"""Generated metadata controls only; all papers/values/hashes below are invented."""

import copy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from neurobench import paper_reproduction as paper

SPEC = importlib.util.spec_from_file_location("improvement_fixture", Path(__file__).with_name("test_paper_improvement.py"))
legacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(legacy)


def fixture():
    """One synthetic task with two findings and independent outcome policies."""
    improvement, improvement_result = legacy.fixture()
    deterministic = {"kind": "deterministic", "method": "fixture exact category",
                     "independent_unit": "not_applicable", "minimum_independent_units": None,
                     "confidence_level": None, "statistic": None, "operator": None, "threshold": None,
                     "rationale": "Generated deterministic software-control finding, not a scientific observation.",
                     "evidence_ids": ["paper"]}
    identity = {key: str(index) * 64 for index, key in enumerate(paper.IDENTITIES)}
    computation = {
        "status": "specified", "rationale": "Invented source-native derived outputs for software controls only.",
        "analysis_interface_sha256": "a" * 64, "authentic_data_manifest_sha256": "b" * 64,
        "verification_program_sha256": "c" * 64, "evidence_ids": ["paper", "code"],
        "required_outputs": [{"id": "source-derived", "kind": "source_grounded_derived",
                              "description": "Synthetic observation-level contrasts and coefficients, not copied printed aggregates.",
                              "identity_sha256": "a" * 64, "finding_ids": ["primary", "companion"], "evidence_ids": ["paper"]}],
    }
    reproduction = {
        "schema_version": "paper-reproduction/v1", "task_id": improvement["task_id"],
        "objective": "recreate_original_findings_same_task", "eligibility": "eligible",
        "eligibility_reason": "Fully synthetic endpoint contract for unit tests only.",
        "source_paper": copy.deepcopy(improvement["source_paper"]),
        "evidence": copy.deepcopy(improvement["evidence"]),
        "same_task": copy.deepcopy(improvement["same_task"]),
        "findings": [{
            "id": "primary", "kind": "scalar", "description": "Invented original numerical finding",
            "status": "verified", "expected": 80.0, "units": "fixture_points",
            "aggregation": "original fixture aggregation", "evidence_ids": ["paper"], "categories": [],
            "tolerance": {"status": "justified", "absolute": 0.5,
                          "rationale": "Arbitrary fixture bound, never a default or empirical tolerance.", "evidence_ids": ["paper"]},
            "uncertainty": {"kind": "interval_containment", "method": "fixture interval",
                            "independent_unit": "subject", "minimum_independent_units": 4, "confidence_level": 0.9,
                            "statistic": None, "operator": None, "threshold": None,
                            "rationale": "Synthetic equivalence interval must lie wholly within tolerance.", "evidence_ids": ["paper"]},
        }, {
            "id": "companion", "kind": "categorical", "description": "Invented required scientific companion",
            "status": "verified", "expected": "positive", "units": "category", "aggregation": "original contrast",
            "evidence_ids": ["paper"], "categories": ["positive", "negative", "absent"],
            "tolerance": {"status": "not_applicable", "absolute": None,
                          "rationale": "Exact category match with the frozen source statement.", "evidence_ids": []},
            "uncertainty": deterministic,
        }],
        "panel_rule": "all_declared_findings_and_companions", "blocking_issues": [],
        "admission_policy": {"evaluator": {"id": "fixture-reproduction-evaluator", "sha256": "e" * 64,
                                            "evidence_ids": ["code"]}, "evaluation_identity": identity, "computation": computation},
    }
    for key in ("full_panel", "permitted_observations"):
        reproduction["same_task"][key] = {"status": "verified", "description": "Original fixture " + key, "evidence_ids": ["paper"]}
    outcomes = {
        "schema_version": "paper-outcomes/v1", "task_id": improvement["task_id"],
        "original_task_sha256": "0" * 64,
        "contracts": {"reproduction": paper.contract_digest(reproduction), "improvement": paper.contract_digest(improvement)},
        "pairing": {},
    }
    for outcome, contract in (("reproduction", reproduction), ("improvement", improvement)):
        outcomes["pairing"][outcome] = {
            "status": "specified", "rationale": "Matched generated test conditions, not a real delivery package.",
            "protocol": {"pair_id": "fixture-" + outcome, "common_input_manifest_sha256": "6" * 64,
                         "author_code_manifest_sha256": "8" * 64, "evaluation_identity": copy.deepcopy(identity),
                         "evaluator": {key: contract["admission_policy"]["evaluator"][key] for key in ("id", "sha256")},
                         "exposure_policy_sha256": "7" * 64, "author_code_is_only_information_difference": True,
                         "budgets": copy.deepcopy(improvement["admission_policy"]["budgets"]),
                         "computation": copy.deepcopy(computation)},
        }
    result = {
        "schema_version": "paper-reproduction-result/v1", "task_id": reproduction["task_id"],
        "claim": "same_task_original_findings_reproduction", "phase": "final",
        "contract_digest": paper.contract_digest(reproduction), "candidate_sha256": "c" * 64,
        "same_task": copy.deepcopy(reproduction["same_task"]), "source_evidence_ids": ["paper", "code"],
        "findings": [
            {"id": "primary", "value": 80.0, "units": "fixture_points", "aggregation": "original fixture aggregation",
             "uncertainty": {"method": "fixture interval", "independent_unit": "subject", "n_independent_units": 8,
                             "confidence_level": 0.9, "interval": [79.9, 80.1], "statistic": None, "value": None}},
            {"id": "companion", "value": "positive", "units": "category", "aggregation": "original contrast",
             "uncertainty": {"method": "fixture exact category", "independent_unit": "not_applicable",
                             "n_independent_units": 0, "confidence_level": None, "interval": None, "statistic": None, "value": None}},
        ],
    }
    return reproduction, improvement, outcomes, result, improvement_result


def receipt_for(outcomes, result, outcome="reproduction", condition="paper_data"):
    protocol = outcomes["pairing"][outcome]["protocol"]
    code = condition == "paper_data_author_code"
    trace, exposure, evaluation, freeze = ("3", "4", "5", "9") if code else ("1", "2", "d", "f")
    receipt = {
        "schema_version": "paper-outcome-receipt/v1", "task_id": outcomes["task_id"],
        "outcome": outcome, "condition": condition, "outcomes_digest": paper.contract_digest(outcomes),
        "original_task_sha256": outcomes["original_task_sha256"], "pair_id": protocol["pair_id"],
        "run_id": "fixture-" + condition, "actor_role": "ai_solver",
        "ai_run": {"started_at": "2026-11-16T08:00:00Z", "trace_sha256": trace * 64, "evidence_ids": ["ai"]},
        "delivery": {"common_input_manifest_sha256": protocol["common_input_manifest_sha256"],
                     "author_code_manifest_sha256": protocol["author_code_manifest_sha256"] if code else None,
                     "exposure_policy_sha256": protocol["exposure_policy_sha256"],
                     "exposure_manifest_sha256": exposure * 64, "evidence_ids": ["exposure"]},
        "candidate_sha256": result["candidate_sha256"],
        "freeze": {"frozen_at": "2026-11-16T09:00:00Z", "candidate_sha256": result["candidate_sha256"],
                   "outcomes_digest": paper.contract_digest(outcomes), "evidence_ids": ["freeze"]},
        "evaluation": {"started_at": "2026-11-16T10:00:00Z", "finished_at": "2026-11-16T11:00:00Z",
                       "evaluator_id": protocol["evaluator"]["id"], "evaluator_sha256": protocol["evaluator"]["sha256"],
                       "evaluation_identity": copy.deepcopy(protocol["evaluation_identity"]),
                       "candidate_sha256": result["candidate_sha256"], "result_digest": paper.contract_digest(result),
                       "evidence_ids": ["evaluation"]},
        "analysis_execution": {
            "execution_id": "fixture-execution-" + condition, "executor_role": "independent_operator",
            "candidate_sha256": result["candidate_sha256"], "entrypoint": "fixture-program --inputs manifest.json --outputs results",
            "analysis_interface_sha256": protocol["computation"]["analysis_interface_sha256"],
            "common_input_manifest_sha256": protocol["common_input_manifest_sha256"],
            "authentic_data_manifest_sha256": protocol["computation"]["authentic_data_manifest_sha256"],
            "author_code_manifest_sha256": protocol["author_code_manifest_sha256"] if code else None,
            "runtime_manifest_sha256": "a" * 64, "invocation_sha256": exposure * 64,
            "started_at": "2026-11-16T10:00:00Z", "finished_at": "2026-11-16T10:30:00Z",
            "output_manifest_sha256": "b" * 64, "evidence_ids": ["execution"],
        },
        "output_verification": {
            "verifier_role": "independent_operator", "verification_program_sha256": protocol["computation"]["verification_program_sha256"],
            "execution_id": "fixture-execution-" + condition, "output_manifest_sha256": "b" * 64,
            "result_digest": paper.contract_digest(result), "started_at": "2026-11-16T10:30:00Z",
            "finished_at": "2026-11-16T11:00:00Z", "evidence_ids": ["verification"],
            "outputs": [{"id": output["id"], "identity_sha256": output["identity_sha256"], "status": "verified"}
                        for output in protocol["computation"]["required_outputs"]],
        },
        "budget_usage": {"access": {"unit": "evaluation_access", "used": 10, "scope": "cumulative_episode", "evidence_ids": ["budget"]},
                         "resource": {"unit": "cpu_hour", "used": 19.5, "scope": "cumulative_episode", "evidence_ids": ["budget"]}},
        "evidence": [{"id": identifier, "kind": kind, "sha256": char * 64, "locator": "urn:fixture:" + identifier}
                     for identifier, kind, char in (("ai", "ai_run", trace), ("exposure", "exposure", exposure),
                                                    ("candidate", "candidate", "c"), ("freeze", "freeze", freeze),
                                                    ("evaluation", "evaluation", evaluation), ("budget", "budget", "a"),
                                                    ("execution", "analysis_execution", evaluation),
                                                    ("verification", "output_verification", freeze))],
        "result": copy.deepcopy(result),
    }
    return receipt


def refreeze(reproduction, improvement, outcomes, result):
    if "admission_policy" in reproduction:
        outcomes["pairing"]["reproduction"]["protocol"]["computation"] = copy.deepcopy(reproduction["admission_policy"]["computation"])
    outcomes["contracts"] = {"reproduction": paper.contract_digest(reproduction), "improvement": paper.contract_digest(improvement)}
    result["contract_digest"] = paper.contract_digest(reproduction)
    result["same_task"] = copy.deepcopy(reproduction["same_task"])


class ContractTests(unittest.TestCase):
    def test_valid_endpoint_and_bundle(self):
        reproduction, improvement, outcomes, _, _ = fixture()
        self.assertEqual(paper.contract_validate(reproduction), [])
        self.assertEqual(paper.outcomes_validate(outcomes, reproduction, improvement), [])
        self.assertTrue(paper.contract_validate(reproduction, "wrong-task"))

    def test_independent_eligibility_four_cells_one_task(self):
        reproduction, improvement, outcomes, result, _ = fixture()
        improvement["disposition"] = "ineligible"
        improvement["disposition_reason"] = "No justified superiority endpoint; reproduction remains possible."
        improvement["blocking_issues"] = ["No meaningful improvement direction for this source finding."]
        improvement.pop("admission_policy")
        outcomes["pairing"]["improvement"].update(status="unresolved", protocol=None)
        refreeze(reproduction, improvement, outcomes, result)
        report = paper.summary(outcomes, reproduction, improvement)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["task_count"], 1)
        self.assertEqual(len(report["cells"]), 4)
        self.assertEqual([cell["endpoint_eligible"] for cell in report["cells"]], [True, True, False, False])
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" and cell["receipt"] is None for cell in report["cells"]))
        self.assertEqual(report["paired_metadata_admitted"], {"reproduction": False, "improvement": False})

    def test_source_paper_and_all_original_anchor_splices_rejected(self):
        for key in ("source_paper", *paper.improvement.ANCHORS):
            reproduction, improvement, outcomes, result, _ = fixture()
            if key == "source_paper":
                improvement[key]["url"] = "https://example.org/another-paper"
            else:
                improvement["same_task"][key]["description"] += " changed original scientific identity"
            refreeze(reproduction, improvement, outcomes, result)
            with self.subTest(key=key):
                self.assertTrue(paper.outcomes_validate(outcomes, reproduction, improvement))

    def test_different_panel_hashes_cannot_splice_outcomes(self):
        reproduction, improvement, outcomes, _, _ = fixture()
        outcomes["pairing"]["improvement"]["protocol"]["evaluation_identity"]["cohort"] = "a" * 64
        self.assertTrue(paper.outcomes_validate(outcomes, reproduction, improvement))

    def test_no_default_tolerance_or_missing_uncertainty(self):
        for mutation in (
            lambda c: c["findings"][0]["tolerance"].update(status="unresolved", absolute=None),
            lambda c: c["findings"][0]["tolerance"].update(evidence_ids=[]),
            lambda c: c["findings"][0]["uncertainty"].update(kind="unresolved", confidence_level=None, minimum_independent_units=None),
            lambda c: c["same_task"]["full_panel"].update(status="unresolved"),
            lambda c: c["blocking_issues"].append("Original split not recovered"),
            lambda c: c.pop("admission_policy"),
        ):
            reproduction, _, _, _, _ = fixture()
            mutation(reproduction)
            self.assertTrue(paper.contract_validate(reproduction))

    def test_unresolved_source_has_unknown_targets(self):
        reproduction, _, _, _, _ = fixture()
        reproduction.update(eligibility="source_unresolved", blocking_issues=["Source numerical result is unavailable."])
        reproduction["findings"][0].update(status="unresolved", expected=None)
        reproduction["findings"][0]["tolerance"].update(status="unresolved", absolute=None)
        reproduction.pop("admission_policy")
        self.assertEqual(paper.contract_validate(reproduction), [])
        reproduction["findings"][0]["expected"] = 80
        self.assertTrue(paper.contract_validate(reproduction))

    def test_nonrejection_never_numeric_equivalence(self):
        reproduction, _, _, _, _ = fixture()
        reproduction["findings"][0]["uncertainty"].update(kind="threshold", confidence_level=None,
            statistic="p_value", operator=">=", threshold=0.05)
        errors = paper.contract_validate(reproduction)
        self.assertTrue(any("scalar equivalence" in error for error in errors))
        self.assertTrue(any("nonrejection" in error for error in errors))

    def test_published_aggregate_only_cannot_qualify_computational_reproduction(self):
        reproduction, _, _, _, _ = fixture()
        computation = reproduction["admission_policy"]["computation"]
        computation.update(status="published_aggregate_only", required_outputs=[])
        self.assertTrue(paper.contract_validate(reproduction))
        reproduction.update(eligibility="design_ready", blocking_issues=["Only copied published aggregates can currently be checked."])
        self.assertEqual(paper.contract_validate(reproduction), [])

    def test_claim_only_or_incomplete_computation_policy_cannot_be_specified(self):
        for mutation in (
            lambda p: p.update(required_outputs=[]),
            lambda p: p.update(authentic_data_manifest_sha256=None),
            lambda p: p.update(verification_program_sha256=None),
            lambda p: p["required_outputs"][0].update(kind="companion_control"),
            lambda p: p["required_outputs"][0].update(finding_ids=["primary"]),
            lambda p: p["required_outputs"][0].update(evidence_ids=[]),
        ):
            reproduction, _, _, _, _ = fixture()
            mutation(reproduction["admission_policy"]["computation"])
            self.assertTrue(paper.contract_validate(reproduction))

    def test_strict_json_schema_finiteness_and_duplicate_ids(self):
        for value in (True, float("nan"), float("inf"), 10 ** 400, "80"):
            reproduction, _, _, _, _ = fixture()
            reproduction["findings"][0]["expected"] = value
            self.assertTrue(paper.contract_validate(reproduction))
        reproduction, _, _, _, _ = fixture()
        reproduction["findings"].append(copy.deepcopy(reproduction["findings"][0]))
        self.assertTrue(paper.contract_validate(reproduction))
        with self.assertRaises(ValueError):
            paper.loads_contract('{"task_id":"a","task_id":"b"}')


class ReceiptTests(unittest.TestCase):
    def admit(self, mutation=None, result_mutation=None, condition="paper_data", outcome="reproduction"):
        reproduction, improvement, outcomes, result, improvement_result = fixture()
        chosen = result if outcome == "reproduction" else improvement_result
        if result_mutation:
            result_mutation(chosen)
        receipt = receipt_for(outcomes, chosen, outcome, condition)
        if mutation:
            mutation(receipt)
        return paper.admit_outcome(outcomes, reproduction, improvement, receipt)

    def test_declared_match_never_becomes_scientific_success(self):
        for condition in paper.CONDITIONS:
            response = self.admit(condition=condition)
            self.assertEqual(response["errors"], [])
            self.assertTrue(response["metadata_admitted"])
            self.assertTrue(response["criterion_satisfied"])
            self.assertEqual(response["scientific_outcome"], "unknown")

    def test_valid_mismatch_is_preserved_without_scientific_failure_claim(self):
        response = self.admit(result_mutation=lambda r: r["findings"][1].update(value="negative"))
        self.assertTrue(response["metadata_admitted"])
        self.assertFalse(response["criterion_satisfied"])
        self.assertFalse(response["finding_matches"]["companion"])
        self.assertEqual(response["scientific_outcome"], "unknown")

    def test_complete_panel_exact_categories_units_and_aggregation(self):
        mutations = (
            lambda r: r["findings"].pop(),
            lambda r: r["findings"].append(copy.deepcopy(r["findings"][0])),
            lambda r: r["findings"][0].update(id="post-hoc-selected"),
            lambda r: r["findings"][0].update(units="wrong-unit"),
            lambda r: r["findings"][0].update(aggregation="selected favorable subjects"),
            lambda r: r["findings"][1].update(value="sign-only-agreement"),
            lambda r: r["same_task"]["full_panel"].update(description="smaller panel"),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                response = self.admit(result_mutation=mutation)
                self.assertFalse(response["metadata_admitted"])
                self.assertIsNone(response["criterion_satisfied"])

    def test_exact_decimal_tolerance_and_interval_containment(self):
        reproduction, improvement, outcomes, result, _ = fixture()
        reproduction["findings"][0]["expected"] = 0.3
        reproduction["findings"][0]["tolerance"]["absolute"] = 0.1
        refreeze(reproduction, improvement, outcomes, result)
        result["findings"][0].update(value=0.3)
        result["findings"][0]["uncertainty"]["interval"] = [0.2, 0.4]
        response = paper.admit_outcome(outcomes, reproduction, improvement, receipt_for(outcomes, result))
        self.assertTrue(response["criterion_satisfied"])
        result["findings"][0]["uncertainty"]["interval"] = [0.2, 0.4000000000000001]
        response = paper.admit_outcome(outcomes, reproduction, improvement, receipt_for(outcomes, result))
        self.assertTrue(response["metadata_admitted"])
        self.assertFalse(response["criterion_satisfied"])

    def test_tiny_source_target_does_not_round_absolute_difference_into_tolerance(self):
        reproduction, improvement, outcomes, result, _ = fixture()
        reproduction["findings"][0]["expected"] = 1e-30
        reproduction["findings"][0]["tolerance"]["absolute"] = 1.0
        result["findings"][0].update(value=-1.0)
        result["findings"][0]["uncertainty"]["interval"] = [-1.0, -1.0]
        refreeze(reproduction, improvement, outcomes, result)
        response = paper.admit_outcome(outcomes, reproduction, improvement, receipt_for(outcomes, result))
        self.assertTrue(response["metadata_admitted"], response)
        self.assertFalse(response["criterion_satisfied"])

    def test_interval_overlap_is_insufficient_and_invalid_uncertainty_rejected(self):
        response = self.admit(result_mutation=lambda r: r["findings"][0]["uncertainty"].update(interval=[0, 100]))
        self.assertTrue(response["metadata_admitted"])
        self.assertFalse(response["criterion_satisfied"])
        for change in ({"interval": [81, 79]}, {"interval": [79, 79.5]}, {"n_independent_units": 1},
                       {"independent_unit": "dependent trial instead of subject"}, {"confidence_level": 0.5}):
            response = self.admit(result_mutation=lambda r: r["findings"][0]["uncertainty"].update(change))
            self.assertFalse(response["metadata_admitted"])

    def test_source_supported_categorical_inference_with_probability_boundary(self):
        reproduction, improvement, outcomes, result, _ = fixture()
        reproduction["findings"][1]["uncertainty"].update(kind="threshold", method="fixture direction test",
            independent_unit="subject", minimum_independent_units=4, statistic="p_value", operator="<", threshold=0.05)
        result["findings"][1]["uncertainty"].update(method="fixture direction test", independent_unit="subject",
            n_independent_units=8, statistic="p_value", value=0.049)
        refreeze(reproduction, improvement, outcomes, result)
        response = paper.admit_outcome(outcomes, reproduction, improvement, receipt_for(outcomes, result))
        self.assertTrue(response["criterion_satisfied"], response)
        result["findings"][1]["uncertainty"]["value"] = 0.05
        response = paper.admit_outcome(outcomes, reproduction, improvement, receipt_for(outcomes, result))
        self.assertTrue(response["metadata_admitted"])
        self.assertFalse(response["criterion_satisfied"])
        result["findings"][1]["uncertainty"]["value"] = -0.1
        self.assertFalse(paper.admit_outcome(outcomes, reproduction, improvement, receipt_for(outcomes, result))["metadata_admitted"])

    def test_calibration_software_and_history_do_not_supply_ai_results(self):
        for role in ("author_baseline_calibration", "software_control", "historical_attempt"):
            response = self.admit(mutation=lambda r: r.update(actor_role=role))
            self.assertFalse(response["metadata_admitted"])
            self.assertIsNone(response["criterion_satisfied"])

    def test_binding_provenance_exposure_freeze_and_budgets(self):
        mutations = (
            lambda r: r.update(outcomes_digest="a" * 64),
            lambda r: r.update(original_task_sha256="a" * 64),
            lambda r: r["evaluation"].update(result_digest="a" * 64),
            lambda r: r["evaluation"]["evaluation_identity"].update(split="a" * 64),
            lambda r: r["evaluation"].update(evaluator_sha256="a" * 64),
            lambda r: r["ai_run"].update(evidence_ids=["evaluation"]),
            lambda r: r["delivery"].update(exposure_manifest_sha256="a" * 64),
            lambda r: r["delivery"].update(common_input_manifest_sha256="a" * 64),
            lambda r: r["delivery"].update(author_code_manifest_sha256="8" * 64),
            lambda r: r["freeze"].update(frozen_at="2026-11-16T10:00:00Z"),
            lambda r: r["ai_run"].update(started_at="2026-11-16T09:30:00Z"),
            lambda r: r["budget_usage"]["access"].update(used=11),
            lambda r: r["budget_usage"]["resource"].update(unit="different unit"),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                response = self.admit(mutation=mutation)
                self.assertFalse(response["metadata_admitted"])
                self.assertIsNone(response["criterion_satisfied"])

    def test_code_condition_cannot_disguise_absent_code(self):
        response = self.admit(condition="paper_data_author_code", mutation=lambda r: r["delivery"].update(author_code_manifest_sha256=None))
        self.assertFalse(response["metadata_admitted"])

    def test_copied_claims_cannot_replace_independent_source_analysis(self):
        mutations = (
            lambda r: r.pop("analysis_execution"),
            lambda r: r.pop("output_verification"),
            lambda r: r["analysis_execution"].update(executor_role="ai_solver"),
            lambda r: r["output_verification"].update(verifier_role="ai_solver"),
            lambda r: r["analysis_execution"].update(candidate_sha256="a" * 64),
            lambda r: r["analysis_execution"].update(authentic_data_manifest_sha256="a" * 64),
            lambda r: r["analysis_execution"].update(author_code_manifest_sha256="8" * 64),
            lambda r: r["analysis_execution"].update(started_at="2026-11-16T08:00:00Z"),
            lambda r: r["output_verification"].update(output_manifest_sha256="a" * 64),
            lambda r: r["output_verification"].update(result_digest="a" * 64),
            lambda r: r["output_verification"].update(verification_program_sha256="a" * 64),
            lambda r: r["output_verification"]["outputs"].clear(),
            lambda r: r["output_verification"]["outputs"][0].update(status="unverified"),
            lambda r: r["output_verification"]["outputs"][0].update(identity_sha256="b" * 64),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                response = self.admit(mutation=mutation)
                self.assertFalse(response["metadata_admitted"])
                self.assertIsNone(response["criterion_satisfied"])

    def test_missing_code_leaves_paper_data_available(self):
        reproduction, improvement, outcomes, result, _ = fixture()
        outcomes["pairing"]["reproduction"]["protocol"]["author_code_manifest_sha256"] = None
        no_code = receipt_for(outcomes, result)
        plus_code = receipt_for(outcomes, result, condition="paper_data_author_code")
        self.assertTrue(paper.admit_outcome(outcomes, reproduction, improvement, no_code)["metadata_admitted"])
        self.assertFalse(paper.admit_outcome(outcomes, reproduction, improvement, plus_code)["metadata_admitted"])
        report = paper.summary(outcomes, reproduction, improvement, [no_code])
        self.assertEqual([cell["condition_available"] for cell in report["cells"][:2]], [True, False])
        self.assertFalse(report["paired_metadata_admitted"]["reproduction"])

    def test_improvement_reuses_unchanged_comparison(self):
        response = self.admit(outcome="improvement")
        self.assertTrue(response["metadata_admitted"], response)
        self.assertTrue(response["criterion_satisfied"])
        self.assertEqual(response["scientific_outcome"], "unknown")
        response = self.admit(outcome="improvement", mutation=lambda r: r["budget_usage"]["access"].update(used=9))
        self.assertFalse(response["metadata_admitted"])
        response = self.admit(outcome="improvement", mutation=lambda r: r["evidence"][3].update(sha256="a" * 64))
        self.assertFalse(response["metadata_admitted"])

    def test_wrong_result_outcome_and_nonfinal_result_rejected(self):
        self.assertFalse(self.admit(result_mutation=lambda r: r.update(phase="validation"))["metadata_admitted"])
        reproduction, improvement, outcomes, _, result = fixture()
        receipt = receipt_for(outcomes, result)
        self.assertFalse(paper.admit_outcome(outcomes, reproduction, improvement, receipt)["metadata_admitted"])


class PairTests(unittest.TestCase):
    def test_independent_runs_may_recreate_identical_candidate_artifacts(self):
        reproduction, improvement, outcomes, result, _ = fixture()
        receipts = [receipt_for(outcomes, result, condition=condition) for condition in paper.CONDITIONS]
        self.assertEqual(receipts[0]["candidate_sha256"], receipts[1]["candidate_sha256"])
        receipts[1]["analysis_execution"]["invocation_sha256"] = receipts[0]["analysis_execution"]["invocation_sha256"]
        report = paper.summary(outcomes, reproduction, improvement, receipts)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["paired_metadata_admitted"]["reproduction"])
        self.assertEqual(report["task_count"], 1)
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in report["cells"]))

    def test_duplicate_cell_and_condition_provenance_reuse_rejected(self):
        for field in ("run_id", "trace", "exposure", "evaluation", "freeze", "duplicate-cell"):
            reproduction, improvement, outcomes, result, _ = fixture()
            one = receipt_for(outcomes, result)
            two = receipt_for(outcomes, result, condition="paper_data_author_code")
            if field == "run_id":
                two["run_id"] = one["run_id"]
            elif field == "trace":
                two["ai_run"]["trace_sha256"] = one["ai_run"]["trace_sha256"]
                two["evidence"][0]["sha256"] = one["evidence"][0]["sha256"]
            elif field == "exposure":
                two["delivery"]["exposure_manifest_sha256"] = one["delivery"]["exposure_manifest_sha256"]
                two["evidence"][1]["sha256"] = one["evidence"][1]["sha256"]
            elif field in ("evaluation", "freeze"):
                for item in two["evidence"]:
                    if item["kind"] == field:
                        item["sha256"] = next(i["sha256"] for i in one["evidence"] if i["kind"] == field)
            else:
                two = copy.deepcopy(one)
            with self.subTest(field=field):
                report = paper.summary(outcomes, reproduction, improvement, [one, two])
                self.assertTrue(report["errors"])
                self.assertFalse(report["paired_metadata_admitted"]["reproduction"])
                self.assertTrue(all(cell["receipt"] is None or cell["receipt"]["criterion_satisfied"] is None for cell in report["cells"]))

    def test_invalid_metadata_does_not_crash_or_claim_failure(self):
        reproduction, improvement, outcomes, _, _ = fixture()
        for invalid in (None, [], {"schema_version": "paper-outcome-receipt/v1"}):
            report = paper.summary(outcomes, reproduction, improvement, [invalid])
            self.assertTrue(report["errors"])
            self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in report["cells"]))
        self.assertTrue(paper.summary(None, reproduction, improvement)["errors"])


if __name__ == "__main__":
    unittest.main()
