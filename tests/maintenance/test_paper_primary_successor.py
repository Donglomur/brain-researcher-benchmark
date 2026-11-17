"""Generated metadata controls for the fixed SMC successor selector.

Tiny invented documents replace the accepted identity table only within tests.
They are not SMC evidence. The independent source audit separately checks the
production pins against the accepted Git blobs and scientific-review packet.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]


def module(name):
    path = ROOT / "src/neurobench" / (name + ".py")
    spec = importlib.util.spec_from_file_location("_successor_control_" + name, path)
    result = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), "exec"), result.__dict__)
    return result


successor = module("paper_primary_successor")
binding = module("paper_outcomes_binding")


def raw(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def pin(path, value):
    return {"path": path, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}


class PrimarySuccessorTests(unittest.TestCase):
    def setUp(self):
        self.previous = {
            "schema_version": 1, "id": successor.TASK, "track": "paper",
            "title": "Invented previous title", "status": "design_ready",
            "objective": "surpass_source_paper_same_task", "scientific_question": "Invented question",
            "paper_identity": {"url": "https://example.invalid/invented-paper"},
            "official_code": {"commit": "invented-source-identity"},
            "primary_outputs": ["Invented retained source outputs"],
            "input_assets": {"observation_boundary": "Invented previous access", "source_panels": ["invented"]},
            "allowed_candidate_methods": "Invented previous methods",
            "resources": {"native_baseline_protocol": "invented-retained-pin", "participant_budget": None},
            "evaluation": {"contract": "invented-original-contract"}, "holds": ["Invented gap"],
            "next_implementation_action": "Invented next action",
            "provenance": {"scientific_contract": "invented-original-scientific-pin", "registration_role": "original"},
            "admission": {"runnable": False, "research_qualified": False, "submission_ready": False},
        }
        self.primary = {"task_id": successor.TASK, "same_task": {"target": {"description": "Invented primary target"}}}
        self.documents = {
            "previous_task": self.previous,
            "previous_improvement": {"task_id": successor.TASK, "retained": "invented-previous-policy"},
            "previous_scientific": {"retained": "invented-previous-scientific"},
            "primary_improvement": self.primary,
            "primary_scientific": {"primary": "invented-current-scientific"},
            "reproduction": {"task_id": successor.TASK, "findings": ["invented"]},
        }
        changes = {key: "Invented approved " + key for key in successor.FIELDS}
        changes["/primary_outputs"] = ["Invented reproduction", "Invented improvement"]
        changes["/holds"] = ["Invented unresolved current hold"]
        self.documents["projection"] = {
            "schema": "smc-temporal-task-projection-proposal/v1", "task_id": successor.TASK,
            "base_task_raw_sha256": hashlib.sha256(raw(self.previous)).hexdigest(),
            "field_replacements": changes,
        }
        table = {}
        self.files = {}
        for key, document in self.documents.items():
            suffix = successor._APPROVED[key][0]
            data = raw(document)
            table[key] = (suffix, len(data), hashlib.sha256(data).hexdigest(), successor._digest(document))
            self.files[successor.HOME + "/" + suffix] = data
        self.patch = mock.patch.object(successor, "_APPROVED", table)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.decision = "Invented reviewed root decision.\n"
        decision_patch = mock.patch.object(successor, "ROOT_DECISION",
                                          (len(self.decision.encode()), hashlib.sha256(self.decision.encode()).hexdigest()))
        decision_patch.start()
        self.addCleanup(decision_patch.stop)
        self.declaration = successor.descriptor(self.decision)
        self.save_descriptor()
        self.base = binding.project_task(self.previous, {"id": successor.TASK, "track": "paper"}, self.primary)
        self.reads = []

    def save_descriptor(self):
        data = raw(self.declaration)
        self.files[successor.DESCRIPTOR] = data
        self.revision_pin = pin(successor.DESCRIPTOR, data)

    def read(self, selected, label):
        self.reads.append(selected["path"])
        data = self.files[selected["path"]]
        self.assertEqual(selected, pin(selected["path"], data), label)
        return json.loads(data)

    def authenticate(self, **overrides):
        arguments = {"revision_pin": self.revision_pin,
                     "primary_pin": successor._pin("primary_improvement"),
                     "reproduction_pin": successor._pin("reproduction"),
                     "previous_pin": successor._pin("previous_task"),
                     "retained_improvement_pin": successor._pin("previous_improvement"),
                     "read_pin": self.read}
        arguments.update(overrides)
        return successor.authenticate(**arguments)

    def test_selects_offline_primary_and_preserves_original_lineage(self):
        before = copy.deepcopy(self.base)
        state = self.authenticate()
        result = successor.project(self.base, state)
        self.assertEqual(self.base, before)
        self.assertEqual(result["title"], self.documents["projection"]["field_replacements"]["/title"])
        self.assertEqual(result["evaluation"]["contracts"]["improvement"], "improvement.temporal-scope.v1.json")
        self.assertIn("offline-nlb-outcomes-v1/scorer.py", result["evaluation"]["candidate_interface"]["scorer"]["path"])
        self.assertIn("source-matched-nlb-v1/scorer.py", result["evaluation"]["author_reproduction_routes"]["scorer"]["path"])
        self.assertEqual(result["evaluation"]["retained_improvement_contract"], successor._pin("previous_improvement"))
        self.assertEqual(result["provenance"]["retained_pre_outcomes_scientific_contract"], self.previous["provenance"]["scientific_contract"])
        for key in ("resources", "paper_identity", "official_code", "status"):
            self.assertEqual(result[key], self.previous[key])
        self.assertEqual(result["input_assets"]["source_panels"], self.previous["input_assets"]["source_panels"])
        self.assertEqual(state.retained_improvement, self.documents["previous_improvement"])
        self.assertEqual(state.primary_improvement, self.primary)

    def test_only_fixed_metadata_is_read_and_no_scientific_status_is_promoted(self):
        state = self.authenticate()
        result = successor.project(self.base, state)
        self.assertEqual(set(self.reads), {successor.DESCRIPTOR} | {successor._pin(name)["path"] for name in successor._APPROVED})
        self.assertTrue(all(path.endswith(".json") for path in self.reads))
        self.assertEqual(len(self.reads), 8)
        self.assertTrue(all(result["admission"][key] is False for key in ("runnable", "research_qualified", "submission_ready")))
        self.assertIsNone(result["evaluation"]["executor_ref"])
        self.assertIsNone(result["evaluation"]["scorer_ref"])
        self.assertEqual(state.candidate_interface["scientific_outcome"], "unknown")
        self.assertEqual(state.author_reproduction_routes["scientific_outcome"], "unknown")
        self.assertEqual({member["path"] for member in state.members},
                         {successor.DESCRIPTOR, successor.PROJECTION, successor._pin("primary_improvement")["path"],
                          successor._pin("primary_scientific")["path"]})

    def test_handle_and_property_copies_cannot_mutate_authenticated_state(self):
        state = self.authenticate()
        expected = successor.project(self.base, state)
        state.primary_improvement["same_task"]["target"]["description"] = "corrupt"
        state.candidate_interface["scorer"]["sha256"] = "0" * 64
        state.members[0]["sha256"] = "0" * 64
        self.assertEqual(successor.project(self.base, state), expected)
        with self.assertRaises(AttributeError):
            state._payload = "{}"
        with self.assertRaises(AttributeError):
            del state._payload
        with self.assertRaises(AttributeError):
            del state._seal
        self.assertEqual(successor.project(self.base, state), expected)
        with self.assertRaises(ValueError):
            successor.project(self.base, {})

    def test_closed_descriptor_rejects_rehashed_unknown_key_or_policy(self):
        for key, value in (("task_id", "PAPER-OTHER"), ("revision", "v2"), ("scientific_outcome", "qualified"),
                           ("source_commit", "0" * 40), ("extra", True)):
            with self.subTest(key=key):
                self.declaration = successor.descriptor(self.decision)
                self.declaration[key] = value
                self.save_descriptor()
                with self.assertRaises(ValueError):
                    self.authenticate()

    def test_root_text_is_authenticated_not_just_declared_digest(self):
        self.declaration["root_decision"]["text"] += " broadened access"
        self.save_descriptor()
        with self.assertRaises(ValueError):
            self.authenticate()

    def test_rehashed_root_and_nested_pin_type_changes_are_rejected(self):
        self.declaration["root_decision"]["bytes"] = float(self.declaration["root_decision"]["bytes"])
        self.save_descriptor()
        with self.assertRaises(ValueError):
            self.authenticate()
        with self.assertRaises(ValueError):
            successor.descriptor(self.decision + "X" * 100000)

    def test_missing_swapped_traversal_or_rehashed_selector_rejected_before_read(self):
        for key in ("primary_pin", "reproduction_pin", "previous_pin", "retained_improvement_pin"):
            for value in (None, {"path": "../task.json", "bytes": 1, "sha256": "0" * 64},
                          {"path": successor._pin("primary_improvement")["path"], "bytes": 1, "sha256": "0" * 64}):
                with self.subTest(key=key, value=value):
                    self.reads.clear()
                    with self.assertRaises(ValueError):
                        self.authenticate(**{key: value})
                    self.assertEqual(self.reads, [])

    def test_descriptor_pin_must_be_exact_path_and_bounded(self):
        for changes in ({"path": "../primary-successor.v1.json"}, {"bytes": 65537}, {"bytes": True},
                        {"sha256": "0" * 63}, {"extra": False}):
            with self.subTest(changes=changes):
                selected = dict(self.revision_pin, **changes)
                with self.assertRaises(ValueError):
                    self.authenticate(revision_pin=selected)

    def test_callback_cannot_substitute_parsed_approved_document(self):
        for name in successor._APPROVED:
            def corrupt(selected, label):
                document = self.read(selected, label)
                if selected["path"] == successor._pin(name)["path"]:
                    document["injected"] = True
                return document
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.authenticate(read_pin=corrupt)

    def test_rehashing_arbitrary_field_correction_cannot_expand_authority(self):
        self.documents["projection"]["field_replacements"]["/resources"] = {"budget": "unlimited"}
        modified = raw(self.documents["projection"])
        self.files[successor.PROJECTION] = modified
        self.declaration["projection"] = pin(successor.PROJECTION, modified)
        self.save_descriptor()
        with self.assertRaises(ValueError):
            self.authenticate()

    def test_closed_projection_fields_remain_required_even_with_fixture_identity(self):
        proposal = copy.deepcopy(self.documents["projection"])
        proposal["field_replacements"]["/metrics"] = "invented malicious replacement"
        modified = raw(proposal)
        table = dict(successor._APPROVED)
        table["projection"] = (table["projection"][0], len(modified), hashlib.sha256(modified).hexdigest(), successor._digest(proposal))
        with mock.patch.object(successor, "_APPROVED", table):
            self.files[successor.PROJECTION] = modified
            self.declaration = successor.descriptor(self.decision)
            self.save_descriptor()
            with self.assertRaises(ValueError):
                self.authenticate()

    def test_unrelated_source_identity_resources_title_or_numeric_type_mutation_rejected(self):
        state = self.authenticate()
        for key, value in (("id", "PAPER-OTHER"), ("title", "unreviewed new title"), ("track", "neural"),
                           ("paper_identity", {}), ("official_code", {}), ("resources", {"budget": "unlimited"}),
                           ("scientific_question", "new target"), ("schema_version", 1.0), ("extra", True)):
            changed = copy.deepcopy(self.base)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                successor.project(changed, state)

    def test_wrong_primary_goal_and_admission_promotion_rejected(self):
        state = self.authenticate()
        changed = copy.deepcopy(self.base)
        changed["goal"] = "Old source-restricted candidate objective"
        with self.assertRaises(ValueError):
            successor.project(changed, state)
        for key, value in (("runnable", True), ("research_qualified", True), ("submission_ready", 0),
                           ("qualified", True), ("reason", "already qualified")):
            changed = copy.deepcopy(self.base)
            changed["admission"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                successor.project(changed, state)

    def test_candidate_executor_extra_qualification_and_criterion_mutation_rejected(self):
        state = self.authenticate()
        for key, value in (("executor_ref", "native.py"), ("scientific_outcome", "success"),
                           ("binary_reward_registered", 0), ("paired_protocol", "other.json")):
            changed = copy.deepcopy(self.base)
            changed["evaluation"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                successor.project(changed, state)
        for index in range(6):
            changed = copy.deepcopy(self.base)
            changed["success_criteria"][index] = "Invented criterion or score"
            with self.subTest(index=index), self.assertRaises(ValueError):
                successor.project(changed, state)


if __name__ == "__main__":
    unittest.main()
