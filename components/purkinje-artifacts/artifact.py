#!/usr/bin/env python3
"""Trusted-operator transport for the accepted full-ten-tree numerical scorer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import types

PROFILE = "released-ten-tree-external-artifact-v1"
PINS = {
    "schema.py": (2123, "76df29fdab9d70dbcf129788c4201bf75df65c4ce9abd9bf1f5fff334cbc4538"),
    "numeric_score.py": (8644, "d04eca18294d3cf328c52e3dea8cff63dd59dd639b366f3fe0a6435fea4a5973"),
    "REFERENCE_PINS.json": (638, "b091a5952a3c0dcacf2e16c49bfa4fa1e862e15af590db0c757cf38e621946cf"),
    "INPUT_PINS.json": (1991, "3478e8bfbfdf7e6ba865f37ac9562427290f9cc770f9b780c6d192a53af4d6fe"),
    "TASK.md": (11039, "f1a3f481639ca70a69e0c761dadaa78cf238bbd05b853b57427b2d83cd82cb00"),
    "SCHEMA.json": (2570, "699633364bc36b47ac67049df5508b5bbaffb7aee83e7ce743da4c74723f1652"),
}
RECEIPT_CAP = 16384
SCORE_CAP = 262144


class Refusal(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise Refusal(message)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def identity(st):
    return tuple(getattr(st, k) for k in
                 ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size",
                  "st_mtime_ns", "st_ctime_ns"))


def path(value):
    p = Path(os.path.abspath(value))
    for x in (p, *p.parents):
        need(not x.is_symlink(), "Symlink path or ancestor")
    return p


def read(p, cap, expected=None, mode=None):
    p = path(p)
    before = p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
         "Ordinary single-link file required")
    need(0 < before.st_size <= cap, "File extent outside limit")
    if mode is not None:
        need(stat.S_IMODE(before.st_mode) == mode, "Unexpected sealed file mode")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        opened = os.fstat(f.fileno())
        need(identity(before) == identity(opened), "File changed before open")
        body = f.read(cap + 1)
        after = os.fstat(f.fileno())
    need(identity(before) == identity(after) == identity(p.lstat()),
         "File changed during read")
    need(len(body) == before.st_size, "Incomplete file read")
    if expected is not None:
        need(pin(body) == {k: expected[k] for k in ("bytes", "sha256")},
             "Pinned file changed")
    return body


def pairs(rows):
    result = {}
    for k, v in rows:
        need(k not in result, "Duplicate metadata key")
        result[k] = v
    return result


def decode(body):
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          Refusal("Nonfinite metadata")))


def encoded(value, cap):
    b = (json.dumps(value, allow_nan=False, sort_keys=True, indent=2) + "\n").encode()
    need(len(b) <= cap, "Encoded metadata outside limit")
    return b


def write_new(p, body, mode):
    p = path(p)
    need(p.parent.is_dir(), "Existing output parent required")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
        os.fchmod(f.fileno(), mode)


def separate(a, b):
    need(a != b and not a.is_relative_to(b) and not b.is_relative_to(a),
         "Input and output paths overlap")


def contracts(profile_root):
    root = path(profile_root)
    bodies = {}
    for name, (size, sha) in PINS.items():
        bodies[name] = read(root / name, size, {"bytes": size, "sha256": sha})
    schema = types.ModuleType("schema")
    exec(compile(bodies["schema.py"], str(root / "schema.py"), "exec"), schema.__dict__)
    scorer = types.ModuleType("purkinje_numeric_score")
    old = sys.modules.get("schema")
    sys.modules["schema"] = schema
    try:
        exec(compile(bodies["numeric_score.py"], str(root / "numeric_score.py"), "exec"),
             scorer.__dict__)
    finally:
        if old is None:
            sys.modules.pop("schema", None)
        else:
            sys.modules["schema"] = old
    inputs = decode(bodies["INPUT_PINS.json"])
    references = decode(bodies["REFERENCE_PINS.json"])
    # These pinned public descriptors have exactly the accepted names/bytes/hashes.
    # Root paths are operator arguments; there is no substitute descriptor option.
    public = {"public_inputs": {n: {"path": n, **p} for n, p in inputs.items()},
              "input_files": len(inputs), "input_total_bytes": sum(p["bytes"] for p in inputs.values())}
    private = {"references": {n: {"path": n, **p} for n, p in references.items()}}
    return schema, scorer, private, public


def candidate(directory, schema, scorer, receipt=None):
    directory = path(directory)
    before = directory.lstat()
    need(stat.S_ISDIR(before.st_mode), "Submission directory required")
    names = {p.name for p in directory.iterdir()}
    actual = names - {"SUBMISSION.json"} if receipt is not None else names
    need(set(schema.REQUIRED) <= actual <= set(schema.CAPS), "Exact numerical file set")
    if receipt is not None:
        need(stat.S_IMODE(before.st_mode) == 0o500 and names == actual | {"SUBMISSION.json"},
             "Sealed submission namespace required")
        need(set(receipt["files"]) == actual, "Receipt member set")
    files = {}
    total = 0
    for name in sorted(actual):
        size = (directory / name).lstat().st_size
        need(0 < size <= schema.CAPS[name] and total + size <= schema.TOTAL_CAP,
             "Submission aggregate extent")
        total += size
        files[name] = read(directory / name, schema.CAPS[name],
                           receipt["files"][name] if receipt else None,
                           0o400 if receipt else None)
    need(identity(before) == identity(directory.lstat()) and
         names == {p.name for p in directory.iterdir()}, "Submission directory changed")
    scorer.admit(files)  # Entire candidate syntax first; exact topology joins remain in grade.
    if receipt is not None:
        need(receipt["total_bytes"] == total, "Receipt aggregate extent")
    return files


def copy_inputs(source_root, destination, assets):
    source_root, destination = path(source_root), path(destination)
    need(not destination.exists(), "Input destination already exists")
    need(destination.parent.is_dir(), "Existing input destination parent required")
    entries = assets["public_inputs"]
    need(len(entries) == assets["input_files"] == 15 and
         sum(x["bytes"] for x in entries.values()) == assets["input_total_bytes"] == 11990405,
         "Accepted complete input inventory")
    for name, row in entries.items():
        need(not Path(name).is_absolute() and ".." not in Path(name).parts,
             "Relative public filename")
        separate(destination, path(source_root / row["path"]))
    destination.mkdir(mode=0o700)
    for name, row in sorted(entries.items()):
        b = read(source_root / row["path"], row["bytes"], row)
        out = destination / name
        out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write_new(out, b, 0o400)
    # A receipt belongs next to the packet so participants receive exactly15 files.
    for d in sorted((x for x in destination.rglob("*") if x.is_dir()), reverse=True):
        d.chmod(0o500)
    destination.chmod(0o500)
    return {"profile": PROFILE, "files": {n: {k: v[k] for k in ("bytes", "sha256")}
            for n, v in entries.items()}, "total_bytes": assets["input_total_bytes"]}


def freeze(directory, attempt, schema, scorer, producer_stopped):
    need(producer_stopped is True, "Stopped-producer operator attestation required")
    directory, attempt = path(directory), path(attempt)
    separate(directory, attempt)
    need(not attempt.exists() and attempt.parent.is_dir(), "Fresh attempt required")
    files = candidate(directory, schema, scorer)
    receipt = {"profile": PROFILE, "schema": 1, "scorer": list(PINS["numeric_score.py"]),
               "wire_schema": list(PINS["schema.py"]), "producer_stopped_attested": True,
               "files": {n: pin(b) for n, b in files.items()},
               "total_bytes": sum(map(len, files.values()))}
    body = encoded(receipt, RECEIPT_CAP)
    attempt.mkdir(mode=0o700)
    for n, b in files.items():
        write_new(attempt / n, b, 0o400)
    write_new(attempt / "SUBMISSION.json", body, 0o400)
    attempt.chmod(0o500)
    return {"profile": PROFILE, "receipt": pin(body), "files": len(files),
            "total_bytes": receipt["total_bytes"]}


def load_attempt(attempt, expected, schema, scorer):
    body = read(path(attempt) / "SUBMISSION.json", RECEIPT_CAP, expected, 0o400)
    receipt = decode(body)
    need(type(receipt) is dict and set(receipt) ==
         {"profile", "schema", "scorer", "wire_schema", "producer_stopped_attested",
          "files", "total_bytes"}, "Exact receipt schema")
    need(receipt["profile"] == PROFILE and receipt["schema"] == 1 and
         receipt["scorer"] == list(PINS["numeric_score.py"]) and
         receipt["wire_schema"] == list(PINS["schema.py"]) and
         receipt["producer_stopped_attested"] is True, "Receipt contract")
    need(type(receipt["files"]) is dict and type(receipt["total_bytes"]) is int,
         "Receipt member map")
    for row in receipt["files"].values():
        need(type(row) is dict and set(row) == {"bytes", "sha256"} and
             type(row["bytes"]) is int and type(row["sha256"]) is str,
             "Receipt pin schema")
    return candidate(attempt, schema, scorer, receipt)


def score(reference_root, attempt, expected, output, schema, scorer, operator_assets):
    reference_root, attempt, output = path(reference_root), path(attempt), path(output)
    separate(attempt, output)
    need(not output.exists() and output.parent.is_dir(), "Fresh score output required")
    files = load_attempt(attempt, expected, schema, scorer)
    # All captured candidate bytes and public syntax are validated before this lazy callback.
    def reference():
        rows = operator_assets["references"]
        need(set(rows) == set(schema.REQUIRED), "Exact private reference inventory")
        return {n: read(reference_root / rows[n]["path"], schema.CAPS[n], rows[n])
                for n in schema.REQUIRED}
    result = scorer.grade(files, reference)
    value = {"profile": PROFILE, "submission_receipt": expected,
             "candidate_code_executed": False, "trusted_operator_only": True,
             "grade": result}
    write_new(output, encoded(value, SCORE_CAP), 0o600)
    return {"profile": PROFILE, "status": result["status"],
            "score_output": str(output), "private_feedback": True}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile-root", required=True, help="Published program-v1 source directory")
    p.add_argument("--seconds", type=int, required=True, help="Owned command wall limit,1..120")
    sub = p.add_subparsers(dest="command", required=True)
    x = sub.add_parser("inputs"); x.add_argument("--destination", required=True)
    x.add_argument("--source-root", required=True, help="Provisioned exact public-input directory")
    x = sub.add_parser("freeze"); x.add_argument("--submission", required=True)
    x.add_argument("--attempt", required=True); x.add_argument("--producer-stopped", action="store_true")
    x = sub.add_parser("score"); x.add_argument("--attempt", required=True)
    x.add_argument("--receipt-bytes", required=True, type=int)
    x.add_argument("--receipt-sha256", required=True); x.add_argument("--output", required=True)
    x.add_argument("--reference-root", required=True, help="Operator-private fixed reference directory")
    a = p.parse_args(argv)
    try:
        need(sys.version_info[:3] == (3, 11, 6), "Accepted CPython3.11.6 required")
        need(1 <= a.seconds <= 120, "Wall limit must be1..120 seconds")
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("Command deadline")))
        signal.setitimer(signal.ITIMER_REAL, a.seconds)
        schema, scorer, private, public = contracts(a.profile_root)
        if a.command == "inputs":
            result = copy_inputs(a.source_root, a.destination, public)
        elif a.command == "freeze":
            result = freeze(a.submission, a.attempt, schema, scorer, a.producer_stopped)
        else:
            need(0 < a.receipt_bytes <= RECEIPT_CAP and len(a.receipt_sha256) == 64 and
                 all(c in "0123456789abcdef" for c in a.receipt_sha256), "Expected receipt pin")
            result = score(a.reference_root, a.attempt,
                           {"bytes": a.receipt_bytes, "sha256": a.receipt_sha256},
                           a.output, schema, scorer, private)
        print(json.dumps(result, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, TimeoutError) as e:
        print(json.dumps({"status": "operator_error", "error": str(e)[:300]}), file=sys.stderr)
        return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
