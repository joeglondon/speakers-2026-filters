# Top Three miniDSP Profiles

These are the three best audition candidates to load alongside the old profile already in miniDSP slot 01.

## Profile 02 - clean_140hz

Source folder: `Output_fixed_harman_15hz_no_sub_hp_max140`

- Crossover: 140 Hz LR4 / 24 dB/oct
- Left: delay 7.102 ms, gain -2.975 dB
- Right: delay 7.102 ms, gain -3.827 dB
- Sub: delay 0.000 ms, gain -4.101 dB
- Why this one: cleanest predicted crossover behavior and lowest 50-160 Hz summed RMS error.

## Profile 03 - 2023ish_54hz

Source folder: `2026x2023_54hz`

- Crossover: 54 Hz LR4 / 24 dB/oct
- Left: delay 1.827 ms, gain -2.980 dB
- Right: delay 1.827 ms, gain -3.823 dB
- Sub: delay 0.000 ms, gain -7.385 dB
- Why this one: best low-crossover candidate; lets the mains carry the midbass closest to the old 2023-ish approach.

## Profile 04 - compromise_95hz

Source folder: `Output_tmp_95`

- Crossover: 95 Hz LR4 / 24 dB/oct
- Left: delay 8.852 ms, gain -2.976 dB
- Right: delay 8.852 ms, gain -3.822 dB
- Sub: delay 0.000 ms, gain +4.188 dB
- Why this one: below 100 Hz compromise; less extreme than 80 Hz, though not as clean as 140 Hz.

## Loading Notes

- Use each profile folder's `settings_summary.txt` as the miniDSP entry checklist.
- Load PEQ files, crossover files or equivalent Basic LR4 settings, FIR files, delays, and output gains together as a matched set.
- Verify at low volume first, then remeasure the loaded profile before judging it too hard.
