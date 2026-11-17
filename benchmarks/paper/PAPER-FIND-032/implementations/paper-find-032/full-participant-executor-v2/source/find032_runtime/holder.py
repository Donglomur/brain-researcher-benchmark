"""Fixed read-only FIND032 output holder; ordinary bytes only, no array decoder.

The candidate must already be absent before the operator invokes inventory/chunk.
This helper never imports candidate files, executes outputs, or accepts a command.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import signal
import stat

ROOT = "/capture"
CHUNK = 65536


def require(ok, why):
    if not ok:
        raise ValueError(why)


def positive(value):
    parsed = int(value)
    require(str(parsed) == value and parsed > 0, "exact positive integer")
    return parsed


def name(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value)
            and value not in (".", ".."), "flat ordinary output name")
    return value


def identity(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_nlink,
            value.st_mode, value.st_uid, value.st_gid, value.st_mtime_ns, value.st_ctime_ns)


def root_open():
    fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        value = os.fstat(fd)
        require(stat.S_ISDIR(value.st_mode) and value.st_uid == 65534
                and value.st_gid == 65534, "fixed candidate-owned volume root")
        return fd, identity(value)
    except BaseException as error:
        close_all((fd,), error)


def member_open(root, member, cap):
    name(member)
    before = os.stat(member, dir_fd=root, follow_symlinks=False)
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
            and before.st_uid == 65534 and before.st_gid == 65534
            and 0 < before.st_size <= cap, "bounded ordinary single-link output")
    fd = os.open(member, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root)
    try:
        require(identity(before) == identity(os.fstat(fd)), "same opened output")
        return fd, before
    except BaseException as error:
        close_all((fd,), error)


def member_end(root, member, fd, before):
    require(identity(before) == identity(os.fstat(fd))
            == identity(os.stat(member, dir_fd=root, follow_symlinks=False)), "output changed")


def close_all(fds, first=None):
    secondary = []
    for fd in fds:
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as error:
                secondary.append(error)
    if first is not None:
        for error in secondary:
            first.add_note("holder descriptor-close error: " + type(error).__name__)
        raise first
    if secondary:
        for error in secondary[1:]:
            secondary[0].add_note("additional descriptor-close error: " + type(error).__name__)
        raise secondary[0]


def members(root, file_count):
    result = []
    with os.scandir(root) as entries:
        for entry in entries:
            require(len(result) < file_count, "complete finite output inventory")
            name(entry.name)
            require(not entry.is_symlink() and entry.is_file(follow_symlinks=False),
                    "no output subdirectory or alias")
            result.append(entry.name)
    require(len(result) == len(set(result)), "unique output names")
    return sorted(result)


def inventory(args):
    root = fd = None
    first = None
    result = None
    try:
        root, root_id = root_open()
        names = members(root, args.file_count)
        require(names, "nonempty complete output inventory")
        rows = []
        total = 0
        for member in names:
            fd, before = member_open(root, member, args.member_bytes)
            total += before.st_size
            require(total <= args.volume_bytes, "whole volume content bound")
            digest = hashlib.sha256()
            remaining = before.st_size
            while remaining:
                block = os.read(fd, min(CHUNK, remaining))
                require(block, "no short member read")
                digest.update(block)
                remaining -= len(block)
            member_end(root, member, fd, before)
            os.close(fd)
            fd = None
            rows.append({"name": member, "bytes": before.st_size, "sha256": digest.hexdigest()})
        require(members(root, args.file_count) == names and identity(os.fstat(root)) == root_id,
                "unchanged full output namespace")
        result = {"schema": "find032_holder_inventory_v1", "files": rows, "body_bytes_read": total}
    except BaseException as error:
        first = error
    finally:
        close_all((fd, root), first)
    return result


def chunk(args):
    root = fd = None
    first = None
    result = None
    try:
        require(type(args.offset) is int and args.offset >= 0 and 0 < args.length <= CHUNK
                and 0 < args.expected_bytes <= args.member_bytes
                and args.offset + args.length <= args.expected_bytes, "exact finite chunk range")
        root, root_id = root_open()
        fd, before = member_open(root, args.name, args.member_bytes)
        require(before.st_size == args.expected_bytes, "same requested member extent")
        require(os.lseek(fd, args.offset, os.SEEK_SET) == args.offset, "exact chunk seek")
        blocks = []
        remaining = args.length
        while remaining:
            block = os.read(fd, remaining)
            require(block, "no short chunk")
            blocks.append(block)
            remaining -= len(block)
        body = b"".join(blocks)
        member_end(root, args.name, fd, before)
        require(identity(os.fstat(root)) == root_id, "same volume root")
        result = {"schema": "find032_holder_chunk_v1", "name": args.name,
                  "file_bytes": args.expected_bytes, "offset": args.offset,
                  "chunk_bytes": len(body), "chunk_sha256": hashlib.sha256(body).hexdigest(),
                  "base64": base64.b64encode(body).decode("ascii")}
    except BaseException as error:
        first = error
    finally:
        close_all((fd, root), first)
    return result


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("action", choices=("hold", "ready", "inventory", "chunk"))
    for option in ("member-bytes", "metadata-bytes", "file-count", "volume-bytes"):
        parser.add_argument("--" + option, type=positive, required=True)
    parser.add_argument("--name")
    parser.add_argument("--offset", type=int)
    parser.add_argument("--length", type=positive)
    parser.add_argument("--expected-bytes", type=positive)
    args = parser.parse_args()
    require(args.metadata_bytes <= args.member_bytes <= args.volume_bytes,
            "nested output bounds")
    extra = (args.name, args.offset, args.length, args.expected_bytes)
    require(all(x is not None for x in extra) if args.action == "chunk"
            else all(x is None for x in extra), "closed action operands")
    if args.action in ("hold", "ready"):
        root, root_id = root_open()
        close_all((root,))
        if args.action == "hold":
            while True:
                signal.pause()
        result = {"schema": "find032_holder_ready_v1", "ready": True}
    elif args.action == "inventory":
        result = inventory(args)
    else:
        result = chunk(args)
    raw = (json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    cap = args.metadata_bytes if args.action != "chunk" else 2048 + 4 * ((CHUNK + 2) // 3)
    require(len(raw) <= cap, "bounded helper response")
    done = 0
    while done < len(raw):
        n = os.write(1, raw[done:])
        require(n > 0, "complete helper response")
        done += n


if __name__ == "__main__":
    main()
