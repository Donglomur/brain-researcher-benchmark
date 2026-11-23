from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / "raw_response.py"
spec = importlib.util.spec_from_file_location("raw_response_under_test", SOURCE)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def panel(roster=None, text="[0,0,1,1]"):
    roster = {"0": ["person", "dog"], "1": []} if roster is None else roster
    packet = {"schema": r.SCHEMA, "task_id": r.g.TASK, "profile": "engineering_controls",
              "query_roster_sha256": r.canonical_sha256(roster),
              "responses": {role: {subject: {image: {category: text for category in cats}
                                             for image, cats in roster.items()}
                                    for subject in r.g.SUBJECTS} for role in r.g.ROLES}}
    return packet, roster


class SourceGrammar(unittest.TestCase):
    def test_source_groups_boxes_and_text_order(self):
        text = "<s> first [0.,0,1,1;0.1,0.2,0.3,0.4]\nsecond [1,2,3,4] </s>"
        self.assertEqual(r.extract_source_grammar(text),
                         [[[0., 0., 1., 1.], [.1, .2, .3, .4]], [[1., 2., 3., 4.]]])

    def test_source_unsupported_forms_are_not_repaired(self):
        for text in ("[0, 0, 1, 1]", "[-0.1,0,1,1]", "[10,0,1,1]", "[0e0,0,1,1]",
                     "[.1,0,1,1]", "[0,0,1]", "[0,0,1,1,1]", "[0,0,1,1; 0,0,1,1]"):
            with self.subTest(text=text):
                self.assertEqual(r.extract_source_grammar(text), [])

    def test_utf8_digit_semantics_match_source_regex_language(self):
        self.assertEqual(r.extract_source_grammar("[٠,٠,١,١]"), [[[0., 0., 1., 1.]]])

    def test_invalid_first_box_is_not_replaced_by_later_good_box(self):
        raw, roster = panel(text="[9,0,1,1;0,0,1,1] [0,0,1,1]")
        result = r.convert_panel(raw, roster)
        extracted = result["responses"]["candidate"]["S1"]["0"]["person"]
        self.assertEqual(extracted[0][0], [9., 0., 1., 1.])
        self.assertEqual(r.g._prediction(extracted), (None, "invalid_extraction"))
        self.assertEqual(result["audit"]["candidate"]["S1"]["first_box_status_counts"],
                         {"invalid_extraction": 2})

    def test_text_and_byte_bounds_refuse_instead_of_silently_truncate(self):
        for value in (123, True, [], None, "\ud800", "x" * (r.MAX_TEXT_BYTES + 1), "é" * r.MAX_TEXT_BYTES):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(r.g.ContractError):
                    r.extract_source_grammar(value)


class CompletePanel(unittest.TestCase):
    def test_null_empty_and_invalid_retain_original_denominator(self):
        raw, roster = panel()
        raw["responses"]["candidate"]["S1"]["0"]["person"] = None
        raw["responses"]["candidate"]["S1"]["0"]["dog"] = "ordinary prose without a box"
        result = r.convert_panel(raw, roster)
        targets = r.g.prepare_reference({"0": {"person": [[0, 0, 1, 1]], "dog": [[0, 0, 1, 1]]}, "1": {}},
                                        {"0": "generated-A", "1": "generated-B"}, "engineering_controls")
        rows = r.g.score_subject(targets, {"0", "1"}, result["responses"]["candidate"]["S1"])
        summary = r.g.summarize(rows)["All"]
        self.assertEqual(summary["query_count"], 2)
        self.assertEqual(summary["accuracy"]["0.5"], 0)
        self.assertEqual(summary["missing_or_invalid"], 2)
        self.assertEqual(result["audit"]["candidate"]["S1"]["first_box_status_counts"],
                         {"empty_extraction": 1, "missing": 1})

    def test_every_arm_subject_image_category_must_be_explicit(self):
        paths = [("responses", "candidate"), ("responses", "candidate", "S7"),
                 ("responses", "candidate", "S1", "1"),
                 ("responses", "candidate", "S1", "0", "person")]
        for path in paths:
            raw, roster = panel()
            parent = raw
            for key in path[:-1]: parent = parent[key]
            del parent[path[-1]]
            with self.subTest(path=path), self.assertRaises(r.g.ContractError):
                r.convert_panel(raw, roster)

    def test_extra_answers_or_wrong_roster_commitment_reject(self):
        raw, roster = panel()
        raw["responses"]["candidate"]["S1"]["0"]["cat"] = "[0,0,1,1]"
        with self.assertRaises(r.g.ContractError): r.convert_panel(raw, roster)
        raw, roster = panel()
        raw["query_roster_sha256"] = "0" * 64
        with self.assertRaises(r.g.ContractError): r.convert_panel(raw, roster)

    def test_invalid_rosters_profiles_and_numeric_responses_reject(self):
        for roster in ({"0": ["made-up"]}, {"1": ["person"]}, {"0": ["person", "person"]}, {"0": []}):
            with self.subTest(roster=roster), self.assertRaises(r.g.ContractError):
                r.validate_roster(roster, "engineering_controls")
        raw, roster = panel()
        raw["responses"]["candidate"]["S1"]["0"]["person"] = [[0, 0, 1, 1]]
        with self.assertRaises(r.g.ContractError): r.convert_panel(raw, roster)
        raw, roster = panel(); raw["profile"] = "paper_population"
        with self.assertRaises(r.g.ContractError): r.convert_panel(raw, roster)

    def test_complete_generated_982_image_panel_does_not_promote_authenticity(self):
        roster = {str(i): ["person"] if i == 0 else [] for i in range(982)}
        raw, roster = panel(roster); raw["profile"] = "paper_population"
        result = r.convert_panel(raw, roster)
        self.assertEqual(len(result["responses"]["candidate"]["S7"]), 982)
        self.assertEqual(result["audit"]["candidate"]["S7"]["query_count"], 1)
        self.assertEqual(result["scientific_qualification"], "not_established")
        self.assertEqual(result["native_author_parser_parity"], "not_run")

    def test_reordering_input_keys_does_not_change_keyed_conversion(self):
        raw, roster = panel()
        expected = r.convert_panel(raw, roster)
        raw["responses"] = dict(reversed(list(raw["responses"].items())))
        self.assertEqual(r.convert_panel(raw, dict(reversed(list(roster.items())))), expected)

    def test_full_extraction_comparison_exposes_changed_first_group(self):
        raw, roster = panel(); converted = r.convert_panel(raw, roster)
        observed = copy.deepcopy(converted["responses"])
        self.assertEqual(r.extraction_comparison(converted, observed)["mismatch_count"], 0)
        observed["candidate"]["S7"]["0"]["dog"] = [[[False, 0., 1., 1.]]]
        report = r.extraction_comparison(converted, observed)
        self.assertEqual(report["mismatches"], [{"role": "candidate", "subject": "S7", "image_id": "0", "category": "dog"}])
        del observed["official_baseline"]["S1"]
        with self.assertRaises(r.g.ContractError): r.extraction_comparison(converted, observed)


class FilesAndCLI(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ.get("UMBRAE_TEST_TMP", tempfile.gettempdir()))
        self.temp = tempfile.TemporaryDirectory(prefix="umbrae-raw-", dir=base)
        self.root = Path(self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def test_bounded_reader_duplicate_keys_nonfinite_and_byte_identity(self):
        path = self.root / "input.json"
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff'):
            path.write_bytes(body)
            with self.assertRaises((r.g.ContractError, UnicodeError)):
                r.read_bounded(path)
        path.write_bytes(b'{"a": 1}\n')
        value, pin = r.read_bounded(path)
        self.assertEqual(value, {"a": 1})
        self.assertEqual(pin, {"bytes": 9, "sha256": hashlib.sha256(b'{"a": 1}\n').hexdigest()})
        with mock.patch.object(r, "MAX_INPUT_BYTES", 2), self.assertRaises(r.g.ContractError):
            r.read_bounded(path)

    def test_cli_preserves_numeric_image_order_beyond_single_digit_ids(self):
        # An identity-aware scorer hides this bug. The author's scorer flattens
        # image dictionaries independently, so lexical 0,1,10,... order matters.
        roster = {str(i): ["person"] for i in reversed(range(12))}
        raw, roster = panel(roster)
        raw_path = self.root / "raw12.json"; raw_path.write_text(json.dumps(raw))
        roster_path = self.root / "roster12.json"; roster_path.write_text(json.dumps(roster))
        output = self.root / "out12"
        run = subprocess.run([sys.executable, "-I", "-S", "-B", str(SOURCE),
                              "--raw-panel", str(raw_path), "--query-roster", str(roster_path),
                              "--output-directory", str(output)], capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr.decode())
        for role in r.g.ROLES:
            for subject in r.g.SUBJECTS:
                loaded = json.loads((output / f"{role}-{subject}.json").read_text())
                self.assertEqual(list(loaded), [str(i) for i in range(12)])

    def test_cli_emits_all16_hash_bound_files_and_refuses_overwrite(self):
        raw, roster = panel()
        raw_path = self.root / "raw.json"; raw_path.write_text(json.dumps(raw))
        roster_path = self.root / "roster.json"; roster_path.write_text(json.dumps(roster))
        output = self.root / "out"
        command = [sys.executable, "-I", "-S", "-B", str(SOURCE), "--raw-panel", str(raw_path),
                   "--query-roster", str(roster_path), "--output-directory", str(output)]
        run = subprocess.run(command, capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr.decode())
        report = json.loads((output / "conversion.json").read_text())
        self.assertEqual(len(list(output.iterdir())), 17)
        self.assertTrue(report["complete"])
        for role in r.g.ROLES:
            for subject in r.g.SUBJECTS:
                pin = report["extracted_files"][role][subject]
                body = (output / pin["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(body).hexdigest(), pin["sha256"])
                self.assertEqual(len(body), pin["bytes"])
                self.assertEqual(json.loads(body)["0"]["person"], [[[0., 0., 1., 1.]]])
        before = (output / "conversion.json").read_bytes()
        again = subprocess.run(command, capture_output=True, timeout=20)
        self.assertEqual(again.returncode, 2)
        self.assertEqual((output / "conversion.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
