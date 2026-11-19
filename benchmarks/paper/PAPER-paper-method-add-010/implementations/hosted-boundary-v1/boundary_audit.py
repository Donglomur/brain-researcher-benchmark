"""Actual prelaunch audit for the selected generated MEG boundary exercise.

No I/O or native calls occur on import. collect_audit has no mock/observer input.
It uses the unchanged authenticated vendor engine.Docker for every Docker call.
Only its live, process-local AuditHandle can authorize exact audited exposures.
evaluate_observations is a separate pure source-control seam and cannot approve
an exposure. The evaluator host/daemon and independently reviewed policy/source
are trusted. This is not a complete image-filesystem absence or escape proof.
"""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import stat
import sys
import time
import types


IMAGE = "sha256:cf2dad23925ed51a00735f57606b2998aedf4705a1634cb9ae1053b5c145d5ba"
MANIFEST = "sha256:e8c69d86735f6df3efa06b324694fe51f0422785f83a3bd463052636c2421944"
PULL_REFERENCE = "docker.io/library/python@" + MANIFEST
REGISTRY_PIN = {"bytes": 2507, "sha256": "245b8f68655362aae9e78bfa1cddca31b781ad0b8e9f0f136cbc84b9bf6fda1a"}
TRANSPORT_PIN = {"bytes": 21159, "sha256": "b87005243c9841eef911edb1d855e2fea2b891562766ba50cd6890e0e267ab8a"}
GENERIC_PIN = {"bytes": 12977, "sha256": "711cd419eed9b0f78ecb4a846f13a3c843808060814055fe50ff2b94f8b70857"}
VENDOR_PIN = {"bytes": 987, "sha256": "335f696f47529a115479f543c62cbcab12d12c02f8a62606b8dc133ae92333c4"}
AUTHENTIC_INVENTORY_SHA256 = "80b16614e7654a4b0efaafced5abb251ab17e625f264c66c87c0c8658737fa2d"
CONSTANT_PIN = {"bytes": 834, "sha256": "d2d7c498503adeb9c1111f6968bf45e788912ecaad5c91ad33d92acfde49cbf5"}
CLI_CAPS = {"audit_version": 131072, "audit_info": 131072, "audit_image": 131072}
POLICY = {
    "schema": "meg-generated-boundary-audit-policy/v1",
    "image": IMAGE, "immutable_pull_reference": PULL_REFERENCE,
    "operator": "Linux Ubuntu24.04 amd64, procfs/pidfd-owned local Docker CLI",
    "inventory_kind": "actual image identity/configuration/environment/rootfs-layer metadata",
    "filesystem_content_absence_established": False,
    "scope": "generated fixture mount/configuration and positive host-canary custody only",
    "role_policy": "A has no author mount; B has one readonly author mount",
    "candidate_behavior_requires_separate_probe": True,
    "original_data_or_scoring_permitted": False,
    "audit_containers_created": 0,
    "image_environment_allowed_keys": ["PATH", "LANG", "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256"],
    "max_cli_binary_bytes": 67108864,
    "max_audit_cli_calls": 3, "max_audit_cli_response_bytes": 393216,
    "max_private_panel_bytes": 262144, "max_sentinel_bytes": 256,
    "max_public_file_bytes": 1048576, "max_audit_artifact_bytes": 524288,
    "max_observer_resources": 24,
    "claims_excluded": ["full production coordinator/admission/scoring", "scientific result",
                        "all image content absence", "universal hostile-code isolation"],
}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


AUDIT_POLICY_PIN = pin(encoded(POLICY))
_ISSUED = object()


def need(value, message):
    if not value:
        raise ValueError(message)


def _fields(value, names, message):
    need(type(value) is dict and set(value) == set(names), message)


def _descriptor(value):
    _fields(value, ("bytes", "sha256"), "exact byte/hash descriptor")
    need(type(value["bytes"]) is int and value["bytes"] > 0
         and type(value["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", value["sha256"]),
         "positive bounded file descriptor")
    return value


def _path(value):
    need(type(value) in (str, Path) or isinstance(value, Path), "path string required")
    result = Path(value)
    need(result.is_absolute() and ".." not in result.parts
         and not any(c in str(result) for c in (",", "\n", "\r", "\0"))
         and not any(p.is_symlink() for p in (result, *result.parents)), "canonical unlinked absolute path")
    return result


def _signature(value):
    return [getattr(value, name) for name in
            ("st_dev", "st_ino", "st_mode", "st_size", "st_nlink", "st_uid", "st_gid", "st_mtime_ns", "st_ctime_ns")]


class _Budget:
    """Audit I/O accounting; process and Docker capture ownership stay in vendor."""
    def __init__(self, read_limit, write_limit, deadline):
        need(type(read_limit) is int and read_limit > 0 and type(write_limit) is int and write_limit > 0,
             "positive explicit audit byte limits")
        need(type(deadline) in (int, float) and math.isfinite(deadline) and time.monotonic() < deadline,
             "live original audit deadline")
        self.read_limit, self.write_limit, self.deadline = read_limit, write_limit, deadline
        self.read_bytes = self.write_reserved_bytes = self.write_bytes = 0
        self.vendor_bootstrap_read_charge = 0

    def tick(self):
        need(time.monotonic() < self.deadline, "original audit deadline")

    def ensure_read(self, count):
        self.tick()
        need(type(count) is int and count >= 0 and self.read_bytes + count <= self.read_limit,
             "audit read ceiling")

    def read(self, count):
        self.ensure_read(count)
        self.read_bytes += count

    def write(self, count):
        self.tick()
        need(type(count) is int and count >= 0 and self.write_reserved_bytes + count <= self.write_limit,
             "audit write ceiling")
        self.write_reserved_bytes += count

    def wrote(self, count):
        self.write_bytes += count

    def counters(self):
        return {"read_charged_bytes": self.read_bytes, "write_reserved_bytes": self.write_reserved_bytes,
                "written_bytes": self.write_bytes, "vendor_bootstrap_read_charge": self.vendor_bootstrap_read_charge,
                "physical_io_measured": False, "external_publish_callback_bytes_included": False}


def _file(path, budget, cap, expected=None, *, retain=True, mode=None):
    path = _path(path)
    if expected is not None:
        _descriptor(expected)
        need(expected["bytes"] <= cap, "file declaration exceeds audit cap")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             "bounded singly linked regular file")
        if mode is not None:
            need(before.st_uid == os.geteuid() and stat.S_IMODE(before.st_mode) == mode, "exact audit file mode/owner")
        if expected is not None:
            need(before.st_size == expected["bytes"], "declared file extent")
        budget.ensure_read(before.st_size + 1)
        digest, pieces, count = hashlib.sha256(), [], 0
        while True:
            budget.tick()
            block = os.read(fd, min(65536, before.st_size + 1 - count))
            budget.read(len(block))
            if not block:
                break
            count += len(block)
            need(count <= before.st_size, "file grew during observation")
            digest.update(block)
            if retain:
                pieces.append(block)
        need(count == before.st_size and _signature(before) == _signature(os.fstat(fd)) == _signature(path.lstat()),
             "stable complete file observation")
        observed = {"bytes": count, "sha256": digest.hexdigest()}
        need(expected is None or observed == expected, "file identity mismatch")
        return b"".join(pieces) if retain else None, observed, _signature(before)
    finally:
        os.close(fd)


def _decoded(body):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, "nonfinite JSON"))


def _expected(value):
    _fields(value, ("schema", "attempt_id", "source_manifest", "registry_metadata", "docker_binary", "docker_socket",
                    "image", "immutable_pull_reference", "fixture_sha256", "fixture_not_before_unix", "policy_sha256"),
            "complete independently frozen audit bindings")
    need(value["schema"] == "meg-boundary-audit-expected/v1" and type(value["attempt_id"]) is str
         and re.fullmatch("[A-Za-z0-9_-]{1,64}", value["attempt_id"]), "audit schema/attempt identity")
    _descriptor(value["source_manifest"])
    _fields(value["registry_metadata"], ("path", "pin"), "registry metadata descriptor")
    need(value["registry_metadata"]["pin"] == REGISTRY_PIN, "selected official registry metadata pin")
    need(value["image"] == IMAGE and value["immutable_pull_reference"] == PULL_REFERENCE,
         "selected immutable manifest and config/image identity")
    need(value["policy_sha256"] == AUDIT_POLICY_PIN["sha256"], "independently selected policy source")
    need(type(value["fixture_sha256"]) is str and re.fullmatch("[0-9a-f]{64}", value["fixture_sha256"]),
         "frozen generated fixture view identity")
    need(type(value["fixture_not_before_unix"]) in (int, float)
         and math.isfinite(value["fixture_not_before_unix"]) and value["fixture_not_before_unix"] > 0,
         "original pre-builder timestamp")
    return value


def _module(name, path, body):
    value = types.ModuleType(name)
    value.__file__ = str(path)
    exec(compile(body, str(path), "exec"), value.__dict__)
    return value


def _load_sources(source_root, expected, budget):
    root = _path(source_root)
    manifest_raw, _, _ = _file(root / "SOURCE_MANIFEST.json", budget, 32768, expected["source_manifest"])
    manifest = _decoded(manifest_raw)
    need(manifest.get("schema") == "meg-paired-program-source-manifest/v1"
         and type(manifest.get("files")) is dict, "selected paired source manifest")
    for name, want in (("transport.py", TRANSPORT_PIN), ("generic_contract.py", GENERIC_PIN),
                       ("vendor_transport/SOURCE_MANIFEST.json", VENDOR_PIN)):
        need(manifest["files"].get(name) == want, "unchanged selected source: " + name)
    transport_body, _, _ = _file(root / "transport.py", budget, 65536, TRANSPORT_PIN)
    generic_body, _, _ = _file(root / "generic_contract.py", budget, 65536, GENERIC_PIN)
    vendor_raw, _, _ = _file(root / "vendor_transport/SOURCE_MANIFEST.json", budget, 4096, VENDOR_PIN)
    vendor_manifest = _decoded(vendor_raw)
    need(vendor_manifest.get("schema") == "osl_transport_source_manifest_v1"
         and set(vendor_manifest["files"]) == {"__init__.py", "engine.py", "bounds.py", "contract.py", "archive.py", "holder.py", "provider.py"},
         "unchanged complete vendor closure")
    for name, want in vendor_manifest["files"].items():
        _descriptor(want)
        need(manifest["files"].get("vendor_transport/" + name) == want, "vendor source-manifest join")
    # Existing _vendor reads/compiles its exact pinned closure. Reserve its full
    # known byte extent prospectively; retain that charge even on failed loading.
    charge = VENDOR_PIN["bytes"] + sum(p["bytes"] for p in vendor_manifest["files"].values())
    budget.read(charge)
    budget.vendor_bootstrap_read_charge += charge
    transport = _module("_meg_boundary_transport", root / "transport.py", transport_body)
    vendor = transport._vendor()
    generic = _module("_meg_boundary_generic", root / "generic_contract.py", generic_body)
    return transport, vendor, generic


def _observe_host(budget):
    # procfs reports zero st_size for this nonempty virtual file. Do not route
    # it through the ordinary exact-extent source/artifact reader.
    budget.ensure_read(129)
    fd = os.open("/proc/sys/kernel/random/boot_id", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(stat.S_ISREG(os.fstat(fd).st_mode), "ordinary procfs boot metadata")
        pieces, total = [], 0
        while True:
            budget.tick()
            part = os.read(fd, 129 - total)
            budget.read(len(part))
            if not part:
                break
            total += len(part)
            need(total <= 128, "bounded complete procfs boot identity")
            pieces.append(part)
        boot = b"".join(pieces)
        need(boot, "nonempty actual boot identity")
    finally:
        os.close(fd)
    release_path = Path("/etc/os-release").resolve(strict=True)
    release, release_pin, _ = _file(release_path, budget, 16384)
    values = {}
    for line in release.decode().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            need(key not in values, "unique os-release keys")
            values[key] = value.strip('"')
    return {"system": platform.system(), "sys_platform": sys.platform, "machine": platform.machine(),
            "uid": os.geteuid(), "pid": os.getpid(), "boot_id": boot.decode().strip(),
            "pidfd_apis_available": hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"),
            "os_release": {"ID": values.get("ID"), "VERSION_ID": values.get("VERSION_ID")},
            "os_release_pin": release_pin}


def _observe_docker(vendor, expected, budget, journal):
    docker = vendor.engine.Docker(expected["docker_binary"], expected["docker_socket"], max_calls=3,
        reply_budget=sum(CLI_CAPS.values()), phase_caps=CLI_CAPS, publish=journal,
        account_read=budget.read, reserve_read=budget.ensure_read)
    observations = {}
    for key, phase, command in (
        ("version", "audit_version", ["version", "--format", "{{json .}}"]),
        ("info", "audit_info", ["info", "--format", "{{json .}}"]),
        ("image", "audit_image", ["image", "inspect", expected["image"], "--format", "{{json .}}"]),
    ):
        raw = docker(command, min(budget.deadline, time.monotonic() + 15), phase, CLI_CAPS[phase])
        observations[key] = vendor.engine.parse(raw)
    vendor.engine.validate_cli_records(docker.records, CLI_CAPS)
    need(docker.reaped is True and len(docker.records) == 3, "all genuine audit CLI groups closed")
    return observations, deepcopy(docker.records)


def _validate_observations(expected, observations):
    _expected(expected)
    _fields(observations, ("schema", "host", "docker", "cli_records", "cli_children", "started", "finished",
                           "deadline", "docker_binary", "docker_socket", "binary_unchanged", "socket_unchanged"),
            "complete observation schema")
    need(observations["schema"] == "meg-boundary-actual-observations/v1", "observation schema")
    host = observations["host"]
    need(type(host) is dict and host.get("system") == "Linux" and type(host.get("sys_platform")) is str
         and host["sys_platform"].startswith("linux")
         and host.get("machine") in ("x86_64", "amd64") and host.get("pidfd_apis_available") is True
         and host.get("os_release") == {"ID": "ubuntu", "VERSION_ID": "24.04"}, "selected actual Linux operator")
    need(type(host.get("uid")) is int and host["uid"] >= 0 and type(host.get("pid")) is int and host["pid"] > 1
         and type(host.get("boot_id")) is str
         and re.fullmatch("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", host["boot_id"]),
         "actual operator identity")
    for key in ("started", "finished", "deadline"):
        need(type(observations[key]) in (int, float) and math.isfinite(observations[key]), "finite observation timing")
    need(0 <= observations["started"] <= observations["finished"] < observations["deadline"], "original observation cutoff")
    need(observations["binary_unchanged"] is True and observations["socket_unchanged"] is True,
         "unchanged actual CLI/socket custody")
    need(observations["docker_binary"]["path"] == expected["docker_binary"]
         and observations["docker_socket"]["path"] == expected["docker_socket"], "exact selected CLI/socket")
    _descriptor(observations["docker_binary"]["pin"])
    docker = observations["docker"]
    _fields(docker, ("version", "info", "image"), "complete actual Docker observations")
    version, info, image = docker["version"], docker["info"], docker["image"]
    need(type(version) is dict and all(type(version.get(role)) is dict
         and version[role].get("Os") == "linux" and version[role].get("Arch") == "amd64"
         and type(version[role].get("Version")) is str and version[role]["Version"] for role in ("Client", "Server")),
         "actual Linux amd64 local client and daemon version")
    need(type(info) is dict and info.get("OSType") == "linux" and info.get("Architecture") in ("x86_64", "amd64")
         and str(info.get("CgroupVersion")) == "2" and type(info.get("ID")) is str and info["ID"],
         "actual local Linux cgroup-v2 daemon")
    need(type(image) is dict and image.get("Id") == IMAGE and image.get("Os") == "linux"
         and image.get("Architecture") == "amd64", "actual selected immutable installed image")
    digests = image.get("RepoDigests")
    need(type(digests) is list and any(type(d) is str and d.split("@", 1)[0] in
         ("python", "library/python", "docker.io/library/python", "registry-1.docker.io/library/python")
         and d.endswith("@" + MANIFEST) for d in digests), "installed official platform-manifest join")
    config = image.get("Config")
    need(type(config) is dict and not config.get("Volumes")
         and (not config.get("Healthcheck") or (type(config["Healthcheck"]) is dict
                                                and config["Healthcheck"].get("Test") == ["NONE"])),
         "no implicit image volumes or health process")
    need(type(config.get("Env")) is list, "complete image environment observed")
    environment = {}
    for item in config["Env"]:
        need(type(item) is str and 0 < len(item) <= 8192 and "=" in item and "\0" not in item, "bounded image environment")
        key, value = item.split("=", 1)
        need(key not in environment and key in POLICY["image_environment_allowed_keys"], "reviewed image environment keys only")
        environment[key] = value
    need("PATH" in environment and environment.get("PYTHON_VERSION", "").startswith("3.11."), "selected Python image environment")
    rootfs = image.get("RootFS")
    need(type(rootfs) is dict and rootfs.get("Type") == "layers" and type(rootfs.get("Layers")) is list
         and len(rootfs["Layers"]) == 4 and all(type(x) is str and re.fullmatch("sha256:[0-9a-f]{64}", x)
                                                for x in rootfs["Layers"]), "complete observed four-layer image metadata")
    records = observations["cli_records"]
    need(type(records) is list and len(records) == 3 and all(type(r) is dict for r in records)
         and [r.get("phase") for r in records] == list(CLI_CAPS), "all three ordered actual CLI observations")
    for row in records:
        _fields(row, ("phase", "returncode", "error_type", "observed_retained_bytes", "seconds", "client_reaped",
                      "cleanup_complete", "cleanup_before_original_cutoff", "owned_group_absence_observed",
                      "leader_exited_with_group_alive", "group_probe_or_cleanup_error"), "complete observed CLI custody fields")
        need(type(row.get("returncode")) is int and row["returncode"] == 0 and row.get("error_type") is None
             and row.get("group_probe_or_cleanup_error") is None and row.get("leader_exited_with_group_alive") is False,
             "successful exact audit CLI")
        need(all(row.get(k) is True for k in ("client_reaped", "cleanup_complete", "cleanup_before_original_cutoff", "owned_group_absence_observed")),
             "known complete audit CLI custody")
        need(type(row.get("observed_retained_bytes")) is int and 0 <= row["observed_retained_bytes"] <= CLI_CAPS[row["phase"]], "bounded actual CLI capture")
        need(type(row["seconds"]) in (int, float) and math.isfinite(row["seconds"]) and row["seconds"] >= 0,
             "finite actual CLI duration")
    children = observations["cli_children"]
    need(type(children) is list and len(children) == 3 and all(type(r) is dict for r in children),
         "all three genuine gated CLI identities")
    for index, row in enumerate(children):
        token = row.get("process_identity", {})
        need(type(token) is dict and type(row.get("index")) is int and row["index"] == index
             and row.get("phase") == list(CLI_CAPS)[index]
             and row.get("docker_exec_still_gated") is True and row.get("independent_group") is True
             and token.get("schema") == "osl_linux_process_identity_v1"
             and type(token.get("pid")) is int and token["pid"] > 1
             and token["pid"] == token.get("pgid") == token.get("session_id") == row.get("pid") == row.get("pgid")
             and type(token.get("uid")) is int and token["uid"] == host["uid"] and token.get("boot_id") == host["boot_id"]
             and type(token.get("start_time_ticks")) is int and token["start_time_ticks"] > 0,
             "genuine anchored Linux process observations")
    return environment


def evaluate_observations(expected_bindings, observations):
    """Pure explicitly mocked source-control evaluation; never native approval."""
    _validate_observations(expected_bindings, observations)
    return {"schema": "meg-boundary-observation-source-control/v1", "evidence_kind": "mock_source_control",
            "observations_valid": True, "native_audit": False, "role_boundary_verified": False}


def _fixture(expected, fixture, transport, vendor, generic, budget):
    _fields(fixture, ("schema", "provenance", "fixture_root", "private", "campaigns"), "complete generated audit fixture")
    need(fixture["schema"] == "meg-boundary-audit-fixture/v1" and fixture["provenance"] == "generated_only"
         and pin(encoded(fixture))["sha256"] == expected["fixture_sha256"], "frozen honest generated fixture")
    root = _path(fixture["fixture_root"])
    need(root.is_dir() and root.stat().st_uid == os.geteuid() and stat.S_IMODE(root.stat().st_mode) == 0o700, "private owned fixture root")
    _fields(fixture["private"], ("sentinel", "panel"), "private generated fixture inputs")
    private, observed, secret = {}, {}, None
    now = time.time()
    for name in ("sentinel", "panel"):
        item = fixture["private"][name]
        _fields(item, ("path", "pin"), "private fixture descriptor")
        path = _path(item["path"])
        need(path.is_relative_to(root) and path.parent != root, "private fixture subdirectory")
        cap = POLICY["max_sentinel_bytes"] if name == "sentinel" else POLICY["max_private_panel_bytes"]
        raw, actual, signature = _file(path, budget, cap, item["pin"], mode=0o600)
        need(expected["fixture_not_before_unix"] <= signature[-2] / 1e9 <= now
             and expected["fixture_not_before_unix"] <= signature[-1] / 1e9 <= now,
             "private generated file observed after original builder-start time")
        private[name] = path
        observed[name] = {"path": str(path), "pin": actual, "signature": signature}
        if name == "sentinel":
            need(32 <= len(raw) <= cap, "bounded nontrivial fresh generated sentinel")
            secret = raw.strip()
    need(private["sentinel"].parent == private["panel"].parent, "one excluded generated private directory")
    private_root = private["sentinel"].parent
    need(private_root.stat().st_uid == os.geteuid() and stat.S_IMODE(private_root.stat().st_mode) == 0o700,
         "private generated directory mode")
    _fields(fixture["campaigns"], ("constant", "probe"), "two separately frozen engineering campaigns")
    approved, seen, context_ids = [], set(), {}
    for kind in ("constant", "probe"):
        campaign = fixture["campaigns"][kind]
        _fields(campaign, ("programme_pin", "mounts"), "frozen campaign audit view")
        _descriptor(campaign["programme_pin"])
        _fields(campaign["mounts"], ("0", "4"), "both selected fold contexts")
        for fold in ("0", "4"):
            pair = campaign["mounts"][fold]
            _fields(pair, ("A", "B"), "both assistance roles")
            for role in ("A", "B"):
                mounts = pair[role]
                transport.validate_mounts(role, mounts, campaign["programme_pin"])
                need("/input/FEATURES.npy" in mounts, "explicit generated scalar mode")
                if kind == "constant":
                    need(mounts["/program"]["files"]["submission.py"] == CONSTANT_PIN, "unchanged constant programme")
                for target, desc in mounts.items():
                    path = _path(desc["path"])
                    need(path.is_relative_to(root) and path != root and not path.is_relative_to(private_root)
                         and not private_root.is_relative_to(path), "public mount excludes the private fixture tree")
                    key = encoded(desc)
                    if key not in seen:
                        vendor.bounds.tree(desc, budget)
                        leaves = [path / name for name in desc["files"]] if desc["kind"] == "directory" else [path]
                        for leaf in leaves:
                            s = leaf.lstat()
                            need(s.st_uid == os.geteuid() and stat.S_IMODE(s.st_mode) == 0o444
                                 and [s.st_dev, s.st_ino] not in [v["signature"][:2] for v in observed.values()],
                                 "sealed public file distinct from private inodes")
                        seen.add(key)
                context_desc = mounts["/input/CONTEXT.json"]
                context_raw, _, _ = _file(context_desc["path"], budget, 131072, context_desc["files"]["CONTEXT.json"])
                context = generic.checked_context(_decoded(context_raw))
                need(context["fold"] == int(fold) and len(context["queries"]) == (20 if fold == "0" else 18)
                     and context["source_binding"]["sha256"] != AUTHENTIC_INVENTORY_SHA256,
                     "generated identity and selected20/18 query batches")
                need(fold not in context_ids or context_ids[fold] == context["context_sha256"], "same generated fold context across roles/campaigns")
                context_ids[fold] = context["context_sha256"]
                paper = mounts["/paper"]
                body, _, _ = _file(Path(paper["path"]) / "PAPER.bin", budget, 16384, paper["files"]["PAPER.bin"])
                need(str(private["sentinel"]).encode() in body and secret not in body
                     and observed["sentinel"]["pin"]["sha256"].encode() not in body,
                     "paper contains only designated private path, not sentinel value/hash")
                approved.append({"kind": kind, "fold": int(fold), "role": role,
                                 "programme_pin": deepcopy(campaign["programme_pin"]), "mounts": deepcopy(mounts)})
            need({k: v for k, v in pair["B"].items() if k != "/author"} == pair["A"], "identical A/B common mounts")
    return approved, {"generated_only": True, "private_positive_control": observed,
                      "private_value_published": False, "public_mount_descriptors": len(seen),
                      "context_sha256_by_fold": context_ids, "approval_count": len(approved)}


class AuditHandle:
    """A live native observation capability, deliberately not restorable from JSON."""
    def __init__(self, token, values, approved, deadline, vendor, budget, expected):
        need(token is _ISSUED, "actual observer-issued audit handle only")
        self._values, self._approved = deepcopy(values), deepcopy(approved)
        self._deadline, self._vendor, self._budget = deadline, vendor, budget
        self._expected, self._pid = deepcopy(expected), os.getpid()
        self._token = token

    def __getitem__(self, key):
        if key == "accounting":
            return deepcopy(self._budget.counters())
        return deepcopy(self._values[key])

    def get(self, key, default=None):
        if key == "accounting":
            return self[key]
        return deepcopy(self._values.get(key, default))

    def as_dict(self):
        return {**deepcopy(self._values), "accounting": self["accounting"]}


def _live(audit):
    need(type(audit) is AuditHandle and audit._token is _ISSUED and audit._pid == os.getpid(),
         "same-process actual native audit handle; cached/dict reports cannot approve")
    need(time.monotonic() < audit._deadline, "audit original deadline has not expired")
    _file(audit._values["audit_path"], audit._budget, POLICY["max_audit_artifact_bytes"], audit._values["audit_pin"], mode=0o600)


def audit_environment(source_root, output_root, expected_bindings, fixture, deadline, read_limit, write_limit, publish):
    """Observe actual host/daemon/image and generated mounts; never launches containers."""
    expected = deepcopy(_expected(expected_bindings))
    need(callable(publish), "bounded owner journal callback required")
    budget = _Budget(read_limit, write_limit, deadline)
    started = time.monotonic()
    root = _path(output_root)
    need(not root.exists() and root.parent.is_dir(), "fresh audit output directory")
    root.mkdir(mode=0o700)
    transport, vendor, generic = _load_sources(source_root, expected, budget)
    policy_path = Path(__file__).with_name("AUDIT_POLICY.json")
    _file(policy_path, budget, 16384, AUDIT_POLICY_PIN)
    registry_raw, _, _ = _file(expected["registry_metadata"]["path"], budget, 8192, REGISTRY_PIN)
    registry = _decoded(registry_raw)
    need(registry.get("immutable_pull_reference") == PULL_REFERENCE
         and registry.get("prospective_local_image_id") == IMAGE
         and registry.get("platform") == {"architecture": "amd64", "os": "linux"}, "selected cached registry binding; not native evidence")
    host = _observe_host(budget)
    need(host["system"] == "Linux" and host["pidfd_apis_available"] is True, "genuine Linux/pidfd operator before any Docker call")
    binary = _path(expected["docker_binary"])
    _, binary_pin, binary_signature = _file(binary, budget, POLICY["max_cli_binary_bytes"], retain=False)
    need(binary_signature[2] & 0o111 and not binary_signature[2] & 0o022, "ordinary executable nonwritable CLI")
    socket = _path(expected["docker_socket"])
    socket_signature = _signature(socket.lstat())
    need(stat.S_ISSOCK(socket_signature[2]), "existing canonical local Unix daemon socket")
    cli_children, journal_index = [], 0
    def journal(name, value):
        nonlocal journal_index
        need(journal_index < 32, "bounded audit ownership journal")
        body = encoded({"schema": "meg-boundary-audit-journal/v1", "event": name, "value": value})
        need(len(body) <= 16384, "bounded audit ownership event")
        saved = vendor.bounds.publish(root / (f"{journal_index:03d}-" + name + ".json"), body, budget)
        journal_index += 1
        if name == "CLI-CHILD":
            cli_children.append(deepcopy(value))
        publish(name, {"pin": saved, "value": value})
    try:
        docker, cli_records = _observe_docker(vendor, expected, budget, journal)
        _, after_binary_pin, after_signature = _file(binary, budget, POLICY["max_cli_binary_bytes"], binary_pin, retain=False)
        observations = {"schema": "meg-boundary-actual-observations/v1", "host": host, "docker": docker,
            "cli_records": cli_records, "cli_children": cli_children, "started": started, "finished": time.monotonic(), "deadline": deadline,
            "docker_binary": {"path": str(binary), "pin": binary_pin, "signature": binary_signature},
            "docker_socket": {"path": str(socket), "signature": socket_signature},
            "binary_unchanged": binary_pin == after_binary_pin and binary_signature == after_signature,
            "socket_unchanged": socket_signature == _signature(socket.lstat())}
        _validate_observations(expected, observations)
        approved, fixture_evidence = _fixture(expected, fixture, transport, vendor, generic, budget)
        inventory = {"schema": "meg-observed-image-metadata-inventory/v1", "kind": POLICY["inventory_kind"],
                     "actual_image_inspect": docker["image"], "registry_metadata": REGISTRY_PIN,
                     "filesystem_content_inventory_performed": False, "filesystem_content_absence_established": False}
        inventory_pin = vendor.bounds.publish(root / "IMAGE_INVENTORY.json", encoded(inventory), budget)
        observation_pin = vendor.bounds.publish(root / "OBSERVATIONS.json", encoded(observations), budget)
        # Reauthenticate the externally selected source and policy after collection.
        _file(Path(source_root) / "SOURCE_MANIFEST.json", budget, 32768, expected["source_manifest"])
        _file(policy_path, budget, 16384, AUDIT_POLICY_PIN)
        record = {"schema": "meg-actual-generated-boundary-audit/v1", "status": "observed",
            "native_observations": True, "attempt_id": expected["attempt_id"], "expected": expected,
            "policy": AUDIT_POLICY_PIN, "inventory": inventory_pin, "observations": observation_pin,
            "fixture": fixture_evidence, "approved_exposure_commitments": [pin(encoded(x)) for x in approved],
            "original_deadline": deadline, "finished": time.monotonic(), "accounting_before_final_record": budget.counters(),
            "scope": POLICY["scope"], "filesystem_content_absence_established": False,
            "candidate_denial_behavior_established": False, "full_production_admission_qualified": False,
            "scientific_qualification": False, "containers_created": 0}
        raw = encoded(record)
        need(len(raw) <= POLICY["max_audit_artifact_bytes"], "bounded final audit record")
        audit_pin = vendor.bounds.publish(root / "AUDIT.json", raw, budget)
        budget.tick()
        values = {"audit_pin": audit_pin, "audit_path": str(root / "AUDIT.json"),
                  "inventory_sha256": inventory_pin["sha256"], "inventory_pin": inventory_pin,
                  "cli_records": cli_records, "observations_pin": observation_pin,
                  "docker_context": {"binary": str(binary), "socket": str(socket), "image": IMAGE,
                                     "daemon_id": docker["info"]["ID"]}, "accounting": budget.counters(),
                  "source_manifest": expected["source_manifest"], "scope": POLICY["scope"]}
        return AuditHandle(_ISSUED, values, approved, deadline, vendor, budget, expected)
    except BaseException as error:
        failure = {"schema": "meg-boundary-audit-failure/v1", "error_type": type(error).__name__,
                   "native_approval_issued": False, "containers_created": 0, "cli_children": cli_children,
                   "accounting": budget.counters(), "automatic_retry": False}
        try:
            vendor.bounds.publish(root / "FAILURE.json", encoded(failure), budget)
        except BaseException:
            pass
        raise


collect_audit = audit_environment


def approve_exposure(audit, role, mounts, programme_pin):
    """Approve only an exact currently audited generated exposure, not a Boolean."""
    _live(audit)
    need(role in ("A", "B"), "selected assistance role")
    matches = [row for row in audit._approved if row["role"] == role and row["mounts"] == mounts
               and row["programme_pin"] == programme_pin]
    need(len(matches) == 1, "exact independently audited role/programme/mount descriptor required")
    return {"image_inventory_sha256": audit["inventory_sha256"], "boundary_audit": audit["audit_pin"],
            "role_boundary_verified": True}


authorize_exposure = approve_exposure


def owners_from_ownership(document):
    """Caller authenticates the ownership body/pin and complete campaign roster."""
    _fields(document, ("schema", "phase_id", "request_pin", "engine_source_pin", "original_deadline", "phase_deadline",
                       "attempt_prefix", "resources"), "exact retained Provider ownership")
    need(document["schema"] == "osl_phase_ownership_v1" and document["engine_source_pin"] == VENDOR_PIN,
         "selected actual ownership schema/source")
    _descriptor(document["request_pin"])
    need(type(document["phase_id"]) is str and re.fullmatch("[A-Za-z0-9_-]{1,96}", document["phase_id"]),
         "exact retained phase identity")
    need(all(type(document[key]) in (int, float) and math.isfinite(document[key])
             for key in ("original_deadline", "phase_deadline"))
         and 0 < document["phase_deadline"] <= document["original_deadline"], "retained original ownership clock")
    prefix = document["attempt_prefix"]
    need(type(prefix) is str and re.fullmatch("osl-[0-9a-f]{24}", prefix), "exact retained owner prefix")
    _fields(document["resources"], ("volume", "holder", "producer"), "complete retained resource plan")
    result = []
    for label in ("producer", "holder", "volume"):
        row = document["resources"][label]
        expected = {"kind": "volume" if label == "volume" else "container", "name": prefix + "-" + label,
                    "owner": prefix + "/" + label, "attempted": False, "acknowledged": False}
        need(type(row) is dict and row == expected and row["attempted"] is False and row["acknowledged"] is False,
             "exact immutable planned resource, no guessed ownership")
        result.append({key: row[key] for key in ("kind", "name", "owner")})
    return result


def observe_owned_resources(audit, resources, output_root, deadline, read_limit, write_limit, publish):
    """Read-only final absence observation; never removes or signals resources."""
    _live(audit)
    need(deadline <= audit._deadline and callable(publish), "observer inside current audit deadline")
    need(type(resources) is list and 0 < len(resources) <= POLICY["max_observer_resources"], "bounded exact owned resource roster")
    seen = set()
    for row in resources:
        _fields(row, ("kind", "name", "owner"), "owned resource identity")
        need(type(row["name"]) is str and re.fullmatch("osl-[0-9a-f]{24}-(producer|holder|volume)", row["name"]), "exact owned name")
        prefix, label = row["name"].rsplit("-", 1)
        need(row["owner"] == prefix + "/" + label and row["kind"] == ("volume" if label == "volume" else "container")
             and row["name"] not in seen, "unique retained owner/kind/name")
        seen.add(row["name"])
    root = _path(output_root)
    need(not root.exists() and root.parent.is_dir(), "fresh observer output directory")
    root.mkdir(mode=0o700)
    budget, vendor = _Budget(read_limit, write_limit, deadline), audit._vendor
    caps = {"absence_" + kind + "_" + selector: 8192 for kind in ("container", "volume") for selector in ("owner", "name")}
    index = 0
    def journal(name, value):
        nonlocal index
        need(index < 128, "bounded final observation journal")
        raw = encoded({"schema": "meg-boundary-final-observer-journal/v1", "event": name, "value": value})
        need(len(raw) <= 16384, "bounded observer ownership event")
        saved = vendor.bounds.publish(root / (f"{index:03d}-" + name + ".json"), raw, budget)
        index += 1
        publish(name, {"pin": saved, "value": value})
    context = audit["docker_context"]
    docker = vendor.engine.Docker(context["binary"], context["socket"], max_calls=2 * len(resources),
        reply_budget=16384 * len(resources), phase_caps=caps, publish=journal,
        account_read=budget.read, reserve_read=budget.ensure_read)
    rows = []
    for resource in resources:
        found = vendor.engine.resource_inventory(docker, resource, resource["owner"], deadline, "absence_" + resource["kind"])
        rows.append({**resource, "observed_members": found, "absence_observed": found == []})
    vendor.engine.validate_cli_records(docker.records, caps)
    need(docker.reaped is True and len(docker.records) == 2 * len(resources)
         and all(row["absence_observed"] for row in rows), "every retained owned resource actually absent")
    result = {"schema": "meg-actual-boundary-final-resource-observation/v1", "native_observations": True,
              "audit_pin": audit["audit_pin"], "resources": rows, "all_exact_owned_resources_absent": True,
              "cli_records": docker.records, "original_deadline": deadline, "finished": time.monotonic(),
              "accounting_before_final_record": budget.counters(), "resource_deletion_or_recovery_performed": False,
              "absence_does_not_resolve_unknown_creation_outcomes": True,
              "worker_pid_absence_established_here": False, "campaign_roster_completeness_checked_by_caller": True}
    saved = vendor.bounds.publish(root / "ABSENCE.json", encoded(result), budget)
    budget.tick()
    return {"pin": saved, "path": str(root / "ABSENCE.json"), "cli_records": deepcopy(docker.records),
            "accounting": budget.counters(), "all_exact_owned_resources_absent": True}
