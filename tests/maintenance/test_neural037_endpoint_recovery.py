"""Regression checks for N037 source recovery and exact authority projection.

Metadata only: no original arrays, private targets, provider or scientific score.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / "benchmarks/neural/NEURAL-037"

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

NU = load_module("n037_neural_understanding", ROOT / "src/neurobench/neural_understanding.py")

class EndpointRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_body = (HOME / "understanding.v1.json").read_bytes()
        cls.contract = json.loads(cls.contract_body)
        cls.original_body = (HOME / "historical/task.pre-understanding.v1.json").read_bytes()
        cls.original = json.loads(cls.original_body)
        cls.binding = NU._binding(cls.contract_body, cls.original_body)

    def project(self, contract):
        return NU._current(self.original, contract, self.binding, "NEURAL-037")

    def test_current_recovery_is_source_bound_and_schema_valid(self):
        self.assertEqual(NU.validate_contract(self.contract, "NEURAL-037"), [])
        self.assertEqual(NU._source_errors(ROOT, self.contract), [])
        self.assertEqual(json.loads((HOME / "task.json").read_bytes()), self.project(self.contract))

    def test_original_complete_geometry_and_cross_acquisition_training(self):
        panel = json.loads((HOME / "implementations/condition-viewer-v1/source/PANEL.json").read_bytes())
        declaration = json.loads((HOME / "implementations/registered-runtime/manifest.json").read_bytes())["scope"]
        contexts = panel["contexts"]
        self.assertEqual(len(contexts), declaration["contexts"])
        self.assertEqual(sum(len(x["cell_keys"]) for x in contexts), declaration["query_roi_occurrences"])
        endpoint = HOME / "implementations/condition-endpoint-v1"
        old_io = sys.modules.get("delivery_io")
        try:
            sys.modules["delivery_io"] = load_module("n037_delivery_io", endpoint / "delivery_io.py")
            core = load_module("n037_preparation_core", endpoint / "preparation_core.py")
            pool = [{"acquisition": x["acquisition"], "order": x["query_order"]} for x in contexts]
            for query in pool:
                selected = core.select_training(pool, query["acquisition"], query["order"])
                self.assertEqual(len(selected), declaration["training_conditions_per_context"])
                self.assertEqual(len({row["acquisition"] for row in selected}), declaration["acquisitions"])
                self.assertEqual(sum(row["acquisition"] == query["acquisition"] for row in selected), 1)
                self.assertNotIn(query, selected)
        finally:
            if old_io is None:
                sys.modules.pop("delivery_io", None)
            else:
                sys.modules["delivery_io"] = old_io

    def test_recovery_replaces_obsolete_implementation_hold_only(self):
        current = self.project(self.contract)
        before = {row["id"]: row for row in self.original["holds"]}
        after = {row["id"]: row for row in current["holds"]}
        self.assertEqual(set(before), set(after))
        self.assertNotEqual(before["scorer"], after["scorer"])
        for key in before.keys() - {"scorer"}:
            self.assertEqual(before[key], after[key])
        self.assertEqual(current["next_implementation_action"], self.contract["implementation"]["missing"])

    def test_projection_requires_exact_task_source_kind_path_and_hash(self):
        for key, replacement in (("id", "unrelated"), ("kind", "local_review"),
                                 ("path", "benchmarks/neural/NEURAL-037/other.json"),
                                 ("sha256", "0" * 64)):
            with self.subTest(key=key):
                altered = copy.deepcopy(self.contract)
                row = next(row for row in altered["evidence"] if row["id"] == "condition-endpoint-recovery")
                row[key] = replacement
                result = self.project(altered)
                self.assertEqual(result["holds"], self.original["holds"])
                self.assertEqual(result["next_implementation_action"], self.original["next_implementation_action"])
        altered = copy.deepcopy(self.contract); altered["task_id"] = "NEURAL-038"
        self.assertEqual(self.project(altered)["holds"], self.original["holds"])

    def test_wrong_source_digest_cannot_authenticate_recovery(self):
        altered = copy.deepcopy(self.contract)
        row = next(row for row in altered["evidence"] if row["id"] == "condition-scorer")
        row["sha256"] = "0" * 64
        self.assertTrue(any(row["path"] in message for message in NU._source_errors(ROOT, altered)))

    def test_source_availability_does_not_grant_scientific_or_native_admission(self):
        current = self.project(self.contract)
        self.assertEqual(self.contract["disposition"], "partial_delivery")
        for key in ("runnable", "research_qualified", "submission_ready"):
            self.assertIs(current["admission"][key], False)
        self.assertEqual(current["access_conditions"]["direct_observation"]["status"], "not_delivered")
        self.assertEqual(current["access_conditions"]["tool_assisted"]["status"], "not_delivered")
        self.assertEqual(current["access_conditions"]["typed_viewer"]["status"], "source_available")
        self.assertEqual(self.contract["empirical_claims"]["new_model_trials"], 0)
        self.assertEqual(self.contract["empirical_claims"]["new_human_results"], 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
