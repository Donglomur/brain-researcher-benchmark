"""Generated engineering controls only; no authentic neuroscience observations."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / "evaluator.py"
spec = importlib.util.spec_from_file_location("neural040", SOURCE)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def fixture(n=24):
    p = {"schema_version": 1, "task_id": ev.TASK, "data_scope": "public_development_only",
         "dataset_commit": ev.DATASET_COMMIT, "estimator": "equal_film_pearson",
         "participants": list(ev.PEOPLE), "tr_seconds": 1.49,
         "parcel_ids": {person: [f"generated-parcel-{i:04d}" for i in range(1000)] for person in ev.PEOPLE},
         "lags_tr": [0, 1], "guard_tr": 1, "feature_context_left_tr": 0,
         "feature_context_right_tr": 0, "capacity_rank": 2, "ridge_alpha": 1.0,
         "feature_assets": {f: {"extractor_revision": "generated-control-v1",
                                 "checkpoint_sha256": "0" * 64,
                                 "context_policy": "generated-pointwise"} for f in ev.FAMILIES},
         "segments": []}
    features, train, private = {}, {}, {}
    rng = np.random.default_rng(47)
    for pi, person in enumerate(ev.PEOPLE):
        for j, split in enumerate(("train", "evaluation", "evaluation")):
            sid = person + "-segment-" + str(j)
            keys = {f: sid + "-" + f for f in ev.FAMILIES}
            s = {"id": sid, "participant_id": person, "film_id": "generated-film-" + str(j),
                 "run_id": "generated-run-1", "split": split, "n_samples": n, "feature_keys": keys}
            if split == "evaluation":
                s["null_offsets_tr"] = [2] if n == 6 else [3, 4, 5]
            p["segments"].append(s)
            for key in keys.values():
                features[key] = rng.normal(size=(n, 3))
            signal = features[keys["audio"]][:, 0] + features[keys["visual"]][:, 1] + .3 * features[keys["language"]][:, 2]
            y = signal[:, None] * np.linspace(.5, 1.5, 1000)[None, :] + pi
            (train if split == "train" else private)[sid] = y
    return p, features, train, private


def target_meta(p, split):
    return {"protocol_sha256": ev.digest(p), "parcel_ids": copy.deepcopy(p["parcel_ids"]), "split": split}


def prediction_meta(p):
    return {"protocol_sha256": ev.digest(p), "parcel_ids": copy.deepcopy(p["parcel_ids"])}


class Controls(unittest.TestCase):
    def test_independent_pearson_oracle(self):
        y = np.array([-3, -1, 1, 3.])[:, None]
        b = np.array([-1, 1, -1, 1.])[:, None]
        self.assertAlmostEqual(ev.pearson_columns(y, b)[0], 1 / math.sqrt(5))
        self.assertAlmostEqual(ev.pearson_columns(y, y)[0] - ev.pearson_columns(y, b)[0],
                               1 - 1 / math.sqrt(5))
        self.assertAlmostEqual(ev.pearson_columns(y, -y)[0], -1)
        with self.assertRaises(ev.ContractError):
            ev.pearson_columns(y, np.ones_like(y))

    def test_ood_films_not_pooled_and_claims(self):
        p, _, _, private = fixture(6)
        predictions = {}
        for s in ev.selected_segments(p, split="evaluation"):
            second = s["film_id"].endswith("2")
            y = np.array([-3, -1, 1, 3.]) + (100 if second else 0)
            private[s["id"]][1:-1] = y[:, None]
            full = y + (-100 if second else 100)
            for arm in ev.ARMS:
                predictions[arm + "__" + s["id"]] = np.tile((full if arm == "full" else -y)[:, None], (1, 1000))
        result = ev.score(p, predictions, private, prediction_meta(p), target_meta(p, "evaluation"),
                          [{"family": "audio", "mean_delta_r": 2.0}, {"family": "visual", "mean_delta_r": 0.0}])
        self.assertAlmostEqual(result["contrasts"]["audio"]["mean_delta_r"], 2)
        self.assertEqual([c["verified"] for c in result["claims"]], [True, False])
        self.assertEqual(result["contrasts"]["audio"]["person_bootstrap_percentile_95"], [2., 2.])

    def test_end_to_end_equal_capacity_and_null_pairing(self):
        p, features, train, private = fixture()
        predictions, metadata = ev.encode(p, features, train, target_meta(p, "train"))
        self.assertEqual(len(metadata["fits"]), 16)
        self.assertEqual(len({f["readout_effective_df_including_intercept"] for f in metadata["fits"]}), 1)
        result = ev.score(p, predictions, private, metadata, target_meta(p, "evaluation"))
        self.assertFalse(result["scientific_qualification"])
        self.assertEqual(result["n_people"], 4)
        for s in ev.selected_segments(p, split="evaluation"):
            for arm in ev.ARMS:
                predictions[arm + "__" + s["id"]] = predictions["full__" + s["id"]].copy()
        result = ev.score(p, predictions, private, metadata, target_meta(p, "evaluation"))
        for v in result["contrasts"].values():
            self.assertEqual(v["mean_delta_r"], 0)
            self.assertEqual(v["paired_circular_shift_null_deltas"], [0, 0, 0])

    def test_no_evaluation_preprocessing_fit(self):
        p, features, train, _ = fixture()
        a, ma = ev.encode(p, features, train, target_meta(p, "train"))
        changed = copy.deepcopy(features)
        s = ev.selected_segments(p, ev.PEOPLE[0], "evaluation")[0]
        for key in s["feature_keys"].values():
            changed[key] += 1e5
        b, mb = ev.encode(p, changed, train, target_meta(p, "train"))
        untouched = ev.selected_segments(p, ev.PEOPLE[0], "evaluation")[1]["id"]
        for arm in ev.ARMS:
            np.testing.assert_array_equal(a[arm + "__" + untouched], b[arm + "__" + untouched])
        self.assertEqual(ma, mb)

    def test_train_only_target_interface_and_rank(self):
        p, features, train, private = fixture()
        with self.assertRaisesRegex(ev.ContractError, "wrong-split"):
            ev.encode(p, features, dict(train, **private), target_meta(p, "train"))
        zero = {key: np.zeros_like(a) for key, a in features.items()}
        with self.assertRaisesRegex(ev.ContractError, "rank"):
            ev.encode(p, zero, train, target_meta(p, "train"))

    def test_identity_split_guard_and_future_controls(self):
        p, _, _, _ = fixture()
        changes = [lambda q: q["participants"].pop(),
                   lambda q: q["segments"][1].update(film_id=q["segments"][0]["film_id"]),
                   lambda q: q.update(guard_tr=0),
                   lambda q: q.update(feature_context_right_tr=1),
                   lambda q: q.update(capacity_rank=True),
                   lambda q: q["segments"][1].update(null_offsets_tr=[0, 0, 0]),
                   lambda q: q["segments"][4].update(null_offsets_tr=[4, 5, 6]),
                   lambda q: q["parcel_ids"]["sub-01"].__setitem__(0, True)]
        for change in changes:
            bad = copy.deepcopy(p)
            change(bad)
            with self.subTest(change=change), self.assertRaises(ev.ContractError):
                ev.validate_protocol(bad)

    def test_malformed_outputs_and_parcel_alignment(self):
        p, features, train, private = fixture()
        predictions, metadata = ev.encode(p, features, train, target_meta(p, "train"))
        key = next(iter(predictions))
        for replacement in (np.ones_like(predictions[key]), predictions[key][:, :-1],
                            np.full_like(predictions[key], np.nan)):
            bad = dict(predictions)
            bad[key] = replacement
            with self.assertRaises(ev.ContractError):
                ev.score(p, bad, private, metadata, target_meta(p, "evaluation"))
        bad_meta = copy.deepcopy(metadata)
        bad_meta["parcel_ids"]["sub-01"].reverse()
        with self.assertRaisesRegex(ev.ContractError, "parcel"):
            ev.score(p, predictions, private, bad_meta, target_meta(p, "evaluation"))
        target = target_meta(p, "evaluation")
        target["parcel_ids"]["sub-01"].reverse()
        with self.assertRaisesRegex(ev.ContractError, "parcel"):
            ev.score(p, predictions, private, metadata, target)
        bad = dict(predictions)
        bad.pop(key)
        with self.assertRaisesRegex(ev.ContractError, "missing"):
            ev.score(p, bad, private, metadata, target_meta(p, "evaluation"))
        with self.assertRaisesRegex(ev.ContractError, "only numerical"):
            ev.score(p, predictions, private, metadata, target_meta(p, "evaluation"), [{"conclusion": "language wins"}])

    def test_equal_person_weight_not_timepoint_weight(self):
        p, _, _, private = fixture(6)
        predictions = {}
        for s in ev.selected_segments(p, split="evaluation"):
            y = np.tile(np.array([-3, -1, 1, 3.])[:, None], (1, 1000))
            if s["participant_id"] == "sub-05":
                s["n_samples"] = 10
                y = np.concatenate([y, y])
                private[s["id"]] = np.zeros((10, 1000))
            private[s["id"]][1:-1] = y
            for arm in ev.ARMS:
                predictions[arm + "__" + s["id"]] = y if (arm == "full" or s["participant_id"] != "sub-01") else -y
        result = ev.score(p, predictions, private, prediction_meta(p), target_meta(p, "evaluation"))
        self.assertAlmostEqual(result["contrasts"]["language"]["mean_delta_r"], .5)
        self.assertEqual(len(result["contrasts"]["language"]["person_deltas"]), 4)

    def test_cli_artifact_hashes_and_duplicate_json(self):
        p, features, train, private = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            ev.write_json(d / "protocol.json", p)
            for filename, arrays, split in (("train", train, "train"), ("private", private, "evaluation")):
                np.savez(d / (filename + ".npz"), **arrays)
                metadata = target_meta(p, split)
                metadata["npz_sha256"] = ev.sha256(d / (filename + ".npz"))
                ev.write_json(d / (filename + ".json"), metadata)
            np.savez(d / "features.npz", **features)
            command = [sys.executable, str(SOURCE), "encode", "--protocol", str(d / "protocol.json"),
                       "--features", str(d / "features.npz"), "--training-targets", str(d / "train.npz"),
                       "--training-target-metadata", str(d / "train.json"), "--output-dir", str(d / "encoded")]
            subprocess.run(command, check=True, capture_output=True)
            command = [sys.executable, str(SOURCE), "score", "--protocol", str(d / "protocol.json"),
                       "--predictions", str(d / "encoded/predictions.npz"), "--prediction-metadata", str(d / "encoded/prediction-metadata.json"),
                       "--private-targets", str(d / "private.npz"), "--private-target-metadata", str(d / "private.json"),
                       "--output", str(d / "score.json")]
            subprocess.run(command, check=True, capture_output=True)
            result = ev.load_json(d / "score.json")
            self.assertFalse(result["native_reference_reproduced"])
            with open(d / "encoded/predictions.npz", "ab") as stream:
                stream.write(b"tamper")
            rejected = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("hash mismatch", rejected.stderr)
            (d / "duplicate.json").write_text('{"task_id":1,"task_id":2}')
            with self.assertRaisesRegex(ev.ContractError, "duplicate JSON"):
                ev.load_json(d / "duplicate.json")


if __name__ == "__main__":
    unittest.main()
