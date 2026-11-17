"""Evaluator-side NeuralFlow likelihood components; no model fitting or runner.

Eq.15: sum(log intensity at spikes) - integrated intensity.
Eq.16: normalized log density = joint log density - reaction-time log density.
No historical spline boundary condition or missing clock is inferred here.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
import math

from neuralflow_adapter import ContractError, validate_roster

CONDITIONS = {"Left_easy", "Left_hard", "Right_easy", "Right_hard"}
POLICY = "explicit-cubic-exact-integral-v1"
MAX_VECTOR = 100_000


def fields(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        raise ContractError(f"{label}: exact fields required")


def number(value, label):
    if type(value) not in (int, float):
        raise ContractError(f"{label}: finite number required")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ContractError(f"{label}: unrepresentable number") from exc
    if not math.isfinite(value):
        raise ContractError(f"{label}: finite number required")
    return value


def integer(value, label):
    if type(value) is not int or value < 0:
        raise ContractError(f"{label}: nonnegative integer required")
    return value


def vector(value, label, minimum=0):
    if type(value) is not list or not minimum <= len(value) <= MAX_VECTOR:
        raise ContractError(f"{label}: bounded list required")
    return [number(x, label) for x in value]


def case_key(row, with_unit=True):
    pid = row["population_id"]
    if type(pid) is not str or not 1 <= len(pid) <= 100:
        raise ContractError("invalid population identity")
    key = (pid,) + tuple(integer(row[k], k) for k in
                        ("subject_id", "session_id", "trial_id"))
    return key + (integer(row["unit_id"], "unit_id"),) if with_unit else key


def build_lono_index(projection, roster):
    """Private complete-cohort index. Never release this object to a candidate.

    Each invocation of public_view exposes ONE query. A future runner must use
    fresh state for each held-unit role: combining views reveals hidden spikes.
    """
    populations = validate_roster(roster)
    if (projection.get("schema") != "neuralflow-row-projection-v1"
            or projection.get("source_clock") not in
            ("absolute_seconds", "stimulus_relative_seconds")
            or projection.get("endpoint_policy") not in
            ("closed", "left_closed_right_open")):
        raise ContractError("authenticated explicit source clock/endpoints required")
    endpoint = projection["endpoint_policy"]
    episodes, support = {}, defaultdict(set)
    for row in projection["episodes"]:
        key = case_key(row, False)
        if key in episodes or key[0] not in populations:
            raise ContractError("duplicate/unknown population trial")
        pop = populations[key[0]]
        if key[1:3] != (pop["subject_id"], pop["session_id"]):
            raise ContractError("population/session mismatch")
        condition = row["stimulus_condition"]
        if condition not in CONDITIONS:
            raise ContractError("unknown stimulus condition")
        duration = number(row["duration_seconds"], "duration")
        if duration <= 0:
            raise ContractError("duration must be positive")
        source_units = row["spikes"]
        if type(source_units) is not list or len(source_units) != len(pop["uids"]):
            raise ContractError("complete population unit axis required")
        units = []
        for dense, (unit, expected) in enumerate(zip(source_units, pop["uids"])):
            if (type(unit.get("unit_id")) is not int or unit["unit_id"] != expected
                    or type(unit.get("dense_neuron_index")) is not int
                    or unit["dense_neuron_index"] != dense):
                raise ContractError("original unit order/dense index mismatch")
            spikes = vector(unit["spike_seconds_from_window_start"], "spikes")
            if (any(a > b for a, b in zip(spikes, spikes[1:]))
                    or any(t < 0 or t > duration or
                           (endpoint == "left_closed_right_open" and t == duration)
                           for t in spikes)):
                raise ContractError("spike order or explicit endpoint violation")
            units.append({"unit_id": expected, "dense_neuron_index": dense,
                          "spike_seconds_from_window_start": spikes})
        # Whitelist: chosen_side, fit flags and arbitrary nested metadata vanish.
        episodes[key] = {"population_id": key[0], "subject_id": key[1],
                         "session_id": key[2], "trial_id": key[3],
                         "stimulus_condition": condition, "duration_seconds": duration,
                         "spikes": units}
        support[key[0]].add(condition)
    if set(support) != set(populations) or any(v != CONDITIONS for v in support.values()):
        raise ContractError("all30 populations and four conditions required")
    return {"populations": populations, "episodes": episodes, "endpoint_policy": endpoint}


def public_view(index, key):
    """One target-free LONO query; held unit stays named but its spikes do not."""
    if type(key) is not tuple or len(key) != 5:
        raise ContractError("complete population/trial/unit key required")
    case_key(dict(zip(("population_id","subject_id","session_id","trial_id","unit_id"),key)))
    episode = index["episodes"].get(key[:4])
    if episode is None or key[4] not in index["populations"][key[0]]["uids"]:
        raise ContractError("unknown held-neuron case")
    clean = {k: episode[k] for k in ("population_id", "subject_id", "session_id",
                                    "trial_id", "stimulus_condition", "duration_seconds")}
    clean.update(schema="neuralflow-one-lono-query-v1", held_unit_id=key[4],
                 endpoint_policy=index["endpoint_policy"],
                 spikes=[{"unit_id": u["unit_id"], "dense_neuron_index": u["dense_neuron_index"],
                          "spike_seconds_from_window_start": list(u["spike_seconds_from_window_start"])}
                         for u in episode["spikes"] if u["unit_id"] != key[4]])
    return clean


def _poly(c, x):
    return ((c[3] * x + c[2]) * x + c[1]) * x + c[0]


def _minimum(c, width):
    # Scale x to [0,1] before solving the derivative to avoid small-bin ratios.
    # Multiply coefficients first: width**2 or width**3 can underflow/overflow
    # even when the scaled coefficient is finite and nonzero.
    b = c[1] * width
    cc = (c[2] * width) * width
    d = ((c[3] * width) * width) * width
    if not all(math.isfinite(x) for x in (b, cc, d)):
        raise ContractError("unrepresentable cubic segment")
    candidates = [0.0, 1.0]
    scale = max(abs(d), abs(cc), abs(b))
    if scale:
        # Normalize BEFORE multiplying by degree: finite d can overflow at3*d.
        a, bb, c0 = 3*(d/scale), 2*(cc/scale), b/scale
        if a == 0:
            roots = [] if bb == 0 else [-c0/bb]
        else:
            disc = bb*bb - 4*a*c0
            if disc < 0:
                roots = []
            else:
                q = -0.5 * (bb + math.copysign(math.sqrt(disc), bb))
                roots = [-bb/(2*a)] if q == 0 else [q/a, c0/q]
        candidates += [x for x in roots if math.isfinite(x) and 0 < x < 1]
    values = [_poly(c, x*width) for x in candidates]
    if not all(math.isfinite(x) for x in values):
        raise ContractError("unrepresentable cubic intensity")
    return min(values)


def curve_log_density(spikes, duration, curve, endpoint_policy):
    """Eq.15 using the exact polynomial integral; trapezoid is diagnostic only.

    Coefficients are ascending powers of seconds since each left knot. The
    submitted curve must be nonnegative throughout each interval. No spline is
    fitted, clipping applied, extrapolation allowed or boundary default chosen.
    """
    fields(curve, ("policy", "rate_units", "knots_seconds", "coefficients",
                   "quadrature_seconds"), "curve")
    if curve["policy"] != POLICY or curve["rate_units"] != "Hz":
        raise ContractError("explicit numeric policy and Hz rate units required")
    duration = number(duration, "duration")
    if duration <= 0 or endpoint_policy not in ("closed", "left_closed_right_open"):
        raise ContractError("positive interval and explicit endpoint required")
    knots = vector(curve["knots_seconds"], "knots", 2)
    quad = vector(curve["quadrature_seconds"], "quadrature", 2)
    for values in (knots, quad):
        if values[0] != 0 or values[-1] != duration or any(a >= b for a,b in zip(values,values[1:])):
            raise ContractError("strict full-window numerical grid required")
    if not set(knots).issubset(quad):
        raise ContractError("quadrature must include every polynomial knot")
    coeff = curve["coefficients"]
    if type(coeff) is not list or len(coeff) != len(knots)-1:
        raise ContractError("one polynomial per interval required")
    coeff = [vector(c, "coefficients", 4) for c in coeff]
    if any(len(c) != 4 for c in coeff):
        raise ContractError("exactly four ascending cubic coefficients required")
    for i,c in enumerate(coeff):
        if _minimum(c, knots[i+1]-knots[i]) < 0:
            raise ContractError("negative cubic intensity between knots")
    def rate(t):
        i = min(len(coeff)-1, bisect_right(knots,t)-1)
        return number(_poly(coeff[i], t-knots[i]), "evaluated intensity")
    # Discontinuity is allowed by this explicit polynomial wire format, but
    # quadrature is segment-local so both one-sided knot values are respected.
    terms = []
    qindex = 0
    for i,c in enumerate(coeff):
        # Every knot is already in quad. This monotone walk visits each interval
        # once, instead of a candidate-controlled quadratic scan of both grids.
        while quad[qindex] < knots[i+1]:
            a,b=quad[qindex],quad[qindex+1]
            terms.append((b-a)*(_poly(c,a-knots[i])+_poly(c,b-knots[i]))/2)
            qindex += 1
    trapezoid = number(math.fsum(terms), "trapezoidal integrated intensity")
    try:
        exact_terms=[]
        for i,c in enumerate(coeff):
            width=knots[i+1]-knots[i]
            exact_terms.append(width*(c[0]+width*(c[1]/2+width*(c[2]/3+width*c[3]/4))))
        integral = number(math.fsum(exact_terms), "exact integrated intensity")
    except OverflowError as exc:
        raise ContractError("unrepresentable exact integral") from exc
    if integral < 0:
        raise ContractError("negative computed intensity integral")
    spikes = vector(spikes,"spikes")
    if (any(a>b for a,b in zip(spikes,spikes[1:])) or any(t<0 or t>duration or
            (endpoint_policy=="left_closed_right_open" and t==duration) for t in spikes)):
        raise ContractError("invalid held-spike times")
    rates = [rate(t) for t in spikes]
    if any(r < 0 for r in rates):
        raise ContractError("negative intensity at spike")
    zero = any(r == 0 for r in rates)
    log_density = None if zero else number(math.fsum(math.log(r) for r in rates)-integral,"log density")
    return {"log_density_nats": log_density, "zero_event_density": zero,
            "integrated_intensity": integral, "spike_count":len(spikes),
            "duration_seconds":duration,
            "trapezoid_integral_diagnostic":trapezoid,
            "trapezoid_minus_exact_integral":number(trapezoid-integral,"quadrature discrepancy")}


def normalized_log_density(joint_log_density, reaction_time_log_density):
    """Eq.16; arguments must be trusted evaluator/model-engine outputs."""
    return number(number(joint_log_density,"joint log density") -
                  number(reaction_time_log_density,"reaction-time log density"),
                  "normalized log density")


def normalized_population_comparison(population, single_neurons, expected_units):
    """Normalize EACH constituent model before summing; never subtract RT once.

    This algebra component cannot authenticate a participant's scalar claims.
    The caller must bind every density to the same protected trial/model engine.
    """
    fields(population,("joint_log_density","reaction_time_log_density"),"population density")
    if type(single_neurons) is not list or type(expected_units) is not list:
        raise ContractError("complete constituent unit list required")
    units = [integer(x,"expected unit") for x in expected_units]
    if not units or len(set(units)) != len(units):
        raise ContractError("unique expected units required")
    logs = {}
    for row in single_neurons:
        fields(row,("unit_id","joint_log_density","reaction_time_log_density"),"single density")
        uid=integer(row["unit_id"],"unit_id")
        if uid in logs:
            raise ContractError("duplicate constituent unit")
        logs[uid]=normalized_log_density(row["joint_log_density"],row["reaction_time_log_density"])
    if set(logs)!=set(units):
        raise ContractError("missing/extra constituent normalization")
    p=normalized_log_density(population["joint_log_density"],population["reaction_time_log_density"])
    independent=number(math.fsum(logs.values()),"independent log density")
    return {"population_log_density_nats":p,"independent_log_density_nats":independent,
            "population_minus_independent_nats":number(p-independent,"density difference"),
            "n_neurons":len(units),"single_neuron_log_densities":[{"unit_id":u,"log_density_nats":logs[u]} for u in units]}


def score_lono(index, predictions, expected_numerics):
    """Complete component grading, with evaluator-pinned grids per case.

    Target spike times never appear in the query. This returns all case values
    and condition denominators; no cohort-level SOTA/qualification pass exists.
    """
    expected={key+(u["unit_id"],):(row,u) for key,row in index["episodes"].items() for u in row["spikes"]}
    if set(expected_numerics)!=set(expected):
        raise ContractError("evaluator numerics must cover every held-neuron case")
    supplied={}
    for row in predictions:
        fields(row,("population_id","subject_id","session_id","trial_id","unit_id","fit_status","curve"),"prediction")
        key=case_key(row)
        if key in supplied or key not in expected:
            raise ContractError("duplicate/extra prediction")
        if row["fit_status"] not in ("fit","fallback_after_fit_failure"):
            raise ContractError("explicit fit/fallback status required")
        supplied[key]=row
    if set(supplied)!=set(expected):
        raise ContractError("complete cases required, including silent/failure cases")
    results, groups=[],defaultdict(list)
    for key,(episode,unit) in sorted(expected.items()):
        pred=supplied[key]
        binding=expected_numerics[key]
        fields(binding,("knots_seconds","quadrature_seconds"),"evaluator numerics")
        if type(pred["curve"]) is not dict or any(pred["curve"].get(k)!=binding[k] for k in binding):
            raise ContractError("candidate changed evaluator-bound numerical grid")
        score=curve_log_density(unit["spike_seconds_from_window_start"],episode["duration_seconds"],pred["curve"],index["endpoint_policy"])
        result={"population_id":key[0],"subject_id":key[1],"session_id":key[2],"trial_id":key[3],"unit_id":key[4],"stimulus_condition":episode["stimulus_condition"],"fit_status":pred["fit_status"],**score}
        results.append(result);groups[(key[0],episode["stimulus_condition"])].append(result)
    summaries=[]
    for (pid,condition),rows in sorted(groups.items()):
        zero=any(r["zero_event_density"] for r in rows)
        summaries.append({"population_id":pid,"stimulus_condition":condition,
                          "n_neuron_trials":len(rows),"n_trials":len({r["trial_id"] for r in rows}),
                          "n_neurons":len({r["unit_id"] for r in rows}),
                          "n_spikes":sum(r["spike_count"] for r in rows),
                          "fallback_cases":sum(r["fit_status"]=="fallback_after_fit_failure" for r in rows),
                          "zero_event_density_cases":sum(r["zero_event_density"] for r in rows),
                          "sum_log_density_nats":None if zero else number(math.fsum(r["log_density_nats"] for r in rows),"group log density"),
                          "sum_status":"negative_infinity" if zero else "finite"})
    return {"schema":"neuralflow-lono-component-score-v1","n_populations":30,
            "n_cases":len(results),"cases":results,"population_conditions":summaries,
            "full_contract_qualified":False,"historical_numerical_parity_established":False,
            "candidate_provenance_verified":False}


def compare_lono(index, candidate, reference, expected_numerics):
    """Paired complete-case likelihood differences; reference is evaluator-owned.

    Reference competence/training separation must be established upstream. The
    function neither fits a reference nor trusts a participant's reference claim.
    """
    a=score_lono(index,candidate,expected_numerics)
    b=score_lono(index,reference,expected_numerics)
    paired=[]
    for x,y in zip(a['cases'],b['cases']):
        if x['zero_event_density'] and y['zero_event_density']:
            status='undefined_both_negative_infinity';delta=None
        elif x['zero_event_density']:
            status='negative_infinity';delta=None
        elif y['zero_event_density']:
            status='positive_infinity';delta=None
        else:
            status='finite';delta=number(x['log_density_nats']-y['log_density_nats'],'paired log density difference')
        paired.append({**{k:x[k] for k in ('population_id','subject_id','session_id','trial_id','unit_id','stimulus_condition')},
                       'candidate_minus_reference_nats':delta,'difference_status':status,
                       'candidate_spike_count':x['spike_count'],'reference_spike_count':y['spike_count']})
    return {'schema':'neuralflow-paired-lono-component-v1','n_cases':len(paired),'cases':paired,
            'candidate':a,'reference':b,'reference_competence_verified':False,
            'full_contract_qualified':False,'new_model_or_SOTA_claim':False}
