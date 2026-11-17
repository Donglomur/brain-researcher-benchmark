"""Generated checks for the curation schema's shared string constraints.

These tests apply only type, length and regex-search constraints from the actual
schema. They are not a general JSON Schema validator or an artifact authenticator.
"""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "src/neurobench/curation/contracts/curation-contracts-v1.schema.json"


def accepts_string(schema, value):
    """Apply the JSON Schema string keywords used by these two definitions."""
    supported = {"type", "minLength", "maxLength", "pattern"}
    if set(schema) - supported or schema.get("type") != "string":
        raise AssertionError("String-constraint coverage needs review")
    if not isinstance(value, str):
        return False
    return (
        len(value) >= schema.get("minLength", 0)
        and ("maxLength" not in schema or len(value) <= schema["maxLength"])
        and ("pattern" not in schema or re.search(schema["pattern"], value) is not None)
    )


class CurationStringSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definitions = json.loads(SCHEMA.read_text(encoding="utf-8"))["$defs"]
        cls.sha = cls.definitions["Sha256"]
        cls.artifact_id = cls.definitions["ArtifactRef"]["properties"]["artifact_id"]

    def test_valid_lowercase_sha256_values(self):
        for value in ("0" * 64, "f" * 64, "0123456789abcdef" * 4):
            with self.subTest(value=value):
                self.assertTrue(accepts_string(self.sha, value))

    def test_sha256_rejects_wrong_lengths_alphabet_and_nonstring_values(self):
        for value in ("", "a" * 63, "a" * 65, "A" * 64, "g" * 64,
                      "0x" + "a" * 64, " " + "a" * 64, None, 123, True):
            with self.subTest(value=value):
                self.assertFalse(accepts_string(self.sha, value))

    def test_valid_artifact_identifiers_keep_existing_alphabet_and_boundaries(self):
        for value in ("a", "0", "A9._:-z", "a" * 128, "Z" + "_" * 127):
            with self.subTest(value=value):
                self.assertTrue(accepts_string(self.artifact_id, value))

    def test_artifact_identifiers_reject_wrong_lengths_alphabet_and_types(self):
        for value in ("", "a" * 129, "_leading", ":leading", "-leading", ".leading",
                      "space here", "path/part", "tab\there", "café", None, 123, True):
            with self.subTest(value=value):
                self.assertFalse(accepts_string(self.artifact_id, value))

    def test_complete_strings_reject_line_endings_and_embedded_separators(self):
        for schema, value in ((self.sha, "a" * 64), (self.artifact_id, "artifact")):
            for ending in ("\n", "\r\n", "\r", "\v", "\f", "\u0085", "\u2028", "\u2029"):
                for changed in (value + ending, ending + value, value[:1] + ending + value[1:]):
                    with self.subTest(value=changed):
                        self.assertFalse(accepts_string(schema, changed))

    def test_nested_integrity_fields_still_use_the_shared_sha_definition(self):
        for name, field in (("ArtifactRef", "sha256"), ("ExecutedBy", "skill_sha"),
                            ("CurationJob", "skill_sha")):
            with self.subTest(definition=name):
                self.assertEqual(self.definitions[name]["properties"][field],
                                 {"$ref": "#/$defs/Sha256"})


if __name__ == "__main__":
    unittest.main()
