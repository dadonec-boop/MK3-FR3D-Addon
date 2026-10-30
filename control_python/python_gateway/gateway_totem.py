"""Cliente Totem integrado (sin TotemBridge / sin subproceso)."""
from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

import requests
import socketio

from fr3d_totem_bridge import totem_safe_lines
from fr3d_totem_commands import (
    build_totem_help_lines,
    build_totem_unknown_help_lines,
    parse_totem_command,
)

from python_gateway.gateway_pi_host import is_linux_gateway_host

if TYPE_CHECKING:
    from python_gateway.gateway_runtime import GatewayRuntime

CommandExecutor = Callable[[str], Tuple[List[str], str]]
StatusProvider = Callable[[], List[str]]
GatewayCfgProvider = Callable[[], Dict[str, str]]

_SESSION_WATCH_INTERVAL_S = 30.0
_RECONNECT_PAUSE_S = 3.0


class GatewayTotemClient:
    def __init__(
        self,
        config: Dict[str, Any],
        status_provider: StatusProvider,
        command_executor: CommandExecutor,
        *,
        line_label: str = "",
        on_connected: Optional[Callable[[bool], None]] = None,
        status_cache_provider: Optional[StatusProvider] = None,
        gateway_cfg_provider: Optional[GatewayCfgProvider] = None,
    ) -> None:
        self._config = dict(config)
        self._status_provider = status_provider
        self._status_cache_provider = status_cache_provider or status_provider
        self._command_executor = command_executor
        self._line_label = line_label
        self._on_connected = on_connected
        self._gateway_cfg_provider = gateway_cfg_provider
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._client: Optional[socketio.Client] = None
        self._active_session_id: int = 0
        self._clients_lock = threading.Lock()
        self._known_clients: List[socketio.Client] = []
        self._status_lines: List[str] = ["[FR3D] STATUS", "Sin datos aun"]
        self._lock = threading.Lock()
        self._cmd_lock = threading.Lock()
        self._recent_command_ids: deque[str] = deque(maxlen=256)
        self._link_ok_cached = False
        self._pending_reconnect_config: Optional[Dict[str, Any]] = None
        self._pending_service_restart = False

    def schedule_reconnect(self, config: Dict[str, Any]) -> None:
        """Desconecta y vuelve a conectar tras responder el comando actual."""
        with self._clients_lock:
            self._pending_reconnect_config = dict(config)

    def schedule_service_restart(self) -> None:
        """Reinicia fr3d-gateway tras responder el comando (cambio de Terminal ID)."""
        with self._clients_lock:
            self._pending_service_restart = True

    def _apply_pending_reconnect(self) -> None:
        with self._clients_lock:
            cfg = self._pending_reconnect_config
            self._pending_reconnect_config = None
        if not cfg:
            return
        self._config = dict(cfg)
        self._active_session_id += 1
        self._disconnect_all_clients()
        self._apply_link_state(False)
        totem_id = str(cfg.get("totem") or "").strip()
        enterprise = str(cfg.get("enterprise") or "").strip()
        print(
            "[Gateway Totem] Reconexion programada "
            f"totem={totem_id} enterprise={enterprise}",
            flush=True,
        )

    def _apply_pending_service_restart(self) -> None:
        with self._clients_lock:
            pending = self._pending_service_restart
            self._pending_service_restart = False
        if not pending:
            return

        def _do() -> None:
            time.sleep(1.0)
            try:
                from python_gateway.gateway_pi_host import pi_restart_gateway

                lines, _ = pi_restart_gateway()
                for line in lines:
                    print(f"[Gateway Totem] {line}", flush=True)
            except Exception as exc:
                print(f"[Gateway Totem] Reinicio servicio error: {exc}", flush=True)

        threading.Thread(
            target=_do,
            name="gateway-svc-restart",
            daemon=True,
        ).start()

    def start(self) -> None:
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_connection, name="gateway-totem", daemon=True)
        self._thread.start()
        self._watch_thread = threading.Thread(
            target=self._session_watch_loop, name="gateway-totem-watch", daemon=True
        )
        self._watch_thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._disconnect_all_clients()
        for th in (self._thread, self._watch_thread):
            if th is not None and th.is_alive() and th is not threading.current_thread():
                th.join(timeout=4.0)
        self._thread = None
        self._watch_thread = None
        if self._on_connected:
            self._on_connected(False)

    @property
    def connected(self) -> bool:
        return self._count_connected_clients() == 1

    def active_session_count(self) -> int:
        return self._count_connected_clients()

    def update_status_cache(self) -> None:
        try:
            lines = self._status_cache_provider()
            if lines:
                with self._lock:
                    self._status_lines = totem_safe_lines(list(lines))
        except Exception:
            pass

    def _build_base_url(self) -> str:
        protocol = str(self._config.get("protocol") or "https").strip() or "https"
        host = str(self._config["host"]).strip()
        return f"{protocol}://{host}"

    def _connection_url(self) -> str:
        totem = str(self._config["totem"]).strip()
        enterprise = str(self._config["enterprise"]).strip()
        return f"{self._build_base_url()}?totem={totem}&enterprise={enterprise}"

    def _namespace(self) -> str:
        namespace = str(self._config.get("namespace") or "caster").strip()
        return namespace if namespace.startswith("/") else f"/{namespace}"

    def _post_action(self, body: Dict[str, Any]) -> None:
        url = f"{self._build_base_url()}/caster/action"
        headers = {
            "enterprise": str(self._config["enterprise"]),
            "totem": str(self._config["totem"]),
            "Content-Type": "application/json",
        }
        requests.post(url, json=body, headers=headers, timeout=30).raise_for_status()

    def _resolve_command(self, message: str) -> tuple[List[str], str]:
        parsed = parse_totem_command(message)
        if parsed.kind == "empty":
            return ["[FR3D] Comando vacio."], "WARNING"
        if parsed.kind == "invalid":
            return [f"[FR3D] Valor numerico invalido: {parsed.raw}"], "WARNING"
        if parsed.kind == "color_invalid":
            return [
                "[FR3D] COLOR: uso CREATE/UPDATE <nombre>, LIST, DELETE <nombre>",
            ], "ERROR"
        if parsed.kind == "material_invalid":
            return [
                "[FR3D] MATERIAL: uso SET <id>, CREATE/UPDATE (3 lineas CSV), LIST, GET <id>, DELETE <id>",
            ], "ERROR"
        if parsed.kind == "status":
            try:
                lines = self._status_provider()
                if lines:
                    with self._lock:
                        self._status_lines = totem_safe_lines(list(lines))
            except Exception:
                pass
            with self._lock:
                return list(self._status_lines), "INFO"
        if parsed.kind == "help":
            return build_totem_help_lines(
                include_pi_host=is_linux_gateway_host()
            ), "INFO"
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

    def _sync_socket_state(self, client: Optional[socketio.Client]) -> bool:
        sock_ok = client is not None and getattr(client, "connected", False)
        self._apply_link_state(sock_ok)
        return sock_ok

    def _apply_link_state(self, ok: bool) -> None:
        if ok == self._link_ok_cached:
            return
        self._link_ok_cached = ok
        if self._on_connected:
            self._on_connected(ok)

    def _prune_dead_clients(self) -> None:
        with self._clients_lock:
            self._known_clients = [
                c for c in self._known_clients if getattr(c, "connected", False)
            ]
            if self._client is not None and self._client not in self._known_clients:
                if getattr(self._client, "connected", False):
                    self._known_clients.append(self._client)
                else:
                    self._client = None

    def _register_client(self, client: socketio.Client) -> None:
        with self._clients_lock:
            if client not in self._known_clients:
                self._known_clients.append(client)

    def _count_connected_clients(self) -> int:
        with self._clients_lock:
            return sum(1 for c in self._known_clients if getattr(c, "connected", False))

    def _disconnect_client(self, client: Optional[socketio.Client]) -> None:
        if client is None:
            return
        try:
            if getattr(client, "connected", False):
                client.disconnect()
        except Exception:
            pass

    def _disconnect_all_clients(self, *, keep: Optional[socketio.Client] = None) -> None:
        with self._clients_lock:
            clients = list(self._known_clients)
        for c in clients:
            if keep is not None and c is keep:
                continue
            self._disconnect_client(c)
        with self._clients_lock:
            if keep is None:
                self._known_clients.clear()
                self._client = None
            else:
                self._known_clients = [c for c in self._known_clients if c is keep]
                self._client = keep

    def _enforce_single_session(self, *, reason: str) -> None:
        """Mantiene una sola sesion Socket.IO local (evita duplicados tras reconexiones)."""
        self._prune_dead_clients()
        n = self._count_connected_clients()
        if n <= 1:
            return
        print(
            f"[Gateway Totem] Vigilancia ({reason}): {n} sesiones locales abiertas; "
            "cerrando conexiones extra.",
            flush=True,
        )
        keep = self._client
        self._disconnect_all_clients(keep=keep)
        if keep is not None and not getattr(keep, "connected", False):
            self._disconnect_all_clients()

    def _session_watch_loop(self) -> None:
        while not self._stop.is_set():
            if self._stop.wait(_SESSION_WATCH_INTERVAL_S):
                break
            try:
                self._prune_dead_clients()
                client = self._client
                if client is not None and getattr(client, "connected", False):
                    self._sync_socket_state(client)
                n = self._count_connected_clients()
                sid = self._active_session_id
                if n > 1:
                    self._enforce_single_session(reason="periodica")
                    n = self._count_connected_clients()
                if n == 1:
                    print(
                        f"[Gateway Totem] Vigilancia: 1 sesion activa (id={sid}).",
                        flush=True,
                    )
                elif n == 0 and self._client is not None:
                    print(
                        "[Gateway Totem] Vigilancia: sin sesion activa; esperando reconexion.",
                        flush=True,
                    )
            except Exception as exc:
                print(f"[Gateway Totem] Vigilancia error: {exc}", flush=True)

    def _make_command_handler(
        self, client: socketio.Client, session_id: int
    ) -> Callable[..., None]:
        def _on_command(*args: Any) -> None:
            if self._stop.is_set():
                return
            if session_id != self._active_session_id:
                return
            if self._client is not client:
                return
            if not args or not isinstance(args[0], dict):
                return
            threading.Thread(
                target=self._process_command,
                args=(args[0], session_id),
                name="gateway-totem-cmd",
                daemon=True,
            ).start()

        return _on_command

    def _process_command(self, payload: Dict[str, Any], session_id: int) -> None:
        if session_id != self._active_session_id:
            return

        command_id = payload.get("_id")
        message = str(payload.get("message", "") or "").strip()

        if command_id:
            cid = str(command_id)
            with self._cmd_lock:
                if cid in self._recent_command_ids:
                    print(f"[Gateway Totem] Comando duplicado ignorado: {cid}", flush=True)
                    return
                self._recent_command_ids.append(cid)

        try:
            lines, entry_type = self._resolve_command(message)
        except Exception as exc:
            lines = [f"[FR3D] Error interno: {exc}"]
            entry_type = "ERROR"

        if not lines and entry_type == "":
            print(
                f"[Gateway Totem] Comando ignorado (sin respuesta): {message!r}",
                flush=True,
            )
            return

        if session_id != self._active_session_id:
            return

        if command_id:
            try:
                self._post_action(
                    {"action": "COMMAND-EXECUTED", "commandId": str(command_id)}
                )
            except requests.RequestException as exc:
                print(f"[Gateway Totem] COMMAND-EXECUTED error: {exc}", flush=True)
                return

        if session_id != self._active_session_id:
            return

        try:
            self._post_action(
                {
                    "action": "CONSOLE",
                    "data": [
                        {
                            "type": entry_type,
                            "ts": time.time() * 1000,
                            "messages": totem_safe_lines(list(lines)),
                        }
                    ],
                }
            )
        except requests.RequestException as exc:
            print(f"[Gateway Totem] send_console error: {exc}", flush=True)
        finally:
            self._apply_pending_reconnect()
            self._apply_pending_service_restart()

    def _run_connection(self) -> None:
        while not self._stop.is_set():
            self._disconnect_all_clients()
            self._apply_link_state(False)
            time.sleep(_RECONNECT_PAUSE_S)

            namespace = self._namespace()
            url = self._connection_url()
            session_id = self._active_session_id + 1
            self._active_session_id = session_id
            totem_id = str(self._config.get("totem") or "").strip()
            enterprise = str(self._config.get("enterprise") or "").strip()
            print(
                "[Gateway Totem] Conectando "
                f"totem={totem_id} enterprise={enterprise} url={url}",
                flush=True,
            )

            client = socketio.Client(
                logger=False,
                engineio_logger=False,
                reconnection=False,
            )
            client.on("COMMAND", self._make_command_handler(client, session_id), namespace=namespace)
            self._register_client(client)
            self._client = client

            try:
                client.connect(url, namespaces=[namespace])
                self._enforce_single_session(reason="post-conexion")
                print(
                    f"[Gateway Totem] Conexion establecida (sesion id={session_id}).",
                    flush=True,
                )
                self._apply_link_state(True)
                self.update_status_cache()
                while not self._stop.is_set() and getattr(client, "connected", False):
                    if session_id != self._active_session_id:
                        break
                    try:
                        client.sleep(0.5)
                    except Exception:
                        break
            except Exception as exc:
                print(f"[Gateway Totem] Error de conexion: {exc}", flush=True)
            finally:
                if self._client is client:
                    self._client = None
                self._disconnect_client(client)
                self._apply_link_state(False)

            if self._stop.is_set():
                break
            print(f"[Gateway Totem] Reintento en {_RECONNECT_PAUSE_S:.0f} s.", flush=True)
            time.sleep(_RECONNECT_PAUSE_S)


def schedule_totem_reconnect_for_runtime(rt: "GatewayRuntime") -> bool:
    """Programa desconexion/reconexion del socket Totem con la identidad activa en cfg."""
    from python_gateway.gateway_config import parse_bool

    client = getattr(rt, "totem_client", None)
    if client is None:
        return False
    if not parse_bool(rt.cfg.get("totem_enabled"), True):
        return False
    totem_cfg = totem_config_from_gateway_cfg(rt.cfg)
    if not totem_cfg:
        return False
    client.schedule_reconnect(totem_cfg)
    rt.totem_socket_totem_id = str(totem_cfg.get("totem") or "").strip()
    rt.totem_socket_enterprise = str(totem_cfg.get("enterprise") or "").strip()
    return True


def schedule_gateway_service_restart_for_runtime(rt: "GatewayRuntime") -> bool:
    """Reinicia el servicio tras responder el comando (identidad Totem en cfg)."""
    from python_gateway.gateway_pi_host import is_linux_gateway_host

    if not is_linux_gateway_host():
        return False
    client = getattr(rt, "totem_client", None)
    if client is None:
        return False
    client.schedule_service_restart()
    return True


def totem_config_from_gateway_cfg(cfg: Dict[str, str]) -> Optional[Dict[str, Any]]:
    totem_id = (cfg.get("totem_id") or "").strip()
    enterprise = (cfg.get("totem_enterprise") or "").strip()
    if not totem_id or not enterprise:
        return None
    return {
        "host": (cfg.get("totem_host") or "caster.toteminsight.com").strip(),
        "protocol": (cfg.get("totem_protocol") or "https").strip() or "https",
        "namespace": (cfg.get("totem_namespace") or "caster").strip() or "caster",
        "totem": totem_id,
        "enterprise": enterprise,
    }
