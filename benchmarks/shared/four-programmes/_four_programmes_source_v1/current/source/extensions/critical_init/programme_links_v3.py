"""Closed V3 programme/development joins; wire checks never grant authority.

These fixed source consumers preserve original census, scientific output and
encoding semantics. Programme-output ABI/manifest/receipt producers remain a
separate required nominal domain; this module does not fabricate them.
"""
from four_programmes.common import need, closed, descriptor, bounded_size, same, pin
from four_programmes.precommit_records import validate_type, CONDITIONS
from four_programmes.backend_json import canonical


def require_canonical_v3(body, expected, kind):
    descriptor(expected)
    validate_type(kind, body)
    raw = canonical(body, expected['bytes'], maximum_depth=64)
    need(pin(raw) == {k: expected[k] for k in ('bytes', 'sha256')},
         'exact current canonical V3 capture bytes, not legacy scientific re-encoding')


def validate_known_v3_links(*, seals, completions, pair, initializations,
                            admissions, closures, bases, policy_pin, interface, meter):
    """Check all selected closed joins without returning a live capability.

    The enclosing original source/root caller must still authenticate capture
    authority and the selected scientific programme-output producer. Parsed
    complete-looking records cannot replace those required producers.
    """
    for value in (seals, completions, initializations, admissions, closures, bases):
        closed(value, CONDITIONS)
    bound=bounded_size([seals,completions,pair,initializations,admissions,closures,bases,interface])
    meter.charge('work_units', bound)
    meter.charge('retained_bytes', 2*bound)
    validate_type('DevelopmentPairClosure', pair)
    validate_type('PublicTaskInterface', interface)
    descriptor(policy_pin)
    ids = [row['job_id'] for row in interface['jobs']]
    need(ids and len(ids) == len(set(ids)), 'complete unique original candidate job order')
    for condition in CONDITIONS:
        for kind, mapping in (('ProgrammeSeal',seals),('DevelopmentCompletion',completions),
                              ('BackendInitializationObservation',initializations),
                              ('BackendAdmissionAck',admissions),('BackendClosure',closures),
                              ('BackendAttemptBase',bases)):
            validate_type(kind,mapping[condition])
    pair_pin = seals[CONDITIONS[0]]['pair_closure']
    require_canonical_v3(pair,pair_pin,'DevelopmentPairClosure')
    environment = seals[CONDITIONS[0]]['environment']
    all_closed = max(completions[c]['closed_ns'] for c in CONDITIONS)
    for condition in CONDITIONS:
        seal = seals[condition]; complete = completions[condition]
        init = initializations[condition]; ack = admissions[condition]
        closure = closures[condition]; base = bases[condition]
        for kind, value in (('ProgrammeSeal',seal),('DevelopmentCompletion',complete),
                            ('BackendInitializationObservation',init),('BackendAdmissionAck',ack),
                            ('BackendClosure',closure),('BackendAttemptBase',base)):
            validate_type(kind, value)
        for body,expected,kind in ((complete,seal['development'],'DevelopmentCompletion'),
             (init,complete['backend_initialization'],'BackendInitializationObservation'),
             (ack,complete['backend_admission'],'BackendAdmissionAck'),
             (closure,complete['backend_closure'],'BackendClosure'),
             (base,init['attempt'],'BackendAttemptBase')):
            require_canonical_v3(body,expected,kind)
        need(seal['condition'] == complete['condition'] == init['condition']
             == ack['condition'] == closure['condition'] == base['condition'] == condition,
             'same exact original arm through all V3 children')
        need(seal['agent_policy'] == policy_pin and seal['environment'] == environment
             and seal['pair_closure'] == pair_pin,
             'two original arm seals share selected policy/environment/pair closure')
        need(seal['development'] == pair['completion_by_condition'][condition]
             and complete['pair_plan'] == pair['pair_plan']
             and seal['exposure'] == complete['exposure'],
             'same actual completed arm and earlier exposure')
        need(complete['backend_initialization'] == pair['initialization_by_condition'][condition]
             and complete['backend_closure'] == pair['backend_closure_by_condition'][condition],
             'exact pair backend initialization and closure maps')
        need(base['profile'] == init['profile'] == pair['backend_profile']
             and base['workspace'] == init['workspace'] == complete['workspace_identity']
             and base['preparation'] == init['preparation'] == complete['state_identity']
             and base['request'] == complete['request']
             and base['worker_attempt'] == ack['worker_attempt'] == complete['original_attempt'],
             'original prelaunch state/request/worker attempt distinct from backend base')
        need(base['worker_launch_ack'] == init['worker_launch_ack']
             and init['attempt'] == ack['backend_attempt'] == closure['attempt']
             and ack['initialization'] == closure['initialization'] == complete['backend_initialization']
             and closure['admission'] == complete['backend_admission']
             and ack['host_owner_binding'] == pair['same_owner_binding'],
             'complete earlier base/initialization/host admission chain')
        need(ack['pair_id'] == base['pair_id'] and ack['nonce'] == base['nonce']
             and ack['generation_deadline_ns'] == base['generation_deadline_ns'],
             'original pair, nonce and generation cutoff')
        need(closure['status'] == 'complete' and closure['purpose'] == 'planned_protocol_shutdown'
             and closure['server_identity'] == init['server_identity'],
             'normal complete same-server shutdown; failure cleanup is never seal eligible')
        need(complete['started_ns'] <= init['observed_ready_ns'] <= base['initialization_deadline_ns']
             and init['observed_ready_ns'] <= ack['issued_ns'] <= base['generation_deadline_ns']
             and complete['started_ns'] <= complete['closed_ns'] <= pair['original_cutoff_ns']
             and all_closed <= seal['sealed_ns'] <= pair['original_cutoff_ns'],
             'earlier readiness/admission and both original arm closures before either seal')
        need([row['job_id'] for row in seal['jobs']] == ids,
             'no reduced or reordered scientific job programme')
        source_ids=[(p['path'],p['bytes'],p['sha256']) for p in seal['source_closure']]
        need(len(source_ids)==len(set(source_ids)), 'unique full per-arm sealed source closure')
        for job in seal['jobs']:
            need(job['report_producer'] in seal['source_closure'],
                 'actual per-arm report producer is captured source, not dispatcher by alias')
    need(completions[CONDITIONS[0]]['workspace_identity'] != completions[CONDITIONS[1]]['workspace_identity']
         and initializations[CONDITIONS[0]]['server_identity'] != initializations[CONDITIONS[1]]['server_identity']
         and initializations[CONDITIONS[0]]['worker_identity'] != initializations[CONDITIONS[1]]['worker_identity'],
         'original distinct fresh workspaces, workers and servers')
    return None


def read_known_v3_links(root, seals, *, policy_pin, interface, cap, budget, meter):
    """Read only exact seal-named earlier metadata via the original reader.

    No source/model/header/array path is followed; these fixed roles remain
    subject to the enclosing original selection and source-output admission.
    """
    from .custody import read_pin, parse, encode
    cache = {}
    def read(expected, kind):
        descriptor(expected)
        identity=(expected['path'],expected['bytes'],expected['sha256'])
        if identity not in cache:
            need(expected['bytes']<=cap,'same original selected metadata read cap')
            meter.charge('retained_bytes',16*expected['bytes']+4096)
            meter.charge('work_units',16*expected['bytes']+4096)
            raw=read_pin(root,expected,cap,budget)
            body=parse(raw)
            if kind=='OriginalProcessReceipt':
                need(pin(encode(body))=={k:expected[k] for k in ('bytes','sha256')},
                     'original H receipt encoding; never canonical-V3 re-encoding')
            else:require_canonical_v3(body,expected,kind)
            cache[identity]=(kind,body)
        need(cache[identity][0]==kind,'one exact metadata Pin cannot impersonate another nominal role')
        return cache[identity][1]
    closed(seals,CONDITIONS)
    for seal in seals.values():validate_type('ProgrammeSeal',seal)
    pair_pin=seals[CONDITIONS[0]]['pair_closure']
    need(all(seals[c]['pair_closure']==pair_pin for c in CONDITIONS),'same pair before child reads')
    pair=read(pair_pin,'DevelopmentPairClosure')
    completions={};initializations={};admissions={};closures={};bases={}
    for condition in CONDITIONS:
        complete=read(seals[condition]['development'],'DevelopmentCompletion');completions[condition]=complete
        init=read(complete['backend_initialization'],'BackendInitializationObservation');initializations[condition]=init
        admissions[condition]=read(complete['backend_admission'],'BackendAdmissionAck')
        closures[condition]=read(complete['backend_closure'],'BackendClosure')
        bases[condition]=read(init['attempt'],'BackendAttemptBase')
    validate_known_v3_links(seals=seals,completions=completions,pair=pair,
        initializations=initializations,admissions=admissions,closures=closures,bases=bases,
        policy_pin=policy_pin,interface=interface,meter=meter)
    from four_programmes.development_targets import validate_target_values
    from four_programmes.development_process_receipt import validate_receipt_values
    for condition in CONDITIONS:
        complete=completions[condition]
        prefix=read(complete['original_attempt'],'DevelopmentAttempt')
        launch=read(complete['launch_request'],'DevelopmentLaunchRequest')
        request=read(complete['request'],'DevelopmentRequest')
        ack=read(complete['actual_launch'],'WorkerLaunchAck')
        streams=read(complete['complete_stream_capture'],'HStreamCaptureV1')
        workspace=read(complete['descendant_and_workspace_closure'],'DevelopmentWorkspaceClosure')
        subtree=read(workspace['subtree'],'SubtreeObservation')
        original_workspace=read(workspace['workspace'],'WorkspaceObservation')
        cost=read(complete['cost_observation'],'CostPrefix')
        original_process=read(complete['actual_original_process'],'OriginalProcessReceipt')
        need(complete['actual_original_process']['path']==launch['output_prefix']+'_PROCESS.json',
             'one exact original H process receipt path; no Completion/self substitute')
        validate_receipt_values(original_process,launch=launch,ack=ack,streams=streams,completion=complete)
        need(all(cost['charged'][dimension]>=original_process['costs']['charged'][dimension]
                 for dimension in cost['charged']),
             'later original aggregate charge prefix never refunds earlier receipt costs')
        need(ack['launch_request']==complete['launch_request'] and
             bases[condition]['worker_launch_ack']==complete['actual_launch'],
             'root-selected actual launch target is the same earlier WorkerLaunchAck')
        validate_target_values(completion=complete,prefix=prefix,launch=launch,request=request,ack=ack,
            streams=streams,workspace=workspace,subtree=subtree,cost=cost,
            cutoff=pair['original_cutoff_ns'],owner_binding=pair['same_owner_binding'],
            workspace_observation=original_workspace)
    # Metadata return only; no private completion/seal capability is reconstructed.
    return None
