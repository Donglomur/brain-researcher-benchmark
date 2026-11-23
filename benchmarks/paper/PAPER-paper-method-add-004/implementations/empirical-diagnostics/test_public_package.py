"""Public packaging controls: generated JSON only, complete required support."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
METHODS = ("acf_full", "isttc_full", "pearsonr_trial_avg", "sttc_trial_concat")
AREAS = ("LGd", "VISp", "VISl", "VISrl", "LP", "VISal", "VISpm", "VISam")


def write_cohort(path, count=5775):
    with path.open("w") as out:
        out.write('{"schema":"isttc_empirical_cohort_v1","source_sha256":"' + "0"*64 + '","units":[')
        for i in range(count):
            if i: out.write(",")
            json.dump(dict(unit_id="generated-unit-"+str(i), mouse_id="generated-mouse-"+str(i%26),
                           session_id="generated-session", area=AREAS[i % len(AREAS)],
                           fr_hz=3.0, lv=0.8), out)
        out.write("]}")


def write_estimates(path, missing=False):
    with path.open("w") as out:
        out.write('{"schema":"isttc_empirical_estimates_v1","rows":[')
        for i in range(5775):
            for k, method in enumerate(METHODS):
                if i or k: out.write(",")
                absent = missing and i == 5774 and k == 3
                json.dump(dict(unit_id="generated-unit-"+str(i), method=method,
                               tau_bins=None if absent else 2.0+k, r_squared=0.7,
                               failure_reason="generated failure" if absent else None), out)
        out.write("]}")


class Packaging(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="isttc public ")
        self.root = Path(self.temp.name).resolve()
        self.package = self.root / "relocated component with spaces"
        shutil.copytree(HERE, self.package, ignore=shutil.ignore_patterns("__pycache__"))
        self.cwd = self.root / "unrelated cwd"
        self.cwd.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *args):
        return subprocess.run([sys.executable, "-I", "-S", "-B",
                               str(self.package / "empirical_bridge.py"), *map(str, args)],
                              cwd=self.cwd, capture_output=True, timeout=30, check=False)

    def test_source_membership_pins_and_privacy(self):
        doc = json.loads((self.package / "SOURCE.json").read_bytes())
        self.assertEqual(doc["schema"], "isttc_empirical_public_source_v1")
        self.assertFalse(doc["authentic_execution_qualified"])
        files = {p.name for p in self.package.iterdir() if p.is_file()}
        self.assertEqual(set(doc["files"]), files-{"SOURCE.json"})
        for name, expected in doc["files"].items():
            b = (self.package/name).read_bytes()
            self.assertEqual({"bytes":len(b), "sha256":hashlib.sha256(b).hexdigest()}, expected)
            text = b.decode()
            for forbidden in ("/"+"Users/", "benchmark-"+"engineering-evidence",
                              "authoring/"+"delivery-", "X-Amz-"+"Signature="):
                self.assertNotIn(forbidden, text, name)
        self.assertEqual(hashlib.sha256((self.package/"empirical_bridge.py").read_bytes()).hexdigest(),
                         "63d41e13b7300f6ba1dc845be9c7fb7dba167c4b44c99b2f869930f42522dd40")

    def test_relocated_help(self):
        result = self.call("--help")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"windows,reduce,compare", result.stdout)

    def test_relocated_full_window_cli(self):
        cohort = self.root/"cohort.json"; output = self.root/"windows.jsonl"
        write_cohort(cohort)
        result = self.call("windows","--cohort",cohort,"--seed","7","--output",output)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b"")
        count=0
        with output.open() as rows:
            for i, line in enumerate(rows):
                row=json.loads(line)
                self.assertEqual(row["unit_id"],"generated-unit-"+str(i))
                self.assertEqual(row["replicate"],0)
                self.assertEqual(row["seed"],7)
                self.assertEqual(row["fs_hz"],30000)
                self.assertEqual(len(row["windows_ticks"]),40)
                for start,end in row["windows_ticks"]:
                    self.assertEqual(end-start,30000)
                    self.assertGreaterEqual(start,0)
                    self.assertLessEqual(end,54000000)
                count+=1
        self.assertEqual(count,5775)

    def test_relocated_full_compare_missing_support(self):
        cohort=self.root/"cohort.json";candidate=self.root/"candidate.json"
        reference=self.root/"reference.json";output=self.root/"comparison.jsonl"
        write_cohort(cohort);write_estimates(reference);write_estimates(candidate,missing=True)
        result=self.call("compare","--cohort",cohort,"--estimates",candidate,
                         "--reference",reference,"--output",output)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        with output.open() as handle:
            report=json.loads(handle.readline())
            self.assertEqual(handle.read(),"")
        self.assertEqual(report["units"],5775)
        self.assertEqual(report["method_coordinates"],23100)
        self.assertFalse(report["full_output_support_matched"])
        self.assertEqual(len(report["availability_mismatches"]),1)
        for value in report["errors_by_quantity"].values():
            self.assertFalse(value["comparable"])
            self.assertIsNone(value["mean_absolute_difference"])
            self.assertIsNone(value["maximum_absolute_difference"])
        self.assertIsNone(report["scientific_pass"])
        self.assertEqual(report["candidate_reduction"]["counts"]["complete_cases"],5774)
        self.assertEqual(report["reference_reduction"]["counts"]["complete_cases"],5775)

    def test_relocated_incomplete_windows_fail_and_leave_empty_file(self):
        cohort=self.root/"incomplete.json";output=self.root/"failed-windows.jsonl"
        write_cohort(cohort,count=1)
        result=self.call("windows","--cohort",cohort,"--seed","7","--output",output)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b"complete 5775-unit cohort required",result.stderr)
        self.assertEqual(output.read_bytes(),b"")

    def test_relocated_existing_output_preserved(self):
        cohort=self.root/"incomplete.json";output=self.root/"already-present.jsonl"
        write_cohort(cohort,count=1);output.write_bytes(b"generated existing output\n")
        result=self.call("windows","--cohort",cohort,"--seed","7","--output",output)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(output.read_bytes(),b"generated existing output\n")

    def test_schema_dimensions_and_relational_limits_declared(self):
        cohort=json.loads((self.package/"cohort.schema.json").read_bytes())
        estimates=json.loads((self.package/"estimates.schema.json").read_bytes())
        self.assertEqual(cohort["properties"]["units"]["minItems"],5775)
        self.assertEqual(cohort["properties"]["units"]["maxItems"],5775)
        self.assertEqual(estimates["properties"]["rows"]["minItems"],23100)
        self.assertEqual(estimates["properties"]["rows"]["maxItems"],23100)
        self.assertEqual(estimates["properties"]["rows"]["items"]["properties"]["method"]["enum"],
                         list(METHODS))
        self.assertEqual(cohort["properties"]["units"]["items"]["properties"]["area"]["enum"], list(AREAS))
        self.assertIn("26",cohort["$comment"])
        self.assertIn("uniqueness",estimates["$comment"])


if __name__=="__main__":
    unittest.main(verbosity=2)
