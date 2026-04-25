#!/usr/bin/env python3
"""Generate Harman-targeted miniDSP PEQ, crossover, and FIR files from REW exports."""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

array = np.array
poly_roots = np.roots

FS_FIR = 96000.0
LEFT_TAPS = 1022
RIGHT_TAPS = 1022
SUB_TAPS = 2040
EPS = 1.0e-12


@dataclass
class Measurement:
    name: str
    delay_ms: float | None
    freq_hz: np.ndarray
    spl_db: np.ndarray
    phase_deg: np.ndarray


@dataclass
class ImpulseInfo:
    name: str
    sample_rate_hz: float
    peak_index: int
    response_length: int
    start_time_s: float


@dataclass
class Biquad:
    b0: float
    b1: float
    b2: float
    a1: float
    a2: float
    internal_a1: float
    internal_a2: float
    type: str
    freq_hz: float
    gain_db: float
    q: float

    def as_minidsp_dict(self) -> dict[str, float | str]:
        return {
            "type": self.type,
            "freq_hz": self.freq_hz,
            "gain_db": self.gain_db,
            "q": self.q,
            "b0": self.b0,
            "b1": self.b1,
            "b2": self.b2,
            "a1": self.a1,
            "a2": self.a2,
            "stable": bool(np.all(np.abs(np.roots([1.0, self.internal_a1, self.internal_a2])) < 1.0)),
        }


def parse_number(token: str) -> float:
    return float(token.replace(",", ""))


def parse_rew_spl(path: Path) -> Measurement:
    name = path.stem
    delay_ms: float | None = None
    rows: list[tuple[float, float, float]] = []
    for line in path.read_text(errors="ignore").splitlines():
        if line.startswith("* Measurement:"):
            name = line.split(":", 1)[1].strip()
        if "Delay " in line:
            match = re.search(r"Delay\s+([-+0-9.]+)\s+ms", line)
            if match:
                delay_ms = float(match.group(1))
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            rows.append((parse_number(parts[0]), parse_number(parts[1]), parse_number(parts[2])))
        except ValueError:
            continue
    if not rows:
        raise ValueError(f"No SPL rows found in {path}")
    data = np.asarray(rows, dtype=float)
    return Measurement(name, delay_ms, data[:, 0], data[:, 1], data[:, 2])


def parse_impulse_info(path: Path) -> ImpulseInfo:
    name = path.stem
    peak_index = 0
    response_length = 0
    sample_interval_s = 0.0
    start_time_s = 0.0
    for line in path.read_text(errors="ignore").splitlines()[:30]:
        if line.startswith("* Measurement:"):
            name = line.split(":", 1)[1].strip()
        elif "// Peak index" in line:
            peak_index = int(line.split("//", 1)[0].strip())
        elif "// Response length" in line:
            response_length = int(line.split("//", 1)[0].strip())
        elif "// Sample interval" in line:
            sample_interval_s = float(line.split("//", 1)[0].strip())
        elif "// Start time" in line:
            start_time_s = float(line.split("//", 1)[0].strip())
    if sample_interval_s <= 0:
        raise ValueError(f"No sample interval found in {path}")
    return ImpulseInfo(name, 1.0 / sample_interval_s, peak_index, response_length, start_time_s)


def parse_target(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows: list[tuple[float, float]] = []
    for line in path.read_text(errors="ignore").splitlines():
        if not line or line.startswith("*") or line.startswith('"'):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            rows.append((parse_number(parts[0]), parse_number(parts[1])))
        except ValueError:
            continue
    if not rows:
        raise ValueError(f"No target rows found in {path}")
    data = np.asarray(rows, dtype=float)
    order = np.argsort(data[:, 0])
    return data[order, 0], data[order, 1]


def extrapolate_target_to_zero(freq_hz: np.ndarray, spl_db: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if len(freq_hz) == 0 or freq_hz[0] == 0.0:
        return freq_hz, spl_db
    return np.concatenate(([0.0], freq_hz)), np.concatenate(([spl_db[0]], spl_db))


def group_name(name: str) -> str:
    return re.sub(r"\s+\d+$", "", name).strip()


def load_measurement_groups(spl_dir: Path) -> dict[str, list[Measurement]]:
    groups: dict[str, list[Measurement]] = {}
    for path in sorted(spl_dir.glob("*.txt")):
        measurement = parse_rew_spl(path)
        groups.setdefault(group_name(measurement.name), []).append(measurement)
    return groups


def complex_average(measurements: list[Measurement]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not measurements:
        raise ValueError("No measurements to average")
    freq = measurements[0].freq_hz
    for measurement in measurements[1:]:
        if len(measurement.freq_hz) != len(freq) or np.max(np.abs(measurement.freq_hz - freq)) > 1.0e-6:
            raise ValueError("Measurement frequency grids do not match")
    complex_rows = []
    for measurement in measurements:
        mag = np.power(10.0, measurement.spl_db / 20.0)
        phase = np.unwrap(np.deg2rad(measurement.phase_deg))
        complex_rows.append(mag * np.exp(1j * phase))
    avg = np.mean(np.vstack(complex_rows), axis=0)
    mag_db = 20.0 * np.log10(np.maximum(np.abs(avg), EPS))
    phase_deg = np.rad2deg(np.unwrap(np.angle(avg)))
    return freq.copy(), mag_db, phase_deg


def interpolate_log(freq_src: np.ndarray, value_src: np.ndarray, freq_dst: np.ndarray) -> np.ndarray:
    src = np.maximum(freq_src, 1.0e-6)
    dst = np.maximum(freq_dst, 1.0e-6)
    return np.interp(np.log10(dst), np.log10(src), value_src, left=value_src[0], right=value_src[-1])


def rbj_biquad(filter_type: str, freq_hz: float, q: float, fs_hz: float, gain_db: float = 0.0) -> Biquad:
    w0 = 2.0 * math.pi * freq_hz / fs_hz
    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)
    alpha = sin_w0 / (2.0 * q)
    a0 = 1.0 + alpha
    if filter_type == "PK":
        amp = math.pow(10.0, gain_db / 40.0)
        alpha = sin_w0 / (2.0 * q)
        b0 = 1.0 + alpha * amp
        b1 = -2.0 * cos_w0
        b2 = 1.0 - alpha * amp
        a0 = 1.0 + alpha / amp
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha / amp
    elif filter_type == "LP":
        b0 = (1.0 - cos_w0) / 2.0
        b1 = 1.0 - cos_w0
        b2 = (1.0 - cos_w0) / 2.0
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif filter_type == "HP":
        b0 = (1.0 + cos_w0) / 2.0
        b1 = -(1.0 + cos_w0)
        b2 = (1.0 + cos_w0) / 2.0
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    else:
        raise ValueError(f"Unsupported biquad type {filter_type}")
    b0, b1, b2, a1, a2 = [x / a0 for x in (b0, b1, b2, a1, a2)]
    return Biquad(b0, b1, b2, -a1, -a2, a1, a2, filter_type, freq_hz, gain_db, q)


def peaking_biquad(freq_hz: float, gain_db: float, q: float, fs_hz: float) -> Biquad:
    return rbj_biquad("PK", freq_hz, q, fs_hz, gain_db)


def biquad_response(biquad: Biquad, freq_hz: np.ndarray, fs_hz: float) -> np.ndarray:
    omega = 2.0 * np.pi * freq_hz / fs_hz
    z1 = np.exp(-1j * omega)
    z2 = np.exp(-2j * omega)
    numerator = biquad.b0 + biquad.b1 * z1 + biquad.b2 * z2
    denominator = 1.0 + biquad.internal_a1 * z1 + biquad.internal_a2 * z2
    return numerator / np.maximum(np.abs(denominator), EPS) * np.exp(1j * np.angle(denominator) * -1.0)


def cascade_response(biquads: list[Biquad], freq_hz: np.ndarray, fs_hz: float) -> np.ndarray:
    response = np.ones_like(freq_hz, dtype=complex)
    for biquad in biquads:
        response *= biquad_response(biquad, freq_hz, fs_hz)
    return response


def lr4_filters(kind: str, freq_hz: float, fs_hz: float) -> list[Biquad]:
    return [rbj_biquad(kind, freq_hz, 1.0 / math.sqrt(2.0), fs_hz), rbj_biquad(kind, freq_hz, 1.0 / math.sqrt(2.0), fs_hz)]


def complex_from_mag_phase(mag_db: np.ndarray, phase_deg: np.ndarray) -> np.ndarray:
    return np.power(10.0, mag_db / 20.0) * np.exp(1j * np.deg2rad(phase_deg))


def db_from_complex(values: np.ndarray) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(np.abs(values), EPS))


def optimize_crossover(
    freq_hz: np.ndarray,
    left_complex: np.ndarray,
    right_complex: np.ndarray,
    sub_complex: np.ndarray,
    target_db: np.ndarray,
) -> dict[str, float]:
    mask = (freq_hz >= 25.0) & (freq_hz <= 300.0)
    f = freq_hz[mask]
    target = target_db[mask]
    left = left_complex[mask]
    right = right_complex[mask]
    sub = sub_complex[mask]
    best: dict[str, float] | None = None
    for crossover_hz in np.arange(40.0, 181.0, 5.0):
        hp = cascade_response(lr4_filters("HP", crossover_hz, FS_FIR), f, FS_FIR)
        lp = cascade_response(lr4_filters("LP", crossover_hz, FS_FIR), f, FS_FIR)
        main_l = left * hp
        main_r = right * hp
        sub_base = sub * lp
        for sub_gain_db in np.arange(-9.0, 9.01, 0.5):
            gain = math.pow(10.0, sub_gain_db / 20.0)
            for sub_delay_ms in np.arange(-8.0, 8.001, 0.25):
                delay_phase = np.exp(-1j * 2.0 * np.pi * f * sub_delay_ms / 1000.0)
                sub_delayed = sub_base * gain * delay_phase
                sum_l = main_l + sub_delayed
                sum_r = main_r + sub_delayed
                err_l = db_from_complex(sum_l) - target
                err_r = db_from_complex(sum_r) - target
                max_l = np.maximum(db_from_complex(main_l), db_from_complex(sub_delayed))
                max_r = np.maximum(db_from_complex(main_r), db_from_complex(sub_delayed))
                cancel_l = np.maximum(0.0, max_l - db_from_complex(sum_l) - 3.0)
                cancel_r = np.maximum(0.0, max_r - db_from_complex(sum_r) - 3.0)
                score = float(np.mean(err_l**2 + err_r**2) + 4.0 * np.mean(cancel_l**2 + cancel_r**2))
                if best is None or score < best["score"]:
                    best = {
                        "crossover_hz": float(crossover_hz),
                        "sub_gain_db": float(sub_gain_db),
                        "sub_delay_ms": float(sub_delay_ms),
                        "score": score,
                    }
    assert best is not None
    return best


def smooth_log(freq_hz: np.ndarray, values: np.ndarray, width_octaves: float) -> np.ndarray:
    log_f = np.log2(np.maximum(freq_hz, 1.0e-6))
    half = width_octaves / 2.0
    order = np.argsort(log_f)
    sorted_log = log_f[order]
    sorted_values = values[order]
    cumulative = np.concatenate(([0.0], np.cumsum(sorted_values)))
    smoothed_sorted = np.empty_like(sorted_values)
    for idx, center in enumerate(sorted_log):
        left = int(np.searchsorted(sorted_log, center - half, side="left"))
        right = int(np.searchsorted(sorted_log, center + half, side="right"))
        smoothed_sorted[idx] = (cumulative[right] - cumulative[left]) / max(right - left, 1)
    smoothed = np.empty_like(values)
    smoothed[order] = smoothed_sorted
    return smoothed


def design_peq(
    freq_hz: np.ndarray,
    measured_db: np.ndarray,
    target_db: np.ndarray,
    channel: str,
    max_filters: int,
) -> list[Biquad]:
    if channel == "sub":
        active = (freq_hz >= 15.0) & (freq_hz <= 250.0)
    else:
        active = (freq_hz >= 20.0) & (freq_hz <= 16000.0)
    f = freq_hz[active]
    residual = smooth_log(f, target_db[active] - measured_db[active], 1.0 / 6.0)
    filters: list[Biquad] = []
    available = np.ones_like(f, dtype=bool)
    log_f = np.log2(np.maximum(f, 1.0e-6))
    for _ in range(max_filters):
        if not np.any(available):
            break
        candidate_error = np.where(available, np.abs(residual), -np.inf)
        idx = int(np.argmax(candidate_error))
        wanted = float(np.clip(residual[idx], -12.0, 6.0))
        if abs(wanted) < 1.0:
            break
        center = float(f[idx])
        sign = 1.0 if wanted >= 0 else -1.0
        threshold = abs(wanted) * 0.5
        left = idx
        right = idx
        while left > 0 and sign * residual[left] > threshold:
            left -= 1
        while right < len(f) - 1 and sign * residual[right] > threshold:
            right += 1
        low = max(float(f[left]), center / 4.0)
        high = min(float(f[right]), center * 4.0)
        bandwidth_oct = max(math.log2(high / low), 0.15)
        q = float(np.clip(1.0 / (2.0 * math.sinh(math.log(2.0) * bandwidth_oct / 2.0)), 0.35, 8.0))
        biquad = peaking_biquad(center, wanted, q, FS_FIR)
        filters.append(biquad)
        response_db = db_from_complex(biquad_response(biquad, f, FS_FIR))
        residual -= response_db
        available &= np.abs(log_f - math.log2(max(center, 1.0e-6))) > 0.25
    return filters


def make_residual_fir(freq_hz: np.ndarray, correction_db: np.ndarray, taps: int, fs_hz: float) -> np.ndarray:
    n_bins = 32768
    grid = np.linspace(0.0, fs_hz / 2.0, n_bins + 1)
    correction = np.interp(grid, freq_hz, correction_db, left=correction_db[0], right=0.0)
    correction = np.clip(correction, -12.0, 6.0)
    mag = np.power(10.0, correction / 20.0)
    full = np.concatenate([mag, mag[-2:0:-1]])
    impulse = np.fft.ifft(full).real
    centered = np.fft.fftshift(impulse)
    center = len(centered) // 2
    start = center - taps // 2
    fir = centered[start : start + taps].copy()
    window = np.hamming(taps)
    fir *= window
    dc = np.sum(fir)
    desired_dc = mag[0]
    if abs(dc) > EPS:
        fir *= desired_dc / dc
    peak = float(np.max(np.abs(fir)))
    if peak > 0.98:
        fir *= 0.98 / peak
    return fir.astype(np.float64)


def fir_response(taps: np.ndarray, freq_hz: np.ndarray, fs_hz: float) -> np.ndarray:
    n_fft = 131072
    response = np.fft.rfft(taps, n=n_fft)
    bins = np.fft.rfftfreq(n_fft, d=1.0 / fs_hz)
    real = np.interp(freq_hz, bins, response.real, left=response.real[0], right=response.real[-1])
    imag = np.interp(freq_hz, bins, response.imag, left=response.imag[0], right=response.imag[-1])
    return real + 1j * imag


def rms_error(response_db: np.ndarray, target_db: np.ndarray, freq_hz: np.ndarray, low: float, high: float) -> float:
    mask = (freq_hz >= low) & (freq_hz <= high)
    return float(np.sqrt(np.mean((response_db[mask] - target_db[mask]) ** 2)))


def write_biquads(path: Path, biquads: list[Biquad]) -> None:
    lines: list[str] = []
    for idx, bq in enumerate(biquads, 1):
        lines.extend(
            [
                f"biquad{idx},",
                f"b0={bq.b0:.15g},",
                f"b1={bq.b1:.15g},",
                f"b2={bq.b2:.15g},",
                f"a1={bq.a1:.15g},",
                f"a2={bq.a2:.15g},",
            ]
        )
    path.write_text("\n".join(lines) + "\n")


def write_readable_peq(path: Path, biquads: list[Biquad]) -> None:
    rows = ["# type freq_hz gain_db q"]
    for bq in biquads:
        rows.append(f"{bq.type} {bq.freq_hz:.4f} {bq.gain_db:+.3f} {bq.q:.4f}")
    path.write_text("\n".join(rows) + "\n")


def write_fir_manual(path: Path, taps: np.ndarray) -> None:
    path.write_text("\n".join(f"b{idx} = {tap:.12e}" for idx, tap in enumerate(taps)) + "\n")


def write_fir_bin(path: Path, taps: np.ndarray) -> None:
    path.write_bytes(struct.pack("<" + "f" * len(taps), *[float(x) for x in taps]))


def median_delay(groups: dict[str, list[Measurement]], name: str) -> float:
    values = [m.delay_ms for m in groups[name] if m.delay_ms is not None]
    return float(np.median(values)) if values else 0.0


def build_filters(root: Path, output: Path) -> dict:
    groups = load_measurement_groups(root / "SPL")
    required = {"L", "R", "L + Sub", "R + Sub", "Sub Only"}
    missing = sorted(required - set(groups))
    if missing:
        raise ValueError(f"Missing measurement groups: {', '.join(missing)}")

    target_freq, target_shape = parse_target(root / "Harman Target.txt")
    target_freq, target_shape = extrapolate_target_to_zero(target_freq, target_shape)

    freq, left_db, left_phase = complex_average(groups["L"])
    _, right_db, right_phase = complex_average(groups["R"])
    _, sub_db, sub_phase = complex_average(groups["Sub Only"])
    _, left_sum_db, _ = complex_average(groups["L + Sub"])
    _, right_sum_db, _ = complex_average(groups["R + Sub"])

    target_interp = interpolate_log(target_freq, target_shape, freq)
    anchor_mask = (freq >= 500.0) & (freq <= 2000.0)
    target_offset = float(np.median(np.concatenate([left_db[anchor_mask], right_db[anchor_mask]]) - np.tile(target_interp[anchor_mask], 2)))
    target_abs = target_interp + target_offset

    left_complex = complex_from_mag_phase(left_db, left_phase)
    right_complex = complex_from_mag_phase(right_db, right_phase)
    sub_complex = complex_from_mag_phase(sub_db, sub_phase)
    crossover = optimize_crossover(freq, left_complex, right_complex, sub_complex, target_abs)

    hp = cascade_response(lr4_filters("HP", crossover["crossover_hz"], FS_FIR), freq, FS_FIR)
    lp = cascade_response(lr4_filters("LP", crossover["crossover_hz"], FS_FIR), freq, FS_FIR)
    sub_gain = math.pow(10.0, crossover["sub_gain_db"] / 20.0)
    sub_delay_phase = np.exp(-1j * 2.0 * np.pi * freq * crossover["sub_delay_ms"] / 1000.0)

    left_xo_db = db_from_complex(left_complex * hp)
    right_xo_db = db_from_complex(right_complex * hp)
    sub_xo_db = db_from_complex(sub_complex * lp * sub_gain * sub_delay_phase)

    peq_left = design_peq(freq, left_xo_db, target_abs, "left", 10)
    peq_right = design_peq(freq, right_xo_db, target_abs, "right", 10)
    peq_sub = design_peq(freq, sub_xo_db, target_abs, "sub", 8)

    left_after_peq = left_xo_db + db_from_complex(cascade_response(peq_left, freq, FS_FIR))
    right_after_peq = right_xo_db + db_from_complex(cascade_response(peq_right, freq, FS_FIR))
    sub_after_peq = sub_xo_db + db_from_complex(cascade_response(peq_sub, freq, FS_FIR))

    fir_left = make_residual_fir(freq, smooth_log(freq, target_abs - left_after_peq, 1.0 / 3.0), LEFT_TAPS, FS_FIR)
    fir_right = make_residual_fir(freq, smooth_log(freq, target_abs - right_after_peq, 1.0 / 3.0), RIGHT_TAPS, FS_FIR)
    fir_sub = make_residual_fir(freq, smooth_log(freq, target_abs - sub_after_peq, 1.0 / 3.0), SUB_TAPS, FS_FIR)

    mean_left = float(np.median(left_after_peq[(freq >= 500.0) & (freq <= 2000.0)] - target_abs[(freq >= 500.0) & (freq <= 2000.0)]))
    mean_right = float(np.median(right_after_peq[(freq >= 500.0) & (freq <= 2000.0)] - target_abs[(freq >= 500.0) & (freq <= 2000.0)]))
    mean_sub = float(np.median(sub_after_peq[(freq >= 30.0) & (freq <= 100.0)] - target_abs[(freq >= 30.0) & (freq <= 100.0)]))

    if crossover["sub_delay_ms"] < 0:
        delays = {"left": -crossover["sub_delay_ms"], "right": -crossover["sub_delay_ms"], "sub": 0.0}
    else:
        delays = {"left": 0.0, "right": 0.0, "sub": crossover["sub_delay_ms"]}

    gains = {
        "left": -mean_left,
        "right": -mean_right,
        "sub": crossover["sub_gain_db"] - mean_sub,
    }

    left_final = (
        left_complex
        * hp
        * cascade_response(peq_left, freq, FS_FIR)
        * fir_response(fir_left, freq, FS_FIR)
        * math.pow(10.0, gains["left"] / 20.0)
        * np.exp(-1j * 2.0 * np.pi * freq * delays["left"] / 1000.0)
    )
    right_final = (
        right_complex
        * hp
        * cascade_response(peq_right, freq, FS_FIR)
        * fir_response(fir_right, freq, FS_FIR)
        * math.pow(10.0, gains["right"] / 20.0)
        * np.exp(-1j * 2.0 * np.pi * freq * delays["right"] / 1000.0)
    )
    sub_final = (
        sub_complex
        * lp
        * cascade_response(peq_sub, freq, FS_FIR)
        * fir_response(fir_sub, freq, FS_FIR)
        * math.pow(10.0, gains["sub"] / 20.0)
        * np.exp(-1j * 2.0 * np.pi * freq * delays["sub"] / 1000.0)
    )
    left_plus_sub_final_db = db_from_complex(left_final + sub_final)
    right_plus_sub_final_db = db_from_complex(right_final + sub_final)
    validation_errors = {
        "left_plus_sub_rms_20_20000_db": rms_error(left_plus_sub_final_db, target_abs, freq, 20.0, 20000.0),
        "right_plus_sub_rms_20_20000_db": rms_error(right_plus_sub_final_db, target_abs, freq, 20.0, 20000.0),
        "left_plus_sub_rms_20_300_db": rms_error(left_plus_sub_final_db, target_abs, freq, 20.0, 300.0),
        "right_plus_sub_rms_20_300_db": rms_error(right_plus_sub_final_db, target_abs, freq, 20.0, 300.0),
        "left_plus_sub_rms_30_120_db": rms_error(left_plus_sub_final_db, target_abs, freq, 30.0, 120.0),
        "right_plus_sub_rms_30_120_db": rms_error(right_plus_sub_final_db, target_abs, freq, 30.0, 120.0),
    }

    output.mkdir(parents=True, exist_ok=True)
    write_biquads(output / "peq_left.txt", peq_left)
    write_biquads(output / "peq_right.txt", peq_right)
    write_biquads(output / "peq_sub.txt", peq_sub)
    write_readable_peq(output / "peq_left_readable.txt", peq_left)
    write_readable_peq(output / "peq_right_readable.txt", peq_right)
    write_readable_peq(output / "peq_sub_readable.txt", peq_sub)
    write_biquads(output / "crossover_left.txt", lr4_filters("HP", crossover["crossover_hz"], FS_FIR))
    write_biquads(output / "crossover_right.txt", lr4_filters("HP", crossover["crossover_hz"], FS_FIR))
    write_biquads(output / "crossover_sub.txt", lr4_filters("LP", crossover["crossover_hz"], FS_FIR))

    for name, taps in [("left", fir_left), ("right", fir_right), ("sub", fir_sub)]:
        tap_count = len(taps)
        write_fir_manual(output / f"fir_{name}_96k_{tap_count}taps_manual.txt", taps)
        write_fir_manual(output / f"fir_{name}_96k_{tap_count}taps_raw.txt", taps)
        write_fir_bin(output / f"fir_{name}_96k_{tap_count}taps.bin", taps)

    validation = np.column_stack(
        [
            freq,
            target_abs,
            left_db,
            right_db,
            sub_db,
            left_sum_db,
            right_sum_db,
            left_plus_sub_final_db,
            right_plus_sub_final_db,
        ]
    )
    np.savetxt(
        output / "validation_response.csv",
        validation,
        delimiter=",",
        header="freq_hz,target_db,left_db,right_db,sub_db,left_plus_sub_measured_db,right_plus_sub_measured_db,left_plus_sub_predicted_final_db,right_plus_sub_predicted_final_db",
        comments="",
    )

    impulse_infos = [parse_impulse_info(path) for path in sorted((root / "Impulse").glob("*.txt"))]
    metadata = {
        "source_mdat": str(root / "All Measurements (center).mdat"),
        "mic_correction_policy": "Trusted REW exports; Microphone Correction.txt was not applied again.",
        "target_file": str(root / "Harman Target.txt"),
        "target_extrapolation": "Added 0 Hz point holding first Harman target SPL constant to DC.",
        "sample_rates": sorted({round(info.sample_rate_hz, 6) for info in impulse_infos}),
        "tap_allocation": {"left": LEFT_TAPS, "right": RIGHT_TAPS, "sub": SUB_TAPS, "unused_output": 6, "total": LEFT_TAPS + RIGHT_TAPS + SUB_TAPS + 6},
        "crossover": crossover,
        "delays_ms": delays,
        "gains_db": gains,
        "rew_delay_medians_ms": {
            "left": median_delay(groups, "L"),
            "right": median_delay(groups, "R"),
            "sub": median_delay(groups, "Sub Only"),
            "left_plus_sub": median_delay(groups, "L + Sub"),
            "right_plus_sub": median_delay(groups, "R + Sub"),
        },
        "validation_errors": validation_errors,
        "filters": {
            "left": [bq.as_minidsp_dict() for bq in peq_left],
            "right": [bq.as_minidsp_dict() for bq in peq_right],
            "sub": [bq.as_minidsp_dict() for bq in peq_sub],
        },
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    summary = [
        "miniDSP 2x4 HD settings summary",
        "",
        "Routing:",
        "Left: Input 1",
        "Right: Input 2",
        "Sub: Input 1 + Input 2",
        "",
        f"Crossover: LR4 / 24 dB/oct at {crossover['crossover_hz']:.1f} Hz",
        "Sub high-pass: none requested; no protective HPF inserted",
        "",
        "Output trims:",
        f"Left: delay {delays['left']:.3f} ms, gain {gains['left']:+.3f} dB",
        f"Right: delay {delays['right']:.3f} ms, gain {gains['right']:+.3f} dB",
        f"Sub: delay {delays['sub']:.3f} ms, gain {gains['sub']:+.3f} dB",
        "",
        "FIR imports:",
        f"Left: fir_left_96k_{LEFT_TAPS}taps.bin / fir_left_96k_{LEFT_TAPS}taps_manual.txt",
        f"Right: fir_right_96k_{RIGHT_TAPS}taps.bin / fir_right_96k_{RIGHT_TAPS}taps_manual.txt",
        f"Sub: fir_sub_96k_{SUB_TAPS}taps.bin / fir_sub_96k_{SUB_TAPS}taps_manual.txt",
        "",
        "PEQ imports:",
        "Left: peq_left.txt",
        "Right: peq_right.txt",
        "Sub: peq_sub.txt",
        "",
        "Crossover advanced-mode imports:",
        "Left: crossover_left.txt",
        "Right: crossover_right.txt",
        "Sub: crossover_sub.txt",
    ]
    (output / "settings_summary.txt").write_text("\n".join(summary) + "\n")

    report = [
        "# Fresh Harman Filter Report",
        "",
        f"- Selected crossover: {crossover['crossover_hz']:.1f} Hz LR4",
        f"- Search score: {crossover['score']:.4f}",
        f"- Relative sub delay from search: {crossover['sub_delay_ms']:+.3f} ms",
        f"- Relative sub gain from search: {crossover['sub_gain_db']:+.3f} dB",
        "- Target extrapolation: first Harman point held constant to 0 Hz.",
        "- Sub high-pass: none inserted.",
        f"- Tap allocation: L {LEFT_TAPS}, R {RIGHT_TAPS}, Sub {SUB_TAPS}, unused output 6.",
        f"- Predicted L+Sub RMS error 20 Hz-20 kHz: {validation_errors['left_plus_sub_rms_20_20000_db']:.3f} dB",
        f"- Predicted R+Sub RMS error 20 Hz-20 kHz: {validation_errors['right_plus_sub_rms_20_20000_db']:.3f} dB",
        f"- Predicted L+Sub RMS error 30 Hz-120 Hz: {validation_errors['left_plus_sub_rms_30_120_db']:.3f} dB",
        f"- Predicted R+Sub RMS error 30 Hz-120 Hz: {validation_errors['right_plus_sub_rms_30_120_db']:.3f} dB",
    ]
    (output / "report.md").write_text("\n".join(report) + "\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path.cwd() / "Output_fresh_harman_center")
    args = parser.parse_args()
    metadata = build_filters(args.root, args.output)
    print(json.dumps({"output": str(args.output), "crossover": metadata["crossover"], "delays_ms": metadata["delays_ms"], "gains_db": metadata["gains_db"]}, indent=2))


if __name__ == "__main__":
    main()
