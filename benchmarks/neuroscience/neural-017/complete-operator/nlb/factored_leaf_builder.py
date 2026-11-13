"""Pure single-leaf extraction of the retained expanded runtime layout.

Install this body as nlb/factored_leaf_builder.py. Admission of source/profile
selection and actual preparation is owned by factored_runtime; this module
neither fabricates successful evidence nor performs filesystem or model effects.
"""
import copy

from .contracts import canonical, closed, descriptor, digest, integer, need, relative
from .runtime_layout import JOB_KEYS, PROFILE_KEYS, _absolute, _text, _unique_pins
from .runtime_policy import PROFILES, tool_variant_profile


GEOMETRY_KEYS = {'programme', 'run_id', 'store_root', 'output_parent', 'metadata_parent'}
OPERAND_KEYS = {'qualification', 'storage_qualification', 'output_manifest',
                'static_manifest', 'config_pin'}


def _geometry(geometry, *, with_census=False):
    need(type(geometry) is dict and
         set(geometry) in (GEOMETRY_KEYS, GEOMETRY_KEYS | {'process_census'}),
         'closed original single-leaf geometry')
    _text(geometry['programme'], 'explicit programme identity')
    _text(geometry['run_id'], 'explicit unique operator run identity')
    _absolute(geometry['store_root'])
    relative(geometry['output_parent']); relative(geometry['metadata_parent'])
    if with_census:
        need(type(geometry.get('process_census')) is dict,
             'actual original parent-group census')


def _identity(job, variant, profile_name, profile):
    """Validate one original job/variant, without expanding another slot."""
    closed(job, JOB_KEYS)
    for key in ('job', 'stage', 'role', 'parent_group'):
        _text(job[key], 'explicit job ' + key)
    need(profile_name in PROFILES, 'original runtime profile')
    full_keys = (PROFILE_KEYS - {'selected_pins'}) | (
        {'gateway_transport'} if profile_name == 'model_gateway' else set())
    need(type(profile) is dict and set(profile) in
         ({'cgroup_parent', 'scratch_parent'}, full_keys),
         'closed original path-only or complete fixed profile')
    for key in ('cgroup_parent', 'scratch_parent'):
        _absolute(profile[key])
    need(profile['cgroup_parent'].startswith('/sys/fs/cgroup/'),
         'delegated cgroup parent')
    variants = job['runtime_profile']
    if job['role'] == 'participant_tool':
        need(job['stage'] in ('S07', 'S08', 'S09'), 'original tool stage')
        closed(variants, {'reference_predict'} if job['stage'] == 'S07'
               else {'run_python', 'reference_predict'})
        participant = variants.get('run_python', 'participant_A')
        for kind, selected in variants.items():
            tool_variant_profile(kind, participant, selected)
        need(type(variant) is str and variant in variants and
             variants[variant] == profile_name, 'exact original physical tool variant')
    else:
        need(variant == '' and type(variants) is str and variants == profile_name,
             'exact ordinary physical profile')
        if job['role'] == 'model_exchange':
            need(profile_name == 'model_gateway', 'actual model gateway profile')
        else:
            need(profile_name != 'model_gateway', 'model profile is not a scientific worker')
        if job['role'] == 'source_syntax':
            need(job['stage'] == 'S01' and profile_name == 'reference_producer',
                 'pre-data source syntax profile')


def leaf_paths(geometry, job, variant, profile_name, profile):
    """Return the exact one-entry value formerly appended by runtime_paths.

The expected output-manifest descriptor is a byte recipe, not evidence that
the directory or file has been created. Actual preparation must supply its
original returned descriptor before build_leaf admits it.
"""
    _geometry(geometry); _identity(job, variant, profile_name, profile)
    namespace = 'nlb017-' + digest(canonical({'programme': geometry['programme'],
                                            'run_id': geometry['run_id']}))
    output_namespace = geometry['output_parent'] + '/' + namespace + '-outputs'
    metadata_namespace = geometry['metadata_parent'] + '/' + namespace + '-metadata'
    token = digest(canonical({'job': job['job'], 'variant': variant, 'profile': profile_name}))
    output_body = canonical({'schema': 'NLB017_mount_tree_v1', 'role': 'output', 'files': []})
    output_manifest = {'path': metadata_namespace + '/' + token + '.output.json',
                       'bytes': len(output_body), 'sha256': digest(output_body)}
    output_prefix = output_namespace + '/' + token
    paths = {'output_prefix': output_prefix,
             'output_root': geometry['store_root'] + '/' + output_prefix,
             'scratch_root': profile['scratch_parent'] + '/' + namespace + '/' + token,
             'cgroup_parent': profile['cgroup_parent'],
             'cgroup_name': namespace + '-' + token,
             'result_path': output_prefix + '/RESULT.json',
             'terminal_path': output_prefix + '/TERMINAL.json',
             'dynamic_manifest_path': metadata_namespace + '/' + token + '.inputs.json'}
    for key in ('output_prefix', 'result_path', 'terminal_path', 'dynamic_manifest_path'):
        relative(paths[key])
    for key in ('output_root', 'scratch_root'):
        _absolute(paths[key])
    return {'token': token, 'job': job['job'], 'role': job['role'], 'variant': variant,
            'runtime_profile': profile_name, 'paths': paths,
            'output_manifest': output_manifest,
            'static_manifest_path': metadata_namespace + '/' + token + '.static.json'}


def leaf_static_manifest(geometry, job, profile, paths_entry, config_pin):
    """Return the exact static-manifest bytes/pin and ordered input recipe.

Actual preparation writes these bytes through its bounded Store and compares
the actual returned pin with this expected pin. No report is issued here.
"""
    inputs = copy.deepcopy(profile['static_inputs'])
    if job['role'] == 'model_exchange':
        descriptor(config_pin)
        need(all(x['source']['path'] != config_pin['path'] for x in inputs),
             'per-job gateway config has its own static input path')
        inputs.append({'role': 'gateway_config', 'source': copy.deepcopy(config_pin)})
    else:
        need(config_pin is None, 'only actual model jobs have a gateway config')
    if job['role'] == 'source_syntax':
        need(job['stage'] == 'S01' and paths_entry['runtime_profile'] == 'reference_producer',
             'pre-data source syntax profile')
        need(all(x['role'] in {'operator_authority', 'engine_source', 'source_contract'}
                 for x in inputs + profile['mounts']), 'syntax checker has no empirical mounts')
    raw = canonical({'schema': 'NLB017_input_mount_set_v1', 'programme': geometry['programme'],
                     'job': job['job'], 'files': inputs})
    need(len(raw) <= 16 * 2**20, 'original mounted input manifest read ceiling')
    expected = {'path': paths_entry['static_manifest_path'], 'bytes': len(raw), 'sha256': digest(raw)}
    return raw, expected, inputs


def build_leaf(geometry, job, variant, profile_name, profile, paths_entry, operand):
    """Return (ordinary_native_row, worker_context), with fresh mutable values.

The caller has already authenticated the fixed profile, exact roster census,
actual selected qualification membership and successful original preparation.
This function admits no arbitrary argv, callbacks or per-job resource/profile
overrides. It constructs only the original row and context keys.
"""
    _geometry(geometry, with_census=True)
    closed(profile, (PROFILE_KEYS - {'selected_pins'}) |
           ({'gateway_transport'} if profile_name == 'model_gateway' else set()))
    expected_entry = leaf_paths(geometry, job, variant, profile_name, profile)
    need(paths_entry == expected_entry, 'exact original single-leaf path identity')
    closed(operand, OPERAND_KEYS)
    for key in ('qualification', 'storage_qualification', 'output_manifest', 'static_manifest'):
        descriptor(operand[key])
    paths = paths_entry['paths']
    _, static_manifest, inputs = leaf_static_manifest(
        geometry, job, profile, paths_entry, operand['config_pin'])
    need(operand['output_manifest'] == paths_entry['output_manifest'] and
         operand['static_manifest'] == static_manifest,
         'actual original manifest publication descriptors')
    mounts = copy.deepcopy(profile['mounts'])
    mounts += [{'host': geometry['store_root'] + '/' + x['source']['path'],
                'guest': '/inputs/' + x['source']['path'], 'access': 'ro',
                'role': x['role'], 'manifest': static_manifest,
                'member': x['source']['path']} for x in inputs]
    mounts.append({'host': paths['output_root'], 'guest': '/output', 'access': 'rw',
                   'role': 'output', 'manifest': paths_entry['output_manifest']})
    need(len({x['guest'] for x in mounts}) == len(mounts), 'unique assembled physical mount targets')
    for mount in mounts:
        need(mount['role'] not in ('assessment_target', 'private_ledger') or
             job['role'] in ('protected_score', 'protected_uncertainty', 'raw_prepare'),
             'original protected mount capability')
        need(mount['role'] != 'raw_asset' or job['role'] == 'raw_prepare', 'raw operator capability')
    sandbox = {key: copy.deepcopy(profile[key]) for key in
               ('bwrap', 'rootfs', 'cgroup_parent', 'memory_bytes', 'pids',
                'cpu_quota_us', 'cpu_period_us', 'runtime_environment',
                'rootfs_qualification', 'scratch_bytes')}
    sandbox.update({'qualification': operand['qualification'],
                    'storage_qualification': operand['storage_qualification'],
                    'cgroup_name': paths['cgroup_name'], 'scratch_root': paths['scratch_root'],
                    'runtime_profile': profile_name, 'mounts': mounts})
    census = geometry['process_census']
    need(job['parent_group'] in census, 'original parent-group census membership')
    integer(census[job['parent_group']], 1)
    common = {'stage': job['stage'], 'role': job['role'], 'source': profile['source'],
              'sandbox': sandbox, 'process_limit': census[job['parent_group']],
              'parent_group': job['parent_group'], 'result_path': paths['result_path']}
    for key in ('stream_limit', 'max_product_bytes', 'worker_io_limits',
                'completion_io_limits', 'worker_receipt_limits'):
        common[key] = copy.deepcopy(profile[key])
    if job['role'] == 'model_exchange':
        from .openai_gateway import gateway_job
        sandbox['gateway_transport'] = copy.deepcopy(profile['gateway_transport'])
        args = {key: value for key, value in common.items() if key != 'role'}
        row = gateway_job(job=job['job'], **args, config_pin=operand['config_pin'],
                          python_executable=profile['python_executable'])
    else:
        row = common
        module = 'nlb.authoring_syntax' if job['role'] == 'source_syntax' else 'nlb.worker'
        row['argv'] = [profile['python_executable'], '-B', '-m', module]
        row['input_manifests'] = _unique_pins([m['manifest'] for m in mounts])
        row['dynamic_input_policy'] = {'schema': 'NLB017_exact_current_input_leaves_v1',
                                       **profile['dynamic_input_limits'],
                                       'manifest_path': paths['dynamic_manifest_path']}
    context = {'input_root': '/inputs', 'output_root': '/output',
               'authority': copy.deepcopy(profile['authority']),
               'declared_inputs': [], 'bindings': {}}
    # The expanded route deep-copies each completed row into its returned map.
    # Preserve that ownership boundary without retaining the map itself.
    return copy.deepcopy(row), context


def validate_fixed_profile(name, profile):
    """Validate every original fixed field without inventing selected pins.

Only the original selected_pins list checks and membership assertions are
excluded. Actual preparation still performs those checks against its genuine
selected descriptor collection before admission; a profile hash is not a
substitute for either that admission or these structural checks.
"""
    from .contracts import Budget
    from .runtime_layout import ENV_KEYS, MODEL_MOUNT_ROLES
    from .worker_runtime import receipt_limits

    need(name in PROFILES, 'original runtime profile')
    closed(profile, (PROFILE_KEYS - {'selected_pins'}) |
           ({'gateway_transport'} if name == 'model_gateway' else set()))
    for key in ('source', 'authority', 'bwrap', 'rootfs_qualification'):
        descriptor(profile[key])
    for key in ('rootfs', 'cgroup_parent', 'scratch_parent', 'python_executable'):
        _absolute(profile[key])
    need(profile['cgroup_parent'].startswith('/sys/fs/cgroup/'),
         'delegated Linux cgroup parent')
    for key in ('memory_bytes', 'pids', 'cpu_quota_us', 'cpu_period_us',
                'scratch_bytes', 'stream_limit', 'max_product_bytes'):
        integer(profile[key], 1)
    need(profile['memory_bytes'] <= 16 * 2**30 and profile['pids'] <= 64 and
         profile['cpu_quota_us'] <= 4 * profile['cpu_period_us'] and
         profile['scratch_bytes'] <= 2 * 2**30, 'original matched resource ceilings')
    for key in ('worker_io_limits', 'completion_io_limits'):
        closed(profile[key], Budget.IO_KEYS)
        for value in profile[key].values():
            integer(value)
    receipts = receipt_limits(profile['worker_receipt_limits'])
    need(profile['worker_io_limits']['write_bytes'] >= sum(receipts.values()) and
         profile['worker_io_limits']['created_files'] >= 3,
         'original worker publication capacity')
    closed(profile['dynamic_input_limits'], {'max_files', 'max_bytes'})
    for value in profile['dynamic_input_limits'].values():
        integer(value, 1)
    environment = profile['runtime_environment']
    need(type(environment) is dict and set(environment) <= ENV_KEYS and
         environment.get('PYTHONPATH') == '/programme',
         'closed environment and separately mounted engine source')
    for value in environment.values():
        need(type(value) in (str, int) and '\0' not in str(value), 'literal environment')
    need(type(profile['static_inputs']) is list, 'finite static inputs')
    static_paths = set()
    for item in profile['static_inputs']:
        closed(item, {'role', 'source'}); descriptor(item['source'])
        _text(item['role'], 'static input role')
        need(item['source']['path'] not in static_paths, 'unique static input path')
        static_paths.add(item['source']['path'])
    need(any(x['source'] == profile['authority'] and x['role'] == 'operator_authority'
             for x in profile['static_inputs']), 'actual worker authority is mounted')
    need(type(profile['mounts']) is list, 'finite selected physical mounts')
    targets = set()
    for mount in profile['mounts']:
        closed(mount, {'host', 'guest', 'access', 'role', 'manifest'})
        _absolute(mount['host']); _absolute(mount['guest']); descriptor(mount['manifest'])
        need(mount['access'] == 'ro' and (mount['guest'].startswith('/inputs/') or
             mount['guest'] in ('/programme', '/state_ro')), 'selected read-only profile mount')
        need(mount['guest'] not in targets, 'one physical profile mount per target')
        targets.add(mount['guest']); _text(mount['role'], 'physical mount role')
    need(any(m['role'] == 'engine_source' and m['guest'] == '/programme'
             for m in profile['mounts']), 'separate exact selected engine tree')
    roles = {x['role'] for x in profile['static_inputs']} | {x['role'] for x in profile['mounts']}
    if name.startswith('participant_'):
        need(not roles & {'reference_method_source', 'protected_scorer_source', 'raw_operator_source'},
             'participant source isolation')
        if name == 'participant_A':
            need('curated_code_B' not in roles, 'paper/data arm excludes curated code')
    if name == 'model_gateway':
        need(profile['worker_io_limits']['created_files'] >= 7,
             'concrete OpenAI gateway original seven output slots')
        need(roles <= MODEL_MOUNT_ROLES, 'model gateway has only source and metadata')
        closed(profile['gateway_transport'], {'transport', 'credential', 'qualification'})
        descriptor(profile['gateway_transport']['qualification'])
