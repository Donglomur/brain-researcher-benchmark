"""Changed ROOT004 metadata behavior only; no neural data or scientific execution."""
from __future__ import annotations
import ast
import copy
import hashlib
import json
from pathlib import Path
import types
import unittest

ROOT = globals().get("_REPOSITORY", Path(__file__).resolve().parents[2])
OVERLAY = globals().get("_OVERLAY", ROOT)
HOME = "benchmarks/paper/PAPER-ROOT-ADD-004"


def read_file(relative):
    path = OVERLAY / relative
    return (path if path.is_file() else ROOT / relative).read_bytes()


def load_binding():
    if "_BINDER" in globals():
        return globals()["_BINDER"]
    path = ROOT / "src/neurobench/paper_outcomes_binding.py"
    module = types.ModuleType("_root004_binding_control")
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


class PreviousRows(dict):
    scope_decisions = None
    scope_pin = None
    endpoint_selections = None


class Root004ManuscriptScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binding = load_binding()
        cls.descriptor = json.loads(read_file(HOME + "/docs/figure3-manuscript-scope.v1.json"))
        cls.pins = cls.binding._ROOT004_PINS
        cls.documents = cls.binding.root004_scope_bundle(cls.read_pin)

    @staticmethod
    def read_pin(identity, label):
        raw = read_file(identity["path"])
        if len(raw) != identity["bytes"] or hashlib.sha256(raw).hexdigest() != identity["sha256"]:
            raise ValueError(label + ": raw identity mismatch")
        return json.loads(raw)

    def row_and_prior(self):
        row = {"id": "PAPER-ROOT-ADD-004", "track": "paper", "task_directory": HOME,
               "title": self.documents["task"]["title"], "specification": copy.deepcopy(self.pins["task"]),
               "specification_revision": {"improvement_contract": copy.deepcopy(self.pins["retained_improvement"])},
               "paper_outcomes": {"schema_version": "paper-outcomes-binding/v1",
                   "previous_specification": copy.deepcopy(self.pins["pre_outcomes"]),
                   "reproduction_contract": copy.deepcopy(self.pins["reproduction"]),
                   "outcomes": copy.deepcopy(self.pins["outcomes"])}}
        prior = {"id": row["id"], "track": "paper", "task_directory": HOME,
                 "specification": copy.deepcopy(self.pins["pre_outcomes"])}
        return row, PreviousRows({row["id"]: prior})

    def run_context(self, row=None, prior=None, reader=None, improvement=None):
        default_row, default_prior = self.row_and_prior()
        return self.binding.context(row or default_row, self.documents["task"], prior or default_prior,
                                    reader or self.read_pin, improvement_contract=improvement)

    def test_coherent_bundle_and_source_closure(self):
        result = self.run_context()
        self.assertEqual(result["improvement_contract_pin"], self.pins["improvement"])
        self.assertEqual(result["retained_improvement_contract_pin"], self.pins["retained_improvement"])
        self.assertEqual(result["primary_policy_revision"], self.pins["descriptor"])
        for name in ("descriptor", "improvement", "retained_reproduction",
                     "retained_task", "retained_outcomes", "pre_outcomes", "reproduction", "outcomes"):
            self.assertIn(self.pins[name]["path"], result["members"])
        retained = self.pins["retained_improvement"]["path"]
        self.assertNotIn(retained, result["members"])
        # Exercise the maintained ownership merge, not only the context in
        # isolation. The retained policy is already owned by task revision.
        checker = ast.parse((ROOT / "src/neurobench/repository_checks.py").read_text())
        prepare = next(node for node in checker.body
                       if isinstance(node, ast.FunctionDef) and node.name == "prepare")
        branches = [node for node in ast.walk(prepare) if isinstance(node, ast.If)
                    and isinstance(node.test, ast.Name) and node.test.id == "outcome_context"]
        self.assertEqual(len(branches), 1)
        merge = compile(ast.fix_missing_locations(ast.Module(
            body=[copy.deepcopy(branches[0])], type_ignores=[])), "<maintained outcome ownership merge>", "exec")
        owner = "task:PAPER-ROOT-ADD-004"
        def environment(members):
            return dict(outcome_context=result, members=members,
                        identifier="PAPER-ROOT-ADD-004", track="paper",
                        allowed_files={"paper": set()}, need=self.binding.need)
        merged = {retained: owner}
        exec(merge, environment(merged))
        self.assertEqual(set(merged), result["members"] | {retained})
        self.assertEqual(set(merged.values()), {owner})
        # No general same-owner deduplication or cross-owner collision bypass.
        collision = min(result["members"])
        for conflicting_owner in (owner, "task:PAPER-ROOT-ADD-005"):
            with self.subTest(conflicting_owner=conflicting_owner):
                with self.assertRaisesRegex(ValueError, "Duplicate paper outcome metadata"):
                    exec(merge, environment({retained: owner, collision: conflicting_owner}))
        self.assertFalse(any(result["summary"]["paired_metadata_admitted"].values()))
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in result["summary"]["cells"]))

    def test_original_projection_and_histories_preserved(self):
        _, prior = self.row_and_prior()
        base = self.binding.project_task(self.documents["pre_outcomes"], prior["PAPER-ROOT-ADD-004"],
                                         self.documents["retained_improvement"])
        self.assertEqual(base, self.documents["retained_task"])
        self.assertEqual(self.binding._project_root004_scope(base, self.documents), self.documents["task"])
        self.assertEqual(self.documents["reproduction"]["findings"],
                         self.documents["retained_reproduction"]["findings"])

    def test_qualification_and_scalar_baselines_remain_unresolved(self):
        current, old = self.documents["improvement"], self.documents["retained_improvement"]
        for name in ("published_baseline", "reproduced_author_baseline", "minimum_effect", "current_sota"):
            self.assertEqual(current["comparison"][name], old["comparison"][name])
        self.assertEqual(current["comparison"]["direction"], "higher")
        self.assertEqual(current["disposition"], "source_unresolved")
        self.assertEqual(self.documents["reproduction"]["eligibility"], "source_unresolved")
        self.assertNotIn("admission_policy", self.documents["reproduction"])
        self.assertFalse(self.documents["task"]["evaluation"]["binary_reward_registered"])
        self.assertIsNone(self.documents["task"]["evaluation"]["executor_ref"])
        self.assertIsNone(current["episode"]["resource_budget"])
        self.assertEqual(current["same_task"]["aggregation"], self.documents["reproduction"]["same_task"]["aggregation"])

    def test_rejects_stale_reproduction_outcome_and_retained_policy_bindings(self):
        for location, name in (("paper_outcomes", "reproduction_contract"),
                               ("paper_outcomes", "outcomes"),
                               ("paper_outcomes", "previous_specification"),
                               ("specification_revision", "improvement_contract")):
            with self.subTest(name=name):
                row, prior = self.row_and_prior()
                row[location][name]["sha256"] = "0" * 64
                with self.assertRaises(ValueError): self.run_context(row, prior)

    def test_rejects_caller_replacing_retained_improvement(self):
        with self.assertRaisesRegex(ValueError, "caller changed"):
            self.run_context(improvement=self.documents["improvement"])

    def test_rejects_reader_tampering_under_approved_pins(self):
        for name in self.pins:
            with self.subTest(name=name):
                def tamper(identity, label):
                    result = self.read_pin(identity, label)
                    if identity == self.pins[name]: result["unreviewed"] = True
                    return result
                with self.assertRaisesRegex(ValueError, "parsed document identity"):
                    self.binding.root004_scope_bundle(tamper)

    def test_rejects_field_predecessor_and_projection_drift(self):
        retained = copy.deepcopy(self.documents["retained_improvement"])
        retained["episode"]["candidate_freeze"] = "Use a spatial proxy"
        with self.assertRaisesRegex(ValueError, "field predecessor"):
            self.binding._root004_replace(retained, self.descriptor["replacements"]["improvement"])
        changed = copy.deepcopy(self.documents["retained_task"])
        changed["status"] = "ready"
        with self.assertRaisesRegex(ValueError, "retained deterministic projection"):
            self.binding._project_root004_scope(changed, self.documents)

    def test_rejects_combined_scope_route(self):
        row, prior = self.row_and_prior()
        prior.scope_decisions = {"entries": {}, "same_primary_corrections": {row["id"]: {"task_id": row["id"]}}}
        with self.assertRaisesRegex(ValueError, "cannot combine another correction"):
            self.run_context(row, prior)

    def test_selection_cannot_spread_to_other_task_or_unreviewed_bytes(self):
        row, _ = self.row_and_prior()
        self.assertTrue(self.binding.has_root004_scope(row))
        row["id"] = "PAPER-ROOT-ADD-005"
        self.assertFalse(self.binding.has_root004_scope(row))
        row["id"] = "PAPER-ROOT-ADD-004"
        row["specification"]["sha256"] = "0" * 64
        self.assertFalse(self.binding.has_root004_scope(row))
        with self.assertRaises(ValueError): self.run_context(row)


if __name__ == "__main__":
    unittest.main()
