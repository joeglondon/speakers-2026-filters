#!/usr/bin/env python3
"""Regenerate and summarize baseline miniDSP profiles.

By default this script summarizes the checked-in baseline artifacts and writes
comparison_summary.json. Pass --regenerate to run fixed generation commands into
Baseline_Runs/ before summarizing those freshly generated artifacts.
"""

from __future__ import annotations

import argparse
import cmath
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


OUT_FS = 96_000.0
CHANNELS = ("left", "right", "sub")
BUNDLED_PYTHON = Path(
    "/Users/josephlondon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
)


@dataclass(frozen=True)
class ProfileSpec:
    name: str
    artifact_dir: Path
    command: list[str]


def command_for(
    python: str,
    root: Path,
    output: Path,
    *,
    min_crossover: int,
    max_crossover: int,
    fir_method: str,
    exact_candidates: int = 30,
    fir_ls_phase_mode: str = "magnitude",
    fir_ls_fallback: str = "on",
    gain_refinement: str = "on",
    prefer_crossover: int | None = None,
) -> list[str]:
    command = [
        python,
        str(root / "generate_minidsp_filters.py"),
        "--root",
        str(root),
        "--output",
        str(output),
        "--target-file",
        "Harman Target extrapolated to 15Hz.txt",
        "--min-crossover",
        str(min_crossover),
        "--max-crossover",
        str(max_crossover),
        "--sub-low-freq",
        "15",
        "--sub-highpass-hz",
        "0",
        "--mic-cal-policy",
        "trust-exports",
        "--fir-method",
        fir_method,
        "--exact-candidates",
        str(exact_candidates),
        "--fir-ls-phase-mode",
        fir_ls_phase_mode,
        "--fir-ls-fallback",
        fir_ls_fallback,
        "--gain-refinement",
        gain_refinement,
    ]
    if prefer_crossover is not None:
        command.extend(["--prefer-crossover", str(prefer_crossover)])
    return command


def default_specs(root: Path, *, python: str, regenerate_output_root: Path, regenerate: bool) -> list[ProfileSpec]:
    output_root = regenerate_output_root if regenerate_output_root.is_absolute() else root / regenerate_output_root
    definitions = [
        (
            "ls_auto_50_140",
            Path("Output_ls_auto_50_140"),
            "ls_auto_50_140",
            {"min_crossover": 50, "max_crossover": 140, "fir_method": "ls"},
        ),
        (
            "legacy_auto_50_140",
            Path("Output_fixed_harman_15hz_no_sub_hp_max140"),
            "legacy_auto_50_140",
            {"min_crossover": 50, "max_crossover": 140, "fir_method": "legacy"},
        ),
        (
            "profile_02_clean_140hz",
            Path("Top_Three_Profiles/Profile_02_clean_140hz"),
            "profile_02_clean_140hz",
            {"min_crossover": 140, "max_crossover": 140, "prefer_crossover": 140, "fir_method": "legacy"},
        ),
        (
            "profile_03_2023ish_54hz",
            Path("Top_Three_Profiles/Profile_03_2023ish_54hz"),
            "profile_03_2023ish_54hz",
            {"min_crossover": 54, "max_crossover": 54, "prefer_crossover": 54, "fir_method": "legacy"},
        ),
        (
            "profile_04_compromise_95hz",
            Path("Top_Three_Profiles/Profile_04_compromise_95hz"),
            "profile_04_compromise_95hz",
            {"min_crossover": 95, "max_crossover": 95, "prefer_crossover": 95, "fir_method": "legacy"},
        ),
    ]

    specs = []
    for name, checked_in_dir, generated_dir, kwargs in definitions:
        output = output_root / generated_dir
        artifact_dir = output if regenerate else checked_in_dir
        specs.append(
            ProfileSpec(
                name=name,
                artifact_dir=artifact_dir,
                command=command_for(python, root, output, **kwargs),
            )
        )
    return specs


def default_python() -> str:
    return str(BUNDLED_PYTHON) if BUNDLED_PYTHON.exists() else sys.executable


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def round_float(value: Any, digits: int = 6) -> float:
    return round(float(value), digits)


def round_mapping(values: dict[str, Any], digits: int = 6) -> dict[str, float]:
    return {key: round_float(value, digits) for key, value in values.items()}


def parse_channel_rms(report_text: str) -> dict[str, dict[str, float]]:
    pattern = re.compile(
        r"- (?P<channel>Left|Right|Sub): RMS target error "
        r"(?P<before>[-+]?\d+(?:\.\d+)?) dB before correction, "
        r"(?P<after>[-+]?\d+(?:\.\d+)?) dB after PEQ\+FIR",
    )
    rms: dict[str, dict[str, float]] = {}
    for match in pattern.finditer(report_text):
        channel = match.group("channel").lower()
        rms[channel] = {
            "before": round_float(match.group("before")),
            "after": round_float(match.group("after")),
        }
    missing = [channel for channel in CHANNELS if channel not in rms]
    if missing:
        raise ValueError(f"report is missing RMS rows for: {', '.join(missing)}")
    return rms


def geomspace(start: float, stop: float, count: int) -> list[float]:
    log_start = math.log(start)
    log_stop = math.log(stop)
    return [
        math.exp(log_start + (log_stop - log_start) * idx / (count - 1))
        for idx in range(count)
    ]


def biquad_response(filter_row: dict[str, Any], freq: float) -> complex:
    w = 2.0 * math.pi * freq / OUT_FS
    z1 = cmath.exp(-1j * w)
    z2 = cmath.exp(-2j * w)
    return (
        float(filter_row["b0"])
        + float(filter_row["b1"]) * z1
        + float(filter_row["b2"]) * z2
    ) / (
        1.0
        + float(filter_row["a1"]) * z1
        + float(filter_row["a2"]) * z2
    )


def fir_response(taps: list[float], freq: float) -> complex:
    if not taps:
        return 1.0 + 0.0j
    return sum(
        tap * cmath.exp(-1j * 2.0 * math.pi * freq * idx / OUT_FS)
        for idx, tap in enumerate(taps)
    )


def read_fir_taps(profile_dir: Path, channel: str, metadata: dict[str, Any]) -> list[float]:
    tap_count = metadata.get("fir_taps", {}).get(channel)
    if tap_count is not None:
        path = profile_dir / f"fir_{channel}_96k_{int(tap_count)}taps_raw.txt"
        if path.exists():
            return [float(line.strip()) for line in path.read_text().splitlines() if line.strip()]
    matches = sorted(profile_dir.glob(f"fir_{channel}_96k_*taps_raw.txt"))
    if not matches:
        return []
    return [float(line.strip()) for line in matches[0].read_text().splitlines() if line.strip()]


def max_boost_below_25hz(profile_dir: Path, metadata: dict[str, Any]) -> dict[str, float]:
    frequencies = geomspace(10.0, 24.99, 96)
    boosts: dict[str, float] = {}
    for channel in CHANNELS:
        taps = read_fir_taps(profile_dir, channel, metadata)
        response_db = []
        for freq in frequencies:
            response = 1.0 + 0.0j
            for filter_row in metadata.get("filters", {}).get(channel, []):
                response *= biquad_response(filter_row, freq)
            response *= fir_response(taps, freq)
            response_db.append(20.0 * math.log10(max(abs(response), 1e-12)))
        boosts[channel] = round_float(max(response_db))
    return boosts


def summarize_profile(root: Path, spec: ProfileSpec) -> dict[str, Any]:
    profile_dir = spec.artifact_dir if spec.artifact_dir.is_absolute() else root / spec.artifact_dir
    metadata_path = profile_dir / "metadata.json"
    report_path = profile_dir / "report.md"
    if not metadata_path.exists():
        raise FileNotFoundError(metadata_path)
    if not report_path.exists():
        raise FileNotFoundError(report_path)

    metadata = load_json(metadata_path)
    validations = metadata["validations"]
    crossover = metadata["crossover"]
    report_text = report_path.read_text()
    return {
        "name": spec.name,
        "artifact_dir": str(profile_dir.relative_to(root) if profile_dir.is_relative_to(root) else profile_dir),
        "command": spec.command,
        "crossover_hz": round_float(crossover["crossover_hz"]),
        "sub_relative_delay_ms": round_float(crossover.get("sub_delay_ms", 0.0)),
        "sub_relative_gain_db": round_float(crossover.get("sub_gain_db", 0.0)),
        "delays_ms": round_mapping(metadata["delays_ms"]),
        "gains_db": round_mapping(metadata["gains_db"]),
        "channel_rms_db": parse_channel_rms(report_text),
        "sum_rms_50_160_db": {
            "left_plus_sub": round_float(validations["left_sum_rms_db"]),
            "right_plus_sub": round_float(validations["right_sum_rms_db"]),
        },
        "worst_cancellation": {
            "db": round_float(validations["worst_cancellation_db"]),
            "hz": round_float(validations["worst_cancellation_hz"]),
        },
        "max_boost_below_25hz_db": max_boost_below_25hz(profile_dir, metadata),
    }


def write_summary(root: Path, specs: Iterable[ProfileSpec], summary_path: Path) -> dict[str, Any]:
    summary = {
        "profiles": [summarize_profile(root, spec) for spec in specs],
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def run_generation_commands(specs: Iterable[ProfileSpec]) -> None:
    for spec in specs:
        subprocess.run(spec.command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--summary", type=Path, default=Path("comparison_summary.json"))
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Run fixed commands into --regenerate-output-root before summarizing.",
    )
    parser.add_argument(
        "--regenerate-output-root",
        type=Path,
        default=Path("Baseline_Runs"),
        help="Output folder used only with --regenerate; Top_Three_Profiles is not overwritten.",
    )
    parser.add_argument("--python", default=default_python())
    args = parser.parse_args()

    root = args.root.resolve()
    summary_path = args.summary if args.summary.is_absolute() else root / args.summary
    specs = default_specs(
        root,
        python=args.python,
        regenerate_output_root=args.regenerate_output_root,
        regenerate=args.regenerate,
    )
    if args.regenerate:
        run_generation_commands(specs)
    write_summary(root, specs, summary_path)
    print(f"Wrote baseline comparison summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
