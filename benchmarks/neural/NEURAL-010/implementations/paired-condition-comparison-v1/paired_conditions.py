"""Joint comparison of two complete, source-replayed seizure campaigns.

This trusted operator code does not run a participant, renderer, detector or
model. Generated transcripts and external declarations never qualify a native
observation condition. Only exact local upstream source is executable here.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
import types
import captured_replay as replay

LEGACY_MANIFEST = {"bytes": 1540, "sha256": "d6456b5cece5ce18d97181bd8e62a9e05d5d088b373cc7acca3a46798b8101d7"}
LEGACY_ENTRY = {"bytes": 10139, "sha256": "a4db3a377fd1f258839df85dfe4bfffe993c7c2a2eac36a32155abc926939c2e"}
METRICS = {"event_f1": "higher", "event_sensitivity": "higher",
           "false_alarms_per_24_observed_hours": "lower"}
need = replay.need


def load_legacy(root):
    """Load only the preserved closure, with its original captured importer."""
    root = Path(root).resolve(strict=True) / "vendor/event-campaign-v1"
    path = root / "entry.py"
    need(not any(p.is_symlink() for p in (path, *path.parents)), "ordinary fixed source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size == LEGACY_ENTRY["bytes"],
             "exact fixed upstream entry")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(LEGACY_ENTRY["bytes"] + 1)
        z, named = os.fstat(fd), path.lstat()
        fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        need(all(getattr(a, k) == getattr(z, k) == getattr(named, k) for k in fields)
             and len(raw) == LEGACY_ENTRY["bytes"]
             and hashlib.sha256(raw).hexdigest() == LEGACY_ENTRY["sha256"], "stable pinned entry")
    finally:
        os.close(fd)
    entry = types.ModuleType("neural010_preserved_event_entry")
    entry.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), entry.__dict__)
    actual_root, bodies, descriptors, load, reads, manifest = entry.bootstrap(
        LEGACY_MANIFEST["bytes"], LEGACY_MANIFEST["sha256"])
    return {"entry": entry, "root": actual_root, "u": load("common"),
            "campaign": load("campaign"), "reads": reads + len(raw) + 1,
            "source": dict(LEGACY_MANIFEST)}


def _argument_snapshot(request_raw, authority_raw, authority_pin, read_roots, output_root):
    need(type(request_raw) is bytes and type(authority_raw) is bytes
         and 0 < len(request_raw) <= 1048576 and 0 < len(authority_raw) <= 1048576,
         "bounded immutable paired selection bytes")
    authority_pin = replay.frozen(authority_pin)
    need(type(read_roots) in (list, tuple) and 1 <= len(read_roots) <= 32
         and all(type(p) is str for p in read_roots), "explicit bounded read roots")
    need(type(output_root) is str, "literal output root")
    return request_raw, authority_raw, authority_pin, tuple(read_roots), output_root


def _selection(raw, authority_raw, authority_pin, source_pin, u):
    request = u.parse(raw)
    u.exact(request, ("schema", "source", "left", "right", "limits", "capture_bytes"))
    need(request["schema"] == "neural010-paired-condition-request-v1"
         and u.c.same(request["source"], source_pin), "exact paired source selection")
    for side in ("left", "right"):
        u.exact(request[side], ("request", "authority"))
        for desc in request[side].values():
            u.c.descriptor(desc, True)
            need(desc["bytes"] <= 1048576, "bounded campaign score selection")
    u.c.descriptor(authority_pin)
    need(u.c.same(u.pin(authority_raw), authority_pin), "selected paired authority bytes")
    authority = u.parse(authority_raw)
    u.exact(authority, ("schema", "request", "source", "left", "right",
                        "assessment", "evidence_class", "interpretation"))
    need(authority["schema"] == "neural010-paired-condition-authority-v1"
         and u.c.same(authority["request"], u.pin(raw))
         and u.c.same(authority["source"], source_pin)
         and authority["interpretation"] == "descriptive_zero_training_access_conditions",
         "independent exact joint selection")
    for side in ("left", "right"):
        need(u.c.same(authority[side], request[side]), "same independently selected arm")
    u.c.descriptor(authority["assessment"], True)
    need(Path(authority["assessment"]["path"]).name == "assessment.json",
         "literal protected assessment selection")
    need(authority["evidence_class"] in ("generated_control", "operator_selected_deployment"),
         "explicit evidence class without qualification")
    return request, authority


def _disjoint_contexts(left, right, u):
    identifiers, paths = [], []
    for request in (left, right):
        for context in request["contexts"].values():
            identifiers.append(context["context_id"])
            paths.extend(p for k, p in context.items() if k.endswith("_exchange") and p is not None)
    need(len(identifiers) == 46 and len(set(identifiers)) == 46,
         "46 fresh disjoint cross-condition context identities")
    normalized = [Path(str(u.c.absolute(p)).casefold()) for p in paths]
    for i, a in enumerate(normalized):
        for b in normalized[i + 1:]:
            need(a != b and not a.is_relative_to(b) and not b.is_relative_to(a),
                 "cross-condition exchange namespaces must be disjoint")


def _matching(adapters, authorities, selection, u, output_root):
    actual, evaluations, provenance = {}, {}, {}
    for side, adapter in adapters.items():
        actual[side] = u.parse(adapter.unique_capture("frozen_original_request"))
        evaluations[side] = u.parse(adapter.unique_capture("frozen_evaluation_selection"))
        provenance[side] = u.parse(adapter.unique_capture("independent_reference_provenance"))
        need(authorities[side]["evidence_class"] == selection["evidence_class"],
             "generated evidence cannot be relabelled by comparison")
        need(adapter.assessment == replay.canonical(selection["assessment"]),
             "one identical selected assessment path/bytes/hash for both arms")
    a, b = actual["left"], actual["right"]
    need({a["mode"], b["mode"]} == {"typed_viewer", "frozen_program"},
         "one viewer and one frozen-program condition")
    need(a["policy"]["training"] == b["policy"]["training"] == "none",
         "zero training in both conditions; other22 is not matched")
    need(u.c.same(a["preparation"], b["preparation"]), "same complete source preparation selection")
    need(u.c.same(a["limits"], b["limits"]), "same selected participant resource limits")
    for key in ("learning_policy_sha256", "training_policy_sha256", "tuning_policy_sha256", "resource_policy_sha256"):
        need(a["candidate_contract"][key] == b["candidate_contract"][key], "same selected " + key)
    for key in ("max_actions_per_fold", "max_samples_per_request", "max_channels_per_request", "frame_bytes"):
        need(u.c.same(a["policy"][key], b["policy"][key]), "same observation opportunity " + key)
    need(adapters["left"].unique_capture("frozen_support") == adapters["right"].unique_capture("frozen_support"),
         "identical complete686/23 observation support")
    for key in ("references", "original_panel", "original_assessment", "interpretation"):
        need(u.c.same(evaluations["left"][key], evaluations["right"][key]), "same scoring evaluation " + key)
    for key in ("reference_pins", "reference_runs", "evidence_class"):
        need(u.c.same(provenance["left"][key], provenance["right"][key]), "same independent reference " + key)
    for role in ("independently_supplied_reference", "independent_matched_no_eeg_run_binding",
                 "independent_signal_reference_run_binding", "independent_montage_only_run_binding",
                 "independent_reference_closure"):
        need(adapters["left"].capture_multiset(role) == adapters["right"].capture_multiset(role),
             "same captured independent reference bodies: " + role)
    _disjoint_contexts(a, b, u)
    output = Path(str(u.c.absolute(str(output_root))).casefold())
    for original in (a, b):
        for context in original["contexts"].values():
            for key, path in context.items():
                if key.endswith("_exchange") and path is not None:
                    exchange = Path(str(u.c.absolute(path)).casefold())
                    need(output != exchange and not output.is_relative_to(exchange)
                         and not exchange.is_relative_to(output),
                         "comparison results must be outside participant/custody/renderer namespaces")
    return actual, evaluations, provenance


def _differences(left, right, expected_people):
    need(set(left) == set(right) == set(expected_people), "same complete paired person support")
    result = {}
    for metric, direction in METRICS.items():
        people, differences = {}, []
        for person in sorted(expected_people):
            x, y = left[person]["candidate"][metric], right[person]["candidate"][metric]
            for value in (x, y):
                need(value is None or (type(value) in (int, float) and math.isfinite(value)),
                     "finite original metric or preserved undefined")
            undefined = x is None or y is None
            delta = None if undefined else x - y
            if delta is not None:
                differences.append(delta)
            people[person] = {"left": x, "right": y, "left_minus_right": delta,
                              "undefined_reason": ("both_undefined" if x is None and y is None
                                  else "left_undefined" if x is None else "right_undefined") if undefined else None}
        n = len(expected_people)
        result[metric] = {"better_direction": direction, "difference": "left_minus_right",
                          "expected_people": n, "defined_people": len(differences), "people": people,
                          "complete_support_mean": math.fsum(differences) / n
                              if n and len(differences) == n else None,
                          "mean_policy": "equal-person mean only when every expected pair is defined"}
    return result


def compare(request_raw, authority_raw, authority_pin, *, source_pin, source_root,
            output_root, read_roots, initial_source_reads=0, started_monotonic=None):
    """Fixed filesystem route; no arbitrary provider, scorer or target callback."""
    now = time.monotonic()
    need(started_monotonic is None or (type(started_monotonic) in (int, float)
         and math.isfinite(started_monotonic) and 0 < started_monotonic <= now),
         "original nonfuture invocation start")
    origin = now if started_monotonic is None else started_monotonic
    request_raw, authority_raw, authority_pin, read_roots, output_root = _argument_snapshot(
        request_raw, authority_raw, authority_pin, read_roots, output_root)
    source_pin = replay.frozen(source_pin)
    need(type(initial_source_reads) is int and initial_source_reads >= 0, "source-read charge")
    legacy = load_legacy(source_root)
    u, campaign = legacy["u"], legacy["campaign"]
    request, authority = _selection(request_raw, authority_raw, authority_pin, source_pin, u)
    budget = u.Budget(request["limits"])
    budget.origin, budget.end = origin, origin + request["limits"]["seconds"]
    budget.charge("read_bytes", legacy["reads"] + initial_source_reads + len(request_raw) + len(authority_raw) + 2)
    retention = replay.Retention(request["capture_bytes"])
    roots = tuple(str(u.c.absolute(p)) for p in (*read_roots, str(Path(source_root).resolve()), output_root))
    io = u.IO(roots, budget)
    out = io.directory(output_root)
    io.create(out / "SELECTION.json", request_raw)
    io.create(out / "AUTHORITY.json", authority_raw)
    io.create(out / "RESERVATION.json", u.encoded({"schema": "neural010-paired-whole-reservation-v1",
              "request": u.pin(request_raw), "limits": request["limits"], "origin": origin,
              "deadline": budget.end, "capture_bytes": retention.maximum,
              "charges_retained_on_failure": True, "os_quota_or_qualification": False}))
    adapters, arguments, score_authorities = {}, {}, {}
    try:
        # Capture both selected score envelopes before either upstream replay.
        for side in ("left", "right"):
            chosen = request[side]
            raw = io.capture(chosen["request"], "paired_selected_score_request", 1048576)
            auth = io.capture(chosen["authority"], "paired_selected_score_authority", 1048576)
            request_doc, auth_doc = u.parse(raw), u.parse(auth)
            need(u.c.same(request_doc["source"], LEGACY_MANIFEST), "preserved campaign source only")
            need(u.c.same(auth_doc["assessment"], authority["assessment"]), "same selected common assessment")
            child = replay.ArmBudget(request_doc["limits"], budget, u)
            adapter = replay.CapturedIO(u.IO(roots, child), retention, u)
            adapters[side] = adapter
            arguments[side] = (raw, auth, u.c.bare(chosen["authority"]))
            score_authorities[side] = auth_doc
        for side in ("left", "right"):
            adapter = adapters[side]
            try:
                campaign.score(*arguments[side], source_pin=legacy["source"], source_root=legacy["root"],
                               output_root=out / side, io=adapter)
            except replay.DeferredAssessment as marker:
                need(marker is adapter.boundary and adapter.admission_hits == 1,
                     "only exact source-controlled target boundary admits a campaign")
                marker.__traceback__ = None
            else:
                raise ValueError("campaign returned before the required deferred target boundary")
        actual, evaluations, provenance = _matching(adapters, score_authorities, authority, u, out)
        need(adapters["left"].assessment_cap == adapters["right"].assessment_cap,
             "same original target capture cap")
        # The only physical protected-target capture in the comparison.
        retention.reserve(authority["assessment"]["bytes"])
        target = io.capture_assessment(authority["assessment"], adapters["left"].assessment_cap)
        outcomes, result_pins = {}, {}
        for side in ("left", "right"):
            adapter = adapters[side]
            adapter.enable_replay(target)
            result_pins[side] = campaign.score(*arguments[side], source_pin=legacy["source"],
                                               source_root=legacy["root"], output_root=out / side, io=adapter)
            need(adapter.replay_hits == 1 and adapter.cursor == len(adapter.events)
                 and adapter.created_body is not None, "complete exact score replay")
            outcomes[side] = u.parse(adapter.created_body)
        left, right = outcomes["left"], outcomes["right"]
        need(left["recordings"] == right["recordings"] == 686
             and left["biological_patients"] == right["biological_patients"] == 23,
             "complete original outcomes")
        people = tuple(sorted(left["patients"]))
        need(len(people) == 23 and left["observed_seconds"] == right["observed_seconds"],
             "same full observed-time denominator")
        need(set(left["montages"]) == set(right["montages"]), "same complete montage support")
        montage_pairs = {}
        for montage in sorted(left["montages"]):
            x, y = left["montages"][montage], right["montages"][montage]
            ids = tuple(sorted(x["patients"]))
            montage_pairs[montage] = {"expected_people": len(ids), "single_person_support": len(ids) == 1,
                                     "metrics": _differences(x["patients"], y["patients"], ids)}
        result = {"schema": "neural010-paired-condition-outcomes-v1", "task_id": "NEURAL-010",
                  "recordings": 686, "people": 23, "observed_seconds": left["observed_seconds"],
                  "original_result_summaries": {s: {k: outcomes[s][k] for k in
                      ("schema", "recordings", "biological_patients", "observed_seconds")}
                      for s in ("left", "right")},
                  "original_result_pins": result_pins,
                  "paired_metrics": _differences(left["patients"], right["patients"], people),
                  "paired_montages": montage_pairs,
                  "conditions": {s: {"mode": actual[s]["mode"], "policy": actual[s]["policy"],
                      "candidate_contract": actual[s]["candidate_contract"],
                      "selected_request": u.pin(adapters[s].unique_capture("frozen_original_request")),
                      "evaluation": u.pin(adapters[s].unique_capture("frozen_evaluation_selection")),
                      "reference_provenance": u.pin(adapters[s].unique_capture("independent_reference_provenance"))}
                      for s in ("left", "right")},
                  "joint_admission": {"physical_protected_assessment_captures": 1,
                      "assessment": authority["assessment"], "both_complete_before_target": True,
                      "captured_operand_replay_only": True, "capture_accounted_bytes": retention.used,
                      "source_kernels_reopened_with_original_hash_checks": True,
                      "events_per_arm": {s: len(adapters[s].events) for s in adapters}},
                  "evidence_class": authority["evidence_class"],
                  "scientific_qualification": False, "native_understanding_established": False,
                  "real_world_isolation_established": False, "rendering_fidelity_established": False,
                  "statistical_superiority_established": False, "ranking": None,
                  "interpretation": "Descriptive zero-training viewer versus numerical-program conditions. Representation and computational access differ together; this is not an isolated effect of tools. External selected receipts do not prove execution, isolation or competence.",
                  "costs_before_final_result": dict(budget.used)}
        body = u.encoded(result)
        return io.create(out / "COMPARISON.json", body)
    except BaseException as error:
        # Failure is never converted into a score or implicit empty detections.
        # Best-effort diagnostic output must not replace the original failure.
        try:
            io.create(out / "FAILURE.json", u.encoded({"schema": "neural010-paired-failure-v1",
                      "error_type": type(error).__name__, "comparison_complete": False,
                      "admission_boundary_hits": {s: a.admission_hits for s, a in adapters.items()},
                      "replay_target_uses": {s: a.replay_hits for s, a in adapters.items()},
                      "costs": dict(budget.used), "capture_accounted_bytes": retention.used,
                      "charges_retained_on_failure": True}))
        except BaseException:
            pass
        raise
