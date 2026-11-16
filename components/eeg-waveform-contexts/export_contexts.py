"""Export the fixed NEURAL-077 waveform contexts, without model or target access.

Only the five pinned public packet members are opened. Numerical waveform text
is never parsed or reserialized. This is preparation, not an inference runner.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

PINS = {
    "queries.jsonl": (14521484, "1a34369834d022d0dc332293b6cd120df006195855c08087697bcdd823b1f126"),
    "demonstrations.json": (129921, "19e4018216376af334fd5ead21e2c33d5761d9d56ce5c76d3a89411483906ed2"),
    "prompt.txt": (1703, "2ecc6656d099083f2d87112147430aa1f780c714ce31579e025c69ac74ec77a0"),
    "response_schema.json": (480, "bd0c92c7016a20b039fbb273aad8802be1da088b0f1fec3e15fac0a1070eed12"),
    "manifest.json": (18502, "edb93d2e6003e90afb54f8f62a97ceccd6088c59ba4fba1e4a2fb780c6bf9dc8"),
}
QUERY_LIMIT = 128 * 1024
CONTEXT_LIMIT = 256 * 1024
OUTPUT_LIMIT = 128 * 1024 * 1024
PATTERN = re.compile(rb'^\{"trial_id":"(development-00[12]-[0-9a-f]{24})","channels":')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(stream):
    info = os.fstat(stream.fileno())
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def open_member(root, name):
    # O_NONBLOCK avoids blocking if a substituted special file is encountered.
    descriptor = os.open(root / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode), "Packet members must be ordinary files")
        require(info.st_size == PINS[name][0], "Packet member size mismatch: " + name)
        stream = os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise
    return stream


def read_text(stream, name):
    before = identity(stream)
    raw = stream.read(PINS[name][0] + 1)
    require((len(raw), hashlib.sha256(raw).hexdigest()) == PINS[name],
            "Packet member digest mismatch: " + name)
    require(identity(stream) == before, "Packet member changed while read: " + name)
    return raw.decode("utf-8")


def queries(stream):
    """One complete bounded pass; validation completes only at iterator exhaustion."""
    before = identity(stream)
    digest = hashlib.sha256()
    count = size = 0
    previous = ""
    populations = {"development-001-": 0, "development-002-": 0}
    while True:
        line = stream.readline(QUERY_LIMIT + 1)
        if not line:
            break
        require(0 < len(line) <= QUERY_LIMIT and line.endswith(b"\n"),
                "Complete bounded query line required; never truncate")
        digest.update(line)
        size += len(line)
        count += 1
        require(count <= 400, "More than 400 queries")
        match = PATTERN.match(line)
        require(match is not None, "Unexpected query serialization or identity")
        identifier = match.group(1).decode("ascii")
        require(identifier > previous, "Query identities must be unique and sorted")
        previous = identifier
        populations[identifier[:16]] += 1
        yield identifier, line.decode("utf-8")
    require(count == 400 and set(populations.values()) == {200}, "All 400 queries, 200 per person, required")
    require((size, digest.hexdigest()) == PINS["queries.jsonl"], "Complete query digest mismatch")
    require(identity(stream) == before, "Query file changed while read")


def record_bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def export_contexts(packet, output):
    """Write one fresh export directory; errors retain a partial directory."""
    packet, output = Path(packet), Path(output)
    require(stat.S_ISDIR(packet.lstat().st_mode), "Packet root must be an ordinary directory")
    with ExitStack() as stack:
        opened = {name: stack.enter_context(open_member(packet, name)) for name in PINS}
        text = {name: read_text(stream, name) for name, stream in opened.items() if name != "queries.jsonl"}
        ids = [identifier for identifier, _ in queries(opened["queries.jsonl"])]
        manifest = json.loads(text["manifest.json"])
        require(manifest["development_ids"] == ids and manifest["query_count"] == 400,
                "Manifest and complete query ordering must agree")
        require(manifest["demonstration_count"] == 4 and manifest["natural_class_prior_supplied"] is False,
                "The original four-demo no-numerical-prior condition is required")
        prompt = text["prompt.txt"]
        require(prompt.count("{{demonstrations_json}}") == prompt.count("{{query_json}}") == 1,
                "Exactly one of each original prompt slot required")
        # Split the template before inserting any data. Inserted text is never
        # recursively substituted, parsed as numbers, or normalized.
        before_demo, after_demo = prompt.split("{{demonstrations_json}}")
        require("{{query_json}}" not in before_demo, "Original template slot order required")
        before_query, after_query = after_demo.split("{{query_json}}")
        prefix = before_demo + text["demonstrations.json"] + before_query
        opened["queries.jsonl"].seek(0)
        output.mkdir(mode=0o700, parents=False, exist_ok=False)
        digest, written = hashlib.sha256(), 0
        count = 0
        with (output / "contexts.jsonl").open("xb") as destination:
            for count, (identifier, query) in enumerate(queries(opened["queries.jsonl"]), 1):
                require(identifier == ids[count - 1], "Query ordering changed between passes")
                context = prefix + query + after_query
                require(len(context.encode("utf-8")) <= CONTEXT_LIMIT, "Complete context exceeds bound; never truncate")
                raw = record_bytes({"ordinal": count - 1, "trial_id": identifier, "prompt": context})
                require(written + len(raw) <= OUTPUT_LIMIT, "Complete export exceeds output bound")
                destination.write(raw)
                digest.update(raw)
                written += len(raw)
            destination.flush()
            os.fsync(destination.fileno())
        require(count == 400, "No incomplete collection may complete")
        receipt = {
            "schema": "neural077_complete_waveform_context_export_v1",
            "task_id": "NEURAL-077", "status": "contexts_exported_no_inference",
            "contexts": 400, "demonstrations_per_context": 4,
            "natural_class_prior_supplied": False,
            "output": {"path": "contexts.jsonl", "bytes": written, "sha256": digest.hexdigest()},
            "inputs": {name: {"bytes": size, "sha256": sha} for name, (size, sha) in PINS.items()},
            "query_passes": 2,
            "explicit_packet_bytes_read": sum(size for size, _ in PINS.values()) + PINS["queries.jsonl"][0],
            "model_calls": 0, "private_target_reads": 0,
            "transport_isolation_qualified": False, "model_context_fit_qualified": False,
            "scientific_result": False, "new_benchmark_ids": 0,
        }
        raw = record_bytes(receipt)
        with (output / ".complete.tmp").open("xb") as destination:
            destination.write(raw)
            destination.flush()
            os.fsync(destination.fileno())
        os.link(output / ".complete.tmp", output / "COMPLETE.json")
        (output / ".complete.tmp").unlink()
        return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path, help="Existing exact five-member public packet")
    parser.add_argument("--output", required=True, type=Path, help="Fresh directory in a trusted parent")
    args = parser.parse_args(argv)
    try:
        receipt = export_contexts(args.packet, args.output)
    except (ValueError, OSError, UnicodeError, KeyError, TypeError) as error:
        print("Context export refused: " + str(error), file=sys.stderr)
        return 2
    print(json.dumps(receipt, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
