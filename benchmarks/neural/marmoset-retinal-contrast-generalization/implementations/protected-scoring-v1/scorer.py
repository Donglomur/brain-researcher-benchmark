"""Owner-only scoring of complete, aligned, already frozen response predictions.

No paths, source loaders, model execution, smoothing, cropping or selection.
The caller owns target custody and authentication of every external identity.
"""
import hashlib
import json
import math
import statistics
import struct

TASK = "marmoset-retinal-contrast-generalization"
DATASETS = {"20220412_SN_252MEA6010_le_s4", "20220426_SS_252MEA6010_le_n3"}
CLASSES = {"off_midget": 51, "off_parasol": 69, "on_parasol": 35, "large_off_pooled": 15}
TARGET_DOMAIN = {
    "wn_to_wn": "WN", "nm_to_nm_source_only": "NM",
    "nm_to_nm_wn_calibrated_author": "NM", "wn_to_nm_source_only": "NM",
    "nm_to_wn_source_only": "WN", "nm_to_wn_wn_assisted": "WN",
}
DTYPES = {"|u1": "B", "|i1": "b", "<u2": "H", "<i2": "h", "<u4": "I",
          "<i4": "i", "<u8": "Q", "<i8": "q", "<f4": "f", "<f8": "d"}
UNIT = "spike_count_per_stimulus_update"


class InputError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise InputError(message)


def exact(obj, names, label):
    need(type(obj) is dict and set(obj) == set(names.split()), label + ": exact fields")


def hex_id(value, length=32):
    need(type(value) is str and len(value) == length and
         all(x in "0123456789abcdef" for x in value), "invalid opaque identity")


def ids(values):
    need(type(values) is list and values, "complete nonempty identity list")
    for value in values:
        hex_id(value)
    need(len(set(values)) == len(values), "duplicate identity")


def fingerprint(value):
    """Canonical content identity; byte bodies become length/SHA descriptors.

    These descriptors are used only for hashing. They are never accepted in
    place of actual bytes by the scorer. Identity is not source authentication.
    """
    def project(obj):
        if type(obj) is bytes:
            return {"bytes": len(obj), "sha256": hashlib.sha256(obj).hexdigest()}
        if type(obj) is dict:
            return {key: project(item) for key, item in obj.items()}
        if type(obj) is list:
            return [project(item) for item in obj]
        return obj
    try:
        raw = json.dumps(project(value), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise InputError("noncanonical operand") from None
    return hashlib.sha256(raw).hexdigest()


def pinned(value, expected):
    hex_id(expected, 64)
    need(fingerprint(value) == expected, "external operand identity mismatch")


def number(value, *, count=False):
    need(type(value) in (int, float), "primitive numerical value required")
    try:
        converted = float(value)
    except OverflowError:
        raise InputError("numerical overflow") from None
    need(math.isfinite(converted) and converted >= 0, "finite nonnegative count units")
    if type(value) is int:
        need(int(converted) == value, "integer cannot be represented exactly in binary64")
    if count:
        need(converted.is_integer(), "targets require individual-repeat integral counts")
    return converted


def validate_policy(policy):
    exact(policy, "schema task_id source_release condition training_policy_sha256 "
          "cohort_evidence_sha256 complete_stream_census_sha256 rate_floor "
          "coverage_policy preparations streams", "policy")
    need(policy["schema"] == "marmoset-protected-score-policy-v1" and
         policy["task_id"] == TASK and policy["source_release"] == "10.12751/g-node.t43ph1",
         "original task/release required")
    need(type(policy["condition"]) is str and policy["condition"] in TARGET_DOMAIN,
         "registered information condition required")
    for key in ("training_policy_sha256", "cohort_evidence_sha256", "complete_stream_census_sha256"):
        hex_id(policy[key], 64)
    need(number(policy["rate_floor"]) > 0, "positive predeclared count floor")
    need(policy["coverage_policy"] == "all_cells_or_null", "fixed undefined-coverage policy")
    need(type(policy["preparations"]) is list and len(policy["preparations"]) == 2,
         "both original preparations required")
    preparations, all_cells = {}, set()
    census = dict.fromkeys(CLASSES, 0)
    for prep in policy["preparations"]:
        exact(prep, "dataset cells", "preparation")
        need(type(prep["dataset"]) is str and prep["dataset"] in DATASETS and
             prep["dataset"] not in preparations, "original preparation identity")
        need(type(prep["cells"]) is list and prep["cells"], "full selected roster")
        for cell in prep["cells"]:
            exact(cell, "cell_id published_class", "cell")
            hex_id(cell["cell_id"])
            need(cell["cell_id"] not in all_cells and type(cell["published_class"]) is str
                 and cell["published_class"] in CLASSES, "unique classified cell")
            all_cells.add(cell["cell_id"])
            census[cell["published_class"]] += 1
        preparations[prep["dataset"]] = prep["cells"]
    need(set(preparations) == DATASETS and census == CLASSES, "complete fixed 170-cell census")
    need(type(policy["streams"]) is list and policy["streams"], "complete target stream census")
    streams, seen = {}, set()
    for stream in policy["streams"]:
        exact(stream, "stream_id dataset stimulus seed sequence_sha256 repeat_ids "
              "repeat_sequence_sha256 frame_ids alignment_evidence_sha256", "stream")
        hex_id(stream["stream_id"])
        need(stream["stream_id"] not in streams, "duplicate stream identity")
        need(type(stream["dataset"]) is str and stream["dataset"] in preparations and
             stream["stimulus"] == TARGET_DOMAIN[policy["condition"]], "condition target domain")
        seed = stream["seed"]
        need((stream["stimulus"] == "WN" and seed is None) or
             (stream["stimulus"] == "NM" and type(seed) is int and seed in (1, 2)), "source seed")
        key = (stream["dataset"], seed)
        need(key not in seen, "duplicate preparation/seed")
        seen.add(key)
        ids(stream["frame_ids"]); ids(stream["repeat_ids"])
        need(len(stream["frame_ids"]) >= 2, "at least two eligible updates")
        hex_id(stream["sequence_sha256"], 64)
        hex_id(stream["alignment_evidence_sha256"], 64)
        need(type(stream["repeat_sequence_sha256"]) is list and
             stream["repeat_sequence_sha256"] == [stream["sequence_sha256"]] * len(stream["repeat_ids"]),
             "only identical frozen stimulus sequences may be repeat-averaged")
        streams[stream["stream_id"]] = stream
    need({s["dataset"] for s in streams.values()} == DATASETS, "every preparation must have target support")
    return preparations, streams


def validate_bundle(bundle, policy, preparations, streams, *, target=False):
    common = "schema task_id condition training_policy_sha256 unit streams"
    exact(bundle, common if target else common + " model_sha256", "bundle")
    need(bundle["schema"] == ("marmoset-target-counts-v1" if target else "marmoset-predictions-v1")
         and bundle["task_id"] == TASK and bundle["condition"] == policy["condition"]
         and bundle["training_policy_sha256"] == policy["training_policy_sha256"]
         and bundle["unit"] == UNIT, "same task, condition, calibration and count units required")
    if not target:
        hex_id(bundle["model_sha256"], 64)
    need(type(bundle["streams"]) is list and len(bundle["streams"]) == len(streams),
         "every declared stream required")
    result = {}
    for packet in bundle["streams"]:
        fields = "stream_id cell_ids frame_ids dtype values"
        exact(packet, fields + " repeat_ids" if target else fields, "packet")
        ident = packet["stream_id"]; hex_id(ident)
        need(ident in streams and ident not in result, "unknown/duplicate target stream")
        stream = streams[ident]
        need(packet["cell_ids"] == [c["cell_id"] for c in preparations[stream["dataset"]]]
             and packet["frame_ids"] == stream["frame_ids"], "exact cell/update order required")
        repeats = len(stream["repeat_ids"]) if target else 1
        if target:
            need(packet["repeat_ids"] == stream["repeat_ids"], "exact repeat order required")
        need(type(packet["dtype"]) is str and packet["dtype"] in DTYPES, "primitive little-endian dtype")
        code = DTYPES[packet["dtype"]]
        width = struct.calcsize("<" + code)
        extent = len(packet["cell_ids"]) * repeats * len(packet["frame_ids"])
        need(type(packet["values"]) is bytes and len(packet["values"]) == extent * width,
             "complete C-order cells/repeats/updates buffer")
        for (value,) in struct.iter_unpack("<" + code, packet["values"]):
            number(value, count=target)
        result[ident] = packet
    return result


def pearson(x, y):
    """Stable scaling before centering, with constants explicitly undefined."""
    def centered(values):
        low, high = min(values), max(values)
        if low == high:
            return None
        scaled = [(value - low) / (high - low) for value in values]
        mean = math.fsum(scaled) / len(scaled)
        return [value - mean for value in scaled]
    a, b = centered(x), centered(y)
    reasons = []
    if a is None:
        reasons.append("constant_prediction")
    if b is None:
        reasons.append("constant_repeat_average_target")
    if reasons:
        return {"r": None, "undefined": reasons}
    norm_a = math.sqrt(math.fsum(v * v for v in a))
    norm_b = math.sqrt(math.fsum(v * v for v in b))
    r = math.fsum((v / norm_a) * (w / norm_b) for v, w in zip(a, b))
    need(math.isfinite(r) and abs(r) <= 1 + 1e-12, "correlation numerical failure")
    return {"r": min(1.0, max(-1.0, r)), "undefined": []}


def poisson_nll(count, expected, floor):
    """Full Poisson NLL in nats; floor affects likelihood only, never Pearson."""
    lam = max(expected, floor)
    if count == 0:
        return lam
    if count < 256:
        loss = lam - count * math.log(lam) + math.lgamma(count + 1)
    else:
        # Stirling remainder avoids cancellation of O(k log k) terms at large k.
        inv = 1.0 / count
        base = 0.5 * (math.log(2 * math.pi) + math.log(count)) + inv / 12 - inv**3 / 360 + inv**5 / 1260
        delta = (lam - count) / count
        deviance = count * (delta - math.log1p(delta)) if -0.5 <= delta <= 1 else (
            lam - count - count * (math.log(lam) - math.log(count)))
        loss = base + deviance
    need(math.isfinite(loss) and loss >= 0, "Poisson numerical range failure")
    return loss


def row_values(packet, row, repeats, frames):
    code = DTYPES[packet["dtype"]]; width = struct.calcsize("<" + code)
    start = row * repeats * frames * width
    body = memoryview(packet["values"])[start:start + repeats * frames * width]
    return [value[0] for value in struct.iter_unpack("<" + code, body)]


def summarize(rows):
    fields = ("candidate_r", "reference_r", "paired_delta_r")
    result = {"cells": len(rows)}
    for field in fields:
        values = [row[field] for row in rows if row[field] is not None]
        result[field + "_defined_cells"] = len(values)
        result[field + "_median_all_cells"] = statistics.median(values) if len(values) == len(rows) else None
    observations = sum(row["repeat_observations"] for row in rows)
    for arm in ("candidate", "reference"):
        result[arm + "_poisson_nll_per_observation"] = math.fsum(
            row[arm + "_poisson_nll"] * (row["repeat_observations"] / observations) for row in rows)
    result["repeat_observations"] = observations
    return result


def score(policy, targets, candidate, reference, *, policy_sha256, targets_sha256,
          candidate_sha256, reference_sha256):
    """Score a sealed candidate and condition-matched SC reference in owner custody.

    Externally freeze all four operand identities; hashes cannot prove freezing
    chronology, training access, census, temporal context or source authenticity.
    The report is protected test feedback and must not be sent to a live solver.
    """
    for obj, expected in ((policy, policy_sha256), (targets, targets_sha256),
                          (candidate, candidate_sha256), (reference, reference_sha256)):
        pinned(obj, expected)
    preparations, streams = validate_policy(policy)
    operands = [validate_bundle(obj, policy, preparations, streams, target=index == 0)
                for index, obj in enumerate((targets, candidate, reference))]
    rows = []
    floor = float(policy["rate_floor"])
    for dataset, cells in preparations.items():
        selected = [s for s in streams.values() if s["dataset"] == dataset]
        for row, cell in enumerate(cells):
            means, predictions = [], [[], []]
            losses, observations, stream_results = [[], []], 0, []
            for stream in selected:
                ident = stream["stream_id"]
                frames, repeats = len(stream["frame_ids"]), len(stream["repeat_ids"])
                counts = row_values(operands[0][ident], row, repeats, frames)
                # Integral summation precedes conversion; refuse lossy huge sums.
                average = [number(sum(int(counts[r * frames + f]) for r in range(repeats))) / repeats
                           for f in range(frames)]
                means.extend(average)
                item = {"stream_id": ident, "seed": stream["seed"], "updates": frames, "repeats": repeats}
                for arm, name in enumerate(("candidate", "reference")):
                    pred = row_values(operands[arm + 1][ident], row, 1, frames)
                    predictions[arm].extend(pred)
                    item[name] = pearson(pred, average)
                    # Each repeat is scored separately, including the factorial.
                    loss = math.fsum(poisson_nll(float(k), float(pred[i % frames]), floor) /
                                     (repeats * frames) for i, k in enumerate(counts))
                    losses[arm].append((loss, repeats * frames))
                observations += repeats * frames
                stream_results.append(item)
            corr = [pearson(pred, means) for pred in predictions]
            out = {"dataset": dataset, **cell, "updates": len(means), "repeat_observations": observations,
                   "candidate_r": corr[0]["r"], "reference_r": corr[1]["r"],
                   "candidate_undefined": corr[0]["undefined"], "reference_undefined": corr[1]["undefined"],
                   "paired_delta_r": None if any(c["r"] is None for c in corr) else corr[0]["r"] - corr[1]["r"],
                   "streams": stream_results}
            for arm, name in enumerate(("candidate", "reference")):
                out[name + "_poisson_nll"] = math.fsum(value * (n / observations) for value, n in losses[arm])
            rows.append(out)
    per_preparation = [{"dataset": dataset, **summarize([r for r in rows if r["dataset"] == dataset])}
                       for dataset in preparations]
    macro = {}
    for field in ("candidate_r", "reference_r", "paired_delta_r"):
        values = [p[field + "_median_all_cells"] for p in per_preparation]
        macro[field] = None if any(v is None for v in values) else math.fsum(values) / 2
    return {"schema": "marmoset-protected-score-v1", "task_id": TASK, "condition": policy["condition"],
            "policy_sha256": policy_sha256, "targets_sha256": targets_sha256,
            "candidate_sha256": candidate_sha256, "reference_sha256": reference_sha256,
            "historical_test_selected_cohort": True, "coverage_policy": "all_cells_or_null",
            "unit": UNIT, "poisson_unit": "nats_per_individual_repeat_update", "rate_floor": floor,
            "cells": rows, "preparations": per_preparation, "equal_preparation_descriptive": macro,
            "class_descriptive": [{"dataset": dataset, "published_class": label,
                **summarize(group)} for dataset in preparations for label in CLASSES
                if (group := [r for r in rows if r["dataset"] == dataset and r["published_class"] == label])],
            "limits": ["Fixed paper-selected cohort used historical WN/NM test reliability.",
                       "Two preparations are not established independent animals; no population inference.",
                       "Encoding scores do not establish direct or viewer-mediated neural understanding.",
                       "Identities establish equality, not source authentication or protected execution.",
                       "No baseline fitting, significance test, pass threshold or qualification is supplied."]}
