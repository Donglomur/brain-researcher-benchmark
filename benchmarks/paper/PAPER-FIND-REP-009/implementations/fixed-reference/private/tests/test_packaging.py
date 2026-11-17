"""Generated schema/IO checks only; no numeric scorer, R or empirical data."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
PRIVATE = Path(__file__).resolve().parents[1]
ROOT = PRIVATE.parent
spec = importlib.util.spec_from_file_location("thalamus_portable_adapter", PRIVATE / "grader.py")
wrapper = importlib.util.module_from_spec(spec); spec.loader.exec_module(wrapper)
core = wrapper.load_core()
manifest = json.loads((ROOT / "public/SESSION_MANIFEST.json").read_text())

def generated_pairs():
    pairs = []
    for session in manifest["sessions"]:
        value = {"schema": "thalamus_figure3C_candidate_pair_v1", "cohort_index": session["cohort_index"],
                 "experiment_id": session["experiment_id"], "conditions": []}
        for condition in core.CONDITIONS:
            s = session["condition_specs"][condition]
            value["conditions"].append({"condition": condition, "feature_order": ["uuid_invented"],
                "training_rows": list(range(1, s["training_rows"] + 1)),
                "test_rows": list(range(s["training_rows"] + 1, s["trial_rows"] + 1)),
                "probability_randomised": [0.5] * s["test_rows"]})
        pairs.append(value)
    return pairs

def bodies(values): return [json.dumps(x).encode() for x in values]

class PackagingTests(unittest.TestCase):
    def test_complete_generated_schema(self): self.assertEqual(len(core.validate_all(bodies(generated_pairs()), manifest)), 17)
    def test_short_final_off_cell(self):
        cell = generated_pairs()[-1]["conditions"][0]
        self.assertEqual(len(cell["test_rows"]), 143)
        self.assertEqual(len(cell["test_rows"]) + len(cell["training_rows"]), 477)
    def test_missing_pair(self):
        with self.assertRaises(core.InvalidSubmission): core.validate_all(bodies(generated_pairs())[:-1], manifest)
    def test_wrong_identity_and_condition_order(self):
        for change in ("identity", "order"):
            values = generated_pairs()
            if change == "identity": values[0]["cohort_index"] = 2
            else: values[0]["conditions"].reverse()
            with self.assertRaises(core.InvalidSubmission): core.validate_all(bodies(values), manifest)
    def test_partition_overlap(self):
        values = generated_pairs(); c = values[0]["conditions"][0]; c["test_rows"][0] = c["training_rows"][0]
        with self.assertRaises(core.InvalidSubmission): core.validate_all(bodies(values), manifest)
    def test_probability_types_bounds(self):
        for bad in (True, -0.1, 1.1, float("nan"), "0.5"):
            values = generated_pairs(); values[0]["conditions"][0]["probability_randomised"][0] = bad
            with self.assertRaises(core.InvalidSubmission): core.validate_all(bodies(values), manifest)
    def test_strict_json(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e-999}', b'{"x":"\\ud800"}'):
            with self.assertRaises(core.InvalidSubmission): core.strict_json(raw)
    def test_invalid_feature_roster(self):
        values = generated_pairs(); values[0]["conditions"][0]["feature_order"] = ["uuid_a", "uuid_a"]
        with self.assertRaises(core.InvalidSubmission): core.validate_all(bodies(values), manifest)
    def test_extra_field(self):
        values = generated_pairs(); values[0]["label"] = "not accepted"
        with self.assertRaises(core.InvalidSubmission): core.validate_all(bodies(values), manifest)
    def test_capture_exact_names_and_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            for name, body in zip(wrapper.PAIR_NAMES, bodies(generated_pairs())): (base / name).write_bytes(body)
            self.assertEqual(len(wrapper.capture_pairs(base, core)), 17)
            (base / "extra").write_text("x")
            with self.assertRaises(core.InvalidSubmission): wrapper.capture_pairs(base, core)
            (base / "extra").unlink(); (base / wrapper.PAIR_NAMES[0]).unlink()
            (base / wrapper.PAIR_NAMES[0]).symlink_to(base / wrapper.PAIR_NAMES[1])
            with self.assertRaises(core.InvalidSubmission): wrapper.capture_pairs(base, core)
    def test_public_session_requests(self):
        for s in manifest["sessions"]:
            request = json.loads((ROOT / "public/sessions" / ("pair%03d.json" % s["cohort_index"])).read_text())
            self.assertEqual(set(request), {"schema", "cohort_index", "experiment_id", "conditions"})
            self.assertEqual(request["experiment_id"], s["experiment_id"])
    def test_source_syntax(self):
        for p in PRIVATE.rglob("*.py"): ast.parse(p.read_text(), filename=str(p))

if __name__ == "__main__": unittest.main(verbosity=2)
