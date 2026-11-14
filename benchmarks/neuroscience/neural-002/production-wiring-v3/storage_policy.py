"""Morse-only admission of independently provisioned private Linux tmpfs roots.

No mount, chmod, mkdir, native qualification issuer, or scientific execution.
The caller authenticates the config file and compiled plan before construction.
This source has not been executed against a native mount namespace.
"""
import hashlib
import json
import os
import re
import stat
import sys

SCHEMA = "morse-preprovisioned-tmpfs-v1"
MECHANISM = "independently_admitted_bounded_host_volumes_v1"
PEOPLE = tuple("sub-%02d" % n for n in range(1, 33))
MODES = ("frozen_program", "case_adaptive")
PHASES = ("train", "query")
CONFIG_KEYS = frozenset((
    "schema", "admission_id", "host_uid", "max_mountinfo_bytes",
    "max_mountinfo_entries", "max_directory_entries", "max_receipt_bytes",
    "campaign", "stages",
))
ROOT_KEYS = frozenset((
    "path", "mount_id", "device_major", "device_minor", "device", "inode",
    "uid", "gid", "mode", "bytes", "inodes",
))
PROFILE_KEYS = frozenset((
    "mechanism", "admission_id", "output_root", "workspace_root",
    "output_bytes", "workspace_bytes",
))
STAGE_KEYS = frozenset(("participant", "mode", "phase", "output", "workspace"))


class StorageFailure(RuntimeError):
    """Raw first/secondary exceptions survive cleanup and failed admission."""
    def __init__(self, first, secondary, receipt):
        super().__init__("Morse storage admission/closure failed; inspect raw causes")
        self.first = first
        self.secondary = tuple(secondary)
        self.receipt = receipt


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _exact(value, keys, message):
    _require(type(value) is dict and set(value) == keys, message)


def _integer(value, name, *, zero=False):
    _require(type(value) is int and (0 if zero else 1) <= value <= 2**64 - 1,
             name + ": explicit kernel-sized integer required")
    return value


def _path(value, *, root_allowed=False):
    _require(type(value) is str and value.startswith("/") and "\0" not in value,
             "absolute ordinary root path required")
    value.encode("utf-8", "strict")
    _require(os.path.normpath(value) == value and "//" not in value
             and (root_allowed or value != "/"), "canonical root path required")
    return value


def _canonical(value, cap):
    """Bound the accumulated ASCII JSON body, including the source newline."""
    parts, used = [], 0
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"),
                               allow_nan=False, ensure_ascii=True)
    for chunk in encoder.iterencode(value):
        _require(len(chunk) <= cap - used - 1, "metadata serialization cap")
        parts.append(chunk)
        used += len(chunk)
    return ("".join(parts) + "\n").encode("ascii")


def _decode_mount_path(value):
    # Linux mountinfo escapes only these four characters. Reject ambiguity.
    out, at = [], 0
    escapes = {"040": " ", "011": "\t", "012": "\n", "134": "\\"}
    while at < len(value):
        if value[at] == "\\":
            _require(value[at+1:at+4] in escapes, "unknown mountinfo escape")
            out.append(escapes[value[at+1:at+4]])
            at += 4
        else:
            out.append(value[at])
            at += 1
    return "".join(out)


def _decimal(value, *, zero=False):
    _require(re.fullmatch(r"0|[1-9][0-9]*", value) is not None,
             "noncanonical mountinfo decimal")
    return _integer(int(value), "mountinfo integer", zero=zero)


class PreprovisionedStorage:
    """One sequential 32-participant / two-mode / two-stage storage campaign."""
    def __init__(self, plan, config, budget):
        self._budget = budget
        self._fds = {}
        self._expected = {}
        self._rows = {}
        self._pairs = {}
        self._selected = set()
        self._consumed = set()
        self._events = []
        self._event_bytes = 0
        self._first = None
        self._secondary = []
        self._unknown_closes = []
        self._state = "initializing"
        self.plan_sha256 = None
        self.config_sha256 = None
        self.admission_id = None
        self._metadata_cap = 0
        try:
            budget.check()
            _require(sys.platform == "linux", "Linux mountinfo/statvfs profile required")
            _exact(config, CONFIG_KEYS, "closed storage configuration required")
            _require(config["schema"] == SCHEMA, "storage schema")
            for key in ("host_uid", "max_mountinfo_bytes", "max_mountinfo_entries",
                        "max_directory_entries", "max_receipt_bytes"):
                _integer(config[key], key)
            self._metadata_cap = config["max_receipt_bytes"]
            # Plan/config canonical buffers plus retained and final receipt buffers.
            # This is a prospective logical transfer reservation, not OS-I/O or RAM.
            budget.write(4 * self._metadata_cap)
            self._mount_cap = config["max_mountinfo_bytes"]
            self._mount_entries = config["max_mountinfo_entries"]
            self._directory_entries = config["max_directory_entries"]
            self._directory_seen = 0
            self._uid = config["host_uid"]
            _require(self._uid == os.getuid() == os.geteuid() and self._uid > 0,
                     "selected unprivileged real/effective host UID required")
            _require(type(plan) is dict and type(plan.get("spec")) is dict,
                     "compiled paired plan required")
            spec = plan["spec"]
            _require(type(plan.get("sha256")) is str
                     and re.fullmatch(r"[0-9a-f]{64}", plan["sha256"]) is not None,
                     "compiled plan digest")
            _require(hashlib.sha256(_canonical(spec, self._metadata_cap)).hexdigest()
                     == plan["sha256"], "compiled plan canonical digest mismatch")
            _require(spec.get("people") == list(PEOPLE) and spec.get("modes") == list(MODES)
                     and plan.get("logical_contexts") == 64
                     and type(plan.get("logical_contexts")) is int
                     and plan.get("stage_launches") == 128
                     and type(plan.get("stage_launches")) is int,
                     "complete 32-person/two-mode/128-stage plan required")
            _require(spec["environment"]["container_uid"] == self._uid
                     and type(spec["environment"]["container_uid"]) is int,
                     "container and host UID must be identical")
            self.plan_sha256 = plan["sha256"]
            _require(type(config["admission_id"]) is str and config["admission_id"]
                     and config["admission_id"] == spec["storage_admission_id"],
                     "fixed storage admission identity mismatch")
            self.admission_id = config["admission_id"]
            self.config_sha256 = hashlib.sha256(
                _canonical(config, self._metadata_cap)).hexdigest()
            stage_limits = spec["stage_limits"]
            for key in ("output_bytes", "workspace_bytes"):
                _integer(stage_limits[key], key)
            _integer(spec["total_reserved_bytes"], "total_reserved_bytes")
            self._add_root("campaign", config["campaign"])
            _require(config["campaign"]["bytes"] >= spec["total_reserved_bytes"],
                     "campaign ceiling omits full declared retained reservation")
            _require(type(config["stages"]) is list and len(config["stages"]) == 128,
                     "exact 128 provisioned stages required")
            index = 0
            for person in PEOPLE:
                for mode in MODES:
                    context_id = hashlib.sha256(
                        (self.plan_sha256 + person + mode).encode()).hexdigest()[:32]
                    for phase in PHASES:
                        row = config["stages"][index]
                        index += 1
                        _exact(row, STAGE_KEYS, "closed stage-root row")
                        _require((row["participant"], row["mode"], row["phase"])
                                 == (person, mode, phase), "complete deterministic stage order")
                        key = (context_id, mode, phase)
                        names = (person + "/" + mode + "/" + phase + "/output",
                                 person + "/" + mode + "/" + phase + "/workspace")
                        self._add_root(names[0], row["output"])
                        self._add_root(names[1], row["workspace"])
                        _require(row["output"]["bytes"] == stage_limits["output_bytes"]
                                 and row["workspace"]["bytes"] == stage_limits["workspace_bytes"],
                                 "stage capacity differs from selected worker limits")
                        self._rows[key] = names
                        pair = (row["output"]["path"], row["workspace"]["path"])
                        _require(pair not in self._pairs, "duplicate root pair")
                        self._pairs[pair] = key
            self._validate_distinct_roots()
            table, table_pin = self._mountinfo()
            for name in self._expected:
                budget.check()
                fd = self._open_root(self._expected[name]["path"])
                self._fds[name] = fd
                self._check_root(name, table, table_pin, "initial", fresh_path=False)
                self._check_empty(name)
            self._state = "ready"
            self._event({"event": "all_roots_admitted", "roots": 257, "stages": 128})
            budget.check()
        except BaseException as exc:
            self._remember(exc, "constructor")
            self._close_all()
            self._state = "closure_unknown" if self._unknown_closes else "failed_closed"
            raise self._failure() from exc

    def _remember(self, exc, where):
        if isinstance(exc, StorageFailure) and exc.first is self._first:
            return
        item = {"where": where, "error": exc}
        if self._first is None:
            self._first = item
        else:
            self._secondary.append(item)

    def _failure(self):
        return StorageFailure(self._first, self._secondary, self._receipt())

    def _receipt(self):
        return {
            "schema": "morse-preprovisioned-storage-receipt-v1",
            "plan_sha256": self.plan_sha256,
            "config_semantic_sha256": self.config_sha256,
            "admission_id": self.admission_id,
            "state": self._state,
            "complete": self._state == "finalized",
            "required_stages": 128,
            "selected_stages": len(self._selected),
            "consumed_stages": len(self._consumed),
            "held_descriptors": len(self._fds),
            "descriptor_closure": "unknown" if self._unknown_closes else
                                  ("held" if self._fds else "closed"),
            "unknown_close_locations": list(self._unknown_closes),
            "first_error_type": None if self._first is None else
                                type(self._first["error"]).__name__,
            "secondary_error_types": [type(x["error"]).__name__ for x in self._secondary],
            "observations": list(self._events),
            "qualification": "external_runtime_assessment_still_required",
            "stage_execution_or_process_closure": "not_observed_by_storage_policy",
            "interpretation": "kernel capacity/identity observations; not cumulative I/O, CPU, memory, or scientific qualification",
        }

    def _event(self, value):
        # Event buffering is charged by the constructor's retained-receipt reserve.
        raw = _canonical(value, self._metadata_cap - self._event_bytes)
        self._event_bytes += len(raw)
        self._events.append(value)

    def _add_root(self, name, row):
        _exact(row, ROOT_KEYS, "closed tmpfs root descriptor")
        _path(row["path"])
        for key in ROOT_KEYS - {"path"}:
            _integer(row[key], key, zero=key in ("device_major", "device_minor", "gid"))
        _require(row["mode"] == 0o700 and row["uid"] == self._uid,
                 "0700 selected-host-owned directory required")
        _require(row["device"] == os.makedev(row["device_major"], row["device_minor"]),
                 "selected st_dev differs from kernel major/minor pair")
        self._expected[name] = dict(row)

    def _validate_distinct_roots(self):
        roots = list(self._expected.values())
        _require(len(roots) == 257, "exact campaign plus256 stage roots")
        for field in ("path", "mount_id", "device"):
            _require(len({x[field] for x in roots}) == len(roots),
                     "shared root/mount/device alias: " + field)
        for i, left in enumerate(roots):
            self._budget.check()
            for right in roots[i+1:]:
                _require(not left["path"].startswith(right["path"] + "/")
                         and not right["path"].startswith(left["path"] + "/"),
                         "nested campaign/stage roots forbidden")

    def _close_owned(self, fd, where):
        # An unsuccessful close retires the numeric FD: retrying might close a
        # reused descriptor. Unknown closure is retained, never called success.
        try:
            os.close(fd)
        except BaseException as exc:
            self._unknown_closes.append(where)
            self._remember(exc, where)

    def _open_root(self, path):
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = None
        try:
            self._budget.check()
            fd = os.open("/", flags)
            for component in path.split("/")[1:]:
                self._budget.check()
                child = os.open(component, flags, dir_fd=fd)
                old, fd = fd, child
                self._close_owned(old, "root_traversal_parent")
                if self._first is not None:
                    raise self._failure()
            result, fd = fd, None
            return result
        except BaseException as exc:
            self._remember(exc, "root_traversal")
            if fd is not None:
                self._close_owned(fd, "root_traversal_failed_leaf")
            raise self._failure() from exc

    def _mountinfo(self):
        self._budget.check()
        self._budget.read(self._mount_cap + 1)
        # Bounded acquisition/join/decode/parse copies, not physical memory proof.
        self._budget.write(3 * (self._mount_cap + 1))
        fd, parts, total = None, [], 0
        try:
            fd = os.open("/proc/self/mountinfo",
                         os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            _require(stat.S_ISREG(os.fstat(fd).st_mode), "ordinary proc mountinfo required")
            while True:
                self._budget.check()
                part = os.read(fd, min(65536, self._mount_cap + 1 - total))
                if not part:
                    break
                parts.append(part)
                total += len(part)
                _require(total <= self._mount_cap, "mountinfo byte cap exceeded")
            raw = b"".join(parts)
            _require(raw.endswith(b"\n") and b"\0" not in raw, "complete mountinfo body")
        except BaseException as exc:
            self._remember(exc, "mountinfo_body")
        finally:
            if fd is not None:
                self._close_owned(fd, "mountinfo_descriptor")
        if self._first is not None:
            raise self._failure()
        text = raw.decode("utf-8", "strict")
        lines = text.splitlines()
        _require(0 < len(lines) <= self._mount_entries, "mountinfo entry cap")
        table, ids = {}, set()
        for line in lines:
            self._budget.check()
            parts = line.split(" ")
            _require("" not in parts and parts.count("-") == 1, "mountinfo framing")
            split = parts.index("-")
            _require(split >= 6 and len(parts) == split + 4, "mountinfo closed fields")
            mount_id, parent = _decimal(parts[0]), _decimal(parts[1], zero=True)
            dev = parts[2].split(":")
            _require(len(dev) == 2, "mountinfo device pair")
            major, minor = _decimal(dev[0], zero=True), _decimal(dev[1], zero=True)
            root = _path(_decode_mount_path(parts[3]), root_allowed=True)
            point = _path(_decode_mount_path(parts[4]), root_allowed=True)
            optional = parts[6:split]
            for item in optional:
                _require(item == "unbindable" or
                         re.fullmatch(r"(shared|master|propagate_from):[1-9][0-9]*", item)
                         is not None, "unknown mountinfo optional field")
            _require(mount_id not in ids and point not in table, "ambiguous mount table")
            ids.add(mount_id)
            table[point] = {
                "mount_id": mount_id, "parent": parent, "device_major": major,
                "device_minor": minor, "root": root, "options": parts[5].split(","),
                "optional": optional, "fstype": parts[split+1],
                "source": _decode_mount_path(parts[split+2]),
                "super_options": parts[split+3].split(","),
            }
        pin = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
               "entries": len(lines)}
        return table, pin

    def _check_root(self, name, table, table_pin, event, *, fresh_path=True):
        self._budget.check()
        expected = self._expected[name]
        fd = self._fds[name]
        s = os.fstat(fd)
        actual_identity = (s.st_dev, s.st_ino, s.st_uid, s.st_gid,
                           stat.S_IMODE(s.st_mode))
        wanted = tuple(expected[k] for k in ("device", "inode", "uid", "gid", "mode"))
        _require(stat.S_ISDIR(s.st_mode) and actual_identity == wanted,
                 "held root physical identity/ownership changed")
        if fresh_path:
            probe = self._open_root(expected["path"])
            try:
                current = os.fstat(probe)
                _require((current.st_dev, current.st_ino) == (s.st_dev, s.st_ino),
                         "root path no longer names held directory")
            except BaseException as exc:
                self._remember(exc, "root_path_identity")
            finally:
                self._close_owned(probe, "root_path_probe")
            if self._first is not None:
                raise self._failure()
        mount = table.get(expected["path"])
        _require(mount is not None and mount["fstype"] == "tmpfs"
                 and mount["root"] == "/" and mount["mount_id"] == expected["mount_id"]
                 and mount["device_major"] == expected["device_major"]
                 and mount["device_minor"] == expected["device_minor"],
                 "exact independent tmpfs mount identity required")
        _require("rw" in mount["options"] and "ro" not in mount["options"]
                 and "rw" in mount["super_options"] and "ro" not in mount["super_options"]
                 and not any(x.startswith(("shared:", "master:", "propagate_from:"))
                             for x in mount["optional"]),
                 "private writable tmpfs mount required")
        aliases = sum((m["device_major"], m["device_minor"]) ==
                      (expected["device_major"], expected["device_minor"])
                      for m in table.values())
        _require(aliases == 1, "tmpfs device has another alias in current mount namespace")
        _require(not any(point.startswith(expected["path"] + "/") for point in table),
                 "nested mount could bypass the selected tmpfs capacity")
        v = os.fstatvfs(fd)
        _require(v.f_frsize > 0 and v.f_blocks > 0 and v.f_files > 0
                 and v.f_blocks * v.f_frsize == expected["bytes"]
                 and v.f_files == expected["inodes"]
                 and not v.f_flag & os.ST_RDONLY,
                 "kernel byte/inode capacity differs from selected ceiling")
        self._event({
            "event": event, "root": name, "path": expected["path"],
            "mountinfo": dict(table_pin), "mount_id": mount["mount_id"],
            "device": s.st_dev, "inode": s.st_ino, "uid": s.st_uid, "gid": s.st_gid,
            "mode": stat.S_IMODE(s.st_mode), "f_blocks": v.f_blocks,
            "f_frsize": v.f_frsize, "byte_ceiling": v.f_blocks * v.f_frsize,
            "inode_ceiling": v.f_files, "f_flag": v.f_flag,
        })
        self._budget.check()

    def _check_empty(self, name):
        iterator = None
        try:
            self._budget.check()
            iterator = os.scandir(self._fds[name])
            member = next(iterator, None)
            if member is not None:
                self._directory_seen += 1
                _require(self._directory_seen <= self._directory_entries,
                         "initial directory-entry budget exceeded")
                raise ValueError("preprovisioned root is not initially empty: " + name)
        except BaseException as exc:
            self._remember(exc, "initial_empty_scan")
        finally:
            if iterator is not None:
                try:
                    iterator.close()
                except BaseException as exc:
                    self._unknown_closes.append("initial_scan_iterator")
                    self._remember(exc, "initial_scan_iterator")
        if self._first is not None:
            raise self._failure()
        self._budget.check()

    def stage_roots(self, context_id, mode, phase):
        try:
            self._budget.check()
            _require(self._state == "ready" and self._first is None, "storage policy not usable")
            key = (context_id, mode, phase)
            _require(key in self._rows and key not in self._selected, "unknown/reused stage")
            names = self._rows[key]
            result = {"output_root": self._expected[names[0]]["path"],
                      "workspace_root": self._expected[names[1]]["path"]}
            self._event({"event": "stage_selected", "context_id": context_id,
                         "mode": mode, "phase": phase})
            self._budget.check()
            self._selected.add(key)
            return result
        except BaseException as exc:
            self._remember(exc, "stage_roots")
            self._state = "failed"
            raise self._failure() from exc

    def require_storage(self, profile):
        try:
            self._budget.check()
            _require(self._state == "ready" and self._first is None, "storage policy not usable")
            _exact(profile, PROFILE_KEYS, "closed incumbent storage profile")
            _require(profile["mechanism"] == MECHANISM
                     and profile["admission_id"] == self.admission_id, "storage profile identity")
            pair = (profile["output_root"], profile["workspace_root"])
            _require(pair in self._pairs, "storage root pair is not selected")
            key = self._pairs[pair]
            _require(key in self._selected and key not in self._consumed,
                     "stage must be selected once before one admission")
            names = self._rows[key]
            for name, field in zip(names, ("output_bytes", "workspace_bytes")):
                _require(type(profile[field]) is int
                         and profile[field] == self._expected[name]["bytes"],
                         "storage profile capacity mismatch")
            table, pin = self._mountinfo()
            # Campaign may now contain exports/context/state; no emptiness repeat.
            self._check_root("campaign", table, pin, "stage_admission")
            for name in names:
                self._check_root(name, table, pin, "stage_admission")
            self._event({"event": "stage_admitted", "context_id": key[0],
                         "mode": key[1], "phase": key[2]})
            self._budget.check()
            self._consumed.add(key)
        except BaseException as exc:
            self._remember(exc, "require_storage")
            self._state = "failed"
            raise self._failure() from exc

    def _close_all(self):
        # Remove numeric ownership before close; uncertain descriptors are never
        # retried. Attempt all remaining independent closes despite any failure.
        for name in reversed(tuple(self._fds)):
            fd = self._fds.pop(name)
            self._close_owned(fd, "held_root:" + name)

    def finalize(self):
        try:
            self._budget.check()
            _require(self._state == "ready" and self._first is None, "failed/closed policy")
            _require(len(self._selected) == len(self._consumed) == 128,
                     "normal finalization requires every selected stage admitted")
            self._state = "finalizing"
            table, pin = self._mountinfo()
            for name in self._expected:
                self._check_root(name, table, pin, "final")
        except BaseException as exc:
            self._remember(exc, "finalize")
        finally:
            self._close_all()
        try:
            self._budget.check()
        except BaseException as exc:
            self._remember(exc, "final_deadline")
        if self._first is not None:
            self._state = "closure_unknown" if self._unknown_closes else "failed_closed"
            raise self._failure()
        self._state = "finalized"
        try:
            result = self._receipt()
            _canonical(result, self._metadata_cap)
            self._budget.check()
            return result
        except BaseException as exc:
            self._remember(exc, "final_receipt")
            self._state = "failed_closed"
            raise self._failure() from exc

    def close_failed(self):
        # Callable after a partially consumed campaign or caller-owned failure.
        # No completion claim follows solely from descriptor cleanup.
        self._state = "failed"
        self._close_all()
        try:
            self._budget.check()
        except BaseException as exc:
            self._remember(exc, "failed_close_deadline")
        self._state = "closure_unknown" if self._unknown_closes else "failed_closed"
        if self._first is not None:
            raise self._failure()
        try:
            result = self._receipt()
            _canonical(result, self._metadata_cap)
            self._budget.check()
            return result
        except BaseException as exc:
            self._remember(exc, "failed_close_receipt")
            raise self._failure() from exc

