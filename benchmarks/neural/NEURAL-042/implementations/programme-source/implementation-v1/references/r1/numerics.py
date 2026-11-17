"""R1 written-math implementation using library convolution/Hilbert/assignment.

No candidate or other reference imports. Numeric libraries are explicit internal
primitive arguments; the public production generators obtain pinned libraries.
"""
import hashlib
import math

from .runtime import METRICS, PAIRS, failure_context, require, seed


def kernel(low, high, np, budget):
    require(0 < low < high < 200, "filter_band")
    df = min(max(0.25 * low, 2.0), low, 200.0 - high)
    order = 2 * math.ceil((3.3 * 400 / df) / 2)
    budget.reserve("elements", 8 * (order + 1))
    budget.reserve("work_units", 32 * (order + 1))
    j = np.arange(-order // 2, order // 2 + 1, dtype=np.float64)
    window = np.hamming(order + 1)
    def lowpass(f):
        coefficients = (2.0 * f / 400) * np.sinc(2.0 * f * j / 400) * window
        total = float(np.sum(coefficients, dtype=np.float64))
        require(math.isfinite(total) and total != 0, "finite_filter_normalization")
        return coefficients / total
    result = lowpass(high + df / 2) - lowpass(low - df / 2)
    require(np.isfinite(result).all(), "finite_filter_kernel")
    budget.tick()
    return result


def analytic(x, low, high, np, signal, budget):
    n, width = x.shape
    require(width == 1000, "analytic_full_epoch")
    coefficients = kernel(low, high, np, budget)
    pad = (len(coefficients) - 1) // 2
    budget.reserve("elements", n * (1000 * 5 + 2 * pad) + len(coefficients))
    budget.reserve("work_units", n * (1000 * len(coefficients) + 160 * 1000))
    budget.tick()
    extended = np.pad(x, ((0, 0), (pad, pad)), mode="edge")
    # This is a qualified library operation, independent of R2's direct code.
    filtered = signal.convolve(extended, coefficients[None, :], mode="valid", method="direct")
    require(filtered.shape == x.shape and np.isfinite(filtered).all(), "filter_complete_finite_shape")
    budget.tick()
    result = signal.hilbert(filtered, N=1000, axis=1)
    require(result.shape == x.shape and np.isfinite(result).all(), "analytic_complete_finite_shape")
    budget.tick()
    return result


def features(x, rates, np, signal, budget):
    """Retain two low phases and 30 high amplitudes; exactly32 analytic calls."""
    n = len(rates)
    budget.reserve("elements", n * (32 * 1000 + 30 * 2 + 12))
    budget.reserve("work_units", max(1, n) * 1000 * 160)
    phases = np.empty((2, n, 1000), dtype=np.float64)
    amplitudes = np.empty((30, n, 1000), dtype=np.float64)
    harmonic_moments = np.empty((30, n), dtype=np.complex128)
    theta = np.zeros(n, dtype=np.float64)
    gamma = np.zeros(n, dtype=np.float64)
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for li, f in enumerate((4, 6)):
            low = analytic(x, f - 1, f + 1, np, signal, budget)
            phases[li] = np.angle(low)
            theta += np.mean(np.abs(low) ** 2, axis=1) / 2
        for pi, (f, g) in enumerate(PAIRS):
            high = analytic(x, g - f, g + f, np, signal, budget)
            amplitude = np.abs(high)
            amplitudes[pi] = amplitude
            gamma += np.mean(amplitude ** 2, axis=1) / 30
            moment = np.exp(1j * (round(g / f) * phases[0 if f == 4 else 1] - np.angle(high)))
            harmonic_moments[pi] = np.mean(moment, axis=1)
        slopes = np.diff(x, axis=1)
        positive = np.mean(np.maximum(slopes, 0) ** 2, axis=1)
        negative = np.mean(np.minimum(slopes, 0) ** 2, axis=1)
        denominator = positive + negative
        asymmetry = np.zeros(n, dtype=np.float64)
        np.divide(positive - negative, denominator, out=asymmetry, where=denominator != 0)
    require(all(np.isfinite(v).all() for v in (phases, amplitudes, theta, gamma, harmonic_moments, asymmetry)),
            "finite_feature_arrays")
    power_supported = bool(np.all(theta > 0) and np.all(gamma > 0))
    z = None
    if power_supported:
        budget.reserve("elements", n * 6)
        z = np.column_stack((np.log(theta), np.log(gamma), np.log1p(rates)))
        require(np.isfinite(z).all(), "finite_nuisance_features")
    budget.tick()
    return {"phases": phases, "amplitudes": amplitudes, "harmonic_moments": harmonic_moments,
            "theta_power": theta, "gamma_power": gamma, "firing_rate": rates,
            "waveform_asymmetry": asymmetry, "z": z, "power_supported": power_supported,
            "analytic_calls": 32}


def matching(channel, z, side_a, side_b, design, np, assignment, budget):
    """Independent complete-stratum matrix and the specified SciPy tie recipe."""
    selected_a, selected_b, evidence = [], [], []
    for quartile in range(4):
        for probe in (0, 1):
            aa = sorted((i for i in side_a if channel["order"][i] // 35 == quartile
                         and channel["probe"][i] == probe), key=lambda i: channel["ids"][i])
            bb = sorted((i for i in side_b if channel["order"][i] // 35 == quartile
                         and channel["probe"][i] == probe), key=lambda i: channel["ids"][i])
            budget.reserve("elements", (len(aa) * len(bb) * 12) + 6 * (len(aa) + len(bb)))
            budget.reserve("work_units", (len(aa) + len(bb) + 1) ** 3 + len(aa) * len(bb) * 32)
            pairs, sd, cost_sum, valid_edges = [], None, 0.0, None
            if design == "count_only":
                pairs = list(zip(aa[:min(len(aa), len(bb))], bb[:min(len(aa), len(bb))]))
                cost_sum = None
                recipe = "sorted_id_prefix_min_count"
            else:
                require(design == "nuisance_matched" and z is not None, "matching_design")
                recipe = "SciPy1.15.3_linear_sum_assignment_complete_rectangular_penalty"
                if aa and bb:
                    complete = np.concatenate((z[aa], z[bb]), axis=0)
                    sd_array = np.std(complete, axis=0, ddof=0)
                    require(np.isfinite(sd_array).all(), "finite_population_sd")
                    sd = [float(v) for v in sd_array]
                    difference = z[aa, None, :] - z[None, bb, :]
                    denominator = np.where(sd_array == 0, 1.0, sd_array)
                    standardized = difference / denominator
                    valid = np.all(np.abs(standardized) <= 0.5, axis=2)
                    valid &= np.all((sd_array != 0) | (difference == 0), axis=2)
                    cost = np.sum(standardized * standardized, axis=2)
                    require(np.isfinite(cost).all(), "finite_matching_costs")
                    penalty = 4.0 * (min(len(aa), len(bb)) + 1)
                    matrix = np.where(valid, cost, penalty)
                    budget.tick()
                    row, col = assignment(matrix)
                    budget.tick()
                    require(len(row) == min(len(aa), len(bb)) and len(set(map(int, row))) == len(row)
                            and len(set(map(int, col))) == len(col), "complete_assignment_shape")
                    for ai, bi in zip(row, col):
                        ai, bi = int(ai), int(bi)
                        require(0 <= ai < len(aa) and 0 <= bi < len(bb), "assignment_indices")
                        if bool(valid[ai, bi]):
                            pairs.append((aa[ai], bb[bi]))
                            cost_sum += float(cost[ai, bi])
                    valid_edges = int(np.count_nonzero(valid))
            selected_a.extend(a for a, _ in pairs)
            selected_b.extend(b for _, b in pairs)
            evidence.append({"stratum": [quartile, probe], "n_a": len(aa), "n_b": len(bb),
                             "population_sd": sd, "selected_count": len(pairs),
                             "selected_pairs": [[channel["ids"][a], channel["ids"][b]] for a, b in pairs],
                             "cost": cost_sum, "valid_edges": valid_edges, "recipe": recipe,
                             "optimality_basis": "count_minimum" if design == "count_only" else
                             "complete_qualified_library_assignment_penalty_gt_any_valid_total",
                             "independent_optimality_algorithm_executed": False,
                             "tie_qualification": "exact_sorted_inputs_and_pinned_SciPy_platform_required"})
    budget.tick()
    return selected_a, selected_b, evidence


def mi(phase, amplitude, np, budget):
    require(phase.shape == amplitude.shape and phase.size > 0, "mi_paired_nonempty_shape")
    size = int(phase.size)
    budget.reserve("elements", size * 5 + 18 * 8)
    budget.reserve("work_units", size * 32 + 18 * 16)
    require(np.isfinite(phase).all() and np.isfinite(amplitude).all()
            and np.all(amplitude >= 0), "mi_finite_inputs")
    phase64 = np.asarray(phase, dtype=np.float64).reshape(-1)
    require(np.isfinite(phase64).all() and np.all(phase64 >= -np.pi)
            and np.all(phase64 <= np.pi), "analytic_phase_domain_minus_pi_to_pi")
    # ABI V3 fixes this exact binary64 operation order. No reciprocal, edge
    # search, subtract/re-add wrap, clipping or extra eighteenth bin is allowed.
    bins = np.floor(((phase64 + np.pi) % (2 * np.pi)) / (2 * np.pi) * 18).astype(np.int64)
    require(np.all(bins >= 0) and np.all(bins < 18), "phase_bin_numeric_range")
    counts = np.bincount(bins, minlength=18)
    if np.any(counts == 0):
        return None, "empty_phase_bin"
    weighted = np.bincount(bins, weights=amplitude.reshape(-1), minlength=18)
    means = weighted / counts
    total = float(np.sum(means, dtype=np.float64))
    if not math.isfinite(total) or total <= 0:
        return None, "nonpositive_or_nonfinite_bin_amplitude_sum"
    q = means / total
    nonzero = q > 0
    value = max(0.0, float((np.sum(q[nonzero] * np.log(q[nonzero])) + np.log(18)) / np.log(18)))
    require(math.isfinite(value), "finite_mi")
    budget.tick()
    return value, None


def no_frequencies(reason):
    return [{"phase_center": f, "amplitude_center": g, "status": "unentered", "reason": reason,
             "mi": None, "early_mi": None, "late_mi": None, "trial_null": None, "shift_null": None}
            for f, g in PAIRS]


def condition(feature, indices, identity, np, budget):
    progress = {"identity": identity, "frequency_entered": None, "frequencies_completed": [], "draws_entered": 0}
    try:
        return condition_calculation(feature, indices, identity, np, budget, progress)
    except Exception as error:
        failure = failure_context(error, budget, "condition_calculation", progress)
        if failure is error:
            raise
        raise failure from error


def condition_calculation(feature, indices, identity, np, budget, progress):
    """Complete deterministic conditional P with a streaming ordered draw commitment."""
    n = len(indices)
    if n < 10:
        return None, "insufficient_pairs", ["requires_at_least_ten_pairs"], \
            {"entered": False, "identity": identity}, no_frequencies("insufficient_pairs")
    numeric_seed = seed(identity)
    rng = np.random.default_rng(numeric_seed)
    start = rng.bit_generator.state
    progress["seed"] = numeric_seed
    progress["start_state"] = start
    draw_hash = hashlib.sha256()
    draws = 0
    frequency = []
    totals = {k: 0.0 for k in ("mi", "early_mi", "late_mi", "trial_null", "shift_null", "harmonic_plv")}
    failed = None
    for pi, (f, g) in enumerate(PAIRS):
        if failed is not None:
            frequency.append(no_frequencies(failed)[pi])
            continue
        progress["frequency_entered"] = [f, g]
        budget.reserve("elements", n * 1000 * 12 + n * 8 + 800)
        with budget.hold(n * 1000 * 8 * 18 + 131072):
            phase = feature["phases"][0 if f == 4 else 1, indices, :]
            amplitude = feature["amplitudes"][pi, indices, :]
            observed, reason = mi(phase, amplitude, np, budget)
            early, er = mi(phase[:, :500], amplitude[:, :500], np, budget)
            late, lr = mi(phase[:, 500:], amplitude[:, 500:], np, budget)
            reason = reason or er or lr
            trial_sum = shift_sum = 0.0
            completed_draws = 0
            pair_hash = hashlib.sha256()
            for _ in range(200):
                if reason is not None:
                    break
                budget.reserve("elements", n * 1000 * 5 + n * 4 + 1)
                budget.reserve("work_units", n * 1000 * 4 + n + 1)
                budget.reserve("serialized_bytes", 16 + 4 * n)
                j = int(rng.integers(1, n))
                offsets = rng.integers(200, 801, size=n)
                encoded = (str(j) + ":" + ",".join(str(int(v)) for v in offsets) + "\n").encode("ascii")
                require(len(encoded) <= 16 + 4 * n, "reserved_draw_encoding")
                draw_hash.update(encoded)
                pair_hash.update(encoded)
                draws += 1
                progress["draws_entered"] = draws
                progress["end_state"] = rng.bit_generator.state
                progress["ordered_draw_sha256"] = draw_hash.hexdigest()
                trial_value, tr = mi(phase, np.roll(amplitude, j, axis=0), np, budget)
                shifted = amplitude[np.arange(n)[:, None], (np.arange(1000)[None, :] - offsets[:, None]) % 1000]
                shift_value, sr = mi(phase, shifted, np, budget)
                reason = tr or sr
                if reason is None:
                    trial_sum += trial_value
                    shift_sum += shift_value
                    completed_draws += 1
            row = {"phase_center": f, "amplitude_center": g, "status": "supported" if reason is None else "undefined_mi",
                   "reason": reason, "mi": observed, "early_mi": early, "late_mi": late,
                   "trial_null": trial_sum / 200 if reason is None else None,
                   "shift_null": shift_sum / 200 if reason is None else None,
                   "completed_surrogate_draws": completed_draws, "ordered_draw_sha256": pair_hash.hexdigest()}
            frequency.append(row)
            progress["frequencies_completed"].append([f, g])
            progress["frequency_entered"] = None
            if reason is not None:
                failed = reason
            else:
                for k in ("mi", "early_mi", "late_mi", "trial_null", "shift_null"):
                    totals[k] += row[k] / 30
                totals["harmonic_plv"] += float(abs(np.mean(feature["harmonic_moments"][pi, indices]))) / 30
    evidence = {"entered": True, "identity": identity, "seed": numeric_seed, "generator": "PCG64",
                "numpy": "2.2.6", "start_state": start, "end_state": rng.bit_generator.state,
                "schedule": "30 low-outer/high-inner pairs; each200 draws:integers(1,n),integers(200,801,size=n)",
                "offset_shape_per_draw": [n], "draw_count": draws, "ordered_draw_sha256": draw_hash.hexdigest(),
                "encoding": "ASCIIdecimal_j:comma_joined_ASCIIdecimal_offsets_LF",
                "complete_draw_schedule": draws == 6000}
    if failed is not None:
        return None, "undefined_mi", [failed], evidence, frequency
    totals["corrected_mi"] = totals["mi"] - totals["trial_null"]
    for name in ("theta_power", "gamma_power", "firing_rate", "waveform_asymmetry"):
        totals[name] = float(np.mean(feature[name][indices]))
    require(set(totals) == set(METRICS) and all(math.isfinite(v) for v in totals.values()), "finite_condition_metrics")
    budget.tick()
    return {k: totals[k] for k in METRICS}, "supported", [], evidence, frequency
