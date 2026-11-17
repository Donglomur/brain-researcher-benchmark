"""Paper-specific release, field-role and unit-coverage contracts.

These checks consume declared metadata. They do not authenticate MAT values,
establish paper-session correspondence or physically isolate a participant.
"""
from collections import Counter
import copy
import re

DATA_COMMIT = "c177cb8fc7afbe74400f882856da8ad2a4bdcdf7"
DATA_DOI = "10.12751/g-node.ejk8kx"
BASE_URL = ("https://gin.g-node.org/doi/"
            "Karamanlis_Gollisch_2023_RGC_spiketrains_natural_movies_and_subunit_models"
            "/raw/" + DATA_COMMIT + "/")
ARCHIVES = (
    "20201112_252MEA_mouse_left_half_dorsal.rar",
    "20201112_252MEA_mouse_right_half_ventral.rar",
    "20201126_252MEA_mouse_left_half_dorsal.rar",
    "20201126_252MEA_mouse_left_half_ventral.rar",
    "20210115_252MEA_mouse_left_half_ventral.rar",
    "20210115_252MEA_mouse_right_half_ventral.rar",
    "20210203_252MEA_mouse_left_half_dorsal.rar",
    "20210203_252MEA_mouse_left_half_ventral.rar",
    "20210803_252MEA_mouse_left_half_dorsal.rar",
    "20210813_252MEA_mouse_left_half_dorsal.rar",
    "20210813_252MEA_mouse_left_half_ventral.rar",
    "20210916_252MEA_mouse_right_half_ventral.rar",
    "20220208_252MEA_marmoset_right_s4.rar",
    "20220208_60MEA_marmoset_right_i1.rar",
    "20220208_60MEA_marmoset_right_n1.rar",
    "20220301_252MEA_marmoset_left_n1.rar",
    "20220301_60MEA_marmoset_left_s1.rar",
    "20220329_60MEA_marmoset_right_i1.rar",
)
CELL_TYPES = (
    "ON parasol", "OFF parasol", "ON midget", "OFF midget",
    "transient-ON alpha", "transient-OFF alpha",
    "sustained-ON alpha", "sustained-OFF alpha",
)
FIG4_CELLS = dict(zip(CELL_TYPES, (41, 34, 37, 53, 18, 43, 88, 76)))
FIG4_PAIRS = dict(zip(CELL_TYPES, (269, 176, 330, 494, 57, 315, 1923, 889)))
METHODS = ("white_noise_ln", "gaussian_ln", "dog_ln", "subunit_grid", "stnmf", "stclus")
DISPOSITIONS = ("eligible", "excluded", "unknown")
METHOD_STATES = ("complete", "fit_failed", "no_eligible_model",
                 "historical_stnmf_omitted", "not_applicable", "unknown")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SAFE_ID = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")


class Refusal(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Refusal(reason)


def closed(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), label + ":schema")


def digest(value, label):
    require(type(value) is str and HEX64.fullmatch(value) is not None, label + ":sha256")
    return value


def positive_int(value, label):
    require(type(value) is int and value > 0, label + ":positive_integer")
    return value


def identifier(value, label, allow_none=False):
    if value is None and allow_none:
        return value
    require(type(value) is str and SAFE_ID.fullmatch(value) is not None, label + ":identifier")
    return value


def validate_release_manifest(value):
    """Require all 18 exact objects; source metadata authority is a separate gate."""
    closed(value, ("schema", "data_doi", "data_commit", "archives"), "release")
    require(value["schema"] == "retina-exact-release-v1", "release:schema_name")
    require(value["data_doi"] == DATA_DOI and value["data_commit"] == DATA_COMMIT,
            "release:identity")
    require(type(value["archives"]) is list and len(value["archives"]) == 18,
            "release:all18")
    seen = {}
    for item in value["archives"]:
        closed(item, ("name", "bytes", "sha256", "metadata_evidence_sha256"), "archive")
        name = item["name"]
        require(type(name) is str and name in ARCHIVES, "archive:not_in_frozen_release")
        require(name not in seen, "archive:duplicate")
        positive_int(item["bytes"], "archive")
        digest(item["sha256"], "archive")
        digest(item["metadata_evidence_sha256"], "archive:metadata_evidence")
        seen[name] = copy.deepcopy(item)
    require(set(seen) == set(ARCHIVES), "release:all18")
    ordered = [seen[name] for name in ARCHIVES]
    total = sum(x["bytes"] for x in ordered)
    return {
        "schema": "retina-acquisition-plan-v1", "data_commit": DATA_COMMIT,
        "archives": [dict(x, url=BASE_URL + x["name"]) for x in ordered],
        "total_archive_bytes": total,
        "maximum_observed_entity_bytes": total + 18,
        "requested_read_admission_bytes": 2 * total + 18 * 1048576,
        "maximum_retained_archive_bytes": total + 18,
        "metadata_authority_verified": False,
        "archive_extraction_selected": False,
        "scientific_qualification": False,
    }


# Exact top-level field roles follow the manual and the pinned flicker demo.
# A whole fixationmovie MAT/rawdata object is never participant material.
FIELD_ROLES = {
    "expdata.mat": {
        "animal": "group_metadata", "array": "group_metadata", "units": "group_metadata",
        "fs": "acquisition_metadata", "projector": "stimulus_metadata",
        "typelabels": "cell_type_metadata", "cellclus_id": "cell_type_metadata",
    },
    "fixationmovie_data.mat": {
        "runningImages": "training_stimulus", "runningfixations": "training_stimulus",
        "runningbin": "training_response",
        "frozenImages": "evaluation_stimulus", "frozenfixations": "evaluation_stimulus",
        "frozenbin": "protected_response",
        "rawdata": "protected_mixed_response",
        "spiketimes": "protected_mixed_response",
        "fonsets": "protected_mixed_timing", "foffsets": "protected_mixed_timing",
        "stimPara": "protected_mixed_metadata", "spikesbin": "protected_mixed_response",
    },
    "gratingflicker_data.mat": {
        "rawdata": "training_gratings", "stiminfo": "training_gratings",
        "stimorder": "training_gratings", "orderfit": "training_gratings",
        "spikesfit": "training_gratings", "ktbas": "training_gratings",
        "spX": "training_gratings", "spY": "training_gratings",
    },
}
SAFE_PARTICIPANT_ROLES = {
    "group_metadata", "acquisition_metadata", "stimulus_metadata",
    "cell_type_metadata", "training_stimulus", "training_response",
    "evaluation_stimulus", "training_gratings",
}


def projection_plan(value):
    """Classify complete declared field inventories without opening a MAT object."""
    closed(value, ("schema", "data_commit", "sessions"), "inventory")
    require(value["schema"] == "retina-field-inventory-v1"
            and value["data_commit"] == DATA_COMMIT, "inventory:identity")
    require(type(value["sessions"]) is list and len(value["sessions"]) == 18,
            "inventory:all18")
    seen = set()
    output, holds = [], []
    for session in value["sessions"]:
        closed(session, ("archive", "complete_member_inventory", "members"), "session")
        name = session["archive"]
        require(name in ARCHIVES and name not in seen, "inventory:archive_identity")
        seen.add(name)
        require(session["complete_member_inventory"] is True, "inventory:incomplete_members")
        require(type(session["members"]) is list, "inventory:members")
        member_names = set()
        for member in session["members"]:
            closed(member, ("name", "sha256", "bytes", "complete_field_inventory", "fields"), "member")
            filename = member["name"]
            require(type(filename) is str and filename and "/" not in filename
                    and "\\" not in filename and filename not in (".", ".."), "member:path")
            require(filename not in member_names, "member:duplicate")
            member_names.add(filename)
            digest(member["sha256"], "member")
            positive_int(member["bytes"], "member")
            require(member["complete_field_inventory"] is True, "member:incomplete_fields")
            require(type(member["fields"]) is list and all(type(x) is str and x for x in member["fields"])
                    and len(member["fields"]) == len(set(member["fields"])), "member:fields")
            if filename.endswith(".txt") or "modelparam" in filename.lower():
                for field in member["fields"] or ["<whole_object>"]:
                    output.append({"archive": name, "member": filename, "field": field,
                                   "role": "protected_fitted_answer", "participant_allowed": False})
                continue
            allowed = FIELD_ROLES.get(filename, {})
            if not member["fields"]:
                holds.append(name + ":" + filename + ":empty_field_inventory")
            for field in member["fields"]:
                role = allowed.get(field, "unmapped")
                output.append({"archive": name, "member": filename, "field": field, "role": role,
                               "participant_allowed": role in SAFE_PARTICIPANT_ROLES})
                if role == "unmapped":
                    holds.append(name + ":" + filename + ":" + field)
        for expected in ("expdata.mat", "fixationmovie_data.mat", "gratingflicker_data.mat"):
            if expected not in member_names:
                holds.append(name + ":" + expected + ":absent")
    return {
        "schema": "retina-projection-plan-v1", "rows": output, "holds": holds,
        "participant_materialization_ready": False,
        "physical_isolation_verified": False,
        "reason": "Declared fields only; exact RAR/MAT decoder, full field census and split provenance remain unbound.",
        "test_range_normalization_role": "protected_scorer_only",
        "historical_test_reliability_role": "protected_scorer_only",
        "scientific_qualification": False,
    }


def coverage_ledger(value):
    """Retain every declared unit and method failure; do not infer source identities."""
    closed(value, ("schema", "data_commit", "sessions"), "coverage")
    require(value["schema"] == "retina-unit-coverage-v1"
            and value["data_commit"] == DATA_COMMIT, "coverage:identity")
    require(type(value["sessions"]) is list and len(value["sessions"]) == 18, "coverage:all18")
    seen = set()
    fig4 = Counter()
    states = {method: Counter() for method in METHODS}
    counts = Counter()
    unresolved = []
    for session in value["sessions"]:
        closed(session, ("archive", "animal_id", "piece_id", "identity_evidence_sha256",
                         "source_unit_count", "units"), "coverage:session")
        name = session["archive"]
        require(name in ARCHIVES and name not in seen, "coverage:archive")
        seen.add(name)
        identifier(session["animal_id"], "animal", True)
        identifier(session["piece_id"], "piece", True)
        if session["animal_id"] is None or session["piece_id"] is None or session["identity_evidence_sha256"] is None:
            unresolved.append(name + ":animal_piece_lineage")
        else:
            digest(session["identity_evidence_sha256"], "identity_evidence")
        require(type(session["source_unit_count"]) is int and session["source_unit_count"] >= 0,
                "coverage:unit_count")
        require(type(session["units"]) is list and len(session["units"]) == session["source_unit_count"],
                "coverage:unit_omission")
        units = set()
        for unit in session["units"]:
            closed(unit, ("unit_id", "cell_type", "fig4_disposition", "fig4_reason",
                          "eligibility_evidence_sha256", "methods"), "unit")
            identifier(unit["unit_id"], "unit")
            require(unit["unit_id"] not in units, "unit:duplicate")
            units.add(unit["unit_id"])
            require(unit["cell_type"] in CELL_TYPES + ("unclassified",), "unit:cell_type")
            species_types = CELL_TYPES[4:] if "_mouse_" in name else CELL_TYPES[:4]
            require(unit["cell_type"] in species_types + ("unclassified",), "unit:species_cell_type")
            require(unit["fig4_disposition"] in DISPOSITIONS, "unit:disposition")
            require(type(unit["fig4_reason"]) is str and bool(unit["fig4_reason"]), "unit:reason")
            if unit["eligibility_evidence_sha256"] is None:
                unresolved.append(name + ":" + unit["unit_id"] + ":eligibility_lineage")
            else:
                digest(unit["eligibility_evidence_sha256"], "unit:eligibility_evidence")
            counts[unit["fig4_disposition"]] += 1
            if unit["fig4_disposition"] == "eligible":
                require(unit["cell_type"] in CELL_TYPES, "unit:unclassified_fig4")
                fig4[unit["cell_type"]] += 1
            if unit["fig4_disposition"] == "unknown":
                unresolved.append(name + ":" + unit["unit_id"] + ":eligibility_unknown")
            closed(unit["methods"], METHODS, "unit:methods")
            for method in METHODS:
                outcome = unit["methods"][method]
                closed(outcome, ("status", "reason", "scope_evidence_sha256"), "method")
                require(outcome["status"] in METHOD_STATES, "method:status")
                require(type(outcome["reason"]) is str and bool(outcome["reason"]), "method:reason")
                if outcome["scope_evidence_sha256"] is None:
                    unresolved.append(name + ":" + unit["unit_id"] + ":" + method + ":scope_lineage")
                else:
                    digest(outcome["scope_evidence_sha256"], "method:scope_evidence")
                if outcome["status"] == "historical_stnmf_omitted":
                    require(method == "stnmf" and unit["cell_type"] in ("ON parasol", "OFF parasol"),
                            "method:invalid_stnmf_omission")
                if outcome["status"] == "no_eligible_model":
                    require(method == "subunit_grid", "method:invalid_sg_exclusion")
                states[method][outcome["status"]] += 1
    observed = {t: fig4[t] for t in CELL_TYPES}
    return {
        "schema": "retina-complete-declared-coverage-v1",
        "release_sessions": 18, "source_units": sum(counts.values()),
        "eligibility_counts": dict(counts), "fig4_observed_cells": observed,
        "fig4_expected_cells": dict(FIG4_CELLS),
        "fig4_cell_count_match": observed == FIG4_CELLS,
        "fig4_expected_pairs": dict(FIG4_PAIRS), "pair_lineage_verified": False,
        "all_method_status_counts": {m: dict(c) for m, c in states.items()},
        "unresolved": unresolved,
        "source_unit_census_authenticated": False,
        "historical_cohort_verified": False,
        "scientific_qualification": False,
        "note": "Counts reconcile declarations only; matching 390 cannot establish animal/session, pair or numerical provenance.",
    }
