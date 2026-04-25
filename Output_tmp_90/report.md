# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 90 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: +3.12 dB
- Sub relative delay from crossover search: -3.65 ms
- Crossover search warning: selected crossover is at the minimum search bound (90 Hz)
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- FIR group delay compensation: Sub FIR is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 8.952 | -2.976 | 1022 | 7 |
| Right | 8.952 | -3.821 | 1022 | 7 |
| Sub | 0.000 | +6.048 | 2040 | 7 |

## Crossover Blocks

- Left: high-pass LR4 at 90 Hz.
- Right: high-pass LR4 at 90 Hz.
- Sub: low-pass LR4 at 90 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 229.25 | +3.00 | 1.508 |
| 2 | PK | 109.13 | +3.00 | 1.112 |
| 3 | PK | 1714.23 | +3.00 | 1.378 |
| 4 | PK | 132.57 | +2.86 | 6.667 |
| 5 | PK | 317.14 | +2.75 | 2.676 |
| 6 | PK | 439.82 | -3.48 | 5.302 |
| 7 | PK | 1339.97 | +2.46 | 3.112 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 174.68 | +3.00 | 3.476 |
| 2 | PK | 76.54 | +3.00 | 1.645 |
| 3 | PK | 252.32 | +3.00 | 1.666 |
| 4 | PK | 1183.59 | +3.00 | 1.392 |
| 5 | PK | 300.29 | +3.00 | 6.667 |
| 6 | PK | 1842.77 | +3.00 | 4.398 |
| 7 | PK | 109.13 | +3.00 | 2.593 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 57.50 | -9.00 | 2.775 |
| 2 | PK | 30.40 | -5.32 | 0.799 |
| 3 | PK | 106.93 | +3.00 | 3.485 |
| 4 | PK | 161.87 | +2.82 | 6.667 |
| 5 | PK | 80.93 | -3.66 | 5.858 |
| 6 | PK | 47.24 | +2.48 | 2.693 |
| 7 | PK | 16.85 | -3.07 | 3.976 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 10.25 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 8.81 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.48 dB.
- Worst crossover-region cancellation indicator: -16.30 dB at 129.64 Hz.
- Left: RMS target error 5.43 dB before correction, 4.46 dB after PEQ+FIR in its correction band.
- Right: RMS target error 5.52 dB before correction, 4.49 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 6.28 dB before correction, 3.32 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 78.44 | 78.20 | 87.81 | 87.45 | -0.80 | -1.04 |
| 60.06 | 85.17 | 84.99 | 91.77 | 93.14 | -1.56 | -1.75 |
| 69.95 | 81.02 | 74.36 | 84.67 | 85.09 | 1.97 | -4.68 |
| 79.83 | 84.00 | 84.03 | 92.97 | 84.91 | 0.18 | 0.20 |
| 90.09 | 76.08 | 82.01 | 84.29 | 73.81 | 0.10 | 6.00 |
| 99.98 | 74.15 | 80.31 | 85.54 | 83.32 | -4.56 | 1.60 |
| 109.86 | 79.09 | 77.28 | 65.27 | 74.58 | 5.70 | 3.90 |
| 120.12 | 85.43 | 77.04 | 80.19 | 89.65 | 4.37 | -5.94 |
| 139.89 | 78.42 | 80.19 | 86.94 | 87.19 | 0.39 | 2.15 |

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
- The FIR filters are linear-phase residual magnitude corrections; output delay handles the main timing alignment.
- Microphone Correction.txt was not reapplied to the exported SPL data.
