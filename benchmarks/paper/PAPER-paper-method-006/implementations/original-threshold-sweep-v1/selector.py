"""Complete original medium-drift score tables to descriptive threshold choice.

No sorter runs here. Supplied source/grid/profile identities and agreement of
two score tables do not establish authenticity, independent implementations,
publication parity, held-out improvement, or a scientific outcome.
"""
import hashlib
import json
import math


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def identity(value):
    require(isinstance(value, str) and 0 < len(value) <= 1024, "invalid identity")
    return value


def pin(value):
    require(isinstance(value, str) and len(value) == 64
            and all(x in "0123456789abcdef" for x in value), "invalid SHA256")
    return value


def roster(values):
    require(type(values) is list, "roster must be a list")
    result = [identity(value) for value in values]
    require(len(result) == len(set(result)), "duplicate identity")
    return result


def keyed(rows, key):
    require(type(rows) is list and all(type(row) is dict and key in row for row in rows),
            "invalid row collection")
    return dict(zip(roster([row[key] for row in rows]), rows))


def score(value):
    require(type(value) in (int, float) and -1 <= value <= 1 and math.isfinite(value),
            "score must be a finite nonboolean scalar in [-1,1]")
    return float(value)


def select_sweep(manifest, exports, *, max_score_rows):
    """Require all 600 targets at every frozen threshold in both supplied banks.

    The caller selects a finite logical row budget before reading score tables.
    Exceeding it refuses; it never shrinks the declared grid or target support.
    Actual file, memory, execution and provenance admission remain external.
    """
    require(type(manifest) is dict and type(exports) is dict, "documents must be objects")
    require(manifest.get("schema") == "kilosort4_original_threshold_sweep_inputs_v1", "manifest schema")
    require(manifest.get("purpose") == "historical_medium_drift_reconstruction",
            "historical tuning only; not held-out improvement")
    require(manifest.get("case_id") == "medium_drift", "original medium-drift case required")
    require(manifest.get("scoring_profile") == "R_paper40", "publication profile required")
    for field in ("source_input_sha256", "scoring_policy_sha256", "grid_provenance_sha256"):
        pin(manifest[field])
    targets = roster(manifest["target_unit_ids"])
    require(len(targets) == 600, "all 600 original single-unit targets required")
    settings = keyed(manifest["thresholds"], "threshold_id")
    require(settings, "complete nonempty declared threshold grid required")
    for row in settings.values():
        pin(row["parameter_setting_sha256"])
    tie_policy = manifest["tie_policy"]
    require(tie_policy in {"first-declared", "last-declared", "unavailable"}, "unresolved tie policy")
    require(type(max_score_rows) is int and max_score_rows > 0, "invalid logical row budget")
    required_rows = 2 * len(settings) * len(targets)
    require(required_rows <= max_score_rows, "complete sweep exceeds logical row budget")
    require(exports.get("schema") == "kilosort4_original_threshold_sweep_exports_v1", "export schema")
    require(exports.get("manifest_sha256") == digest(manifest), "manifest identity mismatch")
    banks = keyed(exports["banks"], "bank_id")
    require(len(banks) == 2, "exactly two distinct supplied score banks required")
    values = {}
    for bank_id, bank in banks.items():
        pin(bank["implementation_sha256"])
        threshold_rows = keyed(bank["thresholds"], "threshold_id")
        require(set(threshold_rows) == set(settings), "complete threshold grid required in each bank")
        values[bank_id] = {}
        for threshold_id, setting in settings.items():
            table = threshold_rows[threshold_id]
            for field in ("source_input_sha256", "scoring_policy_sha256"):
                require(table.get(field) == manifest[field], "score source/profile substitution")
            require(table.get("parameter_setting_sha256") == setting["parameter_setting_sha256"],
                    "threshold parameter substitution")
            units = keyed(table["units"], "unit_id")
            require(set(units) == set(targets), "complete unchanged target support required")
            for unit in units.values():
                require(unit.get("role") == "single-unit-target", "background MUA is not a target")
            values[bank_id][threshold_id] = [score(units[unit]["score"]) for unit in targets]
    first, second = list(banks)
    for threshold_id in settings:
        require(values[first][threshold_id] == values[second][threshold_id],
                "score banks disagree per target; equal counts alone are insufficient")
    counts = {key: sum(value > 0.8 for value in values[first][key]) for key in settings}
    best = max(counts.values())
    ties = [key for key in settings if counts[key] == best]
    require(len(ties) == 1 or tie_policy != "unavailable", "historical threshold tie unresolved")
    selected = ties[-1] if tie_policy == "last-declared" else ties[0]
    return {
        "schema": "kilosort4_original_threshold_sweep_report_v1",
        "manifest_sha256": digest(manifest), "exports_sha256": digest(exports),
        "case_id": "medium_drift", "scoring_profile": "R_paper40",
        "target_count": 600, "target_roster_sha256": digest(targets),
        "declared_threshold_order": list(settings),
        "counts": [{"threshold_id": key, "correctly_identified": counts[key],
                    "parameter_setting_sha256": settings[key]["parameter_setting_sha256"]}
                   for key in settings],
        "selected_threshold_id": selected, "all_ties": ties, "tie_policy": tie_policy,
        "recovery_rule": "binary64 score > binary64(0.8)",
        "supplied_bank_ids": list(banks), "per_target_score_values_agree": True,
        "bank_implementation_identities": {key: banks[key]["implementation_sha256"] for key in banks},
        "logical_score_rows": required_rows,
        "historical_equivalence": False, "independent_bank_authorship_verified": False,
        "source_authenticity_verified": False, "held_out_improvement_evidence": False,
        "paper_reproduction_decision": None, "paper_improvement_decision": None,
        "limits": [
            "The historical complete grid, sorter/wrapper versions, parameter bodies and invocation remain externally unresolved.",
            "Hashes bind supplied identities; two agreeing tables do not prove authentic or independent computation.",
            "R_paper40 is a declared upstream policy, not authentication of its unresolved event/geometry/quality semantics.",
            "Medium-drift threshold selection is historical tuning; these same scores cannot establish held-out improvement.",
            "No other simulation, original companion, full-paper obligation or execution prerequisite is closed here.",
        ],
    }
