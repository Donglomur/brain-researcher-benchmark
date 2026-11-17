"""Generated arithmetic controls; no native recordings, frameworks or models."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction

MODULE = Path(__file__).resolve().parents[1] / "temporal.py"
spec = importlib.util.spec_from_file_location("fast_temporal", MODULE)
t = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = t
spec.loader.exec_module(t)


def windows(plan, width=1):
    for start in range(plan.window_count):
        yield start, [[float(start + 1)] * width for _ in range(plan.channels)]


class TemporalTests(unittest.TestCase):
    def test_original_voltage_count_is_metadata_only(self):
        cli = t.TemporalPlan(4982, 4, "cli")
        gui = t.TemporalPlan(4982, 4, "gui")
        self.assertEqual((cli.window_count, gui.window_count), (4979, 4982))
        self.assertEqual(cli.summary()["saved_output_frames"], 4982)
        self.assertEqual(gui.summary()["augmented_frames"], 5082)
        self.assertEqual(cli.contributions(4981), ((4978, 3, Fraction(1)),))
        self.assertEqual([row[2] for row in gui.contributions(4981)],
                         [Fraction(1, 8), Fraction(1, 8), Fraction(1, 4), Fraction(1, 2)])
        self.assertFalse(cli.summary()["reflected_tail_used_by_network"])
        self.assertTrue(gui.summary()["reflected_tail_used_by_network"])

    def test_reflection_is_endpoint_repeating_and_short_stacks_use_available_tail(self):
        plan = t.TemporalPlan(3, 3, "gui")
        self.assertEqual([plan.source_frame(i) for i in range(6)], [0, 1, 2, 2, 1, 0])
        self.assertEqual(plan.window_frames(2), (2, 2, 1))
        with self.assertRaises(t.TemporalError):
            plan.source_frame(6)
        with self.assertRaises(t.TemporalError):
            plan.window_frames(3)

    def test_closed_form_weights_match_hand_computed_recursive_result(self):
        plan = t.TemporalPlan(6, 4, "gui")
        expected = [Fraction(1, 8), Fraction(1, 8), Fraction(1, 4), Fraction(1, 2)]
        self.assertEqual([row[2] for row in plan.contributions(3)], expected)
        self.assertEqual(sum(expected), 1)
        # A uniform overlap average would yield 2.5, not this source result.
        self.assertEqual(sum(weight * (start + 1) for start, _, weight in plan.contributions(3)),
                         Fraction(25, 8))

    def test_all_boundary_weights_and_support_are_complete(self):
        for frames in range(1, 11):
            for channels in range(1, frames + 1):
                for route in ("cli", "gui"):
                    plan = t.TemporalPlan(frames, channels, route)
                    for frame in range(frames):
                        rows = plan.contributions(frame)
                        self.assertEqual(sum(row[2] for row in rows), 1)
                        self.assertTrue(all(start + channel == frame for start, channel, _ in rows))
                        report = plan.frame_report(frame)
                        self.assertTrue(all(0 <= i < frames for i in report["network_window_original_frame_support"]))

    def test_cli_and_gui_differ_in_tail_even_with_equal_saved_shapes(self):
        cli = t.TemporalPlan(6, 4, "cli")
        gui = t.TemporalPlan(6, 4, "gui")
        a = t.reconstruct_traces(cli, windows(cli), 10)["float_traces"]
        b = t.reconstruct_traces(gui, windows(gui), 10)["float_traces"]
        self.assertEqual(a, [[11], [11.5], [12.25], [12.25], [12.5], [13]])
        self.assertEqual(b, [[11], [11.5], [12.25], [13.125], [14.125], [15.125]])
        self.assertEqual(a[:3], b[:3])
        self.assertNotEqual(a[3:], b[3:])
        self.assertEqual(len(a), len(b))

    def test_algebraic_oracle_agrees_with_reconstruction_for_nondense_values(self):
        for route in ("cli", "gui"):
            plan = t.TemporalPlan(9, 4, route)
            rows = [(start, [[(start + 1) * (channel - 2.5), channel + .125]
                             for channel in range(4)]) for start in range(plan.window_count)]
            result = t.reconstruct_traces(plan, rows, 3.0)
            for frame, actual in enumerate(result["float_traces"]):
                expected = [3.0 + sum(float(weight) * rows[start][1][channel][pixel]
                                     for start, channel, weight in plan.contributions(frame))
                            for pixel in range(2)]
                self.assertEqual(actual, expected)

    def test_uint16_export_clips_then_truncates_without_rounding(self):
        plan = t.TemporalPlan(1, 1, "cli")
        result = t.reconstruct_traces(plan, [(0, [[-1.2, 0.9, 12.99, 65535.9, 90000]])], 0)
        self.assertEqual(result["uint16_traces"], [[0, 0, 12, 65535, 65535]])
        self.assertEqual(result["original_frame_ids"], [0])

    def test_source_mean_uses_full_augmented_movie_not_plain_original_mean(self):
        # 101 one-pixel frames: the first is omitted from the 100-frame tail.
        frame_sums = [202] + [0] * 100
        self.assertAlmostEqual(t.augmented_mean(frame_sums, 1), 202 / 201)
        self.assertNotEqual(t.augmented_mean(frame_sums, 1), 2)
        self.assertEqual(t.augmented_mean([4, 8, 12], 2), 4)
        for values, pixels in [([], 1), ([1], 0), ([float("nan")], 1)]:
            with self.assertRaises(t.TemporalError):
                t.augmented_mean(values, pixels)

    def test_entire_stack_centering_prevents_window_only_acquisition_claim(self):
        plan = t.TemporalPlan(6, 4, "cli")
        times = [0, 1, 2, 3, 4, 5]
        bounds = t.acquisition_bounds(plan, times, [5] * 6)
        self.assertEqual(bounds["earliest_output_s"], [5] * 6)
        self.assertEqual(bounds["minimum_acquisition_delay_s"], [5, 4, 3, 2, 1, 0])
        self.assertEqual(plan.frame_report(0)["network_window_lookahead_frames"], 3)
        with self.assertRaisesRegex(t.TemporalError, "centering"):
            t.acquisition_bounds(plan, times, [3, 4, 5, 5, 5, 5])
        for input_times, output_times in [(times[:-1], None), ([1, 0, 2, 3, 4, 5], None),
                                          (times, [5] * 5), (times, [float("nan")] * 6)]:
            with self.assertRaises(t.TemporalError):
                t.acquisition_bounds(plan, input_times, output_times)

    def test_window_omission_reordering_duplicates_and_wrong_route_are_rejected(self):
        plan = t.TemporalPlan(6, 4, "cli")
        good = list(windows(plan))
        wrong = list(windows(t.TemporalPlan(6, 4, "gui")))
        for stream in (good[:-1], good + [good[-1]], list(reversed(good)),
                       [good[0], good[0], good[2]], wrong, []):
            with self.assertRaises(t.TemporalError):
                t.reconstruct_traces(plan, stream, 0)

    def test_finite_timestamps_cannot_overflow_derived_acquisition_delays(self):
        plan = t.TemporalPlan(2, 1, "cli")
        with self.assertRaisesRegex(t.TemporalError, "acquisition delay"):
            t.acquisition_bounds(plan, [-1e308, 1e308])

    def test_pixel_roster_channels_and_finite_values_cannot_change(self):
        plan = t.TemporalPlan(4, 4, "cli")
        for rows in ([1] * 4, [[1]] * 3, [[1], [1, 2], [1], [1]], [[]] * 4,
                     [[float("inf")]] * 4, [[True]] * 4):
            with self.assertRaises(t.TemporalError):
                t.reconstruct_traces(plan, [(0, rows)], 0)

    def test_invalid_temporal_settings_do_not_silently_change_source(self):
        for args in [(0, 1, "cli"), (4, 5, "cli"), (4, True, "cli"),
                     (4, 2, "unspecified"), (200, 102, "gui")]:
            with self.assertRaises(t.TemporalError):
                t.TemporalPlan(*args)
        # The CLI does not need the reflected frames as network input.
        self.assertEqual(t.TemporalPlan(200, 102, "cli").window_count, 99)

    def test_cli_json_has_no_paths_or_data_and_will_not_overwrite_evidence(self):
        with tempfile.TemporaryDirectory(prefix="fast031-generated-") as folder:
            output = Path(folder) / "report.json"
            command = [sys.executable, "-I", "-B", str(MODULE), "--frames", "6", "--channels", "4",
                       "--route", "gui", "--inspect-frame", "5", "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report["inspected_frames"][0]["original_frame"], 5)
            self.assertEqual(report["qualification"], "source_arithmetic_component_only")
            frozen = output.read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual(output.read_bytes(), frozen)


if __name__ == "__main__":
    unittest.main()
