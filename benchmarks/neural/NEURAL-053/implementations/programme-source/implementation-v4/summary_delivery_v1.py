"""Typed delivery of the existing THINGS-MEG summaries, without unit conversion.

The author writes baseline z-scores back into an EpochsArray with its original
MEG info. Channel kind alone therefore does not establish the values' units.
This additive exporter preserves V4's numerical representation and all rows.
It does not replace V4's authenticated preparation, fold construction or gates.
"""
from pathlib import Path

from cohort import ARMS, require
from io_support import object_digest
from preparation import EYE_CHANNELS, SENSOR_ORDER_SHA256
from storage import write_array_fresh, write_json_fresh


SOURCE_CONVENTIONS = {
    "revision": "5e0eccac51eac78b57045f5b90b4f53814f56c32",
    "meg_source_sha256": "2c20c84a69327750147e7482a032f6a21464a49009cce357b87e26ad4b2361ab",
    "eye_source_sha256": "649a119db0fa36e2e50bdeb202e00d4482b4164a8ac1ee5e312a5cdafb6242c9",
    "meaning": "Source-code units; authentic derivative/header compatibility remains unqualified",
}


def _sensors(names):
    require(type(names) in (list, tuple) and len(names) == 271 and
            all(type(x) is str and x for x in names) and len(set(names)) == 271,
            "271 unique ordered processed sensor names")


def feature_columns(sensor_names, arm):
    """Column semantics follow the exact V4 mean-then-fraction concatenation.

    Names must come from the operator's admitted sensor order. This pure schema
    primitive also supports invented sensor names in software controls.
    """
    _sensors(sensor_names)
    require(arm in ARMS, "One of the four registered feature arms")

    def means(names, units, quantity):
        return [{"channel": name, "statistic": "finite_sample_mean", "unit": unit,
                 "quantity": q} for name, unit, q in zip(names, units, quantity)]

    def fractions(names, samples):
        return [{"channel": name, "statistic": "finite_sample_fraction",
                 "unit": "1", "quantity": "availability", "denominator": samples}
                for name in names]

    neural = means(sensor_names, ["1"] * 271, ["author_baseline_zscore"] * 271)
    for column in neural:
        column["normalization"] = "per_epoch_sensor_baseline_standard_deviation"
    neural += fractions(sensor_names, 40)
    ocular = means(EYE_CHANNELS, ["degree", "degree", "V"],
                   ["detrended_horizontal_gaze", "detrended_vertical_gaze",
                    "detrended_pupil_analog_signal"]) + fractions(EYE_CHANNELS, 240)
    columns = {"neural": neural, "ocular": ocular, "joint": neural + ocular,
               "neural_availability": neural[271:]}[arm]
    return [{"index": i, **column} for i, column in enumerate(columns)]


def _validate_view(matrix, width, samples):
    import numpy as np
    require(isinstance(matrix, np.ndarray) and matrix.ndim == 2 and
            matrix.shape[1] == width * 2 and matrix.shape[0] > 0 and
            matrix.dtype == np.dtype("float32"), "Unconverted prepared float32 summary rows")
    # Validate the exact float32 encodings that V4's count/denominator produces.
    # Tolerance would silently admit fractions with no possible sample count.
    lattice = (np.arange(samples + 1, dtype=np.float64) / samples).astype(np.float32)
    for start in range(0, len(matrix), 128):
        block = matrix[start:start + 128]
        require(np.isfinite(block).all(), "Finite means and finite fractions")
        mean, fraction = block[:, :width], block[:, width:]
        require(((fraction >= 0) & (fraction <= 1)).all(), "Finite fraction in [0,1]")
        count = np.rint(fraction.astype(np.float64) * samples).astype(np.int64)
        require(np.array_equal(fraction, lattice[count]), "Fraction has exact original sample support")
        require((mean[fraction == 0] == 0).all(), "No-observation mean uses V4's zero sentinel")


def project_summary_rows(features, arm):
    """Return the registered arm on matched rows, with no scaling or row removal.

    This accepts an already selected training or query batch. It does not select
    rows, fit transforms, infer source identity, or expose the other arm in its
    result. Original source and fold authentication remain with the operator.
    """
    import numpy as np
    require(type(features) is dict and set(features) == {"neural", "ocular"},
            "Exactly the two prepared base views")
    require(arm in ARMS, "One of the four registered feature arms")
    _validate_view(features["neural"], 271, 40)
    _validate_view(features["ocular"], 3, 240)
    require(len(features["neural"]) == len(features["ocular"]), "Matched base-view rows")
    if arm == "joint":
        values = np.concatenate((features["neural"], features["ocular"]), axis=1)
    elif arm == "neural_availability":
        values = features["neural"][:, 271:]
    else:
        values = features[arm]
    # A delivery is an independent snapshot: changing a caller's array after
    # export cannot change the returned values or the other feature arm.
    return np.array(values, dtype=np.float32, order="C", copy=True)


def write_typed_summary(output_root, features, arm, sensor_names, row_ids, budget):
    """Write an array plus a participant-readable column/row descriptor.

    This operator-side additive export accepts only the frozen sensor order and
    opaque IDs from existing V4 packet construction. The directory must be
    fresh. It returns artifact pins for the parent's normal custody checks.
    It is not enrolled in the V4 production source closure automatically.
    """
    _sensors(sensor_names)
    require(object_digest(list(sensor_names)) == SENSOR_ORDER_SHA256,
            "Frozen actual processed sensor order")
    require(type(row_ids) in (list, tuple) and len(row_ids) > 0 and
            all(type(x) is str and len(x) == 32 and
                all(c in "0123456789abcdef" for c in x) for x in row_ids) and
            len(set(row_ids)) == len(row_ids), "Unique opaque V4 row identities")
    values = project_summary_rows(features, arm)
    require(len(row_ids) == len(values), "Exact ordered row identity extent")
    columns = feature_columns(sensor_names, arm)
    require(len(columns) == values.shape[1] == ARMS[arm], "Typed feature axis equals numeric axis")
    root = Path(output_root)
    require(not root.exists(), "Fresh typed summary delivery")
    root.mkdir(parents=False)
    value_pin = write_array_fresh(root / "features.npy", values, budget)
    document = {
        "schema": "neural053_typed_summary_v1", "arm": arm,
        "rows": list(row_ids), "columns": columns,
        "values": {"path": "features.npy", "bytes": value_pin["bytes"],
                   "sha256": value_pin["sha256"], "shape": list(values.shape), "dtype": "float32"},
        "window": {"start_ms": 100, "stop_ms_exclusive": 300,
                   "meg_samples": 40, "ocular_samples": 240},
        "missing_mean": {"value": 0, "interpretation": "missing only when paired fraction is zero"},
        "unit_provenance": dict(SOURCE_CONVENTIONS),
        "interpretation": "Retrospective author-processed summaries; no causal latency claim",
    }
    descriptor_pin = write_json_fresh(root / "features.json", document, budget)
    return {"features": value_pin, "descriptor": descriptor_pin}
