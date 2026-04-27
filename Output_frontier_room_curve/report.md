# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 140 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Correction bands: Left 140.3-17999.6 Hz; Right 140.3-17999.6 Hz; Sub 15.0-139.9 Hz.
- Sub relative gain from crossover search: +1.62 dB
- Sub relative delay from crossover search: -1.90 ms
- Exact crossover candidates rescored: 8 of 8
- Crossover search warning: selected crossover is at the maximum search bound (140 Hz)
- Room curve overlay: LF +1.00 dB/oct from 200 Hz down to 20 Hz; HF -0.50 dB/oct above 1000 Hz.
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- PEQ selection: greedy seeds refined with bounded SciPy soft-L1 least squares.
- FIR requested: frontier constrained multipoint CVXPY design (96 design points, phase strategy minphase-limited-excess, boost/cut guardrails +3.0/-10.0 dB).
- Left FIR used: frontier cvxpy.
- Left frontier accepted: yes; solver status optimal_inaccurate; dense max FIR boost +3.00 dB at 5668.6 Hz; dense boost over cap +0.00 dB; safety refinements 0; inaccurate status certified by dense guardrail.
- Right FIR used: frontier cvxpy.
- Right frontier accepted: yes; solver status optimal_inaccurate; dense max FIR boost +3.04 dB at 17999.6 Hz; dense boost over cap +0.04 dB; safety refinements 0; inaccurate status certified by dense guardrail.
- Sub FIR used: frontier cvxpy.
- Sub frontier accepted: yes; solver status optimal; dense max FIR boost +0.30 dB at 83.1 Hz; dense boost over cap -0.16 dB; safety refinements 0.
- FIR target delay compensation: Sub FIR target delay is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 7.202 | -9.212 | 1022 | 1 |
| Right | 7.202 | -10.096 | 1022 | 1 |
| Sub | 0.000 | +3.756 | 2040 | 5 |

## Crossover Blocks

- Left: high-pass LR4 at 140 Hz.
- Right: high-pass LR4 at 140 Hz.
- Sub: low-pass LR4 at 140 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 1287.83 | +3.00 | 0.350 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 1310.30 | +3.00 | 0.350 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 58.39 | -8.99 | 6.658 |
| 2 | PK | 137.61 | -5.40 | 7.046 |
| 3 | PK | 102.43 | +3.00 | 3.497 |
| 4 | PK | 80.53 | -6.60 | 7.781 |
| 5 | PK | 44.07 | +1.45 | 3.801 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Built multipoint SPL and impulse response models; SPL/impulse magnitude RMS deltas left 71.05 dB, right 73.82 dB, sub 35.14 dB, left_sum 70.99 dB, right_sum 74.41 dB.
- Target curve shifted by +77.84 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 6.05 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 5.89 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.50 dB.
- Worst crossover-region cancellation indicator: -1.42 dB at 159.67 Hz.
- Left: RMS target error 7.56 dB before correction, 7.54 dB after PEQ+FIR in its correction band.
- Right: RMS target error 7.73 dB before correction, 7.43 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 4.87 dB before correction, 3.03 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%. Sub boost cap below 25 Hz: +0.0 dB; actual max Sub PEQ+FIR boost below 25 Hz is -0.16 dB, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 82.52 | 82.50 | 87.81 | 87.45 | 0.00 | -0.01 |
| 60.06 | 87.29 | 87.30 | 91.77 | 93.14 | -0.09 | -0.08 |
| 69.95 | 82.17 | 81.88 | 84.67 | 85.09 | 0.13 | -0.16 |
| 79.83 | 84.20 | 83.78 | 92.97 | 84.91 | 0.30 | -0.12 |
| 90.09 | 79.53 | 79.41 | 84.29 | 73.81 | 0.30 | 0.18 |
| 99.98 | 83.00 | 83.18 | 85.54 | 83.32 | 0.21 | 0.39 |
| 109.86 | 77.14 | 77.47 | 65.27 | 74.58 | -0.01 | 0.32 |
| 120.12 | 83.29 | 84.79 | 80.19 | 89.65 | -0.70 | 0.81 |
| 139.89 | 80.29 | 78.91 | 86.94 | 87.19 | 0.70 | -0.67 |

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
