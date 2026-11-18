"""Private source successor for a prospective, ungraded NEURAL-095 frozen pair.

Assembly returns bytes only. It neither writes a deployment nor issues a request.
COLLECTION_SOURCE must be supplied as already captured, externally pinned bytes.
Closed-output validation is read-only and never calls native recovery or scoring.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types

Q = 'authoring/delivery-20261105/common/remaining-builds-wave40'
BASE = Q + '/dmfc-complete-four-cell-owner-source-20261115-v1'
GATE = Q + '/dmfc-external-candidate-admission-source-20261115-v1'
MODE = 'frozen_pair_ungraded/v1'
VIEWS = ('cue_only', 'neural')
CONTEXTS = tuple('frozen_program__' + v for v in VIEWS)
POLICY = 'single_frozen_fit_batch/v1'
CONFIGURE_PIN = {'bytes': 13187, 'sha256': 'f6d94662cba01373ffec136c71b354952e806edab4915a14adad604f9aee90f9'}
MANIFEST_PIN = {'bytes': 12343, 'sha256': '1c99da5b2c48aa98e233461c76232ac434b302fb364bd545239293df2e7ed082'}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def decode(body):
    def unique(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'duplicate metadata key'); out[key] = value
        return out
    return json.loads(body, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite metadata')))


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def capture(path, cap=1048576):
    p = Path(path).absolute()
    need('..' not in p.parts and all(not x.is_symlink() for x in (p, *p.parents)), 'ordinary unlinked path')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap, 'bounded regular single-link bytes')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            body = f.read(a.st_size + 1)
        b = os.fstat(fd)
        need(len(body) == a.st_size and all(getattr(a, k) == getattr(b, k) for k in
             ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'stable captured bytes')
        return body
    finally:
        os.close(fd)


def checked(root, descriptor, cap=1048576):
    need(type(descriptor) is dict and set(descriptor) == {'path', 'bytes', 'sha256'}, 'exact descriptor')
    name = descriptor['path']
    need(type(name) is str and not Path(name).is_absolute() and Path(name).as_posix() == name
         and '..' not in Path(name).parts, 'relative descriptor')
    body = capture(Path(root) / name, cap)
    need(pin(body) == {k: descriptor[k] for k in ('bytes', 'sha256')}, 'selected captured bytes')
    return body


def module(name, filename, body, injected=None):
    value = types.ModuleType(name); value.__file__ = str(filename)
    value.__dict__.update(injected or {})
    exec(compile(body, str(filename), 'exec'), value.__dict__)
    return value


def replace(body, old, new, count=1):
    text = body.decode()
    need(text.count(old) == count, 'exact reviewed source seam: ' + old[:80])
    return text.replace(old, new).encode()


def _review(c, bodies, program, method, review, base_freeze):
    """Use the original review procedure on only the three captured operands."""
    paths = {'program': BASE + '/frozen-candidate/program.py',
             'method': BASE + '/frozen-candidate/METHOD.json',
             'review': BASE + '/frozen-candidate/REVIEW.json'}
    selected = {paths[k]: b for k, b in (('program', program), ('method', method), ('review', review))}
    def bounded(root, descriptor, cap=262144):
        body = selected.get(descriptor['path'], bodies.get(descriptor['path']))
        need(type(body) is bytes and 0 < len(body) <= cap and
             pin(body) == {k: descriptor[k] for k in ('bytes', 'sha256')}, 'captured review operand')
        return body
    reader_path = 'authoring/dmfc-timing/paired-program-cli-v1/admission.py'
    reader = module('_frozen_method_reader', reader_path, bodies[reader_path],
                    {'json': json, 'need': need, 'decode': decode})
    gate_path = GATE + '/candidate_admission.py'
    gate = module('_frozen_review_gate', gate_path, bodies[gate_path])
    s = types.SimpleNamespace(root=Path('/'), c=types.SimpleNamespace(checked=bounded, decode=decode),
        base=base_freeze, read_method=reader.read_method, fields=reader.METHOD_FIELDS)
    reviewed = gate.review_candidate(s, {'path': paths['review'], **pin(review)})
    need(reviewed['program'] == {'path': paths['program'], **pin(program)} and
         reviewed['method'] == {'path': paths['method'], **pin(method)},
         'reviewed numerical/method operands equal selected captured bytes')
    return paths


def assemble(implementations_root, operator, destination, *, program, method, review, expected,
             collection_source=None):
    """Return the complete proposed source deployment in memory, without authority."""
    source = collection_source if collection_source is not None else globals().get('COLLECTION_SOURCE')
    need(type(source) is bytes and 0 < len(source) <= 65536, 'externally selected captured collection source required')
    package = Path(implementations_root).absolute() / 'neural-095-four-cell-runner'
    helper = capture(package / 'configure.py')
    manifest_body = capture(package / 'SOURCE_MANIFEST.json')
    need(pin(helper) == CONFIGURE_PIN and pin(manifest_body) == MANIFEST_PIN,
         'immutable original source templates')
    marker = '    # All validation/rendering happens before the one fresh destination is created.\n'
    text = helper.decode(); start = text.index(marker); end = text.index('\n\ndef main(', start)
    text = text[:start] + "    return {'bodies': bodies, 'payload': payload, 'deployment': prepared}\n" + text[end:]
    c = module('_frozen_original_configure', package / 'configure.py', text.encode())
    original_capture = c.capture
    c.capture = lambda path, cap=262144: (manifest_body if Path(path) == package / 'SOURCE_MANIFEST.json'
                                         else original_capture(path, cap))
    for name, body, cap in (('program', program, 65536), ('method', method, 32768), ('review', review, 32768)):
        need(type(body) is bytes and 0 < len(body) <= cap and pin(body) == expected[name], 'selected ' + name)
    need(set(expected) == {'program', 'method', 'review'}, 'exact three selected operands')
    result = c.configure(operator, destination, package)
    bodies, payload = result['bodies'], result['payload']
    original = dict(bodies)
    freeze_path = BASE + '/SOURCE_FREEZE.json'; freeze = decode(bodies[freeze_path])
    paths = _review(c, bodies, program, method, review, freeze)
    for key, body in (('program', program), ('method', method), ('review', review)):
        bodies[paths[key]] = body
    conf = BASE + '/configuration.py'
    bodies[conf] = c.assignment(c.assignment(bodies[conf], 'CONTEXTS', CONTEXTS), 'MODES', ('frozen_program',))
    for old, new in (('dmfc-complete-four-cell-config/v1', 'dmfc-frozen-pair-ungraded-config/v1'),
                     ('dmfc-complete-four-cell-source/v1', 'dmfc-frozen-pair-ungraded-source/v1')):
        bodies[conf] = replace(bodies[conf], old, new)
    bodies[conf] = replace(bodies[conf], 'all four isolated actor contexts', 'both isolated frozen actor contexts')
    bodies[conf] = replace(bodies[conf], "value['repository_root'] == str(ROOT),", 
        "value['repository_root'] == str(ROOT) and value.get('collection_mode') == 'frozen_pair_ungraded/v1',")
    bodies[conf] = replace(bodies[conf], "freeze['execution_authority'] is False,",
        "freeze['execution_authority'] is False and freeze.get('collection_mode') == 'frozen_pair_ungraded/v1',")
    controller = BASE + '/controller.py'
    text = bodies[controller].decode()
    start = text.index('    sources = {mode:'); end = text.index('    return study, backends, budget', start)
    text = text[:start] + '''    source = stack.captured_sources[values['actor']['arms']['frozen_program__cue_only']['program']['path']]
    def seal(pair):
        stack.entrypoint.durable(out / 'FROZEN_PAIR.json', pair, budget)
        return api.digest(api.encode(pair))
    study = stack.frozen_collection.FrozenPairCollection(api=api, source=source,
        method=config.method_source, case_ids=ids, limits=limits, reservations=reservations,
        tool_ids=tuple(tools), backend_factory=backend_factory,
        comparison_id=config.request_sha256, seal=seal)
''' + text[end:]
    bodies[controller] = text.encode()
    bodies[controller] = replace(bodies[controller], 'max_units=46', 'max_units=6')
    bodies[controller] = replace(bodies[controller], 'dmfc-complete-four-cell-controller-result/v1', 'dmfc-frozen-pair-ungraded-controller-result/v1')
    bodies[controller] = replace(bodies[controller], 'four_cell_outputs_scored', 'frozen_pair_outputs_collected_ungraded', 3)
    owner = BASE + '/operation_owner.py'
    bodies[owner] = c.assignment(bodies[owner], 'CELL_KEYS', CONTEXTS)
    for old, new, count in (
        ('dmfc-complete-four-cell-root-request/v1', 'dmfc-frozen-pair-ungraded-root-request/v1', 1),
        ('admit_one_complete_dmfc_four_cell_operation', 'admit_one_complete_dmfc_frozen_pair_ungraded_operation', 1),
        ('dmfc-complete-four-cell-capacity/v1', 'dmfc-frozen-pair-ungraded-capacity/v1', 1),
        ('dmfc-complete-four-cell-outer-result/v1', 'dmfc-frozen-pair-ungraded-outer-result/v1', 1),
        ('dmfc-complete-four-cell-controller-result/v1', 'dmfc-frozen-pair-ungraded-controller-result/v1', 1),
        ('four_cell_outputs_scored', 'frozen_pair_outputs_collected_ungraded', 2),
        ('complete_four_cell_operation', 'complete_frozen_pair_ungraded_operation', 1),
        ('len(folders) <= 46', 'len(folders) <= 6', 1),
        ("14 <= units.get('unit_count', 0) <= 46", "units.get('unit_count', 0) == 6", 1)):
        bodies[owner] = replace(bodies[owner], old, new, count)
    entry = BASE + '/entrypoint.py'
    bodies[entry] = replace(bodies[entry], "'controller', 'entrypoint')", "'controller', 'entrypoint', 'frozen_collection')")
    bodies[entry] = replace(bodies[entry], 'complete_four_cell_operation', 'complete_frozen_pair_ungraded_operation')
    # MAX_UNITS remains the unchanged transport's conservative maximum46;
    # this specific controller and owner impose the tighter exact6 limit.
    profile_path = BASE + '/OPERATION_PROFILE.json'; profile = decode(bodies[profile_path])
    profile.update(schema='dmfc-frozen-pair-ungraded-operation-profile/v1', cells=list(CONTEXTS),
                   maximum_numerical_units=6, reference_count=0)
    bodies[profile_path] = encode(profile)
    collection_path = BASE + '/frozen_collection.py'; bodies[collection_path] = source
    payload.update(schema='dmfc-frozen-pair-ungraded-config/v1', collection_mode=MODE,
                   numerical_tool={'path': paths['program'], **pin(program)},
                   method={'path': paths['method'], **pin(method)},
                   candidate_review={'path': paths['review'], **pin(review)})
    payload['actor']['arms'] = {k: payload['actor']['arms'][k] for k in CONTEXTS}
    for key, arm in payload['actor']['arms'].items():
        name = arm['config']['path']
        bodies[name] = encode({'schema': 'dmfc-offline-reference/v1', 'mode': key,
            'tool_id': 'dmfc_predict@' + pin(program)['sha256'], 'policy': POLICY})
        arm['config'] = {'path': name, **pin(bodies[name])}
    files = set(freeze['files'])
    files -= {BASE + '/actor-configs/' + k + '.json' for k in
              ('case_adaptive__cue_only', 'case_adaptive__neural')}
    files.update(paths.values()); files.add(collection_path)
    freeze.update(schema='dmfc-frozen-pair-ungraded-source/v1', collection_mode=MODE)
    freeze['modules']['frozen_collection'] = collection_path
    freeze['scientific_scope'].update(modes=['frozen_program'], maximum_numerical_units=6,
        reference_count=5, protected_reference_reads=0, gradings_in_collection=0,
        grading='deferred_to_separate_cross_access_adapter')
    freeze['files'] = {n: pin(bodies[n]) for n in sorted(files)}
    freeze['entrypoint'] = {'path': entry, **pin(bodies[entry])}
    bodies[freeze_path] = encode(freeze)
    payload['successor_freeze'] = {'path': freeze_path, **pin(bodies[freeze_path])}
    for name in (conf, controller, owner, entry, collection_path):
        ast.parse(bodies[name], filename=name)
    need(bodies[BASE + '/adaptive_producer.py'] == original[BASE + '/adaptive_producer.py']
         and bodies[BASE + '/actor_backend.py'] == original[BASE + '/actor_backend.py']
         and bodies[BASE + '/offline_actor.py'] == original[BASE + '/offline_actor.py'], 'unchanged actual cell/actor mechanisms')
    bodies['CONFIGURATION_PAYLOAD.json'] = encode(payload)
    result['deployment'].update(schema='dmfc-frozen-pair-ungraded-source-deployment/v1', mode=MODE,
        core_member_count=len(freeze['files']), external_candidate_member_count=len(bodies),
        rendered_sources={n: pin(b) for n, b in sorted(bodies.items())},
        payload={'path': 'CONFIGURATION_PAYLOAD.json', **pin(encode(payload))},
        payload_sha256_for_operator_request=pin(encode(payload))['sha256'],
        numerical_units=6, private_grading=False,
        original_four_cell_templates_unchanged=True)
    return result


def _group(runtime, folder, receipt, descriptor, argv):
    """Join existing durable creator identity; never probe or stop a process."""
    owner, unused = runtime.owner.expected(folder)
    need(owner['controller'] == descriptor and owner['child_argv'] == argv,
         'exact source/config creator argv')
    ready = decode(capture(folder / 'process_ready.json', 16384))
    gate = decode(capture(folder / 'process_gate.json', 16384))
    need(ready == {'token': owner['token'], 'pid': owner['pid'], 'pgid': owner['pgid'],
                  'python_initialized_before_identity_snapshot': True}
         and gate == {'token': owner['token'], 'activate': True}, 'durable preactivation identity')
    need(receipt.get('status') == 'owned_group_absent' and receipt.get('absence_verified') is True
         and receipt.get('pid') == receipt.get('pgid') == owner['pid'], 'source-bound historical creator absence')
    return owner


def validate_mounts(deployment, folder, admission, unit_inputs, operation, fitted_pin):
    """The actual unit mounts must equal this exact admitted public view."""
    expected = {}
    for row in admission['public_inputs']:
        if operation == 'prepare' and row['mount_destination'] == '/input/query.npz':
            continue
        expected[row['mount_destination']] = {**row, 'path': str(Path(deployment) / row['path'])}
    request_path = folder / ('request-0000.json' if operation == 'prepare' else 'request-0001.json')
    if operation != 'prepare':
        expected['/input/fitted.bin'] = {'path': str(folder / 'fitted.bin'), **fitted_pin,
            'mount_destination': '/input/fitted.bin', 'read_only': True}
    need(type(unit_inputs) is list and all(type(x) is dict for x in unit_inputs), 'typed actual unit inputs')
    by_dest = {x['mount_destination']: x for x in unit_inputs}
    need(len(by_dest) == len(unit_inputs) and set(by_dest) == set(expected) | {'/input/operation.json'},
         'exact public/TRAIN/frozen artifact mount inventory')
    need(all(by_dest[k] == value for k, value in expected.items()), 'actual mounted bytes equal admitted public/frozen inputs')
    request_input = by_dest['/input/operation.json']
    need(set(request_input) == {'path','bytes','sha256','mount_destination','read_only'}
         and request_input['path'] == str(request_path) and request_input['read_only'] is True,
         'exact generated operation request path before capture')
    return request_input


def validate_export(folder, intent, submission_pin):
    writer = b"from pathlib import Path\nPath('/output/submission.npz').write_bytes(Path('/input/opaque.bin').read_bytes())\n"
    need({k: intent['program'][k] for k in ('bytes','sha256')} == pin(writer)
         and intent['unit']['output_filename'] == 'submission.npz'
         and intent['unit']['max_output_bytes'] == 1048576
         and intent['unit']['public_inputs'] == [{'path': str(folder / 'opaque-output.bin'),
            **submission_pin, 'mount_destination': '/input/opaque.bin', 'read_only': True}],
         'unchanged opaque-only exporter source and single input; no evaluator mounts')


def validate_closed(root, expected_selection):
    """Authenticate one newly typed closed collection; read no targets/references.

The independent selection pins the exact deployed source freeze and OUTER_RESULT.
These are trusted operator provenance, not signatures or live absence probes.
The caller must still run the original public NPZ validator on both captured
submissions and verify its reads against these pins before any private loader.
"""
    need(type(expected_selection) is dict and set(expected_selection) ==
         {'deployment_root', 'configuration', 'source_freeze', 'outer_result'}, 'explicit frozen collection selection')
    deployment = Path(expected_selection['deployment_root']).absolute()
    root = Path(root).absolute()
    need(Path(expected_selection['configuration']['path']).parent == Path('.')
         and expected_selection['configuration']['path'].endswith('.json')
         and expected_selection['source_freeze']['path'] == BASE + '/SOURCE_FREEZE.json',
         'selected root-level config and fixed source-freeze roles before capture')
    config_raw = checked(deployment, expected_selection['configuration'], 262144)
    value = decode(config_raw)
    need(value.get('schema') == 'dmfc-frozen-pair-ungraded-config/v1'
         and value.get('collection_mode') == MODE and value['repository_root'] == str(deployment)
         and value['output_root'] == str(root) and value['successor_freeze'] == expected_selection['source_freeze'],
         'new prospective frozen-only configuration and independently selected source closure')
    freeze_raw = checked(deployment, expected_selection['source_freeze'], 262144)
    freeze = decode(freeze_raw)
    need(freeze['schema'] == 'dmfc-frozen-pair-ungraded-source/v1' and freeze['collection_mode'] == MODE
         and freeze['execution_authority'] is False and
         freeze['modules']['frozen_collection'] == BASE + '/frozen_collection.py', 'typed frozen source closure')
    # Prejoin source roles before the original loader's preliminary captures.
    need(Path(value['request']['path']).parent == Path('.') and value['request']['path'].endswith('.json'),
         'root-level request metadata only')
    need(set(value['actor']['arms']) == set(CONTEXTS), 'exact two actor roles before source capture')
    descriptors = [(value['numerical_tool'], '.py'), (value['method'], '.json'), (value['candidate_review'], '.json')]
    descriptors += [(arm[key], '.py' if key == 'program' else '.json')
                    for arm in value['actor']['arms'].values() for key in ('program','config')]
    for descriptor, suffix in descriptors:
        need(type(descriptor) is dict and set(descriptor) == {'path','bytes','sha256'}
             and descriptor['path'].startswith(BASE + '/') and descriptor['path'].endswith(suffix)
             and freeze['files'].get(descriptor['path']) == {k:descriptor[k] for k in ('bytes','sha256')},
             'selected source role belongs to owner closure before operand capture')
    config_rel = BASE + '/configuration.py'
    cm = module('_frozen_selected_configuration', deployment / config_rel,
        checked(deployment, {'path': config_rel, **freeze['files'][config_rel]}))
    config, captured, loaded_freeze = cm.load(deployment / expected_selection['configuration']['path'], pin(config_raw)['sha256'])
    need(config.value == value and loaded_freeze == freeze, 'one captured configuration/source identity')
    source = globals().get('COLLECTION_SOURCE')
    need(type(source) is bytes and captured[BASE + '/frozen_collection.py'] == source,
         'selected local collection equals deployed collection implementation')
    need(set(value['actor']['arms']) == set(CONTEXTS), 'only two actual frozen actor contexts')
    request = config.request
    need(request['schema'] == 'dmfc-frozen-pair-ungraded-root-request/v1'
         and request['decision'] == 'admit_one_complete_dmfc_frozen_pair_ungraded_operation'
         and request['candidate_id'] == 'NEURAL-095' and request['source_freeze'] == value['successor_freeze']
         and request['output_root'] == str(root) and request['actor_contexts'] == list(CONTEXTS)
         and request['runtime_identity'] == value['runtime_identity'], 'new actual request, not historical four-cell authority')
    need(request['profile'] == {'path': BASE + '/OPERATION_PROFILE.json',
         **freeze['files'][BASE + '/OPERATION_PROFILE.json']}, 'fixed profile role before capture')
    profile_raw = checked(deployment, request['profile'])
    need(profile_raw == captured[BASE + '/OPERATION_PROFILE.json'], 'actual selected operation profile')
    profile = decode(profile_raw)
    need(profile['schema'] == 'dmfc-frozen-pair-ungraded-operation-profile/v1'
         and profile['cells'] == list(CONTEXTS) and profile['maximum_numerical_units'] == 6
         and profile['reference_count'] == 0 and profile['work_seconds'] == 4200
         and profile['whole_seconds'] == 4800, 'ungraded six-unit profile with original conservative horizon')
    outer_raw = capture(root / 'OUTER_RESULT.json')
    need(pin(outer_raw) == expected_selection['outer_result'], 'independently selected closed outer receipt')
    outer = decode(outer_raw)
    need(outer.get('schema') == 'dmfc-frozen-pair-ungraded-outer-result/v1'
         and outer.get('status') == 'complete_frozen_pair_ungraded_operation'
         and outer.get('all_owned_absent') is True and outer.get('controller_returncode') == 0
         and outer.get('config_sha256') == config.sha256 and outer.get('request_sha256') == config.request_sha256
         and outer.get('profile') == request['profile'] and outer.get('automatic_retry') is False
         and outer.get('research_qualified') is False and not any(k.endswith('error_type') for k in outer)
         and 'interrupted_signal' not in outer, 'successful ungraded actual owner, no failure promotion')
    need(outer['actual_runtime'] == {'server': value['runtime_identity']['server'],
         'image': {k: value['runtime_identity']['image'][k] for k in ('Id', 'Os', 'Architecture')}},
         'original exact runtime identity was observed')
    inner_raw = capture(root / 'controller_result.json')
    need(pin(inner_raw) == outer['controller_result'], 'outer binds actual controller receipt')
    inner = decode(inner_raw)
    need(inner.get('schema') == 'dmfc-frozen-pair-ungraded-controller-result/v1'
         and inner.get('status') == 'frozen_pair_outputs_collected_ungraded'
         and inner.get('config_sha256') == config.sha256 and inner.get('request_sha256') == config.request_sha256
         and not any(k.endswith('error_type') for k in inner), 'ungraded controller identity')
    pair_raw = capture(root / 'FROZEN_PAIR.json'); pair = decode(pair_raw)
    need(inner['study_result'] == {'status': 'frozen_pair_outputs_collected_ungraded', 'mode': MODE,
         'pair_sha256': pin(pair_raw)['sha256'], 'private_grades_so_far': 0,
         'operational_qualification_claimed': False}, 'controller binds complete original Cell pair')
    need(pair.get('schema') == 'dmfc-frozen-pair-ungraded-collection/v1' and pair.get('mode') == MODE
         and pair['comparison_id'] == config.request_sha256 and pair['case_count_per_cell'] == 258
         and pair['training_count'] == 748 and pair['policy'] == POLICY
         and pair['private_grades_so_far'] == pair['private_target_reads'] == pair['private_reference_reads'] == 0
         and pair['numerical_units_expected'] == 6 and len(pair['cells']) == 2,
         'complete typed ungraded pair with no private phase')
    rb_rel = BASE + '/runtime_binding.py'
    rb = module('_frozen_closed_runtime', deployment / rb_rel, captured[rb_rel])
    runtime = rb.load_runtime(deployment, captured, freeze['files'], value['runtime_identity'])
    runtime.bind_aliases(freeze['modules'])
    owner_api = runtime.load(freeze['modules']['operation_owner'])
    live = runtime.load(freeze['modules']['live'])
    api = runtime.load(freeze['modules']['producer'])
    actor_runtime = runtime.load(freeze['modules']['actor_runtime'])
    contract = runtime.load(freeze['modules']['actor_contract'])
    stack = types.SimpleNamespace(operator_config=cm)
    def desc(name):
        path = freeze['modules'][name]; return {'path': path, **freeze['files'][path]}
    main_argv = [runtime.sys.executable, str(deployment / desc('controller')['path']), '--config',
        str(config.source_path), '--config-sha256', config.sha256, '--owner-directory', str(root / 'owner'),
        '--work-deadline', str(outer['work_deadline']), '--whole-deadline', str(outer['whole_deadline'])]
    main_owner = _group(runtime, root / 'owner', outer['group_cleanup'], desc('controller'), main_argv)
    completion = decode(capture(root / 'owner/process_completion.json', 16384))
    need(completion['token'] == main_owner['token'] and completion.get('returncode') == 0
         and completion.get('group_leader_waits_for_owner_stop') is True, 'natural controller zero joined before stop')
    need(set(outer['actor_creator_group_cleanup']) == set(outer['actor_cleanup']) == set(CONTEXTS),
         'both creator groups and both actor containers')
    actor_names, actor_ids = set(), set()
    for key in CONTEXTS:
        folder = root / 'actors' / key
        intent = actor_runtime.read_intent(config, stack, key)
        argv = [runtime.sys.executable, str(deployment / desc('actor_service')['path']), '--config',
            str(config.source_path), '--config-sha256', config.sha256, '--mode', key,
            '--owner-directory', str(folder / 'owner')]
        need(intent['child_argv'] == argv and intent['controller'] == desc('actor_service'), 'actual admitted actor creator')
        _group(runtime, folder / 'owner', outer['actor_creator_group_cleanup'][key], desc('actor_service'), argv)
        for field in ('program', 'actor_config'):
            need(pin(capture(intent[field]['path'], 65536)) == {k: intent[field][k] for k in ('bytes', 'sha256')},
                 'actor snapshot equals selected captured source/config')
        mounts = {'/actor/program.py': {'type': 'bind', 'source': intent['program']['path'], 'rw': False}}
        journal = decode(capture(folder / 'engine/resource_ownership.json', 65536))
        need(len(journal['owned']) == 1, 'one actual actor create')
        row = journal['owned'][0]
        need(row['name'] == intent['name'] and row['kind'] == 'container'
             and row['attempted_before_dispatch'] is True
             and row['canonical_create_argv'] == contract.argv(intent['name'], 'offline_actor', mounts, contract.descriptor()),
             'actor create matches unchanged isolated source-only profile')
        clean = outer['actor_cleanup'][key]
        container = clean.get('container', {})
        need(clean.get('mode') == key and clean.get('absence_verified') is True
             and clean.get('profile') == contract.descriptor() and container.get('absence_verified') is True
             and container.get('name') == intent['name'] and container.get('kind') == 'container'
             and container.get('immutable_id_and_name_absence') is True
             and re.fullmatch('[a-f0-9]{64}', container.get('verified_identity', '')) is not None,
             'actual captured-ID actor absence, not no-dispatch stand-in')
        need(intent['name'] not in actor_names and container['verified_identity'] not in actor_ids,
             'fresh actor identities across views')
        actor_names.add(intent['name']); actor_ids.add(container['verified_identity'])
    units = outer['numerical_cleanup']
    need(units.get('all_owned_absent') is True and units.get('unit_family_identity_valid') is True
         and units.get('all_unit_commits_verified') is True and units.get('unit_count') == 6
         and units.get('reused_closed_receipts') == 6 and units.get('pending_units_recovered') == 0
         and units.get('closed_receipt_reuse_disabled') is False, 'all six stopped-output unit commitments')
    folders = sorted((root / 'units').iterdir())
    need([p.name for p in folders] == ['unit-%04d' % i for i in range(6)], 'exact complete numerical family')
    for index, folder in enumerate(folders):
        intent = decode(capture(folder / 'UNIT_INTENT.json'))
        need(intent['unit']['output_filename'] == ('submission.npz' if index % 3 == 2 else 'result.json'),
             'fixed public-only captured numerical output path')
    names, ids = set(actor_names), set(actor_ids)
    rows = [owner_api.completed_unit(folder, i, live, runtime.engines, names, ids)
            for i, folder in enumerate(folders)]
    need(rows == units['units'], 'revalidated original closed numerical receipt chain')
    manifest_path = Q + '/dmfc-paired-delivery-20261114-v1/DELIVERY_MANIFEST.json'
    manifest = decode(captured[manifest_path])
    need(pair['delivery_manifest_sha256'] == pin(captured[manifest_path])['sha256'], 'original delivery source manifest')
    identity = manifest['evaluator_only_assets']['identity']
    public_ids = decode(checked(deployment, identity))['case_id']
    need(pair['case_ids'] == public_ids and len(public_ids) == len(set(public_ids)) == 258,
         'same complete original ordered query identity')
    submissions, paths, public_inputs, sessions = {}, {}, {}, set()
    limits = api.Limits(api.Usage(**value['limits']['total']), api.Usage(**value['limits']['preparation']),
        value['limits']['wall_us'], value['limits']['preparation_wall_us'],
        value['limits']['max_memory_bytes'], value['limits']['response_bytes'])
    reservations = {k: api.Usage(**v) for k,v in value['reservation_policy'].items()}
    for index, view in enumerate(VIEWS):
        folder = root / 'cells' / ('frozen_program__' + view)
        commit_raw = capture(folder / 'COMMIT.json'); commit = decode(commit_raw)
        admission_raw = capture(folder / 'ADMISSION.json'); admission = decode(admission_raw)
        frozen_raw = capture(folder / 'FREEZE.json'); frozen = decode(frozen_raw)
        actor = value['actor']['arms']['frozen_program__' + view]['program']
        expected_cell = api.Cell(mode='frozen_program', view=view, source=captured[actor['path']],
            method=captured[value['method']['path']], case_ids=tuple(public_ids), limits=limits,
            reservations=reservations, tool_ids=('dmfc_predict@' + value['numerical_tool']['sha256'],),
            backend=None, comparison_id=config.request_sha256, manifest=manifest,
            clock_us=lambda: 0, on_admission=lambda _: None)
        need(admission == expected_cell.specification() and pair['limits_sha256'] == limits.identity(),
             'entire original Cell admission, limits and reservation policy')
        need(commit == pair['cells'][index] and commit['mode'] == 'frozen_program' and commit['view'] == view
             and commit['case_count'] == 258 and commit['source_sha256'] == actor['sha256']
             and commit['method_sha256'] == value['method']['sha256'] and commit['limits_sha256'] == pair['limits_sha256']
             and commit['freeze_sha256'] == pin(frozen_raw)['sha256']
             and set(commit['absence']) == {'producer_absent','controller_absent','tools_absent','holder_absent','volume_absent'}
             and all(v is True for v in commit['absence'].values()), 'complete original stopped Cell commitment')
        need(commit['session_id'] not in sessions, 'separate committed actor sessions'); sessions.add(commit['session_id'])
        need(admission['mode'] == 'frozen_program' and admission['view'] == view
             and admission['comparison_id'] == config.request_sha256 and admission['case_count'] == 258
             and admission['training_count'] == 748 and admission['case_ids_sha256'] == pin(encode(tuple(public_ids)))['sha256']
             and admission['public_identity'] == identity
             and admission['public_inputs'] == manifest['public_views'][view]['public_inputs']
             and admission['source'].encode() == captured[actor['path']]
             and admission['method'].encode() == captured[value['method']['path']]
             and admission['tool_ids'] == ['dmfc_predict@' + value['numerical_tool']['sha256']]
             and admission['query_transduction'] == 'forbidden_training_artifacts_read_only_after_freeze',
             'exact source, method and five public input commitments')
        fitted_pin = pin(capture(folder / 'fitted.bin', 65536))
        need(frozen['specification_sha256'] == pin(admission_raw)['sha256']
             and frozen['source_sha256'] == actor['sha256'] and frozen['method_sha256'] == value['method']['sha256']
             and frozen['training_artifacts_sha256'] == fitted_pin['sha256'],
             'TRAIN artifact frozen before query')
        for offset, operation in ((0, 'prepare'), (1, 'tool')):
            u = folders[3 * index + offset]
            intent = decode(capture(u / 'UNIT_INTENT.json'))
            need({k: intent['program'][k] for k in ('bytes','sha256')} ==
                 {k: value['numerical_tool'][k] for k in ('bytes','sha256')}
                 and intent['unit']['output_filename'] == 'result.json'
                 and intent['unit']['max_output_bytes'] == 262144, 'same frozen numerical source and bounded output in both phases')
            request_input = validate_mounts(deployment, folder, admission, intent['unit']['public_inputs'], operation, fitted_pin)
            request_body = capture(deployment / request_input['path'])
            need(pin(request_body) == {k: request_input[k] for k in ('bytes','sha256')}, 'captured operation request')
            op = decode(request_body)
            need(op['operation'] == operation and (op['payload'] is None if operation == 'prepare' else
                 op['payload'] == {'case_id': public_ids[0], 'action': 'tool',
                     'tool_id': 'dmfc_predict@' + value['numerical_tool']['sha256'], 'arguments': {}}),
                 'single once-only frozen batch, no adaptive request')
        body = capture(folder / 'submission.npz')
        need(pin(body) == commit['submission'], 'exact stopped full submission bytes')
        export = decode(capture(folders[3 * index + 2] / 'attempt/commit.json'))
        export_intent = decode(capture(folders[3 * index + 2] / 'UNIT_INTENT.json'))
        validate_export(folder, export_intent, commit['submission'])
        need(pin(capture(folder / 'opaque-output.bin')) == commit['submission'], 'opaque export input bytes equal stopped output')
        need(export['output'] == commit['submission'], 'opaque stopped exporter captured same submission')
        submissions[view] = {'body': body, 'pin': pin(body)}
        paths[view] = str(folder / 'submission.npz')
        public_inputs[view] = admission['public_inputs']
    return {'mode': MODE, 'status': 'closed_ungraded', 'case_ids': public_ids,
        'public_inputs': public_inputs, 'program': {k: value['numerical_tool'][k] for k in ('bytes','sha256')},
        'method_document': {k: value['method'][k] for k in ('bytes','sha256')},
        'actor': {k: value['actor']['arms'][CONTEXTS[0]]['program'][k] for k in ('bytes','sha256')},
        'resource_policy': {'limits': value['limits'], 'reservation_policy': value['reservation_policy'],
            'host_budget': value['host_budget'], 'operation_profile': profile,
            'operation_profile_descriptor': request['profile']},
        'policy': POLICY, 'submissions': submissions, 'submission_paths': paths,
        'closure': {'configuration': pin(config_raw), 'source_freeze': pin(freeze_raw),
            'request': {k: value['request'][k] for k in ('bytes','sha256')},
            'outer': pin(outer_raw), 'controller': pin(inner_raw), 'pair': pin(pair_raw),
            'numerical_units': rows, 'historical_owned_absence_not_live_probe': True}}
