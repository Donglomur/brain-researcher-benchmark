"""Generated transport controls; fixtures never qualify an empirical fit or oracle."""
import copy
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location("cardiac_delivery_tested", HERE / "delivery.py")
D = importlib.util.module_from_spec(loader)
loader.loader.exec_module(D)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.assets = self.root / "assets"
        self.assets.mkdir()
        self.real_spec = D.spec()
        self.value = copy.deepcopy(self.real_spec)
        self.csv = self.csv_bytes()
        for name in self.value["common"] | self.value["B_only"]:
            if name in self.value["local_common"]:
                continue
            raw = self.csv if name == "meg_slope_data_sbg.csv" else ("generated control " + name + "\n").encode()
            path = self.assets / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            group = "common" if name in self.value["common"] else "B_only"
            self.value[group][name] = D.pin(raw)
        self.value["input"]["input_sha256"] = D.pin(self.csv)["sha256"]
        self.value["participant_id_sha256"] = D.hashlib.sha256(json.dumps(["generated-" + str(i) for i in range(655)], separators=(",", ":")).encode()).hexdigest()
        self.seam = patch.object(D, "spec", return_value=self.value)
        self.seam.start()
        self.addCleanup(self.seam.stop)
        self.addCleanup(self.tmp.cleanup)
        self.candidates = {}
        s = D.scorer(self.value)
        for condition in ("A", "B"):
            folder = self.root / ("candidate-" + condition)
            folder.mkdir()
            (folder / "program.py").write_text("# Generated transport fixture; no inference.\n")
            summary = {"schema_version": 1, "input_sha256": self.value["input"]["input_sha256"],
                "target": "salzburg_bambi091_six_student_t_targets", "models": {}}
            for name in s.MODELS:
                summary["models"][name] = {"summary": {v: {"mean": 1.0, "sd_population": 1.0, "hdi_94_low": 0.0, "hdi_94_high": 2.0, "mcse_mean_batch": None} for v in s.VARIABLES},
                    "diagnostics": {k: None for k in ("chains", "draws_per_chain", "tune_per_chain", "divergences", "max_rhat", "min_ess_bulk", "min_ess_tail")}}
            (folder / "summary.json").write_bytes(D.encode(summary))
            self.candidates[condition] = folder

    @staticmethod
    def csv_bytes(count=655):
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["", "subject_id", "age", "ECG_components", "ECG_not_rejected", "ECG_rejected"])
        for i in range(count):
            writer.writerow([i, "generated-" + str(i), 18 + i / 100, i / 1000, i / 2000, i / 3000])
        return stream.getvalue().encode()

    def build(self):
        D.build(self.assets, self.root / "pair")
        return self.root / "pair"

    def capture(self, condition, pair=None):
        pair = pair or self.root / "pair"
        folder = self.candidates[condition]
        out = self.root / ("capture-" + condition)
        D.capture(pair, condition, folder / "program.py", folder / "summary.json", out)
        return out

    def rewrite(self, path, value):
        os.chmod(path, 0o600)
        path.write_bytes(D.encode(value))

    def test_complete_pair_distinct_conditions_and_no_oracle(self):
        pair = self.build()
        receipt = D.verify_pair(pair)
        self.assertEqual(receipt["coverage"]["participants"], 655)
        self.assertFalse(any(x.startswith("official_source/") for x in D.tree(pair / "A")))
        self.assertEqual(D.tree(pair / "B") - D.tree(pair / "A"), set(self.value["B_only"]))
        a, b = self.capture("A"), self.capture("B")
        # No reference argument, reference body, candidate import or inference step.
        result = D.close_pair(pair, a, b, self.root / "closed")
        self.assertEqual(result["reference_accesses"], 0)
        self.assertFalse(result["scientific_qualified"])
        self.assertEqual(result["summary_files"]["A"], D.pin((a / "summary.json").read_bytes()))

    def test_production_cli_rejects_generated_assets(self):
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(HERE / "delivery.py"), "build", "--assets", str(self.assets), "--out", str(self.root / "production")], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "production" / "receipt.json").exists())
        self.assertIn("pinned asset", result.stderr)

    def test_missing_person_refused_even_if_content_pin_updated(self):
        raw = self.csv_bytes(654)
        value = copy.deepcopy(self.value)
        value["input"]["input_sha256"] = D.pin(raw)["sha256"]
        with self.assertRaisesRegex(ValueError, "655-row"):
            D.check_table(raw, value)

    def test_changed_ordered_people_refused(self):
        raw = self.csv.replace(b"generated-100", b"generated-xxx")
        value = copy.deepcopy(self.value)
        value["input"]["input_sha256"] = D.pin(raw)["sha256"]
        with self.assertRaisesRegex(ValueError, "ordered participant"):
            D.check_table(raw, value)

    def test_packet_extra_private_file_refused(self):
        pair = self.build()
        (pair / "A" / "reference.json").write_text("not a reference")
        with self.assertRaisesRegex(ValueError, "closed candidate"):
            self.capture("A")

    def test_packet_tamper_refused(self):
        pair = self.build()
        path = pair / "A" / "article_text.txt"
        os.chmod(path, 0o600)
        path.write_text("tamper")
        with self.assertRaisesRegex(ValueError, "pinned asset"):
            self.capture("A")

    def test_program_symlink_refused(self):
        self.build()
        folder = self.candidates["A"]
        (folder / "program.py").unlink()
        (folder / "program.py").symlink_to(self.candidates["B"] / "program.py")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.capture("A")

    def test_duplicate_key_summary_refused(self):
        self.build()
        path = self.candidates["A"] / "summary.json"
        path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.capture("A")

    def test_missing_model_refused(self):
        self.build()
        path = self.candidates["A"] / "summary.json"
        value = json.loads(path.read_text())
        del value["models"][next(iter(value["models"]))]
        self.rewrite(path, value)
        with self.assertRaisesRegex(ValueError, "six unique"):
            self.capture("A")

    def test_wrong_summary_input_refused(self):
        self.build()
        path = self.candidates["A"] / "summary.json"
        value = json.loads(path.read_text())
        value["input_sha256"] = "0" * 64
        self.rewrite(path, value)
        with self.assertRaisesRegex(ValueError, "original input"):
            self.capture("A")

    def test_one_arm_cannot_close_pair(self):
        pair = self.build()
        a = self.capture("A")
        with self.assertRaisesRegex(ValueError, "condition/pair/source"):
            D.close_pair(pair, a, a, self.root / "closed")
        self.assertFalse((self.root / "closed").exists())

    def test_changed_capture_fails(self):
        pair = self.build()
        a, b = self.capture("A"), self.capture("B")
        (a / "program.py").write_text("# mutated\n")
        with self.assertRaisesRegex(ValueError, "pinned asset"):
            D.close_pair(pair, a, b, self.root / "closed")

    def test_qualification_forgery_refused(self):
        pair = self.build()
        a, b = self.capture("A"), self.capture("B")
        path = a / "receipt.json"
        value = json.loads(path.read_text())
        value["inference_verified"] = True
        self.rewrite(path, value)
        with self.assertRaisesRegex(ValueError, "capture authority"):
            D.close_pair(pair, a, b, self.root / "closed")

    def test_different_pair_capture_refused(self):
        pair = self.build()
        a = self.capture("A")
        other = self.root / "other-pair"
        D.build(self.assets, other)
        b = self.capture("B", other)
        with self.assertRaisesRegex(ValueError, "condition/pair/source"):
            D.close_pair(pair, a, b, self.root / "closed")

    def test_no_overwrite(self):
        self.build()
        with self.assertRaisesRegex(ValueError, "fresh output"):
            self.build()

    def test_runtime_discovery_not_qualification(self):
        with patch.object(D.importlib.util, "find_spec", return_value=None):
            result = D.runtime_report()
            self.assertTrue(result["native_fitting_blocked"])
            self.assertIn("pymc", result["missing_modules"])
        with patch.object(D.importlib.util, "find_spec", return_value=object()):
            result = D.runtime_report()
            self.assertFalse(result["native_fitting_blocked"])
            self.assertFalse(result["runtime_qualified"])

    def test_current_validator_pin_is_enforced(self):
        value = copy.deepcopy(self.value)
        value["summary_scorer"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "pinned asset"):
            D.scorer(value)


if __name__ == "__main__":
    unittest.main()
