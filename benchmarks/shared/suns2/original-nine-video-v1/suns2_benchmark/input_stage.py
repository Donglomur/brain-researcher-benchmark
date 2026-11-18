"""One explicitly admitted stage of original SUNS2 source preparation.

This entry point requires a pinned protocol and a matching active native lease.
It never allocates resources, admits itself, retries, runs a model or scores a
candidate. The outer launcher must supply the pinned wall watchdog.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time

SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT))


class StageRefusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise StageRefusal(message)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def bounded_json(path, expected_sha=None, cap=131072):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        initial = os.fstat(stream.fileno())
        require(stat.S_ISREG(initial.st_mode) and initial.st_nlink == 1 and initial.st_size <= cap,
                "bounded regular JSON input required")
        raw = stream.read(cap+1)
        require(len(raw) == initial.st_size, "JSON byte-size changed")
    if expected_sha is not None:
        require(hashlib.sha256(raw).hexdigest() == expected_sha, "JSON identity mismatch")
    return json.loads(raw, object_pairs_hook=_unique)


def verify_pin(pin):
    path = Path(pin["path"])
    # Runtime executables may intentionally be declared symlinks; the protocol
    # pins both link text and resolved content. Ordinary code files are regular.
    if "symlink_target" in pin:
        require(path.is_symlink() and os.readlink(path) == pin["symlink_target"], "runtime symlink changed")
    else:
        require(not path.is_symlink(), "unpinned source symlink")
    require(path.is_file() and path.stat().st_size == pin["bytes"], "frozen file size mismatch")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1048576):
            digest.update(block)
    require(digest.hexdigest() == pin["sha256"], "frozen file digest mismatch")


def authority(profile, protocol_path, protocol_sha, stage):
    ledger = bounded_json(profile["resource_ledger"], cap=2097152)
    configured = profile["stages"][stage]
    runs = [row for row in ledger.get("native_runs", []) if row.get("id") == configured["native_id"]]
    require(len(runs) == 1, "exact native lease record required")
    run = runs[0]
    require(run.get("status") == "running" and run.get("owner") == profile["owner"] and
            run.get("approval_id") == configured["approval_id"] and
            run.get("protocol", {}).get("sha256") == protocol_sha and
            Path(run.get("protocol", {}).get("path", "")) == Path(protocol_path),
            "stage has no matching active admitted native lease")
    for grant in profile["payload_reservations"]:
        rows = [row for row in ledger.get("reservations", []) if row.get("id") == grant["id"]]
        require(len(rows) == 1 and rows[0].get("status") == "active" and
                rows[0].get("owner") == profile["owner"] and
                rows[0].get("reserved_bytes") == grant["bytes"] and
                rows[0].get("destination") == grant["destination"],
                "exact original-input allocation is not active")
    return {"native_id": configured["native_id"], "approval_id": configured["approval_id"],
            "protocol_sha256": protocol_sha, "owner": profile["owner"]}


def _prior_result(path, stage, profile, protocol_sha):
    value = bounded_json(path)
    require(value.get("stage") == stage and value.get("status") == "succeeded",
            "previous stage did not complete successfully")
    require(type(value.get("result")) is dict, "previous result schema")
    selected = profile["stages"][stage]
    expected_authority = {"native_id": selected["native_id"], "approval_id": selected["approval_id"],
                          "protocol_sha256": protocol_sha, "owner": profile["owner"]}
    require(value.get("authority") == expected_authority, "previous stage authority belongs to another pipeline")
    process = bounded_json(Path(profile["process_evidence"])/f"{stage}-process.json")
    require(process.get("stage") == stage and process.get("authority") == expected_authority and
            process.get("status") == "succeeded" and process.get("returncode") == 0 and
            process.get("error") is None and process.get("capture_complete") is True and
            type(process.get("child_peak_RSS_bytes")) is int and
            process["child_peak_RSS_bytes"] <= 268435456,
            "previous bounded process did not qualify")
    ledger = bounded_json(profile["resource_ledger"], cap=2097152)
    rows = [row for row in ledger.get("native_runs", []) if row.get("id") == selected["native_id"]]
    require(len(rows) == 1 and rows[0].get("status") == "succeeded" and rows[0].get("exit_code") == 0 and
            rows[0].get("owner") == profile["owner"] and rows[0].get("approval_id") == selected["approval_id"] and
            rows[0].get("protocol", {}).get("sha256") == protocol_sha,
            "previous outer native run did not qualify")
    return value["result"]


def execute(stage, profile, protocol_sha):
    from suns2_benchmark import input_acquisition as acquisition
    from suns2_benchmark.constants import VIDEO_IDS
    selection_pin = profile["selection"]
    proposal = bounded_json(selection_pin["path"], selection_pin["sha256"])
    identity = proposal["source_selection"]
    require(identity["object_id"] == 49636131 and identity["archive_bytes"] == 248562067
            and identity["expected_expanded_bytes"] == 270030454,
            "original full input selection changed")
    download, bank = Path(profile["download_directory"]), Path(profile["bank_directory"])
    results = Path(profile["execution_evidence"])
    if stage == "acquire":
        download.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        parent_info = download.parent.stat()
        require(not download.parent.is_symlink() and stat.S_ISDIR(parent_info.st_mode)
                and parent_info.st_uid == os.getuid() and parent_info.st_mode & 0o077 == 0,
                "protected payload parent required")
        return acquisition.acquire_complete_archive(identity, download, results/"http", wall_seconds=175)
    acquired = _prior_result(results/"acquire-result.json", "acquire", profile, protocol_sha)
    require(acquired.get("status") == "complete_object_md5_authenticated" and
            acquired.get("object_id") == identity["object_id"] and
            acquired.get("archive_bytes") == identity["archive_bytes"] and
            acquired.get("archive_md5") == identity["published_MD5"] and
            acquired.get("captured_body_bytes") == identity["archive_bytes"] and
            acquired.get("archive_path") == str(download/"archive.zip"),
            "successful complete-source acquisition identity required")
    if stage == "zip":
        reference_pin = profile["protected_reference_inputs"]
        references = bounded_json(reference_pin["path"], reference_pin["sha256"])
        old_gt = {row["original_member_name"]: row["sha256"] for row in references["members"]
                  if row["role"] == "ground_truth"}
        result = acquisition.extract_complete_archive(download/"archive.zip", identity, bank,
            expected_archive_sha256=acquired["archive_sha256"], expected_gt_pins=old_gt,
            wall_seconds=115)
        plugin_root = Path(profile["private_plugin_directory"])
        plugin_root.mkdir(mode=0o700, exist_ok=False)
        return result
    require(stage == "hdf5", "unknown preparation stage")
    extracted = _prior_result(results/"zip-result.json", "zip", profile, protocol_sha)
    require(extracted.get("status") == "complete_original_input_ZIP_authenticated" and
            extracted.get("archive_sha256") == acquired["archive_sha256"] and
            extracted.get("archive_md5") == identity["published_MD5"] and
            extracted.get("written_payload_bytes") == identity["expected_expanded_bytes"] and
            extracted.get("write_observations_complete") is True and extracted.get("bank") == str(bank),
            "complete authenticated original bank required")
    require(type(extracted.get("members")) is list and len(extracted["members"]) == 19,
            "complete source member list required")
    members = {row["name"]: row for row in extracted["members"]}
    require(len(members) == 19 and set(members) == {e["name"] for e in identity["all_20_entries"] if not e["directory"]},
            "original source names changed")
    expected_names = [f"{video}.h5" for video in VIDEO_IDS] + ["1P_spike_tempolate.h5"]
    entries = [{"name": name, "bytes": members[name]["bytes"], "sha256": members[name]["sha256"]}
               for name in expected_names]
    from suns2_benchmark import input_preparation as preparation
    runtime = preparation.initialize_runtime(profile["HDF5_runtime_versions"],
                                              profile["private_plugin_directory"])
    return preparation.inspect_bank(bank, entries, runtime, deadline=time.monotonic()+115)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("acquire", "zip", "hdf5"))
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    args = parser.parse_args(argv)
    started = time.monotonic()
    profile = bounded_json(args.protocol, args.protocol_sha256)
    require(profile.get("schema") == "suns2-original-input-native-protocol/v1", "native protocol schema")
    for pin in profile["frozen_files"]:
        verify_pin(pin)
    admission = authority(profile, args.protocol, args.protocol_sha256, args.stage)
    evidence = Path(profile["execution_evidence"])
    if args.stage == "acquire":
        evidence.mkdir(mode=0o700, exist_ok=False)
    else:
        require(evidence.is_dir() and not evidence.is_symlink(), "existing protected stage evidence required")
    receipt_path = evidence/f"{args.stage}-result.json"
    require(not receipt_path.exists(), "stage already attempted; automatic retry forbidden")
    receipt = {"schema": "suns2-original-input-stage-result/v1", "stage": args.stage,
               "authority": admission, "status": "started", "result": None}
    from suns2_benchmark.input_acquisition import _save_json
    code = 0
    try:
        receipt["result"] = execute(args.stage, profile, args.protocol_sha256)
        receipt["status"] = "succeeded"
    except BaseException as exc:
        code = 1
        receipt.update(status="failed_or_refused", error=f"{type(exc).__name__}: {exc}")
        for field in ("receipt", "partial_receipt", "bank_progress", "scan_progress", "cleanup_errors",
                      "native_closure_unverified"):
            if hasattr(exc, field):
                receipt[field] = getattr(exc, field)
    finally:
        receipt["wall_seconds"] = time.monotonic()-started
        try:
            _save_json(receipt_path, receipt)
            print(json.dumps({"stage": args.stage, "status": receipt["status"],
                              "wall_seconds": receipt["wall_seconds"], "receipt": str(receipt_path)}),
                  flush=True)
        finally:
            if receipt.get("native_closure_unverified"):
                # A native Dataset may still refer to its Python file object.
                # Do not trigger arbitrary destructor ordering on Python exit.
                try:
                    try:
                        descriptor = os.open(receipt_path, os.O_RDWR | os.O_NOFOLLOW)
                        try:
                            os.fsync(descriptor)
                        finally:
                            os.close(descriptor)
                    except BaseException as exc:
                        print(json.dumps({"receipt_sync_unverified": type(exc).__name__}),
                              file=sys.stderr, flush=True)
                    sys.stdout.flush()
                    sys.stderr.flush()
                finally:
                    os._exit(1)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
