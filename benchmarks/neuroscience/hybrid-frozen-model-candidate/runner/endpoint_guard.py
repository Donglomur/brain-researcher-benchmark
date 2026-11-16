"""Physical Docker endpoint guard reused from the accepted Hybrid R owner."""
import hashlib
import os
import stat
from pathlib import Path
from donor_checked_source import need


def endpoint_identity(plan):
    binding = plan["endpoint_binding"]; expected = binding["expected_observation"]
    link = Path(binding["original_executable_path"])
    need(link.is_symlink() and os.readlink(link) == binding["original_symlink_target"], "Docker alias")
    target = link.resolve(strict=True); need(str(target) == expected["binary"]["path"], "Docker resolution")
    socket = Path(binding["socket"]["path"])
    for path in (target, socket):
        need(path.is_absolute() and ".." not in path.parts and not any(x.is_symlink() for x in (path, *path.parents)), "endpoint ancestry")
    binary = target.lstat(); sock = socket.lstat()
    need(stat.S_ISREG(binary.st_mode) and os.access(target, os.X_OK) and stat.S_ISSOCK(sock.st_mode), "endpoint types")
    stamp = lambda v: [v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_ctime_ns, v.st_nlink]
    observed = {"binary": {"path": str(target), "physical_identity": stamp(binary), "mode": binary.st_mode, "uid": binary.st_uid, "gid": binary.st_gid},
                "socket": {"path": str(socket), "physical_identity": stamp(sock), "mode": sock.st_mode, "uid": sock.st_uid, "gid": sock.st_gid}}
    need(observed == expected, "exact selected Docker physical authority")
    return observed


def authenticate_endpoint_binary(plan):
    before = endpoint_identity(plan); p = Path(before["binary"]["path"])
    need(p.stat().st_size <= 32 * 1024**2, "complete Docker executable bound")
    h = hashlib.sha256(); used = 0
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            used += len(b); need(used <= 32 * 1024**2, "Docker read cap"); h.update(b)
    need(h.hexdigest() == plan["endpoint_binding"]["binary_historical_sha256"] and endpoint_identity(plan) == before,
         "complete unchanged Docker executable")
    return {"bytes": used, "sha256": h.hexdigest(), "physical": before}
