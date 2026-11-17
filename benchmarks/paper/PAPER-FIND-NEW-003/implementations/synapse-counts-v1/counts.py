"""Count reduction for the original BANC synaptic-link evaluation.

This module starts AFTER the source's expert matching/adjudication. It does not
infer TP/FP/FN from detector output or establish candidate superiority.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction


class CountError(ValueError):
    """A count table does not satisfy the original evaluation structure."""


@dataclass(frozen=True)
class Counts:
    tp: int
    fp: int
    fn: int

    def __post_init__(self):
        for value in (self.tp, self.fp, self.fn):
            if type(value) is not int or value < 0:
                raise CountError("Counts must be nonnegative integers, not bools/floats")

    def __add__(self, other):
        if not isinstance(other, Counts):
            return NotImplemented
        return Counts(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)

    def metrics(self):
        """Undefined precision/recall/F1 stay None instead of becoming 0 or 1."""
        def ratio(numerator, denominator):
            return Fraction(numerator, denominator) if denominator else None

        return {
            "precision": ratio(self.tp, self.tp + self.fp),
            "recall": ratio(self.tp, self.tp + self.fn),
            "f1_score": ratio(2 * self.tp, 2 * self.tp + self.fp + self.fn),
        }

    def summary(self):
        return {
            "true_positives": self.tp,
            "false_positives": self.fp,
            "false_negatives": self.fn,
            "expert_positive_links": self.tp + self.fn,
            "predicted_links": self.tp + self.fp,
            **{key: None if value is None else float(value)
               for key, value in self.metrics().items()},
        }


def integer(text, column):
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]+", text.strip()):
        raise CountError(f"{column} must contain an unsigned integer")
    return int(text)


def rows_from_csv(payload):
    """Strictly read the author's count/metric columns; reject ragged rows."""
    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), strict=True)
        fields = reader.fieldnames or []
        required = {"cutouts", "neuropil", "region", "true_positives", "false_positives",
                    "false_negatives", "precision", "recall", "f1_score"}
        if len(set(fields)) != len(fields) or not required.issubset(fields):
            raise CountError("Missing or duplicate source CSV columns")
        result = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise CountError("Ragged source CSV row")
            if any(not row[key].strip() for key in required):
                raise CountError("Empty source CSV field")
            result.append(row)
        return result
    except (UnicodeDecodeError, csv.Error) as error:
        raise CountError("Invalid UTF-8 CSV") from error


def validate_displayed_metric(text, exact, name):
    """Check source displays within one unit of their printed precision.

    This checks the author table, not a candidate-submitted performance claim.
    The actual source includes F1 values outside nearest-rounding tolerance:
    SPS_left and HTct_left. Preserve that evidence instead of editing counts.
    Full-precision decimals get a 1e-12 numerical allowance. Return whether a
    value lies beyond nearest-rounding tolerance for the report's diagnostics.
    """
    try:
        value = Decimal(text)
    except (InvalidOperation, TypeError):
        raise CountError(f"Invalid {name}") from None
    if not value.is_finite() or not 0 <= value <= 1 or exact is None:
        raise CountError(f"Invalid or undefined {name}")
    unit = Fraction(Decimal(1).scaleb(value.as_tuple().exponent))
    difference = abs(Fraction(value) - exact)
    if difference > unit + Fraction(1, 10**12):
        raise CountError(f"Source {name} disagrees with source counts")
    return difference > unit / 2 + Fraction(1, 10**12)


def reduce_rows(rows, cohort, pooled_identity=None):
    """Reduce the frozen (cutout ID, neuropil, region) roster before scoring.

    The recovered source has 16 rows and no pooled row. If a future table also
    contains a pooled row, explicitly identify and check it, never include it
    in the sum. Row order does not affect cohort identity.
    """
    cohort = tuple(tuple(identity) for identity in cohort)
    pooled_identity = None if pooled_identity is None else tuple(pooled_identity)
    if len(cohort) != 16 or len(set(cohort)) != 16 or pooled_identity in cohort:
        raise CountError("Original cohort must have 16 distinct cutouts")
    if any(len(identity) != 3 for identity in cohort):
        raise CountError("Cutout identities need ID, neuropil and region")
    expected = set(cohort) | ({pooled_identity} if pooled_identity else set())
    observed = {}
    display_diagnostics = []
    for row in rows:
        try:
            identity = (row["cutouts"], row["neuropil"], row["region"])
            counts = Counts(*(integer(row[name], name) for name in
                              ("true_positives", "false_positives", "false_negatives")))
        except KeyError as error:
            raise CountError(f"Missing column {error.args[0]}") from error
        if identity not in expected:
            raise CountError("Unexpected cutout/region identity")
        if identity in observed:
            raise CountError("Duplicate cutout/region identity")
        for name, exact in counts.metrics().items():
            if name not in row:
                raise CountError(f"Missing column {name}")
            if validate_displayed_metric(row[name], exact, name):
                display_diagnostics.append({"cutout_id": identity[0], "metric": name,
                    "source_display": row[name], "from_counts": float(exact),
                    "issue": "outside_nearest_rounding_but_within_one_printed_unit"})
        observed[identity] = counts
    if set(observed) != expected:
        raise CountError("Missing original cutouts or explicitly requested pooled source row")
    total = Counts(0, 0, 0)
    for identity in cohort:
        total += observed[identity]
    if pooled_identity and total != observed[pooled_identity]:
        raise CountError("Pooled source counts differ from the sum of all 16 cutouts")
    return {
        "cutout_count": 16,
        "aggregation": "sum_tp_fp_fn_then_compute_metrics",
        "aggregate": total.summary(),
        "source_display_diagnostics": display_diagnostics,
        "per_cutout": [{"cutout_id": identity[0], "neuropil": identity[1], "region": identity[2],
                        **observed[identity].summary()} for identity in cohort],
    }
