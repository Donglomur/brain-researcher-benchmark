"""Concrete local JSONL provider/tool session, for later isolated execution.

The model backend is an exact separately admitted executable, not implemented
or selected by this source delivery. This bridge implements the complete
transport, tool dispatch, usage limits and transcript custody; it makes no
network calls and cannot grant itself a scientific run.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from k4bench.custody import cleanup, terminal
from k4bench.protocol import Meter


def line(process, cap, deadline):
    """Bounded read of exactly one protocol frame, with a wall deadline."""
    buffer = bytearray()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while time.monotonic() < deadline:
            if selector.select(timeout=min(0.1, max(0, deadline - time.monotonic()))):
                chunk = os.read(process.stdout.fileno(), 1)
                if not chunk:
                    raise RuntimeError("provider/tool closed before protocol response")
                buffer.extend(chunk)
                if len(buffer) > cap:
                    raise RuntimeError("protocol response byte cap")
                if chunk == b"\n":
                    return json.loads(buffer)
        raise RuntimeError("provider/tool wall deadline")
    finally:
        selector.close()


def send(process, value):
    process.stdin.write(json.dumps(value, separators=(",", ":"), allow_nan=False).encode() + b"\n")
    process.stdin.flush()


def main():
    if len(sys.argv) != 2 or sys.argv[1] != "/run/request.json":
        raise ValueError("fixed request path")
    request_path = Path(sys.argv[1])
    if request_path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("provider request cap")
    request = json.loads(request_path.read_text())
    if request["transport"] != "isolated-local-jsonl-v1":
        raise ValueError("unsupported provider transport")
    backend = Path("/provider/backend")
    pin = request["backend_executable_pin"]
    if pin["path"] != str(backend) or backend.is_symlink() or backend.stat().st_size != pin["bytes"]:
        raise ValueError("backend immutable executable identity")
    if hashlib.sha256(backend.read_bytes()).hexdigest() != pin["sha256"]:
        raise ValueError("backend digest mismatch")
    caps = request["caps"]
    if not all(type(v) is int and v > 0 for v in caps.values()):
        raise ValueError("finite positive provider caps required")
    if request["backend_argv"][0] != str(backend) or any(not isinstance(x, str) for x in request["backend_argv"]):
        raise ValueError("fixed source-bound backend argv")
    deadline = time.monotonic() + caps["wall_seconds"]
    processes, transcript, stderr_streams = [], None, []
    usage, calls, final = 0, 0, None
    failure = None
    try:
        transcript = open("/output/provider-transcript.jsonl", "xb", buffering=0)
        def record(kind, value):
            body = json.dumps({"kind": kind, "value": value}, allow_nan=False).encode() + b"\n"
            if transcript.tell() + len(body) > caps["transcript_bytes"]:
                raise RuntimeError("transcript cap; complete previous frames retained")
            transcript.write(body)
        for args, error_file in ((request["backend_argv"], "/output/provider-stderr.log"),
                                 ([sys.executable, "-I", "/opt/k4bench/tool_worker.py", "/run/tool-caps.json"],
                                  "/output/tool-stderr.log")):
            stderr = open(error_file, "xb", buffering=0)
            stderr_streams.append(stderr)
            processes.append(subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                              stderr=stderr, start_new_session=True, bufsize=0))
        provider, tools = processes
        initialization = {"type": "initialize", "protocol": "kilosort4-provider-jsonl-v1",
                          "cell": request["cell"], "prompt": request["prompt"],
                          "packet_manifest": request["packet_manifest"],
                          "token_budget": caps["tokens"], "tool_budget": caps["tool_calls"]}
        record("provider-input", initialization)
        send(provider, initialization)
        seen = set()
        while final is None:
            frame = line(provider, caps["frame_bytes"], deadline)
            record("provider-output", frame)
            increment = frame.get("usage_increment_tokens")
            if type(increment) is not int or increment < 0:
                raise ValueError("every provider frame requires measured token increment")
            usage += increment
            if usage > caps["tokens"]:
                raise RuntimeError("provider token budget exceeded")
            if sum(Path(s.name).stat().st_size for s in stderr_streams) > caps["stderr_bytes"]:
                raise RuntimeError("provider/tool stderr cap")
            if frame["type"] == "tool_call":
                calls += 1
                if calls > caps["tool_calls"] or frame["id"] in seen:
                    raise RuntimeError("duplicate/excess tool request")
                seen.add(frame["id"])
                call = {"id": frame["id"], "tool": frame["tool"], "arguments": frame["arguments"]}
                send(tools, call)
                reply = line(tools, caps["frame_bytes"], deadline)
                if reply["id"] != call["id"]:
                    raise RuntimeError("tool response ID mismatch")
                record("tool-response", reply)
                send(provider, {"type": "tool_result", **reply})
            elif frame["type"] == "final":
                final = frame["submission"]
            else:
                raise ValueError("unsupported provider frame")
    except BaseException as error:
        failure = {"type": type(error).__name__, "message": str(error)}
    finally:
        base_receipt = {"schema": "kilosort4_provider_session_receipt_v2", "cell": request["cell"],
                        "reported_token_usage": usage, "token_counter_native_qualification_required": True,
                        "tool_calls": calls, "submission": final,
                        "provider_profile_sha256": request["provider_profile_sha256"],
                        "candidate_quality": None, "no_automatic_retry": True,
                        "separate_host_seal_required": True}
        result = finish_provider(Path("/output/PROVIDER_RECEIPT.json"), base_receipt,
                                 failure, processes, [transcript, *stderr_streams],
                                 Meter(0, caps["terminal_receipt_bytes"], 0))
    if result["status"] == "failed":
        raise SystemExit(1)


def finish_provider(path, base_receipt, original_failure, processes, streams, meter, killpg=None):
    """Actual provider finalizer, also exercised with inert cleanup failures."""
    termination = cleanup(processes, streams, killpg=killpg)
    failure = original_failure
    if termination["errors"] and failure is None:
        failure = {"type": "CleanupFailure", "message": "Provider termination or stream custody incomplete"}
    record = {**base_receipt, "status": "failed" if failure else "submission-produced",
              "failure": failure, "original_failure": original_failure,
              "cleanup": termination, "scientific_qualified": False}
    receipt = terminal(path, record, meter)
    return {**record, "status": "failed" if not receipt["written"] else record["status"],
            "terminal_receipt_written": receipt["written"], "terminal_receipt_pin": receipt["pin"],
            "terminal_receipt_error": receipt["error"]}



if __name__ == "__main__":
    main()
