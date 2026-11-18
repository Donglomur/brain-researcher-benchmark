"""Exact NEURAL067 train/query candidate profile; no query files or private mounts."""
from pathlib import Path
from .io_guard import need
from .lifecycle import LABEL,SOURCE_LABEL
import mount_policy
IMAGE='sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
ARMS=('neural','clock','neural_clock','shifted_neural_clock')
THREADS=('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','OMP_THREAD_LIMIT','MKL_NUM_THREADS','NUMBA_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS')
TMPFS={'/tmp':'rw,nosuid,nodev,noexec,size=134217728,mode=1777'}

def command(mode,arm):
    need(mode in('train','query')and arm in ARMS,'Fixed mode/arm')
    tail=['train','--arm',arm,'--train','/train/TRAIN.json','--state-stdout']if mode=='train'else['predict','--arm',arm,'--state','/state/STATE.bin','--protocol','neural067_causal_v1']
    return ['-I','-B','/program/program.py',*tail]

def limits(mode):
    return {'core':(0,0),'nofile':(1024,1024),'cpu':(650,652)if mode=='train'else(150,152),'fsize':(134217728,134217728)}

def create_args(name,owner,source,mode,arm,mounts):
    mounts={dst:str(src)for dst,src in mounts.items()}
    wanted={'/program/program.py','/contract/CONTRACT.md','/train'if mode=='train'else'/state/STATE.bin'}
    need(set(mounts)==wanted,'Exact three candidate mounts')
    a=['container','create','--pull','never','--name',name,'--label',LABEL+'='+owner,'--label',SOURCE_LABEL+'='+source,
       '--network','none','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges',
       '--memory','2147483648','--memory-swap','2147483648','--cpus','1','--pids-limit','64','--shm-size','1048576',
       '--cgroupns','private','--ipc','private','--restart','no','--log-driver','none','--workdir','/tmp','--entrypoint','python',
       '--tmpfs','/tmp:'+TMPFS['/tmp'],'-i']
    for key,(soft,hard)in limits(mode).items():a+=['--ulimit',f'{key}={soft}:{hard}']
    for key in THREADS:a+=['--env',key+'=1']
    a+=['--env','PYTHONDONTWRITEBYTECODE=1']
    for dst,src in sorted(mounts.items()):
        need(Path(src).is_absolute()and not any(c in src for c in ',\r\n\0'),'Literal absolute source')
        a+=['--mount','type=bind,src='+src+',dst='+dst+',readonly']
    return a+[IMAGE,*command(mode,arm)]

def verify(info,name,owner,source,mode,arm,mounts,mount_source_policy='identity'):
    mounts={dst:str(src)for dst,src in mounts.items()}
    h,c=info['HostConfig'],info['Config']
    need(info['Name']=='/'+name and info['Image']==c['Image']==IMAGE and c['Labels'].get(LABEL)==owner and c['Labels'].get(SOURCE_LABEL)==source,'Exact candidate image/ownership/source')
    need(h['Memory']==h['MemorySwap']==2147483648 and h['NanoCpus']==1000000000 and h['PidsLimit']==64,'Exact candidate resources')
    need(h['NetworkMode']=='none'and h['ReadonlyRootfs']is True and h['Privileged']is False and h['CapDrop']==['ALL']and not h.get('CapAdd')and h['SecurityOpt']==['no-new-privileges'],'Offline nonprivileged boundary')
    need(h['LogConfig']=={'Type':'none','Config':{}}and h['AutoRemove']is False and h['RestartPolicy']['Name']=='no'and h['ShmSize']==1048576 and h['CgroupnsMode']=='private'and h['IpcMode']=='private','Exact lifecycle/namespace/log boundary')
    need(set(info.get('NetworkSettings',{}).get('Networks',{}))<={'none'},'No effective network attachment')
    need(not h.get('Devices')and not h.get('DeviceRequests')and not h.get('PortBindings')and h.get('PidMode')!='host'and h.get('OomKillDisable')in(None,False),'No devices/ports/host PID')
    need(c['User']=='65534:65534'and c['Cmd']==command(mode,arm)and c['Entrypoint']==['python']and c['WorkingDir']=='/tmp'and c['OpenStdin']is True and c['Tty']is False,'Exact candidate ABI')
    envrows=[x.split('=',1)for x in c['Env']];need(len(envrows)==len({x[0]for x in envrows}),'Unique environment')
    env=dict(envrows);need(all(env.get(k)=='1'for k in THREADS)and env.get('PYTHONDONTWRITEBYTECODE')=='1','One numeric thread/bytecode control')
    need(h['Tmpfs']==TMPFS and len(h['Ulimits'])==4 and {x['Name']:(x['Soft'],x['Hard'])for x in h['Ulimits']}==limits(mode),'Exact scratch and process limits')
    return mount_policy.admit(info,{dst:('bind',str(src),False)for dst,src in mounts.items()},mount_source_policy)
