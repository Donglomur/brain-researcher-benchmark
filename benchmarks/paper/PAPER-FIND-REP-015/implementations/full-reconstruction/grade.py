"""Complete 1020-record saved-artifact comparison with the unchanged science core."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import stat
import time
import types

TASK = "PAPER-FIND-REP-015"
CORE_PIN = (11539, "81aab53cdc08376c00bac759f842196abd2dad8c1127d926750a063cb5fa23a3")
ROSTER_PIN = (122364, "5fc17a0e33f646fee83ea19eccb7954e6ff11e2b87e6920cb3b1e4b9fb3a2128")
CANDIDATE_SCHEMA = "cerebellar-committed-numerical-artifacts-v1"
REFERENCE_SCHEMA = "cerebellar-canonical-private-references-v1"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def decode(body):
    def pairs(items):
        value = {}
        for k, v in items:
            need(k not in value, "duplicate JSON key")
            value[k] = v
        return value
    def constant(_):
        raise ValueError("nonfinite JSON literal")
    return json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def valid_pin(value, cap):
    need(type(value) is dict and set(value) == {"bytes", "sha256"}, "exact pin fields")
    need(type(value["bytes"]) is int and 0 < value["bytes"] <= cap, "bounded pin length")
    h = value["sha256"]
    need(type(h) is str and len(h) == 64 and all(x in "0123456789abcdef" for x in h), "exact SHA256")
    return value


def absolute(path):
    path = Path(path).absolute()
    need(path.parent.resolve(strict=True) == path.parent, "canonical trusted parent path")
    return path


def stamp(value):
    return tuple(getattr(value, k) for k in ("st_dev", "st_ino", "st_size", "st_mode", "st_nlink", "st_mtime_ns", "st_ctime_ns"))


def read_file(path, cap, pin=None, sealed=False):
    path = absolute(path); before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap
         and (not sealed or before.st_mode & 0o222 == 0), "bounded ordinary single-link sealed operand")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        need(stamp(before) == stamp(os.fstat(stream.fileno())), "unchanged opened identity")
        raw = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    need(len(raw) == before.st_size and stamp(before) == stamp(after) == stamp(path.lstat()), "stable complete operand")
    if pin is not None:
        valid_pin(pin, cap)
        need(len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"], "exact committed bytes")
    return raw


def load_sources(directory):
    directory = Path(directory)
    def source(name, p):
        return read_file(directory / name, p[0], {"bytes":p[0], "sha256":p[1]})
    science = types.ModuleType("pinned_cerebellar_science")
    exec(compile(source("science.py", CORE_PIN), str(directory / "science.py"), "exec"), science.__dict__)
    value = decode(source("ROSTER.json", ROSTER_PIN))
    return science, value["roster"]


def filename(identity):
    if identity["figure"] == "F2":
        return "F2_%s_u%04d.json" % (identity["mouse_source_label"], identity["source_index1"])
    return "F3_%s_rw%d.json" % (identity["mouse_source_label"], identity["source_index1"])


def inventory(folder, manifest_pin, names, reference=False):
    folder = absolute(folder); before = folder.lstat()
    need(stat.S_ISDIR(before.st_mode) and before.st_mode & 0o222 == 0, "trusted sealed directory")
    seen = []
    with os.scandir(folder) as iterator:
        for entry in iterator:
            seen.append(entry.name)
            need(len(seen) <= 1021, "bounded complete directory roster")
    need(set(seen) == set(names) | {"COMMIT.json"}, "exact complete tree")
    manifest = decode(read_file(folder / "COMMIT.json", 250000, manifest_pin, sealed=True))
    need(type(manifest) is dict and set(manifest) == {"schema", "candidate_id", "files", "total_bytes"}, "exact inventory fields")
    need(manifest["schema"] == (REFERENCE_SCHEMA if reference else CANDIDATE_SCHEMA)
         and manifest["candidate_id"] == TASK and type(manifest["files"]) is dict
         and set(manifest["files"]) == set(names), "complete fixed inventory")
    cap = 8000000 if reference else 2000000
    total = sum(valid_pin(manifest["files"][name], cap)["bytes"] for name in names)
    need(type(manifest["total_bytes"]) is int and total == manifest["total_bytes"]
         and total <= (4000000000 if reference else 1500000000), "complete bounded inventory extent")
    need(stamp(before) == stamp(folder.lstat()), "unchanged directory inventory")
    return folder, manifest


def validate_reference(science, reference, identity):
    need(type(reference) is dict and set(reference) == {"target", "trial_count_steps"}, "exact canonical reference fields")
    science.validate(reference["target"], identity)
    rows = reference["trial_count_steps"]
    need(type(rows) is list and len(rows) == identity["trials"], "exact reference trial count")
    for steps in rows:
        need(type(steps) is list and 1 <= len(steps) <= science.GRIDS[identity["figure"]], "nonempty bounded reference step series")
        previous = 0
        for step in steps:
            need(type(step) is list and len(step) == 5 and type(step[0]) is int
                 and previous < step[0] <= science.GRIDS[identity["figure"]], "exact ascending reference step row")
            need(previous != 0 or step[0] == 1, "reference covers first threshold")
            science.count_validate(step[1:]); previous = step[0]
    target = reference["target"]
    need(science.reference_counts(reference, target["selected_index1"]) == target["selected_trial_counts"], "reference selected counts agree with lossless steps")


def evaluate(science, roster, candidate_dir, candidate_pin, reference_dir, reference_pin, tick):
    names = [filename(row) for row in roster]
    need(len(roster) == len(set(names)) == 1020, "complete fixed roster")
    count = 0; rows = []; total = 0
    def failure(status, reason, record_name=None):
        return {"candidate_id":TASK, "status":status, "reason":reason, "record":record_name,
                "records_scored":len(rows), "private_reference_records_loaded":count,
                "partial_score":None, "scientific_qualified":False}
    try:
        tick(); candidate_dir, manifest = inventory(candidate_dir, candidate_pin, names)
        total = manifest["total_bytes"]
        for identity, name in zip(roster, names, strict=True):
            tick()
            science.validate(decode(read_file(candidate_dir / name, 2000000, manifest["files"][name], sealed=True)), identity)
    except (ValueError, OSError, UnicodeError, RecursionError, OverflowError, KeyError, TypeError) as error:
        if isinstance(error, TimeoutError): raise
        return failure("invalid_submission", type(error).__name__ + ": " + str(error)[:160], locals().get("name"))
    # Reference metadata and records are first opened after all 1020 candidates pass.
    try:
        tick(); reference_dir, references = inventory(reference_dir, reference_pin, names, reference=True)
    except (ValueError, OSError, UnicodeError, RecursionError, OverflowError, KeyError, TypeError) as error:
        if isinstance(error, TimeoutError): raise
        return failure("operator_error", "reference inventory: " + type(error).__name__)
    for identity, name in zip(roster, names, strict=True):
        tick()
        try:
            record = decode(read_file(candidate_dir / name, 2000000, manifest["files"][name], sealed=True))
            science.validate(record, identity)
        except (ValueError, OSError, UnicodeError, RecursionError, OverflowError, KeyError, TypeError) as error:
            if isinstance(error, TimeoutError): raise
            return failure("invalid_submission", "changed candidate: " + type(error).__name__, name)
        try:
            reference = decode(read_file(reference_dir / name, 8000000, references["files"][name], sealed=True))
            count += 1
            validate_reference(science, reference, identity)
        except (ValueError, OSError, UnicodeError, RecursionError, OverflowError, KeyError, TypeError) as error:
            if isinstance(error, TimeoutError): raise
            return failure("operator_error", "reference record: " + type(error).__name__ + ": " + str(error)[:160], name)
        try:
            score = science.grade(record, reference)
            need(all(type(v) not in (int, float) or math.isfinite(v) for v in score.values()), "finite scalar grade")
            rows.append(score)
        except (OverflowError, ValueError) as error:
            if isinstance(error, TimeoutError): raise
            return failure("invalid_submission", "unrepresentable scoring arithmetic: " + str(error)[:160], name)
    try:
        summary = science.aggregate(rows, roster)
        need(all(math.isfinite(x) for s in summary["figures"].values() for x in s["equal_mouse_mean"].values()), "finite aggregate")
    except (ValueError, OverflowError) as error:
        if isinstance(error, TimeoutError): raise
        return failure("invalid_submission", "unrepresentable aggregate: " + str(error)[:160])
    tables = {}
    for figure in ("F2", "F3"):
        group = [row for row in rows if row["identity"]["figure"] == figure]
        columns = [k for k in group[0] if k != "identity"]
        tables[figure] = {"columns":columns, "rows":[[row[k] for k in columns] for row in group]}
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    tick()
    return {"candidate_id":TASK, "status":"scored", "records_scored":1020,
            "private_reference_records_loaded":count, "submission_manifest":candidate_pin,
            "committed_artifact_bytes":total, "summary":summary, "diagnostics":tables,
            "ordered_record_scores_sha256":hashlib.sha256(raw).hexdigest(), "partial_score":None,
            "scientific_qualified":False, "canonical_reference_projection_qualified_by_this_run":False}


def write_report(path, result):
    raw = (json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    need(len(raw) <= 1000000, "complete output cap")
    path = absolute(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for x in ("candidate-dir", "reference-dir", "candidate-sha256", "reference-sha256", "output"):
        parser.add_argument("--"+x, required=True)
    for x in ("candidate-bytes", "reference-bytes", "seconds"):
        parser.add_argument("--"+x, required=True, type=int)
    args = parser.parse_args(argv)
    need(0 < args.seconds <= 600, "explicit bounded operation seconds")
    deadline = time.monotonic() + args.seconds
    def expired(*_): raise TimeoutError("operation deadline")
    def tick():
        if time.monotonic() >= deadline: expired()
    old = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, args.seconds)
    try:
        science, roster = load_sources(Path(__file__).resolve().parent)
        result = evaluate(science, roster, args.candidate_dir,
            {"bytes":args.candidate_bytes,"sha256":args.candidate_sha256}, args.reference_dir,
            {"bytes":args.reference_bytes,"sha256":args.reference_sha256}, tick)
        tick(); write_report(args.output, result); tick()
        return 2 if result["status"] == "operator_error" else 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, old)


if __name__ == "__main__":
    raise SystemExit(main())
