# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 95 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: +2.00 dB
- Sub relative delay from crossover search: -3.55 ms
- Crossover search warning: selected crossover is at the minimum search bound (95 Hz)
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- FIR group delay compensation: Sub FIR is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 8.852 | -2.976 | 1022 | 7 |
| Right | 8.852 | -3.822 | 1022 | 7 |
| Sub | 0.000 | +4.188 | 2040 | 7 |

## Crossover Blocks

- Left: high-pass LR4 at 95 Hz.
- Right: high-pass LR4 at 95 Hz.
- Sub: low-pass LR4 at 95 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 109.13 | +3.00 | 1.205 |
| 2 | PK | 229.25 | +3.00 | 1.540 |
| 3 | PK | 1714.23 | +3.00 | 1.378 |
| 4 | PK | 132.57 | +3.00 | 6.667 |
| 5 | PK | 316.77 | +2.78 | 2.676 |
| 6 | PK | 439.82 | -3.45 | 5.413 |
| 7 | PK | 1339.97 | +2.46 | 3.112 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 174.68 | +3.00 | 3.476 |
| 2 | PK | 80.93 | +3.00 | 1.850 |
| 3 | PK | 252.32 | +3.00 | 1.660 |
| 4 | PK | 1183.59 | +3.00 | 1.392 |
| 5 | PK | 300.29 | +3.00 | 6.667 |
| 6 | PK | 108.76 | +3.00 | 3.217 |
| 7 | PK | 1842.77 | +3.00 | 4.398 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 57.86 | -9.00 | 2.993 |
| 2 | PK | 170.65 | +3.00 | 6.667 |
| 3 | PK | 106.93 | +3.00 | 3.554 |
| 4 | PK | 30.76 | -4.04 | 1.279 |
| 5 | PK | 80.93 | -3.50 | 5.858 |
| 6 | PK | 47.24 | +2.35 | 2.769 |
| 7 | PK | 16.85 | -2.85 | 3.976 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 9.58 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 8.80 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.48 dB.
- Worst crossover-region cancellation indicator: -11.82 dB at 130.00 Hz.
- Left: RMS target error 5.44 dB before correction, 4.46 dB after PEQ+FIR in its correction band.
- Right: RMS target error 5.52 dB before correction, 4.49 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 6.14 dB before correction, 3.57 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 79.07 | 78.89 | 87.81 | 87.45 | -0.52 | -0.70 |
| 60.06 | 85.05 | 85.09 | 91.77 | 93.14 | -1.36 | -1.33 |
| 69.95 | 80.76 | 74.96 | 84.67 | 85.09 | 1.81 | -3.99 |
| 79.83 | 84.51 | 83.67 | 92.97 | 84.91 | 0.64 | -0.20 |
| 90.09 | 76.87 | 81.45 | 84.29 | 73.81 | 0.89 | 5.47 |
| 99.98 | 76.15 | 80.92 | 85.54 | 83.32 | -2.65 | 2.12 |
| 109.86 | 78.89 | 77.54 | 65.27 | 74.58 | 5.27 | 3.92 |
| 120.12 | 84.88 | 77.99 | 80.19 | 89.65 | 4.25 | -4.20 |
| 139.89 | 79.62 | 79.92 | 86.94 | 87.19 | 1.06 | 1.36 |

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
