"""Exact owned host file staging and durable retirement; never follows symlinks."""
import failures
import hashlib, os, stat
from pathlib import Path
from .io import encoded, pin, need, failure
from .vendor.bounds import relative, fsync_dir
from .vendor.engine import finish_cleanup

def identity(path):
    s = path.lstat()
    need(not stat.S_ISLNK(s.st_mode), 'Ordinary owned inode')
    return {'device': s.st_dev, 'inode': s.st_ino, 'kind': 'directory' if stat.S_ISDIR(s.st_mode) else 'file' if stat.S_ISREG(s.st_mode) else 'other'}

def stage_files(root, files, budget):
    """Operator-only returned evidence; candidate mount is root/files only.

    On failure the exception carries the live observed ownership map. No partial
    tree is silently forgotten or assigned zero cost. Caller stops dispatch.
    """
    root = Path(root)
    need(root.is_absolute() and (not os.path.lexists(root)) and (not any((p.is_symlink() for p in root.parents))), 'Fresh exact owned host stage')
    need(type(files) is dict and 0 < len(files) <= 100000, 'Explicit finite complete stage membership')
    for name, d in files.items():
        relative(name)
        need(type(d) is dict and set(d) == {'path', 'bytes', 'sha256'} and (type(d['bytes']) is int) and (d['bytes'] >= 0), 'Exact input file descriptor')
    evidence = {'schema': 'neural066_owned_stage_v1', 'root': str(root), 'status': 'partial', 'entries': {}, 'payload_write_reserved_bytes': 0, 'actual_payload_written_bytes': 0, 'files': {}, 'credit_released': False}

    def directory(path):
        path.mkdir(mode=448)
        evidence['entries'][str(path.relative_to(root))] = identity(path)
        fsync_dir(path.parent)
    budget.event({'event': 'STAGE-INTENT', 'root': str(root), 'files': files})
    budget.tick()
    try:
        directory(root)
        directory(root / 'files')
        for name, d in sorted(files.items()):
            target = root / 'files' / name
            for parent in reversed(target.parents):
                if parent == root or not parent.is_relative_to(root):
                    continue
                if str(parent.relative_to(root)) not in evidence['entries']:
                    directory(parent)
            source = Path(d['path'])
            need(source.is_absolute() and (not any((p.is_symlink() for p in (source, *source.parents)))), 'Exact ordinary source')
            budget.read(d['bytes'] + 1)
            budget.write(d['bytes'])
            evidence['payload_write_reserved_bytes'] += d['bytes']
            src = dst = None
            primary = None
            digest = hashlib.sha256()
            total = 0
            try:
                src = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                before = os.fstat(src)
                need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and (before.st_size == d['bytes']), 'Exact complete staged input extent')
                dst = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 256)
                evidence['entries'][str(target.relative_to(root))] = identity(target)
                while True:
                    budget.tick()
                    raw = os.read(src, min(65536, d['bytes'] + 1 - total))
                    if not raw:
                        break
                    total += len(raw)
                    need(total <= d['bytes'], 'No source growth')
                    digest.update(raw)
                    at = 0
                    while at < len(raw):
                        budget.tick()
                        n = os.write(dst, memoryview(raw)[at:])
                        need(type(n) is int and 0 < n <= len(raw) - at, 'Checked full stage write')
                        at += n
                        evidence['actual_payload_written_bytes'] += n
                fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
                sig = lambda s: tuple((getattr(s, k) for k in fields))
                need(sig(before) == sig(os.fstat(src)) == sig(source.lstat()) and total == d['bytes'] and (digest.hexdigest() == d['sha256']), 'Complete exact stable source bytes')
                os.fchmod(dst, 292)
                os.fsync(dst)
            except BaseException as exc:
                failures.hold(exc, 'caught')
                primary = exc
                raise
            finally:
                actions = []
                if src is not None:
                    actions.append(('stage.source.close', lambda: os.close(src)))
                if dst is not None:
                    actions.append(('stage.output.close', lambda: os.close(dst)))
                finish_cleanup(actions, primary)
            fsync_dir(target.parent)
            evidence['files'][name] = {k: d[k] for k in ('bytes', 'sha256')}
            budget.event({'event': 'STAGE-FILE', 'root': str(root), 'name': name, 'file': evidence['files'][name]})
        for name, d in sorted(evidence['entries'].items(), key=lambda x: len(Path(x[0]).parts), reverse=True):
            if d['kind'] == 'directory' and name != '.':
                os.chmod(root / name, 365)
                fsync_dir(root / name)
        fsync_dir(root)
        fsync_dir(root.parent)
        budget.tick()
        evidence['status'] = 'complete'
        budget.event({'event': 'STAGE-COMPLETE', 'evidence': evidence})
        budget.tick()
        return evidence
    except BaseException as exc:
        failures.hold(exc, 'caught')
        evidence['error'] = failure(exc)
        failures.remember(exc, 'stage_evidence', evidence)
        try:
            budget.event({'event': 'STAGE-FAILED', 'evidence': evidence})
        except BaseException as secondary:
            failures.hold(secondary, 'caught')
            failures.note(exc, 'Stage failure ledger unavailable: ' + failures.kind(secondary))
        raise

def retire_stage(evidence, budget):
    """No credit until all exact owned entries are absent and parent is durable."""
    root = Path(evidence['root'])
    need(evidence['schema'] == 'neural066_owned_stage_v1' and (not evidence['credit_released']), 'Unique unretired source-owned stage')
    entries = evidence['entries']
    need('.' in entries and all((d['kind'] in ('file', 'directory') for d in entries.values())), 'Complete observed owned inode map')
    found = {'.': identity(root)}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            q = Path(parent) / name
            rel = str(q.relative_to(root))
            need(rel in entries and len(found) < len(entries), 'No extra/unowned stage member')
            found[rel] = identity(q)
    need(found == entries, 'Every current inode equals owned stage before deletion')
    budget.event({'event': 'STAGE-RETIRE-INTENT', 'root': str(root), 'entries': entries})
    budget.tick()
    for name, d in sorted(entries.items(), key=lambda x: len(Path(x[0]).parts)):
        if d['kind'] == 'directory':
            need(identity(root / name) == d, 'Same directory before chmod')
            os.chmod(root / name, 448)
    for name, d in sorted(entries.items(), key=lambda x: len(Path(x[0]).parts), reverse=True):
        budget.tick()
        q = root / name
        need(identity(q) == d, 'Same owned inode immediately before removal')
        q.rmdir() if d['kind'] == 'directory' else q.unlink()
    fsync_dir(root.parent)
    need(not os.path.lexists(root), 'Complete independent owned root absence')
    budget.tick()
    result = {'schema': 'neural066_owned_stage_retired_v1', 'root': str(root), 'all_owned_entries_removed': True, 'parent_synced': True, 'payload_retained_credit_eligible_bytes': evidence['actual_payload_written_bytes'], 'unused_write_reservation_bytes': evidence['payload_write_reserved_bytes'] - evidence['actual_payload_written_bytes'], 'physical_io_measured': False}
    budget.event({'event': 'STAGE-RETIRED', 'result': result})
    budget.tick()
    evidence['credit_released'] = True
    return result
