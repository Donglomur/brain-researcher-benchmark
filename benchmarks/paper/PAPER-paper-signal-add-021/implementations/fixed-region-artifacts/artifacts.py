"""Trusted external-artifact route for the existing complete TMS fixed-region profile.

No participant process is executed or supervised. Snapshots bind artifact bytes,
not authorship, input dependence, producer closure or isolated code access.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

PROFILE = "PAPER-paper-signal-add-021.fixed-regions-v1"
SCORER = {"bytes": 12412, "sha256": "0211d01f059378f09c665df7c7b825c4bd1812e33671b420c49da9ce6504fd3e"}
REFERENCE = {"bytes": 359637, "sha256": "ceba59b4702c692c4e6819deb5cf72f8d6ebdb68b2a48228caf1860b266f30d8"}
INPUTS = {
    "INPUT.json": {"bytes": 4814, "sha256": "a0e3328495f4ba090ba1b2e3b1fe78ed22793ce38a6c78963d9f5637b9b1ab70"},
    "values.f64": {"bytes": 35616000, "sha256": "93e721d490676f232ae2ac11b065294c0e660f267bcdc466080791c91641264c"},
    "pair_counts.u8": {"bytes": 222600, "sha256": "6c0d2c0bb833b9bb8efb1ff72400403abbf92882cb5ae1e96322e246f805b4d8"},
    "missingness.json": {"bytes": 1428, "sha256": "a2d16bef2777c493df79bbdc83cb058908a6cd28b45723e1a0d11cbd83c61e20"},
}
SHARED = {
    "TASK.md": {"bytes": 2773, "sha256": "dc4c933535debdf6e26cbc527665fedf5ecf0dcbed7ad29a843fff2673102d98"},
    "METHOD.json": {"bytes": 6292, "sha256": "d0868b617aa4e936319767603c2d34b10275133c21b80250d48fe5302bb709aa"},
    "SUBMISSION_SCHEMA.json": {"bytes": 15889, "sha256": "1167b43d7b352254b5e04d6f230c9a76b03b5829e461835cbee92edec04f0aac"},
}
MAX_SUBMISSION = 2 * 1024 * 1024
PHYSICAL = ("st_dev", "st_ino", "st_uid", "st_gid", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")


class Refusal(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Refusal(message)


def ordinary_path(value):
    p = Path(value).absolute()
    need(".." not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)),
         "canonical path without symlink ancestors required")
    return p


def fresh_file(value):
    p = ordinary_path(value)
    need(not p.exists() and p.parent.is_dir(), "fresh output file with existing parent required")
    return p


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def read_file(value, cap, expected=None, *, sink=None, readonly=False):
    """One stable ordinary-file pass; optional streaming copy never decodes arrays."""
    p = ordinary_path(value)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             "nonempty single-link ordinary file within byte cap required")
        if readonly:
            need(stat.S_IMODE(before.st_mode) == 0o400, "frozen artifact mode0400 required")
        h = hashlib.sha256(); parts = []; remaining = before.st_size
        while remaining:
            block = os.read(fd, min(65536, remaining))
            need(bool(block), "short source read")
            h.update(block); remaining -= len(block)
            if sink is None:
                parts.append(block)
            else:
                need(sink.write(block) == len(block), "short output write")
        need(os.read(fd, 1) == b"", "source grew while reading")
        old = tuple(getattr(before, k) for k in PHYSICAL)
        need(old == tuple(getattr(os.fstat(fd), k) for k in PHYSICAL)
             == tuple(getattr(p.lstat(), k) for k in PHYSICAL), "source changed while reading")
        observed = {"bytes": before.st_size, "sha256": h.hexdigest()}
        if expected is not None:
            need(observed == expected, "file identity mismatch")
        return (b"".join(parts) if sink is None else None), observed
    finally:
        os.close(fd)


def write_new(path, body, mode=0o400):
    p = fresh_file(path)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            need(stream.write(body) == len(body), "short artifact write")
            stream.flush(); os.fsync(fd)
        os.fchmod(fd, mode)
    finally:
        os.close(fd)


def source(profile_root):
    root = ordinary_path(profile_root)
    for name, expected in SHARED.items():
        read_file(root / name, expected["bytes"], expected)
    body, _ = read_file(root / "scorer.py", SCORER["bytes"], SCORER)
    module = types.ModuleType("tms_fixed_regions_accepted_scorer")
    module.__file__ = str(root / "scorer.py")
    # Execute the exact authenticated bytes, avoiding a second loader path read.
    exec(compile(body, module.__file__, "exec"), module.__dict__)
    return module


def check_inputs(root, *, expected=INPUTS, destination=None):
    """Import already accepted full inputs; no MAT conversion or reference read."""
    root = ordinary_path(root)
    need(root.is_dir() and {x.name for x in root.iterdir()} == set(expected), "exact complete input directory required")
    target = None
    if destination is not None:
        target = ordinary_path(destination)
        need(not target.exists() and target.parent.is_dir(), "fresh input destination required")
        need(not target.is_relative_to(root) and not root.is_relative_to(target), "input roots must be disjoint")
        target.mkdir(mode=0o700)
    observed = {}
    for name, descriptor in expected.items():
        if target is None:
            # A discard sink retains no array bytes during the identity pass.
            class Discard:
                def write(self, block): return len(block)
            _, observed[name] = read_file(root / name, descriptor["bytes"], descriptor, sink=Discard())
        else:
            out = target / name
            fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(fd, "wb", closefd=False) as stream:
                    _, observed[name] = read_file(root / name, descriptor["bytes"], descriptor, sink=stream)
                    stream.flush(); os.fsync(fd)
                os.fchmod(fd, 0o400)
            finally:
                os.close(fd)
    need({x.name for x in root.iterdir()} == set(expected), "input membership changed")
    if target is not None:
        target.chmod(0o500)
    return {"schema": "tms_fixed_regions_input_import_v1", "profile_id": PROFILE,
            "input_files": observed, "complete_input_bytes": sum(x["bytes"] for x in observed.values()),
            "copied": target is not None, "input_root": str(target or root),
            "array_decode": False, "reference_reads": 0,
            "identity_basis": "One stable source stream; copied bytes written/fsynced. No independent output rehash."}


def validate_submission(path, scorer, *, expected=None, readonly=False):
    body, observed = read_file(path, MAX_SUBMISSION, expected, readonly=readonly)
    scorer.validate(scorer.decode(body))
    return body, observed


def freeze_pair(a, b, output, scorer):
    a, b = ordinary_path(a), ordinary_path(b)
    need(a != b, "two distinct A/B artifact locators required")
    need(not a.samefile(b), "two distinct physical A/B artifact files required")
    target = ordinary_path(output)
    need(not target.exists() and target.parent.is_dir(), "fresh pair directory required")
    bodies = {}; descriptors = {}
    for role, path in (("A", a), ("B", b)):
        bodies[role], observed = validate_submission(path, scorer)
        descriptors[role] = {"file": role + ".json", **observed}
    # Both complete schemas pass before the snapshot is published.
    target.mkdir(mode=0o700)
    for role, body in bodies.items():
        write_new(target / (role + ".json"), body)
    receipt = {"schema": "tms_fixed_regions_artifact_pair_v1", "profile_id": PROFILE,
               "scorer": SCORER, "submissions": descriptors,
               "trusted_external_artifacts": True, "protected_execution_attested": False}
    write_new(target / "PAIR.json", encode(receipt))
    target.chmod(0o500)
    return {"pair_root": str(target), "pair_manifest": pin(encode(receipt)), **receipt}


def load_pair(root, scorer):
    root = ordinary_path(root)
    need(root.is_dir() and stat.S_IMODE(root.stat().st_mode) == 0o500,
         "frozen pair directory mode0500 required")
    need({x.name for x in root.iterdir()} == {"A.json", "B.json", "PAIR.json"}, "exact pair membership required")
    raw, identity = read_file(root / "PAIR.json", 65536, readonly=True)
    receipt = scorer.decode(raw)
    need(type(receipt) is dict and set(receipt) == {"schema", "profile_id", "scorer", "submissions",
         "trusted_external_artifacts", "protected_execution_attested"}, "exact pair receipt fields required")
    need(receipt["schema"] == "tms_fixed_regions_artifact_pair_v1" and receipt["profile_id"] == PROFILE
         and receipt["scorer"] == SCORER and receipt["trusted_external_artifacts"] is True
         and receipt["protected_execution_attested"] is False, "wrong artifact profile or protection claim")
    need(type(receipt["submissions"]) is dict and set(receipt["submissions"]) == {"A", "B"}, "both artifact arms required")
    bodies = {}
    for role in ("A", "B"):
        row = receipt["submissions"][role]
        need(type(row) is dict and set(row) == {"file", "bytes", "sha256"} and row["file"] == role + ".json"
             and type(row["bytes"]) is int and 0 < row["bytes"] <= MAX_SUBMISSION
             and type(row["sha256"]) is str and len(row["sha256"]) == 64
             and all(c in "0123456789abcdef" for c in row["sha256"]), "exact bounded artifact descriptor required")
        bodies[role], _ = validate_submission(root / row["file"], scorer,
                            expected={k: row[k] for k in ("bytes", "sha256")}, readonly=True)
    return bodies, identity


def score_pair(pair_root, reference_path, output, scorer, *, reference_pin=REFERENCE, reference_reader=read_file):
    target = fresh_file(output)
    root = ordinary_path(pair_root)
    need(not target.is_relative_to(root), "score output must be outside frozen pair")
    bodies, pair_identity = load_pair(root, scorer)
    # This is the sole private-reference body read, after BOTH frozen snapshots
    # have passed complete public validation. No producer process claim follows.
    try:
        reference, observed = reference_reader(reference_path, reference_pin["bytes"], reference_pin)
    except (OSError, Refusal) as exc:
        raise scorer.InvalidReference("private reference intake failed") from exc
    scores = {role: scorer.score_submission(bodies[role], reference, reference_pin["sha256"])
              for role in ("A", "B")}
    result = {"schema": "tms_fixed_regions_trusted_pair_scores_v1", "profile_id": PROFILE,
              "pair_manifest": pair_identity, "reference_identity": observed, "scores": scores,
              "protected_execution_attested": False, "causal_code_access_effect_established": False,
              "combined_arm_metric": None}
    body = encode(result); need(len(body) <= 65536, "score report extent")
    write_new(target, body, mode=0o600)
    return {"status": "scored_trusted_external_artifacts", "output": str(target), **pin(body)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-root", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    p = commands.add_parser("check-inputs"); p.add_argument("--input-root", type=Path, required=True)
    p = commands.add_parser("prepare-inputs"); p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True); p.add_argument("--receipt", type=Path, required=True)
    p = commands.add_parser("validate"); p.add_argument("--submission", type=Path, required=True)
    p = commands.add_parser("freeze-pair"); p.add_argument("--submission-a", type=Path, required=True)
    p.add_argument("--submission-b", type=Path, required=True); p.add_argument("--output-root", type=Path, required=True)
    p = commands.add_parser("score-pair"); p.add_argument("--pair-root", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv); scorer = source(args.profile_root)
    try:
        if args.command == "inspect":
            result = {"profile_id": PROFILE, "input_files": INPUTS, "reference": REFERENCE,
                      "scorer": SCORER, "regions": 12, "effects": 36, "omissions": 540,
                      "candidate_execution": False, "kind": "trusted_external_artifacts"}
        elif args.command == "check-inputs":
            result = check_inputs(args.input_root)
        elif args.command == "prepare-inputs":
            receipt = fresh_file(args.receipt)
            need(not receipt.is_relative_to(ordinary_path(args.source_root))
                 and not receipt.is_relative_to(ordinary_path(args.output_root)), "receipt must be outside both input directories")
            result = check_inputs(args.source_root, destination=args.output_root)
            write_new(receipt, encode(result))
        elif args.command == "validate":
            _, observed = validate_submission(args.submission, scorer)
            result = {"status": "valid_complete_artifact", "profile_id": PROFILE, **observed,
                      "regions": 12, "effects": 36, "omissions": 540, "reference_reads": 0}
        elif args.command == "freeze-pair":
            result = freeze_pair(args.submission_a, args.submission_b, args.output_root, scorer)
        else:
            need(sys.implementation.name == "cpython" and sys.version_info[:3] == (3, 11, 6),
                 "accepted scoring convention requires CPython3.11.6")
            result = score_pair(args.pair_root, args.reference, args.output, scorer)
        print(json.dumps(result, indent=2, allow_nan=False)); return 0
    except scorer.InvalidReference as exc:
        print(json.dumps({"status": "invalid_reference", "reason": str(exc)}), file=sys.stderr); return 3
    except scorer.InvalidSubmission as exc:
        print(json.dumps({"status": "invalid_submission", "reason": str(exc)}), file=sys.stderr); return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
