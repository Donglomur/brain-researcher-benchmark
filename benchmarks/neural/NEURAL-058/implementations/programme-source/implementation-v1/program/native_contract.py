"""Independent literal native command/configuration reconstruction; no I/O."""
import hashlib
from core import need,encoded,pin,integer


def command(python,source,bootstrap,request,origin,cutoff,limits):
    return [python,'-I','/inputs/source/program/entry.py','--mode','native',
            '--source-root','/inputs/source','--manifest','/inputs/source/RUNTIME_SOURCE.json',
            '--manifest-pin',encoded(source).decode(),'--bootstrap-pin',encoded(bootstrap).decode(),
            '--request','/inputs/request.json','--request-pin',encoded(request).decode(),
            '--origin',str(origin),'--deadline',str(cutoff),
            '--read-cap',str(limits['worker_read_bytes']),'--write-cap',str(limits['worker_write_bytes'])]


def config(engine,operation,source,argv,mounts,output,limits):
    # Exact independent reconstruction of the unchanged donor Engine config.
    bind=[{'Type':'bind','Source':r['source'],'Target':r['destination'],'ReadOnly':True,
           'BindOptions':{'Propagation':'rprivate'}} for r in mounts]
    bind.append({'Type':'bind','Source':output,'Target':'/output','ReadOnly':False,
                 'BindOptions':{'Propagation':'rprivate'}})
    nonce=hashlib.sha256(encoded([engine['study'],operation,source])).hexdigest()
    labels={'mindeye2.study':engine['study'],'mindeye2.operation':operation,'mindeye2.nonce':nonce}
    return {'Image':engine['image_id'],'Cmd':argv,'Env':['PYTHONHASHSEED=0','OMP_NUM_THREADS=1',
                'OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','HOME=/scratch'],
            'WorkingDir':'/scratch','User':engine['uid_gid'],'AttachStdout':False,'AttachStderr':False,
            'NetworkDisabled':True,'Labels':labels,'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,
                'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges:true'],'Privileged':False,
                'PidsLimit':integer(limits['pids'],1),'Memory':integer(limits['memory_bytes'],1),
                'MemorySwap':integer(limits['memory_bytes'],1),'NanoCpus':integer(limits['cpu_rate_ns'],1),
                'AutoRemove':False,'Mounts':bind,'DeviceRequests':[{'Driver':'nvidia','DeviceIDs':engine['gpu_ids'],
                'Capabilities':[['gpu']]}] if engine['gpu_ids'] else [],
                'Tmpfs':{'/scratch':'rw,noexec,nosuid,nodev,size='+str(integer(limits['scratch_bytes'],1))},
                'LogConfig':{'Type':'local','Config':{'max-size':'1m','max-file':'1'}},
                'Ulimits':[{'Name':'nofile','Soft':1024,'Hard':1024}]}}


def profile_key(product):
    inner=product['envelope']['request']
    if product['envelope']['producer']=='reference':return 'reference_'+inner['config']['family']
    need(product['envelope']['producer']=='candidate','literal native producer')
    return {'analysis':'candidate_analysis','fit':'candidate_fit',
            'numeric_features':'candidate_features','infer':'candidate_infer'}[inner['stage']]


def verify(intent,product,selection,frozen,scopes):
    limits=selection['native_profiles'][profile_key(product)]
    need(intent['limits']==limits,'exact selected phase profile')
    original_cutoff=product['envelope']['deadline']
    argv=command(selection['native_python'],frozen['pin'],frozen['manifest']['files']['program/bootstrap.py'],
                 product['request'],selection['origin'],original_cutoff,limits)
    need(intent['argv']==argv and intent['source']==frozen['pin'] and intent['original_origin']==selection['origin'],
         'literal task/source/request/clock command')
    cutoff=min(original_cutoff,intent['started']+limits['cpu_ns']/limits['cpu_rate_ns'])
    inner=product['envelope']['request']
    scope=None if product['envelope']['producer']=='reference' else inner['panel']
    need(intent['candidate_scope']==scope,'candidate work belongs to its persistent whole-panel ledger')
    if scope is not None:cutoff=min(cutoff,scopes[scope]['cutoff'])
    need(intent['cutoff']==cutoff,'same native CPU/scope cutoff without reset')
    key=hashlib.sha256(intent['operation'].encode()).hexdigest()
    expected_output=selection['roots']['output']+'/native/'+key
    need(intent['output']==expected_output and product['native']['output']==expected_output
         and intent['output_target']=='/output','exact source-owned native output namespace')
    need(intent['expected_artifacts']=={'RESULT.n058':selection['bundle_limits']['bundle_bytes'],'TERMINAL.json':1<<20}
         and intent['optional_artifacts']=={},'complete fixed output contract')
    expected=config(selection['engine'],intent['operation'],frozen['pin'],argv,intent['mounts'],expected_output,limits)
    need(intent['config']==pin(encoded(expected)),'exact independently reconstructed isolation/resource configuration')
    return True
