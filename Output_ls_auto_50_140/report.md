# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 140 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: -0.50 dB
- Sub relative delay from crossover search: -1.80 ms
- Crossover search warning: selected crossover is at the maximum search bound (140 Hz)
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- PEQ selection: greedy seeds refined with bounded SciPy soft-L1 least squares.
- FIR solver: weighted regularized least-squares acoustic inverse (1024 design points, lambda 0.01, boost/cut guardrails +3.0/-10.0 dB).
- FIR target delay compensation: Sub FIR target delay is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 7.102 | -2.975 | 1022 | 6 |
| Right | 7.102 | -3.827 | 1022 | 6 |
| Sub | 0.000 | -4.101 | 2040 | 6 |

## Crossover Blocks

- Left: high-pass LR4 at 140 Hz.
- Right: high-pass LR4 at 140 Hz.
- Sub: low-pass LR4 at 140 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 149.62 | +3.00 | 0.350 |
| 2 | PK | 158.85 | +3.00 | 0.360 |
| 3 | PK | 2784.77 | +3.00 | 0.368 |
| 4 | PK | 168.88 | +3.00 | 0.382 |
| 5 | PK | 437.74 | -9.00 | 4.288 |
| 6 | PK | 1468.48 | +3.00 | 1.793 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 150.56 | +3.00 | 0.669 |
| 2 | PK | 157.58 | +3.00 | 0.694 |
| 3 | PK | 154.16 | +3.00 | 0.684 |
| 4 | PK | 2524.50 | +3.00 | 0.350 |
| 5 | PK | 254.34 | +3.00 | 2.247 |
| 6 | PK | 1297.29 | +3.00 | 1.007 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 104.86 | +3.00 | 4.685 |
| 2 | PK | 104.78 | +3.00 | 4.685 |
| 3 | PK | 19.52 | +3.00 | 3.111 |
| 4 | PK | 43.81 | +3.00 | 3.007 |
| 5 | PK | 58.12 | -8.99 | 7.449 |
| 6 | PK | 42.12 | +3.00 | 0.350 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 12.27 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 10.87 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.83 dB.
- Worst crossover-region cancellation indicator: -4.65 dB at 139.89 Hz.
- Left: RMS target error 5.45 dB before correction, 10.19 dB after PEQ+FIR in its correction band.
- Right: RMS target error 5.54 dB before correction, 7.28 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 7.40 dB before correction, 9.15 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 71.25 | 71.16 | 87.81 | 87.45 | 0.69 | 0.59 |
| 60.06 | 75.67 | 76.76 | 91.77 | 93.14 | -0.89 | 0.21 |
| 69.95 | 73.08 | 71.75 | 84.67 | 85.09 | 1.43 | 0.10 |
| 79.83 | 80.24 | 78.59 | 92.97 | 84.91 | 1.26 | -0.40 |
| 90.09 | 72.51 | 69.86 | 84.29 | 73.81 | 1.19 | -1.46 |
| 99.98 | 76.47 | 78.51 | 85.54 | 83.32 | -0.80 | 1.23 |
| 109.86 | 74.50 | 72.87 | 65.27 | 74.58 | 1.41 | -0.22 |
| 120.12 | 79.12 | 82.70 | 80.19 | 89.65 | 0.32 | 3.91 |
| 139.89 | 74.30 | 69.53 | 86.94 | 87.19 | 0.12 | -4.65 |

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
