"""Unrun numerical-contract controls; no production arithmetic is replaced.

The stable-log helper is an invented analytical diagnostic, never a reference
kernel, alternative score or permission to reinterpret historical results.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import stat
import time

BASE = Path(__file__).resolve().parent
PINS = (
    {"path": str(BASE / "functional_balance.py"),
     "bytes": 15493, "sha256": "38c57c6ed5b33b84f362abd29f082c79df6cbf44da132eeb2ccf565ba356ca83"},
    {"path": str(BASE / "evaluation_protocol.py"),
     "bytes": 33385, "sha256": "9e9b1690e14391e4f584c34d0d63886e167d547f76dc0c9bcd1c22de6445b9b6"},
)
KEYS = tuple((c, e, d, n) for c in ("mics", "hcp") for e in ("cortical", "extended")
             for d in ("input", "output") for n in range(2, 9))
CONTEXT = {"scope": "INVENTED_ANALYTICAL", "case_set_id": "numerical-boundary-v1",
           "input_manifest_sha256": None, "method_binding_sha256": None, "spin_manifest_sha256": None,
           "null_protocol": "matched_extrinsic_null_prospective",
           "tolerance_id": "dmn-f64-abs1e-12-rel1e-10-proposed-v1"}


class BoundaryInterrupted(BaseException):
    pass


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def stable_log_diagnostic(strengths):
    """Diagnostic KL from positive finite logs; deliberately has no wire output.

Keep tiny components in the mean log even when exponentiating a relative
component underflows. The discarded denominator contribution is then below
binary64 resolution. This is not claimed to reproduce MATLAB operations.
"""
    require(len(strengths) == 6 and all(type(x) in (int, float) and math.isfinite(x)
                                      and x >= 0 for x in strengths), "six finite nonnegative strengths")
    require(any(x > 0 for x in strengths), "zero total is undefined")
    if any(x == 0 for x in strengths):
        return math.inf
    logs = [math.log2(x) for x in strengths]
    largest = max(logs)
    shifted = [x - largest for x in logs]
    return math.log2(math.fsum(2.0 ** x for x in shifted)) - math.log2(6) - math.fsum(shifted) / 6


def load_source(pin):
    p = Path(pin["path"])
    for ancestor in (p, *p.parents):
        require(not ancestor.is_symlink(), "ordinary pinned source ancestry")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_size == pin["bytes"] <= 65536, "bounded ordinary pinned source")
        body = stream.read(pin["bytes"] + 1)
        after = os.fstat(stream.fileno())
    fields = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(fields(before) == fields(after) == fields(p.lstat()), "pinned source unchanged")
    require(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"], "exact source content")
    namespace = {"__name__": "invented_numerical_boundary_source", "__file__": str(p)}
    exec(compile(body, str(p), "exec"), namespace)
    return namespace


def _run(output):
    root = Path(output)
    require(root.is_absolute() and ".." not in root.parts, "canonical output")
    for ancestor in root.parents:
        require(ancestor.is_dir() and not ancestor.is_symlink(), "ordinary output ancestry")
    root.mkdir(mode=0o700, exist_ok=False)
    kernel, protocol = (load_source(pin) for pin in PINS)
    outcomes = []

    def case(name, action):
        try:
            outcomes.append({"name": name, "passed": True, "detail": action()})
        except Exception as error:
            outcomes.append({"name": name, "passed": False, "error_type": type(error).__name__,
                             "error": str(error)[:2048]})

    def overflow():
        strengths = [1e308] * 6
        require(all(math.isfinite(x) for x in strengths), "finite input witness")
        raw = kernel["kl_uniform_to_profile"](strengths)
        wire = protocol["profile_to_wire"](raw)
        protocol["validate_profile"](wire)
        require(raw["status"] == "UNDEFINED" and raw["probabilities"] is None and raw["KL_bits"] is None,
                "strict finite-strength sum overflow remains explicit undefined")
        require(wire["reason"] == "NONFINITE_TOTAL_STRENGTH"
                and wire["total_strength"] == {"status": "POSITIVE_INFINITY", "value": None},
                "overflow classification survives the wire")
        stable = stable_log_diagnostic(strengths)
        require(stable == 0.0, "independent equal-positive-strength log diagnostic")
        diagnostic = kernel["kl_uniform_to_profile"](strengths, "historical_nansum_diagnostic")
        require(diagnostic["KL_bits"] == 0.0 and diagnostic["NaN_terms_dropped"] == 6,
                "legacy nansum diagnostic is not a literal overflow oracle")
        return {"strict_wire": wire, "diagnostic_log_KL": stable,
                "legacy_nansum_diagnostic_KL": diagnostic["KL_bits"],
                "legacy_dropped_terms": diagnostic["NaN_terms_dropped"],
                "historical_MATLAB_executed": False,
                "meaning": "Finite input does not guarantee finite normalization. Neither the strict status nor the legacy diagnostic is a universal literal-MATLAB result."}

    case("01_finite_total_overflow_is_not_scale_invariance", overflow)

    def underflow():
        tiny = float.fromhex("0x0.0000000000001p-1022")
        strengths = [tiny, 1.0, 1.0, 1.0, 1.0, 1.0]
        require(tiny > 0 and math.log2(tiny) == -1074, "exact positive binary64 subnormal witness")
        raw = kernel["kl_uniform_to_profile"](strengths)
        wire = protocol["profile_to_wire"](raw)
        protocol["validate_profile"](wire)
        require(raw["probabilities"][0] == 0.0 and raw["KL_bits"] == math.inf
                and raw["status"] == "INFINITE", "positive strength can underflow during normalization")
        stable = stable_log_diagnostic(strengths)
        closed_form = 179 + math.log2(5 / 6)
        require(math.isfinite(stable) and abs(stable - closed_form) <= 1e-12,
                "independent finite log-domain result")
        genuine_zero = kernel["kl_uniform_to_profile"]([0.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        require(genuine_zero["KL_bits"] == math.inf and stable_log_diagnostic([0.0, 1, 1, 1, 1, 1]) == math.inf,
                "genuine input zero remains a distinct mechanism")
        incompatible = dict(wire, kl_bits=stable)
        try:
            protocol["validate_profile"](incompatible)
        except protocol["ProtocolError"] as error:
            require("KL disagreement" in str(error), "stable substitution refused specifically at KL coherence")
            wire_refused_stable_substitution = True
        else:
            raise AssertionError("finite KL cannot silently replace a zero-probability wire KL")
        return {"positive_input_hex": tiny.hex(), "literal_wire": wire, "diagnostic_log_KL": stable,
                "exact_real_expression": "179 + log2((5 + 2^-1074)/6)",
                "rounded_diagnostic_expression": "179 + log2(5/6)",
                "genuine_zero_literal_status": genuine_zero["status"],
                "stable_substitution_refused": wire_refused_stable_substitution,
                "meaning": "INFINITE wire KL alone cannot establish a genuinely zero input strength or biological absence."}

    case("02_positive_subnormal_is_not_genuine_zero", underflow)

    def near_tie():
        baseline = [1, 2, 4, 8, 16, 32]
        changed = [1, 2, 4, 8, 16, 32 + 2.0 ** -30]
        reference = protocol["profile_to_wire"](kernel["kl_uniform_to_profile"](baseline))
        candidate = protocol["profile_to_wire"](kernel["kl_uniform_to_profile"](changed))
        def scalars(profile):
            return profile["strengths"] + profile["probabilities"] + profile["kl_terms"] + [profile["total_strength"], profile["kl_bits"]]
        actual, expected = scalars(candidate), scalars(reference)
        require(len(actual) == 20 and all(abs(a-e) <= 1e-12 + 1e-10*abs(e) for a,e in zip(actual,expected)),
                "all20 profile scalars independently satisfy the frozen tolerance")
        require(candidate["kl_bits"] > reference["kl_bits"], "fixed nonadaptive perturbation raises strict KL")
        def tail(changed_cell):
            k = 10000 if changed_cell else 0
            return {"status": "FINITE", "strict_count": k, "N": 10000, "p": k/10000,
                    "tie_count": 0 if changed_cell else 10000, "infinite_null_count": 0,
                    "undefined_null_count": 0, "plus_one_p": (k+1)/10001}
        def records(role):
            yield {"record": "header", "schema": "dmn56-profile-stream-v1", "role": role,
                   "assistance": "paper_data" if role == "candidate" else None,
                   "context": dict(CONTEXT), "cells": 56, "spins_each": 10000}
            for index,key in enumerate(KEYS):
                modified = role == "candidate" and index == 0
                center = 64 if key[3] == 8 else 56
                outside = (60,60,54,54,54,54) if key[3] == 8 else (57,57,58,58,57,57)
                counts = [{"type": i, "center_count": center, "outside_type_count": n} for i,n in enumerate(outside,1)]
                yield {"record": "empirical", "cell": list(key), "partner_counts": counts,
                       "profile": candidate if modified else reference}
                for spin in range(1,10001):
                    yield {"record": "null", "cell": list(key), "spin": spin, "profile": reference}
                yield {"record": "tail", "cell": list(key), "tail": tail(modified)}
            yield {"record": "end", "cells": 56, "null_profiles": 560000, "profile_records": 560056}
        scored = protocol["score_analytical_streams"](records("candidate"), records("reference"), dict(CONTEXT))
        require(scored["complete_traversal"] and scored["status"] == "COMPLETE_MISMATCH"
                and scored["progress"]["profile_pairs_compared"] == 560056
                and scored["progress"]["null_pairs_compared"] == 560000
                and scored["discrepancies_by_kind"] == {"tail": 4} and scored["discrepancy_count"] == 4,
                "complete comparison rejects exactly four strict-tail fields, never tolerated profiles")
        return {"fixed_perturbation": "32 + 2^-30", "all20_profile_scalars_within_tolerance": True,
                "expected_first_reference_tail": tail(False), "expected_first_candidate_tail": tail(True),
                "complete_score": scored, "serialized_JSONL_bytes": 0,
                "meaning": "Exact strict-tail agreement is an additional requirement. Scalar tolerance is not a promise that the entire submission passes."}

    case("03_full56_near_tie_requires_exact_tail", near_tie)
    report = {"schema": "dmn-numerical-boundary-controls-v1", "defined": 3, "executed": len(outcomes),
              "passed": sum(x["passed"] for x in outcomes),
              "failed": sum(not x["passed"] for x in outcomes), "outcomes": outcomes,
              "source_bytes_read": sum(p["bytes"] for p in PINS), "source_pins": PINS,
              "original28_controls_rerun": False, "authentic_inputs_read": 0,
              "production_arithmetic_changed": False, "stable_log_variant_adopted": False,
              "full_numerical_kernel_calls": 0, "model_runs": 0, "scientific_admission": False,
              "accounting_limit": "source_bytes_read covers only the two explicit pinned source-body reads after success; it is not total logical, runtime or physical IO."}
    body = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    require(len(body) <= 1048576, "bounded complete control receipt")
    with (root / "NUMERICAL_BOUNDARY_RESULTS.json").open("xb") as stream:
        require(stream.write(body) == len(body), "complete receipt write")
        stream.flush(); os.fsync(stream.fileno())
    return report


def run(output):
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0,0.0), "no preexisting timer")
    started = time.monotonic()
    def stop(signum, frame):
        raise BoundaryInterrupted("complete numerical controls exceeded300 seconds")
    previous = signal.signal(signal.SIGALRM, stop)
    try:
        signal.setitimer(signal.ITIMER_REAL, 300)
        report = _run(output)
        require(time.monotonic()-started < 300, "complete deadline")
        return report
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    result = run(parser.parse_args().output)
    print(json.dumps({"defined": result["defined"], "passed": result["passed"]}))
    raise SystemExit(0 if result["executed"] == result["passed"] == 3 else 1)
