"""Local JSONL tool endpoint inside the qualified candidate container only.

Outer runtime enforces the whole authoring resource envelope. These per-call
limits supplement it; this endpoint is not a host sandbox and must never be
launched directly on private host paths.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def safe_path(name, writable=False):
    root = Path("/output/work") if writable else Path("/input")
    p = Path(name)
    if p.is_absolute() or not p.parts or any(x in {".", ".."} for x in p.parts):
        raise ValueError("relative packet/work path required")
    target = root / p
    if any(x.is_symlink() for x in [target, *target.parents]):
        raise ValueError("symlink forbidden")
    return target


def execute(call, caps, ordinal):
    tool, args = call["tool"], call["arguments"]
    if tool == "read_text":
        path = safe_path(args["path"])
        if path.stat().st_size > caps["max_read_bytes"]:
            raise ValueError("read cap")
        body = path.read_bytes()
        return {"text": body.decode("utf-8"), "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest()}
    if tool == "write_text":
        path = safe_path(args["path"], writable=True)
        body = args["text"].encode("utf-8")
        if len(body) > caps["max_write_bytes"]:
            raise ValueError("write cap")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Distinct source revisions have distinct files. Never erase an attempt.
        with path.open("xb") as stream:
            stream.write(body)
        return {"path": args["path"], "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    if tool == "list_files":
        root = safe_path(args["path"])
        result = []
        for path in sorted(root.iterdir()):
            if len(result) >= caps["max_listing_entries"]:
                raise ValueError("listing cap")
            if not path.is_symlink():
                result.append({"name": path.name, "directory": path.is_dir(),
                               "bytes": None if path.is_dir() else path.stat().st_size})
        return {"entries": result}
    if tool == "run_python":
        script = safe_path(args["path"], writable=True)
        if not script.is_file() or script.suffix != ".py":
            raise ValueError("written Python source required")
        run = Path("/output") / f"tool-run-{ordinal:06}"
        run.mkdir(exist_ok=False)
        log = run / "combined.log"
        start = time.monotonic()
        with log.open("xb") as stream:
            process = subprocess.Popen([sys.executable, "-I", str(script)], cwd=run,
                                       stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                                       start_new_session=True)
            failure = None
            while process.poll() is None:
                if time.monotonic() - start > caps["max_wall_seconds"] or log.stat().st_size > caps["max_log_bytes"]:
                    failure = "tool resource limit; failed output retained"
                    os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(0.02)
            code = process.wait(timeout=2)
        return {"exit_code": code, "failure": failure, "log_path": str(log),
                "log_bytes": log.stat().st_size, "wall_seconds": time.monotonic() - start,
                "scientific_result": None, "no_automatic_retry": True}
    raise ValueError("unknown tool")


def main():
    if sys.argv != [sys.argv[0], "/run/tool-caps.json"]:
        raise ValueError("fixed in-container cap path required")
    caps = json.loads(Path(sys.argv[1]).read_text())
    if not all(type(v) is int and v > 0 for v in caps.values()):
        raise ValueError("finite positive caps required")
    Path("/output/work").mkdir(exist_ok=False)
    seen = set()
    transcript = Path("/output/tool-transcript.jsonl").open("x")
    for ordinal in range(caps["max_calls"]):
        line = sys.stdin.buffer.readline(caps["max_request_bytes"] + 1)
        if not line:
            break
        if len(line) > caps["max_request_bytes"]:
            raise ValueError("request byte cap")
        call = json.loads(line)
        if call["id"] in seen:
            raise ValueError("duplicate tool request ID")
        seen.add(call["id"])
        try:
            result = {"id": call["id"], "status": "ok", "result": execute(call, caps, ordinal)}
        except BaseException as error:
            result = {"id": call["id"], "status": "failed", "error": type(error).__name__, "detail": str(error)}
        transcript.write(json.dumps({"request": call, "response": result}, allow_nan=False) + "\n")
        transcript.flush()
        print(json.dumps(result, allow_nan=False), flush=True)
    transcript.close()


if __name__ == "__main__":
    main()
