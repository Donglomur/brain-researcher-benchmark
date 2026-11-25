"""Full-panel Figure 3 output scorer. No fitting, unpickling, or data generation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import Invalid, number, require

TASK = "paper-pcca-fa-bilateral-pfc-arousal-2026"
GRID = (100, 150, 300, 600, 1000, 1500)
KEYS = tuple((n, i) for i in range(30) for n in GRID)
COMPONENTS = ("across_1", "across_2", "within_1", "within_2")
METRICS = ("psv_percent", "dshared")
CONDITIONS = ("paper_data", "paper_data_author_code")
CAP = 2 * 1024 * 1024


def fields(obj, names):
    require(type(obj) is dict and set(obj) == set(names), "unexpected or missing fields")


def digest(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "SHA256 required")


def decode(raw):
    require(type(raw) is bytes and len(raw) <= CAP, "JSON byte limit")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid("nonfinite JSON")))
    except Invalid:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Invalid("malformed JSON") from exc


def read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= CAP, "regular bounded file required")
        raw = handle.read(CAP + 1)
    require(len(raw) <= CAP, "JSON byte limit")
    return raw


def endpoint(obj, *, control=False):
    components = COMPONENTS[:2] if control else COMPONENTS
    fields(obj, components)
    result = {}
    for component in components:
        fields(obj[component], METRICS)
        sv = number(obj[component]["psv_percent"])
        dim = obj[component]["dshared"]
        require(0 <= sv <= 100, "%sv range")
        require(type(dim) is int and 0 <= dim <= 30, "d_shared integer range")
        require((dim == 0) == (sv == 0), "zero dimension and zero shared variance must agree")
        result[component] = {"psv_percent": sv, "dshared": dim}
    if not control:
        for area in (1, 2):
            require(result[f"across_{area}"]["psv_percent"] + result[f"within_{area}"]["psv_percent"] <= 100 + 1e-10, "variance components exceed 100 percent")
    return result


def identity(row, expected):
    n, i = expected
    require(type(row["trials"]) is int and type(row["draw"]) is int, "integer identity required")
    require((row["trials"], row["draw"]) == (n, i), "complete source draw-major panel/order required")
    digest(row["observations_sha256"])


def support(raw):
    obj = decode(raw)
    fields(obj, ("schema", "task", "preparation_sha256", "protocol_sha256", "rows"))
    require(obj["schema"] == "pcca-fig3-support-v1" and obj["task"] == TASK, "support schema/task")
    digest(obj["preparation_sha256"])
    digest(obj["protocol_sha256"])
    require(type(obj["rows"]) is list and len(obj["rows"]) == 180, "all 180 simulation datasets required")
    hashes = set()
    for row, key in zip(obj["rows"], KEYS):
        fields(row, ("trials", "draw", "observations_sha256", "truth", "author", "pcca"))
        identity(row, key)
        require(row["observations_sha256"] not in hashes, "duplicated observation binding")
        hashes.add(row["observations_sha256"])
        row["truth"] = endpoint(row["truth"])
        row["author"] = endpoint(row["author"])
        row["pcca"] = endpoint(row["pcca"], control=True)
    return obj


def submission(raw, prepared, binding):
    obj = decode(raw)
    fields(obj, ("schema", "task", "support_sha256", "condition", "rows"))
    require(obj["schema"] == "pcca-fig3-submission-v1" and obj["task"] == TASK, "submission schema/task")
    require(obj["support_sha256"] == binding, "support byte binding mismatch")
    require(obj["condition"] in CONDITIONS, "paper/code access condition required")
    require(type(obj["rows"]) is list and len(obj["rows"]) == 180, "all 180 simulation datasets required")
    for row, truth, key in zip(obj["rows"], prepared["rows"], KEYS):
        fields(row, ("trials", "draw", "observations_sha256", "estimates"))
        identity(row, key)
        require(row["observations_sha256"] == truth["observations_sha256"], "paired observation binding mismatch")
        row["estimates"] = endpoint(row["estimates"])
    return obj


def moments(values):
    avg = math.fsum(values) / len(values)
    residuals = [x - avg for x in values]
    variance = math.fsum(x ** 2 for x in residuals) / len(values)
    deviation = math.sqrt(variance)
    if variance < sys.float_info.min and any(residuals):
        # A finite population SD can be representable when its squared
        # intermediate is not. Retain the same centered population statistic.
        deviation = math.hypot(*residuals) / math.sqrt(len(values))
    return {"mean": avg, "std_population": deviation, "n_area_values": len(values)}


def compare(support_raw, candidate_raw):
    prepared = support(support_raw)
    binding = hashlib.sha256(support_raw).hexdigest()
    candidate = submission(candidate_raw, prepared, binding)
    draws = []
    for source, estimate in zip(prepared["rows"], candidate["rows"]):
        row = {"trials": source["trials"], "draw": source["draw"], "signed_errors": {}, "candidate_minus_author": {}}
        for method, values in (("candidate", estimate["estimates"]), ("author", source["author"]), ("pcca", source["pcca"])):
            row["signed_errors"][method] = {c: {m: values[c][m] - source["truth"][c][m] for m in METRICS} for c in values}
        row["candidate_minus_author"] = {c: {m: estimate["estimates"][c][m] - source["author"][c][m] for m in METRICS} for c in COMPONENTS}
        draws.append(row)
    curves, reproduction, improvement = [], [], []
    for n in GRID:
        selected = [r for r in draws if r["trials"] == n]
        for component in ("across", "within"):
            areas = (component + "_1", component + "_2")
            for metric in METRICS:
                key = {"trials": n, "component": component, "metric": metric, "independent_datasets": 30}
                methods = ("candidate", "author", "pcca") if component == "across" else ("candidate", "author")
                curves.append({**key, "signed_error": {method: moments([r["signed_errors"][method][a][metric] for a in areas for r in selected]) for method in methods}})
                reproduction.append({**key, "candidate_minus_author": moments([r["candidate_minus_author"][a][metric] for a in areas for r in selected])})
                # Dataset remains the unit for these paired diagnostic values.
                # These losses are explicit benchmark diagnostics, not the paper's curve.
                paired = [math.fsum(abs(r["signed_errors"]["candidate"][a][metric]) - abs(r["signed_errors"]["author"][a][metric]) for a in areas) / 2 for r in selected]
                improvement.append({**key, "mean_paired_absolute_error_difference": math.fsum(paired) / 30, "paired_differences_by_draw": paired})
    return {
        "schema": "pcca-fig3-report-v1", "task": TASK, "support_sha256": binding,
        "condition": candidate["condition"], "source_curves": curves,
        "reproduction_discrepancies": reproduction,
        "improvement_diagnostics": improvement, "per_draw": draws,
        "qualification": "software output component; authentic preparation and author fitting unqualified",
        "reproduction_pass": None, "improvement_pass": None,
        "interpretation": "Source curves use signed estimation error and population SD across 60 area values per trial condition. There are 30 independent datasets. Absolute-error diagnostics are benchmark-owned, with no admitted margin or uncertainty decision. pCCA has only across-area source controls.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("support", help="operator-owned complete endpoint support")
    parser.add_argument("candidate", help="complete submission JSON")
    args = parser.parse_args()
    try:
        report = compare(read(args.support), read(args.candidate))
    except (Invalid, OSError) as exc:
        parser.exit(2, f"refused: {exc}\n")
    json.dump(report, sys.stdout, allow_nan=False, separators=(",", ":"))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
