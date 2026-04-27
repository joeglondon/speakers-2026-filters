# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 166 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Correction bands: Left 166.3-17999.6 Hz; Right 166.3-17999.6 Hz; Sub 15.0-165.9 Hz.
- Sub relative gain from crossover search: +1.00 dB
- Sub relative delay from crossover search: -3.00 ms
- Exact crossover candidates rescored: 8 of 8
- Room curve overlay: LF +1.00 dB/oct from 200 Hz down to 20 Hz; HF -0.50 dB/oct above 1000 Hz.
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- PEQ selection: greedy seeds refined with bounded SciPy soft-L1 least squares.
- FIR requested: frontier constrained multipoint CVXPY design (96 design points, phase strategy minphase-limited-excess, boost/cut guardrails +3.0/-10.0 dB).
- Left FIR used: legacy fallback.
- Left frontier accepted: no; solver status clarabel_failed; dense max FIR boost +1.72 dB at 612.7 Hz; dense boost over cap -1.28 dB; out-of-band FIR deviation +1.63 dB at 18000.0 Hz; safety refinements 0; rejection reason: solver_status: clarabel_failed.
- Right FIR used: legacy fallback.
- Right frontier accepted: no; solver status frontier_disabled_after_left_rejected; dense max FIR boost +0.00 dB at 0.0 Hz; dense boost over cap +0.00 dB; out-of-band FIR deviation +0.00 dB at 0.0 Hz; safety refinements 0; rejection reason: solver_status: frontier_disabled_after_left_rejected.
- Sub FIR used: flat guardrail fallback.
- Sub frontier accepted: no; solver status frontier_disabled_after_left_rejected; dense max FIR boost +0.00 dB at 0.0 Hz; dense boost over cap +0.00 dB; out-of-band FIR deviation +0.00 dB at 0.0 Hz; safety refinements 0; rejection reason: solver_status: frontier_disabled_after_left_rejected.
- FIR target delay compensation: Sub FIR target delay is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 8.302 | -9.221 | 1022 | 7 |
| Right | 8.302 | -10.096 | 1022 | 5 |
| Sub | 0.000 | +2.911 | 2040 | 5 |

## Crossover Blocks

- Left: high-pass LR4 at 166 Hz.
- Right: high-pass LR4 at 166 Hz.
- Sub: low-pass LR4 at 166 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 218.85 | +3.00 | 1.960 |
| 2 | PK | 1729.63 | +3.00 | 6.780 |
| 3 | PK | 181.69 | +3.00 | 1.196 |
| 4 | PK | 234.03 | +2.84 | 3.160 |
| 5 | PK | 441.11 | -8.24 | 5.395 |
| 6 | PK | 1359.42 | +3.00 | 3.717 |
| 7 | PK | 284.53 | +2.09 | 7.826 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 193.20 | +3.00 | 1.191 |
| 2 | PK | 190.03 | +3.00 | 1.183 |
| 3 | PK | 252.34 | +3.00 | 2.491 |
| 4 | PK | 1182.05 | +3.00 | 3.402 |
| 5 | PK | 1435.74 | +3.00 | 2.397 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 57.67 | -8.89 | 7.511 |
| 2 | PK | 146.30 | -7.99 | 5.572 |
| 3 | PK | 100.92 | +3.00 | 3.071 |
| 4 | PK | 80.83 | -5.01 | 7.983 |
| 5 | PK | 48.04 | +0.66 | 5.814 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Built multipoint SPL and impulse response models; SPL/impulse magnitude RMS deltas left 71.05 dB, right 73.82 dB, sub 35.14 dB, left_sum 70.99 dB, right_sum 74.41 dB.
- Target curve shifted by +77.84 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 6.55 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 6.07 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.51 dB.
- Worst crossover-region cancellation indicator: -2.59 dB at 153.81 Hz.
- Left: RMS target error 7.58 dB before correction, 8.35 dB after PEQ+FIR in its correction band.
- Right: RMS target error 7.73 dB before correction, 8.31 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 5.18 dB before correction, 3.17 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%. Sub boost cap below 25 Hz: +0.0 dB; actual max Sub PEQ+FIR boost below 25 Hz is -0.00 dB, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 81.60 | 81.60 | 87.81 | 87.45 | -0.01 | -0.02 |
| 60.06 | 87.84 | 87.84 | 91.77 | 93.14 | -0.05 | -0.04 |
| 69.95 | 82.04 | 81.87 | 84.67 | 85.09 | 0.08 | -0.09 |
| 79.83 | 85.18 | 85.03 | 92.97 | 84.91 | 0.11 | -0.05 |
| 90.09 | 79.54 | 79.57 | 84.29 | 73.81 | 0.11 | 0.14 |
| 99.98 | 82.78 | 82.95 | 85.54 | 83.32 | 0.05 | 0.22 |
| 109.86 | 77.38 | 77.50 | 65.27 | 74.58 | 0.14 | 0.26 |
| 120.12 | 84.40 | 85.11 | 80.19 | 89.65 | -0.32 | 0.39 |
| 139.89 | 81.21 | 80.11 | 86.94 | 87.19 | 0.57 | -0.53 |

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
