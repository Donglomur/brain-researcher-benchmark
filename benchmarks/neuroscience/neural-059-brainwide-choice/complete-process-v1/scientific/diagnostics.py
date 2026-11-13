"""Operator-only finite disruptions; no scientific randomization-test claim.

Only Python's standard library is used. No data paths, native fits or actor tools
are opened. These transforms preserve protected identities and original history.
"""
import copy
import hashlib
import json
import math

STATUS = "source_only_unqualified"
PREFIX = "N059-complete-choice-v1"


def compact(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


class HashRNG:
    """Specified SHA256 counter stream, including rejection and exhaustion."""
    def __init__(self, key):
        self.key_bytes = compact(key)
        self.counter = 0

    def randbelow(self, m):
        if type(m) is not int or not 1 <= m <= 2 ** 64:
            raise ValueError("invalid_integer_range")
        limit = (2 ** 64 // m) * m
        while True:
            if self.counter >= 2 ** 64:
                raise ValueError("sha256_counter_exhausted")
            digest = hashlib.sha256(self.key_bytes + self.counter.to_bytes(8, "big")).digest()
            self.counter += 1
            x = int.from_bytes(digest[:8], "big")
            if x < limit:
                return x % m


def _category(values, width):
    if not isinstance(values, list) or len(values) != width:
        raise ValueError("diagnostic_category_shape")
    if any(type(x) not in (int, float) or x not in (0, 1) for x in values):
        raise ValueError("diagnostic_category_encoding")
    if sum(values) != 1:
        raise ValueError("diagnostic_category_not_one_hot")
    return values.index(1)


def diagnostic_transform(prepared_session, tag, replicate):
    """Return copied session, complete donor maps and disruption accounting.

    Identity uses tag='identity', replicate=None. D-label/D-neural use 0..19.
    The returned session is a private diagnostic operand, never a primary actor
    view. Its source identity and all original history features remain intact.
    """
    if tag == "identity":
        if replicate is not None:
            raise ValueError("identity_replicate_must_be_none")
    elif tag not in ("D-label", "D-neural") or type(replicate) is not int or not 0 <= replicate < 20:
        raise ValueError("undeclared_diagnostic_identity")
    if prepared_session.get("status") != STATUS or prepared_session.get("structural_holds", []):
        raise ValueError("diagnostic_preparation_held")
    session_id = prepared_session["session_id"]
    units = prepared_session["unit_ids"]
    if not units or any(not isinstance(u, str) or not u for u in units) or len(set(units)) != len(units):
        raise ValueError("diagnostic_unit_axis")
    original = prepared_session["cases"]
    if len({c["case_id"] for c in original}) != len(original):
        raise ValueError("duplicate_diagnostic_case")
    if len({c["ordinal"] for c in original}) != len(original):
        raise ValueError("duplicate_diagnostic_ordinal")
    groups = {}
    for i, case in enumerate(original):
        if case["split"] not in ("train", "val", "test"):
            raise ValueError("diagnostic_split_axis")
        if type(case["ordinal"]) is not int or case["ordinal"] < 0:
            raise ValueError("diagnostic_ordinal_axis")
        if type(case["y"]) is not int or case["y"] not in (0, 1):
            raise ValueError("diagnostic_binary_truth")
        if len(case["N"]) != len(units) or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in case["N"]):
            raise ValueError("diagnostic_neural_axis")
        if "unit_ids" in case and case["unit_ids"] != units:
            raise ValueError("diagnostic_case_unit_axis")
        key = (case["split"], _category(case["S"], 9),
               _category(case["B"], 3), _category(case["H"], 7))
        groups.setdefault(key, []).append(i)
    result = copy.deepcopy(prepared_session)
    maps, strata = [], []
    changed = moved = 0
    for key in sorted(groups):
        split, s, b, h = key
        indices = sorted(groups[key], key=lambda i: original[i]["ordinal"])
        donors = list(indices)
        active = tag == "D-neural" or (tag == "D-label" and split in ("train", "val"))
        rng = None
        if active:
            rng = HashRNG([PREFIX, tag, session_id, split, s, b, h, replicate])
            for i in range(len(donors) - 1, 0, -1):
                j = rng.randbelow(i + 1)
                donors[i], donors[j] = donors[j], donors[i]
        before = [sum(original[i]["y"] == y for i in indices) for y in (0, 1)]
        group_changed = group_moved = 0
        for recipient, donor in zip(indices, donors):
            src, dst = original[donor], result["cases"][recipient]
            field = "y" if tag == "D-label" else "N"
            differs = active and original[recipient][field] != src[field]
            if active:
                dst[field] = copy.deepcopy(src[field])
            group_changed += int(differs)
            group_moved += int(donor != recipient)
            maps.append({"split": split, "S_category": s, "B_category": b, "H_category": h,
                         "recipient_case_id": dst["case_id"], "recipient_ordinal": dst["ordinal"],
                         "donor_case_id": src["case_id"], "donor_ordinal": src["ordinal"],
                         "donor_moved": donor != recipient, "payload_changed": bool(differs)})
        after = [sum(result["cases"][i]["y"] == y for i in indices) for y in (0, 1)]
        if before != after:
            raise AssertionError("diagnostic_class_balance_invariant_failed")
        strata.append({"split": split, "S_category": s, "B_category": b, "H_category": h,
                       "case_ids": [original[i]["case_id"] for i in indices],
                       "rows": len(indices), "fixed_payload_rows": len(indices) - group_changed,
                       "changed_payload_rows": group_changed, "moved_donor_rows": group_moved,
                       "class_counts_before": before, "class_counts_after": after,
                       "rng_counter": rng.counter if rng else 0,
                       "reason": "identity_panel_or_held_truth" if not active else
                                 "singleton" if len(indices) == 1 else
                                 "effective_disruption_zero" if not group_changed else None})
        changed += group_changed
        moved += group_moved
    result["diagnostic_identity"] = {"tag": tag, "replicate": replicate}
    return {"status": STATUS, "tag": tag, "replicate": replicate,
            "interpretation": "association stress diagnostic; no exchangeable null or p-value",
            "prepared_session": result, "donor_maps": maps, "strata": strata,
            "rows": len(original), "changed_payload_rows": changed,
            "fixed_payload_rows": len(original) - changed, "moved_donor_rows": moved,
            "informative_disruption": bool(changed),
            "reason": None if changed else "effective_disruption_zero"}


def diagnostic_panels(prepared_session):
    """Stream identity plus all forty finite diagnostic panels, one at a time."""
    yield diagnostic_transform(prepared_session, "identity", None)
    for tag in ("D-label", "D-neural"):
        for replicate in range(20):
            yield diagnostic_transform(prepared_session, tag, replicate)
