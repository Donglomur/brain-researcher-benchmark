"""Prospective optical-only MAD peak producer on the complete native frame grid.

All scale and threshold choices are supplied in a frozen training-calibration
record. This component neither fits calibration nor authenticates its origin.
It never opens electrical references, infers a clock, or scores predictions.
"""
import argparse
from bisect import bisect_right
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import types

VIEWER_SHA256 = "7afa39be4aeecdf117cb42e165f43f007330e812b58fa0c9789d38ea41857c41"
_viewer_path = Path(__file__).resolve().parent.parent / "voltron-optical-viewer-v1/viewer.py"
_viewer_body = _viewer_path.read_bytes()
if hashlib.sha256(_viewer_body).hexdigest() != VIEWER_SHA256:
    raise ImportError("prepared-optical dependency changed; review before adoption")
V = types.ModuleType("voltron_mad_prepared_optical_dependency")
V.__file__ = str(_viewer_path)
exec(compile(_viewer_body, str(_viewer_path), "exec"), V.__dict__)
del _viewer_body
S = V.S
TASK = S.TASK
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
PROGRAM_SHA256 = V.identity({"detector_sha256": SOURCE_SHA256,
                            "viewer_sha256": VIEWER_SHA256,
                            "scorer_sha256": V.SCORER_SHA256})


class CalibrationError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise CalibrationError(message)


def fields(value, names):
    need(type(value) is dict and set(value) == set(names), "exact calibration fields required")


def calibration_contract(value, contract, traces):
    """Capture explicit fold calibration without reading training data or labels."""
    fields(value, ("schema", "task_id", "public_sha256", "folds"))
    need(value["schema"] == "voltron-optical-mad-calibration/v1" and
         value["task_id"] == TASK and value["public_sha256"] == contract["identity"],
         "calibration task/public binding")
    cell_folds = {m["cell_id"]: m["fold_id"] for m in contract["movies"].values()}
    folds = set(cell_folds.values())
    need(type(value["folds"]) is dict and set(value["folds"]) == folds,
         "all six held-fold calibrations required")
    captured = {}
    for fold in sorted(folds):
        row = value["folds"][fold]
        fields(row, ("training_cells", "fit_sha256", "amplitude_unit", "indicator_polarity",
                     "center", "mad", "threshold_mads", "refractory_seconds"))
        train = row["training_cells"]
        need(type(train) is list and all(type(c) is str for c in train) and
             len(train) == len(set(train)) and
             set(train) == {c for c, f in cell_folds.items() if f != fold},
             "complete other-fold training-cell roster required")
        S.digest(row["fit_sha256"], CalibrationError)
        unit, polarity = row["amplitude_unit"], row["indicator_polarity"]
        need(type(unit) is str and unit in V.UNITS and
             type(polarity) is int and polarity in (-1, 1), "explicit calibration units/polarity")
        try:
            center, mad, threshold = (V.scalar(row[k]) for k in ("center", "mad", "threshold_mads"))
            refractory = S.exact_time(row["refractory_seconds"], CalibrationError)
        except V.ViewerError as error:
            raise CalibrationError(str(error)) from error
        need(mad > 0, "positive training MAD required; zero scale has no automatic fallback")
        need(threshold > 0 and refractory >= 0, "positive threshold and nonnegative exact refractory time")
        # A pooled training calibration is only applicable when the operator
        # supplies one common representation. This is a declared-unit check,
        # not a biological calibration or comparability certificate.
        need(all(t[1] == unit and t[2] == polarity for t in traces.values()),
             "all training/query movies must share declared calibration units and polarity")
        captured[fold] = {"center": center, "mad": mad, "threshold": threshold,
                          "polarity": polarity, "refractory": refractory}
    return captured, V.identity(value)


def _run_peaks(run, threshold, refractory):
    """One earliest frame per flat local maximum; chronological refractory rule."""
    peaks = []
    previous_time = None
    i = 0
    while i < len(run):
        # A plateau is one maximum, never one event per equal-valued frame.
        stop = i + 1
        while stop < len(run) and run[stop][2] == run[i][2]:
            stop += 1
        value = run[i][2]
        above_left = i == 0 or value > run[i - 1][2]
        above_right = stop == len(run) or value > run[stop][2]
        index, timestamp, _ = run[i]
        if (value >= threshold and above_left and above_right and
                (previous_time is None or timestamp - previous_time >= refractory)):
            peaks.append(index)
            previous_time = timestamp
        i = stop
    return peaks


def detect_movie(movie, trace, settings):
    """Detect across core edges, never across optical-validity gaps."""
    values = trace[0]
    spans = movie["optical_valid_intervals"]
    selected, run = [], []
    previous_span = None

    def finish_run():
        selected.extend(_run_peaks(run, settings["threshold"], settings["refractory"]))
        run.clear()

    for index, (timestamp, value) in enumerate(zip(movie["frame_times"], values)):
        span = bisect_right(spans, (timestamp, Fraction(S.MAX_TIME + 1))) - 1
        valid = span >= 0 and spans[span][0] <= timestamp < spans[span][1]
        if not valid or value is None:
            finish_run()
            previous_span = None
            continue
        if previous_span is not None and span != previous_span:
            finish_run()
        z = settings["polarity"] * (V.scalar(value) - settings["center"]) / settings["mad"]
        run.append((index, timestamp, z))
        previous_span = span
    finish_run()
    return selected


def produce(public, optical, calibration):
    """Generate the complete optical_mad role; no private callback or scoring."""
    contract, traces, packet_sha = V._capture(public, optical)
    settings, calibration_sha = calibration_contract(calibration, contract, traces)
    cores = {}
    total = 0
    for mid, movie in contract["movies"].items():
        indices = detect_movie(movie, traces[mid], settings[movie["fold_id"]])
        total += len(indices)
        need(total <= S.MAX_EVENTS, "whole-role event ceiling; never truncate")
        at = 0
        for cid, left, right in movie["cores"]:
            begin = at
            while at < len(indices) and indices[at] < right:
                at += 1
            cores[cid] = indices[begin:at]
    return {"schema": "voltron-optical-mad-output/v1", "task_id": TASK,
            "public_sha256": contract["identity"], "packet_sha256": packet_sha,
            "role_name": "optical_mad",
            "role": {"program_sha256": PROGRAM_SHA256,
                     "calibration_sha256": calibration_sha, "cores": cores},
            "movie_count": len(contract["movies"]), "frame_count": contract["frame_count"],
            "event_count": total, "calibration_fitted": False,
            "training_provenance_authenticated": False,
            "physical_clock_authenticity_established": False,
            "scientific_qualified": False, "new_benchmark_ids": 0}


def _read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", required=True)
    parser.add_argument("--optical", required=True)
    parser.add_argument("--calibration", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = produce(_read_json(args.public), _read_json(args.optical), _read_json(args.calibration))
    body = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    # Refuse accidental replacement of a previously frozen prediction artifact.
    with Path(args.output).open("x", encoding="utf-8") as handle:
        handle.write(body)


if __name__ == "__main__":
    main()
