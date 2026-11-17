"""Generated branch/counterexample controls; never authentic benchmark outcomes."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("source_score", Path(__file__).resolve().parents[1] / "source_score.py")
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)


def fixture():
    vocabulary = ["yes", "no", "ride", "on", "_is", "novel"]
    train = s.BUILTINS + ["cat", "dog", "hold", "on"]
    # id, answer, native parser's query concept names, monitor execution, posthoc
    specs = [
        ("q0", "yes", ["cat"], {"kind": "bool", "value": 1}, "yes"),
        ("q1", "no", ["cat"], {"kind": "vocab", "value": [0, 0, 1, 0, 0, 0]}, "ride"),
        ("q2", "ride", ["unseen"], "skip", "skip"),
        ("q3", "no", [], {"kind": "bool", "value": -1}, "skip"),
        ("q4", "ride", ["cat", "dog", "hold", "on"], {"kind": "vocab", "value": [0, 0, 1, 0, 0, 0]}, "ride"),
        ("q5", "on", ["cat"], None, None),
        ("q6", "ride", ["cat"], {"kind": "vocab", "value": [0, 0, 0, 1, 0, 0]}, "on"),
        ("q7", "_is", ["cat"], {"kind": "bool", "value": 1}, "_is"),
        ("q8", "novel", ["cat"], {"kind": "vocab", "value": [0, 0, 0, 0, 0, 1]}, "novel"),
        ("q9", "yes", ["cat", "dog", "hold", "on"], {"kind": "bool", "value": 1}, "skip"),
        ("q10", "no", ["cat"], None, None),
    ]
    queries, monitor, posthoc = [], [], []
    for qid, answer, concepts, execution, predicted in specs:
        queries.append({"id": qid, "answer": answer, "query_sha256": s.digest(qid),
                        "domain_functions": s.BUILTINS + concepts})
        monitor.append({"id": qid, "outcome": "not_called" if execution == "skip" else "returned",
                        "execution": None if execution == "skip" else execution})
        posthoc.append({"id": qid, "outcome": "not_called" if predicted == "skip" else
                        "raised" if predicted is None else "returned",
                        "pred_answer": None if predicted == "skip" else predicted})
    manifest = {"schema": s.SCHEMA, "engineering_fixture": True,
                "source_code_revision": s.legacy.CODE_REVISION,
                "data_revision": s.legacy.DATA_REVISION, "training_manifest_sha256": "a" * 64,
                "train_domain_functions": train,
                "records": [{"path": "CSI1/test/4804.npy", "source_sha256": "b" * 64,
                             "queries": queries[:1]},
                            {"path": "CSI1/test/4805.npy", "source_sha256": "c" * 64,
                             "queries": queries[1:]}]}
    run = {"manifest_sha256": s.digest(manifest), "train_hop": "all",
           "checkpoint_sha256": "d" * 64, "selection_policy": "source_best_test_accuracy",
           "access_condition": "paper_data_author_code", "neural_condition": "neural",
           "vocabulary_sha256": s.digest(vocabulary), "training_monitor": monitor, "posthoc": posthoc}
    return manifest, run, vocabulary


class SourceScoreTests(unittest.TestCase):
    def test_distinct_denominators_and_original_categories(self):
        report = s.score(*fixture())
        self.assertEqual((report["training_monitor"]["correct"], report["training_monitor"]["queries"]), (5, 10))
        self.assertEqual((report["posthoc"]["Overall"]["correct"], report["posthoc"]["Overall"]["queries"]), (5, 6))
        self.assertEqual(report["posthoc"]["Action"]["accuracy"], 1 / 2)
        self.assertEqual(report["posthoc"]["T/F"]["accuracy"], 1)
        self.assertIsNone(report["posthoc"]["Position"]["accuracy"])
        self.assertEqual(report["posthoc"]["Thing"]["queries"], 1)
        self.assertEqual(report["posthoc"]["unknown"]["queries"], 1)
        self.assertEqual(report["posthoc"]["Vocabulary"]["queries"], 4)
        self.assertFalse(report["table1_parity_authenticated"])
        # One image has one question, the other has ten; no image-macro substitution.
        self.assertEqual(report["training_monitor"]["accuracy"], 0.5)

    def test_source_non_yes_coercion_and_hop_asymmetry_are_visible(self):
        rows = {r["id"]: r for r in s.score(*fixture())["ledger"]}
        self.assertEqual((rows["q1"]["training_correct"], rows["q1"]["posthoc_correct"]), (0, 1))
        self.assertEqual(rows["q3"]["posthoc_reason"], "tf_hop_outside_1_3")
        self.assertEqual(rows["q9"]["posthoc_reason"], "tf_hop_outside_1_3")
        self.assertEqual(rows["q4"]["posthoc_reason"], "included")
        self.assertEqual(rows["q2"]["posthoc_reason"], "unseen_concept")
        self.assertEqual(rows["q5"]["posthoc_reason"], "caught_exception")

    def test_denominator_change_cannot_create_comparable_improvement(self):
        manifest, reference, vocabulary = fixture()
        candidate = deepcopy(reference)
        candidate["posthoc"][6].update(outcome="raised", pred_answer=None)
        result = s.compare(manifest, reference, candidate, vocabulary)
        metric = result["posthoc_comparison"]["Overall"]
        self.assertEqual(result["candidate"]["posthoc"]["Overall"]["accuracy"], 1)
        self.assertFalse(metric["same_included_queries"])
        self.assertIsNone(metric["candidate_minus_reference"])
        self.assertEqual(metric["reference_only_ids"], ["q6"])

    def test_reproduction_distance_separate_from_same_query_delta(self):
        manifest, reference, vocabulary = fixture()
        candidate = deepcopy(reference)
        candidate["posthoc"][6]["pred_answer"] = "ride"
        candidate["access_condition"] = "paper_data"
        candidate["selection_policy"] = "train_validation_only"
        result = s.compare(manifest, reference, candidate, vocabulary)
        self.assertAlmostEqual(result["posthoc_comparison"]["Overall"]["candidate_minus_reference"], 1 / 6)
        self.assertAlmostEqual(result["posthoc_comparison"]["Overall"]["reference_minus_published"], 5 / 6 - 0.7041)
        self.assertFalse(result["reproduction_established"])
        self.assertFalse(result["improvement_established"])

    def test_source_abort_is_not_a_completed_monitor(self):
        manifest, run, vocabulary = fixture()
        run["training_monitor"][0].update(outcome="raised", execution=None)
        for row in run["training_monitor"][1:]:
            row.update(outcome="not_called", execution=None)
        result = s.score(manifest, run, vocabulary)
        self.assertFalse(result["training_monitor"]["completed"])
        self.assertIsNone(result["training_monitor"]["accuracy"])
        run["training_monitor"][1].update(outcome="returned", execution=None)
        with self.assertRaises(s.ContractError):
            s.score(manifest, run, vocabulary)

    def test_complete_identity_and_skip_accounting(self):
        for mutation in ("missing", "duplicate", "eligible_not_called", "unseen_called"):
            manifest, run, vocabulary = fixture()
            if mutation == "missing":
                run["posthoc"].pop()
            elif mutation == "duplicate":
                run["posthoc"].append(run["posthoc"][0])
            elif mutation == "eligible_not_called":
                run["posthoc"][0].update(outcome="not_called", pred_answer=None)
            else:
                run["posthoc"][2].update(outcome="returned", pred_answer="ride")
            with self.subTest(mutation=mutation), self.assertRaises(s.ContractError):
                s.score(manifest, run, vocabulary)

    def test_manifest_hash_production_population_and_parser_order(self):
        for mutation in ("hash", "production", "ordered_builtins", "repeated_path"):
            manifest, run, vocabulary = fixture()
            if mutation == "hash":
                manifest["records"][0]["queries"][0]["answer"] = "no"
            elif mutation == "production":
                manifest["engineering_fixture"] = False
                run["manifest_sha256"] = s.digest(manifest)
            elif mutation == "ordered_builtins":
                manifest["train_domain_functions"][0:2] = ["greater_than", "equal"]
            else:
                manifest["records"].append(deepcopy(manifest["records"][0]))
            with self.subTest(mutation=mutation), self.assertRaises(s.ContractError):
                s.score(manifest, run, vocabulary)

    def test_unknown_vocab_predictions_still_count_as_errors(self):
        manifest, run, vocabulary = fixture()
        run["posthoc"][4]["pred_answer"] = "outside_observed_answers"
        result = s.score(manifest, run, vocabulary)
        self.assertEqual(result["posthoc"]["Action"]["queries"], 2)
        self.assertEqual(result["posthoc"]["Action"]["accuracy"], 0)

    def test_source_vocab_loss_requires_target_in_vocab(self):
        manifest, run, vocabulary = fixture()
        manifest["records"][1]["queries"][0]["answer"] = "not_in_vocab"
        run["manifest_sha256"] = s.digest(manifest)
        with self.assertRaises(s.ContractError):
            s.score(manifest, run, vocabulary)

    def test_json_duplicate_keys_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            path.write_text('{"records":[],"records":[]}')
            with self.assertRaises(s.ContractError):
                s.legacy._load(str(path))


if __name__ == "__main__":
    unittest.main()
