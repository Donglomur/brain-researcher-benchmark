"""Generated complete-panel comparison controls; no authentic data or models."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare
import numpy as np
from test_generated import Fixture, encode, npy, panel, write


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="neural069-paired-", dir=Path(__file__).parent)
        cls.fixture = Fixture(Path(cls.temporary.name))
        f = cls.fixture
        cls.second = f.root / "second"
        cls.second.mkdir()
        rows = []
        for row in f.submission["predictions"]:
            # First is exact. Second reverses two ROIs in every participant:
            # current difference 1 - .5 = .5, historical difference 2/3.
            subject, roi = row["id"].split("/")
            values = f.truth[subject][roi] * (-1 if roi in ("lMT", "rMT") else 1)
            rows.append({"id": row["id"], **write(cls.second, row["path"], npy(values))})
        cls.second_value = {"task_id": "NEURAL-069", "roster_sha256": f.submission["roster_sha256"],
                            "predictions": rows}
        cls.second_path = cls.second / "submission.json"
        cls.second_path.write_bytes(encode(cls.second_value))
        cls.written_bytes = sum(p.stat().st_size for p in f.root.rglob("*") if p.is_file())

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({"generated_fixture_cumulative_writes": cls.written_bytes,
                          "retained_fixture_bytes": 0}, sort_keys=True), flush=True)
        cls.temporary.cleanup()

    def run_comparison(self, **kwargs):
        f = self.fixture
        return compare.compare(f.path, self.second_path, f.root, f.binding_sha, **kwargs)

    def test_full_pair_uses_current_equal_roi_weighting_and_loads_targets_once(self):
        loader = Mock(wraps=compare.score.load_targets)
        result = self.run_comparison(loader=loader)
        self.assertEqual(result["status"], "compared")
        self.assertAlmostEqual(result["score_difference"], .5)
        self.assertAlmostEqual(result["legacy_companion_difference"]["value"], 2 / 3)
        self.assertEqual(result["metric"], compare.score.METRIC)
        self.assertEqual(len(result["participants"]), 10)
        self.assertTrue(all(len(v["rois"]) == 8 for v in result["participants"].values()))
        self.assertAlmostEqual(result["participants"]["sub-10"]["rois"]["rMT"]["value"], 2)
        self.assertEqual(result["submissions"]["second"]["submission_sha256"],
                         hashlib.sha256(encode(self.second_value)).hexdigest())
        loader.assert_called_once()

    def test_reversing_the_pair_reverses_the_difference(self):
        f = self.fixture
        result = compare.compare(self.second_path, f.path, f.root, f.binding_sha)
        self.assertAlmostEqual(result["score_difference"], -.5)
        self.assertEqual(result["difference_direction"], "first_minus_second")

    def test_missing_reordered_wrong_roster_or_final_nonfinite_second_never_opens_targets(self):
        for fault in ("missing", "reordered", "roster", "nonfinite"):
            with self.subTest(fault=fault):
                value = copy.deepcopy(self.second_value)
                loader = Mock(side_effect=AssertionError("targets must remain closed"))
                if fault == "missing":
                    value["predictions"].pop()
                elif fault == "reordered":
                    value["predictions"].reverse()
                elif fault == "roster":
                    value["roster_sha256"] = "0" * 64
                else:
                    bad = np.ones((102, 1)); bad[-1, 0] = np.nan
                    raw = npy(bad)
                    original_capture = compare.score.validate_prediction_files.__globals__["_capture"]
                    record = value["predictions"][-1]
                    record.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                    def capture(name, *args, **kwargs):
                        second_root = (kwargs.get("dir_fd") is not None
                                       and os.fstat(kwargs["dir_fd"]).st_ino == self.second.stat().st_ino)
                        return ((raw, record["sha256"]) if name == record["path"] and second_root
                                else original_capture(name, *args, **kwargs))
                original = compare.score.capture_regular
                def submission_capture(path, *args, **kwargs):
                    if Path(path) == self.second_path:
                        raw_value = encode(value)
                        return raw_value, hashlib.sha256(raw_value).hexdigest()
                    return original(path, *args, **kwargs)
                with patch.object(compare.score, "capture_regular", side_effect=submission_capture):
                    if fault == "nonfinite":
                        with patch.dict(compare.score.validate_prediction_files.__globals__, {"_capture": capture}):
                            result = self.run_comparison(loader=loader)
                    else:
                        result = self.run_comparison(loader=loader)
                self.assertEqual(result["status"], "invalid_submission")
                self.assertEqual(set(result["invalid_submissions"]), {"second"})
                self.assertIsNone(result["score_difference"])
                loader.assert_not_called()

    def test_both_invalid_sides_are_identified_without_a_target_read(self):
        loader = Mock(side_effect=AssertionError("targets must remain closed"))
        with patch.object(compare, "admit", side_effect=compare.score.IOContractError("bad")):
            result = self.run_comparison(loader=loader)
        self.assertEqual(set(result["invalid_submissions"]), {"first", "second"})
        loader.assert_not_called()

    def test_undefined_last_roi_blocks_full_paired_score(self):
        truth = panel(); truth["sub-10"]["rSTS"][:] = .1
        result = self.run_comparison(loader=lambda _: truth)
        self.assertEqual(result["status"], "undefined_required_support")
        self.assertIsNone(result["score_difference"])
        self.assertEqual(result["paired_primary"]["support"]["undefined_component_ids"], ["sub-10"])
        self.assertIsNone(result["participants"]["sub-10"]["rois"]["rSTS"]["value"])

    def test_target_failure_remains_an_operator_failure(self):
        with self.assertRaisesRegex(compare.score.PacketError, "target fault"):
            self.run_comparison(loader=Mock(side_effect=compare.score.PacketError("target fault")))

    def test_cli_writes_comparison_and_refuses_existing_output(self):
        f = self.fixture
        output = f.root / "comparison.json"
        argv = ["compare.py", "--packet", str(f.root), "--binding-sha256", f.binding_sha,
                "--first", str(f.path), "--second", str(self.second_path), "--output", str(output)]
        with patch.object(sys, "argv", argv):
            self.assertEqual(compare.main(), 0)
            type(self).written_bytes += output.stat().st_size
            result = json.loads(output.read_text())
            self.assertAlmostEqual(result["score_difference"], .5)
            with self.assertRaisesRegex(SystemExit, "fresh output"):
                compare.main()


if __name__ == "__main__":
    print(json.dumps({"python": sys.version.split()[0], "numpy": np.__version__}, sort_keys=True), flush=True)
    unittest.main(verbosity=2)
