"""Concrete fixed native stage/candidate/collector phases; shared repaired CLI."""
import os,re,time,types,uuid,signal
from pathlib import Path
from common import need,path,capture,decode,encode,short,write,syncdir,inventory,before,FILES,KEYS,PRED,VIEW,PHASE,FLOOR,MIB

class PhaseWriter:
    def __init__(self,root,other,end,cap=PHASE):self.root=path(root);self.other=other;self.end=end;self.cap=cap;self.pending=None;self.written=0
    def check(self,n=0):
        before(self.end);used=inventory(self.root,100)[2];need(used+n+65536<=self.cap,'phase allocation');fs=os.statvfs(self.root.parent);need(fs.f_bavail*fs.f_frsize>=FLOOR+self.other+max(0,self.cap-used),'phase remaining floor');need(self.written+n<=self.cap,'phase write cap')
    def mkdir(self,p,mode=0o700):
        self.check(65536);p=path(p);need(p==self.root or self.root in p.parents,'owned phase directory');p.mkdir(mode=mode);self.written+=65536;syncdir(p.parent)
    def bytes(self,p,b,cap):
        self.check(len(b));p=path(p);need(self.root in p.parents,'owned phase file');self.written+=len(b);return write(p,b,cap)
    def json(self,p,d,cap=131072):return self.bytes(p,encode(d),cap)

def stage_binding(view,key,tick):
    view=path(view);files,dirs,used=inventory(view,8);need(set(files)==FILES and dirs==[view]and used<=VIEW+65536,'exact one-context view')
    raw,cp=capture(view/'COMPLETE.json',65536,tick=tick);d=decode(raw);need(d['schema']=='neural076_prepared_v1'and set(d['files'])==FILES-{'COMPLETE.json'},'complete staging manifest')
    allpins={**d['files'],'COMPLETE.json':cp}
    for name,p in allpins.items():capture(view/name,VIEW,p,body=False,tick=tick)
    raw,_=capture(view/'context.json',65536,allpins['context.json'],tick=tick);ctx=decode(raw)
    need(ctx=={'schema':'neural076_matched_hierarchy_v1','key':key,'source_design_sha256':'56ff1e67bb824b9ad6ab9005db82a11349581bb634a0725f4a1cca81019a6026','max_selected_voxels':316},'exact fixed context')
    return {'key':key,'files':allpins,'allocated_bytes':used}

def seal_view(view,binding,tick):
    for name in binding['files']:
        tick();p=Path(view)/name;fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        try:os.fchmod(fd,0o444);os.fsync(fd)
        finally:os.close(fd)
    Path(view).chmod(0o555);syncdir(view);syncdir(Path(view).parent)
    need(stage_binding(view,binding['key'],tick)['files']==binding['files'],'sealed exact view')

def trusted_admission(r,v,item,mounts,args,image,file_cap):
    r.owned(v,item,item['owner']);h=v['HostConfig'];c=v['Config'];uid=f'{os.getuid()}:{os.getgid()}'
    need(v['Image']==c['Image']==image and c['User']==uid and c['Entrypoint']==['python']and c['Cmd']==args,'trusted image command user')
    need(h['Memory']==h['MemorySwap']==4*2**30 and h['NanoCpus']==10**9 and h['PidsLimit']==64,'trusted resources')
    need(h['NetworkMode']=='none'and h['ReadonlyRootfs']is True and h['CgroupnsMode']=='private'and h['IpcMode']=='none'and h['LogConfig']['Type']=='none','trusted isolation')
    need(h.get('Privileged')is False and not h.get('CapAdd')and not h.get('Devices')and not h.get('DeviceRequests')and h.get('PidMode')in('','private'),'trusted no extra privilege')
    need(h['CapDrop']==['ALL']and'no-new-privileges'in h['SecurityOpt']and h['RestartPolicy']['Name']=='no'and h['AutoRemove']is False,'trusted no restart')
    actual={x['Destination']:(x['Type'],x['Source'],x['RW'])for x in v['Mounts']};need(len(v['Mounts'])==len(mounts)and actual=={str(p):('bind',str(p),rw)for p,rw in mounts.items()},'exact trusted mounts')
    need(h.get('Tmpfs')=={'/tmp':'rw,nosuid,nodev,noexec,size=16777216'}and{x['Name']:(x['Soft'],x['Hard'])for x in h['Ulimits']}=={'core':(0,0),'nofile':(128,128),'fsize':(file_cap,file_cap)},'trusted scratch/file caps')

def native_trusted(mode,key,s,source,here,folder,output,r,end,w):
    # Only this fixed worker can receive protected collection access.
    work=end-45;need(mode in('stage','collect')and os.getuid()>0,'fixed trusted phase');result=folder/'TRUSTED_RESULT.json';name='neural076-'+uuid.uuid4().hex[:24]+'-trusted';item={'kind':'container','name':name,'owner':name,'attempted':False,'acknowledged':False};d=r.Docker(s['docker_binary'],path(s['docker_socket']))
    mounts={here:False,path(s['collection']):False,folder:True}
    mounts[path(output).parent if mode=='stage'else path(output)]=mode=='stage'
    seconds=max(1,int(work-time.monotonic()-15));args=['-I','-B',str(here/'trusted.py'),'--source-sha256',source['sha256'],'--mode',mode,'--collection',s['collection'],'--output',str(output),'--result',str(result),'--seconds',str(seconds)]
    if key is not None:args+=['--key',key]
    file_cap=VIEW if mode=='stage'else 262144
    w.json(folder/'NATIVE_INTENT.json',{'mode':mode,'key':key,'resource':item,'result':str(result),'automatic_retry':False})
    error=None;natural=None;closure=None
    try:
        image=r.parse(r.call(d,['image','inspect',s['image'],'--format','{{json .}}'],work,'image',131072));need(image['Id']==s['image']and not image['Config'].get('Volumes')and(not image['Config'].get('Healthcheck')or image['Config']['Healthcheck'].get('Test')==['NONE']),'trusted existing image')
        need(r.resource_inventory(d,item,name,work,'precreate')==[],'fresh native name')
        cmd=['container','create','--pull','never','--name',name,'--label',r.LABEL+'='+name,'--cpus','1','--memory',str(4*2**30),'--memory-swap',str(4*2**30),'--pids-limit','64','--network','none','--cgroupns','private','--ipc','none','--read-only','--user',f'{os.getuid()}:{os.getgid()}','--cap-drop','ALL','--security-opt','no-new-privileges','--restart','no','--log-driver','none','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=16777216','--ulimit','core=0:0','--ulimit','nofile=128:128','--ulimit',f'fsize={file_cap}:{file_cap}']
        for p,rw in mounts.items():cmd+=['--mount','type=bind,src='+str(p)+',dst='+str(p)+(''if rw else',readonly')]
        for k in('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):cmd+=['--env',k+'=1']
        cmd+=['--entrypoint','python',s['image'],*args];item['attempted']=True
        ident=r.call(d,cmd,work,'create_trusted',4096,12).decode('ascii').strip();need(re.fullmatch('[a-f0-9]{64}',ident),'native identity');item.update(id=ident,acknowledged=True)
        trusted_admission(r,r.inspect(d,'container',ident,work,'admit'),item,mounts,args,s['image'],file_cap)
        r.call(d,['container','start',ident],work,'start',4096)
        reply=d(['container','wait',ident],work,'wait',4096);v=r.inspect(d,'container',ident,work,'exit');r.owned(v,item,name);natural={k:v['State'][k]for k in('Status','Running','Dead','Pid','ExitCode','OOMKilled')};need(reply.strip()==b'0'and natural=={'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False},'natural native zero')
    except BaseException as exc:error=type(exc).__name__
    finally:
        try:closure=r.retire(d,item,end)
        except BaseException as exc:error=error or type(exc).__name__
    report={'mode':mode,'key':key,'source':source,'natural':natural,'closure':closure,'cli_reaped':d.reaped,'commands':d.records,'error':error,'scientific_scoring':False};w.json(folder/'NATIVE_CLOSURE.json',report,262144)
    need(error is None and natural is not None and closure and closure['closed']and closure.get('removed')and d.reaped,'closed trusted native phase');before(end)
    raw,p=capture(result,262144,tick=lambda:before(end));return decode(raw),p

def main(args,loader,bodies,manifest,source):
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--source-sha256',required=True);a.add_argument('--request',required=True);a.add_argument('--request-sha256',required=True);v=a.parse_args(args)
    raw,_=capture(v.request,131072);need(short(raw)['sha256']==v.request_sha256,'root phase request');q=decode(raw)
    need(set(q)=={'schema','source','selection','mode','key','folder','view','end','other','commit'}and q['schema']=='neural076_owned_phase_request_v1'and q['source']==source,'fixed phase source');s=q['selection'];end=q['end'];before(end);loader('coordinator').validate_selection(s,source,bodies);need(end-time.monotonic()>40,'owned cleanup reserve');signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('original owned-phase work deadline')));signal.setitimer(signal.ITIMER_REAL,end-time.monotonic()-30)
    need(q['mode']in('stage','candidate','collect')and(q['key']in KEYS if q['mode']!='collect'else q['key']is None),'complete context mode')
    root=path(s['output']);commit_raw,_=capture(root/'program/COMMIT.json',131072,q['commit']);commit_doc=decode(commit_raw);need(commit_doc=={'schema':'neural076_frozen_program_v1','source':source,'program':{k:s['program'][k]for k in('bytes','sha256')},'keys':list(KEYS),'image':s['image'],'candidate_seconds':s['candidate_seconds'],'memory_bytes':s['memory_bytes'],'procedural_review':s['program_review'],'runtime_qualification':s['runtime_qualification'],'condition':'full650_feature_recovery','feedback_before_commitment':False},'exact all-phase commitment before any query access');folder=path(q['folder']);need(folder.parent==root/'phases'and not folder.exists(),'fresh owned phase');need(path(q['view'])==(root/'submission'if q['mode']=='collect'else root/'current'/q['key'].replace('/','__')),'fixed root-owned phase view');need(type(q['other'])is int and q['other']>=s['other_future_bytes'],'fixed phase reservation');here=Path(__file__).absolute().parent;r=loader('runtime');r.IMAGE=s['image'];w=PhaseWriter(folder,q['other'],end,PHASE if q['mode']=='candidate'else 2*MIB);w.mkdir(folder)
    if q['mode']in('stage','collect'):
        result,p=native_trusted(q['mode'],q['key'],s,source,here,folder,path(q['view']),r,end,w)
        if q['mode']=='stage':
            need(result['schema']=='neural076_trusted_stage_v1'and result['key']==q['key']and result['source']==source,'same trusted stage');binding=stage_binding(q['view'],q['key'],lambda:before(end));seal_view(q['view'],binding,lambda:before(end));result={'key':q['key'],'binding':binding,'trusted_result':p}
        else:need(result['schema']=='neural076_complete_public_validation_v1'and result['source']==source and result['gold_opened']is False and result['scientific_scoring']is False,'same public-only collector')
    else:
        commit=q['commit'];program_dir=root/'program';raw,_=capture(program_dir/'COMMIT.json',262144,commit);c=decode(raw)
        need(c['source']==source and c['image']==s['image']and c['keys']==list(KEYS),'frozen whole-cohort commitment');program,_=capture(program_dir/'program.py',131072,c['program']);view=path(q['view']);binding=stage_binding(view,q['key'],lambda:before(end));need(all((view/n).stat().st_mode&0o004 for n in FILES)and view.stat().st_mode&0o005==0o005,'readable sealed candidate view')
        snap=folder/'snapshot';w.mkdir(snap,0o755)
        for n,b in [('program.py',program),('entry.py',bodies['entry.py']),('holder.py',bodies['holder.py'])]:w.bytes(snap/n,b,131072)
        snap.chmod(0o555);syncdir(snap);life=loader('lifecycle');e=types.SimpleNamespace(r=r);d=r.Docker(s['docker_binary'],path(s['docker_socket']));cfg={'program':c['program'],'condition':'full650_feature_recovery','candidate_seconds':s['candidate_seconds'],'memory_bytes':s['memory_bytes']}
        x=life.case_lifecycle(e,d,snap,cfg,view,folder,folder,w,min(end-45,time.monotonic()+s['candidate_seconds']+420));w.json(folder/'EXECUTION.json',x,262144);life.lifecycle_closed(x)
        need(stage_binding(view,q['key'],lambda:before(end))==binding,'input immutability');need(w.pending is not None and short(w.pending)==x['score']['predictions.npz'],'closed opaque capture')
        pred=w.bytes(folder/'predictions.npz',w.pending,PRED);w.pending=None;result={'key':q['key'],'program':c['program'],'commit':commit,'input':binding,'prediction':pred,'all_resources_closed':True,'producer_removed_before_capture':True,'public_numerical_validation':False}
    before(end);p=w.json(folder/'COMPLETE.json',{'schema':'neural076_phase_complete_v1','mode':q['mode'],'source':source,'key':q['key'],'result':result,'private_gold_opened':False,'scientific_scoring':False},262144);before(end)
    signal.setitimer(signal.ITIMER_REAL,0);before(end);print(encode({'completion':p,'folder':str(folder)}).decode(),end='',flush=True);return 0
