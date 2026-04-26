#!/usr/bin/env python3
"""Generate miniDSP-style PEQ, crossover, delay, gain, and FIR files.

The script depends on NumPy for DSP/FIR math and SciPy for bounded PEQ
least-squares refinement. It reads the REW text exports in the SPL and Impulse
folders, averages the repeated measurements, optimizes the subwoofer crossover
alignment, and writes a reproducible Output folder.
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
from scipy.signal import freqz


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
    peq_optimization: Dict[str, object]
    fir: np.ndarray
    gain_db: float
    delay_ms: float
    fir_taps: int
    rms_before_db: float
    rms_after_db: float
    max_boost_db: float
    max_cut_db: float
    rms_after_peq_db: float = 0.0
    fir_requested_method: str = "legacy"
    fir_used_method: str = "legacy"
    fir_metrics: Dict[str, float] | None = None


@dataclass
class PeakOptimizationResult:
    filters: List[Biquad]
    seed_rms_db: float
    refined_rms_db: float
    success: bool


@dataclass
class PeqOptimizationResult:
    filters: List[Biquad]
    seed_rms_db: float
    refined_rms_db: float
    success: bool
    message: str
    nfev: int


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
        shifted = np.zeros_like(m.samples)
        if shift >= 0:
            shifted[shift:] = m.samples[: m.samples.size - shift]
        else:
            shifted[:shift] = m.samples[-shift:]
        aligned.append(shifted)
    return np.mean(np.vstack(aligned), axis=0)


def db(x: np.ndarray) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(np.abs(x), EPS))


def rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values)))) if values.size else float("nan")


def boost_cap_curve_db(
    freq: np.ndarray,
    distortion: Dict[str, np.ndarray] | None,
    channel_key: str,
    default_boost_db: float,
    no_boost_below_hz: float = 25.0,
) -> np.ndarray:
    cap = np.full(freq.shape, float(default_boost_db), dtype=np.float64)
    if channel_key == "sub":
        cap[freq < no_boost_below_hz] = 0.0
    if channel_key == "sub" and distortion is not None and "freq" in distortion and "thd_pct" in distortion:
        d_freq = np.asarray(distortion["freq"], dtype=np.float64)
        thd = np.asarray(distortion["thd_pct"], dtype=np.float64)
        if d_freq.size and thd.size:
            thd_on_grid = np.interp(freq, d_freq, thd, left=thd[0], right=thd[-1])
            thd_factor = 1.0 - np.clip((thd_on_grid - 5.0) / 5.0, 0.0, 1.0)
            cap = np.minimum(cap, float(default_boost_db) * thd_factor)
    return np.maximum(cap, 0.0)


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


def limit_peak_gain_to_boost_cap(
    freq: np.ndarray,
    existing_filters: Sequence[Biquad],
    centre: float,
    gain_db: float,
    q: float,
    boost_cap_db: np.ndarray,
    fs: float = OUT_FS,
) -> float:
    if gain_db <= 0.0:
        return gain_db
    existing = cascade_response(existing_filters, freq, fs)

    def max_over_cap(candidate_gain: float) -> float:
        candidate = biquad_peak(centre, candidate_gain, q, fs)
        boost_db = db(existing * candidate.response(freq, fs))
        return float(np.max(boost_db - boost_cap_db))

    cap_tolerance_db = 0.0
    if max_over_cap(gain_db) <= cap_tolerance_db:
        return gain_db
    lo = 0.0
    hi = gain_db
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if max_over_cap(mid) <= cap_tolerance_db:
            lo = mid
        else:
            hi = mid
    return lo


def limit_peak_filters_to_boost_cap(
    filters: Sequence[Biquad],
    freq: np.ndarray,
    boost_cap_db: np.ndarray,
    fs: float = OUT_FS,
) -> List[Biquad]:
    capped_filters: List[Biquad] = []
    for filt in filters:
        gain = limit_peak_gain_to_boost_cap(
            freq,
            capped_filters,
            filt.freq,
            filt.gain_db,
            filt.q,
            boost_cap_db,
            fs,
        )
        capped_filters.append(biquad_peak(filt.freq, gain, filt.q, fs))
    return capped_filters


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
    sorted_candidates = sorted(candidates, key=lambda row: row["score"])
    diverse_by_fc: Dict[float, Dict[str, float]] = {}
    for row in sorted_candidates:
        fc_key = round(row["crossover_hz"] * 2.0) / 2.0
        diverse_by_fc.setdefault(fc_key, row)
    top_candidates = list(sorted_candidates[:50])
    top_candidates.extend(diverse_by_fc.values())
    deduped: Dict[Tuple[float, float, float], Dict[str, float]] = {}
    for row in top_candidates:
        key = (row["crossover_hz"], row["sub_delay_ms"], row["sub_gain_db"])
        deduped[key] = row
    best["top_candidates"] = sorted(deduped.values(), key=lambda row: row["score"])[:120]
    return best


def seed_peak_filters(
    freq: np.ndarray,
    response: np.ndarray,
    target_db: np.ndarray,
    correction_mask: np.ndarray,
    max_filters: int = MAX_PEQ_FILTERS,
    boost_cap_db: np.ndarray | None = None,
) -> List[Biquad]:
    filters: List[Biquad] = []
    current = response.copy()
    used_ranges: List[Tuple[float, float]] = []
    boost_cap = (
        np.asarray(boost_cap_db, dtype=np.float64)
        if boost_cap_db is not None
        else np.full(freq.shape, 3.0, dtype=np.float64)
    )

    for _ in range(max_filters):
        error = db(current) - target_db
        smooth_error = smooth_log(error, freq, width_oct=1 / 5)
        masked = np.where(correction_mask, smooth_error, 0.0)
        cut_idx = int(np.argmax(masked))
        cut_amount = masked[cut_idx]

        dip = np.where(correction_mask & (boost_cap > 1e-6), -smooth_error, 0.0)
        boost_idx = int(np.argmax(dip))
        boost_amount = dip[boost_idx]

        if cut_amount >= 2.0 and cut_amount >= boost_amount * 0.65:
            idx = cut_idx
            gain = -float(np.clip(cut_amount * 0.75, 1.0, 9.0))
        elif boost_amount >= 2.0:
            idx = boost_idx
            # Boost gently and avoid trying to fill nulls.
            gain = float(np.clip(boost_amount * 0.35, 0.5, min(3.0, boost_cap[idx])))
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
        if gain > 0.0 and boost_cap_db is not None:
            gain = limit_peak_gain_to_boost_cap(freq, filters, centre, gain, q, boost_cap)
            if gain < 0.1:
                used_ranges.append((centre / (2.0 ** 0.2), centre * (2.0 ** 0.2)))
                continue
        filt = biquad_peak(centre, gain, q)
        if not filt.is_stable():
            break
        filters.append(filt)
        current *= filt.response(freq)
        used_ranges.append((centre / (2.0 ** 0.2), centre * (2.0 ** 0.2)))

    return filters


def _require_least_squares():
    try:
        from scipy.optimize import least_squares
    except ImportError as exc:
        raise RuntimeError(
            "SciPy is required for bounded PEQ least-squares refinement. "
            "Install dependencies with: python3 -m pip install -r requirements.txt"
        ) from exc
    return least_squares


def _require_minimize():
    try:
        from scipy.optimize import minimize
    except ImportError as exc:
        raise RuntimeError(
            "SciPy is required for gain refinement. "
            "Install dependencies with: python3 -m pip install -r requirements.txt"
        ) from exc
    return minimize


def _peq_rms_error(
    filters: Sequence[Biquad],
    freq: np.ndarray,
    base_db: np.ndarray,
    target_db: np.ndarray,
) -> float:
    corrected_db = base_db + db(cascade_response(filters, freq))
    return rms(corrected_db - target_db)


def prune_redundant_peq_filters(
    filters: Sequence[Biquad],
    freq: np.ndarray,
    response: np.ndarray,
    target_db: np.ndarray,
    correction_mask: np.ndarray,
    max_rms_worsening_db: float = 0.2,
    same_sign_octaves: float = 1.0 / 3.0,
    fs: float = OUT_FS,
) -> List[Biquad]:
    remaining = [filt for filt in filters if filt.is_stable()]
    mask = correction_mask.astype(bool)
    if len(remaining) < 2 or np.count_nonzero(mask) < 3:
        return remaining

    fit_freq = freq[mask]
    base = response[mask]
    fit_target = target_db[mask]

    def fit_rms(candidate_filters: Sequence[Biquad]) -> float:
        corrected = base * cascade_response(candidate_filters, fit_freq, fs)
        return rms(db(corrected) - fit_target)

    def impact(candidate_filters: Sequence[Biquad], idx: int) -> float:
        with_filter = fit_rms(candidate_filters)
        without_filter = fit_rms(candidate_filters[:idx] + candidate_filters[idx + 1 :])
        return without_filter - with_filter

    changed = True
    while changed:
        changed = False
        current_rms = fit_rms(remaining)
        best_remove: int | None = None
        best_worsening = float("inf")
        for left_idx, left in enumerate(remaining):
            for right_idx in range(left_idx + 1, len(remaining)):
                right = remaining[right_idx]
                if left.gain_db * right.gain_db <= 0.0:
                    continue
                spacing_oct = abs(math.log2(left.freq / right.freq))
                if spacing_oct > same_sign_octaves:
                    continue
                left_impact = impact(remaining, left_idx)
                right_impact = impact(remaining, right_idx)
                candidate_idx = left_idx if left_impact <= right_impact else right_idx
                candidate = remaining[:candidate_idx] + remaining[candidate_idx + 1 :]
                worsening = fit_rms(candidate) - current_rms
                if worsening <= max_rms_worsening_db and worsening < best_worsening:
                    best_remove = candidate_idx
                    best_worsening = worsening
        if best_remove is not None:
            remaining.pop(best_remove)
            changed = True

    return remaining


def optimize_peak_filters(
    freq: np.ndarray,
    response: np.ndarray,
    target_db: np.ndarray,
    correction_mask: np.ndarray,
    seed_filters: Sequence[Biquad],
    distortion: Dict[str, np.ndarray] | None = None,
    boost_cap_db: np.ndarray | None = None,
    boost_cap_penalty_weight: float = 8.0,
    peq_cumulative_boost_cap_db: float = 5.0,
    fs: float = OUT_FS,
) -> PeqOptimizationResult:
    """Refine all PEQ parameters together with bounded robust least squares."""
    if not seed_filters:
        masked = correction_mask.astype(bool)
        base_db = db(response[masked])
        return PeqOptimizationResult([], rms(base_db - target_db[masked]), rms(base_db - target_db[masked]), True, "No seed filters.", 0)

    least_squares = _require_least_squares()
    mask = correction_mask.astype(bool)
    fit_freq = freq[mask]
    if fit_freq.size < 3:
        return PeqOptimizationResult(list(seed_filters), float("nan"), float("nan"), False, "Correction mask is too small.", 0)

    lo_freq = float(np.min(fit_freq))
    hi_freq = float(np.max(fit_freq))
    grid_points = min(512, fit_freq.size)
    fit_grid = np.geomspace(lo_freq, hi_freq, grid_points)
    base_db = np.interp(fit_grid, freq, db(response))
    fit_target_db = np.interp(fit_grid, freq, target_db)
    boost_cap_grid_db = (
        np.interp(fit_grid, freq, np.asarray(boost_cap_db, dtype=np.float64))
        if boost_cap_db is not None
        else None
    )
    cumulative_boost_cap_grid_db = np.full(
        fit_grid.shape,
        float(peq_cumulative_boost_cap_db),
        dtype=np.float64,
    )
    if boost_cap_grid_db is not None:
        cumulative_boost_cap_grid_db = np.minimum(cumulative_boost_cap_grid_db, boost_cap_grid_db)

    q_min, q_max = 0.35, 8.0
    gain_min, gain_max = -9.0, 3.0
    distortion_freq = None
    distortion_thd = None
    if distortion is not None and "freq" in distortion and "thd_pct" in distortion:
        distortion_freq = np.asarray(distortion["freq"], dtype=np.float64)
        distortion_thd = np.asarray(distortion["thd_pct"], dtype=np.float64)

    x0: List[float] = []
    lower: List[float] = []
    upper: List[float] = []
    for filt in seed_filters:
        clipped_freq = float(np.clip(filt.freq, lo_freq, hi_freq))
        clipped_q = float(np.clip(filt.q, q_min, q_max))
        filter_gain_max = gain_max
        if boost_cap_db is not None:
            filter_gain_max = min(
                filter_gain_max,
                float(np.interp(clipped_freq, freq, np.asarray(boost_cap_db, dtype=np.float64))),
            )
        if distortion_freq is not None and distortion_thd is not None and clipped_freq < 25.0:
            thd = float(
                np.interp(
                    clipped_freq,
                    distortion_freq,
                    distortion_thd,
                    left=distortion_thd[0],
                    right=distortion_thd[-1],
                )
            )
            if thd > 5.0:
                filter_gain_max = 1.0
        clipped_gain = float(np.clip(filt.gain_db, gain_min, filter_gain_max))
        x0.extend([math.log2(clipped_freq), math.log(clipped_q), clipped_gain])
        lower.extend([math.log2(lo_freq), math.log(q_min), gain_min])
        upper.extend([math.log2(hi_freq), math.log(q_max), filter_gain_max])

    def decode(params: np.ndarray) -> List[Biquad]:
        filters: List[Biquad] = []
        for idx in range(0, params.size, 3):
            centre = 2.0 ** float(params[idx])
            q = math.exp(float(params[idx + 1]))
            gain = float(params[idx + 2])
            filters.append(biquad_peak(centre, gain, q, fs))
        return filters

    cumulative_boost_cap_full = np.full(
        freq.shape,
        float(peq_cumulative_boost_cap_db),
        dtype=np.float64,
    )
    if boost_cap_db is not None:
        cumulative_boost_cap_full = np.minimum(
            cumulative_boost_cap_full,
            np.asarray(boost_cap_db, dtype=np.float64),
        )
    seed_for_fallback = limit_peak_filters_to_boost_cap(
        decode(np.asarray(x0, dtype=np.float64)),
        freq,
        cumulative_boost_cap_full,
        fs,
    )
    seed_for_fallback = prune_redundant_peq_filters(
        seed_for_fallback,
        freq,
        response,
        target_db,
        correction_mask,
        max_rms_worsening_db=0.2,
        fs=fs,
    )
    seed_rms = _peq_rms_error(seed_for_fallback, fit_grid, base_db, fit_target_db)

    def penalty_residuals(filters: Sequence[Biquad]) -> List[float]:
        penalties: List[float] = []
        for filt in filters:
            boost = max(filt.gain_db, 0.0)
            penalties.append(boost / 8.0)
            penalties.append(max(filt.q - 4.0, 0.0) / 3.0)
            if distortion_freq is not None and distortion_thd is not None:
                thd = float(
                    np.interp(
                        filt.freq,
                        distortion_freq,
                        distortion_thd,
                        left=distortion_thd[0],
                        right=distortion_thd[-1],
                    )
                )
                low_freq_risk = max(0.0, (25.0 - filt.freq) / 10.0)
                thd_risk = max(0.0, (thd - 5.0) / 5.0)
                penalties.append(boost * low_freq_risk * thd_risk * 6.0)
        if boost_cap_grid_db is not None:
            peq_boost_db = db(cascade_response(filters, fit_grid, fs))
            over_boost = np.maximum(peq_boost_db - boost_cap_grid_db, 0.0)
            penalties.extend((over_boost * boost_cap_penalty_weight).tolist())
        peq_boost_db = db(cascade_response(filters, fit_grid, fs))
        over_cumulative_boost = np.maximum(peq_boost_db - cumulative_boost_cap_grid_db, 0.0)
        penalties.extend((over_cumulative_boost * 3.0).tolist())
        for left_idx, left in enumerate(filters):
            for right in filters[left_idx + 1 :]:
                spacing_oct = abs(math.log2(left.freq / right.freq))
                same_sign = 1.0 if left.gain_db * right.gain_db > 0.0 else 0.35
                penalties.append(max((1.0 / 3.0) - spacing_oct, 0.0) * 3.0 * same_sign)
        return penalties

    def residuals(params: np.ndarray) -> np.ndarray:
        filters = decode(params)
        corrected_db = base_db + db(cascade_response(filters, fit_grid, fs))
        response_residual = corrected_db - fit_target_db
        return np.r_[response_residual, np.asarray(penalty_residuals(filters), dtype=np.float64)]

    result = least_squares(
        residuals,
        np.asarray(x0, dtype=np.float64),
        bounds=(np.asarray(lower), np.asarray(upper)),
        loss="soft_l1",
        f_scale=1.5,
        max_nfev=900,
    )
    decoded_filters = decode(result.x)
    if peq_cumulative_boost_cap_db > 0.0:
        decoded_filters = limit_peak_filters_to_boost_cap(
            decoded_filters,
            freq,
            cumulative_boost_cap_full,
            fs,
        )
    all_filters = [filt for filt in decoded_filters if abs(filt.gain_db) >= 0.1]
    stable_filters = [filt for filt in all_filters if filt.is_stable()]
    stable_filters = prune_redundant_peq_filters(
        stable_filters,
        freq,
        response,
        target_db,
        correction_mask,
        max_rms_worsening_db=0.2,
        fs=fs,
    )
    refined_rms = _peq_rms_error(stable_filters, fit_grid, base_db, fit_target_db)
    if not stable_filters and seed_filters:
        refined_rms = rms(base_db - fit_target_db)
    if not np.isfinite(refined_rms) or refined_rms > seed_rms:
        stable_filters = seed_for_fallback
        stable_filters = prune_redundant_peq_filters(
            stable_filters,
            freq,
            response,
            target_db,
            correction_mask,
            max_rms_worsening_db=0.2,
            fs=fs,
        )
        refined_rms = seed_rms
    accepted = bool(result.success) or bool(np.isfinite(refined_rms) and refined_rms <= seed_rms)
    return PeqOptimizationResult(
        filters=stable_filters,
        seed_rms_db=seed_rms,
        refined_rms_db=refined_rms,
        success=accepted,
        message=str(result.message),
        nfev=int(result.nfev),
    )


def find_peak_filters(
    freq: np.ndarray,
    response: np.ndarray,
    target_db: np.ndarray,
    correction_mask: np.ndarray,
    max_filters: int = MAX_PEQ_FILTERS,
    distortion: Dict[str, np.ndarray] | None = None,
) -> List[Biquad]:
    seed = seed_peak_filters(freq, response, target_db, correction_mask, max_filters)
    return optimize_peak_filters(freq, response, target_db, correction_mask, seed, distortion).filters


def peq_optimization_metadata(result: PeqOptimizationResult) -> Dict[str, object]:
    return {
        "method": "scipy.optimize.least_squares",
        "loss": "soft_l1",
        "f_scale_db": 1.5,
        "bounds": {
            "q": [0.35, 8.0],
            "gain_db": [-9.0, 3.0],
            "frequency_hz": "channel correction mask",
        },
        "cumulative_boost_cap_db": 5.0,
        "redundant_filter_pruning": {
            "same_sign_octaves": 1.0 / 3.0,
            "max_rms_worsening_db": 0.2,
        },
        "seed_rms_db": result.seed_rms_db,
        "refined_rms_db": result.refined_rms_db,
        "success": result.success,
        "message": result.message,
        "nfev": result.nfev,
    }


def make_fir(
    freq: np.ndarray,
    residual_db: np.ndarray,
    taps: int,
    correction_mask: np.ndarray,
    fs: float = OUT_FS,
    boost_cap_db: np.ndarray | None = None,
    max_cut_db: float = 10.0,
) -> np.ndarray:
    nfft = 65536
    grid = np.linspace(0.0, fs / 2.0, nfft // 2 + 1)
    safe_residual = np.zeros_like(freq)
    safe_residual[correction_mask] = residual_db[correction_mask]
    safe_residual = smooth_log(safe_residual, np.maximum(freq, 1.0), width_oct=1 / 3)
    boost_cap = (
        np.asarray(boost_cap_db, dtype=np.float64)
        if boost_cap_db is not None
        else np.full(freq.shape, 3.0, dtype=np.float64)
    )
    safe_residual = np.maximum(safe_residual, -float(max_cut_db))
    safe_residual = np.minimum(safe_residual, boost_cap)

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


def design_fir_frequency_grid(
    freq: np.ndarray,
    correction_mask: np.ndarray,
    fs: float = OUT_FS,
    grid_points: int = 1024,
) -> np.ndarray:
    if grid_points < 32:
        raise ValueError("--fir-ls-grid-points must be at least 32")
    positive_freq = freq[freq > 0.0]
    low = max(float(positive_freq[0]), 1.0)
    high = min(float(freq[-1]), fs * 0.5 * 0.98)
    if np.any(correction_mask):
        active_freq = freq[correction_mask]
        low = min(low, max(float(active_freq[0]) * 0.5, 1.0))
        high = max(high, min(float(active_freq[-1]) * 1.35, fs * 0.5 * 0.98))
    grid = np.geomspace(low, high, grid_points)
    anchors = np.asarray([0.0, low, high, fs * 0.5], dtype=np.float64)
    return np.unique(np.r_[anchors, grid])


def interp_complex(freq: np.ndarray, response: np.ndarray, design_freq: np.ndarray) -> np.ndarray:
    real = np.interp(design_freq, freq, np.real(response), left=np.real(response[0]), right=np.real(response[-1]))
    imag = np.interp(design_freq, freq, np.imag(response), left=np.imag(response[0]), right=np.imag(response[-1]))
    return real + 1j * imag


def second_difference_matrix(taps: int) -> np.ndarray:
    if taps < 3:
        return np.zeros((0, taps), dtype=np.float64)
    d = np.zeros((taps - 2, taps), dtype=np.float64)
    rows = np.arange(taps - 2)
    d[rows, rows] = 1.0
    d[rows, rows + 1] = -2.0
    d[rows, rows + 2] = 1.0
    return d


def solve_real_complex_lstsq(
    matrix: np.ndarray,
    target: np.ndarray,
    regularizer: np.ndarray,
    lambda_reg: float,
) -> np.ndarray:
    real_system = np.vstack([np.real(matrix), np.imag(matrix)])
    real_target = np.r_[np.real(target), np.imag(target)]
    if lambda_reg > 0.0 and regularizer.size:
        scale = math.sqrt(lambda_reg)
        real_system = np.vstack([real_system, scale * regularizer])
        real_target = np.r_[real_target, np.zeros(regularizer.shape[0], dtype=np.float64)]
    solution, *_ = np.linalg.lstsq(real_system, real_target, rcond=None)
    return np.asarray(solution, dtype=np.float64)


def make_fir_ls(
    freq: np.ndarray,
    measured_response: np.ndarray,
    target_db: np.ndarray,
    taps: int,
    correction_mask: np.ndarray,
    fs: float = OUT_FS,
    grid_points: int = 1024,
    lambda_reg: float = 0.01,
    max_boost_db: float = 3.0,
    max_cut_db: float = 10.0,
    boost_cap_db: np.ndarray | None = None,
    phase_mode: str = "magnitude",
) -> np.ndarray:
    if lambda_reg < 0.0:
        raise ValueError("--fir-ls-lambda must be non-negative")
    design_freq, correction_target, weights = ls_fir_correction_target(
        freq,
        measured_response,
        target_db,
        taps,
        correction_mask,
        fs=fs,
        grid_points=grid_points,
        max_boost_db=max_boost_db,
        max_cut_db=max_cut_db,
        boost_cap_db=boost_cap_db,
        phase_mode=phase_mode,
    )
    n = np.arange(taps, dtype=np.float64)
    fourier = np.exp(-1j * 2.0 * np.pi * np.outer(design_freq / fs, n))
    system = fourier * weights[:, None]
    weighted_target = correction_target * weights
    fir = solve_real_complex_lstsq(
        system,
        weighted_target,
        second_difference_matrix(taps),
        lambda_reg=lambda_reg,
    )

    return fir.astype(np.float64)


def ls_fir_correction_target(
    freq: np.ndarray,
    measured_response: np.ndarray,
    target_db: np.ndarray,
    taps: int,
    correction_mask: np.ndarray,
    fs: float = OUT_FS,
    grid_points: int = 1024,
    max_boost_db: float = 3.0,
    max_cut_db: float = 10.0,
    boost_cap_db: np.ndarray | None = None,
    phase_mode: str = "magnitude",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if taps <= 0:
        raise ValueError("FIR tap count must be positive")
    if max_boost_db < 0.0 or max_cut_db < 0.0:
        raise ValueError("FIR boost/cut guardrails must be non-negative")
    if phase_mode not in {"magnitude", "complex-inverse"}:
        raise ValueError("--fir-ls-phase-mode must be 'magnitude' or 'complex-inverse'")

    design_freq = design_fir_frequency_grid(freq, correction_mask, fs=fs, grid_points=grid_points)
    measured = interp_complex(freq, measured_response, design_freq)
    target = np.interp(design_freq, freq, target_db, left=target_db[0], right=target_db[-1])
    active = np.interp(design_freq, freq, correction_mask.astype(np.float64), left=0.0, right=0.0) >= 0.5

    measured_db = db(measured)
    boost_cap_design = (
        np.interp(design_freq, freq, np.asarray(boost_cap_db, dtype=np.float64))
        if boost_cap_db is not None
        else np.full(design_freq.shape, float(max_boost_db), dtype=np.float64)
    )
    correction_db = np.maximum(target - measured_db, -max_cut_db)
    correction_db = np.minimum(correction_db, boost_cap_design)
    correction_db[~active] = 0.0
    desired_active_db = measured_db + correction_db
    delay_samples = (taps - 1) / 2.0
    delay_phase = np.exp(-1j * 2.0 * np.pi * design_freq * (delay_samples / fs))

    confidence = np.ones_like(design_freq, dtype=np.float64) * 0.08
    confidence[active] = 1.0
    confidence *= np.clip(np.abs(measured) / np.percentile(np.abs(measured), 75), 0.1, 1.0)
    confidence[boost_cap_design <= 0.1] *= 25.0
    weights = np.sqrt(confidence)

    if phase_mode == "magnitude":
        correction_mag = 10.0 ** (correction_db / 20.0)
        correction_target = correction_mag * delay_phase
    else:
        desired = measured * delay_phase
        desired[active] = (10.0 ** (desired_active_db[active] / 20.0)) * delay_phase[active]
        safe_measured = np.where(np.abs(measured) > EPS, measured, EPS + 0.0j)
        correction_target = desired / safe_measured
    return design_freq, correction_target, weights

def fir_response(fir: np.ndarray, freq: np.ndarray, fs: float = OUT_FS) -> np.ndarray:
    _, response = freqz(fir, worN=2.0 * np.pi * freq / fs)
    return response


def channel_rms_error(
    response: np.ndarray,
    target_db: np.ndarray,
    mask: np.ndarray,
) -> float:
    return rms(db(response[mask]) - target_db[mask])


def choose_fir_with_fallback(
    freq: np.ndarray,
    after_peq: np.ndarray,
    target_db: np.ndarray,
    correction_mask: np.ndarray,
    requested_method: str,
    fallback_enabled: bool,
    ls_fir: np.ndarray | None,
    legacy_fir: np.ndarray,
    guardrail_fir: np.ndarray | None = None,
    fallback_tolerance_db: float = 0.25,
    boost_cap_db: np.ndarray | None = None,
    peq_response: np.ndarray | None = None,
) -> Dict[str, object]:
    after_peq_rms = channel_rms_error(after_peq, target_db, correction_mask)
    legacy_response = after_peq * fir_response(legacy_fir, freq)
    legacy_rms = channel_rms_error(legacy_response, target_db, correction_mask)
    peq_filter_response = peq_response if peq_response is not None else np.ones_like(freq, dtype=np.complex128)
    legacy_filter_boost = db(peq_filter_response * fir_response(legacy_fir, freq))
    legacy_boost_over_cap = (
        float(np.max(legacy_filter_boost - boost_cap_db))
        if boost_cap_db is not None
        else 0.0
    )
    metrics = {
        "after_peq_rms_db": after_peq_rms,
        "legacy_rms_db": legacy_rms,
        "legacy_boost_over_cap_db": legacy_boost_over_cap,
    }
    if (
        (requested_method == "legacy" or ls_fir is None)
        and boost_cap_db is not None
        and legacy_boost_over_cap > 0.1
    ):
        if guardrail_fir is not None:
            guardrail_response = after_peq * fir_response(guardrail_fir, freq)
            guardrail_filter_boost = db(peq_filter_response * fir_response(guardrail_fir, freq))
            guardrail_boost_over_cap = float(np.max(guardrail_filter_boost - boost_cap_db))
            metrics["guardrail_rms_db"] = channel_rms_error(guardrail_response, target_db, correction_mask)
            metrics["guardrail_boost_over_cap_db"] = guardrail_boost_over_cap
            if guardrail_boost_over_cap <= 0.1:
                return {
                    "fir": guardrail_fir,
                    "used_method": "flat guardrail fallback",
                    "metrics": metrics,
                }
        raise ValueError(
            "Legacy FIR violates the configured boost cap and no acceptable guardrail FIR is available."
        )
    if requested_method == "legacy" or ls_fir is None:
        return {
            "fir": legacy_fir,
            "used_method": "legacy",
            "metrics": metrics,
        }

    ls_response = after_peq * fir_response(ls_fir, freq)
    ls_rms = channel_rms_error(ls_response, target_db, correction_mask)
    ls_filter_boost = db(peq_filter_response * fir_response(ls_fir, freq))
    ls_boost_over_cap = (
        float(np.max(ls_filter_boost - boost_cap_db))
        if boost_cap_db is not None
        else 0.0
    )
    metrics["ls_rms_db"] = ls_rms
    metrics["ls_boost_over_cap_db"] = ls_boost_over_cap
    if fallback_enabled and not (
        ls_rms < after_peq_rms and ls_rms <= legacy_rms + fallback_tolerance_db
        and ls_boost_over_cap <= 0.1
    ):
        if boost_cap_db is not None and legacy_boost_over_cap > 0.1 and guardrail_fir is not None:
            guardrail_response = after_peq * fir_response(guardrail_fir, freq)
            guardrail_filter_boost = db(peq_filter_response * fir_response(guardrail_fir, freq))
            guardrail_boost_over_cap = float(np.max(guardrail_filter_boost - boost_cap_db))
            metrics["guardrail_rms_db"] = channel_rms_error(guardrail_response, target_db, correction_mask)
            metrics["guardrail_boost_over_cap_db"] = guardrail_boost_over_cap
            if guardrail_boost_over_cap <= 0.1:
                return {
                    "fir": guardrail_fir,
                    "used_method": "flat guardrail fallback",
                    "metrics": metrics,
                }
        return {
            "fir": legacy_fir,
            "used_method": "legacy fallback",
            "metrics": metrics,
        }
    return {
        "fir": ls_fir,
        "used_method": "ls",
        "metrics": metrics,
    }


def flat_delay_fir(taps: int) -> np.ndarray:
    fir = np.zeros(taps, dtype=np.float64)
    fir[taps // 2] = 1.0
    return fir


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


def phase_alignment_penalty(
    freq: np.ndarray,
    main: np.ndarray,
    sub: np.ndarray,
    crossover_hz: float,
) -> float:
    mask = (freq >= crossover_hz / math.sqrt(2.0)) & (freq <= crossover_hz * math.sqrt(2.0))
    if not np.any(mask):
        return 0.0
    main_db = db(main)
    sub_db = db(sub)
    overlap = mask & (np.abs(main_db - sub_db) <= 12.0)
    if np.count_nonzero(overlap) < 2:
        overlap = mask
    phase_error = np.angle(main[overlap] * np.conj(sub[overlap]))
    weights = np.minimum(np.abs(main[overlap]), np.abs(sub[overlap]))
    if float(np.sum(weights)) <= EPS:
        return 0.0
    return float(np.sqrt(np.average(np.square(phase_error / np.pi), weights=weights)))


def score_final_system_candidate(
    freq: np.ndarray,
    final_channels: Dict[str, np.ndarray],
    lsum_measured: np.ndarray,
    rsum_measured: np.ndarray,
    target_db: np.ndarray,
    crossover_hz: float,
    crossover_preference_hz: float | None = None,
) -> Dict[str, float]:
    pred_lsum = final_channels["left"] + final_channels["sub"]
    pred_rsum = final_channels["right"] + final_channels["sub"]
    score_mask = (freq >= 50.0) & (freq <= 160.0)
    if np.count_nonzero(score_mask) < 3:
        score_mask = np.ones_like(freq, dtype=bool)

    target_rms = rms(
        np.r_[
            db(pred_lsum[score_mask]) - target_db[score_mask],
            db(pred_rsum[score_mask]) - target_db[score_mask],
        ]
    )
    lr_mismatch = rms(db(pred_lsum[score_mask]) - db(pred_rsum[score_mask]))
    validation_rms = rms(
        np.r_[
            db(pred_lsum[score_mask]) - db(lsum_measured[score_mask]),
            db(pred_rsum[score_mask]) - db(rsum_measured[score_mask]),
        ]
    )

    left_cancellation = db(pred_lsum) - np.maximum(db(final_channels["left"]), db(final_channels["sub"]))
    right_cancellation = db(pred_rsum) - np.maximum(db(final_channels["right"]), db(final_channels["sub"]))
    cancellation_penalty = float(
        np.sqrt(
            np.mean(
                np.square(
                    np.r_[
                        np.minimum(left_cancellation[score_mask] + 1.0, 0.0),
                        np.minimum(right_cancellation[score_mask] + 1.0, 0.0),
                    ]
                )
            )
        )
    )
    phase_penalty = 0.5 * (
        phase_alignment_penalty(freq, final_channels["left"], final_channels["sub"], crossover_hz)
        + phase_alignment_penalty(freq, final_channels["right"], final_channels["sub"], crossover_hz)
    )
    preference_penalty = (
        abs(math.log2(crossover_hz / crossover_preference_hz))
        if crossover_preference_hz is not None
        else 0.0
    )
    score = (
        target_rms
        + 0.35 * lr_mismatch
        + 0.25 * validation_rms
        + 0.4 * cancellation_penalty
        + 0.5 * phase_penalty
        + preference_penalty
    )
    return {
        "score": float(score),
        "target_rms_db": float(target_rms),
        "lr_mismatch_rms_db": float(lr_mismatch),
        "validation_rms_db": float(validation_rms),
        "cancellation_penalty": float(cancellation_penalty),
        "phase_penalty": float(phase_penalty),
        "preference_penalty": float(preference_penalty),
    }


def apply_gain_deltas(
    final_channels: Dict[str, np.ndarray],
    deltas_db: Dict[str, float],
) -> Dict[str, np.ndarray]:
    return {
        key: final_channels[key] * (10.0 ** (deltas_db.get(key, 0.0) / 20.0))
        for key in final_channels
    }


def refine_output_gains(
    freq: np.ndarray,
    final_channels: Dict[str, np.ndarray],
    lsum_measured: np.ndarray,
    rsum_measured: np.ndarray,
    target_db: np.ndarray,
    crossover_hz: float,
    seed_gains_db: Dict[str, float],
    crossover_preference_hz: float | None = None,
    max_delta_db: float = 3.0,
) -> Dict[str, object]:
    minimize = _require_minimize()
    channels = ("left", "right", "sub")
    zero = {key: 0.0 for key in channels}
    score_before = score_final_system_candidate(
        freq,
        final_channels,
        lsum_measured,
        rsum_measured,
        target_db,
        crossover_hz,
        crossover_preference_hz,
    )

    def objective(deltas: np.ndarray) -> float:
        delta_map = {key: float(deltas[idx]) for idx, key in enumerate(channels)}
        scored_channels = apply_gain_deltas(final_channels, delta_map)
        return score_final_system_candidate(
            freq,
            scored_channels,
            lsum_measured,
            rsum_measured,
            target_db,
            crossover_hz,
            crossover_preference_hz,
        )["score"]

    result = minimize(
        objective,
        np.zeros(3, dtype=np.float64),
        method="L-BFGS-B",
        bounds=[(-max_delta_db, max_delta_db)] * 3,
        options={"maxiter": 80, "ftol": 1e-7},
    )
    deltas = np.asarray(result.x if result.success else np.zeros(3), dtype=np.float64)
    deltas = np.clip(deltas, -max_delta_db, max_delta_db)
    delta_db = {key: float(deltas[idx]) for idx, key in enumerate(channels)}
    refined_channels = apply_gain_deltas(final_channels, delta_db)
    score_after = score_final_system_candidate(
        freq,
        refined_channels,
        lsum_measured,
        rsum_measured,
        target_db,
        crossover_hz,
        crossover_preference_hz,
    )
    if score_after["score"] > score_before["score"]:
        delta_db = zero
        refined_channels = final_channels
        score_after = score_before
    return {
        "enabled": True,
        "gain_seed_db": dict(seed_gains_db),
        "gain_delta_db": delta_db,
        "gain_final_db": {
            key: float(seed_gains_db[key] + delta_db[key])
            for key in channels
        },
        "final_channels": refined_channels,
        "score_before": score_before,
        "score_after": score_after,
        "optimizer_success": bool(result.success),
        "optimizer_message": str(result.message),
    }


def gain_refinement_metadata(refinement: Dict[str, object]) -> Dict[str, object]:
    return {
        key: value
        for key, value in refinement.items()
        if key != "final_channels"
    }


def select_exact_crossover_candidate(
    candidates: Sequence[Dict[str, float]],
    exact_scorer,
    max_candidates: int = 8,
) -> Dict[str, float]:
    shortlist: List[Dict[str, float]] = []
    sorted_candidates = sorted(candidates, key=lambda row: row["score"])
    for candidate in sorted_candidates:
        if len(shortlist) >= max_candidates:
            break
        if all(abs(candidate["crossover_hz"] - existing["crossover_hz"]) >= 2.0 for existing in shortlist):
            shortlist.append(candidate)
    for candidate in sorted_candidates:
        if len(shortlist) >= max_candidates:
            break
        if candidate not in shortlist:
            shortlist.append(candidate)

    exact_rows: List[Dict[str, float]] = []
    for candidate in shortlist:
        exact = exact_scorer(candidate)
        row = dict(candidate)
        row["proxy_score"] = float(candidate["score"])
        row["exact_score"] = float(exact["score"])
        row["score"] = float(exact["score"])
        for key, value in exact.items():
            row[f"exact_{key}"] = float(value)
        exact_rows.append(row)

    best = dict(min(exact_rows, key=lambda row: row["exact_score"]))
    best["top_candidates"] = sorted(exact_rows, key=lambda row: row["exact_score"])
    best["exact_candidate_limit"] = int(max_candidates)
    best["exact_candidates_scored"] = len(exact_rows)
    return best


def crossover_selection_metadata(crossover: Dict[str, float]) -> Dict[str, object]:
    exact_rows = list(crossover.get("top_candidates", []))
    selected_keys = (
        "crossover_hz",
        "sub_delay_ms",
        "sub_gain_db",
        "proxy_score",
        "exact_score",
        "score",
    )
    selected = {key: crossover[key] for key in selected_keys if key in crossover}
    return {
        "exact_candidate_limit": int(crossover.get("exact_candidate_limit", len(exact_rows))),
        "exact_candidates_scored": int(crossover.get("exact_candidates_scored", len(exact_rows))),
        "selected_candidate": selected,
        "exact_scored_candidates": exact_rows,
    }


def correction_masks(
    freq: np.ndarray, crossover_hz: float, sub_low_freq: float = 20.0
) -> Dict[str, np.ndarray]:
    return {
        "left": (freq >= max(crossover_hz * 0.85, 60.0)) & (freq <= 18_000.0),
        "right": (freq >= max(crossover_hz * 0.85, 60.0)) & (freq <= 18_000.0),
        "sub": (freq >= sub_low_freq) & (freq <= min(crossover_hz * 1.8, 180.0)),
    }


def build_final_filter_system(
    freq: np.ndarray,
    avg: Dict[str, np.ndarray],
    target_db: np.ndarray,
    crossover: Dict[str, float],
    sub_low_freq: float,
    sub_highpass_hz: float,
    distortion: Dict[str, np.ndarray] | None = None,
    fir_method: str = "legacy",
    fir_ls_grid_points: int = 1024,
    fir_ls_lambda: float = 0.01,
    fir_ls_max_boost_db: float = 3.0,
    fir_ls_max_cut_db: float = 10.0,
    fir_ls_phase_mode: str = "magnitude",
    fir_ls_fallback: str = "on",
    gain_refinement_enabled: bool = True,
    crossover_preference_hz: float | None = None,
) -> Dict[str, object]:
    fc = float(crossover["crossover_hz"])
    masks = correction_masks(freq, fc, sub_low_freq=sub_low_freq)
    hp = cascade_response(lr4_filters(fc, "hp"), freq)
    lp = cascade_response(lr4_filters(fc, "lp"), freq)
    sub_hp_filters = [biquad_highpass(sub_highpass_hz)] if sub_highpass_hz > 0 else []
    sub_hp = cascade_response(sub_hp_filters, freq)
    xover = {"left": hp, "right": hp, "sub": lp * sub_hp}
    delays = translate_relative_delay_to_outputs(
        float(crossover["sub_delay_ms"]),
        main_taps=FIR_TAPS["left"],
        sub_taps=FIR_TAPS["sub"],
        fs=OUT_FS,
    )
    seed_gains = {
        "left": choose_channel_gain(freq, avg["left"] * hp, target_db, masks["left"]),
        "right": choose_channel_gain(freq, avg["right"] * hp, target_db, masks["right"]),
        "sub": float(crossover["sub_gain_db"])
        + choose_channel_gain(freq, avg["sub"] * lp * sub_hp, target_db, masks["sub"], headroom_db=-3.0),
    }

    def build_with_gains(current_gains: Dict[str, float]) -> Dict[str, object]:
        results: List[ChannelResult] = []
        corrected: Dict[str, np.ndarray] = {}
        final_channels: Dict[str, np.ndarray] = {}
        for key, title in [("left", "Left"), ("right", "Right"), ("sub", "Sub")]:
            base = avg[key] * xover[key] * 10.0 ** (current_gains[key] / 20.0)
            peq_boost_cap = boost_cap_curve_db(freq, distortion, key, default_boost_db=3.0)
            fir_boost_cap = boost_cap_curve_db(
                freq,
                distortion,
                key,
                default_boost_db=fir_ls_max_boost_db if fir_method == "ls" else 3.0,
            )
            seed = seed_peak_filters(
                freq,
                base,
                target_db,
                masks[key],
                MAX_PEQ_FILTERS,
                boost_cap_db=peq_boost_cap,
            )
            peq_result = optimize_peak_filters(
                freq,
                base,
                target_db,
                masks[key],
                seed,
                distortion,
                boost_cap_db=peq_boost_cap,
            )
            peq = peq_result.filters
            peq_resp = cascade_response(peq, freq)
            after_peq = base * peq_resp
            residual = target_db - db(after_peq)
            legacy_fir = make_fir(
                freq,
                residual,
                FIR_TAPS[key],
                masks[key],
                boost_cap_db=fir_boost_cap,
                max_cut_db=fir_ls_max_cut_db,
            )
            ls_fir = None
            if fir_method == "ls":
                ls_fir = make_fir_ls(
                    freq,
                    after_peq,
                    target_db,
                    FIR_TAPS[key],
                    masks[key],
                    grid_points=fir_ls_grid_points,
                    lambda_reg=fir_ls_lambda,
                    max_boost_db=fir_ls_max_boost_db,
                    max_cut_db=fir_ls_max_cut_db,
                    boost_cap_db=fir_boost_cap,
                    phase_mode=fir_ls_phase_mode,
                )
            elif fir_method != "legacy":
                raise ValueError(f"Unsupported FIR method: {fir_method}")

            selected_fir = choose_fir_with_fallback(
                freq,
                after_peq,
                target_db,
                masks[key],
                requested_method=fir_method,
                fallback_enabled=fir_ls_fallback == "on",
                ls_fir=ls_fir,
                legacy_fir=legacy_fir,
                guardrail_fir=flat_delay_fir(FIR_TAPS[key]),
                boost_cap_db=fir_boost_cap if key == "sub" else None,
                peq_response=peq_resp,
            )
            fir = selected_fir["fir"]  # type: ignore[assignment]
            f_resp = fir_response(fir, freq)
            after_all = after_peq * f_resp
            corrected[key] = after_all
            final_channels[key] = apply_output_delay(after_all, freq, delays[key])
            max_boost, max_cut = summarize_filters(peq)
            before_err = db(base[masks[key]]) - target_db[masks[key]]
            after_err = db(after_all[masks[key]]) - target_db[masks[key]]
            results.append(
                ChannelResult(
                    key=key,
                    title=title,
                    peq=peq,
                    peq_optimization=peq_optimization_metadata(peq_result),
                    fir=fir,
                    gain_db=current_gains[key],
                    delay_ms=delays[key],
                    fir_taps=FIR_TAPS[key],
                    rms_before_db=rms(before_err),
                    rms_after_db=rms(after_err),
                    max_boost_db=max_boost,
                    max_cut_db=max_cut,
                    rms_after_peq_db=channel_rms_error(after_peq, target_db, masks[key]),
                    fir_requested_method=fir_method,
                    fir_used_method=str(selected_fir["used_method"]),
                    fir_metrics=selected_fir["metrics"],  # type: ignore[arg-type]
                )
            )
        return {
            "results": results,
            "corrected": corrected,
            "final_channels": final_channels,
            "gains": dict(current_gains),
        }

    def apply_gain_refinement(build: Dict[str, object], refinement: Dict[str, object]) -> Dict[str, object]:
        gain_delta = refinement["gain_delta_db"]  # type: ignore[assignment]
        final_gains = refinement["gain_final_db"]  # type: ignore[assignment]
        corrected_with_gains = apply_gain_deltas(build["corrected"], gain_delta)  # type: ignore[arg-type]
        final_with_gains = refinement["final_channels"]
        results_with_gains = build["results"]  # type: ignore[assignment]
        for result in results_with_gains:
            result.gain_db = float(final_gains[result.key])
            result.rms_after_db = channel_rms_error(corrected_with_gains[result.key], target_db, masks[result.key])
        return {
            **build,
            "gains": final_gains,
            "corrected": corrected_with_gains,
            "final_channels": final_with_gains,
            "results": results_with_gains,
        }

    built = build_with_gains(seed_gains)
    gain_refinement = {
        "enabled": False,
        "gain_seed_db": dict(seed_gains),
        "gain_delta_db": {"left": 0.0, "right": 0.0, "sub": 0.0},
        "gain_final_db": dict(seed_gains),
        "score_before": {},
        "score_after": {},
        "rebuilt_after_large_delta": False,
    }
    if gain_refinement_enabled:
        gain_refinement = refine_output_gains(
            freq,
            built["final_channels"],  # type: ignore[arg-type]
            avg["left_sum"],
            avg["right_sum"],
            target_db,
            fc,
            seed_gains,
            crossover_preference_hz=crossover_preference_hz,
        )
        if max(abs(v) for v in gain_refinement["gain_delta_db"].values()) > 0.75:  # type: ignore[union-attr]
            rebuilt = build_with_gains(gain_refinement["gain_final_db"])  # type: ignore[arg-type]
            gain_refinement = refine_output_gains(
                freq,
                rebuilt["final_channels"],  # type: ignore[arg-type]
                avg["left_sum"],
                avg["right_sum"],
                target_db,
                fc,
                rebuilt["gains"],  # type: ignore[arg-type]
                crossover_preference_hz=crossover_preference_hz,
            )
            gain_refinement["rebuilt_after_large_delta"] = True
            built = apply_gain_refinement(rebuilt, gain_refinement)
        else:
            gain_refinement["rebuilt_after_large_delta"] = False
            built = apply_gain_refinement(built, gain_refinement)

    return {
        "fc": fc,
        "masks": masks,
        "sub_hp_filters": sub_hp_filters,
        "xover": xover,
        "delays": delays,
        "gains": built["gains"],
        "gain_refinement": gain_refinement_metadata(gain_refinement),
        "results": built["results"],
        "corrected": built["corrected"],
        "final_channels": built["final_channels"],
        "crossover_filters": {
            "left": lr4_filters(fc, "hp"),
            "right": lr4_filters(fc, "hp"),
            "sub": lr4_filters(fc, "lp") + sub_hp_filters,
        },
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
    header = sorted({name for row in rows for name in row.keys()})

    def format_value(value: object) -> str:
        if isinstance(value, (int, float, np.integer, np.floating)):
            return f"{float(value):.6f}"
        if isinstance(value, (list, tuple, dict)):
            return json.dumps(value, sort_keys=True).replace('"', '""')
        return str(value).replace('"', '""')

    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(f'"{format_value(row.get(name, ""))}"' for name in header))
    path.write_text("\n".join(lines) + "\n")


def summarize_filters(filters: Sequence[Biquad]) -> Tuple[float, float]:
    gains = np.asarray([f.gain_db for f in filters], dtype=np.float64)
    if gains.size == 0:
        return 0.0, 0.0
    return float(np.max(np.maximum(gains, 0.0))), float(np.min(np.minimum(gains, 0.0)))


def channel_filter_boost_db(result: ChannelResult, freq: np.ndarray) -> np.ndarray:
    return db(cascade_response(result.peq, freq) * fir_response(result.fir, freq))


def max_filter_boost_below_hz(
    freq: np.ndarray,
    results: Sequence[ChannelResult],
    channel_key: str,
    limit_hz: float,
) -> float:
    for result in results:
        if result.key == channel_key:
            mask = freq < limit_hz
            if not np.any(mask):
                return 0.0
            return float(np.max(channel_filter_boost_db(result, freq)[mask]))
    return 0.0


def distortion_guardrail_note(
    distortion: Dict[str, np.ndarray] | None,
    freq: np.ndarray,
    results: Sequence[ChannelResult],
    no_boost_below_hz: float = 25.0,
) -> str:
    if distortion is None:
        return "No distortion file was found."
    d_freq = distortion["freq"]
    thd = distortion["thd_pct"]
    low = (d_freq >= 20.0) & (d_freq <= 120.0)
    measurement = str(distortion.get("measurement", ["unknown"])[0])
    median_thd = float(np.median(thd[low])) if np.any(low) else float(np.median(thd))
    actual_boost = max_filter_boost_below_hz(freq, results, "sub", no_boost_below_hz)
    note = (
        "Distortion guardrail used from Distortion.txt "
        f"({measurement}); median THD 20-120 Hz is {median_thd:.2f}%. "
        f"Sub boost cap below {no_boost_below_hz:g} Hz: +0.0 dB; "
        f"actual max Sub PEQ+FIR boost below {no_boost_below_hz:g} Hz is {actual_boost:+.2f} dB"
    )
    if actual_boost <= 0.1:
        return note + ", so boosts below 25 Hz were avoided."
    return note + ", so boosts below 25 Hz were not fully avoided."


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
    fir_method: str,
    fir_ls_settings: Dict[str, float],
    exact_candidate_limit: int,
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
    lines.append(
        f"- Exact crossover candidates rescored: {crossover.get('exact_candidates_scored', 0)} of "
        f"{exact_candidate_limit}"
    )
    if boundary_warning:
        lines.append(f"- Crossover search warning: {boundary_warning}")
    lines.append(f"- Mic calibration policy: {mic_cal_policy}. {mic_compare_note}")
    lines.append("- PEQ selection: greedy seeds refined with bounded SciPy soft-L1 least squares.")
    if fir_method == "ls":
        lines.append(
            "- FIR requested: weighted regularized least-squares "
            f"({fir_ls_settings['grid_points']:.0f} design points, lambda {fir_ls_settings['lambda_reg']:.4g}, "
            f"phase mode {fir_ls_settings['phase_mode']}, fallback {fir_ls_settings['fallback']}, "
            f"boost/cut guardrails +{fir_ls_settings['max_boost_db']:.1f}/-{fir_ls_settings['max_cut_db']:.1f} dB)."
        )
    else:
        lines.append("- FIR requested: legacy smoothed magnitude inverse via frequency sampling and windowed truncation.")
    for result in results:
        lines.append(f"- {result.title} FIR used: {result.fir_used_method}.")
    lines.append(
        f"- FIR target delay compensation: Sub FIR target delay is "
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
        "- The FIR files are generated as matched acoustic correction filters; output delay handles the main timing alignment."
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
    fir_method: str,
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
            f"FIR requested: {'weighted regularized least-squares' if fir_method == 'ls' else 'legacy smoothed magnitude inverse'}",
            "FIR used:",
            *[f"{result.title}: {result.fir_used_method}" for result in results],
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
            "PEQ selection: greedy seeds refined with bounded SciPy soft-L1 least squares.",
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
    parser.add_argument(
        "--fir-method",
        choices=("ls", "legacy"),
        default="ls",
        help="FIR design method. 'ls' uses weighted regularized least-squares; 'legacy' uses the old windowed inverse.",
    )
    parser.add_argument(
        "--fir-ls-grid-points",
        type=int,
        default=1024,
        help="Number of log-spaced frequency design points for --fir-method ls.",
    )
    parser.add_argument(
        "--fir-ls-lambda",
        type=float,
        default=0.01,
        help="Second-difference regularization strength for --fir-method ls.",
    )
    parser.add_argument(
        "--fir-ls-max-boost-db",
        type=float,
        default=3.0,
        help="Maximum FIR boost requested by the LS target before solving.",
    )
    parser.add_argument(
        "--fir-ls-max-cut-db",
        type=float,
        default=10.0,
        help="Maximum FIR cut requested by the LS target before solving.",
    )
    parser.add_argument(
        "--fir-ls-phase-mode",
        choices=("magnitude", "complex-inverse"),
        default="magnitude",
        help="LS FIR phase target. 'magnitude' keeps linear FIR delay; 'complex-inverse' also inverts measured phase.",
    )
    parser.add_argument(
        "--fir-ls-fallback",
        choices=("on", "off"),
        default="on",
        help="When on, use legacy FIR for any channel where LS fails the RMS acceptance gate.",
    )
    parser.add_argument(
        "--gain-refinement",
        choices=("on", "off"),
        default="on",
        help="Refine final output gains after PEQ/FIR construction.",
    )
    parser.add_argument(
        "--exact-candidates",
        type=int,
        default=30,
        help="Number of proxy crossover candidates to rescore with the full final-system objective.",
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
    fir_ls_settings = {
        "grid_points": float(args.fir_ls_grid_points),
        "lambda_reg": float(args.fir_ls_lambda),
        "max_boost_db": float(args.fir_ls_max_boost_db),
        "max_cut_db": float(args.fir_ls_max_cut_db),
        "phase_mode": args.fir_ls_phase_mode,
        "fallback": args.fir_ls_fallback,
    }

    proxy_crossover = optimize_crossover(
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
    system_cache: Dict[Tuple[float, float, float], Dict[str, object]] = {}

    def candidate_key(candidate: Dict[str, float]) -> Tuple[float, float, float]:
        return (
            round(float(candidate["crossover_hz"]), 6),
            round(float(candidate["sub_delay_ms"]), 6),
            round(float(candidate["sub_gain_db"]), 6),
        )

    def exact_scorer(candidate: Dict[str, float]) -> Dict[str, float]:
        key = candidate_key(candidate)
        if key not in system_cache:
            system_cache[key] = build_final_filter_system(
                freq=freq,
                avg=avg,
                target_db=shifted_target_db,
                crossover=candidate,
                sub_low_freq=args.sub_low_freq,
                sub_highpass_hz=args.sub_highpass_hz,
                distortion=distortion,
                fir_method=args.fir_method,
                fir_ls_grid_points=args.fir_ls_grid_points,
                fir_ls_lambda=args.fir_ls_lambda,
                fir_ls_max_boost_db=args.fir_ls_max_boost_db,
                fir_ls_max_cut_db=args.fir_ls_max_cut_db,
                fir_ls_phase_mode=args.fir_ls_phase_mode,
                fir_ls_fallback=args.fir_ls_fallback,
                gain_refinement_enabled=args.gain_refinement == "on",
                crossover_preference_hz=args.prefer_crossover,
            )
        return score_final_system_candidate(
            freq=freq,
            final_channels=system_cache[key]["final_channels"],  # type: ignore[arg-type]
            lsum_measured=avg["left_sum"],
            rsum_measured=avg["right_sum"],
            target_db=shifted_target_db,
            crossover_hz=float(candidate["crossover_hz"]),
            crossover_preference_hz=args.prefer_crossover,
        )

    crossover = select_exact_crossover_candidate(
        proxy_crossover["top_candidates"],
        exact_scorer=exact_scorer,
        max_candidates=args.exact_candidates,
    )
    selected_system = system_cache[candidate_key(crossover)]
    fc = float(crossover["crossover_hz"])
    delays = selected_system["delays"]  # type: ignore[assignment]
    gains = selected_system["gains"]  # type: ignore[assignment]
    results = selected_system["results"]  # type: ignore[assignment]
    corrected = selected_system["corrected"]  # type: ignore[assignment]
    final_channels = selected_system["final_channels"]  # type: ignore[assignment]
    crossover_filters = selected_system["crossover_filters"]  # type: ignore[assignment]
    gain_refinement = selected_system["gain_refinement"]  # type: ignore[assignment]

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

    distortion_note = distortion_guardrail_note(distortion, freq, results)

    # Write files.
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
    write_settings_summary(
        out,
        crossover,
        delays,
        gains,
        results,
        args.sub_highpass_hz,
        args.sub_low_freq,
        args.fir_method,
    )
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
        fir_method=args.fir_method,
        fir_ls_settings=fir_ls_settings,
        exact_candidate_limit=args.exact_candidates,
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
        "exact_crossover_selection": crossover_selection_metadata(crossover),
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
        "fir_method": args.fir_method,
        "fir_ls_settings": fir_ls_settings if args.fir_method == "ls" else None,
        "gain_refinement": gain_refinement,
        "validations": validations,
        "midbass_alignment": midbass_rows,
        "peq_optimizer": {result.key: result.peq_optimization for result in results},
        "fir": {
            result.key: {
                "requested_method": result.fir_requested_method,
                "used_method": result.fir_used_method,
                "metrics": result.fir_metrics,
            }
            for result in results
        },
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
