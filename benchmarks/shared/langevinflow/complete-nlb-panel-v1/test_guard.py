"""Generated interface controls; the original numerical evaluator is never run."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import h5py
import numpy as np

MODULE = Path(__file__).with_name("guard.py")
loader = importlib.util.spec_from_file_location("langevin_guard", MODULE)
guard = importlib.util.module_from_spec(loader)
loader.loader.exec_module(guard)
FIXTURE_CAP = 1572864
FIXTURE_WRITTEN = 0
FIXTURE_PEAK = 0


def tracked_write(path, action, upper=524288):
    """Reserve before each fixture/write; account every observed file version."""
    global FIXTURE_WRITTEN, FIXTURE_PEAK
    if FIXTURE_WRITTEN + upper > FIXTURE_CAP:
        raise RuntimeError("prospective generated-fixture budget exhausted")
    try:
        return action()
    finally:
        size = path.stat().st_size if path.exists() else 0
        FIXTURE_WRITTEN += size
        FIXTURE_PEAK = max(FIXTURE_PEAK, sum(p.stat().st_size for p in path.parent.iterdir() if p.is_file()))
        if size > upper:
            raise RuntimeError("generated fixture exceeded its reserved bound")


def payloads():
    submission, targets = {}, {}
    for group in guard.GROUPS:
        dataset, _, observed, forward, _ = guard.spec(group)
        submission[group] = {
            key: np.ones((2, forward if key.endswith("_forward") else observed, 1), dtype=np.float32)
            for key in guard.RATE_KEYS
        }
        target = {"eval_spikes_heldout": np.ones((2, observed, 1), dtype=np.float32),
                  "eval_spikes_heldin_forward": np.ones((2, forward, 1), dtype=np.float32),
                  "eval_spikes_heldout_forward": np.ones((2, forward, 1), dtype=np.float32)}
        for split in ("train", "eval"):
            target[split + "_behavior"] = np.ones((2, 5) if dataset == "dmfc_rsg" else (2, observed, 2), dtype=np.float32)
        if dataset != "mc_rtt":
            target["psth"] = np.ones((1, observed, 2), dtype=np.float32)
            indices = np.empty(1, dtype=object)
            indices[0] = np.array([0, 1], dtype=np.int64)
            target["eval_cond_idx"] = indices
        if dataset == "area2_bump":
            target["train_decode_mask"] = np.array([[True, False], [False, True]])
            target["eval_decode_mask"] = np.array([[True, False], [False, True]])
        if dataset == "dmfc_rsg":
            target["eval_spikes_heldout"][:, :3] = np.nan
            target["eval_behavior"][0, -1] = np.nan
            target["psth"][:, :3] = np.nan
            target["eval_jitter"] = np.zeros(2, dtype=np.int64)
            submission[group]["eval_rates_heldout"][:, :3] = np.nan
        targets[group] = target
    return submission, targets


def results():
    return [{group + "_split": {metric: float(i) / 10 for i, metric in enumerate(guard.spec(group)[4])}}
            for group in guard.GROUPS]


def write_h5(path, payload):
    def write():
        with h5py.File(path, "w") as handle:
            for group, fields in payload.items():
                dest = handle.create_group(group)
                for name, array in fields.items():
                    if array.dtype.kind == "O":
                        dest.create_dataset(name, data=array, dtype=h5py.vlen_dtype(np.dtype("int64")))
                    else:
                        dest.create_dataset(name, data=array)
    return tracked_write(path, write)


class GuardTests(unittest.TestCase):
    def test_complete_panel_is_only_structural_coverage(self):
        submission, targets = payloads()
        shapes = guard.validate_submission(submission)
        guard.validate_targets(targets, shapes)
        self.assertEqual(len(shapes), 8)
        self.assertEqual(sum(len(guard.spec(g)[4]) for g in guard.GROUPS), 30)

    def test_wrong_time_resolution_refused(self):
        submission, _ = payloads()
        submission["mc_maze_20"]["eval_rates_heldout"] = np.ones((2, 140, 1))
        with self.assertRaises(guard.ContractError):
            guard.validate_submission(submission)

    def test_forward_unit_mismatch_refused(self):
        submission, _ = payloads()
        submission["dmfc_rsg"]["eval_rates_heldin_forward"] = np.ones((2, 40, 2))
        with self.assertRaises(guard.ContractError):
            guard.validate_submission(submission)

    def test_missing_author_rate_field_refused(self):
        submission, _ = payloads()
        del submission["dmfc_rsg"]["train_rates_heldin"]
        with self.assertRaises(guard.ContractError):
            guard.validate_submission(submission)

    def test_target_trial_mismatch_refused(self):
        submission, targets = payloads()
        targets["mc_rtt"]["train_behavior"] = np.ones((3, 120, 2))
        with self.assertRaises(guard.ContractError):
            guard.validate_targets(targets, guard.validate_submission(submission))

    def test_target_forward_companion_required(self):
        submission, targets = payloads()
        del targets["mc_maze"]["eval_spikes_heldin_forward"]
        with self.assertRaises(guard.ContractError):
            guard.validate_targets(targets, guard.validate_submission(submission))

    def test_area2_both_original_masks_required(self):
        submission, targets = payloads()
        targets["area2_bump"]["train_decode_mask"] = np.ones((2, 1), dtype=bool)
        targets["area2_bump"]["eval_decode_mask"] = np.ones((2, 1), dtype=bool)
        with self.assertRaises(guard.ContractError):
            guard.validate_targets(targets, guard.validate_submission(submission))

    def test_additional_official_target_groups_allowed(self):
        submission, targets = payloads()
        targets["mc_maze_large"] = {"uninspected": object()}
        guard.validate_targets(targets, guard.validate_submission(submission))

    def test_masked_nans_and_source_order_are_unchanged(self):
        submission, targets = payloads()
        before_submission = {g: {k: v.tobytes() for k, v in fields.items()} for g, fields in submission.items()}
        before_targets = {g: {k: v.tobytes() for k, v in fields.items() if v.dtype.kind != "O"}
                          for g, fields in targets.items()}
        guard.validate_targets(targets, guard.validate_submission(submission))
        self.assertEqual(before_submission, {g: {k: v.tobytes() for k, v in fields.items()} for g, fields in submission.items()})
        self.assertEqual(before_targets, {g: {k: v.tobytes() for k, v in fields.items() if v.dtype.kind != "O"}
                                        for g, fields in targets.items()})

    def test_operator_file_flow_uses_fake_evaluator_and_keeps_unknown_qualification(self):
        submission, targets = payloads()
        with tempfile.TemporaryDirectory(prefix="langevin-generated-") as temporary:
            folder = Path(temporary)
            prediction, target = folder / "predictions.h5", folder / "targets.h5"
            freeze_path, output = folder / "freeze.json", folder / "score.json"
            write_h5(prediction, submission)
            write_h5(target, targets)
            frozen = tracked_write(freeze_path, lambda: guard.freeze(prediction, freeze_path, max_submission_bytes=524288), upper=16384)
            self.assertFalse(frozen["authentic_case_coverage_qualified"])
            seen = []
            def fake_evaluate(target_handle, prediction_handle):
                seen.append((set(target_handle.keys()), set(prediction_handle.keys())))
                self.assertTrue(np.isnan(target_handle["dmfc_rsg"]["eval_spikes_heldout"][0, 0, 0]))
                self.assertTrue(np.isnan(prediction_handle["dmfc_rsg"]["eval_rates_heldout"][0, 0, 0]))
                return results()
            original_snapshot = guard._snapshot
            def snapshot(source, destination, maximum, expected):
                return tracked_write(Path(destination), lambda: original_snapshot(source, destination, maximum, expected))
            target_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            with patch.object(guard, "TARGET_SHA256", target_hash), \
                 patch.object(guard, "load_original_scorer", return_value=types.SimpleNamespace(evaluate=fake_evaluate)), \
                 patch.object(guard, "_snapshot", side_effect=snapshot), \
                 patch.object(guard.importlib.metadata, "version", return_value="generated-control"):
                report = tracked_write(output, lambda: guard.score(prediction, freeze_path, target, "unused-source", output,
                                       max_submission_bytes=524288), upper=16384)
            self.assertEqual(len(seen), 1)
            self.assertEqual(report["results"], results())
            self.assertEqual(report["scientific_qualification"], "unestablished")
            self.assertFalse(report["authentic_case_coverage_qualified"])

    def test_changed_submission_fails_before_target_or_scorer_access(self):
        submission, _ = payloads()
        with tempfile.TemporaryDirectory(prefix="langevin-generated-") as temporary:
            folder = Path(temporary)
            prediction, freeze_path = folder / "predictions.h5", folder / "freeze.json"
            write_h5(prediction, submission)
            tracked_write(freeze_path, lambda: guard.freeze(prediction, freeze_path, max_submission_bytes=524288), upper=16384)
            def mutate():
                with h5py.File(prediction, "r+") as handle:
                    handle["mc_maze"]["eval_rates_heldin"][0, 0, 0] = 2
            tracked_write(prediction, mutate)
            with patch.object(guard, "load_original_scorer", side_effect=AssertionError("unexpected evaluator load")):
                with self.assertRaisesRegex(guard.ContractError, "changed after freeze"):
                    guard.score(prediction, freeze_path, folder / "never-created-target.h5", "unused-source", folder / "no-result.json",
                                max_submission_bytes=524288)
            self.assertFalse((folder / "no-result.json").exists())


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GuardTests)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    print(json.dumps({"generated_controls": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                      "fixture_version_bytes": FIXTURE_WRITTEN, "peak_observed_fixture_bytes": FIXTURE_PEAK,
                      "retained_fixture_bytes": 0, "fixture_cap_bytes": FIXTURE_CAP,
                      "guard_sha256": hashlib.sha256(MODULE.read_bytes()).hexdigest(),
                      "original_numeric_evaluator_executed": False}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
