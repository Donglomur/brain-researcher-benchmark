"""Stream the source synthetic summary tables, preserving failed original units.

No fitting, candidate execution, truth loading from pickle, or superiority rule.
The JSONL input and all numeric outputs belong to the operator's external store.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

N_UNITS = 100_000
FULL = ("acf_full", "isttc_full")
TRIAL = ("pearsonr_trial_avg", "sttc_trial_concat")
EXTRA = "sttc_trial_avg"
DURATIONS = (60, 150, 300, 450, 600)
TRIAL_COUNTS = (40, 60, 80, 100)
PANELS = ("four_methods", "continuous", "trials", "duration", "trial_count")
BASE_COLUMNS = ("unit_id", "tau", "tau_lower", "tau_upper", "fit_r_squared",
                "acf_decline", "method", "tau_ms", "fr", "alpha", "tau_ms_true",
                "tau_diff_abs", "tau_diff_rel", "ci_width")
MAX_LINE_BYTES = 128 * 1024


class Invalid(ValueError):
    pass


def finite(value, name, *, missing=False):
    if value is None and missing:
        return None
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise Invalid(name + " must be finite numeric" + (" or null" if missing else ""))
    return value


def checked(value, name):
    if not math.isfinite(value):
        raise Invalid(name + " arithmetic overflow")
    return value


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Invalid("duplicate JSON key: " + key)
            result[key] = value
        return result
    def constant(value):
        raise Invalid("non-JSON numeric constant: " + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def expected_keys():
    return {(method, "duration_s", n) for method in FULL for n in DURATIONS} | {
        (method, "n_trials", n) for method in TRIAL for n in TRIAL_COUNTS
    } | {(EXTRA, "n_trials", 40)}


def fit_row(unit, fit):
    method = fit.get("method")
    axis = "duration_s" if method in FULL else "n_trials"
    fields = {"method", axis, "tau", "tau_lower", "tau_upper", "fit_r_squared", "acf_lags_1_3"}
    if axis == "n_trials":
        fields.add("trial_iteration")
    if set(fit) != fields:
        raise Invalid("fit fields differ from the source summary interface")
    coordinate = fit[axis]
    if type(coordinate) is not int:
        raise Invalid("condition coordinate must be an integer")
    key = (method, axis, coordinate)
    if key not in expected_keys():
        raise Invalid("unknown original method/condition coordinate")
    if axis == "n_trials" and (type(fit["trial_iteration"]) is not int or fit["trial_iteration"] != 0):
        raise Invalid("the source summary selects original trial iteration zero")
    tau, lower, upper, r2 = [finite(fit[k], k, missing=True)
                            for k in ("tau", "tau_lower", "tau_upper", "fit_r_squared")]
    lags = fit["acf_lags_1_3"]
    if not isinstance(lags, list) or len(lags) != 3:
        raise Invalid("acf_lags_1_3 must contain the three original ACF ordinates")
    lags = [finite(x, "ACF ordinate", missing=True) for x in lags]
    # np.diff(acf[1:4]) <= 0 is false when any of these ordinates is NaN.
    decline = all(x is not None for x in lags) and lags[1] <= lags[0] and lags[2] <= lags[1]
    tau_ms = None if tau is None else checked(tau * 50, "tau_ms")
    error_abs = None if tau_ms is None else checked(abs(tau_ms - unit["tau_ms_true"]), "absolute error")
    error_rel = None if error_abs is None else checked(error_abs / unit["tau_ms_true"] * 100, "REE")
    width = None if lower is None or upper is None else checked(abs(upper - lower), "CI width")
    row = dict(unit_id=unit["unit_id"], tau=tau, tau_lower=lower, tau_upper=upper,
               fit_r_squared=r2, acf_decline=decline, method=method,
               tau_ms=tau_ms, fr=unit["fr"], alpha=unit["alpha"],
               tau_ms_true=unit["tau_ms_true"], tau_diff_abs=error_abs,
               tau_diff_rel=error_rel, ci_width=width)
    row[axis] = coordinate
    return key, row


def complete(row):
    """Literal source clean support: every column present and R-squared >= 0."""
    return all(value is not None for value in row.values()) and row["fit_r_squared"] >= 0


def summarize_unit(unit):
    """Return every original row plus source clean flags for one parameter draw.

    Missing fits are explicit nulls, never absent coordinates. R-squared equality
    at zero is retained. CI crossing zero and nondeclining ACF are diagnostics,
    not exclusions in this notebook. The lag-unit CI width is preserved.
    """
    if not isinstance(unit, dict) or set(unit) != {"unit_id", "tau_ms_true", "fr", "alpha", "lv", "fits"}:
        raise Invalid("unit fields differ from the source summary interface")
    if type(unit["unit_id"]) is not int or unit["unit_id"] < 0:
        raise Invalid("unit_id must be a nonnegative integer")
    truth = finite(unit["tau_ms_true"], "tau_ms_true")
    if truth <= 0:
        raise Invalid("tau_ms_true must be positive")
    for field in ("fr", "alpha"):
        finite(unit[field], field)
    finite(unit["lv"], "lv", missing=True)
    if not isinstance(unit["fits"], list) or len(unit["fits"]) != 19:
        raise Invalid("all 19 source method/condition fits are required")
    fits = {}
    for fit in unit["fits"]:
        if not isinstance(fit, dict):
            raise Invalid("fit must be an object")
        key, row = fit_row(unit, fit)
        if key in fits:
            raise Invalid("duplicate method/condition fit")
        fits[key] = row
    if set(fits) != expected_keys():
        raise Invalid("incomplete original condition grid")

    def base(method):
        axis, value = ("duration_s", 600) if method in FULL else ("n_trials", 40)
        row = dict(fits[method, axis, value])
        del row[axis]
        row["lv"] = unit["lv"]
        return row

    groups = {
        "four_methods": [[base(method) for method in FULL + TRIAL]],
        "continuous": [[dict(base(method), duration_s=600) for method in FULL]],
        "trials": [[dict(base(method), n_trials=40) for method in TRIAL + (EXTRA,)]],
        # Sensitivity support is paired within each coordinate, not intersected
        # across durations/trial counts; the source does not merge Lv here.
        "duration": [[fits[method, "duration_s", n] for method in FULL] for n in DURATIONS],
        "trial_count": [[fits[method, "n_trials", n] for method in TRIAL] for n in TRIAL_COUNTS],
    }
    return {panel: [(row, all(complete(member) for member in group))
                    for group in panel_groups for row in group]
            for panel, panel_groups in groups.items()}


def columns(panel):
    if panel == "four_methods":
        return BASE_COLUMNS + ("lv",)
    if panel in ("continuous", "duration"):
        return BASE_COLUMNS + ("duration_s",) + (("lv",) if panel == "continuous" else ())
    return BASE_COLUMNS + ("n_trials",) + (("lv",) if panel == "trials" else ())


def produce(source, output, *, expected_units=N_UNITS):
    """Write all/clean CSV pairs and per-unit support audit in a fresh directory.

    expected_units is a generated-control hook. The CLI fixes the original
    100000-unit support and exposes no subset option. No numeric input is read
    until invoked explicitly by an operator under the applicable native budget.
    """
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    digest = hashlib.sha256()
    counts = {panel: {"all_rows": 0, "clean_rows": 0} for panel in PANELS}
    files = []
    writers = {}
    succeeded = False
    try:
        for panel in PANELS:
            for kind in ("all", "clean"):
                handle = (output / (panel + "." + kind + ".csv")).open("x", newline="")
                files.append(handle)
                writer = csv.DictWriter(handle, fieldnames=columns(panel))
                writer.writeheader()
                writers[panel, kind] = writer
        audit = (output / "support.jsonl").open("x")
        files.append(audit)
        unit_count = 0
        with source.open("rb") as handle:
            while True:
                line = handle.readline(MAX_LINE_BYTES + 1)
                if not line:
                    break
                if len(line) > MAX_LINE_BYTES:
                    raise Invalid("unit record exceeds 128 KiB")
                digest.update(line)
                unit = strict_json(line)
                if not isinstance(unit, dict) or unit.get("unit_id") != unit_count or type(unit.get("unit_id")) is not int:
                    raise Invalid("unit records must retain original contiguous ordered identities")
                if unit_count >= expected_units:
                    raise Invalid("more units than the original panel")
                panels = summarize_unit(unit)
                support = {"unit_id": unit_count, "panels": {}}
                for panel, rows in panels.items():
                    support["panels"][panel] = []
                    for row, admitted in rows:
                        writers[panel, "all"].writerow(row)
                        counts[panel]["all_rows"] += 1
                        if admitted:
                            writers[panel, "clean"].writerow(row)
                            counts[panel]["clean_rows"] += 1
                        support["panels"][panel].append({
                            "method": row["method"],
                            "coordinate": row.get("duration_s", row.get("n_trials")),
                            "clean": admitted,
                            "row_missing_fields": [key for key, value in row.items() if value is None],
                            "negative_r_squared": row["fit_r_squared"] is not None and row["fit_r_squared"] < 0,
                        })
                audit.write(json.dumps(support, allow_nan=False, separators=(",", ":")) + "\n")
                unit_count += 1
        if unit_count != expected_units:
            raise Invalid("incomplete original unit panel")
        succeeded = True
    finally:
        for handle in files:
            handle.close()
    if succeeded:
        report = {"schema": "isttc_synthetic_source_summary_v1", "unit_count": unit_count,
                  "source_sha256": digest.hexdigest(), "counts": counts,
                  "source_reproduction": "summary arithmetic and support only; not fitted results or figures",
                  "improvement_evaluation": "not provided; source masks depend on author fit diagnostics",
                  "source_release": "7cdeaf0560b9bffa6c8fe4bda7a4594b312c10c5"}
        (output / "COMPLETE.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    produce(args.input, args.output)


if __name__ == "__main__":
    main()
