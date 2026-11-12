"""Authenticated source composition and externally supervised trusted callables.

This module is an externally selected trust anchor, not a candidate entry point.
It provides no observer, API authority, native qualification, or TokenAdmission
implementation. A separately admitted deployment supplies those capabilities.
No candidate numerical program, reference fit, model or target loader runs when
source is captured or definitions are built. Local modules never use sys.path
discovery; temporary import bindings are restored even on compilation failure.
"""

import copy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import time
import types
from types import MappingProxyType

INCUMBENT_PIN = {"bytes": 2466, "sha256": "474baf4949c318b8a6213ccbb9562a71d1e13e3a3fa282a527cf0277fc892771"}
NEW_NAMES = (
    "trusted_entry.py", "paired_policy.py", "paired_report.py", "controller_successor.py",
    "admission_successor.py", "pairing_api.py", "broker_factory.py", "adaptive_native.py",
    "adaptive_entry.py", "openbmi_agent_tools.py", "agent_driver.py",
)
BROKER_NAMES = ("morse_protocol.py", "morse_broker.py", "morse_docker.py", "morse_bootstrap.py")
PANELS = ("frozen_program", "case_adaptive", "reference")
_CAPTURED = object()
_BUILT = object()


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _exact(value, fields, message):
    _need(type(value) is dict and set(value) == set(fields), message)


def _pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _valid_pin(pin):
    _exact(pin, ("bytes", "sha256"), "Exact content pin")
    _need(type(pin["bytes"]) is int and 0 < pin["bytes"] <= 1048576 and
          type(pin["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]), "Bounded source pin")
    return pin


def _parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            _need(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def _path(path):
    path = Path(path).absolute()
    _need(".." not in path.parts and not any(c in str(path) for c in "\0\n\r") and
          not any(p.is_symlink() for p in (path, *path.parents)), "Ordinary source path")
    return path


def _relative(repository, row):
    _exact(row, ("path", "bytes", "sha256"), "Exact source descriptor")
    name = row["path"]
    _need(type(name) is str and bool(name) and "\\" not in name and
          PurePosixPath(name).as_posix() == name and not PurePosixPath(name).is_absolute() and
          not any(p in ("", ".", "..") for p in name.split("/")), "Repository-relative source descriptor")
    return _path(repository / name), _valid_pin({k: row[k] for k in ("bytes", "sha256")})


def _stamp(info):
    return tuple(getattr(info, k) for k in ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size",
                                           "st_uid", "st_gid", "st_mtime_ns", "st_ctime_ns"))


class _Meter:
    def __init__(self, deadline, limit):
        _need(type(deadline) in (int, float) and math.isfinite(deadline), "Finite deadline")
        _need(type(limit) is int and limit > 0, "Positive bounded read allowance")
        self.deadline, self.limit, self.spent = deadline, limit, 0
        self.tick()

    def tick(self):
        _need(time.monotonic() < self.deadline, "Original selected read deadline")

    def read(self, amount):
        _need(type(amount) is int and amount >= 0 and self.spent + amount <= self.limit,
              "Managed read allowance")
        self.spent += amount
        self.tick()


def _capture(path, expected, meter):
    expected = _valid_pin(expected)
    meter.tick()
    path = _path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        initial = os.fstat(fd)
        _need(stat.S_ISREG(initial.st_mode) and initial.st_nlink == 1 and
              initial.st_size == expected["bytes"], "Exact ordinary selected source extent")
        meter.read(initial.st_size + 1)
        pieces, remaining = [], initial.st_size + 1
        while remaining:
            meter.tick()
            part = os.read(fd, min(65536, remaining))
            if not part:
                break
            pieces.append(part)
            remaining -= len(part)
        raw = b"".join(pieces)
        _need(_stamp(initial) == _stamp(os.fstat(fd)) == _stamp(path.lstat()), "Source changed during capture")
    finally:
        os.close(fd)
    _need(_pin(raw) == expected, "Selected source digest")
    meter.tick()
    return raw


class CapturedSource:
    """Immutable byte maps; construction is reserved to authenticated capture."""
    __slots__ = ("_tag", "repository", "manifest_path", "source_pin", "incumbent_pin",
                 "old", "new", "dependencies", "external", "paths", "read_reservations")

    def __init__(self, tag, **values):
        _need(tag is _CAPTURED, "Use authenticated capture")
        object.__setattr__(self, "_tag", tag)
        for key, value in values.items():
            object.__setattr__(self, key, MappingProxyType(value) if type(value) is dict else value)

    def __setattr__(self, name, value):
        raise AttributeError("Captured source is immutable")


def capture(repository, manifest_path, manifest_pin, *, deadline, read_limit):
    """Capture every selected body, including original bindings, before compile.

    Manifest shape: schema=neural083_paired_source_v1, incumbent repository-
    relative manifest descriptor, files exact NEW_NAMES descriptors, and
    broker_dependencies exact BROKER_NAMES descriptors. The trust-anchor source
    itself is selected as trusted_entry.py. Original scientific/reference
    binding bodies are authenticated but never executed by this loader.
    """
    root, manifest_path = _path(repository), _path(manifest_path)
    _need(root.is_dir() and manifest_path.is_relative_to(root), "Manifest inside selected repository")
    meter = _Meter(deadline, read_limit)
    raw = _capture(manifest_path, manifest_pin, meter)
    manifest = _parse(raw)
    _exact(manifest, ("schema", "incumbent", "files", "broker_dependencies"), "Closed paired source manifest")
    _need(manifest["schema"] == "neural083_paired_source_v1", "Paired source schema")
    old_path, old_pin = _relative(root, manifest["incumbent"])
    _need(old_pin == INCUMBENT_PIN, "Exact accepted predecessor source")
    old_manifest = _parse(_capture(old_path, old_pin, meter))
    _exact(old_manifest, ("schema", "files"), "Closed predecessor manifest")
    _need(old_manifest["schema"] == "neural083_full_program_source_v1" and
          type(old_manifest["files"]) is dict and len(old_manifest["files"]) == 18, "All 18 predecessor members")
    old, new, dependencies, external, paths = {}, {}, {}, {}, {}
    for name, pin in old_manifest["files"].items():
        _need(type(name) is str and Path(name).name == name, "Flat predecessor member")
        path = old_path.parent / name
        old[name] = _capture(path, pin, meter)
        paths["old/" + name] = str(path)
    _exact(manifest["files"], NEW_NAMES, "Exact new source closure")
    _exact(manifest["broker_dependencies"], BROKER_NAMES, "Exact four broker dependencies")
    used = set()
    for field, destination in (("files", new), ("broker_dependencies", dependencies)):
        for name, descriptor in manifest[field].items():
            path, pin = _relative(root, descriptor)
            _need(path not in used, "Distinct selected new source paths")
            used.add(path)
            destination[name] = _capture(path, pin, meter)
            paths[("new/" if field == "files" else "dependencies/") + name] = str(path)
    binding = _parse(old["BINDING.json"])
    _need(binding.get("schema") == "neural083_original_scientific_binding_v1", "Original scientific binding")
    descriptors = {"reference_core.py": binding["reference_core"]}
    for section in ("scoring_sources", "scientific_sources"):
        for name, descriptor in binding[section].items():
            descriptors[section + "/" + name] = descriptor
    for name, descriptor in descriptors.items():
        path, pin = _relative(root, descriptor)
        external[name] = _capture(path, pin, meter)
        paths["external/" + name] = str(path)
    _need(_pin(old["reference_program.py"]) == binding["reference"], "Original independent reference source")
    meter.tick()
    return CapturedSource(_CAPTURED, repository=root, manifest_path=manifest_path,
                          source_pin=dict(manifest_pin), incumbent_pin=old_pin,
                          old=old, new=new, dependencies=dependencies, external=external,
                          paths=paths, read_reservations=meter.spent)


def _module(body, name, path, **bindings):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__dict__.update(bindings)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def _fresh_dependencies(source):
    absent, previous, modules = object(), {}, {}
    names = ("morse_protocol", "morse_broker", "morse_docker")
    saved_path = sys.path[:]
    for name in names:
        previous[name] = sys.modules.get(name, absent)
    try:
        # All selected dependency bodies were captured before any local compile.
        for name in names:
            module = types.ModuleType(name)
            module.__file__ = source.paths["dependencies/" + name + ".py"]
            sys.modules[name] = module
            exec(compile(source.dependencies[name + ".py"], module.__file__, "exec"), module.__dict__)
            modules[name] = module
    finally:
        sys.path[:] = saved_path
        for name, value in previous.items():
            if value is absent:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return modules


class Runtime:
    __slots__ = ("_tag", "source", "modules", "token_admission")
    def __init__(self, tag, source, modules, token_admission):
        _need(tag is _BUILT, "Use captured build")
        self._tag, self.source, self.modules, self.token_admission = tag, source, modules, token_admission


def build(source, *, token_admission):
    """Build trusted definitions only; never fit, infer, call a model or grade.

    The supplied token policy is an external trusted deployment capability, not
    reconstructed from JSON or a review flag. Fresh broker dependency modules
    are compiled from immutable captured bytes, preserving per-context reset.
    The incumbent conservative reread reservations remain charged even though
    this composition obtains dependency bytes from the authenticated capsule.
    """
    _need(type(source) is CapturedSource and source._tag is _CAPTURED, "Authenticated source capsule")
    _need(token_admission is not None and type(token_admission) not in (bool, dict) and
          callable(getattr(token_admission, "require_model_bound", None)), "External TokenAdmission capability required")
    # Syntax-check every Python source before executing any local definition.
    for group, bodies in (("old", source.old), ("new", source.new),
                          ("dependencies", source.dependencies), ("external", source.external)):
        for name, body in bodies.items():
            if name.endswith(".py"):
                compile(body, source.paths[group + "/" + name], "exec")
    modules = {}
    def old(name, **bindings):
        module = _module(source.old[name], "captured_openbmi_" + name[:-3], source.paths["old/" + name], **bindings)
        modules[name] = module
        return module
    def new(name, **bindings):
        module = _module(source.new[name], "captured_paired_" + name[:-3], source.paths["new/" + name], **bindings)
        modules[name] = module
        return module
    c = old("common.py")
    contracts = old("contracts.py", c=c)
    scientific = old("scientific_protocol.py")
    store = old("store.py", c=c, contracts=contracts, scientific=scientific)
    policy = old("policy.py", c=c, contracts=contracts)
    native = old("native.py", c=c)
    paired_policy = new("paired_policy.py")
    new("paired_report.py")
    broker = new("broker_factory.py")
    _need(set(broker.PINS) == set(BROKER_NAMES) and all(
        _pin(source.dependencies[name]) == {"bytes": extent, "sha256": digest}
        for name, (extent, digest) in broker.PINS.items()), "Broker constants match all captured dependencies")
    broker.load_dependencies = lambda: _fresh_dependencies(source)
    absent, previous = object(), sys.modules.get("broker_factory")
    existed = "broker_factory" in sys.modules
    saved_path = sys.path[:]
    try:
        sys.modules["broker_factory"] = broker
        adaptive = new("adaptive_native.py", c=c)
        _need(adaptive.ContextBroker is broker.ContextBroker, "Adaptive native binds exact captured broker class")
    finally:
        sys.path[:] = saved_path
        if existed:
            sys.modules["broker_factory"] = previous
        else:
            sys.modules.pop("broker_factory", None)
    agent = new("agent_driver.py")
    bodies = {**source.old, **source.new, **source.dependencies}
    pairing_api = new("pairing_api.py", c=c, contracts=contracts, paired_policy=paired_policy,
                      agent_driver=agent, broker_factory=broker, adaptive_native=adaptive,
                      source_bodies=MappingProxyType(bodies), incumbent_source=dict(source.incumbent_pin),
                      token_admission=token_admission)
    new("controller_successor.py", c=c, policy=policy, contracts=contracts, store=store,
        native=native, pairing_api=pairing_api)
    new("admission_successor.py")
    # The original scorer's historical path mutation and import are contained.
    previous = sys.modules.get("protocol", absent)
    saved_path = sys.path[:]
    try:
        protocol = _module(source.external["scoring_sources/protocol.py"], "protocol",
                           source.paths["external/scoring_sources/protocol.py"])
        sys.modules["protocol"] = protocol
        scorer = _module(source.external["scoring_sources/scorer_core.py"], "captured_openbmi_original_scorer",
                         source.paths["external/scoring_sources/scorer_core.py"])
        _need(scorer.p is protocol, "Original scorer binds captured protocol")
    finally:
        sys.path[:] = saved_path
        if previous is absent:
            sys.modules.pop("protocol", None)
        else:
            sys.modules["protocol"] = previous
    modules["original_scorer"] = scorer
    return Runtime(_BUILT, source, modules, token_admission)


def _runtime(runtime):
    _need(type(runtime) is Runtime and runtime._tag is _BUILT, "Captured trusted runtime")
    return runtime.modules["common.py"]


def _operand(c, operand, cap, meter):
    _exact(operand, ("path", "bytes", "sha256"), "Exact selected operand")
    return c.capture(operand["path"], cap, c.only_pin(operand), meter.tick, meter.read)


def _supervise(supervisor, action, context):
    _need(supervisor is not None and type(supervisor) not in (bool, dict), "External supervisor capability required")
    method = getattr(supervisor, "require_" + action, None)
    _need(callable(method), "External supervisor lacks selected capability")
    _need(method(copy.deepcopy(context)) is None, "Supervisor must raise on refusal and return None on admission")


def _selected(runtime, selection_operand, pairing, meter):
    c = _runtime(runtime)
    raw = _operand(c, selection_operand, 32768, meter)
    selection = runtime.modules["policy.py"].selection(c.parse(raw), dict(runtime.source.incumbent_pin))
    _need(c.path(selection["repository"]) == runtime.source.repository, "Source and execution repository identity")
    pairing_raw = c.encoded(pairing)
    _need(len(pairing_raw) <= 65536, "Bounded paired operand selection")
    meter.read(len(pairing_raw) + 1)
    return selection, c.parse(pairing_raw), c.pin(raw), c.pin(pairing_raw)


def _context(runtime, action, selection, selection_pin, pairing_pin, origin, worker_end, whole_end):
    return {"action": action, "source": dict(runtime.source.source_pin),
            "incumbent_source": dict(runtime.source.incumbent_pin),
            "manifest_path": str(runtime.source.manifest_path), "repository": str(runtime.source.repository),
            "selection": selection_pin, "pairing": pairing_pin, "attempt": selection["output"],
            "origin": origin, "worker_end": worker_end, "original_whole_deadline": whole_end,
            "broker_dependency_sources": {name: {"path": runtime.source.paths["dependencies/" + name],
                                                   **_pin(body)} for name, body in runtime.source.dependencies.items()},
            "child_source_path_immutability_required": True,
            "model_child_interpreter_path": os.path.abspath(sys.executable),
            "native_image": selection["image"], "provider_token_and_state_admission_required": True,
            "three_panel_observer_required": True, "old_two_panel_observer_sufficient": False}


def execute(runtime, selection_operand, pairing, *, origin, worker_end, external_supervision):
    """Actual callable controller route; requires separately selected supervision.

    This function does not install signal handlers or supply a hard observer.
    The external deployment must own process-group/stream/native cleanup and
    original deadlines. Calling it is an execution action, not source validation.
    """
    c = _runtime(runtime)
    _need(type(origin) in (int, float) and math.isfinite(origin) and origin <= time.monotonic() < worker_end,
          "Inherited original worker clock")
    meter = _Meter(min(worker_end, origin + 120), 1048576)
    selection, pairing, selection_pin, pairing_pin = _selected(runtime, selection_operand, pairing, meter)
    whole_end = origin + selection["limits"]["whole_seconds"]
    _need(worker_end == whole_end - selection["limits"]["observer_seconds"], "Unchanged original worker endpoint")
    _supervise(external_supervision, "execution",
               _context(runtime, "execution", selection, selection_pin, pairing_pin, origin, worker_end, whole_end))
    for name in ("native.py", "adaptive_native.py"):
        runtime.modules[name].IMAGE = selection["image"]
    # Source old policy reviews and new paired method/token gates remain inside
    # the captured controller before creation or staging of the output attempt.
    result = runtime.modules["controller_successor.py"].run(
        selection, dict(runtime.source.source_pin), dict(runtime.source.old), origin, worker_end,
        runtime.source.read_reservations + meter.spent, pairing=pairing)
    c.before(worker_end)
    return result


def protected_grade(runtime, selection_operand, pairing, terminal_operand, *, original_whole_deadline,
                    deadline, read_limit, load_targets, external_supervision):
    """Authenticate complete 3,888-condition closure before protected scoring.

    The selected external supervisor must separately admit the completed worker,
    its process/stream closure, all original deadlines, and grading authority.
    The predecessor's two-panel observer is not an accepted replacement. Read
    clock checks are cooperative; an enclosing hard grade cutoff remains external.
    Target-callback I/O is a separate explicitly authorized operator allowance.
    """
    c = _runtime(runtime)
    meter = _Meter(deadline, read_limit)
    meter.read(runtime.source.read_reservations)
    selection, pairing, selection_pin, pairing_pin = _selected(runtime, selection_operand, pairing, meter)
    _need(type(original_whole_deadline) in (int, float) and math.isfinite(original_whole_deadline),
          "Finite original whole deadline")
    origin = original_whole_deadline - selection["limits"]["whole_seconds"]
    worker_end = original_whole_deadline - selection["limits"]["observer_seconds"]
    context = _context(runtime, "grading", selection, selection_pin, pairing_pin, origin,
                       worker_end, original_whole_deadline)
    context.update(terminal=c.only_pin(terminal_operand), terminal_path=str(c.path(terminal_operand["path"])),
                   grade_deadline=deadline, grade_read_limit=read_limit)
    _supervise(external_supervision, "grading", context)
    terminal = c.parse(_operand(c, terminal_operand, 65536, meter))
    binding = c.parse(runtime.source.old["BINDING.json"])
    runtime.modules["policy.py"].reviews(selection, dict(runtime.source.incumbent_pin), binding,
        lambda path, cap, pin: c.capture(path, cap, pin, meter.tick, meter.read))
    program = c.capture(selection["program"]["path"], 1048576, c.only_pin(selection["program"]), meter.tick, meter.read)
    paired = runtime.modules["pairing_api.py"].prepare(selection, dict(runtime.source.source_pin), program, pairing, meter)
    root = c.path(selection["output"])
    # Preserve original execution-clock arithmetic while checking fresh bounded
    # grade reads against this grade's deadline, never inventing an execution end.
    wrapped = types.SimpleNamespace(**vars(c))
    wrapped.before = lambda _execution_deadline: meter.tick()
    runtime.modules["admission_successor.py"].admit(
        wrapped, runtime.modules["contracts.py"], c.pin(runtime.source.old["reference_program.py"]),
        root, terminal, dict(runtime.source.source_pin), selection, original_whole_deadline,
        meter.read, paired=paired)
    # Admission above traverses all actual closures, models, retirements, native
    # and broker receipts. Only now reconstruct the three unchanged submissions.
    canonical = c.parse(c.capture(selection["canonical"]["path"], 4000000,
                                  c.only_pin(selection["canonical"]), meter.tick, meter.read))
    panel = runtime.modules["contracts.py"].canonical(canonical)
    submission = c.parse(c.capture(root / "submission.json", 2000000, terminal["submission"], meter.tick, meter.read))
    bundles = {name: {"schema": "neural083_predictions_v1", "generation": panel["generation"], "outcomes": []}
               for name in PANELS}
    for expected, row in zip(paired.schedule(panel), submission["conditions"]):
        _need(row["condition"] == expected and row["ordinal"] == expected["ordinal"], "Identical admitted collection schedule")
        folder = root / "conditions" / ("condition%04d" % expected["ordinal"])
        closed = c.parse(c.capture(folder / "CLOSED.json", 2000000, row["closed"], meter.tick, meter.read))
        result = c.parse(c.capture(folder / "infer" / "predictions.json", 100000, closed["output"], meter.tick, meter.read))
        bundles[expected["panel"]]["outcomes"].append(result)
    _need(all(len(bundle["outcomes"]) == 1296 for bundle in bundles.values()), "All three reconstructed panels")
    def protected():
        meter.tick()
        value = load_targets()
        meter.tick()
        return value
    result = runtime.modules["paired_report.py"].compare(
        panel, bundles, protected, runtime.modules["original_scorer"], external_admission=True)
    meter.tick()
    result.update(source=dict(runtime.source.source_pin), selection=selection_pin, pairing=pairing_pin,
                  managed_read_reservations=meter.spent,
                  target_callback_accounting="Separate trusted allowance; excluded from managed source/output reads",
                  observer_implemented_here=False, native_qualification=False)
    return result
