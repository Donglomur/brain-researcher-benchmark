"""Independent arithmetic cross-check for NEURAL-078; operator use only.

Does not open historical gold, admit a reference, or provide candidate feedback.
The source packet validator is shared; matching and statistics are recomputed.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import types

HERE = Path(__file__).resolve().parent
CORE_PATH = HERE.parent / "neural078-deferred-grade/scorer/analysis_core.py"
CORE_SHA256 = "d8780ed20e7c55d9d726fc894a605332856a729323ed51b95d4038e0e007bd7e"
PROTOCOL_SHA256 = "3424a79612d5a157377fd32615834652623edfb2fd662b56d89c2acf06fb71e2"
PEOPLE = tuple("sub-" + p for p in ("001", "002", "003", "004", "005", "006", "007", "010"))
NUMBERS = ("mean_RT_difference_ms", "max_abs_RT_difference_ms", "unmatched_FCz_contrast",
           "matched_FCz_contrast", "matched_HEOG_contrast", "matched_VEOG_contrast",
           "matched_preresponse_FCz_placebo")
AGGREGATES = ("matched_FCz_equal_person_mean", "matched_FCz_between_person_descriptive_SE")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read_bounded(path, limit):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        before = os.fstat(handle.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_size <= limit, "Bounded regular file required")
        raw = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    need(len(raw) <= limit and (before.st_size, before.st_mtime_ns) ==
         (after.st_size, after.st_mtime_ns), "File changed or exceeded bound")
    return raw


def load_core():
    raw = read_bounded(CORE_PATH, 32768)
    need(pin(raw)["sha256"] == CORE_SHA256, "Reviewed numerical source identity changed")
    module = types.ModuleType("neural078_pinned_audit_core")
    module.__file__ = str(CORE_PATH)
    exec(compile(raw, str(CORE_PATH), "exec"), module.__dict__)
    return module


def prefix_pairs(errors, correct, rt, ids):
    """Prefix path optimization, independent of the source suffix recurrence.

    Optimize (pair count, negative L1 distance, action-word). Base-four action
    digits are match=3, skip-correct=2, skip-error=1. At a fixed grid cell,
    equal pair count implies equal word length, so integer word order is exactly
    lexicographic action priority. Full paths include trailing skips; tied
    optimal paths have equal lengths. This recovers the source's deterministic
    earliest-action tie rule without calling its matcher or copying its table.
    """
    errors = sorted(errors, key=lambda i: (int(rt[i]), str(ids[i])))
    correct = sorted(correct, key=lambda i: (int(rt[i]), str(ids[i])))
    m, n = len(errors), len(correct)
    previous = None
    actions = [bytearray(n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        current = []
        for j in range(n + 1):
            if i == j == 0:
                current.append((0, 0, 0))
                continue
            options = []
            if i:
                a, b, word = previous[j]
                options.append(((a, b, word * 4 + 1), 1))
            if j:
                a, b, word = current[j - 1]
                options.append(((a, b, word * 4 + 2), 2))
            if i and j:
                distance = abs(int(rt[errors[i - 1]]) - int(rt[correct[j - 1]]))
                if distance * 1000 <= 25 * 1024:
                    a, b, word = previous[j - 1]
                    options.append(((a + 1, b - distance, word * 4 + 3), 3))
            best, action = max(options)
            current.append(best)
            actions[i][j] = action
        previous = current
    pairs = []
    i, j = m, n
    while i or j:
        action = actions[i][j]
        if action == 3:
            pairs.append((errors[i - 1], correct[j - 1]))
            i, j = i - 1, j - 1
        elif action == 2:
            j -= 1
        else:
            i -= 1
    return pairs[::-1]


def mean(values):
    values = list(values)
    need(bool(values), "Mean requires observations")
    # Accumulate the exact binary values before dividing. Dividing each term
    # first can erase an entirely representable mean of subnormal samples.
    exact = sum((Fraction.from_float(float(value)) for value in values), Fraction()) / len(values)
    result = float(exact)
    need(math.isfinite(result) and (result != 0 or exact == 0),
         "Mean outside finite representable arithmetic range")
    return result


def independent_summary(packet, person):
    """Consume a source-validated packet; do not call source numeric functions."""
    ids, rt = packet["trial_ids"], packet["rt_samples"]
    errors = [i for i in range(len(ids)) if int(packet["response_error"][i]) == 1]
    correct = [i for i in range(len(ids)) if int(packet["response_error"][i]) == 0]
    pairs, support = [], {}
    for hand in (1, 2):
        for congruency in (1, 2):
            def belongs(i):
                return (int(packet["response_hand"][i]) == hand and
                        int(packet["stimulus_congruency"][i]) == congruency)
            es, cs = [i for i in errors if belongs(i)], [i for i in correct if belongs(i)]
            matched = prefix_pairs(es, cs, rt, ids)
            support[f"hand{hand}_congruency{congruency}"] = {
                "error_n": len(es), "correct_n": len(cs), "pairs_n": len(matched)}
            pairs.extend(matched)
    names = sorted([[str(ids[e]), str(ids[c])] for e, c in pairs])
    digest = hashlib.sha256(json.dumps(names, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    row = {"participant_id": person, "eligible_error_n": len(errors),
           "eligible_correct_n": len(correct), "matched_pairs_n": len(pairs),
           "pair_digest": digest, "stratum_support": support,
           "status": "supported" if len(pairs) >= 10 else "insufficient_matched_pairs"}
    row.update({field: None for field in NUMBERS})
    if len(pairs) < 10:
        return row
    # Positions in the fixed -614..409 axis, using explicit integer endpoints.
    post = [[mean(packet["epochs"][i, channel, sample] for sample in range(614, 717))
             for channel in range(3)] for i in range(len(ids))]
    pre = [mean(packet["epochs"][i, 0, sample] for sample in range(102, 205))
           for i in range(len(ids))]
    deltas = [(int(rt[e]) - int(rt[c])) * 1000 / 1024 for e, c in pairs]
    row.update(mean_RT_difference_ms=mean(deltas), max_abs_RT_difference_ms=max(map(abs, deltas)),
               unmatched_FCz_contrast=mean(post[i][0] for i in errors) - mean(post[i][0] for i in correct),
               matched_FCz_contrast=mean(post[e][0] - post[c][0] for e, c in pairs),
               matched_HEOG_contrast=mean(post[e][1] - post[c][1] for e, c in pairs),
               matched_VEOG_contrast=mean(post[e][2] - post[c][2] for e, c in pairs),
               matched_preresponse_FCz_placebo=mean(pre[e] - pre[c] for e, c in pairs))
    return row


def independent_aggregate(rows):
    need([r["participant_id"] for r in rows] == list(PEOPLE), "Complete fixed cohort required")
    supported = all(r["status"] == "supported" for r in rows)
    result = {"status": "all_participants_supported" if supported else "not_all_participants_supported",
              **{field: None for field in AGGREGATES}}
    if supported:
        values = [r["matched_FCz_contrast"] for r in rows]
        average = mean(values)
        # hypot avoids unnecessary squaring overflow; denominator is sqrt(n*(n-1)).
        se = math.hypot(*(value - average for value in values)) / math.sqrt(8 * 7)
        result.update(zip(AGGREGATES, (average, se)))
    return result


def flatten(value, path=""):
    if type(value) is dict:
        for key in sorted(value):
            yield from flatten(value[key], path + "/" + key)
    else:
        yield path, value


def check_agreement(independent, original):
    """Exact support and fixed source tolerance; no sign or biological gate."""
    a, b = dict(flatten(independent)), dict(flatten(original))
    need(a.keys() == b.keys(), "Report field sets disagree")
    maximum = 0.0
    for key, value in a.items():
        other = b[key]
        if key.rsplit("/", 1)[-1] in NUMBERS + AGGREGATES and value is not None:
            need(type(value) in (int, float) and type(other) in (int, float) and
                 math.isfinite(value) and math.isfinite(other), "Finite numeric agreement required")
            error = abs(value - other)
            need(error <= 1e-9 + 1e-7 * abs(other), "Independent numerical disagreement: " + key)
            maximum = max(maximum, error / (1e-9 + 1e-7 * abs(other)))
        else:
            need(type(value) is type(other) and value == other, "Independent support disagreement: " + key)
    return {"checked_fields": len(a), "max_fraction_of_numeric_tolerance": maximum}


def audit_packets(packets, core):
    """Iterable must yield exactly the fixed eight validated-input identities."""
    rows, originals, checks = [], [], []
    for person, packet in packets:
        need(len(rows) < 8 and person == PEOPLE[len(rows)], "Complete fixed ordered cohort required")
        core.validate_packet(packet, person)
        row = independent_summary(packet, person)
        original = core.summarize(packet, person)
        checks.append(check_agreement({k: v for k, v in row.items() if k != "participant_id"},
                                      {k: v for k, v in original.items() if k != "participant_id"}))
        rows.append(row)
        originals.append(original)
    aggregate = independent_aggregate(rows)
    checks.append(check_agreement(aggregate, core.aggregate(originals)))
    report = {"schema": "neural078_contrast_submission_v1", "protocol_sha256": PROTOCOL_SHA256,
              "participants": rows, "aggregate": aggregate}
    core.validate_report(report)
    need(sum(c["checked_fields"] for c in checks) == 195, "All 195 fields required")
    return report, {"checked_fields": 195,
                    "max_fraction_of_numeric_tolerance": max(c["max_fraction_of_numeric_tolerance"] for c in checks)}


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, "Duplicate JSON key")
            out[key] = value
        return out
    def invalid(_):
        raise ValueError("Nonfinite JSON constant")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-directory", required=True, type=Path)
    parser.add_argument("--packet-pins", required=True, type=Path,
                        help="Operator-selected JSON mapping all eight person IDs to bytes/sha256")
    parser.add_argument("--output-directory", required=True, type=Path, help="Fresh operator-only directory")
    args = parser.parse_args(argv)
    try:
        need(not args.output_directory.exists() and not args.output_directory.is_symlink(), "Fresh output directory required")
        pins_raw = read_bounded(args.packet_pins, 16384)
        pins = strict_json(pins_raw)
        need(type(pins) is dict and set(pins) == set(PEOPLE), "All eight packet pins required")
        for value in pins.values():
            need(type(value) is dict and set(value) == {"bytes", "sha256"} and
                 type(value["bytes"]) is int and 1 <= value["bytes"] <= 15000000 and
                 type(value["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", value["sha256"]),
                 "Bounded canonical packet pin required")
        core = load_core()
        def packets():
            for person in PEOPLE:
                raw = read_bounded(args.packet_directory / (person + ".npz"), 15000000)
                need(pin(raw) == pins[person], "Selected packet identity mismatch: " + person)
                yield person, core.load_packet_bytes(raw, person)
        report, check = audit_packets(packets(), core)
        body = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
        receipt = {"schema": "neural078_independent_reference_arithmetic_audit_v1", "task_id": "NEURAL-078",
                   "protocol_sha256": PROTOCOL_SHA256, "source_core_sha256": CORE_SHA256,
                   "audit_source": pin(read_bounded(Path(__file__), 32768)),
                   "packet_pins": pins, "packet_pin_file": pin(pins_raw), "reference": pin(body),
                   "comparison": check, "historical_reference_opened": False,
                   "qualification": "Independent arithmetic agreement only; operator admission and source timing remain external."}
        # Publish only after every person and aggregate has agreed. An incomplete
        # directory after an I/O failure has no successful receipt and must not be used.
        args.output_directory.mkdir(mode=0o700)
        with (args.output_directory / "REFERENCE.json").open("xb") as handle:
            handle.write(body)
        with (args.output_directory / "AUDIT.json").open("x", encoding="utf-8") as handle:
            json.dump(receipt, handle, indent=2, allow_nan=False)
            handle.write("\n")
        return 0
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        print("NEURAL-078 reference audit refused: " + str(exc), file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
