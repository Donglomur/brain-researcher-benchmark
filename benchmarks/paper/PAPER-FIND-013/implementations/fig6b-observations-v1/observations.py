"""Original CA observation support and unadjusted R2; no model fitting.

Preparation requires the exact public MAT files. Run authentic preparation only
under a separately coordinated native protocol. The stdlib kernels are testable
without opening empirical inputs or importing a numerical library.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path

REVISION = "7a6ecc2bbf8f1e1fbca3b769a0db53299ee8171c"
SOURCE_SHA256 = {
    "CA1": "c565dcef738683fb398880a63e30031fda3170870b4a4e254c9bc5dac028c5b9",
    "CA3": "ec8a31ae5d2c73dbed089d6d4c3c0aa56599336342e6918470216d49416da9fc",
}
SOURCE_BYTES = {"CA1": 4429731, "CA3": 1121031}
ANIMALS = {
    "CA1": ["1-3"] * 4 + ["cdc", "cfc", "cfc", "wt1", "wt1"],
    "CA3": (["4-2"] * 6 + ["4-1"] * 6 + ["5-3"] * 3 + ["5-1"] * 3
            + ["5-3"] * 3 + ["5-4"] * 3 + ["5-1"] * 3 + ["5-4"] * 3
            + ["7-2"] * 4 + ["9-1"] * 3),
}
TOTALS = {"CA1/f": 1072, "CA1/n": 1168, "CA3/f": 179, "CA3/n": 238}
ELIGIBLE = {"CA1/f": 1068, "CA1/n": 1167, "CA3/f": 179, "CA3/n": 235}


def finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: expected a finite number")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name}: unsupported numeric magnitude") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name}: expected a finite number")
    return value


def support(com_bins, onset_lap):
    """Faithfully retain both literal source clocks, without interpolating y.

    None represents source NaN on the JSON wire. Internal NaN is also accepted
    for scipy's MAT adapter. The onset COM must be finite, as in the saved census.
    """
    if not isinstance(com_bins, (list, tuple)) or not com_bins:
        raise ValueError("COM must be a nonempty row")
    onset = finite_number(onset_lap, "onset")
    if not onset.is_integer() or not 1 <= onset <= len(com_bins):
        raise ValueError("onset must be a one-based source column")
    onset = int(onset)
    origin = finite_number(com_bins[onset - 1], "onset COM")
    if abs(origin) > 2**50:
        raise ValueError("unsupported COM magnitude")
    observed_laps, y, missing_laps = [], [], []
    segment = com_bins[onset - 1:]
    for lap1, value in enumerate(segment, 1):
        if value is None or (isinstance(value, float) and math.isnan(value)):
            missing_laps.append(lap1)
            continue
        value = finite_number(value, "COM")
        if abs(value) > 2**50:
            raise ValueError("unsupported COM magnitude")
        observed_laps.append(lap1)
        # Preserve the original multiply-before-subtract operation order.
        y.append(6.0 * value - 6.0 * origin)
    # Source interp1 requires at least two observations. Do not repair this.
    if len(observed_laps) < 2:
        raise ValueError("source interpolation support has fewer than two points")
    span = observed_laps[-1] - observed_laps[0] + 1
    return {
        "onset_lap1": onset,
        "source_segment_length": len(segment),
        "observed_laps_since_onset1": observed_laps,
        "source_laps1": [onset + lap - 1 for lap in observed_laps],
        "literal_nonlinear_clock0": list(range(len(y))),
        "missing_laps_since_onset1": missing_laps,
        "com_displacement_cm": y,
        "interior_filled_span": span,
        "in_original_Tok": span >= 15,
        "disposition": "original_Tok" if span >= 15 else "short_interpolated_span",
    }


def _scalar_struct(value, name):
    if getattr(value, "shape", None) != (1, 1) or not value.dtype.names:
        raise ValueError(f"{name}: expected scalar MATLAB struct")
    return value[0, 0]


def _snapshot(path, expected_sha256, mismatch_message, *, expected_bytes=None):
    """Authenticate the immutable bytes consumed downstream, never a later read."""
    with Path(path).open("rb") as stream:
        raw = stream.read() if expected_bytes is None else stream.read(expected_bytes + 1)
    if ((expected_bytes is not None and len(raw) != expected_bytes)
            or hashlib.sha256(raw).hexdigest() != expected_sha256):
        raise ValueError(mismatch_message)
    return raw


def prepare(ca1_path, ca3_path):
    """Prepare the exact source cohort; this performs no regression or fitting."""
    paths = {"CA1": Path(ca1_path), "CA3": Path(ca3_path)}
    # Capture and authenticate both originals before numerical imports. The
    # fixed original byte lengths also bound capture of an incorrect large file.
    sources = {
        region: _snapshot(path, SOURCE_SHA256[region],
                          f"{region}: original source hash mismatch",
                          expected_bytes=SOURCE_BYTES[region])
        for region, path in paths.items()
    }
    # Imported only after identity admission; not needed by generated kernels.
    import numpy as np
    from scipy.io import loadmat

    fields, planes = [], []
    for region, raw in sources.items():
        data = _scalar_struct(loadmat(BytesIO(raw), variable_names=["data"])["data"], region)
        if list(data.dtype.names) != ["f", "n"]:
            raise ValueError(f"{region}: source condition order changed")
        for condition in ("f", "n"):
            cond = _scalar_struct(data[condition], condition)
            names = list(cond.dtype.names)
            if len(names) != len(ANIMALS[region]):
                raise ValueError("source positional animal mapping changed")
            for plane1, name in enumerate(names, 1):
                plane = _scalar_struct(cond[name], name)
                com, onset = plane["COM"], plane["onset_lap"]
                if (not np.issubdtype(com.dtype, np.number) or not np.isrealobj(com)
                        or not np.issubdtype(onset.dtype, np.number) or not np.isrealobj(onset)):
                    raise ValueError("non-real source COM/onset")
                if com.ndim != 2 or onset.ndim != 2:
                    raise ValueError("unsupported source shape")
                if com.size == 0:
                    if com.shape != (0, 0) or onset.shape != (0, 0):
                        raise ValueError("unexpected source empty plane")
                    onset_values = []
                else:
                    if min(onset.shape) != 1 or onset.size != com.shape[0]:
                        raise ValueError("onset vector must match COM rows")
                    onset_values = onset.reshape(-1, order="F").tolist()
                animal = ANIMALS[region][plane1 - 1]
                planes.append({"region": region, "condition": condition, "plane": name,
                               "plane_ordinal1": plane1, "animal": animal,
                               "field_count": len(onset_values)})
                for row1, onset_value in enumerate(onset_values, 1):
                    item = support(com[row1 - 1].tolist(), onset_value)
                    item.update({"id": f"{region}/{condition}/{name}/{row1}",
                                 "region": region, "condition": condition, "plane": name,
                                 "plane_ordinal1": plane1, "field_row1": row1,
                                 "animal": animal})
                    fields.append(item)
    packet = {"schema": "find013-original-observations/v1", "source_revision": REVISION,
              "source_sha256": SOURCE_SHA256.copy(), "units": {"response": "cm", "clock": "lap"},
              "planes": planes, "fields": fields}
    validate_panel(packet)
    return packet


def validate_panel(packet):
    """Validate the complete fixed panel and internal support before scoring."""
    if (packet.get("schema") != "find013-original-observations/v1"
            or packet.get("source_revision") != REVISION
            or packet.get("source_sha256") != SOURCE_SHA256
            or packet.get("units") != {"response": "cm", "clock": "lap"}):
        raise ValueError("original observation provenance/schema mismatch")
    fields, planes = packet.get("fields"), packet.get("planes")
    if not isinstance(fields, list) or len(fields) != 2657:
        raise ValueError("expected all 2657 source fields, including 8 exclusions")
    if not isinstance(planes, list) or len(planes) != 92:
        raise ValueError("expected all 92 condition-plane entries")
    seen, total, eligible, by_plane = set(), Counter(), Counter(), Counter()
    plane_map = {}
    for plane in planes:
        key = (plane["region"], plane["condition"], plane["plane"])
        if key in plane_map:
            raise ValueError("duplicate plane")
        plane_map[key] = plane
    for row in fields:
        identity = row["id"]
        if identity in seen:
            raise ValueError("duplicate PF identity")
        seen.add(identity)
        region, condition, name = row["region"], row["condition"], row["plane"]
        if identity != f"{region}/{condition}/{name}/{row['field_row1']}":
            raise ValueError("PF identity disagrees with source coordinates")
        plane = plane_map.get((region, condition, name))
        if plane is None or row["animal"] != plane["animal"] or row["plane_ordinal1"] != plane["plane_ordinal1"]:
            raise ValueError("PF/plane/animal mapping mismatch")
        if type(row["field_row1"]) is not int or not 1 <= row["field_row1"] <= plane["field_count"]:
            raise ValueError("invalid original field row")
        obs, missing, length = row["observed_laps_since_onset1"], row["missing_laps_since_onset1"], row["source_segment_length"]
        if type(length) is not int or length < 2 or len(obs) < 2 or obs[0] != 1:
            raise ValueError("invalid source support")
        if any(type(x) is not int for x in obs + missing):
            raise ValueError("source laps must be integers")
        if obs != sorted(set(obs)) or missing != sorted(set(missing)) or sorted(obs + missing) != list(range(1, length + 1)):
            raise ValueError("source observed/missing support must partition original clock")
        onset = row["onset_lap1"]
        if type(onset) is not int or onset < 1 or row["source_laps1"] != [onset + x - 1 for x in obs]:
            raise ValueError("original clock mismatch")
        y = row["com_displacement_cm"]
        if len(y) != len(obs) or any(not math.isfinite(finite_number(v, "COM response")) for v in y) or y[0] != 0:
            raise ValueError("response/support mismatch")
        span = obs[-1] - obs[0] + 1
        admitted = span >= 15
        if (row["literal_nonlinear_clock0"] != list(range(len(y)))
                or row["interior_filled_span"] != span
                or type(row["in_original_Tok"]) is not bool
                or row["in_original_Tok"] != admitted
                or row["disposition"] != ("original_Tok" if admitted else "short_interpolated_span")):
            raise ValueError("original eligibility or nonlinear clock changed")
        key = f"{region}/{condition}"
        total[key] += 1
        eligible[key] += int(admitted)
        by_plane[(region, condition, name)] += 1
    if dict(total) != TOTALS or dict(eligible) != ELIGIBLE:
        raise ValueError("original group totals/2649-PF panel changed")
    if sum(p["field_count"] == 0 for p in planes) != 4:
        raise ValueError("original empty planes changed")
    for key, plane in plane_map.items():
        region, condition, _ = key
        ordinal = plane["plane_ordinal1"]
        if (region not in ANIMALS or condition not in ("f", "n")
                or type(ordinal) is not int or not 1 <= ordinal <= len(ANIMALS[region])
                or plane["animal"] != ANIMALS[region][ordinal - 1]
                or type(plane["field_count"]) is not int
                or by_plane[key] != plane["field_count"]):
            raise ValueError("original positional plane mapping/count mismatch")
    for region in ANIMALS:
        for condition in ("f", "n"):
            ordinals = [p["plane_ordinal1"] for p in planes if p["region"] == region and p["condition"] == condition]
            if sorted(ordinals) != list(range(1, len(ANIMALS[region]) + 1)):
                raise ValueError("missing/duplicated source plane ordinal")


def r_squared(y, fitted):
    """Ordinary 1-SSE/SST, including negative values; no adjusted/clipped R2."""
    if not isinstance(y, list) or not isinstance(fitted, list) or len(y) < 2 or len(y) != len(fitted):
        raise ValueError("predictions must cover every observed point")
    y = [finite_number(v, "response") for v in y]
    fitted = [finite_number(v, "fitted value") for v in fitted]
    def square(value):
        result = value * value
        if value != 0 and result == 0:
            raise ValueError("squared residual/deviation underflow")
        return result
    try:
        mean = math.fsum(y) / len(y)
        sst = math.fsum(square(v - mean) for v in y)
        sse = math.fsum(square(v - p) for v, p in zip(y, fitted))
        result = None if sst == 0 else 1.0 - sse / sst
    except (OverflowError, ValueError) as exc:
        raise ValueError("unsupported derived numerics") from exc
    if not math.isfinite(sst) or not math.isfinite(sse) or (result is not None and not math.isfinite(result)):
        raise ValueError("unsupported derived numerics")
    return {"n": len(y), "sse_cm2": sse, "sst_cm2": sst, "r2": result,
            "status": "constant_response" if sst == 0 else "defined"}


def score(packet, predictions):
    """Score three supplied curves; arm names are not proof of author inference."""
    validate_panel(packet)
    expected = [r for r in packet["fields"] if r["in_original_Tok"]]
    if not isinstance(predictions, dict) or set(predictions) != {"linear", "plateau", "candidate"}:
        raise ValueError("require separate linear, plateau and candidate predictions")
    ids = {r["id"] for r in expected}
    for arm, supplied in predictions.items():
        if not isinstance(supplied, dict) or set(supplied) != ids:
            raise ValueError(f"{arm}: require the exact complete 2649-PF panel")
    results = []
    for row in expected:
        metrics = {arm: r_squared(row["com_displacement_cm"], predictions[arm][row["id"]]) for arm in predictions}
        candidate = metrics["candidate"]["r2"]
        baseline = metrics["plateau"]["r2"]
        results.append({"id": row["id"], "region": row["region"], "condition": row["condition"],
                        "animal": row["animal"], "metrics": metrics,
                        "candidate_minus_plateau_r2": None if candidate is None or baseline is None else candidate - baseline})
    return {"schema": "find013-paired-r2/v1", "fields": results, "panel_count": 2649,
            "source_rows": 2657, "source_exclusions": 8,
            "metric": "unadjusted_unclipped_R2", "scientific_qualification": "not_established",
            "author_prediction_authentication": "required_separately",
            "aggregate_superiority_decision": None}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _decode(raw):
    def invalid(value):
        raise ValueError(f"nonfinite JSON constant: {value}")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=invalid)


def _read(path):
    return _decode(Path(path).read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--ca1", required=True)
    prep.add_argument("--ca3", required=True)
    grading = sub.add_parser("score")
    grading.add_argument("--observations", required=True)
    grading.add_argument("--expected-observations-sha256", required=True)
    grading.add_argument("--predictions", required=True)
    for child in (prep, grading):
        child.add_argument("--output", required=True)
    args = parser.parse_args()
    if Path(args.output).exists():
        raise ValueError("output must be a fresh path")
    if args.command == "prepare":
        result = prepare(args.ca1, args.ca3)
    else:
        raw = _snapshot(args.observations, args.expected_observations_sha256,
                        "operator observation digest mismatch")
        result = score(_decode(raw), _read(args.predictions))
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, allow_nan=False, separators=(",", ":"))
        stream.write("\n")


if __name__ == "__main__":
    main()
