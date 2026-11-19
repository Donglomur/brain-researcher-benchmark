"""N007 host-only epoch projection/request preflight.

Trusted driver, not an OS sandbox or participant operator. Original operation is
source-disabled in this preparation release. No provider, answers or grading.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import time

ORIGINAL_OPERATION_ENABLED = False
SCHEMA = "n007_epoch_host_preflight_v1"
CASES = (("development-001", 2780), ("development-002", 2670))
VISUAL_PIN = {"bytes": 15668, "sha256": "56025c814c05f7e3f88571dc8316517f8fae664be93829e4734ba0f4f104205f"}
MAX_READ = 2 * 2**30
MAX_WRITE = 32 * 2**20
TERMINAL_RESERVE = 65536
FORBIDDEN_EVENTS = ("socket.", "subprocess.", "os.system", "os.exec", "os.posix_spawn", "os.fork", "pty.spawn")
QUALIFICATIONS = {
    "provider_capacity_qualified": False, "input_token_bound_qualified": False,
    "remote_context_qualified": False, "complete_paired_campaign_qualified": False,
    "shared_model_prior_qualified": False, "hostile_programme_containment_qualified": False,
    "scientific_readiness": False, "population_generalization": False,
}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode()


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, "nonfinite JSON"))


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def ordinary(value):
    need(type(value) is str and Path(value).is_absolute(), "absolute path required")
    path = Path(os.path.abspath(value))
    need(".." not in Path(value).parts and all(not p.is_symlink() for p in (path, *path.parents)),
         "linked or traversing path")
    return path


def checked_descriptor(value, cap):
    need(type(value) is dict and set(value) == {"path", "bytes", "sha256"}, "exact descriptor")
    ordinary(value["path"])
    need(type(value["bytes"]) is int and 0 < value["bytes"] <= cap
         and type(value["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", value["sha256"]),
         "bounded descriptor pin")
    return value


def read_descriptor(value, cap):
    checked_descriptor(value, cap)
    path = ordinary(value["path"])
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == value["bytes"], "ordinary exact descriptor file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(value["bytes"] + 1)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(path.stat())
             and pin(raw) == {k: value[k] for k in ("bytes", "sha256")}, "descriptor identity mismatch")
        return raw
    finally:
        os.close(fd)


class Meter:
    """Conservative logical admitted extents, not physical IO or RSS telemetry."""
    def __init__(self, read_limit, write_limit, deadline):
        self.read_limit, self.write_limit, self.deadline = read_limit, write_limit, deadline
        self.read_bytes = self.write_bytes = self.transient_projection_bytes = 0

    def check(self):
        need(time.monotonic() < self.deadline, "preflight deadline exhausted")

    def read(self, count):
        self.check()
        need(type(count) is int and count >= 0 and self.read_bytes + count <= self.read_limit,
             "read extent budget exhausted")
        self.read_bytes += count

    def write(self, count, terminal=False):
        self.check()
        reserve = 0 if terminal else TERMINAL_RESERVE
        need(type(count) is int and count >= 0 and self.write_bytes + count + reserve <= self.write_limit,
             "artifact budget exhausted")
        self.write_bytes += count

    def snapshot(self):
        return {"admitted_read_extent_bytes": self.read_bytes,
                "cumulative_artifact_write_bytes": self.write_bytes,
                "transient_constructed_projection_bytes": self.transient_projection_bytes,
                "read_scope": "conservative file-open extents plus explicit mapped original-sample accounting; not physical IO",
                "write_scope": "driver and maintained projection writes reserved before emission, including failed writes"}


class Guard:
    """Scoped CPython audit guard. Cannot police native syscalls/inherited FDs."""
    def __init__(self, read_roots, read_files, output_root, deadline, meter=None):
        self.read_roots = tuple(ordinary(str(p)) for p in read_roots)
        self.read_files = {ordinary(str(p)) for p in read_files}
        self.output_root = ordinary(str(output_root))
        self.deadline, self.meter = deadline, meter
        self.active, self.denials = False, []
        self.denial_fd, self.denial_bytes = None, 0
        self.precharged_files = set()
        self._busy = False

    def deny(self, event):
        if len(self.denials) < 32:
            self.denials.append(str(event)[:120])
            if self.denial_fd is not None:
                raw = encode({"event": self.denials[-1], "sequence": len(self.denials) - 1})
                if self.denial_bytes + len(raw) <= 8192:
                    # This create-only owned journal is part of the reserved
                    # terminal allowance. No path or original content is logged.
                    if self.meter is not None:
                        need(self.meter.write_bytes + len(raw) <= self.meter.write_limit,
                             "reserved denial journal exhausted")
                        self.meter.write_bytes += len(raw)
                    at = 0
                    while at < len(raw):
                        n = os.write(self.denial_fd, raw[at:])
                        need(n > 0, "durable denial journal write")
                        at += n
                    os.fsync(self.denial_fd)
                    self.denial_bytes += len(raw)
        raise PermissionError("preflight guard denied " + str(event)[:120])

    def _path(self, value):
        if isinstance(value, int):
            return None  # fdopen/write on already-open descriptors is outside path-event coverage.
        if not isinstance(value, (str, bytes, os.PathLike)):
            self.deny("unresolvable_path")
        # Exact descriptors reject symlinks independently. Library import paths
        # may legitimately name a selected framework through an installation link.
        return Path(os.path.abspath(os.fsdecode(value))).resolve()

    def _inside(self, path, root):
        return path == root or root in path.parents

    def _read(self, path):
        return path in self.read_files or any(self._inside(path, p) for p in self.read_roots) or self._inside(path, self.output_root)

    def _write(self, path):
        return self._inside(path, self.output_root)

    def __call__(self, event, args):
        if not self.active or self._busy:
            return
        self._busy = True
        try:
            if time.monotonic() >= self.deadline:
                self.deny("deadline")
            if any(event.startswith(name) for name in FORBIDDEN_EVENTS):
                self.deny(event)
            if event == "open":
                path = self._path(args[0])
                if path is None:
                    return
                mode, flags = args[1], args[2]
                writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                    isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
                if writing:
                    if not self._write(path):
                        self.deny("write_outside_output")
                elif not self._read(path):
                    self.deny("read_outside_allowlist")
                elif self.meter is not None and path not in self.precharged_files:
                    try:
                        info = path.stat()
                    except FileNotFoundError:
                        pass
                    else:
                        if stat.S_ISREG(info.st_mode):
                            self.meter.read(info.st_size + 1)
            elif event in ("os.listdir", "os.scandir"):
                path = self._path(args[0])
                if path is not None and not self._read(path) and not any(path in p.parents for p in self.read_files):
                    self.deny("directory_outside_allowlist")
            elif event in ("os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.chown",
                           "os.truncate", "os.utime"):
                path = self._path(args[0])
                if path is not None and not self._write(path):
                    self.deny("mutation_outside_output")
            elif event in ("os.rename", "os.link", "os.symlink"):
                self.deny(event)  # No rename/link workflow is needed by this driver.
            elif event in ("os.chdir", "os.fchdir"):
                self.deny(event)
        finally:
            self._busy = False

    def checkpoint(self):
        need(not self.denials, "sticky guard denial")
        need(time.monotonic() < self.deadline, "preflight deadline exhausted")

    def __enter__(self):
        sys.addaudithook(self)
        self.active = True
        return self

    def __exit__(self, *unused):
        self.active = False


class Writer:
    def __init__(self, root, meter):
        self.root, self.meter, self.files = root, meter, {}

    def put(self, relative, raw, terminal=False):
        path = self.root / relative
        need(type(raw) is bytes and not path.exists(), "new exact artifact only")
        self.meter.write(len(raw), terminal)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            at = 0
            while at < len(raw):
                n = os.write(fd, raw[at:])
                need(n > 0, "complete artifact write")
                at += n
            os.fsync(fd)
        finally:
            os.close(fd)
        self.files[relative] = pin(raw)
        return {"path": str(path), **pin(raw)}


class _Clock:
    def __init__(self, epochs):
        self.epochs = epochs

    def __getitem__(self, index):
        need(type(index) is int and 0 <= index < self.epochs, "generated clock index")
        return (index / 120.0, 0.0, 1.0)


class GeneratedPacket:
    """One authenticated generated epoch repeated lazily; never original evidence."""
    def __init__(self, case, raw, contract):
        self.case, self.epochs = case, dict(CASES)[case]
        self.clock = _Clock(self.epochs)
        self._offset = contract._signal_offset(raw)
        self._rows = [struct.unpack_from("<3000d", raw, self._offset + k * 24000) for k in range(3)]

    def samples(self, start, stop, channels):
        need(type(start) is int and type(stop) is int and 0 <= start < stop <= self.epochs * 3000
             and stop - start == 3000 and start % 3000 == 0, "generated complete epoch only")
        need(channels == ["EEG Fpz-Cz", "EEG Pz-Oz", "EOG horizontal"], "generated all channels")
        return [list(row) for row in self._rows]

    def close(self):
        self._rows = ()


def validate_protocol(value):
    need(type(value) is dict and set(value) == {"schema", "mode", "selected", "repository_root",
         "output_root", "limits", "knowledge", "budget", "source", "fixtures", "materials"},
         "exact preflight protocol fields")
    need(value["schema"] == SCHEMA and value["mode"] in ("generated_control", "original")
         and type(value["selected"]) is bool, "typed preflight mode")
    need(value["selected"], "operation unselected")
    if value["mode"] == "original":
        need(ORIGINAL_OPERATION_ENABLED, "original operation source-disabled")
    root, output = ordinary(value["repository_root"]), ordinary(value["output_root"])
    need(root.is_dir() and not output.exists() and output.parent.is_dir()
         and output != root and root not in output.parents and output not in root.parents,
         "fresh disjoint output directory")
    limits = value["limits"]
    need(type(limits) is dict and set(limits) == {"read_bytes", "write_bytes", "wall_seconds"},
         "exact finite limits")
    need(type(limits["read_bytes"]) is int and 1 <= limits["read_bytes"] <= MAX_READ
         and type(limits["write_bytes"]) is int and 2 * TERMINAL_RESERVE <= limits["write_bytes"] <= MAX_WRITE
         and type(limits["wall_seconds"]) in (int, float) and math.isfinite(limits["wall_seconds"])
         and 0 < limits["wall_seconds"] <= 1800, "bounded finite operation")
    expected = root / "benchmarks/neural/NEURAL-007/implementations/epoch-isolated-pair-v1/epoch_visual.py"
    source = checked_descriptor(value["source"], 65536)
    need(ordinary(source["path"]) == expected and {k: source[k] for k in ("bytes", "sha256")} == VISUAL_PIN,
         "maintained visual source identity")
    if value["mode"] == "generated_control":
        need(value["materials"] is None and type(value["fixtures"]) is list and len(value["fixtures"]) == 2,
             "generated mode has two fixture inputs and no original materials")
        for row, (case, _) in zip(value["fixtures"], CASES):
            need(type(row) is dict and set(row) == {"case_id", "signals"} and row["case_id"] == case,
                 "canonical generated fixture order")
            checked_descriptor(row["signals"], 76106)
        need(len({r["signals"]["path"] for r in value["fixtures"]}) == 2, "distinct generated fixture files")
    else:
        need(value["fixtures"] == [], "original mode has no fixture substitution")
        checked_descriptor(value["materials"], 65536)
    need(type(value["knowledge"]) is dict and type(value["budget"]) is dict, "explicit request operands")
    return root, output, limits


def _load_visual(source):
    raw = read_descriptor(source, 65536)
    name = "_n007_host_preflight_visual"
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = source["path"]
    sys.modules[name] = module
    exec(compile(raw, source["path"], "exec"), module.__dict__)
    return module


def _original_setup(value, runtime, guard, meter):
    """Unreachable in this source-disabled release; retained future operator seam."""
    materials = decode(read_descriptor(value["materials"], 65536))
    need(materials["schema"] == "n007_epoch_qualification_materials_v1", "original materials schema")
    rows = materials["original_packets"]
    need([(x["case_id"], x["epochs"]) for x in rows] == list(CASES), "complete original roster")
    for row in rows:
        fact = runtime["viewer"].source_facts(row["case_id"])
        need(row["members"] == fact["raw_member_pins"], "unchanged original input pins")
    # Runtime body pins and retained proof metadata must authenticate before originals.
    for item in materials["proofs"]:
        descriptor = {k: item[k] for k in ("path", "bytes", "sha256")}
        guard.read_files.add(ordinary(item["path"]))
        read_descriptor(descriptor, 1048576)
    for key in ("resolved_executable", "numpy_core", "zlib_module"):
        descriptor = materials["runtime"][key]
        guard.read_files.add(ordinary(descriptor["path"]))
        read_descriptor(descriptor, 8 * 2**20)
    observed = runtime["runtime_identity"]
    expected = materials["runtime"]["versions"]
    need(all(observed[k] == expected[k] for k in ("python", "numpy", "zlib_compile", "zlib_runtime")),
         "selected existing runtime identity")
    # Authorize exact original body paths only after all retained/runtime proofs.
    for row in rows:
        for name in ("signals.npy", "manifest.json", "clock.npz"):
            path = ordinary(str(ordinary(row["root"]) / name))
            guard.read_files.add(path)
            guard.precharged_files.add(path)
    return rows, materials


def _saved_anchor(materials, runtime, case, png, guard, meter):
    """Read only the authenticated first-view range, never rehash the full wire."""
    expected_complete = {"bytes": 6551, "sha256": "fc4b99d1860903e06976e33ae13202253d75d1569b2985af486c0da62290559e"}
    matches = [p for p in materials["proofs"]
               if {k: p[k] for k in ("bytes", "sha256")} == expected_complete]
    need(len(matches) == 1, "exact accepted complete-render receipt")
    complete_descriptor = {k: matches[0][k] for k in ("path", "bytes", "sha256")}
    complete = decode(read_descriptor(complete_descriptor, 65536))
    base = ordinary(complete_descriptor["path"]).parent
    members = complete["output_members"]
    journal_name, wire_name = case + "/transport/journal.jsonl", case + "/transport/wire.bin"
    journal_path, wire_path = base / journal_name, base / wire_name
    guard.read_files.update((ordinary(str(journal_path)), ordinary(str(wire_path))))
    journal = read_descriptor({"path": str(journal_path), **members[journal_name]}, 4 * 2**20)
    previous, offset, selected = "0" * 64, 0, None
    rows = journal.splitlines()
    for sequence, line in enumerate(rows):
        guard.checkpoint()
        row = decode(line)
        need(type(row) is dict and set(row) == {"sequence", "direction", "offset", "bytes", "sha256", "complete", "previous"}
             and row["sequence"] == sequence and row["offset"] == offset and row["previous"] == previous
             and row["complete"] is True and row["direction"] == ("out" if sequence % 2 == 0 else "in")
             and type(row["bytes"]) is int and row["bytes"] > 0,
             "accepted journal chain/offset/order")
        if row["direction"] == "out":
            need(row["bytes"] <= 43454, "retained overview complete-frame bound")
        if sequence == 2:
            selected = row
        previous = hashlib.sha256(runtime["transport"].encode(row)).hexdigest()
        offset += row["bytes"]
    need(selected is not None and offset == members[wire_name]["bytes"], "complete accepted wire extent")
    # The journal body is authenticated by COMPLETE. The exact range digest,
    # rather than an unauthenticated file size, authenticates the consumed frame.
    guard.precharged_files.add(ordinary(str(wire_path)))
    meter.read(selected["bytes"])
    fd = os.open(wire_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == members[wire_name]["bytes"], "ordinary retained wire extent")
        frame = os.pread(fd, selected["bytes"], selected["offset"])
        after = os.fstat(fd)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(stamp(before) == stamp(after) == stamp(wire_path.stat())
             and len(frame) == selected["bytes"] and pin(frame)["sha256"] == selected["sha256"],
             "exact stable authenticated saved frame")
    finally:
        os.close(fd)
    header, saved = runtime["transport"].unpack(frame)
    need(header["kind"] == "view" and header["epoch_id"] == case + "/00000"
         and saved == png, "anchor agrees with accepted original overview bytes")
    return {"journal": members[journal_name], "wire_receipt_pin": members[wire_name],
            "offset": selected["offset"], "frame": pin(frame), "png": pin(saved),
            "scope": "one journal-authenticated range; whole wire was not rehashed"}


def execute(value, protocol_path):
    root, output, limits = validate_protocol(value)
    deadline = time.monotonic() + limits["wall_seconds"]
    meter = Meter(limits["read_bytes"], limits["write_bytes"], deadline)
    files = [ordinary(str(protocol_path)), ordinary(value["source"]["path"])]
    files += [ordinary(r["signals"]["path"]) for r in value["fixtures"]]
    if value["materials"] is not None:
        files.append(ordinary(value["materials"]["path"]))
    library_roots = {Path(sys.base_prefix).resolve(), Path(sys.prefix).resolve()}
    # stdlib/extension imports are allowed; arbitrary cwd/home inputs are not.
    guard = Guard([root, *library_roots], files, output, deadline, meter)
    report = {"schema": "n007_epoch_host_preflight_report_v1", "status": "failed",
              "mode": value["mode"], "roster_epochs": 5450, "projection_count": 0,
              "request_count": 0, "original_body_access": False,
              "original_packet_open_attempted": False,
              "full_original_projection_qualified": False,
              "original_operation_enabled": ORIGINAL_OPERATION_ENABLED,
              **QUALIFICATIONS}
    writer, roster_fd, stage = None, None, "guard"
    old_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        with guard:
            output.mkdir(mode=0o700)
            writer = Writer(output, meter)
            guard.denial_fd = os.open(output / "GUARD_DENIALS.jsonl",
                                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            writer.put("CONFIG.json", encode(value))
            stage = "maintained_source_runtime"
            need("contract" not in sys.modules, "fresh process without preloaded epoch contract required")
            visual = _load_visual(value["source"])
            runtime = visual.load_runtime(root)
            contract = runtime["contract"]
            need(contract.CASES == CASES and contract.TOTAL == 5450, "canonical unchanged roster")
            targets = contract.required_targets()
            need(len(targets) == 5450 and len(set(targets)) == 5450
                 and targets == tuple(f"{case}/{i:05d}" for case, count in CASES for i in range(count)),
                 "exact canonical roster audit")
            contract.checked_knowledge(value["knowledge"])
            budget = runtime["provider"].Budget(**value["budget"])
            budget.validate()
            need(budget.max_images == 2 and budget.image_detail == "original"
                 and budget.max_request_bytes <= runtime["sender"].REQUEST_CAP,
                 "unchanged complete-view byte policy")
            report["roster_sha256"] = pin(encode(list(targets)))["sha256"]
            report["runtime_identity"] = runtime["runtime_identity"]
            report["source_identity"] = runtime["source"]
            report["source_identity_scope"] = "Executed visual/contract/renderer dependency closure authenticated; epoch_provider.py local pin is recorded, not executed or independently qualified."
            rows, materials = (_original_setup(value, runtime, guard, meter)
                               if value["mode"] == "original" else (value["fixtures"], None))
            (output / "anchors").mkdir(mode=0o700)
            roster_fd = os.open(output / "roster.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            chain, roster_hash, roster_bytes, anchors = "0" * 64, hashlib.sha256(), 0, []
            for row, (case, count) in zip(rows, CASES):
                guard.checkpoint()
                stage = "packet"
                if value["mode"] == "generated_control":
                    packet = GeneratedPacket(case, read_descriptor(row["signals"], 76106), contract)
                else:
                    pins = row["members"]
                    # Packet authenticates signals once; locked metadata is read twice.
                    meter.read(pins["signals.npy"]["bytes"] + 2 * pins["manifest.json"]["bytes"]
                               + 2 * pins["clock.npz"]["bytes"] + 128 + 8)
                    report["original_packet_open_attempted"] = True
                    report["original_body_access"] = None  # Failed construction cannot prove zero reads.
                    packet = runtime["viewer"].Packet(row["root"], case)
                    report["original_body_access"] = True
                try:
                    for index in range(count):
                        guard.checkpoint()
                        stage = "projection"
                        if value["mode"] == "original":
                            meter.read(72000)
                        epoch = contract.project_epoch(packet, index)
                        metadata = contract.encode(epoch.metadata())
                        need(epoch.epoch_id == targets[report["projection_count"]]
                             and len(epoch.signals_npy) == 72128, "complete canonical projection")
                        meter.transient_projection_bytes += len(epoch.signals_npy)
                        line = encode({"epoch_id": epoch.epoch_id, "metadata": pin(metadata),
                                       "signals": pin(epoch.signals_npy), "previous_sha256": chain})
                        need(len(line) <= 512 and roster_bytes + len(line) <= 4 * 2**20, "compact bounded roster")
                        meter.write(len(line))
                        at = 0
                        while at < len(line):
                            n = os.write(roster_fd, line[at:])
                            need(n > 0, "complete roster write")
                            at += n
                        roster_hash.update(line)
                        roster_bytes += len(line)
                        chain = pin(line)["sha256"]
                        report["projection_count"] += 1
                        if index == 0:
                            stage = "anchor"
                            anchor_root = output / "anchors" / case
                            meter.write(len(metadata) + len(epoch.signals_npy))
                            projection = contract.write_projection(epoch, anchor_root)
                            writer.files[f"anchors/{case}/case.json"] = pin(metadata)
                            writer.files[f"anchors/{case}/signals.npy"] = pin(epoch.signals_npy)
                            session = visual.Session(epoch, runtime, budget.max_turns)
                            header, images = session.initial()
                            need(len(images) == 1 and images[0][:8] == b"\x89PNG\r\n\x1a\n"
                                 and struct.unpack(">II", images[0][16:24]) == (1400, 820),
                                 "actual complete original renderer geometry")
                            request = visual.request_bytes(session, value["knowledge"]["model"], budget, value["knowledge"])
                            guard.checkpoint()
                            request_pin = writer.put(f"anchors/{case}/request.json", request)
                            saved = (_saved_anchor(materials, runtime, case, images[0], guard, meter)
                                     if value["mode"] == "original" else None)
                            anchors.append({"epoch_id": epoch.epoch_id, "projection": projection,
                                            "request": request_pin, "png": pin(images[0]),
                                            "pixel_dimensions": [1400, 820],
                                            "session_id": session.session_id, "accepted_saved_frame": saved})
                            report["request_count"] += 1
                finally:
                    packet.close()
            os.fsync(roster_fd)
            os.close(roster_fd)
            roster_fd = None
            writer.files["roster.jsonl"] = {"bytes": roster_bytes, "sha256": roster_hash.hexdigest()}
            report["roster_chain_final_sha256"] = chain
            need(report["projection_count"] == 5450 and report["request_count"] == 2,
                 "complete projection audit and exactly two anchor requests")
            report["anchors"] = anchors
            proposals = {"schema": "n007_epoch_ingress_bindings_proposal_v1",
                         "status": "incomplete_false_approval_proposals", "rows": [
                {"epoch_id": a["epoch_id"], "approved": False, "role_boundary_verified": False,
                 "input_projection": a["projection"],
                 "required_six_mounts": ["/input/case.json", "/input/signals.npy", "/program/program.py",
                                         "/trusted/PROGRAMME.json", "/trusted/epoch_producer.py", "/trusted/contract.py"],
                 "programme_source": None, "image_content_boundary": None,
                 "scope": "exact input pins only; no exposure or native approval"} for a in anchors]}
            writer.put("PROPOSED_EXPOSURES.json", encode(proposals))
            guard.checkpoint()
            report["status"] = "passed"
            report["full_original_projection_qualified"] = value["mode"] == "original"
            stage = "terminal"
    except BaseException as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)[:240]}
    finally:
        guard.active = False
        if roster_fd is not None:
            os.close(roster_fd)
        sys.dont_write_bytecode = old_bytecode
    report["failure_stage"] = None if report["status"] == "passed" else stage
    report["guard_denials"] = list(guard.denials)
    report["guard_scope"] = "CPython audit path events; not native syscalls, inherited descriptors or OS sandbox"
    report["denial_journal"] = {"path": "GUARD_DENIALS.jsonl",
                                "scope": "append-only through closure; excluded from immutable artifact inventory; any nonempty body invalidates success"}
    report["counters"] = meter.snapshot()
    report["scope"] = ("Generated repeated-epoch fixtures; no original data or original qualification."
                       if value["mode"] == "generated_control" else
                       "Original projection audit and two request constructions only; no whole-panel requests, answers or provider evidence.")
    if writer is not None:
        report["artifacts_before_terminal"] = dict(writer.files)
        report["status_is_provisional"] = True
        report["completion_rule"] = "Require CLOSURE.json status passed and an empty GUARD_DENIALS.jsonl; any late denial invalidates success."
        report["terminal_report_bytes"] = 0
        for _ in range(8):
            raw = encode(report)
            if (report["terminal_report_bytes"] == len(raw)
                    and report["counters"]["cumulative_artifact_write_bytes"] == meter.write_bytes + len(raw)):
                break
            report["terminal_report_bytes"] = len(raw)
            report["counters"]["cumulative_artifact_write_bytes"] = meter.write_bytes + len(raw)
        else:
            raise ValueError("terminal accounting fixed point")
        # Terminal reserve remains writable after a deadline so the refusal is durable.
        saved_deadline, saved_guard_deadline = meter.deadline, guard.deadline
        meter.deadline = float("inf")
        guard.deadline, guard.active = float("inf"), True
        try:
            need(len(raw) <= 49152, "bounded terminal report")
            writer.put("REPORT.json", raw, terminal=True)
            # A caught denial during REPORT emission is now durable in the
            # independent journal. Reconcile it before the create-only closure.
            closure = {"schema": "n007_epoch_host_preflight_closure_v1",
                       "status": "passed" if report["status"] == "passed" and not guard.denials else "failed",
                       "guard_denials": list(guard.denials),
                       "report": writer.files["REPORT.json"],
                       "completion_rule": "passed is valid only with an empty GUARD_DENIALS.jsonl",
                       "counters": meter.snapshot(), "closure_bytes": 0}
            for _ in range(8):
                closure_raw = encode(closure)
                if (closure["closure_bytes"] == len(closure_raw)
                        and closure["counters"]["cumulative_artifact_write_bytes"] == meter.write_bytes + len(closure_raw)):
                    break
                closure["closure_bytes"] = len(closure_raw)
                closure["counters"]["cumulative_artifact_write_bytes"] = meter.write_bytes + len(closure_raw)
            else:
                raise ValueError("closure accounting fixed point")
            need(len(closure_raw) <= 4096, "bounded terminal closure")
            writer.put("CLOSURE.json", closure_raw, terminal=True)
            if guard.denials:
                report["status"], report["failure_stage"] = "failed", "guard_closure"
            report["guard_denials"], report["counters"] = list(guard.denials), meter.snapshot()
        finally:
            meter.deadline, guard.deadline, guard.active = saved_deadline, saved_guard_deadline, False
            if guard.denial_fd is not None:
                os.close(guard.denial_fd)
                guard.denial_fd = None
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--bytes", required=True, type=int)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    try:
        descriptor = {"path": args.protocol, "bytes": args.bytes, "sha256": args.sha256}
        value = decode(read_descriptor(descriptor, 65536))
        report = execute(value, args.protocol)
        sys.stdout.write(encode({"status": report["status"], "projection_count": report["projection_count"],
                                "request_count": report["request_count"], "failure_stage": report["failure_stage"]}).decode())
        return 0 if report["status"] == "passed" else 2
    except BaseException as exc:
        sys.stdout.write(encode({"status": "failed", "failure_stage": "protocol",
                                "error_type": type(exc).__name__, "message": str(exc)[:240]}).decode())
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
