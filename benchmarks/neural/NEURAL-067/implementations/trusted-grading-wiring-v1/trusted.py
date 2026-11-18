"""Fixed NEURAL067 preparation/assembly/grading role; no candidate imports."""
import os,re,time,uuid
from runtime_io import need
from runtime import lifecycle as life
import mount_policy

IMAGE='sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
THREADS=('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','OMP_THREAD_LIMIT','MKL_NUM_THREADS','NUMBA_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS')

def checked(info,ident,name,owner,mounts,command,policy='identity'):
    life.ownership(info,ident,name,owner);h,c=info['HostConfig'],info['Config']
    need(info['Image']==IMAGE and c['Cmd']==command and c['Entrypoint']==['python']
         and c['User']==str(os.getuid())+':'+str(os.getgid()) and os.getuid()>0,'fixed unprivileged worker')
    need(h['Memory']==h['MemorySwap']==2147483648 and h['NanoCpus']==1000000000
        and h['PidsLimit']==64 and h['NetworkMode']=='none' and h['ReadonlyRootfs'] is True
        and h['Privileged'] is False and h['LogConfig']['Type']=='none' and h['CapDrop']==['ALL']
        and 'no-new-privileges' in h['SecurityOpt'] and h['CgroupnsMode']=='private'
        and h['IpcMode']=='none' and h['Tmpfs']=={'/tmp':'rw,nosuid,nodev,noexec,size=16777216'},'trusted role limits')
    expected={d:('bind',str(s),not ro) for s,d,ro in mounts}
    need(len(expected)==len(mounts),'unique trusted mount targets')
    admission=mount_policy.admit(info,expected,policy)
    env=[x.split('=',1) for x in c['Env']]
    need(len(env)==len({k for k,v in env}) and all(dict(env).get(k)=='1' for k in THREADS),'all numerical thread limits')
    return admission

def run(command,mounts,phase,budget,config,seconds=120):
    need(seconds==120,'fixed trusted work ceiling');now=time.monotonic();end=now+140
    need(end<budget.end-10,'full trusted work+cleanup reserve')
    name='neural067-trusted-'+uuid.uuid4().hex;owner=uuid.uuid4().hex
    args=['container','create','--pull','never','--name',name,'--label',life.LABEL+'='+owner,
        '--network','none','--read-only','--user',str(os.getuid())+':'+str(os.getgid()),'--cpus','1',
        '--memory','2g','--memory-swap','2g','--pids-limit','64','--cgroupns','private','--ipc','none',
        '--cap-drop','ALL','--security-opt','no-new-privileges','--log-driver','none',
        '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=16777216','--env','PYTHONDONTWRITEBYTECODE=1']
    for key in THREADS:args+=['--env',key+'=1']
    for src,dst,ro in mounts:
        need(not any(c in str(src) for c in ',\n\r\0'),'unambiguous mount')
        args+=['--mount','type=bind,src='+str(src)+',dst='+dst+(',readonly' if ro else '')]
    args+=['--entrypoint','python',IMAGE,*command]
    budget.save(phase/'INTENT.json',{'name':name,'owner':owner,'argv':args,'mounts':[(str(s),d,r) for s,d,r in mounts]})
    docker=life.Docker(config['binary'],config['env'],config['check_socket'],budget)
    ident=None;attempted=False;failure=None;state=None;clean=None;created_mounts=finished_mounts=None
    try:
        attempted=True;raw=docker(args,min(end,time.monotonic()+5),'create',4096).decode().strip()
        need(re.fullmatch('[a-f0-9]{64}',raw),'acknowledged immutable worker ID');ident=raw
        created_mounts=checked(life.inspected(docker,ident,min(end,time.monotonic()+5),'created'),ident,name,owner,mounts,command,config['mount_source_policy'])
        budget.save(phase/'CREATED.json',{'identifier':ident,'name':name,'owner':owner,'profile_checked_before_start':True})
        active=time.monotonic();need(end-active>=130,'full120 work plus closure')
        docker(['container','start',ident],min(end,active+5),'start',4096)
        response=docker(['container','wait',ident],min(end-10,active+120),'wait',4096)
        need(response.strip()==b'0','natural trusted worker zero')
        info=life.inspected(docker,ident,min(end-5,time.monotonic()+5),'finished')
        finished_mounts=checked(info,ident,name,owner,mounts,command,config['mount_source_policy']);state=life.natural_exit(info)
    except BaseException as e:failure=type(e).__name__
    finally:
        try:
            clean=life.cleanup(docker,ident,name,owner,end)
            if attempted and ident is None and not clean.get('removed'):
                clean.update(owned_absence_confirmed=False,creation_outcome_unknown=True)
        except BaseException as e:clean={'owned_absence_confirmed':False,'error_type':type(e).__name__}
    result={'error_type':failure,'natural_state':state,'cleanup':clean,'create_attempted':attempted,
        'create_acknowledged':ident is not None,'commands':docker.records,
        'role_deadline_met':time.monotonic()<end,'elapsed_seconds':time.monotonic()-now,
        'created_mount_admission':created_mounts,'finished_mount_admission':finished_mounts}
    pin=budget.save(phase/'HOST.json',result)
    need(failure is None and state and clean['owned_absence_confirmed'] and not clean.get('forced_stop')
        and result['role_deadline_met'] and time.monotonic()<end,'natural closed trusted worker')
    return pin
