"""Read-only admission of exact fresh whole-person provider custody.

This module never sends HTTP or imports a token-bound callback. Public admission
loads only source-pinned runtime code. The current provider's 1500-image guard
continues to reject both canonical people; helper replay is not qualification.
"""
import io
import json
import math
import os
from pathlib import Path

import common as C

CONDITION = "whole_person_raw_viewer_zero_shot"
EVIDENCE_SCHEMA = "sleep007_fresh_viewer_evidence_v1"
EVENT_SCHEMA = "neural007_viewer_provider_event_v1"


def exact_inventory(root, names):
    root = C.path(root)
    C.need(root.is_dir() and {p.name for p in root.iterdir()} == set(names),
           "exact complete evidence inventory")
    return root


def http_receipt(value, config_pin, request, response, deadline):
    """Same successful HTTPS custody contract as the unchanged N077 sender."""
    fixed = {"schema": "neural077_https_binding_v1", "config_pin": config_pin,
             "endpoint": "https://api.openai.com/v1/responses",
             "request": C.pin(request), "response": C.pin(response),
             "status_code": 200, "request_complete": True,
             "response_complete": True, "body_overflow": False,
             "requests_attempted": 1, "redirects_followed": 0, "retries": 0,
             "connection_closed": True, "credential_retained": False,
             "failure": None, "deadline": deadline}
    C.need(type(value) is dict and set(value) == set(fixed) |
           {"started_monotonic", "finished_monotonic"}, "complete HTTP receipt")
    C.need(all(type(value[k]) is type(v) and value[k] == v for k, v in fixed.items()),
           "exact HTTPS request, response and no-retry policy")
    C.need(all(type(value[k]) in (int, float) and math.isfinite(value[k])
               for k in ("started_monotonic", "finished_monotonic")), "finite HTTP clock")
    C.need(value["started_monotonic"] <= value["finished_monotonic"] <= deadline,
           "complete provider exchange within original deadline")
    return value["started_monotonic"], value["finished_monotonic"]


class WireReplay:
    """One bounded frame at a time; writes verify captured original actions."""
    def __init__(self, stream, transport):
        self.stream, self.t = stream, transport
        self.pending = b""
        self.sequence, self.actions, self.images = 0, 0, 0
        self.answers = {}

    def frame(self, inbound):
        C.need(self.sequence % 2 == int(inbound), "alternating exact wire directions")
        prefix = self.stream.read(self.t.PREFIX.size)
        C.need(len(prefix) == self.t.PREFIX.size, "complete wire prefix")
        hs, ps = self.t.PREFIX.unpack(prefix)
        C.need(0 < hs <= (self.t.MAX_REQUEST if inbound else self.t.HEADER_MAX)
               and 0 <= ps <= self.t.PNG_MAX and (not inbound or ps == 0),
               "bounded exact original wire frame")
        body = self.stream.read(hs + ps)
        C.need(len(body) == hs + ps, "complete wire body")
        self.sequence += 1
        if not inbound:
            self.images += bool(ps)
        return prefix + body

    def read(self, size):
        C.need(type(size) is int and size > 0, "bounded replay read")
        if not self.pending:
            self.pending = self.frame(False)
        value, self.pending = self.pending[:size], self.pending[size:]
        return value

    def write(self, value):
        C.need(type(value) is bytes and not self.pending, "action after complete observation")
        expected = self.frame(True)
        C.need(value == expected, "provider action equals exact original wire action")
        action, png = self.t.unpack(value, inbound=True)
        C.need(not png, "no image in participant action")
        self.actions += 1
        if action.get("action") == "respond":
            epoch = action["epoch_id"]
            C.need(epoch not in self.answers, "irreversible first accepted epoch answer")
            self.answers[epoch] = action["probabilities"]
        return len(value)

    def flush(self):
        return None

    def closed(self):
        C.need(not self.pending and self.stream.read(1) == b"", "no extra wire after finish")


def audit_provider_session(provider_root, transport_root, client, runtime):
    """Verify custody by replay, without credentials, HTTP, or new observations.

    Dependency injection belongs to this component helper. Public ``admit``
    below supplies only the source-authenticated original runtime; no test-mode
    or caller-supplied qualification switch exists in that entrypoint.
    """
    p, t = runtime["provider"], runtime["transport"]
    root = exact_inventory(provider_root, {"CONFIG.json", "events", "turns", "CLIENT_END.json"})
    config_raw = C.snapshot(root / "CONFIG.json", 65536)
    config, config_pin = p.decode(config_raw), C.pin(config_raw)
    C.need(config_raw == p.encode(config), "canonical immutable session configuration")
    budget = client.checked_config(config, runtime)
    end = p.decode(C.snapshot(root / "CLIENT_END.json", 65536))
    C.need(type(end) is dict and end.get("status") == "complete_unscored",
           "failed or partial provider session cannot be admitted")
    deadline = end.get("deadline")
    C.need(type(deadline) in (int, float) and math.isfinite(deadline), "finite original deadline")
    events, turns, request_bytes, response_bytes = 0, 0, 0, 0
    previous_http_end = deadline - budget.wall_seconds
    response_ids = []

    def event():
        raw = C.snapshot(root / "events" / f"{events:06d}.json", 65536)
        wrapper = p.decode(raw)
        C.need(type(wrapper) is dict and set(wrapper) == {"schema", "config", "deadline", "bridge"}
               and wrapper["schema"] == EVENT_SCHEMA and wrapper["config"] == config_pin
               and type(wrapper["deadline"]) is type(deadline) and wrapper["deadline"] == deadline
               and raw == p.encode(wrapper), "exact ordered private provider event")
        return wrapper, raw

    def token_bound(request, replay_deadline):
        wrapper, _ = event()
        meta = wrapper["bridge"]
        C.need(meta.get("event") == "exchange" and meta.get("request") == C.pin(request),
               "token bound belongs to exact reconstructed complete request")
        bound = meta.get("input_token_bound")
        C.need(type(bound) is int and bound > 0, "recorded conservative token bound")
        return bound

    def send_json(request, replay_deadline):
        nonlocal turns, request_bytes, response_bytes, previous_http_end
        row = exact_inventory(root / "turns" / f"{turns:06d}",
                              {"REQUEST.bin", "RESPONSE.bin", "HTTP.json", "BRIDGE.json"})
        saved_request = C.snapshot(row / "REQUEST.bin", min(8 * 2**20, budget.max_request_bytes))
        response = C.snapshot(row / "RESPONSE.bin", budget.max_response_bytes)
        C.need(saved_request == request, "full exact PNG and visible context request lineage")
        value = p.decode(C.snapshot(row / "HTTP.json", 16384))
        started, finished = http_receipt(value, config_pin, request, response, deadline)
        C.need(previous_http_end <= started, "ordered nonoverlapping provider exchanges")
        previous_http_end = finished
        wrapper, _ = event()
        C.need(C.snapshot(row / "BRIDGE.json", 65536) == runtime["sender"].encode(wrapper)
               and wrapper["bridge"].get("sender_calls_attempted") == 1,
               "sender-owned exchange custody bound to exact bridge event")
        request_bytes += len(request)
        response_bytes += len(response)
        turns += 1
        return response

    def record(metadata, request, response):
        nonlocal events
        wrapper, _ = event()
        C.need(p.encode(wrapper["bridge"]) == p.encode(metadata), "recomputed complete bridge event and hash chain")
        C.need(metadata["request"] == (None if request is None else C.pin(request))
               and metadata["response"] == (None if response is None else C.pin(response)),
               "exact event body identities")
        if metadata["event"] == "exchange":
            C.need(metadata.get("status") == "action_prepared_unscored"
                   and metadata.get("sender_calls_attempted") == 1, "successful original provider exchange")
            identity = metadata["provider_response_id"]
            C.need(identity not in response_ids, "no reused provider response identity")
            response_ids.append(identity)
        events += 1

    bridge = p.Bridge(task="NEURAL-007", condition=CONDITION, model=config["model"],
                      budget=budget, send_json=send_json, input_token_bound=token_bound, record=record)
    wire_path = C.path(transport_root) / "transport" / "wire.bin"
    # The authenticated transport's own limits bound its captured wire file.
    boundary = p.decode(C.snapshot(C.path(transport_root) / "BOUNDARY.json", 65536))
    limits = t.Limits(**boundary["limits"])
    limits.validate(dict(C.SPEC_CASES)[config["case_id"]])
    stream, before = t.ordinary(wire_path, limits.max_output_bytes + limits.max_actions * (t.MAX_REQUEST + t.PREFIX.size))
    try:
        wire = WireReplay(stream, t)
        terminal = bridge.serve(wire, wire)
        wire.closed()
        C.need(t.identity(before) == t.identity(os.fstat(stream.fileno())) == t.identity(wire_path.stat()),
               "wire evidence stable throughout provider replay")
    finally:
        stream.close()
    exact_inventory(root / "events", {f"{i:06d}.json" for i in range(events)})
    exact_inventory(root / "turns", {f"{i:06d}" for i in range(turns)})
    expected = {"schema": "neural007_viewer_provider_end_v1", "config": config_pin,
                "case_id": config["case_id"], "condition": CONDITION, "status": "complete_unscored",
                "events": events, "turns": turns, "request_bytes": request_bytes,
                "response_bytes": response_bytes, "response_charge_contains_upper_bound": False,
                "episode_id": bridge.p.episode, "deadline": deadline, "terminal": C.pin(p.encode(terminal)),
                "provider_capacity_qualified": False, "provider_context_qualified": False,
                "scientific_qualification": False, "token_bound_qualified": False, "error_type": None}
    C.need(p.encode(end) == p.encode(expected), "exact complete provider closure; no qualification manufactured")
    C.need(turns == wire.actions and len(response_ids) == turns,
           "every original action has one authenticated provider exchange")
    return {"config": config, "end": end, "answers": wire.answers,
            "response_ids": response_ids, "wire_records": wire.sequence, "images": wire.images}


def checked_evidence(value):
    C.need(type(value) is dict and set(value) == {"schema", "condition", "rows", "collection", "viewer_collection"}
           and value["schema"] == EVIDENCE_SCHEMA and value["condition"] == CONDITION,
           "exact canonical fresh viewer evidence request")
    rows = value["rows"]
    C.need(type(rows) is list and len(rows) == 2, "both original development people")
    for row, (case, epochs) in zip(rows, C.SPEC_CASES):
        C.need(type(row) is dict and set(row) == {"case_id", "epochs", "packet_root", "transport_root", "provider_root"}
               and row["case_id"] == case and type(row["epochs"]) is int and row["epochs"] == epochs,
               "all 5450 original epochs in canonical order")
        for name in ("packet_root", "transport_root", "provider_root"):
            C.need(type(row[name]) is str and Path(row[name]).is_absolute(), "absolute trusted evidence location")
            C.path(row[name])
    for name in ("packet_root", "transport_root", "provider_root"):
        C.need(len({row[name] for row in rows}) == 2, "distinct complete person evidence roots")
    return rows


def admit(proof, submission):
    """Both finite-workflow callers enter here before any private target load."""
    C.need(type(proof) is dict and set(proof) == {"fresh_provider"}, "exact fresh provider proof descriptor")
    value = json.loads(C.descriptor_read(proof["fresh_provider"], 65536))
    rows = checked_evidence(value)
    client = C._module("sleep007_fresh_provider_client", *C.original("fresh_provider_client"))
    runtimes, provider_rows = [], []
    for row in rows:
        cfg = json.loads(C.snapshot(C.path(row["provider_root"]) / "CONFIG.json", 65536))
        runtime = client.load_runtime(Path(cfg["root"]), Path(cfg["integration_root"]))
        C.need(cfg["case_id"] == row["case_id"], "matching original person configuration")
        client.checked_config(cfg, runtime)
        bound = cfg["token_bound_source"]
        C.need(bound is not None, "complete real CLI execution requires its frozen token-bound source")
        client.source_bytes(bound["path"], C.plain(bound))  # Authenticate only; never import or call it.
        # This invokes the unchanged Bridge.serve capacity gate before packet
        # construction. Current canonical people remain blocked at 1500 images.
        provider_rows.append(audit_provider_session(row["provider_root"], row["transport_root"], client, runtime))
        runtimes.append(runtime)
    shared = ("root", "integration_root", "model", "budget", "source", "token_bound_source")
    C.need(all({k: item["config"][k] for k in shared} ==
               {k: provider_rows[0]["config"][k] for k in shared} for item in provider_rows),
           "same original provider, source, full-history budget and token-bound source")
    C.need(len({item["end"]["episode_id"] for item in provider_rows}) == 2,
           "fresh independent local person contexts")
    identities = [identity for item in provider_rows for identity in item["response_ids"]]
    C.need(len(identities) == len(set(identities)), "no response reused between people")
    receipts = {}
    for row, runtime, provider in zip(rows, runtimes, provider_rows):
        t = runtime["transport"]
        packet = t.v.Packet(row["packet_root"], row["case_id"])
        try:
            receipt = t.audit_transport(row["transport_root"], packet)
        finally:
            packet.close()
        boundary, result = receipt["boundary"], receipt["result"]
        C.need(boundary["sandbox"] == "protocol_only"
               and boundary["client_sha256"] == C.original("fresh_provider_client")[1]["sha256"]
               and boundary["episode_id"] == provider["end"]["episode_id"]
               and result["actions"] == provider["end"]["turns"]
               and result["wire_records"] == provider["wire_records"] and result["images"] == provider["images"],
               "trusted client capture and exact replayed transport closure")
        expected_ids = {f"{row['case_id']}/{i:05d}" for i in range(row["epochs"])}
        C.need(set(provider["answers"]) == expected_ids, "all irreversible first epoch responses required")
        receipts[row["case_id"]] = receipt
    shared_boundary = ("schema", "mode", "limits", "sandbox", "client_sha256", "python", "source")
    boundaries = [receipt["boundary"] for receipt in receipts.values()]
    C.need(all({k: b[k] for k in shared_boundary} == {k: boundaries[0][k] for k in shared_boundary}
               for b in boundaries), "unchanged matching complete transport collection conditions")
    t = runtimes[0]["transport"]
    transport_collection = json.loads(C.descriptor_read(value["collection"], 65536))
    expected_transport = {"schema": "sleep-viewer-transport-collection/v1", "mode": CONDITION, "epochs": 5450,
                          "status": "complete_unscored", "sessions": receipts, "source": t.source_identity(),
                          "provider_context_qualified": False, "scientific_qualification": False,
                          "scope": "Complete local image/action transport and original validator only; not model interpretation or protected evaluation."}
    C.need(transport_collection == expected_transport, "exact original complete transport collection")
    collection = json.loads(C.descriptor_read(value["viewer_collection"], 16384))
    expected_collection = {"mode": CONDITION, "epochs": 5450, "submission": C.plain(submission),
                           "sessions": {case: receipt["viewer"] for case, receipt in receipts.items()},
                           "source": t.v.source_identity(),
                           "scope": "Source/packet/history replay and complete response validation only; no labels or model qualification."}
    C.need(collection == expected_collection, "unchanged original collector and prediction identity")
    base = C.path(value["viewer_collection"]["path"]).parent
    C.need(C.path(value["collection"]["path"]) == base / "TRANSPORT_COMPLETE.json"
           and C.path(value["viewer_collection"]["path"]) == base / "collection.json"
           and C.path(submission["path"]) == base / "predictions.npz", "one original complete collector output")
    _, adapter, _ = t.v.dependencies()
    spec = adapter.Specification(tuple(adapter.Case(case, count) for case, count in C.SPEC_CASES), ("YASA", "RF"))
    adapter.validate_submission(Path(submission["path"]), C.plain(submission), spec)
    raw = C.descriptor_read(submission, 4_000_000)
    import numpy as np
    with np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=4096) as arrays:
        for row, provider in zip(rows, provider_rows):
            ids = [f"{row['case_id']}/{i:05d}" for i in range(row["epochs"])]
            C.need(arrays[row["case_id"] + "__epoch_id"].tolist() == ids
                   and np.array_equal(arrays[row["case_id"] + "__probabilities"],
                                      np.asarray([provider["answers"][epoch] for epoch in ids], dtype=np.float64)),
                   "submission equals every exact first provider response without normalization")
    return {"schema": "sleep007_fresh_viewer_admitted_v1", "status": "complete_unscored",
            "epochs": 5450, "people": 2, "submission": C.plain(submission),
            "provider_calls": len(identities), "private_target_reads": 0,
            "provider_capacity_qualified": False, "provider_context_qualified": False,
            "scientific_qualification": False, "token_bound_qualified": False}
