"""Fixed 1 Hz engineering control; reads public metadata, never signal arrays.

This is a nonlearning transport control, not a fitted source-model reference or
a paper reproduction/improvement result. The original collector independently
checks the emitted binding, complete geometry and numerical artifact.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct

CONDITION = "current_source_noise7_eligible_v1"
POLICY = "eligible_same_cohort_except_entire_held_neuron"
MAX_METADATA = 100_000
MAX_CAPTURE = 1_000_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def strict_pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def read_metadata(path):
    # Only three public metadata files are opened by this program. No directory
    # scan, array decoder, training loader or target lookup is used.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= MAX_METADATA, "bounded regular metadata")
        body = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    require(len(body) == before.st_size and all(
        getattr(before, key) == getattr(after, key) for key in fields), "stable metadata")
    value = json.loads(body, object_pairs_hook=strict_pairs,
                       parse_constant=lambda _: require(False, "finite JSON"))
    require(isinstance(value, dict), "metadata object")
    return value, body


def checked_metadata(folder, config_path, binding_path):
    config, unused = read_metadata(config_path)
    binding, binding_body = read_metadata(binding_path)
    fold, fold_body = read_metadata(Path(folder) / "FOLD.json")
    require(binding_body == encoded(binding), "canonical original binding")
    require(binding.get("schema") == "spinal_current_program_binding_v1"
            and binding.get("condition_id") == CONDITION
            and binding.get("training_policy") == POLICY
            and binding.get("fresh_context_required") is True, "original binding condition")
    require(binding.get("arm") in ("paper_data", "paper_data_author_code")
            and binding.get("purpose") in ("reproduction", "improvement"), "arm and purpose")
    require(binding.get("output_unit") == "hz", "fixed control emits exactly 1 Hz")
    require(config == {"schema": "spinal_current_program_config_v1", "condition_id": CONDITION,
            "arm": binding["arm"], "purpose": binding["purpose"], "output_unit": "hz",
            "training_policy": POLICY}, "exact original configuration")
    require(binding.get("fold_manifest") == pin(fold_body)
            and binding.get("input_files", {}).get("FOLD.json") == pin(fold_body),
            "public fold bytes match binding")
    require(fold.get("schema") == "spinal_current_fold_materials_v1"
            and fold.get("condition_id") == CONDITION
            and fold.get("nominal_rate_hz") == 30
            and fold.get("target_sigma_seconds") == .05
            and fold.get("context_margin_bins") == 32, "original fold constants")
    for name in ("held_neuron", "arm", "purpose", "query_records"):
        require(fold.get(name) == binding.get(name), "fold/binding identity")
    require(isinstance(binding["held_neuron"], str) and 0 < len(binding["held_neuron"]) <= 200,
            "held-neuron identity")
    seal = binding.get("program_seal", {}).get("sha256")
    require(isinstance(seal, str) and len(seal) == 64
            and all(c in "0123456789abcdef" for c in seal), "program seal SHA256")
    records = binding["query_records"]
    require(isinstance(records, list) and 0 < len(records) <= 132, "query record roster")
    total = 0
    seen = set()
    for row in records:
        require(isinstance(row, dict) and set(row) == {"recording_id", "neuron_id", "offset", "samples"},
                "original query row shape")
        identity = row["recording_id"]
        require(isinstance(identity, str) and 0 < len(identity) <= 200 and identity not in seen
                and row["neuron_id"] == binding["held_neuron"], "unique held-neuron recordings")
        require(type(row["offset"]) is int and row["offset"] == total
                and type(row["samples"]) is int and row["samples"] > 64,
                "complete contiguous original recording lengths")
        total += row["samples"]
        require(8 * total + 1036 <= MAX_CAPTURE, "complete fold fits original capture")
        seen.add(identity)
    return binding, binding_body, total


def constant_npy(count):
    # Ordinary NumPy v1.0 little-endian float64, written using the standard
    # library so the control does not depend on a model/numerical package.
    header = repr({"descr": "<f8", "fortran_order": False, "shape": (count,)}).encode("ascii")
    padding = (-((10 + len(header) + 1) % 64)) % 64
    header += b" " * padding + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + struct.pack("<d", 1.0) * count


def write_new(path, body):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fchmod(stream.fileno(), 0o644)
        os.fsync(stream.fileno())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "config", "binding", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    binding, binding_body, total = checked_metadata(args.input, args.config, args.binding)
    output = Path(args.output)
    require(output.is_dir() and not output.is_symlink() and not any(output.iterdir()),
            "fresh existing output volume")
    fold = {"schema": "spinal_current_fold_prediction_v1", "condition_id": CONDITION,
            "held_neuron": binding["held_neuron"], "arm": binding["arm"], "purpose": binding["purpose"],
            "program_seal_sha256": binding["program_seal"]["sha256"],
            "binding_sha256": hashlib.sha256(binding_body).hexdigest(), "unit": "hz",
            "query_recording_ids": [row["recording_id"] for row in binding["query_records"]]}
    write_new(output / "predictions.npy", constant_npy(total))
    write_new(output / "fold.json", encoded(fold))


if __name__ == "__main__":
    main()
