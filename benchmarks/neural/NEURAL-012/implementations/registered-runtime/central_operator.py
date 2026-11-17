"""N012 source inspection and original-owner host integration.

The inspect CLI reads ordinary source only. Typed HostRuntime operations are
future real preparation/campaign calls, not JSON owner factories or qualification.
Start a fresh trusted host interpreter with -I -B. No candidate code is imported.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from types import ModuleType


TASK = "NEURAL-012"
ANCESTOR_MANIFEST = (10353, "b7c9efb16d422c442c504e7e8107a894671f130462964aef13882a03fe1f5f32")
# Bound after the two new integration source producers have completed review.
INTEGRATION_LOCK = (416, 'a93c00b878633090d7d8b2ca723eb2c23f601dd2266f068807750ee52f6b1c69')
MAX_MEMBER = 1048576
MAX_INSPECTION = 2097152
RAW_SOURCE_ERRORS = []


class OperatorRefusal(RuntimeError):
    pass


def need(value, message):
    if not value:
        raise OperatorRefusal(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def relative(value):
    need(type(value) is str and value and "\\" not in value and not any(c in value for c in "\0\r\n"), "ordinary relative source name")
    path = PurePosixPath(value)
    need(not path.is_absolute() and path.as_posix() == value and all(x not in ("", ".", "..") for x in value.split("/")), "canonical relative source name")
    return path


def identity(st):
    return tuple(getattr(st, name) for name in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"))


def source_read(root, name, pin, budget):
    name = relative(name)
    size, sha = pin
    need(type(size) is int and 0 < size <= MAX_MEMBER and type(sha) is str and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), "bounded exact source pin")
    budget["reserved"] += size + 1
    need(budget["reserved"] <= MAX_INSPECTION, "complete source inspection allowance")
    path = root.joinpath(*name.parts)
    need(not any(p.is_symlink() for p in (path, *path.parents)), "source path has no symlink ancestry")
    fd = None
    primary = None
    body = bytearray()
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == size, "ordinary exact source extent")
        while len(body) < size:
            block = os.read(fd, min(65536, size - len(body)))
            budget["returned"] += len(block)
            need(bool(block), "no short source read")
            body.extend(block)
        extra = os.read(fd, 1)
        budget["returned"] += len(extra)
        need(not extra and identity(before) == identity(os.fstat(fd)), "unchanged complete source")
        need(hashlib.sha256(body).hexdigest() == sha, "exact source digest")
    except BaseException as error:
        RAW_SOURCE_ERRORS.append(error)
        primary = error
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as error:
                RAW_SOURCE_ERRORS.append(error)
                if primary is None:
                    primary = error
    if primary is not None:
        raise primary
    return bytes(body)


def source_inverse(root, prefix, expected):
    base = root / prefix
    need(base.is_dir() and not base.is_symlink(), "ordinary complete source directory")
    stack = [base]
    seen = set()
    nodes = 0
    while stack:
        with os.scandir(stack.pop()) as entries:
            for entry in entries:
                nodes += 1
                need(nodes <= 256 and not entry.is_symlink(), "bounded ordinary source tree")
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                else:
                    need(entry.is_file(follow_symlinks=False), "no special source nodes")
                    seen.add(path.relative_to(root).as_posix())
    need(seen == expected, "full source filename inverse, including no import caches")


def inspect_source():
    """Authenticate all inherited and new operative source without importing it."""
    need(sys.dont_write_bytecode, "start with python3 -B")
    root = Path(__file__).absolute().parent
    need(not any(p.is_symlink() for p in (root, *root.parents)), "ordinary installed package")
    budget = {"reserved": 0, "returned": 0}
    manifest = json.loads(source_read(root, "runtime/ACCEPTED_SOURCE_MANIFEST.json", ANCESTOR_MANIFEST, budget))
    rows = manifest["files"]
    need(manifest["source_roles"] == len(rows) == 57 and manifest["total_bytes"] == sum(r["bytes"] for r in rows) == 371420, "complete accepted57-role source")
    names = set()
    for row in rows:
        name = "runtime/" + row["path"]
        need(name.startswith("runtime/source/") and name not in names, "unique inherited source role")
        source_read(root, name, (row["bytes"], row["sha256"]), budget)
        names.add(name)
    source_inverse(root, "runtime/source", names)
    need(INTEGRATION_LOCK is not None, "integration source lock has not been frozen")
    lock = json.loads(source_read(root, "runtime/INTEGRATION_SOURCE.json", INTEGRATION_LOCK, budget))
    need(set(lock) == {"schema", "files"} and lock["schema"] == "neural012_integration_source_v1", "closed integration source lock")
    expected = {"runtime/integration/selection_bridge.py", "runtime/integration/signal_snapshot.py"}
    need(type(lock["files"]) is list and len(lock["files"]) == 2 and {r["path"] for r in lock["files"]} == expected, "both actual source producers")
    for row in lock["files"]:
        need(set(row) == {"path", "bytes", "sha256"}, "closed integration source row")
        source_read(root, row["path"], (row["bytes"], row["sha256"]), budget)
    source_inverse(root, "runtime/integration", expected)
    return {"schema": "neural012_central_source_inspection_v1", "id": TASK,
            "accepted_source_roles": 57, "integration_source_roles": 2,
            "scope": {"recordings": 727, "people": 37, "arms": 4, "jobs": 96, "phases": 192, "record_arm_outputs": 2908},
            "source_bytes_authenticated": True, "scientific_or_native_execution": False,
            "genuine_inputs_qualified": False, "runnable": False, "research_qualified": False,
            "generic_run": None, "generic_score": None, "authority_issued": False,
            "inspection_bytes": budget}


def loaded_class(module, name, path):
    need(type(module) is ModuleType and Path(vars(module).get("__file__", "")).absolute() == path, "exact installed module origin")
    value = vars(module).get(name)
    need(isinstance(value, type) and value.__module__ == module.__name__, "original concrete installed class")
    return value


class PreparationAttempt:
    """One acquired snapshot/source observation chain, never restored from JSON."""

    def __init__(self, host, selection_raw, prepared_roots, destination, source_roots, snapshot_limits, source_limits):
        self.host = host
        self.selection_raw = selection_raw
        self.prepared_roots = prepared_roots
        self.destination = destination
        self.source_roots = source_roots
        self.snapshot_limits = snapshot_limits
        self.source_limits = source_limits
        self.snapshot = None
        self.source_owner = None
        self.target_publication = None
        self.campaign_attempt = None
        self.complete = False
        self.started = False
        self.first_error = None
        self.secondary_errors = []

    def run(self):
        need(not self.started, "one original preparation attempt")
        self.started = True
        try:
            host = self.host
            host.require_original()
            selection = host.io.strict(self.selection_raw)
            host.evidence.validate_selection(selection)
            assets = {r["asset_id"]: r for r in selection["assets"]}
            prepared_ids = {assets[r["prepared_asset"]]["root"] for r in selection["records"]}
            need(len(prepared_ids) == 1, "one selected unified prepared root")
            prepared_id = next(iter(prepared_ids))
            roots = host.io.strict(host.io.encoded(self.source_roots))
            need(type(roots) is dict and prepared_id not in roots, "supervisor supplies the prepared root from its original snapshot")
            self.snapshot = host.snapshot_type(self.selection_raw, self.prepared_roots, self.destination, self.snapshot_limits)
            need(self.snapshot.run() is self.snapshot, "same original complete snapshot owner")
            signal_root = self.snapshot.require_complete(self.selection_raw)
            roots[prepared_id] = str(signal_root)
            self.source_owner = host.source_type(self.selection_raw, roots, self.source_limits)
            need(self.source_owner.observe() is self.source_owner, "same original complete source-validation owner")
            self.source_owner.require_observed()
            self.complete = True
        except BaseException as error:
            if self.first_error is None:
                self.first_error = error
            else:
                self.secondary_errors.append(error)
            raise self.first_error
        return self

    def require_original(self, host):
        need(type(self) is PreparationAttempt and self.host is host and self in host.preparations, "same acquired original preparation")
        need(self.complete and self.first_error is None and self.started, "successful original source preparation required")
        need(type(self.snapshot) is host.snapshot_type and type(self.source_owner) is host.source_type, "original installed owners required")
        root = self.snapshot.require_complete(self.selection_raw)
        need(self.source_owner.selection_raw == self.selection_raw, "same exact selected source bytes")
        selection = self.source_owner.selection
        self.source_owner.require_original(host.io.encoded(selection["panel"]), host.io.encoded(selection["reference"]), host.io.encoded(selection["source_targets"]), host.scientific.profile_sha256(selection["panel"]["scientific_profile"]))
        assets = {r["asset_id"]: r for r in selection["assets"]}
        need(all(self.source_owner.roots[assets[r["prepared_asset"]]["root"]] == str(root) for r in selection["records"]), "every original observation uses this unified snapshot")
        return root


class TargetPublicationOwner:
    """Private target construction, distinct from postprediction target release."""

    def __init__(self, preparation, write_bytes):
        self.preparation = preparation
        self.write_limit = write_bytes
        self.descriptors = []
        self.directory_bindings = []
        self.close_outcomes = []
        self.output_fd = None
        self.bytes_written = 0
        self.started = False
        self.complete = False
        self.first_error = None
        self.secondary_errors = []

    def retain(self, error):
        if self.first_error is None:
            self.first_error = error
        else:
            self.secondary_errors.append(error)

    def connected_directories(self):
        self.preparation.source_owner.budget.check()
        for parent, name, fd, expected in self.directory_bindings:
            opened = os.fstat(fd)
            linked = os.stat(name, dir_fd=parent, follow_symlinks=False)
            need(stat.S_ISDIR(opened.st_mode) and stat.S_ISDIR(linked.st_mode) and
                 (opened.st_dev, opened.st_ino) == (linked.st_dev, linked.st_ino) == expected,
                 "same connected original private target directory")

    def run(self):
        need(not self.started, "one original private target publication")
        self.started = True
        try:
            p = self.preparation
            host = p.host
            p.require_original(host)
            owner = p.source_owner
            selection = owner.selection
            target = owner.require_target_selection(owner.target_selection)
            # Full original labels are private live-owner derivations, not the
            # unqualified planning result or a caller-provided target object.
            labels = owner.validation["labels"]
            gold = {"panel_sha256": target["panel_sha256"], "scientific_profile_sha256": target["scientific_profile_sha256"],
                    "records": [{"recording_id": row["recording_id"], "events": labels[row["recording_id"]]} for row in selection["panel"]["records"]]}
            raw = host.io.encoded(gold)
            owner.require_target_content(raw)
            need(type(self.write_limit) is int and len(raw) <= self.write_limit, "explicit complete private target write allowance")
            owner.require_qualified("full_panel_source_join", selection["panel"]["source_qualification_sha256"])
            owner.budget.check()
            path = Path(target["path"])
            need(path.is_absolute() and path.name not in ("", ".", ".."), "exact private target destination")
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
            fd = os.open(path.anchor, flags)
            self.descriptors.append(fd)
            st = os.fstat(fd)
            self.directory_bindings.append((None, path.anchor, fd, (st.st_dev, st.st_ino)))
            for part in path.parts[1:-1]:
                owner.budget.check()
                parent = fd
                fd = os.open(part, flags, dir_fd=parent)
                self.descriptors.append(fd)
                st = os.fstat(fd)
                self.directory_bindings.append((parent, part, fd, (st.st_dev, st.st_ino)))
            self.connected_directories()
            self.output_fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=fd)
            self.descriptors.append(self.output_fd)
            st = os.fstat(self.output_fd)
            need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == 0, "fresh private ordinary target")
            while self.bytes_written < len(raw):
                owner.budget.check()
                block = raw[self.bytes_written:self.bytes_written + 65536]
                need(self.bytes_written + len(block) <= self.write_limit, "private target write cap before effect")
                count = os.write(self.output_fd, block)
                need(type(count) is int and 0 < count <= len(block), "complete advancing private target write")
                self.bytes_written += count
            os.fchmod(self.output_fd, 0o400)
            end = os.fstat(self.output_fd)
            need(end.st_size == len(raw) and end.st_nlink == 1 and stat.S_IMODE(end.st_mode) == 0o400, "complete readonly private target extent")
            linked = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
            need(identity(linked) == identity(end) and stat.S_ISREG(linked.st_mode), "same exact private target at the selected path")
            self.connected_directories()
            owner.budget.check()
        except BaseException as error:
            self.retain(error)
        finally:
            for fd in reversed(self.descriptors):
                outcome = {"descriptor":fd, "attempted":True, "completed":False, "error":None}
                self.close_outcomes.append(outcome)
                try:
                    os.close(fd)
                    outcome["completed"] = True
                except BaseException as error:
                    outcome["error"] = error
                    self.retain(error)
            # Keep acquired descriptor numbers and all errors as occurrence
            # evidence. A close failure is unresolved, never successful cleanup.
        if self.first_error is not None:
            raise self.first_error
        try:
            self.preparation.source_owner.budget.check()
        except BaseException as error:
            self.retain(error)
            raise
        self.complete = True
        return self


class HostRuntime:
    """Fresh trusted-host imports and real producer/campaign API.

    These object/module checks establish local consistency only. They do not
    authenticate Python, the publisher, clocks, targets, Docker or the kernel.
    """

    def __init__(self):
        need(sys.flags.isolated and sys.dont_write_bytecode, "fresh trusted host with python3 -I -B")
        inspect_source()
        self.root = Path(__file__).absolute().parent
        self.private = self.root / "runtime/source/neural012/private"
        self.integration = self.root / "runtime/integration"
        self.expected = {p.stem: p for p in self.private.glob("*.py")}
        self.expected.update({p.stem: p for p in self.integration.glob("*.py")})
        self.expected["vendor.analysis_core"] = self.private / "vendor/analysis_core.py"
        self.expected["vendor.event_protocol"] = self.private / "vendor/event_protocol.py"
        need(not any(name in sys.modules for name in (*self.expected, "vendor")), "fresh host, no previously loaded scientific aliases")
        self.old_path = tuple(sys.path)
        sys.path[:0] = [str(self.integration), str(self.private)]
        self.modules = {}
        self.preparations = []
        self.campaigns = []
        self.campaign_attempts = []
        self.first_error = None
        self.secondary_errors = []
        try:
            for name in ("selection_bridge", "signal_snapshot", "source_validation", "source_evidence", "campaign_owner", "prepare_analysis", "scientific_contract", "io_contract"):
                self.modules[name] = importlib.import_module(name)
            self.io = self.modules["io_contract"]
            self.evidence = self.modules["source_evidence"]
            self.scientific = self.modules["scientific_contract"]
            self.snapshot_type = loaded_class(self.modules["signal_snapshot"], "SignalSnapshotOwner", self.integration / "signal_snapshot.py")
            self.source_type = loaded_class(self.modules["source_validation"], "SourceValidationOwner", self.private / "source_validation.py")
            self.campaign_type = loaded_class(self.modules["campaign_owner"], "CampaignOwner", self.private / "campaign_owner.py")
            self.require_original()
        except BaseException as error:
            self.first_error = error
            raise

    def require_original(self):
        need(type(self) is HostRuntime and self.first_error is None, "same live host runtime")
        need(tuple(sys.path[:2]) == (str(self.integration), str(self.private)) and tuple(sys.path[2:]) == self.old_path, "same trusted import path")
        for name, expected in self.expected.items():
            module = sys.modules.get(name)
            if module is not None:
                need(type(module) is ModuleType and Path(vars(module).get("__file__", "")).absolute() == expected, "foreign scientific module alias: " + name)
        for name, original in self.modules.items():
            need(sys.modules.get(name) is original, "same original imported module")
        return self

    def plan_selection(self, *args, **kwargs):
        """Construct complete unqualified inputs; keys remain host-only operands."""
        self.require_original()
        return self.modules["selection_bridge"].build_selection(*args, **kwargs)

    def prepare(self, selection_raw, prepared_roots, destination, source_roots, snapshot_limits, source_limits):
        self.require_original()
        attempt = PreparationAttempt(self, selection_raw, prepared_roots, destination, source_roots, snapshot_limits, source_limits)
        self.preparations.append(attempt)
        return attempt.run()

    def publish_target(self, preparation, write_bytes):
        self.require_original()
        preparation.require_original(self)
        need(preparation.target_publication is None, "one private target publication occurrence")
        owner = TargetPublicationOwner(preparation, write_bytes)
        preparation.target_publication = owner
        return owner.run()

    def invoke(self, preparation, programmes, runtime_selection, workspace):
        """Run the complete original campaign then its original target release.

        The accepted CampaignOwner performs genuine admission before candidate
        effects. No supplied report or this host API can satisfy that gate.
        """
        self.require_original()
        signal_root = preparation.require_original(self)
        publication = preparation.target_publication
        need(type(publication) is TargetPublicationOwner and publication.preparation is preparation and publication.complete and publication.first_error is None, "same successful original private target publication before campaign")
        source_owner = preparation.source_owner
        selection = source_owner.selection
        need(preparation.campaign_attempt is None, "one campaign attempt for this source/target preparation")
        attempt = {"preparation": preparation, "owner": None, "first_error": None, "complete": False}
        preparation.campaign_attempt = attempt
        self.campaign_attempts.append(attempt)
        try:
            execution = self.campaign_type(self.io.encoded(selection["panel"]), self.io.encoded(selection["source_targets"]), programmes, runtime_selection, workspace, signal_root, self.io.encoded(selection["reference"]), source_owner)
            attempt["owner"] = execution
            self.campaigns.append(execution)
            result = execution.run()
            need(result is execution and execution.source_owner is source_owner, "same original completed campaign and source owner")
            self.modules["prepare_analysis"].prepare_completed_campaign(execution)
            need(execution.target_owner is not None and execution.target_owner.execution is execution and execution.analysis_complete, "same original protected target and completed analysis")
            attempt["complete"] = True
        except BaseException as error:
            attempt["first_error"] = error
            raise
        return execution


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    need(argv == ["inspect"], "CLI supports source inspection; real preparation/campaign uses the typed HostRuntime API, never a receipt loader")
    print(json.dumps(inspect_source(), indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
