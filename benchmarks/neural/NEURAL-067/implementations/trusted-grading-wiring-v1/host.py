"""Complete full-panel NEURAL067 train/seal/causal-query/grade orchestration."""
import os,time
from pathlib import Path
from runtime_io import *
from causal_io import ARMS,Rows,Journal,retire,tree
from runtime import candidate
import trusted
import mount_policy

CAPS={'train':60000000,'query':14000000,'assemble':8200000,'grade':1000000}

def socket_identity(selection):
    p=ordinary(selection['docker_socket']);s=p.lstat()
    need(stat.S_ISSOCK(s.st_mode) and {'device':s.st_dev,'inode':s.st_ino}==selection['docker_socket_identity'],'selected local socket')

def daemon_policy(config,selection,budget):
    from runtime import lifecycle
    client=lifecycle.Docker(config['binary'],config['env'],config['check_socket'],budget)
    raw=client(['info','--format','{{json .OperatingSystem}}'],min(budget.end,time.monotonic()+5),'daemon_policy',4096)
    os_name=parse(raw);need(type(os_name)is str and len(os_name)<=256,'bounded observed daemon OS')
    observed={'OperatingSystem':os_name}
    mount_policy.gate(selection['mount_source_policy'],observed)
    budget.save(budget.root/'DAEMON.json',{'mount_source_policy':selection['mount_source_policy'],
        'observed':observed,'docker_socket':selection['docker_socket'],'docker_socket_identity':selection['docker_socket_identity'],
        'commands':client.records,'source_identity_independently_measured':False})
    return observed

def worker_files(lock,mode):
    names={'public/common.py','public/array_io.py','public/design.json'}
    d=lock['design']
    if mode=='train':names|={f'private/data/{r["run"]}/{n}.npz' for r in d['train'] for n in ('input','target')}
    elif mode=='query':names|={f'private/data/{r["run"]}/input.npz' for r in d['query']}
    elif mode=='grade':names|={'private/PRIVATE_BINDINGS.json','private/data/PREPARATION.json'}|{f'private/data/{r["run"]}/target.npz' for r in d['query']}
    else:need(mode=='assemble','fixed worker mode')
    return {n:lock['files'][n] for n in sorted(names)}

def invoke(here,bodies,lock,package,attempt,mode,tag,budget,config,extra=None,mount_extra=()):
    phase=attempt/tag;budget.mkdir(phase);out=phase/'output';budget.mkdir(out,0o777);out.chmod(0o777)
    files=worker_files(lock,mode)
    inv={'schema':'neural067_worker_invocation_v1','mode':mode,'design':lock['design_pin'],
        'files':files,'worker_source':identity(bodies['worker/worker.py'])}
    if extra:inv.update(extra)
    if mode=='grade':inv['grading_evidence']=lock['grading_evidence']
    ip=budget.save(phase/'INVOCATION.json',inv)
    mounts=[(here/'worker','/worker',True),(phase/'INVOCATION.json','/invocation.json',True),(out,'/out',False)]
    mounts += [((here/'operator-evidence/PREPARATION.json' if n=='private/data/PREPARATION.json' else package/n),'/package/'+n,True) for n in files]
    if mode=='grade':
        mounts += [(here/'operator-evidence'/(n+'.json'),'/grading-evidence/'+n+'.json',True) for n in lock['grading_evidence']]
    mounts += list(mount_extra)
    command=['-I','-B','-X','pycache_prefix=/tmp/.disabled-pycache','/worker/worker.py',
        '--invocation','/invocation.json','--invocation-sha256',ip['sha256'],'--package','/package','--output','/out']
    if mode in ('assemble','grade'):command+=['--journals','/journals']
    budget.read(sum(p['bytes'] for p in files.values())+2000000)
    if mode=='grade':budget.read(sum(p['bytes'] for p in inv['journals'])+sum(p['bytes'] for p in lock['grading_evidence'].values()))
    budget.debit(CAPS[mode]+100000)
    hp=trusted.run(command,mounts,phase,budget,config)
    raw=capture(out/'WORKER.json',100000);receipt=parse(raw)
    need(receipt['schema']=='neural067_worker_completion_v1' and receipt['mode']==mode
        and receipt['invocation']==ip and receipt['worker_source']==inv['worker_source']
        and receipt['package_files']==files and receipt['requires_external_natural_exit'] is True
        and receipt['runtime_qualified'] is False and receipt['scientific_qualification'] is False,'worker source/invocation/closure binding')
    expected=receipt['files'];need(type(expected)is dict and all(n.startswith('data/') and '..' not in Path(n).parts for n in expected),'fixed owned worker files')
    need(sum(p['bytes'] for p in expected.values())<=CAPS[mode],'full role output cap')
    full={**expected,'WORKER.json':identity(raw)}
    actual,dirs=tree(out);wanted={str(p) for n in full for p in Path(n).parents if str(p)!='.'}
    need(set(actual)==set(full) and dirs==wanted,'exact ordinary worker tree')
    for n,pin in full.items():budget.read(pin['bytes']);capture(out/n,pin['bytes'],pin)
    ap=budget.save(phase/'ADMISSION.json',{'mode':mode,'invocation':ip,'host':hp,'worker':identity(raw),'files':full})
    return {'phase':phase,'out':out,'receipt':receipt,'files':full,'admission':ap,'host':hp,'worker':identity(raw)}

def retire_output(part,budget,link):
    cp=budget.save(part['phase']/'CLOSED.json',{'admission':part['admission'],'files':part['files'],'link':link,
        'all_owned_resources_absent':True,'source_only_preparation_or_execution_evidence':True})
    retire(part['out'],part['files'],budget)
    return budget.save(part['phase']/'RETIRED.json',{'closed':cp,'output_absent':not os.path.lexists(part['out'])})

def needed_seconds(remaining_training,remaining_queries,remaining_workers):
    # Includes setup/normal cleanup; every phase also checks absolute ends locally.
    return remaining_training*610+remaining_queries*130+remaining_workers*140+30

def execute(here,bodies,selection,source_pin,end):
    repo=ordinary(selection['repository']);attempt=ordinary(selection['attempt']);lock=parse(bodies['LOCK.json'])
    package=repo/lock['package_root'];observer=attempt.with_name(attempt.name+'.observer')
    need(not os.path.lexists(attempt) and attempt.parent.is_dir() and attempt.parent.stat().st_dev==repo.stat().st_dev,'fresh same-volume attempt')
    s=os.statvfs(attempt.parent);need(s.f_bavail*s.f_frsize>=FLOOR+selection['other_bytes']+OWN,'full future reservation')
    budget=Budget(attempt,selection['other_bytes'],end,(attempt,observer),write_limit=WRITE-131072,meta_limit=META-131072)
    budget.mkdir(attempt);result={'schema':'neural067_causal_attempt_v1','success':False,'source_manifest':source_pin,
        'scope':lock['scope'],'runtime_qualified':False,'scientific_qualification':False,'mechanism_adherence_proven':False}
    try:
        budget.read(400000000) # Shared independent-parent final-verification reserve, not a second allowance.
        socket_identity(selection)
        for n in ('docker-home','docker-config','states','journals','queries'):budget.mkdir(attempt/n)
        env={'PATH':'/usr/bin:/bin','HOME':str(attempt/'docker-home'),'DOCKER_CONFIG':str(attempt/'docker-config'),
            'DOCKER_HOST':'unix://'+selection['docker_socket'],'PYTHONDONTWRITEBYTECODE':'1'}
        for key,filename,cap in [('program','program.py',1048576),('method','method.json',16384)]:
            budget.read(cap);raw=capture(selection[key]['path'],cap,selection[key]);raw.decode('utf8')
            if key=='method':need(type(parse(raw))is dict and parse(raw),'genuine bounded method disclosure')
            budget.write(attempt/filename,raw,receipt=True)
        budget.write(attempt/'CONTRACT.md',bodies['CONTRACT.md'],receipt=True)
        commit=budget.save(attempt/'PROGRAM_COMMIT.json',{'program':{k:selection['program'][k] for k in ('bytes','sha256')},
            'method':{k:selection['method'][k] for k in ('bytes','sha256')},'no_training_release_before_commit':True,
            'related_exposure':selection['related_exposure'],'prior_exposure_verified':False})
        config={'program':attempt/'program.py','program_pin':identity(capture(attempt/'program.py',1048576)),
            'contract':attempt/'CONTRACT.md','contract_pin':identity(bodies['CONTRACT.md']),'image':lock['image'],
            'binary':selection['docker_binary'],'env':env,'check_socket':lambda:socket_identity(selection),'states':{},
            'mount_source_policy':selection['mount_source_policy']}
        result['daemon_observed']=daemon_policy(config,selection,budget)
        for row in (lock['selected_source'],lock['selected_export']):budget.read(row['bytes']);capture(repo/row['path'],row['bytes'],row)
        budget.read(lock['design_pin']['bytes']);capture(package/'public/design.json',lock['design_pin']['bytes'],lock['design_pin'])
        # Cache preparation cannot release any candidate input; first candidate starts only after closure.
        cache=invoke(here,bodies,lock,package,attempt,'query','cache',budget,config)
        c=parse(capture(cache['out']/'data/CACHE.json',100000,cache['files']['data/CACHE.json']))
        need(c['schema']=='neural067_private_query_cache_v1' and c['rows']==34490 and c['row_bytes']==368
            and c['candidate_mount_allowed'] is False and c['query_target_reads']==0,'full private cache')
        need([r['run'] for r in c['runs']]==[r['run'] for r in lock['design']['query']],'all ordered query cache runs')
        for actual,expected in zip(c['runs'],lock['design']['query']):
            need(actual['n_rows']==expected['n_rows'] and actual['input_pin']==expected['input']
                and actual['file']==expected['run']+'.bin' and actual['bytes']==368*expected['n_rows']
                and cache['files']['data/'+actual['file']]=={k:actual[k] for k in ('bytes','sha256')},'exact query input/row identity')
        result.update(program_commit=commit,cache_admission=cache['admission'],training=[],queries=[])
        for ai,arm in enumerate(ARMS):
            need(end-time.monotonic()>needed_seconds(4-ai,56,6-ai),'remaining full training/query/grade reserves')
            part=invoke(here,bodies,lock,package,attempt,'train','train-'+arm,budget,config,{'arm':arm})
            need(part['receipt']['result']=={'training_runs':13,'arm':arm,'training_rows':135991},'all training rows per arm')
            phase=attempt/('fit-'+arm);budget.mkdir(phase);now=time.monotonic()
            state=candidate.train_phase(config,arm,part['out']/'data',attempt/'states'/(arm+'.bin'),phase,budget,now+605,now+610)
            need(state['all_owned_absent'] is True,'closed fitted-state producer')
            sp=state['state'];config['states'][arm]={'path':attempt/'states'/(arm+'.bin'),**sp,'program_sha256':selection['program']['sha256']}
            retired=retire_output(part,budget,{'program_commit':commit,'state':sp,'producer_host':state['host']})
            result['training'].append({'arm':arm,'state':sp,'producer_host':state['host'],'admission':part['admission'],'retired':retired})
        # Every model state is admitted before any first query; each query starts from its own same bytes.
        sealed=budget.save(attempt/'STATES_SEALED.json',{'program_commit':commit,'states':result['training']})
        journals=[];index=0
        for row,cr in zip(lock['design']['query'],c['runs']):
            for arm in ARMS:
                need(end-time.monotonic()>needed_seconds(0,56-index,2),'all remaining query/scoring reserves')
                phase=attempt/'queries'/f'{index:02d}';budget.mkdir(phase)
                source=Rows(cache['out']/'data'/cr['file'],{k:cr[k] for k in ('bytes','sha256')},row['run'],arm,row['n_rows'],budget)
                jp=attempt/'journals'/(row['run']+'__'+arm+'.bin');journal=Journal(jp,row['run'],arm,row['n_rows'],row['input'],budget)
                try:
                    now=time.monotonic();closed=candidate.query_phase(config,arm,config['states'][arm]['path'],source,journal,phase,budget,now+125,now+130)
                finally:
                    if not journal.closed:journal.close()
                need(closed['all_owned_absent'] is True and closed['rows']==row['n_rows'] and source.i==row['n_rows'],'complete closed query stream')
                entry={'run':row['run'],'arm':arm,'file':jp.name,**closed['journal'],'final_chain':journal.previous.hex()};journals.append(entry)
                cp=budget.save(phase/'CLOSED.json',{'program_commit':commit,'states_sealed':sealed,'run':row['run'],'arm':arm,
                    'journal':entry,'host':closed['host'],'committed_rows':row['n_rows'],'all_owned_absent':True})
                result['queries'].append({'run':row['run'],'arm':arm,'closed':cp,'host':closed['host'],'journal':entry});index+=1
        need(index==56 and len(journals)==56 and sum(lock['design']['query'][i//4]['n_rows'] for i in range(index))==137960,'complete four-arm support')
        result['cache_retired']=retire_output(cache,budget,{'states_sealed':sealed,'closed_queries':56})
        grading_input=budget.save(attempt/'GRADING_INPUT.json',{'schema':'neural067_closed_journal_grading_input_v1',
            'journals':journals,'all_query_producers_absent':True,'program_commit':commit,'states_sealed':sealed,
            'contract_sha256':lock['trusted_grading']['contract_sha256']})
        grade=invoke(here,bodies,lock,package,attempt,'grade','grade',budget,config,{'journals':journals},[(attempt/'journals','/journals',True)])
        need(grade['receipt']['result']['causal_program_execution_verified'] is False,'unchanged scorer causal limitation')
        result.update(success=True,states_sealed=sealed,grading_input=grading_input,grade={'admission':grade['admission'],'host':grade['host'],
            'worker':grade['worker'],'score':grade['files']['data/score.json']},query_blocks=56,committed_arm_rows=137960,
            controlled_read_reservations=budget.reads,write_reservations_before_final=budget.written,
            observed_live_allocation=budget.peak,claimed_protected_or_mechanistic_qualification=False)
        budget.save(attempt/'COMPLETION.json',result,cap=100000);budget.tick();return result
    except BaseException as e:
        result.update(success=False,error_type=type(e).__name__,partial_outputs_preserved=True,
            operator_recovery_required_before_retry=True,controlled_read_reservations=budget.reads,write_reservations=budget.written)
        try:budget.save(attempt/'FAILED.json',result,cap=100000)
        except BaseException:pass
        raise
