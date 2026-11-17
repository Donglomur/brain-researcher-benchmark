"""Pinned original producer admission and capture-bound, unchanged numerical score."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

HERE = Path(__file__).resolve().parent
NUMERICAL = ('interface', 'encoding_core', 'data_io', 'report_contract', 'grade', 'run')


def need(value, message):
    if not value:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def parse(body):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    return json.loads(body, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def path(value):
    value = Path(os.path.abspath(value))
    need(not any(p.is_symlink() for p in (value, *value.parents)), 'No linked path or parent')
    return value


def read(value, cap, expected=None):
    value = path(value)
    fd = os.open(value, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded ordinary single-link file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(cap + 1)
        after, named = os.fstat(fd), value.lstat()
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k)
                                              for k in fields), 'Stable complete captured file')
        need(expected is None or pin(raw) == expected, 'Exact captured content pin')
        return raw
    finally:
        os.close(fd)


def save(value, body):
    value = path(value)
    fd = os.open(value, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(value.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return pin(body)


def module(name, filename, body, **bindings):
    value = types.ModuleType(name)
    value.__file__ = str(filename)
    value.__package__ = name.rpartition('.')[0]
    value.__dict__.update(bindings)
    exec(compile(body, str(filename), 'exec'), value.__dict__)
    return value


def source(expected):
    root = HERE.parents[4]
    body = read(HERE / 'SOURCE.json', 65536, expected)
    value = parse(body)
    need(value['schema'] == 'neural052_full_panel_bridge_source_v1', 'Exact bridge source version')
    captured = {}
    for relative, identity in value['files'].items():
        member = Path(relative)
        need(not member.is_absolute() and '..' not in member.parts, 'Repository-relative source')
        captured[str(root / member)] = read(root / member, 1048576, identity)
    return value, captured


def original(captured):
    directory = HERE / 'producer'
    bodies = {Path(name).name: body for name, body in captured.items() if Path(name).parent == directory}
    manifest = parse(bodies['SOURCE_MANIFEST.json'])
    need(manifest['schema'] == 'neural052_full3_program_source_v1' and len(manifest['files']) == 13,
         'Complete original producer closure')
    for name, expected in manifest['files'].items():
        need(pin(bodies[name]) == expected, 'Unchanged original producer member')
    common = module('neural052_recovered_common', directory / 'common.py', bodies['common.py'])
    policy = common.module(bodies, 'policy.py', directory, c=common)
    observer = common.module(bodies, 'observe.py', directory)
    process = common.module(bodies, 'process.py', directory)
    binding = parse(bodies['BINDINGS.json'])
    public = [r for r in binding['files'] if r['visibility'] == 'public']
    need(len(public) == 14 and sum(r['bytes'] for r in public) == 71207593,
         'Original complete public fourteen-member panel')
    return common, policy, observer, process, binding, pin(bodies['SOURCE_MANIFEST.json'])


def natural(record):
    need(record['natural_exit'] is True and type(record['exit_code']) is int and record['exit_code'] == 0
         and record['process_reaped'] is True and record['process_group_absent'] is True
         and record['streams_closed'] is True and record['timed_out'] is False
         and record['kill_sent'] is False and record['error_type'] is None,
         'Actually observed natural zero and closed process group')


def admit_producer(common, observer, binding, selection, selection_pin, legacy_source,
                   external, external_pin, process_record, deadline):
    natural(process_record)
    receipt = parse(read(external, 8192, external_pin))
    need(receipt['schema'] == 'neural052_full3_external_v1' and receipt['status'] == 'complete_unqualified'
         and receipt['source'] == legacy_source and receipt['selection'] == selection_pin
         and receipt['attempt'] == selection['output'] and receipt['error_type'] is None
         and receipt['full3_source_scope'] is True and receipt['scientific_qualified'] is False
         and receipt['runtime_qualified'] is False and receipt['numerical_grading_performed'] is False
         and receipt['nested_cli_and_native_recovery_may_be_required'] is False,
         'Exact original ungraded external observation')
    natural(receipt['child'])
    root = path(selection['output'])
    terminal = {'schema': 'neural052_full3_worker_v1', 'status': 'complete_unqualified',
                'source': legacy_source, 'scope': binding['scope'], 'complete': receipt['complete']}
    used = 0
    def charge(n):
        nonlocal used
        used += n
        need(used <= 16000000 and time.monotonic() < deadline, 'Bounded original closure recheck')
    outputs, complete = observer.admit(common, root, terminal, legacy_source, binding, deadline, charge)
    need(outputs == receipt['outputs'], 'Observed and replayed original paired-output identity')
    return {'root': str(root), 'outputs': outputs, 'complete': complete,
            'external': external_pin, 'process': process_record, 'closure_recheck_bytes': used,
            'package': str(path(selection['repository']) / binding['package']), 'scope': binding['scope']}


@contextmanager
def numerical_modules(directory, identities):
    """Execute captured original source; restore all temporary import bindings."""
    need(set(identities) == set(NUMERICAL), 'Complete unchanged numerical source closure')
    bodies = {name: read(Path(directory) / (name + '.py'), 1048576, identities[name]) for name in NUMERICAL}
    previous = {name: sys.modules.get(name) for name in NUMERICAL}
    loaded = {}
    try:
        for name in NUMERICAL:
            loaded[name] = module(name, Path(directory) / (name + '.py'), bodies[name])
            sys.modules[name] = loaded[name]
        yield loaded
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def bound_score(modules, packet_root, result_path, methods_path, outputs):
    """Bind the bytes the original scorer actually captures before reference work."""
    need(set(outputs) == {'result.json', 'METHODS.md'}, 'Both stopped participant artifacts')
    runner, grade, interface = modules['run'], modules['grade'], modules['interface']
    original_methods, original_result = runner.capture_regular, grade.capture_regular
    observed = {'result.json': False, 'METHODS.md': False}
    def methods_capture(value, *args, **kwargs):
        body = original_methods(value, *args, **kwargs)
        if Path(value) == Path(methods_path):
            if pin(body) != outputs['METHODS.md']:
                raise interface.Invalid('METHODS capture differs from stopped-producer commitment')
            observed['METHODS.md'] = True
        return body
    def result_capture(value, *args, **kwargs):
        body = original_result(value, *args, **kwargs)
        if Path(value) == Path(result_path):
            if pin(body) != outputs['result.json']:
                raise interface.Invalid('Result capture differs from stopped-producer commitment')
            observed['result.json'] = True
        return body
    runner.capture_regular, grade.capture_regular = methods_capture, result_capture
    try:
        score = runner.score(Path(packet_root), Path(result_path), Path(methods_path))
    finally:
        runner.capture_regular, grade.capture_regular = original_methods, original_result
    if score['status'] == 'scored':
        need(all(observed.values()) and score['submission_sha256'] == outputs['result.json']['sha256']
             and {k: score['methods'][k] for k in ('bytes', 'sha256')} == outputs['METHODS.md'],
             'Scientific score must bind both exact captured artifacts')
    score['producer_custody'] = {'expected_outputs': outputs, 'exact_capture_observed': observed,
                                'prose_quality_scored': False, 'scientific_qualification': False}
    return score


def transport(captured):
    directory = HERE.parents[2] / 'NEURAL-007/implementations/whole-night-programme/program/vendor_transport'
    package_name = 'neural052_trusted_grade_transport'
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package
    loaded = {}
    for name in ('engine', 'bounds', 'archive', 'contract', 'provider'):
        filename = directory / (name + '.py')
        key = package_name + '.' + name
        loaded[name] = module(key, filename, captured[str(filename)])
        sys.modules[key] = loaded[name]
        setattr(package, name, loaded[name])
    return loaded['provider'].Provider, loaded['bounds'].mount_identity, directory
