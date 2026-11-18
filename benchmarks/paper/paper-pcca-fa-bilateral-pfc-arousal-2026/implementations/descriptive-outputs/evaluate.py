"""Complete descriptive pCCA-FA output evaluator; no fitting or execution authority.

See METHOD.md for exact source mapping and limits. Standard library only.
"""
import argparse
import hashlib
import json
import math
import os
import stat
from pathlib import Path

TASK = "paper-pcca-fa-bilateral-pfc-arousal-2026"
GROUPS = ("across", "within_left", "within_right")
MODES = ("all", "one")
ANIMALS = ("Pe", "Wa", "Sa")
MAX_RECORD = 2 * 1024 * 1024
MAX_SUBMISSION = 256 * 1024 * 1024
MAX_MANIFEST = 16 * 1024 * 1024


class Invalid(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise Invalid(reason)


def keys(obj, names, label):
    require(isinstance(obj, dict) and set(obj) == set(names), label + ": keys")


def number(x):
    require(type(x) in (int, float), "number required (booleans forbidden)")
    try:
        y = float(x)
    except (OverflowError, ValueError):
        raise Invalid("unrepresentable number") from None
    require(math.isfinite(y), "nonfinite number")
    return y


def finite(x):
    require(math.isfinite(x), "unrepresentable computed metric")
    return x


def vector(x, n):
    require(isinstance(x, list) and len(x) == n, "vector support mismatch")
    return [number(v) for v in x]


def ids(x, minimum=1):
    require(isinstance(x, list) and minimum <= len(x) <= 100000, "identity support")
    require(all(type(v) is str and 0 < len(v) <= 256 for v in x), "identity type")
    require(len(set(x)) == len(x), "duplicate identity")
    return x


def mean(x):
    return finite(math.fsum(v / len(x) for v in x))


def variance(x):
    m = mean(x)
    return finite(math.fsum((v - m) ** 2 / len(x) for v in x))


def percentile(x, p):
    """NumPy's default linear interpolation, without a NumPy dependency."""
    y = sorted(x)
    h = (len(y) - 1) * p
    i = int(h)
    return y[i] if i == len(y) - 1 else y[i] + (h - i) * (y[i + 1] - y[i])


def r2(y, prediction):
    require(len(y) >= 2 and len(y) == len(prediction), "R2 support mismatch")
    m = mean(y)
    scale = max(abs(v - m) for v in y)
    require(scale > 0, "constant pupil target: no invented R2")
    den = math.fsum(((v - m) / scale) ** 2 for v in y)
    num = math.fsum(((p - v) / scale) ** 2 for p, v in zip(prediction, y))
    return finite(1 - num / den)


def _betacf(a, b, x):
    """Modified Lentz continued fraction for the regularized beta integral."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1 / d
    h = d
    for m in range(1, 1001):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)),
                   -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d, c = 1 + aa * d, 1 + aa / c
            if abs(d) < tiny:
                d = tiny
            if abs(c) < tiny:
                c = tiny
            d = 1 / d
            delta = d * c
            h *= delta
        if abs(delta - 1) <= 4e-15:
            return h
    raise Invalid("beta integral failed to converge")


def _ibeta(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1 - bt * _betacf(b, a, 1 - x) / b


def t_greater(differences):
    """One-sample t on complete paired contrasts; area pairing is historical."""
    n = len(differences)
    require(n >= 2, "t support")
    scale = max(abs(v) for v in differences)
    if scale == 0:
        return {"n": n, "mean_difference": 0.0, "t": None, "p": None,
                "status": "undefined_zero_contrast_variance", "log10_p": None}
    y = [v / scale for v in differences]
    m = mean(y)
    ss = math.fsum((v - m) ** 2 for v in y)
    if ss == 0:
        p = 0.0 if m > 0 else 1.0
        return {"n": n, "mean_difference": mean(differences), "t": None,
                "p": p, "status": "constant_nonzero_contrast_limit",
                "log10_p": None if p == 0 else 0.0}
    t = finite(m / math.sqrt(ss / (n * (n - 1))))
    # Avoid squaring a possibly huge t.
    u = math.sqrt(n - 1) / math.hypot(math.sqrt(n - 1), t)
    tail = 0.5 * _ibeta((n - 1) / 2, 0.5, u * u)
    p = tail if t >= 0 else 1 - tail
    require(0 <= p <= 1, "invalid t probability")
    return {"n": n, "mean_difference": mean(differences), "t": t, "p": p,
            "status": "finite" if p > 0 else "tail_underflow",
            "log10_p": math.log10(p) if p > 0 else None}


def spectrum(loadings):
    """Eigenvalues of L'L, equal to nonzero eigenvalues of LL'.

    Cyclic Jacobi on at most 15 factors; no native library or fit. Returned
    energies are normalized to avoid gratuitous unit-dependent overflow.
    """
    d = len(loadings[0])
    scale = max(abs(v) for row in loadings for v in row)
    require(scale > 0, "nonzero selected loading dimension has zero energy")
    z = [[v / scale for v in row] for row in loadings]
    a = [[math.fsum(row[i] * row[j] for row in z) for j in range(d)] for i in range(d)]
    trace = math.fsum(a[i][i] for i in range(d))
    for _ in range(100):
        off = max((abs(a[i][j]) for i in range(d) for j in range(i + 1, d)), default=0)
        if off <= trace * 2e-15:
            vals = sorted((max(0.0, a[i][i]) for i in range(d)), reverse=True)
            total = math.fsum(vals)
            vals = [v / total for v in vals]
            for k in range(d):
                if math.fsum(vals[:k + 1]) >= 0.95 - 1e-9:
                    return vals, k + 1
            raise Invalid("spectrum threshold")
        for p in range(d):
            for q in range(p + 1, d):
                if abs(a[p][q]) <= trace * 2e-16:
                    continue
                tau = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = math.copysign(1, tau) / (abs(tau) + math.hypot(1, tau))
                c = 1 / math.hypot(1, t)
                s = t * c
                app, aqq, apq = a[p][p], a[q][q], a[p][q]
                for k in range(d):
                    if k not in (p, q):
                        ap, aq = a[k][p], a[k][q]
                        a[k][p] = a[p][k] = c * ap - s * aq
                        a[k][q] = a[q][k] = s * ap + c * aq
                a[p][p], a[q][q] = app - t * apq, aqq + t * apq
                a[p][q] = a[q][p] = 0.0
    raise Invalid("spectrum failed to converge")


def gram(a, b):
    return [[finite(math.fsum(x * y for x, y in zip(ra, rb))) for rb in b] for ra in a]


def matrix(obj, rows, columns):
    require(isinstance(obj, list) and len(obj) == rows, "matrix row support")
    return [vector(row, columns) for row in obj]


def model(record, support):
    keys(record, ("kind", "session", "channels", "dimensions", "loadings", "noise",
                  "selected_cv_loglik", "final_loglik"), "model")
    require(record["kind"] == "model" and record["session"] == support["id"], "model identity")
    require(record["channels"] == support["channels"], "channel identity/order")
    dims = record["dimensions"]
    keys(dims, ("across", "left", "right"), "dimensions")
    n1, n2 = (len(support["channels"][k]) for k in ("left", "right"))
    for k, ceiling in (("across", min(n1, n2, 15)), ("left", min(n1, 15)), ("right", min(n2, 15))):
        require(type(dims[k]) is int and 1 <= dims[k] <= ceiling, "selected dimension")
    keys(record["loadings"], ("W_left", "W_right", "L_left", "L_right"), "loadings")
    a, b, c, d = [matrix(record["loadings"][k], n, dim) for k, n, dim in
                  (("W_left", n1, dims["across"]), ("W_right", n2, dims["across"]),
                   ("L_left", n1, dims["left"]), ("L_right", n2, dims["right"]))]
    keys(record["noise"], ("left", "right"), "noise")
    noise = {h: vector(record["noise"][h], n) for h, n in (("left", n1), ("right", n2))}
    require(all(v >= 0 for arr in noise.values() for v in arr), "negative noise variance")
    vector(record["selected_cv_loglik"], 10)
    number(record["final_loglik"])
    result = {"id": support["id"], "dimensions": dims, "areas": {}}
    for h, w, l in (("left", a, c), ("right", b, d)):
        cw, cl = gram(w, w), gram(l, l)
        total = [finite(cw[i][i] + cl[i][i] + noise[h][i]) for i in range(len(w))]
        require(all(v > 0 for v in total), "zero total variance")
        fractions = {"across": [100 * cw[i][i] / total[i] for i in range(len(w))],
                     "within": [100 * cl[i][i] / total[i] for i in range(len(w))],
                     "private": [100 * noise[h][i] / total[i] for i in range(len(w))]}
        sw, dw = spectrum(w)
        sl, dl = spectrum(l)
        result["areas"][h] = {"fractions_percent": fractions,
                               "mean_percent": {k: mean(v) for k, v in fractions.items()},
                               "spectrum_fraction": {"across": sw, "within": sl},
                               "dshared": {"across": dw, "within": dl},
                               "covariance": {"across": cw, "within": cl}, "noise": noise[h]}
    result["cross_covariance"] = gram(a, b)
    return result


def no_duplicates(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, "duplicate JSON key")
        result[k] = v
    return result


def decode(raw):
    try:
        return json.loads(raw, object_pairs_hook=no_duplicates,
                          parse_constant=lambda x: (_ for _ in ()).throw(Invalid("nonfinite JSON")))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Invalid("invalid JSON") from exc


def read_regular(path, cap):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        require(stat.S_ISREG(os.fstat(f.fileno()).st_mode), "regular file required")
        require(os.fstat(f.fileno()).st_size <= cap, "file exceeds byte ceiling")
        raw = f.read(cap + 1)
        require(len(raw) <= cap, "growing file exceeds byte ceiling")
    return raw


def records(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        require(stat.S_ISREG(os.fstat(f.fileno()).st_mode), "regular submission required")
        require(os.fstat(f.fileno()).st_size <= MAX_SUBMISSION, "submission byte ceiling")
        size = 0
        while True:
            raw = f.readline(MAX_RECORD + 1)
            if not raw:
                break
            size += len(raw)
            require(size <= MAX_SUBMISSION and len(raw) <= MAX_RECORD, "submission/record byte ceiling")
            require(raw.endswith(b"\n") and raw.strip(), "JSONL newline/blank record")
            yield decode(raw)


def manifest(raw, roster):
    obj = decode(raw)
    keys(obj, ("task", "schema", "preparation_binding", "sessions"), "manifest")
    require(obj["task"] == TASK and obj["schema"] == "pcca-prepared-support-v1", "manifest schema")
    binding = obj["preparation_binding"]
    require(type(binding) is str and len(binding) == 64 and all(v in "0123456789abcdef" for v in binding), "preparation hash")
    require(isinstance(obj["sessions"], list) and len(obj["sessions"]) == 42, "all42 sessions required")
    require(all(isinstance(r, dict) for r in obj["sessions"]), "session object required")
    require([r.get("id") for r in obj["sessions"]] == roster, "exact sorted42-session roster")
    support, pupil = {}, {}
    for r in obj["sessions"]:
        keys(r, ("id", "channels", "trial_ids", "fast_pupil"), "session support")
        keys(r["channels"], ("left", "right"), "hemispheres")
        for h in ("left", "right"):
            ids(r["channels"][h])
            require(len(r["channels"][h]) <= 512, "engineering channel ceiling; never subsample")
        ids(r["trial_ids"], 2)
        y = vector(r["fast_pupil"], len(r["trial_ids"]))
        support[r["id"]] = r
        pupil[r["id"]] = y
    included, diagnostics = [], {}
    for animal, expected in zip(ANIMALS, (16, 9, 16)):
        ss = [s for s in roster if s.startswith(animal)]
        vv = [variance(pupil[s]) for s in ss]
        q1, q3 = percentile(vv, .25), percentile(vv, .75)
        lower, upper = q1 - 2 * (q3 - q1), q3 + 2 * (q3 - q1)
        keep = [s for s, v in zip(ss, vv) if lower <= v <= upper]
        require(len(keep) == expected, "historical pupil support mismatch; do not force exclusion")
        included.extend(keep)
        diagnostics[animal] = {"variance_ddof": 0, "q1": q1, "q3": q3, "lower": lower,
                               "upper": upper, "variance_by_session": dict(zip(ss, vv)),
                               "included": keep, "excluded": [s for s in ss if s not in keep]}
    included.sort()
    require("Sa191206" in included, "fixed pupil example missing")
    normalized = {}
    for s in included:
        y, m, sd = pupil[s], mean(pupil[s]), math.sqrt(variance(pupil[s]))
        # The original driver applies its complete-cohort variance fence first.
        # An excluded constant session still belongs to the42 neural models,
        # but never needs a pupil z-score. Retained constants remain invalid.
        require(sd > 0, "constant retained pupil target: no invented z-score")
        normalized[s] = [(v - m) / sd for v in y]
    return support, included, normalized, diagnostics


def prediction(record, support, source, target, pair):
    names = ("kind", "source", "target", "source_trial_ids", "target_trial_ids", "predictions") if pair else ("kind", "session", "trial_ids", "predictions")
    keys(record, names, "prediction")
    n = min(len(support[source]["trial_ids"]), len(support[target]["trial_ids"]))
    if pair:
        require(record["kind"] == "pair" and record["source"] == source and record["target"] == target, "ordered pair identity")
        require(record["source_trial_ids"] == support[source]["trial_ids"][:n]
                and record["target_trial_ids"] == support[target]["trial_ids"][:n], "pair prefix lineage")
    else:
        require(record["kind"] == "pupil" and record["session"] == target
                and record["trial_ids"] == support[target]["trial_ids"], "pupil trial identity")
    out = {}
    keys(record["predictions"], MODES, "prediction modes")
    for mode in MODES:
        keys(record["predictions"][mode], GROUPS, "prediction groups")
        out[mode] = {g: vector(record["predictions"][mode][g], n) for g in GROUPS}
    return out


def discrepancy(a, b):
    """Invariant output differences; never compare latent coordinates directly."""
    if isinstance(a, dict):
        require(set(a) == set(b), "reference metric structure")
        return {k: discrepancy(a[k], b[k]) for k in a}
    if isinstance(a, list):
        require(len(a) == len(b), "reference numeric support")
        return [discrepancy(x, y) for x, y in zip(a, b)]
    return finite(abs(a - b))


def summary(models, pupil, pairs):
    out = {}
    for animal in ("pooled",) + ANIMALS:
        ss = [s for s in models if animal == "pooled" or s.startswith(animal)]
        sv_a, sv_w, ds_a, ds_w = [], [], [], []
        for s in ss:
            for h in ("left", "right"):
                a = models[s]["areas"][h]
                sv_a.append(a["mean_percent"]["across"]); sv_w.append(a["mean_percent"]["within"])
                ds_a.append(a["dshared"]["across"]); ds_w.append(a["dshared"]["within"])
        pss = [s for s in pupil if animal == "pooled" or s.startswith(animal)]
        row = {"sessions": len(ss), "areas": len(sv_a),
               "P01": {"across_percent": mean(sv_a), "within_percent": mean(sv_w),
                       "paired_greater": t_greater([x - y for x, y in zip(sv_a, sv_w)])},
               "P02": {"across_dshared": mean(ds_a), "within_dshared": mean(ds_w),
                       "paired_greater": t_greater([x - y for x, y in zip(ds_a, ds_w)])}}
        for mode, key in (("all", "P03"), ("one", "P04")):
            diffs = [pupil[s][mode]["across"] - pupil[s][mode][g]
                     for s in pss for g in ("within_left", "within_right")]
            row[key] = {"sessions": len(pss), "means": {g: mean([pupil[s][mode][g] for s in pss]) for g in GROUPS},
                        "paired_greater": t_greater(diffs)}
        if animal != "pooled":
            pr = [r for r in pairs if r["source"].startswith(animal)]
            row["P05"] = {"ordered_pairs": len(pr), "intervals": {
                mode: {g: [percentile([r["r2"][mode][g] for r in pr], q) for q in (.025, .975)] for g in GROUPS}
                for mode in MODES}}
        out[animal] = row
    return out


def published_differences(aggregates, models, pupil):
    """Rounded paper numbers are contextual discrepancies, never pass floors."""
    pvalues = {
        "P01": {"pooled": 2.6e-7, "Pe": .00048, "Wa": .40, "Sa": 4.2e-6},
        "P02": {"pooled": 3.1e-6, "Pe": .0013, "Wa": .32, "Sa": 9e-5},
        "P03": {"pooled": 1.3e-30, "Pe": 6.7e-12, "Wa": 1.3e-8, "Sa": 2.7e-21},
        "P04": {"pooled": 4.3e-22},
    }
    result = {"absolute_log10_p_difference": {}, "examples": {}}
    for endpoint, strata in pvalues.items():
        result["absolute_log10_p_difference"][endpoint] = {}
        for stratum, printed in strata.items():
            observed = aggregates[stratum][endpoint]["paired_greater"]["log10_p"]
            result["absolute_log10_p_difference"][endpoint][stratum] = (
                None if observed is None else abs(observed - math.log10(printed)))
    result["examples"]["P06"] = {
        h: {k: abs(models["Pe180726"]["areas"][h]["mean_percent"][k] - v)
            for k, v in values.items()}
        for h, values in (("right", {"across": 14.97, "within": 5.65}),
                          ("left", {"across": 17.47, "within": 7.47}))}
    result["examples"]["P07"] = {g: abs(pupil["Sa191206"]["all"][g] - v) for g, v in
                                  (("across", .35), ("within_right", .013), ("within_left", .052))}
    return result


def evaluate(support_raw, candidate_path, reference_path=None):
    roster_obj = decode(read_regular(Path(__file__).with_name("ROSTER.json"), 65536))
    roster = roster_obj["session_ids"]
    require(len(roster) == 42 and len(set(roster)) == 42, "installed roster")
    sup, included, targets, selection = manifest(support_raw, roster)
    digest = hashlib.sha256(support_raw).hexdigest()
    streams = [iter(records(candidate_path))]
    if reference_path is not None:
        streams.append(iter(records(reference_path)))
    def pull():
        try:
            return [next(s) for s in streams]
        except StopIteration:
            raise Invalid("missing record: complete output required") from None
    try:
        for header in pull():
            require(header == {"kind": "header", "schema": "pcca-output-v1", "task": TASK,
                               "support_sha256": digest}, "submission header binding")
        models, pupil, pairs, errors = {}, {}, [], {"models": {}, "pupil": {}, "pairs": []}
        for s in roster:
            parsed = [model(r, sup[s]) for r in pull()]
            models[s] = parsed[0]
            if len(parsed) == 2:
                errors["models"][s] = {}
                for h in ("left", "right"):
                    errors["models"][s][h] = {k: discrepancy(parsed[0]["areas"][h][k], parsed[1]["areas"][h][k])
                                              for k in ("covariance", "noise", "mean_percent", "dshared")}
                errors["models"][s]["cross_covariance"] = discrepancy(parsed[0]["cross_covariance"], parsed[1]["cross_covariance"])
        for source, target, pair in ([(s, s, False) for s in included]
                                     + [(s, t, True) for s in included for t in included if s != t and s[:2] == t[:2]]):
            parsed = [prediction(r, sup, source, target, pair) for r in pull()]
            n = len(parsed[0]["all"]["across"])
            scores = {mode: {g: r2(targets[target][:n], parsed[0][mode][g]) for g in GROUPS} for mode in MODES}
            if pair:
                pairs.append({"source": source, "target": target, "n": n, "r2": scores})
            else:
                pupil[target] = scores
            if len(parsed) == 2:
                delta = {mode: {g: finite(math.fsum((a - b) ** 2 / n for a, b in zip(parsed[0][mode][g], parsed[1][mode][g])))
                                for g in GROUPS} for mode in MODES}
                if pair:
                    errors["pairs"].append({"source": source, "target": target, "prediction_mse": delta})
                else:
                    errors["pupil"][target] = delta
        end = object()
        for stream in streams:
            require(next(stream, end) is end, "extra output record")
        aggregates = summary(models, pupil, pairs)
        require(len(pairs) == 552, "complete ordered-pair support")
        return {"task": TASK, "schema": "pcca-descriptive-evaluation-v1", "support_sha256": digest,
                "status": "complete_output_evaluated_not_scientific_reproduction_qualified",
                "reference_present": reference_path is not None, "numerical_pass": None,
                "pupil_selection": selection, "models": models, "pupil_r2": pupil, "pairs": pairs,
                "aggregates": aggregates, "reference_absolute_differences": errors if reference_path else None,
                "fixed_examples": {"P06": models["Pe180726"], "P07": pupil["Sa191206"]},
                "published_p_and_example_discrepancies": published_differences(aggregates, models, pupil),
                "published_mean_absolute_differences": {
                    "P01_across": abs(aggregates["pooled"]["P01"]["across_percent"] - 11.50),
                    "P01_within": abs(aggregates["pooled"]["P01"]["within_percent"] - 7.66),
                    "P02_across": abs(aggregates["pooled"]["P02"]["across_dshared"] - 5.41),
                    "P02_within": abs(aggregates["pooled"]["P02"]["within_dshared"] - 4.06),
                    "P03": {g: abs(aggregates["pooled"]["P03"]["means"][g] - v) for g, v in
                            (("across", .25), ("within_right", .038), ("within_left", .030))}},
                "limits": ["Historical descriptive fitted R2; no protected improvement score.",
                           "Native preparation, complete dimension search, model fitting and reference provenance are external obligations.",
                           "Output consistency and published rounded discrepancies do not prove reproduction or method compliance.",
                           "Area-level historical t tests are not independent-animal inference."]}
    finally:
        for stream in streams:
            stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--support", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--reference")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = evaluate(read_regular(args.support, MAX_MANIFEST), args.candidate, args.reference)
        raw = (json.dumps(result, sort_keys=True, allow_nan=False) + "\n").encode()
        with open(args.output, "xb") as f:
            f.write(raw)
    except (Invalid, ArithmeticError, OSError) as exc:
        parser.exit(2, "evaluation refused: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
