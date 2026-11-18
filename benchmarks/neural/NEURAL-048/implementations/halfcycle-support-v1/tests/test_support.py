"""Generated dependency-lineage controls; no native neural observations."""
import copy
import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / "support.py"
spec = importlib.util.spec_from_file_location("neural048_halfcycle_support", path)
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


def fixture(offset=0):
    samples, intervals = [], []
    for t in range(1, 31):
        intervals.append({
            "id": f"h{t}", "worm_id": "A", "session_id": "s", "clock": "physical_ns",
            "start_ns": offset + t - 1, "end_ns": offset + t,
            "signal_support_end_ns": offset + t, "signal_available_ns": offset + t,
            "crossing_support_end_ns": offset + t, "crossing_available_ns": offset + t,
        })
        samples.append({
            "id": f"x{t}", "worm_id": "A", "session_id": "s", "interval_id": f"h{t}",
            "time_ns": offset + t, "curvature": t / 10, "velocity": 1,
            "odor_encounter": t % 2, "neural": [t, 2 * t],
        })
    events = [{"id": "e", "worm_id": "A", "session_id": "s", "cutoff_ns": offset + 20}]
    return samples, intervals, events


def build(samples, intervals, events):
    return support.build_histories(samples, intervals, events, [1, 2, 3], 6, 0)


class HalfCycleSupportTests(unittest.TestCase):
    def test_complete_past_dependencies_reach_original_history_builder(self):
        samples, intervals, events = fixture()
        result = build(samples, intervals, events)
        row = result["histories"][0]
        self.assertEqual(row["neural_sample_times_ns"], [19, 18, 17])
        self.assertEqual(row["shifted_neural_sample_times_ns"], [13, 12, 11])
        self.assertEqual(row["behavior"], [1.9, 1., 1., 1.8, 1., 0., 1.7, 1., 1.])
        self.assertEqual(row["neural_history"][9:], [19., 38., 18., 36., 17., 34.])
        self.assertEqual(row["shifted_neural_history"][9:], [13., 26., 12., 24., 11., 22.])
        self.assertFalse(result["admission"]["runnable_native"])

    def test_phase_location_before_query_cannot_hide_future_right_crossing(self):
        samples, intervals, events = fixture()
        row = intervals[18]
        row.update(end_ns=20, signal_support_end_ns=20, signal_available_ns=20,
                   crossing_support_end_ns=20, crossing_available_ns=20)
        self.assertEqual(samples[18]["time_ns"], 19)
        with self.assertRaisesRegex(support.ContractError, "future-derived"):
            build(samples, intervals, events)

    def test_upstream_signal_or_crossing_latency_is_not_discarded(self):
        for dependency in ("signal", "crossing"):
            samples, intervals, events = fixture()
            intervals[18][dependency + "_available_ns"] = 20
            with self.subTest(dependency=dependency), self.assertRaisesRegex(
                    support.ContractError, "future-derived"):
                build(samples, intervals, events)

    def test_support_is_joint_maximum_not_nominal_sample_time(self):
        samples, intervals, _ = fixture()
        intervals[0].update(signal_support_end_ns=4, signal_available_ns=7,
                            crossing_support_end_ns=5, crossing_available_ns=6)
        row = support.compile_samples(samples, intervals)[0]
        self.assertEqual(row["time_ns"], 1)
        self.assertEqual((row["support_end_ns"], row["available_ns"]), (5, 7))

    def test_understated_support_or_extra_manual_override_is_rejected(self):
        for mutation in ("signal", "crossing", "override"):
            samples, intervals, _ = fixture()
            if mutation == "override":
                samples[18]["support_end_ns"] = 19
            else:
                intervals[18][mutation + "_support_end_ns"] = 18
            with self.subTest(mutation=mutation), self.assertRaises(support.ContractError):
                support.compile_samples(samples, intervals)

    def test_exact_physical_clocks_above_float_precision(self):
        small = build(*fixture())["histories"][0]
        big = build(*fixture(2 ** 60))["histories"][0]
        self.assertEqual(big["neural_history"], small["neural_history"])
        self.assertEqual(big["neural_sample_times_ns"], [2 ** 60 + t for t in (19, 18, 17)])

    def test_phase_clock_or_float_clock_is_rejected(self):
        for mutation in ("clock", "float"):
            samples, intervals, _ = fixture()
            if mutation == "clock":
                intervals[0]["clock"] = "aligned_frame"
            else:
                samples[0]["time_ns"] = 1.0
            with self.subTest(mutation=mutation), self.assertRaises(support.ContractError):
                support.compile_samples(samples, intervals)

    def test_cross_animal_or_session_interval_cannot_be_borrowed(self):
        for field in ("worm_id", "session_id"):
            samples, intervals, _ = fixture()
            samples[18][field] = "other"
            with self.subTest(field=field), self.assertRaisesRegex(support.ContractError, "identity"):
                support.compile_samples(samples, intervals)

    def test_duplicate_physical_samples_and_unknown_or_unused_intervals_rejected(self):
        for mutation in ("physical", "unknown", "unused", "duplicate_interval"):
            samples, intervals, _ = fixture()
            if mutation == "physical":
                row = copy.deepcopy(samples[0]); row["id"] = "copy"; samples.append(row)
            elif mutation == "unknown":
                samples[0]["interval_id"] = "missing"
            elif mutation == "unused":
                samples.pop()
            else:
                intervals.append(copy.deepcopy(intervals[0]))
            with self.subTest(mutation=mutation), self.assertRaises(support.ContractError):
                support.compile_samples(samples, intervals)

    def test_missing_or_nonfinite_input_and_changed_width_rejected(self):
        for mutation in ("nonfinite", "width", "missing"):
            samples, intervals, _ = fixture()
            if mutation == "nonfinite":
                samples[0]["neural"][0] = float("nan")
            elif mutation == "width":
                samples[0]["neural"].append(1)
            else:
                del intervals[0]["crossing_available_ns"]
            with self.subTest(mutation=mutation), self.assertRaises(support.ContractError):
                support.compile_samples(samples, intervals)

    def test_future_values_do_not_affect_any_returned_history(self):
        samples, intervals, events = fixture()
        before = build(samples, intervals, events)
        for row in samples:
            if row["time_ns"] >= 20:
                row["neural"] = [-999., 999.]
                row["curvature"] = -999.
        after = build(samples, intervals, events)
        self.assertEqual(before["histories"], after["histories"])
        self.assertNotEqual(before["input_sha256"], after["input_sha256"])

    def test_one_bad_event_rejects_complete_request_without_dropping(self):
        samples, intervals, events = fixture()
        events.append({"id": "early", "worm_id": "A", "session_id": "s", "cutoff_ns": 5})
        with self.assertRaisesRegex(support.ContractError, "insufficient history"):
            build(samples, intervals, events)


if __name__ == "__main__":
    unittest.main()
