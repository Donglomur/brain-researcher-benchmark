"""Generated contract controls; fixture numbers are not neuroscience results."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from neurobench import paper_panel_comparison as panel


def fixture():
    evidence = [{"id": "paper", "kind": "paper", "url": "https://example.org/generated-paper",
                 "locator": "Generated fixture; not a real result", "supports": "Generated contract checks"}]
    anchor = {"status": "verified", "description": "Generated fixed source support", "evidence_ids": ["paper"]}
    def number(value, status="justified"):
        return {"status": status, "value": value, "rationale": "Generated prespecified rule", "evidence_ids": ["paper"]}
    def baseline(value):
        return {"status": "verified", "value": value, "description": "Generated source baseline", "evidence_ids": ["paper"]}
    def coordinate(name, direction, value, unit, role="score"):
        return {"id": name, "group_id": name, "role": role, "support_key": "full-source-summary",
            "metric": name, "unit": unit, "direction": direction,
            "published_baseline": baseline(value), "reproduced_author_baseline": baseline(value),
            "reproduction_tolerance": number(.1),
            "minimum_gain": number(.05) if role == "score" else number(None, "not_applicable"),
            "gain_eligible": role == "score", "gain_operator": ">=",
            "control_rule": {"status": "not_applicable" if role == "score" else "specified",
                "minimum": None if role == "score" else .45, "maximum": None if role == "score" else .55,
                "rationale": "Generated fixed negative control constraint", "evidence_ids": ["paper"]},
            "metric_domain": {"minimum": 0, "maximum": 100, "rationale": "Generated domain", "evidence_ids": ["paper"]},
            "evidence_ids": ["paper"]}
    coordinates = [coordinate("accuracy", "higher", .5, "fraction"),
                   coordinate("error", "lower", 2, "millimeters"),
                   coordinate("shuffle", "not_applicable", .5, "fraction", "control")]
    pin = {"path": "generated-only.json", "bytes": 1, "sha256": "1" * 64}
    conditions = {"paper_sha256": "2" * 64, "data_sha256": "3" * 64,
                  "official_code_sha256": None, "tool_policy_sha256": "4" * 64}
    contract = {"schema_version": panel.VERSION, "task_id": "GENERATED-PANEL",
        "objective": "reproduce_and_surpass_source_paper_same_panel",
        "disposition": "metadata_ready", "disposition_reason": "Generated source-only fixture",
        "source_paper": {"title": "Generated fixture", "url": "https://example.org/generated-paper"},
        "evidence": evidence, "same_task": {key: deepcopy(anchor) for key in panel.scalar.ANCHORS},
        "episode": {"improvement_loop": "Generated validation only", "candidate_freeze": "Before final feedback",
            "final_evaluation": "Complete generated panel", "access_budget": "2 source accesses",
            "resource_budget": "10 generated seconds", "baseline_policy": "Both frozen source and reproduced reference"},
        "lineage": {"scalar_contract": pin, "selected_endpoint_contract": None, "notes": "Generated fixture only"},
        "panel": {"source_manifest": pin, "support_scope": "Complete generated panel including mandatory shuffle control",
            "groups": [{"id": row["id"], "role": row["role"], "description": "Generated endpoint group",
                "independent_unit": "generated person", "support_description": "Generated complete support",
                "evidence_ids": ["paper"]} for row in coordinates],
            "coordinates": coordinates,
            "reference_selection": {"status": "verified", "description": "Generated strongest-reference binding", "evidence_ids": ["paper"]},
            "comparison_target": "stronger_of_published_and_reproduced_author_per_score_coordinate",
            "score_rule": "no_regression_on_every_score_coordinate_and_meaningful_gain_on_at_least_one_eligible_score_coordinate",
            "control_rule": "all_required_controls_pass_their_frozen_constraints_without_contributing_improvement",
            "scalar_aggregation": "none"},
        "scientific_inference": {"status": "unresolved", "method": "No scientific inference from generated fixture",
            "independent_unit": "Not established", "multiplicity_policy": "Not established", "evidence_ids": []},
        "blocking_issues": [], "binding_policy": {"evaluator": {"id": "generated-evaluator", "sha256": "5" * 64,
            "status": "verified", "evidence_ids": ["paper"]},
            "budgets": {"access": {"unit": "accesses", "limit": 2, "scope": "cumulative_episode"},
                        "resource": {"unit": "seconds", "limit": 10, "scope": "cumulative_episode"}},
            "conditions": {"paper_data": conditions,
                           "paper_data_official_code": dict(conditions, official_code_sha256="6" * 64)}}}
    result = {"schema_version": panel.RESULT_VERSION, "task_id": contract["task_id"],
        "claim": "same_task_finite_panel_numerical_comparison", "phase": "final",
        "contract_digest": panel.contract_digest(contract), "candidate_sha256": "7" * 64,
        "same_task": deepcopy(contract["same_task"]), "source_evidence_ids": ["paper"],
        "access_condition": "paper_data", "condition_binding": deepcopy(conditions),
        "freeze": {"contract_digest": panel.contract_digest(contract), "candidate_sha256": "7" * 64,
                   "frozen_at": "2026-01-01T00:00:00Z", "evidence_ids": ["freeze"]},
        "evaluation": {"evaluator_id": "generated-evaluator", "evaluator_sha256": "5" * 64,
                       "contract_digest": panel.contract_digest(contract), "candidate_sha256": "7" * 64,
                       "started_at": "2026-01-01T00:01:00Z", "evidence_ids": ["evaluation"]},
        "reproduced_author_baseline": {"role": "evaluator_owned_reference_shared_between_assistance_arms", "same_task": deepcopy(contract["same_task"]), "evidence_ids": ["reference"]},
        "measurements": [{**{key: row[key] for key in ("id", "group_id", "role", "support_key", "metric", "unit", "direction")},
                          "candidate_value": {"accuracy": .6, "error": 2, "shuffle": .5}[row["id"]],
                          "published_value": row["published_baseline"]["value"],
                          "reproduced_value": row["published_baseline"]["value"]} for row in coordinates],
        "budget_usage": {"access": {"unit": "accesses", "used": 2, "scope": "cumulative_episode", "evidence_ids": ["budget"]},
                         "resource": {"unit": "seconds", "used": 8, "scope": "cumulative_episode", "evidence_ids": ["budget"]}},
        "evidence": [{"id": key, "kind": kind, "sha256": "7" * 64 if kind == "candidate" else "8" * 64,
                      "locator": "generated-only/" + key} for key, kind in
                     [("candidate", "candidate"), ("freeze", "freeze"), ("evaluation", "evaluation"),
                      ("reference", "reproduced_baseline"), ("budget", "budget")]]}
    condition_digest = panel.contract_digest({"access_condition": result["access_condition"], "condition_binding": result["condition_binding"]})
    for row in (result["freeze"], result["evaluation"]):
        row.update(access_condition=result["access_condition"], condition_binding_digest=condition_digest)
    return contract, result


def rebind(contract, result):
    for row in (result, result["freeze"], result["evaluation"]):
        row["contract_digest"] = panel.contract_digest(contract)


class PanelComparisonTests(unittest.TestCase):
    def test_complete_mixed_unit_panel_without_aggregation(self):
        c, r = fixture(); self.assertEqual(panel.contract_validate(c), [])
        out = panel.compare(c, r)
        self.assertTrue(out["metadata_admitted"]); self.assertTrue(out["finite_numerical_dominance"])
        self.assertIsNone(out["paper_win"]); self.assertIsNone(out["scientific_superiority"])
        self.assertEqual(out["coordinate_results"][0]["gain"], "0.1")
        self.assertIsNone(out["coordinate_results"][2]["gain"])

    def test_hidden_regression_cannot_be_offset_by_large_gain(self):
        c, r = fixture(); r["measurements"][0]["candidate_value"] = 50
        r["measurements"][1]["candidate_value"] = 2.000000000000001
        out = panel.compare(c, r)
        self.assertFalse(out["finite_numerical_dominance"]); self.assertFalse(out["score_nonregression"])

    def test_missing_extra_and_duplicate_coordinates(self):
        for edit in (lambda rows: rows.pop(), lambda rows: rows.append(dict(rows[0], id="extra")), lambda rows: rows.append(deepcopy(rows[0]))):
            c, r = fixture(); edit(r["measurements"])
            self.assertFalse(panel.compare(c, r)["metadata_admitted"])

    def test_identity_units_role_and_direction_mismatch(self):
        for key, value in [("unit", "percent"), ("direction", "lower"), ("support_key", "subset"),
                           ("group_id", "other"), ("role", "control"), ("metric", "other")]:
            c, r = fixture(); r["measurements"][0][key] = value
            self.assertFalse(panel.compare(c, r)["metadata_admitted"], key)

    def test_invalid_json_numeric_and_duplicate_key_inputs(self):
        for value in [float("nan"), float("inf"), -float("inf"), True, 10**1000]:
            c, r = fixture(); r["measurements"][0]["candidate_value"] = value
            self.assertFalse(panel.compare(c, r)["metadata_admitted"])
        for value in ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e10000}']:
            with self.assertRaises(ValueError): panel.loads_contract(value)

    def test_candidate_and_contract_freeze_and_evaluator_source_binding(self):
        edits = [lambda r: r.update(contract_digest="9" * 64),
                 lambda r: r["freeze"].update(candidate_sha256="9" * 64),
                 lambda r: r["freeze"].update(frozen_at=r["evaluation"]["started_at"]),
                 lambda r: r["evaluation"].update(evaluator_sha256="9" * 64),
                 lambda r: r["same_task"]["split"].update(description="Different split"),
                 lambda r: r.update(source_evidence_ids=["unbound"]),
                 lambda r: r.update(phase="validation")]
        for edit in edits:
            c, r = fixture(); edit(r); self.assertFalse(panel.compare(c, r)["metadata_admitted"])

    def test_budget_history_and_evidence_kind_enforced(self):
        c, r = fixture(); r["budget_usage"]["resource"]["used"] = 11
        self.assertFalse(panel.compare(c, r)["metadata_admitted"])
        c, r = fixture(); r["budget_usage"]["access"]["scope"] = "latest_attempt"
        self.assertFalse(panel.compare(c, r)["metadata_admitted"])
        c, r = fixture(); r["evidence"][-1]["kind"] = "evaluation"
        self.assertFalse(panel.compare(c, r)["metadata_admitted"])

    def test_official_code_arms_are_distinct_and_same_data(self):
        c, r = fixture(); r["access_condition"] = "paper_data_official_code"
        self.assertFalse(panel.compare(c, r)["metadata_admitted"])
        r["condition_binding"] = deepcopy(c["binding_policy"]["conditions"][r["access_condition"]])
        self.assertFalse(panel.compare(c, r)["metadata_admitted"])
        condition_digest = panel.contract_digest({"access_condition": r["access_condition"], "condition_binding": r["condition_binding"]})
        for row in (r["freeze"], r["evaluation"]):
            row.update(access_condition=r["access_condition"], condition_binding_digest=condition_digest)
        self.assertTrue(panel.compare(c, r)["finite_numerical_dominance"])
        c["binding_policy"]["conditions"]["paper_data_official_code"]["data_sha256"] = "9" * 64
        self.assertTrue(panel.contract_validate(c))

    def test_stronger_reproduced_comparator_and_reproduction_gate(self):
        c, r = fixture(); r["measurements"][0]["candidate_value"] = .6; r["measurements"][0]["reproduced_value"] = .59
        self.assertFalse(panel.compare(c, r)["finite_numerical_dominance"])
        c, r = fixture(); r["measurements"][0]["candidate_value"] = 1; r["measurements"][0]["reproduced_value"] = .61
        out = panel.compare(c, r); self.assertFalse(out["finite_numerical_dominance"])

    def test_strict_vs_inclusive_meaningful_gain_no_epsilon(self):
        c, r = fixture(); r["measurements"][0]["candidate_value"] = .55
        self.assertTrue(panel.compare(c, r)["finite_numerical_dominance"])
        c["panel"]["coordinates"][0]["gain_operator"] = ">"; rebind(c, r)
        self.assertFalse(panel.compare(c, r)["finite_numerical_dominance"])

    def test_control_gain_never_counts_and_control_failure_blocks(self):
        c, r = fixture(); r["measurements"][0]["candidate_value"] = .5; r["measurements"][2]["candidate_value"] = .54
        self.assertFalse(panel.compare(c, r)["finite_numerical_dominance"])
        c, r = fixture(); r["measurements"][2]["candidate_value"] = .9
        out = panel.compare(c, r); self.assertFalse(out["required_controls_pass"]); self.assertFalse(out["finite_numerical_dominance"])
        c, r = fixture(); c["panel"]["coordinates"][2]["gain_eligible"] = True
        self.assertTrue(panel.contract_validate(c))

    def test_unresolved_thresholds_comparator_or_controls_do_not_pass(self):
        for edit in [lambda c: c["panel"]["coordinates"][0]["minimum_gain"].update(status="unresolved", value=None),
                     lambda c: c["panel"]["reference_selection"].update(status="unresolved"),
                     lambda c: c["panel"]["coordinates"][2]["control_rule"].update(status="unresolved", minimum=None, maximum=None)]:
            c, r = fixture(); c["disposition"] = "source_unresolved"; edit(c); rebind(c, r)
            self.assertEqual(panel.contract_validate(c), [])
            self.assertEqual(panel.compare(c, r)["status"], "unqualified_contract")

    def test_bad_tolerance_gain_domain_and_duplicate_contract_support(self):
        edits = [lambda c: c["panel"]["coordinates"][0]["reproduction_tolerance"].update(value=-1),
                 lambda c: c["panel"]["coordinates"][0]["minimum_gain"].update(value=0),
                 lambda c: c["panel"]["coordinates"][0]["metric_domain"].update(minimum=2, maximum=1),
                 lambda c: c["panel"]["coordinates"].append(deepcopy(c["panel"]["coordinates"][0])),
                 lambda c: c["panel"]["groups"].append(dict(c["panel"]["groups"][0], id="unused"))]
        for edit in edits:
            c, r = fixture(); edit(c); self.assertTrue(panel.contract_validate(c))

    def test_scientific_boolean_forgery_and_unsupported_aggregation_rejected(self):
        c, r = fixture(); r["scientific_superiority"] = True
        self.assertFalse(panel.compare(c, r)["metadata_admitted"])
        c, r = fixture(); c["panel"]["scalar_aggregation"] = "mean"
        self.assertTrue(panel.contract_validate(c))
        c, r = fixture(); c["scientific_inference"].update(status="specified", method="Caller claimed valid", evidence_ids=["paper"])
        rebind(c, r); out = panel.compare(c, r)
        self.assertTrue(out["finite_numerical_dominance"]); self.assertIsNone(out["scientific_superiority"])

    def test_schema_artifact_matches_frozen_source(self):
        path = ROOT / "docs/science/paper-panel-comparison/contract.schema.json"
        self.assertEqual(json.loads(path.read_text()), panel.CONTRACT_SCHEMA)

    def test_real_source_examples_stay_blocked_and_complete(self):
        root = ROOT / "docs/science/paper-panel-comparison/examples"
        cards = [json.loads(p.read_text()) for p in sorted(root.glob('*.contract.json'))]
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["task_id"], "PAPER-paper-method-replacement-005")
        self.assertEqual(panel.contract_validate(card), [])
        self.assertEqual(card["disposition"], "source_unresolved")
        self.assertTrue(panel._unresolved(card))
        self.assertEqual((len(card["panel"]["groups"]), len(card["panel"]["coordinates"])), (9, 9))
        self.assertTrue(all(row["minimum_gain"]["value"] is None for row in card["panel"]["coordinates"]))
        mapping = json.loads((root / "cardiac-source-endpoint-mapping.json").read_text())
        self.assertEqual(mapping["schema_version"], "paper-source-endpoint-mapping/v1")
        self.assertFalse(mapping["executable"])
        self.assertIsNone(mapping["comparison_contract"])
        self.assertIsNone(mapping["comparison_targets"])
        support = mapping["mandatory_support"]
        self.assertEqual(support["role"], "cohort_audit_and_paired_uncertainty_support")
        self.assertEqual((support["source_row_count"], support["source_group_count"]), (120, 6))
        self.assertEqual(len(support["released_participant_ids"]), 20)
        self.assertIsNone(mapping["comparison_mapping"]["nonregression_policy"])
        self.assertNotIn("panel", mapping)
        self.assertNotIn("binding_policy", mapping)
        self.assertTrue(panel.contract_validate(mapping))
        self.assertFalse((root / "cardiac-six-groups.contract.json").exists())


if __name__ == "__main__": unittest.main()
