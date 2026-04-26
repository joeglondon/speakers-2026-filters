# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 95 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: +2.00 dB
- Sub relative delay from crossover search: -3.45 ms
- Exact crossover candidates rescored: 30 of 30
- Crossover search warning: selected crossover is at the minimum search bound (95 Hz)
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- PEQ selection: greedy seeds refined with bounded SciPy soft-L1 least squares.
- FIR requested: legacy smoothed magnitude inverse via frequency sampling and windowed truncation.
- Left FIR used: legacy.
- Right FIR used: legacy.
- Sub FIR used: flat guardrail fallback.
- FIR target delay compensation: Sub FIR target delay is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 8.752 | -2.553 | 1022 | 1 |
| Right | 8.752 | -1.200 | 1022 | 1 |
| Sub | 0.000 | +6.856 | 2040 | 7 |

## Crossover Blocks

- Left: high-pass LR4 at 95 Hz.
- Right: high-pass LR4 at 95 Hz.
- Sub: low-pass LR4 at 95 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 168.95 | +3.00 | 0.350 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 129.35 | +3.00 | 0.350 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 58.87 | -9.00 | 4.184 |
| 2 | PK | 166.43 | +3.00 | 7.937 |
| 3 | PK | 28.77 | -7.57 | 1.643 |
| 4 | PK | 104.04 | +2.14 | 3.220 |
| 5 | PK | 79.65 | -8.09 | 7.028 |
| 6 | PK | 45.58 | +3.00 | 5.584 |
| 7 | PK | 16.70 | -6.17 | 7.990 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 9.87 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 7.69 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.54 dB.
- Worst crossover-region cancellation indicator: -11.42 dB at 149.05 Hz.
- Left: RMS target error 5.04 dB before correction, 4.58 dB after PEQ+FIR in its correction band.
- Right: RMS target error 4.73 dB before correction, 4.31 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 6.29 dB before correction, 3.42 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%. Sub boost cap below 25 Hz: +0.0 dB; actual max Sub PEQ+FIR boost below 25 Hz is -0.00 dB, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 82.05 | 81.58 | 87.81 | 87.45 | -0.44 | -0.91 |
| 60.06 | 85.69 | 85.12 | 91.77 | 93.14 | -1.47 | -2.04 |
| 69.95 | 81.95 | 75.13 | 84.67 | 85.09 | 1.82 | -5.00 |
| 79.83 | 81.48 | 81.61 | 92.97 | 84.91 | 0.37 | 0.50 |
| 90.09 | 75.60 | 82.81 | 84.29 | 73.81 | -1.10 | 5.92 |
| 99.98 | 74.97 | 81.32 | 85.54 | 83.32 | -4.35 | 2.00 |
| 109.86 | 78.65 | 78.00 | 65.27 | 74.58 | 5.13 | 4.48 |
| 120.12 | 85.08 | 80.70 | 80.19 | 89.65 | 4.50 | -3.88 |
| 139.89 | 80.26 | 81.51 | 86.94 | 87.19 | 1.05 | 2.30 |

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
