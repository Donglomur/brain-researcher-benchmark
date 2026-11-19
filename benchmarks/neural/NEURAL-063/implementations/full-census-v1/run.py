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
    if not isinstance(profile, dict) or set(profile) not in (TOP_KEYS, TOP_KEYS | {"partial_layouts"}):
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
    if "partial_layouts" in profile:
        validate_partial_config(profile["partial_layouts"], profile)
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



def validate_partial_config(value, profile):
    keys = {"manifest", "report", "seed_count", "seed_body_bytes", "max_new_planes",
            "seed_read_bytes", "provenance_bytes"}
    if type(value) is not dict or set(value) != keys or profile["stage"] != "layouts":
        raise ValueError("exact typed partial-layout configuration required")
    for key in ("manifest", "report"):
        pin(value[key])
        if value[key]["bytes"] > profile["input_json_bytes"]:
            raise ValueError("partial metadata cap")
    for key in keys - {"manifest", "report"}:
        positive(value[key], key)
    if not 0 < value["seed_count"] < 1936 or not 0 < value["max_new_planes"] <= 1936 - value["seed_count"]:
        raise ValueError("finite partial step within unchanged1936 inventory")
    if value["seed_body_bytes"] > 16777216 or value["provenance_bytes"] != 1048576:
        raise ValueError("bounded seed cache and provenance reservation")
    minimum = value["manifest"]["bytes"] + value["report"]["bytes"] + value["seed_body_bytes"] + 2 * (value["seed_count"] + 2)
    if value["seed_read_bytes"] < minimum or value["seed_read_bytes"] > profile["local_read_bytes"]:
        raise ValueError("complete seed authentication and EOF reserve")
    return value


def admit_partial_layouts(config, manifest_body, report_body, assets, read_seed, *, assets_pin):
    """Pure typed admission plus bounded reader callbacks; never creates a provider or writes.

    read_seed(name, bytes, sha256) returns exactly one authenticated local body.
    Every metadata/body admission finishes before this function returns any seeds.
    The caller owns ordinary-FD custody and read accounting, including EOF probes.
    """
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    def digest(value):
        return hashlib.sha256((json.dumps(value, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=False, allow_nan=False) + "\n").encode()).hexdigest()
    for raw, key in ((manifest_body, "manifest"), (report_body, "report")):
        require(type(raw) is bytes and len(raw) == config[key]["bytes"] and
                hashlib.sha256(raw).hexdigest() == config[key]["sha256"], "exact partial metadata body")
    seed, report = unique_json(manifest_body), unique_json(report_body)
    expected = {"experiments": 1936, "sessions": 703, "mice": 107, "rois": 133066}
    require(type(seed) is dict and set(seed) == {"schema", "source_counts", "selection_sha256", "assets_snapshot",
            "report", "source_root", "seed_count", "body_bytes", "entries"} and
            seed["schema"] == "neural063_partial_layout_seed_v1" and seed["source_counts"] == expected and
            seed["selection_sha256"] == SELECTION_SHA and seed["assets_snapshot"] == assets_pin and
            seed["seed_count"] == config["seed_count"] and seed["body_bytes"] == config["seed_body_bytes"],
            "fixed typed partial source identity")
    require(type(seed["source_root"]) is str and Path(seed["source_root"]).is_absolute() and
            len(seed["source_root"].encode()) <= 1024 and
            seed["report"] == {"path": str(Path(seed["source_root"]) / "census_report.json"), **config["report"]},
            "exact old report/root provenance")
    require(type(assets) is dict and assets.get("schema") == "neural063_versioned_range_assets_v1" and
            assets.get("selection_sha256") == SELECTION_SHA and assets.get("source_counts") == expected,
            "unchanged full asset inventory")
    values = assets.get("assets")
    require(type(values) is list and len(values) == 1936, "all1936 assets required")
    amap = {x["experiment"]: x for x in values}
    require(len(amap) == 1936, "unique asset identities")
    groups = {}
    for eid, row in amap.items():
        require(type(eid) is str and eid.isascii() and eid.isdigit() and len(eid) <= 16,
                "bounded experiment identity")
        groups.setdefault(row["session"], set()).add(eid)
    require(len(groups) == 703, "unchanged703 session inventory")
    require(type(report) is dict and report.get("schema") == "neural063_full_census_report_v1" and
            report.get("stage") == "layouts" and report.get("complete") is False and report.get("bank") is None and
            report.get("source_counts") == expected and report.get("selection_sha256") == SELECTION_SHA and
            report.get("dff_values_decoded") is False and report.get("benchmark_ready") is False and
            report.get("full_object_BLAKE2b_verified") is False, "partial structural report only")
    planes, sessions = report.get("planes"), report.get("sessions")
    require(type(planes) is list and len(planes) == 1936 and type(sessions) is list and len(sessions) == 703,
            "complete partial-run disposition inventory")
    pmap, smap = {x["experiment"]: x for x in planes}, {x["session"]: x for x in sessions}
    require(len(pmap) == 1936 and set(pmap) == set(amap) and len(smap) == 703 and set(smap) == set(groups) and
            all(pmap[e]["session"] == a["session"] and pmap[e].get("stage") == "layouts" and
                pmap[e].get("status") in ("complete", "failed", "unattempted") for e, a in amap.items()) and
            all(smap[s]["required_planes"] == len(es) for s, es in groups.items()),
            "exact complete inventory/session joins")
    entries = seed["entries"]
    completed = [x["experiment"] for x in planes if x["status"] == "complete"]
    require(type(entries) is list and len(entries) == config["seed_count"] and
            [x.get("experiment") for x in entries] == completed and len(set(completed)) == len(completed),
            "all and only complete seed rows in canonical report order")
    total = 0
    for entry in entries:
        require(type(entry) is dict and set(entry) == {"experiment", "session", "name", "bytes", "sha256", "asset_sha256"},
                "exact seed entry fields")
        eid = entry["experiment"]
        require(entry["name"] == "layout_" + eid + ".json" and entry["session"] == amap[eid]["session"], "exact seed name/session")
        pin({k: entry[k] for k in ("bytes", "sha256")})
        require(entry["bytes"] <= 1048576, "bounded individual seed")
        asset = {k: amap[eid][k] for k in ("experiment", "url", "version_id", "etag", "extent_bytes", "provider_blake2b")}
        require(entry["asset_sha256"] == digest(asset), "fixed-version seed asset identity")
        compact = {k: entry[k] for k in ("name", "bytes", "sha256")}; compact["role"] = "range_layout"
        require(pmap[eid].get("artifact_sha256") == entry["sha256"] and pmap[eid].get("artifacts") == [compact],
                "exact report seed artifact")
        total += entry["bytes"]
    require(total == config["seed_body_bytes"], "entire seed body cache bounded before read")
    admitted = []
    for entry in entries:
        raw = read_seed(entry["name"], entry["bytes"], entry["sha256"])
        require(type(raw) is bytes and len(raw) == entry["bytes"] and hashlib.sha256(raw).hexdigest() == entry["sha256"],
                "exact seed bytes before any provider")
        value = unique_json(raw)
        require(type(value) is dict and set(value) == {"schema", "experiment", "asset_sha256", "fields",
                "array_values_decoded", "full_object_BLAKE2b_verified"} and
                value["schema"] == "neural063_range_layout_v1" and value["experiment"] == entry["experiment"] and
                value["asset_sha256"] == entry["asset_sha256"] and type(value["fields"]) is dict and
                value["array_values_decoded"] is False and value["full_object_BLAKE2b_verified"] is False,
                "authenticated structural-only seed schema")
        admitted.append({"entry": entry, "body": raw})
    return {"schema": "neural063_admitted_partial_layouts_v1", "items": admitted,
            "source_root": seed["source_root"], "manifest": config["manifest"], "report": seed["report"],
            "body_bytes": total, "max_new_planes": config["max_new_planes"],
            "provenance_bytes": config["provenance_bytes"], "new_provider_requests_for_import": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--range-source-root", required=True)
    parser.add_argument("--original-root", required=True)
    parser.add_argument("--input-bank")
    parser.add_argument("--partial-layouts")
    parser.add_argument("--partial-root")
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
    partial_config = profile.get("partial_layouts")
    if bool(partial_config) != bool(args.partial_layouts) or bool(partial_config) != bool(args.partial_root):
        raise ValueError("exact typed partial input arguments")
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
    ranges = deps.range.Budget(limits) if partial_config is None else None
    admitted_partial = None
    partial_admission = None if partial_config is None else {"complete": False, "attempted_captures": 0,
        "configured_capture_byte_reservations_including_EOF": 0, "source_bytes_returned": 0,
        "new_provider_requests": 0, "accounting": "Declared source-byte-plus-EOF reservations; maintained meter charges source extents, not syscall requests."}
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
        if partial_config is not None:
            def capture_seed(path, size, descriptor=None):
                partial_admission["attempted_captures"] += 1
                partial_admission["configured_capture_byte_reservations_including_EOF"] += size + 2
                if partial_admission["configured_capture_byte_reservations_including_EOF"] > partial_config["seed_read_bytes"]:
                    raise ValueError("finite partial authentication read reservation")
                raw = deps.io.capture(path, size, descriptor=descriptor, meter=meter)
                partial_admission["source_bytes_returned"] += len(raw)
                return raw
            manifest_raw = capture_seed(args.partial_layouts, partial_config["manifest"]["bytes"])
            report_path = Path(args.partial_root) / "census_report.json"
            report_raw = capture_seed(report_path, partial_config["report"]["bytes"])
            def read_seed(name, size, sha):
                ref = deps.io.Artifact(str(Path(args.partial_root) / name), size, sha,
                                      "range_layout", "operator", "neural063-full-census-v1")
                return capture_seed(ref.path, size, descriptor=ref)
            admitted_partial = admit_partial_layouts(partial_config, manifest_raw, report_raw, assets,
                                                    read_seed, assets_pin=inputs["assets"])
            partial_admission["complete"] = True
        # No provider budget/object is constructed until the entire seed set authenticates.
        if ranges is None:
            ranges = deps.range.Budget(limits)
        scope_entered = True
        result = core.run_census(selection, assets, deps=deps, store=store, ranges=ranges,
                                 profile=profile["core"], input_bank=bank, partial_layouts=admitted_partial)
    except BaseException as exc:
        failure = core.failure_evidence(exc)
    finally:
        # Core owns the separately reserved complete disposition writer. Its
        # failure cannot consume this final receipt's protected reservation.
        meter.write_limit = profile["logical_write_bytes"]
        complete = failure is None and store.census_complete is True
        partial_step = getattr(store, "census_partial_step", None)
        step_complete = failure is None and type(partial_step) is dict and partial_step.get("bounded_step_complete") is True
        value = {"schema": "neural063_full_census_operation_receipt_v1",
                 "stage": profile["stage"], "profile_sha256": args.profile_sha256,
                 "complete": complete, "failure": failure, "scope_entered": scope_entered,
                 "report": result or store.census_report, "bank": store.census_bank,
                 "retained_census_artifact_count": len(store.census_artifacts),
                 "complete_artifact_inventory_is_in_report": store.census_report is not None,
                 "range": None if ranges is None else ranges.receipt(), "logical_usage_before_final_receipt": meter.snapshot(),
                 "partial_step": partial_step, "bounded_step_complete": step_complete, "partial_seed_admission": partial_admission,
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
    return 0 if complete or step_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
