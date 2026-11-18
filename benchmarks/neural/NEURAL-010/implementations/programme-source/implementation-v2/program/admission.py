"""Independent source-owned analyst artifact and native/provider admission."""
import json,re,types
from pathlib import Path
import common as c
import native,analysts
from observation import observer
from transport.provider import parse_completion

def body(d,budget):return c.capture_json(d,budget,[Path(d['path']).parent])
def local_cost(value,limits,budget):
    c.need(value['original_origin']==budget.origin and budget.origin<=value['started_monotonic']<=value['original_deadline']==min(budget.end,value['started_monotonic']+limits['seconds']),'same original clock and preselected local interval')
    expected={k:v for k,v in limits.items()if k!='seconds'};c.need(c.typed_equal(value['limits'],expected),'same permitted local counters');c.exact(value['logical_used'],expected)
    for k,n in value['logical_used'].items():c.integer(n,0,c.integer(expected[k]))
    c.need(value['physical_IO_or_RSS_measured']is False,'logical reservations do not become physical measurements')
def stream_hex(value,pin,observation):
    c.need(type(value)is str and len(value)%2==0,'complete original hexadecimal stream')
    raw=bytes.fromhex(value);c.need(c.pin(raw)==pin,'exact original captured stream')
    c.need(type(observation['bytes'])is int and type(observation['retained_bytes'])is int and observation['bytes']==observation['retained_bytes']==len(raw)and observation['sha256']==observation['retained_sha256']==pin['sha256'],'whole stream EOF identity')
    return raw

def native_job(descriptor,*,job_id,kind,script,args,inputs,sources,workspace,config,phase_limits,context_deadline,budget):
    n=body(descriptor,budget);native.natural(n);c.need(n['schema']=='neural010-native-job-v1'and n['job_id']==job_id and n['kind']==kind and n['script']==script and c.typed_equal(n['args'],args),'exact closed native producer role/argv')
    c.need(type(n['ordinal'])is int and n['ordinal']>=0 and n['status']=='completed'and type(n['returncode'])is int and n['returncode']==0 and n['natural_completion']is True and n['unknown_survivors']is False,'complete original native record')
    selected={}
    for d in [*sources,*inputs]:
        c.descriptor(d);c.need(d['path']not in selected or c.typed_equal(selected[d['path']],d),'consistent repeated input identity');selected[d['path']]=d
    c.need(c.typed_equal(n['source_files'],sources)and c.typed_equal(n['inputs'],list(selected.values()))and n['worker_only_label_inputs']==[],'exact analyst input/source mounts; no training-label view')
    c.need(n['worker_io_reservation']is None and n['worker_io_reservation_refunded']is False and n['arbitrary_native_io_measured']is False,'arbitrary candidate IO is not a false measured total')
    native.admit_durability(n,config)
    c.need(c.typed_equal(n['workspace_origin'],workspace),'exact complete prior tool workspace origins')
    directory=Path(descriptor['path']).parent;work=directory/'work';c.need(n['work_root']==str(work)and n['intent']['path']==str(directory/'INTENT.json'),'literal original job/intent paths')
    intent=body(n['intent'],budget)
    c.need(intent['status']=='entered','prelaunch intent is not a fabricated complete record')
    for key in ('schema','job_id','kind','ordinal','source_files','inputs','worker_only_label_inputs','host_prepared_label_body_reads','work_root','workspace_inputs','workspace_origin','script','args','original_origin','phase_original_deadline','cpu_reservation_is_not_unknown_survivor_cost_bound','worker_io_reservation','worker_io_reservation_refunded','arbitrary_native_io_measured'):
        c.need(c.typed_equal(intent[key],n[key]),'original prelaunch exact '+key)
    c.need(len(n['workspace_inputs'])==len(workspace),'complete copied workspace input roster')
    for origin,destination in zip(workspace,n['workspace_inputs']):
        c.exact(origin,('relative_path','source'));relative=origin['relative_path']
        c.need(type(relative)is str and not relative.startswith('/')and all(x not in('','.','..')for x in relative.split('/')),'confined workspace origin')
        c.need(destination['path']==str(work/relative)and c.typed_equal({k:destination[k]for k in('bytes','sha256')},{k:origin['source'][k]for k in('bytes','sha256')}),'exact whole-copy origin/destination bytes')
        c.authenticate_stream(origin['source'],budget,[Path(origin['source']['path']).parent],empty=True)
    for d in selected.values():c.authenticate_stream(d,budget,[Path(d['path']).parent],empty=True)
    cost=n['budget'];c.need(c.typed_equal(cost['limits'],phase_limits)and cost['origin_monotonic']==budget.origin,'same preselected nested transport limits and original origin')
    context_deadline=c.finite(context_deadline,0);c.need(context_deadline<=budget.end,'context does not extend complete study')
    c.need(cost['deadline_monotonic']==n['phase_original_deadline']==min(context_deadline,cost['started_monotonic']+config['tool_seconds']+3*config['cleanup_seconds']),'exact preselected native closeout interval under original context clock')
    c.exact(cost['used'],phase_limits)
    for key,amount in cost['used'].items():c.integer(amount,0,c.integer(phase_limits[key]))
    clock_view=types.SimpleNamespace(origin=budget.origin,end=n['phase_original_deadline'])
    commands=n['host_commands'];c.need(type(commands)is list and len(commands)>=7,'whole exact-owned Docker lifecycle')
    cfg=config;name=n['container_observation']['container_name'];c.need(type(name)is str and re.fullmatch('neural010-[0-9a-f]{32}',name),'exact predeclared owned container name')
    prefix=[cfg['docker_binary']['path'],'--host',cfg['docker_endpoint'],'--config',str(directory/'docker-config')]
    parsed=[];creates=[];starts=[];removals=[];absence=[];inspects=[];stats=[]
    for index,command in enumerate(commands):
        c.need(command['status']=='completed','no discarded failed host command')
        argv=prefix+command['arguments'];o=command['observation'];observer.natural(o,argv,clock_view)
        c.need(type(n['original_origin'])is float and n['original_origin']==budget.origin and o['original_deadline_monotonic']<=budget.end,'native host observation retains original clock')
        out=stream_hex(command['stdout_hex'],command['stdout'],o['streams']['stdout']);stream_hex(command['stderr_hex'],command['stderr'],o['streams']['stderr']);a=command['arguments']
        c.need(type(a)is list and a,'exact host command operands')
        if a[0]=='image':c.need(index==0 and a==['image','inspect',cfg['image_digest']],'first command pins existing image');image=c.parse(out);c.need(len(image)==1 and image[0]['Id']==cfg['image_digest'],'actual selected image')
        elif a[0]=='create':creates.append((index,a,out))
        elif a==['start','--attach',name]:starts.append((index,o,out))
        elif a==['inspect',name]:
            values=c.parse(out);c.need(type(values)is list and len(values)==1 and values[0]['Name']=='/'+name,'actual exact-owned inspection');inspects.append((index,values[0]))
        elif a==['stats','--no-stream','--format','{{json .}}',name]:
            if out.strip():c.need(type(c.parse(out))is dict,'original owned-container stats JSON when available')
            stats.append(index)
        elif a==['rm','--force',name]:removals.append(index)
        elif a==['ps','--all','--filter','name=^/'+name+'$','--format','{{.ID}}']:c.need(out.strip()==b'','observed owned-container absence');absence.append(index)
        else:c.need(False,'unselected host command in closed analyst execution')
        parsed.append(out)
    c.need(len(creates)==len(starts)==len(removals)==len(absence)==1 and len(inspects)>=2,'one complete lifecycle with all observed inspections')
    create_i,create_args,container_id=creates[0];start_i,start_o,start_out=starts[0]
    c.need(create_i==1 and create_i<inspects[0][0]<start_i<inspects[-1][0]<removals[0]<absence[0]==len(commands)-1,'original create/inspect/run/natural-final/retirement order')
    c.need(all(start_i<index<inspects[-1][0]for index in stats),'stats only within the original workload interval')
    for index in stats:
        o=commands[index]['observation'];c.need(start_o['started_monotonic']<=o['started_monotonic']<=o['ended_monotonic']<=start_o['ended_monotonic'],'actual monitor command lies within observed attached workload')
    mounts=[(d['path'],d['path'],True)for d in selected.values()]+[(str(work),'/work',False),(str(work),str(work),False)]
    expected=['create','--pull','never','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--user',cfg['user'],'--pids-limit',str(cfg['pids_limit']),'--memory',str(cfg['memory_bytes']),'--memory-swap',str(cfg['memory_bytes']),'--cpus',str(cfg['cpus']),'--tmpfs','/tmp:rw,noexec,nosuid,size='+str(cfg['tmpfs_bytes']),'--workdir','/work','--env','PYTHONDONTWRITEBYTECODE=1']
    for host,target,readonly in mounts:expected+=['--mount','type=bind,src='+host+',dst='+target+(',readonly'if readonly else'')]
    expected+=['--entrypoint',cfg['python'],cfg['image_digest'],'-I','-B',script,*[a.replace('{WORK}',str(work))for a in args]]
    c.need(c.typed_equal(create_args,expected),'exact readonly data/source and writable current-work mounts; no protected/other-context input')
    current=inspects[0][1];host=current['HostConfig'];c.need(current['Id']==container_id.decode().strip()==n['container_observation']['container_id']and current['Image']==cfg['image_digest'],'same actual container/image')
    c.need(host['NetworkMode']=='none'and host['ReadonlyRootfs']is True and type(host['Memory'])is int and host['Memory']==host['MemorySwap']==cfg['memory_bytes']and host['NanoCpus']==int(cfg['cpus']*1000000000)and host['PidsLimit']==cfg['pids_limit']and current['Config']['User']==cfg['user'],'actual selected isolation/resource configuration')
    actual={(m['Source'],m['Destination'],not m['RW'])for m in current['Mounts']if m['Type']=='bind'};c.need(actual==set(mounts),'actual exact complete mounted path set')
    c.need(c.typed_equal(inspects[-1][1],n['container_observation']['final_inspection'])and c.typed_equal(start_o,n['observation'])and c.typed_equal(start_o,n['container_observation']['workload_observation']),'same original workload/final inspection')
    for stream in('stdout','stderr'):
        raw=c.capture({'path':str(directory/(stream+'.bin')),'bytes':n['observation']['streams'][stream]['bytes'],'sha256':n['observation']['streams'][stream]['sha256']},budget,[directory],empty=True)
        c.need(raw==bytes.fromhex(commands[start_i][stream+'_hex']),'original attached raw stream retained')
    budget.check_clock();return n

def author_episode(descriptor,*,identity,replication,inputs,config,sources,budget):
    a=body(descriptor,budget);c.need(a['schema']=='neural010-author-episode-v1'and a['identity']==identity and type(a['replication'])is int and a['replication']==replication and a['status']=='completed'and c.typed_equal(a['input_files'],inputs),'exact original isolated author context')
    local_cost(a['budget'],config['author_limits'],budget)
    provider=a['provider'];tools=a['tools'];c.need(type(provider)is list and 1<=len(provider)<=config['author_turns']and len(tools)==len(provider)-1,'every tool episode and one final source response')
    workspace=[];messages=None;final=None
    for index,p in enumerate(provider):
        c.need(p['status']=='complete'and p['response_stream_closed']is True and p['model']==config['provider']['model'],'original complete selected-model provider call')
        request=body(p['request_artifact'],budget);response=body(p['response_artifact'],budget);message,finish,usage=parse_completion(response)
        c.need(request['model']==response['model']==config['provider']['model']and request['n']==1 and request['stream']is False,'exact complete provider configuration')
        c.need(c.typed_equal(usage,p['usage']),'original provider usage, never a rerun estimate')
        expected_seed=analysts.seed(replication,config['provider']['model'],config['design_sha256'])if config['provider_seed_supported']else None
        c.need(request.get('seed')==expected_seed and p['requested_seed']==expected_seed and a['provider_seed']==expected_seed,'paired requested seed; nondeterminism still unknown')
        if messages is None:
            messages=request['messages'];c.need(type(messages)is list and len(messages)==2 and messages[1]['role']=='user'and c.typed_equal(c.parse(messages[1]['content']),a['prompt']),'actual initial declared source-owned prompt')
        else:c.need(c.typed_equal(request['messages'],messages),'complete source-owned provider conversation chain')
        messages=[*messages,message]
        if finish=='stop':c.need(index==len(provider)-1,'final source is last completed request');final=analysts.source_response(message['content'],config['max_source_bytes'])
        else:
            t=tools[index];call=message['tool_calls'][0];code=c.parse(call['function']['arguments'])['code'].encode()
            c.need(type(t['turn'])is int and t['turn']==index and c.pin(code)=={k:t['script'][k]for k in('bytes','sha256')},'actual provider tool code/source identity')
            n=native_job(t['native'],job_id=identity+'/tool/'+str(index),kind='tool',script=t['script']['path'],args=[],inputs=[t['script'],*inputs],sources=sources,workspace=workspace,config=config['native'],phase_limits=config['native_phase_limits'],context_deadline=a['budget']['original_deadline'],budget=budget)
            workspace=t['workspace'];seen=set()
            for item in workspace:
                c.need(item['relative_path']not in seen,'complete unique workspace');seen.add(item['relative_path']);c.need(item['source']['path']==str(Path(n['work_root'])/item['relative_path']),'actual current tool workspace output');c.authenticate_stream(item['source'],budget,[Path(n['work_root'])],empty=True)
            out=c.capture({'path':str(Path(t['native']['path']).parent/'stdout.bin'),'bytes':n['observation']['streams']['stdout']['bytes'],'sha256':n['observation']['streams']['stdout']['sha256']},budget,[Path(t['native']['path']).parent],empty=True)
            tool_result={'stdout':out.decode('utf-8'),'workspace':[{'relative_path':x['relative_path'],'bytes':x['source']['bytes'],'sha256':x['source']['sha256']}for x in workspace],'natural_receipt':t['native']}
            messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(tool_result,sort_keys=True,allow_nan=False)})
    c.need(final is not None and c.pin(final)=={k:a['sealed_source'][k]for k in('bytes','sha256')},'same final provider source before any final execution')
    c.authenticate_stream(a['sealed_source'],budget,[Path(a['sealed_source']['path']).parent]);budget.check_clock();return a
