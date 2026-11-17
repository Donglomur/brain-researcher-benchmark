#!/usr/bin/env python3
"""Operator-side isolated replay, separate from the frozen Harbor verifier.

Candidate code is never imported on the host. Docker is a trust boundary, not a
proof against kernel/daemon vulnerabilities. Only the pinned operator image is used.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[1]
TASK = REPO / "tasks/life-sciences/neuroscience/language-encoding"
AUTHORING = REPO / "authoring/language-encoding"
IMAGE = "sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156"
VERIFIER_SHA = "231b580ed81c9f96ed18118d87464b843e9a8c6fdbf41910b061fabc2180e3ee"
INPUTS = frozenset({"data_dictionary.json", "train_features.npz", "search_features.npz", "train_items.csv", "search_items.csv", "train_responses.csv", "search_responses.csv"})
LIMITS = {"model.npz": 100_000, "predictions.csv": 1_000_000, "cv_predictions.csv": 1_000_000, "report.json": 100_000, "reproduce.py": 1_000_000}
REQUIRED = frozenset(LIMITS) - {"reproduce.py"}
VOLUME_BYTES = 32 * 1024 * 1024
INODES = 512


class GateError(ValueError):
    pass


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def regular(path, maximum):
    path = Path(path).absolute()
    for parent in path.parents:
        if parent.is_symlink():
            raise GateError(f"Symlinked ancestor: {parent}")
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or not 0 < s.st_size <= maximum:
        raise GateError(f"Nonregular, linked, empty or oversized file: {path.name}")
    return s


def copy_regular(source, destination, maximum, expected=None):
    regular(source, maximum)
    # O_NOFOLLOW protects the final component during opening; metadata is checked
    # before and after copying. Concurrent mutation of the trusted host is out of scope.
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as src:
        before = os.fstat(src.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= maximum:
            raise GateError("Unsafe source at open")
        total = 0
        with Path(destination).open("xb") as dst:
            for part in iter(lambda: src.read(1024 * 1024), b""):
                total += len(part)
                if total > maximum:
                    raise GateError("Source grew beyond limit")
                dst.write(part)
        after = os.fstat(src.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise GateError("Source changed during snapshot")
    digest = sha(destination)
    if expected and digest != expected:
        raise GateError(f"Pinned input hash mismatch: {Path(source).name}")
    Path(destination).chmod(0o444)
    return {"bytes": total, "sha256": digest}


def pinned_inputs(lock_path):
    regular(lock_path, 4_000_000)
    lock = json.loads(Path(lock_path).read_text())
    result = {}
    if not isinstance(lock, dict) or lock.get("schema_version") != 1 or not isinstance(lock.get("inputs"), list):
        raise GateError("Invalid operator input lock")
    for item in lock["inputs"]:
        if not isinstance(item, dict) or item.get("role") != "public_input":
            continue
        relative = item.get("local_path", "")
        name = relative.removeprefix("environment/data/") if isinstance(relative, str) else ""
        if name not in INPUTS or name in result or type(item.get("bytes")) is not int or not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise GateError("Invalid/duplicate public input lock entry")
        result[name] = item
    if set(result) != INPUTS:
        raise GateError("Public input lock must identify exactly the seven files")
    return result


def stage_inputs(source, input_dir, lock_path, staging):
    input_dir = Path(input_dir)
    if input_dir.is_symlink() or not input_dir.is_dir() or {x.name for x in input_dir.iterdir()} != INPUTS:
        raise GateError("Public input inventory differs from the exact allowlist")
    locked = pinned_inputs(lock_path)
    public, program = staging / "public", staging / "source"
    public.mkdir(mode=0o755); program.mkdir(mode=0o755)
    source_record = copy_regular(source, program / "reproduce.py", 1_000_000)
    records = {}
    for name in sorted(INPUTS):
        records[name] = copy_regular(input_dir / name, public / name, 64_000_000, locked[name]["sha256"])
        if records[name]["bytes"] != locked[name]["bytes"]:
            raise GateError("Pinned public input size mismatch")
    public.chmod(0o555); program.chmod(0o555)
    return source_record, records


def validate_inventory(entries, policy="strict"):
    if policy not in {"strict", "artifact-contract"}:
        raise GateError("Unknown output policy")
    if not isinstance(entries, list) or len(entries) > (len(LIMITS) if policy == "strict" else INODES):
        raise GateError("Unexpected output inventory")
    result = {}
    total = 0
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"] or item["name"] in {".", ".."} or "/" in item["name"] or "\x00" in item["name"] or item["name"] in result or (policy == "strict" and item["name"] not in LIMITS):
            raise GateError("Unexpected or duplicate output name")
        name = item["name"]
        minimum = 1 if name in LIMITS else 0
        maximum = LIMITS.get(name, 1_000_000)
        if type(item.get("mode")) is not int or not stat.S_ISREG(item["mode"]) or type(item.get("nlink")) is not int or item["nlink"] != 1 or type(item.get("size")) is not int or not minimum <= item["size"] <= maximum:
            raise GateError(f"Unsafe linked/nonregular/oversized output: {name}")
        result[name] = item
        total += item["size"]
    if total > VOLUME_BYTES:
        raise GateError("Logical output bytes exceed total budget")
    if not REQUIRED <= result.keys():
        raise GateError("Missing required replay outputs")
    return result


def unpack_one(raw, name, size):
    if len(raw) > LIMITS[name] + 1_000_000:
        raise GateError("Oversized Docker archive")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        members = archive.getmembers()
        if len(members) != 1:
            raise GateError("Unexpected archive member count")
        m = members[0]
        if not m.isfile() or m.name not in (name, "./" + name) or m.size != size or m.linkname:
            raise GateError("Unsafe Docker archive entry")
        f = archive.extractfile(m)
        content = f.read(LIMITS[name] + 1) if f else b""
        if len(content) != size:
            raise GateError("Docker archive size mismatch")
        return content


def validate_model_headers(path):
    """Reject allocation bombs before NumPy/the trusted verifier sees an archive."""
    expected = {"coef.npy": (1600,), "intercept.npy": (), "alpha.npy": ()}
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) != 3 or {x.filename for x in infos} != set(expected):
            raise GateError("Wrong model archive inventory")
        for info in infos:
            if info.file_size > 100_000 or info.flag_bits & 1:
                raise GateError("Oversized/encrypted model member")
            raw = archive.read(info)
            if len(raw) < 10 or raw[:6] != b"\x93NUMPY" or raw[6:8] not in (b"\x01\x00", b"\x02\x00", b"\x03\x00"):
                raise GateError("Invalid NPY member")
            width = 2 if raw[6] == 1 else 4
            length = int.from_bytes(raw[8:8 + width], "little")
            if not 0 < length <= 4096:
                raise GateError("Oversized NPY header")
            header = ast.literal_eval(raw[8 + width:8 + width + length].decode("utf-8"))
            if not isinstance(header, dict) or set(header) != {"descr", "fortran_order", "shape"} or header["shape"] != expected[info.filename] or type(header["fortran_order"]) is not bool:
                raise GateError("Unexpected NPY shape/header")
            dtype = header["descr"]
            if not isinstance(dtype, str) or not re.fullmatch(r"[<>=|](?:f[248]|[iu][1248])", dtype):
                raise GateError("Unsafe model dtype")
            count = 1600 if info.filename == "coef.npy" else 1
            if len(raw) != 8 + width + length + count * int(dtype[-1]):
                raise GateError("NPY payload length mismatch")


class Docker:
    def __init__(self, binary="docker"):
        self.binary, self.commands = binary, []

    def run(self, arguments, timeout=30, binary=False, check=True):
        command = [self.binary, *arguments]
        self.commands.append(command)
        r = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        if check and r.returncode:
            raise GateError(f"Docker command failed ({r.returncode}): {r.stderr.decode(errors='replace')[:2000]}")
        return r if binary else r.stdout.decode()

    def inspect(self, container):
        return json.loads(self.run(["inspect", container]))[0]


def restrictions(memory, cpus, pids):
    return ["--network", "none", "--read-only", "--user", "65534:65534", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", str(pids), "--cpus", str(cpus), "--memory", str(memory), "--memory-swap", str(memory), "--log-driver", "none", "--ulimit", "core=0:0", "--ulimit", "nofile=128:128"]


def candidate_command(name, image, volume, staging, memory, cpus, pids, wall):
    for directory in (staging / "public", staging / "source"):
        if any(c in str(directory) for c in ",\r\n"):
            raise GateError("Mount path contains unsupported characters")
    return ["create", "--pull", "never", "--name", name, *restrictions(memory, cpus, pids), "--ulimit", "fsize=1000000:1000000", "--ulimit", f"cpu={wall + 1}:{wall + 2}", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=67108864,mode=1777", "--mount", f"type=bind,src={staging / 'public'},dst=/app/data,readonly", "--mount", f"type=bind,src={staging / 'source'},dst=/submission,readonly", "--mount", f"type=volume,src={volume},dst=/app/output,volume-nocopy", "--workdir", "/app/output", "--env", "OPENBLAS_NUM_THREADS=2", "--env", "OMP_NUM_THREADS=2", "--env", "MKL_NUM_THREADS=2", "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "HOME=/tmp", "--entrypoint", "python", image, "-I", "/submission/reproduce.py", "--input", "/app/data", "--output", "/app/output"]


def verify_mounts(inspect, staging, volume):
    actual = {(m["Destination"], m["Type"], m["RW"]): m for m in inspect["Mounts"] if m["Type"] != "tmpfs"}
    expected = {("/app/data", "bind", False): str(staging / "public"), ("/submission", "bind", False): str(staging / "source"), ("/app/output", "volume", True): volume}
    if set(actual) != set(expected):
        raise GateError("Unexpected candidate mount topology")
    for key, value in expected.items():
        if actual[key].get("Name" if key[1] == "volume" else "Source") != value:
            raise GateError("Candidate mount source mismatch")
    host, config = inspect["HostConfig"], inspect["Config"]
    if host.get("NetworkMode") != "none" or not host.get("ReadonlyRootfs") or host.get("Privileged") or config.get("User") != "65534:65534" or host.get("PidMode") == "host" or host.get("Devices"):
        raise GateError("Candidate isolation configuration differs from policy")
    if "ALL" not in host.get("CapDrop", []) or "no-new-privileges:true" not in host.get("SecurityOpt", []):
        raise GateError("Candidate capabilities/privilege policy differs")


def verify_collector(inspect, volume):
    mounts = inspect["Mounts"]
    if len(mounts) != 1 or mounts[0].get("Type") != "volume" or mounts[0].get("Name") != volume or mounts[0].get("Destination") != "/capture" or mounts[0].get("RW") is not False:
        raise GateError("Collector must have only the read-only output volume")
    h, c = inspect["HostConfig"], inspect["Config"]
    if h.get("NetworkMode") != "none" or not h.get("ReadonlyRootfs") or h.get("Privileged") or c.get("User") != "65534:65534" or "ALL" not in h.get("CapDrop", []) or "no-new-privileges:true" not in h.get("SecurityOpt", []):
        raise GateError("Collector isolation configuration differs from policy")


INVENTORY_CODE = "import os,stat,json; print(json.dumps([dict(name=e.name,mode=e.stat(follow_symlinks=False).st_mode,nlink=e.stat(follow_symlinks=False).st_nlink,size=e.stat(follow_symlinks=False).st_size) for e in os.scandir('/capture')]))"
VERIFY_CODE = """import importlib.util,json,pathlib,resource,sys
resource.setrlimit(resource.RLIMIT_CPU,(60,61))
resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
spec=importlib.util.spec_from_file_location('trusted_language_verifier',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
print(json.dumps(module.validate(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]))))
"""


def verify_private_reference(private, lock_path):
    lock = json.loads(Path(lock_path).read_text())
    entries = [x for x in lock.get("inputs", []) if isinstance(x, dict) and x.get("role") == "verifier_reference" and x.get("local_path") == "tests/private/expected.npz"]
    if len(entries) != 1:
        raise GateError("Expected reference needs exactly one operator pin")
    pin = entries[0]
    regular(private / "expected.npz", 64_000_000)
    if type(pin.get("bytes")) is not int or (private / "expected.npz").stat().st_size != pin["bytes"] or sha(private / "expected.npz") != pin.get("sha256"):
        raise GateError("Privileged expected reference differs from its pinned bytes/hash")


def numeric_verifier(output, python, record, lock_path):
    verifier, private = TASK / "tests/validation.py", TASK / "tests/private"
    regular(verifier, 100_000); regular(private / "expected.npz", 64_000_000)
    if sha(verifier) != VERIFIER_SHA:
        raise GateError("Trusted numerical verifier changed; operator review required")
    if sha(lock_path) != record["input_lock_sha256"]:
        raise GateError("Operator input/reference lock changed during replay")
    verify_private_reference(private, lock_path)
    validate_model_headers(output / "model.npz")
    command = [python, "-I", "-c", VERIFY_CODE, str(verifier), str(output), str(private)]
    record["trusted_verifier"] = {"command": command, "source_sha256": sha(verifier), "reference_sha256": sha(private / "expected.npz"), "candidate_code_imported_or_executed_on_host": False}
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT") if k in os.environ}
    env.update(OPENBLAS_NUM_THREADS="2", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")
    r = subprocess.run(command, cwd=output.parent, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=65)
    record["trusted_verifier"].update(returncode=r.returncode, stdout=r.stdout.decode(errors="replace")[:16000], stderr=r.stderr.decode(errors="replace")[:16000])
    if r.returncode:
        raise GateError("Trusted numerical verification failed")
    verdict = json.loads(r.stdout)
    if not isinstance(verdict, dict) or verdict.get("passed") is not True:
        raise GateError("No passing trusted numerical verdict")
    return verdict


def replay(source, run_dir, *, input_dir=TASK / "environment/data", lock_path=AUTHORING / "provenance/inputs.lock.json", image=IMAGE, docker="docker", verifier_python=sys.executable, wall=120, memory=4 * 1024**3, cpus=2.0, pids=128, output_policy="strict"):
    if image != IMAGE:
        raise GateError("Only the operator-vetted immutable scientific image is supported")
    if type(wall) is not int or not 1 <= wall <= 300 or not 256 * 1024**2 <= memory <= 4 * 1024**3 or not 0 < cpus <= 2 or not 16 <= pids <= 128:
        raise GateError("Resource request outside bounded operator policy")
    if output_policy not in {"strict", "artifact-contract"}:
        raise GateError("Unknown output policy")
    run_dir = Path(run_dir).absolute()
    for parent in run_dir.parents:
        if parent.is_symlink():
            raise GateError("Symlinked evidence path")
    run_dir.mkdir(parents=True, exist_ok=False)
    record = {"schema_version": 1, "mode": "real_public_input_replay", "output_policy": output_policy, "status": "started", "started_at": datetime.now(timezone.utc).isoformat(), "source": str(source), "image_id": image, "gate_source_sha256": sha(Path(__file__)), "not_upstream_harbor_verifier": True, "limits": {"cpus": cpus, "wall_seconds": wall, "memory_bytes": memory, "pids": pids, "output_volume_bytes": VOLUME_BYTES, "output_inode_limit": INODES, "per_file_bytes": LIMITS, "extra_regular_file_bytes": 1_000_000}, "scientific_scope": "repeatability on the same public development inputs; not novel evidence, model evaluation, or proof against answer copying"}
    engine = Docker(docker)
    suffix = uuid.uuid4().hex
    volume, holder, candidate = ("neuro-replay-" + prefix + "-" + suffix for prefix in ("volume", "collector", "candidate"))
    created = {"volume": False, "holder": False, "candidate": False}
    started = time.monotonic()
    staging = Path(tempfile.mkdtemp(prefix="neuro-replay-", dir="/tmp")).resolve()
    try:
        record["source_snapshot"], record["public_input_snapshot"] = stage_inputs(Path(source), Path(input_dir), Path(lock_path), staging)
        record["input_lock_sha256"] = sha(lock_path)
        record["image_inspect"] = json.loads(engine.run(["image", "inspect", image]))[0]
        if record["image_inspect"].get("Id") != IMAGE or record["image_inspect"].get("Config", {}).get("Volumes"):
            raise GateError("Unexpected image identity or implicit image volumes")
        options = f"size={VOLUME_BYTES},nr_inodes={INODES},uid=65534,gid=65534,mode=0700"
        engine.run(["volume", "create", "--driver", "local", "--opt", "type=tmpfs", "--opt", "device=tmpfs", "--opt", "o=" + options, volume]); created["volume"] = True
        record["volume_inspect"] = json.loads(engine.run(["volume", "inspect", volume]))[0]
        if record["volume_inspect"].get("Options") != {"type": "tmpfs", "device": "tmpfs", "o": options}:
            raise GateError("Output volume is not the requested bounded tmpfs")
        engine.run(["create", "--pull", "never", "--name", holder, *restrictions(128 * 1024**2, .25, 16), "--mount", f"type=volume,src={volume},dst=/capture,readonly,volume-nocopy", "--entrypoint", "python", image, "-I", "-c", "import time;time.sleep(600)"]); created["holder"] = True
        engine.run(["start", holder])
        record["collector_inspect"] = engine.inspect(holder)
        verify_collector(record["collector_inspect"], volume)
        if json.loads(engine.run(["exec", holder, "python", "-I", "-c", INVENTORY_CODE])) != []:
            raise GateError("Output volume was not empty")
        engine.run(candidate_command(candidate, image, volume, staging, memory, cpus, pids, wall)); created["candidate"] = True
        record["candidate_created_inspect"] = engine.inspect(candidate)
        verify_mounts(record["candidate_created_inspect"], staging, volume)
        engine.run(["start", candidate]); candidate_start = time.monotonic()
        try:
            engine.run(["wait", candidate], timeout=wall)
        except subprocess.TimeoutExpired:
            engine.run(["kill", candidate], check=False)
            record["status"] = "wall_timeout"
        record["candidate_wall_seconds"] = time.monotonic() - candidate_start
        state = engine.inspect(candidate)
        record["candidate_finished_inspect"] = state
        if record["status"] == "wall_timeout" or state["State"].get("Running") or state["State"].get("OOMKilled") or state["State"].get("ExitCode") != 0:
            raise GateError("Candidate timed out, failed, or exceeded memory; no outputs accepted")
        # The candidate container has exited: no candidate process can modify outputs.
        inventory = json.loads(engine.run(["exec", holder, "python", "-I", "-c", INVENTORY_CODE]))
        record["output_inventory_before_copy"] = inventory
        safe = validate_inventory(inventory, output_policy)
        record["ignored_regular_outputs"] = [item for name, item in safe.items() if name not in LIMITS]
        output = run_dir / "sanitized-output"; output.mkdir(mode=0o700)
        for name, item in safe.items():
            if name not in LIMITS:
                continue  # Contract-allowed diagnostics remain unread in bounded tmpfs.
            r = engine.run(["cp", holder + ":/capture/" + name, "-"], binary=True)
            content = unpack_one(r.stdout, name, item["size"])
            if name == "reproduce.py":
                if hashlib.sha256(content).hexdigest() != record["source_snapshot"]["sha256"]:
                    raise GateError("Candidate emitted a different source program")
                continue  # Source presence is established only by the trusted runner.
            with (output / name).open("xb") as stream:
                stream.write(content)
            (output / name).chmod(0o400)
        copy_regular(staging / "source/reproduce.py", output / "reproduce.py", 1_000_000, record["source_snapshot"]["sha256"])
        record["source_attachment"] = "trusted runner attached original source after candidate exit; candidate self-copy is not required"
        record["output_hashes"] = {name: {"sha256": sha(output / name), "bytes": (output / name).stat().st_size} for name in sorted(LIMITS)}
        # Recheck snapshots; code/inputs were never writable container mounts.
        for name, info in record["public_input_snapshot"].items():
            if sha(staging / "public" / name) != info["sha256"]:
                raise GateError("Read-only public snapshot changed")
        if sha(staging / "source/reproduce.py") != record["source_snapshot"]["sha256"]:
            raise GateError("Read-only source snapshot changed")
        record["numerical_verdict"] = numeric_verifier(output, verifier_python, record, lock_path)
        record["status"] = "replay_and_numeric_checks_passed"
    except Exception as exc:
        if record["status"] != "wall_timeout":
            record["status"] = "rejected"
        record["error"] = {"type": type(exc).__name__, "message": str(exc)[:4000]}
    finally:
        cleanup = []
        for key, name in (("candidate", candidate), ("holder", holder)):
            if created[key]:
                try:
                    r = engine.run(["rm", "--force", name], binary=True, check=False)
                    cleanup.append({"resource": name, "returncode": r.returncode})
                except Exception as exc:
                    cleanup.append({"resource": name, "error": str(exc)[:1000]})
        if created["volume"]:
            try:
                r = engine.run(["volume", "rm", volume], binary=True, check=False)
                cleanup.append({"resource": volume, "returncode": r.returncode})
            except Exception as exc:
                cleanup.append({"resource": volume, "error": str(exc)[:1000]})
        for directory in (staging / "public", staging / "source"):
            if directory.is_dir() and not directory.is_symlink():
                directory.chmod(0o700)
        shutil.rmtree(staging, ignore_errors=True)
        if staging.exists():
            cleanup.append({"resource": str(staging), "error": "Temporary snapshot cleanup incomplete"})
        record.update(cleanup=cleanup, docker_commands=engine.commands, wall_seconds=time.monotonic() - started, finished_at=datetime.now(timezone.utc).isoformat())
        if any(x.get("returncode") != 0 for x in cleanup):
            record["cleanup_incomplete"] = True
            if record["status"] == "replay_and_numeric_checks_passed":
                record["status"] = "checks_passed_cleanup_incomplete"
        (run_dir / "replay.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--run-dir", type=Path, required=True, help="Fresh evidence directory, normally artifacts-build/replay-language/<run>")
    p.add_argument("--docker", default="docker")
    p.add_argument("--verifier-python", default=sys.executable)
    p.add_argument("--wall-seconds", type=int, default=120)
    p.add_argument("--output-policy", choices=("strict", "artifact-contract"), default="strict", help="Strict exact inventory, or bounded regular diagnostic files ignored as the frozen artifact contract permits")
    a = p.parse_args()
    try:
        result = replay(a.source, a.run_dir, docker=a.docker, verifier_python=a.verifier_python, wall=a.wall_seconds, output_policy=a.output_policy)
    except (OSError, ValueError) as exc:
        p.exit(1, f"Replay setup rejected: {exc}\n")
    print(json.dumps({"status": result["status"], "record": str(a.run_dir / "replay.json")}, indent=2))
    return 0 if result["status"] == "replay_and_numeric_checks_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
