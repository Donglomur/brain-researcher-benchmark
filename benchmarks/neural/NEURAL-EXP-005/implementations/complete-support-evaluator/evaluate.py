"""Complete-support infant-macro and separate expert Brier evaluation."""

import math

from protocol import ContractError, PROTOCOL, STRATA, _finite, _seconds, _sha, _text, stratum


class _Sum:
    """Compensated streaming sum; memory does not grow with case count."""

    def __init__(self):
        self.total = 0.0
        self.correction = 0.0

    def add(self, value):
        y = value - self.correction
        new = self.total + y
        self.correction = (new - self.total) - y
        self.total = new


class _Scores:
    def __init__(self):
        self.n = 0
        self.soft = _Sum()
        self.experts = [_Sum() for _ in range(3)]
        self.disagreement = _Sum()

    def add(self, p, labels):
        q = sum(labels) / 3
        self.n += 1
        self.soft.add((p - q) ** 2)
        self.disagreement.add(q * (1 - q))
        for accumulator, label in zip(self.experts, labels):
            accumulator.add((p - label) ** 2)

    def report(self):
        if not self.n:
            return {"n": 0, "soft_vote_brier": None, "expert_brier": [None] * 3,
                    "expert_mean_brier": None, "disagreement": None}
        experts = [acc.total / self.n for acc in self.experts]
        return {"n": self.n, "soft_vote_brier": self.soft.total / self.n,
                "expert_brier": experts, "expert_mean_brier": math.fsum(experts) / 3,
                "disagreement": self.disagreement.total / self.n}


def evaluate(reference, rows):
    """Consume exactly one correctly bound probability per case in frozen order.

    Exceptions mean no full primary score; no partial report is returned. Constant
    valid predictions are legitimate controls and receive their ordinary loss.
    """
    expected = iter(reference.case_rows())
    predictions = iter(rows)
    infants = []
    for rid in reference.record_ids():
        record = reference._records[rid]
        scores = _Scores()
        strata = {name: _Scores() for name in STRATA}
        for k in range(29, _seconds(record)):
            binding = next(expected)
            try:
                row = next(predictions)
            except StopIteration as exc:
                raise ContractError("missing prediction; complete primary score withheld") from exc
            if not isinstance(row, dict) or set(row) != set(binding) | {"probability"}:
                raise ContractError("prediction requires exactly the frozen binding and probability")
            if (type(row["fold"]) is not int
                    or any(row[field] != value for field, value in binding.items())):
                raise ContractError("wrong, duplicate or out-of-order prediction binding")
            p = row["probability"]
            _finite(p, "probability")
            if not 0 <= p <= 1:
                raise ContractError("probability must be in [0,1]")
            labels = [stream[k] for stream in record["labels"]]
            scores.add(p, labels)
            strata[stratum(record["quality_flags"], k)].add(p, labels)
        rate = record["sample_rate"]
        remainder = record["sample_count"] * rate["den"] % rate["num"]
        infants.append(dict(scores.report(), recording_id=rid,
                            fold=reference._folds[rid],
                            excluded_initial_complete_seconds=29,
                            excluded_final_incomplete_second={"num": remainder, "den": rate["num"]},
                            strata={name: acc.report() for name, acc in strata.items()}))
    sentinel = object()
    if next(predictions, sentinel) is not sentinel:
        raise ContractError("extra prediction; complete primary score withheld")
    experts = [math.fsum(x["expert_brier"][i] for x in infants) / 79 for i in range(3)]
    return {
        "schema": "helsinki-complete-support-score-v1",
        "reference_sha256": reference.reference_sha256,
        "protocol_id": reference._document["protocol_id"],
        "assessment_id": reference._document["assessment_id"],
        "n_infants": 79, "n_cases": sum(x["n"] for x in infants),
        "primary_soft_vote_brier": math.fsum(x["soft_vote_brier"] for x in infants) / 79,
        "expert_brier": experts, "expert_mean_brier": math.fsum(experts) / 3,
        "disagreement": math.fsum(x["disagreement"] for x in infants) / 79,
        "stratum_case_counts": {name: sum(x["strata"][name]["n"] for x in infants) for name in STRATA},
        "infants": infants,
        "qualification": "normalized-source evaluation only; authentic data and scientific qualification remain external",
    }


def _comparison_rows(report):
    if not isinstance(report, dict) or report.get("schema") != "helsinki-complete-support-score-v1":
        raise ContractError("a complete-support score report is required")
    _sha(report.get("reference_sha256"), "reference_sha256")
    _text(report.get("assessment_id"), "assessment_id")
    if report.get("protocol_id") != PROTOCOL:
        raise ContractError("wrong comparison protocol")
    if type(report.get("n_infants")) is not int or report["n_infants"] != 79:
        raise ContractError("comparisons require exactly 79 infants")
    if type(report.get("n_cases")) is not int or report["n_cases"] <= 0:
        raise ContractError("comparisons require a positive integer total case count")
    rows = report.get("infants")
    if not isinstance(rows, list) or len(rows) != 79:
        raise ContractError("comparisons require all 79 infant scores")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ContractError("invalid infant report")
        rid = row.get("recording_id")
        _text(rid, "recording_id")
        if rid in seen:
            raise ContractError("duplicate infant report")
        seen.add(rid)
        if type(row.get("n")) is not int or row["n"] <= 0:
            raise ContractError("every infant requires positive integer primary support")
        if type(row.get("fold")) is not int or row["fold"] not in range(5):
            raise ContractError("invalid infant fold")
        value = row.get("soft_vote_brier")
        _finite(value, "infant loss")
        if not 0 <= value <= 1:
            raise ContractError("invalid Brier loss")
    if sum(row["n"] for row in rows) != report["n_cases"]:
        raise ContractError("reported total case count differs from infant support")
    primary = report.get("primary_soft_vote_brier")
    _finite(primary, "primary loss")
    macro = math.fsum(row["soft_vote_brier"] for row in rows) / 79
    if not math.isclose(primary, macro, rel_tol=0, abs_tol=1e-12):
        raise ContractError("reported primary loss differs from the equal-infant mean")
    return rows


def compare(left, right):
    """Paired infant losses for two already evaluated arms; lower loss is better.

    No resampling, significance or superiority claim. Windows/raters are not
    independent experimental units. Caller must retain the original score reports.
    """
    lrows, rrows = _comparison_rows(left), _comparison_rows(right)
    if (left["reference_sha256"] != right["reference_sha256"]
            or left["assessment_id"] != right["assessment_id"]):
        raise ContractError("comparisons require the same complete frozen reference")
    result = []
    for a, b in zip(lrows, rrows):
        if (a["recording_id"] != b["recording_id"] or a["n"] != b["n"]
                or a["fold"] != b["fold"]):
            raise ContractError("mismatched or duplicate infant support")
        result.append({"recording_id": a["recording_id"], "n": a["n"],
                       "right_minus_left_soft_vote_brier": b["soft_vote_brier"] - a["soft_vote_brier"]})
    return {"reference_sha256": left["reference_sha256"], "n_infants": 79,
            "macro_right_minus_left_soft_vote_brier": math.fsum(x["right_minus_left_soft_vote_brier"] for x in result) / 79,
            "infants": result}
