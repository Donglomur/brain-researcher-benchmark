"""Metadata validation for a FUTURE separately inspected complete source release.

This module does not inspect/download/hash authentic data, resolve private IDs,
or infer header contents. A successful schema check is not independent admission.
"""
from .strict import need, sha, digest, natural, text
from .programme import CONFIGS, validate_contract
from .splits import validate_rows
from .units import require_hz


def validate_admission(manifest, contract):
    validate_contract(contract)
    need(type(manifest) is dict and set(manifest) == {"schema", "programme_digest", "source_files", "members", "cases", "rows", "evidence"}
         and manifest["schema"] == "paper020_original_full_admission_v1"
         and manifest["programme_digest"] == digest(contract), "admission", "Source-bound full admission manifest required")
    roles = {x["member"]: x for x in contract["source_roles"]}
    need(type(manifest["source_files"]) is dict
         and set(manifest["source_files"]) == set(contract["source_release"]["regular_files"]),
         "source", "All 43 original file identities required")
    for path, facts in manifest["source_files"].items():
        need(type(facts) is dict and set(facts) == {"bytes", "sha256"}
             and type(facts["bytes"]) is int and facts["bytes"] == contract["source_release"]["regular_files"][path],
             "source", "Complete original member size required")
        sha(facts["sha256"])
    need(type(manifest["members"]) is dict and set(manifest["members"]) == set(roles),
         "coverage", "All thirty original MAT members, including ancillary screening, required")
    for member, facts in manifest["members"].items():
        need(type(facts) is dict and set(facts) == {"bytes", "sha256", "observed_fields", "header_receipt"},
             "admission", "Exact observed member evidence required")
        need(facts["bytes"] == roles[member]["declared_bytes"] and type(facts["bytes"]) is int,
             "source", "Original archive member byte count changed")
        sha(facts["sha256"]); sha(facts["header_receipt"])
        need(facts["sha256"] == manifest["source_files"][member]["sha256"], "source", "Header/full-member custody differs")
        need(type(facts["observed_fields"]) is list and facts["observed_fields"]
             and len(set(facts["observed_fields"])) == len(facts["observed_fields"]),
             "admission", "Actual inspected top-level field roster required")
        for field in facts["observed_fields"]: text(field, "observed field")
    cases = manifest["cases"]
    need(type(cases) is dict and set(cases) == set(CONFIGS), "coverage", "All fourteen exact source configurations required")
    from .reproduction import build_windows
    for case, header in cases.items():
        need(type(header) is dict and set(header) == {"source_rows", "cell_ids", "feature_ids", "feature_groups", "times_ms",
            "static_bins", "time_bins", "trial_fields", "axis_mapping_receipt", "identity_join_receipt", "inclusion_receipt",
            "clock_units_receipt", "feature_semantics_receipt", "ancillary_rows", "response_units"}, "admission", "Complete inspected case header required")
        require_hz(header["response_units"])
        base = 1036 if CONFIGS[case][2] == 2 else 1080
        natural(header["source_rows"], "native source row count")
        need(header["source_rows"] >= base and header["ancillary_rows"] == list(range(base, header["source_rows"])),
             "coverage", "Every extra native row requires explicit retained ancillary status")
        need(type(header["cell_ids"]) is list and header["cell_ids"] and len(set(header["cell_ids"])) == len(header["cell_ids"]),
             "identity", "All observed cells require unique admitted identities")
        for cell in header["cell_ids"]: text(cell, "cell ID")
        need(type(header["feature_ids"]) is list and len(header["feature_ids"]) == len(set(header["feature_ids"])) == 20
             and header["feature_groups"] == ["shape"]*10+["appearance"]*10, "features", "Twenty semantic source coordinates required")
        for feature in header["feature_ids"]: text(feature, "feature ID")
        for field in ("axis_mapping_receipt", "identity_join_receipt", "inclusion_receipt", "clock_units_receipt", "feature_semantics_receipt"):
            sha(header[field])
        need(type(header["trial_fields"]) is list and len(set(header["trial_fields"])) == len(header["trial_fields"]),
             "admission", "Observed optional trial-field availability must be explicit")
        for mode, key in (("static", "static_bins"), ("time_course", "time_bins")):
            plan = build_windows(header["times_ms"], mode)
            need(header[key] == [list(x) for x in plan.indices], "window", "Original complete native window membership changed")
    validate_rows(manifest["rows"], contract["configurations"])
    evidence = {"archive_identity", "feature_row_identity_join", "individual_pooled_cell_join", "published_roster_discrepancy",
                "source_visually_responsive_inclusion", "native_sampling_and_environment", "native_solver_and_undefined_states",
                "independent_reference_agreement", "whole_programme_memory_time_profile", "isolation_and_original_clock_closure"}
    need(type(manifest["evidence"]) is dict and set(manifest["evidence"]) == evidence,
         "admission", "Every unresolved source/roster/parity/exposure gate requires independent evidence")
    for value in manifest["evidence"].values(): sha(value)
    # Receipts are references, not self-attesting proof. Operator verification
    # checks their actual independent provenance and scientific conclusions.
    return {"admission_digest": digest(manifest), "schema_consistent": True,
            "scientific_qualification_claim": False}
