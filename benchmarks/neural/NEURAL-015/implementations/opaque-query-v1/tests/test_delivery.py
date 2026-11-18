"""Generated complete26-record controls; no authentic observations or model runs."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("opaque_neural015_test", ROOT / "delivery.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
fixture_spec = importlib.util.spec_from_file_location("opaque_neural015_fixture", d.BASE / "tests" / "test_evaluator.py")
fixture_module = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture_module)
KEY = bytes(range(32))  # Deliberately public generated-test key; never use for a benchmark.


def fixture():
    reference, original = fixture_module.fixture()
    # Different predictions per recording detect accidental reassignment.
    for number, row in enumerate(original["predictions"]):
        row["neural"] = [(number * 8 + j + 1) / 209 for j in range(len(row["neural"]))]
    _, query, mapping, _ = d._identity_map(reference, KEY)
    by_source = {row["recording_id"]: row for row in original["predictions"]}
    opaque = {"task_id": d.e.TASK, "delivery_profile": d.PROFILE,
              "query_sha256": d.e.digest(query), "predictions": [
                  {"case_id": row["case_id"], "fold_id": row["fold_id"],
                   "neural": by_source[mapping[row["case_id"]]["recording_id"]]["neural"][:]}
                  for row in query["recordings"]]}
    return reference, original, opaque


class QueryControls(unittest.TestCase):
    def test_exact_allowlist_and_complete_coverage(self):
        ref, _, _ = fixture()
        query = d.public_query(ref, KEY)
        self.assertEqual(set(query), {"task_id", "delivery_profile", "protocol_sha256", "recordings"})
        self.assertEqual(len(query["recordings"]), 26)
        self.assertEqual(len({row["case_id"] for row in query["recordings"]}), 26)
        self.assertEqual(len({row["fold_id"] for row in query["recordings"]}), 5)
        for row in query["recordings"]:
            self.assertEqual(set(row), {"case_id", "fold_id", *d.GRID_FIELDS})
            self.assertEqual(row["n_grid_points"], 8)
        text = json.dumps(query)
        for identity in d.e.IDENTITIES.values():
            self.assertNotIn(identity["recording_id"], text)
            self.assertNotIn(identity["movie_id"], text)
        self.assertNotIn(KEY.hex(), text)
        self.assertNotIn("joint-", text)

    def test_labels_comparator_and_private_label_hashes_do_not_change_query(self):
        ref, _, _ = fixture()
        expected = d.public_query(ref, KEY)
        for row in ref["recordings"]:
            row["word_onset_samples"] = [6, 8, 12]
            row["acoustic_visual_probabilities"] = [.8] * 8
            row["alignment_sha256"] = "1" * 64
            row["transcript_sha256"] = "2" * 64
        self.assertEqual(d.public_query(ref, KEY), expected)

    def test_source_observation_and_key_changes_bind_a_different_query(self):
        ref, _, _ = fixture()
        before = d.public_query(ref, KEY)
        other_key = bytes(reversed(KEY))
        self.assertNotEqual(d.public_query(ref, other_key), before)
        ref["recordings"][0]["neural_sha256"] = "0" * 64
        self.assertNotEqual(d.public_query(ref, KEY), before)

    def test_original_record_order_cannot_reveal_source_order(self):
        ref, _, _ = fixture()
        before = d.public_query(ref, KEY)
        ref["recordings"].reverse()
        ref["folds"].reverse()
        for fold in ref["folds"]:
            for part in ("train", "test", "unused"):
                fold[part].reverse()
        self.assertEqual(d.public_query(ref, KEY), before)
        aliases = [r["case_id"] for r in before["recordings"]]
        self.assertEqual(aliases, sorted(aliases))

    def test_training_membership_change_rebinds_query_and_rejects_stale_response(self):
        ref, _, stale = fixture()
        before = d.public_query(ref, KEY)
        fold = ref["folds"][0]
        fold["unused"].append(fold["train"].pop())
        # This is a valid original reference with unchanged test grids.
        d.e.validate_reference(ref)
        self.assertNotEqual(d.public_query(ref, KEY), before)
        with self.assertRaisesRegex(d.ContractError, "binding"):
            d.restore_submission(ref, KEY, stale)

    def test_exact_binary_key_length_and_type(self):
        ref, _, _ = fixture()
        for bad in (b"", KEY[:-1], KEY + b"x", KEY.hex(), bytearray(KEY), None):
            with self.subTest(kind=type(bad).__name__), self.assertRaises(d.ContractError):
                d.public_query(ref, bad)

    def test_source_reference_coverage_and_leakage_gates_remain_active(self):
        ref, _, _ = fixture()
        ref["recordings"].pop()
        with self.assertRaises(d.ContractError):
            d.public_query(ref, KEY)
        ref, _, _ = fixture()
        fold = ref["folds"][0]
        moved = fold["test"].pop()
        fold["train"].append(moved)
        with self.assertRaises(d.ContractError):
            d.public_query(ref, KEY)


class RestorationControls(unittest.TestCase):
    def test_every_distinct_prediction_restores_and_scores_identically(self):
        ref, original, opaque = fixture()
        self.assertEqual(len({tuple(row["neural"]) for row in original["predictions"]}), 26)
        opaque["predictions"].reverse()
        self.assertEqual(d.restore_submission(ref, KEY, opaque), original)
        expected = d.e.evaluate(ref, original)
        actual = d.evaluate(ref, KEY, opaque)
        self.assertEqual(actual["score"], expected)
        self.assertFalse(actual["access_isolation_qualified"])
        self.assertFalse(actual["scientific_admission"])
        self.assertFalse(actual["score"]["admitted"])

    def test_missing_duplicate_and_foreign_cases_reject(self):
        for mutation in ("missing", "duplicate", "foreign"):
            ref, _, opaque = fixture()
            if mutation == "missing":
                opaque["predictions"].pop()
            elif mutation == "duplicate":
                opaque["predictions"].append(copy.deepcopy(opaque["predictions"][0]))
            else:
                opaque["predictions"][0]["case_id"] = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(d.ContractError):
                d.restore_submission(ref, KEY, opaque)

    def test_wrong_fold_and_binding_reject(self):
        ref, _, opaque = fixture()
        row = opaque["predictions"][0]
        row["fold_id"] = next(r["fold_id"] for r in opaque["predictions"] if r["fold_id"] != row["fold_id"])
        with self.assertRaisesRegex(d.ContractError, "fold"):
            d.restore_submission(ref, KEY, opaque)
        ref, _, opaque = fixture()
        opaque["query_sha256"] = "0" * 64
        with self.assertRaisesRegex(d.ContractError, "binding"):
            d.restore_submission(ref, KEY, opaque)
        ref, _, opaque = fixture()
        with self.assertRaises(d.ContractError):
            d.restore_submission(ref, bytes(reversed(KEY)), opaque)

    def test_unknown_fields_cannot_smuggle_source_ids_or_controls(self):
        for field in ("recording_id", "movie_id", "acoustic_visual", "target"):
            ref, _, opaque = fixture()
            opaque["predictions"][0][field] = "not-permitted"
            with self.subTest(field=field), self.assertRaises(d.ContractError):
                d.restore_submission(ref, KEY, opaque)
        ref, _, opaque = fixture()
        opaque["secret"] = KEY.hex()
        with self.assertRaises(d.ContractError):
            d.restore_submission(ref, KEY, opaque)

    def test_probabilities_and_full_lengths_are_strict(self):
        for value in (True, "0.5", float("nan"), float("inf"), -.01, 1.01):
            ref, _, opaque = fixture()
            opaque["predictions"][0]["neural"][0] = value
            with self.subTest(value=repr(value)), self.assertRaises(d.ContractError):
                d.restore_submission(ref, KEY, opaque)
        for change in (-1, 1):
            ref, _, opaque = fixture()
            values = opaque["predictions"][0]["neural"]
            if change < 0:
                values.pop()
            else:
                values.append(.5)
            with self.assertRaises(d.ContractError):
                d.restore_submission(ref, KEY, opaque)

    def test_constant_predictions_remain_valid_not_a_success_claim(self):
        ref, _, opaque = fixture()
        for row in opaque["predictions"]:
            row["neural"] = [.5] * 8
        out = d.evaluate(ref, KEY, opaque)
        self.assertEqual(out["score"]["primary_uniform_grid"]["participant_macro"]["neural_average_precision"], .25)
        self.assertFalse(out["scientific_admission"])


class CommandControls(unittest.TestCase):
    def test_cli_new_private_output_and_score_path(self):
        ref, _, opaque = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference, key, submission = root / "reference.json", root / "key.bin", root / "submission.json"
            reference.write_text(json.dumps(ref))
            key.write_bytes(KEY)
            submission.write_text(json.dumps(opaque))
            output = root / "query.json"
            args = ["query", str(reference), "--key-file", str(key), "--output", str(output)]
            self.assertEqual(d.main(args), 0)
            first = output.read_bytes()
            self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(first), d.public_query(ref, KEY))
            self.assertEqual(d.main(args), 2)
            self.assertEqual(output.read_bytes(), first)
            score = root / "score.json"
            self.assertEqual(d.main(["score", str(reference), "--key-file", str(key), "--submission", str(submission), "--output", str(score)]), 0)
            self.assertEqual(json.loads(score.read_text())["score"]["population"]["recordings"], 26)

    def test_invalid_cli_input_produces_no_output(self):
        ref, _, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference, key, output = root / "reference.json", root / "key.bin", root / "absent.json"
            reference.write_text(json.dumps(ref))
            key.write_bytes(KEY + b"x")
            self.assertEqual(d.main(["query", str(reference), "--key-file", str(key), "--output", str(output)]), 2)
            self.assertFalse(output.exists())
            key.write_bytes(KEY)
            reference.write_text('{"task_id":"NEURAL-015","task_id":"NEURAL-015"}')
            self.assertEqual(d.main(["query", str(reference), "--key-file", str(key), "--output", str(output)]), 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
