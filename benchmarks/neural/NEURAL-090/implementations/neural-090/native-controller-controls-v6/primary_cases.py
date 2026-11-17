"""C01–C12: actual source admission/caller/owner boundaries, invented operands."""
import base64, contextlib, copy, hashlib, json, os, stat, sys, types
from pathlib import Path
from harness_core import Proxy, InjectedRead, InjectedClose, InjectedPublication, StopBeforeScience, budget, bare_owner

def _raise(error):raise error
def _asset(ctx,path,body):return ctx.modules['programme.contracts'].Asset(path,ctx.modules['programme.contracts'].Pin(len(body),hashlib.sha256(body).hexdigest()))
def _limits(ctx):
    return {'evaluator':{'read_bytes':2**26,'write_bytes':2**26},'actor':{'read_bytes':2**20,'write_bytes':2**20,'cpu_seconds':2,'wall_seconds':3,'rss_bytes':2**20,'pids':4,'threads':2,'tool_calls':2,'model_tokens':400,'toolset':ctx.selection['TOOLSET.json']}}

def C01(ctx):
    p=ctx.modules['broad090.protocol'];cap=ctx.modules['broad090.capture'];jobs=p.jobs();cases=p.cases()
    ctx.check(len(cases)==384 and len(jobs)==38400,'full384 case/38400 slot inventory')
    ctx.check({c.person for c in cases}==set(map(str,range(1,33)))and {c.query_chapter for c in cases}=={'11','12'},'32 people and both chapters')
    ctx.check(len(p.PHONEMES)==39 and len(set(p.PHONEMES))==39,'39 original phones')
    ctx.check(len(p.full_work_identity(jobs))==38400,'actual full-work identity')
    keys={cap.invocation_key(j,t)for j in jobs for t in cap.TRACKS};ctx.charge('read',sum(len(k)+1 for k in keys))
    ctx.check(len(keys)==76800,'full paired invocations')
    counts={a:sum(j['arm']==a for j in jobs)*2 for a in p.ARMS}
    ctx.check(sum(counts[a]for a in p.PROTECTED)==46080 and sum(counts[a]for a in p.EXPOSED)==30720,'protected/exposed fullcount')
    ctx.check({j['mode']for j in jobs}==set(p.MODES)and {j['seed']for j in jobs}==set(p.SEEDS),'all modes and seeds')
    ctx.reject(lambda:p.full_work_identity(jobs[:-1]),ctx.modules['programme.contracts'].Refusal,'complete38400')

def C02(ctx):
    entry=ctx.modules['n090native.entry'];d=ctx.fixture('bootstrap');rows=[]
    for name in ctx.bodies:
        if '/'not in name and name.endswith('.py'):
            raw=ctx.bodies[name];ctx.put(d/name,(b'!'+raw[1:])if name=='common.py'else raw);rows.append({'path':name,**ctx.selection[name]})
    raw=json.dumps({'files':rows},sort_keys=True).encode();ctx.put(d/'SOURCE_MANIFEST.json',raw)
    ctx.put(d/'common.pyc',b'INERT SAME NAME CACHE SENTINEL; NEVER EXECUTABLE')
    before={k:v for k,v in sys.modules.items()if k.startswith('n090native')}
    fake_sys=Proxy(sys,argv=[str(d/'entry.py'),'run',str(d/'MUST_NOT_READ.json'),'0'*64,hashlib.sha256(raw).hexdigest()])
    with ctx.patch(entry,__file__=str(d/'entry.py'),sys=fake_sys):
        ctx.reject(entry.main,ValueError,'source member pin')
    ctx.check(all(sys.modules[k]is v for k,v in before.items()),'failed bootstrap did not replace any admitted namespace')
    ctx.check(not(d/'MUST_NOT_READ.json').exists(),'changed source refused before request/host access')
    ctx.charge('read',sum(r['bytes']+32 for r in rows)+len(raw))

def C03(ctx):
    entry=ctx.modules['n090native.entry'];common=ctx.modules['n090native.common'];first=InjectedRead('selected read');close=InjectedClose('selected descriptor close');calls=[]
    st=types.SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_nlink=1,st_size=8)
    def read(fd,n):
        calls.append(('read',n))
        if len(calls)==1:return b'abc'
        raise first
    fake=Proxy(os,open=lambda *a,**k:91,fstat=lambda fd:st,read=read,close=lambda fd:_raise(close))
    with ctx.patch(entry,os=fake):e=ctx.reject(lambda:entry.capture('/invented',16),entry.BootstrapFailure,'source bootstrap failed')
    ctx.check(e.first is first and e.secondary==(close,)and e.prefix==b'abc','exact bootstrap original/secondary/prefix')
    class Iterator:
        def __iter__(self):yield types.SimpleNamespace(name='known');raise first
        def close(self):raise close
    with ctx.patch(common,os=Proxy(os,scandir=lambda path:Iterator())):
        names,errors=common.bounded_names('/invented',4,budget(ctx))
    ctx.check(names==['known']and errors.events[0][1]is first and errors.events[1][1]is close,'independent inventory preserves partial known names and raw iteration/close')
    class CloseOnly:
        def __iter__(self):return iter(())
        def close(self):raise close
    with ctx.patch(common,os=Proxy(os,scandir=lambda path:CloseOnly())):_,errors=common.bounded_names('/invented',4,budget(ctx))
    ctx.check(errors.events==[('name-inventory-close',close)],'close-only inventory is failure')
    # Join that actual partial-name carrier to actual recovery, not just its helper.
    import native_cases as fixtures
    controller=ctx.modules['n090native.controller'];root,folder,token,campaign,cg,cfg=fixtures.recovery_fixture(ctx,'C03-partial-inventory');effects=[]
    real_scan=common.os.scandir
    class PartialRoot:
        def __iter__(self):yield types.SimpleNamespace(name=token);raise first
        def close(self):raise close
    def scan(path):return PartialRoot()if Path(path)==root else real_scan(path)
    def docker(self,args,*a,**k):effects.append(tuple(args));return {'stdout_base64':''}
    with fixtures.recovery_patches(ctx,set(),effects,docker,lambda *a:b''),ctx.patch(common,os=Proxy(common.os,scandir=scan)):
        failed=ctx.reject(lambda:controller.recovery(cfg,root,budget(ctx),ctx.work_end),common.Failure,'raw first and secondary retained')
    ctx.check(failed.first is first and failed.events[:2]==(('root:name-inventory',first),('root:name-inventory-close',close)),'actual recovery preserves inventory first and descriptor-close secondary')
    ctx.check(failed.record==[{'token':token,'normal_closed':False}],'only already-captured known intent reaches actual retirement')
    ctx.check(any('label=n090.campaign='+campaign in args for args in effects),'partial inventory does not skip independent final daemon observation')

def C04(ctx):
    op=ctx.modules['broad090.operator'];runtime=ctx.modules['broad090.runtime_source'];owner_mod=ctx.modules['n090native.owner'];common=ctx.modules['n090native.common'];p=ctx.modules['broad090.protocol']
    root=ctx.fixture('programme-selection');program_root=root/'programs';program_root.mkdir();body=b'def next_action(context): return {}\n';ctx.put(program_root/'candidate.py',body)
    o=bare_owner(ctx);o.program_root=program_root;o.runtime=root/'reference';o.runtime_pin=ctx.selection['runtime/RUNTIME_SOURCE.json'];events=[]
    original_admit=o.admit_programs
    def admit(programs,modes,arms):events.append('admit_programs');return original_admit(programs,modes,arms)
    o.admit_programs=admit;o.admit_runtime=lambda *a:events.append('runtime');o.admit_originals=lambda *a:events.append('original_identity')
    def load(*a,**k):events.append('original_load');raise StopBeforeScience('intentional boundary before scientific loading')
    good={m:_asset(ctx,'candidate.py',body)for m in p.MODES};limits=_limits(ctx);rm=_asset(ctx,'RUNTIME_SOURCE.json',b'x')
    with ctx.patch(runtime,prepare_capsule=lambda *a:root/'reference',verify_runtime=lambda *a:None),ctx.patch(op,load_originals=load):
        ctx.reject(lambda:op.run(o,root/'original',{},root/'runtime',rm,{p.MODES[0]:good[p.MODES[0]]},limits,root/'omitted'),ctx.modules['programme.contracts'].Refusal,'both frozen and interactive')
        bad=dict(good);contracts=ctx.modules['programme.contracts'];bad[p.MODES[0]]=contracts.Asset('candidate.py',contracts.Pin(len(body),'0'*64))
        e=ctx.reject(lambda:op.run(o,root/'original',{},root/'runtime',rm,bad,limits,root/'changed'),common.Failure,'actual operation failed')
    ctx.check(type(e.first)is ValueError and 'selected whole content identity'in str(e.first),'changed pin exact source failure')
    ctx.check('original_load'not in events,'candidate source pin checked before original loading')
    # Independent positive admission reaches the deliberately inert original-load leaf.
    o2=bare_owner(ctx);o2.program_root=program_root;o2.admit_runtime=lambda *a:None;o2.admit_originals=lambda *a:None
    with ctx.patch(runtime,prepare_capsule=lambda *a:root/'reference',verify_runtime=lambda *a:None),ctx.patch(op,load_originals=load):
        ctx.reject(lambda:op.run(o2,root/'original',{},root/'runtime',rm,good,limits,root/'valid'),StopBeforeScience,'intentional boundary')
    ctx.check(events.count('original_load')==1 and set(o2.program_paths)==set(p.MODES),'both fixed sources present before one original-load leaf')
    ctx.charge('read',32768);ctx.charge('write',32768)

def _view(ctx):
    vmod=ctx.modules['broad090.views'];root=ctx.fixture('arm-view');roles={}
    for i,(stage,role,_)in enumerate(vmod.ROLES):
        data=b'INERT VALUES '+str(i).encode();timing=b'INERT TIMING '+str(i).encode();a=_asset(ctx,'v'+str(i)+'.txt',data);t=_asset(ctx,'t'+str(i)+'.txt',timing)
        ctx.put(root/a.path,data);ctx.put(root/t.path,timing)
        row={'ids':[hashlib.sha256(str(i).encode()).hexdigest()],'values':{'path':a.path,**a.pin.json()},'timing':{'path':t.path,**t.pin.json()},'shape':[1,1],'count':1}
        if role!='query':row.update(labels=[0],seed_orders={str(s):[0]for s in range(10)})
        roles[stage+'/'+role]=row
    value={'schema':'n090-arm-view-v1','arm':'neural','roles':roles,'vocabulary_sizes':{},'query_labels_present':False,'exposure':'protected','row_identity':'opaque','source_complete':True,'research_qualified':False}
    # Use the exact first protected arm; numerical array leaves remain uncalled.
    value['arm']=ctx.modules['broad090.protocol'].PROTECTED[0]
    raw=ctx.modules['n090native.common'].encoded(value);ctx.put(root/'view.json',raw)
    return root,value,{'path':'view.json',**ctx.modules['n090native.common'].pin(raw)}

def C05(ctx):
    v=ctx.modules['broad090.views'];n=ctx.modules['n090native.native'];c=ctx.modules['programme.contracts'];root,value,asset=_view(ctx)
    v.ArmViews(root,value,None,None);ctx.check(True,'actual arm metadata constructor accepts invented complete roles')
    wrong=copy.deepcopy(value);wrong['roles']['final/query']['labels']=[0]
    ctx.reject(lambda:v.ArmViews(root,wrong,None,None),c.Refusal,'exact fields')
    extra=ctx.put(root/'private-target.txt',b'INERT PRIVATE SENTINEL')
    ctx.reject(lambda:v.ArmViews(root,value,None,None),c.Refusal,'no extra source')
    # A second clean source permits the actual publish pin boundary to be reached.
    root,value,asset=_view(ctx);bad=dict(asset);bad['sha256']='0'*64
    iso=n.Isolation.__new__(n.Isolation);iso.view=None;iso.job={'arm':value['arm']};iso.actor=budget(ctx);iso.root=ctx.fixture('publish');iso.limits={'read_bytes':1048576}
    error=ctx.reject(lambda:iso.publish(root,bad),ctx.modules['n090native.common'].Failure,'actual operation failed')
    ctx.check(type(error.first)is ValueError and 'selected whole content identity'in str(error.first),'publish rejects changed view pin')
    ctx.check(iso.view is None and not(iso.root/'view').exists(),'failed view does not stage or activate')
    root,value,asset=_view(ctx);payload=root/'v4.txt';body=payload.read_bytes();ctx.charge('read',len(body));ctx.charge('write',len(body))
    with payload.open('r+b')as stream:stream.write(b'!'+body[1:])
    staged=n.Isolation.__new__(n.Isolation);staged.view=None;staged.job={'arm':value['arm']};staged.actor=budget(ctx);staged.root=ctx.fixture('payload-publish');staged.limits={'read_bytes':1048576}
    error=ctx.reject(lambda:staged.publish(root,asset),ctx.modules['n090native.common'].Failure,'actual operation failed')
    ctx.check(type(error.first)is ValueError and str(error.first)=='selected whole content identity'and error.record['consumed_prefix'].startswith(b'!'),'actual publish payload loop refuses same-size changed selected member')
    ctx.check(staged.view is None,'partial payload copies never publish an admitted arm view')
    ctx.charge('read',32768)

def C06(ctx):
    n=ctx.modules['n090native.native'];i=n.Isolation.__new__(n.Isolation);root=ctx.fixture('call-identity');a=_asset(ctx,'view.json',b'v');r=_asset(ctx,'RUNTIME_SOURCE.json',b'r')
    i.owner=types.SimpleNamespace(runtime=root/'runtime',runtime_pin=r.pin.json());i.published_root=root/'view';i.view=(root,{'path':a.path,**a.pin.json()},());i.job={'seed':3};i.limits={'selected':1};events=[];i.execute=lambda reference=False:events.append(reference)
    i.run_candidate(i.published_root,a,3,i.limits);i.run_reference('broad090.worker:reference',i.owner.runtime,r,i.published_root,a,3,i.limits)
    ctx.check(events==[False,True],'actual exact candidate/reference caller routes')
    for seed,view,asset,limits in [(4,i.published_root,a,i.limits),(3,root/'other',a,i.limits),(3,i.published_root,_asset(ctx,'other.json',b'v'),i.limits),(3,i.published_root,a,{'selected':2})]:
        ctx.reject(lambda: i.run_candidate(view,asset,seed,limits),ValueError,'exact current candidate call')
    ctx.reject(lambda:i.run_reference('wrong',i.owner.runtime,r,i.published_root,a,3,i.limits),ValueError,'exact existing reference call')
    ctx.reject(lambda:i.run_reference('broad090.worker:reference',root/'other',r,i.published_root,a,3,i.limits),ValueError,'exact existing reference call')
    ctx.reject(lambda:i.run_reference('broad090.worker:reference',i.owner.runtime,_asset(ctx,'RUNTIME_SOURCE.json',b'other'),i.published_root,a,3,i.limits),ValueError,'exact existing reference call')
    ctx.check(events==[False,True],'stale caller arguments never execute')

def C07(ctx):
    cg=ctx.modules['n090native.cgroup'];events=[]
    class KernelPath:
        def __str__(self):return '/sys/fs/cgroup/invented'
        def exists(self):return False
        def mkdir(self):events.append(('mkdir',))
        def stat(self):return types.SimpleNamespace(st_dev=1,st_ino=2)
    def io(self,name,value=None):events.append((name,value));return ''if name=='cgroup.procs'else 'usage_usec 0'
    with ctx.patch(cg,os=Proxy(os,uname=lambda:types.SimpleNamespace(sysname='Linux'))),ctx.patch(cg.Cgroup,io=io):
        for branch in (True,False):
            events.clear();g=cg.Cgroup('/sys/fs/cgroup','invented',budget(ctx),{'rss_bytes':1000,'pids':4,'threads':2});g.path=KernelPath();ctx.check(g.create(branch=branch)is g,'actual cgroup create returns owned instance')
            ctx.check((('cgroup.subtree_control','+cpu +memory +pids')in events)==branch,'branch enables descendants; direct-process leaf does not')
            ctx.check(('pids.max','2')in events and ('memory.swap.max','0')in events,'actual selected cumulative task/memory controls')

def _container(ctx,wrong=None,deadline=False):
    n=ctx.modules['n090native.native'];c=ctx.modules['n090native.common'];i=n.Isolation.__new__(n.Isolation);root=ctx.fixture('container');work=root/'work';work.mkdir();view=root/'view';view.mkdir();launcher=root/'launcher';launcher.mkdir();candidate=root/'candidate';candidate.mkdir()
    i.root=root;i.work=work;i.view=(view,{},());i.closed=False;i.normal_end=10.;i.cleanup_end=20.;i.token='a'*64;i.uid=100001;i.containers=[];i.commands=[];i.budget=budget(ctx);i.errors=c.Ledger();i.job={'mode':'frozen_program'};i.program=object();i.limits=_limits(ctx)['actor'];i.cgroup=types.SimpleNamespace(path=Path('/sys/fs/cgroup/owned'),monitor=lambda:None)
    o=types.SimpleNamespace(cfg={'image_id':'sha256:'+'1'*64,'image_python':'/usr/bin/python3'},campaign='b'*64,image_env={},launcher=launcher,program_paths={'frozen_program':candidate});i.owner=o;state={'stage':'created','calls':[],'clock':1.}
    def inspected():
        stage=state['stage'];mounts=[(str(work),'/work',True),(str(view),'/view',False),(str(launcher),'/launcher',False),(str(candidate),'/candidate',False),(str(root/'tool-request-1'),'/request',False)]
        return {'Image':o.cfg['image_id'],'Config':{'Labels':{'n090.invocation':i.token,'n090.campaign':o.campaign},'Entrypoint':[o.cfg['image_python']],'Cmd':['-I','-S','-B','/launcher/boot.py','/request/LAUNCH.json'],'Env':['HOME=/work','OMP_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2'],'User':str(i.uid)+':'+str(i.uid)},'HostConfig':{'Memory':i.limits['rss_bytes'],'MemorySwap':i.limits['rss_bytes'],'CgroupnsMode':'private','CapAdd':[],'Devices':[],'DeviceRequests':[],'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,'LogConfig':{'Type':'none'},'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges'],'PidMode':'','IpcMode':'private','CgroupParent':'owned','PidsLimit':2},'State':{'Status':stage,'Pid':123 if stage=='running'else 0,'Running':stage=='running','Dead':False,'OOMKilled':False,'ExitCode':0},'Mounts':[{'Source':a,'Destination':b,'RW':rw,'Type':'bind','Propagation':'rprivate'}for a,b,rw in mounts]}
    def docker(args,*a,monitor=None):
        state['calls'].append(args[0])
        if args[0]=='inspect':return {'stdout_base64':base64.b64encode(c.encoded([inspected()])).decode()}
        if args[0]=='start':
            state['stage']='running'
            if deadline:state['clock']=10.
            monitor();state['stage']='exited'
        return {'stdout_base64':'','stderr_base64':'','exit_code':0}
    o.docker=docker
    def kernel(path,*a):
        if str(path).endswith('/cgroup'):return ('0::/'+('foreign'if wrong=='cgroup'else 'owned/child')).encode()
        uid=i.uid+(1 if wrong=='uid'else 0)
        return ('Uid: '+(' '.join([str(uid)]*4))+'\nGid: '+(' '.join([str(i.uid)]*4))+'\nNoNewPrivs: 1\nCapEff: 0\n').encode()
    class ProcPath:
        def __init__(self,p):self.p=Path(p)
        def __truediv__(self,n):return ProcPath(self.p/n)
        def __str__(self):return str(self.p)
        def stat(self):return types.SimpleNamespace(st_ino=1 if str(self.p).startswith('/proc/self/')else 2)
    path=lambda p:ProcPath(p)if str(p).startswith('/proc')else Path(p)
    with ctx.patch(n,Path=path,kernel_body=kernel,time=types.SimpleNamespace(monotonic=lambda:state['clock'])):
        if wrong or deadline:
            reason='bounded descendant cgroup'if wrong=='cgroup'else 'unprivileged actor identity'if wrong=='uid'else 'original activation deadline'
            ctx.reject(lambda:i.container_step(['/invented']),ValueError,reason)
            ctx.check(not(root/'tool-request-1/GO').exists(),'rejected host facts cannot publish GO')
        else:
            i.container_step(['/invented']);ctx.check((root/'tool-request-1/GO').read_bytes()==(i.token+'-1').encode(),'GO follows full actual admission monitor')
            ctx.check(i.containers[0]['removed']and i.containers[0]['activation']['pid']==123,'actual fixed container caller closes after inert zero')
    ctx.charge('read',65536);ctx.charge('write',65536)
    return i,state

def C08(ctx):
    _container(ctx);_container(ctx,'cgroup');_container(ctx,'uid')

def C09(ctx):
    i,state=_container(ctx,deadline=True);ctx.check(i.normal_end==10. and i.cleanup_end==20.,'failed activation does not refresh original endpoints')
    n=ctx.modules['n090native.native']
    for now in (10.,11.):
        with ctx.patch(n,time=types.SimpleNamespace(monotonic=lambda:now)):
            ctx.reject(lambda:i.container_step(['/must-not-dispatch']),ValueError,'live current isolation')
    ctx.check(state['calls'].count('create')==1,'equal/past endpoint adds no new native dispatch')

def C10(ctx):
    p=ctx.modules['n090native.process'];first=FileNotFoundError('selected disappearing stat');secondary=InjectedClose('selected proc directory close');events=[]
    class Scan:
        def __iter__(self):return iter([types.SimpleNamespace(name='999')])
        def close(self):events.append('iterator-close')
    def opened(path,*a,**k):
        if path=='/proc':return 10
        if path=='999':return 11
        if path=='stat':raise first
        raise AssertionError('unexpected proc open')
    def closed(fd):
        events.append(('close',fd))
        if fd==11:raise secondary
    fake=Proxy(os,open=opened,close=closed,scandir=lambda fd:Scan())
    group=p._PinnedGroup(types.SimpleNamespace(pid=123));group.terminal=0
    with ctx.patch(p,os=fake,time=types.SimpleNamespace(monotonic=lambda:1.)):
        error=ctx.reject(lambda:group.other_members(2.),FileNotFoundError,'selected disappearing stat')
    ctx.check(error is first and group.errors==[secondary]and group.evidence()['proc_descriptor_closure_known']is False,'actual complete helper retains original and unknown closure')
    ctx.check('iterator-close'in events and ('close',10)in events,'independent iterator/root retirement attempted')
    # Actual final consumer receives this exact group error list, with inert wait/stream/kernel leaves.
    original=group.other_members
    class Stream:
        def __init__(self,n):self.n=n
        def fileno(self):return self.n
        def close(self):pass
    child=types.SimpleNamespace(pid=123,stdout=Stream(1),stderr=Stream(2),returncode=None)
    class Selector:
        def __init__(self):self.items={}
        def register(self,s,e,n):self.items[s.n]=types.SimpleNamespace(fileobj=s,data=n)
        def get_map(self):return self.items
        def select(self,t):return [(v,1)for v in list(self.items.values())]
        def unregister(self,s):self.items.pop(s.n,None)
        def close(self):pass
    group=p._PinnedGroup(child);group.terminal=0
    # Keep actual other_members/_stat_body for the first failing traversal.
    group.observe=lambda *a,**k:0;group.send=lambda *a,**k:None
    def reap(*a):group.reaped=True;group.signals_retired=True;child.returncode=0;return 0
    group.reap=reap;group.absent_after_reap=lambda:True
    with ctx.patch(p,os=Proxy(fake,set_blocking=lambda *a:None,read=lambda *a:b''),signal=Proxy(p.signal,setitimer=lambda *a:(0.,0.)),time=types.SimpleNamespace(monotonic=lambda:1.,sleep=lambda x:None),_pinned_platform=lambda f:f(p.PROC_READ_CAP),_PinnedGroup=lambda proc:group,subprocess=Proxy(p.subprocess,Popen=lambda *a,**k:child),selectors=Proxy(p.selectors,DefaultSelector=Selector)):
        error=ctx.reject(lambda:p._run_owned(['/inert'],normal_end=2.,cleanup_end=3.,env={},metadata_read=lambda n:None),p.ChildFailure,'selected trusted child')
    ctx.check(error.original_error is first and any(raw is secondary for where,raw in error.secondary),'actual command consumer preserves helper failure and raw close secondary')
    ctx.check(error.record['primary_error']is not None,'unknown descriptor closure cannot become success')

def C11(ctx):
    o=bare_owner(ctx);m=ctx.modules['n090native.owner'];p=ctx.modules['n090native.process'];c=ctx.modules['n090native.common'];publication=InjectedPublication('selected fsync publication');record={'stdout_base64':base64.b64encode(b'original stdout').decode(),'stderr_base64':base64.b64encode(b'original stderr').decode()};names=[]
    def save(path,*a):names.append(path.name);raise publication
    with ctx.patch(m,time=types.SimpleNamespace(monotonic=lambda:1.),save=save),ctx.patch(p,_run_owned=lambda *a,**k:record):
        e=ctx.reject(lambda:o.command(['/inert'],10.,20.,budget(ctx)),c.Failure,'actual operation failed')
    ctx.check(e.first is publication and e.record['result']is record and o.command_records[0][0]['result']is record,'completed original command retained before failed publication')
    ctx.check(e.record['result']['stdout_base64']==record['stdout_base64']and e.record['result']['stderr_base64']==record['stderr_base64'],'both exact raw streams retained')
    numbers=[];depth=[0]
    def run(*a,**k):
        if depth[0]==0:
            depth[0]=1;o.command(['/nested'],10.,20.,budget(ctx))
        return record
    with ctx.patch(m,time=types.SimpleNamespace(monotonic=lambda:1.),save=lambda path,*a:numbers.append(path.name)),ctx.patch(p,_run_owned=run):o.command(['/outer'],10.,20.,budget(ctx))
    ctx.check(numbers==['command-3.json','command-2.json'],'nested monitor commands have distinct reserved numbers')

def C12(ctx):
    # Actual isolation constructor catches partially created cgroup and calls real close.
    n=ctx.modules['n090native.native'];c=ctx.modules['n090native.common'];first=InjectedRead('selected mount creation failure');events=[];root=ctx.fixture('partial-isolation')
    class Group:
        def __init__(self,*a):self.closed=False;self.identity=(1,2)
        def create(self):events.append('group-create');return self
        def kill(self):events.append('group-kill')
        def finish(self):events.append('group-finish');self.closed=True;return {}
    owner=types.SimpleNamespace(root=root,campaign='b'*64,cfg={'uid_base':100000,'cleanup_seconds':10,'isolation_read_bytes':1048576,'isolation_write_bytes':1048576,'isolation_cleanup_read_bytes':1048576,'isolation_cleanup_write_bytes':1048576,'cgroup_root':'/sys/fs/cgroup/invented','work_bytes':65536,'work_inodes':32,'mount':{'path':'/inert/mount'}},work_end=10.,end=20.,invocation=lambda j,t:'invented-invocation',command=lambda *a,**k:_raise(first))
    old_clocks=(n.time,c.time);clock=types.SimpleNamespace(monotonic=lambda:1.)
    with ctx.patch(n,Cgroup=Group,time=clock,Broker=lambda i:object()),ctx.patch(c,time=clock):
        error=ctx.reject(lambda:n.Isolation(owner,{'mode':'frozen_program'},'candidate',None,_limits(ctx)['actor'],0),c.Failure,'actual operation failed')
    ctx.check(n.time is old_clocks[0]and c.time is old_clocks[1],'both production clock bindings restored after C12')
    ctx.check(error.first is first and events==['group-create','group-kill','group-finish'],'partial isolation preserves original and retires created group')
    ctx.check(not any(p.name=='CLOSED.json'for p in root.rglob('CLOSED.json')),'partial failed native owner cannot issue closure')
    # Partial controller cgroup recovery is covered again through invoke in C24.

def run(ctx):
    for number in range(1,13):ctx.case('C'+str(number).zfill(2),lambda n=number:globals()['C'+str(n).zfill(2)](ctx))
