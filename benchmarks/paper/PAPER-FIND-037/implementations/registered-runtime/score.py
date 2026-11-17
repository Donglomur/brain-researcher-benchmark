#!/usr/bin/env python3
"""Shared-CLI argv bridge to the held supplied-artifact scorer.

This file adds no evaluator or lifecycle. The held scorer validates the actual
submission, source closure, grant, cumulative cost, capacity and cleanup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

SCORER = 'authoring/freeenergy-eeg-v1/submission-scoring-v2/score.py'
SCORER_PIN = (1254, '2bedc09a2d0704bc264b7cd708edae968acf3888ae05143be6b5baab231ec0c1')
FREEZE = 'authoring/freeenergy-eeg-v1/submission-scoring-v2/FREEZE.json'
FREEZE_PIN = (70770, '3976253d6b74b7bb996091573f350ca95c66c354667ca53642df6ce4428b6956')
INSTALLED = 'benchmarks/neuroscience/paper-find-037/score.py'


def need(value, message):
    if not value:
        raise ValueError(message)


def bounded_file(root, value, cap):
    path = Path(value).absolute()
    need(path.is_relative_to(root) and '..' not in path.parts
         and all(not p.is_symlink() for p in (path, *path.parents)),
         'Canonical repository file without linked ancestors')
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and 0 < before.st_size <= cap, 'Bounded ordinary single-link file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    identity = lambda row: tuple(getattr(row, key) for key in fields)
    need(identity(before) == identity(opened) == identity(after) == identity(path.stat())
         and len(body) == before.st_size and len(body) <= cap, 'Stable complete bounded file')
    return path, body


def review_metadata(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate review field')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Invalid review numeric token: ' + value)
    value = json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)
    need(type(value) is dict, 'Review object required')
    return value


def command(root, submission, output, review, other_reserve_bytes):
    """Construct argv only; do not read submitted artifact bytes or execute code."""
    root = Path(root).resolve()
    review_path, raw = bounded_file(root, review, 32768)
    metadata = review_metadata(raw)
    declared = metadata.get('other_unmaterialized_reserves_bytes')
    need(type(other_reserve_bytes) is int and type(declared) is int
         and other_reserve_bytes == declared and declared >= 102000000,
         'CLI reserve must exactly match the independently reviewed current reserve')
    for relative, expected in ((SCORER, SCORER_PIN), (FREEZE, FREEZE_PIN)):
        _, body = bounded_file(root, root / relative, 131072)
        need((len(body), hashlib.sha256(body).hexdigest()) == expected,
             'Held scoring facade and source freeze remain unchanged')
    return [sys.executable, '-B', str(root / SCORER), 'score',
            '--submission', str(Path(submission).absolute()),
            '--output', str(Path(output).absolute()), '--review', str(review_path)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--submission', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--review', required=True, type=Path)
    parser.add_argument('--other-reserve-bytes', required=True, type=int)
    args = parser.parse_args()
    # The shared CLI already fixes cwd to the repository root. Staged proposal
    # copies cannot accidentally dispatch as if they had been installed.
    root = Path.cwd().resolve()
    need(Path(__file__).absolute() == root / INSTALLED, 'Use the installed package-local facade')
    argv = command(root, args.submission, args.output, args.review, args.other_reserve_bytes)
    os.execv(sys.executable, argv)
    raise AssertionError('Process replacement returned')


if __name__ == '__main__':
    raise SystemExit(main())
