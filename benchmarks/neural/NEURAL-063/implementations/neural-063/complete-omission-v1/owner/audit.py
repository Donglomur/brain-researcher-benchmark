"""Concrete final evidence bindings and resource inventory from signed producers.

No scientific review is synthesized here. The external reviewer must identify
which actual frozen outputs substantiate each finding. Counter classes remain
separate to avoid adding a trusted parent's usage to its nested child usage.
"""
from __future__ import annotations

import hashlib
from .io import Artifact, ContractError, canonical
from .scoring import number


OBLIGATION_STAGES = {
    "source_native_correspondence": {"S00", "S01", "S02", "S03"},
    "original_support": {"S04", "S05", "S06"},
    "reference_reconstruction": {"R03", "RC00", "R06"},
    "actual_isolation": {"D00", "D01", "Q00", "Q01", "Q02", "Q03", "N00"},
    "immutable_capture": {"Q02", "Q03", "N00", "E00"},
    "all_resources_failures": set(),  # populated with the complete ancestor set
    "interpretation_limits": {"N00", "E01"},
}


def ancestor_inventory(ctx):
    expected = ctx.contract["ancestors"][ctx.stage]
    if set(ctx.prerequisites) != expected or set(ctx.receipt_refs) != expected:
        raise ContractError("complete authenticated ancestor receipt inventory required")
    by_stage = {}
    available = {}
    for stage in ctx.contract["order"]:
        if stage not in expected:
            continue
        content = ctx.prerequisites[stage]
        receipt = Artifact.parse(ctx.receipt_refs[stage])
        if receipt.producer != stage or receipt.role != "signed_stage_completion" or content.get("stage") != stage:
            raise ContractError("ancestor completion identity mismatch")
        usage = content.get("worker_usage")
        if not isinstance(usage, dict) or not usage:
            raise ContractError("actual trusted worker usage absent: " + stage)
        wall = number(content.get("wall_seconds"))
        if wall < 0:
            raise ContractError("negative measured stage duration")
        artifacts = {key: Artifact.parse(value).object() for key, value in content["artifacts"].items()}
        if any(d["producer"] != stage for d in artifacts.values()):
            raise ContractError("ancestor produced output attributed to another stage")
        for value in [receipt.object(), *artifacts.values()]:
            available[hashlib.sha256(canonical(value)).hexdigest()] = value
        by_stage[stage] = {
            "receipt": receipt.object(), "outcome": content["outcome"],
            "entry_evidence": content.get("entry_evidence"),
            "input_descriptors": content.get("input_descriptors"),
            "parameters_sha256": content.get("parameters_sha256"),
            "failure": content.get("failure"), "reasons": content.get("reasons", []),
            "wall_seconds": wall, "worker_usage": usage,
            "runtime_parent_cleanup": content.get("runtime_parent_cleanup"),
            "retained_outputs": content.get("retained_outputs"),
            "proof_read_bytes": content.get("proof_read_bytes"),
            "journal_usage_before_receipt": content.get("journal_usage_before_receipt"),
            "artifacts": artifacts,
        }
    inventory = {"schema": "neural063_authenticated_ancestor_inventory_v1", "attempt": ctx.attempt,
                 "stages": by_stage,
                 "counter_policy": "Retain all parent and nested counters. Do not sum overlapping CPU/RSS/wall classes; logical byte accounting is distinct from unmeasured physical OS I/O.",
                 "physical_os_io_bytes": None}
    return inventory, hashlib.sha256(canonical(inventory)).hexdigest(), available


def review_findings(scientific, *, ctx, inventory_hash, available):
    if (scientific.get("schema") != "neural063_independent_scientific_review_v1" or
            scientific.get("attempt") != ctx.attempt or
            scientific.get("paired_report_sha256") != ctx.inputs["paired_report"].sha256 or
            scientific.get("ancestor_inventory_sha256") != inventory_hash):
        raise ContractError("independent scientific review must bind actual complete attempt inventory")
    reviewer = scientific.get("reviewer")
    if (not isinstance(reviewer, dict) or set(reviewer) != {"identity", "independence_declaration"} or
            any(not isinstance(v, str) or not v.strip() for v in reviewer.values())):
        raise ContractError("external reviewer identity and explicit independence declaration required")
    obligations = scientific.get("obligations")
    if not isinstance(obligations, dict) or set(obligations) != set(OBLIGATION_STAGES):
        raise ContractError("complete original independent scientific obligations required")
    outstanding = []
    for name, finding in obligations.items():
        if (not isinstance(finding, dict) or set(finding) != {"disposition", "reasoning", "evidence"} or
                finding["disposition"] not in {"verified", "open", "failed"} or
                not isinstance(finding["reasoning"], str) or not finding["reasoning"].strip() or
                not isinstance(finding["evidence"], list) or not finding["evidence"]):
            raise ContractError("each finding needs explicit reasoning and exact actual evidence")
        stages, seen = set(), set()
        for raw in finding["evidence"]:
            ref = Artifact.parse(raw).object()
            key = hashlib.sha256(canonical(ref)).hexdigest()
            if key in seen or available.get(key) != ref:
                raise ContractError("scientific finding points to duplicate or unbound evidence")
            seen.add(key); stages.add(ref["producer"])
        needed = set(ctx.prerequisites) if name == "all_resources_failures" else OBLIGATION_STAGES[name]
        if not needed <= stages:
            raise ContractError("finding omits required actual producer evidence: " + name)
        if finding["disposition"] != "verified":
            outstanding.append(name)
    return outstanding


def source_bytes(ctx, census):
    """Derive full native-byte total from both actual HEAD and body inventories."""
    sizes = ctx.read_input("source_sizes", roles={"source_sizes"}, cap=16_000_000)
    source = ctx.read_input("source_inventory", roles={"source_inventory"}, cap=16_000_000)
    if (sizes.get("schema") != "neural063_source_sizes_v2" or
            source.get("schema") != "neural063_source_inventory_v2" or
            source.get("source_sizes_sha256") != ctx.inputs["source_sizes"].sha256 or
            source.get("source_selection_sha256") != sizes.get("source_selection_sha256")):
        raise ContractError("authenticated source size/body provenance binding mismatch")
    entries, files = sizes.get("entries"), source.get("files")
    if not isinstance(entries, list) or not isinstance(files, list) or len(entries) != 1936 or len(files) != 1936:
        raise ContractError("all 1936 original native source sizes and bodies required")
    by_id = {}
    for entry in entries:
        key = entry.get("experiment")
        if (not isinstance(key, str) or not key.isdecimal() or key in by_id or
                type(entry.get("bytes")) is not int or entry["bytes"] <= 0):
            raise ContractError("unique exact experiment identity and positive measured size required")
        by_id[key] = entry
    seen = set()
    for entry in files:
        key = entry.get("experiment")
        if key not in by_id or key in seen:
            raise ContractError("native body identity is absent or duplicated")
        seen.add(key)
        descriptor = Artifact.parse(entry.get("source"))
        expected = by_id[key]
        if (descriptor.role != "native_source" or descriptor.visibility != "operator" or
                descriptor.bytes != expected["bytes"] or entry.get("version_id") != expected.get("version_id") or
                entry.get("blake2b_512") != expected.get("blake2b_512") or
                entry.get("disposition") not in {"authenticated_existing", "acquired_authenticated"}):
            raise ContractError("actual acquired native source differs from selected measured version/size")
    total = sum(x["bytes"] for x in entries)
    if sizes.get("total_bytes") != total or source.get("total_bytes") != total:
        raise ContractError("full native source byte totals do not reconcile")
    # Every census experiment is resolved by preparation. Preserve its full
    # identities in operator output; public candidate projections never see them.
    census_ids = [x.get("experiment") for x in census.get("experiments", [])]
    if set(census_ids) != set(by_id) or len(census_ids) != len(set(census_ids)):
        raise ContractError("whole native inventory and support census identity sets differ")
    return {"bytes": total, "files": 1936,
            "source_sizes_sha256": ctx.inputs["source_sizes"].sha256,
            "source_inventory_sha256": ctx.inputs["source_inventory"].sha256,
            "basis": "actual authenticated complete source size and body inventories; no guessed total"}
