#!/usr/bin/env python3
"""
FR3D Python Gateway — agente headless MK3 USB <-> cloud (Firebase; Totem solo no-Windows).

Uso (desde control_python/):
  python -m python_gateway

No modifica fr3d_control_ui.py ni el control NiceGUI existente.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Asegurar imports desde control_python/ (dev) o _MEIPASS (exe)
_ROOT = Path(__file__).resolve().parents[1]
if getattr(sys, "frozen", False):
    _meipass = getattr(sys, "_MEIPASS", None)
    if _meipass and str(_meipass) not in sys.path:
        sys.path.insert(0, str(_meipass))
elif str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from python_gateway.gateway_config import default_config_path, parse_bool
from python_gateway.gateway_identity import (
    identity_store_path,
    load_persisted_token,
    read_gateway_identity,
)
from python_gateway.gateway_executor import execute_totem_command
from python_gateway.gateway_firebase import (
    GatewayFirebaseClient,
    firebase_config_from_gateway_cfg,
)
from python_gateway.gateway_pi_led import PiStatusLed
from python_gateway.gateway_runtime import GatewayRuntime
from python_gateway.gateway_single_instance import acquire_single_instance
from python_gateway.gateway_status import build_status_lines, refresh_runtime

from i18n import set_language

_WINDOWS_HOST = sys.platform == "win32"


def _check_totem_socketio_stack() -> None:
    """Totem requiere Engine.IO 3 (python-socketio 4.x), no Socket.IO 5 del UI."""
    try:
        import engineio

        major = int(str(getattr(engineio, "__version__", "0")).split(".")[0])
    except Exception:
        major = 0
    if major >= 4:
        print(
            "[Gateway] ERROR: python-engineio 4+ detectado (Socket.IO 5). "
            "Totem necesita engineio 3.x.\n"
            "  Ejecute: setup_gateway_venv.bat\n"
            "  Luego: run_gateway.bat",
            flush=True,
        )
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="FR3D Python Gateway (MK3 + cloud)")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Ruta a config_gateway.csv (default: python_gateway/config_gateway.csv)",
    )
    args = parser.parse_args(argv)

    acquire_single_instance()

    cfg_path = args.config or default_config_path()
    rt = GatewayRuntime.create(cfg_path)
    _ui_lang = (rt.cfg.get("ui_lang") or "en").strip().lower()
    if _ui_lang not in ("es", "en"):
        _ui_lang = "en"
    set_language(_ui_lang)
    _identity = read_gateway_identity()
    _boot_token = load_persisted_token(identity_store_path(), _identity)
    if _boot_token:
        rt.gateway_token = _boot_token
    totem = None
    firebase: GatewayFirebaseClient | None = None
    pi_led = PiStatusLed(lambda: rt)
    pi_led.start()

    def _on_cloud_connected(ok: bool) -> None:
        if firebase is not None:
            rt.firebase_connected = bool(ok)
            rt.gateway_token = firebase.token if ok else ""
        elif totem is not None:
            rt.totem_connected = bool(ok)

    def _status() -> list[str]:
        return build_status_lines(rt)

    def _status_cache() -> list[str]:
        return build_status_lines(rt, include_wifi=False)

    def _exec_cmd(msg: str) -> tuple[list[str], str]:
        with rt.cmd_lock:
            return execute_totem_command(rt, msg)

    # Windows release path: Firebase only (no Totem Insight).
    if _WINDOWS_HOST:
        firebase_cfg = firebase_config_from_gateway_cfg(rt.cfg)
        if not parse_bool(rt.cfg.get("firebase_enabled"), True):
            print(
                "[Gateway] Windows requiere firebase_enabled=true. "
                "Totem Insight no se usa en este host.",
                flush=True,
            )
        elif firebase_cfg:
            firebase = GatewayFirebaseClient(
                rt.cfg,
                _status,
                _exec_cmd,
                line_label=rt.line_label(),
                on_connected=_on_cloud_connected,
                status_cache_provider=_status_cache,
            )
            firebase.start()
            rt.firebase_client = firebase
            print(
                f"[Gateway] Firebase iniciado url={firebase_cfg.get('firebase_database_url') or '(default)'}",
                flush=True,
            )
        else:
            print(
                "[Gateway] Windows/Firebase: revise firebase_auth_email/password "
                "en config_gateway.csv (usuario gateway, sin service account). "
                "Totem NO se inicia en Windows.",
                flush=True,
            )
    else:
        firebase_cfg = firebase_config_from_gateway_cfg(rt.cfg)
        if parse_bool(rt.cfg.get("firebase_enabled"), False):
            if firebase_cfg:
                firebase = GatewayFirebaseClient(
                    rt.cfg,
                    _status,
                    _exec_cmd,
                    line_label=rt.line_label(),
                    on_connected=_on_cloud_connected,
                    status_cache_provider=_status_cache,
                )
                firebase.start()
                rt.firebase_client = firebase
                print(
                    f"[Gateway] Firebase iniciado url={firebase_cfg.get('firebase_database_url') or '(default)'}",
                    flush=True,
                )
            else:
                print(
                    "[Gateway] firebase_enabled=true pero faltan credenciales Auth "
                    "(firebase_auth_email/password). Totem NO se inicia. "
                    "Edite config_gateway.csv y reinicie.",
                    flush=True,
                )
        else:
            from python_gateway.gateway_totem import (
                GatewayTotemClient,
                totem_config_from_gateway_cfg,
            )

            totem_cfg = totem_config_from_gateway_cfg(rt.cfg)
            if totem_cfg and parse_bool(rt.cfg.get("totem_enabled"), True):
                _check_totem_socketio_stack()
                totem = GatewayTotemClient(
                    totem_cfg,
                    _status,
                    _exec_cmd,
                    line_label=rt.line_label(),
                    on_connected=_on_cloud_connected,
                    status_cache_provider=_status_cache,
                    gateway_cfg_provider=lambda: rt.cfg,
                )
                totem.start()
                rt.totem_client = totem
                rt.totem_socket_totem_id = str(totem_cfg.get("totem") or "").strip()
                rt.totem_socket_enterprise = str(totem_cfg.get("enterprise") or "").strip()
                from python_gateway.gateway_totem_identity import (
                    active_totem_identity,
                    totem_identity_mode_label,
                )

                tid, ent = active_totem_identity(rt.cfg)
                print(
                    "[Gateway] Totem iniciado "
                    f"modo={totem_identity_mode_label(rt.cfg)} "
                    f"totem={tid} enterprise={ent}",
                    flush=True,
                )
            elif totem_cfg:
                print("[Gateway] Totem deshabilitado en config.", flush=True)
            else:
                print(
                    "[Gateway] Sin cloud: habilite firebase_enabled (+ firebase_auth_email/password) "
                    "o totem_id/enterprise.",
                    flush=True,
                )

    # En Pi / UNO Q el gateway EXISTE para hablar con el MK3: auto_connect se fuerza a
    # true (como DH=1). El flag del CSV solo se respeta en Windows/dev, donde a
    # veces se levanta el agente sin abrir el COM. Un false olvidado dejaba el
    # host "vivo en Firebase, muerto en USB" hasta que alguien abria la app.
    from python_gateway.gateway_pi_host import is_linux_gateway_host
    from python_gateway.gateway_serial import resolve_mk3_port

    if is_linux_gateway_host():
        auto_connect = True
        if not parse_bool(rt.cfg.get("auto_connect"), True):
            print(
                "[Gateway] Auto-conexion: forzada a true en gateway Linux "
                "(auto_connect=false ignorado; el gateway siempre abre el MK3).",
                flush=True,
            )
    else:
        auto_connect = parse_bool(rt.cfg.get("auto_connect"), True)

    if not auto_connect:
        print(
            "[Gateway] Auto-conexion: DESHABILITADA (auto_connect=false en "
            f"{rt.config_path}). El MK3 no se conecta solo.",
            flush=True,
        )
    elif not resolve_mk3_port(rt.cfg):
        print(
            "[Gateway] Auto-conexion: omitida (puerto MK3 vacio; use SERIAL SET PORT).",
            flush=True,
        )
    elif rt.session is None:
        print("[Gateway] Auto-conexion: omitida (sin sesion inicializada).", flush=True)
    else:
        ok, msg = rt.session.connect()
        print(f"[Gateway] Auto-conexion: {msg}", flush=True)
        # Con MK3+BDWidth (ambos CH340) el by-id suele ser ambiguo. Si el monitor
        # BDWidth sondea durante el boot del Mega, puede abrir el puerto del MK3 y
        # el LCD queda en blanco. Esperar bootstrap (o timeout) antes de sondear.
        if ok:
            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                if rt.session.mk3_ready():
                    print("[Gateway] MK3 bootstrap listo; iniciando BDWidth.", flush=True)
                    break
                dead = rt.session.finalize_if_dead()
                if dead:
                    print(f"[Gateway] MK3 no arranco: {dead}", flush=True)
                    break
                time.sleep(0.2)
            else:
                print(
                    "[Gateway] MK3 aun sin bootstrap tras 15 s; inicio BDWidth igual "
                    "(probe sin DTR).",
                    flush=True,
                )

    from python_gateway.gateway_artme import is_artme_backend, start_artme_monitor
    from python_gateway.gateway_bdwidth import start_bdwidth_monitor

    if is_artme_backend(rt.cfg) and parse_bool(rt.cfg.get("artme_enabled"), False):
        start_artme_monitor(rt)
        print(
            "[Gateway] ARTME ADS1115: hilo iniciado "
            f"port={rt.cfg.get('artme_port') or 'auto'} "
            f"bus={rt.cfg.get('artme_i2c_bus') or '1'}.",
            flush=True,
        )
    else:
        start_bdwidth_monitor(rt)
        if parse_bool(rt.cfg.get("bdwidth_enabled"), False):
            print(
                "[Gateway] BDWidth: hilo iniciado "
                f"port={rt.cfg.get('bdwidth_port') or 'auto'} "
                "(sin inyeccion MK3).",
                flush=True,
            )
        else:
            print("[Gateway] BDWidth: deshabilitado (bdwidth_enabled=false).", flush=True)

    try:
        from python_gateway.gateway_lan_http import start_lan_http

        rt.lan_http = start_lan_http(rt, _exec_cmd)
    except OSError as exc:
        print(f"[Gateway] LAN API no inicio (puerto 8765): {exc}", flush=True)

    print("[Gateway] En ejecucion (Ctrl+C para salir).", flush=True)
    try:
        while True:
            refresh_runtime(rt)
            rt.tick_mk3_eeprom_store()
            if totem is not None:
                totem.update_status_cache()
            if firebase is not None:
                firebase.update_status_cache()
                if firebase.token and firebase.token != rt.gateway_token:
                    rt.gateway_token = firebase.token
                    rt.gw_mac_last_push_mono = 0.0
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\n[Gateway] Deteniendo...", flush=True)
    finally:
        pi_led.stop()
        lan = getattr(rt, "lan_http", None)
        if lan is not None:
            try:
                lan.stop()
            except Exception:
                pass
        if firebase is not None:
            firebase.stop()
        if totem is not None:
            totem.stop()
        mon = getattr(rt, "bdwidth", None)
        if mon is not None:
            try:
                mon.stop()
            except Exception:
                pass
        if rt.session:
            rt.session.disconnect()


if __name__ == "__main__":
    main()
