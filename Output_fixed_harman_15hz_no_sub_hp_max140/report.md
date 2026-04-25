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
- FIR group delay compensation: Sub FIR is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

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
| 1 | PK | 131.10 | +3.00 | 3.370 |
| 2 | PK | 229.25 | +3.00 | 1.286 |
| 3 | PK | 1714.23 | +3.00 | 1.378 |
| 4 | PK | 316.77 | +2.86 | 2.676 |
| 5 | PK | 439.82 | -3.46 | 5.413 |
| 6 | PK | 1339.97 | +2.46 | 3.112 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 174.68 | +3.00 | 3.126 |
| 2 | PK | 252.32 | +3.00 | 1.606 |
| 3 | PK | 137.70 | +3.00 | 3.213 |
| 4 | PK | 1183.59 | +3.00 | 1.392 |
| 5 | PK | 300.29 | +3.00 | 6.667 |
| 6 | PK | 1842.77 | +3.00 | 4.398 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 179.81 | +3.00 | 6.667 |
| 2 | PK | 106.57 | +3.00 | 2.861 |
| 3 | PK | 15.01 | +3.00 | 6.667 |
| 4 | PK | 45.78 | +3.00 | 1.889 |
| 5 | PK | 57.50 | -5.25 | 4.554 |
| 6 | PK | 19.41 | +1.99 | 1.910 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 6.88 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 6.74 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.48 dB.
- Worst crossover-region cancellation indicator: -4.48 dB at 120.12 Hz.
- Left: RMS target error 5.45 dB before correction, 4.48 dB after PEQ+FIR in its correction band.
- Right: RMS target error 5.54 dB before correction, 4.51 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 7.40 dB before correction, 5.08 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 78.33 | 78.28 | 87.81 | 87.45 | 0.00 | -0.05 |
| 60.06 | 85.84 | 85.91 | 91.77 | 93.14 | -0.22 | -0.14 |
| 69.95 | 78.47 | 77.51 | 84.67 | 85.09 | 0.47 | -0.49 |
| 79.83 | 85.47 | 84.47 | 92.97 | 84.91 | 0.74 | -0.26 |
| 90.09 | 76.69 | 74.72 | 84.29 | 73.81 | 1.63 | -0.34 |
| 99.98 | 79.04 | 78.94 | 85.54 | 83.32 | 1.60 | 1.50 |
| 109.86 | 72.04 | 73.46 | 65.27 | 74.58 | -0.57 | 0.86 |
| 120.12 | 75.89 | 83.75 | 80.19 | 89.65 | -4.48 | 3.38 |
| 139.89 | 81.98 | 77.68 | 86.94 | 87.19 | 2.02 | -2.29 |

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
