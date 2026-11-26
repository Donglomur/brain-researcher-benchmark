"""Focused malformed-Unicode controls; only generated metadata is used."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "paper_unicode_fixture", ROOT / "tests/framework/test_paper_improvement.py")
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)
paper = fixture_module.paper


class UnicodeAdmissionTests(unittest.TestCase):
    def assert_safe_errors(self, errors):
        self.assertTrue(errors)
        self.assertTrue(any("surrogate" in error for error in errors))
        for error in errors:
            error.encode("utf-8", errors="strict")

    def test_json_lone_surrogates_rejected_in_nested_values_and_keys(self):
        documents = [
            r'{"nested":[{"value":"\ud800"}]}',
            r'{"nested":[{"value":"\udfff"}]}',
            r'{"nested":{"\ud800":"value"}}',
            r'{"nested":{"\udfff":{"value":"\ud800"}}}',
        ]
        for text in documents:
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as caught:
                    paper.loads_contract(text)
                self.assertIs(type(caught.exception), ValueError)
                str(caught.exception).encode("utf-8", errors="strict")

    def test_python_surrogates_rejected_by_contract_validator_and_digest(self):
        edits = [
            lambda c: c.update(task_id="PAPER-\ud800"),
            lambda c: c["evidence"][0].update(supports=["source", "\udfff"]),
            lambda c: c["same_task"]["inputs"].update({"\ud800": "value"}),
            lambda c: c["same_task"]["inputs"].update({"\ud800": "\udfff"}),
        ]
        for edit in edits:
            c, _ = fixture_module.fixture(); edit(c)
            self.assert_safe_errors(paper.contract_validate(c))
            with self.assertRaises(ValueError) as caught:
                paper.contract_digest(c)
            self.assertIs(type(caught.exception), ValueError)
            str(caught.exception).encode("utf-8", errors="strict")

    def test_duplicate_json_key_diagnostics_are_utf8_safe(self):
        keys = ("\ud800", "\udfff", "ordinary", "\u03b1", "\U0001f9e0")
        for key in keys:
            encoded_key = json.dumps(key, ensure_ascii=True)
            duplicate = "{" + encoded_key + ":1," + encoded_key + ":2}"
            for text in (duplicate, '{"nested":' + duplicate + "}"):
                with self.subTest(key=ascii(key), text=text):
                    with self.assertRaises(ValueError) as caught:
                        paper.loads_contract(text)
                    self.assertIs(type(caught.exception), ValueError)
                    diagnostic = str(caught.exception)
                    self.assertIn("duplicate JSON key", diagnostic)
                    diagnostic.encode("utf-8", errors="strict")

    def test_rejected_summaries_do_not_echo_invalid_unicode(self):
        edits = [
            lambda c: c.update(task_id="PAPER-\ud800"),
            lambda c: c.update(objective="invalid\udfff"),
            lambda c: c.update(disposition_reason="invalid\ud800"),
            lambda c: c["comparison"].update(primary_metric="invalid\udfff"),
            lambda c: c.update(blocking_issues=["invalid\ud800"]),
        ]
        documents = []
        for edit in edits:
            c, _ = fixture_module.fixture(); edit(c); documents.append(c)
        for version in ("paper-improvement/v1", "paper-improvement/v2"):
            documents.append({"schema_version": version, "task_id": "PAPER-\ud800"})
        for index, document in enumerate(documents):
            for summarize in (paper.summary, paper.contract_summary):
                with self.subTest(index=index, api=summarize.__name__):
                    out = summarize(document)
                    self.assertFalse(out["valid"])
                    self.assertFalse(out["improvement_ready"])
                    self.assertIsNone(out["task_id"])
                    self.assert_safe_errors(out["errors"])
                    if document["schema_version"] == "paper-improvement/v2":
                        self.assertIsNone(out["paper_win"])
                        self.assertEqual(out["scientific_outcome"], "unknown")
                        self.assertFalse(out["branch_metadata_ready"])
                    else:
                        self.assertIs(out["paper_win"], False)
                    json.dumps(out, ensure_ascii=False, allow_nan=False).encode("utf-8", errors="strict")
        c, _ = fixture_module.fixture()
        c.update(task_id="PAPER-神経-\U0001f9e0", disposition_reason="e\u0301 and \u00e9 stay distinct")
        for summarize in (paper.summary, paper.contract_summary):
            out = summarize(c)
            self.assertTrue(out["valid"])
            self.assertTrue(out["improvement_ready"])
            self.assertEqual(out["task_id"], c["task_id"])
            self.assertEqual(out["disposition_reason"], c["disposition_reason"])
            self.assertEqual(out["contract_digest"], paper.contract_digest(c))
            json.dumps(out, ensure_ascii=False, allow_nan=False).encode("utf-8", errors="strict")

    def test_compare_rejects_invalid_contract_without_digest_crash(self):
        c, r = fixture_module.fixture()
        c["source_paper"]["title"] = "invalid\ud800"
        out = paper.compare(c, r)
        self.assertFalse(out["comparison_admitted"])
        self.assertEqual(out["status"], "rejected")
        self.assert_safe_errors(out["errors"])
        json.dumps(out, ensure_ascii=False).encode("utf-8", errors="strict")

    def test_compare_rejects_invalid_result_values_and_keys(self):
        edits = [
            lambda r: r["evidence"][0].update(locator="\udfff"),
            lambda r: r["same_task"]["inputs"].update(description="\ud800"),
            lambda r: r["budget_usage"]["resource"].update({"\ud800": "\udfff"}),
        ]
        for edit in edits:
            c, r = fixture_module.fixture(); edit(r)
            out = paper.compare(c, r)
            self.assertFalse(out["comparison_admitted"])
            self.assert_safe_errors(out["errors"])
            json.dumps(out, ensure_ascii=False).encode("utf-8", errors="strict")

    def test_paired_json_escapes_and_supplementary_keys_are_valid(self):
        escaped = r'{"\ud83d\ude00":"\ud83e\udde0","greek":"\u03b1","han":"神経"}'
        document = paper.loads_contract(escaped)
        self.assertEqual(document, {"😀": "🧠", "greek": "α", "han": "神経"})
        self.assertEqual(paper._json_errors(document), [])
        self.assertEqual(paper.contract_digest(document), paper.contract_digest(json.loads(escaped)))
        # Two surrogate code units in a Python str are not a Unicode scalar;
        # json.loads above combines a valid escaped pair into its scalar.
        with self.assertRaises(ValueError) as caught:
            paper.contract_digest({"direct": "\ud83d\ude00"})
        self.assertIs(type(caught.exception), ValueError)

    def test_valid_unicode_golden_digests_unchanged_without_normalization(self):
        examples = [
            ({"emoji": "🧠", "greek": "α", "han": "神経"}, "a6bae4a6c90c07ce2b984adf8895c6f142b8ef77d5eba43adec85c3e5df7e71b"),
            ({"cafe": "e\u0301"}, "0b873f6b4c90d5e1f954745a895914a2b5ac12e47ebee68a04ad9db65b6d6123"),
            ({"cafe": "é"}, "c4dce9757998cd825ae724e1e67b409fe36d19fc0482a5ede25c38ffe497a4e0"),
        ]
        for document, expected in examples:
            self.assertEqual(paper._json_errors(document), [])
            self.assertEqual(paper.contract_digest(document), expected)

    def test_valid_unicode_contract_still_admitted_under_existing_rules(self):
        c, r = fixture_module.fixture()
        c["source_paper"]["title"] = "神経 α 🧠"
        digest = paper.contract_digest(c)
        for row in (r, r["freeze"], r["evaluation"], r["uncertainty"]):
            row["contract_digest"] = digest
        self.assertEqual(paper.contract_validate(c), [])
        out = paper.compare(c, r)
        self.assertTrue(out["comparison_admitted"], out["errors"])
        self.assertIsNone(out["paper_win"])


if __name__ == "__main__":
    unittest.main()
