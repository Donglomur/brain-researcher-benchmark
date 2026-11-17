"""Generated software controls. No observations or paper results are used."""
import copy
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("treebank_curves", Path(__file__).with_name("evaluate.py"))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def fixture():
    reference = {"schema": "treebank-decoding-reference/v1", "task_id": module.TASK_ID,
        "access_condition": "paper_and_data",
        "scope": "generated_control", "window_ids": ["invented_before", "invented_after"],
        "regions": ["invented_region"], "subjects": [], "source_manifest_sha256": "0" * 64}
    prediction = {"schema": "treebank-decoding-scores/v1", "task_id": module.TASK_ID,
                  "access_condition": "paper_and_data", "subjects": []}
    # Ten ordinary contacts plus a poorer CV contact with perfect held-out AUC.
    # Subject 5 has perfect CV scores but must only remain in the electrode map.
    for sid, count in [(1, 11), (5, 1)]:
        rows = [{"id": f"train_{fold}_{y}", "label": y, "fold": fold}
                for fold in range(5) for y in (0, 1)]
        rows += [{"id": f"test_{y}", "label": y, "fold": None} for y in (0, 1)]
        reference["subjects"].append({"id": sid,
            "examples": {task: copy.deepcopy(rows) for task in module.DECODING_TASKS},
            "electrodes": [{"id": f"e{i}", "regions": ["invented_region"]} for i in range(count)],
            "corrupted_electrodes": []})
        electrodes = []
        for index in range(count):
            tasks = {}
            for task in module.DECODING_TASKS:
                scores = {"train_cv": [], "test": []}
                for row in rows:
                    y = row["label"]
                    if row["fold"] is None:
                        values = [float(y if index == 10 else 1-y), 0.0]
                        split = "test"
                    else:
                        values = [float(1-y if index == 10 else y), float(y)]
                        # The bad contact must be poor at every window for exclusion.
                        if index == 10:
                            values[1] = float(1-y)
                        split = "train_cv"
                    scores[split].append({"id": row["id"], "scores": values})
                tasks[task] = scores
            electrodes.append({"id": f"e{index}", "tasks": tasks})
        prediction["subjects"].append({"id": sid, "electrodes": electrodes})
    return reference, prediction


class AUCTests(unittest.TestCase):
    def test_against_pairwise_definition(self):
        rng = random.Random(117)
        for count in range(2, 34):
            labels = [0, 1] + [rng.randrange(2) for _ in range(count - 2)]
            scores = [rng.randrange(-3, 4) for _ in labels]
            pos = [s for y, s in zip(labels, scores) if y]
            neg = [s for y, s in zip(labels, scores) if not y]
            expected = sum((a > b) + .5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))
            self.assertAlmostEqual(module.auc(labels, scores), expected)

    def test_chance_inversion_nonfinite_and_one_class(self):
        self.assertEqual(module.auc([0, 1], [3, 3]), .5)
        self.assertEqual(module.auc([0, 1], [1, 0]), 0)
        for labels, scores in [([0, 0], [0, 1]), ([0, 1], [0, float("nan")]),
                               ([False, True], [0, 1]), ([0, 1], [0, True])]:
            with self.assertRaises(ValueError):
                module.auc(labels, scores)


class PanelTests(unittest.TestCase):
    def test_overlapping_lobe_and_anatomical_groups_preserve_contact_unit(self):
        reference, prediction = fixture()
        reference["regions"].append("invented_lobe")
        for subject in reference["subjects"]:
            for electrode in subject["electrodes"]:
                electrode["regions"].append("invented_lobe")
        result = module.evaluate(reference, prediction)
        self.assertEqual(len(result["electrodes"]["sentence_onset"]), 12)
        groups = result["regional_top_ten"]["sentence_onset"]
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["selected_contacts"], groups[1]["selected_contacts"])

    def test_paired_access_conditions_are_separate(self):
        reference, prediction = fixture()
        prediction["access_condition"] = "paper_data_and_author_code"
        with self.assertRaisesRegex(ValueError, "condition differs"):
            module.evaluate(reference, prediction)
        reference["access_condition"] = "paper_data_and_author_code"
        self.assertEqual(module.evaluate(reference, prediction)["access_condition"],
                         "paper_data_and_author_code")

    def test_train_only_selection_and_subject_five(self):
        reference, prediction = fixture()
        result = module.evaluate(reference, prediction)
        for task in module.DECODING_TASKS:
            self.assertEqual(len(result["electrodes"][task]), 12)
            region = result["regional_top_ten"][task][0]
            self.assertEqual(region["test_mean_auc"], [0, .5])
            self.assertEqual(region["selected_participant_ids"], [1])
            self.assertNotIn("e10", [e["electrode_id"] for e in region["selected_contacts"]])
        self.assertFalse(any(result["qualification"].values()))

    def test_fold_mean_not_pooled_training_auc(self):
        reference, prediction = fixture()
        # Perfect ranking within every fold, strongly separated fold intercepts.
        # Pooled out-of-fold AUC would be 0.6, not the source mean CV AUC of 1.
        for subject in prediction["subjects"]:
            for electrode in subject["electrodes"][:10]:
                for scores in electrode["tasks"].values():
                    for row in scores["train_cv"]:
                        _, fold, label = row["id"].split("_")
                        row["scores"] = [int(fold) * 10 + int(label)] * 2
        result = module.evaluate(reference, prediction)
        self.assertEqual(result["electrodes"]["sentence_onset"][0]["train_cv_mean_auc"], [1, 1])
        self.assertEqual(module.auc([0, 1] * 5, list(range(10))), .6)

    def test_reordering_scores_is_identity_safe(self):
        reference, prediction = fixture()
        expected = module.evaluate(reference, prediction)
        for subject in prediction["subjects"]:
            subject["electrodes"].reverse()
            for electrode in subject["electrodes"]:
                for task in electrode["tasks"].values():
                    task["test"].reverse()
                    task["train_cv"].reverse()
        self.assertEqual(module.evaluate(reference, prediction), expected)

    def test_window_and_inventory_attacks(self):
        for attack, message in [
            (lambda r, p: p["subjects"][0]["electrodes"].pop(), "inventory"),
            (lambda r, p: p["subjects"][0]["electrodes"][0]["tasks"].pop("word_onset"), "fields"),
            (lambda r, p: p["subjects"][0]["electrodes"][0]["tasks"]["sentence_onset"]["test"][0]["scores"].pop(), "grid"),
            (lambda r, p: r["subjects"][0]["corrupted_electrodes"].append("e0"), "corrupted"),
            (lambda r, p: p["subjects"].pop(), "subject"),
            (lambda r, p: p["subjects"][0]["electrodes"][0]["tasks"]["sentence_onset"]["test"].append({"id": "train_0_0", "scores": [0, 0]}), "identities"),
        ]:
            with self.subTest(message=message):
                reference, prediction = fixture()
                attack(reference, prediction)
                with self.assertRaisesRegex(ValueError, message):
                    module.evaluate(reference, prediction)

    def test_cutoff_tie_fails_instead_of_selecting_on_test(self):
        reference, prediction = fixture()
        for task in module.DECODING_TASKS:
            prediction["subjects"][0]["electrodes"][10]["tasks"][task]["train_cv"] = copy.deepcopy(
                prediction["subjects"][0]["electrodes"][0]["tasks"][task]["train_cv"])
        with self.assertRaisesRegex(ValueError, "tie"):
            module.evaluate(reference, prediction)

    def test_small_region_and_incomplete_cohort_cannot_be_source_panel(self):
        reference, prediction = fixture()
        reference["scope"] = "operator_declared_panel"
        with self.assertRaisesRegex(ValueError, "ten-participant"):
            module.evaluate(reference, prediction)
        reference["scope"] = "generated_control"
        reference["subjects"][0]["electrodes"] = reference["subjects"][0]["electrodes"][:9]
        prediction["subjects"][0]["electrodes"] = prediction["subjects"][0]["electrodes"][:9]
        with self.assertRaisesRegex(ValueError, "ten eligible"):
            module.evaluate(reference, prediction)

    def test_cli_receipts_and_no_overwrite(self):
        reference, prediction = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ref, pred, output = [root / f"{name}.json" for name in ("ref", "pred", "out")]
            ref.write_text(json.dumps(reference))
            pred.write_text(json.dumps(prediction))
            command = [sys.executable, "-I", "-B", str(Path(module.__file__)), str(ref), str(pred), "--output", str(output)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(output.read_text())
            self.assertEqual(result["input_sha256"]["reference"], module.hashlib.sha256(ref.read_bytes()).hexdigest())
            self.assertNotIn('"label"', output.read_text())
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            json.loads('{"x":1,"x":2}', object_pairs_hook=module.reject_duplicates)


if __name__ == "__main__":
    unittest.main()
