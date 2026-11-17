"""Synthetic contract/admission tests; no scientific artifacts or models read."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("paper_improvement_tests", ROOT / "src/neurobench/paper_improvement.py")
paper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(paper)


def fixture():
    """Invented scores, subjects, sources and hashes solely for admission tests."""
    contract = {
        "schema_version": "paper-improvement/v1", "task_id": "PAPER-TEST-001",
        "objective": "surpass_source_paper_same_task", "disposition": "improvement_ready",
        "disposition_reason": "Synthetic source identity and execution evidence for this unit test.",
        "source_paper": {"title": "Invented fixture paper", "url": "https://example.org/fixture"},
        "evidence": [
            {"id": "paper", "kind": "paper", "url": "https://example.org/fixture", "locator": "Table 1, test cohort row",
             "supports": ["Published score and original task identity", "Predeclared effect and uncertainty justification"]},
            {"id": "code", "kind": "author_code", "url": "https://example.org/fixture-code", "locator": "release 1, evaluate.py",
             "supports": "Author evaluator and reproduction route"},
        ],
        "same_task": {key: {"status": "verified", "description": "Original fixture " + key, "evidence_ids": ["paper"]} for key in paper.ANCHORS},
        "comparison": {
            "primary_metric": "mean fixture score", "direction": "higher",
            "published_baseline": {"status": "verified", "value": 80.0, "description": "Original Table 1 score", "evidence_ids": ["paper"]},
            "reproduced_author_baseline": {"status": "verified", "value": 79.9, "description": "Author recipe calibration", "evidence_ids": ["code"]},
            "minimum_effect": {"status": "justified", "value": 2.0, "rationale": "Fixture-specific meaningful point difference", "evidence_ids": ["paper"]},
            "uncertainty": {"status": "specified", "method": "paired subject interval", "independent_unit": "subject",
                            "rationale": "Subjects, rather than dependent trials, define replication", "evidence_ids": ["paper"]},
            "paper_win_requires": ["Final score improves the original published score by at least two points with the declared interval."],
            "current_sota": {"status": "not_claimed", "description": "No current SOTA survey", "evidence_ids": []},
        },
        "episode": {"improvement_loop": "Use only training and validation feedback to iterate.",
                    "candidate_freeze": "Freeze candidate hash and contract before final evaluation.",
                    "final_evaluation": "Run the bound evaluator once on the original protected split.",
                    "access_budget": "Ten cumulative evaluation accesses.", "resource_budget": "Twenty cumulative CPU hours.",
                    "baseline_policy": "Calibrate with the original author method; victory requires the published score."},
        "blocking_issues": [],
        "legacy": {"role": "calibration_only", "original_task": "historical/task.pre-improvement.v1.json", "notes": "Historical reproduction retained."},
        "admission_policy": {
            "evaluator": {"id": "original-evaluator-v1", "sha256": "e" * 64, "status": "verified", "evidence_ids": ["code"]},
            "author_baseline": {"route": "reproduced_author", "description": "Original author recipe", "tolerance": 0.5, "evidence_ids": ["code"]},
            "comparator": "both_published_and_reproduced_author",
            "metric_domain": {"minimum": 0.0, "maximum": 100.0, "rationale": "Fixture score is a percentage bounded by zero and one hundred.", "evidence_ids": ["paper"]},
            "effect_operator": ">=",
            "requirement_checks": [{"requirement": "Final score improves the original published score by at least two points with the declared interval.",
                                    "checks": ["same_task", "published_effect", "reproduced_author_effect", "uncertainty", "candidate_freeze", "final_evaluation", "budgets", "provenance"]}],
            "uncertainty_rule": {"statistic": "effect_lower_bound", "operator": ">", "threshold": 0.0,
                                 "method": "paired subject interval", "independent_unit": "subject", "minimum_independent_units": 4,
                                 "confidence_level": 0.9, "null_effect": 0.0, "alternative": "directional_improvement", "evidence_ids": ["paper"],
                                 "comparison_target": "stronger_of_published_and_reproduced_author"},
            "budgets": {"access": {"unit": "evaluation_access", "limit": 10, "scope": "cumulative_episode"},
                        "resource": {"unit": "cpu_hour", "limit": 20, "scope": "cumulative_episode"}},
        },
    }
    result = {
        "schema_version": "paper-improvement-result/v1", "task_id": contract["task_id"], "claim": "same_task_paper_improvement",
        "phase": "final", "contract_digest": paper.contract_digest(contract), "candidate_sha256": "c" * 64,
        "same_task": copy.deepcopy(contract["same_task"]), "source_evidence_ids": ["paper", "code"],
        "freeze": {"contract_digest": paper.contract_digest(contract), "candidate_sha256": "c" * 64,
                   "frozen_at": "2026-11-16T09:00:00Z", "evidence_ids": ["freeze"]},
        "evaluation": {"evaluator_id": "original-evaluator-v1", "evaluator_sha256": "e" * 64,
                       "contract_digest": paper.contract_digest(contract), "candidate_sha256": "c" * 64,
                       "started_at": "2026-11-16T10:00:00Z", "evidence_ids": ["evaluation"]},
        "measurement": {"primary_metric": "mean fixture score", "direction": "higher", "candidate_value": 83.0,
                        "comparator_kind": "published_source_paper", "published_value": 80.0},
        "reproduced_author_baseline": {"value": 79.9, "same_task": copy.deepcopy(contract["same_task"]), "evidence_ids": ["baseline"]},
        "uncertainty": {"statistic": "effect_lower_bound", "value": 1.5, "method": "paired subject interval",
                        "independent_unit": "subject", "n_independent_units": 8, "confidence_level": 0.9,
                        "null_effect": 0.0, "alternative": "directional_improvement", "interval": [1.5, 4.5], "evidence_ids": ["evaluation"]},
        "budget_usage": {"access": {"unit": "evaluation_access", "used": 10, "scope": "cumulative_episode", "evidence_ids": ["budget"]},
                         "resource": {"unit": "cpu_hour", "used": 19.5, "scope": "cumulative_episode", "evidence_ids": ["budget"]}},
        "evidence": [{"id": identifier, "kind": kind, "sha256": char * 64, "locator": "urn:fixture:" + identifier}
                     for identifier, kind, char in (("candidate", "candidate", "c"), ("freeze", "freeze", "f"),
                                                     ("evaluation", "evaluation", "d"), ("baseline", "reproduced_baseline", "b"), ("budget", "budget", "a"))],
    }
    result["uncertainty"].update(comparison_target="stronger_of_published_and_reproduced_author", published_value=80.0,
                                 reproduced_value=79.9, comparator_value=80.0, candidate_sha256="c" * 64,
                                 contract_digest=paper.contract_digest(contract))
    return contract, result


def refreeze(contract, result):
    digest = paper.contract_digest(contract)
    for record in (result, result["freeze"], result["evaluation"], result["uncertainty"]):
        record["contract_digest"] = digest


class ContractTests(unittest.TestCase):
    def test_schema_artifact_matches_runtime(self):
        schema = json.loads((ROOT / "docs/science/paper-improvement/contract.schema.json").read_text())
        self.assertEqual(schema, paper.CONTRACT_SCHEMA)
        self.assertEqual(schema["$defs"]["admission_result"], paper.RESULT_SCHEMA)

    def test_ready_fixture_and_aliases(self):
        contract, _ = fixture()
        self.assertEqual(paper.contract_validate(contract, "PAPER-TEST-001"), [])
        self.assertEqual(paper.validate_contract(contract, expected_task_id="PAPER-TEST-001"), [])
        self.assertTrue(paper.contract_validate(contract, "PAPER-WRONG"))
        self.assertTrue(paper.validate_contract(contract, "a", expected_task_id="b"))
        summary = paper.contract_summary(contract)
        self.assertTrue(summary["improvement_ready"])
        self.assertFalse(summary["paper_win"])
        self.assertEqual(summary["current_sota"], "not_assessed")

    def test_common_guide_contract_does_not_need_execution_policy_when_nonready(self):
        for disposition in ("design_ready", "source_unresolved", "ineligible"):
            contract, _ = fixture()
            contract["disposition"] = disposition
            contract.pop("admission_policy")
            contract["blocking_issues"] = ["Evaluator and final execution are incomplete."]
            contract["comparison"]["published_baseline"]["value"] = None
            with self.subTest(disposition=disposition):
                self.assertEqual(paper.contract_validate(contract), [])
                self.assertFalse(paper.summary(contract)["improvement_ready"])

    def test_ready_rejects_missing_policy_or_unresolved_execution_conditions(self):
        mutations = [
            lambda c: c.pop("admission_policy"),
            lambda c: c["blocking_issues"].append("Final evaluator missing"),
            lambda c: c["same_task"]["split"].update(status="unresolved"),
            lambda c: c["comparison"].update(direction="unresolved"),
            lambda c: c["comparison"]["published_baseline"].update(value=None),
            lambda c: c["comparison"]["minimum_effect"].update(value=0),
            lambda c: c["comparison"]["uncertainty"].update(status="unresolved"),
            lambda c: c["episode"].update(resource_budget=None),
            lambda c: c["comparison"]["reproduced_author_baseline"].update(status="unresolved", value=None),
        ]
        for index, mutation in enumerate(mutations):
            contract, _ = fixture()
            mutation(contract)
            with self.subTest(index=index):
                self.assertTrue(paper.contract_validate(contract))
                self.assertFalse(paper.summary(contract)["improvement_ready"])

    def test_source_authorized_route_can_be_ready_before_reproduction_but_final_must_reproduce(self):
        contract, result = fixture()
        contract["comparison"]["reproduced_author_baseline"].update(status="unresolved", value=None)
        contract["admission_policy"]["author_baseline"]["route"] = "source_authorized_route"
        refreeze(contract, result)
        self.assertEqual(paper.contract_validate(contract), [])
        self.assertTrue(paper.compare(contract, result)["comparison_admitted"])
        result["reproduced_author_baseline"]["value"] = 77
        self.assertFalse(paper.compare(contract, result)["comparison_admitted"])

    def test_tiny_source_baseline_does_not_round_inside_tolerance(self):
        # abs(Decimal) obeys the ambient precision and would round 1+1e-30
        # down to 1. The declared absolute distance must remain exact.
        for target, valid in ((0.0, True), (1e-30, False)):
            contract, _ = fixture()
            contract["comparison"]["published_baseline"]["value"] = target
            contract["comparison"]["reproduced_author_baseline"]["value"] = -1.0
            contract["admission_policy"]["author_baseline"]["tolerance"] = 1.0
            contract["admission_policy"]["metric_domain"]["minimum"] = None
            with self.subTest(target=target):
                errors = paper.contract_validate(contract)
                self.assertEqual(not errors, valid, errors)
                if not valid:
                    self.assertTrue(any("exceeds predeclared reproduction tolerance" in error for error in errors))

    def test_missing_or_registration_only_primary_evidence_rejected(self):
        for mutation in (
            lambda c: c["same_task"]["split"].update(evidence_ids=[]),
            lambda c: c["evidence"][0].update(kind="registration"),
            lambda c: c["same_task"]["cohort"].update(evidence_ids=["missing"]),
            lambda c: c["comparison"]["published_baseline"].update(evidence_ids=[]),
            lambda c: c["admission_policy"]["evaluator"].update(evidence_ids=["missing"]),
        ):
            contract, _ = fixture()
            mutation(contract)
            self.assertTrue(paper.contract_validate(contract))

    def test_duplicate_evidence_ids_and_refs_rejected(self):
        contract, _ = fixture()
        contract["evidence"].append(copy.deepcopy(contract["evidence"][0]))
        self.assertTrue(any("duplicate evidence id" in error for error in paper.contract_validate(contract)))
        contract, _ = fixture()
        contract["same_task"]["target"]["evidence_ids"] = ["paper", "paper"]
        self.assertTrue(paper.contract_validate(contract))

    def test_not_applicable_anchor_requires_primary_rationale(self):
        contract, _ = fixture()
        contract["same_task"]["preprocessing"].update(status="not_applicable", description="No preprocessing in original protocol")
        self.assertEqual(paper.contract_validate(contract), [])
        contract["same_task"]["preprocessing"]["evidence_ids"] = []
        self.assertTrue(paper.contract_validate(contract))

    def test_ready_and_design_require_defined_target_and_metric(self):
        for disposition in ("design_ready", "improvement_ready"):
            for key in ("target", "metric"):
                for status in ("unresolved", "not_applicable"):
                    contract, _ = fixture()
                    contract["disposition"] = disposition
                    contract["same_task"][key]["status"] = status
                    self.assertTrue(paper.contract_validate(contract))

    def test_source_url_null_is_explicitly_unresolved(self):
        contract, _ = fixture()
        contract["source_paper"]["url"] = None
        self.assertTrue(paper.contract_validate(contract))
        contract.update(disposition="source_unresolved", blocking_issues=["Source paper not recoverable"])
        self.assertEqual(paper.contract_validate(contract), [])

    def test_strict_shapes_and_finite_numeric_types(self):
        for bad in (True, False, float("nan"), float("inf"), -float("inf"), 10 ** 400, "80"):
            contract, _ = fixture()
            contract["comparison"]["published_baseline"]["value"] = bad
            with self.subTest(bad=bad):
                self.assertTrue(paper.contract_validate(contract))
        for bad in (None, [], True, {}, {"task_id": "a"}):
            self.assertTrue(paper.contract_validate(bad))
            self.assertFalse(paper.summary(bad)["improvement_ready"])
        contract, _ = fixture()
        contract["comparison"]["unknown"] = "silently ignored risk"
        self.assertTrue(paper.contract_validate(contract))
        contract, _ = fixture()
        contract["evidence"][0]["locator"] = " \n\t"
        self.assertTrue(paper.contract_validate(contract))

    def test_strict_json_parser_rejects_duplicate_keys_and_overflow(self):
        for raw in ('{"x":1,"x":2}', '{"nested":{"x":1,"x":2}}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e10000}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                paper.loads_contract(raw)
        contract, _ = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract))
            self.assertEqual(paper.load_contract(path), contract)

    def test_digest_is_order_independent_and_content_sensitive(self):
        contract, _ = fixture()
        reordered = dict(reversed(list(contract.items())))
        self.assertEqual(paper.contract_digest(contract), paper.contract_digest(reordered))
        changed = copy.deepcopy(contract)
        changed["same_task"]["split"]["description"] = "new split"
        self.assertNotEqual(paper.contract_digest(contract), paper.contract_digest(changed))
        with self.assertRaises(ValueError):
            paper.contract_digest({"value": float("nan")})


class ComparisonTests(unittest.TestCase):
    def rejected(self, contract, result, message=None):
        decision = paper.compare(contract, result)
        self.assertFalse(decision["paper_win"], decision)
        self.assertFalse(decision["comparison_admitted"], decision)
        self.assertEqual(decision["status"], "rejected")
        self.assertTrue(decision["errors"])
        if message:
            self.assertTrue(any(message in error for error in decision["errors"]), decision)
        return decision

    def test_final_meaningful_uncertain_improvement_admitted_conditionally(self):
        contract, result = fixture()
        decision = paper.admit_comparison(contract, result)
        self.assertTrue(decision["comparison_admitted"], decision)
        self.assertIsNone(decision["paper_win"])
        self.assertEqual(decision["paper_win_verification"], "unverified")
        self.assertEqual(decision["published_improvement"], 3)
        self.assertEqual(decision["current_sota"], "not_assessed")
        self.assertIn("not independently authenticated", decision["assurance"])
        self.assertEqual(decision["status"], "admitted_on_declared_evidence")

    def test_each_original_anchor_and_reproduced_anchor_is_exact(self):
        for key in paper.ANCHORS:
            for owner in ("candidate", "baseline"):
                contract, result = fixture()
                anchors = result["same_task"] if owner == "candidate" else result["reproduced_author_baseline"]["same_task"]
                anchors[key]["description"] += " changed/subset/new condition"
                with self.subTest(key=key, owner=owner):
                    self.rejected(contract, result, f"same_task.{key}")

    def test_nonready_validation_reproduction_extension_and_local_claims_never_win(self):
        for disposition in ("design_ready", "source_unresolved", "ineligible"):
            contract, result = fixture()
            contract["disposition"] = disposition
            refreeze(contract, result)
            self.rejected(contract, result, "disposition")
        contract, result = fixture()
        result["phase"] = "validation"
        self.rejected(contract, result, "validation")
        for claim in ("prospective_extension", "reproduction_only", "candidate_vs_local_baseline"):
            contract, result = fixture()
            result["claim"] = claim
            self.rejected(contract, result, "claims cannot paper-win")

    def test_published_baseline_cannot_be_replaced_with_weaker_local_score(self):
        contract, result = fixture()
        result["measurement"].update(candidate_value=79.95, published_value=79.9)
        decision = self.rejected(contract, result, "published_value")
        self.assertGreater(decision["reproduced_improvement"], 0)
        self.assertLess(decision["published_improvement"], 0)
        contract, result = fixture()
        result["measurement"]["comparator_kind"] = "reproduced_author"
        self.rejected(contract, result, "comparator_kind")

    def test_higher_and_lower_direction_and_effect_threshold(self):
        for direction, candidate, win in (("higher", 82, True), ("higher", 81.99, False), ("higher", 80, False),
                                          ("lower", 78, True), ("lower", 78.01, False), ("lower", 83, False)):
            contract, result = fixture()
            contract["comparison"]["direction"] = direction
            contract["comparison"]["reproduced_author_baseline"]["value"] = 80
            result["measurement"].update(direction=direction, candidate_value=candidate)
            result["reproduced_author_baseline"]["value"] = 80
            result["uncertainty"].update(reproduced_value=80, comparator_value=80)
            refreeze(contract, result)
            with self.subTest(direction=direction, candidate=candidate):
                self.assertEqual(paper.compare(contract, result)["comparison_admitted"], win)
        contract, result = fixture()
        result["measurement"]["direction"] = "lower"
        self.rejected(contract, result, "direction")
        contract, result = fixture()
        contract["admission_policy"]["effect_operator"] = ">"
        result["measurement"]["candidate_value"] = 82
        refreeze(contract, result)
        self.rejected(contract, result, "meaningful effect")

    def test_stronger_author_reproduction_cannot_be_ignored(self):
        contract, result = fixture()
        contract["comparison"]["reproduced_author_baseline"]["value"] = 80.5
        result["reproduced_author_baseline"]["value"] = 80.5
        result["measurement"]["candidate_value"] = 82.25
        result["uncertainty"].update(reproduced_value=80.5, comparator_value=80.5)
        refreeze(contract, result)
        self.rejected(contract, result, "reproduced author score")

    def test_metric_domain_rejects_impossible_scores(self):
        for location in ("candidate", "published", "reproduced"):
            contract, result = fixture()
            if location == "candidate":
                result["measurement"]["candidate_value"] = 110
            elif location == "published":
                contract["comparison"]["published_baseline"]["value"] = 110
            else:
                result["reproduced_author_baseline"]["value"] = -1
            self.rejected(contract, result, "metric domain")
        contract, result = fixture()
        contract["admission_policy"]["metric_domain"].update(minimum=100, maximum=0)
        self.rejected(contract, result, "minimum must be below")

    def test_decimal_strict_threshold_has_no_floating_point_false_win(self):
        contract, result = fixture()
        contract["comparison"]["published_baseline"]["value"] = 0.80
        contract["comparison"]["reproduced_author_baseline"]["value"] = 0.80
        contract["comparison"]["minimum_effect"]["value"] = 0.01
        contract["admission_policy"]["effect_operator"] = ">"
        result["measurement"].update(candidate_value=0.81, published_value=0.80)
        result["reproduced_author_baseline"]["value"] = 0.80
        result["uncertainty"].update(published_value=0.80, reproduced_value=0.80, comparator_value=0.80,
                                    value=0.001, interval=[0.001, 0.02])
        refreeze(contract, result)
        self.rejected(contract, result, "meaningful effect")
        contract["admission_policy"]["effect_operator"] = ">="
        refreeze(contract, result)
        self.assertTrue(paper.compare(contract, result)["comparison_admitted"])

    def test_published_and_pinned_baseline_tolerances_preserve_tiny_differences(self):
        for baseline in ("published", "pinned"):
            for offset, admitted in ((0.0, True), (1e-30, False)):
                contract, result = fixture()
                published = offset if baseline == "published" else 0.0
                pinned = None if baseline == "published" else offset
                contract["comparison"]["published_baseline"]["value"] = published
                contract["comparison"]["reproduced_author_baseline"].update(
                    status="unresolved" if pinned is None else "verified", value=pinned)
                contract["admission_policy"]["author_baseline"].update(route="source_authorized_route", tolerance=1.0)
                contract["admission_policy"]["metric_domain"]["minimum"] = None
                result["measurement"]["published_value"] = published
                result["reproduced_author_baseline"]["value"] = -1.0
                result["uncertainty"].update(published_value=published, reproduced_value=-1.0, comparator_value=published)
                refreeze(contract, result)
                with self.subTest(baseline=baseline, offset=offset):
                    self.assertEqual(paper.contract_validate(contract), [])
                    decision = paper.compare(contract, result)
                    self.assertEqual(decision["comparison_admitted"], admitted, decision)
                    if not admitted:
                        reason = "outside declared tolerance" if baseline == "published" else "frozen reproduced baseline beyond tolerance"
                        self.assertTrue(any(reason in error for error in decision["errors"]), decision)

    def test_extra_prose_requirement_needs_supported_machine_binding(self):
        contract, result = fixture()
        contract["comparison"]["paper_win_requires"].append("Protected subgroup noninferiority must hold.")
        refreeze(contract, result)
        self.rejected(contract, result, "every prose requirement")
        contract["admission_policy"]["requirement_checks"].append({"requirement": "Protected subgroup noninferiority must hold.",
                                                                  "checks": ["subgroup_noninferiority"]})
        self.rejected(contract, result, "unsupported value")

    def test_uncertainty_binds_stronger_comparator_and_this_evaluation(self):
        for key, value in (("comparison_target", "local_baseline"), ("published_value", 20), ("reproduced_value", 20),
                           ("comparator_value", 20), ("candidate_sha256", "a" * 64), ("contract_digest", "a" * 64)):
            contract, result = fixture()
            result["uncertainty"][key] = value
            self.rejected(contract, result, "uncertainty")
        contract, result = fixture()
        result["evidence"].append({"id": "unrelated", "kind": "evaluation", "sha256": "a" * 64, "locator": "urn:fixture:unrelated"})
        result["uncertainty"]["evidence_ids"] = ["unrelated"]
        self.rejected(contract, result, "this final evaluation")

    def test_uncertainty_uses_frozen_rule_and_valid_units(self):
        mutations = [
            ("value", -0.1), ("method", "unpaired trial interval"), ("independent_unit", "dependent trial"),
            ("n_independent_units", 3), ("confidence_level", 0.95), ("null_effect", -1),
            ("interval", [3, 1]), ("interval", None), ("interval", [1.0, 4.0]),
        ]
        for key, value in mutations:
            contract, result = fixture()
            result["uncertainty"][key] = value
            with self.subTest(key=key, value=value):
                self.rejected(contract, result, "uncertainty")
        contract, result = fixture()
        result["uncertainty"].update(value=0, interval=[0, 4])
        self.rejected(contract, result, "actual predeclared rule")

    def test_p_value_rule_does_not_invent_universal_alpha(self):
        contract, result = fixture()
        contract["comparison"]["uncertainty"]["method"] = "paired subject permutation test"
        rule = contract["admission_policy"]["uncertainty_rule"]
        rule.update(statistic="p_value", operator="<", threshold=0.01, method="paired subject permutation test", confidence_level=None)
        uncertainty = result["uncertainty"]
        uncertainty.update(statistic="p_value", method="paired subject permutation test", confidence_level=None, interval=None)
        refreeze(contract, result)
        for value, passes in ((0.009, True), (0.01, False), (0.04, False), (-0.1, False), (1.1, False)):
            uncertainty["value"] = value
            with self.subTest(value=value):
                self.assertEqual(paper.compare(contract, result)["comparison_admitted"], passes)
        uncertainty["value"] = 0.001
        result["measurement"]["candidate_value"] = 79
        self.rejected(contract, result, "meaningful effect")

    def test_posterior_rule_uses_declared_threshold(self):
        contract, result = fixture()
        contract["comparison"]["uncertainty"]["method"] = "subject posterior"
        contract["admission_policy"]["uncertainty_rule"].update(statistic="posterior_probability", method="subject posterior",
                                                                operator=">=", threshold=0.97, confidence_level=None)
        result["uncertainty"].update(statistic="posterior_probability", method="subject posterior", confidence_level=None, interval=None)
        refreeze(contract, result)
        for value, win in ((0.97, True), (0.96, False), (1.1, False)):
            result["uncertainty"]["value"] = value
            self.assertEqual(paper.compare(contract, result)["comparison_admitted"], win)

    def test_bad_or_unsupported_uncertainty_policy_fails_closed(self):
        for updates in ({"statistic": "unknown"}, {"operator": "<"}, {"operator": ">="}, {"threshold": -0.1},
                        {"confidence_level": None}, {"minimum_independent_units": True}, {"method": "different"}):
            contract, result = fixture()
            contract["admission_policy"]["uncertainty_rule"].update(updates)
            self.rejected(contract, result)

    def test_freeze_pins_contract_candidate_time_and_evaluator(self):
        mutations = [
            lambda c, r: c["episode"].update(improvement_loop="Changed after freeze"),
            lambda c, r: r.update(candidate_sha256="a" * 64),
            lambda c, r: r["freeze"].update(candidate_sha256="a" * 64),
            lambda c, r: r["evaluation"].update(candidate_sha256="a" * 64),
            lambda c, r: r["freeze"].update(contract_digest="a" * 64),
            lambda c, r: r["evaluation"].update(contract_digest="a" * 64),
            lambda c, r: r["freeze"].update(frozen_at=r["evaluation"]["started_at"]),
            lambda c, r: r["evaluation"].update(started_at="2026-11-16T08:00:00Z"),
            lambda c, r: r["freeze"].update(frozen_at="2026-11-16T09:00:00"),
            lambda c, r: r["evaluation"].update(evaluator_id="different evaluator"),
            lambda c, r: r["evaluation"].update(evaluator_sha256="a" * 64),
        ]
        for index, mutate in enumerate(mutations):
            contract, result = fixture()
            mutate(contract, result)
            with self.subTest(index=index):
                self.rejected(contract, result)

    def test_required_provenance_unknown_and_duplicate_ids(self):
        mutations = [
            lambda r: r.update(source_evidence_ids=["code"]),
            lambda r: r["evaluation"].update(evidence_ids=["unknown"]),
            lambda r: r["evaluation"].update(evidence_ids=["baseline"]),
            lambda r: r["freeze"].update(evidence_ids=[]),
            lambda r: r["evidence"].pop(0),
            lambda r: r["evidence"][0].update(sha256="a" * 64),
            lambda r: r["evidence"].append(copy.deepcopy(r["evidence"][0])),
            lambda r: r["budget_usage"]["access"].update(evidence_ids=["unknown"]),
        ]
        for index, mutate in enumerate(mutations):
            contract, result = fixture()
            mutate(result)
            with self.subTest(index=index):
                self.rejected(contract, result)

    def test_budget_counters_are_cumulative_finite_and_correct_units(self):
        for key in ("access", "resource"):
            for field, value in (("used", 21), ("used", -1), ("used", True), ("used", float("nan")),
                                 ("unit", "different unit"), ("scope", "only_this_successful_attempt")):
                contract, result = fixture()
                result["budget_usage"][key][field] = value
                with self.subTest(key=key, field=field, value=value):
                    self.rejected(contract, result)

    def test_result_rejects_nonfinite_numbers_booleans_and_claimed_pass_flags(self):
        for invalid in (True, False, float("nan"), float("inf"), -float("inf"), 10 ** 400):
            for area, key in (("measurement", "candidate_value"), ("uncertainty", "value"), ("uncertainty", "n_independent_units")):
                contract, result = fixture()
                result[area][key] = invalid
                with self.subTest(area=area, key=key, invalid=invalid):
                    self.rejected(contract, result)
        contract, result = fixture()
        result["uncertainty"]["passed"] = True
        self.rejected(contract, result, "unknown field")


if __name__ == "__main__":
    unittest.main()
