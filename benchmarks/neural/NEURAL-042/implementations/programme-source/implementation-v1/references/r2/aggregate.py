"""Independent complete-person aggregation and exact declared group RNG calls."""
import hashlib
import math
from .budget import ReferenceFailure, require, real
from .numeric import libraries
from .protocol import (METRICS, DESIGNS, CONTRASTS, EventSlot, REFERENCE, opaque,
                       lineage_valid, canonical_bytes, seed, state_copy, metrics_valid)

CLAIM_SCOPE = "descriptive_patient_associations_not_causal_or_crossoscillator_proof"


def _group_summary(values, identity, budget):
    n = len(values)
    if n < 2:
        return {"n_patients": n, "mean": None, "ci95": None, "sign_flip_p": None}, {
            "status": "unentered", "reason": "fewer_than_two_people"}
    np = libraries()
    require(all(type(x) in (int, float) and math.isfinite(x) for x in values),
            "group_finite", budget)
    size = 10000 * n
    with budget.numeric(10 * size + 24 * 10000, 20 * size + 200000,
                        144 * size + 192 * 10000 + 4096):
        d = np.asarray(values, dtype=np.float64)
        rng_seed = seed(identity, budget)
        generator = np.random.default_rng(rng_seed)
        start = state_copy(generator, budget)
        budget.tick()
        bootstrap_indices = generator.integers(0, n, size=(10000, n))
        bootstrap = np.mean(d[bootstrap_indices], axis=1)
        # The entire bootstrap draw precedes the entire sign draw.
        signs = generator.choice([-1, 1], size=(10000, n))
        flips = np.mean(signs * d[None, :], axis=1)
        budget.tick()
        mean = float(np.mean(d))
        ci = np.quantile(bootstrap, [0.025, 0.975], method="linear")
        pvalue = (1 + int(np.count_nonzero(np.abs(flips) >= abs(mean)))) / 10001
        budget.reserve("serialized_bytes", 16 * size)
        hashes = []
        for array in (bootstrap_indices, signs):
            contiguous = np.asarray(array, dtype="<i8", order="C")
            hashes.append(hashlib.sha256(memoryview(contiguous).cast("B")).hexdigest())
        answer = {"n_patients": n, "mean": mean, "ci95": [float(ci[0]), float(ci[1])],
                  "sign_flip_p": pvalue}
        evidence = {"status": "entered", "identity": identity, "seed": rng_seed,
                    "bit_generator": "PCG64", "numpy": "2.2.6",
                    "start_state": start, "end_state": state_copy(generator, budget),
                    "calls": ["integers(0,n,size=(10000,n))", "choice([-1,1],size=(10000,n))"],
                    "shape": [10000, n], "bootstrap_indices_sha256": hashes[0],
                    "signs_sha256": hashes[1], "commitment_encoding": "C-order little-endian signed int64",
                    "quantile": "linear", "extremeness": "absolute mean greater than or equal"}
        budget.tick()
        return answer, evidence


def _budget_record(value, budget):
    fields = {"origin", "deadline", "limits", "reservations", "planned_live_current",
              "planned_live_peak", "failures", "physical_RSS_measured"}
    require(type(value) is dict and set(value) == fields, "producer_budget_fields", budget)
    require(real(value["origin"]) and real(value["deadline"])
            and value["deadline"] > value["origin"], "producer_clocks", budget)
    require(value["physical_RSS_measured"] is False and value["failures"] == [],
            "successful_producer_budget", budget)
    require(type(value["limits"]) is dict and set(value["limits"]) ==
            {"elements", "work_units", "serialized_bytes", "events", "live_bytes"},
            "producer_limits", budget)
    require(type(value["reservations"]) is dict and set(value["reservations"]) ==
            {"elements", "work_units", "serialized_bytes", "events"},
            "producer_reservations", budget)
    for k, v in value["limits"].items():
        require(type(v) is int and v > 0, "producer_limit_integer", budget)
    for k, v in value["reservations"].items():
        require(type(v) is int and 0 <= v <= value["limits"][k],
                "producer_reservation_integer", budget)
    current, peak = value["planned_live_current"], value["planned_live_peak"]
    require(type(current) is int and type(peak) is int
            and 0 <= current <= peak <= value["limits"]["live_bytes"],
            "producer_live_record", budget)


def _person_event(event, person, world, budget):
    require(type(event) is dict and set(event) ==
            {"schema", "reference", "world", "person", "kind", "payload", "lineage", "budget"},
            "person_event_fields", budget)
    require(event["schema"] == "neural042_reference_event_v1"
            and event["reference"] == REFERENCE and event["world"] == world
            and event["person"] == person and event["kind"] == "person_result",
            "person_event_identity", budget)
    lineage_valid(event["lineage"], budget)
    _budget_record(event["budget"], budget)
    payload = event["payload"]
    require(type(payload) is dict and set(payload) ==
            {"rows", "channel_ids", "session_ids", "condition_count", "channel_count"},
            "person_payload_fields", budget)
    require(type(payload["channel_ids"]) is list and type(payload["session_ids"]) is list,
            "person_id_lists", budget)
    budget.reserve("elements", 1024 + 64 * (len(payload["channel_ids"]) + len(payload["session_ids"])))
    budget.reserve("work_units", 1024 + 64 * (len(payload["channel_ids"]) + len(payload["session_ids"])))
    for key in ("channel_ids", "session_ids"):
        require(type(payload[key]) is list, "complete_person_ids", budget)
        for identity in payload[key]:
            opaque(identity, budget)
        require(payload[key] == sorted(set(payload[key])), "person_ids_sorted_unique", budget)
    require(len(payload["session_ids"]) <= 44, "person_session_extent", budget)
    require(type(payload["channel_count"]) is int
            and payload["channel_count"] == len(payload["channel_ids"])
            and type(payload["condition_count"]) is int
            and 0 <= payload["condition_count"] <= 12 * payload["channel_count"],
            "person_disposition_counts", budget)
    require(type(payload["rows"]) is list and len(payload["rows"]) == 4,
            "complete_person_rows", budget)
    for row, (design, contrast) in zip(payload["rows"], ((d, c) for d in DESIGNS for c in CONTRASTS)):
        require(type(row) is dict and set(row) ==
                {"patient", "design", "contrast", "n_sessions", "n_channels", "metrics"}
                and (row["patient"], row["design"], row["contrast"]) == (person, design, contrast),
                "person_row_identity", budget)
        ns, nc = row["n_sessions"], row["n_channels"]
        require(type(ns) is int and type(nc) is int
                and 0 <= ns <= len(payload["session_ids"])
                and 0 <= nc <= payload["channel_count"], "row_support_counts", budget)
        if row["metrics"] is None:
            require(ns == nc == 0, "null_row_zero_support", budget)
        else:
            require(0 < ns <= nc, "supported_row_positive_counts", budget)
            metrics_valid(row["metrics"], budget)
    return payload


def aggregate_world(person_records, roster, world, budget):
    """Exactly 36 same-world person_result records; no reference-result callback."""
    phase = "aggregate_admission"
    try:
        budget.tick()
        require(world in ("O", "D") and type(roster) is list and len(roster) == 36,
                "complete_world_roster", budget)
        for p in roster:
            opaque(p, budget)
        require(roster == sorted(set(roster)), "world_unique_sorted_people", budget)
        require(type(person_records) is list and len(person_records) == 36,
                "complete_person_results", budget)
        libraries(production=True)
        budget.reserve("elements", 20000)
        budget.reserve("serialized_bytes", 65536)
        metadata_capacity = 65536
        for event in person_records:
            require(type(event) is dict and type(event.get("payload")) is dict, "person_metadata_shape", budget)
            for key in ("channel_ids", "session_ids"):
                value = event["payload"].get(key)
                require(type(value) is list, "person_metadata_ids", budget)
                metadata_capacity += 1024 * len(value)
        with budget.live(metadata_capacity):
            payloads, pins = [], []
            shared = None
            all_channels, all_sessions = set(), set()
            for person, event in zip(roster, person_records):
                # Reserve all incoming metadata traversal/serialization before inspection.
                budget.reserve("elements", 4096)
                payload = _person_event(event, person, world, budget)
                current_shared = {k: event["lineage"][k] for k in
                                  ("source", "environment", "reference_source", "protocol")}
                if shared is None:
                    shared = current_shared
                require(current_shared == shared, "shared_source_environment_protocol", budget)
                require(all_channels.isdisjoint(payload["channel_ids"])
                        and all_sessions.isdisjoint(payload["session_ids"]),
                        "cross_person_session_channel_alias", budget)
                all_channels.update(payload["channel_ids"])
                all_sessions.update(payload["session_ids"])
                capacity = 32768 + 256 * (len(payload["channel_ids"]) + len(payload["session_ids"]))
                raw = canonical_bytes(event, budget, capacity)
                pins.append({"person": person, "bytes": len(raw),
                             "sha256": hashlib.sha256(raw).hexdigest()})
                payloads.append(payload)
            # The owner authenticates complete 44/36 source membership externally.
            manifest = canonical_bytes(pins, budget, 32768)
            lineage = dict(shared)
            lineage["packet"] = {"bytes": len(manifest), "sha256": hashlib.sha256(manifest).hexdigest()}
            groups = []
            for row_index, (design, contrast) in enumerate((d, c) for d in DESIGNS for c in CONTRASTS):
                phase = "group:" + design + ":" + contrast
                slot = EventSlot(world, None, "group_result", lineage, budget, 32768)
                supported = [(person, payload["rows"][row_index]["metrics"]["corrected_mi"])
                             for person, payload in zip(roster, payloads)
                             if payload["rows"][row_index]["metrics"] is not None]
                summary, rng = _group_summary([value for _, value in supported],
                                              design + ":" + contrast, budget)
                row = {"design": design, "contrast": contrast, **summary}
                groups.append(row)
                yield slot.finish({"row": row, "supported_person_ids": [p for p, _ in supported],
                                   "rng_evidence": rng})
            phase = "world_result"
            final = EventSlot(world, None, "world_result", lineage, budget,
                              131072 + 256 * sum(len(p["channel_ids"]) for p in payloads))
            report = {"schema": "neural042_report_v1",
                      "patients": [row for p in payloads for row in p["rows"]],
                      "groups": groups, "claim_scope": CLAIM_SCOPE}
            yield final.finish({"report": report, "person_ids": list(roster), "person_result_pins": pins})
    except ReferenceFailure as exc:
        exc.record["phase"] = phase
        raise
    except Exception as exc:
        raise ReferenceFailure("unexpected_aggregation_failure",
                               {"status": "failed", "phase": phase,
                                "error_type": type(exc).__name__,
                                "budget": budget.snapshot()}) from exc

