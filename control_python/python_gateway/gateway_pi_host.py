"""Comandos de host Linux del gateway (Raspberry Pi y Arduino UNO Q)."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_SO_TIMEOUT_S = 60.0
_SO_MAX_CHARS = 12000
_NMCLI = "/usr/bin/nmcli"
_WIFI_RESCAN_WAIT_S = 3.0


def _device_tree_model() -> str:
    try:
        with open("/proc/device-tree/model", encoding="utf-8") as f:
            return f.read().split("\x00", 1)[0].strip().lower()
    except OSError:
        return ""


def is_pi_gateway_host() -> bool:
    return "raspberry pi" in _device_tree_model()


def is_uno_q_gateway_host() -> bool:
    """Arduino UNO Q (device-tree: 'Arduino SA,Imola')."""
    model = _device_tree_model()
    return "imola" in model or "arduino sa" in model


def is_linux_gateway_host() -> bool:
    """Pi o UNO Q: OTA programa/UI, reboot, WiFi Totem, identidad /var/lib/fr3d."""
    return is_pi_gateway_host() or is_uno_q_gateway_host()


def supports_mk3_gwid() -> bool:
    """Pi, UNO Q o Windows: pueden empujar token GWID al LCD del MK3."""
    return is_linux_gateway_host() or sys.platform == "win32"


def gateway_host_type() -> str:
    """Identificador estable para Flutter CONFIG (presence.hostType)."""
    if is_pi_gateway_host():
        return "raspberry_pi"
    if is_uno_q_gateway_host():
        return "uno_q"
    if sys.platform == "win32":
        return "windows"
    return "other"


def pi_host_unavailable_lines() -> List[str]:
    return [
        "[FR3D] Comando solo disponible en gateway Linux (Raspberry Pi o Arduino UNO Q).",
        "Use el agente python_gateway en la Pi / UNO Q.",
    ]


def _run(
    args: List[str],
    *,
    timeout: float = 30.0,
    check: bool = False,
) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", f"No se encuentra: {args[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"Timeout ({timeout:.0f} s)"
    except subprocess.CalledProcessError as exc:
        return (
            int(exc.returncode or 1),
            (exc.stdout or "").strip(),
            (exc.stderr or "").strip(),
        )


def _needs_privilege_retry(code: int, err: str, out: str) -> bool:
    if code == 0:
        return False
    msg = f"{err} {out}".lower()
    return any(
        token in msg
        for token in (
            "privilege",
            "permission",
            "authorized",
            "not permitted",
            "insufficient",
        )
    )


def _run_nmcli(args: List[str], *, timeout: float = 30.0) -> Tuple[int, str, str]:
    """nmcli como usuario del gateway; reintenta con sudo -n si faltan permisos."""
    code, out, err = _run(args, timeout=timeout)
    if not _needs_privilege_retry(code, err, out):
        return code, out, err
    code2, out2, err2 = _run(["sudo", "-n", *args], timeout=timeout)
    return code2, out2, err2


def _nmcli_ok() -> bool:
    code, _, _ = _run([_NMCLI, "--version"], timeout=5.0)
    return code == 0


def _wifi_iface() -> str:
    code, out, _ = _run(
        [_NMCLI, "-t", "-f", "DEVICE,TYPE,STATE", "dev", "status"],
        timeout=10.0,
    )
    if code != 0:
        return "wlan0"
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[1] == "wifi":
            return parts[0] or "wlan0"
    return "wlan0"


def _wifi_rescan(iface: str) -> tuple[bool, str]:
    """Escaneo WiFi (async en NM). Espera unos segundos antes de listar."""
    code, _, err = _run_nmcli(
        [_NMCLI, "dev", "wifi", "rescan", "ifname", iface],
        timeout=25.0,
    )
    time.sleep(_WIFI_RESCAN_WAIT_S)
    return code == 0, err


def _parse_wifi_scan(out: str) -> List[tuple[str, int, str, bool]]:
    """SSID, señal, seguridad, conectada ahora. Una fila por SSID (mejor señal)."""
    best: Dict[str, Dict[str, object]] = {}
    for row in out.splitlines():
        if not row.strip():
            continue
        parts = row.split(":", 3)
        if len(parts) < 3:
            continue
        in_use = parts[0].strip() == "*"
        ssid = parts[1].strip()
        if not ssid:
            continue
        try:
            signal = int(str(parts[2]).strip())
        except ValueError:
            signal = 0
        sec = str(parts[3]).strip() if len(parts) > 3 else ""
        cur = best.get(ssid)
        if cur is None or signal > int(cur["signal"]):
            best[ssid] = {"signal": signal, "sec": sec, "in_use": in_use}
        elif in_use:
            cur["in_use"] = True

    rows: List[tuple[str, int, str, bool]] = []
    for ssid, info in best.items():
        rows.append(
            (
                ssid,
                int(info["signal"]),
                str(info["sec"]),
                bool(info["in_use"]),
            )
        )
    rows.sort(key=lambda r: (-r[1], r[0].lower()))
    return rows


GWID_WIFI_OFFLINE_TEXT = "Not addonfr3d WIFI"
GWID_WIFI_CONNECTING_TEXT = "WiFi connecting"


def build_gwid_wifi_status() -> str:
    """Texto GWID para MK3: SSID conectada o mensaje offline (sin ':' — el serial corta en ':')."""
    if sys.platform == "win32":
        # Etiqueta corta y estable en LCD (no usa ':').
        return "Windows"
    ssid = get_connected_wifi_ssid()
    if ssid:
        return f"WIFI {ssid}"
    return GWID_WIFI_OFFLINE_TEXT


def get_connected_wifi_ssid() -> str:
    if not _nmcli_ok():
        return ""
    code, out, _ = _run_nmcli(
        [_NMCLI, "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
        timeout=3.0,
    )
    if code != 0:
        return ""
    for line in out.splitlines():
        parts = line.split(":", 1)
        if len(parts) == 2 and parts[0] == "yes" and parts[1].strip():
            return parts[1].strip()
    code, out, _ = _run_nmcli(
        [_NMCLI, "-t", "-f", "NAME,TYPE", "connection", "show", "--active"],
        timeout=3.0,
    )
    if code == 0 and out:
        name, _, typ = (out.split(":") + ["", ""])[:3]
        if typ == "802-11-wireless" and name:
            return name.strip()
    return ""


def run_so_command(shell_line: str) -> Tuple[List[str], str]:
    cmd = str(shell_line or "").strip()
    if not cmd:
        return ["[FR3D] SO: comando vacio."], "WARNING"

    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_SO_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return [f"[FR3D] SO: timeout ({_SO_TIMEOUT_S:.0f} s)."], "ERROR"

    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    out = out.strip("\n")
    if len(out) > _SO_MAX_CHARS:
        out = out[:_SO_MAX_CHARS] + "\n... (salida truncada)"

    lines = ["[FR3D] SO", f"Comando: {cmd}", f"Exit: {proc.returncode}"]
    if out:
        lines.extend(out.splitlines())
    else:
        lines.append("(sin salida)")
    entry = "INFO" if proc.returncode == 0 else "WARNING"
    return lines, entry


def wifi_show() -> Tuple[List[str], str]:
    ssid = get_connected_wifi_ssid()
    lines = ["[FR3D] WIFI"]
    if ssid:
        lines.append(f"Conectado: {ssid}")
    else:
        lines.append("Conectado: (ninguna)")
    return lines, "INFO"


def wifi_saved_networks() -> List[str]:
    return _wifi_saved_names()


def _wifi_list_cmd(*, iface: str = "", rescan: str = "") -> List[str]:
    args = [
        _NMCLI,
        "-t",
        "-f",
        "IN-USE,SSID,SIGNAL,SECURITY",
        "dev",
        "wifi",
        "list",
    ]
    if rescan:
        args.extend(["--rescan", rescan])
    if iface:
        args.extend(["ifname", iface])
    return args


def wifi_scan_networks() -> List[tuple[str, int, str, bool]]:
    """Redes visibles: (ssid, señal %, seguridad, conectada ahora)."""
    if not _nmcli_ok():
        return []
    iface = _wifi_iface()
    # --rescan yes espera el barrido (mismo resultado que el panel web).
    code, out, _ = _run_nmcli(_wifi_list_cmd(iface=iface, rescan="yes"), timeout=30.0)
    if code != 0 or not out.strip():
        code, out, _ = _run_nmcli(_wifi_list_cmd(rescan="yes"), timeout=30.0)
    if code != 0 or not out.strip():
        _wifi_rescan(iface)
        code, out, _ = _run_nmcli(_wifi_list_cmd(iface=iface), timeout=25.0)
    if code != 0:
        return []
    return _parse_wifi_scan(out)


def wifi_list_saved() -> Tuple[List[str], str]:
    if not _nmcli_ok():
        return ["[FR3D] WIFI LIST", "nmcli no disponible (NetworkManager)."], "ERROR"

    names = wifi_saved_networks()
    lines = ["[FR3D] WIFI LIST"]
    if not names:
        lines.append("(ninguna red WiFi guardada)")
    else:
        for name in names:
            lines.append(name)
    return lines, "INFO"


def wifi_available() -> Tuple[List[str], str]:
    if not _nmcli_ok():
        return ["[FR3D] WIFI AVAILABLE", "nmcli no disponible (NetworkManager)."], "ERROR"

    networks = wifi_scan_networks()
    lines = ["[FR3D] WIFI AVAILABLE"]
    if not networks:
        lines.append("(ninguna red visible)")
    else:
        for ssid, signal, sec, in_use in networks:
            mark = "*" if in_use else " "
            lines.append(f"{mark} {ssid}  ({signal}%  {sec or '--'})")

    return lines, "INFO"


def _wifi_saved_names() -> List[str]:
    if not _nmcli_ok():
        return []
    code, out, _ = _run(
        [_NMCLI, "-t", "-f", "NAME,TYPE", "connection", "show"],
        timeout=15.0,
    )
    if code != 0:
        return []
    names: List[str] = []
    for row in out.splitlines():
        parts = row.split(":")
        if len(parts) >= 2 and parts[1] == "802-11-wireless" and parts[0].strip():
            names.append(parts[0].strip())
    return names


def _wifi_apply_profile_security(args: List[str], psk: str) -> None:
    if psk:
        args.extend(["802-11-wireless-security.key-mgmt", "wpa-psk", "wifi-sec.psk", psk])
    else:
        args.extend(["802-11-wireless-security.key-mgmt", "none"])


def wifi_add(name: str, password: str) -> Tuple[List[str], str]:
    ssid = str(name or "").strip()
    psk = str(password or "").strip()
    if psk == "-":
        psk = ""
    if not ssid:
        return ["[FR3D] WIFI ADD: SSID vacio."], "ERROR"
    if not _nmcli_ok():
        return ["[FR3D] WIFI ADD", "nmcli no disponible (NetworkManager)."], "ERROR"

    iface = _wifi_iface()
    lines = ["[FR3D] WIFI ADD", f"SSID: {ssid}"]
    existing = ssid in _wifi_saved_names()

    if existing:
        args: List[str] = [
            _NMCLI,
            "connection",
            "modify",
            ssid,
            "802-11-wireless.ssid",
            ssid,
        ]
        _wifi_apply_profile_security(args, psk)
        if ssid.lower() != "addonfr3d":
            args.extend(["connection.autoconnect", "yes", "connection.autoconnect-priority", "20"])
        code, out, err = _run_nmcli(args, timeout=20.0)
        if code != 0:
            msg = err or out or "Error actualizando red."
            lines.append(msg)
            if _needs_privilege_retry(code, err, out):
                lines.append("Falta permiso NM: ejecute install_pi.sh en la Pi.")
            return lines, "ERROR"
        if out:
            lines.append(out)
        lines.append("Perfil actualizado.")
        return lines, "INFO"

    args = [
        _NMCLI,
        "connection",
        "add",
        "type",
        "wifi",
        "ifname",
        iface,
        "con-name",
        ssid,
        "ssid",
        ssid,
    ]
    _wifi_apply_profile_security(args, psk)
    if ssid.lower() != "addonfr3d":
        args.extend(["connection.autoconnect", "yes", "connection.autoconnect-priority", "20"])
    code, out, err = _run_nmcli(args, timeout=20.0)
    if code != 0:
        msg = err or out or "Error guardando red."
        if "already exists" in msg.lower() or "ya existe" in msg.lower():
            lines.append("El perfil ya existe; use WIFI CONNECT o WIFI REMOVE.")
        elif _needs_privilege_retry(code, err, out):
            lines.append(msg)
            lines.append("Falta permiso NM: ejecute install_pi.sh en la Pi.")
        else:
            lines.append(msg)
        return lines, "ERROR"
    if out:
        lines.append(out)
    lines.append("Red guardada.")
    return lines, "INFO"


def wifi_remove(name: str) -> Tuple[List[str], str]:
    ssid = str(name or "").strip()
    if not ssid:
        return ["[FR3D] WIFI REMOVE: nombre vacio."], "ERROR"
    if not _nmcli_ok():
        return ["[FR3D] WIFI REMOVE", "nmcli no disponible (NetworkManager)."], "ERROR"

    code, out, err = _run_nmcli([_NMCLI, "connection", "delete", ssid], timeout=20.0)
    lines = ["[FR3D] WIFI REMOVE", f"Nombre: {ssid}"]
    if code != 0:
        lines.append(err or out or "No se pudo eliminar (perfil inexistente?).")
        return lines, "ERROR"
    lines.append("Perfil eliminado.")
    return lines, "INFO"


def wifi_connect(name: str) -> Tuple[List[str], str]:
    ssid = str(name or "").strip()
    if not ssid:
        return ["[FR3D] WIFI CONNECT: nombre vacio."], "ERROR"
    if not _nmcli_ok():
        return ["[FR3D] WIFI CONNECT", "nmcli no disponible (NetworkManager)."], "ERROR"

    iface = _wifi_iface()
    code, out, err = _run_nmcli(
        [_NMCLI, "connection", "up", ssid],
        timeout=45.0,
    )
    if code != 0:
        code2, out2, err2 = _run_nmcli(
            [_NMCLI, "dev", "wifi", "connect", ssid, "ifname", iface],
            timeout=45.0,
        )
        if code2 != 0:
            lines = [
                "[FR3D] WIFI CONNECT",
                f"SSID: {ssid}",
                err or out or err2 or out2 or "Error de conexion.",
            ]
            return lines, "ERROR"
        out = out2

    lines = ["[FR3D] WIFI CONNECT", f"SSID: {ssid}", "Conectado."]
    if out:
        lines.append(out)
    return lines, "INFO"


def is_gateway_network_up() -> bool:
    """True si el gateway Linux tiene WiFi/conectividad util hacia Internet."""
    if not is_linux_gateway_host():
        return True
    if not _nmcli_ok():
        return bool(get_connected_wifi_ssid())
    code, out, _ = _run_nmcli(
        [_NMCLI, "-g", "CONNECTIVITY", "g"],
        timeout=4.0,
    )
    if code == 0:
        state = (out.splitlines()[0] if out else "").strip().lower()
        if state in ("full", "limited"):
            return True
        if state == "none":
            return False
    iface = _wifi_iface()
    code, out, _ = _run_nmcli(
        [_NMCLI, "-t", "-f", "DEVICE,STATE", "dev", "status"],
        timeout=4.0,
    )
    if code != 0:
        return bool(get_connected_wifi_ssid())
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[0] == iface:
            return parts[1] == "connected"
    return bool(get_connected_wifi_ssid())


def _windows_primary_ipv4() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addr = sock.getsockname()[0]
        if addr.count(".") == 3 and not addr.startswith("127."):
            return addr
    except OSError:
        pass
    return ""


def get_wlan_ipv4() -> str:
    """IPv4 de wlan0 (Pi/UNO Q) o IP primaria (Windows), sin mascara."""
    if sys.platform == "win32":
        return _windows_primary_ipv4()
    if not is_linux_gateway_host():
        return ""
    iface = _wifi_iface()
    code, out, _ = _run_nmcli(
        [_NMCLI, "-g", "IP4.ADDRESS", "device", "show", iface],
        timeout=4.0,
    )
    if code == 0 and out:
        addr = out.splitlines()[0].strip().split("/", 1)[0].strip()
        if addr.count(".") == 3:
            return addr
    for candidate in (iface, "wlan0", "eth0"):
        code, out, _ = _run(
            ["ip", "-4", "-o", "addr", "show", candidate],
            timeout=4.0,
        )
        if code != 0 or not out:
            continue
        parts = out.split()
        for i, part in enumerate(parts):
            if part == "inet" and i + 1 < len(parts):
                addr = parts[i + 1].split("/", 1)[0].strip()
                if addr.count(".") == 3 and not addr.startswith("127."):
                    return addr
    # Fallback: IP de la ruta default
    code, out, _ = _run(["ip", "-4", "route", "get", "1.1.1.1"], timeout=4.0)
    if code == 0 and out:
        parts = out.split()
        if "src" in parts:
            try:
                addr = parts[parts.index("src") + 1].strip()
                if addr.count(".") == 3:
                    return addr
            except (ValueError, IndexError):
                pass
    return ""


def build_wifi_status_line() -> str:
    ssid = get_connected_wifi_ssid()
    return f"WIFI {ssid}" if ssid else "WIFI (desconectada)"


_wlan_mac_cache: Optional[str] = None


def _read_iface_mac(iface: str) -> str:
    try:
        mac = Path(f"/sys/class/net/{iface}/address").read_text(encoding="utf-8").strip().lower()
    except OSError:
        return ""
    if not mac or mac == "00:00:00:00:00:00":
        return ""
    return mac


def get_wlan_mac_address() -> str:
    """MAC de wlan0/eth0 (Pi / UNO Q). Cache en memoria."""
    global _wlan_mac_cache
    if _wlan_mac_cache is not None:
        return _wlan_mac_cache
    if not is_linux_gateway_host():
        return ""

    for iface in ("wlan0", _wifi_iface(), "eth0"):
        mac = _read_iface_mac(iface)
        if mac:
            _wlan_mac_cache = mac
            return mac
    return ""


def build_mac_status_line() -> str:
    mac = get_wlan_mac_address()
    return f"MAC: {mac}" if mac else "MAC: —"


def _append_command_output(
    lines: List[str],
    *,
    code: int,
    out: str,
    err: str,
    empty_msg: str = "(sin salida)",
) -> None:
    body = (out or "").strip()
    if not body and err:
        body = err.strip()
    if not body:
        lines.append(empty_msg if code == 0 else f"(error exit {code})")
        return
    lines.extend(body.splitlines())


def pi_status() -> Tuple[List[str], str]:
    lines = ["[FR3D] PI STATUS"]

    lines.append("============ gateway status")
    code, out, err = _run(
        ["sudo", "-n", "systemctl", "--no-pager", "status", "fr3d-gateway"],
        timeout=20.0,
    )
    if code != 0:
        code, out, err = _run(
            ["systemctl", "--no-pager", "status", "fr3d-gateway"],
            timeout=20.0,
        )
    _append_command_output(lines, code=code, out=out, err=err)

    lines.append("============ Procesos que más consumen")
    code, out, err = _run(
        ["/bin/bash", "-lc", "top -bn1 | head -15"],
        timeout=20.0,
    )
    _append_command_output(lines, code=code, out=out, err=err)

    lines.append("============ Temperatura")
    code, out, err = _run(["/usr/bin/vcgencmd", "measure_temp"], timeout=10.0)
    if code != 0:
        code, out, err = _run(["/bin/bash", "-lc", "vcgencmd measure_temp"], timeout=10.0)
    _append_command_output(lines, code=code, out=out, err=err)

    return lines, "INFO"


def pi_restart_gateway() -> Tuple[List[str], str]:
    lines = ["[FR3D] PI REINICIAR GATEWAY"]
    code, out, err = _run(
        ["sudo", "-n", "systemctl", "restart", "fr3d-gateway"],
        timeout=30.0,
    )
    if code != 0:
        msg = (err or out or "Error reiniciando fr3d-gateway.").strip()
        lines.append(msg)
        lines.append("En la Pi: sudo ./python_gateway/deploy/install_pi.sh")
        return lines, "ERROR"

    code2, active, _ = _run(
        ["sudo", "-n", "systemctl", "is-active", "fr3d-gateway"],
        timeout=15.0,
    )
    state = (active or "desconocido").strip()
    lines.append(f"Servicio fr3d-gateway: {state}")
    if code2 == 0 and state == "active":
        lines.append("Gateway reiniciado.")
        return lines, "INFO"
    lines.append("Reinicio enviado; compruebe con PI STATUS si no queda active.")
    return lines, "WARNING"


def pi_reboot() -> Tuple[List[str], str]:
    lines = ["[FR3D] PI REINICIAR"]
    candidates = [
        ["sudo", "-n", "systemctl", "reboot"],
        ["sudo", "-n", "/usr/sbin/reboot"],
        ["sudo", "-n", "reboot"],
    ]
    last_err = ""
    for cmd in candidates:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            time.sleep(0.4)
            rc = proc.poll()
            if rc is None or rc == 0:
                lines.append("Reinicio solicitado. La Pi volvera en ~1 min.")
                lines.append("(Totem se desconectara durante el reinicio.)")
                return lines, "INFO"
            last_err = (proc.stderr.read() if proc.stderr else "").strip()
        except OSError as exc:
            last_err = str(exc)

    lines.append("No se pudo reiniciar (falta permiso sudo).")
    if last_err:
        lines.append(last_err)
    lines.append("En la Pi: sudo ./python_gateway/deploy/install_pi.sh")
    lines.append("O use: SO sudo reboot")
    return lines, "ERROR"


# --- OTA gateway (zip) -----------------------------------------------------

_UPDATE_STATUS = Path("/var/lib/fr3d/gateway_update_status.json")
_WEB_UPDATE_STATUS = Path("/var/lib/fr3d/web_update_status.json")
_DEFAULT_UPDATE_BASE = (
    os.environ.get("FR3D_UPDATE_BASE")
    or os.environ.get("FR3D_GATEWAY_UPDATE_BASE")
    or "https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/latest/download"
).rstrip("/")


def _gateway_update_script() -> Path:
    return Path(__file__).resolve().parent / "deploy" / "fr3d-gateway-update.sh"


def _web_update_script() -> Path:
    return Path(__file__).resolve().parent / "deploy" / "fr3d-web-update.sh"


def _control_python_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_gateway_version() -> str:
    from python_gateway.gateway_version import read_gateway_version

    return read_gateway_version()


def _read_update_status_file() -> Dict[str, str]:
    try:
        import json

        raw = _UPDATE_STATUS.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) if v is not None else "" for k, v in data.items()}
    except Exception:
        pass
    return {}


def pi_update_status() -> Tuple[List[str], str]:
    lines = ["[FR3D] PI UPDATE STATUS"]
    lines.append(f"version_local={_read_gateway_version()}")
    st = _read_update_status_file()
    if not st:
        lines.append("state=idle")
        lines.append("message=sin actualizaciones recientes")
        return lines, "INFO"
    for key in (
        "state",
        "message",
        "from_version",
        "to_version",
        "updated_at",
        "active_path",
    ):
        if key in st and st[key]:
            lines.append(f"{key}={st[key]}")
    return lines, "INFO"


def pi_update_check(manifest_url: str = "") -> Tuple[List[str], str]:
    lines = ["[FR3D] PI UPDATE CHECK"]
    script = _gateway_update_script()
    if not script.is_file():
        lines.append(f"ERROR: no existe {script}")
        return lines, "ERROR"
    url = (manifest_url or "").strip()
    if not url and _DEFAULT_UPDATE_BASE:
        url = f"{_DEFAULT_UPDATE_BASE}/MANIFEST.json"
    args = ["/bin/bash", str(script), "check"]
    if url:
        args.append(url)
    code, out, err = _run(args, timeout=60.0)
    body = (out or err or "").strip()
    if body:
        lines.extend(body.splitlines())
    else:
        lines.append(f"(sin salida; exit {code})")
    return lines, "INFO" if code == 0 else "ERROR"


def pi_update_gateway(
    target: str = "latest",
    sha_ref: str = "",
    *,
    background: bool = True,
) -> Tuple[List[str], str]:
    """Lanza OTA del programa gateway.

    Por defecto arranca en background (el servicio se reinicia al final).
    Use PI UPDATE STATUS para seguir el progreso.
    """
    lines = ["[FR3D] PI UPDATE GATEWAY"]
    script = _gateway_update_script()
    if not script.is_file():
        lines.append(f"ERROR: no existe {script}")
        return lines, "ERROR"

    target = (target or "latest").strip() or "latest"
    sha_ref = (sha_ref or "").strip()
    env = dict(os.environ)
    env["FR3D_CONTROL_PYTHON"] = str(_control_python_root())
    env.setdefault("FR3D_UPDATE_BASE", _DEFAULT_UPDATE_BASE)

    cmd = ["/bin/bash", str(script), "apply", target]
    if sha_ref:
        cmd.append(sha_ref)

    if background:
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(_control_python_root()),
                env=env,
                start_new_session=True,
            )
        except OSError as exc:
            lines.append(f"ERROR al lanzar update: {exc}")
            return lines, "ERROR"
        lines.append(f"target={target}")
        lines.append("Actualizacion iniciada en background.")
        lines.append("Siga el progreso con: PI UPDATE STATUS")
        lines.append("(El gateway se reiniciara al finalizar.)")
        return lines, "INFO"

    code, out, err = _run(cmd, timeout=600.0)
    body = (out or err or "").strip()
    if body:
        lines.extend(body.splitlines())
    else:
        lines.append(f"(sin salida; exit {code})")
    return lines, "INFO" if code == 0 else "ERROR"


def _read_web_version_local() -> str:
    path = _control_python_root() / "fr3d_web" / "web_build_id.txt"
    try:
        return path.read_text(encoding="utf-8").strip() or "none"
    except OSError:
        return "none"


def _read_web_update_status_file() -> Dict[str, str]:
    try:
        import json

        raw = _WEB_UPDATE_STATUS.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) if v is not None else "" for k, v in data.items()}
    except Exception:
        pass
    return {}


def pi_update_ui_status() -> Tuple[List[str], str]:
    lines = ["[FR3D] PI UPDATE UI STATUS"]
    lines.append(f"version_local={_read_web_version_local()}")
    st = _read_web_update_status_file()
    if not st:
        lines.append("state=idle")
        lines.append("message=sin actualizaciones UI recientes")
        return lines, "INFO"
    for key in (
        "state",
        "message",
        "from_version",
        "to_version",
        "updated_at",
        "web_root",
    ):
        if key in st and st[key]:
            lines.append(f"{key}={st[key]}")
    return lines, "INFO"


def pi_update_ui_check(manifest_url: str = "") -> Tuple[List[str], str]:
    lines = ["[FR3D] PI UPDATE UI CHECK"]
    script = _web_update_script()
    if not script.is_file():
        lines.append(f"ERROR: no existe {script}")
        return lines, "ERROR"
    url = (manifest_url or "").strip()
    if not url and _DEFAULT_UPDATE_BASE:
        url = f"{_DEFAULT_UPDATE_BASE}/MANIFEST-WEB.json"
    args = ["/bin/bash", str(script), "check"]
    if url:
        args.append(url)
    code, out, err = _run(args, timeout=60.0)
    body = (out or err or "").strip()
    if body:
        lines.extend(body.splitlines())
    else:
        lines.append(f"(sin salida; exit {code})")
    return lines, "INFO" if code == 0 else "ERROR"


def pi_update_ui(
    target: str = "latest",
    sha_ref: str = "",
    *,
    background: bool = True,
) -> Tuple[List[str], str]:
    """Actualiza fr3d_web (Flutter LAN) sin reiniciar el gateway."""
    lines = ["[FR3D] PI UPDATE UI"]
    script = _web_update_script()
    if not script.is_file():
        lines.append(f"ERROR: no existe {script}")
        return lines, "ERROR"

    target = (target or "latest").strip() or "latest"
    sha_ref = (sha_ref or "").strip()
    env = dict(os.environ)
    env["FR3D_CONTROL_PYTHON"] = str(_control_python_root())
    env.setdefault("FR3D_UPDATE_BASE", _DEFAULT_UPDATE_BASE)

    cmd = ["/bin/bash", str(script), "apply", target]
    if sha_ref:
        cmd.append(sha_ref)

    if background:
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(_control_python_root()),
                env=env,
                start_new_session=True,
            )
        except OSError as exc:
            lines.append(f"ERROR al lanzar update UI: {exc}")
            return lines, "ERROR"
        lines.append(f"target={target}")
        lines.append("Actualizacion UI iniciada en background.")
        lines.append("Siga el progreso con: PI UPDATE UI STATUS")
        lines.append("(nginx reload; el gateway no se reinicia.)")
        return lines, "INFO"

    code, out, err = _run(cmd, timeout=600.0)
    body = (out or err or "").strip()
    if body:
        lines.extend(body.splitlines())
    else:
        lines.append(f"(sin salida; exit {code})")
    return lines, "INFO" if code == 0 else "ERROR"
