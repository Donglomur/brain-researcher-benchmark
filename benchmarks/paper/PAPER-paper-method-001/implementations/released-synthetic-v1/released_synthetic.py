"""Released examples/synthetic.py recipe, with explicit cases and failure custody.

This is calibration of that released example, not final Figure 1 qualification.
No arrays, estimator calls, file writes or scientific runs occur during import.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

REVISION = "f18de35818502744329f7c92bb17a80af8f48549"
RECIPE = "released_synthetic_example_f18de358_v1"
SIZES = (10, 20, 30, 50, 75, 100, 150, 200, 300, 500)
ESTIMATORS = ("naive", "row", "col", "both")
SEEDS = tuple(range(20))


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def cases():
    """All 400 source slots; the two occurrences of (P=200,Q=100) stay distinct."""
    return [{"case_id": f"{axis}/{ordinal:02d}/{seed:02d}", "axis": axis,
             "ordinal": ordinal, "P": size if axis == "P" else 200,
             "Q": size if axis == "Q" else 100, "seed": seed}
            for axis in ("P", "Q") for ordinal, size in enumerate(SIZES)
            for seed in SEEDS]


def _case(case):
    _need(type(case) is dict, "source case must be a mapping")
    roster = {row["case_id"]: row for row in cases()}
    _need(type(case.get("case_id")) is str and case["case_id"] in roster,
          "unknown source case")
    # JSON comparison is type-sensitive, including bool versus int substitutions.
    _need(json.dumps(case, sort_keys=True, allow_nan=False) ==
          json.dumps(roster[case["case_id"]], sort_keys=True, allow_nan=False),
          "source case dimensions, identity or seed changed")
    return roster[case["case_id"]]


def observation(case):
    """One original noisy matrix, not a fabricated two-repeat observation.

    Resets default_rng(seed) for every point exactly as the source sweep does.
    All four author estimators consume this same matrix without pre-centering.
    """
    import numpy as np
    row = _case(case)
    rng = np.random.default_rng(row["seed"])
    X = rng.standard_normal((row["P"], 50))
    W = rng.standard_normal((50, row["Q"]))
    phi = X @ W / 50
    return phi + rng.standard_normal((row["P"], row["Q"])) * np.sqrt(0.2)


def _encode(value):
    value = float(value)
    return {"value": value if math.isfinite(value) else None,
            "nonfinite": None if math.isfinite(value) else str(value)}


def _decode(value):
    _need(type(value) is dict and set(value) == {"value", "nonfinite"},
          "closed scalar encoding required")
    scalar, kind = value["value"], value["nonfinite"]
    if scalar is None:
        _need(kind in ("nan", "inf", "-inf"), "missing nonfinite kind")
        return float(kind)
    _need(type(scalar) in (int, float) and math.isfinite(scalar) and kind is None,
          "finite scalar must have no nonfinite kind")
    return float(scalar)


def _source_pins():
    return json.loads((Path(__file__).parent / "SOURCE.json").read_text())["estimator_dependencies"]


def _author_estimator():
    """Load the unchanged, already published author implementation by exact hash."""
    directory = Path(__file__).parent.parent / "dimensionality-programme" / "programme" / "scientific-runtime" / "finite_science" / "literal_author"
    pins = _source_pins()
    for name, digest in pins.items():
        _need(hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest,
              "published author dependency changed: " + name)
    # A separate namespace prevents accidentally resolving an installed package.
    namespace = "_released_synthetic_author_f18de358"
    if namespace not in sys.modules:
        spec = importlib.util.spec_from_file_location(namespace, directory / "__init__.py",
                                                     submodule_search_locations=[str(directory)])
        package = importlib.util.module_from_spec(spec)
        sys.modules[namespace] = package
        spec.loader.exec_module(package)
    name = namespace + ".estimators"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, directory / "estimators.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            del sys.modules[name]
            raise
    return sys.modules[name].participation_ratio


def author_case(case):
    """Explicit calibration operation; operator resource approval remains external.

    Dependency/acquisition failures propagate; they cannot become estimator loss.
    Arithmetic failures are retained as failed draws, without zero imputation.
    """
    import numpy as np
    import opt_einsum
    row = _case(case)
    estimator = _author_estimator()
    phi = observation(row)
    record = {"case": row, "recipe": RECIPE,
              "environment": {"numpy": np.__version__, "opt_einsum": opt_einsum.__version__}}
    try:
        with np.errstate(all="ignore"):
            values = estimator(phi, return_all=True)
        _need(set(values) == set(ESTIMATORS), "author estimator output changed")
        record.update(status="returned", values={key: _encode(values[key]) for key in ESTIMATORS},
                      error_kind=None)
    except (ArithmeticError, FloatingPointError) as error:
        record.update(status="arithmetic_failure", values=None, error_kind=type(error).__name__)
    return record


def summarize(records):
    """The source's per-point ordinary mean and ddof=1 SEM, with no omitted slots.

    NaN/Inf are encoded exactly; failure counts survive independently of means.
    No MSE, new loss, aggregate panel score, interval or paper win is invented.
    """
    import numpy as np
    _need(type(records) is list and len(records) == 400, "all 400 source slots required")
    by_id, environments = {}, set()
    for record in records:
        _need(type(record) is dict and set(record) ==
              {"case", "recipe", "environment", "status", "values", "error_kind"},
              "closed draw record required")
        row = _case(record["case"])
        _need(row["case_id"] not in by_id and record["recipe"] == RECIPE,
              "duplicate draw or changed recipe")
        env = record["environment"]
        _need(type(env) is dict and set(env) == {"numpy", "opt_einsum"} and
              all(type(v) is str and v for v in env.values()), "exact dependency versions required")
        environments.add(tuple(sorted(env.items())))
        if record["status"] == "returned":
            _need(type(record["values"]) is dict and set(record["values"]) == set(ESTIMATORS)
                  and record["error_kind"] is None, "four source estimates required")
            for value in record["values"].values():
                _decode(value)
        else:
            _need(record["status"] == "arithmetic_failure" and record["values"] is None and
                  record["error_kind"] in ("ArithmeticError", "FloatingPointError", "OverflowError", "ZeroDivisionError"),
                  "invalid arithmetic failure")
        by_id[row["case_id"]] = record
    _need(set(by_id) == {row["case_id"] for row in cases()}, "incomplete source roster")
    _need(len(environments) == 1, "mixed numerical dependency versions")
    panels = []
    for axis in ("P", "Q"):
        for ordinal, size in enumerate(SIZES):
            rows = [by_id[f"{axis}/{ordinal:02d}/{seed:02d}"] for seed in SEEDS]
            failures = [row["case"]["seed"] for row in rows if row["status"] != "returned"]
            estimates = {}
            for key in ESTIMATORS:
                values = [_decode(row["values"][key]) for row in rows if row["status"] == "returned"]
                counts = {"finite": sum(math.isfinite(v) for v in values),
                          "nan": sum(math.isnan(v) for v in values),
                          "positive_infinity": sum(v == math.inf for v in values),
                          "negative_infinity": sum(v == -math.inf for v in values),
                          "nonpositive_finite": sum(math.isfinite(v) and v <= 0 for v in values)}
                # No surviving-draw mean: a thrown estimator has no source curve.
                if failures:
                    estimates[key] = {"mean": None, "sem": None, "counts": counts}
                else:
                    with np.errstate(all="ignore"):
                        array = np.asarray(values, dtype=float)
                        estimates[key] = {"mean": _encode(np.mean(array)),
                                          "sem": _encode(np.std(array, ddof=1) / np.sqrt(20)),
                                          "counts": counts}
            panels.append({"axis": axis, "ordinal": ordinal, "P": size if axis == "P" else 200,
                           "Q": size if axis == "Q" else 100, "planned_draws": 20,
                           "failed_seeds": failures, "estimates": estimates})
    return {"recipe": RECIPE, "environment": dict(next(iter(environments))),
            "aggregation_numpy_version": np.__version__,
            "planned_draw_slots": 400, "retained_draw_slots": len(records),
            "planned_estimates": 1600, "unique_dimension_seed_tuples": 380,
            "panels": panels,
            "scope": "released example calibration; final-paper correspondence unresolved",
            "uncertainty_scope": "source SEM within each point; seeds reused across points; no pooled interval"}
