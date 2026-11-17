"""Complete remaining support/contrast census from exact retained original inputs.

No acquisition, fits, row exclusions, or changes to the accepted family semantics.
The lost accumulators are recomputed, never inferred from aggregate receipt claims.
"""
from pathlib import Path
import json


def need(ok, why):
    if not ok:
        raise ValueError(why)


def comparable(report):
    # These are serialization/read-cost and separately retained roster annotations.
    # Every scientific scalar, complete typed group, identity and authentication
    # field remains in the exact equality comparison.
    value = {k: v for k, v in report.items() if k not in (
        "managed_read_bytes", "static_roster_comparison", "group_parts", "group_count")}
    # The original writer encoded Python tuples as JSON arrays. Compare exactly
    # in that representation; do not mistake the container type change for drift.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def resume_tail(members_root, ledger, family_ledger, budget, prior_tables, *,
                census_module, rules_module, ordinary_module, ordinary_policy, parquet_factory=None):
    budget.check()
    tables = tuple(census_module.TABLES)
    need(set(prior_tables) == set(tables) and len(prior_tables) == 13,
         "Complete thirteen independently accepted original table reports")
    members = {m["path"]: m for m in ledger["members"] if m["path"].endswith(".pqt")}
    need(set(members) == set(tables), "Complete original thirteen-table ledger")
    for name, item in prior_tables.items():
        report = item["report"]
        need(report["table"] == name and report["all_decoded_rows_accounted"] is True
             and report["rows"] == members[name]["footer_advertised_rows"]
             and report["group_rows_total"] == report["rows"],
             "Original complete table census matches pinned footer and groups")
    book = rules_module.build_rules(family_ledger, ledger)
    need(len(book.ids) == len(set(book.ids)) == 98, "Exact all98 family rule book")
    accumulators = {identifier: book.new_accumulator(identifier) for identifier in book.ids}
    table_accumulators = {name: [accumulators[identifier] for identifier in book.ids
                                if name in book.tables_for(identifier)] for name in tables}
    # This static union is determined before observing any new row values.
    required = set(census_module.SMALL) | {
        name for identifier in book.ids for name in book.tables_for(identifier)}
    need(required <= set(tables), "Remaining source computation uses only original tables")
    retained = {}
    schemas = {}
    replayed = []
    for name in sorted(required):
        report, rows = census_module._table_census(
            Path(members_root), members[name], budget,
            parquet_factory or census_module._default_parquet, table_accumulators[name])
        need(comparable(report) == comparable(prior_tables[name]["report"]),
             "Complete replayed table/group/value census equals independently accepted original")
        replayed.append({"table": name, "rows": report["rows"],
                         "managed_read_bytes": report["managed_read_bytes"],
                         "original_report": prior_tables[name]["pin"]})
        if name in census_module.SMALL:
            retained[name] = rows
            schemas[name] = report["schema"]
    family_reports = []
    for identifier in book.ids:
        budget.check()
        support = accumulators[identifier].finish()
        need(support["census_rows_complete"] is True,
             "Every declared table row accounted in every family")
        family_reports.append({"id": identifier, "schema_assessment": book.assess_schema(identifier),
                               "support": support})
    families = budget.write_json("family-support-98.private.json", {
        "families": family_reports, "families_accounted": 98,
        "scope": "Complete eligibility/support census, no statistical fits or inferential results"})
    definitions = getattr(rules_module, "EXPORTED_CONTRAST_DEFINITIONS", {})
    gates = [{"scope": name, "gate": gate} for name in tables
             for gate in prior_tables[name]["report"]["readiness_gates"]]
    contrasts = []
    for prefix, keys in (("condition", ("subject", "experiment")),
                         ("multicortical_condition", ("subject", "experiment", "acronym", "spw_probe", "region"))):
        if prefix == "condition":
            result = ordinary_module.reconcile(
                retained["condition_measures.pqt"], retained["condition_contrasts.pqt"],
                schemas["condition_measures.pqt"], schemas["condition_contrasts.pqt"],
                policy=ordinary_policy)
        else:
            result = census_module.reconcile_contrasts(
                retained[prefix + "_measures.pqt"], retained[prefix + "_contrasts.pqt"],
                keys, definitions.get(prefix, {}))
        contrasts.append(budget.write_json(prefix + "-reconstruction.private.json", result))
        if not result["all_target_cells_reconciled"]:
            gates.append({"scope": prefix, "gate": "contrast_reconstruction_not_fully_reconciled"})
    gates.extend({"scope": "published_support", "gate": gate} for gate in (
        "29_static_sessions_vs_endpoint_specific_23_28_requires_actual_family_join",
        "68_regional_contrast_rows_vs_64_caption_requires_actual_family_join",
        "SGFG_factor_alias_design_matrix_reconciliation_before_fit",
        "stored_normalized_measure_scale_not_assumed_percent"))
    return {"schema": "findlay-complete-intake-census/v1",
            "status": "COMPLETE_INTAKE_CENSUS_WITH_GATES", "table_count": 13, "family_count": 98,
            "decoded_rows": sum(item["report"]["rows"] for item in prior_tables.values()),
            "table_reports": [prior_tables[name]["pin"] for name in sorted(tables)],
            "family_report": families, "contrast_reports": contrasts, "readiness_gates": gates,
            "scientific_ready": False, "models_fitted": 0, "all_tables_and_families_accounted": True,
            "numeric_and_identity_outputs": "operator-only; not candidate input",
            "continuation": {"new_GETs": 0, "previous_whole_status": "REFUSED",
                             "prior_table_reports_reused": 13, "replayed_remaining_tables": replayed,
                             "original_lost_family_serialized_bytes": None,
                             "original_lost_family_serialized_bytes_upper_bound": 2097152}}
