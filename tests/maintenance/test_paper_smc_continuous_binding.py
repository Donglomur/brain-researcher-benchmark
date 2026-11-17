"""Generated metadata controls for the fixed SMC continuous-current selector.

Accepted identities are replaced with invented, internally pinned documents in
this process only. No task implementation is imported or executed. The real
proposal/retained-byte closure is checked separately during current adoption.
"""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
base = runpy.run_path(str(ROOT / "tests/maintenance/test_paper_primary_successor_binding.py"))
SuccessorFixture = base["SuccessorFixture"]
binder, binding = base["binder"], base["binding"]


def configure_continuous(case):
    """Add an invented continuous layer to an already adopted temporal fixture."""
    module = case.module
    temporal_raw = (case.root / case.task_path).read_bytes()
    temporal = json.loads(temporal_raw)
    original_descriptor = module.continuous_descriptor
    decision = "Invented continuous policy decision; generated metadata only.\n"
    patcher = mock.patch.object(module, "CONTINUOUS_ROOT", (
        len(decision.encode()), hashlib.sha256(decision.encode()).hexdigest()))
    patcher.start()
    case.addCleanup(patcher.stop)
    policy = {"schema": "smc_continuous_measurement_policy_v1", "task_id": case.identifier,
              "root_adoption_sha256": module.CONTINUOUS_ROOT[1], "tolerance": None}
    policy_pin = binding.pin(module.CONTINUOUS_PACKAGE + "policy.json", binding.encode(policy))
    entry = case.put_pin(module.CONTINUOUS_PACKAGE + "benchmark.py",
                         b'raise AssertionError("Generated task source must never execute")\n')
    patcher = mock.patch.object(module, "continuous_entrypoint", return_value=entry)
    patcher.start()
    case.addCleanup(patcher.stop)
    values = {pointer: "Invented continuous correction " + pointer for pointer in module._CONTINUOUS_FIELDS}
    values.update({
        "/admission": {"runnable": False, "research_qualified": False, "submission_ready": False},
        "/continuous_outcomes_v1": {"version": 1, "policy_sha256": policy_pin["sha256"]},
        "/evaluation/candidate_interface": {"role": "continuous_paired_outcomes", "policy": policy_pin,
            "delivery": entry, "scorer": entry, "scientific_outcome": "not_attempted",
            "selection_limit": "Generated route is not an instantiated or qualified scientific episode."},
        "/evaluation/continuous_assessment": {"binary_reproduction": "not_applicable",
            "binary_improvement": "not_applicable", "aggregation_across_arms_or_metrics": "none"},
        "/evaluation/contracts": {"reproduction": "implementations/continuous-outcomes-v1/policy.json",
                                  "improvement": "implementations/continuous-outcomes-v1/policy.json"},
        "/evaluation/operator_entrypoint": dict(entry, commands=["prepare", "inspect", "freeze", "score"]),
        "/evaluation/paired_protocol": None,
        "/evaluation/retained_pre_continuous_contracts": {"reproduction": "reproduction.v1.json",
                                                        "improvement": "improvement.temporal-scope.v1.json"},
        "/evaluation/retained_pre_continuous_paired_protocol": "outcomes.v1.json",
        "/evaluation/scorer_ref": entry["path"],
        "/holds": ["Invented materials and execution remain unattempted."],
        "/primary_outputs": ["Invented continuous discrepancy", "Invented continuous metric vector"],
        "/provenance/continuous_policy": policy_pin,
        "/provenance/continuous_predecessor": binding.pin(module.CONTINUOUS_PACKAGE + "predecessor.task.json", temporal_raw),
        "/resources/participant_access_budget": {"policy_sha256": policy_pin["sha256"]},
        "/resources/participant_resource_budget": {"matched_across_access_conditions": True},
        "/success_criteria": ["Invented continuous reporting without a binary threshold."],
    })
    proposal = copy.deepcopy(temporal)
    for pointer, value in values.items():
        keys = pointer[1:].split("/")
        target = proposal
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = copy.deepcopy(value)
    proposal_raw = (json.dumps(proposal, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    documents = {
        "retained_task": temporal_raw, "source_predecessor": temporal_raw,
        "policy": binding.encode(policy),
        "amendment": binding.encode({"schema": "smc_continuous_task_amendment_proposal_v1",
                                      "set_by_json_pointer": values}),
        "proposal": proposal_raw,
        "retained_outcomes": (case.root / (case.home + "/outcomes.v1.json")).read_bytes(),
    }
    table = {}
    for name, raw in documents.items():
        path = module._CONTINUOUS_APPROVED[name][0]
        table[name] = (path, len(raw), hashlib.sha256(raw).hexdigest(), module._digest(json.loads(raw)))
        case.put(path, raw)
    patcher = mock.patch.object(module, "_CONTINUOUS_APPROVED", table)
    patcher.start()
    case.addCleanup(patcher.stop)
    def generated_descriptor(text):
        result = original_descriptor(text)
        result["retained_temporal_revision"] = case.revision_pin
        return result
    patcher = mock.patch.object(module, "continuous_descriptor", side_effect=generated_descriptor)
    patcher.start()
    case.addCleanup(patcher.stop)
    current_revision = case.put_pin(module.CONTINUOUS_DESCRIPTOR, generated_descriptor(decision))
    registry = case.load(binding.REGISTRY)
    row = next(item for item in registry["tasks"] if item["id"] == case.identifier)
    row["paper_outcomes"]["continuous_policy_revision"] = current_revision
    row["specification"] = case.put_pin(case.task_path, proposal_raw)
    case.put(binding.REGISTRY, registry)
    case.continuous = {"revision": current_revision, "policy": policy_pin,
        "temporal_raw": temporal_raw, "proposal_raw": proposal_raw, "documents": documents}
    return case.continuous


class ContinuousBindingTests(SuccessorFixture):
    def setUp(self):
        super().setUp()
        self.adopt()
        self.temporal_snapshot = self.snapshot()
        configure_continuous(self)

    def test_current_contracts_are_typed_policy_and_results_unattempted(self):
        row, context = self.context()
        public = binding.public_summary(row, context)
        self.assertEqual(public["reproduction_contract"], self.continuous["policy"])
        self.assertEqual(public["improvement_contract"], self.continuous["policy"])
        self.assertIsNone(public["outcomes"])
        self.assertEqual(public["improvement_disposition"], "continuous_measurement")
        self.assertEqual(public["continuous_outcomes_v1"]["legacy_binary_admission"], "not_applicable")
        self.assertIsNone(public["continuous_outcomes_v1"]["paired_protocol"])
        self.assertTrue(all(cell["result_status"] == "not_attempted" and cell["scientific_outcome"] == "unknown"
                            and not cell["condition_available"] and cell["endpoint_eligible"] is None
                            for cell in public["cells"]))
        self.assertEqual(context["improvement_contract"], self.primary)
        self.assertEqual(context["retained_improvement_contract"], self.old)
        self.assertEqual(context["outcomes"]["original_task_sha256"], hashlib.sha256(self.continuous["temporal_raw"]).hexdigest())

    def test_binder_is_idempotent_and_preserves_old_bytes(self):
        before = self.snapshot()
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)
        self.assertEqual(binder.write_or_check(self.root, write=True)["changed_files"], 0)
        self.assertEqual(self.snapshot(), before)
        for suffix in ("reproduction.v1.json", "improvement.v1.json", "improvement.temporal-scope.v1.json",
                       "outcomes.v1.json", "primary-successor.v1.json"):
            path = self.home + "/" + suffix
            self.assertEqual(before[path], self.temporal_snapshot[path])
        self.assertEqual(before[self.module.CONTINUOUS_ARCHIVE], self.continuous["temporal_raw"])
        self.assertEqual(before[self.task_path], self.continuous["proposal_raw"])

    def test_only_descriptor_and_archive_gain_metadata_ownership(self):
        _, context = self.context()
        self.assertIn(self.module.CONTINUOUS_DESCRIPTOR, context["members"])
        self.assertIn(self.module.CONTINUOUS_ARCHIVE, context["members"])
        self.assertFalse(any(path.startswith(self.module.CONTINUOUS_PACKAGE) for path in context["members"]))

    def test_missing_selector_cannot_downgrade_current_task(self):
        registry = self.load(binding.REGISTRY)
        del registry["tasks"][0]["paper_outcomes"]["continuous_policy_revision"]
        self.put(binding.REGISTRY, registry)
        self.reject_without_writes()

    def test_selector_is_smc_only_and_requires_retained_temporal_pair(self):
        row = copy.deepcopy(self.load(binding.REGISTRY)["tasks"][0])
        row["id"] = "PAPER-INVENTED-OTHER"
        with self.assertRaises(ValueError):
            binding.has_continuous_outcomes(row)
        row["id"] = self.identifier
        del row["paper_outcomes"]["primary_improvement_contract"]
        with self.assertRaises(ValueError):
            binding.has_continuous_outcomes(row)

    def test_rehashed_descriptor_cannot_change_root_or_add_qualification(self):
        original = self.load(self.module.CONTINUOUS_DESCRIPTOR)
        for mutate in (lambda doc: doc["root_decision"].update(text="Unauthorized root decision"),
                       lambda doc: doc.update(scientific_outcome="qualified")):
            changed = copy.deepcopy(original)
            mutate(changed)
            registry = self.load(binding.REGISTRY)
            registry["tasks"][0]["paper_outcomes"]["continuous_policy_revision"] = self.put_pin(self.module.CONTINUOUS_DESCRIPTOR, changed)
            self.put(binding.REGISTRY, registry)
            self.reject_without_writes()

    def test_changed_source_policy_or_predecessor_is_rejected(self):
        for name in ("policy", "amendment", "proposal", "retained_task", "source_predecessor"):
            with self.subTest(name=name):
                path = self.module.continuous_pin(name)["path"]
                raw = (self.root / path).read_bytes()
                self.put(path, raw + b" ")
                self.reject_without_writes()
                self.put(path, raw)

    def test_current_rehash_cannot_change_reviewed_projection(self):
        changed = self.load(self.task_path)
        changed["success_criteria"] = ["Invented unreviewed binary win"]
        registry = self.load(binding.REGISTRY)
        registry["tasks"][0]["specification"] = self.put_pin(self.task_path, changed)
        self.put(binding.REGISTRY, registry)
        self.reject_without_writes()

    def test_old_bundle_cannot_be_repinned_as_continuous_admission(self):
        registry = self.load(binding.REGISTRY)
        outcomes = self.load(self.home + "/outcomes.v1.json")
        outcomes["original_task_sha256"] = registry["tasks"][0]["specification"]["sha256"]
        registry["tasks"][0]["paper_outcomes"]["outcomes"] = self.put_pin(self.home + "/outcomes.v1.json", outcomes)
        self.put(binding.REGISTRY, registry)
        self.reject_without_writes()

    def test_authenticated_handle_cannot_be_deleted_or_mutated_through_snapshot(self):
        handles = []
        original = self.module.project_continuous
        def capture(task, handle):
            handles.append(handle)
            return original(task, handle)
        with mock.patch.object(self.module, "project_continuous", side_effect=capture):
            self.context()
        handle = handles[0]
        with self.assertRaises(AttributeError):
            del handle._payload
        with self.assertRaises(AttributeError):
            handle._payload = "{}"
        changed = handle.snapshot()
        changed["documents"]["policy"]["tolerance"] = 1
        self.assertIsNone(handle.snapshot()["documents"]["policy"]["tolerance"])
        self.assertEqual(binding.encode(original(json.loads(self.continuous["temporal_raw"]), handle)),
                         self.continuous["proposal_raw"])


if __name__ == "__main__":
    unittest.main()
