"""Complete per-person P reference; no files, providers or finished-answer callback."""
import hashlib
import math
from .budget import ReferenceFailure, require
from .numeric import (libraries, features, band_analytic, phase_bins, mi_from_bins,
                      LOW, PAIRS, SAMPLES)
from .matching import select_pairs
from .protocol import (METRICS, DESIGNS, CONTRASTS, EventSlot, seed, state_copy,
                       packet_metadata, channel_arrays, average_metrics)


def _unentered_frequencies(reason):
    return [{"phase_hz": f, "amplitude_hz": g, "status": "unentered",
             "reason": reason, "observed": None, "early": None, "late": None,
             "trial_null_mean": None, "shift_null_mean": None}
            for f, g in PAIRS]


def _condition(channel, x, feature, indices, counterparts, strata, design,
               contrast, part, side, budget, counters):
    np = libraries()
    n = len(indices)
    identity = f"{channel['id']}:{design}:{contrast}:{part}:{side}"
    # Caller reserved a complete event slot before any result construction.
    base = {"channel": channel["id"], "design": design, "contrast": contrast,
            "part": part, "side": side,
            "selected_trial_ids": [channel["ids"][i] for i in indices],
            "paired_trial_ids": [channel["ids"][i] for i in counterparts],
            "strata": strata, "pair_count": n, "metrics": None,
            "status": "insufficient_pairs", "reasons": [],
            "rng_evidence": {"status": "unentered", "identity": identity},
            "frequency_evidence": []}
    if n < 10:
        base["reasons"] = ["fewer_than_10_pairs"]
        base["frequency_evidence"] = _unentered_frequencies("fewer_than_10_pairs")
        return base
    budget.reserve("elements", 4 * n * SAMPLES + 4 * len(PAIRS) + 400)
    budget.reserve("work_units", 8 * n * SAMPLES)
    with budget.live(64 * n * SAMPLES + 65536):
        selected = x[indices]
        rng_seed = seed(identity, budget)
        generator = np.random.default_rng(rng_seed)
        start = state_copy(generator, budget)
        draw_hash, draws, completed = hashlib.sha256(), 0, 0
        frequency = []
        low_plans = {}
        undefined = False
        failure_reason = None
        for pair_index, (f, g) in enumerate(PAIRS):
            if undefined:
                frequency.extend(_unentered_frequencies(failure_reason)[pair_index:])
                break
            if f not in low_plans:
                phase = feature["low_phase"][f][indices]
                low_plans[f] = (phase_bins(phase, budget),
                                phase_bins(phase[:, :500], budget),
                                phase_bins(phase[:, 500:], budget))
            full, early_plan, late_plan = low_plans[f]
            analytic = band_analytic(selected, g - f, g + f, budget, counters)
            with budget.numeric(8 * n * SAMPLES, 10 * n * SAMPLES, 80 * n * SAMPLES):
                amplitude = np.abs(analytic)
                observed = mi_from_bins(full, amplitude, budget)
                early = mi_from_bins(early_plan, amplitude[:, :500], budget)
                late = mi_from_bins(late_plan, amplitude[:, 500:], budget)
                counters["mi_evaluations"] += 3
                row = {"phase_hz": f, "amplitude_hz": g, "status": "supported",
                       "reason": None, "observed": observed, "early": early, "late": late,
                       "trial_null_mean": None, "shift_null_mean": None,
                       "draws_attempted": 0, "ordered_draw_sha256": None}
                if any(v is None for v in (observed, early, late)):
                    undefined, failure_reason = True, "undefined_observed_or_half_mi"
                    row["status"], row["reason"] = "undefined_mi", failure_reason
                    frequency.append(row)
                    continue
                budget.reserve("elements", 400)
                trial_values, shift_values = [], []
                pair_hash = hashlib.sha256()
                for _ in range(200):
                    # Both exact prescribed draws occur before checking their two MIs.
                    with budget.numeric(14 * n * SAMPLES + 4 * n,
                                        24 * n * SAMPLES, 128 * n * SAMPLES + 64 * n):
                        j = int(generator.integers(1, n))
                        offsets = generator.integers(200, 801, size=n)
                        budget.reserve("serialized_bytes", 8 * n + 64)
                        line = (str(j) + ":" + ",".join(str(int(o)) for o in offsets) + "\n").encode("ascii")
                        draw_hash.update(line)
                        pair_hash.update(line)
                        draws += 1
                        row["draws_attempted"] += 1
                        rolled = np.roll(amplitude, j, axis=0)
                        time_indices = (np.arange(SAMPLES)[None, :] - offsets[:, None]) % SAMPLES
                        shifted = np.take_along_axis(amplitude, time_indices, axis=1)
                        trial_mi = mi_from_bins(full, rolled, budget)
                        shift_mi = mi_from_bins(full, shifted, budget)
                        counters["mi_evaluations"] += 2
                        counters["surrogate_draws"] += 1
                        budget.tick()
                    if trial_mi is None or shift_mi is None:
                        undefined, failure_reason = True, "undefined_surrogate_mi"
                        row["status"], row["reason"] = "undefined_mi", failure_reason
                        break
                    trial_values.append(trial_mi)
                    shift_values.append(shift_mi)
                row["ordered_draw_sha256"] = pair_hash.hexdigest()
                if not undefined:
                    require(len(trial_values) == len(shift_values) == 200,
                            "complete_surrogate_support", budget)
                    row["trial_null_mean"] = math.fsum(trial_values) / 200
                    row["shift_null_mean"] = math.fsum(shift_values) / 200
                    completed += 1
                frequency.append(row)
        require(len(frequency) == 30, "complete_frequency_dispositions", budget)
        base["frequency_evidence"] = frequency
        base["rng_evidence"] = {"status": "entered", "identity": identity, "seed": rng_seed,
                                "bit_generator": "PCG64", "numpy": "2.2.6",
                                "start_state": start, "end_state": state_copy(generator, budget),
                                "ordered_draw_sha256": draw_hash.hexdigest(),
                                "draw_count": draws, "complete_pairs": completed,
                                "calls_per_draw": ["integers(1,n)", "integers(200,801,size=n)"],
                                "offset_shape": [n], "commitment_encoding":
                                "ASCII j:comma-separated offsets followed by LF; pair order is fixed"}
        if undefined:
            base["status"] = "undefined_mi"
            base["reasons"] = [failure_reason]
            return base
        observed = math.fsum(row["observed"] for row in frequency) / 30
        trial_null = math.fsum(row["trial_null_mean"] for row in frequency) / 30
        metrics = {"corrected_mi": observed - trial_null, "mi": observed,
                   "trial_null": trial_null,
                   "shift_null": math.fsum(row["shift_null_mean"] for row in frequency) / 30,
                   "early_mi": math.fsum(row["early"] for row in frequency) / 30,
                   "late_mi": math.fsum(row["late"] for row in frequency) / 30}
        budget.reserve("elements", 8 * n * 30 + 64)
        budget.reserve("work_units", 8 * n * 30 + 64)
        for key in ("theta_power", "gamma_power", "firing_rate", "waveform_asymmetry"):
            metrics[key] = float(np.mean(feature[key][indices]))
        metrics["harmonic_plv"] = math.fsum(
            float(abs(np.mean(feature["harmonic"][pair][indices]))) for pair in PAIRS) / 30
        require(set(metrics) == set(METRICS) and all(math.isfinite(x) for x in metrics.values()),
                "condition_finite_metrics", budget)
        base["metrics"], base["status"] = metrics, "supported"
        return base


def _parts(contrast):
    return (0,) if contrast == CONTRASTS[0] else (0, 1)


def _null_channel(channel, reason):
    estimates, dispositions = [], []
    for design in DESIGNS:
        for contrast in CONTRASTS:
            estimates.append({"design": design, "contrast": contrast, "metrics": None,
                              "matched_pairs": [], "unsupported_reasons": [reason]})
            for part in _parts(contrast):
                for side in ("a", "b"):
                    dispositions.append({"design": design, "contrast": contrast,
                                         "part": part, "side": side,
                                         "status": "unentered", "reason": reason})
    return {"channel": channel["id"], "session": channel["session"],
            "estimates": estimates, "condition_dispositions": dispositions}


def _person_rows(person, channels, budget):
    rows = []
    for design in DESIGNS:
        for contrast in CONTRASTS:
            sessions = {}
            for channel in channels:
                estimate = next(x for x in channel["estimates"]
                                if x["design"] == design and x["contrast"] == contrast)
                if estimate["metrics"] is not None:
                    sessions.setdefault(channel["session"], []).append(estimate["metrics"])
            row = {"patient": person, "design": design, "contrast": contrast,
                   "n_sessions": len(sessions),
                   "n_channels": sum(len(x) for x in sessions.values()), "metrics": None}
            if sessions:
                means = [average_metrics(sessions[s], budget) for s in sorted(sessions)]
                row["metrics"] = average_metrics(means, budget)
            rows.append(row)
    return rows


def evaluate_person(packet, budget):
    """Generator: caller must durably retain each event before advancing."""
    phase = "packet"
    try:
        budget.tick()
        packet_metadata(packet, budget)
        world, person, lineage = packet["world"], packet["person"], packet["lineage"]
        # Admission of the exact libraries precedes numeric conversion/work.
        libraries(production=True)
        import scipy
        require(scipy.__version__ == "1.15.3", "qualified_SciPy_1_15_3_required", budget)
        initial = EventSlot(world, person, "person_started", lineage, budget,
                            4096 + 128 * (len(packet["sessions"]) + len(packet["channels"])))
        yield initial.finish({"session_ids": list(packet["sessions"]),
                              "channel_ids": [c["id"] for c in packet["channels"]],
                              "expected_condition_maximum": 12 * len(packet["channels"])})
        counters = {"analytic_filter_calls": 0, "filtered_trial_calls": 0,
                    "mi_evaluations": 0, "surrogate_draws": 0}
        channel_results, condition_count = [], 0
        # Retained channel summaries and shared metadata remain admitted throughout.
        with budget.live(16384 + 32768 * len(packet["channels"])):
            for channel in packet["channels"]:
                phase = "channel:" + channel["id"]
                n = len(channel["ids"])
                channel_slot = EventSlot(world, person, "channel_result", lineage,
                                         budget, 32768 + 4096 * (n + 1))
                before = dict(counters)
                with budget.live(96 * n * SAMPLES + 65536):
                    x, rates = channel_arrays(channel, budget)
                    if n < 20:
                        result = _null_channel(channel, "insufficient_total_trials_for_10_pairs")
                    else:
                        feature = features(x, rates, budget, counters)
                        if not feature["positive_power"]:
                            result = _null_channel(channel, "nonpositive_retained_trial_theta_or_gamma_power")
                        else:
                            result = {"channel": channel["id"], "session": channel["session"],
                                      "estimates": [], "condition_dispositions": []}
                            for design in DESIGNS:
                                for contrast in CONTRASTS:
                                    part_vectors, pair_records, reasons = [], [], []
                                    for part in _parts(contrast):
                                        a, b, strata = select_pairs(channel, feature["nuisance"],
                                                                    design, contrast, part, budget)
                                        pair_records.append({"part": part, "pair_count": len(a),
                                                             "pairs": [[channel["ids"][i], channel["ids"][j]]
                                                                       for i, j in zip(a, b)]})
                                        results = {}
                                        for side, selected, other in (("a", a, b), ("b", b, a)):
                                            phase = f"condition:{channel['id']}:{design}:{contrast}:{part}:{side}"
                                            slot = EventSlot(world, person, "condition_result", lineage,
                                                             budget, 65536 + 2048 * (n + 1))
                                            value = _condition(channel, x, feature, selected, other, strata,
                                                               design, contrast, part, side, budget, counters)
                                            results[side] = value
                                            condition_count += 1
                                            result["condition_dispositions"].append({
                                                "design": design, "contrast": contrast, "part": part,
                                                "side": side, "status": value["status"],
                                                "reasons": list(value["reasons"])})
                                            yield slot.finish(value)
                                        if all(results[s]["metrics"] is not None for s in ("a", "b")):
                                            part_vectors.append({k: results["a"]["metrics"][k]
                                                                 - results["b"]["metrics"][k] for k in METRICS})
                                        else:
                                            reasons.append("unsupported_part_" + str(part))
                                    vector = average_metrics(part_vectors, budget) if len(part_vectors) == len(_parts(contrast)) else None
                                    result["estimates"].append({"design": design, "contrast": contrast,
                                                                "metrics": vector, "matched_pairs": pair_records,
                                                                "unsupported_reasons": reasons})
                    result["work"] = {k: counters[k] - before[k] for k in counters}
                    result["work"]["strategy"] = "32_feature_filters_then_30_per_entered_supported_condition"
                    result["work"]["historical_34_calls_claimed"] = False
                    channel_results.append({"channel": result["channel"],
                                            "session": result["session"],
                                            "estimates": [{"design": z["design"],
                                                           "contrast": z["contrast"],
                                                           "metrics": z["metrics"]}
                                                          for z in result["estimates"]]})
                    yield channel_slot.finish(result)
                    budget.tick()
            phase = "person_aggregation"
            final = EventSlot(world, person, "person_result", lineage, budget,
                              16384 + 128 * (len(packet["channels"]) + len(packet["sessions"])))
            rows = _person_rows(person, channel_results, budget)
            yield final.finish({"rows": rows, "channel_ids": [c["id"] for c in packet["channels"]],
                                "session_ids": list(packet["sessions"]),
                                "condition_count": condition_count, "channel_count": len(channel_results)})
    except ReferenceFailure as exc:
        exc.record["phase"] = phase
        raise
    except Exception as exc:
        # Never embed private numeric values or a lower-level exception's repr.
        raise ReferenceFailure("unexpected_reference_failure",
                               {"status": "failed", "phase": phase,
                                "error_type": type(exc).__name__,
                                "budget": budget.snapshot()}) from exc

