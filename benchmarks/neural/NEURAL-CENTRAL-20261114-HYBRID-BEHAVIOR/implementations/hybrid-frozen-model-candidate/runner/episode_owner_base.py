"""One owned container at a time, exact image and mounts, complete bounded IO.

The request/cleanup shape reuses the accepted Horrocks/PFC owner design.
The process-group closer is copied verbatim from the accepted manifest caller.
This adaptation is independently reviewed as a whole; no inherited acceptance.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import time
from endpoint_guard import endpoint_identity

DOCKER = "/usr/local/bin/docker"
FMT = ('{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Image}},'
       '"state":{{json .State}},"memory":{{json .HostConfig.Memory}},'
       '"swap":{{json .HostConfig.MemorySwap}},"cpus":{{json .HostConfig.NanoCpus}},'
       '"network":{{json .HostConfig.NetworkMode}},"readonly":{{json .HostConfig.ReadonlyRootfs}},'
       '"mounts":{{json .Mounts}},"pids":{{json .HostConfig.PidsLimit}},'
       '"owner":{{json (index .Config.Labels "org.neurobench.owner")}},'
       '"tmpfs":{{json .HostConfig.Tmpfs}},"caps":{{json .HostConfig.CapDrop}},'
       '"security":{{json .HostConfig.SecurityOpt}},"args":{{json .Config.Cmd}},'
       '"entrypoint":{{json .Config.Entrypoint}},"user":{{json .Config.User}},'
       '"privileged":{{json .HostConfig.Privileged}},"pid_mode":{{json .HostConfig.PidMode}},'
       '"ipc_mode":{{json .HostConfig.IpcMode}},"cgroupns_mode":{{json .HostConfig.CgroupnsMode}},'
       '"devices":{{json .HostConfig.Devices}},"restart":{{json .HostConfig.RestartPolicy}},'
       '"log_driver":{{json .HostConfig.LogConfig.Type}},"workdir":{{json .Config.WorkingDir}}}')


class Owner:
    def __init__(self, cust, closer, root, source, plan, lock_sha, deadline, signals, token,
                 lifecycle=None, cli_group_mode="controller"):
        self.cust, self.closer, self.root, self.source = cust, closer, root, source
        self.plan, self.lock_sha, self.deadline, self.signals, self.token = plan, lock_sha, deadline, signals, token
        self.calls, self.bytes, self.received = 0, 0, 0
        self.active = None
        self.cleanups = []
        self.runtime_fingerprint = None
        self.lifecycle, self.cli_group_mode = lifecycle, cli_group_mode
        self.creations, self.last_call_receipt = {}, None
        self.cli_closures = []

    def write(self, name, obj, cap=65536):
        body = self.cust.encode(obj)
        self.cust.need(self.bytes + len(body) <= 4*1024**2, "whole owner retention cap")
        self.cust.write_new(self.root / name, body, cap)
        self.bytes += len(body)
        return {"name": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

    def call(self, args, seconds=10, cleanup=False, stdout_cap=65536, allowed=(0,), creation=None):
        self.calls += 1
        self.cust.need(self.calls <= 16, "finite complete command count")
        stem = "call-%03d" % self.calls
        endpoint_identity(self.plan)
        argv = self.plan["docker_prefix"] + args
        self.write(stem+".intent.json", {"argv": argv, "cleanup": cleanup, "attempts": 1})
        deadline = min(self.deadline if cleanup else self.deadline-20, time.monotonic()+seconds)
        closure_deadline = min(self.deadline, deadline+10)
        proc, selector, issue, closure = None, selectors.DefaultSelector(), None, None
        streams = {"stdout": bytearray(), "stderr": bytearray()}
        caps = {"stdout": stdout_cap, "stderr": 65536}
        received = {"stdout": 0, "stderr": 0}
        eof = {"stdout": False, "stderr": False}
        started = time.monotonic()
        try:
            self.cust.need(started < deadline and (cleanup or not self.signals), "original command horizon/signal")
            self.cust.need(self.cli_group_mode in ("separate", "controller"), "explicit CLI ownership mode")
            self.cust.need(self.cli_group_mode == "separate" or os.getpid() == os.getpgrp(),
                           "controller CLI inherits separately owned controller session")
            if creation is not None:
                self.lifecycle.mark_dispatch(creation, self.calls)
                self.write(creation["journal_base"]+".dispatch.json", creation, 4096)
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=self.cli_group_mode == "separate",
                env={"HOME": self.plan["operator_home"], "PATH": "/usr/local/bin:/usr/bin:/bin"})
            for label, f in (("stdout", proc.stdout), ("stderr", proc.stderr)):
                os.set_blocking(f.fileno(), False)
                selector.register(f, selectors.EVENT_READ, label)
            while selector.get_map():
                self.cust.need(time.monotonic() < deadline and (cleanup or not self.signals), "command horizon/signal")
                for key, _ in selector.select(min(0.1, max(0, deadline-time.monotonic()))):
                    label = key.data
                    b = os.read(key.fileobj.fileno(), min(8192, caps[label]-len(streams[label])+1))
                    if not b:
                        eof[label] = True
                        selector.unregister(key.fileobj)
                        continue
                    received[label] += len(b); self.received += len(b)
                    left = caps[label]-len(streams[label])
                    streams[label].extend(b[:left])
                    self.cust.need(len(b) <= left, "complete command stream cap")
            proc.wait(timeout=max(0, deadline-time.monotonic()))
        except BaseException as exc:
            issue = {"type": type(exc).__name__, "reason": str(exc)[:1024]}
        finally:
            selector.close()
            if proc is not None:
                if self.cli_group_mode == "separate":
                    closure = self.closer.close_owned_group(proc, closure_deadline)
                # CLI stays in the owner process group. The outer owns that
                # complete group, including any unexpected CLI descendants.
                # Locally close and reap this direct child without signalling
                # a fictitious process group whose number happens to be its PID.
                else:
                    errors, sent = [], []
                    for method in ("terminate", "kill"):
                        try:
                            if proc.poll() is None:
                                getattr(proc, method)(); sent.append(method)
                                proc.wait(timeout=max(0, min(2, closure_deadline-time.monotonic())))
                        except ProcessLookupError:
                            pass
                        except BaseException as exc:
                            errors.append({"stage": method, "type": type(exc).__name__})
                    code = proc.poll()
                    closure = {"exit_code": code, "reaped": code is not None,
                               "controller_process_group": os.getpgrp(), "errors": errors,
                               "signals_sent": sent}
                for f in (proc.stdout, proc.stderr):
                    if f is not None:
                        f.close()
        rows = []
        for label, b in streams.items():
            name = stem+"."+label
            self.cust.need(self.bytes + len(b) <= 4*1024**2, "whole captured retention cap")
            self.cust.write_new(self.root / name, b, caps[label]); self.bytes += len(b)
            rows.append({"name": name, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
                         "received_bytes": received[label], "complete": issue is None})
        result = {"argv": argv, "seconds": time.monotonic()-started, "issue": issue,
                  "closure": closure, "streams": rows, "no_retry": True,
                  "stdout_eof": eof["stdout"], "stderr_eof": eof["stderr"],
                  "cli_group_mode": self.cli_group_mode, "original_command_deadline": deadline,
                  "original_command_cleanup_deadline": closure_deadline}
        self.last_call_receipt = self.write(stem+".result.json", result)
        endpoint_identity(self.plan)
        self.cli_closures.append({"cli_group_mode": self.cli_group_mode, "closure": closure,
            "issue": issue, "stdout_eof": eof["stdout"], "stderr_eof": eof["stderr"]})
        self.cust.need(issue is None and closure is not None and closure["exit_code"] in allowed and
            closure["reaped"] and not closure["errors"] and
            not closure["signals_sent"] and all(eof.values()) and
            (self.cli_group_mode == "controller" or closure["process_group_absent"]), "natural complete Docker CLI closure")
        return closure["exit_code"], bytes(streams["stdout"]), bytes(streams["stderr"]), rows[0]

    def inspect(self, ident, absent=False, cleanup=False):
        rc, out, err, _ = self.call(["inspect", "--type=container", "--format", FMT, ident],
                                  seconds=5, cleanup=cleanup, allowed=(0, 1) if absent else (0,))
        if rc == 1:
            self.cust.need(absent and b"no such" in err.lower() and ident.encode() in err,
                           "exact absence distinguished from daemon failure")
            return None
        return self.cust.strict(out)

    def owned(self, info, name, cid=None):
        i = info["id"]
        self.cust.need(len(i) == 64 and all(c in "0123456789abcdef" for c in i) and
            info["image"] == self.plan["image"] and info["owner"] == self.token and
            info["name"] == "/"+name and (cid is None or i == cid), "exact owned container identity")
        return i

    def cleanup(self, name, cid=None, creation=None):
        # Each observation survives prior errors; uncertain identity never
        # authorizes a deletion. Absence is an observation, not an exit-code guess.
        result = {"name": name, "cid": cid, "errors": [], "removed": False, "absent": False}
        info = None
        try:
            info = self.inspect(cid or name, absent=True, cleanup=True)
            if info is not None:
                cid = self.owned(info, name, cid)
                result["observed_state"] = info["state"]
                result["cid"] = cid
            else:
                result["initially_absent"] = True
        except BaseException as exc:
            result["errors"].append({"stage": "identify", "type": type(exc).__name__, "reason": str(exc)[:512]})
        if info is not None and cid is not None and not result["errors"]:
            try:
                _, out, _, _ = self.call(["rm", "-f", "-v", cid], seconds=5, cleanup=True)
                self.cust.need(out.decode().strip() == cid, "owned removal acknowledgement")
                result["removed"] = True
            except BaseException as exc:
                result["errors"].append({"stage": "remove", "type": type(exc).__name__, "reason": str(exc)[:512]})
        observations = []
        for identity in ([cid, name] if cid else [name]):
            try:
                observations.append(self.inspect(identity, absent=True, cleanup=True) is None)
            except BaseException as exc:
                observations.append(False)
                result["errors"].append({"stage": "absence", "identity": identity, "type": type(exc).__name__, "reason": str(exc)[:512]})
        observed = bool(observations) and all(observations)
        record = creation or self.creations.get(name) or {"state": "dispatched_completion_unresolved"}
        result.update(self.lifecycle.closure(record, observed, result["errors"]))
        self.cleanups.append(result)
        return result

