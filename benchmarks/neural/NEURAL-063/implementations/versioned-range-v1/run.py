"""Explicit operator CLI; no native/network stage runs without its selection flag."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import manifest
import pipeline
from range_io import Budget, Limits, RangeContractError, canonical


def pinned_json(path, sha256, cap):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > cap:
        raise RangeContractError("ordinary bounded JSON required")
    body = p.read_bytes()
    if hashlib.sha256(body).hexdigest() != sha256:
        raise RangeContractError("selected JSON identity mismatch")
    return manifest.unique_json(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("compile-assets", "headers", "metadata", "schedule", "project"))
    parser.add_argument("--selection", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--original-root", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--extent-index")
    parser.add_argument("--assets")
    parser.add_argument("--assets-sha256")
    parser.add_argument("--input-bank")
    parser.add_argument("--input-bank-sha256")
    parser.add_argument("--execute-authentic", action="store_true")
    args = parser.parse_args(argv)
    profile = pinned_json(args.profile, args.profile_sha256, 65536)
    if profile.get("schema") != "neural063_range_operation_profile_v1" or profile.get("stage") != args.stage:
        raise RangeContractError("exact selected stage profile required")
    if args.stage != "compile-assets" and not args.execute_authentic:
        raise RangeContractError("authentic operation requires explicit selection")
    if args.stage in ("headers", "metadata", "project") and profile.get("runtime_qualified") is not True:
        raise RangeContractError("native reader runtime qualification still required")
    pins = manifest.unique_json((HERE / "ORIGINAL_SOURCES.json").read_bytes())
    native, alg, original_io = pipeline.load_original(args.original_root, pins["files"])
    out = Path(args.output)
    if out.exists():
        raise RangeContractError("fresh output directory required")
    # Caller provisions the ordinary owned parent; no implicit ancestor creation.
    original_io.ordinary(out.parent, directory=True)
    out.mkdir(mode=0o700)
    reserve = profile["receipt_bytes"]
    if type(reserve) is not int or not 8192 <= reserve < profile["logical_write_bytes"]:
        raise RangeContractError("explicit final-receipt reserve required")
    meter = original_io.ByteMeter(profile["local_read_bytes"], profile["logical_write_bytes"] - reserve)
    store = original_io.ArtifactStore(out, meter)
    cap = profile["artifact_bytes"]
    if type(cap) is not int or cap <= 0 or cap > profile["logical_write_bytes"]:
        raise RangeContractError("finite per-artifact write allowance required")
    if args.stage in ("headers", "metadata", "project") and profile["range_limits"]["record_bytes"] + 8192 > reserve:
        raise RangeContractError("range records must fit the final-receipt reserve")
    budget = None
    result = None
    try:
        if args.stage == "compile-assets":
            if not args.extent_index:
                raise RangeContractError("saved exact extent index required")
            value = manifest.build(args.selection, args.extent_index)
            result = pipeline.write_value(store, "assets", value, "range_assets", cap)
        else:
            wrapped = manifest.read_pin(args.selection, manifest.SELECTION_BYTES, manifest.SELECTION_SHA256)
            selection = wrapped["original_selection"]
            assets = pinned_json(args.assets, args.assets_sha256, profile["input_json_bytes"])
            if args.stage == "headers":
                budget = Budget(Limits(**profile["range_limits"]))
                result = pipeline.headers(selection, assets, native, store, budget, profile["runtime_versions"], cap)
            elif args.stage == "metadata":
                bank = pinned_json(args.input_bank, args.input_bank_sha256, profile["input_json_bytes"])
                budget = Budget(Limits(**profile["range_limits"]))
                result = pipeline.metadata(selection, assets, bank, native, store, budget, profile["runtime_versions"], cap)
            else:
                bank = pinned_json(args.input_bank, args.input_bank_sha256, profile["input_json_bytes"])
                if args.stage == "schedule":
                    result = pipeline.schedules(selection, assets, bank, alg, store, cap)
                else:
                    budget = Budget(Limits(**profile["range_limits"]))
                    result = pipeline.projections(selection, assets, bank, native, alg, store, budget,
                                                  profile["runtime_versions"], cap)
        return result
    finally:
        # Failure still retains every earlier artifact and all admitted charges.
        # This receipt is not a scientific/runtime-completion certificate.
        status = {"schema": "neural063_range_operation_receipt_v1", "stage": args.stage,
                  "result": result, "complete": result is not None,
                  "range": None if budget is None else budget.receipt(),
                  "logical_store_usage_before_receipt": meter.snapshot(),
                  "unmetered_local_reads": "input/source profile capture and normal imports; not zero I/O",
                  "full_object_BLAKE2b_verified": False,
                  "scientific_equivalence_qualified": False}
        meter.write_limit = profile["logical_write_bytes"]
        pipeline.write_value(store, "operation_receipt", status, "range_operation_receipt", reserve)


if __name__ == "__main__":
    result = main()
    print(json.dumps({"status": "stage_returned", "artifact": result}, sort_keys=True))
