#!/usr/bin/env python3
"""Operator-only entry point for the existing complete40 author-API component.

No original data, numeric libraries or source components are imported here.
This supplies neither process containment nor a full-paper success decision.
"""
from __future__ import annotations
import argparse
import hashlib
import math
import os
from pathlib import Path
import stat
import sys
import time
import types

DEPENDENCIES = {'common.py': {'bytes': 9056, 'sha256': 'e208aeee70fb575bbe1aa53e3275b03916ea2bf69b5f73719a1bc6ce859057e3'}, 'prepare.py': {'bytes': 23973, 'sha256': '3d63aef632a923fa951ef3f937342afd3dd7bc657fbf6f74ac8121c4fe2f9213'}, 'support.py': {'bytes': 5219, 'sha256': '71bf28c5bd3a74e2b3ab003931779d66f6c2c4f807a7f3f682c93f74f689cc84'}, 'array_io.py': {'bytes': 1553, 'sha256': 'c8fb187355eb6e2c1f5555ea6c6c3af5762d68fb4c2ebe630b0a406bd05000bd'}, 'author_replay.py': {'bytes': 11855, 'sha256': '82a2ead200b4998ea1d15d022211f66e70c60352c2905f62b5b7f36e00d92959'}}
MAX_AUTHORITY = 1 << 20
MAX_PREPARED = 16 << 20
MAX_METADATA = 2 << 20
DIAGNOSTIC_BYTES = 8192
SCHEMA = 'foraging_source_api_cli_authority_v1'


def _source(path, pin):
    """Capture exact small source before compiling; no import-path lookup."""
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('source path must be ordinary')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != pin['bytes']:
            raise ValueError('source extent/type mismatch')
        chunks, left = [], pin['bytes']
        while left:
            part = os.read(fd, min(left, 65536))
            if not part:
                raise ValueError('short source')
            chunks.append(part)
            left -= len(part)
        extra = os.read(fd, 1)
        after, named = os.fstat(fd), path.lstat()
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink', 'st_mode')
        if extra or any(getattr(before, k) != getattr(after, k) or getattr(before, k) != getattr(named, k) for k in fields):
            raise ValueError('source changed during capture')
        body = b''.join(chunks)
        if hashlib.sha256(body).hexdigest() != pin['sha256']:
            raise ValueError('source hash mismatch')
        return body
    finally:
        os.close(fd)


def load_components(source_root):
    """Load only five frozen components into this fresh operator process."""
    root = Path(source_root).absolute()
    bodies = {name: _source(root / name, pin) for name, pin in DEPENDENCIES.items()}
    names = [Path(name).stem for name in DEPENDENCIES]
    if any(name in sys.modules for name in names):
        raise ValueError('component module namespace is not fresh')
    modules = {}
    for filename, body in bodies.items():
        name = Path(filename).stem
        module = types.ModuleType(name)
        module.__file__ = str(root / filename)
        sys.modules[name] = module
        modules[name] = module
        exec(compile(body, module.__file__, 'exec'), module.__dict__)
    return modules, sum(len(v) + 1 for v in bodies.values())


def _execute(selection, budget, modules, state):
    """Internal generated-control seam; CLI fixes modules via load_components."""
    c, replay = modules['common'], modules['author_replay']
    fields = {'schema', 'task_id', 'limits', 'prepared', 'author_source', 'output_root',
              'output_numeric_capacity_bytes', 'metadata_cap_bytes', 'component_scope_acknowledged'}
    c.need(type(selection) is dict and set(selection) == fields, 'exact component authority fields')
    c.need(selection['schema'] == SCHEMA and selection['task_id'] == c.TASK,
           'selected task/component authority')
    c.need(selection['component_scope_acknowledged'] is True, 'component-only scope acknowledgement')
    cap = selection['metadata_cap_bytes']
    c.need(type(cap) is int and 0 < cap <= MAX_METADATA, 'bounded complete metadata capacity')
    capacity = selection['output_numeric_capacity_bytes']
    c.need(type(capacity) is int and capacity > 0, 'positive full numeric capacity')
    output = c.ordinary(selection['output_root'])
    c.need(not output.exists(), 'fresh output root; never overwrite or resume a partial run')
    state['stage'] = 'prepared_admission'
    pdesc = selection['prepared']
    prepared = c.parse(c.read(pdesc['path'], pdesc, budget, MAX_PREPARED))
    state['stage'] = 'author_source_admission'
    adesc = selection['author_source']
    c.need(c.descriptor(adesc) == {'bytes': replay.AUTHOR_BYTES, 'sha256': replay.AUTHOR_SHA256},
           'exact retained author source descriptor')
    author = c.read(adesc['path'], adesc, budget, replay.AUTHOR_BYTES)
    state['stage'] = 'replay'
    state['attempted_fits'] = None
    state['completed_sessions'] = None
    report, probabilities = replay.replay_prepared(prepared, author, budget, capacity)
    state['stage'] = 'complete_panel_validation'
    c.need(type(report) is dict, 'component report object')
    state['attempted_fits'] = report.get('completed_real_fits')
    state['completed_sessions'] = len(report.get('sessions', {}))
    c.need(type(report) is dict and report.get('schema') == 'foraging_source_api_real_branch_v1'
           and report.get('task_id') == c.TASK and report.get('completed_real_fits') == 200,
           'complete200-fit component report')
    records = prepared['records']
    ids = [row['session_id'] for row in records]
    c.need(len(ids) == len(set(ids)) == 40 and set(probabilities) == set(ids)
           and set(report['sessions']) == set(ids), 'complete matching40-session panel')
    c.need(report.get('paper_reproduced') is None and report.get('paper_win') is None
           and report.get('improvement_ready') is False
           and report.get('source_shuffle_companions_executed') is False,
           'component report must preserve qualification limits')
    c.need(sys.byteorder == 'little', 'this version exports explicit little-endian float64')
    total = 0
    for row in records:
        sid, rows = row['session_id'], row['rows']
        c.need(type(sid) is str and len(sid) == 24 and all(v in '0123456789abcdef' for v in sid)
               and type(rows) is int and rows > 0, 'bounded private session identity and rows')
        a = memoryview(probabilities[sid])
        c.need(a.ndim == 1 and a.c_contiguous and a.format == 'd' and a.itemsize == 8
               and a.shape == (rows,), 'complete nativefloat64 vector')
        budget.reading(a.nbytes)
        c.need(all(math.isfinite(p) and 0 <= p <= 1 for p in a), 'every probability finite and bounded')
        total += a.nbytes
        c.need(total <= capacity, 'cumulative complete numeric output cap')
    c.need(report.get('output_numeric_bytes') == total, 'exact numeric report accounting')
    raw_report = c.encode_bounded(report, cap)
    state['stage'] = 'persist_complete_component'
    c.mkdir_owned(output, budget)
    exports = {}
    for row in records:
        sid = row['session_id']
        a = memoryview(probabilities[sid])
        budget.reading(a.nbytes)
        body = a.tobytes()
        dest = output / (sid + '.f64')
        exports[sid] = {'file': dest.name, 'rows': row['rows'], 'dtype': '<f8',
                        **c.write(dest, body, budget)}
    report_pin = c.write(output / 'AUTHOR_COMPONENT.json', raw_report, budget)
    result = {'schema': 'foraging_source_api_cli_result_v1', 'task_id': c.TASK,
              'status': 'complete_author_api_component_only', 'complete_sessions': 40,
              'completed_real_fits': 200, 'probabilities': exports,
              'author_component': {'file': 'AUTHOR_COMPONENT.json', **report_pin},
              'prepared': c.descriptor(pdesc), 'author_source': c.descriptor(adesc),
              'numeric_output_bytes': total,
              'paper_reproduced': None, 'paper_win': None, 'overall_benchmark_ready': False,
              'remaining': ['original source shuffle companions', 'required model audit',
                            'independent reference qualification', 'protected paired participant execution'],
              'accounting_scope': 'Managed explicit I/O only; no physical I/O, hard RAM or complete outer closure claim.'}
    result_pin = c.write(output / 'COMPONENT_RESULT.json', c.encode_bounded(result, cap), budget)
    state['stage'] = 'completed'
    return {'status': result['status'], 'complete_sessions': 40, 'completed_real_fits': 200,
            'result_file': str(output / 'COMPONENT_RESULT.json'), 'result': result_pin,
            'managed_read_bytes': budget.read, 'managed_write_charge_bytes': budget.write,
            'managed_retained_charge_bytes': budget.retained,
            'paper_reproduced': None, 'paper_win': None}


def _failure(exc, state, modules):
    replay = modules.get('author_replay') if modules else None
    if replay is not None and isinstance(exc, replay.ReplayFailure):
        state['attempted_fits'] = exc.attempted_fits
        state['completed_sessions'] = exc.completed_sessions
    # This is an operator-only stream. Preserve bounded existing string details
    # without invoking arbitrary exception formatting or publishing hidden data.
    detail = exc.args[0] if len(exc.args) == 1 and type(exc.args[0]) is str else None
    return {'schema': 'foraging_source_api_cli_failure_v1', 'status': 'failed',
            'stage': state['stage'], 'exception_type': type(exc).__name__,
            'message_prefix': None if detail is None else detail[:1024],
            'message_truncated': detail is not None and len(detail) > 1024,
            'stream_role': 'operator_only_not_candidate_visible',
            'attempted_fits': state['attempted_fits'],
            'completed_sessions': state['completed_sessions'],
            'partial_output_is_success': False, 'automatic_retry': False,
            'paper_reproduced': None, 'paper_win': None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--authority', required=True)
    parser.add_argument('--authority-sha256', required=True)
    args = parser.parse_args(argv)
    origin, modules, budget = time.monotonic(), {}, None
    state = {'stage': 'source_capture', 'attempted_fits': 0, 'completed_sessions': 0}
    try:
        if not sys.dont_write_bytecode:
            raise ValueError('invoke with -B; source cache writes are not selected')
        modules, source_read = load_components(args.source_root)
        c = modules['common']
        state['stage'] = 'authority_admission'
        _, selection, budget = c.authority(args.authority, args.authority_sha256, origin)
        budget.reading(source_read)
        # Reserve this operation's single terminal diagnostic in the selected
        # cumulative write/retained allowance before consuming numerical inputs.
        c.need(budget.limits['write_bytes'] > DIAGNOSTIC_BYTES
               and budget.limits['retained_bytes'] > DIAGNOSTIC_BYTES, 'terminal diagnostic reservation')
        budget.limits = dict(budget.limits)
        budget.limits['write_bytes'] -= DIAGNOSTIC_BYTES
        budget.limits['retained_bytes'] -= DIAGNOSTIC_BYTES
        result = _execute(selection, budget, modules, state)
        code = 0
    except Exception as exc:
        result, code = _failure(exc, state, modules), 2
    import json
    body = (json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if len(body) > DIAGNOSTIC_BYTES:
        body = b'{"status":"failed","stage":"terminal_encoding","partial_output_is_success":false}\n'
        code = 2
    # Caller must drain and bound this stream and enforce the outer deadline.
    view = memoryview(body)
    while view:
        written = os.write(1, view)
        if written <= 0:
            return 2
        view = view[written:]
    return code


if __name__ == '__main__':
    raise SystemExit(main())
