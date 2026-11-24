"""Operator-owned JSON-lines transport for the unchanged APCx typed viewer.

Only requests and replies belong on the participant channel. The episode path,
source root, and this process belong to a trusted host, not the participant.
This transport is not an operating-system sandbox or a model/provider client.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

VIEWER_BYTES = 13354
VIEWER_SHA256 = "d90831fc1dea330d861932b4a14a8aa347272dc7fb169e5477f2620c8b49dbfd"
MAX_EPISODE_BYTES = 2 * 1024**2
MAX_REQUEST_BYTES = 16384


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def decode(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonfinite JSON constant")

    return json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def read_episode(path):
    path = Path(path).expanduser().absolute()
    if ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("ordinary episode path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_EPISODE_BYTES:
            raise ValueError("bounded ordinary episode file")
        body = stream.read(MAX_EPISODE_BYTES + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if len(body) != before.st_size or identity(before) != identity(after):
        raise ValueError("stable complete episode file")
    return decode(body)


def load_viewer(source_root):
    path = Path(source_root) / "typed-count-viewer-v1" / "viewer.py"
    # Bound reads before executing the exact authenticated bytes.
    with path.open("rb") as stream:
        body = stream.read(VIEWER_BYTES + 1)
    if len(body) != VIEWER_BYTES or hashlib.sha256(body).hexdigest() != VIEWER_SHA256:
        raise ValueError("pinned typed viewer source")
    module = types.ModuleType("apcx_pinned_typed_viewer")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def send(output, value):
    output.write(canonical(value))
    output.flush()


def serve(session, incoming, outgoing):
    """One complete session; no owner reads, fits, or arbitrary execution."""
    while True:
        line = incoming.readline(MAX_REQUEST_BYTES + 1)
        if not line:
            send(outgoing, {"schema": "apcx-viewer-transport-error-v1", "code": "incomplete_eof"})
            return 2
        if len(line) > MAX_REQUEST_BYTES:
            send(outgoing, {"schema": "apcx-viewer-transport-error-v1", "code": "request_too_large"})
            return 2
        try:
            if not line.endswith(b"\n"):
                raise ValueError("newline-delimited request required")
            request = decode(line)
            reply = session.dispatch(request)
        except (ValueError, TypeError, OverflowError, RecursionError):
            # Do not reflect arbitrary request text or operator paths. Rejected
            # requests are replies, not accepted answers or successful results.
            send(outgoing, {"schema": "apcx-viewer-transport-error-v1", "code": "invalid_request"})
            continue
        send(outgoing, reply)
        if reply["schema"] == "apcx-viewer-finish-v1":
            return 0


def main(argv=None, *, incoming=None, outgoing=None, errors=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True)
    parser.add_argument("--episode-sha256", required=True,
                        help="operator's canonical episode SHA-256 from authenticated preparation")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="operator-only implementations directory; exact viewer/boundary pins still apply")
    args = parser.parse_args(argv)
    incoming = sys.stdin.buffer if incoming is None else incoming
    outgoing = sys.stdout.buffer if outgoing is None else outgoing
    errors = sys.stderr.buffer if errors is None else errors
    try:
        viewer = load_viewer(args.source_root)
        session = viewer.Session(read_episode(args.episode), args.episode_sha256,
                                 boundary_directory=args.source_root / "deposited-label")
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        send(errors, {"schema": "apcx-viewer-transport-error-v1", "code": "operator_input_refused"})
        return 2
    try:
        return serve(session, incoming, outgoing)
    except (OSError, BrokenPipeError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
