"""Independent R2 arithmetic bank for the authored Kilosort4 contract.

No file, network, provider or scientific-data access occurs in this module.
dispatch accepts already admitted in-memory values. It cannot authenticate their
scientific provenance; the enclosing protected service must do that first.

R2 uses range-index event graphs, augmenting-path event matching, an integer
Hungarian assignment with dummy vertices, and independent range-bin ACG counts.
Probability comparisons use rational enclosures, not floating tolerances.
"""

from bisect import bisect_left, bisect_right
from collections import deque
from fractions import Fraction
from math import isqrt


SCHEMA = "kilosort4_bank_response_v1"
MAX_INTEGER_BITS = 4096
MAX_PRECISION_DIGITS = 256
TOLERANCE = Fraction(1, 5000)
EPSILON = Fraction(1, 10**10)
THRESHOLD = Fraction(1, 5)


class InputError(ValueError):
    pass


class ResourceLimit(RuntimeError):
    pass


class SourceGate(RuntimeError):
    def __init__(self, gate, reason, partial=None):
        super().__init__(reason)
        self.gate, self.reason, self.partial = gate, reason, partial


def integer(x, name, minimum=None):
    if type(x) is not int or x.bit_length() > MAX_INTEGER_BITS:
        raise InputError(name + " must be a bounded integer, not bool")
    if minimum is not None and x < minimum:
        raise InputError(name + " below permitted minimum")
    return x


def rational(x, name="rational"):
    if not isinstance(x, (tuple, list)) or len(x) != 2:
        raise InputError(name + " must be [integer, positive integer]")
    return Fraction(integer(x[0], name), integer(x[1], name, 1))


def pair(x):
    return [x.numerator, x.denominator] if x is not None else None


def identifier(x, name="unit_id"):
    if not isinstance(x, str) or not x or len(x.encode("utf-8")) > 1024:
        raise InputError(name + " must be a nonempty bounded UTF8 string")
    return x


class Meter:
    """Logical algorithmic bounds; neither a RAM nor a wall-clock instrument."""

    def __init__(self, limits):
        if not isinstance(limits, dict):
            raise InputError("limits must be an explicit object")
        names = {"max_truth_units": 1, "max_detected_units": 0,
                 "max_total_events": 0, "max_pair_edges": 0,
                 "max_work": 1, "max_precision_digits": 1}
        self.limits = {k: integer(limits.get(k), k, v) for k, v in names.items()}
        if self.limits["max_precision_digits"] > MAX_PRECISION_DIGITS:
            raise InputError("max_precision_digits exceeds implemented finite cap")
        self.work = 0
        self.edges = 0
        self.events = 0
        self.pair_rows = 0
        self.precision = 0
        self.counts = {}

    def tick(self, amount=1, category="steps"):
        amount = integer(amount, "work increment", 0)
        if self.work + amount > self.limits["max_work"]:
            raise ResourceLimit("max_work exceeded before " + category)
        self.work += amount
        self.counts[category] = self.counts.get(category, 0) + amount

    def add_edges(self, amount):
        if self.edges + amount > self.limits["max_pair_edges"]:
            raise ResourceLimit("cumulative temporal coincidence-edge cap exceeded")
        self.edges += amount
        self.tick(amount, "temporal_edges")

    def add_events(self, amount):
        if self.events + amount > self.limits["max_total_events"]:
            raise ResourceLimit("max_total_events exceeded")
        self.events += amount
        self.tick(amount, "event_validation")

    def report(self):
        return {"work": self.work, "temporal_edges": self.edges,
                "event_count": self.events, "pair_rows": self.pair_rows,
                "max_precision_digits_used": self.precision,
                "counts": dict(self.counts),
                "measurement": "logical steps only; physical IO/RSS/time unmeasured"}


def event_values(raw, duration, meter):
    if not isinstance(raw, list):
        raise InputError("events must be a list")
    meter.add_events(len(raw))
    values = [rational(x, "event time") for x in raw]
    if any(t < 0 or t >= duration for t in values):
        raise InputError("event outside admitted [0,duration) interval")
    return values


def case_input(case, meter, preserve_order=False):
    if not isinstance(case, dict):
        raise InputError("case must be an object")
    identifier(case.get("id"), "case id")
    if case.get("kind") not in {"hybrid", "synthetic", "biophysical"}:
        raise InputError("unknown case kind")
    duration = rational(case.get("duration"), "duration")
    if duration <= 0:
        raise InputError("duration must be positive")
    bin_seconds = rational(case.get("quality_bin_seconds"), "quality_bin_seconds")
    if bin_seconds not in {Fraction(1, 1000), Fraction(1, 2000)}:
        raise InputError("quality bin must be exactly 1ms or 0.5ms")
    if bin_seconds == Fraction(1, 2000) and case["kind"] != "biophysical":
        raise InputError("0.5ms quality bin is only for admitted twice-speed biophysical view")
    # Whether this is actually the twice-speed view is an enclosing admission gate.
    rosters = []
    for role, limit in (("truth", "max_truth_units"), ("detected", "max_detected_units")):
        source = case.get(role)
        if not isinstance(source, list):
            raise InputError(role + " roster must be a list")
        if len(source) > meter.limits[limit]:
            raise ResourceLimit(role + " roster cap exceeded")
        if role == "truth" and not source:
            raise InputError("complete evaluation truth roster must not be empty")
        seen, parsed = set(), []
        for row in source:
            if not isinstance(row, dict):
                raise InputError("unit row must be an object")
            uid = identifier(row.get("unit_id"))
            if uid in seen:
                raise InputError("duplicate " + role + " unit_id")
            seen.add(uid)
            values = event_values(row.get("events"), duration, meter)
            original = list(enumerate(values))
            if not preserve_order:
                meter.tick(len(values) * max(1, len(values).bit_length()), "stable_sort_bound")
                original.sort(key=lambda item: (item[1], item[0]))
            parsed.append({"unit_id": uid, "events": [x[1] for x in original],
                           "original_rows": [x[0] for x in original], "raw": row})
        rosters.append(parsed)
    return duration, bin_seconds, rosters[0], rosters[1]


def temporal_matching(left, right, meter):
    """Exhaustive rational range graph and independent augmenting paths."""
    adjacency = []
    for t in left:
        meter.tick(2 * max(1, len(right).bit_length()), "temporal_range_search")
        lo = bisect_left(right, t - TOLERANCE)
        hi = bisect_right(right, t + TOLERANCE)
        meter.add_edges(hi - lo)
        adjacency.append(list(range(lo, hi)))
    matched_left = [-1] * len(left)
    matched_right = [-1] * len(right)
    count = 0
    for root in range(len(left)):
        queue = deque([root])
        seen_left = {root}
        predecessor_right = {}
        endpoint = None
        while queue and endpoint is None:
            u = queue.popleft()
            meter.tick(category="event_matching_vertices")
            for v in adjacency[u]:
                meter.tick(category="event_matching_edges")
                if v in predecessor_right:
                    continue
                predecessor_right[v] = u
                if matched_right[v] < 0:
                    endpoint = v
                    break
                following = matched_right[v]
                if following not in seen_left:
                    seen_left.add(following)
                    queue.append(following)
        if endpoint is not None:
            while endpoint >= 0:
                meter.tick(category="event_augmentation")
                u = predecessor_right[endpoint]
                previous = matched_left[u]
                matched_left[u] = endpoint
                matched_right[endpoint] = u
                endpoint = previous
            count += 1
    return count


def weighted_assignment(adjacency, detected_count, good, meter):
    """Padded Hungarian formulation, with no flow algorithm or shared edges.

    U+D rows/columns allow every vertex to remain unmatched. A true edge has
    weight M+good, M=min(U,D)+1. This dominates every possible good-count change.
    Forbidden real pairs have negative weight; dummy pairs have weight zero.
    """
    truth_count = len(adjacency)
    n = truth_count + detected_count
    dominant = min(truth_count, detected_count) + 1
    forbidden = -(dominant * (min(truth_count, detected_count) + 1))

    def cost(i, j):
        if i < truth_count and j < detected_count:
            return -(dominant + int(good[j])) if j in adjacency[i] else -forbidden
        return 0

    u, v, p, way = [0] * (n + 1), [0] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for row in range(1, n + 1):
        p[0] = row
        j0 = 0
        minimum = [None] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta, j1 = None, None
            for j in range(1, n + 1):
                meter.tick(category="integer_assignment_relaxation")
                if used[j]:
                    continue
                current = cost(i0 - 1, j - 1) - u[i0] - v[j]
                if minimum[j] is None or current < minimum[j]:
                    minimum[j], way[j] = current, j0
                if delta is None or minimum[j] < delta:
                    delta, j1 = minimum[j], j
            if j1 is None:
                raise InputError("internal padded assignment lost a dummy completion")
            for j in range(n + 1):
                meter.tick(category="integer_assignment_potential")
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                elif minimum[j] is not None:
                    minimum[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            meter.tick(category="integer_assignment_augmentation")
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    chosen = []
    for j in range(1, detected_count + 1):
        row = p[j] - 1
        if 0 <= row < truth_count and j - 1 in adjacency[row]:
            chosen.append((row, j - 1))
    return sorted(chosen), dominant


def sqrt_interval(x, digits, meter):
    if x < 0:
        raise InputError("sqrt of negative rational")
    meter.tick(max(1, digits), "rational_root_bound")
    scale = 10**digits
    root = isqrt((x.numerator * scale * scale) // x.denominator)
    low = Fraction(root, scale)
    high = low if low * low == x else Fraction(root + 1, scale)
    return low, high


def atan_interval_inverse(denominator, tolerance, meter):
    """Alternating atan(1/q) series, rational remainder enclosure."""
    power, total, k = Fraction(1, denominator), Fraction(0), 0
    while True:
        meter.tick(category="atan_series_terms")
        term = power / (2 * k + 1)
        total += term if k % 2 == 0 else -term
        power /= denominator * denominator
        next_term = power / (2 * k + 3)
        if next_term <= tolerance:
            return ((total - next_term, total) if k % 2 == 0
                    else (total, total + next_term))
        k += 1


def pi_interval(digits, meter):
    tolerance = Fraction(1, 32 * 10**digits)
    a, b = atan_interval_inverse(5, tolerance, meter)
    c, d = atan_interval_inverse(239, tolerance, meter)
    # Machin's exact identity: pi = 16 atan(1/5) - 4 atan(1/239).
    return 16 * a - 4 * d, 16 * b - 4 * c


def erf_series(x, tolerance, meter):
    """Bound the integral series before multiplying by 2/sqrt(pi).

    For 0<=x<=1, the terms x^(2k+1)/(k!(2k+1)) decrease from
    the first term. Successive alternating partial sums bracket the value.
    """
    if not 0 <= x <= 1:
        raise InputError("certified small-erf series outside [0,1]")
    total, term, k = Fraction(0), x, 0
    while True:
        meter.tick(category="erf_series_terms")
        total += term if k % 2 == 0 else -term
        next_term = term * x * x * (2 * k + 1) / ((k + 1) * (2 * k + 3))
        if next_term <= tolerance:
            return ((total - next_term, total) if k % 2 == 0
                    else (total, total + next_term))
        term, k = next_term, k + 1


def probability_interval(n_minus_lambda, variance, digits, meter):
    """Certified [1+erf(a/sqrt(b))]/2 enclosure, no float calls."""
    if variance <= 0:
        raise InputError("probability denominator must be positive")
    if n_minus_lambda == 0:
        return Fraction(1, 2), Fraction(1, 2)
    negative = n_minus_lambda < 0
    magnitude = abs(n_minus_lambda)
    if magnitude * magnitude >= variance:
        # erf(1) > (2/sqrt(pi))*(1-1/3) > 2/3 because pi<4.
        # Monotonicity therefore gives a rigorous, intentionally coarse bound.
        return ((Fraction(0), Fraction(1, 6)) if negative
                else (Fraction(5, 6), Fraction(1)))
    root_low, root_high = sqrt_interval(variance, digits, meter)
    if root_low == 0:
        return Fraction(0), Fraction(1)
    x_low, x_high = magnitude / root_high, min(Fraction(1), magnitude / root_low)
    pi_low, pi_high = pi_interval(digits, meter)
    pi_root_low = sqrt_interval(pi_low, digits, meter)[0]
    pi_root_high = sqrt_interval(pi_high, digits, meter)[1]
    tolerance = Fraction(1, 10**digits)
    integral_low = erf_series(x_low, tolerance, meter)[0]
    integral_high = erf_series(x_high, tolerance, meter)[1]
    erf_low = max(Fraction(0), 2 * integral_low / pi_root_high)
    erf_high = min(Fraction(1), 2 * integral_high / pi_root_low)
    if negative:
        return (1 - erf_high) / 2, (1 - erf_low) / 2
    return (1 + erf_low) / 2, (1 + erf_high) / 2


def range_acg(events, tbin, meter):
    """Count exact rounding cells by independent binary range-index queries.

    A ties-even cell for integer h includes both half boundaries exactly when
    h is even. Intersect with s>t-window, s<=t+window before counting.
    """
    histogram = [0] * 1001
    window = 500 * tbin
    search_charge = 2 * max(1, len(events).bit_length())
    for t in events:
        for h in range(-500, 501):
            meter.tick(search_charge + 1, "acg_range_bins")
            low = t - (Fraction(h) + Fraction(1, 2)) * tbin
            high = t - (Fraction(h) - Fraction(1, 2)) * tbin
            low_closed = high_closed = (h % 2 == 0)
            if low <= t - window:
                low, low_closed = t - window, False
            if high > t + window:
                high, high_closed = t + window, True
            # When high == t+window both constraints hold iff cell includes it.
            start = (bisect_left if low_closed else bisect_right)(events, low)
            stop = (bisect_right if high_closed else bisect_left)(events, high)
            histogram[h + 500] += max(0, stop - start)
    return histogram


def quality(events, tbin, meter):
    result = {"count": len(events), "good": False, "Q": None,
              "P_interval": None, "P_less_than_one_fifth": None,
              "Q_less_than_one_fifth": None, "histogram": None}
    if len(events) <= 10:
        return dict(result, definedness="not-assessable-short-train")
    span = events[-1] - events[0]
    if span <= 0:
        return dict(result, definedness="not-assessable-nonpositive-span")
    histogram = range_acg(events, tbin, meter)
    far = list(range(1, 250)) + list(range(750, 1000))
    left, right = list(range(450, 490)), list(range(510, 550))
    factor = tbin * len(events) ** 2 / span
    means = [Fraction(sum(histogram[j] for j in ix), len(ix)) for ix in (far, left, right)]
    baseline = max(means)
    q_baseline = baseline / factor
    zeroed = histogram.copy()
    zeroed[500] = 0
    probabilities, q_values = [], []
    for i in range(1, 11):
        meter.tick(2 * i + 1, "quality_central_sums")
        c = sum(zeroed[500-i:501+i])
        q_values.append(Fraction(c, 2 * i) / factor)
        lam = baseline * i
        probabilities.append((Fraction(c, 2) - lam, EPSILON + 2 * lam))
    q = min(q_values) / (EPSILON + q_baseline)
    cap = meter.limits["max_precision_digits"]
    digits = min(8, cap)
    decision = None
    final_intervals = []
    while True:
        meter.precision = max(meter.precision, digits)
        final_intervals = [probability_interval(a, b, digits, meter) for a, b in probabilities]
        p_low = min(x[0] for x in final_intervals)
        p_high = min(x[1] for x in final_intervals)
        if p_high < THRESHOLD:
            decision = True
        elif p_low >= THRESHOLD:
            decision = False
        if decision is not None or digits == cap:
            break
        digits = min(cap, digits * 2)
    result.update(Q=pair(q), Q_less_than_one_fifth=q < THRESHOLD,
                  P_interval=[pair(p_low), pair(p_high)],
                  P_less_than_one_fifth=decision,
                  good=(q < THRESHOLD and decision) if decision is not None else None,
                  definedness="defined" if decision is not None else "unresolved-probability-boundary",
                  histogram=histogram, zeroed_center_count=histogram[500],
                  baseline_count_mean=pair(baseline), span=pair(span),
                  probability_intervals=[[pair(a), pair(b)] for a, b in final_intervals],
                  precision_digits=digits,
                  interval_method="rational Machin/alternating-erf/root enclosures")
    return result


def score_i(request, meter):
    case = request.get("case")
    duration, tbin, truth, detected = case_input(case, meter)
    domain = len(truth) * len(detected)
    if domain > meter.limits["max_pair_edges"]:
        raise ResourceLimit("complete UxD output row cap exceeds max_pair_edges")
    meter.pair_rows = domain
    rows, adjacency, best = [], [], []
    for target in truth:
        edges, alternatives = set(), []
        n = len(target["events"])
        for j, observation in enumerate(detected):
            meter.tick(category="pair_score_rows")
            m = len(observation["events"])
            k = temporal_matching(target["events"], observation["events"], meter) if n and m else 0
            value = Fraction(k, m) + Fraction(k, n) - 1 if n and m else None
            recovery = bool(n and m and 5 * k * (n + m) > 9 * n * m)
            definedness = "defined" if n and m else ("empty-truth" if not n else "empty-detected-train")
            if recovery:
                edges.add(j)
            row = {"truth_id": target["unit_id"], "detected_id": observation["unit_id"],
                   "match_count": k, "n": n, "m": m, "score": pair(value),
                   "precision": pair(Fraction(k, m)) if m else None,
                   "recall": pair(Fraction(k, n)) if n else None,
                   "FP": pair(1 - Fraction(k, m)) if m else None,
                   "FN": pair(1 - Fraction(k, n)) if n else None,
                   "recovery_edge": recovery, "definedness": definedness}
            rows.append(row)
            if value is not None:
                alternatives.append((value, observation["unit_id"]))
        if alternatives:
            value = max(x[0] for x in alternatives)
            witness = min(x[1] for x in alternatives if x[0] == value)
            best.append({"truth_id": target["unit_id"], "score": pair(value),
                         "detected_id": witness, "definedness": "defined"})
        else:
            best.append({"truth_id": target["unit_id"], "score": None,
                         "detected_id": None,
                         "definedness": "abstention" if not detected else "no-defined-pair",
                         "FN": [1, 1] if n else None})
        adjacency.append(edges)
    qualities = [{"unit_id": x["unit_id"], **quality(x["events"], tbin, meter)} for x in detected]
    known = all(x["good"] is not None for x in qualities)
    good = [x["good"] is True for x in qualities]
    assignment, dominant = weighted_assignment(adjacency, len(detected), good, meter)
    recovered = len(assignment)
    good_assigned = sum(good[j] for _, j in assignment) if known else None
    total_good = sum(good) if known else None
    incident = set().union(*adjacency) if adjacency else set()
    result = {"case_id": case["id"], "profile": "I_bijective_full",
              "truth_count": len(truth), "detected_count": len(detected),
              "recovered": recovered, "good_assigned": good_assigned,
              "total_good": total_good, "duplicates": len(incident) - recovered,
              "unmatched_good": total_good - good_assigned if known and case["kind"] != "hybrid" else None,
              "unmatched_good_definedness": "unlabelled-natural-background" if case["kind"] == "hybrid" else ("defined" if known else "unresolved-quality"),
              "pair_scores": rows, "assignment": [[truth[i]["unit_id"], detected[j]["unit_id"]] for i, j in assignment],
              "assignment_witness_definedness": "both-objectives" if known else "cardinality-only-quality-unresolved",
              "quality": qualities, "best_scores": best,
              "event_support": {"truth": [{"unit_id": x["unit_id"], "count": len(x["events"]), "sorted_original_rows": x["original_rows"]} for x in truth],
                                "detected": [{"unit_id": x["unit_id"], "count": len(x["events"]), "sorted_original_rows": x["original_rows"]} for x in detected]},
              "assignment_dominant_weight": dominant,
              "resource": meter.report(), "full_support_provenance": "enclosing admission required"}
    if not known:
        raise SourceGate("I-quality-probability", "At least one P threshold is unresolved within finite precision", result)
    return result


def source20(request, meter):
    _, _, truth, detected = case_input(request.get("case"), meter, preserve_order=True)
    profile = request.get("source_profile")
    mandatory = {"numpy_version", "argsort_kind", "depth_dtype", "sample_frequency", "sample_origin", "source_clock_admitted", "dt_samples"}
    if not isinstance(profile, dict) or not mandatory <= set(profile):
        raise SourceGate("R-source-runtime", "Need pinned NumPy version/default quicksort/depth dtype and exact source sample-origin profile")
    if profile["source_clock_admitted"] is not True or profile["argsort_kind"] != "quicksort" or profile["dt_samples"] != 6:
        raise SourceGate("R-source-runtime", "Captured compare_recordings uses default NumPy quicksort and dt=6; exact source clock must be admitted")
    if profile["depth_dtype"] not in {"float32", "float64"}:
        raise SourceGate("R-source-dtype", "Only explicitly pinned float32/float64 depth profiles are implemented")
    fs = rational(profile["sample_frequency"], "sample_frequency")
    origin = rational(profile["sample_origin"], "sample_origin")
    if fs <= 0:
        raise InputError("sample_frequency must be positive")
    for row in truth + detected:
        raw = row["raw"].get("source_samples")
        if not isinstance(raw, list) or len(raw) != len(row["events"]):
            raise InputError("source_samples required, with one integral sample per event")
        row["samples"] = [integer(x, "source sample") for x in raw]
        if any((Fraction(s) - origin) / fs != t for s, t in zip(row["samples"], row["events"])):
            raise InputError("source sample/time join fails; no implicit waveform offset allowed")
        row["depth"] = rational(row["raw"].get("depth"), "source depth")
    try:
        import numpy as np
    except ImportError:
        raise SourceGate("R-source-runtime", "Pinned NumPy is unavailable; no replacement tie rule used") from None
    if np.__version__ != profile["numpy_version"]:
        raise SourceGate("R-source-runtime", "Installed NumPy version differs from admitted source profile")
    dtype = np.dtype(profile["depth_dtype"])
    depths = np.asarray([float(x["depth"]) for x in detected], dtype=dtype)
    if not np.isfinite(depths).all():
        raise InputError("depth conversion produced a nonfinite source value")
    completed = []
    for target in truth:
        if not detected:
            raise SourceGate("R-source-empty-depths", "Literal match_neuron accesses isort[0] for empty detected depths", {"completed_truth_rows": completed, "failure_branch": "IndexError", "observed_native_failure": False})
        target_depth = np.asarray(float(target["depth"]), dtype=dtype)
        if not np.isfinite(target_depth):
            raise InputError("nonfinite truth depth after source dtype conversion")
        meter.tick(len(detected) * max(1, len(detected).bit_length()), "source_numpy_argsort_bound")
        order = np.argsort(np.abs(target_depth - depths), kind="quicksort").tolist()
        best, maximum, miss, false_positive = order[0], 0.0, 0.0, 0.0
        matched_all, top_indices, inspected = [-1.0] * 20, [-1] * 20, []
        n = len(target["samples"])
        for rank, j in enumerate(order[:20]):
            top_indices[rank] = j
            candidate = detected[j]["samples"]
            if not candidate:
                continue
            if not n:
                raise SourceGate("R-source-empty-truth", "Literal n0/len(ss) divides by zero; initialized zeros are not valid science", {"completed_truth_rows": completed, "failed_truth_id": target["unit_id"], "failure_branch": "ZeroDivisionError", "observed_native_failure": False})
            cursor, n0, used = 0, 0, set()
            for event in target["samples"]:
                meter.tick(category="source_truth_iterations")
                while cursor + 1 < len(candidate) and candidate[cursor + 1] <= event + 6:
                    meter.tick(category="source_detected_advance")
                    cursor += 1
                if abs(candidate[cursor] - event) <= 6:
                    n0 += 1
                    used.add(cursor)
            fn = max(0.0, 1 - n0 / n)
            fp = max(0.0, 1 - n0 / len(candidate))
            value = 1 - fn - fp
            matched_all[rank] = float(n0)
            inspected.append({"detected_id": detected[j]["unit_id"], "truth_iterations_matched": n0,
                              "distinct_detected_matched": len(used), "n": n, "m": len(candidate),
                              "raw_score": value, "FP": fp, "FN": fn})
            if value > maximum:
                maximum, miss, false_positive, best = value, fn, fp, j
        completed.append({"truth_id": target["unit_id"], "fmax": maximum,
                          "fmiss": miss, "fpos": false_positive, "best_ind": best,
                          "best_detected_id": detected[best]["unit_id"], "matched_all": matched_all,
                          "top_inds": top_indices, "inspected": inspected,
                          "definedness": "positive-source-score" if maximum > 0 else "initialized-zero-not-evidence-of-no-errors"})
    return {"profile": "R_source20", "rows": completed, "runtime_profile": profile,
            "native_parity": "not established", "resource": meter.report()}


PAPER_GAPS = ["best-channel estimator and geometry", "depth and score ties",
              "event reuse/coverage/bijection", "empty train behavior", "good-unit classifier",
              "matched identity bookkeeping", "waveform windows", "historical runtime and producer"]


def paper40(request, meter):
    # Operator-supplied policy strings cannot create an authenticated historical
    # algorithm. A later separately reviewed concrete profile needs source code.
    raise SourceGate("R-paper40-scientific-policy", "No closed publication producer is admitted; missing: " + "; ".join(PAPER_GAPS))


def family_values(rows):
    if not isinstance(rows, list) or len(rows) != 11:
        raise InputError("exactly eleven complete core case summaries required")
    groups = {"hybrid": [], "synthetic": [], "biophysical": []}
    seen = set()
    for row in rows:
        cid = identifier(row.get("case_id"), "case_id")
        if cid in seen or row.get("kind") not in groups:
            raise InputError("duplicate case ID or invalid family")
        seen.add(cid)
        u = integer(row.get("truth_count"), "truth_count", 1)
        r = integer(row.get("recovered"), "recovered", 0)
        d = integer(row.get("duplicates"), "duplicates", 0)
        if r > u:
            raise InputError("recovered count exceeds evaluation roster")
        q = None if row["kind"] == "hybrid" else Fraction(integer(row.get("unmatched_good"), "unmatched_good", 0), u)
        groups[row["kind"]].append((cid, Fraction(r, u), Fraction(d, u), q))
    if tuple(len(groups[k]) for k in groups) != (3, 6, 2):
        raise InputError("all three hybrid, six synthetic, two biophysical cases required")
    recovery = {k: sum((v[1] for v in values), Fraction(0)) / len(values) for k, values in groups.items()}
    duplicate = {k: sum((v[2] for v in values), Fraction(0)) / len(values) for k, values in groups.items()}
    q = sum((sum((v[3] for v in groups[k]), Fraction(0)) / len(groups[k]) for k in ("synthetic", "biophysical")), Fraction(0)) / 2
    return groups, recovery, sum(recovery.values(), Fraction(0)) / 3, sum(duplicate.values(), Fraction(0)) / 3, q


def diagnostic(request, meter):
    name = request.get("name")
    data = request.get("operands")
    if not isinstance(data, dict):
        raise InputError("diagnostic operands must be an object")
    if name == "I_family_aggregates":
        groups, recovery, r, v, q = family_values(data.get("cases"))
        meter.tick(11, "family_aggregate_rows")
        return {"family_recovery": {k: pair(x) for k, x in recovery.items()},
                "r": pair(r), "v": pair(v), "q": pair(q),
                "cases": data["cases"], "claim": "arithmetic only; full identity/admission gates remain"}
    if name == "I_joint_improvement":
        cg, cr, ctotal, cv, cq = family_values(data.get("candidate"))
        rg, rr, rtotal, rv, rq = family_values(data.get("reference"))
        candidate_rows = {x[0]: (family, x) for family, values in cg.items() for x in values}
        reference_rows = {x[0]: (family, x) for family, values in rg.items() for x in values}
        if candidate_rows.keys() != reference_rows.keys():
            raise InputError("candidate/reference complete case IDs differ")
        candidate_denominators = {x["case_id"]: x["truth_count"] for x in data["candidate"]}
        reference_denominators = {x["case_id"]: x["truth_count"] for x in data["reference"]}
        if candidate_denominators != reference_denominators:
            raise InputError("paired evaluation roster denominators changed")
        deltas = []
        for cid in sorted(candidate_rows):
            family, c = candidate_rows[cid]
            rf, r = reference_rows[cid]
            if family != rf:
                raise InputError("paired family changed")
            deltas.append({"case_id": cid, "recovery_delta": pair(c[1] - r[1]),
                           "duplicate_delta": pair(c[2] - r[2]),
                           "unmatched_good_delta": pair(c[3] - r[3]) if c[3] is not None else None})
        tests = {"recovery_margin_at_least_1_50": ctotal - rtotal >= Fraction(1, 50),
                 "no_family_decrease": all(cr[k] >= rr[k] for k in cr),
                 "no_case_decrease_beyond_1_50": all(rational(x["recovery_delta"]) >= -Fraction(1, 50) for x in deltas),
                 "aggregate_duplicate_nonincrease": cv <= rv,
                 "unmatched_good_nonincrease": cq <= rq}
        meter.tick(22, "improvement_rows")
        return {"arithmetic_pass": all(tests.values()), "tests": tests, "case_deltas": deltas,
                "recovery_delta": pair(ctotal-rtotal), "duplicate_delta": pair(cv-rv),
                "unmatched_good_delta": pair(cq-rq),
                "scientific_improvement_claim": None,
                "claim_gate": "Exact input/resource/source pairing, diagnostics and competent fixed references require enclosing admission"}
    if name == "source_learned_matching_expression":
        if not isinstance(data.get("B"), list) or not isinstance(data.get("nm"), list):
            raise InputError("B and nm must be explicit lists")
        meter.add_events(len(data["B"]) + len(data["nm"]))
        b = [rational(x) for x in data.get("B", [])]
        norms = [rational(x) for x in data.get("nm", [])]
        if len(b) != len(norms) or any(x <= 0 for x in norms):
            raise InputError("B/nm requires equal lengths and positive norms")
        meter.tick(len(b), "source_expression_rows")
        return {"Cf": [pair(max(Fraction(0), x)**2 / n) for x, n in zip(b, norms)],
                "amplitude": [pair(x/n) for x, n in zip(b, norms)],
                "profile": "exact algebraic source expression, not native floating parity or R_paper policy"}
    if name == "source_400_edges_histogram":
        if not isinstance(data.get("values"), list):
            raise InputError("values must be an explicit list")
        meter.add_events(len(data["values"]))
        values = [rational(x) for x in data.get("values", [])]
        edges = [Fraction(-2) + Fraction(4 * j, 399) for j in range(400)]
        counts = [0] * 399
        outside = 0
        for value in values:
            meter.tick(10, "source_histogram_range_search")
            if value < -2 or value > 2:
                outside += 1
            elif value == 2:
                counts[-1] += 1
            else:
                counts[bisect_right(edges, value) - 1] += 1
        return {"edges": [pair(x) for x in edges], "counts": counts, "outside": outside,
                "profile": "400 rational source-expression edges, 399 bins; native float linspace parity remains separate"}
    raise SourceGate("diagnostic-constructor", "Historical constructor not closed/implemented for " + str(name) + "; exact roster, windows, normalization, binning, geometry, seeds, percentile/SEM/T2P/MDHM and producer profile required")


def dispatch(request):
    operation = request.get("operation") if isinstance(request, dict) else None
    response = {"schema": SCHEMA, "bank": "R2", "operation": operation,
                "status": "ok", "result": None, "gaps": []}
    meter = None
    try:
        if not isinstance(request, dict):
            raise InputError("request must be an object")
        meter = Meter(request.get("limits"))
        if operation == "score_I":
            result = score_i(request, meter)
        elif operation == "source20":
            result = source20(request, meter)
        elif operation == "paper40":
            result = paper40(request, meter)
        elif operation == "quality":
            duration = rational(request.get("duration"), "duration")
            if duration <= 0:
                raise InputError("duration must be positive")
            tbin = rational(request.get("quality_bin_seconds"), "quality_bin_seconds")
            if tbin not in {Fraction(1, 1000), Fraction(1, 2000)}:
                raise InputError("invalid quality bin width")
            events = event_values(request.get("events"), duration, meter)
            meter.tick(len(events) * max(1, len(events).bit_length()), "stable_sort_bound")
            events.sort()
            result = quality(events, tbin, meter)
            if result["good"] is None:
                raise SourceGate("I-quality-probability", "Finite probability interval did not separate threshold", result)
        elif operation == "diagnostic":
            result = diagnostic(request, meter)
        else:
            raise InputError("unknown operation")
        result["resource"] = meter.report()
        response["result"] = result
    except SourceGate as error:
        response.update(status="required-unscorable", result=error.partial,
                        gaps=[{"id": error.gate, "reason": error.reason}])
    except ResourceLimit as error:
        response.update(status="resource-limit", gaps=[{"id": "finite-resource-cap", "reason": str(error)}])
    except (InputError, KeyError, TypeError, UnicodeError, OverflowError) as error:
        response.update(status="invalid-input", gaps=[{"id": "input-contract", "reason": str(error)}])
    if meter is not None:
        response["resource"] = meter.report()
    return response
