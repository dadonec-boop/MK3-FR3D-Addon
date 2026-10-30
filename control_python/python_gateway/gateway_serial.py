"""Resolucion de enlace MK3 USB vs UART GPIO (config_gateway.csv)."""
from __future__ import annotations

from typing import Dict, List, Tuple

from python_gateway.gateway_config import parse_bool

MK3_LINK_USB = "usb"
MK3_LINK_UART = "uart"
DEFAULT_PORT_UART = "/dev/serial0"


def normalize_mk3_link_mode(raw: str) -> str:
    t = str(raw or "").strip().lower()
    if t in (MK3_LINK_UART, "serial", "gpio", "uart0"):
        return MK3_LINK_UART
    return MK3_LINK_USB


def mk3_link_mode_label(cfg: Dict[str, str]) -> str:
    return "UART" if normalize_mk3_link_mode(cfg.get("mk3_link_mode", MK3_LINK_USB)) == MK3_LINK_UART else "USB"


def migrate_mk3_serial_config(cfg: Dict[str, str]) -> None:
    """In-place: port_fr3d legacy -> port_fr3d_usb; defaults para modo UART."""
    if not (cfg.get("mk3_link_mode") or "").strip():
        cfg["mk3_link_mode"] = MK3_LINK_USB
    if not (cfg.get("port_fr3d_uart") or "").strip():
        cfg["port_fr3d_uart"] = DEFAULT_PORT_UART
    usb = (cfg.get("port_fr3d_usb") or "").strip()
    legacy = (cfg.get("port_fr3d") or "").strip()
    if not usb and legacy and not legacy.startswith("/dev/serial0"):
        # Legacy port_fr3d suele ser USB by-id o COMx; no copiar /dev/serial0 ambiguo.
        cfg["port_fr3d_usb"] = legacy
    cfg["port_fr3d"] = resolve_mk3_port(cfg)


def resolve_mk3_port(cfg: Dict[str, str]) -> str:
    mode = normalize_mk3_link_mode(cfg.get("mk3_link_mode", MK3_LINK_USB))
    if mode == MK3_LINK_UART:
        return (cfg.get("port_fr3d_uart") or DEFAULT_PORT_UART).strip()
    usb = (cfg.get("port_fr3d_usb") or "").strip()
    if usb:
        return usb
    return (cfg.get("port_fr3d") or "").strip()


def resolve_mk3_serial_open_flags(cfg: Dict[str, str]) -> Tuple[bool, bool]:
    """
    Devuelve (serial_pulse_reset, serial_open_passive) para run_merge.
    UART GPIO: sin DTR (siempre pasivo). USB: respeta chk_passive.
    """
    if normalize_mk3_link_mode(cfg.get("mk3_link_mode", MK3_LINK_USB)) == MK3_LINK_UART:
        return False, True
    passive = parse_bool(cfg.get("chk_passive"), False)
    return (not passive), passive


def port_config_key_for_mode(mode: str) -> str:
    return "port_fr3d_uart" if normalize_mk3_link_mode(mode) == MK3_LINK_UART else "port_fr3d_usb"


def set_mk3_port_for_active_mode(cfg: Dict[str, str], port: str) -> None:
    key = port_config_key_for_mode(cfg.get("mk3_link_mode", MK3_LINK_USB))
    cfg[key] = port.strip()
    cfg["port_fr3d"] = resolve_mk3_port(cfg)


def set_mk3_link_mode(cfg: Dict[str, str], mode: str) -> str:
    normalized = normalize_mk3_link_mode(mode)
    cfg["mk3_link_mode"] = normalized
    cfg["port_fr3d"] = resolve_mk3_port(cfg)
    return normalized


def build_serial_status_lines(cfg: Dict[str, str], config_path: str) -> List[str]:
    mode = mk3_link_mode_label(cfg)
    port = resolve_mk3_port(cfg) or "(vacio)"
    baud = (cfg.get("baud_fr3d") or "250000").strip()
    usb_port = (cfg.get("port_fr3d_usb") or "").strip() or "(vacio)"
    uart_port = (cfg.get("port_fr3d_uart") or DEFAULT_PORT_UART).strip()
    passive = parse_bool(cfg.get("chk_passive"), False)
    return [
        "[FR3D] SERIAL",
        f"mk3_link_mode: {mode.lower()} (usb | uart)",
        f"port efectivo: {port}",
        f"port_fr3d_usb: {usb_port}",
        f"port_fr3d_uart: {uart_port}",
        f"baud_fr3d: {baud}",
        f"chk_passive (solo USB): {str(passive).lower()}",
        f"Archivo: {config_path}",
    ]


def list_serial_ports() -> List[str]:
    """Puertos serie detectados (COMx / ttyUSB* / ttyCH341USB* / by-id)."""
    found: set[str] = set()
    try:
        from serial.tools import list_ports
    except ImportError:
        list_ports = None
    if list_ports is not None:
        for item in list_ports.comports():
            device = (getattr(item, "device", None) or "").strip()
            if device:
                found.add(device)
    # UNO Q: modulo ch341 out-of-tree puede no aparecer en comports()
    try:
        import glob as _glob
        import os

        for pattern in ("/dev/ttyCH341USB*", "/dev/ttyUSB*", "/dev/ttyACM*"):
            for path in _glob.glob(pattern):
                if os.path.exists(path):
                    found.add(path)
    except OSError:
        pass
    uniq = sorted(
        found,
        key=lambda p: (0 if p.upper().startswith("COM") else 1, p.upper()),
    )
    return uniq


def build_serial_list_lines(cfg: Dict[str, str]) -> List[str]:
    from python_gateway.gateway_pi_host import gateway_host_type

    active = resolve_mk3_port(cfg).strip()
    lines = [
        "[FR3D] SERIAL LIST",
        f"Host: {gateway_host_type()}",
        f"Activo: {active or '(vacio)'}",
    ]
    ports = list_serial_ports()
    if not ports:
        lines.append("(sin puertos detectados)")
        return lines
    active_u = active.upper()
    for port in ports:
        mark = " *" if port.upper() == active_u else ""
        lines.append(f"{port}{mark}")
    return lines
