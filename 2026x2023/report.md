# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 80 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: +2.00 dB
- Sub relative delay from crossover search: -3.90 ms
- Crossover search warning: selected crossover is at the minimum search bound (80 Hz)
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- FIR group delay compensation: Sub FIR is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 9.202 | -2.975 | 1022 | 6 |
| Right | 9.202 | -3.821 | 1022 | 6 |
| Sub | 0.000 | +4.018 | 2040 | 7 |

## Crossover Blocks

- Left: high-pass LR4 at 80 Hz.
- Right: high-pass LR4 at 80 Hz.
- Sub: low-pass LR4 at 80 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 229.25 | +3.00 | 1.510 |
| 2 | PK | 109.13 | +3.00 | 1.371 |
| 3 | PK | 1714.23 | +3.00 | 1.378 |
| 4 | PK | 69.95 | +3.00 | 5.469 |
| 5 | PK | 316.77 | +2.79 | 2.676 |
| 6 | PK | 132.57 | +2.67 | 6.667 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 174.68 | +3.00 | 3.516 |
| 2 | PK | 252.32 | +3.00 | 1.660 |
| 3 | PK | 77.27 | +3.00 | 1.287 |
| 4 | PK | 1183.59 | +3.00 | 1.392 |
| 5 | PK | 300.29 | +3.00 | 6.667 |
| 6 | PK | 1842.77 | +3.00 | 4.398 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 57.50 | -8.51 | 3.338 |
| 2 | PK | 106.93 | +3.00 | 1.817 |
| 3 | PK | 30.76 | -3.99 | 1.279 |
| 4 | PK | 47.24 | +2.31 | 2.769 |
| 5 | PK | 133.67 | +2.05 | 5.457 |
| 6 | PK | 16.85 | -2.77 | 3.976 |
| 7 | PK | 80.57 | -2.63 | 6.667 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 9.98 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 9.36 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.47 dB.
- Worst crossover-region cancellation indicator: -19.07 dB at 129.64 Hz.
- Left: RMS target error 5.43 dB before correction, 4.50 dB after PEQ+FIR in its correction band.
- Right: RMS target error 5.51 dB before correction, 4.49 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 7.50 dB before correction, 4.42 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 78.61 | 77.92 | 87.81 | 87.45 | -1.15 | -1.84 |
| 60.06 | 83.90 | 83.79 | 91.77 | 93.14 | -2.69 | -2.80 |
| 69.95 | 82.45 | 74.35 | 84.67 | 85.09 | 3.46 | -4.64 |
| 79.83 | 83.68 | 84.33 | 92.97 | 84.91 | -0.02 | 0.63 |
| 90.09 | 76.71 | 81.82 | 84.29 | 73.81 | -0.14 | 5.13 |
| 99.98 | 74.50 | 78.43 | 85.54 | 83.32 | -4.27 | 2.15 |
| 109.86 | 78.28 | 74.74 | 65.27 | 74.58 | 4.26 | 4.67 |
| 120.12 | 85.26 | 76.83 | 80.19 | 89.65 | 3.32 | -5.01 |
| 139.89 | 77.63 | 77.24 | 86.94 | 87.19 | 2.31 | 1.92 |

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
