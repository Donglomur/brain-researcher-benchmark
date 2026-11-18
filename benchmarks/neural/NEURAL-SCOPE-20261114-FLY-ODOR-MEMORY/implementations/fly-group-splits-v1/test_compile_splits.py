"""Generated metadata controls only; no biological input or native execution."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

_spec = importlib.util.spec_from_file_location("fly_split", Path(__file__).with_name("compile_splits.py"))
split = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(split)
SHA = "a" * 64


def fixture():
    """Invented metadata with the declared complete geometry, never an animal result."""
    files, identities = [], []
    for index in range(42):
        member = "generated-member-" + str(index)
        fly = index // 6
        population = "generated-persistent" if fly < 4 else "generated-transient"
        count = 33 if index == 41 else 32
        files.append({"archive_member_id": member, "official_lookup_index": index,
                      "population_label": population, "trial_count": count,
                      "trials": [{"trial_index_zero_based": i} for i in range(count)]})
        identities.append({"archive_member_id": member, "official_lookup_index": index,
                           "source_population_label": population, "fly_id": "fly-" + str(fly),
                           "genotype": "VT062617" if fly < 4 else "52G12",
                           "identity_evidence_sha256": SHA})
    return {"files": files}, {
        "schema": "fly-odor-identity-resolution/v1", "task_id": split.TASK_ID,
        "base_plan_sha256": split.PLAN_SHA256, "identity_status": "reviewed_resolved",
        "identity_review_sha256": SHA, "files": identities,
        "record_50_51_resolution": {"decision": "same_animal", "evidence_sha256": SHA,
                                     "record_50_members": ["generated-member-0"],
                                     "record_51_members": ["generated-member-1"]}}


class CompleteGroupedSplits(unittest.TestCase):
    def compile(self, plan=None, identities=None):
        original, mapping = fixture()
        return split.compile_splits(original if plan is None else plan,
                                    mapping if identities is None else identities,
                                    resolution_sha256=SHA)

    def test_complete_outer_and_inner_disjoint_support(self):
        result = self.compile()
        self.assertEqual((result["source_files"], result["source_trials"],
                          result["biological_flies"]), (42, 1345, 7))
        self.assertEqual(sum(row["trial_index_stop_exclusive"] for row in result["file_census"]), 1345)
        file_fly = {row["archive_member_id"]: row["fly_id"] for row in result["file_census"]}
        file_genotype = {row["archive_member_id"]: row["genotype"] for row in result["file_census"]}
        all_test_members = []
        for outer in result["outer_folds"]:
            held = outer["test_fly"]
            test, train = set(outer["test_members"]), set(outer["outer_training_members"])
            all_test_members.extend(test)
            self.assertFalse(test & train)
            self.assertEqual(test | train, {m for m, g in file_genotype.items() if g == outer["genotype"]})
            self.assertEqual({file_fly[m] for m in test}, {held})
            self.assertNotIn(held, outer["outer_training_flies"])
            for inner in outer["inner_folds"]:
                validation, inner_train = set(inner["validation_members"]), set(inner["training_members"])
                self.assertFalse(validation & inner_train)
                self.assertFalse(test & (validation | inner_train))
                self.assertEqual(validation | inner_train, train)
                self.assertEqual({file_fly[m] for m in validation}, {inner["validation_fly"]})
        self.assertEqual(len(all_test_members), len(set(all_test_members)), 42)
        self.assertEqual(set(all_test_members), set(file_fly))
        self.assertFalse(result["scientific_admission"])
        self.assertFalse(result["identity_independently_proved_by_this_program"])

    def test_order_independent_assignment_and_file_lists(self):
        plan, mapping = fixture()
        expected = self.compile(plan, mapping)
        plan["files"].reverse()
        mapping["files"].reverse()
        self.assertEqual(self.compile(plan, mapping), expected)

    def test_alias_names_are_not_lookup_indices(self):
        plan, mapping = fixture()
        self.assertNotIn(50, {row["official_lookup_index"] for row in plan["files"]})
        self.compile(plan, mapping)  # explicit record-label/member map suffices
        alias = mapping["record_50_51_resolution"]
        alias["decision"] = "different_animals"
        alias["record_51_members"] = ["generated-member-6"]
        self.compile(plan, mapping)
        alias["decision"] = "same_animal"
        with self.assertRaisesRegex(split.Refused, "alias_decision_assignment_mismatch"):
            self.compile(plan, mapping)

    def test_missing_unresolved_or_foreign_alias_refuses(self):
        for change in ("unresolved", "empty", "foreign", "duplicate"):
            plan, mapping = fixture()
            alias = mapping["record_50_51_resolution"]
            if change == "unresolved": alias["decision"] = "unknown"
            elif change == "empty": alias["record_50_members"] = []
            elif change == "foreign": alias["record_50_members"] = ["unregistered"]
            else: alias["record_50_members"] *= 2
            with self.subTest(change=change), self.assertRaises(split.Refused):
                self.compile(plan, mapping)

    def test_missing_duplicate_or_extra_file_refuses(self):
        for change in ("missing", "duplicate", "extra"):
            plan, mapping = fixture()
            if change == "missing": plan["files"].pop()
            elif change == "duplicate": plan["files"][-1] = copy.deepcopy(plan["files"][0])
            else: plan["files"].append(copy.deepcopy(plan["files"][0]))
            with self.subTest(change=change), self.assertRaises(split.Refused):
                self.compile(plan, mapping)

    def test_missing_reordered_and_boolean_trial_identity_refuse(self):
        for change in ("missing", "reordered", "boolean"):
            plan, mapping = fixture()
            trials = plan["files"][0]["trials"]
            if change == "missing": trials.pop()
            elif change == "reordered": trials.reverse()
            else: trials[0]["trial_index_zero_based"] = False
            with self.subTest(change=change), self.assertRaises(split.Refused):
                self.compile(plan, mapping)

    def test_all_trial_total_is_required(self):
        plan, mapping = fixture()
        plan["files"][0]["trials"].pop()
        plan["files"][0]["trial_count"] -= 1
        with self.assertRaisesRegex(split.Refused, "complete_1345_trial_support"):
            self.compile(plan, mapping)

    def test_assignment_coverage_join_and_review_are_required(self):
        for change in ("missing", "duplicate", "lookup", "population", "review", "state", "plan"):
            plan, mapping = fixture()
            if change == "missing": mapping["files"].pop()
            elif change == "duplicate": mapping["files"][-1] = copy.deepcopy(mapping["files"][0])
            elif change == "lookup": mapping["files"][0]["official_lookup_index"] = True
            elif change == "population": mapping["files"][0]["source_population_label"] = "other"
            elif change == "review": mapping["identity_review_sha256"] = "not-a-digest"
            elif change == "state": mapping["identity_status"] = "unresolved"
            else: mapping["base_plan_sha256"] = "b" * 64
            with self.subTest(change=change), self.assertRaises(split.Refused):
                self.compile(plan, mapping)

    def test_fly_cannot_span_genotypes(self):
        plan, mapping = fixture()
        mapping["files"][24]["fly_id"] = "fly-0"
        with self.assertRaisesRegex(split.Refused, "fly_spans_genotypes"):
            self.compile(plan, mapping)

    def test_nested_grouping_requires_three_flies_per_genotype(self):
        plan, mapping = fixture()
        for row in mapping["files"]:
            if row["fly_id"] == "fly-6": row["fly_id"] = "fly-5"
        with self.assertRaisesRegex(split.Refused, "insufficient_flies_for_nested_grouping"):
            self.compile(plan, mapping)

    def test_future_or_target_fields_in_resolution_are_not_accepted(self):
        plan, mapping = fixture()
        mapping["files"][0]["future_reencounter"] = True
        with self.assertRaisesRegex(split.Refused, "identity_assignment_fields"):
            self.compile(plan, mapping)

    def test_bound_reader_rejects_mismatch_duplicates_symlink_and_fifo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "metadata.json"
            body = b'{"x": 1}'
            path.write_bytes(body)
            sha = hashlib.sha256(body).hexdigest()
            self.assertEqual(split.read_bound_json(path, 100, sha), {"x": 1})
            with self.assertRaisesRegex(split.Refused, "operand_digest_mismatch"):
                split.read_bound_json(path, 100, SHA)
            with self.assertRaisesRegex(split.Refused, "operand_size_limit"):
                split.read_bound_json(path, 2, sha)
            duplicate = b'{"x": 1, "x": 2}'
            path.write_bytes(duplicate)
            with self.assertRaisesRegex(split.Refused, "duplicate_json_key"):
                split.read_bound_json(path, 100, hashlib.sha256(duplicate).hexdigest())
            symlink = root / "link"
            symlink.symlink_to(path)
            with self.assertRaises(OSError):
                split.read_bound_json(symlink, 100, SHA)
            fifo = root / "fifo"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(split.Refused, "regular_file_required"):
                split.read_bound_json(fifo, 100, SHA)

    def test_output_is_private_immutable_and_size_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "output.json"
            prior = os.umask(0)
            try:
                result = split.write_new_private(path, {"generated": True})
            finally:
                os.umask(prior)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(result["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            with self.assertRaises(FileExistsError):
                split.write_new_private(path, {"replacement": True})
            too_big = Path(tmp) / "too-big.json"
            with self.assertRaisesRegex(split.Refused, "output_size_limit"):
                split.write_new_private(too_big, {"generated": "x" * split.MAX_OUTPUT_BYTES})
            self.assertFalse(too_big.exists())

    def test_production_cli_does_not_accept_generated_descriptor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            descriptor = root / "invented.json"
            descriptor.write_bytes(b'{"files":[]}')
            output = root / "not-created.json"
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                split.main(["--base-plan", str(descriptor), "--identity-resolution", str(root / "absent"),
                            "--identity-resolution-sha256", SHA, "--output", str(output)])
            self.assertEqual(caught.exception.code, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
