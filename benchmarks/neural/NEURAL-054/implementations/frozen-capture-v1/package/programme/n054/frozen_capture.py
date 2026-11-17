"""Bounded same-host reads of an independently frozen container's tmpfs.

Only /proc/PID/root is intentionally followed as a kernel magic link. Every
participant-controlled component is opened relative to a held directory FD.
This source is not evidence that a particular host permits these reads.
"""
import hashlib
import os
import stat
import sys
import time


class CaptureError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CaptureError(message)


def signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_dir(name, parent=None):
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                   dir_fd=parent)


def _metadata(fd, name, cap=4096):
    item = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        raw = os.read(item, cap + 1)
        require(len(raw) <= cap, 'Process metadata cap')
        return raw
    finally:
        os.close(item)


def parse_process_stat(raw, pid):
    # comm may contain spaces and parentheses; the last ')' terminates it.
    require(raw.startswith((str(pid) + ' (').encode()), 'Original PID mismatch')
    end = raw.rfind(b')')
    fields = raw[end + 1:].split()
    require(end > 0 and len(fields) >= 20, 'Process stat shape')
    start = fields[19]
    require(start.isdigit(), 'Original process starttime')
    return int(start)


def _identity(proc_fd, root_fd, pid):
    start = parse_process_stat(_metadata(proc_fd, 'stat'), pid)
    group = _metadata(proc_fd, 'cgroup').decode('ascii')
    rows = group.splitlines()
    require(len(rows) == 1 and rows[0].startswith('0::/'), 'One unified cgroup')
    path = rows[0][3:]
    require('..' not in path.split('/'), 'Cgroup traversal')
    proc = os.fstat(proc_fd)
    root = os.fstat(root_fd)
    return {'pid': pid, 'starttime': start, 'cgroup': path,
            'proc_identity': [proc.st_dev, proc.st_ino],
            'root_identity': [root.st_dev, root.st_ino]}


def process_identity(pid):
    require(sys.platform == 'linux' and type(pid) is int and pid > 0,
            'Same-host Linux process identity required')
    proc = _open_dir('/proc/' + str(pid))
    root = None
    try:
        # proc is a held kernel procfs directory, not a participant input path.
        root = os.open('root', os.O_RDONLY | os.O_DIRECTORY, dir_fd=proc)
        return _identity(proc, root, pid)
    finally:
        if root is not None:
            os.close(root)
        os.close(proc)


def _close_copy_fds(fds, budget):
    failed = []
    for fd in fds:
        if fd is not None:
            try:
                os.close(fd)
            except OSError as error:
                failed.append(type(error).__name__ + ': ' + str(error))
    budget['nested_fd_close_errors'].extend(failed)
    require(not failed, 'Nested capture descriptor closure failed')


def _boundary(budget, check):
    remaining = budget['deadline'] - time.monotonic()
    require(remaining > 0, 'Capture boundary deadline')
    return check(remaining)


def _copy_tree(source_fd, destination_fd, budget, prefix='', depth=0):
    require(depth <= 64, 'Directory depth cap')
    before = os.fstat(source_fd)
    names = []
    with os.scandir(source_fd) as iterator:
        for entry in iterator:
            require(time.monotonic() <= budget['deadline'], 'Capture deadline')
            budget['entries'] += 1
            require(budget['entries'] <= budget['entry_cap'], 'Directory entry cap')
            name = entry.name
            encoded = name.encode('utf-8', 'strict')
            require(name not in ('', '.', '..') and '/' not in name and '\x00' not in name
                    and len(encoded) <= 255 and len((prefix + name).encode()) <= 4096,
                    'Bounded relative member name')
            names.append(name)
    for name in sorted(names):
        require(time.monotonic() <= budget['deadline'], 'Capture deadline')
        before_name = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
        relative = prefix + name
        if stat.S_ISDIR(before_name.st_mode):
            child = _open_dir(name, source_fd)
            dest = None
            try:
                require(signature(os.fstat(child)) == signature(before_name), 'Directory identity changed')
                os.mkdir(name, 0o700, dir_fd=destination_fd)
                budget['created_directories'] += 1
                dest = _open_dir(name, destination_fd)
                budget['roster'].append({'path': relative, 'kind': 'directory'})
                _copy_tree(child, dest, budget, relative + '/', depth + 1)
                require(signature(os.stat(name, dir_fd=source_fd, follow_symlinks=False)) ==
                        signature(before_name), 'Directory name changed')
            finally:
                _close_copy_fds((dest, child), budget)
            continue
        require(stat.S_ISREG(before_name.st_mode) and before_name.st_nlink == 1,
                'Only ordinary single-link files')
        budget['files'] += 1
        require(budget['files'] <= budget['file_cap'], 'File count cap')
        require(before_name.st_size <= budget['byte_cap'] - budget['bytes_read'], 'File byte cap')
        item = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=source_fd)
        output = None
        try:
            require(signature(os.fstat(item)) == signature(before_name), 'Opened file identity changed')
            output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=destination_fd)
            remaining = before_name.st_size
            sha = hashlib.sha256()
            while remaining:
                require(time.monotonic() <= budget['deadline'], 'Capture deadline')
                block = os.read(item, min(65536, remaining))
                budget['bytes_read'] += len(block)
                require(block, 'Truncated source file')
                sha.update(block)
                view = memoryview(block)
                while view:
                    written = os.write(output, view)
                    require(written > 0, 'Capture destination write')
                    budget['bytes_written'] += written
                    view = view[written:]
                remaining -= len(block)
            excess = os.read(item, 1)
            budget['bytes_read'] += len(excess)
            require(not excess, 'Source file grew')
            require(signature(os.fstat(item)) == signature(before_name) and
                    signature(os.stat(name, dir_fd=source_fd, follow_symlinks=False)) == signature(before_name),
                    'Source file changed during capture')
            budget['roster'].append({'path': relative, 'kind': 'file',
                                    'bytes': before_name.st_size, 'sha256': sha.hexdigest()})
        finally:
            _close_copy_fds((output, item), budget)
    require(signature(os.fstat(source_fd)) == signature(before), 'Directory changed during capture')


def capture(pid, expected, source, destination, file_cap, byte_cap, wall_s, assert_frozen):
    """Copy /work or /observed while the original whole-container freeze holds.

    A failure carries partial logical counts and FD-close evidence. Partial host
    files remain quarantined by the caller's failed original-process record.
    """
    require(type(pid) is int and pid > 0, 'Positive original PID')
    require(source in ('/work', '/observed'), 'Fixed tmpfs source only')
    require(all(type(x) is int and x > 0 for x in (file_cap, byte_cap, wall_s)), 'Positive capture caps')
    budget = {'files': 0, 'entries': 0, 'created_directories': 0,
              'bytes_read': 0, 'bytes_written': 0, 'roster': [], 'nested_fd_close_errors': [],
              'file_cap': file_cap, 'entry_cap': file_cap * 2 + 4,
              'byte_cap': byte_cap, 'deadline': time.monotonic() + wall_s}
    descriptors = []
    before_cpu = time.process_time()
    proof = {'schema': 'n054_frozen_namespace_capture_v1', 'source': source,
             'process_identity': expected, 'transport': 'same_host_proc_root_directory_fds',
             'fd_closure_complete': False, 'complete': False,
             'physical_IO_measured': False,
             'separate_process_metadata_read_allowance_bytes': 4 * 4097}
    primary = None
    try:
        require(sys.platform == 'linux', 'Same-host Linux proc root required')
        proc = _open_dir('/proc/' + str(pid)); descriptors.append(proc)
        root = os.open('root', os.O_RDONLY | os.O_DIRECTORY, dir_fd=proc); descriptors.append(root)
        require(_identity(proc, root, pid) == expected, 'Original process identity changed')
        proof['boundary_before'] = _boundary(budget, assert_frozen)
        folder = _open_dir(source[1:], root); descriptors.append(folder)
        source_identity = signature(os.fstat(folder))
        require(signature(os.stat(source[1:], dir_fd=root, follow_symlinks=False)) == source_identity,
                'Top-level source identity changed')
        dest = _open_dir(os.fspath(destination)); descriptors.append(dest)
        _copy_tree(folder, dest, budget)
        require(signature(os.stat(source[1:], dir_fd=root, follow_symlinks=False)) == source_identity,
                'Top-level source name changed after capture')
        require(_identity(proc, root, pid) == expected, 'Original process identity changed after capture')
        proof['boundary_after'] = _boundary(budget, assert_frozen)
        require(time.monotonic() <= budget['deadline'], 'Capture deadline')
        proof['complete'] = True
    except BaseException as error:
        primary = error
    finally:
        close_errors = list(budget['nested_fd_close_errors'])
        for fd in reversed(descriptors):
            try:
                os.close(fd)
            except OSError as error:
                close_errors.append(type(error).__name__ + ': ' + str(error))
        proof.update({k: budget[k] for k in ('files', 'entries', 'created_directories',
                                           'bytes_read', 'bytes_written', 'roster')})
        proof['host_process_cpu_s'] = time.process_time() - before_cpu
        proof['fd_closure_complete'] = not close_errors
        proof['fd_close_errors'] = close_errors
        if close_errors:
            proof['complete'] = False
            if primary is None:
                primary = CaptureError('Capture descriptor closure failed')
    if primary is not None:
        proof['complete'] = False
        error = CaptureError(type(primary).__name__ + ': ' + str(primary))
        error.capture_observation = proof
        raise error from primary
    return proof
