#!/usr/bin/env bash
# Instala FR3D Python Gateway en Arduino UNO Q (Debian Linux MPU).
# Uso (en la UNO Q, desde control_python/):
#   chmod +x python_gateway/deploy/install_uno_q.sh
#   sudo bash python_gateway/deploy/install_uno_q.sh
# Opcional: sudo FR3D_INSTALL_DIR=/otra/ruta bash python_gateway/deploy/install_uno_q.sh
#
# Requisitos previos:
#   - SSH / App Lab con red
#   - Modulo CH340/CH341 cargado (ttyCH341USB0 / ttyCH341USB1)
#   - Hub USB con alimentacion PD correcta
if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SERVICE_NAME="fr3d-gateway"
SETUP_SERVICE_NAME="fr3d-setup"
SERVICE_SRC="$ROOT/python_gateway/deploy/fr3d-gateway.service"
SETUP_SERVICE_SRC="$ROOT/python_gateway/deploy/fr3d-setup.service"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}.service"
SETUP_SERVICE_DST="/etc/systemd/system/${SETUP_SERVICE_NAME}.service"
INSTALL_DIR="${FR3D_INSTALL_DIR:-$ROOT}"

echo "[FR3D] Instalacion gateway UNO Q en: $INSTALL_DIR"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecute con sudo: sudo FR3D_INSTALL_DIR=$INSTALL_DIR $0"
  exit 1
fi

if [[ ! -f "$ROOT/python_gateway/fr3d_gateway_main.py" ]]; then
  echo "ERROR: no se encuentra python_gateway (ejecute desde el repo clonado)."
  exit 1
fi

MODEL="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || true)"
MODEL_LC="$(echo "$MODEL" | tr '[:upper:]' '[:lower:]')"
if [[ "$MODEL_LC" != *imola* && "$MODEL_LC" != *arduino* ]]; then
  echo "[WARN] device-tree model='$MODEL' — no parece UNO Q; se continua igual."
fi

# Usuario que corre el servicio (quien invoco sudo, o arduino).
RUN_USER="${SUDO_USER:-${FR3D_RUN_USER:-arduino}}"
usermod -aG dialout "$RUN_USER" 2>/dev/null || true

# Venv propio del gateway
if [[ ! -x "$INSTALL_DIR/python_gateway/.venv/bin/python" ]]; then
  echo "[FR3D] Creando venv..."
  if [[ -x "$INSTALL_DIR/setup_gateway_venv.sh" ]]; then
    sudo -u "$RUN_USER" bash -c "cd '$INSTALL_DIR' && ./setup_gateway_venv.sh"
  else
    echo "ERROR: falta setup_gateway_venv.sh en $INSTALL_DIR"
    exit 1
  fi
fi

# systemd: ajustar rutas en la unidad (plantilla Pi -> ruta real)
sed "s|/home/pi/fr3d/control_python|$INSTALL_DIR|g" "$SERVICE_SRC" > "$SERVICE_DST"
sed -i "s|^User=.*|User=$RUN_USER|" "$SERVICE_DST"
sed -i "s|^Group=.*|Group=$RUN_USER|" "$SERVICE_DST"

# WiFi / NetworkManager para comandos Totem/Flutter (WIFI ADD, CONNECT, ...).
POLKIT_RULE="/etc/polkit-1/rules.d/49-fr3d-gateway-wifi.rules"
cat > "$POLKIT_RULE" <<EOF
polkit.addRule(function(action, subject) {
    if (subject.user == "$RUN_USER" &&
        action.id.indexOf("org.freedesktop.NetworkManager.") === 0) {
        return polkit.Result.YES;
    }
});
EOF
chmod 644 "$POLKIT_RULE"

SUDOERS_FILE="/etc/sudoers.d/fr3d-gateway-nmcli"
cat > "$SUDOERS_FILE" <<EOF
# FR3D gateway UNO Q: comandos sin password interactivo
$RUN_USER ALL=(ALL) NOPASSWD: /usr/bin/nmcli
$RUN_USER ALL=(ALL) NOPASSWD: /usr/sbin/reboot
$RUN_USER ALL=(ALL) NOPASSWD: /usr/sbin/shutdown
$RUN_USER ALL=(ALL) NOPASSWD: /bin/systemctl
EOF
chmod 440 "$SUDOERS_FILE"

mkdir -p /var/lib/fr3d
chown "$RUN_USER:$RUN_USER" /var/lib/fr3d
chmod 750 /var/lib/fr3d
mkdir -p "/home/$RUN_USER/secrets"
chown "$RUN_USER:$RUN_USER" "/home/$RUN_USER/secrets"
chmod 700 "/home/$RUN_USER/secrets"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# Primer arranque post-clon / imagen de fabrica: identidad unica.
FIRST_BOOT_SERVICE_NAME="fr3d-first-boot-clone"
FIRST_BOOT_SERVICE_SRC="$ROOT/python_gateway/deploy/fr3d-first-boot-clone.service"
FIRST_BOOT_SERVICE_DST="/etc/systemd/system/${FIRST_BOOT_SERVICE_NAME}.service"
LIB_MARKER="/var/lib/fr3d/first-boot-clone-fix.done"
if [[ -f "$FIRST_BOOT_SERVICE_SRC" ]]; then
  FIRST_BOOT_SH="$INSTALL_DIR/python_gateway/deploy/first_boot_clone_fix.sh"
  chmod +x "$FIRST_BOOT_SH" || true
  sed "s|/home/pi/fr3d/control_python|$INSTALL_DIR|g" "$FIRST_BOOT_SERVICE_SRC" > "$FIRST_BOOT_SERVICE_DST"
  systemctl daemon-reload
  systemctl enable "$FIRST_BOOT_SERVICE_NAME"
  echo "[FR3D] Servicio $FIRST_BOOT_SERVICE_NAME habilitado (una vez si no existe $LIB_MARKER)."
fi

# Panel HTTP local (estado) — puerto 8080, solo LAN.
if [[ -f "$SETUP_SERVICE_SRC" ]]; then
  sed "s|/home/pi/fr3d/control_python|$INSTALL_DIR|g" "$SETUP_SERVICE_SRC" > "$SETUP_SERVICE_DST"
  sed -i "s|^User=.*|User=$RUN_USER|" "$SETUP_SERVICE_DST"
  sed -i "s|^Group=.*|Group=$RUN_USER|" "$SETUP_SERVICE_DST"
  systemctl enable "$SETUP_SERVICE_NAME"
  systemctl restart "$SETUP_SERVICE_NAME"
  echo "[FR3D] Servicio $SETUP_SERVICE_NAME en http://<IP-LAN>:8080/"
fi

echo
echo "[FR3D] Servicio $SERVICE_NAME habilitado (arranque automatico)."
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"

# nginx: Flutter LAN (puerto 80) + /api → gateway 8765 + /setup → 8080.
WEB_ROOT="$INSTALL_DIR/fr3d_web"
NGINX_SRC="$ROOT/python_gateway/deploy/nginx-fr3d.conf"
NGINX_DST="/etc/nginx/sites-available/fr3d"
mkdir -p "$WEB_ROOT"
if [[ ! -f "$WEB_ROOT/lan.json" && -f "$ROOT/fr3d_web/lan.json" ]]; then
  cp -a "$ROOT/fr3d_web/." "$WEB_ROOT/"
fi
if [[ ! -f "$WEB_ROOT/index.html" && -f "$ROOT/fr3d_web/index.html" ]]; then
  cp -a "$ROOT/fr3d_web/." "$WEB_ROOT/"
fi
chown -R "$RUN_USER:$RUN_USER" "$WEB_ROOT" 2>/dev/null || true
chmod -R a+rX "$WEB_ROOT" 2>/dev/null || true
_path="$WEB_ROOT"
while [[ "$_path" != "/" && -n "$_path" ]]; do
  chmod a+x "$_path" 2>/dev/null || true
  _path="$(dirname "$_path")"
done
if [[ -f "$NGINX_SRC" ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y nginx || echo "[WARN] apt nginx fallo"
  fi
  sed "s|__FR3D_WEB_ROOT__|$WEB_ROOT|g" "$NGINX_SRC" > "$NGINX_DST"
  rm -f /etc/nginx/sites-enabled/default
  ln -sfn "$NGINX_DST" /etc/nginx/sites-enabled/fr3d
  if nginx -t 2>/dev/null; then
    systemctl enable nginx
    systemctl reload nginx || systemctl restart nginx
    echo "[FR3D] nginx LAN http://<IP-LAN>/  (Flutter)  /setup/  /api/"
  else
    echo "[WARN] nginx -t fallo; revise $NGINX_DST"
  fi
fi

echo
echo "Revise config_gateway.csv:"
echo "  USB: mk3_link_mode=usb, port_fr3d_usb=/dev/ttyCH341USB0  (o el del MK3)"
echo "  BDWidth: suele ser el otro /dev/ttyCH341USB1"
echo "  Comandos:      SERIAL | SERIAL SET PORT /dev/ttyCH341USB0"
echo
echo "Verifique CH340:"
echo "  ls -l /dev/ttyCH341USB*"
