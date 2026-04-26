# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 126 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: +0.00 dB
- Sub relative delay from crossover search: -1.50 ms
- Exact crossover candidates rescored: 8 of 8
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- PEQ selection: greedy seeds refined with bounded SciPy soft-L1 least squares.
- FIR requested: frontier constrained multipoint CVXPY design (96 design points, phase strategy minphase-limited-excess, boost/cut guardrails +3.0/-10.0 dB).
- Left FIR used: frontier cvxpy.
- Left frontier accepted: yes; solver status optimal_inaccurate; dense max FIR boost +3.04 dB at 16700.3 Hz; dense boost over cap +0.04 dB; safety refinements 0; inaccurate status certified by dense guardrail.
- Right FIR used: frontier cvxpy.
- Right frontier accepted: yes; solver status optimal_inaccurate; dense max FIR boost +3.03 dB at 17999.6 Hz; dense boost over cap +0.03 dB; safety refinements 0; inaccurate status certified by dense guardrail.
- Sub FIR used: flat guardrail fallback.
- Sub frontier accepted: no; solver status optimal; dense max FIR boost +0.06 dB at 119.8 Hz; dense boost over cap -1.01 dB; safety refinements 0; rejection reason: frontier_worse_than_reliable.
- FIR target delay compensation: Sub FIR target delay is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 6.802 | -8.976 | 1022 | 1 |
| Right | 6.802 | -9.823 | 1022 | 1 |
| Sub | 0.000 | +2.177 | 2040 | 4 |

## Crossover Blocks

- Left: high-pass LR4 at 126 Hz.
- Right: high-pass LR4 at 126 Hz.
- Sub: low-pass LR4 at 126 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 1639.82 | +3.00 | 0.350 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 1384.12 | +3.00 | 0.350 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 57.86 | -7.15 | 3.686 |
| 2 | PK | 106.93 | +2.33 | 3.710 |
| 3 | PK | 80.93 | -3.28 | 6.107 |
| 4 | PK | 142.82 | -2.14 | 6.008 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Built multipoint SPL and impulse response models; SPL/impulse magnitude RMS deltas left 71.05 dB, right 73.82 dB, sub 35.14 dB, left_sum 70.99 dB, right_sum 74.41 dB.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 7.10 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 6.83 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.49 dB.
- Worst crossover-region cancellation indicator: -1.53 dB at 159.67 Hz.
- Left: RMS target error 7.43 dB before correction, 7.49 dB after PEQ+FIR in its correction band.
- Right: RMS target error 7.53 dB before correction, 7.34 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 6.15 dB before correction, 5.09 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%. Sub boost cap below 25 Hz: +0.0 dB; actual max Sub PEQ+FIR boost below 25 Hz is -0.00 dB, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 78.57 | 78.52 | 87.81 | 87.45 | 0.01 | -0.03 |
| 60.06 | 86.29 | 86.32 | 91.77 | 93.14 | -0.14 | -0.12 |
| 69.95 | 79.37 | 78.75 | 84.67 | 85.09 | 0.27 | -0.35 |
| 79.83 | 84.41 | 83.76 | 92.97 | 84.91 | 0.46 | -0.20 |
| 90.09 | 76.89 | 76.28 | 84.29 | 73.81 | 0.76 | 0.15 |
| 99.98 | 79.63 | 79.94 | 85.54 | 83.32 | 0.56 | 0.86 |
| 109.86 | 74.25 | 74.90 | 65.27 | 74.58 | -0.06 | 0.59 |
| 120.12 | 80.42 | 83.18 | 80.19 | 89.65 | -1.28 | 1.49 |
| 139.89 | 80.23 | 78.61 | 86.94 | 87.19 | 0.76 | -0.86 |

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
