"""Generated full-support metadata controls; no waveform bank, gold or model."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural084_collection_bridge", HERE / "panel.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
SOURCE_ROOT = Path(os.environ.get("NEURAL084_SOURCE_IMPLEMENTATIONS", str(HERE.parent)))
VIEWER_SOURCE = Path(os.environ.get("NEURAL084_VIEWER_SOURCE", str(HERE.parent / "typed-waveform-v1/viewer.py")))


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode("ascii")


def identity(person, position):
    return f"{person * 100000 + position:064x}"


def training_raw(held):
    rows = []
    for person in range(1, 55):
        if person == held:
            continue
        position = 0
        for session in (1, 2):
            for phase in ("train", "test"):
                for label in (1, 2, 3, 4):
                    for _ in range(25):
                        rows.append({"id": identity(person, position), "label": label,
                                     "person": person, "session": session, "phase": phase})
                        position += 1
    return canonical({"schema": "neural084_training_v1", "rows": rows})


def no_waveforms(_):
    raise AssertionError("generated collection control must not access any waveform")


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folds = []
        for person in range(1, 55):
            raw = training_raw(person)
            descriptor = lambda path: {"path": path, "bytes": 1, "sha256": "e" * 64}
            cls.folds.append({"schema": "neural084_fold_v1", "generation": "generated-full54-software-only",
                              "fold": f"fold{person:03d}",
                              "ids": [identity(person, i) for i in range(400)],
                              "classes": [1, 2, 3, 4], "training": descriptor("training.npy"),
                              "queries": descriptor("queries.npy"),
                              "training_metadata": {"path": "training.json", "bytes": len(raw),
                                                     "sha256": hashlib.sha256(raw).hexdigest()}})
        # Deliberately do not retain54 copies of full donor metadata or arrays.
        cls.raw1 = training_raw(1)

    def make(self, folds=None, **limits):
        return bridge.Panel(self.folds if folds is None else folds,
                            max_requests=limits.get("max_requests", 100000),
                            max_capture_bytes=limits.get("max_capture_bytes", bridge.CAPTURE_CAP),
                            viewer_source=VIEWER_SOURCE, source_root=SOURCE_ROOT)

    def call(self, panel, action, **fields):
        return json.loads(panel.handle(canonical({"action": action, **fields})))

    def close_fold(self, panel, person):
        panel.open_next(self.raw1 if person == 1 else training_raw(person), no_waveforms, no_waveforms)
        opened = self.call(panel, "begin_queries")
        self.assertEqual(opened["id"], identity(person, 0))
        for i in range(400):
            self.call(panel, "answer", id=identity(person, i), scores=[-3, 0, 0, 9])
        return self.call(panel, "finish")

    def test_full54_outputs_pass_preserved_frozen_and_scorer_admission(self):
        panel = self.make()
        instances = set()
        # Keep objects solely to establish distinct identity without id reuse;
        # each closes/retains only its small400-response metadata, not training.
        closed_instances = []
        for person in range(1, 55):
            panel.open_next(self.raw1 if person == 1 else training_raw(person), no_waveforms, no_waveforms)
            instances.add(id(panel._active))
            closed_instances.append(panel._active)
            self.assertEqual(self.call(panel, "information")["stage"], "training")
            self.call(panel, "begin_queries")
            for i in range(400):
                self.call(panel, "answer", id=identity(person, i), scores=[-3, 0, 0, 9])
            ack = self.call(panel, "finish")
            self.assertEqual(set(ack), {"schema", "fold", "closed_folds", "required_folds"})
            self.assertEqual(ack["closed_folds"], person)
            self.assertNotIn("predictions", ack)
            with self.assertRaisesRegex(ValueError, "complete54"):
                panel.candidate_prediction(f"fold{person:03d}")
        self.assertEqual(len(instances), 54)
        receipt = json.loads(panel.finish_collection())
        self.assertEqual(receipt["query_count"], 21600)
        self.assertEqual(receipt["fold_count"], 54)
        self.assertFalse(receipt["native_programme_execution_receipt"])
        self.assertFalse(receipt["scientific_qualified"])
        scorer_spec = importlib.util.spec_from_file_location("original_neural084_scorer", SOURCE_ROOT / "full-cohort-scoring-v1/score.py")
        scorer = importlib.util.module_from_spec(scorer_spec)
        scorer_spec.loader.exec_module(scorer)
        total = 0
        for person, fold in enumerate(self.folds, 1):
            raw = panel.candidate_prediction(fold["fold"])
            parsed = panel._contracts.prediction(raw, fold)
            winners = scorer.prediction(raw, fold["generation"], fold["fold"], tuple(fold["ids"]))
            self.assertEqual(winners, (4,) * 400)
            total += len(parsed["predictions"])
            self.assertEqual(receipt["folds"][person - 1]["prediction"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(total, 21600)
        with self.assertRaisesRegex(ValueError, "immutable"):
            panel.open_next(self.raw1, no_waveforms, no_waveforms)
        with self.assertRaisesRegex(ValueError, "exact original"):
            panel.candidate_prediction("fold055")

    def test_incomplete_panels_cannot_export_or_skip_active_fold(self):
        panel = self.make()
        with self.assertRaisesRegex(ValueError, "all54"):
            panel.finish_collection()
        panel.open_next(self.raw1, no_waveforms, no_waveforms)
        with self.assertRaisesRegex(ValueError, "finish active"):
            panel.open_next(training_raw(2), no_waveforms, no_waveforms)
        with self.assertRaisesRegex(ValueError, "400"):
            self.call(panel, "finish")
        with self.assertRaisesRegex(ValueError, "complete54"):
            panel.candidate_prediction("fold001")

    def test_header_order_generation_and_crossfold_identity_rejected(self):
        variants = []
        missing = copy.deepcopy(self.folds); missing.pop(); variants.append(missing)
        wrong_order = copy.deepcopy(self.folds); wrong_order[0], wrong_order[1] = wrong_order[1], wrong_order[0]; variants.append(wrong_order)
        same_ids = copy.deepcopy(self.folds); same_ids[1]["ids"] = list(same_ids[0]["ids"]); variants.append(same_ids)
        generation = copy.deepcopy(self.folds); generation[53]["generation"] = "other"; variants.append(generation)
        incomplete = copy.deepcopy(self.folds); incomplete[53]["ids"].pop(); variants.append(incomplete)
        for records in variants:
            with self.subTest(records=len(records)), self.assertRaises(ValueError):
                self.make(records)

    def test_training_bytes_identity_failure_is_terminal(self):
        panel = self.make()
        with self.assertRaisesRegex(ValueError, "training metadata identity"):
            panel.open_next(self.raw1 + b" ", no_waveforms, no_waveforms)
        with self.assertRaisesRegex(ValueError, "failed collection"):
            panel.open_next(self.raw1, no_waveforms, no_waveforms)
        with self.assertRaisesRegex(ValueError, "complete54"):
            panel.candidate_prediction("fold001")

    def test_full_donor_support_still_checked_after_byte_identity(self):
        malformed = json.loads(self.raw1)
        malformed["rows"][0]["person"] = 1
        raw = canonical(malformed)
        folds = copy.deepcopy(self.folds)
        folds[0]["training_metadata"].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        panel = self.make(folds)
        with self.assertRaisesRegex(ValueError, "exclude held"):
            panel.open_next(raw, no_waveforms, no_waveforms)
        with self.assertRaisesRegex(ValueError, "failed collection"):
            panel.finish_collection()

    def test_original_phase_gate_and_first_final_answer_preserved(self):
        panel = self.make()
        panel.open_next(self.raw1, no_waveforms, no_waveforms)
        with self.assertRaisesRegex(ValueError, "unanswered"):
            self.call(panel, "answer", id=identity(1, 0), scores=[0] * 4)
        self.call(panel, "begin_queries")
        self.call(panel, "answer", id=identity(1, 0), scores=[0] * 4)
        with self.assertRaisesRegex(ValueError, "first-final"):
            self.call(panel, "answer", id=identity(1, 0), scores=[1, 0, 0, 0])
        with self.assertRaisesRegex(ValueError, "retired"):
            self.call(panel, "training", index=0, channels=["P7"], start=0, stop=2)

    def test_capture_budget_failure_retains_no_export_or_resume(self):
        panel = self.make(max_capture_bytes=1)
        with self.assertRaisesRegex(ValueError, "capture allowance"):
            self.close_fold(panel, 1)
        with self.assertRaisesRegex(ValueError, "failed collection"):
            panel.open_next(self.raw1, no_waveforms, no_waveforms)
        with self.assertRaisesRegex(ValueError, "complete54"):
            panel.candidate_prediction("fold001")

    def test_request_budget_and_input_snapshot(self):
        folds = copy.deepcopy(self.folds)
        panel = self.make(folds, max_requests=2)
        folds[0]["ids"][0] = "f" * 64
        panel.open_next(self.raw1, no_waveforms, no_waveforms)
        self.assertEqual(self.call(panel, "begin_queries")["id"], identity(1, 0))
        with self.assertRaisesRegex(ValueError, "allowance exhausted"):
            self.call(panel, "answer", id=identity(1, 0), scores=[0] * 4)


if __name__ == "__main__":
    unittest.main()
