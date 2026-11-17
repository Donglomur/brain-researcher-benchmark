"""Independent complete native/model creation and creator histories; metadata only."""
import os
import re
import time
from pathlib import Path
from .core import need, pin, capture, read_json, integer, number, decode
from _sleep_parent.vendor_transport.engine import validate_cli_records, validate_natural_exit
from _sleep_parent.vendor_transport.provider import caps


def group_absent(pid, end):
    integer(pid, 2); need(time.monotonic() < end, 'Creator observation inside selected closeout')
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    # Permission errors propagate. Existing/reused groups are ambiguous and no
    # mutating signal is sent by this observer.
    return False


def children(events, records, limits, phase_end, end):
    intents=[]; born=[]
    for label,value in events:
        if label == 'CLI-INTENT':
            need(type(value) is dict and set(value)=={'index','phase','cap','original_end'}, 'Exact CLI intent')
            need(value['index']==len(intents)==len(born), 'Sequential completed intent/child capture')
            need(type(value['index']) is int and value['phase'] in limits and value['cap']==limits[value['phase']], 'Exact CLI phase cap')
            need(number(value['original_end']) and value['original_end']<=phase_end,'Unrenewed CLI cutoff')
            intents.append(value)
        elif label == 'CLI-CHILD':
            need(len(intents)==len(born)+1, 'One child for each issued intent')
            intent=intents[-1]; token=value['process_identity']
            need(value['index']==intent['index'] and value['phase']==intent['phase']
                 and value['original_end']==intent['original_end'] and value['independent_group'] is True
                 and value['docker_exec_still_gated'] is True, 'Durable gated command identity')
            integer(value['pid'],2)
            need(value['pid']==value['pgid']==token['pid']==token['pgid']==token['session_id'], 'Exact recorded CLI group join')
            need(token['schema']=='osl_linux_process_identity_v1' and type(token['uid']) is int
                 and type(token['start_time_ticks']) is int and token['start_time_ticks']>0
                 and re.fullmatch('[0-9a-f-]{36}',token['boot_id']), 'Recorded source-owned birth token')
            need(group_absent(value['pgid'],end), 'Creator group still exists or has ambiguous reuse')
            born.append(value)
    need(intents and len(intents)==len(born), 'No unresolved command creation')
    if records is not None:
        validate_cli_records(records,limits)
        need(len(records)==len(intents) and all(r['phase']==i['phase'] for r,i in zip(records,intents)),
             'Every terminal native CLI record joins its original intent')
    return {'commands':len(intents),'current_groups_absent':True,
            'atomic_birth_acquisition_proved':False,
            'parent_runtime_ownership_semantics_require_qualification':True}


def indexed_events(root, members, model, meter):
    pattern = r'event-([0-9]{5})\.json' if model else r'([0-9]{6})-([A-Z-]+)\.json'
    selected=[]
    for name in members:
        match=re.fullmatch(pattern,name)
        if match:
            selected.append((int(match[1]),name))
    selected.sort(); start=1 if model else 0
    need([i for i,_ in selected]==list(range(start,start+len(selected))), 'Complete indexed event sequence')
    events=[]
    for i,name in selected:
        row=read_json(root/name,meter)
        if model:
            need(set(row)=={'kind','value'},'Exact model event record')
            events.append((row['kind'],row['value']))
        else:
            need(set(row)=={'schema','phase_id','request_sha256','index','event','value'}
                 and row['schema']=='osl_transport_journal_v1' and row['index']==i
                 and name==f"{i:06d}-{row['event']}.json", 'Exact native journal identity')
            events.append((row['event'],row['value'],row))
    return events, {name for _,name in selected}


def native(control, job, quarantine, members, expected, configuration, source, meter):
    """All three resources, complete command history and whole captured envelope."""
    request=read_json(control/'REQUEST.json',meter)
    need(set(request)=={'schema','phase_id','action','role','image','command','workdir','source','exposure','clock','resources','output'}
         and request['schema']=='osl_owned_phase_request_v1' and request['action']=='held_attempt'
         and request['command']==['/usr/local/bin/python','-I','-B','/library/program/entry.py','worker']
         and request['workdir']=='/work' and request['output']=={'kind':'generic','manifest':'OUTPUTS.json'},
         'Exact immutable Native worker command, action, workdir and output contract')
    raw=capture(control/'RECEIPT.json',meter=meter); receipt=decode(raw,meter.depth,meter.nodes)
    rp=pin(raw); ownership=read_json(control/'OWNERSHIP.json',meter)
    join=read_json(job/'JOIN.json',meter); job_value=read_json(job/'JOB.json',meter)
    exposure=read_json(job/'EXPOSURE.json',meter,request['exposure'])
    wire=control.name
    limits=request['resources']
    need(read_json(control/'POLICY.json',meter)=={'schema':'osl_holder_policy_v1','phase_id':wire,
         'role':request['role'],'file_cap':limits['max_file_bytes'],'total_cap':limits['max_output_bytes'],
         'files':limits['max_files'],'directories':limits['max_directories']},
         'Exact captured holder output policy for this phase and selected limits')
    need(re.fullmatch('[0-9a-f]{32}',wire) and join['wire_phase']==wire
         and join['logical_phase']==expected['logical'] and join['action']==expected['action']
         and join['role']==expected['role'], 'Exact independently derived logical/wire/JOB identity')
    need(join['request']==pin(capture(control/'REQUEST.json',meter=meter)) and join['receipt']==rp
         and join['source']==source and join['job']==pin(capture(job/'JOB.json',meter=meter)), 'Native exact captured join')
    need(request['phase_id']==receipt['phase_id']==wire and request['source']==receipt['source']==source
         and request['role']==receipt['role']==expected['role'] and job_value['action']==expected['action']
         and request['image']==receipt['image']==configuration['image'], 'Native source/role/image/action')
    need(receipt['request_sha256']==join['request']['sha256'] and receipt['status']=='captured'
         and receipt['error'] is None and receipt['exit_observation_error'] is None
         and receipt['producer_closed_before_capture'] is True and receipt['all_native_resources_closed'] is True
         and receipt['cli_reaped'] is True and receipt['deadline_exceeded'] is False,'Complete successful native phase')
    validate_natural_exit(receipt['natural_exit'])
    timing=receipt['timing']
    need(all(number(timing[k]) for k in ('origin','started','finished','phase_deadline','original_deadline'))
         and timing['origin']<=timing['started']<timing['finished']<timing['phase_deadline']<=timing['original_deadline']
         and request['clock']=={'origin':timing['origin'],'phase_deadline':timing['original_deadline']}, 'Native unrenewed chronology')
    need(exposure['schema']=='osl_transport_exposure_v1' and exposure['role']==request['role']
         and exposure['image']==request['image'] and exposure['source']==source
         and exposure['command']==request['command'] and exposure['mounts']==receipt['input_before']
         and exposure['boundary_audit']==configuration['mechanical_policy_pin']
         and exposure['approved_image_inventory_sha256']==configuration['_captured_mechanical_policy']['image_inventory_sha256']
         and exposure['role_boundary_verified'] is True and receipt['exposure']==request['exposure'],
         'Exact independently captured EXPOSURE body, selected image policy and all actual mounts')
    need(receipt['input_before']==receipt['input_after'] and receipt['quarantine_root']==str(quarantine)
         and receipt['output_inventory']['complete'] is True,'Complete immutable-input capture')
    # Trusted completion envelope is metadata, not a candidate numerical answer.
    files=receipt['output_inventory']['files']
    need('RESULT.json' in files and 'OUTPUTS.json' in files,'Trusted worker completion and complete inventory')
    completion=read_json(quarantine/'RESULT.json',meter,files['RESULT.json'])
    inventory=read_json(quarantine/'OUTPUTS.json',meter,files['OUTPUTS.json'])
    need(completion=={'schema':'neural007_trusted_worker_completion_v1','phase_id':wire,
         'request_sha256':join['request']['sha256'],'producer_completed':True,'scientific_qualification':False},
         'Exact trusted worker completion envelope')
    need(type(inventory) is dict and set(inventory)=={'schema','phase_id','request_sha256','files'}
         and inventory['schema']=='osl_transport_output_manifest_v1' and inventory['phase_id']==wire
         and inventory['request_sha256']==join['request']['sha256']
         and inventory['files']=={k:v for k,v in files.items() if k!='OUTPUTS.json'},
         'Complete captured worker output inventory')
    events,names=indexed_events(control,members,False,meter)
    need(set(members)==names|{'OWNERSHIP.json','REQUEST.json','POLICY.json','RECEIPT.json'},'No missing/extra/recovery native history')
    need(events and events[0][0]=='OWNERSHIP' and events[-1][0]=='PHASE-CLOSURE'
         and events[-1][1]==receipt,'Complete source-owned native closure')
    for _,_,row in events:
        need(row['phase_id']==wire and row['request_sha256']==join['request']['sha256'],'Every journal operand join')
    op=pin(capture(control/'OWNERSHIP.json',meter=meter))
    need(events[0][1]=={'ownership_pin':op,'ownership':ownership} and receipt['ownership_pin']==op
         and ownership['phase_id']==wire and ownership['request_pin']==join['request']
         and ownership['engine_source_pin']==configuration['engine_source']
         and ownership['original_deadline']==timing['original_deadline']
         and ownership['phase_deadline']==timing['phase_deadline'],'Precreation ownership joins')
    prefix=ownership['attempt_prefix']; need(re.fullmatch('osl-[0-9a-f]{24}',prefix),'Exact native namespace')
    need(set(ownership['resources'])=={'volume','holder','producer'},'All three planned resources')
    allowed={'OWNERSHIP','CLI-INTENT','CLI-CHILD','RESOURCE-INTENT','CREATE-ATTEMPT','RESOURCE-ACK','PHASE-CLOSURE'}
    need(all(label in allowed for label,_,_ in events),'No unknown native operation')
    resources=[]
    for label,kind in [('volume','volume'),('holder','container'),('producer','container')]:
        planned={'kind':kind,'name':prefix+'-'+label,'owner':prefix+'/'+label,'attempted':False,'acknowledged':False}
        need(ownership['resources'][label]==planned,'Frozen name/owner/kind plan')
        relevant=[(event,value) for event,value,_ in events if event in ('RESOURCE-INTENT','CREATE-ATTEMPT','RESOURCE-ACK')
                  and (value.get('resource',value)).get('name')==planned['name']]
        need([k for k,_ in relevant]==['RESOURCE-INTENT','CREATE-ATTEMPT','RESOURCE-ACK'],'Complete unique create disposition')
        need(relevant[0][1]=={'resource':planned,'creation_obligation_until_closed':True}
             and relevant[1][1]=={**planned,'attempted':True},'Ownership before exact creation attempt')
        ack=relevant[2][1]; expected_ack={**planned,'attempted':True,'acknowledged':True}
        if kind=='container':
            need(re.fullmatch('[0-9a-f]{64}',ack.get('id','')),'Exact acknowledged container ID'); expected_ack['id']=ack['id']
        need(ack==expected_ack,'Exact acknowledged resource')
        closure=[x for x in receipt['retired_resources'] if x.get('name')==planned['name']]
        need(len(closure)==1 and closure[0]['kind']==kind and closure[0]['closed'] is True
             and closure[0]['absence_observed'] is True and closure[0]['creation_outcome_unknown'] is False,
             'No incomplete/unknown native creation')
        resources.append({'kind':kind,'name':planned['name'],'owner':planned['owner'],
                          'id':ack.get('id'),'creation_complete':True})
    need(len(receipt['retired_resources'])==3 and sum(k in ('RESOURCE-INTENT','CREATE-ATTEMPT','RESOURCE-ACK') for k,_,_ in events)==9,
         'No unaccounted additional native resource')
    cli=children([(k,v) for k,v,_ in events],receipt['command_metadata'],caps(request['resources']['inventory_bytes']),timing['phase_deadline'],meter.end)
    return {'receipt':receipt,'receipt_pin':rp,'request':request,'join':join,'job':job_value,'resources':resources,'creator_observation':cli}


def model(root, members, seal, configuration, source, meter):
    events,event_names=indexed_events(root,members,True,meter)
    allowed={'CLI-INTENT','CLI-CHILD','OWNERSHIP','ACK','READY','CLOSED'}
    need(events and all(k in allowed for k,_ in events),'No failed/unknown provider lifecycle')
    unique={}
    for name in ('OWNERSHIP','ACK','READY','CLOSED'):
        values=[v for k,v in events if k==name]
        need(len(values)==1,'One complete provider '+name); unique[name]=values[0]
    order=[k for k,_ in events]
    need(order.index('OWNERSHIP')<order.index('ACK')<order.index('READY')<order.index('CLOSED'), 'Provider source lifecycle chronology')
    own,ack=unique['OWNERSHIP'],unique['ACK']
    need(own['kind']=='container' and re.fullmatch('neural007-[0-9a-f]{32}',own['name'])
         and re.fullmatch('[0-9a-f]{32}',own['owner']) and own['attempted'] is True
         and own['acknowledged'] is False, 'Provider precreation namespace')
    need(re.fullmatch('[0-9a-f]{64}',ack.get('id','')) and ack=={**own,'acknowledged':True,'id':ack['id']}, 'Provider complete ACK')
    need(seal['context']==root.name and seal['programme_source']==source
         and seal['mode']=='case_adaptive_equal_inputs_tools_compute', 'Exact adaptive context seal')
    closure=seal['provider_closure']; validate_natural_exit(closure['natural_exit'])
    need(closure['context']==root.name and closure['turns']==len(seal['decisions'])
         and closure['closure']['kind']=='container' and closure['closure']['name']==ack['name']
         and closure['closure']['closed'] is True and closure['closure']['absence_observed'] is True
         and closure['closure']['creation_outcome_unknown'] is False,'Successful source-bound Session.close disposition')
    need(unique['READY']['context']==root.name and unique['READY']['deadline']==seal['clock']['deadline']
         and unique['CLOSED']['context']==root.name and unique['CLOSED']['server_reaped'] is True
         and unique['CLOSED']['model_unloaded'] is True,'Provider original clock and owned service closure')
    capture(root/'SERVER.log',unique['CLOSED']['log'],meter,1048576)
    required=set(event_names)|{'requests','SERVER.log'}
    requests={'CLOSE.json','ACK.json'}
    for row in seal['decisions']:
        turn=row['turn']; expected=row['receipt']
        request_path=root/'requests'/f'turn-{turn}.json'; response_path=root/f'response-{turn}.json'
        request=read_json(request_path,meter,expected['request']); response=read_json(response_path,meter,expected['response'])
        need(request['context']==response['context']==root.name and request['turn']==response['turn']==turn
             and response['request']==expected['request'] and request['deadline']==expected['deadline']
             and response['finished']<expected['deadline']<=seal['clock']['deadline'], 'Exact provider request/response source clock')
        required.add(response_path.name); requests.add(request_path.name)
    need(set(members)==required,'Complete provider root inventory')
    for name in ('CLOSE.json','ACK.json'):
        need(read_json(root/'requests'/name,meter)=={'context':root.name},'Exact provider close handshake')
    limits=caps(65536); limits.update(model_create=4096,model_start=4096,model_admit=131072,model_image=131072,
        model_ready=2097152,model_turn=8388608,model_close=2097152,model_wait=4096,model_exit=131072)
    cli=children(events,None,limits,seal['clock']['deadline'],meter.end)
    need(cli['commands']<=256,'Original provider CLI maximum')
    return {'resources':[{'kind':'container','name':ack['name'],'owner':ack['owner'],'id':ack['id'],'creation_complete':True}],
            'request_names':requests,'creator_observation':cli,'terminal_per_command_receipts_exported':False,
            'terminal_success_basis':'exact successful captured Session.close and investigation seal flow; current independent process/resource observation still required'}
