"""Single trusted grader; original 80 s phase, 40 s wait and 20 s cleanup."""
import re
import time
import uuid
from pathlib import Path
from common import (HERE, IMAGE, capture, decode, encoded, file_mount, need,
                    ordinary, pin, publish, scientific_mounts)
from transport.bounds import Meter, tree
from transport.engine import (Docker, LABEL, call, inspect, mounts_argv, owned,
                              resource_inventory, retire, validate_natural_exit)

THREADS=('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','OMP_THREAD_LIMIT','MKL_NUM_THREADS','NUMBA_NUM_THREADS','NUMEXPR_NUM_THREADS')
TMP='rw,noexec,nosuid,nodev,size=134217728,mode=1777'
LIMITS={'memory_bytes':3221225472,'cpu_nanos':1750000000,'cpu_soft':20,'cpu_hard':22,
        'whole_seconds':80,'wait_seconds':40,'cleanup_seconds':20,
        'source_read_bytes':8388608,'host_write_bytes':1048576,'max_cli_bytes':1048576}


def command(contract_pin, inputs_pin):
    return ['python','-I','-B','/source/grade_export.py','--contract','/source/CONTRACT.json',
            '--contract-sha256',contract_pin['sha256'],'--inputs','/source/INPUTS.json',
            '--inputs-sha256',inputs_pin['sha256']]


def create_args(item,mounts,argv,submission_pin):
    args=['container','create','--pull','never','--name',item['name'],'--label',LABEL+'='+item['owner'],
          '--network','none','--read-only','--user','65534:65534','--cap-drop','ALL',
          '--security-opt','no-new-privileges:true','--memory','3g','--memory-swap','3g','--cpus','1.75',
          '--pids-limit','64','--restart','no','--log-driver','local','--log-opt','max-size=2m',
          '--log-opt','max-file=1','--log-opt','compress=false','--tmpfs','/tmp:'+TMP,'--workdir','/tmp',
          '--ulimit','cpu=20:22','--ulimit','nofile=1024:1024','--ulimit','core=0:0',
          '--ulimit','fsize=1048576:1048576']
    for key in THREADS:args+=['--env',key+'=2']
    args+=['--env','PYTHONDONTWRITEBYTECODE=1','--env','EXPECTED_SUBMISSION_SHA256='+submission_pin['sha256']]
    return args+mounts_argv(mounts)+['--entrypoint',argv[0],IMAGE,*argv[1:]]


def admit(info,item,mounts,argv,submission_pin):
    owned(info,item,item['owner']);h,c,s=info['HostConfig'],info['Config'],info['State']
    need(info['Image']==c['Image']==IMAGE and c['Entrypoint']==[argv[0]] and c['Cmd']==argv[1:]
         and c['WorkingDir']=='/tmp' and c['User']=='65534:65534','Exact trusted grader command')
    need(s['Status']=='created' and s['Running'] is False and s['Pid']==0,'Before start admission')
    need(h['Memory']==h['MemorySwap']==LIMITS['memory_bytes'] and h['NanoCpus']==LIMITS['cpu_nanos']
         and h['PidsLimit']==64,'Original grader resource headroom')
    need(h['NetworkMode']=='none' and h['ReadonlyRootfs'] is True and h['Privileged'] is False
         and not h.get('Devices') and not h.get('DeviceRequests') and not h.get('PortBindings')
         and h.get('IpcMode')!='host' and h.get('PidMode')!='host','No host/network/device access')
    need(h.get('CapDrop')==['ALL'] and not h.get('CapAdd') and 'no-new-privileges:true' in h['SecurityOpt']
         and h['AutoRemove'] is False and h['RestartPolicy']['Name'] in ('','no')
         and h.get('OomKillDisable') in (False,None),'Exact capabilities/lifecycle')
    need(h['Tmpfs']=={'/tmp':TMP} and h['LogConfig']=={'Type':'local','Config':{'max-size':'2m','max-file':'1','compress':'false'}},'Original bounded scratch and logs')
    limits=h['Ulimits'];expected={'cpu':(20,22),'nofile':(1024,1024),'core':(0,0),'fsize':(1048576,1048576)}
    need(len(limits)==4 and {v['Name']:(v['Soft'],v['Hard']) for v in limits}==expected,'Original exact grader ulimits')
    env=dict(v.split('=',1) for v in c['Env'])
    need(len(env)==len(c['Env']) and all(env.get(k)=='2' for k in THREADS)
         and env.get('PYTHONDONTWRITEBYTECODE')=='1'
         and env.get('EXPECTED_SUBMISSION_SHA256')==submission_pin['sha256'],'Exact environment and prediction commitment')
    for rows,key in ((h['Mounts'],'Target'),([v for v in info['Mounts'] if v['Type']!='tmpfs'],'Destination')):
        need(len(rows)==len(mounts) and {v[key] for v in rows}==set(mounts),'Exact individual file mounts')
        for row in rows:
            kind,source,rw=mounts[row[key]]
            need(row['Type']==kind=='bind' and row['Source']==str(source)
                 and (row.get('ReadOnly') is True if key=='Target' else row['RW'] is False),'Exact immutable mount source')
    need(all(v['Destination']=='/tmp' and v['RW'] is True for v in info['Mounts'] if v['Type']=='tmpfs'),'Only private tmpfs')


def execute(config,output,packet_root,packet,prediction,prediction_pin,source_pin,deadline):
    """Called only after stopped predictions pass complete public-format validation."""
    started=time.monotonic();need(started+80<=deadline,'Full original 80 s grader allocation remains')
    end=started+80;work_end=end-20
    output=ordinary(output);need(not output.exists(),'Fresh one-shot grader directory');output.mkdir(mode=0o700)
    meter=Meter(LIMITS['source_read_bytes'],LIMITS['host_write_bytes'],end)
    serial=0
    def record(event,value):
        nonlocal serial
        raw=encoded({'event':event,'value':value});meter.write(len(raw))
        publish(output/(str(serial).zfill(6)+'-'+event+'.json'),raw);meter.wrote(len(raw));serial+=1
    contract_pin=pin(capture(HERE/'original/CONTRACT.json',65536))
    inputs={'schema':'neural022_finite_grade_inputs_v1','source_contract':contract_pin,
            'packet_receipt':packet['files']['receipt.json'],'candidate':prediction_pin,
            'candidate_resources_absent':True,'prediction_commit_before_private_grade':True}
    inputs_pin=publish(output/'INPUTS.json',encoded(inputs),0o444)
    descriptors=scientific_mounts('grade.py')
    descriptors.update({'/source/grade_export.py':file_mount(HERE/'grade_export.py',pin(capture(HERE/'grade_export.py',16384)),'program'),
                        '/source/INPUTS.json':file_mount(output/'INPUTS.json',inputs_pin,'contract'),
                        '/packet/receipt.json':file_mount(packet_root/'receipt.json',packet['files']['receipt.json'],'operator_reference'),
                        '/public/cases.json':file_mount(packet_root/'cases.json',packet['files']['cases.json'],'input'),
                        '/submission/predictions.json':file_mount(prediction,prediction_pin,'input'),
                        '/private/reference.npz':file_mount(packet_root/'reference.private.npz',packet['files']['reference.private.npz'],'operator_reference')})
    # This is deliberately the first private file authentication in the programme route.
    before={k:tree(v,meter) for k,v in descriptors.items()}
    mounts={k:('bind',ordinary(v['path']),False) for k,v in descriptors.items()}
    argv=command(contract_pin,inputs_pin)
    token=uuid.uuid4().hex;item={'kind':'container','name':'neural022-grade-'+token,'owner':'neural022-grade/'+token,'attempted':False,'acknowledged':False}
    caps={k:8192 for k in ('before_container_owner','before_container_name','cleanup_container_owner','cleanup_container_name','absence_container_owner','absence_container_name')}
    caps.update(create=4096,admit=131072,start=4096,wait=4096,stopped=131072,logs=65536,
                cleanup_inspect=131072,cleanup_kill=4096,cleanup_wait=4096,cleanup_remove=4096)
    engine=Docker(config['docker_binary'],config['docker_socket'],max_calls=32,reply_budget=LIMITS['max_cli_bytes'],
                  phase_caps=caps,publish=record,account_read=meter.read,reserve_read=meter.ensure_read)
    result=None;failure=None;closure=None
    record('OWNERSHIP',{'resource':item.copy(),'original_deadline':deadline,'phase_deadline':end,
                         'source':source_pin,'submission':prediction_pin,'mounts':descriptors,'limits':LIMITS})
    try:
        need(resource_inventory(engine,item,item['owner'],work_end,'before_container')==[],'Fresh owned grader')
        args=create_args(item,mounts,argv,prediction_pin);record('CREATE-INTENT',{'argv':args})
        item['attempted']=True
        ident=call(engine,args,work_end,'create',4096,5).decode('ascii').strip()
        need(re.fullmatch('[0-9a-f]{64}',ident),'Exact returned grader ID');item.update(id=ident,acknowledged=True)
        record('CREATE-ACK',item.copy())
        info=inspect(engine,'container',ident,work_end,'admit');admit(info,item,mounts,argv,prediction_pin)
        need(work_end-time.monotonic()>=55,'Full start, wait, inspect and capture remain')
        call(engine,['container','start',ident],work_end,'start',4096,5)
        need(work_end-time.monotonic()>=50,'Full 40 s wait and stopped capture remain')
        waited=call(engine,['container','wait',ident],min(work_end,time.monotonic()+40),'wait',4096,40)
        info=inspect(engine,'container',ident,work_end,'stopped');owned(info,item,item['owner'])
        state={k:info['State'][k] for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')}
        validate_natural_exit(state);need(waited.strip()==b'0','Trusted worker natural success')
        raw=call(engine,['container','logs',ident],work_end,'logs',65536,5);result=decode(raw)
        need(result['schema']=='neural022_finite_candidate_score_v1' and result['candidate_id']=='NEURAL-022'
             and result['submission_commitment']==prediction_pin and result['source_contract']==contract_pin
             and result['packet_receipt']==inputs['packet_receipt'] and result['candidate_code_executed_by_grader'] is False,
             'Exact original score identity')
        need(result['status'] in ('scored_exposed_transfer_candidate','unsupported_numerical_result')
             and result['private_target_loads']==1,'Public-admitted original numerical disposition')
        record('STOPPED-REPORT',{'state':state,'report':pin(raw)})
        need(before=={k:tree(v,meter) for k,v in descriptors.items()},'Inputs unchanged through trusted grading')
    except BaseException as error:
        failure=error
    finally:
        try:closure=retire(engine,item,end)
        except BaseException as error:
            closure={'closed':False,'error_type':type(error).__name__}
            if failure is None:failure=error
        receipt={'schema':'neural022_trusted_grader_execution_v1','resource':item,'closure':closure,
                 'cli_reaped':engine.reaped,'commands':engine.records,'source':source_pin,'submission':prediction_pin,
                 'error_type':None if failure is None else type(failure).__name__,
                 'elapsed_seconds_before_receipt':time.monotonic()-started,
                 'metered_read_bytes':meter.read_bytes,'metered_write_bytes':meter.write_bytes,
                 'cost_excludes':'final receipt, operator Python/library I/O and exact producer RSS',
                 'runtime_qualified':False,'automatic_retry_authorized':False}
        publish(output/'EXECUTION.json',encoded(receipt))
    if failure is not None:raise failure
    need(closure['closed'] is True and engine.reaped and time.monotonic()<end,'Observed removed grader before score acceptance')
    publish(output/'SCORE.json',encoded(result))
    return result
