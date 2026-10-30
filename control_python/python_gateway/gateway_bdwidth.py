"""Lector BDWidth (PandaPi) en el core del gateway.

Tramo 1: poll USB, parse Ø/motion, log y STATUS. No inyecta al MK3
(bdwidth_inject_mk3 queda para DIAMSET en firmware).

Protocolo (wiki + klipper/bdwidth.py):
  baud 500000; TX 0x0A; RX 5 bytes LE uint16 width, LE uint16 motion, 0x0A.
  width_mm = raw * 0.00525
  Probe version: G00; → contiene 'pandapi3dV'
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

CCD_MM = 0.00525
BDWIDTH_BAUD = 500000
MOCK_LO_MIN = 1.20
MOCK_HI_MAX = 2.80
# Debajo de esto no se reenvia DIAMSET (sin filamento / ruido); MK3 USB stale → AN.
DIAMSET_MIN_VALID_MM = 0.5
BDWIDTH_POLL = b"\n"
BDWIDTH_FRAME_LEN = 5
BDWIDTH_VERSION_MARKER = "pandapi3dV"
CH340_VID = 0x1A86
CH340_KEYWORDS = (
    "ch340",
    "ch341",
    "1a86",
    "qinheng",
    "usb_serial",
    "ttych341",
    "ch341usb",
)
# Auto-recover USB (equiv. OFF→espera→REAL sin tocar MK3/DIAMSRC).
BDWIDTH_AUTO_RECOVER_STREAK = 25
BDWIDTH_AUTO_RECOVER_WAIT_S = 1.5
BDWIDTH_AUTO_RECOVER_COOLDOWN_S = 90.0
BDWIDTH_AUTO_RECOVER_MAX_PER_HOUR = 5
BDWIDTH_AUTO_RECOVER_WINDOW_S = 3600.0


@dataclass(frozen=True)
class BdwidthSample:
    diameter_mm: float
    raw_width: int
    motion: int
    motion_raw: int
    mono: float


@dataclass
class BdwidthSnapshot:
    enabled: bool = False
    mode: str = "off"  # off | usb | mock
    connected: bool = False
    port: str = ""
    baud: int = BDWIDTH_BAUD
    diameter_mm: Optional[float] = None
    raw_width: int = 0
    motion: int = 0
    samples: int = 0
    error: str = ""
    last_mono: float = 0.0
    inject_mk3: bool = False
    version: str = ""
    inject_mm: Optional[float] = None
    inject_mono: float = 0.0
    mock_lo: float = 1.738
    mock_hi: float = 1.762

    def age_s(self, now: Optional[float] = None) -> Optional[float]:
        if self.last_mono <= 0:
            return None
        return max(0.0, float(now if now is not None else time.monotonic()) - self.last_mono)


def build_bdwidth_frame(width_mm: float, motion: int = 0) -> bytes:
    raw = int(round(float(width_mm) / CCD_MM))
    raw = max(0, min(65535, raw))
    mot = int(motion) & 0xFFFF
    return bytes(
        [
            raw & 0xFF,
            (raw >> 8) & 0xFF,
            mot & 0xFF,
            (mot >> 8) & 0xFF,
            0x0A,
        ]
    )


def parse_bdwidth_frame(data: bytes) -> Optional[BdwidthSample]:
    if not data or len(data) < BDWIDTH_FRAME_LEN:
        return None
    frame = bytes(data[:BDWIDTH_FRAME_LEN])
    if 0x0A not in frame:
        return None
    raw_width = ((frame[1] << 8) + frame[0]) & 0xFFFF
    motion_raw = ((frame[3] << 8) + frame[2]) & 0xFFFF
    motion = motion_raw
    if motion > 32767:
        motion = motion - 65535
    motion = -motion
    return BdwidthSample(
        diameter_mm=raw_width * CCD_MM,
        raw_width=raw_width,
        motion=int(motion),
        motion_raw=int(motion_raw),
        mono=time.monotonic(),
    )


def bdwidth_auto_recover_due(
    invalid_streak: int,
    *,
    now_mono: float,
    last_recover_mono: float,
    recovers_in_window: int,
    window_start_mono: float,
    streak_need: int = BDWIDTH_AUTO_RECOVER_STREAK,
    cooldown_s: float = BDWIDTH_AUTO_RECOVER_COOLDOWN_S,
    max_per_window: int = BDWIDTH_AUTO_RECOVER_MAX_PER_HOUR,
    window_s: float = BDWIDTH_AUTO_RECOVER_WINDOW_S,
) -> tuple[bool, int, float]:
    """¿Reabrir USB tras N frames invalidos? Devuelve (due, recovers, window_start)."""
    streak_need = max(1, int(streak_need))
    if invalid_streak < streak_need:
        return False, recovers_in_window, window_start_mono
    if window_start_mono <= 0.0 or (now_mono - window_start_mono) >= window_s:
        recovers_in_window = 0
        window_start_mono = now_mono
    if recovers_in_window >= max(1, int(max_per_window)):
        return False, recovers_in_window, window_start_mono
    if last_recover_mono > 0.0 and (now_mono - last_recover_mono) < float(cooldown_s):
        return False, recovers_in_window, window_start_mono
    return True, recovers_in_window, window_start_mono


def list_ch340_ports() -> List[str]:
    found: set[str] = set()
    try:
        from serial.tools import list_ports
    except ImportError:
        list_ports = None
    if list_ports is not None:
        for item in list_ports.comports():
            vid = getattr(item, "vid", None)
            desc = (getattr(item, "description", None) or "").lower()
            hwid = (getattr(item, "hwid", None) or "").lower()
            device = (getattr(item, "device", None) or "").strip()
            if not device:
                continue
            if vid == CH340_VID or any(k in desc or k in hwid for k in CH340_KEYWORDS):
                found.add(device)
    by_id = "/dev/serial/by-id"
    if os.path.isdir(by_id):
        try:
            for name in os.listdir(by_id):
                if any(k in name.lower() for k in CH340_KEYWORDS):
                    found.add(os.path.join(by_id, name))
        except OSError:
            pass
    # UNO Q / kernels con modulo ch341 out-of-tree: /dev/ttyCH341USB*
    try:
        import glob as _glob

        for path in _glob.glob("/dev/ttyCH341USB*"):
            if os.path.exists(path):
                found.add(path)
    except OSError:
        pass
    return sorted(found)

def list_bdwidth_port_lines() -> List[str]:
    lines = ["[FR3D] BDWIDTH LIST"]
    ports = list_ch340_ports()
    if not ports:
        lines.append("(sin CH340 / by-id candidatos)")
        return lines
    for port in ports:
        lines.append(port)
    return lines


def _port_key(port: str) -> str:
    p = (port or "").strip()
    if not p:
        return ""
    try:
        return os.path.realpath(p)
    except OSError:
        return p


def port_is_excluded(port: str, exclude: Sequence[str]) -> bool:
    """True si `port` es el mismo dispositivo que alguno de `exclude` (by-id vs tty)."""
    key = _port_key(port)
    if not key:
        return False
    keys = {_port_key(x) for x in exclude if str(x or "").strip()}
    if key in keys:
        return True
    base = os.path.basename(key)
    if not base:
        return False
    return any(os.path.basename(k) == base for k in keys)


def mk3_ports_from_cfg(cfg: Optional[Dict[str, str]]) -> List[str]:
    if not cfg:
        return []
    raw = [
        cfg.get("port_fr3d") or "",
        cfg.get("port_fr3d_usb") or "",
        cfg.get("port_fr3d_uart") or "",
    ]
    try:
        from python_gateway.gateway_serial import resolve_mk3_port

        raw.append(resolve_mk3_port(cfg) or "")
    except Exception:
        pass
    out: List[str] = []
    seen = set()
    for p in raw:
        t = str(p or "").strip()
        if not t or t.lower() in ("auto", "mock"):
            continue
        for item in (t, _port_key(t)):
            if item and item not in seen:
                seen.add(item)
                out.append(item)
    return out


def _open_serial_no_autoreset(port: str, baud: int, timeout_s: float):
    """Abre USB-UART sin pulsar DTR/RTS (evita reset del Mega si el puerto es el MK3).

    Los CH340 genéricos suelen compartir el mismo by-id (`usb-1a86_USB_Serial-...`);
    un probe al puerto equivocado con DTR por defecto deja el LCD en blanco.
    """
    import serial

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = timeout_s
    ser.dsrdtr = False
    ser.rtscts = False
    ser.xonxoff = False
    try:
        ser.dtr = False
    except Exception:
        pass
    ser.open()
    try:
        ser.dtr = False
    except Exception:
        pass
    return ser


def probe_bdwidth_version(port: str, baud: int = BDWIDTH_BAUD, timeout_s: float = 0.6) -> Optional[str]:
    try:
        import serial  # noqa: F401 — presencia de pyserial
    except ImportError:
        return None
    ser = None
    try:
        ser = _open_serial_no_autoreset(port, baud, timeout_s)
        time.sleep(0.15)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(b"G00;\n")
        line = ser.readline()
        text = line.decode("utf-8", errors="ignore").strip()
        if BDWIDTH_VERSION_MARKER in text:
            return text
    except Exception:
        return None
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
    return None


def auto_detect_bdwidth_port(
    baud: int = BDWIDTH_BAUD,
    exclude: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Solo un puerto que responda `pandapi3dV`. Nunca el CH340 del MK3."""
    ex = list(exclude or [])
    candidates = [p for p in list_ch340_ports() if not port_is_excluded(p, ex)]
    for port in candidates:
        if probe_bdwidth_version(port, baud=baud, timeout_s=0.25):
            return port
    return None


def clamp_mock_mm(mm: float) -> float:
    return max(MOCK_LO_MIN, min(MOCK_HI_MAX, float(mm)))


def clamp_mock_range(lo: float, hi: float) -> tuple[float, float]:
    a = float(lo)
    b = float(hi)
    if a > b:
        a, b = b, a
    a = max(MOCK_LO_MIN, min(MOCK_HI_MAX, a))
    b = max(MOCK_LO_MIN, min(MOCK_HI_MAX, b))
    if (b - a) < 1e-4:
        v = clamp_mock_mm(a)
        return v, v
    if (b - a) < 0.01:
        b = min(MOCK_HI_MAX, a + 0.01)
        if (b - a) < 0.01:
            a = max(MOCK_LO_MIN, b - 0.01)
    return a, b


def mock_range_from_cfg(cfg: Optional[Dict[str, str]]) -> tuple[float, float]:
    from python_gateway.gateway_config import parse_float

    cfg = cfg or {}
    lo = parse_float(cfg.get("bdwidth_mock_lo"), 1.738)
    hi = parse_float(cfg.get("bdwidth_mock_hi"), 1.762)
    return clamp_mock_range(lo, hi)


def _mock_sample(t0: float, lo: float = 1.738, hi: float = 1.762) -> BdwidthSample:
    now = time.monotonic()
    lo, hi = clamp_mock_range(lo, hi)
    motion = int(8 + 4 * math.sin((now - t0) * 1.3))
    if (hi - lo) < 1e-4:
        # Fijo: Ø pedido (1.75), no el paso CCD 0.00525 (1.748).
        sample = parse_bdwidth_frame(build_bdwidth_frame(lo, motion))
        assert sample is not None
        return BdwidthSample(
            diameter_mm=lo,
            raw_width=sample.raw_width,
            motion=sample.motion,
            motion_raw=sample.motion_raw,
            mono=sample.mono,
        )
    mid = (lo + hi) * 0.5
    amp = (hi - lo) * 0.5
    width = mid + amp * math.sin((now - t0) * 0.7)
    sample = parse_bdwidth_frame(build_bdwidth_frame(width, motion))
    assert sample is not None
    return sample


class BdwidthMonitor:
    """Hilo de poll. Independiente del MK3."""

    def __init__(self, cfg: Dict[str, str]) -> None:
        self._cfg = cfg
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._snap = BdwidthSnapshot()
        self._t0 = time.monotonic()

    def snapshot(self) -> BdwidthSnapshot:
        from python_gateway.gateway_config import parse_bool

        inject = parse_bool(self._cfg.get("bdwidth_inject_mk3"), False)
        lo, hi = mock_range_from_cfg(self._cfg)
        with self._lock:
            s = self._snap
            return BdwidthSnapshot(
                enabled=s.enabled,
                mode=s.mode,
                connected=s.connected,
                port=s.port,
                baud=s.baud,
                diameter_mm=s.diameter_mm,
                raw_width=s.raw_width,
                motion=s.motion,
                samples=s.samples,
                error=s.error,
                last_mono=s.last_mono,
                inject_mk3=inject,
                version=s.version,
                inject_mm=s.inject_mm,
                inject_mono=s.inject_mono,
                mock_lo=lo,
                mock_hi=hi,
            )

    def _apply_sample(self, sample: BdwidthSample, *, port: str, mode: str, version: str) -> None:
        with self._lock:
            self._snap.connected = True
            self._snap.mode = mode
            self._snap.port = port
            self._snap.diameter_mm = sample.diameter_mm
            self._snap.raw_width = sample.raw_width
            self._snap.motion = sample.motion
            self._snap.samples += 1
            self._snap.last_mono = sample.mono
            self._snap.error = ""
            if version:
                self._snap.version = version

    def note_inject(self, mm: float) -> None:
        with self._lock:
            self._snap.inject_mm = float(mm)
            self._snap.inject_mono = time.monotonic()

    def _set_error(self, msg: str, *, connected: bool = False) -> None:
        with self._lock:
            self._snap.connected = connected
            self._snap.error = msg

    def start(self) -> None:
        from python_gateway.gateway_config import parse_bool, parse_int

        enabled = parse_bool(self._cfg.get("bdwidth_enabled"), False)
        inject = parse_bool(self._cfg.get("bdwidth_inject_mk3"), False)
        baud = parse_int(self._cfg.get("bdwidth_baud"), BDWIDTH_BAUD)
        port_cfg = (self._cfg.get("bdwidth_port") or "auto").strip()
        with self._lock:
            self._snap = BdwidthSnapshot(
                enabled=enabled,
                mode="off" if not enabled else ("mock" if port_cfg.lower() == "mock" else "usb"),
                port=port_cfg,
                baud=baud if baud > 0 else BDWIDTH_BAUD,
                inject_mk3=inject,
            )
        if not enabled:
            return
        if self._thread and self._thread.is_alive():
            print("[BDWidth] hilo anterior aun vivo; no se lanza otro", flush=True)
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="fr3d-bdwidth", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thr = self._thread
        if thr and thr.is_alive():
            thr.join(timeout=2.5)
        if thr and thr.is_alive():
            print("[BDWidth] stop: hilo no termino a tiempo", flush=True)
            return
        self._thread = None
        with self._lock:
            self._snap.connected = False

    def restart(self) -> None:
        """Releer config (enabled/port/inject) y relanzar el hilo mock/USB."""
        self.stop()
        if self._thread and self._thread.is_alive():
            self._set_error("no se pudo detener el hilo BDWidth")
            return
        self._stop.clear()
        self._t0 = time.monotonic()
        self.start()

    def wait_sample(self, timeout_s: float = 0.8) -> bool:
        deadline = time.monotonic() + max(0.05, float(timeout_s))
        while time.monotonic() < deadline:
            snap = self.snapshot()
            if snap.diameter_mm is not None:
                return True
            time.sleep(0.04)
        return False

    def _poll_hz(self) -> float:
        from python_gateway.gateway_config import parse_float

        hz = parse_float(self._cfg.get("bdwidth_poll_hz"), 5.0)
        # Banco / sensor USB: hasta 50 Hz. En gateway productivo suele bastar 5–10.
        return max(0.5, min(50.0, hz))

    def _log_every_n(self) -> int:
        from python_gateway.gateway_config import parse_int

        # 1 = imprimir cada muestra (banco). 0 = cada ~5 s (default gateway).
        every = parse_int(self._cfg.get("bdwidth_log_every"), 0)
        if every > 0:
            return max(1, every)
        return int(max(1, self._poll_hz() * 5))

    def _auto_recover_enabled(self) -> bool:
        from python_gateway.gateway_config import parse_bool

        return parse_bool(self._cfg.get("bdwidth_auto_recover"), True)

    def _auto_recover_params(self) -> tuple[int, float, float, int]:
        from python_gateway.gateway_config import parse_float, parse_int

        streak = parse_int(self._cfg.get("bdwidth_auto_recover_streak"), BDWIDTH_AUTO_RECOVER_STREAK)
        wait_s = parse_float(self._cfg.get("bdwidth_auto_recover_wait_s"), BDWIDTH_AUTO_RECOVER_WAIT_S)
        cool_s = parse_float(
            self._cfg.get("bdwidth_auto_recover_cooldown_s"), BDWIDTH_AUTO_RECOVER_COOLDOWN_S
        )
        max_n = parse_int(
            self._cfg.get("bdwidth_auto_recover_max_per_hour"), BDWIDTH_AUTO_RECOVER_MAX_PER_HOUR
        )
        return (
            max(1, int(streak or BDWIDTH_AUTO_RECOVER_STREAK)),
            max(0.2, float(wait_s or BDWIDTH_AUTO_RECOVER_WAIT_S)),
            max(5.0, float(cool_s or BDWIDTH_AUTO_RECOVER_COOLDOWN_S)),
            max(1, int(max_n or BDWIDTH_AUTO_RECOVER_MAX_PER_HOUR)),
        )

    def _run(self) -> None:
        port_cfg = (self._cfg.get("bdwidth_port") or "auto").strip()
        if port_cfg.lower() == "mock":
            self._run_mock()
            return
        self._run_usb(port_cfg)

    def _run_mock(self) -> None:
        with self._lock:
            self._snap.mode = "mock"
            self._snap.port = "mock"
            self._snap.connected = True
        print("[BDWidth] modo mock (sin sensor USB)", flush=True)
        period = 1.0 / self._poll_hz()
        while not self._stop.is_set():
            lo, hi = mock_range_from_cfg(self._cfg)
            self._apply_sample(
                _mock_sample(self._t0, lo, hi),
                port="mock",
                mode="mock",
                version="mock",
            )
            snap = self.snapshot()
            if snap.samples == 1 or snap.samples % self._log_every_n() == 0:
                _log_sample(snap)
            if self._stop.wait(period):
                break

    def _run_usb(self, port_cfg: str) -> None:
        period = 1.0 / self._poll_hz()
        ser = None
        version = ""
        resolved = ""
        invalid_streak = 0
        last_recover_mono = 0.0
        recovers_in_window = 0
        window_start_mono = 0.0
        while not self._stop.is_set():
            if ser is None:
                resolved = port_cfg
                if not resolved or resolved.lower() == "auto":
                    resolved = (
                        auto_detect_bdwidth_port(
                            self.snapshot().baud,
                            exclude=mk3_ports_from_cfg(self._cfg),
                        )
                        or ""
                    )
                elif port_is_excluded(resolved, mk3_ports_from_cfg(self._cfg)):
                    self._set_error(
                        "puerto es el MK3; no se abre. Enchufe BDWidth o use BDWIDTH MOCK."
                    )
                    resolved = ""
                if not resolved:
                    self._set_error(
                        "sin BDWidth USB (el CH340 del MK3 no se usa). MOCK o enchufe el sensor."
                    )
                    self._stop.wait(2.0)
                    continue
                try:
                    baud = self.snapshot().baud
                    if not version and port_cfg.lower() != "auto":
                        version = probe_bdwidth_version(resolved, baud=baud) or ""
                    ser = _open_serial_no_autoreset(resolved, baud, 0.08)
                    time.sleep(0.15)
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    with self._lock:
                        self._snap.port = resolved
                        self._snap.mode = "usb"
                        self._snap.version = version
                        self._snap.error = ""
                    print(
                        f"[BDWidth] USB abierto {resolved} baud={baud}"
                        + (f" ver={version}" if version else ""),
                        flush=True,
                    )
                except Exception as exc:
                    self._set_error(f"open {resolved}: {exc}")
                    ser = None
                    self._stop.wait(2.0)
                    continue
            try:
                ser.reset_input_buffer()
                ser.write(BDWIDTH_POLL)
                data = ser.read(BDWIDTH_FRAME_LEN)
                sample = parse_bdwidth_frame(data)
                if sample is None:
                    invalid_streak += 1
                    self._set_error("frame invalido", connected=True)
                    if self._auto_recover_enabled():
                        streak_need, wait_s, cool_s, max_n = self._auto_recover_params()
                        now = time.monotonic()
                        due, recovers_in_window, window_start_mono = bdwidth_auto_recover_due(
                            invalid_streak,
                            now_mono=now,
                            last_recover_mono=last_recover_mono,
                            recovers_in_window=recovers_in_window,
                            window_start_mono=window_start_mono,
                            streak_need=streak_need,
                            cooldown_s=cool_s,
                            max_per_window=max_n,
                        )
                        if due:
                            recovers_in_window += 1
                            last_recover_mono = now
                            invalid_streak = 0
                            version = ""
                            print(
                                f"[BDWidth] auto-recover: {streak_need} frames invalidos; "
                                f"reabriendo USB (espera {wait_s:.1f}s, "
                                f"intento {recovers_in_window}/{max_n} en 1h)",
                                flush=True,
                            )
                            self._set_error(
                                f"auto-recover USB ({recovers_in_window}/{max_n})",
                                connected=False,
                            )
                            try:
                                ser.close()
                            except Exception:
                                pass
                            ser = None
                            self._stop.wait(wait_s)
                            continue
                else:
                    invalid_streak = 0
                    self._apply_sample(sample, port=resolved, mode="usb", version=version)
                    snap = self.snapshot()
                    if snap.samples == 1 or snap.samples % self._log_every_n() == 0:
                        _log_sample(snap)
            except Exception as exc:
                invalid_streak = 0
                self._set_error(str(exc))
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                self._stop.wait(1.0)
                continue
            self._stop.wait(period)
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass


def _log_sample(snap: BdwidthSnapshot) -> None:
    diam = "—" if snap.diameter_mm is None else f"{snap.diameter_mm:.3f}"
    print(
        f"[BDWidth] D={diam} mm motion={snap.motion} rawW={snap.raw_width} "
        f"n={snap.samples} port={snap.port or '—'}",
        flush=True,
    )


def build_bdwidth_status_lines(monitor: Optional[BdwidthMonitor]) -> List[str]:
    lines = ["[FR3D] BDWIDTH"]
    if monitor is None:
        lines.append("enabled: no")
        lines.append("NOTE: modulo no iniciado.")
        return lines
    snap = monitor.snapshot()
    lines.append(f"enabled: {'yes' if snap.enabled else 'no'}")
    lines.append(f"mode: {snap.mode}")
    lines.append(f"connected: {'yes' if snap.connected else 'no'}")
    lines.append(f"port: {snap.port or '—'}")
    lines.append(f"baud: {snap.baud}")
    if snap.version:
        lines.append(f"version: {snap.version}")
    if snap.diameter_mm is None:
        lines.append("D: — mm")
    else:
        lines.append(f"D: {snap.diameter_mm:.3f} mm")
    lines.append(f"raw: {snap.raw_width}")
    lines.append(f"motion: {snap.motion}")
    lines.append(f"samples: {snap.samples}")
    age = snap.age_s()
    lines.append(f"age_s: {'—' if age is None else f'{age:.2f}'}")
    lines.append(f"inject_mk3: {'on' if snap.inject_mk3 else 'off'}")
    if snap.mode == "mock":
        if abs(snap.mock_hi - snap.mock_lo) < 1e-4:
            lines.append(f"mock_range: {snap.mock_lo:.3f} mm (fijo)")
        else:
            lines.append(f"mock_range: {snap.mock_lo:.3f} .. {snap.mock_hi:.3f} mm")
    if snap.inject_mm is None:
        lines.append("mk3_set: — mm")
    else:
        lines.append(f"mk3_set: {snap.inject_mm:.3f} mm")
        if snap.inject_mono > 0:
            lines.append(f"mk3_set_age_s: {max(0.0, time.monotonic() - snap.inject_mono):.2f}")
    if snap.error:
        lines.append(f"error: {snap.error}")
    if not snap.enabled:
        lines.append("NOTE: bdwidth_enabled=false en config_gateway.csv")
    return lines


def build_bdwidth_diam_lines(monitor: Optional[BdwidthMonitor]) -> List[str]:
    """Ø vivo y último DIAMSET enviado al MK3."""
    lines = ["[FR3D] BDWIDTH DIAM"]
    if monitor is None:
        lines.append("live: — mm")
        lines.append("mk3_set: — mm")
        lines.append("NOTE: modulo no iniciado.")
        return lines
    snap = monitor.snapshot()
    if snap.diameter_mm is None:
        lines.append("live: — mm")
    else:
        lines.append(f"live: {snap.diameter_mm:.3f} mm")
    if snap.inject_mm is None:
        lines.append("mk3_set: — mm")
        if snap.inject_mk3:
            lines.append("NOTE: inject on, aun no se envio DIAMSET (MK3 no listo o sin muestra).")
        else:
            lines.append("NOTE: inject_mk3=off")
    else:
        lines.append(f"mk3_set: {snap.inject_mm:.3f} mm")
        if snap.inject_mono > 0:
            lines.append(f"mk3_set_age_s: {max(0.0, time.monotonic() - snap.inject_mono):.2f}")
    return lines


def tick_bdwidth_inject(rt: Any) -> None:
    """DIAMSRC solo si hace falta; DIAMSET periodico (USB) / si cambia (manual fijo).

    No reenviar DIAMSRC cada N s: en el MK3 hace Config_StoreSettings (EEPROM)
    y satura el Mega (~tropiezo del sinfin cada ~8-10 s con la Pi conectada).

    DIAMSET va PRI_USER (+ coalesce en cola TX) para convivir con LCDQ/ENC sin
    dejar HOST stale (firmware USB ~5 s). Keepalive: si el ultimo TX tiene
    >= DIAMSET_KEEPALIVE_S, fuerza otro envio aunque el valor no haya cambiado.

    USB live: diameter_mm < DIAMSET_MIN_VALID_MM no inyecta (evita fantasma del
    ultimo Ø y deja stale → predictor AN).
    """
    from python_gateway.gateway_config import parse_bool

    # MK3 HOST stale = 5 s; keepalive < eso aunque LCDQ compita por el USB.
    DIAMSET_KEEPALIVE_S = 2.5
    DIAMSET_MIN_GAP_S = 1.0

    if not parse_bool(getattr(rt, "cfg", {}).get("bdwidth_inject_mk3"), False):
        return

    mon = getattr(rt, "bdwidth", None)
    if not isinstance(mon, BdwidthMonitor):
        return
    snap = mon.snapshot()
    if not snap.enabled or not snap.connected or snap.diameter_mm is None:
        return
    sess = getattr(rt, "session", None)
    if sess is None or not getattr(sess, "mk3_ready", lambda: False)():
        return
    from python_gateway.gateway_mk3_caps import mk3_supports_host_diam

    if not mk3_supports_host_diam(rt):
        return
    now = time.monotonic()
    last = float(getattr(rt, "bdwidth_last_inject_mono", 0.0) or 0.0)
    age = (now - last) if last > 0.0 else 999.0
    if last > 0.0 and age < DIAMSET_MIN_GAP_S:
        return

    try:
        from control_and_merge_dual_serial_csv import mk3_cmd_diam_set, mk3_cmd_diam_src
        from python_gateway.gateway_mk3 import PRI_USER, send_mk3_immediate

        # Releer cfg/O pedido justo antes de enviar. Un tick que arranco con
        # mock_lo=1.75 no debe pisar un BDWIDTH DIAM 1.65 concurrente.
        snap = mon.snapshot()
        lo, hi = mock_range_from_cfg(getattr(rt, "cfg", {}) or {})
        fixed_manual = snap.mode == "mock" and abs(hi - lo) < 1e-4
        want_src = 2 if fixed_manual else 1
        commanded = getattr(rt, "bdwidth_manual_mm", None)
        if fixed_manual:
            mm = float(commanded) if commanded is not None else float(lo)
        else:
            if snap.diameter_mm is None:
                return
            mm = float(snap.diameter_mm)

        if not bool(getattr(rt, "bdwidth_host_src_sent", False)):
            send_mk3_immediate(
                sess,
                mk3_cmd_diam_src(want_src),
                priority=PRI_USER,
            )
            rt.bdwidth_host_src_sent = True
            rt.bdwidth_last_src_mono = now

        # Sin filamento / Ø basura: no keepalive del ultimo valor.
        if not fixed_manual and mm < DIAMSET_MIN_VALID_MM:
            return

        if fixed_manual:
            prev = snap.inject_mm
            already = prev is not None and abs(float(prev) - mm) < 1e-4
            # Manual fijo no usa stale USB; igual keepalive por si el MK3 reinicio.
            if already and last > 0.0 and age < DIAMSET_KEEPALIVE_S:
                return

        send_mk3_immediate(
            sess,
            mk3_cmd_diam_set(mm),
            priority=PRI_USER,
        )
        rt.bdwidth_last_inject_mono = now
        if fixed_manual:
            rt.bdwidth_manual_mm = mm
        mon.note_inject(mm)
    except Exception as exc:
        print(f"[BDWidth] inject MK3: {exc}", flush=True)
        rt.bdwidth_host_src_sent = False
        rt.bdwidth_last_inject_mono = 0.0



def start_bdwidth_monitor(rt: Any) -> Optional[BdwidthMonitor]:
    cfg = getattr(rt, "cfg", None) or {}
    mon = BdwidthMonitor(cfg)
    rt.bdwidth = mon
    mon.start()
    return mon


def status_line_for_gateway(rt: Any) -> Optional[str]:
    mon = getattr(rt, "bdwidth", None)
    if not isinstance(mon, BdwidthMonitor):
        return None
    snap = mon.snapshot()
    if not snap.enabled:
        return None
    diam = "—" if snap.diameter_mm is None else f"{snap.diameter_mm:.3f}"
    link = "OK" if snap.connected else "NO"
    return f"BDWidth: {link} Ø={diam} mm ({snap.mode} {snap.port or '—'})"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Banco BDWidth FR3D (sin MK3). mock | auto | puerto USB."
    )
    parser.add_argument(
        "--port",
        default="mock",
        help="mock | auto | COMx | /dev/serial/by-id/...",
    )
    parser.add_argument("--baud", type=int, default=BDWIDTH_BAUD)
    parser.add_argument(
        "--hz",
        type=float,
        default=20.0,
        help="Polls/s (default banco 20, max 50). No hay promedio: cada muestra es cruda.",
    )
    parser.add_argument("--seconds", type=float, default=8.0, help="0 = hasta Ctrl+C")
    parser.add_argument(
        "--every",
        type=int,
        default=1,
        help="Imprimir cada N muestras (1=todas). Default banco: 1.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    cfg = {
        "bdwidth_enabled": "true",
        "bdwidth_port": str(args.port),
        "bdwidth_baud": str(args.baud),
        "bdwidth_poll_hz": str(args.hz),
        "bdwidth_log_every": str(max(1, int(args.every))),
        "bdwidth_inject_mk3": "false",
    }
    mon = BdwidthMonitor(cfg)
    mon.start()
    print(
        f"[BDWidth] banco port={args.port} baud={args.baud} hz={args.hz} "
        f"log_every={args.every} (Ctrl+C para salir)",
        flush=True,
    )
    t_end = None if float(args.seconds) <= 0 else time.monotonic() + float(args.seconds)
    try:
        while True:
            if t_end is not None and time.monotonic() >= t_end:
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[BDWidth] stop", flush=True)
    finally:
        snap = mon.snapshot()
        for line in build_bdwidth_status_lines(mon):
            print(line)
        mon.stop()
        if snap.enabled and snap.samples <= 0 and snap.mode != "mock":
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
