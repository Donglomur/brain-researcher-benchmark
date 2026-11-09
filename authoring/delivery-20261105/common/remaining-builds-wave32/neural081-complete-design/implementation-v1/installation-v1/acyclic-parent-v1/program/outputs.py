"""Worker-owned full output hashes and exact finite completion accounting."""
import hashlib
import os
from pathlib import Path
import stat
import time
import common as c


def relative(value):
    c.need(type(value) is str and value and not value.startswith('/') and '\\' not in value and
           all(x not in ('', '.', '..') for x in value.split('/')), 'ordinary output relative path')
    return value


def digest_file(path, budget):
    p = c.absolute(str(path))
    c.need(not any(x.is_symlink() for x in (p, *p.parents)), 'no linked output')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        c.need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'ordinary single-link output')
        budget.charge('read_bytes', before.st_size + 1)
        h, total = hashlib.sha256(), 0
        while total <= before.st_size:
            budget.check_clock()
            data = os.read(fd, min(2**20, before.st_size + 1 - total))
            if not data:
                break
            total += len(data); h.update(data)
        after, named = os.fstat(fd), p.lstat()
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        c.need(total == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in fields), 'stable complete output hashing')
        os.fsync(fd)
    finally:
        os.close(fd)
    return {'bytes': total, 'sha256': h.hexdigest()}


def finish(root, result, budget, request, source, job):
    root = c.absolute(str(root))
    c.need(result['path'] == str(root / 'RESULT.json'), 'canonical operation result')
    artifacts, directories = [], []
    for current, dirs, files in os.walk(root, followlinks=False):
        directory = Path(current); directories.append(directory)
        c.need(not directory.is_symlink() and all(not (directory / d).is_symlink() for d in dirs), 'ordinary output directories')
        for filename in sorted(files):
            path = directory / filename; name = relative(path.relative_to(root).as_posix())
            c.need(name not in ('COMPLETE.json', 'runtime-artifacts.json'), 'fresh completion outputs only')
            artifacts.append({'relative_path': name, **digest_file(path, budget)})
    c.need(any(x['relative_path'] == 'RESULT.json' and x['bytes'] == result['bytes'] and x['sha256'] == result['sha256'] for x in artifacts), 'computed operation result identity')
    complete = {'schema': 'neural081_worker_complete_v1', 'job': job, 'request': request, 'numeric_source': source,
                'original_origin': budget.origin, 'original_deadline': budget.end,
                'observed_before_publication': time.monotonic(), 'managed_requested_io': dict(budget.used),
                'reservation': dict(budget.limits), 'eof_probe_demand_included': True,
                'physical_library_IO_or_RSS_measured': False}
    # The own completion/hash/final-manifest byte counts converge without a hash cycle.
    for _ in range(16):
        body = c.encoded(complete)
        final_rows = sorted(artifacts + [{'relative_path': 'COMPLETE.json', **c.pin(body)}], key=lambda x: x['relative_path'])
        manifest = c.encoded({'schema': 'neural081_runtime_artifacts_v1', 'artifacts': final_rows, 'operation_result': 'RESULT.json'})
        wanted = {'read_bytes': budget.used['read_bytes'] + len(body) + 1,
                  'write_bytes': budget.used['write_bytes'] + len(body) + len(manifest)}
        if complete['managed_requested_io'] == wanted:
            break
        complete['managed_requested_io'] = wanted
    else:
        c.need(False, 'completion accounting fixed point')
    c.need(all(wanted[k] <= budget.limits[k] for k in wanted), 'completion and manifest fully reserved before writing')
    cp = c.publish(root / 'COMPLETE.json', body, budget)
    c.need(digest_file(root / 'COMPLETE.json', budget) == {k: cp[k] for k in ('bytes', 'sha256')}, 'completion own genuine hash read')
    for directory in reversed(directories):
        c.sync_directory(directory)
    md = c.publish(root / 'runtime-artifacts.json', manifest, budget)
    c.need(budget.used == wanted, 'exact completed managed IO counters')
    budget.check_clock()
    return md
