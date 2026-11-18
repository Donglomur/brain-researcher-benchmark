"""Generated sample-grid controls; no MNE, recordings, fits or target data."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from neural003 import window


def predecessor():
    name = "neural003_window_before_sample_grid"
    spec = importlib.util.spec_from_file_location(
        name, HERE / "fixtures" / "window_before_sample_grid.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


OLD = predecessor()


class Block:
    def __init__(self, source, picks, start, stop):
        self.source, self.picks, self.start = source, picks, start
        self.shape = (len(picks), stop - start)

    def __getitem__(self, index):
        channel, offset = index
        return self.source.signal(self.picks[channel], self.start + offset)


class Reader:
    """get_data indices are relative to first_samp, as in the documented API."""
    def __init__(self, first=0, count=6000, signal=None):
        self.first_samp, self.n_times = first, count
        self.info = {"sfreq": 1024}
        self.signal = signal or (lambda channel, sample: 0.0)
        self.calls = []

    def get_data(self, *, picks, start, stop):
        self.calls.append((tuple(picks), start, stop))
        if not 0 <= start < stop <= self.n_times:
            raise AssertionError("generated reader range exceeded")
        return Block(self, picks, start, stop)


def signal(channel, sample):
    return (channel - 15) * ((sample % 17) - 8) * 1e-6


class SampleGridTests(unittest.TestCase):
    picks = tuple(range(32))

    def produce(self, raw, origin=0, budget=1403):
        return window.produce_prefix(
            raw, self.picks, window.schedule(origin, origin + 1300), budget)

    def test_predecessor_nonzero_origin_can_read_after_deadline(self):
        # Only data unavailable at the intended deadline carry a signal.
        future = lambda channel, sample: float(channel == 0 and sample >= 1403)
        old_reader = Reader(2000, signal=future)
        old_plan = OLD.schedule(2000, 3300)
        old_values = OLD.produce_prefix(old_reader, self.picks, old_plan, 1403)
        new_reader = Reader(2000, signal=future)
        new_values = self.produce(new_reader, 2000)
        self.assertEqual(len(old_values), 307)  # Shape alone did not catch it.
        self.assertTrue(any(row[0] > 0 for row in old_values))
        self.assertTrue(all(all(value == 0 for value in row) for row in new_values))
        self.assertGreater(2000 + old_reader.calls[-1][2] - 1, 3402)
        self.assertEqual(2000 + new_reader.calls[-1][2] - 1, 3402)

    def test_zero_origin_preserves_predecessor_values_and_reads(self):
        before, after = Reader(signal=signal), Reader(signal=signal)
        old_values = OLD.produce_prefix(before, self.picks, OLD.schedule(0, 1300), 1403)
        values = self.produce(after)
        self.assertEqual(values, old_values)
        self.assertEqual(after.calls, before.calls)
        self.assertEqual(window.fixed_features(values), OLD.fixed_features(old_values))

    def test_coordinate_translation_preserves_signal_and_full_history(self):
        zero, shifted = Reader(signal=signal), Reader(2000, signal=signal)
        self.assertEqual(self.produce(zero), self.produce(shifted, 2000))
        self.assertEqual(zero.calls, shifted.calls)
        self.assertEqual([(start, stop) for _, start, stop in shifted.calls],
                         [(0, 1024), (1024, 1403)])

    def test_future_only_perturbation_does_not_change_features(self):
        def changed(channel, sample):
            if sample >= 1403:
                return 1e12 * (channel + 1)
            return signal(channel, sample)
        a, b = Reader(2000, signal=signal), Reader(2000, signal=changed)
        self.assertEqual(window.fixed_features(self.produce(a, 2000)),
                         window.fixed_features(self.produce(b, 2000)))

    def test_missing_cropped_or_short_reader_refused_before_capture(self):
        readers = [Reader(2001), Reader(1999), Reader(2000, 1402), Reader(2000, 0)]
        missing = Reader(2000)
        del missing.first_samp
        readers.append(missing)
        for raw in readers:
            with self.subTest(first=getattr(raw, "first_samp", "missing"), count=raw.n_times):
                with self.assertRaises(ValueError):
                    self.produce(raw, 2000)
                self.assertEqual(raw.calls, [])

    def test_reader_integer_scalars_supported_without_accepting_float_or_bool(self):
        class IndexScalar:
            def __init__(self, value):
                self.value = value
            def __index__(self):
                return self.value
        raw = Reader(2000)
        raw.first_samp = IndexScalar(2000)
        # Block range comparison needs the real count; only the origin scalar
        # exercises non-builtin integer compatibility on this generated reader.
        self.assertEqual(len(self.produce(raw, 2000)), 307)
        for field, value in (("first_samp", 2000.0), ("first_samp", True),
                             ("n_times", 6000.0), ("n_times", True)):
            raw = Reader(2000)
            setattr(raw, field, value)
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    self.produce(raw, 2000)
                self.assertEqual(raw.calls, [])

    def test_exact_deadline_and_forged_schedule_eligibility(self):
        plan = window.schedule(2000, 3300)
        self.assertTrue(window.response_at_or_before_deadline(3402, plan))
        self.assertFalse(window.response_at_or_before_deadline(3403, plan))
        for forged in (replace(plan, deadline_numerator=999999),
                       replace(plan, deadline_denominator=1),
                       replace(plan, start=plan.start + 1),
                       replace(plan, stop=plan.stop + 1)):
            with self.subTest(forged=forged):
                with self.assertRaises(ValueError):
                    window.response_at_or_before_deadline(3402, forged)

    def test_history_budget_refuses_before_capture(self):
        raw = Reader(2000)
        with self.assertRaisesRegex(ValueError, "history budget"):
            self.produce(raw, 2000, budget=1402)
        self.assertEqual(raw.calls, [])

    def test_first_native_error_identity_is_preserved(self):
        error = RuntimeError("generated capture failure")
        class FailedReader(Reader):
            def get_data(self, **kwargs):
                self.calls.append(kwargs)
                raise error
        raw = FailedReader(2000)
        with self.assertRaises(RuntimeError) as caught:
            self.produce(raw, 2000)
        self.assertIs(caught.exception, error)
        self.assertEqual(raw.calls[0]["start"], 0)
        self.assertEqual(raw.calls[0]["stop"], 1024)
        self.assertIn("attempted logical scalar reads=32768", error.__notes__[0])


if __name__ == "__main__":
    unittest.main()
