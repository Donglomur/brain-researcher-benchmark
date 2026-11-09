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

CONTRACT = 'authoring/delivery-20261105/common/campaign-exposure-contract-v2-bounded-work'
CONTRACT_MANIFEST_SHA = '5311b8f382511198ba555225a0dbd7683b78701daebf518a60eb314e80ca85b6'
VALIDATOR = {'bytes': 18624, 'sha256': 'be7b0a71df0a9b7bf84f35652a6a21dd8ecd51c7d382f1faf321b7ce480453ef'}
REQUEST_CAP = 131072
CAPTURE_CAP = 4194304
WORK_CAP = 2097152


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


def view_capture(repo, path, cap, expected=None, *, view=None):
    if view is None:
        return capture(path, cap, expected)
    root, path = Path(repo).absolute(), Path(path).absolute()
    need(path.is_relative_to(root), 'capture confined to repository')
    key = path.relative_to(root).as_posix()
    need(relative_file(root, key) == path and Path(view.resolve(root, key)) == path, 'canonical trusted view')
    raw = view.capture(key, cap, expected)
    need(type(raw) is bytes and 0 < len(raw) <= cap, 'bounded trusted view capture')
    if expected is not None:
        need(pin(raw) == {k: expected[k] for k in ('bytes', 'sha256')}, 'exact trusted view pin')
    return raw


def validator(repo, *, view=None):
    here = Path(repo).absolute() / CONTRACT
    body = view_capture(repo, here / 'validate.py', 20000, VALIDATOR, view=view)
    module = types.ModuleType('_neurobench_captured_campaign_contract')
    module.__file__ = str(here / 'validate.py')
    if view is not None:
        module.__dict__['__builtins__'] = __builtins__
    exec(compile(body, module.__file__, 'exec'), module.__dict__)
    return module, here


def contract_metadata(repo, *, view=None):
    contract, here = validator(repo, view=view)
    reader = contract.Reader(CAPTURE_CAP, repo=repo, view=view)
    manifest, bodies, lock, declarations, manifest_pin = contract.load_source_bound(
        repo, here, CONTRACT_MANIFEST_SHA, reader)
    need(contract.POLICY['work_body_bytes'] == WORK_CAP
         and contract.POLICY['aggregate_bytes'] == CAPTURE_CAP == PREFERENCE_READ_CAP
         and contract.POLICY['validator_bytes'] == 20000
         and contract.POLICY['request_bytes'] == REQUEST_CAP, 'gate/source policy equality')
    return contract, manifest, bodies, lock, declarations, manifest_pin, reader


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
PREFERENCE_READ_CAP = 4194304


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


def _python_options(argv):
    need(type(argv) is list and 4 <= len(argv) <= 256
         and all(type(v) is str and '\0' not in v and len(v) <= 4096 for v in argv)
         and argv[0] in ('python3', '{python}'), 'registered Python launch')
    index, cache = 1, None
    if argv[1].startswith('-'):
        need(len(argv) >= 9 and argv[1:5] == ['-I', '-S', '-B', '-X']
             and argv[5].startswith('pycache_prefix='), 'unsupported Python interpreter options')
        prefix = argv[5][len('pycache_prefix='):]
        cache = Path(prefix)
        need(prefix.startswith('/') and '\\' not in prefix and '{' not in prefix and '}' not in prefix
             and all(v not in ('', '.', '..') for v in prefix.split('/')[1:])
             and cache.as_posix() == prefix, 'canonical absolute fresh pycache prefix')
        index = 6
    return index, cache


def python_source_launch(argv):
    """Registered structure only; runtime filesystem/environment unproved."""
    index, _ = _python_options(argv)
    wrapper = argv[index]
    relative_file(Path('.'), wrapper)
    need(not wrapper.startswith('-') and '{' not in wrapper and '}' not in wrapper
         and Path(wrapper).suffix == '.py', 'literal Python wrapper path')
    return index


def _require_fresh_cache(cache):
    need(not cache.exists() and not any(p.is_symlink() for p in (cache, *cache.parents))
         and all(not p.exists() or p.is_dir() for p in cache.parents), 'fresh ordinary pycache prefix')


def python_launch(argv):
    """Execution admission: structural parsing plus unconditional local freshness."""
    index = python_source_launch(argv)
    if index == 6:
        _require_fresh_cache(Path(argv[5][len('pycache_prefix='):]))
    return index


def runtime_environment(command):
    """Recheck on the executing process host immediately before its dispatch.

    This proves only the observed local cache predicates, not qualification,
    immutable namespace custody, or a future/cross-machine environment.
    """
    need(type(command) is list and command and command[0] == sys.executable,
         'actual selected Python interpreter')
    index, cache = _python_options(['python3', *command[1:]])
    need(Path(command[index]).is_absolute(), 'constructed absolute wrapper')
    if cache is not None:
        _require_fresh_cache(cache)
    return {'source_only': False, 'pycache_freshness_checked': cache is not None,
            'current_process_filesystem_only': True, 'runtime_qualification_granted': False}



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


def preferred_route(repo, task_id, action, condition, work_sha256, registered=None, *, view=None):
    """Source preference is a refusal boundary, never runtime authorization.

    Runtime filesystem freshness is never inferred from a source capture.
    The receipt governs program interfaces only. Artifact scorers and legacy
    tools are not silently redirected. Current declarations and routing are
    captured again before launch by the caller.
    """
    dispatch = context(task_id, action, condition)
    if action == 'score':
        return {'status': 'not_a_program_interface_selection', 'metadata_read_charge_bytes': 0,
                'runtime_authorization': False}
    repo = Path(repo).absolute()
    contract, manifest, bodies, lock, declarations, manifest_pin, source_reader = contract_metadata(repo, view=view)
    used = source_reader.used + VALIDATOR['bytes'] + 1
    need(used <= PREFERENCE_READ_CAP, 'contract bootstrap fits preference aggregate')
    captures = []
    def read(path, cap, expected=None):
        nonlocal used
        need(used + cap + 1 <= PREFERENCE_READ_CAP, 'preference capture reservation')
        raw = view_capture(repo, path, cap, expected, view=view)
        used += len(raw) + 1
        captures.append({'path':Path(path).relative_to(repo).as_posix(), **pin(raw), 'reservation_cap_bytes':cap + 1})
        return raw
    work_raw = read(repo / WORK, WORK_CAP)
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
                'runtime_authorization': False,
                'policy': pin(bodies['POLICY.json']), 'contract': manifest_pin,
                'source_capture_charge_bytes': source_reader.used,
                'validator_bootstrap_charge_bytes': VALIDATOR['bytes'] + 1,
                'trusted_view': view is not None,
                'pycache_freshness_checked': False,
                'runtime_environment_verified': False,
                'validation_scope': 'registered_source_only'}
    if task_id not in interfaces:
        return {**evidence, 'status': 'no_preferred_program_source_for_task',
                'metadata_read_charge_bytes': used, 'captures': captures}
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
    index = python_source_launch(argv)
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
            'metadata_read_charge_bytes': used, 'captures': captures}

def campaign_capacity_plan(repo, work_descriptor, *, view=None):
    """Authenticate source only; derive full admission capacity without targets."""
    repo = Path(repo).absolute()
    need(type(work_descriptor) is dict and set(work_descriptor) == {'path','bytes','sha256'}
         and work_descriptor['path'] == WORK
         and type(work_descriptor['bytes']) is int and 0 < work_descriptor['bytes'] <= WORK_CAP
         and type(work_descriptor['sha256']) is str
         and re.fullmatch('[a-f0-9]{64}', work_descriptor['sha256']), 'bounded proposed WORK descriptor')
    contract, manifest, bodies, lock, declarations, manifest_pin, reader = contract_metadata(repo, view=view)
    policy = contract.POLICY
    expected = {}
    def dependency(row, cap):
        need(type(row) is dict and set(row) == {'path','bytes','sha256'}, 'dependency descriptor')
        relative_file(repo, row['path'])
        need(type(row['bytes']) is int and 0 < row['bytes'] <= cap
             and type(row['sha256']) is str and re.fullmatch('[a-f0-9]{64}', row['sha256']),
             'bounded dependency descriptor')
        need(row['path'] not in expected, 'unique dependency path')
        expected[row['path']] = row
        return row['bytes'] + 1
    audit_cost = dependency(lock['audit'], policy['audit_bytes'])
    builder_cost = dependency(lock['builder'], policy['builder_bytes'])
    declarations_cost = 0
    need(type(declarations['tasks']) is dict and len(declarations['tasks']) <= 200, 'bounded declarations')
    for task, facts in sorted(declarations['tasks'].items()):
        declarations_cost += dependency(facts['selected_source'], policy['declaration_descriptor_bytes'])
        declarations_cost += dependency(facts['declaration'], policy['declaration_bytes'])
    dependencies = manifest['dependencies']
    need(type(dependencies) is list and len(dependencies) == len(expected)
         and len({x['path'] for x in dependencies}) == len(expected)
         and {x['path']:x for x in dependencies} == expected, 'complete exact dependency map')
    source_members = sum(row['bytes'] + 1 for row in manifest['files'])
    source_bound = policy['manifest_bytes'] + 1 + source_members
    terms = {'request': policy['request_bytes'] + 1, 'source_manifest_and_members': source_bound,
             'audit_descriptor_extent': audit_cost, 'builder_descriptor_extent': builder_cost,
             'maximum_WORK': policy['work_body_bytes'] + 1, 'all_declaration_pairs': declarations_cost}
    reader_floor = sum(terms.values())
    bootstrap = VALIDATOR['bytes'] + 1
    route_caps = [policy[k] for k in ('work_body_bytes','preference_bytes','source_bytes','registration_bytes','wrapper_bytes')]
    route_body_floor = sum(x + 1 for x in route_caps)
    route_floor = bootstrap + source_bound + route_body_floor
    need(reader_floor <= policy['aggregate_bytes'], 'complete exposure Reader capacity')
    need(route_floor <= policy['aggregate_bytes'], 'complete preferred-route capacity')
    # Every run caller performs two admissions and two preference checks.
    # Five helper captures occur along a qualified default/named command path.
    trace = {
        'admit_calls': 2, 'preferred_route_calls': 2, 'validator_bootstrap_captures': 4,
        'contract_source_passes': 4, 'gate_source_captures': 5,
        'condition_additional_base_captures': 1,
        'per_gate_or_base_source_capture_cap_bytes': 200000,
        'default_gate_source_upper_bytes': 5 * (200000 + 1),
        'named_additional_base_source_upper_bytes': 200000 + 1,
        'command_construction_separate': [
            'canonical/specification and complete registry scans',
            'qualification receipt/source binding/freeze and <=64 MiB qualified source closure',
            'registered wrapper recaptures, candidate/review/output/cache filesystem checks',
            'finish invocation <=65536 and receipt <=16384; final CLI serialization'],
        'scope': 'complete admission/preference read bound; not whole CLI CPU, parse memory, filesystem IO, or execution',
        'all_ordinary_filesystem_checks_still_required': True}
    two_pass = 2 * (reader_floor + bootstrap + route_floor)
    return {'schema':'campaign_capacity_plan_v2', 'source_only':True, 'admission_performed':False,
        'runtime_authorization':False, 'private_dependency_bodies_read':False,
        'policy': {'path':CONTRACT + '/POLICY.json', **pin(bodies['POLICY.json'])},
        'contract': {'path':CONTRACT + '/SOURCE_MANIFEST.json', **manifest_pin},
        'validator': {'path':CONTRACT + '/validate.py', **VALIDATOR},
        'limits':policy, 'WORK':work_descriptor,
        'construction_headroom_bytes':policy['construction_work_max_bytes'] - work_descriptor['bytes'],
        'construction_size_admitted': work_descriptor['bytes'] <= policy['construction_work_max_bytes'],
        'reader_terms_bytes':terms, 'reader_required_bytes':reader_floor,
        'preferred_capture_terms_bytes':[v + 1 for v in route_caps],
        'preferred_route_required_bytes':route_floor, 'validator_bootstrap_bytes':bootstrap,
        'two_pass_admission_preference_upper_bytes':two_pass, 'caller_trace':trace,
        'source_read_receipts':reader.receipts,
        'planner_actual_source_charge_bytes':reader.used + bootstrap,
        'planner_validator_capture': {'path':CONTRACT + '/validate.py', **VALIDATOR, 'reserved_bytes':bootstrap},
        'logical_metadata_live_upper_bytes':2 * policy['aggregate_bytes'] + policy['report_bytes'],
        'live_bound_scope':'logical captured input/output bytes only; parsed Python/RSS separately provisioned',
        'logical_canonical_output_cap_bytes':policy['report_bytes'],
        'logical_retained_input_cap_bytes':policy['aggregate_bytes'],
        'work_bound_scope':'finite read/capture cardinalities above; no wall-clock or CPU qualification',
        'dependency_descriptors':list(expected.values())}
