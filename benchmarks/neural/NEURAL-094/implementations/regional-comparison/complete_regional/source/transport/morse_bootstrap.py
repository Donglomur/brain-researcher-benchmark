"""Trusted in-container stage entrypoint; candidate Python never runs on host.

Worker files and manifests are untrusted proposals. The host independently
captures/revalidates them after terminal cleanup before granting a fresh stage.
This module does not prove P0 compliance of arbitrary in-memory code.
"""
import hashlib
import importlib.util
import os
from pathlib import Path, PurePosixPath
import stat
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from morse_protocol import _decode_body, _check_value, encode_frame, FrameDecoder


class BootstrapError(ValueError):
    pass


def relative_path(value):
    if type(value) is not str or not value or "\\" in value or "\x00" in value:
        raise BootstrapError("invalid relative artifact path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts) or PurePosixPath(value).is_absolute():
        raise BootstrapError("unsafe relative artifact path")
    return value


def ordinary_file(root, relative):
    relative_path(relative)
    path = Path(root)
    if path.is_symlink() or not path.is_dir():
        raise BootstrapError("nonordinary artifact root")
    parts = relative.split("/")
    for name in parts[:-1]:
        path = path/name
        mode = path.lstat().st_mode
        if not stat.S_ISDIR(mode) or path.is_symlink():
            raise BootstrapError("nonordinary artifact parent")
    path = path/parts[-1]
    record = path.lstat()
    if not stat.S_ISREG(record.st_mode) or record.st_nlink != 1:
        raise BootstrapError("artifact must be singly linked regular file")
    return path


def file_record(root, relative):
    path = ordinary_file(root, relative)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise BootstrapError("artifact changed type")
        hashed, size = hashlib.sha256(), 0
        while True:
            data = os.read(fd, 65536)
            if not data:
                break
            hashed.update(data)
            size += len(data)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) or size != before.st_size:
            raise BootstrapError("artifact changed during read")
        return {"path": relative, "bytes": size, "sha256": hashed.hexdigest()}
    finally:
        os.close(fd)


def write_json(root, relative, value, limit):
    relative_path(relative)
    # Only trusted fixed flat manifest/prediction outputs use this writer.
    if "/" in relative:
        raise BootstrapError("trusted output name must be flat")
    # Bound the actual artifact, not an unrelated protocol wrapper.
    _check_value(value)
    import json
    body = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(body) > limit:
        raise BootstrapError("output file limit")
    fd = os.open(str(Path(root)/relative), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)


class ToolClient:
    def __init__(self, input_stream, output_stream, frame_bytes):
        self.input = input_stream
        self.output = output_stream
        self.limit = frame_bytes
        self.sequence = 0

    def generate(self, messages, max_output_tokens):
        request = {"seq": self.sequence, "tool": "model.generate",
                   "arguments": {"messages": messages, "max_output_tokens": max_output_tokens}}
        outgoing = memoryview(encode_frame(request, self.limit))
        while outgoing:
            written = self.output.write(outgoing)
            if written is None or written <= 0:
                raise BootstrapError("host request pipe made no progress")
            outgoing = outgoing[written:]
        self.output.flush()
        decoder = FrameDecoder(self.limit)
        # Read exactly one frame. No candidate-controlled URL, tool, phase,
        # session ID or host path is supplied through this client.
        header = bytearray()
        while len(header) < 4:
            part = self.input.read(4-len(header))
            if not part:
                raise BootstrapError("missing host response header")
            header.extend(part)
        header = bytes(header)
        decoder.feed(header)
        size = int.from_bytes(header, "big")
        remaining = size
        result = []
        while remaining:
            chunk = self.input.read(min(remaining, 65536))
            if not chunk:
                decoder.finish()
            remaining -= len(chunk)
            result.extend(decoder.feed(chunk))
        decoder.finish()
        if len(result) != 1 or set(result[0]) != {"seq", "ok", "result"} or result[0]["seq"] != self.sequence or result[0]["ok"] is not True:
            raise BootstrapError("invalid host response")
        self.sequence += 1
        return result[0]["result"]


def validate_context(context):
    if type(context) is not dict or set(context) != {"context_id", "mode", "phase", "entrypoint", "capsule_files", "payload"}:
        raise BootstrapError("invalid context schema")
    if context["mode"] not in ("frozen_program", "case_adaptive") or context["phase"] not in ("train", "query"):
        raise BootstrapError("invalid stage")
    if type(context["context_id"]) is not str or not context["context_id"] or type(context["payload"]) is not dict:
        raise BootstrapError("invalid public context")
    entrypoint = relative_path(context["entrypoint"])
    if "/" in entrypoint or not entrypoint.endswith(".py"):
        raise BootstrapError("entrypoint must be a flat Python filename")
    files = context["capsule_files"]
    if type(files) is not dict or entrypoint not in files or not files:
        raise BootstrapError("invalid capsule inventory")
    folded = set()
    for name, sha in files.items():
        relative_path(name)
        if name.casefold() in folded or type(sha) is not str or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise BootstrapError("invalid capsule file binding")
        folded.add(name.casefold())
    return context


def execute_stage(context, tools, *, capsule_root="/capsule", output_root="/output", file_bytes):
    """Called in-container. Alternate roots are for tiny invented controls only."""
    context = validate_context(context)
    for name, sha in context["capsule_files"].items():
        if file_record(capsule_root, name)["sha256"] != sha:
            raise BootstrapError("capsule content mismatch")
    # Parent freezes complete inventory; this checks it again in worker.
    observed = []
    for directory, dirs, files in os.walk(capsule_root, followlinks=False):
        for child in dirs:
            if Path(directory, child).is_symlink():
                raise BootstrapError("capsule symlink directory")
        for child in files:
            observed.append(str(Path(directory, child).relative_to(capsule_root)).replace(os.sep, "/"))
    if set(observed) != set(context["capsule_files"]):
        raise BootstrapError("capsule inventory changed")
    module_spec = importlib.util.spec_from_file_location("morse_candidate_entrypoint", str(Path(capsule_root)/context["entrypoint"]))
    module = importlib.util.module_from_spec(module_spec)
    sys.path.insert(0, str(capsule_root))
    try:
        module_spec.loader.exec_module(module)
        public = {"context_id": context["context_id"], "mode": context["mode"], "phase": context["phase"],
                  "payload": context["payload"], "paths": {"training": "/training", "output": "/output", "work": "/work",
                   "query": "/query" if context["phase"] == "query" else None,
                   "fit": "/fit" if context["phase"] == "query" else None}}
        if context["phase"] == "train":
            result = module.train(public, tools)
            if type(result) is not dict or set(result) != {"fit_files"} or type(result["fit_files"]) is not list:
                raise BootstrapError("invalid train return")
            names = result["fit_files"]
            if any(type(name) is not str for name in names) or len(set(name.casefold() for name in names)) != len(names) or "fit_manifest.json" in names:
                raise BootstrapError("invalid fitted inventory")
            records = [file_record(output_root, name) for name in names]
            write_json(output_root, "fit_manifest.json", {"context_id": context["context_id"], "files": records}, file_bytes)
        else:
            result = module.predict(public, tools)
            if type(result) is not list:
                raise BootstrapError("predict must return a list")
            write_json(output_root, "predictions.json", result, file_bytes)
    finally:
        sys.path.remove(str(capsule_root))


def main():
    if len(sys.argv) != 4 or sys.argv[1] != "/context/context.json":
        raise BootstrapError("fixed stage arguments required")
    file_bytes, frame_bytes = int(sys.argv[2]), int(sys.argv[3])
    if file_bytes <= 0 or not 1 <= frame_bytes <= 0xffffffff:
        raise BootstrapError("invalid explicit protocol limits")
    with open(sys.argv[1], "rb") as source:
        body = source.read(file_bytes+1)
    if len(body) > file_bytes:
        raise BootstrapError("context file limit")
    context = _decode_body(body)
    # Keep a dedicated protocol descriptor; normal candidate stdout is stderr.
    wire_out = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
    wire_in = os.fdopen(os.dup(sys.stdin.fileno()), "rb", buffering=0)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    tools = ToolClient(wire_in, wire_out, frame_bytes)
    try:
        execute_stage(context, tools, file_bytes=file_bytes)
    finally:
        wire_in.close()
        wire_out.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stderr.write("candidate stage failed\n")
        raise SystemExit(1)
