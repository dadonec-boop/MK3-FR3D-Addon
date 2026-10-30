"""Parser BDWidth — sin hardware."""
from fr3d_totem_commands import parse_totem_command
from python_gateway.gateway_bdwidth import (
    CCD_MM,
    build_bdwidth_frame,
    parse_bdwidth_frame,
)


def test_wiki_example_1_764_mm():
    # Wiki: 50 01 78 00 0A → 0x0150 = 336 * 0.00525 = 1.764 mm
    sample = parse_bdwidth_frame(bytes([0x50, 0x01, 0x78, 0x00, 0x0A]))
    assert sample is not None
    assert sample.raw_width == 0x0150
    assert abs(sample.diameter_mm - 1.764) < 1e-9
    assert sample.motion_raw == 0x0078


def test_roundtrip_1_75():
    frame = build_bdwidth_frame(1.75, motion=12)
    sample = parse_bdwidth_frame(frame)
    assert sample is not None
    assert abs(sample.diameter_mm - round(1.75 / CCD_MM) * CCD_MM) < 1e-12
    assert frame[-1] == 0x0A


def test_short_frame_rejected():
    assert parse_bdwidth_frame(b"\x50\x01") is None
    assert parse_bdwidth_frame(b"") is None


def test_auto_recover_due_streak_and_cooldown():
    from python_gateway.gateway_bdwidth import bdwidth_auto_recover_due

    due, recovers, win = bdwidth_auto_recover_due(
        24,
        now_mono=100.0,
        last_recover_mono=0.0,
        recovers_in_window=0,
        window_start_mono=0.0,
        streak_need=25,
    )
    assert due is False

    due, recovers, win = bdwidth_auto_recover_due(
        25,
        now_mono=100.0,
        last_recover_mono=0.0,
        recovers_in_window=0,
        window_start_mono=0.0,
        streak_need=25,
    )
    assert due is True
    assert recovers == 0

    due, _, _ = bdwidth_auto_recover_due(
        25,
        now_mono=150.0,
        last_recover_mono=100.0,
        recovers_in_window=1,
        window_start_mono=100.0,
        streak_need=25,
        cooldown_s=90.0,
    )
    assert due is False

    due, recovers, _ = bdwidth_auto_recover_due(
        25,
        now_mono=200.0,
        last_recover_mono=100.0,
        recovers_in_window=1,
        window_start_mono=100.0,
        streak_need=25,
        cooldown_s=90.0,
    )
    assert due is True
    assert recovers == 1

    due, recovers, _ = bdwidth_auto_recover_due(
        25,
        now_mono=300.0,
        last_recover_mono=200.0,
        recovers_in_window=5,
        window_start_mono=100.0,
        streak_need=25,
        cooldown_s=90.0,
        max_per_window=5,
    )
    assert due is False
    assert recovers == 5


def test_signed_motion_high_bit():
    # motion_raw 0xFF00 → >32767 → signed path in klipper driver
    sample = parse_bdwidth_frame(bytes([0x50, 0x01, 0x00, 0xFF, 0x0A]))
    assert sample is not None
    assert sample.motion_raw == 0xFF00
    assert sample.motion == -(0xFF00 - 65535)


def test_totem_commands():
    assert parse_totem_command("BDWIDTH").kind == "bdwidth_status"
    assert parse_totem_command("bdwidth status").kind == "bdwidth_status"
    assert parse_totem_command("BDWIDTH LIST").kind == "bdwidth_list"
    assert parse_totem_command("BDWIDTH INJECT ON").kind == "bdwidth_inject_on"
    assert parse_totem_command("BDWIDTH INJECT OFF").kind == "bdwidth_inject_off"
    assert parse_totem_command("BDWIDTH ON").kind == "bdwidth_mock"
    assert parse_totem_command("BDWIDTH OFF").kind == "bdwidth_off"
    assert parse_totem_command("BDWIDTH MOCK").kind == "bdwidth_mock"
    assert parse_totem_command("BDWIDTH MOCK ON").kind == "bdwidth_mock"
    assert parse_totem_command("bdwidth mock off").kind == "bdwidth_off"
    assert parse_totem_command("BDWIDTH REAL").kind == "bdwidth_real"
    src = parse_totem_command("BDWIDTH SOURCE MANUAL")
    assert src.kind == "bdwidth_source"
    assert src.item_key == "manual"
    assert parse_totem_command("BDWIDTH SOURCE A3").item_key == "a3"
    assert parse_totem_command("BDWIDTH SOURCE USB").item_key == "usb"
    assert parse_totem_command("BDWIDTH USB").kind == "bdwidth_real"
    assert parse_totem_command("BDWIDTH SIMULADOR").kind == "bdwidth_mock"
    assert parse_totem_command("BDWIDTH DIAM").kind == "bdwidth_diam"
    dset = parse_totem_command("BDWIDTH DIAM 1.76")
    assert dset.kind == "bdwidth_diam_set"
    assert abs(float(dset.value) - 1.76) < 1e-9
    inj = parse_totem_command("BDWIDTH INJECT ON 1.75")
    assert inj.kind == "bdwidth_diam_set"
    assert abs(float(inj.value) - 1.75) < 1e-9
    assert parse_totem_command("BDWIDTH INJECT 1.70").kind == "bdwidth_diam_set"
    rng = parse_totem_command("BDWIDTH MOCK 1.650 1.8")
    assert rng.kind == "bdwidth_mock"
    assert abs(float(rng.value) - 1.650) < 1e-9
    assert abs(float(rng.pred_value) - 1.8) < 1e-9


def test_mock_range_clamp():
    from python_gateway.gateway_bdwidth import clamp_mock_range, _mock_sample

    lo, hi = clamp_mock_range(1.8, 1.65)
    assert abs(lo - 1.65) < 1e-9
    assert abs(hi - 1.8) < 1e-9
    fixed_lo, fixed_hi = clamp_mock_range(1.76, 1.76)
    assert abs(fixed_lo - 1.76) < 1e-9
    assert abs(fixed_hi - 1.76) < 1e-9
    sample = _mock_sample(0.0, 1.650, 1.800)
    assert 1.649 <= sample.diameter_mm <= 1.801
    fixed = _mock_sample(0.0, 1.75, 1.75)
    assert abs(fixed.diameter_mm - 1.75) < 1e-9


def test_mk3_port_excluded():
    from python_gateway.gateway_bdwidth import port_is_excluded

    mk3 = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
    assert port_is_excluded(mk3, [mk3])
    assert port_is_excluded(mk3, ["/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"])
    assert not port_is_excluded("/dev/ttyUSB1", [mk3])


def test_mk3_diam_cmds():
    from control_and_merge_dual_serial_csv import (
        mk3_cmd_diam_set,
        mk3_cmd_diam_src,
        parse_mk3_query_diam_src,
    )

    assert mk3_cmd_diam_src(True) == "DIAMSRC1"
    assert mk3_cmd_diam_src(False) == "DIAMSRC0"
    assert mk3_cmd_diam_src(2) == "DIAMSRC2"
    assert mk3_cmd_diam_set(1.764) == "DIAMSET1.764"
    assert parse_mk3_query_diam_src("echo:DIAMSRC,1,\n") == 1
    assert parse_mk3_query_diam_src("echo:DIAMSRC,0,\n") == 0
    assert parse_mk3_query_diam_src("echo:DIAMSRC,2,\n") == 2
    assert parse_mk3_query_diam_src("echo:A3,off,\n") is None


if __name__ == "__main__":
    test_wiki_example_1_764_mm()
    test_roundtrip_1_75()
    test_short_frame_rejected()
    test_signed_motion_high_bit()
    test_totem_commands()
    test_mock_range_clamp()
    test_mk3_port_excluded()
    test_mk3_diam_cmds()
    print("test_gateway_bdwidth: OK")
