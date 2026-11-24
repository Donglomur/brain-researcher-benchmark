#!/usr/bin/env python3
"""Operator CLI for the complete source HW reference. Never a paper-win grader."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import types

LEGACY_PIN = {'bytes': 12127, 'sha256': '49de75cbcab0392cccae2d365f78c11fe63c428308ba37d8a0af8b53a61741ea'}
REFERENCE_PIN = {'bytes': 17118, 'sha256': '99354734914ec91f308d7d7f0d4e34979e1d3b5cae50d28039c363c6e0ea18ba'}
SCHEMA = "foraging_full_hw_authority_v1"
DIAGNOSTIC_BYTES = 8192
MAX_METADATA = 16 << 20

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


def load_components(program_root):
    root = Path(program_root).absolute()
    old_body = _source(root.parent / 'source-api-cli-v1/cli.py', LEGACY_PIN)
    new_path = Path(__file__).absolute().with_name('reference.py')
    new_body = _source(new_path, REFERENCE_PIN)
    old = types.ModuleType('_foraging_source_api_bootstrap')
    old.__file__ = str(root.parent / 'source-api-cli-v1/cli.py')
    exec(compile(old_body, old.__file__, 'exec'), old.__dict__)
    modules, read_bytes = old.load_components(root)
    name = 'full_hw_reference'
    if name in sys.modules:
        raise ValueError('full reference module namespace is not fresh')
    new = types.ModuleType(name)
    new.__file__ = str(new_path)
    sys.modules[name] = new
    exec(compile(new_body, new.__file__, 'exec'), new.__dict__)
    modules[name] = new
    return modules, read_bytes + len(old_body) + len(new_body) + 2


def _execute(selection, budget, modules, state):
    c, ref, prior = modules['common'], modules['full_hw_reference'], modules['author_replay']
    fields = {'schema', 'task_id', 'limits', 'prepared', 'author_source', 'output_root',
              'output_numeric_capacity_bytes', 'metadata_cap_bytes', 'fold_audit_cap_bytes',
              'audit_total_capacity_bytes', 'rng', 'component_scope_acknowledged'}
    c.need(type(selection) is dict and set(selection) == fields
           and selection['schema'] == SCHEMA and selection['task_id'] == c.TASK
           and selection['component_scope_acknowledged'] is True, 'exact full-HW component authority')
    for key in ('metadata_cap_bytes', 'fold_audit_cap_bytes'):
        c.need(type(selection[key]) is int and 0 < selection[key] <= MAX_METADATA,
               'explicit bounded metadata document capacity')
    for key in ('output_numeric_capacity_bytes', 'audit_total_capacity_bytes'):
        c.need(type(selection[key]) is int and selection[key] > 0, 'positive full-panel capacity')
    ref.validate_rng(selection['rng'])
    output = c.ordinary(selection['output_root'])
    c.need(not output.exists(), 'fresh private output root; no overwrite or resume')
    state['stage'] = 'source_and_prepared_admission'
    pdesc, adesc = selection['prepared'], selection['author_source']
    prepared = c.parse(c.read(pdesc['path'], pdesc, budget, MAX_METADATA))
    records = prior._source_records(prepared)
    c.need(c.descriptor(adesc) == {'bytes': prior.AUTHOR_BYTES, 'sha256': prior.AUTHOR_SHA256},
           'exact author source descriptor')
    source = c.read(adesc['path'], adesc, budget, prior.AUTHOR_BYTES)
    ref.author_hw_branch(source)  # Refuse bad source before any artifact creation.
    c.need(16 * sum(r['rows'] for r in records) <= selection['output_numeric_capacity_bytes'],
           'complete real-and-shuffle output capacity')
    c.mkdir_owned(output, budget)
    ids = {r['session_id'] for r in records}
    captures, audit_bytes = {}, 0
    def capture(audit):
        nonlocal audit_bytes
        sid, fold = audit['session_id'], audit['fold']
        c.need(sid in ids and type(fold) is int and 1 <= fold <= 5
               and (sid, fold) not in captures, 'unique original fold audit identity')
        raw = c.encode_bounded(audit, selection['fold_audit_cap_bytes'])
        c.need(audit_bytes + len(raw) <= selection['audit_total_capacity_bytes'],
               'cumulative complete model-audit capacity')
        audit_bytes += len(raw)
        file = f'{sid}.fold{fold}.json'
        pin = {'file': file, **c.write(output / file, raw, budget)}
        captures[(sid, fold)] = pin
        return pin
    state['stage'] = 'full_reference'
    state['fit_counts'], state['completed_sessions'] = None, None
    report, probabilities = ref.replay_prepared(
        prepared, source, budget, selection['output_numeric_capacity_bytes'], selection['rng'], capture)
    state['fit_counts'], state['completed_sessions'] = report.get('fit_counts'), len(report.get('sessions', {}))
    state['stage'] = 'complete_output_readmission'
    expected_counts = {f'{role}_{event}': 200 for role in ('real', 'shuffle')
                       for event in ('attempted', 'completed')}
    c.need(report.get('schema') == ref.SCHEMA and report.get('task_id') == c.TASK
           and report.get('fit_counts') == expected_counts and set(report['sessions']) == ids
           and report.get('paper_reproduced') is None and report.get('paper_win') is None
           and report.get('improvement_ready') is False
           and report.get('source_shuffle_companions_executed') is True
           and report.get('historical_shuffle_realization_reproduced') is False,
           'complete component report with unchanged scientific limits')
    expected_audits = {(sid, fold) for sid in ids for fold in range(1, 6)}
    c.need(set(captures) == expected_audits and len(report['model_audits']) == 200,
           'all200 paired model audits required')
    expected_pins = [{'session_id': sid, 'fold': fold, **pin}
                     for (sid, fold), pin in captures.items()]
    c.need(report['model_audits'] == expected_pins, 'captured model audits match report exactly')
    for (sid, fold), pin in captures.items():
        saved = c.parse(c.read(output / pin['file'], pin, budget, selection['fold_audit_cap_bytes']))
        c.need(saved.get('session_id') == sid and saved.get('fold') == fold
               and set(saved.get('models', {})) == {'real', 'shuffle'}, 'persisted paired model audit')
    c.need(set(probabilities) == {(sid, role) for sid in ids for role in ('real', 'shuffle')},
           'complete80 original probability vectors')
    c.need(sys.byteorder == 'little', 'explicit little-endian float64 export')
    total, exports = 0, {}
    for row in records:
        sid = row['session_id']
        exports[sid] = {}
        for role in ('real', 'shuffle'):
            view = memoryview(probabilities[(sid, role)])
            c.need(view.ndim == 1 and view.c_contiguous and view.format == 'd'
                   and view.itemsize == 8 and view.shape == (row['rows'],),
                   'complete native float64 probability vector')
            budget.reading(view.nbytes)
            c.need(all(math.isfinite(p) and 0 <= p <= 1 for p in view), 'all probabilities valid')
            total += view.nbytes
            c.need(total <= selection['output_numeric_capacity_bytes'], 'full numerical capacity')
            file = f'{sid}.{role}.f64'
            exports[sid][role] = {'file': file, 'rows': row['rows'], 'dtype': '<f8',
                                  **c.write(output / file, view.tobytes(), budget)}
    c.need(total == report['output_numeric_bytes'], 'exact complete numerical accounting')
    cap = selection['metadata_cap_bytes']
    rpin = c.write(output / 'REFERENCE.json', c.encode_bounded(report, cap), budget)
    result = {'schema': 'foraging_full_hw_result_v1', 'task_id': c.TASK,
              'status': 'complete_source_reference_component_only', 'complete_sessions': 40,
              'fit_counts': expected_counts, 'model_audit_files': 200, 'fitted_states': 400,
              'audit_payload_bytes': audit_bytes, 'numeric_output_bytes': total,
              'reference': {'file': 'REFERENCE.json', **rpin}, 'probabilities': exports,
              'prepared': c.descriptor(pdesc), 'author_source': c.descriptor(adesc),
              'rng_selection': selection['rng'], 'paper_reproduced': None, 'paper_win': None,
              'overall_benchmark_ready': False,
              'remaining': ['authentic reference qualification', 'historical source reconciliation',
                            'rat-session provenance', 'scientific comparison criteria',
                            'protected paired participant execution'],
              'accounting_scope': 'Explicit managed I/O only; no hard RAM, isolation or outer closure claim.'}
    pin = c.write(output / 'COMPONENT_RESULT.json', c.encode_bounded(result, cap), budget)
    state['stage'] = 'completed'
    return {'status': result['status'], 'result_file': str(output / 'COMPONENT_RESULT.json'),
            'result': pin, 'complete_sessions': 40, 'fit_counts': expected_counts,
            'managed_read_bytes': budget.read, 'managed_write_charge_bytes': budget.write,
            'managed_retained_charge_bytes': budget.retained, 'paper_reproduced': None, 'paper_win': None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--authority', required=True)
    parser.add_argument('--authority-sha256', required=True)
    args = parser.parse_args(argv)
    origin, modules = time.monotonic(), {}
    state = {'stage': 'source_capture', 'fit_counts': None, 'completed_sessions': None}
    try:
        if not sys.dont_write_bytecode:
            raise ValueError('invoke with -B; source cache writes are not selected')
        modules, source_bytes = load_components(args.source_root)
        c = modules['common']
        _, selection, budget = c.authority(args.authority, args.authority_sha256, origin)
        budget.reading(source_bytes)
        c.need(budget.limits['write_bytes'] > DIAGNOSTIC_BYTES
               and budget.limits['retained_bytes'] > DIAGNOSTIC_BYTES, 'terminal diagnostic reservation')
        budget.limits = dict(budget.limits)
        budget.limits['write_bytes'] -= DIAGNOSTIC_BYTES
        budget.limits['retained_bytes'] -= DIAGNOSTIC_BYTES
        result, code = _execute(selection, budget, modules, state), 0
    except Exception as exc:
        ref = modules.get('full_hw_reference')
        if ref is not None and isinstance(exc, ref.ReferenceFailure):
            state['fit_counts'], state['completed_sessions'] = exc.fit_counts, exc.completed_sessions
        detail = exc.args[0] if len(exc.args) == 1 and type(exc.args[0]) is str else None
        result = {'status': 'failed', **state, 'exception_type': type(exc).__name__,
                  'message_prefix': None if detail is None else detail[:1024],
                  'stream_role': 'operator_only_not_candidate_visible',
                  'partial_output_is_success': False, 'automatic_retry': False,
                  'paper_reproduced': None, 'paper_win': None}
        code = 2
    body = (json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if len(body) > DIAGNOSTIC_BYTES:
        body, code = b'{"status":"failed","stage":"terminal_encoding"}\n', 2
    view = memoryview(body)
    while view:
        written = os.write(1, view)
        if written <= 0:
            return 2
        view = view[written:]
    return code


if __name__ == '__main__':
    raise SystemExit(main())
