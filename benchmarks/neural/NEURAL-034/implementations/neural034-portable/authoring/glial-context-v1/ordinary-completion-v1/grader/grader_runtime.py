"""Finite host-lifecycle adaptation of the exact frozen NEURAL-034 scorer.

The frozen grader worker, source/asset pins, public-first validation, numerical
calculations and 4 GiB / 2 CPU profile remain in the held run_child source.
Only trusted standard-library host source is loaded in this private namespace.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PACKAGE = ROOT / 'benchmarks/neuroscience/neural-034'
FROZEN_SCORE_PIN = {'bytes': 17590, 'sha256': '82787ea36072a24e21c65ff1088a4238f6126ea43a46ba1949a2635bdeed81bc'}
FROZEN_SOURCE_PINS = {
    'execution_pins.json': {'bytes': 567, 'sha256': 'ba53c99cd74ec2a3cec63f26efe1a1057c6ee44acb4beeee17b7b6bb2a68ec48'},
    'grader.py': {'bytes': 6091, 'sha256': 'e48954a3b0e6ab44fbe4ad393b2716a31151bd8c2362e472bc0fef99bee2b5e6'},
    'operator_assets.json': {'bytes': 732, 'sha256': 'bab6b3fc10d6acdc0227e4c48c835d8d37bb5d9c089c2715ba77969d23010e23'},
}
FILE_CAPS = {
    'outer_intent.json': 16384, 'child_ownership.json': 16384,
    'invocation.json': 16384, 'ownership.json': 65536,
    'create_attempt.json': 16384, 'create_result.json': 32768,
    'inspection.json': 150000, 'terminal_inspection.json': 150000,
    'child_receipt.json': 300000, 'cleanup-00.json': 300000,
    'cleanup-01.json': 300000, 'cleanup-02.json': 300000, 'score.json': 150000,
}
TOTAL_BYTES = sum(FILE_CAPS.values())
ENTRY_CAP = len(FILE_CAPS) + 1  # One operator directory and these fixed files.
_HELD = None


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def read(path, cap):
    path = Path(path)
    need(path.is_absolute() and all(not p.is_symlink() for p in (path, *path.parents)),
         'Literal unlinked grader metadata path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded ordinary grader metadata')
        body = os.read(fd, cap + 1)
        after, linked = os.fstat(fd), path.lstat()
        keys = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(linked, k)
             for k in keys), 'Stable complete grader metadata')
        return body
    finally:
        os.close(fd)


def decode(body):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            need(key not in value, 'Duplicate grader metadata key')
            value[key] = item
        return value
    value = json.loads(body, object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite grader metadata')))
    need(type(value) is dict, 'Object grader metadata')
    return value


def metadata(path):
    return decode(read(path, FILE_CAPS[Path(path).name]))


def write(path, value):
    """Exclusive bounded write; file and directory are durable before dispatch."""
    path = Path(path)
    need(path.name in FILE_CAPS, 'Only fixed grader journal names')
    root = path.parent.parent if path.parent.name == 'operator' else path.parent
    need(all(not p.is_symlink() for p in (root, *root.parents)), 'Unlinked grader output root')
    used = 0
    for item in root.rglob('*'):
        info = item.lstat()
        need(not item.is_symlink(), 'Unlinked grader output entry')
        if stat.S_ISREG(info.st_mode):
            need(info.st_nlink == 1 and item.name in FILE_CAPS and info.st_size <= FILE_CAPS[item.name],
                 'Bounded fixed grader output file')
            used += info.st_size
        else:
            need(item == root / 'operator' and stat.S_ISDIR(info.st_mode), 'Only grader operator directory')
    body = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    need(len(body) <= FILE_CAPS[path.name] and used + len(body) <= TOTAL_BYTES and not path.exists(),
         'Bounded exclusive grader journal')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(body); stream.flush(); os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def identifier(result):
    need(type(result) is dict and type(result.get('returncode')) is int
         and result['returncode'] == 0 and result.get('stderr') == ''
         and type(result.get('stdout')) is str and re.fullmatch(r'[a-f0-9]{64}\n?', result['stdout']) is not None,
         'Successful create returned exactly one immutable container ID')
    return result['stdout'].rstrip('\n')


def valid_name(name):
    need(type(name) is str and re.fullmatch(r'neural034-score-[a-f0-9]{16}', name) is not None,
         'Exact owned grader container name')


def ownership(run, name):
    valid_name(name)
    owned_raw = read(run / 'ownership.json', FILE_CAPS['ownership.json'])
    owned = decode(owned_raw); attempt = metadata(run / 'create_attempt.json')
    need(owned.get('container') == name and owned.get('intent_before_create') is True
         and attempt.get('container') == name and attempt.get('create_attempted') is True
         and attempt.get('ownership_pin') == pin(owned_raw), 'Exact durable attempted-create ownership')
    returned = metadata(run / 'create_result.json')
    need(returned.get('container') == name and returned.get('create_returned') is True,
         'Durable exact create return before inspection')
    return identifier(returned['result'])


def compact(result):
    if len(result.get('stdout', '').encode()) + len(result.get('stderr', '').encode()) <= 16384:
        return result
    return {'returncode': result['returncode'], 'oversized_cli_output_retained_as_pins': True,
            **{key + '_pin': pin(result[key].encode()) for key in ('stdout', 'stderr')}}


def cleanup(run, name, deadline):
    """Remove only the durable created ID, then prove ID and name absence separately."""
    run = Path(run)
    result = {'name': name, 'absent': False, 'absence_verified': False,
              'immutable_id': None, 'create_extent_unknown': True}
    try:
        created_id = ownership(run, name)
        result.update(immutable_id=created_id, create_extent_unknown=False)
    except Exception as error:
        result['ownership_error'] = repr(error)[:2000]
    if result['immutable_id'] is not None:
        held = scorer(); created_id = result['immutable_id']
        try:
            result['remove'] = compact(held.docker(['rm', '--force', created_id], min(deadline, time.monotonic() + 1.5)))
        except Exception as error:
            result['remove_error'] = repr(error)[:2000]
        absent_rows = {}
        for key, target in (('id', created_id), ('name', name)):
            try:
                observed = held.docker(['inspect', '--type', 'container', target], deadline)
                absent_rows[key] = held.absent(observed, target)
                result[key + '_inspect'] = compact(observed)
            except Exception as error:
                absent_rows[key] = False; result[key + '_inspect_error'] = repr(error)[:2000]
        result['id_absent'] = absent_rows['id']; result['name_absent'] = absent_rows['name']
        result['absent'] = result['absence_verified'] = all(absent_rows.values())
    slots = [run / ('cleanup-%02d.json' % index) for index in range(3)]
    available = [path for path in slots if not path.exists()]
    need(available, 'Finite grader cleanup journal slots exhausted')
    write(available[0], result)
    return result


def verify(held_verify, info, name, mounts, environment):
    held_verify(info, name, mounts, environment)
    state, host = info['State'], info['HostConfig']
    need('OomKillDisable' in host and
         (host['OomKillDisable'] is None or host['OomKillDisable'] is False),
         'Present OOM setting; only literal null or false accepted')
    need(state['Running'] is False and state['OOMKilled'] is False and state['Pid'] == 0,
         'Strict stopped prestart grader state')


def terminal(info, created_id, name, returncode):
    state = info['State']
    need(info['Id'] == created_id and info['Name'] == '/' + name and info['Image'] == scorer().IMAGE
         and state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0
         and state['OOMKilled'] is False and state['ExitCode'] == returncode,
         'Exact immutable stopped grader and returned exit identity')


RUN_CHILD_SUBSTITUTIONS = [
    ('for dst, src in mounts.items():', 'for dst, src in sorted(mounts.items()):', 1),
    ("        owned = True\n        created = docker(args, work); evidence['create'] = created\n        need(created['returncode'] == 0, 'container create failed')\n        inspected = docker(['inspect', '--type', 'container', name], work)",
     "        write(run/'create_attempt.json', {'container': name, 'create_attempted': True,\n"
     "              'ownership_pin': lock(run/'ownership.json')})\n"
     "        owned = True\n"
     "        created = docker(args, work)\n"
     "        write(run/'create_result.json', {'container': name, 'create_returned': True, 'result': created})\n"
     "        created_id = identifier(created); evidence['created_id'] = created_id\n"
     "        evidence['create'] = created\n"
     "        inspected = docker(['inspect', '--type', 'container', created_id], work)", 1),
    ("        info = json.loads(inspected['stdout'])[0]\n        write(run/'inspection.json', info)",
     "        inspected_rows = json.loads(inspected['stdout'])\n"
     "        need(type(inspected_rows) is list and len(inspected_rows) == 1, 'One created grader inspection')\n"
     "        info = inspected_rows[0]\n"
     "        need(info['Id'] == created_id, 'Create stdout and inspected immutable ID agree')\n"
     "        write(run/'inspection.json', info)", 1),
    ("outcome = docker(['start', '--attach', name], work)",
     "outcome = docker(['start', '--attach', created_id], work)", 1),
    ("        report = json.loads(outcome['stdout'])",
     "        stopped = docker(['inspect', '--type', 'container', created_id], work)\n"
     "        need(stopped['returncode'] == 0, 'Stopped grader inspection returned')\n"
     "        stopped_rows = json.loads(stopped['stdout'])\n"
     "        need(type(stopped_rows) is list and len(stopped_rows) == 1, 'One stopped grader inspection')\n"
     "        terminal(stopped_rows[0], created_id, name, outcome['returncode'])\n"
     "        write(run/'terminal_inspection.json', stopped_rows[0])\n"
     "        report = json.loads(outcome['stdout'])", 1),
    ("cleanup(name, start+8.5)", "cleanup(run, name, start+8.5)", 1),
]


def scorer():
    global _HELD
    if _HELD is not None:
        return _HELD
    source = read(PACKAGE / 'score.py', FROZEN_SCORE_PIN['bytes'])
    need(pin(source) == FROZEN_SCORE_PIN, 'Exact frozen scorer source before private loading')
    for filename, expected in FROZEN_SOURCE_PINS.items():
        need(pin(read(PACKAGE / filename, expected['bytes'])) == expected,
             'Unchanged frozen grader worker and source/asset registries')
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run_child']
    need(len(functions) == 1, 'One exact frozen run_child function')
    body = ast.get_source_segment(source.decode(), functions[0])
    for before, after, count in RUN_CHILD_SUBSTITUTIONS:
        need(body.count(before) == count, 'Exact finite grader lifecycle substitution')
        body = body.replace(before, after)
    name = '_neural034_ordinary_completion_frozen_grader'
    need(name not in sys.modules, 'Fresh private grader namespace')
    held = types.ModuleType(name); held.__file__ = str(PACKAGE / 'score.py')
    sys.modules[name] = held
    exec(compile(source, held.__file__, 'exec'), held.__dict__)
    held_verify = held.verify
    held.write = write; held.cleanup = cleanup; held.identifier = identifier; held.terminal = terminal
    held.verify = lambda info, name, mounts, environment: verify(held_verify, info, name, mounts, environment)
    exec(compile(body, held.__file__ + '::ordinary-completion-run_child', 'exec'), held.__dict__)
    _HELD = held
    return held
