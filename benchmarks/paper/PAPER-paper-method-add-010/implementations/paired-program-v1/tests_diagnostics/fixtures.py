"""Bounded local daemon observations for generated diagnostic regression inputs.

This fixture never calls Docker. Archive bytes come from the files written by
the real wrapper invoked through fixture_cli, not from canned artifact replies.
Importing this module does not create sockets, threads, or files.
"""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import tarfile
import threading
import time
from urllib.parse import parse_qs, urlsplit

LABEL = "org.neurobench.osl-program-owner"


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def exact(sock, count):
    parts = []
    while count:
        part = sock.recv(count)
        if not part:
            raise EOFError("Generated fixture message ended")
        parts.append(part)
        count -= len(part)
    return b"".join(parts)


def send(sock, value):
    raw = encoded(value)
    if len(raw) > 32768:
        raise ValueError("Bounded generated fixture reply")
    sock.sendall(struct.pack("!I", len(raw)) + raw)


def options(args, key):
    return [args[i + 1] for i, value in enumerate(args[:-1]) if value == key]


class FixtureDaemon:
    def __init__(self, socket_path, image, diagnostic_path, deadline, candidate_output):
        self.path, self.image = Path(socket_path), image
        self.diagnostic_path, self.deadline = Path(diagnostic_path), deadline
        self.candidate_output = Path(candidate_output)
        self.resources = {"container": {}, "volume": {}}
        self.commands, self.removals, self.wrapper_reports, self.errors = [], [], [], []
        self.archive_names = []
        self.inventory_calls = 0
        self.producer_id = None
        self.stop_event = threading.Event()
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.settimeout(.1)
        # A basename avoids platform-specific Unix socket path-length limits.
        # Both endpoints use this caller-owned directory for the connection.
        previous = Path.cwd()
        try:
            os.chdir(self.path.parent)
            self.listener.bind(self.path.name)
        finally:
            os.chdir(previous)
        os.chmod(self.path, 0o600)
        self.listener.listen(4)
        self.thread = threading.Thread(target=self.serve, name="generated-daemon-observations", daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=max(0, min(2, self.deadline - time.monotonic())))
        if self.thread.is_alive():
            raise RuntimeError("Generated fixture server did not close")
        self.listener.close()
        self.path.unlink()

    def serve(self):
        while not self.stop_event.is_set():
            if time.monotonic() >= self.deadline:
                self.errors.append("fixture_deadline")
                return
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            try:
                with connection:
                    connection.settimeout(2)
                    prefix = exact(connection, 4)
                    if prefix == b"GET ":
                        self.archive_response(connection, prefix)
                        continue
                    length = struct.unpack("!I", prefix)[0]
                    if not 0 < length <= 32768:
                        raise ValueError("Bounded generated message")
                    message = json.loads(exact(connection, length))
                    if message.get("kind") == "wrapper_exit":
                        code = message["exit_code"]
                        if type(code) is not int or code not in (0, 1):
                            raise ValueError("Actual wrapper outcome")
                        self.wrapper_reports.append(dict(message))
                        self.resources["container"][self.producer_id]["State"] = self.state("exited", code)
                        reply = {"acknowledged": True}
                    else:
                        if message.get("kind") != "docker":
                            raise ValueError("Generated daemon request")
                        reply = self.command(message["args"])
                    send(connection, reply)
            except BaseException as error:
                self.errors.append(type(error).__name__)

    @staticmethod
    def state(status, code=0):
        return {"Status": status, "Running": status == "running", "Dead": False,
                "Pid": 81001 if status == "running" else 0, "ExitCode": code, "OOMKilled": False}

    def files(self):
        names = sorted(p.name for p in self.candidate_output.iterdir())
        if names != ["OUTPUTS.json", "RESULT.json"]:
            raise ValueError("Only real wrapper outputs")
        rows = []
        for name in names:
            info = (self.candidate_output / name).lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= 4096:
                raise ValueError("Bounded real generated output")
            rows.append({"name": name, "bytes": info.st_size})
        return rows

    def command(self, args):
        if not isinstance(args, list) or len(args) < 2 or len(self.commands) >= 64:
            raise ValueError("Finite generated daemon command")
        if args[:2] == ["container", "exec"] and "inventory" in args:
            self.commands.append({"kind": "container", "operation": "exec", "attached": False})
            if self.producer_id in self.resources["container"]:
                raise ValueError("No archive before producer removal")
            holder = self.resources["container"][args[2]]
            owner = options(args, "--owner-token")[0]
            role = options(args, "--role")[0]
            if holder["Config"]["Labels"][LABEL] != owner:
                raise ValueError("Exact generated holder owner")
            rows = self.files()
            self.inventory_calls += 1
            value = {"schema": "osl_capture_inventory_v1", "owner": owner, "role": role,
                     "directories": [], "files": rows, "total_bytes": sum(r["bytes"] for r in rows)}
            return {"stdout": encoded(value).decode()}
        kind, operation = args[:2]
        self.commands.append({"kind": kind, "operation": operation, "attached": "--attach" in args})
        if kind == "image" and operation == "inspect":
            if args[2] != self.image:
                raise ValueError("Generated image identity")
            return {"stdout": encoded({"Id": self.image, "Config": {"Env": [], "Volumes": None}}).decode()}
        if kind not in self.resources:
            raise ValueError("Generated resource kind")
        items = self.resources[kind]
        if operation == "ls":
            selector = options(args, "--filter")[0]
            found = []
            for ident, value in items.items():
                labels = value["Labels"] if kind == "volume" else value["Config"]["Labels"]
                if selector.startswith("label="):
                    key, expected = selector[6:].split("=", 1)
                    matched = labels.get(key) == expected
                elif selector.startswith("name="):
                    matched = re.fullmatch(selector[5:], value["Name"]) is not None
                else:
                    raise ValueError("Generated exact inventory selector")
                if matched:
                    found.append(ident)
            return {"stdout": "".join(value + "\n" for value in found)}
        if operation == "create":
            if kind == "volume":
                name = args[-1]
                label_key, label_value = options(args, "--label")[0].split("=", 1)
                value = {"Name": name, "Driver": options(args, "--driver")[0],
                         "Labels": {label_key: label_value},
                         "Options": dict(entry.split("=", 1) for entry in options(args, "--opt"))}
                ident = name
            else:
                name = options(args, "--name")[0]
                ident = hashlib.sha256(("generated-container:" + name).encode()).hexdigest()
                value = self.container(args, name, ident)
                if name.endswith("-producer"):
                    self.producer_id = ident
            if ident in items:
                raise ValueError("Generated creation collision")
            items[ident] = value
            return {"stdout": ident + "\n"}
        ident = args[-1] if operation in ("inspect", "rm", "wait", "start", "kill") else args[2]
        if ident not in items:
            raise ValueError("Unknown generated resource identity")
        item = items[ident]
        if operation == "inspect":
            return {"stdout": encoded([deepcopy(item)]).decode()}
        if operation == "start":
            item["State"] = self.state("running")
            if "--attach" in args:
                if ident != self.producer_id:
                    raise ValueError("Only selected producer is attached")
                return {"run_wrapper": True}
            return {"stdout": ident + "\n"}
        if operation == "exec":
            if "ready" not in args:
                raise ValueError("No artifact admission on failing producer")
            return {"stdout": encoded({"ready": True}).decode()}
        if operation == "kill":
            item["State"] = self.state("exited", 137)
            return {"stdout": ident + "\n"}
        if operation == "wait":
            return {"stdout": str(item["State"]["ExitCode"]) + "\n"}
        if operation == "rm":
            self.removals.append({"kind": kind, "name": item["Name"],
                                  "private_diagnostic_already_present": self.diagnostic_path.is_file()})
            del items[ident]
            return {"stdout": ident + "\n"}
        raise ValueError("Unselected generated daemon operation")

    def container(self, args, name, ident):
        entry = args.index("--entrypoint")
        image = args[entry + 2]
        if image != self.image:
            raise ValueError("Generated exact create image")
        label_key, label_value = options(args, "--label")[0].split("=", 1)
        mounts = []
        for declaration in options(args, "--mount"):
            parts = declaration.split(",")
            values = dict(part.split("=", 1) for part in parts if "=" in part)
            row = {"Type": values["type"], "Destination": values["dst"], "RW": "readonly" not in parts}
            row["Name" if row["Type"] == "volume" else "Source"] = values["src"]
            mounts.append(row)
        cpu = options(args, "--cpus")[0].split(".")
        host = {"Memory": int(options(args, "--memory")[0]), "MemorySwap": int(options(args, "--memory-swap")[0]),
                "NanoCpus": int(cpu[0]) * 1000000000 + int(cpu[1]), "PidsLimit": int(options(args, "--pids-limit")[0]),
                "ShmSize": int(options(args, "--shm-size")[0]), "NetworkMode": options(args, "--network")[0],
                "ReadonlyRootfs": "--read-only" in args, "CgroupnsMode": options(args, "--cgroupns")[0],
                "LogConfig": {"Type": options(args, "--log-driver")[0]}, "IpcMode": options(args, "--ipc")[0],
                "PidMode": "", "Privileged": False, "CapAdd": [], "Devices": [], "DeviceRequests": [],
                "CapDrop": options(args, "--cap-drop"), "SecurityOpt": options(args, "--security-opt"),
                "RestartPolicy": {"Name": options(args, "--restart")[0]}, "AutoRemove": False, "Init": False,
                "Tmpfs": dict(value.split(":", 1) for value in options(args, "--tmpfs")), "Ulimits": []}
        for value in options(args, "--ulimit"):
            key, extent = value.split("=", 1)
            soft, hard = map(int, extent.split(":"))
            host["Ulimits"].append({"Name": key, "Soft": soft, "Hard": hard})
        return {"Id": ident, "Name": "/" + name, "Image": image, "State": self.state("created"),
                "Config": {"Image": image, "User": options(args, "--user")[0],
                           "Entrypoint": [args[entry + 1]], "Cmd": args[entry + 3:],
                           "WorkingDir": options(args, "--workdir")[0], "Env": options(args, "--env"),
                           "Labels": {label_key: label_value}}, "HostConfig": host, "Mounts": mounts}

    def archive_response(self, connection, prefix):
        header = bytearray(prefix)
        while not header.endswith(b"\r\n\r\n"):
            if len(header) >= 4096:
                raise ValueError("Bounded generated HTTP header")
            header.extend(exact(connection, 1))
        line = bytes(header).split(b"\r\n", 1)[0].decode("ascii")
        method, target, version = line.split(" ")
        parsed = urlsplit(target)
        parts = parsed.path.split("/")
        if (method != "GET" or version != "HTTP/1.1" or len(parts) != 5
                or parts[1:3] != ["v1.41", "containers"] or parts[4] != "archive"):
            raise ValueError("Exact generated archive route")
        holder = self.resources["container"].get(parts[3])
        if (holder is None or not holder["Name"].endswith("-holder")
                or self.producer_id in self.resources["container"]):
            raise ValueError("Only stopped producer output through selected holder")
        query = parse_qs(parsed.query, strict_parsing=True)
        if set(query) != {"path"} or len(query["path"]) != 1:
            raise ValueError("One exact archive path")
        name = query["path"][0]
        if name not in ("/capture/RESULT.json", "/capture/OUTPUTS.json"):
            raise ValueError("Only generated output members")
        name = name.rsplit("/", 1)[1]
        self.files()
        raw = (self.candidate_output / name).read_bytes()
        if len(raw) > 4096:
            raise ValueError("Bounded generated archive payload")
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            member = tarfile.TarInfo(name)
            member.size = len(raw)
            member.mode = 0o600
            archive.addfile(member, io.BytesIO(raw))
        body = buffer.getvalue()
        if len(body) > 16384 or name in self.archive_names:
            raise ValueError("Bounded once-only generated transfer")
        self.archive_names.append(name)
        response = (b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode()
                    + b"\r\nContent-Encoding: identity\r\nConnection: close\r\n\r\n")
        connection.sendall(response + body)
