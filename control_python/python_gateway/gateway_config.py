"""Persistencia minima en config_gateway.csv (solo gateway)."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict

from python_gateway.gateway_paths import app_dir

CONFIG_FILENAME = "config_gateway.csv"

DEFAULTS: Dict[str, str] = {
    "port_fr3d": "",
    "mk3_link_mode": "usb",
    "port_fr3d_usb": "",
    "port_fr3d_uart": "/dev/serial0",
    "baud_fr3d": "250000",
    "ui_line_label": "",
    "auto_connect": "true",
    "chk_passive": "false",
    "chk_skip_st": "false",
    "mk3_preheat_temp_c": "150",
    "startup_mode": "safe",
    "gateway_default_rpm": "15",
    "gateway_default_temp": "175",
    "gateway_default_fan": "50",
    "gateway_default_pull": "12",
    "pred_enabled": "true",
    "pred_mode": "automatic",
    "pred_profile": "balanced",
    "pred_target_diam_mm": "1.75",
    "pred_deadband_half_width_mm": "0.03",
    "pred_jump_debounce_mm": "0.1",
    "pred_jump_confirm_mm": "0.03",
    "pred_diam_debug": "true",
    "pred_temp_match_max_c": "2.0",
    "pred_require_es1": "true",
    "pred_clear_buffer_on_invalid": "false",
    "pred_r_min": "12.0",
    "pred_r_max": "30.0",
    "pred_t_min": "174",
    "pred_t_max": "185",
    "pred_delta_t_per_step": "1",
    "pred_delta_t_max": "1",
    "pred_delta_t_min": "0.2",
    "pred_k_span_r": "10.0",
    "pred_k_err_r": "15.0",
    "pred_k_span_t": "15.0",
    "pred_k_err_t": "55.0",
    "pred_delta_r_min": "0.05",
    "pred_delta_r_max_per_update": "0.6",
    "pred_cooldown_fusions": "0",
    "pred_r_switch_margin": "2.0",
    "pred_t_switch_margin": "2",
    "pred_t_settle_fusions": "15",
    "pred_hold_m": "0.50",
    "pred_hold_timeout_s": "60",
    "pred_csv_cycle_s": "2",
    "totem_enabled": "true",
    "totem_host": "caster.toteminsight.com",
    "totem_protocol": "https",
    "totem_namespace": "caster",
    "totem_id": "6a4696036daf98235e798779",
    "totem_enterprise": "6a4696026daf9832d7798777",
    "totem_custom_active": "false",
    "totem_id_custom": "",
    "totem_enterprise_custom": "",
    "winder_speed_rpm": "80",
    "winder_meters_target": "999",
    "winder_diam_min_mm": "1.6",
    "winder_diam_max_mm": "1.9",
    "pi_led_enabled": "true",
    "pi_led_sysfs": "ACT",
    "pi_led_slow_ms": "1000",
    "pi_led_fast_ms": "250",
    "firebase_enabled": "false",
    "firebase_database_url": "https://fr3d-3889a-default-rtdb.firebaseio.com",
    "firebase_web_api_key": "",
    "firebase_auth_email": "gateway@fr3d-addon.internal",
    "firebase_auth_password": "gateway",
    "firebase_service_account": "",
    "firebase_rtdb_cleanup_enabled": "true",
    "firebase_rtdb_cleanup_minutes": "10",
    "firebase_rtdb_cleanup_hours": "1",
    "firebase_command_drain_idle_minutes": "10",
    "gwid_wifi_offline_grace_seconds": "90",
    "bdwidth_enabled": "false",
    "bdwidth_port": "auto",
    "bdwidth_baud": "500000",
    "bdwidth_poll_hz": "5",
    "bdwidth_inject_mk3": "false",
    "bdwidth_mock_lo": "1.738",
    "bdwidth_mock_hi": "1.762",
    "bdwidth_auto_recover": "true",
    "bdwidth_auto_recover_streak": "25",
    "bdwidth_auto_recover_wait_s": "1.5",
    "bdwidth_auto_recover_cooldown_s": "90",
    "bdwidth_auto_recover_max_per_hour": "5",
    # Digital subtype (opcion B): bdwidth | artme
    "digital_backend": "bdwidth",
    "artme_enabled": "false",
    "artme_port": "auto",  # auto | mock
    "artme_i2c_bus": "1",
    "artme_i2c_addr": "72",  # 0x48
    "artme_channel": "0",
    "artme_poll_hz": "5",
    "artme_inject_mk3": "false",
    "artme_calv": "false",
    "artme_doff": "0.000",
    "artme_d150": "",
    "artme_d160": "",
    "artme_d170": "",
    "artme_d180": "",
    "artme_d190": "",
    "artme_d200": "",
}

KEY_ORDER: tuple[str, ...] = tuple(DEFAULTS.keys())


def default_config_path(base: Path | None = None) -> Path:
    root = base or app_dir()
    return root / CONFIG_FILENAME


def load_gateway_config(path: Path) -> Dict[str, str]:
    out = dict(DEFAULTS)
    if not path.is_file():
        return out
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = [
                (name or "").strip().lstrip("\ufeff")
                for name in (reader.fieldnames or [])
            ]
            if not fieldnames or "key" not in fieldnames:
                return out
            for row in reader:
                k = (row.get("key") or row.get("\ufeffkey") or "").strip()
                v = (row.get("value") or "").strip()
                if k:
                    out[k] = v
    except OSError:
        return dict(DEFAULTS)
    from python_gateway.gateway_serial import migrate_mk3_serial_config

    migrate_mk3_serial_config(out)
    return out


def save_gateway_config(path: Path, data: Dict[str, str]) -> None:
    merged = {**DEFAULTS, **data}
    tmp = path.with_name(path.name + ".tmp")
    keys = [k for k in KEY_ORDER if k in merged]
    for k in merged:
        if k not in keys:
            keys.append(k)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["key", "value"])
            w.writeheader()
            for k in keys:
                w.writerow({"key": k, "value": merged.get(k, "")})
        tmp.replace(path)
    except OSError:
        pass


def parse_bool(s: Any, default: bool) -> bool:
    if isinstance(s, bool):
        return s
    t = str(s or "").strip().lower()
    if t in ("1", "true", "yes", "si", "on"):
        return True
    if t in ("0", "false", "no", "off"):
        return False
    return default


def parse_int(s: Any, default: int) -> int:
    try:
        return int(float(str(s or "").strip().replace(",", ".")))
    except (TypeError, ValueError):
        return default


def parse_float(s: Any, default: float) -> float:
    try:
        return float(str(s or "").strip().replace(",", "."))
    except (TypeError, ValueError):
        return default
