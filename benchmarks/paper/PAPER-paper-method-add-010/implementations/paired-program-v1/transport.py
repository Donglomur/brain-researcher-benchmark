"""MEG adapter for the exact owned Provider; construction is not run authority.

One instance is one outcome campaign: two frozen programmes and ten fresh folds
per programme. The concrete Provider, original deadline and cumulative I/O
ceilings are shared across all twenty phases. Scientific response admission and
protected scoring belong to the parent task contract, never this transport.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import types
import uuid


HERE = Path(__file__).resolve().parent
VENDOR_PIN = {"bytes": 987, "sha256": "335f696f47529a115479f543c62cbcab12d12c02f8a62606b8dc133ae92333c4"}
MODULES = ("engine", "bounds", "contract", "archive", "holder", "provider")
COMMAND = ["/usr/local/bin/python", "-I", "-B", "/program/candidate_wrapper.py"]
RESULT_LIMIT = 1024 * 1024
# Filled from the independently tested adjacent wrapper at this source cutoff.
WRAPPER_PIN = {"bytes": 9016, "sha256": "7b2469be0f2445152c2c405043bcf1023dd8203f304c764b79053bb69ad550d5"}
_VENDOR = None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def check_pin(value, *, allow_empty=False):
    require(type(value) is dict and set(value) == {"bytes", "sha256"}, "exact byte/hash descriptor")
    require(type(value["bytes"]) is int and (0 if allow_empty else 1) <= value["bytes"] <= 2**63 - 1,
            "bounded exact byte count")
    require(type(value["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]), "SHA256 descriptor")
    return value


def decode(raw):
    def unique(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def _read_exact(file, expected, maximum):
    check_pin(expected)
    require(expected["bytes"] <= maximum, "bounded declared extent")
    file = Path(file)
    fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        first = os.fstat(fd)
        require(stat.S_ISREG(first.st_mode) and first.st_nlink == 1
                and first.st_size == expected["bytes"], "exact ordinary single-link extent")
        chunks, total = [], 0
        while total <= expected["bytes"]:
            part = os.read(fd, min(65536, expected["bytes"] + 1 - total))
            if not part:
                break
            chunks.append(part)
            total += len(part)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_nlink,
                           s.st_mtime_ns, s.st_ctime_ns)
        require(stamp(first) == stamp(os.fstat(fd)) == stamp(file.lstat()), "unchanged file identity")
        raw = b"".join(chunks)
        require(pin(raw) == expected, "exact complete file bytes")
        return raw
    finally:
        os.close(fd)


def _authenticated_vendor_sources(root):
    """Pure source authentication; tests may supply an explicitly generated copy."""
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "ordinary provider source directory")
    expected_names = {"SOURCE_MANIFEST.json", "__init__.py", *(name + ".py" for name in MODULES)}
    require({p.name for p in root.iterdir()} == expected_names, "complete eight-file provider closure")
    manifest = decode(_read_exact(root / "SOURCE_MANIFEST.json", VENDOR_PIN, 4096))
    require(manifest["schema"] == "osl_transport_source_manifest_v1"
            and set(manifest) == {"schema", "files"}
            and set(manifest["files"]) == expected_names - {"SOURCE_MANIFEST.json"}, "exact provider manifest")
    return {name: _read_exact(root / name, expected, 65536)
            for name, expected in manifest["files"].items()}


def _vendor():
    global _VENDOR
    if _VENDOR is not None:
        return _VENDOR
    root = HERE / "vendor_transport"
    bodies = _authenticated_vendor_sources(root)
    # Compile authenticated bytes directly: no unchecked import or pyc sidecar.
    name = "_meg_owned_provider_" + uuid.uuid4().hex
    package = types.ModuleType(name)
    package.__file__ = str(root / "__init__.py")
    package.__package__, package.__path__ = name, []
    sys.modules[name] = package
    loaded = []
    try:
        for member in MODULES:
            full = name + "." + member
            module = types.ModuleType(full)
            module.__package__, module.__file__ = name, str(root / (member + ".py"))
            sys.modules[full] = module
            loaded.append(full)
            setattr(package, member, module)
            exec(compile(bodies[member + ".py"], module.__file__, "exec"), module.__dict__)
        exec(compile(bodies["__init__.py"], package.__file__, "exec"), package.__dict__)
    except BaseException:
        for full in loaded:
            sys.modules.pop(full, None)
        sys.modules.pop(name, None)
        raise
    _VENDOR = package
    return package


def phase_id(campaign_id, role, fold):
    require(type(campaign_id) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", campaign_id), "bounded campaign identity")
    require(role in ("A", "B") and type(role) is str, "paper assistance condition")
    require(type(fold) is int and 0 <= fold < 10, "original ten-fold index")
    return f"{campaign_id}-{role}-fold-{fold:02d}"


def validate_mounts(role, mounts, program_pin=None):
    require(role in ("A", "B"), "A/B assistance role")
    expected = {"/input/WINDOWS.npy": ("input", "file"),
                "/input/CONTEXT.json": ("input", "file"),
                "/program": ("program", "directory"),
                "/paper": ("paper", "directory"),
                "/contract": ("contract", "directory")}
    if role == "B":
        expected["/author"] = ("historical_author_source", "directory")
    require(type(mounts) is dict and set(mounts) == set(expected), "exact role-specific mount set")
    for target, (purpose, kind) in expected.items():
        desc = mounts[target]
        require(type(desc) is dict and set(desc) == {"path", "kind", "purpose", "files"}
                and desc["kind"] == kind and desc["purpose"] == purpose, "typed mount purpose and geometry")
        require(type(desc["files"]) is dict and desc["files"], "nonempty complete public file inventory")
        require(type(desc["path"]) is str and Path(desc["path"]).is_absolute(), "absolute evaluator-owned mount path")
        for name, expected_pin in desc["files"].items():
            _vendor().bounds.relative(name)
            check_pin(expected_pin, allow_empty=True)
    files = mounts["/program"]["files"]
    require(set(files) == {"submission.py", "candidate_wrapper.py", "PROGRAM.json"},
            "complete three-file frozen programme")
    require(WRAPPER_PIN is not None and files["candidate_wrapper.py"] == WRAPPER_PIN,
            "programme binds exact selected wrapper")
    manifest = {"schema": "meg-frozen-program/v1", "files": {
        name: files[name] for name in ("candidate_wrapper.py", "submission.py")}}
    require(files["PROGRAM.json"] == pin(canonical(manifest)), "programme manifest binds exact source files")
    if program_pin is not None:
        require(check_pin(program_pin) == files["PROGRAM.json"], "selected programme identity matches complete mount")
    return mounts


def make_exposure(role, image, program_pin, mounts, image_inventory_sha256, boundary_audit,
                  *, role_boundary_verified):
    """Serialize an already reviewed operator boundary, never self-qualify it."""
    validate_mounts(role, mounts, program_pin)
    check_pin(program_pin)
    check_pin(boundary_audit)
    require(type(image) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", image), "immutable selected image")
    require(type(image_inventory_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", image_inventory_sha256), "reviewed image inventory")
    require(role_boundary_verified is True, "an external reviewed operator boundary is required")
    return {"schema": "osl_transport_exposure_v1", "role": role, "image": image,
            "source": copy.deepcopy(program_pin), "command": list(COMMAND),
            "mounts": _vendor().bounds.mount_identity(mounts),
            "approved_image_inventory_sha256": image_inventory_sha256,
            "boundary_audit": copy.deepcopy(boundary_audit), "role_boundary_verified": True}


def make_request(campaign_id, role, fold, image, program_pin, exposure_pin, resources,
                 origin, phase_deadline):
    check_pin(program_pin)
    check_pin(exposure_pin)
    require(type(image) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", image), "immutable selected image")
    for value in (origin, phase_deadline):
        require(type(value) in (int, float) and math.isfinite(value), "finite original clock")
    require(0 <= origin < phase_deadline, "ordered original clock")
    require(type(resources) is dict and set(resources) == _vendor().contract.RESOURCE_KEYS,
            "complete fixed resource profile")
    require(all(type(v) is int and v > 0 for v in resources.values()), "positive typed resource limits")
    return {"schema": "osl_owned_phase_request_v1", "phase_id": phase_id(campaign_id, role, fold),
            "action": "held_attempt", "role": role, "image": image, "command": list(COMMAND),
            "workdir": "/work", "source": copy.deepcopy(program_pin), "exposure": copy.deepcopy(exposure_pin),
            "clock": {"origin": origin, "phase_deadline": phase_deadline},
            "resources": copy.deepcopy(resources), "output": {"kind": "generic", "manifest": "OUTPUTS.json"}}


def validate_closed_receipt(receipt, request, mounts, original_deadline):
    """Shared by real execution and generated controls; no receipt creates authority."""
    required = {"schema", "phase_id", "request_sha256", "ownership_pin", "action", "role", "image",
                "source", "exposure", "status", "producer_closed_before_capture", "all_native_resources_closed",
                "cli_reaped", "oom", "deadline_exceeded", "error", "exit_observation_error", "natural_exit",
                "retired_resources", "enforced_resource_limits", "input_before", "input_after", "timing",
                "command_metadata", "output_inventory", "quarantine_root"}
    require(type(receipt) is dict and required <= set(receipt), "complete Provider receipt")
    check_pin(receipt["ownership_pin"])
    expected = {"schema": "osl_owned_phase_receipt_v1", "phase_id": request["phase_id"],
                "request_sha256": pin(_vendor().engine.encoded(request))["sha256"],
                "action": "held_attempt", "role": request["role"], "image": request["image"],
                "source": request["source"], "exposure": request["exposure"], "status": "captured"}
    require(all(receipt.get(k) == v for k, v in expected.items()), "exact request/condition/source receipt join")
    for key in ("producer_closed_before_capture", "all_native_resources_closed", "cli_reaped"):
        require(receipt.get(key) is True, "complete concrete resource custody")
    for key in ("oom", "deadline_exceeded"):
        require(receipt.get(key) is False, "no OOM/deadline violation")
    require(receipt.get("error") is None and receipt.get("exit_observation_error") is None, "no hidden execution failure")
    _vendor().engine.validate_natural_exit(receipt["natural_exit"])
    rows = receipt.get("retired_resources")
    require(type(rows) is list and len(rows) == 3, "three owned resources closed")
    require(sorted(row.get("kind", "") for row in rows) == ["container", "container", "volume"]
            and len({row.get("name") for row in rows}) == 3, "distinct exact resource classes")
    names = {row["name"] for row in rows}
    prefix = next((name[:-9] for name in names if type(name) is str and name.endswith("-producer")), None)
    require(prefix is not None and re.fullmatch(r"osl-[0-9a-f]{24}", prefix)
            and names == {prefix + "-" + suffix for suffix in ("producer", "holder", "volume")},
            "same exact owned resource namespace")
    for row in rows:
        require(row.get("closed") is True and row.get("absence_observed") is True
                and row.get("creation_outcome_unknown") is False, "acknowledged resource absence")
    require(receipt.get("enforced_resource_limits") == request["resources"], "unchanged resource limits")
    identity = _vendor().bounds.mount_identity(mounts)
    require(receipt.get("input_before") == identity == receipt.get("input_after"), "unchanged complete mount identity")
    timing = receipt.get("timing")
    require(type(timing) is dict and set(timing) == {"origin", "original_deadline", "phase_deadline", "started", "finished"}, "complete receipt timing")
    require(all(type(v) in (int, float) and math.isfinite(v) for v in timing.values()), "finite receipt timing")
    require(timing["origin"] == request["clock"]["origin"] and timing["original_deadline"] == original_deadline
            and timing["origin"] <= timing["started"] <= timing["finished"] < timing["phase_deadline"]
            <= request["clock"]["phase_deadline"] <= original_deadline, "unrefreshed original deadline")
    _vendor().engine.validate_cli_records(receipt.get("command_metadata"),
                                         _vendor().provider.caps(request["resources"]["inventory_bytes"]))
    inventory = receipt.get("output_inventory")
    require(type(inventory) is dict and inventory.get("complete") is True, "complete captured output inventory")
    require(type(inventory.get("files")) is dict and set(inventory["files"]) == {"OUTPUTS.json", "RESULT.json"}, "only scientific result and envelope exported")
    for value in inventory["files"].values():
        check_pin(value)
    require(type(inventory.get("total_bytes")) is int
            and inventory["total_bytes"] == sum(p["bytes"] for p in inventory["files"].values())
            <= request["resources"]["max_output_bytes"], "complete bounded output extent")
    require(inventory["files"]["RESULT.json"]["bytes"] <= min(RESULT_LIMIT, request["resources"]["max_file_bytes"]), "bounded result")
    require(inventory["files"]["OUTPUTS.json"]["bytes"] <= request["resources"]["manifest_bytes"], "bounded envelope")
    return copy.deepcopy(inventory["files"]["RESULT.json"])


def _private_path(root, file):
    root, file = Path(root), Path(file)
    require(root.is_absolute() and file.is_absolute() and file.is_relative_to(root), "owned absolute private output path")
    require(".." not in file.parts and root.resolve() == root, "canonical private root")
    current = root
    for part in (None, *file.parent.relative_to(root).parts):
        if part is not None:
            current = current / part
        mode = current.lstat()
        require(stat.S_ISDIR(mode.st_mode) and mode.st_uid == os.geteuid()
                and stat.S_IMODE(mode.st_mode) & 0o077 == 0, "operator-private ordinary directory")
    mode = file.lstat()
    require(stat.S_ISREG(mode.st_mode) and mode.st_uid == os.geteuid()
            and stat.S_IMODE(mode.st_mode) & 0o077 == 0 and mode.st_nlink == 1,
            "private ordinary captured file")
    return file


class OwnedTransport:
    """Production path always constructs the selected concrete Provider class."""
    def __init__(self, *, campaign_id, image, frozen_programs, control_root, quarantine_root,
                 docker_binary, docker_socket, trusted_exposures, source_read_limit,
                 host_write_limit, origin, original_deadline):
        require(type(frozen_programs) is dict and set(frozen_programs) == {"A", "B"}, "both frozen programme identities")
        for value in frozen_programs.values():
            check_pin(value)
        phase_id(campaign_id, "A", 0)
        require(type(origin) in (int, float) and type(original_deadline) in (int, float)
                and math.isfinite(origin) and math.isfinite(original_deadline)
                and 0 <= origin < original_deadline, "one original campaign clock")
        require(type(image) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", image), "immutable image")
        self.campaign_id, self.image = campaign_id, image
        self.frozen_programs = copy.deepcopy(frozen_programs)
        self.origin, self.deadline = origin, original_deadline
        self.control_root, self.quarantine_root = Path(control_root), Path(quarantine_root)
        self._read_ceiling, self._adapter_read_reserved = source_read_limit, 0
        self._attempted, self._accepted = set(), {}
        self._provider = _vendor().Provider(control_root, quarantine_root, docker_binary,
            docker_socket, copy.deepcopy(VENDOR_PIN), trusted_exposures, source_read_limit, host_write_limit)

    def execute_fold(self, role, fold, mounts, exposure_pin, resources, phase_deadline, journal):
        key = (role, fold)
        request = make_request(self.campaign_id, role, fold, self.image, self.frozen_programs[role],
                               exposure_pin, resources, self.origin, phase_deadline)
        require(key not in self._attempted, "no repeated phase or automatic retry")
        validate_mounts(role, mounts, self.frozen_programs[role])
        _vendor().contract.validate_request(request, mounts, self.deadline)
        require(self.origin <= time.monotonic() < self.deadline, "within original campaign deadline")
        self._attempted.add(key)
        # Sole production execution call. No arbitrary executor injection exists.
        result = self._provider.execute_phase(request, mounts, self.deadline, journal)
        require(type(result) is dict and set(result) == {"receipt", "receipt_pin", "receipt_path",
            "final_transport_counters", "finished_after_receipt"}, "exact concrete Provider return")
        check_pin(result["receipt_pin"])
        receipt_path = self.control_root / request["phase_id"] / "RECEIPT.json"
        require(result["receipt_path"] == str(receipt_path), "selected private receipt path")
        _private_path(self.control_root, receipt_path)
        observed = self._provider.observe(request["phase_id"], pin(_vendor().engine.encoded(request))["sha256"],
                                           result["receipt_pin"], self.deadline)
        require(observed["independent_candidate_channel"] is True
                and observed["receipt_pin"] == result["receipt_pin"]
                and canonical(observed["receipt"]) == canonical(result["receipt"]), "retained complete receipt pin and body")
        receipt = observed["receipt"]
        expected = validate_closed_receipt(receipt, request, mounts, self.deadline)
        output = self.quarantine_root / request["phase_id"]
        require(receipt["quarantine_root"] == str(output), "selected private captured output")
        require(type(result["finished_after_receipt"]) in (int, float)
                and receipt["timing"]["finished"] <= result["finished_after_receipt"] < self.deadline,
                "receipt publication within original cutoff")
        # These extra reads reduce the same Provider's remaining campaign ceiling.
        reserve = expected["bytes"] + 1
        require(self._provider.read_used + self._adapter_read_reserved + reserve <= self._read_ceiling,
                "full adapter read reservation inside original campaign ceiling")
        self._adapter_read_reserved += reserve
        self._provider.read_limit = self._read_ceiling - self._adapter_read_reserved
        raw = _read_exact(_private_path(self.quarantine_root, output / "RESULT.json"), expected,
                          min(RESULT_LIMIT, resources["max_file_bytes"]))
        require(time.monotonic() < self.deadline, "result admission within original cutoff")
        accepted = {"phase_id": request["phase_id"], "request_pin": pin(_vendor().engine.encoded(request)),
                    "receipt_pin": copy.deepcopy(result["receipt_pin"]), "result_pin": expected}
        self._accepted[key] = copy.deepcopy(accepted)
        return {"result_bytes": raw, "receipt": receipt, **accepted,
                "final_transport_counters": copy.deepcopy(result["final_transport_counters"]),
                "adapter_read_reserved_bytes": self._adapter_read_reserved,
                "runtime_qualification_inherited": False}

    def complete_for_grading(self):
        require(set(self._accepted) == {(role, fold) for role in ("A", "B") for fold in range(10)},
                "all twenty distinct concrete phases closed before protected grading")
        require(time.monotonic() < self.deadline, "campaign still within original deadline")
        return [copy.deepcopy(self._accepted[key]) for key in sorted(self._accepted)]
