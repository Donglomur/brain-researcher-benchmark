"""Explicit operator-only NEURAL-063 census; projection is never a stage."""
import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace


HERE = Path(__file__).absolute().parent
STAGES = {"layouts", "metadata_support", "chunks"}
TOP_KEYS = {
    "schema", "stage", "selected", "runtime_qualified", "input_pins",
    "component_pins", "input_json_bytes", "local_read_bytes",
    "logical_write_bytes", "receipt_bytes", "range_limits",
    "header_planning_bytes_per_request", "conservative_global_bytes",
    "declared_ram_bytes", "outer_wall_seconds", "core", "notes",
}
SELECTION_BYTES = 9605316
SELECTION_SHA = "d484ac018c7b7a0cc9ed826de5977a9ec9724a82e68126ec7e13be23507c1ab7"
DISPOSITION_MIN = 8192 + 4096 * 1936 + 2048 * 703


def unique_json(body):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    def real(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite JSON number")
        return result

    def bad(_):
        raise ValueError("nonfinite JSON literal")

    return json.loads(body, object_pairs_hook=pairs, parse_float=real, parse_constant=bad)


def positive(value, name):
    if type(value) is not int or not 0 < value <= 2**63 - 1:
        raise ValueError("positive bounded integer required: " + name)
    return value


def pin(value):
    if not isinstance(value, dict) or set(value) != {"bytes", "sha256"}:
        raise ValueError("exact byte/hash descriptor required")
    positive(value["bytes"], "descriptor bytes")
    h = value["sha256"]
    if not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        raise ValueError("exact lowercase SHA256 required")
    return value


def exact_file(path, descriptor, *, cache_guard=False):
    descriptor = pin(descriptor)
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size != descriptor["bytes"]:
        raise ValueError("ordinary exact source extent required")
    if cache_guard and (p.parent / "__pycache__").exists():
        raise ValueError("uncached source directory required")
    body = p.read_bytes()
    if len(body) != descriptor["bytes"] or hashlib.sha256(body).hexdigest() != descriptor["sha256"]:
        raise ValueError("source identity changed")
    return body


def read_profile(path, sha256):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 65536:
        raise ValueError("ordinary bounded profile required")
    body = p.read_bytes()
    if hashlib.sha256(body).hexdigest() != sha256:
        raise ValueError("operation profile hash differs")
    return unique_json(body)


def validate_operation_profile(profile, *, require_selected=True):
    if not isinstance(profile, dict) or set(profile) != TOP_KEYS:
        raise ValueError("exact full-census operation profile fields required")
    if profile["schema"] != "neural063_full_census_operation_profile_v1" or profile["stage"] not in STAGES:
        raise ValueError("explicit census stage required; project is forbidden")
    if type(profile["selected"]) is not bool or type(profile["runtime_qualified"]) is not bool:
        raise ValueError("selection/runtime qualification must be explicit booleans")
    if require_selected and (not profile["selected"] or not profile["runtime_qualified"]):
        raise ValueError("separately selected and qualified actual operation required")
    for name in ("input_json_bytes", "local_read_bytes", "logical_write_bytes", "receipt_bytes",
                 "header_planning_bytes_per_request", "conservative_global_bytes",
                 "declared_ram_bytes", "outer_wall_seconds"):
        positive(profile[name], name)
    if not isinstance(profile["notes"], str) or len(profile["notes"].encode()) > 8192:
        raise ValueError("bounded profile explanation required")
    core = profile["core"]
    if not isinstance(core, dict) or core.get("stage") != profile["stage"]:
        raise ValueError("wrapper/core stages must agree")
    for name in ("disposition_bytes", "total_artifact_reservation_bytes"):
        positive(core.get(name), name)
    if core["disposition_bytes"] < DISPOSITION_MIN:
        raise ValueError("full1936-plane/703-session failure inventory is not reserved")
    limits = profile["range_limits"]
    names = {"max_requests", "response_body_bytes", "logical_read_bytes", "record_bytes",
             "block_bytes", "cache_blocks", "hdf5_cache_bytes", "read_operation_bytes",
             "seconds", "request_seconds"}
    if not isinstance(limits, dict) or set(limits) != names:
        raise ValueError("exact maintained-reader limit fields required")
    for name, value in limits.items():
        positive(value, "range " + name)
    if limits["seconds"] >= profile["outer_wall_seconds"]:
        raise ValueError("outer owned runtime must retain explicit closure time")
    if profile["header_planning_bytes_per_request"] != 32768:
        raise ValueError("selected conservative header planning policy differs")
    if profile["receipt_bytes"] < limits["record_bytes"] + 16384:
        raise ValueError("complete range records and bounded final receipt are not reserved")
    ordinary = profile["logical_write_bytes"] - profile["receipt_bytes"] - core["disposition_bytes"]
    if ordinary < core["total_artifact_reservation_bytes"]:
        raise ValueError("ordinary artifacts consume a protected terminal reserve")
    # Header planning reserves the complete configured request count even when
    # another counter causes an earlier refusal. It is not a physical wire cap.
    global_cap = (profile["logical_write_bytes"] + limits["response_body_bytes"]
                  + limits["max_requests"] * profile["header_planning_bytes_per_request"])
    if profile["conservative_global_bytes"] != global_cap:
        raise ValueError("disjoint body/header/write planning total differs")
    if not isinstance(profile["input_pins"], dict) or set(profile["input_pins"]) != {"selection", "assets", "input_bank"}:
        raise ValueError("exact frozen input descriptor slots required")
    if not isinstance(profile["component_pins"], dict) or set(profile["component_pins"]) != {"run.py", "census.py", "DEPENDENCIES.json"}:
        raise ValueError("exact component source descriptor slots required")
    if require_selected:
        for name, descriptor in profile["component_pins"].items():
            pin(descriptor)
        inputs = profile["input_pins"]
        for name in ("selection", "assets"):
            pin(inputs[name])
            if inputs[name]["bytes"] > profile["input_json_bytes"]:
                raise ValueError("frozen whole input exceeds its admission cap")
        if inputs["selection"] != {"bytes": SELECTION_BYTES, "sha256": SELECTION_SHA}:
            raise ValueError("unchanged complete original selection required")
        if profile["stage"] == "layouts":
            if inputs["input_bank"] is not None:
                raise ValueError("layout stage cannot inherit a partial bank")
        else:
            pin(inputs["input_bank"])
            if inputs["input_bank"]["bytes"] > profile["input_json_bytes"]:
                raise ValueError("complete predecessor bank exceeds its input allowance")
    return {"ordinary_write_limit": ordinary,
            "disposition_reserved_bytes": core["disposition_bytes"],
            "final_receipt_reserved_bytes": profile["receipt_bytes"],
            "maximum_body_planning_bytes": limits["response_body_bytes"],
            "maximum_header_planning_bytes": limits["max_requests"] * 32768,
            "conservative_global_bytes": global_cap,
            "expected_transfer_bytes": None,
            "guaranteed_complete_census_budget": False,
            "hard_RAM_certificate": False}


def load_sources(profile, range_root, original_root):
    for name, descriptor in profile["component_pins"].items():
        exact_file(HERE / name, descriptor, cache_guard=True)
    closure = unique_json((HERE / "DEPENDENCIES.json").read_bytes())
    if closure.get("schema") != "neural063-full-census-source-dependency-closure-v1":
        raise ValueError("exact census dependency closure required")
    if profile["core"]["runtime_versions"] != closure["runtime_versions"]:
        raise ValueError("maintained runtime version selection differs")
    names = ("census", "manifest", "pipeline", "range_io", "owner", "preparation")
    if any(name in sys.modules for name in names):
        raise ValueError("fresh scientific/census source namespace required")
    root = Path(range_root).absolute()
    for name, descriptor in closure["range_source_files"].items():
        exact_file(root / name, descriptor, cache_guard=True)
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(HERE))
    try:
        modules = {name: importlib.import_module(name) for name in ("census", "manifest", "pipeline", "range_io")}
        for name, module in modules.items():
            expected = HERE if name == "census" else root
            if Path(module.__file__).absolute() != expected / (name + ".py"):
                raise ValueError("wrong source module origin")
        modules["census"].validate_profile(profile["core"])
        native, alg, original_io = modules["pipeline"].load_original(original_root, closure["original_files"])
        deps = SimpleNamespace(pipeline=modules["pipeline"], native=native, alg=alg,
                               io=original_io, range=modules["range_io"], manifest=modules["manifest"])
        return modules["census"], deps
    finally:
        sys.path.pop(0)
        sys.path.pop(0)


def capture_input(path, descriptor, role, deps, meter):
    ref = deps.io.Artifact(str(Path(path).absolute()), descriptor["bytes"], descriptor["sha256"],
                           role, "operator", "frozen_neural063_census_input")
    return deps.io.decode(deps.io.capture(path, descriptor["bytes"], descriptor=ref, meter=meter))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--range-source-root", required=True)
    parser.add_argument("--original-root", required=True)
    parser.add_argument("--input-bank")
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute-authentic", action="store_true")
    args = parser.parse_args(argv)
    for value in vars(args).values():
        if isinstance(value, str) and len(value.encode()) > 1024:
            raise ValueError("bounded explicit operator argument required")
    profile = read_profile(args.profile, args.profile_sha256)
    bounds = validate_operation_profile(profile)
    if not args.execute_authentic:
        raise ValueError("source presence does not select authentic census execution")
    if (profile["stage"] == "layouts") != (args.input_bank is None):
        raise ValueError("exact stage predecessor bank required")
    core, deps = load_sources(profile, args.range_source_root, args.original_root)
    from importlib.metadata import version
    if any(version(name) != expected for name, expected in profile["core"]["runtime_versions"].items()):
        raise ValueError("installed maintained runtime versions differ before acquisition")
    limits = deps.range.Limits(**profile["range_limits"]).validate()
    out = Path(args.output).absolute()
    deps.io.ordinary(out.parent, directory=True)
    if out.exists() or out.is_symlink():
        raise ValueError("fresh output namespace required")
    capacity = os.statvfs(out.parent)
    if capacity.f_bavail * capacity.f_frsize < profile["logical_write_bytes"]:
        raise ValueError("complete cumulative writer reservation lacks current storage")
    out.mkdir(mode=0o700)
    meter = deps.io.ByteMeter(profile["local_read_bytes"], bounds["ordinary_write_limit"])
    store = deps.io.ArtifactStore(out, meter)
    store.census_complete = False
    store.census_report = None
    store.census_bank = None
    store.census_artifacts = []
    ranges = deps.range.Budget(limits)
    result = failure = None
    scope_entered = False
    try:
        inputs = profile["input_pins"]
        wrapped = capture_input(args.selection, inputs["selection"], "source_selection", deps, meter)
        selection = wrapped["original_selection"]
        assets = capture_input(args.assets, inputs["assets"], "range_assets", deps, meter)
        deps.manifest.validate_assets(assets, selection)
        bank = None if args.input_bank is None else capture_input(args.input_bank, inputs["input_bank"],
                                                                "complete_census_predecessor", deps, meter)
        scope_entered = True
        result = core.run_census(selection, assets, deps=deps, store=store, ranges=ranges,
                                 profile=profile["core"], input_bank=bank)
    except BaseException as exc:
        failure = {"class": type(exc).__name__, "message": str(exc)[:256]}
    finally:
        # Core owns the separately reserved complete disposition writer. Its
        # failure cannot consume this final receipt's protected reservation.
        meter.write_limit = profile["logical_write_bytes"]
        complete = failure is None and store.census_complete is True
        value = {"schema": "neural063_full_census_operation_receipt_v1",
                 "stage": profile["stage"], "profile_sha256": args.profile_sha256,
                 "complete": complete, "failure": failure, "scope_entered": scope_entered,
                 "report": result or store.census_report, "bank": store.census_bank,
                 "retained_census_artifact_count": len(store.census_artifacts),
                 "complete_artifact_inventory_is_in_report": store.census_report is not None,
                 "range": ranges.receipt(), "logical_usage_before_final_receipt": meter.snapshot(),
                 "planning_bounds": bounds,
                 "bootstrap_IO": "Source/import/profile bootstrap reads are separately unmetered; pinned selection/assets/bank and artifact reads use the local meter.",
                 "runtime_enforcement": "Requires separately selected owned outer deadline/RSS observation and root admission; this CLI does not supply a hard OS RAM or wire ceiling.",
                 "projection_performed": False, "full_object_BLAKE2b_verified": False,
                 "full_benchmark_complete": False, "models_or_scoring": False}
        # Receipt content is bounded by charged range records, one descriptor
        # per report/bank, fixed fields and a256-character failure message.
        body = deps.io.canonical(value)
        if len(body) > profile["receipt_bytes"]:
            raise ValueError("complete final receipt exceeds its protected reserve")
        receipt = store.write("operation_receipt.json", body, role="full_census_operation_receipt",
                              visibility="operator", producer="neural063-full-census-v1").object()
    print(json.dumps({"status": "complete" if complete else "incomplete", "receipt": receipt}, sort_keys=True))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
