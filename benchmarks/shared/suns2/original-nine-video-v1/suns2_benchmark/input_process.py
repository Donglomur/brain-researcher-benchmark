"""Bounded stage process owner adapted from the reviewed SUNS2 reference wrapper.

Original wrapper SHA256 d5267491bff80080fc6bdbcd02d4b42f742d46cf5b2650515cd2c74ac8b36906.
Capture is now lossless base64; cleanup/selector behavior remains explicit.
"""
import argparse
import base64
import hashlib
import json
import os
import resource
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path

def cleanup_group(proc):
    evidence = {"child_pid": proc.pid, "owned_process_group_id": proc.pid,
                "signal_errors": [], "final_wait_error": None, "status": "signal_requests_completed"}
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try: os.killpg(proc.pid, sig)
        except ProcessLookupError: pass
        except PermissionError as denied: evidence["signal_errors"].append(f"{sig.name}: {denied}")
        try: proc.wait(timeout=2)
        except subprocess.TimeoutExpired as pending:
            if sig == signal.SIGKILL: evidence["final_wait_error"] = str(pending)
    if evidence["signal_errors"] or evidence["final_wait_error"]:
        evidence["status"] = "cleanup_unverified"
    return evidence

def run_child(command, cwd, seconds=55, capture_bytes=65536):
    if type(capture_bytes) is not int or not 1 <= capture_bytes <= 65536:
        raise ValueError("capture bound must be between1and65536B")
    started = time.monotonic()
    proc = None
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    observed = {"stdout": 0, "stderr": 0}
    capture_complete = True
    cleanup = None
    selector = selectors.DefaultSelector()
    error = None
    prior = {}
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"received signal {signum}")
    try:
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            prior[sig] = signal.signal(sig, interrupted)
        proc = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True, close_fds=True)
        for name, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            remaining_time = started + seconds - time.monotonic()
            if remaining_time <= 0:
                raise subprocess.TimeoutExpired(command, seconds)
            for key, _ in selector.select(min(0.05, remaining_time)):
                remaining_bytes = capture_bytes - sum(map(len, buffers.values()))
                data = os.read(key.fileobj.fileno(), min(8192, remaining_bytes + 1))
                if not data:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                observed[key.data] += len(data)
                buffers[key.data].extend(data[:remaining_bytes])
                if len(data) > remaining_bytes:
                    capture_complete = False
                    raise ValueError(f"combined stdout/stderr capture exceeded{capture_bytes}B; stopped at bounded prefix")
        remaining_time = started + seconds - time.monotonic()
        if remaining_time <= 0:
            raise subprocess.TimeoutExpired(command, seconds)
        proc.wait(timeout=remaining_time)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        capture_complete = False
        # Kill our group even if the leader exited but descendants retain pipes.
        if proc is not None:
            cleanup = cleanup_group(proc)
    finally:
        for key in list(selector.get_map().values()):
            selector.unregister(key.fileobj)
            key.fileobj.close()
        selector.close()
        for sig, handler in prior.items(): signal.signal(sig, handler)
    stdout, stderr = bytes(buffers["stdout"]), bytes(buffers["stderr"])
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    peak = int(peak if sys.platform == "darwin" else peak * 1024)
    status = "succeeded" if proc is not None and proc.returncode == 0 and error is None else "failed"
    if peak > 268435456:
        status, error = "failed", "Observed child peakRSS exceeded declared256MiB; notOS-hard-enforced"
    return {"status": status, "error": error, "returncode": proc.returncode if proc else None,
            "wall_seconds": time.monotonic() - started, "child_peak_RSS_bytes": peak,
            "RAM_enforcement": "preflight element/expansion bounds and observed peakRSS check; notOS-hard-limit",
            "stdout_base64": base64.b64encode(stdout).decode("ascii"),
            "stderr_base64": base64.b64encode(stderr).decode("ascii"),
            "stdout_captured_bytes": len(stdout), "stderr_captured_bytes": len(stderr),
            "stdout_observed_bytes": observed["stdout"], "stderr_observed_bytes": observed["stderr"],
            "capture_complete": capture_complete,
            "capture_limit_bytes": capture_bytes,
            "cleanup": cleanup,
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_sha256": hashlib.sha256(stderr).hexdigest()}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("acquire", "zip", "hdf5"))
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    args = parser.parse_args(argv)
    source_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(source_root))
    from suns2_benchmark.input_stage import bounded_json, verify_pin, authority, require
    profile = bounded_json(args.protocol, args.protocol_sha256)
    require(profile.get("schema") == "suns2-original-input-native-protocol/v1", "native protocol schema")
    for pin in profile["frozen_files"]:
        verify_pin(pin)
    admission = authority(profile, args.protocol, args.protocol_sha256, args.stage)
    configured = profile["stages"][args.stage]
    evidence = Path(profile["process_evidence"])
    evidence.mkdir(mode=0o700, exist_ok=True)
    require(not evidence.is_symlink() and evidence.is_dir(), "private process evidence directory required")
    receipt = evidence / (args.stage + "-process.json")
    require(not receipt.exists(), "process stage already attempted; no automatic retry")
    command = [part.replace("{protocol_sha256}", args.protocol_sha256)
               .replace("{protocol_path}", str(Path(args.protocol)))
               for part in configured["child_command"]]
    # The pinned outer watchdog is separately required by the native protocol.
    # Native child arguments are an argv list, never shell source.
    result = run_child(command, profile["source_directory"], configured["child_wall_seconds"],
                       configured["capture_bytes"])
    result.update(stage=args.stage, authority=admission, child_command=command,
                  capture_encoding="base64 of exact captured bytes",
                  resource_readiness="source preparation only; no model or benchmark readiness")
    encoded = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()
    if len(encoded) > 131072:
        raise ValueError("bounded process receipt exceeded131072B")
    with receipt.open("xb") as stream:
        stream.write(encoded)
    print(json.dumps({k: result[k] for k in ("stage", "status", "wall_seconds", "child_peak_RSS_bytes", "error")}))
    return 0 if result["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
