"""Generated checks for full-cohort external input and numerical grading delivery."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("neural033_operator", Path(__file__).with_name("operator.py"))
op = importlib.util.module_from_spec(spec)
spec.loader.exec_module(op)


def generated_full_cohort():
    rows = []
    for treatment, count, mice, members in (("control", 1143, 20, 27), ("kir", 793, 10, 17)):
        for index in range(count):
            member = index % members
            observation = index // members
            base = 2. ** ((observation // 3) % 3)
            activity = observation % 3
            rows.append({"row_id": f"generated-{treatment}-{index}",
                         "mouse_id": f"generated-{treatment}-{member % mice:02d}",
                         "treatment": treatment,
                         "compartment": "apical" if member < (members + 1) // 2 else "basal",
                         "member_index0": member, "source_row0": observation,
                         "baseline_flag": {"kind": "list", "value": []},
                         "followup_flag": {"kind": "str", "value": "Stable"},
                         "baseline_volume": base, "followup_volume": base * 2. ** (.1 * activity),
                         "event_rate": activity})
    return rows


class OperatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = generated_full_cohort()
        cls.observations = op.io.encode({"rows": cls.rows})
        cls.identity = {"row_ids": [r["row_id"] for r in cls.rows],
                        "mouse_ids": sorted({r["mouse_id"] for r in cls.rows}),
                        "input_sha256": op.io.pin(cls.observations)["sha256"]}
        cls.analysis = op.core.analyze(cls.rows)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # macOS exposes /var through a symlink; exercise ordinary-file reads at
        # the resolved fixture location without weakening production rejection.
        self.root = Path(self.temp.name).resolve()
        (self.root / "protocol").mkdir()
        self.inputs = self.root / "external"
        self.inputs.mkdir()
        self.bodies = {name: b"generated metadata\n" for name in op.VIEW}
        self.bodies.update({"CONTRACT.json": b'{"generated":true}\n',
                            "identity.json": op.io.encode(self.identity),
                            "observations.json": self.observations})
        records = []
        for name, body in self.bodies.items():
            target = self.inputs / name if name in op.EXTERNAL else self.root / "protocol" / name
            target.write_bytes(body)
            records.append({"target": "public/" + name, **op.io.pin(body)})
        (self.root / "SOURCE_INPUTS.json").write_bytes(op.io.encode({"files": records}))
        self.patch = mock.patch.object(op, "HERE", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.submission = self.root / "candidate.json"
        self.candidate = {"schema_version": 1, "task_id": "NEURAL-033",
                          "contract_sha256": op.io.pin(self.bodies["CONTRACT.json"])["sha256"],
                          "input_sha256": self.identity["input_sha256"],
                          "analysis": copy.deepcopy(self.analysis)}

    def submit(self, candidate):
        self.submission.write_bytes(op.io.encode(candidate))
        return op.grade(self.inputs, self.submission)

    def test_complete_preparation_exports_exact_six_files_without_analysis(self):
        with mock.patch.object(op.core, "analyze", side_effect=AssertionError("no fit during export")):
            result = op.prepare(self.inputs, self.root / "view")
        self.assertFalse(result["analysis_executed"])
        self.assertEqual(set(p.name for p in (self.root / "view").iterdir()), set(op.VIEW))
        for name, expected in self.bodies.items():
            self.assertEqual((self.root / "view" / name).read_bytes(), expected)

    def test_wrong_payload_refused_before_export_or_analysis(self):
        (self.inputs / "observations.json").write_bytes(b'{"rows":[]}')
        with self.assertRaisesRegex(ValueError, "asset identity differs"):
            op.prepare(self.inputs, self.root / "view")
        self.assertFalse((self.root / "view").exists())
        result, code = self.submit(self.candidate)
        self.assertEqual((code, result["status"]), (3, "operator_error"))

    def test_wrong_contrast_numerically_penalized_and_missing_deletion_invalidates_primary(self):
        result, code = self.submit(self.candidate)
        self.assertEqual((code, result["primary_normalized_contrast_mae"]), (0, 0.))
        wrong = copy.deepcopy(self.candidate)
        wrong["analysis"]["panels"]["all"]["contrasts"][op.core.CONTRASTS[0]]["estimate"] += 7.
        result, code = self.submit(wrong)
        self.assertEqual(code, 0)
        self.assertGreater(result["primary_normalized_contrast_mae"], .1)
        wrong = copy.deepcopy(self.candidate)
        wrong["analysis"]["panels"]["balanced"]["delete_one_mouse"].pop(next(iter(wrong["analysis"]["panels"]["balanced"]["delete_one_mouse"])))
        result, code = self.submit(wrong)
        self.assertEqual(code, 0)
        self.assertIsNone(result["primary_normalized_contrast_mae"])
        self.assertGreater(result["structural_mismatch_count"], 0)

    def test_invalid_submission_does_not_open_observations(self):
        self.submission.write_bytes(b'{"schema_version":true}')
        original = op.read_asset
        calls = []
        def observed(name, source):
            calls.append(name)
            if name == "observations.json":
                raise AssertionError("unadmitted report accessed outcomes")
            return original(name, source)
        with mock.patch.object(op, "read_asset", observed):
            result, code = op.grade(self.inputs, self.submission)
        self.assertEqual((code, result["status"]), (2, "invalid_submission"))
        self.assertNotIn("observations.json", calls)

    def test_source_join_rejects_reorder_truncation_and_changed_mouse(self):
        op.validate_source_join(self.rows, self.identity)
        mutations = [self.rows[::-1], self.rows[:-1], copy.deepcopy(self.rows)]
        mutations[-1][0]["mouse_id"] = "generated-invented-mouse"
        for rows in mutations:
            with self.assertRaises(ValueError):
                op.validate_source_join(rows, self.identity)

    def test_missing_input_is_operator_failure_and_no_fresh_output_overwrite(self):
        (self.inputs / "identity.json").unlink()
        result, code = op.grade(self.inputs, self.submission)
        self.assertEqual((code, result["status"]), (3, "operator_error"))
        output = self.root / "result.json"
        output.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            op.main(["grade", "--source-input", str(self.inputs), "--submission", str(self.submission), "--output", str(output)])
        self.assertEqual(output.read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main(verbosity=2)
