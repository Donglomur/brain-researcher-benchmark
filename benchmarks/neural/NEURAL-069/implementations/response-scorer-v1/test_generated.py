"""Small generated full-panel controls; never reads authentic data or fits models."""
from __future__ import annotations
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import score


def encode(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def write(root, path, raw):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def npy(array):
    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    return buffer.getvalue()


def panel():
    vector = np.arange(102, dtype=np.float64)[:, None]
    return {s: {r: vector.copy() for r in score.ROIS} for s in score.SUBJECTS}


class Fixture:
    def __init__(self, root):
        self.root = root
        self.candidate = root / "candidate"
        self.candidate.mkdir()
        self.truth = panel()
        cases, operators, outputs = [], [], []
        for subject in score.SUBJECTS:
            for roi in score.ROIS:
                identifier = f"{subject}/{roi}"
                stem = f"{subject}_{roi}.npy"
                data = npy(self.truth[subject][roi])
                target = write(root, "private/targets/" + stem, data)
                cases.append({"id": identifier, "subject": subject, "roi": roi,
                              "voxels": 1, "coordinates": [[1, 2, 3]]})
                operators.append({"id": identifier, "target": target})
                outputs.append({"id": identifier, **write(self.candidate, stem, data)})
        self.roster = {"schema": "boldmoments-public-roster-v1", "subjects": list(score.SUBJECTS),
                       "families": {k: list(v) for k, v in score.FAMILIES.items()},
                       "train_video_ids": [f"vid{i:04}" for i in range(1, 1001)],
                       "query_video_ids": [f"vid{i:04}" for i in range(1001, 1103)],
                       "training_repeats": 3, "query_repeats": 10, "cases": cases}
        self.binding = {"schema": "boldmoments-private-binding-v1", "cases": operators}
        self.submission = {"task_id": "NEURAL-069", "predictions": outputs}
        self.save_metadata()

    def save_metadata(self):
        self.binding["roster"] = write(self.root, "public/input/ROSTER.json", encode(self.roster))
        self.binding_sha = write(self.root, "private/DATA_BINDING.json", encode(self.binding))["sha256"]
        self.submission["roster_sha256"] = self.binding["roster"]["sha256"]
        self.save_submission()

    def save_submission(self):
        self.path = self.candidate / "submission.json"
        self.path.write_bytes(encode(self.submission))


class Controls(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix="neural069-generated-")
        self.addCleanup(temporary.cleanup)
        return Fixture(Path(temporary.name))

    def test_current_roi_weighting_is_not_historical_family_weighting(self):
        truth = panel()
        prediction = copy.deepcopy(truth)
        for subject in score.SUBJECTS:
            for roi in score.ROIS[4:]:
                prediction[subject][roi] *= -1
        result = score.score_arrays(truth, prediction)
        # Four V1 cells are +1; four MT/STS cells -1. Current eight-cell mean
        # is zero; historical three-family mean is (1 - 1 - 1)/3.
        self.assertAlmostEqual(result["primary"]["value"], 0)
        self.assertAlmostEqual(result["legacy_companion"]["value"], -1 / 3)
        self.assertEqual(result["metric"], score.METRIC)

    def test_roi_weights_are_equal_despite_voxel_count(self):
        truth, prediction = panel(), panel()
        for subject in score.SUBJECTS:
            truth[subject]["rV1v"] = np.repeat(truth[subject]["rV1v"], 9, axis=1)
            prediction[subject]["rV1v"] = -truth[subject]["rV1v"]
        result = score.score_arrays(truth, prediction)
        self.assertAlmostEqual(result["primary"]["value"], .75)
        self.assertAlmostEqual(result["legacy_companion"]["value"], .5)

    def test_participant_macro_and_raw_error(self):
        truth, prediction = panel(), panel()
        for roi in score.ROIS:
            prediction["sub-10"][roi] *= -1
        result = score.score_arrays(truth, prediction)
        self.assertAlmostEqual(result["primary"]["value"], .8)
        self.assertAlmostEqual(result["raw_mse"]["value"], 4 * sum(i * i for i in range(102)) / 1020)

    def test_last_constant_truth_blocks_complete_endpoint(self):
        truth, prediction = panel(), panel()
        truth["sub-10"]["rSTS"][:] = .1
        result = score.score_arrays(truth, prediction)
        self.assertIsNone(result["primary"]["value"])
        self.assertEqual(result["primary"]["support"]["undefined_component_ids"], ["sub-10"])
        self.assertEqual(result["participants"]["sub-10"]["rois"]["rSTS"]["support"]["dispositions"],
                         {"constant_truth": 1})

    def test_constant_prediction_zero_and_affine_correlation(self):
        truth, prediction = panel(), panel()
        for subject in score.SUBJECTS:
            for roi in score.ROIS:
                prediction[subject][roi] = 7 * truth[subject][roi] + 19
        result = score.score_arrays(truth, prediction)
        self.assertAlmostEqual(result["primary"]["value"], 1)
        self.assertGreater(result["raw_mse"]["value"], 0)
        for subject in score.SUBJECTS:
            for roi in score.ROIS:
                prediction[subject][roi][:] = .1
        self.assertEqual(score.score_arrays(truth, prediction)["primary"]["value"], 0)

    def test_complete_disk_packet_scores(self):
        f = self.fixture()
        result = score.grade(f.path, f.root, f.binding_sha)
        self.assertEqual(result["status"], "scored")
        self.assertAlmostEqual(result["score"], 1)
        self.assertEqual(len(result["analysis"]["participants"]), 10)

    def test_final_nan_and_object_files_rejected_before_target_callback(self):
        for dtype in (np.float64, object):
            with self.subTest(dtype=dtype):
                f = self.fixture()
                bad = np.ones((102, 1), dtype=dtype)
                if dtype is np.float64:
                    bad[-1, -1] = np.nan
                    raw = npy(bad)
                else:
                    buffer = io.BytesIO()
                    np.save(buffer, bad, allow_pickle=True)
                    raw = buffer.getvalue()
                record = f.submission["predictions"][-1]
                record.update(write(f.candidate, record["path"], raw))
                f.save_submission()
                loader = Mock(side_effect=AssertionError("targets must stay closed"))
                result = score.grade(f.path, f.root, f.binding_sha, loader=loader)
                self.assertEqual(result["status"], "invalid_submission")
                loader.assert_not_called()

    def test_prediction_missing_reordered_or_wrong_roster_rejected(self):
        for change in ("missing", "reordered", "roster", "path", "shape"):
            with self.subTest(change=change):
                f = self.fixture()
                if change == "missing":
                    f.submission["predictions"].pop()
                elif change == "reordered":
                    f.submission["predictions"].reverse()
                elif change == "roster":
                    f.submission["roster_sha256"] = "0" * 64
                elif change == "path":
                    f.submission["predictions"][-1]["path"] = "../target.npy"
                else:
                    record = f.submission["predictions"][-1]
                    record.update(write(f.candidate, record["path"], npy(np.ones((101, 1)))))
                f.save_submission()
                loader = Mock(side_effect=AssertionError("targets must stay closed"))
                self.assertEqual(score.grade(f.path, f.root, f.binding_sha, loader=loader)["status"],
                                 "invalid_submission")
                loader.assert_not_called()

    def test_external_binding_pin_required(self):
        f = self.fixture()
        with self.assertRaisesRegex(score.PacketError, "binding pin"):
            score.read_contract(f.root, "0" * 64)

    def test_video_coordinate_repeat_and_case_joins_rejected(self):
        for change in ("video", "coordinates", "repeat", "case"):
            with self.subTest(change=change):
                f = self.fixture()
                if change == "video":
                    f.roster["query_video_ids"].reverse()
                elif change == "coordinates":
                    f.roster["cases"][-1]["coordinates"] = [[1, -2, 3]]
                elif change == "repeat":
                    f.roster["query_repeats"] = 9
                else:
                    f.binding["cases"].pop()
                f.save_metadata()
                with self.assertRaises(score.PacketError):
                    score.read_contract(f.root, f.binding_sha)

    def test_target_pin_failure_is_operator_error(self):
        f = self.fixture()
        f.binding["cases"][-1]["target"]["sha256"] = "0" * 64
        f.save_metadata()
        with self.assertRaisesRegex(score.PacketError, "file pin"):
            score.grade(f.path, f.root, f.binding_sha)

    def test_undefined_support_has_distinct_status(self):
        f = self.fixture()
        f.truth["sub-10"]["rSTS"][:] = .1
        result = score.grade(f.path, f.root, f.binding_sha, loader=lambda _: f.truth)
        self.assertEqual(result["status"], "undefined_required_support")
        self.assertIsNone(result["score"])

    def test_extreme_float_pearson_and_unrepresentable_error(self):
        y = np.array([-1e308, 1e308, 0., 2e307])[:, None]
        self.assertAlmostEqual(score.pearson_columns(y, -y)["value"], -1)
        self.assertIsNone(score.raw_mse(y, -y)["value"])
        y = np.array([0., 1e-320, 2e-320, -1e-320])[:, None]
        self.assertAlmostEqual(score.pearson_columns(y, y)["value"], 1)
        self.assertEqual(score.raw_mse(y, -y)["reason"], "squared_error_underflow")


if __name__ == "__main__":
    print(json.dumps({"python": sys.version.split()[0], "numpy": np.__version__,
                      "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in sorted(Path(__file__).parent.glob("*.py"))}},
                     sort_keys=True), flush=True)
    unittest.main(verbosity=2)
