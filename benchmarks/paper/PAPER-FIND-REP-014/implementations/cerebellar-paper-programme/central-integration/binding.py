"""Exact future root selection and qualified resource/author-context joins."""
import math
from pathlib import Path
import shutil
from paper_i_central_safety import need, parse, pin, descriptor, ordinary, typed_equal

TASK = 'PAPER-FIND-REP-014'
GATE_READ_RESERVATION = 134217728
RESOURCE_FIELDS = ('global_limits','host','phase_resources','attempt_limits','native_limits','native_matlab')
PROFILE_FIELDS = {'schema','resources','parent_manifest','parent_qualification','images',
    'caller_limits','observer_memory_bytes','worker_memory_bytes','central_finish_seconds',
    'worker_grace_seconds','worker_log_bytes','metadata_cap_bytes','outer_receipt_cap_bytes',
    'receipt_read_bytes','source_copy_retained_bytes','disk_floor_bytes',
    'exclusive_operator_host_custody_verified','full_workload_feasibility_verified'}


def positive(value, label):
    need(type(value) is int and 0 < value <= 2**63-1, 'Positive bounded integer '+label)
    return value


def file_ref(value):
    need(type(value) is dict and set(value) == {'path','bytes','sha256'}, 'Exact external descriptor')
    ordinary(value['path'])
    descriptor({k:value[k] for k in ('bytes','sha256')})
    return value


def ref_pin(value):
    return {k:value[k] for k in ('bytes','sha256')}


def read_ref(io, value, cap):
    file_ref(value)
    return parse(io.read(value['path'], ref_pin(value), cap))


def qualified_profile(profile, operation, parent_pin):
    need(type(profile) is dict and set(profile) == PROFILE_FIELDS and
         profile['schema'] == 'paper_i_central_runtime_profile_v1', 'Complete exact caller profile')
    need(profile['parent_manifest'] == parent_pin, 'Exact qualified immutable parent')
    need(typed_equal(profile['resources'], {k:operation[k] for k in RESOURCE_FIELDS}),
         'Original complete resource policies unchanged')
    need(profile['parent_qualification'] == operation['qualification'] and
         typed_equal(profile['images'], operation['images']), 'Exact qualified image/native runtime evidence')
    need(profile['exclusive_operator_host_custody_verified'] is True and
         profile['full_workload_feasibility_verified'] is True,
         'Independent exclusive host custody and full-workload feasibility qualification')
    integers = PROFILE_FIELDS - {'schema','resources','parent_manifest','parent_qualification','images',
        'caller_limits','exclusive_operator_host_custody_verified','full_workload_feasibility_verified'}
    for name in integers:
        positive(profile[name], name)
    limits = profile['caller_limits']
    need(type(limits) is dict and set(limits) == {'read_bytes','write_bytes','retained_bytes'},
         'Separate complete caller partition')
    for key,value in limits.items():
        positive(value,key)
    need(limits['retained_bytes'] <= limits['write_bytes'], 'Caller retention inside cumulative write ceiling')
    host = operation['host']
    need(profile['worker_memory_bytes'] >= host['parent_memory_bytes'] >= host['controller_memory_bytes'],
         'Original nested hard RLIMIT_AS compatibility')
    need(profile['worker_grace_seconds'] < profile['central_finish_seconds'] < operation['global_limits']['wall_seconds'],
         'Caller cleanup fits original clock')
    need(profile['outer_receipt_cap_bytes'] <= host['parent_limits']['write_bytes'] and
         profile['metadata_cap_bytes'] >= host['max_metadata_bytes'], 'Full parent receipt and metadata bounds')
    p,e,h = host['max_phases'],host['max_events'],profile['metadata_cap_bytes']
    outer_events = 2+p*(3+2*host['recovery']['max_cli_calls'])
    # Conservatively includes duplicate references; raw-cache reuse reduces actual
    # reads, never expands the selected cap. No original numeric array is read here.
    floor = (profile['outer_receipt_cap_bytes'] + (e+outer_events+33)*(h+1)
             + outer_events*(min(h,host['recovery']['max_record_bytes'])+1)
             + p*(8*(h+1)+65537+host['recovery']['max_metadata_bytes'])
             + host['log_bytes']+profile['worker_log_bytes']+131072)
    need(floor <= 2**63-1 and profile['receipt_read_bytes'] >= floor,
         'Complete all-phase receipt read reservation, no small-roster proxy')
    source_floor = 67108864 + host['python']['bytes']  # bounded source/metadata plus exact interpreter body
    need(limits['read_bytes'] >= GATE_READ_RESERVATION+source_floor+profile['receipt_read_bytes'],
         'Caller budget includes independent gate, source and complete receipt reads')
    need(profile['source_copy_retained_bytes'] >= 437883+6012 and
         limits['retained_bytes'] >= profile['source_copy_retained_bytes']+profile['worker_log_bytes']+524288,
         'Full source/log/control retention separately allocated')
    return {'outer_event_upper':outer_events,'receipt_read_floor':floor,
            'whole_read_upper':operation['global_limits']['read_bytes']+limits['read_bytes'],
            'whole_write_upper':operation['global_limits']['write_bytes']+limits['write_bytes'],
            'whole_retained_upper':operation['global_limits']['retained_bytes']+limits['retained_bytes']}


def bind(io, repo, program, review, output, other, qualification, parent):
    repo = ordinary(repo)
    need(type(other) is int and other >= 0, 'Nonnegative unrelated future reserve')
    program, review, output = ordinary(program), ordinary(review), ordinary(output)
    need(review.is_relative_to(repo), 'Root review remains inside repository')
    raw = io.read(review, cap=32768)
    authority_pin = pin(raw)
    authority = parse(raw)
    keys = {'schema','task','authorized','protected_grading_authorized','exclusive_host_custody_verified',
        'selection','operation','output','work','other_future_bytes','qualified_source_freeze_sha256',
        'qualification_sha256','runtime_profile','independent_author_contexts_verified'}
    need(type(authority) is dict and set(authority) == keys and
         authority['schema'] == 'paper_i_central_root_authority_v1' and authority['task'] == TASK,
         'Independent exact complete-operation root authority')
    for flag in ('authorized','protected_grading_authorized','exclusive_host_custody_verified',
                 'independent_author_contexts_verified'):
        need(authority[flag] is True, 'Separate root authorization '+flag)
    need(authority['qualified_source_freeze_sha256'] == qualification['freeze_pin']['sha256'] and
         authority['qualification_sha256'] == qualification['qualification_pin']['sha256'],
         'Root authority binds actual source and runtime qualification')
    need(ordinary(authority['output']) == output and not output.exists(), 'Fresh exact reviewed output')
    file_ref(authority['selection'])
    need(ordinary(authority['selection']['path']) == program, 'Exact program selection operand')
    selected_raw = io.read(program, ref_pin(authority['selection']), 1048576)
    selected = parse(selected_raw)
    need(type(selected) is dict and set(selected) == {'schema','task','operation','author_contexts'} and
         selected['schema'] == 'paper_i_central_selection_v1' and selected['task'] == TASK,
         'Declarative whole programme selection, never executable candidate import')
    need(typed_equal(authority['operation'], selected['operation']), 'Exact root selected original operation')
    operation_raw = io.read(file_ref(selected['operation'])['path'], ref_pin(selected['operation']), 1048576)
    operation = parent.modules['operation'].validate_operation(parse(operation_raw))
    need(ref_pin(operation['source_manifest']) == parent.modules['manifest'], 'Unchanged original parent manifest')
    work_ref = file_ref(authority['work'])
    need(ordinary(work_ref['path']) == repo/'authoring/delivery-20261105/WORK_ASSIGNMENTS.json',
         'Exact current complete WORK authority')
    work = read_ref(io, work_ref, 2097152)
    current = work['latest_construction_state']['global_future_bytes']
    need(type(current) is int and type(authority['other_future_bytes']) is int and
         current == other == authority['other_future_bytes'], 'Current exact unrelated future reservation')
    profile = qualification['document'].get('paper_i_central_runtime_profile')
    need(typed_equal(profile, authority['runtime_profile']), 'Root and independent qualified profile match')
    resource = qualified_profile(profile, operation, parent.modules['manifest'])
    end = io.origin+operation['global_limits']['wall_seconds']
    need(io.tick() < min(io.origin+120, end-profile['central_finish_seconds']),
         'All startup inside original operation and finish reserve')
    attestations = selected['author_contexts']
    need(type(attestations) is list and len(attestations) == 4, 'Exactly four independent authoring contexts')
    seen, ids, records = set(), set(), []
    for ref in attestations:
        raw = io.read(file_ref(ref)['path'], ref_pin(ref), 1048576)
        value = parse(raw)
        fields = {'schema','role','method','context_id','committed_before_numeric','access_condition',
                  'source','commands','configurations'}
        need(type(value) is dict and set(value) == fields and
             value['schema'] == 'paper_i_author_context_v1', 'Exact source author-context record')
        role,method = value['role'],value['method']
        need(role in ('A','B') and method in ('encoding','reconstruction') and (role,method) not in seen,
             'Unique role/method commitment')
        context = value['context_id']
        need(type(context) is str and 0 < len(context.encode()) <= 256 and context not in ids,
             'Four distinct external authoring identities')
        need(value['committed_before_numeric'] is True and value['access_condition'] ==
             ('paper_and_data' if role == 'A' else 'paper_data_official_code'), 'Matched declared code access')
        source = operation['programs'][role]
        commands = ('fit','query') if method == 'encoding' else ('reconstruct',)
        need(typed_equal(value['source'], source['source']) and
             typed_equal(value['commands'], {k:source['commands'][k] for k in commands}) and
             typed_equal(value['configurations'], source['configurations'] if method == 'encoding' else None),
             'Full co-resident source inventory and method-specific argv/configuration commitment')
        seen.add((role,method));ids.add(context);records.append({'value':value,'pin':pin(raw)})
    need(ordinary(operation['programs']['A']['source']['root']) != ordinary(operation['programs']['B']['source']['root']),
         'Separate A/B source packages; not independent authorship proof by itself')
    need(output.parent.is_dir(), 'Existing private output parent')
    needed = resource['whole_retained_upper']+other+profile['disk_floor_bytes']
    need(needed <= 2**63-1 and shutil.disk_usage(output.parent).free >= needed,
         'Full original/caller/unrelated retained allocation and disk floor')
    return {'operation':operation,'operation_raw':operation_raw,'operation_path':selected['operation']['path'],
            'operation_pin':pin(operation_raw),'root_authority':authority_pin,
            'selection_pin':pin(selected_raw),'work_pin':ref_pin(work_ref),'author_contexts':records,
            'profile':profile,'resource':resource,'output':output,'original_end':end,
            'worker_cutoff':end-profile['central_finish_seconds'],'other_future_bytes':other}
