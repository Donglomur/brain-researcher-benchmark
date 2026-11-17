"""PROPOSED, UNEXECUTED storage controls with explicitly invented kernel leaves.

No filesystem, mount, process or native evidence is produced by this suite.
The owning selected harness supplies the authenticated source loader and Meter.
"""
import hashlib
import json
import posixpath
import stat
from contextlib import contextmanager
from types import SimpleNamespace

SOURCE_PIN = {
    "bytes": 26572,
    "sha256": "42168a46237686bc54099ef6da35fcfb548804e0c0ddac18c24870d5e9c97360",
}
PEOPLE = tuple("sub-%02d" % n for n in range(1, 33))
MODES = ("frozen_program", "case_adaptive")
PHASES = ("train", "query")
FULL_MOUNT_CAP = 16384
SMALL_MOUNT_CAP = 4096
FULL_RECEIPT_CAP = 524288
EARLY_RECEIPT_CAP = 131072
SMALL_RECEIPT_CAP = 8192
RESULT_BOUND = 131072
RETURN_JSON_CAP = 32768
CASE_RESULT_BOUND = 4096
FULL_FIXTURE_BOUND = 655360
EARLY_FIXTURE_BOUND = 655360
SMALL_FIXTURE_BOUND = 65536
# Structural object/byte-buffer bound for this fixed recipe, not measured RSS.
PROPOSED_LIVE_ENVELOPE = 8 * 1024 * 1024

EARLY_NAMES = (
    "constructor_duplicate_root", "constructor_nested_roots",
    "constructor_initial_nonempty", "constructor_first_body_and_close",
)
SMALL_NAMES = (
    "held_wrong_owner", "held_wrong_byte_ceiling", "held_wrong_inode_ceiling",
    "mount_device_alias", "nested_mount_bypass", "root_path_replacement",
    "duplicate_stage_selection", "unselected_storage_profile",
    "duplicate_storage_profile", "wrong_profile_capacity",
    "partial_finalize_refuses", "unknown_descriptor_close",
    "mountinfo_over_cap", "iterator_close_preserves_first",
    "failed_cleanup_stays_incomplete",
)


def reservation():
    """Pure fixed integer proposal; does not construct any filesystem fixture."""
    cases = [{
        "name": "complete_128_stage_lifecycle",
        "fixture_write": FULL_FIXTURE_BOUND + CASE_RESULT_BOUND,
        "policy_read": 130 * (FULL_MOUNT_CAP + 1),
        "policy_write": 4 * FULL_RECEIPT_CAP + 3 * 130 * (FULL_MOUNT_CAP + 1),
    }]
    for name in EARLY_NAMES:
        mounts = 0 if name in EARLY_NAMES[:2] else 1
        cases.append({
            "name": name, "fixture_write": EARLY_FIXTURE_BOUND + CASE_RESULT_BOUND,
            "policy_read": mounts * (FULL_MOUNT_CAP + 1),
            "policy_write": 4 * EARLY_RECEIPT_CAP + 3 * mounts * (FULL_MOUNT_CAP + 1),
        })
    for name in SMALL_NAMES:
        # Every small case may acquire at most one bounded mount table.
        cases.append({
            "name": name, "fixture_write": SMALL_FIXTURE_BOUND + CASE_RESULT_BOUND,
            "policy_read": SMALL_MOUNT_CAP + 1,
            "policy_write": 3 * (SMALL_MOUNT_CAP + 1),
        })
    return {
        "schema": "morse-storage-controls-reservation-v1",
        "cases": cases,
        "read_bytes": sum(c["policy_read"] for c in cases),
        "write_bytes": RESULT_BOUND + sum(c["fixture_write"] + c["policy_write"]
                                        for c in cases),
        "result_buffer_bytes": RESULT_BOUND,
        "max_return_json_bytes": RETURN_JSON_CAP,
        "known_live_envelope_bytes": PROPOSED_LIVE_ENVELOPE,
        "hard_rss_enforcement": False,
        "source_capture_and_loader_budget": "charged separately by parent loader",
    }


class ControlFailure(RuntimeError):
    def __init__(self, name, original, checks, charges):
        super().__init__("storage control failed: " + name)
        self.original = original
        self.partial = {"checks": list(checks), "charges": dict(charges),
                        "failed_case": name, "native_evidence": False}


class _CleanupFailure(RuntimeError):
    def __init__(self, first, cleanup):
        super().__init__("control cleanup also failed after: " + str(first))
        self.first, self.cleanup = first, cleanup


def _need(value, message):
    if not value:
        raise AssertionError(message)


def _json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False, ensure_ascii=True) + "\n").encode("ascii")


class _CaseMeter:
    """All synthetic policy Budget calls still debit the caller's real Meter."""
    def __init__(self, parent, row):
        self.parent = parent
        self.row = row
        self.read_bytes = self.write_bytes = 0

    def charge(self, *, read=0, write=0, label):
        _need(type(read) is int and read >= 0 and type(write) is int and write >= 0,
              "nonnegative exact control charge")
        _need(self.read_bytes + read <= self.row["policy_read"],
              "case read reservation exceeded")
        _need(self.write_bytes + write <=
              self.row["fixture_write"] + self.row["policy_write"],
              "case write reservation exceeded")
        self.parent.charge(read=read, write=write,
                           label="storage/" + self.row["name"] + "/" + label)
        self.read_bytes += read
        self.write_bytes += write

    def read(self, n):
        self.charge(read=n, label="actual-policy-read-reservation")

    def write(self, n):
        self.charge(write=n, label="actual-policy-write-reservation")

    def check(self):
        self.parent.check()


class _BodyError(OSError):
    pass


class _CloseError(OSError):
    pass


class _Scan:
    def __init__(self, kernel, path):
        self.kernel, self.path, self.done = kernel, path, False
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.done:
            raise StopIteration
        self.done = True
        if self.path in self.kernel.nonempty:
            return "invented-unexpected-member"
        raise StopIteration

    def close(self):
        _need(not self.closed, "scan closed twice")
        self.closed = True
        self.kernel.scan_closes += 1
        if self.path == self.kernel.scan_close_failure:
            raise self.kernel.close_error


class _Kernel:
    """Inert os facade: integer handles and metadata only, no actual syscalls."""
    O_RDONLY, O_DIRECTORY, O_NOFOLLOW, O_CLOEXEC, O_NONBLOCK = 0, 2, 4, 8, 16
    ST_RDONLY = 1
    path = posixpath

    @staticmethod
    def makedev(major, minor):
        # A declared synthetic device encoding, not the Linux device ABI.
        return (major << 32) | minor

    def __init__(self, roots, mount_cap):
        self.facts = {r["path"]: dict(r) for r in roots}
        self.nonempty = set()
        self.body_failure = None
        self.close_failure = None
        self.scan_close_failure = None
        self.body_error = _BodyError("invented original fstat failure")
        self.close_error = _CloseError("invented unknown descriptor close")
        self.live = {}
        self.next_fd = 100
        self.opens = self.closes = self.peak = 0
        self.mount_opens = self.scans = self.scan_closes = 0
        self.close_failure_attempts = 0
        self.extra_mount = None
        self.mount_cap = mount_cap
        self.overcap = False

    def getuid(self):
        return 1000

    def geteuid(self):
        return 1000

    def mount_body(self):
        lines = []
        for r in self.facts.values():
            lines.append("%d 1 %d:%d / %s rw - tmpfs tmpfs rw\n" %
                         (r["mount_id"], r["device_major"], r["device_minor"], r["path"]))
        if self.extra_mount:
            lines.append(self.extra_mount)
        raw = "".join(lines).encode("ascii")
        _need(len(raw) <= self.mount_cap, "invented normal table exceeded its declared cap")
        return raw if not self.overcap else b"x" * (self.mount_cap + 1)

    def open(self, path, flags, *, dir_fd=None):
        if dir_fd is not None:
            _need(dir_fd in self.live and self.live[dir_fd]["kind"] == "directory",
                  "relative open without held directory")
            path = posixpath.join(self.live[dir_fd]["path"], path)
        if path == "/proc/self/mountinfo":
            _need(flags == (self.O_NOFOLLOW | self.O_NONBLOCK | self.O_CLOEXEC),
                  "mountinfo flag mismatch")
            item = {"kind": "mountinfo", "path": path, "body": self.mount_body(), "offset": 0}
            self.mount_opens += 1
        else:
            _need(flags == (self.O_DIRECTORY | self.O_NOFOLLOW | self.O_CLOEXEC),
                  "directory open must retain nofollow/cloexec")
            _need(path == "/" or path in self.facts, "unexpected inert path")
            facts = self.facts.get(path, {"device": 99999, "inode": 1})
            item = {"kind": "directory", "path": path,
                    "device": facts["device"], "inode": facts["inode"]}
        fd = self.next_fd
        self.next_fd += 1
        self.live[fd] = item
        self.opens += 1
        self.peak = max(self.peak, len(self.live))
        return fd

    def close(self, fd):
        _need(fd in self.live, "unknown/repeated numeric FD close")
        item = self.live.pop(fd)
        self.closes += 1
        if item["kind"] == "directory" and item["path"] == self.close_failure:
            self.close_failure_attempts += 1
            # Retire the synthetic numeric handle, but make its outcome unknown
            # to the real policy exactly as a failing kernel close would be.
            raise self.close_error

    def read(self, fd, n):
        _need(fd in self.live and self.live[fd]["kind"] == "mountinfo",
              "only the invented mountinfo stream can be read")
        _need(type(n) is int and 0 < n <= self.mount_cap + 1, "bounded inert read")
        item = self.live[fd]
        out = item["body"][item["offset"]:item["offset"]+n]
        item["offset"] += len(out)
        return out

    def fstat(self, fd):
        _need(fd in self.live, "fstat requires held descriptor")
        item = self.live[fd]
        if item["kind"] == "mountinfo":
            return SimpleNamespace(st_mode=stat.S_IFREG | 0o400)
        if item["path"] == self.body_failure:
            raise self.body_error
        facts = self.facts.get(item["path"], {"uid": 1000, "gid": 1000, "mode": 0o700})
        return SimpleNamespace(st_mode=stat.S_IFDIR | facts["mode"],
                               st_dev=item["device"], st_ino=item["inode"],
                               st_uid=facts["uid"], st_gid=facts["gid"])

    def fstatvfs(self, fd):
        _need(fd in self.live and self.live[fd]["kind"] == "directory",
              "fstatvfs requires held directory")
        facts = self.facts[self.live[fd]["path"]]
        return SimpleNamespace(f_frsize=4096, f_blocks=facts["bytes"] // 4096,
                               f_files=facts["inodes"], f_flag=0)

    def scandir(self, fd):
        _need(fd in self.live and self.live[fd]["kind"] == "directory",
              "scandir requires held directory")
        self.scans += 1
        return _Scan(self, self.live[fd]["path"])


@contextmanager
def _bound(module, kernel):
    previous_os, previous_sys = module.os, module.sys
    module.os, module.sys = kernel, SimpleNamespace(platform="linux")
    try:
        yield
    finally:
        # Do not modify global sys.modules or shared stdlib module objects.
        module.os, module.sys = previous_os, previous_sys


def _root(index):
    return {
        "path": "/m%03d" % index, "mount_id": 100 + index,
        "device_major": 0, "device_minor": index + 1, "device": index + 1,
        "inode": 1, "uid": 1000, "gid": 1000, "mode": 0o700,
        "bytes": 262144 if index == 0 else (4096 if index % 2 else 8192),
        "inodes": 1024,
    }


def _fixture(receipt_cap):
    # This is explicitly a storage-only plan projection. It is not a fabricated
    # result from the complete paired-plan compiler or any native qualification.
    spec = {
        "schema": "invented-storage-plan-projection-v1",
        "people": list(PEOPLE), "modes": list(MODES),
        "environment": {"container_uid": 1000},
        "stage_limits": {"output_bytes": 4096, "workspace_bytes": 8192},
        "total_reserved_bytes": 262144,
        "storage_admission_id": "invented-storage",
    }
    plan = {"spec": spec, "sha256": hashlib.sha256(_json(spec)).hexdigest(),
            "logical_contexts": 64, "stage_launches": 128}
    config = {
        "schema": "morse-preprovisioned-tmpfs-v1", "admission_id": "invented-storage",
        "host_uid": 1000, "max_mountinfo_bytes": FULL_MOUNT_CAP,
        "max_mountinfo_entries": 257, "max_directory_entries": 1,
        "max_receipt_bytes": receipt_cap, "campaign": _root(0), "stages": [],
    }
    roots = [config["campaign"]]
    index = 1
    for person in PEOPLE:
        for mode in MODES:
            for phase in PHASES:
                output, workspace = _root(index), _root(index+1)
                index += 2
                config["stages"].append({"participant": person, "mode": mode,
                                         "phase": phase, "output": output,
                                         "workspace": workspace})
                roots.extend((output, workspace))
    _need(len(_json(config)) <= 65536 and len(_json(plan)) <= 4096,
          "fixed fixture serialization exceeded its prospectively charged buffers")
    return plan, config, _Kernel(roots, FULL_MOUNT_CAP)


def _profile(paths, *, admission="invented-storage"):
    return {
        "mechanism": "independently_admitted_bounded_host_volumes_v1",
        "admission_id": admission, "output_root": paths["output_root"],
        "workspace_root": paths["workspace_root"],
        "output_bytes": 4096, "workspace_bytes": 8192,
    }


def _context(plan, row):
    return hashlib.sha256((plan["sha256"] + row["participant"] + row["mode"]).encode()).hexdigest()[:32]


def _error_summary(exc):
    return {
        "first_type": type(exc.first["error"]).__name__,
        "first_message": str(exc.first["error"]),
        "first_where": exc.first["where"],
        "secondary": [{"where": x["where"], "type": type(x["error"]).__name__,
                       "message": str(x["error"])} for x in exc.secondary],
        "state": exc.receipt["state"], "complete": exc.receipt["complete"],
        "descriptor_closure": exc.receipt["descriptor_closure"],
    }


def _expect(module, call, fragment):
    try:
        call()
    except module.StorageFailure as exc:
        _need(exc.first is not None and fragment in str(exc.first["error"]),
              "wrong original storage refusal: " + str(exc.first))
        _need(exc.receipt["complete"] is False, "refusal falsely reports complete")
        return exc
    raise AssertionError("expected real policy refusal: " + fragment)


def _cleanup(module, policy, kernel):
    if policy is None or not kernel.live:
        return
    before = policy._first
    try:
        receipt = policy.close_failed()
        _need(before is None and receipt["complete"] is False,
              "failure cleanup lost original error or claimed complete")
    except module.StorageFailure as exc:
        _need(before is not None and exc.first is before,
              "cleanup did not preserve its first exception record")
    _need(not kernel.live, "inert descriptors remain after cleanup")


def _full(module, case):
    plan, config, kernel = _fixture(FULL_RECEIPT_CAP)
    policy = None
    primary = None
    with _bound(module, kernel):
        try:
            policy = module.PreprovisionedStorage(plan, config, case)
            _need(len(kernel.live) == 257 and kernel.scans == kernel.scan_closes == 257,
                  "constructor did not admit all257 roots")
            kernel.nonempty.add("/m000")
            for row in config["stages"]:
                ident = _context(plan, row)
                paths = policy.stage_roots(ident, row["mode"], row["phase"])
                _need(paths == {"output_root": row["output"]["path"],
                                "workspace_root": row["workspace"]["path"]},
                      "stage path mapping differs from frozen full roster")
                kernel.nonempty.update(paths.values())
                policy.require_storage(_profile(paths))
            receipt = policy.finalize()
            _need(receipt["complete"] is True and receipt["state"] == "finalized"
                  and receipt["selected_stages"] == receipt["consumed_stages"] == 128,
                  "full storage lifecycle incomplete")
            _need(not kernel.live and kernel.opens == kernel.closes
                  and kernel.scans == kernel.scan_closes == 257
                  and kernel.mount_opens == 130, "lifecycle/empty-check/descriptor count mismatch")
            events = receipt["observations"]
            _need(len(events) == 1155, "full observation coverage mismatch")
            initial = {e["root"] for e in events if e["event"] == "initial"}
            final = {e["root"] for e in events if e["event"] == "final"}
            _need(len(initial) == 257 and initial == final,
                  "full initial/final root coverage differs")
            stages = {(e["context_id"], e["mode"], e["phase"])
                      for e in events if e["event"] == "stage_admitted"}
            _need(len(stages) == 128, "stage admissions were duplicated or reduced")
            _need(receipt["stage_execution_or_process_closure"] ==
                  "not_observed_by_storage_policy", "storage promoted to execution evidence")
            return {"roots": 257, "logical_contexts": 64, "stages": 128,
                    "mountinfo_acquisitions": kernel.mount_opens,
                    "root_observations": 898, "events": len(events),
                    "peak_inert_descriptors": kernel.peak,
                    "nonempty_after_initial_admission": True,
                    "native_execution_evidence": False}
        except BaseException as exc:
            primary = exc
            raise
        finally:
            try:
                _cleanup(module, policy, kernel)
            except BaseException as cleanup:
                if primary is not None:
                    raise _CleanupFailure(primary, cleanup) from primary
                raise


def _early(module, case, name):
    plan, config, kernel = _fixture(EARLY_RECEIPT_CAP)
    if name == "constructor_duplicate_root":
        config["stages"][0]["output"]["path"] = config["campaign"]["path"]
        fragment = "shared root/mount/device alias"
    elif name == "constructor_nested_roots":
        config["stages"][0]["output"]["path"] = config["campaign"]["path"] + "/nested"
        fragment = "nested campaign/stage roots"
    elif name == "constructor_initial_nonempty":
        kernel.nonempty.add("/m000")
        fragment = "not initially empty"
    else:
        kernel.body_failure = kernel.close_failure = "/m000"
        fragment = "invented original fstat failure"
    with _bound(module, kernel):
        exc = _expect(module, lambda: module.PreprovisionedStorage(plan, config, case), fragment)
        _need(not kernel.live and kernel.opens == kernel.closes,
              "constructor did not attempt all acquired closes")
        if name in EARLY_NAMES[:2]:
            _need(kernel.opens == 0, "structural refusal reached inert kernel")
        if name == "constructor_first_body_and_close":
            _need(exc.first["error"] is kernel.body_error
                  and any(x["error"] is kernel.close_error for x in exc.secondary)
                  and exc.receipt["descriptor_closure"] == "unknown"
                  and kernel.close_failure_attempts == 1,
                  "raw first/secondary error or no-retry close policy lost")
        return _error_summary(exc)


def _small_state(module, case):
    """Explicit small held-state seam; never substitutes for the full constructor."""
    roots = [_root(i) for i in range(3)]
    kernel = _Kernel(roots, SMALL_MOUNT_CAP)
    policy = object.__new__(module.PreprovisionedStorage)
    key = ("c" * 32, "frozen_program", "train")
    policy._budget = case
    policy._fds = {}
    policy._expected = dict(zip(("campaign", "output", "workspace"), roots))
    policy._rows = {key: ("output", "workspace")}
    policy._pairs = {(roots[1]["path"], roots[2]["path"]): key}
    policy._selected, policy._consumed = set(), set()
    policy._events, policy._secondary, policy._unknown_closes = [], [], []
    policy._event_bytes = 0
    policy._first = None
    policy._state = "ready"
    policy.plan_sha256, policy.config_sha256 = "a" * 64, "b" * 64
    policy.admission_id = "invented-storage"
    policy._metadata_cap = SMALL_RECEIPT_CAP
    policy._mount_cap, policy._mount_entries = SMALL_MOUNT_CAP, 4
    policy._directory_entries, policy._directory_seen, policy._uid = 1, 0, 1000
    for name, root in policy._expected.items():
        policy._fds[name] = kernel.open(root["path"],
            kernel.O_DIRECTORY | kernel.O_NOFOLLOW | kernel.O_CLOEXEC)
    return policy, kernel, key


def _small(module, case, name):
    policy, kernel, key = _small_state(module, case)
    paths = {"output_root": "/m001", "workspace_root": "/m002"}
    primary = None
    with _bound(module, kernel):
        try:
            if name in ("held_wrong_owner", "held_wrong_byte_ceiling",
                        "held_wrong_inode_ceiling", "mount_device_alias",
                        "nested_mount_bypass", "root_path_replacement"):
                facts = kernel.facts["/m000"]
                if name == "held_wrong_owner":
                    facts["uid"] += 1
                    fragment = "physical identity/ownership changed"
                elif name == "held_wrong_byte_ceiling":
                    facts["bytes"] += 4096
                    fragment = "kernel byte/inode capacity"
                elif name == "held_wrong_inode_ceiling":
                    facts["inodes"] += 1
                    fragment = "kernel byte/inode capacity"
                elif name == "mount_device_alias":
                    kernel.extra_mount = "999 1 0:1 / /alias rw - tmpfs tmpfs rw\n"
                    fragment = "another alias"
                elif name == "nested_mount_bypass":
                    kernel.extra_mount = "999 1 0:999 / /m000/nested rw - tmpfs tmpfs rw\n"
                    fragment = "nested mount could bypass"
                else:
                    facts["inode"] += 1
                    fragment = "no longer names held directory"
                policy.stage_roots(*key)
                exc = _expect(module, lambda: policy.require_storage(_profile(paths)), fragment)
            elif name == "duplicate_stage_selection":
                policy.stage_roots(*key)
                exc = _expect(module, lambda: policy.stage_roots(*key), "unknown/reused stage")
            elif name == "unselected_storage_profile":
                exc = _expect(module, lambda: policy.require_storage(_profile(paths)),
                              "stage must be selected once")
            elif name == "duplicate_storage_profile":
                policy.stage_roots(*key)
                policy.require_storage(_profile(paths))
                exc = _expect(module, lambda: policy.require_storage(_profile(paths)),
                              "stage must be selected once")
                _need(kernel.mount_opens == 1, "duplicate admission reread kernel")
            elif name == "wrong_profile_capacity":
                policy.stage_roots(*key)
                profile = _profile(paths)
                profile["output_bytes"] += 1
                exc = _expect(module, lambda: policy.require_storage(profile),
                              "storage profile capacity mismatch")
            elif name == "partial_finalize_refuses":
                exc = _expect(module, policy.finalize, "every selected stage admitted")
                _need(not kernel.live, "partial finalize did not close held roots")
            elif name == "unknown_descriptor_close":
                kernel.close_failure = "/m002"
                exc = _expect(module, policy.close_failed, "invented unknown descriptor close")
                _need(exc.first["error"] is kernel.close_error
                      and exc.receipt["descriptor_closure"] == "unknown"
                      and kernel.close_failure_attempts == 1 and not kernel.live,
                      "unknown descriptor close was retried or promoted")
            elif name == "mountinfo_over_cap":
                kernel.overcap = True
                policy.stage_roots(*key)
                exc = _expect(module, lambda: policy.require_storage(_profile(paths)),
                              "mountinfo byte cap exceeded")
            elif name == "iterator_close_preserves_first":
                kernel.nonempty.add("/m000")
                kernel.scan_close_failure = "/m000"
                exc = _expect(module, lambda: policy._check_empty("campaign"),
                              "not initially empty")
                _need(any(x["error"] is kernel.close_error for x in exc.secondary)
                      and exc.receipt["descriptor_closure"] == "unknown",
                      "iterator close replaced/lost initial nonempty error")
            elif name == "failed_cleanup_stays_incomplete":
                receipt = policy.close_failed()
                _need(receipt["complete"] is False and receipt["state"] == "failed_closed"
                      and receipt["descriptor_closure"] == "closed" and not kernel.live,
                      "partial cleanup claimed finalization")
                return {"complete": False, "descriptor_closure": "closed"}
            else:
                raise AssertionError("unselected case")
            return _error_summary(exc)
        except BaseException as exc:
            primary = exc
            raise
        finally:
            try:
                _cleanup(module, policy, kernel)
            except BaseException as cleanup:
                if primary is not None:
                    raise _CleanupFailure(primary, cleanup) from primary
                raise


def run(load_captured, meter):
    """Run only after the owning harness receives an explicit execution selection."""
    meter.check()
    meter.charge(write=RESULT_BOUND, label="storage/final-summary-envelope")
    spec = reservation()
    module = load_captured("storage_policy")
    checks, totals = [], {"read": 0, "write": RESULT_BOUND}
    for row in spec["cases"]:
        case = _CaseMeter(meter, row)
        try:
            case.check()
            case.charge(write=row["fixture_write"], label="fixture-and-result-before-construction")
            if row["name"] == "complete_128_stage_lifecycle":
                facts = _full(module, case)
            elif row["name"] in EARLY_NAMES:
                facts = _early(module, case, row["name"])
            else:
                facts = _small(module, case, row["name"])
            checks.append({"case": row["name"], "status": "PASS", "facts": facts,
                           "charged_read": case.read_bytes, "charged_write": case.write_bytes})
            case.check()
        except BaseException as exc:
            totals["read"] += case.read_bytes
            totals["write"] += case.write_bytes
            raise ControlFailure(row["name"], exc, checks, totals) from exc
        totals["read"] += case.read_bytes
        totals["write"] += case.write_bytes
    result = {
        "schema": "morse-storage-control-observations-v1",
        "source_pin": dict(SOURCE_PIN), "checks": checks,
        "substitutions": [
            "module-local os facade: inert integer FDs and invented mount/stat/statvfs/scandir metadata",
            "module-local sys.platform=linux; no shared sys or os module mutation",
            "storage-only synthetic plan projection, not complete paired-plan compiler evidence",
            "small held-state seams for selected individual guard/cleanup methods; full positive uses actual constructor",
        ],
        "reservation": spec, "charged": totals, "native_evidence": False,
    }
    _need(len(_json(result)) <= spec["max_return_json_bytes"], "control result exceeded envelope")
    meter.check()
    return result

