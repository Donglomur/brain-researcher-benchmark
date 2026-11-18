"""Trusted structural check of the complete MEG delivery, never a candidate run.

This evaluator-side operation intentionally opens the private panel before
delivery. It is separate from the paired runner's post-execution scoring gate.
No source arrays are reread, programme bytes executed, or cache introduced.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import struct
import time
import types

HERE = Path(__file__).resolve().parent
PAIRED = HERE.parent / "paired-program-v1"
ROSTER = {"bytes": 563, "sha256": "6e0970cb1a1a9aab53a35c43c3bcf84af527131631418bfd00594528e43bf70a"}
JSON_CAP = 2 * 1024**2
DATA_CAP = 13 * 1024**2


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def decoded(raw):
    def unique(rows):
        value = {}
        for key, item in rows:
            need(key not in value, "duplicate JSON key")
            value[key] = item
        return value
    def invalid(_):
        raise ValueError("nonfinite JSON")
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def descriptor(value):
    need(type(value) is dict and set(value) == {"bytes", "sha256"}
         and type(value["bytes"]) is int and 0 <= value["bytes"] <= 2**63 - 1
         and type(value["sha256"]) is str and len(value["sha256"]) == 64
         and all(c in "0123456789abcdef" for c in value["sha256"]), "exact byte/hash descriptor")
    return value


def ordinary(path):
    path = Path(path).absolute()
    need(".." not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
         "canonical ordinary path")
    return path


def signature(info):
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class Budget:
    """Bound logical file reads and report writes inside one original deadline."""
    def __init__(self, read_limit, write_limit, seconds, clock=time.monotonic, original_deadline=None):
        need(all(type(v) is int and v > 0 for v in (read_limit, write_limit, seconds)), "finite integer ceilings")
        need(read_limit <= 256 * 1024**2 and write_limit <= 1024**2 and seconds <= 300,
             "structural verifier maximum ceilings")
        self.read_limit, self.write_limit = read_limit, write_limit
        self.read_reserved = self.write_reserved = 0
        self.captured = {}
        self.clock, self.started = clock, clock()
        self.deadline = self.started + seconds
        if original_deadline is not None:
            need(type(original_deadline) in (int, float) and math.isfinite(original_deadline)
                 and self.started < original_deadline, "live original parent deadline")
            self.deadline = min(self.deadline, original_deadline)

    def tick(self):
        need(self.clock() < self.deadline, "original verification deadline")

    def read(self, path, expected, cap, mode=None):
        self.tick(); descriptor(expected)
        need(expected["bytes"] <= cap, "declared extent exceeds per-file ceiling")
        charge = expected["bytes"] + 1
        need(self.read_reserved + charge <= self.read_limit, "whole-verification logical read ceiling")
        self.read_reserved += charge
        path = ordinary(path)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                 and before.st_size == expected["bytes"], "exact regular single-link extent")
            if mode is not None:
                need(before.st_uid == os.geteuid() and stat.S_IMODE(before.st_mode) == mode,
                     "exact owned delivery leaf permissions")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                raw = handle.read(expected["bytes"] + 1)
            need(signature(before) == signature(os.fstat(fd)) == signature(path.lstat()), "file identity changed")
            need(pin(raw) == expected, "complete immutable bytes differ")
            need(path not in self.captured or self.captured[path] == signature(before), "reopened file changed identity")
            self.captured[path] = signature(before)
            self.tick()
            return raw
        finally:
            os.close(fd)

    def write(self, path, raw):
        self.tick()
        need(len(raw) <= 65536 and self.write_reserved + len(raw) <= self.write_limit, "report write ceiling")
        self.write_reserved += len(raw)
        path = ordinary(path)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as handle:
                handle.write(raw); handle.flush(); os.fchmod(fd, 0o600); os.fsync(fd)
        finally:
            os.close(fd)
        self.tick()
        return pin(raw)

    def final_snapshot(self):
        for path, captured in self.captured.items():
            self.tick()
            need(signature(ordinary(path).lstat()) == captured, "captured leaf changed before final observation")


def captured_sources(budget, paired_source_manifest):
    """Authenticate source bytes before compiling only the pure panel contract."""
    raw = budget.read(PAIRED / "SOURCE_MANIFEST.json", descriptor(paired_source_manifest), 8192)
    manifest = decoded(raw)
    files = manifest["files"]
    need(set(files) == {str(p.relative_to(PAIRED)) for p in PAIRED.rglob("*")
                       if p.is_file() and p != PAIRED / "SOURCE_MANIFEST.json"}, "exact paired source membership")
    captured = {name: budget.read(PAIRED / name, value, 131072) for name, value in files.items()}
    roster = budget.read(HERE.parent / "nested-connectivity-v1/published_participants.txt", ROSTER, 4096)
    constants = {}
    for node in ast.parse(captured["prepare.py"]).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("AUTHOR_FILES", "AUTHOR_REVISION", "PREPARED_BINDING"):
                constants[node.targets[0].id] = ast.literal_eval(node.value)
    need(set(constants) == {"AUTHOR_FILES", "AUTHOR_REVISION", "PREPARED_BINDING"}, "fixed source constants")
    contract = types.ModuleType("meg_delivery_captured_contract")
    contract.__file__ = str(PAIRED / "contract.py")
    exec(compile(captured["contract.py"], contract.__file__, "exec"), contract.__dict__)
    class CapturedRoster:
        def open(self, mode):
            need(mode == "rb", "read-only captured roster")
            return io.BytesIO(roster)
    # Preserve the exact roster reader's checks using the already accounted,
    # immutable captured bytes rather than unmetered repeat filesystem reads.
    contract.ROSTER_PATH = CapturedRoster()
    return captured, constants, contract


def inventory(root, expected_files, public_directories, captured=None):
    """Reject extra payloads, writable public trees, links and escaping mounts."""
    root = ordinary(root)
    dirs = {root}
    for path in expected_files:
        for parent in path.parents:
            if parent == root or root in parent.parents:
                dirs.add(parent)
    seen_files, seen_dirs = set(), {root}
    stack = [root]
    while stack:
        parent = stack.pop()
        need(len(seen_files) + len(seen_dirs) <= 256, "bounded complete delivery inventory")
        info = parent.lstat()
        public = any(parent == p or p in parent.parents for p in public_directories)
        need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
             and stat.S_IMODE(info.st_mode) == (0o555 if public else 0o700), "exact owned delivery directory mode")
        for entry in parent.iterdir():
            info = entry.lstat()
            if stat.S_ISDIR(info.st_mode):
                need(entry in dirs, "unexpected delivery directory")
                seen_dirs.add(entry); stack.append(entry)
            else:
                need(stat.S_ISREG(info.st_mode) and entry in expected_files, "unexpected delivery file or link")
                if captured is not None:
                    need(signature(info) == captured[entry], "captured delivery leaf changed")
                seen_files.add(entry)
    need(seen_files == set(expected_files) and seen_dirs == dirs, "complete exact delivery tree")


def bank_rows(raw, windows, budget):
    """Validate the fixed NumPy framing and all376 untouched tensor commitments."""
    need(raw[:8] == b"\x93NUMPY\x01\x00", "source np.save version1 framing")
    length = struct.unpack("<H", raw[8:10])[0]
    need(0 < length <= 4096 and len(raw) >= 10 + length, "bounded complete NPY header")
    header = raw[10:10 + length]
    need(header.endswith(b"\n"), "NPY header newline")
    shape = ast.literal_eval(header.decode("ascii"))
    need(type(shape) is dict and set(shape) == {"descr", "fortran_order", "shape"}
         and shape["descr"] == "<f8" and shape["fortran_order"] is False
         and type(shape["shape"]) is tuple and all(type(n) is int for n in shape["shape"])
         and shape["shape"] == (376, 4, 1000), "exact original bank dtype/order/geometry")
    start, width = 10 + length, 4 * 1000 * 8
    need(len(raw) == start + 376 * width, "no missing or trailing NPY payload")
    view = memoryview(raw)
    for index, row in enumerate(windows):
        budget.tick()
        tensor = view[start + index * width:start + (index + 1) * width]
        need(hashlib.sha256(tensor).hexdigest() == row["tensor_sha256"], "anonymous row/source tensor mismatch")
        need(all(math.isfinite(x[0]) for x in struct.iter_unpack("<d", tensor)), "nonfinite original tensor")


def verify(root, prepared_pin, paper_pin, output, *, paired_source_manifest,
           read_limit, write_limit, seconds, clock=time.monotonic,
           original_deadline=None, _generated_author_hashes=None):
    """No participant execution, source numerical rederivation or runtime grant.

    The explicit private test seam changes only the seven fictional author-file
    hashes, is absent from the CLI, and always emits a generated-only receipt.
    """
    budget = Budget(read_limit, write_limit, seconds, clock, original_deadline)
    root, output = ordinary(root), ordinary(output)
    need(output.parent.is_dir() and output != root and root not in output.parents,
         "private report must be outside the sealed delivery")
    out_dir = output.parent.stat()
    need(out_dir.st_uid == os.geteuid() and stat.S_IMODE(out_dir.st_mode) & 0o077 == 0,
         "operator-private report directory")
    captured, constants, contract = captured_sources(budget, paired_source_manifest)
    document = contract.decode_json(budget.read(root / "PREPARED.json", prepared_pin, JSON_CAP, 0o600))
    keys = {"schema", "task_id", "panel_sha256", "private_panel", "data", "contexts", "rows", "query_rows",
            "original_preparation", "programmes", "paper", "author", "contract", "fold_evidence",
            "historical_folds_authenticated", "source_revision", "freeze_order", "preparation_only",
            "native_phases", "scientific_results"}
    need(set(document) == keys and document["schema"] == "meg-prepared-paired-campaign/v1"
         and document["task_id"] == "PAPER-paper-method-add-010"
         and type(document["rows"]) is int and document["rows"] == 376
         and type(document["query_rows"]) is int and document["query_rows"] == 188,
         "exact complete selected preparation")
    need(document["original_preparation"] == constants["PREPARED_BINDING"]
         and document["source_revision"] == constants["AUTHOR_REVISION"], "accepted declared source identities")
    need(document["historical_folds_authenticated"] is False and document["scientific_results"] is False
         and document["preparation_only"] is True and type(document["native_phases"]) is int
         and document["native_phases"] == 0, "no preparation qualification promotion")
    need(document["freeze_order"] == "both programmes frozen before any original windows or fold labels were prepared"
         and type(document["fold_evidence"]) is str and 0 < len(document["fold_evidence"]) <= 4096,
         "fixed preparation declaration; not independent history proof")
    need(set(document["programmes"]) == {"A", "B"} and set(document["contexts"]) == {str(f) for f in range(10)},
         "both arms and all ten contexts")
    expected_files = {root / "PREPARED.json": (prepared_pin, 0o600, JSON_CAP)}
    expected_files[root / "PROGRAMMES_FROZEN.json"] = (pin(encoded(document["programmes"])), 0o600, 32768)
    expected_files[root / "PRIVATE_PANEL.json"] = (descriptor(document["private_panel"]), 0o600, JSON_CAP)
    mounts = {}
    def mount(name, value, relative, purpose, kind, names):
        path = root / relative
        need(type(value) is dict and set(value) == {"path", "kind", "purpose", "files"}
             and value["path"] == str(path) and value["kind"] == kind and value["purpose"] == purpose
             and type(value["files"]) is dict and set(value["files"]) == set(names), "exact declared delivery mount: " + name)
        for leaf, value_pin in value["files"].items():
            file = path / leaf if kind == "directory" else path
            cap = DATA_CAP if name == "data" else 32 * 1024**2 if name == "paper" else JSON_CAP
            if name.startswith("program-"):
                cap = {"submission.py": 1048576, "candidate_wrapper.py": 131072, "PROGRAM.json": 8192}[leaf]
                need(value_pin["bytes"] > 0, "nonempty frozen programme leaf")
            elif name == "author":
                cap = 1048576
            elif name == "contract":
                cap = 65536
            need(descriptor(value_pin)["bytes"] <= cap, "producer-compatible delivery leaf ceiling")
            need(file not in expected_files, "no aliased delivery leaf")
            expected_files[file] = (descriptor(value_pin), 0o444, cap)
        mounts[name] = value
    mount("data", document["data"], "data/WINDOWS.npy", "input", "file", {"WINDOWS.npy"})
    mount("paper", document["paper"], "paper", "paper", "directory", {"PAPER.bin"})
    need(document["paper"]["files"]["PAPER.bin"] == descriptor(paper_pin), "external selected paper pin")
    mount("contract", document["contract"], "contract", "contract", "directory", {"PARTICIPANT.md"})
    need(document["contract"]["files"]["PARTICIPANT.md"] == pin(captured["PARTICIPANT.md"]), "exact participant instructions")
    authors = constants["AUTHOR_FILES"]
    if _generated_author_hashes is not None:
        need(type(_generated_author_hashes) is dict and set(_generated_author_hashes) == set(authors), "complete explicit generated author seam")
        authors = _generated_author_hashes
    mount("author", document["author"], "author", "historical_author_source", "directory", authors)
    need(all(document["author"]["files"][name]["sha256"] == expected for name, expected in authors.items()), "fixed official source capsule")
    for role in ("A", "B"):
        programme = document["programmes"][role]
        need(type(programme) is dict and set(programme) == {"source", "mount"}, "exact frozen programme declaration")
        mount("program-" + role, programme["mount"], "program-" + role, "program", "directory",
              {"PROGRAM.json", "submission.py", "candidate_wrapper.py"})
        files = programme["mount"]["files"]
        need(files["candidate_wrapper.py"] == pin(captured["candidate_wrapper.py"]), "exact fixed wrapper")
        manifest = {"schema": "meg-frozen-program/v1", "files": {n: files[n] for n in ("submission.py", "candidate_wrapper.py")}}
        need(files["PROGRAM.json"] == programme["source"] == pin(encoded(manifest)), "complete frozen programme closure")
    for fold in range(10):
        context = document["contexts"][str(fold)]
        need(type(context) is dict and set(context) == {"mount", "context_sha256"}, "exact fold descriptor")
        mount("context-" + str(fold), context["mount"], f"contexts/fold-{fold:02d}/CONTEXT.json", "input", "file", {"CONTEXT.json"})
    public_dirs = [root / n for n in ("program-A", "program-B", "paper", "contract", "author")]
    inventory(root, expected_files, public_dirs)
    bodies = {}
    for path, (expected, mode, cap) in expected_files.items():
        if path.name != "PREPARED.json":
            bodies[path] = budget.read(path, expected, cap, mode)
    need(contract.decode_json(bodies[root / "PROGRAMMES_FROZEN.json"]) == document["programmes"], "both frozen programmes match prepared declaration")
    panel = contract.decode_json(bodies[root / "PRIVATE_PANEL.json"])
    windows = contract.ordered_public_windows(panel)
    need(panel["panel_sha256"] == document["panel_sha256"]
         and panel["source_binding"] == constants["PREPARED_BINDING"], "complete private/source panel identity")
    contexts = []
    for fold in range(10):
        path = root / f"contexts/fold-{fold:02d}/CONTEXT.json"
        expected = contract.public_context(panel, fold)
        need(contract.decode_json(bodies[path]) == expected
             and document["contexts"][str(fold)]["context_sha256"] == expected["context_sha256"],
             "context labels, held queries, participant folds or bank order changed")
        contexts.append(expected["context_sha256"])
    bank_rows(bodies[root / "data/WINDOWS.npy"], windows, budget)
    inventory(root, expected_files, public_dirs, budget.captured)
    # Re-pin the small declaration after checking its complete leaf inventory.
    budget.read(root / "PREPARED.json", prepared_pin, JSON_CAP, 0o600)
    budget.final_snapshot()
    report = {"schema": "meg-protected-delivery-verification/v1", "status": "provisional_structural_check",
              "scope": "generated_delivery_control" if _generated_author_hashes is not None else "protected_delivery_structure",
              "prepared": prepared_pin, "paper": paper_pin, "paired_source_manifest": paired_source_manifest,
              "programmes": {r: document["programmes"][r]["source"] for r in ("A", "B")},
              "panel_sha256": document["panel_sha256"], "contexts": contexts,
              "participants": 94, "windows": 376, "predictions_per_condition": 188, "folds": 10,
              "verified_delivery_files": len(expected_files), "read_reserved_bytes": budget.read_reserved,
              "private_panel_reads": 1,
              "original_deadline": budget.deadline, "elapsed_before_report": clock() - budget.started,
              "external_successful_exit_deadline_and_final_report_pin_required": True,
              "source_array_numerical_rederivation": False, "preparation_history_independently_observed": False,
              "candidate_authorship_exposure_verified": False, "native_runtime_qualification": False,
              "scientific_qualification": False, "cache_introduced": False,
              "counter_scope": "Explicit verifier reads only; captured roster rereads are in memory. Interpreter/library I/O, physical I/O, aggregate CPU/RSS are not measured."}
    budget.write(output, encoded(report))
    return report


def bootstrap_pin(path):
    """Read one tiny regular descriptor; FIFO/device/symlink inputs cannot block."""
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= 8192,
             "bounded regular single-link bootstrap descriptor")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = handle.read(before.st_size + 1)
        need(len(raw) == before.st_size and signature(before) == signature(os.fstat(fd)) == signature(path.lstat()),
             "bootstrap descriptor changed")
        return descriptor(decoded(raw))
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared-root", "prepared-pin-json", "paper-pin-json", "paired-manifest-pin-json", "output"):
        parser.add_argument("--" + name, required=True)
    for name in ("read-limit", "write-limit", "seconds"):
        parser.add_argument("--" + name, required=True, type=int)
    args = parser.parse_args()
    # Tiny externally selected argument files are bootstrap inputs. Their own
    # identities must be included by the admitting operator/supervisor.
    value = verify(args.prepared_root, bootstrap_pin(args.prepared_pin_json), bootstrap_pin(args.paper_pin_json),
                   args.output, paired_source_manifest=bootstrap_pin(args.paired_manifest_pin_json),
                   read_limit=args.read_limit, write_limit=args.write_limit, seconds=args.seconds)
    print(encoded({"status": "returned_before_deadline", "persisted_status": value["status"],
                   "native_runtime_qualification": False, "scientific_qualification": False}).decode())


if __name__ == "__main__":
    main()
