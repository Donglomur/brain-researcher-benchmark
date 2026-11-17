"""Tiny generated software controls. No authentic data or model calls."""
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).with_name("score_panel.py")
SPEC = importlib.util.spec_from_file_location("p300_panel", MODULE)
panel = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(panel)


def fixture():
    roster = {"schema": "physiop300_operator_roster_v1", "subjects": []}
    predictions = {"schema": "physiop300_predictions_v1",
                   "repetitions": ["declared-a", "declared-b", "declared-c"], "cells": []}
    for sid in panel.SUBJECTS:
        events = [{"event_id": f"s{sid}:rec-{i // 2}:event-{i}",
                   "recording_id": f"s{sid}:rec-{i // 2}", "target": y}
                  for i, y in enumerate([0, 0, 1, 1])]
        roster["subjects"].append({"subject_id": sid, "events": events})
        for repetition, method in itertools.product(predictions["repetitions"], panel.METHODS):
            probabilities = [0.1, 0.2, 0.8, 0.9] if method == "candidate" else [0.9, 0.8, 0.2, 0.1]
            predictions["cells"].append({"subject_id": sid, "repetition": repetition,
                "method": method, "probabilities": [{"event_id": e["event_id"], "p_target": p}
                    for e, p in zip(events, probabilities)]})
    return roster, predictions


class MetricTests(unittest.TestCase):
    def test_rank_auc_matches_independent_all_pairs_oracle_with_ties(self):
        targets = [0, 1, 0, 1]
        for scores in itertools.product((0.0, 0.5, 1.0), repeat=4):
            positives = [p for y, p in zip(targets, scores) if y]
            negatives = [p for y, p in zip(targets, scores) if not y]
            expected = sum(float(p > n) + 0.5 * (p == n)
                           for p, n in itertools.product(positives, negatives)) / 4
            self.assertEqual(panel.binary_metrics(targets, scores)["auroc"], expected)

    def test_all_metrics_hand_computed_imbalanced_support(self):
        result = panel.binary_metrics([0, 0, 0, 1], [0.1, 0.4, 0.8, 0.9])
        self.assertEqual(result["auroc"], 1.0)
        self.assertAlmostEqual(result["threshold_metrics"]["ge"]["balanced_accuracy"], 5 / 6)
        self.assertEqual(result["threshold_metrics"]["ge"]["cohen_kappa"], 0.5)
        self.assertEqual(result["threshold_metrics"]["ge"]["confusion_true_by_predicted"], [[2, 1], [0, 1]])

    def test_exact_threshold_tie_does_not_assume_dependency_parity(self):
        result = panel.binary_metrics([0, 1], [0.1, 0.5])
        self.assertEqual(result["threshold_ties"], 1)
        self.assertEqual(result["threshold_metrics"]["ge"]["balanced_accuracy"], 1)
        self.assertEqual(result["threshold_metrics"]["gt"]["balanced_accuracy"], 0.5)
        self.assertEqual(result["threshold_metrics"]["ge"]["cohen_kappa"], 1)
        self.assertEqual(result["threshold_metrics"]["gt"]["cohen_kappa"], 0)

    def test_missing_class_is_unavailable_not_zero(self):
        for targets in ([0, 0], [1, 1]):
            result = panel.binary_metrics(targets, [0.2, 0.7])
            self.assertIsNone(result["auroc"])
            self.assertIsNone(result["threshold_metrics"]["ge"]["balanced_accuracy"])

    def test_invalid_probabilities_and_targets(self):
        for bad in (float("nan"), float("inf"), -0.1, 1.01, 10 ** 400, True, "0.5", None):
            with self.subTest(bad=bad), self.assertRaises(panel.PanelError):
                panel.binary_metrics([0, 1], [0.2, bad])
        for bad in (True, 2, 1.0, None):
            with self.subTest(bad=bad), self.assertRaises(panel.PanelError):
                panel.binary_metrics([0, bad], [0.2, 0.8])
        with self.assertRaises(panel.PanelError):
            panel.binary_metrics([0, 1], [0.2])


class CompletePanelTests(unittest.TestCase):
    def test_complete_panel_has_all_controls_and_paired_deltas_without_aggregate(self):
        result = panel.score_panel(*fixture())
        self.assertEqual(len(result["cells"]), 135)
        self.assertEqual(len(result["candidate_minus_reference"]), 108)
        self.assertEqual(result["undefined_cells"], 0)
        self.assertIsNone(result["source_panel_aggregate"])
        self.assertFalse(result["paper_improvement_established"])
        for delta in result["candidate_minus_reference"]:
            self.assertEqual(delta["auroc"], 1)
            self.assertEqual(delta["threshold_metrics"]["ge"]["cohen_kappa"], 2)

    def test_event_pairing_is_order_independent_and_keeps_all_recordings(self):
        roster, predictions = fixture()
        expected = panel.score_panel(roster, predictions)
        roster["subjects"].reverse()
        predictions["cells"].reverse()
        for subject in roster["subjects"]:
            subject["events"].reverse()
        for cell in predictions["cells"]:
            cell["probabilities"].reverse()
        self.assertEqual(panel.score_panel(roster, predictions), expected)
        self.assertTrue(all(s["recordings"] == 2 for s in expected["support"]))

    def test_no_available_method_subject_or_repetition_subset(self):
        for missing in ("LaBraM", "candidate", "EEGPT", "BENDR", "BIOT"):
            roster, predictions = fixture()
            predictions["cells"] = [c for c in predictions["cells"] if c["method"] != missing]
            with self.subTest(missing=missing), self.assertRaises(panel.PanelError):
                panel.score_panel(roster, predictions)
        roster, predictions = fixture()
        roster["subjects"].pop(0)  # Converter's omission of s01 cannot shrink this panel.
        with self.assertRaises(panel.PanelError):
            panel.score_panel(roster, predictions)
        roster, predictions = fixture()
        predictions["repetitions"].pop()
        with self.assertRaises(panel.PanelError):
            panel.score_panel(roster, predictions)

    def test_missing_extra_duplicate_and_cross_subject_events_rejected(self):
        for mode in ("missing", "extra", "duplicate", "cross-subject"):
            roster, predictions = fixture()
            rows = predictions["cells"][0]["probabilities"]
            if mode == "missing":
                rows.pop()
            elif mode == "extra":
                rows.append({"event_id": "unknown", "p_target": 0.5})
            elif mode == "duplicate":
                rows.append(copy.deepcopy(rows[0]))
            else:
                rows[0]["event_id"] = roster["subjects"][1]["events"][0]["event_id"]
            with self.subTest(mode=mode), self.assertRaises(panel.PanelError):
                panel.score_panel(roster, predictions)

    def test_duplicate_cells_global_events_and_cross_subject_recording_rejected(self):
        for mode in ("cell", "event", "recording"):
            roster, predictions = fixture()
            if mode == "cell":
                predictions["cells"].append(copy.deepcopy(predictions["cells"][0]))
            else:
                key = "event_id" if mode == "event" else "recording_id"
                roster["subjects"][1]["events"][0][key] = roster["subjects"][0]["events"][0][key]
            with self.subTest(mode=mode), self.assertRaises(panel.PanelError):
                panel.score_panel(roster, predictions)

    def test_single_class_subject_preserves_failed_cells_and_pairings(self):
        roster, predictions = fixture()
        for event in roster["subjects"][0]["events"]:
            event["target"] = 0
        result = panel.score_panel(roster, predictions)
        self.assertEqual(result["undefined_cells"], 15)
        self.assertEqual(len(result["cells"]), 135)
        self.assertEqual(sum(d["auroc"] is None for d in result["candidate_minus_reference"]), 12)

    def test_predictions_cannot_supply_or_override_targets(self):
        roster, predictions = fixture()
        predictions["cells"][0]["probabilities"][0]["target"] = 0
        with self.assertRaises(panel.PanelError):
            panel.score_panel(roster, predictions)

    def test_json_rejects_overwritten_members_and_nonfinite_literals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for document in ('{"a":1,"a":2}', '{"p":NaN}', '{"p":Infinity}'):
                path.write_text(document)
                with self.subTest(document=document), self.assertRaises(panel.PanelError):
                    panel.load_json(path)
            path.write_text(json.dumps(fixture()[0]))
            self.assertEqual(panel.load_json(path), fixture()[0])

    def test_cli_rejects_invalid_utf8_as_document_error(self):
        with tempfile.TemporaryDirectory() as directory:
            roster_path = Path(directory) / "roster.json"
            predictions_path = Path(directory) / "predictions.json"
            for malformed in (roster_path, predictions_path):
                roster, predictions = fixture()
                roster_path.write_text(json.dumps(roster))
                predictions_path.write_text(json.dumps(predictions))
                malformed.write_bytes(b"\xff\xfeinvalid-json")
                completed = subprocess.run(
                    [sys.executable, "-I", "-B", str(MODULE),
                     "--operator-roster", str(roster_path), "--predictions", str(predictions_path)],
                    capture_output=True, text=True, timeout=10)
                with self.subTest(input=malformed.name):
                    self.assertEqual(completed.returncode, 2)
                    self.assertEqual(completed.stdout, "")
                    self.assertIn("Panel rejected:", completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
