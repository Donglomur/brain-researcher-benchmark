"""Unexecuted invented controls for the new complete56 streaming protocol.

No authentic input, native reader, NumPy or full reference kernel is called.
One explicit future run loads only the exactly pinned accepted Python source
and exercises its scalar KL/tail functions. Complete composition streams are
analytical generators, not simulated authentic scientific reference outputs.
"""
import argparse
import copy
from functools import lru_cache
import hashlib
import io
import json
import math
import os
from pathlib import Path
import signal
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluation_protocol as protocol

ANALYTICAL_KEYS = tuple((cohort, extent, direction, network)
                       for cohort in ("mics", "hcp")
                       for extent in ("cortical", "extended")
                       for direction in ("input", "output") for network in range(2, 9))
SPINS = 10000
INNER_WALL_SECONDS = 1200
CONTEXT = {"scope": "INVENTED_ANALYTICAL", "case_set_id": "analytical-composition-v1",
           "input_manifest_sha256": None, "method_binding_sha256": None, "spin_manifest_sha256": None,
           "null_protocol": "matched_extrinsic_null_prospective",
           "tolerance_id": "dmn-f64-abs1e-12-rel1e-10-proposed-v1"}
RATIOS = ((1, 1, 1, 1, 1, 1), (1, 1, 1, 1, 1, 5), (1, 2, 4, 8, 16, 32),
          (0, 1, 1, 1, 1, 1), (0, 0, 0, 0, 0, 0))
ANALYTICAL_KL = (0.0, math.log2(5 / 3) - math.log2(5) / 6,
                 math.log2(63 / 6) - 2.5, math.inf, None)


def check(ok, reason):
    if not ok:
        raise AssertionError(reason)


class ControlInterrupted(BaseException):
    """Whole-operation termination; ordinary per-case handlers cannot swallow it."""


def scalar(value):
    if value is None:
        return {"status": "UNDEFINED", "value": None}
    if value == math.inf:
        return {"status": "POSITIVE_INFINITY", "value": None}
    return value


@lru_cache(maxsize=64)
def _basis(kind, shift):
    ratio = RATIOS[kind]
    ratio = ratio[shift:] + ratio[:shift]
    total = sum(ratio)
    if total == 0:
        return ratio, [scalar(None) for _ in ratio], [scalar(None) for _ in ratio]
    probabilities = [value / total for value in ratio]
    # Independent algebra: D=log2(R/6)-(1/6)sum(log2(r_k)).
    terms = [math.inf if value == 0 else (math.log2(total / 6) - math.log2(value)) / 6 for value in ratio]
    return ratio, probabilities, [scalar(term) for term in terms]


def analytical_profile(cell_index, kind, scale):
    shift = (cell_index % 7 + (3 if ANALYTICAL_KEYS[cell_index][2] == "output" else 0)) % 6
    ratio, probabilities, terms = _basis(kind, shift)
    total = scale * sum(ratio)
    return {"status": "UNDEFINED" if kind == 4 else "INFINITE" if kind == 3 else "FINITE",
            "reason": "ZERO_TOTAL_STRENGTH" if kind == 4 else "ZERO_PROBABILITY" if kind == 3 else None,
            "strengths": [scale * value for value in ratio], "total_strength": total,
            "probabilities": probabilities, "kl_terms": terms, "kl_bits": scalar(ANALYTICAL_KL[kind])}


def empirical_kind(cell_index):
    return 3 if cell_index % 8 == 0 else 4 if cell_index % 8 == 1 else 2


def null_kind(cell_index, spin):
    if cell_index % 8 == 2 and spin == 10000:
        return 4
    kind = (spin - 1) % 4
    return 2 if cell_index % 8 == 4 and kind == 3 else kind


def analytical_tail(cell_index):
    flavor = cell_index % 8
    if flavor == 0:
        count, ties, infinite, undefined, status = 7500, 2500, 2500, 0, "EXTENDED_REAL"
    elif flavor == 1:
        count, ties, infinite, undefined, status = None, None, 2500, 0, "UNDEFINED"
    elif flavor == 2:
        count, ties, infinite, undefined, status = None, 2500, 2499, 1, "UNDEFINED"
    elif flavor == 4:
        count, ties, infinite, undefined, status = 5000, 5000, 0, 0, "FINITE"
    else:
        count, ties, infinite, undefined, status = 5000, 2500, 2500, 0, "EXTENDED_REAL"
    return {"status": status, "strict_count": count, "N": 10000,
            "p": scalar(None if count is None else count / 10000), "tie_count": ties,
            "infinite_null_count": infinite, "undefined_null_count": undefined,
            "plus_one_p": scalar(None if count is None else (count + 1) / 10001)}


def partner_counts(network):
    # An invented complete400 census: six56-parcel networks plus one64-parcel
    # network, global type populations[67,67,67,67,66,66]. No authentic labels.
    center = 64 if network == 8 else 56
    outside = (60, 60, 54, 54, 54, 54) if network == 8 else (57, 57, 58, 58, 57, 57)
    return [{"type": k, "center_count": center, "outside_type_count": count}
            for k, count in enumerate(outside, 1)]


def cell_records(index, stats=None):
    key = ANALYTICAL_KEYS[index]
    if stats is not None:
        stats["profiles"] = stats.get("profiles", 0) + 1
    yield {"record": "empirical", "cell": list(key), "partner_counts": partner_counts(key[3]),
           "profile": analytical_profile(index, empirical_kind(index), index + 1)}
    for spin in range(1, 10001):
        if stats is not None:
            stats["profiles"] = stats.get("profiles", 0) + 1
        yield {"record": "null", "cell": list(key), "spin": spin,
               "profile": analytical_profile(index, null_kind(index, spin), (index + 1) * (10001 + spin))}
    yield {"record": "tail", "cell": list(key), "tail": analytical_tail(index)}


def composition(role, assistance=None, *, stats=None, omit_cohort=None):
    yield {"record": "header", "schema": "dmn56-profile-stream-v1", "role": role,
           "assistance": assistance, "context": dict(CONTEXT), "cells": 56, "spins_each": 10000}
    for index, key in enumerate(ANALYTICAL_KEYS):
        if key[0] != omit_cohort:
            yield from cell_records(index, stats)
    yield {"record": "end", "cells": 56, "null_profiles": 560000, "profile_records": 560056}


class GeneratedJSONL:
    """At most one pending invented line; never a materialized full wire file."""
    def __init__(self, records):
        self.records = iter(records)
        self.pending = b""
        self.bytes = self.lines = 0
        self.eof = False

    def readline(self, maximum):
        if not self.pending:
            try:
                record = next(self.records)
            except StopIteration:
                self.eof = True
                return b""
            self.pending = (json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
            check(len(self.pending) <= 1536, "analytical positive line bound")
            self.lines += 1
        result, self.pending = self.pending[:maximum], self.pending[maximum:]
        self.bytes += len(result)
        return result


def mutate(records, predicate, transform, evidence):
    for record in records:
        if predicate(record):
            evidence["mutations"] = evidence.get("mutations", 0) + 1
            record = transform(copy.deepcopy(record))
        yield record


def double_strengths(record):
    profile = record["profile"]
    profile["strengths"] = [value * 2 for value in profile["strengths"]]
    profile["total_strength"] *= 2
    return record


def refusal(call, *, contains, expected_type=protocol.ProtocolError):
    try:
        call()
    except expected_type as exc:
        check(contains in str(exc), "refusal occurred at the wrong stage: " + str(exc))
        result = {"observed_exception": type(exc).__name__, "observed_message": str(exc),
                  "expected_message_fragment": contains}
        if isinstance(exc, protocol.StreamRejection):
            check(exc.report["accepted"] is False and exc.report["complete_traversal"] is False,
                  "structural refusal must retain incomplete traversal")
            result["observed_progress"] = exc.report["progress"]
        return result
    raise AssertionError("incorrect input was accepted")


def load_pinned_kernel():
    """Only called by a separately selected future control run; no native arrays."""
    pin = protocol.KERNEL_REFERENCE
    path = Path(__file__).resolve().parent / pin["path"]
    check(not path.is_symlink(), "selected kernel source cannot be a symlink")
    with open(path, "rb") as source:
        raw = source.read(pin["bytes"] + 1)
    check(len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"], "exact accepted kernel source pin")
    namespace = {"__name__": "dmn_accepted_scalar_kernel_control", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace


def _run_controls(output):
    root = Path(output)
    check(root.is_absolute() and not root.exists(), "fresh absolute control output required")
    root.mkdir(mode=0o700)
    fixtures = root / "wire-fixtures"
    fixtures.mkdir(mode=0o700)
    kernel = load_pinned_kernel()
    outcomes = []
    fixture_bytes = 0

    def case(name, action, fixture=None):
        nonlocal fixture_bytes
        witness = None
        if fixture is not None:
            check(type(fixture) is bytes and len(fixture) <= 4096, "small wire fixture cap")
            fixture_bytes += len(fixture)
            check(fixture_bytes <= 65536, "whole wire fixture retention cap")
            path = fixtures / (name + ".jsonl")
            with open(path, "xb") as stream:
                check(stream.write(fixture) == len(fixture), "complete fixture write")
            witness = {"path": str(path), "bytes": len(fixture), "sha256": hashlib.sha256(fixture).hexdigest()}
        try:
            detail = action(fixture)
            outcomes.append({"name": name, "passed": True, "fixture": witness, "detail": detail})
        except Exception as exc:
            # Owner interruption/BaseException must escape; never run later cases after cancellation.
            outcomes.append({"name": name, "passed": False, "fixture": witness,
                             "error_type": type(exc).__name__, "error": str(exc)[:2048]})

    def kernel_profiles(_):
        witnesses = []
        for kind, ratio in enumerate(RATIOS):
            actual = kernel["kl_uniform_to_profile"](list(ratio))
            expected = ANALYTICAL_KL[kind]
            value = actual["KL_bits"]
            check(value is None if expected is None else value == math.inf if expected == math.inf
                  else abs(value - expected) <= 1e-14, "independent closed-form KL witness")
            wire = protocol.profile_to_wire(actual)
            protocol.validate_profile(wire)
            check(wire["kl_bits"] == scalar(value), "source KL preserved by codec")
            witnesses.append({"ratio": list(ratio), "expected_KL": scalar(expected),
                              "observed_KL": scalar(value), "observed_status": actual["status"]})
        return {"witnesses": witnesses, "source_pin": protocol.KERNEL_REFERENCE}

    case("01_independent_analytic_kernel_and_codec", kernel_profiles)

    def scalar_tails(_):
        null = [0.0, ANALYTICAL_KL[1], ANALYTICAL_KL[2], math.inf] * 2500
        cases = []
        for empirical, expected_count in ((ANALYTICAL_KL[2], 5000), (math.inf, 7500)):
            actual = kernel["strict_lower_tail"](empirical, null)
            check(actual["strict_count"] == expected_count and actual["N"] == 10000
                  and actual["p"] == expected_count / 10000, "closed-form strict tail including infinity")
            cases.append({"empirical": scalar(empirical), "expected_count": expected_count, "observed": actual})
        null[-1] = None
        actual = kernel["strict_lower_tail"](ANALYTICAL_KL[2], null)
        check(actual["status"] == "UNDEFINED" and actual["N"] == 10000 and actual["p"] is None,
              "undefined slot must preserve full denominator and block tail")
        return {"defined_witnesses": cases, "undefined_witness": actual}

    case("02_complete_scalar_tail_oracles", scalar_tails)

    def full_match(_):
        cs, rs = {}, {}
        header = GeneratedJSONL([next(composition("candidate", "paper_data"))])
        cells = [GeneratedJSONL(cell_records(index, cs)) for index in range(56)]
        end = GeneratedJSONL([{"record": "end", "cells": 56, "null_profiles": 560000, "profile_records": 560056}])
        candidate = protocol.read_sharded_jsonl(header, cells, end)
        result = protocol.score_analytical_streams(candidate,
                                                   composition("reference", stats=rs), dict(CONTEXT))
        check(result["status"] == "COMPLETE_MATCH" and result["accepted"] is True
              and result["complete_traversal"] is True and result["discrepancy_count"] == 0,
              "complete analytical stream agreement")
        check(cs["profiles"] == rs["profiles"] == 560056 and result["null_profiles"] == 560000,
              "every empirical and null profile consumed")
        shards = [header] + cells + [end]
        check(all(shard.eof for shard in shards) and [shard.lines for shard in shards] == [1] + [10002] * 56 + [1],
              "all58 physical shard boundaries and EOFs traversed")
        return {"observed": result, "candidate_profiles": cs["profiles"], "reference_profiles": rs["profiles"],
                "expected_profiles_each": 560056, "virtual_wire_bytes": sum(shard.bytes for shard in shards),
                "complete_virtual_shard_EOFs": 58, "large_wire_bytes_retained": 0}

    case("03_full56_560000_complete_match", full_match)

    def last_profile(_):
        evidence = {}
        candidate = mutate(composition("candidate", "paper_data_code"),
                           lambda r: r["record"] == "null" and r["cell"] == list(ANALYTICAL_KEYS[-1]) and r["spin"] == 10000,
                           double_strengths, evidence)
        result = protocol.score_analytical_streams(candidate, composition("reference"), dict(CONTEXT))
        check(evidence.get("mutations") == 1, "one genuine final-slot mutation")
        check(result["status"] == "COMPLETE_MISMATCH" and not result["accepted"] and result["complete_traversal"],
              "final-slot corruption must reject after complete traversal")
        # Final null has five nonzero strengths and a positive total; KL/probabilities are unchanged.
        check(result["discrepancy_count"] == 6 and result["progress"]["null_pairs_compared"] == 560000,
              "six final-slot strength/total discrepancies")
        return {"observed": result, "expected_discrepancies": 6, "mutations": evidence["mutations"]}

    case("04_final_spin_valid_profile_corruption", last_profile)

    def all_wrong(_):
        evidence = {}
        candidate = mutate(composition("candidate", "paper_data_code"),
                           lambda r: r["record"] in ("empirical", "null"), double_strengths, evidence)
        result = protocol.score_analytical_streams(candidate, composition("reference"), dict(CONTEXT), max_findings=100)
        # For each eight-cell cycle: [67506,67500,67501,67507,70007,67507,67507,67507].
        # Positive profiles disagree in six strengths+total; zero-component profiles in five+total;
        # all-zero profiles agree. Seven complete cycles give this independent exact count.
        expected = 7 * (67506 + 67500 + 67501 + 70007 + 4 * 67507)
        check(expected == 3797794 and result["discrepancy_count"] == expected, "complete exact discrepancy count")
        check(result["complete_traversal"] and result["status"] == "COMPLETE_MISMATCH"
              and len(result["findings_sample"]) == 100 and evidence["mutations"] == 560056,
              "wrong full stream must remain bounded and traverse every record")
        return {"observed": result, "expected_discrepancies": expected, "mutated_profile_records": evidence["mutations"]}

    case("05_full_wrong_stream_bounded_findings", all_wrong)

    case("06_missing_cohort_rejected", lambda _: refusal(
        lambda: protocol.score_analytical_streams(composition("candidate", "paper_data", omit_cohort="mics"),
                                                  composition("reference"), dict(CONTEXT)),
        contains="ordered cell/record"))

    def framed_mutation(field, value, kind, message):
        evidence = {}
        def change(record):
            if field == "direction":
                record["cell"][2] = value
            elif field == "network":
                record["cell"][3] = value
            else:
                record[field] = value
            return record
        candidate = mutate(composition("candidate", "paper_data"), lambda r: r["record"] == kind,
                           change, evidence)
        detail = refusal(lambda: protocol.score_analytical_streams(candidate, composition("reference"), dict(CONTEXT)),
                         contains=message)
        check(evidence.get("mutations") == 1, "negative frame fixture reached its deliberate mutation")
        return detail

    case("07_direction_order_rejected", lambda _: framed_mutation("direction", "output", "empirical", "ordered cell/record"))
    case("08_spin_order_rejected", lambda _: framed_mutation("spin", 2, "null", "ordered spin"))
    case("09_float_network_identity_rejected", lambda _: framed_mutation("network", 2.0, "empirical", "typed cell"))

    def bad_profile(field):
        profile = copy.deepcopy(analytical_profile(0, 2, 1))
        if field == "probabilities":
            profile[field][0] += 0.01
        elif field == "kl_terms":
            profile[field][0] += 0.01
        else:
            profile[field] = 0.0
        return refusal(lambda: protocol.validate_profile(profile), contains="disagreement")

    def probability_domain(_):
        ordinary = bad_profile("probabilities")
        negative = copy.deepcopy(analytical_profile(0, 3, 1))
        negative["probabilities"][0] = -1e-13  # Within numeric tolerance of zero, but not a probability.
        negative_result = refusal(lambda: protocol.validate_profile(negative), contains="outside domain")
        negative_total = copy.deepcopy(analytical_profile(0, 4, 1))
        negative_total["total_strength"] = -1e-13
        total_result = refusal(lambda: protocol.validate_profile(negative_total), contains="negative total")
        return {"normalization": ordinary, "negative_probability": negative_result,
                "negative_total": total_result}

    case("10_probability_normalization_rejected", probability_domain)
    case("11_kl_term_rejected", lambda _: bad_profile("kl_terms"))
    case("12_reverse_or_wrong_KL_rejected", lambda _: bad_profile("kl_bits"))

    def tail_error(_):
        accumulator = protocol.TailAccumulator(ANALYTICAL_KL[2])
        for spin in range(10000):
            accumulator.add(ANALYTICAL_KL[spin % 4])
        expected = analytical_tail(3)
        check(accumulator.wire() == expected, "independent full10000 accumulator witness")
        bad = dict(expected, strict_count=5001, p=0.5001)
        result = refusal(lambda: protocol._validate_tail(bad, expected), contains="tail count disagreement")
        result["expected_strict_count"] = 5000
        result["incorrect_supplied_count"] = 5001
        return result

    case("13_genuine_wrong_tail_rejected", tail_error)
    case("14_missing_null_refused", lambda _: refusal(lambda: protocol.TailAccumulator(0.0).wire(), contains="complete10000"))
    case("15_bad_nonfinite_encoding_rejected", lambda _: refusal(
        lambda: protocol.decode_scalar({"status": "POSITIVE_INFINITY", "value": 1}), contains="null value"))
    case("16_missing_sixth_type_rejected", lambda _: refusal(
        lambda: protocol.validate_profile(dict(analytical_profile(0, 2, 1), strengths=[1, 2, 4, 8, 16])), contains="six ordered types"))

    valid_record = {"record": "null", "cell": list(ANALYTICAL_KEYS[0]), "spin": 1,
                    "profile": analytical_profile(0, 3, 17)}
    valid_wire = (json.dumps(valid_record, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()

    def wire_roundtrip(body):
        accounting = {}
        decoded = list(protocol.read_jsonl_records(io.BytesIO(body), accounting=accounting))
        check(decoded == [valid_record] and accounting["complete_eof"] is True and accounting["records"] == 1,
              "independent valid wire roundtrip")
        check(protocol.encode_record(decoded[0]) == body and len(body) <= 1536, "canonical bounded wire bytes")
        return {"expected_records": 1, "observed_accounting": accounting, "wire_bytes": len(body)}

    case("17_valid_special_wire_roundtrip", wire_roundtrip, valid_wire)
    malformed = (
        ("18_json_NaN_rejected", b'{"x":NaN}\n', "nonstandard JSON"),
        ("19_json_overflow_rejected", b'{"x":1e999}\n', "overflows finite"),
        ("20_duplicate_wire_key_rejected", b'{"record":"null","record":"tail"}\n', "duplicate JSON"),
        ("21_missing_LF_rejected", b'{"record":"null"}', "LF-terminated"),
        ("22_line_bound_rejected", b'{"x":"' + b'a' * 1536 + b'"}\n', "exceeds1536"),
    )
    for name, body, message in malformed:
        case(name, lambda raw, fragment=message: refusal(
            lambda: list(protocol.read_jsonl_records(io.BytesIO(raw))), contains=fragment), body)

    case("23_missing_physical_cell_shard_rejected", lambda _: refusal(
        lambda: list(protocol.read_sharded_jsonl(io.BytesIO(), [io.BytesIO() for _ in range(55)], io.BytesIO())),
        contains="exact56"))

    def extra_header(_):
        header = next(composition("candidate", "paper_data"))
        raw = (json.dumps(header, separators=(",", ":")) + "\n").encode()
        return refusal(lambda: next(protocol.read_sharded_jsonl(io.BytesIO(raw + raw),
                       [io.BytesIO() for _ in range(56)], io.BytesIO())), contains="extra JSONL")

    case("24_extra_header_record_rejected", extra_header)

    def unbound_provenance(_):
        attempts = {"iterator_pulls": 0}
        class Poison:
            def __iter__(self):
                attempts["iterator_pulls"] += 1
                raise AssertionError("unbound admission touched a participant/reference stream")
        result = refusal(lambda: protocol.score_protected_streams(Poison(), Poison(), binding=None,
                         expected_binding_sha256=None, accepted_gate_digests=None),
                         contains="unbound", expected_type=protocol.AdmissionError)
        check(attempts["iterator_pulls"] == 0, "disabled provenance must refuse before I/O")
        result.update(attempts)
        return result

    case("25_unbound_provenance_before_streams", unbound_provenance)

    def tolerance_error(_):
        wrong = dict(CONTEXT, tolerance_id="posthoc-loose-tolerance")
        return refusal(lambda: protocol.score_analytical_streams(iter(()), iter(()), wrong), contains="tolerance identity")

    case("26_posthoc_tolerance_identity_rejected", tolerance_error)

    def wrong_tail_type(_):
        valid = analytical_tail(4)
        wrong = dict(valid, strict_count=5000.0)
        return refusal(lambda: protocol._validate_tail(wrong, valid), contains="bounded integer")

    case("27_float_tail_count_rejected", wrong_tail_type)

    def complete_codec_writer(_):
        raw = kernel["kl_uniform_to_profile"]([1] * 6)
        shared_nulls = [raw] * 10000
        zeros = [0.0] * 10000
        strict = kernel["strict_lower_tail"](0.0, zeros)
        plus_one = kernel["plus_one_tail_separate"](0.0, zeros)
        result = {"complete_cells": 56, "spins_each": 10000,
                  "records": [{"key": list(key), "null_protocol": CONTEXT["null_protocol"],
                               "partner_counts": partner_counts(key[3]), "empirical": raw,
                               "all10000_null_profiles": shared_nulls, "historical_strict_tail": strict,
                               "plus_one_tail_separate": plus_one} for key in ANALYTICAL_KEYS]}
        class CountingSink:
            def __init__(self, index):
                self.index = index
                self.lines = self.bytes = 0
                self.hash = hashlib.sha256()

            def write(self, body):
                check(type(body) is bytes and len(body) <= 1536 and body.endswith(b"\n"), "bounded complete writer line")
                record = json.loads(body)
                if self.index == -1:
                    check(self.lines == 0 and record["record"] == "header" and record["role"] == "reference", "one private header")
                elif self.index == 56:
                    check(self.lines == 0 and record == {"record": "end", "cells": 56, "null_profiles": 560000,
                                                       "profile_records": 560056}, "one complete footer")
                else:
                    check(record["cell"] == list(ANALYTICAL_KEYS[self.index]), "independent writer cell identity")
                    expected_kind = "empirical" if self.lines == 0 else "tail" if self.lines == 10001 else "null"
                    check(record["record"] == expected_kind, "independent writer record order")
                    if expected_kind == "null":
                        check(record["spin"] == self.lines, "independent writer spin identity")
                    if expected_kind in ("empirical", "null"):
                        profile = record["profile"]
                        check(profile["strengths"] == [1] * 6 and profile["total_strength"] == 6
                              and profile["probabilities"] == [1 / 6] * 6 and profile["kl_terms"] == [0] * 6
                              and profile["kl_bits"] == 0 and profile["status"] == "FINITE",
                              "constant analytical profile preserved through source adapter and writer")
                    else:
                        check(record["tail"] == {"status": "FINITE", "strict_count": 0, "N": 10000,
                              "p": 0.0, "tie_count": 10000, "infinite_null_count": 0, "undefined_null_count": 0,
                              "plus_one_p": 1 / 10001}, "constant analytical strict tail")
                self.lines += 1
                self.bytes += len(body)
                self.hash.update(body)
                return len(body)
        sinks = [CountingSink(index) for index in range(-1, 57)]
        observed = protocol.write_sharded_jsonl(protocol.iter_result_stream(result, dict(CONTEXT), role="reference"),
                                               sinks[0], sinks[1:57], sinks[57])
        check(observed["records"] == [1] + [10002] * 56 + [1] and observed["complete"], "all58 writer shards complete")
        check(observed["total_bytes"] == sum(sink.bytes for sink in sinks), "independent writer byte accounting")
        return {"observed": observed, "shard_digests": [sink.hash.hexdigest() for sink in sinks],
                "large_wire_bytes_retained": 0, "source_null_pointer_slots": 10000,
                "full_reference_kernel_calls": 0}

    case("28_complete_codec_and58shard_writer", complete_codec_writer)

    report = {"schema": "dmn56-analytical-protocol-controls-v1", "defined": 28, "executed": len(outcomes),
              "passed": sum(row["passed"] for row in outcomes), "failed": sum(not row["passed"] for row in outcomes),
              "outcomes": outcomes, "fixture_retained_bytes": fixture_bytes,
              "authentic_inputs_read": 0, "full_reference_kernel_calls": 0,
              "numpy_import_selected": False, "scientific_admission": False,
              "authentication_qualified": False, "protected_improvement_target": None}
    body = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    check(len(body) <= 1024**2, "bounded complete control report")
    with open(root / "ANALYTICAL_CONTROL_RESULTS.json", "xb") as stream:
        check(stream.write(body) == len(body), "complete report write")
        stream.flush()
        os.fsync(stream.fileno())
    return report


def run_controls(output):
    """Finite whole operation, including source read, fixtures and report writes.

    Interruption preserves any partial files and may leave no final report.
    An interrupted run is never accepted, even if a report was written before
    the deadline exception. The external owner must also verify process closure.
    """
    check(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0),
          "control worker must not replace an existing real-time timer")
    started = time.monotonic()

    def terminate(signum, frame):
        raise ControlInterrupted("analytical controls exceeded1200-second whole-operation deadline")

    previous = signal.signal(signal.SIGALRM, terminate)
    try:
        signal.setitimer(signal.ITIMER_REAL, INNER_WALL_SECONDS)
        report = _run_controls(output)
        if time.monotonic() - started >= INNER_WALL_SECONDS:
            raise ControlInterrupted("analytical controls completed after the1200-second deadline")
        return report
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    report = run_controls(parser.parse_args().output)
    print(json.dumps({"defined": report["defined"], "passed": report["passed"], "failed": report["failed"]}))
    raise SystemExit(0 if report["executed"] == 28 and report["failed"] == 0 else 1)
