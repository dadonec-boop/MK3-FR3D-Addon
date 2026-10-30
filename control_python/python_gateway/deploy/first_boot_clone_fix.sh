#!/usr/bin/env bash
# Personaliza identidad de una Pi / UNO Q (imagen de fabrica clonada).
# Pensado para correr SOLO al primer arranque via systemd (usuarios no lo ejecutan).
#
# Manual (opcional):
#   sudo bash python_gateway/deploy/first_boot_clone_fix.sh --auto
#   sudo bash python_gateway/deploy/first_boot_clone_fix.sh --force fr3dgateway2
set -euo pipefail

MARKER="/var/lib/fr3d/first-boot-clone-fix.done"
FORCE=0
AUTO=0
NEW_HOST=""

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --auto) AUTO=1 ;;
    -h|--help)
      echo "Uso: sudo $0 [--auto] [--force] [hostname]"
      echo "  --auto   Primer arranque (systemd): sin prompts; reinicia al final."
      echo "  hostname ej. fr3dgateway2 (default segun serial/MAC)"
      exit 0
      ;;
    *)
      if [[ -z "$NEW_HOST" ]]; then
        NEW_HOST="$arg"
      fi
      ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecute con sudo."
  exit 1
fi

if [[ -f "$MARKER" && "$FORCE" -ne 1 ]]; then
  echo "Ya ejecutado antes ($(cat "$MARKER" 2>/dev/null || echo '?'))."
  echo "Use --force para repetir."
  exit 0
fi

_is_uno_q() {
  local model
  model="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || true)"
  model="$(printf '%s' "$model" | tr '[:upper:]' '[:lower:]')"
  [[ "$model" == *imola* || "$model" == *arduino sa* ]]
}

OLD_HOST="$(hostname)"
SERIAL="$(awk '/Serial/ {print $3; exit}' /proc/cpuinfo 2>/dev/null || true)"
HOST_PREFIX="fr3dgateway"
if _is_uno_q; then
  HOST_PREFIX="fr3dunoq"
  # UNO Q no tiene Serial en cpuinfo; usar machine-id actual (antes de regenerar).
  if [[ -z "$SERIAL" && -f /etc/machine-id ]]; then
    SERIAL="$(tr -d '[:space:]' </etc/machine-id)"
  fi
fi

SERIAL_SUFFIX="${SERIAL: -4}"
if [[ -z "$SERIAL_SUFFIX" ]]; then
  MAC_COMPACT="$(tr -d ':\n' </sys/class/net/wlan0/address 2>/dev/null || true)"
  SERIAL_SUFFIX="${MAC_COMPACT: -4}"
fi
if [[ -z "$SERIAL_SUFFIX" ]]; then
  SERIAL_SUFFIX="$(tr -dc 'a-f0-9' </dev/urandom | head -c 4)"
fi

if [[ -z "$NEW_HOST" ]]; then
  NEW_HOST="${HOST_PREFIX}-${SERIAL_SUFFIX}"
fi

WLAN_MAC="$(cat /sys/class/net/wlan0/address 2>/dev/null || echo '?')"

echo "=============================================="
echo " FR3D first_boot_clone_fix"
echo " Hostname: $OLD_HOST -> $NEW_HOST"
echo " Serial:   ${SERIAL:-desconocido}"
echo " MAC wlan0: $WLAN_MAC"
echo " Host:     $( _is_uno_q && echo 'UNO Q' || echo 'Pi/otro' )"
echo " Mode:     $([[ "$AUTO" -eq 1 ]] && echo auto || echo manual)"
echo "=============================================="

set_hostname() {
  local h="$1"
  if command -v hostnamectl >/dev/null 2>&1; then
    if hostnamectl set-hostname "$h" 2>/dev/null; then
      return 0
    fi
    echo "AVISO: hostnamectl fallo (dbus?); usando /etc/hostname"
  fi
  printf '%s\n' "$h" > /etc/hostname
  hostname "$h" 2>/dev/null || true
}

set_hostname "$NEW_HOST"

if [[ -f /etc/hosts ]]; then
  sed -i "s/\b${OLD_HOST}\b/${NEW_HOST}/g" /etc/hosts
  if ! grep -q "$NEW_HOST" /etc/hosts; then
    echo "127.0.1.1	${NEW_HOST}" >> /etc/hosts
  fi
fi

echo "[1/4] machine-id..."
rm -f /etc/machine-id /var/lib/dbus/machine-id 2>/dev/null || true
systemd-machine-id-setup
# Re-sincronizar dbus machine-id si existe el directorio
if [[ -d /var/lib/dbus ]]; then
  ln -sf /etc/machine-id /var/lib/dbus/machine-id 2>/dev/null || \
    cp -f /etc/machine-id /var/lib/dbus/machine-id 2>/dev/null || true
fi

echo "[2/4] Claves SSH del servidor..."
rm -f /etc/ssh/ssh_host_*
DEBIAN_FRONTEND=noninteractive dpkg-reconfigure openssh-server >/dev/null 2>&1 || true
systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true

echo "[3/4] Cliente DHCP (duid)..."
rm -f /var/lib/dhcpcd/duid 2>/dev/null || true
rm -f /var/lib/NetworkManager/dhclient-*.lease 2>/dev/null || true

echo "[4/4] Raspberry Pi Connect (solo Pi)..."
if command -v rpi-connect >/dev/null 2>&1; then
  rpi-connect off 2>/dev/null || true
  rpi-connect signout 2>/dev/null || true
  rpi-connect on 2>/dev/null || true
  if [[ "$AUTO" -ne 1 ]]; then
    echo "Opcional mas tarde: rpi-connect signin"
  fi
else
  echo "    (rpi-connect no instalado; omitido)"
fi

mkdir -p "$(dirname "$MARKER")"
{
  echo "hostname=$NEW_HOST"
  echo "serial=$SERIAL"
  echo "mac_wlan0=$WLAN_MAC"
  echo "auto=$AUTO"
  echo "uno_q=$( _is_uno_q && echo 1 || echo 0 )"
  echo "date=$(date -Is 2>/dev/null || date)"
} > "$MARKER"

echo ""
echo "Identidad lista (hostname=$NEW_HOST)."
if [[ "$AUTO" -eq 1 ]]; then
  echo "Reiniciando para aplicar machine-id/hostname..."
  sleep 2
  systemctl reboot
else
  echo "Reinicie:  sudo reboot"
fi
