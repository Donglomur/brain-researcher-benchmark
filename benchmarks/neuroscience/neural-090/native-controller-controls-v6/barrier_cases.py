"""C21–C24 full metadata barriers and real enclosing caller, no scientific values."""
import contextlib, hashlib, json, os, signal, stat, sys, types
from pathlib import Path
from harness_core import Proxy, InjectedRead, InjectedClose, InjectedPublication, budget, bare_owner
from primary_cases import _limits, _asset, _raise

class MemoryFiles:
    """Inert byte-level descriptors below the actual ordinary capture consumer."""
    def __init__(self,ctx,root,raw,mapped,audit,receipt):
        self.ctx=ctx;self.root=root;self.role={'raw':raw,'mapped':mapped,'audit':audit,'native':receipt};self.published={};self.handles={};self.next=100;self.bad=None;self.counts={k:0 for k in self.role};self.open_count=self.close_count=0
    def body(self,path):
        s=str(path);name=Path(s).name
        if s in self.published:return self.published[s]
        if name.startswith('native-'):role='native'
        elif name.startswith('audit-'):role='audit'
        elif name.startswith('mapped-'):role='mapped'
        else:role='raw'
        self.counts[role]+=1
        raw=self.role[role]
        return (b'!'+raw[1:])if s==self.bad else raw
    def stat(self,body):return types.SimpleNamespace(st_mode=stat.S_IFREG|0o400,st_nlink=1,st_size=len(body),st_dev=1,st_ino=2,st_uid=0,st_gid=0,st_mtime_ns=1,st_ctime_ns=1)
    def path(self,p):
        parent=self
        class Ordinary:
            def __str__(self):return str(p)
            def lstat(self):
                # Same bytes/stamp without incrementing consumer-open counts.
                old=dict(parent.counts);raw=parent.body(p);parent.counts=old;return parent.stat(raw)
        return Ordinary()
    def open(self,p,*a):
        raw=self.body(p);self.next+=1;self.handles[self.next]=[raw,0];self.open_count+=1;return self.next
    def read(self,fd,n):
        raw,pos=self.handles[fd];out=raw[pos:pos+n];self.handles[fd][1]+=len(out);self.ctx.charge('read',len(out));return out
    def fstat(self,fd):return self.stat(self.handles[fd][0])
    def close(self,fd):self.handles.pop(fd);self.close_count+=1
    def write(self,path,body,account,ledger):
        if len(body)>40*1048576:raise AssertionError('selected full-set serialization bound')
        self.ctx.charge('write',len(body));account.charge('write',len(body));self.published={str(path):body}
        return self.ctx.modules['programme.contracts'].Pin(len(body),hashlib.sha256(body).hexdigest())

def _book(ctx,protected_only):
    cap=ctx.modules['broad090.capture'];cust=ctx.modules['broad090.custody'];p=ctx.modules['broad090.protocol'];common=ctx.modules['n090native.common']
    o=bare_owner(ctx);root=ctx.fixture('capturebook');book=cap.CaptureBook(root/'book',cust.Accounting(2**30,2**30),cust.Ledger(),o)
    raw=b'INERT RAW';mapped=b'{}';receipt=b'INERT NATIVE';receipt_pin=common.pin(receipt);audit=common.encoded({'native_resources':{'path':'native-invented.json',**receipt_pin}})
    pins={k:ctx.modules['programme.contracts'].Pin(len(v),hashlib.sha256(v).hexdigest())for k,v in [('asset',raw),('mapped',mapped),('private_audit',audit)]}
    jobs=p.jobs();selected=[j for j in jobs if not protected_only or j['arm']in p.PROTECTED]
    records={};sealed={}
    for j in selected:
        for track in cap.TRACKS:
            key=cap.invocation_key(j,track);name=hashlib.sha256(key.encode()).hexdigest()+'.json'
            records[key]={role:ctx.modules['programme.contracts'].Asset(prefix+name,pins[role])for role,prefix in [('asset',''),('mapped','mapped-'),('private_audit','audit-')]}
            sealed[key]={'path':str(book.root/name),'pin':pins['asset'].json()}
    book.records=records;o.sealed=sealed;o.expected=book.expected;o.protected_expected={cap.invocation_key(j,t)for j in jobs if j['arm']in p.PROTECTED for t in cap.TRACKS}
    o.keys={};o.invocation=cap.invocation_key;o.limits=_limits(ctx);o.programs={m:_asset(ctx,'candidate.py',b'x')for m in p.MODES}
    fs=MemoryFiles(ctx,book.root,raw,mapped,audit,receipt)
    ctx.charge('read',sum(len(k)+1 for k in records))
    return book,o,fs,jobs

@contextlib.contextmanager
def _memory_capture(ctx,fs):
    common=ctx.modules['n090native.common'];owner=ctx.modules['n090native.owner'];cap=ctx.modules['broad090.capture']
    with ctx.patch(common,regular_path=fs.path,os=Proxy(os,open=fs.open,read=fs.read,fstat=fs.fstat,close=fs.close)),ctx.patch(owner,os=Proxy(os,chmod=lambda *a:None)),ctx.patch(cap,write_fresh=fs.write):yield

def C21(ctx):
    cap=ctx.modules['broad090.capture'];contracts=ctx.modules['programme.contracts'];owner=ctx.modules['n090native.owner'];p=ctx.modules['broad090.protocol']
    book,o,fs,jobs=_book(ctx,True);ctx.check(len(book.records)==46080,'all protected track/mode/seed/case keys')
    first=next(iter(book.records));saved=book.records.pop(first)
    ctx.reject(book.protected_release,contracts.Refusal,'every protected arm')
    book.records[first]=saved
    # Wrong invocation list/stale raw-seal set are refused before any content access.
    wrong=tuple(sorted(o.protected_expected))[:-1]
    ctx.reject(lambda:o.seal_protected_set('/inert',saved['asset'].pin,wrong),ValueError,'all46080')
    with _memory_capture(ctx,fs):release=book.protected_release()
    ctx.check(o.protected and book.seal is not None and release.scope_id=='whole-broad-programme','actual full protected-set release after all role/native joins')
    ctx.check(fs.counts=={'raw':46080,'mapped':46080,'audit':46080,'native':46080}and fs.open_count==fs.close_count and not fs.handles,'complete protected raw/mapped/audit/native pin joins and descriptor closure')
    ctx.reject(book.protected_release,contracts.Refusal,'one immutable global diagnostic release')
    protected_job=next(j for j in jobs if j['arm']in p.PROTECTED);duplicate=cap.invocation_key(protected_job,'candidate');book.attempted.add(duplicate)
    ctx.reject(lambda:book.capture(protected_job,'candidate','/never-read',None,{},{}),contracts.Refusal,'fixed one-shot invocation')
    # Actual new_isolation exposure gate, with only the native constructor inert.
    job=next(j for j in jobs if j['arm']in p.EXPOSED);key=cap.invocation_key(job,'candidate');o.expected={key:job};o.keys={};o.isolations=[];o.protected=False;calls=[]
    with ctx.patch(owner,Isolation=lambda *a:calls.append(a)or object()):
        ctx.reject(lambda:o.new_isolation(job,'candidate',o.programs[job['mode']],o.limits['actor']),ValueError,'protected global set')
        ctx.check(calls==[],'no exposed construction before full protected seal')
        o.protected=True;o.new_isolation(job,'candidate',o.programs[job['mode']],o.limits['actor']);ctx.check(len(calls)==1,'same actual exposure gate after seal')

def C22(ctx):
    cap=ctx.modules['broad090.capture'];contracts=ctx.modules['programme.contracts'];common=ctx.modules['n090native.common']
    book,o,fs,jobs=_book(ctx,False);o.protected=True;book.seal=_asset(ctx,'protected.json',b'protected').pin
    ctx.check(len(book.records)==76800 and len(book.expected)==76800,'entire paired programme record/expected roster')
    last=sorted(book.records)[-1];saved=book.records.pop(last)
    ctx.reject(book.finish,contracts.Refusal,'all76800');ctx.reject(lambda:book.targets({}),contracts.Refusal,'target scoring only after complete')
    book.records[last]=saved;fs.bad=str(book.root/saved['private_audit'].path)
    with _memory_capture(ctx,fs):
        error=ctx.reject(book.finish,common.Failure,'actual operation failed')
    ctx.check(type(error.first)is ValueError and 'selected whole content identity'in str(error.first),'actual late changed audit pin refusal')
    ctx.check(not book.completed and not o.completed,'late invalid full set cannot release targets')
    ctx.reject(lambda:book.targets({}),contracts.Refusal,'target scoring only after complete')
    ctx.reject(book.finish,contracts.Refusal,'one complete-set sealing attempt')
    ctx.check(fs.counts['raw']==76800 and fs.counts['mapped']==76800 and fs.counts['audit']==76800 and fs.counts['native']==76799,'late refusal occurred after complete full-prefix joins')
    # Fresh one-shot consumer object, same immutable complete source metadata; no retry.
    positive=cap.CaptureBook.__new__(cap.CaptureBook);positive.__dict__=dict(book.__dict__);positive.finish_attempted=False;positive.completed=False
    o2=bare_owner(ctx);o2.protected=True;o2.expected=book.expected;o2.sealed=o.sealed;positive.native_owner=o2;fs.bad=None;fs.counts={k:0 for k in fs.counts}
    with _memory_capture(ctx,fs):pin=positive.finish()
    ctx.check(positive.completed and o2.completed and pin.bytes>0,'fresh actual complete set seals all76800 before target access')
    positive.supports={('invented','11'):frozenset({'invented-target'})}
    ctx.check(positive.targets({'invented-target':0})=={'invented-target':0},'only complete sealed source allows invented target handoff; no scoring leaf')
    ctx.check(fs.counts=={'raw':76800,'mapped':76800,'audit':76800,'native':76800}and fs.open_count==fs.close_count,'full positive role/native closure')

def config(ctx,root):
    cfg=json.loads(ctx.bodies['REQUEST.template.json']);cfg['limits']=_limits(ctx)
    for k in ('original_root','program_root','output_root'):cfg[k]=str(root/k)
    n=cfg['native']
    for k in ('campaign_seconds','cleanup_seconds','controller_read_bytes','controller_write_bytes','isolation_cleanup_read_bytes','isolation_cleanup_write_bytes','isolation_read_bytes','isolation_write_bytes','recovery_read_bytes','recovery_write_bytes','work_bytes','work_inodes','proc_metadata_bytes'):n[k]=2**26
    n['campaign_seconds']=10;n['cleanup_seconds']=6;n['uid_base']=100000;n['host_site_packages']=[]
    n['parent_custody_root']=str(root/'parent');n['custody_root']=str(root/'native');n['cgroup_root']='/sys/fs/cgroup/invented'
    n['controller_native']={'rss_bytes':1048576,'pids':2,'threads':2,'cpu_seconds':5}
    for k in ('docker','mount','umount'):n[k]={'path':str(root/k),'bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}
    n['provider']={'model':'inert','credential':{},'input_tokens':100,'output_tokens':100,'request_bytes':1024,'response_bytes':1024,'max_calls':2,'input_contract':{}}
    n['proc_metadata_bytes']=262144
    cfg['programs']={m:{'path':'candidate.py',**_asset(ctx,'candidate.py',b'x').pin.json()}for m in ctx.modules['broad090.protocol'].MODES}
    cfg['source_operands']={k:{'path':k+'.json',**_asset(ctx,k+'.json',b'x').pin.json()}for k in cfg['source_operands']}
    return cfg

def C23(ctx):
    c=ctx.modules['n090native.controller'];op=ctx.modules['broad090.operator'];common=ctx.modules['n090native.common'];root=ctx.fixture('child-failure');cfg=config(ctx,root)
    first=InjectedRead('selected original programme');alarm=InjectedClose('selected alarm disable');close=InjectedClose('selected owner close');term=InjectedClose('selected term restore');alrm=InjectedClose('selected alarm restore');events=[];handlers={};calls=[0]
    class Owner:
        def __init__(self,*a):events.append('owner-create')
        def close(self):events.append('owner-close');raise close
    def handler(sig,value):
        if sig not in handlers:handlers[sig]=value;return 'original-'+str(sig)
        events.append('restore-'+str(sig));raise term if sig==signal.SIGTERM else alrm
    def timer(which,value,*a):
        calls[0]+=1;events.append('timer-'+str(value))
        if value==0:raise alarm
        return(0.,0.)
    with ctx.patch(c,runtime=lambda *a:root,NativeOwner=Owner,capture=lambda *a:b'{}',signal=Proxy(signal,signal=handler,setitimer=timer),time=types.SimpleNamespace(monotonic=lambda:1.)),ctx.patch(op,run=lambda *a:_raise(first)):
        error=ctx.reject(lambda:c.run_child(cfg,ctx.source,ctx.selection,(0.,10.,16.)),common.Failure,'actual operation failed')
    ctx.check(error.first is first and [e for _,e in error.events]==[first,alarm,close,term,alrm],'original error plus every ordered raw cleanup occurrence')
    ctx.check(calls[0]==2 and events[-3:]==['owner-close','restore-'+str(signal.SIGTERM),'restore-'+str(signal.SIGALRM)],'all independent final cleanup and restorations attempted')

def C24(ctx):
    c=ctx.modules['n090native.controller'];common=ctx.modules['n090native.common'];p=ctx.modules['n090native.process'];proofs=[]
    modes=('positive','nonzero','unknown','partial-create','close-error','short-roster','recovery-only','late-publication')
    for mode in modes:
        root=ctx.fixture('invoke-'+mode);cfg=config(ctx,root);Path(cfg['output_root']).mkdir();ctx.put(Path(cfg['output_root'])/'point-report.json',b'{"invented_report":true}\n')
        clock=[1.];events=[];published=[];native_first=InjectedRead('selected '+mode);groups=[]
        class Group:
            def __init__(self,parent,name,b,limits):self.path=Path(parent)/name;self.identity=None;self.budget=b;groups.append(self)
            def create(self,branch):
                ctx.check(branch is False,'actual controller is direct-process leaf');self.identity=(1,2);events.append('create')
                if mode=='partial-create':raise native_first
            def monitor(self):pass
            def kill(self):events.append('kill')
            def finish(self):
                events.append('finish')
                if mode=='close-error':raise native_first
                return {}
        def run(argv,**kw):
            b=kw['metadata_read'].__self__
            ctx.check(b.reads>=8193+cfg['native']['proc_metadata_bytes']+262145 and b.writes>=16384+32+524290,'invoke reserves placement and command reads/writes before dispatch')
            ctx.check('--'in argv and 'trusted-place.py'in argv[4]and kw['cleanup_end']<17.,'actual captured placement argv and original partial cleanup reserve')
            if mode in ('nonzero','unknown'):
                raise p.ChildFailure({'exit_code':1 if mode=='nonzero'else None,'stdout_base64':'','stderr_base64':'','process_reaped':mode=='nonzero'},native_first)
            placement=Path(argv[8]);value={'schema':'n090-actual-placement-v1','pid':4321,'cgroup':str(groups[0].path),'identity':[1,2],'moved':True,'readback':'0::/'+str(groups[0].path.relative_to('/sys/fs/cgroup')),'descriptor_closure_known':True,'first':None,'secondary':[],'kernel_prefix_base64':''}
            ctx.put(placement,common.encoded(value))
            return {'pid':4321,'exit_code':0,'natural_exit':True,'process_reaped':True,'process_group_absent':True,'stdout_eof':True,'stderr_eof':True,'stdout_base64':'','stderr_base64':'','primary_error':None,'cleanup_errors':[]}
        def recovery(*a):
            events.append('recovery');n=76799 if mode=='short-roster'else 76800
            # Complete roster retained as metadata; all native effects are inert.
            return {'root_absent':False,'intents':[{'token':str(i),'normal_closed':mode!='recovery-only'}for i in range(n)]}
        original_save=c.save
        def save(path,body,b,mode_=0o400):
            if path.name in ('ENCLOSED_SUPPORT.json','FAILED.json'):
                ctx.charge('write',len(body));b.write(len(body));published.append((path.name,common.pin(body)))
                if mode=='late-publication'and path.name=='ENCLOSED_SUPPORT.json':clock[0]=17.
                return common.pin(body)
            ctx.charge('write',len(body));return original_save(path,body,b,mode_)
        fake_time=types.SimpleNamespace(monotonic=lambda:clock[0])
        with ctx.patch(c,Cgroup=Group,recovery=recovery,save=save,time=fake_time,os=Proxy(os,geteuid=lambda:0),sys=Proxy(sys,platform='linux')),ctx.patch(common,time=fake_time),ctx.patch(p,_run_owned=run):
            invoke=lambda:c.invoke(cfg,ctx.source,ctx.selection,root/'request.json',common.pin(b'{}'),{'bytes':7199,'sha256':'4cec25d6083a51a43e50e65318ac598be5e2a32ac74cd07a3eb8647c4304e8d8'})
            if mode=='positive':
                result=invoke();ctx.check(len(result['retirement']['intents'])==76800 and result['point_report']==common.pin(b'{"invented_report":true}\n'),'actual complete enclosing support binds whole roster and point-report')
            elif mode in ('nonzero','unknown','partial-create','close-error'):
                error=ctx.reject(invoke,common.Failure,'actual operation failed')
                if mode in ('nonzero','unknown'):ctx.check(type(error.first)is p.ChildFailure and error.first.original_error is native_first,'original child failure carrier remains exact')
                else:ctx.check(error.first is native_first,'original partial/retirement error remains exact')
            elif mode in ('short-roster','recovery-only'):ctx.reject(invoke,ValueError,'complete natural full campaign')
            else:ctx.reject(invoke,ValueError,'original operation deadline')
        ctx.check(events[-3:]==['kill','finish','recovery'],'actual enclosing finally attempts all independent retirement')
        if mode not in ('positive','late-publication'):ctx.check(not any(n=='ENCLOSED_SUPPORT.json'for n,pin in published),'no support after child/closure/whole-roster failure')
        if mode=='late-publication':ctx.check(any(n=='ENCLOSED_SUPPORT.json'for n,pin in published),'late publication is failure even after support-shaped bytes')
        proofs.append({'mode':mode,'events':events,'published':[n for n,_ in published]})
    ctx.check(len(proofs)==8,'all selected enclosing caller branches')

def run(ctx):
    for number in range(21,25):ctx.case('C'+str(number),lambda n=number:globals()['C'+str(n)](ctx))
