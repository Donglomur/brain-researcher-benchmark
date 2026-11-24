"""Generated identity/report controls; never read a neural response or reference."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from interface import Invalid
import participant_check as check
from test_report_contract_generated import complete_fixture

WRITTEN = 0


def write(path, body):
    global WRITTEN
    path.write_bytes(body)
    WRITTEN += len(body)
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def encode(value):
    return json.dumps(value, sort_keys=True).encode()


def fixture(root):
    names = [f"generated_feature_{i}" for i in range(15)]
    features = {"feature_names": names, "concept_features": {f"generated_{i:03d}": {} for i in range(100)}}
    desc = dict(write(root / "features.json", encode(features)), file="features.json")
    manifest = {"schema": "neural052_inputs_v1", "task_id": "NEURAL-052", "design": check.DESIGN_PIN,
                "features": desc, "feature_names": names, "subjects": [{"subject_id": s} for s in check.SUBJECTS]}
    digest = write(root / "INPUTS.json", encode(manifest))["sha256"]
    design = dict(features, subjects=manifest["subjects"])
    report = complete_fixture(design)
    report["input_manifest_sha256"] = digest
    return manifest, digest, report


class ParticipantChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest, self.digest, self.report = fixture(self.root)

    def artifacts(self, report=None, methods=b"Generated interpretation.\n"):
        result = self.root / "result.json"
        prose = self.root / "METHODS.md"
        write(result, encode(report if report is not None else self.report))
        write(prose, methods)
        return result, prose

    def test_complete_report_without_private_files_or_response_arrays(self):
        result, methods = self.artifacts()
        captured = []
        modules_before = set(sys.modules)
        original = check.capture_regular
        def record(path, *args, **kwargs):
            captured.append(Path(path).name)
            return original(path, *args, **kwargs)
        with patch.object(check, "capture_regular", side_effect=record):
            outcome = check.check_submission(self.root, self.digest, result, methods)
        self.assertEqual(captured, ["INPUTS.json", "features.json", "result.json", "METHODS.md"])
        self.assertEqual(outcome["status"], "valid_structure")
        self.assertFalse(outcome["numerical_correctness_checked"])
        self.assertFalse(outcome["scientific_qualification"])
        self.assertFalse(any(name in (set(sys.modules) - modules_before) for name in ("data_io", "encoding_core", "grade", "numpy")))

    def test_numeric_alternative_remains_structurally_admissible(self):
        self.report["analysis"]["participants"][0]["roi_metrics"]["macro_primary"]["V1"]["joint"]["value"] = -123.0
        result, methods = self.artifacts()
        outcome = check.check_submission(self.root, self.digest, result, methods)
        self.assertEqual(outcome["status"], "valid_structure")
        self.assertFalse(outcome["interpretation_quality_scored"])

    def test_missing_participant_wrong_manifest_and_missing_roi_are_rejected(self):
        variants = []
        missing = copy.deepcopy(self.report); missing["analysis"]["participants"].pop(); variants.append(missing)
        wrong = copy.deepcopy(self.report); wrong["input_manifest_sha256"] = "a" * 64; variants.append(wrong)
        roi = copy.deepcopy(self.report); del roi["analysis"]["participants"][0]["roi_metrics"]["macro_primary"]["IT"]; variants.append(roi)
        for report in variants:
            result, methods = self.artifacts(report)
            with self.assertRaises(Invalid):
                check.check_submission(self.root, self.digest, result, methods)

    def test_blank_and_non_utf8_methods_rejected(self):
        for content in (b" \n", b"\xff"):
            result, methods = self.artifacts(methods=content)
            with self.assertRaises(Invalid):
                check.check_submission(self.root, self.digest, result, methods)

    def test_public_pins_and_full_identity_are_required(self):
        with self.assertRaises(Invalid):
            check.public_identity(self.root, "a" * 64)
        write(self.root / "features.json", b"{}")
        with self.assertRaises(Invalid):
            check.public_identity(self.root, self.digest)
        self.manifest["subjects"].pop()
        digest = write(self.root / "INPUTS.json", encode(self.manifest))["sha256"]
        with self.assertRaises(Invalid):
            check.public_identity(self.root, digest)

    def test_incomplete_concepts_and_absent_methods_rejected(self):
        result, methods = self.artifacts()
        methods.unlink()
        with self.assertRaises(Invalid):
            check.check_submission(self.root, self.digest, result, methods)
        features = json.loads((self.root / "features.json").read_bytes())
        features["concept_features"].pop(next(iter(features["concept_features"])))
        self.manifest["features"] = dict(write(self.root / "features.json", encode(features)), file="features.json")
        digest = write(self.root / "INPUTS.json", encode(self.manifest))["sha256"]
        with self.assertRaises(Invalid):
            check.public_identity(self.root, digest)

    def test_features_cannot_escape_input_directory(self):
        for name in ("../private/DESIGN.json", "/private/DESIGN.json", "a\\b", ".."):
            self.manifest["features"]["file"] = name
            digest = write(self.root / "INPUTS.json", encode(self.manifest))["sha256"]
            with self.assertRaises(Invalid):
                check.public_identity(self.root, digest)

    def test_cli_schema_rejection_and_fresh_output(self):
        schema = self.root / "schema.json"
        self.assertEqual(check.main(["schema", "--input-dir", str(self.root), "--manifest-sha256", self.digest,
                                     "--output", str(schema)]), 0)
        self.assertEqual(json.loads(schema.read_bytes())["title"], "NEURAL-052 complete protocol report")
        original = schema.read_bytes()
        with self.assertRaises(SystemExit):
            check.main(["schema", "--input-dir", str(self.root), "--manifest-sha256", self.digest,
                        "--output", str(schema)])
        self.assertEqual(schema.read_bytes(), original)
        result, methods = self.artifacts()
        rejected = self.root / "rejected.json"
        self.assertEqual(check.main(["check", "--input-dir", str(self.root), "--manifest-sha256", "b" * 64,
            "--submission", str(result), "--methods", str(methods), "--output", str(rejected)]), 2)
        self.assertEqual(json.loads(rejected.read_bytes())["status"], "preflight_rejected")
        global WRITTEN
        WRITTEN += schema.stat().st_size + rejected.stat().st_size


def tearDownModule():
    print(json.dumps({"generated_fixture_cumulative_written_bytes": WRITTEN}))


if __name__ == "__main__":
    unittest.main()
