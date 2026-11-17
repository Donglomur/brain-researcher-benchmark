#!/usr/bin/env python3
"""Prepare the exact historical public-source namespace; never execute a study.

The original constructor and all release identities remain unchanged. This
additive adapter resolves reviewed current locations into a fresh source tree.
It reuses the exact released constructor's bounded file and publication helpers.
"""
import argparse
import hashlib
import math
import os
from pathlib import Path
import stat
import sys
import time
import types


CONSTRUCTOR_PIN = (153697, 'ef339b63f9a817a6ed8feb620451c8cf3b73389345a3d80bcdb376609416c1d9')
RELEASE_PIN = (54631, 'd6d3406ba2e0fce136fbe7d71bf76fd311915324eb031493a2d963184f2ae2ca')
MAP_PIN = (46779, '7bef659582ad926385e79c972dc6a0d8ab67286585873646ec81ad0dea0bb8e3')
REPORT_RESERVATION = 65536


def _require(value, message):
    if not value:
        raise ValueError(message)


def _bootstrap_capture(path, expected):
    """Bound and authenticate helper bytes before compiling them, never pyc."""
    for entry in [*reversed(path.parents), path]:
        info = entry.lstat()
        _require(not stat.S_ISLNK(info.st_mode), 'no symlink source component')
        if entry != path:
            _require(stat.S_ISDIR(info.st_mode), 'ordinary source parent')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                 and before.st_size == expected[0], 'exact ordinary constructor source')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(expected[0] + 1)
        after, named = os.fstat(fd), path.lstat()
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        _require(all(getattr(before, key) == getattr(after, key) == getattr(named, key)
                     for key in fields), 'stable constructor source')
        _require(len(raw) == expected[0] and hashlib.sha256(raw).hexdigest() == expected[1],
                 'pinned constructor source')
        return raw
    finally:
        os.close(fd)


def _load_helpers(read_cap, write_cap, live_cap, deadline):
    for value in (read_cap, write_cap, live_cap):
        _require(type(value) is int and value > 0, 'positive integer source preparation cap')
    _require(type(deadline) in (int, float) and math.isfinite(deadline)
             and time.monotonic() < deadline, 'future monotonic source preparation deadline')
    entry = Path(__file__).absolute()
    for parent in [*reversed(entry.parents), entry]:
        info = parent.lstat()
        _require(not stat.S_ISLNK(info.st_mode), 'ordinary preparer source path')
        _require(stat.S_ISDIR(info.st_mode) if parent != entry else
                 stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                 'ordinary preparer source entry')
    entry_bytes = entry.lstat().st_size
    _require(read_cap >= entry_bytes + CONSTRUCTOR_PIN[0] + 1 and live_cap >= CONSTRUCTOR_PIN[0] + 1,
             'constructor bootstrap within explicit caps')
    package = entry.parent.parent
    path = package / 'release/neural081_instance.py'
    raw = _bootstrap_capture(path, CONSTRUCTOR_PIN)
    _require(time.monotonic() < deadline, 'source preparation deadline during bootstrap')
    module = types.ModuleType('_neural081_pinned_source_helpers')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec', dont_inherit=True), module.__dict__)
    budget = module.Budget(read_cap, write_cap, live_cap, deadline)
    # The authenticated bootstrap read is included in this operation's budget.
    # Compiled Python objects and OS RSS are not physical-memory claims.
    budget.charge('read_bytes', entry_bytes + len(raw) + 1)
    held = budget.hold(len(raw) + 1)
    del raw
    budget.release(held)
    return module, budget, package


def _descriptor(path, expected):
    return {'path': str(path), 'bytes': expected[0], 'sha256': expected[1]}


def prepare(public_root, destination, *, read_cap, write_cap, live_cap, deadline):
    """Publish all 105 exact prerequisites to a fresh external source tree.

    No profile, neural input, protected target, qualification or campaign is read.
    A failed copy may leave an incomplete owned prefix; it is never a release.
    """
    core, budget, package = _load_helpers(read_cap, write_cap, live_cap, deadline)
    root, target = core.canonical(public_root), core.canonical(destination)
    core.disjoint([root, target])
    core.ordinary_ancestors(root)
    core.need(root.is_dir(), 'ordinary public checkout')
    core.ordinary_ancestors(target.parent)
    core.need(not target.exists(), 'fresh prerequisite destination')
    core.need(not package.is_relative_to(target), 'source helper outside destination')

    mapping = core.capture_json(_descriptor(package / 'source-resolution/SOURCE_MAP.json', MAP_PIN), budget)
    core.exact(mapping, ('schema', 'task_id', 'source_checkout_base', 'rows',
                         'historical_helpers', 'scientific_execution', 'runtime_authorization'))
    core.need(mapping['schema'] == 'neural081_current_source_resolution_v1'
              and mapping['task_id'] == core.TASK and mapping['scientific_execution'] is False
              and mapping['runtime_authorization'] is False, 'source-only resolution map')
    release = core.validate_release(core.capture_json(
        _descriptor(package / 'release/PORTABLE_RELEASE.json', RELEASE_PIN), budget))
    rows = mapping['rows']
    core.need(type(rows) is list and len(rows) == 105, 'complete 105-member resolution map')
    mapped = []
    for row in rows:
        core.exact(row, ('path', 'source', 'bytes', 'sha256'))
        logical = {key: row[key] for key in ('path', 'bytes', 'sha256')}
        core.descriptor(logical, absolute=False)
        core.relative(row['source'])
        mapped.append(logical)
    core.need(core.same(mapped, release['public_files']), 'exact original 105 identities and order')
    core.need(len({row['source'] for row in rows}) == 105, 'distinct current source members')

    def source(row):
        return {'path': str(root / row['source']), 'bytes': row['bytes'], 'sha256': row['sha256']}

    # Verify every source before creating a destination. Recapture while copying
    # so a later source change cannot be published under an earlier identity.
    for row in rows:
        core.capture_bytes(source(row), budget)
    core.need(budget.used['write_bytes'] + sum(row['bytes'] for row in rows) <= write_cap,
              'complete prerequisite bodies within write cap')
    owned = core.CreatedRoot()
    outputs = []
    try:
        owned.create(target)
        core.sync_directory(target, budget)
        core.sync_directory(target.parent, budget)
        for row in rows:
            owned.check()
            raw = core.capture_bytes(source(row), budget)
            outputs.append(core.publish_bytes(target, target / row['path'], raw, budget))
            del raw
            owned.check()
        receipt = {
            'schema': 'neural081_prepared_source_tree_v1', 'task_id': core.TASK,
            'public_root': str(root), 'destination': str(target),
            'source_map': {'bytes': MAP_PIN[0], 'sha256': MAP_PIN[1]},
            'original_release': {'bytes': RELEASE_PIN[0], 'sha256': RELEASE_PIN[1]},
            'original_constructor': {'bytes': CONSTRUCTOR_PIN[0], 'sha256': CONSTRUCTOR_PIN[1]},
            'files': outputs, 'prerequisites': 105,
            'runtime_authorization': False, 'qualification_created': False,
            'scientific_execution': False,
        }
        descriptor = core.publish_json(target, target / 'SOURCE_RESOLUTION.json', receipt, budget)
        owned.check()
        budget.charge('write_bytes', REPORT_RESERVATION)
        budget.check()
        return {'status': 'prepared_not_qualified', 'prerequisites': 105,
                'receipt': descriptor, 'runtime_authorization': False,
                'qualification_created': False, 'scientific_execution': False,
                'terminal_report_reservation_bytes': REPORT_RESERVATION,
                'budget': budget.snapshot()}
    finally:
        original_error = sys.exc_info()[0] is not None
        try:
            owned.close()
        except BaseException:
            if not original_error:
                raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-root', required=True)
    parser.add_argument('--destination', required=True)
    for name in ('read-cap', 'write-cap', 'live-cap'):
        parser.add_argument('--' + name, type=int, required=True)
    parser.add_argument('--deadline', type=float, required=True)
    args = parser.parse_args(argv)
    result = prepare(args.public_root, args.destination, read_cap=args.read_cap,
                     write_cap=args.write_cap, live_cap=args.live_cap, deadline=args.deadline)
    # Its fixed conservative reservation is included in the logical write budget.
    import json
    raw = (json.dumps(result, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
    _require(len(raw) <= REPORT_RESERVATION, 'bounded terminal preparation report')
    _require(time.monotonic() < args.deadline, 'source preparation deadline before terminal report')
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()
    _require(time.monotonic() < args.deadline, 'source preparation deadline after terminal report')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
