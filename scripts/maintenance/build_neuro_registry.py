#!/usr/bin/env python3
"""Materialize the construction roster without promoting execution evidence.

This joins existing source-qualified paper intake with the separately curated
neural roster. It deliberately does not infer scientific validity from files,
names, model scores, or reaching the requested count.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/neuroscience-benchmarks"


def read(path: Path):
    return json.loads(path.read_text())


def unique(rows, key):
    counts = Counter(row[key] for row in rows)
    duplicates = [value for value, count in counts.items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate {key}: {duplicates}")


def paper_roster():
    selection = read(DOCS / "readiness/selection_100.json")
    source = read(DOCS / "readiness/paper_projects.json")
    unique(source, "id")
    indexed = {row["id"]: row for row in source}
    selected = selection["selected_ids"]
    if len(selected) != 100 or len(set(selected)) != 100:
        raise ValueError("The selected paper intake must contain 100 unique projects")
    rows = []
    for source_id in selected:
        item = indexed[source_id]
        if not item["target_eligible_artifact_ready"]:
            raise ValueError(f"Selected paper lacks source qualification: {source_id}")
        if not item["data_urls"] or not item["code_revision_or_archive_version"]:
            raise ValueError(f"Missing pinned source inputs: {source_id}")
        rows.append({
            "id": f"PAPER-{source_id}",
            "track": "paper",
            "source_id": source_id,
            "title": item["title"],
            "status": "sourced_candidate",
            "assignment": item["declared_scope"],
            "central_reproduction_outputs": item["central_reproduction_outputs"],
            "improvement_outputs": item["improvement_outputs"],
            "paired_access_conditions": ["paper_and_data", "paper_data_official_code"],
            "counting_unit": "one_paper_project_with_nested_reproduction_and_improvement",
            "paper_url": item["paper_url"],
            "publication_year": item["publication_year"],
            "venue": item["venue"],
            "data_urls": item["data_urls"],
            "code_url": item["code_url"],
            "code_revision_or_archive_version": item["code_revision_or_archive_version"],
            "entrypoints": item["entrypoints"],
            "overlap_group": item.get("overlap_group"),
            "source_evidence": f"../readiness/{item['evidence_file']}",
            "remaining_gates": list(dict.fromkeys(item["unresolved_items"] + [
                "Freeze paper-specific central claims, input/assessment manifest and information boundary.",
                "Execute and independently audit references, controls, grading and measured resources.",
                "Qualify harness, meaningful difficulty, scientific review and target submission requirements.",
            ])),
            "resource_class": item["resource_class"],
            "fully_specified": False,
            "reference_validated": False,
            "research_qualified": False,
        })
    return rows


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-only", action="store_true")
    args = parser.parse_args()
    out = DOCS / "build"
    papers = paper_roster()
    write_json(out / "paper_100.json", {
        "schema_version": 1,
        "target": 100,
        "meaning": "Construction candidates, not 100 implemented or validated tasks",
        "tasks": papers,
    })
    if args.paper_only:
        print(json.dumps({"paper_construction_candidates": len(papers)}))
        return
    neural_doc = read(out / "neural_100.json")
    neural = neural_doc["tasks"]
    unique(neural, "id")
    for item in neural:
        if item["status"] not in {"sourced_candidate", "discovery_candidate"}:
            raise ValueError(f"Candidate roster cannot assert execution qualification: {item['id']}")
    combined = papers + [{**item, "track": "neural"} for item in neural]
    unique(combined, "id")
    counts = Counter(row["status"] for row in combined)
    summary = {
        "target_distinct_assignments": 200,
        "paper_candidate_projects": len(papers),
        "neural_candidate_assignments": len(neural),
        "candidate_assignments_total": len(combined),
        "remaining_candidate_slots": max(0, 200 - len(combined)),
        "candidate_evidence_stage_counts": dict(sorted(counts.items())),
        "source_maturity_detail": {
            "paper_artifact_ready_projects": len(papers),
            "neural_tasks_on_source_supported_collections": neural_doc["summary"]["audited_source_supported_tasks"],
            "neural_tasks_on_audited_but_unresolved_sources": neural_doc["summary"]["audited_unresolved_source_tasks"],
            "neural_discovery_tasks": sum(r["status"] == "discovery_candidate" for r in neural),
        },
        "implementation_and_qualification": "implementation_status.json (milestones are separate from full candidate qualification)",
        "scientific_admission_standard": "../RESEARCH_QUALITY_STANDARD.md (independent review required; never inferred by this generator)",
        "independence": "Assignments can share cohorts, stimuli, participants and model tools; counts are not independent biological replications",
        "paper_conditions_counted_separately": False,
        "source_files_sha256": {
            name: hashlib.sha256((out / name).read_bytes()).hexdigest()
            for name in ("paper_100.json", "neural_100.json")
        },
    }
    write_json(out / "registry.json", {"schema_version": 1, "summary": summary, "tasks": combined})
    lines = [
        "# Neuroscience task construction roster", "",
        f"Target: **200 distinct assignments** across the paper and neural suites. Current roster: **{len(papers)} paper projects + {len(neural)} neural assignments**.", "",
        "These counts describe construction candidates. Data/code access conditions, repeated model runs, individual cases and nested paper milestones do not add tasks. Shared cohorts remain dependent evidence. Actual reference, harness and scientific qualification are recorded separately.", "",
        "| Candidate evidence | Count |", "|---|---:|",
        *[f"| {status.replace('_', ' ')} | {count} |" for status, count in sorted(counts.items())], "",
        "The 168 sourced candidates comprise 100 artifact-ready paper projects, 58 neural assignments on source-supported collections, and 10 neural assignments whose audited sources retain unresolved access, adapter or terms gates. These are source checks, not executed benchmarks.", "",
        "- [Paper roster](paper_100.json): original selected source IDs, scientific scopes, artifacts and unresolved gates.",
        "- [Neural roster](NEURAL_100.md): source-specific questions, data contracts and qualification gaps.",
        "- [Combined machine-readable registry](registry.json).",
        "- [Implementation checkpoint](implementation_status.json): measured package milestones and unclosed full-project gates.",
        "- [Construction-audit overlay](construction_audit_index.json): later bounded source findings and current remaining gates; source audits do not promote task status.",
        "- [Cross-suite exposure audit](EXPOSURE_AUDIT.md): typed reuse and source/stimulus-family links to review before evaluation or RL splits.",
        "- [Research quality standard](../RESEARCH_QUALITY_STANDARD.md): actual PR-review lessons and scientific admission gates.",
        "- [Live build status](../BUILD_STATUS.md) and [Terminal-Bench standard](../TERMINAL_BENCH_STANDARD.md).", "",
        "Regenerate with `python3 tools/build_neuro_registry.py`. This operation joins metadata only; it performs no scientific execution and cannot promote a benchmark to research-qualified status.", "",
    ]
    (out / "README.md").write_text("\n".join(lines))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
