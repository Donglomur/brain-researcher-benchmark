"""Positive inactive-by-default selection; every actual cost profile is external."""
from core import need, integer, finite, canonical, disjoint, descriptor
from contracts import TASK, PROFILE, GATES, modules

ROOTS = ('source', 'packet', 'targets', 'reference', 'output', 'operator', 'observation', 'secrets', 'store')
HOST_LIMITS = ('source_bytes', 'authority_bytes', 'qualification_bytes', 'packet_bytes', 'view_bytes',
               'producer_bytes', 'journal_bytes', 'event_bytes', 'array_bytes', 'state_bytes', 'selection_bytes',
               'host_read_bytes', 'host_write_bytes', 'native_inventory_bytes', 'native_response_bytes',
               'max_operations', 'max_output_files', 'failure_bytes', 'record_bytes', 'index_bytes', 'host_live_bytes')
PHASE_LIMITS = ('seconds', 'cpu_ns', 'cpu_rate_ns', 'qualified_enforcement_lag_seconds', 'retirement_seconds',
                'memory_bytes', 'pids', 'output_bytes', 'scratch_bytes',
                'numeric_read_bytes', 'numeric_write_bytes', 'numeric_serialized_bytes', 'numeric_allocation_bytes',
                'numeric_live_bytes', 'numeric_elements', 'numeric_work', 'numeric_files')


def validate(a, source_pin):
    need(type(a) is dict and a.get('schema') == 'neural049_execution_authority_v1'
         and a.get('active') is True, 'not qualified: source construction only')
    need(a['task_id'] == TASK and a['profile'] == PROFILE and a['source_manifest'] == source_pin,
         'exact existing task/profile/source authority')
    modules(a['modules']); need(type(a['cache']) is bool, 'explicit cache execution plan')
    need(set(a['roots']) == set(ROOTS), 'complete physical namespace selection')
    need(canonical(a['roots']['targets']) == canonical(a['roots']['packet'])/'private',
         'fixed protected prepared-label subtree; never a public operand')
    roots = [canonical(a['roots'][k]) for k in ROOTS if k != 'targets']
    need(all(disjoint(x, y) for i, x in enumerate(roots) for y in roots[i+1:]), 'lexically disjoint roots')
    c = a['clock']
    need(set(c) == {'origin', 'production_end', 'observation_end', 'readback_end'}
         and finite(c['origin']) < finite(c['production_end']) < finite(c['observation_end']) < finite(c['readback_end']),
         'one original monotonic clock across all phases')
    for k in HOST_LIMITS: integer(a['resources'][k], 1)
    for name in ('reference_fit', 'reference_predict', 'reference_select', 'actor_fit', 'actor_predict', 'analysis', 'audit'):
        row = a['profiles'][name]
        for k in PHASE_LIMITS:
            if k in ('seconds', 'qualified_enforcement_lag_seconds', 'retirement_seconds'):
                need(finite(row[k]) > 0, 'positive phase elapsed allowance')
            else: integer(row[k], 1)
    for name in ('global_author', 'case'):
        p = a['provider_profiles'][name]
        for k in ('provider_calls', 'tokens', 'per_response_tokens', 'request_bytes', 'response_bytes', 'steps', 'numeric_values'):
            integer(p[k], 1)
        need(finite(p['seconds']) > 0 and finite(p['money']) > 0, 'complete provider profile')
        ep = a['episode_limits'][name]
        integer(ep['native_cpu_ns'],1); need(finite(ep['gpu_device_seconds']) >= 0, 'complete episode CPU/GPU envelope')
    for key in ('public', 'private'):
        n = a['native_' + key]
        need(n['api'] == 'v1.47' and n['image_id'].startswith('sha256:') and len(n['image_id']) == 71,
             'immutable qualified engine image')
        canonical(n['socket']); need(n['study'] and n['uid_gid'].split(':')[0] != '0', 'isolated study and unprivileged worker')
        need(type(n['gpu_ids']) is list and len(n['gpu_ids']) == len(set(n['gpu_ids'])), 'explicit selected GPU devices')
        for field in ('whole_cpu_ns', 'whole_gpu_device_seconds', 'operations', 'whole_output_quota_bytes'):
            need(finite(n[field]) >= (0 if field == 'whole_gpu_device_seconds' else 1), 'prospective whole native and retirement bounds')
        expected_root = a['roots']['reference' if key == 'private' else 'output']
        need(canonical(n['output_root']) == canonical(expected_root)
             and canonical(n['whole_output_quota_root']) == canonical(expected_root)
             and n['whole_output_quota_qualified'] is True and n['enforcement_lag_qualified'] is True,
             'exact independently qualified role output/quota/lag custody')
    need(set(a['qualifications']) == set(GATES), 'all twenty gate dispositions required')
    need(a['grading']['selected'] is False, 'production never predicts its future outer completion')
    need(type(a['method_admissions']) is dict and type(a['operator_identity']) is str and a['operator_identity'],
         'concrete protected semantic admission namespace')
    descriptor(a['packet']['complete']['pin']); descriptor(a['bank']['manifest']['pin'])
    need(canonical(a['packet']['root']) == canonical(a['roots']['packet']), 'exact fixed protected packet root')
    need(a['preparation_context']['origin'] == c['origin'] and a['preparation_context']['deadline'] == c['readback_end'],
         'selected original helper accounting clock')
    need(a['provider']['wire_protocol'] == 'neural049_chat_json_v1', 'exact provider wire contract')
    need(type(a['host_environment']) is dict and all(type(k) is str and type(v) is str
         for k,v in a['host_environment'].items()), 'exact qualified caller environment strings')
    canonical(a['host_python'])
    software = a['actor_environment_inventory']
    need(type(software) is dict and set(software) == {'schema','image_id','python','libraries','study_values_included'}
         and software['schema'] == 'neural049_actor_software_inventory_v1'
         and software['image_id'] == a['native_public']['image_id'] and software['study_values_included'] is False
         and type(software['python']) is str and software['python']
         and type(software['libraries']) is dict and 'numpy' in software['libraries']
         and all(type(k) is str and type(v) is str and k and v for k,v in software['libraries'].items()),
         'qualified concrete software-only inventory shared by F/I before values')
    for field in ('absolute','relative'):
        need(finite(a['reference_tolerance'][field]) >= 0, 'preselected finite numerical tolerance')
    descriptor(a['seed_contract']); descriptor(a['numerical_contract'])
    need(type(a['base_generation']) is str and a['base_generation'], 'exact original/D shared base generation')
    for impl in ('r1','r2'):
        env = a['numerical_environments'][impl]
        need(env['qualified'] is True and env['shared_monotonic_domain'] is True
             and env['deterministic_algorithms'] is True, 'actual qualified complete numerical environment')
        need(type(env['receipt']) is str and len(env['receipt']) == 64, 'independent numerical environment receipt identity')
    return a
