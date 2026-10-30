"""Identidad hardware del gateway (Pi/UNO Q: serial+MAC; Windows: MachineGuid+MAC)."""
from __future__ import annotations

import json
import re
import secrets
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from python_gateway.gateway_pi_host import (
    get_wlan_mac_address,
    is_linux_gateway_host,
    is_pi_gateway_host,
    is_uno_q_gateway_host,
)
from python_gateway.gateway_paths import app_dir

TOKEN_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
TOKEN_LENGTH = 8

_IDENTITY_FILENAME = "gateway_identity.json"
_MAC_RE = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


@dataclass(frozen=True)
class GatewayIdentity:
    serial: str
    mac: str
    mac_compact: str
    gateway_key: str

    @property
    def valid(self) -> bool:
        return bool(self.serial and self.mac_compact and self.gateway_key)


def get_pi_serial() -> str:
    if not is_pi_gateway_host():
        return ""
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("serial"):
                return line.split(":", 1)[-1].strip()
    except OSError:
        pass
    return ""


def get_uno_q_serial() -> str:
    """Serial estable: unoq + machine-id (hex, sin guiones)."""
    if not is_uno_q_gateway_host():
        return ""
    try:
        mid = Path("/etc/machine-id").read_text(encoding="utf-8").strip().lower()
        cleaned = re.sub(r"[^0-9a-f]", "", mid)
        if len(cleaned) >= 8:
            return f"unoq{cleaned}"
    except OSError:
        pass
    return ""


def get_windows_machine_serial() -> str:
    """Serial estable: win + MachineGuid (hex, sin guiones)."""
    if sys.platform != "win32":
        return ""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
        ) as key:
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        cleaned = re.sub(r"[^0-9a-fA-F]", "", str(guid)).lower()
        if len(cleaned) >= 8:
            return f"win{cleaned}"
    except OSError:
        pass
    return ""


def _format_mac_from_node(node: int) -> str:
    return ":".join(f"{(node >> ele) & 0xff:02x}" for ele in range(40, -1, -8))


def _normalize_mac(raw: str) -> str:
    mac = (raw or "").strip().lower().replace("-", ":")
    if not _MAC_RE.fullmatch(mac) or mac == "00:00:00:00:00:00":
        return ""
    return mac


def get_windows_mac_address() -> str:
    """Primera MAC fisica util (getmac); fallback uuid.getnode si no es random."""
    if sys.platform != "win32":
        return ""
    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW
    try:
        out = subprocess.check_output(
            ["getmac", "/fo", "csv", "/nh"],
            text=True,
            timeout=5,
            creationflags=creationflags,
        )
        for line in out.splitlines():
            part = line.split(",", 1)[0].strip().strip('"')
            mac = _normalize_mac(part)
            if mac:
                return mac
    except (OSError, subprocess.SubprocessError):
        pass
    node = uuid.getnode()
    # Bit multicast/localmente administrado => MAC aleatoria de Python
    if (node >> 40) & 1:
        return ""
    return _normalize_mac(_format_mac_from_node(node))


def get_host_serial() -> str:
    if is_pi_gateway_host():
        return get_pi_serial()
    if is_uno_q_gateway_host():
        return get_uno_q_serial()
    if sys.platform == "win32":
        return get_windows_machine_serial()
    return ""


def get_host_mac_address() -> str:
    if is_linux_gateway_host():
        return get_wlan_mac_address()
    if sys.platform == "win32":
        return get_windows_mac_address()
    return ""


def build_gateway_key(serial: str, mac: str) -> str:
    mac_compact = (mac or "").replace(":", "").strip().lower()
    serial = (serial or "").strip()
    if not serial or not mac_compact:
        return ""
    return f"{serial}-{mac_compact}"


def read_gateway_identity() -> GatewayIdentity:
    serial = get_host_serial()
    mac = get_host_mac_address()
    mac_compact = mac.replace(":", "") if mac else ""
    return GatewayIdentity(
        serial=serial,
        mac=mac,
        mac_compact=mac_compact,
        gateway_key=build_gateway_key(serial, mac),
    )


def identity_store_path(base: Path | None = None) -> Path:
    if is_linux_gateway_host():
        return Path("/var/lib/fr3d") / _IDENTITY_FILENAME
    root = base or app_dir()
    return root / "data" / _IDENTITY_FILENAME

def generate_gateway_token(length: int = TOKEN_LENGTH) -> str:
    n = max(6, min(12, int(length)))
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(n))


def load_persisted_token(path: Path, identity: GatewayIdentity) -> str:
    if not identity.valid or not path.is_file():
        return ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(raw, dict):
        return ""
    if (
        str(raw.get("gatewayKey") or "") != identity.gateway_key
        or str(raw.get("serial") or "") != identity.serial
        or str(raw.get("mac") or "") != identity.mac
    ):
        return ""
    token = str(raw.get("token") or "").strip().upper()
    if len(token) != TOKEN_LENGTH or not all(c in TOKEN_ALPHABET for c in token):
        return ""
    return token


def save_persisted_token(path: Path, identity: GatewayIdentity, token: str) -> None:
    if not identity.valid or not token:
        return
    payload = {
        "gatewayKey": identity.gateway_key,
        "serial": identity.serial,
        "mac": identity.mac,
        "token": token,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass
