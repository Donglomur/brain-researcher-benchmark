"""Bounded trusted grading derived from the existing NEURAL087 V2 grade lifecycle."""
import json,math,stat,time,uuid
from bound_io import need,identity,parse,capture,fsync_dir
COMMAND=['-I','-B','/source/trusted_entry.py']
THREADS=('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','OMP_THREAD_LIMIT','MKL_NUM_THREADS','NUMBA_NUM_THREADS','NUMEXPR_NUM_THREADS')
ULIMITS={'cpu':(30,31),'nofile':(1024,1024),'core':(0,0),'fsize':(65536,65536)}
TMPFS={'/tmp':'rw,noexec,nosuid,nodev,size=67108864,mode=1777'}

def grade_user(mounts):
    # Existing private targets may be owner-readable only. Bind the trusted
    # nonroot worker to their actual owner; never chmod or copy target bytes.
    s=mounts['/private/GOLD.json'].lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid>0 and s.st_gid>=0 and bool(s.st_mode & stat.S_IRUSR),'Ordinary owner-readable private target owned by nonroot UID')
    return str(s.st_uid)+':'+str(s.st_gid)

def command(name,mounts,image):
    argv=['create','--pull','never','--name',name,'--network','none','--read-only','--user',grade_user(mounts),
        '--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory',str(512*1024**2),
        '--memory-swap',str(512*1024**2),'--cpus','1','--pids-limit','32','--shm-size','1048576',
        '--restart','no','--init=false','--ipc','private','--no-healthcheck','--log-driver','local','--log-opt','max-size=64k','--log-opt','max-file=1','--log-opt','compress=false','--workdir','/']
    for k,(a,b) in ULIMITS.items():argv+=['--ulimit',f'{k}={a}:{b}']
    for dest,path in mounts.items():argv+=['--mount',f'type=bind,src={path},dst={dest},readonly']
    for k,v in TMPFS.items():argv+=['--tmpfs',k+':'+v]
    for k in THREADS:argv+=['--env',k+'=1']
    return argv+['--env','PYTHONDONTWRITEBYTECODE=1','--entrypoint','python',image,*COMMAND]

def verify(v,name,mounts,image):
    h,c,s=v['HostConfig'],v['Config'],v['State']
    need(v['Name']=='/'+name and v['Image']==c['Image']==image and c['Entrypoint']==['python'] and c['Cmd']==COMMAND,'Exact trusted grade identity/command')
    need(s['Status']=='created' and s['Running'] is False and type(s['Pid']) is int and s['Pid']==0,'Grade inspected before start')
    need(h['NetworkMode']=='none' and h['ReadonlyRootfs'] is True and h['Privileged'] is False and c['User']==grade_user(mounts) and c['WorkingDir']=='/','Offline nonroot readonly grader bound to private-file owner')
    need(h.get('CapDrop')==['ALL'] and not h.get('CapAdd') and 'no-new-privileges:true' in h.get('SecurityOpt',[]) and not h.get('Devices') and not h.get('DeviceRequests') and not h.get('PortBindings') and type(h.get('PidMode'))is str and h['PidMode']=='' and type(h.get('IpcMode'))is str and h['IpcMode']=='private','No additional grader privileges')
    need(set(v.get('NetworkSettings',{}).get('Networks',{}))<={'none'} and h['AutoRemove'] is False and h.get('Init') is False and h['RestartPolicy']['Name'] in ('','no'),'Exact grader lifecycle')
    need(c.get('Healthcheck',{}).get('Test')==['NONE'],'No additional image healthcheck process')
    need(all(type(h[k]) is int for k in ('Memory','MemorySwap','NanoCpus','PidsLimit','ShmSize')) and h['Memory']==h['MemorySwap']==512*1024**2 and h['NanoCpus']==1000000000 and h['PidsLimit']==32 and h['ShmSize']==1048576,'Grade resource limits')
    need(h.get('OomKillDisable') is None or h.get('OomKillDisable') is False,'Do not disable OOM handling')
    need((h.get('Tmpfs') or {})==TMPFS and h['LogConfig']=={'Type':'local','Config':{'max-size':'64k','max-file':'1','compress':'false'}},'Bounded grade scratch/log')
    need(len(h['Ulimits'])==4 and {x['Name']:(x['Soft'],x['Hard']) for x in h['Ulimits']}==ULIMITS,'Grade process limits')
    env=[x.split('=',1) for x in c['Env']];need(len(env)==len({x[0] for x in env}),'Unique grade environment')
    env=dict(env);need(all(env.get(k)=='1' for k in THREADS) and env.get('PYTHONDONTWRITEBYTECODE')=='1','Grade threads/bytecode')
    for label,rows,key in [('daemon',h.get('Mounts',[]),'Target'),('effective',[x for x in v['Mounts'] if x['Type']!='tmpfs'],'Destination')]:
        need(len(rows)==len(mounts) and {x[key] for x in rows}==set(mounts),'Exact grade mount inventory')
        for row in rows:
            expected=str(mounts[row[key]])
            need(row['Type']=='bind' and (row['Source']==expected or (expected.startswith('/Users/') and row['Source']=='/host_mnt'+expected)),'Exact grade source path')
            if label=='effective':need(row['RW'] is False,'Every trusted grade input read only')
            else:need(row.get('ReadOnly') is True,'Every requested grade input read only')
    need(len({x['Destination'] for x in v['Mounts']})==len(v['Mounts']) and all(x['Destination'] in TMPFS and x['RW'] is True for x in v['Mounts'] if x['Type']=='tmpfs'),'No extra grade mounts')

def score_envelope(result):
    fields={'schema','score','matching_fields','required_fields','full_reconstruction','field_checks','effect_sign_is_not_a_pass_criterion'}
    need(type(result)is dict and set(result)==fields and result['schema']=='neural078_numeric_grade_v1','Unchanged original score envelope')
    need(type(result['required_fields'])is int and result['required_fields']==195 and type(result['matching_fields'])is int and 0<=result['matching_fields']<=195,'Complete195 field denominator')
    rows=result['field_checks'];need(type(rows)is list and len(rows)==195 and all(type(x)is dict and set(x)=={'field','matches'} and type(x['field'])is str and type(x['matches'])is bool for x in rows),'Complete typed field results')
    need(len({x['field'] for x in rows})==195 and sum(x['matches'] for x in rows)==result['matching_fields'],'Unique complete field aggregation')
    need(type(result['score'])in(int,float) and math.isfinite(result['score']) and result['score']==result['matching_fields']/195,'Unchanged proportion score')
    need(type(result['full_reconstruction'])is bool and result['full_reconstruction']==(result['matching_fields']==195) and result['effect_sign_is_not_a_pass_criterion'] is True,'Original reconstruction and sign interpretation')
    return result

def run(lib,folder,mounts,budget,outer_end):
    start=time.monotonic();end=min(outer_end-15,start+30)
    need(end-start>=30-0.01,'Full original30second trusted grade phase')
    engine=lib['engine_class'](end,folder,budget);name='neural078-grade-'+uuid.uuid4().hex
    row={'name':name,'grade_worker_seconds':15,'grade_phase_seconds':30,'private_inputs_released':True,'success':False}
    raw=None
    try:
        args=command(name,mounts,lib['contract'].IMAGE);engine.own('container',name,args)
        need(engine.run(args).returncode==0,'Grade create');v=engine.inspect('container',name);verify(v,name,mounts,lib['contract'].IMAGE)
        need(end-time.monotonic()>=23,'Full15second worker and8second cleanup reserve')
        worker_start=time.monotonic();reply=engine.run(['start','--attach',name],timeout=15,cap=65536)
        worker_elapsed=time.monotonic()-worker_start;v=engine.inspect('container',name);state=v['State']
        need(worker_elapsed<=15 and type(reply.returncode)is int and reply.returncode==0 and state['Status']=='exited' and state['Running'] is False and state['Dead'] is False and type(state['Pid'])is int and state['Pid']==0 and type(state['ExitCode'])is int and state['ExitCode']==0 and state['OOMKilled'] is False,'Natural trusted grade zero/noOOM within15s')
        need(reply.stderr==b'' and 0<len(reply.stdout)<=65536,'Exact bounded complete score stdout')
        raw=reply.stdout;row.update(natural_exit=state,worker_elapsed_seconds=worker_elapsed)
    finally:
        engine.end=end;row['cleanup']=engine.cleanup('container',name);row['commands']=engine.commands
        row['elapsed_seconds']=time.monotonic()-start;budget.save(folder/'GRADE_LIFECYCLE.json',row,200000)
    need(row['cleanup']['absence_verified'] is True and raw is not None and time.monotonic()<end,'Removed grader before score admission')
    score_envelope(parse(raw));budget.write(folder/'score.json',raw)
    row.update(success=True,files={'score.json':identity(raw)},elapsed_seconds=time.monotonic()-start)
    need(row['elapsed_seconds']<=30,'Grade phase includes complete score admission')
    marker=folder/'GRADE_COMPLETION.json';published={}
    try:
        budget.save(marker,row,200000,publication=published)
        need(time.monotonic()<end,'Original30second grade phase includes completion publication')
    except BaseException:
        if published and marker.exists():
            saved=marker.lstat()
            if (saved.st_dev,saved.st_ino)==(published['st_dev'],published['st_ino']):
                links=(1,)
                if saved.st_nlink==2:
                    pending=marker.with_name('.'+marker.name+'.pending').lstat()
                    need((pending.st_dev,pending.st_ino)==(saved.st_dev,saved.st_ino),'Own pending grade marker');links=(1,2)
                capture(marker,200000,published,allowed_links=links);marker.unlink();fsync_dir(folder)
        raise
    return row
