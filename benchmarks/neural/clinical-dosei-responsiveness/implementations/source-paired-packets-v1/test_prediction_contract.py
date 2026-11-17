"""Generated transport-admission controls; no source labels or model results."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("contract", Path(__file__).with_name("prediction_contract.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def fixture():
    manifest = [{"case_id": f"{i:064x}", "observation_sha256": f"{i+10:064x}"} for i in range(3)]
    pair = {arm: {"schema": "dosei_paired_workflow_predictions_v1", "arm": arm,
                  "cases": [{**row, "status": "ok", "probabilities": [0, 0.2, 0.3, 0.4, 0.1]}
                            for row in manifest]} for arm in m.ARMS}
    return manifest, pair


class Predictions(unittest.TestCase):
    def test_two_workflows_full_coverage_and_explicit_abstention(self):
        manifest, pair = fixture()
        pair["viewer_only"]["cases"][1].update(status="abstain", probabilities=None)
        pair["code_enabled"]["cases"].reverse()
        result = m.admit_pair(manifest, pair)
        self.assertEqual([x["case_id"] for x in result["code_enabled"]], [x["case_id"] for x in manifest])
        self.assertEqual(result["viewer_only"][1]["status"], "abstain")
        self.assertIsNone(result["viewer_only"][1]["probabilities"])
        pair["code_enabled"]["cases"][0]["probabilities"][0] = 1
        self.assertEqual(result["code_enabled"][2]["probabilities"][0], 0)

    def test_missing_duplicate_extra_and_rebound_cases_refuse(self):
        for mutation in ("missing", "duplicate", "extra", "unknown", "rebound"):
            manifest, pair = fixture(); cases = pair["viewer_only"]["cases"]
            if mutation == "missing": cases.pop()
            if mutation == "duplicate": cases[1] = copy.deepcopy(cases[0])
            if mutation == "extra": cases.append(copy.deepcopy(cases[0]))
            if mutation == "unknown": cases[0]["case_id"] = "f" * 64
            if mutation == "rebound": cases[0]["observation_sha256"] = "f" * 64
            with self.assertRaises(m.PredictionRefusal): m.admit_pair(manifest, pair)

    def test_invalid_probabilities_never_normalized_or_filtered(self):
        for probabilities in ([True, 0, 0, 0, 0], [float("nan"), 0, 0, 0, 0],
                              [float("inf"), 0, 0, 0, 0], [0.3] * 5,
                              [-0.1, 1.1, 0, 0, 0], [1, 0], None, ["1", 0, 0, 0, 0],
                              [10 ** 1000, 0, 0, 0, 0]):
            manifest, pair = fixture()
            pair["code_enabled"]["cases"][0]["probabilities"] = probabilities
            with self.assertRaises(m.PredictionRefusal): m.admit_pair(manifest, pair)

    def test_private_fields_wrong_arm_and_bad_abstention_refuse(self):
        for mutation in ("label", "recording", "arm", "abstention", "status"):
            manifest, pair = fixture(); row = pair["viewer_only"]["cases"][0]
            if mutation == "label": row["moaas_grouped_ordinal"] = 3
            if mutation == "recording": manifest[0]["recording_id"] = "41"
            if mutation == "arm": pair["viewer_only"]["arm"] = "code_enabled"
            if mutation == "abstention": row["status"] = "abstain"
            if mutation == "status": row["status"] = "drop_failed_case"
            with self.assertRaises(m.PredictionRefusal): m.admit_pair(manifest, pair)

    def test_manifest_integrity_and_two_arm_requirements(self):
        for mutation in ("duplicate", "bad_hash", "empty", "one_arm"):
            manifest, pair = fixture()
            if mutation == "duplicate": manifest[1] = copy.deepcopy(manifest[0])
            if mutation == "bad_hash": manifest[0]["case_id"] = "x" * 64
            if mutation == "empty": manifest = []
            if mutation == "one_arm": del pair["viewer_only"]
            with self.assertRaises(m.PredictionRefusal): m.admit_pair(manifest, pair)


if __name__ == "__main__": unittest.main()
