"""Full four-stream admission and separately authorized assessment release.

No operation occurs on import. In particular, no assessment descriptor is an
operand of seal_reference_study. release_assessment first admits the complete
source/job/model/array barrier and original observer/external closure. Source
checks do not create physical custody, runtime or scientific qualifications.
"""
import hashlib
import math
from pathlib import Path
from types import SimpleNamespace
import common as c
import arrays
import schedule
import native
import reference_study
import grading
from observation import observer

SEAL_FIELDS=('schema','source','reference_study','preparation','reference_source','reference_limits','native_config','native_phase_limits','native_source_files','reference_phase_request')
RELEASE_FIELDS=('schema','source','master','master_admission','reference_spec','reference_observation','reference_external')
AUTHORITY_FIELDS=('schema','source','release_request','master','master_admission','reference_spec','reference_observation','reference_external','reference_external_authority','execution_authority','assessment','original_origin','original_deadline')
MASTER_FIELDS=('schema','task_id','seal_request','reference_study','source','reference_source','reference_phase_request','preparation','panel','metadata','event_source','reference_counts','dispositions','final_folds','predictions','admission','observer_own_exit_established','assessment_operand_opened','global_assessment_release_authorized')


def _eq(a,b,reason):c.need(c.typed_equal(a,b),reason)
def _descriptor_pin(d):return {k:d[k]for k in('bytes','sha256')}
def _phase_clock(budget,end):return SimpleNamespace(origin=budget.origin,end=end)


def _observer_source_and_roster(spec,source,phase,budget,roots):
    """No arbitrary public data/artifact may be opened by closure replay."""
    c.need(spec['phase']==phase and spec['public_inputs']==[],'no observer task-data pre-capture')
    _eq(spec['source'],source,'same selected complete observer source')
    manifest=c.capture_json(source,budget,roots);c.exact(manifest,('schema','files','runtime_qualified'));c.need(manifest['schema']=='neural010-complete-runtime-source-v1'and manifest['runtime_qualified']is False,'selected full source manifest')
    root=Path(source['path']).parent;files=[];names=set()
    for member in manifest['files']:
        c.exact(member,('name','bytes','sha256'));name=member['name'];c.need(type(name)is str and name and not name.startswith('/')and all(x not in('','.','..')for x in name.split('/'))and name not in names,'unique confined complete source member');names.add(name)
        d={'path':str(root/name),'bytes':member['bytes'],'sha256':member['sha256']};c.descriptor(d);files.append(d)
    c.need({'entry.py','release.py'}<=names,'actual entry/release source members');_eq(spec['source_files'],files,'exact whole source closure, no injected data descriptor')
    for d in files:c.authenticate_stream(d,budget,roots)
    entry=next(d for d in files if Path(d['path']).name=='entry.py'and Path(d['path']).parent==root);_eq(spec['entry'],entry,'actual captured whole-source entry')
    output=c.absolute(spec['child_output_root']);c.need(spec['output_manifest_path']==str(output/'OUTPUT_MANIFEST.json'),'literal phase output manifest')
    if phase=='references':
        wanted=[('reference_study',output/'REFERENCE_STUDY.json'),('master',output/'seal/MASTER.json'),('admission',output/'seal/ADMISSION.json')]+[('merged_'+arm,output/'seal'/(arm+'.predictions.json'))for arm in c.ARMS]+[('phase_result',output/'RESULT.json')]
    else:
        c.need(phase=='fixed-authors','only selected pre-assessment predecessor phases')
        wanted=[item for i in range(3)for item in [('fixed_source_'+str(i),output/str(i)/'SEALED_PROGRAM.py'),('fixed_author_'+str(i),output/str(i)/'AUTHOR.json')]]+[('phase_result',output/'RESULT.json')]
    roster=spec['expected_artifacts'];c.need(type(roster)is list and len(roster)==len(wanted),'complete source-owned original artifact roster')
    for actual,(kind,path) in zip(roster,wanted):
        c.exact(actual,('path','max_bytes','kind'));c.need(actual['path']==str(path)and actual['kind']==kind,'no extra or relabeled observer data capture');c.integer(actual['max_bytes'],1)
    return files


def _predecessor(bundle,phase,source,budget,roots):
    c.exact(bundle,('spec','receipt','external','external_authority'))
    spec=c.capture_json(bundle['spec'],budget,roots);receipt_raw=c.capture(bundle['receipt'],budget,roots);external_raw=c.capture(bundle['external'],budget,roots);receipt=c.parse(receipt_raw);external=c.parse(external_raw);issuer=c.capture_json(bundle['external_authority'],budget,roots)
    c.need(spec['phase']==phase,'complete original predecessor phase');_observer_source_and_roster(spec,source,phase,budget,roots)
    c.need(receipt_raw==c.encoded(receipt)and external_raw==c.encoded(external),'actual original canonical observer artifacts')
    _eq(issuer['external_body'],c.pin(external_raw),'original predecessor external byte identity')
    return observer.admit_external_closure(receipt,external,expected_spec=spec,receipt_descriptor=bundle['receipt'],budget=budget,external_authority=issuer)


def _empty_output(path,budget):
    budget.check_clock();p=c.absolute(str(path));c.need(not any(q.is_symlink()for q in(p,*p.parents))and p.is_dir()and next(p.iterdir(),None)is None,'existing fresh ordinary empty output directory selected by phase driver');return p


def _source(request,budget,roots):
    for key in('source','reference_source','reference_phase_request','reference_study'):c.descriptor(request[key])
    c.authenticate_stream(request['source'],budget,roots)
    c.authenticate_stream(request['native_config']['docker_binary'],budget,roots)
    manifest=c.capture_json(request['reference_source'],budget,roots)
    c.exact(manifest,('schema','files','numerical_qualification','authentic_execution'))
    c.need(manifest['schema']=='neural010-reference-source-v1'and manifest['numerical_qualification']is False and manifest['authentic_execution']is False,'exact unqualified reference source closure')
    expected=('common.py','contracts.py','event_protocol.py','features.py','learners.py','math_core.py','reference_cli.py','selection.py')
    c.need([r['name']for r in manifest['files']]==list(expected),'complete8 reference source members')
    root=Path(request['reference_source']['path']).parent;required=[request['reference_source']]
    for member in manifest['files']:
        c.exact(member,('name','bytes','sha256'));d={'path':str(root/member['name']),'bytes':member['bytes'],'sha256':member['sha256']};c.authenticate_stream(d,budget,roots);required.append(d)
    files=request['native_source_files'];c.need(type(files)is list and len(files)==len({d['path']for d in files}),'exact unique native source files')
    bypath={d['path']:d for d in files}
    for d in files:c.descriptor(d);c.authenticate_stream(d,budget,roots)
    for d in required:c.need(c.typed_equal(bypath.get(d['path']),d),'complete pinned reference source mounted')
    # Join every selected setting to the original actual phase request, not a
    # parallel claim inside the master. This object contains descriptors only.
    phase=c.capture_json(request['reference_phase_request'],budget,roots)
    c.exact(phase,('schema','phase','source','run','output_root','payload'));c.need(phase['schema']=='neural010-phase-request-v1'and phase['phase']=='references','actual original reference phase request')
    _eq(phase['source'],request['source'],'same full original operative source')
    c.exact(phase['payload'],('reference_seal_settings','fixed_authors_closure','capture_roots'));c.need(type(phase['payload']['capture_roots'])is list and phase['payload']['capture_roots'],'explicit original reference capture roots')
    for root in phase['payload']['capture_roots']:c.absolute(root)
    fields=('preparation','reference_source','reference_limits','native_config','native_phase_limits','native_source_files');settings=phase['payload']['reference_seal_settings'];c.exact(settings,fields)
    for field in fields:_eq(settings[field],request[field],'actual original selected setting '+field)
    _predecessor(phase['payload']['fixed_authors_closure'],'fixed-authors',request['source'],budget,roots)

    event=next(d for d in required if Path(d['path']).name=='event_protocol.py')
    c.need(event['bytes']==3258 and event['sha256']=='462afe5bb002df77567bda53c232607b86552a658f99515c283774635956599c','unchanged original event source')
    return event


def _stream_hex(row,name,observation,cap):
    text=row[name+'_hex'];c.need(type(text)is str and len(text)%2==0 and len(text)<=2*cap and all(x in '0123456789abcdef'for x in text),'bounded original hexadecimal stream')
    raw=bytes.fromhex(text);_eq(row[name],c.pin(raw),'original host-command raw stream pin');observer.stream_join(raw,observation['streams'][name]);return raw


def _monitor_stats(command,raw,name,index,start_index,final_inspection_index,workload):
    """Only original bounded stats observations within the attached workload."""
    _eq(command['arguments'],['stats','--no-stream','--format','{{json .}}',name],'exact owned-container stats command')
    c.need(start_index<index<final_inspection_index,'stats occur after start-enter and before final inspection')
    c.need(workload['started_monotonic']<=command['started_monotonic']<=command['ended_monotonic']<=workload['ended_monotonic'],'stats command inside original attached workload interval')
    # A container can exit before stats return a measurement; empty complete
    # stdout is retained as unavailable, never converted to measured zero.
    if raw.strip():c.need(type(c.parse(raw))is dict,'one original stats JSON object')


def _native(operation,expected_inputs,opaque,request,ordinal,budget,roots):
    """Admit actual recorded host/container commands, not status booleans alone."""
    desc=operation['native'];body=c.capture_json(desc,budget,roots);c.need(body['schema']=='neural010-native-job-v1'and body['job_id']==operation['job']['id']and body['kind']=='reference'and type(body['ordinal'])is int and body['ordinal']==ordinal,'exact original native job identity')
    c.need(body['status']=='completed'and type(body['returncode'])is int and body['returncode']==0 and body['natural_completion']is True and body['unknown_survivors']is False,'native completion cannot be inferred from cleanup')
    _eq(body['source_files'],request['native_source_files'],'all selected native source mounts')
    _eq(body['workspace_origin'],[],'references have no prior workspace source');_eq(body['workspace_inputs'],[],'references have no prior mutable workspace or cross-fit state');c.need(body['cpu_reservation_is_not_unknown_survivor_cost_bound']is True,'CPU reservation is not an unknown-survivor upper bound')
    selected={}
    for d in [*request['native_source_files'],*expected_inputs]:
        c.descriptor(d);c.need(d['path']not in selected or c.typed_equal(selected[d['path']],d),'consistent exact input descriptors');selected[d['path']]=d
    _eq(body['inputs'],list(selected.values()),'exact actual native read authority, no ancestor mounts')
    _eq(body['worker_only_label_inputs'],sorted(opaque),'exact isolated label input roster');c.need(type(body['host_prepared_label_body_reads'])is int and body['host_prepared_label_body_reads']==0,'no host label normalization')
    cfg=request['native_config'];c.exact(cfg,('docker_binary','docker_endpoint','image_digest','python','user','pids_limit','memory_bytes','cpus','tmpfs_bytes','tool_seconds','cleanup_seconds','stream_cap_bytes','workspace_cap_bytes','workspace_entry_cap','poll_seconds'))
    c.descriptor(cfg['docker_binary']);native.admit_durability(body,cfg)
    expected_io={'read_bytes':request['reference_limits']['max_input_bytes'],'write_bytes':request['reference_limits']['max_output_bytes']}
    _eq(body['worker_io_reservation'],expected_io,'full prospective reference worker IO caps');c.need(body['worker_io_reservation_refunded']is False and body['arbitrary_native_io_measured']is False,'retained worker reservation is not arbitrary native IO measurement')
    c.need(expected_io['read_bytes']>=reference_study.bootstrap_floor(operation['request'],request['native_source_files']),'source-owned bootstrap fits original worker cap')
    b=body['budget'];c.exact(b,('origin_monotonic','started_monotonic','deadline_monotonic','limits','used'))
    _eq(b['limits'],request['native_phase_limits'],'preselected complete native counters');c.need(type(b['origin_monotonic'])is float and b['origin_monotonic']==float(budget.origin),'same original source clock')
    start=c.finite(b['started_monotonic'],0);deadline=c.finite(b['deadline_monotonic'],0)
    c.need(float(budget.origin)<=start<deadline==min(float(budget.end),start+cfg['tool_seconds']+3*cfg['cleanup_seconds']),'fixed original native interval, no reset')
    _eq(body['original_origin'],budget.origin,'original native parent origin');_eq(body['phase_original_deadline'],deadline,'original native deadline')
    c.exact(b['used'],b['limits'])
    for key,value in b['used'].items():c.integer(value,0,b['limits'][key])
    work=c.absolute(body['work_root']);root=Path(desc['path']).parent;c.need(Path(desc['path']).name=='NATIVE.json'and work==root/'work','confined exact native workspace')
    script=str(Path(request['reference_source']['path']).parent/'reference_cli.py');args=[operation['job']['kind'],'--request',operation['request']['path'],'--request-sha256',operation['request']['sha256'],'--read-cap-bytes',str(request['reference_limits']['max_input_bytes']),'--output','{WORK}/output'];_eq(body['script'],script,'exact native program');_eq(body['args'],args,'exact captured command request')
    intent_desc={'path':str(root/'INTENT.json')}
    # Admit the exact original prelaunch intent carried by NATIVE.
    intent=body.get('intent')
    c.need(type(intent)is dict,'native receipt must carry exact durable INTENT descriptor');c.descriptor(intent);c.need(intent['path']==intent_desc['path'],'literal native intent artifact')
    original=c.capture_json(intent,budget,roots)
    for key in('schema','job_id','kind','ordinal','source_files','inputs','worker_only_label_inputs','host_prepared_label_body_reads','work_root','workspace_origin','workspace_inputs','script','args','original_origin','phase_original_deadline','cpu_reservation_is_not_unknown_survivor_cost_bound','worker_io_reservation','worker_io_reservation_refunded','arbitrary_native_io_measured'):_eq(original[key],body[key],'durable prelaunch native intent '+key)
    c.need(original['status']=='entered','original entered intent, not rewritten completion')
    commands=body['host_commands'];c.need(type(commands)is list and len(commands)>=7,'whole original Docker command history');streams=[]
    prefix=[cfg['docker_binary']['path'],'--host',cfg['docker_endpoint'],'--config',str(root/'docker-config')]
    for command in commands:
        c.need(command['status']=='completed','no failed native helper command may disappear');o=command['observation'];argv=prefix+command['arguments'];observer.natural(o,argv,_phase_clock(budget,deadline));c.need(start<=command['started_monotonic']<=o['started_monotonic']<=o['ended_monotonic']<=command['ended_monotonic']<=deadline,'nested original host-command timing')
        stdout=_stream_hex(command,'stdout',o,cfg['stream_cap_bytes']);stderr=_stream_hex(command,'stderr',o,cfg['stream_cap_bytes']);c.need(len(stdout)+len(stderr)<=cfg['stream_cap_bytes'],'aggregate exact helper streams');streams.append((stdout,stderr))
    con=body['container_observation'];name=con['container_name'];c.need(type(name)is str and name.startswith('neural010-')and len(name)==42 and all(ch in '0123456789abcdef'for ch in name[10:]),'source-owned unique container identity')
    _eq(commands[0]['arguments'],['image','inspect',cfg['image_digest']],'exact existing-image inspection');image=c.parse(streams[0][0]);c.need(type(image)is list and len(image)==1 and image[0]['Id']==cfg['image_digest'],'actual pinned existing image')
    mounts=[(d['path'],d['path'],True)for d in selected.values()]+[(str(work),'/work',False),(str(work),str(work),False)]
    create=['create','--pull','never','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--user',cfg['user'],'--pids-limit',str(cfg['pids_limit']),'--memory',str(cfg['memory_bytes']),'--memory-swap',str(cfg['memory_bytes']),'--cpus',str(cfg['cpus']),'--tmpfs','/tmp:rw,noexec,nosuid,size='+str(cfg['tmpfs_bytes']),'--workdir','/work','--env','PYTHONDONTWRITEBYTECODE=1']
    for host,target,ro in mounts:create+=['--mount','type=bind,src='+host+',dst='+target+(',readonly'if ro else'')]
    create+=['--entrypoint',cfg['python'],cfg['image_digest'],'-I','-B',script,*[a.replace('{WORK}',str(work))for a in args]];_eq(commands[1]['arguments'],create,'exact no-network read-only source/data mounts and method argv')
    c.digest(con['container_id']);c.need(streams[1][0].decode().strip()==con['container_id']and con['image_digest']==cfg['image_digest'],'exact originally created container')
    inspections=[];inspection_ordinals=[];starts=[];stats=[]
    for index,command in enumerate(commands[2:-2],2):
        a=command['arguments']
        if a==['start','--attach',name]:starts.append(index)
        elif a==['stats','--no-stream','--format','{{json .}}',name]:stats.append(index)
        else:
            _eq(a,['inspect',name],'only exact owned-container monitor inspections');v=c.parse(streams[index][0]);c.need(type(v)is list and len(v)==1 and v[0]['Name']=='/'+name and v[0]['Id']==con['container_id']and v[0]['Image']==cfg['image_digest'],'captured actual owned-container inspection');inspections.append(v[0]);inspection_ordinals.append(index)
            host=v[0]['HostConfig'];c.need(host['NetworkMode']=='none'and host['ReadonlyRootfs']is True and host['Memory']==host['MemorySwap']==cfg['memory_bytes']and host['NanoCpus']==int(cfg['cpus']*1000000000)and host['PidsLimit']==cfg['pids_limit']and v[0]['Config']['User']==cfg['user'],'actual original selected runtime resource configuration')
            actual={(m['Source'],m['Destination'],not m['RW'])for m in v[0]['Mounts']if m['Type']=='bind'};c.need(actual==set(mounts),'actual exact-file mount custody, no extra label ancestor')
    c.need(len(starts)==1 and len(inspections)>=2,'one workload and both initial/final original inspections');_eq(con['final_inspection'],inspections[-1],'actual final inspection body');_eq(body['observation'],commands[starts[0]]['observation'],'original attached workload observation');_eq(con['workload_observation'],body['observation'],'container workload observation join')
    for index in stats:_monitor_stats(commands[index],streams[index][0],name,index,starts[0],inspection_ordinals[-1],body['observation'])
    _eq(commands[-2]['arguments'],['rm','--force',name],'owned retirement only after recorded natural completion');_eq(commands[-1]['arguments'],['ps','--all','--filter','name=^/'+name+'$','--format','{{.ID}}'],'exact owned-container absence query');c.need(streams[-1][0].strip()==b'','actual final absence observation');_eq(con['retirement_observation'],commands[-2]['observation'],'original retirement observation');native.natural(body)
    _eq(body['resources'],[con],'complete exact owned container resource history')
    for label,raw in zip(('stdout','stderr'),streams[starts[0]]):
        desc_stream={'path':str(root/(label+'.bin')),**c.pin(raw)};_eq(c.capture(desc_stream,budget,roots,empty=True),raw,'actual retained original native stream')
    c.need(c.typed_equal(c.parse(streams[starts[0]][0]),operation['completion']),'actual native stdout supplies exact completion descriptor')
    budget.check_clock();return {**body,'receipt':desc}


def _replay(request,budget,roots,legacy):
    c.exact(request,SEAL_FIELDS);c.need(request['schema']=='neural010-four-stream-seal-request-v1','complete source-owned seal request')
    event=_source(request,budget,roots);p=reference_study.preparation(request['preparation'],budget,legacy);study=c.capture_json(request['reference_study'],budget,roots)
    c.exact(study,('schema','preparation','panel','metadata','reference_source','operations','final_folds','reference_counts','observer_own_exit_established','assessment_operand_opened','global_assessment_release_authorized'));c.need(study['schema']=='neural010-reference-study-provisional-v1'and study['observer_own_exit_established']is False and study['assessment_operand_opened']is False and study['global_assessment_release_authorized']is False,'honest target-free provisional study')
    for k,w in(('preparation',p['receipt_pin']),('panel',p['panel_pin']),('metadata',p['metadata_pin']),('reference_source',request['reference_source']),('reference_counts',schedule.expected_counts())):_eq(study[k],w,'same original study '+k)
    admitted=schedule.complete_reference_admission(p['rows'],study['operations'])
    # Reuse concrete source-owned request/admit algorithms, never producer.run.
    replay=reference_study.ReferenceStudy.__new__(reference_study.ReferenceStudy);replay.p=p;replay.source=request['reference_source'];replay.identity=_descriptor_pin(request['reference_source']);replay.limits=request['reference_limits'];replay.budget=budget;replay.legacy=legacy;replay.ops={};replay.features={};replay.final={};replay.reference_source_files=request['native_source_files']
    for ordinal,operation in enumerate(study['operations']):
        c.exact(operation,('job','request','completion','output','native','authenticated_artifacts','worker_only_label_outputs','record','previous','status','returncode','natural_completion','unknown_survivors'));_eq(operation['native'],operation['record'],'same original operation receipt')
        job=operation['job'];wanted,inputs,opaque=replay.request(job);actual=c.capture_json(operation['request'],budget,roots);_eq(actual,wanted,'deterministic exact current-fold source request')
        native_body=_native(operation,[operation['request'],*inputs],opaque,request,ordinal,budget,roots)
        complete=c.capture_json(operation['completion'],budget,roots);_eq(complete['output'],operation['output'],'exact complete output identity');out=c.capture_json(operation['output'],budget,roots)
        admitted_artifacts=replay.admit(job,actual,operation['request'],native_body,complete,out,completion_descriptor=operation['completion'])
        if job['kind']=='fit':
            required_rows=sum(r['duration_seconds']for r in p['rows']if r['patient_id']in job['training_people']);_eq(out['complete_training_rows'],required_rows,'every selected training second fitted')
            if job['inner']is not None:c.need(out['selection_threshold']is None,'inner model is unselected')
            elif job['arm']=='signal_reference':c.finite(out['selection_threshold'])
            else:_eq(out['selection_threshold'],replay.ops[job['dependencies'][0]]['body']['threshold'],'final threshold fixed by complete inner selection')
        elif job['kind']=='infer':
            fitted=replay.ops[job['dependencies'][0]]['body']
            for key in('grid_index','support_sha256'):_eq(out[key],fitted[key],'same sealed fitted '+key)
            _eq(out['threshold'],fitted['selection_threshold']if job['inner']is None else None,'same sealed threshold before any outer query')
            _eq(out['threshold_kind'],'amplitude'if job['arm']=='signal_reference'else'probability','fixed threshold interpretation')
        elif job['kind']=='validate':
            prediction=replay.ops[job['dependencies'][1]]['body']
            for key in('grid_index','support_sha256','model','fit_receipt'):_eq(out[key],prediction[key],'validation retains exact model ancestry '+key)

        for key in('authenticated_artifacts','worker_only_label_outputs'):_eq(operation[key],admitted_artifacts[key],'same exact admitted output custody '+key)
        replay.ops[job['id']]={**operation,'body':out}
    wanted_folds=[{'outer':person,'arm':arm,**replay.final[(person,arm)]}for person in p['people']for arm in c.ARMS];_eq(study['final_folds'],wanted_folds,'all92 exact sealed final fold outputs')
    ids=[op['job']['id']for op in study['operations']];dispositions=schedule.dispositions(ids,ids,ids,[])
    c.need(len(ids)==29781 and admitted['counts']['fit']==9706,'all complete prescribed jobs and fits')
    return {'prepared':p,'study':study,'counts':admitted,'dispositions':dispositions,'final':replay.final,'event_source':event}


def _carriers(replayed,budget,roots,legacy):
    p=replayed['prepared'];records=p['panel'];event=legacy['event_protocol'];scorer=legacy['scorer']
    for arm in c.ARMS:
        rows=[]
        for person in p['people']:
            fold=replayed['final'][(person,arm)]['body'];context={'panel_people':p['people'],'outer_person':person,'inner_person':None};_eq(fold['context'],context,'final outer context');c.need(fold['condition']==reference_study.condition(arm)and fold['family']==reference_study.family(arm),'exact final condition')
            expected=sorted((r for r in p['rows']if r['patient_id']==person),key=lambda r:r['recording_id']);c.need(len(fold['records'])==len(expected),'whole final outer recording set')
            c.need(fold['threshold_kind']==('amplitude'if arm=='signal_reference'else'probability'),'fixed threshold interpretation');threshold=c.finite(fold['threshold'])
            if arm!='signal_reference':c.need(0<=threshold<=1,'selected frozen probability threshold')
            for output,meta in zip(fold['records'],expected):
                c.exact(output,('recording_id','patient_id','duration_seconds','probabilities','scores','events'))
                for key in('recording_id','patient_id','duration_seconds'):_eq(output[key],meta[key],'same full recorded geometry')
                d=meta['duration_seconds'];prob=arrays.vector(output['probabilities'],d,'probabilities',budget,roots);score=arrays.vector(output['scores'],d,'scores',budget,roots)
                if arm=='signal_reference':c.need(all(x in(0.,1.)for x in prob)and score==[int(x)for x in prob],'original historical signal decisions')
                else:c.need(score==[int(x>=threshold)for x in prob],'every second agrees with sealed threshold')
                derived=event.from_scores(score,d);_eq(output['events'],derived,'independently recomputed original canonical events')
                rows.append({'recording_id':meta['recording_id'],'scores':score,'events':derived})
        rows.sort(key=lambda r:r['recording_id']);c.need([r['recording_id']for r in rows]==sorted(records),'each original recording once per stream')
        carrier={'schema_version':1,'task_id':'NEURAL-009','records':rows};events=scorer.predictions(carrier,records);budget.check_clock();yield arm,carrier,events


def _admission(request,replayed):
    return {'schema':'neural010-four-stream-admission-v1','source':request['source'],'reference_study':request['reference_study'],'reference_phase_request':request['reference_phase_request'],'counts':replayed['counts'],'dispositions':replayed['dispositions'],'all_final_array_bodies_and_events_admitted':True,'all_model_bodies_stream_authenticated':True,'worker_only_label_bodies_read':False,'assessment_operand_accepted':False,'observer_own_exit_established':False,'physical_or_numerical_qualification_created':False}


def seal_reference_study(request,*,budget,capture_roots,output_root,legacy):
    """References phase creates this before its own independently observed exit."""
    roots=[c.absolute(str(r))for r in capture_roots];replayed=_replay(request,budget,roots,legacy);out=_empty_output(output_root,budget);predictions={}
    for arm,carrier,events in _carriers(replayed,budget,roots,legacy):predictions[arm]=c.publish_json(out/(arm+'.predictions.json'),carrier,budget)
    admission=_admission(request,replayed)
    apin=c.publish_json(out/'ADMISSION.json',admission,budget);p=replayed['prepared']
    master={'schema':'neural010-four-stream-master-v1','task_id':c.TASK,'seal_request':request,'reference_study':request['reference_study'],'source':request['source'],'reference_source':request['reference_source'],'reference_phase_request':request['reference_phase_request'],'preparation':p['receipt_pin'],'panel':p['panel_pin'],'metadata':p['metadata_pin'],'event_source':replayed['event_source'],'reference_counts':schedule.expected_counts(),'dispositions':replayed['dispositions'],'final_folds':replayed['study']['final_folds'],'predictions':predictions,'admission':apin,'observer_own_exit_established':False,'assessment_operand_opened':False,'global_assessment_release_authorized':False}
    mpin=c.publish_json(out/'MASTER.json',master,budget);return {'master':mpin,'admission':apin,'predictions':predictions}


def _reference_observer(request,authority,budget,roots,master):
    spec_raw=c.capture(request['reference_spec'],budget,roots);spec=c.parse(spec_raw);receipt_raw=c.capture(request['reference_observation'],budget,roots);receipt=c.parse(receipt_raw);external_raw=c.capture(request['reference_external'],budget,roots);external=c.parse(external_raw)
    c.need(spec['phase']=='references'and spec['provider_config']is None and spec['credential_names']==[],'exact credential-free original reference observer phase');_observer_source_and_roster(spec,request['source'],'references',budget,roots);_eq(spec['request'],master['reference_phase_request'],'exact original reference phase request')
    c.need(receipt_raw==c.encoded(receipt)and external_raw==c.encoded(external),'root/observer original canonical bytes, no replacement reserialization')
    _eq(authority['reference_external_authority']['external_body'],c.pin(external_raw),'actual original external raw body pin')
    observer.admit_external_closure(receipt,external,expected_spec=spec,receipt_descriptor=request['reference_observation'],budget=budget,external_authority=authority['reference_external_authority'])
    observed={a['path']:{k:a[k]for k in('path','bytes','sha256')}for a in receipt['artifacts']}
    for desc in [request['master'],request['master_admission'],master['reference_study'],*master['predictions'].values()]:_eq(observed.get(desc['path']),desc,'master/study/streams were actually captured by original completed reference observer')
    return {'spec':request['reference_spec'],'receipt':request['reference_observation'],'external':request['reference_external'],'source':request['source'],'request':master['reference_phase_request']}


def release_assessment(request,*,protected_authority,budget,capture_roots,output_root,legacy):
    """Assessment descriptor access occurs at the single marked line below."""
    c.exact(request,RELEASE_FIELDS);c.need(request['schema']=='neural010-assessment-release-request-v1','exact protected release request');a=protected_authority;c.exact(a,AUTHORITY_FIELDS);c.need(a['schema']=='neural010-root-assessment-release-authority-v1','separately protected root-selected release authority')
    c.source_authority(a['execution_authority'],request['source']);_eq(a['release_request'],c.pin(c.encoded(request)),'actual root-selected exact canonical release request')
    for key in('source','master','master_admission','reference_spec','reference_observation','reference_external'):_eq(a[key],request[key],'root-selected release identity '+key)
    c.need(type(a['original_origin'])is float and type(a['original_deadline'])is float and a['original_origin']==float(budget.origin)and a['original_deadline']==float(budget.end),'unchanged protected release original clock')
    roots=[c.absolute(str(r))for r in capture_roots];master_raw=c.capture(request['master'],budget,roots);master=c.parse(master_raw);c.exact(master,MASTER_FIELDS);c.need(master_raw==c.encoded(master)and master['schema']=='neural010-four-stream-master-v1'and master['task_id']==c.TASK,'exact canonical complete master body')
    for key in('observer_own_exit_established','assessment_operand_opened','global_assessment_release_authorized'):c.need(master[key]is False,'master cannot self-certify future observer exit or assessment release')
    _eq(master['source'],request['source'],'exact source of master');_eq(master['seal_request']['source'],request['source'],'same full replay source');_eq(master['admission'],request['master_admission'],'same actual master admission receipt');_eq(master['reference_counts'],schedule.expected_counts(),'full original job cardinality');c.exact(master['predictions'],c.ARMS)
    closure=_reference_observer(request,a,budget,roots,master)
    replayed=_replay(master['seal_request'],budget,roots,legacy);p=replayed['prepared']
    for key,wanted in(('reference_study',master['seal_request']['reference_study']),('reference_source',master['seal_request']['reference_source']),('reference_phase_request',master['seal_request']['reference_phase_request']),('preparation',p['receipt_pin']),('panel',p['panel_pin']),('metadata',p['metadata_pin']),('event_source',replayed['event_source']),('dispositions',replayed['dispositions']),('final_folds',replayed['study']['final_folds'])):_eq(master[key],wanted,'same master complete scientific/source lineage '+key)
    admission=c.capture_json(request['master_admission'],budget,roots);_eq(admission,_admission(master['seal_request'],replayed),'exact original complete admission document, independently replayed')
    events={}
    for arm,carrier,hyp in _carriers(replayed,budget,roots,legacy):
        desc=master['predictions'][arm];raw=c.capture(desc,budget,roots);c.need(raw==c.encoded(carrier),'all exact merged bytes agree with92 full fold outputs');legacy['scorer'].predictions(c.parse(raw),p['panel']);events[arm]=hyp
    # No protected assessment descriptor value has been accessed above this line.
    # Complete original four streams, 29,781 jobs, models, original observations
    # and separate root external closure are now admitted under selected authority.
    out=_empty_output(output_root,budget);budget.check_clock()
    assessment=a['assessment']
    c.descriptor(assessment);_eq(_descriptor_pin(assessment),p['receipt']['assessment'],'independently prepared original global assessment bytes')
    c.need(assessment['path']==str(p['private_root']/'assessment.json'),'literal separately protected assessment location')
    raw=c.capture(assessment,budget,roots);gold=legacy['scorer'].targets(c.parse(raw),p['panel'],p['panel_pin']['sha256'])
    byid={r['recording_id']:r for r in p['rows']};hrows=[]
    for rid,row in sorted(p['panel'].items()):
        hrows.append({'recording_id':rid,'patient_id':row['patient_id'],'montage_id':byid[rid]['montage_id'],'duration_seconds':row['duration_seconds'],'signal':{k:row[k]for k in('path','bytes','sha256')},'annotations':gold[rid],'arms':{arm:events[arm][rid]for arm in('candidate','signal_reference','montage_only')}})
    h={'schema_version':1,'task_id':c.TASK,'phase':'post_prediction_analysis','sealed_inputs':{'panel':p['panel_pin']['sha256'],'targets':assessment['sha256'],**{arm:master['predictions'][arm]['sha256']for arm in('candidate','signal_reference','montage_only')},'phase1_seal':request['master']['sha256']},'records':hrows};legacy['analysis_core'].validate_packet(h);hpin=c.publish_json(out/'H.json',h,budget)
    m={'schema_version':1,'task_id':c.TASK,'phase':'post_prediction_matched_diagnostic','historical_packet':hpin,'four_stream_seal':request['master'],'matched_prediction':master['predictions']['matched_no_eeg'],'records':[{'recording_id':rid,'events':events['matched_no_eeg'][rid]}for rid in sorted(p['panel'])]};grading.matched_packet(h,m,hpin,request['master'],legacy['analysis_core']);mpin=c.publish_json(out/'M.json',m,budget)
    descriptions=[{'outer':f['outer'],'arm':f['arm'],'fit_receipt':f['body']['fit_receipt'],'model':f['body']['model'],'source_identity':f['body']['source_identity'],'grid_index':f['body']['grid_index'],'support_sha256':f['body']['support_sha256'],'threshold':f['body']['threshold'],'threshold_kind':f['body']['threshold_kind']}for f in master['final_folds']]
    envelope={'schema':'neural010-four-stream-analysis-v1','task_id':c.TASK,'four_stream_seal':request['master'],'historical_packet':hpin,'matched_packet':mpin,'event_source':master['event_source'],'source':request['source'],'recordings':686,'biological_patients':23,'observed_seconds':sum(r['duration_seconds']for r in hrows),'realized_detectors':descriptions,'expected_report_included':False};epin=c.publish_json(out/'ENVELOPE.json',envelope,budget)
    receipt={'schema':'neural010-protected-assessment-release-v1','source':request['source'],'request':c.pin(c.encoded(request)),'master':request['master'],'master_admission':request['master_admission'],'reference_closure':closure,'assessment':assessment,'assessment_body_captures':1,'historical_packet':hpin,'matched_packet':mpin,'envelope':epin,'all29781_jobs_and9706_fits_admitted_before_assessment':True,'physical_or_scientific_qualification_created':False,'release_observer_own_future_exit_established':False};rpin=c.publish_json(out/'RELEASE.json',receipt,budget)
    waveforms=[{'path':str(p['public_root']/row['path']),**{k:row[k]for k in('bytes','sha256')}}for rid,row in sorted(p['panel'].items())]
    return {'schema':'neural010-released-analysis-v1','historical':hpin,'matched':mpin,'envelope':epin,'master':request['master'],'waveforms':waveforms,'receipt':rpin}
