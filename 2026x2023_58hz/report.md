# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 58 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: -10.62 dB
- Sub relative delay from crossover search: +3.47 ms
- Crossover search warning: selected crossover is at the minimum search bound (58 Hz)
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- FIR group delay compensation: Sub FIR is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 1.827 | -2.979 | 1022 | 7 |
| Right | 1.827 | -3.821 | 1022 | 6 |
| Sub | 0.000 | -7.728 | 2040 | 5 |

## Crossover Blocks

- Left: high-pass LR4 at 58 Hz.
- Right: high-pass LR4 at 58 Hz.
- Sub: low-pass LR4 at 58 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 229.25 | +3.00 | 1.517 |
| 2 | PK | 1714.23 | +3.00 | 1.376 |
| 3 | PK | 109.13 | +3.00 | 2.041 |
| 4 | PK | 316.77 | +2.82 | 2.676 |
| 5 | PK | 132.57 | +2.59 | 5.759 |
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
| 6 | PK | 77.64 | +3.00 | 2.016 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 104.37 | +3.00 | 3.000 |
| 2 | PK | 87.52 | +3.00 | 2.155 |
| 3 | PK | 46.88 | +3.00 | 1.524 |
| 4 | PK | 71.04 | +3.00 | 4.449 |
| 5 | PK | 15.01 | +3.00 | 1.271 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 10.10 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 9.09 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.48 dB.
- Worst crossover-region cancellation indicator: -12.34 dB at 68.12 Hz.
- Left: RMS target error 5.42 dB before correction, 4.46 dB after PEQ+FIR in its correction band.
- Right: RMS target error 5.49 dB before correction, 4.48 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 16.92 dB before correction, 10.94 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 81.04 | 81.18 | 87.81 | 87.45 | 5.63 | 5.14 |
| 60.06 | 88.17 | 88.76 | 91.77 | 93.14 | 4.50 | 5.09 |
| 69.95 | 67.86 | 83.06 | 84.67 | 85.09 | -8.10 | 2.83 |
| 79.83 | 81.38 | 80.96 | 92.97 | 84.91 | -2.59 | 4.94 |
| 90.09 | 77.47 | 79.46 | 84.29 | 73.81 | -1.17 | 0.30 |
| 99.98 | 79.49 | 76.91 | 85.54 | 83.32 | -0.80 | -0.85 |
| 109.86 | 75.75 | 70.99 | 65.27 | 74.58 | 0.46 | 0.23 |
| 120.12 | 82.92 | 82.09 | 80.19 | 89.65 | 0.22 | -0.31 |
| 139.89 | 75.46 | 71.19 | 86.94 | 87.19 | 0.26 | -0.38 |

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
