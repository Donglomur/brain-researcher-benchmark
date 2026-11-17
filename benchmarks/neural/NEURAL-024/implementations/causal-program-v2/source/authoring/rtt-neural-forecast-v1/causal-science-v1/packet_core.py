"""Bounded canonical metadata and write-once packet publication helpers."""
from pathlib import Path
import hashlib
import json
import math
import os
import re
import stat

PROTOCOL = 'NEURAL024-causal-v1'
CHANNELS = 96
ROUNDS = 22100
WARMUP = 10
SCORED = 22090
FIRST = 3000
OBSERVATION_LINE_CAP = 2048
COMMIT_LINE_CAP = 4608
PREP_CAPS = {'source_counts.npz': 7400000, 'calibration_counts.npz': 1200000,
             'observations.jsonl': 45260800, 'schedule.json': 2000000,
             'references.json': 256000, 'prepare_receipt.json': 128000}
GRADE_CAPS = {'score.json': 131072, 'grade_receipt.json': 65536}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def no_duplicate_keys(pairs):
    answer = {}
    for key, value in pairs:
        need(key not in answer, 'Duplicate JSON member')
        answer[key] = value
    return answer


def parse(body, canonical_required=False):
    need(type(body) is bytes and len(body) > 0, 'Nonempty JSON bytes')
    value = json.loads(body, object_pairs_hook=no_duplicate_keys,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON token')))
    if canonical_required:
        need(canonical(value) == body, 'Exact canonical JSON bytes including newline')
    return value


def digest(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def valid_pin(value, allow_empty=False):
    return (type(value) is dict and set(value) == {'bytes', 'sha256'} and
            type(value['bytes']) is int and (value['bytes'] > 0 or
                (allow_empty and value['bytes'] == 0 and
                 value['sha256'] == hashlib.sha256(b'').hexdigest())) and
            type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None)


def read_bound(path, cap, expected=None):
    path = Path(path)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and not path.is_symlink() and 0 < info.st_size <= cap,
         'Bounded ordinary input file')
    with path.open('rb') as stream:
        body = stream.read(cap + 1)
    need(len(body) == info.st_size and len(body) <= cap, 'Complete bounded input read')
    if expected is not None:
        need(valid_pin(expected) and digest(body) == expected, 'Exact input bytes and hash')
    return body


def ordinary_size(path, cap, expected):
    path = Path(path)
    info = path.lstat()
    need(valid_pin(expected) and stat.S_ISREG(info.st_mode) and not path.is_symlink()
         and info.st_size == expected['bytes'] and 0 < info.st_size <= cap,
         'Exact bounded ordinary stream size')
    return info.st_size


def observation(value, target):
    need(type(value) is dict and set(value) == {'target_bin', 'counts'} and
         type(value['target_bin']) is int and value['target_bin'] == target,
         'Exact observation identity')
    counts = value['counts']
    need(type(counts) is list and len(counts) == CHANNELS and
         all(type(x) is int and 0 <= x <= 4294967295 for x in counts),
         'All 96 exact unsigned channel counts')
    return counts


def interval(value):
    need(type(value) is list and len(value) == 2 and
         all(type(x) in (int, float) and math.isfinite(x) for x in value) and
         0 <= value[0] < value[1], 'Finite session-relative native interval')
    return value


class Writer:
    def __init__(self, root, caps):
        self.root, self.caps, self.pins = Path(root), dict(caps), {}
        need(self.root.is_dir() and not any(self.root.iterdir()), 'Fresh owned output directory')
        self.attempted = 0
        self.completed = 0

    def sync(self):
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def stream(self, name, pieces):
        need(name in self.caps and name not in self.pins, 'Fixed write-once evidence name')
        final, pending = self.root / name, self.root / (name + '.next')
        need(not final.exists() and not final.is_symlink(), 'Final path absent before pending creation')
        self.attempted += 1
        total, sha = 0, hashlib.sha256()
        with pending.open('xb') as target:
            self.sync()
            for body in pieces:
                need(type(body) is bytes and len(body) > 0, 'Nonempty exact output chunk')
                need(total + len(body) <= self.caps[name], 'Declared output file-byte cap')
                written = target.write(body)
                need(written == len(body), 'Complete output chunk write')
                total += written
                sha.update(body)
            need(total > 0, 'Nonempty sealed output')
            target.flush()
            os.fsync(target.fileno())
        pending.rename(final)
        self.sync()
        self.pins[name] = {'bytes': total, 'sha256': sha.hexdigest()}
        self.completed += 1
        return self.pins[name]

    def write(self, name, body):
        return self.stream(name, (body,))

    def json(self, name, value):
        return self.write(name, canonical(value))
