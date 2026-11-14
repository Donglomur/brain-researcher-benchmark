"""Observe three externally prepared Linux tmpfs roots; never mount or unmount.

Future native operations only. Independent custody/runtime/storage qualification
and actual candidate UID/group/bind admission are owned by the fixed host module.
No returned field is execution authority or a qualified=True shortcut.
"""
import base64
import ctypes
import errno
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

_ROLES = ("work", "output", "logs")
_LIMIT_NAMES = {"work": "work_bytes", "output": "output_bytes", "logs": "log_bytes"}
_MOUNTINFO = "/proc/self/mountinfo"
_ACCESS_KEYS = {
    "uid", "gid", "mode", "host_uid", "host_gids", "candidate_uid",
    "candidate_gids", "candidate_access", "mount_options", "super_options",
    "optional_fields",
}


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _integer(value, *, minimum=0):
    _need(type(value) is int and value >= minimum, "nonnegative exact integer")
    return value


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _path(value):
    _need(type(value) is str and value.startswith("/") and len(value.encode()) <= 4096,
          "bounded absolute root path")
    _need("\0" not in value and "\n" not in value and "\r" not in value,
          "ordinary root path characters")
    path = Path(value)
    _need(str(path) == value and ".." not in path.parts, "canonical root path")
    _need(all(not item.is_symlink() for item in (path, *path.parents)),
          "no symbolic root ancestors")
    return path


def _tokens(value):
    _need(type(value) is list and len(value) <= 32
          and all(type(x) is str and 0 < len(x.encode()) <= 128
                  and not any(c.isspace() for c in x) and "," not in x
                  and "\0" not in x for x in value),
          "bounded exact mount option tokens")
    _need(len(value) == len(set(value)), "duplicate selected option")
    return tuple(sorted(value))


def _policy(paths, limits):
    _need(sys.platform == "linux", "Linux tmpfs observer only")
    _need(type(paths) is dict and set(paths) == set(_ROLES), "exact three storage roots")
    required = {"work_bytes", "output_bytes", "log_bytes", "mountinfo_max_bytes", "access"}
    _need(type(limits) is dict and set(limits) == required, "exact storage limit operands")
    maximum = _integer(limits["mountinfo_max_bytes"], minimum=1)
    _need(type(limits["access"]) is dict and set(limits["access"]) == set(_ROLES),
          "per-root explicit access policy")
    page = os.sysconf("SC_PAGE_SIZE")
    _need(type(page) is int and page > 0, "observed Linux page size")
    result = {}
    actual_host_uid = os.geteuid()
    actual_host_gids = sorted(set(os.getgroups()) | {os.getegid()})
    for role in _ROLES:
        path = _path(paths[role])
        selected_bytes = _integer(limits[_LIMIT_NAMES[role]], minimum=1)
        _need(selected_bytes <= 2**63 - 1 and selected_bytes % page == 0,
              "page-aligned signed64 selected capacity")
        access = limits["access"][role]
        _need(type(access) is dict and set(access) == _ACCESS_KEYS, "closed access policy")
        _need(_integer(access["uid"]) == 0, "root-owned mount root")
        _integer(access["gid"])
        mode = _integer(access["mode"])
        _need(mode <= 0o7777, "explicit permission bits only")
        _need(_integer(access["host_uid"]) == actual_host_uid, "actual host UID policy")
        _need(_integer(access["candidate_uid"], minimum=1) != 0, "nonroot candidate UID")
        _need(all(access[key] < 2**32 - 1 for key in
                  ("uid", "gid", "host_uid", "candidate_uid")), "Linux UID/GID range")
        for key in ("host_gids", "candidate_gids"):
            groups = access[key]
            _need(type(groups) is list and len(groups) <= 32
                  and all(type(x) is int and 0 <= x < 2**32 - 1 for x in groups)
                  and groups == sorted(set(groups)), "canonical actor group policy")
        _need(access["host_gids"] == actual_host_gids, "actual host groups policy")
        _need(access["candidate_access"] in ("write", "none"), "explicit candidate root access")
        if access["candidate_access"] == "write":
            _need(mode & stat.S_ISVTX, "sticky writable root protects root-owned children")
        mount_options = _tokens(access["mount_options"])
        super_options = _tokens(access["super_options"])
        optional_fields = _tokens(access["optional_fields"])
        _need({"rw", "nodev", "nosuid"}.issubset(mount_options) and "ro" not in mount_options,
              "actual rw,nodev,nosuid required")
        _need("rw" in super_options and "ro" not in super_options,
              "rw superblock required")
        # noexec may be selected or absent; scientific tool execution is not
        # silently forbidden by this observer.
        result[role] = {
            "path": str(path), "selected_bytes": selected_bytes,
            "access": {**access, "mount_options": list(mount_options),
                       "super_options": list(super_options),
                       "optional_fields": list(optional_fields)},
        }
    for i, role in enumerate(_ROLES):
        a = Path(result[role]["path"])
        for other in _ROLES[i + 1:]:
            b = Path(result[other]["path"])
            _need(not a.is_relative_to(b) and not b.is_relative_to(a),
                  "three distinct nonnested roots")
    return result, maximum, page


def _unescape(raw):
    result = bytearray()
    i = 0
    escapes = {b"040": 32, b"011": 9, b"012": 10, b"134": 92}
    while i < len(raw):
        if raw[i] == 92:
            code = raw[i + 1:i + 4]
            _need(code in escapes, "unsupported mountinfo path escape")
            result.append(escapes[code])
            i += 4
        else:
            result.append(raw[i])
            i += 1
    return bytes(result)


def _selected_mounts(raw, roots):
    _need(raw.endswith(b"\n") and b"\0" not in raw, "complete mountinfo text")
    desired = {os.fsencode(v["path"]): role for role, v in roots.items()}
    selected = {}
    device_mounts = {}
    for line in raw.splitlines():
        fields = line.split(b" ")
        _need(fields and b"" not in fields and fields.count(b"-") == 1,
              "mountinfo record grammar")
        sep = fields.index(b"-")
        _need(sep >= 6 and len(fields) == sep + 4, "mountinfo fields")
        device = fields[2].split(b":")
        _need(len(device) == 2 and all(x.isdigit() for x in device), "mount device grammar")
        device_key = (int(device[0]), int(device[1]))
        device_mounts[device_key] = device_mounts.get(device_key, 0) + 1
        point = _unescape(fields[4])
        if point not in desired:
            continue
        role = desired[point]
        _need(role not in selected, "stacked/duplicate selected mount root")
        _need(fields[0].isdigit() and fields[1].isdigit(), "mount ID grammar")
        _need(_unescape(fields[3]) == b"/" and fields[sep + 1] == b"tmpfs",
              "tmpfs filesystem root; subtree roots refused")
        selected[role] = {
            "mount_id": int(fields[0]), "parent_id": int(fields[1]),
            "major": int(device[0]), "minor": int(device[1]),
            "root": "/", "mount_point": roots[role]["path"], "fstype": "tmpfs",
            "source": fields[sep + 2].decode("utf-8", "strict"),
            "mount_options": sorted(fields[5].decode("ascii").split(",")),
            "optional_fields": sorted(x.decode("ascii") for x in fields[6:sep]),
            "super_options": sorted(fields[sep + 3].decode("ascii").split(",")),
        }
    _need(set(selected) == set(_ROLES), "all exact roots must be actual mountpoints")
    ids = {v["mount_id"] for v in selected.values()}
    devices = {(v["major"], v["minor"]) for v in selected.values()}
    _need(len(ids) == 3 and len(devices) == 3, "independent mount IDs and tmpfs devices")
    _need(all(device_mounts[device] == 1 for device in devices),
          "no additional selected-filesystem mount alias in observed host namespace")
    _need(all(v["parent_id"] not in ids for v in selected.values()), "nonnested mount ancestry")
    return selected


def _size_option(options):
    values = [x[5:] for x in options if x.startswith("size=")]
    _need(len(values) == 1 and values[0], "one explicit tmpfs size option")
    text = values[0]
    factor = 1
    if text[-1:] in ("k", "K", "m", "M", "g", "G"):
        factor = {"k": 1024, "m": 1024**2, "g": 1024**3}[text[-1].lower()]
        text = text[:-1]
    _need(text.isascii() and text.isdecimal(), "integer byte/k/m/g tmpfs size")
    return int(text) * factor


def _read_mountinfo(maximum, budget):
    budget.charge()
    fd = os.open(_MOUNTINFO, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        _need(stat.S_ISREG(before.st_mode), "ordinary proc mountinfo node")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(maximum + 1)
        after = os.fstat(fd)
        _need(len(raw) <= maximum and
              (before.st_dev, before.st_ino, before.st_mode) ==
              (after.st_dev, after.st_ino, after.st_mode),
              "bounded same proc mountinfo descriptor")
        budget.charge()
        return raw
    finally:
        os.close(fd)


def _identity(info):
    # Directory size/mtime can change as selected producers write, so they are
    # not immutable mount identity fields.
    return {"device": info.st_dev, "inode": info.st_ino,
            "uid": info.st_uid, "gid": info.st_gid,
            "mode": stat.S_IMODE(info.st_mode)}


def _mode_bits(uid, groups, info):
    if uid == 0:
        return 7  # rw tmpfs, selected trusted host root; not candidate root.
    if uid == info.st_uid:
        return (info.st_mode >> 6) & 7
    if info.st_gid in groups:
        return (info.st_mode >> 3) & 7
    return info.st_mode & 7


def _require_no_access_acl(fd):
    # Fixed Linux size-only probe: do not allocate/read an unbounded ACL body.
    # The trusted runtime qualification owns libc ABI/environment admission.
    libc = ctypes.CDLL(None, use_errno=True)
    probe = libc.fgetxattr
    probe.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t]
    probe.restype = ctypes.c_ssize_t
    ctypes.set_errno(0)
    size = probe(fd, b"system.posix_acl_access", None, 0)
    if size >= 0:
        raise ValueError("access ACL unsupported by selected mode-only policy")
    _need(ctypes.get_errno() in (errno.ENODATA, errno.ENOTSUP, errno.EOPNOTSUPP),
          "access ACL observation unavailable")


def _root_observation(path, record, selection, budget):
    budget.charge()
    before = path.lstat()
    _need(stat.S_ISDIR(before.st_mode), "ordinary mounted directory")
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        _need(_identity(before) == _identity(opened), "stable opened mount root")
        _need((os.major(opened.st_dev), os.minor(opened.st_dev)) ==
              (record["major"], record["minor"]), "mountinfo device matches opened root")
        access = selection["access"]
        _need(opened.st_uid == access["uid"] and opened.st_gid == access["gid"]
              and stat.S_IMODE(opened.st_mode) == access["mode"], "exact root ownership/mode")
        for key in ("mount_options", "super_options", "optional_fields"):
            _need(record[key] == access[key], "exact selected " + key)
        _need(_size_option(record["super_options"]) == selection["selected_bytes"],
              "explicit mounted size equals selected bytes")
        # Permission-bit calculations are not valid with a POSIX access ACL.
        _require_no_access_acl(fd)
        host_bits = _mode_bits(access["host_uid"], access["host_gids"], opened)
        candidate_bits = _mode_bits(access["candidate_uid"], access["candidate_gids"], opened)
        _need(host_bits & 3 == 3, "host actor needs root write/search access")
        if access["candidate_access"] == "write":
            _need(candidate_bits & 3 == 3, "selected candidate needs write/search access")
        else:
            _need(candidate_bits == 0, "selected candidate must have no mode access")
        values = os.fstatvfs(fd)
        _need(values.f_frsize > 0 and values.f_blocks >= 0
              and 0 <= values.f_bavail <= values.f_bfree <= values.f_blocks,
              "valid observed tmpfs capacity counters")
        capacity = values.f_blocks * values.f_frsize
        _need(0 < capacity <= selection["selected_bytes"], "actual capacity within selected limit")
        _need(_identity(opened) == _identity(os.fstat(fd)) == _identity(path.lstat()),
              "root identity unchanged during statvfs")
        budget.charge()
        return {
            "mount": record, "root_identity": _identity(opened),
            "selected_bytes": selection["selected_bytes"],
            "access_observation": {"host_uid": access["host_uid"],
                                   "host_gids": access["host_gids"],
                                   "host_rwx_bits": host_bits,
                                   "candidate_uid_from_policy": access["candidate_uid"],
                                   "candidate_gids_from_policy": access["candidate_gids"],
                                   "candidate_rwx_bits_from_mode": candidate_bits,
                                   "candidate_access": access["candidate_access"],
                                   "access_acl": "absent_or_filesystem_unsupported"},
            "statvfs": {"fragment_bytes": values.f_frsize, "blocks": values.f_blocks,
                        "free_blocks": values.f_bfree, "available_blocks": values.f_bavail,
                        "capacity_bytes": capacity,
                        "allocated_bytes": (values.f_blocks - values.f_bfree) * values.f_frsize,
                        "available_bytes": values.f_bavail * values.f_frsize},
        }
    finally:
        os.close(fd)


def admit_storage(paths, limits, budget):
    """Observe exact selected externally prepared mounts twice around root checks.

    Logical precharge: read=2*(mountinfo_max_bytes+1),
    write=16*mountinfo_max_bytes+131072 for retained observation construction,
    including conservative JSON escaping and original-observation copies.
    Independent mount custody and physical qualification are not minted here.
    """
    budget.charge()
    roots, maximum, page = _policy(paths, limits)
    output_bound = 16 * maximum + 131072
    budget.charge(read=2 * (maximum + 1), write=output_bound)
    first = _read_mountinfo(maximum, budget)
    before = _selected_mounts(first, roots)
    observations = {
        role: _root_observation(Path(roots[role]["path"]), before[role], roots[role], budget)
        for role in _ROLES
    }
    second = _read_mountinfo(maximum, budget)
    _need(_selected_mounts(second, roots) == before, "selected mount records changed during admission")
    body = {
        "schema": "tms_external_tmpfs_observation_v1",
        "policy_pin": _pin(_encode({"paths": paths, "limits": limits})),
        "page_bytes": page,
        "mountinfo_observations": [
            {"pin": _pin(raw), "base64": base64.b64encode(raw).decode("ascii")}
            for raw in (first, second)
        ],
        "roots": observations,
        "scope": "Observed root mounts/capacities/mode access only; independent custody and candidate UID/bind qualification remain external.",
    }
    encoded = _encode(body)
    _need(len(encoded) <= output_bound, "storage observation construction bound")
    budget.charge()
    return {"observation": body, "pin": _pin(encoded)}


def recheck_storage(admission, paths, limits, budget):
    """Reobserve after actual producer closure, refusing root/mount policy drift."""
    budget.charge()
    _need(type(admission) is dict and set(admission) == {"observation", "pin"},
          "exact prior storage observation envelope")
    _need(type(limits) is dict and "mountinfo_max_bytes" in limits,
          "selected observation bound")
    bound = 16 * _integer(limits["mountinfo_max_bytes"], minimum=1) + 131072
    prior_pin = admission["pin"]
    _need(type(prior_pin) is dict and set(prior_pin) == {"bytes", "sha256"}
          and type(prior_pin["bytes"]) is int and 0 < prior_pin["bytes"] <= bound
          and type(prior_pin["sha256"]) is str and len(prior_pin["sha256"]) == 64
          and all(c in "0123456789abcdef" for c in prior_pin["sha256"]),
          "bounded prior observation pin")
    budget.charge(read=2 * prior_pin["bytes"], write=prior_pin["bytes"])
    previous = admission["observation"]
    _need(type(previous) is dict
          and set(previous) == {"schema", "policy_pin", "page_bytes",
                               "mountinfo_observations", "roots", "scope"}
          and previous["schema"] == "tms_external_tmpfs_observation_v1",
          "prior storage observation schema")
    # Caller has already admitted this private observation under its source/I/O
    # envelope. This hash is integrity, never a self-issued runtime authority.
    _need(_pin(_encode(previous)) == admission["pin"], "prior observation content pin")
    current = admit_storage(paths, limits, budget)
    now = current["observation"]
    _need(previous["policy_pin"] == now["policy_pin"]
          and previous["page_bytes"] == now["page_bytes"], "same selected storage policy")
    _need(set(previous["roots"]) == set(_ROLES), "prior exact three roots")
    for role in _ROLES:
        old, new = previous["roots"][role], now["roots"][role]
        _need(old["mount"] == new["mount"]
              and old["root_identity"] == new["root_identity"]
              and old["selected_bytes"] == new["selected_bytes"]
              and old["access_observation"] == new["access_observation"],
              "same admitted mount/root/access identity after producer closure")
    current["prior_observation_pin"] = dict(admission["pin"])
    budget.charge()
    return current
