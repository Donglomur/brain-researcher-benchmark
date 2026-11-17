"""Boundary controls using explicitly synthetic accepted metadata.

The fixed real cases have a separate independently reviewed metadata freeze.
These controls replace only module-local fixture identities to exercise malformed
callbacks, strict replacement semantics, immutable handles and task preservation.
They never execute a task implementation or assert scientific qualification.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[2] / "src/neurobench/paper_scope_policy_successor.py"
SPEC = importlib.util.spec_from_file_location("scope_policy_successor_controls", PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
TASK = "PAPER-paper-signal-add-004"


def raw(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n").encode()


def identity(value):
    data = raw(value)
    return [len(data), hashlib.sha256(data).hexdigest(), M._digest(value)]


class ScopePolicySuccessorTests(unittest.TestCase):
    def setUp(self):
        anchors = {key: {"description": "invented " + key} for key in
                   ("dataset", "cohort", "target", "inputs", "split", "preprocessing", "metric", "aggregation")}
        old = {"schema_version": "paper-improvement/v1", "task_id": TASK,
               "disposition": "source_unresolved", "source_paper": {"url": "https://example.invalid/paper"},
               "same_task": anchors, "episode": {"rule": "old scope", "budget": None},
               "blocking_issues": ["old scope gap"], "comparison": {"minimum_effect": None, "uncertainty": None}}
        current = copy.deepcopy(old)
        current["episode"]["rule"] = "reviewed current scope"
        current["blocking_issues"][0] = "current unresolved gap"
        reproduction = {"schema_version": "paper-reproduction/v2", "task_id": TASK,
                        "eligibility": "source_unresolved", "source_paper": copy.deepcopy(old["source_paper"]),
                        "same_task": copy.deepcopy(anchors)}
        previous = {"id": TASK, "track": "paper", "objective": "old", "goal": "old goal",
                    "primary_outputs": ["old output"], "success_criteria": ["old criterion"],
                    "evaluation": {"contract": "improvement.v1.json"}, "episode": copy.deepcopy(old["episode"]),
                    "blocking_issues": copy.deepcopy(old["blocking_issues"]),
                    "holds": {"task_specific": copy.deepcopy(old["blocking_issues"])},
                    "next_implementation_action": "old instructions", "legacy": {"old": True},
                    "resources": {"budget": None}, "input_assets": {"immutable": True},
                    "provenance": {"old_source": "preserve"}}
        changes = []
        for pointer, before, after in (("/episode/rule", "old scope", "reviewed current scope"),
                                       ("/blocking_issues/0", "old scope gap", "current unresolved gap")):
            changes.append({"json_pointer": pointer, "predecessor_value": before, "successor_value": after,
                            "predecessor_value_canonical_sha256": M._digest(before),
                            "successor_value_canonical_sha256": M._digest(after)})
        self.delta = {"task_id": TASK, "field_replacements": changes}
        self.entry = {"task_id": TASK, "primary_goal": "selected goal", "primary_scope": "selected scope",
                      "remaining_source_limits": ["unresolved scientific source"], "scientific_outcome": "unknown"}
        self.scope = {"same_primary_corrections": {TASK: self.entry}}
        scope_size, scope_sha, scope_canonical = identity(self.scope)
        scope_pin = {"path": "docs/provenance/paper-outcome-scope-decisions.v1.json",
                     "bytes": scope_size, "sha256": scope_sha}
        self.base = copy.deepcopy(previous)
        self.base.update({"goal": "selected goal", "primary_scope": "selected scope",
                          "primary_outputs": ["reproduction", "old selector", "conditions"],
                          "success_criteria": ["first", "second", "third", "fourth", "last"],
                          "evaluation": {"contracts": {"improvement": "improvement.v1.json", "reproduction": "reproduction.v2.json"}},
                          "admission": {"runnable": False, "scientific_outcome": "unknown"}})
        self.docs = {"previous_task": previous, "previous_improvement": old,
                     "primary_improvement": current, "reproduction": reproduction}
        self.case = {name: identity(value) for name, value in self.docs.items()}
        self.case.update({"descriptor": [1, "0" * 64, "0" * 64], "delta_canonical": M._digest(self.delta),
                          "base_projection_canonical": M._digest(self.base),
                          "scope_entry_canonical": M._digest(self.entry),
                          "deltas": [item["json_pointer"] for item in changes]})
        self.stack = [patch.dict(M._APPROVED, {TASK: self.case}, clear=True),
                      patch.object(M, "SCOPE_PIN", scope_pin), patch.object(M, "SCOPE_CANONICAL", scope_canonical)]
        for item in self.stack:
            item.start()
            self.addCleanup(item.stop)
        declaration = M.descriptor(TASK, self.delta)
        self.docs["descriptor"] = declaration
        self.case["descriptor"] = identity(declaration)
        self.pins = M.approved_pins(TASK)
        self.reads = []

    def read_pin(self, pin, label):
        self.reads.append(copy.deepcopy(pin))
        if pin == M.SCOPE_PIN:
            value = self.scope
        else:
            names = [name for name in self.docs if pin == self.pins[name]]
            self.assertEqual(len(names), 1, label)
            value = self.docs[names[0]]
        data = raw(value)
        self.assertEqual((len(data), hashlib.sha256(data).hexdigest()), (pin["bytes"], pin["sha256"]))
        return copy.deepcopy(value)

    def authenticate(self, **overrides):
        arguments = dict(task_id=TASK, revision_pin=self.pins["descriptor"],
                         primary_pin=self.pins["primary_improvement"], reproduction_pin=self.pins["reproduction"],
                         previous_pin=self.pins["previous_task"], retained_improvement_pin=self.pins["previous_improvement"],
                         read_pin=self.read_pin)
        arguments.update(overrides)
        return M.authenticate(**arguments)

    def test_valid_authentication_reads_all_dependencies(self):
        handle = self.authenticate()
        self.assertEqual(len(self.reads), 6)
        self.assertEqual(handle.primary_improvement, self.docs["primary_improvement"])
        self.assertEqual(handle.retained_improvement, self.docs["previous_improvement"])
        self.assertIsNone(handle.candidate_interface)
        self.assertIsNone(handle.author_reproduction_routes)

    def test_missing_selector_never_falls_back(self):
        for declared in ({}, {"reproduction_contract": self.pins["reproduction"]}):
            with self.subTest(declared=declared), self.assertRaises(ValueError):
                M.has_primary_successor({"id": TASK, "paper_outcomes": declared})
        self.assertFalse(M.has_primary_successor({"id": TASK}))

    def test_complete_selector_is_explicit(self):
        self.assertTrue(M.has_primary_successor({"id": TASK, "paper_outcomes": {
            "primary_policy_revision": self.pins["descriptor"],
            "primary_improvement_contract": self.pins["primary_improvement"],
            "reproduction_contract": self.pins["reproduction"]}}))

    def test_other_tasks_and_unfrozen_cases_rejected(self):
        for task in ("PAPER-SMC-RNN-2024", "PAPER-paper-method-add-010", "../evil", None):
            with self.subTest(task=task), self.assertRaises(ValueError):
                M.approved_pins(task)

    def test_selector_path_size_hash_and_closed_shape(self):
        mutations = ({"path": "elsewhere.json"}, {"bytes": True}, {"bytes": 1048577},
                     {"sha256": "f" * 64}, {"extra": True})
        for update in mutations:
            value = {**self.pins["primary_improvement"], **update}
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.authenticate(primary_pin=value)
        self.assertEqual(self.reads, [])

    def test_callback_parsed_substitution_rejected(self):
        def changed(pin, label):
            value = self.read_pin(pin, label)
            if pin == self.pins["primary_improvement"]:
                value["comparison"]["minimum_effect"] = 0.01
            return value
        with self.assertRaisesRegex(ValueError, "parsed identity"):
            self.authenticate(read_pin=changed)

    def test_callback_mutating_its_pin_cannot_change_registry_pin(self):
        original = copy.deepcopy(self.pins)
        def changed(pin, label):
            value = self.read_pin(pin, label)
            pin["sha256"] = "0" * 64
            return value
        self.authenticate(read_pin=changed)
        self.assertEqual(self.pins, original)

    def test_scope_substitution_rejected(self):
        def changed(pin, label):
            value = self.read_pin(pin, label)
            if pin == M.SCOPE_PIN:
                value["same_primary_corrections"][TASK]["primary_scope"] = "wrong scope"
            return value
        with self.assertRaisesRegex(ValueError, "scope authority"):
            self.authenticate(read_pin=changed)

    def test_descriptor_extra_field_rejected(self):
        def changed(pin, label):
            value = self.read_pin(pin, label)
            if pin == self.pins["descriptor"]:
                value["qualification"] = "ready"
            return value
        with self.assertRaises(ValueError):
            self.authenticate(read_pin=changed)

    def test_delta_payload_change_rejected(self):
        changed = copy.deepcopy(self.delta)
        changed["field_replacements"][0]["successor_value"] = "unreviewed"
        with self.assertRaises(ValueError):
            M.descriptor(TASK, changed)

    def test_delta_partial_duplicate_reordered_and_extra_changes_rejected(self):
        changes = self.delta["field_replacements"]
        for altered in (changes[:1], list(reversed(changes)), [changes[0], changes[0]], changes + changes[:1]):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                M._verify_delta(self.docs["previous_improvement"], self.docs["primary_improvement"], altered, self.case["deltas"])

    def test_delta_rejects_stale_value_and_wrong_value_digest(self):
        for key, value in (("predecessor_value", "not old"), ("successor_value_canonical_sha256", "0" * 64)):
            changes = copy.deepcopy(self.delta["field_replacements"])
            changes[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                M._verify_delta(self.docs["previous_improvement"], self.docs["primary_improvement"], changes, self.case["deltas"])

    def test_delta_does_not_accept_unrelated_criterion_change(self):
        changed = copy.deepcopy(self.docs["primary_improvement"])
        changed["comparison"]["minimum_effect"] = 0
        with self.assertRaisesRegex(ValueError, "outside complete policy"):
            M._verify_delta(self.docs["previous_improvement"], changed, self.delta["field_replacements"], self.case["deltas"])

    def _fixture_disposition(self, disposition):
        # Rebind synthetic fixture identities only; production cases remain fixed.
        for name in ("previous_improvement", "primary_improvement"):
            self.docs[name]["disposition"] = disposition
            self.case[name] = identity(self.docs[name])
        self.docs["descriptor"] = M.descriptor(TASK, self.delta)
        self.case["descriptor"] = identity(self.docs["descriptor"])
        self.pins = M.approved_pins(TASK)

    def test_retained_design_ready_is_metadata_only(self):
        self._fixture_disposition("design_ready")
        handle = self.authenticate()
        result = M.project(self.base, handle)
        self.assertEqual(result["evaluation"]["disposition"], "design_ready")
        self.assertEqual(result["admission"], self.base["admission"])
        self.assertIsNone(handle.primary_improvement["comparison"]["minimum_effect"])
        self.assertIsNone(handle.primary_improvement["comparison"]["uncertainty"])

    def test_qualification_promotion_rejected_even_by_synthetic_rebound_identity(self):
        self._fixture_disposition("improvement_ready")
        with self.assertRaisesRegex(ValueError, "scientific disposition"):
            self.authenticate()

    def test_delta_type_sensitive_values(self):
        change = {"json_pointer": "/value", "predecessor_value": 0, "successor_value": 1,
                  "predecessor_value_canonical_sha256": M._digest(0), "successor_value_canonical_sha256": M._digest(1)}
        with self.assertRaisesRegex(ValueError, "stale"):
            M._verify_delta({"value": False}, {"value": 1}, [change], ["/value"])

    def test_invalid_and_ambiguous_pointers_rejected(self):
        for pointer in ("", "value", "/", "/a//b", "/a/~1", "/a/00", "/a/-1", "/a/2"):
            with self.subTest(pointer=pointer), self.assertRaises(ValueError):
                M._replacement_target({"a": [1]}, pointer)

    def test_handle_blocks_attribute_replacement_and_deletion(self):
        handle = self.authenticate()
        for name in ("_payload", "_seal", "new"):
            with self.subTest(name=name), self.assertRaises(AttributeError):
                setattr(handle, name, None)
            with self.subTest(name=name), self.assertRaises(AttributeError):
                delattr(handle, name)

    def test_handle_properties_are_fresh_copies(self):
        handle = self.authenticate()
        handle.primary_improvement["disposition"] = "improvement_ready"
        handle.retained_improvement.clear()
        handle.descriptor_pin.clear()
        handle.members.clear()
        self.assertEqual(handle.primary_improvement["disposition"], "source_unresolved")
        self.assertEqual(handle.retained_improvement, self.docs["previous_improvement"])
        self.assertEqual(len(handle.members), 2)

    def test_forged_handle_and_mutated_preprojection_rejected(self):
        with self.assertRaises(ValueError):
            M.project(self.base, object())
        handle = self.authenticate()
        for field in ("goal", "resources", "admission", "primary_scope"):
            changed = copy.deepcopy(self.base)
            changed[field] = "unreviewed"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "projection"):
                M.project(changed, handle)

    def test_projection_keeps_old_sections_explicitly_and_current_policy_separate(self):
        handle = self.authenticate()
        before = copy.deepcopy(self.base)
        result = M.project(self.base, handle)
        self.assertEqual(self.base, before)
        self.assertEqual(result["episode"]["improvement"], self.docs["primary_improvement"]["episode"])
        self.assertEqual(result["blocking_issues"]["improvement"], ["current unresolved gap"])
        self.assertNotIn("preserved_limits", result["holds"])
        for field in M._SECTIONS:
            self.assertEqual(result["retained_pre_scope_policy"]["sections"][field], self.docs["previous_task"][field])
        self.assertEqual(result["evaluation"]["contracts"]["improvement"], M.CURRENT_FILE)
        self.assertIn(M.CURRENT_FILE, result["next_implementation_action"]["improvement"])

    def test_projection_preserves_materials_history_scope_admission_and_null_criteria(self):
        handle = self.authenticate()
        result = M.project(self.base, handle)
        for field in ("legacy", "resources", "input_assets", "provenance", "goal", "primary_scope", "admission"):
            self.assertEqual(result[field], self.base[field])
        self.assertIsNone(handle.primary_improvement["comparison"]["minimum_effect"])
        self.assertIsNone(handle.primary_improvement["comparison"]["uncertainty"])
        self.assertEqual(result["holds"]["remaining_primary_source_limits"], ["unresolved scientific source"])


if __name__ == "__main__":
    unittest.main()
