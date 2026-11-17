#!/usr/bin/env python3
"""Trusted-host external artifact scoring; never execute submitted code."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import stat
import sys
import time
import types

ID = "NEURAL-023"
PROFILE = "neural023-indy-two-day-full22091-external-artifact-v1"
SOURCES = {
    "bundle": ("bundle.py", 5609, "8af2960dd6ee536b8232d9b7b91ff267b18df58e1749adc46411b004b565863f"),
    "candidate_io": ("candidate_io.py", 10034, "76ae6019ab40f08fbc98b0e2f52e64201884ef1111bb0d7a1e1553d054a2fdf4"),
    "score_core": ("score_core.py", 3150, "8cef8d269540d99b39ddf662542fff0c23aac41a1bf54dd2506d3f2f1a6319ca"),
    "arithmetic_audit": ("arithmetic_audit.py", 4083, "95cb22a4a115d7ede0278e8c1dfec7b5a1f830c16516b180c66a1a74e2b4f666"),
}
TARGET = {"bytes": 442344, "sha256": "ea6ff9173a8c9844901ab8dbe359993a648f9d883d60e7d61d0c3cb1159fb849"}
REFERENCE = {"bytes": 50164, "sha256": "36d70c140be63b585800b09d9c7d56cc34175a5c010f0182cc911d86f9337b3b"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def literal(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "Absolute path without parent traversal required")
    require(all(not p.is_symlink() for p in (path, *path.parents)), "No linked path or ancestor")
    return path


def snapshot(path, cap, expected=None, allow_empty=False):
    path = literal(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and (0 if allow_empty else 1) <= before.st_size <= cap, "Bounded ordinary single-link file")
        chunks, remaining = [], before.st_size
        while remaining:
            part = os.read(fd, min(65536, remaining))
            require(bool(part), "Snapshot truncated")
            chunks.append(part)
            remaining -= len(part)
        require(not os.read(fd, 1), "Snapshot grew")
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_nlink", "st_mtime_ns", "st_ctime_ns")
        require(all(getattr(before, k) == getattr(after, k) for k in fields), "Snapshot changed")
        body = b"".join(chunks)
    finally:
        os.close(fd)
    pin = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    if expected is not None:
        require(pin == {k: expected[k] for k in ("bytes", "sha256")}, "Pinned input mismatch")
    return body, pin


def project_path(root, relative):
    require(type(relative) is str and not Path(relative).is_absolute()
            and ".." not in Path(relative).parts, "Project-relative fixed source/input path required")
    return literal(root / relative)


def load_modules(root):
    """Compile only exact held source snapshots; never add a project directory to sys.path."""
    bodies = {}
    for name, (relative, size, digest) in SOURCES.items():
        bodies[name] = snapshot(project_path(root, relative), 64000,
                                {"bytes": size, "sha256": digest})[0]
    modules, old = {}, {}
    try:
        for name, body in bodies.items():
            old[name] = sys.modules.get(name)
            module = types.ModuleType(name)
            module.__file__ = str(root / SOURCES[name][0])
            modules[name] = module
            sys.modules[name] = module
            exec(compile(body, module.__file__, "exec"), module.__dict__)
    finally:
        for name in modules:
            if old[name] is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old[name]
    return modules


def score_snapshot(candidate_body, candidate_pin, modules, target_path, reference_path):
    """Reuse unchanged loaders/math through immutable in-memory input snapshots."""
    io = modules["candidate_io"]
    held = {"/submission/predictions.npz": (candidate_body, candidate_pin)}

    def held_bytes(path, pin, cap):
        body, saved = held[str(path)]
        require(len(body) <= cap and saved == {k: pin[k] for k in ("bytes", "sha256")},
                "Exact bounded snapshot binding")
        return body

    prior_reader = io.pinned_bytes
    io.pinned_bytes = held_bytes
    common = {"candidate_id": ID, "profile_id": PROFILE, "private_target_loads": 0,
              "candidate_code_executed": False, "method_provenance_verified": False,
              "primary_metric": "mean_axis_r2", "positive_gain_required": False,
              "binary_scientific_success": None, "biological_independent_units": 1,
              "unseen_final_evaluation": False}
    try:
        try:
            public = io.load_submission("/submission/predictions.npz", candidate_pin)
        except (io.InvalidSubmission, RecursionError) as error:
            return common | {"status": "invalid_submission", "reason": str(error), "primary_score": None}
        # No private/reference file, metadata or body is accessed before this boundary.
        ref_body, ref_pin = snapshot(reference_path, 150000, REFERENCE)
        held["/reference/metrics.json"] = (ref_body, ref_pin)
        references = io.load_reference("/reference/metrics.json", ref_pin)
        target_body, target_pin = snapshot(target_path, 1_000_000, TARGET)
        held["/private/assessment.npz"] = (target_body, target_pin)
        common["private_target_loads"] = 1
        target = io.load_target("/private/assessment.npz", target_pin)
        require((public["case_id"] == target["case_id"]).all(), "Exact public/private identity join")
        streams = {"candidate": public["velocity_m_s"]}
        try:
            result = modules["score_core"].score(target["velocity_m_s"], streams)
        except (ArithmeticError, ValueError) as error:
            return common | {"status": "unsupported_numerical_result", "primary_score": None,
                             "reason": "Finite predictions exceed supported metric arithmetic: " + type(error).__name__}
        try:
            independent = modules["arithmetic_audit"].audit(target["velocity_m_s"], streams, result)
        except ArithmeticError as error:
            return common | {"status": "unsupported_numerical_result", "primary_score": None,
                             "reason": "Independent scalar arithmetic cannot represent this finite submission: " + type(error).__name__}
        # Audit ValueError is an operator discrepancy, matching the accepted grade.py.
        candidate = result["metrics"]["candidate"]
        comparisons = {}
        for name, reference in references.items():
            comparisons[name] = {
                "candidate_minus_reference_r2": None if candidate["mean_axis_r2"] is None or reference["mean_axis_r2"] is None
                    else candidate["mean_axis_r2"] - reference["mean_axis_r2"],
                "reference_minus_candidate_mse": reference["mse"] - candidate["mse"],
                "reference_minus_candidate_mae": reference["mae"] - candidate["mae"]}
        return common | {"status": "scored_development_candidate", "primary_score": candidate["mean_axis_r2"],
                         "candidate_metrics": candidate, "fixed_clock_blocks": result["fixed_clock_blocks"],
                         "fixed_reference_metrics": references, "signed_reference_comparisons": comparisons,
                         "independent_candidate_arithmetic": independent, "submission_rows": len(public["case_id"])}
    finally:
        io.pinned_bytes = prior_reader


def write_new(path, value, cap=200000):
    body = (json.dumps(value, allow_nan=False, sort_keys=True, indent=2) + "\n").encode()
    require(len(body) <= cap, "Bounded complete output")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def run(root, submission, output, *, target, reference):
    start = time.monotonic()
    root, submission, output = map(literal, (root, submission, output))
    require(root.is_dir() and output.parent.is_dir() and not output.exists(), "Existing root/parent and fresh output required")
    modules = load_modules(root)
    output.mkdir(mode=0o700)
    receipt = {"candidate_id": ID, "profile_id": PROFILE, "status": "operator_error",
               "trusted_operator": True, "protected_candidate_execution": False,
               "candidate_program_executed": False, "private_target_loads": None,
               "scientific_requalification": False}
    try:
        body, pin = snapshot(submission, 1_000_000, allow_empty=True)
        receipt["submission"] = pin
        receipt["source_pins"] = {k: {"path": v[0], "bytes": v[1], "sha256": v[2]} for k, v in SOURCES.items()}
        receipt["reference_pin"] = REFERENCE
        receipt["target_pin"] = TARGET
        result = score_snapshot(body, pin, modules, target, reference)
        receipt["score"] = write_new(output / "score.json", result)
        receipt["status"] = result["status"]
        receipt["private_target_loads"] = result["private_target_loads"]
        receipt["scientific_claim_scope"] = "One exposed animal/day pair, full 22091-row artifact only"
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)[:1500]
    finally:
        receipt["wall_seconds"] = time.monotonic() - start
        write_new(output / "receipt.json", receipt)
    return receipt


def main():
    import resource
    import signal
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[key] = "1"
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), "Dedicated operator process without competing timer")
    def expired(*_):
        raise TimeoutError("30-second trusted operator wall limit")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 30)
    soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
    ceiling = min([20] + [value for value in (soft, hard) if value != resource.RLIM_INFINITY])
    resource.setrlimit(resource.RLIMIT_CPU, (ceiling, hard))
    try:
        result = run(args.source_root, args.submission, args.output, target=args.target, reference=args.reference)
        print(json.dumps({"status": result["status"], "output": str(args.output)}, allow_nan=False))
        return 1 if result["status"] == "operator_error" else 2 if result["status"] == "invalid_submission" else 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
