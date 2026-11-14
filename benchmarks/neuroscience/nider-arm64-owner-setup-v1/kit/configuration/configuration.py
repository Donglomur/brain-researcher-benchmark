"""Owner configuration and submission custody; never launches a candidate.

The numerical implementation stays at its authenticated installed anchor. This
module creates locator-bearing metadata, not another evaluator or estimator.
"""
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

LOCK_SHA256 = '5d872bedb8bc916e043788b66b4dcb0d40f70f7f1d0005b7044d3363e9465ece'
MODULE_ORDER = ('custody', 'build_spec', 'runtime_policy', 'reporting_core', 'scientific_score', 'owner_binding', 'protected_runner')
_runtime_cache = {}


def require(value, code):
    if not value:
        raise ValueError(code)


def _bootstrap_read(path, identity, maximum=1048576):
    """Authenticate the custody module before any of its code is imported."""
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and
            not any(x.is_symlink() for x in (p, *p.parents)), 'bootstrap_path')
    require(type(identity['bytes']) is int and 0 <= identity['bytes'] <= maximum, 'bootstrap_extent')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size == identity['bytes'], 'bootstrap_file')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    current = p.lstat()
    require(all(getattr(before, k) == getattr(after, k) == getattr(current, k)
                for k in ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')),
            'bootstrap_changed')
    require(len(raw) == identity['bytes'] and hashlib.sha256(raw).hexdigest() == identity['sha256'],
            'bootstrap_identity')
    return raw


def lock():
    p = Path(__file__).with_name('LOCK.json')
    raw = _bootstrap_read(p, {'bytes': 5457, 'sha256': LOCK_SHA256})
    value = json.loads(raw)
    require(value['schema'] == 'nider_portable_configuration_lock_v1', 'lock_schema')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def load_runtime(anchor):
    """Compile only authenticated bytes; reject unrelated preloaded helpers."""
    anchor = Path(anchor)
    fixed = lock()
    bodies = {name: _bootstrap_read(anchor / name, identity)
              for name, identity in fixed['modules'].items()}
    key = str(anchor)
    if key in _runtime_cache:
        modules = _runtime_cache[key]
        require(all(sys.modules.get(name) is modules[name] for name in MODULE_ORDER), 'module_cache_changed')
        return modules, fixed
    require(not any(name in sys.modules for name in MODULE_ORDER), 'unrelated_preloaded_runtime')
    modules = {}
    try:
        for name in MODULE_ORDER:
            path = anchor / (name + '.py')
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            modules[name] = module
            exec(compile(bodies[name + '.py'], str(path), 'exec'), module.__dict__)
            require(Path(module.__file__) == path, 'loaded_module_location')
    except BaseException:
        for name, module in modules.items():
            if sys.modules.get(name) is module:
                del sys.modules[name]
        raise
    _runtime_cache[key] = modules
    return modules, fixed


def source_pins(anchor, fixed):
    return {name + '.py': {'path': str(Path(anchor) / (name + '.py')),
                          **fixed['modules'][name + '.py']} for name in MODULE_ORDER} | {'DEPENDENCIES.json': {'path': str(Path(anchor) / 'DEPENDENCIES.json'), **fixed['modules']['DEPENDENCIES.json']}}


def resolved_assets(paths, fixed):
    require(type(paths) is dict and set(paths) == set(fixed['payloads']), 'complete_asset_map')
    return {name: {'path': paths[name], **identity} for name, identity in fixed['payloads'].items()}


def documents(anchor, assets, fixed, runtime_entry, runtime):
    """Every changed locator gets a new enclosing document pin."""
    catalogue = {'schema': 'nider_trusted_scientific_catalogue_v1', 'task': fixed['task'],
                 'policy': fixed['policy'], 'image': runtime['image'], 'runtime_policy': runtime_entry,
                 'published_targets': assets['published_targets'],
                 'official_code': assets['official_code'], 'official_code_license': assets['official_code_license'],
                 'reporting_core': {'path': str(Path(anchor) / 'reporting_core.py'), **fixed['modules']['reporting_core.py']},
                 'evidence': [assets[k] for k in fixed['evidence_keys']],
                 'cases': [{'case_id': item['case_id'], 'kind': item['kind'],
                            'workbook': assets[item['workbook_key']], 'reference': assets[item['reference_key']]}
                           for item in fixed['cases']]}
    material = {'schema': 'nider_full_paper_materials_v1', 'paper': assets['paper'],
                'paper_doi': fixed['paper_doi'], 'paper_scope': fixed['paper_scope'],
                'delivery_basis': assets['delivery_basis']}
    return catalogue, material


def authenticate_assets(custody, assets):
    """Bytes are authenticated without interpreting scientific values."""
    for entry in assets.values():
        custody.read_pin(entry, maximum=8388608)


def prepare_bundle(anchor, asset_manifest, output, runtime_entry):
    modules, fixed = load_runtime(anchor)
    c = modules['custody']
    manifest = c.decode(c.read_pin(asset_manifest, maximum=65536))
    require(type(manifest) is dict and set(manifest) == {'schema','task','assets'} and manifest['schema'] == 'nider_symbolic_asset_locations_v1' and manifest['task'] == fixed['task'], 'symbolic_asset_manifest')
    runtime = modules['runtime_policy'].admit(runtime_entry)
    assets = resolved_assets(manifest['assets'], fixed)
    authenticate_assets(c, assets)
    catalogue, material = documents(anchor, assets, fixed, runtime_entry, runtime)
    root = c.plain(output)
    root.mkdir(mode=0o700)
    catalogue_pin = c.write_new(root / 'CATALOGUE.json', c.encoded(catalogue))
    materials_pin = c.write_new(root / 'MATERIALS.json', c.encoded(material))
    modules['owner_binding'].admit_catalogue(catalogue_pin)
    modules['owner_binding'].admit_materials(materials_pin)
    value = {'schema': 'nider_prepared_owner_bundle_v1', 'task': fixed['task'], 'profile': fixed['profile'],
             'lock_sha256': LOCK_SHA256, 'source_anchor': str(Path(anchor)),
             'sources': source_pins(anchor, fixed),
             'observer': {'path': str(Path(anchor) / 'observe_protected_runner.py'),
                          **fixed['modules']['observe_protected_runner.py']},
             'assets': assets, 'asset_manifest': asset_manifest, 'runtime_policy': runtime_entry, 'runtime': runtime, 'catalogue': catalogue_pin, 'materials': materials_pin}
    return c.write_new(root / 'PREPARED.json', c.encoded(value))


def prepare_authoring(prepared_entry, arm, policy, output, session_root):
    modules, fixed, prepared = admit_prepared(prepared_entry)
    c = modules['custody']
    require(arm in ('A', 'B'), 'authoring_arm')
    authoring_policy(policy)
    root = c.plain(output); root.mkdir(mode=0o700)
    session = c.plain(session_root)
    require(not session.exists(), 'fresh_authoring_root')
    plan = {'schema': 'nider_local_authoring_plan_v1', 'prepared': prepared_entry, 'arm': arm,
            'policy': policy, 'runtime_policy': prepared['runtime_policy'], 'owner_root': str(session)}
    entry = c.write_new(root / 'AUTHORING_PLAN.json', c.encoded(plan))
    return {'plan': entry,
            'argv': ['python3', '-B', str(Path(__file__).with_name('authoring_gateway.py')),
                     entry['path'], entry['sha256']],
            'execution_selected': False}


def admit_prepared(entry):
    # This small descriptor is owner-selected, never a candidate argument.
    raw = _bootstrap_read(entry['path'], entry)
    untrusted = json.loads(raw)
    modules, fixed = load_runtime(untrusted['source_anchor'])
    c = modules['custody']
    value = c.decode(c.read_pin(entry))
    require(set(value) == {'schema', 'task', 'profile', 'lock_sha256', 'source_anchor', 'sources',
                           'observer', 'assets', 'asset_manifest', 'runtime_policy', 'runtime', 'catalogue', 'materials'}, 'prepared_keys')
    require(value['schema'] == 'nider_prepared_owner_bundle_v1' and value['task'] == fixed['task'] and
            value['profile'] == fixed['profile'] and value['lock_sha256'] == LOCK_SHA256, 'prepared_identity')
    require(value['sources'] == source_pins(value['source_anchor'], fixed), 'prepared_sibling_closure')
    require(value['observer'] == {'path': str(Path(value['source_anchor']) / 'observe_protected_runner.py'),
                                 **fixed['modules']['observe_protected_runner.py']}, 'prepared_observer')
    runtime = modules['runtime_policy'].admit(value['runtime_policy'])
    require(runtime == value['runtime'], 'prepared_runtime_join')
    manifest = c.decode(c.read_pin(value['asset_manifest'], maximum=65536))
    require(type(manifest) is dict and set(manifest) == {'schema','task','assets'} and manifest['schema'] == 'nider_symbolic_asset_locations_v1' and manifest['task'] == fixed['task'], 'symbolic_asset_manifest')
    assets = resolved_assets(manifest['assets'], fixed)
    require(assets == value['assets'], 'prepared_payload_identity')
    authenticate_assets(c, assets)
    catalogue, material = documents(value['source_anchor'], assets, fixed, value['runtime_policy'], runtime)
    require(c.decode(c.read_pin(value['catalogue'])) == catalogue, 'prepared_catalogue_graph')
    require(c.decode(c.read_pin(value['materials'])) == material, 'prepared_material_graph')
    return modules, fixed, value


def authoring_policy(value):
    required = {'schema', 'comparison_id', 'wall_seconds', 'command_seconds', 'command_limit',
                'total_input_bytes', 'total_output_bytes', 'network', 'tools', 'model_execution'}
    require(type(value) is dict and set(value) == required, 'authoring_policy_keys')
    require(value['schema'] == 'nider_local_authoring_policy_v1' and
            type(value['comparison_id']) is str and 1 <= len(value['comparison_id']) <= 128, 'authoring_policy_identity')
    for name, maximum in [('wall_seconds', 3600), ('command_seconds', 30), ('command_limit', 128),
                          ('total_input_bytes', 1048576), ('total_output_bytes', 1048576)]:
        require(type(value[name]) is int and 1 <= value[name] <= maximum, 'authoring_policy_extent')
    require(value['command_seconds'] <= value['wall_seconds'] and value['network'] == 'none' and
            value['tools'] == ['exec', 'submit'] and value['model_execution'] is False, 'authoring_policy_surface')
    return hashlib.sha256(canonical(value)).hexdigest()


def material_fingerprint(prepared, fixed):
    # The arm-specific two-file difference is deliberate; shared assets match.
    shared = ['workbook_0', 'paper', 'paper_text', *fixed['candidate_doc_keys']]
    return {name: prepared['assets'][name]['sha256'] for name in shared}


def seal_handoff(c, root, prepared_entry, prepared, fixed, arm, policy, program, deviations, lifecycle):
    """Only the trusted gateway calls this after actual owned cleanup."""
    require(arm in ('A', 'B') and lifecycle['terminal_event'] == 'submitted' and
            lifecycle['cleanup_verified'] and lifecycle['failure'] is None, 'handoff_requires_actual_closure')
    require(type(program) is str and type(deviations) is str and '\x00' not in program + deviations,
            'submission_text')
    require(lifecycle['runtime_policy'] == prepared['runtime_policy'], 'handoff_runtime_lifecycle')
    live = c.decode(c.read_pin(lifecycle['runtime_admission']))
    require(live['runtime_policy_sha256'] == digest_runtime(prepared), 'handoff_live_runtime_join')
    program_raw = program.encode('utf-8'); report_raw = deviations.encode('utf-8')
    require(1 <= len(program_raw) <= 262144 and 1 <= len(report_raw) <= 65536, 'submission_extent')
    submission = c.plain(root) / 'submission'; submission.mkdir(mode=0o700)
    code_pin = c.write_new(submission / 'solution.R', program_raw)
    report_pin = c.write_new(submission / 'DEVIATIONS.md', report_raw)
    Path(code_pin['path']).chmod(0o400); Path(report_pin['path']).chmod(0o400)
    lifecycle_pin = c.write_new(c.plain(root) / 'LIFECYCLE.json', c.encoded(lifecycle))
    payload = {'schema': 'nider_authoring_handoff_payload_v1', 'task': fixed['task'], 'profile': fixed['profile'],
               'lock_sha256': LOCK_SHA256, 'prepared': prepared_entry, 'arm': arm,
               'policy': policy, 'policy_sha256': authoring_policy(policy),
               'shared_materials': material_fingerprint(prepared, fixed), 'image': prepared['runtime']['image'], 'runtime_policy': prepared['runtime_policy'],
               'program': code_pin, 'deviations': report_pin, 'lifecycle': lifecycle_pin}
    key = os.urandom(32)
    key_pin = c.write_new(c.plain(root) / 'ISSUER_KEY.bin', key)
    signature = hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()
    handoff = c.write_new(c.plain(root) / 'HANDOFF.json', c.encoded({'payload': payload, 'hmac_sha256': signature}))
    return {'handoff': handoff, 'issuer_key': key_pin}


def neutral_finalization_pin(handoff_entry):
    return {'path': str(Path(handoff_entry['path']).with_name('EMERGENCY_RESERVE.bin')),
            'bytes': 65536, 'sha256': hashlib.sha256(bytes(65536)).hexdigest()}


def admit_handoff(entry, key_entry, prepared_entry, prepared, modules, fixed, completion_entry):
    c = modules['custody']
    record = c.decode(c.read_pin(entry)); key = c.read_pin(key_entry, maximum=32)
    require(set(record) == {'payload', 'hmac_sha256'} and len(key) == 32, 'handoff_record')
    value = record['payload']
    require(hmac.compare_digest(record['hmac_sha256'], hmac.new(key, canonical(value), hashlib.sha256).hexdigest()),
            'handoff_authentication')
    require(set(value) == {'schema', 'task', 'profile', 'lock_sha256', 'prepared', 'arm', 'policy',
                           'policy_sha256', 'shared_materials', 'image', 'runtime_policy', 'program', 'deviations', 'lifecycle'}, 'handoff_keys')
    require(value['schema'] == 'nider_authoring_handoff_payload_v1' and value['task'] == fixed['task'] and
            value['profile'] == fixed['profile'] and value['lock_sha256'] == LOCK_SHA256 and
            value['prepared'] == prepared_entry and value['image'] == prepared['runtime']['image'] and value['runtime_policy'] == prepared['runtime_policy'] and
            value['arm'] in ('A', 'B'), 'handoff_identity')
    require(value['policy_sha256'] == authoring_policy(value['policy']) and
            value['shared_materials'] == material_fingerprint(prepared, fixed), 'handoff_policy_and_materials')
    c.read_pin(value['program'], maximum=262144); c.read_pin(value['deviations'], maximum=65536)
    life = c.decode(c.read_pin(value['lifecycle']))
    require(life['terminal_event'] == 'submitted' and life['cleanup_verified'] and life['failure'] is None,
            'handoff_lifecycle')
    require(life['runtime_policy'] == prepared['runtime_policy'], 'handoff_runtime_lifecycle')
    live = c.decode(c.read_pin(life['runtime_admission']))
    require(live['runtime_policy_sha256'] == modules['runtime_policy'].digest(prepared['runtime']), 'handoff_live_runtime_join')
    # A signed partial handoff is not a successfully finalized gateway session.
    completion_path = c.plain(completion_entry['path'])
    require(completion_path == Path(entry['path']).with_name('AUTHORING_RESULT.json'), 'handoff_completion_location')
    require(completion_path.is_file(), 'handoff_completion_missing')
    completion = c.decode(c.read_pin(completion_entry))
    require(type(completion) is dict and set(completion) == {'schema', 'successful_handoff', 'handoff', 'issuer_key'} and
            completion['schema'] == 'nider_local_authoring_result_v1' and completion['successful_handoff'] is True and
            completion['handoff'] == entry and completion['issuer_key'] == key_entry, 'handoff_completion_join')
    # write_new may finish writing success JSON before a later chmod fails.
    # The gateway records such failed finalization in this preallocated file;
    # a complete-looking result cannot override that failure evidence.
    c.read_pin(neutral_finalization_pin(entry), maximum=65536)
    return value


def paired_handoffs(a, b):
    require(a['arm'] == 'A' and b['arm'] == 'B', 'paired_arms')
    for key in ('task', 'profile', 'lock_sha256', 'policy_sha256', 'shared_materials', 'image', 'runtime_policy'):
        require(a[key] == b[key], 'paired_common_policy_or_materials')
    return {'matched': True, 'policy_sha256': a['policy_sha256'], 'model_comparison': False}


def prepare_assessment(prepared_entry, handoff_entry, key_entry, completion_entry, output, expected_arm):
    modules, fixed, prepared = admit_prepared(prepared_entry)
    c = modules['custody']
    handoff = admit_handoff(handoff_entry, key_entry, prepared_entry, prepared, modules, fixed, completion_entry)
    require(expected_arm == handoff['arm'], 'assessment_arm_from_handoff')
    root = c.plain(output); root.mkdir(mode=0o700)
    owner = {'schema': 'nider_protected_runner_plan_v1',
             'selection_id': 'NIDER-LOCAL-HANDOFF-' + handoff_entry['sha256'][:24],
             'owner_root': str(root / 'owner'), 'catalogue': prepared['catalogue'],
             'materials': prepared['materials'], 'program': handoff['program'],
             'arm': handoff['arm'], 'sources': prepared['sources'], 'runtime_policy': prepared['runtime_policy']}
    owner_pin = c.write_new(root / 'OWNER_PLAN.json', c.encoded(owner))
    pins = [owner_pin, prepared_entry, handoff_entry, completion_entry, neutral_finalization_pin(handoff_entry),
            handoff['deviations'], handoff['lifecycle'],
            prepared['observer'], prepared['catalogue'], prepared['materials'], handoff['program'],
            *prepared['sources'].values(), *prepared['assets'].values(), prepared['asset_manifest'], *runtime_pins(prepared)]
    unique = {entry['path']: entry for entry in pins}
    require(len(unique) == len(pins), 'assessment_duplicate_pin_path')
    outer = {'schema': 'nider_protected_outer_plan_v1', 'owner_root': str(root), 'wall_seconds': 240,
             'maximum_attempts': 1, 'whole_private_limit_bytes': 16777216,
             'argv': ['python3', '-B', str(Path(prepared['source_anchor']) / 'protected_runner.py'),
                      owner_pin['path'], owner_pin['sha256']], 'pins': list(unique.values())}
    outer_pin = c.write_new(root / 'OUTER_PLAN.json', c.encoded(outer))
    result = {'schema': 'nider_prepared_assessment_invocation_v1', 'handoff': handoff_entry,
              'authoring_completion': completion_entry,
              'neutral_finalization': neutral_finalization_pin(handoff_entry),
              'provenance_sidecar': handoff['deviations'], 'owner_plan': owner_pin, 'outer_plan': outer_pin,
              'observer': prepared['observer'],
              'argv': ['python3', prepared['observer']['path'], outer_pin['path'], outer_pin['sha256']],
              'execution_selected': False}
    return c.write_new(root / 'INVOCATION.json', c.encoded(result))


def runtime_pins(prepared):
    modules, _ = load_runtime(prepared['source_anchor'])
    rp = prepared['runtime_policy']; runtime = modules['runtime_policy'].admit(rp)
    ev = runtime['image_evidence']; record = modules['custody'].decode(modules['custody'].read_pin(ev))
    return [rp, ev, *[record[k] for k in ('build_plan','build_lifecycle','image_inspection','base_image_inspection','image_history','runtime_inventory','filesystem_audit')]]


def digest_runtime(prepared):
    modules, _ = load_runtime(prepared['source_anchor'])
    return modules['runtime_policy'].digest(prepared['runtime'])
