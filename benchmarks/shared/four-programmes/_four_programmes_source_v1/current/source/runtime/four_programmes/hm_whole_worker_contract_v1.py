"""Closed, distinct whole-job HM worker wire; compilation creates no authority.

H's actual retained reservation/carrier owns issuance. These routines neither
launch a process nor turn an equal dictionary into an H capability.
"""
from pathlib import Path
from .common import need, closed, integer, descriptor, encode, pin, relative
from .hm_whole_job_profile_v1 import HMWholeJobPlanV1

HM = 'PAPER-paper-method-replacement-016'
BOOTSTRAP_FORMAT_MAXIMUM = 1048576
ENTRY_MODULE = 'four_programmes.hm_whole_worker_entry_v1'
FD_ENVIRONMENT = ('NEUROBENCH_HM_BOOTSTRAP_FD', 'NEUROBENCH_HM_READ_FD',
                  'NEUROBENCH_HM_WRITE_FD')
STAGES = ('reference', 'candidate:A', 'candidate:B')
LOGICAL = ('read_bytes', 'write_bytes', 'work_units', 'retained_bytes')
REQUEST_FIELDS = ('schema', 'scope', 'inputs', 'full_plan', 'original_authority',
                  'submission', 'package', 'root', 'output', 'terminal_name')
SUBJECT_FIELDS = ('schema', 'profile', 'sequence', 'stage', 'source_manifest',
                  'environment', 'launch_policy', 'scope', 'inputs', 'full_plan',
                  'submission', 'original_authority', 'request')
LEASE_FIELDS = ('schema', 'profile', 'resource_plan', 'sequence', 'stage', 'subject',
                'original_authority', 'controller', 'host', 'worker_nonce',
                'workspace_nonce', 'stage_started_ns', 'deadline_ns', 'evidence_deadline_ns')
START_FIELDS = ('schema', 'profile', 'lease', 'subject', 'bootstrap',
                'stage', 'sequence', 'host', 'controller', 'worker',
                'stage_started_ns', 'observed_ns', 'deadline_ns', 'evidence_deadline_ns')
CONFIG_FIELDS = ('roots', 'relative_base', 'ordinary_source_root', 'terminal_root',
                 'catalog', 'extension_sources', 'selected_context', 'selected_templates',
                 'environment_record', 'clock_mapping', 'selected_channel_qualification',
                 'bootstrap_limits', 'terminal_limits', 'metadata_cap', 'python_executable', 'environment_values')
BODY_FIELDS = ('schema', 'profile_body', 'profile_pin', 'resource_plan', 'lease',
               'subject', 'request', 'launch_binding', 'native_configuration', 'worker_configuration', 'pipe_identities')


def bare(value):
    closed(value, ('bytes', 'sha256'))
    integer(value['bytes'])
    need(type(value['sha256']) is str and len(value['sha256']) == 64 and
         all(c in '0123456789abcdef' for c in value['sha256']), 'exact bare content pin')
    return value


def pinlike(value):
    need(type(value) is dict, 'source-selected content identity')
    if set(value) == {'path', 'bytes', 'sha256'}:
        descriptor(value)
    else:
        bare(value)
    return value


def wrapped(value):
    closed(value, ('descriptor', 'body'))
    pinlike(value['descriptor'])
    need(pin(encode(value['body'])) == {k: value['descriptor'][k] for k in ('bytes', 'sha256')},
         'complete canonical original metadata wrapper')
    return value['body']


def process(value):
    closed(value, ('boot_id', 'pid', 'start_monotonic_ns', 'launch_nonce', 'source', 'parent_launch'))
    integer(value['pid'], 1); integer(value['start_monotonic_ns'], 1)
    need(type(value['boot_id']) is str and value['boot_id'] and
         type(value['launch_nonce']) is str and value['launch_nonce'], 'original process identity')
    pinlike(value['source']); pinlike(value['parent_launch'])
    return value


def absolute(value):
    need(type(value) is str and value.startswith('/') and '\\' not in value and '\0' not in value,
         'explicit absolute selected root')
    relative(value[1:])
    need(str(Path(value)) == value, 'canonical explicit root spelling')
    return value


def validate_request(request):
    closed(request, REQUEST_FIELDS)
    need(request['schema'] == 'hm_whole_worker_scientific_request_v1', 'distinct whole-job scientific request')
    for key in ('scope', 'inputs', 'full_plan', 'original_authority'):
        descriptor(request[key])
    if request['submission'] is not None:
        descriptor(request['submission'])
    for key in ('package', 'root', 'output'):
        absolute(request[key])
    root = Path(request['root'])
    need(Path(request['package']).is_relative_to(root) and Path(request['output']).is_relative_to(root)
         and request['package'] != request['output'] and request['output'] != request['root'],
         'explicit separate source/fresh output in actual scientific root')
    relative(request['terminal_name'])
    need('/' not in request['terminal_name'], 'one fixed terminal leaf')
    return request


def validate_worker_configuration(configuration):
    closed(configuration, CONFIG_FIELDS)
    roots = configuration['roots']
    need(type(roots) is dict and roots and all(type(k) is str and k for k in roots), 'explicit named roots')
    for value in roots.values():
        absolute(value)
    need(len(set(roots.values())) == len(roots) and configuration['relative_base'] in roots,
         'distinct explicit root roles and relative base')
    need(configuration['ordinary_source_root'] in roots.values() and
         configuration['terminal_root'] in roots.values(), 'selected existing source and terminal roots')
    for key in ('catalog', 'selected_context', 'selected_templates', 'environment_record', 'selected_channel_qualification'):
        descriptor(configuration[key])
    expected = {'fixed_tables', 'reservations', 'identity_contract', 'stage_budget',
                'stage_worker', 'issuance', 'stage_closure', 'coordinator'}
    need(type(configuration['extension_sources']) is dict and
         set(configuration['extension_sources']) == expected, 'entire unchanged SourceSession HM extension closure')
    for value in configuration['extension_sources'].values():
        descriptor(value)
    for name in ('bootstrap_limits', 'terminal_limits'):
        closed(configuration[name], LOGICAL)
        for amount in configuration[name].values():
            integer(amount, 1)
    integer(configuration['metadata_cap'], 1)
    need(configuration['metadata_cap'] <= 16777216, 'complete original metadata format bound')
    absolute(configuration['python_executable'])
    need(type(configuration['environment_values']) is dict and
         all(type(k) is str and type(v) is str for k, v in configuration['environment_values'].items()) and
         not any(k in configuration['environment_values'] for k in FD_ENVIRONMENT),
         'fixed complete selected non-FD environment values')
    mapping = configuration['clock_mapping']
    closed(mapping, ('schema', 'source', 'qualification', 'clock_ticks', 'tick_to_monotonic_offset_ns', 'boot_id'))
    need(mapping['schema'] == 'four_linux_start_clock_mapping_v1', 'original selected clock mapping')
    integer(mapping['clock_ticks'], 1)
    need(type(mapping['tick_to_monotonic_offset_ns']) is int, 'signed original clock offset')
    pinlike(mapping['source']); pinlike(mapping['qualification'])
    return configuration


def validate_stage_chain(profile, *, resource_plan, lease, subject, request):
    need(type(profile) is HMWholeJobPlanV1, 'actual distinct compiled whole-job plan')
    resource = wrapped(resource_plan)
    lease_body, subject_body = wrapped(lease), wrapped(subject)
    request_body = validate_request(wrapped(request))
    for value in (lease, subject, request):
        descriptor(value['descriptor'])
    need(resource_plan['descriptor'] == profile.resource_plan_pin and
         encode(resource) == encode(profile.resource_plan), 'same compiled complete root resource selection')
    closed(lease_body, LEASE_FIELDS); closed(subject_body, SUBJECT_FIELDS)
    need(lease_body['schema'] == 'hm_whole_stage_lease_v1' and
         subject_body['schema'] == 'hm_whole_stage_subject_v1', 'distinct whole-job lease and Subject')
    sequence = integer(lease_body['sequence'], 1)
    row = profile.stage(sequence)
    need(lease_body['stage'] == row['stage'] == subject_body['stage'] and
         row['stage'] in STAGES and subject_body['sequence'] == sequence,
         'same complete fixed reference/A/B stage')
    need(lease_body['profile'] == subject_body['profile'] == profile.pin and
         lease_body['resource_plan'] == resource_plan['descriptor'], 'same original profile and root resource plan')
    need(lease_body['subject'] == subject['descriptor'] and
         lease_body['original_authority'] == subject_body['original_authority'] == request_body['original_authority'] and
         subject_body['request'] == pin(encode(request_body)), 'complete immutable actual call binding')
    for key in ('source_manifest', 'environment', 'launch_policy'):
        need(subject_body[key] == profile.body[key], 'same prospective whole-profile ' + key)
    for key in ('scope', 'inputs', 'full_plan'):
        bare(subject_body[key])
    if subject_body['submission'] is not None:
        bare(subject_body['submission'])
    need((row['stage'] == 'reference') == (request_body['submission'] is None) ==
         (subject_body['submission'] is None), 'complete reference or one own-run candidate domain')
    need(lease_body['worker_nonce'] == row['worker_nonce'] and
         lease_body['workspace_nonce'] == row['workspace_nonce'], 'original nonreusable stage identities')
    process(lease_body['host']); process(lease_body['controller'])
    need(lease_body['host'] != lease_body['controller'], 'distinct original H/C identities')
    need(lease_body['host']['source'] == profile.body['observer_source'], 'original H observer source')
    for key in ('stage_started_ns', 'deadline_ns', 'evidence_deadline_ns'):
        integer(lease_body[key], 1)
    need(lease_body['stage_started_ns'] < lease_body['deadline_ns'] < lease_body['evidence_deadline_ns'] and
         lease_body['evidence_deadline_ns'] - lease_body['stage_started_ns'] == row['physical']['wall_ns'] and
         lease_body['evidence_deadline_ns'] - lease_body['deadline_ns'] == profile.body['polling']['termination_grace_ns'],
         'entire reserved stage lifetime includes bootstrap and selected cleanup grace')
    need(lease_body['evidence_deadline_ns'] <= profile.run_deadline_ns,
         'same earlier whole-job run deadline; no fresh lifetime after failure')
    return row


def compile_worker_bootstrap_body_v1(profile, *, resource_plan, lease, subject, request,
                                     launch_binding, native_configuration, pipe_identities):
    """Pure exact wire compilation; H must reserve/retain its actual native attempt."""
    validate_stage_chain(profile, resource_plan=resource_plan, lease=lease, subject=subject, request=request)
    native = wrapped(native_configuration)
    need(native_configuration['descriptor'] == profile.body['native_configuration'], 'original selected native configuration')
    closed(native['worker_bootstrap'], STAGES)
    config = validate_worker_configuration(native['worker_bootstrap'][lease['body']['stage']])
    request_body = request['body']
    need(request_body['root'] in config['roots'].values() and
         config['terminal_root'] != request_body['output'], 'actual selected stage-visible root and separate terminal custody')
    for stage in STAGES:
        validate_worker_configuration(native['worker_bootstrap'][stage])
    # Access-condition differences live in the scientific request, never in
    # the benchmark's implementation, clock mapping or selected admission.
    for key in ('bootstrap_limits', 'terminal_limits', 'python_executable',
                'environment_values', 'environment_record', 'metadata_cap',
                'catalog', 'extension_sources', 'selected_context',
                'selected_templates', 'clock_mapping', 'selected_channel_qualification'):
        need(native['worker_bootstrap']['candidate:A'][key] == native['worker_bootstrap']['candidate:B'][key],
             'same prospective A/B adapter opportunity and launch selection')
    body = {'schema': 'hm_whole_worker_bootstrap_v1', 'profile_body': profile.body,
            'profile_pin': profile.pin, 'resource_plan': resource_plan, 'lease': lease,
            'subject': subject, 'request': request, 'launch_binding': launch_binding,
            'native_configuration': native_configuration['descriptor'],
            'worker_configuration': config, 'pipe_identities': pipe_identities}
    return validate_worker_bootstrap_body_v1(profile, body)


def validate_worker_bootstrap_body_v1(profile, body):
    """W validates its complete visible projection; actual H event binds its raw bytes."""
    closed(body, BODY_FIELDS)
    need(body['schema'] == 'hm_whole_worker_bootstrap_v1' and
         body['profile_body'] == profile.body and body['profile_pin'] == profile.pin and
         body['native_configuration'] == profile.body['native_configuration'], 'same complete whole-job profile selection')
    validate_stage_chain(profile, resource_plan=body['resource_plan'], lease=body['lease'],
                         subject=body['subject'], request=body['request'])
    config = validate_worker_configuration(body['worker_configuration'])
    need(config['environment_record'] == profile.body['environment'] and
         body['request']['body']['root'] in config['roots'].values() and
         config['terminal_root'] != body['request']['body']['output'], 'selected stage-visible environment and roots')
    launch_binding = body['launch_binding'];pipe_identities = body['pipe_identities']
    need(config['environment_record'] == profile.body['environment'], 'original selected runtime environment body')
    closed(launch_binding, ('campaign', 'source', 'launch', 'read_identity', 'write_identity', 'maximum_frame_bytes'))
    closed(pipe_identities, ('read', 'write'))
    for value in pipe_identities.values():
        need(type(value) is list and len(value) == 3, 'actual complete pipe object identity')
        for number in value:
            integer(number)
    need(launch_binding['read_identity'] == pipe_identities['read'] and
         launch_binding['write_identity'] == pipe_identities['write'] and
         launch_binding['source'] == profile.body['observer_source'] and
         launch_binding['campaign'] == profile.body['campaign_id'], 'exact H source/campaign and selected inherited pipe ends')
    integer(launch_binding['maximum_frame_bytes'], 1)
    need(launch_binding['launch'] == body['lease']['descriptor'], 'channel belongs to this exact issued stage lease')
    need(len(encode(body)) <= BOOTSTRAP_FORMAT_MAXIMUM, 'complete bootstrap fits source-selected format ceiling')
    return body


def fixed_worker_argv_v1(configuration):
    validate_worker_configuration(configuration)
    return [configuration['python_executable'], '-I', '-m', ENTRY_MODULE]


def validate_start_response(profile, bootstrap, raw_pin, event, channel, actual_worker):
    from .channel import RootChannel, HostEvent
    need(type(channel) is RootChannel and type(event) is HostEvent and channel.owns_completed_event(event),
         'actual completed event belongs to this original W/H channel')
    need(event.body['status'] == 'observed' and event.source == profile.body['observer_source'] and
         event.campaign == bootstrap['launch_binding']['campaign'], 'actual selected H source and campaign')
    result = event.body['result']
    closed(result, ('schema', 'start', 'start_body'))
    need(result['schema'] == 'hm_whole_worker_start_response_v1', 'distinct whole-job H start response')
    start = wrapped({'descriptor': result['start'], 'body': result['start_body']})
    closed(start, START_FIELDS)
    lease = bootstrap['lease']['body']
    need(start['schema'] == 'hm_whole_stage_start_v1' and start['profile'] == profile.pin and
         start['lease'] == bootstrap['lease']['descriptor'] and
         start['subject'] == bootstrap['subject']['descriptor'] and
         start['bootstrap'] == raw_pin,
         'actual H observation joins this exact immutable worker invocation')
    need(start['worker'] == actual_worker and start['host'] == lease['host'] and
         start['controller'] == lease['controller'] and actual_worker not in (start['host'], start['controller']),
         'actual distinct original W/H/C boot/PID/start identities')
    for key in ('stage', 'sequence', 'stage_started_ns', 'deadline_ns', 'evidence_deadline_ns'):
        need(start[key] == lease[key], 'same original start and reserved opportunity ' + key)
    integer(start['observed_ns'], 1)
    need(lease['stage_started_ns'] <= start['observed_ns'] < lease['deadline_ns'], 'original H start before scientific cutoff')
    return start
