"""Portable preparation of the fixed public cfa24/M1 stored-angle session.

The caller verifies the public dependency sources before supplying their loaded
modules. One authenticated original handle supplies fresh metadata and then the
unchanged projection/pair/reference/collector/export route. Outputs are private
caller-selected artifacts. No download, fit, score, split, or native lease is
performed here. A completed RESULT is required; array presence is insufficient.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time


SESSION = "cfa24_20220727_160603"
FILENAME = "R,cfa24_20220727_160603,thresholded,DLC3.mat"
AUTHOR_COMMIT = "815b610b3beddfed5a3abf611d3a465ab9e4ce5c"
ORIGINAL_BYTES = 980063226
ORIGINAL_SHA256 = "f97834b22135ca1509be34913e29300dd4ebbcc52436173fb1cb63c9afdf29d0"
ORIGINAL_MD5 = "5c89cea4cae04adf8c21f46b740d2c4b"
METADATA_BYTES = 834680
METADATA_SHA256 = "f8ad6940b5a7a6e092e69d5740283c6e03d4c8b04261968a15f7dd7e96ea18e8"
CONTRACT_BYTES = 86577
CONTRACT_SHA256 = "5c6573e611abbbd491065b4ee74c83d2d2d86d357575795360e0ecdeee44dacd"
VARIANT = "smoothed_deconvolved_events"
DEPENDENCIES = {"admission", "metadata", "projection", "collector", "pairing",
                "reference", "export", "source_condition"}
METADATA_LIMITS = {"max_decoded_elements": 1000000, "max_trials": 2000,
                   "max_shape_nodes": 20000, "max_clock_points_per_trial": 20000,
                   "max_report_bytes": 4194304}
PROJECTION_LIMITS = {"max_numeric_elements": 54368292, "max_reader_elements": 55297550,
                     "max_trial_numeric_elements": 866917, "max_trials": 416,
                     "max_eligible_trials": 372, "max_decoded_chunk_bytes": 8388608}
RESOURCE_CONFIG = {"logical_read_cap_bytes": 2147483648,
                   "single_callback_read_cap_bytes": 8388608,
                   "array_output_cap_bytes": 94371840,
                   "json_output_cap_bytes": 4194304, "work_seconds": 750}
JOINT_LABELS = ("SHDRf", "SHDRa", "SHDRr", "ELBOf", "WRSTf", "WRSTd", "WRSTr",
                "MCP1f", "MCP2f", "MCP3f", "MCP4f", "MCP1a", "MCP2a", "MCP3a",
                "MCP4a", "MCP1o", "MCP4o", "P1P2", "P2P3", "P3P4",
                "PIP1f", "PIP2f", "PIP3f", "PIP4f")


class PreparationRefusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise PreparationRefusal(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def ordinary(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts and
            all(not item.is_symlink() for item in (path, *path.parents)),
            "Ordinary absolute path without parent traversal required")
    return path


def validate_input_path(input_path):
    """Metadata-only admission before any full-file reader or numeric work."""
    source = ordinary(input_path)
    require(source.name == FILENAME, "Fixed original public filename required")
    info = source.stat(follow_symlinks=False)
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
            info.st_size == ORIGINAL_BYTES,
            "Original must be an exact-sized ordinary single-link file")
    return source.resolve(strict=True)


def input_manifest():
    """The original path-independent public manifest; no acquisition receipt."""
    return {"schema": "calcium_single_session_metadata_manifest_v1",
            "author_commit": AUTHOR_COMMIT,
            "source": {"session_id": SESSION, "figshare_file_id": 60332984,
                       "path": FILENAME, "bytes": ORIGINAL_BYTES, "sha256": ORIGINAL_SHA256},
            "limits": dict(METADATA_LIMITS)}


def metadata_binding(manifest):
    return {"published_asset_verified": True, "session_id": SESSION,
            "filename": FILENAME, "figshare_file_id": 60332984,
            "bytes": ORIGINAL_BYTES, "published_md5": ORIGINAL_MD5,
            "sha256": ORIGINAL_SHA256,
            "manifest_sha256": hashlib.sha256(canonical(manifest)).hexdigest(),
            "whole_file_bytes_hashed": ORIGINAL_BYTES,
            "scope": "file_checksums_and_metadata_only_not_scientific_identity"}


def session_contract(metadata):
    """Preserve source ordinals, all exclusions, source-local columns and clock."""
    rows = []
    for row in metadata["trials"]:
        eligible = row["eligibility"]["eligible_by_loadLock4Decode"]
        rows.append({"ordinal": row["raw_ordinal_one_based"],
                     "trial_number": row["original_trial_number"], "eligible": eligible,
                     "exclusion_reasons": row["eligibility"]["exclusion_reasons"],
                     "frame_rows": row["events"]["matlab_shape"][0] if eligible else None,
                     "camera_rows": row["jointAngles"]["matlab_shape"][0] if eligible else None,
                     "LR": row["scalar_values"]["LR"]})
    return {"schema": "calcium-session-pair-contract-v1", "raw_trial_count": 416,
            "eligible_trial_count": 372, "author_excluded_trial_count": 44,
            "session_id": SESSION, "source_sha256": ORIGINAL_SHA256,
            "metadata_sha256": METADATA_SHA256, "roi_indices": list(range(1, 566)),
            "joint_labels": list(JOINT_LABELS),
            "shared_camera_step_ms": metadata["first_eligible_max_cams"]["cam_time_base_ms"],
            "first_camera_ordinal": metadata["first_eligible_max_cams"]["raw_ordinal_one_based"],
            "first_neural_ordinal": metadata["first_eligible_neural"]["raw_ordinal_one_based"],
            "cycle_ms": metadata["roi_metadata"]["cycle_duration_ms"], "trials": rows}


def unattempted_collection(contract):
    return {"schema": "calcium-session-unattempted-dispositions-v1", "completed": False,
            "session_id": SESSION,
            "dispositions": [dict(row, status="not_attempted_after_failure" if row["eligible"]
                                  else "author_excluded") for row in contract["trials"]],
            "counts": {"author_excluded": 44, "paired": 0, "failed": 0,
                       "not_attempted_after_failure": 372},
            "failure_stage": "before_first_eligible_trial"}


class BudgetFile:
    """Logical callback budget after the one fixed-size hash/header pass.

    This is the previous bounded file protocol without machine-specific paths.
    It meters returned/requested bytes, not physical storage or native caches.
    """
    def __init__(self, handle, accounting, deadline):
        self.handle, self.accounting, self.deadline = handle, accounting, deadline

    def check(self, size):
        require(time.monotonic() < self.deadline, "Preparation work deadline")
        require(type(size) is int and 0 <= size <= RESOURCE_CONFIG["single_callback_read_cap_bytes"],
                "Bounded explicit HDF5 callback required")
        require(self.accounting["logical_original_bytes_read"] + size <=
                RESOURCE_CONFIG["logical_read_cap_bytes"], "Combined original logical read cap")

    def read(self, size=-1):
        self.check(size)
        self.accounting["logical_original_bytes_read"] += size
        self.accounting["hdf5_read_calls"] += 1
        try:
            body = self.handle.read(size)
            require(type(body) is bytes and len(body) == size, "Short or invalid callback body")
        except BaseException:
            self.accounting["logical_original_bytes_read_exact"] = False
            self.accounting["failed_callback_request_upper_allowance_bytes"] += size
            raise
        return body

    def readinto(self, destination):
        size = memoryview(destination).nbytes
        self.check(size)
        self.accounting["logical_original_bytes_read"] += size
        self.accounting["hdf5_read_calls"] += 1
        try:
            count = self.handle.readinto(destination)
            require(type(count) is int and count == size, "Short or invalid callback count")
        except BaseException:
            self.accounting["logical_original_bytes_read_exact"] = False
            self.accounting["failed_callback_request_upper_allowance_bytes"] += size
            raise
        return count

    def seek(self, offset, whence=0):
        require(time.monotonic() < self.deadline and whence in (0, 1, 2), "Bounded seek deadline")
        return self.handle.seek(offset, whence)

    def tell(self): return self.handle.tell()
    def fileno(self): return self.handle.fileno()
    def close(self): return self.handle.close()
    def flush(self): return self.handle.flush()
    def readable(self): return True
    def writable(self): return False
    def seekable(self): return True
    @property
    def closed(self): return self.handle.closed


class JsonOutput:
    """Combined JSON attempted-write budget, including failed writes."""
    def __init__(self, directory):
        self.directory, self.attempted_bytes = directory, 0

    def write(self, name, body):
        require(name in {"INPUT_MANIFEST.json", "METADATA_SHAPES.json", "SESSION_CONTRACT.json", "RESULT.json"}
                and type(body) is bytes, "Fixed JSON output name/body required")
        require(self.attempted_bytes + len(body) <= RESOURCE_CONFIG["json_output_cap_bytes"],
                "Combined JSON output budget")
        self.attempted_bytes += len(body)
        path = ordinary(self.directory / name)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            view = memoryview(body)
            while view:
                count = os.write(fd, view[:1048576])
                require(count > 0, "Short JSON output write")
                view = view[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        return {"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def validate_projection_accounting(accounting, contract, metadata, admission):
    a = accounting
    eligible = [row["ordinal"] for row in contract["trials"] if row["eligible"]]
    excluded = [row["ordinal"] for row in contract["trials"] if not row["eligible"]]
    require(a["state"] == "complete" and a["session_id"] == SESSION and
            a["metadata_sha256"] == METADATA_SHA256 and
            a["complete_census_sha256"] == admission.digest(metadata["complete_scalar_census"]) and
            (a["total_original_trials"], a["eligible_original_trials"], a["excluded_original_trials"]) ==
            (416, 372, 44) and a["excluded_original_ordinals"] == excluded and
            a["attempted_eligible_ordinals"] == a["completed_eligible_ordinals"] == eligible and
            a["eligible_ordinals_not_attempted"] == [] and a["next_expected_ordinal"] is None and
            a["failure"] is None and a["shared_numeric_values_cached"] is True and
            a["numeric_read_accounting_exact"] is True and a["limits"] == PROJECTION_LIMITS and
            a["numeric_elements_reserved"] == a["numeric_elements_decoded_finite"] == 54368292 and
            a["decoded_numeric_bytes_or_failure_upper_allowance"] == 434946336 and
            a["posXYZ_values_read"] is False, "Complete original numeric/support accounting required")
    require(type(a["conservatively_charged_reader_elements"]) is int and
            55297548 <= a["conservatively_charged_reader_elements"] <= 55297550 and
            a["remaining_reader_elements"] == 55297550 - a["conservatively_charged_reader_elements"],
            "Exact observed reference accounting differs from the admitted finite range")


def prepare_session(dependencies, input_path, output_dir, *, resource_config, source_condition):
    """Prepare one fixed original session using caller-authenticated modules.

    Eight module keys are required. ``admission`` and ``source_condition`` come
    from existing sibling public implementations; the six mathematical/metadata
    modules are unchanged local copies. The loader verifies their source pins.
    A new empty output directory must already exist. Failures after admission
    retain RESULT plus any partial artifacts; no automatic retry or cleanup
    deletion occurs. The returned receipt equals the persisted RESULT body.
    """
    require(type(dependencies) is dict and set(dependencies) == DEPENDENCIES,
            "Exactly eight source-authenticated dependency modules required")
    require(type(resource_config) is dict and set(resource_config) == set(RESOURCE_CONFIG) and
            all(type(resource_config[key]) is int and resource_config[key] == value
                for key, value in RESOURCE_CONFIG.items()), "Fixed preparation resource limits required")
    a, meta = dependencies["admission"], dependencies["metadata"]
    project, collect, export = dependencies["projection"], dependencies["collector"], dependencies["export"]
    condition_body = canonical(source_condition)
    require(len(condition_body) <= 65536, "Bounded source-condition record required")
    condition = json.loads(condition_body)
    exposure_sha = dependencies["source_condition"].validate_source_condition(condition, VARIANT)
    source = validate_input_path(input_path)
    out = ordinary(output_dir)
    require(out.is_dir(), "Existing private output directory required")
    with os.scandir(out) as entries:
        require(next(entries, None) is None, "Fresh empty output directory required; no overwrite")
    manifest = input_manifest()
    started = time.monotonic()
    deadline = started + RESOURCE_CONFIG["work_seconds"]
    writer = JsonOutput(out)
    accounting = {"logical_original_bytes_read": 0, "hdf5_read_calls": 0,
                  "logical_original_bytes_read_exact": True,
                  "failed_callback_request_upper_allowance_bytes": 0,
                  "physical_storage_bytes_metered": False, "full_hash_and_header_completed": False,
                  "logical_read_cap_bytes": RESOURCE_CONFIG["logical_read_cap_bytes"],
                  "single_callback_cap_bytes": RESOURCE_CONFIG["single_callback_read_cap_bytes"]}
    receipt = {"schema": "calcium-portable-session-preparation-result-v1", "completed": False,
               "source_condition": condition, "upstream_exposure_sha256": exposure_sha,
               "feature_variant": VARIANT, "session_id": SESSION,
               "source_binding": {"bytes": ORIGINAL_BYTES, "sha256": ORIGINAL_SHA256,
                                  "published_md5": ORIGINAL_MD5, "figshare_file_id": 60332984},
               "resources": dict(RESOURCE_CONFIG), "output_files": {}, "collection": None,
               "runtime_observed": {"python": sys.version.split()[0], "numpy": a.np.__version__,
                                    "h5py": a.h5py.__version__, "hdf5": a.h5py.version.hdf5_version},
               "full_installed_library_binary_seal": False,
               "hard_os_memory_or_time_limit_enforced_here": False,
               "deadline_policy": "cooperative callbacks and operation boundaries; caller owns external stop",
               "source_condition_body_authenticated": True,
               "upstream_exposure_qualified": False, "scientific_qualification": False,
               "matlab_numerical_parity": False, "inverse_kinematics_executed": False,
               "full_native_eventLockKinematics_executed": False,
               "fit_or_score_produced": False, "whole_mouse_endpoint_complete": False,
               "current_task_endpoint_packet_complete": False}
    handle = sink = accessor = None
    hashing_attempted = False

    def check_deadline():
        require(time.monotonic() < deadline, "Preparation work deadline")

    def bounded_pair(*values):
        check_deadline()
        result = dependencies["pairing"].pair_trial(*values)
        check_deadline()
        return result

    def bounded_reference(*values):
        check_deadline()
        result = dependencies["reference"].reference_pair(*values)
        check_deadline()
        return result

    try:
        receipt["output_files"]["input_manifest"] = writer.write("INPUT_MANIFEST.json", canonical(manifest) + b"\n")
        check_deadline()
        hashing_attempted = True
        # The unchanged reader hashes one finite exact-sized file, with one EOF
        # probe and one520-byte header read. Reserve the whole failure allowance
        # before entry; only successful authentication makes returned bytes exact.
        accounting["logical_original_bytes_read"] = ORIGINAL_BYTES + 521
        accounting["logical_original_bytes_read_exact"] = False
        handle, before = a.opened_mat(source.parent, manifest["source"],
                                      {"max_file_bytes": ORIGINAL_BYTES}, published_md5=ORIGINAL_MD5)
        accounting.update(logical_original_bytes_read=ORIGINAL_BYTES + 520,
                          logical_original_bytes_read_exact=True, full_hash_and_header_completed=True)
        check_deadline()
        bounded = BudgetFile(handle, accounting, deadline)
        with a.h5py.File(bounded, "r", rdcc_nbytes=8388608) as hf:
            metadata = meta.inspect_structure(hf, a, dict(METADATA_LIMITS))
            metadata["source_binding"] = metadata_binding(manifest)
            metadata_bytes = canonical(metadata) + b"\n"
            require((len(metadata_bytes), hashlib.sha256(metadata_bytes).hexdigest()) ==
                    (METADATA_BYTES, METADATA_SHA256), "Fresh original metadata differs from the accepted exact session")
            receipt["output_files"]["metadata"] = writer.write("METADATA_SHAPES.json", metadata_bytes)
            del metadata_bytes
            check_deadline()
            contract = session_contract(metadata)
            contract_bytes = (json.dumps(contract, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
            require((len(contract_bytes), hashlib.sha256(contract_bytes).hexdigest()) ==
                    (CONTRACT_BYTES, CONTRACT_SHA256), "Metadata-derived original contract identity changed")
            collect.check_contract(contract)
            receipt["collection"] = unattempted_collection(contract)
            receipt["output_files"]["contract"] = writer.write("SESSION_CONTRACT.json", contract_bytes)
            del contract_bytes
            receipt["read_accounting_after_metadata"] = dict(accounting)
            arrays = out / "arrays"
            arrays.mkdir(mode=0o700)
            accessor = project.make_session_projection(hf, a, metadata, limits=dict(PROJECTION_LIMITS))
            require(accessor.trial_identities == tuple((row["ordinal"], row["trial_number"], row["eligible"])
                                                       for row in contract["trials"]),
                    "Accessor must preserve all original trial identities")
            sink = export.SessionSink(arrays, 372, 565, max_output_bytes=RESOURCE_CONFIG["array_output_cap_bytes"])
            receipt["collection"] = collect.collect_session(contract, accessor.read_trial,
                                                            bounded_pair, bounded_reference, sink)
            receipt["projection_accounting"] = dict(accessor.accounting)
        a.stable(handle, before)
        handle.close()
        handle = None
        check_deadline()
        require(receipt["collection"]["completed"] is True and receipt["collection"]["counts"] ==
                {"author_excluded": 44, "paired": 372, "failed": 0, "not_attempted_after_failure": 0},
                "All372 original eligible trials and44 original exclusions must be retained")
        validate_projection_accounting(receipt["projection_accounting"], contract, metadata, a)
        receipt["completed"] = True
    except BaseException as exc:
        receipt["error"] = {"kind": type(exc).__name__, "detail": str(exc)[:512]}
        if receipt["collection"] is not None:
            receipt["collection"]["completed"] = False
            receipt["collection"]["authoritative_session_packet"] = False
            if "exports" in receipt["collection"]:
                receipt["collection"]["exports"]["authoritative_session_packet"] = False
        if sink is not None:
            try:
                receipt["partial_exports"] = sink.abort()
            except BaseException as close_error:
                receipt["partial_export_close_error"] = {"kind": type(close_error).__name__, "detail": str(close_error)[:512]}
        elif (out / "arrays").exists():
            receipt["array_write_upper_allowance_if_sink_unavailable"] = RESOURCE_CONFIG["array_output_cap_bytes"]
    finally:
        if handle is not None:
            try:
                handle.close()
            except BaseException as exc:
                receipt["completed"] = False
                receipt["original_close_error"] = {"kind": type(exc).__name__, "detail": str(exc)[:512]}
        if accessor is not None:
            receipt["projection_accounting"] = dict(accessor.accounting)
        if sink is not None:
            receipt["array_output_attempted_bytes"] = sink.attempted_bytes
        if hashing_attempted and not accounting["full_hash_and_header_completed"]:
            accounting["failed_checksum_pass_upper_bound_bytes"] = ORIGINAL_BYTES + 521
        receipt["read_accounting"] = accounting
        receipt["elapsed_seconds"] = time.monotonic() - started
    # RESULT's own attempted bytes are included without a recursive self-hash.
    receipt["json_output_attempted_bytes_including_result"] = writer.attempted_bytes
    for unused in range(8):
        body = canonical(receipt) + b"\n"
        total = writer.attempted_bytes + len(body)
        if receipt["json_output_attempted_bytes_including_result"] == total:
            break
        receipt["json_output_attempted_bytes_including_result"] = total
    else:
        raise PreparationRefusal("Unable to stabilize bounded JSON accounting")
    writer.write("RESULT.json", body)
    return receipt
