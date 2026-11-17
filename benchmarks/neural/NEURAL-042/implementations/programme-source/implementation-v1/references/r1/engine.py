"""Independent full per-person P and equal-person world aggregation for O/D."""
import hashlib
import math

from .runtime import (Budget, CONTRASTS, DESIGNS, ID, METRICS, REFERENCE, canonical,
                      event, failure_context, libraries, number, require, seed, slot,
                      typed_pin, validate_lineage, validate_snapshot)
from .numerics import condition, features, matching

CLAIM_SCOPE = "descriptive_patient_associations_not_causal_or_crossoscillator_proof"


def identity(value):
    return type(value) is str and ID.fullmatch(value) is not None


def packet_metadata(packet):
    require(type(packet) is dict and set(packet) ==
            {"schema", "world", "person", "sessions", "channels", "lineage"}, "person_packet_keys")
    require(packet["schema"] == "neural042_reference_person_v1" and packet["world"] in ("O", "D")
            and identity(packet["person"]), "person_packet_identity")
    sessions, channels = packet["sessions"], packet["channels"]
    require(type(sessions) is list and 1 <= len(sessions) <= 44 and all(identity(s) for s in sessions)
            and sessions == sorted(set(sessions)), "complete_sorted_sessions")
    require(type(channels) is list, "channel_list")
    ids = []
    for channel in channels:
        require(type(channel) is dict and set(channel) ==
                {"id", "session", "lfp", "rates", "loads", "correct", "probe", "order", "ids"},
                "channel_keys")
        require(identity(channel["id"]) and channel["session"] in sessions, "channel_session_identity")
        ids.append(channel["id"])
    require(ids == sorted(set(ids)), "complete_sorted_unique_channels")
    validate_lineage(packet["lineage"])
    return sessions, ids


def numeric_channel(channel, np, budget, consistency):
    ids = channel["ids"]
    require(type(ids) is list and len(ids) <= 140 and all(identity(v) for v in ids)
            and len(set(ids)) == len(ids), "unique_trial_ids")
    n = len(ids)
    budget.reserve("elements", n * (1000 * 3 + 12))
    budget.reserve("work_units", n * (1000 * 5 + 32) + 1)
    output = {"id": channel["id"], "session": channel["session"], "ids": list(ids)}
    for key, allowed in (("loads", {1, 3}), ("correct", {0, 1}), ("probe", {0, 1}), ("order", set(range(140)))):
        values = channel[key]
        if type(values) is np.ndarray:
            require(values.ndim == 1 and values.shape == (n,) and values.dtype.kind in "iu", "integer_metadata_array")
            values = values.tolist()
        require(type(values) is list and len(values) == n
                and all(type(v) is int and v in allowed for v in values), "integer_trial_metadata")
        output[key] = list(values)
    require(len(set(output["order"])) == n, "unique_original_trial_order")
    for i, trial in enumerate(ids):
        fingerprint = (channel["session"], output["order"][i], output["loads"][i],
                       output["correct"][i], output["probe"][i])
        require(trial not in consistency or consistency[trial] == fingerprint, "cross_channel_trial_metadata_join")
        consistency[trial] = fingerprint
    waveform = channel["lfp"]
    if type(waveform) is list:
        require(len(waveform) == n and all(type(row) is list and len(row) == 1000 for row in waveform),
                "full_waveform_list_shape")
        require(all(number(v) for row in waveform for v in row), "finite_nonboolean_waveform_list")
        waveform = np.asarray(waveform, dtype=np.float64).reshape(n, 1000)
    else:
        require(type(waveform) is np.ndarray and waveform.shape == (n, 1000)
                and waveform.dtype.kind == "f" and waveform.dtype.itemsize == 8, "primitive_float64_waveform")
        waveform = np.asarray(waveform, dtype=np.float64)
    rates = channel["rates"]
    if type(rates) is list:
        require(len(rates) == n and all(number(v) and v >= 0 for v in rates), "finite_nonnegative_rate_list")
        rates = np.asarray(rates, dtype=np.float64)
    else:
        require(type(rates) is np.ndarray and rates.shape == (n,) and rates.dtype.kind == "f", "primitive_rate_array")
        rates = np.asarray(rates, dtype=np.float64)
    require(np.isfinite(waveform).all() and np.isfinite(rates).all() and np.all(rates >= 0), "finite_numeric_channel")
    output.update(lfp=waveform, rates=rates)
    budget.tick()
    return output


def side_indices(channel, contrast, part):
    if contrast == CONTRASTS[0]:
        require(part == 0, "load_part_zero")
        a = [i for i, (load, correct) in enumerate(zip(channel["loads"], channel["correct"])) if load == 3 and correct == 1]
        b = [i for i, (load, correct) in enumerate(zip(channel["loads"], channel["correct"])) if load == 1 and correct == 1]
    else:
        require(contrast == CONTRASTS[1] and part in (0, 1), "accuracy_part")
        selected_load = 1 if part == 0 else 3
        a = [i for i, (load, correct) in enumerate(zip(channel["loads"], channel["correct"])) if load == selected_load and correct == 1]
        b = [i for i, (load, correct) in enumerate(zip(channel["loads"], channel["correct"])) if load == selected_load and correct == 0]
    return a, b


def condition_keys():
    return [(design, contrast, part, side) for design in DESIGNS for contrast in CONTRASTS
            for part in ((0,) if contrast == CONTRASTS[0] else (0, 1)) for side in ("a", "b")]


def equal_mean(vectors):
    require(bool(vectors), "nonempty_equal_mean")
    return {key: math.fsum(v[key] for v in vectors) / len(vectors) for key in METRICS}


def evaluate_person(packet, budget):
    """Reserve persistent metadata across yielded events as well as numeric buffers."""
    try:
        require(isinstance(budget, Budget), "reference_budget")
        require(type(packet) is dict and type(packet.get("sessions")) is list
                and type(packet.get("channels")) is list, "packet_metadata_container")
        ns, nc = len(packet["sessions"]), len(packet["channels"])
        budget.reserve("elements", 4096 * nc + 128 * ns + 4096)
        with budget.hold(1048576 + 8192 * ns + 262144 * nc):
            yield from evaluate_person_calculation(packet, budget)
    except Exception as error:
        failure = failure_context(error, budget, "person_persistent_metadata", {})
        if failure is error:
            raise
        raise failure from error


def evaluate_person_calculation(packet, budget):
    """Yield complete private evidence and exactly four final rows; never open files."""
    progress = {"channels_completed": [], "conditions_completed": [], "channel_entered": None,
                "condition_entered": None}
    phase = "packet_metadata"
    try:
        require(isinstance(budget, Budget), "reference_budget")
        budget.tick()
        require(type(packet) is dict and type(packet.get("sessions")) is list
                and type(packet.get("channels")) is list, "packet_metadata_container")
        budget.reserve("elements", 128 * len(packet["channels"]) + 16 * len(packet["sessions"]) + 64)
        budget.reserve("work_units", 256 * len(packet["channels"]) + 64 * len(packet["sessions"]) + 64)
        sessions, channel_ids = packet_metadata(packet)
        world, person, lineage = packet["world"], packet["person"], packet["lineage"]
        cap = slot(budget, 8192 + 96 * (len(sessions) + len(channel_ids)))
        yield event("person_started", {"session_ids": list(sessions), "channel_ids": list(channel_ids)},
                    world, person, lineage, budget, cap)
        phase = "qualified_libraries"
        np, signal, assignment = libraries()
        budget.tick()
        session_vectors = {(d, c): {} for d in DESIGNS for c in CONTRASTS}
        consistency = {}
        condition_count = 0
        for raw_channel in packet["channels"]:
            phase = "channel_admission"
            progress["channel_entered"] = raw_channel["id"]
            require(type(raw_channel["ids"]) is list and len(raw_channel["ids"]) <= 140, "bounded_trial_list")
            n = len(raw_channel["ids"])
            channel_cap = slot(budget, 65536 + n * 256)
            # Includes retained features, input/conversion copies and declared library temporaries.
            # Hidden library/allocator workspace is separately physically qualified by the owner.
            with budget.hold(max(1, n) * 1000 * 8 * 80 + 1048576):
                channel = numeric_channel(raw_channel, np, budget, consistency)
                phase = "channel_features"
                feature = features(channel["lfp"], channel["rates"], np, signal, budget) if n else None
                gate = "no_retained_trials" if n == 0 else (None if feature["power_supported"] else "nonpositive_power")
                estimates, dispositions = [], []
                for design in DESIGNS:
                    for contrast in CONTRASTS:
                        parts = (0,) if contrast == CONTRASTS[0] else (0, 1)
                        differences, selected_pairs, reasons = [], [], []
                        for part in parts:
                            if gate is not None:
                                reasons.append(gate)
                                for side in ("a", "b"):
                                    dispositions.append({"design": design, "contrast": contrast, "part": part,
                                                         "side": side, "status": "unentered", "reason": gate})
                                selected_pairs.append({"part": part, "pair_count": 0, "a": [], "b": []})
                                continue
                            phase = "matching_and_conditions"
                            # Reserve first condition's complete payload before constructing matching evidence.
                            first_cap = slot(budget, 65536 + n * 256)
                            a, b = side_indices(channel, contrast, part)
                            aa, bb, strata = matching(channel, feature["z"], a, b, design, np, assignment, budget)
                            selected_pairs.append({"part": part, "pair_count": len(aa),
                                                   "a": [channel["ids"][i] for i in aa],
                                                   "b": [channel["ids"][i] for i in bb]})
                            values = {}
                            for side, selected, paired in (("a", aa, bb), ("b", bb, aa)):
                                cap = first_cap if side == "a" else slot(budget, 65536 + n * 256)
                                key = f"{channel['id']}:{design}:{contrast}:{part}:{side}"
                                progress["condition_entered"] = key
                                metrics, status, why, rng, frequencies = condition(feature, selected, key, np, budget)
                                values[side] = metrics
                                dispositions.append({"design": design, "contrast": contrast, "part": part,
                                                     "side": side, "status": status, "reasons": why})
                                condition_count += 1
                                progress["conditions_completed"].append(key)
                                payload = {"channel": channel["id"], "design": design, "contrast": contrast,
                                           "part": part, "side": side, "selected_trial_ids": [channel["ids"][i] for i in selected],
                                           "paired_trial_ids": [channel["ids"][i] for i in paired], "strata": strata,
                                           "pair_count": len(selected), "metrics": metrics, "status": status,
                                           "reasons": why, "rng_evidence": rng, "frequency_evidence": frequencies}
                                yield event("condition_result", payload, world, person, lineage, budget, cap)
                                budget.tick()
                                progress["condition_entered"] = None
                            if values["a"] is not None and values["b"] is not None:
                                differences.append({name: values["a"][name] - values["b"][name] for name in METRICS})
                            else:
                                reasons.append("unsupported_required_condition_part_" + str(part))
                        metrics = equal_mean(differences) if len(differences) == len(parts) else None
                        estimates.append({"design": design, "contrast": contrast, "metrics": metrics,
                                          "matched_pairs": selected_pairs, "unsupported_reasons": list(dict.fromkeys(reasons))})
                        if metrics is not None:
                            session_vectors[(design, contrast)].setdefault(channel["session"], []).append(metrics)
                phase = "channel_result"
                progress["channels_completed"].append(channel["id"])
                yield event("channel_result", {"channel": channel["id"], "session": channel["session"],
                            "estimates": estimates, "condition_dispositions": dispositions,
                            "analytic_calls": 0 if feature is None else feature["analytic_calls"]},
                            world, person, lineage, budget, channel_cap)
                budget.tick()
            progress["channel_entered"] = None
        phase = "person_aggregation"
        cap = slot(budget, 16384 + 96 * (len(channel_ids) + len(sessions)))
        rows = []
        for design in DESIGNS:
            for contrast in CONTRASTS:
                per_session = session_vectors[(design, contrast)]
                session_means = [equal_mean(per_session[s]) for s in sorted(per_session)]
                metrics = equal_mean(session_means) if session_means else None
                rows.append({"patient": person, "design": design, "contrast": contrast,
                             "n_sessions": len(session_means),
                             "n_channels": sum(len(v) for v in per_session.values()), "metrics": metrics})
        yield event("person_result", {"rows": rows, "channel_ids": list(channel_ids), "session_ids": list(sessions),
                                      "condition_count": condition_count, "channel_count": len(channel_ids)},
                    world, person, lineage, budget, cap)
        budget.tick()
    except Exception as error:
        failure = failure_context(error, budget, phase, progress)
        if failure is error:
            raise
        raise failure from error


def validate_person_record(record, person, world):
    require(type(record) is dict and set(record) ==
            {"schema", "reference", "world", "person", "kind", "payload", "lineage", "budget"}, "person_event_keys")
    require(record["schema"] == "neural042_reference_event_v1" and record["reference"] == REFERENCE
            and record["world"] == world and record["person"] == person
            and record["kind"] == "person_result", "person_event_identity")
    validate_lineage(record["lineage"])
    validate_snapshot(record["budget"])
    payload = record["payload"]
    require(type(payload) is dict and set(payload) ==
            {"rows", "channel_ids", "session_ids", "condition_count", "channel_count"}, "person_result_payload")
    for key in ("channel_ids", "session_ids"):
        values = payload[key]
        require(type(values) is list and all(identity(v) for v in values)
                and values == sorted(set(values)), "person_result_sorted_ids")
    require(1 <= len(payload["session_ids"]) <= 44, "person_result_complete_sessions")
    require(type(payload["channel_count"]) is int and payload["channel_count"] == len(payload["channel_ids"])
            and type(payload["condition_count"]) is int
            and 0 <= payload["condition_count"] <= 12 * payload["channel_count"]
            and payload["condition_count"] % 12 == 0, "person_result_counts")
    rows = payload["rows"]
    require(type(rows) is list and len(rows) == 4, "four_person_rows")
    for row, (design, contrast) in zip(rows, [(d, c) for d in DESIGNS for c in CONTRASTS]):
        require(type(row) is dict and set(row) ==
                {"patient", "design", "contrast", "n_sessions", "n_channels", "metrics"}, "canonical_person_row_keys")
        require((row["patient"], row["design"], row["contrast"]) == (person, design, contrast), "canonical_person_row_order")
        ns, nc, metrics = row["n_sessions"], row["n_channels"], row["metrics"]
        require(type(ns) is int and type(nc) is int and 0 <= ns <= len(payload["session_ids"])
                and ns <= nc <= payload["channel_count"], "typed_person_support_counts")
        if metrics is None:
            require(ns == nc == 0, "null_support_counts")
        else:
            require(ns > 0 and type(metrics) is dict and set(metrics) == set(METRICS)
                    and all(number(v) for v in metrics.values()), "complete_finite_person_metrics")
            for key in ("mi", "trial_null", "shift_null", "early_mi", "late_mi", "harmonic_plv"):
                require(-1 <= metrics[key] <= 1, "contrast_analytic_range")
            require(-2 <= metrics["corrected_mi"] <= 2 and -2 <= metrics["waveform_asymmetry"] <= 2,
                    "corrected_and_shape_contrast_range")
    return rows


def group_statistic(values, design, contrast, np, budget):
    n = len(values)
    if n < 2:
        return {"design": design, "contrast": contrast, "n_patients": n,
                "mean": None, "ci95": None, "sign_flip_p": None}, {"entered": False}
    budget.reserve("elements", 10000 * n * 6 + n + 40000)
    budget.reserve("work_units", 10000 * n * 32 + 10000 * 16)
    identity_value = design + ":" + contrast
    numeric_seed = seed(identity_value)
    with budget.hold(10000 * n * 8 * 6 + 10000 * 8 * 8 + 65536):
        vector = np.asarray(values, dtype=np.float64)
        rng = np.random.default_rng(numeric_seed)
        start = rng.bit_generator.state
        indices = rng.integers(0, n, size=(10000, n))
        bootstrap = np.mean(vector[indices], axis=1)
        ci = np.quantile(bootstrap, [0.025, 0.975], method="linear")
        signs = rng.choice([-1, 1], size=(10000, n))
        null = np.mean(signs * vector, axis=1)
        center = float(np.mean(vector))
        probability = (1 + int(np.count_nonzero(np.abs(null) >= abs(center)))) / 10001
        require(np.isfinite(bootstrap).all() and np.isfinite(ci).all() and math.isfinite(center), "finite_group_statistics")
        budget.tick()
        row = {"design": design, "contrast": contrast, "n_patients": n,
               "mean": center, "ci95": [float(v) for v in ci], "sign_flip_p": probability}
        evidence = {"entered": True, "identity": identity_value, "seed": numeric_seed, "start_state": start,
                    "end_state": rng.bit_generator.state, "generator": "PCG64", "numpy": "2.2.6",
                    "bootstrap_call": "integers(0,n,size=(10000,n))",
                    "sign_call_after_bootstrap": "choice([-1,1],size=(10000,n))",
                    "shape": [10000, n], "quantile": "linear", "draw_order": "bootstrap_then_signs"}
        return row, evidence


def aggregate_world(person_records, roster, world, budget):
    """Reserve persistent row/pin metadata without pretending it is physical RSS."""
    try:
        require(isinstance(budget, Budget), "reference_budget")
        require(type(person_records) is list and len(person_records) == 36
                and type(roster) is list and len(roster) == 36, "complete36_sorted_roster")
        total_channels = total_sessions = 0
        for record in person_records:
            require(type(record) is dict and type(record.get("payload")) is dict, "person_event_keys")
            for key in ("channel_ids", "session_ids"):
                require(type(record["payload"].get(key)) is list, "person_result_sorted_ids")
            total_channels += len(record["payload"]["channel_ids"])
            total_sessions += len(record["payload"]["session_ids"])
        budget.reserve("elements", 8192 + 16 * (total_channels + total_sessions))
        with budget.hold(2097152 + 8192 * 36 + 1024 * total_channels + 256 * total_sessions):
            yield from aggregate_world_calculation(person_records, roster, world, budget)
    except Exception as error:
        failure = failure_context(error, budget, "world_persistent_metadata", {})
        if failure is error:
            raise
        raise failure from error


def aggregate_world_calculation(person_records, roster, world, budget):
    phase, progress = "world_admission", {"people_admitted": [], "groups_completed": []}
    try:
        require(isinstance(budget, Budget), "reference_budget")
        budget.tick()
        require(world in ("O", "D") and type(roster) is list and len(roster) == 36
                and all(identity(v) for v in roster) and roster == sorted(set(roster)), "complete36_sorted_roster")
        require(type(person_records) is list and len(person_records) == 36, "all36_final_person_events")
        np, _, _ = libraries()
        shared, patients, pins = None, [], []
        all_sessions, all_channels = set(), set()
        # Bound the exact canonical encodings before serialization, including caller-held nested metadata.
        for record, person in zip(person_records, roster):
            rows = validate_person_record(record, person, world)
            session_ids, channel_ids = record["payload"]["session_ids"], record["payload"]["channel_ids"]
            require(not all_sessions.intersection(session_ids) and not all_channels.intersection(channel_ids),
                    "distinct_person_session_and_channel_ids")
            budget.reserve("elements", 128 + 8 * (len(session_ids) + len(channel_ids)))
            all_sessions.update(session_ids)
            all_channels.update(channel_ids)
            present = {k: v for k, v in record["lineage"].items() if k != "packet"}
            require(shared is None or present == shared, "shared_reference_lineage")
            shared = present
            bound = 32768 + 128 * (len(record["payload"]["channel_ids"]) + len(record["payload"]["session_ids"]))
            budget.reserve("serialized_bytes", bound)
            with budget.hold(bound * 3):
                raw = canonical(record)
                require(len(raw) <= bound, "bounded_person_event_encoding")
                pins.append({"person": person, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            patients.extend(rows)
            progress["people_admitted"].append(person)
        require(len(all_sessions) == 44, "complete44_session_support")
        # ABI refinement: packet is the ordered complete person-event pin-list descriptor.
        budget.reserve("serialized_bytes", 16384)
        with budget.hold(49152):
            raw_pins = canonical(pins)
            require(len(raw_pins) <= 16384, "bounded_world_packet_descriptor")
            lineage = dict(shared, packet={"bytes": len(raw_pins), "sha256": hashlib.sha256(raw_pins).hexdigest()})
        phase = "group_aggregation"
        groups = []
        for design in DESIGNS:
            for contrast in CONTRASTS:
                cap = slot(budget, 16384)
                supported = [r for r in patients if r["design"] == design and r["contrast"] == contrast
                             and r["metrics"] is not None]
                row, evidence = group_statistic([r["metrics"]["corrected_mi"] for r in supported], design, contrast, np, budget)
                groups.append(row)
                progress["groups_completed"].append(design + ":" + contrast)
                yield event("group_result", {"row": row, "supported_person_ids": [r["patient"] for r in supported],
                                            "rng_evidence": evidence}, world, None, lineage, budget, cap)
                budget.tick()
        phase = "world_result"
        cap = slot(budget, 262144)
        report = {"schema": "neural042_report_v1", "patients": patients, "groups": groups, "claim_scope": CLAIM_SCOPE}
        yield event("world_result", {"report": report, "person_ids": list(roster), "person_result_pins": pins},
                    world, None, lineage, budget, cap)
        budget.tick()
    except Exception as error:
        failure = failure_context(error, budget, phase, progress)
        if failure is error:
            raise
        raise failure from error
