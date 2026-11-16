"""Fixed private-metadata admission; no data, reference values or animal IDs.

The pinned metadata is required externally. A digest proves selected bytes, not
scientific qualification. No alternate digest or relaxed production mode exists.
"""
import hashlib
import json
import re

PINS = {
    "input_ledger": {"bytes": 18075, "sha256": "d2756c791ccdedf22de2ef5e2949b43d804c0232c1aeddcb6ff25411ddaafed1"},
    "published_families": {"bytes": 66285, "sha256": "e6602394041e2a6f448db374ffccbf06856f262e13df468003a901ae4fa2eced"},
    "private_policy": {"bytes": 935, "sha256": "4879ce87b72c06d88a67149c990f876ffca8254bfcfc659229a72e0ebd569ab2"},
}
TABLES = frozenset(("condition_measures.pqt", "condition_contrasts.pqt",
    "multicortical_condition_measures.pqt", "multicortical_condition_contrasts.pqt",
    "cortical_spindle_condition_measures.pqt", "cortical_spindle_state_rates.pqt",
    "dspk_state_rates.pqt", "firing_rates.pqt", "off_durations.pqt",
    "ripple_frequency_by_state.pqt", "AeryJones_sgfg_medians_by_epoch_type.pqt",
    "sleep_period_fractional_occupancy.pqt", "rec_rem_vs_ewk_tdr.pqt"))
COUNTS = {"condition_correlation": 15, "condition_difference_correlation": 24,
    "cortical_spindle": 6, "eta_ext_wake_increase": 1, "firing_rates": 3,
    "first_novelty": 7, "homeostasis": 13,
    "multiregion_condition_difference_correlation": 20, "ripple_freq": 1,
    "sgfg": 1, "state_rate": 2, "fractional_occupancy": 5}
OCCUPANCY = ("baseline_occupancy", "recovery_occupancy", "novelty_occupancy",
             "locomotion_occupancy", "rem_fraction_theta_delta")
IDS = frozenset(f + ":" + str(i) for f, n in COUNTS.items()
    if f != "fractional_occupancy"
    for i in (range(4, 7) if f == "firing_rates" else range(1, n + 1))) | frozenset(
        "fractional_occupancy:" + name for name in OCCUPANCY)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def decode(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "Duplicate private metadata key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite private metadata")))


def text(value):
    return type(value) is str and 0 < len(value) <= 256 and not any(ord(c) < 32 for c in value)


def validate_schema(field, value):
    """Shape checks are separate for invented tests; production also requires exact pins."""
    need(type(value) is dict, "Private metadata object required")
    if field == "input_ledger":
        need(value.get("schema") == "findlay-full-input-contract/v1",
             "Complete input-ledger schema")
        for key, expected in (("member_count", 17), ("parquet_member_count", 13),
                ("static_subjects", 16), ("static_sessions", 29), ("archive_bytes", 3015691)):
            need(type(value.get(key)) is int and value[key] == expected, "Unchanged full input scope")
        members = value.get("members")
        need(type(members) is list and len(members) == 17 and all(type(x) is dict for x in members),
             "All seventeen original members required")
        names = [x.get("path") for x in members]
        need(all(text(n) and "/" not in n and n not in (".", "..") for n in names)
             and len(set(names)) == 17, "Exact unique original member basenames")
        need({n for n in names if n.endswith(".pqt")} == TABLES, "All thirteen original tables")
        for row in members:
            need(type(row.get("bytes")) is int and row["bytes"] > 0, "Positive member extent")
            if row["path"] in TABLES:
                fields = row.get("columns")
                need(type(fields) is list and all(text(x) for x in fields)
                     and len(fields) == len(set(fields)), "Complete distinct table fields")
                need(type(row.get("footer_advertised_rows")) is int
                     and 0 <= row["footer_advertised_rows"] <= 2000000, "Bounded original row count")
                need(type(row.get("footer_sha256")) is str
                     and re.fullmatch("[a-f0-9]{64}", row["footer_sha256"]), "Pinned original footer")
        roster = value.get("static_source_roster")
        need(type(roster) is list and len(roster) == 16
             and all(type(x) is dict and text(x.get("subject"))
                     and type(x.get("protocols")) is list for x in roster), "Complete sixteen-animal roster")
        need(len({x["subject"] for x in roster}) == 16
             and sum(len(x["protocols"]) for x in roster) == 29, "Distinct animals and complete sessions")
    elif field == "published_families":
        need(value.get("schema") == "findlay-published98-exact-family-join/v1"
             and type(value.get("published_families")) is int and value["published_families"] == 98,
             "Complete published-family ledger")
        rows = value.get("rows")
        need(type(rows) is list and len(rows) == 98 and all(type(x) is dict for x in rows),
             "All ninety-eight families")
        ids = [x.get("source_analysis_id") for x in rows]
        need(all(text(x) for x in ids) and len(set(ids)) == 98 and set(ids) == IDS,
             "Exact ninety-eight published identities")
        for row in rows:
            need(type(row.get("source_parameters")) is dict
                 and type(row.get("input_tables")) is list
                 and all(x in TABLES for x in row["input_tables"]), "Family parameter/table contract")
            need(type(row.get("table1_row")) is int, "Published table row provenance")
    elif field == "private_policy":
        need(set(value) == {"schema", "balanced_subjects", "ordinary_exclusion", "provenance"}
             and value["schema"] == "findlay-private-identity-policy/v1", "Exact private identity-policy schema")
        cohort = value["balanced_subjects"]
        need(type(cohort) is list and len(cohort) == 5 and all(text(x) for x in cohort)
             and len(set(cohort)) == 5, "Exactly five balanced identities")
        exclusion = value["ordinary_exclusion"]
        need(type(exclusion) is dict and set(exclusion) == {"subject", "experiment", "columns"}
             and text(exclusion["subject"]) and exclusion["experiment"] == "Novelty",
             "One fixed exclusion identity")
        columns = exclusion["columns"]
        need(type(columns) is list and len(columns) == 13 and all(text(x) for x in columns)
             and len(set(columns)) == 13, "Thirteen distinct source exclusions")
        provenance = value["provenance"]
        need(type(provenance) is dict and set(provenance) == {
            "family_rules_sha256", "ordinary_policy_sha256", "input_ledger_sha256", "family_ledger_sha256"},
             "Complete fixed policy derivation provenance")
        need(provenance["input_ledger_sha256"] == PINS["input_ledger"]["sha256"]
             and provenance["family_ledger_sha256"] == PINS["published_families"]["sha256"],
             "Private metadata ancestry agrees")
        need(provenance["family_rules_sha256"] == "099c182250d5610a4f9aea3c58e9897fae96157eb464c5c24f327eb60a35d2f4"
             and provenance["ordinary_policy_sha256"] == "d9ef897d0387fa3785ea46f94730e886b429a38ca5e589e89e82134fa1725b01",
             "Accepted scientific policy source ancestry")
    else:
        raise ValueError("Unknown private metadata role")
    return value


def authenticate(field, body):
    need(field in PINS and type(body) is bytes, "Fixed private role and bytes")
    pin = PINS[field]
    need(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"],
         "Exact accepted private metadata required; replacements are not admitted")
    return validate_schema(field, decode(body))


def join(metadata):
    need(set(metadata) == set(PINS), "All three external metadata roles required")
    roster = {row["subject"] for row in metadata["input_ledger"]["static_source_roster"]}
    policy = metadata["private_policy"]
    need(set(policy["balanced_subjects"]) <= roster
         and policy["ordinary_exclusion"]["subject"] in roster, "Policy identities belong to full source cohort")
    return metadata

