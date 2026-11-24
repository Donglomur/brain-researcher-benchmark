"""Generated pair-admission and arithmetic controls; no authentic data or models."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import compare
from io_contract import encoded


def probabilities(label):
    result = [0.0] * 39
    result[label] = 1.0
    return result


class ComparisonTests(unittest.TestCase):
    def fixture(self, root):
        ids = [format(i, "024x") for i in range(6)]
        panel = {"schema_version": 1, "task_id": "NEURAL-089", "query_ids": ids}
        panel_raw = encoded(panel)
        paths = {name: root / (name + ".json")
                 for name in ("restricted", "program", "panel", "comparison", "targets")}
        paths["panel"].write_bytes(panel_raw)
        for role, called in (("restricted", [0, 0, 2, 1, 4, 6]), ("program", [0, 1, 1, 3, 4, 7])):
            rows = [{"query_id": q, "probabilities": probabilities(y)} for q, y in zip(ids, called)]
            if role == "restricted":
                rows.reverse()  # Pair by identity, never submitted row position.
            paths[role].write_bytes(encoded({"schema_version": 1, "task_id": "NEURAL-089", "predictions": rows}))
        targets = {"schema_version": 1, "task_id": "NEURAL-089",
                   "panel_sha256": compare.digest(panel_raw),
                   "targets": [{"query_id": q, "label": y} for y, q in enumerate(ids)]}
        paths["targets"].write_bytes(encoded(targets))
        declaration = {"schema_version": 1, "task_id": "NEURAL-089",
                       "panel_sha256": compare.digest(panel_raw), "conditions": []}
        for role, key in zip(compare.ROLES, ("restricted", "program")):
            declaration["conditions"].append({"access_condition": role,
                "submission_sha256": compare.digest(paths[key].read_bytes()),
                "query_observations_sha256": "a" * 64,
                "labeled_calibration_sha256": "b" * 64})
        paths["comparison"].write_bytes(encoded(declaration))
        return paths, declaration

    def run_pair(self, paths, pin=None):
        return compare.score_pair(*(paths[key] for key in ("restricted", "program", "panel", "comparison", "targets")),
                                  pin or compare.digest(paths["targets"].read_bytes()))

    def assert_no_private_access(self, paths, status, pin=None):
        real_read = compare.read
        opened = []
        def read(path, *args, **kwargs):
            self.assertNotEqual(Path(path), paths["targets"], "private target opened before pair admission")
            opened.append(Path(path))
            return real_read(path, *args, **kwargs)
        with mock.patch.object(compare, "read", side_effect=read):
            result = self.run_pair(paths, pin)
        self.assertEqual(result["status"], status)
        self.assertIsNone(result["metrics"])
        self.assertFalse(result["private_targets_read"])
        self.assertFalse(result["private_targets_open_attempted"])
        return result, opened

    def test_hand_computed_complete_pair_and_read_order(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, _ = self.fixture(Path(directory))
            opened = []
            original = compare.read
            def read(path, *args, **kwargs):
                opened.append(Path(path))
                return original(path, *args, **kwargs)
            with mock.patch.object(compare, "read", side_effect=read):
                result = self.run_pair(paths)
            self.assertEqual(result["status"], "scored")
            self.assertEqual(opened, [paths[k] for k in ("panel", "comparison", "restricted", "program", "targets")])
            self.assertEqual(result["query_count"], 6)
            self.assertEqual(result["paired_correctness"], {"both_correct": 2, "restricted_only_correct": 1,
                                                          "program_only_correct": 2, "neither_correct": 1})
            self.assertAlmostEqual(result["metrics"]["restricted_observation"]["macro_f1_39"], (8 / 3) / 39)
            self.assertAlmostEqual(result["metrics"]["frozen_program"]["macro_f1_39"], (11 / 3) / 39)
            self.assertAlmostEqual(result["restricted_minus_program"]["macro_f1_39"], -1 / 39)
            self.assertAlmostEqual(result["restricted_minus_program"]["accuracy"], -1 / 6)
            self.assertEqual(len(result["restricted_minus_program"]["per_class_f1"]), 39)
            self.assertFalse(result["same_information_delivery_verified"])
            self.assertFalse(result["access_enforcement_verified"])
            self.assertIsNone(result["confidence_interval"])
            self.assertEqual(result["bindings"]["comparison_sha256"], compare.digest(paths["comparison"].read_bytes()))

    def test_either_incomplete_submission_blocks_all_target_access(self):
        for role, expected in zip(("restricted", "program"), compare.ROLES):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                paths, declaration = self.fixture(Path(directory))
                submission = json.loads(paths[role].read_bytes())
                submission["predictions"].pop()
                paths[role].write_bytes(encoded(submission))
                next(r for r in declaration["conditions"] if r["access_condition"] == expected)["submission_sha256"] = compare.digest(paths[role].read_bytes())
                paths["comparison"].write_bytes(encoded(declaration))
                result, _ = self.assert_no_private_access(paths, "invalid_submission")
                self.assertEqual(result["invalid_condition"], expected)

    def test_submission_replacement_after_declaration_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, _ = self.fixture(Path(directory))
            paths["program"].write_bytes(paths["restricted"].read_bytes())
            result, _ = self.assert_no_private_access(paths, "invalid_submission")
            self.assertIn("SHA256", result["reason"])

    def test_unequal_observation_or_calibration_declarations_are_rejected(self):
        for field in ("query_observations_sha256", "labeled_calibration_sha256"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                paths, declaration = self.fixture(Path(directory))
                declaration["conditions"][1][field] = "c" * 64
                paths["comparison"].write_bytes(encoded(declaration))
                result, opened = self.assert_no_private_access(paths, "operator_error")
                self.assertIn("unequal declared information", result["reason"])
                self.assertEqual(opened, [paths["panel"], paths["comparison"]])

    def test_manifest_rejects_duplicate_roles_wrong_panel_and_extra_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, declaration = self.fixture(Path(directory))
            variants = []
            altered = copy.deepcopy(declaration); altered["conditions"][1]["access_condition"] = compare.ROLES[0]; variants.append(altered)
            altered = copy.deepcopy(declaration); altered["panel_sha256"] = "0" * 64; variants.append(altered)
            altered = copy.deepcopy(declaration); altered["conditions"][0]["query_label"] = 1; variants.append(altered)
            altered = copy.deepcopy(declaration); altered["conditions"][0]["submission_sha256"] = "G" * 64; variants.append(altered)
            for variant in variants:
                paths["comparison"].write_bytes(encoded(variant))
                self.assert_no_private_access(paths, "operator_error")

    def test_every_public_role_target_alias_is_rejected_before_reads(self):
        for role in ("restricted", "program", "panel", "comparison"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                paths, _ = self.fixture(Path(directory))
                paths[role] = paths["targets"]
                with mock.patch.object(compare, "read", side_effect=AssertionError("input body opened")) as reader:
                    result = self.run_pair(paths)
                self.assertEqual(result["status"], "operator_error")
                self.assertIn("input role alias", result["reason"])
                reader.assert_not_called()

    def test_hardlink_and_symlink_aliases_are_rejected_before_reads(self):
        for kind in ("hardlink", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                paths, _ = self.fixture(Path(directory))
                alias = Path(directory) / "alias.json"
                if kind == "hardlink": os.link(paths["targets"], alias)
                else: alias.symlink_to(paths["targets"])
                paths["comparison"] = alias
                with mock.patch.object(compare, "read", side_effect=AssertionError("input body opened")) as reader:
                    result = self.run_pair(paths)
                self.assertEqual(result["status"], "operator_error")
                reader.assert_not_called()

    def test_target_digest_failure_is_an_operator_error_after_complete_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, _ = self.fixture(Path(directory))
            result = self.run_pair(paths, "f" * 64)
            self.assertEqual(result["status"], "operator_error")
            self.assertTrue(result["private_targets_read"])
            self.assertTrue(result["private_targets_open_attempted"])
            self.assertIsNone(result["metrics"])
            self.assert_no_private_access(paths, "operator_error", "invalid-pin")

    def test_inherited_metric_sources_match_frozen_binding(self):
        root = Path(__file__).resolve().parent
        binding = json.loads((root / "SOURCE_BINDING.json").read_text())
        for source in binding["inherited_unchanged"]:
            raw = (root / source["copy"]).read_bytes()
            self.assertEqual(len(raw), source["bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), source["sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
