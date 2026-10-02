"""Prospective public FCSTAB numerical rules; pure functions, no source or file IO.

Input arrays are already identity-aligned by the caller. Source decoding and
authentication are deliberately outside this module. No historical bank is used.
"""
from __future__ import annotations

import math
import numpy as np
from scipy import stats

TAU = 1e-6
EPS64 = np.finfo(np.float64).eps
ZCAP = float(np.arctanh(.999999))
SCHEMES = ("forward", "reverse", "independent", "random")
CSV_COLUMNS = ("subject_id", "n_edges", "forward_first_half", "forward_second_half",
               "forward_delta", "reverse_delta", "independent_delta", "random_delta")


class ContractError(ValueError):
    pass


def numeric(value, ndim=None):
    a = np.asarray(value)
    if a.dtype.kind not in "fiu" or (ndim is not None and a.ndim != ndim):
        raise ContractError("numeric shape/dtype")
    a = a.astype(np.float64)
    if not np.isfinite(a).all():
        raise ContractError("nonfinite numeric input")
    return a


def mean(x):
    x = numeric(x, 1)
    if not x.size:
        raise ContractError("empty mean")
    if np.all(x == x[0]):
        return float(x[0])
    try:
        answer = math.fsum(map(float, x)) / x.size
    except OverflowError as exc:
        raise ContractError("nonfinite accurate mean") from exc
    if not math.isfinite(answer):
        raise ContractError("nonfinite accurate mean")
    return answer


def centered(x):
    x = numeric(x, 1)
    return x - mean(x)


def stable_l2(x):
    x = numeric(x, 1)
    scale = float(np.max(np.abs(x), initial=0))
    if scale == 0:
        return 0.0
    v = x / scale
    answer = scale * math.sqrt(math.fsum(float(t) * float(t) for t in v))
    if not math.isfinite(answer):
        raise ContractError("L2 overflow")
    return answer


def population_sd(x):
    x = numeric(x, 1)
    if not x.size:
        raise ContractError("empty SD")
    c = centered(x)
    scale = float(np.max(np.abs(c), initial=0))
    if scale == 0:
        return 0.0
    q = c / scale
    result = scale * math.sqrt(math.fsum(float(v)*float(v) for v in q)/x.size)
    if not math.isfinite(result):
        raise ContractError("nonfinite SD")
    return result


def pearson(a, b):
    """Scale-normalized Pearson; never multiply two tiny L2 norms."""
    a, b = numeric(a, 1), numeric(b, 1)
    if a.shape != b.shape or a.size < 2:
        return None
    ca, cb = centered(a), centered(b)
    na, nb = stable_l2(ca), stable_l2(cb)
    if na == 0 or nb == 0:
        return None
    value = math.fsum(float(x)*float(y) for x, y in zip(ca/na, cb/nb))
    if not math.isfinite(value) or abs(value) > 1 + 1e-12:
        raise ContractError("Pearson excursion")
    return min(1.0, max(-1.0, value))


def fisher_z(x):
    """T x common-ROI input; caller alone computes the cohort-global mask."""
    x = numeric(x, 2)
    if min(x.shape) < 2:
        raise ContractError("insufficient correlation shape")
    normalized = np.empty_like(x)
    for j in range(x.shape[1]):
        c = centered(x[:, j])
        n = stable_l2(c)
        if n == 0:
            raise ContractError("constant common ROI")
        normalized[:, j] = c/n
    r = (normalized.T @ normalized)[np.triu_indices(x.shape[1], 1)]
    if not np.isfinite(r).all() or np.any(np.abs(r) > 1+1e-12):
        raise ContractError("correlation excursion")
    return np.arctanh(np.clip(r, -.999999, .999999))


def scalar_close(a, b, atol=1e-6, rtol=1e-6):
    if not (math.isfinite(a) and math.isfinite(b)):
        raise ContractError("nonfinite receipt")
    if abs(a-b) > atol+rtol*abs(b):
        raise ContractError("scalar replay mismatch")


def edge_fidelity(accepted, source):
    a, b = numeric(accepted, 1), numeric(source, 1)
    if a.shape != b.shape or not a.size:
        raise ContractError("edge vector shape")
    if np.any(np.abs(a-b) > 1e-6+1e-6*np.abs(b)):
        raise ContractError("edge source fidelity")
    if np.any(np.abs(a) > ZCAP + 1e-6 + 1e-6*ZCAP):
        raise ContractError("Fisher cap")
    cb = centered(b)
    nb = stable_l2(cb)
    if nb > 0:
        ca = centered(a)
        if stable_l2(ca) == 0 or stable_l2((ca-cb)/nb) > TAU:
            raise ContractError("edge centered fidelity")
    return nb > 0


def reliability(a_first, a_second, s_first, s_second):
    a1, a2, s1, s2 = [numeric(x, 1) for x in (a_first,a_second,s_first,s_second)]
    if not (a1.shape == a2.shape == s1.shape == s2.shape):
        raise ContractError("reliability shape")
    active1, active2 = edge_fidelity(a1,s1), edge_fidelity(a2,s2)
    status = ("source_insufficient_edges" if a1.size < 2 else
              "source_constant" if not (active1 and active2) else "ok")
    if status != "ok":
        return {"edge_pearson":None,"edge_spearman":None,"status":status}
    r = pearson(a1,a2)
    rho = pearson(stats.rankdata(a1,method="average"),stats.rankdata(a2,method="average"))
    if r is None or rho is None:
        raise ContractError("accepted reliability support collapsed")
    return {"edge_pearson":r,"edge_spearman":rho,"status":"ok"}


def source_delta_resolution(delta, mean_abs_first, mean_abs_second):
    d, f, s = [numeric(x, 1) for x in (delta,mean_abs_first,mean_abs_second)]
    if not d.size or not (d.shape == f.shape == s.shape) or np.any(f<0) or np.any(s<0):
        raise ContractError("source anchor shape/absolute means")
    c = centered(d)
    C = stable_l2(c)
    scale = max(float(np.max(np.abs(d))),float(np.max(f)),float(np.max(s)))
    if scale == 0:
        B_scaled = C_scaled = 0.0
    else:
        B_scaled = stable_l2(8*EPS64*(f/scale+s/scale+np.abs(d)/scale))
        C_scaled = stable_l2(c/scale)
    B = scale*B_scaled
    if C == 0:
        status = "source_zero_variance"
    elif C_scaled*TAU <= B_scaled:
        status = "numerical_resolution"
    else:
        status = "active"
    return {"status":status,"source_centered_l2":C,"resolution_budget_l2":B,
            "scale":scale,"centered_l2_scaled":C_scaled,"budget_l2_scaled":B_scaled,
            "budget_underflow":bool(scale>0 and B_scaled>0 and B==0)}


def group_summary(accepted_delta, source_delta, mean_abs_first, mean_abs_second):
    a, b = numeric(accepted_delta,1), numeric(source_delta,1)
    if a.shape != b.shape or not a.size:
        raise ContractError("group shape")
    support = source_delta_resolution(b,mean_abs_first,mean_abs_second)
    if support["status"] == "active":
        if stable_l2((a-b)/support["source_centered_l2"]) > TAU:
            raise ContractError("delta full-error fidelity")
    n = a.size
    m = mean(a)
    sd = stable_l2(centered(a))/math.sqrt(n-1) if n>1 else None
    se = sd/math.sqrt(n) if sd is not None else None
    status = support["status"]
    if n<2:
        status = "insufficient_subjects"
    elif status == "active":
        status = "ok" if se is not None and se>0 and math.isfinite(se) else "numerical_underflow"
    out = {"n":int(n),"df":int(n-1),"delta_mean":m,"delta_sd":sd,"delta_se":se,
           "n_negative":int(np.count_nonzero(a<0)),"inference_status":status,
           "t":None,"p":None,"ci95_lo":None,"ci95_hi":None,"source_support":support}
    eq = {"margin_z":.05,"p_lower":None,"p_upper":None,"tost_p":None,
          "equivalent_within_margin":None,"status":status}
    if status == "ok":
        t = m/se
        q = float(stats.t.ppf(.975,n-1))*se
        lower = (m+.05)/se
        upper = (.05-m)/se
        if not all(map(math.isfinite,(t,q,m-q,m+q,lower,upper))):
            out["inference_status"] = eq["status"] = "numerical_nonfinite"
        else:
            out.update(t=t,p=float(2*stats.t.sf(abs(t),n-1)),ci95_lo=m-q,ci95_hi=m+q)
            pl, pu = float(stats.t.sf(lower,n-1)), float(stats.t.sf(upper,n-1))
            p = max(pl,pu)
            eq.update(p_lower=pl,p_upper=pu,tost_p=p,equivalent_within_margin=bool(p<.05))
    out["equivalence"] = eq
    return out


def select_sets(z, subject_ids, pairs):
    z = numeric(z,3)
    pairs = np.asarray(pairs)
    ids = list(subject_ids)
    if z.shape[:2] != (len(ids),3) or len(ids)<2 or len(ids)!=len(set(ids)) or not all(isinstance(s,str) for s in ids):
        raise ContractError("selection subject/segment shape")
    if pairs.dtype.kind not in "iu" or pairs.shape != (z.shape[2],2) or not len(pairs):
        raise ContractError("pair axis")
    pair_list = [tuple(map(int,p)) for p in pairs]
    if pair_list != sorted(set(pair_list)) or any(i>=j or i<1 for i,j in pair_list):
        raise ContractError("pairs not canonical unique i<j")
    E = len(pairs)
    k = max(1,E//10)
    rng = np.random.Generator(np.random.PCG64(0))
    result = {}
    for i,sid in enumerate(ids):
        others = [j for j in range(len(ids)) if i!=j]
        train = np.array([mean(z[others,2,e]) for e in range(E)])
        scores = {"forward":z[i,0],"reverse":z[i,1],"independent":train}
        sets = {key:np.sort(np.lexsort((pairs[:,1],pairs[:,0],-score))[:k])
                for key,score in scores.items()}
        sets["random"] = np.sort(rng.choice(E,size=k,replace=False))
        result[sid] = {"training_subject_ids":[ids[j] for j in others],
                       **{key+"_edge_indices":value.tolist() for key,value in sets.items()}}
    return result


def _receipt_number(value):
    if isinstance(value,(bool,np.bool_)):
        raise ContractError("Boolean numerical receipt")
    try:
        answer = float(value)
    except (TypeError,ValueError,OverflowError) as exc:
        raise ContractError("invalid numerical receipt") from exc
    if not math.isfinite(answer):
        raise ContractError("nonfinite numerical receipt")
    return answer


def analyze(accepted_z, source_z, subject_ids, pairs, accepted_rows=None, accepted_reliability=None):
    """Canonical-axis replay; artifacts/metadata authentication belongs to caller.

    Returned evidence means are receipts only. Group means use accepted CSV
    fields, and group inference uses accepted CSV deltas with source anchors.
    """
    a, b = numeric(accepted_z,3), numeric(source_z,3)
    if a.shape != b.shape:
        raise ContractError("source/accepted shape")
    ids = list(subject_ids)
    evidence = select_sets(a,ids,pairs)
    for i in range(len(ids)):
        for seg in range(3):
            edge_fidelity(a[i,seg],b[i,seg])
    generated = []
    anchors = {s:{"delta":[],"abs_first":[],"abs_second":[]} for s in SCHEMES}
    E = a.shape[2]
    k = max(1,E//10)
    for i,sid in enumerate(ids):
        ev = evidence[sid]
        row = {"subject_id":sid,"n_edges":E}
        ev["means"] = {}
        for scheme in SCHEMES:
            ix = ev[scheme+"_edge_indices"]
            first, second = mean(a[i,0,ix]),mean(a[i,1,ix])
            delta = second-first
            ev["means"][scheme] = {"first":first,"second":second}
            row[scheme+"_delta"] = delta
            if scheme == "forward":
                row.update(forward_first_half=first,forward_second_half=second)
            anchors[scheme]["delta"].append(mean(b[i,1,ix])-mean(b[i,0,ix]))
            anchors[scheme]["abs_first"].append(mean(np.abs(b[i,0,ix])))
            anchors[scheme]["abs_second"].append(mean(np.abs(b[i,1,ix])))
        ev["reliability"] = reliability(a[i,0],a[i,1],b[i,0],b[i,1])
        ev["reliability"]["overlap"] = len(set(ev["forward_edge_indices"]) & set(ev["reverse_edge_indices"]))/k
        generated.append(row)
    if accepted_rows is None:
        rows = generated
    else:
        if len(accepted_rows)!=len(ids) or any(not isinstance(r,dict) or set(r)!=set(CSV_COLUMNS) for r in accepted_rows):
            raise ContractError("CSV columns/cardinality")
        by_id = {r["subject_id"]:r for r in accepted_rows}
        if len(by_id)!=len(ids) or set(by_id)!=set(ids):
            raise ContractError("CSV subject identity")
        rows = []
        for expect in generated:
            given = by_id[expect["subject_id"]]
            if str(given["n_edges"]) != str(E):
                raise ContractError("CSV n_edges")
            row = {"subject_id":expect["subject_id"],"n_edges":E}
            for key in CSV_COLUMNS[2:]:
                row[key] = _receipt_number(given[key])
                scalar_close(row[key],expect[key])
            bound = sum(1e-6+1e-6*abs(expect[key]) for key in
                        ("forward_first_half","forward_second_half","forward_delta"))
            if abs(row["forward_delta"]-(row["forward_second_half"]-row["forward_first_half"]))>bound:
                raise ContractError("forward linear receipt coherence")
            rows.append(row)
    schemes = {}
    supports = {}
    equivalence = None
    for scheme in SCHEMES:
        src = anchors[scheme]
        group = group_summary([r[scheme+"_delta"] for r in rows],src["delta"],src["abs_first"],src["abs_second"])
        supports[scheme] = group.pop("source_support")
        eq = group.pop("equivalence")
        if scheme == "independent":
            equivalence = eq
        schemes[scheme] = group
    own_rel = {sid:evidence[sid]["reliability"] for sid in ids}
    if accepted_reliability is None:
        accepted_rel = own_rel
    else:
        if not isinstance(accepted_reliability,dict) or set(accepted_reliability)!=set(ids):
            raise ContractError("reliability receipt subjects")
        accepted_rel = {}
        for sid in ids:
            given, expected = accepted_reliability[sid],own_rel[sid]
            if not isinstance(given,dict) or set(given)!=set(expected) or given["status"]!=expected["status"]:
                raise ContractError("reliability receipt status/schema")
            accepted_rel[sid] = {"status":given["status"]}
            for key in ("overlap","edge_pearson","edge_spearman"):
                if expected[key] is None:
                    if given[key] is not None:
                        raise ContractError("source-inactive reliability must be null")
                    accepted_rel[sid][key] = None
                else:
                    value = _receipt_number(given[key])
                    if not ((0<=value<=1) if key=="overlap" else (-1<=value<=1)):
                        raise ContractError("reliability receipt range")
                    scalar_close(value,expected[key])
                    accepted_rel[sid][key] = value
    rel = {"overlap":mean([accepted_rel[s]["overlap"] for s in ids])}
    for name in ("edge_pearson","edge_spearman"):
        values = [accepted_rel[s][name] for s in ids]
        count = sum(x is not None for x in values)
        rel[name] = {"mean":mean(values) if count==len(ids) else None,
                     "n_defined":count,"n_undefined":len(ids)-count,
                     "status":"ok" if count==len(ids) else "undefined_member"}
    forward = {"first_half_mean":mean([r["forward_first_half"] for r in rows]),
               "second_half_mean":mean([r["forward_second_half"] for r in rows]),
               "change":schemes["forward"]["delta_mean"]}
    return {"n_edges":E,"k":k,"rows":rows,"evidence":evidence,
            "accepted_reliability":accepted_rel,
            "summaries":{"selection_schemes":schemes,"equivalence":equivalence,
                         "forward_top_decile_connectivity":forward,"reliability":rel},
            "support_diagnostics":supports}
