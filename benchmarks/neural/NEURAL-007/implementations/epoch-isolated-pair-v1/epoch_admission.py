"""Complete epoch-paired custody admission and protected original-metric comparison."""
from __future__ import annotations
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C
import epoch_programme as P

DECLARED_SCOPE = {"claim_matched_information": False, "matched_access_audit": None}


def _collection(descriptor, condition):
    value = C.decode(P.descriptor(descriptor, 8 * 2**20))
    keys = {"schema", "condition", "knowledge", "source", "rows", "submission"}
    C.need(type(value) is dict and set(value) in (keys, keys | {"comparison_scope"})
           and value["schema"] == "sleep007_epoch_arm_collection_v1"
           and value["condition"] == condition, "Explicit new condition; no whole-history pooling")
    value = dict(value, comparison_scope=value.get("comparison_scope", dict(DECLARED_SCOPE)))
    scope = value["comparison_scope"]
    P.M.check_claim(scope, {"claim_matched_information": scope.get("claim_matched_information")})
    P.source_freeze(value["source"])
    knowledge_raw = P.descriptor(value["knowledge"], 8192)
    knowledge = C.checked_knowledge(C.decode(knowledge_raw))
    C.need(C.encode(knowledge) == knowledge_raw, "Canonical shared prior declaration")
    C.checked_complete_rows(value["rows"])
    C.need(all(set(row) == {"epoch_id", "record"} for row in value["rows"]), "Only complete immutable row descriptors")
    return value, knowledge


def _visual_record(record, packet, runtime, knowledge, comparison_scope=None):
    import epoch_provider as V
    scope = dict(DECLARED_SCOPE) if comparison_scope is None else comparison_scope
    keys = {"epoch_id", "projection", "session_root", "end"}
    C.need(type(record) is dict and set(record) in (keys, keys | {"comparison_scope"})
           and record["epoch_id"] == packet.epoch_id, "Exact visual target record")
    C.need(record.get("comparison_scope", DECLARED_SCOPE) == scope, "Immutable visual record comparison scope")
    projection = C.read_projection(record["projection"])
    C.need(projection.metadata() == packet.metadata() and projection.signals_npy == packet.signals_npy,
           "Exact original target available to visual and programme arms")
    C.need(C.ordinary_path(record["end"]["path"]) == C.ordinary_path(record["session_root"]) / "END.json",
           "Visual terminal evidence belongs to this private session")
    P.descriptor(record["end"], 65536)
    return V.audit_session(record["session_root"], packet, runtime, knowledge)


def _new_collection(condition, knowledge_descriptor, source, rows, answers, root, comparison_scope=None):
    C.need(condition in (C.VISUAL_CONDITION, C.PROGRAMME_CONDITION), "New epoch condition only")
    C.checked_complete_rows(rows)
    complete = answers.complete()
    root = C.ordinary_path(root)
    root.mkdir(mode=0o700)
    submission = C.write_new(root / "predictions.npz", C.submission_bytes(complete))
    return C.write_new(root / "COLLECTION.json", C.encode({
        "schema": "sleep007_epoch_arm_collection_v1", "condition": condition,
        "knowledge": knowledge_descriptor, "source": source, "rows": rows, "submission": submission,
        "comparison_scope": dict(DECLARED_SCOPE) if comparison_scope is None else comparison_scope}))


def collect_visual(records, knowledge_descriptor, source, runtime, output_root, *,
                   claim_matched_information=False, matched_access_audit=None):
    """All5450 terminal sessions, one immutable first answer per target; no raw truth."""
    selection = {"claim_matched_information": claim_matched_information, "matched_access_audit": matched_access_audit}
    scope = P.M.comparison_scope(selection)
    if claim_matched_information:
        audit = P.M.selected(selection)
        C.need(audit["knowledge"] == P.plain(knowledge_descriptor) and audit["source"] == P.plain(source),
               "Visual collection shares the selected source and declared knowledge review")
    P.source_freeze(source)
    knowledge = C.checked_knowledge(C.decode(P.descriptor(knowledge_descriptor, 8192)))
    C.checked_complete_rows(records)
    C.need(all(set(row) == {"epoch_id", "record"} for row in records), "Complete pinned visual record roster")
    answers, sessions, response_ids = C.FirstAnswers(), set(), set()
    for row in records:
        raw = P.descriptor(row["record"], 2**20)
        record = C.decode(raw)
        packet = C.read_projection(record["projection"])
        C.need(packet.epoch_id == row["epoch_id"], "Exact target row")
        result = _visual_record(record, packet, runtime, knowledge, scope)
        C.need(result["session_id"] not in sessions, "Fresh independent context for every target")
        sessions.add(result["session_id"])
        C.need(not response_ids.intersection(result["response_ids"]), "No provider response reused across targets")
        response_ids.update(result["response_ids"])
        answers.accept(row["epoch_id"], result["probabilities"], C.pin(raw))
    return _new_collection(C.VISUAL_CONDITION, knowledge_descriptor, source, records, answers, output_root, scope)


def collect_programme(records, knowledge_descriptor, source, runtime, output_root):
    """All5450 closed independent producers; never accepts a partial or revised panel."""
    P.M.selected(runtime)
    P.source_freeze(source)
    knowledge = C.checked_knowledge(C.decode(P.descriptor(knowledge_descriptor, 8192)))
    C.checked_complete_rows(records)
    C.need(all(set(row) == {"epoch_id", "record"} for row in records), "Complete pinned programme record roster")
    answers, resources, definition = C.FirstAnswers(), set(), None
    for row in records:
        raw = P.descriptor(row["record"], 2**20)
        record = C.decode(raw)
        packet = C.read_projection(record["projection"])
        C.need(packet.epoch_id == row["epoch_id"], "Exact target row")
        result = P.admit_phase(runtime, record, packet, knowledge)
        owned = {(item["kind"], item["name"]) for item in result["resources"]}
        C.need(not resources.intersection(owned), "No container/volume reused across targets")
        resources.update(owned)
        if definition is None: definition = result["definition"]
        C.need(result["definition"] == definition, "One pre-input programme and declared prior across all targets")
        answers.accept(row["epoch_id"], result["probabilities"], C.pin(raw))
    return _new_collection(C.PROGRAMME_CONDITION, knowledge_descriptor, source, records, answers, output_root, P.M.comparison_scope(runtime))


def execute_programme_collection(runtime, prepared, projections, exposures, provider_config, resources,
                                 root, *, origin, deadline, provider_read_limit, provider_write_limit,
                                 journal_bytes_limit, journal_records_limit):
    """Finite all-target operator loop; external native admission is required before calling."""
    value, source, definition, knowledge = P.checked_prepared(prepared, runtime=runtime)
    targets = C.required_targets()
    C.need(type(projections) is dict and set(projections) == set(targets)
           and type(exposures) is dict and set(exposures) == set(targets), "No subset execution contract")
    phase_seconds = sum(resources[key] for key in ("setup_seconds", "producer_seconds", "capture_seconds", "cleanup_seconds"))
    C.need(all(type(v) in (int, float) and math.isfinite(v) for v in (origin, deadline))
           and 0 <= origin <= time.monotonic() < deadline and deadline >= origin + len(targets) * phase_seconds,
           "Complete finite all-target phase allocation declared before execution")
    C.need(type(journal_bytes_limit) is int and journal_bytes_limit > 0
           and type(journal_records_limit) is int and journal_records_limit > 0, "Explicit complete journal limits")
    root = C.ordinary_path(root)
    root.mkdir(mode=0o700)
    for name in ("control", "quarantine", "journal", "records"):
        (root / name).mkdir(mode=0o700)
    provider = P.open_provider(runtime, root / "control", root / "quarantine", provider_config, exposures,
                               provider_read_limit, provider_write_limit)
    used, count = 0, 0
    def journal(event, value):
        nonlocal used, count
        raw = C.encode({"event": event, "value": value})
        C.need(count < journal_records_limit and used + len(raw) <= journal_bytes_limit,
               "Original finite journal allocation")
        C.write_new(root / "journal" / (str(count).zfill(8) + ".json"), raw)
        used += len(raw)
        count += 1
    rows, seen_resources = [], set()
    for ordinal, epoch_id in enumerate(targets):
        approval = exposures[epoch_id]
        record = P.execute_phase(runtime, provider, prepared, projections[epoch_id], approval["exposure"],
                                 resources, origin, origin + (ordinal + 1) * phase_seconds, deadline, journal,
                                 boundary_audit=approval["boundary_audit"])
        packet = C.read_projection(projections[epoch_id])
        C.need(packet.epoch_id == epoch_id, "Projection cannot substitute another target")
        result = P.admit_phase(runtime, record, packet, knowledge)
        owned = {(item["kind"], item["name"]) for item in result["resources"]}
        C.need(not seen_resources.intersection(owned), "Fresh owned native resources per target")
        seen_resources.update(owned)
        record_descriptor = C.write_new(root / "records" / (str(ordinal).zfill(5) + ".json"), C.encode(record))
        rows.append({"epoch_id": epoch_id, "record": record_descriptor})
    # Re-admission before commitment also ensures the same pre-input source remains frozen.
    return collect_programme(rows, value["knowledge"], value["source"], runtime, root / "complete")


@dataclass(frozen=True)
class AdmittedPair:
    specification: object
    viewer: object
    programme: object
    references: object
    adapter: object
    assets: object
    helper: object
    knowledge: object
    evidence: object


def admit_pair(viewer_collection, programme_collection, packet_roots, references, runtime, visual_runtime):
    """Both complete source/byte/first-answer chains pass before any private target operand is read."""
    matched_access = P.M.selected(runtime)
    visual, visual_knowledge = _collection(viewer_collection, C.VISUAL_CONDITION)
    programme, programme_knowledge = _collection(programme_collection, C.PROGRAMME_CONDITION)
    scope = P.M.comparison_scope(runtime)
    C.need(visual["comparison_scope"] == programme["comparison_scope"] == scope,
           "Both immutable arm scopes must match the selected comparison claim")
    C.need(visual_knowledge == programme_knowledge
           and P.plain(visual["knowledge"]) == P.plain(programme["knowledge"]), "Identical immutable shared prior declaration")
    C.need(P.plain(visual["source"]) == P.plain(programme["source"]), "Same frozen condition implementation")
    C.need(type(packet_roots) is dict and set(packet_roots) == {case for case, _ in C.CASES},
           "Both original person packet operands")
    adapter, helper, assets, _ = runtime["common"].load_sources()
    specification = adapter.checked_specification(adapter.Specification(
        tuple(adapter.Case(case, count) for case, count in C.CASES), ("YASA", "RF")))
    # All full predictions and reference pins are validated before original waveform replay or private truth.
    view = adapter.validate_submission(visual["submission"]["path"], P.plain(visual["submission"]), specification)
    prog = adapter.validate_submission(programme["submission"]["path"], P.plain(programme["submission"]), specification)
    C.need(type(references) is dict and set(references) == {"YASA", "RF"}, "Original richer-information references kept explicit")
    refs = {}
    for name, item in references.items():
        C.need(P.plain(item) == P.plain(assets["comparators"][name]), "Original saved reference identity")
        refs[name] = adapter.validate_submission(item["path"], P.plain(item), specification)
    sessions, response_ids, resources = set(), set(), set()
    programme_definition, ordinal = None, 0
    for case, count in C.CASES:
        original = runtime["viewer"].Packet(packet_roots[case], case)
        try:
            for index in range(count):
                packet = C.project_epoch(original, index)
                visual_row, programme_row = visual["rows"][ordinal], programme["rows"][ordinal]
                C.need(visual_row["epoch_id"] == programme_row["epoch_id"] == packet.epoch_id, "Matched exact target order")
                vr = C.decode(P.descriptor(visual_row["record"], 2**20))
                pr = C.decode(P.descriptor(programme_row["record"], 2**20))
                v = _visual_record(vr, packet, visual_runtime, visual_knowledge, scope)
                p = P.admit_phase(runtime, pr, packet, programme_knowledge)
                expected_knowledge = P.plain(visual["knowledge"])
                C.need(v["knowledge"] == p["knowledge"] == expected_knowledge, "Same declared agent/prior provenance binding")
                C.need(v["session_id"] not in sessions, "No reused visual context")
                sessions.add(v["session_id"])
                C.need(not response_ids.intersection(v["response_ids"]), "No cross-target provider response")
                response_ids.update(v["response_ids"])
                owned = {(item["kind"], item["name"]) for item in p["resources"]}
                C.need(not resources.intersection(owned), "No persistent native process or volume across targets")
                resources.update(owned)
                if programme_definition is None: programme_definition = p["definition"]
                C.need(p["definition"] == programme_definition, "Frozen programme/knowledge across both people")
                for validated, answer in ((view, v), (prog, p)):
                    actual = validated["people"][case]["probabilities"][index]
                    C.need(adapter.np.array_equal(actual, adapter.np.asarray(answer["probabilities"], dtype=adapter.np.float64)),
                           "Every collected row equals the irreversible first accepted answer")
                ordinal += 1
        finally:
            original.close()
    C.need(ordinal == C.TOTAL and len(sessions) == C.TOTAL, "All5450 targets; two exposed people")
    return AdmittedPair(specification, view, prog, refs, adapter, assets, helper, visual_knowledge,
                        {"viewer": viewer_collection, "programme": programme_collection,
                         "knowledge": P.plain(visual["knowledge"]), "source": P.plain(visual["source"]),
                          "comparison_scope": scope,
                          "matched_access_audit": scope["matched_access_audit"],
                          "programme_generation_origin": matched_access["generation_origin"] if matched_access is not None else None})


def score_admitted(admitted, target_loader):
    """Original numerical endpoint and masks, called only after complete paired admission."""
    C.need(type(admitted) is AdmittedPair and callable(target_loader), "Admitted pair and trusted target loader")
    adapter, spec = admitted.adapter, admitted.specification
    C.need(tuple((case.case_id, case.epochs) for case in spec.cases) == C.CASES,
           "Original complete panel and biological units")
    targets = adapter._checked_targets(target_loader(), spec)
    arms = {"viewer": adapter._score(admitted.viewer, targets, spec),
            "programme": adapter._score(admitted.programme, targets, spec)}
    refs = {name: adapter._score(value, targets, spec) for name, value in admitted.references.items()}
    differences = {"programme_minus_viewer": adapter._difference(arms["programme"], arms["viewer"])}
    for arm, score in arms.items():
        for name, reference in refs.items():
            differences[arm + "_minus_" + name] = adapter._difference(score, reference)
    return {"schema": "sleep007_epoch_paired_grade_v1", "status": "valid_descriptive_paired_result",
            "pair_condition": C.PAIR_CONDITION,
            "arm_conditions": {"viewer": C.VISUAL_CONDITION, "programme": C.PROGRAMME_CONDITION},
            "n_people": 2, "full_epochs": 5450, "epochs_nested_within_people": True,
            "class_order": list(adapter.CLASS_ORDER), "row_sum_atol": adapter.ROW_SUM_ATOL,
            "argmax_tie_rule": "first_class_index", "normalization_or_clipping": False,
            "arms": arms, "references": refs, "signed_differences": differences,
            "reference_access": "Original richer-information YASA/RF references; not matched same-epoch conditions.",
            "temporal_context_removed": True, "whole_history_pooling_allowed": False,
            "contrast": "same_epoch_signal_access_pairing_under_declared_shared_prior_policy",
             "comparison_scope": admitted.evidence["comparison_scope"],
            "rendered_and_numerical_information_equivalence_proven": False,
            "hidden_pretraining_verified": False, "matched_agent_provenance_qualified": False,
            "population_inference": False, "confidence_interval": None, "p_value": None,
            "scientific_qualification": False, "sota_claim": False,
            "private_loader_calls": 1, "all_public_bundles_validated_before_private_loader": True,
            "evidence": admitted.evidence,
            "scope": "Two already exposed development people; 5450 nested epochs, not5450 independent people."}


def _checked_config(value):
    required = {"schema", "source", "viewer_collection", "programme_collection", "packet_roots", "references",
                "private_locations", "implementations_root", "finite_bindings_root", "visual_runtime"}
    C.need(type(value) is dict and required <= set(value)
           and set(value) <= required | {"matched_access_audit", "claim_matched_information"}
           and value["schema"] == "sleep007_epoch_pair_request_v1", "Exact separately selected epoch pair request")
    value = dict(value)
    value.setdefault("matched_access_audit", None)
    value.setdefault("claim_matched_information", False)
    P.M.claim(value)
    P.source_freeze(value["source"])
    C.need(type(value["visual_runtime"]) is dict and set(value["visual_runtime"]) == {
        "root", "whole_history_integration_root", "whole_history_admission_root"}, "Exact trusted visual source roots")
    return value


def _public(value):
    import epoch_visual as V
    value = _checked_config(value)
    if value["claim_matched_information"]:
        C.need(value["matched_access_audit"] is not None, "Externally selected matched-access audit required")
    runtime = P.load_runtime(value["implementations_root"], value["finite_bindings_root"],
                             matched_access_audit=value["matched_access_audit"],
                             claim_matched_information=value["claim_matched_information"])
    P.M.selected(runtime)
    visual_runtime = V.load_runtime(**value["visual_runtime"])
    admitted = admit_pair(value["viewer_collection"], value["programme_collection"], value["packet_roots"],
                          value["references"], runtime, visual_runtime)
    return admitted, runtime


def coordinate_compare(config, output_root, *, grader_wall_seconds):
    """Coordinator admission, followed by independent fresh-process admission before truth."""
    _public(config)  # No private-location descriptor contents are opened here.
    C.need(type(grader_wall_seconds) is int and 0 < grader_wall_seconds <= 86400, "Explicit separately admitted grader wall bound")
    root = C.ordinary_path(output_root)
    root.mkdir(mode=0o700)
    request = C.write_new(root / "GRADE_REQUEST.json", C.encode(config))
    stdout, stderr = root / "grade.stdout.json", root / "grade.stderr"
    process = None
    def limits():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (200000, 200000))
        resource.setrlimit(resource.RLIMIT_CPU, (grader_wall_seconds, grader_wall_seconds))
    try:
        with stdout.open("xb") as out, stderr.open("xb") as err:
            env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(root), "TMPDIR": str(root),
                   "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
                   "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"}
            process = subprocess.Popen([sys.executable, "-I", "-B", str(HERE / "epoch_admission.py"),
                         "--request", request["path"], "--bytes", str(request["bytes"]), "--sha256", request["sha256"]],
                         stdin=subprocess.DEVNULL, stdout=out, stderr=err, cwd=root, env=env,
                         start_new_session=True, preexec_fn=limits)
            process.wait(timeout=grader_wall_seconds)
    finally:
        if process is not None:
            if process.returncode is None:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            process.wait(timeout=2)
    C.need(process is not None and process.returncode == 0, "Independent protected grader succeeded")
    try: os.killpg(process.pid, 0)
    except ProcessLookupError: pass
    else: raise ValueError("Trusted grader process group remains")
    report_raw = P.snapshot(stdout, 200000)
    report = C.decode(report_raw)
    C.need(report["schema"] == "sleep007_epoch_paired_grade_v1" and report["private_loader_calls"] == 1
           and report["pair_condition"] == C.PAIR_CONDITION and report["whole_history_pooling_allowed"] is False,
           "Explicit new-condition protected report")
    return {"report": {"path": str(stdout), **C.pin(report_raw)}, "process_group_closed": True,
            "provider_qualification": False, "scientific_qualification": False}


def main(argv=None):
    calls, stage = 0, "request"
    try:
        argv = sys.argv[1:] if argv is None else argv
        C.need(len(argv) == 6 and set(argv[::2]) == {"--request", "--bytes", "--sha256"}, "Exact worker arguments")
        flags = dict(zip(argv[::2], argv[1::2]))
        config = C.decode(P.descriptor({"path": flags["--request"], "bytes": int(flags["--bytes"]),
                                       "sha256": flags["--sha256"]}, 32768))
        stage = "public_admission"
        admitted, runtime = _public(config)  # Independent complete re-admission.
        def load_once():
            nonlocal calls, stage
            stage = "private_targets"
            calls += 1
            C.need(calls == 1, "Exactly one protected target load")
            return runtime["grading"].private_targets(config["private_locations"], admitted.assets,
                                                       admitted.adapter, admitted.helper)
        report = score_admitted(admitted, load_once)
        raw = C.encode(report)
        C.need(len(raw) <= 200000, "Bounded protected report")
        sys.stdout.write(raw.decode())
        return 0
    except Exception:
        sys.stdout.write(C.encode({"status": "failed", "failure_stage": stage, "private_loader_calls": calls}).decode())
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
