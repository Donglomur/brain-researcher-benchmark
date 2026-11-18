"""Generated observations only; no recordings, estimators or scientific runs."""
from collections import Counter
import copy
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify as v


def fixture():
    prepared = {"schema": "treebank-figure4-preparation/v2", "task_id": v.TASK_ID,
                "eligibility": {"sub_1": ["A1"]}}
    windows = [{"source_key": "-1.0", "nominal_start": -1.0,
                "requested_start_sample": 0, "requested_sample_count": 512}]
    context = {"source_subject": "sub_1", "contact": "A1", "window": {
        "index": 0, "nominal_start": -1.0, "requested_sample_start": 0,
        "requested_sample_duration": 512}}
    def event(kind, **fields):
        return {"event": kind, "subject": "sub_1", "context": copy.deepcopy(context), **fields}
    labels = [0, 1] * 7
    scores = {"test_score": 1., "cv_score": .7}
    events = [{"event": "observation_started", "subject": None, "unavailable_hooks": {}}]
    events += [event("split", status="observed", train=list(range(10)), validation=[],
                     test=list(range(10, 14)), dataset_labels=labels, train_labels=labels[:10],
                     test_labels=labels[10:], validation_labels=[]),
               event("label_mapping", status="observed", mapping=[{"label": False, "index": 0},
                                                                     {"label": True, "index": 1}])]
    for k in range(5):
        valid = [2 * k, 2 * k + 1]
        events.append(event("training_cv_fold", train_relative_to_training=[i for i in range(10) if i not in valid],
                            validation_relative_to_training=valid, result={"test_scores": .7}))
    events += [event("training_cv_scores", scores=[.7] * 5),
               event("heldout_probabilities", source_column_used=1,
                     class_order={"status": "observed", "values": [0, 1]},
                     probabilities=[[.9, .1], [.2, .8], [.7, .3], [.1, .9]]),
               event("window_result", status="observed", scores=scores,
                     observation_counts={"split": 1, "label_mapping": 1, "training_cv_fold": 5,
                                         "training_cv_scores": 1, "heldout_probabilities": 1},
                     unavailable_observations=[])]
    events.append({"event": "observation_finished", "subject": "sub_1",
                   "status": "observed_not_scientifically_qualified", "observer_failure": None,
                   "unavailable_hooks": {}, "windows_with_unavailable_observations": 0,
                   "completed_window_calls": 1, "event_counts": dict(Counter(x["event"] for x in events))})
    return prepared, windows, {"sub_1": {"A1": {"-1.0": scores}}}, events


def run_fixture(parts):
    prepared, windows, scores, events = parts
    return v.verify(iter(events), prepared, windows, scores, max_examples_per_window=100, max_events=100)


class ArithmeticTests(unittest.TestCase):
    def test_rank_auc_matches_independent_pair_definition_with_ties(self):
        rng = random.Random(91)
        for n in range(2, 30):
            labels = [0, 1] + [rng.randrange(2) for _ in range(n - 2)]
            scores = [rng.randrange(5) for _ in labels]
            pos = [s for y, s in zip(labels, scores) if y]
            neg = [s for y, s in zip(labels, scores) if not y]
            direct = sum((a > b) + .5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))
            self.assertEqual(v.rank_auc(labels, scores), direct)

    def test_valid_stream_checks_scores_and_retains_nonqualification(self):
        result = run_fixture(fixture())
        self.assertEqual(result["window_calls_verified"], 1)
        self.assertEqual(result["heldout_prediction_rows_verified"], 4)
        self.assertFalse(result["cv_prediction_level_auc_recomputed"])
        self.assertFalse(result["original_support_authenticated"])
        self.assertEqual(result["full_primary_reproduction"], "unavailable")
        self.assertNotIn("labels", result)
        self.assertNotIn("probabilities", result)
        self.assertNotIn("examples", result)

    def test_reversed_probability_column_cannot_match_source_auc(self):
        parts = fixture()
        e = next(x for x in parts[3] if x["event"] == "heldout_probabilities")
        e["probabilities"] = [row[::-1] for row in e["probabilities"]]
        with self.assertRaisesRegex(v.VerificationError, "source test AUC"):
            run_fixture(parts)

    def test_saved_scores_cannot_be_changed_after_observation(self):
        parts = list(fixture())
        parts[2] = copy.deepcopy(parts[2])
        parts[2]["sub_1"]["A1"]["-1.0"]["test_score"] = .5
        with self.assertRaisesRegex(v.VerificationError, "saved score artifact"):
            run_fixture(parts)

    def test_cv_is_mean_of_fold_scores_not_claimed_as_prediction_replay(self):
        parts = fixture()
        next(x for x in parts[3] if x["event"] == "training_cv_scores")["scores"][-1] = .1
        with self.assertRaisesRegex(v.VerificationError, "five-CV mean"):
            run_fixture(parts)

    def test_repeated_fold_and_heldout_index_cannot_enter_training_cv(self):
        for mode in ("repeat", "test_index"):
            with self.subTest(mode=mode):
                parts = fixture()
                folds = [x for x in parts[3] if x["event"] == "training_cv_fold"]
                if mode == "repeat":
                    folds[-1].update({k: copy.deepcopy(folds[0][k]) for k in
                                     ("train_relative_to_training", "validation_relative_to_training")})
                else:
                    folds[0]["validation_relative_to_training"][0] = 10
                with self.assertRaises(v.VerificationError):
                    run_fixture(parts)

    def test_split_must_be_complete_disjoint_and_label_aligned(self):
        for field, value in (("test", [10, 11, 12, 12]), ("train", list(range(9))),
                             ("test_labels", [1, 0, 1, 0]), ("train_labels", [False, True] * 5)):
            parts = fixture()
            parts[3][1][field] = value
            with self.subTest(field=field), self.assertRaises(v.VerificationError):
                run_fixture(parts)

    def test_probabilities_reject_nonfinite_boolean_wrong_polarity_or_count(self):
        for field, value in (("probabilities", [[.9, .1]]),
                             ("probabilities", [[False, True]] * 4),
                             ("probabilities", [[float("nan"), .1]] * 4),
                             ("probabilities", [[.9, .9]] * 4),
                             ("source_column_used", 0),
                             ("class_order", {"status": "observed", "values": [1, 0]}),
                             ("class_order", {"status": "observed", "values": [False, True]})):
            parts = fixture()
            next(x for x in parts[3] if x["event"] == "heldout_probabilities")[field] = value
            with self.subTest(field=field, value=str(value)[:60]), self.assertRaises(v.VerificationError):
                run_fixture(parts)

    def test_missing_extra_duplicate_or_foreign_window_is_rejected(self):
        for mode in ("missing", "duplicate", "foreign", "after_finish", "missing_finish"):
            parts = fixture()
            if mode == "missing":
                del parts[3][2]
            elif mode == "duplicate":
                parts[3].insert(3, copy.deepcopy(parts[3][2]))
            elif mode == "foreign":
                parts[3][2]["context"]["contact"] = "B2"
            elif mode == "after_finish":
                parts[3].append(copy.deepcopy(parts[3][1]))
            else:
                parts[3].pop()
            with self.subTest(mode=mode), self.assertRaises(v.VerificationError):
                run_fixture(parts)

    def test_declared_missing_contact_cannot_disappear_from_coverage(self):
        parts = fixture()
        parts[0]["eligibility"]["sub_1"].append("B2")
        parts[2]["sub_1"]["B2"] = copy.deepcopy(parts[2]["sub_1"]["A1"])
        with self.assertRaises(v.VerificationError):
            run_fixture(parts)

    def test_wrong_window_bounds_and_receipt_counts_are_rejected(self):
        parts = fixture()
        parts[3][1]["context"]["window"]["requested_sample_start"] = 1
        with self.assertRaisesRegex(v.VerificationError, "window definition"):
            run_fixture(parts)
        parts = fixture()
        parts[3][-2]["observation_counts"]["training_cv_fold"] = 4
        with self.assertRaisesRegex(v.VerificationError, "event counts"):
            run_fixture(parts)
        parts = fixture()
        parts[3][-1]["event_counts"]["split"] = 2
        with self.assertRaisesRegex(v.VerificationError, "total counts"):
            run_fixture(parts)

    def test_support_disagreement_is_preserved_not_a_same_case_claim(self):
        parts = fixture()
        parts[3].insert(-1, {"event": "source_support_disagreement", "reason": "different cases"})
        result = run_fixture(parts)
        self.assertEqual(result["source_support_disagreements_observed"], 1)
        self.assertEqual(result["same_case_claim"], "not_admitted_by_this_verifier")

    def test_all_declared_budgets_apply(self):
        p, w, s, e = fixture()
        with self.assertRaisesRegex(v.VerificationError, "example budget"):
            v.verify(e, p, w, s, max_examples_per_window=13, max_events=100)
        with self.assertRaisesRegex(v.VerificationError, "event allocation"):
            v.verify(e, p, w, s, max_examples_per_window=100, max_events=11)

    def test_strict_json_and_decompressed_stream_bounds(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{bad'):
            with self.assertRaises(v.VerificationError):
                v.strict_loads(raw)
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "observations.gz"
            raw = b'{"event":"one"}\n{"event":"two"}\n'
            path.write_bytes(gzip.compress(raw, mtime=0))
            identity = {}
            self.assertEqual(len(list(v.event_stream(path, compressed=True, maximum_bytes=100,
                                                    maximum_line_bytes=100, identity=identity))), 2)
            self.assertEqual(identity["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(identity["bytes"], len(raw))
            for maximum, line_max in ((10, 100), (100, 10)):
                with self.assertRaises(v.VerificationError):
                    list(v.event_stream(path, compressed=True, maximum_bytes=maximum, maximum_line_bytes=line_max))

    def test_source_json_limit_excludes_framing_newline(self):
        # Real 1 MiB boundary; no large fixture is written to disk.
        prefix, suffix = b'{"padding":"', b'"}'
        raw = prefix + b'x' * (v.MAXIMUM_EVENT_JSON_BYTES - len(prefix) - len(suffix)) + suffix
        self.assertEqual(len(raw), 1048576)
        line = raw + b'\n'
        identity = {}
        with patch("builtins.open", return_value=io.BytesIO(line)):
            events = list(v.event_stream("memory", compressed=False, maximum_bytes=len(line),
                                         identity=identity))
        self.assertEqual(events, [{"padding": "x" * (len(raw) - len(prefix) - len(suffix))}])
        self.assertEqual(identity["bytes"], len(line))
        self.assertEqual(identity["sha256"], hashlib.sha256(line).hexdigest())
        oversized = prefix + b'x' * (v.MAXIMUM_EVENT_JSON_BYTES + 1 - len(prefix) - len(suffix)) + suffix + b'\n'
        for content, total_limit in ((oversized, len(oversized)), (line, len(raw))):
            with patch("builtins.open", return_value=io.BytesIO(content)):
                with self.assertRaisesRegex(v.VerificationError, "byte/line budget"):
                    list(v.event_stream("memory", compressed=False, maximum_bytes=total_limit))

    def test_real_observer_generated_fixture_fails_its_invalid_fold_support(self):
        # Use the maintained producer's actual event emitter. Its old fixture
        # deliberately repeats a fold and has a one-class held-out set; source
        # hook success must not be mistaken for independent numeric validation.
        path = HERE.parent / "treebank-figure4-producer-v2/tests/test_observation.py"
        spec = importlib.util.spec_from_file_location("treebank_emitter_fixture", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as name:
            f = module.Fixture(Path(name))
            events = []
            try:
                with patch.object(module.observation.importlib.metadata, "distribution", f.distribution):
                    observer = module.observation.SourceObserver(f.root, events.append)
                    observer.subject = "sub_1"
                    with observer:
                        saved = f.run()
                p, w, _, _ = fixture()
                w.append({"source_key": "-0.9", "nominal_start": -.9,
                          "requested_start_sample": 204, "requested_sample_count": 512})
                saved = {"sub_1": json.loads(json.dumps(saved))}
                with self.assertRaisesRegex(v.VerificationError, "CV fold|CV validation"):
                    v.verify(events, p, w, saved, max_examples_per_window=100, max_events=100)
            finally:
                f.close()
                sys.setprofile(None)
                sys.settrace(None)


if __name__ == "__main__":
    unittest.main()
