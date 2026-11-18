"""Literal optogenetic linear-classification summaries, not a paper scorer.

This consumes supplied derived row statistics; it does not establish that they
were derived from original trajectories. A separately frozen operator roster
binds row identities. Neither that binding nor these calculations authenticate
the original source tables or establish reproduction/improvement.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math

REVISION = "7a6ecc2bbf8f1e1fbca3b769a0db53299ee8171c"
BRANCHES = ("opto_first", "opto_later")
ROW_META = {"id", "branch", "row1", "mouse", "opto_on"}
ROW_FIELDS = ROW_META | {"slope_cm_per_lap", "p_value"}
CLASSES = ("backward", "forward", "nonsignificant", "unclassified")


def _keys(value, expected, description):
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{description}: unexpected fields")


def _identifier(value, description):
    if (not isinstance(value, str) or not value or len(value) > 256
            or any(ord(c) < 32 for c in value)):
        raise ValueError(f"{description}: invalid identifier")
    return value


def _number(value, description, *, probability=False):
    # JSON null explicitly represents a missing source statistic. Never treat
    # arbitrary invalid numbers as source missingness.
    if value is None:
        return None
    if type(value) not in (int, float):
        raise ValueError(f"{description}: expected finite number or null")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{description}: unsupported number") from exc
    if not math.isfinite(result) or (probability and not 0 <= result <= 1):
        raise ValueError(f"{description}: invalid numeric range")
    return result


def classify(slope, p_value):
    """Preserve the source's inclusive .05 threshold and residual category."""
    slope = _number(slope, "slope")
    p_value = _number(p_value, "p_value", probability=True)
    if p_value is None:
        return "unclassified"
    if p_value > 0.05:
        # The author mask tests p alone in this branch, even if slope is NaN.
        return "nonsignificant"
    if slope is not None and slope < 0:
        return "backward"
    if slope is not None and slope > 0:
        return "forward"
    return "unclassified"


def _ratio(numerator, denominator):
    return None if denominator == 0 else numerator / denominator


def _group(rows, *, denominator_kind):
    if denominator_kind not in ("all_source_rows", "classified_rows"):
        raise ValueError("unknown denominator")
    labels = [(row["id"], classify(row["slope_cm_per_lap"], row["p_value"]))
              for row in rows]
    observed = Counter(label for _, label in labels)
    counts = {label: observed[label] for label in CLASSES}
    classified = len(rows) - counts["unclassified"]
    denominator = len(rows) if denominator_kind == "all_source_rows" else classified
    p_only = sum(row["p_value"] is not None and row["p_value"] <= 0.05 for row in rows)
    return {
        "row_ids": [row["id"] for row in rows],
        "source_row_count": len(rows),
        "classified_row_count": classified,
        "counts": counts,
        "denominator_kind": denominator_kind,
        "denominator": denominator,
        "fractions": {label: _ratio(counts[label], denominator)
                      for label in CLASSES[:-1]},
        "directional_shifting_fraction": _ratio(counts["backward"] + counts["forward"], denominator),
        "p_only_shifting_count": p_only,
        "p_only_shifting_fraction_all_rows": _ratio(p_only, len(rows)),
        "unclassified_row_ids": [identity for identity, label in labels if label == "unclassified"],
        "undefined_p_row_ids": [row["id"] for row in rows if row["p_value"] is None],
        "undefined_slope_row_ids": [row["id"] for row in rows if row["slope_cm_per_lap"] is None],
        "fraction_status": "undefined_empty_denominator" if denominator == 0 else "defined",
    }


def _difference(opto, control):
    return None if opto is None or control is None else opto - control


def _contrast(control, opto):
    return {
        "orientation": "opto_minus_control",
        "fractions": {label: _difference(opto["fractions"][label], control["fractions"][label])
                      for label in CLASSES[:-1]},
        "directional_shifting_fraction": _difference(opto["directional_shifting_fraction"],
                                                     control["directional_shifting_fraction"]),
        "p_only_shifting_fraction_all_rows": _difference(opto["p_only_shifting_fraction_all_rows"],
                                                         control["p_only_shifting_fraction_all_rows"]),
    }


def _admit_roster(roster):
    _keys(roster, {"schema", "source_revision", "mice", "rows"}, "roster")
    if roster["schema"] != "find013-opto-derived-roster/v1" or roster["source_revision"] != REVISION:
        raise ValueError("roster schema/revision mismatch")
    mice = roster["mice"]
    if (not isinstance(mice, list) or len(mice) != 9
            or any(not isinstance(v, str) for v in mice) or len(set(mice)) != 9):
        raise ValueError("roster must declare all nine distinct source mice")
    for mouse in mice:
        _identifier(mouse, "mouse")
    entries = roster["rows"]
    if not isinstance(entries, list) or not entries or len(entries) > 100000:
        raise ValueError("invalid row roster")
    counters = Counter()
    used_mice = set()
    seen = set()
    prior_branch = 0
    for entry in entries:
        _keys(entry, ROW_META, "roster row")
        branch = entry["branch"]
        if branch not in BRANCHES:
            raise ValueError("unknown optogenetic timing branch")
        branch_index = BRANCHES.index(branch)
        if branch_index < prior_branch:
            raise ValueError("source pooling order must be first then later")
        prior_branch = branch_index
        counters[branch] += 1
        if type(entry["row1"]) is not int or entry["row1"] != counters[branch]:
            raise ValueError("branch row coordinates must be complete and ordered")
        if entry["id"] != f"{branch}/{entry['row1']}":
            raise ValueError("row ID differs from branch coordinate")
        if entry["id"] in seen:
            raise ValueError("duplicate row identity")
        seen.add(entry["id"])
        if entry["mouse"] not in mice:
            raise ValueError("mouse not in the operator roster")
        used_mice.add(entry["mouse"])
        if type(entry["opto_on"]) is not int or entry["opto_on"] not in (0, 1):
            raise ValueError("Opto_ON must be exactly integer zero or one")
    if set(counters) != set(BRANCHES) or used_mice != set(mice):
        raise ValueError("both timing branches and all nine mice are required")
    return entries


def summarize(rows, roster):
    """Join to an operator-owned complete roster and return literal summaries.

    The caller must authenticate and freeze the roster independently. Supplying
    a self-consistent replacement roster is not proof of original completeness.
    """
    entries = _admit_roster(roster)
    if not isinstance(rows, list) or len(rows) != len(entries):
        raise ValueError("derived rows must cover the complete operator roster")
    by_id = {}
    for row in rows:
        _keys(row, ROW_FIELDS, "derived row")
        identity = _identifier(row["id"], "row ID")
        if identity in by_id:
            raise ValueError("duplicate derived row")
        _number(row["slope_cm_per_lap"], "slope")
        _number(row["p_value"], "p_value", probability=True)
        by_id[identity] = row
    ordered = []
    for expected in entries:
        row = by_id.get(expected["id"])
        if row is None or any(type(row[key]) is not type(expected[key]) or row[key] != expected[key]
                              for key in ROW_META):
            raise ValueError("derived row identity/condition/mouse differs from operator roster")
        ordered.append(row)

    def conditions(subset, denominator_kind):
        control = _group([r for r in subset if r["opto_on"] == 0], denominator_kind=denominator_kind)
        opto = _group([r for r in subset if r["opto_on"] == 1], denominator_kind=denominator_kind)
        return {"control": control, "opto": opto, "contrast": _contrast(control, opto)}

    pooled = conditions(ordered, "all_source_rows")
    mice = [{"mouse": mouse, **conditions([r for r in ordered if r["mouse"] == mouse], "classified_rows")}
            for mouse in roster["mice"]]
    classifications = [{"id": r["id"], "branch": r["branch"], "mouse": r["mouse"],
                        "opto_on": r["opto_on"],
                        "class": classify(r["slope_cm_per_lap"], r["p_value"])} for r in ordered]
    return {
        "schema": "find013-opto-linear-aggregation/v1",
        "source_revision": REVISION,
        "row_count": len(ordered),
        "branch_row_counts": dict(Counter(r["branch"] for r in ordered)),
        "mouse_order": list(roster["mice"]),
        "classifications": classifications,
        "pooled": pooled,
        "per_mouse": mice,
        "source_table_authentication": "required_separately",
        "trajectory_to_statistic_derivation": "not_verified",
        "scientific_reproduction": "unknown",
        "scientific_improvement": "unknown",
        "inferential_tests": None,
        "readiness_promoted": False,
    }


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _decode(raw):
    def nonfinite(value):
        raise ValueError("nonfinite JSON number: " + value)
    def floating(token):
        value = float(token)
        mantissa = token.lower().split("e", 1)[0]
        if not math.isfinite(value) or (value == 0 and any(c in "123456789" for c in mantissa)):
            raise ValueError("JSON floating overflow/underflow would change classification")
        return value
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=nonfinite,
                      parse_float=floating)


def summarize_bytes(rows_bytes, roster_bytes, expected_roster_sha256):
    """Content binding only; the operator must supply the expected digest."""
    if not isinstance(rows_bytes, bytes) or not isinstance(roster_bytes, bytes):
        raise ValueError("byte inputs required")
    if max(len(rows_bytes), len(roster_bytes)) > 16 * 1024 * 1024:
        raise ValueError("component input byte limit exceeded")
    if (not isinstance(expected_roster_sha256, str) or len(expected_roster_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_roster_sha256)):
        raise ValueError("operator SHA256 required")
    if hashlib.sha256(roster_bytes).hexdigest() != expected_roster_sha256:
        raise ValueError("operator roster digest mismatch")
    result = summarize(_decode(rows_bytes), _decode(roster_bytes))
    result["input_bindings"] = {"roster_sha256": expected_roster_sha256,
                                "derived_rows_sha256": hashlib.sha256(rows_bytes).hexdigest()}
    return result
