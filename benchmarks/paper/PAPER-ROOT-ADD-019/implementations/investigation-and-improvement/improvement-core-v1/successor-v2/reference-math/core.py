"""Exact-scope prospective ACh reference mathematics, pure standard library.

No I/O, scientific work or allocations occur on import. Authentic support,
schema/custody and a qualified execution/resource envelope belong to the caller.
Finite binary64 arithmetic is declared; this is not exact-real/correct rounding.
"""
import bisect
import math
import sys

STRATA = ("offer_CPIn", "reward_SideOff", "side_on", "opt_out")
LAMBDAS = (1e-6, 1e-4, 1e-2, 1.0, 100.0)
WIDTHS = (0.5, 1.0, 2.0)
VARIANTS = ("B", "D", "ACh", "F")
WEIGHT_TOL = 64 * sys.float_info.epsilon
RESIDUAL_TOL = 1e-10
NUMERIC_POLICY = {
    "scalar": "Python binary64", "sums": "math.fsum in original row/column order",
    "solver": "dense lower Cholesky, positive pivots, scaled infinity residual <= 1e-10",
    "underflow": "nonzero multiplication/division yielding zero and exp underflow fail",
    "weight_sum_absolute_tolerance": WEIGHT_TOL,
    "no_renormalization_jitter_pseudoinverse_retry_approximation": True,
    "forward_error_correct_rounding_native_parity_or_RSS_qualified": False,
}


class NumericFailure(ValueError):
    def __init__(self, code, detail):
        super().__init__(code + ": " + detail)
        self.code, self.detail = code, detail
    def as_record(self):
        return {"status": "undefined_numeric_or_support", "code": self.code,
                "detail": self.detail, "retry_or_weak_survivor_permitted": False}


def _need(condition, code, detail):
    if not condition:
        raise NumericFailure(code, detail)


def _num(value, name):
    _need(type(value) in (int, float), "numeric_type", name)
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise NumericFailure("numeric_conversion", name) from exc
    _need(math.isfinite(result), "nonfinite", name)
    return result


def _finite(value, name):
    _need(math.isfinite(value), "nonfinite_arithmetic", name)
    return value


def _sum(values):
    try:
        return _finite(math.fsum(values), "sum")
    except (OverflowError, ValueError) as exc:
        raise NumericFailure("sum_failure", str(exc)) from exc


def _mul(a, b):
    value = _finite(a * b, "product")
    _need(value != 0 or a == 0 or b == 0, "underflow", "nonzero product became zero")
    return value


def _div(a, b):
    _need(b != 0, "zero_denominator", "division")
    value = _finite(a / b, "division")
    _need(value != 0 or a == 0, "underflow", "nonzero quotient became zero")
    return value


def _dot(a, b):
    _need(len(a) == len(b), "shape", "dot product")
    return _sum(_mul(x, y) for x, y in zip(a, b))


def _seq(value, name):
    _need(type(value) in (list, tuple), "sequence", name + " must have a declared extent")
    return value


def _matrix(X, name="features"):
    _seq(X, name); _need(len(X) > 0, "empty_support", name)
    p = len(_seq(X[0], name + " row"))
    _need(all(type(row) in (list, tuple) and len(row) == p for row in X), "shape", name)
    return [[_num(x, name) for x in row] for row in X]


def _weights(weights, n):
    _seq(weights, "weights"); _need(len(weights) == n and n > 0, "shape", "weights")
    w = [_num(x, "weight") for x in weights]
    _need(all(x > 0 for x in w), "weight_support", "weights must be positive")
    _need(abs(_sum(w) - 1.0) <= WEIGHT_TOL, "weight_sum", "sum is not one; no renormalization")
    return w


def _strings(values, name):
    _seq(values, name)
    _need(all(type(x) is str and x for x in values) and len(set(values)) == len(values),
          "identity", name + " must be unique nonempty strings")
    return list(values)


def group_weights(rows, expected_animals, expected_sessions):
    """One head's complete admitted animal/session/row hierarchy; no stratum mixing."""
    animals = _strings(expected_animals, "expected animals")
    _need(animals and type(expected_sessions) is dict and set(expected_sessions) == set(animals),
          "group_support", "exact expected animals/session map")
    sessions = {a: _strings(expected_sessions[a], "eligible sessions") for a in animals}
    _need(all(sessions.values()), "empty_support", "required animal has no eligible session")
    _seq(rows, "rows"); _need(rows, "empty_support", "rows")
    counts = {(a, s): 0 for a in animals for s in sessions[a]}
    ids = []
    for row in rows:
        _need(type(row) is dict and {"row_id", "animal", "session"} <= set(row), "row_schema", "group row")
        ids.append(row["row_id"])
        _need(type(row["animal"]) is str and type(row["session"]) is str,
              "identity", "animal/session strings")
        key = (row["animal"], row["session"])
        _need(key in counts, "unexpected_group", str(key))
        counts[key] += 1
    _strings(ids, "row IDs")
    _need(all(counts.values()), "missing_group", "every expected eligible group needs all rows")
    w = [1.0 / (len(animals) * len(sessions[row["animal"]]) * counts[(row["animal"], row["session"])]) for row in rows]
    return _weights(w, len(rows))


def weighted_moments(values, weights):
    _seq(values, "values")
    y = [_num(x, "moment value") for x in values]
    w = _weights(weights, len(y))
    if all(x == y[0] for x in y):
        return {"mean": y[0], "variance": 0.0}
    mean = _dot(w, y)
    variance = _sum(_mul(wi, _mul(_finite(yi - mean, "center"), _finite(yi - mean, "center")))
                    for wi, yi in zip(w, y))
    _need(variance >= 0, "variance", "negative population moment")
    return {"mean": mean, "variance": variance}


def _raw_columns(values, observed, kinds):
    _seq(values, "values"); _seq(observed, "observed"); _seq(kinds, "kinds")
    _need(values and len(values) == len(observed), "shape", "feature observations")
    p = len(kinds)
    _need(all(k in ("continuous", "indicator") for k in kinds), "feature_kind", "unsupported feature type")
    _need(all(type(v) in (list, tuple) and len(v) == p for v in values) and
          all(type(o) in (list, tuple) and len(o) == p for o in observed), "shape", "column width")
    for row, flags in zip(values, observed):
        for j, (value, flag) in enumerate(zip(row, flags)):
            _need(type(flag) is bool, "observation_flag", "explicit boolean required")
            if kinds[j] == "indicator":
                _need(flag and type(value) in (int, float) and value in (0, 1), "indicator", "observed literal0/1")
            elif flag:
                _num(value, "observed continuous value")
            else:
                _need(value is None, "hidden_value", "absent values must be None, not a hidden numeric payload")
    return p


def fit_standardizer(values, observed, kinds, weights):
    p = _raw_columns(values, observed, kinds); w = _weights(weights, len(values))
    columns = []
    for j in range(p):
        if kinds[j] == "indicator":
            columns.append({"kind": "indicator"}); continue
        indices = [i for i in range(len(values)) if observed[i][j]]
        mass = _sum(w[i] for i in indices)
        if not indices:
            columns.append({"kind": "continuous", "observed_mass": 0.0, "mean": None, "variance": None,
                            "scale": None, "constant_training": False, "unobserved_training": True}); continue
        mean = _div(_sum(_mul(w[i], _num(values[i][j], "feature")) for i in indices), mass)
        variance = _div(_sum(_mul(w[i], _mul(_finite(values[i][j] - mean, "feature center"),
                                             _finite(values[i][j] - mean, "feature center"))) for i in indices), mass)
        if all(values[i][j] == values[indices[0]][j] for i in indices):
            mean, variance = float(values[indices[0]][j]), 0.0
        _need(variance >= 0, "variance", "observed feature variance")
        columns.append({"kind": "continuous", "observed_mass": mass, "mean": mean, "variance": variance,
                        "scale": math.sqrt(variance), "constant_training": variance == 0,
                        "unobserved_training": False})
    return {"schema": "ach_training_standardizer_v1", "feature_count": p, "columns": columns}


def transform_standardizer(state, values, observed):
    _need(type(state) is dict and state.get("schema") == "ach_training_standardizer_v1", "transform", "exact state schema")
    columns = state["columns"]
    _need(type(columns) is list and type(state["feature_count"]) is int and len(columns) == state["feature_count"],
          "shape", "sealed transform columns")
    kinds = [c["kind"] for c in columns]; _raw_columns(values, observed, kinds)
    result = []
    for row, flags in zip(values, observed):
        encoded = []
        for value, flag, column in zip(row, flags, columns):
            if column["kind"] == "indicator": encoded.append(float(value)); continue
            if column["unobserved_training"] or column["constant_training"] or not flag:
                encoded.append(0.0)
            else:
                encoded.append(_div(_finite(value - column["mean"], "query center"), column["scale"]))
        result.append(encoded)
    return result


def epoch_features(times, values, stratum):
    """Fixed accepted processed epochs, complete actual clocks, no extrapolation."""
    _need(stratum in STRATA, "stratum", "unknown window")
    _seq(times, "epoch times"); _seq(values, "epoch values")
    _need(len(times) == len(values) and len(times) >= 2, "epoch_shape", "complete paired clock/value arrays")
    t = [_num(x, "epoch clock seconds") for x in times]
    y = [_num(x, "epoch value") for x in values]
    _need(all(a < b for a, b in zip(t, t[1:])), "clock_order", "strict authentic sample order required")
    first, bins = (-6, 10) if stratum == "opt_out" else (-2, 12)
    edges = [(first + k) / 20.0 for k in range(bins + 1)]
    _need(t[0] <= edges[0] and t[-1] >= edges[-1], "unbracketed_epoch", "no extrapolation")
    def at(x):
        j = bisect.bisect_left(t, x)
        if j < len(t) and t[j] == x: return y[j]
        _need(0 < j < len(t), "unbracketed_boundary", "fixed edge")
        fraction = _div(x - t[j-1], t[j] - t[j-1])
        return _finite(y[j-1] + _mul(fraction, _finite(y[j] - y[j-1], "interpolation slope")), "interpolation")
    def integral(lo, hi):
        i, j = bisect.bisect_right(t, lo), bisect.bisect_left(t, hi)
        knots = [lo] + t[i:j] + [hi]
        vals = [at(lo)] + y[i:j] + [at(hi)]
        return _sum(_mul(_mul(0.5, _finite(a + b, "trapezoid values")), _finite(v-u, "clock interval"))
                    for u, v, a, b in zip(knots, knots[1:], vals, vals[1:]))
    means = [_div(integral(lo, hi), .05) for lo, hi in zip(edges, edges[1:])]
    total = integral(edges[0], edges[-1])
    return {"bins": means, "integral": total, "features": means + [total], "edges": edges}


def _indicator(x, name):
    _need(type(x) is int and x in (0, 1), "indicator", name + " must be literal integer0/1")
    return x


def build_variant(b, o_D, o_A, c_D, c_A, *, variant, n_D=None, n_A=None):
    _need(variant in VARIANTS, "variant", "B/D/ACh/F only")
    # Check withdrawn operands before inspecting any channel values/statistics.
    keep_d, keep_a = variant in ("D", "F"), variant in ("ACh", "F")
    _need(keep_d or n_D is None, "withdrawn_information", "DA block must not be supplied")
    _need(keep_a or n_A is None, "withdrawn_information", "ACh block must not be supplied")
    _need(not keep_d or n_D is not None, "missing_retained_block", "DA")
    _need(not keep_a or n_A is not None, "missing_retained_block", "ACh")
    _seq(b, "behavior"); behavior = [_num(x, "behavior") for x in b]
    _seq(o_D, "DA observation metadata"); _seq(o_A, "ACh observation metadata")
    d, a = _indicator(c_D, "DA channel"), _indicator(c_A, "ACh channel")
    od = [_indicator(x, "DA feature") for x in o_D]; oa = [_indicator(x, "ACh feature") for x in o_A]
    _need(d or not any(od), "availability", "absent DA has observed feature")
    _need(a or not any(oa), "availability", "absent ACh has observed feature")
    result = behavior + [d*x for x in behavior] + [a*x for x in behavior] + [d*a*x for x in behavior]
    for keep, block, flags in ((keep_d, n_D, od), (keep_a, n_A, oa)):
        if keep:
            _seq(block, "retained value block"); _need(len(block) == len(flags), "shape", "retained value/observation width")
            vals = [_num(x, "retained channel value") for x in block]
            _need(all(flag or value == 0 for value, flag in zip(vals, flags)), "absence_placeholder", "absent retained value must be zero")
            result.extend(vals)
    return result + [float(x) for x in od + oa + [d, a]]


def settings():
    ridge = [{"id": "ridge/lambda=" + format(lam, "g"), "family": "ridge", "lambda": lam, "width_multiplier": 0.0} for lam in LAMBDAS]
    rbf = [{"id": "rbf/width=" + format(width, "g") + "/lambda=" + format(lam, "g"),
            "family": "rbf", "lambda": lam, "width_multiplier": width} for width in WIDTHS for lam in LAMBDAS]
    return ridge + rbf


def _setting(setting):
    _need(type(setting) is dict and set(setting) == {"id", "family", "lambda", "width_multiplier"}, "setting", "exact frozen setting fields")
    _num(setting["lambda"], "lambda"); _num(setting["width_multiplier"], "width")
    _need(type(setting["id"]) is str and type(setting["family"]) is str, "setting", "literal setting identity")
    _need(setting in settings(), "setting", "not one of the twenty declared settings")
    return dict(setting)


def resource_plan(n, p, setting, limits):
    """Preventive internal scalar extents, not a physical RSS or caller-input cap."""
    _need(type(n) is int and n > 0 and type(p) is int and p >= 0, "extent", "n/p")
    chosen = _setting(setting)
    keys = {"max_rows", "max_features", "max_pairs", "max_matrix_elements", "max_live_float_slots"}
    _need(type(limits) is dict and set(limits) == keys and all(type(v) is int and v >= 0 for v in limits.values()),
          "limits", "all explicit nonnegative integer preventive limits required")
    pair_count = n*(n-1)//2 if chosen["family"] == "rbf" else 0
    matrix_elements = n*n if chosen["family"] == "rbf" else p*p
    live_slots = 3*n*p + 4*matrix_elements + pair_count + 32*(n+p) + 64
    required = dict(zip(("max_rows", "max_features", "max_pairs", "max_matrix_elements", "max_live_float_slots"),
                        (n, p, pair_count, matrix_elements, live_slots)))
    _need(all(required[k] <= limits[k] for k in keys), "preventive_extent_limit", str(required))
    return {"rows": n, "features": p, "pair_distances": pair_count, "matrix_elements": matrix_elements,
            "live_float_slots_upper_provision": live_slots, "selected_limits": dict(limits),
            "physical_RSS_caller_owned_inputs_runtime_or_workload_qualified": False}


def _distance_squared(x, y):
    return _sum(_mul(_finite(a-b, "coordinate difference"), _finite(a-b, "coordinate difference")) for a, b in zip(x, y))


def positive_distance_median(X, *, max_pairs):
    _seq(X, "features")
    _need(type(max_pairs) is int and max_pairs >= 0 and len(X)*(len(X)-1)//2 <= max_pairs,
          "pair_limit", "complete all-pair population must fit the declared extent")
    rows = _matrix(X); distances = []
    for i in range(len(rows)):
        for j in range(i+1, len(rows)):
            d2 = _distance_squared(rows[i], rows[j])
            if d2 > 0: distances.append(math.sqrt(d2))
    _need(distances, "undefined_RBF_bandwidth", "no strictly positive complete-pair distance")
    distances.sort(); n = len(distances)
    median = distances[n//2] if n % 2 else _mul(.5, _finite(distances[n//2-1] + distances[n//2], "median sum"))
    _need(median > 0, "undefined_RBF_bandwidth", "nonpositive median")
    return median


def _kernel(x, y, sigma):
    denominator = _mul(2.0, _mul(sigma, sigma))
    value = math.exp(-_div(_distance_squared(x, y), denominator))
    _need(value > 0 and math.isfinite(value), "RBF_underflow_or_nonfinite", "kernel cannot be silently clipped to zero")
    return value


def _factor(A):
    n = len(A); L = [[0.0]*n for _ in range(n)]
    for i in range(n):
        for j in range(i+1):
            value = _finite(A[i][j] - _sum(_mul(L[i][k], L[j][k]) for k in range(j)), "Cholesky remainder")
            if i == j:
                _need(value > 0, "Cholesky_pivot", "nonpositive pivot; no jitter or retry")
                L[i][j] = math.sqrt(value)
            else:
                L[i][j] = _div(value, L[j][j])
    return L


def _solve(A, L, rhs):
    n = len(A); y = [0.0]*n; x = [0.0]*n
    for i in range(n):
        y[i] = _div(_finite(rhs[i] - _sum(_mul(L[i][j], y[j]) for j in range(i)), "forward solve"), L[i][i])
    for i in range(n-1, -1, -1):
        x[i] = _div(_finite(y[i] - _sum(_mul(L[j][i], x[j]) for j in range(i+1,n)), "back solve"), L[i][i])
    residual = max((abs(_finite(_dot(row,x)-r, "linear residual")) for row,r in zip(A,rhs)), default=0.0)
    matrix_norm = max((_sum(abs(v) for v in row) for row in A), default=0.0)
    scale = _finite(_mul(matrix_norm, max(map(abs,x), default=0.0)) + max(map(abs,rhs), default=0.0), "residual scale")
    relative = _div(residual, scale) if scale else residual
    _need(relative <= RESIDUAL_TOL, "solve_residual", "declared backward residual test failed")
    return x, {"residual_inf":residual,"scaled_residual":relative,"limit":RESIDUAL_TOL}


def fit_head(X, seconds, weights, setting, row_ids, *, limits):
    _seq(X,"features"); _need(X, "empty_support", "head")
    p = len(_seq(X[0],"feature row")); n = len(X)
    plan = resource_plan(n,p,setting,limits)  # Before any internal pair/matrix allocation.
    rows = _matrix(X); ids = _strings(row_ids,"full training row IDs")
    _need(len(ids)==n, "shape", "full row IDs")
    _seq(seconds,"targets"); _need(len(seconds)==n, "shape", "complete targets")
    w = _weights(weights,n); times = [_num(x,"positive seconds") for x in seconds]
    _need(all(x>0 for x in times), "target_support", "positive finite times only; no clipping")
    logs = [math.log(x) for x in times]; target = weighted_moments(logs,w)
    _need(target["variance"]>0, "target_variance", "positive fitting-partition population variance required")
    target["scale"] = math.sqrt(target["variance"])
    z = [_div(_finite(x-target["mean"],"target center"),target["scale"]) for x in logs]
    chosen = _setting(setting); lam = chosen["lambda"]
    model = {"schema":"ach_complete_reference_head_v1","setting":chosen,"row_ids":ids,
             "feature_count":p,"target":target,"fit_resource_plan":plan,"numeric_policy":dict(NUMERIC_POLICY)}
    if chosen["family"] == "ridge":
        means = [_sum(_mul(wi,row[j]) for wi,row in zip(w,rows)) for j in range(p)]
        mean_z = _dot(w,z)
        centered = [[_finite(x-m,"feature center") for x,m in zip(row,means)] for row in rows]
        zc = [_finite(x-mean_z,"standard target center") for x in z]
        A = [[_sum(_mul(w[i],_mul(centered[i][j],centered[i][k])) for i in range(n)) + (lam if j==k else 0.0)
              for k in range(p)] for j in range(p)]
        rhs = [_sum(_mul(w[i],_mul(centered[i][j],zc[i])) for i in range(n)) for j in range(p)]
        beta, check = _solve(A,_factor(A),rhs)
        model.update({"intercept":_finite(mean_z-_dot(means,beta),"intercept"),"coefficients":beta,"solve_checks":[check]})
    else:
        median = positive_distance_median(rows,max_pairs=plan["pair_distances"])
        sigma = _mul(chosen["width_multiplier"],median)
        A = [[_finite(_kernel(rows[i],rows[j],sigma) + (_div(lam,w[i]) if i==j else 0.0),"regularized kernel")
              for j in range(n)] for i in range(n)]
        L = _factor(A)
        invz,c1 = _solve(A,L,z); inv1,c2 = _solve(A,L,[1.0]*n)
        denom = _sum(inv1); _need(denom>0,"RBF_intercept","positive denominator")
        intercept = _div(_sum(invz),denom)
        alpha,c3 = _solve(A,L,[_finite(x-intercept,"dual right-hand side") for x in z])
        constraint = abs(_sum(alpha)); alpha_scale = _sum(abs(x) for x in alpha)
        _need(constraint <= RESIDUAL_TOL*max(1.0,alpha_scale),"RBF_intercept_constraint","sum(alpha) residual")
        model.update({"intercept":intercept,"coefficients":alpha,"training_features":rows,"sigma":sigma,
                      "positive_pair_median":median,"solve_checks":[c1,c2,c3],"alpha_sum_residual":constraint})
    return model


def predict_head(model, X):
    _need(type(model) is dict and model.get("schema")=="ach_complete_reference_head_v1","model","exact sealed head schema")
    chosen = _setting(model["setting"]); rows = _matrix(X)
    _need(type(model["feature_count"]) is int and model["feature_count"] >= 0 and
          all(len(row)==model["feature_count"] for row in rows),"shape","query feature order/width")
    ids = _strings(model["row_ids"], "sealed full training row IDs")
    _seq(model["coefficients"], "sealed coefficients")
    coefficients = [_num(x,"sealed coefficient") for x in model["coefficients"]]
    intercept = _num(model["intercept"], "sealed intercept")
    target = model["target"]
    _need(type(target) is dict and set(target)=={"mean","variance","scale"}, "model", "target moment schema")
    mean = _num(target["mean"], "target mean")
    variance = _num(target["variance"], "target variance")
    scale = _num(target["scale"], "target scale")
    _need(variance>0 and scale>0 and scale==math.sqrt(variance), "model", "sealed positive population target scale")
    if chosen["family"]=="ridge":
        _need(len(coefficients)==model["feature_count"], "shape", "ridge coefficient width")
    else:
        training = _matrix(model["training_features"], "sealed RBF features")
        sigma = _num(model["sigma"], "sealed sigma")
        _need(sigma>0 and len(training)==len(coefficients)==len(ids) and
              all(len(row)==model["feature_count"] for row in training), "model", "complete RBF support and width")
    out=[]
    for row in rows:
        if chosen["family"]=="ridge": value = _finite(intercept+_dot(row,coefficients),"ridge prediction")
        else:
            value = _finite(intercept+_sum(_mul(a,_kernel(train,row,sigma))
                           for a,train in zip(coefficients,training)),"RBF prediction")
        out.append(_finite(mean+_mul(scale,value),"original log-time prediction"))
    return out


def validation_loss(predicted_log, positive_seconds, rows, expected_animal, expected_sessions, training_variance):
    w=group_weights(rows,[expected_animal],{expected_animal:expected_sessions})
    _seq(predicted_log,"predictions");_seq(positive_seconds,"targets")
    _need(len(predicted_log)==len(positive_seconds)==len(w),"shape","complete validation support")
    variance=_num(training_variance,"training variance");_need(variance>0,"target_variance","fitting variance only")
    terms=[]
    for p,t,wi in zip(predicted_log,positive_seconds,w):
        p=_num(p,"predicted log-time");t=_num(t,"positive time");_need(t>0,"target_support","positive time")
        delta=_finite(p-math.log(t),"validation error");terms.append(_mul(wi,_mul(delta,delta)))
    return _div(_sum(terms),variance)


def select_setting(loss_rows, validation_animals):
    animals=_strings(validation_animals,"inner held animals");_need(animals,"empty_support","validation animals")
    _seq(loss_rows,"complete inner loss rows");grid=settings()
    expected={(s["id"],a,k) for s in grid for a in animals for k in STRATA}
    cells={}
    for row in loss_rows:
        _need(type(row) is dict and set(row)=={"setting_id","animal","stratum","loss"},"loss_cell","exact finite cell schema")
        key=(row["setting_id"],row["animal"],row["stratum"])
        _need(key in expected and key not in cells,"loss_support","unexpected or repeated cell")
        loss=_num(row["loss"],"validation loss");_need(loss>=0,"validation_loss","nonnegative squared error")
        cells[key]=loss
    _need(set(cells)==expected,"incomplete_portfolio","no missing/failed setting, animal or stratum; no survivor selection")
    objectives={s["id"]:_div(_sum(_mul(.25,_sum(cells[(s["id"],a,k)] for k in STRATA)) for a in animals),len(animals)) for s in grid}
    winner=min(grid,key=lambda s:(objectives[s["id"]],-s["lambda"],-s["width_multiplier"],0 if s["family"]=="ridge" else 1))
    return {"setting":winner,"joint_loss":objectives[winner["id"]],"objectives":objectives,
            "complete_cells":len(cells),"validation_animals":animals,"strata":list(STRATA),"exact_equal_loss_ties_only":True}
