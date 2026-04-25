import math
import tempfile
import unittest
from pathlib import Path

import create_harman_filters as chf


class HarmanFilterGeneratorTests(unittest.TestCase):
    def test_parse_rew_spl_handles_thousands_separators_and_delay(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SPL.txt"
            path.write_text(
                "\n".join(
                    [
                        "* Note: ; Delay -0.0494 ms using estimated IR delay",
                        "* Measurement: L 1",
                        "* Freq(Hz) SPL(dB) Phase(degrees)",
                        "999.7559 70.000 -10.0",
                        "1,000.1221 71.500 -11.0",
                    ]
                )
            )

            measurement = chf.parse_rew_spl(path)

            self.assertEqual(measurement.name, "L 1")
            self.assertAlmostEqual(measurement.delay_ms, -0.0494)
            self.assertEqual(measurement.freq_hz.tolist(), [999.7559, 1000.1221])
            self.assertEqual(measurement.spl_db.tolist(), [70.0, 71.5])
            self.assertEqual(measurement.phase_deg.tolist(), [-10.0, -11.0])

    def test_target_extrapolates_to_zero_hz(self):
        freq, spl = chf.extrapolate_target_to_zero(
            chf.array([20.0, 40.0, 80.0]),
            chf.array([6.0, 5.0, 4.0]),
        )

        self.assertEqual(freq[0], 0.0)
        self.assertEqual(spl[0], 6.0)
        self.assertEqual(freq.tolist()[1:], [20.0, 40.0, 80.0])

    def test_peaking_biquad_is_stable_and_minidsp_signs_are_exported(self):
        biquad = chf.peaking_biquad(100.0, 3.0, 1.2, 96000.0)

        roots = chf.array([1.0, biquad.internal_a1, biquad.internal_a2])
        poles = chf.poly_roots(roots)
        self.assertTrue(all(abs(pole) < 1.0 for pole in poles))
        self.assertAlmostEqual(biquad.a1, -biquad.internal_a1)
        self.assertAlmostEqual(biquad.a2, -biquad.internal_a2)

    def test_fir_exports_exact_tap_count(self):
        taps = chf.make_residual_fir(
            chf.array([0.0, 100.0, 1000.0, 24000.0, 48000.0]),
            chf.array([0.0, -1.0, 0.5, 0.0, 0.0]),
            17,
            96000.0,
        )

        self.assertEqual(len(taps), 17)
        self.assertTrue(math.isfinite(float(taps.sum())))


if __name__ == "__main__":
    unittest.main()
