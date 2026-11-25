"""Generated controls: each named NPZ operand has exactly one member."""
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

import numpy as np


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPONENT = Path(__file__).resolve().parents[1]
selector = load("find024_member_selector", COMPONENT / "selector.py")
evaluator = load("find024_member_evaluator", COMPONENT.parent / "initial-evaluator-v1" / "evaluator.py")


def duplicate(path, name, value):
    data = io.BytesIO()
    np.save(data, value, allow_pickle=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr(name + ".npy", data.getvalue())


def selection_fixture(path):
    np.savez(path, loss=np.arange(4.).reshape(2, 2, 1, 1, 1, 1),
             intper_sec=[.1, .3], delay_sec_start=[0.], shape=[1.],
             boundstrength=[0.], channel_ids=["electrode-A"],
             rates=[1 / math.sqrt(3), math.sqrt(3)])


def manifest_fixture(root, source):
    manifest = {"schema": evaluator.SCHEMA, "input_role": "empirical_electrode_timecourses",
                "boundary_policy": "explicit_distinct_contexts", "alignment_policy": "linear_interpolation",
                "cohort_id": "generated", "eligibility_provenance": "generated",
                "selection_uses_assessment_effects": False, "lags_sec": [0., 1.],
                "expected_participants": ["p1"], "story_splits": {"story": "analysis"},
                "evaluation_mode": "unsplit_recomputation", "participants": [{"participant_id": "p1",
                "source": {"role": "empirical_electrode_timecourses", "npz_path": source.name,
                           "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}]}
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


class MemberAdmissionTests(unittest.TestCase):
    def test_selector_rejects_duplicate_named_operand(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, out = root / "grid.npz", root / "result.json"
            selection_fixture(path)
            duplicate(path, "channel_ids", np.array(["conflicting-electrode"]))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(selector.SelectionError, "duplicate members"):
                selector.main([str(path), str(out), "--expected-sha256", digest])
            self.assertFalse(out.exists())

    def test_timecourse_loader_rejects_duplicate_named_operand(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "traces.npz"
            np.savez(path, D=np.arange(4.), t=[0., 1.])
            duplicate(path, "D", np.arange(4.) + 100.)
            manifest = manifest_fixture(root, path)
            with self.assertRaisesRegex(evaluator.ContractError, "duplicate members"):
                evaluator.load_input(manifest)

    def test_unambiguous_inputs_preserve_selected_values_and_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, out = root / "grid.npz", root / "result.json"
            selection_fixture(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            selector.main([str(path), str(out), "--expected-sha256", digest])
            result = json.loads(out.read_text())
            self.assertEqual(result["input_sha256"], digest)
            self.assertEqual([row["channel_id"] for row in result["rows"]], ["electrode-A"] * 2)
            traces = root / "traces.npz"
            expected = np.arange(4.)
            np.savez(traces, D=expected, t=[0., 1.])
            _, arrays, receipts = evaluator.load_input(manifest_fixture(root, traces))
            np.testing.assert_array_equal(arrays["p1"]["D"], expected)
            self.assertEqual(receipts[0]["sha256"], hashlib.sha256(traces.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
