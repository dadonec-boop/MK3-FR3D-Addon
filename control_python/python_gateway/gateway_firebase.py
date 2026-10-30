"""Cliente Firebase RTDB para gateway (reemplaza Totem cuando firebase_enabled)."""
from __future__ import annotations

import socket
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from fr3d_totem_bridge import totem_safe_lines
from fr3d_totem_commands import (
    build_totem_help_lines,
    build_totem_unknown_help_lines,
    parse_totem_command,
)

from python_gateway.gateway_firebase_auth import (
    GatewayFirebaseAuthError,
    GatewayFirebaseAuthSession,
    firebase_auth_config_from_gateway_cfg,
    resolve_firebase_auth_email,
    resolve_firebase_auth_password,
    resolve_firebase_web_api_key,
    _MIN_AUTH_RETRY_S,
    _QUOTA_BACKOFF_S,
)
from python_gateway.gateway_rtdb_client import GatewayRtdbClient, RtdbListenEvent
from python_gateway.gateway_config import parse_bool, parse_float
from python_gateway.gateway_identity import (
    GatewayIdentity,
    TOKEN_ALPHABET,
    TOKEN_LENGTH,
    generate_gateway_token,
    identity_store_path,
    load_persisted_token,
    read_gateway_identity,
    save_persisted_token,
)
from python_gateway.gateway_pi_host import (
    get_wlan_ipv4,
    is_gateway_network_up,
    is_linux_gateway_host,
    gateway_host_type,
)
from python_gateway.gateway_serial import resolve_mk3_port
from python_gateway.gateway_version import read_gateway_version

if TYPE_CHECKING:
    from python_gateway.gateway_runtime import GatewayRuntime

CommandExecutor = Callable[[str], Tuple[List[str], str]]
StatusProvider = Callable[[], List[str]]

_PRESENCE_INTERVAL_S = 30.0
_COMMAND_POLL_INTERVAL_S = 2.0
_DEFAULT_COMMAND_DRAIN_IDLE_MINUTES = 10.0
_RTDB_CLEANUP_INTERVAL_S = 3600.0
_DEFAULT_RTDB_CLEANUP_MINUTES = 10.0
_DESTRUCTIVE_RESTART_DELAY_S = 1.5
_RECONNECT_PAUSE_S = 3.0
_NETWORK_WAIT_S = 2.0
# Espera del lock de ejecucion para un POLL3 con comando adjunto, antes de
# devolver ERROR. Debe quedar por debajo del timeout de Flutter (20 s) con
# margen para la escritura RTDB + reintentos.
_POLL_CMD_LOCK_WAIT_S = 12.0
_MAX_TOKEN_ATTEMPTS = 32
_DESTRUCTIVE_PI_KINDS = frozenset({"pi_reboot", "pi_restart_gateway"})


class GatewayFirebaseClient:
    def __init__(
        self,
        cfg: Dict[str, str],
        status_provider: StatusProvider,
        command_executor: CommandExecutor,
        *,
        line_label: str = "",
        on_connected: Optional[Callable[[bool], None]] = None,
        status_cache_provider: Optional[StatusProvider] = None,
    ) -> None:
        self._cfg = dict(cfg)
        self._status_provider = status_provider
        self._status_cache_provider = status_cache_provider or status_provider
        self._command_executor = command_executor
        self._line_label = line_label
        self._on_connected = on_connected
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._presence_thread: Optional[threading.Thread] = None
        self._listener = None
        self._rtdb: Optional[GatewayRtdbClient] = None
        self._auth: Optional[GatewayFirebaseAuthSession] = None
        self._identity: GatewayIdentity = read_gateway_identity()
        self._token = ""
        self._link_ok = False
        self._cmd_lock = threading.Lock()
        self._recent_command_ids: deque[str] = deque(maxlen=256)
        self._in_flight_command_ids: set[str] = set()
        # Serial MK3: polls que no consiguen el lock responden al toque con cache
        # (evita cola de POLL3 >20s → TimeoutException en Flutter).
        self._exec_lock = threading.Lock()
        # Comandos de archivo (CSV FILE *): lock aparte, no frenan la telemetria.
        self._disk_lock = threading.Lock()
        self._status_lines: List[str] = ["[FR3D] STATUS", "Sin datos aun"]
        # Ultimo payload POLL3 valido (v1;...) para el cache: nunca devolver el
        # bloque STATUS de texto a un POLL3 (Flutter lo descartaria).
        self._last_poll3_payload: List[str] = []
        self._last_command_activity_mono = time.monotonic()

    @property
    def connected(self) -> bool:
        return self._link_ok

    @property
    def token(self) -> str:
        return self._token

    @property
    def gateway_key(self) -> str:
        return self._identity.gateway_key

    def start(self) -> None:
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="gateway-firebase", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._close_listener()
        if self._rtdb is not None and self._identity.valid:
            try:
                self._set_presence(online=False)
            except Exception:
                pass
        for th in (self._thread, self._presence_thread):
            if th is not None and th.is_alive() and th is not threading.current_thread():
                th.join(timeout=4.0)
        self._thread = None
        self._presence_thread = None
        self._apply_link_state(False)

    def update_status_cache(self) -> None:
        try:
            lines = self._status_cache_provider()
            if lines:
                self._status_lines = totem_safe_lines(list(lines))
        except Exception:
            pass

    def _apply_link_state(self, ok: bool) -> None:
        if ok == self._link_ok:
            return
        self._link_ok = ok
        if self._on_connected:
            self._on_connected(ok)

    def _init_client(self) -> None:
        if self._auth is None:
            self._auth = GatewayFirebaseAuthSession(
                api_key=resolve_firebase_web_api_key(self._cfg),
                email=resolve_firebase_auth_email(self._cfg),
                password=resolve_firebase_auth_password(self._cfg),
            )
        self._auth.sign_in()
        self._rtdb = GatewayRtdbClient(self._database_url(), self._auth)

    def _database_url(self) -> str:
        url = (self._cfg.get("firebase_database_url") or "").strip()
        if url:
            return url
        return "https://fr3d-3889a-default-rtdb.firebaseio.com"

    def _token_entry_matches_us(self, token: str) -> bool:
        if self._rtdb is None or not token:
            return False
        try:
            entry = self._rtdb.get(f"gatewaysByToken/{token}")
        except Exception:
            return False
        if not isinstance(entry, dict):
            return False
        return str(entry.get("gatewayKey") or "") == self._identity.gateway_key

    def _lookup_token_in_catalog(self) -> str:
        """Sin escaneo global: solo token ya guardado en config si es valido."""
        if self._rtdb is None:
            return ""
        try:
            raw_cfg = self._rtdb.get(
                f"gateways/{self._identity.gateway_key}/config/token"
            )
        except Exception as exc:
            print(f"[Gateway Firebase] config token: {exc}", flush=True)
            return ""
        if not isinstance(raw_cfg, str):
            return ""
        token = raw_cfg.strip().upper()
        if token and self._token_entry_matches_us(token):
            return token
        return ""

    def _resolve_token(self) -> str:
        store = identity_store_path()
        token = load_persisted_token(store, self._identity)
        if token:
            return token

        if self._rtdb is None:
            return ""

        cfg_token = None
        try:
            raw_cfg = self._rtdb.get(
                f"gateways/{self._identity.gateway_key}/config/token"
            )
            if isinstance(raw_cfg, str):
                cfg_token = raw_cfg
        except Exception as exc:
            print(
                f"[Gateway Firebase] config/token no legible (gateway nuevo?): {exc}",
                flush=True,
            )
        if cfg_token:
            token = cfg_token.strip().upper()
            if token:
                save_persisted_token(store, self._identity, token)
                return token

        token = self._lookup_token_in_catalog()
        if token:
            save_persisted_token(store, self._identity, token)
            return token

        for _ in range(_MAX_TOKEN_ATTEMPTS):
            candidate = generate_gateway_token()
            if self._reserve_token(candidate):
                save_persisted_token(store, self._identity, candidate)
                return candidate
        raise RuntimeError("No se pudo reservar token unico en gatewaysByToken")

    def _reserve_token(self, token: str) -> bool:
        assert self._rtdb is not None
        try:
            existing = self._rtdb.get(f"gatewaysByToken/{token}")
        except Exception:
            existing = None
        if existing is not None:
            return False
        now_ms = int(time.time() * 1000)
        self._rtdb.set(
            f"gatewaysByToken/{token}",
            {
                "gatewayKey": self._identity.gateway_key,
                "serial": self._identity.serial,
                "mac": self._identity.mac,
                "createdAt": now_ms,
            },
        )
        return True

    def _register_gateway(self) -> None:
        assert self._rtdb is not None
        label = (self._cfg.get("ui_line_label") or socket.gethostname() or "pi").strip()
        now_ms = int(time.time() * 1000)
        self._rtdb.update(
            f"gateways/{self._identity.gateway_key}/config",
            {"token": self._token, "label": label},
        )
        self._set_presence(online=True, now_ms=now_ms)

    def _set_presence(self, *, online: bool, now_ms: Optional[int] = None) -> None:
        assert self._rtdb is not None
        ts = now_ms if now_ms is not None else int(time.time() * 1000)
        lan_ip = (get_wlan_ipv4() or "").strip()
        if lan_ip in ("0.0.0.0", "127.0.0.1"):
            lan_ip = ""
        payload = {
            "gatewayKey": self._identity.gateway_key,
            "serial": self._identity.serial,
            "mac": self._identity.mac,
            "token": self._token,
            "hostname": socket.gethostname(),
            "hostType": gateway_host_type(),
            "mk3Port": resolve_mk3_port(self._cfg),
            "lanIp": lan_ip,
            "version": read_gateway_version(),
            "online": bool(online),
            "lastSeen": ts,
        }
        self._rtdb.update(
            f"gateways/{self._identity.gateway_key}/presence",
            payload,
        )

    def _presence_loop(self) -> None:
        while not self._stop.wait(_PRESENCE_INTERVAL_S):
            try:
                if self._link_ok:
                    self._set_presence(online=True)
            except Exception as exc:
                print(f"[Gateway Firebase] presence: {exc}", flush=True)

    def _close_listener(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            try:
                listener.close()
            except Exception:
                pass

    def _commands_path(self) -> str:
        return f"gateways/{self._identity.gateway_key}/commands"

    def _responses_path(self) -> str:
        return f"gateways/{self._identity.gateway_key}/responses"

    def _command_drain_idle_s(self) -> float:
        minutes = parse_float(
            self._cfg.get("firebase_command_drain_idle_minutes"),
            _DEFAULT_COMMAND_DRAIN_IDLE_MINUTES,
        )
        if minutes <= 0:
            return 0.0
        return minutes * 60.0

    def _touch_command_activity(self) -> None:
        self._last_command_activity_mono = time.monotonic()

    def _fetch_pending_commands(self) -> Dict[str, Dict[str, Any]]:
        assert self._rtdb is not None
        try:
            pending = self._rtdb.query_equal_to(
                self._commands_path(), "status", "pending"
            )
            if pending:
                return {
                    str(cmd_id): dict(data)
                    for cmd_id, data in pending.items()
                    if isinstance(data, dict)
                }
        except Exception as exc:
            print(f"[Gateway Firebase] query pending: {exc}", flush=True)

        try:
            all_cmds = self._rtdb.get(self._commands_path()) or {}
        except Exception as exc:
            print(f"[Gateway Firebase] drain pending fallback: {exc}", flush=True)
            return {}
        if not isinstance(all_cmds, dict):
            return {}
        return {
            str(cmd_id): dict(data)
            for cmd_id, data in all_cmds.items()
            if isinstance(data, dict) and str(data.get("status") or "") == "pending"
        }

    def _poll_pending_commands(self) -> None:
        """Fallback: poll RTDB if SSE listener misses events (Auth REST on Windows)."""
        pending = self._fetch_pending_commands()
        if not pending:
            return
        for cmd_id, data in pending.items():
            self._schedule_command(str(cmd_id), data)

    def _maybe_drain_idle(self, idle_s: float) -> int:
        if idle_s <= 0:
            return 0
        if time.monotonic() - self._last_command_activity_mono < idle_s:
            return 0
        processed = self._drain_pending_commands()
        self._touch_command_activity()
        if processed:
            print(
                f"[Gateway Firebase] drain idle ({idle_s / 60.0:.0f} min sin actividad): "
                f"{processed} pending",
                flush=True,
            )
        return processed

    def _rtdb_cleanup_cutoff_ms(self) -> Optional[int]:
        if not parse_bool(self._cfg.get("firebase_rtdb_cleanup_enabled"), True):
            return None
        minutes_raw = self._cfg.get("firebase_rtdb_cleanup_minutes")
        if minutes_raw is not None and str(minutes_raw).strip() != "":
            minutes = parse_float(minutes_raw, _DEFAULT_RTDB_CLEANUP_MINUTES)
        else:
            hours = parse_float(
                self._cfg.get("firebase_rtdb_cleanup_hours"),
                _DEFAULT_RTDB_CLEANUP_MINUTES / 60.0,
            )
            minutes = hours * 60.0
        if minutes <= 0:
            return None
        return int(time.time() * 1000) - int(minutes * 60 * 1000)

    @staticmethod
    def _entry_timestamp_ms(data: Dict[str, Any]) -> Optional[int]:
        for key in ("doneAt", "createdAt", "ts"):
            val = data.get(key)
            if val is None:
                continue
            try:
                return int(val)
            except (TypeError, ValueError):
                continue
        return None

    def _cleanup_stale_rtdb(self) -> None:
        if self._rtdb is None:
            return
        cutoff_ms = self._rtdb_cleanup_cutoff_ms()
        if cutoff_ms is None:
            return

        removed_cmds = 0
        removed_resps = 0
        for rel_path, label in (
            (self._commands_path(), "commands"),
            (self._responses_path(), "responses"),
        ):
            try:
                all_nodes = self._rtdb.get(rel_path) or {}
            except Exception as exc:
                print(f"[Gateway Firebase] cleanup {label}: {exc}", flush=True)
                continue
            if not isinstance(all_nodes, dict):
                continue
            for node_id, data in all_nodes.items():
                if not isinstance(data, dict):
                    continue
                ts = self._entry_timestamp_ms(data)
                if ts is None or ts > cutoff_ms:
                    continue
                try:
                    self._rtdb.delete(f"{rel_path}/{node_id}")
                    if label == "commands":
                        removed_cmds += 1
                    else:
                        removed_resps += 1
                except Exception as exc:
                    print(
                        f"[Gateway Firebase] cleanup delete {label}/{node_id}: {exc}",
                        flush=True,
                    )

        if removed_cmds or removed_resps:
            minutes_raw = self._cfg.get("firebase_rtdb_cleanup_minutes")
            if minutes_raw is not None and str(minutes_raw).strip() != "":
                retention = parse_float(minutes_raw, _DEFAULT_RTDB_CLEANUP_MINUTES)
                retention_label = f"{retention:.0f} min"
            else:
                hours = parse_float(
                    self._cfg.get("firebase_rtdb_cleanup_hours"),
                    _DEFAULT_RTDB_CLEANUP_MINUTES / 60.0,
                )
                retention_label = f"{hours:.1f} h"
            print(
                "[Gateway Firebase] Limpieza RTDB: "
                f"{removed_cmds} commands, {removed_resps} responses "
                f"(mas de {retention_label})",
                flush=True,
            )

    def _claim_command(self, cmd_id: str) -> bool:
        with self._cmd_lock:
            if cmd_id in self._recent_command_ids:
                return False
            if cmd_id in self._in_flight_command_ids:
                return False
            self._in_flight_command_ids.add(cmd_id)
            return True

    def _release_command(self, cmd_id: str) -> None:
        with self._cmd_lock:
            self._in_flight_command_ids.discard(cmd_id)

    def _forget_recent_command(self, cmd_id: str) -> None:
        with self._cmd_lock:
            if cmd_id not in self._recent_command_ids:
                return
            self._recent_command_ids = deque(
                (x for x in self._recent_command_ids if x != cmd_id),
                maxlen=self._recent_command_ids.maxlen,
            )

    def _command_in_flight(self, cmd_id: str) -> bool:
        with self._cmd_lock:
            return cmd_id in self._in_flight_command_ids

    def _republish_existing_response(self, cmd_id: str, resp: Dict[str, Any]) -> bool:
        """Re-escribe la respuesta para re-disparar el listener de Flutter."""
        if self._rtdb is None:
            return False
        now_ms = int(time.time() * 1000)
        payload = dict(resp)
        payload["ts"] = now_ms
        payload["doneAt"] = now_ms
        resp_path = f"{self._responses_path()}/{cmd_id}"
        cmd_path = f"{self._commands_path()}/{cmd_id}"
        try:
            self._rtdb.set(resp_path, payload)
            self._rtdb.update(cmd_path, {"status": "done", "doneAt": now_ms})
        except Exception as exc:
            print(
                f"[Gateway Firebase] republicar respuesta {cmd_id}: {exc}",
                flush=True,
            )
            return False
        with self._cmd_lock:
            if cmd_id not in self._recent_command_ids:
                self._recent_command_ids.append(cmd_id)
        print(
            f"[Gateway Firebase] respuesta {cmd_id} republicada "
            f"(duplicado; Flutter re-notificado)",
            flush=True,
        )
        return True

    def _handle_duplicate_command(
        self,
        cmd_id: str,
        data: Dict[str, Any],
        *,
        allow_destructive: bool = True,
        run_rtdb_cleanup: bool = False,
    ) -> None:
        """Si el claim falla: o sigue en vuelo, o hay que republicar/reprocesar.

        Antes solo se logueaba 'duplicado ignorado' sin tocar responses/ — Flutter
        seguia esperando hasta TimeoutException 20s.
        """
        if self._command_in_flight(cmd_id):
            # Todavia procesando el primero; no spamear journal.
            return

        if self._rtdb is None:
            return

        try:
            cmd_now = self._rtdb.get(f"{self._commands_path()}/{cmd_id}")
        except Exception:
            cmd_now = None
        if isinstance(cmd_now, dict) and str(cmd_now.get("status") or "") == "done":
            # Query pending obsoleto; no republicar en loop.
            with self._cmd_lock:
                if cmd_id not in self._recent_command_ids:
                    self._recent_command_ids.append(cmd_id)
            return

        try:
            resp = self._rtdb.get(f"{self._responses_path()}/{cmd_id}")
        except Exception as exc:
            print(
                f"[Gateway Firebase] duplicado {cmd_id} get response: {exc}",
                flush=True,
            )
            resp = None

        if isinstance(resp, dict) and (
            resp.get("lines") is not None or resp.get("type") is not None
        ):
            self._republish_existing_response(cmd_id, resp)
            return

        # Marcado reciente o carrera, pero sin respuesta util: reprocesar.
        self._forget_recent_command(cmd_id)
        print(
            f"[Gateway Firebase] duplicado sin respuesta — reprocesar {cmd_id}",
            flush=True,
        )
        if not self._claim_command(cmd_id):
            return
        threading.Thread(
            target=self._process_command,
            args=(cmd_id, data),
            kwargs={
                "allow_destructive": allow_destructive,
                "run_rtdb_cleanup": run_rtdb_cleanup,
            },
            name=f"gateway-firebase-cmd-{cmd_id[:8]}",
            daemon=True,
        ).start()

    def _schedule_command(
        self,
        cmd_id: str,
        data: Dict[str, Any],
        *,
        allow_destructive: bool = True,
        run_rtdb_cleanup: bool = False,
    ) -> None:
        if str(data.get("status") or "") != "pending":
            return
        if not self._claim_command(cmd_id):
            self._handle_duplicate_command(
                cmd_id,
                data,
                allow_destructive=allow_destructive,
                run_rtdb_cleanup=run_rtdb_cleanup,
            )
            return
        threading.Thread(
            target=self._process_command,
            args=(cmd_id, data),
            kwargs={
                "allow_destructive": allow_destructive,
                "run_rtdb_cleanup": run_rtdb_cleanup,
            },
            name=f"gateway-firebase-cmd-{cmd_id[:8]}",
            daemon=True,
        ).start()

    def _on_command_event(self, event: RtdbListenEvent) -> None:
        if self._stop.is_set():
            return
        if event.event_type not in ("put", "patch", "child_added"):
            return
        self._touch_command_activity()

        path = (event.path or "/").strip("/")
        data = event.data

        if not path:
            if isinstance(data, dict):
                for cmd_id, cmd_data in data.items():
                    if isinstance(cmd_data, dict):
                        self._schedule_command(str(cmd_id), cmd_data)
            return

        if "/" in path:
            cmd_id = path.split("/", 1)[0]
            try:
                cmd_data = self._rtdb.get(f"{self._commands_path()}/{cmd_id}")
            except Exception as exc:
                print(
                    f"[Gateway Firebase] comando {cmd_id} (evento {event.event_type}): {exc}",
                    flush=True,
                )
                return
            if isinstance(cmd_data, dict):
                self._schedule_command(cmd_id, cmd_data)
            return

        if isinstance(data, dict):
            self._schedule_command(path, data)

    def _drain_pending_commands(self) -> int:
        pending_cmds = self._fetch_pending_commands()
        for cmd_id, data in pending_cmds.items():
            self._schedule_command(str(cmd_id), data, allow_destructive=False)
        return len(pending_cmds)

    def _resolve_command(self, message: str) -> tuple[List[str], str]:
        parsed = parse_totem_command(message)
        if parsed.kind == "empty":
            return ["[FR3D] Comando vacio."], "WARNING"
        if parsed.kind == "invalid":
            return [f"[FR3D] Valor numerico invalido: {parsed.raw}"], "WARNING"
        if parsed.kind == "status":
            try:
                lines = self._status_provider()
                if lines:
                    self._status_lines = totem_safe_lines(list(lines))
            except Exception:
                pass
            return list(self._status_lines), "INFO"
        if parsed.kind == "help":
            return build_totem_help_lines(include_pi_host=is_linux_gateway_host()), "INFO"
        if parsed.kind == "echo":
            upper = message.upper()
            payload = message[4:].strip() if upper.startswith("ECHO") else message
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            label = (self._line_label or "FR3D").strip() or "FR3D"
            return [
                "[FR3D] ECHO OK",
                f"Recibido: {payload or '(vacio)'}",
                f"Linea: {label}",
                f"Hora local: {now}",
            ], "INFO"
        if parsed.kind == "unknown":
            return build_totem_unknown_help_lines(
                message, include_pi_host=is_linux_gateway_host()
            ), "WARNING"
        return self._command_executor(message)

    def _destructive_pi_ack(self, kind: str) -> Tuple[List[str], str]:
        if kind == "pi_restart_gateway":
            return (
                [
                    "[FR3D] PI REINICIAR GATEWAY",
                    "Reinicio del servicio solicitado.",
                    "El gateway volvera en unos segundos.",
                ],
                "INFO",
            )
        return (
            [
                "[FR3D] PI REINICIAR",
                "Reinicio de la Raspberry solicitado.",
                "La Pi volvera en ~1 min.",
            ],
            "INFO",
        )

    def _schedule_destructive_pi_action(self, kind: str) -> None:
        def _run() -> None:
            time.sleep(_DESTRUCTIVE_RESTART_DELAY_S)
            try:
                from python_gateway.gateway_pi_host import pi_reboot, pi_restart_gateway

                if kind == "pi_restart_gateway":
                    pi_restart_gateway()
                elif kind == "pi_reboot":
                    pi_reboot()
            except Exception as exc:
                print(f"[Gateway Firebase] accion reinicio: {exc}", flush=True)

        threading.Thread(
            target=_run,
            name=f"gateway-firebase-{kind}",
            daemon=True,
        ).start()

    def _finish_command(self, cmd_id: str, lines: List[str], entry_type: str) -> bool:
        if self._auth is not None:
            try:
                self._auth.refresh_or_sign_in()
            except Exception as exc:
                print(
                    f"[Gateway Firebase] auth refresh antes de respuesta {cmd_id}: {exc}",
                    flush=True,
                )
        now_ms = int(time.time() * 1000)
        resp_path = f"{self._responses_path()}/{cmd_id}"
        cmd_path = f"{self._commands_path()}/{cmd_id}"
        payload = {
            "type": entry_type,
            "lines": totem_safe_lines(list(lines)),
            "ts": now_ms,
            "doneAt": now_ms,
        }
        try:
            self._rtdb.set(resp_path, payload)
        except Exception as exc:
            print(f"[Gateway Firebase] respuesta {cmd_id} PUT responses: {exc}", flush=True)
            return False
        try:
            self._rtdb.update(cmd_path, {"status": "done", "doneAt": now_ms})
        except Exception as exc:
            print(
                f"[Gateway Firebase] respuesta {cmd_id} PATCH command "
                f"(responses OK): {exc}",
                flush=True,
            )
            return False
        with self._cmd_lock:
            self._recent_command_ids.append(cmd_id)
        print(
            f"[Gateway Firebase] respuesta {cmd_id} OK ({len(lines)} lineas)",
            flush=True,
        )
        return True

    @staticmethod
    def _is_poll_like(message: str) -> bool:
        u = (message or "").strip().upper()
        if not u:
            return False
        if u.startswith("POLL3") or u.startswith("POLL2"):
            return True
        if u == "STATUS" or u == "HALL STATUS":
            return True
        if ";HALL STATUS" in u:
            return True
        return False

    @staticmethod
    def _is_disk_only(message: str) -> bool:
        """CSV FILE LIST/READ/SAVE/NOTE/DELETE: solo tocan csv_logs/, no el serial.

        Van por un lock propio para no congelar la telemetria POLL3 mientras se
        guarda o se lee una corrida larga.
        """
        u = (message or "").strip().upper()
        if not u.startswith("CSV FILE "):
            return False
        verb = u.split()[2] if len(u.split()) >= 3 else ""
        return verb in ("LIST", "READ", "SAVE", "NOTE", "DELETE")

    @staticmethod
    def _poll3_carries_command(message: str) -> bool:
        """True si el POLL3 lleva un comando adjunto (no es solo telemetria)."""
        u = (message or "").strip().upper()
        if not u.startswith("POLL3"):
            return False
        try:
            from python_gateway.gateway_poll3 import _parse_poll3_request

            _csv_n, cmd_lines = _parse_poll3_request(message)
        except Exception:
            # Ante la duda, tratarlo como comando: mejor esperar que descartar.
            return True
        return bool(cmd_lines)

    def _is_cacheable_poll(self, message: str) -> bool:
        """
        Solo cacheable si NO puede perder una accion: telemetria pura o consultas
        de solo lectura. Un POLL3 con comando adjunto NO entra por el cache
        (se ejecuta de verdad o devuelve ERROR explicito).
        """
        u = (message or "").strip().upper()
        if not u:
            return False
        if u in ("STATUS", "HALL STATUS", "POLL2", "POLL3"):
            return True
        if u.startswith("POLL2"):
            return True
        if u.startswith("POLL3"):
            return not self._poll3_carries_command(message)
        return False

    @staticmethod
    def _extract_poll3_payload(lines: List[str]) -> Optional[List[str]]:
        """Devuelve ['[FR3D] POLL3', 'v1;...'] si las lineas traen payload POLL2 v1."""
        for ln in lines:
            s = (ln or "").strip()
            if s.startswith("v1;"):
                return ["[FR3D] POLL3", s]
        return None

    def _cached_poll_lines(self, message: str = "") -> List[str]:
        u = (message or "").strip().upper()
        # POLL3: responder el ultimo payload v1; valido (Flutter lo parsea).
        # Devolver el bloque STATUS de texto haria que Flutter lo descarte
        # con "invalid POLL3 payload".
        if u.startswith("POLL3") and self._last_poll3_payload:
            return list(self._last_poll3_payload)
        if self._status_lines:
            return list(self._status_lines)
        return ["[FR3D] POLL3", "busy (no cache yet)"]

    def _finish_with_retries(
        self, cmd_id: str, lines: List[str], entry_type: str
    ) -> bool:
        for attempt in range(1, 4):
            if self._finish_command(cmd_id, lines, entry_type):
                return True
            print(
                f"[Gateway Firebase] finish {cmd_id} intento {attempt}/3 fallo; "
                "reintento…",
                flush=True,
            )
            time.sleep(0.4 * attempt)
        print(
            f"[Gateway Firebase] finish {cmd_id} agoto reintentos "
            "(Flutter vera timeout)",
            flush=True,
        )
        return False

    def _process_command(
        self,
        cmd_id: str,
        data: Dict[str, Any],
        *,
        allow_destructive: bool = True,
        run_rtdb_cleanup: bool = False,
    ) -> None:
        try:
            message = str(data.get("text") or data.get("message") or "").strip()
            print(
                f"[Gateway Firebase] Procesando comando {cmd_id}: {message or '(vacio)'}",
                flush=True,
            )

            parsed = parse_totem_command(message)
            if parsed.kind in _DESTRUCTIVE_PI_KINDS:
                if not allow_destructive:
                    self._finish_with_retries(
                        cmd_id,
                        [
                            "[FR3D] Comando de reinicio pendiente tras corte.",
                            "No re-ejecutado al arrancar el gateway.",
                            "Envie el comando de nuevo si aun lo necesita.",
                        ],
                        "WARNING",
                    )
                    return
                lines, entry_type = self._destructive_pi_ack(parsed.kind)
                if self._finish_with_retries(cmd_id, lines, entry_type):
                    self._schedule_destructive_pi_action(parsed.kind)
                return

            poll_like = self._is_poll_like(message)
            cacheable_poll = self._is_cacheable_poll(message)
            try:
                if cacheable_poll:
                    # Telemetria/consulta pura: si el MK3 esta ocupado, responder
                    # YA con el ultimo payload cacheado (Flutter no hace timeout).
                    got_lock = self._exec_lock.acquire(blocking=False)
                    if not got_lock:
                        lines = self._cached_poll_lines(message)
                        print(
                            f"[Gateway Firebase] poll {cmd_id} → cache "
                            "(MK3 ocupado; evita timeout Flutter)",
                            flush=True,
                        )
                        self._finish_with_retries(cmd_id, lines, "INFO")
                        return
                    try:
                        lines, entry_type = self._resolve_command(message)
                    finally:
                        self._exec_lock.release()
                elif poll_like:
                    # POLL3 CON comando adjunto: NUNCA descartar en silencio.
                    # Esperar el lock acotado (< timeout Flutter) y ejecutar de
                    # verdad; si no se libera, ERROR explicito (no falso OK).
                    got_lock = self._exec_lock.acquire(timeout=_POLL_CMD_LOCK_WAIT_S)
                    if not got_lock:
                        print(
                            f"[Gateway Firebase] poll+cmd {cmd_id} → canal ocupado "
                            f"tras {_POLL_CMD_LOCK_WAIT_S:.0f}s (ERROR, no cache)",
                            flush=True,
                        )
                        self._finish_with_retries(
                            cmd_id,
                            [
                                "[FR3D] POLL3",
                                "v1;-;ERROR;canal MK3 ocupado (reintente)",
                                "[FR3D] Canal MK3 ocupado: comando no ejecutado. Reintente.",
                            ],
                            "ERROR",
                        )
                        return
                    try:
                        lines, entry_type = self._resolve_command(message)
                    finally:
                        self._exec_lock.release()
                elif self._is_disk_only(message):
                    with self._disk_lock:
                        lines, entry_type = self._resolve_command(message)
                else:
                    with self._exec_lock:
                        lines, entry_type = self._resolve_command(message)
            except Exception as exc:
                lines = [f"[FR3D] Error interno: {exc}"]
                entry_type = "ERROR"

            if not lines and entry_type == "":
                lines = ["[FR3D] Comando ignorado (sin respuesta)."]
                entry_type = "WARNING"

            if lines and entry_type == "INFO" and poll_like:
                self._status_lines = totem_safe_lines(list(lines))
                payload = self._extract_poll3_payload(lines)
                if payload is not None:
                    self._last_poll3_payload = payload

            self._finish_with_retries(cmd_id, lines, entry_type)
        finally:
            self._release_command(cmd_id)
            if run_rtdb_cleanup:
                try:
                    self._cleanup_stale_rtdb()
                except Exception as exc:
                    print(f"[Gateway Firebase] cleanup RTDB: {exc}", flush=True)

    def _mark_offline(self) -> None:
        self._close_listener()
        try:
            if self._rtdb is not None and self._identity.valid and self._token:
                self._set_presence(online=False)
        except Exception as exc:
            print(f"[Gateway Firebase] presence offline: {exc}", flush=True)
        self._apply_link_state(False)

    def _wait_for_network(self) -> bool:
        """Espera red util en gateway Linux; marca offline mientras tanto."""
        if not is_linux_gateway_host():
            return True
        logged_wait = False
        while not self._stop.is_set():
            if is_gateway_network_up():
                return True
            self._mark_offline()
            if not logged_wait:
                print("[Gateway Firebase] Sin red: esperando...", flush=True)
                logged_wait = True
            if self._stop.wait(_NETWORK_WAIT_S):
                return False
        return False

    def _reconnect_listener(self, *, reason: str) -> int:
        """Cierra y reabre el listener RTDB; drena pending al volver."""
        self._close_listener()
        pending = 0
        try:
            self._listener = self._rtdb.listen(
                self._commands_path(),
                self._on_command_event,
            )
            pending = self._drain_pending_commands()
            self._touch_command_activity()
            if pending:
                print(
                    f"[Gateway Firebase] drain {reason}: {pending} pending",
                    flush=True,
                )
        except Exception as exc:
            print(f"[Gateway Firebase] listener {reason}: {exc}", flush=True)
            self._close_listener()
            raise
        return pending

    def _run(self) -> None:
        if not self._identity.valid:
            print(
                "[Gateway Firebase] Identidad invalida (serial/MAC). "
                "En Pi usa serial+wlan0; en Windows MachineGuid+MAC.",
                flush=True,
            )
            return

        while not self._stop.is_set():
            self._mark_offline()
            try:
                if not self._wait_for_network():
                    break
                self._init_client()
                self._token = self._resolve_token()
                self._register_gateway()
                print(
                    "[Gateway Firebase] Registrado "
                    f"gatewayKey={self._identity.gateway_key} token={self._token}",
                    flush=True,
                )
                # Marcar online ANTES del drain: WHOAREYOU/STATUS no deben
                # decir "NO CONECTADO" mientras se procesan pending.
                self._apply_link_state(True)
                pending = self._reconnect_listener(reason="inicial")
                try:
                    self._cleanup_stale_rtdb()
                except Exception as exc:
                    print(f"[Gateway Firebase] cleanup RTDB: {exc}", flush=True)
                self.update_status_cache()
                self._presence_thread = threading.Thread(
                    target=self._presence_loop,
                    name="gateway-firebase-presence",
                    daemon=True,
                )
                self._presence_thread.start()
                idle_drain_s = self._command_drain_idle_s()
                last_cleanup = time.monotonic()
                last_command_poll = time.monotonic()
                network_was_up = True
                network_down_hits = 0
                while not self._stop.is_set():
                    now = time.monotonic()
                    network_up = is_gateway_network_up()
                    if not network_up:
                        network_down_hits += 1
                        # Debounce: un falso negativo de nmcli no debe marcar offline.
                        if network_down_hits < 3:
                            time.sleep(0.5)
                            continue
                        if network_was_up:
                            print(
                                "[Gateway Firebase] Red perdida: cerrando listener",
                                flush=True,
                            )
                        self._mark_offline()
                        network_was_up = False
                        break
                    network_down_hits = 0

                    if not network_was_up:
                        print(
                            "[Gateway Firebase] Red restaurada: reconectando listener",
                            flush=True,
                        )
                        try:
                            self._set_presence(online=True)
                            self._apply_link_state(True)
                            self._reconnect_listener(reason="red")
                        except Exception as exc:
                            print(
                                f"[Gateway Firebase] reconexion red: {exc}",
                                flush=True,
                            )
                            break
                    network_was_up = True

                    if idle_drain_s > 0:
                        try:
                            self._maybe_drain_idle(idle_drain_s)
                        except Exception as exc:
                            print(
                                f"[Gateway Firebase] drain idle: {exc}",
                                flush=True,
                            )
                    if now - last_command_poll >= _COMMAND_POLL_INTERVAL_S:
                        last_command_poll = now
                        try:
                            self._poll_pending_commands()
                        except Exception as exc:
                            print(
                                f"[Gateway Firebase] poll pending: {exc}",
                                flush=True,
                            )
                    if now - last_cleanup >= _RTDB_CLEANUP_INTERVAL_S:
                        last_cleanup = now
                        try:
                            self._cleanup_stale_rtdb()
                        except Exception as exc:
                            print(f"[Gateway Firebase] cleanup RTDB: {exc}", flush=True)
                    time.sleep(0.5)
            except GatewayFirebaseAuthError as exc:
                blocked = self._auth.blocked_seconds() if self._auth else 0.0
                msg = str(exc)
                if exc.quota_exceeded or "QUOTA_EXCEEDED" in msg:
                    pause = max(_QUOTA_BACKOFF_S, blocked)
                    print(
                        "[Gateway Firebase] Cuota Auth excedida — "
                        f"esperando {pause:.0f}s antes de reintentar login.",
                        flush=True,
                    )
                elif "espere" in msg.lower() and blocked <= 0:
                    # Throttle local: esperar el tiempo que pide Auth (no reintentar cada 3s).
                    import re

                    m = re.search(r"espere\s+(\d+)s", msg, re.I)
                    pause = float(m.group(1)) + 1.0 if m else _MIN_AUTH_RETRY_S
                    print(f"[Gateway Firebase] Auth: {exc}", flush=True)
                else:
                    pause = max(_RECONNECT_PAUSE_S, blocked, _MIN_AUTH_RETRY_S)
                    print(f"[Gateway Firebase] Auth: {exc}", flush=True)
                self._mark_offline()
                if self._stop.wait(pause):
                    break
            except Exception as exc:
                pause = _RECONNECT_PAUSE_S
                print(f"[Gateway Firebase] Error: {exc}", flush=True)
                self._mark_offline()
                if self._stop.wait(pause):
                    break
                print(f"[Gateway Firebase] Reintento en {pause:.0f} s.", flush=True)


_DEFAULT_SA_FILENAMES = (
    "firebase_service_account.json",
    "fr3d-gateway-service-account.json",
)


def resolve_firebase_service_account_path(cfg: Dict[str, str]) -> str:
    """Legacy Admin SDK path (dev only — release gateways use Auth email/password)."""
    from python_gateway.gateway_paths import app_dir

    root = app_dir()
    candidates: list[Path] = []
    raw = (cfg.get("firebase_service_account") or "").strip()
    if raw:
        p = Path(raw)
        if p.is_absolute():
            candidates.append(p)
        else:
            candidates.append(root / p)
            candidates.append(Path.cwd() / p)
    for name in _DEFAULT_SA_FILENAMES:
        candidates.append(root / name)
        candidates.append(root / "secrets" / name)
    seen: set[str] = set()
    for cand in candidates:
        try:
            key = str(cand)
            if key in seen:
                continue
            seen.add(key)
            if cand.is_file():
                return str(cand.resolve())
        except OSError:
            continue
    return ""


def firebase_config_from_gateway_cfg(cfg: Dict[str, str]) -> Optional[Dict[str, str]]:
    from python_gateway.gateway_cloud_link import firebase_enabled

    if not firebase_enabled(cfg):
        return None
    auth_cfg = firebase_auth_config_from_gateway_cfg(cfg)
    if not auth_cfg:
        return None
    return auth_cfg
