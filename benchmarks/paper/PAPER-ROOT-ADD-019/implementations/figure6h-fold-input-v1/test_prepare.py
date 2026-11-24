"""Generated controls only; no authentic arrays, native fits or scientific score."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ach_fold_prepare", HERE / "prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def fixture():
    _, projection = prepare.dependencies()
    source = {"schema": "ach_fig6h_projection_panel_input_v1", "task": prepare.TASK,
              "source_cohort_manifest_sha256": "b" * 64, "sessions": []}
    manifest = {"schema": "ach_fig6h_oof_manifest_v1", "task": prepare.TASK,
                "preparation_sha256": "c" * 64, "sessions": []}
    for i in range(18):
        trials = ["PRIVATE_trial_%02d_%02d" % (i, t) for t in range(20)]
        labels = [int(t % 2 == 0) for t in range(20)]
        session = "PRIVATE_session_%02d" % i
        rat = "PRIVATE_rat_%d" % (i % 8)
        source["sessions"].append({
            "schema": "ach_fig6h_projection_input_v1", "task": prepare.TASK,
            "source_code_sha256": projection.SOURCE_SHA256, "source_export_sha256": "a" * 64,
            "session_id": session, "rat_id": rat, "source_session_index_one_based": i + 1,
            "trial_ids": trials,
            "units": [{"unit_id": "PRIVATE_unit_%d" % u, "trial_ids": trials[:],
                       "son_time_s": [0., .5],
                       "son_values": [[10000 * i + 100 * t + 10 * u + k for k in range(2)]
                                      for t in range(20)]} for u in range(5)],
            "selection": {"is_fast": [bool(y) for y in labels],
                          "is_slow": [not y for y in labels],
                          "trial_indices_one_based": list(range(1, 21)), "literal_labels": labels[:]}})
        manifest["sessions"].append({"session_id": session, "rat_id": rat, "unit_count": 5,
                                     "trial_ids": trials[:], "folds": [t % 10 + 1 for t in range(20)],
                                     "labels": labels[:]})
    return source, manifest


class FoldPreparationControls(unittest.TestCase):
    def test_exact_neural_values_source_order_all_sessions_and_training_labels(self):
        source, manifest = fixture()
        before = copy.deepcopy((source, manifest))
        view, receipt = prepare.prepare_fold(source, manifest, 2)
        self.assertEqual((source, manifest), before)
        self.assertEqual(len(view["sessions"]), 18)
        first = view["sessions"][0]
        self.assertEqual(len(first["training"]), 18)
        self.assertEqual(len(first["held_out"]), 2)
        self.assertEqual(first["held_out"][0], {
            "trial_id": "held_out_000001", "predictors": [100,110,120,130,140,101,111,121,131,141]})
        self.assertEqual(first["training"][0]["label"], 1)
        self.assertEqual(first["training"][1]["label"], 1)
        self.assertEqual(first["feature_columns"],
                         [{"unit_index_one_based": u + 1, "time_s": t}
                          for t in (0., .5) for u in range(5)])
        self.assertEqual(receipt["sessions"][0]["held_out"][0]["source_trial_id"],
                         manifest["sessions"][0]["trial_ids"][1])
        self.assertFalse(receipt["secure_execution_established"])
        self.assertFalse(receipt["readiness_promoted"])

    def test_public_allowlist_contains_no_private_identity_audit_digest_or_test_label(self):
        source, manifest = fixture()
        view, receipt = prepare.prepare_fold(source, manifest, 2)
        self.assertEqual(set(view), {"schema", "task", "held_out_fold", "sessions"})
        for session in view["sessions"]:
            self.assertEqual(set(session), {"session_id", "feature_columns", "training", "held_out"})
            for row in session["training"]:
                self.assertEqual(set(row), {"trial_id", "predictors", "label"})
            for row in session["held_out"]:
                self.assertEqual(set(row), {"trial_id", "predictors"})
        serialized = json.dumps(view)
        for canary in ("PRIVATE_", "sha256", "literal", "audit", "rat_id", "source_retained_row"):
            self.assertNotIn(canary, serialized)
        self.assertIn("PRIVATE_", json.dumps(receipt))

    def test_withheld_labels_do_not_change_participant_payload(self):
        source, manifest = fixture()
        before, old_receipt = prepare.prepare_fold(source, manifest, 2)
        for native, target in zip(source["sessions"], manifest["sessions"]):
            for t in (1, 11):
                native["selection"]["is_fast"][t] = True
                native["selection"]["is_slow"][t] = False
                native["selection"]["literal_labels"][t] = 1
                target["labels"][t] = 1
        after, new_receipt = prepare.prepare_fold(source, manifest, 2)
        self.assertEqual(before, after)
        self.assertEqual(old_receipt["participant_input_sha256"], new_receipt["participant_input_sha256"])
        self.assertNotEqual(old_receipt["operator_manifest_sha256"], new_receipt["operator_manifest_sha256"])

    def test_original_source_identity_and_label_join_must_match(self):
        mutations = [
            lambda m: m["sessions"].reverse(),
            lambda m: m["sessions"][0]["trial_ids"].reverse(),
            lambda m: m["sessions"][0].update(unit_count=6),
            lambda m: m["sessions"][0].update(rat_id=m["sessions"][1]["rat_id"]),
            lambda m: m["sessions"][0]["labels"].__setitem__(2, 0),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                source, manifest = fixture()
                mutate(manifest)
                with self.assertRaises(ValueError):
                    prepare.prepare_fold(source, manifest, 2)

    def test_no_generated_folds_or_reduced_cohort(self):
        source, manifest = fixture()
        for fold in (0, 11, True, 1.0):
            with self.assertRaises(ValueError):
                prepare.prepare_fold(source, manifest, fold)
        for mutate in (lambda m: m["sessions"].pop(),
                       lambda m: m["sessions"][0].update(folds=[1] * 20)):
            altered = copy.deepcopy(manifest)
            mutate(altered)
            with self.assertRaises(ValueError):
                prepare.prepare_fold(source, altered, 2)

    def test_all_original_folds_partition_every_retained_trial_once(self):
        source, manifest = fixture()
        seen = [[] for _ in range(18)]
        for fold in range(1, 11):
            view, receipt = prepare.prepare_fold(source, manifest, fold)
            for i, (public, mapping) in enumerate(zip(view["sessions"], receipt["sessions"])):
                held_out = [r["source_trial_id"] for r in mapping["held_out"]]
                training = [r["source_trial_id"] for r in mapping["training"]]
                self.assertFalse(set(training) & set(held_out))
                self.assertEqual(set(training + held_out), set(manifest["sessions"][i]["trial_ids"]))
                self.assertEqual(len(public["held_out"]), len(held_out))
                seen[i].extend(held_out)
        for i, trials in enumerate(seen):
            self.assertEqual(sorted(trials), sorted(manifest["sessions"][i]["trial_ids"]))

    def test_cli_serializes_separate_outputs_and_refuses_overwrite_or_codelivery(self):
        source, manifest = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public_dir, private_dir = root / "participant", root / "operator"
            public_dir.mkdir(); private_dir.mkdir()
            a, b = private_dir / "source.json", private_dir / "manifest.json"
            a.write_text(json.dumps(source)); b.write_text(json.dumps(manifest))
            public, receipt = public_dir / "input.json", private_dir / "receipt.json"
            args = ["prepare.py", "--source-panel", str(a), "--manifest", str(b), "--fold", "2",
                    "--participant-output", str(public), "--operator-receipt", str(receipt)]
            with patch.object(sys, "argv", args):
                prepare.main()
                saved = public.read_bytes()
                with self.assertRaisesRegex(ValueError, "already exists"):
                    prepare.main()
                self.assertEqual(public.read_bytes(), saved)
            score, _ = prepare.dependencies()
            self.assertEqual(json.loads(receipt.read_text())["participant_input_sha256"],
                             score.digest(json.loads(public.read_text())))
            args[-1] = str(public_dir / "bad-receipt.json")
            with patch.object(sys, "argv", args), self.assertRaisesRegex(ValueError, "separate directories"):
                prepare.main()
            self.assertFalse((public_dir / "bad-receipt.json").exists())
            print("GENERATED_TRANSIENT_WRITE_BYTES=" + str(sum(p.stat().st_size for p in (a,b,public,receipt))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
