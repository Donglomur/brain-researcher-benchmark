"""Operator-only probability diagnostics for already admitted sleep predictions.

No data loading, model fitting, network, calibration fitting, or grading authority.
All nights are pooled within person; panel summaries give each person equal weight.
The log-loss probability floor is a declared reporting convention, not a repair
of prediction rows. Marginal frequency agreement is not full calibration.
"""
import copy
import math

CLASSES = ("W", "N1", "N2", "N3", "R")
EPSILON = 1e-15
SIMPLEX_TOLERANCE = 1e-6  # Unchanged from the full153 scorer's admission rule.


def need(condition, message):
    if not condition:
        raise ValueError(message)


class _Sum:
    """Compensated streaming addition; memory does not grow with epoch count."""
    def __init__(self):
        self.total = 0.0
        self.correction = 0.0

    def add(self, value):
        result = self.total + value
        if abs(self.total) >= abs(value):
            self.correction += (self.total - result) + value
        else:
            self.correction += (value - result) + self.total
        self.total = result

    def value(self):
        return self.total + self.correction


class ProbabilityAccumulator:
    """Accumulate one person's complete nights after the protected score barrier."""
    def __init__(self):
        self._active = None
        self._nights = {}
        self._clock = 0
        self._eligible = 0
        self._masked = 0
        self._clipped = 0
        self._truth = [0] * 5
        self._probabilities = [_Sum() for _ in CLASSES]
        self._brier = _Sum()
        self._loss = _Sum()

    def begin_night(self, night, epochs):
        need(self._active is None, "Finish the previous night")
        need(type(night) is int and night >= 0, "Integer source night")
        need(night not in self._nights, "Unique night within person")
        need(type(epochs) is int and epochs > 0, "Positive full-clock extent")
        self._active = {"night": night, "expected": epochs, "clock": 0,
                        "eligible": 0, "masked": 0}

    def update(self, row, stage):
        need(self._active is not None, "A declared night must be open")
        need(self._active["clock"] < self._active["expected"], "No excess rows")
        need(type(stage) is int and -1 <= stage < 5, "Declared stage or mask")
        need(type(row) is list and len(row) == 5, "Five ordered probabilities")
        need(all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1
                 for x in row), "Finite nonboolean probability values")
        need(abs(math.fsum(row) - 1) <= SIMPLEX_TOLERANCE,
             "Unchanged probability simplex rule; no renormalization")
        self._active["clock"] += 1
        self._clock += 1
        if stage < 0:
            self._active["masked"] += 1
            self._masked += 1
            return
        self._active["eligible"] += 1
        self._eligible += 1
        self._truth[stage] += 1
        for summation, probability in zip(self._probabilities, row):
            summation.add(probability)
        self._brier.add(math.fsum((p - int(k == stage)) ** 2
                                 for k, p in enumerate(row)))
        self._loss.add(-math.log(max(EPSILON, row[stage])))
        self._clipped += int(row[stage] < EPSILON)

    def end_night(self):
        need(self._active is not None, "A night must be open")
        a = self._active
        need(a["clock"] == a["expected"], "Every declared full-clock row required")
        self._nights[a["night"]] = {k: a[k] for k in ("clock", "eligible", "masked")}
        self._active = None

    def result(self):
        need(self._active is None and self._nights, "Complete nonempty night panel")
        count = self._eligible
        predicted = [s.value() / count for s in self._probabilities] if count else None
        observed = [n / count for n in self._truth] if count else None
        return {
            "schema": "sleep_probability_diagnostics_person_v1",
            "classes": list(CLASSES),
            "clock_epochs": self._clock,
            "eligible_epochs": count,
            "masked_epochs": self._masked,
            "nights": {str(k): dict(v) for k, v in sorted(self._nights.items())},
            "truth_counts": list(self._truth),
            "mean_multiclass_brier": self._brier.value() / count if count else None,
            "mean_clipped_log_loss_nats": self._loss.value() / count if count else None,
            "log_loss_floor": EPSILON,
            "log_loss_clipped_epochs": self._clipped,
            "mean_predicted_probability": predicted,
            "observed_class_frequency": observed,
            "calibration_in_large_predicted_minus_observed": (
                [p - t for p, t in zip(predicted, observed)] if count else None),
            "defined": bool(count),
        }


def panel_macro(reports, confusion_by_person):
    """Bind diagnostic support to the same trusted per-person confusion matrices.

    This consistency join does not authenticate an arbitrary submitted dictionary.
    The caller must already have admitted the complete source/provenance panel.
    """
    need(type(reports) is dict and type(confusion_by_person) is dict,
         "Person mappings required")
    need(reports and set(reports) == set(confusion_by_person), "Exact person support")
    for person, report in reports.items():
        matrix = confusion_by_person[person]
        need(type(matrix) is list and len(matrix) == 5 and
             all(type(row) is list and len(row) == 5 for row in matrix),
             "Five-class confusion matrix")
        need(all(type(x) is int and x >= 0 for row in matrix for x in row),
             "Nonnegative integer confusion counts")
        truth = [sum(row) for row in matrix]
        need(report["schema"] == "sleep_probability_diagnostics_person_v1" and
             report["classes"] == list(CLASSES), "Matching diagnostic taxonomy")
        need(report["truth_counts"] == truth and report["eligible_epochs"] == sum(truth),
             "Probability and argmax metrics use identical private targets")
        need(report["log_loss_floor"] == EPSILON, "One frozen log-loss floor")
    ordered = sorted(reports)
    undefined = [person for person in ordered if not reports[person]["defined"]]
    def average(field):
        return None if undefined else math.fsum(reports[p][field] for p in ordered) / len(ordered)
    calibration = None if undefined else [
        math.fsum(reports[p]["calibration_in_large_predicted_minus_observed"][k]
                  for p in ordered) / len(ordered) for k in range(5)]
    return {
        "schema": "sleep_probability_diagnostics_panel_v1",
        "people": {str(p): copy.deepcopy(reports[p]) for p in ordered},
        "required_people": len(ordered),
        "undefined_people": list(undefined),
        "person_macro_brier": average("mean_multiclass_brier"),
        "person_macro_clipped_log_loss_nats": average("mean_clipped_log_loss_nats"),
        "person_macro_calibration_in_large_predicted_minus_observed": calibration,
        "aggregation": "eligible epochs pooled within person; equal people",
        "log_loss_floor": EPSILON,
        "interval": None,
        "p_value": None,
        "interpretation": "Prediction quality and marginal calibration diagnostics; no full calibration or inference guarantee",
    }
