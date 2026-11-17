"""Complete owner-only Stroop report validation and window-geometry ledger.

Consumes independently regenerated metadata, never MAT or signal arrays.
Geometry is conditional on the saved scalar T; it is not timing validation.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct
import types

HERE = Path(__file__).absolute().parent
CONTRACT_BYTES = 221135
CONTRACT_SHA = "1cd811af54ac31ff894b437bb3abbdd473374b1fe167844d84b9f619c5296fd4"
TASK = "NEURAL-SCOPE-20261114-STROOP"
CODES = ("11", "12", "13", "101", "102")
CONDITIONS = {"11": "neutral", "12": "congruent", "13": "incongruent"}
REPORT_CAP = 1048576
AUDIT_CAP = 8 * 1048576
OUTPUT_CAP = 8 * 1048576
MAX_ONSETS = 32768


def need(ok, message):
    if not ok:
        raise ValueError(message)


def donor(name, size, sha):
    path = HERE / (name + ".py")
    need(not any(p.is_symlink() for p in (path, *path.parents)), "ordinary source graph")
    st = path.lstat()
    need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == size,
         "exact ordinary donor extent")
    raw = path.read_bytes()
    need(len(raw) == size and hashlib.sha256(raw).hexdigest() == sha, "exact accepted donor")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


inspector = donor("inspect_prepared_v2", 16671,
                  "b4f6b10967ef23c3e2910e295901cd0e5dd510e18d603becc78ba456ee10ee58")
io = donor("stroop", 11941,
           "6f41c9fb318ce079e0d83ceb9fd480d503e96df42ea24ab1a62e2f949745af3e")


def integer(value, minimum, maximum, context):
    need(type(value) is int and minimum <= value <= maximum, context)
    return value


def scalar(value, name):
    result = inspector._scalar(value, name)
    need(type(result) in (int, float), "numeric, nonboolean " + name)
    return result


def ceil_fraction(value):
    return -((-value.numerator) // value.denominator)


def window_offsets(T):
    need(type(T) in (int, float) and math.isfinite(T) and T > 0, "positive finite saved T")
    period = Fraction(T)  # Exact binary value for a stored IEEE float; no decimal fit.
    first = ceil_fraction(Fraction(-5) / period)
    stop = ceil_fraction(Fraction(20) / period)
    return {"first_offset_inclusive": first, "stop_offset_exclusive": stop,
            "sample_count": stop - first,
            "saved_T_exact_ratio": [str(period.numerator), str(period.denominator)],
            "saved_T_float_hex": T.hex() if type(T) is float else None}


def numeric_schema(value, shape, context):
    need(type(value) is dict and set(value) == {"class", "storage_type", "shape", "stored_bytes"},
         context + " exact report schema")
    integer(value["class"], 6, 15, context + " numeric class")
    k = value["storage_type"]
    need(type(k) is int and k in inspector.FORMATS and type(value["shape"]) is list
         and all(type(x) is int for x in value["shape"]) and value["shape"] == shape,
         context + " storage and axes")
    need(value["stored_bytes"] == math.prod(shape) * struct.calcsize("<" + inspector.FORMATS[k])
         and type(value["stored_bytes"]) is int, context + " declared storage extent")


def report_record(expected, report):
    need(type(report) is dict and report.get("schema") == "stroop_prepared_schema_clock_inspection_v1",
         "accepted nested inspection report schema")
    need(type(report.get("index")) is int and report["index"] == expected["index"]
         and type(report.get("session")) is int and report["session"] == expected["session"],
         "complete ordered record/session join")
    need(report.get("saved_subject_join") == "exact" and report.get("scientific_ready") is False,
         "declared identity join and unchanged scientific hold")
    integrity = report["file_integrity"]
    need(integrity["bytes"] == expected["bytes"] and type(integrity["bytes"]) is int
         and integrity["crc32"] == expected["crc32"] and type(integrity["crc32"]) is int,
         "exact expected original MAT extent and CRC")
    io.digest(integrity["sha256"], "regenerated original MAT digest")
    integer(integrity["maximum_physical_read_bytes"], 1, 65536, "bounded accepted physical read")
    need(integrity["publisher_SHA256_predeclared"] is False, "derived digest provenance")
    signals = report["signals"]
    need(set(signals) == {"oxyData", "dxyData", "totalData"}, "all three original signal fields")
    shape = signals["oxyData"]["shape"]
    need(type(shape) is list and len(shape) == 2 and shape[1] == 35 and type(shape[1]) is int,
         "35-channel sample axes")
    samples = integer(shape[0], 1, inspector.MAX_SAMPLES, "bounded full sample axis")
    for name in signals:
        numeric_schema(signals[name], [samples, 35], name)
    need(report["signal_values_decoded"] is False and report["signal_finiteness_verified"] is False,
         "metadata report is not signal-finiteness proof")
    metadata = report["metadata_private"]
    need(set(metadata) == set(inspector.FIELDS) - set(signals) - {"vector_onset"},
         "all nested small metadata fields")
    subject = metadata["subject"]
    need(subject["class"] == 4 and subject["logical"] is False
         and subject["text"] == expected["source_id"], "literal saved internal subject join")
    T = scalar(metadata["T"], "T")
    need(T > 0 and scalar(metadata["nch"], "nch") == 35, "clock/channel metadata")
    clock = report["clock"]
    need(type(clock["saved_T_seconds"]) in (int, float) and clock["saved_T_seconds"] == T
         and clock["saved_T_source"] == "nirsdata.T scalar"
         and clock["explicit_original_time_vector"] == "absent from observed root field roster"
         and clock["uniform_time_verified"] is False and clock["fitted_or_replaced_clock"] is False,
         "saved scalar clock and unresolved full timing")
    preprocessing = inspector.preprocessing_evidence(metadata["preprocessSet"], T)
    need(preprocessing == report["preprocessing"], "recorded crop rederived with accepted inspector")
    trim = preprocessing.get("trim")
    if trim is None:
        crop = "unresolved:" + preprocessing.get("trim_status", "metadata_form")
    else:
        left, right = map(inspector.Decimal, (trim["left_seconds_literal"], trim["right_seconds_literal"]))
        crop = "15/5" if (left, right) == (15, 5) else "15/15" if (left, right) == (15, 15) else "other_literal"
    units = report["units"]
    need(units == {"concentration_pathlength_scale": "unresolved; no explicit root unit field",
                   "geometry_units_not_concentration_units": True}, "unchanged physical-unit hold")
    onsets = report["onsets"]
    numeric_schema(onsets["schema"], [samples, 1], "vector_onset")
    need(onsets["indices_shifted"] is False and set(onsets["direct_marker_comparison"]) == set(CODES),
         "five complete unshifted marker comparisons")
    counts = onsets["nonzero_code_counts"]
    need(type(counts) is dict and len(counts) <= 256, "bounded nonzero-code census")
    for code, count in counts.items():
        need(type(code) is str and str(int(code)) == code and code != "0"
             and -2147483648 <= int(code) < 2147483648, "literal signed nonzero marker code")
        integer(count, 1, samples, "positive exact vector code count")
    need(sum(counts.values()) <= samples, "one code per vector sample")
    matches = {}
    for code in CODES:
        item = onsets["direct_marker_comparison"][code]
        need(set(item) == {"expected", "same_index_same_code", "wrong_code_at_expected_index",
                          "expected_indices_outside_sample_axis", "vector_count", "exact"},
             "closed marker comparison schema")
        n = len(expected["marker_onsets"][code])
        outside = sum(x > samples for x in expected["marker_onsets"][code])
        for key in ("expected", "same_index_same_code", "wrong_code_at_expected_index",
                    "expected_indices_outside_sample_axis", "vector_count"):
            integer(item[key], 0, inspector.MAX_SAMPLES, "nonnegative marker comparison count")
        need(item["expected"] == n and item["expected_indices_outside_sample_axis"] == outside
             and item["vector_count"] == counts.get(code, 0)
             and item["same_index_same_code"] + item["wrong_code_at_expected_index"] + outside == n,
             "exact marker-count arithmetic joins")
        need(item["same_index_same_code"] <= item["vector_count"]
             <= samples - item["wrong_code_at_expected_index"],
             "matched positions and vector census are arithmetically possible")
        exact = item["same_index_same_code"] == n == counts.get(code, 0)
        need(type(item["exact"]) is bool and item["exact"] == exact, "derived marker exactness")
        matches[code] = dict(item)
    # Five fixed codes: all31 nonempty subset bounds for distinct matching
    # positions. This checks the reports' necessary arithmetic, not the vector.
    in_axis = {code: {x for x in expected["marker_onsets"][code] if x <= samples}
               for code in CODES}
    for mask in range(1, 1 << len(CODES)):
        subset = [code for j, code in enumerate(CODES) if mask & (1 << j)]
        positions = set().union(*(in_axis[code] for code in subset))
        need(sum(matches[code]["same_index_same_code"] for code in subset) <= len(positions),
             "distinct marker codes cannot claim the same matching position")
    unknown = {k: v for k, v in counts.items() if k not in CODES}
    geometry = window_offsets(T)
    events = sorted((pos, code) for code in CONDITIONS for pos in expected["marker_onsets"][code])
    need(len(events) <= MAX_ONSETS, "bounded complete event ledger")
    positions = sorted(set(pos for pos, _ in events))
    next_position = dict(zip(positions, positions[1:] + [None]))
    multiplicity = Counter(pos for pos, _ in events)
    windows = []
    for position, code in events:
        start = position + geometry["first_offset_inclusive"]
        stop = position + geometry["stop_offset_exclusive"]
        subsequent = next_position[position]
        flags = []
        if start < 1: flags.append("starts_before_recording")
        if stop > samples + 1: flags.append("ends_after_recording")
        if multiplicity[position] > 1: flags.append("simultaneous_condition_codes")
        if subsequent is not None and start <= subsequent < stop:
            flags.append("contains_subsequent_condition_onset")
        if not all(v["exact"] for v in matches.values()): flags.append("internal_marker_mismatch")
        if unknown: flags.append("unmapped_vector_codes_positions_not_retained")
        windows.append({"onset_sample_one_based": position, "condition_code": code,
                        "condition": CONDITIONS[code], "first_sample_one_based_inclusive": start,
                        "stop_sample_one_based_exclusive": stop,
                        "next_condition_onset_one_based": subsequent, "geometry_flags": flags})
    return {"index": expected["index"], "session": expected["session"],
            "source_internal_id_private": expected["source_id"], "sample_count": samples,
            "saved_T_seconds": T, "original_MAT_sha256": integrity["sha256"],
            "clock_geometry": geometry, "recorded_crop_category": crop,
            "recorded_preprocessing": preprocessing, "marker_comparisons": matches,
            "unmapped_nonzero_code_counts": unknown, "all_condition_onset_windows_private": windows,
            "eligibility_assigned": False, "scientific_ready": False}


def compile_metadata(contract, audit, reports):
    need(type(contract) is dict and contract.get("schema") == "stroop165_prospective_prepared_metadata_contract_v1",
         "accepted complete inspection contract")
    expected = contract["rows"]
    census = inspector.validate_roster(expected)
    need(audit.get("schema") == "stroop165_independent_whole_outcome_audit_v1"
         and audit.get("status") == "COMPLETE165_INDEPENDENT_OUTCOME_VERIFIED"
         and audit.get("complete165_verified") is True and audit.get("scientific_qualification") is False
         and audit.get("complete_originals") == 165 and audit.get("complete_inspection_reports") == 165,
         "complete accepted-audit result, never failed partial custody")
    summary = audit["regenerated_summary"]
    output = []
    iterator = iter(reports)
    for row in expected:
        try: report = next(iterator)
        except StopIteration: raise ValueError("missing complete-population report") from None
        output.append(report_record(row, report))
    try: next(iterator)
    except StopIteration: pass
    else: raise ValueError("extra complete-population report")
    exact = sum(all(v["exact"] for v in r["marker_comparisons"].values()) for r in output)
    periods = sorted(set(r["saved_T_seconds"] for r in output))
    need(summary.get("schema") == "stroop165_complete_prepared_metadata_inspection_v1"
         and summary.get("complete") is True and all(summary.get(k) == v for k, v in census.items())
         and summary.get("physical_member_bytes") == sum(r["bytes"] for r in expected)
         and summary.get("records_with_exact_direct_marker_join") == exact
         and summary.get("distinct_saved_T_values") == periods
         and summary.get("signal_arrays_materialized") is False
         and summary.get("clock_fitted") is False and summary.get("marker_shifted") is False
         and summary.get("scientific_ready") is False and summary.get("contract_sha256") == CONTRACT_SHA,
         "complete independently regenerated summary agrees with all records")
    total_events = sum(len(r["all_condition_onset_windows_private"]) for r in output)
    need(total_events <= MAX_ONSETS, "whole condition-onset retention bound")
    groups = []
    for sid in sorted({r["source_id"] for r in expected}):
        records = [r for r in output if r["source_internal_id_private"] == sid]
        session3 = next(r for r in records if r["session"] == 3)
        support = Counter(w["condition"] for w in session3["all_condition_onset_windows_private"])
        groups.append({"source_internal_id_private": sid, "record_indices": [r["index"] for r in records],
                       "sessions": [r["session"] for r in records],
                       "session3_declared_condition_support": {k: support[k] for k in CONDITIONS.values()},
                       "verified_distinct_biological_person": False})
    return {"schema": "stroop165_owner_metadata_window_ledger_v1", "task": TASK,
            "status": "COMPLETE_METADATA_LEDGER_SCIENTIFIC_HOLDS_RETAINED", **census,
            "condition_onsets_retained": total_events, "condition_onsets_discarded": 0,
            "records_with_exact_direct_marker_join": exact,
            "recorded_crop_counts": dict(sorted(Counter(r["recorded_crop_category"] for r in output).items())),
            "records_private": output, "groups_private": groups,
            "interpretation": {"window": "Integer k satisfying -5 <= k*T < 20 using exact saved numeric T; geometry only.",
                               "timing": "Saved T is a scalar, not proof of uniform sampling or stimulus-clock alignment.",
                               "crop": "Recorded strings only; no historical execution or removed-sample count inferred.",
                               "units": "Unresolved concentration/pathlength scale; geometry mm is not Hb units.",
                               "identity": "55 internally joined source groups, not independently verified distinct people.",
                               "flags": "Diagnostics retain every event; no event eligibility or exclusion is assigned."},
            "signal_values_read": False, "signal_finiteness_qualified": False,
            "candidate_packet": False, "forty_row_transform_qualified": False,
            "eligibility_assigned": False, "scientific_ready": False, "new_benchmarks": 0}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("audit", "audit-sha256", "contract", "output"):
        ap.add_argument("--" + name, required=True)
    args = ap.parse_args(argv)
    io.digest(args.audit_sha256, "externally accepted complete audit digest")
    # Configure the unchanged donor's byte cap for each serial metadata role.
    io.CAP = AUDIT_CAP
    audit = io.load_json(args.audit, args.audit_sha256)
    io.CAP = CONTRACT_BYTES
    contract = io.load_json(args.contract, CONTRACT_SHA)
    need(Path(args.contract).stat().st_size == CONTRACT_BYTES, "exact retained contract extent")
    pins = audit.get("regenerated_reports")
    need(type(pins) is list and len(pins) == 165, "all165 regenerated report descriptors")
    seen = set()
    for i, pin in enumerate(pins):
        need(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "closed report descriptor")
        path = Path(pin["path"])
        need(path.is_absolute() and path.name == "record-%03d.json" % i and str(path) not in seen,
             "complete ordered distinct report paths")
        seen.add(str(path));integer(pin["bytes"], 1, REPORT_CAP, "bounded report bytes")
        io.digest(pin["sha256"], "report digest")
    def reports():
        io.CAP = REPORT_CAP
        for pin in pins:
            need(Path(pin["path"]).stat().st_size == pin["bytes"], "report descriptor extent")
            yield io.load_json(pin["path"], pin["sha256"])
    result = compile_metadata(contract, audit, reports())
    result["accepted_audit_sha256"] = args.audit_sha256
    result["contract_sha256"] = CONTRACT_SHA
    raw = (json.dumps(result, sort_keys=True, allow_nan=False) + "\n").encode()
    need(len(raw) <= OUTPUT_CAP, "bounded full owner-only metadata ledger")
    output = Path(args.output)
    need(output.is_absolute() and not any(p.is_symlink() for p in (output, *output.parents)),
         "fresh ordinary private output path")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    print(json.dumps({"path": str(output), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                      "scientific_ready": False, "candidate_packet": False}, sort_keys=True))


if __name__ == "__main__":
    main()
