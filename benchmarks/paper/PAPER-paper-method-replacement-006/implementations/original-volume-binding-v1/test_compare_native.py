"""Generated paired Volume controls; no native arrays, fitting or inference."""
import copy
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import score_native as s
from test_score_native import generated_panel

b = s.b


def generated_pair():
    binding, native = generated_panel()
    pairing = {"schema": "original-volume-pairing/v1",
               "binding_sha256": binding["binding_sha256"], "protocol_sha256": "a" * 64,
               "author_comparator": "pretrained_popt_brainbert",
               "methods": {"author": {"method_id": "generated-author", "implementation_sha256": "b" * 64},
                           "candidate": {"method_id": "generated-candidate", "implementation_sha256": "c" * 64}},
               "runs": {cell: {"pair_id": "pair-" + cell, "seed": 42,
                   "run_ids": {role: role + "-" + cell for role in ("author", "candidate")}}
                   for cell in native["runs"]}}
    exports = []
    for role in ("author", "candidate"):
        exports.append({"schema": "original-volume-paired-export/v1",
            "pairing_sha256": b.canonical_sha(pairing), "protocol_sha256": pairing["protocol_sha256"],
            "role": role, **pairing["methods"][role],
            "run_provenance": {cell: {"pair_id": row["pair_id"], "seed": row["seed"],
                                      "run_id": row["run_ids"][role]} for cell, row in pairing["runs"].items()},
            "native": copy.deepcopy(native)})
    return binding, pairing, *exports


def auc_oracle(run):
    positive = [p for y, p in zip(run["labels"], run["predicts"]) if y == 1]
    negative = [p for y, p in zip(run["labels"], run["predicts"]) if y == 0]
    return sum((p > n) + 0.5 * (p == n) for p in positive for n in negative) / (len(positive) * len(negative))


class PairedScoringControls(unittest.TestCase):
    def test_complete_panel_oracle_and_equal_subject_contrasts(self):
        binding, pairing, author, candidate = generated_pair()
        expected = {}
        for ordinal, subject in enumerate(b.TRIALS):
            for count in b.COUNTS:
                cell = f"{subject}/{count}"
                for offset, export in ((0, author), (1, candidate)):
                    run = export["native"]["runs"][cell]
                    run["predicts"] = [((i * 3 + ordinal + count + offset) % 7) / 8
                                       for i in range(len(run["labels"]))]
                expected[cell] = auc_oracle(candidate["native"]["runs"][cell]) - auc_oracle(author["native"]["runs"][cell])
        report = s.compare_native(binding, pairing, author, candidate)
        self.assertEqual(len(report["per_subject_count"]), 49)
        self.assertEqual(len(report["by_electrode_count"]), 7)
        for row in report["per_subject_count"]:
            self.assertEqual(row["candidate_minus_author_roc_auc"], expected[f'{row["subject"]}/{row["electrode_count"]}'])
        for row in report["by_electrode_count"]:
            self.assertEqual(row["n_subjects"], 7)
            self.assertEqual(row["subject_mean_candidate_minus_author_roc_auc"],
                             math.fsum(expected[f'{subject}/{row["electrode_count"]}'] for subject in b.TRIALS) / 7)
        self.assertEqual(report["method_scores"]["author"], s.score_native(binding, author["native"]))
        self.assertEqual(report["method_scores"]["candidate"], s.score_native(binding, candidate["native"]))
        self.assertEqual(report["primary_electrode_count"], 90)
        self.assertEqual(report["scientific_qualification"], "unknown")
        for key in ("full_control_panel_qualified", "reproduction_qualified", "improvement_qualified"):
            self.assertIs(report[key], False)

    def test_equality_and_reversing_predictions_reverse_contrasts(self):
        binding, pairing, author, candidate = generated_pair()
        equal = s.compare_native(binding, pairing, author, candidate)
        self.assertTrue(all(row["candidate_minus_author_roc_auc"] == 0 for row in equal["per_subject_count"]))
        for run in author["native"]["runs"].values():
            run["predicts"] = [0.5] * len(run["labels"])
        positive = s.compare_native(binding, pairing, author, candidate)
        author["native"], candidate["native"] = candidate["native"], author["native"]
        negative = s.compare_native(binding, pairing, author, candidate)
        for first, second in zip(positive["per_subject_count"], negative["per_subject_count"]):
            self.assertEqual(first["candidate_minus_author_roc_auc"], 0.5)
            self.assertEqual(second["candidate_minus_author_roc_auc"], -0.5)

    def test_operator_roles_protocol_and_identity_rejected_before_scoring(self):
        binding, pairing, author, candidate = generated_pair()
        mutations = [lambda p, a, c: p.update(author_comparator="linear_brainbert"),
                     lambda p, a, c: p["methods"].update(candidate=p["methods"]["author"]),
                     lambda p, a, c: p.update(protocol_sha256="not-a-digest"),
                     lambda p, a, c: p.update(binding_sha256="d" * 64),
                     lambda p, a, c: c.update(role="author"),
                     lambda p, a, c: a.update(method_id="generated-candidate"),
                     lambda p, a, c: c.update(implementation_sha256="e" * 64),
                     lambda p, a, c: c.update(protocol_sha256="f" * 64),
                     lambda p, a, c: c.update(pairing_sha256="0" * 64)]
        for mutate in mutations:
            p, a, c = copy.deepcopy((pairing, author, candidate))
            mutate(p, a, c)
            with self.subTest(mutate=mutate), patch.object(s, "score_native", side_effect=AssertionError("must not score")):
                with self.assertRaises(b.BindingError):
                    s.compare_native(binding, p, a, c)
        with self.assertRaisesRegex(b.BindingError, "role"):
            s.compare_native(binding, pairing, candidate, author)

    def test_matched_run_provenance_rejected_before_scoring(self):
        binding, pairing, author, candidate = generated_pair()
        for field, value in (("seed", 43), ("seed", True), ("pair_id", "other"), ("run_id", "author-sub_1/1")):
            bad = copy.deepcopy(candidate)
            bad["run_provenance"]["sub_1/1"][field] = value
            with self.subTest(field=field, value=value), patch.object(s, "score_native", side_effect=AssertionError("must not score")):
                with self.assertRaisesRegex(b.BindingError, "matched run"):
                    s.compare_native(binding, pairing, author, bad)
        for mutate in (lambda p: p["runs"].pop("sub_1/1"),
                       lambda p: p["runs"].update(extra=p["runs"]["sub_1/1"]),
                       lambda p: p["runs"]["sub_2/1"].update(pair_id=p["runs"]["sub_1/1"]["pair_id"]),
                       lambda p: p["runs"]["sub_1/1"]["run_ids"].update(candidate="author-sub_1/1"),
                       lambda p: p["runs"]["sub_1/1"].update(seed=False)):
            bad = copy.deepcopy(pairing)
            mutate(bad)
            with self.assertRaises(b.BindingError):
                s.compare_native(binding, bad, author, candidate)

    def test_native_support_rejected_before_either_method_is_scored(self):
        binding, pairing, author, candidate = generated_pair()
        mutations = [lambda n: n.update(binding_sha256="a" * 64),
                     lambda n: n["runs"].pop("sub_10/90"),
                     lambda n: n["runs"].update(extra=n["runs"]["sub_1/1"]),
                     lambda n: n["runs"]["sub_1/1"].update(manifest_indices=[36, 37, 38, 39]),
                     lambda n: n["runs"]["sub_1/10"].update(channels=list(reversed(n["runs"]["sub_1/10"]["channels"]))),
                     lambda n: n["runs"]["sub_1/1"].update(labels=[0, 0, 0, 0])]
        for role in ("author", "candidate"):
            for mutate in mutations:
                a, c = copy.deepcopy((author, candidate))
                mutate((a if role == "author" else c)["native"])
                with self.subTest(role=role, mutate=mutate), patch.object(s, "score_native", side_effect=AssertionError("must not score")):
                    with self.assertRaises(b.BindingError):
                        s.compare_native(binding, pairing, a, c)

    def test_native_orientations_tiny_probabilities_and_ties(self):
        binding, pairing, author, candidate = generated_pair()
        tiny = 2.0 ** -60
        for run in candidate["native"]["runs"].values():
            run["label2idx"] = {key: 1 - value for key, value in run["label2idx"].items()}
            run["labels"] = [1 - label for label in run["labels"]]
            run["predicts"] = [2 * tiny if label else tiny for label in run["labels"]]
        report = s.compare_native(binding, pairing, author, candidate)
        self.assertTrue(all(row["candidate_minus_author_roc_auc"] == 0 for row in report["per_subject_count"]))
        for run in candidate["native"]["runs"].values():
            run["predicts"] = [0.5] * len(run["labels"])
        report = s.compare_native(binding, pairing, author, candidate)
        self.assertTrue(all(row["candidate_minus_author_roc_auc"] == -0.5 for row in report["per_subject_count"]))
        self.assertTrue(all(row["f1_native_index1"] == 0 for row in report["method_scores"]["candidate"]["per_subject_count"]))

    def test_cli_pair_roundtrip_flags_and_duplicate_json(self):
        binding, pairing, author, candidate = generated_pair()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, value in (("binding", binding), ("pairing", pairing), ("author", author), ("candidate", candidate)):
                (root / (name + ".json")).write_text(json.dumps(value))
            base = ["score_native.py", str(root / "binding.json"), str(root / "author.json"), str(root / "score.json")]
            flags = ["--pairing", str(root / "pairing.json"), "--candidate", str(root / "candidate.json")]
            with patch.object(sys, "argv", base + flags):
                s.main()
            self.assertEqual(json.loads((root / "score.json").read_text()), s.compare_native(binding, pairing, author, candidate))
            for one_flag in (flags[:2], flags[2:]):
                with patch.object(sys, "argv", base + one_flag), patch("sys.stderr", io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        s.main()
                    self.assertEqual(raised.exception.code, 2)
            (root / "candidate.json").write_text('{"role":"candidate","role":"author"}')
            with patch.object(sys, "argv", base + flags), self.assertRaisesRegex(b.BindingError, "duplicate JSON"):
                s.main()


if __name__ == "__main__":
    unittest.main(verbosity=2)
