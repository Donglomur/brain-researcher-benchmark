"""Exact phase invocation, actual source and upstream-output custody.

Only canonical JSON pins enter the production dispatcher. Numerical leaves are
opened by their phase-specific loaders, never by this metadata gate. In
particular this gate cannot open query arrays or targets early. An independently
approved invocation binds every path and declared pin; actual loaders verify
those same bodies immediately before use in a qualified immutable namespace.
"""
from pathlib import Path
from cohort import require
from io_support import admit_full_run, object_digest, authenticate_file, safe_relative
from storage import read_json_exact

PHASES = ("prepare_original", "prepare_views", "train_references", "author_candidates", "predict_all", "grade_all")
ROLES = {
 "prepare_original": {"source_spec", "metadata_manifest", "sensors"},
 "prepare_views": {"prepared"},
 "train_references": {"case_store"},
 "author_candidates": {"case_store", "static_task_spec", "adapter_config"},
 "predict_all": {"case_store", "reference_program", "reference_selection", "candidate_program", "prediction_cases", "method_registry", "adapter_config"},
 "grade_all": {"case_store", "reference_program", "reference_selection", "completed_predictions", "method_registry", "execution_registry"}}
ORIGINS = {
 "prepare_original": {}, "prepare_views": {"prepared": ("prepare_original", "prepared")},
 "train_references": {"case_store": ("prepare_views", "case_store")},
 "author_candidates": {"case_store": ("prepare_views", "case_store")},
 "predict_all": {"case_store": ("prepare_views", "case_store"), "reference_program": ("train_references", "reference_program"),
                 "reference_selection": ("train_references", "reference_selection"), "candidate_program": ("author_candidates", "candidate_program")},
 "grade_all": {"case_store": ("prepare_views", "case_store"), "reference_program": ("train_references", "reference_program"),
               "reference_selection": ("train_references", "reference_selection"), "completed_predictions": ("predict_all", "completed_predictions")}}
SOURCE_FILES = frozenset({"cohort.py", "io_support.py", "preparation.py", "packets.py", "grading.py", "study.py", "storage.py", "outputs.py", "prediction_worker.py", "selection.py", "frontdoor.py", "phase_manifest.py", "phase_worker.py", "phase_launcher.py", "reference/__init__.py", "reference/models.py", "method/__init__.py", "method/plan.py", "method/admission.py", "adapters/__init__.py", "adapters/common.py", "adapters/process.py", "adapters/provider.py", "adapters/contexts.py", "adapters/worker.py"})


def budget_snapshot(budget):
    return {"origin_monotonic": budget.origin_monotonic, "deadline_monotonic": budget.deadline_monotonic,
            "limits": dict(budget.limits), "used": dict(budget.used)}


def pin_shape(pin):
    require(type(pin) is dict and {"path", "bytes", "sha256"} <= set(pin) and
            type(pin["path"]) is str and Path(pin["path"]).is_absolute() and
            type(pin["bytes"]) is int and pin["bytes"] >= 0 and
            type(pin["sha256"]) is str and len(pin["sha256"]) == 64 and
            all(c in "0123456789abcdef" for c in pin["sha256"]), "Exact absolute ordinary artifact pin")
    return pin


def metadata(pin, budget, cap=16 * 1024 * 1024):
    pin_shape(pin)
    require(pin["bytes"] <= cap, "Predeclared metadata extent cap")
    return read_json_exact(pin["path"], pin, budget)


def source_closure(root, manifest, budget):
    root = Path(root)
    require(root.resolve() == Path(__file__).resolve().parent and not root.is_symlink(), "Running production source root")
    require(type(manifest) is list and len(manifest) == len(SOURCE_FILES) and
            {p.get("path") for p in manifest} == SOURCE_FILES, "Exact complete production source path set")
    for pin in manifest:
        require(set(pin) == {"path", "bytes", "sha256"}, "Only reviewed relative source descriptors")
        authenticate_file(safe_relative(root, pin["path"]), pin, budget)
    return object_digest(manifest)


def completion(pin, phase, approved, budget):
    record = metadata(pin, budget)
    require(object_digest(record) in approved and record.get("schema") == "neural053_phase_observed_completion_v2" and
            record.get("phase") == phase and type(record.get("natural_exit_code")) is int and
            record["natural_exit_code"] == 0 and record.get("source_state_unchanged") is True and
            record.get("process_group_absent") is True and record.get("streams_closed") is True,
            "Exact independently approved natural phase completion, not a worker assertion")
    output = metadata(record["output_manifest"], budget)
    require(output.get("schema") == "neural053_phase_outputs_v2" and output.get("phase") == phase and
            output.get("invocation_sha256") == record.get("invocation_sha256") and
            output.get("runtime_source_sha256") == record.get("runtime_source_sha256"), "Observed actual phase output joins source and operands")
    require(type(output.get("artifacts")) is dict, "Actual persisted phase output inventory")
    for value in output["artifacts"].values(): pin_shape(value)
    return record, output


def admit_invocation(phase, invocation_pin, permit, bindings, approved, budget):
    """Refuse absent/stale/unjoined operands before opening any operand body."""
    require(phase in PHASES, "Canonical phase")
    admit_full_run(permit, bindings, approved, phase)
    before = budget_snapshot(budget)
    require(bindings.get("budget_before_sha256") == object_digest(before), "Inherited full clock/cumulative ledger")
    bootstrap = getattr(budget, "bootstrap_read_bytes", 0)
    if bootstrap:
        budget.charge("source_read", bootstrap)
        budget.bootstrap_read_bytes = 0
    pin_shape(invocation_pin)
    require(bindings.get("invocation") == invocation_pin, "Actual invocation pin equals independently approved phase operand")
    invocation = metadata(invocation_pin, budget)
    require(set(invocation) == {"schema", "phase", "source_root", "runtime_sources", "artifacts", "parameters", "upstream", "ledger_parent"} and
            invocation["schema"] == "neural053_phase_invocation_v2" and invocation["phase"] == phase,
            "Closed phase invocation vocabulary; no callable/live operands")
    require(bindings.get("runtime_source_manifest_sha256") == object_digest(invocation["runtime_sources"]),
            "Source list independently bound, not caller-generated authority")
    source_closure(invocation["source_root"], invocation["runtime_sources"], budget)
    artifacts = invocation["artifacts"]
    require(type(artifacts) is dict and set(artifacts) == ROLES[phase], "Exact phase-specific operand roles")
    for pin in artifacts.values(): pin_shape(pin)
    require(type(invocation["parameters"]) is dict, "JSON-only phase parameters")
    expected_upstream = {v[0] for v in ORIGINS[phase].values()}
    require(type(invocation["upstream"]) is dict and set(invocation["upstream"]) == expected_upstream,
            "Complete exact upstream phase graph")
    upstream = {}
    for name, pin in invocation["upstream"].items():
        record, output = completion(pin, name, approved, budget)
        require(record["runtime_source_sha256"] == bindings["runtime_source_manifest_sha256"], "Same reviewed programme source across phases")
        old = record["budget_after"]
        require(all(old[k] == before[k] for k in ("origin_monotonic", "deadline_monotonic", "limits")) and
                set(old["used"]) == set(before["used"]) and
                all(type(v) is int and 0 <= v <= before["used"][k] for k, v in old["used"].items()),
                "Upstream clock/counters cannot be reset or omitted")
        upstream[name] = output["artifacts"]
    for role, (name, upstream_role) in ORIGINS[phase].items():
        require(artifacts[role] == upstream[name].get(upstream_role), "Actual operand joins independently accepted upstream output: " + role)
    if phase == "prepare_original":
        require(invocation["ledger_parent"] is None and all(v == 0 for v in before["used"].values()), "New ledger only at first phase")
    else:
        parent_pin = invocation["ledger_parent"]
        parent = metadata(parent_pin, budget)
        require(object_digest(parent) in approved and parent.get("schema") == "neural053_phase_observed_completion_v2" and
                type(parent.get("natural_exit_code")) is int and parent["natural_exit_code"] == 0 and
                parent.get("source_state_unchanged") is True and parent.get("budget_after") == before,
                "Exact most recent observed cumulative ledger, no branch/reset")
    return invocation
