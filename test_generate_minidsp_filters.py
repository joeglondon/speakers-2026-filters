import math
import unittest

import numpy as np

import generate_minidsp_filters as gen


class GenerateMiniDSPFiltersTests(unittest.TestCase):
    def test_complex_from_spl_trust_exports_does_not_apply_mic_correction(self):
        measurement = gen.SPLMeasurement(
            name="L 1",
            path=None,
            freq=np.asarray([50.0, 100.0]),
            spl_db=np.asarray([80.0, 70.0]),
            phase_deg=np.asarray([0.0, 0.0]),
            delay_ms=None,
        )
        mic_freq = np.asarray([20.0, 200.0])
        mic_db = np.asarray([10.0, 10.0])

        trusted = gen.complex_from_spl(measurement, mic_freq, mic_db, mic_cal_policy="trust-exports")
        applied = gen.complex_from_spl(measurement, mic_freq, mic_db, mic_cal_policy="apply")

        self.assertAlmostEqual(gen.db(trusted)[0], 80.0, places=6)
        self.assertAlmostEqual(gen.db(applied)[0], 90.0, places=6)

    def test_translate_relative_delay_accounts_for_fir_group_delay(self):
        delays = gen.translate_relative_delay_to_outputs(
            sub_relative_delay_ms=-1.8,
            main_taps=1022,
            sub_taps=2040,
            fs=96000.0,
        )

        self.assertAlmostEqual(delays["left"], 7.102083333333333, places=6)
        self.assertAlmostEqual(delays["right"], 7.102083333333333, places=6)
        self.assertAlmostEqual(delays["sub"], 0.0, places=6)

    def test_output_delay_changes_final_summed_response(self):
        freq = np.asarray([100.0])
        left = np.asarray([1.0 + 0.0j])
        sub = np.asarray([1.0 + 0.0j])

        no_delay = gen.apply_output_delay(left, freq, delay_ms=0.0) + gen.apply_output_delay(
            sub, freq, delay_ms=0.0
        )
        half_cycle_delay = gen.apply_output_delay(left, freq, delay_ms=0.0) + gen.apply_output_delay(
            sub, freq, delay_ms=5.0
        )

        self.assertAlmostEqual(gen.db(no_delay)[0], 20.0 * math.log10(2.0), places=6)
        self.assertLess(gen.db(half_cycle_delay)[0], -200.0)


if __name__ == "__main__":
    unittest.main()
