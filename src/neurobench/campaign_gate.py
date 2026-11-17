"""Mandatory declared-exposure gate for the two operator execution CLIs.

No candidate/data/scientific code is imported. Successful admission does not
attest history or replace the registered task's independent runtime admission.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

CONTRACT = 'authoring/delivery-20261105/common/campaign-exposure-contract-v1'
CONTRACT_MANIFEST_SHA = '4b3ba488a6e808558f83fa38486ef52dd773260ce5198726e063e1c836915757'
VALIDATOR = {'bytes': 15638, 'sha256': 'dc9fc898bcb94a2e15a510bd206a3caeb03d29aed434541e70973a16ccf056bb'}
REQUEST_CAP = 131072
CAPTURE_CAP = 1500000


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def capture(path, limit, expected=None):
    p = Path(path).absolute()
    need('..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)), 'ordinary campaign metadata path')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= limit, 'bounded campaign metadata')
        if expected is not None:
            need(a.st_size == expected['bytes'], 'campaign metadata extent')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(a.st_size + 1)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
        b, c = os.fstat(fd), p.lstat()
        need(len(raw) == a.st_size and all(getattr(a, k) == getattr(b, k) == getattr(c, k) for k in fields), 'stable campaign capture')
        if expected is not None:
            need(pin(raw) == expected, 'campaign metadata pin')
        return raw
    finally:
        os.close(fd)


def validator(repo):
    here = Path(repo) / CONTRACT
    body = capture(here / 'validate.py', 20000, VALIDATOR)
    module = types.ModuleType('_neurobench_captured_campaign_contract')
    module.__file__ = str(here / 'validate.py')
    exec(compile(body, module.__file__, 'exec'), module.__dict__)
    return module, here


def context(task_id, action, condition):
    need(type(task_id) is str and 0 < len(task_id) <= 128, 'one task ID')
    need(action in ('run', 'score'), 'execution action')
    need(condition is None or type(condition) is str and 0 < len(condition) <= 128, 'literal condition')
    need(action != 'score' or condition is None, 'score has no information condition')
    return {'task_id': task_id, 'action': action, 'condition': condition}


def admit(repo, task_id, action, condition, request_path, request_sha256, work_sha256):
    """Called before command construction and again directly before dispatch."""
    dispatch = context(task_id, action, condition)
    need(request_path is not None, 'explicit operator campaign request required')
    for value in (request_sha256, work_sha256):
        need(type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None, 'explicit current request and WORK hashes required')
    repo = Path(repo).absolute()
    need(repo.is_dir() and not any(x.is_symlink() for x in (repo, *repo.parents)), 'ordinary repository')
    contract, here = validator(repo)
    reader = contract.Reader(CAPTURE_CAP)
    raw = reader.read(request_path, REQUEST_CAP)
    need(pin(raw)['sha256'] == request_sha256, 'exact operator request hash')
    envelope = contract.parse(raw)
    need(type(envelope) is dict and set(envelope) == {'schema', 'context_id', 'dispatch', 'campaign'}
         and envelope['schema'] == 'campaign_dispatch_request_v1', 'dispatch request schema')
    ident = envelope['context_id']
    need(type(ident) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}', ident), 'bounded declared context ID')
    need(envelope['dispatch'] == dispatch, 'campaign request must bind this exact task, action and condition')
    request = envelope['campaign']
    relevant = contract.references(request)
    need(sum(row['task_id'] == task_id for row in request['evaluations']) == 1, 'dispatched task must be an admitted evaluation, not just a reference')
    audit, declarations, evidence, lock = contract.load_bound(
        repo, here, CONTRACT_MANIFEST_SHA, work_sha256, reader, relevant)
    need(len(raw) <= lock['request_cap_bytes'], 'contract request bound')
    decision = contract.assess(request, audit, declarations)
    need(decision['accepted'] is True and decision['status'] == 'compatible_development_selection'
         and all(row['accepted'] is True for row in decision['decisions']), 'campaign exposure claims unresolved, contradicted or forbidden')
    need(sum(row['task_id'] == task_id and row['accepted'] is True for row in decision['decisions']) == 1, 'exact target decision')
    return {'schema': 'campaign_dispatch_admission_v1', 'dispatch': dispatch, 'context_id': ident,
            'request': pin(raw), 'evidence': evidence, 'decision': pin(encode(decision)),
            'declared_history_only': True, 'history_independently_verified': False,
            'input_mount_authorization': False, 'runtime_authorization': False,
            'metadata_read_charge_bytes': reader.used + VALIDATOR['bytes'] + 1}


def finish(first, second, command, cwd):
    """Bind the freshly repeated admission to exactly the argv about to launch."""
    need(type(command) is list and 2 <= len(command) <= 256
         and all(type(x) is str and '\0' not in x for x in command), 'literal bounded parsed argv')
    need(type(cwd) in (str, Path) or isinstance(cwd, Path), 'literal working directory')
    need({k: v for k, v in first.items() if k != 'metadata_read_charge_bytes'}
         == {k: v for k, v in second.items() if k != 'metadata_read_charge_bytes'}, 'campaign authority changed during command construction')
    route = second.get('preferred_program_route', {})
    if route.get('status') == 'preferred_source_bound':
        expected = route['registered_argv']
        index = route['wrapper_index']
        need(len(command) == len(expected) and command[0] == sys.executable
             and command[index] == route['wrapper_absolute'] and command[1:index] == expected[1:index]
             and str(cwd) == route['working_directory_absolute'],
             'constructed command differs from admitted preferred wrapper')
        for actual, template in zip(command[index + 1:], expected[index + 1:]):
            if template not in ('{program}', '{output}', '{review}', '{other_reserve_bytes}'):
                need(actual == template, 'constructed command differs from admitted preferred arguments')
        python_launch(expected)
    invocation = encode({'argv': command, 'working_directory': str(cwd)})
    need(len(invocation) <= 65536, 'bounded dispatch identity')
    receipt = {**second, 'invocation': pin(invocation),
               'metadata_read_charge_bytes': first['metadata_read_charge_bytes'] + second['metadata_read_charge_bytes'],
               'current_request_and_work_rechecked_before_launch': True}
    need(len(encode(receipt)) <= 16384, 'bounded admission receipt')
    return receipt


WORK = 'authoring/delivery-20261105/WORK_ASSIGNMENTS.json'
PREFERENCE_READ_CAP = 2000000


def metadata(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'duplicate preference metadata key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: need(False, 'nonfinite preference metadata'))


def relative_file(repo, relative):
    need(type(relative) is str and 0 < len(relative) <= 4096 and '\\' not in relative
         and not relative.startswith('/') and all(v not in ('', '.', '..') for v in relative.split('/')),
         'confined preference metadata path')
    return repo / relative


def python_launch(argv):
    """Only legacy script argv or the exact isolated/no-site fresh-cache form.

    This recognizes a registered launch, not arbitrary Python option syntax.
    A task's argument schema, runtime qualification and external observer still
    govern admission. No interpreter is launched or inferred from a pathname.
    """
    need(type(argv) is list and 4 <= len(argv) <= 256
         and all(type(v) is str and '\0' not in v and len(v) <= 4096 for v in argv)
         and argv[0] in ('python3', '{python}'), 'registered Python launch')
    index = 1
    if argv[1].startswith('-'):
        need(len(argv) >= 9 and argv[1:5] == ['-I', '-S', '-B', '-X']
             and argv[5].startswith('pycache_prefix='), 'unsupported Python interpreter options')
        prefix = argv[5][len('pycache_prefix='):]
        cache = Path(prefix)
        need(prefix.startswith('/') and '\\' not in prefix and '{' not in prefix and '}' not in prefix
             and all(v not in ('', '.', '..') for v in prefix.split('/')[1:])
             and cache.as_posix() == prefix, 'canonical absolute fresh pycache prefix')
        need(not cache.exists() and not any(p.is_symlink() for p in (cache, *cache.parents))
             and all(not p.exists() or p.is_dir() for p in cache.parents), 'fresh ordinary pycache prefix')
        index = 6
    wrapper = argv[index]
    relative_file(Path('.'), wrapper)
    need(not wrapper.startswith('-') and '{' not in wrapper and '}' not in wrapper
         and Path(wrapper).suffix == '.py', 'literal Python wrapper path')
    return index


def source_wrapper_pin(source_doc, local, repository_relative):
    """Join one wrapper per inventory; identical cross-inventory pins may repeat.

    Both inventories can intentionally describe the same source file. Repeated
    rows within one inventory and contradictory cross-inventory pins refuse.
    Local and repository-relative names retain exact path matching.
    """
    need(type(source_doc) is dict, 'preferred source manifest object')
    matches = []
    for key in ('files', 'runtime_files'):
        inventory = source_doc.get(key, [])
        need(type(inventory) in (list, dict) and len(inventory) <= 512,
             'bounded preferred source inventory')
        inventory_matches = []
        rows = inventory.items() if type(inventory) is dict else ((None, row) for row in inventory)
        for map_path, row in rows:
            need(type(row) is dict, 'preferred source inventory row')
            paths = [v for v in (map_path, row.get('path'), row.get('name')) if v is not None]
            need(paths and all(v == paths[0] for v in paths), 'unambiguous source member identity')
            relative_file(Path('.'), paths[0])
            if paths[0] in (local, repository_relative):
                inventory_matches.append(descriptor({'path': paths[0], 'bytes': row.get('bytes'), 'sha256': row.get('sha256')}))
        need(len(inventory_matches) <= 1, 'at most one preferred wrapper per source inventory')
        matches.extend(inventory_matches)
    need(matches and all(value == matches[0] for value in matches),
         'one consistent preferred wrapper source descriptor')
    return matches[0]


def descriptor(value):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'exact preferred source descriptor')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= 262144
         and type(value['sha256']) is str and re.fullmatch('[a-f0-9]{64}', value['sha256']),
         'bounded preferred source descriptor')
    return {k: value[k] for k in ('bytes', 'sha256')}


def preferred_route(repo, task_id, action, condition, work_sha256, registered=None):
    """Source preference is a refusal boundary, never runtime authorization.

    The receipt governs program interfaces only. Artifact scorers and legacy
    tools are not silently redirected. Current declarations and routing are
    captured again before launch by the caller.
    """
    dispatch = context(task_id, action, condition)
    if action == 'score':
        return {'status': 'not_a_program_interface_selection', 'metadata_read_charge_bytes': 0,
                'runtime_authorization': False}
    repo = Path(repo).absolute()
    used = 0
    def read(path, cap, expected=None):
        nonlocal used
        need(used + cap <= PREFERENCE_READ_CAP, 'preference capture reservation')
        raw = capture(path, cap, expected)
        used += len(raw) + 1
        return raw
    work_raw = read(repo / WORK, 1000000)
    need(pin(work_raw)['sha256'] == work_sha256, 'current WORK preference identity')
    work = metadata(work_raw)
    selected = work.get('latest_construction_state', {}).get('latest_program_source_selection')
    receipt_pin = descriptor(selected)
    receipt_raw = read(relative_file(repo, selected['path']), receipt_pin['bytes'], receipt_pin)
    receipt = metadata(receipt_raw)
    need(type(receipt) is dict and receipt.get('schema') == 'root_reviewed_program_source_preference_v1',
         'current program preference receipt schema')
    interfaces = receipt.get('selected_source_interfaces')
    need(type(interfaces) is dict and len(interfaces) <= 200, 'bounded preferred interface map')
    evidence = {'dispatch': dispatch, 'work': pin(work_raw),
                'preference_receipt': {'path': selected['path'], **pin(receipt_raw)},
                'runtime_authorization': False}
    if task_id not in interfaces:
        return {**evidence, 'status': 'no_preferred_program_source_for_task',
                'metadata_read_charge_bytes': used}
    preferred = interfaces[task_id]
    need(type(preferred) is dict and type(preferred.get('path')) is str, 'preferred interface path')
    directory = relative_file(repo, preferred['path'])
    source = preferred.get('source'); source_pin = descriptor(source)
    source_path = relative_file(repo, source['path'])
    need(source_path.parent == directory, 'preferred source manifest belongs to interface')
    source_raw = read(source_path, source_pin['bytes'], source_pin)
    source_doc = metadata(source_raw)
    message = ('Preferred reviewed program interface: ' + preferred['path']
               + '; central route is absent or stale. Register and independently qualify this exact interface; no launch.')
    need(isinstance(registered, tuple) and len(registered) == 2, message)
    registration, supplied = registered
    registration = Path(registration).absolute()
    need(registration.parent.parent == repo / 'benchmarks/neuroscience'
         and registration.name == 'manifest.json', 'central registration location')
    registration_raw = read(registration, 131072)
    doc = metadata(registration_raw)
    need(doc == supplied and doc.get('id') == task_id, 'captured actual central registration')
    meta = doc.get('program_execution')
    if condition is not None:
        options = doc.get('program_conditions', {})
        need(type(options) is dict and condition in options, message)
        meta = options[condition]
        if meta == 'default':
            meta = doc.get('program_execution')
    binding = {'path': preferred['path'], 'source': source}
    need(type(meta) is dict and meta.get('preferred_source_interface') == binding, message)
    entry = meta.get('entrypoint', {})
    argv = entry.get('argv')
    index = python_launch(argv)
    need(entry.get('working_directory') == '.', message)
    wrapper = relative_file(repo, argv[index])
    need(wrapper.is_relative_to(directory) and wrapper != source_path and wrapper.suffix == '.py', message)
    local = wrapper.relative_to(directory).as_posix()
    wrapper_pin = source_wrapper_pin(source_doc, local, argv[index])
    need(wrapper_pin['sha256'] == entry.get('sha256'), message)
    read(wrapper, wrapper_pin['bytes'], wrapper_pin)
    return {**evidence, 'status': 'preferred_source_bound', 'interface': binding,
            'registration': {'path': registration.relative_to(repo).as_posix(), **pin(registration_raw)},
            'wrapper_absolute': str(wrapper), 'wrapper': wrapper_pin, 'registered_argv': argv,
            'wrapper_index': index, 'working_directory_absolute': str(repo),
            'existing_runtime_qualification_still_required': True,
            'metadata_read_charge_bytes': used}
