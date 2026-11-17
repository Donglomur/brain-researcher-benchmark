"""Fixed participant I interpreter. Renderer binds SPEC and public source pins.

Generated analysis is candidate code inside the original offline actor, never
trusted controller code. The outer host/cgroup is the containment boundary.
This file makes no scientific or independent qualification claim.
"""
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import runpy
import selectors
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time

SPEC = None  # RENDER_SPEC
PARTICIPANT_INTERFACE = None  # RENDER_INTERFACE
MAGIC = b'N055I-SEAL-1\n'
DTYPES = {'<f8': (8, 'd'), '<f4': (4, 'f'), '<i8': (8, 'q'),
          '<i4': (4, 'i'), '<u8': (8, 'Q'), '<u4': (4, 'I'), '|u1': (1, 'B')}
NAME = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')
PROVIDER = re.compile(r'[a-z][a-z0-9_]{0,47}\Z')
METHOD_KEYS = {'schema', 'cell', 'fitted_people', 'fit_rows', 'learned_transforms',
               'inner_search', 'selected_settings', 'inference_action_policy', 'source_lineage'}


class Refusal(ValueError):
    pass


class AnalysisFailure(RuntimeError):
    def __init__(self, first, evidence):
        super().__init__(str(first))
        self.first = first
        self.evidence = evidence


def need(ok, message):
    if not ok:
        raise Refusal(message)


def keys(value, names):
    need(type(value) is dict and set(value) == set(names), 'closed keys: ' + ','.join(sorted(names)))


def sha(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def parse(body, cap):
    need(type(body) is bytes and 0 < len(body) <= cap, 'bounded nonempty JSON')
    def pairs(items):
        out = {}
        for name, value in items:
            need(name not in out, 'duplicate JSON key')
            out[name] = value
        return out
    def bad(value):
        raise Refusal('nonfinite JSON constant')
    def number(value):
        result = float(value); need(math.isfinite(result), 'nonfinite JSON number'); return result
    return json.loads(body.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad, parse_float=number)


def identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def ordinary(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'absolute canonical file')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'no path links')
    s = path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'ordinary single-link file')
    return s


def read(path, cap):
    path = Path(path); before = ordinary(path)
    need(0 <= before.st_size <= cap, 'file extent before read')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(identity(os.fstat(fd)) == identity(before), 'same opened file')
        out = bytearray()
        while len(out) <= before.st_size:
            part = os.read(fd, min(65536, before.st_size + 1 - len(out)))
            if not part:
                break
            out.extend(part)
        need(len(out) == before.st_size and identity(os.fstat(fd)) == identity(before)
             == identity(path.lstat()), 'complete stable file')
        return bytes(out)
    finally:
        os.close(fd)


def write_new(path, body, cap):
    path = Path(path)
    need(type(body) is bytes and 0 < len(body) <= cap, 'bounded publication')
    need(not any(p.is_symlink() for p in (path.parent, *path.parents)), 'publication parents')
    need(not path.exists() and not path.is_symlink(), 'fresh output member')
    temp = path.with_name(path.name + '.partial')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        pos = 0
        while pos < len(body):
            n = os.write(fd, memoryview(body)[pos:]); need(n > 0, 'write progress'); pos += n
        os.fchmod(fd, 0o444); os.fsync(fd)
    finally:
        os.close(fd)
    # No overwrite: both names are private, newly allocated, single-writer paths.
    need(not path.exists() and not path.is_symlink(), 'fresh final output name')
    os.link(temp, path, follow_symlinks=False); temp.unlink()
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    need(read(path, cap) == body, 'exact published bytes')
    return {'bytes': len(body), 'sha256': sha(body)}


def validate_spec(spec):
    keys(spec, ('schema', 'model_provider', 'tool_provider', 'fit_prompt', 'infer_prompt',
                'max_new_tokens', 'phase_steps', 'malformed_repair_slots', 'dependencies',
                'row_sum_abs_tolerance', 'limits'))
    need(spec['schema'] == 'neural055-fixed-i-loop-v1', 'selected I system schema')
    need(type(spec['model_provider']) is str and PROVIDER.fullmatch(spec['model_provider']), 'model provider ID')
    tool = spec['tool_provider']
    need(tool is None or (type(tool) is str and PROVIDER.fullmatch(tool) and tool != spec['model_provider']), 'distinct tool provider ID or explicit null')
    need(all(type(spec[k]) is str and spec[k] for k in ('fit_prompt', 'infer_prompt')), 'explicit phase prompts')
    need(type(spec['max_new_tokens']) is int and spec['max_new_tokens'] > 0, 'explicit token limit')
    keys(spec['phase_steps'], ('fit', 'infer'))
    need(all(type(x) is int and x > 0 for x in spec['phase_steps'].values()), 'finite phase decision counts')
    need(type(spec['malformed_repair_slots']) is int and spec['malformed_repair_slots'] >= 0, 'explicit parser repair slots')
    need(type(spec['dependencies']) is list, 'declared dependencies')
    tolerance = spec['row_sum_abs_tolerance']
    need(type(tolerance) in (int, float) and math.isfinite(tolerance) and 0 <= tolerance < 1, 'explicit normalization tolerance')
    names = ('context_bytes', 'decision_bytes', 'analysis_source_bytes', 'analysis_seconds',
             'closure_seconds', 'stream_bytes', 'workspace_bytes', 'workspace_files',
             'artifact_bytes', 'seal_bytes', 'seal_header_bytes', 'state_count', 'sealed_action_count')
    lim = spec['limits']; keys(lim, names)
    for k, v in lim.items():
        need(type(v) in ((int, float) if k.endswith('_seconds') else (int,))
             and math.isfinite(v) and v > 0, 'positive finite selected limit: ' + k)
    need(lim['context_bytes'] <= 786432 and lim['decision_bytes'] <= 262144,
         'model dialogue fits original wire envelope')
    need(lim['analysis_source_bytes'] <= 131072 and lim['seal_bytes'] <= 268435456
         and lim['seal_header_bytes'] <= 8388608 and lim['artifact_bytes'] <= 268435456,
         'original source/model limits')
    need(lim['stream_bytes'] <= 1048576 and lim['workspace_files'] <= 65536,
         'finite diagnostics and workspace enumeration')
    need(lim['artifact_bytes'] <= lim['workspace_bytes'] and lim['seal_header_bytes'] < lim['seal_bytes'], 'coherent selected extents')
    need(len(encoded(spec)) <= 65536, 'bounded emitted immutable specification')
    return spec


def validate_interface(interface):
    keys(interface, ('schema', 'documents'))
    need(interface['schema'] == 'neural055-participant-interface-v4', 'current public interface')
    expected = {'TASK.md', 'POLICY.json', 'interface.py', 'CASE_SCHEMA.json', 'PREDICTION_SCHEMA.json',
                'PROGRAM_ABI_V3.md', 'CELL_SCHEMA.json', 'SELECTED_METHOD_SCHEMA.json', 'OPERATIONS_SCHEMA.json',
                'BROKER_REQUEST_SCHEMA.json', 'BROKER_RESPONSE_SCHEMA.json', 'PREEXPOSURE_POLICY_SCHEMA.json', 'RESOURCE_POLICY_V1.json'}
    need(type(interface['documents']) is dict and set(interface['documents']) == expected, 'whole public interface acknowledgement')
    for p in interface['documents'].values():
        keys(p, ('bytes', 'sha256'))
        need(type(p['bytes']) is int and 0 < p['bytes'] <= 1048576 and type(p['sha256']) is str
             and re.fullmatch('[0-9a-f]{64}', p['sha256']), 'public body pin')
    return interface


def guard(end):
    need(time.monotonic() < end, 'original work deadline')


def validate_cell(cell):
    keys(cell, ('task_id', 'protocol_version', 'evaluated_system', 'mode', 'tool_setting', 'seed', 'arm', 'outer_person'))
    need(cell['task_id'] == 'NEURAL-055' and cell['protocol_version'] == 'complete-scientific-api-design-s3'
         and cell['mode'] == 'I' and type(cell['evaluated_system']) is str
         and bool(cell['evaluated_system']), 'same original investigator cell')
    need(cell['tool_setting'] in ('T0', 'T1') and cell['seed'] in (55055, 55056, 55057)
         and cell['arm'] in ('FULL', 'IMAGE_ONLY', 'PRE_ONLY', 'POST_ONLY', 'ALIGN_SHUFFLE')
         and cell['outer_person'] in ['sub-%02d' % i for i in range(1, 11)], 'original cell factors')


def method(value, cell, spec):
    need(type(value) is dict and METHOD_KEYS <= set(value) <= METHOD_KEYS | {'reference_detail'}, 'selected method fields')
    need(value['schema'] == 'neural055-selected-method-v2' and value['cell'] == cell, 'same selected method cell')
    people = value['fitted_people']; eligible = {'sub-%02d' % i for i in range(1, 11)} - {cell['outer_person']}
    need(type(people) is list and len(people) == len(set(people)) and set(people) <= eligible, 'eligible fitting people')
    rows = value['fit_rows']
    need(type(rows) is list and all(type(x) is int and 0 <= x < 16540 for x in rows) and len(rows) == len(set(rows)), 'original fitting rows')
    need(all(type(value[k]) is list for k in ('learned_transforms', 'inner_search', 'source_lineage')), 'method evidence arrays')
    policy = value['inference_action_policy']; need(type(policy) is dict and policy.get('query_fit') is False, 'no query fitting')
    actions = policy.get('broker_actions'); need(type(actions) is list, 'sealed broker action list')
    admitted = set()
    for a in actions:
        keys(a, ('provider', 'operation')); pair = (a['provider'], a['operation'])
        need(pair not in admitted, 'unique sealed action')
        need(pair == (spec['model_provider'], 'generate') or (cell['tool_setting'] == 'T1'
             and spec['tool_provider'] is not None and a['provider'] == spec['tool_provider']
             and a['operation'] in ('development_report', 'candidate_predictions', 'query_scores')), 'permitted sealed broker action')
        admitted.add(pair)
    need((spec['model_provider'], 'generate') in admitted, 'fixed inference decision loop is declared')
    return value


def decode_decision(text, phase, spec):
    need(type(text) is str, 'one text decision')
    value = parse(text.encode('utf-8'), spec['limits']['decision_bytes'])
    need(type(value) is dict and type(value.get('kind')) is str, 'decision object')
    kind = value['kind']
    forms = {'tool': ('kind', 'operation', 'payload'), 'finish_fit': ('kind',),
             'finish_infer': ('kind',), 'analysis': ('kind', 'source'), 'sealed_analysis': ('kind', 'action')}
    need(kind in forms, 'known decision kind'); keys(value, forms[kind])
    need(kind in (('tool', 'analysis', 'finish_fit') if phase == 'fit' else ('tool', 'sealed_analysis', 'finish_infer')), 'phase decision permission')
    if kind == 'analysis':
        need(type(value['source']) is str and 0 < len(value['source'].encode()) <= spec['limits']['analysis_source_bytes'], 'bounded generated FIT source')
    if kind == 'sealed_analysis':
        need(type(value['action']) is str and NAME.fullmatch(value['action']), 'sealed action name')
    return value


def workspace_inventory(root, spec):
    files = {}; total = 0; directories = 0
    for base, dirs, names in os.walk(root, followlinks=False):
        need(not any((Path(base) / n).is_symlink() for n in dirs), 'no workspace directory links')
        directories += len(dirs)
        need(directories + len(files) <= spec['limits']['workspace_files'], 'bounded workspace directories')
        for name in names:
            p = Path(base) / name; s = ordinary(p); total += s.st_size
            need(directories + len(files) < spec['limits']['workspace_files'] and total <= spec['limits']['workspace_bytes'], 'selected workspace file/byte cap')
            files[str(p.relative_to(root))] = identity(s)
    return files, total


class ActorChildren:
    """Actual same-container Linux children; never usable as a host PID killer."""
    def __init__(self):
        need(sys.platform == 'linux' and os.getpid() == 1 and os.getuid() == 65534,
             'analysis must run in the original unprivileged PID1 actor')
        need(hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'), 'required exact Linux child signal handles')
        self.scope = Path('/proc/self/cgroup').read_bytes()
        need(self.members() == {1}, 'no earlier actor children before analysis')

    def members(self):
        raw = Path('/sys/fs/cgroup/cgroup.procs').read_bytes()
        need(len(raw) <= 1048576, 'bounded actual actor membership')
        result = {int(x) for x in raw.split()}
        need(1 in result and all(x > 0 for x in result), 'actual PID namespace membership')
        return result

    def close(self, end, natural):
        records = []; unexpected = False
        while True:
            while True:
                try:
                    pid, status = os.waitpid(-1, os.WNOHANG)
                except ChildProcessError:
                    break
                if pid == 0:
                    break
                records.append({'reaped_pid': pid, 'wait_status': status})
            members = self.members() - {1}
            if not members:
                if natural:
                    need(not unexpected, 'natural analysis left live descendants')
                return records
            unexpected = True
            guard(end)
            for pid in sorted(members):
                try:
                    fd = os.pidfd_open(pid, 0)
                except ProcessLookupError:
                    continue
                try:
                    need(Path('/proc/%d/cgroup' % pid).read_bytes() == self.scope, 'same original actor cgroup')
                    signal.pidfd_send_signal(fd, signal.SIGKILL, None, 0)
                    records.append({'killed_actor_pid': pid})
                except ProcessLookupError:
                    pass
                finally:
                    os.close(fd)
            time.sleep(min(.005, max(0, end - time.monotonic())))


def execute_analysis(source, request, ctx):
    """Real bounded child; generated source has only original actor privileges."""
    spec = ctx['spec']; lim = spec['limits']; guard(ctx['work_end'])
    body = source.encode('utf-8'); need(0 < len(body) <= lim['analysis_source_bytes'], 'analysis source cap')
    owner = ActorChildren()  # Fixed concrete production observer; no request-supplied callback.
    job = Path(tempfile.mkdtemp(prefix='analysis-', dir=ctx['scratch']))
    (job / 'artifacts').mkdir(mode=0o700)
    req = dict(request, artifact_root=str(job / 'artifacts'))
    write_new(job / 'analysis.py', body, lim['analysis_source_bytes'])
    request_raw = encoded(req); write_new(job / 'REQUEST.json', request_raw, 8388608)
    argv = [sys.executable, '-I', '-B', str(job / 'analysis.py'), '--request', str(job / 'REQUEST.json'), '--result', str(job / 'RESULT.json')]
    end = min(ctx['work_end'], time.monotonic() + lim['analysis_seconds'])
    cleanup_end = min(ctx['deadline'], end + lim['closure_seconds'])
    record = {'kind': 'analysis_process', 'source_sha256': sha(body), 'request_sha256': sha(request_raw),
              'argv': argv, 'returncode': None, 'natural_exit': False, 'stdout': '', 'stderr': '',
              'observed_stream_bytes': 0, 'stream_complete': False, 'closure': None, 'errors': []}
    child = None; first = None; sel = selectors.DefaultSelector(); streams = {'stdout': bytearray(), 'stderr': bytearray()}
    def limits():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        file_cap = min(536870912, lim['workspace_bytes'])
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_cap, file_cap))
    try:
        workspace_inventory(ctx['scratch'], spec)
        child = subprocess.Popen(argv, cwd=job, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, start_new_session=True, preexec_fn=limits,
                                 close_fds=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        for name, pipe in (('stdout', child.stdout), ('stderr', child.stderr)):
            os.set_blocking(pipe.fileno(), False); sel.register(pipe, selectors.EVENT_READ, name)
        while sel.get_map() or child.poll() is None:
            guard(end); workspace_inventory(ctx['scratch'], spec)
            for key, _ in sel.select(min(.02, max(0, end - time.monotonic()))):
                part = os.read(key.fileobj.fileno(), 65536)
                if not part:
                    sel.unregister(key.fileobj); key.fileobj.close(); continue
                record['observed_stream_bytes'] += len(part)
                room = max(0, lim['stream_bytes'] - sum(map(len, streams.values())))
                streams[key.data].extend(part[:room])
                need(record['observed_stream_bytes'] <= lim['stream_bytes'], 'selected combined analysis stream cap')
        record['returncode'] = child.wait(timeout=max(.001, end - time.monotonic()))
        record['natural_exit'] = True; record['stream_complete'] = True
        need(record['returncode'] == 0, 'analysis natural nonzero')
    except BaseException as exc:
        first = exc; record['errors'].append({'stage': 'analysis', 'type': type(exc).__name__, 'message': str(exc)[:512]})
    finally:
        if child is not None:
            try:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                record['returncode'] = child.wait(timeout=max(.001, cleanup_end - time.monotonic()))
            except BaseException as exc:
                record['errors'].append({'stage': 'child_reap', 'type': type(exc).__name__})
                if first is None: first = exc
        try:
            record['closure'] = owner.close(cleanup_end, first is None)
        except BaseException as exc:
            record['errors'].append({'stage': 'actor_descendants', 'type': type(exc).__name__})
            if first is None: first = exc
        for key in list(sel.get_map().values()):
            try:
                sel.unregister(key.fileobj); key.fileobj.close()
            except BaseException as exc:
                record['errors'].append({'stage': 'stream_close', 'type': type(exc).__name__})
                if first is None: first = exc
        sel.close()
        record['stdout'] = streams['stdout'].decode('utf-8', 'replace')
        record['stderr'] = streams['stderr'].decode('utf-8', 'replace')
        ctx['records'].append(record)
    if first is not None:
        raise AnalysisFailure(first, record) from first
    need(read(job / 'analysis.py', lim['analysis_source_bytes']) == body
         and read(job / 'REQUEST.json', 8388608) == request_raw, 'analysis source/request unchanged')
    workspace_inventory(ctx['scratch'], spec); guard(ctx['work_end'])
    result_raw = read(job / 'RESULT.json', lim['seal_header_bytes'])
    result = parse(result_raw, lim['seal_header_bytes'])
    record.update(result_sha256=sha(result_raw), result_bytes=len(result_raw), captured=True)
    return result, job


def shape_extent(dtype, shape, cap):
    need(dtype in DTYPES and type(shape) is list and 0 < len(shape) <= 8
         and all(type(x) is int and x >= 0 for x in shape), 'finite typed raw geometry')
    n = DTYPES[dtype][0]
    for x in shape:
        n *= x; need(n <= cap, 'typed extent cap')
    return n


def array_pin(path, dtype, shape, ctx):
    cap = ctx['spec']['limits']['artifact_bytes']; n = shape_extent(dtype, shape, cap)
    before = ordinary(path); need(before.st_size == n, 'complete typed array extent')
    h = hashlib.sha256(); count = 0; fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        need(identity(os.fstat(fd)) == identity(before), 'same typed array handle')
        while count < n:
            guard(ctx['work_end']); b = os.read(fd, min(65536, n - count)); need(bool(b), 'complete typed array read')
            if dtype.startswith('<f'):
                need(len(b) % DTYPES[dtype][0] == 0, 'whole scalar chunk')
                need(all(math.isfinite(x[0]) for x in struct.iter_unpack('<' + DTYPES[dtype][1], b)), 'finite raw floating state')
            h.update(b); count += len(b)
        need(not os.read(fd, 1) and identity(os.fstat(fd)) == identity(before) == identity(Path(path).lstat()), 'stable exact typed array')
    finally:
        os.close(fd)
    return {'dtype': dtype, 'shape': shape, 'bytes': n, 'sha256': h.hexdigest(), 'path': str(path)}


def admit_fit_result(result, job, ctx):
    keys(result, ('schema', 'observation', 'state', 'inference_actions', 'selected_method', 'context'))
    need(result['schema'] == 'neural055-i-fit-analysis-v1', 'FIT analysis result schema')
    lim = ctx['spec']['limits']; need(len(encoded(result['observation'])) <= lim['context_bytes'], 'bounded actual observation')
    need(type(result['state']) is list and len(result['state']) <= lim['state_count'], 'finite typed state table')
    state = []; names = set(); size = 0
    for row in result['state']:
        keys(row, ('name', 'dtype', 'shape', 'path')); name = row['name']
        need(type(name) is str and NAME.fullmatch(name) and name not in names, 'unique state name'); names.add(name)
        need(row['path'] == 'artifacts/' + name + '.raw', 'fixed state artifact path')
        p = array_pin(job / row['path'], row['dtype'], row['shape'], ctx); size += p['bytes']
        need(size <= lim['artifact_bytes'], 'whole state bytes'); state.append(dict(p, name=name))
    actions = result['inference_actions']; need(type(actions) is list and 0 < len(actions) <= lim['sealed_action_count'], 'finite nonempty inference actions')
    action_map = {}
    for row in actions:
        keys(row, ('name', 'source')); name = row['name']; source = row['source']
        need(type(name) is str and NAME.fullmatch(name) and name not in action_map, 'unique inference action')
        need(type(source) is str and 0 < len(source.encode()) <= lim['analysis_source_bytes'], 'bounded frozen inference source')
        action_map[name] = source
    need(len(encoded(result['context'])) <= lim['context_bytes'], 'bounded training-derived inference context')
    selected = method(result['selected_method'], ctx['cell'], ctx['spec'])
    return {'state': state, 'actions': action_map, 'method': selected, 'context': result['context']}


def tool_action(value, ctx, seal=None):
    spec = ctx['spec']; provider = spec['tool_provider']; operation = value['operation']; payload = value['payload']
    need(ctx['cell']['tool_setting'] == 'T1' and provider is not None, 'R2 unavailable to T0 or undeclared system')
    permitted = ('development_report', 'training_predictions') if ctx['phase'] == 'fit' else ('development_report', 'candidate_predictions', 'query_scores')
    need(operation in permitted and type(payload) is dict, 'phase tool operation')
    keys(payload, ('rows',) if operation == 'training_predictions' else ())
    if operation == 'training_predictions':
        rows = payload['rows']; need(type(rows) is list and 0 < len(rows) <= 200 and len(rows) == len(set(rows))
                                    and all(type(x) is int and 0 <= x < 16540 for x in rows), 'original requested train rows')
    if seal is not None:
        need({'provider': provider, 'operation': operation} in seal['method']['inference_action_policy']['broker_actions'], 'FIT-sealed tool permission')
    guard(ctx['work_end']); result = ctx['broker'].request(provider, operation, payload); guard(ctx['work_end'])
    need(type(result) is dict, 'actual tool result')
    if operation == 'development_report':
        keys(result, ('reference_detail', 'selected_settings', 'outer_query_outcomes', 'purpose'))
        need(result['outer_query_outcomes'] is False and result['purpose'] == 'original nested training-only report', 'training-only tool report')
        summary = result
    else:
        expected = {'synthetic_eeg', 'training_or_current_view_only', 'query_fit'}
        if operation == 'query_scores': expected |= {'correlation_scores', 'independent_probabilities', 'assignment', 'temperature'}
        keys(result, expected); need(result['training_or_current_view_only'] is True and result['query_fit'] is False, 'same no-query-fit fixed tool')
        geometry = {'synthetic_eeg': [len(payload['rows']) if operation == 'training_predictions' else 200, 1700]}
        if operation == 'query_scores': geometry.update(correlation_scores=[200, 200], independent_probabilities=[200, 200])
        summary = {'operation': operation, 'arrays': {}}
        for name, shape in geometry.items():
            a = result[name]; keys(a, ('encoding', 'dtype', 'shape', 'bytes', 'data'))
            n = shape_extent('<f8', shape, 8388608)
            need(a['encoding'] == 'base64' and a['dtype'] == '<f8' and a['shape'] == shape and type(a['bytes']) is int and a['bytes'] == n and type(a['data']) is str, 'exact fixed tool geometry')
            need(len(a['data']) == 4 * ((n + 2) // 3), 'bounded base64 envelope before decode')
            raw = base64.b64decode(a['data'], validate=True); need(len(raw) == n, 'complete tool body')
            values = struct.iter_unpack('<d', raw)
            need(all(math.isfinite(v[0]) and (name != 'independent_probabilities' or 0 <= v[0] <= 1) for v in values), 'finite actual tool values')
            summary['arrays'][name] = {'shape': shape, 'bytes': n, 'sha256': sha(raw)}
        if operation == 'query_scores':
            need(type(result['temperature']) in (float, int) and math.isfinite(result['temperature']) and result['temperature'] > 0, 'finite actual temperature')
            need(type(result['assignment']) is list and len(result['assignment']) == 200
                 and set(result['assignment']) == set(ctx['case']['candidate_ids']), 'whole tool assignment')
    raw = encoded(result); need(len(raw) <= 8388608, 'complete actual tool result cap')
    path = Path(ctx['scratch']) / ('tool-%04d.json' % len(ctx['tools']))
    pin = write_new(path, raw, 8388608); ctx['tools'].append({'path': str(path), 'operation': operation, **pin})
    ctx['records'].append({'kind': 'tool', 'provider': provider, 'operation': operation, 'payload': payload, 'result': pin})
    workspace_inventory(ctx['scratch'], spec)
    return summary


def dialogue(ctx, observation, history):
    spec = ctx['spec']; guard(ctx['work_end'])
    need(len(operations(ctx)) + spec['limits']['decision_bytes'] + 65536 <= 8388608,
         'reserve complete operation evidence before another model effect')
    history.append({'role': 'user', 'content': encoded(observation).decode()})
    need(len(history) <= 128 and len(encoded(history)) <= spec['limits']['context_bytes'], 'whole retained dialogue fits selected context')
    result = ctx['broker'].request(spec['model_provider'], 'generate', {'messages': history, 'max_new_tokens': spec['max_new_tokens']})
    guard(ctx['work_end']); keys(result, ('text',)); need(type(result['text']) is str, 'actual model text')
    need(len(result['text'].encode()) <= spec['limits']['decision_bytes'], 'actual model decision extent')
    ctx['records'].append({'kind': 'model_text', 'provider': spec['model_provider'], 'text': result['text'], 'sha256': sha(result['text'].encode())})
    history.append({'role': 'assistant', 'content': result['text']})
    return result['text']


def analysis_request(ctx, state):
    return {'schema': 'neural055-i-analysis-request-v1', 'phase': ctx['phase'], 'cell': ctx['cell'],
            'input': ctx['input'], 'state': state, 'tools': list(ctx['tools']),
            'original_work_deadline': ctx['work_end'], 'no_query_fit': ctx['phase'] == 'infer'}


def analysis_contract(phase):
    common = {'argv': 'python -I -B analysis.py --request REQUEST.json --result RESULT.json',
              'request_schema': 'neural055-i-analysis-request-v1',
              'request_fields': ['phase', 'cell', 'input', 'state', 'tools', 'original_work_deadline', 'no_query_fit', 'artifact_root'],
              'input_and_state': 'Only original mounted phase input and explicitly passed same-cell typed state. Never pickle.',
              'observation': 'A bounded JSON value reflecting the actual permitted analysis.',
              'no_semantic_approval': 'Declared method and operation records require independent review.'}
    if phase == 'fit':
        common['result'] = {'schema': 'neural055-i-fit-analysis-v1', 'fields': ['observation', 'state', 'inference_actions', 'selected_method', 'context'],
                            'state': 'List of {name,dtype,shape,path}; path exactly artifacts/NAME.raw, finite C-order raw data with dtype in <f8,<f4,<i8,<i4,<u8,<u4,|u1.',
                            'inference_actions': 'Nonempty list of {name,source} frozen at FIT. Same --request/--result analysis CLI.',
                            'selected_method': 'Exact /input/SELECTED_METHOD_SCHEMA.json, same full cell. Declare actual rows/people, selection and exact future broker pairs, including model generate.',
                            'context': 'Bounded training-derived JSON context needed at INFER; no future query access.'}
    else:
        common['result'] = {'schema': 'neural055-i-infer-analysis-v1', 'fields': ['observation', 'prediction'],
                            'prediction': 'Literal artifacts/prediction.json containing complete original 200x200 prediction and bijection. No state mutation or query fitting.'}
    return common


def investigate_fit(ctx):
    history = []; observation = {'instructions': ctx['spec']['fit_prompt'], 'cell': ctx['cell'], 'input': ctx['input'],
                                'decision_kinds': ['analysis', 'tool', 'finish_fit'], 'analysis_contract': analysis_contract('fit')}
    last = None; bad = 0
    for _ in range(ctx['spec']['phase_steps']['fit']):
        text = dialogue(ctx, observation, history)
        try:
            action = decode_decision(text, 'fit', ctx['spec'])
        except (Refusal, ValueError, UnicodeError, RecursionError) as exc:
            bad += 1; need(bad <= ctx['spec']['malformed_repair_slots'], 'selected parser repairs exhausted')
            ctx['records'].append({'kind': 'malformed_decision', 'error': type(exc).__name__})
            observation = {'parser_error': str(exc)[:512]}; continue
        if action['kind'] == 'tool':
            observation = tool_action(action, ctx); continue
        if action['kind'] == 'analysis':
            result, job = execute_analysis(action['source'], analysis_request(ctx, [] if last is None else last['state']), ctx)
            last = admit_fit_result(result, job, ctx)
            observation = {'actual_analysis_observation': result['observation'], 'state': [{k: r[k] for k in ('name', 'dtype', 'shape', 'bytes', 'sha256')} for r in last['state']], 'sealed_actions': sorted(last['actions'])}
            continue
        need(last is not None, 'finish_fit requires actual successful training analysis')
        last['fit_history_sha256'] = sha(encoded(history))
        return last
    raise Refusal('FIT decision count exhausted without completion')


def seal_header(fitted, ctx):
    return {'schema': 'neural055-i-typed-seal-v1', 'cell': ctx['cell'], 'source_sha256': ctx['source_sha256'],
            'loop_spec_sha256': sha(encoded(ctx['spec'])), 'method': fitted['method'], 'actions': fitted['actions'],
            'context': fitted['context'], 'fit_history_sha256': fitted['fit_history_sha256'],
            'state': [{k: r[k] for k in ('name', 'dtype', 'shape', 'bytes', 'sha256')} for r in fitted['state']]}


def write_seal(path, fitted, ctx):
    header = seal_header(fitted, ctx); meta = encoded(header); lim = ctx['spec']['limits']
    need(len(meta) <= lim['seal_header_bytes'], 'selected seal header cap')
    total = len(MAGIC) + 8 + len(meta) + sum(r['bytes'] for r in fitted['state'])
    need(total <= lim['seal_bytes'], 'whole typed seal cap')
    path = Path(path); temp = path.with_name(path.name + '.partial'); need(not path.exists() and not path.is_symlink(), 'fresh model output')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600); whole = hashlib.sha256(); count = 0
    def put(b):
        nonlocal count
        offset = 0
        while offset < len(b):
            guard(ctx['work_end']); n = os.write(fd, memoryview(b)[offset:]); need(n > 0, 'seal write progress'); whole.update(b[offset:offset+n]); offset += n; count += n
    try:
        put(MAGIC + struct.pack('<Q', len(meta)) + meta)
        for row in fitted['state']:
            need(array_pin(row['path'], row['dtype'], row['shape'], ctx) == {k: row[k] for k in ('dtype', 'shape', 'bytes', 'sha256', 'path')}, 'unchanged training state before seal')
            original = ordinary(row['path']); source = os.open(row['path'], os.O_RDONLY | os.O_NOFOLLOW); h = hashlib.sha256(); n = 0
            try:
                while n < row['bytes']:
                    b = os.read(source, min(65536, row['bytes'] - n)); need(bool(b), 'complete seal state copy'); h.update(b); n += len(b); put(b)
                need(h.hexdigest() == row['sha256'] and identity(os.fstat(source)) == identity(original) == identity(Path(row['path']).lstat()), 'exact stable seal source')
            finally:
                os.close(source)
        need(count == total, 'complete seal bytes'); os.fchmod(fd, 0o444); os.fsync(fd)
    finally:
        os.close(fd)
    os.link(temp, path, follow_symlinks=False); temp.unlink()
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)
    return {'bytes': count, 'sha256': whole.hexdigest()}


def read_seal(path, ctx):
    lim = ctx['spec']['limits']; before = ordinary(path); need(0 < before.st_size <= lim['seal_bytes'], 'bounded same-cell seal')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW); count = 0
    def take(n):
        nonlocal count
        out = bytearray()
        while len(out) < n:
            guard(ctx['work_end']); b = os.read(fd, n - len(out)); need(bool(b), 'complete typed seal'); out.extend(b); count += len(b)
        return bytes(out)
    try:
        need(identity(os.fstat(fd)) == identity(before), 'same sealed file handle')
        need(take(len(MAGIC)) == MAGIC, 'typed seal magic'); n = struct.unpack('<Q', take(8))[0]
        need(0 < n <= lim['seal_header_bytes'], 'typed header extent before allocation'); header = parse(take(n), lim['seal_header_bytes'])
        keys(header, ('schema', 'cell', 'source_sha256', 'loop_spec_sha256', 'method', 'actions', 'context', 'fit_history_sha256', 'state'))
        need(header['schema'] == 'neural055-i-typed-seal-v1' and header['cell'] == ctx['cell']
             and header['source_sha256'] == ctx['source_sha256'] and header['loop_spec_sha256'] == sha(encoded(ctx['spec'])), 'same cell/source/system seal')
        method(header['method'], ctx['cell'], ctx['spec'])
        need(type(header['actions']) is dict and 0 < len(header['actions']) <= lim['sealed_action_count'], 'finite sealed action map')
        need(all(type(k) is str and NAME.fullmatch(k) and type(v) is str and 0 < len(v.encode()) <= lim['analysis_source_bytes'] for k, v in header['actions'].items()), 'sealed executable action extent')
        need(len(encoded(header['context'])) <= lim['context_bytes'] and type(header['fit_history_sha256']) is str and re.fullmatch('[0-9a-f]{64}', header['fit_history_sha256']), 'training context provenance')
        need(type(header['state']) is list and len(header['state']) <= lim['state_count'], 'finite sealed state')
        seen = set(); state = []; total = 0
        for row in header['state']:
            keys(row, ('name', 'dtype', 'shape', 'bytes', 'sha256')); name = row['name']
            need(type(name) is str and NAME.fullmatch(name) and name not in seen, 'unique sealed state'); seen.add(name)
            extent = shape_extent(row['dtype'], row['shape'], lim['artifact_bytes']); total += extent
            need(type(row['bytes']) is int and row['bytes'] == extent and total <= lim['artifact_bytes'], 'whole sealed state extent')
            need(type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'sealed array digest')
            target = Path(ctx['scratch']) / (name + '.raw'); out = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600); h = hashlib.sha256(); copied = 0
            try:
                while copied < extent:
                    b = take(min(65536, extent - copied)); h.update(b); copied += len(b); offset = 0
                    while offset < len(b):
                        k = os.write(out, memoryview(b)[offset:]); need(k > 0, 'state extraction write'); offset += k
                os.fchmod(out, 0o444); os.fsync(out)
            finally:
                os.close(out)
            need(h.hexdigest() == row['sha256'], 'exact extracted typed state')
            value = array_pin(target, row['dtype'], row['shape'], ctx); need(value['sha256'] == row['sha256'], 'finite same extracted array')
            state.append(dict(value, name=name)); workspace_inventory(ctx['scratch'], ctx['spec'])
        need(count == before.st_size and not os.read(fd, 1) and identity(os.fstat(fd)) == identity(before) == identity(Path(path).lstat()), 'whole unchanged seal, no trailing payload')
    finally:
        os.close(fd)
    header['state'] = state
    return header


def execute_sealed_inference(ctx, seal):
    history = []; observation = {'instructions': ctx['spec']['infer_prompt'], 'cell': ctx['cell'], 'input': ctx['input'],
                                'training_context': seal['context'], 'sealed_actions': sorted(seal['actions']),
                                'decision_kinds': ['sealed_analysis', 'tool', 'finish_infer'], 'analysis_contract': analysis_contract('infer')}
    last = None; bad = 0
    for _ in range(ctx['spec']['phase_steps']['infer']):
        text = dialogue(ctx, observation, history)
        try:
            action = decode_decision(text, 'infer', ctx['spec'])
        except (Refusal, ValueError, UnicodeError, RecursionError) as exc:
            bad += 1; need(bad <= ctx['spec']['malformed_repair_slots'], 'selected inference parser repairs exhausted')
            ctx['records'].append({'kind': 'malformed_decision', 'error': type(exc).__name__})
            observation = {'parser_error': str(exc)[:512]}; continue
        if action['kind'] == 'tool':
            observation = tool_action(action, ctx, seal); continue
        if action['kind'] == 'sealed_analysis':
            name = action['action']; need(name in seal['actions'], 'action was fixed during FIT')
            result, job = execute_analysis(seal['actions'][name], analysis_request(ctx, seal['state']), ctx)
            for row in seal['state']:
                need(array_pin(row['path'], row['dtype'], row['shape'], ctx) == {k: row[k] for k in ('dtype', 'shape', 'bytes', 'sha256', 'path')}, 'frozen inference state was not changed')
            keys(result, ('schema', 'observation', 'prediction'))
            need(result['schema'] == 'neural055-i-infer-analysis-v1' and result['prediction'] == 'artifacts/prediction.json', 'exact inference analysis result')
            raw = read(job / result['prediction'], 4194304); last = ctx['public']['decode_json'](raw)
            ctx['public']['validate_prediction'](ctx['case'], last, row_sum_abs_tolerance=ctx['spec']['row_sum_abs_tolerance'])
            need(len(encoded(result['observation'])) <= ctx['spec']['limits']['context_bytes'], 'bounded inference observation')
            observation = {'actual_analysis_observation': result['observation'], 'prediction_sha256': sha(raw)}
            continue
        need(last is not None, 'finish_infer requires actual complete admitted prediction')
        return last
    raise Refusal('INFER decision count exhausted without completion')


def operations(ctx, error=None):
    value = {'schema': 'neural055-participant-operations-v3', 'cell': ctx['cell'], 'phase': ctx['phase'],
             'records': ctx['records'], 'first_error': None if error is None else {'type': type(error).__name__, 'message': str(error)[:1024]}}
    return encoded(value)


def runtime_context(phase, input_path):
    spec = validate_spec(SPEC); validate_interface(PARTICIPANT_INTERFACE)
    need(input_path == ('/input/train.json' if phase == 'fit' else '/input/query.json'), 'literal mounted phase input')
    cell = parse(read('/input/CELL.json', 1048576), 1048576); validate_cell(cell)
    host = parse(read('/input/HOST.json', 1048576), 1048576)
    need(host['schema'] == 'neural055-visible-native-profile-v3' and type(host['original_action_deadline']) in (int, float), 'original host clock')
    lease = parse(read('/broker/LEASE.json', 1048576), 1048576)
    need(lease['schema'] == 'neural055-visible-broker-lease-v3' and lease['cell'] == cell and lease['phase'] == phase.upper(), 'original same-cell phase lease')
    source_hash = sha(read(Path(__file__).absolute(), 131072)); need(lease['source_sha256'] == source_hash, 'same committed interpreter')
    providers = {spec['model_provider']} | ({spec['tool_provider']} if spec['tool_provider'] is not None else set())
    need(providers <= set(lease['providers']), 'precommitted actual services')
    deadline = min(host['original_action_deadline'], lease['deadline']); need(math.isfinite(deadline), 'finite original clock')
    work_end = deadline - spec['limits']['closure_seconds']; guard(work_end)
    for name, pin in PARTICIPANT_INTERFACE['documents'].items():
        raw = read('/input/' + name, pin['bytes']); need(len(raw) == pin['bytes'] and sha(raw) == pin['sha256'], 'exact complete public document: ' + name)
    public = runpy.run_path('/input/interface.py', run_name='_n055_public_transport')
    broker = runpy.run_path('/runtime/broker_client.py', run_name='_n055_original_client')['Broker']()
    need(broker.lease == lease, 'same captured broker lease')
    scratch = tempfile.mkdtemp(prefix='n055-i-', dir='/tmp')
    ctx = {'spec': spec, 'cell': cell, 'phase': phase, 'input': input_path, 'deadline': deadline,
           'work_end': work_end, 'source_sha256': source_hash, 'scratch': scratch, 'broker': broker,
           'public': public, 'tools': [], 'records': []}
    if phase == 'infer': ctx['case'] = public['validate_case'](public['decode_json'](read('/input/CASE.json', 4194304)))
    return ctx


def main(argv=None):
    p = argparse.ArgumentParser(allow_abbrev=False); sub = p.add_subparsers(dest='phase', required=True)
    fit = sub.add_parser('fit', allow_abbrev=False); fit.add_argument('--train', required=True); fit.add_argument('--model-output', required=True)
    infer = sub.add_parser('infer', allow_abbrev=False); infer.add_argument('--query', required=True); infer.add_argument('--model', required=True); infer.add_argument('--output', required=True)
    a = p.parse_args(argv)
    if a.phase == 'fit': need(a.model_output == '/output/model.bin', 'literal FIT output')
    else: need(a.model == '/model/model.bin' and a.output == '/output/prediction.json', 'literal INFER state/output')
    need(not list(Path('/output').iterdir()), 'fresh exact output namespace')
    ctx = runtime_context(a.phase, a.train if a.phase == 'fit' else a.query)
    try:
        if a.phase == 'fit':
            fitted = investigate_fit(ctx)
            ctx['records'].append({'kind': 'typed_training_seal', 'model': write_seal(a.model_output, fitted, ctx)})
            write_new('/output/selected_method.json', encoded(fitted['method']), 8388608)
        else:
            seal = read_seal(a.model, ctx); prediction = execute_sealed_inference(ctx, seal)
            write_new(a.output, encoded(prediction), 4194304)
        guard(ctx['work_end']); write_new('/output/operations.json', operations(ctx), 8388608)
        expected = {'model.bin', 'selected_method.json', 'operations.json'} if a.phase == 'fit' else {'prediction.json', 'operations.json'}
        need({x.name for x in Path('/output').iterdir()} == expected, 'complete exact original output namespace')
        return 0
    except BaseException as exc:
        if not Path('/output/operations.json').exists():
            try: write_new('/output/operations.json', operations(ctx, exc), 8388608)
            except BaseException as publication_error:
                try:
                    sys.stderr.write(json.dumps({'first_error': type(exc).__name__, 'operations_publication_error': type(publication_error).__name__}) + '\n')
                except BaseException:
                    pass  # Natural nonzero remains; unavailable streams are host-observed failures.
        raise


if __name__ == '__main__':
    raise SystemExit(main())
