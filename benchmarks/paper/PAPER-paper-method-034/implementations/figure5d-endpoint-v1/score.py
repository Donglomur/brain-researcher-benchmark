"""Operator-side MARBLE Figure 5d endpoint, without representation fitting.

Fits only the published 36-neighbor cosine position decoder. Upstream embedding
training and original row provenance are separate, unresolved qualifications.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

TASK_ID = "PAPER-paper-method-034"
QUERY_COUNT = 2000
DIMENSION = 32
NEIGHBORS = 36


def require(value, message):
    if not value:
        raise ValueError(message)


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def digest(value):
    require(type(value) is str and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), "invalid SHA256")


def row_ids(value, count=None):
    require(type(value) is list and all(type(x) is str and x and
            len(x) <= 256 and "\n" not in x and "\r" not in x for x in value),
            "row identities must be bounded nonempty strings")
    require(len(set(value)) == len(value), "duplicate row identity")
    require(count is None or len(value) == count, "wrong number of rows")
    return value


def support_check(support):
    require(set(support) == {"schema", "task_id", "panel", "animal", "unit",
            "source_sha256", "training_row_ids", "query_row_ids"},
            "unexpected support fields")
    require(support["schema"] == "marble_figure5d_support_v1" and
            support["task_id"] == TASK_ID and support["panel"] == "Figure 5d" and
            support["animal"] == "rat1" and support["unit"] == "m",
            "Figure 5d rat1 support in metres is required")
    digest(support["source_sha256"])
    train = row_ids(support["training_row_ids"])
    query = row_ids(support["query_row_ids"], QUERY_COUNT)
    require(NEIGHBORS <= len(train) <= 10000, "invalid decoder fit support")
    require(set(train).isdisjoint(query), "training/query support overlaps")
    return train, query


def numbers(values, count, name, columns=None):
    import numpy as np
    require(type(values) is list and len(values) == count, name + " row count")
    flat = values
    if columns is not None:
        require(all(type(row) is list and len(row) == columns for row in values),
                name + " requires exactly 32 columns")
        flat = [v for row in values for v in row]
    require(all(type(v) in (int, float) and math.isfinite(v) for v in flat),
            name + " must contain finite numbers, not booleans")
    array = np.asarray(values, dtype=np.float64)
    require(np.isfinite(array).all(), name + " cannot overflow float64")
    return array


def decode(support, training, query):
    """No query labels enter this function; no row is dropped or reordered."""
    import numpy as np
    from sklearn.neighbors import KNeighborsRegressor
    train_ids, query_ids = support_check(support)
    require(set(training) == {"row_ids", "embedding", "position_m"},
            "unexpected training fields")
    require(set(query) == {"row_ids", "embedding"},
            "query input may contain only row IDs and embeddings")
    require(training["row_ids"] == train_ids and query["row_ids"] == query_ids,
            "embedding rows do not match frozen support order")
    train_x = numbers(training["embedding"], len(train_ids), "training", DIMENSION)
    query_x = numbers(query["embedding"], QUERY_COUNT, "query", DIMENSION)
    train_y = numbers(training["position_m"], len(train_ids), "training position")
    # Retains sklearn/CEBRA cosine handling, including zeros and distance ties.
    decoder = KNeighborsRegressor(n_neighbors=NEIGHBORS, metric="cosine", n_jobs=1)
    prediction = decoder.fit(train_x, train_y).predict(query_x)
    require(prediction.shape == (QUERY_COUNT,) and np.isfinite(prediction).all(),
            "nonfinite/invalid decoder output")
    return prediction.tolist()


def finite_mean(values):
    """Preserve finite means when their intermediate binary64 sum overflows."""
    try:
        value = math.fsum(values) / len(values)
    except OverflowError:
        value = float(sum(Fraction.from_float(v) for v in values) / len(values))
    require(math.isfinite(value), "mean outside finite output range")
    return value


def error_summary(support, prediction, targets):
    """Mean is primary; SD denominators are explicit, never a guessed paper SD."""
    _, query_ids = support_check(support)
    require(set(targets) == {"row_ids", "position_m"}, "unexpected target fields")
    require(targets["row_ids"] == query_ids, "target rows do not match frozen order")
    pred = numbers(prediction, QUERY_COUNT, "prediction")
    target = numbers(targets["position_m"], QUERY_COUNT, "query position")
    errors = abs(pred - target)
    require(all(math.isfinite(float(x)) for x in errors), "absolute error overflow")
    # Preserve the ordinary fsum reduction; use exact binary input values only
    # when an intermediate total/square cannot represent the finite statistic.
    values = [float(x) for x in errors]
    mean = finite_mean(values)
    try:
        terms = [(value - mean) ** 2 for value in values]
        squares = math.fsum(terms)
        population = math.sqrt(squares / QUERY_COUNT)
        sample = math.sqrt(squares / (QUERY_COUNT - 1))
        varying = any(value != values[0] for value in values)
        fallback = (not math.isfinite(squares) or
                    (varying and (population == 0.0 or sample == 0.0)))
    except OverflowError:
        fallback = True
    if fallback:
        # Scaling the exact variance avoids both squared underflow and overflow.
        # Center exactly here: a rounded subnormal mean can itself be zero.
        exact = [Fraction.from_float(value) for value in values]
        center = sum(exact) / QUERY_COUNT
        variance = sum((value - center) ** 2 for value in exact) / QUERY_COUNT
        scale = max(values)
        scaled = variance / Fraction.from_float(scale) ** 2 if scale else Fraction(0)
        population = scale * math.sqrt(float(scaled))
        sample = scale * math.sqrt(float(scaled * QUERY_COUNT / (QUERY_COUNT - 1)))
    require(math.isfinite(population) and math.isfinite(sample),
            "error deviation outside finite output range")
    return {"samples": QUERY_COUNT, "mean_absolute_error_m": mean,
            "absolute_error_sd_population_m": population,
            "absolute_error_sd_sample_m": sample}


def _prediction_report(support, prediction, targets):
    """Report already decoded outputs; only this final step consumes targets."""
    return {"schema": "marble_figure5d_endpoint_v1", "task_id": TASK_ID,
            "panel": "Figure 5d", "animal": "rat1", "unit": "m",
            "decoder": {"neighbors": NEIGHBORS, "metric": "cosine",
                        "weights": "uniform", "embedding_dimension": DIMENSION},
            "score": error_summary(support, prediction, targets),
            "qualification": "numerical_endpoint_only_original_support_unqualified",
            "scope": "Within one recording; SD describes errors, not independent animal uncertainty.",
            "historical_source_support_verified": False,
            "author_baseline_qualified": False,
            "scientific_improvement_awarded": None}


def score(support, training, query, targets):
    # In-process callers already hold targets and must enforce their own custody.
    return _prediction_report(support, decode(support, training, query), targets)


def read_json(path, limit):
    # JSON only: never deserialize checkpoint/pickle data or execute supplied code.
    with Path(path).open("rb") as stream:
        body = stream.read(limit + 1)
    require(0 < len(body) <= limit, "input exceeds JSON byte bound")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    data = json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, "nonfinite JSON"))
    require(type(data) is dict, "JSON object required")
    return data, {"bytes": len(body), "sha256": sha256(body)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("support", "training", "query", "targets"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--support-sha256", required=True,
                        help="Operator-frozen digest; a digest does not attest scientific provenance")
    args = parser.parse_args(argv)
    try:
        digest(args.support_sha256)
        values, pins = {}, {}
        values["support"], pins["support"] = read_json(args.support, 4 << 20)
        require(pins["support"]["sha256"] == args.support_sha256,
                "support digest mismatch")
        support_check(values["support"])
        for name, limit in (("training", 32 << 20), ("query", 16 << 20)):
            values[name], pins[name] = read_json(getattr(args, name), limit)
        # Validate and decode complete admitted public operands before the first
        # protected-target read. Never rerun a decoder after target access.
        prediction = decode(values["support"], values["training"], values["query"])
        values["targets"], pins["targets"] = read_json(args.targets, 1 << 20)
        result = _prediction_report(values["support"], prediction, values["targets"])
        import numpy
        import sklearn
        result["input_pins"] = pins
        result["runtime"] = {"numpy": numpy.__version__, "scikit_learn": sklearn.__version__}
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OverflowError, OSError) as error:
        print(json.dumps({"error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
