import math
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import generate_minidsp_filters as gen


class GenerateMiniDSPFiltersTests(unittest.TestCase):
    def test_multipoint_dataset_preserves_positions_and_provides_average(self):
        freq = np.asarray([100.0, 200.0])
        responses = {
            "left": [
                np.asarray([1.0 + 0.0j, 2.0 + 0.0j]),
                np.asarray([3.0 + 0.0j, 4.0 + 0.0j]),
            ],
            "right": [
                np.asarray([2.0 + 0.0j, 2.0 + 0.0j]),
                np.asarray([4.0 + 0.0j, 4.0 + 0.0j]),
            ],
        }

        dataset = gen.MultiPointResponses(freq=freq, responses=responses)

        self.assertEqual(dataset.position_count("left"), 2)
        self.assertEqual(dataset.position_count("right"), 2)
        self.assertEqual(dataset.position_count(), 2)
        np.testing.assert_allclose(dataset.average("left"), np.asarray([2.0 + 0.0j, 3.0 + 0.0j]))
        self.assertEqual(len(dataset.training_indices(held_out=1)), 1)
        self.assertEqual(dataset.training_indices(held_out=1), [0])

    def test_impulse_to_frequency_response_recovers_delayed_impulse_phase(self):
        impulse = gen.ImpulseMeasurement(
            name="unit",
            path=Path("unit.txt"),
            peak_value=1.0,
            peak_index=2,
            length=8,
            sample_interval=1.0 / 8.0,
            start_time=0.0,
            samples=np.asarray([0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        )
        freq = np.asarray([0.0, 1.0, 2.0])

        response = gen.impulse_to_frequency_response(impulse, freq)

        expected = np.exp(-1j * 2.0 * np.pi * freq * (2.0 / 8.0))
        np.testing.assert_allclose(response, expected, atol=1e-12)

    def test_frontier_fir_respects_frequency_boost_cap(self):
        freq = np.geomspace(20.0, 500.0, 80)
        measured_positions = [
            np.ones_like(freq, dtype=np.complex128) * (10.0 ** (-8.0 / 20.0)),
            np.ones_like(freq, dtype=np.complex128) * (10.0 ** (-4.0 / 20.0)),
        ]
        target_db = np.zeros_like(freq)
        mask = (freq >= 40.0) & (freq <= 300.0)
        cap = np.full_like(freq, 2.0)

        fir, metadata = gen.make_frontier_fir(
            freq,
            measured_positions,
            target_db,
            taps=48,
            correction_mask=mask,
            grid_points=96,
            max_boost_db=2.0,
            max_cut_db=10.0,
            boost_cap_db=cap,
            max_filter_energy_db=18.0,
            pre_ringing_limit_db=-18.0,
        )

        response_db = gen.db(gen.fir_response(fir, freq))
        self.assertEqual(fir.shape, (48,))
        self.assertEqual(metadata["method"], "cvxpy")
        self.assertLessEqual(float(np.max(response_db[mask])), 2.35)
        self.assertTrue(np.all(np.isfinite(fir)))

    def test_frontier_fir_falls_back_when_clarabel_raises_solver_error(self):
        import cvxpy as cp

        freq = np.geomspace(40.0, 400.0, 48)
        measured_positions = [np.ones_like(freq, dtype=np.complex128)]
        target_db = np.zeros_like(freq)
        mask = np.ones_like(freq, dtype=bool)
        original_solve = cp.Problem.solve
        clarabel_calls = 0

        def flaky_solve(problem, *args, **kwargs):
            nonlocal clarabel_calls
            if kwargs.get("solver") == "CLARABEL":
                clarabel_calls += 1
                raise cp.error.SolverError("forced CLARABEL failure")
            return original_solve(problem, *args, **kwargs)

        with mock.patch.object(cp.Problem, "solve", flaky_solve):
            fir, metadata = gen.make_frontier_fir(
                freq,
                measured_positions,
                target_db,
                taps=24,
                correction_mask=mask,
                grid_points=48,
            )

        self.assertEqual(clarabel_calls, 1)
        self.assertEqual(metadata["solver"], "SCS")
        self.assertEqual(metadata["clarabel_error"], "forced CLARABEL failure")
        self.assertTrue(np.all(np.isfinite(fir)))

    def test_frontier_dense_guardrail_detects_peak_missed_between_sparse_design_points(self):
        freq = np.linspace(2_000.0, 2_800.0, 801)
        sparse_freq = np.asarray([2_000.0, 2_800.0])
        center_hz = 2_400.0
        taps = 512
        n = np.arange(taps, dtype=np.float64)
        fir = np.cos(2.0 * np.pi * center_hz * n / gen.OUT_FS) * np.hamming(taps)
        fir *= (10.0 ** (12.0 / 20.0)) / abs(gen.fir_response(fir, np.asarray([center_hz]))[0])
        mask = np.ones_like(freq, dtype=bool)
        cap = np.full_like(freq, 3.0)

        sparse_boost = gen.db(gen.fir_response(fir, sparse_freq))
        metrics = gen.dense_fir_guardrail_metrics(freq, fir, mask, boost_cap_db=cap)

        self.assertLess(float(np.max(sparse_boost)), 3.25)
        self.assertGreater(metrics["dense_boost_over_cap_db"], 6.0)
        self.assertAlmostEqual(metrics["dense_max_boost_hz"], center_hz, delta=5.0)

    def test_frontier_fallback_uses_legacy_when_frontier_worsens_channel_rms(self):
        freq = np.asarray([100.0, 200.0, 400.0])
        target_db = np.zeros_like(freq)
        after_peq = np.ones_like(freq, dtype=np.complex128)
        mask = np.ones_like(freq, dtype=bool)
        frontier_fir = np.asarray([2.0])
        legacy_fir = np.asarray([1.0])

        selected = gen.choose_frontier_fir_with_fallback(
            freq,
            after_peq,
            target_db,
            mask,
            fallback_enabled=True,
            frontier_fir=frontier_fir,
            frontier_metrics={
                "status": "optimal",
                "dense_boost_over_cap_db": 0.0,
            },
            legacy_fir=legacy_fir,
        )

        self.assertEqual(selected["used_method"], "legacy fallback")
        self.assertIs(selected["fir"], legacy_fir)
        self.assertFalse(selected["metrics"]["frontier_accepted"])
        self.assertEqual(selected["metrics"]["frontier_rejection_reason"], "frontier_worse_than_reliable")

    def test_frontier_fallback_rejects_optimal_inaccurate_status(self):
        freq = np.asarray([100.0, 200.0, 400.0])
        target_db = np.zeros_like(freq)
        after_peq = np.ones_like(freq, dtype=np.complex128)
        mask = np.ones_like(freq, dtype=bool)
        frontier_fir = np.asarray([1.0])
        legacy_fir = np.asarray([1.0])

        selected = gen.choose_frontier_fir_with_fallback(
            freq,
            after_peq,
            target_db,
            mask,
            fallback_enabled=True,
            frontier_fir=frontier_fir,
            frontier_metrics={
                "status": "optimal_inaccurate",
                "dense_boost_over_cap_db": 0.0,
            },
            legacy_fir=legacy_fir,
        )

        self.assertEqual(selected["used_method"], "legacy fallback")
        self.assertFalse(selected["metrics"]["frontier_accepted"])
        self.assertEqual(selected["metrics"]["frontier_rejection_reason"], "solver_status: optimal_inaccurate")

    def test_frontier_fallback_raises_when_fallback_disabled(self):
        freq = np.asarray([100.0, 200.0, 400.0])
        target_db = np.zeros_like(freq)
        after_peq = np.ones_like(freq, dtype=np.complex128)
        mask = np.ones_like(freq, dtype=bool)

        with self.assertRaisesRegex(ValueError, "Frontier FIR rejected"):
            gen.choose_frontier_fir_with_fallback(
                freq,
                after_peq,
                target_db,
                mask,
                fallback_enabled=False,
                frontier_fir=np.asarray([2.0]),
                frontier_metrics={
                    "status": "optimal",
                    "dense_boost_over_cap_db": 20.0,
                    "dense_max_boost_db": 23.0,
                    "dense_max_boost_hz": 200.0,
                },
                legacy_fir=np.asarray([1.0]),
            )

    def test_multipoint_score_uses_80th_percentile_not_only_average(self):
        freq = np.asarray([80.0, 100.0, 120.0])
        target = np.zeros_like(freq)
        good_everywhere = [
            np.ones_like(freq, dtype=np.complex128),
            np.ones_like(freq, dtype=np.complex128) * (10.0 ** (1.0 / 20.0)),
            np.ones_like(freq, dtype=np.complex128) * (10.0 ** (-1.0 / 20.0)),
        ]
        bad_one_seat = [
            np.ones_like(freq, dtype=np.complex128) * (10.0 ** (-2.0 / 20.0)),
            np.ones_like(freq, dtype=np.complex128) * (10.0 ** (-2.0 / 20.0)),
            np.ones_like(freq, dtype=np.complex128) * (10.0 ** (8.0 / 20.0)),
        ]
        mask = np.ones_like(freq, dtype=bool)

        good = gen.multipoint_magnitude_score(good_everywhere, target, mask)
        bad = gen.multipoint_magnitude_score(bad_one_seat, target, mask)

        self.assertLess(good["score"], bad["score"])
        self.assertGreater(bad["p80_rms_db"], bad["median_rms_db"])

    def test_frontier_final_system_records_multipoint_fir_metrics(self):
        freq = np.geomspace(40.0, 500.0, 80)
        target = np.zeros_like(freq)
        flat = np.ones_like(freq, dtype=np.complex128)
        responses = {
            "left": [flat.copy(), flat * (10.0 ** (-1.0 / 20.0))],
            "right": [flat.copy(), flat * (10.0 ** (1.0 / 20.0))],
            "sub": [flat.copy(), flat * (10.0 ** (-2.0 / 20.0))],
            "left_sum": [flat * 2.0, flat * 2.0],
            "right_sum": [flat * 2.0, flat * 2.0],
        }
        multipoint = gen.MultiPointResponses(freq=freq, responses=responses)
        avg = {key: multipoint.average(key) for key in responses}
        original_taps = dict(gen.FIR_TAPS)
        try:
            gen.FIR_TAPS.update({"left": 48, "right": 48, "sub": 48})
            system = gen.build_final_filter_system(
                freq=freq,
                avg=avg,
                target_db=target,
                crossover={"crossover_hz": 100.0, "sub_delay_ms": 0.0, "sub_gain_db": 0.0},
                sub_low_freq=40.0,
                sub_highpass_hz=0.0,
                fir_ls_grid_points=96,
                fir_ls_max_boost_db=2.0,
                optimizer_mode="frontier",
                multipoint=multipoint,
                gain_refinement_enabled=False,
            )
        finally:
            gen.FIR_TAPS.clear()
            gen.FIR_TAPS.update(original_taps)

        for result in system["results"]:
            self.assertEqual(result.fir_requested_method, "frontier")
            self.assertIn(result.fir_used_method, {"frontier cvxpy", "legacy fallback", "flat guardrail fallback"})
            self.assertIn("frontier_accepted", result.fir_metrics)
            self.assertIn("multipoint_score", result.fir_metrics)

    def test_frontier_final_system_records_rejection_metadata_when_falling_back(self):
        freq = np.geomspace(40.0, 500.0, 80)
        target = np.zeros_like(freq)
        flat = np.ones_like(freq, dtype=np.complex128)
        responses = {
            "left": [flat.copy(), flat.copy()],
            "right": [flat.copy(), flat.copy()],
            "sub": [flat.copy(), flat.copy()],
            "left_sum": [flat * 2.0, flat * 2.0],
            "right_sum": [flat * 2.0, flat * 2.0],
        }
        multipoint = gen.MultiPointResponses(freq=freq, responses=responses)
        avg = {key: multipoint.average(key) for key in responses}
        original_taps = dict(gen.FIR_TAPS)

        def unsafe_frontier(*args, **kwargs):
            fir = gen.flat_delay_fir(args[3]) * 2.0
            return fir, {
                "method": "cvxpy",
                "solver": "CLARABEL",
                "status": "optimal",
                "dense_boost_over_cap_db": 3.0,
                "dense_max_boost_db": 6.0,
                "dense_max_boost_hz": 100.0,
            }

        try:
            gen.FIR_TAPS.update({"left": 48, "right": 48, "sub": 48})
            with mock.patch.object(gen, "make_frontier_fir", unsafe_frontier):
                system = gen.build_final_filter_system(
                    freq=freq,
                    avg=avg,
                    target_db=target,
                    crossover={"crossover_hz": 100.0, "sub_delay_ms": 0.0, "sub_gain_db": 0.0},
                    sub_low_freq=40.0,
                    sub_highpass_hz=0.0,
                    fir_ls_grid_points=96,
                    fir_ls_max_boost_db=2.0,
                    optimizer_mode="frontier",
                    multipoint=multipoint,
                    gain_refinement_enabled=False,
                )
        finally:
            gen.FIR_TAPS.clear()
            gen.FIR_TAPS.update(original_taps)

        reasons = []
        for result in system["results"]:
            self.assertEqual(result.fir_requested_method, "frontier")
            self.assertIn(result.fir_used_method, {"legacy fallback", "flat guardrail fallback"})
            self.assertFalse(result.fir_metrics["frontier_accepted"])
            reasons.append(result.fir_metrics["frontier_rejection_reason"])
        self.assertEqual(reasons[0], "dense_guardrail_violation")
        self.assertTrue(all(reason for reason in reasons))

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

    def test_ls_fir_magnitude_phase_mode_does_not_invert_measured_phase(self):
        freq = np.geomspace(80.0, 800.0, 128)
        measured = (10.0 ** (-4.0 / 20.0)) * np.exp(-1j * 2.0 * np.pi * freq * 0.003)
        target_db = np.zeros_like(freq)
        mask = np.ones_like(freq, dtype=bool)

        design_freq, magnitude_target, _ = gen.ls_fir_correction_target(
            freq,
            measured,
            target_db,
            taps=64,
            correction_mask=mask,
            grid_points=96,
            phase_mode="magnitude",
        )
        _, complex_target, _ = gen.ls_fir_correction_target(
            freq,
            measured,
            target_db,
            taps=64,
            correction_mask=mask,
            grid_points=96,
            phase_mode="complex-inverse",
        )
        measured_on_grid = gen.interp_complex(freq, measured, design_freq)
        delay_phase = np.exp(-1j * 2.0 * np.pi * design_freq * (((64 - 1) / 2.0) / gen.OUT_FS))
        active = np.interp(design_freq, freq, mask.astype(np.float64), left=0.0, right=0.0) >= 0.5

        magnitude_extra_phase = np.angle(magnitude_target[active] / delay_phase[active])
        complex_extra_phase = np.angle(
            complex_target[active]
            / delay_phase[active]
            * measured_on_grid[active]
            / np.abs(measured_on_grid[active])
        )

        self.assertLess(float(np.max(np.abs(magnitude_extra_phase))), 1e-9)
        self.assertLess(float(np.max(np.abs(complex_extra_phase))), 1e-9)

    def test_ls_fir_fallback_uses_legacy_when_ls_worsens_channel_rms(self):
        freq = np.asarray([100.0, 200.0, 400.0])
        target_db = np.zeros_like(freq)
        after_peq = np.ones_like(freq, dtype=np.complex128)
        mask = np.ones_like(freq, dtype=bool)
        ls_fir = np.asarray([2.0])
        legacy_fir = np.asarray([1.0])

        selected = gen.choose_fir_with_fallback(
            freq,
            after_peq,
            target_db,
            mask,
            requested_method="ls",
            fallback_enabled=True,
            ls_fir=ls_fir,
            legacy_fir=legacy_fir,
        )

        self.assertEqual(selected["used_method"], "legacy fallback")
        self.assertIs(selected["fir"], legacy_fir)
        self.assertGreater(selected["metrics"]["ls_rms_db"], selected["metrics"]["after_peq_rms_db"])

    def test_ls_fir_fallback_uses_flat_fir_when_all_correction_violates_boost_cap(self):
        freq = np.asarray([15.0, 20.0, 24.0])
        target_db = np.zeros_like(freq)
        after_peq = np.ones_like(freq, dtype=np.complex128)
        mask = np.ones_like(freq, dtype=bool)
        ls_fir = np.asarray([2.0])
        legacy_fir = np.asarray([1.5])
        guardrail_fir = np.asarray([1.0])
        cap = np.full_like(freq, 2.0)

        selected = gen.choose_fir_with_fallback(
            freq,
            after_peq,
            target_db,
            mask,
            requested_method="ls",
            fallback_enabled=True,
            ls_fir=ls_fir,
            legacy_fir=legacy_fir,
            guardrail_fir=guardrail_fir,
            boost_cap_db=cap,
        )

        self.assertEqual(selected["used_method"], "flat guardrail fallback")
        self.assertIs(selected["fir"], guardrail_fir)

    def test_legacy_fir_uses_flat_guardrail_when_it_violates_boost_cap(self):
        freq = np.asarray([15.0, 20.0, 24.0])
        target_db = np.zeros_like(freq)
        after_peq = np.ones_like(freq, dtype=np.complex128)
        mask = np.ones_like(freq, dtype=bool)
        legacy_fir = np.asarray([1.5])
        guardrail_fir = np.asarray([1.0])
        cap = np.zeros_like(freq)

        selected = gen.choose_fir_with_fallback(
            freq,
            after_peq,
            target_db,
            mask,
            requested_method="legacy",
            fallback_enabled=True,
            ls_fir=None,
            legacy_fir=legacy_fir,
            guardrail_fir=guardrail_fir,
            boost_cap_db=cap,
        )

        self.assertEqual(selected["used_method"], "flat guardrail fallback")
        self.assertIs(selected["fir"], guardrail_fir)
        self.assertGreater(selected["metrics"]["legacy_boost_over_cap_db"], 0.1)

    def test_ls_fir_is_kept_when_legacy_violates_boost_cap_but_ls_is_safe(self):
        freq = np.asarray([15.0, 20.0, 24.0])
        target_db = np.zeros_like(freq)
        after_peq = np.ones_like(freq, dtype=np.complex128) * 0.8
        mask = np.ones_like(freq, dtype=bool)
        ls_fir = np.asarray([1.25])
        legacy_fir = np.asarray([1.5])
        guardrail_fir = np.asarray([1.0])
        cap = np.full_like(freq, 2.0)

        selected = gen.choose_fir_with_fallback(
            freq,
            after_peq,
            target_db,
            mask,
            requested_method="ls",
            fallback_enabled=True,
            ls_fir=ls_fir,
            legacy_fir=legacy_fir,
            guardrail_fir=guardrail_fir,
            boost_cap_db=cap,
        )

        self.assertEqual(selected["used_method"], "ls")
        self.assertIs(selected["fir"], ls_fir)
        self.assertLessEqual(selected["metrics"]["ls_boost_over_cap_db"], 0.1)

    def test_average_impulse_aligns_without_wrapping_samples(self):
        first = gen.ImpulseMeasurement(
            name="first",
            path=Path("first.txt"),
            peak_value=1.0,
            peak_index=1,
            length=5,
            sample_interval=1.0,
            start_time=0.0,
            samples=np.asarray([0.0, 1.0, 0.0, 0.0, 9.0]),
        )
        second = gen.ImpulseMeasurement(
            name="second",
            path=Path("second.txt"),
            peak_value=1.0,
            peak_index=2,
            length=5,
            sample_interval=1.0,
            start_time=0.0,
            samples=np.asarray([0.0, 0.0, 1.0, 0.0, 0.0]),
        )

        averaged = gen.average_impulse([first, second])

        np.testing.assert_allclose(averaged, np.asarray([0.0, 0.0, 1.0, 0.0, 0.0]))

    def test_gain_refinement_updates_score_with_same_final_gains(self):
        freq = np.asarray([80.0, 100.0, 120.0])
        target_db = np.full(freq.shape, 6.020599913279624)
        channels = {
            "left": np.ones(freq.shape, dtype=np.complex128),
            "right": np.ones(freq.shape, dtype=np.complex128),
            "sub": np.ones(freq.shape, dtype=np.complex128) * (10.0 ** (-6.0 / 20.0)),
        }
        measured_sum = np.ones(freq.shape, dtype=np.complex128) * 2.0
        seed_gains = {"left": 0.0, "right": 0.0, "sub": 0.0}

        refinement = gen.refine_output_gains(
            freq,
            channels,
            lsum_measured=measured_sum,
            rsum_measured=measured_sum,
            target_db=target_db,
            crossover_hz=100.0,
            seed_gains_db=seed_gains,
        )
        rescored = gen.score_final_system_candidate(
            freq,
            refinement["final_channels"],
            measured_sum,
            measured_sum,
            target_db,
            crossover_hz=100.0,
        )

        self.assertGreater(refinement["gain_delta_db"]["sub"], 0.0)
        self.assertEqual(refinement["gain_final_db"], {
            key: seed_gains[key] + refinement["gain_delta_db"][key]
            for key in seed_gains
        })
        self.assertAlmostEqual(rescored["score"], refinement["score_after"]["score"], places=9)

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

    def test_peak_filter_refinement_does_not_stack_same_sign_boosts_on_broad_dip(self):
        freq = np.geomspace(80.0, 320.0, 300)
        target_db = np.zeros_like(freq)
        measured = gen.biquad_peak(155.0, -8.0, 0.7).response(freq)
        mask = np.ones_like(freq, dtype=bool)
        seed = [
            gen.biquad_peak(145.0, 3.0, 1.0),
            gen.biquad_peak(155.0, 3.0, 1.0),
            gen.biquad_peak(165.0, 3.0, 1.0),
        ]

        refined = gen.optimize_peak_filters(freq, measured, target_db, mask, seed)
        clustered_boosts = [
            filt
            for filt in refined.filters
            if filt.gain_db > 0.0 and 140.0 <= filt.freq <= 170.0
        ]
        peq_boost_db = gen.db(gen.cascade_response(refined.filters, freq))

        self.assertLessEqual(len(clustered_boosts), 1)
        self.assertLessEqual(float(np.max(peq_boost_db)), 5.0)

    def test_prune_redundant_peq_filters_removes_duplicate_unless_material(self):
        freq = np.geomspace(80.0, 240.0, 260)
        target_db = np.zeros_like(freq)
        measured = gen.biquad_peak(120.0, -1.5, 1.0).response(freq)
        mask = np.ones_like(freq, dtype=bool)
        filters = [
            gen.biquad_peak(120.0, 1.5, 1.0),
            gen.biquad_peak(121.0, 1.5, 1.0),
        ]

        pruned = gen.prune_redundant_peq_filters(
            filters,
            freq,
            measured,
            target_db,
            mask,
            max_rms_worsening_db=0.25,
        )

        self.assertEqual(len(pruned), 1)

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

    def test_distortion_guardrail_blocks_sub_peq_boost_below_25hz(self):
        freq = np.geomspace(15.0, 120.0, 300)
        target_db = np.zeros_like(freq)
        measured = gen.biquad_peak(20.0, -8.0, 1.2).response(freq)
        mask = (freq >= 15.0) & (freq <= 120.0)
        distortion = {
            "freq": np.asarray([15.0, 20.0, 25.0, 40.0]),
            "thd_pct": np.asarray([12.0, 10.0, 2.0, 1.0]),
        }
        cap = gen.boost_cap_curve_db(freq, distortion, "sub", default_boost_db=3.0)

        seed = gen.seed_peak_filters(freq, measured, target_db, mask, boost_cap_db=cap)
        refined = gen.optimize_peak_filters(
            freq,
            measured,
            target_db,
            mask,
            seed,
            distortion=distortion,
            boost_cap_db=cap,
        )
        peq_boost_db = gen.db(gen.cascade_response(refined.filters, freq))

        self.assertTrue(refined.success)
        self.assertLessEqual(float(np.max(peq_boost_db[freq < 25.0])), 0.1)

    def test_distortion_guardrail_blocks_fir_boost_below_25hz(self):
        freq = np.geomspace(15.0, 120.0, 240)
        target_db = np.zeros_like(freq)
        measured = np.ones_like(freq, dtype=np.complex128) * (10.0 ** (-6.0 / 20.0))
        mask = (freq >= 15.0) & (freq <= 120.0)
        distortion = {
            "freq": np.asarray([15.0, 20.0, 25.0, 40.0]),
            "thd_pct": np.asarray([12.0, 10.0, 2.0, 1.0]),
        }
        cap = gen.boost_cap_curve_db(freq, distortion, "sub", default_boost_db=3.0)

        legacy_fir = gen.make_fir(freq, target_db - gen.db(measured), 96, mask, boost_cap_db=cap)
        ls_fir = gen.make_fir_ls(
            freq,
            measured,
            target_db,
            96,
            mask,
            grid_points=128,
            lambda_reg=0.01,
            max_boost_db=3.0,
            boost_cap_db=cap,
        )

        below_25 = freq < 25.0
        self.assertLessEqual(float(np.max(gen.db(gen.fir_response(legacy_fir, freq))[below_25])), 0.5)
        self.assertLessEqual(float(np.max(gen.db(gen.fir_response(ls_fir, freq))[below_25])), 0.5)

    def test_report_guardrail_statement_matches_actual_filters(self):
        freq = np.geomspace(15.0, 120.0, 80)
        distortion = {
            "freq": np.asarray([15.0, 20.0, 25.0, 40.0]),
            "thd_pct": np.asarray([12.0, 10.0, 2.0, 1.0]),
            "measurement": np.asarray(["Sub Only 5"]),
        }
        boosted = gen.ChannelResult(
            key="sub",
            title="Sub",
            peq=[gen.biquad_peak(20.0, 3.0, 1.0)],
            peq_optimization={},
            fir=np.r_[1.0, np.zeros(31)],
            gain_db=0.0,
            delay_ms=0.0,
            fir_taps=32,
            rms_before_db=0.0,
            rms_after_db=0.0,
            max_boost_db=3.0,
            max_cut_db=0.0,
        )

        note = gen.distortion_guardrail_note(distortion, freq, [boosted])

        self.assertNotIn("boosts below 25 Hz were avoided", note)
        self.assertIn("actual max Sub PEQ+FIR boost below 25 Hz", note)

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

    def test_exact_selection_records_requested_and_scored_candidate_counts(self):
        candidates = [
            {
                "score": float(idx),
                "crossover_hz": 50.0 + 2.0 * idx,
                "sub_delay_ms": 0.0,
                "sub_gain_db": 0.0,
            }
            for idx in range(40)
        ]
        scored = []

        selected = gen.select_exact_crossover_candidate(
            candidates,
            exact_scorer=lambda row: scored.append(row["crossover_hz"]) or {"score": row["score"]},
            max_candidates=17,
        )

        self.assertEqual(len(scored), 17)
        self.assertEqual(selected["exact_candidate_limit"], 17)
        self.assertEqual(selected["exact_candidates_scored"], 17)
        self.assertEqual(len(selected["top_candidates"]), 17)

    def test_exact_candidate_scorer_uses_requested_optimizer_mode(self):
        freq = np.asarray([80.0, 100.0, 120.0])
        target = np.full(freq.shape, 6.020599913279624)
        measured_sum = np.full(freq.shape, 2.0 + 0.0j)
        candidate = {"crossover_hz": 100.0, "sub_delay_ms": 0.0, "sub_gain_db": 0.0}
        cache = {}
        calls = []

        def builder(**kwargs):
            calls.append(kwargs["optimizer_mode"])
            return {
                "final_channels": {
                    "left": np.ones(freq.shape, dtype=np.complex128),
                    "right": np.ones(freq.shape, dtype=np.complex128),
                    "sub": np.ones(freq.shape, dtype=np.complex128),
                }
            }

        score = gen.score_exact_candidate_system(
            candidate,
            cache=cache,
            build_kwargs={
                "freq": freq,
                "avg": {},
                "target_db": target,
                "sub_low_freq": 40.0,
                "sub_highpass_hz": 0.0,
                "optimizer_mode": "frontier",
                "multipoint": object(),
            },
            score_kwargs={
                "freq": freq,
                "lsum_measured": measured_sum,
                "rsum_measured": measured_sum,
                "target_db": target,
                "crossover_preference_hz": None,
            },
            builder=builder,
        )

        self.assertEqual(calls, ["frontier"])
        self.assertLess(score["score"], 1e-6)

    def test_crossover_selection_metadata_records_selected_and_exact_rows(self):
        selected = {
            "crossover_hz": 100.0,
            "sub_delay_ms": -1.5,
            "sub_gain_db": -0.25,
            "proxy_score": 2.0,
            "exact_score": 1.0,
            "top_candidates": [
                {"crossover_hz": 100.0, "proxy_score": 2.0, "exact_score": 1.0},
                {"crossover_hz": 90.0, "proxy_score": 2.5, "exact_score": 1.5},
            ],
        }

        metadata = gen.crossover_selection_metadata(selected)

        self.assertEqual(metadata["selected_candidate"]["crossover_hz"], 100.0)
        self.assertEqual(metadata["selected_candidate"]["proxy_score"], 2.0)
        self.assertEqual(metadata["selected_candidate"]["exact_score"], 1.0)
        self.assertEqual(metadata["exact_candidates_scored"], 2)
        self.assertEqual(metadata["exact_scored_candidates"], selected["top_candidates"])
        self.assertEqual(selected["exact_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
