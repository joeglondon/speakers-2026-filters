# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 118 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: +2.00 dB
- Sub relative delay from crossover search: -1.50 ms
- Exact crossover candidates rescored: 30 of 30
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- PEQ selection: greedy seeds refined with bounded SciPy soft-L1 least squares.
- FIR requested: legacy smoothed magnitude inverse via frequency sampling and windowed truncation.
- Left FIR used: legacy.
- Right FIR used: legacy.
- Sub FIR used: legacy.
- FIR target delay compensation: Sub FIR target delay is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 6.802 | -8.977 | 1022 | 1 |
| Right | 6.802 | -9.823 | 1022 | 1 |
| Sub | 0.000 | +2.671 | 2040 | 6 |

## Crossover Blocks

- Left: high-pass LR4 at 118 Hz.
- Right: high-pass LR4 at 118 Hz.
- Sub: low-pass LR4 at 118 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 1749.04 | +3.00 | 0.350 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 1335.19 | +3.00 | 0.350 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 58.72 | -9.00 | 5.105 |
| 2 | PK | 80.14 | -7.66 | 7.190 |
| 3 | PK | 103.10 | +2.57 | 3.337 |
| 4 | PK | 28.94 | -4.86 | 2.177 |
| 5 | PK | 44.61 | +3.00 | 4.146 |
| 6 | PK | 143.43 | -4.44 | 7.973 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 7.40 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 6.91 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.50 dB.
- Worst crossover-region cancellation indicator: -2.19 dB at 159.67 Hz.
- Left: RMS target error 7.43 dB before correction, 7.55 dB after PEQ+FIR in its correction band.
- Right: RMS target error 7.53 dB before correction, 7.78 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 6.32 dB before correction, 4.68 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%. Sub boost cap below 25 Hz: +0.0 dB; actual max Sub PEQ+FIR boost below 25 Hz is -0.12 dB, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 80.81 | 80.77 | 87.81 | 87.45 | 0.03 | -0.01 |
| 60.06 | 84.95 | 85.02 | 91.77 | 93.14 | -0.23 | -0.16 |
| 69.95 | 79.65 | 78.90 | 84.67 | 85.09 | 0.36 | -0.39 |
| 79.83 | 81.65 | 80.44 | 92.97 | 84.91 | 0.87 | -0.33 |
| 90.09 | 77.56 | 77.16 | 84.29 | 73.81 | 0.80 | 0.41 |
| 99.98 | 80.84 | 81.13 | 85.54 | 83.32 | 0.58 | 0.86 |
| 109.86 | 74.88 | 75.53 | 65.27 | 74.58 | -0.02 | 0.63 |
| 120.12 | 80.67 | 83.72 | 80.19 | 89.65 | -1.52 | 1.53 |
| 139.89 | 79.27 | 77.22 | 86.94 | 87.19 | 1.01 | -1.04 |

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
