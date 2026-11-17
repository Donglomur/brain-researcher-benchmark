"""Full-cohort behavior component; source only, no authentic evaluation yet.

Figure means follow the released generateFigure2.py conditions and abs(metric).
The helper's signed paired formulas and global trial-label shuffle algorithm are
applied to those declared figure predicates and reported separately; this does
not execute the helper's different pro/anti-filtered all5/clubbed pipeline.
Participant sign flips and bootstrap are explicit benchmark
analyses, not a claim to recover the publication's unknown random seed/results.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import math
import random
from collections import Counter
from pathlib import Path

ROSTER = (1, 3, 5, 6, 7, 10, 12, 14, 15, 17, 22, 23, 25, 26, 27)
CONDITIONS = ("No TMS", "mid inPF", "mid outPF", "early inPF",
              "early outPF", "midrep inPF", "midrep outPF")
METRICS = ("ierr", "isacc_rt", "isacc_peakvel")
CONTRASTS = {
    "exp1_in_minus_no": ("mid inPF", "No TMS"),
    "exp1_in_minus_out": ("mid inPF", "mid outPF"),
    "exp1_out_minus_no": ("mid outPF", "No TMS"),
    "exp2_middle_in_minus_out": ("midrep inPF", "midrep outPF"),
    "exp2_early_in_minus_out": ("early inPF", "early outPF"),
    "exp2_early_in_minus_middle_in": ("early inPF", "midrep inPF"),
}
RELEASE_BYTES = 4926544
RELEASE_SHA256 = "b677bede5c7c8c2806e2796ed58c783b07d2a73687d662b97ceb078916ade80a"
MISSING = frozenset(("", "nan", "na", "null", "none"))


class InvalidInput(ValueError):
    pass


def integer(text: str, name: str) -> int:
    try:
        value = float(text)
    except (TypeError, ValueError) as exc:
        raise InvalidInput(name + " must be an integer") from exc
    if not math.isfinite(value) or value != int(value):
        raise InvalidInput(name + " must be an integer")
    return int(value)


def number(text: str, name: str) -> float | None:
    if text is None:
        raise InvalidInput("ragged CSV row")
    if text.strip().lower() in MISSING:
        return None
    try:
        value = float(text)
    except ValueError as exc:
        raise InvalidInput(name + " must be numeric or an explicit missing value") from exc
    if not math.isfinite(value):
        raise InvalidInput(name + " contains infinity")
    return value


def condition(day: int, label: str) -> str | None:
    if day not in (1, 2, 3, 4, 5):
        raise InvalidInput("unexpected study day")
    if label not in ("No TMS", "TMS intoVF", "TMS outVF"):
        raise InvalidInput("unknown TMS_condition")
    if day <= 3:
        return {"No TMS": "No TMS", "TMS intoVF": "mid inPF",
                "TMS outVF": "mid outPF"}[label]
    if label == "No TMS":
        return None  # Explicitly excluded by the released figure's seven predicates.
    return ("early" if day == 4 else "midrep") + (
        " inPF" if label == "TMS intoVF" else " outPF")


def parse_release(data: bytes, *, authenticate: bool = True) -> tuple[list[dict], dict]:
    if authenticate and (len(data) != RELEASE_BYTES or hashlib.sha256(data).hexdigest() != RELEASE_SHA256):
        raise InvalidInput("wrong released behavioral CSV identity")
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    except UnicodeDecodeError as exc:
        raise InvalidInput("behavior CSV must be UTF-8") from exc
    fields = reader.fieldnames
    required = {"subjID", "day", "TMS_condition", *METRICS}
    if fields is None or len(fields) != len(set(fields)) or not required.issubset(fields):
        raise InvalidInput("missing or duplicate release columns")
    rows, excluded, flags = [], Counter(), Counter()
    subjects = set()
    for ordinal, raw in enumerate(reader, 1):
        if None in raw or any(value is None for value in raw.values()):
            raise InvalidInput("ragged CSV row")
        person = integer(raw["subjID"], "subjID")
        if person not in ROSTER:
            raise InvalidInput("subject outside the full registered cohort")
        subjects.add(person)
        day = integer(raw["day"], "day")
        group = condition(day, raw["TMS_condition"].strip())
        if "ispro" in raw:
            flags["ispro=" + raw["ispro"]] += 1
        values = {name: number(raw[name], name) for name in METRICS}
        if group is None:
            excluded["No TMS on day 4 or 5"] += 1
        rows.append({"release_row": ordinal, "person": person, "day": day,
                     "condition": group, "values": values})
    if subjects != set(ROSTER):
        raise InvalidInput("the complete fifteen-person release is required")
    return rows, {"rows": len(rows), "columns": fields,
                  "excluded_by_figure_condition": dict(excluded),
                  "observed_ispro_labels": dict(flags),
                  "source_sha256": hashlib.sha256(data).hexdigest(),
                  "source_bytes": len(data),
                  "preprocessing_assumption": "Released derivative; no additional trial exclusion applied.",
                  "row_identity": "CSV row ordinal, not independently verified physical trial ID."}


def mean(values: list[float]) -> float:
    if not values or any(not math.isfinite(v) for v in values):
        raise InvalidInput("empty or nonfinite statistical group")
    return math.fsum(values) / len(values)


def describe(values: list[float]) -> dict:
    center, n = mean(values), len(values)
    variance = math.fsum((x - center) ** 2 for x in values) / (n - 1) if n > 1 else None
    sd = math.sqrt(variance) if variance is not None else None
    return {"n": n, "mean": center, "sample_sd": sd,
            "standard_error": sd / math.sqrt(n) if sd is not None else None}


def paired_summary(differences: list[float]) -> dict:
    if len(differences) < 2:
        raise InvalidInput("at least two paired people are required")
    result = describe(differences)
    sem, sd, mu = result["standard_error"], result["sample_sd"], result["mean"]
    result.update({"df": len(differences) - 1,
                   "t": mu / sem if sem else None,
                   "cohens_dz": mu / sd if sd else None,
                   "degenerate": None if sd else ("all_zero" if mu == 0 else "constant_nonzero")})
    return result


def exact_sign_flip(differences: list[float]) -> dict:
    """All2^n person-level signs; exact enumeration conditional on sign exchangeability.

    For fixed squared norm, |paired t| is monotone in |sum(d)|. Comparing sums
    avoids infinite t statistics for constant nonzero data. A documented floating
    tie allowance is used, rather than claiming exact rational arithmetic.
    """
    if not 2 <= len(differences) <= 15:
        raise InvalidInput("sign-flip cohort must contain 2..15 paired people")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in differences):
        raise InvalidInput("sign-flip inputs must be finite numeric paired differences")
    observed = abs(math.fsum(differences))
    # ULP-scale rounding allowance follows the actual units; no fixed unit floor.
    tol = 32 * math.ulp(math.fsum(abs(x) for x in differences))
    extreme = 0
    for signs in itertools.product((-1, 1), repeat=len(differences)):
        statistic = abs(math.fsum(s * x for s, x in zip(signs, differences)))
        extreme += statistic >= observed - tol
    total = 1 << len(differences)
    return {"p_two_sided": extreme / total, "extreme": extreme,
            "enumerated": total, "tie_tolerance": tol,
            "unit": "participant", "assumption": "joint sign exchangeability of paired differences"}


def quantile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def bootstrap_interval(differences: list[float], *, seed: int, draws: int = 2000) -> dict:
    if type(draws) is not int or draws < 2:
        raise InvalidInput("at least two bootstrap draws required")
    rng, n = random.Random(seed), len(differences)
    estimates = [mean([differences[rng.randrange(n)] for _ in range(n)]) for _ in range(draws)]
    return {"lower": quantile(estimates, 0.025), "upper": quantile(estimates, 0.975),
            "confidence": 0.95, "draws": draws, "seed": seed,
            "method": "participant-paired percentile bootstrap; type7 quantiles"}


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    ordered = sorted(pvalues, key=lambda key: (pvalues[key], key))
    output, previous, count = {}, 0.0, len(ordered)
    for rank, key in enumerate(ordered):
        previous = max(previous, min(1.0, (count - rank) * pvalues[key]))
        output[key] = previous
    return output


def literal_global_trial_shuffle(rows: list[dict], metric: str, a: str, b: str,
                                 *, draws: int, seed: int) -> dict:
    """Author global-label algorithm applied to figure predicates; not exact pipeline execution.

    Raw signed metric, across-person shuffling, and the author's asymmetric
    comparison operators are preserved. Python's RNG is explicitly different
    from the author's unseeded NumPy RNG: this is algorithm-level reproduction.
    """
    if type(draws) is not int or not 1 <= draws <= 10000:
        raise InvalidInput("literal diagnostic draws must be1..10000")
    population = [r for r in rows if r["condition"] in (a, b)]
    labels = [r["condition"] for r in population]
    def statistic(current_labels):
        grouped = {(person, group): [] for person in ROSTER for group in (a, b)}
        for row, group in zip(population, current_labels):
            if row["values"][metric] is not None:
                grouped[row["person"], group].append(row["values"][metric])
        if any(not values for values in grouped.values()):
            raise InvalidInput("global shuffle removes a participant-condition cell")
        differences = [mean(grouped[person, a]) - mean(grouped[person, b]) for person in ROSTER]
        value = paired_summary(differences)["t"]
        if value is None:
            raise InvalidInput("undefined literal t statistic")
        return value
    observed, rng, both, greater = statistic(labels), random.Random(seed), 0, 0
    for _ in range(draws):
        current = labels.copy(); rng.shuffle(current)
        value = statistic(current)
        both += value >= abs(observed) or value < -abs(observed)
        greater += value >= observed
    return {"observed_signed_t": observed, "p_source_two_sided": both / draws,
            "p_source_greater": greater / draws, "draws": draws, "seed": seed,
            "rng": "Python Random, not recovered historical NumPy state",
            "warning": "Global trial labels cross participants/sessions; diagnostic only. No plus-one correction, matching source. Figure predicates differ from the author's pro/anti-filtered all5/clubbed pipeline."}


def build_reference(rows: list[dict], *, seed: int = 20261114, bootstrap_draws: int = 2000,
                    literal_draws: int = 0) -> dict:
    result = {"schema": "tms-full-behavior-component-v1", "roster": list(ROSTER),
              "helper_reproduction_scope": "Signed mean/t/dz formulas on released figure predicates; not full author helper pipeline execution.",
              "metrics": {}, "complete_task_qualified": False}
    for metric in METRICS:
        groups = {(person, group): [] for person in ROSTER for group in CONDITIONS}
        missing = Counter()
        for row in rows:
            group = row["condition"]
            if group is None:
                continue
            value = row["values"][metric]
            if value is None:
                missing[row["person"], group] += 1
            else:
                groups[row["person"], group].append(value)
        if any(not values for values in groups.values()):
            raise InvalidInput("all fifteen people must have every figure condition for " + metric)
        cells = [{"person": person, "condition": group,
                  "valid_trials": len(groups[person, group]),
                  "missing_trials": missing[person, group],
                  "figure_mean_abs": mean([abs(v) for v in groups[person, group]]),
                  "source_helper_mean_signed": mean(groups[person, group])}
                 for person in ROSTER for group in CONDITIONS]
        lookup = {(x["person"], x["condition"]): x for x in cells}
        contrasts = {}
        for name, (a, b) in CONTRASTS.items():
            diffs = [lookup[p, a]["figure_mean_abs"] - lookup[p, b]["figure_mean_abs"] for p in ROSTER]
            signed = [lookup[p, a]["source_helper_mean_signed"] - lookup[p, b]["source_helper_mean_signed"] for p in ROSTER]
            contrast = {"a": a, "b": b, "figure_paired": paired_summary(diffs),
                        "source_helper_signed_paired": paired_summary(signed),
                        "corrected_participant_sign_flip": exact_sign_flip(diffs),
                        "corrected_participant_bootstrap": bootstrap_interval(diffs, seed=seed, draws=bootstrap_draws),
                        "leave_one_person_out": [{"excluded_person": p, "summary": paired_summary(diffs[:i] + diffs[i+1:])}
                                                 for i, p in enumerate(ROSTER)]}
            if literal_draws:
                contrast["literal_global_trial_shuffle_diagnostic"] = literal_global_trial_shuffle(
                    rows, metric, a, b, draws=literal_draws, seed=seed)
            contrasts[name] = contrast
        adjusted = holm({name: item["corrected_participant_sign_flip"]["p_two_sided"] for name, item in contrasts.items()})
        for name, value in adjusted.items():
            contrasts[name]["corrected_sign_flip_holm_six_contrasts"] = value
        result["metrics"][metric] = {"participant_cells": cells, "contrasts": contrasts}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--literal-draws", type=int, default=0)
    args = parser.parse_args()
    # Scientific intake/operation must be separately selected; this CLI never downloads.
    with args.csv.open("rb") as stream:
        data = stream.read(RELEASE_BYTES + 1)
    rows, intake = parse_release(data)
    result = build_reference(rows, literal_draws=args.literal_draws)
    result["intake"] = intake
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
