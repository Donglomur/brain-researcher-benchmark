"""Owned Docker resources and full native/fit/predict phase; no work on import."""
import base64,hashlib,json,math,os,re,stat,time,uuid
from pathlib import Path
from common import *
from docker_cli import Docker,call
LABEL="org.neurobench.foraging-owner"
HERE=Path(__file__).resolve().parent

def inventory(d,kind,item,end):
    fmt='{{.Name}}' if kind=='volume' else '{{.ID}}';prefix=[kind,'ls']+([] if kind=='volume' else ['--all','--no-trunc'])
    a=call(d,prefix+['--filter','label='+LABEL+'='+item['owner'],'--format',fmt],end,'inventory-owner',8192).decode().splitlines()
    b=call(d,prefix+['--filter','name=^'+('/' if kind=='container' else '')+item['name']+'$','--format',fmt],end,'inventory-name',8192).decode().splitlines()
    need(a==b and len(a)<=1,'exactowned name/label inventory');return a


def inspect(d,item,end):
    v=parse(call(d,[item['kind'],'inspect',item.get('id',item['name'])],end,'inspect',131072));need(type(v)is list and len(v)==1,'exact resourceinspect');v=v[0];need(v['Name']==('/' if item['kind']=='container' else '')+item['name'],'exactresourcename');labels=v.get('Labels') if item['kind']=='volume' else v['Config'].get('Labels');need(labels and labels.get(LABEL)==item['owner'],'exact ownerlabel')
    if item.get('id'):need(v['Id']==item['id'],'exact immutablecontainerID')
    return v


def retire(d,item,end):
    rows=inventory(d,item['kind'],item,end);removed=False
    if item['attempted'] and rows:
        v=inspect(d,item,end)
        if item['kind']=='container' and v['State']['Running']:
            call(d,['container','kill','--signal','KILL',rows[0]],end,'kill-owned',4096);call(d,['container','wait',rows[0]],end,'wait-owned',4096)
        call(d,[item['kind'],'rm',rows[0]],end,'remove-owned',4096);removed=True
    after=inventory(d,item['kind'],item,end);unknown=item['attempted'] and not item['acknowledged'] and not removed
    return {'kind':item['kind'],'name':item['name'],'closed':not after and not unknown,'creation_outcome_unknown':unknown,'absence_observed':not after,'removed':removed}


def mount_args(mounts):
    out=[]
    for dst,(kind,src,rw) in mounts.items():
        need(dst.startswith('/') and not any(c in str(src) for c in ',\n\r\0'),'unambiguous mount');out+=['--mount','type='+kind+',src='+str(src)+',dst='+dst+(',volume-nocopy' if kind=='volume' else '')+('' if rw else ',readonly')]
    return out


def create(d,item,image,cmd,mounts,profile,end,interactive=False,holder=False):
    need(not inventory(d,'container',item,end),'fresh ownednamespace');item['attempted']=True
    args=['container','create','--pull','never','--name',item['name'],'--label',LABEL+'='+item['owner'],'--network','none','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges','--restart','no','--log-driver','none','--cgroupns','private','--ipc','private','--memory',str(profile['memory_bytes']),'--memory-swap',str(profile['memory_bytes']),'--cpus',str(profile['cpus']),'--pids-limit',str(profile['pids']),'--shm-size','16777216','--ulimit','core=0:0','--ulimit','nofile=128:128','--ulimit',f'fsize={profile["file_cap"]}:{profile["file_cap"]}','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size='+str(profile['tmp_bytes'])]
    if interactive:args+=['--interactive']
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):args+=['--env',key+'='+str(profile['threads'])]
    argv=args+mount_args(mounts)+['--entrypoint','python',image,'-I','-B',*cmd]
    cid=call(d,argv,end,'create',4096,20).decode().strip();need(re.fullmatch('[a-f0-9]{64}',cid),'exactcreateID');item.update(id=cid,acknowledged=True);v=inspect(d,item,end);h,c=v['HostConfig'],v['Config']
    need(v['Image']==c['Image']==image and c['Entrypoint']==['python'] and c['Cmd']==['-I','-B',*cmd] and c['User']=='65534:65534','exactimage/command/user')
    need(h['NetworkMode']=='none' and h['ReadonlyRootfs']is True and h['Memory']==h['MemorySwap']==profile['memory_bytes'] and h['NanoCpus']==int(profile['cpus']*1e9) and h['PidsLimit']==profile['pids'],'exact resources/network')
    need(h['CapDrop']==['ALL'] and not h.get('CapAdd') and not h.get('Privileged') and not h.get('Devices') and not h.get('DeviceRequests') and h['CgroupnsMode']=='private' and h['IpcMode']=='private' and h.get('PidMode')in('','private'),'no added capability/device/hostnamespace')
    need('no-new-privileges' in h['SecurityOpt'] and h['RestartPolicy']['Name']=='no' and h['LogConfig']['Type']=='none' and h['AutoRemove']is False and h['ShmSize']==16777216,'fixed lifecycle')
    actual={m['Destination']:(m['Type'],m['Name'] if m['Type']=='volume' else m['Source'],m['RW']) for m in v['Mounts']};need(len(actual)==len(v['Mounts']) and actual=={k:(a,str(b),c) for k,(a,b,c) in mounts.items()},'exact mountinventory');need(all(not rw for kind,src,rw in mounts.values() if kind=='bind'),'no candidatewritable hostbind')
    need(h['Tmpfs']=={'/tmp':'rw,nosuid,nodev,noexec,size='+str(profile['tmp_bytes'])},'bounded scratch')
    need({x['Name']:(x['Soft'],x['Hard']) for x in h['Ulimits']}=={'core':(0,0),'nofile':(128,128),'fsize':(profile['file_cap'],profile['file_cap'])},'exact ulimits')
    need(bool(c['OpenStdin'])==interactive,'exact duplexmode');return cid


def natural_state(v):
    s=v['State'];need(s['Status']=='exited' and s['Running']is False and s['Dead']is False and s['Pid']==0 and s['ExitCode']==0 and s['OOMKilled']is False,'naturallyclosed producer noOOM');return {k:s[k] for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')}


def phase(selection,context,view,program,model,output,budget):
    out=ordinary(output);need(not out.exists(),'fresh phase directory');mkdir_owned(out,budget);kind=context['kind'];name='model.bin' if kind=='fit' else 'result.bin';cap=selection['model_cap_bytes'] if kind=='fit' else context['output_bytes'];need(type(cap)is int and cap>0,'complete phase output extent');start=time.monotonic();work=min(budget.end-selection['cleanup_seconds'],start+selection['phase_seconds'][kind]);end=min(budget.end,work+selection['cleanup_seconds']);need(end>work>start,'original phase and cleanup clocks');profile={**selection['profile'],'file_cap':cap}
    d=Docker(selection['docker']['binary'],selection['docker']['socket'],budget);items=[];closures=[];error=None;resultpin=None;natural=None;producer_closed=False;token='foraging-'+uuid.uuid4().hex
    def item(role,typ):
        row={'name':token+'-'+role,'kind':typ,'owner':token+'/'+role,'attempted':False,'acknowledged':False};write(out/('INTENT-'+role+'.json'),encode(row),budget);items.append(row);return row
    try:
        image=selection['images'][context['role']];v=parse(call(d,['image','inspect',image,'--format','{{json .}}'],work,'image',131072));need(v['Id']==image and not v['Config'].get('Volumes') and (not v['Config'].get('Healthcheck') or v['Config']['Healthcheck'].get('Test')==['NONE']),'exact cached image without implicit volumes or processes')
        mounts={'/input':('bind',ordinary(view),False),'/program.py':('bind',ordinary(program),False),'/bootstrap.py':('bind',HERE/'bootstrap.py',False)}
        if context['role']=='operator':mounts['/runtime']=('bind',HERE,False)
        if kind=='predict':need(model is not None,'sealed fitted state required');mounts['/model/model.bin']=('bind',ordinary(model),False)
        vol=item('volume','volume');need(not inventory(d,'volume',vol,work),'fresh volume name');vol['attempted']=True;options=f'size={cap+1048576},uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev';ack=call(d,['volume','create','--driver','local','--label',LABEL+'='+vol['owner'],'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+options,vol['name']],work,'volume-create',4096).decode().strip();need(ack==vol['name'],'exact volume acknowledgement');vol['acknowledged']=True;v=inspect(d,vol,work);need(v['Driver']=='local' and v['Options']=={'type':'tmpfs','device':'tmpfs','o':options},'quota-backed output volume')
        hold=item('holder','container');hp={'memory_bytes':268435456,'cpus':1,'pids':16,'file_cap':cap,'tmp_bytes':1048576,'threads':1};hm={'/holder.py':('bind',HERE/'holder.py',False),'/capture':('volume',vol['name'],False)};create(d,hold,image,['/holder.py','hold'],hm,hp,work,holder=True);call(d,['container','start',hold['id']],work,'holder-start',4096);need(inspect(d,hold,work)['State']['Running']is True,'holder ready');mounts['/output']=('volume',vol['name'],True)
        producer=item('producer','container');command=['/bootstrap.py',kind,'--input','/input','--case','/input/CASE.json','--output','/output/'+name]
        if kind=='predict':command+=['--model','/model/model.bin']
        create(d,producer,image,command,mounts,profile,work);call(d,['container','start',producer['id']],work,'producer-start',4096);need(d(['container','wait',producer['id']],work,'producer-wait',4096).strip()==b'0','natural producer exit0');natural=natural_state(inspect(d,producer,work));closed=retire(d,producer,work);closures.append(closed);need(closed['closed'],'producer gone before output capture');items.remove(producer);producer_closed=True
        args=['exec',hold['id'],'python','-I','-B','/holder.py'];desc=parse(call(d,args+['describe','--name',name,'--cap',str(cap)],work,'describe-output',4096,30));descriptor(desc);need(0<desc['bytes']<=cap and (kind=='fit' or desc['bytes']==cap),'full opaque output extent');budget.reserve(out,desc['bytes']+8192);budget.writing(desc['bytes']+8192);target=out/name;fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400);h=hashlib.sha256()
        try:
            for offset in range(0,desc['bytes'],1048576):
                size=min(1048576,desc['bytes']-offset);chunk=parse(call(d,args+['chunk','--name',name,'--cap',str(cap),'--offset',str(offset),'--size',str(size)],work,'capture-chunk',1500000,30));body=base64.b64decode(chunk['base64'],validate=True);budget.reading(len(body));need(chunk['identity']==desc['identity'] and chunk['offset']==offset and chunk['bytes']==size and pin(body)==descriptor(chunk),'stable exact output chunk');h.update(body);remaining=memoryview(body)
                while remaining:n=os.write(fd,remaining);need(n>0,'complete capture write');remaining=remaining[n:]
            need(h.hexdigest()==desc['sha256'],'complete output identity');os.fchmod(fd,0o444);os.fsync(fd)
        finally:os.close(fd)
        sync(out);resultpin={'path':str(target),**descriptor(desc)}
    except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)[:512]}
    finally:
        for row in reversed(items):
            try:closures.append(retire(d,row,end))
            except BaseException as exc:closures.append({'kind':row['kind'],'name':row['name'],'closed':False,'error':type(exc).__name__})
    good=error is None and producer_closed and natural is not None and len(closures)==3 and all(x['closed'] for x in closures) and d.reaped and time.monotonic()<end
    receipt={'schema':'foraging_owned_phase_v1','context':context,'status':'captured' if good else 'failed','artifacts':resultpin,'natural_exit':natural,'producer_closed_before_capture':producer_closed,'all_resources_closed':good,'closures':closures,'command_records':d.records,'cli_reaped':d.reaped,'original_work_deadline':budget.end,'phase_work_deadline':work,'phase_cleanup_deadline':end,'started':start,'finished':time.monotonic(),'error':error,'private_scoring_called':False}
    write(out/'PHASE.json',encode(receipt),budget);need(good,'complete owned phase required');return receipt
