"""Construccion de STATUS y refresco de snapshot live."""
from __future__ import annotations

import time
from typing import Any, Dict, List

from control_and_merge_dual_serial_csv import (
    merged_row_as_dict,
    parse_mk3_query_dlcd,
    parse_mk3_query_extruder_enabled,
    parse_mk3_query_pr_sw,
    parse_mk3_query_rtf,
)

from fr3d_totem_predictor import build_pred_status_section_lines

from python_gateway.gateway_mk3 import try_push_gateway_mac
from python_gateway.gateway_pred import flush_pred_snapshot
from python_gateway.gateway_pi_host import (
    build_mac_status_line,
    build_wifi_status_line,
    is_linux_gateway_host,
    is_pi_gateway_host,
)
from python_gateway.gateway_pi_led import build_led_status_line
from python_gateway.gateway_serial import mk3_link_mode_label, resolve_mk3_port
from python_gateway.gateway_totem_identity import build_totem_identity_summary_lines
from python_gateway.gateway_cloud_link import cloud_link_label, cloud_link_ok, firebase_enabled
from python_gateway.gateway_runtime import GENERIC_MATERIAL_ID, GatewayRuntime
from python_gateway.gateway_winder import (
    flush_winder_snapshot,
    sync_winder_session_on_mk3_stop,
)


def build_status_lines(rt: GatewayRuntime, *, include_wifi: bool = True) -> List[str]:
    label = rt.line_label()
    snap = dict(rt.live_snapshot)
    lines: List[str] = ["[FR3D] STATUS", f"Linea: {label}"]

    if snap:
        lines.append(str(snap.get("d_line") or "D: —/— · Tact/Ttgt: —/— SW/HM: —/—"))
        lines.append(
            "R/T/F/P: "
            f"{snap.get('r_v', '—')} rpm | "
            f"{snap.get('t_v', '—')} C | "
            f"{snap.get('f_v', '—')} % | "
            f"Pull {snap.get('p_v', snap.get('pull_rpm_v', '—'))} rpm "
            f"({snap.get('pull_mode_v', '—')})"
        )
        extruder_v = str(snap.get("extruder_v") or "STOP").strip().upper()
        if extruder_v not in ("START", "STOP"):
            extruder_v = "START" if extruder_v in ("RUN", "ON", "1", "TRUE") else "STOP"
        pull_pm = str(snap.get("pull_mode_v") or "—").strip().upper()
        if pull_pm not in ("AUTO", "MANUAL"):
            pull_pm = "AUTO" if pull_pm in ("PAUT", "RTF") else pull_pm
        lines.append(f"Extrusor: {extruder_v}")
        lines.append(f"Pulling: {pull_pm if pull_pm in ('AUTO', 'MANUAL') else '—'}")
        lines.append(f"Material: {snap.get('material_v', GENERIC_MATERIAL_ID)}")
        csv_log = "SI" if snap.get("csv_file_write_v") else "NO"
        lines.append(f"CSV log disco: {csv_log}")
        lines.append(f"Record {snap.get('record_v', '—')}")
        lines.append(f"Ciclo telemetria: {snap.get('cycle_s', 10)} s")
        lines.append(
            f"Extruded: {snap.get('l_m_v', '—')} mts / {snap.get('ext_min', 0)} min"
        )
        lines.append(
            f"Pulling {snap.get('pull_rpm_v', '—')}  "
            f"Height Measurement {snap.get('hm_four', '— – —/— – —')}"
        )
    else:
        cycle = rt.session.csv_cycle_s() if rt.session else 10
        lines.extend(
            [
                "D: —/— · Tact/Ttgt: —/— SW/HM: —/—",
                "R/T/F/P: — rpm | — C | — % | Pull — rpm (—)",
                "Extrusor: STOP",
                "Pulling: —",
                f"Material: {rt.effective_material_id()}",
                "Record —",
                f"Ciclo telemetria: {cycle} s",
                "Extruded: — mts / 0 min",
                "Pulling —  Height Measurement — – —/— – —",
            ]
        )

    cloud_ok = cloud_link_ok(rt)
    cloud_name = cloud_link_label(rt)
    lines.append(f"{cloud_name}: {'CONECTADO' if cloud_ok else 'NO CONECTADO'}")
    if firebase_enabled(rt.cfg):
        token = (rt.gateway_token or "").strip()
        client = getattr(rt, "firebase_client", None)
        gk = getattr(client, "gateway_key", "") if client is not None else ""
        lines.append(f"Gateway key: {gk or '—'}")
        lines.append(f"Token: {token or '—'}")
    else:
        lines.extend(
            build_totem_identity_summary_lines(
                rt.cfg,
                socket_connected=cloud_ok,
                socket_totem_id=rt.totem_socket_totem_id,
                socket_enterprise=rt.totem_socket_enterprise,
            )
        )

    if is_linux_gateway_host():
        lines.append(build_mac_status_line())
        if include_wifi:
            lines.append(build_wifi_status_line())
        if is_pi_gateway_host():
            lines.append(build_led_status_line(rt))
        link = mk3_link_mode_label(rt.cfg).lower()
        port = resolve_mk3_port(rt.cfg) or "—"
        lines.append(f"MK3 enlace: {link} @ {port}")

    sess = rt.session
    if sess and sess.mk3_link_ok():
        bootstrap = (
            "LISTO"
            if bool(getattr(sess.merge_rt.state, "mk3_bootstrap_ready", False))
            else "PENDIENTE"
        )
        lines.append(f"Sesion MK3: CONECTADA | bootstrap: {bootstrap}")
    else:
        lines.append("Sesion MK3: DESCONECTADA")

    from python_gateway.gateway_bdwidth import status_line_for_gateway as bdwidth_status_line
    from python_gateway.gateway_artme import status_line_for_gateway as artme_status_line

    bd_line = bdwidth_status_line(rt)
    if bd_line:
        lines.append(bd_line)
    art_line = artme_status_line(rt)
    if art_line:
        lines.append(art_line)

    lines.extend(build_pred_status_section_lines())
    return lines


def refresh_runtime(rt: GatewayRuntime) -> None:
    sess = rt.session
    if sess is None:
        return
    dead = sess.finalize_if_dead()
    if dead:
        rt.extruder_run = False
        rt.winder_active = False
        rt.stop_csv_file_write()
        rt.gw_mac_last_push_mono = 0.0
        rt.gw_last_pushed_wifi = ""
        rt.gw_last_pushed_token = ""
        rt.gw_last_pushed_cloud = ""
        rt.gw_last_pushed_ip = ""
        rt.gw_wifi_offline_since_mono = 0.0
        rt.live_snapshot.clear()
        rt.bdwidth_host_src_sent = False
        rt.bdwidth_last_src_mono = 0.0
        rt.bdwidth_last_inject_mono = 0.0
        flush_pred_snapshot(rt)
        flush_winder_snapshot(rt)
        print(f"[Gateway] {dead}", flush=True)
        return

    sess.poll_fifo(rt)

    mr = sess.merge_rt
    if mr is None:
        rt.live_snapshot.clear()
        flush_pred_snapshot(rt)
        flush_winder_snapshot(rt)
        return

    merged_d: Dict[str, str] = {}
    if mr.state.last_merged_row:
        try:
            merged_d = merged_row_as_dict(
                mr.state.last_merged_row,
                mr.state.header_fr3d,
                mr.state.header_med,
            )
        except Exception:
            merged_d = {}

    try:
        _refresh_live_snapshot(rt, mr, merged_d)
    except Exception as exc:
        print(f"[Gateway] refresh snapshot: {exc}", flush=True)
    try_push_gateway_mac(rt)
    flush_pred_snapshot(rt)
    flush_winder_snapshot(rt)
    try:
        from python_gateway.gateway_artme import is_artme_backend, tick_artme_inject
        from python_gateway.gateway_bdwidth import tick_bdwidth_inject

        if is_artme_backend(getattr(rt, "cfg", {}) or {}):
            tick_artme_inject(rt)
        else:
            tick_bdwidth_inject(rt)
    except Exception as exc:
        print(f"[Gateway] Digital diam inject: {exc}", flush=True)
    try:
        from python_gateway.gateway_lcd import tick_lcd_rem_mirror

        tick_lcd_rem_mirror(rt)
    except Exception as exc:
        print(f"[Gateway] LCDREM mirror: {exc}", flush=True)


def _refresh_live_snapshot(
    rt: GatewayRuntime,
    mr: Any,
    merged_d: Dict[str, str],
) -> None:
    sess = rt.session
    assert sess is not None

    snap_q = mr.state.last_mk3_query_snapshot
    dlcd = getattr(mr.state, "last_mk3_dlcd_mm", None)
    if dlcd is None:
        dlcd = parse_mk3_query_dlcd(snap_q)
    dlcd_v = f"{float(dlcd):.3f}" if dlcd is not None else "—"
    diam_prom_v = (merged_d.get("diam_prom_mm") or "—").strip() or "—"
    t_act_v = (merged_d.get("t_act") or "—").strip() or "—"
    t_tgt_v = (merged_d.get("t_tgt") or "—").strip() or "—"

    s_w_raw = (merged_d.get("S_w") or "").strip()
    _qpr, q_sw, q_swmin, q_swmid, q_swmax = parse_mk3_query_pr_sw(snap_q)
    sw_hm_show = s_w_raw if s_w_raw else (f"{float(q_sw):.3f}" if q_sw is not None else "")
    if not sw_hm_show:
        sw_hm_show = "—"
    swmin_s = f"{float(q_swmin):.3f}" if q_swmin is not None else "—"
    swmid_s = f"{float(q_swmid):.3f}" if q_swmid is not None else "—"
    swmax_s = f"{float(q_swmax):.3f}" if q_swmax is not None else "—"
    hm_four = f"{swmin_s} – {sw_hm_show}/{swmid_s} – {swmax_s}"

    pull_rpm_v = (merged_d.get("pull_rpm") or "—").strip() or f"{rt.pull:.1f}"
    l_m_v = (merged_d.get("L_m") or "—").strip() or "—"
    fus = int(getattr(mr.state, "fusion_counter", 0) or 0)
    record_v = str(fus) if fus else "—"
    ext_min = 0
    if rt.extruder_run and rt.extruder_start_mono is not None:
        ext_min = max(0, int((time.monotonic() - rt.extruder_start_mono) / 60.0))

    qr, qt, qf = parse_mk3_query_rtf(snap_q)
    r_v = f"{float(qr):.2f}" if qr is not None else f"{rt.rpm:.2f}"
    t_v = str(int(qt)) if qt is not None else str(int(round(rt.temp)))
    f_v = str(int(qf)) if qf is not None else str(int(round(rt.fan)))
    p_v = pull_rpm_v if pull_rpm_v != "—" else f"{rt.pull:.1f}"
    pull_mode_v = "AUTO" if bool(getattr(rt, "pull_auto", False)) else "MANUAL"
    pm_csv = (merged_d.get("pull_mode") or "").strip().upper()
    if pm_csv in ("AUTO", "PAUT", "RTF"):
        pull_mode_v = "AUTO"
        rt.pull_auto = True
    elif pm_csv in ("MANUAL", "PNAO", "PMAN"):
        pull_mode_v = "MANUAL"
        rt.pull_auto = False

    extruder_v = "START" if rt.extruder_run else "STOP"
    q_enabled = parse_mk3_query_extruder_enabled(snap_q)
    if q_enabled is True:
        extruder_v = "START"
        rt.extruder_run = True
        if rt.extruder_start_mono is None:
            rt.extruder_start_mono = time.monotonic()
    elif q_enabled is False:
        extruder_v = "STOP"
        rt.extruder_run = False
        rt.extruder_start_mono = None
        sync_winder_session_on_mk3_stop(rt)

    rt.live_snapshot = {
        "d_line": (
            f"D: {dlcd_v}/{diam_prom_v} · Tact/Ttgt: {t_act_v}/{t_tgt_v} "
            f"SW/HM: {sw_hm_show}/{swmid_s}"
        ),
        "record_v": record_v,
        "cycle_s": sess.csv_cycle_s(),
        "l_m_v": l_m_v,
        "ext_min": ext_min,
        "pull_rpm_v": pull_rpm_v,
        "hm_four": hm_four,
        "r_v": r_v,
        "t_v": t_v,
        "f_v": f_v,
        "p_v": p_v,
        "pull_mode_v": pull_mode_v,
        "extruder_v": extruder_v,
        "material_v": rt.effective_material_id(),
        "csv_file_write_v": rt.csv_file_write_active,
    }
