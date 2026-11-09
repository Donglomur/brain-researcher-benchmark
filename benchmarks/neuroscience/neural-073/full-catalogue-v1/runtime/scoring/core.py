"""Explicit-data scoring only: importing this module never discovers inputs."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
import math
import sys

PERSONS = ("sub-01", "sub-02", "sub-04", "sub-05", "sub-06", "sub-07", "sub-08",
           "sub-09", "sub-11", "sub-12", "sub-13", "sub-14", "sub-15")
CLASSES = 25


class QualificationError(ValueError):
    """An input/reference/numerical problem, never a candidate failure score."""


@dataclass(frozen=True)
class Record:
    case_id: str
    person: str
    label: int

    def to_dict(self):
        return {"case_id": self.case_id, "person": self.person, "label": self.label}

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {"case_id", "person", "label"}:
            raise QualificationError("exact private record fields required")
        return cls(**value)


def checked_records(records, classes=CLASSES):
    records = tuple(records)
    if type(classes) is not int or classes < 2 or not records:
        raise QualificationError("nonempty records and at least two classes required")
    ids = set()
    for r in records:
        if (not isinstance(r, Record) or not isinstance(r.case_id, str) or not r.case_id
                or not isinstance(r.person, str) or not r.person or type(r.label) is not int
                or not 0 <= r.label < classes or r.case_id in ids):
            raise QualificationError("invalid or duplicate private record")
        ids.add(r.case_id)
    return records


def validate_full_scope(records):
    """Structural guard, NOT authentication of the frozen source catalogue."""
    records = checked_records(records)
    cells = {(r.person, r.label) for r in records}
    support = Counter(p for p, _ in cells)
    expected = {p: 12 if p == "sub-02" else 13 if p == "sub-08" else 25 for p in PERSONS}
    if len(records) != 9532 or dict(support) != expected or len(cells) != 300:
        raise QualificationError("complete 9532/13/25/300 available-support scope required")
    return {"records": 9532, "persons": 13, "classes": 25, "cells": 300,
            "identity_authentication": "separate trusted admission required"}


def exact_weights(records, classes=CLASSES):
    """Use the complete required rows of each included person, never valid-output rows."""
    records = checked_records(records, classes)
    cells = Counter((r.person, r.label) for r in records)
    support = Counter(p for p, _ in cells)
    persons = len(support)
    weights = {r.case_id: Fraction(1, persons * support[r.person] * cells[r.person, r.label])
               for r in records}
    if sum(weights.values(), Fraction()) != 1:
        raise QualificationError("weight closure failed")
    return weights


def fraction_json(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def argmax(values):
    if not values:
        raise QualificationError("empty class vector")
    return max(range(len(values)), key=values.__getitem__)


def finite_scores(values, classes=CLASSES):
    if (sys.float_info.radix, sys.float_info.mant_dig, sys.float_info.max_exp) != (2, 53, 1024):
        raise QualificationError("IEEE-754 binary64 Python float required")
    if not isinstance(values, (list, tuple)) or len(values) != classes:
        raise QualificationError("wrong raw score vector length")
    out = []
    for v in values:
        if type(v) not in (int, float):
            raise QualificationError("score is not a real JSON number")
        try:
            v = float(v)
        except (ValueError, OverflowError):
            raise QualificationError("score conversion overflow") from None
        if not math.isfinite(v):
            raise QualificationError("nonfinite score")
        out.append(v)
    return tuple(out)


def probability_vector(values, classes=CLASSES):
    """Return normalized accepted float64 values; do not clip or repair invalid rows."""
    out = finite_scores(values, classes)
    if any(v < 0 or v > 1 for v in out):
        raise QualificationError("probability outside [0,1]")
    total = math.fsum(out)
    if total <= 0 or abs(total - 1.0) > 1e-6:
        raise QualificationError("probability sum outside absolute tolerance")
    return tuple(v / total for v in out)


def accepted_probability_vector(values, classes=CLASSES):
    """Check an already normalized vector without a second rounding operation."""
    out = finite_scores(values, classes)
    if any(v < 0 or v > 1 for v in out) or abs(math.fsum(out) - 1.0) > 1e-12:
        raise QualificationError("scorer requires previously normalized accepted probabilities")
    return out


def brier(probabilities, label):
    return math.fsum((p - (k == label)) ** 2 for k, p in enumerate(probabilities))


def records_digest(records):
    """SHA256 of canonical ordered list [{case_id,person,label}, ...]."""
    from ..core.custody import digest
    return digest([r.to_dict() for r in records])


def score_panel(records, probabilities, *, production=True, classes=CLASSES,
                authority=None, closure_digest=None, construction_by_case=None):
    """Unknown IDs are an evaluator error. Missing/None IDs are candidate failures.

    Parser returns only normalized valid vectors or None. Direct callers must supply
    already accepted probabilities; invalid direct vectors raise QualificationError.
    Production is the default. Tiny controls must opt out explicitly.
    """
    records = checked_records(records, classes)
    authorization = None
    record_pin = records_digest(records)
    if production:
        from ..core.custody import VerifiedAuthority, require_digest
        if not isinstance(authority, VerifiedAuthority):
            raise QualificationError("production scoring requires verified trusted authority")
        require_digest(closure_digest)
        authorization = authority.require(role="score", domain="authentic", bindings={
            "records_digest": record_pin, "closure_digest": closure_digest})
        if classes != CLASSES:
            raise QualificationError("production classes must be 25")
        validate_full_scope(records)
    weights = exact_weights(records, classes)
    expected = {r.case_id for r in records}
    if set(probabilities) - expected:
        raise QualificationError("score input contains unknown IDs")
    if construction_by_case is None:
        if production:
            raise QualificationError("complete private construction mapping required")
    elif (set(construction_by_case) != expected or
          any(v not in ("AP", "PA", "FFX") for v in construction_by_case.values())):
        raise QualificationError("invalid private construction mapping")
    if production:
        from ..core.custody import digest
        if Counter(construction_by_case.values()) != {"AP": 3505, "PA": 3975, "FFX": 2052}:
            raise QualificationError("complete declared construction counts required")
        authority.require(role="score", domain="authentic", bindings={
            "construction_digest": digest(construction_by_case)})
    rows, by_person, by_cell = {}, defaultdict(list), defaultdict(list)
    for r in records:
        raw = probabilities.get(r.case_id)
        valid = raw is not None
        p = accepted_probability_vector(raw, classes) if valid else None
        correct = int(argmax(p) == r.label) if valid else 0
        loss = brier(p, r.label) if valid else 2.0
        row = {"accuracy": correct, "brier_with_failure_penalty": loss, "valid": valid}
        rows[r.case_id] = row
        by_person[r.person].append(r)
        by_cell[r.person, r.label].append(r)
    exact_acc = sum((weights[r.case_id] * rows[r.case_id]["accuracy"] for r in records), Fraction())
    valid_weight = sum((weights[r.case_id] for r in records if rows[r.case_id]["valid"]), Fraction())
    valid_count = sum(row["valid"] for row in rows.values())
    valid_loss = math.fsum(float(weights[r.case_id]) * rows[r.case_id]["brier_with_failure_penalty"]
                           for r in records if rows[r.case_id]["valid"])
    people = {}
    for person, subset in sorted(by_person.items()):
        local_w = exact_weights(subset, classes)
        local_acc = sum((local_w[r.case_id] * rows[r.case_id]["accuracy"] for r in subset), Fraction())
        local_valid_weight = sum((local_w[r.case_id] for r in subset if rows[r.case_id]["valid"]), Fraction())
        people[person] = {"accuracy": float(local_acc), "accuracy_exact": fraction_json(local_acc),
                          "brier_with_failure_penalty": math.fsum(float(local_w[r.case_id]) * rows[r.case_id]["brier_with_failure_penalty"] for r in subset),
                          "records": len(subset), "valid_records": sum(rows[r.case_id]["valid"] for r in subset),
                          "failed_records": sum(not rows[r.case_id]["valid"] for r in subset),
                          "weighted_coverage": float(local_valid_weight),
                          "weighted_coverage_exact": fraction_json(local_valid_weight),
                          "unweighted_coverage": sum(rows[r.case_id]["valid"] for r in subset) / len(subset)}
    cells = [{"person": p, "label": c, "records": len(rs),
              "valid_records": sum(rows[r.case_id]["valid"] for r in rs),
              "failures": sum(not rows[r.case_id]["valid"] for r in rs),
              "weighted_coverage": sum(rows[r.case_id]["valid"] for r in rs) / len(rs),
              "unweighted_coverage": sum(rows[r.case_id]["valid"] for r in rs) / len(rs)}
             for (p, c), rs in sorted(by_cell.items())]
    labels = []
    for label in range(classes):
        rs = [r for r in records if r.label == label]
        mass = sum((weights[r.case_id] for r in rs), Fraction())
        valid_mass = sum((weights[r.case_id] for r in rs if rows[r.case_id]["valid"]), Fraction())
        labels.append({"label": label, "records": len(rs),
            "valid_records": sum(rows[r.case_id]["valid"] for r in rs),
            "failed_records": sum(not rows[r.case_id]["valid"] for r in rs),
            "weighted_coverage": float(valid_mass / mass) if mass else None,
            "unweighted_coverage": sum(rows[r.case_id]["valid"] for r in rs) / len(rs) if rs else None,
            "global_weight_mass_exact": fraction_json(mass), "valid_global_weight_mass_exact": fraction_json(valid_mass)})
    construction = []
    if construction_by_case is not None:
        for group in ("AP", "PA", "FFX"):
            rs = [r for r in records if construction_by_case[r.case_id] == group]
            total_mass = sum((weights[r.case_id] for r in rs), Fraction())
            valid_mass = sum((weights[r.case_id] for r in rs if rows[r.case_id]["valid"]), Fraction())
            construction.append({"construction": group, "records": len(rs),
                "valid_records": sum(rows[r.case_id]["valid"] for r in rs),
                "failures": sum(not rows[r.case_id]["valid"] for r in rs),
                "unweighted_coverage": sum(rows[r.case_id]["valid"] for r in rs) / len(rs) if rs else None,
                "global_weight_mass_exact": fraction_json(total_mass),
                "valid_global_weight_mass_exact": fraction_json(valid_mass),
                "within_group_weighted_coverage": float(valid_mass / total_mass) if total_mass else None})
    return {"mode": "production-authorized" if production else "invented-control",
            "records_digest": record_pin, "closure_digest": closure_digest if production else None,
            "authority_digest": authorization,
            "accuracy": float(exact_acc), "accuracy_exact": fraction_json(exact_acc),
            "brier_with_failure_penalty": math.fsum(float(weights[r.case_id]) * rows[r.case_id]["brier_with_failure_penalty"] for r in records),
            "probability_metric_label": "Brier" if valid_count == len(records) else "Brier with failure penalty",
            "weighted_coverage": float(valid_weight), "weighted_coverage_exact": fraction_json(valid_weight),
            "unweighted_coverage": valid_count / len(records),
            "valid_row_weighted_brier": valid_loss / float(valid_weight) if valid_weight else None,
            "valid_records": valid_count, "failed_records": len(records) - valid_count,
            "people": people, "cells": cells, "labels": labels, "construction": construction, "rows": rows}


def weighted_prior(records, classes=CLASSES):
    records = checked_records(records, classes)
    weights = exact_weights(records, classes)
    mass = [sum((weights[r.case_id] for r in records if r.label == k), Fraction()) for k in range(classes)]
    return {"probabilities": [float(v) for v in mass], "exact_mass": [fraction_json(v) for v in mass],
            "optimized_fits": 0, "calibrator_fits": 0}
