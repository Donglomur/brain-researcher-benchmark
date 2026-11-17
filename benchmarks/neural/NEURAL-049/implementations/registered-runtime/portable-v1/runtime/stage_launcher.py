"""Pinned dormant preparation/bank launcher; never manufactures qualification."""
import argparse
import contextlib
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import types


class Refused(ValueError):
    pass


def need(value, message):
    if not value:
        raise Refused(message)


def fields(value, keys, message):
    need(type(value) is dict and set(value) == set(keys), message)


def positive(value, zero=False):
    need(type(value) is int and value >= (0 if zero else 1), 'ordinary bounded integer')
    return value


def pin(value):
    fields(value, ('bytes', 'sha256'), 'exact pin')
    positive(value['bytes'], True)
    need(type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'SHA256 pin')
    return value


def path(value):
    need(type(value) is str and len(value) <= 4096 and value.startswith('/') and not value.startswith('//')
         and '\\' not in value and value == str(Path(value))
         and all(x not in ('.', '..') for x in value.split('/')[1:]), 'canonical absolute path')
    return Path(value)


def descriptor(value):
    fields(value, ('path', 'pin'), 'exact absolute descriptor')
    path(value['path']); pin(value['pin'])
    return value


def pairs(rows):
    result = {}
    for key, value in rows:
        need(key not in result, 'duplicate JSON field')
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(Refused('nonfinite JSON')))


def bounded_json(value, cap):
    """Reserve a conservative serialization bound before the JSON allocation."""
    total = 1
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop(); nodes += 1
        need(depth <= 32 and nodes <= 100000, 'bounded metadata tree')
        if item is None or type(item) is bool:
            total += 6
        elif type(item) is int:
            need(item.bit_length() <= 256, 'bounded metadata integer'); total += 80
        elif type(item) is float:
            need(math.isfinite(item), 'finite metadata number'); total += 32
        elif type(item) is str:
            # ensure_ascii emits a surrogate pair (12 bytes) for non-BMP text.
            total += 12 * len(item) + 3
        elif type(item) in (list, tuple):
            total += len(item) + 2
            need(len(item) <= 10000, 'bounded metadata list')
            pending.extend((v, depth + 1) for v in item)
        elif type(item) is dict:
            total += len(item) * 2 + 2
            need(len(item) <= 10000 and all(type(k) is str for k in item), 'bounded metadata map')
            pending.extend((v, depth + 1) for pair in item.items() for v in pair)
        else:
            raise Refused('primitive metadata only')
        need(total <= cap, 'prospective serialized metadata bound')
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False) + '\n').encode('ascii')
    need(len(raw) <= cap, 'serialized metadata cap')
    return raw


def exception_record(exc, depth=0):
    result = {'type': type(exc).__name__[:128]}
    if depth >= 4:
        return {**result, 'details_truncated': True}
    if isinstance(exc, BaseExceptionGroup):
        result['errors'] = [exception_record(e, depth + 1) for e in exc.exceptions[:8]]
        result['total_errors'] = len(exc.exceptions)
    else:
        result['args'] = [a[:512] if type(a) is str else a if type(a) in (bool, int, float)
                          and (type(a) is not int or a.bit_length() < 128)
                          and (type(a) is not float or math.isfinite(a)) else type(a).__name__
                          for a in exc.args[:8]]
    return result


class Ledger:
    def __init__(self, context):
        fields(context, ('schema', 'operation', 'origin', 'deadline', 'source_read_cap',
            'request_read_cap', 'outer_read_cap', 'outer_write_cap', 'outer_live_cap',
            'failure_write_reserve', 'operation_context'), 'exact outer context')
        need(context['schema'] == 'neural049_portable_stage_context_v1'
             and context['operation'] in ('prepare', 'bank'), 'selected original operation')
        for k in ('origin', 'deadline'):
            need(type(context[k]) in (int, float) and math.isfinite(context[k]), 'finite original clock')
        need(context['origin'] < context['deadline'], 'ordered original clock')
        for k in ('source_read_cap', 'request_read_cap', 'outer_read_cap', 'outer_write_cap',
                  'outer_live_cap', 'failure_write_reserve'):
            positive(context[k])
        self.context = context
        self.read_reserved = self.read_observed = self.write_reserved = self.write_observed = 0
        self.live_reserved = 0
        self.paths = []
        self.source_context = None
        self.operation_entered = False
        self.operation_returned = False
        self.native_io = 'unknown; child allowance reserved, independent original capture required'
        self.tick()

    def tick(self):
        now = time.monotonic()
        need(self.context['origin'] <= now < self.context['deadline'], 'original clock expired or reset')
        return now

    def reserve(self, read, write, live):
        self.tick()
        need(self.read_reserved + read <= self.context['outer_read_cap'], 'outer read reservation')
        need(self.write_reserved + write <= self.context['outer_write_cap'], 'outer write reservation')
        need(live <= self.context['outer_live_cap'], 'outer declared live reservation')
        self.read_reserved += read; self.write_reserved += write; self.live_reserved = live

    def record(self):
        return {'read_reserved': self.read_reserved, 'outer_read_observed': self.read_observed,
            'write_reserved': self.write_reserved, 'outer_stdout_bytes': self.write_observed,
            'declared_live_reserved': self.live_reserved, 'attempted_paths': list(self.paths),
            'original_source_context': self.source_context,
            'known_source_and_outer_read_bytes': self.read_observed + (self.source_context['read_observed'] if self.source_context else 0),
            'operation_entered': self.operation_entered,
            'operation_returned': self.operation_returned, 'native_io': self.native_io,
            'physical_peak_rss_or_allocator': 'unqualified',
            'unused_read_ceiling_is_not_measured_io': self.context['outer_read_cap'] - self.read_reserved}

    def capture(self, value, ceiling, account):
        descriptor(value); n = value['pin']['bytes']; need(n <= ceiling, 'bounded exact extent')
        self.tick(); p = path(value['path']); self.paths.append(str(p))
        parents = []
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        for parent in reversed(p.parents):
            s = os.lstat(parent); need(stat.S_ISDIR(s.st_mode), 'ordinary source parent')
            parents.append((parent, (s.st_dev, s.st_ino, s.st_mode)))
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        primary = None; raw = None; opened_stamp = None
        try:
            before = os.fstat(fd)
            opened_stamp = stamp(before)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == n
                 and before.st_mode & 0o222 == 0, 'sealed ordinary exact file')
            data = bytearray()
            while len(data) < n:
                self.tick(); block = os.read(fd, min(65536, n - len(data)))
                self.read_observed += len(block); account['observed'] += len(block)
                need(block, 'short capture'); data.extend(block)
            self.tick(); extra = os.read(fd, 1)
            self.read_observed += len(extra); account['observed'] += len(extra)
            need(not extra and stamp(before) == stamp(os.fstat(fd)) == stamp(os.lstat(p)), 'capture custody')
            for parent, expected in parents:
                s = os.lstat(parent)
                need((s.st_dev, s.st_ino, s.st_mode) == expected, 'parent custody')
            raw = bytes(data)
            need(hashlib.sha256(raw).hexdigest() == value['pin']['sha256'], 'capture hash')
            self.tick()
        except BaseException as exc:
            primary = exc
        try:
            os.close(fd)
        except BaseException as exc:
            primary = BaseExceptionGroup('capture and close failed', [primary, exc]) if primary else exc
        try:
            if opened_stamp is not None:
                need(stamp(os.lstat(p)) == opened_stamp, 'post-close current-name custody')
            for parent, expected in parents:
                s = os.lstat(parent)
                need((s.st_dev, s.st_ino, s.st_mode) == expected, 'post-close parent custody')
        except BaseException as exc:
            primary = BaseExceptionGroup('capture and post-close custody failed', [primary, exc]) if primary else exc
        try:
            self.tick()
        except BaseException as exc:
            primary = BaseExceptionGroup('capture and terminal clock failed', [primary, exc]) if primary else exc
        if primary:
            raise primary
        return raw


class BoundedOutput:
    def __init__(self, cap, ledger):
        self.cap = cap; self.ledger = ledger; self.parts = []; self.size = 0
    def write(self, text):
        self.ledger.tick()
        need(type(text) is str and text.isascii() and self.size + len(text) <= self.cap,
             'bounded original preparation stdout')
        self.parts.append(text); self.size += len(text); return len(text)
    def flush(self):
        self.ledger.tick()
    def value(self):
        self.ledger.tick(); return ''.join(self.parts)


def admit_context(context, operation, request):
    need(context['operation'] == operation, 'matching selected operation')
    op = context['operation_context']
    need(type(op) is dict and op.get('origin') == context['origin']
         and op.get('deadline') == context['deadline'], 'unchanged original child clock')
    if operation == 'prepare':
        fields(op, ('origin', 'deadline', 'limits'), 'exact original preparation context')
        limits = op['limits']
        names = {'read_bytes', 'write_bytes', 'array_bytes', 'metadata_bytes', 'files',
                 'array_elements', 'live_bytes', 'rows', 'channels', 'source_files', 'output_files'}
        fields(limits, names, 'all original preparation limits')
        for v in limits.values(): positive(v)
        need(limits['files'] == limits['output_files'], 'original output file alias')
        fields(request, ('schema', 'operation', 'authority_path', 'authority_pin'), 'preparation request')
        need(request['schema'] == 'neural049_preparation_worker_request_v1'
             and request['operation'] == 'prepare', 'prepare only; no view substitution')
        path(request['authority_path']); pin(request['authority_pin'])
        return limits['read_bytes'], limits['write_bytes'], limits['live_bytes'], 12 * limits['metadata_bytes'] + 65536
    fields(op, ('origin', 'deadline', 'read_cap', 'write_cap'), 'exact original bank context')
    fields(request, ('schema', 'authority', 'source_manifest', 'operation_live_bytes'), 'launcher-only bank request')
    need(request['schema'] == 'neural049_portable_bank_stage_request_v1', 'bank request schema')
    descriptor(request['authority']); pin(request['source_manifest'])
    return positive(op['read_cap']), positive(op['write_cap']), positive(request['operation_live_bytes']), 0


def source_plan(manifest, expected, bootstrap):
    need(type(manifest) is dict and manifest.get('schema') == 'neural049_runtime_source_v1'
         and type(manifest.get('files')) is dict and len(manifest['files']) == 70, 'complete original70 source set')
    total = expected['bytes'] + 1
    retained = expected['bytes']
    for name, row in manifest['files'].items():
        need(type(name) is str and not name.startswith('/') and '\\' not in name
             and all(x not in ('', '.', '..') for x in name.split('/')), 'source relative name')
        pin(row); need(row['bytes'] <= 2 << 20, 'original bounded source member')
        total += row['bytes'] + 1; retained += row['bytes']
    need(retained <= 16 << 20 and manifest['files'].get('program/bootstrap.py') == bootstrap,
         'original total and bootstrap source join')
    need(manifest.get('overrides') == {'preparation/prepare.py': 'owner-helper-repairs-v1/preparation_prepare.py',
         'references/r2/budget.py': 'owner-helper-repairs-v1/r2_budget.py'}, 'unchanged original overlays')
    return total, retained


def execute(args, context, ledger):
    """Actual selected path; engineering controls must not invoke this function."""
    root = path(args.parent_root)
    source = pin({'bytes': args.source_bytes, 'sha256': args.source_sha256})
    bootpin = pin({'bytes': args.bootstrap_bytes, 'sha256': args.bootstrap_sha256})
    request_desc = descriptor({'path': args.request, 'pin': {'bytes': args.request_bytes, 'sha256': args.request_sha256}})
    need(source['bytes'] <= 2 << 20 and bootpin['bytes'] <= 2 << 20
         and request_desc['pin']['bytes'] <= 2 << 20, 'source/request bounded metadata')
    sc = context['source_read_cap']; rc = context['request_read_cap']
    need(request_desc['pin']['bytes'] + 1 <= rc
         and bootpin['bytes'] + source['bytes'] + 2 <= sc, 'initial exact probe ceilings')
    retained_bound = 16 * (sc + rc) + 65536
    ledger.reserve(sc + rc, context['failure_write_reserve'], retained_bound)
    probes = {'observed': 0}; req_reads = {'observed': 0}
    boot = ledger.capture({'path': str(root / 'program/bootstrap.py'), 'pin': bootpin}, 2 << 20, probes)
    manifest_raw = ledger.capture({'path': str(root / 'RUNTIME_SOURCE_V3.json'), 'pin': source}, 2 << 20, probes)
    manifest = parse(manifest_raw); original_reads, retained = source_plan(manifest, source, bootpin)
    need(bootpin['bytes'] + source['bytes'] + 2 + original_reads <= sc,
         'complete original source schedule reserved before capture')
    raw = ledger.capture(request_desc, 2 << 20, req_reads); request = parse(raw)
    op_read, op_write, op_live, stdout_cap = admit_context(context, args.operation, request)
    if args.operation == 'bank': need(request['source_manifest'] == source, 'bank source request join')
    failure_paths = [str(root / n) for n in manifest['files']]
    failure_paths += [str(root / 'program/bootstrap.py'), str(root / 'RUNTIME_SOURCE_V3.json'), args.request]
    failure_floor = 65536 + 12 * sum(len(n) + 32 for n in failure_paths)
    need(context['failure_write_reserve'] >= failure_floor, 'terminal reserve includes full original source path accounting')
    # Retains source copies, decoded metadata, compiled definitions and bounded output.
    ledger.reserve(op_read, op_write + 16 * stdout_cap,
                   retained_bound + op_live + 80 * stdout_cap + 4 * context['failure_write_reserve'])
    source_context = {'origin': context['origin'], 'deadline': context['deadline'],
                      'read_cap': sc - (bootpin['bytes'] + source['bytes'] + 2),
                      'read_reserved': 0, 'read_observed': 0, 'attempted_paths': []}
    ledger.source_context = source_context
    before_modules = set(sys.modules); before_finders = tuple(sys.meta_path)
    primary = None; result = None; sink = None
    try:
        module = types.ModuleType('_portable_authenticated_bootstrap')
        module.__file__ = str(root / 'program/bootstrap.py')
        ledger.tick(); exec(compile(boot, module.__file__, 'exec', dont_inherit=True), module.__dict__); ledger.tick()
        captured = module.load(root, root / 'RUNTIME_SOURCE_V3.json', source, source_context)
        need(captured['pin'] == source and captured['manifest'] == manifest, 'same complete captured source')
        ledger.tick()
        if args.operation == 'prepare':
            worker = importlib.import_module('preparation.worker_cli')
            sink = BoundedOutput(stdout_cap, ledger)
            child_context = bounded_json(context['operation_context'], 16384).decode('ascii')
            ledger.operation_entered = True
            with contextlib.redirect_stdout(sink):
                code = worker.main(['--request', args.request, '--request-bytes', str(args.request_bytes),
                    '--request-sha256', args.request_sha256, '--inherited-context', child_context])
            ledger.operation_returned = True; ledger.tick()
            need(type(code) is int, 'ordinary original worker return code')
            text = sink.value()
            result = {'operation': 'prepare', 'worker_return_code': code, 'worker_stdout': text,
                      'worker_stdout_pin': {'bytes': len(text), 'sha256': hashlib.sha256(text.encode('ascii')).hexdigest()}}
            need(code == 0, 'original preparation worker returned failure; stdout retained in failure envelope')
        else:
            bank = importlib.import_module('program.bank')
            ledger.operation_entered = True
            value = bank.build(request['authority'], source, context['operation_context'])
            ledger.operation_returned = True; ledger.tick()
            result = {'operation': 'bank', 'bank_return': value}
    except BaseException as exc:
        primary = exc
        if sink is not None and result is None:
            # A worker exception may occur before its normal returned record exists.
            # Preserve already captured text without requiring an unexpired clock.
            text = ''.join(sink.parts)
            result = {'operation': 'prepare', 'worker_return_code': None,
                'worker_stdout': text, 'worker_stdout_pin': {'bytes': len(text),
                'sha256': hashlib.sha256(text.encode('ascii')).hexdigest()}}
        if args.operation == 'bank' and hasattr(exc, 'failure_record'):
            try:
                bounded_json(exc.failure_record, context['failure_write_reserve'])
                result = {'operation': 'bank', 'bank_failure_record': exc.failure_record}
            except BaseException as later:
                primary = BaseExceptionGroup('bank failure and retained record admission failed', [primary, later])
                result = {'operation': 'bank', 'bank_failure_record_unavailable': True,
                          'child_costs_or_kernel_completion': 'unknown; inspect independent original capture'}
    finally:
        # Captured modules only; never remove unrelated pre-existing imports.
        try:
            new_finders = [v for v in sys.meta_path if v not in before_finders
                           and type(v).__module__ == '_portable_authenticated_bootstrap']
            for name in tuple(set(sys.modules) - before_modules):
                mod = sys.modules.get(name)
                if getattr(mod, '__loader__', None) in new_finders:
                    del sys.modules[name]
            for finder in new_finders:
                sys.meta_path.remove(finder)
            ledger.tick()
        except BaseException as exc:
            primary = BaseExceptionGroup('operation and source cleanup failed', [primary, exc]) if primary else exc
    if primary:
        failure = Refused('selected source operation failed')
        failure.operation_error = exception_record(primary)
        failure.partial_result = result
        raise failure from primary
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--operation', required=True, choices=('prepare', 'bank'))
    parser.add_argument('--parent-root', required=True)
    for name in ('source', 'bootstrap', 'request'):
        parser.add_argument('--' + name + '-bytes', required=True, type=int)
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--request', required=True)
    parser.add_argument('--context-json', required=True)
    args = parser.parse_args(argv)
    ledger = None; result = None; error = None; rc = 1
    try:
        need(len(args.context_json) <= 16384, 'bounded inherited outer context argument')
        context = parse(args.context_json); ledger = Ledger(context)
        result = execute(args, context, ledger); ledger.tick(); rc = 0
    except BaseException as exc:
        error = exception_record(exc)
        if hasattr(exc, 'operation_error'): error['operation_error'] = exc.operation_error
        result = getattr(exc, 'partial_result', result)
    envelope = {'schema': 'neural049_portable_stage_launcher_result_v1',
        'status': 'returned' if rc == 0 else 'failed', 'operation': args.operation,
        'result': result, 'error': error, 'costs_before_publication': ledger.record() if ledger else None,
        'own_future_exit_not_self_certified': True, 'actual_external_completion_required': True,
        'automatic_retry': False}
    cap = ledger.context['failure_write_reserve'] if ledger else 65536
    # The envelope may include retained original stdout; its separate allowance is explicit.
    if ledger and args.operation == 'prepare':
        limits = ledger.context.get('operation_context', {}).get('limits', {})
        if type(limits.get('metadata_bytes')) is int and limits['metadata_bytes'] > 0:
            cap += 16 * (12 * limits['metadata_bytes'] + 65536)
    try:
        raw = bounded_json(envelope, cap)
        if ledger:
            need(len(raw) <= ledger.write_reserved, 'reserved terminal publication')
            # Failure disclosure remains possible after expiry; never reports successful expiry.
            if rc == 0: ledger.tick()
        sys.stdout.buffer.write(raw); sys.stdout.buffer.flush()
        if ledger:
            ledger.write_observed += len(raw)
            if rc == 0: ledger.tick()
    except BaseException:
        # External original stream capture is authoritative if publication itself fails.
        raise
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
