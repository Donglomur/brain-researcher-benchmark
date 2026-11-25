"""FUS-DIRECTION: complete adjudicated intake -> descriptive, grouped score.

This schema is a trusted operator projection, not an original MAT-file schema.
No file access, model, fit, image manipulation, or acquisition occurs here.
"""
import hashlib
import json
import math
import re
from collections import Counter
from fractions import Fraction
from roster import FIELDS, ROSTER

CONTRACT_SHA256 = "a0fc7cd1008f907df8d24c8a2133896d99b90915764debd141194022914f301f"
ROSTER_SHA256 = "deb726b85aa3c8894cfebe0485ce22ceb99fa55f97c3a52a22f4e4cccabacc8d"
CONDITIONS = ("native_A", "program_B", "tools_C", "augmented_program_B", "augmented_tools_C")
EXCLUSIONS = ("missing_target", "missing_timing", "missing_baseline", "no_complete_memory_acquisition")
METRICS = ("balanced_accuracy", "accuracy", "angular_error_deg", "brier")
HEX = re.compile(r"[0-9a-f]{64}\Z")
OPAQUE = re.compile(r"q_[0-9a-f]{32}\Z")


class ConstructionError(ValueError):
    """The fixed scientific denominator is not admitted. No candidate score."""


def require(ok, message):
    if not ok:
        raise ConstructionError(message)


def exact_keys(value, keys, where):
    require(type(value) is dict and set(value) == set(keys), where + ": keys")


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def pin(value):
    return type(value) is str and HEX.fullmatch(value) is not None


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def validate_intake(intake):
    """Validate ALL rows before scoring; return the private query partitions.

    External review must authenticate the source/clock/eligibility/projection
    receipts. Their digests alone cannot prove provenance or protected custody.
    """
    exact_keys(intake, ("schema", "contract_sha256", "source_roster_sha256",
                       "source_archive_sha256", "intake_review_sha256", "records"), "intake")
    require(intake["schema"] == "fus_adjudicated_intake_v1", "intake schema")
    require(intake["contract_sha256"] == CONTRACT_SHA256, "contract identity")
    require(intake["source_roster_sha256"] == ROSTER_SHA256, "source roster identity")
    require(pin(intake["source_archive_sha256"]) and pin(intake["intake_review_sha256"]),
            "complete archive and independent intake review identities required")
    roster = [dict(zip(FIELDS, row)) for row in ROSTER]
    require(type(intake["records"]) is list and len(intake["records"]) == 49, "complete intake roster")
    expected = {r["record_id"]: r for r in roster}
    require(len(expected) == 49 and sum(r["declared_trials"] for r in roster) == 20622,
            "source roster support")
    partitions, source_ids, opaque_ids, seen_records = [], set(), set(), set()
    for record in intake["records"]:
        exact_keys(record, ("record_id", "native_hz", "reconciliation_sha256",
                           "clock_mapping_sha256", "representation_sha256", "trials"), "record")
        rid = record["record_id"]
        require(type(rid) is str and rid in expected and rid not in seen_records, "record membership")
        seen_records.add(rid)
        meta = expected[rid]
        require(pin(record["reconciliation_sha256"]), "record reconciliation evidence")
        trials = record["trials"]
        require(type(trials) is list and len(trials) == meta["declared_trials"],
                "observed count disagrees with source metadata: amend intake before evaluation")
        if not trials:
            require(rid == "L-S45-R1" and record["native_hz"] is None and
                    record["clock_mapping_sha256"] is None and record["representation_sha256"] is None,
                    "preserve reconciled zero record without inventing timing")
            partitions.append((meta, record, [], 0, 0))
            continue
        require(type(record["native_hz"]) is int and record["native_hz"] in (1, 2), "native Hz")
        require(pin(record["clock_mapping_sha256"]) and pin(record["representation_sha256"]),
                "clock mapping and complete field representation evidence required")
        eligible, excluded = [], 0
        for ordinal, trial in enumerate(trials):
            exact_keys(trial, ("source_trial_id", "source_order", "disposition", "query_id",
                               "direction", "timing", "exclusion_reason", "adjudication_sha256"), "trial")
            sid = trial["source_trial_id"]
            require(type(sid) is str and 0 < len(sid) <= 200 and sid not in source_ids,
                    "globally unique source trial lineage, including Run99, required")
            source_ids.add(sid)
            require(type(trial["source_order"]) is int and trial["source_order"] == ordinal,
                    "complete ordered source census")
            if trial["disposition"] == "adjudicated_excluded":
                require(trial["exclusion_reason"] in EXCLUSIONS and
                        trial["adjudication_sha256"] == intake["intake_review_sha256"] and
                        trial["query_id"] is None and trial["timing"] is None and
                        (trial["direction"] is None or
                         (type(trial["direction"]) is int and 0 <= trial["direction"] < 8)),
                        "unresolved/extraneous eligibility exclusion")
                excluded += 1
                continue
            require(trial["disposition"] == "eligible" and trial["exclusion_reason"] is None and
                    trial["adjudication_sha256"] is None, "eligibility is unresolved")
            qid = trial["query_id"]
            require(type(qid) is str and OPAQUE.fullmatch(qid) and qid not in opaque_ids,
                    "unique opaque case identity required")
            opaque_ids.add(qid)
            require(type(trial["direction"]) is int and 0 <= trial["direction"] < 8, "direction class")
            t = trial["timing"]
            exact_keys(t, ("cue", "memory_start", "memory_end", "go",
                           "baseline_start", "baseline_end", "acquisition_start", "acquisition_end"), "timing")
            require(all(finite(v) for v in t.values()), "finite common-clock timing")
            require(t["baseline_start"] < t["baseline_end"] < t["cue"] <= t["memory_start"] <
                    t["memory_end"] <= t["go"], "cue/memory/go or pre-cue baseline interval")
            require(t["memory_start"] <= t["acquisition_start"] < t["acquisition_end"] <=
                    min(t["memory_end"], t["go"]), "complete acquisition must lie wholly inside memory")
            eligible.append(trial)
        support = set()
        queries = []
        for trial in eligible:
            if trial["direction"] not in support:
                support.add(trial["direction"])
            else:
                queries.append(trial)
        require(support == set(range(8)), "all eight earliest eligible calibration directions required")
        require({t["direction"] for t in queries} == set(range(8)),
                "missing post-calibration class: balanced-accuracy estimand undefined")
        partitions.append((meta, record, queries, 8, excluded))
    require(seen_records == set(expected), "complete 49-row census")
    return partitions


def probabilities(value):
    """Tolerance is validation only; normalize admitted vectors for proper loss."""
    if type(value) is not list or len(value) != 8 or not all(finite(x) and 0 <= x <= 1 for x in value):
        return None
    total = math.fsum(value)
    if abs(total - 1.0) > 1e-6:
        return None
    return [x / total for x in value]


def prediction_index(predictions, expected):
    """Extra/unassignable rows invalidate the whole submission; no added trials."""
    found, reasons, global_reasons = {}, Counter(), Counter()
    if type(predictions) is not list:
        return {}, {"malformed_submission": 1}, True
    for row in predictions:
        if type(row) is not dict or type(row.get("query_id")) is not str or row["query_id"] not in expected:
            global_reasons["extra_or_unassignable_row"] += 1
            continue
        qid = row["query_id"]
        if qid in found:
            found[qid] = None
            reasons["duplicate_rows"] += 1
        else:
            found[qid] = probabilities(row.get("probabilities")) if set(row) == {"query_id", "probabilities"} else None
            if found[qid] is None:
                reasons["malformed_rows"] += 1
    reasons["missing_queries"] = len(expected - set(found))
    reasons.update(global_reasons)
    return found, dict(reasons), bool(global_reasons)


def session_score(queries, values, invalidate_all):
    confusion = [[0] * 8 for _ in range(8)]
    support, invalid = [0] * 8, [0] * 8
    angles, briers = [], []
    bins = [{"count": 0, "confidence_sum": 0.0, "correct": 0} for _ in range(10)]
    for trial in queries:
        y = trial["direction"]
        support[y] += 1
        p = None if invalidate_all else values.get(trial["query_id"])
        if p is None:
            invalid[y] += 1
            angles.append(180.0)
            briers.append(2.0)
            continue
        predicted = max(range(8), key=lambda i: p[i])  # first/lowest angle wins exact ties
        confusion[y][predicted] += 1
        distance = abs(predicted - y)
        angles.append(45.0 * min(distance, 8 - distance))
        residuals = [p[i] - int(i == y) for i in range(8)]
        squares = [r ** 2 for r in residuals]
        if any(r != 0 and square < float.fromhex("0x1p-1022")
               for r, square in zip(residuals, squares)):
            # Round the complete sum once when individual squares underflow.
            # Normal-range inputs keep the established reduction unchanged.
            briers.append(float(sum((Fraction(r) ** 2 for r in residuals), Fraction())))
        else:
            briers.append(math.fsum(squares))
        b = bins[min(9, int(max(p) * 10))]
        b["count"] += 1
        b["confidence_sum"] += max(p)
        b["correct"] += int(predicted == y)
    n = len(queries)
    return {"queries": n, "class_support": support, "confusion": confusion, "invalid_by_class": invalid,
            "balanced_accuracy": math.fsum(confusion[i][i] / support[i] for i in range(8)) / 8,
            "accuracy": sum(confusion[i][i] for i in range(8)) / n,
            "angular_error_deg": math.fsum(angles) / n, "brier": math.fsum(briers) / n,
            "reliability_bins": bins, "reliability_invalid": sum(invalid)}


def aggregate(rows):
    """Equal sessions within each represented animal, then equal animals."""
    animals = {}
    for animal in ("L", "P"):
        selected = [r for r in rows if r["animal"] == animal]
        if selected:
            animals[animal] = {key: math.fsum(r[key] for r in selected) / len(selected) for key in METRICS}
            animals[animal]["sessions"] = len(selected)
    return {"animals": animals, "equal_animal_mean":
            {key: math.fsum(a[key] for a in animals.values()) / len(animals) for key in METRICS}}


def evaluate(intake, predictions, *, condition):
    require(condition in CONDITIONS, "explicit allowed evidence condition required")
    partitions = validate_intake(intake)
    expected = {t["query_id"] for _, _, queries, _, _ in partitions for t in queries}
    values, reasons, invalidate_all = prediction_index(predictions, expected)
    rows, census = [], []
    for meta, record, queries, calibration, excluded in partitions:
        census.append({"record_id": meta["record_id"], "source_trials": meta["declared_trials"],
                       "calibration": calibration, "queries": len(queries), "adjudicated_excluded": excluded})
        if not queries:
            continue  # exactly the admitted zero record; no invented replicate
        score = session_score(queries, values, invalidate_all)
        score.update({k: meta[k] for k in ("record_id", "animal", "system", "elapsed_days")})
        score["native_hz"] = record["native_hz"]
        rows.append(score)
    overall = aggregate(rows)
    require({a: b["sessions"] for a, b in overall["animals"].items()} == {"L": 26, "P": 22},
            "complete positive session support")
    return {"schema": "fus_complete_descriptive_score_v1", "status": "scored",
            "condition": condition, "intake_sha256": canonical_hash(intake),
            "scientifically_qualified": False, "protected_evaluation_established": False,
            "biological_animals": 2, "roster_records": 49, "positive_records": 48,
            "queries": len(expected), "source_census": census, "sessions": rows,
            "prediction_issues": reasons, "whole_submission_invalid": invalidate_all,
            "primary": overall["equal_animal_mean"]["balanced_accuracy"], "overall": overall,
            "by_system": {s: aggregate([r for r in rows if r["system"] == s])
                          for s in sorted({r["system"] for r in rows})},
            "by_native_hz": {str(h): aggregate([r for r in rows if r["native_hz"] == h])
                             for h in sorted({r["native_hz"] for r in rows})},
            "uncertainty": "descriptive; two animals; no population CI or trialwise independent-replicate inference"}


def paired_delta(candidate, reference):
    """Positive accuracy differences favor candidate; negative loss differences do.

    Inputs must be owner-retained complete evaluator outputs. This helper does
    not authenticate arbitrary result JSON or establish matched information.
    """
    require(candidate["schema"] == reference["schema"] == "fus_complete_descriptive_score_v1" and
            candidate["intake_sha256"] == reference["intake_sha256"] and
            candidate["source_census"] == reference["source_census"], "paired intake/support mismatch")
    left, right = candidate["sessions"], reference["sessions"]
    require(len(left) == len(right) == 48, "complete paired session support")
    rows = []
    for a, b in zip(left, right):
        require(all(a[k] == b[k] for k in ("record_id", "animal", "class_support", "queries")),
                "paired session/class mismatch")
        rows.append({"record_id": a["record_id"], "animal": a["animal"],
                     **{key: a[key] - b[key] for key in METRICS}})
    require(candidate["condition"] in CONDITIONS and reference["condition"] in CONDITIONS,
            "paired evidence conditions required")
    return {"sign": "candidate_minus_reference", "candidate_condition": candidate["condition"],
            "reference_condition": reference["condition"], "intake_sha256": candidate["intake_sha256"],
            "sessions": rows, "overall": aggregate(rows),
            "information_matched_by_scorer": False, "population_inference": False}
