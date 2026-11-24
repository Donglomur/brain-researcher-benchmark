"""Source-grounded parameter-table statistics for PAPER-ROOT-ADD-021.

This independently written component does not run or substitute for the author
spectral fitter, authenticate data, freeze grading tolerances, or qualify a task.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path, PurePosixPath
import numpy as np

TASK_ID = "PAPER-ROOT-ADD-021"
SOURCE_COMMIT = "218f87e81d4aa8ac3658467f4a4c85ad1dc4128d"
REGIONS = {
    "Postcentral_gyrus": "S", "Precentral_gyrus": "S",
    "Superior_temporal_gyrus": "S", "Middle_frontal_gyrus": "A",
    "Middle_temporal_gyrus": "A", "Supramarginal_gyrus": "A",
}
METRICS = ("PAF", "INT")
COLUMNS = ("ID", "age", "region", "time", "fit0", "PAF", "PAA", "INT", "offset", "knee", "exp")
HOLDS = [
    "Authentic complete 13-participant archive payload and montage coverage not validated.",
    "Native spectrum generation and custom FOOOF fit not executed or validated here.",
    "Historical FOOOF branch revision used for the paper remains unproven; inspected pin is prospective.",
    "Notebook/model knee-to-INT transformations and paper/source peak definitions disagree; supplied INT is preserved.",
    "Figure-specific empirical references, score, and numeric tolerances are not frozen.",
    "Public inputs/results are exposed; no sealed independent improvement panel exists.",
    "Official analysis-code license unknown; data CC-BY-NC-4.0 terms remain distinct.",
    "Clinical cohort and electrode coverage limit developmental interpretation.",
]

class ContractError(ValueError):
    """An input would change the declared population or endpoint semantics."""


def portable_relative_path(root, relative):
    """Normalize notebook separators without accepting absolute/traversing paths."""
    text = str(relative).replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or ":" in text or any(p == ".." for p in path.parts):
        raise ContractError("Only a contained relative path is allowed")
    target = (Path(root).resolve() / Path(*path.parts)).resolve()
    if not target.is_relative_to(Path(root).resolve()):
        raise ContractError("Path escapes root")
    return target


def _number(value, name, allow_nan=False):
    try:
        if allow_nan and (value is None or str(value).strip().lower() in ("", "nan")):
            return float("nan")
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ContractError(f"Invalid {name}: {value!r}") from exc
    if math.isnan(number) and allow_nan:
        return number
    if not math.isfinite(number):
        raise ContractError(f"Nonfinite {name}")
    return number


def validate_roster(expected_participants):
    if not isinstance(expected_participants, (list, tuple)):
        raise ContractError("Expected participant roster must be a list of strings")
    if (not expected_participants or any(not isinstance(p, str) or not p.strip() for p in expected_participants)
            or len(expected_participants) != len(set(expected_participants))):
        raise ContractError("Expected participant roster must contain unique nonempty strings")
    return list(expected_participants)


def validate_rows(rows, expected_participants):
    """Require the complete declared roster; each key is ID/region/time."""
    expected = validate_roster(expected_participants)
    output, seen, ages = [], set(), {}
    for row in rows:
        if not set(COLUMNS).issubset(row):
            raise ContractError(f"Missing columns: {sorted(set(COLUMNS) - set(row))}")
        pid, region = str(row["ID"]), str(row["region"])
        if pid not in expected:
            raise ContractError(f"Unexpected participant {pid}")
        if region not in REGIONS:
            raise ContractError(f"Unknown source region {region}")
        item = {"ID": pid, "region": region, "ctx": REGIONS[region]}
        for name in COLUMNS:
            if name not in ("ID", "region"):
                item[name] = _number(row[name], name, name not in ("age", "time"))
        if item["age"] <= 0 or item["time"] < 0:
            raise ContractError("Age must be positive and time nonnegative")
        if pid in ages and ages[pid] != item["age"]:
            raise ContractError(f"Contradictory ages for {pid}")
        ages[pid] = item["age"]
        key = (pid, region, item["time"])
        if key in seen:
            raise ContractError(f"Duplicate ID/region/time: {key}")
        seen.add(key)
        if math.isfinite(item["PAF"]) and not 2 <= item["PAF"] <= 14:
            raise ContractError("PAF outside inspected source search range [2,14] Hz")
        if math.isfinite(item["INT"]) and item["INT"] <= 0:
            raise ContractError("INT must be positive milliseconds or missing")
        output.append(item)
    if set(ages) != set(expected):
        raise ContractError(f"Missing participants: {sorted(set(expected)-set(ages))}")
    return sorted(output, key=lambda r: (r["ID"], r["region"], r["time"]))


def read_table(path, packet):
    """Bind an explicit generated CSV to its SHA-256 and declared complete roster."""
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if packet.get("table_sha256") != digest:
        raise ContractError("Generated parameter-table SHA-256 mismatch")
    if packet.get("official_code_commit") != SOURCE_COMMIT:
        raise ContractError("Official analysis-code pin mismatch")
    if packet.get("assessment_kind") not in ("generated_engineering_control", "unqualified_public_parameter_table"):
        raise ContractError("Declare generated engineering or unqualified public table status")
    rows = list(csv.DictReader(data.decode("utf-8-sig").splitlines()))
    return validate_rows(rows, packet.get("expected_participants", [])), digest


def qc_and_smooth(rows):
    """Strict |fit0|<.2, then centered 5-row Gaussian sigma1 within ID/region.

    NaNs are excluded from each local denominator. Like the source notebook,
    smoothing may fill a QC-masked row; original keep and refill flags are kept.
    Rows are explicitly time sorted, repairing the notebook's implicit order.
    """
    groups = defaultdict(list)
    for original in rows:
        row = dict(original)
        row["keep"] = math.isfinite(row["fit0"]) and abs(row["fit0"]) < 0.2
        for metric in METRICS:
            row[metric + "_raw"] = row[metric]
            if not row["keep"]:
                row[metric] = float("nan")
        groups[(row["ID"], row["region"])].append(row)
    output = []
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda r: r["time"])
        values = {m: [r[m] for r in group] for m in METRICS}
        for index, row in enumerate(group):
            neighbors = range(max(0, index-2), min(len(group), index+3))
            row["smoothing_window_keys"] = [[group[j]["ID"], group[j]["region"], group[j]["time"]]
                                             for j in neighbors]
            for metric in METRICS:
                numerator = denominator = 0.0
                contributors = []
                for j in neighbors:
                    if math.isfinite(values[metric][j]):
                        weight = math.exp(-0.5 * (j-index)**2)
                        numerator += weight * values[metric][j]
                        denominator += weight
                        contributors.append({"key": [group[j]["ID"], group[j]["region"], group[j]["time"]],
                                             "row_offset": j-index, "gaussian_weight": weight})
                for contributor in contributors:
                    contributor["normalized_weight"] = contributor["gaussian_weight"]/denominator
                row[metric + "_smoothing_contributors"] = contributors
                row[metric] = numerator/denominator if denominator else float("nan")
                row[metric + "_filled"] = not math.isfinite(values[metric][index]) and math.isfinite(row[metric])
            output.append(row)
    return output


def parameter_window_audit(processed):
    """Retain every declared window and the exact post-QC smoothing support.

    Keys are ID/region/time, independent of CSV row order. Contributions use
    raw values from a neighbor that passes fit0 and has a finite endpoint;
    filled values never become inputs to another smoothing window.
    """
    audit = []
    for row in processed:
        entry = {name: row[name] for name in ("ID", "age", "region", "ctx", "time")}
        entry["raw_parameters"] = {
            name: row[name + "_raw"] if name in METRICS else row[name]
            for name in COLUMNS if name not in ("ID", "age", "region", "time")}
        entry["fit0_pass"] = row["keep"]
        entry["smoothing_window_keys"] = row["smoothing_window_keys"]
        for metric in METRICS:
            entry[metric] = {
                "post_qc": row[metric + "_raw"] if row["keep"] else float("nan"),
                "smoothed": row[metric], "filled_after_masking": row[metric + "_filled"],
                "contributors": row[metric + "_smoothing_contributors"]}
        audit.append(entry)
    return audit


def _betacf(a, b, x):
    # Continued fraction for the regularized incomplete beta; numerical method,
    # not copied author implementation. Guard tiny denominators and convergence.
    tiny = 1e-300
    c = 1.0
    d = 1 - (a+b)*x/(a+1)
    d = 1/(d if abs(d)>tiny else tiny)
    h = d
    for m in range(1, 301):
        for aa in (m*(b-m)*x/((a+2*m-1)*(a+2*m)),
                   -(a+m)*(a+b+m)*x/((a+2*m)*(a+2*m+1))):
            d = 1 + aa*d
            c = 1 + aa/c
            d = 1/(d if abs(d)>tiny else tiny)
            c = c if abs(c)>tiny else tiny
            delta = d*c
            h *= delta
        if abs(delta-1) < 3e-14:
            return h
    raise ArithmeticError("Incomplete beta did not converge")


def student_t_two_sided(t, df):
    if df <= 0:
        raise ContractError("Student t requires positive degrees of freedom")
    if math.isinf(t):
        return 0.0
    x = df/(df+t*t)
    if x >= 1:
        return 1.0
    if x <= 0:
        return 0.0
    a, b = df/2, 0.5
    front = math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log1p(-x))
    value = front*_betacf(a,b,x)/a if x < (a+1)/(a+b+2) else 1-front*_betacf(b,a,1-x)/b
    return max(0.0, min(1.0, value))


def ols(y, x, names, clusters=None):
    """OLS with source nonrobust inference; optional participant CR1 covariance."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    if x.ndim != 2 or y.ndim != 1 or len(y) != len(x) or x.shape[1] != len(names):
        raise ContractError("Invalid regression shapes")
    n, p = x.shape
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ContractError("Regression input must be finite after eligibility accounting")
    if n <= p or np.linalg.matrix_rank(x) < p:
        return {"status": "not_estimable", "n": n, "terms": names, "reason": "insufficient residual degrees of freedom or rank"}
    beta = np.linalg.lstsq(x,y,rcond=None)[0]
    residual = y-x@beta
    rss = float(residual@residual)
    if not np.isfinite(beta).all() or not math.isfinite(rss):
        raise ContractError("Nonfinite derived regression coefficient or residual sum of squares")
    bread = np.linalg.inv(x.T@x)
    covariance = bread*rss/(n-p)
    df = n-p
    covariance_kind = "source_nonrobust"
    if clusters is not None:
        if len(clusters) != n:
            raise ContractError("Cluster length mismatch")
        keys = sorted(set(clusters))
        if len(keys) < 2:
            return {"status": "not_estimable", "n": n, "terms": names, "reason": "fewer than two participant clusters"}
        meat = np.zeros((p,p))
        cluster_array = np.asarray(clusters)
        for key in keys:
            selected = cluster_array == key
            score = x[selected].T@residual[selected]
            meat += np.outer(score,score)
        covariance = bread@meat@bread*(len(keys)/(len(keys)-1))*((n-1)/(n-p))
        df = len(keys)-1
        covariance_kind = "prospective_participant_CR1_t_G_minus_1"
    if not np.isfinite(covariance).all():
        raise ContractError("Nonfinite derived regression covariance")
    se = np.sqrt(np.maximum(np.diag(covariance),0))
    terms = {}
    for i,name in enumerate(names):
        t = float(beta[i]/se[i]) if se[i] else (math.copysign(math.inf,beta[i]) if beta[i] else 0.0)
        terms[name] = {"coefficient":float(beta[i]), "standard_error":float(se[i]), "t":t, "p_two_sided":student_t_two_sided(t,df)}
    total = float(((y-_mean(y))**2).sum())
    if not math.isfinite(total):
        raise ContractError("Nonfinite derived regression total sum of squares")
    return {"status":"estimated", "n":n, "residual_df":n-p, "inference_df":df, "covariance":covariance_kind,
            "r_squared":1-rss/total if total>0 else None, "terms":terms, "rss":rss}


def bh_adjust(values):
    """Benjamini-Hochberg adjustment with original key order restored."""
    keys = sorted(values, key=lambda k: values[k])
    adjusted, bound = {}, 1.0
    for i in range(len(keys)-1,-1,-1):
        bound = min(bound, values[keys[i]]*len(keys)/(i+1))
        adjusted[keys[i]] = bound
    return adjusted


def _mean(values):
    values = list(values)
    if any(math.isinf(v) for v in values):
        raise ContractError("Infinite value cannot be omitted from an aggregate")
    values = [v for v in values if math.isfinite(v)]
    try:
        result = math.fsum(v/len(values) for v in values) if values else float("nan")
    except OverflowError as exc:
        raise ContractError("Nonfinite aggregate") from exc
    if math.isinf(result):
        raise ContractError("Nonfinite aggregate")
    return result


def summarize(rows, fields):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[f] for f in fields)].append(row)
    summaries = []
    for key, group in sorted(groups.items()):
        entry = dict(zip(fields,key))
        entry["age"] = group[0]["age"]
        entry["rows"] = len(group)
        for metric in METRICS:
            values = [r[metric] for r in group if math.isfinite(r[metric])]
            entry[metric] = _mean(values)
            entry[metric+"_n"] = len(values)
            entry[metric+"_q25"] = float(np.quantile(values,.25)) if values else float("nan")
            entry[metric+"_q75"] = float(np.quantile(values,.75)) if values else float("nan")
        summaries.append(entry)
    return summaries


def age_model(rows, metric):
    eligible = [r for r in rows if math.isfinite(r[metric])]
    result = ols([r[metric] for r in eligible], [[1,math.log2(r["age"])] for r in eligible], ["Intercept","log2_age"]) if eligible else {"status":"not_estimable","n":0,"reason":"no finite endpoints"}
    result["included_participants"] = [r["ID"] for r in eligible]
    result["excluded_participants"] = [r["ID"] for r in rows if not math.isfinite(r[metric])]
    return result


def analyze(rows, expected_participants):
    rows = validate_rows(rows,expected_participants)
    processed = qc_and_smooth(rows)
    regional = summarize(processed,["ID","region","ctx"])
    contexts = summarize(processed,["ID","ctx"])
    omnibus = summarize(processed,["ID"])
    source_models = {}
    prospective = {}
    for metric in METRICS:
        by_region = {region:age_model([r for r in regional if r["region"]==region],metric) for region in REGIONS}
        pvalues = {r:m["terms"]["log2_age"]["p_two_sided"] for r,m in by_region.items() if m["status"]=="estimated"}
        adjustments = bh_adjust(pvalues) if len(pvalues)==len(REGIONS) else {}
        for region, adjusted in adjustments.items():
            by_region[region]["age_p_FDR_BH_within_metric"] = adjusted
        source_models[metric] = {"omnibus":age_model(omnibus,metric),
            "contexts":{c:age_model([r for r in contexts if r["ctx"]==c],metric) for c in ("S","A")}, "regions":by_region,
            "region_FDR_family":{"expected_regions":len(REGIONS), "estimable_regions":len(pvalues),
                "status":"complete_six_region_family" if len(pvalues)==len(REGIONS) else "not_computed_incomplete_six_region_family"}}
        # Prospective paired contrast gives each observed region equal weight
        # before differencing contexts; participant is the regression unit.
        pairs, absent = [], []
        for pid in sorted(expected_participants):
            subject = [r for r in regional if r["ID"]==pid]
            context_values = {c:_mean([r[metric] for r in subject if r["ctx"]==c]) for c in ("S","A")}
            if all(math.isfinite(v) for v in context_values.values()):
                pairs.append({"ID":pid,"age":subject[0]["age"],metric:context_values["A"]-context_values["S"]})
            else:
                absent.append(pid)
        prospective[metric] = {"estimand":"equal_observed_region A-minus-S slope per log2 age; paired participants only", "pairs":pairs,
                               "excluded_missing_context_or_endpoint":absent,"model":age_model(pairs,metric)}
    joint = [r for r in regional if all(math.isfinite(r[m]) for m in METRICS)]
    design = [[1,float(r["ctx"]=="S"),r["PAF"],float(r["ctx"]=="S")*r["PAF"],math.log2(r["age"])] for r in joint]
    names = ["Intercept","ctx_S","PAF","ctx_S:PAF","log2_age"]
    interaction = ols([r["INT"] for r in joint],design,names) if joint else {"status":"not_estimable","n":0}
    clustered = ols([r["INT"] for r in joint],design,names,[r["ID"] for r in joint]) if joint else {"status":"not_estimable","n":0}
    contextual_coupling = {}
    for context in ("S", "A"):
        subset = [r for r in joint if r["ctx"] == context]
        cx = [[1, r["PAF"], math.log2(r["age"])] for r in subset]
        contextual_coupling[context] = ols([r["INT"] for r in subset], cx, ["Intercept", "PAF", "log2_age"]) if subset else {"status": "not_estimable", "n": 0}
    correlation = {"status": "not_estimable", "n": len(joint), "reason": "insufficient or constant paired endpoints"}
    if len(joint) > 2:
        paf = np.asarray([r["PAF"] for r in joint])
        tau = np.asarray([r["INT"] for r in joint])
        a, b = paf-paf.mean(), tau-tau.mean()
        denominator = float(np.linalg.norm(a)*np.linalg.norm(b))
        if denominator > 0:
            corr = max(-1.0, min(1.0, float(a@b)/denominator))
            t = corr*math.sqrt((len(joint)-2)/(1-corr*corr)) if abs(corr)<1 else math.copysign(math.inf,corr)
            correlation = {"status":"estimated", "n":len(joint), "r":corr,
                           "p_two_sided":student_t_two_sided(t,len(joint)-2),
                           "inference":"source_region_level_nonindependence_not_corrected"}
    return {"task_id":TASK_ID,"component":"parameter_table_statistics", "scientifically_qualified":False, "binary_reward_registered":False,
            "official_code_commit":SOURCE_COMMIT,"expected_participants":sorted(expected_participants),
            "declared_population_count":len(expected_participants), "canonical_13_participant_count_matches":len(expected_participants)==13,
            "coverage":[{"ID":p,"regions":sorted(r["region"] for r in regional if r["ID"]==p)} for p in sorted(expected_participants)],
            "qc":{"input_rows":len(rows),"failed_fit0_rows":sum(not r["keep"] for r in processed),
                  "missing_raw":{m:sum(not math.isfinite(r[m+"_raw"]) for r in processed) for m in METRICS},
                  "filled_after_masking":{m:sum(r[m+"_filled"] for r in processed) for m in METRICS},
                  "remaining_missing":{m:sum(not math.isfinite(r[m]) for r in processed) for m in METRICS}},
            "parameter_window_audit":parameter_window_audit(processed),
            "parameter_window_audit_policy":{"identity":["ID","region","time"],
                "order":"ID/region/time; prospective stable-time sorting, not original CSV row positions",
                "smoothing":"centered five-row Gaussian sigma=1, clipped at group edges; metric-specific finite post-QC contributors",
                "scope":"supplied-table lineage only; no authentication of recording, montage, spectra or native estimator"},
            "participant_region":regional,"participant_context_pooled_time_rows":contexts,"participant_omnibus_pooled_time_rows":omnibus,
            "source_age_models":source_models,"source_region_level_INT_PAF_interaction":interaction,
            "source_context_INT_PAF_age_models":contextual_coupling,"source_pooled_region_PAF_INT_correlation":correlation,
            "prospective_participant_clustered_INT_PAF_interaction":clustered,"prospective_paired_hierarchy":prospective,
            "preserved_holds":HOLDS}


def evaluate_heldout(reference, submission):
    """Prospective participant-macro prediction errors, with a train-only baseline.

    Reference participant-region means are operator-side. Submissions must declare
    full participant partitions and exactly one prediction for every finite target.
    This validates declared split isolation, not provenance of a model's training.
    """
    if reference.get("task_id") != TASK_ID or reference.get("component") != "parameter_table_statistics":
        raise ContractError("Protected reference task/component mismatch")
    roster = validate_roster(reference.get("expected_participants"))
    records = reference.get("participant_region")
    if not isinstance(records,list) or not records:
        raise ContractError("Protected reference must contain participant-region records")
    targets, reference_keys, covered = {}, set(), set()
    for record in records:
        pid, region = record.get("ID"), record.get("region")
        if not isinstance(pid,str) or pid not in roster or region not in REGIONS:
            raise ContractError("Protected reference participant/region mismatch")
        key = (pid,region)
        if key in reference_keys:
            raise ContractError("Duplicate protected participant-region key")
        reference_keys.add(key)
        covered.add(pid)
        for metric in METRICS:
            if metric not in record:
                raise ContractError("Protected reference metric missing")
            value = _number(record[metric],metric,allow_nan=True)
            if math.isfinite(value):
                if (metric == "PAF" and not 2 <= value <= 14) or (metric == "INT" and value <= 0):
                    raise ContractError("Protected reference endpoint outside source domain")
                targets[(pid,region,metric)] = value
    if covered != set(roster):
        raise ContractError("Incomplete protected reference participant population")
    predictions, baseline, fold_ids, seen_test = {}, {}, set(), set()
    for fold in submission.get("folds",[]):
        fid = str(fold["fold"])
        train, test = validate_roster(fold["train_participants"]), validate_roster(fold["test_participants"])
        if fid in fold_ids or not train or not test or len(train)!=len(set(train)) or len(test)!=len(set(test)):
            raise ContractError("Duplicate fold/participant or empty partition")
        fold_ids.add(fid)
        if set(train)&set(test) or set(train)|set(test)!=set(roster) or seen_test&set(test):
            raise ContractError("Each fold must partition the roster and each test participant occur once")
        seen_test.update(test)
        expected_keys = {k for k in targets if k[0] in test}
        actual = set()
        for row in fold.get("predictions",[]):
            key = (str(row["ID"]),str(row["region"]),str(row["metric"]))
            if key not in expected_keys or key in actual or key in predictions:
                raise ContractError("Unexpected or duplicate prediction target")
            actual.add(key)
            predictions[key] = _number(row["prediction"],"prediction")
            training = [v for k,v in targets.items() if k[0] in train and k[1:]==key[1:]]
            if not training:
                raise ContractError("No train-only same-region baseline support")
            baseline[key] = _mean(training)
        if actual != expected_keys:
            raise ContractError("Missing held-out prediction targets")
    if seen_test != set(roster) or set(predictions)!=set(targets):
        raise ContractError("Incomplete held-out participant population")
    scores = {}
    for metric in METRICS:
        participant_scores = []
        for pid in roster:
            keys = [k for k in targets if k[0]==pid and k[2]==metric]
            if not keys:
                participant_scores.append({"ID":pid,"status":"no_finite_reference_target"})
                continue
            result = {"ID":pid,"status":"scored","region_count":len(keys)}
            for name, values in (("candidate",predictions),("train_only_region_mean",baseline)):
                errors = [values[k]-targets[k] for k in keys]
                squares = [error*error for error in errors]
                if not all(math.isfinite(v) for v in errors+squares):
                    raise ContractError("Nonfinite derived prediction error or squared error")
                result[name] = {"mae":_mean([abs(v) for v in errors]),"mse":_mean(squares)}
            participant_scores.append(result)
        scored = [r for r in participant_scores if r["status"]=="scored"]
        scores[metric] = {"participants":participant_scores,"scored_participant_count":len(scored)}
        for name in ("candidate","train_only_region_mean"):
            scores[metric][name] = {"participant_macro_mae":_mean([r[name]["mae"] for r in scored]),
                "root_participant_macro_mse":math.sqrt(_mean([r[name]["mse"] for r in scored])) if scored else float("nan")}
    return {"task_id":TASK_ID,"assessment":"prospective_grouped_prediction_component_not_frozen_benchmark_score",
            "scientifically_qualified":False,"scores":scores,"protected_reference_requirement":"operator keeps targets and excludes evaluation feedback from selection",
            "training_exposure_verified":False,"preserved_holds":HOLDS}


def json_safe(value):
    if isinstance(value,dict): return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [json_safe(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value): return None
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command",required=True)
    table = sub.add_parser("analyze")
    table.add_argument("--parameters",required=True,type=Path)
    table.add_argument("--packet",required=True,type=Path)
    table.add_argument("--output",required=True,type=Path)
    score = sub.add_parser("score-heldout")
    score.add_argument("--reference",required=True,type=Path)
    score.add_argument("--submission",required=True,type=Path)
    score.add_argument("--output",required=True,type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            packet = json.loads(args.packet.read_text())
            rows,digest = read_table(args.parameters,packet)
            result = analyze(rows,packet["expected_participants"])
            result["input_table_sha256"] = digest
            result["assessment_kind"] = packet["assessment_kind"]
        else:
            result = evaluate_heldout(json.loads(args.reference.read_text()),json.loads(args.submission.read_text()))
        args.output.write_text(json.dumps(json_safe(result),indent=2,allow_nan=False)+"\n")
    except (ContractError,KeyError,ValueError,OSError) as exc:
        parser.exit(2,f"Input rejected: {exc}\n")

if __name__ == "__main__":
    main()
