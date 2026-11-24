"""Export the deposited distance/coactivity curves from identity-bound pair rows.

This is a partial original-endpoint preparation, not a fit, paper score or
verification of complete original population membership. No data are acquired.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from coactivity_row_audit import AREA_CUTOFF_UM2, SOURCE_SHA256, audit


def _summary(rows, responses):
    values = [responses[row["row_id"]] for row in rows]
    observed = [value for value in values if value is not None]
    infinite = sum(value == "Inf" for value in observed)
    count = len(observed)
    if not count:
        mean, sem, status = None, None, "no_nonmissing_values"
    elif infinite:
        # MATLAB nanmean/nanstd omit NaN, but do not omit positive infinity.
        mean, sem, status = "Inf", None, "infinite_mean_undefined_sem"
    else:
        # Scaling avoids overflow for a finite mean of nonnegative values.
        scale = max(observed)
        scaled = [value / scale for value in observed] if scale else observed
        center = math.fsum(scaled) / count
        mean = center * scale
        sem = (math.sqrt(math.fsum((value - center) ** 2 for value in scaled)
                         / (count - 1) / count) * scale) if count > 1 else 0.0
        status = "finite"
    return {"row_ids": [row["row_id"] for row in rows],
            "rows": len(rows), "nonmissing_rows": count,
            "nan_rows": len(values) - count, "positive_infinity_rows": infinite,
            "mean_normalized_coactivity": mean, "source_sem": sem,
            "summary_status": status}


def export_curves(data):
    if not isinstance(data, dict) or data.get("schema_version") != "rep011-coactivity-curves-input-v1":
        raise ValueError("unsupported input schema")
    if data.get("source_sha256") != SOURCE_SHA256:
        raise ValueError("input must name the deposited source SHA-256")
    if data.get("input_kind") not in ("generated_engineering_control", "empirical"):
        raise ValueError("explicit input_kind required")
    for name in ("population_id", "native_pair_order_provenance"):
        if not isinstance(data.get(name), str) or not data[name].strip():
            raise ValueError(f"{name} required")
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("nonempty complete supplied row metadata required")
    row_audit = audit(rows)
    expected = {row["row_id"] for row in rows}
    entries = data.get("responses")
    if not isinstance(entries, list):
        raise ValueError("keyed responses must be a list")
    responses = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("row_id"), str):
            raise ValueError("every response requires row_id")
        key = entry["row_id"]
        if key not in expected or key in responses:
            raise ValueError("extra or duplicate response row_id")
        if "normalized_coactivity" not in entry:
            raise ValueError("every response requires normalized_coactivity")
        value = entry["normalized_coactivity"]
        if not (value is None or value == "Inf" or
                (type(value) in (int, float) and math.isfinite(value) and value >= 0)):
            raise ValueError("coactivity must be nonnegative finite, null (NaN), or 'Inf'")
        responses[key] = value
    if set(responses) != expected:
        raise ValueError("responses must cover all supplied rows, including distance-excluded rows")

    curves = []
    for family in ("all_spines", "size_stratified", "session_stratified"):
        strata = (None,) if family == "all_spines" else (
            ("small", "large") if family == "size_stratified" else ("early", "middle"))
        for state in ("stable", "eliminated"):
            for stratum in strata:
                points = []
                for start in range(0, 51, 5):
                    selected = []
                    for row in rows:
                        distance, area = row["distance_um"], row["area_um2"]
                        if row["stability"] != state or distance is None or not start <= distance < start + 5:
                            continue
                        if family == "size_stratified" and (area is None or
                                ((area <= AREA_CUTOFF_UM2) != (stratum == "small"))):
                            continue
                        if family == "session_stratified" and row["session"] != stratum:
                            continue
                        selected.append(row)
                    # Original plotting vectors concatenate early then middle.
                    selected.sort(key=lambda row: row["session"] == "middle")
                    points.append({"bin_start_um": start, "bin_end_exclusive_um": start + 5,
                                   "plot_center_um": start + 2.5, **_summary(selected, responses)})
                curves.append({"family": family, "stability": state, "stratum": stratum,
                               "points": points})
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {"schema_version": "rep011-coactivity-curves-result-v1",
            "task_id": "PAPER-FIND-REP-011", "source_sha256": SOURCE_SHA256,
            "input_sha256": hashlib.sha256(encoded).hexdigest(),
            "input_kind": data["input_kind"], "population_id": data["population_id"],
            "native_pair_order_provenance": data["native_pair_order_provenance"],
            "coverage": "all supplied rows; original population completeness unverified",
            "scientific_qualification": "unknown", "reproduction_score": None,
            "improvement_score": None, "complete_original_population_verified": False,
            "source_summary": "nanmean and sample nanstd/sqrt(non-NaN count); pair-weighted, not mouse-weighted",
            "area_cutoff_um2": AREA_CUTOFF_UM2,
            "missing_area_row_ids": [row["row_id"] for row in rows if row["area_um2"] is None],
            "row_audit": row_audit, "curves": curves,
            "limits": ["No native MATLAB loading, activity calculation, or authentic cohort verification.",
                       "Pair rows retain directed pairs, repeats and missing responses; no independence claim.",
                       "No source table repair, mixed-effects inference, source/manuscript discrepancy resolution or paper score.",
                       "Other primary activity, spatial, environment and timing endpoints remain required.",
                       "Paper+data and paper+data+author-code delivery and scoring remain unqualified."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.input.resolve() == args.output.resolve():
        parser.error("output must be a new file")
    result = export_curves(json.loads(args.input.read_text()))
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
