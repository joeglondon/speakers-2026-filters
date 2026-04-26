# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 54 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: -10.38 dB
- Sub relative delay from crossover search: +3.52 ms
- Exact crossover candidates rescored: 30 of 30
- Crossover search warning: selected crossover is at the minimum search bound (54 Hz)
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- PEQ selection: greedy seeds refined with bounded SciPy soft-L1 least squares.
- FIR requested: legacy smoothed magnitude inverse via frequency sampling and windowed truncation.
- Left FIR used: legacy.
- Right FIR used: legacy.
- Sub FIR used: flat guardrail fallback.
- FIR target delay compensation: Sub FIR target delay is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 1.777 | -0.167 | 1022 | 5 |
| Right | 1.777 | -2.142 | 1022 | 1 |
| Sub | 0.000 | -7.518 | 2040 | 0 |

## Crossover Blocks

- Left: high-pass LR4 at 54 Hz.
- Right: high-pass LR4 at 54 Hz.
- Sub: low-pass LR4 at 54 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 229.25 | +3.00 | 1.699 |
| 2 | PK | 440.19 | -4.34 | 4.125 |
| 3 | PK | 1714.23 | +2.77 | 3.496 |
| 4 | PK | 109.13 | +2.59 | 4.453 |
| 5 | PK | 317.14 | +0.86 | 4.820 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 168.73 | +3.00 | 0.350 |

### Sub

No PEQ filters generated.

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 8.27 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 7.71 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.59 dB.
- Worst crossover-region cancellation indicator: -1.61 dB at 67.75 Hz.
- Left: RMS target error 4.71 dB before correction, 4.27 dB after PEQ+FIR in its correction band.
- Right: RMS target error 4.80 dB before correction, 4.37 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 15.89 dB before correction, 16.01 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%. Sub boost cap below 25 Hz: +0.0 dB; actual max Sub PEQ+FIR boost below 25 Hz is +0.00 dB, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 81.54 | 81.51 | 87.81 | 87.45 | 1.87 | 1.78 |
| 60.06 | 87.16 | 87.27 | 91.77 | 93.14 | 2.50 | 2.70 |
| 69.95 | 77.82 | 82.60 | 84.67 | 85.09 | -1.23 | 0.81 |
| 79.83 | 86.00 | 78.70 | 92.97 | 84.91 | -0.46 | 1.61 |
| 90.09 | 80.28 | 81.01 | 84.29 | 73.81 | -0.27 | 0.05 |
| 99.98 | 81.94 | 80.01 | 85.54 | 83.32 | -0.18 | -0.23 |
| 109.86 | 77.52 | 73.59 | 65.27 | 74.58 | 0.08 | -0.04 |
| 120.12 | 83.58 | 85.31 | 80.19 | 89.65 | 0.15 | -0.12 |
| 139.89 | 75.23 | 74.35 | 86.94 | 87.19 | 0.07 | 0.03 |

## Files

- `peq_left.txt`, `peq_right.txt`, `peq_sub.txt`: PEQ filters and biquad coefficients.
- `peq_left_readable.txt`, `peq_right_readable.txt`, `peq_sub_readable.txt`: human-readable PEQ notes.
- `crossover_left.txt`, `crossover_right.txt`, `crossover_sub.txt`: advanced-mode crossover biquads.
- `fir_left_96k_1022taps.bin`, `fir_right_96k_1022taps.bin`, `fir_sub_96k_2040taps.bin`: FIR File Mode binary float32 coefficients.
- `fir_left_96k_1022taps_manual.txt`, `fir_right_96k_1022taps_manual.txt`, `fir_sub_96k_2040taps_manual.txt`: FIR Manual Mode text coefficients.
- `fir_left_96k_1022taps_raw.txt`, `fir_right_96k_1022taps_raw.txt`, `fir_sub_96k_2040taps_raw.txt`: raw coefficient lists for inspection.
- `settings_summary.txt`: concise miniDSP entry values.
- `validation_response.csv`: compact frequency-response validation data.

## Notes

- These filters are derived from exported in-room measurements. Verify at low volume first, then remeasure through the miniDSP.
- The FIR files are generated as matched acoustic correction filters; output delay handles the main timing alignment.
- Microphone Correction.txt was not reapplied to the exported SPL data.
