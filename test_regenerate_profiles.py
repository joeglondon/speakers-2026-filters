import tempfile
import unittest
from pathlib import Path

from scripts.regenerate_profiles import ProfileSpec, default_specs, write_summary, summarize_profile


class RegenerateProfilesTests(unittest.TestCase):
    def test_summarize_profile_parses_metadata_report_and_low_frequency_boost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "Profile"
            profile.mkdir()
            profile.joinpath("metadata.json").write_text(
                """{
  "crossover": {"crossover_hz": 140.0},
  "delays_ms": {"left": 7.1, "right": 7.1, "sub": 0.0},
  "gains_db": {"left": -2.0, "right": -3.0, "sub": -4.0},
  "validations": {
    "left_sum_rms_db": 6.8,
    "right_sum_rms_db": 6.7,
    "worst_cancellation_db": -4.4,
    "worst_cancellation_hz": 120.1
  },
  "filters": {
    "left": [],
    "right": [],
    "sub": [
      {
        "b0": 1.0,
        "b1": 0.0,
        "b2": 0.0,
        "a1": 0.0,
        "a2": 0.0,
        "freq_hz": 19.5,
        "gain_db": 3.0,
        "q": 1.0,
        "type": "PK"
      }
    ]
  },
  "fir_taps": {"left": 4, "right": 4, "sub": 4}
}
"""
            )
            profile.joinpath("report.md").write_text(
                "\n".join(
                    [
                        "- Left: RMS target error 5.45 dB before correction, 10.19 dB after PEQ+FIR in its correction band.",
                        "- Right: RMS target error 5.54 dB before correction, 7.28 dB after PEQ+FIR in its correction band.",
                        "- Sub: RMS target error 7.40 dB before correction, 9.15 dB after PEQ+FIR in its correction band.",
                    ]
                )
            )
            for channel in ("left", "right", "sub"):
                profile.joinpath(f"fir_{channel}_96k_4taps_raw.txt").write_text("1.0\n0.0\n0.0\n0.0\n")

            summary = summarize_profile(
                root,
                ProfileSpec(
                    name="example",
                    artifact_dir=Path("Profile"),
                    command=["python3", "generate_minidsp_filters.py"],
                ),
            )

        self.assertEqual(summary["name"], "example")
        self.assertEqual(summary["crossover_hz"], 140.0)
        self.assertEqual(summary["delays_ms"]["left"], 7.1)
        self.assertEqual(summary["gains_db"]["sub"], -4.0)
        self.assertEqual(summary["channel_rms_db"]["left"]["before"], 5.45)
        self.assertEqual(summary["channel_rms_db"]["sub"]["after"], 9.15)
        self.assertEqual(summary["sum_rms_50_160_db"]["left_plus_sub"], 6.8)
        self.assertEqual(summary["worst_cancellation"]["db"], -4.4)
        self.assertGreaterEqual(summary["max_boost_below_25hz_db"]["sub"], 0.0)
        self.assertEqual(summary["command"], ["python3", "generate_minidsp_filters.py"])

    def test_write_summary_parses_checked_in_generated_artifacts(self):
        root = Path.cwd()
        specs = default_specs(
            root,
            python="python3",
            regenerate_output_root=Path("Baseline_Runs"),
            regenerate=False,
        )

        with tempfile.TemporaryDirectory() as tmp:
            summary = write_summary(root, specs, Path(tmp) / "comparison_summary.json")

        self.assertEqual(
            [profile["name"] for profile in summary["profiles"]],
            [
                "ls_auto_50_140",
                "legacy_auto_50_140",
                "profile_02_clean_140hz",
                "profile_03_2023ish_54hz",
                "profile_04_compromise_95hz",
            ],
        )
        for profile in summary["profiles"]:
            self.assertEqual(set(profile["channel_rms_db"]), {"left", "right", "sub"})
            self.assertIn("left_plus_sub", profile["sum_rms_50_160_db"])
            self.assertIn("db", profile["worst_cancellation"])

    def test_default_specs_store_repo_relative_replay_commands(self):
        root = Path.cwd()
        specs = default_specs(
            root,
            python="/custom/python",
            regenerate_output_root=Path("Baseline_Runs"),
            regenerate=True,
        )

        first = specs[0]

        self.assertEqual(first.command[0], "python")
        self.assertEqual(first.command[1], "generate_minidsp_filters.py")
        self.assertIn("--root", first.command)
        self.assertEqual(first.command[first.command.index("--root") + 1], ".")
        self.assertEqual(
            first.command[first.command.index("--output") + 1],
            "Baseline_Runs/ls_auto_50_140",
        )
        self.assertIsNotNone(first.run_command)
        self.assertEqual(first.run_command[0], "/custom/python")


if __name__ == "__main__":
    unittest.main()
