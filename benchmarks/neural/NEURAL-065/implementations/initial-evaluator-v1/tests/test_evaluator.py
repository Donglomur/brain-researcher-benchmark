"""Generated controls only: no authentic cohort, reference model or signal claim."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("typing_evaluator", ROOT / "evaluator.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def fixture():
    packet = {"schema_version": 1, "task_id": e.TASK_ID, "source_commit": e.SOURCE_COMMIT,
              "data_commit": e.DATA_COMMIT, "modality": "MEG",
              "target_definition": "pinned_v1_typed_button_classes",
              "protocol": {"protocol_sha256": "1" * 64, "selection_sha256": "2" * 64,
                  "calibration_sentences_per_person": 0, "calibration_keystrokes_per_person": 0,
                  "bootstrap_seed": 11, "bootstrap_replicates": 200,
                  "max_sentence_characters": 100, "fixed_lm_id": None},
              "alignments": [], "sentences": []}
    # Oracle: A=mean(1,0)=.5, B=0, macro=.25; pooled would incorrectly be 1/12.
    examples = [("S2", "train", "zz"), ("S1", "query", "a"),
                ("S18", "query", "aaaaaaaaa"), ("S3", "query", "aa")]
    for i, (subject, phase, target) in enumerate(examples):
        ids = [f"event{j}" for j in range(len(target))]
        packet["alignments"].append({"recording_subject": "Pinet2024Meg/" + subject,
            "session_id": "session1", "biological_session_id": "visit-" + subject, "log_events": [{"id": k, "time_s": j} for j, k in enumerate(ids)],
            "neural_events": [{"id": "n" + k, "time_s": j + 10} for j, k in enumerate(ids)],
            "pairs": [{"log_id": k, "neural_id": "n" + k} for k in ids],
            "excluded_log_events": [], "excluded_neural_events": [],
            "log_to_neural_offset_s": 10, "max_residual_s": 0.001, "evidence_sha256": "3" * 64})
        packet["sentences"].append({"query_id": f"{i:032x}", "recording_subject": "Pinet2024Meg/" + subject,
            "session_id": "session1", "phase": phase, "template_id": f"template{i}",
            "template_text": f"sentence template {i}", "target_classes": [e.CHARACTERS.index(c) for c in target],
            "log_event_ids": ids, "neural_asset_sha256": f"{i:064x}"})
    neural = submission(packet, "neural_only", ["b", "aaaaaaaaa", "aa"])
    language = submission(packet, "language_only", ["", "", ""])
    return packet, neural, language


def submission(packet, arm, predictions):
    rows = [r for r in packet["sentences"] if r["phase"] == "query"]
    return {"schema_version": 1, "task_id": e.TASK_ID, "packet_sha256": e.digest(packet),
            "arm": arm, "lm_id": None,
            "predictions": [{"query_id": r["query_id"], "text": text} for r, text in zip(rows, predictions)]}


class MetricControls(unittest.TestCase):
    def test_independent_oracle_alias_and_two_level_weighting(self):
        p, n, l = fixture()
        out = e.evaluate(p, n, l)
        self.assertEqual(out["scores"]["neural_only"]["person_macro_cer"], .25)
        self.assertEqual(out["scores"]["neural_only"]["person_count"], 2)
        self.assertEqual(out["scores"]["language_only"]["person_macro_cer"], 1)
        self.assertEqual(out["paired_comparison"]["difference"], -.75)
        self.assertEqual(out["paired_comparison"]["interval_95"], [-1, -.5])
        self.assertNotIn("target_text", json.dumps(out))
        self.assertEqual(out["scientific_qualification"], "unknown")

    def test_exact_class_identity_and_edit_operations(self):
        self.assertEqual(e.decode_classes([0, 8, 13, 28]), "s @9")
        self.assertEqual(e.edit_distance("kitten", "sitting"), 3)
        self.assertEqual(e.edit_distance("abc", ""), 3)
        self.assertEqual(e.edit_distance("a", "bbbb"), 4)
        self.assertEqual(e.edit_distance("ab", "ba"), 2)
        with self.assertRaises(e.ContractError): e.decode_classes([True])
        with self.assertRaises(e.ContractError): e.decode_classes([-1])

    def test_insertion_cer_not_clipped_and_constants_valid(self):
        p, n, l = fixture(); n["predictions"][0]["text"] = "bbbb"
        self.assertEqual(e.evaluate(p, n, l)["scores"]["neural_only"]["person_macro_cer"], 1)
        self.assertTrue(e.evaluate(p, n, l)["scores"]["language_only"]["diagnostics"]["constant_output"])

    def test_reordering_predictions_does_not_change_score(self):
        p, n, l = fixture(); out = e.evaluate(p, n, l)
        n["predictions"].reverse()
        self.assertEqual(e.evaluate(p, n, l), out)

    def test_query_allowlist_and_single_person_uncertainty(self):
        p, _, _ = fixture(); q = e.query_manifest(p)
        self.assertEqual(set(q["queries"][0]), {"query_id", "neural_asset_sha256"})
        for field in ("template_text", "target_classes", "log_event_ids", "recording_subject"):
            self.assertNotIn(field, json.dumps(q))
        self.assertIsNone(e.paired_uncertainty({"a": .2}, {"a": .5}, 0, 100)["interval_95"])

    def test_modality_qualified_aliases_and_exclusions(self):
        self.assertEqual(e.canonical_person("Pinet2024Meg/S21", "MEG"), "Pinet2024Meg/S5")
        self.assertEqual(e.canonical_person("Pinet2024Eeg/018", "EEG"), "Pinet2024Eeg/018")
        for subject in ("S13", "S23", "S11122024"):
            with self.assertRaises(e.ContractError): e.canonical_person("Pinet2024Meg/" + subject, "MEG")
        with self.assertRaises(e.ContractError): e.canonical_person("Pinet2024Eeg/001", "EEG")


class RejectionControls(unittest.TestCase):
    def reject_packet(self, edit):
        p, _, _ = fixture(); edit(p)
        with self.assertRaises(e.ContractError): e.validate_packet(p)

    def reject_submission(self, edit):
        p, n, l = fixture(); edit(n)
        with self.assertRaises(e.ContractError): e.evaluate(p, n, l)

    def test_missing_extra_duplicate_and_bound_submission(self):
        for change in (lambda n: n["predictions"].pop(),
                       lambda n: n["predictions"].append(n["predictions"][0]),
                       lambda n: n["predictions"][0].update(query_id="f" * 32),
                       lambda n: n.update(packet_sha256="0" * 64),
                       lambda n: n.update(lm_id="secret-lm"),
                       lambda n: n["predictions"][0].update(text="Á"),
                       lambda n: n["predictions"][0].update(keycode=1),
                       lambda n: n["predictions"][0].update(text=None)):
            with self.subTest(change=change): self.reject_submission(change)

    def test_person_alias_and_template_leakage(self):
        def alias_leak(p):
            p["sentences"][0]["recording_subject"] = "Pinet2024Meg/S10"
            p["alignments"][0]["recording_subject"] = "Pinet2024Meg/S10"
            p["sentences"][1]["recording_subject"] = "Pinet2024Meg/S21"
            p["alignments"][1]["recording_subject"] = "Pinet2024Meg/S21"
        self.reject_packet(alias_leak)
        self.reject_packet(lambda p: p["sentences"][1].update(template_id="template0", template_text="sentence template 0"))
        self.reject_packet(lambda p: p["sentences"][1].update(template_text="Sentence  template 0!"))

    def test_grouped_template_variants_and_biological_session_aliases(self):
        p, _, _ = fixture()
        # Different near-duplicate texts can intentionally share one template family.
        p["sentences"][2]["template_id"] = p["sentences"][1]["template_id"]
        e.validate_packet(p)
        # Alias-resolved same biological visit cannot straddle calibration/query.
        p["alignments"][2]["biological_session_id"] = p["alignments"][1]["biological_session_id"]
        p["sentences"][2].update(phase="calibration", template_id="cal-family")
        with self.assertRaisesRegex(e.ContractError, "biological session crosses"):
            e.validate_packet(p)

    def test_neural_asset_identity_leakage(self):
        self.reject_packet(lambda p: p["sentences"][1].update(neural_asset_sha256=p["sentences"][0]["neural_asset_sha256"]))

    def test_session_leakage(self):
        p, _, _ = fixture()
        row = copy.deepcopy(p["sentences"][1]); row.update(query_id="e" * 32, phase="calibration", template_id="cal", template_text="cal text")
        p["sentences"].append(row)
        with self.assertRaisesRegex(e.ContractError, "session crosses"): e.validate_packet(p)

    def test_alignment_loss_keystroke_order_and_residual(self):
        self.reject_packet(lambda p: p["alignments"][1]["pairs"].append(p["alignments"][1]["pairs"][0]))
        self.reject_packet(lambda p: p["alignments"][1]["neural_events"].append({"id": "extra", "time_s": 12}))
        self.reject_packet(lambda p: p["alignments"][1].update(log_to_neural_offset_s=20))
        self.reject_packet(lambda p: p["alignments"][1].update(max_residual_s=float("nan")))
        self.reject_packet(lambda p: p["sentences"][2]["log_event_ids"].reverse())
        self.reject_packet(lambda p: p["sentences"][1].update(log_event_ids=["missing"]))
        self.reject_packet(lambda p: p["sentences"][1].update(target_classes=[]))

    def test_documented_losses_are_accounted_not_silently_dropped(self):
        p, _, _ = fixture(); a = p["alignments"][1]
        a["log_events"].append({"id": "lost", "time_s": 4})
        a["excluded_log_events"].append({"id": "lost", "reason": "ambiguous DTW mapping"})
        _, audit = e.validate_packet(p)
        self.assertEqual(audit[("Pinet2024Meg/S1", "session1")]["excluded_log_events"], 1)

    def test_calibration_and_v1_target_gates(self):
        self.reject_packet(lambda p: p["protocol"].update(calibration_sentences_per_person=1, calibration_keystrokes_per_person=1))
        self.reject_packet(lambda p: p.update(data_commit="V2"))
        self.reject_packet(lambda p: p.update(target_definition="intended_sentence"))
        self.reject_packet(lambda p: p.update(modality="combined"))

    def test_fixed_lm_separate_and_matching(self):
        p, _, _ = fixture(); p["protocol"]["fixed_lm_id"] = "frozen-lm"
        n = submission(p, "neural_only", ["b", "aaaaaaaaa", "aa"])
        l = submission(p, "language_only", ["", "", ""]); l["lm_id"] = "frozen-lm"
        f = submission(p, "fixed_lm", ["a", "aaaaaaaaa", "aa"]); f["lm_id"] = "frozen-lm"
        out = e.evaluate(p, n, l, f)
        self.assertEqual(out["scores"]["neural_only"]["person_macro_cer"], .25)
        self.assertEqual(out["scores"]["fixed_lm"]["person_macro_cer"], 0)
        l["lm_id"] = "different"
        with self.assertRaises(e.ContractError): e.evaluate(p, n, l, f)

    def test_cli_success_and_duplicate_json_key_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p, n, l = fixture(); paths = []
            for name, data in (("packet", p), ("neural", n), ("language", l)):
                path = Path(d) / (name + ".json"); path.write_text(json.dumps(data)); paths.append(str(path))
            result = subprocess.run([sys.executable, "-B", str(ROOT / "evaluator.py"), "evaluate", *paths], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["scores"]["neural_only"]["person_macro_cer"], .25)
            Path(paths[0]).write_text('{"schema_version":1,"schema_version":1}')
            result = subprocess.run([sys.executable, "-B", str(ROOT / "evaluator.py"), "queries", paths[0]], text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__": unittest.main()
