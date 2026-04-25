#!/usr/bin/env python3
"""Generate miniDSP-style PEQ, crossover, delay, gain, and FIR files.

The script is intentionally self-contained and only depends on NumPy so it can
run in the bundled Codex Python runtime. It reads the REW text exports in the
SPL and Impulse folders, averages the repeated measurements, optimizes the
subwoofer crossover alignment, and writes a reproducible Output folder.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np


OUT_FS = 96_000.0
INPUT_FS_EXPECTED = 48_000.0
MAX_PEQ_FILTERS = 10
FIR_TAPS = {"left": 1022, "right": 1022, "sub": 2040}
TOTAL_TAPS_AVAILABLE = 4096
OUTPUT4_RESERVED_TAPS = 6
EPS = 1e-12


@dataclass
class SPLMeasurement:
    name: str
    path: Path
    freq: np.ndarray
    spl_db: np.ndarray
    phase_deg: np.ndarray
    delay_ms: float | None


@dataclass
class ImpulseMeasurement:
    name: str
    path: Path
    peak_value: float
    peak_index: int
    length: int
    sample_interval: float
    start_time: float
    samples: np.ndarray

    @property
    def sample_rate(self) -> float:
        return 1.0 / self.sample_interval

    @property
    def peak_time(self) -> float:
        return self.start_time + self.peak_index * self.sample_interval


@dataclass
class Biquad:
    kind: str
    freq: float
    gain_db: float
    q: float
    b0: float
    b1: float
    b2: float
    a1: float
    a2: float
    enabled: bool = True

    def response(self, freq: np.ndarray, fs: float = OUT_FS) -> np.ndarray:
        w = 2.0 * np.pi * freq / fs
        z1 = np.exp(-1j * w)
        z2 = np.exp(-2j * w)
        return (self.b0 + self.b1 * z1 + self.b2 * z2) / (
            1.0 + self.a1 * z1 + self.a2 * z2
        )

    def is_stable(self) -> bool:
        roots = np.roots([1.0, self.a1, self.a2])
        return bool(np.all(np.abs(roots) < 1.0))


@dataclass
class ChannelResult:
    key: str
    title: str
    peq: List[Biquad]
    fir: np.ndarray
    gain_db: float
    delay_ms: float
    fir_taps: int
    rms_before_db: float
    rms_after_db: float
    max_boost_db: float
    max_cut_db: float


def clean_number(token: str) -> float:
    return float(token.replace(",", ""))


def parse_delay_ms(line: str) -> float | None:
    match = re.search(r"Delay\s+([-+]?\d+(?:\.\d+)?)\s+ms", line)
    return float(match.group(1)) if match else None


def parse_spl_file(path: Path) -> SPLMeasurement:
    freq: List[float] = []
    spl: List[float] = []
    phase: List[float] = []
    name = path.stem
    delay_ms = None

    for line in path.read_text(errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("*"):
            if stripped.startswith("* Measurement:"):
                name = stripped.split(":", 1)[1].strip()
            if "Delay " in stripped:
                delay_ms = parse_delay_ms(stripped)
            continue
        parts = stripped.split()
        if len(parts) < 3:
            continue
        try:
            freq.append(clean_number(parts[0]))
            spl.append(clean_number(parts[1]))
            phase.append(clean_number(parts[2]))
        except ValueError:
            continue

    if not freq:
        raise ValueError(f"No SPL rows found in {path}")
    return SPLMeasurement(
        name=name,
        path=path,
        freq=np.asarray(freq, dtype=np.float64),
        spl_db=np.asarray(spl, dtype=np.float64),
        phase_deg=np.asarray(phase, dtype=np.float64),
        delay_ms=delay_ms,
    )


def parse_impulse_file(path: Path) -> ImpulseMeasurement:
    name = path.stem
    peak_value = None
    peak_index = None
    length = None
    sample_interval = None
    start_time = None
    samples: List[float] = []
    in_data = False

    for line in path.read_text(errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("* Measurement:"):
            name = stripped.split(":", 1)[1].strip()
            continue
        if stripped.startswith("* Data start"):
            in_data = True
            continue
        if stripped.startswith("*"):
            continue
        if in_data:
            try:
                samples.append(float(stripped.split()[0]))
            except ValueError:
                pass
            continue

        value = stripped.split("//", 1)[0].strip()
        label = stripped.split("//", 1)[1].strip() if "//" in stripped else ""
        if not value:
            continue
        if label.startswith("Peak value"):
            peak_value = float(value)
        elif label.startswith("Peak index"):
            peak_index = int(value)
        elif label.startswith("Response length"):
            length = int(value)
        elif label.startswith("Sample interval"):
            sample_interval = float(value)
        elif label.startswith("Start time"):
            start_time = float(value)

    missing = [
        label
        for label, value in [
            ("peak value", peak_value),
            ("peak index", peak_index),
            ("length", length),
            ("sample interval", sample_interval),
            ("start time", start_time),
        ]
        if value is None
    ]
    if missing:
        raise ValueError(f"{path} missing impulse metadata: {', '.join(missing)}")
    arr = np.asarray(samples, dtype=np.float64)
    if arr.size != int(length):
        raise ValueError(f"{path} expected {length} samples, got {arr.size}")
    return ImpulseMeasurement(
        name=name,
        path=path,
        peak_value=float(peak_value),
        peak_index=int(peak_index),
        length=int(length),
        sample_interval=float(sample_interval),
        start_time=float(start_time),
        samples=arr,
    )


def parse_curve_file(path: Path, min_cols: int = 2) -> Tuple[np.ndarray, np.ndarray]:
    freq: List[float] = []
    value: List[float] = []
    for line in path.read_text(errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("*") or stripped.startswith('"'):
            continue
        parts = stripped.split()
        if len(parts) < min_cols:
            continue
        try:
            freq.append(clean_number(parts[0]))
            value.append(clean_number(parts[1]))
        except ValueError:
            continue
    if not freq:
        raise ValueError(f"No curve rows found in {path}")
    return np.asarray(freq, dtype=np.float64), np.asarray(value, dtype=np.float64)


def parse_distortion_file(path: Path) -> Dict[str, np.ndarray] | None:
    if not path.exists():
        return None
    rows: List[List[float]] = []
    measurement = ""
    for line in path.read_text(errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("* Measurement:"):
            measurement = stripped.split(":", 1)[1].strip()
            continue
        if not stripped or stripped.startswith("*"):
            continue
        parts = stripped.split()
        if len(parts) < 4:
            continue
        try:
            rows.append([clean_number(p) for p in parts[:4]])
        except ValueError:
            continue
    if not rows:
        return None
    arr = np.asarray(rows, dtype=np.float64)
    return {
        "measurement": np.asarray([measurement]),
        "freq": arr[:, 0],
        "fundamental_db": arr[:, 1],
        "thd_pct": arr[:, 2],
        "noise_pct": arr[:, 3],
    }


def group_names(prefix: str) -> List[str]:
    return [f"{prefix} {idx}" for idx in range(1, 6)]


def load_measurements(root: Path) -> Tuple[Dict[str, SPLMeasurement], Dict[str, ImpulseMeasurement]]:
    spl = {m.name: m for m in sorted((root / "SPL").glob("*.txt")) for m in [parse_spl_file(m)]}
    impulse = {
        m.name: m
        for m in sorted((root / "Impulse").glob("*.txt"))
        for m in [parse_impulse_file(m)]
    }
    return spl, impulse


def assert_measurement_set(
    spl: Dict[str, SPLMeasurement], impulse: Dict[str, ImpulseMeasurement]
) -> List[str]:
    required = (
        group_names("L")
        + group_names("R")
        + group_names("L + Sub")
        + group_names("R + Sub")
        + group_names("Sub Only")
    )
    notes: List[str] = []
    missing_spl = [name for name in required if name not in spl]
    missing_ir = [name for name in required if name not in impulse]
    if missing_spl:
        raise ValueError(f"Missing SPL measurements: {', '.join(missing_spl)}")
    if missing_ir:
        raise ValueError(f"Missing impulse measurements: {', '.join(missing_ir)}")

    ref_freq = spl[required[0]].freq
    ref_rows = ref_freq.size
    for name in required:
        if spl[name].freq.size != ref_rows or not np.allclose(spl[name].freq, ref_freq):
            raise ValueError(f"SPL frequency grid mismatch: {name}")
        ir = impulse[name]
        if ir.length != 131072:
            raise ValueError(f"Unexpected impulse length for {name}: {ir.length}")
        if abs(ir.sample_rate - INPUT_FS_EXPECTED) > 1e-3:
            raise ValueError(f"Unexpected impulse sample rate for {name}: {ir.sample_rate:.3f}")
    notes.append(f"Validated {len(required)} SPL files on a {ref_rows}-point shared grid.")
    notes.append(f"Validated {len(required)} impulse files at {INPUT_FS_EXPECTED:.0f} Hz, 131072 samples each.")
    return notes


def complex_from_spl(
    meas: SPLMeasurement,
    mic_freq: np.ndarray,
    mic_db: np.ndarray,
    mic_cal_policy: str = "trust-exports",
) -> np.ndarray:
    if mic_cal_policy not in {"trust-exports", "apply", "compare"}:
        raise ValueError(f"Unsupported mic calibration policy: {mic_cal_policy}")
    if mic_cal_policy == "apply":
        cal = np.interp(meas.freq, mic_freq, mic_db, left=mic_db[0], right=mic_db[-1])
    else:
        cal = np.zeros_like(meas.freq)
    mag = 10.0 ** ((meas.spl_db + cal) / 20.0)
    phase = np.deg2rad(meas.phase_deg)
    return mag * np.exp(1j * phase)


def average_complex(responses: Sequence[np.ndarray]) -> np.ndarray:
    return np.mean(np.vstack(responses), axis=0)


def average_impulse(measurements: Sequence[ImpulseMeasurement]) -> np.ndarray:
    # Align by peak index before averaging to avoid a one-sample export offset.
    target_peak = int(round(np.median([m.peak_index for m in measurements])))
    aligned = []
    for m in measurements:
        shift = target_peak - m.peak_index
        aligned.append(np.roll(m.samples, shift))
    return np.mean(np.vstack(aligned), axis=0)


def db(x: np.ndarray) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(np.abs(x), EPS))


def rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values)))) if values.size else float("nan")


def smooth_log(values: np.ndarray, freq: np.ndarray, width_oct: float = 1 / 6) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    freq = np.asarray(freq, dtype=np.float64)
    logf = np.log2(np.maximum(freq, 1e-6))
    half = width_oct / 2.0
    order = np.argsort(logf)
    sorted_log = logf[order]
    sorted_values = values[order]
    prefix = np.r_[0.0, np.cumsum(sorted_values)]
    left = np.searchsorted(sorted_log, sorted_log - half, side="left")
    right = np.searchsorted(sorted_log, sorted_log + half, side="right")
    counts = np.maximum(right - left, 1)
    sorted_out = (prefix[right] - prefix[left]) / counts
    out = np.empty_like(sorted_out)
    out[order] = sorted_out
    return out


def interp_curve(freq: np.ndarray, curve_freq: np.ndarray, curve_db: np.ndarray) -> np.ndarray:
    return np.interp(freq, curve_freq, curve_db, left=curve_db[0], right=curve_db[-1])


def biquad_peak(freq: float, gain_db: float, q: float, fs: float = OUT_FS) -> Biquad:
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * freq / fs
    alpha = np.sin(w0) / (2.0 * q)
    cosw = np.cos(w0)
    b0 = 1.0 + alpha * a
    b1 = -2.0 * cosw
    b2 = 1.0 - alpha * a
    a0 = 1.0 + alpha / a
    a1 = -2.0 * cosw
    a2 = 1.0 - alpha / a
    return Biquad(
        kind="PK",
        freq=float(freq),
        gain_db=float(gain_db),
        q=float(q),
        b0=float(b0 / a0),
        b1=float(b1 / a0),
        b2=float(b2 / a0),
        a1=float(a1 / a0),
        a2=float(a2 / a0),
    )


def biquad_lowpass(freq: float, q: float = math.sqrt(0.5), fs: float = OUT_FS) -> Biquad:
    w0 = 2.0 * np.pi * freq / fs
    alpha = np.sin(w0) / (2.0 * q)
    cosw = np.cos(w0)
    b0 = (1.0 - cosw) / 2.0
    b1 = 1.0 - cosw
    b2 = (1.0 - cosw) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cosw
    a2 = 1.0 - alpha
    return Biquad("LP", freq, 0.0, q, b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def biquad_highpass(freq: float, q: float = math.sqrt(0.5), fs: float = OUT_FS) -> Biquad:
    w0 = 2.0 * np.pi * freq / fs
    alpha = np.sin(w0) / (2.0 * q)
    cosw = np.cos(w0)
    b0 = (1.0 + cosw) / 2.0
    b1 = -(1.0 + cosw)
    b2 = (1.0 + cosw) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cosw
    a2 = 1.0 - alpha
    return Biquad("HP", freq, 0.0, q, b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def cascade_response(filters: Sequence[Biquad], freq: np.ndarray, fs: float = OUT_FS) -> np.ndarray:
    response = np.ones_like(freq, dtype=np.complex128)
    for filt in filters:
        if filt.enabled:
            response *= filt.response(freq, fs)
    return response


def lr4_filters(freq_hz: float, kind: str) -> List[Biquad]:
    if kind == "hp":
        return [biquad_highpass(freq_hz), biquad_highpass(freq_hz)]
    if kind == "lp":
        return [biquad_lowpass(freq_hz), biquad_lowpass(freq_hz)]
    raise ValueError(kind)


def target_shift(
    freq: np.ndarray, target_db: np.ndarray, left: np.ndarray, right: np.ndarray
) -> float:
    # The supplied Harman/HATS target carries a strong bass rise. Anchor the
    # absolute level to the upper mid/treble region so the bass shelf remains
    # intentional instead of forcing the whole target down to the vocal band.
    mask = (freq >= 2000.0) & (freq <= 10_000.0)
    measured = 0.5 * (db(left[mask]) + db(right[mask]))
    return float(np.mean(measured - target_db[mask]))


def choose_channel_gain(
    freq: np.ndarray,
    response: np.ndarray,
    target_db: np.ndarray,
    mask: np.ndarray,
    headroom_db: float = -2.0,
) -> float:
    diff = target_db[mask] - db(response[mask])
    # Median avoids chasing narrow nulls. Add a little attenuation for EQ/FIR headroom.
    return float(np.clip(np.median(diff) + headroom_db, -12.0, 6.0))


def optimize_crossover(
    freq: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
    sub: np.ndarray,
    lsum_measured: np.ndarray,
    rsum_measured: np.ndarray,
    target_db: np.ndarray,
    min_crossover_hz: int = 50,
    max_crossover_hz: int = 140,
    crossover_preference_hz: float | None = None,
    sub_highpass_hz: float = 20.0,
) -> Dict[str, float]:
    mask = (freq >= 50.0) & (freq <= 160.0)
    mask_indices = np.flatnonzero(mask)
    # The exported grid is very dense. A 2 Hz-ish grid is plenty for crossover
    # scoring and keeps the optimizer fast enough to rerun while iterating.
    decimated = mask_indices[:: max(1, int(round(2.0 / np.median(np.diff(freq[mask])))))]
    if decimated.size < 24:
        decimated = mask_indices
    best: Dict[str, float] | None = None
    candidates: List[Dict[str, float]] = []
    fc_cache: Dict[float, Dict[str, np.ndarray]] = {}

    def score_candidate(fc: float, delay_ms: float, gain_db: float) -> float:
        idx = decimated
        if fc not in fc_cache:
            hp = cascade_response(lr4_filters(float(fc), "hp"), freq)
            lp = cascade_response(lr4_filters(float(fc), "lp"), freq)
            sub_hp_filters = [biquad_highpass(sub_highpass_hz)] if sub_highpass_hz > 0 else []
            sub_hp = cascade_response(sub_hp_filters, freq)
            fc_cache[fc] = {
                "xsub": (sub * lp * sub_hp)[idx],
                "xl": (left * hp)[idx],
                "xr": (right * hp)[idx],
                "lsum": lsum_measured[idx],
                "rsum": rsum_measured[idx],
                "target": target_db[idx],
                "freq": freq[idx],
            }
        cached = fc_cache[fc]
        phase = np.exp(-1j * 2.0 * np.pi * cached["freq"] * (delay_ms / 1000.0))
        gain = 10.0 ** (gain_db / 20.0)
        delayed_sub = cached["xsub"] * phase * gain
        pl = cached["xl"] + delayed_sub
        pr = cached["xr"] + delayed_sub
        target = cached["target"]
        err_target = np.r_[db(pl) - target, db(pr) - target]
        err_lr = db(pl) - db(pr)
        err_validation = np.r_[
            db(pl) - db(cached["lsum"]),
            db(pr) - db(cached["rsum"]),
        ]
        cancel_penalty = 0.0
        for combined, main in [(pl, cached["xl"]), (pr, cached["xr"])]:
            delta = db(combined) - db(main)
            cancel_penalty += float(np.mean(np.square(np.minimum(delta + 1.0, 0.0))))
        score = (
            rms(err_target)
            + 0.35 * rms(err_lr)
            + 0.25 * rms(err_validation)
            + 0.4 * math.sqrt(cancel_penalty)
        )
        if crossover_preference_hz is not None:
            # Soft preference, not a hard override: one octave away costs 1 dB
            # in score, enough to break ties without hiding real summation wins.
            score += abs(math.log2(fc / crossover_preference_hz))
        return score

    def consider(fc: float, delay_ms: float, gain_db: float) -> None:
        nonlocal best
        score = score_candidate(fc, delay_ms, gain_db)
        candidates.append(
            {
                "score": float(score),
                "crossover_hz": float(fc),
                "sub_delay_ms": float(delay_ms),
                "sub_gain_db": float(gain_db),
            }
        )
        if best is None or score < best["score"]:
            best = {
                "score": float(score),
                "crossover_hz": float(fc),
                "sub_delay_ms": float(delay_ms),
                "sub_gain_db": float(gain_db),
            }

    start = int(min_crossover_hz)
    stop = int(max_crossover_hz)
    for fc in range(start, stop + 1, 2):
        for delay_ms in np.arange(-4.0, 12.0001, 0.5):
            for gain_db in np.arange(-10.0, 8.0001, 1.0):
                consider(float(fc), float(delay_ms), float(gain_db))

    assert best is not None
    coarse = dict(best)
    for fc in np.arange(coarse["crossover_hz"] - 3.0, coarse["crossover_hz"] + 3.0001, 0.5):
        if fc < float(start) or fc > float(stop):
            continue
        for delay_ms in np.arange(coarse["sub_delay_ms"] - 0.4, coarse["sub_delay_ms"] + 0.4001, 0.025):
            for gain_db in np.arange(coarse["sub_gain_db"] - 0.75, coarse["sub_gain_db"] + 0.7501, 0.125):
                consider(float(fc), float(delay_ms), float(gain_db))
    assert best is not None
    best["top_candidates"] = sorted(candidates, key=lambda row: row["score"])[:50]
    return best


def find_peak_filters(
    freq: np.ndarray,
    response: np.ndarray,
    target_db: np.ndarray,
    correction_mask: np.ndarray,
    max_filters: int = MAX_PEQ_FILTERS,
) -> List[Biquad]:
    filters: List[Biquad] = []
    current = response.copy()
    used_ranges: List[Tuple[float, float]] = []

    for _ in range(max_filters):
        error = db(current) - target_db
        smooth_error = smooth_log(error, freq, width_oct=1 / 5)
        masked = np.where(correction_mask, smooth_error, 0.0)
        cut_idx = int(np.argmax(masked))
        cut_amount = masked[cut_idx]

        dip = np.where(correction_mask, -smooth_error, 0.0)
        boost_idx = int(np.argmax(dip))
        boost_amount = dip[boost_idx]

        if cut_amount >= 2.0 and cut_amount >= boost_amount * 0.65:
            idx = cut_idx
            gain = -float(np.clip(cut_amount * 0.75, 1.0, 9.0))
        elif boost_amount >= 3.0:
            idx = boost_idx
            # Boost gently and avoid trying to fill nulls.
            gain = float(np.clip(boost_amount * 0.35, 0.5, 3.0))
        else:
            break

        centre = float(freq[idx])
        if any(lo <= centre <= hi for lo, hi in used_ranges):
            masked_window = correction_mask & (
                (freq < centre / (2.0 ** 0.25)) | (freq > centre * (2.0 ** 0.25))
            )
            if np.count_nonzero(masked_window) < 10:
                break
            correction_mask = masked_window
            continue

        abs_error = abs(smooth_error[idx])
        threshold = max(abs_error * 0.5, 1.5)
        low_idx = idx
        high_idx = idx
        while low_idx > 0 and correction_mask[low_idx] and abs(smooth_error[low_idx]) > threshold:
            low_idx -= 1
        while (
            high_idx < freq.size - 1
            and correction_mask[high_idx]
            and abs(smooth_error[high_idx]) > threshold
        ):
            high_idx += 1
        low_f = max(float(freq[low_idx]), centre / 3.0)
        high_f = min(float(freq[high_idx]), centre * 3.0)
        bandwidth_oct = max(math.log2(high_f / low_f), 0.15)
        q = float(np.clip(1.0 / bandwidth_oct, 0.35, 8.0))
        filt = biquad_peak(centre, gain, q)
        if not filt.is_stable():
            break
        filters.append(filt)
        current *= filt.response(freq)
        used_ranges.append((centre / (2.0 ** 0.2), centre * (2.0 ** 0.2)))

    return filters


def make_fir(
    freq: np.ndarray,
    residual_db: np.ndarray,
    taps: int,
    correction_mask: np.ndarray,
    fs: float = OUT_FS,
) -> np.ndarray:
    nfft = 65536
    grid = np.linspace(0.0, fs / 2.0, nfft // 2 + 1)
    safe_residual = np.zeros_like(freq)
    safe_residual[correction_mask] = residual_db[correction_mask]
    safe_residual = smooth_log(safe_residual, np.maximum(freq, 1.0), width_oct=1 / 3)
    safe_residual = np.clip(safe_residual, -10.0, 3.0)

    interp_db = np.interp(grid, freq, safe_residual, left=0.0, right=0.0)
    # Blend correction to flat at the correction band edges to reduce ripple.
    if np.any(correction_mask):
        lo = float(freq[np.argmax(correction_mask)])
        hi = float(freq[len(correction_mask) - np.argmax(correction_mask[::-1]) - 1])
        low_fade = np.clip((grid - lo * 0.65) / max(lo * 0.35, 1.0), 0.0, 1.0)
        high_fade = np.clip((hi * 1.25 - grid) / max(hi * 0.25, 1.0), 0.0, 1.0)
        interp_db *= low_fade * high_fade

    mag = 10.0 ** (interp_db / 20.0)
    zero_phase = np.fft.irfft(mag, nfft)
    centred = np.fft.fftshift(zero_phase)
    mid = centred.size // 2
    start = mid - taps // 2
    fir = centred[start : start + taps].copy()
    fir *= np.hamming(taps)

    # Preserve unity at 1 kHz for mains and 60 Hz-ish for sub-like filters by
    # normalizing DC only if the sum is wildly off.
    peak = float(np.max(np.abs(fir)))
    if peak > 1.0:
        fir /= peak
    return fir.astype(np.float64)


def fir_response(fir: np.ndarray, freq: np.ndarray, fs: float = OUT_FS) -> np.ndarray:
    n = np.arange(fir.size)
    return np.exp(-1j * 2.0 * np.pi * np.outer(freq / fs, n)) @ fir


def fir_group_delay_ms(taps: int, fs: float = OUT_FS) -> float:
    return (taps - 1) / (2.0 * fs) * 1000.0


def translate_relative_delay_to_outputs(
    sub_relative_delay_ms: float,
    main_taps: int = FIR_TAPS["left"],
    sub_taps: int = FIR_TAPS["sub"],
    fs: float = OUT_FS,
) -> Dict[str, float]:
    fir_sub_minus_main_ms = fir_group_delay_ms(sub_taps, fs) - fir_group_delay_ms(main_taps, fs)
    needed_output_sub_minus_main_ms = sub_relative_delay_ms - fir_sub_minus_main_ms
    delays = {"left": 0.0, "right": 0.0, "sub": 0.0}
    if needed_output_sub_minus_main_ms >= 0:
        delays["sub"] = needed_output_sub_minus_main_ms
    else:
        delays["left"] = -needed_output_sub_minus_main_ms
        delays["right"] = -needed_output_sub_minus_main_ms
    return delays


def apply_output_delay(response: np.ndarray, freq: np.ndarray, delay_ms: float) -> np.ndarray:
    return response * np.exp(-1j * 2.0 * np.pi * freq * (delay_ms / 1000.0))


def correction_masks(
    freq: np.ndarray, crossover_hz: float, sub_low_freq: float = 20.0
) -> Dict[str, np.ndarray]:
    return {
        "left": (freq >= max(crossover_hz * 0.85, 60.0)) & (freq <= 18_000.0),
        "right": (freq >= max(crossover_hz * 0.85, 60.0)) & (freq <= 18_000.0),
        "sub": (freq >= sub_low_freq) & (freq <= min(crossover_hz * 1.8, 180.0)),
    }


def write_peq_file(path: Path, title: str, filters: Sequence[Biquad]) -> None:
    lines = [
        f"# {title} PEQ filters",
        "# miniDSP-style peaking filters plus normalized biquad coefficients",
        "# Biquad convention: y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]",
        "",
    ]
    if not filters:
        lines.append("# No PEQ filters generated.")
    for idx, filt in enumerate(filters, start=1):
        lines.append(
            f"Filter {idx}: ON {filt.kind} Fc {filt.freq:.3f} Hz Gain {filt.gain_db:+.3f} dB Q {filt.q:.4f}"
        )
        lines.append(
            "  biquad "
            f"b0={filt.b0:.12g} b1={filt.b1:.12g} b2={filt.b2:.12g} "
            f"a1={filt.a1:.12g} a2={filt.a2:.12g}"
        )
    path.write_text("\n".join(lines) + "\n")


def write_minidsp_biquad_file(path: Path, filters: Sequence[Biquad]) -> None:
    """Write Device Console advanced biquad import format.

    miniDSP's text format uses a feedback sign opposite our normalized transfer
    function denominator: H(z) = (b0 + b1 z^-1 + b2 z^-2)/(1 + a1 z^-1 + a2 z^-2).
    Therefore the exported a1/a2 values are sign-flipped for miniDSP.
    """
    tokens: List[str] = []
    for idx, filt in enumerate(filters, start=1):
        tokens.extend(
            [
                f"biquad{idx}",
                f"b0={filt.b0:.15g}",
                f"b1={filt.b1:.15g}",
                f"b2={filt.b2:.15g}",
                f"a1={-filt.a1:.15g}",
                f"a2={-filt.a2:.15g}",
            ]
        )
    lines = []
    for idx, token in enumerate(tokens):
        comma = "," if idx < len(tokens) - 1 else ""
        lines.append(f"{token}{comma}")
    path.write_text("\n".join(lines) + "\n")


def write_minidsp_fir_manual_file(path: Path, fir: np.ndarray) -> None:
    lines = [f"b{idx} = {coef:.12e}" for idx, coef in enumerate(fir)]
    path.write_text("\n".join(lines) + "\n")


def write_fir_file(path: Path, fir: np.ndarray) -> None:
    path.write_text("\n".join(f"{coef:.12e}" for coef in fir) + "\n")


def write_fir_binary_file(path: Path, fir: np.ndarray) -> None:
    np.asarray(fir, dtype="<f4").tofile(path)


def response_csv(
    path: Path,
    freq: np.ndarray,
    columns: Dict[str, np.ndarray],
) -> None:
    header = ["freq_hz"] + list(columns.keys())
    lines = [",".join(header)]
    for idx in range(freq.size):
        row = [f"{freq[idx]:.6f}"] + [f"{columns[name][idx]:.6f}" for name in columns]
        lines.append(",".join(row))
    path.write_text("\n".join(lines) + "\n")


def write_rows_csv(path: Path, rows: Sequence[Dict[str, float]]) -> None:
    if not rows:
        path.write_text("\n")
        return
    header = list(rows[0].keys())
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(f"{row[name]:.6f}" for name in header))
    path.write_text("\n".join(lines) + "\n")


def summarize_filters(filters: Sequence[Biquad]) -> Tuple[float, float]:
    gains = np.asarray([f.gain_db for f in filters], dtype=np.float64)
    if gains.size == 0:
        return 0.0, 0.0
    return float(np.max(np.maximum(gains, 0.0))), float(np.min(np.minimum(gains, 0.0)))


def build_report(
    out: Path,
    notes: Sequence[str],
    crossover: Dict[str, float],
    target_file: Path,
    sub_highpass_hz: float,
    sub_low_freq: float,
    target_offset_db: float,
    target_absolute: bool,
    delays: Dict[str, float],
    gains: Dict[str, float],
    results: Sequence[ChannelResult],
    validations: Dict[str, float],
    distortion_note: str,
    mic_cal_policy: str,
    mic_compare_note: str,
    boundary_warning: str,
    midbass_rows: Sequence[Dict[str, float]],
) -> None:
    lines: List[str] = []
    lines.append("# miniDSP 2x4 HD Filter Report")
    lines.append("")
    lines.append("## Recommended Settings")
    lines.append("")
    lines.append(f"- Sample rate: 96 kHz")
    lines.append(f"- Target file: `{target_file.name}`")
    lines.append(f"- Crossover: LR4 / 24 dB/oct at {crossover['crossover_hz']:.0f} Hz")
    if sub_highpass_hz > 0:
        lines.append(f"- Sub protective high-pass: {sub_highpass_hz:g} Hz, 2nd-order Butterworth")
    else:
        lines.append("- Sub protective high-pass: none")
    lines.append(f"- Sub correction lower limit: {sub_low_freq:g} Hz")
    lines.append(f"- Sub relative gain from crossover search: {crossover['sub_gain_db']:+.2f} dB")
    lines.append(f"- Sub relative delay from crossover search: {crossover['sub_delay_ms']:+.2f} ms")
    if boundary_warning:
        lines.append(f"- Crossover search warning: {boundary_warning}")
    lines.append(f"- Mic calibration policy: {mic_cal_policy}. {mic_compare_note}")
    lines.append(
        f"- FIR group delay compensation: Sub FIR is "
        f"{fir_group_delay_ms(FIR_TAPS['sub']) - fir_group_delay_ms(FIR_TAPS['left']):.3f} ms "
        "longer than the Left/Right FIRs, included in the output delay settings below."
    )
    lines.append("")
    lines.append("| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |")
    lines.append("|---|---:|---:|---:|---:|")
    for result in results:
        lines.append(
            f"| {result.title} | {delays[result.key]:.3f} | {gains[result.key]:+.3f} | "
            f"{result.fir_taps} | {len(result.peq)} |"
        )
    lines.append("")
    lines.append("## Crossover Blocks")
    lines.append("")
    lines.append(f"- Left: high-pass LR4 at {crossover['crossover_hz']:.0f} Hz.")
    lines.append(f"- Right: high-pass LR4 at {crossover['crossover_hz']:.0f} Hz.")
    if sub_highpass_hz > 0:
        lines.append(
            f"- Sub: low-pass LR4 at {crossover['crossover_hz']:.0f} Hz plus {sub_highpass_hz:g} Hz high-pass."
        )
    else:
        lines.append(f"- Sub: low-pass LR4 at {crossover['crossover_hz']:.0f} Hz with no high-pass.")
    lines.append("")
    lines.append("## PEQ Summary")
    lines.append("")
    for result in results:
        lines.append(f"### {result.title}")
        if not result.peq:
            lines.append("")
            lines.append("No PEQ filters generated.")
            lines.append("")
            continue
        lines.append("")
        lines.append("| # | Type | Fc (Hz) | Gain (dB) | Q |")
        lines.append("|---:|---|---:|---:|---:|")
        for idx, filt in enumerate(result.peq, start=1):
            lines.append(
                f"| {idx} | {filt.kind} | {filt.freq:.2f} | {filt.gain_db:+.2f} | {filt.q:.3f} |"
            )
        lines.append("")
    lines.append("## Validation")
    lines.append("")
    for note in notes:
        lines.append(f"- {note}")
    lines.append(
        f"- Target curve shifted by {target_offset_db:+.2f} dB to match the measured 2-10 kHz average; "
        "this shapes the response without forcing an arbitrary playback SPL."
    )
    if target_absolute:
        lines.append("- Absolute target mode was requested, so no target-level shift was applied.")
    lines.append(
        f"- Tap budget check: Left {FIR_TAPS['left']} + Right {FIR_TAPS['right']} + "
        f"Sub {FIR_TAPS['sub']} + Output 4 reserve {OUTPUT4_RESERVED_TAPS} = "
        f"{sum(FIR_TAPS.values()) + OUTPUT4_RESERVED_TAPS} of {TOTAL_TAPS_AVAILABLE} total taps."
    )
    lines.append(f"- Predicted Left+Sub RMS error, 50-160 Hz: {validations['left_sum_rms_db']:.2f} dB.")
    lines.append(f"- Predicted Right+Sub RMS error, 50-160 Hz: {validations['right_sum_rms_db']:.2f} dB.")
    lines.append(f"- Predicted L/R mismatch after correction, 80-10000 Hz: {validations['lr_mismatch_rms_db']:.2f} dB.")
    lines.append(
        f"- Worst crossover-region cancellation indicator: {validations['worst_cancellation_db']:.2f} dB "
        f"at {validations['worst_cancellation_hz']:.2f} Hz."
    )
    for result in results:
        lines.append(
            f"- {result.title}: RMS target error {result.rms_before_db:.2f} dB before correction, "
            f"{result.rms_after_db:.2f} dB after PEQ+FIR in its correction band."
        )
    lines.append(f"- {distortion_note}")
    lines.append("")
    lines.append("## Midbass Alignment")
    lines.append("")
    lines.append("| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|")
    for row in midbass_rows:
        lines.append(
            f"| {row['freq_hz']:.2f} | {row['final_left_plus_sub_db']:.2f} | "
            f"{row['final_right_plus_sub_db']:.2f} | {row['measured_left_plus_sub_db']:.2f} | "
            f"{row['measured_right_plus_sub_db']:.2f} | {row['left_cancellation_db']:.2f} | "
            f"{row['right_cancellation_db']:.2f} |"
        )
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append("- `peq_left.txt`, `peq_right.txt`, `peq_sub.txt`: PEQ filters and biquad coefficients.")
    lines.append("- `peq_left_readable.txt`, `peq_right_readable.txt`, `peq_sub_readable.txt`: human-readable PEQ notes.")
    lines.append("- `crossover_left.txt`, `crossover_right.txt`, `crossover_sub.txt`: advanced-mode crossover biquads.")
    lines.append(
        f"- `fir_left_96k_{FIR_TAPS['left']}taps.bin`, `fir_right_96k_{FIR_TAPS['right']}taps.bin`, "
        f"`fir_sub_96k_{FIR_TAPS['sub']}taps.bin`: FIR File Mode binary float32 coefficients."
    )
    lines.append(
        f"- `fir_left_96k_{FIR_TAPS['left']}taps_manual.txt`, "
        f"`fir_right_96k_{FIR_TAPS['right']}taps_manual.txt`, "
        f"`fir_sub_96k_{FIR_TAPS['sub']}taps_manual.txt`: FIR Manual Mode text coefficients."
    )
    lines.append(
        f"- `fir_left_96k_{FIR_TAPS['left']}taps_raw.txt`, "
        f"`fir_right_96k_{FIR_TAPS['right']}taps_raw.txt`, "
        f"`fir_sub_96k_{FIR_TAPS['sub']}taps_raw.txt`: raw coefficient lists for inspection."
    )
    lines.append("- `settings_summary.txt`: concise miniDSP entry values.")
    lines.append("- `validation_response.csv`: compact frequency-response validation data.")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- These filters are derived from exported in-room measurements. Verify at low volume first, then remeasure through the miniDSP."
    )
    lines.append(
        "- The FIR filters are linear-phase residual magnitude corrections; output delay handles the main timing alignment."
    )
    if mic_cal_policy == "apply":
        lines.append("- Microphone Correction.txt was applied to the exported SPL data.")
    else:
        lines.append("- Microphone Correction.txt was not reapplied to the exported SPL data.")
    out.joinpath("report.md").write_text("\n".join(lines) + "\n")


def write_settings_summary(
    out: Path,
    crossover: Dict[str, float],
    delays: Dict[str, float],
    gains: Dict[str, float],
    results: Sequence[ChannelResult],
    sub_highpass_hz: float,
    sub_low_freq: float,
) -> None:
    lines = [
        "miniDSP 2x4 HD settings summary",
        "",
        "Routing:",
        "Left: Input 1",
        "Right: Input 2",
        "Sub: Input 1 + Input 2",
        "",
        f"Crossover: LR4 / 24 dB/oct at {crossover['crossover_hz']:.0f} Hz",
        (
            f"Sub high-pass: {sub_highpass_hz:g} Hz, 2nd-order Butterworth"
            if sub_highpass_hz > 0
            else "Sub high-pass: none"
        ),
        f"Sub correction lower limit: {sub_low_freq:g} Hz",
        "",
        "Output trims:",
    ]
    for result in results:
        lines.append(f"{result.title}: delay {delays[result.key]:.3f} ms, gain {gains[result.key]:+.3f} dB")
    lines.extend(
        [
            "",
            "FIR group delay compensation:",
            f"Sub FIR group delay is {fir_group_delay_ms(FIR_TAPS['sub']):.3f} ms.",
            f"Left/Right FIR group delay is {fir_group_delay_ms(FIR_TAPS['left']):.3f} ms.",
            "The output delays above include this difference.",
            "",
            "FIR imports:",
            "File Mode binary:",
            f"Left: fir_left_96k_{FIR_TAPS['left']}taps.bin",
            f"Right: fir_right_96k_{FIR_TAPS['right']}taps.bin",
            f"Sub: fir_sub_96k_{FIR_TAPS['sub']}taps.bin",
            "Manual Mode text:",
            f"Left: fir_left_96k_{FIR_TAPS['left']}taps_manual.txt",
            f"Right: fir_right_96k_{FIR_TAPS['right']}taps_manual.txt",
            f"Sub: fir_sub_96k_{FIR_TAPS['sub']}taps_manual.txt",
            "",
            "PEQ imports:",
            "Left: peq_left.txt",
            "Right: peq_right.txt",
            "Sub: peq_sub.txt",
            "",
            "Crossover advanced-mode imports, if you do not use Basic LR4 controls:",
            "Left: crossover_left.txt",
            "Right: crossover_right.txt",
            "Sub: crossover_sub.txt",
        ]
    )
    out.joinpath("settings_summary.txt").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--target-file",
        type=Path,
        default=None,
        help="REW target text file. Defaults to 'Harman Audio Test System Target.txt'.",
    )
    parser.add_argument("--min-crossover", type=int, default=50)
    parser.add_argument("--max-crossover", type=int, default=140)
    parser.add_argument(
        "--prefer-crossover",
        type=float,
        default=None,
        help="Optional soft crossover preference in Hz; the optimizer may still choose another frequency.",
    )
    parser.add_argument(
        "--sub-low-freq",
        type=float,
        default=20.0,
        help="Lowest frequency the sub correction is allowed to target.",
    )
    parser.add_argument(
        "--sub-highpass-hz",
        type=float,
        default=20.0,
        help="Sub protective high-pass frequency. Use 0 to omit it.",
    )
    parser.add_argument(
        "--absolute-target",
        action="store_true",
        help="Use the target file's absolute SPL instead of shifting it to the measurement level.",
    )
    parser.add_argument(
        "--mic-cal-policy",
        choices=("trust-exports", "apply", "compare"),
        default="trust-exports",
        help=(
            "How to handle Microphone Correction.txt. 'trust-exports' assumes REW already applied it, "
            "'apply' preserves the legacy behavior, and 'compare' reports the difference but generates "
            "filters from trusted exports."
        ),
    )
    args = parser.parse_args()

    root = args.root.resolve()
    out = (args.output or root / "Output").resolve()
    out.mkdir(parents=True, exist_ok=True)

    spl, impulse = load_measurements(root)
    validation_notes = assert_measurement_set(spl, impulse)
    mic_freq, mic_db = parse_curve_file(root / "Microphone Correction.txt")
    generation_mic_policy = "trust-exports" if args.mic_cal_policy == "compare" else args.mic_cal_policy
    mic_samples = []
    for sample_hz in (20.0, 50.0, 60.0, 100.0, 1000.0, 10000.0):
        sample_db = float(np.interp(sample_hz, mic_freq, mic_db, left=mic_db[0], right=mic_db[-1]))
        mic_samples.append(f"{sample_hz:g} Hz {sample_db:+.2f} dB")
    if args.mic_cal_policy == "apply":
        mic_compare_note = "Applied Microphone Correction.txt to SPL exports."
    elif args.mic_cal_policy == "compare":
        mic_compare_note = (
            "Generated final filters without reapplying mic correction; correction samples for comparison: "
            + ", ".join(mic_samples)
            + "."
        )
    else:
        mic_compare_note = (
            "Trusted REW SPL exports as already calibrated; correction samples not applied: "
            + ", ".join(mic_samples)
            + "."
        )
    target_path = args.target_file or root / "Harman Audio Test System Target.txt"
    if not target_path.is_absolute():
        target_path = root / target_path
    target_freq, target_raw_db = parse_curve_file(target_path, min_cols=2)
    distortion = parse_distortion_file(root / "Distortion" / "Distortion.txt")

    freq = spl["L 1"].freq
    target_db = interp_curve(freq, target_freq, target_raw_db)

    groups = {
        "left": group_names("L"),
        "right": group_names("R"),
        "sub": group_names("Sub Only"),
        "left_sum": group_names("L + Sub"),
        "right_sum": group_names("R + Sub"),
    }
    avg = {
        key: average_complex(
            [
                complex_from_spl(
                    spl[name],
                    mic_freq,
                    mic_db,
                    mic_cal_policy=generation_mic_policy,
                )
                for name in names
            ]
        )
        for key, names in groups.items()
    }
    avg_ir = {
        key: average_impulse([impulse[name] for name in names])
        for key, names in groups.items()
    }

    shift = 0.0 if args.absolute_target else target_shift(freq, target_db, avg["left"], avg["right"])
    shifted_target_db = target_db + shift

    crossover = optimize_crossover(
        freq=freq,
        left=avg["left"],
        right=avg["right"],
        sub=avg["sub"],
        lsum_measured=avg["left_sum"],
        rsum_measured=avg["right_sum"],
        target_db=shifted_target_db,
        min_crossover_hz=args.min_crossover,
        max_crossover_hz=args.max_crossover,
        crossover_preference_hz=args.prefer_crossover,
        sub_highpass_hz=args.sub_highpass_hz,
    )
    fc = crossover["crossover_hz"]
    masks = correction_masks(freq, fc, sub_low_freq=args.sub_low_freq)

    hp = cascade_response(lr4_filters(fc, "hp"), freq)
    lp = cascade_response(lr4_filters(fc, "lp"), freq)
    sub_hp_filters = [biquad_highpass(args.sub_highpass_hz)] if args.sub_highpass_hz > 0 else []
    sub_hp = cascade_response(sub_hp_filters, freq)
    xover = {"left": hp, "right": hp, "sub": lp * sub_hp}

    # Translate the acoustic sub-vs-main delay target into output delay fields.
    # The FIR files are causal linear-phase filters, so unequal tap counts add
    # unequal group delays. The sub FIR is longer than the mains FIR, and that
    # extra FIR delay must be compensated in the output delays.
    delays = translate_relative_delay_to_outputs(
        crossover["sub_delay_ms"],
        main_taps=FIR_TAPS["left"],
        sub_taps=FIR_TAPS["sub"],
        fs=OUT_FS,
    )

    # The right speaker's measured timing is close enough to left that forcing a
    # right-only delay from the noisy in-room impulse would add false precision.
    gains = {
        "left": choose_channel_gain(freq, avg["left"] * hp, shifted_target_db, masks["left"]),
        "right": choose_channel_gain(freq, avg["right"] * hp, shifted_target_db, masks["right"]),
        "sub": crossover["sub_gain_db"]
        + choose_channel_gain(freq, avg["sub"] * lp * sub_hp, shifted_target_db, masks["sub"], headroom_db=-3.0),
    }

    results: List[ChannelResult] = []
    corrected: Dict[str, np.ndarray] = {}
    final_channels: Dict[str, np.ndarray] = {}
    for key, title in [("left", "Left"), ("right", "Right"), ("sub", "Sub")]:
        base = avg[key] * xover[key] * 10.0 ** (gains[key] / 20.0)
        peq = find_peak_filters(freq, base, shifted_target_db, masks[key], MAX_PEQ_FILTERS)
        peq_resp = cascade_response(peq, freq)
        after_peq = base * peq_resp
        residual = shifted_target_db - db(after_peq)
        fir = make_fir(freq, residual, FIR_TAPS[key], masks[key])
        f_resp = fir_response(fir, freq)
        after_all = after_peq * f_resp
        corrected[key] = after_all
        final_channels[key] = apply_output_delay(after_all, freq, delays[key])
        max_boost, max_cut = summarize_filters(peq)
        before_err = db(base[masks[key]]) - shifted_target_db[masks[key]]
        after_err = db(after_all[masks[key]]) - shifted_target_db[masks[key]]
        results.append(
            ChannelResult(
                key=key,
                title=title,
                peq=peq,
                fir=fir,
                gain_db=gains[key],
                delay_ms=delays[key],
                fir_taps=FIR_TAPS[key],
                rms_before_db=rms(before_err),
                rms_after_db=rms(after_err),
                max_boost_db=max_boost,
                max_cut_db=max_cut,
            )
        )

    # Predicted combined response after the actual miniDSP output delays.
    pred_lsum = final_channels["left"] + final_channels["sub"]
    pred_rsum = final_channels["right"] + final_channels["sub"]
    sum_mask = (freq >= 50.0) & (freq <= 160.0)
    lr_mask = (freq >= 80.0) & (freq <= 10_000.0)
    left_cancellation = db(pred_lsum) - np.maximum(db(final_channels["left"]), db(final_channels["sub"]))
    right_cancellation = db(pred_rsum) - np.maximum(db(final_channels["right"]), db(final_channels["sub"]))
    worst_left_idx = int(np.argmin(np.where(sum_mask, left_cancellation, np.inf)))
    worst_right_idx = int(np.argmin(np.where(sum_mask, right_cancellation, np.inf)))
    if left_cancellation[worst_left_idx] <= right_cancellation[worst_right_idx]:
        worst_cancellation_db = float(left_cancellation[worst_left_idx])
        worst_cancellation_hz = float(freq[worst_left_idx])
    else:
        worst_cancellation_db = float(right_cancellation[worst_right_idx])
        worst_cancellation_hz = float(freq[worst_right_idx])
    validations = {
        "left_sum_rms_db": rms(db(pred_lsum[sum_mask]) - db(avg["left_sum"][sum_mask])),
        "right_sum_rms_db": rms(db(pred_rsum[sum_mask]) - db(avg["right_sum"][sum_mask])),
        "lr_mismatch_rms_db": rms(db(final_channels["left"][lr_mask]) - db(final_channels["right"][lr_mask])),
        "worst_cancellation_db": worst_cancellation_db,
        "worst_cancellation_hz": worst_cancellation_hz,
    }
    midbass_rows: List[Dict[str, float]] = []
    for sample_hz in (50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0, 140.0):
        idx = int(np.argmin(np.abs(freq - sample_hz)))
        midbass_rows.append(
            {
                "freq_hz": float(freq[idx]),
                "target_db": float(shifted_target_db[idx]),
                "final_left_db": float(db(final_channels["left"])[idx]),
                "final_right_db": float(db(final_channels["right"])[idx]),
                "final_sub_db": float(db(final_channels["sub"])[idx]),
                "final_left_plus_sub_db": float(db(pred_lsum)[idx]),
                "final_right_plus_sub_db": float(db(pred_rsum)[idx]),
                "measured_left_plus_sub_db": float(db(avg["left_sum"])[idx]),
                "measured_right_plus_sub_db": float(db(avg["right_sum"])[idx]),
                "left_cancellation_db": float(left_cancellation[idx]),
                "right_cancellation_db": float(right_cancellation[idx]),
            }
        )
    if abs(fc - float(args.min_crossover)) < 1e-9:
        boundary_warning = f"selected crossover is at the minimum search bound ({args.min_crossover} Hz)"
    elif abs(fc - float(args.max_crossover)) < 1e-9:
        boundary_warning = f"selected crossover is at the maximum search bound ({args.max_crossover} Hz)"
    else:
        boundary_warning = ""

    distortion_note = "No distortion file was found."
    if distortion is not None:
        d_freq = distortion["freq"]
        thd = distortion["thd_pct"]
        low = (d_freq >= 20.0) & (d_freq <= 120.0)
        below_25 = (d_freq >= 10.0) & (d_freq < 25.0)
        distortion_note = (
            "Distortion guardrail used from Distortion.txt "
            f"({str(distortion['measurement'][0])}); median THD 20-120 Hz is "
            f"{float(np.median(thd[low])):.2f}%"
        )
        if np.any(below_25) and float(np.max(thd[below_25])) > 5.0:
            distortion_note += ", so boosts below 25 Hz were avoided."
        else:
            distortion_note += "."

    # Write files.
    crossover_filters = {
        "left": lr4_filters(fc, "hp"),
        "right": lr4_filters(fc, "hp"),
        "sub": lr4_filters(fc, "lp") + sub_hp_filters,
    }
    for result in results:
        write_peq_file(out / f"peq_{result.key}_readable.txt", result.title, result.peq)
        write_minidsp_biquad_file(out / f"peq_{result.key}.txt", result.peq)
        write_minidsp_biquad_file(out / f"crossover_{result.key}.txt", crossover_filters[result.key])
        write_fir_file(out / f"fir_{result.key}_96k_{result.fir_taps}taps_raw.txt", result.fir)
        write_minidsp_fir_manual_file(out / f"fir_{result.key}_96k_{result.fir_taps}taps_manual.txt", result.fir)
        write_fir_binary_file(out / f"fir_{result.key}_96k_{result.fir_taps}taps.bin", result.fir)

    response_csv(
        out / "validation_response.csv",
        freq,
        {
            "target_db": shifted_target_db,
            "left_raw_db": db(avg["left"]),
            "right_raw_db": db(avg["right"]),
            "sub_raw_db": db(avg["sub"]),
            "left_corrected_db": db(corrected["left"]),
            "right_corrected_db": db(corrected["right"]),
            "sub_corrected_db": db(corrected["sub"]),
            "left_final_db": db(final_channels["left"]),
            "right_final_db": db(final_channels["right"]),
            "sub_final_db": db(final_channels["sub"]),
            "pred_left_plus_sub_db": db(pred_lsum),
            "pred_right_plus_sub_db": db(pred_rsum),
            "measured_left_plus_sub_db": db(avg["left_sum"]),
            "measured_right_plus_sub_db": db(avg["right_sum"]),
            "left_cancellation_db": left_cancellation,
            "right_cancellation_db": right_cancellation,
        },
    )
    write_rows_csv(out / "midbass_alignment.csv", midbass_rows)
    write_rows_csv(out / "crossover_candidates.csv", crossover["top_candidates"])
    write_settings_summary(out, crossover, delays, gains, results, args.sub_highpass_hz, args.sub_low_freq)
    build_report(
        out=out,
        notes=validation_notes,
        crossover=crossover,
        target_file=target_path,
        sub_highpass_hz=args.sub_highpass_hz,
        sub_low_freq=args.sub_low_freq,
        target_offset_db=shift,
        target_absolute=args.absolute_target,
        delays=delays,
        gains=gains,
        results=results,
        validations=validations,
        distortion_note=distortion_note,
        mic_cal_policy=args.mic_cal_policy,
        mic_compare_note=mic_compare_note,
        boundary_warning=boundary_warning,
        midbass_rows=midbass_rows,
    )

    metadata = {
        "sample_rate_hz": OUT_FS,
        "input_impulse_sample_rate_hz": INPUT_FS_EXPECTED,
        "target_file": str(target_path),
        "mic_cal_policy": args.mic_cal_policy,
        "generation_mic_policy": generation_mic_policy,
        "mic_compare_note": mic_compare_note,
        "sub_low_freq": args.sub_low_freq,
        "sub_highpass_hz": args.sub_highpass_hz,
        "crossover": crossover,
        "crossover_boundary_warning": boundary_warning,
        "target_offset_db": shift,
        "delays_ms": delays,
        "fir_group_delays_ms": {
            "left": fir_group_delay_ms(FIR_TAPS["left"]),
            "right": fir_group_delay_ms(FIR_TAPS["right"]),
            "sub": fir_group_delay_ms(FIR_TAPS["sub"]),
            "sub_minus_main": fir_group_delay_ms(FIR_TAPS["sub"]) - fir_group_delay_ms(FIR_TAPS["left"]),
        },
        "gains_db": gains,
        "fir_taps": FIR_TAPS,
        "validations": validations,
        "midbass_alignment": midbass_rows,
        "filters": {
            result.key: [
                {
                    "type": f.kind,
                    "freq_hz": f.freq,
                    "gain_db": f.gain_db,
                    "q": f.q,
                    "b0": f.b0,
                    "b1": f.b1,
                    "b2": f.b2,
                    "a1": f.a1,
                    "a2": f.a2,
                    "stable": f.is_stable(),
                }
                for f in result.peq
            ]
            for result in results
        },
    }
    out.joinpath("metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    print(f"Wrote miniDSP filter outputs to {out}")
    print(f"Crossover: {fc:.0f} Hz LR4")
    for result in results:
        print(
            f"{result.title}: gain {gains[result.key]:+.2f} dB, delay {delays[result.key]:.3f} ms, "
            f"{len(result.peq)} PEQs, {result.fir_taps} FIR taps"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
