# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 169 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: -1.38 dB
- Sub relative delay from crossover search: -3.25 ms
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- FIR group delay compensation: Sub FIR is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 8.552 | -2.978 | 1022 | 7 |
| Right | 8.552 | -3.834 | 1022 | 6 |
| Sub | 0.000 | -6.118 | 2040 | 6 |

## Crossover Blocks

- Left: high-pass LR4 at 169 Hz.
- Right: high-pass LR4 at 169 Hz.
- Sub: low-pass LR4 at 169 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 228.88 | +3.00 | 0.938 |
| 2 | PK | 143.92 | +3.00 | 2.780 |
| 3 | PK | 1714.23 | +3.00 | 1.378 |
| 4 | PK | 316.77 | +2.82 | 2.264 |
| 5 | PK | 439.82 | -3.82 | 4.558 |
| 6 | PK | 1339.97 | +2.45 | 3.117 |
| 7 | PK | 178.71 | +2.28 | 6.667 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 174.68 | +3.00 | 2.215 |
| 2 | PK | 143.92 | +3.00 | 6.667 |
| 3 | PK | 251.22 | +3.00 | 1.581 |
| 4 | PK | 1183.59 | +3.00 | 1.392 |
| 5 | PK | 298.83 | +3.00 | 6.415 |
| 6 | PK | 1842.77 | +3.00 | 4.392 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 179.81 | +3.00 | 6.667 |
| 2 | PK | 106.57 | +3.00 | 2.681 |
| 3 | PK | 15.01 | +3.00 | 6.667 |
| 4 | PK | 45.78 | +3.00 | 1.740 |
| 5 | PK | 57.50 | -3.94 | 5.469 |
| 6 | PK | 19.41 | +2.68 | 1.357 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 8.55 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 7.57 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.50 dB.
- Worst crossover-region cancellation indicator: -8.99 dB at 154.54 Hz.
- Left: RMS target error 5.45 dB before correction, 4.46 dB after PEQ+FIR in its correction band.
- Right: RMS target error 5.56 dB before correction, 4.52 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 7.65 dB before correction, 5.01 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 77.85 | 77.82 | 87.81 | 87.45 | -0.06 | -0.08 |
| 60.06 | 86.06 | 86.09 | 91.77 | 93.14 | -0.12 | -0.10 |
| 69.95 | 77.70 | 77.10 | 84.67 | 85.09 | 0.27 | -0.33 |
| 79.83 | 84.18 | 83.86 | 92.97 | 84.91 | 0.23 | -0.09 |
| 90.09 | 74.91 | 74.77 | 84.29 | 73.81 | 0.60 | 0.45 |
| 99.98 | 76.98 | 77.52 | 85.54 | 83.32 | 0.21 | 0.75 |
| 109.86 | 72.94 | 73.07 | 65.27 | 74.58 | 0.82 | 0.94 |
| 120.12 | 79.58 | 80.95 | 80.19 | 89.65 | -0.67 | 0.70 |
| 139.89 | 81.80 | 79.57 | 86.94 | 87.19 | 1.26 | -0.96 |

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
