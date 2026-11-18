"""Generated controls for the no-neural comparator; no authentic records."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from core import ContractError, canonical, digest, score, validate_submission
from sequence_prior import fit_prior, predict_prior

HERE = Path(__file__).resolve().parent


def bind(public, labels):
    body = canonical(labels) + b"\n"
    public["training_labels"] = {
        "path": "training_labels.json", "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    public["packet_id"] = digest({k: v for k, v in public.items() if k != "packet_id"})
    return body


def panel():
    sessions = [{"session_id": "session-%03d" % i,
                 "role": "train" if i <= 27 else "development" if i <= 36 else "query"}
                for i in range(1, 46)]
    cases = []
    labels = {"schema": "neural013-training-labels-v1", "labels": []}
    for i, row in enumerate(sessions):
        key = digest(["generated-prior-control", i])
        cases.append(dict(case_id=key, **row, n_time_steps=i + 1,
                          features={"path": "features/" + key + ".npy", "bytes": 200,
                                    "sha256": "a" * 64}))
        if row["role"] != "query":
            labels["labels"].append({"case_id": key, "tokens": ["AA", "|"] if i < 20 else ["B"]})
    public = {"schema": "neural013-public-v1", "protocol_id": "neural013-chronological-v1",
              "sessions": sessions, "cases": cases}
    return public, labels, bind(public, labels)


class SequencePriorTests(unittest.TestCase):
    def test_modal_complete_sequence_and_boundary_are_preserved(self):
        public, labels, body = panel()
        model = fit_prior(public, body)
        self.assertEqual(model["tokens"], ["AA", "|"])
        self.assertEqual(model["training_cases"], 27)
        self.assertEqual(model["chosen_training_count"], 20)
        self.assertEqual(model["unique_training_sequences"], 2)

    def test_development_labels_do_not_select_prior(self):
        public, labels, body = panel()
        original = fit_prior(public, body)
        for row in labels["labels"][27:]:
            row["tokens"] = ["ZH"] * 20
        changed = fit_prior(public, bind(public, labels))
        for key in ("tokens", "chosen_training_count", "training_sequence_counts_sha256"):
            self.assertEqual(original[key], changed[key])

    def test_tie_break_and_row_order_are_deterministic(self):
        public, labels, body = panel()
        for i, row in enumerate(labels["labels"][:27]):
            row["tokens"] = ["B"] if i < 10 else ["AA"] if i < 20 else ["ZH"]
        first = fit_prior(public, bind(public, labels))
        self.assertEqual(first["tokens"], ["AA"])
        labels["labels"].reverse()
        second = fit_prior(public, bind(public, labels))
        self.assertEqual(first["tokens"], second["tokens"])
        self.assertEqual(first["training_sequence_counts_sha256"], second["training_sequence_counts_sha256"])

    def test_byte_binding_precedes_label_parsing(self):
        public, labels, body = panel()
        with patch("sequence_prior.parse_json", side_effect=AssertionError("must not parse")):
            with self.assertRaises(ContractError):
                fit_prior(public, body + b" ")

    def test_missing_duplicate_query_unknown_and_empty_labels_fail(self):
        for kind in ("missing", "duplicate", "query", "unknown", "empty", "extra"):
            public, labels, body = panel()
            if kind == "missing": labels["labels"].pop()
            elif kind == "duplicate": labels["labels"][1] = copy.deepcopy(labels["labels"][0])
            elif kind == "query": labels["labels"][0]["case_id"] = public["cases"][-1]["case_id"]
            elif kind == "unknown": labels["labels"][0]["case_id"] = "f" * 64
            elif kind == "empty": labels["labels"][0]["tokens"] = []
            else: labels["labels"][0]["transcript"] = "not allowed"
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                fit_prior(public, bind(public, labels))

    def test_every_query_is_scored_by_existing_endpoint(self):
        public, labels, body = panel()
        model = fit_prior(public, body)
        prediction = predict_prior(public, model, model["model_id"])
        self.assertEqual(len(prediction["predictions"]), 9)
        private = {"schema": "neural013-targets-v1", "packet_id": public["packet_id"],
                   "targets": [{"case_id": r["case_id"], "tokens": ["AA", "|"]}
                               for r in public["cases"] if r["role"] == "query" ]}
        result = score(public, prediction, lambda: private)
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["query_sessions"], 9)
        self.assertEqual(result["participant_count"], 1)

    def test_model_mutation_or_unfrozen_id_fails(self):
        public, labels, body = panel()
        model = fit_prior(public, body)
        frozen = model["model_id"]
        for field, value in (("tokens", ["B"]), ("training_cases", True),
                             ("method", "different"), ("packet_id", "f" * 64)):
            changed = copy.deepcopy(model)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ContractError):
                predict_prior(public, changed, frozen)
        with self.assertRaises(ContractError):
            predict_prior(public, model, "f" * 64)

    def test_feature_durations_and_labels_are_not_query_operands(self):
        public, labels, body = panel()
        model = fit_prior(public, body)
        # No feature arrays or private target file exist anywhere in this test.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "public.json").write_bytes(canonical(public))
            (root / "model.json").write_bytes(canonical(model))
            command = [sys.executable, "-B", str(HERE / "sequence_prior.py"), "predict",
                       "--public", str(root / "public.json"), "--model", str(root / "model.json"),
                       "--expected-model-id", model["model_id"], "--output", str(root / "result.json")]
            out = subprocess.run(command, capture_output=True, text=True, timeout=5)
            self.assertEqual(out.returncode, 0, out.stderr[:1000])
            result = json.loads((root / "result.json").read_text())
            validate_submission(public, result)
            self.assertEqual({tuple(r["tokens"]) for r in result["predictions"]}, {("AA", "|")})
            # Exclusive output prevents replacing an already collected result.
            out = subprocess.run(command, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(out.returncode, 0)

    def test_fit_cli_binds_allowed_labels(self):
        public, labels, body = panel()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "public.json").write_bytes(canonical(public))
            (root / "labels.json").write_bytes(body)
            out = subprocess.run([sys.executable, "-B", str(HERE / "sequence_prior.py"), "fit",
                                  "--public", str(root / "public.json"), "--labels", str(root / "labels.json"),
                                  "--output", str(root / "model.json")],
                                 capture_output=True, text=True, timeout=5)
            self.assertEqual(out.returncode, 0, out.stderr[:1000])
            self.assertEqual(json.loads((root / "model.json").read_text()), fit_prior(public, body))


if __name__ == "__main__":
    unittest.main(verbosity=2)
