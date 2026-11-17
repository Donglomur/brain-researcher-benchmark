"""Closed whole-study source views, with no scientific computation on this route."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

from find032.access import SourceMember, prepare_view
from find032.admission import parse_input_manifest
from find032.core import Custody, Refusal, encode_json, read_exact, write_exact

ARMS = ("A", "B")
ACCESS = {"A": "paper_and_data", "B": "paper_data_official_code"}
SOURCE_ROLES = frozenset(("paper", "base", "sound", "omission", "postprocessing", "environment", "readme"))


def need(ok, message):
    if not ok:
        raise Refusal(message)


def strict(raw):
    def pairs(values):
        out = {}
        for key, value in values:
            need(key not in out, "duplicate configuration member")
            out[key] = value
        return out
    def nonfinite(value):
        raise Refusal("nonfinite configuration number")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def path(value):
    need(type(value) is str and value.startswith("/") and len(value) <= 4096 and
         "\x00" not in value and os.path.normpath(value) == value,
         "exact absolute selected path")
    result = Path(value)
    need(not any(p.is_symlink() for p in (result, *result.parents)), "unlinked selected path")
    return result


def positive(value, name):
    need(type(value) is int and value > 0, "positive selected " + name)
    return value


def descriptor(value, *, name_key="name", maximum=None):
    need(type(value) is dict and set(value) == {name_key, "bytes", "sha256"}, "closed source descriptor")
    from find032.core import relative_name
    relative_name(value[name_key])
    positive(value["bytes"], "member extent")
    need(maximum is None or value["bytes"] <= maximum, "selected member ceiling")
    need(type(value["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", value["sha256"]), "exact source hash")
    return value


def validate_config(value):
    fields = {"schema", "profile", "endpoint", "fixed_seed", "input_root", "source_root", "program_root",
              "input_manifest", "source_members", "programs", "workspace", "limits", "docker"}
    need(type(value) is dict and set(value) == fields and
         value["schema"] == "FIND032_PAIRED_PARTICIPANT_V1" and
         value["profile"] == "corrected_methods_v1", "fixed complete corrected-profile selection")
    need(value["endpoint"] in ("complete", "empirical_and_most_likely", "theoretical"),
         "prospectively selected original diagnostic endpoint")
    need(type(value["fixed_seed"]) is int and 0 <= value["fixed_seed"] < 2**32,
         "prospectively fixed group seed")
    roots = [path(value[k]) for k in ("input_root", "source_root", "program_root", "workspace")]
    for i, a in enumerate(roots):
        for b in roots[i + 1:]:
            need(not a.is_relative_to(b) and not b.is_relative_to(a), "disjoint selected custody roots")
    need(not os.path.lexists(roots[-1]) and roots[-1].parent.is_dir(), "fresh owned workspace")
    descriptor(value["input_manifest"], maximum=1048576)
    need(type(value["source_members"]) is list and len(value["source_members"]) == 7,
         "paper plus six exact official source roles")
    roles = set()
    names = set()
    for member in value["source_members"]:
        need(type(member) is dict and set(member) == {"role", "path", "bytes", "sha256"}, "closed exposure member")
        descriptor({k: member[k] for k in ("path", "bytes", "sha256")}, name_key="path", maximum=1048576)
        need(member["role"] in SOURCE_ROLES and member["role"] not in roles and
             member["path"] not in names, "exact unique original source roles")
        roles.add(member["role"]); names.add(member["path"])
    need(roles == SOURCE_ROLES, "whole approved source exposure")
    need(type(value["programs"]) is dict and set(value["programs"]) == set(ARMS), "exact paired programmes")
    for program in value["programs"].values():
        descriptor(program, maximum=1048576)
    limits = value["limits"]
    need(type(limits) is dict and set(limits) == {"normal", "cleanup", "evidence", "receipt_bytes", "attach_evidence_bytes", "receipt_seconds"},
         "independent selected work, cleanup and original evidence envelopes")
    for scope in ("normal", "cleanup", "evidence"):
        need(type(limits[scope]) is dict and set(limits[scope]) == {"read_bytes", "write_bytes", "files"}, "complete logical envelope")
        for key, amount in limits[scope].items():
            positive(amount, scope + " " + key)
    need(type(limits["receipt_bytes"]) is int and 0 < limits["receipt_bytes"] <= 1048576,
         "finite precharged terminal receipt")
    need(type(limits["attach_evidence_bytes"]) is int and limits["attach_evidence_bytes"] > 131072 and
         type(limits["receipt_seconds"]) in (int, float) and math.isfinite(limits["receipt_seconds"]) and
         limits["receipt_seconds"] > 0, "explicit original attach evidence space and inner time reserve")
    docker = value["docker"]
    expected = {"binary", "socket", "image", "memory_bytes", "nano_cpus", "pids_limit", "scratch_bytes",
                "volume_bytes", "stdio_bytes", "fd_limit", "member_bytes", "metadata_bytes", "file_count"}
    need(type(docker) is dict and set(docker) == expected, "closed same-arm Docker selection")
    path(docker["binary"]); path(docker["socket"])
    need(type(docker["image"]) is str and re.fullmatch("sha256:[0-9a-f]{64}", docker["image"]), "fixed dependency image")
    for key in expected - {"binary", "socket", "image"}:
        positive(docker[key], key)
    need(docker["metadata_bytes"] <= docker["member_bytes"] <= docker["volume_bytes"] and
         docker["file_count"] >= 33 + 990 + 52 + 3 + 1 + 6 + 2,
         "complete full-study output capacity, never a cheaper subset")
    need(limits["attach_evidence_bytes"] >= docker["stdio_bytes"] + 1 + 131072 and
         limits["evidence"]["write_bytes"] >= 2 * limits["attach_evidence_bytes"] and
         limits["evidence"]["files"] >= 8,
         "both original attach receipts pre-reserved; actual filesystem rounding checked before launch")
    return value


def mkdir(parent_fd, name, custody, budget):
    need(type(name) is str and name and "/" not in name and name not in (".", ".."), "single owned directory component")
    token = budget.reserve("files", 1)
    os.mkdir(name, 0o700, dir_fd=parent_fd)
    budget.observed(token, 1)
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)


def freeze_directory(fd, names):
    """Only exact files created by this invocation become immutable view members."""
    actual = os.listdir(fd)
    need(len(actual) == len(names) and set(actual) == set(names), "closed prepared view inventory")
    for name in names:
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "ordinary owned projection member")
        os.chmod(name, 0o444, dir_fd=fd, follow_symlinks=False)
    os.fsync(fd)
    os.fchmod(fd, 0o555)


class Stage:
    """Own the original input/source/program descriptors until both views close."""
    def __init__(self, cfg, budget, custody, *, holder_source):
        self.cfg, self.budget, self.custody = cfg, budget, custody
        need(type(holder_source) is bytes and 0 < len(holder_source) <= 1048576,
             "exact captured fixed holder source")
        self.holder_source = holder_source
        self.handles, self.closed, self.programs, self.views = [], False, {}, {}
        self.first = None
        self.work = path(cfg["workspace"])
        try:
            self.inputs = self._open(cfg["input_root"])
            self.sources = self._open(cfg["source_root"])
            self.program_root = self._open(cfg["program_root"])
            item = cfg["input_manifest"]
            raw, self.manifest_capture = read_exact(self.inputs, item["name"], item["bytes"], item["sha256"], budget, custody)
            self.plan = parse_input_manifest(raw)
            # Source programmes commit before either arm opens any recording.
            for arm in ARMS:
                row = cfg["programs"][arm]
                raw, captured = read_exact(self.program_root, row["name"], row["bytes"], row["sha256"], budget, custody)
                need(b"\0" not in raw, "ordinary UTF8 participant programme")
                raw.decode("utf8")
                self.programs[arm] = (raw, captured)
            total_input = sum(row.bytes for row in self.plan.members)
            need(budget.limits["read"] >= 2 * total_input and budget.limits["write"] >= 2 * total_input,
                 "both complete input views reserved prospectively")
            self.copy_buffer_lower_bound = 2 * max(row.bytes for row in self.plan.members)
            token = budget.reserve("files", 1)
            os.mkdir(self.work, 0o700)
            budget.observed(token, 1)
            self.root = self._open(str(self.work))
            self.source_members = tuple(SourceMember(**row) for row in cfg["source_members"])
        except BaseException as error:
            self.first = error
            if custody.first is None:
                custody.catch("original stage acquisition", error)
            self.close()
            custody.raise_first()

    def _open(self, value):
        selected = path(value)
        fd = os.open(selected, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.handles.append(fd)
        need(stat.S_ISDIR(os.fstat(fd).st_mode), "ordinary selected directory")
        return fd

    def arm(self, arm, contract):
        need(arm in ARMS and arm not in self.views and not self.closed, "one original arm view")
        local = Custody(self.custody)
        arm_fd = view_fd = output_fd = docker_fd = None
        with local.attempt("whole132 arm projection"):
            try:
                arm_fd = mkdir(self.root, arm, local, self.budget)
                view_fd = mkdir(arm_fd, "view", local, self.budget)
                output_fd = mkdir(arm_fd, "captured", local, self.budget)
                docker_fd = mkdir(arm_fd, "docker-config", local, self.budget)
                exposure = prepare_view(self.plan, ACCESS[arm], self.inputs, self.sources,
                                        view_fd, self.source_members, self.budget, local)
                selected = [r["name"] for r in exposure["members"]] + ["INPUT_MANIFEST.json", "ACCESS_VIEW.json"]
                freeze_directory(view_fd, selected)
                raw, original = self.programs[arm]
                program = write_exact(arm_fd, "program.py", raw, self.budget, local)
                interface = write_exact(arm_fd, "contract.json", contract, self.budget, local)
                holder = write_exact(arm_fd, "holder.py", self.holder_source, self.budget, local)
                for name in ("program.py", "contract.json", "holder.py"):
                    os.chmod(name, 0o444, dir_fd=arm_fd, follow_symlinks=False)
                os.fsync(arm_fd)
                self.views[arm] = {"path": str(self.work / arm), "program": program,
                                   "contract": interface, "holder_source": holder, "exposure": exposure,
                                   "complete_recordings": len(self.plan.members)}
                self.handles.append(output_fd)
                retained = output_fd; output_fd = None
            finally:
                for name, fd in (("untransferred capture root", output_fd), ("empty Docker config root", docker_fd),
                                 ("view root", view_fd), ("arm root", arm_fd)):
                    if fd is not None:
                        local.close(name, lambda fd=fd: os.close(fd))
            local.raise_first()
        return self.work / arm, retained, self.views[arm]

    def close(self):
        if self.closed:
            return
        self.closed = True
        for fd in reversed(self.handles):
            self.custody.close("original stage descriptor", lambda fd=fd: os.close(fd))


def candidate_contract(cfg):
    """Same non-code instruction bytes in both original access arms."""
    from .output_protocol import OUTPUT_PROTOCOL
    return encode_json({"schema": "FIND032_WHOLE_PROGRAMME_CONTRACT_V1",
        "task": "PAPER-FIND-032", "profile": "corrected_methods_v1",
        "fixed_seed": cfg["fixed_seed"],
        "command": ["python", "-I", "-B", "/candidate.py", "--view", "/view",
                    "--contract", "/contract.json", "--output", "/output"],
        "scope": {"participants": 33, "recordings": 132, "planned_products": 990,
                  "comparison_dispositions": 52, "BF10_dispositions": 3, "figures": 6},
        "input_manifest": "/view/INPUT_MANIFEST.json", "access_manifest": "/view/ACCESS_VIEW.json",
        "outputs": "Literal original complete RESULT_MANIFEST.json and GROUP_INDEX.json families; all33 coverage files, available planned products/group arrays, six PDF figures; no extra files.",
        "output_protocol": OUTPUT_PROTOCOL,
        "unavailability": "Only original theoretical support and Fisher-domain dispositions; preserve full identities and reasons, never zero-fill or drop subjects.",
        "historical_reproduction": "unavailable, not substituted by corrected profile",
        "assessment_endpoint_frozen_before_outputs": cfg["endpoint"],
        "output_caps": {k: cfg["docker"][k] for k in ("member_bytes", "metadata_bytes", "volume_bytes", "file_count")},
        "scientific_reward": None, "figure_agreement_metric": "not selected",
        "reference_or_private_answers_in_view": False})
