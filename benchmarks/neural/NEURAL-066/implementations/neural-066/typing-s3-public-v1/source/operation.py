"""Root-selected immutable operation/qualification and complete resource admission."""
import math
from pathlib import Path
import operator_policy
from core import CONDITIONS, MODES, descriptor, encoded, exact, expected_counts, identity, need, positive
from safe_io import capture, child, strict
SCHEMA = 'neural066_complete_operation_v1'
ROLES = ('A', 'B', 'reference', 'operator')
QUALIFICATIONS = ('input_membership', 'geometry', 'native_environment', 'reference_environment', 'provider_environment', 'candidate_environment', 'process_custody', 'source_exposure', 'method_admission')

def read_document(root, desc, cap, meter):
    exact(desc, ('path', 'bytes', 'sha256'))
    return strict(meter.read_file(child(root, desc['path']), {k: desc[k] for k in ('bytes', 'sha256')}, cap))

def admit(op, authority, root, *, meter):
    need(op['schema'] == SCHEMA and authority['schema'] == 'neural066_root_execution_authority_v1', 'Exact operation/authority schemas')
    need(authority['task'] == 'NEURAL-066' and authority['selected_operation_sha256'] == identity(op) and (authority['actual_operation_selected'] is True), 'Explicit independent root operation authority; source grant cannot execute')
    need(authority['public_export_selected'] is False and op['task'] == 'NEURAL-066', 'No implicit publication')
    need(op['scope'] == {'MEG_people': 19, 'EEG_people': 20, 'timelines': 143, 'assets': 329, 'cases': 78, 'candidate_contexts': 936, 'R2_fits': 5928, 'reference_fits': 6474, 'prediction_contexts': 1794, 'contrasts': 164}, 'Unchanged complete scientific scope')
    need(op['modes'] == list(MODES) and op['conditions'] == list(CONDITIONS), 'Both full modes and matched conditions')
    need(set(op['qualification']) == set(QUALIFICATIONS), 'Every independent future qualification operand')
    for scope, d in op['qualification'].items():
        need(d == authority['reviewed_qualification'][scope], 'Exact root-selected independent qualification pin')
        q = read_document(root, d, op['metadata']['json_bytes'],meter)
        need(q['schema'] == 'neural066_external_qualification_v1' and q['task'] == 'NEURAL-066' and (q['scope'] == scope) and (q['accepted'] is True) and (q['source_lock'] == op['source_lock']) and q['evidence'] and (q['reviewer_role'] == 'independent_operator'), 'Independent source-bound qualification, not worker assertion')
        need(q['environment_identity'] == op['environment_identity'], 'Exact actual environment binding')
    need(op['source_manifest']['path']==str(Path(op['source_root'])/'SOURCE_MANIFEST.json'),'Exact source-owned manifest location')
    manifest=read_document(op['source_root'],{'path':'SOURCE_MANIFEST.json',**op['source_lock']},op['metadata']['json_bytes'],meter)
    rd=manifest['files']['ROLE_SOURCES.json'];roles=read_document(op['source_root'],{'path':'ROLE_SOURCES.json',**rd},op['metadata']['json_bytes'],meter)
    need(roles['schema']=='neural066_closed_role_sources_v1' and op['sources_by_role']==roles['roles'],'Closed source-owned exact role inventories, not arbitrary caller subsets')
    for files in roles['roles'].values():
        need(all(manifest['files'][name]==d for name,d in files.items()),'All role members join full authenticated source closure')
    need(set(op['sources_by_role']) == set(ROLES), 'Exact source inventory for every role')
    for role, files in op['sources_by_role'].items():
        need(files and all((type(p) is str and '..' not in Path(p).parts for p in files)), 'Closed source inventory')
        for d in files.values():
            descriptor(d)
        if role in ('A', 'B'):
            need(not any((any((x in p.lower() for x in ('reference/', 'author/', 'protected_score', 'independent_score', 'preparation.py', 'dependency-scout'))) for p in files)), 'No private/operator/author reference bodies in candidate program image view')
    need(op['source_lock'] == authority['source_lock'] and op['environment_identity'] == authority['environment_identity'], 'Root-selected full source/environment, not mutable claims')
    native = op['native_inputs']
    selected = native.get('membership_policy')
    need(type(selected) is dict and set(selected) == {'path','bytes','sha256'},
         'Required reviewed operator membership policy is missing')
    expected = authority.get('reviewed_membership_policy')
    operator_policy.descriptor(expected)
    need({k:selected[k] for k in ('bytes','sha256')} == expected,
         'Exact independent root membership-policy selection')
    policy = operator_policy.validate(read_document(native['root'], selected, op['metadata']['json_bytes'], meter))
    for kind in ('cohort','logs','loader'):
        need({k:native[kind][k] for k in ('bytes','sha256')} == policy['asset_pins'][kind],
             'Exact original operator artifact identity from reviewed policy')
    for name in ('investigation_policy', 'language_policy', 'contrasts', 'gates'):
        need(op[name] == authority['reviewed_policy'][name], 'Independent precommitted exact ' + name)
    need(op['contrasts']['sha256'] == authority['adopted_contrasts_sha256'] and op['gates']['sha256'] == authority['adopted_gates_sha256'], 'Full adopted immutable roster/gates, not arbitrary caller replacement')
    return reservation(op)

def transport_compatibility(op):
    """Declared physical route, not a hypothetical GPU or measured host peak."""
    need(op['reference_device'] == 'cpu', 'Current concrete transport admits CPU only; CUDA requires a separately implemented/qualified device-custody successor')
    provider_memory = positive(op['model_transport']['resources']['memory_bytes'], 'Full provider-container memory reservation')
    tool_memory = positive(op['tool_limits']['memory_bytes'], 'Full simultaneous preliminary-worker memory reservation')
    need(op['phase_limits']['candidate_author']['memory_bytes'] >= provider_memory + tool_memory, 'Episode memory envelope covers concurrently live provider and one preliminary worker; not aggregate host RSS')
    return {'reference_device': 'cpu', 'candidate_author_container_memory_floor': provider_memory + tool_memory, 'actual_host_feasibility_qualified': False}

def reservation(op):
    transport_compatibility(op)
    counts = expected_counts()
    need(set(op['phase_limits']) == set(counts), 'Every logical phase has a full profile')
    T = positive(op['candidate']['max_preliminary_tools'], 'Shared finite tool cap')
    need(T >= 2, 'The same shared T includes both mandatory post-seal policy realms')
    positive(op['candidate']['max_provider_turns'], 'Finite provider turn cap')
    for k in ('source_bytes', 'recipe_bytes', 'model_bytes', 'request_bytes', 'response_bytes', 'transcript_bytes', 'max_source_files'):
        positive(op['candidate'][k], 'Finite complete candidate artifact ceiling')
    positive(op['metadata']['json_bytes'], 'Metadata cap')
    positive(op['metadata']['event_bytes'], 'Journal cap')
    read = write = retained = wall = 0
    for action, count in counts.items():
        p = op['phase_limits'][action]
        for k in ('read_bytes', 'write_bytes', 'retained_bytes', 'output_bytes', 'memory_bytes', 'array_bytes', 'live_array_bytes', 'max_output_files', 'producer_read_bytes', 'producer_write_bytes', 'producer_retained_bytes'):
            positive(p[k], action + ' ' + k)
        need(type(p['wall_seconds']) in (int, float) and math.isfinite(p['wall_seconds']) and (p['wall_seconds'] > 0), 'Phase wall')
        need(p['read_bytes'] >= p['producer_read_bytes'] and p['write_bytes'] >= p['producer_write_bytes'] >= p['producer_retained_bytes'] >= p['output_bytes'], 'Whole independent producer cost reservation')
        need(p['retained_bytes'] >= p['producer_retained_bytes'] >= p['output_bytes'] and p['write_bytes'] >= p['retained_bytes'], 'Full phase retention and write support')
        read += count * p['read_bytes']
        write += count * p['write_bytes']
        retained += count * p['retained_bytes']
        wall += count * p['wall_seconds']
    tool = op['tool_limits']
    for k in ('read_bytes', 'write_bytes', 'retained_bytes', 'output_bytes', 'memory_bytes', 'array_bytes', 'live_array_bytes', 'max_output_files', 'producer_read_bytes', 'producer_write_bytes', 'producer_retained_bytes'):
        positive(tool[k], 'Complete nested tool cap')
    need(tool['read_bytes'] >= tool['producer_read_bytes'] and tool['write_bytes'] >= tool['producer_write_bytes'] >= tool['producer_retained_bytes'] >= tool['output_bytes'] and (tool['write_bytes'] >= tool['retained_bytes'] >= tool['producer_retained_bytes']) and (tool['wall_seconds'] > 0), 'Complete nested producer/read/write/retained resources')
    read += 936 * T * tool['read_bytes']
    write += 936 * T * tool['write_bytes']
    retained += 936 * T * tool['retained_bytes']
    wall += 936 * T * tool['wall_seconds']
    shape = op['full_shape_reservation']
    for k in ('original_bytes', 'projection_bytes', 'reference_view_bytes', 'candidate_view_bytes', 'model_and_checkpoints_bytes', 'largest_live_array_bytes', 'largest_attention_bytes', 'concurrent_stage_bytes'):
        positive(shape[k], 'Full selected shape/graph reservation')
    need(shape['original_bytes'] == 187980093465 and shape['reference_views'] == 468 and (shape['candidate_views'] == 936) and (shape['cases'] == 78), 'Complete original/private/public view counts')
    required_shape = shape['original_bytes'] + shape['projection_bytes'] + shape['reference_view_bytes'] + shape['candidate_view_bytes'] + shape['model_and_checkpoints_bytes']
    retained = max(retained, required_shape) + shape['original_bytes'] + shape['concurrent_stage_bytes'] + op['metadata']['retained_control_bytes']
    write += op['metadata']['retained_control_bytes']
    read += op['metadata']['read_control_bytes']
    wall += op['cleanup_seconds'] + op['host_finish_seconds']
    for k in ('retained_control_bytes', 'read_control_bytes', 'host_control_memory_bytes', 'max_events'):
        positive(op['metadata'][k], 'Whole retained control/ledger bound')
    need(op['metadata']['max_events'] >= sum(counts.values()) * 2 + 936 * T, 'All fixed start/end and nested tool ledger events')
    limits = op['controller_limits']
    for k in ('outer_limits', 'controller_limits'):
        need(set(op[k]) == {'wall_seconds', 'read_bytes', 'write_bytes', 'retained_bytes'} and op[k]['wall_seconds'] == op['limits']['wall_seconds'], 'Partitions share original clock; no resets')
    for k in ('read_bytes', 'write_bytes', 'retained_bytes'):
        need(op['outer_limits'][k] + op['controller_limits'][k] <= op['limits'][k], 'Disjoint global parent/child allocation')
    need(limits['read_bytes'] >= read and limits['write_bytes'] >= write and (limits['retained_bytes'] >= retained) and (limits['wall_seconds'] >= wall), 'Prospective full11306+936*T reservation, never reduced cohort')
    need(op['host_memory_bytes'] >= shape['largest_live_array_bytes'] + op['metadata']['host_control_memory_bytes'], 'Whole host arrays/control memory ceiling')
    need(op['phase_limits']['r2_inner']['memory_bytes'] >= shape['largest_attention_bytes'] and op['phase_limits']['r2_final']['memory_bytes'] >= shape['largest_attention_bytes'], 'Complete full-sequence reference attention profile')
    return {'schema': 'neural066_complete_reservation_v1', 'fixed_logical_phases': sum(counts.values()), 'nested_tool_jobs_max': 936 * T, 'read_upper': read, 'write_upper': write, 'retained_upper': retained, 'wall_upper': wall, 'shape_plan': shape, 'physical_IO_or_RSS_certified': False}
