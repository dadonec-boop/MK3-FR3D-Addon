#!/usr/bin/env python3
"""
Captura CSV del puerto USB serie MK3S+ FR3D (telemetría + material/lote).

1) Abre el puerto FR3D (250000 baud por defecto).
2) Espera boot, limpia buffers y envía ST para sincronizar muestreo (~10 s).
3) Cada fila: fecha_hora_pc_fr3d + columnas FR3D + metadatos material.

  pip install pyserial
  python control_and_merge_dual_serial_csv.py --fr3d COM7
  python control_and_merge_dual_serial_csv.py --list
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import threading
import time
import traceback
from pathlib import Path
from dataclasses import dataclass
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
from queue import Empty, Queue
from typing import Deque, Dict, List, Optional, Sequence, Tuple

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("Install pyserial: pip install pyserial", file=sys.stderr)
    sys.exit(1)

from ui_config_csv import resolve_app_data_path

# Logging convention (keep all runtime logs in English):
# [INFO] normal lifecycle/status updates
# [WARN] recoverable anomalies/timeouts
# [ERROR] failures requiring user attention/action
# [ACK src] device acknowledgements and protocol feedback
# [BOOT src] boot/startup lines captured from serial devices
# [OK] successful merge/progress milestones

# Cabeceras por defecto si el stream ya pasó la línea de cabecera
DEFAULT_HEADER_FR3D = (
    "FR3D,T,t_act,t_tgt,E_state,S_w,diam_prom_mm,diam_max_mm,diam_min_mm,ext_rpm,pull_rpm,L_m,status,fan_pct,pull_mode,sinfin,"
    "corr_drop_n,corr_jump_hold,fifo_n_used,fifo_n_raw,med_raw_mm,med_pub_mm,jump_pending_mm,servos"
)
# Columnas extra del MK3 cuando DIAMDEBUG=1 (fr3d_telemetry.cpp); OFF omite este bloque.
_DIAMDEBUG_EXTRA_COLS: Tuple[str, ...] = (
    "fifo_n_used",
    "fifo_n_raw",
    "med_raw_mm",
    "med_pub_mm",
    "jump_pending_mm",
)
# Legacy: bloque addon en CSV antiguos (solo lectura / import history).
DEFAULT_HEADER_MED = (
    "tramo,diam_prom_mm,diam_max_mm,diam_min_mm,temp_C,hum_pct,suelo_pct,servos,"
    "tolva_C,tolva_pwm_duty_pct,tolva_pwm,tolva_adc"
)

# Fecha y hora local del PC cuando cada linea llego por USB (ano-mes-dia + hora + ms)
COL_RECV_FR3D = "fecha_hora_pc_fr3d"
COL_RECV_MED = "fecha_hora_pc_med"  # solo CSV legacy dual-puerto
MATERIAL_COLUMNS = [
    "material",
    "type",
    "origen_trit",
    "col_tritur",
    "granulado",
    "sinfin_comp",
    "sinfin_comp_en",
    "batch",
    "pct_pla_v",
    "pct_col",
    "color_colorant",
    "mk3_doff",
    "pred_source",
    "pred_msg_main",
    "pred_msg_detail",
]


@dataclass
class AppState:
    addon_enabled: bool
    # True cuando la sesión se abrió sin puerto MK3 (solo STM32 addon); la UI usa esto para habilitar addon sin bootstrap MK3.
    addon_only_mode: bool = False
    mk3_connected: bool = False
    addon_connected: bool = False
    sync_ok: bool = False
    capture_active: bool = False
    measuring_active: bool = False
    fusion_counter: int = 0
    pending_mk3_queue: Deque[Tuple[str, datetime]] = field(default_factory=deque)
    pending_addon_queue: Deque[Tuple[str, datetime]] = field(default_factory=deque)
    last_mk3_row: Optional[Dict[str, str]] = None
    last_addon_row: Optional[Dict[str, str]] = None
    last_merged_row: Optional[List[str]] = None
    material_ctx: Dict[str, str] = field(default_factory=dict)
    last_mk3_ack: Optional[str] = None
    last_addon_ack: Optional[str] = None
    last_addon_cfg_snapshot: Optional[str] = None
    last_addon_query_cal: Optional[str] = None
    last_addon_med_line: Optional[str] = None
    last_command_sent: Optional[str] = None
    med_waiting_response: bool = False
    med_next_due_ts: Optional[float] = None
    med_last_sent_ts: Optional[float] = None
    # Respuesta multilínea QUERY (echo:R,..., echo:T,..., … hasta echo:G/M,...)
    mk3_query_collecting: bool = False
    mk3_query_lines: List[str] = field(default_factory=list)
    last_mk3_query_snapshot: Optional[str] = None
    mk3_csv_cycle_s: int = 2
    # DIAMQ: lecturas DLCD cada 1.5 s tras QUERY (1 shot con fusion 2 s).
    mk3_diamq_shots_left: int = 0
    mk3_diamq_next_due_mono: Optional[float] = None
    mk3_diamq_collecting: bool = False
    mk3_diamq_lines: List[str] = field(default_factory=list)
    mk3_diamq_sent_mono: Optional[float] = None
    last_mk3_dlcd_mm: Optional[float] = None
    # LCDQ remoto (espejo 4x20)
    mk3_lcdq_collecting: bool = False
    mk3_lcdq_lines: List[str] = field(default_factory=list)
    mk3_lcdq_sent_mono: Optional[float] = None
    mk3_lcdq_seq: int = 0
    last_mk3_lcd_snapshot: Optional[str] = None
    last_mk3_lcd_lines: List[str] = field(default_factory=list)
    # Tras sync ST: STOP + COOLDOWN enviados; la UI habilita comandos solo cuando es True.
    mk3_bootstrap_ready: bool = False
    # Archivo de captura activo y último CSV cerrado (para UX en pestaña análisis).
    current_capture_path: str = ""
    last_closed_capture_path: str = ""
    # Cabeceras reales detectadas durante la sesión (evita desalinear columnas en UI).
    header_fr3d: Optional[str] = None
    header_med: Optional[str] = None


@dataclass
class MergeRuntime:
    """Estado compartido y referencias a serie para UI o control externo durante run_merge."""

    state: AppState
    stop_event: threading.Event = field(default_factory=threading.Event)
    ser_fr3d: Optional[serial.Serial] = None
    ser_med: Optional[serial.Serial] = None
    finished: bool = False
    error_message: Optional[str] = None


def format_recv_ts(dt: datetime) -> str:
    """YYYY-MM-DDTHH:MM:SS.mmm (ISO local, fecha+hora completas)."""
    ms = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms:03d}"


def list_serial_ports() -> None:
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return
    for p in ports:
        print(f"  {p.device}  -  {p.description}")


def normalize_com_port(name: str) -> str:
    """
    En Windows, COM10 y superiores suelen necesitar el prefijo \\\\.\\
    Si no, pyserial puede fallar al abrir justo despues de escribir el segundo COM.
    """
    n = (name or "").strip()
    if not n:
        return n
    if sys.platform != "win32":
        return n
    up = n.upper()
    if not up.startswith("COM"):
        return n
    tail = up[3:]
    if not tail.isdigit():
        return n
    num = int(tail)
    if num >= 10:
        return "\\\\.\\" + up
    return n


def is_fr3d_header(line: str) -> bool:
    s = line.strip()
    if not s.startswith("FR3D,"):
        return False
    low = s.lower()
    return "t_act" in low or "material" in low


def is_medidor_header(line: str) -> bool:
    s = line.strip()
    return s.startswith("tramo,") and "diam_prom" in s


def is_fr3d_data(line: str) -> bool:
    s = line.strip()
    if not s or s.startswith("#"):
        return False
    parts = s.split(",")
    return len(parts) >= 3 and parts[0].strip() == "FR3D"


def is_medidor_data(line: str) -> bool:
    s = line.strip()
    if s.startswith("tramo,"):
        return False
    if not re.match(r"^\d+,", s):
        return False
    parts = s.split(",")
    return len(parts) >= 3 and parts[0].strip().isdigit()


def is_meta(line: str) -> bool:
    u = line.upper()
    return (
        "CSV,ST," in u
        or line.startswith("SER,")
        or line.startswith("RTC,")
        or line.startswith("===")
        or "SHOWTIME" in u
    )


def is_mk3_control_line(line: str) -> bool:
    s = line.strip().lower()
    return (
        s.startswith("echo:")
        or s.startswith("ok ")
        or s == "ok"
        or s.startswith("err ")
        or s.startswith("start")
    )


def is_addon_control_line(line: str) -> bool:
    s = line.strip()
    u = s.upper()
    if u.startswith("CAL,"):
        return True
    # MED_SUEL, MED_HALL, MED_*, etc.
    if u.startswith("MED"):
        return True
    if "CFG_" in u:
        return True
    return False


def serial_send_cmd(ser: serial.Serial, cmd: str) -> str:
    wire = (cmd.strip() + "\r\n").encode("ascii", errors="ignore")
    ser.write(wire)
    ser.flush()
    return cmd.strip()


class Mk3SerialLost(SystemExit):
    """USB/COM MK3 perdido; termina run_merge con mensaje legible para la UI."""


def is_mk3_serial_io_error(exc: BaseException) -> bool:
    return isinstance(exc, (PermissionError, serial.SerialException, OSError))


def mk3_serial_lost_from(exc: BaseException, *, action: str = "comunicar") -> Mk3SerialLost:
    return Mk3SerialLost(f"MK3 USB desconectado al {action}: {exc}")


# Debe coincidir con EXTRUDER_RPM_MAX / FR3D_SERIAL_RPM_MAX en MK3/Configuration.h
FR3D_EXTRUDER_RPM_MAX: float = 40.0


def mk3_cmd_set_rpm(value: float) -> str:
    v = max(0.0, min(FR3D_EXTRUDER_RPM_MAX, value))
    return f"R{v:.2f}"


def mk3_cmd_set_temp(value: int) -> str:
    v = max(0, min(250, int(value)))
    return f"T{v}"


def mk3_cmd_set_fan(value: int) -> str:
    v = max(0, min(100, int(value)))
    return f"F{v}"


def mk3_cmd_start(start_on: bool) -> str:
    return "START" if start_on else "STOP"


def mk3_cmd_pull_mode(auto_mode: bool) -> str:
    # PNAO = pull not auto (manual); sin letra "M" en el token (evita conflictos Marlin con PMAN).
    return "PAUT" if auto_mode else "PNAO"


def mk3_cmd_set_pull_rpm(rpm: float) -> str:
    """
    Comando compacto PR<rpm> — pulling manual en RPM (0–80, firmware FR3D).
    Requiere PNAO (modo manual) + hotend caliente; si no, el Mega responde ok PR nohot / err PR auto.
    """
    v = max(0.0, min(80.0, float(rpm)))
    return f"PR{v:.2f}"


def mk3_cmd_set_sw_mid(mm: float) -> str:
    """SWMID<mm> — setpoint de diámetro objetivo del sensor."""
    v = max(0.0, min(7.55, float(mm)))
    return f"SWMID{v:.3f}"


def mk3_cmd_set_sw_min(mm: float) -> str:
    """SWMIN<mm> — límite mínimo de runout del sensor."""
    v = max(0.0, min(7.55, float(mm)))
    return f"SWMIN{v:.3f}"


def mk3_cmd_set_sw_max(mm: float) -> str:
    """SWMAX<mm> — límite máximo de runout del sensor."""
    v = max(0.0, min(7.55, float(mm)))
    return f"SWMAX{v:.3f}"


def mk3_cmd_set_dh(enabled: bool) -> str:
    """DH1 — Hall A3 siempre activo (el flag enabled se ignora)."""
    del enabled
    return "DH1"


def mk3_cmd_diam_src(host: bool | int) -> str:
    """DIAMSRC0=A3, DIAMSRC1=USB HOST, DIAMSRC2=MANUAL."""
    if isinstance(host, bool):
        return "DIAMSRC1" if host else "DIAMSRC0"
    v = int(host)
    if v < 0:
        v = 0
    if v > 2:
        v = 2
    return f"DIAMSRC{v}"


def mk3_cmd_diam_set(mm: float) -> str:
    """DIAMSET<mm> — Ø HOST para LCD/predictor (stale 5 s en MK3)."""
    v = max(1.20, min(2.80, float(mm)))
    return f"DIAMSET{v:.3f}"


def mk3_cmd_set_dpoint(slot: str, adc: float) -> str:
    """D150..D200 (6 puntos) o D170/D175/D180 (firmware viejo)."""
    key = str(slot or "").strip().upper()
    if not key.startswith("D"):
        key = f"D{key}"
    v = max(0.0, min(1023.0, float(adc)))
    return f"{key}{v:.1f}"


def mk3_cmd_set_d170(adc: float) -> str:
    return mk3_cmd_set_dpoint("D170", adc)


def mk3_cmd_set_d175(adc: float) -> str:
    return mk3_cmd_set_dpoint("D175", adc)


def mk3_cmd_set_d180(adc: float) -> str:
    return mk3_cmd_set_dpoint("D180", adc)


def mk3_cmd_set_doff(offset_mm: float) -> str:
    v = max(-0.20, min(0.20, float(offset_mm)))
    return f"DOFF{v:.3f}"


def mk3_cmd_set_hall_pattern(pattern: str) -> str:
    """HPATA / HPATB — preset de patrones; invalida CALV y pone DOFF=0 en MK3."""
    p = str(pattern or "").strip().upper()
    if p not in ("A", "B"):
        raise ValueError("pattern must be A or B")
    return f"HPAT{p}"


def mk3_cmd_activate_hall_cal() -> str:
    """Reactiva CALV=1 si hay 3 ADC guardados (compacto CALV1)."""
    return "CALV1"


def mk3_cmd_capture_d170() -> str:
    return "C170"


def mk3_cmd_capture_d175() -> str:
    return "C175"


def mk3_cmd_capture_d180() -> str:
    return "C180"


def mk3_cmd_cooldown() -> str:
    return "COOL"


def mk3_cmd_query() -> str:
    return "QUERY"


def mk3_cmd_diamq() -> str:
    return "DIAMQ"


def mk3_cmd_lcdq() -> str:
    return "LCDQ"


def mk3_cmd_enc_plus() -> str:
    return "ENC+"


def mk3_cmd_enc_minus() -> str:
    return "ENC-"


def mk3_cmd_enc_click() -> str:
    return "ENCC"


def mk3_cmd_lcd_hw_enc(on: bool) -> str:
    return "LCDHWENC1" if on else "LCDHWENC0"


MK3_DIAMQ_INTERVAL_S = 1.5
MK3_DIAMQ_RESPONSE_TIMEOUT_S = 2.0
MK3_LCDQ_RESPONSE_TIMEOUT_S = 1.5


def mk3_diamq_shots_for_cycle(cycle_s: int) -> int:
    """Lecturas DIAMQ por ventana: 1 si ciclo <=5 s, 2 si mayor (intervalo 1.5 s)."""
    return 1 if int(cycle_s) <= 5 else 2


def mk3_cmd_stats_clear() -> str:
    """SCLEAR — placeholder comando FR3D para resetear estadísticas de metraje."""
    return "SCLEAR"


def mk3_cmd_set_length_target_m(meters: float) -> str:
    """
    LN<mm> — fija longitud objetivo para auto-stop (firmware usa fil_length_cutoff en mm).
    Rango útil de firmware: 1000..999000 mm (1..999 m).
    """
    mm = int(round(max(1.0, min(999.0, float(meters))) * 1000.0))
    return f"LN{mm}"


def mk3_cmd_save_settings() -> str:
    """MS — graba EEPROM por comando compacto FR3D."""
    return "MS"


def mk3_cmd_set_pred_enabled(enabled: bool) -> str:
    """PREDEN<0|1> — habilita/deshabilita predictor en MK3."""
    return "PREDEN1" if enabled else "PREDEN0"


def mk3_cmd_set_pred_mode(auto_mode: bool) -> str:
    """PREDMODE<0|1> — modo predictor MK3 (0=manual, 1=automático)."""
    return "PREDMODE1" if auto_mode else "PREDMODE0"


def mk3_cmd_set_pred_opt(optimize: bool) -> str:
    """PREDOPT<0|1> — optimizar P de sesión (RAM MK3, no EEPROM)."""
    return "PREDOPT1" if optimize else "PREDOPT0"


def mk3_cmd_set_pred_p_star(rpm: float) -> str:
    """PREDPSTAR<rpm> — objetivo de eficiencia P* (RAM MK3). 0 = sin objetivo."""
    v = float(rpm)
    if v <= 0.05:
        return "PREDPSTAR0"
    v = max(5.0, min(45.0, v))
    return f"PREDPSTAR{v:.2f}"


def parse_mk3_query_pred_p_star(
    snapshot: Optional[str],
) -> Tuple[Optional[float], Optional[int]]:
    """PREDPSTAR,<rpm>,<valid> desde QUERY."""
    rpm: Optional[float] = None
    valid: Optional[int] = None
    if not snapshot or not snapshot.strip():
        return rpm, valid
    for raw in snapshot.splitlines():
        s = raw.strip()
        if not s.lower().startswith("echo:"):
            continue
        rest = s[5:].lstrip()
        segs = [x.strip() for x in rest.split(",") if x.strip() != ""]
        if len(segs) < 2:
            continue
        if segs[0].upper() != "PREDPSTAR":
            continue
        try:
            rpm = float(segs[1].replace(",", "."))
        except ValueError:
            continue
        if len(segs) >= 3:
            try:
                valid = int(round(float(segs[2].replace(",", "."))))
            except ValueError:
                valid = 1
        else:
            valid = 1
        break
    return rpm, valid


def mk3_cmd_set_pred_cycle(seconds: int) -> str:
    """PREDCYCLE<n> — periodo de fusion predictor (MK3 fuerza 2 s)."""
    _ = seconds
    return "PREDCYCLE2"


def parse_mk3_query_rtf(snapshot: Optional[str]) -> Tuple[Optional[float], Optional[int], Optional[int]]:
    """
    Extrae R, T y F de la salida del comando QUERY del MK3 (líneas echo:R,..., echo:T,..., echo:F,...).
    """
    if not snapshot or not snapshot.strip():
        return None, None, None
    r_v: Optional[float] = None
    t_v: Optional[int] = None
    f_v: Optional[int] = None
    for raw in snapshot.splitlines():
        s = raw.strip()
        low = s.lower()
        if not low.startswith("echo:"):
            continue
        rest = s[5:].lstrip()
        segs = [x.strip() for x in rest.split(",") if x.strip() != ""]
        if not segs:
            continue
        key = segs[0].upper()
        if key == "R" and len(segs) >= 2:
            try:
                r_v = float(segs[1].replace(",", "."))
            except ValueError:
                pass
        elif key == "T" and len(segs) >= 2:
            try:
                t_v = int(round(float(segs[1].replace(",", "."))))
            except ValueError:
                pass
        elif key == "F" and len(segs) >= 2:
            try:
                f_v = int(round(float(segs[1].replace(",", "."))))
            except ValueError:
                pass
    return r_v, t_v, f_v


def parse_mk3_query_extruder_enabled(snapshot: Optional[str]) -> Optional[bool]:
    """
    Extrae ES (bit ES_ENABLE_SET) de QUERY:
      echo:ES,1, -> Start/Run
      echo:ES,0, -> Stop
    """
    if not snapshot or not snapshot.strip():
        return None
    for raw in snapshot.splitlines():
        s = raw.strip()
        low = s.lower()
        if not low.startswith("echo:"):
            continue
        rest = s[5:].lstrip()
        segs = [x.strip() for x in rest.split(",") if x.strip() != ""]
        if len(segs) < 2:
            continue
        if segs[0].upper() != "ES":
            continue
        v = segs[1].strip()
        if v in ("1", "ON", "on", "true", "TRUE"):
            return True
        if v in ("0", "OFF", "off", "false", "FALSE"):
            return False
    return None


def parse_mk3_query_pr_sw(
    snapshot: Optional[str],
) -> Tuple[
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
]:
    """
    Extrae PR (rpm pull), SW (medida actual), SWmin, SWmid, SWmax del snapshot QUERY
    (líneas echo:PR,..., echo:SW,..., etc.). SWmid en firmware = Ø objetivo (menú Filament / PID),
    no el punto medio entre SWmin y SWmax (ventana runout).
    """
    pr_v: Optional[float] = None
    sw_v: Optional[float] = None
    sw_min: Optional[float] = None
    sw_mid: Optional[float] = None
    sw_max: Optional[float] = None
    if not snapshot or not snapshot.strip():
        return pr_v, sw_v, sw_min, sw_mid, sw_max
    for raw in snapshot.splitlines():
        s = raw.strip()
        low = s.lower()
        if not low.startswith("echo:"):
            continue
        rest = s[5:].lstrip()
        segs = [x.strip() for x in rest.split(",") if x.strip() != ""]
        if len(segs) < 2:
            continue
        key = segs[0].upper()
        try:
            fv = float(segs[1].replace(",", "."))
        except ValueError:
            continue
        if key == "PR":
            pr_v = fv
        elif key == "SWMAX":
            sw_max = fv
        elif key == "SWMID":
            sw_mid = fv
        elif key == "SWMIN":
            sw_min = fv
        elif key == "SW":
            sw_v = fv
    return pr_v, sw_v, sw_min, sw_mid, sw_max


def parse_mk3_query_hall(
    snapshot: Optional[str],
) -> Tuple[
    Optional[int],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[str],
    Optional[int],
]:
    """
    Compat 8-tuple. Preferir parse_mk3_query_hall_ex (CALN/6 puntos).
    """
    ex = parse_mk3_query_hall_ex(snapshot)
    return (
        ex["dh"],
        ex["d170"],
        ex["d175"],
        ex["d180"],
        ex["doff"],
        ex["a3"],
        ex["pat"],
        ex["calv"],
    )


def parse_mk3_query_hall_ex(snapshot: Optional[str]) -> dict:
    """Hall QUERY: CALN=6 (nuevo) o PAT A/B + D170/D175/D180 (firmware viejo)."""
    out: dict = {
        "dh": None,
        "d150": None,
        "d160": None,
        "d170": None,
        "d175": None,
        "d180": None,
        "d190": None,
        "d200": None,
        "doff": None,
        "a3": None,
        "pat": None,
        "calv": None,
        "caln": None,
        "six_point": False,
    }
    if not snapshot or not snapshot.strip():
        return out
    for raw in snapshot.splitlines():
        s = raw.strip()
        low = s.lower()
        if not low.startswith("echo:"):
            continue
        rest = s[5:].lstrip()
        segs = [x.strip() for x in rest.split(",") if x.strip() != ""]
        if len(segs) < 2:
            continue
        key = segs[0].upper()
        if key == "DH":
            try:
                dh_i = int(round(float(segs[1].replace(",", "."))))
                if dh_i in (0, 1):
                    out["dh"] = dh_i
            except ValueError:
                pass
            continue
        if key == "CALN":
            try:
                cn = int(round(float(segs[1].replace(",", "."))))
                if cn in (3, 6):
                    out["caln"] = cn
            except ValueError:
                pass
            continue
        if key == "PAT":
            token = str(segs[1]).strip().upper()
            if token.startswith("6"):
                out["pat"] = "6"
                out["caln"] = 6
            elif token[:1] in ("A", "B"):
                out["pat"] = token[:1]
            continue
        if key == "CALV":
            try:
                cv = int(round(float(segs[1].replace(",", "."))))
                if cv in (0, 1):
                    out["calv"] = cv
            except ValueError:
                pass
            continue
        try:
            fv = float(segs[1].replace(",", "."))
        except ValueError:
            continue
        lk = key.lower()
        if lk in ("d150", "d160", "d170", "d175", "d180", "d190", "d200", "doff", "a3"):
            out[lk] = fv
    if out["caln"] == 6 or out["pat"] == "6":
        out["six_point"] = True
        out["caln"] = 6
        out["pat"] = "6"
    return out


def parse_mk3_query_diam_src(snapshot: Optional[str]) -> Optional[int]:
    """DIAMSRC 0=A3, 1=USB, 2=MANUAL. None si el QUERY no lo trae."""
    if not snapshot or not snapshot.strip():
        return None
    for raw in snapshot.splitlines():
        s = raw.strip()
        low = s.lower()
        if not low.startswith("echo:"):
            continue
        rest = s[5:].lstrip()
        segs = [x.strip() for x in rest.split(",") if x.strip() != ""]
        if len(segs) < 2 or segs[0].upper() != "DIAMSRC":
            continue
        try:
            src = int(round(float(segs[1].replace(",", "."))))
        except ValueError:
            continue
        if src in (0, 1, 2):
            return src
    return None


def parse_mk3_query_hostd(snapshot: Optional[str]) -> Optional[float]:
    """HOSTD mm (Ø USB/manual)."""
    if not snapshot or not snapshot.strip():
        return None
    for raw in snapshot.splitlines():
        s = raw.strip()
        low = s.lower()
        if not low.startswith("echo:"):
            continue
        rest = s[5:].lstrip()
        segs = [x.strip() for x in rest.split(",") if x.strip() != ""]
        if len(segs) < 2 or segs[0].upper() != "HOSTD":
            continue
        try:
            return float(segs[1].replace(",", "."))
        except ValueError:
            continue
    return None


def parse_mk3_query_dlcd(snapshot: Optional[str]) -> Optional[float]:
    """Extrae DLCD (campo D del LCD: mediana 2 ultimas muestras FIFO Hall, mm) del snapshot QUERY."""
    if not snapshot or not snapshot.strip():
        return None
    for raw in snapshot.splitlines():
        s = raw.strip()
        if not s.lower().startswith("echo:"):
            continue
        rest = s[5:].lstrip()
        segs = [x.strip() for x in rest.split(",") if x.strip() != ""]
        if len(segs) < 2:
            continue
        if segs[0].upper() != "DLCD":
            continue
        try:
            return float(segs[1].replace(",", "."))
        except ValueError:
            return None
    return None


def arm_mk3_diamq_after_query(state: AppState) -> None:
    """Programa DIAMQ espaciados 1.5 s tras completar QUERY post-CSV."""
    shots = mk3_diamq_shots_for_cycle(state.mk3_csv_cycle_s)
    state.mk3_diamq_shots_left = shots
    state.mk3_diamq_next_due_mono = time.monotonic() + MK3_DIAMQ_INTERVAL_S
    state.mk3_diamq_collecting = False
    state.mk3_diamq_lines = []
    state.mk3_diamq_sent_mono = None


def cancel_mk3_diamq_schedule(state: AppState) -> None:
    state.mk3_diamq_shots_left = 0
    state.mk3_diamq_next_due_mono = None
    state.mk3_diamq_collecting = False
    state.mk3_diamq_lines = []
    state.mk3_diamq_sent_mono = None


def finish_mk3_query_snapshot(state: AppState) -> None:
    state.mk3_query_collecting = False
    state.last_mk3_query_snapshot = "\n".join(state.mk3_query_lines)
    state.mk3_query_lines = []
    dlcd = parse_mk3_query_dlcd(state.last_mk3_query_snapshot)
    if dlcd is not None:
        state.last_mk3_dlcd_mm = dlcd
    q_pred = parse_mk3_query_pred_params(state.last_mk3_query_snapshot)
    if "PREDCYCLE" in q_pred:
        state.mk3_csv_cycle_s = 2
    arm_mk3_diamq_after_query(state)


def finish_mk3_diamq_response(state: AppState, snapshot: str, ok: bool) -> None:
    state.mk3_diamq_collecting = False
    state.mk3_diamq_sent_mono = None
    state.mk3_diamq_lines = []
    if ok:
        dlcd = parse_mk3_query_dlcd(snapshot)
        if dlcd is not None:
            state.last_mk3_dlcd_mm = dlcd
    state.mk3_diamq_shots_left = max(0, state.mk3_diamq_shots_left - 1)
    if state.mk3_diamq_shots_left > 0:
        state.mk3_diamq_next_due_mono = time.monotonic() + MK3_DIAMQ_INTERVAL_S
    else:
        state.mk3_diamq_next_due_mono = None


def mk3_diamq_scheduler_tick(
    state: AppState,
    ser_mk3: Optional[serial.Serial],
) -> None:
    if ser_mk3 is None or state.mk3_diamq_shots_left <= 0:
        return
    now = time.monotonic()
    if state.mk3_diamq_collecting and state.mk3_diamq_sent_mono is not None:
        if (now - state.mk3_diamq_sent_mono) >= MK3_DIAMQ_RESPONSE_TIMEOUT_S:
            print("[WARN] DIAMQ timeout; retrying schedule.", flush=True)
            finish_mk3_diamq_response(state, "", ok=False)
    if state.mk3_query_collecting or state.mk3_diamq_collecting:
        return
    if state.mk3_diamq_next_due_mono is None or now < state.mk3_diamq_next_due_mono:
        return
    state.mk3_diamq_collecting = True
    state.mk3_diamq_lines = []
    state.mk3_diamq_sent_mono = now
    try:
        serial_send_cmd(ser_mk3, mk3_cmd_diamq())
    except (PermissionError, serial.SerialException, OSError) as exc:
        cancel_mk3_diamq_schedule(state)
        raise mk3_serial_lost_from(exc, action="enviar DIAMQ") from exc
    state.last_command_sent = "mk3:DIAMQ"


def parse_mk3_query_pred_state(
    snapshot: Optional[str],
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Extrae PREDEN, PREDMODE y PREDOPT desde QUERY/PREDQ."""
    enabled: Optional[int] = None
    mode: Optional[int] = None
    opt: Optional[int] = None
    if not snapshot or not snapshot.strip():
        return enabled, mode, opt
    for raw in snapshot.splitlines():
        s = raw.strip()
        if not s.lower().startswith("echo:"):
            continue
        rest = s[5:].lstrip()
        segs = [x.strip() for x in rest.split(",") if x.strip() != ""]
        if len(segs) < 2:
            continue
        key = segs[0].upper()
        if key not in ("PREDEN", "PREDMODE", "PREDOPT"):
            continue
        try:
            v = int(round(float(segs[1].replace(",", "."))))
        except ValueError:
            continue
        if v not in (0, 1):
            continue
        if key == "PREDEN":
            enabled = v
        elif key == "PREDMODE":
            mode = v
        elif key == "PREDOPT":
            opt = v
    return enabled, mode, opt


_PRED_UI_TOKENS = frozenset(
    {
        "SIN A",
        "AR",
        "A",
        "AH",
        "AB",
        "AS",
        "AC",
        "AO",
        "AG",
        "AN",
        "AP",
        "AU",
        "AZ",
        "AE+",
        "AE-",
        "AT+",
        "AT-",
    }
)


def parse_mk3_query_pred_ui(snapshot: Optional[str]) -> Optional[str]:
    """Extrae token PREDUI (SIN A | AR | A | AH | AB | AE± | AT±) desde QUERY/PREDQ."""
    if not snapshot or not snapshot.strip():
        return None
    for raw in snapshot.splitlines():
        s = raw.strip()
        if not s.lower().startswith("echo:"):
            continue
        rest = s[5:].lstrip()
        # PREDUI,<token>,  — token puede ser "SIN A"
        if not rest.upper().startswith("PREDUI"):
            continue
        parts = rest.split(",", 2)
        if len(parts) < 2:
            continue
        tok = parts[1].strip()
        if not tok:
            continue
        upper = tok.upper()
        if upper == "SINA":
            upper = "SIN A"
        if upper in _PRED_UI_TOKENS:
            return "SIN A" if upper == "SIN A" else upper
    return None

def parse_mk3_query_pred_params(snapshot: Optional[str]) -> Dict[str, float]:
    """
    Extrae parámetros PRED* de QUERY/PREDQ en un diccionario normalizado.
    Los enteros también se exponen como float para simplificar consumo UI.
    """
    out: Dict[str, float] = {}
    if not snapshot or not snapshot.strip():
        return out
    for raw in snapshot.splitlines():
        s = raw.strip()
        if not s.lower().startswith("echo:"):
            continue
        rest = s[5:].lstrip()
        segs = [x.strip() for x in rest.split(",") if x.strip() != ""]
        if len(segs) < 2:
            continue
        key = segs[0].upper()
        if key not in (
            "PREDEN", "PREDMODE", "PREDOPT", "PREDPSTAR", "PREDW", "PREDTGT", "PREDDB", "PREDTM",
            "PREDTRNG", "PREDRRNG", "PREDDTRNG", "PREDDRRNG", "PREDKR", "PREDKT",
            "PREDMARG", "PREDSETTLE", "PREDHOLDM", "PREDHOLDT", "PREDCYCLE", "DIAMJDB", "DIAMJPM", "DIAMDEBUG",
        ):
            continue
        try:
            if key in ("PREDTRNG", "PREDRRNG", "PREDDTRNG", "PREDDRRNG", "PREDKR", "PREDKT", "PREDMARG"):
                if len(segs) >= 3:
                    out[f"{key}_A"] = float(segs[1].replace(",", "."))
                    out[f"{key}_B"] = float(segs[2].replace(",", "."))
            elif key == "PREDPSTAR":
                out["PREDPSTAR"] = float(segs[1].replace(",", "."))
                if len(segs) >= 3:
                    out["PREDPSTAR_V"] = float(segs[2].replace(",", "."))
                else:
                    out["PREDPSTAR_V"] = 1.0
            else:
                out[key] = float(segs[1].replace(",", "."))
        except ValueError:
            continue
    return out


def addon_cmd_servo(on: bool) -> str:
    return "SERVO ON" if on else "SERVO OFF"


# Tiempo para retorno arriba en firmware (SERVO_RETORNO_ARRIBA_MS ~500 ms).
ADDON_SERVO_OFF_SETTLE_S = 0.6


def wait_addon_servo_off_ack(ser: serial.Serial, timeout_s: float = 2.0) -> bool:
    """Espera CAL,SERVO,OK,OFF tras SERVO OFF (confirma que el STM32 procesó el comando)."""
    if timeout_s <= 0:
        return False
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            raw = ser.readline()
        except (serial.SerialException, OSError, ValueError):
            return False
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").strip().upper()
        if not line:
            continue
        if "SERVO,OK,OFF" in line:
            return True
    return False


def send_addon_servo_off_on_connect(ser: serial.Serial) -> str:
    """Al abrir sesión con el addon, apaga mezclador para posicionar servos arriba."""
    cmd = addon_cmd_servo(False)
    serial_send_cmd(ser, cmd)
    if wait_addon_servo_off_ack(ser, 2.0):
        print(f"[addon] {cmd} -> CAL,SERVO,OK,OFF")
    else:
        print(f"[addon] {cmd} (sin ACK del addon; revisar COM/baud)", file=sys.stderr)
    time.sleep(ADDON_SERVO_OFF_SETTLE_S)
    return cmd


def addon_cmd_cfg(name: str, value: str) -> str:
    return f"{name} {value}".strip()


def addon_cmd_query() -> str:
    return "CFG_QUERY"


def addon_cmd_med() -> str:
    return "MED"


def med_scheduler_tick(
    state: AppState,
    ser_addon: Optional[serial.Serial],
    med_interval_s: float,
    med_timeout_s: float,
) -> None:
    if not state.measuring_active or ser_addon is None:
        return

    now = time.monotonic()

    # Si quedo esperando respuesta demasiado tiempo, liberar y reintentar.
    if state.med_waiting_response and state.med_last_sent_ts is not None:
        if (now - state.med_last_sent_ts) >= med_timeout_s:
            state.med_waiting_response = False
            state.med_next_due_ts = now
            print("[WARN] MED timeout; retrying...")

    if state.med_waiting_response:
        return

    if state.med_next_due_ts is None:
        state.med_next_due_ts = now

    if now >= state.med_next_due_ts:
        cmd = addon_cmd_med()
        serial_send_cmd(ser_addon, cmd)
        state.last_command_sent = f"addon:{cmd}"
        state.med_last_sent_ts = now
        state.med_waiting_response = True


def serial_open_like_data_only(port: str, baud: int) -> serial.Serial:
    """Abre el puerto sin flow control por hardware; timeout corto para readline."""
    return serial.Serial(
        port,
        baud,
        timeout=0.1,
        dsrdtr=False,
        rtscts=False,
        xonxoff=False,
    )


def serial_open_quiet_preopen(port: str, baud: int) -> serial.Serial:
    """
    Variante para minimizar auto-reset:
    1) Configura DTR en bajo ANTES de abrir.
    2) Abre el COM con flow control desactivado.
    3) Reafirma DTR en bajo despues de abrir.
    """
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = 0.1
    ser.dsrdtr = False
    ser.rtscts = False
    ser.xonxoff = False
    try:
        ser.dtr = False
    except Exception:
        pass
    ser.open()
    serial_quiet_usb_autoreset(ser)
    return ser


def serial_quiet_usb_autoreset(ser: serial.Serial) -> None:
    """
    Tras abrir, pyserial (sobre todo en Windows) suele dejar DTR=1; en placas Arduino/Mega
    la línea DTR va al circuito de auto-reset USB → un pulso de reinicio. Bajar DTR
    reduce ese efecto (no garantiza 0 resets: el driver puede haber pulsado al abrir).
    Nota: no tocamos RTS para evitar cuelgues en algunos USB-UART.
    """
    try:
        ser.dtr = False
    except (AttributeError, serial.SerialException, OSError, ValueError):
        pass


def safe_reset_input_buffer(ser: serial.Serial, label: str) -> None:
    """
    En Windows algunos drivers USB-Serie fallan en PurgeComm al limpiar el buffer;
    no debe tumbar el script.
    """
    try:
        ser.reset_input_buffer()
    except (serial.SerialException, OSError, ValueError) as e:
        print(f"[WARN] Failed to clear input buffer ({label}): {e}")


def wait_fr3d_boot_quiet(
    ser: serial.Serial,
    timeout_ms: int,
    quiet_ms: int,
) -> bool:
    """
    Espera a que FR3D termine el ruido de arranque (lineas por serie) antes de ST.
    Devuelve True si detecta una ventana de silencio; False si vence timeout.

    Si no llega ninguna linea en ~1 s, el MK3 ya esta quieto (CH340 / sin reset
    DTR / usb_on_demand): no quemar el timeout completo.
    """
    if timeout_ms <= 0:
        return False
    quiet_s = max(0.0, quiet_ms / 1000.0)
    timeout_s = timeout_ms / 1000.0
    start = time.monotonic()
    deadline = start + timeout_s
    # Sin banner de boot: salir rapido (MK3 ya corriendo).
    no_boot_grace_s = min(1.0, timeout_s)
    last_rx: Optional[float] = None
    boot_lines = 0
    saw_any = False

    while time.monotonic() < deadline:
        try:
            raw = ser.readline()
        except (serial.SerialException, OSError, ValueError):
            return False

        now = time.monotonic()
        if raw:
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                saw_any = True
                last_rx = now
                if boot_lines < 6:
                    print(f"[BOOT fr3d] {line}")
                    boot_lines += 1
            continue

        if not saw_any and (now - start) >= no_boot_grace_s:
            return True

        if saw_any and last_rx is not None and (now - last_rx) >= quiet_s:
            return True

    return False


def wait_first_fr3d_activity(
    ser: serial.Serial,
    timeout_ms: int,
    *,
    probe_interval_ms: int = 1000,
) -> bool:
    """
    Confirma enlace FR3D antes de ST: sondea con QUERY y lee entre sondeos.

    El techo (timeout_ms) sigue cubriendo el reset por DTR al abrir el puerto:
    la placa puede tardar segundos en rearrancar y reenumerar el USB. Pero con
    usb_on_demand el MK3 no habla solo, asi que la espera pasiva agotaba el
    timeout entero incluso con la placa viva. Sondeando se sale al primer eco.
    """
    if timeout_ms <= 0:
        return False
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    interval_s = max(0.2, probe_interval_ms / 1000.0)
    probes = 0
    logged_port_wait = False

    while time.monotonic() < deadline:
        try:
            serial_send_cmd(ser, mk3_cmd_query())
            probes += 1
        except (serial.SerialException, OSError, ValueError) as exc:
            # Puerto aun reenumerando tras el reset: reintentar hasta el techo.
            if not logged_port_wait:
                print(f"[INFO] FR3D probe: port not ready yet ({exc}); retrying...")
                logged_port_wait = True
            time.sleep(min(interval_s, max(0.0, deadline - time.monotonic())))
            continue

        window_end = min(deadline, time.monotonic() + interval_s)
        while time.monotonic() < window_end:
            try:
                raw = ser.readline()
            except (serial.SerialException, OSError, ValueError):
                break
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            print(f"[FR3D ready] {line} (probe {probes})")
            return True

    print(f"[WARN] No FR3D reply after {probes} QUERY probes.")
    return False


def send_st(ser: serial.Serial) -> None:
    ser.write(b"ST\r\n")
    ser.flush()


def build_settime_now_cmd() -> str:
    now = datetime.now()
    return "SETTIME " + now.strftime("%Y-%m-%d %H:%M:%S")


def send_settime_medidor(ser: serial.Serial) -> str:
    cmd = build_settime_now_cmd()
    ser.write((cmd + "\r\n").encode("ascii", errors="ignore"))
    ser.flush()
    return cmd


def wait_first_addon_activity(ser: serial.Serial, timeout_s: float) -> bool:
    """
    Espera una primera línea del addon tras SETTIME/ST.
    Si el COM apunta a un dispositivo incorrecto, suele no llegar nada.
    """
    if timeout_s <= 0:
        return False
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            raw = ser.readline()
        except (serial.SerialException, OSError, ValueError):
            return False
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        print(f"[ADDON ready] {line}")
        return True
    return False


def parse_csv_row(line: str) -> List[str]:
    r = csv.reader(io.StringIO(line.strip()))
    try:
        return next(r)
    except StopIteration:
        return []


def normalize_fr3d_row_width(row_f: List[str], header_fr3d: Optional[str]) -> List[str]:
    """
    Alinea filas FR3D al ancho de la cabecera activa.
    Si DIAMDEBUG cambia ON↔OFF sin nueva cabecera en el CSV abierto, las filas cortas
    desplazan material/servos/tolva (p. ej. servos=«25.rojo»).
    """
    h = parse_csv_row(header_fr3d or DEFAULT_HEADER_FR3D)
    if not h or not row_f:
        return row_f
    n = len(h)
    nf = len(row_f)
    if nf == n:
        return row_f
    n_extra = len(_DIAMDEBUG_EXTRA_COLS)
    has_extra = all(c in h for c in _DIAMDEBUG_EXTRA_COLS)
    if has_extra and nf == n - n_extra:
        # Cabecera con DIAMDEBUG; fila sin bloque fifo (OFF): rellenar antes de servos.
        return row_f[:-1] + [""] * n_extra + [row_f[-1]]
    if has_extra and nf == n + n_extra:
        try:
            ji = h.index("corr_jump_hold")
        except ValueError:
            return row_f
        # Cabecera sin DIAMDEBUG; fila con bloque fifo (ON): quitar columnas sobrantes.
        return row_f[: ji + 1] + row_f[ji + 1 + n_extra :]
    return row_f


def parse_fr3d_csv_row(line: str, header_fr3d: Optional[str]) -> List[str]:
    return normalize_fr3d_row_width(parse_csv_row(line), header_fr3d)


def row_with_header_as_dict(row: List[str], header_line: Optional[str], default_header: str) -> Dict[str, str]:
    """Mapea una fila CSV a dict usando la cabecera real (o default)."""
    header = parse_csv_row(header_line or default_header)
    out: Dict[str, str] = {}
    for i, k in enumerate(header):
        out[k] = row[i] if i < len(row) else ""
    return out


def _merged_row_has_legacy_med_timestamp(row: Sequence[str]) -> bool:
    """CSV dual MK3+addon: col 2 = fecha_hora_pc_med. MK3-only: col 2 = «FR3D»."""
    if len(row) < 2:
        return False
    second = (row[1] or "").strip()
    if second == "FR3D" or second.startswith("FR3D,"):
        return False
    if "T" in second or re.match(r"\d{4}-\d{2}-\d{2}", second):
        return True
    return False


def merged_row_as_dict(
    row: Optional[List[str]],
    header_fr3d: Optional[str] = None,
    header_med: Optional[str] = None,
) -> Dict[str, str]:
    """Convierte fila CSV (MK3-only o legacy dual) en dict por nombre de columna."""
    if not row:
        return {}
    h_f = header_fr3d or DEFAULT_HEADER_FR3D
    h_m = header_med or DEFAULT_HEADER_MED
    out: Dict[str, str] = {}
    i = 0
    out[COL_RECV_FR3D] = row[i] if i < len(row) else ""
    i += 1
    legacy_dual = _merged_row_has_legacy_med_timestamp(row)
    if legacy_dual:
        out[COL_RECV_MED] = row[i] if i < len(row) else ""
        i += 1
    else:
        out[COL_RECV_MED] = ""

    fr3d_cols = parse_csv_row(h_f)
    med_cols = parse_csv_row(h_m)

    for key in fr3d_cols:
        v = row[i] if i < len(row) else ""
        out[key] = v
        out[f"mk3_{key}"] = v
        i += 1

    if legacy_dual:
        for key in med_cols:
            v = row[i] if i < len(row) else ""
            out[key] = v
            out[f"addon_{key}"] = v
            i += 1

    for key in MATERIAL_COLUMNS:
        out[key] = row[i] if i < len(row) else ""
        i += 1
    return out


def build_addon_only_merged_row(
    addon_csv_line: str,
    t_recv_med: datetime,
    *,
    header_fr3d: Optional[str],
    header_med: Optional[str],
    material_values: List[str],
) -> List[str]:
    """
    Fila con la misma forma que el merge MK3+addon, pero bloque MK3 vacío.
    Permite que la UI lea temp_C, hum_pct, suelo_pct, tolva_C, etc. desde el CSV del addon.
    """
    h_f = header_fr3d or DEFAULT_HEADER_FR3D
    h_m = header_med or DEFAULT_HEADER_MED
    n_fr3d = len(parse_csv_row(h_f))
    med_cols = parse_csv_row(h_m)
    n_med = len(med_cols)
    parts = parse_csv_row(addon_csv_line.strip())
    while len(parts) < n_med:
        parts.append("")
    parts = parts[:n_med]
    mv = list(material_values)[: len(MATERIAL_COLUMNS)]
    while len(mv) < len(MATERIAL_COLUMNS):
        mv.append("")
    return (
        ["", format_recv_ts(t_recv_med)]
        + [""] * n_fr3d
        + parts
        + mv
    )


def mk3_extruder_running_from_merged_dict(md: Dict[str, str]) -> bool:
    """
    True si la columna `status` del CSV fusionado indica extrusor en marcha.
    El firmware usa el texto «Extruder running»; el resto de estados = no Start.
    """
    st = (md.get("status") or "").strip().casefold()
    return st == "extruder running"


def extruder_csv_run_from_merged_row(
    row: List[str],
    header_fr3d: Optional[str],
    header_med: Optional[str],
) -> bool:
    md = merged_row_as_dict(row, header_fr3d, header_med)
    return mk3_extruder_running_from_merged_dict(md)


def load_material_catalog(path: str) -> List[Dict[str, str]]:
    """
    Filas del catálogo de recetas. Columnas habituales: material, type, origen_trit, …

    Para etiquetas en inglés en la UI (sin cambiar valores enviados al merge), añade columnas
    opcionales paralelas: type_en, origen_trit_en, col_tritur_en, granulado_en, sinfin_comp_en.
    Si una celda _en está vacía, se usa el texto en español de la columna base.
    """
    if not path or not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows: List[Dict[str, str]] = []
        for row in reader:
            if not row:
                continue
            rows.append({(k or "").strip(): (v or "").strip() for k, v in row.items()})
        return rows


@dataclass(frozen=True)
class ColorCatalog:
    """Catálogo de colorantes: valor interno (p. ej. negro) y etiqueta en inglés opcional."""

    values: Tuple[str, ...]
    label_en: Dict[str, str]

    @property
    def values_list(self) -> List[str]:
        return list(self.values)

    def options_for_lang(self, lang: str) -> Dict[str, str]:
        """NiceGUI select: clave = valor guardado en material_ctx; valor = texto mostrado."""
        if lang == "en":
            return {v: self.label_en.get(v, v) for v in self.values}
        return {v: v for v in self.values}


def load_color_catalog(path: str) -> ColorCatalog:
    """
    CSV con cabecera recomendada: color,color_en

    - Primera columna (color): valor canónico guardado en sesión / material_ctx (ej. negro).
    - Segunda columna opcional (color_en): texto mostrado si el idioma de la UI es inglés.
      Si falta o está vacía, se muestra el mismo valor que en la primera columna.

    Formato antiguo (una columna por fila, sin cabecera tipo DictReader): se sigue admitiendo
    leyendo filas sueltas; en ese caso la etiqueta EN coincide con el valor.
    """
    if not path or not os.path.isfile(path):
        return ColorCatalog((), {})
    with open(path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    if not raw.strip():
        return ColorCatalog((), {})

    def _norm_header(s: str) -> str:
        return (s or "").strip().lstrip("\ufeff").lower()

    fio = io.StringIO(raw)
    reader = csv.DictReader(fio)
    fieldnames = reader.fieldnames or []
    rows = list(reader)
    fn_map = {_norm_header(h): h for h in fieldnames if h}

    color_col = None
    for cand in ("color", "colors", "name", "nombre"):
        if cand in fn_map:
            color_col = fn_map[cand]
            break

    if color_col and rows:
        en_col = None
        for cand in ("color_en", "en", "english", "ingles", "inglés"):
            if cand in fn_map:
                en_col = fn_map[cand]
                break
        vals: List[str] = []
        label_en: Dict[str, str] = {}
        for row in rows:
            c = (row.get(color_col) or "").strip()
            if not c:
                continue
            if c.lower() in ("color", "colors", "name"):
                continue
            vals.append(c)
            if en_col:
                label_en[c] = (row.get(en_col) or "").strip() or c
            else:
                label_en[c] = c
        if vals:
            return ColorCatalog(tuple(vals), label_en)

    # Legado: una columna por fila (comportamiento previo).
    vals2: List[str] = []
    label_en2: Dict[str, str] = {}
    fio2 = io.StringIO(raw)
    for r in csv.reader(fio2):
        if not r:
            continue
        v = (r[0] or "").strip()
        if not v:
            continue
        if v.lower() in ("color", "colors", "name"):
            continue
        vals2.append(v)
        label_en2[v] = v
    return ColorCatalog(tuple(vals2), label_en2)


def build_material_ctx(
    material_rows: List[Dict[str, str]],
    colors: Sequence[str],
    material_id: Optional[str],
    pct_virgin: int,
    pct_dye: int,
    dye_color: Optional[str],
) -> Dict[str, str]:
    from material_id import resolve_material_row

    selected: Dict[str, str] = {}
    if material_rows:
        if material_id:
            row = resolve_material_row(material_rows, material_id.strip(), dye_color)
            if row:
                selected = row
        if not selected:
            selected = material_rows[0]

    color = (dye_color or "").strip()
    if not color:
        color = colors[0] if colors else ""
    elif colors and color not in colors:
        color = colors[0]

    now_batch = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "material": selected.get("material", ""),
        "type": selected.get("type", ""),
        "origen_trit": selected.get("origen_trit", ""),
        "col_tritur": selected.get("col_tritur", ""),
        "granulado": selected.get("granulado", ""),
        "sinfin_comp": selected.get("sinfin_comp", ""),
        "sinfin_comp_en": selected.get("sinfin_comp_en", ""),
        "batch": now_batch,
        "pct_pla_v": str(max(0, min(100, int(pct_virgin)))),
        "pct_col": str(max(0, min(20, int(pct_dye)))),
        "color_colorant": color,
    }


def sanitize_filename_component(value: str, fallback: str) -> str:
    s = (value or "").strip()
    if not s:
        s = fallback
    s = re.sub(r"[^\w\-.]+", "_", s, flags=re.UNICODE)
    s = s.strip("._")
    return s or fallback


def build_capture_path(out_dir: str, material_ctx: Dict[str, str], file_ts: str) -> str:
    material = sanitize_filename_component(material_ctx.get("material", ""), "material")
    lote = sanitize_filename_component(material_ctx.get("batch", ""), "lote")
    prefix_raw = str(material_ctx.get("capture_prefix", "") or "").strip()
    prefix = re.sub(r"[^\w\-.]+", "_", prefix_raw, flags=re.UNICODE)
    # Mantener separador visual del prefijo (ej. Spool_) en el nombre final.
    if prefix and not prefix.endswith("_"):
        prefix = f"{prefix}_"
    base = f"{prefix}{material}-{lote}.csv"
    path = os.path.join(out_dir, base)
    if not os.path.exists(path):
        return path
    # Colision: conservar base y agregar sello temporal.
    return os.path.join(out_dir, f"{prefix}{material}-{lote}_{file_ts}.csv")


def classify_serial_line(name: str, line: str) -> str:
    if is_meta(line):
        return "meta"
    if name == "fr3d":
        if is_mk3_control_line(line):
            return "control"
        if is_fr3d_header(line):
            return "header"
        if is_fr3d_data(line):
            return "data"
    else:
        if is_addon_control_line(line):
            return "control"
        if is_medidor_header(line):
            return "header"
        if is_medidor_data(line):
            return "data"
    return "noise"


def reader_thread(
    name: str,
    ser: serial.Serial,
    out_q: Queue,
    stop_evt: threading.Event,
) -> None:
    while not stop_evt.is_set():
        try:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            kind = classify_serial_line(name, line)
            if kind == "data":
                out_q.put((name, kind, line, datetime.now()))
            else:
                out_q.put((name, kind, line, None))
        except (serial.SerialException, OSError, PermissionError):
            break
        except Exception as e:
            print(f"[WARN] Lector {name}: {type(e).__name__}: {e}", file=sys.stderr)
            break


def ensure_writer(
    header_fr3d: Optional[str],
    header_med: Optional[str],
    writer: Optional[csv.writer],
    f_out: Optional[object],
    capture_path: str,
    material_ctx: Dict[str, str],
) -> tuple[Optional[csv.writer], Optional[object]]:
    if writer is not None:
        return writer, f_out
    h_f = header_fr3d or DEFAULT_HEADER_FR3D
    f = open(capture_path, "w", newline="", encoding="utf-8")
    w = csv.writer(f)
    w.writerow([COL_RECV_FR3D] + parse_csv_row(h_f) + MATERIAL_COLUMNS)
    f.flush()
    print(f"[INFO] Writing: {capture_path}")
    if material_ctx:
        print(f"[INFO] Active material: {material_ctx.get('material','')} batch={material_ctx.get('batch','')}")
    return w, f


def run_merge(
    port_fr3d: str,
    port_med: Optional[str],
    baud_fr3d: int,
    baud_med: int,
    addon_enabled: bool,
    out_dir: str,
    st_delay_ms: int,
    fr3d_boot_wait_ms: int,
    fr3d_ready_timeout_ms: int,
    fr3d_quiet_ms: int,
    fr3d_first_line_timeout_ms: int,
    serial_pulse_reset: bool,
    serial_open_passive: bool,
    skip_st: bool,
    capture_enabled: bool,
    measure_enabled: bool,
    med_interval_s: float,
    med_timeout_s: float,
    material_ctx: Dict[str, str],
    merge_runtime: Optional[MergeRuntime] = None,
    mk3_session_enabled: bool = True,
) -> None:
    if merge_runtime is None:
        merge_runtime = MergeRuntime(
            state=AppState(addon_enabled=addon_enabled),
            stop_event=threading.Event(),
        )
    state = merge_runtime.state
    # Sesión MK3-only: addon FR3D STM32 ya no se usa en esta versión de la UI.
    addon_enabled = False
    port_med = None
    state.addon_enabled = False
    state.capture_active = capture_enabled
    state.measuring_active = measure_enabled
    state.material_ctx = dict(material_ctx)
    state.addon_only_mode = (not mk3_session_enabled) and addon_enabled
    diameter_source = str(material_ctx.get("diameter_source", "addon") or "addon").strip().lower()
    addon_skip_sync = addon_enabled and (diameter_source == "mk3")
    addon_cache_by_mk3 = addon_enabled and (diameter_source == "mk3")
    if fr3d_boot_wait_ms < 0:
        fr3d_boot_wait_ms = 0
    if st_delay_ms < 0:
        st_delay_ms = 0
    if fr3d_ready_timeout_ms < 0:
        fr3d_ready_timeout_ms = 0
    if fr3d_quiet_ms < 0:
        fr3d_quiet_ms = 0
    if fr3d_first_line_timeout_ms < 0:
        fr3d_first_line_timeout_ms = 0
    out_dir = str(resolve_app_data_path(out_dir, Path.cwd()))
    os.makedirs(out_dir, exist_ok=True)
    # El CSV en disco solo con columna status = «Extruder running»; se cierra al cambiar de estado.

    pf = normalize_com_port(port_fr3d)
    pm = normalize_com_port(port_med or "")
    if addon_enabled and pf and pm and pf.upper() == pm.upper():
        print(
            "[ERROR] FR3D y medidor no pueden ser el mismo puerto. Cierra el monitor serie del IDE en uno de ellos.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    ser_f: Optional[serial.Serial] = None
    ser_m: Optional[serial.Serial] = None
    tf: Optional[threading.Thread] = None
    try:
        if not state.addon_only_mode:
            print(f"[INFO] Opening FR3D: {pf!r} @ {baud_fr3d} ...")
            if serial_open_passive or serial_pulse_reset:
                ser_f = serial_open_like_data_only(pf, baud_fr3d)
            else:
                ser_f = serial_open_quiet_preopen(pf, baud_fr3d)
            state.mk3_connected = True
            merge_runtime.ser_fr3d = ser_f
        else:
            print("[INFO] Addon-only session: MK3 serial not opened (solo addon FR3D).")
            state.mk3_connected = False
            merge_runtime.ser_fr3d = None

    except (serial.SerialException, OSError, ValueError) as e:
        tip = (
            "¿Otro programa usando ese COM? "
            "¿Baud 250000 soportado por el adaptador USB?"
        )
        msg = f"No se pudo abrir FR3D ({pf}): {e}. {tip}"
        print(f"[ERROR] {msg}", file=sys.stderr)
        raise SystemExit(msg) from e

    if addon_enabled:
        try:
            print(f"[INFO] Opening addon meter: {pm!r} @ {baud_med} ...")
            if serial_open_passive or serial_pulse_reset:
                ser_m = serial_open_like_data_only(pm, baud_med)
            else:
                ser_m = serial_open_quiet_preopen(pm, baud_med)
            state.addon_connected = True
            merge_runtime.ser_med = ser_m
        except (serial.SerialException, OSError, ValueError) as e:
            tip = "Is Arduino IDE Serial Monitor using that COM port?"
            msg = f"No se pudo abrir addon meter ({pm}): {e}. {tip}"
            print(f"[ERROR] {msg}", file=sys.stderr)
            if ser_f is not None:
                ser_f.close()
            raise SystemExit(msg) from e

    if serial_open_passive:
        print(
            "[INFO] Passive open: DTR/RTS untouched (open/read/write only)."
        )
    elif not serial_pulse_reset:
        print(
            "[INFO] DTR kept low after open (RTS untouched). "
            "If LCD/link fails, try --serial-pulse-reset."
        )
    if state.addon_only_mode:
        boot_addon_ms = min(int(fr3d_boot_wait_ms), 2000)
        print(
            f"[INFO] Addon-only: espera USB {boot_addon_ms} ms (sin puerto MK3)…"
        )
        time.sleep(boot_addon_ms / 1000.0)
        if not serial_open_passive and ser_m is not None:
            safe_reset_input_buffer(ser_m, "medidor")
    else:
        print(
            f"[INFO] Waiting {fr3d_boot_wait_ms} ms for FR3D boot (boot/EEPROM/CSV) before ST..."
        )
        time.sleep(fr3d_boot_wait_ms / 1000.0)
        # Modo pasivo: no leer en bucle ni PurgeComm; en Windows eso a veces cuelga el driver
        # aunque no toquemos DTR/RTS (no es lo mismo que "abrir sin pulso de líneas").
        if serial_open_passive:
            print(
                "[INFO] Passive mode: skipping FR3D idle wait and buffer cleanup "
                "(readline/PurgeComm can hang some COM ports)."
            )
        else:
            if ser_f is not None and fr3d_ready_timeout_ms > 0:
                print(
                    f"[INFO] Waiting for FR3D idle ({fr3d_quiet_ms} ms; timeout {fr3d_ready_timeout_ms} ms) before ST..."
                )
                ready = wait_fr3d_boot_quiet(ser_f, fr3d_ready_timeout_ms, fr3d_quiet_ms)
                if ready:
                    print("[INFO] FR3D is idle; sending ST.")
                else:
                    print("[WARN] Timeout waiting for FR3D idle; continuing with ST.")
            if ser_f is not None:
                safe_reset_input_buffer(ser_f, "FR3D")
            if addon_enabled and ser_m is not None:
                safe_reset_input_buffer(ser_m, "medidor")

    if addon_enabled and ser_m is not None:
        sent_servo = send_addon_servo_off_on_connect(ser_m)
        print(f"[addon] {sent_servo} (home al conectar)")

    if addon_enabled:
        print(f"[INFO] Baud FR3D={baud_fr3d}  addon={baud_med}")
    else:
        print(f"[INFO] Baud FR3D={baud_fr3d}  addon disabled")
    if skip_st:
        if addon_enabled:
            print("[INFO] Test mode: no ST. ST is not sent to FR3D or addon.")
        else:
            print("[INFO] Test mode: no ST. ST is not sent to FR3D.")
    else:
        if state.addon_only_mode:
            if addon_enabled and ser_m is not None and not addon_skip_sync:
                sent_settime = send_settime_medidor(ser_m)
                print(f"[addon] {sent_settime}")
            elif addon_enabled and ser_m is not None and addon_skip_sync:
                print("[INFO] diameter_source=mk3: skipping SETTIME/ST to addon (startup fast path).")
            if addon_enabled and ser_m is not None and not addon_skip_sync:
                print("[INFO] Addon-only: envío ST al medidor STM32.")
                send_st(ser_m)
                time.sleep(st_delay_ms / 1000.0)
                print("[INFO] Waiting for initial addon activity (timeout 4.0 s)...")
                addon_alive = wait_first_addon_activity(ser_m, 4.0)
                if not addon_alive:
                    msg = (
                        "Addon no response after SETTIME/ST (wrong COM, disconnected cable, "
                        "device off, or busy port)."
                    )
                    print(f"[ERROR] {msg}", file=sys.stderr)
                    raise SystemExit(msg)
            time.sleep(0.2)
        else:
            if addon_enabled and ser_m is not None and not addon_skip_sync:
                sent_settime = send_settime_medidor(ser_m)
                print(f"[addon] {sent_settime}")
            elif addon_enabled and ser_m is not None and addon_skip_sync:
                print("[INFO] diameter_source=mk3: skipping SETTIME/ST to addon (startup fast path).")
            print(
                f"[INFO] Confirming FR3D link before ST "
                f"(probe+wait timeout {fr3d_first_line_timeout_ms} ms)..."
            )
            fr3d_alive = wait_first_fr3d_activity(ser_f, fr3d_first_line_timeout_ms)
            if not fr3d_alive:
                print("[WARN] No FR3D reply in time; sending ST anyway.")
            if addon_enabled and ser_m is not None and not addon_skip_sync:
                print("[INFO] Near-simultaneous ST: addon -> short pause -> FR3D")
                send_st(ser_m)
                time.sleep(st_delay_ms / 1000.0)
            else:
                print("[INFO] ST FR3D (addon disabled mode)")
            assert ser_f is not None
            send_st(ser_f)
            if addon_enabled and ser_m is not None and not addon_skip_sync:
                print("[INFO] Waiting for initial addon activity (timeout 4.0 s)...")
                addon_alive = wait_first_addon_activity(ser_m, 4.0)
                if not addon_alive:
                    msg = (
                        "Addon no response after SETTIME/ST (wrong COM, disconnected cable, "
                        "device off, or busy port)."
                    )
                    print(f"[ERROR] {msg}", file=sys.stderr)
                    raise SystemExit(msg)
            time.sleep(0.2)
    state.sync_ok = True
    if ser_f is not None:
        print("[INFO] MK3 safe boot: sending STOP (extruder) and COOLDOWN...")
        try:
            serial_send_cmd(ser_f, mk3_cmd_start(False))
            time.sleep(1.0)
            serial_send_cmd(ser_f, mk3_cmd_cooldown())
            time.sleep(0.1)
        except Exception as e:
            print(f"[WARN] STOP/COOLDOWN commands during connect failed: {e}", file=sys.stderr)
        state.mk3_bootstrap_ready = True
        print("[INFO] MK3 ready for user commands (bootstrap complete).")
    else:
        print("[INFO] Addon-only session: omitiendo STOP/COOLDOWN del MK3.")
        state.mk3_bootstrap_ready = False

    if state.measuring_active and addon_enabled and ser_m is not None:
        state.med_next_due_ts = time.monotonic()
        print(
            f"[INFO] Measuring ON: MED every {med_interval_s:.1f}s from response (timeout {med_timeout_s:.1f}s)"
        )

    stop_evt = merge_runtime.stop_event
    q: Queue = Queue()
    tf = None
    if ser_f is not None:
        tf = threading.Thread(
            target=reader_thread, args=("fr3d", ser_f, q, stop_evt), daemon=True
        )
        tf.start()
    tm = None
    if addon_enabled and ser_m is not None:
        tm = threading.Thread(
            target=reader_thread, args=("medidor", ser_m, q, stop_evt), daemon=True
        )
        tm.start()

    header_fr3d: Optional[str] = None
    header_med: Optional[str] = None
    pending_f: Optional[Tuple[str, datetime]] = None
    pending_m: Optional[Tuple[str, datetime]] = None
    last_addon_csv_row: Optional[List[str]] = None
    last_addon_csv_ts: Optional[datetime] = None
    writer: Optional[csv.writer] = None
    f_out: Optional[object] = None
    capture_path_active = ""
    csv_recording = False
    merged_count = 0
    med_width = len(parse_csv_row(header_med or DEFAULT_HEADER_MED))

    def close_csv_capture(*, log_reason: Optional[str] = None) -> None:
        nonlocal writer, f_out, csv_recording, capture_path_active
        had_file = f_out is not None
        closed_path = capture_path_active if had_file else ""
        if f_out is not None:
            try:
                f_out.close()
            except Exception:
                pass
        writer = None
        f_out = None
        csv_recording = False
        state.current_capture_path = ""
        if closed_path:
            state.last_closed_capture_path = closed_path
        capture_path_active = ""
        if had_file and log_reason:
            print(f"[INFO] Capture CSV closed ({log_reason}).")

    def normalize_merged_diameter_source(row: List[str]) -> List[str]:
        """MK3-only: la fila ya trae diam_* y servos del bloque FR3D."""
        return row

    def write_csv_if_extruder_run(row: List[str]) -> None:
        """Solo escribe si «Capturar CSV» y status «Extruder running»; abre al entrar y cierra al salir."""
        nonlocal writer, f_out, capture_path_active, csv_recording
        if not state.capture_active:
            if csv_recording:
                close_csv_capture(log_reason="captura desactivada")
            return
        cap_prefix = str(state.material_ctx.get("capture_prefix", "") or "").strip().upper()
        cap_paused = str(state.material_ctx.get("capture_paused", "") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        cap_hold_on_stop = str(state.material_ctx.get("capture_hold_on_stop", "") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        # Bobinado en pausa (Pause/Continue): no anexar filas, pero mantener el mismo CSV abierto
        # para continuar en el mismo archivo al reanudar.
        if cap_prefix.startswith("SPOOL") and cap_paused:
            return
        if not extruder_csv_run_from_merged_row(row, header_fr3d, header_med):
            # Bobinador Pause/Continue: llega STOP pero se mantiene el mismo CSV para continuar.
            if cap_prefix.startswith("SPOOL") and cap_hold_on_stop:
                if csv_recording:
                    print("[INFO] capture hold active (spool pause): keep current CSV open.")
                return
            if csv_recording:
                close_csv_capture(log_reason="status distinto de Extruder running")
            return
        if not csv_recording:
            file_ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            capture_path_active = build_capture_path(out_dir, state.material_ctx, file_ts)
            csv_recording = True
            state.current_capture_path = capture_path_active
        writer, f_out = ensure_writer(
            header_fr3d,
            header_med,
            writer,
            f_out,
            capture_path_active,
            state.material_ctx,
        )
        row = normalize_merged_diameter_source(row)
        try:
            writer.writerow(row)
            f_out.flush()
        except (PermissionError, OSError, serial.SerialException) as exc:
            raise mk3_serial_lost_from(exc, action="escribir CSV") from exc

    def _mk3_doff_for_row() -> str:
        """DOFF activo al momento de fusionar (último QUERY hall válido)."""
        try:
            _on, _d170, _d175, _d180, doff_v, _a3, _pat, _calv = parse_mk3_query_hall(
                state.last_mk3_query_snapshot
            )
            if doff_v is None:
                return ""
            return f"{float(doff_v):.3f}"
        except (TypeError, ValueError, AttributeError):
            return ""

    def _material_values_for_row() -> List[str]:
        vals = [state.material_ctx.get(k, "") for k in MATERIAL_COLUMNS]
        try:
            i_doff = MATERIAL_COLUMNS.index("mk3_doff")
            vals[i_doff] = _mk3_doff_for_row()
        except ValueError:
            pass
        return vals

    def trigger_mk3_query_after_fusion() -> None:
        """Tras cada línea CSV fusionada, pedir QUERY (salvo modo USB on-demand del gateway)."""
        if ser_f is None:
            return
        # Fase 2 gateway: Flutter/POLL pide CSVQ+QUERY; no auto-QUERY tras cada fusión.
        uod = str(state.material_ctx.get("usb_on_demand", "") or "").strip().lower()
        if uod in ("1", "true", "yes", "on"):
            return
        cancel_mk3_diamq_schedule(state)
        if state.mk3_query_collecting:
            return
        state.mk3_query_collecting = True
        state.mk3_query_lines = []
        try:
            serial_send_cmd(ser_f, mk3_cmd_query())
        except (PermissionError, serial.SerialException, OSError) as exc:
            state.mk3_query_collecting = False
            raise mk3_serial_lost_from(exc, action="enviar QUERY") from exc

    # Cuando se desenchufa USB del MK3, reader_thread termina pero run_merge sigue vivo.
    def check_mk3_reader_alive() -> None:
        if tf is not None and not tf.is_alive():
            raise Mk3SerialLost("MK3 USB desconectado (sin datos serie).")

    # Cuando se desenchufa USB del Addon, reader_thread termina pero run_merge sigue vivo.
    # Hay que reabrir COM y reiniciar el lector aquí (no basta con abrir puerto desde la UI).
    _addon_reopen_last_mono = [0.0]
    _ADDON_REOPEN_MIN_INTERVAL_S = 5.0

    def reopen_addon_reader_if_dead() -> None:
        nonlocal ser_m, tm
        if not addon_enabled or stop_evt.is_set():
            return
        if tm is None:
            return
        if tm.is_alive():
            return
        now_m = time.monotonic()
        if now_m - _addon_reopen_last_mono[0] < _ADDON_REOPEN_MIN_INTERVAL_S:
            return
        _addon_reopen_last_mono[0] = now_m

        print(
            "[WARN] Medidor: lector serie terminó (USB desconectado?). Reintentando abrir COM…",
            flush=True,
        )
        try:
            if ser_m is not None:
                try:
                    ser_m.close()
                except Exception:
                    pass
            ser_m = None
            merge_runtime.ser_med = None
            state.addon_connected = False

            print(f"[INFO] Re-opening addon meter: {pm!r} @ {baud_med} …")
            if serial_open_passive or serial_pulse_reset:
                ser_m = serial_open_like_data_only(pm, baud_med)
            else:
                ser_m = serial_open_quiet_preopen(pm, baud_med)
            merge_runtime.ser_med = ser_m
            state.addon_connected = True

            if not serial_open_passive:
                safe_reset_input_buffer(ser_m, "medidor")

            if ser_m is not None:
                sent_servo = send_addon_servo_off_on_connect(ser_m)
                print(f"[addon reconnect] {sent_servo} (home al reconectar)")

            if not addon_skip_sync and ser_m is not None:
                sent_settime = send_settime_medidor(ser_m)
                print(f"[addon reconnect] {sent_settime}")
                if state.addon_only_mode:
                    print("[INFO] Addon-only reconnect: envío ST al medidor STM32.")
                    send_st(ser_m)
                    time.sleep(st_delay_ms / 1000.0)
                    if not wait_first_addon_activity(ser_m, 4.0):
                        print(
                            "[WARN] Addon reconnect: sin actividad inicial; se reintentará.",
                            file=sys.stderr,
                        )
                else:
                    print("[INFO] MK3 session: ST al addon tras reconexión (sin tocar FR3D).")
                    send_st(ser_m)
                    time.sleep(st_delay_ms / 1000.0)
                    if not wait_first_addon_activity(ser_m, 4.0):
                        print(
                            "[WARN] Addon reconnect: sin actividad tras ST; se reintentará.",
                            file=sys.stderr,
                        )

            tm = threading.Thread(
                target=reader_thread,
                args=("medidor", ser_m, q, stop_evt),
                daemon=True,
            )
            tm.start()
            print("[INFO] Lector medidor reiniciado.", flush=True)
        except Exception as e:
            print(f"[ERROR] Fallo reconexión addon: {e}", file=sys.stderr)
            ser_m = None
            merge_runtime.ser_med = None
            state.addon_connected = False

    try:
        while not stop_evt.is_set():
            check_mk3_reader_alive()
            reopen_addon_reader_if_dead()
            med_scheduler_tick(
                state=state,
                ser_addon=ser_m if addon_enabled else None,
                med_interval_s=med_interval_s,
                med_timeout_s=med_timeout_s,
            )
            try:
                mk3_diamq_scheduler_tick(state=state, ser_mk3=ser_f)
            except Mk3SerialLost:
                raise
            except (PermissionError, serial.SerialException, OSError) as exc:
                raise mk3_serial_lost_from(exc, action="programar DIAMQ") from exc
            try:
                src, kind, line, t_recv = q.get(timeout=0.2)
            except Empty:
                continue

            if kind == "header":
                if src == "fr3d":
                    new_cols = parse_csv_row(line)
                    old_cols = parse_csv_row(header_fr3d) if header_fr3d else []
                    if header_fr3d and new_cols != old_cols:
                        if csv_recording:
                            close_csv_capture(
                                log_reason="cabecera FR3D cambiada (p. ej. DIAMDEBUG ON/OFF)"
                            )
                    header_fr3d = line
                    state.header_fr3d = line
                else:
                    old_med = parse_csv_row(header_med) if header_med else []
                    new_med = parse_csv_row(line)
                    if header_med and new_med != old_med:
                        if csv_recording:
                            close_csv_capture(log_reason="cabecera medidor cambiada")
                    header_med = line
                    state.header_med = line
                print(f"[HEADER {src}] ok")
                continue

            if kind == "noise":
                continue

            if kind == "meta":
                print(f"[{src}] {line}")
                umeta = line.strip().upper()
                if (
                    src == "medidor"
                    and "CSV,ST," in umeta
                    and "ERROR" in umeta
                ):
                    print(
                        "[WARN] Addon meter rejected ST (CSV sync). "
                        "ERROR_MENU usually means menu/screen active or STM32 not ready. "
                        "Exit device menus, confirm it accepts serial commands, or reboot the addon; "
                        "SETTIME may be OK while ST sampling is still not aligned.",
                        file=sys.stderr,
                    )
                continue

            if kind == "control":
                if src == "fr3d":
                    state.last_mk3_ack = line
                    lu = line.strip().lower()
                    cap_prefix = str(state.material_ctx.get("capture_prefix", "") or "").strip().upper()
                    cap_hold_on_stop = str(state.material_ctx.get("capture_hold_on_stop", "") or "").strip().lower() in (
                        "1",
                        "true",
                        "yes",
                        "on",
                    )
                    # Si el MK3 reporta ES=0 o STOP por control, cerrar CSV aunque no llegue otra fila.
                    if (
                        csv_recording
                        and (
                            lu.startswith("echo:es,0")
                            or "ok stop" in lu
                            or "ok es" in lu
                        )
                    ):
                        # Pause/Continue bobinador: llega STOP/ES0 pero se conserva el mismo CSV abierto.
                        if not (cap_prefix.startswith("SPOOL") and cap_hold_on_stop):
                            close_csv_capture(log_reason="mk3 control stop/es0")
                        else:
                            print("[INFO] capture hold active (spool pause): ignore control STOP/ES0.")
                    if state.mk3_diamq_collecting:
                        if lu.startswith("echo:"):
                            state.mk3_diamq_lines.append(line)
                        if lu.startswith("echo:dlcd,"):
                            finish_mk3_diamq_response(
                                state,
                                "\n".join(state.mk3_diamq_lines),
                                ok=True,
                            )
                        elif "err diamq" in lu:
                            finish_mk3_diamq_response(state, "", ok=False)
                    if state.mk3_lcdq_collecting:
                        if lu.startswith("echo:"):
                            state.mk3_lcdq_lines.append(line)
                        snap_tmp = "\n".join(state.mk3_lcdq_lines)
                        if "err lcdq" in lu:
                            from python_gateway.gateway_lcd import finish_mk3_lcdq_response

                            finish_mk3_lcdq_response(state, "", ok=False)
                        elif lu.startswith("echo:lcd,"):
                            from python_gateway.gateway_lcd import (
                                finish_mk3_lcdq_response,
                                lcdq_rows_complete,
                            )

                            if lcdq_rows_complete(snap_tmp):
                                finish_mk3_lcdq_response(state, snap_tmp, ok=True)
                        sent_m = state.mk3_lcdq_sent_mono
                        if (
                            state.mk3_lcdq_collecting
                            and sent_m is not None
                            and (time.monotonic() - sent_m) >= MK3_LCDQ_RESPONSE_TIMEOUT_S
                        ):
                            from python_gateway.gateway_lcd import finish_mk3_lcdq_response

                            finish_mk3_lcdq_response(
                                state,
                                "\n".join(state.mk3_lcdq_lines),
                                ok=bool(state.mk3_lcdq_lines),
                            )
                    if state.mk3_query_collecting and lu.startswith("echo:"):
                        state.mk3_query_lines.append(line)
                        # Cerrar solo al final real (ES / g/m). El tope 40 truncaba
                        # PRED*/LCDREM/LCDHWENC del QUERY actual (~50+ líneas).
                        if (
                            "echo:g/m" in lu
                            or lu.startswith("echo:es,")
                            or len(state.mk3_query_lines) >= 96
                        ):
                            finish_mk3_query_snapshot(state)
                else:
                    state.last_addon_ack = line
                    lu = line.strip().upper()
                    st = line.strip()
                    if lu.startswith("CAL,QUERY,"):
                        state.last_addon_query_cal = st
                    if lu.startswith("MED"):
                        state.last_addon_med_line = st
                    if "CFG_" in lu or (lu.startswith("CAL,") and "CFG" in lu):
                        state.last_addon_cfg_snapshot = st
                    if state.measuring_active and lu.startswith("MED"):
                        # El intervalo de 2s empieza al recibir la respuesta (MED_SUEL,..., MED_*, ...).
                        state.med_waiting_response = False
                        state.med_next_due_ts = time.monotonic() + med_interval_s
                print(f"[ACK {src}] {line}")
                continue

            if kind != "data":
                continue

            if t_recv is None:
                continue

            if state.addon_only_mode and src == "medidor":
                row_m_in = parse_csv_row(line)
                state.last_addon_row = row_with_header_as_dict(
                    row_m_in, header_med, DEFAULT_HEADER_MED
                )
                last_addon_csv_row = row_m_in
                last_addon_csv_ts = t_recv
                # Misma forma que fila fusionada: la UI lee temp_C / hum_pct / suelo_pct / tolva_* desde aquí.
                row_ui = build_addon_only_merged_row(
                    line,
                    t_recv,
                    header_fr3d=header_fr3d,
                    header_med=header_med,
                    material_values=_material_values_for_row(),
                )
                merged_count += 1
                state.fusion_counter = merged_count
                state.last_merged_row = row_ui
                continue

            # Emparejar FIFO; t_recv = instante en que esta linea llego al PC por USB
            if src == "fr3d":
                if not addon_enabled:
                    row_f = parse_fr3d_csv_row(line, header_fr3d)
                    state.last_mk3_row = row_with_header_as_dict(
                        row_f, header_fr3d, DEFAULT_HEADER_FR3D
                    )
                    t_f = t_recv
                    mat_vals = _material_values_for_row()
                    row = [format_recv_ts(t_f)] + row_f + mat_vals
                    write_csv_if_extruder_run(row)
                    merged_count += 1
                    state.fusion_counter = merged_count
                    state.last_merged_row = row
                    trigger_mk3_query_after_fusion()
                    continue
                if addon_cache_by_mk3:
                    row_f = parse_fr3d_csv_row(line, header_fr3d)
                    state.last_mk3_row = row_with_header_as_dict(
                        row_f, header_fr3d, DEFAULT_HEADER_FR3D
                    )
                    t_f = t_recv
                    if last_addon_csv_row is not None:
                        row_m = last_addon_csv_row
                        t_m = last_addon_csv_ts if last_addon_csv_ts is not None else t_f
                    else:
                        row_m = [""] * med_width
                        t_m = t_f
                    mat_vals = _material_values_for_row()
                    row = [format_recv_ts(t_f), format_recv_ts(t_m)] + row_f + row_m + mat_vals
                    write_csv_if_extruder_run(row)
                    merged_count += 1
                    state.fusion_counter = merged_count
                    state.last_merged_row = row
                    trigger_mk3_query_after_fusion()
                    continue
                if pending_m is not None:
                    m_line, t_m = pending_m
                    row_f = parse_fr3d_csv_row(line, header_fr3d)
                    state.last_mk3_row = row_with_header_as_dict(
                        row_f, header_fr3d, DEFAULT_HEADER_FR3D
                    )
                    row_m = parse_csv_row(m_line)
                    t_f = t_recv
                    pending_m = None
                    mat_vals = _material_values_for_row()
                    row = [format_recv_ts(t_f), format_recv_ts(t_m)] + row_f + row_m + mat_vals
                    write_csv_if_extruder_run(row)
                    merged_count += 1
                    state.fusion_counter = merged_count
                    state.last_merged_row = row
                    print(f"[OK] merge #{merged_count}")
                    trigger_mk3_query_after_fusion()
                else:
                    pending_f = (line, t_recv)
            else:
                row_m_in = parse_csv_row(line)
                state.last_addon_row = row_with_header_as_dict(
                    row_m_in, header_med, DEFAULT_HEADER_MED
                )
                last_addon_csv_row = row_m_in
                last_addon_csv_ts = t_recv
                if addon_cache_by_mk3:
                    # Modo fuente MK3: el addon actualiza cache, pero no bloquea la fusión por FIFO.
                    continue
                if pending_f is not None:
                    f_line, t_f = pending_f
                    row_f = parse_fr3d_csv_row(f_line, header_fr3d)
                    row_m = row_m_in
                    t_m = t_recv
                    pending_f = None
                    mat_vals = _material_values_for_row()
                    row = [format_recv_ts(t_f), format_recv_ts(t_m)] + row_f + row_m + mat_vals
                    write_csv_if_extruder_run(row)
                    merged_count += 1
                    state.fusion_counter = merged_count
                    state.last_merged_row = row
                    print(f"[OK] merge #{merged_count}")
                    trigger_mk3_query_after_fusion()
                else:
                    pending_m = (line, t_recv)

    except KeyboardInterrupt:
        print("\n[INFO] End (Ctrl+C).")
    finally:
        stop_evt.set()
        merge_runtime.ser_fr3d = None
        merge_runtime.ser_med = None
        merge_runtime.finished = True
        if tf is not None:
            tf.join(timeout=1.5)
        if tm is not None:
            tm.join(timeout=1.5)
        close_csv_capture(log_reason="session end")
        if ser_f is not None:
            try:
                ser_f.close()
            except Exception:
                pass
        if ser_m is not None:
            try:
                ser_m.close()
            except Exception:
                pass
        print(f"[INFO] Written merges: {merged_count}")


def interactive_pick_ports(addon_enabled: bool) -> tuple[str, Optional[str]]:
    list_serial_ports()
    try:
        a = input("Puerto FR3D (ej. COM7): ").strip()
        b = None
        if addon_enabled:
            b = input("Puerto medidor STM32 (ej. COM5): ").strip()
    except EOFError:
        print("\n[ERROR] Input cancelled.", file=sys.stderr)
        raise SystemExit(1)
    if not a or (addon_enabled and not b):
        raise SystemExit("Faltan puertos.")
    if addon_enabled and b is not None and a.upper() == b.upper():
        print(
            "[ERROR] Debes elegir dos COM distintos. Cierra el monitor serie del IDE en los puertos que uses.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return a, b


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fusiona CSV de dos serie tras ST (sincronismo)."
    )
    ap.add_argument("--list", action="store_true", help="Listar puertos USB serie")
    ap.add_argument("--fr3d", help="COM del dispositivo FR3D")
    ap.add_argument("--medidor", help="COM del medidor Hall")
    ap.add_argument(
        "--addon-enabled",
        dest="addon_enabled",
        action="store_true",
        default=True,
        help="Habilita addon FR3D (default)",
    )
    ap.add_argument(
        "--no-addon",
        dest="addon_enabled",
        action="store_false",
        help="Modo sin addon FR3D: solo usa MK3S+",
    )
    ap.add_argument(
        "--fr3d-baud",
        type=int,
        default=250000,
        help="Baudios puerto FR3D (default 250000)",
    )
    ap.add_argument(
        "--medidor-baud",
        type=int,
        default=115200,
        help="Baudios medidor STM32 (default 115200)",
    )
    ap.add_argument(
        "--baud",
        type=int,
        default=None,
        help="Si se indica, fija el mismo baud en ambos puertos (anula --fr3d-baud y --medidor-baud)",
    )
    ap.add_argument("--out-dir", default="logs_merged", help="Salida (default logs_merged)")
    ap.add_argument(
        "--no-capture",
        action="store_true",
        help="No escribir archivo merged (solo monitor en consola)",
    )
    ap.add_argument(
        "--material-csv",
        default="material.csv",
        help="Archivo catalogo de materiales (default material.csv)",
    )
    ap.add_argument(
        "--colors-csv",
        default="colors.csv",
        help="Archivo catalogo de colores (default colors.csv)",
    )
    ap.add_argument(
        "--material-id",
        default=None,
        help="ID material a seleccionar del catalogo (columna material)",
    )
    ap.add_argument(
        "--pct-virgin",
        type=int,
        default=30,
        help="%% material virgen agregado (0-100, default 30)",
    )
    ap.add_argument(
        "--pct-dye",
        type=int,
        default=3,
        help="%% colorante agregado (0-20, default 3)",
    )
    ap.add_argument(
        "--dye-color",
        default="",
        help="Color de colorante (si vacio usa primer color del catalogo)",
    )
    ap.add_argument(
        "--st-delay-ms",
        type=int,
        default=50,
        help="Ms entre ST al primero y al segundo",
    )
    ap.add_argument(
        "--fr3d-boot-wait-ms",
        type=int,
        default=5000,
        help=(
            "Ms de espera tras abrir puertos antes de ST al FR3D "
            "(dejar terminar arranque; default 5000)"
        ),
    )
    ap.add_argument(
        "--fr3d-ready-timeout-ms",
        type=int,
        default=6000,
        help=(
            "Espera maxima para detectar silencio FR3D antes de ST "
            "(0 desactiva; default 6000)"
        ),
    )
    ap.add_argument(
        "--fr3d-quiet-ms",
        type=int,
        default=800,
        help="Ventana de silencio FR3D previa a ST (default 800)",
    )
    ap.add_argument(
        "--fr3d-first-line-timeout-ms",
        type=int,
        default=30000,
        help=(
            "Tiempo maximo para esperar la primera linea FR3D antes de sincronizar ST "
            "(default 30000)"
        ),
    )
    ap.add_argument(
        "--serial-pulse-reset",
        action="store_true",
        default=True,
        help=(
            "Modo clasico pyserial (default): no bajar DTR tras abrir; "
            "puede reiniciar el Mega al conectar el COM)"
        ),
    )
    ap.add_argument(
        "--serial-quiet-dtr",
        action="store_false",
        dest="serial_pulse_reset",
        help="Forzar DTR bajo tras abrir (puede evitar reset, pero en algunos casos cuelga)",
    )
    ap.add_argument(
        "--serial-open-passive",
        action="store_true",
        help=(
            "Abrir sin tocar DTR/RTS; ademas omite silencio FR3D y PurgeComm "
            "(evita cuelgues de driver en algunos COM)"
        ),
    )
    ap.add_argument(
        "--skip-st",
        action="store_true",
        help="Prueba diagnostica: no enviar ST (ni SETTIME) a ningun equipo",
    )
    ap.add_argument(
        "--measure",
        action="store_true",
        help="Habilita MED periodico (addon) para diagnostico",
    )
    ap.add_argument(
        "--med-interval-s",
        type=float,
        default=2.0,
        help="Intervalo MED en segundos, contado desde respuesta (default 2.0)",
    )
    ap.add_argument(
        "--med-timeout-s",
        type=float,
        default=3.0,
        help="Timeout de respuesta MED para reintento (default 3.0)",
    )
    args = ap.parse_args()

    if args.list:
        list_serial_ports()
        return

    if args.addon_enabled:
        if args.fr3d and args.medidor:
            fr3d, med = args.fr3d.strip(), args.medidor.strip()
            if fr3d.upper() == med.upper():
                print("[ERROR] --fr3d and --addon must be two different COM ports.", file=sys.stderr)
                sys.exit(2)
        elif not args.fr3d and not args.medidor:
            print("Ports (or use --fr3d and --addon):")
            fr3d, med = interactive_pick_ports(addon_enabled=True)
        else:
            ap.error("With addon enabled use both --fr3d and --medidor, or none.")
    else:
        if args.fr3d and not args.medidor:
            fr3d, med = args.fr3d.strip(), None
        elif not args.fr3d and not args.medidor:
            print("FR3D port (addon disabled mode):")
            fr3d, med = interactive_pick_ports(addon_enabled=False)
        else:
            ap.error("With --no-addon use only --fr3d (without --medidor), or none.")

    if args.baud is not None:
        bf, bm = args.baud, args.baud
    else:
        bf, bm = args.fr3d_baud, args.medidor_baud

    material_rows = load_material_catalog(args.material_csv)
    colors = load_color_catalog(args.colors_csv).values_list
    material_ctx = build_material_ctx(
        material_rows=material_rows,
        colors=colors,
        material_id=args.material_id,
        pct_virgin=args.pct_virgin,
        pct_dye=args.pct_dye,
        dye_color=args.dye_color,
    )

    try:
        run_merge(
            fr3d,
            med,
            bf,
            bm,
            args.addon_enabled,
            args.out_dir,
            args.st_delay_ms,
            args.fr3d_boot_wait_ms,
            args.fr3d_ready_timeout_ms,
            args.fr3d_quiet_ms,
            args.fr3d_first_line_timeout_ms,
            args.serial_pulse_reset,
            args.serial_open_passive,
            args.skip_st,
            not args.no_capture,
            args.measure,
            max(0.2, float(args.med_interval_s)),
            max(0.5, float(args.med_timeout_s)),
            material_ctx,
        )
    except SystemExit:
        raise
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
