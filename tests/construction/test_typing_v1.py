"""Independent generated V1 arithmetic, complete-panel and split controls.

No source recordings, model, native training or scientific campaign is run.
The five-row fixture is an explicitly declared invented panel, not a real cohort.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import importlib.util
from itertools import product
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


RELATIVE_PACKAGE = Path("benchmarks/paper/PAPER-ROOT-ADD-002/implementations/v1-transcript-evaluation-v1")
ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / RELATIVE_PACKAGE
SPEC = importlib.util.spec_from_file_location("typing_v1_independent_target", PACKAGE / "evaluator.py")
TARGET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TARGET)


def independent_distance(reference, prediction):
    """Full-table DP, independent of the implementation's rolling row."""
    matrix = [[0] * (len(prediction) + 1) for _ in range(len(reference) + 1)]
    for i in range(len(reference) + 1):
        matrix[i][0] = i
    for j in range(len(prediction) + 1):
        matrix[0][j] = j
    for i in range(1, len(reference) + 1):
        for j in range(1, len(prediction) + 1):
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1,
                               matrix[i - 1][j - 1] + (reference[i - 1] != prediction[j - 1]))
    return matrix[-1][-1]


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def limits(**changes):
    values = {"max_json_bytes": 1000000, "max_edit_cells": 1000000, "max_codepoints": 100000}
    values.update(changes)
    return TARGET.Limits(**values)


def fixture():
    # Expected aggregate derived using exact fractions, before inspecting target code:
    # S1 CER=(1+0)/2=1/2; S5 CER=(1/5+2/5+2)/3=13/15.
    # Macro CER=41/60; WER=(1/2+11/18)/2=5/9; CER SEM=11/60.
    contract = TARGET.source_contract()
    definitions = [("S1", "S1", "01", "a", ""),
                   ("S18", "S1", "18", "aaaa", "aaaa"),
                   ("S5", "S5", "05", "ab cd", "ab xd"),
                   ("S10", "S5", "10", "a b c", "a b"),
                   ("S21", "S5", "21", "x", "x y")]
    panel = {"schema": "typing-v1-panel-v1", "task_id": "PAPER-ROOT-ADD-002",
             "metric_route": "pinned-v1-presented-sentence-export",
             "source": {"code_commit": "5f9889621d0df391c5aab37c996683d308e6e926",
                        "data_revision": "88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684"},
             "modality": "MEG",
             "condition": {"id": "generated-arithmetic-control", "access_condition": "paper_and_data",
                           "split_kind": "prospective-declared", "disjoint_units": ["sentence_cluster"],
                           "calibration_sentence_limit_per_person": 0, "representation": "transcript"},
             "provenance": {"panel_id": "invented-five-row-control",
                            "eligibility_manifest_sha256": "0" * 64, "preprocessing_manifest_sha256": "1" * 64,
                            "grouping_manifest_sha256": "2" * 64, "training_or_checkpoint_manifest_sha256": "3" * 64},
             "aliases": [], "recordings": [], "cases": []}
    candidate = {"schema": "typing-v1-predictions-v1", "task_id": "PAPER-ROOT-ADD-002",
                 "metric_route": "pinned-v1-presented-sentence-export", "representation": "transcript", "predictions": []}
    for i, (participant, person, folder, reference, prediction) in enumerate(definitions):
        source = next(row for row in contract["source_records"] if row["path"].startswith(f"MEG/FIF/{folder}_") and contract["recording_identities"][row["path"]]["primary_case_eligible"])
        metadata = contract["recording_identities"][source["path"]]
        uid = f"{i + 2}.0_{metadata['study']}_subject-{participant}_session-{metadata['session_id']}_task-{metadata['task']}"
        panel["aliases"].append({"participant_id": participant, "person_id": person})
        panel["recordings"].append({"path": source["path"], "bytes": source["bytes"], "sha256": "4" * 64})
        row = {"case_id": f"case-{i}", "participant_id": participant, "session_id": metadata["session_id"],
               "sentence_uid": uid, "sentence_cluster_id": f"generated-cluster-{i}",
               "trial_id": i + 2, "split": "test", "source_path": source["path"], "reference_text": reference,
               "keystroke_ids": [f"{uid}_button_1", f"{uid}_button_2"]}
        panel["cases"].append(row)
        candidate["predictions"].append({"case_id": row["case_id"], "keystroke_ids": list(row["keystroke_ids"]), "text": prediction})
    return panel, candidate


def evaluate(panel, candidate, configured_limits=None):
    raw = encoded(panel)
    return TARGET.evaluate_bytes(raw, hashlib.sha256(raw).hexdigest(), encoded(candidate), configured_limits or limits())


def add_training_case(panel, *, participant="S1", text="new", cluster="training-cluster", split="train", trial=77):
    row = copy.deepcopy(next(r for r in panel["cases"] if r["participant_id"] == participant))
    metadata = TARGET.source_contract()["recording_identities"][row["source_path"]]
    uid = f"{trial}.0_{metadata['study']}_subject-{participant}_session-{metadata['session_id']}_task-{metadata['task']}"
    row.update(case_id=f"training-case-{trial}", sentence_uid=uid, sentence_cluster_id=cluster,
               trial_id=trial, split=split, reference_text=text,
               keystroke_ids=[f"{uid}_button_1", f"{uid}_button_2"])
    panel["cases"].append(row)


class TypingIndependentControls(unittest.TestCase):
    def test_exact_raw_metric_cases(self):
        cases = [("abc", "abxc", Fraction(1, 3), Fraction(1)),
                 ("a b", "a  b", Fraction(1, 3), Fraction(0)),
                 ("a\tb", "a b", Fraction(1, 3), Fraction(0)),
                 ("Árbol", "árbol", Fraction(1, 5), Fraction(1)),
                 ("é", "e\u0301", Fraction(2), Fraction(1)),
                 ("e\u0301", "é", Fraction(1), Fraction(1)),
                 ("mañana", "manana", Fraction(1, 6), Fraction(1)),
                 ("", "a", None, None), (" \t ", "", Fraction(1), None),
                 ("a", "abcdef", Fraction(5), Fraction(1)),
                 ("hello world", "hello", Fraction(6, 11), Fraction(1, 2)),
                 ("hola mundo", "", Fraction(1), Fraction(1)),
                 ("hola mundo", "hola mundo", Fraction(0), Fraction(0))]
        for reference, prediction, cer, wer in cases:
            with self.subTest(reference=reference, prediction=prediction):
                result = TARGET.sentence_metrics(reference, prediction, TARGET.EditBudget(10000))
                self.assertEqual(result["character_edits"], independent_distance(reference, prediction))
                self.assertEqual(result["word_edits"], independent_distance(reference.split(), prediction.split()))
                self.assertEqual(result["cer"], None if cer is None else float(cer))
                self.assertEqual(result["wer"], None if wer is None else float(wer))

    def test_exhaustive_small_string_oracle(self):
        corpus = ["".join(p) for size in range(4) for p in product("ab ", repeat=size)]
        self.assertEqual(len(corpus), 40)
        for reference in corpus:
            for prediction in corpus:
                result = TARGET.sentence_metrics(reference, prediction, TARGET.EditBudget(10000))
                self.assertEqual(result["character_edits"], independent_distance(reference, prediction))
                self.assertEqual(result["word_edits"], independent_distance(reference.split(), prediction.split()))

    def test_alias_merged_person_arithmetic_and_complete_coverage(self):
        panel, candidate = fixture()
        result = evaluate(panel, candidate)
        self.assertAlmostEqual(result["summary"]["cer"], 41 / 60)
        self.assertAlmostEqual(result["summary"]["wer"], 5 / 9)
        self.assertAlmostEqual(result["summary"]["cer_sem"], 11 / 60)
        self.assertEqual(result["summary"]["person_count"], 2)
        self.assertEqual([r["person_id"] for r in result["summary"]["source_conditional_defined_support"]["people"]], ["S1", "S5"])
        self.assertEqual(result["declared_population"]["assessment_cases"], 5)
        self.assertEqual(result["cases"][-1]["cer"], 2.0)
        self.assertTrue(result["summary"]["complete_metric_support"])
        self.assertTrue(all(value is False for value in result["verification"].values()))

    def test_undefined_support_diagnostics_do_not_invent_zero(self):
        rows = [{"person_id": "S1", "cer": None, "wer": None},
                {"person_id": "S1", "cer": 2 / 3, "wer": 1 / 2},
                {"person_id": "S2", "cer": 1, "wer": None},
                {"person_id": "S3", "cer": None, "wer": None}]
        summary = TARGET.summarize(rows)
        self.assertIsNone(summary["cer"])
        self.assertIsNone(summary["wer"])
        self.assertIsNone(summary["cer_sem"])
        conditional = summary["source_conditional_defined_support"]
        self.assertAlmostEqual(conditional["cer"], 5 / 6)
        self.assertEqual(conditional["wer"], 1 / 2)
        self.assertAlmostEqual(conditional["source_cer_sem"] ** 2, 1 / 54)
        self.assertEqual(conditional["cer_defined_people"], 2)
        self.assertEqual(conditional["wer_defined_people"], 1)
        self.assertFalse(summary["complete_metric_support"])
        empty = TARGET.summarize([{"person_id": "S1", "cer": None, "wer": None}])
        self.assertIsNone(empty["cer"])
        self.assertIsNone(empty["wer"])
        self.assertIsNone(empty["cer_sem"])

    def test_frozen_vocabulary_and_no_ctc_collapse(self):
        panel, candidate = fixture()
        panel["condition"]["split_kind"] = "pinned-source-sentence-clusters"
        panel["condition"]["representation"] = candidate["representation"] = "per-keystroke-classes"
        for i, row in enumerate(candidate["predictions"]):
            row.pop("text")
            row["class_ids"] = [0, 0] if i == 0 else [13, 28]
            panel["cases"][i]["reference_text"] = "ss" if i == 0 else "@9"
            panel["cases"][i]["sentence_cluster_id"] = "ss" if i == 0 else "at-nine"
        result = evaluate(panel, candidate)
        self.assertEqual(result["summary"]["cer"], 0)
        self.assertEqual(result["summary"]["wer"], 0)
        for bad in (True, -1, 29, 1.0, "1", None):
            altered = copy.deepcopy(candidate)
            altered["predictions"][0]["class_ids"][0] = bad
            with self.subTest(bad=bad), self.assertRaises(TARGET.CandidateError):
                evaluate(panel, altered)

    def test_missing_extra_duplicate_or_reordered_candidate_support_refused(self):
        panel, candidate = fixture()
        mutations = []
        altered = copy.deepcopy(candidate); altered["predictions"].pop(); mutations.append(altered)
        altered = copy.deepcopy(candidate); extra = copy.deepcopy(altered["predictions"][0]); extra["case_id"] = "extra"; altered["predictions"].append(extra); mutations.append(altered)
        altered = copy.deepcopy(candidate); altered["predictions"].append(copy.deepcopy(altered["predictions"][0])); mutations.append(altered)
        altered = copy.deepcopy(candidate); altered["predictions"][0]["keystroke_ids"].reverse(); mutations.append(altered)
        altered = copy.deepcopy(candidate); altered["predictions"][0]["true"] = "injected target"; mutations.append(altered)
        for i, altered in enumerate(mutations):
            with self.subTest(mutation=i), self.assertRaises(TARGET.CandidateError):
                evaluate(panel, altered)

    def test_declared_grouping_design_allows_source_within_person_but_refuses_holdout_overlap(self):
        panel, candidate = fixture()
        add_training_case(panel)
        self.assertEqual(evaluate(panel, candidate)["summary"]["person_count"], 2)
        panel["condition"]["split_kind"] = "prospective-declared"
        for unit in ("person", "person_session"):
            panel["condition"]["disjoint_units"] = ["sentence_cluster", unit]
            with self.subTest(unit=unit), self.assertRaises(TARGET.PanelError):
                evaluate(panel, candidate)
        # Raw S18 differs from S1, but aliases to S1 and must still overlap.
        panel["cases"].pop()
        add_training_case(panel, participant="S18")
        panel["condition"]["disjoint_units"] = ["sentence_cluster", "person"]
        with self.assertRaises(TARGET.PanelError):
            evaluate(panel, candidate)

    def test_identical_text_cannot_hide_behind_distinct_sentence_groups(self):
        panel, candidate = fixture()
        add_training_case(panel, text="a", cluster="forged-new-group")
        with self.assertRaises(TARGET.PanelError):
            evaluate(panel, candidate)
        panel["cases"][-1]["sentence_cluster_id"] = panel["cases"][0]["sentence_cluster_id"]
        with self.assertRaises(TARGET.PanelError):
            evaluate(panel, candidate)

    def test_calibration_budget_is_biological_person_grouped(self):
        panel, candidate = fixture()
        add_training_case(panel, split="calibration")
        with self.assertRaises(TARGET.PanelError):
            evaluate(panel, candidate)
        panel["condition"]["split_kind"] = "prospective-declared"
        panel["condition"]["calibration_sentence_limit_per_person"] = 1
        self.assertEqual(evaluate(panel, candidate)["summary"]["person_count"], 2)
        add_training_case(panel, participant="S18", text="other", cluster="other-calibration", split="calibration", trial=78)
        with self.assertRaises(TARGET.PanelError):
            evaluate(panel, candidate)

    def test_source_population_and_endpoint_contradictions_refused(self):
        panel, candidate = fixture()
        mutations = []
        altered = copy.deepcopy(panel); altered["aliases"][1]["person_id"] = "S18"; mutations.append(altered)
        altered = copy.deepcopy(panel); altered["modality"] = "EEG"; mutations.append(altered)
        altered = copy.deepcopy(panel); altered["source"]["code_commit"] = "0" * 40; mutations.append(altered)
        altered = copy.deepcopy(panel); altered["cases"][0]["trial_id"] = 1; mutations.append(altered)
        altered = copy.deepcopy(panel); altered["cases"][0]["sentence_uid"] = "65.0_Pinet2024Meg_subject-S1_session-1_task-block1"; mutations.append(altered)
        altered = copy.deepcopy(panel); altered["metric_route"] = "v2-final-language-model"; mutations.append(altered)
        altered = copy.deepcopy(panel); altered["condition"]["split_kind"] = "pinned-source-sentence-clusters"; mutations.append(altered)
        altered = copy.deepcopy(panel); altered["cases"][0]["participant_id"] = "S18"; mutations.append(altered)
        altered = copy.deepcopy(panel); altered["cases"][0]["session_id"] = "2"; mutations.append(altered)
        altered = copy.deepcopy(panel); altered["cases"][0]["sentence_uid"] = "999.0_Pinet2024Meg_subject-S1_session-1_task-block1"; mutations.append(altered)
        altered = copy.deepcopy(panel); altered["cases"][0]["keystroke_ids"] = []; mutations.append(altered)
        altered = copy.deepcopy(panel); altered["cases"].append(copy.deepcopy(altered["cases"][0])); mutations.append(altered)
        for i, altered in enumerate(mutations):
            with self.subTest(mutation=i), self.assertRaises(TARGET.PanelError):
                evaluate(altered, candidate)

    def test_independent_freeze_digest_and_resource_refusals(self):
        panel, candidate = fixture(); raw = encoded(panel)
        with self.assertRaises(TARGET.PanelError):
            TARGET.evaluate_bytes(raw, "0" * 64, encoded(candidate), limits())
        with self.assertRaises(TARGET.ResourceLimit):
            evaluate(panel, candidate, limits(max_json_bytes=1))
        with self.assertRaises(TARGET.ResourceLimit):
            evaluate(panel, candidate, limits(max_codepoints=1))
        with self.assertRaises(TARGET.ResourceLimit):
            TARGET.sentence_metrics("a", "", TARGET.EditBudget(3))
        self.assertEqual(TARGET.sentence_metrics("a", "", TARGET.EditBudget(4))["cer"], 1)

    def test_source_acquisition_sessions_distinguish_raw_alias_visits_and_same_visit_blocks(self):
        # S18 is the same biological person as S1, but its session1 is a
        # different source acquisition label. This is not biological-session proof.
        panel, candidate = fixture()
        add_training_case(panel, participant="S18")
        removed = next(row["case_id"] for row in panel["cases"]
                       if row["participant_id"] == "S18" and row["split"] == "test")
        panel["cases"] = [row for row in panel["cases"] if row["case_id"] != removed]
        candidate["predictions"] = [row for row in candidate["predictions"] if row["case_id"] != removed]
        panel["condition"]["disjoint_units"] = ["sentence_cluster", "person_session"]
        result = evaluate(panel, candidate)
        self.assertEqual(result["declared_population"]["assessment_cases"], 4)
        self.assertEqual(result["summary"]["person_count"], 2)
        self.assertTrue(all(value is False for value in result["verification"].values()))
        panel["condition"]["disjoint_units"] = ["sentence_cluster", "person"]
        with self.assertRaises(TARGET.PanelError):
            evaluate(panel, candidate)

        # Two different blocks still belong to one raw participant/session.
        panel, candidate = fixture()
        add_training_case(panel, participant="S1")
        training = panel["cases"][-1]
        contract = TARGET.source_contract()
        first = contract["recording_identities"][training["source_path"]]
        path, metadata = next((path, identity) for path, identity in contract["recording_identities"].items()
                              if identity["primary_case_eligible"] and identity["participant_id"] == "S1"
                              and identity["session_id"] == first["session_id"] and identity["task"] != first["task"])
        record = next(row for row in contract["source_records"] if row["path"] == path)
        panel["recordings"].append({"path": path, "bytes": record["bytes"], "sha256": "4" * 64})
        uid = f"77.0_{metadata['study']}_subject-S1_session-{metadata['session_id']}_task-{metadata['task']}"
        training.update(source_path=path, session_id=metadata["session_id"], sentence_uid=uid,
                        keystroke_ids=[f"{uid}_button_1", f"{uid}_button_2"])
        # Establish that the metadata and complete prediction panel are otherwise valid.
        self.assertEqual(evaluate(panel, candidate)["declared_population"]["assessment_cases"], 5)
        panel["condition"]["disjoint_units"] = ["sentence_cluster", "person_session"]
        with self.assertRaises(TARGET.PanelError):
            evaluate(panel, candidate)

    def test_trial_uid_numeric_spellings_cannot_double_weight_one_physical_trial(self):
        panel, candidate = fixture()
        baseline = evaluate(panel, candidate)
        self.assertAlmostEqual(baseline["summary"]["cer"], 41 / 60)
        integer_panel, integer_candidate = copy.deepcopy(panel), copy.deepcopy(candidate)
        row = integer_panel["cases"][0]
        suffix = row["sentence_uid"].split("_", 1)[1]
        integer_uid = f"{row['trial_id']}_{suffix}"
        row["sentence_uid"] = integer_uid
        row["keystroke_ids"] = [f"{integer_uid}_button_1", f"{integer_uid}_button_2"]
        integer_candidate["predictions"][0]["keystroke_ids"] = list(row["keystroke_ids"])
        # Either loader-supported numeric spelling is valid by itself.
        self.assertAlmostEqual(evaluate(integer_panel, integer_candidate)["summary"]["cer"], 41 / 60)

        duplicate = copy.deepcopy(row)
        duplicate["case_id"] = "second-spelling-same-physical-trial"
        duplicate_prediction = copy.deepcopy(integer_candidate["predictions"][0])
        duplicate_prediction["case_id"] = duplicate["case_id"]
        panel["cases"].append(duplicate)
        candidate["predictions"].append(duplicate_prediction)
        # Literal case, UID and keystroke strings are distinct and coverage matches;
        # only the physical trial key reveals that the observation was duplicated.
        with self.assertRaises(TARGET.PanelError):
            evaluate(panel, candidate)

        # A genuinely different trial may present the same text in the same fold.
        duplicate["trial_id"] = 78
        distinct_uid = f"78_{suffix}"
        duplicate["sentence_uid"] = distinct_uid
        duplicate["keystroke_ids"] = [f"{distinct_uid}_button_1", f"{distinct_uid}_button_2"]
        duplicate_prediction["keystroke_ids"] = list(duplicate["keystroke_ids"])
        result = evaluate(panel, candidate)
        self.assertEqual(result["declared_population"]["assessment_cases"], 6)
        # S1 means become2/3 rather than1/2; S5 remains13/15CER and11/18WER.
        self.assertAlmostEqual(result["summary"]["cer"], 23 / 30)
        self.assertAlmostEqual(result["summary"]["wer"], 23 / 36)
        self.assertAlmostEqual(result["summary"]["cer_sem"], 1 / 10)

    def test_corrupted_trial_exclusion_normalizes_uid_numeric_spellings(self):
        for trial, must_reject in ((65, True), (64, False)):
            for spelling in (str(trial), f"{trial}.0"):
                panel, candidate = fixture()
                row = panel["cases"][0]
                suffix = row["sentence_uid"].split("_", 1)[1]
                self.assertEqual(suffix, "Pinet2024Meg_subject-S1_session-1_task-block1")
                uid = f"{spelling}_{suffix}"
                row.update(trial_id=trial, sentence_uid=uid,
                           keystroke_ids=[f"{uid}_button_1", f"{uid}_button_2"])
                candidate["predictions"][0]["keystroke_ids"] = list(row["keystroke_ids"])
                with self.subTest(trial=trial, spelling=spelling):
                    if must_reject:
                        # Valid metadata and matching candidate identities isolate
                        # the known source exclusion rather than an unrelated guard.
                        with self.assertRaisesRegex(TARGET.PanelError, "source-excluded"):
                            evaluate(panel, candidate)
                    else:
                        result = evaluate(panel, candidate)
                        self.assertEqual(result["declared_population"]["assessment_cases"], 5)
                        self.assertAlmostEqual(result["summary"]["cer"], 41 / 60)

    def test_budget_schema_refuses_nonpositive_or_unsupported_read_sizes(self):
        for value in (True, False, 0, -1, 1.0, "1", None):
            for field in ("max_json_bytes", "max_edit_cells", "max_codepoints"):
                with self.subTest(value=value, field=field), self.assertRaises(TARGET.ResourceLimit):
                    limits(**{field: value})
        for value in (sys.maxsize, 10 ** 100):
            with self.subTest(huge=value), self.assertRaises(TARGET.ResourceLimit):
                limits(max_json_bytes=value)

    def test_read_budget_is_chunked_before_allocation(self):
        observed = []
        original_fdopen = TARGET.os.fdopen

        class GuardedStream:
            def __init__(self, fd, mode):
                self.stream = original_fdopen(fd, mode)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.stream.close()

            def read(self, size=-1):
                # Fail before allocation if a regression requests an enormous read.
                if not 0 < size <= 65536:
                    raise AssertionError("read must remain chunk-bounded")
                observed.append(size)
                return self.stream.read(size)

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tiny.json"
            path.write_bytes(b"abc")
            for maximum in (3, sys.maxsize - 1):
                with self.subTest(maximum=maximum), mock.patch.object(TARGET.os, "fdopen", side_effect=GuardedStream):
                    self.assertEqual(TARGET.read_bounded(path, maximum), b"abc")
            with mock.patch.object(TARGET.os, "fdopen", side_effect=GuardedStream):
                with self.assertRaises(TARGET.ResourceLimit):
                    TARGET.read_bounded(path, 2)
        self.assertTrue(observed)

    def test_duplicate_json_nonfinite_and_surrogates_are_candidate_errors(self):
        panel, candidate = fixture(); raw = encoded(panel); digest = hashlib.sha256(raw).hexdigest()
        duplicate = b'{"schema":"x","schema":"y"}'
        nonfinite = b'{"schema":NaN}'
        for payload in (duplicate, nonfinite, b'\xff', b'[' * 1500 + b']' * 1500):
            with self.subTest(payload=payload[:30]), self.assertRaises(TARGET.CandidateError):
                TARGET.evaluate_bytes(raw, digest, payload, limits())
        candidate["predictions"][0]["text"] = "\ud800"
        with self.assertRaises(TARGET.CandidateError):
            TARGET.evaluate_bytes(raw, digest, json.dumps(candidate).encode(), limits())

    def test_cli_valid_output_no_overwrite_and_malformed_candidate_before_panel(self):
        panel, candidate = fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); p = root / "panel.json"; c = root / "candidate.json"; out = root / "result.json"
            p.write_bytes(encoded(panel)); c.write_bytes(encoded(candidate))
            args = [sys.executable, "-I", "-S", "-B", str(PACKAGE / "evaluator.py"), "--panel", str(p),
                    "--panel-sha256", hashlib.sha256(p.read_bytes()).hexdigest(), "--predictions", str(c),
                    "--output", str(out), "--max-json-bytes", "1000000", "--max-edit-cells", "1000000", "--max-codepoints", "100000"]
            result = subprocess.run(args, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            original = out.read_bytes()
            again = subprocess.run(args, capture_output=True, text=True, timeout=10)
            self.assertEqual(again.returncode, 3)
            self.assertEqual(out.read_bytes(), original)
            p.unlink(); c.write_bytes(b'{"bad":true}')
            bad = subprocess.run(args, capture_output=True, text=True, timeout=10)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(json.loads(bad.stdout)["status"], "invalid_candidate")
            self.assertNotIn(str(p), bad.stdout)


if __name__ == "__main__":
    unittest.main()
