"""Ejecutor de comandos Totem (gateway headless)."""
from __future__ import annotations

import socket
import sys
import time
from typing import List, Tuple

from control_and_merge_dual_serial_csv import (
    FR3D_EXTRUDER_RPM_MAX,
    mk3_cmd_activate_hall_cal,
    mk3_cmd_cooldown,
    mk3_cmd_pull_mode,
    mk3_cmd_set_dpoint,
    mk3_cmd_set_dh,
    mk3_cmd_set_doff,
    mk3_cmd_set_hall_pattern,
    mk3_cmd_set_fan,
    mk3_cmd_set_pull_rpm,
    mk3_cmd_set_rpm,
    mk3_cmd_set_temp,
    mk3_cmd_set_length_target_m,
    mk3_cmd_start,
    mk3_cmd_stats_clear,
    parse_mk3_query_diam_src,
    parse_mk3_query_dlcd,
    parse_mk3_query_hall_ex,
    parse_mk3_query_hostd,
)

from fr3d_totem_commands import normalize_mac_address, parse_totem_command
from fr3d_totem_winder import build_winder_status_lines

from python_gateway.gateway_config import parse_int, save_gateway_config
from python_gateway.gateway_serial import (
    MK3_LINK_UART,
    build_serial_list_lines,
    build_serial_status_lines,
    mk3_link_mode_label,
    set_mk3_link_mode,
    set_mk3_port_for_active_mode,
)
from python_gateway.gateway_csv_material_logs import (
    delete_material_csv,
    delete_material_csv_tree,
    list_material_csv_files,
    persist_staging_csv_to_material,
    read_material_csv_lines,
    start_material_csv_write,
    stop_material_csv_write_reply,
    write_material_note,
)
from python_gateway.gateway_materials import (
    color_delete_lines,
    color_list_lines,
    color_upsert_lines,
    ensure_pi_material_files,
    material_delete_lines,
    material_get_lines,
    material_list_lines,
    material_upsert_lines,
)
from python_gateway.gateway_identity import read_gateway_identity
from python_gateway.gateway_mk3 import (
    build_gwid_status_lines,
    force_push_gateway_id,
    send_mk3_immediate,
)
from python_gateway.gateway_pi_host import (
    get_wlan_mac_address,
    is_linux_gateway_host,
    is_pi_gateway_host,
    is_uno_q_gateway_host,
    pi_host_unavailable_lines,
    pi_reboot,
    pi_restart_gateway,
    pi_status,
    pi_update_check,
    pi_update_gateway,
    pi_update_status,
    pi_update_ui,
    pi_update_ui_check,
    pi_update_ui_status,
    run_so_command,
    wifi_add,
    wifi_available,
    wifi_connect,
    wifi_list_saved,
    wifi_remove,
    wifi_show,
)
from python_gateway.gateway_windows_update import (
    windows_update_check,
    windows_update_howto,
)
from python_gateway.gateway_version import read_gateway_version
from python_gateway.gateway_pred import (
    apply_pred_mode,
    apply_pred_opt,
    apply_pred_p_star,
    apply_pred_set,
    pred_params_response,
    pred_status_response,
)
from python_gateway.gateway_cloud_link import cloud_link_label, cloud_link_ok, firebase_enabled
from python_gateway.gateway_totem_identity import (
    active_totem_identity,
    totem_identity_mode_label,
)
from python_gateway.gateway_runtime import FR3D_PULL_RPM_MAX, FR3D_START_AFTER_PREP_DELAY_S, GENERIC_MATERIAL_ID, GatewayRuntime
from python_gateway.gateway_poll2 import build_poll2_response
from python_gateway.gateway_poll3 import handle_poll3
from python_gateway.gateway_status import build_status_lines
from python_gateway.gateway_winder import (
    flush_winder_snapshot,
    winder_continue,
    winder_pause,
    winder_set,
    winder_start,
    winder_stop,
)


def _bdwidth_send_diam_src(rt: GatewayRuntime, src: int) -> None:
    sess = getattr(rt, "session", None)
    if sess is None or not getattr(sess, "mk3_ready", lambda: False)():
        return
    from python_gateway.gateway_mk3_caps import mk3_supports_host_diam

    if not mk3_supports_host_diam(rt):
        return
    try:
        from control_and_merge_dual_serial_csv import mk3_cmd_diam_src
        from python_gateway.gateway_mk3 import send_mk3_immediate

        send_mk3_immediate(sess, mk3_cmd_diam_src(int(src)))
        rt.bdwidth_host_src_sent = True
        rt.bdwidth_last_src_mono = time.monotonic()
    except Exception as exc:
        print(f"[BDWidth] DIAMSRC: {exc}", flush=True)


def _bdwidth_force_host_diam(rt: GatewayRuntime, mm: float, *, src: int = 2) -> List[str]:
    """DIAMSRC + DIAMSET inmediato (no depender solo del tick 1 Hz)."""
    from python_gateway.gateway_bdwidth import clamp_mock_mm

    notes: List[str] = []
    mm = clamp_mock_mm(float(mm))
    sess = getattr(rt, "session", None)
    if sess is None or not getattr(sess, "mk3_ready", lambda: False)():
        notes.append("NOTE: MK3 no listo; Ø guardado en gateway (se inyecta al conectar).")
        return notes
    from python_gateway.gateway_mk3_caps import mk3_supports_host_diam

    if not mk3_supports_host_diam(rt):
        notes.append("NOTE: firmware MK3 sin DIAMSRC; no se envia DIAMSET.")
        return notes
    try:
        from control_and_merge_dual_serial_csv import mk3_cmd_diam_set, mk3_cmd_diam_src
        from python_gateway.gateway_mk3 import PRI_USER, send_mk3_immediate

        # DIAMSRC hace EEPROM si cambia la fuente: breve pausa antes de DIAMSET.
        send_mk3_immediate(sess, mk3_cmd_diam_src(int(src)), priority=PRI_USER)
        rt.bdwidth_host_src_sent = True
        rt.bdwidth_last_src_mono = time.monotonic()
        time.sleep(0.05)
        send_mk3_immediate(
            sess,
            mk3_cmd_diam_set(mm),
            priority=PRI_USER,
        )
        rt.bdwidth_last_inject_mono = time.monotonic()
        if int(src) == 2:
            rt.bdwidth_manual_mm = mm
        mon = getattr(rt, "bdwidth", None)
        if mon is not None and hasattr(mon, "note_inject"):
            mon.note_inject(mm)
        notes.append(f"NOTE: enviado DIAMSRC{int(src)} + DIAMSET{mm:.3f}")
    except Exception as exc:
        notes.append(f"NOTE: no se pudo inyectar Ø al MK3: {exc}")
        print(f"[BDWidth] force host diam: {exc}", flush=True)
        rt.bdwidth_host_src_sent = False
    return notes


def _mk3_query_snapshot(rt: GatewayRuntime, *, refresh: bool = False) -> str:
    sess = getattr(rt, "session", None)
    if sess is None or not sess.alive() or sess.merge_rt is None:
        return ""
    if refresh:
        try:
            from python_gateway.gateway_mk3_sync import sync_mk3_on_demand

            sync_mk3_on_demand(rt, want_csv=False, want_query=True, wait_s=0.85)
        except Exception as exc:
            print(f"[Gateway] DIAMSRC cap sync: {exc}", flush=True)
    return str(sess.merge_rt.state.last_mk3_query_snapshot or "")


def _mk3_supports_host_diam_src(rt: GatewayRuntime, *, refresh: bool = True) -> bool:
    """True si el QUERY trae DIAMSRC (firmware con USB/Manual)."""
    from python_gateway.gateway_mk3_caps import mk3_supports_host_diam

    if refresh:
        _mk3_query_snapshot(rt, refresh=True)
    return mk3_supports_host_diam(rt)


def _bdwidth_host_src_unsupported_msg() -> Tuple[List[str], str]:
    return [
        "[FR3D] BDWIDTH SOURCE",
        "MK3 firmware solo Hall A3 (sin DIAMSRC).",
        "Actualice el firmware MK3 para Digital USB / Manual.",
    ], "ERROR"


def _stop_digital_monitors(rt: GatewayRuntime) -> None:
    from python_gateway.gateway_artme import stop_artme_monitor
    from python_gateway.gateway_bdwidth import BdwidthMonitor

    mon = getattr(rt, "bdwidth", None)
    if isinstance(mon, BdwidthMonitor):
        mon.stop()
    stop_artme_monitor(rt)


def _digital_backend_apply(
    rt: GatewayRuntime,
    backend: str,
) -> Tuple[List[str], str]:
    """backend: bdwidth | artme. Persiste y, si Digital activo, reinicia el monitor."""
    from python_gateway.gateway_artme import (
        build_artme_status_lines,
        digital_backend_from_cfg,
    )
    from python_gateway.gateway_bdwidth import build_bdwidth_status_lines
    from python_gateway.gateway_config import parse_bool

    b = (backend or "").strip().lower()
    if b in ("artme", "ads", "ads1115", "optical"):
        b = "artme"
    elif b in ("bdwidth", "usb", "bd"):
        b = "bdwidth"
    else:
        return [
            "[FR3D] DIGITAL BACKEND",
            "uso: DIGITAL BACKEND BDWIDTH | ARTME",
            f"actual: {digital_backend_from_cfg(rt.cfg)}",
        ], "ERROR"

    rt.cfg["digital_backend"] = b
    save_gateway_config(rt.config_path, rt.cfg)

    digital_on = parse_bool(rt.cfg.get("bdwidth_inject_mk3"), False) or parse_bool(
        rt.cfg.get("artme_inject_mk3"), False
    )
    # Si ya está en modo Digital (host), reaplicar SOURCE USB con el nuevo backend.
    if digital_on and (
        parse_bool(rt.cfg.get("bdwidth_enabled"), False)
        or parse_bool(rt.cfg.get("artme_enabled"), False)
    ):
        lines, level = _bdwidth_apply_source(rt, "real")
        head = [f"[FR3D] DIGITAL BACKEND {b.upper()}", f"NOTE: Digital activo → reinicio {b}."]
        return head + lines, level

    lines = [
        f"[FR3D] DIGITAL BACKEND {b.upper()}",
        f"backend: {b}",
        "NOTE: se usara al elegir Fuente Digital (BDWIDTH SOURCE USB).",
    ]
    if b == "artme":
        lines.extend(build_artme_status_lines(getattr(rt, "artme", None)))
    else:
        lines.extend(build_bdwidth_status_lines(getattr(rt, "bdwidth", None)))
    return lines, "INFO"


def _bdwidth_apply_source(
    rt: GatewayRuntime,
    source: str,
    *,
    fixed_mm: float | None = None,
) -> Tuple[List[str], str]:
    """source: mock | real | off | manual. Persiste CSV y reinicia el monitor."""
    from python_gateway.gateway_artme import (
        build_artme_status_lines,
        is_artme_backend,
        start_artme_monitor,
        tick_artme_inject,
    )
    from python_gateway.gateway_bdwidth import (
        build_bdwidth_status_lines,
        clamp_mock_mm,
        mock_range_from_cfg,
        start_bdwidth_monitor,
        tick_bdwidth_inject,
    )

    src = (source or "").strip().lower()
    # OFF/A3 siempre OK en MK3 viejo. USB/Manual/Mock requieren DIAMSRC.
    if src in ("manual", "mock", "real") and not _mk3_supports_host_diam_src(rt):
        return _bdwidth_host_src_unsupported_msg()

    from python_gateway.gateway_config import parse_bool

    already_manual = (
        parse_bool(rt.cfg.get("bdwidth_enabled"), False)
        and parse_bool(rt.cfg.get("bdwidth_inject_mk3"), False)
        and (rt.cfg.get("bdwidth_port") or "").strip().lower() == "mock"
        and getattr(rt, "bdwidth", None) is not None
    )

    use_artme = False
    diam_src = 0
    mm_only = False
    if src == "manual":
        if fixed_mm is not None:
            mm = clamp_mock_mm(float(fixed_mm))
        else:
            lo, hi = mock_range_from_cfg(rt.cfg)
            mm = lo if abs(hi - lo) < 1e-4 else clamp_mock_mm(lo)
        rt.cfg["bdwidth_mock_lo"] = f"{mm:.3f}"
        rt.cfg["bdwidth_mock_hi"] = f"{mm:.3f}"
        rt.cfg["bdwidth_enabled"] = "true"
        rt.cfg["bdwidth_port"] = "mock"
        rt.cfg["bdwidth_inject_mk3"] = "true"
        rt.cfg["artme_enabled"] = "false"
        rt.cfg["artme_inject_mk3"] = "false"
        rt.bdwidth_manual_mm = mm
        title = "MANUAL"
        cfg_line = f"config: enabled=true port=mock inject_mk3=true D={mm:.3f}"
        note = "Ingreso manual. MK3 LCD Source = Manual. Si Auto ON y 70s sin nuevo Ø → PREDTGT (PREDUI=AR)."
        diam_src = 2
        src = "mock"
        mm_only = already_manual
    elif src == "mock":
        rt.cfg["bdwidth_enabled"] = "true"
        rt.cfg["bdwidth_port"] = "mock"
        rt.cfg["bdwidth_inject_mk3"] = "true"
        rt.cfg["artme_enabled"] = "false"
        rt.cfg["artme_inject_mk3"] = "false"
        lo, hi = mock_range_from_cfg(rt.cfg)
        title = "MOCK"
        cfg_line = f"config: enabled=true port=mock inject_mk3=true range={lo:.3f}..{hi:.3f}"
        note = "Simulador seno. MK3 LCD Source = Digital USB."
        diam_src = 1
    elif src == "real":
        use_artme = is_artme_backend(rt.cfg)
        if use_artme:
            rt.cfg["artme_enabled"] = "true"
            rt.cfg["artme_inject_mk3"] = "true"
            rt.cfg["bdwidth_enabled"] = "false"
            rt.cfg["bdwidth_inject_mk3"] = "false"
            title = "REAL ARTME"
            cfg_line = (
                f"config: artme_enabled=true port={rt.cfg.get('artme_port') or 'auto'} "
                f"inject_mk3=true backend=artme"
            )
            note = (
                "ARTME ADS1115 (Pi). Calibre 6 puntos (ARTME SET D150..D200) y CALV 1. "
                "MK3 LCD Source = Digital USB."
            )
        else:
            rt.cfg["bdwidth_enabled"] = "true"
            rt.cfg["bdwidth_port"] = "auto"
            rt.cfg["bdwidth_inject_mk3"] = "true"
            rt.cfg["artme_enabled"] = "false"
            rt.cfg["artme_inject_mk3"] = "false"
            title = "REAL"
            cfg_line = "config: enabled=true port=auto inject_mk3=true backend=bdwidth"
            note = "Sensor USB BDWidth. No abre el CH340 del MK3. Sin BDWidth extra: use MANUAL."
        diam_src = 1
    else:
        rt.cfg["bdwidth_enabled"] = "false"
        rt.cfg["bdwidth_inject_mk3"] = "false"
        rt.cfg["artme_enabled"] = "false"
        rt.cfg["artme_inject_mk3"] = "false"
        title = "OFF"
        cfg_line = "config: enabled=false inject_mk3=false"
        note = "Digital apagado. MK3 LCD Source = Analog A3."
        diam_src = 0
        src = "off"
    save_gateway_config(rt.config_path, rt.cfg)
    if mm_only:
        mon = getattr(rt, "bdwidth", None)
        if mon is not None and hasattr(mon, "note_inject"):
            mon.note_inject(float(rt.cfg.get("bdwidth_mock_lo") or 0.0))
        lines = [f"[FR3D] BDWIDTH {title}", cfg_line, f"NOTE: {note}"]
        lines.extend(build_bdwidth_status_lines(mon))
        return lines, "INFO"

    rt.bdwidth_host_src_sent = False
    rt.bdwidth_last_inject_mono = 0.0
    if diam_src != 2:
        rt.bdwidth_manual_mm = None
    _bdwidth_send_diam_src(rt, diam_src)
    _stop_digital_monitors(rt)

    if use_artme and src == "real":
        mon_a = start_artme_monitor(rt)
        if mon_a is not None:
            mon_a.wait_sample(0.8)
            try:
                tick_artme_inject(rt)
            except Exception:
                pass
        lines = [f"[FR3D] BDWIDTH {title}", cfg_line, f"NOTE: {note}"]
        lines.extend(build_artme_status_lines(mon_a))
        return lines, "INFO"

    mon = getattr(rt, "bdwidth", None)
    if mon is None:
        start_bdwidth_monitor(rt)
        mon = getattr(rt, "bdwidth", None)
    else:
        mon.restart()
    if mon is not None and src in ("mock", "real"):
        mon.wait_sample(0.8)
        if src == "mock":
            try:
                tick_bdwidth_inject(rt)
            except Exception:
                pass
    lines = [f"[FR3D] BDWIDTH {title}", cfg_line, f"NOTE: {note}"]
    lines.extend(build_bdwidth_status_lines(mon))
    return lines, "INFO"


def _hall_status_lines(rt: GatewayRuntime) -> Tuple[List[str], str]:
    sess = rt.session
    if sess is None or not sess.alive() or sess.merge_rt is None:
        return ["[FR3D] HALL", "Sesion MK3 no conectada."], "WARNING"
    try:
        from python_gateway.gateway_mk3_sync import sync_mk3_on_demand

        sync_mk3_on_demand(rt, want_csv=False, want_query=True, wait_s=0.85)
    except Exception as exc:
        print(f"[Gateway] HALL STATUS sync: {exc}", flush=True)
    snap = sess.merge_rt.state.last_mk3_query_snapshot
    if not snap or not str(snap).strip():
        return ["[FR3D] HALL", "Sin snapshot QUERY aun."], "WARNING"
    hall = parse_mk3_query_hall_ex(snap)
    dh, doff, a3, pat, calv = hall["dh"], hall["doff"], hall["a3"], hall["pat"], hall["calv"]
    six = bool(hall["six_point"])
    diam_src = parse_mk3_query_diam_src(snap)
    hostd = parse_mk3_query_hostd(snap)
    lines = ["[FR3D] HALL"]
    if diam_src == 2:
        lines.append("DIAMSRC: MANUAL")
        lines.append("HALLCAL: OFF")
        lines.append("NOTE: Ingreso manual (LCD D mm / Flutter). Hall A3 off.")
    elif diam_src == 1:
        lines.append("DIAMSRC: USB")
        lines.append("HALLCAL: OFF")
        lines.append("NOTE: ADC A3 y calibracion Hall deshabilitados (modo Digital USB).")
    elif diam_src == 0:
        lines.append("DIAMSRC: A3")
    else:
        lines.append("NOTE: Firmware Hall A3 only (sin DIAMSRC USB/Manual).")
    from python_gateway.gateway_mk3_caps import refresh_mk3_caps

    refresh_mk3_caps(rt)
    host_cap = 1 if getattr(rt, "mk3_cap_host_diam", False) else 0
    opt = 1 if getattr(rt, "mk3_cap_pred_opt", False) else 0
    pstar = 1 if getattr(rt, "mk3_cap_pred_pstar", False) else 0
    lines.append(f"CAPS: host_diam={host_cap} pred_opt={opt} pred_pstar={pstar}")
    if hostd is not None and diam_src in (1, 2):
        lines.append(f"HOSTD: {float(hostd):.3f}")
    if pat is not None:
        lines.append(f"PAT: {pat}")
        if six:
            lines.append("CALN: 6")
            lines.append("PATMM: 1.50,1.60,1.70,1.80,1.90,2.00")
        elif pat == "A":
            lines.append("PATMM: 1.50,1.70,2.00")
        elif pat == "B":
            lines.append("PATMM: 1.70,1.75,2.00")
    elif six:
        lines.append("CALN: 6")
        lines.append("PAT: 6")
        lines.append("PATMM: 1.50,1.60,1.70,1.80,1.90,2.00")
    if dh is not None:
        lines.append(f"DH: {int(dh)}")
        if int(dh) == 0:
            lines.append("NOTE: DH=0 legacy — FW nuevo fuerza DH=1 al boot.")
    if calv is not None:
        lines.append(f"CALV: {int(calv)}")
        if int(calv) == 0 and (diam_src is None or diam_src == 0):
            npts = 6 if six else 3
            lines.append(
                f"NOTE: Need Calibrate! ({npts} puntos) — predictor off hasta CALV=1."
            )
    if six:
        for key in ("d150", "d160", "d170", "d180", "d190", "d200"):
            val = hall.get(key)
            if val is not None:
                lines.append(f"{key.upper()}: {float(val):.1f}")
    else:
        if hall.get("d170") is not None:
            lines.append(f"D170: {float(hall['d170']):.1f}")
        if hall.get("d175") is not None:
            lines.append(f"D175: {float(hall['d175']):.1f}")
        if hall.get("d180") is not None:
            lines.append(f"D180: {float(hall['d180']):.1f}")
    if doff is not None:
        lines.append(f"DOFF: {float(doff):.3f}")
    if (diam_src is None or diam_src == 0) and a3 is not None:
        lines.append(f"A3: {float(a3):.1f}")
    if len(lines) == 1:
        lines.append("Sin datos Hall en el ultimo QUERY.")
    return lines, "INFO"


def _hall_set_and_save(rt: GatewayRuntime, cmd: str, label: str) -> Tuple[List[str], str]:
    sess = rt.session
    if sess is None or not sess.mk3_ready():
        return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"
    snap = ""
    if sess.merge_rt is not None:
        snap = str(sess.merge_rt.state.last_mk3_query_snapshot or "")
    if parse_mk3_query_diam_src(snap) in (1, 2):
        return [
            "[FR3D] HALL SET",
            "Modo USB/Manual: calibracion Hall A3 deshabilitada.",
        ], "ERROR"
    send_mk3_immediate(sess, cmd)
    send_mk3_immediate(sess, "MS")
    # Devolver estado Hall fresco para que Flutter actualice PAT/A3 sin un 2º round-trip.
    status_lines, _ = _hall_status_lines(rt)
    out = [f"[FR3D] {label} enviado y guardado (MS)."]
    out.extend(status_lines)
    return out, "INFO"


def _poll_response(rt: GatewayRuntime, csv_n: int) -> Tuple[List[str], str]:
    """STATUS + CSV opcional + WINDER STATUS en una sola respuesta."""
    lines: List[str] = ["[FR3D] POLL"]
    try:
        status_lines = build_status_lines(rt, include_wifi=False)
    except Exception:
        status_lines = ["[FR3D] STATUS", "Sin datos aun"]
    lines.extend(status_lines)
    if int(csv_n or 0) > 0:
        csv_lines, _ = rt.csv_fifo.build_response(int(csv_n))
        lines.extend(csv_lines)
    winder_lines, _ = build_winder_status_lines()
    lines.extend(winder_lines)
    return lines, "INFO"


def _whoareyou_lines(rt: GatewayRuntime) -> Tuple[List[str], str]:
    lines = ["[FR3D] WHOAREYOU"]
    identity = read_gateway_identity()
    if identity.valid:
        lines.append(f"MAC: {identity.mac or '—'}")
        lines.append(f"Serial: {identity.serial}")
        lines.append(f"Gateway key: {identity.gateway_key}")
    elif is_linux_gateway_host():
        mac = normalize_mac_address(get_wlan_mac_address())
        lines.append(f"MAC: {mac or '—'}")
    else:
        lines.append("MAC: — (identidad no disponible)")
    token = (rt.gateway_token or "").strip()
    if token:
        lines.append(f"Token: {token}")
    lines.append(f"Hostname: {socket.gethostname()}")
    if is_pi_gateway_host():
        host = "Raspberry Pi"
    elif is_uno_q_gateway_host():
        host = "Arduino UNO Q"
    elif sys.platform == "win32":
        host = "Windows"
    else:
        host = "otro"
    lines.append(f"Host: {host}")
    lines.append(f"Version: {read_gateway_version()}")
    cloud = cloud_link_label(rt)
    lines.append(f"Cloud: {cloud}")
    lines.append(f"{cloud}: {'CONECTADO' if cloud_link_ok(rt) else 'NO CONECTADO'}")
    if firebase_enabled(rt.cfg):
        from python_gateway.gateway_firebase_auth import resolve_firebase_auth_email

        email = resolve_firebase_auth_email(rt.cfg)
        lines.append("Auth: account (email/password)")
        lines.append(f"Auth email: {email or '—'}")
        lines.append("Service account JSON: no usado")
    else:
        # Totem Terminal/Enterprise solo si la nube activa es Totem (legado).
        lines.append(f"Modo: {totem_identity_mode_label(rt.cfg)}")
        tid, ent = active_totem_identity(rt.cfg)
        lines.append(f"Terminal ID: {tid or '—'}")
        lines.append(f"Enterprise: {ent or '—'}")
    return lines, "INFO"


def execute_totem_command(rt: GatewayRuntime, message: str) -> Tuple[List[str], str]:
    # Multilinea POLL3: detectar antes del parser de una linea.
    head = str(message or "").lstrip()
    if head.upper().startswith("POLL3"):
        return handle_poll3(rt, message)

    parsed = parse_totem_command(message)

    if parsed.kind == "poll3":
        return handle_poll3(rt, message)

    if parsed.kind == "whoareyou":
        return _whoareyou_lines(rt)

    if parsed.kind == "gwid_push":
        return force_push_gateway_id(rt)

    if parsed.kind == "gwid_status":
        return build_gwid_status_lines(rt)

    if parsed.kind in ("status", "echo", "help", "empty", "invalid", "unknown"):
        return [f"[FR3D] Comando delegado al worker Totem: {parsed.kind}"], "WARNING"

    if parsed.kind == "material_set_invalid":
        return ["[FR3D] MATERIAL SET: falta id (ej. MATERIAL SET 2)."], "ERROR"

    if parsed.kind == "material_set_active":
        mat_id = str(parsed.item_key or "").strip() or GENERIC_MATERIAL_ID
        rt.active_material_id = mat_id
        rt.sync_active_material_to_session()
        return [
            f"[FR3D] MATERIAL SET: material={mat_id} (extrusor/bobinador CSV).",
        ], "INFO"

    if parsed.kind == "windows_update_invalid":
        return [
            "[FR3D] WINDOWS UPDATE: usage CHECK [manifest_url] | HOWTO",
        ], "ERROR"
    if parsed.kind == "windows_update_check":
        if sys.platform != "win32":
            return [
                "[FR3D] WINDOWS UPDATE CHECK: Windows gateway only.",
            ], "WARNING"
        return windows_update_check(str(parsed.pred_value or ""))
    if parsed.kind == "windows_update_howto":
        if sys.platform != "win32":
            return [
                "[FR3D] WINDOWS UPDATE HOWTO: Windows gateway only.",
            ], "WARNING"
        return windows_update_howto()

    material_kinds = {
        "material_list",
        "material_get",
        "material_create",
        "material_update",
        "material_delete",
        "material_invalid",
        "color_list",
        "color_create",
        "color_update",
        "color_delete",
        "color_invalid",
    }
    if parsed.kind in material_kinds:
        base = rt.config_path.parent
        ensure_pi_material_files(base)
        if parsed.kind == "material_invalid":
            return [
                "[FR3D] MATERIAL: uso SET <id>, CREATE/UPDATE (3 lineas CSV), LIST, GET <id>, DELETE <id>",
            ], "ERROR"
        if parsed.kind == "color_invalid":
            return [
                "[FR3D] COLOR: uso CREATE/UPDATE <nombre>, LIST, DELETE <nombre>",
            ], "ERROR"
        if parsed.kind == "material_list":
            return material_list_lines(base)
        if parsed.kind == "material_get":
            return material_get_lines(str(parsed.item_key or ""), base)
        if parsed.kind == "material_delete":
            return material_delete_lines(str(parsed.item_key or ""), base)
        if parsed.kind == "material_create":
            return material_upsert_lines(
                str(parsed.csv_header or ""),
                str(parsed.csv_row or ""),
                action="create",
                base=base,
            )
        if parsed.kind == "material_update":
            return material_upsert_lines(
                str(parsed.csv_header or ""),
                str(parsed.csv_row or ""),
                action="update",
                base=base,
            )
        if parsed.kind == "color_list":
            return color_list_lines(base)
        if parsed.kind == "color_create":
            return color_upsert_lines(str(parsed.item_key or ""), action="create", base=base)
        if parsed.kind == "color_update":
            return color_upsert_lines(str(parsed.item_key or ""), action="update", base=base)
        if parsed.kind == "color_delete":
            return color_delete_lines(str(parsed.item_key or ""), base=base)

    pi_kinds = {
        "so_shell",
        "wifi_show",
        "wifi_list",
        "wifi_available",
        "wifi_add",
        "wifi_remove",
        "wifi_connect",
        "pi_reboot",
        "pi_restart_gateway",
        "pi_status",
        "pi_update_check",
        "pi_update_gateway",
        "pi_update_status",
        "pi_update_ui",
        "pi_update_ui_check",
        "pi_update_ui_status",
        "pi_update_invalid",
    }
    if parsed.kind in pi_kinds:
        if not is_linux_gateway_host():
            return pi_host_unavailable_lines(), "WARNING"
        if parsed.kind == "pi_status":
            return pi_status()
        if parsed.kind == "pi_update_invalid":
            return [
                "[FR3D] PI UPDATE: uso CHECK|GATEWAY|STATUS | UI CHECK|UI STATUS|UI [latest]",
            ], "ERROR"
        if parsed.kind == "pi_update_check":
            return pi_update_check(str(parsed.pred_value or ""))
        if parsed.kind == "pi_update_status":
            return pi_update_status()
        if parsed.kind == "pi_update_gateway":
            return pi_update_gateway(
                str(parsed.pred_param or "latest"),
                str(parsed.pred_value or ""),
            )
        if parsed.kind == "pi_update_ui_check":
            return pi_update_ui_check(str(parsed.pred_value or ""))
        if parsed.kind == "pi_update_ui_status":
            return pi_update_ui_status()
        if parsed.kind == "pi_update_ui":
            return pi_update_ui(
                str(parsed.pred_param or "latest"),
                str(parsed.pred_value or ""),
            )
        if parsed.kind == "pi_restart_gateway":
            return pi_restart_gateway()
        if parsed.kind == "pi_reboot":
            return pi_reboot()
        if parsed.kind == "so_shell":
            return run_so_command(str(parsed.pred_value or ""))
        if parsed.kind == "wifi_show":
            return wifi_show()
        if parsed.kind == "wifi_list":
            return wifi_list_saved()
        if parsed.kind == "wifi_available":
            return wifi_available()
        if parsed.kind == "wifi_add":
            return wifi_add(str(parsed.pred_param or ""), str(parsed.pred_value or ""))
        if parsed.kind == "wifi_remove":
            return wifi_remove(str(parsed.pred_value or ""))
        if parsed.kind == "wifi_connect":
            return wifi_connect(str(parsed.pred_value or ""))

    # Comandos de archivo: solo disco, no necesitan sesion MK3 abierta.
    if parsed.kind == "csv_file_invalid":
        return [
            "[FR3D] CSV FILE: uso LIST | WRITE | STOP | SAVE <id> [NOTE <txt>] | "
            "NOTE <id> [txt] | READ TAIL <n> <id> | READ <id> | "
            "DELETE <id> [<id>...] | DELETE PREFIX <id>",
        ], "ERROR"

    if parsed.kind in (
        "csv_file_list",
        "csv_file_write",
        "csv_file_stop",
        "csv_file_save",
        "csv_file_note",
        "csv_file_read",
        "csv_file_delete",
        "csv_file_delete_tree",
    ):
        base = rt.config_path.parent
        if parsed.kind == "csv_file_list":
            return list_material_csv_files(base)
        if parsed.kind == "csv_file_write":
            return start_material_csv_write(rt, base=base)
        if parsed.kind == "csv_file_stop":
            return stop_material_csv_write_reply(rt, base=base)
        if parsed.kind == "csv_file_save":
            return persist_staging_csv_to_material(
                str(parsed.item_key or ""),
                note=str(parsed.text_value or ""),
                base=base,
            )
        if parsed.kind == "csv_file_note":
            return write_material_note(
                str(parsed.item_key or ""),
                str(parsed.text_value or ""),
                base=base,
            )
        if parsed.kind == "csv_file_read":
            return read_material_csv_lines(
                str(parsed.item_key or ""),
                tail_lines=parsed.int_value,
                base=base,
            )
        if parsed.kind == "csv_file_delete_tree":
            return delete_material_csv_tree(str(parsed.item_key or ""), base=base)
        keys = list(parsed.item_keys) or [str(parsed.item_key or "")]
        return delete_material_csv(keys, base=base)

    if parsed.kind == "bdwidth_status":
        from python_gateway.gateway_bdwidth import build_bdwidth_status_lines

        return build_bdwidth_status_lines(getattr(rt, "bdwidth", None)), "INFO"

    if parsed.kind == "bdwidth_diam":
        from python_gateway.gateway_bdwidth import build_bdwidth_diam_lines

        return build_bdwidth_diam_lines(getattr(rt, "bdwidth", None)), "INFO"

    if parsed.kind == "bdwidth_diam_set":
        from python_gateway.gateway_bdwidth import (
            build_bdwidth_diam_lines,
            clamp_mock_mm,
        )

        if parsed.value is None:
            return ["[FR3D] BDWIDTH DIAM: uso DIAM <mm>"], "ERROR"
        mm = clamp_mock_mm(float(parsed.value))
        lines, level = _bdwidth_apply_source(rt, "manual", fixed_mm=mm)
        if level == "ERROR":
            return lines, level
        force_notes = _bdwidth_force_host_diam(rt, mm, src=2)
        hostd = None
        diam_src = None
        try:
            snap = _mk3_query_snapshot(rt, refresh=True)
            if snap.strip():
                hostd = parse_mk3_query_hostd(snap)
                diam_src = parse_mk3_query_diam_src(snap)
        except Exception:
            pass
        out = [
            f"[FR3D] BDWIDTH DIAM {mm:.3f}",
            f"NOTE: Ø fijo {mm:.3f} mm → MK3 Source Manual (DIAMSRC2).",
        ]
        out.extend(force_notes)
        if diam_src is not None:
            out.append(f"VERIFY DIAMSRC: {int(diam_src)}")
        if hostd is not None:
            out.append(f"VERIFY HOSTD: {float(hostd):.3f}")
            if abs(float(hostd) - mm) >= 0.0005:
                out.append(
                    "NOTE: HOSTD distinto del pedido — revise DIAMSRC=2 y firmware."
                )
                if level == "INFO":
                    level = "WARNING"
        out.extend(lines)
        out.extend(build_bdwidth_diam_lines(getattr(rt, "bdwidth", None)))
        return out, level

    if parsed.kind == "bdwidth_list":
        from python_gateway.gateway_bdwidth import list_bdwidth_port_lines

        return list_bdwidth_port_lines(), "INFO"

    if parsed.kind == "bdwidth_source":
        key = (parsed.item_key or "").strip().lower()
        if key == "a3":
            return _bdwidth_apply_source(rt, "off")
        if key == "usb":
            return _bdwidth_apply_source(rt, "real")
        if key == "manual":
            return _bdwidth_apply_source(rt, "manual")
        return ["[FR3D] BDWIDTH SOURCE: uso A3 | USB | MANUAL"], "ERROR"

    if parsed.kind == "bdwidth_mock":
        if parsed.value is not None and parsed.pred_value:
            from python_gateway.gateway_bdwidth import clamp_mock_range

            try:
                hi = float(str(parsed.pred_value).replace(",", "."))
            except ValueError:
                return ["[FR3D] BDWIDTH MOCK: uso MOCK <lo> <hi>"], "ERROR"
            lo, hi = clamp_mock_range(float(parsed.value), hi)
            rt.cfg["bdwidth_mock_lo"] = f"{lo:.3f}"
            rt.cfg["bdwidth_mock_hi"] = f"{hi:.3f}"
        else:
            # Sin rango: seno por defecto (sale del Ø fijo de DIAM <mm>).
            from python_gateway.gateway_config import DEFAULTS

            rt.cfg["bdwidth_mock_lo"] = DEFAULTS["bdwidth_mock_lo"]
            rt.cfg["bdwidth_mock_hi"] = DEFAULTS["bdwidth_mock_hi"]
        return _bdwidth_apply_source(rt, "mock")
    if parsed.kind == "bdwidth_real":
        return _bdwidth_apply_source(rt, "real")
    if parsed.kind == "bdwidth_off":
        return _bdwidth_apply_source(rt, "off")

    if parsed.kind in ("bdwidth_inject_on", "bdwidth_inject_off"):
        on = parsed.kind == "bdwidth_inject_on"
        rt.cfg["bdwidth_inject_mk3"] = "true" if on else "false"
        save_gateway_config(rt.config_path, rt.cfg)
        rt.bdwidth_host_src_sent = False
        return [
            f"[FR3D] BDWIDTH INJECT: {'ON' if on else 'OFF'} "
            "(DIAMSRC/DIAMSET; requiere firmware con DIAMSET).",
        ], "INFO"

    if parsed.kind == "digital_backend":
        key = (parsed.item_key or "").strip().lower()
        if not key:
            from python_gateway.gateway_artme import digital_backend_from_cfg

            b = digital_backend_from_cfg(rt.cfg)
            return [
                "[FR3D] DIGITAL BACKEND",
                f"backend: {b}",
                "uso: DIGITAL BACKEND BDWIDTH | ARTME",
            ], "INFO"
        return _digital_backend_apply(rt, key)

    if parsed.kind == "artme_status":
        from python_gateway.gateway_artme import build_artme_status_lines, start_artme_monitor

        if getattr(rt, "artme", None) is None:
            start_artme_monitor(rt)
        return build_artme_status_lines(getattr(rt, "artme", None)), "INFO"

    if parsed.kind == "artme_set_dpoint":
        from python_gateway.gateway_artme import (
            SLOT_KEYS,
            build_artme_status_lines,
            start_artme_monitor,
        )

        slot = (parsed.item_key or "").strip()
        if slot not in SLOT_KEYS or parsed.value is None:
            return ["[FR3D] ARTME SET: uso D150..D200 <raw>"], "ERROR"
        raw = int(round(float(parsed.value)))
        rt.cfg[f"artme_d{slot}"] = str(raw)
        rt.cfg["artme_calv"] = "false"
        save_gateway_config(rt.config_path, rt.cfg)
        if getattr(rt, "artme", None) is None:
            start_artme_monitor(rt)
        lines = [f"[FR3D] ARTME SET D{slot} {raw}", "NOTE: CALV reseteado; active con ARTME SET CALV 1."]
        lines.extend(build_artme_status_lines(getattr(rt, "artme", None)))
        return lines, "INFO"

    if parsed.kind == "artme_set_doff":
        from python_gateway.gateway_artme import (
            build_artme_status_lines,
            clamp_doff,
            start_artme_monitor,
        )

        if parsed.value is None:
            return ["[FR3D] ARTME SET DOFF: uso DOFF <mm>"], "ERROR"
        doff = clamp_doff(float(parsed.value))
        rt.cfg["artme_doff"] = f"{doff:.3f}"
        save_gateway_config(rt.config_path, rt.cfg)
        if getattr(rt, "artme", None) is None:
            start_artme_monitor(rt)
        lines = [f"[FR3D] ARTME SET DOFF {doff:.3f}"]
        lines.extend(build_artme_status_lines(getattr(rt, "artme", None)))
        return lines, "INFO"

    if parsed.kind == "artme_set_calv":
        from python_gateway.gateway_artme import (
            build_artme_status_lines,
            can_activate_cal,
            start_artme_monitor,
            tick_artme_inject,
        )

        if not can_activate_cal(rt.cfg):
            return [
                "[FR3D] ARTME SET CALV",
                "ERROR: capture 6 puntos monótonos (D150..D200) antes de CALV 1.",
            ], "ERROR"
        rt.cfg["artme_calv"] = "true"
        save_gateway_config(rt.config_path, rt.cfg)
        if getattr(rt, "artme", None) is None:
            start_artme_monitor(rt)
        try:
            tick_artme_inject(rt)
        except Exception:
            pass
        lines = ["[FR3D] ARTME SET CALV 1", "NOTE: curva activa; inyeccion DIAMSET si Digital ARTME."]
        lines.extend(build_artme_status_lines(getattr(rt, "artme", None)))
        return lines, "INFO"

    sess = rt.session
    assert sess is not None

    if parsed.kind == "poll2":
        return build_poll2_response(rt, int(parsed.int_value or 1))

    if parsed.kind == "poll":
        return _poll_response(rt, int(parsed.int_value or 0))

    if parsed.kind == "csv":
        return rt.csv_fifo.build_response(int(parsed.int_value or 1))

    if parsed.kind == "query":
        if not sess.alive() or sess.merge_rt is None:
            return ["[FR3D] QUERY", "Sesion MK3 no conectada."], "WARNING"
        # Refrescar: el snapshot cacheado podia estar truncado (tope viejo 40 lineas).
        snap = _mk3_query_snapshot(rt, refresh=True)
        if not snap or not str(snap).strip():
            return ["[FR3D] QUERY", "Aun no se recibio QUERY del MK3."], "WARNING"
        lines = ["[FR3D] QUERY", *str(snap).splitlines()]
        return lines, "INFO"

    if parsed.kind == "diamq":
        if not sess.alive() or sess.merge_rt is None:
            return ["[FR3D] DIAMQ", "Sesion MK3 no conectada."], "WARNING"
        st = sess.merge_rt.state
        dlcd = getattr(st, "last_mk3_dlcd_mm", None)
        if dlcd is None:
            dlcd = parse_mk3_query_dlcd(st.last_mk3_query_snapshot)
        if dlcd is None:
            return ["[FR3D] DIAMQ", "Sin lectura DLCD disponible."], "WARNING"
        return ["[FR3D] DIAMQ", f"DLCD: {float(dlcd):.3f} mm"], "INFO"

    if parsed.kind == "lcdq":
        if not sess.mk3_ready():
            return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"
        from python_gateway.gateway_lcd import request_lcdq_and_wait, touch_lcd_rem

        touch_lcd_rem(rt)
        return request_lcdq_and_wait(sess)

    if parsed.kind == "lcdrem":
        from python_gateway.gateway_lcd import request_lcdrem

        # int_value: 0=off, 1=on, None=keepalive
        enable = None
        if parsed.int_value is not None:
            enable = bool(int(parsed.int_value))
        if not sess.mk3_ready() and enable is not False:
            return ["[FR3D] LCDREM", "MK3 no listo."], "ERROR"
        return request_lcdrem(sess, rt, enable=enable, force_usb=(enable is True))

    if parsed.kind == "enc_plus":
        if not sess.mk3_ready():
            return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"
        from python_gateway.gateway_lcd import enc_with_lcd_snapshot

        n = int(parsed.int_value) if parsed.int_value is not None else 1
        return enc_with_lcd_snapshot(sess, "ENC+", rt, steps=n)

    if parsed.kind == "enc_minus":
        if not sess.mk3_ready():
            return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"
        from python_gateway.gateway_lcd import enc_with_lcd_snapshot

        n = int(parsed.int_value) if parsed.int_value is not None else 1
        return enc_with_lcd_snapshot(sess, "ENC-", rt, steps=n)

    if parsed.kind == "enc_click":
        if not sess.mk3_ready():
            return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"
        from python_gateway.gateway_lcd import enc_with_lcd_snapshot

        return enc_with_lcd_snapshot(sess, "ENCC", rt, steps=1)

    if parsed.kind == "lcdhwenc" and parsed.int_value is not None:
        if not sess.mk3_ready():
            return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"
        v = 1 if int(parsed.int_value) else 0
        send_mk3_immediate(sess, f"LCDHWENC{v}")
        return [f"[FR3D] LCDHWENC{v} enviado (EEPROM MK3)."], "INFO"

    if parsed.kind == "hall_status":
        return _hall_status_lines(rt)

    if parsed.kind == "hall_set_dpoint" and parsed.item_key and parsed.value is not None:
        key = str(parsed.item_key).upper()
        return _hall_set_and_save(
            rt,
            mk3_cmd_set_dpoint(key, float(parsed.value)),
            f"HALL {key}={float(parsed.value):.1f}",
        )

    if parsed.kind == "hall_set_d170" and parsed.value is not None:
        return _hall_set_and_save(
            rt,
            mk3_cmd_set_dpoint("D170", float(parsed.value)),
            f"HALL D170={float(parsed.value):.1f}",
        )

    if parsed.kind == "hall_set_d175" and parsed.value is not None:
        return _hall_set_and_save(
            rt,
            mk3_cmd_set_dpoint("D175", float(parsed.value)),
            f"HALL D175={float(parsed.value):.1f}",
        )

    if parsed.kind == "hall_set_d180" and parsed.value is not None:
        return _hall_set_and_save(
            rt,
            mk3_cmd_set_dpoint("D180", float(parsed.value)),
            f"HALL D180={float(parsed.value):.1f}",
        )

    if parsed.kind == "hall_set_doff" and parsed.value is not None:
        return _hall_set_and_save(
            rt,
            mk3_cmd_set_doff(float(parsed.value)),
            f"HALL DOFF={float(parsed.value):.3f}",
        )

    if parsed.kind == "hall_set_pattern" and parsed.item_key:
        pat = str(parsed.item_key).upper()
        try:
            cmd = mk3_cmd_set_hall_pattern(pat)
        except ValueError:
            return ["[FR3D] HALL SET PATTERN: use A or B"], "ERROR"
        return _hall_set_and_save(
            rt,
            cmd,
            f"HALL PATTERN={pat} (CALV invalidado, DOFF=0)",
        )

    if parsed.kind == "hall_set_calv":
        return _hall_set_and_save(
            rt,
            mk3_cmd_activate_hall_cal(),
            "HALL SET CALV 1 (reactivar calibracion guardada)",
        )

    if parsed.kind == "hall_set_dh" and parsed.value is not None:
        on = int(round(float(parsed.value))) == 1
        return _hall_set_and_save(
            rt,
            mk3_cmd_set_dh(on),
            f"HALL SET DH={1 if on else 0}",
        )

    if parsed.kind == "pred_status":
        return pred_status_response()

    if parsed.kind == "pred_params":
        return pred_params_response()

    if parsed.kind == "pred_set":
        if not parsed.pred_param or parsed.pred_value is None:
            return ["[FR3D] PRED SET: uso PRED SET <param> <valor>"], "ERROR"
        return apply_pred_set(rt, str(parsed.pred_param), str(parsed.pred_value))

    if parsed.kind == "pred_auto":
        return apply_pred_mode(rt, True)

    if parsed.kind == "pred_manual":
        return apply_pred_mode(rt, False)

    if parsed.kind == "pred_opt_on":
        return apply_pred_opt(rt, True)

    if parsed.kind == "pred_opt_off":
        return apply_pred_opt(rt, False)

    if parsed.kind == "pred_p_star":
        if parsed.value is None:
            return ["[FR3D] PRED PSTAR: uso PRED PSTAR <rpm>"], "ERROR"
        return apply_pred_p_star(rt, float(parsed.value))

    if parsed.kind == "pulling_auto":
        return _apply_pulling_mode(rt, True)

    if parsed.kind == "pulling_manual":
        return _apply_pulling_mode(rt, False)

    if parsed.kind == "winder_start":
        return winder_start(rt)

    if parsed.kind == "winder_stop":
        return winder_stop(rt)

    if parsed.kind == "winder_pause":
        return winder_pause(rt)

    if parsed.kind == "winder_continue":
        return winder_continue(rt)

    if parsed.kind == "winder_status":
        return build_winder_status_lines()

    if parsed.kind == "winder_set":
        if not parsed.winder_param or parsed.winder_value is None:
            return ["[FR3D] WINDER SET: uso WINDER SET <param> <valor>"], "ERROR"
        return winder_set(rt, str(parsed.winder_param), str(parsed.winder_value))

    if parsed.kind == "conectar":
        # Siempre anexar STATUS real: Flutter marca mk3Ready buscando
        # "Sesion MK3: CONECTADA | bootstrap: LISTO". Sin eso, un CONECTAR
        # con "ya activa" reafirma desconectado y rearma el reintento de 60 s.
        if sess.alive():
            lines = ["[FR3D] CONECTAR", "Sesion MK3 ya activa."]
            try:
                lines.extend(build_status_lines(rt, include_wifi=False))
            except Exception:
                pass
            entry = "INFO" if sess.mk3_ready() else "WARNING"
            return lines, entry
        ok, msg = sess.connect()
        rt.sync_active_material_to_session()
        if not ok:
            return [f"[FR3D] {msg}"], "ERROR"
        # Espera corta: este bloque corre con el lock de ejecucion tomado y el
        # timeout de Flutter es 20 s. Si el MK3 se resetea al abrir el puerto
        # tarda ~10 s, y ahi conviene responder PENDIENTE: el POLL3 siguiente
        # (15 s) reporta LISTO sin bloquear el canal.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if sess.mk3_ready():
                break
            dead = sess.finalize_if_dead()
            if dead:
                return [f"[FR3D] {msg}", f"Fallo: {dead}"], "ERROR"
            time.sleep(0.15)
        lines = [f"[FR3D] {msg}"]
        try:
            lines.extend(build_status_lines(rt, include_wifi=False))
        except Exception:
            pass
        entry = "INFO" if sess.mk3_ready() else "WARNING"
        return lines, entry

    if parsed.kind == "desconectar":
        rt.stop_csv_file_write()
        msg = sess.disconnect()
        rt.extruder_run = False
        rt.winder_active = False
        rt.live_snapshot.clear()
        return [f"[FR3D] {msg}"], "INFO"

    if parsed.kind == "serial_show":
        return build_serial_status_lines(rt.cfg, str(rt.config_path)), "INFO"

    if parsed.kind == "serial_list":
        return build_serial_list_lines(rt.cfg), "INFO"

    if parsed.kind == "serial_set_link":
        if sess.alive():
            return [
                "[FR3D] SERIAL SET LINK: DESCONECTAR primero (sesion MK3 activa).",
            ], "ERROR"
        mode_raw = str(parsed.pred_value or "").strip()
        if not mode_raw:
            return ["[FR3D] SERIAL SET LINK: use usb o uart."], "ERROR"
        allowed = {"usb", MK3_LINK_UART, "serial", "gpio", "uart0"}
        if mode_raw.lower() not in allowed:
            return [f"[FR3D] SERIAL SET LINK: modo invalido ({mode_raw!r}). Use usb o uart."], "ERROR"
        set_mk3_link_mode(rt.cfg, mode_raw)
        save_gateway_config(rt.config_path, rt.cfg)
        label = mk3_link_mode_label(rt.cfg)
        return [f"[FR3D] SERIAL SET LINK: {label.lower()} guardado."], "INFO"

    if parsed.kind == "serial_set_port":
        port = str(parsed.pred_value or "").strip()
        if not port:
            return ["[FR3D] SERIAL SET PORT: valor vacio."], "ERROR"
        set_mk3_port_for_active_mode(rt.cfg, port)
        save_gateway_config(rt.config_path, rt.cfg)
        label = mk3_link_mode_label(rt.cfg)
        lines = [f"[FR3D] SERIAL SET PORT ({label}): {port} guardado."]
        # En Windows aplicar al toque (cerrar/abrir COM).
        if sys.platform == "win32":
            if sess.alive():
                rt.stop_csv_file_write()
                sess.disconnect()
                rt.extruder_run = False
                rt.winder_active = False
                rt.live_snapshot.clear()
            ok, msg = sess.connect()
            rt.sync_active_material_to_session()
            lines.append(f"Reconexion: {msg}")
            return lines, "INFO" if ok else "ERROR"
        return lines, "INFO"

    if parsed.kind == "serial_set_baud":
        baud = parse_int(parsed.pred_value, 0)
        if baud <= 0:
            return ["[FR3D] SERIAL SET BAUD: valor invalido."], "ERROR"
        rt.cfg["baud_fr3d"] = str(baud)
        save_gateway_config(rt.config_path, rt.cfg)
        return [f"[FR3D] SERIAL SET BAUD: {baud} guardado."], "INFO"

    if parsed.kind == "extruder_start":
        if not sess.mk3_ready():
            return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"
        gap = 0.03
        send_mk3_immediate(sess, mk3_cmd_set_rpm(float(rt.rpm)))
        time.sleep(gap)
        send_mk3_immediate(sess, mk3_cmd_set_temp(int(round(rt.temp))))
        time.sleep(gap)
        send_mk3_immediate(sess, mk3_cmd_set_fan(int(round(rt.fan))))
        time.sleep(gap)
        send_mk3_immediate(sess, mk3_cmd_pull_mode(False))
        rt.pull_auto = False
        send_mk3_immediate(sess, mk3_cmd_set_pull_rpm(float(rt.pull)))
        rt.winder_meters_target = 900.0
        send_mk3_immediate(sess, mk3_cmd_set_length_target_m(rt.winder_meters_target))
        flush_winder_snapshot(rt)
        time.sleep(FR3D_START_AFTER_PREP_DELAY_S)
        send_mk3_immediate(sess, mk3_cmd_stats_clear())
        send_mk3_immediate(sess, mk3_cmd_start(True))
        rt.extruder_run = True
        rt.extruder_start_mono = time.monotonic()
        rt.begin_csv_feedback_lock()
        write_lines, _ = start_material_csv_write(rt)
        out = ["[FR3D] EXTRUSOR START → MK3."]
        out.extend(write_lines[1:])
        return out, "INFO"

    if parsed.kind == "extruder_stop":
        if not sess.mk3_ready():
            return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"
        # Siempre TX STOP: Pi no decide por rt.extruder_run (puede estar desfasado).
        send_mk3_immediate(sess, mk3_cmd_start(False))
        rt.extruder_run = False
        rt.extruder_start_mono = None
        rt.pred_optimize = False
        rt.stop_csv_file_write()
        rt.begin_csv_feedback_lock()
        return ["[FR3D] EXTRUSOR STOP → MK3."], "INFO"

    if parsed.kind == "cooldown":
        if not sess.mk3_ready():
            return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"
        send_mk3_immediate(sess, mk3_cmd_cooldown())
        rt.begin_csv_feedback_lock()
        return ["[FR3D] COOLDOWN enviado."], "INFO"

    if parsed.kind == "preheat":
        if not sess.mk3_ready():
            return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"
        t_pre = rt.preheat_c()
        send_mk3_immediate(sess, mk3_cmd_set_temp(int(t_pre)))
        rt.temp = float(t_pre)
        rt.begin_csv_feedback_lock()
        return [f"[FR3D] PREHEAT: T={int(t_pre)} C enviado."], "INFO"

    if not sess.mk3_ready():
        return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"

    if parsed.kind == "rpm" and parsed.value is not None:
        v = max(0.0, min(FR3D_EXTRUDER_RPM_MAX, float(parsed.value)))
        send_mk3_immediate(sess, mk3_cmd_set_rpm(v))
        rt.rpm = v
        rt.begin_csv_feedback_lock()
        return [f"[FR3D] RPM {v:.2f} enviado."], "INFO"

    if parsed.kind == "temp" and parsed.value is not None:
        v = max(0, min(250, int(round(float(parsed.value)))))
        send_mk3_immediate(sess, mk3_cmd_set_temp(v))
        rt.temp = float(v)
        rt.begin_csv_feedback_lock()
        return [f"[FR3D] TEMP {v} C enviado."], "INFO"

    if parsed.kind == "fan" and parsed.value is not None:
        v = max(0, min(100, int(round(float(parsed.value)))))
        send_mk3_immediate(sess, mk3_cmd_set_fan(v))
        rt.fan = float(v)
        rt.begin_csv_feedback_lock()
        return [f"[FR3D] FAN {v} % enviado."], "INFO"

    if parsed.kind == "pull" and parsed.value is not None:
        v = max(0.0, min(FR3D_PULL_RPM_MAX, float(parsed.value)))
        send_mk3_immediate(sess, mk3_cmd_pull_mode(False))
        rt.pull_auto = False
        send_mk3_immediate(sess, mk3_cmd_set_pull_rpm(v))
        rt.pull = v
        rt.begin_csv_feedback_lock()
        return [f"[FR3D] PULL {v:.2f} rpm enviado (modo manual)."], "INFO"

    return [f"[FR3D] Comando no implementado: {message}"], "WARNING"


def _apply_pulling_mode(rt: GatewayRuntime, auto: bool) -> Tuple[List[str], str]:
    """Relay transparente: PULLING AUTO|MANUAL → PAUT/PMAN al MK3. Pi no decide."""
    sess = rt.session
    if sess is None or not sess.mk3_ready():
        return ["[FR3D] MK3 no listo (conecta y espera bootstrap)."], "ERROR"
    mode_txt = "AUTO" if auto else "MANUAL"
    send_mk3_immediate(sess, mk3_cmd_pull_mode(bool(auto)))
    rt.pull_auto = bool(auto)
    rt.begin_csv_feedback_lock()
    return [f"[FR3D] PULLING → MK3 ({mode_txt})."], "INFO"
