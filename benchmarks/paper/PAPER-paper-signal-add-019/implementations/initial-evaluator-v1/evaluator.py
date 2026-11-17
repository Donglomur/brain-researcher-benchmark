"""Auditable decision-times export analysis; no HMP fitting or qualification.

Original implementation of source-defined equations and explicit prospective
aggregation policies. Python standard library only. See docs for held scopes.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

TASK = "PAPER-paper-signal-add-019"
REVISION = "76464a9ca15564897e58256081af4b99d08ae8db"
EVENTS = ["C1", "P100", "N200", "LRP", "CPP"]
STAGES = ["stimulus_to_C1", "C1_to_P100", "P100_to_N200", "N200_to_LRP", "LRP_to_CPP", "CPP_to_model_end"]
TARGETS = STAGES + ["encoding", "decision", "rt"]
ROIS = {"occipital": ["O1", "Oz", "O2"], "centroparietal": ["CP1", "Pz", "CP2"], "frontal": ["AF3", "Fz", "AF4"]}
# Exact source bin construction, not rounded boundaries.
ERP_BOUNDS = [0.034999999 * 100, (0.034999999 + 0.9550001) * 50, 0.9550001 * 100]
HOLDS = [
    "No native FIF payload/header was acquired or validated; complete trial population is an external export assertion.",
    "No native HMP 1.0.0-b2 execution/API compatibility, event-number selection or model estimation is established.",
    "OSF data redistribution license remains unresolved; no data are bundled.",
    "Source point-time export, response offset and ERP alignment need native parity before reproduction.",
    "Numeric reference outputs/tolerances and independent authentic reproduction remain unfrozen.",
    "Generated engineering controls do not establish baseline competence or scientific qualification.",
    "PCA/scaling/HMP training-only provenance remains externally auditable; supplied declarations are not proof.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, label):
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value), f"{label}: finite number required")
    return float(value)


def identifier(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label}: nonempty string required")
    return value


def unique(values, label):
    require(len(values) == len(set(values)), f"{label}: duplicate")


def mean(values):
    return statistics.fmean(values)


def r_squared(observed, predicted):
    require(len(observed) == len(predicted) and len(observed) > 0, "R2: nonempty aligned vectors required")
    center = mean(observed)
    sst = sum((v - center) ** 2 for v in observed)
    return None if sst == 0 else 1 - sum((a - b) ** 2 for a, b in zip(observed, predicted)) / sst


def interval(values, seed=19019, draws=2000):
    """Prospective participant bootstrap; no trial pseudoreplication."""
    require(values and draws >= 100, "bootstrap needs values and >=100 draws")
    if len(values) == 1:
        return {"mean": values[0], "n_participants": 1, "ci95": None}
    rng = random.Random(seed)
    samples = sorted(mean(rng.choices(values, k=len(values))) for _ in range(draws))
    def quantile(q):
        z = q * (len(samples) - 1)
        lo = int(z)
        return samples[lo] + (samples[min(lo + 1, len(samples) - 1)] - samples[lo]) * (z - lo)
    return {"mean": mean(values), "n_participants": len(values), "ci95": [quantile(.025), quantile(.975)]}


def posterior_point_times(probabilities, sample_rate_hz):
    """Five event marginal PMFs -> mode times and source model-support endpoint.

    Replicates hmp v1.0.0-b2 event_times max/first-tie and add_rt support
    convention for complete, already aligned marginals. It does not infer
    events from EEG or remove the upstream response offset.
    """
    rate = number(sample_rate_hz, "sample rate")
    require(rate > 0 and isinstance(probabilities, list) and len(probabilities) == 5, "five event marginals and positive rate required")
    rows = [[number(p, "probability") for p in row] for row in probabilities]
    require(rows[0] and all(len(r) == len(rows[0]) for r in rows), "equal nonempty posterior support required")
    require(all(all(p >= 0 for p in r) and math.isclose(sum(r), 1, rel_tol=0, abs_tol=1e-8) for r in rows), "event marginals must be nonnegative and normalize to one")
    modes, ends = [], []
    for row in rows:
        modes.append(max(range(len(row)), key=row.__getitem__))
        total, cumulative = 0., []
        for p in row:
            total += p
            cumulative.append(total)
        ends.append(max(range(len(row)), key=cumulative.__getitem__) + 1)
    require(modes[0] > 0, "zero-mode/missing-event ambiguity requires native group context")
    require(all(b >= a for a,b in zip(modes,modes[1:])), "posterior modes violate event order")
    return {"event_times_ms": [i * 1000 / rate for i in modes], "model_end_ms": max(ends) * 1000 / rate}


def read_trials(payload):
    require(payload.get("schema") == "decision-times-export-v1", "wrong schema")
    require(payload.get("purpose") in {"engineering_control", "empirical_export"}, "explicit purpose required")
    require(payload.get("time_unit") == "ms" and payload.get("contrast_unit") == "percent", "units must be ms and percent")
    require(payload.get("time_origin") == "stimulus_onset", "time origin must be stimulus onset")
    require(payload.get("point_time_method") in {"hmp_export_unverified", "explicit_point_estimates"}, "explicit point-time method required")
    rate = number(payload.get("sample_rate_hz"), "sample rate")
    require(rate > 0, "sample rate must be positive")
    roster = payload.get("expected_participants")
    require(isinstance(roster, list) and roster, "expected participant roster required")
    for p in roster:
        identifier(p, "participant")
    unique(roster, "participant roster")
    if payload["purpose"] == "empirical_export":
        require(set(roster) == {f"{i}_epo" for i in range(26)}, "empirical source cohort must retain all 26 participants")
    inventory = payload.get("trial_inventory")
    require(isinstance(inventory, list) and inventory, "full retained/excluded trial inventory required")
    inv = {}
    for row in inventory:
        key = (identifier(row.get("participant"), "inventory participant"), identifier(row.get("epoch"), "inventory epoch"))
        require(key[0] in roster and key not in inv, "unknown/duplicate inventory trial")
        require(row.get("disposition") in {"retained", "excluded"}, "inventory disposition required")
        if row["disposition"] == "excluded":
            identifier(row.get("reason"), "exclusion reason")
        inv[key] = row["disposition"]
    require(set(p for p, _ in inv) == set(roster), "inventory must cover complete roster")
    trials = payload.get("trials")
    require(isinstance(trials, list) and trials, "trials required")
    out, seen = [], set()
    for row in trials:
        key = (identifier(row.get("participant"), "participant"), identifier(row.get("epoch"), "epoch"))
        require(key not in seen, "duplicate trial")
        seen.add(key)
        require(inv.get(key) == "retained", "trial absent or excluded in inventory")
        condition = row.get("condition")
        require(condition in {"speed", "accuracy"}, "unknown condition")
        side, response = row.get("side"), row.get("response")
        require(side in {"left", "right"} and response in {"left", "right"}, "left/right side and responded trial required")
        contrast = number(row.get("contrast_percent"), "contrast")
        require(2.5 < contrast <= 100, "contrast outside law domain (2.5,100]")
        rt = number(row.get("rt_ms"), "RT")
        require(rt > 0, "RT must be positive")
        events = row.get("event_times_ms")
        require(isinstance(events, list) and len(events) == 5, "exactly five event point times required")
        endpoint = number(row.get("model_end_ms"), "model endpoint")
        require(endpoint > 0, "model endpoint must be positive")
        points = [0.] + [number(v, "event time") for v in events] + [endpoint]
        require(all(b >= a for a, b in zip(points, points[1:])), "event order must lie within stimulus/response")
        values = dict(zip(STAGES, [b - a for a, b in zip(points, points[1:])]))
        values.update(encoding=points[3] - points[1], decision=points[5] - points[3], rt=rt)
        out.append({"participant": key[0], "epoch": key[1], "condition": condition, "contrast_percent": contrast,
                    "correct": side == response, "side": side, "response": response, "model_end_minus_rt_ms": endpoint - rt, "values": values})
    require(seen == {key for key, state in inv.items() if state == "retained"}, "missing retained trial: no silent subset")
    require(set(t["participant"] for t in out) == set(roster), "every participant must have retained trials")
    return out


def latency_summary(trials):
    """All responded trials and explicitly separate correct-response sensitivity."""
    outputs = {}
    accuracy_groups = defaultdict(list)
    for t in trials:
        accuracy_groups[(t["participant"], t["condition"], t["contrast_percent"])].append(t["correct"])
    for selection in ["correct_only", "all_responded"]:
        subset = [t for t in trials if selection == "all_responded" or t["correct"]]
        cells = defaultdict(list)
        for t in subset:
            cells[(t["participant"], t["condition"], t["contrast_percent"])].append(t)
        rows = []
        for (part, cond, contrast), group in sorted(cells.items()):
            rows.append({"participant": part, "condition": cond, "contrast_percent": contrast, "n_trials": len(group),
                         "accuracy_all_responded": mean(accuracy_groups[(part, cond, contrast)]),
                         "means_ms": {name: mean(t["values"][name] for t in group) for name in TARGETS}})
        slopes, cellgroups = [], defaultdict(list)
        for row in rows:
            cellgroups[(row["participant"], row["condition"])].append(row)
        for (part, cond), group in sorted(cellgroups.items()):
            xs = [r["contrast_percent"] for r in group]
            center = mean(xs)
            denom = sum((x - center) ** 2 for x in xs)
            slopes.append({"participant": part, "condition": cond, "n_contrasts": len(xs),
                           "ms_per_percent": {name: None if denom == 0 else sum((r["contrast_percent"] - center) * r["means_ms"][name] for r in group) / denom for name in TARGETS}})
        group_effects = []
        for cond in ["accuracy", "speed"]:
            for target in TARGETS:
                valid = [r for r in slopes if r["condition"] == cond and r["ms_per_percent"][target] is not None]
                if valid:
                    group_effects.append({"condition": cond, "target": target, "unit": "ms/percentage_point", **interval([r["ms_per_percent"][target] for r in valid]), "participants": [r["participant"] for r in valid]})
        # Pair condition effects at identical participant/contrast cells; no pooled-trial contrast.
        lookup = {(r["participant"], r["condition"], r["contrast_percent"]): r for r in rows}
        paired, unpaired = defaultdict(list), []
        for part, contrast in sorted({(p,c) for p,_,c in lookup}):
            a, s = lookup.get((part, "accuracy", contrast)), lookup.get((part, "speed", contrast))
            if a and s:
                for target in TARGETS:
                    paired[(contrast, target)].append((part, a["means_ms"][target] - s["means_ms"][target]))
            else:
                unpaired.append((part, contrast))
        outputs[selection] = {"n_trials": len(subset), "cells": rows, "participant_slopes": slopes,
            "participant_equal_contrast_slopes": group_effects,
            "accuracy_minus_speed_ms": [{"contrast_percent": c, "target": target, "participants": [p for p, _ in pairs], **interval([v for _, v in pairs])} for (c, target), pairs in sorted(paired.items())],
            "unpaired_condition_cells": [list(k) for k in unpaired],
            "absent_participants": sorted(set(t["participant"] for t in trials) - set(t["participant"] for t in subset))}
    return outputs


def law_prediction(name, contrast_percent, parameters):
    """Pinned models.py equations; parameters use seconds and contrast fraction."""
    x = number(contrast_percent, "contrast") / 100
    require(.025 < x <= 1, "contrast outside Fechner domain")
    p = [number(v, "law parameter") for v in parameters]
    if name == "linear":
        require(len(p) == 2, "linear needs slope,t0")
        seconds, accuracy = p[0] * x + p[1], None
    elif name == "pieron":
        require(len(p) == 2 and all(v >= 0 for v in p), "Pieron needs nonnegative slope,alpha; no intercept")
        seconds, accuracy = p[0] * x ** (-p[1]), None
    elif name == "fechner":
        require(len(p) == 3 and all(0 <= v <= bound for v, bound in zip(p, [18.51, 7.47, 3.69])), "Fechner parameter bounds violated")
        k, a, t0 = p
        z = math.log((x + .025) / (x - .025))
        # Continuous k=0 limit avoids source division-by-zero boundary.
        seconds = a * a + t0 if k == 0 else a / (k * z) * math.tanh(a * k * z) + t0
        accuracy = 1 / (1 + math.exp(-2 * a * k * z))
    else:
        raise ValueError("unknown psychophysical law")
    require(math.isfinite(seconds), "nonfinite law prediction")
    return seconds * 1000, accuracy


def law_scores(trials, spec):
    """Evaluate frozen exported parameters, never refit on scored data."""
    require(spec.get("target") in TARGETS, "unknown law target")
    require(spec.get("selection") in {"all_responded", "correct_only"}, "law selection required")
    require(spec.get("mode") in {"descriptive", "leave_one_contrast_out"}, "law mode required")
    target, model = spec["target"], spec.get("model")
    rows = [r for r in trials if spec["selection"] == "all_responded" or r["correct"]]
    require(rows, "law selection empty")
    by_cell = defaultdict(list)
    for r in rows:
        by_cell[(r["participant"], r["condition"], r["contrast_percent"])].append(r)
    coefficients = {}
    for r in spec.get("parameters", []):
        key = (r.get("participant"), r.get("condition"), r.get("held_out_contrast_percent") if spec["mode"] == "leave_one_contrast_out" else None)
        require(key not in coefficients, "duplicate law parameters")
        require(isinstance(r.get("values"), list), "law values required")
        if spec["mode"] == "leave_one_contrast_out":
            held = number(key[2], "held contrast")
            train = r.get("fit_contrasts_percent")
            require(isinstance(train, list) and train, "fit contrasts required")
            train = [number(x, "fit contrast") for x in train]
            unique(train, "fit contrasts")
            available = {c for p, cond, c in by_cell if (p, cond) == key[:2]}
            require(set(train) == available - {held} and held in available, "contrast leakage or incomplete fit contrast declaration")
        coefficients[key] = r["values"]
    required = {(p, c, x if spec["mode"] == "leave_one_contrast_out" else None) for p, c, x in by_cell}
    require(set(coefficients) == required, "law parameters must exactly cover all selected participant/condition cells")
    cells, individual_errors = [], defaultdict(list)
    for (part, cond, contrast), group in sorted(by_cell.items()):
        pred, acc = law_prediction(model, contrast, coefficients[(part, cond, contrast if spec["mode"] == "leave_one_contrast_out" else None)])
        observed = [r["values"][target] for r in group]
        individual_errors[(part, cond)].extend((v - pred) ** 2 / 1e6 for v in observed)
        cells.append({"participant": part, "condition": cond, "contrast_percent": contrast, "n_trials": len(group), "observed_ms": mean(observed), "predicted_ms": pred, "observed_accuracy": mean(r["correct"] for r in trials if r["participant"] == part and r["condition"] == cond and r["contrast_percent"] == contrast), "predicted_accuracy": acc})
    grouped = []
    for cond in sorted({r["condition"] for r in cells}):
        contrasts = sorted({r["contrast_percent"] for r in cells if r["condition"] == cond})
        obs_equal, obs_pooled, pred_equal, acc_equal, acc_pred = [], [], [], [], []
        for c in contrasts:
            group = [r for r in cells if r["condition"] == cond and r["contrast_percent"] == c]
            obs_equal.append(mean(r["observed_ms"] for r in group))
            obs_pooled.append(sum(r["observed_ms"] * r["n_trials"] for r in group) / sum(r["n_trials"] for r in group))
            pred_equal.append(mean(r["predicted_ms"] for r in group))
            acc_equal.append(mean(r["observed_accuracy"] for r in group))
            if model == "fechner":
                acc_pred.append(mean(r["predicted_accuracy"] for r in group))
        grouped.append({"condition": cond, "contrasts_percent": contrasts,
            "participant_equal_curve_rmse_ms": math.sqrt(mean((a-b)**2 for a,b in zip(obs_equal,pred_equal))),
            "source_asymmetric_curve_rmse_ms": math.sqrt(mean((a-b)**2 for a,b in zip(obs_pooled,pred_equal))),
            "participant_equal_curve_r2": r_squared(obs_equal,pred_equal),
            "participant_equal_accuracy_r2": r_squared(acc_equal,acc_pred) if model == "fechner" else None})
    return {"target": target, "model": model, "mode": spec["mode"], "selection": spec["selection"], "assessment_role": "canonical_correct_response_primary" if spec["selection"] == "correct_only" else "source_all_responded_sensitivity", "cells": cells,
        "participant_trial_mse_seconds_squared": [{"participant":p,"condition":c,"mse_s2":mean(v)} for (p,c),v in sorted(individual_errors.items())],
        "curve_scores": grouped, "fit_provenance": "supplied_parameters_not_independently_verified"}


def erp_scores(trials, spec):
    """Source ROI/bin participant averages on already stimulus-aligned voltages."""
    require(spec.get("alignment") == "stimulus" and spec.get("amplitude_unit") == "V", "ERP requires stimulus-aligned volts")
    times = [number(v, "ERP time") for v in spec.get("times_ms", [])]
    require(len(times) >= 2 and all(b>a for a,b in zip(times,times[1:])) and times[0] == 0 and times[-1] == 1000, "ERP common grid must increase from 0 to 1000 ms")
    channels = spec.get("channels")
    require(isinstance(channels,list) and all(isinstance(c,str) for c in channels), "ERP channels required")
    unique(channels,"ERP channels")
    require(all(c in channels for roi in ROIS.values() for c in roi), "all nine source ROI electrodes required")
    by_trial = {(t["participant"],t["epoch"]):t for t in trials}
    waves, seen, outside_bins = defaultdict(list), set(), []
    for row in spec.get("trials", []):
        key = (row.get("participant"),row.get("epoch"))
        require(key in by_trial and key not in seen, "unknown/duplicate ERP trial")
        seen.add(key)
        data = row.get("volts")
        require(isinstance(data,list) and len(data)==len(channels), "ERP channel count mismatch")
        data = [[number(v,"voltage") for v in values] for values in data]
        require(all(len(a)==len(times) for a in data), "ERP time length mismatch")
        t=by_trial[key]; contrast=t["contrast_percent"]
        if not ERP_BOUNDS[0] < contrast <= ERP_BOUNDS[-1]:
            outside_bins.append({"participant":key[0],"epoch":key[1],"contrast_percent":contrast,"reason":"outside_source_ERP_analysis_bins"})
            continue
        bin_name = "low" if contrast <= ERP_BOUNDS[1] else "high"
        for roi,names in ROIS.items():
            curve=[mean(data[channels.index(c)][i] for c in names)*1e6 for i in range(len(times))]
            waves[(t["participant"],t["condition"],bin_name,roi)].append(curve)
    require(seen==set(by_trial), "ERP must cover exactly all retained trials")
    average={key:[mean(curve[i] for curve in curves) for i in range(len(times))] for key,curves in waves.items()}
    outputs=[]
    for cond in ["accuracy","speed"]:
        for roi in ROIS:
            parts=sorted({p for p,c,b,r in average if c==cond and r==roi})
            valid=[p for p in parts if (p,cond,"low",roi) in average and (p,cond,"high",roi) in average]
            if not valid:
                outputs.append({"condition":cond,"roi":roi,"status":"no_paired_low_high_participants","unpaired_participants":parts});continue
            differences=[[a-b for a,b in zip(average[(p,cond,"low",roi)],average[(p,cond,"high",roi)])] for p in valid]
            outputs.append({"condition":cond,"roi":roi,"participants":valid,"unpaired_participants":sorted(set(parts)-set(valid)),
                "low_minus_high_uV":[mean(d[i] for d in differences) for i in range(len(times))],
                "participant_window_mean_difference_uV":dict(zip(valid,[sum((a+b)/2*(tb-ta) for a,b,ta,tb in zip(d,d[1:],times,times[1:]))/(times[-1]-times[0]) for d in differences])),
                "cluster_significance":"not_computed_native_cluster_recipe_held"})
    return {"times_ms":times,"bins_percent":ERP_BOUNDS,"out_of_source_bin_trials":outside_bins,"n_input_trials":len(seen),"n_ERP_scored_trials":len(seen)-len(outside_bins),"summaries":outputs,"alignment_provenance":"supplied_aligned_curves_not_native_parity"}


def heldout_likelihood(trials, spec):
    """Check declared group separation and score paired externally fitted likelihoods."""
    require(spec.get("unit")=="natural_log_per_trial" and spec.get("same_observation_space") is True, "comparable natural-log trial likelihoods required")
    reference=identifier(spec.get("baseline_model"),"baseline model")
    population={t["participant"] for t in trials}; expected={(t["participant"],t["epoch"]) for t in trials}
    models=spec.get("models")
    require(isinstance(models,list) and len(models)>=2,"at least baseline and candidate required")
    names=[identifier(m.get("name"),"model name") for m in models];unique(names,"model names")
    require(reference in names,"baseline model absent")
    scores={}; signatures={}
    for model in models:
        n=number(model.get("event_count"),"event count");width=number(model.get("event_width_ms"),"event width")
        require(n>=1 and n.is_integer() and width>0,"event count/width invalid")
        scored={};fold_sig={}
        for fold in model.get("folds",[]):
            test=fold.get("test_participants"); fit=fold.get("fit_participants");pre=fold.get("preprocess_fit_participants")
            require(all(isinstance(x,list) and x for x in [test,fit,pre]),"nonempty fold train/test declarations required")
            for a in [test,fit,pre]:unique(a,"fold roster")
            require(set(test)|set(fit)==population and not set(test)&set(fit) and set(pre)==set(fit),"participant or preprocessing leakage / incomplete fold")
            for p in test:
                require(p not in fold_sig,"participant tested in multiple folds")
                fold_sig[p]=tuple(sorted(fit))
            for row in fold.get("scores",[]):
                key=(row.get("participant"),row.get("epoch"))
                require(key in expected and key[0] in test and key not in scored,"unknown/duplicate/wrong-fold likelihood")
                scored[key]=number(row.get("log_likelihood"),"log likelihood")
        require(set(scored)==expected and set(fold_sig)==population,"likelihood omits retained trial/participant")
        scores[model["name"]]=scored;signatures[model["name"]]=fold_sig
    require(all(s==signatures[reference] for s in signatures.values()),"model folds differ")
    outputs=[]
    for name in names:
        if name==reference:continue
        deltas={p:mean(scores[name][k]-scores[reference][k] for k in expected if k[0]==p) for p in sorted(population)}
        outputs.append({"candidate":name,"baseline":reference,"participant_mean_delta_log_likelihood":deltas,
            "participant_equal_delta":interval(list(deltas.values())),"total_delta":sum(scores[name][k]-scores[reference][k] for k in expected)})
    return {"comparisons":outputs,"training_separation":"declaration_consistent_not_independent_execution_attestation", "model_selection":"no_winner_or_event_number_selected_on_this_panel"}


def evaluate(payload):
    trials=read_trials(payload)
    result={"task_id":TASK,"implementation":"initial-evaluator-v1","scope":"export_metric_component",
        "qualification":"unknown","scientific_runs":0,"binary_reward":None,"source_revision":REVISION,
        "sample_rate_hz":payload["sample_rate_hz"],"sampling_profile":"source_512_hz" if payload["sample_rate_hz"]==512 else "explicit_alternative_not_native_recipe",
        "purpose":payload["purpose"],"primary_latency_selection":"correct_only","source_sensitivity_selection":"all_responded","participants":sorted(set(t["participant"] for t in trials)),"n_trials":len(trials),
        "exclusions":[r for r in payload["trial_inventory"] if r["disposition"]=="excluded"],
        "model_end_minus_behavior_rt_ms":[{"participant":t["participant"],"epoch":t["epoch"],"difference_ms":t["model_end_minus_rt_ms"]} for t in trials],
        "latency":latency_summary(trials),"laws":[law_scores(trials,s) for s in payload.get("law_evaluations",[])],"holds":HOLDS}
    if "erp" in payload:result["erp"]=erp_scores(trials,payload["erp"])
    if "heldout_likelihood" in payload:result["heldout_likelihood"]=heldout_likelihood(trials,payload["heldout_likelihood"])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",type=Path);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();raw=args.input.read_bytes()
    result=evaluate(json.loads(raw));result["input_sha256"]=hashlib.sha256(raw).hexdigest()
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")

if __name__=="__main__":main()
