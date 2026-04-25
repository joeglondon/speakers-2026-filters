# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Target file: `Harman Target extrapolated to 15Hz.txt`
- Crossover: LR4 / 24 dB/oct at 140 Hz
- Sub protective high-pass: none
- Sub correction lower limit: 15 Hz
- Sub relative gain from crossover search: +1.00 dB
- Sub relative delay from crossover search: -1.80 ms
- FIR group delay compensation: Sub FIR is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 7.102 | -2.433 | 1022 | 7 |
| Right | 7.102 | -3.284 | 1022 | 6 |
| Sub | 0.000 | -0.849 | 2040 | 5 |

## Crossover Blocks

- Left: high-pass LR4 at 140 Hz.
- Right: high-pass LR4 at 140 Hz.
- Sub: low-pass LR4 at 140 Hz with no high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 131.10 | +3.00 | 3.289 |
| 2 | PK | 229.25 | +3.00 | 0.874 |
| 3 | PK | 1714.23 | +3.00 | 1.153 |
| 4 | PK | 316.77 | +3.00 | 2.644 |
| 5 | PK | 1339.97 | +2.95 | 2.169 |
| 6 | PK | 17920.17 | +2.44 | 6.667 |
| 7 | PK | 192.63 | +2.34 | 3.222 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 174.68 | +3.00 | 1.377 |
| 2 | PK | 252.32 | +3.00 | 1.585 |
| 3 | PK | 137.70 | +3.00 | 3.213 |
| 4 | PK | 1183.59 | +3.00 | 0.944 |
| 5 | PK | 300.29 | +3.00 | 6.579 |
| 6 | PK | 1842.77 | +3.00 | 4.041 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 179.81 | +3.00 | 6.667 |
| 2 | PK | 106.93 | +3.00 | 3.319 |
| 3 | PK | 57.86 | -5.24 | 4.229 |
| 4 | PK | 15.01 | +3.00 | 6.667 |
| 5 | PK | 46.88 | +2.99 | 2.141 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by +78.85 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 7.94 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 6.68 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.52 dB.
- Worst crossover-region cancellation indicator: -11.21 dB.
- Left: RMS target error 5.64 dB before correction, 4.44 dB after PEQ+FIR in its correction band.
- Right: RMS target error 5.76 dB before correction, 4.58 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 6.55 dB before correction, 4.88 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%, so boosts below 25 Hz were avoided.

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
- The measurement exports appear to have been made with a mic calibration active in REW. The supplied mic calibration file was still applied because the requested plan explicitly included it.
