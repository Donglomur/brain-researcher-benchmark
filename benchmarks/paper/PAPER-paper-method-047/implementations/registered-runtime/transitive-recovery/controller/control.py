"""Source-only full117 controller primitives; no execution on import."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time
import types

TASK = 'PAPER-paper-method-047'
PRED_CAP = 67108864
VIEWS = 468
RETAIN = 33000000000
WRITE_RESERVE = 100000000000
READ_RESERVE = 700000000000
GRADING_READ = 500000000
FLOOR = 21474836480


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def path(value):
    p = Path(value).absolute()
    need('..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)) and
         not any(c in str(p) for c in ',\n\r\0'), 'canonical unlinked path')
    return p


def stamp(s):
    return tuple(getattr(s, k) for k in ('st_dev', 'st_ino', 'st_mode', 'st_nlink',
                                       'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def read(p, cap, expected=None):
    p = path(p)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap, 'bounded source')
        body = bytearray()
        while len(body) <= a.st_size:
            chunk = os.read(fd, min(65536, a.st_size + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        need(len(body) == a.st_size and stamp(a) == stamp(os.fstat(fd)) == stamp(p.lstat()),
             'stable complete source')
    finally:
        os.close(fd)
    raw = bytes(body)
    need(expected is None or pin(raw) == expected, 'source identity')
    return raw


def only_pin(row):
    return {k: row[k] for k in ('bytes', 'sha256')}


def source(repo, row, name):
    rel = Path(row['path'])
    need(not rel.is_absolute() and '..' not in rel.parts, 'relative dependency')
    p = path(repo) / rel
    raw = read(p, 1000000, only_pin(row))
    m = types.ModuleType(name)
    m.__file__ = str(p)
    exec(compile(raw, str(p), 'exec'), m.__dict__)
    return m


def sync(p):
    fd = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write(p, raw, cap=1000000):
    need(0 < len(raw) <= cap, 'bounded fresh publication')
    p = path(p)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    try:
        view = memoryview(raw)
        while view:
            n = os.write(fd, view)
            need(n > 0, 'complete write')
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    sync(p.parent)
    return pin(raw)


def inventory(root, cap=RETAIN, entries=200000):
    todo = [path(root)]
    files, dirs, total, count = {}, [], 0, 0
    while todo:
        p = todo.pop()
        s = p.lstat()
        count += 1
        need(count <= entries, 'bounded owned enumeration')
        need(stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode) and s.st_nlink == 1,
             'owned ordinary tree')
        total += max(s.st_size, s.st_blocks * 512)
        need(total <= cap, 'owned allocated-byte cap')
        if stat.S_ISDIR(s.st_mode):
            dirs.append(p)
            with os.scandir(p) as it:
                for x in it:
                    need(count + len(todo) < entries, 'bounded owned pending enumeration')
                    todo.append(p / x.name)
        else:
            files[p.relative_to(root).as_posix()] = (p, stamp(s))
    return files, dirs, total


def capacity(root, other, extra=0):
    used = inventory(root)[2] if root.exists() else 0
    need(type(other) is int and other >= 0 and used + extra <= RETAIN, 'complete owned reserve')
    need(shutil.disk_usage(root if root.exists() else root.parent).free >=
         FLOOR + other + RETAIN - used, 'free floor plus all outstanding reservations')


def whole_seconds(cfg):
    # One original campaign clock; neither phase failures nor cleanup reset it.
    return 1200 + VIEWS * (cfg['stage_seconds'] + cfg['train_seconds'] +
                           cfg['predict_seconds'] + 2600 + cfg['grade_seconds'] + 60) + 240


def validate_selection(s):
    required = {'schema', 'enabled', 'task_id', 'source', 'programs', 'authoring_receipt',
                'runtime_receipt', 'image', 'memory_bytes', 'train_seconds', 'predict_seconds',
                'stage_seconds', 'grade_seconds', 'other_reserved_bytes', 'private_grading_authorized',
                'exclusive_immutable_operator_storage', 'python', 'docker', 'socket'}
    need(type(s) is dict and set(s) == required and s['schema'] == 'gcamp8_full117_selection_v1' and
         s['enabled'] is True and s['task_id'] == TASK, 'explicit selected complete condition')
    need(s['private_grading_authorized'] is True and s['exclusive_immutable_operator_storage'] is True,
         'explicit evaluator and storage authority')
    need(set(s['programs']) == {'A', 'B'} and re.fullmatch('sha256:[0-9a-f]{64}', s['image']),
         'two programs and existing digest image')
    for k, high in [('train_seconds', 86400), ('predict_seconds', 3600),
                    ('stage_seconds', 3600), ('grade_seconds', 3600)]:
        need(type(s[k]) is int and 1 <= s[k] <= high, 'fixed bounded phase seconds')
    need(type(s['memory_bytes']) is int and 1073741824 <= s['memory_bytes'] <= 17179869184 and
         s['memory_bytes'] % 1048576 == 0, 'selected candidate RAM 1..16GiB')
    need(type(s['other_reserved_bytes']) is int and s['other_reserved_bytes'] >= 0, 'current OTHER')
    return s


def training_packet(packet):
    # No rows/frames/segments/signals/hashes/eligibility derived from the query.
    return {'schema': 'gcamp8_training_packet_v1', 'task_id': TASK,
            **{k: packet[k] for k in ('neuron_id', 'indicator', 'track', 'access_view', 'training_ids')}}


def phase_inputs(plan, view, training_packet_path, candidate_abi_path):
    train, query = {}, {}
    for row in plan['files']:
        n = row['target']
        if n in ('ROSTER.json', 'PACKET.json'):
            continue
        mount = ('bind', view / n, False)
        if n.startswith('training/'):
            train['/input/' + n] = mount
        elif n.startswith('query/'):
            query['/input/' + n] = mount
        else:
            train['/input/' + n] = mount
            query['/input/' + n] = mount
    train['/input/TRAIN_PACKET.json'] = ('bind', training_packet_path, False)
    query['/input/PACKET.json'] = ('bind', view / 'PACKET.json', False)
    for mounts in (train, query):
        mounts['/input/CANDIDATE_ABI.md'] = ('bind', candidate_abi_path, False)
    return train, query


def barrier(expected, records):
    need(len(expected) == VIEWS and len({tuple(x) for x in expected}) == VIEWS, 'exact full468 roster')
    need(len(records) == VIEWS and [x['identity'] for x in records] == expected, 'complete ordered outcomes')
    need(all(x['status'] == 'captured' and x['all_resources_closed'] is True and
             x['cli_groups_closed'] is True and x['input_retired'] is True and
             x['private_grade_started'] is False for x in records), 'full producer closure barrier')
    return {'schema': 'gcamp8_full468_barrier_v1', 'count': VIEWS,
            'identities': expected, 'all_producers_closed_before_any_grade': True}


def retire_view(root, expected, proof, deadline):
    files, dirs, used = inventory(root, 200000000, 1024)
    need(set(files) == set(expected), 'exact owned view before retirement')
    for name, (p, _) in files.items():
        need(time.monotonic() < deadline, 'retirement original deadline')
        read(p, expected[name]['bytes'], expected[name])
    intent = write(proof / 'RETIRE_INTENT.json', encoded({'root': str(root),
                   'files': expected, 'allocated_bytes': used}))
    for p, identity in files.values():
        need(time.monotonic() < deadline and stamp(p.lstat()) == identity, 'unchanged owned member')
        p.parent.chmod(0o700)
        p.unlink()
        sync(p.parent)
    for d in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        d.chmod(0o700)
        d.rmdir()
        sync(d.parent)
    need(not os.path.lexists(root) and time.monotonic() < deadline, 'observed retired absence')
    return write(proof / 'RETIRE_ACK.json', encoded({'intent': intent, 'absence_observed': True}))
