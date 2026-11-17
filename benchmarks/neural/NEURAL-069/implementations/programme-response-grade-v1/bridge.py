"""Original complete producer custody, public admission, and unchanged response score."""
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
NUMERICAL = ('io_contract', 'numerical_core', 'score')
DONOR = 'authoring/delivery-20261105/neural069/program-transport-v1'
ADAPTER = 'authoring/delivery-20261105/common/next-three-registrations-v1/neural069'
BINDING = {'bytes': 36627, 'sha256': '4bcaaa8054b0de76e7e48575fb9968f2fa0aa1c84cd6f57e1167994a94bd5f5f'}
ROSTER = {'bytes': 1022157, 'sha256': '45ce81fde0ec94dcc52b2aee97141f7b956b435f11e87dd26852ea35b0d24880'}
CUSTODY_BYTES = 32 * 1024**2
OUTPUT_CAP = 14328960
WRITE_LIMIT = None
WRITTEN = 0


class CandidateInvalid(ValueError):
    """Original public candidate refusal; never an operator packet fault."""
    def __init__(self, error):
        super().__init__(str(error))
        self.result = {'task_id': 'NEURAL-069', 'status': 'invalid_submission',
                       'score': None, 'reason': str(error)}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def parse(raw):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


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
        if expected is not None:
            need(before.st_size == expected['bytes'], 'Exact extent before body read')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(before.st_size + 1)
        after, named = os.fstat(fd), value.lstat()
        keys = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k)
                                              for k in keys), 'Stable captured bytes')
        need(expected is None or pin(raw) == expected, 'Exact captured pin')
        return raw
    finally:
        os.close(fd)


def save(value, raw, mode=0o400):
    global WRITTEN
    if WRITE_LIMIT is not None:
        need(WRITTEN + len(raw) <= WRITE_LIMIT, 'Preventive cumulative outer write allocation')
    # Failed attempts remain charged; no deletion or retry resets this counter.
    WRITTEN += len(raw)
    value = path(value)
    fd = os.open(value, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(value.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return pin(raw)


def module(name, filename, raw):
    value = types.ModuleType(name)
    value.__file__ = str(filename)
    value.__package__ = name.rpartition('.')[0]
    exec(compile(raw, str(filename), 'exec'), value.__dict__)
    return value


def source(expected):
    root = HERE.parents[4]
    value = parse(read(HERE / 'SOURCE.json', 65536, expected))
    need(value['schema'] == 'neural069_programme_response_source_v1', 'Exact source version')
    captured = {}
    for name, identity in value['files'].items():
        member = Path(name)
        need(not member.is_absolute() and '..' not in member.parts, 'Repository-relative source member')
        captured[str(root / member)] = read(root / member, 1048576, identity)
    return value, captured


def original(captured):
    root = HERE / 'recovered'
    donor, adapter = root / DONOR, root / ADAPTER
    for directory, key, count in ((donor, 'runtime_files', 7), (adapter, 'files', 5)):
        manifest = parse(captured[str(directory / 'SOURCE_MANIFEST.json')])
        need(len(manifest[key]) == count, 'Complete original source closure')
        for name, identity in manifest[key].items():
            need(pin(captured[str(directory / name)]) == identity, 'Unchanged original member')
    a = module('neural069_original_adapter', adapter / 'run_program.py', captured[str(adapter / 'run_program.py')])
    child = module('neural069_original_child', donor / 'child.py', captured[str(donor / 'child.py')])
    # This unchanged supervisor bootstrap reauthenticates runtime.py itself.
    supervisor = module('neural069_original_supervisor', donor / 'supervise.py', captured[str(donor / 'supervise.py')])
    lock = parse(captured[str(donor / 'LOCK.json')])
    need(len(lock['public_files']) == 101 and len(lock['cases']) == 80 and lock['output_count'] == 81,
         'Complete original panel')
    return a, child, supervisor, lock


def natural(record):
    need(record['natural_exit'] is True and record['process_reaped'] is True
         and record['streams_closed'] is True and record['timed_out'] is False
         and record['kill_sent'] is False and type(record['exit_code']) is int and record['exit_code'] == 0
         and record['error_type'] is None, 'Actually observed natural zero, reaped leader and closed streams')


def admit_producer(original_modules, prepared, terminal_raw, process_record):
    a, child, supervisor, lock = original_modules
    natural(process_record)
    terminal = parse(terminal_raw)
    need(set(terminal) == {'schema', 'status', 'original_host_exit', 'review', 'outputs',
                           'external_natural_zero_required', 'scientific_qualification'}
         and terminal['schema'] == 'neural069_review_bound_terminal_v1'
         and terminal['status'] == 'closed' and terminal['review'] == prepared['review_pin']
         and terminal['outputs'] == 81 and terminal['external_natural_zero_required'] is True
         and terminal['scientific_qualification'] is False, 'Exact original adapter terminal')
    review = prepared['review']
    submission = supervisor.admit_closed(Path(review['output']), terminal['original_host_exit'],
                                         Path(review['commit']['path']), review['commit']['metadata'], a.DONOR_PIN)
    receipt = parse(read(Path(review['output']) / 'HOST_EXIT.json', 40000, terminal['original_host_exit']))
    a.validate_return({'status': 'closed', 'receipt': terminal['original_host_exit'], 'outputs': 81,
                       'worker_natural_exit': True}, receipt, prepared)
    rows = receipt['outputs']
    need(len(rows) == 81 and rows[0]['path'] == 'submission.json'
         and len({row['path'] for row in rows}) == 81, 'Complete unique original output pins')
    outputs = {row['path']: {k: row[k] for k in ('bytes', 'sha256')} for row in rows}
    need(sum(p['bytes'] for p in outputs.values()) <= OUTPUT_CAP, 'Original complete output cap')
    return {'submission': str(submission), 'outputs': outputs, 'host_exit': terminal['original_host_exit'],
            'review': prepared['review_pin'], 'process': process_record, 'packet': review['package'], 'docker_socket': review['docker_socket'],
            'scientific_qualification': False, 'descendant_absence_not_certified': True}


@contextmanager
def numerical_modules(directory, identities):
    need(set(identities) == set(NUMERICAL), 'Complete current numerical source')
    directory = Path(directory)
    bodies = {name: read(directory / (name + '.py'), 1048576, identities[name]) for name in NUMERICAL}
    old = {name: sys.modules.get(name) for name in NUMERICAL}
    old_path = sys.path[:]
    loaded = {}
    try:
        for name in NUMERICAL:
            loaded[name] = module(name, directory / (name + '.py'), bodies[name])
            sys.modules[name] = loaded[name]
        yield loaded
    finally:
        sys.path[:] = old_path
        for name, value in old.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


@contextmanager
def capture_outputs(modules, submission, outputs):
    """Bind exact bytes returned at both unchanged original capture boundaries."""
    score, io = modules['score'], modules['io_contract']
    need(len(outputs) == 81 and 'submission.json' in outputs, 'Exactly 81 stopped artifacts')
    need(sum(p['bytes'] for p in outputs.values()) <= OUTPUT_CAP, 'Original output extent cap')
    old_submission, old_array = score.capture_regular, io._capture
    captured = {}
    def admit(name, raw, digest):
        if name not in outputs or pin(raw) != outputs[name] or digest != outputs[name]['sha256']:
            raise io.IOContractError('Actual captured bytes differ from stopped-producer pin')
        if name in captured:
            raise io.IOContractError('Repeated prediction capture')
        captured[name] = raw
    def submission_capture(value, *args, **kwargs):
        raw, digest = old_submission(value, *args, **kwargs)
        if Path(value) == Path(submission):
            admit('submission.json', raw, digest)
        return raw, digest
    def array_capture(value, *args, **kwargs):
        raw, digest = old_array(value, *args, **kwargs)
        if kwargs.get('dir_fd') is not None:
            admit(str(value), raw, digest)
        return raw, digest
    score.capture_regular, io._capture = submission_capture, array_capture
    try:
        yield captured
    finally:
        score.capture_regular, io._capture = old_submission, old_array


def validate_public(modules, packet, binding_sha256, submission, outputs):
    """No target path/stat/body or provider is used in this stage."""
    score, io = modules['score'], modules['io_contract']
    contract = score.read_contract(packet, binding_sha256)  # binding and public roster metadata only
    try:
        with capture_outputs(modules, submission, outputs) as captured:
            raw, digest = score.capture_regular(submission, 100000)
            value = io.strict_json(raw)
            if (type(value) is not dict or set(value) != {'task_id', 'roster_sha256', 'predictions'}
                    or value['task_id'] != 'NEURAL-069' or value['roster_sha256'] != contract['roster_sha256']):
                raise io.IOContractError('exact task and roster identity required')
            admitted = io.validate_prediction_files(Path(submission).parent, value['predictions'], contract['shapes'],
                         max_total_bytes=sum(8 * math.prod(s) + 16396 for s in contract['shapes'].values()))
            need(len(admitted['arrays']) == 80 and set(captured) == set(outputs), 'Complete captured public panel')
    except (io.IOContractError, OSError) as error:
        raise CandidateInvalid(error) from error
    return contract, captured


def publish_public(directory, contract, captured, outputs):
    """Write only already validated bytes; never recapture candidate paths here."""
    need(set(captured) == set(outputs) and len(captured) == 81
         and all(pin(raw) == outputs[name] for name, raw in captured.items()), 'Complete validated custody input')
    need(sum(map(len, captured.values())) <= OUTPUT_CAP, 'Bounded original complete snapshot')
    directory = path(directory)
    need(not directory.exists() and directory.parent.is_dir(), 'Fresh operator-owned custody directory')
    directory.mkdir(mode=0o700)
    for name, raw in captured.items():
        need(Path(name).name == name and name not in ('.', '..'), 'Ordinary custody basename')
        save(directory / name, raw, 0o444)
    completed = {'schema': 'neural069_validated_public_custody_v1', 'outputs': outputs,
                 'binding_sha256': contract['binding_sha256'], 'roster_sha256': contract['roster_sha256'],
                 'complete_cases': 80, 'participants': 10, 'query_videos': 102,
                 'private_target_files_accessed': False, 'candidate_code_executed': False}
    save(directory / 'VALIDATED.json', encode(completed))
    directory.chmod(0o500)
    return completed


def bound_score(modules, packet, binding_sha256, submission, outputs, *, loader=None):
    score = modules['score']
    original_loader = score.load_targets if loader is None else loader
    with capture_outputs(modules, submission, outputs) as captured:
        def target_loader(contract):
            need(set(captured) == set(outputs) and len(captured) == 81,
                 'All exact captured candidate bytes validated before numerical target loader')
            return original_loader(contract)
        result = score.grade(submission, packet, binding_sha256, loader=target_loader)
    result['producer_custody'] = {'outputs': outputs, 'captured_count': len(captured),
                                'complete_capture': set(captured) == set(outputs),
                                'scientific_qualification': False}
    if result['status'] in ('scored', 'undefined_required_support'):
        need(result['submission_sha256'] == outputs['submission.json']['sha256']
             and result['producer_custody']['complete_capture'], 'Scored bytes bind stopped producer')
    return result


def transport(captured):
    directory = HERE.parents[2] / 'NEURAL-007/implementations/whole-night-programme/program/vendor_transport'
    package_name = 'neural069_trusted_grade_transport'
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
