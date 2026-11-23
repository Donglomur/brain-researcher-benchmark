"""Generated metadata controls; no authentic MAT files or MATLAB execution."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "prepare_summary", Path(__file__).resolve().with_name("prepare_summary.py"))
preparer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparer)
load_inputs, prepare = preparer.load_inputs, preparer.prepare


class SummaryPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.records = [
            {"mouse_id": "mouse-z", "location_id": "site-1", "unitmatch_file": "one/UnitMatch.mat"},
            {"mouse_id": "mouse-a", "location_id": "site-1", "unitmatch_file": "two/UnitMatch.mat"},
            {"mouse_id": "mouse-z", "location_id": "site-'2", "unitmatch_file": "three's/UnitMatch.mat"},
        ]
        for row in self.records:
            target = self.root / row["unitmatch_file"]
            target.parent.mkdir()
            target.write_bytes(b"generated placeholder; not a MAT payload")

    def encoded(self, records=None):
        return json.dumps({"schema": "unitmatch-summary-roster/v1",
                           "records": self.records if records is None else records}).encode()

    def test_grouping_and_exact_roster_capture(self):
        roster = self.root / "selected.json"
        raw = self.encoded()
        roster.write_bytes(raw)
        output = self.root / "prepared"
        result = prepare(roster, self.root, output)
        self.assertEqual(result["group_vector"], [1, 2, 1])
        self.assertEqual((result["mice"], result["locations"]), (2, 3))
        self.assertFalse(result["matlab_executed"])
        self.assertFalse(result["original_cohort_qualified"])
        self.assertEqual((output / "roster.json").read_bytes(), raw)
        script = (output / "run_summary.m").read_text()
        self.assertIn("groupVector = [1 2 1];", script)
        self.assertIn("three''s/UnitMatch.mat", script)
        self.assertIn("'site-''2'", script)
        self.assertIn("res = summaryFunctionalPlots(UMFiles, 'Corr', groupVector, 0, 0);", script)
        self.assertIn("'groupVector', 'resolvedSummaryFunction', '-v7.3'", script)
        self.assertFalse((output / "native_summary.mat").exists())
        with self.assertRaises(FileExistsError):
            prepare(roster, self.root, output)

    def test_missing_file_refused_before_output(self):
        (self.root / self.records[1]["unitmatch_file"]).unlink()
        roster = self.root / "selected.json"
        roster.write_bytes(self.encoded())
        with self.assertRaises(FileNotFoundError):
            prepare(roster, self.root, self.root / "prepared")
        self.assertFalse((self.root / "prepared").exists())

    def test_repeated_location_and_repeated_file_refused(self):
        for field in ("identity", "file"):
            with self.subTest(field=field):
                records = copy.deepcopy(self.records)
                if field == "identity":
                    records[1]["mouse_id"] = records[0]["mouse_id"]
                else:
                    records[1]["unitmatch_file"] = records[0]["unitmatch_file"]
                with self.assertRaisesRegex(ValueError, "duplicate|more than once"):
                    load_inputs(self.encoded(records), self.root)

    def test_file_alias_refused(self):
        target = self.root / self.records[1]["unitmatch_file"]
        target.unlink()
        os.link(self.root / self.records[0]["unitmatch_file"], target)
        with self.assertRaisesRegex(ValueError, "more than once"):
            load_inputs(self.encoded(), self.root)

    def test_outside_root_and_unsafe_paths_refused(self):
        for path in ("../UnitMatch.mat", "/tmp/UnitMatch.mat", "one//UnitMatch.mat",
                     "one/./UnitMatch.mat", "one\\UnitMatch.mat", "one/data.mat"):
            with self.subTest(path=path):
                records = copy.deepcopy(self.records)
                records[0]["unitmatch_file"] = path
                with self.assertRaises(ValueError):
                    load_inputs(self.encoded(records), self.root)
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "UnitMatch.mat").write_bytes(b"generated")
        inner = self.root / "inner"
        inner.mkdir()
        (inner / "link").symlink_to(outside, target_is_directory=True)
        row = {"mouse_id": "x", "location_id": "y", "unitmatch_file": "link/UnitMatch.mat"}
        with self.assertRaisesRegex(ValueError, "outside"):
            load_inputs(self.encoded([row]), inner)

    def test_empty_or_malformed_roster_and_control_characters_refused(self):
        for value in (b'[]', b'{}', self.encoded([]),
                      b'{"schema":"unitmatch-summary-roster/v1","records":[],"records":[]}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                load_inputs(value, self.root)
        records = copy.deepcopy(self.records)
        records[0]["mouse_id"] = "x\n; disp('unwanted')"
        with self.assertRaisesRegex(ValueError, "control character"):
            load_inputs(self.encoded(records), self.root)

    def test_empty_or_directory_mat_file_refused(self):
        target = self.root / self.records[0]["unitmatch_file"]
        target.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "nonempty regular"):
            load_inputs(self.encoded(), self.root)
        target.unlink()
        target.mkdir()
        with self.assertRaisesRegex(ValueError, "nonempty regular"):
            load_inputs(self.encoded(), self.root)


if __name__ == "__main__":
    unittest.main()
