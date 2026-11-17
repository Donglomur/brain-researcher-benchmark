"""Typed whole-person sleep viewer; authentic preparation has not been run.

Only the response projection is participant-facing. This trusted operator tool
does not sandbox a model/provider, read labels, fit a model, or award a score.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import importlib.util
import io
import json
import math
import mmap
import os
from pathlib import Path
import stat
import struct
import sys
import zipfile
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CASES = {"development-001": 2780, "development-002": 2670}
CHANNELS = ("EEG Fpz-Cz", "EEG Pz-Oz", "EOG horizontal")
CLOCK = ("elapsed_hours", "wall_clock_sin", "wall_clock_cos")
CLASSES = ("W", "N1", "N2", "N3", "R")
GAINS = (10, 20, 50, 100, 200, 500, 1000)
MODE = "whole_person_raw_viewer_zero_shot"
MAX_REQUEST = 8192


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, "Duplicate JSON field")
        result[key] = value
    return result


def decode(body):
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, "Nonfinite JSON"))


def identity(info):
    return tuple(getattr(info, name) for name in
                 ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"))


def unlinked(path):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), "Linked paths refused")
    return path


def pinned_file(path, pin):
    """Return an open, hashed regular file; do not reopen after authentication."""
    path = unlinked(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stream = os.fdopen(fd, "rb")
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == pin["bytes"] <= 256 * 1024**2,
             "Exact bounded single-link input required")
        digest = hashlib.sha256()
        remaining = pin["bytes"]
        while remaining:
            block = stream.read(min(1024**2, remaining))
            need(block, "Input truncated during authentication")
            digest.update(block)
            remaining -= len(block)
        need(stream.read(1) == b"", "Input grew during authentication")
        need(digest.hexdigest() == pin["sha256"], "Input checksum mismatch")
        need(identity(before) == identity(os.fstat(fd)) == identity(path.stat()), "Input changed")
        stream.seek(0)
        stream.authenticated_identity = identity(before)
        return stream
    except BaseException:
        stream.close()
        raise


def locked_body(path, pin):
    with pinned_file(path, pin) as stream:
        body = stream.read(pin["bytes"] + 1)
        need(stream.authenticated_identity == identity(os.fstat(stream.fileno())) == identity(Path(path).stat()),
             "Input changed after authentication")
        need(len(body) == pin["bytes"] and sha(body) == pin["sha256"], "Authenticated body changed")
        return body


def load_module(name, path, body):
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def dependencies():
    bindings = decode((HERE / "SOURCE_BINDINGS.json").read_bytes())
    need(set(bindings) == {"raster", "adapter"}, "Exact source dependency closure required")
    result = {}
    for name, entry in bindings.items():
        relative = Path(entry["path"])
        need(not relative.is_absolute() and ".." not in relative.parts
             and str(relative) == entry["path"], "Normalized relative source path required")
        path = unlinked(ROOT / entry["path"])
        need(path.resolve().is_relative_to(ROOT.resolve()), "Source path escaped checkout")
        result[name] = load_module("sleep_viewer_" + name, path, locked_body(path, entry["pin"]))
    render = load_module("sleep_viewer_render", HERE / "render.py", (HERE / "render.py").read_bytes())
    return result["raster"], result["adapter"], render


def source_identity():
    return {name: {"bytes": (HERE / name).stat().st_size, "sha256": sha((HERE / name).read_bytes())}
            for name in ("viewer.py", "render.py", "SOURCE_BINDINGS.json", "SOURCE_FACTS.json")}


def runtime_identity():
    import numpy as np
    return {"python": sys.version.split()[0], "implementation": sys.implementation.name,
            "byte_order": sys.byteorder, "numpy": np.__version__,
            "zlib_compile": zlib.ZLIB_VERSION, "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION}


def source_facts(case):
    need(case in CASES, "Unknown development person")
    facts = decode((HERE / "SOURCE_FACTS.json").read_bytes())
    entries = {row["case_id"]: row for row in facts["cases"]}
    need({key: row["epochs"] for key, row in entries.items()} == CASES, "Canonical full roster required")
    return entries[case]


class Packet:
    """Read-only mapped original packet. Construction hashes actual signal bytes."""
    def __init__(self, root, case):
        import numpy as np
        self.root, self.case = unlinked(root), case
        fact = source_facts(case)
        self.epochs, self.pins = fact["epochs"], fact["raw_member_pins"]
        self.stream = self.mapping = None
        need({p.name for p in self.root.iterdir()} == {"manifest.json", "signals.npy", "clock.npz"},
             "Only the three original public packet members are admitted")
        manifest = decode(locked_body(self.root / "manifest.json", self.pins["manifest.json"]))
        need(manifest == fact["manifest"], "Complete source manifest required")
        clock_body = locked_body(self.root / "clock.npz", self.pins["clock.npz"])
        with zipfile.ZipFile(io.BytesIO(clock_body)) as archive:
            members = archive.infolist()
            need(len(members) == 2 and {m.filename for m in members} ==
                 {"epoch_start_seconds.npy", "clock_features.npy"}
                 and all(m.compress_type == zipfile.ZIP_STORED for m in members), "Exact stored clock members required")
        with np.load(io.BytesIO(clock_body), allow_pickle=False, max_header_size=4096) as clock:
            starts, values = clock["epoch_start_seconds"], clock["clock_features"]
        need(starts.dtype.str == values.dtype.str == "<f8" and starts.shape == (self.epochs,)
             and values.shape == (self.epochs, 3), "Exact source clock dtype and geometry required")
        need(np.array_equal(starts, np.arange(self.epochs, dtype=np.float64) * 30)
             and np.isfinite(values).all(), "Complete finite whole-clock metadata required")
        self.clock = values
        try:
            self.stream = pinned_file(self.root / "signals.npy", self.pins["signals.npy"])
            self.stat_identity = self.stream.authenticated_identity
            self.unchanged()
            header = self.stream.read(10)
            need(header[:8] == b"\x93NUMPY\x01\x00", "Original NPY version 1 required")
            size = struct.unpack("<H", header[8:10])[0]
            need(0 < size <= 4096, "Bounded NPY header required")
            descriptor = ast.literal_eval(self.stream.read(size).decode("latin1"))
            need(descriptor == {"descr": "<f8", "fortran_order": False,
                                "shape": (3, self.epochs * 3000)}, "Original complete signal geometry required")
            self.offset = size + 10
            need(self.offset + self.epochs * 3000 * 3 * 8 == self.pins["signals.npy"]["bytes"],
                 "NPY payload length mismatch")
            self.mapping = mmap.mmap(self.stream.fileno(), 0, access=mmap.ACCESS_READ)
            self.unchanged()
        except BaseException:
            self.close()
            raise

    def unchanged(self):
        need(identity(os.fstat(self.stream.fileno())) == self.stat_identity ==
             identity((self.root / "signals.npy").stat()), "Mapped signal changed or was replaced")

    def samples(self, start, stop, channels):
        need(type(start) is int and type(stop) is int and 0 <= start < stop <= self.epochs * 3000
             and 100 <= stop - start <= 6000 and type(channels) is list and channels
             and channels == [c for c in CHANNELS if c in channels], "Bounded ordered signal view required")
        self.unchanged()
        result = []
        for name in channels:
            offset = self.offset + (CHANNELS.index(name) * self.epochs * 3000 + start) * 8
            row = list(struct.unpack_from("<" + "d" * (stop - start), self.mapping, offset))
            need(all(math.isfinite(v) for v in row), "Nonfinite signal sample")
            result.append(row)
        self.unchanged()
        return result

    def close(self):
        if self.mapping is not None:
            self.mapping.close()
            self.mapping = None
        if self.stream is not None:
            self.stream.close()
            self.stream = None


def probabilities(values):
    import numpy as np
    need(type(values) is list and len(values) == 5 and all(type(v) in (int, float)
         and 0 <= v <= 1 and math.isfinite(v) for v in values), "Five finite class probabilities required")
    # Match the unchanged scorer's float64 summation and absolute tolerance.
    need(abs(float(np.sum(values, dtype=np.float64)) - 1) <= 1e-6, "Class probabilities must sum to one")
    return [float(v) for v in values]


class Session:
    """One complete person; future context and prior self-responses are allowed."""
    def __init__(self, packet, max_actions, raster, renderer):
        need(type(max_actions) is int and 2 * packet.epochs + 1 <= max_actions <= 100000,
             "Explicit sufficient action budget within the 100000-action implementation limit required")
        self.packet, self.max_actions, self.raster, self.renderer = packet, max_actions, raster, renderer
        self.actions, self.finished = 0, False
        self.answers, self.seen = {}, set()
        self.state = {"epoch": 0, "start_sample": 0, "stop_sample": 3000,
                      "gain_uv": 50, "channels": list(CHANNELS)}

    def epoch_id(self):
        return f'{self.packet.case}/{self.state["epoch"]:05d}'

    def handle(self, request):
        need(not self.finished and self.actions < self.max_actions, "Session closed or action budget exhausted")
        self.actions += 1
        fields = {"inspect": set(), "epoch": {"index"}, "window": {"start_sample", "stop_sample"},
                  "gain": {"microvolts_per_division"}, "channels": {"channels"},
                  "respond": {"epoch_id", "probabilities"}, "finish": set()}
        need(type(request) is dict and type(request.get("action")) is str, "Typed request required")
        action = request["action"]
        need(action in fields and set(request) == fields[action] | {"action"}, "Unknown action or fields")
        if action == "epoch":
            index = request["index"]
            need(type(index) is int and 0 <= index < self.packet.epochs, "Epoch outside current person")
            self.state.update(epoch=index, start_sample=index * 3000, stop_sample=(index + 1) * 3000)
        elif action == "window":
            start, stop = request["start_sample"], request["stop_sample"]
            need(type(start) is int and type(stop) is int and 0 <= start < stop <= self.packet.epochs * 3000
                 and 100 <= stop - start <= 6000, "Window must be 100–6000 samples within this complete person")
            self.state.update(start_sample=start, stop_sample=stop)
        elif action == "gain":
            gain = request["microvolts_per_division"]
            need(type(gain) is int and gain in GAINS, "Unsupported display gain")
            self.state["gain_uv"] = gain
        elif action == "channels":
            names = request["channels"]
            need(type(names) is list and names and names == [c for c in CHANNELS if c in names],
                 "Nonempty ordered channel subset required")
            self.state["channels"] = names[:]
        elif action == "respond":
            epoch = self.state["epoch"]
            need(request["epoch_id"] == self.epoch_id() and epoch in self.seen,
                 "Exact target and a previously rendered complete three-channel target interval required")
            need(epoch not in self.answers, "Only the first final response for each epoch is accepted")
            self.answers[epoch] = probabilities(request["probabilities"])
            return {"kind": "response_accepted", "epoch_id": self.epoch_id(), "completed_epochs": len(self.answers)}
        elif action == "finish":
            need(set(self.answers) == set(range(self.packet.epochs)), "Every whole-clock epoch requires a response")
            self.finished = True
            return {"kind": "complete", "case_id": self.packet.case, "epochs": self.packet.epochs}
        start, stop = self.state["start_sample"], self.state["stop_sample"]
        target = self.state["epoch"] * 3000
        clock = dict(zip(CLOCK, map(float, self.packet.clock[self.state["epoch"]])))
        png = self.renderer.render(self.epoch_id(), start, self.state["channels"],
                                   self.packet.samples(start, stop, self.state["channels"]),
                                   self.state["gain_uv"], clock, self.raster, target_start_sample=target)
        if start <= target and stop >= target + 3000 and self.state["channels"] == list(CHANNELS):
            self.seen.add(self.state["epoch"])
        state = dict(self.state, channels=self.state["channels"][:])
        return {"kind": "view", "mode": MODE, "epoch_id": self.epoch_id(), "state": state,
                "clock_features": clock, "sample_rate_hz": 100, "signal_units": "V", "display_units": "uV",
                "image": {"mime_type": "image/png", "base64": base64.b64encode(png).decode("ascii")}}


PROMPT = ("Score every 30-second epoch as W, N1, N2, N3 or R in that fixed probability order. "
          "Use only the typed waveform viewer. No code, raw-file access, retrieval, detector/model cache, "
          "training labels or human feedback is provided. Signals are EEG Fpz-Cz, EEG Pz-Oz and horizontal "
          "EOG at 100 Hz. Underlying samples remain calibrated volts without added filtering/resampling. "
          "Display gain converts volts to microvolt axes. The window is within the same complete person; "
          "future context and your own earlier responses are allowed. No between-person state is permitted. "
          "Navigate with epoch/index or window/start_sample/stop_sample; inspect, gain, channels, respond "
          "and finish are the only actions. Every target must first have its full three-channel 30-second "
          "view rendered. All epochs require one final five-probability response; no private score mask "
          "or labels are available. This is an already exposed development person, not a new holdout.")


def fresh_output(path):
    path = unlinked(path)
    need(not path.exists() and path.parent.is_dir() and not path.resolve().is_relative_to(ROOT.resolve()),
         "Fresh external output required")
    path.mkdir(mode=0o700)
    return path


def write_new(path, body):
    with Path(path).open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def serve(args):
    output = fresh_output(args.output)
    packet = session = None
    captured = None
    input_events = successful_actions = 0
    chain = None
    try:
        raster, _, renderer = dependencies()
        packet = Packet(args.packet, args.case)
        session = Session(packet, args.max_actions, raster, renderer)
        manifest = {"schema": "sleep-whole-person-viewer-session/v1", "mode": MODE, "case_id": args.case,
                    "epochs": packet.epochs, "max_actions": args.max_actions, "inputs": packet.pins,
                    "source": source_identity(), "runtime": runtime_identity(), "prompt": PROMPT}
        write_new(output / "manifest.json", encode(manifest))
        print(encode({"kind": "instructions", "prompt": PROMPT, "case_id": args.case,
                      "epochs": packet.epochs, "max_actions": args.max_actions}).decode(), end="", flush=True)
        chain = sha(encode(manifest))
        with (output / "actions.jsonl").open("xb") as log:
            while not session.finished:
                captured = None
                captured = sys.stdin.buffer.readline(MAX_REQUEST + 1)
                input_events += 1
                need(0 < len(captured) <= MAX_REQUEST and captured.endswith(b"\n"), "Complete bounded request required")
                request = decode(captured)
                response = session.handle(request)
                entry = {"ordinal": session.actions, "previous": chain, "request": request,
                         "response_sha256": sha(encode(response))}
                record_body = encode(entry)
                log.write(record_body)
                log.flush()
                chain = sha(record_body)
                successful_actions = session.actions
                print(encode(response).decode(), end="", flush=True)
        write_new(output / "completion.json", encode({"actions": session.actions, "last_sha256": chain,
                  "case_id": args.case, "epochs": packet.epochs, "mode": MODE}))
    except BaseException as exc:
        failure = {"schema": "sleep-viewer-failed-attempt/v1", "status": "incomplete",
                   "case_id": args.case, "mode": MODE, "error_type": type(exc).__name__,
                   "error": str(exc)[:1000], "successful_actions": successful_actions,
                   "handled_action_attempts": session.actions if session else 0,
                   "input_events_observed": input_events, "last_success_chain": chain,
                   "last_input_capture": None if captured is None else {
                       "bytes": len(captured), "sha256": sha(captured),
                       "base64": base64.b64encode(captured).decode("ascii"),
                       "possible_truncation": len(captured) == MAX_REQUEST + 1 and not captured.endswith(b"\n"),
                       "eof": captured == b""}}
        try:
            write_new(output / "failure.json", encode(failure))
        except OSError:
            # Outer operator stderr/exit capture remains necessary if storage fails.
            pass
        raise
    finally:
        if packet is not None:
            packet.close()


def bounded_body(path, cap):
    path = unlinked(path)
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap, "Bounded regular evidence required")
    with path.open("rb") as stream:
        body = stream.read(cap + 1)
        need(identity(before) == identity(os.fstat(stream.fileno())) == identity(path.stat()), "Evidence changed")
    need(len(body) <= cap, "Evidence cap exceeded")
    return body


def replay(session_dir, packet, raster, renderer):
    session_dir = unlinked(session_dir)
    need(not os.path.lexists(session_dir / "failure.json"), "Failed sessions cannot be collected")
    manifest = decode(bounded_body(session_dir / "manifest.json", 65536))
    expected = {"schema": "sleep-whole-person-viewer-session/v1", "mode": MODE, "case_id": packet.case,
                "epochs": packet.epochs, "max_actions": manifest.get("max_actions"), "inputs": packet.pins,
                "source": source_identity(), "runtime": runtime_identity(), "prompt": PROMPT}
    need(manifest == expected, "Session source/input/condition mismatch")
    session = Session(packet, manifest["max_actions"], raster, renderer)
    chain = sha(encode(manifest))
    body = bounded_body(session_dir / "actions.jsonl", 64 * 1024**2)
    need(body.endswith(b"\n"), "Truncated action log")
    for line in body.splitlines():
        need(0 < len(line) <= MAX_REQUEST + 1024, "Bounded action record required")
        row = decode(line)
        need(set(row) == {"ordinal", "previous", "request", "response_sha256"}
             and type(row["ordinal"]) is int and row["ordinal"] == session.actions + 1
             and row["previous"] == chain, "Incomplete/reordered action chain")
        response = session.handle(row["request"])
        need(sha(encode(response)) == row["response_sha256"], "Rendered or collected response changed")
        chain = sha(encode(row))
    need(session.finished, "Missing complete-person finish")
    completion = decode(bounded_body(session_dir / "completion.json", 4096))
    need(completion == {"actions": session.actions, "last_sha256": chain, "case_id": packet.case,
                        "epochs": packet.epochs, "mode": MODE}, "Completion mismatch")
    return session.answers, {"manifest_sha256": sha(encode(manifest)), "actions_sha256": sha(body),
                             "last_sha256": chain, "actions": session.actions}


def collect(args):
    import numpy as np
    output = fresh_output(args.output)
    raster, adapter, renderer = dependencies()
    arrays, receipts = {"class_order": np.asarray(CLASSES)}, {}
    for case, packet_root, session_root in zip(CASES, args.packets, args.sessions):
        packet = Packet(packet_root, case)
        try:
            answers, receipts[case] = replay(session_root, packet, raster, renderer)
            arrays[case + "__epoch_id"] = np.asarray([f"{case}/{i:05d}" for i in range(CASES[case])])
            arrays[case + "__probabilities"] = np.asarray([answers[i] for i in range(CASES[case])], dtype=np.float64)
        finally:
            packet.close()
    path = output / "predictions.npz"
    np.savez(path, **arrays)
    body = bounded_body(path, 4000000)
    pin = {"bytes": len(body), "sha256": sha(body)}
    spec = adapter.Specification(tuple(adapter.Case(case, count) for case, count in CASES.items()), ("YASA", "RF"))
    adapter.validate_submission(path, pin, spec)
    write_new(output / "collection.json", encode({"mode": MODE, "epochs": sum(CASES.values()),
              "submission": pin, "sessions": receipts, "source": source_identity(),
              "scope": "Source/packet/history replay and complete response validation only; no labels or model qualification."}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--case", choices=CASES, required=True)
    serve_parser.add_argument("--packet", type=Path, required=True)
    serve_parser.add_argument("--max-actions", type=int, required=True)
    serve_parser.add_argument("--output", type=Path, required=True)
    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("--packets", nargs=2, type=Path, required=True, metavar=("PERSON1", "PERSON2"))
    collect_parser.add_argument("--sessions", nargs=2, type=Path, required=True, metavar=("PERSON1", "PERSON2"))
    collect_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        (serve if args.action == "serve" else collect)(args)
    except (ValueError, OSError, KeyError, TypeError, EOFError) as exc:
        print(type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
