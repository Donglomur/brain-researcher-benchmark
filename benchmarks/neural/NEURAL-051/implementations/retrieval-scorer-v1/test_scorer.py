"""Generated controls only: no authentic responses, source roster or targets."""
import copy
import hashlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("n051_scorer", HERE / "scorer.py")
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def fixture():
    candidates = [f"i{i:024x}" for i in range(3700)]
    concepts = [f"c{i}" for i in range(720) for _ in range(5 if i < 620 else 6)]
    roster, cases = {}, []
    for person in scorer.SUBJECTS:
        queries = []
        for i in range(1540):
            trials = [8200 + i] if i < 1440 else [9640 + 2 * (i - 1440), 9641 + 2 * (i - 1440)]
            queries.append({"id": f"q{int(person) * 10000 + i:024x}",
                            "candidate_index": i, "trial_ids": trials})
        for roi in scorer.ROIS:
            key = f"sub-{person}_{roi}"
            roster[key] = {"candidate_ids": candidates.copy(), "query_ids": [q["id"] for q in queries]}
            cases.append({"id": key, "person": person, "roi": roi, "queries": copy.deepcopy(queries)})
    return roster, {"schema": "neural051-design-v1", "full_canonical_split": True,
                    "candidate_ids": candidates, "candidate_concepts": concepts, "cases": cases}


class RetrievalControls(unittest.TestCase):
    def test_ties_against_all_candidate_permutations(self):
        # Independent enumeration of every legal tie order, including the Top5 boundary.
        for values, target in [([1.] * 6, 2), ([3., 2., 2., 2., 2., 2.], 4),
                               ([3., 2., 1., 0., 0., 0.], 5), ([1., 4., 3., 2., 0., -1.], 1)]:
            ranks = []
            for order in itertools.permutations(range(len(values))):
                if all(values[order[i]] >= values[order[i + 1]] for i in range(len(values) - 1)):
                    ranks.append(order.index(target) + 1)
            got = scorer.rank_metrics(np.array(values), target)
            self.assertAlmostEqual(got["top1"], sum(r == 1 for r in ranks) / len(ranks))
            self.assertAlmostEqual(got["top5"], sum(r <= 5 for r in ranks) / len(ranks))
            self.assertAlmostEqual(got["mrr"], sum(1 / r for r in ranks) / len(ranks))
            legacy = scorer._protocol.expected_rank_metrics(values, target)
            self.assertAlmostEqual(got["top1"], legacy[0])
            self.assertAlmostEqual(got["mrr"], legacy[1])

    def test_score_row_rejections(self):
        for row, target in [(np.array([np.nan]), 0), (np.array([np.inf]), 0),
                            (np.array([1., 0.]), -1), (np.array([1., 0.]), True),
                            (np.array([1, 0]), 0), (np.array([[1.]]), 0)]:
            with self.subTest(row=row, target=target), self.assertRaises(ValueError):
                scorer.rank_metrics(row, target)

    def test_paired_image_mapping_disagreement_rejected(self):
        roster, design = fixture()
        queries = design["cases"][1]["queries"]
        queries[0]["candidate_index"], queries[1]["candidate_index"] = 1, 0
        with self.assertRaisesRegex(ValueError, "paired ROI"):
            scorer.validate_design(roster, design)

    def test_paired_trial_mapping_disagreement_rejected(self):
        roster, design = fixture()
        queries = design["cases"][1]["queries"]
        queries[0]["trial_ids"], queries[1]["trial_ids"] = queries[1]["trial_ids"], queries[0]["trial_ids"]
        with self.assertRaisesRegex(ValueError, "paired ROI"):
            scorer.validate_design(roster, design)

    def test_duplicate_native_trial_rejected(self):
        roster, design = fixture()
        design["cases"][0]["queries"][1]["trial_ids"] = [8200]
        with self.assertRaisesRegex(ValueError, "unique native"):
            scorer.validate_design(roster, design)

    def test_complete_concept_census_required(self):
        roster, design = fixture()
        design["candidate_concepts"][-1] = "generated-extra-concept"
        with self.assertRaisesRegex(ValueError, "720-concept"):
            scorer.validate_design(roster, design)

    def test_roster_duplicate_and_paired_order_rejected(self):
        roster, _ = fixture()
        roster["sub-01_V1"]["query_ids"][1] = roster["sub-01_V1"]["query_ids"][0]
        with self.assertRaises(ValueError):
            scorer.validate_roster(roster)
        roster, _ = fixture()
        roster["sub-03_IT"]["query_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "paired ROI"):
            scorer.validate_roster(roster)

    def test_full_shape_array_parser(self):
        array = np.zeros(scorer.SHAPE, dtype=np.float32)
        stream = io.BytesIO()
        np.save(stream, array, allow_pickle=False)
        raw = stream.getvalue()
        self.assertEqual(scorer.load_array(raw).shape, scorer.SHAPE)
        with self.assertRaisesRegex(ValueError, "exact payload"):
            scorer.load_array(raw + b"x")
        array[0, 0] = np.nan
        stream = io.BytesIO()
        np.save(stream, array, allow_pickle=False)
        with self.assertRaisesRegex(ValueError, "finite"):
            scorer.load_array(stream.getvalue())

    def test_complete_artifact_path_and_target_last(self):
        roster, design = fixture()
        # All six independent files, all 9,240 generated query rows, actual NPY parser.
        hits = dict(zip(scorer.CASES, [0, 1540, 770, 770, 1540, 0]))
        with tempfile.TemporaryDirectory(prefix="neural051-generated-") as directory:
            root = Path(directory).resolve()
            files = {}
            for case in scorer.CASES:
                scores = np.zeros(scorer.SHAPE, dtype=np.float32)
                target = np.arange(1540)
                chosen = np.where(target < hits[case], target, (target + 1) % 3700)
                scores[target, chosen] = 1
                path = root / (case + ".npy")
                np.save(path, scores, allow_pickle=False)
                files[case] = {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            manifest = {"schema": "neural051-scores-v1", "files": files,
                        "roster_sha256": scorer.roster_digest(roster)}
            (root / "submission.json").write_text(json.dumps(manifest))
            calls = []
            def private_loader():
                calls.append(True)
                return design
            result = scorer.evaluate(root, manifest, roster, private_loader)
            self.assertEqual(result["status"], "scored")
            self.assertEqual(len(calls), 1)
            self.assertEqual(result["primary"], {"V1": .5, "IT": .5})
            self.assertEqual(result["historical_primary"], .5)
            self.assertEqual(result["biological_units"], 3)
            self.assertEqual([result["paired_IT_minus_V1"][p]["top1"] for p in scorer.SUBJECTS], [1., 0., -1.])
            self.assertEqual(sum(c["all_images"]["images"] for c in result["cases"].values()), 9240)
            self.assertEqual(result["cases"]["sub-01_IT"]["two_repeat_mean"]["images"], 100)
            # Late failure in the sixth case still prevents ANY private loader access.
            calls.clear()
            with (root / (scorer.CASES[-1] + ".npy")).open("ab") as handle:
                handle.write(b"trailing")
            invalid = scorer.evaluate(root, manifest, roster, private_loader)
            self.assertEqual(invalid["status"], "invalid_submission")
            self.assertFalse(invalid["private_reference_invoked"])
            self.assertEqual(calls, [])

    def test_operator_error_is_distinct_from_submission_failure(self):
        roster, _ = fixture()
        roster.pop("sub-01_IT")
        result = scorer.evaluate("unopened", {}, roster, lambda: self.fail("private read"))
        self.assertEqual(result["status"], "operator_error")
        roster, _ = fixture()
        result = scorer.evaluate("unopened", {}, roster, lambda: self.fail("private read"))
        self.assertEqual(result["status"], "invalid_submission")


class CliFailureControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="neural051-cli-generated-")
        cls.root = Path(cls.temporary.name).resolve()
        roster, _ = fixture()
        cls.roster = cls.root / "roster.json"
        cls.roster.write_text(json.dumps(roster, separators=(",", ":")))
        cls.roster_sha = hashlib.sha256(cls.roster.read_bytes()).hexdigest()
        cls.submission = cls.root / "submission"
        cls.submission.mkdir()
        cls.private_design = cls.root / "never-created-private-design.json"

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def invoke(self, roster_path, roster_sha, manifest, output_name):
        (self.submission / "submission.json").write_bytes(manifest)
        output = self.root / output_name
        arguments = ["scorer.py", "--submission", str(self.submission),
                     "--roster", str(roster_path), "--roster-sha256", roster_sha,
                     "--design", str(self.private_design), "--design-sha256", "0" * 64,
                     "--output", str(output)]
        capture = scorer._io.capture
        def observed_capture(path, *args, **kwargs):
            self.assertNotEqual(Path(path), self.private_design, "private design opened on invalid input")
            return capture(path, *args, **kwargs)
        with mock.patch.object(sys, "argv", arguments), mock.patch.object(scorer._io, "capture", observed_capture):
            code = scorer.main()
        return code, json.loads(output.read_text())

    def test_nested_submission_is_reported_without_private_read(self):
        raw = b"[" * 3000 + b"0" + b"]" * 3000
        self.assertLess(len(raw), 10_000)
        code, result = self.invoke(self.roster, self.roster_sha, raw, "nested-submission.json")
        self.assertEqual(code, 1)
        self.assertEqual(result, {"status": "invalid_submission", "primary": None,
                                  "private_reference_invoked": False})

    def test_nested_operator_roster_keeps_operator_classification(self):
        raw = b"[" * 3000 + b"0" + b"]" * 3000
        roster = self.root / "nested-roster.json"
        roster.write_bytes(raw)
        code, result = self.invoke(roster, hashlib.sha256(raw).hexdigest(), b"{}", "nested-operator.json")
        self.assertEqual(code, 2)
        self.assertEqual(result, {"status": "operator_error", "primary": None,
                                  "private_reference_invoked": False})

    def test_ordinary_invalid_manifest_retains_existing_report(self):
        code, result = self.invoke(self.roster, self.roster_sha, b"{}", "ordinary-invalid.json")
        self.assertEqual(code, 1)
        self.assertEqual(result, {"status": "invalid_submission", "primary": None,
                                  "private_reference_invoked": False})


if __name__ == "__main__":
    unittest.main(verbosity=2)
