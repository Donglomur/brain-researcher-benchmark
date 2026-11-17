"""Fixed trusted Docker metadata commands using the captured bounded process owner."""
import base64
import hashlib
import os
from pathlib import Path
import threading
import time
from .schema import canonical, require, save
from .host_support import process
from .host_process import capture, plain_json

_LOCK = threading.Lock()


class DockerCommands:
    def __init__(self, runtime, private, budget, deadline):
        self.runtime, self.private, self.budget, self.deadline = runtime, Path(private), budget, deadline
        self.rows = []
        self.config = self.private / "docker-config"
        self.config.mkdir(mode=0o700)
        self.executable_identity = None

    def admit_executable(self):
        d = self.runtime["docker"]
        raw = capture(d["path"], d["bytes"], self.budget)
        require(len(raw) == d["bytes"] and hashlib.sha256(raw).hexdigest() == d["sha256"]
                and os.access(d["path"], os.X_OK), "exact selected Docker executable")
        s = Path(d["path"]).lstat()
        self.executable_identity = (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

    def run(self, args, *, cleanup=False):
        require(threading.current_thread() is threading.main_thread(), "dedicated main-thread supervisor")
        require(type(args) is list and args and args[0] in {"info", "image", "ps", "inspect", "rm", "network"},
                "closed metadata/recovery command family")
        require(all(type(x) is str and "\0" not in x for x in args), "literal trusted Docker argv")
        require(self.executable_identity is not None, "admitted Docker executable")
        s = Path(self.runtime["docker"]["path"]).lstat()
        require((s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                == self.executable_identity, "same Docker executable")
        self.budget.charge()
        now = time.monotonic()
        normal_end = min(now + self.runtime["command_seconds"],
                         self.deadline - self.runtime["command_seconds"])
        require(now < normal_end < self.deadline, "remaining fixed metadata and cleanup horizons")
        cap = self.runtime["metadata_output_bytes"]
        argv = [self.runtime["docker"]["path"], "--config", str(self.config),
                "--host", self.runtime["docker_host"], *args]
        self.budget.charge(read=cap + 1, write=4 * (cap + 1) + 6 * len(canonical(argv)) + 8192)
        row = {"ordinal": len(self.rows), "argv": argv, "process": None, "streams": None,
               "error_type": None, "cleanup_phase": cleanup}
        self.rows.append(row)
        streams = {}
        original_os, original_cap = process.os, process.CAP
        failure = None

        class OSProxy:
            def __getattr__(self, name):
                return getattr(original_os, name)

            def read(self, descriptor, extent):
                body = original_os.read(descriptor, extent)
                require(descriptor in streams or len(streams) < 2, "two actual CLI stream descriptors")
                streams.setdefault(descriptor, bytearray()).extend(body)
                # The complete cap-plus-probe envelope was charged before spawn.
                require(sum(len(v) for v in streams.values()) <= cap + 1, "actual reserved CLI stream extent")
                return body

        with _LOCK:
            process.os, process.CAP = OSProxy(), cap
            try:
                output, record = process.run(argv, normal_end, self.deadline,
                                             {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
                row["process"] = record
                row["stdout"] = {"bytes": len(output), "sha256": hashlib.sha256(output).hexdigest()}
                return output
            except BaseException as error:
                failure = error
                row["error_type"] = type(error).__name__
                if hasattr(error, "record"):
                    row["process"] = error.record
                raise
            finally:
                process.os, process.CAP = original_os, original_cap
                row["streams"] = {str(fd): {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                                             "base64": base64.b64encode(body).decode("ascii")}
                                  for fd, body in streams.items()}
                try:
                    row["receipt"] = {"path": str(self.private / f"DOCKER-{row['ordinal']:03d}.json"),
                                      **save(self.private / f"DOCKER-{row['ordinal']:03d}.json",
                                             row, self.budget, cap=self.runtime["journal_bytes"])}
                except BaseException as publication:
                    row["publication_failure"] = type(publication).__name__
                    if failure is None:
                        raise
                    failure.add_note("Docker receipt publication failed: " + type(publication).__name__)

    def preflight(self, project):
        daemon = plain_json(self.run(["info", "--format", "{{json .}}"]))
        require(daemon["ID"] == self.runtime["daemon_id"] and daemon["OSType"] == "linux"
                and daemon["CgroupVersion"] == "2" and daemon["CgroupDriver"] == "cgroupfs",
                "selected actual local cgroup-v2 daemon")
        require(not any("rootless" in x or "userns" in x for x in daemon.get("SecurityOptions", [])),
                "selected rootful identity mapping")
        image_rows = plain_json(self.run(["image", "inspect", self.runtime["image"]]))
        require(type(image_rows) is list and len(image_rows) == 1, "one selected cached image")
        image = image_rows[0]
        require(image["Id"] == self.runtime["image"] and image["Os"] == "linux"
                and image["Architecture"] == self.runtime["architecture"]
                and (image["Config"].get("Env") or []) == self.runtime["image_env"]
                and not image["Config"].get("Volumes")
                and (not image["Config"].get("Healthcheck") or
                     image["Config"]["Healthcheck"].get("Test") == ["NONE"]),
                "selected cached image without implicit producers")
        for kind in ("containers", "networks"):
            args = ["ps", "-aq", "--no-trunc"] if kind == "containers" else ["network", "ls", "-q"]
            raw = self.run(args + ["--filter", "label=com.docker.compose.project=" + project])
            require(not raw.strip(), "fresh unowned project before any child activation")
        return {"daemon": daemon, "image": image, "project": project,
                "command_receipts": [x["receipt"] for x in self.rows]}

    def retire(self, project):
        """Actual exact-project recovery, after the owned host actor has stopped."""
        raw = self.run(["ps", "-aq", "--no-trunc", "--filter",
                        "label=com.docker.compose.project=" + project], cleanup=True)
        ids = raw.decode("ascii").split()
        require(len(ids) <= 1, "at most one selected main-service container")
        retired = []
        for cid in ids:
            require(len(cid) == 64 and all(x in "0123456789abcdef" for x in cid), "full container ID")
            value = plain_json(self.run(["inspect", cid], cleanup=True))
            require(type(value) is list and len(value) == 1, "one owned recovery inspection")
            x = value[0]
            require(x["Id"] == cid and x["Image"] == self.runtime["image"]
                    and x["Config"]["Labels"]["com.docker.compose.project"] == project
                    and x["Config"]["Labels"]["com.docker.compose.service"] == "main",
                    "exact original project/image/service recovery")
            self.run(["rm", "-f", cid], cleanup=True)  # No --volumes; output custody remains.
            retired.append({"container_id": cid, "original_inspection": x})
        absent = self.run(["ps", "-aq", "--no-trunc", "--filter",
                           "label=com.docker.compose.project=" + project], cleanup=True)
        networks = self.run(["network", "ls", "-q", "--filter",
                             "label=com.docker.compose.project=" + project], cleanup=True)
        require(not absent.strip() and not networks.strip(), "actual full owned project absent")
        return {"schema": "tms_figure2b_docker_absence_v1", "project": project,
                "retired": retired, "containers_stdout": absent.decode("ascii"),
                "networks_stdout": networks.decode("ascii"),
                "command_receipts": [r["receipt"] for r in self.rows]}
