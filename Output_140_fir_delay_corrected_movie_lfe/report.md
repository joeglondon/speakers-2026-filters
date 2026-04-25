# miniDSP 2x4 HD Filter Report

## Recommended Settings

- Sample rate: 96 kHz
- Crossover: LR4 / 24 dB/oct at 140 Hz
- Sub protective high-pass: 20 Hz, 2nd-order Butterworth
- Sub relative gain from crossover search: +2.12 dB
- Sub relative delay from crossover search: -1.50 ms
- FIR group delay compensation: Sub FIR is 5.302 ms longer than the Left/Right FIRs, included in the output delay settings below.

| Output | Delay (ms) | Gain (dB) | FIR taps | PEQ filters |
|---|---:|---:|---:|---:|
| Left | 6.802 | -2.775 | 1022 | 6 |
| Right | 6.802 | -3.686 | 1022 | 6 |
| Sub | 0.000 | +1.884 | 2040 | 6 |

## Crossover Blocks

- Left: high-pass LR4 at 140 Hz.
- Right: high-pass LR4 at 140 Hz.
- Sub: low-pass LR4 at 140 Hz plus 20 Hz high-pass.

## PEQ Summary

### Left

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 131.10 | +3.00 | 3.177 |
| 2 | PK | 229.25 | +3.00 | 0.853 |
| 3 | PK | 1714.23 | +3.00 | 0.756 |
| 4 | PK | 316.77 | +3.00 | 2.573 |
| 5 | PK | 1339.97 | +3.00 | 1.094 |
| 6 | PK | 192.63 | +3.00 | 5.098 |

### Right

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 174.68 | +3.00 | 1.342 |
| 2 | PK | 252.32 | +3.00 | 1.521 |
| 3 | PK | 1183.59 | +3.00 | 0.856 |
| 4 | PK | 137.70 | +3.00 | 3.213 |
| 5 | PK | 300.29 | +3.00 | 6.193 |
| 6 | PK | 1780.52 | +3.00 | 0.932 |

### Sub

| # | Type | Fc (Hz) | Gain (dB) | Q |
|---:|---|---:|---:|---:|
| 1 | PK | 179.81 | +3.00 | 6.667 |
| 2 | PK | 57.86 | -5.63 | 4.229 |
| 3 | PK | 106.57 | +3.00 | 3.634 |
| 4 | PK | 46.88 | +2.77 | 2.258 |
| 5 | PK | 80.93 | -3.06 | 6.107 |
| 6 | PK | 142.82 | -2.88 | 4.117 |

## Validation

- Validated 25 SPL files on a 54614-point shared grid.
- Validated 25 impulse files at 48000 Hz, 131072 samples each.
- Target curve shifted by -4.53 dB to match the measured 2-10 kHz average; this shapes the response without forcing an arbitrary playback SPL.
- Tap budget check: Left 1022 + Right 1022 + Sub 2040 + Output 4 reserve 6 = 4090 of 4096 total taps.
- Predicted Left+Sub RMS error, 50-160 Hz: 7.12 dB.
- Predicted Right+Sub RMS error, 50-160 Hz: 5.83 dB.
- Predicted L/R mismatch after correction, 80-10000 Hz: 6.52 dB.
- Worst crossover-region cancellation indicator: -9.45 dB.
- Left: RMS target error 6.03 dB before correction, 4.53 dB after PEQ+FIR in its correction band.
- Right: RMS target error 6.22 dB before correction, 4.63 dB after PEQ+FIR in its correction band.
- Sub: RMS target error 6.04 dB before correction, 4.48 dB after PEQ+FIR in its correction band.
- Distortion guardrail used from Distortion.txt (Sub Only 5); median THD 20-120 Hz is 0.77%, so boosts below 25 Hz were avoided.

## Movie/LFE Trim

This variant also changes only the Sub PEQ relative to the FIR-delay-corrected profile:

- The 57.86 Hz cut is relaxed from -5.63 dB to -2.81 dB.
- A +4.0 dB low shelf at 35 Hz is added for movie/LFE weight.
- Try the plain FIR-delay-corrected package first; use this if movies still feel polite.

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
