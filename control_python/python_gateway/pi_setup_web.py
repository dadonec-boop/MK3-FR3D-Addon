"""Panel HTTP local en la Pi: estado LAN (WiFi se configura en la app Flutter)."""
from __future__ import annotations

import argparse
import html
import http.cookies
import json
import os
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from python_gateway.gateway_pi_host import (
    get_connected_wifi_ssid,
    get_wlan_ipv4,
    get_wlan_mac_address,
    is_linux_gateway_host,
)

DEFAULT_USER = "addonfr3d"
DEFAULT_PASS = "addonfr3d"
DEFAULT_PORT = 8080
DEFAULT_LANG = "en"
LANG_COOKIE = "fr3d_setup_lang"
AUTH_FILE = Path("/var/lib/fr3d/setup_auth.json")

_PAGE_STYLE = """
body{font-family:system-ui,sans-serif;max-width:640px;margin:1.5rem auto;padding:0 1rem;color:#222}
h1{font-size:1.35rem} h2{font-size:1.1rem;margin-top:1.5rem}
a{color:#1565c0} nav a{margin-right:.75rem}
.lang{margin:.5rem 0 1rem;font-size:.9rem}
.lang a{margin-right:.5rem;text-decoration:none;padding:.15rem .4rem;border-radius:4px}
.lang a.on{font-weight:700;background:#e3f2fd}
.card{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0;background:#fafafa}
label{display:block;margin:.5rem 0 .2rem;font-weight:600}
input,select,button{font-size:1rem;padding:.45rem .6rem;margin:.25rem 0}
button{background:#1565c0;color:#fff;border:none;border-radius:6px;cursor:pointer}
button.secondary{background:#666}
.msg{padding:.6rem;border-radius:6px;margin:.8rem 0}
.msg.ok{background:#e8f5e9}.msg.err{background:#ffebee}
table{width:100%;border-collapse:collapse;font-size:.95rem}
td,th{border-bottom:1px solid #eee;padding:.4rem;text-align:left}
tr:hover{background:#f5f5f5}
.hint{color:#666;font-size:.85rem}
.tag{font-size:.75rem;color:#666;margin-left:.35rem}
"""

# clave -> {en, es, de}
_I18N: Dict[str, Dict[str, str]] = {
    "title_login": {"en": "Sign in", "es": "Ingresar", "de": "Anmelden"},
    "title_status": {"en": "Status", "es": "Estado", "de": "Status"},
    "title_wifi": {"en": "WiFi", "es": "WiFi", "de": "WLAN"},
    "title_password": {"en": "Change password", "es": "Cambiar clave", "de": "Passwort ändern"},
    "title_404": {"en": "Not found", "es": "No encontrado", "de": "Nicht gefunden"},
    "nav_status": {"en": "Status", "es": "Estado", "de": "Status"},
    "nav_wifi": {"en": "WiFi", "es": "WiFi", "de": "WLAN"},
    "nav_password": {"en": "Change password", "es": "Cambiar clave", "de": "Passwort ändern"},
    "nav_logout": {"en": "Sign out", "es": "Salir", "de": "Abmelden"},
    "user": {"en": "Username", "es": "Usuario", "de": "Benutzer"},
    "password": {"en": "Password", "es": "Clave", "de": "Passwort"},
    "current_password": {"en": "Current password", "es": "Clave actual", "de": "Aktuelles Passwort"},
    "new_password": {"en": "New password", "es": "Clave nueva", "de": "Neues Passwort"},
    "confirm_password": {"en": "Confirm new password", "es": "Confirmar clave", "de": "Passwort bestätigen"},
    "submit_login": {"en": "Sign in", "es": "Entrar", "de": "Anmelden"},
    "submit_save": {"en": "Save", "es": "Guardar", "de": "Speichern"},
    "submit_connect": {"en": "Connect", "es": "Conectar", "de": "Verbinden"},
    "submit_remove": {"en": "Remove", "es": "Quitar", "de": "Entfernen"},
    "submit_save_connect": {"en": "Save and connect", "es": "Guardar y conectar", "de": "Speichern und verbinden"},
    "login_hint": {
        "en": "Default: addonfr3d / addonfr3d",
        "es": "Por defecto: addonfr3d / addonfr3d",
        "de": "Standard: addonfr3d / addonfr3d",
    },
    "login_error": {
        "en": "Incorrect username or password.",
        "es": "Usuario o clave incorrectos.",
        "de": "Benutzername oder Passwort falsch.",
    },
    "wifi_label": {"en": "WiFi", "es": "WiFi", "de": "WLAN"},
    "ip_label": {"en": "LAN IP", "es": "IP LAN", "de": "LAN-IP"},
    "mac_label": {"en": "WLAN MAC", "es": "MAC wlan", "de": "WLAN-MAC"},
    "gateway_label": {"en": "Gateway", "es": "Gateway", "de": "Gateway"},
    "pi_label": {"en": "Raspberry Pi", "es": "Raspberry Pi", "de": "Raspberry Pi"},
    "pi_yes": {"en": "Yes", "es": "Sí", "de": "Ja"},
    "pi_no": {"en": "No (dev mode)", "es": "No (modo dev)", "de": "Nein (Dev-Modus)"},
    "none": {"en": "(none)", "es": "(ninguna)", "de": "(keine)"},
    "configure_wifi": {"en": "Configure WiFi →", "es": "Configurar WiFi →", "de": "WLAN einrichten →"},
    "wifi_in_app": {
        "en": "WiFi is configured in the control app: CONFIG → WiFi.",
        "es": "El WiFi se configura en la app de control: CONFIG → WiFi.",
        "de": "WLAN wird in der Steuer-App eingerichtet: KONFIG → WLAN.",
    },
    "saved_networks": {"en": "Saved networks", "es": "Redes guardadas", "de": "Gespeicherte Netze"},
    "visible_networks": {"en": "Visible networks", "es": "Redes visibles", "de": "Sichtbare Netze"},
    "scan_hint": {
        "en": "Scanning may take a few seconds.",
        "es": "El escaneo tarda unos segundos.",
        "de": "Der Scan kann einige Sekunden dauern.",
    },
    "no_saved": {"en": "(none)", "es": "(ninguna)", "de": "(keine)"},
    "no_visible": {
        "en": "No networks found. Check antenna and nmcli permissions.",
        "es": "No se ven redes. Compruebe antena y permisos nmcli.",
        "de": "Keine Netze gefunden. Antenne und nmcli-Berechtigungen prüfen.",
    },
    "add_manual": {"en": "Add network manually", "es": "Agregar red manual", "de": "Netz manuell hinzufügen"},
    "ssid": {"en": "SSID", "es": "SSID", "de": "SSID"},
    "wifi_password": {
        "en": "Password (empty = open)",
        "es": "Clave (vacío = abierta)",
        "de": "Passwort (leer = offen)",
    },
    "wifi_password_ph": {
        "en": "password (optional)",
        "es": "clave (opcional)",
        "de": "Passwort (optional)",
    },
    "col_network": {"en": "Network", "es": "Red", "de": "Netz"},
    "col_signal": {"en": "Signal", "es": "Señal", "de": "Signal"},
    "col_sec": {"en": "Sec.", "es": "Seg.", "de": "Sich."},
    "protected_network": {
        "en": "(protected)",
        "es": "(protegida)",
        "de": "(geschützt)",
    },
    "err_empty_ssid": {"en": "SSID is empty.", "es": "SSID vacío.", "de": "SSID leer."},
    "err_wifi_add": {"en": "Could not save network.", "es": "Error al guardar red.", "de": "Netz konnte nicht gespeichert werden."},
    "err_connect": {"en": "Connection failed.", "es": "Error de conexión.", "de": "Verbindung fehlgeschlagen."},
    "err_remove": {"en": "Could not remove profile.", "es": "No se pudo quitar.", "de": "Profil konnte nicht entfernt werden."},
    "err_protected_wifi": {
        "en": "The addonfr3d network cannot be removed.",
        "es": "La red addonfr3d no se puede quitar.",
        "de": "Das Netz addonfr3d kann nicht entfernt werden.",
    },
    "msg_connected": {"en": "Connected to {ssid}", "es": "Conectado a {ssid}", "de": "Verbunden mit {ssid}"},
    "msg_removed": {"en": "Profile {ssid} removed", "es": "Perfil {ssid} eliminado", "de": "Profil {ssid} entfernt"},
    "err_wrong_current": {
        "en": "Current password is incorrect.",
        "es": "La clave actual es incorrecta.",
        "de": "Aktuelles Passwort ist falsch.",
    },
    "err_password_short": {
        "en": "New password must be at least 4 characters.",
        "es": "La clave nueva debe tener al menos 4 caracteres.",
        "de": "Neues Passwort: mindestens 4 Zeichen.",
    },
    "err_password_mismatch": {
        "en": "New passwords do not match.",
        "es": "Las claves nuevas no coinciden.",
        "de": "Neue Passwörter stimmen nicht überein.",
    },
    "msg_password_saved": {
        "en": "Password updated.",
        "es": "Clave actualizada.",
        "de": "Passwort aktualisiert.",
    },
    "err_password_save": {
        "en": "Could not save password.",
        "es": "No se pudo guardar la clave.",
        "de": "Passwort konnte nicht gespeichert werden.",
    },
    "not_found": {"en": "Not found.", "es": "No encontrado.", "de": "Nicht gefunden."},
    "lang_en": {"en": "English", "es": "English", "de": "English"},
    "lang_es": {"en": "Español", "es": "Español", "de": "Español"},
    "lang_de": {"en": "Deutsch", "es": "Deutsch", "de": "Deutsch"},
}


def _t(lang: str, key: str, **kwargs: object) -> str:
    entry = _I18N.get(key, {})
    text = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def _load_credentials() -> Tuple[str, str]:
    if AUTH_FILE.is_file():
        try:
            data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
            user = str(data.get("user") or DEFAULT_USER)
            pw = str(data.get("password") or DEFAULT_PASS)
            return user, pw
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return DEFAULT_USER, DEFAULT_PASS


def _save_credentials(user: str, password: str) -> bool:
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"user": user, "password": password}, indent=2)
    try:
        AUTH_FILE.write_text(payload + "\n", encoding="utf-8")
        os.chmod(AUTH_FILE, 0o600)
        return True
    except OSError:
        return False


def _parse_cookies(cookie_header: str) -> http.cookies.SimpleCookie:
    jar = http.cookies.SimpleCookie()
    if cookie_header:
        try:
            jar.load(cookie_header)
        except http.cookies.CookieError:
            pass
    return jar


def _lang_from_cookies(cookie_header: str) -> str:
    jar = _parse_cookies(cookie_header)
    morsel = jar.get(LANG_COOKIE)
    if morsel and morsel.value in ("en", "es", "de"):
        return morsel.value
    return DEFAULT_LANG


def _esc(text: object) -> str:
    return html.escape(str(text or ""), quote=True)


def _gateway_active() -> str:
    for cmd in (
        ["systemctl", "is-active", "fr3d-gateway"],
        ["sudo", "-n", "systemctl", "is-active", "fr3d-gateway"],
    ):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if proc.returncode == 0:
                return (proc.stdout or "").strip() or "?"
        except (OSError, subprocess.TimeoutExpired):
            continue
    return "?"


def _parse_form(body: bytes) -> Dict[str, str]:
    raw = body.decode("utf-8", errors="replace")
    return {k: v for k, v in urllib.parse.parse_qsl(raw, keep_blank_values=True)}


class SetupHandler(BaseHTTPRequestHandler):
    server_version = "FR3D-Setup/1.1"
    _pending_cookies: List[str]

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _lang(self, query: Optional[Dict[str, List[str]]] = None) -> str:
        if query:
            raw = (query.get("lang") or [""])[0]
            if raw in ("en", "es", "de"):
                return raw
        return _lang_from_cookies(self.headers.get("Cookie", ""))

    def _queue_cookie(self, value: str) -> None:
        if not hasattr(self, "_pending_cookies"):
            self._pending_cookies = []
        self._pending_cookies.append(value)

    def _redirect(self, path: str, *, cookies: Optional[List[str]] = None) -> None:
        self.send_response(303)
        self.send_header("Location", path)
        for c in cookies or []:
            self.send_header("Set-Cookie", c)
        for c in getattr(self, "_pending_cookies", []):
            self.send_header("Set-Cookie", c)
        self.end_headers()

    def _html(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for c in getattr(self, "_pending_cookies", []):
            self.send_header("Set-Cookie", c)
        self.end_headers()
        self.wfile.write(body)

    def _set_lang_cookie(self, lang: str) -> None:
        self._queue_cookie(f"{LANG_COOKIE}={lang}; Path=/; Max-Age=31536000; SameSite=Lax")

    def _lang_switcher(self, lang: str) -> str:
        parts = []
        for code, label_key in (("en", "lang_en"), ("es", "lang_es"), ("de", "lang_de")):
            cls = ' class="on"' if code == lang else ""
            parts.append(f'<a href="?lang={code}"{cls}>{_esc(_t(lang, label_key))}</a>')
        return '<div class="lang">' + "".join(parts) + "</div>"

    def _layout(self, lang: str, title_key: str, body: str, *, nav: bool = True) -> bytes:
        if nav:
            nav_html = (
                f'<nav><a href="/">{_esc(_t(lang, "nav_status"))}</a>'
                f'<a href="/password">{_esc(_t(lang, "nav_password"))}</a></nav>'
            )
        else:
            nav_html = ""
        doc = f"""<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(_t(lang, title_key))} — FR3D Setup</title>
<style>{_PAGE_STYLE}</style></head>
<body>
<h1>FR3D Setup</h1>
{self._lang_switcher(lang)}
{nav_html}
{body}
</body></html>"""
        return doc.encode("utf-8")

    def do_GET(self) -> None:
        self._pending_cookies = []
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        lang = self._lang(query)
        if query.get("lang"):
            self._set_lang_cookie(lang)

        if path in ("/login", "/login/", "/wifi", "/wifi/"):
            self._redirect("/")
        elif path in ("/", "/status"):
            self._get_status(lang, query)
        elif path in ("/password", "/password/"):
            self._get_password(lang, query)
        else:
            self._html(404, self._layout(lang, "title_404", f"<p>{_esc(_t(lang, 'not_found'))}</p>", nav=False))

    def do_POST(self) -> None:
        self._pending_cookies = []
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        path = urllib.parse.urlparse(self.path).path
        form = _parse_form(body)
        lang = _lang_from_cookies(self.headers.get("Cookie", ""))

        if path in ("/login", "/login/", "/logout", "/logout/", "/wifi/connect", "/wifi/connect/", "/wifi/remove", "/wifi/remove/"):
            self._redirect("/")
        elif path in ("/password", "/password/"):
            self._post_password(lang, form)
        else:
            self._html(404, self._layout(lang, "title_404", f"<p>{_esc(_t(lang, 'not_found'))}</p>", nav=False))

    def _banner(self, lang: str, query: Dict[str, List[str]]) -> str:
        msg = (query.get("msg") or [""])[0]
        err = (query.get("err") or [""])[0]
        banner = ""
        if msg:
            banner += f'<div class="msg ok">{_esc(msg)}</div>'
        if err:
            banner += f'<div class="msg err">{_esc(err)}</div>'
        return banner

    def _get_status(self, lang: str, query: Dict[str, List[str]]) -> None:
        ssid = get_connected_wifi_ssid() or _t(lang, "none")
        ip = get_wlan_ipv4() or "—"
        mac = get_wlan_mac_address() or "—"
        gw = _gateway_active()
        pi = _t(lang, "pi_yes") if is_linux_gateway_host() else _t(lang, "pi_no")
        body = self._layout(
            lang,
            "title_status",
            self._banner(lang, query)
            + f"""<div class="card">
<p><b>{_esc(_t(lang, "wifi_label"))}:</b> {_esc(ssid)}</p>
<p><b>{_esc(_t(lang, "ip_label"))}:</b> {_esc(ip)}</p>
<p><b>{_esc(_t(lang, "mac_label"))}:</b> {_esc(mac)}</p>
<p><b>{_esc(_t(lang, "gateway_label"))}:</b> {_esc(gw)}</p>
<p><b>{_esc(_t(lang, "pi_label"))}:</b> {_esc(pi)}</p>
</div>
<p class="hint">{_esc(_t(lang, "wifi_in_app"))}</p>""",
        )
        self._html(200, body)

    def _get_password(self, lang: str, query: Dict[str, List[str]]) -> None:
        body = self._layout(
            lang,
            "title_password",
            self._banner(lang, query)
            + f"""<div class="card">
<form method="post" action="/password">
<label>{_esc(_t(lang, "current_password"))}</label>
<input name="current" type="password" autocomplete="current-password" required>
<label>{_esc(_t(lang, "new_password"))}</label>
<input name="new_password" type="password" autocomplete="new-password" required>
<label>{_esc(_t(lang, "confirm_password"))}</label>
<input name="confirm" type="password" autocomplete="new-password" required>
<button type="submit">{_esc(_t(lang, "submit_save"))}</button>
</form>
</div>""",
        )
        self._html(200, body)

    def _post_password(self, lang: str, form: Dict[str, str]) -> None:
        user, pw = _load_credentials()
        current = str(form.get("current") or "")
        new_pw = str(form.get("new_password") or "")
        confirm = str(form.get("confirm") or "")

        if current != pw:
            self._redirect("/password?err=" + urllib.parse.quote(_t(lang, "err_wrong_current")))
            return
        if len(new_pw) < 4:
            self._redirect("/password?err=" + urllib.parse.quote(_t(lang, "err_password_short")))
            return
        if new_pw != confirm:
            self._redirect("/password?err=" + urllib.parse.quote(_t(lang, "err_password_mismatch")))
            return
        if not _save_credentials(user, new_pw):
            self._redirect("/password?err=" + urllib.parse.quote(_t(lang, "err_password_save")))
            return
        self._redirect("/password?msg=" + urllib.parse.quote(_t(lang, "msg_password_saved")))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="FR3D setup web (HTTP LAN)")
    parser.add_argument("--host", default="0.0.0.0", help="bind address (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("FR3D_SETUP_PORT", DEFAULT_PORT)))
    args = parser.parse_args(argv)

    if not is_linux_gateway_host():
        print("[FR3D Setup] Aviso: no parece Pi/UNO Q; modo desarrollo.", file=sys.stderr)

    httpd = ThreadingHTTPServer((args.host, args.port), SetupHandler)
    print(f"[FR3D Setup] http://{args.host}:{args.port}/  (sin login; WiFi en la app Flutter)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[FR3D Setup] Detenido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
