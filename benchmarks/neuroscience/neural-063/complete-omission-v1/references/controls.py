"""Exact direct and matched-history controls; no data reads or fits at import."""
from __future__ import annotations
from collections import defaultdict
import hashlib
import math
from owner.io import ContractError
from owner.scoring import hierarchy, stable_mean
from .schema import SEEDS, row_numeric, row_categories, object_hash


def fit_mean(rows):
    if any(r["split"] != "fit" for r in rows): raise ContractError("FIT-only mean control")
    weights, _ = hierarchy(rows, 73)
    values = []
    for k in range(3):
        raw = [float(r["target"][k]) for r in rows]
        scale = max(abs(v) for v in raw)
        values.append(0.0 if scale == 0 else math.fsum(weights[r["id"]] * v / scale for r, v in zip(rows, raw)) * scale)
    if not all(math.isfinite(x) for x in values): raise ContractError("nonfinite FIT mean control")
    return {"schema": "neural063_fit_mean_control_v1", "values": values,
            "fit_mice": 73, "fit_ids_sha256": object_hash([r["id"] for r in rows]),
            "weights_sha256": object_hash([[r["id"], weights[r["id"]]] for r in rows])}


def direct(rows, fitted_mean):
    constant = fitted_mean["values"]
    if len(constant) != 3 or not all(math.isfinite(v) for v in constant):
        raise ContractError("complete finite mean control required")
    outputs = {"zero": [], "fit_mean": [], "trend": []}
    times = (-0.7, -0.5, -0.3, -0.1)
    centered = [t - math.fsum(times) / 4 for t in times]
    denominator = math.fsum(t * t for t in centered)
    for row in rows:
        h = row["history"]
        if len(h) != 12 or h[-1] != 0 or not all(math.isfinite(v) for v in h):
            raise ContractError("complete baseline-subtracted history required")
        recent = h[8:12]
        mean = stable_mean(recent)
        numerator = math.fsum(t * (value - mean) for t, value in zip(centered, recent))
        slope = numerator / denominator
        trend = [slope * t for t in (0.2, 0.4, 0.6)]
        if not all(math.isfinite(v) for v in trend): raise ContractError("trend arithmetic overflow; no clipping")
        outputs["zero"].append({"id": row["id"], "values": [0.0, 0.0, 0.0]})
        outputs["fit_mean"].append({"id": row["id"], "values": list(constant)})
        outputs["trend"].append({"id": row["id"], "values": trend})
    return outputs


def stratum(row):
    categories = row_categories(row)
    numeric = row_numeric(row, "T")
    # The accepted order is six context categories, then three prior tokens,
    # followed by depth and three cadence bins. No target/history is consulted.
    return tuple(categories) + (math.floor(numeric[3] / 25),) + tuple(math.floor(x / 0.025) for x in numeric[:3])


def permute(rows, seed):
    if seed not in SEEDS or any(r["split"] != "fit" for r in rows):
        raise ContractError("fixed FIT-only history permutation seed required")
    weights, _ = hierarchy(rows, 73)
    groups = defaultdict(list)
    for row in rows: groups[stratum(row)].append(row)
    donor_ids = {}; dispositions = []; changed_mice = set(); changed_ids = set(); reassigned_ids = set()
    all_mice = {r["mouse"] for r in rows}
    by_id = {r["id"]: r for r in rows}
    for key in sorted(groups, key=lambda x: object_hash(list(x))):
        ordered = sorted(groups[key], key=lambda r: (hashlib.sha256((str(seed) + ":" + r["id"]).encode()).hexdigest(), r["id"]))
        offset = next((k for k in range(1, len(ordered)) if all(row["mouse"] != ordered[(i + k) % len(ordered)]["mouse"] for i, row in enumerate(ordered))), None)
        for i, row in enumerate(ordered):
            donor = row if offset is None else ordered[(i + offset) % len(ordered)]
            donor_ids[row["id"]] = donor["id"]
            if donor["id"] != row["id"]:
                reassigned_ids.add(row["id"])
            if donor["history"] != row["history"]:
                changed_ids.add(row["id"]); changed_mice.add(row["mouse"])
        dispositions.append({"stratum_sha256": object_hash(list(key)), "rows": len(ordered),
                             "mice": len({r["mouse"] for r in ordered}), "rotation": offset,
                             "status": "undisturbable" if offset is None else "changed",
                             "reason": "no_cross_mouse_cyclic_rotation" if offset is None else None})
    perturbed = [{**r, "history": list(by_id[donor_ids[r["id"]]]["history"])} for r in rows]
    changed_weight = math.fsum(weights[ident] for ident in changed_ids)
    supported = changed_weight >= 0.5 and changed_mice == all_mice
    receipt = {"schema": "neural063_history_permutation_v1", "seed": seed,
               "pairs": [[r["id"], donor_ids[r["id"]]] for r in rows],
               "permutation_sha256": object_hash([[r["id"], donor_ids[r["id"]]] for r in rows]),
               "strata": dispositions, "rows_total": len(rows), "rows_changed": len(changed_ids),
               "rows_reassigned": len(reassigned_ids),
               "hierarchical_fit_weight_reassigned": math.fsum(weights[i] for i in reassigned_ids),
               "changed_definition": "history vector differs numerically; reassigned but identical vectors are separately counted",
               "hierarchical_fit_weight_changed": changed_weight,
               "recipient_mice_changed": sorted(changed_mice),
               "donor_mice_changed": sorted({by_id[donor_ids[i]]["mouse"] for i in changed_ids}),
               "fit_mice_total": 73, "support": "supported" if supported else "unsupported",
               "reason": None if supported else "requires_half_weight_and_every_FIT_mouse_changed",
               "all_rows_retained": True, "strata_relaxed": False}
    return perturbed, receipt
