"""Invented numerical controls, never authentic data or reference predictions."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("barista_endpoint_score", ROOT / "score.py")
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)
import numpy as np
from arrays import write_array
from design import contexts, SOURCE_PROTOCOL_SHA
from io_contract import put, capture
from protocol import digest


def public_panel():
    rows = [dict(e, query_count=4, query_ids_sha256=digest([e["id"], "invented"])) for e in contexts()]
    panel = {"schema": "barista_public_panel_v1", "task_id": score.TASK_ID,
             "source_protocol_sha256": SOURCE_PROTOCOL_SHA, "contexts": rows,
             "generation_commitment": "a" * 64}
    panel["panel_id"] = digest(panel)
    return panel


def paired_cells():
    return [dict(row, candidate_auc=.75, baseline_auc=.5, paired_gain=.25) for row in contexts()]


class EndpointTests(unittest.TestCase):
    def test_six_source_endpoints_and_original_repetition_units(self):
        rows = paired_cells()
        # Unequal participant effects expose a seed/fold-as-person mistake.
        for row in rows:
            row["candidate_auc"] = row["person"] / 10
            row["paired_gain"] = row["candidate_auc"] - .5
        out = score.endpoint_summaries(rows)
        self.assertEqual([(r["protocol"], r["task"]) for r in out], [
            ("random_nonoverlap", "sentence_onset"),
            ("random_nonoverlap", "speech_vs_nonspeech"),
            ("chronological", "sentence_onset_time"),
            ("chronological", "speech_vs_nonspeech_time"),
            ("chronological", "volume"), ("chronological", "optical_flow")])
        for endpoint, count, repeats in zip(out, [35, 35, 175, 175, 175, 175], [5, 5, 25, 25, 25, 25]):
            self.assertEqual(endpoint["source_cell_count"], count)
            self.assertEqual(endpoint["person_count"], 7)
            self.assertEqual([r["repeat_count"] for r in endpoint["paired_people"]], [repeats] * 7)
            individual = np.array([.1, .2, .3, .4, .6, .7, 1.])
            summary = endpoint["candidate_auc"]["equal_person_summary"]
            self.assertAlmostEqual(summary["mean"], individual.mean())
            self.assertAlmostEqual(summary["sem"], individual.std(ddof=1) / np.sqrt(7))
            self.assertNotEqual(summary["sem"], endpoint["candidate_auc"]["source_cell_summary"]["sem"])

    def test_no_task_can_hide_regression_in_another(self):
        rows = paired_cells()
        for row in rows:
            if row["task"] == "sentence_onset":
                row.update(candidate_auc=.25, paired_gain=-.25)
        out = score.endpoint_summaries(rows)
        self.assertEqual(out[0]["paired_gain"]["source_cell_summary"]["mean"], -.25)
        self.assertTrue(all(r["paired_gain"]["source_cell_summary"]["mean"] == .25 for r in out[1:]))
        with self.assertRaisesRegex(ValueError, "roster"):
            score.endpoint_summaries(rows[:-1])
        with self.assertRaisesRegex(ValueError, "roster"):
            score.endpoint_summaries(rows[::-1])

    def test_undefined_is_retained_only_in_affected_endpoint(self):
        rows = paired_cells()
        rows[0].update(candidate_auc=None, baseline_auc=None, paired_gain=None)
        out = score.endpoint_summaries(rows)
        self.assertIsNone(out[0]["paired_gain"]["source_cell_summary"]["mean"])
        self.assertIsNone(out[0]["paired_gain"]["equal_person_summary"]["mean"])
        self.assertEqual(out[0]["paired_gain"]["source_cell_summary"]["count"], 35)
        self.assertEqual(out[1]["paired_gain"]["source_cell_summary"]["mean"], .25)

    def test_auc_matches_independent_pairwise_definition(self):
        labels = np.array([0, 1, 0, 1, 1, 0])
        predictions = np.array([.5, .5, .2, .8, .2, .9])
        pairs = [float(p > n) + .5 * float(p == n)
                 for p in predictions[labels == 1] for n in predictions[labels == 0]]
        self.assertAlmostEqual(score.auc(labels, predictions)["roc_auc"], sum(pairs) / len(pairs))

    def test_gold_cannot_borrow_baseline_from_wrong_panel_or_context(self):
        public = public_panel()
        body = b"fixture"
        gold = {"schema": "barista_endpoint_gold_v2", "panel_id": public["panel_id"],
                "public_sha256": hashlib.sha256(body).hexdigest(), "baseline_model": score.BASELINE_MODEL,
                "contexts": [{"id": r["id"], "query_ids_sha256": r["query_ids_sha256"],
                              "labels": {}, "trusted_parcels_channels": {},
                              "provenance": {k: "a" * 64 for k in score.PROVENANCE_KEYS}}
                             for r in public["contexts"]]}
        score.validate_gold(gold, public, body)
        for mutate in (lambda g: g.update(baseline_model="random_channels"),
                       lambda g: g["contexts"][0].update(query_ids_sha256="b" * 64),
                       lambda g: g["contexts"].pop(),
                       lambda g: g["contexts"][0]["provenance"].pop("checkpoint_sha256")):
            changed = copy.deepcopy(gold)
            mutate(changed)
            with self.assertRaises(ValueError):
                score.validate_gold(changed, public, body)

    def test_complete_file_route_controls_pairing_and_early_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            public = public_panel()
            put(root / "PUBLIC.json", public)
            y = write_array(root / "y.npy", np.array([0, 1, 0, 1]))
            good = write_array(root / "good.npy", np.array([.1, .9, .2, .8]))
            bad = write_array(root / "bad.npy", np.array([.9, .1, .8, .2]))
            trusted = write_array(root / "trusted.npy", np.full(4, .5))
            predictions = []
            for row in score.outputs(public):
                # All candidate-declared companions are perfect; they must not
                # replace the independently bound .5 trusted comparator.
                desc = bad if row["model"] == "improved" and row["task"] == "sentence_onset" else good
                predictions.append({k: row[k] for k in ("id", "arm", "model", "query_ids_sha256")} | {"values": desc})
            self.assertEqual(len(predictions), 23100)
            submission = {"schema": "barista_endpoint_submission_v2", "task_id": score.TASK_ID,
                          "panel_id": public["panel_id"], "predictions": predictions}
            put(root / "SUB.json", submission)
            gold = {"schema": "barista_endpoint_gold_v2", "panel_id": public["panel_id"],
                    "public_sha256": hashlib.sha256(capture(root / "PUBLIC.json")).hexdigest(),
                    "baseline_model": score.BASELINE_MODEL, "contexts": [
                        {"id": r["id"], "query_ids_sha256": r["query_ids_sha256"], "labels": y,
                         "trusted_parcels_channels": trusted,
                         "provenance": {k: "a" * 64 for k in score.PROVENANCE_KEYS}}
                        for r in public["contexts"]]}
            put(root / "GOLD.json", gold)
            result = score.grade(root / "PUBLIC.json", root / "GOLD.json", root / "SUB.json")
            self.assertEqual(result["status"], "defined")
            self.assertIsNone(result["cross_task_primary"])
            self.assertFalse(result["paper_win_established"])
            for arm in score.ARMS:
                self.assertEqual(len(result["source_companions"][arm]), 84)
                self.assertEqual(len(result["source_cells"][arm]), 10780)
                self.assertEqual(len(result["candidate_cells"][arm]), 770)
                endpoints = result["classification_endpoints"][arm]
                self.assertEqual(endpoints[0]["paired_gain"]["source_cell_summary"]["mean"], -.5)
                self.assertTrue(all(e["paired_gain"]["source_cell_summary"]["mean"] == .5 for e in endpoints[1:]))
            # Invalid last artifact must fail before even opening GOLD metadata.
            submission["predictions"][-1]["values"] = dict(good, path="missing.npy")
            put(root / "INVALID.json", submission)
            rejected = score.grade(root / "PUBLIC.json", root / "DOES_NOT_EXIST.json", root / "INVALID.json")
            self.assertEqual(rejected["status"], "invalid_submission")
            self.assertFalse(rejected["private_numeric_inputs_opened"])
            # The v1 subset cannot be silently upgraded into main-task evidence.
            submission["predictions"] = [r for r in predictions
                if not (r["model"] == "improved" and r["id"].startswith("random_nonoverlap"))]
            put(root / "INCOMPLETE.json", submission)
            rejected = score.grade(root / "PUBLIC.json", root / "DOES_NOT_EXIST.json", root / "INCOMPLETE.json")
            self.assertEqual(rejected["status"], "invalid_submission")


if __name__ == "__main__":
    unittest.main(verbosity=2)
