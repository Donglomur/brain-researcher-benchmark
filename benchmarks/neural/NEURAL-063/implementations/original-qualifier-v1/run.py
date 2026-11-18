"""Explicit one-original N063 qualification entry point; no implicit data access."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).absolute().parent
sys.path.insert(0, str(HERE))
import acquire_original
import qualifier


def unique_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def bad(value):
        raise ValueError("nonfinite JSON literal")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


def exact_file(path, pin):
    p = Path(path)
    if (p.is_symlink() or not p.is_file() or p.stat().st_size != pin["bytes"]
            or (p.parent / "__pycache__").exists()):
        raise ValueError("exact ordinary uncached source required")
    body = p.read_bytes()
    if len(body) != pin["bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
        raise ValueError("source/input hash differs")
    return body


def load_sources(range_root, original_root):
    closure = unique_json((HERE / "DEPENDENCIES.json").read_bytes())
    if any(name in sys.modules for name in ("range_io", "pipeline", "manifest", "owner", "preparation")):
        raise ValueError("fresh dependency namespace required")
    root = Path(range_root).absolute()
    for name, pin in closure["range_source_files"].items():
        exact_file(root / name, pin)
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    try:
        modules = {name: importlib.import_module(name) for name in ("range_io", "pipeline", "manifest")}
        for name, module in modules.items():
            if Path(module.__file__).absolute() != root / (name + ".py"):
                raise ValueError("wrong range dependency origin")
        native, alg, original_io = modules["pipeline"].load_original(original_root, closure["original_files"])
        return SimpleNamespace(native=native, alg=alg, io=original_io,
                               range=modules["range_io"], pipeline=modules["pipeline"],
                               manifest=modules["manifest"]), closure
    finally:
        sys.path.pop(0)
        sys.dont_write_bytecode = old


def write(store, name, value, cap, deps):
    body = deps.io.canonical(value)
    if len(body) > cap:
        raise ValueError("complete operation receipt exceeds its reserved extent")
    return store.write(name + ".json", body, role="original_qualification_" + name,
                       visibility="operator", producer="neural063-original-qualification-v1").object()


def check_profile(profile):
    if (profile.get("schema") != "neural063_single_original_operation_profile_v1"
            or profile.get("selected") is not True
            or profile.get("stage") != "same_original_reader_qualification"):
        raise ValueError("separately selected exact one-original operation profile required")
    qualifier.validate_profile(profile)
    for name in ("local_read_bytes", "total_write_bytes", "controller_artifact_bytes", "acquisition_receipt_bytes",
                 "range_receipt_bytes", "final_receipt_bytes"):
        if type(profile.get(name)) is not int or profile[name] <= 0:
            raise ValueError("positive finite operation allowance required")
    if profile["range_receipt_bytes"] < profile["range_limits"]["record_bytes"] + 8192:
        raise ValueError("complete range receipt is not reserved")
    final = profile["range_receipt_bytes"] + profile["final_receipt_bytes"] + profile["acquisition_receipt_bytes"]
    ordinary = profile["metadata_artifact_bytes"] + profile["projection_artifact_bytes"] + profile["comparison_artifact_bytes"]
    raw = profile["candidate"]["extent_bytes"]
    if type(raw) is not int or raw <= 0:
        raise ValueError("positive exact original extent required")
    if profile["range_limits"]["block_bytes"] >= raw:
        raise ValueError("range blocks must remain smaller than the complete original")
    if final + ordinary + raw + profile["controller_artifact_bytes"] > profile["total_write_bytes"]:
        raise ValueError("all named writers and failure receipts require prospective reservation")
    cost = (profile["total_write_bytes"] + profile["range_limits"]["response_body_bytes"]
            + profile["range_limits"]["max_requests"] * 32768
            + profile["acquisition_limits"]["parser_reservation_bytes"])
    if profile.get("conservative_global_bytes") != cost:
        raise ValueError("disjoint full-body/range/other-write/header cost differs")
    return final


def capture_input(path, pin, role, deps, meter):
    ref = deps.io.Artifact(str(Path(path).absolute()), pin["bytes"], pin["sha256"],
                           role, "operator", "frozen_qualification_input")
    return unique_json(deps.io.capture(path, pin["bytes"], descriptor=ref, meter=meter))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--range-source-root", required=True)
    parser.add_argument("--original-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute-authentic", action="store_true")
    args = parser.parse_args(argv)
    p = Path(args.profile)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 65536:
        raise ValueError("ordinary bounded profile required")
    body = p.read_bytes()
    if hashlib.sha256(body).hexdigest() != args.profile_sha256:
        raise ValueError("operation profile hash mismatch")
    profile = unique_json(body)
    if not args.execute_authentic:
        raise ValueError("authentic execution is not selected by source presence")
    final_reserve = check_profile(profile)
    deps, closure = load_sources(args.range_source_root, args.original_root)
    if profile["runtime_versions"] != closure["runtime_versions"]:
        raise ValueError("selected runtime compatibility differs")
    acquisition_limits = acquire_original.AcquisitionLimits(**profile["acquisition_limits"]).validate()
    range_limits = deps.range.Limits(**profile["range_limits"]).validate()
    if acquisition_limits.response_body_bytes != profile["candidate"]["extent_bytes"]:
        raise ValueError("exact single full-body reservation required")
    from importlib.metadata import version
    if any(version(name) != expected for name, expected in profile["runtime_versions"].items()):
        raise ValueError("installed maintained-stack versions differ before acquisition")
    out = Path(args.output).absolute()
    deps.io.ordinary(out.parent, directory=True)
    if out.exists() or out.is_symlink():
        raise ValueError("fresh output namespace required")
    capacity = os.statvfs(out.parent)
    if capacity.f_bavail * capacity.f_frsize < profile["total_write_bytes"]:
        raise ValueError("complete original and failed/output writes lack current storage")
    out.mkdir(mode=0o700)
    owner_write_cap = profile["total_write_bytes"] - profile["controller_artifact_bytes"]
    meter = deps.io.ByteMeter(profile["local_read_bytes"], owner_write_cap - final_reserve)
    store = deps.io.ArtifactStore(out, meter)
    source = acquisition = result = ranges = range_ref = None
    failure = None
    try:
        wrapped = capture_input(args.selection, profile["selection"], "source_selection", deps, meter)
        if (profile["selection"]["bytes"] != deps.manifest.SELECTION_BYTES
                or profile["selection"]["sha256"] != deps.manifest.SELECTION_SHA256):
            raise ValueError("original full selection must remain pinned")
        selection = wrapped["original_selection"]
        assets = capture_input(args.assets, profile["assets"], "range_assets", deps, meter)
        bank = deps.manifest.validate_assets(assets, selection)
        candidate = profile["candidate"]
        asset = bank[candidate["experiment"]]
        row = next(r for r in selection["experiments"] if r["ophys_experiment_id"] == asset.experiment)
        session_planes = sum(r["ophys_session_id"] == row["ophys_session_id"] for r in selection["experiments"])
        if (qualifier.digest(vars(asset), deps) != candidate["asset_sha256"]
                or qualifier.digest(row, deps) != candidate["row_sha256"]
                or asset.extent_bytes != candidate["extent_bytes"]
                or len(row["rois"]) != candidate["published_valid_rois"]
                or session_planes != candidate["original_session_planes"]):
            raise ValueError("selected original identity/lineage/support scope differs")
        source, acquisition = acquire_original.acquire(asset, store.path("original.nwb"), meter,
                                                       acquisition_limits, owner_io=deps.io)
        ranges = deps.range.Budget(range_limits)
        result = qualifier.qualify(asset, source, row, deps=deps, store=store,
                                   ranges=ranges, profile=profile)
    except BaseException as exc:
        if isinstance(exc, acquire_original.AcquisitionError):
            acquisition = exc.receipt
        failure = {"class": type(exc).__name__, "message": str(exc)[:4096]}
    finally:
        # Reserved terminal receipts survive exhausted ordinary writes. The raw
        # original is charged exactly once by acquire(), even if incomplete.
        meter.write_limit = owner_write_cap
        acquisition_ref = None
        if acquisition is not None:
            acquisition_ref = write(store, "acquisition_receipt", acquisition,
                                    profile["acquisition_receipt_bytes"], deps)
        if ranges is not None:
            range_ref = write(store, "range_receipt", ranges.receipt(),
                              profile["range_receipt_bytes"], deps)
        receipt = {"schema": "neural063_single_original_operation_receipt_v1",
                   "profile_sha256": args.profile_sha256, "comparison": result,
                   "complete": failure is None and result is not None,
                   "failure": failure, "native_source": source,
                   "retained_intermediate_artifacts": getattr(store, "qualification_artifacts", []),
                   "intermediates_are_not_completion": True,
                   "acquisition_receipt": acquisition_ref, "range_receipt": range_ref,
                   "logical_usage_before_final_receipt": meter.snapshot(),
                   "source_capture_and_normal_import_io": "separate unmetered bootstrap reads, not zero physical I/O",
                   "all_plane_session_consensus_established": False,
                   "full_cohort_scientific_equivalence_qualified": False,
                   "full_benchmark_complete": False, "models_or_scoring": False}
        final = write(store, "operation_receipt", receipt, profile["final_receipt_bytes"], deps)
    print(json.dumps({"status": "failed" if failure else "returned", "receipt": final}, sort_keys=True))
    return 1 if failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
