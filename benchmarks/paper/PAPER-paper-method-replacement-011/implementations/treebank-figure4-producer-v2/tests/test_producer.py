"""Generated metadata/scores and mocked source calls only; no scientific fit."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import custody
import preparation
import collect_figure4 as figures
import replay
from support_checks import SupportChecks


def fixture():
    inventory = {"sub_5": ["generated0"], "sub_10": ["generated0", "generated1"]}
    labels = {"sub_5": ["A*", "DC4"], "sub_10": [f"G{index}" for index in range(37)] + ["T1cIf8"]}
    excluded = {"sub_5": ["DC4"], "sub_10": []}
    recordings = {(subject, run): {"filename": f"movie-{subject}-{run}"}
                  for subject, runs in inventory.items() for run in runs}
    anatomy = {subject: [{"Electrode": label, "DesikanKilliany": "generated-DK"} for label in names]
               for subject, names in labels.items()}
    anatomy["sub_10"].append({"Electrode": "extra-anatomy-only", "DesikanKilliany": "outside"})
    coords = {("sub_5", "A"): {"X": "1", "Y": "2", "Z": "3"},
              ("sub_10", "T1cIf8"): {"X": "4", "Y": "5", "Z": "6"}}
    manifest = preparation.build_manifest(inventory, labels, excluded, recordings, anatomy, coords)
    windows = [{"source_key": "generated-left"}, {"source_key": "generated-right"}]
    scores = {subject: {name: {"generated-left": {"test_score": .6, "cv_score": .7},
                               "generated-right": {"test_score": .8, "cv_score": .5}} for name in names}
              for subject, names in manifest["eligibility"].items()}
    return manifest, scores, windows


class CustodyTests(unittest.TestCase):
    def test_strict_json(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                custody.loads(raw)

    def test_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            custody.write_json_exclusive(path, {"generated": 1})
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                custody.write_json_exclusive(path, {"generated": 2})
            self.assertEqual(path.read_bytes(), original)

    def test_metadata_pin_fails_without_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata"
            path.write_bytes(b"generated wrong payload")
            with self.assertRaisesRegex(ValueError, "authenticated labels"):
                custody.pinned_metadata(path, "labels")

    def test_zip_ambiguity_and_limit(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("one", b"generated")
        with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
            self.assertEqual(custody.zip_member(archive, "one"), b"generated")
            with self.assertRaises(ValueError):
                custody.zip_member(archive, "one", limit=2)
            with self.assertRaises(ValueError):
                custody.zip_member(archive, "absent")

    def test_git_injections_and_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            def git(*args):
                return custody.source_git(repo, *args).decode().strip()
            git("init", "--template=", "-q")
            git("config", "user.name", "Generated Test")
            git("config", "user.email", "generated@example.invalid")
            (repo / "original.py").write_text("# generated source fixture\n")
            git("add", "original.py")
            git("commit", "-qm", "generated fixture")
            commit = git("rev-parse", "HEAD")
            verified = custody.verify_checkout(repo, commit)
            self.assertEqual(set(verified["files"]), {"original.py"})
            (repo / "injected.py").write_text("# never imported\n")
            with self.assertRaises(ValueError):
                custody.verify_checkout(repo, commit)
            git("add", "injected.py")
            with self.assertRaisesRegex(ValueError, "added/removed"):
                custody.verify_checkout(repo, commit)
            git("reset", "-q", "HEAD", "--", "injected.py")
            (repo / "injected.py").unlink()
            (repo / "original.py").write_text("# modified generated fixture\n")
            with self.assertRaisesRegex(ValueError, "modified source"):
                custody.verify_checkout(repo, commit)

    def test_git_is_offline_and_noninteractive(self):
        completed = types.SimpleNamespace(returncode=0, stdout=b"generated", stderr=b"")
        with patch.object(custody.subprocess, "run", return_value=completed) as call:
            custody.source_git(Path("/generated"), "rev-parse", "HEAD")
        args, kwargs = call.call_args
        self.assertIn("protocol.allow=never", args[0])
        self.assertEqual(kwargs["env"]["GIT_ALLOW_PROTOCOL"], "")
        self.assertEqual(kwargs["env"]["GIT_NO_LAZY_FETCH"], "1")
        self.assertEqual(kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)


class MetadataAndFigureTests(unittest.TestCase):
    def test_order_aliases_and_control_counts(self):
        contacts = preparation.ordered_contacts(["B_1", "A#1", "DC4"], ["A1", "DC4"])
        self.assertEqual([row["contact"] for row in contacts], ["B1", "A1", "DC4"])
        self.assertEqual([row["hdf5_dataset"] for row in contacts],
                         ["data/electrode_0", "data/electrode_1", "data/electrode_2"])
        manifest, _, _ = fixture()
        self.assertEqual(manifest["counts"]["recording_controls"], 1)
        self.assertEqual(manifest["counts"]["excluded_neural"], 0)
        self.assertEqual(manifest["eligibility"]["sub_5"], ["A"])
        self.assertEqual(manifest["subjects"][1]["unused_anatomy_rows"], ["extra-anatomy-only"])

    def test_label_and_csv_rejections(self):
        for labels, rejected in [(["A*", "A"], []), (["A"], ["missing"]), (["*#_"], []),
                                 (["A"], ["A", "A*"])]:
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                preparation.ordered_contacts(labels, rejected)
        for raw in (b"x,x\n1,2\n", b"x,y\n1\n", b"x\n1,2\n"):
            with self.assertRaises(ValueError):
                preparation.csv_rows(raw)

    def test_known_panel_math_and_map_only_omissions(self):
        manifest, scores, windows = fixture()
        result = figures.collect(manifest, scores, windows)
        support = result["supplied_prediction_support"]
        self.assertEqual(support["contacts"], 39)
        self.assertEqual(support["original_support_authentication"], "not_performed_by_this_pure_reducer")
        self.assertTrue(any(row["identity"][0] == "sub_5" for row in support["curves"]))
        self.assertEqual(result["panel_b"]["example"]["test_curve"], [.6, .8])
        self.assertEqual(result["panel_b"]["example"]["label_index"], 37)
        self.assertEqual(len(result["panel_a"]["released_coordinate_join"]), 1)
        self.assertEqual(len(result["panel_a"]["map_only_omissions"]), 38)
        self.assertEqual(result["panel_c"]["status"], "unavailable_original_dk_to_lobe_definition")
        self.assertEqual(result["full_primary_reproduction"], "unavailable")

    def test_full_declared_coverage_failures(self):
        for kind in ("subject", "contact", "window", "extra-window", "row-missing", "row-duplicate"):
            manifest, scores, windows = fixture()
            if kind == "subject":
                del scores["sub_5"]
            elif kind == "contact":
                del scores["sub_10"]["G0"]
            elif kind == "window":
                del scores["sub_10"]["G0"]["generated-left"]
            elif kind == "extra-window":
                scores["sub_10"]["G0"]["invented"] = {"test_score": .8, "cv_score": .8}
            elif kind == "row-missing":
                manifest["subjects"].pop(0)
            else:
                manifest["subjects"].append(copy.deepcopy(manifest["subjects"][0]))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                figures.collect(manifest, scores, windows)

    def test_auc_requires_finite_real_probability(self):
        for invalid in (True, "0.9", None, float("nan"), float("inf"), -.1, 1.1):
            manifest, scores, windows = fixture()
            scores["sub_5"]["A"]["generated-left"]["test_score"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                figures.collect(manifest, scores, windows)

    def test_selection_is_training_only_and_exact_mean(self):
        rows = [{"identity": ["generated", str(index)], "cv_curve": [index / 20, .01],
                 "test_curve": [1 - index / 20, .2]} for index in range(12)]
        result = figures.ranked_group(rows)
        self.assertEqual([row["identity"][1] for row in result["selected"]], list(map(str, range(11, 1, -1))))
        self.assertAlmostEqual(result["mean_test_curve"][0], .675)
        self.assertIsNone(result["display_interval"])
        changed = copy.deepcopy(rows)
        changed[0]["test_curve"] = [1, 1]
        self.assertEqual([row["identity"] for row in figures.ranked_group(changed)["selected"]],
                         [row["identity"] for row in result["selected"]])

    def test_cutoff_tie_is_not_invented(self):
        rows = [{"identity": ["generated", str(index)], "cv_curve": [.7], "test_curve": [.4 + index / 100]}
                for index in range(11)]
        result = figures.ranked_group(rows)
        self.assertEqual(result["status"], "unavailable_cutoff_tie_rule")
        self.assertIsNone(result["selected"])


class NativeBoundaryTests(unittest.TestCase):
    def test_complete_claim_requires_mapping_and_all_window_observations(self):
        manifest = {"eligibility": {"generated": ["A"]}, "recording_inventory": {"generated": ["trial"]}}
        windows = [{"source_key": "0.0", "nominal_start": 0.0,
                    "requested_start_sample": 0, "requested_sample_count": 2}]
        context = {"source_subject": "generated", "contact": "A", "window": {
            "index": 0, "nominal_start": 0.0, "requested_sample_start": 0,
            "requested_sample_duration": 2, "supplied_shape": [2, 1, 2], "parent_shape": [2, 1, 2]}}
        for missing in ([], ["complete_training_cv_fold_membership"]):
            with self.subTest(missing=missing):
                check = SupportChecks(manifest, windows)
                check.observe({"event": "sampling", "context": dict(context, window=None), "status": "observed",
                               "run_subject": "generated", "run_id": "trial", "positive": [], "negative": []})
                check.observe({"event": "split", "context": context, "status": "observed",
                               "train": [0], "validation": [], "test": [1], "dataset_labels": [0, 1],
                               "train_labels": [0], "test_labels": [1]})
                check.observe({"event": "window_result", "context": context, "status": "observed",
                               "unavailable_observations": missing})
                self.assertEqual(check.summary()["same_case_claim"], "unavailable")
                check.observe({"event": "label_mapping", "context": context, "status": "observed",
                               "mapping": [{"label": "generated-negative", "index": 0},
                                           {"label": "generated-positive", "index": 1}]})
                expected = "unavailable" if missing else "consistent_in_complete_observed_support"
                self.assertEqual(check.summary()["same_case_claim"], expected)
                self.assertEqual(check.summary()["observed_label_mapping_calls"], 1)
                reordered = {"event": "label_mapping", "context": context, "status": "observed",
                             "mapping": [{"label": "generated-positive", "index": 1},
                                         {"label": "generated-negative", "index": 0}]}
                unchanged = copy.deepcopy(reordered)
                self.assertEqual(check.observe(reordered), [])
                self.assertEqual(reordered, unchanged)
                reordered["mapping"][0]["index"], reordered["mapping"][1]["index"] = 0, 1
                self.assertEqual(len(check.observe(reordered)), 1)
                if missing:
                    self.assertEqual(check.summary()["window_unavailable_reasons"], {missing[0]: 1})

    def test_case_disagreement_is_reported_without_changing_source_event(self):
        manifest, _, _ = fixture()
        windows = [{"source_key": "0.0", "nominal_start": 0.0,
                    "requested_start_sample": 100, "requested_sample_count": 512}]
        validator = SupportChecks(manifest, windows)
        context = {"source_subject": "sub_10", "contact": "G0", "window": {
            "index": 0, "nominal_start": 0.0, "requested_sample_start": 100,
            "requested_sample_duration": 512, "supplied_shape": [4, 1, 400], "parent_shape": [4, 1, 500]}}
        event = {"event": "split", "context": context, "status": "observed",
                 "train": [0, 1], "validation": [], "test": [2, 3],
                 "dataset_labels": [0, 1, 0, 1], "train_labels": [0, 1], "test_labels": [0, 1]}
        self.assertEqual(validator.observe(event), [])
        second = copy.deepcopy(event)
        second["context"]["contact"] = "G1"
        second["train"], second["test"] = [2, 3], [0, 1]
        before = copy.deepcopy(second)
        issues = validator.observe(second)
        self.assertTrue(any("differ across" in issue["reason"] for issue in issues))
        self.assertEqual(second, before)
        self.assertEqual(validator.summary()["same_case_claim"], "unavailable")
        self.assertEqual(validator.summary()["observed_split_calls"], 2)

    def test_changed_samples_remain_observed_evidence(self):
        manifest, _, _ = fixture()
        check = SupportChecks(manifest, [])
        event = {"event": "sampling", "context": {"source_subject": "sub_10", "contact": "G0", "window": None},
                 "status": "observed", "run_subject": "sub_10", "run_id": "generated0",
                 "positive": [{"sample_bounds": [10, 20]}], "negative": [{"sample_bounds": [30, 40]}]}
        self.assertEqual(check.observe(event), [])
        other = copy.deepcopy(event)
        other["context"]["contact"] = "G1"
        other["positive"][0]["sample_bounds"] = [11, 21]
        self.assertEqual(len(check.observe(other)), 1)
        self.assertEqual(check.summary()["observed_sampling_calls"], 2)

    def test_multi_subject_original_calls_and_single_observer(self):
        manifest, _, _ = fixture()
        data = types.SimpleNamespace()
        cfg = types.SimpleNamespace(data=data)
        calls = []
        class Observer:
            enters = 0
            subject = None
            def __enter__(self):
                self.enters += 1
                if self.enters != 1:
                    raise ValueError("observer reused")
                return self
            def __exit__(self, *args):
                return False
        observer = Observer()
        def original(data_cfg, runs, electrodes, passed_cfg):
            self.assertIs(data_cfg, data)
            self.assertEqual(observer.subject, data_cfg.subject)
            calls.append((data_cfg.subject, list(runs), list(electrodes)))
            passed_cfg.data = types.SimpleNamespace(name="source-copy-mutation")
            return {name: {-.1: {"test_score": .7, "cv_score": .8}} for name in electrodes}
        with tempfile.TemporaryDirectory() as tmp:
            result = replay.run_original(types.SimpleNamespace(run_subject_test=original), cfg, manifest, observer, Path(tmp))
            self.assertEqual(set(result), {"sub_5", "sub_10"})
            self.assertEqual([row[0] for row in calls], ["sub_5", "sub_10"])
            self.assertEqual(calls[1][1], ["generated0", "generated1"])
            self.assertEqual(observer.enters, 1)
            self.assertTrue((Path(tmp) / "source_scores.sub_10.json").is_file())
            self.assertEqual(list(result["sub_5"]["A"]), ["-0.1"])

    def test_evidence_limit_preserves_prior_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.gz"
            log = replay.EvidenceLog(path, 60)
            log.emit({"generated": 1})
            with self.assertRaisesRegex(ValueError, "budget exhausted"):
                log.emit({"oversized": "x" * 100})
            log.close()
            self.assertEqual(gzip.decompress(path.read_bytes()), b'{"generated":1}\n')
            self.assertEqual(log.records, 1)

    def test_streamed_input_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generated-input"
            path.write_bytes(b"generated input only")
            expected = {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(replay.stream_identity(path, expected)["sha256"], expected["sha256"])
            with self.assertRaises(ValueError):
                replay.stream_identity(path, dict(expected, sha256="0" * 64))

    def test_exact_input_support_required_before_read(self):
        prepared = {"runtime_metadata_members": [], "subjects": [{"recordings": [
            {"hdf5_relative_path": "all_subject_data/generated.h5", "timings_relative_path": "subject_timings/generated.csv",
             "metadata": {"filename": "generated-movie"}}]}]}
        declaration = {"schema": "treebank-owner-frozen-inputs/v1", "task_id": custody.TASK_ID,
                       "source_provenance": {"kind": "generated"}, "files": []}
        with self.assertRaisesRegex(ValueError, "full original"):
            replay.authenticate_inputs(prepared, declaration, {})

    def test_native_preflight_failure_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source"
            source.mkdir()
            args = argparse.Namespace(**{name: base / name for name in (
                "labels_zip", "excluded_json", "subjects_zip", "localization_zip", "prepared", "data_root",
                "transcripts_root", "input_manifest")}, source_checkout=source, output=base / "output",
                runtime_identity="generated-mock-only", max_evidence_bytes=1000)
            with patch.object(replay, "assemble", side_effect=ValueError("generated input failure")):
                with self.assertRaisesRegex(ValueError, "generated input failure"):
                    replay.execute(args)
            receipt = json.loads((base / "output/provenance.json").read_text())
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["scientific_outcome"], "unqualified")
            self.assertFalse((base / "output/source_scores.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
