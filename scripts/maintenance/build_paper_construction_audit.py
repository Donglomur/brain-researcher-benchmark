#!/usr/bin/env python3
"""Integrate saved paper construction reviews; never execute scientific sources.

Usage: python3 tools/build_paper_construction_audit.py [--check | --self-test]
The two known historical exposure pins are retained, not silently re-signed.
All other stale pins, unknown status values and reordered/missing IDs fail closed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = "docs/neuroscience-benchmarks/build"
AUDITS = "authoring/paper-construction-audit"
ROSTER = f"{BUILD}/paper_100.json"
SELF = "tools/build_paper_construction_audit.py"
BATCHES = [("a", 0, 34), ("b", 34, 67), ("c", 67, 100)]
REQUIRED = ("id", "source_id", "title", "evidence", "documented_endpoint",
            "input_and_code_lineage", "reference_execution_status",
            "improvement_evaluation_status", "comparability_gates",
            "resource_evidence", "remaining_gates", "next_action")
REFERENCE_CLASSES = {
    "source_only_no_executed_reference_established_in_inspected_evidence": "no_empirical_reference_established",
    "source_only_explicit_hold": "no_empirical_reference_established",
    "source_only_no_project_reference_run_evidence_found": "no_empirical_reference_established",
    "source_and_metadata_only_for_this_project": "no_empirical_reference_established",
    "bounded_real_reference_checkpoint": "bounded_empirical_reference",
    "bounded_real_reconstruction_and_known_program_replay": "bounded_empirical_reference",
    "executed_bounded_subset_source_reconciliation_blocked": "bounded_empirical_reference",
    "three_bounded_operator_references_executed": "bounded_empirical_reference",
    "generated_source_behavior_only": "generated_source_diagnostics_only",
}
IMPROVEMENT_CLASSES = {
    "independent_panel_not_established_in_inspected_evidence": False,
    "not_frozen_or_run": False,
    "not_executed_or_independently_qualified": False,
}
# Explicitly approved MICrONS supersession, not a general stale-pin exemption.
KNOWN_SUPERSESSIONS = {
    f"{BUILD}/exposure_aliases.json": (
        "d9862c468c3ece0d0e0cfca975f8980cea6a9dfbb7abfe5d3b4b96ca76045ac7",
        "963f9e1b6d528573c1c321629a0ab2ba6e1fb25b3e0404e3882b483ea7207c5f"),
    f"{BUILD}/exposure_audit.json": (
        "96c826360af4b8858cb33406e95242d27d7806e5896b98c211ccd3478a76661d",
        "974e56e839620059345f5b8ae1f5893e1d404c007864159dc84e6b330f49edca"),
}
QUEUE = [
    ("PAPER-paper-signal-add-020", "source-to-reference", "Active source/intake follow-up; prove table joins/scaling before fitting."),
    ("PAPER-paper-method-001", "bounded-reference-to-scientific-study", "Specify repeated-sampling uncertainty and source-figure scope."),
    ("PAPER-FIND-NEW-001", "bounded-reference-to-scientific-study", "Fresh paired-access study/report rubric and a separate budget/panel."),
    ("PAPER-ROOT-ADD-003", "bounded-reference-to-scientific-study", "Equal-runtime paired runner and protected-improvement enforcement."),
    ("PAPER-FIND-NEW-002", "source-to-reference", "Map optogenetic/context contrasts, experiments and bounded archive extraction."),
    ("PAPER-ROOT-ADD-013", "source-to-reference", "Map feeding/ripple conditions, detector and animal/session units."),
    ("PAPER-FIND-REP-012", "source-to-reference", "Separate spine features, intervention controls and future-dependent predictors."),
    ("PAPER-ROOT-ADD-020", "source-to-reference", "Bind memory-geometry axes to subject/face/PSTH units and amplitude nulls."),
    ("PAPER-paper-method-replacement-015", "baseline-eligibility-before-reference", "Resolve spinal-indicator training membership, timing, grouping and memory parity."),
]


class AuditError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise AuditError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def read_json(root, name):
    try:
        return json.loads((root / name).read_text())
    except (OSError, ValueError) as error:
        raise AuditError(f"Cannot read JSON {name}: {error}") from error


def file_pin(root, name):
    require(isinstance(name, str), "Non-string evidence path")
    p = Path(name)
    require(not p.is_absolute() and ".." not in p.parts, f"Unsafe evidence path: {name}")
    full = root / p
    require(full.is_file() and not full.is_symlink(), f"Missing/nonregular/symlink evidence: {name}")
    require(full.resolve().is_relative_to(root.resolve()), f"Evidence escapes root: {name}")
    data = full.read_bytes()
    return {"bytes": len(data), "sha256": digest(data)}


def declared_pins(batch):
    pins = batch.get("source_pins")
    if isinstance(pins, dict):
        require(all(isinstance(v, dict) for v in pins.values()), "Malformed pin values")
        return [dict(v, path=k) for k, v in pins.items()]
    require(isinstance(pins, list) and all(isinstance(v, dict) for v in pins), "Malformed pin inventory")
    return pins


def validate_rows(rows, expected, origin):
    require(isinstance(rows, list) and all(isinstance(t, dict) for t in rows), f"{origin}: malformed tasks")
    require([t.get("id") for t in rows] == [t["id"] for t in expected], f"{origin}: IDs missing, duplicated or reordered")
    for t, source in zip(rows, expected):
        require(all(k in t and t[k] not in (None, "", [], {}) for k in REQUIRED), f"{origin}/{t.get('id')}: incomplete required fields")
        require(t["source_id"] == source["source_id"] and t["title"] == source["title"], f"{t['id']}: source/title mismatch")
        for field, mapping in [("reference_execution_status", REFERENCE_CLASSES), ("improvement_evaluation_status", IMPROVEMENT_CLASSES)]:
            value = t[field]
            require(isinstance(value, dict) and isinstance(value.get("status"), str) and value["status"] in mapping, f"{t['id']}: unreviewed {field} value")
        require(isinstance(t["evidence"], list) and all(isinstance(e, dict) and isinstance(e.get("path"), str) for e in t["evidence"]), f"{t['id']}: malformed evidence")
        for flag in ["readiness_promotion", "global_status_changed", "roster_promotion"]:
            require(t.get(flag, False) is False, f"{t['id']}: unexpected promotion")


def validate_declared_pin(root, declaration, batch_name):
    require(isinstance(declaration.get("sha256"), str) and isinstance(declaration.get("bytes"), int), "Incomplete evidence pin")
    path = declaration.get("path")
    actual = file_pin(root, path)
    if all(actual[k] == declaration[k] for k in ["bytes", "sha256"]):
        return actual, None
    allowed = KNOWN_SUPERSESSIONS.get(path)
    require(batch_name == "c" and allowed == (declaration["sha256"], actual["sha256"]), f"Stale evidence pin: {path}")
    return actual, {"type": "historical_pin_superseded", "origin_batch": batch_name, "path": path,
                    "original_declaration": declaration, "current_pin": actual,
                    "reason": "Root-approved MICrONS family integration changed exposure aliases and audit from 55 to 57 cross-suite pairs. Original batch declarations retained; no biological-overlap verification inferred.",
                    "evidence": f"{AUDITS}/microns-route-reconciliation.json"}


def find_record(document, record_id):
    if isinstance(document, list):
        groups = [document]
    elif isinstance(document, dict):
        groups = [v for v in document.values() if isinstance(v, list)]
    else:
        groups = []
    return [x for group in groups for x in group if isinstance(x, dict) and x.get("id") == record_id]


def check_evidence_locator(root, evidence):
    """Resolve two literal historical prose locators without guessing record IDs."""
    path, locator = evidence["path"], evidence["record_id"]
    if (path, locator) == ("docs/neuroscience-benchmarks/readiness/signals_extension_c.json", "FIND-REP-012 source_provenance"):
        matches = find_record(read_json(root, path), "SIGNAL-EXT-C004")
        require(len(matches) == 1 and matches[0].get("source_provenance", {}).get("paper_record_id") == "FIND-REP-012", "Changed explicit spine-provenance locator")
        return "SIGNAL-EXT-C004.source_provenance.paper_record_id = FIND-REP-012"
    if (path, locator) == ("authoring/neural-source-audits/boldmoments-v1/AUDIT.md", "source-only BOLDMoments input/rights audit"):
        text = (root / path).read_text()
        require(text.startswith("# BOLDMoments: NEURAL-069/070 source audit") and "VersionA and VersionB are different estimands/preprocessing routes" in text, "Changed explicit BOLDMoments document locator")
        return "Whole Markdown document; heading and VersionA/VersionB scope checked"
    matches = find_record(read_json(root, path), locator)
    require(matches, f"Missing evidence record {path}/{locator}")
    if "record_sha256" in evidence:
        require(any(digest(canonical(m)) == evidence["record_sha256"] for m in matches), f"Changed evidence record {locator}")
    return None


def supported_erp_reference(reference, audit_receipt, audit_report):
    """Require completed reference, cleanup and saved-output audit; never infer from a plan."""
    return (reference.get("status") == "three_conditional_source_models_executed"
            and reference.get("container_absent") is True
            and audit_receipt.get("status") == "saved_output_audit_completed"
            and audit_receipt.get("returncode") == 0
            and audit_report.get("status") == "saved_output_arithmetic_consistent")


def validate_food_hold(summary):
    require(summary.get("candidate_id") == "PAPER-ROOT-ADD-013"
            and summary.get("status") == "inputs_and_primary_joins_qualified_scientific_reference_on_provenance_hold",
            "Food source/schema hold requires the reviewed candidate and status")
    require(summary.get("scientific_fits") == 0
            and all(summary.get(key) is False for key in (
                "scientific_reference_executed", "full_candidate_contract_complete", "readiness_promoted",
                "raw_temporal_provenance_verified", "NREM_rate_denominator_verified",
                "publication_detector_lineage_verified", "auxiliary_all_sheet_join_coverage_complete",
                "candidate_packet_sanitized")), "Food schema evidence cannot silently become scientific qualification")
    require(summary.get("current_cycle_seconds_charged") == 145 and summary.get("cycle_cap_seconds") == 240,
            "Food hold budget change requires explicit review")


def build(root):
    roster = read_json(root, ROSTER)
    require(isinstance(roster, dict) and isinstance(roster.get("tasks"), list), "Malformed paper roster")
    sources = roster["tasks"]
    require(len(sources) == 100 and len({t["id"] for t in sources}) == 100, "Expected100 distinct roster IDs")
    pins = {ROSTER: file_pin(root, ROSTER), SELF: file_pin(root, SELF)}
    rows, declarations, conflicts, originals, priorities = [], [], [], [], {}
    record_checks, locator_resolutions = 0, []
    for name, start, end in BATCHES:
        path = f"{AUDITS}/batch-{name}.json"
        batch = read_json(root, path)
        require(isinstance(batch, dict), f"Malformed batch {name}")
        validate_rows(batch.get("tasks"), sources[start:end], name)
        pins[path] = file_pin(root, path)
        for declaration in declared_pins(batch):
            actual, conflict = validate_declared_pin(root, declaration, name)
            pins[declaration["path"]] = actual
            declarations.append({"origin_batch": name, **declaration})
            if conflict:
                conflicts.append(conflict)
        for row in batch["tasks"]:
            for evidence in row["evidence"]:
                epath = evidence["path"]
                pins[epath] = file_pin(root, epath)
                if evidence.get("record_id"):
                    resolution = check_evidence_locator(root, evidence)
                    if resolution:
                        locator_resolutions.append({"id": row["id"], "original_evidence": evidence, "explicit_resolution": resolution})
                    record_checks += 1
            merged = copy.deepcopy(row)
            merged["origin_batch"] = {"name": name, "path": path, "sha256": pins[path]["sha256"], "original_row_sha256": digest(canonical(row))}
            merged["integration_classification"] = REFERENCE_CLASSES[row["reference_execution_status"]["status"]]
            rows.append(merged)
        original = {k: v for k, v in batch.items() if k not in ["tasks", "source_pins"]}
        originals.append({"origin_batch": name, "retained_context": original})
        require(isinstance(batch.get("priority_candidates"), list), f"Missing batch{name} priorities")
        for p in batch["priority_candidates"]:
            require(isinstance(p, dict) and p.get("id") not in priorities and isinstance(p.get("reason"), str), "Malformed/duplicate priority")
            priorities[p["id"]] = {"origin_batch": name, **p}
    require([t["id"] for t in rows] == [t["id"] for t in sources], "Combined order mismatch")
    counts = Counter(r["integration_classification"] for r in rows)
    empirical = [r["id"] for r in rows if r["integration_classification"] == "bounded_empirical_reference"]
    require(set(empirical) == {"PAPER-paper-method-001", "PAPER-FIND-NEW-001", "PAPER-FIND-REP-013", "PAPER-ROOT-ADD-003"}, "Empirical-reference identity set requires explicit review")
    generated = [r["id"] for r in rows if r["integration_classification"] == "generated_source_diagnostics_only"]
    require(generated == ["PAPER-paper-method-replacement-009"], "Generated-only identity set requires review")
    for source in sources:
        require(all(source.get(k) is False for k in ["fully_specified", "reference_validated", "research_qualified"]), "Roster qualification changed; review integration semantics")
    improvement_count = sum(IMPROVEMENT_CLASSES[r["improvement_evaluation_status"]["status"]] for r in rows)
    require(set(priorities) == {p[0] for p in QUEUE}, "Nine priority identity set mismatch")
    by_id = {r["id"]: r for r in rows}
    queue = []
    for rank, (id_, group, gate) in enumerate(QUEUE, 1):
        p = priorities[id_]
        queue.append({"position": rank, "id": id_, "title": by_id[id_]["title"], "gate_group": group,
                      "integration_gate": gate, "batch_recommendation": p,
                      "next_action": by_id[id_]["next_action"], "remaining_gates": by_id[id_]["remaining_gates"],
                      "execution_authorized_by_index": False})
    reconciliation = f"{AUDITS}/microns-route-reconciliation.json"
    pins[reconciliation] = file_pin(root, reconciliation)
    conflicts.append({"type": "source_route_reconciliation", "id": "PAPER-FIND-020", "path": reconciliation,
                      "detail": read_json(root, reconciliation), "readiness_change": False})
    overlays = []
    erp = "authoring/reward-emotion-erp"
    erp_stages = [
        ("source-v1/receipt.json", "bounded_source_acquisition", "completed_source_acquisition_not_empirical_reference"),
        ("source-v1/SCIENTIFIC_CONTRACT_REVIEW.json", "source_scientific_contract_review", "completed_source_review"),
        ("source-v1/R_RUNTIME_REVIEW.json", "source_runtime_review", "source_runtime_review_not_execution"),
        ("table-intake-v1/PLAN.md", "table_intake_plan", "historical_preparation"),
        ("table-intake-v1/execution.json", "table_intake", "completed_table_shapes_source_alignment_assumed"),
        ("table-intake-v1/outer-execution-001/receipt.json", "table_intake_receipt", "completed_intake_not_model_fit"),
        ("reference-v1/outer-execution-001/receipt.json", "reference_v1_startup", "failed_before_R_script_full_allowance_retained"),
        ("reference-v1/execution-001/worker.stderr", "reference_v1_failure_diagnostic", "file_descriptor_limit_failure_not_scientific_result"),
        ("reference-v2/FREEZE.json", "reference_v2_scientific_runtime_freeze", "unchanged_scientific_R_runtime_only_repair"),
        ("reference-v2/execution-001/receipt.json", "reference_v2_inner_execution", "read_receipt_for_actual_state"),
        ("reference-v2/outer-execution-001/receipt.json", "reference_v2_outer_execution", "read_receipt_for_actual_state"),
        ("reference-v2/execution-001/result.json", "reference_v2_saved_result", "bounded_conditional_model_outputs_not_full_paper"),
        ("reference-review-v1/FREEZE.json", "saved_output_audit_freeze", "audit_frozen_before_numerical_result_read"),
        ("reference-review-v1/execution-001/receipt.json", "saved_output_audit_receipt", "read_receipt_for_actual_state"),
        ("reference-review-v1/execution-001/audit/report.json", "saved_output_arithmetic_audit", "arithmetic_scope_not_refit_or_alignment_proof"),
        ("reference-review-v1/SUMMARY.json", "saved_output_review_summary", "bounded_reference_scope_and_remaining_gates"),
        ("reference-review-v1/SUMMARY.md", "saved_output_review_summary_text", "bounded_reference_scope_and_remaining_gates"),
        ("RESULT_SUMMARY.json", "root_current_result_summary", "current_bounded_reference_not_full_contract"),
        ("README.md", "root_current_result_scope", "current_bounded_reference_not_full_contract"),
    ]
    for suffix, stage, state in erp_stages:
        path = f"{erp}/{suffix}"
        if (root / path).exists():
            pins[path] = file_pin(root, path)
            if state == "read_receipt_for_actual_state":
                state = read_json(root, path)["status"]
            overlays.append({"id": "PAPER-paper-signal-add-020", "stage": stage, "path": path,
                             "state": state,
                             "snapshot_reference_count_effect": 0})
    current_declarations = []
    root_summary_path = f"{erp}/RESULT_SUMMARY.json"
    if root_summary_path in pins:
        for path, declared in read_json(root, root_summary_path)["source_pins"].items():
            actual = file_pin(root, path)
            require(actual == declared, "Current ERP summary has stale evidence: " + path)
            pins[path] = actual
            current_declarations.append({"origin": root_summary_path, "path": path, **declared})
    completion_paths = [f"{erp}/reference-v2/outer-execution-001/receipt.json",
                        f"{erp}/reference-review-v1/execution-001/receipt.json",
                        f"{erp}/reference-review-v1/execution-001/audit/report.json"]
    erp_completed = False
    if all(path in pins for path in completion_paths):
        reference, audit_receipt, audit_report = [read_json(root, path) for path in completion_paths]
        erp_completed = supported_erp_reference(reference, audit_receipt, audit_report)
        if erp_completed:
            result_path = f"{erp}/reference-v2/execution-001/result.json"
            inner_path = f"{erp}/reference-v2/execution-001/receipt.json"
            require(result_path in pins and inner_path in pins, "Completed ERP overlay needs exact reference result/inner receipt")
            require(reference["inner_receipt_sha256"] == pins[inner_path]["sha256"], "ERP outer/inner receipt linkage")
            inner = read_json(root, inner_path)
            require(inner["result_sha256"] == audit_report["result_pin"]["sha256"] == pins[result_path]["sha256"], "ERP result/audit linkage")
            require(audit_receipt["report_sha256"] == pins[completion_paths[2]]["sha256"], "ERP audit receipt/report linkage")
            require(audit_report["outer_reference_receipt_pin"] == pins[completion_paths[0]], "ERP independently reviewed reference receipt")
            erp_item = next(q for q in queue if q["id"] == "PAPER-paper-signal-add-020")
            erp_item["historical_batch_next_action"] = erp_item["next_action"]
            erp_item["historical_batch_remaining_gates"] = erp_item["remaining_gates"]
            erp_item["gate_group"] = "bounded-reference-to-scientific-study"
            erp_item["integration_gate"] = "Three conditional fits and saved-output arithmetic audit completed; resolve independent ERP-to-trial lineage, explicit partial endpoint coverage and a separate improvement panel/candidate-report contract. The 240-second cycle is exhausted."
            erp_item["next_action"] = "Document the unverified positional alignment; construct independent row-lineage evidence where possible, define remaining paper endpoints and a grouped/disjoint improvement panel under a new reviewed budget."
            erp_item["remaining_gates"] = ["Independent ERP-to-behavior row correspondence remains unverified.", "Raw EEG and other paper endpoints have not been reconstructed.", "No independent improvement panel or completed candidate/report-grading contract.", "New execution requires a separately authorized budget; the 240-second cycle is exhausted."]
    current_empirical = empirical + (["PAPER-paper-signal-add-020"] if erp_completed else [])
    holds = []
    food = "authoring/food-ripples"
    food_summary_path = f"{food}/RESULT_SUMMARY.json"
    if (root / food_summary_path).exists():
        food_summary = read_json(root, food_summary_path)
        validate_food_hold(food_summary)
        food_stages = [
            ("RESULT_SUMMARY.json", "root_source_schema_hold_summary"),
            ("README.md", "source_schema_hold_scope"),
            ("SOURCE_QUESTIONS.md", "unsent_provenance_questions"),
            ("source-v1/execution-001/receipt.json", "bounded_source_text_acquisition"),
            ("intake-schema-v1/outer-execution-001/receipt.json", "failed_intake_before_payload_and_container"),
            ("intake-schema-v2/execution-001/receipt.json", "repaired_transport_schema_execution"),
            ("intake-review-v1/REVIEW.md", "saved_metadata_review_and_limits"),
        ]
        for suffix, stage in food_stages:
            path = f"{food}/{suffix}"
            pins[path] = file_pin(root, path)
            overlays.append({"id": "PAPER-ROOT-ADD-013", "stage": stage, "path": path,
                             "state": "source_schema_evidence_on_scientific_provenance_hold",
                             "snapshot_reference_count_effect": 0, "current_reference_count_effect": 0})
        for path, declared in food_summary["source_pins"].items():
            require(not path.lower().endswith((".mat", ".xlsx")), "No raw food input may be opened by this metadata integration")
            actual = file_pin(root, path)
            require(actual == declared, "Current food summary has stale evidence: " + path)
            pins[path] = actual
            current_declarations.append({"origin": food_summary_path, "path": path, **declared})
        fouter_path = f"{food}/intake-schema-v2/outer-execution-001/receipt.json"
        finner_path = f"{food}/intake-schema-v2/execution-001/receipt.json"
        freceipt_path = f"{food}/intake-review-v1/execution-receipt.json"
        freview_path = f"{food}/intake-review-v1/execution-001/review.json"
        fouter, finner, freceipt, freview = [read_json(root, p) for p in (fouter_path, finner_path, freceipt_path, freview_path)]
        require(fouter["inner_receipt_sha256"] == pins[finner_path]["sha256"], "Food outer/inner receipt linkage")
        require(fouter["status"] == finner["status"] == "schema_complete_requires_provenance_review"
                and fouter["owned_container_absent"] is True and finner["cleanup_absence_verified"] is True,
                "Food schema and cleanup evidence")
        require(freceipt["status"] == "saved_metadata_review_completed"
                and freceipt["review_sha256"] == pins[freview_path]["sha256"]
                and freview["status"] == "saved_metadata_consistent_provenance_gates_remain"
                and freceipt["cumulative_charged_seconds"] == food_summary["current_cycle_seconds_charged"],
                "Food saved-review receipt and budget linkage")
        require(freview["cohort"]["records"] == food_summary["records"] == food_summary["unique_animal_day_keys"]
                and freview["cohort"]["animals"] == food_summary["animals"]
                and freview["join_dispositions"]["matched_source_range"] == food_summary["primary_worksheet_joins_consistent"],
                "Food summary and reviewed cohort metadata")
        food_item = next(q for q in queue if q["id"] == "PAPER-ROOT-ADD-013")
        food_item["historical_batch_next_action"] = food_item["next_action"]
        food_item["historical_batch_remaining_gates"] = food_item["remaining_gates"]
        food_item["gate_group"] = "provenance-resolution-before-effects"
        food_item["current_recommendation"] = "The verified 95-record/10-animal release and primary worksheet joins make the remaining source discrepancies concrete. Resolve them before interpreting pre/post effects; schema consistency alone is insufficient."
        food_item["integration_gate"] = "Resolve the generating revision, detector-to-publication mapping, true pre/post periods, rate denominator and five unexplained condition-code records before any effect estimate. Preserve transport repair and auxiliary join/header caveats; no scientific reference was run."
        food_item["next_action"] = "Use the prepared unsent provenance questions and existing metadata to close source lineage. Freeze any later numerical calculation only after its estimand and unresolved assumptions are explicitly reviewed; the current intake authorizes no future effect analysis."
        food_item["remaining_gates"] = [
            "Released event powers versus the paper's joint-threshold detector are not reconciled.",
            "Raw post-only temporal provenance and NREM-occupancy rate denominator remain unverified.",
            "Three condition1000 records, one1700 and one2000 lack biological meanings;300/adlib has one explicit label conversion.",
            "Primary95 joins are consistent; auxiliary all-sheet joins omit a first-row data record, and the operator header capture contains a recording path.",
            "No effect estimate, scientific paper reference, sanitized candidate packet or independent improvement is qualified."]
        holds.append({"id": "PAPER-ROOT-ADD-013", "status": food_summary["status"],
                      "summary_path": food_summary_path, "records": food_summary["records"],
                      "animals": food_summary["animals"], "primary_joins": food_summary["primary_worksheet_joins_consistent"],
                      "charged_seconds": 145, "cycle_cap_seconds": 240,
                      "scientific_reference_count_effect": 0, "readiness_promotion": False,
                      "remaining_gates": food_item["remaining_gates"]})
    # Snapshot read-set stability; do not pin volatile BUILD_STATUS.md or mutate inputs.
    for path, expected in pins.items():
        require(file_pin(root, path) == expected, f"Input changed during build: {path}")
    result = {
        "schema_version": 1, "checked_on": "2026-10-30", "status": "construction_audit_not_scientific_admission",
        "scope": "All 100 existing paper projects. Integrates saved text/metadata and prior scalar-result reports only; no source execution, recording reads, fits, new tasks or roster/status edits.",
        "summary": {"scope": "original_three_batch_snapshot_preserved_before_ERP_reference_overlay", "paper_projects": len(rows), "bounded_empirical_reference_projects": counts["bounded_empirical_reference"],
                    "bounded_empirical_reference_ids": empirical, "generated_diagnostics_only_projects": counts["generated_source_diagnostics_only"],
                    "generated_diagnostics_only_ids": generated, "no_empirical_reference_established": counts["no_empirical_reference_established"],
                    "qualified_improvement_projects": improvement_count, "full_candidate_contracts_completed": sum(t["fully_specified"] for t in sources),
                    "research_qualified": sum(t["research_qualified"] for t in sources), "readiness_promotions": 0,
                    "meaning": "Historical three-batch snapshot: four paper IDs have bounded empirical references, 95 have none established, and one RRR project has generated-source diagnostics only. Current separately evidenced work is in current_reference_summary; original rows and statuses are unchanged."},
        "current_reference_summary": {"scope": "original_snapshot_plus_completed_linked_ERP_reference_and_independent_saved_output_audit",
                    "paper_projects": len(rows), "bounded_empirical_reference_projects": len(current_empirical),
                    "bounded_empirical_reference_ids": current_empirical,
                    "generated_diagnostics_only_projects": len(generated), "generated_diagnostics_only_ids": generated,
                    "no_empirical_reference_established": len(rows) - len(current_empirical) - len(generated),
                    "qualified_improvement_projects": improvement_count,
                    "full_candidate_contracts_completed": sum(t["fully_specified"] for t in sources),
                    "research_qualified": sum(t["research_qualified"] for t in sources), "roster_readiness_promotions": 0,
                    "erp_completed_reference_overlay": erp_completed,
                    "meaning": "A current bounded-reference milestone may be added only from linked completed reference and audit receipts; it does not rewrite historical batch statuses or promote benchmark readiness."},
        "validation": {"ordered_roster_ids": len(rows), "batch_sizes": [34, 33, 33], "evidence_record_checks": record_checks,
                       "declared_pin_occurrences": len(declarations), "unique_current_evidence_pins": len(pins),
                       "known_historical_pin_conflicts": sum(c["type"] == "historical_pin_superseded" for c in conflicts),
                       "unknown_stale_pins": 0, "all_other_declared_pins_current": True,
                       "required_fields_complete": True, "original_rows_preserved": True,
                       "explicit_historical_locator_resolutions": locator_resolutions,
                       "classification_policy": "Exact reviewed status-enum mapping; unknown statuses fail. No substring or heuristic classification."},
        "tasks": rows, "execution_queue": queue,
        "queue_interpretation": "Nine inherited priorities organized by prerequisite gates. Order is a reviewable construction queue, not automatic execution permission, scientific ranking, a runtime promise or readiness promotion.",
        "subsequent_work_overlays": overlays, "current_construction_holds": holds,
        "conflicts_and_reconciliations": conflicts,
        "original_batch_context": originals, "original_declared_pins": declarations,
        "current_work_declared_pins": current_declarations,
        "source_pins": dict(sorted(pins.items())),
    }
    return result


def render(report):
    s = report["current_reference_summary"]
    erp_complete = s["erp_completed_reference_overlay"]
    snapshot_note = ("The subsequent ERP reference and independent saved-output audit add one bounded result; they do not rewrite any original row or promote roster readiness."
                     if erp_complete else "No completed linked ERP reference/audit addition is established; original rows and roster readiness remain unchanged.")
    erp_note = ("The ERP overlay preserves intake, the failed first startup, the runtime-only repair, the completed reference and its independent saved-output audit. The first failure occurred before the R script because its file-descriptor limit was too low; its full budget charge remains. Three models now share 6,403 retained rows and 41 people. The added within-P3b contrast has two-sided full-covariance normal p≈0.2134 (source-reported Satterthwaite p≈0.2146): no rejection at 0.05, no equivalence or cross-component claim. The 240-second cycle is exhausted. Its next gates are row lineage, remaining endpoint scope and an independent improvement/candidate-report contract, not a pending first fit."
                if erp_complete else "ERP source, intake and any available execution/audit artifacts are preserved as subsequent work. A completed linked reference and audit chain is required before adding an empirical-reference milestone.")
    lines = ["# Construction audit of the 100 paper projects", "",
             f"All 100 existing projects have source-level construction reviews. **{s['bounded_empirical_reference_projects']} paper projects have bounded empirical reference results; {s['generated_diagnostics_only_projects']} has generated-source diagnostics only; {s['no_empirical_reference_established']} have no empirical reference established in the inspected evidence.** None has a completed full candidate contract or independently qualified improvement result.", "",
             "The original three-batch snapshot remains **4 bounded references / 1 generated-only / 95 without an empirical reference**. " + snapshot_note, "",
             "The [machine-readable audit](paper_construction_audit.json) preserves every original batch row, its source and its unresolved gates. Source availability does not establish runtime compatibility, whole-paper reproduction, model difficulty or scientific acceptance.", "",
             "| Empirical project | Executed scope and limits |", "|---|---|"]
    for row in report["tasks"]:
        if row["integration_classification"] != "bounded_empirical_reference":
            continue
        ref = row["reference_execution_status"]
        detail = ref.get("scope", ref.get("evidence", "See exact saved reference status."))
        lines.append(f"| {row['id']} | {str(detail).replace('|', '/')} |")
    if s["erp_completed_reference_overlay"]:
        lines.append("| PAPER-paper-signal-add-020 | Three conditional processed-ERP mixed models, 6,403 common rows / 41 people; four frozen paper beta/t rounding pairs match and independent saved-output arithmetic passes. ERP-to-behavior row order remains assumed; raw EEG, other paper endpoints and improvement remain outside scope. |")
    lines += ["", "RRR's generated-input checks demonstrate specific source behavior, not its incidence or scientific impact on real recordings. GCaMP8 remains held on grouping, target timing, checkpoint membership and memory. Negative results and unresolved findings are retained.", "",
              "## Nine next construction decisions", "",
              "These priorities combine scientific value with a concrete evidence gap. They include source-to-reference work, turning existing references into a defensible study, baseline-eligibility repair and provenance resolution before effects. Large or difficult projects are not removed merely because a smaller table exists.", ""]
    for item in report["execution_queue"]:
        reason = item.get("current_recommendation", item["batch_recommendation"]["reason"])
        lines += [f"{item['position']}. **{item['id']} — {item['title']}** ({item['gate_group']}). {reason} Next gate: {item['integration_gate']}", ""]
    if report["current_construction_holds"]:
        lines += ["## Food/ripple source and schema hold", "",
                  "**Food/ripple adds no empirical reference.** The release contains 95 unique animal/day records from 10 animals; all 95 primary worksheet joins are internally consistent. The source, failed transport attempt, repaired isolated schema run and independent saved-metadata review are retained, with **145/240 seconds charged**. No effect estimate or paper-result reproduction ran.", "",
                  "The generating source version, exported detector versus the paper's detector, raw post-only periods and NREM rate denominator remain unresolved. Five records with codes1000/1700/2000 have no established biological mapping. A negative event-prefix diagnostic cannot resolve raw temporal provenance. The auxiliary all-sheet join omits a real first-row record and its header capture contains an author recording path; it is not a sanitized candidate packet. Resolve these gates before effects. Prepared source questions have not been sent, and the remaining budget does not authorize bypassing the hold.", "",
                  "The current paper totals remain **5 bounded references / 1 generated-only / 94 without an empirical reference**; this metadata-only addition leaves the existing three neural references and global eight-reference total unchanged. The earlier independent review remains a prior snapshot, not a review of this amendment.", ""]
    lines += ["## Evidence and scope that remain open", "",
              "Reproduction and improvement require separate endpoints. Keep literal author metrics/preprocessing distinct from corrected or newly proposed analyses; matching a published p-value, a plotted aggregate or an exposed target is insufficient. Preserve independent participant/animal/session/stimulus units, exact assessment exposure, signed effects and all exclusions. A null or inconclusive conclusion can be correct.", "",
              erp_note, "",
              "Two batch-C exposure pins are historical after the approved MICrONS update. The original hashes remain recorded, alongside the current hashes and the route reconciliation. All other declared pins must match; unknown stale pins stop regeneration. No historical batch was silently rewritten.", "",
              "The references are partial: dimensionality covers one session; astrocyte covers a declared reconstruction policy rather than full null/cohort inference; Purkinje retains source-to-export discrepancies; language covers bounded encoding, mixed-model and condition-summary endpoints. The ERP overlay's scope is described above. The astrocyte reference allowance is nearly spent, and an agent study needs its own budget. Public observations are not automatically an independent improvement panel.", "",
              "Shared IBL, Allen, Stringer, COGITATE, BrainTreebank and MICrONS sources require explicit overlap and exposure handling. Manuscript, software, recordings, stimuli and model licenses have different scopes; source records with conflicting license notes remain unresolved rather than being assigned blanket clearance.", "",
              "## Rebuild and validation", "",
              f"The integration covers 100 ordered task IDs, {report['validation']['evidence_record_checks']} evidence locators, {report['validation']['declared_pin_occurrences']} original pin declarations and {report['validation']['unique_current_evidence_pins']} unique current evidence files. Two historical prose locators have explicit resolutions; their original wording is preserved.", "",
              "Run `python3 tools/build_paper_construction_audit.py --self-test`, then `python3 tools/build_paper_construction_audit.py --check`. A normal invocation regenerates only this JSON and Markdown. Validation checks the exact ordered 100 IDs, required fields, evidence records, original pin declarations, current hashes and explicit status mapping. The generator pins its own source and avoids volatile BUILD_STATUS.md.", ""]
    return "\n".join(lines)


class Tests(unittest.TestCase):
    def fixture(self):
        t = {k: "value" for k in REQUIRED}
        t.update(id="PAPER-x", source_id="x", title="X", evidence=[{"path": "e.json"}],
                 reference_execution_status={"status": "source_only_explicit_hold"},
                 improvement_evaluation_status={"status": "not_frozen_or_run"})
        return t

    def test_valid_and_changed_order(self):
        a = self.fixture(); b = dict(a, id="PAPER-y", source_id="y")
        validate_rows([a, b], [a, b], "test")
        with self.assertRaises(AuditError): validate_rows([b, a], [a, b], "test")

    def test_duplicate_and_missing_ids(self):
        a = self.fixture(); b = dict(a, id="PAPER-y")
        for value in [[a, a], [a]]:
            with self.assertRaises(AuditError): validate_rows(value, [a, b], "test")

    def test_malformed_shapes_and_missing_field(self):
        for rows in [None, {}, ["row"], [dict(self.fixture(), evidence="bad")]]:
            with self.assertRaises(AuditError): validate_rows(rows, [self.fixture()], "test")
        row = self.fixture(); del row["next_action"]
        with self.assertRaises(AuditError): validate_rows([row], [self.fixture()], "test")

    def test_unknown_status_and_promotion(self):
        for replacement in [{"reference_execution_status": {"status": "probably_passed"}}, {"reference_execution_status": {"status": []}}, {"readiness_promotion": True}]:
            with self.assertRaises(AuditError): validate_rows([dict(self.fixture(), **replacement)], [self.fixture()], "test")

    def test_hash_size_and_path_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "x.json").write_text("{}")
            p = dict(file_pin(root, "x.json"), path="x.json")
            validate_declared_pin(root, p, "a")
            for altered in [dict(p, bytes=99), dict(p, sha256="0" * 64)]:
                with self.assertRaises(AuditError): validate_declared_pin(root, altered, "a")
            with self.assertRaises(AuditError): file_pin(root, "../x")
            (root / "link").symlink_to(root / "x.json")
            with self.assertRaises(AuditError): file_pin(root, "link")

    def test_exact_status_categories(self):
        self.assertEqual(REFERENCE_CLASSES["generated_source_behavior_only"], "generated_source_diagnostics_only")
        self.assertEqual(REFERENCE_CLASSES["source_only_explicit_hold"], "no_empirical_reference_established")

    def test_record_locator_hash_and_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            row = {"id": "r1", "value": 2}
            (root / "records.json").write_text(json.dumps({"tasks": [row]}))
            e = {"path": "records.json", "record_id": "r1", "record_sha256": digest(canonical(row))}
            self.assertIsNone(check_evidence_locator(root, e))
            for altered in [dict(e, record_id="r2"), dict(e, record_sha256="0" * 64)]:
                with self.assertRaises(AuditError): check_evidence_locator(root, altered)

    def test_erp_reference_requires_complete_audited_chain(self):
        ref = {"status": "three_conditional_source_models_executed", "container_absent": True}
        receipt = {"status": "saved_output_audit_completed", "returncode": 0}
        report = {"status": "saved_output_arithmetic_consistent"}
        self.assertTrue(supported_erp_reference(ref, receipt, report))
        for a, b, c in [(dict(ref, status="failed_preserved"), receipt, report),
                        (dict(ref, container_absent=False), receipt, report),
                        (ref, dict(receipt, returncode=1), report),
                        (ref, receipt, dict(report, status="started"))]:
            self.assertFalse(supported_erp_reference(a, b, c))

    def test_food_schema_hold_cannot_promote_reference(self):
        summary = {"candidate_id": "PAPER-ROOT-ADD-013",
                   "status": "inputs_and_primary_joins_qualified_scientific_reference_on_provenance_hold",
                   "scientific_fits": 0, "current_cycle_seconds_charged": 145, "cycle_cap_seconds": 240}
        for key in ("scientific_reference_executed", "full_candidate_contract_complete", "readiness_promoted",
                    "raw_temporal_provenance_verified", "NREM_rate_denominator_verified",
                    "publication_detector_lineage_verified", "auxiliary_all_sheet_join_coverage_complete",
                    "candidate_packet_sanitized"):
            summary[key] = False
        validate_food_hold(summary)
        for change in ({"scientific_reference_executed": True}, {"scientific_fits": 1},
                       {"readiness_promoted": True}, {"current_cycle_seconds_charged": 0},
                       {"publication_detector_lineage_verified": True}):
            with self.assertRaises(AuditError): validate_food_hold(dict(summary, **change))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument("--check", action="store_true", help="Verify current outputs match regenerated metadata")
    options.add_argument("--self-test", action="store_true", help="Run generated metadata-only validation cases")
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
        return 0 if result.wasSuccessful() else 1
    try:
        report = build(ROOT)
        outputs = {ROOT / BUILD / "paper_construction_audit.json": json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   ROOT / BUILD / "PAPER_CONSTRUCTION_AUDIT.md": render(report)}
        if args.check:
            require(all(p.exists() and p.read_text() == text for p, text in outputs.items()), "Generated outputs differ; inspect source changes before regeneration")
        else:
            for p, text in outputs.items():
                tmp = p.with_name(p.name + ".tmp")
                tmp.write_text(text)
                tmp.replace(p)
        print(json.dumps({"status": "PASS", "check_only": args.check, "summary": report["summary"], "current_reference_summary": report["current_reference_summary"], "validation": report["validation"]}, indent=2))
        return 0
    except (AuditError, KeyError, TypeError, OSError) as error:
        print(f"Paper construction audit blocked: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
