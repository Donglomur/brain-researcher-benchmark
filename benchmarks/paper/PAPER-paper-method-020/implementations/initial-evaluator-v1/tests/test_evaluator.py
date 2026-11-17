"""Generated engineering controls; no authentic fMRI or model results."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import evaluator as e


def fixture():
    paths = ("S1/train/0.npy", "S1/test/1.npy", "S1/test/2.npy",
             "S2/train/0.npy", "S2/test/1.npy", "S2/test/2.npy")
    inventory = e.Inventory(paths, "generated-only", engineering_fixture=True)
    identities, records = [], []
    for i, path in enumerate(paths):
        subject = path.split("/")[0]
        image = f"image-{i}"
        identities.append({"path": path, "subject": subject, "person_id": subject,
                           "image_id": image, "image_sha256": hashlib.sha256(image.encode()).hexdigest(),
                           "identity_evidence": "generated engineering identity"})
        records.append({"path": path, "queries": [f"exists({image})", "relation(x,y)"],
                        "answers": ["yes", "no"], "brain_region": [[float(i + 1)] * 1024 for _ in range(5)],
                        "image": "PRIVATE PIXELS", "scene_graph": "PRIVATE GRAPH",
                        "caption": "PRIVATE ANSWER", "config": {"label": "PRIVATE"}})
    return inventory, identities, records


def prepared():
    return e.prepare_assessment(*fixture(), shuffle_seed="frozen-seed", id_salt="opaque-identifiers-012345")


def provenance(vocabulary):
    return {"model_sha256": "1" * 64, "language_model_sha256": "2" * 64,
            "prompt_sha256": "3" * 64, "domain_sha256": "4" * 64,
            "vocabulary_sha256": e._digest(vocabulary), "runtime_sha256": "5" * 64,
            "decoding_config_sha256": "6" * 64, "training_partition_sha256": "7" * 64,
            "non_neural_resources_sha256": "8" * 64,
            "selection_policy": "train_validation_only", "domain_policy": "train_only",
            "inference_seed": "fixed-42"}


def execution(answer, vocabulary):
    if answer in ("yes", "no"):
        return {"kind": "bool", "value": 1.0 if answer == "yes" else 0.0}
    return {"kind": "vocab", "value": [float(word == answer) for word in vocabulary]}


def perfect_runs(protected, vocabulary):
    return {condition: {"assessment_sha256": protected["assessment_sha256"],
                        "input_packet_sha256": protected["arm_packet_sha256"][condition],
                        "provenance": provenance(vocabulary),
                        "predictions": [{"id": t["id"], "execution": execution(t["answer"], vocabulary)}
                                        for t in protected["targets"]]}
            for condition in e.CONDITIONS}


class InventoryAndIdentityTests(unittest.TestCase):
    def test_full_canonical_population_and_production_subset_rejection(self):
        inventory = e.load_inventory(PACKAGE.parents[1] / "historical/task.pre-improvement.v1.json")
        self.assertEqual(e.inventory_summary(inventory)["counts"], {"CSI1/train": 4802, "CSI1/test": 84})
        self.assertEqual(len(inventory.paths), 4886)
        with self.assertRaises(e.ContractError):
            e.Inventory(("CSI1/test/4804.npy",), e.CONTRACT_SHA256)

    def test_label_blind_audit_keeps_person_overlap_visible(self):
        inventory, identities, _ = fixture()
        result = e.audit_identities(inventory, identities)
        self.assertTrue(result["image_disjoint_as_declared"])
        self.assertFalse(result["person_disjoint_as_declared"])
        self.assertFalse(result["identity_evidence_independently_verified"])
        self.assertEqual(result["cross_split_person_ids"], ["S1", "S2"])

    def test_duplicate_missing_and_subject_mismatch_rejected(self):
        inventory, identities, _ = fixture()
        for rows in (identities[:-1], identities + identities[:1]):
            with self.assertRaises(e.ContractError):
                e.audit_identities(inventory, rows)
        identities[0]["subject"] = "WRONG"
        with self.assertRaises(e.ContractError):
            e.audit_identities(inventory, identities)

    def test_hash_alias_cross_person_overlap_and_transitive_groups(self):
        inventory, identities, records = fixture()
        identities[4]["image_sha256"] = identities[0]["image_sha256"]
        report = e.audit_identities(inventory, identities)
        self.assertFalse(report["image_disjoint_as_declared"])
        with self.assertRaises(e.ContractError):
            e.prepare_assessment(inventory, identities, records, shuffle_seed="seed", id_salt="salt-012345678901")
        rows = {"a": {"image_id": "A", "image_sha256": "x"},
                "b": {"image_id": "B", "image_sha256": "x"},
                "c": {"image_id": "B", "image_sha256": "y"}}
        self.assertEqual(len(set(e._image_groups(rows).values())), 1)


class PreparationTests(unittest.TestCase):
    def test_public_allowlist_and_arm_isolation(self):
        bundle, protected = prepared()
        packet = e.arm_packet(bundle, "no_neural")
        self.assertEqual(set(packet), {"task_id", "protocol", "condition", "engineering_fixture", "training", "evaluation"})
        self.assertNotIn("conditions", packet)
        self.assertEqual(len(packet["training"]), 2)
        self.assertEqual(len(packet["evaluation"]), 4)
        self.assertEqual(len(protected["targets"]), 8)
        for row in packet["evaluation"]:
            self.assertEqual(set(row), {"id", "question_ids", "queries", "brain_region"})
            self.assertTrue(all(value == 0 for time in row["brain_region"] for value in time))
        serialized = json.dumps(packet)
        for forbidden in ("PRIVATE", "scene_graph", "caption", "person_id", "image_sha256"):
            self.assertNotIn(forbidden, serialized)
        self.assertNotIn("answers", json.dumps(packet["evaluation"]))
        self.assertIn("answers", packet["training"][0])
        self.assertEqual(protected["arm_packet_sha256"]["no_neural"], e._digest(packet))

    def test_same_queries_and_within_subject_bijective_donors(self):
        bundle, protected = prepared()
        donors = protected["donor_bindings"]
        self.assertEqual(set(donors), set(donors.values()))
        for target, donor in donors.items():
            self.assertNotEqual(target, donor)
            self.assertEqual(target.split("/")[:2], donor.split("/")[:2])
        for neural, zero, shuffled in zip(*(bundle["conditions"][c] for c in e.CONDITIONS)):
            self.assertEqual(neural["queries"], zero["queries"])
            self.assertEqual(neural["queries"], shuffled["queries"])
            self.assertEqual(neural["question_ids"], shuffled["question_ids"])
            self.assertNotEqual(neural["brain_region"], shuffled["brain_region"])
        self.assertEqual(prepared(), (bundle, protected))

    def test_shuffle_label_blind_and_input_order_independent(self):
        inventory, identities, records = fixture()
        one = e.prepare_assessment(inventory, identities, records, shuffle_seed="fixed", id_salt="salt-012345678901")[1]
        for row in records:
            row["answers"] = ["no", "yes"]
        two = e.prepare_assessment(inventory, list(reversed(identities)), list(reversed(records)),
                                   shuffle_seed="fixed", id_salt="salt-012345678901")[1]
        self.assertEqual(one["donor_bindings"], two["donor_bindings"])

    def test_singleton_and_impossible_image_groups_rejected(self):
        _, identities, _ = fixture()
        indexed = {row["path"]: row for row in identities}
        with self.assertRaises(e.ContractError):
            e._donors(["S1/test/1.npy"], indexed, "seed")
        indexed["S1/test/2.npy"]["image_id"] = indexed["S1/test/1.npy"]["image_id"]
        with self.assertRaises(e.ContractError):
            e._donors(["S1/test/1.npy", "S1/test/2.npy"], indexed, "seed")

    def test_repeated_image_groups_keep_one_donor_image(self):
        rows = {}
        for i, image in enumerate(("A", "A", "B", "B")):
            rows[f"S/test/{i}.npy"] = {"image_id": image, "image_sha256": image * 64}
        result = e._donors(list(rows), rows, "seed")
        self.assertEqual(set(result), set(result.values()))
        for path, donor in result.items():
            self.assertNotEqual(rows[path]["image_id"], rows[donor]["image_id"])
        self.assertEqual({rows[result[p]]["image_id"] for p in list(rows)[:2]}, {"B"})

    def test_missing_query_answers_nonfinite_shape_and_bool_numeric_rejected(self):
        _, _, records = fixture()
        for mutation in (lambda x: x.update(queries=[]), lambda x: x.update(answers=[]),
                         lambda x: x.update(brain_region=[[1]]),
                         lambda x: x["brain_region"][0].__setitem__(0, float("nan")),
                         lambda x: x["brain_region"][0].__setitem__(0, True)):
            bad = deepcopy(records[0]); mutation(bad)
            with self.assertRaises(e.ContractError):
                e.project_record(bad, supervised=True)


class ScoringTests(unittest.TestCase):
    def test_independent_rational_reference_and_aggregation(self):
        reference = json.loads((PACKAGE / "tests" / "independent_reference_fixture.json").read_text())
        vocabulary = ["hold", "ride", "on", "under"]
        protected = {"task_id": e.TASK_ID, "protocol": e.PROTOCOL, "engineering_fixture": True,
                     "targets": [], "arm_packet_sha256": {c: e._digest(c) for c in e.CONDITIONS},
                     "preserved_holds": list(e.HOLDS)}
        for row in reference["rows"]:
            protected["targets"].append({"id": row["question_id"], "person_id": row["subject_id"],
                                          "image_id": row["image_id"], "image_group": row["image_id"],
                                          "answer": row["answer"]})
        protected["assessment_sha256"] = e._digest(protected)
        runs = perfect_runs(protected, vocabulary)
        for condition in e.CONDITIONS:
            runs[condition]["predictions"] = [{"id": row["question_id"], "execution": execution(row[condition], vocabulary)}
                                                for row in reference["rows"]]
        result = e.score_assessment(protected, runs, vocabulary)
        for condition in e.CONDITIONS:
            actual, expected = result["conditions"][condition], reference["expected"][condition]
            self.assertEqual(actual["correct"], expected["correct"])
            for key, ref in (("qa_accuracy", "qa_micro_accuracy"), ("image_macro_accuracy", "image_macro_accuracy"),
                             ("person_macro_accuracy", "subject_macro_accuracy")):
                self.assertAlmostEqual(actual[key], expected[ref]["value"])
        shuffled = result["neural_minus_control"]["shuffled_neural"]
        self.assertAlmostEqual(shuffled["query_paired_accuracy_difference"], 1 / 6)
        self.assertAlmostEqual(shuffled["image_macro_paired_difference"], 1 / 18)
        self.assertEqual(shuffled["person_macro_paired_difference"], 0)
        self.assertFalse(result["scientifically_qualified"])

    def test_source_decoding_boundaries_and_exact_strings(self):
        self.assertEqual(e.decode_execution({"kind": "bool", "value": 0}, ["x"]), "no")
        self.assertEqual(e.decode_execution({"kind": "bool", "value": 1e-50}, ["x"]), "yes")
        self.assertEqual(e.decode_execution({"kind": "int64", "value": 2.5}, ["x"]), "2")
        self.assertEqual(e.decode_execution({"kind": "int64", "value": 3.5}, ["x"]), "4")
        self.assertEqual(e.decode_execution({"kind": "vocab", "value": [1, 1]}, ["a", "b"]), "a")
        self.assertEqual(e._correct({"kind": "bool", "value": 1}, "Yes", ["yes"]), (0, 1))
        self.assertEqual(e._correct({"kind": "int64", "value": 1}, True, ["yes"]), (0, 1))
        self.assertEqual(e._correct({"kind": "Object", "value": 0}, "yes", ["yes"]), (0, 1))
        for value in (True, float("nan"), float("inf")):
            with self.assertRaises(e.ContractError):
                e.decode_execution({"kind": "bool", "value": value}, ["x"])

    def test_explicit_failures_remain_in_denominator(self):
        _, protected = prepared(); vocabulary = ["hold"]
        runs = perfect_runs(protected, vocabulary)
        runs["neural"]["predictions"][0]["execution"] = None
        result = e.score_assessment(protected, runs, vocabulary)
        self.assertEqual(result["conditions"]["neural"]["queries"], 8)
        self.assertEqual(result["conditions"]["neural"]["qa_accuracy"], 7 / 8)
        self.assertEqual(result["conditions"]["neural"]["execution_success_rate"], 7 / 8)
        self.assertEqual(result["neural_minus_control"]["no_neural"]["query_paired_accuracy_difference"], -1 / 8)

    def test_complete_conditions_ids_packet_and_provenance_enforced(self):
        _, protected = prepared(); vocabulary = ["hold"]
        good = perfect_runs(protected, vocabulary)
        mutations = [lambda x: x.pop("no_neural"),
                     lambda x: x["neural"]["predictions"].pop(),
                     lambda x: x["neural"]["predictions"].append(x["neural"]["predictions"][0]),
                     lambda x: x["neural"]["predictions"][0].update(id="unknown"),
                     lambda x: x["neural"]["provenance"].update(prompt_sha256="9" * 64),
                     lambda x: x["neural"].update(input_packet_sha256="9" * 64),
                     lambda x: x["neural"]["provenance"].update(selection_policy="best_test"),
                     lambda x: x["neural"]["provenance"].update(domain_policy="train_plus_test")]
        for mutation in mutations:
            bad = deepcopy(good); mutation(bad)
            with self.assertRaises(e.ContractError):
                e.score_assessment(protected, bad, vocabulary)
        bad = deepcopy(protected); bad["targets"][0]["answer"] = "tampered"
        with self.assertRaises(e.ContractError):
            e.score_assessment(bad, good, vocabulary)

    def test_generated_assessment_cannot_be_promoted_to_production_by_flag(self):
        _, protected = prepared(); vocabulary = ["hold"]
        for flag in (False, "false", 0):
            bad = deepcopy(protected)
            bad["engineering_fixture"] = flag
            del bad["assessment_sha256"]
            bad["assessment_sha256"] = e._digest(bad)
            with self.assertRaises(e.ContractError):
                e.score_assessment(bad, perfect_runs(bad, vocabulary), vocabulary)

    def test_production_binding_full_path_and_query_index_controls(self):
        # Metadata-only engineering control of the production binder, not data.
        inventory = e.load_inventory(PACKAGE.parents[1] / "historical/task.pre-improvement.v1.json")
        audit = {**e.inventory_summary(inventory), "image_disjoint_as_declared": True}
        assessment = {"engineering_fixture": False, "contract_sha256": e.CONTRACT_SHA256,
                      "audit": audit,
                      "source_records": [{"path": p, "query_count": 1} for p in inventory.paths]}
        targets = {p: {"path": p, "query_index": 0} for p in inventory.paths if "/test/" in p}
        e._production_binding(assessment, targets)
        with self.assertRaises(e.ContractError):
            e._production_binding(assessment, dict(list(targets.items())[:-1]))
        bad = deepcopy(assessment); bad["source_records"][0]["query_count"] = 2
        with self.assertRaises(e.ContractError):
            e._production_binding(bad, targets)
        bad = deepcopy(assessment); bad["source_records"].pop()
        with self.assertRaises(e.ContractError):
            e._production_binding(bad, targets)


if __name__ == "__main__":
    unittest.main()
