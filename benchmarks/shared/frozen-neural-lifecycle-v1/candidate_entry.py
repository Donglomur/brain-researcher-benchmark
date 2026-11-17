"""Child-only resource setup, then execution of the committed trusted programme."""
from pathlib import Path
import json
import os
import resource
import runpy
import sys


def main():
    script, request, output, receipt, memory, mode = sys.argv[1:]
    details = {"mode": mode, "platform": sys.platform, "memory_bytes": int(memory),
               "cpu_threads_environment": 2, "authoring_and_filesystem_security": "not_isolated"}
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 121))
        resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024**2, 2 * 1024**2))
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
        if mode == "hard":
            if sys.platform != "linux":
                raise RuntimeError("Hard RLIMIT_AS memory admission supported only on Linux; no candidate code executed")
            resource.setrlimit(resource.RLIMIT_AS, (int(memory), int(memory)))
            details["memory_enforcement"] = "RLIMIT_AS"
        elif mode == "generated":
            details["memory_enforcement"] = "generated tiny engineering process only; no hard-memory qualification"
        else:
            raise ValueError("Unknown resource mode")
        details["status"] = "admitted"
    except Exception as exc:
        details.update(status="resource_setup_failed", error=str(exc))
        Path(receipt).write_text(json.dumps(details, indent=2) + "\n")
        return 76
    Path(receipt).write_text(json.dumps(details, indent=2) + "\n")
    # No repository/site paths or inherited PYTHONPATH; method-local imports work.
    sys.path.insert(0, str(Path(script).parent))
    sys.argv = [script, "--request", request, "--output", output]
    runpy.run_path(script, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
