"""Local generated daemon client that invokes the pinned production wrapper.

The caller supplies a launcher using its own Python executable and a bounded
configuration file. Importing this module does not read configuration or run it.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import struct
import sys
import types


def message(endpoint, value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(raw) > 32768:
        raise ValueError("Bounded generated command")
    previous = Path.cwd()
    try:
        os.chdir(endpoint.parent)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(2)
            connection.connect(endpoint.name)
            connection.sendall(struct.pack("!I", len(raw)) + raw)

            def exact(count):
                parts = []
                while count:
                    part = connection.recv(count)
                    if not part:
                        raise EOFError("Generated response ended")
                    parts.append(part)
                    count -= len(part)
                return b"".join(parts)

            length = struct.unpack("!I", exact(4))[0]
            if not 0 < length <= 32768:
                raise ValueError("Bounded generated reply")
            return json.loads(exact(length))
    finally:
        os.chdir(previous)


def main():
    signal.alarm(5)
    path = Path(os.environ["MEG_DIAGNOSTIC_FIXTURE_CONFIG"])
    raw = path.read_bytes()
    if len(raw) > 8192:
        raise ValueError("Bounded generated fixture configuration")
    config = json.loads(raw)
    endpoint = Path(config["socket"])
    if sys.argv[1:3] != ["--host", "unix://" + str(endpoint)]:
        raise ValueError("Exact generated endpoint")
    reply = message(endpoint, {"kind": "docker", "args": sys.argv[3:]})
    if not reply.get("run_wrapper"):
        sys.stdout.write(reply["stdout"])
        return 0
    wrapper = Path(config["wrapper_source"])
    source = wrapper.read_bytes()
    if {"bytes": len(source), "sha256": hashlib.sha256(source).hexdigest()} != config["wrapper_pin"]:
        raise ValueError("Unchanged actual wrapper source")
    module = types.ModuleType("actual_wrapper_in_generated_producer")
    module.__file__ = str(wrapper)
    exec(compile(source, str(wrapper), "exec"), module.__dict__)
    code, error_type = 0, None
    try:
        module.main(_generated=config["wrapper_paths"])
    except SystemExit as error:
        if type(error.code) is not int or error.code not in (0, 1):
            raise
        code, error_type = error.code, "SystemExit"
    acknowledged = message(endpoint, {"kind": "wrapper_exit", "exit_code": code,
                                       "error_type": error_type, "actual_main_called": True})
    if acknowledged != {"acknowledged": True}:
        raise ValueError("Observed wrapper exit report")
    sys.stdout.flush()
    sys.stderr.flush()
    signal.alarm(0)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
