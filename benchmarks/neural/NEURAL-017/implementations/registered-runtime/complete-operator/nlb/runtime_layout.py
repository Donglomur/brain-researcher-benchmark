"""Concrete NEURAL-017 deployment layout; no science, credentials or API calls.

Compilation is pure. Preparation is an explicitly separate future operator
action: exclusive directories and bounded Store publication only. Neither
operation creates a containment/storage qualification or an execution authority.
"""
import copy
import os
from collections import Counter
from pathlib import PurePosixPath
from .contracts import (Budget, Custody, Handles, Store, canonical, closed,
                        descriptor, digest, integer, need, relative)
from .runtime_policy import PROFILES, tool_variant_profile
from .worker_runtime import receipt_limits


SELECTION_KEYS = {'programme', 'run_id', 'store_root', 'output_parent',
                  'metadata_parent', 'jobs', 'process_census', 'profiles',
                  'gateway_jobs'}
PATH_KEYS = SELECTION_KEYS - {'gateway_jobs'}
PROFILE_KEYS = {'source', 'authority', 'selected_pins', 'static_inputs',
                'mounts', 'bwrap', 'rootfs', 'rootfs_qualification',
                'cgroup_parent', 'scratch_parent', 'memory_bytes', 'pids',
                'cpu_quota_us', 'cpu_period_us', 'scratch_bytes',
                'runtime_environment', 'python_executable', 'stream_limit',
                'max_product_bytes', 'worker_io_limits', 'completion_io_limits',
                'worker_receipt_limits', 'dynamic_input_limits'}
JOB_KEYS = {'job', 'stage', 'role', 'parent_group', 'runtime_profile'}
MODEL_MOUNT_ROLES = {'engine_source', 'gateway_config', 'operator_authority',
                     'gateway_qualification', 'output'}
ENV_KEYS = {'PATH', 'PYTHONPATH', 'LANG', 'LC_ALL', 'OMP_NUM_THREADS',
            'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'}


def _absolute(value):
    need(type(value) is str and value != '/' and value.startswith('/') and
         str(PurePosixPath(value)) == value, 'canonical absolute deployment path')
    relative(value[1:])
    return value


def _text(value, label):
    need(type(value) is str and value and '\0' not in value and
         all(ord(c) >= 32 and ord(c) != 127 for c in value), label)
    return value


def _pins(rows):
    need(type(rows) is list, 'finite selected descriptor list')
    paths = {}
    for pin in rows:
        descriptor(pin)
        need(pin['path'] not in paths or paths[pin['path']] == pin,
             'one selected identity per artifact path')
        paths[pin['path']] = pin
    return paths


def _unique_pins(rows):
    out = []
    for pin in rows:
        if pin not in out:
            out.append(copy.deepcopy(pin))
    _pins(out)
    return out


def _profile(name, profile):
    need(name in PROFILES, 'original runtime profile')
    closed(profile, PROFILE_KEYS | ({'gateway_transport'} if name == 'model_gateway' else set()))
    for key in ('source', 'authority', 'bwrap', 'rootfs_qualification'):
        descriptor(profile[key])
    selected = _pins(profile['selected_pins'])
    need(profile['rootfs_qualification'] in list(selected.values()),
         'selected actual rootfs qualification descriptor')
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
        need(profile['gateway_transport']['qualification'] in list(selected.values()),
             'selected actual gateway transport qualification')


def _path_selection(selection):
    need(type(selection) is dict and set(selection) in (PATH_KEYS, SELECTION_KEYS),
         'closed path or complete runtime selection')
    _text(selection['programme'], 'explicit programme identity')
    _text(selection['run_id'], 'explicit unique operator run identity')
    _absolute(selection['store_root'])
    relative(selection['output_parent']); relative(selection['metadata_parent'])
    need(type(selection['jobs']) is list and selection['jobs'], 'finite ordered job roster')
    need(type(selection['profiles']) is dict and selection['profiles'], 'closed selected profiles')
    for name, profile in selection['profiles'].items():
        need(name in PROFILES and type(profile) is dict and
             {'cgroup_parent', 'scratch_parent'} <= set(profile), 'selected profile roots')
        if set(selection) == PATH_KEYS:
            closed(profile, {'cgroup_parent', 'scratch_parent'})
        for key in ('cgroup_parent', 'scratch_parent'):
            _absolute(profile[key])
        need(profile['cgroup_parent'].startswith('/sys/fs/cgroup/'), 'delegated cgroup parent')
    need(type(selection['process_census']) is dict and selection['process_census'],
         'explicit selected process census')
    for group, count in selection['process_census'].items():
        _text(group, 'group identity'); integer(count, 1)
    seen = set(); actual = Counter(); leaves = []
    for job in selection['jobs']:
        closed(job, JOB_KEYS)
        for key in ('job', 'stage', 'role', 'parent_group'):
            _text(job[key], 'explicit job ' + key)
        need(job['job'] not in seen, 'one original top-level process slot')
        seen.add(job['job']); actual[job['parent_group']] += 1
        variants = job['runtime_profile']
        if job['role'] == 'participant_tool':
            need(job['stage'] in ('S07', 'S08', 'S09'), 'original tool stage')
            closed(variants, {'reference_predict'} if job['stage'] == 'S07'
                   else {'run_python', 'reference_predict'})
            participant = variants.get('run_python', 'participant_A')
            for kind, profile in variants.items():
                tool_variant_profile(kind, participant, profile)
                leaves.append((job, kind, profile))
        else:
            need(type(variants) is str, 'one ordinary physical profile')
            if job['role'] == 'model_exchange':
                need(variants == 'model_gateway', 'actual model gateway profile')
            else:
                need(variants != 'model_gateway', 'model profile is not a scientific worker')
            if job['role'] == 'source_syntax':
                need(job['stage'] == 'S01' and variants == 'reference_producer',
                     'pre-data source syntax profile')
            leaves.append((job, '', variants))
    need(dict(actual) == selection['process_census'], 'exact original top-level lifetime census')
    need({profile for _, _, profile in leaves} == set(selection['profiles']),
         'exact selected profile roster without unused profiles')
    return leaves


def _selection(selection):
    closed(selection, SELECTION_KEYS)
    leaves = _path_selection(selection)
    for name, profile in selection['profiles'].items():
        _profile(name, profile)
    need(type(selection['gateway_jobs']) is dict and set(selection['gateway_jobs']) ==
         {j['job'] for j in selection['jobs'] if j['role'] == 'model_exchange'},
         'exact concrete gateway job config census')
    for binding in selection['gateway_jobs'].values():
        closed(binding, {'config_pin'}); descriptor(binding['config_pin'])
    return leaves


def runtime_paths(selection):
    """Derive all future paths and exact source-owned manifest descriptors.

No directories or qualification reports are inspected or created here. The
returned paths are the targets for genuine later per-path qualifications.
"""
    leaves = _path_selection(selection)
    namespace = 'nlb017-' + digest(canonical({'programme': selection['programme'],
                                            'run_id': selection['run_id']}))
    output_namespace = selection['output_parent'] + '/' + namespace + '-outputs'
    metadata_namespace = selection['metadata_parent'] + '/' + namespace + '-metadata'
    entries = []; seen = set()
    for job, variant, profile_name in leaves:
        profile = selection['profiles'][profile_name]
        token = digest(canonical({'job': job['job'], 'variant': variant, 'profile': profile_name}))
        need(token not in seen, 'unique deterministic physical invocation'); seen.add(token)
        output_body = canonical({'schema': 'NLB017_mount_tree_v1', 'role': 'output', 'files': []})
        def pin(suffix, body):
            return {'path': metadata_namespace + '/' + token + suffix,
                    'bytes': len(body), 'sha256': digest(body)}
        output_prefix = output_namespace + '/' + token
        paths = {'output_prefix': output_prefix,
                 'output_root': selection['store_root'] + '/' + output_prefix,
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
        entries.append({'token': token, 'job': job['job'], 'role': job['role'], 'variant': variant,
                        'runtime_profile': profile_name, 'paths': paths,
                        'output_manifest': pin('.output.json', output_body),
                        'static_manifest_path': metadata_namespace + '/' + token + '.static.json'})
    geometry = {key: copy.deepcopy(selection[key]) for key in PATH_KEYS - {'profiles'}}
    geometry['profiles'] = {name: {key: value[key] for key in ('cgroup_parent', 'scratch_parent')}
                            for name, value in selection['profiles'].items()}
    return {'schema': 'NLB017_runtime_paths_v1', 'namespace': namespace,
            'path_selection_sha256': digest(canonical(geometry)),
            'output_namespace': output_namespace, 'metadata_namespace': metadata_namespace,
            'entries': entries}


class LayoutPreparation:
    """Caller owns this original carrier before any directory effect."""
    def __init__(self):
        self.custody = Custody('runtime_layout_preparation')
        self.layout = None
        self.manifests = {}
        self.started = False
        self.paths_complete = False
        self.mounts_started = False
        self.mounts_complete = False
        self.selection_sha256 = None
        self.static_inputs = {}

    def snapshot(self):
        return {'layout': self.layout, 'manifests': copy.deepcopy(self.manifests),
                'paths_complete': self.paths_complete, 'mounts_complete': self.mounts_complete,
                'selection_sha256': self.selection_sha256,
                'custody': self.custody.snapshot(), 'no_cleanup_or_rollback': True}


def prepare_paths(store, selection, preparation):
    """Exclusively prepare directories and publish exact empty-output manifests.

All profile/output/metadata ancestors must already exist. Existing run/job
directories are a refusal. On failure the caller's preparation retains every
attempt and original failure; no path is removed and this object cannot retry.
"""
    need(type(store) is Store and type(preparation) is LayoutPreparation,
         'actual bounded Store and caller-owned original preparation')
    need(not preparation.started, 'one original preparation attempt')
    preparation.started = True
    owner = preparation.custody
    try:
        layout = runtime_paths(selection); preparation.layout = layout
        need(str(store.root) == selection['store_root'], 'exact selected artifact Store root')
        scoped = Store(store.root, store.budget, owner)
        def mkdir(parent_store, name):
            relative(name); parent_store.budget.admit()
            event = {'path': str(parent_store.root) + '/' + name,
                     'effect': 'not_attempted', 'created': False}
            owner.events.append(event); handles = Handles(owner)
            try:
                parent_store.budget.reserve('created_files', 1)
                parent, leaf = parent_store.parent(name, handles)
                event['effect'] = 'attempted_unknown'
                os.mkdir(leaf, mode=0o700, dir_fd=parent)
                event['created'] = True; event['effect'] = 'created'
                parent_store.budget.charge('created_files', 1)
                os.fsync(parent)
            except BaseException as error:
                owner.fail(error, 'exclusive_layout_directory')
                parent_store.budget.stop('incomplete original layout preparation')
            finally:
                handles.finish()
            owner.raise_if_failed()
        mkdir(scoped, layout['output_namespace'])
        mkdir(scoped, layout['metadata_namespace'])
        scratch_stores = {}
        for profile in selection['profiles'].values():
            root = profile['scratch_parent']
            if root not in scratch_stores:
                scratch_stores[root] = Store(root, store.budget, owner)
                mkdir(scratch_stores[root], layout['namespace'])
        for entry in layout['entries']:
            mkdir(scoped, entry['paths']['output_prefix'])
            root = selection['profiles'][entry['runtime_profile']]['scratch_parent']
            mkdir(scratch_stores[root], layout['namespace'] + '/' + entry['token'])
        for entry in layout['entries']:
            bodies = {'output_manifest': {'schema': 'NLB017_mount_tree_v1', 'role': 'output', 'files': []}}
            preparation.manifests[entry['token']] = {}
            for key, body in bodies.items():
                raw = canonical(body); expected = entry[key]
                pin = scoped.write(expected['path'], raw, expected['bytes'])
                need(pin == expected, 'exact original generated mount manifest')
                preparation.manifests[entry['token']][key] = pin
        preparation.paths_complete = True; owner.complete = True
    except BaseException as error:
        owner.fail(error, 'runtime_layout_preparation')
    owner.raise_if_failed()
    return preparation


def _static_inputs(selection, entry):
    profile = selection['profiles'][entry['runtime_profile']]
    inputs = copy.deepcopy(profile['static_inputs'])
    if entry['role'] == 'model_exchange':
        config = selection['gateway_jobs'][entry['job']]['config_pin']
        need(all(x['source']['path'] != config['path'] for x in inputs),
             'per-job gateway config has its own static input path')
        inputs.append({'role': 'gateway_config', 'source': copy.deepcopy(config)})
    if entry['role'] == 'source_syntax':
        need(all(x['role'] in {'operator_authority', 'engine_source', 'source_contract'}
                 for x in inputs + profile['mounts']), 'syntax checker has no empirical mounts')
    return inputs


def _static_manifest(selection, entry, inputs):
    raw = canonical({'schema': 'NLB017_input_mount_set_v1', 'programme': selection['programme'],
                     'job': entry['job'], 'files': inputs})
    need(len(raw) <= 16 * 2**20, 'original mounted input manifest read ceiling')
    return raw, {'path': entry['static_manifest_path'], 'bytes': len(raw), 'sha256': digest(raw)}


def prepare_mounts(store, selection, preparation):
    """After actual qualification/authority selection, publish static manifests.

Separating this from directory creation avoids a circular dependency between
fresh scratch roots, actual storage reports and the authority descriptor.
"""
    need(type(store) is Store and type(preparation) is LayoutPreparation,
         'actual bounded Store and caller-owned preparation')
    need(preparation.paths_complete and preparation.custody.complete and
         preparation.custody.first_error is None and not preparation.mounts_started,
         'one original manifest publication after complete path creation')
    preparation.mounts_started = True; owner = preparation.custody; owner.complete = False
    try:
        _selection(selection); layout = runtime_paths(selection)
        need(preparation.layout == layout and str(store.root) == selection['store_root'],
             'final source and authority retain exact prepared geometry')
        preparation.selection_sha256 = digest(canonical(selection))
        scoped = Store(store.root, store.budget, owner)
        for entry in layout['entries']:
            inputs = _static_inputs(selection, entry)
            raw, expected = _static_manifest(selection, entry, inputs)
            pin = scoped.write(expected['path'], raw, expected['bytes'])
            need(pin == expected, 'exact original static input manifest')
            preparation.manifests[entry['token']]['static_manifest'] = pin
            preparation.static_inputs[entry['token']] = inputs
        preparation.mounts_complete = True; owner.complete = True
    except BaseException as error:
        owner.fail(error, 'runtime_static_mount_preparation')
    owner.raise_if_failed()
    return preparation


def compile_runtime_layout(selection, prepared, qualifications):
    """Compile original Executor rows and Campaign contexts, with no I/O.

Qualification rows contain descriptors of actual later reports selected by the
operator. Path equality is checked here; existing Linux validators authenticate
and inspect those original reports before native dispatch.
"""
    _selection(selection); layout = runtime_paths(selection)
    need(type(prepared) is LayoutPreparation and prepared.started and
         prepared.custody.complete and prepared.custody.first_error is None and
         prepared.layout == layout and prepared.mounts_complete and
         prepared.selection_sha256 == digest(canonical(selection)),
         'completed original exact path and static manifest preparation')
    need(type(qualifications) is dict and set(qualifications) ==
         {x['token'] for x in layout['entries']}, 'exact per-path qualification census')
    rows = {}; contexts = {}; by_job = {j['job']: j for j in selection['jobs']}
    selected_pins = {name: _pins(profile['selected_pins'])
                     for name, profile in selection['profiles'].items()}
    for entry in layout['entries']:
        job = by_job[entry['job']]; profile = selection['profiles'][entry['runtime_profile']]
        paths = entry['paths']; selected = qualifications[entry['token']]
        closed(selected, {'paths', 'qualification', 'storage_qualification'})
        need(selected['paths'] == paths, 'genuine qualification selection binds exact generated paths')
        for key in ('qualification', 'storage_qualification'):
            descriptor(selected[key])
            need(selected_pins[entry['runtime_profile']].get(selected[key]['path']) == selected[key],
                 'actual selected qualification descriptor')
        inputs = _static_inputs(selection, entry)
        _, static_manifest = _static_manifest(selection, entry, inputs)
        need(prepared.manifests.get(entry['token']) ==
             {'output_manifest': entry['output_manifest'], 'static_manifest': static_manifest} and
             prepared.static_inputs.get(entry['token']) == inputs,
             'actual original manifest publication descriptors')
        mounts = copy.deepcopy(profile['mounts'])
        mounts += [{'host': selection['store_root'] + '/' + x['source']['path'],
                    'guest': '/inputs/' + x['source']['path'], 'access': 'ro',
                    'role': x['role'], 'manifest': static_manifest,
                    'member': x['source']['path']} for x in inputs]
        mounts.append({'host': paths['output_root'], 'guest': '/output', 'access': 'rw',
                       'role': 'output', 'manifest': entry['output_manifest']})
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
        sandbox.update({'qualification': selected['qualification'],
                        'storage_qualification': selected['storage_qualification'],
                        'cgroup_name': paths['cgroup_name'], 'scratch_root': paths['scratch_root'],
                        'runtime_profile': entry['runtime_profile'], 'mounts': mounts})
        common = {'stage': job['stage'], 'role': job['role'], 'source': profile['source'],
                  'sandbox': sandbox, 'process_limit': selection['process_census'][job['parent_group']],
                  'parent_group': job['parent_group'], 'result_path': paths['result_path']}
        for key in ('stream_limit', 'max_product_bytes', 'worker_io_limits',
                    'completion_io_limits', 'worker_receipt_limits'):
            common[key] = copy.deepcopy(profile[key])
        if job['role'] == 'model_exchange':
            from .openai_gateway import gateway_job
            sandbox['gateway_transport'] = copy.deepcopy(profile['gateway_transport'])
            args = {key: value for key, value in common.items() if key != 'role'}
            row = gateway_job(job=job['job'], **args,
                              config_pin=selection['gateway_jobs'][job['job']]['config_pin'],
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
        if entry['variant']:
            if job['job'] not in rows:
                rows[job['job']] = {key: common[key] for key in
                                    ('stage', 'role', 'parent_group', 'process_limit')}
                rows[job['job']]['tool_variants'] = {}
            rows[job['job']]['tool_variants'][entry['variant']] = copy.deepcopy(row)
            # Authority and protocol are shared by both variants; source is
            # selected by Executor after the actual tool kind is consumed.
            if job['job'] in contexts:
                need(contexts[job['job']] == context, 'one original tool slot worker context')
        else:
            rows[job['job']] = copy.deepcopy(row)
        contexts[job['job']] = context
    return {'schema': 'NLB017_compiled_runtime_layout_v1',
            'selection_sha256': digest(canonical(selection)), 'paths': layout,
            'native_jobs': rows, 'worker_context': contexts}
