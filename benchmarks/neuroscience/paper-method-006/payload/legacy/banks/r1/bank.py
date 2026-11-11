"""Independent R1 arithmetic for PAPER-paper-method-006.

No file, process, network, candidate-code or model operations occur here. The
owner must admit complete inputs and runtime provenance before calling a bank.
This module implements closed arithmetic, not a spike sorter or a historical
publication producer. Source-only engineering controls confer no qualification.
"""

from fractions import Fraction
from math import isqrt


BANK = "R1"
MAX_INPUT_BITS = 4096
MAX_PRECISION = 128
EPS = Fraction(1, 10**10)
TOLERANCE = Fraction(1, 5000)


class Invalid(Exception):
    pass


class Limit(Exception):
    pass


class Unclosed(Exception):
    def __init__(self, identifier, reason):
        super().__init__(reason)
        self.identifier = identifier


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum or value.bit_length() > MAX_INPUT_BITS:
        raise Invalid(name + ": expected bounded integer >= " + str(minimum))
    return value


def rational(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise Invalid(name + ": expected [integer, positive integer]")
    n, d = value
    if type(n) is not int or type(d) is not int or d <= 0:
        raise Invalid(name + ": invalid rational")
    if abs(n).bit_length() > MAX_INPUT_BITS or d.bit_length() > MAX_INPUT_BITS:
        raise Limit(name + ": rational input bit bound")
    return Fraction(n, d)


def packed(value):
    return [value.numerator, value.denominator]


def identifier(value, name):
    try:
        valid = isinstance(value, str) and bool(value) and len(value.encode("utf-8")) <= 1024
    except UnicodeError:
        valid = False
    if not valid:
        raise Invalid(name + ": expected nonempty bounded UTF8 identifier")
    return value


class Meter:
    """Logical algorithmic work, not measured OS memory, I/O, or CPU time."""

    def __init__(self, limits):
        if not isinstance(limits, dict):
            raise Invalid("limits required")
        self.limits = {
            key: integer(limits.get(key), key, minimum)
            for key, minimum in (
                ("max_truth_units", 1), ("max_detected_units", 0),
                ("max_total_events", 0), ("max_pair_edges", 0),
                ("max_work", 1), ("max_precision_digits", 1),
            )
        }
        if self.limits["max_precision_digits"] > MAX_PRECISION:
            raise Invalid("max_precision_digits exceeds implementation bound128")
        self.work = 0
        self.counts = {}

    def charge(self, amount=1, kind="arithmetic"):
        integer(amount, "work charge")
        self.work += amount
        self.counts[kind] = self.counts.get(kind, 0) + amount
        if self.work > self.limits["max_work"]:
            raise Limit("max_work exceeded during " + kind)

    def ensure(self, amount, limit):
        if amount > self.limits[limit]:
            raise Limit(limit + " exceeded")

    def receipt(self):
        return {"work": self.work, "counts": dict(self.counts),
                "meaning": "logical operations; physical resource use unmeasured"}


def event_list(raw, duration, meter, sort=True):
    if not isinstance(raw, list):
        raise Invalid("events must be a list")
    meter.ensure(len(raw), "max_total_events")
    values = []
    for index, event in enumerate(raw):
        meter.charge(kind="event_admission")
        value = rational(event, "event")
        if not 0 <= value < duration:
            raise Invalid("event outside half-open recording interval [0,duration)")
        values.append((value, index))
    if sort:
        # Python tuple order makes the original-row tie break explicit.
        meter.charge(len(values) * max(1, len(values).bit_length()), "stable_sort_bound")
        values.sort()
    return [v for v, _ in values]


def case_input(request, meter, sort=True):
    case = request.get("case")
    if not isinstance(case, dict):
        raise Invalid("case required")
    identifier(case.get("id"), "case id")
    if case.get("kind") not in ("hybrid", "synthetic", "biophysical"):
        raise Invalid("unknown case kind")
    duration = rational(case.get("duration"), "duration")
    if duration <= 0:
        raise Invalid("duration must be positive")
    bin_width = rational(case.get("quality_bin_seconds"), "quality bin")
    if bin_width not in (Fraction(1, 1000), Fraction(1, 2000)):
        raise Invalid("quality bin must be1/1000 or1/2000")
    if bin_width == Fraction(1, 2000) and case["kind"] != "biophysical":
        raise Invalid("half-millisecond quality bin only for admitted biophysical twice-speed view")
    parsed = []
    total = 0
    for name, limit in (("truth", "max_truth_units"), ("detected", "max_detected_units")):
        roster = case.get(name)
        if not isinstance(roster, list):
            raise Invalid(name + " roster required")
        meter.ensure(len(roster), limit)
        if name == "truth" and not roster:
            raise Invalid("complete evaluation truth roster cannot be empty")
        ids = set()
        units = []
        for unit in roster:
            if not isinstance(unit, dict):
                raise Invalid("unit must be an object")
            uid = identifier(unit.get("unit_id"), "unit id")
            if uid in ids:
                raise Invalid("duplicate unit id in " + name)
            ids.add(uid)
            if any(key in unit for key in ("good", "score", "matched", "quality")):
                raise Invalid("candidate-supplied score or quality field")
            events = event_list(unit.get("events"), duration, meter, sort)
            total += len(events)
            meter.ensure(total, "max_total_events")
            units.append({"id": uid, "events": events, "raw": unit})
        parsed.append(units)
    meter.ensure(len(parsed[0]) * len(parsed[1]), "max_pair_edges")
    return case, parsed[0], parsed[1], duration, bin_width


def event_matches(truth, detected, meter):
    """Greedy earliest-compatible interval matching, with each event used once."""
    i = j = k = 0
    while i < len(truth) and j < len(detected):
        meter.charge(kind="event_pair_comparison")
        if truth[i] < detected[j] - TOLERANCE:
            i += 1
        elif detected[j] < truth[i] - TOLERANCE:
            j += 1
        else:
            k += 1
            i += 1
            j += 1
    return k


def nearest_even(value):
    q, r = divmod(value.numerator, value.denominator)
    double = 2 * r
    return q + (double > value.denominator or (double == value.denominator and q % 2 != 0))


def ccg(target, source, bin_width, meter):
    """Independent moving-window enumerator; left-open, right-closed."""
    h = [0] * 1001
    meter.charge(1001, "histogram_allocation")
    low = high = 0
    window = 500 * bin_width
    for time in target:
        meter.charge(kind="ccg_target")
        while high < len(source) and source[high] <= time + window:
            high += 1
            meter.charge(kind="ccg_high_advance")
        while low < len(source) and source[low] <= time - window:
            low += 1
            meter.charge(kind="ccg_low_advance")
        for index in range(low, high):
            meter.charge(kind="ccg_pair")
            position = nearest_even((time - source[index]) / bin_width) + 500
            if not 0 <= position <= 1000:
                raise Invalid("internal CCG interval inconsistency")
            h[position] += 1
    return h


def sqrt_bounds(value, digits, meter):
    """Exact rational enclosure, using integer square root on a fixed grid."""
    if value < 0:
        raise Invalid("negative square root")
    meter.charge(max(1, digits), "certified_sqrt")
    scale = 10**digits
    q = isqrt((value.numerator * scale * scale) // value.denominator)
    lo = Fraction(q, scale)
    hi = lo if q * q * value.denominator == value.numerator * scale * scale else Fraction(q + 1, scale)
    return lo, hi


def atan_inverse_bounds(inverse, digits, meter):
    """Alternating arctan series enclosure, all arithmetic rational."""
    x = Fraction(1, inverse)
    power = x
    total = Fraction(0)
    epsilon = Fraction(1, 10**digits)
    index = 0
    while True:
        meter.charge(kind="certified_atan_term")
        term = power / (2 * index + 1)
        total += term if index % 2 == 0 else -term
        next_term = power * x * x / (2 * index + 3)
        if next_term <= epsilon:
            return (total - next_term, total) if index % 2 == 0 else (total, total + next_term)
        power *= x * x
        index += 1


def pi_bounds(digits, meter):
    a, b = atan_inverse_bounds(5, digits + 3, meter)
    c, d = atan_inverse_bounds(239, digits + 3, meter)
    return 16 * a - 4 * d, 16 * b - 4 * c


def erf_series_bounds(value, digits, meter):
    """Bounds integral_0^x exp(-t^2)dt for0<=x<=1."""
    if not 0 <= value <= 1:
        raise Invalid("erf series support")
    total = Fraction(0)
    power_over_factorial = value
    index = 0
    epsilon = Fraction(1, 10**digits)
    while True:
        meter.charge(kind="certified_erf_term")
        term = power_over_factorial / (2 * index + 1)
        total += term if index % 2 == 0 else -term
        next_power = power_over_factorial * value * value / (index + 1)
        next_term = next_power / (2 * index + 3)
        if next_term <= epsilon:
            return (total - next_term, total) if index % 2 == 0 else (total, total + next_term)
        power_over_factorial = next_power
        index += 1


def probability_interval(n, lam, digits, meter):
    """Certified interval for(1+erf((n-lambda)/sqrt(eps+2lambda)))/2.

    For |z|>=1 use erf(1)>2/3: integral >=1-1/3,
    and sqrt(pi)<2. This deliberately coarse interval still resolves1/5.
    For |z|<1 bound sqrt, pi (Machin), and the alternating erf integral.
    """
    difference = n - lam
    if difference == 0:
        return Fraction(1, 2), Fraction(1, 2)
    square = difference * difference / (EPS + 2 * lam)
    if square >= 1:
        return (Fraction(0), Fraction(1, 6)) if difference < 0 else (Fraction(5, 6), Fraction(1))
    xl, xh = sqrt_bounds(square, digits + 3, meter)
    pl, ph = pi_bounds(digits + 3, meter)
    rootlo, _ = sqrt_bounds(pl, digits + 3, meter)
    _, roothi = sqrt_bounds(ph, digits + 3, meter)
    sl, _ = erf_series_bounds(xl, digits + 3, meter)
    _, sh = erf_series_bounds(xh, digits + 3, meter)
    el = max(Fraction(0), 2 * sl / roothi)
    eh = min(Fraction(1), 2 * sh / rootlo)
    if difference < 0:
        return (1 - eh) / 2, (1 - el) / 2
    return (1 + el) / 2, (1 + eh) / 2


def quality(events, bin_width, meter):
    n_events = len(events)
    span = events[-1] - events[0] if events else Fraction(0)
    if n_events <= 10 or span <= 0:
        return {"status": "not-assessable", "good": False,
                "reason": "requires more than10 events and positive event span",
                "event_count": n_events, "span": packed(span), "Q": None,
                "P_interval": None, "P_lt_one_fifth": None, "histogram": None}
    histogram = ccg(events, events, bin_width, meter)
    work_hist = list(histogram)
    work_hist[500] = 0
    far = sum(work_hist[1:250]) + sum(work_hist[750:1000])
    left, right = sum(work_hist[450:490]), sum(work_hist[510:550])
    meter.charge(1001, "quality_histogram_summary")
    rate_scale = bin_width * n_events * n_events / span
    q00 = Fraction(far, 499) / rate_scale
    q1, q2 = Fraction(left, 40) / rate_scale, Fraction(right, 40) / rate_scale
    r00 = max(Fraction(far, 499), Fraction(left, 40), Fraction(right, 40))
    qs, terms = [], []
    for width in range(1, 11):
        meter.charge(2 * width + 1, "quality_center_sum")
        count = sum(work_hist[500 - width:501 + width])
        qs.append(Fraction(count, 2 * width) / rate_scale)
        terms.append((Fraction(count, 2), r00 * width))
    q = min(qs) / (EPS + max(q00, q1, q2))
    limit = meter.limits["max_precision_digits"]
    digits = min(8, limit)
    while True:
        intervals = [probability_interval(n, lam, digits, meter) for n, lam in terms]
        low = min(a for a, _ in intervals)
        high = min(b for _, b in intervals)
        decision = True if high < Fraction(1, 5) else False if low >= Fraction(1, 5) else None
        if decision is not None or digits == limit:
            break
        digits = min(limit, 2 * digits)
    return {"status": "ok" if decision is not None else "required-unscorable",
            "good": (q < Fraction(1, 5) and decision) if decision is not None else None,
            "event_count": n_events, "span": packed(span), "Q": packed(q),
            "Q_lt_one_fifth": q < Fraction(1, 5), "P_interval": [packed(low), packed(high)],
            "P_lt_one_fifth": decision, "probability_precision_digits": digits,
            "probability_method": "rational Machin/alternating-erf interval with integer sqrt",
            "Q00": packed(q00), "Q1": packed(q1), "Q2": packed(q2), "R00": packed(r00),
            "histogram": histogram, "zero_bin_removed_only_for_quality": histogram[500]}


def assignment(truth_count, detected_count, edges, good, meter):
    """Integral min-cost max-flow: maximize flow, then minimize -good count."""
    source, sink = truth_count + detected_count, truth_count + detected_count + 1
    graph = [[] for _ in range(sink + 1)]

    def add(start, end, cost):
        meter.charge(kind="flow_edge_construction")
        graph[start].append([end, len(graph[end]), 1, cost])
        graph[end].append([start, len(graph[start]) - 1, 0, -cost])

    for index in range(truth_count):
        add(source, index, 0)
    for index in range(detected_count):
        add(truth_count + index, sink, 0)
    forward = []
    for left, right in edges:
        forward.append((left, right, len(graph[left])))
        add(left, truth_count + right, -int(good[right] is True))
    flow = cost = 0
    while True:
        distance = [None] * len(graph)
        previous = [None] * len(graph)
        distance[source] = 0
        for _ in range(len(graph) - 1):
            changed = False
            for start, arcs in enumerate(graph):
                if distance[start] is None:
                    continue
                for edge_id, edge in enumerate(arcs):
                    meter.charge(kind="flow_relaxation")
                    end, _, capacity, edge_cost = edge
                    if capacity and (distance[end] is None or distance[start] + edge_cost < distance[end]):
                        distance[end] = distance[start] + edge_cost
                        previous[end] = (start, edge_id)
                        changed = True
            if not changed:
                break
        if distance[sink] is None:
            break
        current = sink
        while current != source:
            meter.charge(kind="flow_augmentation")
            start, edge_id = previous[current]
            edge = graph[start][edge_id]
            edge[2] -= 1
            graph[current][edge[1]][2] += 1
            current = start
        flow += 1
        cost += distance[sink]
    witness = [(left, right) for left, right, index in forward if graph[left][index][2] == 0]
    if len(witness) != flow:
        raise Invalid("flow witness inconsistency")
    return flow, -cost, witness


def score_i(request, meter):
    case, truths, detected, _, bin_width = case_input(request, meter)
    qualities = [{"unit_id": unit["id"], **quality(unit["events"], bin_width, meter)} for unit in detected]
    good = [q["good"] for q in qualities]
    unresolved = any(x is None for x in good)
    scores, edges, best_scores = [], [], []
    matchable_detected = set()
    for ti, truth in enumerate(truths):
        best = None
        for di, unit in enumerate(detected):
            meter.charge(kind="unit_pair")
            n, m = len(truth["events"]), len(unit["events"])
            k = event_matches(truth["events"], unit["events"], meter)
            value = Fraction(k, n) + Fraction(k, m) - 1 if n and m else None
            edge = bool(n and m and 5 * k * (n + m) > 9 * n * m)
            row = {"truth_id": truth["id"], "detected_id": unit["id"], "match_count": k,
                   "n": n, "m": m, "score": packed(value) if value is not None else None,
                   "precision": packed(Fraction(k, m)) if m else None,
                   "recall": packed(Fraction(k, n)) if n else None,
                   "FP": packed(1 - Fraction(k, m)) if m else None,
                   "FN": packed(1 - Fraction(k, n)) if n else None,
                   "recovery_edge": edge,
                   "definedness": "defined" if n and m else "empty-truth" if not n else "empty-detected"}
            scores.append(row)
            if value is not None and (best is None or value > best[0] or (value == best[0] and unit["id"] < best[1])):
                best = value, unit["id"]
            if edge:
                edges.append((ti, di))
                matchable_detected.add(di)
        best_scores.append({"truth_id": truth["id"], "score": packed(best[0]) if best else None,
                            "detected_id": best[1] if best else None,
                            "definedness": "defined" if best else "abstention" if not detected else "no-defined-pair",
                            "FN_if_abstention": [1, 1] if not detected and truth["events"] else None})
    count, good_count, witness = assignment(len(truths), len(detected), edges, good, meter)
    total_good = None if unresolved else sum(good)
    return {"case_id": case["id"], "kind": case["kind"], "profile": "I_bijective_full",
            "truth_count": len(truths), "detected_count": len(detected), "recovered": count,
            "good_assigned": None if unresolved else good_count, "total_good": total_good,
            "duplicates": len(matchable_detected) - count,
            "unmatched_good": None if unresolved or case["kind"] == "hybrid" else total_good - good_count,
            "unmatched_good_reason": "unlabelled natural background" if case["kind"] == "hybrid" else "unresolved-quality" if unresolved else "quality-surrogate; not biological proof",
            "pair_scores": scores, "best_scores": best_scores, "quality": qualities,
            "assignment": [[truths[a]["id"], detected[b]["id"]] for a, b in witness],
            "assignment_objective": "cardinality-only; secondary quality unresolved" if unresolved else "maximum-cardinality-then-maximum-good",
            "quality_unresolved": unresolved, "resource": meter.receipt()}


def literal_nmatch(truth, detected, dt, meter):
    # The order is intentionally untouched. This emulates bench.nmatch's
    # n0 and two Boolean arrays, not its native numba/compiler environment.
    if not detected and truth:
        raise Unclosed("source-empty-detected", "literal nmatch indexes ss0[0]; no result")
    i = j = count = 0
    truth_flags, detected_flags = [False] * len(truth), [False] * len(detected)
    while i < len(truth):
        meter.charge(kind="source_truth_iteration")
        while j + 1 < len(detected) and detected[j + 1] <= truth[i] + dt:
            j += 1
            meter.charge(kind="source_detected_advance")
        if abs(detected[j] - truth[i]) <= dt:
            count += 1
            truth_flags[i] = detected_flags[j] = True
        i += 1
    return count, truth_flags, detected_flags


def source_coordinates(units, frequency, origin, meter):
    """Verify the exact sample/seconds join without inferring source samples."""
    all_samples = []
    for unit in units:
        samples = unit["raw"].get("source_samples")
        if not isinstance(samples, list) or len(samples) != len(unit["events"]):
            raise Unclosed("source20-sample-roster", "Explicit source_samples must match every event in original order")
        for sample, event in zip(samples, unit["events"]):
            meter.charge(kind="source_clock_join")
            if type(sample) is not int or not -(2**63) <= sample <= 2**63 - 7:
                raise Unclosed("source20-event-dtype", "Explicit safe int64 sample coordinates required; no rounding or overflow repair")
            if (Fraction(sample) - origin) / frequency != event:
                raise Unclosed("source20-sample-seconds-join", "events must equal(source_sample-sample_origin)/sample_frequency in original order")
            all_samples.append(sample)
        unit["samples"] = list(samples)
        unit["depth"] = rational(unit["raw"].get("depth"), "source unit depth")
    if all_samples and max(all_samples) - min(all_samples) > 2**63 - 1:
        raise Unclosed("source20-int64-difference-overflow", "Source sample difference could overflow int64; exact native outcome remains gated")


def source20(request, meter):
    case, truths, detected, _, _ = case_input(request, meter, sort=False)
    profile = request.get("source_profile", {})
    required = ("numpy_version", "argsort_kind", "depth_dtype", "sample_frequency", "sample_origin", "source_clock_admitted", "dt_samples")
    if not isinstance(profile, dict) or any(key not in profile for key in required):
        raise Unclosed("source20-runtime-profile", "Need pinned NumPy version, default quicksort, depth dtype, exact frequency/origin and dt_samples6")
    if profile["argsort_kind"] != "quicksort" or profile["depth_dtype"] not in ("float32", "float64"):
        raise Unclosed("source20-array-profile", "Captured default argsort is quicksort; exact supported depth dtype required")
    if profile["source_clock_admitted"] is not True or type(profile["dt_samples"]) is not int or profile["dt_samples"] != 6:
        raise Unclosed("source20-clock", "Caller must admit exact source clock with default six-sample tolerance")
    fs = rational(profile["sample_frequency"], "source sample frequency")
    if fs <= 0:
        raise Invalid("source frequency must be positive")
    origin = rational(profile["sample_origin"], "source sample origin")
    source_coordinates(truths + detected, fs, origin, meter)
    try:
        import numpy as np
    except ImportError as exc:
        raise Unclosed("source20-library-missing", "Pinned NumPy is absent") from exc
    if np.__version__ != profile["numpy_version"]:
        raise Unclosed("source20-library-version", "Loaded NumPy differs from admitted source profile")
    if not detected:
        raise Unclosed("source20-empty-detected-depths", "Literal match_neuron accesses isort[0]; entire native result undefined")
    dtype = getattr(np, profile["depth_dtype"])
    ys = np.asarray([float(u["depth"]) for u in detected], dtype=dtype)
    yt = np.asarray([float(u["depth"]) for u in truths], dtype=dtype)
    if not np.isfinite(ys).all() or not np.isfinite(yt).all():
        raise Unclosed("source20-nonfinite-depth", "Depth conversion is nonfinite under selected native dtype")
    if any(Fraction(float(ys[k])) != u["depth"] for k, u in enumerate(detected)) or any(Fraction(float(yt[k])) != u["depth"] for k, u in enumerate(truths)):
        raise Unclosed("source20-depth-representation", "Rational depth must exactly represent its admitted native float value; no silent depth rounding")
    rows = []
    for ti, truth in enumerate(truths):
        meter.charge(len(detected) * max(1, len(detected).bit_length()), "source_argsort_bound")
        order = np.argsort(np.abs(yt[ti] - ys), kind="quicksort")
        ntest = min(len(order), 20)
        top = [-1] * 20
        counts = [-1.0] * 20
        top[:ntest] = [int(x) for x in order[:ntest]]
        best = int(order[0])
        maximum = miss = false_positive = 0.0
        pair_rows = []
        for rank in range(ntest):
            di = int(order[rank])
            unit = detected[di]
            if not unit["samples"]:
                pair_rows.append({"detected_id": unit["id"], "status": "source-skipped-empty-detected"})
                continue
            if not truth["samples"]:
                raise Unclosed("source20-empty-truth-division", "Literal score divides n0 by zero truth length; no fabricated score")
            n0, flags_truth, flags_detected = literal_nmatch(truth["samples"], unit["samples"], 6, meter)
            fn = np.maximum(0, 1 - n0 / len(truth["samples"]))
            fp = np.maximum(0, 1 - n0 / len(unit["samples"]))
            value = 1 - fn - fp
            counts[rank] = float(n0)
            pair_rows.append({"detected_id": unit["id"], "n0": n0, "truth_matched_flags": flags_truth,
                              "detected_matched_flags": flags_detected, "FN": float(fn), "FP": float(fp), "score": float(value)})
            if value > maximum:
                maximum, miss, false_positive, best = float(value), float(fn), float(fp), di
        rows.append({"truth_id": truth["id"], "fmax": maximum, "fmiss": miss, "fpos": false_positive,
                     "best_ind": best, "best_id": detected[best]["id"], "top_inds": top,
                     "matched_all": counts, "pairs": pair_rows,
                     "status": "literal-positive-best" if maximum > 0 else "literal-initialized-zero-errors-not-scientific-success"})
    return {"case_id": case["id"], "profile": "R_source20", "rows": rows,
            "source_runtime_profile": profile, "native_parity": "unqualified; emulator only",
            "dt_seconds": packed(Fraction(6, 1) / fs), "resource": meter.receipt()}


PAPER40_GAPS = (
    "best-channel estimator and distance geometry", "distance/score tie behavior",
    "event reuse versus coverage versus bijection", "empty truth/detected handling",
    "good-unit policy and matched identity bookkeeping", "waveform windows and source runtime",
)


def diagnostic(request, meter):
    name = request.get("name")
    operands = request.get("operands", {})
    if not isinstance(operands, dict):
        raise Invalid("diagnostic operands must be object")
    if name == "source_nmatch":
        truth, detected = operands.get("truth_samples"), operands.get("detected_samples")
        if not isinstance(truth, list) or not isinstance(detected, list):
            raise Invalid("source sample lists required")
        meter.ensure(len(truth) + len(detected), "max_total_events")
        for value in truth + detected:
            integer(value, "source sample")
        dt = integer(operands.get("dt_samples"), "dt_samples")
        if dt != 6:
            raise Unclosed("source_nmatch-default", "Only the captured default six-sample primitive is selected")
        n, t, d = literal_nmatch(truth, detected, dt, meter)
        return {"n0": n, "truth_flags": t, "detected_flags": d, "role": "source primitive emulation; not native parity"}
    if name == "ccg":
        duration = rational(operands.get("duration"), "duration")
        if duration <= 0:
            raise Invalid("duration must be positive")
        width = rational(operands.get("quality_bin_seconds"), "quality bin")
        if width not in (Fraction(1, 1000), Fraction(1, 2000)):
            raise Invalid("invalid quality bin")
        target = event_list(operands.get("target"), duration, meter)
        source = event_list(operands.get("source"), duration, meter)
        meter.ensure(len(target) + len(source), "max_total_events")
        return {"histogram": ccg(target, source, width, meter), "central_bin_includes_all_same-bin_pairs": True}
    if name == "family_aggregates":
        return family_aggregates(operands.get("cases"), meter)
    if name == "paired_improvement":
        return paired_improvement(operands, meter)
    if name == "learned_template_expressions":
        b, nm = rational(operands.get("B"), "B"), rational(operands.get("nm"), "nm")
        if nm <= 0:
            raise Unclosed("learned-template-denominator", "Positive norm denominator required; zero source policy not admitted")
        meter.charge(5, "source_expression")
        return {"Cf": packed(max(Fraction(0), b)**2 / nm), "amplitude": packed(b / nm),
                "role": "exact expression diagnostic; no floating native or R_paper policy equivalence"}
    if name == "pooled_recovery_curve":
        values = operands.get("scores")
        if not isinstance(values, list) or not values:
            raise Invalid("nonempty complete score list required")
        meter.ensure(len(values), "max_pair_edges")
        if any(v is None for v in values):
            raise Unclosed("undefined-score-support", "Complete source curve includes undefined scores")
        scores = [rational(v, "score") for v in values]
        meter.charge(len(scores) * max(1, len(scores).bit_length()), "curve_sort_bound")
        scores.sort(reverse=True)
        return {"scores_descending": [packed(v) for v in scores], "recovered_strictly_above_four_fifths": sum(v > Fraction(4, 5) for v in scores), "denominator": len(scores)}
    raise Unclosed("historical-numeric-constructor", "No admitted exact constructor for " + str(name) + "; original pooled figures, bins, waveform T2P/MDHM, drift percentiles, SEM, split regression and native histogram producers are not inferred from unspecified profiles")


def count_cases(raw, meter):
    if not isinstance(raw, list) or len(raw) != 11:
        raise Invalid("exactly11 complete core cases required")
    expected = {"hybrid": 3, "synthetic": 6, "biophysical": 2}
    groups = {name: [] for name in expected}
    ids = set()
    for item in raw:
        meter.charge(kind="aggregate_case")
        if not isinstance(item, dict):
            raise Invalid("case count record required")
        uid = identifier(item.get("case_id"), "case id")
        if uid in ids:
            raise Invalid("duplicate case id")
        ids.add(uid)
        kind = item.get("kind")
        if kind not in groups:
            raise Invalid("unknown family")
        u = integer(item.get("truth_count"), "truth_count", 1)
        if kind == "hybrid" and u != 100 or kind == "synthetic" and u != 600:
            raise Invalid("original designated single-unit denominator mismatch")
        recovered = integer(item.get("recovered"), "recovered")
        if recovered > u:
            raise Invalid("recovery exceeds truth support")
        duplicate = integer(item.get("duplicates"), "duplicates")
        unmatched = None if kind == "hybrid" else integer(item.get("unmatched_good"), "unmatched_good")
        groups[kind].append({"case_id": uid, "kind": kind, "U": u,
                             "r": Fraction(recovered, u), "v": Fraction(duplicate, u),
                             "q": Fraction(unmatched, u) if unmatched is not None else None})
    if any(len(groups[k]) != expected[k] for k in expected):
        raise Invalid("family cardinality mismatch")
    return groups


def aggregate(groups):
    means = {family: sum((row["r"] for row in rows), Fraction(0)) / len(rows) for family, rows in groups.items()}
    v = sum((sum((row["v"] for row in rows), Fraction(0)) / len(rows) for rows in groups.values()), Fraction(0)) / 3
    q = sum((sum((row["q"] for row in groups[k]), Fraction(0)) / len(groups[k]) for k in ("synthetic", "biophysical")), Fraction(0)) / 2
    return {"h": means["hybrid"], "d": means["synthetic"], "b": means["biophysical"],
            "r": sum(means.values(), Fraction(0)) / 3, "q": q, "v": v}


def family_aggregates(raw, meter):
    groups = count_cases(raw, meter)
    values = aggregate(groups)
    return {"aggregates": {k: packed(v) for k, v in values.items()},
            "cases": [{"case_id": row["case_id"], "kind": row["kind"], "truth_count": row["U"],
                       "recovery": packed(row["r"]), "duplicates_per_truth": packed(row["v"]),
                       "unmatched_good_per_truth": packed(row["q"]) if row["q"] is not None else None}
                      for group in groups.values() for row in group]}


def paired_improvement(operands, meter):
    candidate, reference = count_cases(operands.get("candidate"), meter), count_cases(operands.get("reference"), meter)
    c, r = aggregate(candidate), aggregate(reference)
    ca = {row["case_id"]: row for group in candidate.values() for row in group}
    re = {row["case_id"]: row for group in reference.values() for row in group}
    if set(ca) != set(re) or any((ca[k]["kind"], ca[k]["U"]) != (re[k]["kind"], re[k]["U"]) for k in ca):
        raise Invalid("paired case identity/family/denominator mismatch")
    deltas = []
    case_ok = True
    for uid in sorted(ca):
        dr = ca[uid]["r"] - re[uid]["r"]
        dv = ca[uid]["v"] - re[uid]["v"]
        dq = ca[uid]["q"] - re[uid]["q"] if ca[uid]["q"] is not None else None
        case_ok &= dr >= -Fraction(1, 50)
        deltas.append({"case_id": uid, "recovery_delta": packed(dr), "duplicate_delta": packed(dv), "unmatched_good_delta": packed(dq) if dq is not None else None})
    predicates = {"recovery_margin_at_least_one_fiftieth": c["r"] - r["r"] >= Fraction(1, 50),
                  "hybrid_noninferior": c["h"] >= r["h"], "synthetic_noninferior": c["d"] >= r["d"],
                  "biophysical_noninferior": c["b"] >= r["b"], "each_case_margin_at_least_minus_one_fiftieth": case_ok,
                  "unmatched_good_nonincrease": c["q"] <= r["q"], "aggregate_duplicates_nonincrease": c["v"] <= r["v"]}
    return {"numerical_predicates": predicates, "all_numerical_predicates": all(predicates.values()),
            "aggregate_deltas": {k: packed(c[k] - r[k]) for k in c}, "case_deltas": deltas,
            "whole_scientific_claim": None, "claim_gate": "Owner must independently bind all input/source/resource/diagnostic/reference-competence and both-bank gates; numerical predicates alone are not a claim"}


def dispatch(request):
    operation = request.get("operation") if isinstance(request, dict) else None
    response = {"schema": "kilosort4_bank_response_v1", "bank": BANK, "operation": operation,
                "status": "invalid-input", "result": None, "gaps": []}
    meter = None
    try:
        if not isinstance(request, dict):
            raise Invalid("request must be object")
        meter = Meter(request.get("limits"))
        if operation == "score_I":
            result = score_i(request, meter)
        elif operation == "source20":
            result = source20(request, meter)
        elif operation == "paper40":
            # A user-supplied profile object is not closure of original science.
            raise Unclosed("R_paper40-scientific-definition", "; ".join(PAPER40_GAPS))
        elif operation == "quality":
            duration = rational(request.get("duration"), "duration")
            if duration <= 0:
                raise Invalid("duration must be positive")
            width = rational(request.get("quality_bin_seconds"), "quality bin")
            if width not in (Fraction(1, 1000), Fraction(1, 2000)):
                raise Invalid("invalid quality bin")
            events = event_list(request.get("events"), duration, meter)
            result = quality(events, width, meter)
        elif operation == "diagnostic":
            result = diagnostic(request, meter)
        else:
            raise Invalid("unknown operation")
        response["result"] = result
        if result.get("quality_unresolved") or result.get("status") == "required-unscorable":
            response["status"] = "required-unscorable"
            response["gaps"] = [{"id": "quality-transcendental-boundary", "reason": "Finite certified precision did not decide P<1/5"}]
        else:
            response["status"] = "ok"
    except Unclosed as exc:
        response["status"] = "required-unscorable"
        response["gaps"] = [{"id": exc.identifier, "reason": str(exc)}]
    except Limit as exc:
        response["status"] = "resource-limit"
        response["gaps"] = [{"id": "finite-resource-bound", "reason": str(exc)}]
    except (Invalid, KeyError, TypeError, ValueError, OverflowError) as exc:
        response["status"] = "invalid-input"
        response["gaps"] = [{"id": "invalid-input", "reason": str(exc)}]
    if meter is not None:
        response["resource"] = meter.receipt()
    return response
