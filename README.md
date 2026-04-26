# Speakers 2026 miniDSP Filters

This repository contains the 2026 room measurements, target curves, calibration data, scripts, generated miniDSP filters, and final audition profiles for a left/right/sub speaker setup.

The work here is centered on creating miniDSP 2x4 HD filters from repeated REW measurements for:

- Left channel
- Right channel
- Left + Sub
- Right + Sub
- Sub Only

The measurement set includes exported SPL files, impulse files, a measurement microphone calibration file, REW target files, and the original `.mdat` project.

## Final Audition Profiles

The most useful output folder is:

- `Top_Three_Profiles/`

That folder is organized for loading three new miniDSP profiles alongside the old profile already loaded in slot 01:

- `Profile_02_clean_140hz` - the cleanest predicted crossover behavior and best objective reference.
- `Profile_03_2023ish_54hz` - the best low-crossover candidate, intended to let the mains carry more of the midbass like the older 2023 setup.
- `Profile_04_compromise_95hz` - a below-100 Hz compromise profile.

Each profile folder includes:

- `settings_summary.txt` - the miniDSP entry checklist.
- `report.md` - detailed filter report and validation notes.
- `peq_left.txt`, `peq_right.txt`, `peq_sub.txt` - miniDSP PEQ biquads.
- `crossover_left.txt`, `crossover_right.txt`, `crossover_sub.txt` - advanced-mode crossover biquads.
- FIR files in both binary File Mode and text Manual Mode formats.
- `validation_response.csv`, `midbass_alignment.csv`, and `metadata.json` diagnostics.

## Main Scripts

- `generate_minidsp_filters.py` - the primary filter-generation script. It reads REW exports, averages measurements, handles mic-cal policy, optimizes crossover/delay/gain, creates PEQ and FIR filters, and writes reports/diagnostics.
- `create_harman_filters.py` - an experimental from-scratch filter generator kept for comparison.
- `test_generate_minidsp_filters.py` and `test_create_harman_filters.py` - unit tests for parsing, mic-cal handling, delay translation, FIR export sizing, and target extrapolation behavior.

Install the Python dependencies before generating filters:

```bash
/Users/josephlondon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pip install -r requirements.txt
```

The primary script uses NumPy for DSP/FIR math and SciPy for bounded nonlinear PEQ refinement.

`generate_minidsp_filters.py` now supports two FIR solvers:

- `--fir-method ls` - weighted, regularized least-squares FIR generation. This is the default and is intended for experimentation.
- `--fir-method legacy` - the older smoothed magnitude inverse using frequency sampling, inverse FFT, truncation, and windowing.

`Output_ls_auto_50_140/` is the first auto-crossover LS output. It is included as a solver experiment, not as the current recommended listening profile: its generated report shows worse magnitude RMS than the legacy/reference 140 Hz output, even though crossover cancellation is improved.

Example:

```bash
/Users/josephlondon/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 generate_minidsp_filters.py \
  --root . \
  --output 2026x2023_54hz \
  --target-file "Harman Target extrapolated to 15Hz.txt" \
  --min-crossover 54 \
  --max-crossover 54 \
  --prefer-crossover 54 \
  --sub-low-freq 15 \
  --sub-highpass-hz 0 \
  --mic-cal-policy trust-exports
```

## Measurement And Target Files

- `All Measurements (center).mdat` - original REW measurement project.
- `SPL/` - exported frequency response measurements.
- `Impulse/` - exported impulse measurements.
- `Distortion/` - distortion export used as a low-frequency boost guardrail.
- `Microphone Correction.txt` - measurement microphone calibration file.
- `Harman Target.txt`, `Harman Audio Test System Target.txt`, and extrapolated target variants - target curves used during filter generation.

The generated filters generally use the `trust-exports` mic-cal policy, meaning the REW SPL exports are treated as already calibrated rather than applying `Microphone Correction.txt` a second time.

## Important Listening Notes

The objectively cleanest generated profile is the 140 Hz LR4 version. It has the best modeled crossover-region behavior.

The more subjective, 2023-inspired profile is the 54 Hz LR4 version. It keeps more midbass responsibility on the mains and is probably the most relevant audition candidate if the goal is to recover the older "earthshattering" character, even though its modeled response is not as clean.

The 95 Hz LR4 version is included as a compromise because it stays below 100 Hz while avoiding some of the roughest behavior seen in the forced 80 Hz run.

All profiles should be loaded as complete matched sets: PEQ, crossover, FIR, delay, and gain together. Verify at low volume first, then remeasure the loaded miniDSP profile before making final listening judgments.

## Historical And Comparison Outputs

Several earlier output folders are kept for traceability. They include older 140 Hz attempts, fixed-script outputs, lower-crossover experiments, REW-only IIR comparisons, and the older 2023 `best/` filters.

These folders are useful for understanding what changed, but `Top_Three_Profiles/` is the recommended starting point for auditioning.
