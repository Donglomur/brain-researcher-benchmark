"""Small source/metadata helpers; never interpret empirical numerical arrays."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ID = 'PAPER-ROOT-ADD-016'


def need(ok, text):
    if not ok:
        raise ValueError(text)


def path(relative):
    p = Path(relative)
    need(type(relative) is str and relative and not p.is_absolute() and '..' not in p.parts
         and p.as_posix() == relative and not any(c in relative for c in ',\r\n'), 'Canonical project path')
    return ROOT / p


def stream(source, cap):
    p = Path(source).absolute()
    need('..' not in p.parts and all(not x.is_symlink() for x in (p, *p.parents)), 'Unlinked path')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    a = os.fstat(fd)
    if not (stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap):
        os.close(fd)
        raise ValueError('Bounded ordinary single-link file')
    return os.fdopen(fd, 'rb'), a


def stable(a, b):
    need(all(getattr(a, k) == getattr(b, k) for k in
             ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mode', 'st_mtime_ns', 'st_ctime_ns')), 'Stable full input')


def read(source, cap=250000):
    f, a = stream(source, cap)
    with f:
        raw = f.read(cap + 1)
        stable(a, os.fstat(f.fileno()))
    need(len(raw) == a.st_size, 'Complete bytes')
    return raw


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def opaque(source, cap):
    f, a = stream(source, cap)
    h = hashlib.sha256()
    with f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
        stable(a, os.fstat(f.fileno()))
    return {'bytes': a.st_size, 'sha256': h.hexdigest()}


def descriptor(value, cap=250000, decode=True):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'Exact file descriptor')
    raw = read(path(value['path']), cap)
    need(pin(raw) == {k: value[k] for k in ('bytes', 'sha256')}, 'Pinned identity')
    return json.loads(raw) if decode else raw


def json_read(source, cap=250000):
    return json.loads(read(source, cap))


def write(source, value, cap=250000):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    need(len(raw) <= cap, 'Bounded complete metadata')
    fd = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return pin(raw)


def freeze(review, filename='FREEZE.json'):
    need(filename in ('FREEZE.json', 'PREP_FREEZE.json'), 'Declared source closure role')
    raw = read(HERE / filename, 500000)
    need(pin(raw)['sha256'] == review['freeze_sha256'], 'Root-bound final source freeze')
    value = json.loads(raw)
    need(value['candidate_id'] == ID and 1 <= len(value['files']) <= 256, 'Bounded exact source closure')
    for relative, item in value['files'].items():
        need(pin(read(path(relative), 2000000)) == item, 'Source closure drift: ' + relative)
    return value


def accounting(review, seconds):
    old = descriptor(review['latest_accounting_evidence'], 500000)
    field = review['prior_seconds_field']
    need(type(field) is str and '.' not in field and field in old, 'Explicit actual prior field')
    prior = review['prior_known_seconds']
    need(type(prior) in (int, float) and math.isfinite(prior) and prior >= 2525 and old[field] == prior
         and review['known_after_seconds'] == prior + seconds, 'Full family history, no reset')
    need(old.get('candidate_id') == ID and review['prior_required_status'] == old['status'], 'Same closed task family')
    need(review['prior_required_cleanup'] and all(old.get(k) is True for k in review['prior_required_cleanup']),
         'Explicit previous cleanup evidence')
    return prior
