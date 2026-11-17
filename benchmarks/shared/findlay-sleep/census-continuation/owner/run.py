"""Single selected Findlay no-download census continuation worker under the current durable V4 owner.

No native parser is imported in this module. The selection is the caller-supplied
request digest; source locks are identities and never execution authorization.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import types

sys.dont_write_bytecode = True
PROFILE = {"work_seconds": 180, "recovery_seconds": 60, "whole_seconds": 240,
           "worker_cpu": [160, 165], "host_memory_planning_bytes": 536870912,
           "runtime_read_cap": 201326592}
OWNER_ROOT = "benchmarks/shared/program-execution/ownership-v4/"
OWNER_PINS = {
    "process_owner.py": {"bytes": 6707, "sha256": "b9e8f366f4b639a87e6c7c580e4bceff228c031cd767a4a3bebe37ea85d496ea"},
    "group_bootstrap.py": {"bytes": 2562, "sha256": "45626b0c7c29ffedb8881260f08099d6d3c9441cf46ddeb8c694e3658067bda9"},
    "trusted_controller.py": {"bytes": 2119, "sha256": "c6b144d400f2e5fff154753d1e2e16ee2fb3e216186ac4dfb2f7fd24a3269234"},
}
META_CAP = 8 * 1024 * 1024
SOURCE_CAP = 2 * 1024 * 1024
DATA_RECEIPT_CAP = 8 * 1024 * 1024
RUNTIME_MANIFEST_CAP = 2 * 1024 * 1024


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def decode(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique, parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def sha(body):
    return hashlib.sha256(body).hexdigest()


def absolute(value):
    need(type(value) is str, "Absolute path string")
    p = Path(value)
    need(p.is_absolute() and ".." not in p.parts and str(p) == value, "Canonical absolute path")
    return p


def relpath(value):
    need(type(value) is str and re.fullmatch(r"[A-Za-z0-9_+./-]+", value)
         and not value.startswith("/") and all(p not in ("", ".", "..") for p in value.split("/")),
         "Canonical selected relative source path")
    return value


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def capture(path, cap):
    p = absolute(str(path))
    need(not any(x.is_symlink() for x in (p, *p.parents)), "Unlinked selected file")
    before = p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
         "Bounded ordinary selected file")
    fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        need(identity(os.fstat(fd)) == identity(before), "Opened selected file identity")
        body = bytearray()
        while True:
            data = os.read(fd, min(65536, cap + 1 - len(body)))
            if not data:
                break
            body.extend(data)
            need(len(body) <= cap, "Complete selected body cap")
        need(identity(os.fstat(fd)) == identity(before), "Selected file stable during read")
    finally:
        os.close(fd)
    need(identity(p.lstat()) == identity(before) and len(body) == before.st_size, "Stable complete selected file")
    return bytes(body)


def checked(pin, cap=262144):
    need(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}
         and type(pin["bytes"]) is int and 0 < pin["bytes"] <= cap
         and type(pin["sha256"]) is str and re.fullmatch("[a-f0-9]{64}", pin["sha256"]), "Exact file pin")
    body = capture(absolute(pin["path"]), cap)
    need(len(body) == pin["bytes"] and sha(body) == pin["sha256"], "Selected file pin mismatch")
    return body


def write(path, value):
    body = canonical(value); need(len(body) <= RUNTIME_MANIFEST_CAP, "Operator metadata member cap")
    path = Path(path)
    with path.open("xb") as f:
        f.write(body); f.flush(); os.fsync(f.fileno())
    os.chmod(path, 0o400)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"path": str(path), "bytes": len(body), "sha256": sha(body)}


def load_request(path, expected_sha256, with_bytes=False):
    body = capture(absolute(str(path)), 131072)
    need(type(expected_sha256) is str and re.fullmatch("[a-f0-9]{64}", expected_sha256)
         and sha(body) == expected_sha256, "Exact selected request")
    value = decode(body)
    need(type(value) is dict and set(value) == {"schema", "execution", "task"}
         and value["schema"] in ("findlay-portable-census-continuation-request/v1",
                              "findlay-portable-first-intake-request/v1"), "Exact Findlay request")
    ex = value["execution"]
    need(type(ex) is dict and set(ex) == {"repository_root", "output_root", "source_lock",
         "runtime_manifest", "source_adoption", "profile"} and ex["profile"] == PROFILE, "Fixed execution profile")
    root, output = absolute(ex["repository_root"]), absolute(ex["output_root"])
    need(output.is_relative_to(root / "artifacts-build") and output != root / "artifacts-build",
         "Private selected artifacts-build output")
    ad = ex["source_adoption"]
    need(type(ad) is dict and set(ad) == {"commit", "worker"}
         and type(ad["commit"]) is str and re.fullmatch("[a-f0-9]{40}", ad["commit"]), "Selected adopted commit")
    task = value["task"]
    input_field = ("original_archive" if value["schema"] == "findlay-portable-first-intake-request/v1" else "prior_attempt")
    need(type(task) is dict and set(task) == {"input_ledger", "published_families", "data_read_cap", "worker_output_cap", input_field, "private_policy"}
         and task["data_read_cap"] == 33554432 and task["worker_output_cap"] == 33554432, "Fixed complete-census-continuation task")
    checked_prior = task[input_field]
    need(type(checked_prior) is dict and set(checked_prior) == {"path", "bytes", "sha256"}, "Exact selected input descriptor")
    selected_input = absolute(checked_prior["path"])
    if input_field == "original_archive":
        need(not selected_input.is_relative_to(root), "Original archive remains outside checkout")
    for field in ("input_ledger", "published_families", "private_policy"):
        pin = task[field]
        need(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "Selected task pin")
        absolute(pin["path"])
        need(not Path(pin["path"]).is_relative_to(root), "Private metadata stays outside checkout")
    return (value, len(body)) if with_bytes else value


def source_members(files):
    need(type(files) is dict and 5 <= len(files) <= 128, "Finite complete source graph")
    for name, pin in files.items():
        relpath(name)
        need(name.endswith(".py"), "Software-only source graph; private metadata is separately admitted")
        need(type(pin) is dict and set(pin) == {"bytes", "sha256"}
             and type(pin["bytes"]) is int and 0 < pin["bytes"] <= 262144
             and type(pin["sha256"]) is str and re.fullmatch("[a-f0-9]{64}", pin["sha256"]),
             "Exact source-member content pin; locators belong to graph keys")
    need(sum(pin["bytes"] for pin in files.values()) <= SOURCE_CAP, "Source closure size ceiling")
    return files


def source_lock(request, with_bytes=False):
    ex = request["execution"]
    body = checked(ex["source_lock"])
    value = decode(body)
    need(type(value) is dict and set(value) == {"schema", "repository_root", "execution_authority",
         "entrypoint", "worker", "files"} and value["schema"] == "findlay-intake-source-lock/v1"
         and value["repository_root"] == ex["repository_root"] and value["execution_authority"] is False,
         "Exact nonauthorizing source lock")
    source_members(value["files"])
    need(value["worker"] == ex["source_adoption"]["worker"], "Selected worker descriptor")
    for name, pin in OWNER_PINS.items():
        need(value["files"].get(OWNER_ROOT + name) == pin, "Selected current V4 owner source")
    for field in ("entrypoint", "worker"):
        pin = value[field]
        need(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}
             and type(pin["bytes"]) is int, "Exact selected source-role descriptor")
        relpath(pin["path"])
        need(value["files"].get(pin["path"]) == {k: pin[k] for k in ("bytes", "sha256")},
             "Entrypoint and worker are exact graph members")
    need(Path(__file__).absolute() == Path(ex["repository_root"]) / value["entrypoint"]["path"],
         "Exact selected runner location")
    return (value, len(body)) if with_bytes else value


def source_capture(request, lock, deadline, adopted=False):
    root = Path(request["execution"]["repository_root"])
    result = {}; read_bytes = 0
    for relative, pin in sorted(source_members(lock["files"]).items()):
        need(time.monotonic() < deadline, "Source verification original deadline")
        relpath(relative)
        body = checked({"path": str(root / relative), "bytes": pin["bytes"], "sha256": pin["sha256"]})
        read_bytes += len(body); result[relative] = body
        if adopted:
            spec = request["execution"]["source_adoption"]["commit"] + ":" + relative
            for args, limit in ((["-s", spec], 32), (["blob", spec], pin["bytes"])):
                response = subprocess.run(["/usr/bin/git", "-C", str(root), "cat-file", *args],
                                          capture_output=True, timeout=min(5, max(.001, deadline-time.monotonic())),
                                          env={"PATH": "/usr/bin:/bin", "HOME": str(root), "LC_ALL": "C",
                                               "GIT_CONFIG_NOSYSTEM": "1", "GIT_OPTIONAL_LOCKS": "0"})
                need(response.returncode == 0 and len(response.stderr) <= 2048
                     and len(response.stdout) <= limit, "Complete adopted source object")
                if args[0] == "-s":
                    need(response.stdout.strip() == str(pin["bytes"]).encode(), "Adopted blob exact size")
                else:
                    read_bytes += len(response.stdout)
                    need(response.stdout == body, "Adopted and working source bytes agree")
    # Only software bodies above are joined to the selected Git commit.
    contract_path = lock["worker"]["path"].rsplit("/", 1)[0] + "/external_contract.py"
    need(contract_path in result, "Private-contract validator in admitted software graph")
    contract = module(root / contract_path, result[contract_path], "_findlay_private_contract")
    metadata = {}
    for field in ("input_ledger", "published_families", "private_policy"):
        need(time.monotonic() < deadline, "Private metadata original deadline")
        pin = request["task"][field]
        body = checked(pin)
        metadata[field] = contract.authenticate(field, body)
        need(time.monotonic() < deadline, "Private metadata original deadline")
        result[pin["path"]] = body
        read_bytes += len(body)
    contract.join(metadata)
    if "original_archive" in request["task"]:
        contract.validate_archive_pin(request["task"]["original_archive"])
    return result, read_bytes


def module(path, body, name, injected=None):
    item = types.ModuleType(name); item.__file__ = str(path)
    item.__dict__.update(injected or {})
    exec(compile(body, str(path), "exec"), item.__dict__)
    return item


def runtime_module(request, captured):
    root = Path(request["execution"]["repository_root"])
    relative = str((Path(__file__).absolute().parent / "runtime_manifest.py").relative_to(root))
    need(relative in captured, "Runtime verifier is an admitted source member")
    return module(root / relative, captured[relative], "_findlay_admitted_runtime_manifest")


def owner_module(request, captured):
    root = Path(request["execution"]["repository_root"])
    trusted = module(root / (OWNER_ROOT + "trusted_controller.py"),
                     captured[OWNER_ROOT + "trusted_controller.py"], "_findlay_trusted_controller")
    saved = sys.modules.get("trusted_controller")
    need(saved is None or getattr(saved, "__file__", None) == trusted.__file__, "Canonical trusted-controller namespace")
    sys.modules["trusted_controller"] = trusted
    try:
        return module(root / (OWNER_ROOT + "process_owner.py"),
                      captured[OWNER_ROOT + "process_owner.py"], "_findlay_process_owner")
    finally:
        if saved is None:
            del sys.modules["trusted_controller"]
        else:
            sys.modules["trusted_controller"] = saved


def worker_admission(path, expected_sha256):
    """Worker-side complete source/receipt/interpreter joins before native import."""
    request, request_bytes = load_request(path, expected_sha256, with_bytes=True)
    ex = request["execution"]; out = Path(ex["output_root"])
    owner_body = capture(out / "owner_intent.json", 16384); owner = decode(owner_body)
    need(owner["schema"] == "findlay-owner-intent/v1" and owner["request_sha256"] == expected_sha256
         and owner["source_lock_sha256"] == ex["source_lock"]["sha256"]
         and owner["runtime_manifest_sha256"] == ex["runtime_manifest"]["sha256"]
         and owner["profile"] == PROFILE and owner["output_root"] == str(out),
         "Original owner request/source/runtime/deadline joins")
    need(owner["work_deadline"] == owner["started_monotonic"] + 180
         and owner["whole_deadline"] == owner["started_monotonic"] + 240
         and time.monotonic() < owner["work_deadline"], "Unreset original worker deadline")
    verified_body = capture(out / "runtime_verified.json", 131072); verified = decode(verified_body)
    need(verified["schema"] == "findlay-runtime-verified/v1" and verified["verified"] is True
         and verified["request_sha256"] == expected_sha256
         and verified["source_lock_sha256"] == ex["source_lock"]["sha256"]
         and verified["runtime_manifest_sha256"] == ex["runtime_manifest"]["sha256"]
         and verified["owner_intent_sha256"] == sha(owner_body), "Pre-GET runtime verification joins")
    source_body = capture(out / "source_verified.json", 131072); sources = decode(source_body)
    need(sources["schema"] == "findlay-source-verified/v1" and sources["verified"] is True
         and sources["request_sha256"] == expected_sha256
         and sources["source_lock_sha256"] == ex["source_lock"]["sha256"]
         and sources["commit"] == ex["source_adoption"]["commit"], "Adopted source receipt")
    lock, lock_bytes = source_lock(request, with_bytes=True)
    captured, source_bytes = source_capture(request, lock, owner["work_deadline"])
    rt = runtime_module(request, captured)
    manifest_body = checked(ex["runtime_manifest"], RUNTIME_MANIFEST_CAP); manifest = decode(manifest_body)
    # This is a small interpreter-only join; the full package pass is the outer receipt.
    reader = rt.Reader(deadline=owner["work_deadline"])
    observation = rt.verify_python(manifest["python"], reader)
    need(observation == verified["runtime"]["python"], "Same physical executing interpreter")
    return {"request": request, "work_deadline": owner["work_deadline"],
            "whole_deadline": owner["whole_deadline"], "output_root": str(out),
            "source_capture": captured, "runtime_manifest": manifest, "runtime_module": rt,
            "python_observation": observation, "source_read_bytes": source_bytes,
            "runtime_join_read_bytes": reader.bytes,
            "receipt_read_bytes": request_bytes + lock_bytes + sum(map(len, (owner_body, verified_body, source_body, manifest_body)))}


def parse_rss(body, leader, caller):
    need(len(body) <= 16384, "Complete bounded ps stdout")
    rows = []; seen = set()
    for line in body.splitlines():
        fields = line.split()
        need(len(fields) == 3 and all(x.isdigit() for x in fields), "Strict numeric ps rows")
        pid, pgid, kib = map(int, fields)
        need(pid > 1 and pid not in seen and (pid == caller or pgid == leader)
             and 0 <= kib <= 2**40, "Exact owned-group/caller RSS selection")
        rows.append({"pid": pid, "pgid": pgid, "rss_bytes": kib * 1024}); seen.add(pid)
    need(1 <= len(rows) <= 64 and caller in seen, "Complete bounded caller/group RSS rows")
    return {"rows": rows, "sampled_aggregate_bytes": sum(r["rss_bytes"] for r in rows),
            "continuous_hard_RSS_limit": False,
            "unmeasured": "Transient metadata-probe process and between-sample peaks"}


def sample_rss(leader, deadline):
    before = time.monotonic()
    result = subprocess.run(["/bin/ps", "-ww", "-g", str(leader), "-p", str(os.getpid()),
                             "-o", "pid=", "-o", "pgid=", "-o", "rss="],
                            capture_output=True, timeout=min(.4, max(.001, deadline-before)),
                            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "COMMAND_MODE": "unix2003"})
    need(result.returncode == 0 and len(result.stderr) <= 1024, "RSS inspection completed")
    row = parse_rss(result.stdout, leader, os.getpid())
    row.update(started_monotonic=before, ended_monotonic=time.monotonic(),
               original_stdout=result.stdout.decode("ascii"), original_stderr=result.stderr.decode("ascii"))
    return row


class LogTail:
    def __init__(self, proc, streams):
        self.proc, self.streams = proc, streams
    @property
    def returncode(self):
        return self.proc.returncode
    def communicate(self, timeout):
        out, err = self.proc.communicate(timeout=timeout)
        for name, data in (("stdout", out), ("stderr", err)):
            need(len(self.streams[name]) + len(data) <= 262144, "Original log retention bound")
            self.streams[name].extend(data)
        return out, err


def monitor(proc, owner, folder, out, deadline, whole_deadline):
    """Bounded pipes and sampled RSS; cleanup always uses the original owner."""
    selector = selectors.DefaultSelector()
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    rows_bytes = 0; samples = 0; peak = 0; completion = None; error = None; clean = None
    for name in streams:
        stream = getattr(proc, name); os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)
    sample_path = out / "rss_samples.jsonl"
    try:
        with sample_path.open("xb") as samples_file:
            next_sample = 0
            try:
                while True:
                    now = time.monotonic()
                    need(now < deadline, "Original work deadline expired")
                    if now >= next_sample:
                        row = sample_rss(proc.pid, deadline); body = canonical(row)
                        need(rows_bytes + len(body) <= 1048576, "Complete sampled RSS receipt cap")
                        samples_file.write(body); samples_file.flush()
                        rows_bytes += len(body); samples += 1
                        peak = max(peak, row["sampled_aggregate_bytes"])
                        need(peak <= PROFILE["host_memory_planning_bytes"], "Sampled aggregate host memory exceeded")
                        next_sample = now + .5
                    for key, _ in selector.select(min(.05, max(0, deadline-time.monotonic()))):
                        data = os.read(key.fileobj.fileno(), 8192)
                        if not data:
                            selector.unregister(key.fileobj); continue
                        streams[key.data].extend(data)
                        need(len(streams[key.data]) <= 65536, "Worker log limit exceeded")
                    if (folder / "process_completion.json").exists():
                        completion = owner.read(folder / "process_completion.json")
                        journal = owner.read(folder / "process_owner.json")
                        need(completion["token"] == journal["token"]
                             and completion["group_leader_waits_for_owner_stop"] is True
                             and type(completion["returncode"]) is int, "Natural worker completion identity")
                        need(time.monotonic() < deadline, "Natural worker exit observed before original work deadline")
                        break
                    need(proc.poll() is None, "Bootstrap exited before natural worker completion")
            except BaseException as exc:
                error = type(exc).__name__ + ": " + str(exc)
            finally:
                samples_file.flush(); os.fsync(samples_file.fileno())
    finally:
        selector.close()
        # The work clock is never reset. Recovery uses only its original tail.
        signal.setitimer(signal.ITIMER_REAL, max(.001, whole_deadline-time.monotonic()))
        # communicate must run on the real original Popen to reap the durable leader.
        for name in streams:
            os.set_blocking(getattr(proc, name).fileno(), True)
        try:
            clean = owner.stop(folder, whole_deadline, LogTail(proc, streams))
        except BaseException as exc:
            clean = {"absence_verified": False, "error": type(exc).__name__ + ": " + str(exc)}
        for name, body in streams.items():
            with (out / ("worker_" + name + ".bin")).open("xb") as f:
                f.write(body); f.flush(); os.fsync(f.fileno())
    return {"completion": completion, "error": error, "cleanup": clean, "sample_count": samples,
            "sampled_aggregate_peak_bytes": peak, "rss_receipt_bytes": rows_bytes,
            "log_bytes": {k: len(v) for k, v in streams.items()},
            "bootstrap_kill_after_natural_worker_exit_is_normal": True,
            "continuous_hard_RSS_limit": False}


def finish_status(observed, worker_result):
    return ("COMPLETE_INTAKE_CENSUS_WITH_GATES"
            if observed["error"] is None and observed["completion"] is not None
            and observed["completion"]["returncode"] == 0 and observed["cleanup"].get("absence_verified") is True
            and worker_result.get("schema") == "findlay-worker-result/v1"
            and worker_result.get("status") == "COMPLETE_INTAKE_CENSUS_WITH_GATES"
            and worker_result.get("all_tables") == 13 and worker_result.get("all_families") == 98
            and worker_result.get("scientific_qualification") is False else "REFUSED")


def truthful_pre_activation_absence(folder, cleanup):
    """An unjournaled launch marker never proves absence of its bootstrap.

    Preserve the original V4 source and its no-group-identity distinction. The
    caller cannot infer a PID or erase ambiguous markers after a launch error.
    """
    folder = Path(folder)
    if not (folder / "process_owner.json").exists() and any(folder.iterdir()):
        return {**cleanup, "absence_verified": False,
                "status": "unactivated_bootstrap_absence_unverified",
                "no_group_identity_claim": True,
                "reason": "Launch markers exist without authenticated owner identity; no PID guessed"}
    return cleanup


def child_environment(source):
    value = {key: source[key] for key in ("HOME", "TMPDIR", "LANG", "LC_ALL") if key in source}
    value.update(PATH="/usr/bin:/bin:/usr/sbin:/sbin", PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
                 SETUPTOOLS_USE_DISTUTILS="stdlib",
                 OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
                 VECLIB_MAXIMUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    return value


def joined_costs(runtime_bytes, receipt_bytes, worker_result):
    keys = ("worker_source_read_bytes", "worker_runtime_join_read_bytes", "worker_admission_receipt_read_bytes")
    need(all(type(worker_result.get(k)) is int and worker_result[k] >= 0 for k in keys),
         "Complete actual worker admission cost witnesses")
    runtime_total = runtime_bytes + worker_result[keys[1]]
    receipt_total = receipt_bytes + worker_result[keys[2]]
    need(runtime_total <= PROFILE["runtime_read_cap"] and receipt_total <= DATA_RECEIPT_CAP,
         "Combined independent runtime pass and receipt-read allowances")
    return {"runtime_verification_and_joins_bytes": runtime_total, "outer_and_worker_receipt_read_bytes": receipt_total,
            "worker_source_read_bytes": worker_result[keys[0]], "complete_worker_admission_costs": True}


def admit_runtime_join(runtime_bytes, manifest):
    known_join = manifest["python"]["bytes"]
    need(type(known_join) is int and known_join > 0
         and runtime_bytes + known_join <= PROFILE["runtime_read_cap"],
         "Reserve exact worker interpreter join before native import or GET")
    return known_join


def run_selected(path, request_sha256, lock_path, lock_sha256, emit=False):
    started = time.monotonic()
    request, request_bytes = load_request(path, request_sha256, with_bytes=True); ex = request["execution"]
    need(ex["source_lock"]["path"] == str(lock_path)
         and ex["source_lock"]["sha256"] == lock_sha256, "Caller-selected exact source freeze")
    out = Path(ex["output_root"]); parent = out.parent
    need(parent.is_dir() and not any(p.is_symlink() for p in (parent, *parent.parents)), "Ordinary output parent")
    out.mkdir(mode=0o700); (out / "owner").mkdir(mode=0o700)
    work_end, whole_end = started + 180, started + 240
    intent = write(out / "owner_intent.json",
        {"schema": "findlay-owner-intent/v1", "request_sha256": request_sha256,
         "source_lock_sha256": ex["source_lock"]["sha256"],
         "runtime_manifest_sha256": ex["runtime_manifest"]["sha256"], "output_root": str(out),
         "started_monotonic": started, "work_deadline": work_end, "whole_deadline": whole_end,
         "profile": PROFILE, "source_lock_is_execution_authority": False})
    owner = None; proc = None; observed = None; worker_result = {}; error = None; costs = None
    source_bytes = runtime_bytes = 0; receipt_bytes = request_bytes
    def alarm(signum, frame):
        if signum == signal.SIGALRM:
            raise TimeoutError("Original outer operation deadline")
        raise InterruptedError("Outer operation interrupted; exact owned cleanup required")
    previous_handlers = {sig: signal.signal(sig, alarm) for sig in (signal.SIGALRM, signal.SIGINT, signal.SIGTERM)}
    signal.setitimer(signal.ITIMER_REAL, max(.001, work_end-time.monotonic()))
    try:
        lock, lock_bytes = source_lock(request, with_bytes=True); receipt_bytes += lock_bytes
        captured, source_bytes = source_capture(request, lock, work_end, adopted=True)
        write(out / "source_verified.json", {"schema": "findlay-source-verified/v1", "verified": True,
              "request_sha256": request_sha256, "source_lock_sha256": ex["source_lock"]["sha256"],
              "commit": ex["source_adoption"]["commit"], "source_files": len(lock["files"]), "private_metadata_files": 3,
              "managed_source_read_bytes": source_bytes, "git_internal_IO_measured": False})
        rt = runtime_module(request, captured)
        manifest_body = checked(ex["runtime_manifest"], RUNTIME_MANIFEST_CAP)
        receipt_bytes += len(manifest_body); manifest = decode(manifest_body)
        runtime = rt.verify(manifest, work_end); runtime_bytes += runtime["managed_read_bytes"]
        write(out / "runtime_verified.json", {"schema": "findlay-runtime-verified/v1", "verified": True,
              "request_sha256": request_sha256, "source_lock_sha256": ex["source_lock"]["sha256"],
              "runtime_manifest_sha256": ex["runtime_manifest"]["sha256"],
              "owner_intent_sha256": intent["sha256"], "runtime": runtime})
        owner = owner_module(request, captured)
        # Preserve sys.executable's verified reporting alias through all V4 bootstrap comparisons.
        dispatch_reader = rt.Reader(deadline=work_end)
        need(rt.verify_python(manifest["python"], dispatch_reader) == runtime["python"], "Exact dispatch interpreter")
        runtime_bytes += dispatch_reader.bytes
        need(runtime_bytes <= PROFILE["runtime_read_cap"], "Complete runtime verification/read-join ceiling")
        admit_runtime_join(runtime_bytes, manifest)
        remaining = work_end - time.monotonic()
        need(remaining >= 1, "No worker starts without remaining original work horizon")
        argv = [sys.executable, str(Path(ex["repository_root"]) / lock["worker"]["path"]),
                "--request", str(path), "--request-sha256", request_sha256]
        saved_environment = dict(os.environ)
        try:
            os.environ.clear(); os.environ.update(child_environment(saved_environment))
            proc = owner.launch(argv, out / "owner", remaining, lock["worker"])
        finally:
            os.environ.clear(); os.environ.update(saved_environment)
        observed = monitor(proc, owner, out / "owner", out, work_end, whole_end)
        result_path = out / "worker" / "result.json"
        if result_path.exists():
            body = capture(result_path, 262144); receipt_bytes += len(body); worker_result = decode(body)
        need(receipt_bytes <= DATA_RECEIPT_CAP, "Reserved outer receipt-read allowance")
        # Preserve a missing/failed worker outcome without masking its primary stderr.
        if worker_result:
            costs = joined_costs(runtime_bytes, receipt_bytes, worker_result)
    except BaseException as exc:
        error = type(exc).__name__ + ": " + str(exc)
    finally:
        # Further catchable interrupts cannot cancel exact owned cleanup in its reserved tail.
        signal.signal(signal.SIGINT, signal.SIG_IGN); signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.setitimer(signal.ITIMER_REAL, max(.001, whole_end-time.monotonic()))
        if observed is None:
            cleanup = {"absence_verified": True, "status": "never_activated"}
            if owner is not None:
                try:
                    cleanup = owner.stop(out / "owner", whole_end, proc)
                except BaseException as exc:
                    cleanup = {"absence_verified": False, "error": type(exc).__name__ + ": " + str(exc)}
            cleanup = truthful_pre_activation_absence(out / "owner", cleanup)
            observed = {"completion": None, "cleanup": cleanup, "error": error or "Incomplete operation",
                        "sample_count": 0, "sampled_aggregate_peak_bytes": None}
        if error:
            observed["error"] = error
        status = finish_status(observed, worker_result)
        result = {"schema": "findlay-outer-result/v1", "status": status,
                  "scientific_qualification": False, "partial_outputs": status == "REFUSED",
                  "request_sha256": request_sha256, "source_lock_sha256": ex["source_lock"]["sha256"],
                  "runtime_manifest_sha256": ex["runtime_manifest"]["sha256"],
                  "elapsed_seconds": time.monotonic()-started, "observed": observed,
                  "worker_result": worker_result, "managed_source_read_bytes": source_bytes,
                  "managed_runtime_read_bytes": runtime_bytes, "outer_receipt_read_bytes": receipt_bytes,
                  "combined_costs": costs, "missing_worker_costs": costs is None,
                  "cost_completeness": "complete worker admission joins" if costs is not None else "known outer lower bound; worker costs unavailable",
                  "runtime_preparation_pass_separate": True,
                  "memory_limit_kind": "512 MiB planning reserve and sampled caller-plus-owned-group RSS; not hard aggregate",
                  "CPU_limit_kind": "worker process RLIMIT_CPU 160:165; no aggregate CPU measurement",
                  "OS_Git_internal_IO_measured": False}
        # All output artifacts, including worker files, are retained even when refusing.
        total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
        metadata_total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file() and not p.is_relative_to(out / "worker"))
        if metadata_total + len(canonical(result)) > META_CAP or total + len(canonical(result)) > 40*1024*1024:
            result["status"] = "REFUSED"; result["partial_outputs"] = True
            result["artifact_ceiling_exceeded"] = True
        result["operator_artifact_bytes_before_final"] = metadata_total
        result["whole_artifact_bytes_before_final"] = total
        need(time.monotonic() < whole_end, "Original whole deadline before final receipt")
        write(out / "outer_result.json", result)
        need(time.monotonic() < whole_end, "Original whole deadline after final receipt")
        if emit:
            print(json.dumps({"status": result["status"], "scientific_qualification": False}), flush=True)
            need(time.monotonic() < whole_end, "Original whole deadline through CLI summary")
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
    return result


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--request", type=Path, required=True)
    p.add_argument("--request-sha256", required=True)
    p.add_argument("--source-lock", type=Path, required=True)
    p.add_argument("--source-lock-sha256", required=True)
    args = p.parse_args(argv)
    result = run_selected(args.request, args.request_sha256, args.source_lock, args.source_lock_sha256, emit=True)
    return 0 if result["status"] == "COMPLETE_INTAKE_CENSUS_WITH_GATES" else 2


if __name__ == "__main__":
    raise SystemExit(main())

