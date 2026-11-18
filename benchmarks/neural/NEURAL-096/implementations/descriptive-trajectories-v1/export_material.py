"""Export separate observation arms and traverse them without solving the task.

This operator-only wrapper uses the frozen attempt API. It never imports a
grader, provider, scientific runtime or renderer. Input metadata commitments
are joined before outputs are created. All payloads remain byte-identical
except the adapter's existing index sanitization. The three-byte engineering
answer is deliberately unscored and establishes no scientific performance.

Read charges cover application file reads routed through this module and the
authenticated adapter's read_body, not Python/stdlib loading or filesystem
metadata syscalls. Each read reserves its requested maximum plus one before
I/O; returned bytes are counted separately. Failures retain partial output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import types


SCHEMA = "neural096-material-export-protocol/v1"
METHOD = "neural096-split-stratified-quarter-rate-contrasts/v1"
ATTEMPT_PIN = {"bytes": 35400, "sha256": "1978aee81cd1335e65a28b055c9dc57b43e5bfd84d5314cb4afcac97984b3085"}
IDS = tuple(f"{split}-segment{segment}-eye{eye}-direction{direction}"
            for split in ("train", "val") for segment in range(6)
            for eye in range(2) for direction in (0, 180))
MAX_META = 65536
MAX_PNG = 7 * 1024**2
MAX_OBSERVATIONS = 4 * 1024**2
MAX_OUTPUT = 8 * 1024**2
MAX_READ = 64 * 1024**2
MAX_CAPTURE = 4096
MAX_RECEIPT = 65536
ANSWER = b"{}\n"
BINDING_KEYS = {"index_sha256", "observation_manifest_sha256", "observation_sha256",
                "preparation_completion_sha256", "renderer_manifest_sha256"}


class ExportError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise ExportError(reason)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf8")


def decoded(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    def real(value):
        number = float(value)
        require(math.isfinite(number), "nonfinite_json")
        return number
    def constant(_):
        raise ExportError("nonfinite_json")
    try:
        return json.loads(body, object_pairs_hook=pairs, parse_float=real, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ExportError):
            raise
        raise ExportError("invalid_json") from None


def digest(value):
    require(type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value), "invalid_sha256")
    return value


def exact(left, right):
    require(type(left) is type(right), "metadata_type")
    if type(right) is dict:
        require(set(left) == set(right), "metadata_fields")
        for key in right:
            exact(left[key], right[key])
    elif type(right) is list:
        require(len(left) == len(right), "metadata_extent")
        for a, b in zip(left, right):
            exact(a, b)
    else:
        require(left == right, "metadata_value")


def commitment(value, maximum, *, file=False):
    keys = {"bytes", "sha256"} | ({"path"} if file else set())
    require(type(value) is dict and set(value) == keys and type(value["bytes"]) is int
            and 0 < value["bytes"] <= maximum, "bounded_commitment")
    digest(value["sha256"])
    if file:
        ordinary_path(value["path"])
    return {key: value[key] for key in ("bytes", "sha256")}


def ordinary_path(value):
    require(type(value) in (str, Path) or isinstance(value, Path), "operator_path_type")
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "absolute_ordinary_path_required")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink_path_refused")
    return path


class Budget:
    def __init__(self):
        self.read_limit = MAX_READ
        self.output_limit = MAX_OUTPUT
        self.charged_read_bytes = 0
        self.returned_read_bytes = 0
        self.read_calls = 0
        self.failed_reads = 0
        self.written_bytes = 0

    def reserve_read(self, maximum):
        require(type(maximum) is int and maximum >= 0, "read_bound")
        require(self.charged_read_bytes + maximum + 1 <= self.read_limit, "application_read_budget")
        self.charged_read_bytes += maximum + 1
        self.read_calls += 1

    def reserve_write(self, size):
        require(self.written_bytes + size <= self.output_limit, "output_budget")
        self.written_bytes += size

    def snapshot(self):
        return {"conservative_charged_read_bytes": self.charged_read_bytes,
                "returned_application_bytes": self.returned_read_bytes,
                "read_calls": self.read_calls, "failed_reads": self.failed_reads,
                "application_read_limit_bytes": self.read_limit,
                "written_bytes": self.written_bytes, "output_limit_bytes": self.output_limit}


def read_body(path, maximum, budget):
    path = ordinary_path(path)
    budget.reserve_read(maximum)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as handle:
            before = os.fstat(handle.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                    and 0 < before.st_size <= maximum, "ordinary_bounded_input")
            body = handle.read(maximum + 1)
            identity = lambda v: (v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_ctime_ns)
            require(len(body) == before.st_size and identity(before) == identity(os.fstat(handle.fileno()))
                    == identity(path.stat()), "input_changed_during_read")
        budget.returned_read_bytes += len(body)
        return body
    except Exception:
        budget.failed_reads += 1
        raise


def read_pinned(item, maximum, budget):
    expected = commitment(item, maximum, file=True)
    body = read_body(item["path"], expected["bytes"], budget)
    exact(pin(body), expected)
    return body


def load_attempt(path, expected_pin, budget):
    """Compile authenticated bytes; do not import a name or reopen a .pyc."""
    exact(expected_pin, ATTEMPT_PIN)
    body = read_pinned({"path": str(path), **expected_pin}, ATTEMPT_PIN["bytes"], budget)
    module = types.ModuleType("neural096_authenticated_attempt")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    original_read = module.read_body
    def measured_read(filename, maximum, *, empty=False):
        budget.reserve_read(maximum)
        try:
            result = original_read(filename, maximum, empty=empty)
            budget.returned_read_bytes += len(result)
            return result
        except Exception:
            budget.failed_reads += 1
            raise
    module.read_body = measured_read
    return module


def allowed_files():
    result = {"material/native/INDEX.json", "material/native/MATERIAL.json",
              "material/programme/INDEX.json", "material/programme/MATERIAL.json",
              "material/programme/observations.json"}
    result.update("material/native/cells/" + key + ".png" for key in IDS)
    for arm, count in (("native", 49), ("programme", 2)):
        prefix = "engineering/" + arm + "/"
        result.update(prefix + name for name in ("ATTEMPT.json", "LOCK", "ANSWER.bin", "FINAL.json"))
        result.update(prefix + f"events/{i:06d}.json" for i in range(1, count + 1))
    result.update("operator/" + name for name in
                  ("INSTRUCTION.md", "ANSWER_CONTRACT.json", "PROTOCOL.json", "CAPTURE_COMMITS.json", "EXPORT_RECEIPT.json"))
    require(len(result) == 117, "fixed_layout_programming_error")
    return result


def verify_closed_output(root, expected_files, budget=None):
    """Check the fixed 117-file inventory and saved byte commitments."""
    root = ordinary_path(root)
    root_info = root.lstat()
    require(stat.S_ISDIR(root_info.st_mode) and stat.S_IMODE(root_info.st_mode) == 0o700,
            "private_output_root_mode")
    require(type(expected_files) is dict and set(expected_files) == allowed_files(), "exact_output_roster")
    if budget is None:
        budget = Budget()
    directories = {""}
    for name in expected_files:
        directories.update(str(p) for p in Path(name).parents if str(p) != ".")
    found = set()
    def scan(folder, relative):
        for child in folder.iterdir():
            name = str(child.relative_to(root))
            info = child.lstat()
            require(not stat.S_ISLNK(info.st_mode), "output_link_refused")
            if stat.S_ISDIR(info.st_mode):
                require(name in directories and stat.S_IMODE(info.st_mode) == 0o700, "extra_or_nonprivate_output_directory")
                scan(child, name)
            else:
                require(name in expected_files and name not in found
                        and stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                        and stat.S_IMODE(info.st_mode) == 0o600, "extra_special_or_nonprivate_output")
                expected = expected_files[name]
                require(type(expected) is dict and set(expected) == {"bytes", "sha256"}
                        and type(expected["bytes"]) is int and expected["bytes"] >= 0, "output_commitment")
                digest(expected["sha256"])
                if expected["bytes"] == 0:
                    require(name.endswith("/LOCK") and info.st_size == 0
                            and expected["sha256"] == pin(b"")["sha256"], "empty_output")
                else:
                    body = read_body(child, expected["bytes"], budget)
                    exact(pin(body), expected)
                found.add(name)
    scan(root, "")
    require(found == set(expected_files), "missing_output")
    return {"files": len(found), "bytes": sum(item["bytes"] for item in expected_files.values())}


def _join_provenance(protocol, provenance, core):
    post, raster, observation = (provenance[k] for k in ("raster_postflight", "raster_manifest", "observation_manifest"))
    require(type(post) is dict and post.get("schema") == "neural096-full48-independent-custody-postflight/v1"
            and post.get("status") == "accepted_saved_full48_raster_custody", "accepted_raster_postflight_required")
    exact({key: post.get(key) for key in ("images", "supported_cells", "unsupported_cells")},
          {"images": 48, "supported_cells": 27, "unsupported_cells": 21})
    binding = protocol["input"]["source_binding"]
    exact(post.get("native_materialization_source_binding"), binding)
    index = commitment(protocol["input"]["index"], MAX_META, file=True)
    aggregate = commitment(protocol["input"]["observations"], MAX_OBSERVATIONS, file=True)
    raster_pin = commitment(protocol["provenance"]["raster_manifest"], MAX_META, file=True)
    observation_pin = commitment(protocol["provenance"]["observation_manifest"], MAX_META, file=True)
    exact({key: binding[key] for key in ("index_sha256", "observation_sha256", "renderer_manifest_sha256", "observation_manifest_sha256")},
          {"index_sha256": index["sha256"], "observation_sha256": aggregate["sha256"],
           "renderer_manifest_sha256": raster_pin["sha256"], "observation_manifest_sha256": observation_pin["sha256"]})
    require(type(observation) is dict and observation.get("schema") == "neural096-observation-delivery-manifest/v1"
            and observation.get("method") == METHOD, "observation_manifest_required")
    source = observation.get("source_binding")
    require(type(source) is dict and set(source) == {"observation", "preparation_completion_sha256", "preparation_receipt"}, "preparation_binding_fields")
    exact(source["observation"], aggregate)
    exact(source["preparation_completion_sha256"], binding["preparation_completion_sha256"])
    commitment(source["preparation_receipt"], 128 * 1024)
    require(type(observation.get("files")) is dict, "observation_file_map")
    exact(observation["files"].get("viewer/INDEX.json"), index)
    exact(observation["files"].get("programme/observations.json"), aggregate)
    require(type(raster) is dict and raster.get("schema") == "neural096-observation-raster-bundle/v1", "raster_manifest_required")
    exact(raster.get("source_observation_manifest"), observation_pin)
    exact(raster.get("source_index"), index)
    exact(raster.get("inherited_preparation_binding"), source)
    wanted = {"INDEX.json": index, **{"cells/" + key + ".png": commitment(protocol["input"]["pngs"][key], MAX_PNG, file=True) for key in IDS}}
    exact(raster.get("files"), wanted)
    inventory = post.get("output_inventory")
    require(type(inventory) is dict, "postflight_inventory")
    exact(inventory.get("bundle/MANIFEST.json"), raster_pin)
    for name, value in wanted.items():
        exact(inventory.get("bundle/" + name), value)


def preflight(protocol_path, protocol_sha256):
    """Authenticate all inputs before creating any output file or directory."""
    digest(protocol_sha256)
    budget = Budget()
    protocol_path = ordinary_path(protocol_path)
    protocol_body = read_body(protocol_path, MAX_META, budget)
    require(pin(protocol_body)["sha256"] == protocol_sha256, "protocol_identity")
    protocol = decoded(protocol_body)
    require(type(protocol) is dict and set(protocol) == {"schema", "attempt_source", "input", "documents", "provenance", "output_root", "limits", "condition"}, "protocol_fields")
    exact(protocol["schema"], SCHEMA)
    exact(protocol["condition"], {"method": METHOD, "engineering_only": True, "cells": 48, "supported": 27, "unsupported": 21})
    limits = protocol["limits"]
    require(type(limits) is dict and set(limits) == {"output_bytes", "application_read_bytes"}, "limit_fields")
    for key, upper in (("output_bytes", MAX_OUTPUT), ("application_read_bytes", MAX_READ)):
        require(type(limits[key]) is int and 0 < limits[key] <= upper, "limit_cap")
    budget.output_limit, budget.read_limit = limits["output_bytes"], limits["application_read_bytes"]
    require(budget.charged_read_bytes <= budget.read_limit, "application_read_budget")
    source_pin = commitment(protocol["attempt_source"], ATTEMPT_PIN["bytes"], file=True)
    exact(source_pin, ATTEMPT_PIN)
    core = load_attempt(protocol["attempt_source"]["path"], source_pin, budget)
    exact(list(core.IDS), list(IDS))
    require(type(protocol["input"]) is dict and set(protocol["input"]) == {"index", "observations", "pngs", "source_binding"}, "input_fields")
    inputs = protocol["input"]
    require(type(inputs["pngs"]) is dict and set(inputs["pngs"]) == set(IDS), "complete_png_roster")
    require(type(inputs["source_binding"]) is dict and set(inputs["source_binding"]) == BINDING_KEYS, "source_binding_fields")
    for value in inputs["source_binding"].values():
        digest(value)
    require(type(protocol["documents"]) is dict and set(protocol["documents"]) == {"instruction", "answer_contract"}, "document_fields")
    require(type(protocol["provenance"]) is dict and set(protocol["provenance"]) == {"raster_postflight", "raster_manifest", "observation_manifest"}, "provenance_fields")
    provenance = {key: decoded(read_pinned(item, MAX_META, budget)) for key, item in protocol["provenance"].items()}
    _join_provenance(protocol, provenance, core)
    documents = {key: read_pinned(item, MAX_META, budget) for key, item in protocol["documents"].items()}
    documents["instruction"].decode("utf8")
    require(type(decoded(documents["answer_contract"])) is dict, "answer_contract_object")
    index = read_pinned(inputs["index"], MAX_META, budget)
    sanitized = core.sanitize_index(index)
    observations = read_pinned(inputs["observations"], MAX_OBSERVATIONS, budget)
    core._observations(observations, core.decode(sanitized))
    for key in IDS:
        core.validate_png(read_pinned(inputs["pngs"][key], MAX_PNG, budget))
    root = ordinary_path(protocol["output_root"])
    require(not os.path.lexists(root) and root.parent.is_dir(), "fresh_export_root_required")
    require(not any((p / ".git").exists() for p in (root.parent, *root.parents)), "export_inside_git")
    input_paths = [protocol_path, Path(protocol["attempt_source"]["path"])]
    input_paths += [Path(item["path"]) for item in list(protocol["provenance"].values()) + list(protocol["documents"].values())]
    input_paths += [Path(inputs["index"]["path"]), Path(inputs["observations"]["path"])]
    input_paths += [Path(item["path"]) for item in inputs["pngs"].values()]
    require(all(not root.is_relative_to(path.parent) and not path.parent.is_relative_to(root) for path in input_paths), "output_overlaps_input_directory")
    png_bytes = sum(inputs["pngs"][key]["bytes"] for key in IDS)
    # Full file-byte ceiling: 53 materials, 59 captures and 5 operator records.
    output_upper = (png_bytes + len(observations) + 2*len(sanitized) + 6*MAX_META
                    + 51*core.MAX_EVENT + 2*len(ANSWER) + sum(map(len, documents.values()))
                    + len(protocol_body) + MAX_CAPTURE + MAX_RECEIPT)
    require(output_upper <= budget.output_limit, "prospective_output_budget")
    return {"protocol": protocol, "protocol_body": protocol_body, "protocol_pin": pin(protocol_body),
            "core": core, "budget": budget, "root": root, "documents": documents,
            "index": index, "sanitized_index": sanitized, "observations": observations,
            "png_bytes": png_bytes, "output_upper_bytes": output_upper, "files": {}}


def write_output(context, relative, body, writer=None):
    require(relative in allowed_files() and relative not in context["files"]
            and type(body) is bytes, "undeclared_or_duplicate_output")
    path = ordinary_path(context["root"] / relative)
    context["budget"].reserve_write(len(body))
    if writer is None:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    else:
        writer(path, body)
    context["files"][relative] = pin(body)


def materialize_native(context):
    protocol = context["protocol"]
    return context["core"].materialize_native(context["index"], protocol["input"]["pngs"],
             protocol["input"]["source_binding"], context["root"] / "material/native")


def run_export(protocol_path, protocol_sha256):
    context = preflight(protocol_path, protocol_sha256)
    root, core, protocol, budget = (context[key] for key in ("root", "core", "protocol", "budget"))
    root.mkdir(mode=0o700)
    for relative in ("material", "engineering", "operator"):
        (root / relative).mkdir(mode=0o700)
    original_core_write = core.write_new
    def core_write(path, body):
        path = ordinary_path(path)
        require(path.is_relative_to(root), "core_output_outside_export")
        write_output(context, str(path.relative_to(root)), body, writer=original_core_write)
    core.write_new = core_write
    write_output(context, "operator/INSTRUCTION.md", context["documents"]["instruction"])
    write_output(context, "operator/ANSWER_CONTRACT.json", context["documents"]["answer_contract"])
    write_output(context, "operator/PROTOCOL.json", context["protocol_body"])
    native = materialize_native(context)
    programme_binding = {k: v for k, v in protocol["input"]["source_binding"].items() if k != "renderer_manifest_sha256"}
    programme = core.materialize_programme(context["index"], context["observations"], programme_binding, root / "material/programme")
    shared = {"instruction_sha256": pin(context["documents"]["instruction"])["sha256"],
              "answer_contract_sha256": pin(context["documents"]["answer_contract"])["sha256"]}
    materials = {"native": native, "programme": programme}
    attempts, captures, traversal = {}, {}, {}
    for arm, count in (("native", 49), ("programme", 2)):
        payload_bytes = len(context["sanitized_index"]) + (context["png_bytes"] if arm == "native" else len(context["observations"]))
        config = {"attempt_id": "neural096_" + arm + "_delivery_engineering_v1", "max_requests": count,
                  "max_response_bytes": payload_bytes + count*core.RESPONSE_HEADER_RESERVE,
                  "max_final_answer_bytes": len(ANSWER), **shared}
        material_root, attempt_root = root / "material" / arm, root / "engineering" / arm
        made = core.create_attempt(material_root, materials[arm]["material_manifest"]["sha256"], config, attempt_root)
        attempts[arm] = made
        requests = [{"kind": "index"}] + ([{"kind": "view", "cell_id": key} for key in IDS] if arm == "native" else [{"kind": "observations"}])
        returned = 0
        for selected in requests:
            result = core.request_observation(material_root, attempt_root, made["attempt_manifest"]["sha256"], selected)
            name = "INDEX.json" if selected["kind"] == "index" else "observations.json" if selected["kind"] == "observations" else "cells/" + selected["cell_id"] + ".png"
            exact(pin(result["body"]), context["files"]["material/" + arm + "/" + name])
            exact(result["content_type"], "image/png" if selected["kind"] == "view" else "application/json")
            returned += len(result["body"])
        require(returned == payload_bytes, "traversal_byte_count")
        captured = core.submit_final(attempt_root, made["attempt_manifest"]["sha256"], ANSWER)
        captures[arm] = {"attempt_manifest": made["attempt_manifest"], "final_receipt": captured["receipt_pin"],
                         "answer": pin(ANSWER), "requests": count, "returned_bytes": returned}
        traversal[arm] = {"requests": count, "returned_bytes": returned, "charged_response_bytes": payload_bytes + count*core.RESPONSE_HEADER_RESERVE}
    # Persist capture-returned pins outside attempt trees BEFORE readback. Do
    # not derive the independent anchors from the current FINAL.json files.
    commits = {"schema": "neural096-engineering-capture-commits/v1", "protocol": context["protocol_pin"],
               "instruction_commitments": shared, "captures": captures, "engineering_answer_unscored": True}
    commit_body = encoded(commits)
    require(len(commit_body) <= MAX_CAPTURE, "capture_record_bound")
    write_output(context, "operator/CAPTURE_COMMITS.json", commit_body)
    for arm in ("native", "programme"):
        final = core.get_final(root / "engineering" / arm, attempts[arm]["attempt_manifest"]["sha256"], captures[arm]["final_receipt"]["sha256"])
        exact(final["receipt_pin"], captures[arm]["final_receipt"])
        exact(final["answer_bytes"], ANSWER)
        exact(final["log"]["events"], captures[arm]["requests"])
        exact(final["log"]["payload_bytes"], captures[arm]["returned_bytes"])
        for key, value in shared.items():
            exact(final["manifest"][key], value)
            exact(final["receipt"][key], value)
    receipt = {"schema": "neural096-separate-arm-engineering-export/v1", "status": "exported_engineering_only",
               "protocol": context["protocol_pin"], "attempt_source": ATTEMPT_PIN,
               "source_binding": protocol["input"]["source_binding"], "instruction_commitments": shared,
               "traversal": traversal, "capture_commits": pin(commit_body), "engineering_answer": pin(ANSWER),
               "files_excluding_this_receipt": dict(context["files"]),
               "read_accounting_before_final_inventory": budget.snapshot(),
               "prospective_output_upper_bytes": context["output_upper_bytes"],
               "qualification": {"full_task_completed": False, "scientific_performance_established": False,
                    "learned_neural_understanding_established": False, "provider_transport_qualified": False,
                    "OS_isolation_qualified": False, "PNG_pixel_semantics_requalified": False,
                    "engineering_answer_graded": False, "scoring_tolerance_changed": False}}
    receipt_body = encoded(receipt)
    require(len(receipt_body) <= MAX_RECEIPT, "export_receipt_bound")
    write_output(context, "operator/EXPORT_RECEIPT.json", receipt_body)
    verified = verify_closed_output(root, context["files"], budget)
    require(verified["files"] == 117 and verified["bytes"] == budget.written_bytes, "output_accounting")
    return {"status": "exported_engineering_only", "files": verified["files"], "bytes": verified["bytes"],
            "receipt": pin(receipt_body), "capture_commits": pin(commit_body),
            "read_accounting": budget.snapshot(), "expected_files": dict(context["files"])}


def main():
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode):
        print(json.dumps({"status": "failed", "reason": "isolated_no_site_no_bytecode_startup_required",
                          "automatic_retry": False}, sort_keys=True))
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    args = parser.parse_args()
    try:
        result = run_export(args.protocol, args.protocol_sha256)
        print(json.dumps({k: v for k, v in result.items() if k != "expected_files"}, sort_keys=True))
        return 0
    except Exception as exc:
        # No body, image, numeric aggregate, traceback or arbitrary exception
        # string is printed. Partial files stay in place; there is no retry.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "reason": str(exc) if isinstance(exc, ExportError) else "operator_export_failure",
                          "partial_outputs_retained": True, "automatic_retry": False}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
