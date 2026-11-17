"""Explicit prospective reconstruction of the complete DN biological family.

The cached Figure4--9 callers are unavailable. No recipe in this module is
labelled the original figure execution. Required policies are supplied and
externally hashed, including policies whose original invocation is unresolved.
"""
import argparse
import importlib.util
import math
from pathlib import Path
import sys

import numpy as np

_spec = importlib.util.spec_from_file_location("temporal_producer_io", Path(__file__).with_name("producer.py"))
io = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(io)
require = io.require


def validate_recipe(recipe, expected, variables):
    keys = {"schema", "auc_window_samples", "reference_onepulse_condition", "longest_onepulse_condition",
            "isi_seconds", "metric_window_samples", "normalization", "duration_category_pool",
            "fwhm_policy", "log_fit", "bootstrap_seed", "reconstruction_status"}
    require(type(recipe) is dict and set(recipe) == keys and io.digest(recipe) == expected,
            "exact externally pinned biological recipe required")
    require(recipe["schema"] == "temporal026-biological-reconstruction/v1" and
            recipe["reconstruction_status"] == "prospective_not_original_figure_execution",
            "unavailable figure callers cannot be represented as historical parity")
    require(recipe["normalization"] == "none" and recipe["duration_category_pool"] == "equal_mean_all_six",
            "this reconstruction supports explicitly unnormalized equal category means only")
    require(recipe["fwhm_policy"] == "sampled_first_rise_first_decay_from_zero" and
            recipe["log_fit"] == "unweighted_linear_least_squares_on_log_seconds", "explicit supported metric policies required")
    require(type(recipe["bootstrap_seed"]) is int and 0 <= recipe["bootstrap_seed"] < 2**32,
            "prospective bootstrap seed required")
    ref, longest = recipe["reference_onepulse_condition"], recipe["longest_onepulse_condition"]
    require(type(ref) is int and ref == 3 and type(longest) is int and longest == 5 and
            variables["cond_temp"][ref] in (133, 134) and variables["cond_temp"][longest] == 533,
            "134ms paper reference (133ms source label) and533ms longest condition required")
    window = recipe["auc_window_samples"]
    require(type(window) is int and 2 <= window <= io.SAMPLES, "explicit integer AUC sample window required")
    starts = [int(variables["onepulse"][0, 0])] + [int(x) for x in variables["twopulse_repeat"][:, 2]]
    require(all(x + window <= io.SAMPLES for x in starts), "AUC window would silently truncate")
    interval = recipe["metric_window_samples"]
    require(type(interval) is list and len(interval) == 2 and all(type(v) is int for v in interval) and
            0 <= interval[0] < interval[1] <= io.SAMPLES, "explicit bounded peak/FWHM window required")
    isi = np.asarray(recipe["isi_seconds"], dtype=float)
    require(isi.shape == (6,) and np.isfinite(isi).all() and (isi > 0).all() and (np.diff(isi) > 0).all() and
            np.allclose(isi, variables["cond_temp"] / 1000, rtol=0, atol=0), "six source condition ISIs in seconds required")
    return recipe


def first_response(one, two, twopulse, reference_condition):
    """Source helper's ordered pair averaging, deliberately not a pooled mean."""
    estimate = np.array(one[reference_condition], dtype=float, copy=True)
    start = int(twopulse[0, 0])
    for condition in range(6):
        stop = int(twopulse[condition, 2])
        estimate[start:stop] = (estimate[start:stop] + two[condition, start:stop]) / 2
    return estimate


def sample_auc(values):
    # Exactly unit-spacing trapezoids, matching np.trapz(values) without x/t.
    values = np.asarray(values, dtype=float)
    return float(np.sum((values[:-1] + values[1:]) / 2))


def duration_metrics(trace, times, onset, interval):
    start, stop = interval
    segment = np.asarray(trace[start:stop], dtype=float)
    peak_index = int(np.argmax(segment))
    peak = float(segment[peak_index])
    if peak <= 0:
        return {"time_to_peak_seconds": None, "fwhm_seconds": None, "status": "no_positive_peak"}
    half = peak / 2
    rises = np.flatnonzero((segment[:-1] < half) & (segment[1:] >= half)) + 1
    falls = np.flatnonzero((segment[:-1] >= half) & (segment[1:] < half)) + 1
    rises = rises[rises <= peak_index]
    falls = falls[falls > peak_index]
    valid = len(rises) > 0 and len(falls) > 0
    return {"time_to_peak_seconds": float(times[start + peak_index] - times[onset]),
            "fwhm_seconds": float(times[start + falls[0]] - times[start + rises[0]]) if valid else None,
            "status": "finite" if valid else "missing_sampled_half_maximum_crossing"}


def trace_metrics(one, two, variables, recipe, retain_traces=True):
    """Derive metrics AFTER the caller averages electrode traces."""
    one, two = np.asarray(one, dtype=float), np.asarray(two, dtype=float)
    require(one.shape == two.shape == (6, io.SAMPLES) and np.isfinite(one).all() and np.isfinite(two).all(),
            "six finite complete one/two-pulse traces required")
    first = first_response(one, two, variables["twopulse_repeat"], recipe["reference_onepulse_condition"])
    isolated = two - first
    window = recipe["auc_window_samples"]
    onset = int(variables["onepulse"][0, 0])
    auc1 = sample_auc(first[onset:onset + window])
    auc2 = [sample_auc(trace[int(start):int(start) + window]) for trace, start in
            zip(isolated, variables["twopulse_repeat"][:, 2])]
    ratios = [v / auc1 for v in auc2] if math.isfinite(auc1) and auc1 != 0 else [None] * 6
    valid = all(v is not None and math.isfinite(v) for v in ratios)
    if not valid:
        ratios = [None] * 6
    log_fit = {"status": "undefined_recovery", "a": None, "c": None, "extrapolated_1_second": None}
    if valid:
        design = np.column_stack((np.log(recipe["isi_seconds"]), np.ones(6)))
        parameters, _, rank, _ = np.linalg.lstsq(design, ratios, rcond=None)
        if rank == 2 and np.isfinite(parameters).all():
            log_fit = {"status": "finite_prospective_fit", "a": float(parameters[0]), "c": float(parameters[1]),
                       "extrapolated_1_second": float(parameters[1])}
    duration = [duration_metrics(trace, variables["t"], int(pulse[0]), recipe["metric_window_samples"])
                for trace, pulse in zip(one, variables["onepulse"])]
    result = {"duration": duration,
            "longest_533ms_time_to_peak_seconds": duration[recipe["longest_onepulse_condition"]]["time_to_peak_seconds"],
            "first_auc_sample_units": auc1, "second_auc_sample_units": auc2, "recovery_ratios": ratios,
            "mean_recovery": float(np.mean(ratios)) if valid else None, "log_recovery": log_fit}
    if retain_traces:
        result.update(first_response_estimate=first.tolist(), isolated_second_responses=isolated.tolist())
    return result


def scalar_metrics(value):
    return {"time_to_peak_533ms": value["longest_533ms_time_to_peak_seconds"],
            **{"fwhm_%d" % i: row["fwhm_seconds"] for i, row in enumerate(value["duration"])},
            **{"recovery_%d" % i: x for i, x in enumerate(value["recovery_ratios"])},
            "mean_recovery": value["mean_recovery"], "recovery_1_second": value["log_recovery"]["extrapolated_1_second"]}


def regional_summary(traces, electrode_rows, variables, recipe):
    """Bounded1000-draw electrode bootstrap; no participant inference claim."""
    traces = np.asarray(traces, dtype=float)
    require(traces.shape == (len(electrode_rows), 2, 6, io.SAMPLES) and len(electrode_rows) > 0 and
            np.isfinite(traces).all(), "complete population traces required")
    mean = np.mean(traces, axis=0)
    observed = trace_metrics(mean[0], mean[1], variables, recipe)
    sampled = {key: [] for key in scalar_metrics(observed)}
    rng = np.random.RandomState(recipe["bootstrap_seed"])
    for _ in range(1000):
        choice = rng.choice(len(traces), size=len(traces), replace=True)
        pooled = np.mean(traces[choice], axis=0)
        metrics = scalar_metrics(trace_metrics(pooled[0], pooled[1], variables, recipe, retain_traces=False))
        for key, value in metrics.items():
            sampled[key].append(value)
    intervals = {}
    for key, values in sampled.items():
        finite = [v for v in values if v is not None and math.isfinite(v)]
        complete = len(finite) == 1000
        intervals[key] = {"draws": values, "finite_count": len(finite), "undefined_count": 1000 - len(finite),
                          "median": float(np.median(finite)) if complete else None,
                          "interval68": np.percentile(finite, [16, 84]).tolist() if complete else None,
                          "status": "finite_descriptive" if complete else "undefined_draws_retained_no_subsetting"}
    return {"electrodes": [r["id"] for r in electrode_rows],
            "participant_nesting": {r["id"]: r["subject"] for r in electrode_rows},
            "participants": sorted({r["subject"] for r in electrode_rows}),
            "mean_onepulse_traces": mean[0].tolist(), "mean_twopulse_traces": mean[1].tolist(),
            "metrics_of_mean_traces": observed, "bootstrap_metrics": intervals,
            "bootstrap_unit": "electrode resampling within region; average traces then measure; descriptive, not participant-level inference",
            "bootstrap_seed": recipe["bootstrap_seed"], "resamples": 1000}


def validate_selection(selection, expected, roster, categories):
    require(type(selection) is dict and set(selection) == {"schema", "entries", "selection_evidence", "pooling"} and
            selection["schema"] == "temporal026-category-selection-input/v1" and io.digest(selection) == expected,
            "externally pinned explicit category selection required")
    require(selection["pooling"] == "equal_mean_explicit_nonpreferred_categories", "explicit category pooling rule required")
    io.validate_pin(selection["selection_evidence"], io.MAX_FILE)
    entries = selection["entries"]
    require(type(entries) is list and len(entries) == 26, "main reported26 roster required; counts alone do not qualify it")
    names = set()
    for entry in entries:
        require(type(entry) is dict and set(entry) == {"electrode_id", "preferred", "nonpreferred", "threshold", "scrambled"}, "complete category identity required")
        name, pref, nonpref = entry["electrode_id"], entry["preferred"], entry["nonpreferred"]
        require(name in roster and name not in names and pref in categories and pref != "SCRAMBLED", "invalid/duplicate selected electrode/category")
        require(type(nonpref) is list and len(nonpref) == 4 and len(set(nonpref)) == 4 and
                set(nonpref) == set(categories) - {pref, "SCRAMBLED"} and
                entry["threshold"] == 0.5 and entry["scrambled"] == "excluded", "main threshold/nonpreferred pooling must be explicit")
        names.add(name)
    return {x["electrode_id"]: x for x in entries}


def summarize(plan, manifest, results, variables, recipe, recipe_sha, region, scaling,
              replay, selection=None, selection_sha=None):
    validate_recipe(recipe, recipe_sha, variables)
    require(region in {"V1-V3", "VOTC", "LOTC", "selected-all"} and scaling in plan["scalings"], "known population/model required")
    roster = replay.cohort()
    selected = validate_selection(selection, selection_sha, {r["id"] for r in roster}, replay.CATEGORIES) if selection is not None else {}
    require(region != "selected-all" or bool(selected), "pooled main category family requires all26 explicit identities")
    rows = [r for r in roster if (r["id"] in selected if region == "selected-all" else r["varea"] == region)]
    expected = {r["id"] for r in rows}
    populations = {"observations": {}, "DN_predictions": {}}
    preferred = {kind: {"preferred": {}, "nonpreferred": {}} for kind in populations}
    seen, failures, parameter_records = set(), [], []
    for result in results:
        compact = io.validate_result(result, plan, manifest)
        job = compact["job"]
        name = job["electrode_id"]
        require(job["mode"] == "full" and job["scaling"] == scaling and name in expected and name not in seen,
                "summary needs exactly one full fit per declared region electrode/model")
        seen.add(name)
        if compact["status"] != "converged":
            failures.append({"electrode": name, "status": compact["status"]})
            continue
        identities = result["prediction_identities"]
        for kind, key in (("observations", "observations"), ("DN_predictions", "predictions")):
            array = np.asarray(result[key])
            def pool(categories):
                return np.stack([np.stack([np.mean(array[[i for i, row in enumerate(identities)
                      if row["trial_type"] == trial and row["temp_cond"] == condition and row["img_cat"] in categories]], axis=0)
                      for condition in range(6)]) for trial in replay.TRIALS])
            populations[kind][name] = pool(replay.CATEGORIES)
            if name in selected:
                preferred[kind]["preferred"][name] = pool([selected[name]["preferred"]])
                preferred[kind]["nonpreferred"][name] = pool(selected[name]["nonpreferred"])
        parameter_records.append({"electrode_id": name, "fit": result["fit"],
                                  "component_source": "full result retains linear/numerator/normalization pool/denominator/semisaturation"})
    require(seen == expected, "incomplete regional full-fit population")
    report = {"schema": "temporal026-biological-reconstruction-result/v1", "plan_sha256": plan["plan_sha256"],
              "recipe_sha256": recipe_sha, "recipe": recipe, "region": region, "scaling": scaling,
              "population_scope": "main_all26_selected_trace_first_pool" if region == "selected-all" else "responsive_regional_family_with_optional_regional_category_companion",
              "electrode_regions": {r["id"]: r["varea"] for r in rows},
              "all_region_electrodes": [r["id"] for r in rows], "failures": failures,
              "parameters": parameter_records, "status": "incomplete_fits" if failures else "complete_prospective_reconstruction",
              "scientific_qualification": False, "historical_figure_execution": False,
              "category_family": {"status": "pending_original_selection_identities_and_trial_protocol" if selection is None else "provided_selection_not_publication_qualified",
                                  "selection_sha256": selection_sha}, "regional": {}}
    if failures:
        return report
    report["regional"] = {kind: regional_summary([mapping[r["id"]] for r in rows], rows, variables, recipe)
                          for kind, mapping in populations.items()}
    if selected:
        chosen_rows = [r for r in rows if r["id"] in selected]
        report["category_family"]["selection"] = selection
        report["category_family"]["regional"] = {kind: {preference:
            regional_summary([mapping[r["id"]] for r in chosen_rows], chosen_rows, variables, recipe)
            if chosen_rows else {"status": "no_selected_electrodes_in_region"}
            for preference, mapping in parts.items()} for kind, parts in preferred.items()}
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for option in ("plan", "plan-sha256", "manifest", "results", "input-root", "recipe", "recipe-sha256", "region", "scaling", "output"):
        p.add_argument("--" + option, required=True)
    p.add_argument("--replay-dir"); p.add_argument("--selection"); p.add_argument("--selection-sha256")
    a = p.parse_args(argv)
    require(bool(a.selection) == bool(a.selection_sha256), "selection path and external identity must be paired")
    replay = io.load_replay(a.replay_dir)
    plan, manifest = (io.parse_json(io.bounded_read(x)) for x in (a.plan, a.manifest))
    io.validate_plan(plan, a.plan_sha256, manifest, replay)
    variables = io.read_variables(a.input_root, plan["input_bindings"]["variables"], replay)
    index_raw = io.bounded_read(a.results)
    index = io.parse_json(index_raw)
    selection = io.parse_json(io.bounded_read(a.selection, 65536)) if a.selection else None
    selected = validate_selection(selection, a.selection_sha256, {r["id"] for r in replay.cohort()}, replay.CATEGORIES) if selection is not None else {}
    require(a.region != "selected-all" or bool(selected), "pooled category route requires exact26 selection")
    expected = [r for r in replay.cohort() if (r["id"] in selected if a.region == "selected-all" else r["varea"] == a.region)]
    require(type(index) is list and len(index) == len(expected), "exact bounded regional full-fit index required")
    for pin in index:
        io.validate_pin(pin, io.MAX_FILE)
    require(len({x["path"] for x in index}) == len(index), "duplicate result path")
    results = (io.parse_json(io.read_member(Path(a.results).parent, pin)) for pin in index)
    recipe = io.parse_json(io.bounded_read(a.recipe, 65536))
    if selection:
        # Evidence is required as bytes, not merely an unaudited hash claim.
        io.read_member(Path(a.selection).parent, selection["selection_evidence"])
    report = summarize(plan, manifest, results, variables, recipe, a.recipe_sha256, a.region, a.scaling,
                       replay, selection, a.selection_sha256)
    report["result_index_sha256"] = io.hashlib.sha256(index_raw).hexdigest()
    print(io.write_new(a.output, report))
    return 2 if report["failures"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise SystemExit("temporal-biological-reconstruction: " + str(exc))
