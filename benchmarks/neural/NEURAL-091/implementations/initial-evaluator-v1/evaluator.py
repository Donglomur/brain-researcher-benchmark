"""NEURAL-091: prospective Allen Neuropixels stimulus-family evaluation.

Standard-library implementation; accepts an explicitly pinned, locally exported
session bundle. Does not acquire recordings or claim native-data qualification.
"""
import argparse
import bisect
import hashlib
import json
import math
import os
import random
import statistics
from collections import defaultdict
from pathlib import Path

TASK_ID = "NEURAL-091"
SOURCE = "Allen Visual Coding Neuropixels"
SDK_PIN = "a9b5c685396126d9748f1ccecf7c00f440569f69"
CONTRACT_SHA256 = "b42c6803c1aede42efe4f65e422494247b355b2dd2799e5817ef61d759cc2445"
STIMULUS_FIELDS = {"orientation", "contrast", "spatial_frequency", "temporal_frequency",
                   "phase", "frame", "color"}
PUBLIC_FIELDS = {"key", "mouse_id", "family", "condition_id", "start_time", "stop_time",
                 "exposure_seconds", "stimulus", "running_speed", "running_coverage",
                 "pupil_area", "pupil_coverage"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, name, minimum=None):
    require(type(value) in (int, float) and math.isfinite(value), name + " must be finite")
    require(minimum is None or value >= minimum, name + " below minimum")
    return float(value)


def identifier(value, name):
    require(isinstance(value, str) and bool(value) and len(value) <= 200, name + " must be a nonempty string")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def unique(values, name):
    require(len(values) == len(set(values)), "duplicate " + name)


def interval(row):
    start = number(row["start_time"], "start_time")
    stop = number(row["stop_time"], "stop_time")
    require(stop > start, "interval must have positive duration")
    return start, stop


def subtract(start, stop, invalid):
    """Union-subtract half-open invalid intervals; never double subtract overlap."""
    pieces = [(start, stop)]
    for left, right in sorted(invalid):
        out = []
        for a, b in pieces:
            if right <= a or left >= b:
                out.append((a, b))
            else:
                if a < left:
                    out.append((a, left))
                if right < b:
                    out.append((right, b))
        pieces = out
    return pieces


def overlap(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def state_intervals(session, max_age):
    running = []
    for row in session["running_samples"]:
        a, b = interval(row)
        value = row["velocity"]
        running.append((a, b, None if value is None else number(value, "running velocity")))
    running.sort()
    require(all(a[1] <= b[0] for a, b in zip(running, running[1:])), "overlapping running samples")
    pupils = session["pupil_samples"]
    times = [number(row["time"], "pupil time") for row in pupils]
    require(all(a < b for a, b in zip(times, times[1:])), "pupil timestamps must increase strictly")
    pupil = []
    for index, row in enumerate(pupils):
        value = row["pupil_area"]
        value = None if value is None else number(value, "pupil area", 0)
        a = times[index]
        b = min(a + max_age, times[index + 1] if index + 1 < len(times) else a + max_age)
        pupil.append((a, b, value))
    return running, pupil


def state_summary(pieces, samples):
    weighted, covered = 0.0, 0.0
    exposure = math.fsum(b - a for a, b in pieces)
    for a, b, value in samples:
        if value is not None:
            width = math.fsum(overlap((a, b), piece) for piece in pieces)
            weighted += width * value
            covered += width
    return (weighted / covered if covered else None, covered / exposure)


class StateIndex:
    """Find only samples intersecting a past-state window, with no unit loop."""

    def __init__(self, samples):
        self.samples = samples
        self.starts = [row[0] for row in samples]
        self.stops = [row[1] for row in samples]

    def summary(self, start, stop, completed_only=False):
        first = bisect.bisect_right(self.stops, start)
        last = bisect.bisect_left(self.starts, stop)
        if completed_only:
            last = min(last, bisect.bisect_right(self.stops, stop))
        return state_summary([(start, stop)], self.samples[first:last])


def prepare(bundle, protocol):
    """Build public allowed inputs and private targets from a complete pinned roster.

    Raw sessions contain source spike times. The only cohort selection is the
    explicit frozen session/unit roster; no response-derived eligibility exists.
    """
    require(bundle["source"] == SOURCE, "requires spike-recorded Allen Visual Coding Neuropixels")
    require(protocol["schema_version"] == 1, "unsupported protocol")
    require(protocol["contract_sha256"] == CONTRACT_SHA256, "wrong canonical contract")
    require(protocol["sdk_commit"] == SDK_PIN, "wrong SDK pin")
    require(protocol["session_type"] in {"brain_observatory_1.1", "functional_connectivity"}, "unsupported Neuropixels session type")
    families = protocol["heldout_families"]
    require(isinstance(families, list) and families, "heldout families required")
    for family in families:
        identifier(family, "family")
    unique(families, "family")
    require("invalid_presentation" not in families, "invalid family")
    guard = number(protocol["temporal_guard_seconds"], "temporal guard", 0)
    max_age = number(protocol["pupil_max_age_seconds"], "pupil max age", 0)
    require(max_age > 0, "pupil max age must be positive")
    state_history = number(protocol["state_history_seconds"], "state history", 0)
    require(state_history > 0, "state history must be positive")
    prior = number(protocol["state_prior_seconds"], "state prior", 0)
    require(prior > 0, "state prior must be positive")
    identifier(protocol["quality_selection_policy"], "quality selection policy")
    roster = protocol["sessions"]
    require(isinstance(roster, list) and roster, "explicit selected session roster required")
    unique([row["session_id"] for row in roster], "roster session")
    sessions = bundle["sessions"]
    unique([row["session_id"] for row in sessions], "export session")
    require({row["session_id"] for row in sessions} == {row["session_id"] for row in roster}, "session roster mismatch")
    by_id = {row["session_id"]: row for row in sessions}
    train, query, targets, audit = [], [], [], []
    train_groups, query_groups = set(), set()
    for selected in roster:
        sid = identifier(selected["session_id"], "session_id")
        mouse = identifier(selected["mouse_id"], "mouse_id")
        session = by_id[sid]
        require(session["mouse_id"] == mouse, "mouse identity mismatch")
        require(session["session_type"] == protocol["session_type"], "mixed or unexpected session type")
        for field in ("source_file_sha256", "source_file_bytes"):
            require(session[field] == selected[field], "source asset pin mismatch")
        require(isinstance(selected["source_file_sha256"], str) and len(selected["source_file_sha256"]) == 64
                and all(c in "0123456789abcdef" for c in selected["source_file_sha256"]), "invalid recording hash")
        require(type(selected["source_file_bytes"]) is int and selected["source_file_bytes"] > 0, "invalid recording size")
        units = session["units"]
        unique([u["unit_id"] for u in units], "unit")
        unique(selected["unit_ids"], "selected unit")
        require(selected["unit_ids"] and set(selected["unit_ids"]) == {u["unit_id"] for u in units}, "unit roster mismatch")
        for unit in units:
            identifier(unit["unit_id"], "unit_id")
            identifier(unit["probe_id"], "probe_id")
            spikes = [number(t, "spike time") for t in unit["spike_times"]]
            require(all(a <= b for a, b in zip(spikes, spikes[1:])), "spike times must be sorted")
        presentations = session["presentations"]
        unique([p["presentation_id"] for p in presentations], "presentation")
        require(bool(presentations), "empty presentation table")
        require(set(selected["presentation_ids"]) == {p["presentation_id"] for p in presentations}, "presentation roster mismatch")
        unique(selected["presentation_ids"], "selected presentation")
        require(selected["presentation_table_sha256"] == digest(presentations), "presentation table pin mismatch")
        presentation_intervals = sorted(interval(p) for p in presentations)
        require(all(a[1] <= b[0] for a, b in zip(presentation_intervals, presentation_intervals[1:])), "overlapping stimulus presentations")
        invalids = []
        known_probes = {u["probe_id"] for u in units}
        for row in session["invalid_intervals"]:
            a, b = interval(row)
            tag = row["scope"]
            require(tag in {"stimulus", "all_probes"} | known_probes, "unknown invalid interval scope")
            invalids.append((a, b, tag))
        heldout = []
        repeat_families = defaultdict(set)
        for p in presentations:
            identifier(p["presentation_id"], "presentation_id")
            identifier(p["stimulus_name"], "stimulus_name")
            interval(p)
            if p["stimulus_name"] != "invalid_presentation":
                identifier(p["stimulus_condition_id"], "stimulus_condition_id")
                repeat_families[p["stimulus_condition_id"]].add(p["stimulus_name"])
            if p["stimulus_name"] in families:
                heldout.append(p)
        require(all(len(f) == 1 for f in repeat_families.values()), "repeat condition crosses stimulus families")
        require({p["stimulus_name"] for p in heldout} == set(families), "each session must contain all heldout families")
        heldout_times = sorted(interval(p) for p in heldout)
        guard_starts = [a - guard for a, _ in heldout_times]
        guard_stops = [b + guard for _, b in heldout_times]
        running, pupil = state_intervals(session, max_age)
        running_index, pupil_index = StateIndex(running), StateIndex(pupil)
        for p in presentations:
            a, b = interval(p)
            family = p["stimulus_name"]
            reason = None
            guard_index = bisect.bisect_left(guard_starts, b) - 1
            if family == "invalid_presentation" or any(tag == "stimulus" and max(a, x) <= min(b, y) for x, y, tag in invalids):
                reason = "invalid_stimulus"
            elif family not in families and guard_index >= 0 and guard_stops[guard_index] > a:
                reason = "temporal_guard"
            if reason:
                audit.append({"session_id": sid, "presentation_id": p["presentation_id"], "reason": reason})
                continue
            stimulus = p.get("stimulus", {})
            require(isinstance(stimulus, dict) and set(stimulus) <= STIMULUS_FIELDS, "unapproved stimulus field")
            for value in stimulus.values():
                if value is not None:
                    number(value, "stimulus value")
            # State is shared across units and depends only on pre-onset samples.
            run, run_coverage = running_index.summary(a - state_history, a, completed_only=True)
            eye, eye_coverage = pupil_index.summary(a - state_history, a)
            for unit in units:
                uid = unit["unit_id"]
                pieces = subtract(a, b, [(x, y) for x, y, tag in invalids if tag in {"all_probes", unit["probe_id"]}])
                exposure = math.fsum(y - x for x, y in pieces)
                key = [sid, uid, p["presentation_id"]]
                if not exposure:
                    audit.append({"key": key, "reason": "zero_valid_exposure"})
                    continue
                spikes = unit["spike_times"]
                count = sum(bisect.bisect_left(spikes, y) - bisect.bisect_left(spikes, x) for x, y in pieces)
                row = {"key": key, "mouse_id": mouse, "family": family, "condition_id": p["stimulus_condition_id"],
                       "start_time": a, "stop_time": b, "exposure_seconds": exposure,
                       "stimulus": stimulus.copy(), "running_speed": run, "running_coverage": run_coverage,
                       "pupil_area": eye, "pupil_coverage": eye_coverage}
                if family in families:
                    query.append(row)
                    targets.append({"key": key, "count": count})
                    query_groups.add((sid, uid, family))
                else:
                    train.append(dict(row, count=count))
                    train_groups.add((sid, uid))
        for unit in units:
            group = (sid, unit["unit_id"])
            require(group in train_groups, "selected unit lacks calibration exposure")
            for family in families:
                require(group + (family,) in query_groups, "selected unit lacks heldout family exposure")
    public = {"schema_version": 1, "task_id": TASK_ID, "protocol_sha256": digest(protocol),
              "heldout_families": families[:], "state_prior_seconds": prior, "training": train, "query": query}
    private = {"schema_version": 1, "task_id": TASK_ID, "public_sha256": digest(public),
               "targets": targets, "exclusions": audit, "source_roster": roster}
    return public, private


def validate_public(public):
    require(public["task_id"] == TASK_ID and public["schema_version"] == 1, "wrong public packet")
    families = public["heldout_families"]
    require(isinstance(families, list) and bool(families), "nonempty heldout families required")
    for family in families:
        identifier(family, "family")
    unique(families, "heldout family")
    require({row["family"] for row in public["query"]} == set(families), "heldout family coverage mismatch")
    all_keys = []
    for split in ("training", "query"):
        require(bool(public[split]), "empty " + split)
        for row in public[split]:
            require(set(row) == PUBLIC_FIELDS | ({"count"} if split == "training" else set()), "unapproved public observation fields")
            key = row["key"]
            require(isinstance(key, list) and len(key) == 3, "key must be session/unit/presentation")
            for part in key:
                identifier(part, "key part")
            all_keys.append(tuple(key))
            number(row["exposure_seconds"], "exposure", 0)
            require(row["exposure_seconds"] > 0, "zero exposure")
            a, b = interval(row)
            require(row["exposure_seconds"] <= b - a + 1e-12, "exposure exceeds presentation duration")
            identifier(row["mouse_id"], "mouse")
            identifier(row["condition_id"], "condition")
            require((row["family"] in public["heldout_families"]) == (split == "query"), "family split violation")
            require(isinstance(row["stimulus"], dict) and set(row["stimulus"]) <= STIMULUS_FIELDS, "unapproved public stimulus fields")
            for value in row["stimulus"].values():
                if value is not None:
                    number(value, "stimulus value")
            for covariate in ("running_speed", "pupil_area"):
                if row[covariate] is not None:
                    number(row[covariate], covariate)
            for covariate, coverage in (("running_speed", "running_coverage"), ("pupil_area", "pupil_coverage")):
                require(number(row[coverage], coverage, 0) <= 1 + 1e-12, "coverage exceeds one")
                require((row[covariate] is None) == (row[coverage] == 0), "state missingness/coverage mismatch")
            if split == "query":
                require("count" not in row, "query target leaked")
            else:
                require(type(row["count"]) is int and row["count"] >= 0, "invalid training count")
    unique(all_keys, "observation")
    session_mice = defaultdict(set)
    for row in public["training"] + public["query"]:
        session_mice[row["key"][0]].add(row["mouse_id"])
    require(all(len(mice) == 1 for mice in session_mice.values()), "inconsistent session/mouse identity")
    repeats = defaultdict(set)
    for split in ("training", "query"):
        for row in public[split]:
            repeats[(row["key"][0], row["condition_id"])].add(split)
    require(all(len(splits) == 1 for splits in repeats.values()), "repeated condition crosses split")
    calibrated = {(tuple(t["key"][:2]), t["mouse_id"]) for t in public["training"]}
    for row in public["query"]:
        require((tuple(row["key"][:2]), row["mouse_id"]) in calibrated, "uncalibrated query unit")


def fit_controls(public):
    """Training-only mean and shrinkage state-cell firing-rate controls."""
    validate_public(public)
    prior = number(public["state_prior_seconds"], "state prior", 0)
    require(prior > 0, "state prior must be positive")
    grouped = defaultdict(list)
    for row in public["training"]:
        grouped[tuple(row["key"][:2])].append(row)
    models = {}
    for group, rows in grouped.items():
        exposure = math.fsum(row["exposure_seconds"] for row in rows)
        rate = sum(row["count"] for row in rows) / exposure
        require(math.isfinite(rate), "nonfinite fitted rate")
        medians = {}
        for name in ("running_speed", "pupil_area"):
            values = [row[name] for row in rows if row[name] is not None]
            medians[name] = statistics.median(values) if values else None
        cells = defaultdict(lambda: [0, 0.0])
        for row in rows:
            cell = state_cell(row, medians)
            cells[cell][0] += row["count"]
            cells[cell][1] += row["exposure_seconds"]
        models[group] = (rate, medians, cells)
    mean_predictions, state_predictions = [], []
    for row in public["query"]:
        rate, medians, cells = models[tuple(row["key"][:2])]
        count, exposure = cells.get(state_cell(row, medians), (0, 0.0))
        state_rate = (count + prior * rate) / (exposure + prior)
        require(math.isfinite(state_rate), "nonfinite state rate")
        mean_predictions.append({"key": row["key"], "rate_hz": rate})
        state_predictions.append({"key": row["key"], "rate_hz": state_rate})
    return {"mean_rate": mean_predictions, "running_pupil": state_predictions}


def state_cell(row, medians):
    return tuple("missing" if row[name] is None or medians[name] is None else
                 "low" if row[name] <= medians[name] else "high"
                 for name in ("running_speed", "pupil_area"))


def keyed_rows(rows, expected, field):
    require(isinstance(rows, list), "rows must be a list")
    keys = []
    result = {}
    for row in rows:
        require(set(row) == {"key", field}, "unexpected output fields")
        key = row["key"]
        require(isinstance(key, list) and len(key) == 3 and all(isinstance(x, str) for x in key), "malformed key")
        key = tuple(key)
        keys.append(key)
        result[key] = row[field]
    unique(keys, "output key")
    require(set(keys) == expected, "output keys must exactly cover the protected query")
    return result


def aggregate(rows):
    mice = defaultdict(list)
    for row in rows:
        mice[row["mouse_id"]].append(row)
    records = []
    for mouse, group in sorted(mice.items()):
        spikes = sum(r["count"] for r in group)
        undefined = sorted({r["undefined"] for r in group if r["undefined"]})
        if not spikes:
            undefined.append("zero_heldout_spikes")
        gain = math.fsum(r["gain"] for r in group) if not undefined and not any(r["negative_infinity"] for r in group) else None
        value = gain / (spikes * math.log(2)) if gain is not None else None
        records.append({"mouse_id": mouse, "spikes": spikes, "observations": len(group),
                        "bits_per_spike": value,
                        "status": "undefined:" + ",".join(undefined) if undefined else
                        "negative_infinity" if value is None else "finite"})
    values = [r["bits_per_spike"] for r in records]
    status = "undefined" if any(r["status"].startswith("undefined") for r in records) else "negative_infinity" if None in values else "finite"
    return {"mouse_count": len(records), "mice": records, "status": status,
            "mouse_macro_bits_per_spike": math.fsum(values) / len(values) if status == "finite" else None}


def score(public, private, predictions, bootstrap_seed=0, bootstrap_replicates=1000):
    validate_public(public)
    require(private["task_id"] == TASK_ID and private["public_sha256"] == digest(public), "protected packet binding mismatch")
    require(type(bootstrap_seed) is int, "bootstrap seed must be integer")
    require(type(bootstrap_replicates) is int and 1 <= bootstrap_replicates <= 100000, "invalid bootstrap count")
    expected = {tuple(row["key"]) for row in public["query"]}
    rates = keyed_rows(predictions, expected, "rate_hz")
    counts = keyed_rows(private["targets"], expected, "count")
    means = {tuple(row["key"]): row["rate_hz"] for row in fit_controls(public)["mean_rate"]}
    results = []
    for row in public["query"]:
        key = tuple(row["key"])
        rate = number(rates[key], "predicted rate", 0)
        count = counts[key]
        require(type(count) is int and count >= 0, "target count must be a nonnegative integer")
        exposure = row["exposure_seconds"]
        reference = means[key]
        undefined = "zero_training_rate_positive_target" if reference == 0 and count > 0 else None
        negative = rate == 0 and count > 0 and not undefined
        gain = -exposure * (rate - reference)
        if count and not undefined and not negative:
            gain += count * (math.log(rate) - math.log(reference))
        require(math.isfinite(gain), "nonfinite likelihood gain from numeric overflow")
        results.append({"mouse_id": row["mouse_id"], "family": row["family"], "count": count,
                        "gain": gain, "undefined": undefined, "negative_infinity": negative})
    overall = aggregate(results)
    families = {family: aggregate([r for r in results if r["family"] == family]) for family in public["heldout_families"]}
    interval_result = {"method": "mouse_percentile_bootstrap", "seed": bootstrap_seed,
                       "replicates": bootstrap_replicates, "confidence": 0.95, "limits": None}
    if overall["status"] == "finite" and overall["mouse_count"] >= 2:
        rng = random.Random(bootstrap_seed)
        values = [row["bits_per_spike"] for row in overall["mice"]]
        draws = sorted(math.fsum(rng.choices(values, k=len(values))) / len(values) for _ in range(bootstrap_replicates))
        def quantile(p):
            pos = (len(draws) - 1) * p
            low = int(pos)
            return draws[low] + (draws[min(low + 1, len(draws) - 1)] - draws[low]) * (pos - low)
        interval_result["limits"] = [quantile(0.025), quantile(0.975)]
    return {"task_id": TASK_ID, "scope": "construction_component_only", "research_qualified": False,
            "overall": overall, "stimulus_families": families, "uncertainty": interval_result,
            "exclusion_count": len(private["exclusions"])}


def read_json(path):
    def reject_constant(value):
        raise ValueError("nonfinite JSON constant: " + value)
    def reject_duplicate_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON object key")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), parse_constant=reject_constant, object_pairs_hook=reject_duplicate_pairs)


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    for option in ("bundle", "protocol", "public", "private"):
        prepare_parser.add_argument("--" + option, required=True)
    control_parser = sub.add_parser("controls")
    control_parser.add_argument("--public", required=True)
    control_parser.add_argument("--output", required=True)
    score_parser = sub.add_parser("score")
    for option in ("public", "private", "predictions", "output"):
        score_parser.add_argument("--" + option, required=True)
    score_parser.add_argument("--bootstrap-seed", type=int, default=0)
    args = parser.parse_args()
    if args.command == "prepare":
        require(Path(args.public).resolve() != Path(args.private).resolve(), "public and private outputs must differ")
        public, private = prepare(read_json(args.bundle), read_json(args.protocol))
        write_json(args.public, public)
        fd = os.open(args.private, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(private, handle, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
    elif args.command == "controls":
        write_json(args.output, fit_controls(read_json(args.public)))
    else:
        write_json(args.output, score(read_json(args.public), read_json(args.private), read_json(args.predictions), args.bootstrap_seed))


if __name__ == "__main__":
    main()
