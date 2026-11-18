"""Pure fresh runtime custody/state adapter; trusted loaders own authentication.

No explicit I/O or live adapters are started here. Only immutable original
bodies and authenticated injected pure modules are consumed. Historical proof
schemas and the historical policy.evaluate entrypoint are never synthesized.
"""
from collections import namedtuple
import hashlib
import json
from pathlib import PurePosixPath
import re
import sys

MAX_READ = 16*1024**2
ORIGINAL_CAP = 524288
ORIGINAL_TOTAL_CAP = 4*1024**2
RECEIPT_CAP = 32768
PROFILE_SHA256 = 'c1830439a06254a982279604d645de5969c3444260e74262f7ad0efc7bc3129b'
PROBE_SHA256 = 'f513ed96f8598d5693fa2dc4e2589d18bc5b92f14ea6d88be7f58311e76f3848'
OBSERVATION_SHA256 = '7a75b0b550192c38c5eb236038c06d5f4320db1b84c261629d45f5e50d761c74'
CASE_ID = hashlib.sha256(b'dosei-generated-runtime-qualification-v1').hexdigest()
FIXED_MODULE_PINS = (
    ('docker_policy','6d4d8e952042d6b7a9557ba8c035da80b557b1778ec9b551f55d6b45bbdd6412'),
    ('network_policy','c0b703578ef0f7be540c4575ca6949d884641677a782cdfc6e8b122e736f0ec0'),
    ('owned','afae111f8dec293391bbf077cd0d700e8061328d5541f5d116ade63c1cf7d219'),
    ('probe',PROBE_SHA256),
)
CASES_SHA256 = '47f0fc57df5a797cc049798bb82703cec3d72cfc847822671f933902dd6829d4'
MODULE_PINS = FIXED_MODULE_PINS + (('cases',CASES_SHA256),)
Authority = namedtuple('Authority', 'protocol_sha256 context_id worker_pid output_directory '
    'python_executable cli_shim_path docker_executable docker_socket canary_path '
    'program_sha256 original_bindings module_source_sha256')
KINDS = ['command_intent','command_output_prefix','command_receipt','code_setup','python_source']
KINDS += ['command_intent','command_output_prefix','command_receipt']*7+['code_call']
ORIGINAL_NAMES = tuple(f'evidence/{i:04d}-{kind}.bin' for i,kind in enumerate(KINDS))
COMMAND_POSITIONS = ((0,1,2),)+tuple((i,i+1,i+2) for i in range(5,24,3))
ROLE_POSITIONS = {'image_inspection':1,'initial_container_inspection':9,
    'final_container_inspection':15,'ownership_inspection':18,'remove_receipt':22,
    'absence_receipt':25,'runtime_call':26,'program_source':4,'runtime_output':12}
COPIED_HELPER_SOURCE_SHA256 = 'c3e02250bc92a2387344683b10e84994e7add4961c0ee99bc545c877abae64f2'


class FreshRuntimeRefusal(ValueError): pass


def require(ok, why):
    if not ok: raise FreshRuntimeRefusal(why)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')


def binding(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def integer(value, low=0, high=MAX_READ):
    require(type(value) is int and low<=value<=high,'bounded exact integer required')
    return value


# The following two custody helpers and reparse_saved_frames are exact copies
# from the pinned saved checker. None imports its Context or reads live inputs.
def exact_counters(value):
    """JSON booleans and floats cannot impersonate retained byte/count integers."""
    names = {'bytes','ordinal','context_index','command_attempts','ordinary_attempts','cleanup_attempts',
             'command_cap','max_calls','owner_pid','leader_pid','process_group_id','returncode','leader_returncode',
             'post_wait_group_absence_probes','post_wait_group_permission_denials_observed',
             'requested_output_limit','effective_output_limit','output_limit'}
    if type(value) is dict:
        for key,item in value.items():
            if key in names or key.endswith('_bytes'):
                # Only explicitly unknown unread bytes may be null; this failed
                # attempt's successful command paths separately require zero.
                require((key == 'unread_output_bytes' and item is None) or
                        (type(item) is int and -(2**63) < item < 2**63),'strict integer counter: '+key)
            exact_counters(item)
    elif type(value) is list:
        for item in value:exact_counters(item)


def verify_cli_closure(receipt,intent,worker_pid,owned):
    spawn,closed = receipt['spawn'],receipt['closure']
    require(spawn['schema'] == 'dosei_owned_process_spawn_v1' and
            closed['schema'] == 'dosei_owned_process_close_v1','owned receipt schema')
    integer(spawn['leader_pid'],1,2**31); integer(worker_pid,1,2**31)
    for item in (spawn,closed):
        require(item['owner_pid'] == worker_pid and item['leader_pid'] == spawn['leader_pid'] and
                item['process_group_id'] == spawn['leader_pid'],'CLI ownership binding')
    require(spawn['command_sha256'] == binding(canonical(intent['command']))['sha256'] and
            spawn['environment_sha256'] == binding(canonical(owned.ENVIRONMENT))['sha256'],
            'CLI exact argv/environment hash')
    require(spawn['fresh_session_requested'] is True and spawn['environment_inherited'] is False and
            spawn['extra_fds_inherited'] is False and
            spawn['leader_polled_or_reaped_before_cleanup'] is False,'CLI spawn scope')
    require(closed['complete'] is True and closed['leader_reaped'] is True and
            closed['post_wait_group_absence_observed'] is True and closed['post_wait_group_probe_error'] is None and
            closed['leader_polled_or_reaped_before_group_signals'] is False and
            closed['group_signals_after_wait_attempt'] is False and closed['stdio_ownership_transferred'] is True and
            closed['escaped_descendant_absence_proven'] is False,'CLI closure unconfirmed')
    integer(closed['post_wait_group_absence_probes'],1,100000)
    require(type(closed['leader_returncode']) is int and closed['leader_returncode'] == receipt['returncode'],
            'CLI return code mismatch')
    events = closed['events']; waits = [i for i,v in enumerate(events) if v['operation'] == 'wait_and_reap_leader']
    require(len(waits) == 1 and events[waits[0]]['returncode'] == receipt['returncode'],'one final reap required')
    signals = [v for i,v in enumerate(events) if v['operation'] == 'signal_owned_group' and i < waits[0]]
    require(not any(v['operation'] == 'signal_owned_group' for v in events[waits[0]+1:]),'signal after wait')
    errors = closed['errors']
    require(all(v['operation'] == 'signal_owned_group' and v['type'] == 'PermissionError' and
                v['resolved_by_observed_group_absence'] is True for v in errors),'unresolved CLI cleanup error')
    require(sorted(v['signal'] for v in signals+errors) == [9,15] and
            all(v['result'] in ('sent','absent') for v in signals),'both owned signal attempts required')
def reparse_saved_frames(value,probe):
    """Reconstruct saved datagrams and reuse the frozen parser with fake I/O."""
    require(value.get('schema')=='dosei_network_state_diagnostic_v1' and
            value.get('collection_complete') is True and value.get('network_qualified') is False and
            value.get('atomic_snapshot') is False,'complete scoped candidate JSON required')
    require(value.get('byteorder')==sys.byteorder,'saved native byte order differs')
    rows=value.get('dumps');require(type(rows) is list and len(rows)==6,'all six saved dumps required')
    collector=probe.Collector(lambda:0.0);views=[]
    total_bytes=0
    for seq,(row,spec) in enumerate(zip(rows,probe.SCHEDULE),1):
        require(type(row) is dict and row.get('name')==spec[0] and row.get('sequence')==seq and
                type(row.get('sequence')) is int and row.get('complete') is True and
                row.get('socket_closed') is True and type(row.get('records')) is list and
                type(row.get('datagrams')) is list and len(row['datagrams'])<=128 and
                type(row.get('done')) is dict,'saved dump envelope')
        frames=row['records']+[row['done']];by_datagram={}
        for frame in frames:
            number=integer(frame['datagram'],0,127);offset=integer(frame['offset'],0,65536)
            text=frame['frame_hex']
            require(type(text) is str and len(text)<=131072 and len(text)%2==0 and
                    re.fullmatch('[0-9a-f]*',text),'bounded exact frame hex')
            raw=bytes.fromhex(text);require(len(raw)>=16,'short saved frame')
            by_datagram.setdefault(number,[]).append((offset,raw))
        require(set(by_datagram)==set(range(len(row['datagrams']))),'all saved datagrams represented')
        datagrams=[]
        for number,item in enumerate(row['datagrams']):
            cursor=0;pieces=[]
            for offset,raw in sorted(by_datagram[number]):
                require(offset==cursor,'overlapping or missing saved frame extent')
                cursor+=len(raw);require(cursor<=65536,'saved datagram bound');pieces.append(raw)
            body=b''.join(pieces);total_bytes+=len(body)
            require(total_bytes<=1048576 and canonical(item)==canonical({'ordinal':number,'bytes':len(body),
                    'sha256':binding(body)['sha256'],'sender':[0,0],'flags':0}),'complete saved datagram hash/identity')
            datagrams.append(body)
        class SavedSocket:
            def __init__(self):self.queue=list(datagrams);self.closed=False
            def settimeout(self,timeout):require(0<timeout<=1,'fake timeout boundary')
            def bind(self,address):require(address==(0,0),'fake bind scope')
            def getsockname(self):return row['local_port'],0
            def sendto(self,raw,address):
                require(address==(0,0) and raw.hex()==row['request_hex'],'exact saved GET request')
                return len(raw)
            def recvmsg(self,maximum,ancillary):
                require(ancillary==0 and self.queue,'complete fake datagram sequence')
                raw=self.queue.pop(0);require(len(raw)<=maximum,'saved receive allowance');return raw,[],0,(0,0)
            def close(self):self.closed=True
        sock=SavedSocket();collector.dump(lambda:sock,spec,seq)
        require(sock.closed and not sock.queue and canonical(collector.result['dumps'][-1])==canonical(row),
                'saved parsed fields/attributes/request/termination disagree with raw frames')
        views.append({'name':spec[0],'records':[{'parsed':r['parsed'],'attributes':r['attributes'],
            'raw_frame':binding(bytes.fromhex(r['frame_hex'])),'datagram':r['datagram'],'offset':r['offset']}
            for r in row['records']]})
    require(canonical(collector.result['counters'])==canonical(value['counters']) and
            canonical(collector.result['last_datagram'])==canonical(value['last_datagram']),
            'full saved receive/send counters differ')
    fields=collector.result['stability_projection_fields']
    project=lambda row:sorted([[r['parsed'][key] for key in fields] for r in row['records']])
    before,after=project(rows[0]),project(rows[-1])
    require(value['stability_projection_fields']==fields and canonical(before)==canonical(after)==
            canonical(value['link_stability_before'])==canonical(value['link_stability_after']),
            'saved stability projection mismatch')
    names=probe.checked_names(value['if_nameindex_before'])
    require(canonical(names)==canonical(probe.checked_names(value['if_nameindex_after'])) and
            canonical(names)==canonical(sorted([[r['parsed']['index'],r['parsed']['name']] for r in rows[0]['records']])),
            'saved name/index crosscheck mismatch')
    status=value['process_status'];require(type(status) is dict and status['EOF_observed'] is True and
            status['capability_policy_inferred'] is False and type(status['source_bytes']) is int and
            0<status['source_bytes']<=16384 and re.fullmatch('[0-9a-f]{64}',status['source_sha256']),
            'saved process status envelope')
    lines=status['selected_raw_lines'];require(set(lines)==set(probe.STATUS_KEYS),'complete saved security fields')
    reconstructed=('\n'.join(lines[key] for key in probe.STATUS_KEYS)+'\n').encode('ascii')
    parsed=probe.parse_status(reconstructed,True)
    require(parsed['selected_raw_lines']==lines and parsed['selected_values']==status['selected_values'],
            'saved security field parse differs')
    require(type(value['uname']) is dict and set(value['uname'])=={'sysname','nodename','release','version','machine'} and
            value['uname']['sysname']=='Linux' and all(type(v) is str and len(v.encode())<=1024 for v in value['uname'].values()),
            'saved kernel identity envelope')
    return {'raw_netlink_frames_reparsed':True,'reparse_uses_live_adapters':False,
        'saved_datagram_bytes':total_bytes,'state_records':views,'link_stability_fields':fields,
        'if_nameindex_before':value['if_nameindex_before'],'if_nameindex_after':value['if_nameindex_after'],
        'process_status':status,'uname':value['uname'],'original_full_proc_status_rehashed':False,
        'probe_timing_not_independently_remeasured':True,'network_qualified':False,'atomic_snapshot':False,
        'routing_rules_collected':False,'firewall_rules_collected':False,
        'unknown_attribute_descriptors_preserved':True,'no_network_safety_predicate_applied':True}


def pin(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}',value),'strict digest required')
    return value


def join(left,right):
    require(canonical(left)==canonical(right),'exact original semantic join differs')


def bound(value,maximum=ORIGINAL_CAP):
    require(type(value) is dict and set(value)=={'bytes','sha256'},'exact binding required')
    integer(value['bytes'],0,maximum);pin(value['sha256']);return value


def absolute_path(value):
    require(type(value) is str and 0<len(value.encode('utf-8'))<=4096 and value.startswith('/') and
            not any(c in value for c in ('\0','\n','\r',',')) and
            all(part not in ('.','..') for part in value.split('/')),'exact absolute path required')
    return PurePosixPath(value)


def full_container(policy,profile,spec,value,identity):
    require(type(value) is list and len(value)==1 and type(value[0]) is dict,'one inspected container required')
    item=value[0];host,state=item['HostConfig'],item['State']
    require(type(host) is dict and type(state) is dict,'native inspection objects required')
    for key in ('Memory','MemorySwap','NanoCpus','PidsLimit'):integer(host[key],1,2**63-1)
    require(type(state['ExitCode']) is int and state['ExitCode']==0 and state['OOMKilled'] is False and
            state['Running'] is False and state['Paused'] is False,'successful non-OOM candidate required')
    require(host['CapDrop']==['ALL'] and host['SecurityOpt']==['no-new-privileges:true'],'effective security declarations')
    policy.admit_container(profile,spec,value,required_id=identity,running=False)
    return item


def derive_runtime_state(originals, *, profile_bytes, probe_source, authority, modules):
    """Return provisional evidence after the first container is removed.

    The caller authenticates source selection, original byte bindings and active
    protocol/worker identity. This record itself does not authenticate a caller.
    Context closure and the other three calls are intentionally still pending.
    """
    require(type(authority) is Authority,'trusted host authority required')
    for key in ('protocol_sha256','context_id','program_sha256'):pin(getattr(authority,key))
    worker=integer(authority.worker_pid,1,2**31)
    pins=authority.module_source_sha256
    require(type(pins) is tuple and len(pins)==5 and pins==MODULE_PINS and
            type(pins[4]) is tuple and pins[4][0]=='cases' and len(pins[4])==2,'exact module source map required')
    pin(pins[4][1])
    require(type(modules) is dict and set(modules)=={k for k,v in pins},'exact injected module set')
    policy,api,owned,probe,cases=(modules[k] for k in ('docker_policy','network_policy','owned','probe','cases'))
    require(policy.PROFILE_SHA256==api.PROFILE_SHA256==PROFILE_SHA256 and
            api.PROBE_SHA256==cases.PROBE_SHA256==PROBE_SHA256 and policy.IMAGE==api.IMAGE_ID,
            'injected module constants differ')
    require(type(profile_bytes) is bytes and len(profile_bytes)<=65536 and
            binding(profile_bytes)['sha256']==PROFILE_SHA256,'fixed profile body required')
    require(type(probe_source) is bytes and len(probe_source)==20443 and
            binding(probe_source)['sha256']==PROBE_SHA256,'fixed embedded probe body required')
    profile=policy.profile(profile_bytes)
    require(type(originals) is dict and set(originals)==set(ORIGINAL_NAMES),'complete first-call originals required')
    originals=dict(originals)
    require(all(type(v) is bytes and len(v)<=ORIGINAL_CAP for v in originals.values()) and
            sum(map(len,originals.values()))<=ORIGINAL_TOTAL_CAP,'bounded immutable original bodies')
    require(type(authority.original_bindings) is tuple and len(authority.original_bindings)==27,
            'complete host original bindings required')
    expected={}
    for item in authority.original_bindings:
        require(type(item) is tuple and len(item)==3 and type(item[0]) is str and
                item[0] in originals and item[0] not in expected,'unique host original binding')
        expected[item[0]]={'bytes':integer(item[1],0,ORIGINAL_CAP),'sha256':pin(item[2])}
    for name,raw in originals.items():join(binding(raw),expected[name])
    def raw(position):return originals[ORIGINAL_NAMES[position]]
    def decode(position):
        value=api.decode(raw(position),ORIGINAL_CAP);exact_counters(value);return value
    setup,call=decode(3),decode(26)
    case={'case_id':CASE_ID,'observation_sha256':OBSERVATION_SHA256}
    context_id=authority.context_id
    require(call['schema']=='dosei_docker_code_call_v1' and call['context_id']==context_id and
            type(call['ordinal']) is int and call['ordinal']==1 and call['failure'] is None and
            'cleanup_failure' not in call,'successful first runtime call required')
    join(call['case'],case);join(call['program'],binding(raw(4)))
    require(binding(raw(4))['sha256']==authority.program_sha256 and len(raw(4))<=65536,'complete program authority')
    program=cases.programs(authority.canary_path,authority.docker_socket,probe_source=probe_source)['runtime'].encode('utf-8')
    require(raw(4)==program,'exact composite runtime program required')
    spec=call['specification'];root=absolute_path(authority.output_directory)
    observation_path=absolute_path(spec['observation_path']);program_path=absolute_path(spec['program_path'])
    require(observation_path.parent.parent==root/'staging' and observation_path.name=='observation.json' and
            program_path.parent==observation_path.parent and program_path.name=='program-001.py','fresh staged source paths')
    join(spec,policy.specification(profile,context_id,1,str(observation_path),str(program_path)))
    require(setup['schema']=='dosei_docker_code_setup_v1' and setup['context_id']==context_id and
            setup['profile_sha256']==PROFILE_SHA256 and type(setup['max_calls']) is int and setup['max_calls']==4 and
            type(setup['call_wall_seconds']) in (int,float) and setup['call_wall_seconds']==30 and
            setup['fresh_container_per_call'] is True and setup['candidate_host_execution'] is False and
            setup['actual_docker_qualification_inherited'] is False,'fresh four-call context setup')
    join(setup['case'],case)
    prefix=[str(absolute_path(authority.python_executable)),'-I','-S','-B',
            str(absolute_path(authority.cli_shim_path)),'--',str(absolute_path(authority.docker_executable)),
            '--config',str(observation_path.parent/'docker-config'),'--host',
            'unix://'+str(absolute_path(authority.docker_socket))]
    commands=[]
    for ordinal,(ip,op,rp) in enumerate(COMMAND_POSITIONS):
        intent,receipt=decode(ip),decode(rp);output=binding(raw(op))
        require(intent['schema']=='dosei_raw_command_intent_v1' and receipt['schema']=='dosei_raw_command_receipt_v1',
                'original CLI schemas')
        join(receipt['intent'],binding(raw(ip)));join(receipt['retained_original'],output);join(receipt['observed_prefix'],output)
        require(receipt['success'] is True and receipt['eof_observed'] is True and
                type(receipt['unread_output_bytes']) is int and receipt['unread_output_bytes']==0 and
                receipt['failure_category'] is None and receipt['errors']==[] and
                type(receipt['returncode']) is int and receipt['returncode']==0 and
                type(receipt['charged_output_bytes']) is int and receipt['charged_output_bytes']==output['bytes'],
                'complete successful CLI prefix required')
        require(type(intent['command']) is list and 1<=len(intent['command'])<=128 and
                all(type(v) is str and 0<len(v.encode('utf-8'))<=4096 and '\0' not in v for v in intent['command']),
                'bounded argv required')
        join(intent['command'][:len(prefix)],prefix)
        require(intent['cwd']==str(observation_path.parent) and intent['stdin']=='closed_without_input' and
                intent['stderr']=='merged_raw_stdout','fixed original CLI transport')
        cap=integer(intent['output_limit'],1,524288 if ordinal==3 else 131072)
        require((ordinal!=3 or cap==524288) and len(raw(op))<=cap and
                type(intent['timeout_seconds']) in (int,float) and
                0<intent['timeout_seconds']<=(30 if ordinal==3 else 15),'fixed effective runtime capture bounds')
        verify_cli_closure(receipt,intent,worker,owned)
        for event in receipt['closure']['events']+receipt['closure']['errors']:
            if 'signal' in event:integer(event['signal'],1,64)
        commands.append(intent['command'][len(prefix):])
    created=raw(6);require(re.fullmatch(b'[0-9a-f]{64}\n',created),'created full container ID')
    identity=created[:-1].decode('ascii')
    join(commands,[['image','inspect',policy.IMAGE],policy.create_arguments(profile,spec),
        ['container','inspect',identity],['container','start','--attach',identity],
        ['container','inspect',identity],['container','inspect',identity],
        ['container','rm','--force',identity],
        ['container','ls','--all','--no-trunc','--quiet','--filter','id='+identity]])
    require(raw(21)==created and raw(24)==b'','exact owned removal and observed absence')
    policy.admit_image(profile,policy.decode(raw(1)))
    initial=full_container(policy,profile,spec,policy.decode(raw(9)),identity)
    final=full_container(policy,profile,spec,policy.decode(raw(15)),identity)
    ownership=policy.decode(raw(18));policy.admit_ownership(spec,ownership,required_id=identity)
    full_container(policy,profile,spec,ownership,identity)
    join(call['state'],{k:final['State'][k] for k in ('ExitCode','OOMKilled','Running','Paused')})
    require(type(call['closure']) is dict and set(call['closure'])=={'remove','absence'},'call cleanup roles')
    for item,position in ((setup['image_receipt'],2),(call['initial_inspection'],10),(call['command'],13),
                          (call['final_inspection'],16),(call['closure']['remove'],22),(call['closure']['absence'],25)):
        join(item,binding(raw(position)))
    # Parse the exact original bytes, never the backend's replace-decoded text.
    envelope=api.decode(raw(12),ORIGINAL_CAP)
    require(set(envelope)=={'schema','case','observation_sha256','program_sha256','embedded_probe_sha256','runtime','network_state'} and
            envelope['schema']=='dosei_fresh_runtime_observation_v1' and envelope['case']=='runtime' and
            envelope['observation_sha256']==OBSERVATION_SHA256 and
            envelope['program_sha256']==authority.program_sha256 and envelope['embedded_probe_sha256']==PROBE_SHA256,
            'fresh output source/context lineage')
    require(canonical(envelope)+b'\n'==raw(12),'complete canonical original runtime output')
    runtime=cases.validate_runtime_component(envelope['runtime'],policy=policy,profile=profile)
    state=envelope['network_state'];require(len(canonical(state))+1<=262144,'embedded state component cap')
    require(state['status']=='diagnostic_collection_complete' and state.get('failure') is None and
            state['socket_cleanup_errors']==[],'complete fresh collector required')
    view=reparse_saved_frames(state,probe)
    join(runtime['network_interfaces'],sorted(name for index,name in view['if_nameindex_before']))
    counts=None;reason=None;matched=False
    try:
        # Only this schema-independent pure function is used, after custody.
        counts=api.state_condition({'state_view':view});matched=True
    except api.Refusal as error:reason=str(error)
    receipt={'schema':'dosei_fresh_runtime_state_v1','status':'provisional_runtime_evidence',
        'runtime_control_confirmed':False,'context_closure_pending':True,'network_qualified':False,
        'necessary_condition_matches':matched,'necessary_condition_reason':reason,'state_counts':counts,
        'protocol_sha256':authority.protocol_sha256,'context_id':context_id,'container_id':identity,
        'case':case,'profile_sha256':PROFILE_SHA256,'image_id':initial['Image'],
        'complete_program':binding(raw(4)),'embedded_probe':binding(probe_source),
        'original_runtime_output':binding(raw(12)),'derived_canonical_state_component':binding(canonical(state)),
        'derived_reparsed_state_view':binding(canonical(view)),
        'runtime_call':binding(raw(26)),
        'original_roles':{role:{'name':ORIGINAL_NAMES[position],**binding(raw(position))} for role,position in ROLE_POSITIONS.items()},
        'authenticated_original_bindings':expected,'original_body_bytes':sum(map(len,originals.values())),
        'verified_CLI_commands':8,'verified_owned_container_lifecycles':1,'context_expected_calls':4,
        'injected_module_source_sha256':dict(pins),'copied_helper_source_sha256':COPIED_HELPER_SOURCE_SHA256,
        'authority_authentication_owned_by_loader':True,'historical_evaluate_called':False,
        'historical_proof_synthesized':False,'no_live_host_adapters':True,
        'raw_frame_reparse_is_second_kernel_observation':False,'probe_timing_independently_remeasured':False,
        'full_original_proc_status_rehashed':False,'atomic_snapshot':False,
        'routing_rules_collected':False,'firewall_rules_collected':False,
        'old_failed_attempts_unchanged':True,'complete_six_control_qualification':False}
    require(len(canonical(receipt))<=RECEIPT_CAP,'bounded provisional runtime receipt')
    return receipt


def bind_context_close(provisional, close_bytes, *, expected_call_bindings):
    """Close a caller-owned provisional receipt with all four context calls.

    The trusted driver retains this exact provisional record and supplies its
    independently checked complete call roster. This pure join is not a MAC or
    authority mechanism, and cannot establish the other controls' semantics.
    """
    require(type(provisional) is dict and len(canonical(provisional))<=RECEIPT_CAP and
            provisional['schema']=='dosei_fresh_runtime_state_v1' and
            provisional['status']=='provisional_runtime_evidence' and
            provisional['runtime_control_confirmed'] is False and provisional['context_closure_pending'] is True and
            provisional['network_qualified'] is False and type(provisional['necessary_condition_matches']) is bool,
            'unmodified provisional caller record required')
    require(type(close_bytes) is bytes and len(close_bytes)<=65536,'bounded original close body')
    def unique(items):
        result={}
        for k,v in items:require(k not in result,'duplicate close key');result[k]=v
        return result
    closed=json.loads(close_bytes,object_pairs_hook=unique,
        parse_constant=lambda _:(_ for _ in ()).throw(FreshRuntimeRefusal('nonfinite close JSON')))
    exact_counters(closed)
    require(type(closed) is dict and closed['schema']=='dosei_docker_code_close_v1' and
            closed['context_id']==provisional['context_id'] and closed['complete'] is True and
            closed['poisoned'] is False and closed['errors']==[] and closed['owned_container_ids_unresolved']==[] and
            closed['pre_container_setup_failures']==[] and closed['container_names_with_unresolved_create']==[],
            'complete non-poisoned shared context closure required')
    require(type(expected_call_bindings) is list and len(expected_call_bindings)==4,'all four checked call bindings required')
    for item in expected_call_bindings:bound(item,65536)
    require(len({item['sha256'] for item in expected_call_bindings})==4,'four distinct call originals required')
    join(expected_call_bindings[0],provisional['runtime_call']);join(closed['calls'],expected_call_bindings)
    result=json.loads(canonical(provisional));result.update(status='fresh_runtime_context_closed',
        context_closure_pending=False,runtime_control_confirmed=provisional['necessary_condition_matches'],
        original_context_close=binding(close_bytes),complete_context_calls=json.loads(canonical(expected_call_bindings)),
        provisional_receipt=binding(canonical(provisional)))
    require(len(canonical(result))<=RECEIPT_CAP,'bounded final runtime receipt')
    return result
