"""Single shared profile-aware export of qualified095 exact resource/mount guards."""
IMAGE='sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
THREADS=('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','OMP_THREAD_LIMIT','MKL_NUM_THREADS','NUMBA_NUM_THREADS','NUMEXPR_NUM_THREADS')
VOLUME_BYTES=40*1024*1024
VOLUME_OPTIONS=f'size={VOLUME_BYTES},nr_inodes=32,uid=65534,gid=65534,mode=0700,noexec,nosuid,nodev'
LIMITS={'holder':{'memory':256*1024*1024,'cpus':250000000,'pids':16},'candidate':{'memory':3*1024**3,'cpus':1750000000,'pids':64}}
TMPFS={'/tmp':'rw,noexec,nosuid,nodev,size=67108864,mode=1777'}

def require(ok,message):
    if not ok:raise ValueError(message)

def source_matches(actual,expected,kind):return actual==expected or(kind=='bind'and expected.startswith('/Users/')and actual=='/host_mnt'+expected)

def canonical(role,mounts,profile):
    wanted={'/trusted/holder.py','/capture'}if role=='holder'else{'/program/program.py','/output',*profile['public_destinations']}
    require(role in LIMITS and set(mounts)==wanted,'Exact role mount destinations')
    for dest,row in mounts.items():
        require(set(row)=={'type','source','rw'}and row['type']in('bind','volume')and type(row['rw'])is bool and type(row['source'])is str,'Explicit canonical mount request')
        require(not any(x in row['source']for x in(',','\n','\r')),'Safe mount encoding')
        is_output=dest in('/capture','/output')
        require(row['type']==('volume'if is_output else'bind')and row['rw']==(dest=='/output'),'Exact source kind/mode')
        if not is_output:require(row['source'].startswith('/')and not row['source'].startswith('/host_mnt/'),'Canonical absolute host bind path')
    return True

def command(role,profile):return ['-I','/trusted/holder.py','hold','--output-name',profile['output_name'],'--max-output-bytes',str(profile['max_output_bytes'])]if role=='holder'else['-I','/program/program.py','--input','/input','--out','/output']

def verify(info,name,role,mounts,profile):
    canonical(role,mounts,profile);h,c,s=info['HostConfig'],info['Config'],info['State'];lim=LIMITS[role]
    require(info['Name']=='/'+name and info['Image']==c['Image']==IMAGE and c['Entrypoint']==['python']and c['Cmd']==command(role,profile),'Exact image/name/entrypoint')
    require(c['WorkingDir']==('/'if role=='holder'else'/output'),'Exact worker directory')
    require(s['Status']=='created'and s['Running']is False and s['Pid']==0,'Inspect before startup')
    require(h['NetworkMode']=='none'and h['ReadonlyRootfs']is True and h['Privileged']is False and c['User']=='65534:65534','Offline nonroot readonly isolation')
    require(h.get('CapDrop')==['ALL']and not h.get('CapAdd')and 'no-new-privileges:true'in h.get('SecurityOpt',[])and not h.get('Devices')and not h.get('DeviceRequests')and not h.get('PortBindings')and h.get('PidMode')!='host'and h.get('IpcMode')!='host','No capabilities/devices/host namespaces')
    require(set(info.get('NetworkSettings',{}).get('Networks',{}))<={'none'}and not h['AutoRemove']and h['RestartPolicy']['Name']in('','no'),'Exact network/lifecycle')
    require(h['Memory']==h['MemorySwap']==lim['memory']and h['NanoCpus']==lim['cpus']and h['PidsLimit']==lim['pids'],'Exact role resource limits')
    wanted_tmp=TMPFS if role=='candidate'else{}
    require((h.get('Tmpfs')or{})==wanted_tmp,'Exact scratch mounts')
    require(h['LogConfig']=={'Type':'local','Config':{'max-size':'64k','max-file':'1','compress':'false'}},'Bounded log retention')
    require(len(h['Ulimits'])==4 and {x['Name']:(x['Soft'],x['Hard'])for x in h['Ulimits']}=={'cpu':(20,22),'nofile':(1024,1024),'core':(0,0),'fsize':(33554432,33554432)},'Exact ulimits')
    env=[x.split('=',1)for x in c['Env']];require(len(env)==len({x[0]for x in env}),'Unique environment keys');env=dict(env)
    require(all(env.get(x)=='2'for x in THREADS)and env.get('PYTHONDONTWRITEBYTECODE')=='1','Thread/bytecode controls')
    for label,rows,key in [('daemon',h.get('Mounts',[]),'Target'),('effective',[x for x in info['Mounts']if x['Type']!='tmpfs'],'Destination')]:
        require(len(rows)==len(mounts)and len({x[key]for x in rows})==len(rows)and {x[key]for x in rows}==set(mounts),'Exact inspected mount inventory')
        for row in rows:
            expected=mounts[row[key]];kind=expected['type'];require(row['Type']==kind,'Exact mount type')
            actual=row.get('Name')if label=='effective'and kind=='volume'else row['Source']
            require(source_matches(actual,expected['source'],kind),'Exact canonical or documented Docker path alias only')
            if label=='daemon':
                readonly=row.get('ReadOnly',False);require(type(readonly)is bool and readonly is(not expected['rw']),'Exact daemon mount mode')
            else:require(row['RW']is expected['rw'],'Exact effective mount mode')
            if label=='daemon'and kind=='volume':require(row.get('VolumeOptions',{}).get('NoCopy')is True,'No volume copyup')
    require(len({x['Destination']for x in info['Mounts']})==len(info['Mounts'])and all(x['Destination']in wanted_tmp and x['RW']for x in info['Mounts']if x['Type']=='tmpfs'),'No extra effective mount')
    return {'status':'exact_boundary_verified','role':role,'mounts':len(mounts)}
