"""Generated event metadata only; no recordings, protected cohort or model run."""
import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).with_name("raw_event_evidence.py")
spec = importlib.util.spec_from_file_location("n098_raw_event_evidence", path)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


def trial(onset, trigger=1, duration=151, *, sf=1000, blank=None):
    offset = onset + round(parser.DURATIONS[duration] / 1000 * sf)
    blank = onset + round(2 * sf) if blank is None else blank
    return [[onset, 0, trigger], [onset + 20, 0, 101],
            [onset + 40, 0, duration], [onset + 60, 0, 203],
            [onset + 80, 0, 111], [offset, 0, 96], [blank, 0, 97]]


def extract(events, **kwargs):
    args = dict(run=1, sfreq=1000, first_sample=0, n_samples=20000)
    args.update(kwargs)
    return parser.extract_raw_trial_evidence(events, **args)


class RawEvidenceTests(unittest.TestCase):
    def test_selects96_not97_for_all_three_durations(self):
        events = trial(1000, duration=151) + trial(4000, duration=152) + trial(7000, duration=153)
        result = extract(events)
        self.assertEqual([r["offset_sample"] for r in result["rows"]], [1500, 5000, 8500])
        self.assertEqual([r["blank_offset_sample"] for r in result["rows"]], [3000, 6000, 9000])
        self.assertFalse(result["compatible_complete_preparation_binding"])
        self.assertFalse(result["source_export_authenticated"])

    def test_missing96_does_not_fall_back_to97_or_nominal_duration(self):
        events = [r for r in trial(1000) if r[2] != 96]
        with self.assertRaisesRegex(ValueError, "stimulus-offset96"):
            extract(events)

    def test_duplicate96_is_ambiguous_even_at_nominal_time(self):
        events = trial(1000) + [[1500, 1, 96]]
        events.sort(key=lambda x: x[0])
        with self.assertRaisesRegex(ValueError, "stimulus-offset96"):
            extract(events)

    def test_nominal_duration_cannot_hide_a_wrong_raw_clock(self):
        with self.assertRaisesRegex(ValueError, "raw clock"):
            extract(trial(1000), sfreq=500)
        events = trial(1000)
        next(r for r in events if r[2] == 96)[0] += 2
        with self.assertRaisesRegex(ValueError, "raw clock"):
            extract(events)

    def test_button_window_includes_start_excludes_end_and_retains_trial(self):
        events = trial(1000) + trial(4000)
        events += [[499, 0, 255], [500, 0, 255], [1799, 0, 255], [1800, 0, 255]]
        events.sort(key=lambda x: x[0])
        result = extract(events)
        self.assertEqual(result["rows"][0]["button_samples"], [500, 1799])
        self.assertIn("button_in_exclusion_window", result["rows"][0]["event_exclusion_reasons"])
        self.assertEqual(len(result["rows"]), 2)

    def test_all_four_source_categories_are_retained(self):
        events = sum([trial(1000 + 3000 * i, trigger=t) for i, t in enumerate([1, 21, 41, 61])], [])
        rows = extract(events)["rows"]
        self.assertEqual([r["category"] for r in rows], list(parser.CATEGORIES))
        self.assertTrue(all(r["selection_index"] is None and r["epoch_event_sample"] is None for r in rows))

    def test_unknown_last_next_onset_remains_unavailable(self):
        row = extract(trial(1000))["rows"][0]
        self.assertIsNone(row["next_onset_sample"])
        self.assertIsNone(row["next_stimulus_intrudes"])
        self.assertIn("next_onset_unobserved", row["event_exclusion_reasons"])

    def test_intrusion_is_exposed_not_silently_dropped(self):
        events = trial(1000, blank=1600) + trial(1700)
        rows = extract(events)["rows"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["next_stimulus_intrudes"])
        self.assertIn("next_stimulus_intrusion", rows[0]["event_exclusion_reasons"])

    def test_incomplete_raw_baseline_remains_explicit(self):
        row = extract(trial(1000), first_sample=600, n_samples=10000)["rows"][0]
        self.assertFalse(row["raw_event_window_covered"])
        self.assertIn("raw_event_window_not_covered", row["event_exclusion_reasons"])

    def test_large_origin_fractional_rate_buttons_and_next_onset(self):
        onset = 999999980000
        sf = 1000.0000000001
        events = trial(onset, blank=onset + 650) + trial(onset + 800)
        events += [[onset + 800, 0, 255]]
        events.sort(key=lambda row: row[0])
        row = extract(events, sfreq=sf, first_sample=onset - 1000,
                      n_samples=10000)["rows"][0]
        # Absolute addition loses this fraction at the admitted large origin.
        self.assertEqual(onset + .8 * sf, onset + 800)
        self.assertLess(800 / sf, .8)
        self.assertEqual(row["button_samples"], [onset + 800])
        self.assertTrue(row["next_stimulus_intrudes"])

    def test_fractional_rate_relative_baseline_coverage(self):
        onset = 999999980000
        sf = 1000.0000000001
        row = extract(trial(onset), sfreq=sf, first_sample=onset - 500,
                      n_samples=10000)["rows"][0]
        self.assertLess(500 / sf, .5)
        self.assertFalse(row["raw_event_window_covered"])

    def test_fractional_rate_relative_stop_coverage(self):
        onset = 999999980000
        sf = 1000.0000000001
        row = extract(trial(onset, blank=onset + 650), sfreq=sf,
                      first_sample=onset - 1000, n_samples=1800)["rows"][0]
        self.assertLess(800 / sf, .8)
        self.assertFalse(row["raw_event_window_covered"])

    def test_exact_relative_coverage_and_next_onset_endpoint(self):
        onset = 999999980000
        events = trial(onset, blank=onset + 650) + trial(onset + 800)
        events += [[onset + 800, 0, 255]]
        events.sort(key=lambda row: row[0])
        row = extract(events, first_sample=onset - 500, n_samples=10000)["rows"][0]
        self.assertTrue(row["raw_event_window_covered"])
        self.assertEqual(row["button_samples"], [])
        self.assertFalse(row["next_stimulus_intrudes"])
        last = extract(trial(onset, blank=onset + 650),
                       first_sample=onset - 500, n_samples=1300)["rows"][0]
        self.assertTrue(last["raw_event_window_covered"])

    def test_unknown_codes_and_ambiguous_conditions_are_refused(self):
        for bad in [84, 104, 154, 204]:
            events = trial(1000) + [[1100, 0, bad]]
            events.sort(key=lambda x: x[0])
            with self.assertRaisesRegex(ValueError, "unresolved event code"):
                extract(events)
        events = trial(1000) + [[1100, 0, 152]]
        events.sort(key=lambda x: x[0])
        with self.assertRaisesRegex(ValueError, "one observed duration"):
            extract(events)

    def test_ordered_bounded_scalar_inputs(self):
        for kwargs in [dict(run=True), dict(sfreq=True), dict(sfreq=float("nan")), dict(n_samples=2)]:
            with self.assertRaises(ValueError):
                extract(trial(1000), **kwargs)
        with self.assertRaisesRegex(ValueError, "ordered events"):
            extract(list(reversed(trial(1000))))
        events = trial(1000)
        events.insert(1, events[0].copy())
        with self.assertRaisesRegex(ValueError, "duplicate raw event"):
            extract(events)


if __name__ == "__main__":
    unittest.main()
