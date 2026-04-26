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

    def test_ls_fir_preserves_even_tap_count_and_returns_real_finite_taps(self):
        freq = np.geomspace(20.0, 20_000.0, 256)
        measured = np.ones_like(freq, dtype=np.complex128)
        target_db = np.zeros_like(freq)
        mask = (freq >= 80.0) & (freq <= 8_000.0)

        fir = gen.make_fir_ls(
            freq,
            measured,
            target_db,
            taps=32,
            correction_mask=mask,
            grid_points=96,
            lambda_reg=0.001,
        )

        self.assertEqual(fir.shape, (32,))
        self.assertTrue(np.all(np.isfinite(fir)))
        self.assertTrue(np.isrealobj(fir))

    def test_ls_fir_reduces_acoustic_error_for_low_measured_response(self):
        freq = np.geomspace(40.0, 10_000.0, 256)
        measured = np.ones_like(freq, dtype=np.complex128) * (10.0 ** (-6.0 / 20.0))
        target_db = np.zeros_like(freq)
        mask = (freq >= 80.0) & (freq <= 8_000.0)

        fir = gen.make_fir_ls(
            freq,
            measured,
            target_db,
            taps=64,
            correction_mask=mask,
            grid_points=128,
            lambda_reg=0.001,
            max_boost_db=6.0,
        )
        corrected = measured * gen.fir_response(fir, freq)

        before = gen.rms(gen.db(measured[mask]) - target_db[mask])
        after = gen.rms(gen.db(corrected[mask]) - target_db[mask])
        self.assertLess(after, before)

    def test_ls_fir_does_not_chase_deep_null_beyond_boost_guardrail(self):
        freq = np.geomspace(20.0, 20_000.0, 256)
        measured = np.ones_like(freq, dtype=np.complex128)
        measured[np.argmin(np.abs(freq - 100.0))] = 10.0 ** (-40.0 / 20.0)
        target_db = np.zeros_like(freq)
        mask = (freq >= 80.0) & (freq <= 200.0)

        fir = gen.make_fir_ls(
            freq,
            measured,
            target_db,
            taps=64,
            correction_mask=mask,
            grid_points=128,
            lambda_reg=0.01,
            max_boost_db=3.0,
        )
        response_db = gen.db(gen.fir_response(fir, freq))

        self.assertTrue(np.all(np.isfinite(fir)))
        self.assertLessEqual(float(np.max(response_db[mask])), 3.5)

    def test_peak_filter_refinement_improves_greedy_seed_on_synthetic_response(self):
        freq = np.geomspace(60.0, 18_000.0, 900)
        target_db = np.zeros_like(freq)
        measured = (
            gen.biquad_peak(320.0, 5.0, 2.4).response(freq)
            * gen.biquad_peak(1800.0, -2.5, 1.1).response(freq)
        )
        mask = np.ones_like(freq, dtype=bool)

        seed = gen.seed_peak_filters(freq, measured, target_db, mask, max_filters=4)
        refined = gen.optimize_peak_filters(freq, measured, target_db, mask, seed)

        self.assertTrue(refined.success)
        self.assertLess(refined.refined_rms_db, refined.seed_rms_db)
        self.assertLess(refined.refined_rms_db, 0.65)
        self.assertTrue(all(filt.is_stable() for filt in refined.filters))

    def test_peak_filter_refinement_respects_frequency_q_and_gain_bounds(self):
        freq = np.geomspace(80.0, 1000.0, 300)
        target_db = np.zeros_like(freq)
        measured = gen.biquad_peak(250.0, 12.0, 14.0).response(freq)
        mask = (freq >= 100.0) & (freq <= 800.0)
        seed = [gen.biquad_peak(250.0, -12.0, 14.0)]

        refined = gen.optimize_peak_filters(freq, measured, target_db, mask, seed)

        self.assertTrue(refined.success)
        for filt in refined.filters:
            self.assertGreaterEqual(filt.freq, 100.0)
            self.assertLessEqual(filt.freq, 800.0)
            self.assertGreaterEqual(filt.q, 0.35)
            self.assertLessEqual(filt.q, 8.0)
            self.assertGreaterEqual(filt.gain_db, -9.0)
            self.assertLessEqual(filt.gain_db, 3.0)

    def test_low_frequency_distortion_guard_discourages_boost(self):
        freq = np.geomspace(15.0, 120.0, 300)
        target_db = np.zeros_like(freq)
        measured = gen.biquad_peak(20.0, -8.0, 1.2).response(freq)
        mask = (freq >= 15.0) & (freq <= 120.0)
        seed = [gen.biquad_peak(20.0, 3.0, 1.2)]
        distortion = {
            "freq": np.asarray([15.0, 20.0, 25.0, 40.0]),
            "thd_pct": np.asarray([12.0, 10.0, 2.0, 1.0]),
        }

        refined = gen.optimize_peak_filters(
            freq,
            measured,
            target_db,
            mask,
            seed,
            distortion=distortion,
        )

        self.assertTrue(refined.success)
        self.assertLessEqual(max((f.gain_db for f in refined.filters), default=0.0), 1.0)

    def test_final_system_score_uses_post_filter_summed_response(self):
        freq = np.asarray([80.0, 100.0, 120.0])
        target = np.full(freq.shape, 6.020599913279624)
        measured_sum = np.full(freq.shape, 2.0 + 0.0j)
        coherent = {
            "left": np.ones(freq.shape, dtype=np.complex128),
            "right": np.ones(freq.shape, dtype=np.complex128),
            "sub": np.ones(freq.shape, dtype=np.complex128),
        }
        cancelled = {
            "left": np.ones(freq.shape, dtype=np.complex128),
            "right": np.ones(freq.shape, dtype=np.complex128),
            "sub": -np.ones(freq.shape, dtype=np.complex128),
        }

        coherent_score = gen.score_final_system_candidate(
            freq=freq,
            final_channels=coherent,
            lsum_measured=measured_sum,
            rsum_measured=measured_sum,
            target_db=target,
            crossover_hz=100.0,
        )
        cancelled_score = gen.score_final_system_candidate(
            freq=freq,
            final_channels=cancelled,
            lsum_measured=measured_sum,
            rsum_measured=measured_sum,
            target_db=target,
            crossover_hz=100.0,
        )

        self.assertLess(coherent_score["score"], cancelled_score["score"])
        self.assertLess(coherent_score["target_rms_db"], 1e-6)
        self.assertGreater(cancelled_score["cancellation_penalty"], coherent_score["cancellation_penalty"])

    def test_phase_alignment_penalty_prefers_aligned_crossover_components(self):
        freq = np.asarray([90.0, 100.0, 110.0])
        target = np.full(freq.shape, 6.020599913279624)
        measured_sum = np.full(freq.shape, 2.0 + 0.0j)
        aligned = {
            "left": np.ones(freq.shape, dtype=np.complex128),
            "right": np.ones(freq.shape, dtype=np.complex128),
            "sub": np.ones(freq.shape, dtype=np.complex128),
        }
        quadrature = {
            "left": np.ones(freq.shape, dtype=np.complex128),
            "right": np.ones(freq.shape, dtype=np.complex128),
            "sub": np.full(freq.shape, 1.0j, dtype=np.complex128),
        }

        aligned_score = gen.score_final_system_candidate(
            freq=freq,
            final_channels=aligned,
            lsum_measured=measured_sum,
            rsum_measured=measured_sum,
            target_db=target,
            crossover_hz=100.0,
        )
        quadrature_score = gen.score_final_system_candidate(
            freq=freq,
            final_channels=quadrature,
            lsum_measured=measured_sum,
            rsum_measured=measured_sum,
            target_db=target,
            crossover_hz=100.0,
        )

        self.assertLess(aligned_score["phase_penalty"], quadrature_score["phase_penalty"])

    def test_exact_selection_uses_exact_score_after_proxy_shortlist(self):
        candidates = [
            {"score": 0.1, "crossover_hz": 80.0, "sub_delay_ms": 0.0, "sub_gain_db": 0.0},
            {"score": 0.2, "crossover_hz": 100.0, "sub_delay_ms": 0.0, "sub_gain_db": 0.0},
        ]

        selected = gen.select_exact_crossover_candidate(
            candidates,
            exact_scorer=lambda row: {"score": 10.0 if row["crossover_hz"] == 80.0 else 1.0},
            max_candidates=2,
        )

        self.assertEqual(selected["crossover_hz"], 100.0)
        self.assertEqual(selected["proxy_score"], 0.2)
        self.assertEqual(selected["exact_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
