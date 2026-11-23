"""Generated controls for participant-only formatting; no original data or score."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import h5py
import numpy as np


SPEC = importlib.util.spec_from_file_location("submission_check", Path(__file__).with_name("check_submission.py"))
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)
SOURCE_DIR = Path(__file__).resolve().parent.parent / "source-matched-nlb-v1"
SCRATCH_DIR = None
WRITTEN_BYTES = 0


def charge(path):
    global WRITTEN_BYTES
    WRITTEN_BYTES += Path(path).stat().st_size


class SubmissionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = check.load_validator(SOURCE_DIR)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="smc-preflight-control-", dir=SCRATCH_DIR)
        self.root = Path(self.temporary.name)
        self.panel_path = self.root / "panel.json"
        self.reference = self.root / "generated_reference.json"
        self.prediction = self.root / "prediction.h5"
        self.panel = {
            "schema": "smc_nlb_panel_v1", "dataset": "mc_maze_20", "phase": "test",
            "source_commit": self.validator.AUTHOR_COMMIT, "dandiset": "000128",
            "dandi_version": "0.220113.0400", "bin_ms": 20,
            "n_train": 3, "n_eval": 2, "n_bins": 35, "forward_bins": 10,
            "n_heldin": 137, "n_heldout": 45, "condition_count": 108,
            "trial_indices_sha256": "1" * 64, "neuron_indices_sha256": "2" * 64,
            "conditions_sha256": "3" * 64, "split_counts": {"train": 2, "val": 1, "test": 2},
            "tensor_trial_indices_sha256": "4" * 64, "condition_membership_sha256": "5" * 64,
            "inputs_sha256": {"generated_input": "6" * 64},
            "input_content_sha256": {"generated_input": "7" * 64},
            "nwb_sources": [{"name": "generated_fixture", "sha256": "8" * 64}],
        }
        self.panel["expected_shapes"] = {
            name: [3 if name.startswith("train_") else 2,
                   10 if name.endswith("_forward") else 35,
                   137 if "heldin" in name else 45]
            for name in self.validator.RATE_KEYS
        }
        self.write_panel()
        self.reference.write_text(json.dumps(self.panel))
        charge(self.reference)
        self.write_prediction(self.prediction)
        self.reference_patch = patch.object(self.validator, "REFERENCE_PANEL", self.reference)
        self.reference_patch.start()
        self.loader_patch = patch.object(check, "load_validator", return_value=self.validator)
        self.loader_patch.start()
        self.no_evaluator = patch.object(self.validator, "load_original_scorer",
                                        side_effect=AssertionError("No evaluator is permitted"))
        self.no_evaluator.start()
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.reference_patch.stop)
        self.addCleanup(self.loader_patch.stop)
        self.addCleanup(self.no_evaluator.stop)

    def write_panel(self):
        self.panel_path.write_text(json.dumps(self.panel))
        charge(self.panel_path)
        self.panel_sha = hashlib.sha256(self.panel_path.read_bytes()).hexdigest()

    def write_prediction(self, path, *, optional=False):
        names = self.validator.RATE_KEYS if optional else self.validator.REQUIRED_KEYS
        with h5py.File(path, "w") as handle:
            group = handle.create_group("mc_maze_20")
            for name in names:
                group.create_dataset(name, shape=self.panel["expected_shapes"][name], dtype="f4", fillvalue=0.25)
        charge(path)

    def run_check(self, **options):
        arguments = dict(panel=self.panel_path, panel_sha256=self.panel_sha,
                         outcome="improvement", submissions={"offline": self.prediction},
                         max_bytes=1024 * 1024, source_dir=SOURCE_DIR)
        arguments.update(options)
        return check.check_submissions(**arguments)

    def test_single_condition_complete_submission_is_target_blind(self):
        report = self.run_check()
        self.assertTrue(report["format_valid"])
        self.assertFalse(report["operator_frozen"])
        self.assertFalse(report["target_accessed"])
        self.assertEqual(report["scientific_outcome"], "unknown")
        self.assertEqual(set(report["submissions"]["offline"]["arrays"]), self.validator.REQUIRED_KEYS)
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_complete_two_method_reproduction_all_eight_arrays(self):
        other = self.root / "other.h5"
        self.write_prediction(other, optional=True)
        report = self.run_check(outcome="reproduction", submissions={"causal": self.prediction, "noncausal": other})
        self.assertEqual(set(report["submissions"]), {"causal", "noncausal"})
        self.assertEqual(len(report["submissions"]["noncausal"]["arrays"]), 8)

    def test_reproduction_requires_both_methods_before_source_loading(self):
        with self.assertRaisesRegex(ValueError, "both causal/noncausal"):
            self.run_check(outcome="reproduction", submissions={"causal": self.prediction})
        check.load_validator.assert_not_called()

    def test_total_byte_cap_applies_to_complete_pair(self):
        size = self.prediction.stat().st_size
        with self.assertRaisesRegex(ValueError, "complete prediction set exceeds"):
            self.run_check(outcome="reproduction", submissions={"causal": self.prediction, "noncausal": self.prediction},
                           max_bytes=2 * size - 1)
        check.load_validator.assert_not_called()

    def test_wrong_panel_pin_fails_before_source_loading(self):
        with self.assertRaisesRegex(ValueError, "differs from supplied pin"):
            self.run_check(panel_sha256="f" * 64)
        check.load_validator.assert_not_called()

    def test_rehashed_changed_panel_still_fails_source_identity(self):
        self.panel["neuron_indices_sha256"] = "9" * 64
        self.write_panel()
        with self.assertRaisesRegex(ValueError, "complete source reference"):
            self.run_check()

    def test_missing_forward_array_fails(self):
        with h5py.File(self.prediction, "a") as handle:
            del handle["mc_maze_20"]["eval_rates_heldout_forward"]
        charge(self.prediction)
        with self.assertRaisesRegex(ValueError, "missing or extra rate arrays"):
            self.run_check()

    def test_one_optional_train_forward_array_is_not_a_complete_pair(self):
        name = "train_rates_heldin_forward"
        with h5py.File(self.prediction, "a") as handle:
            handle["mc_maze_20"].create_dataset(name, shape=self.panel["expected_shapes"][name], dtype="f4")
        charge(self.prediction)
        with self.assertRaisesRegex(ValueError, "missing or extra rate arrays"):
            self.run_check()

    def test_shape_mismatch_is_refused(self):
        with h5py.File(self.prediction, "a") as handle:
            group = handle["mc_maze_20"]
            del group["eval_rates_heldout"]
            group.create_dataset("eval_rates_heldout", shape=(1, 35, 45), dtype="f4")
        charge(self.prediction)
        with self.assertRaisesRegex(ValueError, "incomplete or misaligned"):
            self.run_check()

    def test_negative_nan_and_infinite_values_are_refused(self):
        for value in (-1.0, np.nan, np.inf):
            with self.subTest(value=value):
                with h5py.File(self.prediction, "a") as handle:
                    handle["mc_maze_20"]["eval_rates_heldout"][0, 0, 0] = value
                charge(self.prediction)
                with self.assertRaisesRegex(ValueError, "finite and nonnegative"):
                    self.run_check()

    def test_external_link_does_not_read_its_missing_destination(self):
        with h5py.File(self.prediction, "a") as handle:
            group = handle["mc_maze_20"]
            del group["eval_rates_heldout"]
            group["eval_rates_heldout"] = h5py.ExternalLink(str(self.root / "never-created-target.h5"), "/target")
        charge(self.prediction)
        with self.assertRaisesRegex(ValueError, "external or soft HDF5"):
            self.run_check()

    def test_symlink_and_empty_files_refused_before_loading_source(self):
        link = self.root / "link.h5"
        link.symlink_to(self.prediction)
        with self.assertRaisesRegex(ValueError, "regular file"):
            self.run_check(submissions={"offline": link})
        empty = self.root / "empty.h5"
        empty.touch()
        with self.assertRaisesRegex(ValueError, "empty file"):
            self.run_check(submissions={"offline": empty})
        check.load_validator.assert_not_called()

    def test_changed_earlier_method_is_detected_after_pair_validation(self):
        other = self.root / "other.h5"
        self.write_prediction(other)
        # Allocate the data block first so the later mutation keeps file size.
        with h5py.File(self.prediction, "a") as handle:
            handle["mc_maze_20"]["eval_rates_heldout"][0, 0, 0] = 0.25
        charge(self.prediction)
        original = self.validator.validate_submission
        calls = []
        def validate_and_mutate(path, panel):
            result = original(path, panel)
            calls.append(path)
            if len(calls) == 2:
                with h5py.File(self.prediction, "a") as handle:
                    handle["mc_maze_20"]["eval_rates_heldout"][0, 0, 0] = 0.5
                charge(self.prediction)
            return result
        with patch.object(self.validator, "validate_submission", side_effect=validate_and_mutate):
            with self.assertRaisesRegex(ValueError, "complete-set preflight"):
                self.run_check(outcome="reproduction", submissions={"causal": self.prediction, "noncausal": other})

    def test_changed_retained_source_is_not_imported(self):
        bad_source = self.root / "source"
        bad_source.mkdir()
        path = bad_source / "scorer.py"
        path.write_text("raise AssertionError('must not import changed code')\n")
        charge(path)
        self.loader_patch.stop()
        with self.assertRaisesRegex(ValueError, "retained validation source differs"):
            check.load_validator(bad_source)

    def test_cli_emits_only_complete_success_json(self):
        args = ["--panel", str(self.panel_path), "--panel-sha256", self.panel_sha,
                "--outcome", "improvement", "--submission", "offline=" + str(self.prediction),
                "--max-bytes", "1048576", "--source-dir", str(SOURCE_DIR)]
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            check.main(args)
        self.assertTrue(json.loads(stream.getvalue())["format_valid"])
        stream, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as caught:
                check.main(args + ["--submission", "offline=duplicate.h5"])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(stream.getvalue(), "")
        self.assertIn("duplicate key", errors.getvalue())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--scratch-dir", type=Path)
    args = parser.parse_args()
    SOURCE_DIR, SCRATCH_DIR = args.source_dir, args.scratch_dir
    outcome = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SubmissionChecks))
    print(json.dumps({"generated_file_write_charge_bytes": WRITTEN_BYTES,
                      "original_data_or_target_reads": 0, "scientific_results": 0}))
    raise SystemExit(0 if outcome.wasSuccessful() else 1)
