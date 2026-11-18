"""Generated engineering controls; no authentic neural arrays or model results."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("barista_selected_score", HERE / "score.py")
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)
import numpy as np
from arrays import write_array
from protocol import canonical, digest


def public_panel():
    public = {
        "schema": "barista_selected_primary_panel_v1", "task_id": score.TASK_ID,
        "source_protocol_sha256": score.SOURCE_PROTOCOL_SHA,
        "scope_contract_sha256": score.SCOPE_SHA256,
        "generation_commitment": "a" * 64,
        "contexts": [dict(row, query_count=4, query_ids_sha256=digest([row["id"], "generated"]))
                     for row in score.contexts()],
    }
    public["panel_id"] = digest(public)
    return public


def fingerprint(public):
    public["panel_id"] = digest({k: v for k, v in public.items() if k != "panel_id"})


def gold_panel(public, body, labels=None, baseline=None):
    return {
        "schema": "barista_selected_primary_gold_v1", "panel_id": public["panel_id"],
        "public_sha256": hashlib.sha256(body).hexdigest(), "baseline_model": score.BASELINE_MODEL,
        "contexts": [{"id": row["id"], "query_ids_sha256": row["query_ids_sha256"],
                      "labels": labels, "trusted_parcels_channels": baseline,
                      "provenance": {key: "b" * 64 for key in score.PROVENANCE_KEYS}}
                     for row in public["contexts"]],
    }


class SelectedPrimaryTests(unittest.TestCase):
    def test_exact_selected_panel_and_all_seven_people(self):
        panel = score.validate_public(public_panel())
        rows = list(score.outputs(panel))
        self.assertEqual(len(panel["contexts"]), 420)
        self.assertEqual(len(rows), 5880)
        self.assertEqual(set(row["person"] for row in rows), {1, 2, 3, 4, 6, 7, 10})
        self.assertEqual(set(row["task"] for row in rows), {
            "sentence_onset", "speech_vs_nonspeech", "sentence_onset_time", "speech_vs_nonspeech_time"})
        self.assertEqual(set(row["model"] for row in rows), {
            "barista_channels_channels", "barista_parcels_channels", "barista_lobes_channels",
            "random_channels", "random_parcels", "random_lobes", "improved"})
        for task in ("sentence_onset", "speech_vs_nonspeech"):
            self.assertEqual(sum(row["task"] == task for row in panel["contexts"]), 35)
        for task in ("sentence_onset_time", "speech_vs_nonspeech_time"):
            self.assertEqual(sum(row["task"] == task for row in panel["contexts"]), 175)

    def test_scope_and_generation_cannot_be_borrowed(self):
        for key, value in (("scope_contract_sha256", "f" * 64),
                           ("source_protocol_sha256", "f" * 64),
                           ("schema", "barista_public_panel_v1"),
                           ("task_id", "another-task")):
            changed = public_panel()
            changed[key] = value
            fingerprint(changed)
            with self.assertRaisesRegex(ValueError, "binding"):
                score.validate_public(changed)
        changed = public_panel()
        changed["contexts"][0]["query_ids_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            score.validate_public(changed)

    def test_context_omission_duplication_or_bool_identity_rejected(self):
        mutations = (
            lambda p: p["contexts"].pop(),
            lambda p: p["contexts"].reverse(),
            lambda p: p["contexts"].__setitem__(1, p["contexts"][0]),
            lambda p: p["contexts"][0].update(person=True),
            lambda p: p["contexts"][0].update(query_count=True),
            lambda p: p["contexts"][0].update(task="volume"),
        )
        for mutate in mutations:
            changed = public_panel()
            mutate(changed)
            fingerprint(changed)
            with self.assertRaises(ValueError):
                score.validate_public(changed)

    def test_all_source_control_artifacts_required_before_gold_access(self):
        panel = public_panel()
        rows = [{key: row[key] for key in ("id", "arm", "model", "query_ids_sha256")} | {"values": {}}
                for row in score.outputs(panel)]
        called = []
        def forbidden_gold():
            called.append(True)
            raise AssertionError("Gold must stay unopened")
        sub = {"schema": "barista_selected_primary_submission_v1", "task_id": score.TASK_ID,
               "panel_id": panel["panel_id"], "predictions": rows[:-1]}
        result = score._grade_bytes(canonical(panel), canonical(sub), HERE, forbidden_gold)
        self.assertEqual(result["status"], "invalid_submission")
        self.assertFalse(result["private_numeric_inputs_opened"])
        self.assertFalse(called)
        # A same-size off-primary condition cannot replace a selected control.
        sub["predictions"] = rows
        rows[0]["model"] = "barista_channels_parcels"
        result = score._grade_bytes(canonical(panel), canonical(sub), HERE, forbidden_gold)
        self.assertEqual(result["status"], "invalid_submission")
        self.assertFalse(called)

    def test_reference_cannot_be_candidate_control_or_wrong_query(self):
        panel = public_panel()
        body = canonical(panel)
        gold = gold_panel(panel, body)
        self.assertEqual(len(score.validate_gold(gold, panel, body)), 420)
        mutations = (
            lambda g: g.update(baseline_model="random_parcels"),
            lambda g: g["contexts"].pop(),
            lambda g: g["contexts"][0].update(query_ids_sha256="a" * 64),
            lambda g: g["contexts"][0]["provenance"].pop("execution_receipt_sha256"),
            lambda g: g.update(public_sha256="a" * 64),
        )
        for mutate in mutations:
            changed = copy.deepcopy(gold)
            mutate(changed)
            with self.assertRaises(ValueError):
                score.validate_gold(changed, panel, body)

    def test_endpoint_regression_and_repeated_person_structure_retained(self):
        rows = []
        for context in score.contexts():
            # Deliberately asymmetric per-person values expose pseudoreplication.
            value = context["person"] / 10
            rows.append(dict(context, candidate_auc=value, baseline_auc=.5, paired_gain=value - .5))
        result = score.endpoint_summaries(rows)
        self.assertEqual(len(result), 4)
        for index, endpoint in enumerate(result):
            self.assertEqual(endpoint["source_cell_count"], 35 if index < 2 else 175)
            self.assertEqual([p["repeat_count"] for p in endpoint["paired_people"]],
                             [5 if index < 2 else 25] * 7)
            person = endpoint["candidate_auc"]["equal_person_summary"]
            pooled = endpoint["candidate_auc"]["source_cell_summary"]
            self.assertEqual(person["count"], 7)
            self.assertNotEqual(person["sem"], pooled["sem"])
        for row in rows:
            if row["task"] == "sentence_onset":
                row.update(candidate_auc=.25, paired_gain=-.25)
        result = score.endpoint_summaries(rows)
        self.assertEqual(result[0]["paired_gain"]["source_cell_summary"]["mean"], -.25)
        with self.assertRaisesRegex(ValueError, "roster"):
            score.endpoint_summaries(rows + [dict(rows[0], task="optical_flow")])

    def test_undefined_original_support_not_dropped_or_imputed(self):
        rows = [dict(row, candidate_auc=.75, baseline_auc=.5, paired_gain=.25)
                for row in score.contexts()]
        rows[0].update(candidate_auc=None, baseline_auc=None, paired_gain=None)
        endpoints = score.endpoint_summaries(rows)
        self.assertIsNone(endpoints[0]["paired_gain"]["source_cell_summary"]["mean"])
        self.assertEqual(endpoints[0]["paired_gain"]["source_cell_summary"]["count"], 35)
        self.assertEqual(endpoints[0]["paired_gain"]["equal_person_summary"]["count"], 7)
        self.assertEqual(endpoints[1]["paired_gain"]["source_cell_summary"]["mean"], .25)

    def test_full_selected_numerical_path_and_final_artifact_refusal(self):
        # Four tiny shared generated NPY files; full identity grid stays in RAM.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            y = write_array(root / "y.npy", np.array([0, 1, 0, 1]))
            good = write_array(root / "good.npy", np.array([.1, .9, .2, .8]))
            bad = write_array(root / "bad.npy", np.array([.9, .1, .8, .2]))
            ref = write_array(root / "ref.npy", np.full(4, .5))
            panel = public_panel()
            public_body = canonical(panel)
            rows = []
            for row in score.outputs(panel):
                desc = bad if row["model"] == "improved" and row["task"] == "sentence_onset" else good
                rows.append({key: row[key] for key in ("id", "arm", "model", "query_ids_sha256")}
                            | {"values": desc})
            sub = {"schema": "barista_selected_primary_submission_v1", "task_id": score.TASK_ID,
                   "panel_id": panel["panel_id"], "predictions": rows}
            gold = gold_panel(panel, public_body, y, ref)
            called = []
            def supplied_gold():
                called.append(True)
                return gold, root
            result = score._grade_bytes(public_body, canonical(sub), root, supplied_gold)
            self.assertEqual(called, [True])
            self.assertEqual(result["status"], "defined")
            self.assertIsNone(result["cross_task_primary"])
            for flag in ("paper_win_established", "reference_execution_authenticated",
                         "reference_competence_qualified", "historical_sem_parity_established",
                         "scientific_significance_established", "readiness_promoted"):
                self.assertFalse(result[flag])
            for arm in score.ARMS:
                self.assertEqual(len(result["source_companions"][arm]), 24)
                self.assertEqual(len(result["source_cells"][arm]), 2520)
                self.assertEqual(len(result["candidate_cells"][arm]), 420)
                endpoints = result["classification_endpoints"][arm]
                self.assertEqual(endpoints[0]["paired_gain"]["source_cell_summary"]["mean"], -.5)
                self.assertEqual([e["paired_gain"]["source_cell_summary"]["mean"] for e in endpoints[1:]],
                                 [.5, .5, .5])
                # Perfect submitted source controls do not become the reference.
                self.assertTrue(all(e["baseline_auc"]["source_cell_summary"]["mean"] == .5
                                    for e in endpoints))
            sub["predictions"][-1]["values"] = dict(good, path="absent.npy")
            result = score._grade_bytes(public_body, canonical(sub), root, supplied_gold)
            self.assertEqual(result["status"], "invalid_submission")
            self.assertFalse(result["private_numeric_inputs_opened"])
            self.assertEqual(called, [True])


if __name__ == "__main__":
    unittest.main(verbosity=2)
