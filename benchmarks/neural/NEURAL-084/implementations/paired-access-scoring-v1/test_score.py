"""Generated complete-cohort paired controls; no EEG/model/authentic execution."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("paired_score", HERE / "score.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PairedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(os.environ.get("NEURAL084_SOURCE_IMPLEMENTATIONS", HERE.parent))
        spec = importlib.util.spec_from_file_location(
            "generated_existing_fixture", root / "full-cohort-scoring-v1/test_score.py")
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        fixture.FullCohortTests.setUpClass()
        cls.f = fixture.FullCohortTests
        cls.outputs = {mode: cls.f.outputs[mode] for mode in p.MODES[2:]}
        cls.outputs.update(restricted={}, program={})
        cls.expected = {}
        for person in p.s.PEOPLE:
            fold = "fold%03d" % person
            rows = {mode: [] for mode in ("restricted", "program")}
            counts = dict(both_correct=0, restricted_only=0, program_only=0, neither_correct=0)
            for index, row in enumerate(cls.f.folds[fold]):
                correct = dict(restricted=(index + person) % 4 != 0,
                               program=(index + 2 * person) % 5 != 0)
                for mode in rows:
                    winner = row["label"] if correct[mode] else row["label"] % 4 + 1
                    scores = [-9] * 4
                    scores[winner - 1] = -1
                    rows[mode].append(dict(id=row["id"], scores=scores))
                key = ("both_correct" if all(correct.values()) else "restricted_only"
                       if correct["restricted"] else "program_only" if correct["program"]
                       else "neither_correct")
                counts[key] += 1
            cls.expected[person] = counts
            for mode, predictions in rows.items():
                cls.outputs[mode][fold] = p.io.canonical(dict(schema="neural084_scores_v1",
                    generation=cls.f.gen, fold=fold, predictions=predictions))

    def load(self, mode, fold):
        return self.outputs[mode][fold]

    def test_complete_pair_and_independent_integer_oracle(self):
        calls = []
        def load(mode, fold):
            calls.append((mode, fold))
            return self.load(mode, fold)
        def gold(pin):
            self.assertEqual(len(calls), 270)
            self.assertEqual(pin, p.io.pin(self.f.gold_raw))
            return self.f.gold_raw
        result = p.grade(self.f.pool_raw, load, gold)
        pair = result["comparisons"]["program_minus_restricted"]
        self.assertAlmostEqual(pair["mean"], .05)
        self.assertEqual(len(pair["phases"]), 216)
        self.assertEqual(len(pair["sessions"]), 108)
        self.assertEqual(len(pair["people"]), 54)
        self.assertEqual(result["modes"]["restricted"]["score"], .75)
        self.assertEqual(result["modes"]["program"]["score"], .8)
        matched = result["matched_correctness"]
        for row in matched["people"]:
            expected = self.expected[row["person"]]
            self.assertEqual({key: row[key] for key in expected}, expected)
            self.assertEqual(sum(expected.values()), 400)
            self.assertAlmostEqual(pair["people"][row["person"] - 1]["difference"],
                (expected["program_only"] - expected["restricted_only"]) / 400)
        self.assertEqual(sum(matched[key] for key in self.expected[1]), 21600)
        self.assertAlmostEqual((matched["program_only"] - matched["restricted_only"]) / 21600,
                               pair["mean"])
        for candidate in ("restricted", "program"):
            for control, score in (("cca", 1), ("constant", .25), ("frequency-permuted", 0)):
                self.assertAlmostEqual(result["comparisons"][candidate + "_minus_" + control]["mean"],
                                       result["modes"][candidate]["score"] - score)
        self.assertEqual(result["source"]["predictions"]["program"]["fold054"],
                         p.io.pin(self.outputs["program"]["fold054"]))
        self.assertEqual(result["comparison_scope"]["information_equivalence"],
                         "not_established_by_scoring")
        self.assertNotIn(self.f.rows[0]["id"], p.io.canonical(result).decode())

    def test_incomplete_or_late_malformed_condition_blocks_gold(self):
        for target in (("restricted", "fold054"), ("program", "fold054"),
                       ("frequency-permuted", "fold054")):
            def load(mode, fold):
                if (mode, fold) == target:
                    value = p.io.decode(self.load(mode, fold))
                    value["predictions"].pop()
                    return p.io.canonical(value)
                return self.load(mode, fold)
            with self.subTest(target=target), self.assertRaises(ValueError):
                p.grade(self.f.pool_raw, load, lambda _: self.fail("Gold opened before complete pair"))

    def test_cross_condition_generation_or_case_mismatch_blocks_gold(self):
        for change in (lambda v: v.update(generation="other"),
                       lambda v: v["predictions"].reverse()):
            def load(mode, fold):
                raw = self.load(mode, fold)
                if (mode, fold) == ("program", "fold054"):
                    value = p.io.decode(raw)
                    change(value)
                    return p.io.canonical(value)
                return raw
            with self.assertRaises(ValueError):
                p.grade(self.f.pool_raw, load, lambda _: self.fail("Gold opened on unmatched pair"))

    def test_captured_predictions_are_not_reread_after_gold(self):
        opened = False
        def load(mode, fold):
            self.assertFalse(opened)
            return self.load(mode, fold)
        def gold(_):
            nonlocal opened
            opened = True
            return self.f.gold_raw
        result = p.grade(self.f.pool_raw, load, gold)
        self.assertTrue(opened)
        self.assertAlmostEqual(result["comparisons"]["program_minus_restricted"]["mean"], .05)

    def test_cli_routes_five_complete_directories_and_exclusive_output(self):
        # Real CLI, directory preflight, evaluation and report output. Prediction,
        # pool and gold bytes use an in-memory IO adapter to avoid a 16MB fixture
        # export. Existing bounded-read transport is unchanged and is not retested.
        with tempfile.TemporaryDirectory(dir=os.environ.get("NEURAL084_TEST_TMP")) as directory:
            root = Path(directory).resolve()
            pin = p.io.pin(self.f.pool_raw)
            args = ["--pool", str(root / "pool.json"), "--pool-bytes", str(pin["bytes"]),
                    "--pool-sha256", pin["sha256"], "--out", str(root / "report.json")]
            for mode in p.MODES:
                folder = root / mode
                folder.mkdir()
                for person in p.s.PEOPLE:
                    (folder / ("fold%03d.json" % person)).touch()
                args += ["--" + mode, str(folder)]
            reads = []
            def read(path, cap, expected=None):
                reads.append(path)
                if path.name == "pool.json":
                    self.assertEqual(expected, pin)
                    return self.f.pool_raw
                if path.name == "gold.json":
                    self.assertEqual(len(reads), 272)
                    self.assertEqual(expected, p.io.pin(self.f.gold_raw))
                    return self.f.gold_raw
                return self.outputs[path.parent.name][path.stem]
            with mock.patch.object(p.io, "read", read):
                self.assertEqual(p.main(args), 0)
                result = p.io.decode((root / "report.json").read_bytes())
                print("generated CLI report bytes:", (root / "report.json").stat().st_size)
                self.assertEqual(result["counts"]["modes"], 5)
                reads.clear()
                with self.assertRaises(FileExistsError):
                    p.main(args)
                (root / "program/fold054.json").unlink()
                reads.clear()
                with self.assertRaises(ValueError):
                    p.main(args)
                self.assertEqual(len(reads), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
