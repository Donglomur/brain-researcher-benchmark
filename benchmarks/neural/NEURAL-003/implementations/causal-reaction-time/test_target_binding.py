"""Generated target-callback controls; no recordings or authentic targets."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from neural003 import scoring


def predecessor():
    name = "neural003.scoring_before_roster_snapshot"
    spec = importlib.util.spec_from_file_location(
        name, HERE / "fixtures" / "scoring_before_roster_snapshot.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


OLD = predecessor()


def panel(mutable=False):
    expected, outputs, targets = {}, {}, {}
    for person in range(26):
        ids = tuple(format(2 * person + index, "032x") for index in range(2))
        for arm in scoring.ARMS:
            expected[(person, arm)] = list(ids) if mutable else ids
            predicted = (0.25, 1.25) if arm == "eeg" else (0.75, 0.75)
            outputs[(person, arm)] = [
                {"trial_id": ident, "rt_seconds": value}
                for ident, value in zip(ids, predicted)]
        targets[person] = [
            {"trial_id": ident, "rt_seconds": value}
            for ident, value in zip(ids, (1.25, 0.25))]
    return expected, outputs, targets


def retarget(expected, targets, inplace):
    for key, ids in tuple(expected.items()):
        if inplace:
            ids.reverse()
        else:
            expected[key] = tuple(reversed(ids))
    return {person: list(reversed(rows)) for person, rows in targets.items()}


class TargetRosterBindingTests(unittest.TestCase):
    def test_predecessor_silently_scores_retargeted_trials_as_perfect(self):
        for inplace in (False, True):
            expected, outputs, targets = panel(mutable=inplace)
            result = OLD.grade(outputs, expected,
                               lambda: retarget(expected, targets, inplace))
            self.assertEqual(result["macro_mae_seconds"]["eeg"], 0.0)
            self.assertEqual(result["macro_mae_seconds"]["contrast_instruction"], 0.5)

    def test_callback_cannot_replace_or_reverse_admitted_trial_roster(self):
        for inplace in (False, True):
            expected, outputs, targets = panel(mutable=inplace)
            with self.subTest(inplace=inplace), self.assertRaisesRegex(
                    ValueError, "private target join"):
                scoring.grade(outputs, expected,
                              lambda: retarget(expected, targets, inplace))

    def test_original_targets_keep_original_score_despite_caller_mutation(self):
        for inplace in (False, True):
            expected, outputs, targets = panel(mutable=inplace)
            def callback():
                retarget(expected, targets, inplace)
                return targets
            result = scoring.grade(outputs, expected, callback)
            self.assertEqual(result["macro_mae_seconds"]["eeg"], 1.0)
            self.assertEqual(result["macro_mae_seconds"]["contrast_instruction"], 0.5)
            self.assertEqual(result["paired_gain_seconds"], -0.5)

    def test_unchanged_tuple_and_list_rosters_preserve_entire_result(self):
        for mutable in (False, True):
            expected, outputs, targets = panel(mutable)
            before = copy.deepcopy(expected)
            result = scoring.grade(outputs, expected, lambda: targets)
            self.assertEqual(result, OLD.grade(outputs, expected, lambda: targets))
            self.assertEqual(expected, before)

    def test_caller_mapping_cleared_by_callback_does_not_remove_admitted_ids(self):
        expected, outputs, targets = panel()
        def callback():
            expected.clear()
            return targets
        result = scoring.grade(outputs, expected, callback)
        self.assertEqual(result["macro_mae_seconds"]["eeg"], 1.0)

    def test_invalid_public_admission_still_precedes_callback(self):
        for invalid in ("output", "expected", "mapping"):
            expected, outputs, targets = panel()
            if invalid == "output":
                outputs[(25, "contrast_instruction")].pop()
            elif invalid == "expected":
                expected[(25, "eeg")] = ("invalid", "invalid")
            else:
                expected = None
            called = []
            def callback():
                called.append(True)
                return targets
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                scoring.grade(outputs, expected, callback)
            self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
