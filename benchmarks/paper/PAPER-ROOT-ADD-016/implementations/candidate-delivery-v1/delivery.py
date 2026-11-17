"""Exact-input delivery and structural pair closure; no fitting or reference access."""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import platform
import stat
import sys
import types
import uuid

HERE = Path(__file__).resolve().parent
MAX_JSON = 200_000
PROGRAM_LIMIT = 131_072
SOURCE_LIMIT = 200_000


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def decode(raw):
    def unique(pairs):
        value = {}
        for k, v in pairs:
            need(k not in value, "duplicate JSON key")
            value[k] = v
        return value
    def invalid(value):
        raise ValueError("nonfinite JSON token")
    return json.loads(raw.decode("utf8"), object_pairs_hook=unique, parse_constant=invalid)


def physical(path):
    path = Path(path)
    need(path.is_absolute() and ".." not in path.parts, "absolute physical path required")
    need(not any(p.is_symlink() for p in (path, *path.parents)), "symlink path")
    return path


def read(path, cap=MAX_JSON):
    path = physical(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "ordinary single-link file required")
    need(0 < before.st_size <= cap, "bounded nonempty file required")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    try:
        need(identity(os.fstat(fd)) == identity(before), "changed before snapshot")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(cap + 1)
        need(len(raw) == before.st_size, "changed file extent")
        need(identity(before) == identity(os.fstat(fd)) == identity(path.lstat()), "changed during snapshot")
    finally:
        os.close(fd)
    return raw


def checked(path, expected):
    raw = read(path, expected["bytes"])
    need(pin(raw) == expected, "changed pinned asset: " + Path(path).name)
    return raw


def write(path, raw, mode=0o600):
    path = physical(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(raw)


def fresh(out, forbidden):
    out = physical(out)
    need(out.parent.is_dir() and not out.exists(), "fresh output with existing parent required")
    for source in forbidden:
        source = physical(source)
        need(out != source and out not in source.parents and source not in out.parents,
             "output must be separate from source/input roots")
    out.mkdir(mode=0o700)
    return out


def relative(name):
    p = Path(name)
    need(type(name) is str and name and not p.is_absolute() and p.as_posix() == name and
         ".." not in p.parts and "\\" not in name and all(ord(c) >= 32 for c in name), "safe relative name")
    return p


def spec():
    raw = read(HERE / "DELIVERY_SPEC.json")
    value = decode(raw)
    need(value["schema"] == "cardiac_candidate_delivery_spec_v1", "delivery specification")
    for name in value["common"] | value["B_only"]:
        relative(name)
    need(set(value["common"]).isdisjoint(value["B_only"]), "disjoint condition assets")
    return value


def source_identity():
    # Reviewed release identity binds every local executable/specification body.
    return {name: pin(read(HERE / name)) for name in ("delivery.py", "DELIVERY_SPEC.json", "TASK.md", "SOURCE_MAP.md", "PUBLIC_FILES.json")}


def scorer(value):
    d = value["summary_scorer"]
    path = HERE.parent / "six-model-summary" / "summary_score.py"
    raw = checked(path, {k: d[k] for k in ("bytes", "sha256")})
    module = types.ModuleType("_cardiac_delivery_verified_summary")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def check_table(raw, value):
    need(pin(raw)["sha256"] == value["input"]["input_sha256"], "original CSV identity")
    reader = csv.DictReader(io.StringIO(raw.decode("utf8"), newline=""), strict=True)
    fields = ["", "subject_id", "age", "ECG_components", "ECG_not_rejected", "ECG_rejected"]
    need(reader.fieldnames == fields, "exact CSV header")
    rows = list(reader)
    need(len(rows) == 655, "complete 655-row cohort")
    need(all(set(r) == set(fields) and all(type(v) is str for v in r.values()) for r in rows), "rectangular CSV")
    ids = [r["subject_id"] for r in rows]
    need(all(ids) and len(set(ids)) == 655, "655 unique participants")
    digest = hashlib.sha256(json.dumps(ids, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    need(digest == value["participant_id_sha256"], "original ordered participant roster")
    for key in fields[2:]:
        numbers = [float(r[key]) for r in rows]
        need(all(math.isfinite(x) for x in numbers) and max(numbers) > min(numbers), "finite nonconstant input")
    return {"participants": 655, "models": 6, "parameters": 30,
            "ordered_participant_id_sha256": digest, "input": pin(raw)}


def members(value, condition):
    need(condition in ("A", "B"), "condition A or B required")
    return value["common"] | (value["B_only"] if condition == "B" else {})


def tree(root):
    root = physical(root)
    need(root.is_dir(), "packet directory required")
    files = set()
    for current, dirs, names in os.walk(root, followlinks=False):
        for child in dirs:
            path = Path(current) / child
            need(not path.is_symlink(), "symlink directory")
        for name in names:
            files.add((Path(current) / name).relative_to(root).as_posix())
    return files


def build(assets, out):
    value = spec()
    assets = physical(assets)
    payloads = {}
    # A supplied B packet is an exact source store; only the frozen allowlist copies.
    for name, expected in (value["common"] | value["B_only"]).items():
        origin = HERE if name in value["local_common"] else assets
        payloads[name] = checked(origin / relative(name), expected)
    coverage = check_table(payloads["meg_slope_data_sbg.csv"], value)
    scorer(value)  # Authenticate the current validator before creating anything.
    out = fresh(out, (HERE.parent, assets))
    pair_id = uuid.uuid4().hex
    requests = {}
    for condition in ("A", "B"):
        target = out / condition
        target.mkdir(mode=0o700)
        roster = members(value, condition)
        request = {"schema": "cardiac_delivery_request_v1", "benchmark_id": value["benchmark_id"],
                   "pair_id": pair_id, "condition": condition, "profile": value["profile"],
                   "files": roster, "coverage": coverage, "interface_source": source_identity(),
                   "runtime_qualified": False, "reference_accepted": False, "scientific_qualified": False}
        for name in roster:
            path = target / relative(name)
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            write(path, payloads[name], 0o444)
        requests[condition] = write(target / "REQUEST.json", encode(request), 0o444)
    receipt = {"schema": "cardiac_delivery_pair_v1", "pair_id": pair_id, "requests": requests,
               "coverage": coverage, "interface_source": source_identity(),
               "runtime_qualified": False, "reference_accepted": False, "scientific_qualified": False}
    write(out / "receipt.json", encode(receipt))
    return receipt


def verify_pair(pair):
    value = spec()
    pair = physical(pair)
    receipt = decode(read(pair / "receipt.json"))
    need(set(receipt) == {"schema", "pair_id", "requests", "coverage", "interface_source", "runtime_qualified", "reference_accepted", "scientific_qualified"}, "exact pair receipt")
    need(receipt["schema"] == "cardiac_delivery_pair_v1" and receipt["interface_source"] == source_identity(), "pair interface identity")
    need(set(receipt["requests"]) == {"A", "B"}, "both requests")
    need(type(receipt["pair_id"]) is str and len(receipt["pair_id"]) == 32 and all(c in "0123456789abcdef" for c in receipt["pair_id"]), "pair identifier")
    for flag in ("runtime_qualified", "reference_accepted", "scientific_qualified"):
        need(receipt[flag] is False, "qualification remains unestablished")
    for condition in ("A", "B"):
        root = pair / condition
        roster = members(value, condition)
        need(tree(root) == set(roster) | {"REQUEST.json"}, "closed candidate file roster")
        request = decode(checked(root / "REQUEST.json", receipt["requests"][condition]))
        expected = {"schema": "cardiac_delivery_request_v1", "benchmark_id": value["benchmark_id"],
                    "pair_id": receipt["pair_id"], "condition": condition, "profile": value["profile"],
                    "files": roster, "coverage": receipt["coverage"], "interface_source": source_identity(),
                    "runtime_qualified": False, "reference_accepted": False, "scientific_qualified": False}
        need(request == expected, "exact request/condition identity")
        for name, identity in roster.items():
            checked(root / relative(name), identity)
        coverage = check_table(read(root / "meg_slope_data_sbg.csv"), value)
        need(receipt["coverage"] == coverage, "complete original coverage")
    return receipt


def validate_summary(raw, value):
    summary = decode(raw)
    scorer(value).validate(summary)
    need(summary["input_sha256"] == value["input"]["input_sha256"], "summary original input identity")
    return summary


def capture(pair, condition, program, summary, out):
    value = spec()
    need(condition in ("A", "B"), "condition A or B required")
    receipt = verify_pair(pair)
    program_raw = read(program, PROGRAM_LIMIT)
    program_raw.decode("utf8")
    summary_raw = read(summary, MAX_JSON)
    validate_summary(summary_raw, value)
    out = fresh(out, (HERE.parent, Path(pair), Path(program).parent, Path(summary).parent))
    record = {"schema": "cardiac_delivery_capture_v1", "pair_id": receipt["pair_id"], "condition": condition,
              "request": receipt["requests"][condition], "interface_source": source_identity(),
              "program": write(out / "program.py", program_raw), "summary": write(out / "summary.json", summary_raw),
              "structurally_complete": True, "inference_verified": False, "reference_accepted": False,
              "scientific_qualified": False, "producer_closure_verified": False}
    write(out / "receipt.json", encode(record))
    return record


def verify_capture(path, condition, receipt):
    value = spec()
    path = physical(path)
    need(tree(path) == {"program.py", "summary.json", "receipt.json"}, "closed capture roster")
    record = decode(read(path / "receipt.json"))
    need(set(record) == {"schema", "pair_id", "condition", "request", "interface_source", "program", "summary", "structurally_complete", "inference_verified", "reference_accepted", "scientific_qualified", "producer_closure_verified"}, "exact capture receipt")
    need(record["schema"] == "cardiac_delivery_capture_v1" and record["condition"] == condition and
         record["pair_id"] == receipt["pair_id"] and record["request"] == receipt["requests"][condition] and
         record["interface_source"] == source_identity(), "capture condition/pair/source identity")
    need(record["structurally_complete"] is True and all(record[k] is False for k in
         ("inference_verified", "reference_accepted", "scientific_qualified", "producer_closure_verified")), "capture authority")
    need(record["program"]["bytes"] <= PROGRAM_LIMIT and record["summary"]["bytes"] <= MAX_JSON, "capture extent")
    checked(path / "program.py", record["program"]).decode("utf8")
    raw = checked(path / "summary.json", record["summary"])
    validate_summary(raw, value)
    return record, raw


def close_pair(pair, a, b, out):
    receipt = verify_pair(pair)
    a_record, a_raw = verify_capture(a, "A", receipt)
    b_record, b_raw = verify_capture(b, "B", receipt)
    out = fresh(out, (HERE.parent, Path(pair), Path(a), Path(b)))
    result = {"schema": "cardiac_delivery_closed_pair_v1", "pair_id": receipt["pair_id"],
              "coverage": receipt["coverage"], "captures": {"A": a_record, "B": b_record},
              "summary_files": {"A": write(out / "A.summary.json", a_raw), "B": write(out / "B.summary.json", b_raw)},
              "status": "complete_structural_pair_awaiting_independent_inference_and_reference_admission",
              "reference_accesses": 0, "scientific_qualified": False}
    write(out / "receipt.json", encode(result))
    return result


def runtime_report():
    modules = ("numpy", "pandas", "scipy", "bambi", "pymc", "arviz")
    available = {name: importlib.util.find_spec(name) is not None for name in modules}
    return {"schema": "cardiac_candidate_runtime_probe_v1", "python": sys.version, "executable": sys.executable,
            "platform": platform.platform(), "module_spec_found": available,
            "missing_modules": [name for name in modules if not available[name]],
            "probe_kind": "module discovery only; no numerical imports, native execution, installation or fitting",
            "native_fitting_blocked": not all(available.values()), "runtime_qualified": False,
            "remaining_requirements": ["same declared usable environment and budgets for both arms",
                "actual imports and source-model density validation", "six independent native fits and convergence review",
                "independent reference admission; hashes alone are insufficient"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    command = subs.add_parser("build")
    command.add_argument("--assets", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    command = subs.add_parser("verify-pair")
    command.add_argument("--pair", type=Path, required=True)
    command = subs.add_parser("capture")
    for name in ("pair", "program", "summary", "out"):
        command.add_argument("--" + name, type=Path, required=True)
    command.add_argument("--condition", choices=("A", "B"), required=True)
    command = subs.add_parser("close-pair")
    for name in ("pair", "a", "b", "out"):
        command.add_argument("--" + name, type=Path, required=True)
    command = subs.add_parser("runtime-probe")
    command.add_argument("--out", type=Path, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    if command == "runtime-probe":
        result = runtime_report()
        write(args["out"], encode(result))
    else:
        result = {"build": build, "verify-pair": verify_pair, "capture": capture, "close-pair": close_pair}[command](**args)
    print(json.dumps({"command": command, "status": result.get("status", "complete"), "scientific_qualified": False}))


if __name__ == "__main__":
    main()
