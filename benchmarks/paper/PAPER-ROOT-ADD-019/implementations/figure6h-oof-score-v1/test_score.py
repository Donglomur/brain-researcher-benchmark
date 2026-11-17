#!/usr/bin/env python3
"""Invented software controls only. Run through the shared lightweight pool."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fig6h_score", HERE / "score.py")
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)


def fixture():
    sessions = []
    for i in range(18):
        n = 40 if i == 0 else 20
        sessions.append({"session_id": "invented_session_%02d" % i,
                         "rat_id": "invented_rat_%d" % (i % 8), "unit_count": 5,
                         "trial_ids": ["invented_trial_%d" % j for j in range(n)],
                         "folds": [j % 10 + 1 for j in range(n)],
                         "labels": [j % 2 for j in range(n)]})
    manifest = {"schema": "ach_fig6h_oof_manifest_v1", "task": score.TASK,
                "preparation_sha256": "a" * 64, "sessions": sessions}
    author = {"schema": "ach_fig6h_oof_predictions_v1", "role": "author",
              "manifest_sha256": score.digest(manifest), "program_sha256": "b" * 64,
              "setting_ids": score.AUTHOR_SETTINGS[:], "lambdas": score.LAMBDAS[:], "sessions": []}
    candidate = {"schema": "ach_fig6h_oof_predictions_v1", "role": "candidate",
                 "manifest_sha256": score.digest(manifest), "program_sha256": "c" * 64,
                 "setting_ids": ["frozen_architecture_%d" % i for i in range(11)], "sessions": []}
    for i, session in enumerate(sessions):
        n = len(session["labels"])
        for bundle in (author, candidate):
            best_errors = n // 2 if bundle is author else (0 if i else n)
            errors = [n] * 11
            errors[2] = errors[7] = best_errors
            record = {"session_id": session["session_id"], "trial_ids": session["trial_ids"][:],
                      "folds": session["folds"][:],
                      "predictions": [[1 - y if j < k else y for j, y in enumerate(session["labels"])]
                                      for k in errors]}
            if bundle is author:
                record["native_kfold_losses"] = [k / n for k in errors]
            bundle["sessions"].append(record)
    return manifest, author, candidate


class EndpointControls(unittest.TestCase):
    def test_source_endpoint_selection_and_equal_session_aggregation(self):
        result = score.compare(*fixture())
        self.assertEqual(result["author"]["mean_session_accuracy_percent"], 50)
        self.assertAlmostEqual(result["candidate"]["mean_session_accuracy_percent"], 1700 / 18)
        self.assertAlmostEqual(result["mean_session_delta_percentage_points"], 800 / 18)
        # A trial-pooled result would be 340/380, which is a different endpoint.
        self.assertNotAlmostEqual(result["candidate"]["mean_session_accuracy_percent"], 100 * 340 / 380)
        self.assertEqual(result["author"]["sessions"][0]["selected_index_zero_based"], 2)
        self.assertEqual(result["author"]["sessions"][0]["selected_setting_id"], "ridge_02")
        self.assertEqual(len(result["rat_clusters"]), 8)
        self.assertEqual(result["rat_clusters"][0]["session_count"], 3)
        self.assertAlmostEqual(result["rat_clusters"][0]["mean_session_delta_percentage_points"], 50 / 3)
        self.assertNotIn("paper_win", result)

    def test_all_settings_retained_and_native_parity_required_even_for_nonwinner(self):
        manifest, author, candidate = fixture()
        author["sessions"][0]["native_kfold_losses"][9] = .99
        with self.assertRaisesRegex(ValueError, "native kfoldLoss"):
            score.compare(manifest, author, candidate)

    def test_unequal_fold_sizes_use_trial_loss_and_require_native_agreement(self):
        manifest, author, candidate = fixture()
        session = manifest["sessions"][0]
        session["folds"] = list(range(1, 11)) + [10] * 30
        for bundle in (author, candidate):
            bundle["manifest_sha256"] = score.digest(manifest)
            bundle["sessions"][0]["folds"] = session["folds"][:]
        result = score.compare(manifest, author, candidate)
        row = result["author"]["sessions"][0]
        self.assertEqual(row["losses_by_setting"][2], .5)
        unweighted_fold_error = sum(e / n for e, n in zip(row["errors_by_setting_and_fold"][2], row["fold_sizes"])) / 10
        self.assertNotAlmostEqual(unweighted_fold_error, .5)

    def test_exact_panel_and_pairing_failures(self):
        mutators = [
            lambda m, a, c: m["sessions"].pop(),
            lambda m, a, c: m["sessions"][0].update(rat_id="ninth_rat"),
            lambda m, a, c: m["sessions"][0].update(unit_count=4),
            lambda m, a, c: c["sessions"].reverse(),
            lambda m, a, c: c["sessions"][0]["trial_ids"].reverse(),
            lambda m, a, c: c["sessions"][0]["folds"].reverse(),
            lambda m, a, c: c["sessions"][0]["predictions"].pop(),
            lambda m, a, c: c["sessions"][0]["predictions"][0].pop(),
            lambda m, a, c: c["sessions"][0]["predictions"][0].__setitem__(0, True),
            lambda m, a, c: c["sessions"][0]["predictions"][0].__setitem__(0, float("nan")),
            lambda m, a, c: c["setting_ids"].__setitem__(1, c["setting_ids"][0]),
            lambda m, a, c: a["lambdas"].reverse(),
            lambda m, a, c: m["sessions"][0]["labels"].__setitem__(0, True),
            lambda m, a, c: m["sessions"][0].update(folds=[1] * 40),
            lambda m, a, c: m["sessions"][0].update(labels=[0] * 40),
            lambda m, a, c: a["sessions"][0]["native_kfold_losses"].__setitem__(0, float("inf")),
            lambda m, a, c: c.update(manifest_sha256="0" * 64),
            lambda m, a, c: c.update(program_sha256="not-a-pin"),
            lambda m, a, c: m["sessions"][0]["trial_ids"].__setitem__(1, m["sessions"][0]["trial_ids"][0]),
        ]
        for i, mutate in enumerate(mutators):
            with self.subTest(case=i):
                items = fixture()
                mutate(*items)
                with self.assertRaises(ValueError):
                    score.compare(*items)

    def test_source_label_collision_counterexample(self):
        found = score.audit_source_labels([False, True, True], [True, False, False])
        self.assertEqual(found["literal_native_labels"], [0, 0, 0])
        self.assertEqual(found["mask_semantic_labels_slow_precedence"], [0, 1, 1])
        self.assertEqual(found["mismatched_trial_indices_one_based"], [2, 3])
        ordinary = score.audit_source_labels([True, False, True], [False, True, False])
        self.assertEqual(ordinary["literal_native_labels"], [1, 0, 1])
        self.assertEqual(ordinary["mismatched_trial_indices_one_based"], [])
        overlap = score.audit_source_labels([True, True], [True, True])
        self.assertEqual(overlap["overlapping_quartile_trial_indices_one_based"], [1, 2])

    def test_cli_actual_json_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="fig6h-invented-") as tmp:
            root = Path(tmp)
            args = []
            for name, value in zip(("manifest", "author", "candidate"), fixture()):
                path = root / (name + ".json")
                path.write_text(json.dumps(value), encoding="utf-8")
                args += ["--" + name, str(path)]
            out = root / "result.json"
            command = [sys.executable, "-I", "-B", str(HERE / "score.py"), *args, "--output", str(out)]
            first = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(out.read_text())["author"]["mean_session_accuracy_percent"], 50)
            frozen = out.read_bytes()
            second = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(out.read_bytes(), frozen)

    def test_strict_json_rejects_duplicate_keys_and_nan(self):
        with tempfile.TemporaryDirectory(prefix="fig6h-invented-json-") as tmp:
            path = Path(tmp) / "bad.json"
            for body in ('{"x": 1, "x": 2}', '{"x": NaN}'):
                path.write_text(body)
                with self.assertRaises(ValueError):
                    score.load_json(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
