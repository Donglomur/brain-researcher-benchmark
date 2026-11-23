"""Operator-only complete opaque NPZ export and target-last artifact grading.

No candidate code, process, model or authentic preparation runs on import.
This is a file boundary, not participant execution or host isolation.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
import time
import types
import uuid
import zlib

HERE = Path(__file__).resolve().parent
PUBLIC_CAP = 256 * 1024**2
PREDICTION_CAP = 32 * 1024**2
METADATA_CAP = 2 * 1024**2
EXPORT_SCHEMA = "neural017_opaque_file_export_v1"
SUPPORT = {"training_trials": 1721, "query_trials": 574, "bins": 140,
           "bin_ms": 5, "observed_units": 137, "withheld_units": 45}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def checked_pin(value, cap):
    need(type(value) is dict and set(value) == {"bytes", "sha256"}, "Exact byte pin")
    need(type(value["bytes"]) is int and 0 < value["bytes"] <= cap, "Pinned extent cap")
    need(type(value["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", value["sha256"]), "SHA256 pin")
    return value


def decode(body):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def bad(_):
        raise ValueError("Nonfinite JSON")
    result = json.loads(body, object_pairs_hook=pairs, parse_constant=bad)
    # Also rejects numeric overflow such as 1e999.
    encoded(result)
    return result


def literal(path):
    p = Path(path).absolute()
    need(".." not in p.parts and all(not q.is_symlink() for q in (p, *p.parents)), "Unlinked literal path")
    return p


def state(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_nlink, st.st_mtime_ns, st.st_ctime_ns)


def snapshot(path, expected, cap):
    """Capture exact bounded regular bytes before any decoder sees them."""
    checked_pin(expected, cap)
    p = literal(path)
    before = p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected["bytes"], "Exact ordinary file extent")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        need(state(before) == state(os.fstat(stream.fileno())), "Captured inode identity")
        body = stream.read(expected["bytes"] + 1)
        need(state(before) == state(os.fstat(stream.fileno())) == state(p.lstat()), "File changed during capture")
    need(pin(body) == expected, "Captured bytes differ from pin")
    return body


def small(path, cap):
    p = literal(path)
    size = p.lstat().st_size
    need(0 < size <= cap, "Small trusted source cap")
    before = p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "Ordinary trusted source")
    with p.open("rb") as stream:
        body = stream.read(size + 1)
        need(state(before) == state(os.fstat(stream.fileno())) == state(p.lstat()), "Trusted source changed")
    need(len(body) == size, "Trusted source extent")
    return body


def separate(*paths):
    values = [literal(p) for p in paths]
    for i, p in enumerate(values):
        for q in values[:i]:
            need(p != q and p not in q.parents and q not in p.parents, "Disjoint path roles")
    return values


def fresh(path):
    p = literal(path)
    need(p.parent.is_dir() and not p.exists(), "Fresh output directory with existing parent")
    p.mkdir(mode=0o700)
    return p


def write_new(path, body, cap):
    need(type(body) is bytes and len(body) <= cap, "Output byte cap")
    p = literal(path)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    p.chmod(0o400)
    return pin(body)


def runtime():
    import numpy as np
    return {"python": platform.python_version(), "numpy": np.__version__,
            "zlib_build": zlib.ZLIB_VERSION, "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
            "scope": "observed versions; not binary or hermetic environment qualification"}


def load_sources():
    """Compile the six pinned local dependencies from captured bytes."""
    raw = small(HERE / "SOURCE_BINDINGS.json", 16384)
    manifest = decode(raw)
    need(manifest["schema"] == "neural017_opaque_file_sources_v1", "Source manifest schema")
    bodies = {name: snapshot(HERE.parent / name, expected, 65536)
              for name, expected in manifest["files"].items()}
    prefix = "_neural017_opaque_file_" + uuid.uuid4().hex
    package = types.ModuleType(prefix)
    package.__path__ = []
    sys.modules[prefix] = package
    loaded = []
    def compile_source(role, name):
        module = types.ModuleType(prefix + "." + role)
        module.__file__ = str(HERE.parent / name)
        module.__package__ = prefix
        sys.modules[module.__name__] = module
        loaded.append(module.__name__)
        exec(compile(bodies[name], module.__file__, "exec"), module.__dict__)
        return module
    try:
        compile_source("contracts", "registered-runtime/complete-operator/nlb/contracts.py")
        arrays = compile_source("arrays", "registered-runtime/complete-operator/nlb/arrays.py")
        delivery = compile_source("delivery", "opaque-delivery-v1/delivery.py")
        grader = compile_source("grader", "registered-runtime/engine/investigation/grade.py")
        metrics = compile_source("metrics", "registered-runtime/complete-operator/nlb/metric_core.py")
        return types.SimpleNamespace(arrays=arrays, delivery=delivery, grader=grader, metrics=metrics,
            assets=decode(bodies["registered-runtime/assets.json"]),
            source_pin=pin(raw), implementation_pin=pin(small(HERE / "file_delivery.py", 65536)))
    finally:
        for name in loaded:
            del sys.modules[name]
        del sys.modules[prefix]


def asset_pin(asset):
    return {key: asset[key] for key in ("bytes", "sha256")}


def export_packet(source_path, key_path, public_directory, operator_directory, sources):
    """Trusted API. CLI always supplies the immutable original source selection."""
    source_path, key_path, public_directory, operator_directory, _ = separate(
        source_path, key_path, public_directory, operator_directory, HERE)
    need(public_directory.parent.is_dir() and operator_directory.parent.is_dir()
         and not public_directory.exists() and not operator_directory.exists(), "Fresh separate export roles")
    source_pin = asset_pin(sources.assets["public"]["packet"])
    raw = snapshot(source_path, source_pin, PUBLIC_CAP)
    secret = small(key_path, 32)
    need(len(secret) == 32, "Exactly 32 private key bytes")
    source = sources.arrays.load_arrays(raw, sources.delivery.PUBLIC_KEYS, cap=PUBLIC_CAP)
    del raw
    public, binding = sources.delivery.export_public(source, secret=secret,
        expected_source_fingerprint=sources.assets["panel_fingerprint"])
    # Every array is checked before output allocation; no smaller panel fallback.
    public_body = sources.arrays.dump_arrays(public, cap=PUBLIC_CAP)
    binding_body = encoded(binding)
    need(len(binding_body) <= METADATA_CAP, "Private mapping cap")
    operator_directory = fresh(operator_directory)
    public_directory = fresh(public_directory)
    # A receipt is published only after both complete outputs exist. Failures
    # leave their own partial directories; no overwrite or automatic cleanup.
    public_pin = write_new(public_directory / "public.npz", public_body, PUBLIC_CAP)
    binding_pin = write_new(operator_directory / "binding.json", binding_body, METADATA_CAP)
    receipt = {"schema": EXPORT_SCHEMA, "status": "complete", "source": source_pin,
        "source_panel_fingerprint": sources.assets["panel_fingerprint"],
        "public": public_pin, "public_panel_fingerprint": binding["public_panel_fingerprint"],
        "binding": binding_pin, "binding_content_sha256": sources.delivery.digest(binding),
        "source_dependencies": sources.source_pin, "implementation": sources.implementation_pin,
        "support": dict(SUPPORT),
        "condition_policy": "original permitted labels retained", "runtime": runtime(),
        "old_campaign_commitments_valid_for_this_export": False,
        "participant_execution_or_native_understanding_established": False}
    receipt_pin = write_new(operator_directory / "EXPORT.json", encoded(receipt), METADATA_CAP)
    return {"export_receipt": receipt_pin, "public": public_pin, "binding": binding_pin}


def admit_export(export_path, expected_export, binding_path, sources):
    receipt = decode(snapshot(export_path, expected_export, METADATA_CAP))
    need(set(receipt) == {"schema", "status", "source", "source_panel_fingerprint", "public",
         "public_panel_fingerprint", "binding", "binding_content_sha256", "source_dependencies",
         "implementation", "support", "condition_policy", "runtime",
         "old_campaign_commitments_valid_for_this_export", "participant_execution_or_native_understanding_established"},
         "Exact complete export receipt")
    need(receipt["schema"] == EXPORT_SCHEMA and receipt["status"] == "complete", "Completed opaque export")
    need(receipt["support"] == SUPPORT and receipt["condition_policy"] == "original permitted labels retained"
         and receipt["old_campaign_commitments_valid_for_this_export"] is False
         and receipt["participant_execution_or_native_understanding_established"] is False, "Original support and claim scope")
    checked_pin(receipt["public"], PUBLIC_CAP)
    need(receipt["source"] == asset_pin(sources.assets["public"]["packet"])
         and receipt["source_panel_fingerprint"] == sources.assets["panel_fingerprint"]
         and receipt["source_dependencies"] == sources.source_pin
         and receipt["implementation"] == sources.implementation_pin, "Exact export source selection")
    binding = decode(snapshot(binding_path, receipt["binding"], METADATA_CAP))
    need(sources.delivery.digest(binding) == receipt["binding_content_sha256"], "Independent mapping commitment")
    need(binding["core"]["source_panel_fingerprint"] == receipt["source_panel_fingerprint"]
         and binding["public_panel_fingerprint"] == receipt["public_panel_fingerprint"], "Original and delivered panel linkage")
    return receipt, binding


def collect_and_grade(export_path, expected_export, binding_path, submission_path,
                      expected_submission, output_directory, sources, load_protected):
    """Retain an exact candidate snapshot; target callback follows full restoration."""
    export_path, binding_path, submission_path, output_directory, _ = separate(
        export_path, binding_path, submission_path, output_directory, HERE)
    receipt, binding = admit_export(export_path, expected_export, binding_path, sources)
    submitted = snapshot(submission_path, expected_submission, PREDICTION_CAP)
    output = fresh(output_directory)
    result = {"schema": "neural017_opaque_artifact_grade_v1", "status": "operator_error",
        "export_receipt": expected_export, "submission": expected_submission,
        "public": receipt["public"], "source_dependencies": sources.source_pin,
        "implementation": sources.implementation_pin, "protected_callback_invocations": 0,
        "participant_execution_verified": False, "native_understanding_measured": False,
        "runtime": runtime()}
    started = time.monotonic()
    try:
        captured = output / "captured_predictions.npz"
        write_new(captured, submitted, PREDICTION_CAP)
        del submitted
        candidate = sources.grader.candidate_npz(captured, 574, 45)
        # Candidate processes cannot write this operator-private snapshot. The
        # second identity check also detects accidental mutation during parsing.
        snapshot(captured, expected_submission, PREDICTION_CAP)
        restored = sources.delivery.restore_prediction(candidate, binding,
            expected_binding_sha256=receipt["binding_content_sha256"])
        result["restored_prediction"] = write_new(output / "restored_predictions.npz",
            sources.arrays.dump_arrays(restored, cap=PREDICTION_CAP), PREDICTION_CAP)
        result["protected_callback_invocations"] += 1
        gold, comparator = load_protected()
        score = sources.grader.evaluate(restored, gold, comparator, sources.metrics)
        result["score"] = write_new(output / "score.json", encoded(score), METADATA_CAP)
        result["status"] = score["status"]
        return result
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)[:500]
        raise
    finally:
        result["wall_seconds"] = time.monotonic() - started
        write_new(output / "RECEIPT.json", encoded(result), METADATA_CAP)


def protected_loader(target_path, comparator_path, sources, *, other_roles=()):
    """Construct a deferred loader; do not inspect either path before invocation."""
    def load():
        import numpy as np
        separate(target_path, comparator_path, *other_roles, HERE)
        selected = {}
        specifications = (
            ("targets", target_path, ("counts_heldout", "trial_ids", "unit_ids", "valid_mask", "panel_fingerprint")),
            ("comparator", comparator_path, ("rates_condition_psth", "trial_ids", "heldout_unit_ids", "bin_left_edges_ms", "prediction_units", "panel_fingerprint")),
        )
        for role, path, keys in specifications:
            body = snapshot(path, asset_pin(sources.assets["private"][role]), PUBLIC_CAP)
            with np.load(io.BytesIO(body), allow_pickle=False) as archive:
                need(set(keys) <= set(archive.files), "Original private operand fields")
                selected[role] = {key: archive[key] for key in keys}
        fixed = selected["comparator"]
        fixed["expected_counts"] = fixed.pop("rates_condition_psth")
        for name in ("prediction_units", "panel_fingerprint"):
            fixed[name] = sources.grader.text(fixed[name], name)
        return selected["targets"], fixed
    return load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    exp = sub.add_parser("export")
    for name in ("source", "key", "public-output", "operator-output"):
        exp.add_argument("--" + name, required=True)
    grade = sub.add_parser("grade")
    for name in ("export-receipt", "export-sha256", "binding", "submission", "submission-sha256", "target", "comparator", "output"):
        grade.add_argument("--" + name, required=True)
    for name in ("export-bytes", "submission-bytes"):
        grade.add_argument("--" + name, type=int, required=True)
    args = parser.parse_args()
    sources = load_sources()
    if args.command == "export":
        result = export_packet(args.source, args.key, args.public_output, args.operator_output, sources)
    else:
        result = collect_and_grade(args.export_receipt,
            {"bytes": args.export_bytes, "sha256": args.export_sha256}, args.binding,
            args.submission, {"bytes": args.submission_bytes, "sha256": args.submission_sha256},
            args.output, sources, protected_loader(args.target, args.comparator, sources,
                other_roles=(args.output, args.submission, args.export_receipt, args.binding)))
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
