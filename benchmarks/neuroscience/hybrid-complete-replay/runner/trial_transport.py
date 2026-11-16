"""Hybrid-specific sequential trial adapter over an already qualified owner.

One new container per complete trial. Only the programme and frozen training
artifact are mounted; private cases, labels, Docker socket and evaluator never
enter its namespace. Inherited CLI children remain in the outer-owned group.
"""
import hashlib
import json
import os
import selectors
import subprocess
import time
from pathlib import Path
from consumer import ContractError, OnlineSession, decode_reply
from donor_checked_source import need, encode, exact
from episode_owner_base import Owner
from endpoint_guard import endpoint_identity


class TrialOwner(Owner):
    def operand_identity(self, programme, artifact, programme_pins, artifact_pin):
        programme = Path(programme); artifact = Path(artifact)
        self.cust.ordinary_path(programme); self.cust.ordinary_path(artifact)
        need(programme.is_dir() and {x.name for x in programme.iterdir()} == set(programme_pins), "complete public-only programme directory")
        used = 0
        for name, row in programme_pins.items():
            need(Path(name).name == name and name.endswith(".py"), "flat admitted participant programme")
            used += len(exact(programme / name, row, 1048576))
        need(used <= 1048576 and artifact_pin["bytes"] <= 65536, "declared first participant profile operands")
        used += len(exact(artifact, artifact_pin, 65536))
        return {"read_bytes": used, "programme_files": len(programme_pins), "model_sha256": artifact_pin["sha256"]}

    def exchange(self, cid, protocol, expected_count, seconds, response_seconds):
        """Bounded duplex attach: never enqueue another query before commitment."""
        endpoint_identity(self.plan)
        argv = self.plan["docker_prefix"] + ["start", "-a", "-i", cid]
        self.write("attach.intent.json", {"argv": argv, "attempts": 1, "expected_responses_private": expected_count})
        finish = min(self.deadline - 20, time.monotonic() + seconds)
        proc = None; selector = selectors.DefaultSelector(); issue = None; direct = None
        buffers = {"stdout": bytearray(), "stderr": bytearray()}; seen = {"stdout": 0, "stderr": 0}; eof = set()
        output_cap = (expected_count + 1) * 4097
        counts = {"queries": 0, "commits": 0}; qhash = hashlib.sha256(); rhash = hashlib.sha256()
        raw = {}; query_file = None; pending = None; wire = b""; pos = 0; ready = False; complete = False; ending = False
        horizon = finish
        try:
            need(os.getpid() == os.getpgrp(), "participant CLI inherits owned worker leader")
            for name in ("stdout", "stderr"):
                raw[name] = (self.root / ("attach." + name)).open("xb")
            query_file = (self.root / "queries.jsonl").open("xb")
            proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=False, env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": self.plan["operator_home"]})
            for label, pipe in (("stdout", proc.stdout), ("stderr", proc.stderr)):
                os.set_blocking(pipe.fileno(), False); selector.register(pipe, selectors.EVENT_READ, label)
            os.set_blocking(proc.stdin.fileno(), False)
            def next_query():
                nonlocal pending, wire, pos, horizon, complete, ready, ending
                pending = protocol.next_query()
                if pending is None:
                    # Explicit committed-trial termination avoids depending on
                    # daemon OpenStdin/StdinOnce EOF behavior. No future query,
                    # label or trial length is disclosed before the last commit.
                    ending = True; ready = False; wire = b'{"schema":"hybrid-trial-end-v1"}\n'; pos = 0
                    selector.register(proc.stdin, selectors.EVENT_WRITE, "stdin")
                    return
                wire = encode(pending); need(len(wire) <= 4096, "complete current query bound")
                pos = 0; ready = False; horizon = min(finish, time.monotonic() + response_seconds)
                counts["queries"] += 1; qhash.update(wire); query_file.write(wire)
                selector.register(proc.stdin, selectors.EVENT_WRITE, "stdin")
            next_query()
            while selector.get_map():
                need(not self.signals and time.monotonic() < min(finish, horizon), "whole trial/response deadline or interruption")
                for key, _ in selector.select(min(.05, max(0, min(finish, horizon) - time.monotonic()))):
                    label = key.data
                    if label == "stdin":
                        n = os.write(proc.stdin.fileno(), wire[pos:]); need(n > 0, "query write progress"); pos += n
                        if pos == len(wire):
                            selector.unregister(proc.stdin)
                            if ending:
                                complete = True; proc.stdin.close()
                            else:
                                ready = True
                        continue
                    b = os.read(key.fileobj.fileno(), 8192)
                    if not b:
                        eof.add(label); selector.unregister(key.fileobj)
                        if label == "stdout": need(complete, "participant EOF before complete trial")
                        continue
                    seen[label] += len(b)
                    cap = output_cap if label == "stdout" else 65536
                    previous = seen[label] - len(b); raw[label].write(b[:max(0, cap - previous)])
                    need(seen[label] <= cap, "complete participant output extent")
                    if label == "stderr":
                        continue
                    rhash.update(b); buffers[label].extend(b)
                    need(not complete and ready, "unsolicited output before a fully sent current query")
                    if b"\n" in buffers[label]:
                        line, rest = buffers[label].split(b"\n", 1)
                        need(not rest, "multiple replies ahead of commitment")
                        need(len(line) + 1 <= 4096, "participant reply record bound")
                        protocol.commit(decode_reply(bytes(line) + b"\n")); counts["commits"] += 1
                        buffers[label].clear(); next_query()
                    else:
                        need(len(buffers[label]) <= 4096, "unterminated oversized reply")
            need(complete and not buffers["stdout"], "complete committed transcript")
            need(counts["queries"] == counts["commits"] == expected_count, "all trial decisions committed")
            proc.wait(timeout=max(0, finish - time.monotonic())); need(proc.returncode == 0, "participant natural exit")
        except BaseException as exc:
            issue = {"type": type(exc).__name__, "reason": str(exc)[:1024]}
        finally:
            selector.close()
            if proc is not None:
                errors = []; sent = []
                for method in ("terminate", "kill"):
                    try:
                        if proc.poll() is None:
                            getattr(proc, method)(); sent.append(method); proc.wait(timeout=2)
                    except ProcessLookupError:
                        pass
                    except BaseException as exc:
                        errors.append({"method": method, "type": type(exc).__name__})
                direct = {"pid": proc.pid, "controller_pgid": os.getpgrp(), "reaped": proc.poll() is not None,
                          "exit_code": proc.poll(), "signals_sent": sent, "errors": errors}
                for pipe in (proc.stdin, proc.stdout, proc.stderr):
                    if pipe is not None: pipe.close()
            for f in raw.values(): f.close()
            if query_file is not None: query_file.close()
            after = None
            try: after = endpoint_identity(self.plan)
            except BaseException as exc: issue = issue or {"type": type(exc).__name__, "reason": "endpoint after attach: " + str(exc)}
            result = {"argv": argv, "issue": issue, "direct_child": direct, "counts": counts,
                "stream_bytes_at_least": seen, "EOF": sorted(eof), "query_sha256": qhash.hexdigest(),
                "received_stdout_sha256": rhash.hexdigest(), "endpoint_after": after,
                "complete": issue is None and direct is not None and direct["reaped"] and not direct["errors"] and not direct["signals_sent"]}
            self.write("attach.result.json", result)
        return result

    def run_trial(self, trial, programme, artifact, entry, programme_pins, artifact_pin, episode_index=0, secret=None):
        need(self.active is None and self.deadline - time.monotonic() >= 50, "one complete owned episode lifecycle")
        need(trial and len({(d.subject, d.session, d.trial) for d in trial}) == 1, "one full trial per fresh container")
        name = self.token + "-%02d" % episode_index
        user = "501:20"
        args = ["-i", "PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/tmp", "TMPDIR=/tmp", "LC_ALL=C.UTF-8",
                "/usr/local/bin/python3", "-I", "-S", "-B", "/program/" + entry, "/model/model.json"]
        binds = [(str(programme), "/program", False), (str(artifact), "/model/model.json", False)]
        intent = {"name": name, "owner": self.token, "image": self.plan["image"], "argv": args, "binds": binds, "attempts": 1}
        self.write("member-%02d.intent.json" % episode_index, intent)
        creation = self.lifecycle.begin(name); creation["journal_base"] = "member-%02d" % episode_index
        self.creations[name] = creation; self.active = {"name": name, "cid": None}
        error = None; clean = None; attach = None; predictions = None; before_operand = None; after_operand = None
        protocol = OnlineSession(trial, secret if secret is not None else os.urandom(32))
        try:
            need(entry in programme_pins, "admitted entry belongs to complete public programme")
            before_operand = self.operand_identity(programme, artifact, programme_pins, artifact_pin)
            need(self.inspect(name, absent=True) is None, "fresh owned episode name")
            create = ["create", "--name", name, "--label", "org.neurobench.owner=" + self.token,
                "--label", "hybrid.operation=" + self.plan["operation_token"], "--pull=never", "--platform=linux/arm64",
                "--network=none", "--memory=1g", "--memory-swap=1g", "--cpus=1", "--pids-limit=32",
                "--user", user, "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "--restart=no", "--log-driver=none", "--interactive", "--workdir=/tmp", "--hostname=participant",
                "--ipc=private", "--cgroupns=private",
                "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m", "--ulimit", "nofile=128:128"]
            for src, dst, _ in binds:
                self.cust.ordinary_path(src); create += ["--mount", "type=bind,src=" + src + ",dst=" + dst + ",readonly"]
            create += ["--entrypoint", "/usr/bin/env", self.plan["image"], *args]
            _, out, _, stdout_pin = self.call(create, creation=creation)
            cid = out.decode().strip(); need(len(cid) == 64 and all(c in "0123456789abcdef" for c in cid), "exact create ID")
            self.active["cid"] = cid; self.lifecycle.acknowledge(creation, cid, self.last_call_receipt, stdout_pin)
            try:
                self.write(creation["journal_base"] + ".creation.json", creation, 4096)
            except BaseException:
                creation["state"] = "acknowledgement_custody_unresolved"
                raise
            before = self.inspect(cid); self.owned(before, name, cid)
            expected_mounts = {(src, dst, writable) for src, dst, writable in binds}
            actual_mounts = {(m["Source"], m["Destination"], m["RW"]) for m in before["mounts"]}
            need(len(before["mounts"]) == 2 and actual_mounts == expected_mounts and all(m["Type"] == "bind" for m in before["mounts"]), "no private or unexpected mounts")
            need(before["network"] == "none" and before["readonly"] and before["memory"] == before["swap"] == 1024**3
                 and before["cpus"] == 10**9 and before["pids"] == 32 and before["user"] == user
                 and before["entrypoint"] == ["/usr/bin/env"] and before["args"] == args
                 and before["caps"] == ["ALL"] and before["security"] == ["no-new-privileges"]
                 and before["tmpfs"] == {"/tmp": "rw,noexec,nosuid,nodev,size=64m"}
                 and before["privileged"] is False and before["pid_mode"] == "" and before["ipc_mode"] == "private"
                 and before["cgroupns_mode"] == "private" and not before["devices"]
                 and before["restart"] == {"Name": "no", "MaximumRetryCount": 0}
                 and before["log_driver"] == "none" and before["workdir"] == "/tmp", "effective participant isolation")
            attach = self.exchange(cid, protocol, len(trial), self.plan["trial_seconds"], self.plan["response_seconds"])
            need(attach["complete"], "complete sequential participant exchange")
            after = self.inspect(cid); self.owned(after, name, cid)
            need(after["state"]["Status"] == "exited" and after["state"]["ExitCode"] == 0 and not after["state"]["OOMKilled"], "participant exited naturally")
            predictions = protocol.finished_predictions()
        except BaseException as exc:
            error = {"type": type(exc).__name__, "reason": str(exc)[:1024]}
        finally:
            if creation["state"] == "never_dispatched":
                try:
                    self.lifecycle.reject_before_dispatch(creation, str(error))
                    self.write(creation["journal_base"] + ".creation.json", creation, 4096)
                except BaseException as exc:
                    error = error or {"type": type(exc).__name__, "reason": "pre-dispatch custody: " + str(exc)}
            try: clean = self.cleanup(name, self.active["cid"], creation)
            except BaseException as exc: clean = {"absent": False, "errors": [{"type": type(exc).__name__, "reason": str(exc)}]}
            try:
                after_operand = self.operand_identity(programme, artifact, programme_pins, artifact_pin)
                need(before_operand == after_operand, "unchanged public programme/model operands")
            except BaseException as exc:
                error = error or {"type": type(exc).__name__, "reason": "operand closure: " + str(exc)}
            self.write("member-%02d.cleanup.json" % episode_index, clean); self.active = None
            result = {"name": name, "cid": creation.get("cid"), "error": error, "attach": attach,
                      "cleanup": clean, "complete": error is None and bool(clean["absent"]) and not clean["errors"],
                      "private_decision_count": len(trial), "trial_state_isolation": "new container and tmpfs",
                      "operand_before": before_operand, "operand_after": after_operand}
            self.write("TRIAL_RESULT.json", result)
        return result, predictions
