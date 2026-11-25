"""Generated input-identity regressions; no scientific data or model execution."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

MODULE = Path(__file__).resolve().parents[1] / "scorer.py"
spec = importlib.util.spec_from_file_location("root005_input_identity", MODULE)
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def inputs(root):
    sessions = np.repeat([f"s{i:02}" for i in range(12)], 2)
    trials = np.array([f"t{i:02}" for i in range(24)])
    stimuli = np.tile(["image-a", "image-b"], 12)
    voxels = np.array(["v0"])
    values = np.tile([-1., 1.], 12)[:, None]
    roster = {"task_id": scorer.TASK_ID, "schema_version": scorer.POLICY,
              "participants": {}}
    reference, prediction = {}, {}
    for sub in scorer.PARTICIPANTS:
        roster["participants"][sub] = {
            "trial_ids": trials.tolist(), "stimulus_ids": stimuli.tolist(),
            "session_ids": sessions.tolist(), "voxel_ids": voxels.tolist()}
        prefix = f"sub_{sub}_"
        reference.update({prefix+"trial_id": trials, prefix+"stimulus_id": stimuli,
                          prefix+"session_id": sessions, prefix+"voxel_id": voxels,
                          prefix+"response": values})
        prediction.update({prefix+"trial_id": trials, prefix+"voxel_id": voxels,
                           prefix+"heldout_session_id": sessions,
                           prefix+"prediction": values})
    paths = {name: root/(name + (".json" if name == "roster" else ".npz"))
             for name in ("roster", "reference", "author", "candidate")}
    paths["roster"].write_text(json.dumps(roster))
    for name, bundle in (("reference", reference), ("author", prediction),
                         ("candidate", prediction)):
        np.savez(paths[name], **bundle)
    replacement = root/"replacement.npz"
    swapped = {key: -value if key.endswith("_prediction") else value
               for key, value in prediction.items()}
    np.savez(replacement, **swapped)
    output = root/"scores.json"
    argv = [str(MODULE)]
    for name, path in paths.items():
        argv.extend(["--"+name, str(path)])
    argv.extend(["--output", str(output)])
    return paths, replacement, output, argv


def correct_or_rejected(output, action):
    try:
        action()
    except ValueError as exc:
        if "input changed" not in str(exc):
            raise
        if output.exists():
            raise AssertionError("Changed input produced an output")
        return
    result = json.loads(output.read_text())
    for sub in scorer.PARTICIPANTS:
        if result["participants"][sub]["candidate_mean_fold_pearson_r"][0] < 0.999999999999:
            raise AssertionError("Replacement predictions were scored under the original hash")


class InputIdentityRegression(unittest.TestCase):
    def test_unchanged_inputs_keep_complete_scores_and_exact_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, _, output, argv = inputs(Path(directory))
            with patch.object(sys, "argv", argv):
                scorer.main()
            result = json.loads(output.read_text())
            self.assertEqual(result["input_sha256"], {
                name: hashlib.sha256(path.read_bytes()).hexdigest()
                for name, path in paths.items()})
            self.assertEqual(set(result["participants"]), set(scorer.PARTICIPANTS))
            for sub in scorer.PARTICIPANTS:
                row = result["participants"][sub]
                self.assertEqual(len(row["folds"]), 12)
                self.assertEqual(row["candidate_defined_folds_per_voxel"], [12])
                self.assertAlmostEqual(row["candidate_mean_fold_pearson_r"][0], 1.)
                self.assertEqual(row["paired_mean_fold_delta_r"], [0.])

    def test_path_replacement_cannot_borrow_the_original_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths, replacement, output, argv = inputs(root)
            actual_load = scorer.np.load
            original_hash = hashlib.sha256(paths["candidate"].read_bytes()).hexdigest()
            calls = 0
            def replace_during_open(source, *args, **kwargs):
                nonlocal calls
                calls += 1
                if calls != 3:
                    return actual_load(source, *args, **kwargs)
                held = root/"held.npz"
                paths["candidate"].rename(held)
                replacement.rename(paths["candidate"])
                try:
                    return actual_load(source, *args, **kwargs)
                finally:
                    paths["candidate"].rename(replacement)
                    held.rename(paths["candidate"])
            with patch.object(scorer.np, "load", replace_during_open), patch.object(sys, "argv", argv):
                correct_or_rejected(output, scorer.main)
            self.assertEqual(hashlib.sha256(paths["candidate"].read_bytes()).hexdigest(), original_hash)

    def test_inplace_change_and_restore_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, replacement, output, argv = inputs(Path(directory))
            original = paths["candidate"].read_bytes()
            changed = replacement.read_bytes()
            actual_load = scorer.load_npz
            calls = 0
            def mutate_during_decode(source):
                nonlocal calls
                calls += 1
                if calls != 3:
                    return actual_load(source)
                paths["candidate"].write_bytes(changed)
                try:
                    return actual_load(source)
                finally:
                    paths["candidate"].write_bytes(original)
            with patch.object(scorer, "load_npz", mutate_during_decode), patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(ValueError, "input changed"):
                    scorer.main()
            self.assertFalse(output.exists())
            self.assertEqual(paths["candidate"].read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
