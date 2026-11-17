"""Generated engineering controls for strict export admission and report behavior."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluator as e


def fixture(root):
    near = np.tile(np.arange(5.0)[:, None], (1, 46))
    far = near.copy()
    far[:, 34:37] *= -1
    arrays = root / "generated.npz"
    np.savez(arrays, near_binF=near, far_binF=far, cell_ids=np.arange(5))
    pin = hashlib.sha256(arrays.read_bytes()).hexdigest()
    animals = []
    for animal in e.ANIMALS:
        sessions = [{"session_index": day, "cue_sets": ["Cue Set A"],
                     "behavior_record": f"generated-{day}", "selection": "putative/excl_no_response",
                     "arrays": "generated.npz", "sha256": pin} for day in range(2)]
        # The later pure-A session must not be re-admitted after the transition.
        sessions += [{"session_index": 2, "cue_sets": ["Cue Set B"], "behavior_record": "generated-transition"},
                     {"session_index": 3, "cue_sets": ["Cue Set A"], "behavior_record": "generated-return"}]
        animals.append({"animal_id": animal, "native_session_count": 4, "sessions": sessions})
    manifest = {"schema_version": 1, "task_id": e.TASK_ID, "source_revision": e.SOURCE_REVISION,
                "input_kind": "prepared_putative_placefields_binF", "evidence_kind": "generated_engineering_control",
                "lineage": {"article_id": 27273552, "article_version": 1,
                            **{k: "generated control; no authentic data" for k in ("placefields_record", "registered_fluorescence_record", "behavior_record", "export_procedure", "rights_review")}},
                "animals": animals}
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, manifest


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path, self.manifest = fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def evaluate_changed(self, change):
        value = copy.deepcopy(self.manifest)
        change(value)
        self.path.write_text(json.dumps(value))
        return e.evaluate_manifest(self.path)

    def test_complete_generated_path_preserves_holds_and_source_session_prefix(self):
        r = e.evaluate_manifest(self.path)
        self.assertIs(r["scientifically_qualified"], False)
        self.assertIs(r["full_contract_complete"], False)
        self.assertIsNone(r["binary_reward"])
        self.assertEqual(r["group"]["independent_unit"], "animal")
        self.assertEqual(r["group"]["n_animals"], 11)
        self.assertEqual(len(r["input_pins"]), 22)
        self.assertTrue(r["preserved_holds"])
        for a in r["animals"]:
            self.assertEqual(a["selected_initial_a_sessions"], [0, 1])
            self.assertEqual(a["valid_day_counts_by_region"], [2] * 6)
        json.dumps(r, allow_nan=False)

    def test_missing_or_duplicate_animal_rejected(self):
        for mutation in (lambda m: m["animals"].pop(), lambda m: m["animals"].__setitem__(0, m["animals"][1])):
            with self.assertRaises(e.ContractError):
                self.evaluate_changed(mutation)

    def test_omitted_ledger_session_and_wrong_index_rejected(self):
        for mutation in (lambda m: m["animals"][0]["sessions"].pop(), lambda m: m["animals"][0]["sessions"][1].update(session_index=4)):
            with self.assertRaises(e.ContractError):
                self.evaluate_changed(mutation)

    def test_single_a_session_cannot_form_learning_curve(self):
        with self.assertRaises(e.ContractError):
            self.evaluate_changed(lambda m: m["animals"][0]["sessions"][1].update(cue_sets=["Cue Set A", "Cue Set B"]))

    def test_wrong_source_policy_and_revision_rejected(self):
        for mutation in (lambda m: m.update(source_revision="main"), lambda m: m["animals"][0]["sessions"][0].update(selection="all_trials")):
            with self.assertRaises(e.ContractError):
                self.evaluate_changed(mutation)

    def test_pin_mismatch_and_path_escape_rejected(self):
        for mutation in (lambda m: m["animals"][0]["sessions"][0].update(sha256="0" * 64), lambda m: m["animals"][0]["sessions"][0].update(arrays="../escape.npz")):
            with self.assertRaises(e.ContractError):
                self.evaluate_changed(mutation)

    def test_malformed_container_rejected_after_valid_pin(self):
        path = self.root / "broken.npz"
        path.write_bytes(b"PK\x03\x04broken")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(e.ContractError):
            self.evaluate_changed(lambda m: m["animals"][0]["sessions"][0].update(arrays=path.name, sha256=digest))

    def test_duplicate_json_keys_and_boolean_versions_rejected(self):
        self.path.write_text('{"task_id":"wrong","task_id":"PAPER-FIND-REP-001"}')
        with self.assertRaisesRegex(e.ContractError, "duplicate JSON key"):
            e.evaluate_manifest(self.path)
        for mutation in (lambda m: m.update(schema_version=True), lambda m: m["lineage"].update(article_version=True)):
            with self.assertRaises(e.ContractError):
                self.evaluate_changed(mutation)

    def test_object_array_and_registered_cell_reordering_rejected(self):
        for ids in (np.array([object()] * 5, dtype=object), np.arange(5)[::-1]):
            path = self.root / "bad.npz"
            near = np.tile(np.arange(5.0)[:, None], (1, 46))
            np.savez(path, near_binF=near, far_binF=near, cell_ids=ids)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(e.ContractError):
                self.evaluate_changed(lambda m: m["animals"][0]["sessions"][1].update(arrays=path.name, sha256=digest))

    def test_constant_cells_are_reported_undefined_without_dropping_animal(self):
        path = self.root / "constant.npz"
        np.savez(path, near_binF=np.ones((5, 46)), far_binF=np.ones((5, 46)), cell_ids=np.arange(5))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        def change(m):
            for s in m["animals"][0]["sessions"][:2]:
                s.update(arrays=path.name, sha256=digest)
        r = self.evaluate_changed(change)
        self.assertEqual(r["animals"][0]["valid_day_counts_by_region"], [0] * 6)
        self.assertTrue(all(v is None for v in r["group"]["mean"][0]))
        self.assertEqual(r["group"]["n_animals"], 11)
        self.assertEqual(r["animals"][0]["days"][0]["undefined_correlations"], 46 * 46)

    def test_cli_writes_strict_report_and_refuses_overwrite(self):
        output = self.root / "report.json"
        command = [sys.executable, str(Path(e.__file__)), str(self.path), str(output)]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        before = output.read_bytes()
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(second.returncode, 2)
        self.assertEqual(output.read_bytes(), before)
        same_path = subprocess.run(command[:-1] + [str(self.path)], capture_output=True, text=True)
        self.assertEqual(same_path.returncode, 2)
        self.assertEqual(json.loads(before)["evidence_kind"], "generated_engineering_control")


if __name__ == "__main__":
    unittest.main()
