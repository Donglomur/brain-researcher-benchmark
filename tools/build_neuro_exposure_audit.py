#!/usr/bin/env python3
"""Index declared cross-task exposure links; never infer biological independence.

Reads roster/catalog metadata only. Exact URL/label matches are evidence leads,
not assertions of identical participants or complete acquisition equivalence.
"""
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/neuroscience-benchmarks"
OUT = DOCS / "build"


def load(path):
    return json.loads(path.read_text())


def locator(value):
    if not isinstance(value, str) or not value.strip():
        return None
    u = urlsplit(value.strip())
    if u.scheme not in ("https", "http") or not u.netloc:
        return None
    # Keep query strings: archive versions and object selectors may live there.
    return urlunsplit(("https", u.netloc.lower(), u.path.rstrip("/"), u.query, ""))


def main():
    inputs = [OUT / "paper_100.json", OUT / "neural_100.json"] + [
        DOCS / "catalog" / name for name in (
            "datasets_paper_linked.json", "datasets_fmri_eeg.json",
            "datasets_nonfmri_noneeg.json")]
    papers = load(inputs[0])["tasks"]
    neural = load(inputs[1])["tasks"]
    tasks = {r["id"]: r for r in papers + neural}
    if len(tasks) != len(papers) + len(neural) or len(tasks) != 200:
        raise ValueError("Expected 200 unique candidate identities")
    paper_ids = {r["id"] for r in papers}
    neural_ids = {r["id"] for r in neural}
    links = {}

    def add(left, right, relation, value, evidence):
        if left == right or left not in tasks or right not in tasks:
            raise ValueError("Invalid selected-task edge")
        a, b = sorted((left, right))
        key = (a, b, relation, value)
        item = links.setdefault(key, {
            "tasks": [a, b], "relation": relation, "value": value,
            "evidence": [], "cross_suite": (a in paper_ids) != (b in paper_ids),
            "biological_overlap_verified": False,
        })
        if evidence not in item["evidence"]:
            item["evidence"].append(evidence)

    sources = defaultdict(list)
    labels = defaultdict(list)
    paper_urls = defaultdict(list)
    data_urls = defaultdict(list)
    for row in neural:
        for source in row["source_ids"]:
            sources[source].append(row["id"])
        for label in row.get("overlap_group", []):
            if label:
                labels[str(label).strip().casefold()].append(row["id"])
        reference = row["reference"]
        if key := locator(reference.get("source_paper")):
            paper_urls[key].append(row["id"])
        if key := locator(reference.get("data_url")):
            data_urls[key].append(row["id"])
    for row in papers:
        if label := row.get("overlap_group"):
            labels[str(label).strip().casefold()].append(row["id"])
        if key := locator(row.get("paper_url")):
            paper_urls[key].append(row["id"])
        for url in row.get("data_urls", []):
            if key := locator(url):
                data_urls[key].append(row["id"])
    for relation, mapping in (
        ("shared_declared_neural_source", sources),
        ("shared_literal_overlap_label", labels),
        ("shared_exact_paper_locator", paper_urls),
        ("shared_exact_data_locator", data_urls),
    ):
        for value, ids in mapping.items():
            for a, b in combinations(sorted(set(ids)), 2):
                add(a, b, relation, value, "build/paper_100.json and build/neural_100.json")

    unresolved_links = []
    for path in inputs[2:]:
        for source in load(path):
            if source["id"] not in sources:
                continue
            for related in source.get("related_paper_ids", []):
                pid = related if related.startswith("PAPER-") else "PAPER-" + related
                if pid not in paper_ids:
                    unresolved_links.append({"source_id": source["id"],
                        "catalog_related_paper_id": related,
                        "reason": "not present under this exact ID in selected paper roster"})
                    continue
                for nid in sources[source["id"]]:
                    add(pid, nid, "catalog_declared_source_to_paper", source["id"],
                        str(path.relative_to(DOCS)))

    alias_path = OUT / "exposure_aliases.json"
    aliases = load(alias_path)
    inputs.append(alias_path)
    for group in aliases["groups"]:
        named_papers = set(group.get("paper_ids", []))
        if not named_papers <= paper_ids:
            raise ValueError("Alias names an unselected paper")
        members = named_papers | {r["id"] for r in papers
                   if r.get("overlap_group") in group.get("paper_overlap_labels", [])}
        members.update(r["id"] for r in neural
                       if set(r["source_ids"]) & set(group["neural_source_ids"]))
        for a, b in combinations(sorted(members), 2):
            add(a, b, group["relation"], group["id"], group["evidence"])
            links[(a, b, group["relation"], group["id"])]["scope_limit"] = group["limit"]

    # Pin alias rationale as well as the directly joined fields and generator.
    inputs.extend(ROOT / p for p in aliases.get("supporting_evidence_paths", []))
    inputs.append(Path(__file__).resolve())

    rows = [links[k] for k in sorted(links)]
    cross_pairs = sorted({tuple(r["tasks"]) for r in rows if r["cross_suite"]})
    linked_papers = {i for pair in cross_pairs for i in pair if i in paper_ids}
    linked_neural = {i for pair in cross_pairs for i in pair if i in neural_ids}
    result = {
        "schema_version": 1, "status": "declared_metadata_links_only",
        "candidate_tasks": len(tasks), "typed_evidence_edges": len(rows),
        "unique_linked_task_pairs": len({tuple(r["tasks"]) for r in rows}),
        "cross_suite_linked_task_pairs": len(cross_pairs),
        "cross_suite_linked_paper_tasks": len(linked_papers),
        "cross_suite_linked_neural_tasks": len(linked_neural),
        "relation_counts": dict(sorted(Counter(r["relation"] for r in rows).items())),
        "cross_suite_pairs": [list(p) for p in cross_pairs],
        "papers_without_detected_cross_suite_edge": sorted(paper_ids - linked_papers),
        "neural_tasks_without_detected_cross_suite_edge": sorted(neural_ids - linked_neural),
        "unresolved_catalog_links": unresolved_links,
        "edges": rows,
        "source_pins": {str(p.relative_to(ROOT)): {
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in inputs},
        "limitations": [
            "An edge marks declared reuse or a matching locator/label, not verified participant overlap.",
            "No edge does not mean independent or safe for train/evaluation separation.",
            "Different URLs, DOI forms, source aliases, derivatives and unlabeled stimulus/checkpoint reuse can be missed.",
            "Overlap labels mix study identity and stimulus family; do not use them as a biological equivalence relation.",
            "No graph component count is reported as a number of independent datasets.",
            "No RL train/assessment allocation or source restriction is changed by this audit.",
        ],
    }
    (OUT / "exposure_audit.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# Declared exposure across the 200 candidates", "",
        "This metadata audit makes known reuse visible before any RL or model-evaluation split. "
        "It reads existing rosters and catalogs only; no recording, target or model is accessed.", "",
        f"There are **{len(cross_pairs)} cross-suite task pairs** with at least one explicit catalog link, "
        f"exact locator/label match or reviewed source/stimulus-family alias, involving **{len(linked_papers)} paper projects and "
        f"{len(linked_neural)} neural assignments**. These are task-pair links, not cohort counts.", "",
        "[Machine-readable evidence](exposure_audit.json) records each typed edge and its source pins. "
        "The [relationship audit](../catalog/RELATIONSHIPS.md) explains further known aliases and reuse "
        "that exact matching cannot resolve.", "",
        "| Relation | Evidence edges |", "|---|---:|",
        *[f"| {k.replace('_', ' ')} | {v} |" for k, v in result["relation_counts"].items()], "",
        "Multiple relations can describe one task pair; do not sum these rows as distinct pairs.", "",
        "## Consequence for benchmark and RL splits", "",
        "Before splitting, resolve acquisition/session/participant identity, stimuli, derived inputs and "
        "checkpoint-training exposure separately. Review every proposed split that crosses a listed edge. "
        "Co-group verified shared acquisitions for claims about new biological units; also group stimuli "
        "or methods when the intended generalization claim requires it. A paper can remain a distinct "
        "scientific assignment while sharing neural observations with another task.", "",
        "No-edge tasks remain unresolved. Exact matching misses aliases, different release routes, "
        "derived archives and undocumented reuse. This graph neither certifies independence nor "
        "automatically assigns an RL training/test split. Connected components of mixed relation "
        "types would not have a defensible biological interpretation.", "",
        "Regenerate with `python3 tools/build_neuro_exposure_audit.py`. This operation does not "
        "promote readiness or run a scientific model.", ""]
    (OUT / "EXPOSURE_AUDIT.md").write_text("\n".join(lines))
    print(json.dumps({k: result[k] for k in (
        "candidate_tasks", "typed_evidence_edges", "unique_linked_task_pairs",
        "cross_suite_linked_task_pairs", "cross_suite_linked_paper_tasks",
        "cross_suite_linked_neural_tasks")}))


if __name__ == "__main__":
    main()
