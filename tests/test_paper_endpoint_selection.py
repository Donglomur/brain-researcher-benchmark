"""Synthetic software controls only; no scientific data, execution, or results."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


HERE = Path(__file__).parent
BINDING_SOURCE = HERE / "paper_outcomes_binding.py"
if not BINDING_SOURCE.is_file():
    BINDING_SOURCE = HERE.parent / "src" / "neurobench" / "paper_outcomes_binding.py"
spec = importlib.util.spec_from_file_location("endpoint_test_binding", BINDING_SOURCE)
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)
selector = binding.endpoint_selection_module()
IDENTIFIER = "PAPER-FIND-036"


class Rows(dict):
    pass


class Fixture:
    def __init__(self):
        self.files = {}
        self.home = "benchmarks/paper/" + IDENTIFIER
        self.endpoint = self.home + "/primary-endpoint-v1/"
        self.scope = "Synthetic software fixture endpoint; not a scientific task"
        self.retained_scope = "Synthetic retained biological-scope declaration; no scientific result"
        evidence = [{"id": "fixture-paper", "kind": "paper", "url": "https://example.invalid/software-fixture",
                     "locator": "Synthetic metadata test only", "supports": "Metadata rejection control"}]
        anchors = {key: {"status": "unresolved", "description": self.scope if key == "target" else "Synthetic " + key,
                         "evidence_ids": ["fixture-paper"]} for key in binding.engine().improvement.ANCHORS}
        baseline = {"status": "unresolved", "value": None, "description": "No scientific baseline",
                    "evidence_ids": ["fixture-paper"]}
        self.improvement = {
            "schema_version": "paper-improvement/v1", "task_id": IDENTIFIER,
            "objective": "surpass_source_paper_same_task", "disposition": "source_unresolved",
            "disposition_reason": "Synthetic metadata control", "source_paper": {"title": "Synthetic software fixture",
            "url": "https://example.invalid/software-fixture"}, "evidence": evidence, "same_task": anchors,
            "comparison": {"primary_metric": "Synthetic metric", "direction": "higher",
                           "published_baseline": copy.deepcopy(baseline), "reproduced_author_baseline": copy.deepcopy(baseline),
                           "minimum_effect": {"status": "unresolved", "value": None, "rationale": "No scientific criterion",
                                              "evidence_ids": []},
                           "uncertainty": {"status": "unresolved", "method": "Unresolved", "independent_unit": "Unresolved",
                                           "rationale": "No scientific criterion", "evidence_ids": []},
                           "paper_win_requires": ["Authentic original-source comparison"],
                           "current_sota": {"status": "not_claimed", "description": "Never a scientific result", "evidence_ids": []}},
            "episode": {"improvement_loop": "Uninstantiated", "candidate_freeze": "Uninstantiated",
                        "final_evaluation": "Uninstantiated", "access_budget": None, "resource_budget": None,
                        "baseline_policy": "No scientific baseline"},
            "blocking_issues": ["Synthetic fixture has no scientific artifacts"],
            "legacy": {"role": "no_predecessor", "original_task": None, "notes": "Software-only fixture"}}
        self.reproduction = {
            "schema_version": "paper-reproduction/v1", "task_id": IDENTIFIER,
            "objective": "recreate_original_findings_same_task", "eligibility": "source_unresolved",
            "eligibility_reason": "Synthetic metadata control", "source_paper": self.improvement["source_paper"],
            "evidence": evidence, "same_task": copy.deepcopy(anchors),
            "findings": [{"id": "fixture", "kind": "scalar", "description": "Synthetic source target", "status": "unresolved",
                          "expected": None, "units": "Synthetic", "aggregation": "No fabricated aggregation",
                          "evidence_ids": ["fixture-paper"], "categories": [],
                          "tolerance": {"status": "unresolved", "absolute": None, "rationale": "Not a scientific criterion", "evidence_ids": []},
                          "uncertainty": {"kind": "unresolved", "method": "Unresolved", "independent_unit": "Unresolved",
                                          "minimum_independent_units": None, "confidence_level": None, "statistic": None,
                                          "operator": None, "threshold": None, "rationale": "No scientific criterion", "evidence_ids": []}}],
            "panel_rule": "all_declared_findings_and_companions", "blocking_issues": ["No scientific artifacts"]}
        for key in ("full_panel", "permitted_observations"):
            self.reproduction["same_task"][key] = {"status": "unresolved", "description": "Synthetic " + key,
                                                   "evidence_ids": ["fixture-paper"]}
        self.task = {"id": IDENTIFIER, "title": "Software control", "track": "paper", "status": "source_unresolved",
                     "objective": binding.OBJECTIVE, "primary_scope": self.scope, "retained_secondary_scope": self.retained_scope,
                     "scope_decision": {"path": selector.AUTHORITY_PATH, "task_entry_id": IDENTIFIER},
                     "evaluation": {"contracts": {"reproduction": "primary-endpoint-v1/reproduction.v1.json",
                                                   "improvement": "primary-endpoint-v1/improvement.v1.json"},
                                    "paired_protocol": "primary-endpoint-v1/outcomes.v1.json",
                                    "information_conditions": ["paper_data", "paper_data_author_code"],
                                    "executor_ref": None, "scorer_ref": None, "binary_reward_registered": False}}
        oldtask = {"id": IDENTIFIER, "objective": binding.OBJECTIVE, "status": "source_unresolved", "prior_scope": "Synthetic broader scope"}
        oldtask_identity = self.put(self.home + "/task.json", oldtask)
        history = self.put(self.home + "/historical/task.pre-outcomes.v1.json", {"id": IDENTIFIER, "objective": "surpass_source_paper_same_task"})
        oldimp = self.put(self.home + "/improvement.v1.json", self.improvement)
        oldout = self.put(self.home + "/outcomes.v1.json", {"schema_version": "paper-outcomes-unavailable/v1", "task_id": IDENTIFIER})
        self.oldrow = {"id": IDENTIFIER, "title": "Software control", "track": "paper", "task_directory": self.home,
                       "specification": oldtask_identity["pin"], "specification_revision": {"improvement_contract": oldimp["pin"]},
                       "paper_outcomes": {"previous_specification": history["pin"], "outcomes": oldout["pin"]}}
        self.previous = Rows({IDENTIFIER: {"id": IDENTIFIER, "track": "paper", "specification": history["pin"]}})
        self.previous.scope_decisions = {"entries": {IDENTIFIER: {"prior": "scope"}}}
        self.previous.scope_pin = self.put("docs/provenance/paper-outcome-scope-decisions.v1.json", self.previous.scope_decisions)["pin"]
        self.previous.source_declaration_gaps = {"source": "Synthetic retained gap authority"}
        self.previous.source_declaration_gap_pin = self.put("docs/provenance/paper-outcome-source-declaration-gaps.v1.json", self.previous.source_declaration_gaps)["pin"]
        self.scope_policy = self.put(selector.POLICY_PATH, {"fixture": "Synthetic adopted policy for software controls"})
        self.entry = {"task_id": IDENTIFIER, "previous_registry_row": copy.deepcopy(self.oldrow),
                      "predecessor_task": {"route": "git_blob", "source_commit": selector.BASE_COMMIT,
                                           "source_path": self.home + "/task.json", "identity": oldtask_identity},
                      "retained_documents": [{"role": "prior_improvement", "scope": "Synthetic", "identity": oldimp},
                                             {"role": "prior_outcomes", "scope": "Synthetic", "identity": oldout}],
                      "selected_documents": {}, "scope": {"kind": selector.SELECTION_KIND, "primary_scope": self.scope, "target_description": self.scope,
                          "retained_secondary_scope": self.retained_scope, "source_locator": "Synthetic fixture",
                          "source_evidence_ids": ["fixture-paper"]},
                      "access_policy": {"status": "declared_uninstantiated", "common_input_ids": ["paper", "training-data"],
                          "author_code_only_ids": ["official-code"], "evaluator_only_ids": ["test-answers"],
                          "assisted_common_input_ids": [], "paper_data": ["paper", "training-data"],
                          "paper_data_author_code": ["paper", "training-data", "official-code"],
                          "original_information_limits": ["No test-answer access"], "source_evidence_ids": ["fixture-paper"]},
                      "review": {"semantic_review_sha256": "a" * 64, "complete_task_delta_sha256": "b" * 64},
                      "remaining_blockers": ["Synthetic software fixture; no scientific execution"], "reviewed_evidence": []}
        self.refresh()

    def put(self, path, value):
        raw = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
        self.files[path] = raw
        return {"pin": {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
                "canonical_sha256": selector.canonical(value)}

    def refresh(self):
        selected = self.entry["selected_documents"]
        selected.update({"task": self.put(self.home + "/task.json", self.task),
                         "improvement": self.put(self.endpoint + "improvement.v1.json", self.improvement),
                         "reproduction": self.put(self.endpoint + "reproduction.v1.json", self.reproduction),
                         "selection": self.put(self.endpoint + "selection.v1.json", {"fixture": "Opaque reviewed explanatory selection"}),
                         "access_conditions": self.put(self.endpoint + "access-conditions.v1.json", {"fixture": "Opaque reviewed explanatory access"})})
        engine = binding.engine()
        outcomes = {"schema_version": "paper-outcomes/v1", "task_id": IDENTIFIER,
                    "original_task_sha256": selected["task"]["pin"]["sha256"],
                    "contracts": {"reproduction": engine.contract_digest(self.reproduction),
                                  "improvement": engine.contract_digest(self.improvement)},
                    "pairing": {key: {"status": "unresolved", "rationale": "No source execution in software controls", "protocol": None}
                                for key in ("reproduction", "improvement")}}
        selected["outcomes"] = self.put(self.endpoint + "outcomes.v1.json", outcomes)
        self.row = copy.deepcopy(self.oldrow)
        self.row["title"] = self.task["title"]
        self.row["specification"] = selected["task"]["pin"]
        self.row["paper_outcomes"] = {"schema_version": binding.VERSION,
            "previous_specification": self.oldrow["paper_outcomes"]["previous_specification"],
            "reproduction_contract": selected["reproduction"]["pin"], "outcomes": selected["outcomes"]["pin"],
            "endpoint_selection": selected["selection"]["pin"]}
        self.authority = {"schema_version": selector.AUTHORITY_VERSION, "source_commit": selector.BASE_COMMIT,
                          "scope_policy_sha256": self.scope_policy["pin"]["sha256"], "scope_policy": self.scope_policy,
                          "source_scope_authority": {"pin": self.previous.scope_pin, "canonical_sha256": selector.canonical(self.previous.scope_decisions)},
                          "source_gap_authority": {"pin": self.previous.source_declaration_gap_pin, "canonical_sha256": selector.canonical(self.previous.source_declaration_gaps)},
                          "entries": {IDENTIFIER: self.entry}}
        self.authority_identity = self.put(selector.AUTHORITY_PATH, self.authority)

    def read(self, pin, label):
        raw = self.files[pin["path"]]
        if len(raw) != pin["bytes"] or hashlib.sha256(raw).hexdigest() != pin["sha256"]:
            raise ValueError("Raw identity differs: " + label)
        return json.loads(raw)

    def adopt(self):
        self.previous.endpoint_selections = selector.authenticate_authority(
            self.authority_identity["pin"], self.previous, [self.row], self.read)
        return self.previous.endpoint_selections


class EndpointSelectionControls(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.stack = []
        self.allow_fixture()

    def allow_fixture(self):
        for name, value in (("TASKS", frozenset((IDENTIFIER,))),
                            ("POLICY_SHA256", self.f.scope_policy["pin"]["sha256"]),
                            ("AUTHORITY_PIN", self.f.authority_identity["pin"]),
                            ("AUTHORITY_CANONICAL", self.f.authority_identity["canonical_sha256"])):
            control = patch.object(selector, name, value)
            control.start(); self.stack.append(control)

    def tearDown(self):
        for control in reversed(self.stack):
            control.stop()

    def context(self):
        self.f.adopt()
        return binding.context(self.f.row, self.f.task, self.f.previous, self.f.read)

    def test_positive_declared_only_cells(self):
        result = self.context()
        self.assertEqual(result["availability"], "available")
        self.assertEqual(result["primary_policy_revision"], self.f.entry["selected_documents"]["selection"]["pin"])
        self.assertEqual(binding.endpoint_selection_ids(self.f.previous), {IDENTIFIER})
        for cell in result["summary"]["cells"]:
            self.assertFalse(cell["condition_available"])
            self.assertFalse(cell["endpoint_eligible"])
            self.assertIsNone(cell["receipt"])
            self.assertEqual(cell["scientific_outcome"], "unknown")

    def test_title_is_bound_to_selected_task_and_other_registration_fields_are_immutable(self):
        self.f.oldrow.update(status="source_unresolved", resources={"cpu_threads": 1})
        self.f.entry["previous_registry_row"] = copy.deepcopy(self.f.oldrow)
        self.f.task["title"] = "Reviewed selected endpoint title"
        self.f.refresh(); self.allow_fixture()
        self.assertNotEqual(self.f.row["title"], self.f.oldrow["title"])
        self.assertEqual(self.f.row["title"], self.f.task["title"])
        result = self.context()
        self.assertEqual(result["availability"], "available")
        self.assertTrue(all(cell["scientific_outcome"] == "unknown"
                            for cell in result["summary"]["cells"]))

        for title in ("Unreviewed replacement", self.f.oldrow["title"], "", None):
            row = copy.deepcopy(self.f.row)
            row["title"] = title
            with self.subTest(title=title), self.assertRaisesRegex(ValueError, "registration title"):
                selector.authenticate_authority(self.f.authority_identity["pin"],
                                                self.f.previous, [row], self.f.read)

        for field, changed in (("id", "PAPER-not-reviewed"), ("track", "neural"),
                               ("task_directory", "benchmarks/paper/other"),
                               ("status", "ready"), ("resources", {"cpu_threads": 2}),
                               ("specification_revision", {})):
            row = copy.deepcopy(self.f.row)
            row[field] = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                selector.authenticate_authority(self.f.authority_identity["pin"],
                                                self.f.previous, [row], self.f.read)

        task_path = self.f.entry["selected_documents"]["task"]["pin"]["path"]
        raw = self.f.files[task_path]
        try:
            self.f.files[task_path] = raw + b" "
            with self.assertRaisesRegex(ValueError, "Raw identity differs"):
                self.f.adopt()
        finally:
            self.f.files[task_path] = raw

        def substituted_task(pin, label):
            value = self.f.read(pin, label)
            if pin["path"] == task_path:
                value["title"] = "Callback substitution"
            return value

        row = copy.deepcopy(self.f.row)
        row["title"] = "Callback substitution"
        with self.assertRaisesRegex(ValueError, "parsed identity"):
            selector.authenticate_authority(self.f.authority_identity["pin"],
                                            self.f.previous, [row], substituted_task)

    def test_real_coverage_accepts_only_authority_selected_titles(self):
        """Use real coverage and complete generated records, without adapters."""
        import ast
        from types import SimpleNamespace

        self.f.oldrow["specification_alias"] = False
        self.f.entry["previous_registry_row"] = copy.deepcopy(self.f.oldrow)
        self.f.task["title"] = "Pinned selected title after the prior scope"
        selected_prior = copy.deepcopy(self.f.oldrow)
        selected_prior.pop("paper_outcomes")
        selected_prior["specification"] = {
            **self.f.oldrow["paper_outcomes"]["previous_specification"],
            "path": self.f.home + "/task.json"}

        # Reuse only the existing pure generated-record factory. Its test setup
        # and other controls are not imported or executed.
        factory_path = HERE.parent / "tests/maintenance/test_paper_declaration_gaps.py"
        parsed = ast.parse(factory_path.read_bytes())
        factory_ast = ast.Module(body=[node for node in parsed.body
                                      if isinstance(node, ast.FunctionDef) and node.name == "record"],
                                type_ignores=[])
        gaps = binding.declaration_gap_module()
        factory = {"copy": copy, "binding": binding, "gaps": gaps}
        exec(compile(factory_ast, str(factory_path), "exec"), factory)
        cases, gap_rows, gap_history = {}, [], {}
        for identifier in sorted(gaps.TASK_IDS):
            home = "benchmarks/paper/" + identifier
            task = {"id": identifier, "title": "Generated gap predecessor",
                    "objective": "surpass_source_paper_same_task"}
            improvement = copy.deepcopy(self.f.improvement)
            improvement["task_id"] = identifier
            row = {"id": identifier, "title": task["title"], "track": "paper",
                   "task_directory": home, "specification_alias": False,
                   "specification": self.f.put(home + "/task.json", task)["pin"],
                   "specification_revision": {"improvement_contract":
                       self.f.put(home + "/improvement.v1.json", improvement)["pin"]}}
            gap_history[identifier] = self.f.put(home + "/" + binding.HISTORY, task)["pin"]
            cases[identifier] = SimpleNamespace(prior_row=row, improvement=improvement)
            gap_rows.append(row)
        gap_document = factory["record"](cases)
        gap_pin = self.f.put(binding.SOURCE_DECLARATION_GAP_PATH, gap_document)["pin"]
        scope = {"schema_version": binding.SCOPE_VERSION, "entries": {
            identifier: {"task_id": identifier, "primary_goal": "Generated primary goal",
                         "primary_scope": "Generated primary scope",
                         "retained_secondary_scope": "Generated retained scope",
                         "remaining_source_limits": ["No scientific artifacts"],
                         "primary_same_task_improvement": "unavailable_until_independently_justified",
                         "paired_bundle_status": "unavailable_primary_secondary_scope_mismatch",
                         "scientific_outcome": "unknown"}
            for identifier in sorted(binding.SCOPE_IDS)},
            "source_gap_confirmations": {IDENTIFIER: {"task_id": IDENTIFIER,
                "projection_action": "none", "scientific_outcome": "unknown"}}}
        scope_pin = self.f.put(binding.SCOPE_PATH, scope)["pin"]
        self.f.previous.scope_decisions, self.f.previous.scope_pin = scope, scope_pin
        self.f.previous.source_declaration_gaps = gap_document
        self.f.previous.source_declaration_gap_pin = gap_pin
        snapshot = {"schema_version": 1, "kind": "neuroscience_benchmark_registry",
                    "tasks": [selected_prior] + copy.deepcopy(gap_rows)}
        snapshot_pin = self.f.put(binding.SNAPSHOT, snapshot)["pin"]
        self.f.refresh(); self.allow_fixture()
        current_gaps = copy.deepcopy(gap_rows)
        for row in current_gaps:
            row["paper_outcomes"] = {"schema_version": binding.VERSION,
                "previous_specification": gap_history[row["id"]], "source_declaration_gap": gap_pin}
        registry = {"tasks": [copy.deepcopy(self.f.row)] + current_gaps,
                    "paper_outcomes": {"schema_version": binding.VERSION,
                        "coverage_required": True, "registered_count": 3,
                        "pre_outcomes_registry": snapshot_pin, "scope_decisions": scope_pin,
                        "source_declaration_gaps": gap_pin,
                        "endpoint_selections": self.f.authority_identity["pin"]}}

        # The original prior-title equality deterministically rejects this case.
        self.assertNotEqual(registry["tasks"][0]["title"], selected_prior["title"])
        previous = binding.coverage(registry, self.f.read)
        self.assertIs(type(previous.endpoint_selections), selector.Authority)
        self.assertEqual(binding.endpoint_selection_ids(previous), {IDENTIFIER})
        result = binding.context(self.f.row, self.f.task, previous, self.f.read)
        self.assertEqual(result["availability"], "available")
        self.assertTrue(all(cell["scientific_outcome"] == "unknown"
                            for cell in result["summary"]["cells"]))

        for title in ("Unpinned title", selected_prior["title"]):
            altered = copy.deepcopy(registry)
            altered["tasks"][0]["title"] = title
            with self.subTest(title=title), self.assertRaisesRegex(ValueError, "registration title"):
                binding.coverage(altered, self.f.read)
        altered = copy.deepcopy(registry)
        altered["paper_outcomes"].pop("endpoint_selections")
        with self.assertRaisesRegex(ValueError, "cannot omit"):
            binding.coverage(altered, self.f.read)
        altered = copy.deepcopy(registry)
        altered["tasks"][1]["title"] = "Changed nonselected title"
        with self.assertRaisesRegex(ValueError, "changed prior title"):
            binding.coverage(altered, self.f.read)
        altered = copy.deepcopy(registry)
        altered["tasks"][0]["specification_alias"] = True
        with self.assertRaisesRegex(ValueError, "registration identity"):
            binding.coverage(altered, self.f.read)
        altered = copy.deepcopy(registry)
        altered["tasks"][1]["specification_alias"] = 0
        with self.assertRaisesRegex(ValueError, "changed prior specification_alias"):
            binding.coverage(altered, self.f.read)

    def test_scope_narrative_can_differ_from_scientific_target(self):
        self.f.task["primary_scope"] = self.f.scope + "; complete source panel and companion controls"
        self.f.entry["scope"]["primary_scope"] = self.f.task["primary_scope"]
        self.f.refresh(); self.allow_fixture()
        self.assertEqual(self.context()["availability"], "available")

    def test_retained_improvement_ownership_is_not_duplicated(self):
        result = self.context()
        self.assertNotIn(result["retained_improvement_contract_pin"]["path"], result["members"])
        self.assertEqual(self.f.previous.endpoint_selections.policy_pin, self.f.scope_policy["pin"])

    def test_required_extra_evidence_is_owned_exported_and_authenticated(self):
        path = self.f.endpoint + "granular-evidence.v1.json"
        self.f.entry["reviewed_evidence"] = [{"role": "Mandatory audit records; not numerical targets",
                                               "identity": self.f.put(path, {"audit": "software fixture"})}]
        self.f.refresh(); self.allow_fixture()
        result = self.context()
        self.assertIn(path, result["members"])
        self.assertEqual(result["primary_policy_provenance"]["reviewed_evidence_000"]["path"], path)
        self.f.files[path] = b"{}"
        with self.assertRaisesRegex(ValueError, "Raw identity differs"):
            binding.context(self.f.row, self.f.task, self.f.previous, self.f.read)

    def test_unpopulated_authority_refuses_self_approval(self):
        with patch.object(selector, "AUTHORITY_PIN", None), patch.object(selector, "AUTHORITY_CANONICAL", None):
            with self.assertRaisesRegex(ValueError, "not adopted"):
                self.f.adopt()

    def test_adopted_authority_cannot_be_omitted(self):
        with self.assertRaisesRegex(ValueError, "cannot omit"):
            selector.authenticate_authority(None, self.f.previous, [], self.f.read)

    def test_adopted_selector_cannot_fall_back(self):
        self.f.row["paper_outcomes"] = self.f.oldrow["paper_outcomes"]
        with self.assertRaisesRegex(ValueError, "fall back"):
            self.f.adopt()

    def test_partial_or_mixed_selector_rejected(self):
        for mode in ("partial", "mixed"):
            row = copy.deepcopy(self.f.row)
            if mode == "partial": del row["paper_outcomes"]["outcomes"]
            else: row["paper_outcomes"]["primary_policy_revision"] = row["paper_outcomes"]["endpoint_selection"]
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "complete unmixed"):
                selector.has_endpoint_selection(row)

    def test_unaccepted_id_rejected(self):
        row = copy.deepcopy(self.f.row); row["id"] = "PAPER-not-reviewed"
        with self.assertRaisesRegex(ValueError, "reviewed paper batch"):
            selector.has_endpoint_selection(row)

    def test_incomplete_batch_rejected(self):
        with patch.object(selector, "TASKS", frozenset((IDENTIFIER, "PAPER-other"))):
            with self.assertRaisesRegex(ValueError, "complete reviewed batch"):
                self.f.adopt()

    def test_authority_callback_substitution_rejected(self):
        def malicious(pin, label):
            result = self.f.read(pin, label)
            if pin["path"] == selector.AUTHORITY_PATH: result["scope_policy_sha256"] = "0" * 64
            return result
        with self.assertRaisesRegex(ValueError, "parsed identity"):
            selector.authenticate_authority(self.f.authority_identity["pin"], self.f.previous, [self.f.row], malicious)

    def test_selected_callback_substitution_rejected(self):
        self.f.adopt()
        def malicious(pin, label):
            result = self.f.read(pin, label)
            if pin["path"].endswith("access-conditions.v1.json"): result["injected"] = True
            return result
        with self.assertRaisesRegex(ValueError, "parsed identity"):
            binding.context(self.f.row, self.f.task, self.f.previous, malicious)

    def test_post_authentication_mutation_rejected(self):
        authority = self.f.adopt()
        with self.assertRaises(AttributeError): authority._payload = b"{}"
        altered = authority.entry(IDENTIFIER); altered["scope"]["primary_scope"] = "changed"
        self.assertEqual(authority.entry(IDENTIFIER)["scope"]["primary_scope"], self.f.scope)
        object.__setattr__(authority, "_payload", b"{}")
        with self.assertRaisesRegex(ValueError, "accepted canonical"):
            authority.entry(IDENTIFIER)

    def test_packaged_predecessor_cannot_alias_current(self):
        self.f.entry["predecessor_task"]["route"] = "packaged_file"
        self.f.refresh(); self.allow_fixture()
        with self.assertRaisesRegex(ValueError, "Unexpected endpoint member path"):
            self.f.adopt()

    def test_unsupported_reproduction_filename_rejected(self):
        self.f.row["paper_outcomes"]["reproduction_contract"]["path"] = self.f.endpoint + "reproduction.v3.json"
        with self.assertRaisesRegex(ValueError, "versioned filename"):
            selector.has_endpoint_selection(self.f.row)

    def test_schema_filename_mismatch_rejected(self):
        self.f.reproduction["schema_version"] = "paper-reproduction/v2"
        self.f.refresh(); self.allow_fixture()
        with self.assertRaisesRegex(ValueError, "filename and schema"):
            self.context()

    def test_outcome_task_and_contract_digest_mismatches_rejected(self):
        for field in ("task", "contract"):
            f = Fixture()
            outcomes = f.read(f.entry["selected_documents"]["outcomes"]["pin"], "fixture")
            if field == "task": outcomes["original_task_sha256"] = "c" * 64
            else: outcomes["contracts"]["improvement"] = "c" * 64
            f.entry["selected_documents"]["outcomes"] = f.put(f.endpoint + "outcomes.v1.json", outcomes)
            f.row["paper_outcomes"]["outcomes"] = f.entry["selected_documents"]["outcomes"]["pin"]
            f.authority_identity = f.put(selector.AUTHORITY_PATH, f.authority)
            self.f = f; self.allow_fixture()
            with self.subTest(field=field), self.assertRaises(ValueError): self.context()

    def test_evaluator_label_leakage_rejected(self):
        self.f.entry["access_policy"]["paper_data"].append("test-answers")
        self.f.refresh(); self.allow_fixture()
        with self.assertRaisesRegex(ValueError, "exactly the reviewed author-code difference"):
            self.f.adopt()

    def test_runtime_claim_rejected(self):
        self.f.task["evaluation"]["binary_reward_registered"] = True
        self.f.refresh(); self.allow_fixture()
        with self.assertRaisesRegex(ValueError, "runtime registration"):
            self.context()

    def test_unqualified_source_contract_cannot_become_run_result(self):
        self.f.improvement["disposition"] = "design_ready"
        for key in ("target", "metric"):
            self.f.improvement["same_task"][key]["status"] = "verified"
        self.f.refresh(); self.allow_fixture()
        with self.assertRaisesRegex(ValueError, "cannot promote"):
            self.context()


if __name__ == "__main__":
    unittest.main(verbosity=2)
