"""Prospective full-field FUS representation on trusted normalized inputs.

This is NOT a MAT reader, clock mapper, source authenticator or model runner.
The accepted scorer.py and roster.py must be alongside this module unchanged.
Only prepare_fold is the complete-population interface; lower-level functions
are scientific primitives and cannot establish a complete fold by themselves.
"""
import math
import re
from fractions import Fraction

from scorer import ConstructionError, exact_keys, finite, pin, require, validate_intake

FLOATS = {"binary32": (24, -126, 127), "binary64": (53, -1022, 1023)}
FOLD_KEY = re.compile(r"fold_[0-9a-f]{32}\Z")
SPECIAL = {"nan": float("nan"), "+inf": float("inf"), "-inf": -float("inf")}


def rounded(value, dtype):
    """Exact IEEE round-to-nearest/ties-even of a rational, without double rounding.

    The result is a Python float containing the selected representable value.
    Overflow gives infinity; gradual underflow is preserved. Signed zero has
    no effect here: denominators must be positive and zero deltas encode 128.
    """
    require(dtype in FLOATS, "explicit binary32/binary64 arithmetic required")
    precision, emin, emax = FLOATS[dtype]
    if not value:
        return 0.0
    sign = -1 if value < 0 else 1
    value = abs(value)
    n, d = value.numerator, value.denominator
    exponent = n.bit_length() - d.bit_length()
    if (n < d << exponent) if exponent >= 0 else (n << -exponent < d):
        exponent -= 1
    quantum = max(exponent - precision + 1, emin - precision + 1)
    if quantum >= 0:
        denominator, numerator = d << quantum, n
    else:
        denominator, numerator = d, n << -quantum
    integer, remainder = divmod(numerator, denominator)
    if 2 * remainder > denominator or (2 * remainder == denominator and integer % 2):
        integer += 1
    if integer and integer.bit_length() - 1 + quantum > emax:
        return math.copysign(math.inf, sign)
    return math.copysign(math.ldexp(float(integer), quantum), sign)


def source_value(value, dtype):
    if type(value) is str and value in SPECIAL:
        return SPECIAL[value]
    require(finite(value), "source pixel must be a finite number or explicit nan/+inf/-inf token")
    exact = Fraction(value)
    result = rounded(exact, dtype)
    require(math.isfinite(result) and Fraction(result) == exact,
            "source operand is not exactly representable in its declared floating format")
    return result


def delta_pixel(memory, baseline, dtype):
    """Round subtraction then division in the declared source format, no reassociation."""
    m, b = source_value(memory, dtype), source_value(baseline, dtype)
    if not math.isfinite(m) or not math.isfinite(b) or b <= 0:
        return None
    difference = rounded(Fraction(m) - Fraction(b), dtype)
    if not math.isfinite(difference):
        return None
    result = rounded(Fraction(difference) / Fraction(b), dtype)
    return result if math.isfinite(result) else None


def encode(delta, scale):
    """Literal half-up quantizer evaluated on exact represented scalar values.

    Rational evaluation avoids an accidental float tie flip. Source-format
    subtraction/division have already happened in delta_pixel.
    """
    require(finite(scale) and scale > 0, "positive finite training-only scale required")
    if delta is None:
        return (255, 0, 255), False
    require(finite(delta), "nonfinite delta must have an explicit invalid mask")
    d, s = Fraction(delta), Fraction(scale)
    saturated = abs(d) > s
    d = min(s, max(-s, d))
    level = (255 * (d / s + 1) + 1) / 2
    g = level.numerator // level.denominator
    return (g, g, g), saturated


def select_frames(frames, timing):
    """Select by complete acquisition intervals, never presumed sample duration.

    A tied latest end time is ambiguous and refuses; source order is not a
    license to choose a favorable simultaneous acquisition.
    """
    require(type(frames) is list and frames, "complete acquisition catalogue required")
    seen = set()
    for order, frame in enumerate(frames):
        exact_keys(frame, ("frame_id", "source_order", "start", "end", "complete", "pixels"), "frame")
        identity = frame["frame_id"]
        require(type(identity) is str and 0 < len(identity) <= 200 and identity not in seen,
                "unique source frame identities required within each trial catalogue")
        seen.add(identity)
        require(type(frame["source_order"]) is int and frame["source_order"] == order,
                "complete ordered acquisition catalogue required")
        require(finite(frame["start"]) and finite(frame["end"]) and frame["start"] < frame["end"],
                "finite positive-duration acquisition interval required")
        require(type(frame["complete"]) is bool, "acquisition completeness must be explicit")
    baseline = [f for f in frames if f["complete"] and f["end"] < timing["cue"]]
    memory = [f for f in frames if f["complete"] and
              timing["memory_start"] <= f["start"] and
              f["end"] <= min(timing["memory_end"], timing["go"])]
    chosen = []
    for name, candidates in (("baseline", baseline), ("acquisition", memory)):
        require(candidates, "no complete " + name + "; existing eligibility must be independently re-adjudicated")
        last = max(f["end"] for f in candidates)
        matches = [f for f in candidates if f["end"] == last]
        require(len(matches) == 1, "ambiguous latest " + name + " acquisition")
        selected = matches[0]
        require(selected["start"] == timing[name + "_start"] and
                selected["end"] == timing[name + "_end"], "selected frame differs from frozen intake")
        chosen.append(selected)
    return tuple(chosen)


def record_deltas(record, normalized):
    """Yield every eligible full map in complete frozen source-trial order.

    The normalized producer is trusted and still missing for authentic data.
    Its catalogue must include every candidate acquisition, not only selected
    pairs. Every frame retains its full grid; excluded trials remain explicit
    and cannot be introduced by this component.
    """
    exact_keys(normalized, ("schema", "record_id", "native_hz", "source_float", "shape",
                           "spatial_pitch", "spatial_pitch_unit", "acquisition_census_sha256", "trials"), "normalized record")
    require(normalized["schema"] == "fus_normalized_fullfield_record_v1", "normalized schema")
    require(normalized["record_id"] == record["record_id"] and
            type(normalized["native_hz"]) is int and normalized["native_hz"] == record["native_hz"],
            "record/rate mismatch")
    dtype = normalized["source_float"]
    require(type(dtype) is str and dtype in FLOATS, "declared source floating format")
    shape = normalized["shape"]
    require(type(shape) is list and len(shape) == 2 and all(type(n) is int and n > 0 for n in shape),
            "complete native y,x shape required")
    pitch = normalized["spatial_pitch"]
    require(type(pitch) is list and len(pitch) == 2 and all(finite(x) and x > 0 for x in pitch),
            "native y,x spatial pitch required")
    unit = normalized["spatial_pitch_unit"]
    require(type(unit) is str and 0 < len(unit) <= 64 and unit.strip() == unit, "explicit spatial pitch unit")
    require(pin(normalized["acquisition_census_sha256"]), "independent complete acquisition census identity")
    trials = normalized["trials"]
    require(type(trials) is list and len(trials) == len(record["trials"]), "complete source trial support")
    size = shape[0] * shape[1]
    for frozen, source in zip(record["trials"], trials):
        exact_keys(source, ("source_trial_id", "source_order", "frames"), "normalized trial")
        require(source["source_trial_id"] == frozen["source_trial_id"] and
                type(source["source_order"]) is int and source["source_order"] == frozen["source_order"],
                "source trial join/order mismatch")
        if frozen["disposition"] == "adjudicated_excluded":
            require(source["frames"] is None, "excluded trial must remain explicit; no newly chosen exclusions")
            continue
        baseline, memory = select_frames(source["frames"], frozen["timing"])
        for frame in source["frames"]:
            require(type(frame["pixels"]) is list and len(frame["pixels"]) == size,
                    "every acquisition must retain all native spatial pixels in y-major order")
        # Validate selected operands only; unselected frame pixels are never used.
        deltas = [delta_pixel(m, b, dtype) for m, b in zip(memory["pixels"], baseline["pixels"])]
        yield frozen, deltas, {"shape": list(shape), "spatial_pitch": list(pitch),
                              "spatial_pitch_unit": unit, "native_hz": record["native_hz"],
                              "source_float": dtype}


def prepare_fold(intake, load_record, emit, *, held_record_id, fold_key):
    """Construct one full outer fold; caller commits outputs ONLY after success.

    load_record(record_id) supplies the trusted complete normalized record.
    It is invoked once for each of the 47 other positive records, in canonical
    intake order, and for the held record only after the scale is frozen.
    emit receives one map at a time. Any failure leaves uncommitted partial
    output; neither this API nor its return value is a protected runtime.
    """
    require(callable(load_record) and callable(emit), "explicit normalized source and staged output callbacks")
    require(type(fold_key) is str and FOLD_KEY.fullmatch(fold_key), "opaque fold key required")
    partitions = validate_intake(intake)
    positive = [row for row in partitions if row[0]["declared_trials"] > 0]
    require(len(positive) == 48 and held_record_id in {row[0]["record_id"] for row in positive},
            "held fold must be one of the complete 48 positive records")
    train, held = [r for r in positive if r[0]["record_id"] != held_record_id], next(
        r for r in positive if r[0]["record_id"] == held_record_id)
    scale, training_maps, training_valid_pixels, training_invalid_pixels = 0.0, 0, 0, 0
    for _, record, _, _, _ in train:
        normalized = load_record(record["record_id"])
        for _, deltas, _ in record_deltas(record, normalized):
            training_maps += 1
            for value in deltas:
                if value is None:
                    training_invalid_pixels += 1
                else:
                    training_valid_pixels += 1
                    scale = max(scale, abs(value))
        del normalized
    require(finite(scale) and scale > 0, "zero/nonfinite training scale refuses whole fold before held read")
    # No held pixel callback has occurred before this point.
    _, record, queries, calibration_count, excluded = held
    calibration_ids = {t["query_id"] for t in record["trials"] if t["disposition"] == "eligible"} - {
        t["query_id"] for t in queries}
    require(len(calibration_ids) == calibration_count == 8, "exact eight calibration maps")
    normalized = load_record(held_record_id)
    counts = {"calibration_maps": 0, "query_maps": 0, "invalid_pixels": 0, "saturated_pixels": 0}
    for trial, deltas, metadata in record_deltas(record, normalized):
        rgb, invalid, saturated = [], 0, 0
        for value in deltas:
            pixel, clipped = encode(value, scale)
            rgb.extend(pixel)
            invalid += value is None
            saturated += clipped
        calibration = trial["query_id"] in calibration_ids
        payload = {"schema": "fus_fullfield_map_v1", "fold_key": fold_key, "query_id": trial["query_id"],
                   "role": "calibration" if calibration else "query", "scale": scale, **metadata,
                   "rgb": bytes(rgb), "invalid_pixels": invalid, "saturated_pixels": saturated}
        if calibration:
            payload["direction"] = trial["direction"]
        emit(payload)
        counts["calibration_maps" if calibration else "query_maps"] += 1
        counts["invalid_pixels"] += invalid
        counts["saturated_pixels"] += saturated
    require(counts["calibration_maps"] == 8 and counts["query_maps"] == len(queries), "complete held map support")
    return {"schema": "fus_fullfield_fold_receipt_v1", "status": "source_component_completed",
            "fold_key": fold_key, "roster_records": 49, "positive_records": 48,
            "declared_source_trials": 20622, "training_records": 47, "training_maps": training_maps,
            "training_valid_pixels": training_valid_pixels, "training_invalid_pixels": training_invalid_pixels,
            "held_adjudicated_exclusions": excluded, "scale": scale, **counts,
            "native_source_authenticated": False, "full_resolution_delivery_qualified": False,
            "protected_evaluation_established": False, "scientifically_qualified": False}
