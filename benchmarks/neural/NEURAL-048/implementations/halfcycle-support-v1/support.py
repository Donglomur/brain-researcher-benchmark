"""Derive conservative support for declared complete-half-cycle aligned values.

This is an operator-side construction helper, not a native data converter.
The operator must establish the physical clock map and dependency bounds.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


LEGACY_SHA256 = "cd2dc29f52e4aa79a5dc5b913aad9bef57b08e9bbf74f7c7a463b923c9e03d57"
LEGACY_PATH = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py"
if hashlib.sha256(LEGACY_PATH.read_bytes()).hexdigest() != LEGACY_SHA256:
    raise RuntimeError("NEURAL-048 history dependency changed; independent review required")
_spec = importlib.util.spec_from_file_location("neural048_halfcycle_legacy", LEGACY_PATH)
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)

ContractError = legacy.ContractError
SCHEMA = "neural048-halfcycle-support/v1"
INTERVAL_FIELDS = {
    "id", "worm_id", "session_id", "clock", "start_ns", "end_ns",
    "signal_support_end_ns", "signal_available_ns",
    "crossing_support_end_ns", "crossing_available_ns",
}
SAMPLE_FIELDS = {
    "id", "worm_id", "session_id", "interval_id", "time_ns",
    "curvature", "velocity", "odor_encounter", "neural",
}


def _exact(value, fields, name):
    legacy._mapping(value, name)
    legacy._require(set(value) == fields, f"{name}: exact fields required")


def compile_samples(samples, intervals):
    """Attach the complete alignment dependency, never just an aligned index.

    Each interval declares bounds for ALL signal transformations and BOTH
    curvature crossings used to form the half-cycle. Availability includes
    acquisition/processing latency. Values are already produced by the operator;
    this function neither interpolates them nor authenticates their lineage.
    """
    legacy._require(isinstance(intervals, list) and bool(intervals), "intervals required")
    bound = {}
    for interval in intervals:
        _exact(interval, INTERVAL_FIELDS, "half-cycle interval")
        iid = legacy._text(interval["id"], "interval id")
        legacy._require(iid not in bound, "duplicate interval id")
        worm = legacy._text(interval["worm_id"], "worm_id")
        session = legacy._text(interval["session_id"], "session_id")
        legacy._require(interval["clock"] == "physical_ns",
                        "aligned phase/frame coordinates are not physical nanoseconds")
        start = legacy._integer(interval["start_ns"], "start_ns")
        end = legacy._integer(interval["end_ns"], "end_ns")
        legacy._require(start < end, "half-cycle endpoints must be ordered")
        supports, availabilities = [], []
        for dependency in ("signal", "crossing"):
            support = legacy._integer(interval[dependency + "_support_end_ns"],
                                      dependency + " support")
            available = legacy._integer(interval[dependency + "_available_ns"],
                                        dependency + " availability")
            legacy._require(end <= support <= available,
                            f"{dependency}: complete right boundary/support/availability required")
            supports.append(support)
            availabilities.append(available)
        bound[iid] = (worm, session, start, end, max(supports), max(availabilities))

    legacy._require(isinstance(samples, list) and bool(samples), "samples required")
    output, seen_ids, physical, used, widths = [], set(), set(), set(), {}
    for sample in samples:
        _exact(sample, SAMPLE_FIELDS, "aligned sample")
        sid = legacy._text(sample["id"], "sample id")
        legacy._require(sid not in seen_ids, "duplicate sample id")
        seen_ids.add(sid)
        iid = legacy._text(sample["interval_id"], "interval id")
        legacy._require(iid in bound, "sample has no declared half-cycle")
        worm, session, start, end, support, available = bound[iid]
        legacy._require((sample["worm_id"], sample["session_id"]) == (worm, session),
                        "half-cycle cannot cross worm/session identity")
        time = legacy._integer(sample["time_ns"], "physical sample time_ns")
        legacy._require(start <= time <= end, "sample outside its physical half-cycle")
        key = (worm, session, time)
        legacy._require(key not in physical, "duplicate physical sample under another id")
        physical.add(key)
        used.add(iid)
        neural = sample["neural"]
        legacy._require(isinstance(neural, list) and bool(neural), "neural vector required")
        neural = [legacy._finite(value, "neural") for value in neural]
        session_key = (worm, session)
        legacy._require(session_key not in widths or widths[session_key] == len(neural),
                        "neural width changed in session")
        widths[session_key] = len(neural)
        output.append({
            "worm_id": worm, "session_id": session, "time_ns": time,
            "support_end_ns": support, "available_ns": available,
            **{name: legacy._finite(sample[name], name) for name in legacy.BEHAVIOR},
            "neural": neural,
        })
    legacy._require(used == set(bound), "unused half-cycle in declared selected inventory")
    return output


def build_histories(samples, intervals, events, lags_ns, neural_shift_ns, max_age_ns):
    """Build all declared histories or reject; no dropping unavailable windows."""
    compiled = compile_samples(samples, intervals)
    histories = legacy.causal_histories(compiled, events, lags_ns, neural_shift_ns, max_age_ns)
    return {
        "schema": SCHEMA, "task_id": legacy.TASK_ID,
        "history_dependency_sha256": LEGACY_SHA256,
        "input_sha256": legacy.digest({
            "samples": samples, "intervals": intervals, "events": events,
            "lags_ns": lags_ns, "neural_shift_ns": neural_shift_ns,
            "max_age_ns": max_age_ns,
        }),
        "compiled_samples_sha256": legacy.digest(compiled),
        "histories": histories,
        "scope": {
            "verified": "complete declared half-cycle dependency bounds reach the pinned history builder",
            "not_verified": ["native field mapping and physical-clock authenticity",
                             "completeness of declared upstream dependencies",
                             "correctness of supplied aligned values",
                             "model fitting, participant isolation or scientific qualification"],
        },
        "admission": {"runnable_native": False, "research_qualified": False,
                      "submission_ready": False},
    }
