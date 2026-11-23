from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent / "initial-evaluator-v1"))
spec = importlib.util.spec_from_file_location("alignment_under_test", HERE / "source_alignment.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
from make_control import build


def groups():
    return {source: sorted(a.g.GROUPS[local]) for source, local in a.GROUP_NAMES.items()}


def reference(n=12):
    return {str(i): {"person": [[0, 0, 1, 1]]} for i in range(n)}


def predictions(annotations):
    return {image: {category: [[boxes[0]]] for category, boxes in cats.items()}
            for image, cats in annotations.items()}


class TraversalTests(unittest.TestCase):
    def test_numeric_order_aligns_but_lexical_json_sorting_mispairs(self):
        target = reference()
        response = predictions(target)
        aligned = a.audit_subject(target, response, groups())
        self.assertTrue(aligned["groups"]["All"]["source_pairing_compatible_in_this_process"])
        lexical = json.loads(json.dumps(response, sort_keys=True))
        result = a.audit_subject(target, lexical, groups())
        self.assertTrue(result["source_image_count_assertion_passes"])
        self.assertTrue(result["same_image_membership"])
        self.assertFalse(result["same_image_insertion_order"])
        all_group = result["groups"]["All"]
        self.assertTrue(all_group["same_query_membership"])
        self.assertEqual(all_group["mispaired_queries"], 10)
        self.assertEqual(all_group["wrong_image_pairs"], 10)
        self.assertFalse(all_group["source_pairing_compatible_in_this_process"])

    def test_reversed_images_preserve_identity_set_but_fail_positions(self):
        target = reference(4)
        response = dict(reversed(list(predictions(target).items())))
        result = a.audit_subject(target, response, groups())["groups"]["All"]
        self.assertEqual(result["mispaired_queries"], 4)
        self.assertEqual(result["missing_query_identities"], 0)
        self.assertEqual(result["unpaired_reference_tail"], 0)

    def test_equal_length_wrong_categories_are_not_hidden(self):
        target = reference(2)
        response = predictions(target)
        response["0"] = {"dog": [[[0, 0, 1, 1]]]}
        result = a.audit_subject(target, response, groups())["groups"]["All"]
        self.assertEqual(result["reference_queries"], result["response_queries"])
        self.assertEqual(result["same_image_wrong_category_pairs"], 1)
        self.assertEqual(result["missing_query_identities"], 1)
        self.assertEqual(result["unexpected_query_identities"], 1)

    def test_missing_middle_query_exposes_zip_shift_and_unpaired_tail(self):
        target = reference(4)
        response = predictions(target)
        response["1"] = {}
        result = a.audit_subject(target, response, groups())["groups"]["All"]
        self.assertEqual(result["positional_pairs"], 3)
        self.assertEqual(result["mispaired_queries"], 2)
        self.assertEqual(result["missing_query_identities"], 1)
        self.assertEqual(result["unpaired_reference_tail"], 1)

    def test_empty_images_are_checked_by_source_image_assertion(self):
        target = reference(2); target["2"] = {}
        response = predictions(target); del response["2"]
        result = a.audit_subject(target, response, groups())
        self.assertFalse(result["source_image_count_assertion_passes"])
        self.assertTrue(result["groups"]["All"]["same_query_sequence"])
        self.assertFalse(result["groups"]["All"]["source_pairing_compatible_in_this_process"])

    def test_null_and_malformed_nesting_are_not_claimed_source_compatible(self):
        target = reference(3)
        response = predictions(target)
        response["0"]["person"] = None
        response["1"]["person"] = [[]]
        response["2"]["person"] = []
        result = a.audit_subject(target, response, groups())["groups"]["All"]
        self.assertTrue(result["same_query_sequence"])
        self.assertEqual(result["source_extraction_index_errors"], 2)
        self.assertFalse(result["source_pairing_compatible_in_this_process"])

    def test_group_membership_and_input_shape_refuse(self):
        changed = groups(); changed["coco_cats"].pop()
        with self.assertRaises(a.g.ContractError): a.validate_categories(changed)
        changed = groups(); changed["salient"].append(changed["salient"][0])
        with self.assertRaises(a.g.ContractError): a.validate_categories(changed)
        with self.assertRaises(a.g.ContractError): a.audit_subject(reference(), {"0": []}, groups())


class FileTests(unittest.TestCase):
    def test_complete_panel_preserves_four_subject_flags_and_input_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "control"; contract = build(root)
            category_path = root / "categories.json"; category_path.write_text(json.dumps(groups()))
            report = a.audit(contract, root / "annotations.json", root / "image_order.json", category_path)
            expected = report["primary_all_category_alignment"]
            self.assertEqual(set(expected), set(a.g.ROLES))
            for role in a.g.ROLES:
                self.assertEqual(list(expected[role]), list(a.g.SUBJECTS))
            # make_control deliberately omits its empty image in these arms.
            self.assertTrue(all(expected["candidate"].values()))
            self.assertFalse(any(expected["official_baseline"].values()))
            self.assertEqual(report["input_pins"]["annotations"]["sha256"], a.g.file_sha256(root / "annotations.json"))
            self.assertEqual(report["native_numerical_parity"], "not_established")
            self.assertNotIn("scores", report)
            value = json.loads(contract.read_text()); del value["runs"]["candidate"]["responses"]["S7"]
            contract.write_text(json.dumps(value))
            with self.assertRaises(a.g.ContractError):
                a.audit(contract, root / "annotations.json", root / "image_order.json", category_path)

    def test_changed_annotation_pin_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "control"; contract = build(root)
            category_path = root / "categories.json"; category_path.write_text(json.dumps(groups()))
            annotation_path = root / "annotations.json"
            annotation_path.write_text(annotation_path.read_text() + " ")
            with self.assertRaises(a.g.ContractError):
                a.audit(contract, annotation_path, root / "image_order.json", category_path)

    def test_reader_rejects_ambiguous_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            for body in ('{"0":{},"0":{}}', '{"0": NaN}', '{"0": Infinity}'):
                path.write_text(body)
                with self.assertRaises(a.g.ContractError): a.read_input(path)

    def test_cli_emits_audit_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "control"; contract = build(root)
            category_path = root / "categories.json"; category_path.write_text(json.dumps(groups()))
            output = root / "audit.json"
            command = [sys.executable, "-I", "-S", "-B", str(HERE / "source_alignment.py"),
                       "--contract", str(contract), "--annotations", str(root / "annotations.json"),
                       "--image-order", str(root / "image_order.json"), "--category-groups", str(category_path),
                       "--output", str(output)]
            run = subprocess.run(command, capture_output=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr.decode())
            original = output.read_bytes()
            self.assertEqual(json.loads(original)["subject_order"], list(a.g.SUBJECTS))
            again = subprocess.run(command, capture_output=True, timeout=15)
            self.assertEqual(again.returncode, 2)
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
