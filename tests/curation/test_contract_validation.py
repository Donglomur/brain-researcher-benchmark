"""Validate curation payloads with the actual Draft 2020-12 schema.

Run separately from the standard-library framework suite, in the CI-pinned
jsonschema environment. These generated examples do not authenticate artifacts
or establish scientific execution.
"""

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "src/neurobench/curation/contracts/curation-contracts-v1.schema.json"


def artifact_ref():
    return {
        "artifact_id": "fixture-source",
        "uri": "artifact://fixture/source",
        "sha256": "a" * 64,
        "media_type": "application/json",
        "visibility": "public",
    }


def definition_validator(document, definition):
    # Retain the complete document so local $defs references resolve normally.
    return Draft202012Validator({**document, "$ref": "#/$defs/" + definition})


class EvidenceReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = definition_validator(cls.schema, "EvidenceItem")

    def test_source_backed_statuses_reject_empty_references(self):
        for status in ("reported", "verified", "measured"):
            item = {"field": "dataset_identity", "status": status, "evidence_refs": []}
            with self.subTest(status=status):
                errors = list(self.validator.iter_errors(item))
                self.assertTrue(errors)
                self.assertTrue(any(error.validator == "minItems"
                                    and list(error.path) == ["evidence_refs"]
                                    for error in errors))

    def test_source_backed_statuses_accept_complete_references(self):
        for status in ("reported", "verified", "measured"):
            item = {"field": "dataset_identity", "status": status,
                    "evidence_refs": [artifact_ref()]}
            with self.subTest(status=status):
                self.validator.validate(item)

    def test_planned_and_missing_allow_empty_references(self):
        for status in ("planned", "missing"):
            with self.subTest(status=status):
                self.validator.validate({"field": "ceiling", "status": status,
                                         "evidence_refs": []})

    def test_reference_array_remains_required_for_every_status(self):
        for status in ("reported", "verified", "measured", "planned", "missing"):
            for refs in (None, {}, "source"):
                with self.subTest(status=status, refs=refs):
                    self.assertFalse(self.validator.is_valid(
                        {"field": "dataset_identity", "status": status,
                         "evidence_refs": refs}))
            with self.subTest(status=status, absent=True):
                self.assertFalse(self.validator.is_valid(
                    {"field": "dataset_identity", "status": status}))

    def test_supplied_references_must_be_complete_and_well_formed(self):
        for status in ("reported", "verified", "measured", "planned", "missing"):
            for field in artifact_ref():
                incomplete = artifact_ref()
                del incomplete[field]
                with self.subTest(status=status, missing=field):
                    self.assertFalse(self.validator.is_valid(
                        {"field": "dataset_identity", "status": status,
                         "evidence_refs": [incomplete]}))
            for bad_reference in ({}, {**artifact_ref(), "sha256": "invalid"},
                                  {**artifact_ref(), "visibility": "unknown"}):
                with self.subTest(status=status, reference=bad_reference):
                    self.assertFalse(self.validator.is_valid(
                        {"field": "dataset_identity", "status": status,
                         "evidence_refs": [bad_reference]}))

    def test_optional_fields_and_extension_properties_remain_allowed(self):
        item = {"field": "ceiling", "status": "planned", "evidence_refs": []}
        self.validator.validate(item)
        for probe in (None, {"question": "Which ceiling is supported?"}):
            self.validator.validate({**item, "value": None, "probe": probe,
                                     "curator_note": "Unexecuted plan"})


if __name__ == "__main__":
    unittest.main()
