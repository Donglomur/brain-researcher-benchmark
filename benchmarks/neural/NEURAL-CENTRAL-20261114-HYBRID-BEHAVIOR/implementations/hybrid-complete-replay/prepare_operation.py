"""Materialize the exact Hybrid source closure. Never open scientific assets/run code.

Only authenticated authored Python is loaded; operator JSON is data, never code.
No Docker, subprocess, runtime import, fit or scientific input read occurs here.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types

HELPER_PIN = (4147, "1079a68cb275a35543f02dff2ad973ef2ae2e89b85c72fab9263d00eee89c3ce")
MAX_SOURCE = 4 * 1048576


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def strict(body):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    def nonfinite(value):
        raise ValueError("nonfinite JSON")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=nonfinite)


def keys(value, names):
    need(type(value) is dict and set(value) == set(names), "exact object fields")


def absolute(value):
    need(type(value) is str and 0 < len(value) <= 4096 and
         not any(ord(c) < 32 for c in value), "bounded path text")
    path = Path(value)
    need(path.is_absolute() and str(path) == value and ".." not in path.parts,
         "canonical absolute lexical path")
    return path


def ordinary(path):
    path = absolute(str(path))
    need(not any(x.is_symlink() for x in (path, *path.parents)), "ordinary source ancestry")
    return path


def bootstrap(root):
    # The sole pre-manifest local dependency is read/authenticated before exec.
    path = ordinary(root / "source_binding.py")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             before.st_size == HELPER_PIN[0], "bootstrap extent/type")
        raw = os.read(fd, HELPER_PIN[0] + 1)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
                           s.st_mtime_ns, s.st_ctime_ns)
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()) and
             (len(raw), hashlib.sha256(raw).hexdigest()) == HELPER_PIN, "bootstrap identity")
    finally:
        os.close(fd)
    module = types.ModuleType("hybrid_prepare_binding")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def authenticate(root, manifest_sha):
    root = ordinary(root)
    helper = bootstrap(root)
    need(type(manifest_sha) is str and re.fullmatch(r"[0-9a-f]{64}", manifest_sha), "manifest SHA256")
    path = root / "SOURCE_MANIFEST.json"
    raw = helper.exact(path, {"bytes": path.lstat().st_size, "sha256": manifest_sha}, 65536)
    manifest = strict(raw)
    keys(manifest, ("schema", "files"))
    need(manifest["schema"] == "hybrid-complete-portable-source-v1", "manifest schema")
    need(type(manifest["files"]) is dict and 43 <= len(manifest["files"]) <= 64, "source roster")
    captured, total = {}, 0
    for name, descriptor in manifest["files"].items():
        need(type(name) is str and re.fullmatch(r"[A-Za-z0-9_./-]+", name) and
             not name.startswith("/") and ".." not in Path(name).parts and
             str(Path(name)) == name and name != "SOURCE_MANIFEST.json", "relative source member")
        keys(descriptor, ("bytes", "sha256"))
        need(type(descriptor["bytes"]) is int and 0 < descriptor["bytes"] <= 1048576 and
             type(descriptor["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]), "source pin")
        total += descriptor["bytes"]
        need(total <= MAX_SOURCE, "aggregate source cap")
        captured[name] = helper.exact(root / name, descriptor)
    need(captured.get("prepare_operation.py") == helper.exact(Path(__file__).absolute(),
         manifest["files"]["prepare_operation.py"]), "executing materializer identity")
    core = strict(captured["SOURCE_LOCK.json"])
    need(core["schema"] == "hybrid-public43-source-template-v1" and
         type(core["files"]) is dict and len(core["files"]) == 43, "complete43 core")
    for name, descriptor in core["files"].items():
        need(name in captured and pin(captured[name]) == descriptor, "core/manifest join")
    return helper, captured, core


PATH_FIELDS = ("base_entry", "venv_entry", "cases", "references", "runtime_receipt",
               "venv", "operator_home", "caller", "capacity_binding", "output", "docker_config")


def validate_binding(value, destination, source):
    keys(value, ("schema", "paths", "operation_token", "endpoint", "historical_artifact_locations"))
    need(value["schema"] == "hybrid-operator-local-binding-v1", "operator schema")
    keys(value["paths"], PATH_FIELDS)
    paths = {name: absolute(value["paths"][name]) for name in PATH_FIELDS}
    need(re.fullmatch(r"[a-z0-9][a-z0-9-]{7,63}", value["operation_token"])
         if type(value["operation_token"]) is str else False, "private operation token")
    need(paths["venv_entry"] == paths["venv"] / "bin/python3.11", "unchanged runtime layout")
    ep = value["endpoint"]
    keys(ep, ("original_executable_path", "original_symlink_target", "expected_observation"))
    absolute(ep["original_executable_path"])
    target = ep["original_symlink_target"]
    need(type(target) is str and 0 < len(target) <= 4096 and not any(ord(c) < 32 for c in target), "literal Docker alias")
    keys(ep["expected_observation"], ("binary", "socket"))
    for kind in ("binary", "socket"):
        row = ep["expected_observation"][kind]
        keys(row, ("path", "physical_identity", "mode", "uid", "gid"))
        absolute(row["path"])
        need(type(row["physical_identity"]) is list and len(row["physical_identity"]) == 6 and
             all(type(x) is int and 0 <= x < 2**64 for x in row["physical_identity"]), "exact integer physical identity")
        need(all(type(row[x]) is int and 0 <= row[x] < 2**32 for x in ("mode", "uid", "gid")), "exact mode/owner integers")
        need((stat.S_ISREG if kind == "binary" else stat.S_ISSOCK)(row["mode"]), "endpoint type declaration")
    loc = value["historical_artifact_locations"]
    if loc is not None:
        keys(loc, ("path", "bytes", "sha256"))
        absolute(loc["path"])
        need(type(loc["bytes"]) is int and 0 < loc["bytes"] <= 131072 and
             type(loc["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", loc["sha256"]), "exact private map descriptor")
    # Only namespace metadata is inspected; no operator asset contents are opened.
    new = [ordinary(destination), ordinary(paths["output"]), ordinary(paths["caller"])]
    for path in new:
        need(not os.path.lexists(path) and path.parent.is_dir(), "fresh namespace with existing ordinary parent")
    for i, path in enumerate(new):
        for other in new[i + 1:] + [source]:
            need(path != other and path not in other.parents and other not in path.parents, "disjoint source/output namespaces")
    return paths


def replace_pin(raw, name, descriptor):
    # Exactly one top-level literal assignment, never a broad string substitution.
    text = raw.decode()
    nodes = [n for n in ast.parse(text).body if isinstance(n, ast.Assign) and
             len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == name]
    need(len(nodes) == 1, "one literal pin assignment")
    node = nodes[0]
    old = ast.literal_eval(node.value)
    need(type(old) is tuple and len(old) == 2 and type(old[0]) is int and
         type(old[1]) is str and re.fullmatch(r"[0-9a-f]{64}", old[1]), "pin assignment shape")
    lines = text.splitlines(keepends=True)
    need(node.lineno == node.end_lineno, "single line pin")
    lines[node.lineno - 1] = name + " = " + repr((descriptor["bytes"], descriptor["sha256"])) + "\n"
    return "".join(lines).encode()


def materialize(root, manifest_sha, binding_path, binding_pin, destination):
    root, destination = Path(root).absolute(), Path(destination).absolute()
    helper, captured, core = authenticate(root, manifest_sha)
    raw = helper.exact(binding_path, binding_pin, 65536)
    operator = strict(raw)
    paths = validate_binding(operator, destination, root)
    out = {name: captured[name] for name in core["files"]}
    endpoint = strict(out["runner/EXISTING_ENDPOINT_BINDING.json"])
    endpoint.update(operator["endpoint"])
    endpoint["socket"] = {"path": endpoint["expected_observation"]["socket"]["path"]}
    endpoint["template_only"] = False
    endpoint["schema"] = "hybrid-operator-declared-Docker-physical-binding-v1"
    out["runner/EXISTING_ENDPOINT_BINDING.json"] = encode(endpoint)
    for name in ("PLAN.json", "runner/PLAN.json"):
        plan = strict(out[name])
        for key in ("base_entry", "venv_entry", "cases", "runtime_receipt", "references"):
            if key in plan:
                plan[key]["path"] = str(paths[key])
        for key in ("caller", "capacity_binding", "output", "venv", "operator_home"):
            plan[key] = str(paths[key])
        plan["operation_token"] = operator["operation_token"]
        plan["endpoint_binding"] = endpoint
        plan["docker_prefix"] = [endpoint["expected_observation"]["binary"]["path"], "--host",
            "unix://" + endpoint["socket"]["path"], "--config", str(paths["docker_config"])]
        plan["runtime_checker"]["path"] = str(destination / "runtime/runtime_setup.py")
        plan["source_template_only"] = False
        if name == "PLAN.json":
            for key, relative in (("integration_root", "integration"), ("training_root", "training"), ("runner_root", "runner")):
                plan[key] = str(destination / relative)
            plan["historical_artifact_locations"] = operator["historical_artifact_locations"]
        out[name] = encode(plan)
    runtime = strict(out["runner/EXISTING_RUNTIME_BINDINGS.json"])
    runtime["host_runtime_receipt"]["path"] = str(paths["runtime_receipt"])
    runtime["template_only"] = False
    out["runner/EXISTING_RUNTIME_BINDINGS.json"] = encode(runtime)
    nested = strict(out["runner/SOURCE_LOCK.json"])
    nested["files"] = {name: pin(out["runner/" + name]) for name in nested["files"]}
    out["runner/SOURCE_LOCK.json"] = encode(nested)
    integration = replace_pin(out["integration/protected_delivery.py"], "RUNNER_LOCK_PIN", pin(out["runner/SOURCE_LOCK.json"]))
    out["integration/protected_delivery.py"] = integration
    plan = strict(out["PLAN.json"])
    closure = plan["producer_delivery_source_closure"]
    closure["integration_sha256"] = pin(integration)["sha256"]
    closure["runner_lock_sha256"] = pin(out["runner/SOURCE_LOCK.json"])["sha256"]
    out["PLAN.json"] = encode(plan)
    lock = {"schema": "hybrid-no-refit-complete-operation-source-v1", "files": [
        dict(path=str(destination / name), **pin(out[name])) for name in sorted(out)]}
    out["SOURCE_LOCK.json"] = encode(lock)
    receipt = {"schema": "hybrid-public-source-materialization-v1", "source_manifest_sha256": manifest_sha,
        "operator_binding": binding_pin, "source_lock": pin(out["SOURCE_LOCK.json"]), "core_positions": 43,
        "scope": plan["scope"], "source_prepared_only": True, "execution_selected": False,
        "asset_bodies_read": False, "current_runtime_qualified": False, "benchmark_count_delta": 0,
        "prospective_argv": [str(paths["base_entry"]), "-I", "-B", str(destination / "operation_outer.py"),
                             "--lock-sha256", pin(out["SOURCE_LOCK.json"])["sha256"]]}
    out["PREPARATION.json"] = encode(receipt)
    need(sum(map(len, out.values())) <= MAX_SOURCE, "complete materialized output cap")
    # Recheck all captured source and binding before the first write.
    for name, data in captured.items():
        helper.exact(root / name, pin(data))
    helper.exact(binding_path, binding_pin, 65536)
    validate_binding(operator, destination, root)
    destination.mkdir(mode=0o700)
    for name, data in out.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        path.chmod(0o600)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--binding-bytes", required=True, type=int)
    parser.add_argument("--binding-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    descriptor = {"bytes": args.binding_bytes, "sha256": args.binding_sha256}
    receipt = materialize(Path(__file__).absolute().parent, args.manifest_sha256,
                          args.binding, descriptor, args.output)
    print(json.dumps({"source_prepared_only": True, "core_positions": 43,
                      "source_lock_sha256": receipt["source_lock"]["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
