"""Fresh confined same-epoch programme phases using the existing canonical Provider."""
from __future__ import annotations
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import types

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C

RUNTIME_FILES = {"contract.py", "epoch_programme.py", "epoch_producer.py",
                 "epoch_admission.py", "epoch_visual.py", "epoch_provider.py", "SOURCE_BINDINGS.json"}
COMMAND = ["/usr/local/bin/python", "-I", "-B", "/trusted/epoch_producer.py"]
INPUT_TARGETS = {"/input/case.json", "/input/signals.npy", "/program/program.py",
                 "/trusted/PROGRAMME.json", "/trusted/epoch_producer.py", "/trusted/contract.py"}


def descriptor(value, cap=8 * 2**20):
    C.need(type(value) is dict and set(value) == {"path", "bytes", "sha256"}
           and type(value["path"]) is str and Path(value["path"]).is_absolute(), "Exact absolute descriptor")
    return C.read_exact(value["path"], {k: value[k] for k in ("bytes", "sha256")}, cap)


def plain(value):
    return {key: value[key] for key in ("bytes", "sha256")}


def snapshot(path, cap):
    p = C.ordinary_path(path)
    C.need(p.is_file() and 0 < p.stat().st_size <= cap, "Bounded ordinary source")
    raw = p.read_bytes()
    return C.read_exact(p, C.pin(raw), cap)


def _module(name, path, expected):
    raw = C.read_exact(path, expected)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def load_runtime(implementations_root, finite_bindings_root=None):
    """Read only pinned existing source; never opens original signal or target files."""
    root = C.ordinary_path(implementations_root)
    bindings = C.decode((HERE / "SOURCE_BINDINGS.json").read_bytes())
    C.need(bindings["schema"] == "sleep007_epoch_dependencies_v1", "Exact epoch dependency map")
    finite = root / "finite-workflow-v1"
    common = _module("_sleep007_epoch_legacy_common", finite / "common.py", bindings["common"])
    # A private source preparation may point to the already accepted additive
    # binding directory; publication defaults to its final installed location.
    bound_root = finite if finite_bindings_root is None else C.ordinary_path(finite_bindings_root)
    bound_raw = C.read_exact(bound_root / "SOURCE_BINDINGS.json", bindings["finite_bindings"], 32768)
    common.HERE = bound_root
    C.need(common.bindings() == C.decode(bound_raw), "Exact accepted scientific dependency map")
    # Only the trusted existing grader needs the original unqualified import name.
    prior = sys.modules.get("common")
    sys.modules["common"] = common
    try:
        grading = _module("_sleep007_epoch_legacy_grading", finite / "grading.py", bindings["grading"])
    finally:
        if prior is None: sys.modules.pop("common", None)
        else: sys.modules["common"] = prior
    viewer = _module("_sleep007_epoch_original_viewer",
                     root / "whole-night-viewer-v1/viewer.py", bindings["viewer"])
    for name, expected in bindings["viewer_dependencies"].items():
        C.read_exact(root / "whole-night-viewer-v1" / name, expected)
    return {"implementations_root": root, "common": common, "grading": grading,
            "viewer": viewer, "provider": None, "bindings": bindings}


def source_freeze(value):
    frozen = C.decode(descriptor(value, 32768))
    C.need(type(frozen) is dict and set(frozen) == {"schema", "files"}
           and frozen["schema"] == "sleep007_epoch_source_v1"
           and set(frozen["files"]) == RUNTIME_FILES, "Complete exact epoch source freeze")
    for name, expected in frozen["files"].items():
        C.read_exact(HERE / name, expected)
    return frozen


def prepare_programme(programme_path, knowledge, source, root, *, image, generation_provenance=None):
    """Freeze before any target projection is opened; external provenance never self-qualifies."""
    frozen = source_freeze(source)
    knowledge_value = C.checked_knowledge(C.decode(descriptor(knowledge, 8192)))
    C.need(C.encode(knowledge_value) == descriptor(knowledge, 8192), "Canonical shared knowledge declaration")
    raw = snapshot(programme_path, 200000)
    raw.decode("utf-8", errors="strict")
    C.need(type(image) is str and len(image) == 71 and image.startswith("sha256:")
           and all(c in "0123456789abcdef" for c in image[7:]), "Immutable externally reviewed image")
    if generation_provenance is not None:
        descriptor(generation_provenance, 2**20)
    root = C.ordinary_path(root)
    root.mkdir(mode=0o700)
    programme = C.write_new(root / "program.py", raw)
    definition_value = {"schema": "sleep007_epoch_programme_definition_v1",
                        "condition": C.PROGRAMME_CONDITION, "information_contract": C.PAIR_CONDITION,
                        "programme": plain(programme), "knowledge": plain(knowledge), "image": image,
                        "source": plain(source), "generation_provenance": None if generation_provenance is None else plain(generation_provenance),
                        "additional_training_or_reference_assets": [],
                        "hidden_pretraining_verified": False, "matched_agent_provenance_qualified": False}
    definition = C.write_new(root / "PROGRAMME.json", C.encode(definition_value))
    return C.write_new(root / "PREPARED.json", C.encode({
        "schema": "sleep007_epoch_prepared_v1", "programme": programme, "definition": definition,
        "knowledge": knowledge, "source": source, "generation_provenance": generation_provenance,
        "scientific_input_reads": 0}))


def checked_prepared(prepared):
    value = C.decode(descriptor(prepared, 32768))
    C.need(type(value) is dict and set(value) == {"schema", "programme", "definition", "knowledge", "source",
           "generation_provenance", "scientific_input_reads"} and value["schema"] == "sleep007_epoch_prepared_v1"
           and value["scientific_input_reads"] == 0, "Pre-input immutable programme freeze")
    frozen = source_freeze(value["source"])
    descriptor(value["programme"], 200000).decode("utf-8", errors="strict")
    knowledge_raw = descriptor(value["knowledge"], 8192)
    knowledge = C.checked_knowledge(C.decode(knowledge_raw))
    C.need(C.encode(knowledge) == knowledge_raw, "Exact shared prior declaration")
    if value["generation_provenance"] is not None:
        descriptor(value["generation_provenance"], 2**20)
    definition = C.decode(descriptor(value["definition"], 32768))
    expected = {"schema": "sleep007_epoch_programme_definition_v1",
                "condition": C.PROGRAMME_CONDITION, "information_contract": C.PAIR_CONDITION,
                "programme": plain(value["programme"]), "knowledge": plain(value["knowledge"]),
                "image": definition.get("image"), "source": plain(value["source"]),
                "generation_provenance": None if value["generation_provenance"] is None else plain(value["generation_provenance"]),
                "additional_training_or_reference_assets": [],
                "hidden_pretraining_verified": False, "matched_agent_provenance_qualified": False}
    C.need(definition == expected and type(definition["image"]) is str
           and len(definition["image"]) == 71 and definition["image"].startswith("sha256:")
           and all(c in "0123456789abcdef" for c in definition["image"][7:]), "Exact frozen programme definition")
    return value, frozen, definition, knowledge


def file_mount(path, expected, purpose):
    p = C.ordinary_path(path)
    return {"path": str(p), "kind": "file", "purpose": purpose, "files": {p.name: C.checked_pin(expected)}}


def make_mounts(prepared_value, source_files, projection):
    """Only two epoch inputs and frozen code/definition; no parent directory mounts."""
    packet = C.read_projection(projection)
    root = C.ordinary_path(projection["root"])
    mounts = {
        "/input/case.json": file_mount(root / "case.json", projection["case"], "contract"),
        "/input/signals.npy": file_mount(root / "signals.npy", projection["signals"], "input"),
        "/program/program.py": file_mount(prepared_value["programme"]["path"], plain(prepared_value["programme"]), "program"),
        "/trusted/PROGRAMME.json": file_mount(prepared_value["definition"]["path"], plain(prepared_value["definition"]), "contract"),
        "/trusted/epoch_producer.py": file_mount(HERE / "epoch_producer.py", source_files["epoch_producer.py"], "program"),
        "/trusted/contract.py": file_mount(HERE / "contract.py", source_files["contract.py"], "program")}
    checked_mounts(mounts)
    return mounts, packet


def checked_mounts(mounts):
    C.need(type(mounts) is dict and set(mounts) == INPUT_TARGETS, "Exactly same-epoch inputs and frozen code")
    for target, item in mounts.items():
        C.need(type(item) is dict and set(item) == {"path", "kind", "purpose", "files"}
               and item["kind"] == "file" and item["purpose"] in {"contract", "input", "program"}
               and type(item["files"]) is dict and len(item["files"]) == 1
               and list(item["files"]) == [Path(item["path"]).name], "No directories or extra file exports")
        C.ordinary_path(item["path"])
        C.checked_pin(next(iter(item["files"].values())))
    return mounts


def phase_request(epoch_id, definition, definition_pin, exposure_pin, resources, origin, phase_deadline):
    case, index = C.checked_target(epoch_id)
    C.need(type(resources) is dict and all(type(v) is int and v > 0 for v in resources.values()),
           "Explicit finite existing Provider resources")
    C.need(all(type(v) in (int, float) and math.isfinite(v) for v in (origin, phase_deadline))
           and 0 <= origin < phase_deadline, "Immutable finite clock")
    return {"schema": "osl_owned_phase_request_v1",
            "phase_id": "sleep007_epoch_" + case.replace("-", "_") + "_" + str(index).zfill(5),
            "action": "held_attempt", "role": "A", "image": definition["image"], "command": list(COMMAND),
            "workdir": "/work", "source": C.checked_pin(definition_pin), "exposure": C.checked_pin(exposure_pin),
            "clock": {"origin": origin, "phase_deadline": phase_deadline},
            "resources": dict(resources), "output": {"kind": "generic", "manifest": "OUTPUTS.json"}}


def _provider_module(runtime):
    if runtime["provider"] is None:
        name = "_sleep_finite_transport.provider"
        if name in sys.modules:
            module = sys.modules[name]
            expected = runtime["implementations_root"] / "whole-night-programme/provider-public-mode-v2/vendor_transport/provider.py"
            C.need(Path(module.__file__).resolve() == expected.resolve(), "Exact existing Provider module")
        else:
            module = runtime["common"].load_provider()
        runtime["provider"] = module
    return runtime["provider"]


def validate_request(runtime, request, mounts, deadline):
    module = _provider_module(runtime)
    contract = sys.modules[module.__package__ + ".contract"]
    return contract.validate_request(request, mounts, deadline)


def validate_exposure(runtime, request, mounts, exposure, boundary_audit):
    module = _provider_module(runtime)
    contract = sys.modules[module.__package__ + ".contract"]
    value = C.decode(descriptor(exposure, 2**20))
    C.need(plain(exposure) == request["exposure"], "Exact externally approved exposure")
    contract.validate_exposure(value, request, mounts)
    C.need(plain(boundary_audit) == value["boundary_audit"], "Bound external image/source boundary audit")
    descriptor(boundary_audit, 2**20)
    return value


def open_provider(runtime, control_root, quarantine_root, provider_config, exposures, read_limit, write_limit):
    C.need(type(provider_config) is dict and set(provider_config) == {"docker_binary", "docker_socket"},
           "External admitted Docker interface only")
    C.need(type(exposures) is dict and set(exposures) == set(C.required_targets()), "External exposure approval for every target")
    registry = {}
    for approval in exposures.values():
        C.need(type(approval) is dict and set(approval) == {"exposure", "boundary_audit"},
               "External exposure and its bound audit evidence")
        item = approval["exposure"]
        value = C.decode(descriptor(item, 2**20))
        C.need(plain(approval["boundary_audit"]) == value["boundary_audit"], "Bound external boundary audit")
        descriptor(approval["boundary_audit"], 2**20)
        registry[item["sha256"]] = item["path"]
    module = _provider_module(runtime)
    return module.Provider(control_root, quarantine_root, provider_config["docker_binary"],
                           provider_config["docker_socket"], runtime["common"].bindings()["provider_manifest"],
                           registry, read_limit, write_limit)


def execute_phase(runtime, provider, prepared, projection, exposure, resources, origin, phase_deadline, deadline, journal,
                  *, boundary_audit):
    """One fresh container/volume/scratch. Closure is checked before its answer is accepted."""
    value, source, definition, knowledge = checked_prepared(prepared)
    mounts, packet = make_mounts(value, source["files"], projection)
    descriptor(exposure, 2**20)  # The canonical Provider validates externally approved exact image/mounts.
    request = phase_request(packet.epoch_id, definition, plain(value["definition"]), plain(exposure),
                            resources, origin, phase_deadline)
    C.need(type(deadline) in (int, float) and math.isfinite(deadline) and phase_deadline <= deadline,
           "Original campaign deadline")
    validate_request(runtime, request, mounts, deadline)
    validate_exposure(runtime, request, mounts, exposure, boundary_audit)
    # No participant code or callable is executed in this trusted process.
    result = provider.execute_phase(request, mounts, deadline, journal)
    observed = provider.observe(request["phase_id"], result["receipt"]["request_sha256"], result["receipt_pin"], deadline)
    C.need(observed["receipt"] == result["receipt"] and observed["receipt_pin"] == result["receipt_pin"]
           and observed.get("independent_candidate_channel") is True, "Independent canonical closure observation")
    receipt = observed["receipt"]
    request_path = C.ordinary_path(provider.control_root) / request["phase_id"] / "REQUEST.json"
    output = C.ordinary_path(receipt["quarantine_root"])
    record = {"epoch_id": packet.epoch_id, "projection": projection, "prepared": prepared,
              "exposure": exposure, "boundary_audit": boundary_audit,
              "request": {"path": str(request_path), **C.pin(_provider_module(runtime).encoded(request))},
              "receipt": {"path": result["receipt_path"], **result["receipt_pin"]},
              "observer_value": observed,
              "prediction": {"path": str(output / "prediction.json"), **receipt["output_inventory"]["files"]["prediction.json"]},
              "result": {"path": str(output / "RESULT.json"), **receipt["output_inventory"]["files"]["RESULT.json"]}}
    return record


def admit_phase(runtime, record, packet, expected_knowledge):
    """Read-only exact closure/input/output check; participant self-reports never suffice."""
    C.need(type(record) is dict and set(record) == {"epoch_id", "projection", "prepared", "exposure", "boundary_audit", "request", "receipt",
           "observer_value", "prediction", "result"} and record["epoch_id"] == packet.epoch_id,
           "Exact target phase record")
    projected = C.read_projection(record["projection"])
    C.need(projected.metadata() == packet.metadata() and projected.signals_npy == packet.signals_npy,
           "Only the authenticated original target signal and metadata")
    prepared, source, definition, knowledge = checked_prepared(record["prepared"])
    C.need(knowledge == C.checked_knowledge(expected_knowledge), "Same pinned shared prior declaration")
    request = C.decode(descriptor(record["request"], 32768))
    receipt = C.decode(descriptor(record["receipt"], 2**20))
    observer = record["observer_value"]
    C.need(type(observer) is dict and observer["receipt"] == receipt
           and observer["receipt_pin"] == plain(record["receipt"])
           and observer.get("independent_candidate_channel") is True, "Independent exact captured receipt")
    expected_request = phase_request(packet.epoch_id, definition, plain(prepared["definition"]),
                                     request["exposure"], request["resources"],
                                     request["clock"]["origin"], request["clock"]["phase_deadline"])
    C.need(request == expected_request, "Exact epoch producer request")
    C.need(receipt["schema"] == "osl_owned_phase_receipt_v1" and receipt["request_sha256"] == record["request"]["sha256"]
           and all(receipt[key] == request[key] for key in ("phase_id", "source", "image", "action", "role", "exposure"))
           and receipt["status"] == "captured" and receipt["error"] is None
           and receipt["all_native_resources_closed"] is True and receipt["producer_closed_before_capture"] is True
           and receipt["cli_reaped"] is True and receipt["deadline_exceeded"] is False
           and receipt["enforced_resource_limits"] == request["resources"], "Closed fresh canonical producer")
    natural = receipt["natural_exit"]
    C.need(type(natural["ExitCode"]) is int and natural["ExitCode"] == 0 and natural["Running"] is False
           and natural["Status"] == "exited" and natural["Dead"] is False and natural["Pid"] == 0
           and natural["OOMKilled"] is False, "Natural complete programme exit")
    retired = receipt["retired_resources"]
    C.need(type(retired) is list and len(retired) == 3 and len({r["name"] for r in retired}) == 3
           and sorted(r["kind"] for r in retired) == ["container", "container", "volume"]
           and all(r["closed"] is True and r.get("absence_observed") is True
                   and r.get("creation_outcome_unknown") is False for r in retired),
           "All unique owned resources closed before another target")
    mounts, _ = make_mounts(prepared, source["files"], record["projection"])
    validate_request(runtime, request, mounts, receipt["timing"]["original_deadline"])
    validate_exposure(runtime, request, mounts, record["exposure"], record["boundary_audit"])
    before = receipt["input_before"]
    C.need(before == receipt["input_after"] and set(before) == INPUT_TARGETS, "No richer or persistent participant inputs")
    for destination, expected in mounts.items():
        item = before[destination]
        C.need(item["kind"] == "file" and item["files"] == expected["files"], "Exact projected input/code identity")
    timing = receipt["timing"]
    C.need(set(timing) == {"origin", "original_deadline", "phase_deadline", "started", "finished"}
           and all(type(v) in (int, float) and math.isfinite(v) for v in timing.values())
           and timing["origin"] == request["clock"]["origin"]
           and timing["origin"] <= timing["started"] < timing["finished"] <= timing["phase_deadline"]
           <= request["clock"]["phase_deadline"] <= timing["original_deadline"], "Finite unchanged phase and campaign clock")
    inventory = receipt["output_inventory"]
    C.need(inventory["complete"] is True and set(inventory["files"]) == {"prediction.json", "RESULT.json", "OUTPUTS.json"},
           "Exactly one final target answer and transport envelope")
    for filename, key in (("prediction.json", "prediction"), ("RESULT.json", "result")):
        C.need(inventory["files"][filename] == plain(record[key])
               and C.ordinary_path(record[key]["path"]) == C.ordinary_path(Path(receipt["quarantine_root"]) / filename),
               "Captured output custody")
    prediction = C.decode(descriptor(record["prediction"], 8192))
    C.need(type(prediction) is dict and set(prediction) == {"condition", "epoch_id", "probabilities"}
           and prediction["condition"] == C.PROGRAMME_CONDITION and prediction["epoch_id"] == packet.epoch_id,
           "Exact same-target final answer")
    values = C.probabilities(prediction["probabilities"])
    report = C.decode(descriptor(record["result"], 8192))
    C.need(report == {"schema": "sleep007_epoch_producer_v1", "condition": C.PROGRAMME_CONDITION,
                     "epoch_id": packet.epoch_id, "programme": definition["programme"],
                     "knowledge": definition["knowledge"], "prediction": plain(record["prediction"]), "participant_exit": 0},
           "Exact captured producer envelope")
    return {"epoch_id": packet.epoch_id, "probabilities": values, "knowledge": C.pin(C.encode(knowledge)),
            "resources": retired, "timing": timing, "definition": plain(prepared["definition"]),
            "hidden_pretraining_verified": False, "matched_agent_provenance_qualified": False,
            "runtime_qualification": False, "scientific_qualification": False}
