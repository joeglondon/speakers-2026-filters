# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 60 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: -10.75 dB
- Sub relative delay from crossover search: +3.47 ms
- Crossover search warning: selected crossover is at the minimum search bound (60 Hz)
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- FIR group delay compensation: Sub FIR is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 1.827 | -2.979 | 1022 | 7 |
| Right | 1.827 | -3.821 | 1022 | 6 |
| Sub | 0.000 | -8.254 | 2040 | 5 |

## Crossover Blocks

- Left: high-pass LR4 at 60 Hz.
- Right: high-pass LR4 at 60 Hz.
- Sub: low-pass LR4 at 60 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 229.25 | +3.00 | 1.517 |
| 2 | PK | 1714.23 | +3.00 | 1.376 |
| 3 | PK | 109.13 | +3.00 | 2.020 |
| 4 | PK | 316.77 | +2.82 | 2.676 |
| 5 | PK | 132.57 | +2.60 | 5.759 |
| 6 | PK | 1339.97 | +2.46 | 3.112 |
| 7 | PK | 439.82 | -3.44 | 5.451 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 174.68 | +3.00 | 3.600 |
| 2 | PK | 252.32 | +3.00 | 1.666 |
| 3 | PK | 1183.59 | +3.00 | 1.392 |
| 4 | PK | 300.29 | +3.00 | 6.667 |
| 5 | PK | 1842.77 | +3.00 | 4.398 |
| 6 | PK | 77.64 | +3.00 | 1.918 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 106.93 | +3.00 | 2.737 |
| 2 | PK | 89.72 | +3.00 | 2.070 |
| 3 | PK | 46.51 | +3.00 | 1.488 |
| 4 | PK | 15.01 | +3.00 | 1.239 |
| 5 | PK | 71.04 | +3.00 | 3.742 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 10.35 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 9.11 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.48 dB.
- Worst crossover-region cancellation indicator: -14.83 dB at 68.12 Hz.
- Left: RMS target error 5.42 dB before correction, 4.46 dB after PEQ+FIR in its correction band.
- Right: RMS target error 5.49 dB before correction, 4.48 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 18.09 dB before correction, 12.07 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 80.66 | 80.80 | 87.81 | 87.45 | 5.77 | 5.45 |
| 60.06 | 88.15 | 88.74 | 91.77 | 93.14 | 4.16 | 4.75 |
| 69.95 | 66.59 | 82.89 | 84.67 | 85.09 | -9.05 | 3.00 |
| 79.83 | 80.99 | 81.07 | 92.97 | 84.91 | -2.78 | 5.29 |
| 90.09 | 77.23 | 79.37 | 84.29 | 73.81 | -1.29 | 0.31 |
| 99.98 | 79.33 | 76.76 | 85.54 | 83.32 | -0.89 | -0.96 |
| 109.86 | 75.77 | 70.99 | 65.27 | 74.58 | 0.53 | 0.23 |
| 120.12 | 82.94 | 82.04 | 80.19 | 89.65 | 0.25 | -0.36 |
| 139.89 | 75.53 | 71.13 | 86.94 | 87.19 | 0.31 | -0.45 |

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
