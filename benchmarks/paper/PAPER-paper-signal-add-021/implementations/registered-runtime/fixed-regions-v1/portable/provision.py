"""Source-only owner provisioning for the complete fixed-region TMS profile.

No function downloads assets, opens data/reference/program locators, runs a
candidate, probes a daemon, or starts the generated owner. Selection is a
separate trusted-operator act; JSON is its record, not a credential.
"""
import argparse
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

MIB = 1024 * 1024
SOURCE_LIMIT = 2 * MIB
OUTPUT_LIMIT = 2 * MIB
CATALOG_SHA256 = "482845e21efd6889ddfa5b72c4b1e0f41f8fee92b1c0e2895c0e0b70fe0fdda7"
READ_FIELDS = ("official_code_review", "projection_review",
               "projection_support_review", "reference_acceptance",
               "source_origin_asset_binding")
GUARD_FIELDS = {"dev", "inode", "mode", "uid", "gid", "nlink"}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def decode(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    def bad(value):
        raise ValueError("nonfinite JSON number")
    def real(value):
        result = float(value)
        need(math.isfinite(result), "nonfinite JSON float")
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad, parse_float=real)


def keys(value, names, reason):
    need(type(value) is dict and set(value) == set(names), reason)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def path_text(value):
    need(type(value) is str and 0 < len(value.encode()) <= 4096 and
         all(ord(c) >= 32 for c in value) and "," not in value, "literal bounded path")
    p = Path(value)
    need(p.is_absolute() and str(p) == value and ".." not in p.parts, "canonical absolute path")
    # This is metadata-only. No asset body is opened or followed.
    need(not any(q.is_symlink() for q in (p, *p.parents)), "no symlink component")
    return p


def overlap(a, b):
    return a == b or a in b.parents or b in a.parents


def descriptor(value, cap=MIB):
    keys(value, ("path", "bytes", "sha256"), "closed descriptor")
    path_text(value["path"])
    need(type(value["bytes"]) is int and 0 <= value["bytes"] <= cap, "descriptor extent")
    need(type(value["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", value["sha256"]),
         "descriptor digest")
    return {k: value[k] for k in ("bytes", "sha256")}


def read_source(path, expected=None, cap=MIB):
    p = path_text(str(path))
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             0 <= before.st_size <= cap, "ordinary bounded source")
        raw = bytearray()
        while len(raw) < before.st_size:
            part = os.read(fd, min(65536, before.st_size - len(raw)))
            need(bool(part), "short source read")
            raw.extend(part)
        after, named = os.fstat(fd), p.lstat()
        fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size",
                  "st_mtime_ns", "st_ctime_ns")
        need(all(getattr(before, k) == getattr(after, k) == getattr(named, k)
                 for k in fields), "stable source capture")
    finally:
        os.close(fd)
    body = bytes(raw)
    if expected is not None:
        need(pin(body) == expected, "source identity")
    return body


def catalog():
    raw = read_source(Path(__file__).absolute().with_name("CATALOG.json"), cap=65536)
    need(hashlib.sha256(raw).hexdigest() == CATALOG_SHA256, "catalog identity")
    return decode(raw)


def capture_owner(root, cat):
    root = path_text(str(root))
    lock_raw = read_source(root / cat["template_lock_path"], cat["template_lock"], 65536)
    lock = decode(lock_raw)
    need(lock == {"schema": "tms_fixed_regions_whole_owner_lock_v1",
                  "members": cat["source_members"]}, "complete accepted owner graph")
    total = len(lock_raw)
    bodies = {}
    keys(cat["source_locations"], lock["members"], "complete relocated source map")
    for name, expected in lock["members"].items():
        need(not Path(name).is_absolute() and ".." not in Path(name).parts, "source member")
        total += expected["bytes"]
        need(total <= SOURCE_LIMIT, "source read reservation")
        location = cat["source_locations"][name]
        need(type(location) is str and not Path(location).is_absolute() and
             str(Path(location)) == location and ".." not in Path(location).parts,
             "literal in-tree source binding")
        bodies[name] = read_source(root / location, expected)
    return bodies, total


def bind_config(request, cat):
    keys(request, ("schema", "attempt_id", "package_root", "operation_root",
                   "assets", "evidence", "programs", "runtime", "owner_use"),
         "closed provision request")
    need(request["schema"] == "tms_portable_provision_request_v1", "request schema")
    need(type(request["attempt_id"]) is str and
         re.fullmatch("[a-z0-9][a-z0-9-]{0,63}", request["attempt_id"]), "attempt id")
    package, operation = path_text(request["package_root"]), path_text(request["operation_root"])
    need(not overlap(package, operation), "disjoint package and operation")
    need(not package.exists() and not operation.exists(), "fresh package and operation")
    keys(request["owner_use"], ("authority_reference", "authorized_local_use",
         "redistribution_granted"), "closed owner use")
    need(type(request["owner_use"]["authority_reference"]) is str and
         0 < len(request["owner_use"]["authority_reference"]) <= 1024 and
         request["owner_use"]["authorized_local_use"] is True and
         request["owner_use"]["redistribution_granted"] is False, "explicit local-use scope")
    cfg = copy.deepcopy(cat["config_template"])
    assets, evidence = request["assets"], request["evidence"]
    keys(assets, ("input_files", "paper", "official_code", "reference"), "complete assets")
    keys(assets["input_files"], cfg["input_files"], "all four projection members")
    def fixed(given, expected, cap=40*MIB):
        need(descriptor(given, cap) == {k: expected[k] for k in ("bytes", "sha256")},
             "accepted complete asset identity")
        return copy.deepcopy(given)
    cfg["input_files"] = {n: fixed(assets["input_files"][n], p)
                          for n, p in cfg["input_files"].items()}
    cfg["paper"] = fixed(assets["paper"], cfg["paper"])
    cfg["reference_selection"] = fixed(assets["reference"], cfg["reference_selection"])
    expected_code = {x["relative"]: x["file"] for x in cfg["official_code"]}
    keys(assets["official_code"], expected_code, "all twelve selected code members")
    cfg["official_code"] = [{"relative": n, "file": fixed(assets["official_code"][n], p)}
                            for n, p in expected_code.items()]
    names = set(READ_FIELDS) | set(cfg["image_evidence"]) | {"source_independent_review"}
    keys(evidence, names, "complete inherited and fresh review evidence")
    for name in READ_FIELDS:
        cfg[name] = fixed(evidence[name], cfg[name], MIB)
    for name in cfg["image_evidence"]:
        cfg["image_evidence"][name] = fixed(evidence[name], cfg["image_evidence"][name], MIB)
    descriptor(evidence["source_independent_review"])
    keys(request["programs"], ("A", "B"), "two frozen programs")
    for p in request["programs"].values():
        descriptor(p, 262144)
    rt = request["runtime"]
    keys(rt, ("python", "daemon_socket", "daemon_guard", "admission"), "closed runtime")
    python = path_text(rt["python"])
    need(python.name in ("python3.11", "python3"), "selected CPython 3.11 executable")
    socket = path_text(rt["daemon_socket"])
    keys(rt["daemon_guard"], GUARD_FIELDS, "exact socket identity")
    need(all(type(v) is int and v >= 0 for v in rt["daemon_guard"].values()),
         "integer socket identity")
    need(stat.S_ISSOCK(rt["daemon_guard"]["mode"]) and rt["daemon_guard"]["nlink"] == 1,
         "socket-kind identity")
    descriptor(rt["admission"])
    cfg["daemon_socket"], cfg["daemon_guard"] = str(socket), copy.deepcopy(rt["daemon_guard"])
    # No new scientific assets, image, budget, algorithm or qualification are inferred.
    all_locators = [*cfg["input_files"].values(), cfg["paper"], cfg["reference_selection"],
                    *(x["file"] for x in cfg["official_code"]), *evidence.values(),
                    *request["programs"].values(), rt["admission"]]
    paths = [path_text(x["path"]) for x in all_locators]
    need(len(set(paths)) == len(paths), "distinct asset and evidence locators")
    need(all(not overlap(p, package) and not overlap(p, operation) for p in paths),
         "assets outside generated and output trees")
    need(not overlap(python, package) and not overlap(python, operation) and
         not overlap(socket, package) and not overlap(socket, operation), "runtime outside output")
    return cfg


def replace_value(source, target, expression, function=None):
    """Replace only one AST-located assignment value in pinned predecessor bytes."""
    text = source.decode("utf-8")
    tree = ast.parse(text)
    scope = tree
    if function is not None:
        matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function]
        need(len(matches) == 1, "exact source function")
        scope = matches[0]
    matches = [n for n in ast.walk(scope) if isinstance(n, ast.Assign) and
               len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and
               n.targets[0].id == target]
    need(len(matches) == 1, "exact source assignment")
    node = matches[0].value
    if target == "argv":
        need(isinstance(node, ast.List) and isinstance(node.elts[0], ast.Constant) and
             type(node.elts[0].value) is str, "literal interpreter argv")
        node = node.elts[0]
    # Python AST columns are UTF-8 byte offsets, so operate on encoded lines.
    lines = source.splitlines(keepends=True)
    start = sum(map(len, lines[:node.lineno-1])) + node.col_offset
    end = sum(map(len, lines[:node.end_lineno-1])) + node.end_col_offset
    result = source[:start] + expression.encode() + source[end:]
    ast.parse(result)
    return result


def render(request, cat, bodies):
    cfg = bind_config(request, cat)
    need({n: pin(b) for n, b in bodies.items()} == cat["source_members"],
         "complete captured predecessor")
    result = dict(bodies)
    result["CONFIG.json"] = encode(cfg)
    for name in ("owner/run_once.py", "owner/outer_once.py"):
        result[name] = replace_value(result[name], "EXTERNAL",
                                     "Path(" + repr(request["operation_root"]) + ")")
    result["owner/outer_once.py"] = replace_value(result["owner/outer_once.py"], "argv",
                                                 repr(request["runtime"]["python"]), "main")
    result["owner/docker_owner.py"] = replace_value(result["owner/docker_owner.py"],
        "DAEMON_SOCKET", "Path(" + repr(cfg["daemon_socket"]) + ")")
    result["owner/docker_owner.py"] = replace_value(result["owner/docker_owner.py"],
        "DAEMON_GUARD", repr(cfg["daemon_guard"]))
    lock = {"schema": "tms_fixed_regions_whole_owner_lock_v1",
            "members": {n: pin(b) for n, b in result.items()}}
    # Source remains exactly the accepted 16-member graph, with four explicit changed files.
    changed = sorted(n for n in bodies if bodies[n] != result[n])
    need(set(changed) <= {"CONFIG.json", "owner/run_once.py", "owner/outer_once.py",
                         "owner/docker_owner.py"}, "only declared binding changes")
    source_review = request["evidence"]["source_independent_review"]
    evidence = dict(cfg["image_evidence"], source_independent_review=source_review)
    selected = {"root_execution_selected": False,
        "delivery_selection": {
            "schema": "tms_fixed_region_delivery_selection_v1", "task_id": cfg["task_id"],
            "root_execution_selected": True, "input_files": cfg["input_files"],
            "paper": cfg["paper"], "official_code": cfg["official_code"],
            "official_code_review": {k: cfg["official_code_review"][k] for k in ("bytes","sha256")},
            "projection_review": {k: cfg["projection_review"][k] for k in ("bytes","sha256")},
            "programs": request["programs"], "selected_budget": cfg["study_budget"],
            "runtime_admission": {"image": cfg["image"],
                "image_content_review": {k: evidence["image_independent_review"][k] for k in ("bytes","sha256")},
                "daemon_guard_review": {k: source_review[k] for k in ("bytes","sha256")}}},
        "reference_selection": cfg["reference_selection"], "runtime_evidence": evidence,
        "study_budget": cfg["study_budget"]}
    wrapper = {"schema": "tms_fixed_region_whole_run_v1",
               "attempt_id": request["attempt_id"], "selection": selected}
    return result, encode(lock), encode(wrapper), changed


def write_new(path, body):
    p = path_text(str(path))
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        at = 0
        while at < len(body):
            written = os.write(fd, body[at:])
            need(written > 0, "complete write")
            at += written
        os.fsync(fd)
        os.fchmod(fd, 0o400)
    finally:
        os.close(fd)


def build(request_raw, predecessor_root):
    need(len(request_raw) <= 65536, "request size")
    request, cat = decode(request_raw), catalog()
    bodies, source_reads = capture_owner(predecessor_root, cat)
    rendered, lock, wrapper, changed = render(request, cat, bodies)
    root, operation = path_text(request["package_root"]), path_text(request["operation_root"])
    need(root.parent.is_dir() and operation.parent.is_dir(), "existing ordinary parent directories")
    report = {"schema": "tms_portable_package_v1", "request": pin(request_raw),
        "catalog": {"sha256": CATALOG_SHA256}, "public_template_lock": cat["template_lock"],
        "generated_lock": pin(lock), "unselected_manifest": pin(wrapper),
        "changed_members": changed, "source_reads": source_reads,
        "asset_body_reads": 0, "execution_selected": False,
        "runtime_admission": request["runtime"]["admission"],
        "runtime_qualification_reused_without_new_admission": False}
    request_copy, report_raw = request_raw, encode(report)
    total = sum(map(len, rendered.values())) + len(lock) + len(wrapper) + len(request_copy) + len(report_raw)
    need(total <= OUTPUT_LIMIT, "complete package retention reservation")
    # Failure leaves an unselected partial private tree, never silently retries.
    root.mkdir(mode=0o700)
    (root / "owner").mkdir(mode=0o700)
    operation.mkdir(mode=0o700)
    (operation / "selections").mkdir(mode=0o700)
    (operation / "attempts").mkdir(mode=0o700)
    for name, body in rendered.items():
        write_new(root / name, body)
    for name, body in (("EXECUTION_LOCK.json", lock), ("PROVISION_REQUEST.private.json", request_copy),
                       ("UNSELECTED_RUN.private.json", wrapper), ("PROVISION_RESULT.private.json", report_raw)):
        write_new(root / name, body)
    os.chmod(root / "owner", 0o500)
    os.chmod(root, 0o500)
    return report


def plan(request_raw, predecessor_root):
    """Compute review templates without creating directories or reading assets."""
    need(len(request_raw) <= 65536, "request size")
    request, cat = decode(request_raw), catalog()
    bodies, charged = capture_owner(predecessor_root, cat)
    rendered, lock, wrapper, changed = render(request, cat, bodies)
    rt = request["runtime"]
    selected = decode(wrapper)
    selected["selection"]["root_execution_selected"] = True
    grant = {"schema": "tms_portable_owner_grant_v1",
        "owner_authority_reference": request["owner_use"]["authority_reference"],
        "request": pin(request_raw), "generated_lock": pin(lock),
        "selected_manifest": pin(encode(selected)), "attempt_id": request["attempt_id"],
        "source_review": request["evidence"]["source_independent_review"],
        "runtime_admission": rt["admission"], "daemon_socket": rt["daemon_socket"],
        "daemon_guard": rt["daemon_guard"], "python": rt["python"],
        "complete_scope": {"regions": 12, "effects": 36, "omissions": 540},
        "owner_selected_execution": False}
    return {"schema": "tms_portable_plan_v1", "generated_lock": pin(lock),
        "source_reads": charged, "asset_body_reads": 0, "execution_selected": False,
        "changed_members": changed, "owner_grant_template": grant,
        "source_review_template": {"schema": "tms_portable_source_review_v1",
            "generated_lock": pin(lock), "whole_source_accepted": False},
        "runtime_admission_template": {"schema": "tms_portable_runtime_admission_v1",
            "generated_lock": pin(lock), "python": rt["python"],
            "daemon_socket": rt["daemon_socket"], "daemon_guard": rt["daemon_guard"],
            "image": cat["config_template"]["image"], "host": "Darwin",
            "python_version": "3.11.6", "docker_cli": "/usr/local/bin/docker",
            "selected_runtime_accepted": False, "clean_candidate_image_claim": False}}


def select(package_root, grant_raw):
    """Record a trusted owner's exact once-selected operation; never launch it."""
    need(len(grant_raw) <= 65536, "grant size")
    root = path_text(str(package_root))
    request_raw = read_source(root / "PROVISION_REQUEST.private.json", cap=65536)
    request = decode(request_raw)
    need(request["package_root"] == str(root), "original package location")
    lock_raw = read_source(root / "EXECUTION_LOCK.json", cap=65536)
    wrapper_raw = read_source(root / "UNSELECTED_RUN.private.json", cap=65536)
    report = decode(read_source(root / "PROVISION_RESULT.private.json", cap=65536))
    need(report["request"] == pin(request_raw) and report["generated_lock"] == pin(lock_raw) and
         report["unselected_manifest"] == pin(wrapper_raw), "exact prepared binding")
    lock = decode(lock_raw)
    need(set(lock) == {"schema","members"} and
         lock["schema"] == "tms_fixed_regions_whole_owner_lock_v1" and
         set(lock["members"]) == set(catalog()["source_members"]), "complete generated closure")
    total = len(lock_raw)
    for name, expected in lock["members"].items():
        total += expected["bytes"]
        need(total <= SOURCE_LIMIT, "selection source cap")
        read_source(root / name, expected)
    wrapper = decode(wrapper_raw)
    need(wrapper["selection"]["root_execution_selected"] is False, "unselected original")
    wrapper["selection"]["root_execution_selected"] = True
    selected_raw = encode(wrapper)
    grant = decode(grant_raw)
    expected = {"schema": "tms_portable_owner_grant_v1",
        "owner_authority_reference": request["owner_use"]["authority_reference"],
        "request": pin(request_raw), "generated_lock": pin(lock_raw),
        "selected_manifest": pin(selected_raw), "attempt_id": request["attempt_id"],
        "source_review": request["evidence"]["source_independent_review"],
        "runtime_admission": request["runtime"]["admission"],
        "daemon_socket": request["runtime"]["daemon_socket"],
        "daemon_guard": request["runtime"]["daemon_guard"],
        "python": request["runtime"]["python"],
        "complete_scope": {"regions": 12, "effects": 36, "omissions": 540},
        "owner_selected_execution": True}
    need(encode(grant) == encode(expected), "exact owner grant")
    # Evidence must bind this rendered package and runtime; old image acceptance is
    # only inherited provenance. These are trusted operator attestations, not signatures.
    review = decode(read_source(grant["source_review"]["path"], descriptor(grant["source_review"])))
    need(encode(review) == encode({"schema": "tms_portable_source_review_v1",
         "generated_lock": pin(lock_raw), "whole_source_accepted": True}), "fresh rendered-source review")
    runtime = decode(read_source(grant["runtime_admission"]["path"],
                                 descriptor(grant["runtime_admission"])))
    need(encode(runtime) == encode({"schema": "tms_portable_runtime_admission_v1",
         "generated_lock": pin(lock_raw), "python": grant["python"],
         "daemon_socket": grant["daemon_socket"], "daemon_guard": grant["daemon_guard"],
         "image": catalog()["config_template"]["image"],
         "host": "Darwin", "python_version": "3.11.6",
         "docker_cli": "/usr/local/bin/docker", "selected_runtime_accepted": True,
         "clean_candidate_image_claim": False}), "fresh explicit runtime admission")
    operation = path_text(request["operation_root"])
    need(not (operation / "attempts" / request["attempt_id"]).exists(), "no prior attempt")
    destination = operation / "selections" / (request["attempt_id"] + ".json")
    need(not destination.exists(), "one selected manifest")
    # Persist the exact grant before creating the source owner's selection file.
    write_new(operation / "selections" / (request["attempt_id"] + ".grant.json"), grant_raw)
    write_new(destination, selected_raw)
    return {"selection": {"path": str(destination), **pin(selected_raw)},
            "grant": pin(grant_raw),
            "argv": [grant["python"], "-I", "-S", "-B", str(root / "owner/outer_once.py"),
                     "--attempt-id", request["attempt_id"],
                     "--run-manifest-sha256", pin(selected_raw)["sha256"],
                     "--source-lock-sha256", pin(lock_raw)["sha256"]],
            "launch_performed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("plan", "build"):
        p = commands.add_parser(action)
        p.add_argument("--request", required=True)
        p.add_argument("--source-root", default=str(Path(__file__).absolute().parent.parent))
    p = commands.add_parser("select")
    p.add_argument("--package", required=True)
    p.add_argument("--grant", required=True)
    args = parser.parse_args(argv)
    started = time.monotonic()
    if args.action in ("plan", "build"):
        action = build if args.action == "build" else plan
        result = action(read_source(args.request, cap=65536), args.source_root)
    else:
        result = select(args.package, read_source(args.grant, cap=65536))
    result["provisioner_elapsed_seconds"] = time.monotonic() - started
    print(encode(result).decode(), end="")


if __name__ == "__main__":
    main()
