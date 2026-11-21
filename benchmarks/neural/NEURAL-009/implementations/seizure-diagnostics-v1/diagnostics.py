"""Operator-only raw-event and tolerance diagnostics for the unchanged v1 scorer.

All intervals are half-open integer 10 Hz ticks. This adds no clinical endpoint,
protected execution or participant mode. The full evaluation retains v1 intact.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import types

ROOT = Path(__file__).resolve().parent
PREDECESSOR = ROOT.parent / "seizure-events-v1"
PREDECESSOR_CLI_SHA256 = "3b5ca6fe922a5f674a0598cd6912bae62ca139524466c42f5603c5684ae77dca"
PREDECESSOR_MANIFEST_SHA256 = "6e97b56bd2043184f53e9e9be13317ce312bae10ee213dfdd54edaeb5b32fb62"


def load_predecessor():
    """Reuse the exact reviewed loader and its unchanged source closure."""
    blob = (PREDECESSOR / "cli.py").read_bytes()
    if hashlib.sha256(blob).hexdigest() != PREDECESSOR_CLI_SHA256:
        raise ValueError("Predecessor loader identity mismatch")
    cli = types.ModuleType("neural009_diagnostics_predecessor_cli")
    cli.__file__ = str(PREDECESSOR / "cli.py")
    exec(compile(blob, cli.__file__, "exec"), cli.__dict__)
    core, _ = cli.load_verified_core(PREDECESSOR_MANIFEST_SHA256)
    return core, cli


class IntervalUnion:
    """Sorted interval union with logarithmic prefix-occupancy queries."""

    def __init__(self, intervals):
        merged = []
        for a, b in intervals:
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(b, merged[-1][1])
            else:
                merged.append([a, b])
        self.intervals = merged
        self.starts = [a for a, _ in merged]
        self.ends = [b for _, b in merged]
        self.prefix = [0]
        for a, b in merged:
            self.prefix.append(self.prefix[-1] + b - a)

    def before(self, tick):
        n = bisect_right(self.ends, tick)
        partial = max(0, tick - self.starts[n]) if n < len(self.starts) else 0
        return self.prefix[n] + partial

    def overlap(self, a, b):
        return self.before(b) - self.before(a)

    def first(self, a, b):
        if b <= a:
            return None
        n = bisect_right(self.ends, a)
        if n < len(self.starts) and self.starts[n] < b:
            return max(a, self.starts[n]), self.starts[n]
        return None


def _intersection(left, right):
    """Intersect sorted disjoint unions without allocating a duration-sized mask."""
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a, b = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
        if a < b:
            result.append([a, b])
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return result


def _tick_events(events):
    return [[round(a * 10), round(b * 10)] for a, b in events]


def diagnose_record(reference, prediction, observed_ticks, *, _core=None, _engine=None):
    """Supplement v1 with raw misses/delays and exact processed credit locations.

    Delays use the decision endpoint of the first positive bin that intersects
    each raw event. They are conditional on overlap, never imputed for misses.
    An already-active alarm is identified separately from a new alarm transition.
    """
    core = _core or load_predecessor()[0]
    ticks = core._integer(observed_ticks, "Observed ticks", minimum=1)
    ref = core._intervals(reference, ticks, "Reference")
    hyp = core._intervals(prediction, ticks, "Prediction", core.CandidateError)
    policy = core.recommended_policy()
    Annotation, scoring = _engine or core._upstream()
    parameters = scoring.EventScoring.Parameters(
        toleranceStart=policy["tolerance_start_seconds"],
        toleranceEnd=policy["tolerance_end_seconds"],
        minOverlap=policy["minimum_overlap"],
        maxEventDuration=policy["maximum_event_seconds"],
        minDurationBetweenEvents=policy["merge_gap_seconds"])
    event = scoring.EventScoring(
        Annotation([(a / 10, b / 10) for a, b in ref], 10, ticks),
        Annotation([(a / 10, b / 10) for a, b in hyp], 10, ticks), parameters)
    raw_prediction = IntervalUnion(hyp)
    raw_seizure_prediction = IntervalUnion(_intersection(IntervalUnion(ref).intervals,
                                                       raw_prediction.intervals))
    raw_events = []
    for ordinal, (a, b) in enumerate(ref):
        first = raw_prediction.first(a, b)
        hit, alarm_start = first if first is not None else (None, None)
        raw_events.append({
            "raw_event_ordinal": ordinal, "interval_ticks": [a, b],
            "has_in_event_positive_bin": hit is not None,
            "first_positive_bin_start_tick": hit,
            "first_positive_decision_tick": hit + 1 if hit is not None else None,
            "decision_delay_seconds": (hit + 1 - a) / 10 if hit is not None else None,
            "positive_run_start_offset_seconds": (alarm_start - a) / 10 if first is not None else None,
            "alarm_already_active_before_onset": alarm_start < a if first is not None else False,
        })
    processed_prediction = IntervalUnion(_tick_events(event.hyp.events))
    extended = scoring.EventScoring._extendEvents(event.ref, parameters.toleranceStart,
                                                 parameters.toleranceEnd)
    processed_events = []
    for ordinal, ((a, b), window) in enumerate(zip(_tick_events(event.ref.events), extended.events)):
        lo, hi = round(window[0] * 10), round(window[1] * 10)
        overlap = processed_prediction.overlap(lo, hi)
        relative_overlap = (overlap / 10) / (window[1] - window[0])
        credited = relative_overlap > parameters.minOverlap + 1e-6
        early = processed_prediction.overlap(lo, a)
        inside = processed_prediction.overlap(a, b)
        late = processed_prediction.overlap(b, hi)
        location = "not_credited"
        if credited:
            if inside:
                location = "within_processed_reference"
            elif early and late:
                location = "early_and_late_only"
            elif early:
                location = "early_only"
            elif late:
                location = "late_only"
            else:
                raise AssertionError("Credited event lacks positive support")
        raw_overlap = raw_prediction.overlap(lo, hi)
        raw_would_credit = (raw_overlap / 10) / (window[1] - window[0]) > parameters.minOverlap + 1e-6
        genuine_overlap = raw_seizure_prediction.overlap(a, b)
        processed_events.append({
            "processed_event_ordinal": ordinal, "interval_ticks": [a, b],
            "extended_interval_ticks": [lo, hi], "credited": credited,
            "credit_location": location,
            "processed_positive_ticks": {"early": early, "inside": inside, "late": late},
            "raw_positive_ticks_in_extended_interval": raw_overlap,
            "raw_seizure_and_prediction_ticks_inside_processed_interval": genuine_overlap,
            "credit_requires_prediction_merging": credited and not raw_would_credit,
            "credited_without_raw_seizure_overlap": credited and genuine_overlap == 0,
        })
    if sum(row["credited"] for row in processed_events) != int(event.tp):
        raise AssertionError("Diagnostic credit disagrees with the pinned source scorer")
    return {"observed_ticks": ticks, "raw_events": raw_events,
            "processed_events": processed_events, "summary": summarize(raw_events, processed_events, ticks)}


def summarize(raw_events, processed_events, observed_ticks):
    delays = [r["decision_delay_seconds"] for r in raw_events if r["has_in_event_positive_bin"]]
    counts = {name: sum(r["credit_location"] == name for r in processed_events)
              for name in ("not_credited", "within_processed_reference", "early_only",
                           "late_only", "early_and_late_only")}
    return {
        "observed_ticks": observed_ticks,
        "raw_event_count": len(raw_events), "raw_events_with_in_event_positive_bin": len(delays),
        "raw_event_misses": len(raw_events) - len(delays),
        "raw_event_overlap_fraction": len(delays) / len(raw_events) if raw_events else None,
        "already_active_alarm_count": sum(r["alarm_already_active_before_onset"] for r in raw_events),
        "conditional_decision_delay_seconds": {
            "denominator_detected_raw_events": len(delays),
            "mean": math.fsum(delays) / len(delays) if delays else None,
            "median": statistics.median(delays) if delays else None,
            "maximum": max(delays) if delays else None},
        "processed_event_count": len(processed_events),
        "processed_event_credit_counts": counts,
        "prediction_merging_required_count": sum(r["credit_requires_prediction_merging"] for r in processed_events),
        "credited_without_raw_seizure_overlap_count": sum(r["credited_without_raw_seizure_overlap"] for r in processed_events),
    }


def evaluate(admission, policy, candidate, *, expected_policy_sha256, limits):
    """Return unchanged v1 result plus complete, alias-safe supplemental diagnostics."""
    core, _ = load_predecessor()
    primary = core.evaluate(admission, policy, candidate,
                            expected_policy_sha256=expected_policy_sha256, limits=limits)
    _, people, _ = core.source_index()
    candidates = {r["recording_id"]: r for r in candidate["records"]}
    arms = {name: {p: {"raw": [], "processed": [], "ticks": 0} for p in people}
            for name in ("candidate", "all_negative_control", "all_positive_control")}
    engine, rows = core._upstream(), []
    for record in sorted(admission["records"], key=lambda r: r["recording_id"]):
        identifier, person, ticks = record["recording_id"], record["biological_person"], record["observed_ticks"]
        predictions = {"candidate": candidates[identifier]["predicted_intervals"],
                       "all_negative_control": [], "all_positive_control": [[0, ticks]]}
        for arm, intervals in predictions.items():
            result = diagnose_record(record["reference_intervals"], intervals, ticks, _core=core, _engine=engine)
            aggregate = arms[arm][person]
            aggregate["raw"].extend(result["raw_events"])
            aggregate["processed"].extend(result["processed_events"])
            aggregate["ticks"] += ticks
            if arm == "candidate":
                rows.append({"recording_id": identifier, "biological_person": person, **result})
    summaries = {}
    for arm, persons in arms.items():
        patients = [{"biological_person": p, **summarize(v["raw"], v["processed"], v["ticks"])}
                    for p, v in sorted(persons.items())]
        undefined = [r["biological_person"] for r in patients if r["raw_event_overlap_fraction"] is None]
        summaries[arm] = {
            "patients": patients,
            "patient_macro_raw_event_overlap_fraction": None if undefined else math.fsum(
                r["raw_event_overlap_fraction"] for r in patients) / len(patients),
            "undefined_patients": undefined,
            "pooled_diagnostic": summarize([r for v in persons.values() for r in v["raw"]],
                                           [r for v in persons.values() for r in v["processed"]],
                                           sum(v["ticks"] for v in persons.values()))}
    return {"schema": "neural009_supplemental_diagnostics_v1", "task_id": "NEURAL-009",
            "primary_evaluation": primary, "record_diagnostics": rows, "arm_diagnostics": summaries,
            "predecessor_source_manifest_sha256": PREDECESSOR_MANIFEST_SHA256,
            "decision_time_policy": "10 Hz bin i is available at endpoint (i+1)/10 seconds; no hardware latency modeled.",
            "interpretation": "Conditional raw-event overlap and processed-credit audit. Delays exclude misses and include separately flagged already-active alarms. No one-to-one onset matching, causal execution verification or clinical timeliness qualification.",
            "scientific_qualification": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("admission", "candidate", "policy", "support", "limits", "output", "expected-policy-sha256"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--max-input-bytes", type=int, required=True)
    parser.add_argument("--max-output-bytes", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        core, io = load_predecessor()
        paths = [Path(getattr(args, name)).resolve() for name in
                 ("admission", "candidate", "policy", "support", "limits", "output")]
        io.need(len(set(paths)) == len(paths), "Input and output roles must be distinct paths")
        io.need(not Path(args.output).exists() and not Path(args.output).is_symlink(), "Output must be a new path")
        io.need(args.max_input_bytes > 0 and args.max_output_bytes > 0, "Positive byte budgets required")
        candidate = io.read_json(args.candidate, args.max_input_bytes)
        core.validate_candidate(candidate)
        policy = io.read_json(args.policy, args.max_input_bytes)
        core.validate_policy(policy, args.expected_policy_sha256)
        limits = io.read_json(args.limits, args.max_input_bytes)
        support = io.read_json(args.support, args.max_input_bytes)
        core.prevalidate_candidate(candidate, policy, support,
                                   expected_policy_sha256=args.expected_policy_sha256, limits=limits)
        # All public preflight precedes opening any private reference file.
        admission = io.read_json(args.admission, args.max_input_bytes)
        result = evaluate(admission, policy, candidate,
                          expected_policy_sha256=args.expected_policy_sha256, limits=limits)
        io.write_output(args.output, result, args.max_output_bytes)
        print(json.dumps({"status": "written", "scientific_qualification": False}))
        return 0
    except (ValueError, OSError, ImportError, RecursionError, KeyError, TypeError, MemoryError) as exc:
        print(json.dumps({"status": "refused", "error_type": type(exc).__name__, "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
