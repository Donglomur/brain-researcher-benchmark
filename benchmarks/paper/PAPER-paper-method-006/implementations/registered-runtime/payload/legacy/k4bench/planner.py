"""Complete finite incidence expansion; no effects or speculative scientific defaults."""
from .protocol import require, unique, validate_pin, digest
from .admission import resource_contract, scope_inventory

REFERENCES = ("Kilosort4", "IronClust", "MountainSort4", "SpyKING CIRCUS")


def unresolved_plan(catalog):
    """Concrete missing-work inventory, never a runnable manifest or new tasks."""
    obligations = []
    roles = {x["obligation_id"]: x for x in catalog["assessment"]["rows"]}
    for row in catalog["scope"]["panels"]:
        obligations.append({"id": row["obligation_id"], "type": "panel-or-GUI",
                            "output": row["output"], "roles": roles[row["obligation_id"]],
                            "status": "required-unscorable",
                            "missing_scientific_definition": "S07 exact original producer/settings/selections/tolerance",
                            "concrete_producer_implemented": False})
    for row in catalog["scope"]["methods"]:
        obligations.append({"id": row["xml_id"], "type": "method-section", "output": row["title"],
                            "status": "required-unscorable", "obligation": row["obligation"]})
    for row in catalog["supplement"]["obligations"]:
        obligations.append({"id": row["id"], "type": "older-method", "output": row["title"],
                            "known_constraints": row["known_written_constraints"],
                            "missing_scientific_definitions": row["required_source_configuration_evidence"],
                            "concrete_historical_producer_implemented": False,
                            "status": "required-unscorable"})
    for name in ("Table1", "ReportingSummary", "CompleteProducerInputs"):
        obligations.append({"id": name, "type": "additional-mandatory",
                            "status": "required-unscorable"})
    return {"schema": "kilosort4_full_work_inventory_v1", "canonical_count": 1,
            "canonical_id": "PAPER-paper-method-006", "obligations": obligations,
            "job_families": catalog["jobs"]["rows"],
            "current_gates": catalog["current_gate_state"],
            "minimum_complete_core_reference_sorts": 44,
            "I_query_count": None, "I_query_count_reason": "J_I awaits all diagnostic lineage joins",
            "whole_software_complete": False, "scientific_ready": False,
            "native_runs": 0, "provider_runs": 0}


def expand_jobs(admitted, catalog):
    """Expand an authenticated incidence specification without losing any row.

    The exact publication incidence is evidence, not a guessed Cartesian
    product. Six ablations do not imply 36 original sorts until their case
    mapping is admitted. Each instance binds a complete producer recipe.
    """
    cases = unique(admitted["cases"])
    core = {k: c for k, c in cases.items() if c["kind"] != "diagnostic"}
    require(len(core) == 11, "incomplete-core", "three hybrid, six synthetic, two biophysical")
    require(set(admitted["query_ids"]) == set(cases), "unclosed-J_I", "all distinct inputs")
    source = admitted["source_rosters"]
    for name, count in (("drift_roots", 512), ("waveform_roots", 11),
                        ("waveform_trajectories", 597), ("ISI_donors", 1497)):
        require(len(source[name]) == count and len(set(source[name])) == count,
                "incomplete-source-support", name)
    instances = unique(admitted["original_instances"])
    require({r["family"] for r in instances.values()} >=
            {f"G{k:02}" for k in range(1, 14)} | {"G17", "G21", "G22"},
            "missing-original-family", "original producer graph")
    for instance in instances.values():
        require(instance["incidence_evidence_pin"] and instance["producer_profile_pin"],
                "unadmitted-incidence", instance["id"])
        validate_pin(instance["incidence_evidence_pin"])
        validate_pin(instance["producer_profile_pin"])
        resource_contract(instance["resources"])
    require(set(admitted["obligation_incidence"]) == scope_inventory(catalog),
            "scope-loss", "all panel/method/supplement obligations")
    for obligation, ids in admitted["obligation_incidence"].items():
        require(ids and set(ids) <= set(instances), "missing-producer-instance", obligation)
    require(set(admitted["historical_comparator_roster"]) ==
            set(catalog["scope"]["historical_comparators_named"]) | {"Kilosort4"},
            "comparator-roster-conflict", "10-vs-11 must be reconciled, never silently drop")
    require(set(admitted["ablation_incidence"]) == set(catalog["scope"]["six_ablations"]),
            "missing-ablation", "all six original definitions")
    for ablation, ids in admitted["ablation_incidence"].items():
        require(ids and set(ids) <= set(instances), "missing-ablation-instance", ablation)
    jobs = []
    for arm in ("A", "B"):
        for identifier, instance in sorted(instances.items()):
            jobs.append({**instance, "id": f"{arm}-R/{identifier}", "cell": f"{arm}-R",
                         "depends_on": [f"{arm}-R/{x}" for x in instance["depends_on"]],
                         "profile": instance["profile"]})
        for query in sorted(cases):
            jobs.append({"id": f"{arm}-I/{query}", "family": "G19", "cell": f"{arm}-I",
                         "query_id": query, "profile": "I_bijective_full",
                         "fresh_worker": True, "depends_on": [],
                         "candidate_sealed_before_protected_access": True,
                         "configuration_from": admitted["candidate_execution_profile_pins"][arm]})
    for method in REFERENCES:
        require(method in admitted["reference_profile_pins"], "missing-fixed-reference", method)
        validate_pin(admitted["reference_profile_pins"][method])
        for query in sorted(core):
            sort_id = f"reference/{method}/{query}"
            jobs.append({"id": sort_id, "family": "G18", "query_id": query,
                         "profile": "I_bijective_full", "reference": method,
                         "producer_profile_pin": admitted["reference_profile_pins"][method],
                         "depends_on": []})
    # R scoring profiles and I matching are never reused as one another.
    for target in [x for x in jobs if x.get("query_id") in core]:
        for profile, family in (("R_source20", "G14"), ("R_paper40", "G15"),
                                ("I_bijective_full", "G16")):
            for bank in ("R1", "R2"):
                jobs.append({"id": f"score/{target['id']}/{profile}/{bank}",
                             "family": family, "profile": profile, "bank": bank,
                             "query_id": target["query_id"], "depends_on": [target["id"]],
                             "protected": True})
    for arm in ("A", "B"):
        jobs.append({"id": f"{arm}-R/full-composition", "family": "G20",
                     "profile": "R_paper40", "cell": f"{arm}-R",
                     "depends_on": [x["id"] for x in jobs if x.get("cell") == f"{arm}-R"],
                     "requires_all_obligations": True})
    unique(jobs)
    return {"schema": "kilosort4_finite_job_expansion_v1", "jobs": jobs,
            "incidence_digest": digest(admitted), "runnable": False,
            "reason": "Bind each generated job's finite execution/resource/source profile and authenticate full admission before effects",
            "minimum_core_reference_sorts": 44, "candidate_I_sorts": 2 * len(cases),
            "R_original_instances_per_arm": len(instances),
            "logical_costs_include_failures": True, "canonical_count": 1}
