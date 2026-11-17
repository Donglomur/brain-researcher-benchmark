"""Finite portable metadata construction; no scientific or qualification execution.

This exact fragment is assembled into the one-file constructor. Context methods
are concrete owner machinery, not caller supplied plugins. Independently issued
records are only captured/checked/copied. No credential or private operand body
is read, and no passing issuer verdict is constructed here.
"""
import re
import ipaddress

_STAGE_TASK = 'NEURAL-081'
_STAGE_PHASES = ('G0', 'G1', 'G2', 'G3', 'G5')
_STAGE_ROLES = ('input', 'access', 'native', 'physical_custody', 'provider', 'resources', 'observer')
_STAGE_ACTORS = ('controller', 'outer', 'preparer', 'reference', 'author', 'issuer', 'candidate', 'grader')
_STAGE_COUNTS = ('read_bytes', 'write_bytes', 'native_cpu_seconds', 'native_processes', 'host_processes', 'provider_requests', 'provider_tokens', 'stream_bytes', 'tool_processes')
_STAGE_CONDITIONS = ('default', 'full10_instructed_excerpt_v1')
_STAGE_PEOPLE = ('P01', 'P04', 'P05', 'P06', 'P07', 'P09', 'P11', 'P12', 'P13', 'P14')
_STAGE_CONTROLLER_KEYS = ('schema', 'source', 'run', 'channel', 'output_root', 'protected_roots', 'native_config', 'preparation', 'preparation_manifest', 'reference_manifest', 'issuer_manifest', 'issuer_worker_limits', 'issuer_sandbox', 'host_python', 'host_environment', 'provider_config', 'replication_seeds', 'public_protocol', 'tool_source', 'candidate_runner', 'numeric_source', 'grade_manifest', 'grade_worker_io', 'host_metadata_capacity_bytes')
_STAGE_REVIEW_KEYS = ('schema', 'task_id', 'condition', 'central_source', 'parent_source', 'construction', 'registry', 'program', 'run', 'local_declaration', 'origin', 'normal_endpoint', 'central_limits', 'total_limits', 'external_limits', 'memory', 'roots', 'launch')
_STAGE_CAPABILITIES = {'physical_root_disjointness': True, 'operator_namespace_immutable': True, 'single_credential_boundary': True, 'actual_linux_procfs_observer': True, 'parent_and_central_interpreters': True, 'complete_graph_readback_resources': True, 'inherited_address_space_limit': True, 'independent_central_exit_observer_required': True, 'statistical_semantic_reviewer': False}


def _stage_object(value, schema, keys):
    exact(value, keys)
    need(value['schema'] == schema and value.get('task_id', _STAGE_TASK) == _STAGE_TASK, 'exact portable metadata schema/task')
    return value


def _stage_descriptor(value):
    descriptor(value)
    integer(value['bytes'], 1)
    return value


def _stage_path_descriptor(value, path):
    _stage_descriptor(value)
    need(value['path'] == str(path), 'source-owned exact metadata path')
    return value


def _stage_fixed(ctx, relative_name):
    path = str(ctx.root / relative_name)
    need(path in ctx.fixed_files, 'exact selected fixed source role')
    return _stage_path_descriptor(ctx.fixed_files[path], path)


def _stage_bound_run(ctx):
    need(ctx.run is not None and ctx.run_root is not None, 'original selected run required for immutable operand resolution')
    captured = ctx.stage_record('selection/OPERANDS.json')
    exact(captured, ('descriptor', 'document'))
    _stage_path_descriptor(captured['descriptor'], ctx.run_root/'selection/OPERANDS.json')
    row = captured['document']
    _stage_object(row, 'neural081_portable_run_operands_v1', ('schema', 'task_id', 'construction', 'source', 'run', 'input', 'execution_selection'))
    for key, expected in (('construction', ctx.construction), ('source', ctx.parent), ('run', ctx.run_descriptor)):
        need(same(row[key], expected), 'immutable source/run operand binding ' + key)
    _stage_descriptor(row['input']); _stage_descriptor(row['execution_selection'])
    return row


def _stage_profile(ctx, field, supplied=None):
    need(field in ('input_records', 'execution_selection', 'environment_records'), 'finite profile operand roles')
    original = ctx.profile[field]
    unresolved = same(original, {'disposition': 'not_supplied'})
    if not unresolved:
        _stage_descriptor(original)
    if supplied is not None:
        selected = _stage_descriptor(supplied)
    elif ctx.run is None:
        need(not unresolved, 'unresolved operand requires an explicit selected stage input')
        selected = original
    else:
        bound = _stage_bound_run(ctx)
        if field != 'environment_records':
            selected = bound['input' if field == 'input_records' else 'execution_selection']
        else:
            captured = ctx.stage_record('environment/BINDING.json')
            exact(captured, ('descriptor', 'document'))
            _stage_path_descriptor(captured['descriptor'], ctx.run_root/'environment/BINDING.json')
            row = captured['document']
            _stage_object(row, 'neural081_portable_environment_binding_v1', ('schema', 'task_id', 'source', 'central_source', 'run', 'input', 'execution_selection', 'environment_records', 'artifacts', 'numeric_source'))
            for key, expected in (('source', ctx.parent), ('central_source', ctx.source), ('run', ctx.run_descriptor), ('input', bound['input']), ('execution_selection', bound['execution_selection'])):
                need(same(row[key], expected), 'immutable complete environment lineage ' + key)
            selected = _stage_descriptor(row['environment_records'])
    need(unresolved or same(original, selected), 'an initially pinned profile operand cannot change')
    return ctx.read(selected, scope='input'), selected


def _stage_roots(ctx, name):
    value = ctx.profile['root_roles'][name]
    rows = value if type(value) is list else [value]
    need(type(rows) is list and 0 < len(rows) <= 32, 'bounded complete root list')
    for path in rows:
        canonical(path)
    need(len(set(rows)) == len(rows), 'unique selected root list')
    return rows


def _stage_within(path, roots):
    p = canonical(path)
    need(any(p == canonical(r) or p.is_relative_to(canonical(r)) for r in roots), 'descriptor belongs to selected physical role')
    return p


def _stage_io(value):
    exact(value, ('read_bytes', 'write_bytes'))
    for v in value.values():
        integer(v, 1)
    return value


def _stage_limits(value, seconds):
    exact(value, ('seconds', *_STAGE_COUNTS))
    need(type(value['seconds']) in (int, float) and finite(value['seconds'], 0) == seconds, 'unchanged original interval')
    for key in _STAGE_COUNTS:
        integer(value[key])
    return value


def _stage_input(ctx, supplied=None):
    row, desc = _stage_profile(ctx, 'input_records', supplied)
    _stage_object(row, 'neural081_portable_input_record_v1', ('schema', 'task_id', 'preparation', 'N', 'census_evidence', 'physical_input_evidence'))
    integer(row['N'], 120, 100000)
    for name in ('census_evidence', 'physical_input_evidence'):
        _stage_descriptor(row[name])
    p = row['preparation']
    exact(p, ('inventory', 'release_root', 'raw_files', 'key', 'protocol_source', 'annotation_authority', 'worker_io', 'protected_roots'))
    for name in ('inventory', 'key', 'protocol_source', 'annotation_authority'):
        _stage_descriptor(p[name])
    need(p['key']['bytes'] == 32, 'exact key extent; body never opened')
    _stage_within(p['key']['path'], _stage_roots(ctx, 'secret'))
    release = _stage_within(p['release_root'], _stage_roots(ctx, 'raw'))
    need(type(p['raw_files']) is list and len(p['raw_files']) == 11, 'all eleven original release descriptors')
    expected = [name + '-raw.fif' for name in _STAGE_PEOPLE] + ['README.md']
    for d, name in zip(p['raw_files'], expected):
        _stage_path_descriptor(d, release / name)
    need(type(p['worker_io']) is list and len(p['worker_io']) == 10, 'ten complete worker reservations')
    for io in p['worker_io']:
        _stage_io(io)
    need(same(p['protected_roots'], _stage_roots(ctx, 'protected')), 'exact complete protected roots')
    return row, desc


def _stage_selection(ctx, supplied=None, input_row=None):
    s, desc = _stage_profile(ctx, 'execution_selection', supplied)
    _stage_object(s, 'neural081_portable_execution_selection_v1', ('schema', 'task_id', 'condition', 'origin', 'whole_limits', 'phase_limits', 'outer_limits', 'issuer_limits', 'request_caps', 'artifact_caps', 'central_limits', 'external_limits', 'total_limits', 'memory', 'worker_io', 'replication_seeds', 'channel', 'outputs', 'bootstrap_read_cap'))
    need(s['condition'] in _STAGE_CONDITIONS and type(s['origin']) is float, 'literal complete condition and original float origin')
    finite(s['origin'], 0)
    if input_row is None:
        input_row, _ = _stage_input(ctx)
    n = input_row['N']
    seconds = 10*3600 + 3680*7200 + 3680*900 + 20*300 + 12*n*480 + 3600 + 120*(54*n+27) + 24*60 + 86400 + 60*(7391+54*n+24)
    for name in ('whole_limits', 'outer_limits', 'issuer_limits', 'central_limits', 'external_limits', 'total_limits'):
        _stage_limits(s[name], seconds)
    exact(s['phase_limits'], _STAGE_PHASES)
    exact(s['request_caps'], _STAGE_PHASES)
    exact(s['artifact_caps'], _STAGE_PHASES)
    for phase in _STAGE_PHASES:
        _stage_limits(s['phase_limits'][phase], seconds)
        integer(s['request_caps'][phase], 1)
        integer(s['artifact_caps'][phase], 1)
    for key in _STAGE_COUNTS:
        need(sum(v[key] for v in [*s['phase_limits'].values(), s['outer_limits'], s['issuer_limits']]) <= s['whole_limits'][key], 'all parent shares fit original whole')
        need(s['total_limits'][key] >= s['whole_limits'][key] + s['central_limits'][key] + s['external_limits'][key], 'full parent/central/external allocation')
    need(s['whole_limits']['host_processes'] >= 3 and s['issuer_limits']['host_processes'] >= 1, 'complete original parent hosts')
    need(s['central_limits']['host_processes'] == 1 and all(s['central_limits'][k] == 0 for k in ('native_cpu_seconds', 'native_processes', 'provider_requests', 'provider_tokens', 'tool_processes')), 'central adds one host and no scientific operations')
    need(s['total_limits']['host_processes'] >= 4 + s['external_limits']['host_processes'], 'four task hosts plus external observation')
    m = s['memory']
    exact(m, ('address_space_bytes', 'readback_live_bytes', 'metadata_cap_bytes', 'other_reserve_bytes'))
    integer(m['address_space_bytes'], 512*2**20, 256*2**30)
    integer(m['readback_live_bytes'], 64*2**20, m['address_space_bytes'])
    integer(m['metadata_cap_bytes'], 32768, m['readback_live_bytes']//8)
    integer(m['other_reserve_bytes'])
    need(m['readback_live_bytes'] + m['other_reserve_bytes'] + 512*2**20 <= m['address_space_bytes'], 'separate live memory envelopes')
    exact(s['worker_io'], ('preparation', 'grade', 'host_metadata_capacity_bytes'))
    need(same(s['worker_io']['preparation'], input_row['preparation']['worker_io']), 'same actual ten preparation shares')
    _stage_io(s['worker_io']['grade'])
    integer(s['worker_io']['host_metadata_capacity_bytes'], 12*n*16384 + 7380*8192 + 64*2**20)
    exact(s['replication_seeds'], ('r0', 'r1', 'r2'))
    for seed in s['replication_seeds'].values():
        need(seed is None or type(seed) is int and 0 <= seed < 2**31, 'selected seed or explicit unknown determinism')
    exact(s['channel'], ('maximum_response_bytes', 'poll_seconds'))
    integer(s['channel']['maximum_response_bytes'], 1, 2**20)
    need(.001 <= finite(s['channel']['poll_seconds']) <= 1, 'original bounded channel polling')
    exact(s['outputs'], ('output',))
    _stage_within(s['outputs']['output'], _stage_roots(ctx, 'output'))
    integer(s['bootstrap_read_cap'], 1, 64*2**20)
    run = {'schema': 'neural081_complete_run_v1', 'origin': s['origin'], 'normal_endpoint': s['origin'] + seconds, 'whole_limits': s['whole_limits'], 'phase_limits': s['phase_limits'], 'outer_limits': s['outer_limits'], 'issuer_limits': s['issuer_limits'], 'N': n, 'request_caps': s['request_caps'], 'artifact_caps': s['artifact_caps'], 'status': 'selected_not_qualified_by_this_record'}
    if ctx.run is not None:
        need(same(run, ctx.run), 'profile and captured original run agree')
    return s, desc, run


def _stage_host(value, memory):
    exact(value, ('central_python', 'parent_python', 'host_environment', 'address_space_bytes', 'inherited_address_space_bytes', 'qualification'))
    canonical(value['central_python']); canonical(value['parent_python'])
    env = value['host_environment']
    exact(env, ('PATH', 'PYTHONDONTWRITEBYTECODE'))
    need(type(env['PATH']) is str and env['PATH'] and '\0' not in env['PATH'] and env['PYTHONDONTWRITEBYTECODE'] == '1', 'clean selected environment without credential value')
    need(same(value['address_space_bytes'], memory['address_space_bytes']) and same(value['inherited_address_space_bytes'], memory['address_space_bytes']), 'exact selected/inherited address space')
    _stage_descriptor(value['qualification'])


def _stage_native(v):
    exact(v, ('engine_socket', 'engine_api_version', 'image_digest', 'python', 'user', 'pids_limit', 'cpus', 'tmpfs_bytes', 'stream_cap_bytes', 'workspace_cap_bytes', 'workspace_entry_cap', 'cleanup_seconds', 'poll_seconds', 'engine_response_cap_bytes', 'engine_control_seconds', 'qualification'))
    exact(v['engine_socket'], ('path', 'device', 'inode', 'owner_uid'))
    canonical(v['engine_socket']['path'])
    for key in ('device', 'inode', 'owner_uid'):
        integer(v['engine_socket'][key])
    need(type(v['engine_api_version']) is str and re.fullmatch(r'v1\.\d{2}', v['engine_api_version']), 'exact engine API')
    need(type(v['image_digest']) is str and re.fullmatch('sha256:[0-9a-f]{64}', v['image_digest']), 'immutable installed image')
    canonical(v['python'])
    need(type(v['user']) is str and re.fullmatch(r'[1-9]\d*:\d+', v['user']), 'explicit nonroot UID:GID')
    for key, expected in (('pids_limit', 1), ('cpus', 1), ('stream_cap_bytes', 262144), ('cleanup_seconds', 120)):
        need(type(v[key]) is int and v[key] == expected, 'original fixed native ' + key)
    for key in ('tmpfs_bytes', 'workspace_cap_bytes', 'workspace_entry_cap', 'engine_response_cap_bytes'):
        integer(v[key], 1)
    need(v['engine_response_cap_bytes'] <= 2**21, 'bounded engine response')
    for key in ('poll_seconds', 'engine_control_seconds'):
        need(0 < finite(v[key]) <= 30, 'bounded engine control interval')
    exact(v['qualification'], ('engine', 'clock', 'namespace', 'physical_io'))
    for d in v['qualification'].values():
        _stage_descriptor(d)


def _stage_provider(v):
    exact(v, ('resolved_ip', 'endpoint', 'model', 'api_key_env', 'max_completion_tokens', 'prompt_token_reservation', 'request_cap_bytes', 'response_cap_bytes', 'request_timeout_seconds', 'seed', 'tokenizer_contract', 'transcript_cap_bytes'))
    need(v['endpoint'] == 'https://api.openai.com/v1/chat/completions', 'original literal provider endpoint')
    need(type(v['resolved_ip']) is str and str(ipaddress.ip_address(v['resolved_ip'])) == v['resolved_ip'], 'canonical independently selected literal IP')
    need(type(v['model']) is str and v['model'] and type(v['api_key_env']) is str and re.fullmatch('[A-Z][A-Z0-9_]{1,127}', v['api_key_env']), 'model and single credential NAME only')
    for key in ('max_completion_tokens', 'prompt_token_reservation', 'request_cap_bytes', 'response_cap_bytes', 'transcript_cap_bytes'):
        integer(v[key], 1)
    need(v['max_completion_tokens'] <= 4096 and v['prompt_token_reservation'] == 32768 and v['response_cap_bytes'] <= 2**21 and v['transcript_cap_bytes'] <= 2**24, 'original token/HTTP/transcript caps')
    need(0 < finite(v['request_timeout_seconds']) <= 120, 'original provider timeout')
    need(v['seed'] is None or type(v['seed']) is int and 0 <= v['seed'] < 2**31, 'selected provider seed')
    t = v['tokenizer_contract']
    exact(t, ('schema', 'model', 'package_version', 'encoding_name', 'pattern', 'vocabulary', 'special_tokens', 'request_prefix_tokens', 'per_message_tokens', 'assistant_prefix_tokens', 'qualification'))
    need(t['schema'] == 'neural081_plain_chat_tokenizer_contract_v1' and t['model'] == v['model'], 'exact source tokenizer contract/model')
    for key in ('package_version', 'encoding_name', 'pattern'):
        need(type(t[key]) is str and t[key], 'literal tokenizer metadata')
    for key in ('vocabulary', 'qualification'):
        _stage_descriptor(t[key])
    need(type(t['special_tokens']) is dict and all(type(k) is str and type(x) is int and x >= 0 for k, x in t['special_tokens'].items()), 'typed token table, never body loaded')
    for key in ('request_prefix_tokens', 'per_message_tokens', 'assistant_prefix_tokens'):
        integer(t[key])


def _stage_environment_records(ctx, supplied=None):
    e, desc = _stage_profile(ctx, 'environment_records', supplied)
    _stage_object(e, 'neural081_portable_environment_records_v1', ('schema', 'task_id', 'host', 'worker_environments', 'native', 'provider', 'issuer', 'external_observer'))
    s, _, _ = _stage_selection(ctx)
    _stage_host(e['host'], s['memory'])
    _stage_native(e['native']); _stage_provider(e['provider'])
    need(e['provider']['api_key_env'] not in e['host']['host_environment'], 'credential absent from stored environment')
    exact(e['worker_environments'], ('preparation', 'reference', 'issuer', 'grader'))
    for kind, row in e['worker_environments'].items():
        exact(row, ('qualification', 'installed_versions', 'numeric_role') if kind == 'reference' else ('qualification', 'installed_versions'))
        _stage_descriptor(row['qualification'])
        need(type(row['installed_versions']) is dict and all(type(k) is str and type(v) is str and v for k, v in row['installed_versions'].items()), 'literal independently supplied installed versions')
    need(e['worker_environments']['reference']['numeric_role'] in ('r1', 'r2'), 'one fixed numerical implementation')
    need(same(e['worker_environments']['reference']['installed_versions'], {'numpy': '2.2.6', 'scipy': '1.15.3', 'sklearn': '1.6.1'}), 'original numerical package contract')
    exact(e['issuer'], ('worker_limits', 'sandbox'))
    _stage_limits(e['issuer']['worker_limits'], s['whole_limits']['seconds'])
    for key in _STAGE_COUNTS:
        need(e['issuer']['worker_limits'][key] <= s['issuer_limits'][key], 'issuer worker fits its independent share')
    sandbox = e['issuer']['sandbox']
    exact(sandbox, ('platform', 'machine', 'minimum_landlock_abi', 'memory_bytes', 'cpu_seconds', 'max_open_files'))
    need(sandbox['platform'] == 'Linux' and sandbox['machine'] in ('x86_64', 'aarch64'), 'supported concrete issuer ABI')
    for key in ('minimum_landlock_abi', 'memory_bytes', 'cpu_seconds', 'max_open_files'):
        integer(sandbox[key], 1)
    need(sandbox['minimum_landlock_abi'] >= 3, 'Landlock truncate/right coverage')
    _stage_descriptor(e['external_observer'])
    return e, desc


def stage_select_run(ctx, payload):
    exact(payload, ('input', 'selection'))
    need(ctx.run is None, 'select-run cannot reset a selected run')
    inputs, input_desc = _stage_input(ctx, payload['input'])
    selected, selection_desc, run = _stage_selection(ctx, payload['selection'], inputs)
    ctx.recheck()
    run_desc = ctx.select_run(run)
    operands = ctx.write('P', 'selection/OPERANDS.json', {'schema': 'neural081_portable_run_operands_v1', 'task_id': _STAGE_TASK, 'construction': ctx.construction, 'source': ctx.parent, 'run': run_desc, 'input': input_desc, 'execution_selection': selection_desc})
    requests = {'schema': 'neural081_portable_role_requests_v1', 'task_id': _STAGE_TASK, 'source': ctx.parent, 'source_files': ctx.source_files, 'run': run_desc, 'input': input_desc, 'execution_selection': selection_desc, 'roles': list(_STAGE_ROLES), 'request_binding': 'later-independent-exact-request-v1', 'qualification_emitted': False}
    result = ctx.write('P', 'selection/ROLE_REQUESTS.json', requests)
    ctx.recheck()
    return {'run': run_desc, 'operands': operands, 'role_requests': result, 'qualified': False}


def stage_bind_environment(ctx, payload):
    exact(payload, ('records',))
    need(ctx.run is not None, 'selected original run required')
    e, origin = _stage_environment_records(ctx, payload['records'])
    inputs, input_desc = _stage_input(ctx)
    s, selection_desc, _ = _stage_selection(ctx, input_row=inputs)
    numeric = _stage_fixed(ctx, 'neural081/parent/references/' + e['worker_environments']['reference']['numeric_role'] + '/numeric.py')
    manifests = {}
    # All external qualifications are checked before publishing any bundle.
    for kind in ('preparation', 'reference', 'issuer', 'grader'):
        row = e['worker_environments'][kind]
        manifests[kind] = ctx.worker_manifest(kind, row['qualification'], row['installed_versions'], numeric_source=numeric if kind == 'reference' else None)
    ctx.recheck()
    published = {('preparation_source' if kind == 'preparation' else kind): ctx.write('P', 'environment/' + kind.upper() + '-SOURCE.json', value) for kind, value in manifests.items()}
    for kind, value in (('native_config', e['native']), ('provider_config', e['provider']), ('preparation', inputs['preparation'])):
        published[kind] = ctx.write('P', 'environment/' + kind.upper() + '.json', value)
    bundle = {'schema': 'neural081_portable_environment_binding_v1', 'task_id': _STAGE_TASK, 'source': ctx.parent, 'central_source': ctx.source, 'run': ctx.run_descriptor, 'input': input_desc, 'execution_selection': selection_desc, 'environment_records': origin, 'artifacts': published, 'numeric_source': numeric}
    output = ctx.write('P', 'environment/BINDING.json', bundle)
    ctx.recheck()
    return {'environment': output, 'artifacts': published, 'qualification_generated': False}


def _stage_environment(ctx, desc):
    _stage_path_descriptor(desc, ctx.run_root / 'environment/BINDING.json')
    bundle = ctx.read(desc, scope='operator')
    _stage_object(bundle, 'neural081_portable_environment_binding_v1', ('schema', 'task_id', 'source', 'central_source', 'run', 'input', 'execution_selection', 'environment_records', 'artifacts', 'numeric_source'))
    bound = _stage_bound_run(ctx)
    for key, expected in (('source', ctx.parent), ('central_source', ctx.source), ('run', ctx.run_descriptor), ('input', bound['input']), ('execution_selection', bound['execution_selection'])):
        need(same(bundle[key], expected), 'exact environment binding ' + key)
    e, environment_desc = _stage_environment_records(ctx)
    need(same(bundle['environment_records'], environment_desc), 'same immutable selected environment record')
    inputs, _ = _stage_input(ctx)
    numeric = _stage_fixed(ctx, 'neural081/parent/references/' + e['worker_environments']['reference']['numeric_role'] + '/numeric.py')
    need(same(bundle['numeric_source'], numeric), 'same fixed numerical source')
    a = bundle['artifacts']
    exact(a, ('preparation_source', 'preparation', 'reference', 'issuer', 'grader', 'native_config', 'provider_config'))
    # Reconstruct every role from earlier exact records; a descriptor in the
    # bundle cannot silently substitute another generated configuration.
    expected = {'preparation': inputs['preparation'], 'native_config': e['native'], 'provider_config': e['provider']}
    names = {'preparation': 'PREPARATION.json', 'native_config': 'NATIVE_CONFIG.json', 'provider_config': 'PROVIDER_CONFIG.json'}
    for kind in ('preparation', 'reference', 'issuer', 'grader'):
        row = e['worker_environments'][kind]
        name = 'preparation_source' if kind == 'preparation' else kind
        expected[name] = ctx.worker_manifest(kind, row['qualification'], row['installed_versions'], numeric_source=numeric if kind == 'reference' else None)
        names[name] = kind.upper() + '-SOURCE.json'
    for name in expected:
        _stage_path_descriptor(a[name], ctx.run_root/'environment'/names[name])
        need(same(ctx.read(a[name], scope='operator'), expected[name]), 'complete exact environment artifact ' + name)
    return bundle, e, inputs


def _stage_registry_templates(ctx, desc):
    path = canonical(desc['path'])
    need(path.is_relative_to(ctx.run_root / 'authority'), 'selected run authority namespace')
    r = ctx.read(_stage_descriptor(desc), scope='operator')
    exact(r, ('schema', 'source', 'run', 'templates', 'issuers', 'selected_actual'))
    need(r['schema'] == 'neural081_qualification_registry_v1' and r['selected_actual'] is True and same(r['source'], ctx.parent) and same(r['run'], ctx.run_descriptor), 'actual separately issued source/run registry')
    exact(r['templates'], _STAGE_ROLES); exact(r['issuers'], _STAGE_ROLES)
    templates = {}
    for role in _STAGE_ROLES:
        td = _stage_descriptor(r['templates'][role])
        need(canonical(td['path']).is_relative_to(ctx.run_root / 'authority'), 'only protected selected role metadata')
        t = ctx.read(td, scope='operator')
        exact(t, ('schema', 'role', 'source', 'run', 'issuer', 'status', 'phases', 'actors', 'request_binding', 'conditions'))
        need(t['schema'] == 'neural081_qualification_template_v1' and t['role'] == role and t['status'] == 'qualified' and same(t['source'], ctx.parent) and same(t['run'], ctx.run_descriptor), 'actual template source/run/role')
        need(type(r['issuers'][role]) is list and t['issuer'] in r['issuers'][role], 'externally admitted role issuer')
        need(type(t['phases']) is list and len(set(t['phases'])) == len(t['phases']) and set(t['phases']) == set(_STAGE_PHASES), 'complete phase coverage')
        need(type(t['actors']) is list and len(set(t['actors'])) == len(t['actors']) and set(t['actors']) <= set(_STAGE_ACTORS) and {'controller', 'outer'} <= set(t['actors']), 'actual whole-program actor coverage')
        need(t['request_binding'] == 'later-independent-exact-request-v1' and type(t['conditions']) is dict and t['conditions'], 'acyclic nonempty independent conditions')
        templates[role] = t['conditions']
    need(templates['access'].get('policy') == 'single_query_transductive_v4' and templates['access'].get('statistical_semantic_reviewer') is None, 'matched query adaptation without hidden reviewer')
    return r, templates


def _stage_join(conditions, role, key, value):
    need(same(conditions[role].get(key), value), 'independent ' + role + '/' + key + ' join')


def stage_bind_channel(ctx, payload):
    exact(payload, ('environment', 'registry'))
    bundle, e, inputs = _stage_environment(ctx, payload['environment'])
    _, q = _stage_registry_templates(ctx, payload['registry'])
    a = bundle['artifacts']
    s, _, _ = _stage_selection(ctx, input_row=inputs)
    _stage_join(q, 'input', 'preparation_selection', a['preparation'])
    _stage_join(q, 'native', 'configuration', a['native_config'])
    _stage_join(q, 'native', 'preparation_manifest', a['preparation_source'])
    _stage_join(q, 'native', 'reference_manifest', a['reference'])
    _stage_join(q, 'native', 'grade_manifest', a['grader'])
    _stage_join(q, 'access', 'operative_numeric_source', bundle['numeric_source'])
    _stage_join(q, 'physical_custody', 'issuer_manifest', a['issuer'])
    _stage_join(q, 'physical_custody', 'issuer_sandbox', e['issuer']['sandbox'])
    for key in ('ordinary_controller_descriptor_only', 'one_persistent_current_fd_issuer', 'candidate_namespace_qualified'):
        need(q['physical_custody'].get(key) is True, 'actual physical qualification: ' + key)
    for role in ('observer', 'physical_custody'):
        _stage_join(q, role, 'host_python', e['host']['parent_python'])
        _stage_join(q, role, 'host_environment', e['host']['host_environment'])
    _stage_join(q, 'observer', 'entry', ctx.parent_document['entry'])
    _stage_join(q, 'provider', 'configuration', a['provider_config'])
    _stage_join(q, 'provider', 'launch_credential_name', e['provider']['api_key_env'])
    _stage_join(q, 'provider', 'resolved_ip', e['provider']['resolved_ip'])
    _stage_join(q, 'provider', 'tokenizer_qualification', e['provider']['tokenizer_contract']['qualification'])
    need(q['provider'].get('exact_plain_chat_framing') is True, 'real tokenizer/framing qualification')
    # Grade manifest/native and all later exact request receipts are checked by
    # the unchanged G5/runtime path as well; no future receipt is manufactured.
    ctx.recheck()
    dirs = ctx.channel_directories()
    exact(dirs, ('request_root', 'response_root'))
    need(dirs == {'request_root': str(ctx.run_root/'channel/requests'), 'response_root': str(ctx.run_root/'channel/responses')}, 'exact source-owned channel directories')
    channel = {**dirs, **s['channel'], 'registry': payload['registry'], 'source': ctx.parent, 'run': ctx.run_descriptor}
    controller = {'schema': 'neural081_complete_controller_v1', 'source': ctx.parent, 'run': ctx.run_descriptor, 'channel': channel, 'output_root': str(Path(s['outputs']['output'])/'parent-controller'), 'protected_roots': inputs['preparation']['protected_roots'], 'native_config': a['native_config'], 'preparation': a['preparation'], 'preparation_manifest': a['preparation_source'], 'reference_manifest': a['reference'], 'issuer_manifest': a['issuer'], 'issuer_worker_limits': e['issuer']['worker_limits'], 'issuer_sandbox': e['issuer']['sandbox'], 'host_python': e['host']['parent_python'], 'host_environment': e['host']['host_environment'], 'provider_config': a['provider_config'], 'replication_seeds': s['replication_seeds'], 'public_protocol': ctx.source_text('neural081/protocol/CANDIDATE_PROTOCOL.txt'), 'tool_source': _stage_fixed(ctx, 'neural081/parent/program/reference_tools.py'), 'candidate_runner': _stage_fixed(ctx, 'neural081/parent/program/candidate_runner.py'), 'numeric_source': bundle['numeric_source'], 'grade_manifest': a['grader'], 'grade_worker_io': s['worker_io']['grade'], 'host_metadata_capacity_bytes': s['worker_io']['host_metadata_capacity_bytes']}
    exact(controller, _STAGE_CONTROLLER_KEYS)
    out = ctx.write('P', 'controller/CONTROLLER.json', controller)
    ctx.recheck()
    return {'controller': out, 'channel': channel, 'future_receipts_required': True}


def _stage_controller_body(ctx, c):
    """Reconstruct every controller field from independently selected inputs.

    Metadata custody does not excuse a free-form translated controller. These
    checks precede the original request constructor and all later admissions.
    """
    exact(c, _STAGE_CONTROLLER_KEYS)
    inputs, _ = _stage_input(ctx)
    s, _, _ = _stage_selection(ctx, input_row=inputs)
    e, _ = _stage_environment_records(ctx)
    numeric = _stage_fixed(ctx, 'neural081/parent/references/' + e['worker_environments']['reference']['numeric_role'] + '/numeric.py')
    values = {'preparation': inputs['preparation'], 'native_config': e['native'], 'provider_config': e['provider']}
    names = {'preparation': 'PREPARATION.json', 'native_config': 'NATIVE_CONFIG.json', 'provider_config': 'PROVIDER_CONFIG.json'}
    for kind in ('preparation', 'reference', 'issuer', 'grader'):
        row = e['worker_environments'][kind]
        name = {'preparation': 'preparation_manifest', 'reference': 'reference_manifest', 'issuer': 'issuer_manifest', 'grader': 'grade_manifest'}[kind]
        values[name] = ctx.worker_manifest(kind, row['qualification'], row['installed_versions'], numeric_source=numeric if kind == 'reference' else None)
        names[name] = kind.upper() + '-SOURCE.json'
    artifacts = {name: {'path': str(ctx.run_root/'environment'/names[name]), **pin(encode(value))} for name, value in values.items()}
    for name, value in values.items():
        need(same(c[name], artifacts[name]), 'exact translated artifact identity ' + name)
        need(same(ctx.read(c[name], scope='operator'), value), 'actual translated artifact body ' + name)
    channel = c['channel']
    exact(channel, ('request_root', 'response_root', 'maximum_response_bytes', 'poll_seconds', 'registry', 'source', 'run'))
    _stage_registry_templates(ctx, channel['registry'])
    expected_channel = {'request_root': str(ctx.run_root/'channel/requests'), 'response_root': str(ctx.run_root/'channel/responses'), **s['channel'], 'registry': channel['registry'], 'source': ctx.parent, 'run': ctx.run_descriptor}
    expected = {'schema': 'neural081_complete_controller_v1', 'source': ctx.parent, 'run': ctx.run_descriptor, 'channel': expected_channel, 'output_root': str(Path(s['outputs']['output'])/'parent-controller'), 'protected_roots': inputs['preparation']['protected_roots'], **artifacts, 'issuer_worker_limits': e['issuer']['worker_limits'], 'issuer_sandbox': e['issuer']['sandbox'], 'host_python': e['host']['parent_python'], 'host_environment': e['host']['host_environment'], 'replication_seeds': s['replication_seeds'], 'public_protocol': ctx.source_text('neural081/protocol/CANDIDATE_PROTOCOL.txt'), 'tool_source': _stage_fixed(ctx, 'neural081/parent/program/reference_tools.py'), 'candidate_runner': _stage_fixed(ctx, 'neural081/parent/program/candidate_runner.py'), 'numeric_source': numeric, 'grade_worker_io': s['worker_io']['grade'], 'host_metadata_capacity_bytes': s['worker_io']['host_metadata_capacity_bytes']}
    need(same(c, expected), 'complete literal controller translation, no free-form substitutions')
    return s


def _stage_controller(ctx, desc):
    _stage_path_descriptor(desc, ctx.run_root/'controller/CONTROLLER.json')
    c = ctx.read(desc, scope='operator')
    s = _stage_controller_body(ctx, c)
    return c, s


def stage_request_launch(ctx, payload):
    exact(payload, ('controller',))
    c, s = _stage_controller(ctx, payload['controller'])
    request = ctx.parent_call('outer.launch_request', ctx.parent, c, str(Path(s['outputs']['output'])/'parent-outer'), ctx.parent_document['entry'], s['bootstrap_read_cap'], ctx.run)
    ctx.recheck()
    d = ctx.write('P', 'launch/REQUEST.json', request)
    ctx.recheck()
    return {'request': d, 'authority_required': True, 'envelope_not_yet_issued': True}


def _stage_envelope_from_request(ctx, request_desc, authority_desc):
    _stage_path_descriptor(request_desc, ctx.run_root/'launch/REQUEST.json')
    request = ctx.read(request_desc, scope='operator')
    exact(request, ('schema', 'source_manifest', 'controller', 'outer_output', 'controller_entry', 'bootstrap_read_cap', 'run', 'original_origin', 'normal_endpoint'))
    _stage_controller_body(ctx, request['controller'])
    expected = ctx.parent_call('outer.launch_request', ctx.parent, request['controller'], request['outer_output'], ctx.parent_document['entry'], request['bootstrap_read_cap'], ctx.run)
    need(same(request, expected) and same(request['run'], ctx.run_descriptor), 'complete unchanged independently materializable request')
    s, _, _ = _stage_selection(ctx)
    need(request['outer_output'] == str(Path(s['outputs']['output'])/'parent-outer') and request['controller']['output_root'] == str(Path(s['outputs']['output'])/'parent-controller') and request['bootstrap_read_cap'] == s['bootstrap_read_cap'], 'selected output and bootstrap geometry')
    _stage_descriptor(authority_desc)
    need(canonical(authority_desc['path']).is_relative_to(ctx.run_root/'authority'), 'independently issued selected authority namespace')
    return {'schema': 'neural081_selected_execution_envelope_v2', 'source_manifest': ctx.parent, 'controller': request['controller'], 'launch_request': request_desc, 'outer_authority': authority_desc, 'outer_output': request['outer_output'], 'controller_entry': ctx.parent_document['entry'], 'bootstrap_read_cap': request['bootstrap_read_cap']}


def _stage_admit_envelope(ctx, envelope, desc):
    _stage_controller_body(ctx, envelope['controller'])
    selected, q = ctx.parent_call('outer.admit_launch', envelope, desc, ctx.parent, ctx.source_files, ctx.run, ctx.stage_budget())
    c = envelope['controller']
    _stage_join(q, 'observer', 'entry', ctx.parent_document['entry'])
    _stage_join(q, 'observer', 'host_python', c['host_python'])
    _stage_join(q, 'observer', 'host_environment', c['host_environment'])
    _stage_join(q, 'provider', 'configuration', c['provider_config'])
    provider = ctx.read(c['provider_config'], scope='operator')
    _stage_provider(provider)
    _stage_join(q, 'provider', 'launch_credential_name', provider['api_key_env'])
    need(provider['api_key_env'] not in c['host_environment'], 'no credential value in stored environment')
    return selected, q, provider


def stage_bind_launch(ctx, payload):
    exact(payload, ('request', 'authority'))
    envelope = _stage_envelope_from_request(ctx, payload['request'], payload['authority'])
    preview = {'path': str(ctx.run_root/'launch/ENVELOPE.json'), **pin(encode(envelope))}
    _stage_admit_envelope(ctx, envelope, preview)
    ctx.recheck()
    d = ctx.write('P', 'launch/ENVELOPE.json', envelope)
    need(same(d, preview), 'actual final envelope bytes equal admitted payload')
    ctx.recheck()
    return {'envelope': d, 'runtime_executed': False}


def _stage_registry(ctx, desc, require_qualified=True):
    _stage_path_descriptor(desc, ctx.root/'benchmarks/neuroscience/neural-081/manifest.json')
    doc = ctx.read(desc, scope='source', cap=2**20)
    need(type(doc) is dict and doc.get('id') == _STAGE_TASK, 'single current task registry')
    need(type(doc.get('program_execution')) is dict and type(doc.get('program_conditions')) is dict, 'complete program registrations')
    exact(doc['program_conditions'], ('full10_instructed_excerpt_v1',))
    freeze = ctx.instance['source_freeze']
    expected_freeze = {**freeze, 'path': str(Path(freeze['path']).relative_to(ctx.root))}
    for condition in _STAGE_CONDITIONS:
        record = doc['program_execution'] if condition == 'default' else doc['program_conditions'][condition]
        need(type(record) is dict and same(record.get('entrypoint'), ctx.route(condition)), 'exact literal source-owned route')
        need(same(record.get('source_freeze'), expected_freeze), 'exact complete72 source freeze')
    if require_qualified:
        need(ctx.generic_qualification(doc) is True, 'actual generic qualification before operands')
    return {'descriptor': desc, 'document': doc}


def stage_bind_route(ctx, payload):
    exact(payload, ('current_registry', 'records'))
    registry = _stage_registry(ctx, payload['current_registry'], False)
    exact(payload['records'], ('receipt', 'qualification', 'source_binding'))
    originals = {}
    # All three source operands are captured before any publication. References
    # inside them are checked by the real generic helper, never rewritten.
    for role, d in payload['records'].items():
        originals[role] = ctx.read(_stage_descriptor(d), scope='operator', cap=2**21)
    ctx.recheck()
    copies = []
    for role in ('receipt', 'qualification', 'source_binding'):
        d = payload['records'][role]
        copied = ctx.import_record(d, 'Q', role + '-' + d['sha256'] + '.json')
        exact(copied, ('origin', 'copy'))
        need(same(copied['origin'], d) and copied['copy']['bytes'] == d['bytes'] and copied['copy']['sha256'] == d['sha256'], 'exact byte-preserving qualification import')
        copies.append({'role': role, **copied})
    verification = {'status': 'passed'}
    for row in copies:
        verification[row['role'] + '_path'] = str(Path(row['copy']['path']).relative_to(ctx.root))
        verification[row['role'] + '_sha256'] = row['copy']['sha256']
    new = json.loads(encode(registry['document']))
    new['program_execution']['verification'] = verification
    new['program_conditions']['full10_instructed_excerpt_v1']['verification'] = verification
    need(ctx.generic_qualification(new) is True, 'real exact72 source/control/terminal joins')
    generation_hash = pin(encode(new))['sha256']
    preimage = ctx.import_record(payload['current_registry'], 'V', generation_hash + '/PREIMAGE.json')
    exact(preimage, ('origin', 'copy'))
    need(same(preimage['origin'], payload['current_registry']) and preimage['copy']['bytes'] == preimage['origin']['bytes'] and preimage['copy']['sha256'] == preimage['origin']['sha256'], 'byte-identical registry preimage archive')
    generation = ctx.write('V', generation_hash + '/GENERATION.json', new)
    plan = {'schema': 'neural081_portable_registry_transaction_v1', 'task_id': _STAGE_TASK, 'construction': ctx.construction, 'source': ctx.source, 'registry_path': str(ctx.root/'benchmarks/neuroscience/neural-081/manifest.json'), 'preimage': payload['current_registry'], 'preimage_archive': preimage['copy'], 'generation': generation, 'record_copies': copies}
    transaction = ctx.write('V', generation_hash + '/TRANSACTION.json', plan)
    ctx.recheck()
    return {'transaction': transaction, 'generation': generation, 'registry_activated': False}


def _stage_transaction(ctx, desc):
    _stage_descriptor(desc)
    vroot = ctx.root/'neural081/registry-generations'
    need(canonical(desc['path']).is_relative_to(vroot), 'only designated local registry transaction')
    plan = ctx.read(desc, scope='V')
    _stage_object(plan, 'neural081_portable_registry_transaction_v1', ('schema', 'task_id', 'construction', 'source', 'registry_path', 'preimage', 'preimage_archive', 'generation', 'record_copies'))
    need(same(plan['construction'], ctx.construction) and same(plan['source'], ctx.source), 'exact selected immutable source transaction')
    need(plan['registry_path'] == str(ctx.root/'benchmarks/neuroscience/neural-081/manifest.json'), 'one source-owned mutable registry path')
    _stage_path_descriptor(plan['preimage'], plan['registry_path'])
    for key in ('preimage_archive', 'generation'):
        _stage_descriptor(plan[key]); need(canonical(plan[key]['path']).is_relative_to(vroot), 'immutable V record')
    need(plan['preimage_archive']['bytes'] == plan['preimage']['bytes'] and plan['preimage_archive']['sha256'] == plan['preimage']['sha256'], 'exact preimage identity retained')
    old = ctx.read(plan['preimage'], scope='source')
    archive = ctx.read(plan['preimage_archive'], scope='V')
    new = ctx.read(plan['generation'], scope='V')
    need(same(old, archive), 'current preimage exact archived body')
    need(type(plan['record_copies']) is list and [x.get('role') for x in plan['record_copies']] == ['receipt', 'qualification', 'source_binding'], 'exact three imported records')
    verification = {'status': 'passed'}
    for row in plan['record_copies']:
        exact(row, ('role', 'origin', 'copy'))
        for key in ('origin', 'copy'):
            _stage_descriptor(row[key])
        need(row['origin']['bytes'] == row['copy']['bytes'] and row['origin']['sha256'] == row['copy']['sha256'], 'unchanged issuer bytes')
        need(canonical(row['copy']['path']).parent == ctx.here/'runtime-qualification', 'fixed Q import')
        ctx.read(row['copy'], scope='Q', cap=2**21)
        verification[row['role']+'_path'] = str(Path(row['copy']['path']).relative_to(ctx.root))
        verification[row['role']+'_sha256'] = row['copy']['sha256']
    expected = json.loads(encode(old))
    expected['program_execution']['verification'] = verification
    expected['program_conditions']['full10_instructed_excerpt_v1']['verification'] = verification
    need(same(expected, new), 'only real verification fields may change')
    need(ctx.generic_qualification(new) is True, 'actual unchanged source and generic qualification at activation')
    ctx.recheck()
    return plan


def stage_activate_route(ctx, payload):
    exact(payload, ('transaction',))
    plan = _stage_transaction(ctx, payload['transaction'])
    # This future explicitly selected operation is not exercised successfully by
    # construction controls. The concrete owner CAS retains uncertain failures.
    result = ctx.activate_registry(plan)
    ctx.recheck()
    return result


def _stage_gate_admit(ctx, condition, declaration, registry, review=None, operands=None):
    selection = _stage_descriptor(ctx.instance['selection'])
    need(type(review) is dict and type(operands) is dict, 'actual gate receives review metadata and four literal operands')
    gate_ctx = ctx.gate_context(review=review, invocation_operands=operands)
    return ctx.local_gate.admit(gate_ctx, condition, declaration, selection, registry)


def _stage_review_core(ctx, review, registry, program):
    _stage_object(review, 'neural081_portable_central_review_v1', _STAGE_REVIEW_KEYS)
    s, _, _ = _stage_selection(ctx)
    e, _ = _stage_environment_records(ctx)
    roots = {key: _stage_roots(ctx, key) for key in ('operator', 'protected', 'secret', 'raw')}
    expected = {'condition': s['condition'], 'central_source': ctx.source, 'parent_source': ctx.parent, 'construction': ctx.construction, 'registry': registry['descriptor'], 'program': program, 'run': ctx.run_descriptor, 'origin': ctx.run['origin'], 'normal_endpoint': ctx.run['normal_endpoint'], 'central_limits': s['central_limits'], 'total_limits': s['total_limits'], 'external_limits': s['external_limits'], 'memory': s['memory'], 'roots': roots, 'launch': {'python': e['host']['parent_python'], 'parent_entry': ctx.parent_document['entry'], 'cwd': '/', 'host_environment': e['host']['host_environment'], 'credential_name': e['provider']['api_key_env'], 'inherited_address_space_bytes': s['memory']['address_space_bytes']}}
    for key, value in expected.items():
        need(same(review[key], value), 'complete selected review ' + key)
    exact(review['local_declaration'], ('request', 'selection'))
    need(same(review['local_declaration']['selection'], ctx.instance['selection']), 'exact local source selection')
    _stage_descriptor(review['local_declaration']['request'])
    _stage_path_descriptor(program, ctx.run_root/'launch/ENVELOPE.json')
    envelope = ctx.read(program, scope='operator')
    _, q, provider = _stage_admit_envelope(ctx, envelope, program)
    need(envelope['outer_output'] == str(Path(s['outputs']['output'])/'parent-outer') and envelope['controller']['output_root'] == str(Path(s['outputs']['output'])/'parent-controller'), 'full selected output geometry')
    need(same(envelope['controller']['host_environment'], review['launch']['host_environment']) and envelope['controller']['host_python'] == review['launch']['python'] and provider['api_key_env'] == review['launch']['credential_name'], 'original outer/central clean credential boundary')
    return s, e


def stage_request_review(ctx, payload):
    exact(payload, ('envelope', 'registry', 'declaration'))
    registry = _stage_registry(ctx, payload['registry'])  # before any envelope
    s, _, _ = _stage_selection(ctx)
    e, _ = _stage_environment_records(ctx)
    review = {'schema': 'neural081_portable_central_review_v1', 'task_id': _STAGE_TASK, 'condition': s['condition'], 'central_source': ctx.source, 'parent_source': ctx.parent, 'construction': ctx.construction, 'registry': payload['registry'], 'program': payload['envelope'], 'run': ctx.run_descriptor, 'local_declaration': {'request': payload['declaration'], 'selection': ctx.instance['selection']}, 'origin': ctx.run['origin'], 'normal_endpoint': ctx.run['normal_endpoint'], 'central_limits': s['central_limits'], 'total_limits': s['total_limits'], 'external_limits': s['external_limits'], 'memory': s['memory'], 'roots': {key: _stage_roots(ctx, key) for key in ('operator', 'protected', 'secret', 'raw')}, 'launch': {'python': e['host']['parent_python'], 'parent_entry': ctx.parent_document['entry'], 'cwd': '/', 'host_environment': e['host']['host_environment'], 'credential_name': e['provider']['api_key_env'], 'inherited_address_space_bytes': s['memory']['address_space_bytes']}}
    # Actual gate admission needs the complete declaration/roots/program view
    # and all four operands. At this prequalification stage the review operand
    # identifies the forthcoming immutable payload, not an approved invocation.
    token = pin(encode(review))['sha256']
    operands = {'program': payload['envelope']['path'], 'output': s['outputs']['output'], 'review': str(ctx.here/'operator-selections'/('review-payload-' + token + '.json')), 'other_reserve_bytes': str(integer(s['memory']['other_reserve_bytes']))}
    _stage_gate_admit(ctx, s['condition'], payload['declaration'], registry, review, operands)
    _stage_review_core(ctx, review, registry, payload['envelope'])
    ctx.recheck()
    token = pin(encode(review))['sha256']
    d = ctx.write('R', 'review-payload-' + token + '.json', review)
    request = ctx.write('R', 'qualification-request-' + token + '.json', {'schema': 'neural081_portable_capability_request_v1', 'task_id': _STAGE_TASK, 'payload': d, 'source': ctx.source, 'run': ctx.run_descriptor, 'required_capability_names': sorted(_STAGE_CAPABILITIES), 'qualification_generated': False})
    ctx.recheck()
    return {'payload': d, 'qualification_request': request, 'qualified': False}


def _stage_qualification(ctx, desc, review):
    _stage_descriptor(desc)
    need(canonical(desc['path']).parent == ctx.here/'operator-selections' and desc['bytes'] <= 65536 and Path(desc['path']).name != 'APPROVAL_REGISTRY.json', 'exact source-local central qualification')
    q = ctx.read(desc, scope='R', cap=65536)
    exact(q, ('schema', 'status', 'selected_actual', 'issuer', 'binding', 'capabilities'))
    need(q['schema'] == 'neural081_central_launch_qualification_v1' and q['status'] == 'qualified' and q['selected_actual'] is True and same(q['binding'], review) and same(q['capabilities'], _STAGE_CAPABILITIES), 'actual independently issued exact capability record')
    need(type(q['issuer']) is str and q['issuer'], 'literal independent issuer identity')
    return q


def stage_publish_review(ctx, payload):
    exact(payload, ('payload', 'qualification'))
    _stage_descriptor(payload['payload'])
    need(canonical(payload['payload']['path']).parent == ctx.here/'operator-selections', 'fixed direct-child review payload')
    review = ctx.read(payload['payload'], scope='R', cap=32768)
    _stage_object(review, 'neural081_portable_central_review_v1', _STAGE_REVIEW_KEYS)
    registry = _stage_registry(ctx, review['registry'])
    s, _, _ = _stage_selection(ctx)
    operands = {'program': review['program']['path'], 'output': s['outputs']['output'], 'review': payload['payload']['path'], 'other_reserve_bytes': str(integer(review['memory']['other_reserve_bytes']))}
    _stage_gate_admit(ctx, review['condition'], review['local_declaration']['request'], registry, review, operands)
    _stage_review_core(ctx, review, registry, review['program'])
    _stage_qualification(ctx, payload['qualification'], review)
    final = {**review, 'qualification': payload['qualification']}
    need(len(encode(final)) <= 32768, 'original bounded final review')
    token = pin(encode(final))['sha256']
    ctx.recheck()
    d = ctx.write('R', 'review-' + token + '.json', final)
    request = ctx.write('P', 'commands/approval-request-' + token + '.json', {'schema': 'neural081_portable_approval_request_v1', 'task_id': _STAGE_TASK, 'review': d, 'qualification': payload['qualification'], 'approval_registry_path': str(ctx.here/'operator-selections/APPROVAL_REGISTRY.json'), 'approval_generated': False})
    ctx.recheck()
    return {'review': d, 'approval_request': request, 'approved': False}


def stage_admit_approved_review(ctx, payload):
    exact(payload, ('review', 'approval'))
    _stage_descriptor(payload['review'])
    need(canonical(payload['review']['path']).parent == ctx.here/'operator-selections' and Path(payload['review']['path']).name != 'APPROVAL_REGISTRY.json', 'fixed direct-child final review')
    review = ctx.read(payload['review'], scope='R', cap=32768)
    exact(review, (*_STAGE_REVIEW_KEYS, 'qualification'))
    base = {key: value for key, value in review.items() if key != 'qualification'}
    registry = _stage_registry(ctx, review['registry'])
    s, _ = _stage_review_core(ctx, base, registry, review['program'])
    q = _stage_qualification(ctx, review['qualification'], base)
    _stage_path_descriptor(payload['approval'], ctx.here/'operator-selections/APPROVAL_REGISTRY.json')
    approval = ctx.read(payload['approval'], scope='R', cap=131072)
    exact(approval, ('schema', 'selected_actual', 'allowed_issuers', 'reviews'))
    need(approval['schema'] == 'neural081_protected_central_approvals_v1' and approval['selected_actual'] is True and type(approval['allowed_issuers']) is list and q['issuer'] in approval['allowed_issuers'], 'actual independent protected approval issuer')
    need(type(approval['reviews']) is dict and same(approval['reviews'].get(payload['review']['sha256']), {'review': payload['review'], 'qualification': review['qualification']}), 'exact final review/qualification approved')
    other = integer(review['memory']['other_reserve_bytes'])
    operands = {'program': review['program']['path'], 'output': s['outputs']['output'], 'review': payload['review']['path'], 'other_reserve_bytes': str(other)}
    first = _stage_gate_admit(ctx, review['condition'], review['local_declaration']['request'], registry, review, operands)
    environment, _ = _stage_environment_records(ctx)
    argv = ctx.actual_argv(review['condition'], operands['program'], operands['output'], operands['review'], other, python=environment['host']['central_python'])
    ctx.recheck()
    registry2 = _stage_registry(ctx, review['registry'])
    second = _stage_gate_admit(ctx, review['condition'], review['local_declaration']['request'], registry2, review, operands)
    environment, _ = _stage_environment_records(ctx)
    planned = ctx.local_gate.plan(first, second, argv, str(ctx.root), environment['host']['central_python'])
    need(planned.get('actual_invocation_observed') is False, 'planned command is not an observed invocation')
    command = {'schema': 'neural081_portable_invocation_v1', 'task_id': _STAGE_TASK, 'review': payload['review'], 'approval': payload['approval'], 'registry': review['registry'], 'source': ctx.source, 'condition': review['condition'], 'template': ctx.route(review['condition']), 'argv': argv, 'cwd': str(ctx.root), 'other_condition_requires_its_own_review': True, 'command_emitted_only': True, 'process_invoked': False, 'natural_exit_observed': False, 'independent_original_outer_observation_required': True}
    d = ctx.write('P', 'commands/invocation-' + payload['review']['sha256'] + '.json', command)
    ctx.recheck()
    return {'invocation': d, 'runtime_executed': False}


def stage_respond(ctx, payload):
    exact(payload, ('intent', 'authority'))
    intent = ctx.read(_stage_descriptor(payload['intent']), scope='operator')
    exact(intent, ('schema', 'sequence', 'source', 'source_files', 'run', 'request', 'phase', 'actor', 'registry', 'statistical_semantic_verdict_requested'))
    need(intent['schema'] == 'neural081_operator_metadata_request_v1' and intent['statistical_semantic_verdict_requested'] is False, 'actual source-owned channel intent, no statistical verdict')
    sequence = integer(intent['sequence'], 0, 4)
    need(intent['phase'] == _STAGE_PHASES[sequence] and intent['actor'] == 'controller', 'literal five controller requests in source order')
    need(same(intent['source'], ctx.parent) and same(intent['source_files'], ctx.source_files) and same(intent['run'], ctx.run_descriptor), 'complete exact source/run channel identity')
    name = '%06d-%s-%s.json' % (sequence, intent['phase'], intent['actor'])
    _stage_path_descriptor(payload['intent'], ctx.run_root/'channel/requests'/name)
    _stage_registry_templates(ctx, intent['registry'])
    selected = ctx.read(_stage_descriptor(payload['authority']), scope='operator')
    need(canonical(payload['authority']['path']).is_relative_to(ctx.run_root/'authority'), 'already issued protected authority only')
    need(same(selected.get('registry'), intent['registry']) and same(selected.get('run'), ctx.run_descriptor), 'same independent registry and run')
    ctx.parent_call('authority.admit', selected, ctx.parent, intent['request'], intent['phase'], intent['actor'], ctx.stage_budget(), ctx.source_files, protected_roots=_stage_roots(ctx, 'protected'))
    response = {'schema': 'neural081_operator_metadata_response_v1', 'sequence': sequence, 'intent': payload['intent'], 'authority': selected}
    s, _, _ = _stage_selection(ctx)
    need(len(encode(response)) <= s['channel']['maximum_response_bytes'], 'exact original response cap')
    ctx.recheck()
    d = ctx.write('P', 'channel/responses/' + name, response)
    ctx.recheck()
    return {'response': d, 'authority_issued_by_constructor': False}


STAGES = {'select-run': stage_select_run, 'bind-environment': stage_bind_environment, 'bind-channel': stage_bind_channel, 'request-launch': stage_request_launch, 'bind-launch': stage_bind_launch, 'bind-route': stage_bind_route, 'activate-route': stage_activate_route, 'request-review': stage_request_review, 'publish-review': stage_publish_review, 'admit-approved-review': stage_admit_approved_review, 'respond': stage_respond}
