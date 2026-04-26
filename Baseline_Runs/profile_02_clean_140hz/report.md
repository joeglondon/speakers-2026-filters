# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 140 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: -0.38 dB
- Sub relative delay from crossover search: -1.73 ms
- Exact crossover candidates rescored: 30 of 30
- Crossover search warning: selected crossover is at the minimum search bound (140 Hz)
- Mic calibration policy: trust-exports. Trusted REW SPL exports as already calibrated; correction samples not applied: 20 Hz +0.17 dB, 50 Hz +0.78 dB, 60 Hz +0.73 dB, 100 Hz +0.64 dB, 1000 Hz +0.01 dB, 10000 Hz +2.77 dB.
- PEQ selection: greedy seeds refined with bounded SciPy soft-L1 least squares.
- FIR requested: legacy smoothed magnitude inverse via frequency sampling and windowed truncation.
- Left FIR used: legacy.
- Right FIR used: legacy.
- Sub FIR used: flat guardrail fallback.
- FIR target delay compensation: Sub FIR target delay is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 7.027 | -8.975 | 1022 | 1 |
| Right | 7.027 | -9.827 | 1022 | 1 |
| Sub | 0.000 | +1.995 | 2040 | 5 |

## Crossover Blocks

- Left: high-pass LR4 at 140 Hz.
- Right: high-pass LR4 at 140 Hz.
- Sub: low-pass LR4 at 140 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 1614.55 | +3.00 | 0.350 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 1408.55 | +3.00 | 0.350 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 58.13 | -8.88 | 7.474 |
| 2 | PK | 101.91 | +0.27 | 2.122 |
| 3 | PK | 80.37 | -5.52 | 7.976 |
| 4 | PK | 144.55 | -4.95 | 7.937 |
| 5 | PK | 44.16 | +1.38 | 3.862 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +76.61 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 7.24 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 6.78 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.50 dB.
- Worst crossover-region cancellation indicator: -1.76 dB at 159.67 Hz.
- Left: RMS target error 7.42 dB before correction, 7.60 dB after PEQ+FIR in its correction band.
- Right: RMS target error 7.53 dB before correction, 7.75 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 5.93 dB before correction, 4.64 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%. Sub boost cap below 25 Hz: +0.0 dB; actual max Sub PEQ+FIR boost below 25 Hz is -0.00 dB, so boosts below 25 Hz were avoided.

## Midbass Alignment

| Hz | Final L+Sub | Final R+Sub | Measured L+Sub | Measured R+Sub | Cancellation L | Cancellation R |
|---:|---:|---:|---:|---:|---:|---:|
| 50.17 | 80.86 | 80.84 | 87.81 | 87.45 | 0.01 | -0.01 |
| 60.06 | 85.96 | 85.99 | 91.77 | 93.14 | -0.12 | -0.09 |
| 69.95 | 80.45 | 80.12 | 84.67 | 85.09 | 0.16 | -0.17 |
| 79.83 | 82.83 | 82.24 | 92.97 | 84.91 | 0.44 | -0.15 |
| 90.09 | 76.83 | 76.31 | 84.29 | 73.81 | 0.58 | 0.06 |
| 99.98 | 78.95 | 79.09 | 85.54 | 83.32 | 0.49 | 0.63 |
| 109.86 | 73.50 | 73.96 | 65.27 | 74.58 | 0.04 | 0.50 |
| 120.12 | 80.93 | 82.84 | 80.19 | 89.65 | -0.94 | 0.97 |
| 139.89 | 79.92 | 78.50 | 86.94 | 87.19 | 0.72 | -0.70 |

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
