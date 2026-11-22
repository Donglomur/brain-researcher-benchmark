"""Complete-cohort, conditional normalized CHB-MIT event evaluation.

No EEG samples, native EDF parsing, model execution or scientific admission occur
here. The operator supplies a complete normalized reference table; candidate
sample probabilities are encoded losslessly as runs on the explicit 10 Hz grid.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import types

ROOT = Path(__file__).resolve().parent
RECORDS_SHA256 = "72b640d6a3fef4b40de255933d1403823d1655c56f93d69761105a653798fc08"
INDEX_SHA256 = "17cf3eabacbea67e8275ee062e8f1376460b9c35c4e1e1499ce709999d5e1fd5"
POLICY_FILE_SHA256 = "b05ea7b363f4969fd5f1d1230686e6dea391393637028701f9f9f7785469588e"
UPSTREAM = {
    "annotations.py": "0e7c5b05f257251a986e28c92ed2cb1d1a2532e0c28eae489f85d1c6b0f24928",
    "scoring.py": "0cb3b685c2d7add8d0cb2376d2021ace6d551591a2a31bfbd44a0281efe187c7",
}


class AdmissionError(ValueError):
    """Invalid operator-side source declaration or reference."""


class CandidateError(ValueError):
    """Invalid public candidate artifact."""


class PolicyError(ValueError):
    """Invalid or unbound prospective protocol."""


class SourceError(ValueError):
    """Current executable source identity does not match."""


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _need(condition, message, error=AdmissionError):
    if not condition:
        raise error(message)


def _keys(value, expected, name, error=AdmissionError):
    _need(isinstance(value, dict) and set(value) == set(expected),
          f"{name} has missing or unexpected fields", error)


def _integer(value, name, *, minimum=0, maximum=2**53-1, error=AdmissionError):
    _need(type(value) is int and minimum <= value <= maximum,
          f"{name} must be an exact integer in the admitted range", error)
    return value


def _number(value, name, *, minimum=0, maximum=1, error=AdmissionError):
    _need(type(value) in (int, float), f"{name} must be numeric", error)
    try:
        good = math.isfinite(value) and minimum <= value <= maximum
    except (OverflowError, TypeError):
        good = False
    _need(good, f"{name} is outside its finite admitted range", error)
    return value


def _digest(value, name, error=AdmissionError):
    _need(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
          f"{name} must be a lowercase SHA-256 digest", error)


def source_index():
    """Publisher identity metadata, not a claim that local signal files were read."""
    raw = (ROOT / "record_index.json").read_bytes()
    _need(hashlib.sha256(raw).hexdigest() == INDEX_SHA256,
          "Current source index bytes differ from the reviewed publisher map", SourceError)
    index = json.loads(raw)
    _need(index["records_sha256"] == RECORDS_SHA256, "Unexpected RECORDS identity", SourceError)
    rows = index["recordings"]
    _need(len(rows) == 686 and len({r["path"] for r in rows}) == 686,
          "Incomplete current source index", SourceError)
    people = sorted({r["biological_person"] for r in rows})
    _need(len(people) == 23 and "chb21" not in people, "Invalid biological index", SourceError)
    return {r["path"]: r for r in rows}, people, hashlib.sha256(raw).hexdigest()


def recommended_policy():
    raw = (ROOT / "recommended_policy.json").read_bytes()
    _need(hashlib.sha256(raw).hexdigest() == POLICY_FILE_SHA256,
          "Prospective profile bytes differ from the reviewed policy", SourceError)
    return json.loads(raw)


def validate_policy(policy, expected_policy_sha256):
    _digest(expected_policy_sha256, "Expected policy hash", PolicyError)
    expected = recommended_policy()
    _keys(policy, expected, "Policy", PolicyError)
    # The package implements this explicit profile, not arbitrary post-outcome
    # scorer selection. A changed threshold or tolerance needs a reviewed profile.
    try:
        same_policy = canonical_sha256(policy) == canonical_sha256(expected)
    except (ValueError, TypeError, OverflowError) as exc:
        raise PolicyError("Policy is not canonical finite JSON") from exc
    _need(same_policy, "Policy differs from the reviewed prospective profile", PolicyError)
    _need(canonical_sha256(policy) == expected_policy_sha256,
          "Policy does not match the caller's frozen identity", PolicyError)
    return policy


def _upstream():
    # Capture and execute exactly verified bytes. A .pyc cache is never selected.
    blobs = {}
    for name, digest in UPSTREAM.items():
        data = (ROOT / "vendor" / "timescoring" / name).read_bytes()
        _need(hashlib.sha256(data).hexdigest() == digest,
              "Pinned evaluator source mismatch", SourceError)
        blobs[name] = data
    namespace = "_neural009_pinned_timescoring"
    package = types.ModuleType(namespace)
    package.__path__ = []
    modules = {}
    old = {name: sys.modules.get(name) for name in
           (namespace, namespace + ".annotations", namespace + ".scoring")}
    try:
        sys.modules[namespace] = package
        for name in ("annotations", "scoring"):
            module = types.ModuleType(namespace + "." + name)
            module.__package__ = namespace
            sys.modules[module.__name__] = module
            exec(compile(blobs[name + ".py"], f"<verified-timescoring/{name}.py>", "exec"),
                 module.__dict__)
            modules[name] = module
    finally:
        for name, value in old.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return modules["annotations"].Annotation, modules["scoring"]


def _intervals(value, ticks, name, error=AdmissionError):
    _need(isinstance(value, list), f"{name} must be an interval list", error)
    previous_end = -1
    result = []
    for pair in value:
        _need(isinstance(pair, list) and len(pair) == 2, f"Malformed {name} interval", error)
        a = _integer(pair[0], name, maximum=ticks, error=error)
        b = _integer(pair[1], name, maximum=ticks, error=error)
        _need(a < b and a >= previous_end, f"{name} intervals overlap or are unordered", error)
        previous_end = b
        result.append([a, b])
    return result


def _metrics(reference_count, tp, fp, ticks):
    return {"sensitivity": tp / reference_count if reference_count else None,
            "precision": tp / (tp + fp) if tp + fp else None,
            "f1": 2 * tp / (reference_count + tp + fp) if reference_count + fp else None,
            "false_alarms_per_24_observed_hours": fp * 864000 / ticks}


def _original_event_alarm_diagnostics(reference_intervals, predicted_intervals):
    """Describe original-event alarm alignment, not tolerant counts or latency.

    Inputs are validated ordered, non-overlapping half-open integer intervals.
    Adjacent positive intervals form one alarm; original reference events stay
    separate. A positive run at tick zero has no observed antecedent and is not
    an observed rising edge. All offsets are score-grid ticks, not measured
    decision times. This reference-linked output belongs only to the evaluator.
    """
    alarms = []
    for start, end in predicted_intervals:
        if alarms and alarms[-1][1] == start:
            alarms[-1][1] = end
        else:
            alarms.append([start, end])

    events = []
    first_alarm = 0
    for index, (start, end) in enumerate(reference_intervals):
        while first_alarm < len(alarms) and alarms[first_alarm][1] <= start:
            first_alarm += 1
        active = (first_alarm < len(alarms)
                  and alarms[first_alarm][0] <= start < alarms[first_alarm][1])
        if start == 0:
            state = "positive_at_record_start" if active else "negative_at_record_start"
        elif not active:
            state = "negative"
        else:
            state = "new_alarm" if alarms[first_alarm][0] == start else "continuing_alarm"

        overlap = 0
        first_new_offset = None
        current = first_alarm
        while current < len(alarms) and alarms[current][0] < end:
            alarm_start, alarm_end = alarms[current]
            overlap += min(end, alarm_end) - max(start, alarm_start)
            if first_new_offset is None and start <= alarm_start and alarm_start > 0:
                first_new_offset = alarm_start - start
            current += 1
        events.append({"reference_event_index": index,
                       "reference_duration_ticks": end - start,
                       "onset_alarm_state": state,
                       "first_new_alarm_offset_ticks": first_new_offset,
                       "positive_overlap_ticks": overlap,
                       "no_raw_event_overlap": overlap == 0})
    return {"schema": "raw-event-alarm-diagnostics-v1", "tick_rate_hz": 10,
            "events": events}


def evaluate_record(reference_intervals_ticks, predicted_intervals_ticks, observed_ticks,
                    policy, *, _engine=None):
    """Execute the exact upstream count semantics on explicit aligned intervals.

    This low-level function accepts explicit source parameter values for independent
    source-parity controls; complete-cohort evaluate() admits only the frozen profile.
    """
    ticks = _integer(observed_ticks, "Observed ticks", minimum=1)
    _need(isinstance(policy, dict), "Missing event scoring parameters", PolicyError)
    for name in ("tolerance_start_seconds", "tolerance_end_seconds", "maximum_event_seconds", "merge_gap_seconds"):
        _need(name in policy, "Missing event scoring parameter", PolicyError)
        value = _number(policy[name], name, maximum=(2**53-1)/10, error=PolicyError)
        _need((Fraction(str(value))*10).denominator == 1, "Event parameter is off the explicit 10 Hz grid", PolicyError)
    _need(policy["maximum_event_seconds"] > 0, "Maximum event duration must be positive", PolicyError)
    _need("minimum_overlap" in policy, "Missing minimum overlap", PolicyError)
    _number(policy["minimum_overlap"], "Minimum overlap", error=PolicyError)
    ref = _intervals(reference_intervals_ticks, ticks, "Reference")
    hyp = _intervals(predicted_intervals_ticks, ticks, "Prediction", CandidateError)
    Annotation, scoring = _engine or _upstream()
    parameters = scoring.EventScoring.Parameters(
        toleranceStart=policy["tolerance_start_seconds"],
        toleranceEnd=policy["tolerance_end_seconds"],
        minOverlap=policy["minimum_overlap"],
        maxEventDuration=policy["maximum_event_seconds"],
        minDurationBetweenEvents=policy["merge_gap_seconds"])
    reference = Annotation([(a/10, b/10) for a, b in ref], 10, ticks)
    hypothesis = Annotation([(a/10, b/10) for a, b in hyp], 10, ticks)
    event = scoring.EventScoring(reference, hypothesis, parameters)
    sample = scoring.SampleScoring(reference, hypothesis, fs=10)
    return {"raw_reference_events": len(ref), "raw_predicted_events": len(hyp),
            "processed_reference_events": int(event.refTrue),
            "processed_predicted_events": len(event.hyp.events),
            "true_positives": int(event.tp), "false_positives": int(event.fp),
            "observed_ticks": ticks, "event_metrics": _metrics(int(event.refTrue), int(event.tp), int(event.fp), ticks),
            "sample_reference_positive_ticks": int(sample.refTrue),
            "sample_true_positive_ticks": int(sample.tp),
            "sample_false_positive_ticks": int(sample.fp),
            "sample_predicted_positive_ticks": int(sample.tp + sample.fp),
            "raw_event_alarm_diagnostics": _original_event_alarm_diagnostics(ref, hyp)}


def _folds(people):
    return [{"id": person, "train_people": [p for p in people if p != person],
             "test_people": [person]} for person in people]


def validate_candidate(candidate):
    """Validate public structure before the CLI opens the reference table."""
    index, people, index_sha = source_index()
    _keys(candidate, ["schema", "task_id", "source_index_sha256", "policy_sha256",
                      "support_sha256", "recipe_sha256", "records"], "Candidate", CandidateError)
    _need(candidate["schema"] == "neural009_candidate_v1" and candidate["task_id"] == "NEURAL-009",
          "Wrong candidate schema or task", CandidateError)
    _need(candidate["source_index_sha256"] == index_sha, "Wrong candidate source index", CandidateError)
    for field in ("policy_sha256", "support_sha256", "recipe_sha256"):
        _digest(candidate[field], field, CandidateError)
    _need(isinstance(candidate["records"], list) and len(candidate["records"]) == 686,
          "Candidate must cover all 686 recordings", CandidateError)
    rows = {}
    for row in candidate["records"]:
        _keys(row, ["recording_id", "biological_person", "fold_id", "score_runs",
                    "predicted_intervals"], "Candidate recording", CandidateError)
        identifier = row["recording_id"]
        _need(isinstance(identifier, str) and identifier in index and identifier not in rows,
              "Unknown or repeated candidate recording", CandidateError)
        person = index[identifier]["biological_person"]
        _need(row["biological_person"] == person and row["fold_id"] == person,
              "Candidate patient/fold identity mismatch", CandidateError)
        runs = row["score_runs"]
        _need(isinstance(runs, list) and len(runs) > 0, "Missing candidate sample scores", CandidateError)
        previous = 0
        for run in runs:
            _need(isinstance(run, list) and len(run) == 3, "Malformed score run", CandidateError)
            a = _integer(run[0], "Score start", error=CandidateError)
            b = _integer(run[1], "Score end", minimum=1, error=CandidateError)
            _need(a == previous and a < b, "Score runs have a gap, overlap or reversed interval", CandidateError)
            _number(run[2], "Sample probability", error=CandidateError)
            previous = b
        _intervals(row["predicted_intervals"], previous, "Declared prediction", CandidateError)
        rows[identifier] = row
    _need(set(rows) == set(index), "Incomplete candidate recording support", CandidateError)
    return rows


def _derive_intervals(runs, threshold):
    intervals = []
    for a, b, probability in runs:
        if probability >= threshold:
            if intervals and intervals[-1][1] == a:
                intervals[-1][1] = b
            else:
                intervals.append([a, b])
    return intervals


def public_support(admission):
    """Project only public observation support; never commit candidate to labels.

    The operator creates this projection before exposing a candidate case. This
    helper does not authenticate source payloads, clocks or channel assignments.
    Reference values, annotation status and answer-bearing annotation hashes are
    deliberately absent, so label-only changes cannot alter this commitment.
    """
    try:
        rows = [{"recording_id": r["recording_id"], "biological_person": r["biological_person"],
                 "native_sample_rate_hz": r["native_sample_rate_hz"],
                 "native_sample_count": r["native_sample_count"], "observed_ticks": r["observed_ticks"],
                 "predictor_channels": [{"index": i, "label": r["channels"][i]["label"]}
                                        for i in r["predictor_channels"]]}
                for r in admission["records"]]
        return {"schema": "neural009_public_support_v1", "task_id": "NEURAL-009",
                "source_index_sha256": admission["source_index_sha256"],
                "folds": admission["folds"], "records": sorted(rows, key=lambda r: r["recording_id"])}
    except (KeyError, TypeError, IndexError) as exc:
        raise AdmissionError("Cannot project malformed public support") from exc


def validate_public_support(support, limits):
    index, people, index_sha = source_index()
    _keys(limits, ["max_record_ticks", "max_total_ticks", "max_prediction_segments"], "Resource limits")
    for name, value in limits.items():
        _integer(value, name, minimum=1)
    _keys(support, ["schema", "task_id", "source_index_sha256", "folds", "records"], "Public support")
    _need(support["schema"] == "neural009_public_support_v1" and support["task_id"] == "NEURAL-009",
          "Wrong public support schema or task")
    _need(support["source_index_sha256"] == index_sha and support["folds"] == _folds(people),
          "Public support source or fold identity mismatch")
    _need(isinstance(support["records"], list) and len(support["records"]) == 686,
          "Public support requires all 686 recordings")
    rows, total = {}, 0
    for row in support["records"]:
        _keys(row, ["recording_id", "biological_person", "native_sample_rate_hz", "native_sample_count",
                    "observed_ticks", "predictor_channels"], "Public recording")
        identifier = row["recording_id"]
        _need(isinstance(identifier, str) and identifier in index and identifier not in rows,
              "Unknown or repeated public recording")
        _need(row["biological_person"] == index[identifier]["biological_person"], "Public biological identity mismatch")
        rate = _integer(row["native_sample_rate_hz"], "Public native rate", minimum=1)
        samples = _integer(row["native_sample_count"], "Public native samples", minimum=1)
        ticks = _integer(row["observed_ticks"], "Public observed ticks", minimum=1, maximum=limits["max_record_ticks"])
        _need(samples*10 == ticks*rate, "Public recording duration is off the 10 Hz grid")
        total += ticks
        _need(total <= limits["max_total_ticks"], "Public observation exceeds declared resource limit")
        channels = row["predictor_channels"]
        _need(isinstance(channels, list) and bool(channels), "Missing public predictor channels")
        used = set()
        for channel in channels:
            _keys(channel, ["index", "label"], "Public predictor channel")
            i = _integer(channel["index"], "Predictor index")
            _need(i not in used and isinstance(channel["label"], str) and 0 < len(channel["label"]) <= 256,
                  "Invalid public predictor channel")
            used.add(i)
        rows[identifier] = row
    _need(set(rows) == set(index), "Incomplete public support")
    return rows


def prevalidate_candidate(candidate, policy, support, *, expected_policy_sha256, limits):
    """Candidate/public-input checks requiring no protected reference values."""
    candidates = validate_candidate(candidate)
    validate_policy(policy, expected_policy_sha256)
    _need(candidate["policy_sha256"] == expected_policy_sha256,
          "Candidate is not bound to the frozen policy", CandidateError)
    records = validate_public_support(support, limits)
    _need(candidate["support_sha256"] == canonical_sha256(support),
          "Candidate is not bound to this public observation support", CandidateError)
    _need(sum(len(r["score_runs"]) for r in candidates.values()) <= limits["max_prediction_segments"],
          "Candidate exceeds declared segment budget", CandidateError)
    for identifier, row in candidates.items():
        _need(row["score_runs"][-1][1] == records[identifier]["observed_ticks"],
              "Candidate sample scores omit or extend observed support", CandidateError)
        _need(_derive_intervals(row["score_runs"], policy["threshold"]) == row["predicted_intervals"],
              "Declared intervals disagree with complete thresholded sample scores", CandidateError)
    return candidates


def _admit(admission, index, people, index_sha, limits):
    _keys(limits, ["max_record_ticks", "max_total_ticks", "max_prediction_segments"], "Resource limits")
    for name, value in limits.items():
        _integer(value, name, minimum=1)
    _keys(admission, ["schema", "task_id", "source_index_sha256", "public_development_only",
                      "normalization_recipe_sha256", "clock_review_sha256", "rights_review_sha256",
                      "folds", "records"], "Admission")
    _need(admission["schema"] == "neural009_admission_v1" and admission["task_id"] == "NEURAL-009",
          "Wrong admission schema or task")
    _need(admission["source_index_sha256"] == index_sha, "Wrong admission source index")
    _need(admission["public_development_only"] is True, "Only public-development scope is supported")
    for name in ("normalization_recipe_sha256", "clock_review_sha256", "rights_review_sha256"):
        _digest(admission[name], name)
    _need(admission["folds"] == _folds(people), "LOPO fold membership differs from complete biological grouping")
    _need(isinstance(admission["records"], list) and len(admission["records"]) == 686,
          "Admission requires all 686 complete recordings")
    records = {}
    total = 0
    for row in admission["records"]:
        _keys(row, ["recording_id", "biological_person", "edf_sha256", "edf_header_sha256",
                    "annotation_sha256", "annotation_status", "native_sample_rate_hz",
                    "native_sample_count", "observed_ticks", "channels", "predictor_channels",
                    "reference_intervals"], "Admission recording")
        identifier = row["recording_id"]
        _need(isinstance(identifier, str) and identifier in index and identifier not in records,
              "Unknown or repeated admission recording")
        original = index[identifier]
        _need(row["biological_person"] == original["biological_person"], "Wrong biological identity")
        _need(row["edf_sha256"] == original["publisher_sha256"], "EDF identity differs from publisher")
        for field in ("edf_header_sha256", "annotation_sha256"):
            _digest(row[field], field)
        rate = _integer(row["native_sample_rate_hz"], "Native sample rate", minimum=1)
        samples = _integer(row["native_sample_count"], "Native samples", minimum=1)
        ticks = _integer(row["observed_ticks"], "Observed ticks", minimum=1,
                         maximum=limits["max_record_ticks"])
        _need(samples * 10 == ticks * rate, "Recording duration is not exact on the 10 Hz grid")
        total += ticks
        _need(total <= limits["max_total_ticks"], "Total observation exceeds declared resource limit")
        reference = _intervals(row["reference_intervals"], ticks, "Reference")
        expected_status = "explicit_events" if reference else "explicit_zero_events"
        _need(row["annotation_status"] == expected_status,
              "Absent or contradictory annotation coverage is not negative background")
        channels = row["channels"]
        _need(isinstance(channels, list) and bool(channels), "Missing montage declaration")
        for channel in channels:
            _keys(channel, ["label", "role"], "Channel")
            _need(isinstance(channel["label"], str) and 0 < len(channel["label"]) <= 256,
                  "Invalid channel label")
            _need(channel["role"] in ("eeg", "annotation", "other"), "Unknown channel role")
        selected = row["predictor_channels"]
        _need(isinstance(selected, list) and bool(selected), "No EEG predictor channels")
        _need(all(type(i) is int and 0 <= i < len(channels) for i in selected)
              and len(set(selected)) == len(selected), "Invalid predictor channel indices")
        _need(all(channels[i]["role"] == "eeg" for i in selected),
              "Annotation or non-neural channel selected as a predictor")
        # Duplicate bipolar labels remain permitted; they are not separate
        # biological electrodes or grounds to silently discard source channels.
        records[identifier] = row
    _need(set(records) == set(index), "Incomplete operator support")
    return records, total


_COUNT_FIELDS = ("raw_reference_events", "raw_predicted_events", "processed_reference_events",
                 "processed_predicted_events", "true_positives", "false_positives", "observed_ticks",
                 "sample_reference_positive_ticks", "sample_true_positive_ticks",
                 "sample_false_positive_ticks", "sample_predicted_positive_ticks")


def _summarize(counts):
    result = dict(counts)
    result["event_metrics"] = _metrics(counts["processed_reference_events"], counts["true_positives"],
                                       counts["false_positives"], counts["observed_ticks"])
    r, tp, fp = (counts[k] for k in ("sample_reference_positive_ticks", "sample_true_positive_ticks",
                                    "sample_false_positive_ticks"))
    result["sample_diagnostics"] = {
        "sensitivity": tp/r if r else None,
        "precision": tp/(tp+fp) if tp+fp else None,
        "f1": 2*tp/(r+tp+fp) if r+fp else None,
        "predicted_positive_time_fraction": counts["sample_predicted_positive_ticks"]/counts["observed_ticks"]}
    return result


def _aggregate(per_person):
    rows = [{"biological_person": person, **_summarize(counts)} for person, counts in sorted(per_person.items())]
    totals = {field: sum(row[field] for row in rows) for field in _COUNT_FIELDS}
    macro = {}
    undefined = {}
    for metric in ("f1", "sensitivity", "precision", "false_alarms_per_24_observed_hours"):
        undefined[metric] = [r["biological_person"] for r in rows if r["event_metrics"][metric] is None]
        macro[metric] = None if undefined[metric] else math.fsum(r["event_metrics"][metric] for r in rows)/len(rows)
    return {"patients": rows, "patient_macro_event_metrics": macro,
            "undefined_patient_metrics": undefined, "pooled_diagnostic": _summarize(totals)}


def evaluate(admission, policy, candidate, *, expected_policy_sha256, limits):
    candidates = validate_candidate(candidate)
    validate_policy(policy, expected_policy_sha256)
    _need(candidate["policy_sha256"] == expected_policy_sha256,
          "Candidate is not bound to the frozen policy", CandidateError)
    index, people, index_sha = source_index()
    records, total = _admit(admission, index, people, index_sha, limits)
    support_sha = canonical_sha256(public_support(admission))
    _need(candidate["support_sha256"] == support_sha,
          "Candidate is not bound to this public observation support", CandidateError)
    segment_count = sum(len(row["score_runs"]) for row in candidates.values())
    _need(segment_count <= limits["max_prediction_segments"], "Candidate exceeds declared segment budget", CandidateError)
    derived = {}
    for identifier, row in candidates.items():
        _need(row["score_runs"][-1][1] == records[identifier]["observed_ticks"],
              "Candidate sample scores omit or extend observed support", CandidateError)
        intervals = _derive_intervals(row["score_runs"], policy["threshold"])
        _need(intervals == row["predicted_intervals"],
              "Declared intervals disagree with complete thresholded sample scores", CandidateError)
        derived[identifier] = intervals
    engine = _upstream()
    arms = {name: {person: {field: 0 for field in _COUNT_FIELDS} for person in people}
            for name in ("candidate", "all_negative_control", "all_positive_control")}
    per_record = []
    for identifier in sorted(records):
        row = records[identifier]
        person, ticks = row["biological_person"], row["observed_ticks"]
        hypotheses = {"candidate": derived[identifier], "all_negative_control": [],
                      "all_positive_control": [[0, ticks]]}
        for name, hypothesis in hypotheses.items():
            result = evaluate_record(row["reference_intervals"], hypothesis, ticks, policy, _engine=engine)
            for field in _COUNT_FIELDS:
                arms[name][person][field] += result[field]
            if name == "candidate":
                per_record.append({"recording_id": identifier, "biological_person": person, **result})
    candidate_result = _aggregate(arms.pop("candidate"))
    return {"schema": "neural009_result_v1", "task_id": "NEURAL-009",
            "status": "complete_conditional_normalized_evaluation",
            "source_index_sha256": index_sha, "admission_sha256": canonical_sha256(admission),
            "support_sha256": support_sha,
            "policy_sha256": expected_policy_sha256, "candidate_sha256": canonical_sha256(candidate),
            "counts": {"recordings": 686, "biological_people": 23, "folds": 23,
                       "observed_ticks": total, "score_segments": segment_count},
            "primary": {"name": "patient_macro_event_f1", "value": candidate_result["patient_macro_event_metrics"]["f1"]},
            "candidate": candidate_result,
            "constant_controls": {name: _aggregate(arm) for name, arm in arms.items()},
            "record_results": per_record,
            "verification": {"complete_declared_support": True, "source_identity_metadata_matches": True,
                             "authentic_signal_payloads_verified": False, "normalization_independently_verified": False,
                             "physical_target_privacy_verified": False, "training_or_causal_context_verified": False,
                             "signal_derived_reference_competence_verified": False,
                             "native_runtime_qualified": False, "scientific_qualification": False},
            "limits": limits,
            "interpretation": "Public-development conditional source result. No authentic-data agreement, protected execution, clinical validation or paper reproduction is established."}
