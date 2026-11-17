"""N074 exact eleven captured operator checks; engineering fixtures only.

This launcher is inactive until root separately selects its frozen invocation.
Task modules and their tests are not modified. Only the selected test module's
tempfile binding is replaced by an explicitly retained-fixture adapter.
"""
import argparse
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import stat
import sys
import sysconfig
import time
import types
import unittest

MIB = 1048576
SITE = sysconfig.get_path('purelib')
NUMPY = SITE + '/numpy'
METHODS = (
 'test_actual_submission_commit_and_separate_evaluation',
 'test_late_candidate_disposition_rejected_before_target',
 'test_changed_native_prediction_cannot_be_recommitted',
 'test_failed_candidate_keeps_complete_roster_and_no_targets',
 'test_unclosed_owner_preserves_exact_failure_evidence',
 'test_wrong_training_selection_refused_before_workspace_creation',
 'test_changed_budget_cannot_keep_the_same_policy_identity',
 'test_overlapping_workspace_refused_before_mutation',
 'test_changed_target_pin_rejected_at_owner_admission',
 'test_reused_context_is_not_a_new_fold',
 'test_late_reference_file_tamper_has_zero_target_calls',
)
CONTROL_MODULE = 'n074_operator_boundary_controls'
MODULES = [{"bytes":11318,"module":"n074.programme","package":False,"path":"source/n074/programme.py","sha256":"8d7f550c78e46e4e13d01222a10232b6ceacb3e1385550bbf575406ab37ea6a7"},{"bytes":7286,"module":"n074.contracts","package":False,"path":"source/n074/contracts.py","sha256":"db2e3c2414710a2d318b9b951ea62e744c72c3b8bca9b2e21213a065257fbaac"},{"bytes":14543,"module":"n074.evaluation","package":False,"path":"source/n074/evaluation.py","sha256":"78d0c280b10e3cdb51c2ac83568322e37b057ea15055f2fa0120c54d19398bb4"},{"bytes":2844,"module":"n074.maps","package":False,"path":"source/n074/maps.py","sha256":"c7badf3f068efff174b60b2fcceddeaee4094ee9f648c607a1de61530966d8dd"},{"bytes":4033,"module":"n074.catalogue","package":False,"path":"source/n074/catalogue.py","sha256":"d68aae541c26aeaa08b2038ec21e7cf8e70c43b4504bffc5accdadc80d0e1409"},{"bytes":3933,"module":"n074.splits","package":False,"path":"source/n074/splits.py","sha256":"01ce33309c2203afdee5c38ae9735b378450a1016a0e5a04c878d8f444901c99"},{"bytes":1882,"module":"n074.models","package":False,"path":"source/n074/models.py","sha256":"f74a7a6d5d13d9cbff913180b5bfc657c4d20fe9563ad426bb52acfd23d98f17"},{"bytes":2233,"module":"n074.semantics","package":False,"path":"source/n074/semantics.py","sha256":"8678d4e7d4a41f1720582d0b8aafb86a4744300c7362390b584bc0a391c06435"},{"bytes":3177,"module":"n074.components","package":False,"path":"source/n074/components.py","sha256":"690f0d9ce28322499440834c88e7cd1f13a9e47f087cc54ecb41d0abdd52508f"},{"bytes":2027,"module":"n074.linear","package":False,"path":"source/n074/linear.py","sha256":"0c180f55b266a3221bff932c9be7963f1c2325b17ea2e0ba2c9f96d9be580f54"},{"bytes":1917,"module":"n074.metrics","package":False,"path":"source/n074/metrics.py","sha256":"42dfb59bdde8804187d0b09840240da560b62087b767ef42bbe2e337e22f9363"},{"bytes":83,"module":"n074","package":True,"path":"source/n074/__init__.py","sha256":"15e8a35b10542e7c0e8cfb2ec7e4e12087c4088c05478e40e29f19d4ea212f18"},{"bytes":243,"module":"n074_operator","package":True,"path":"source/n074_operator/__init__.py","sha256":"742997ed0ed990d6266ce407c8890d022fb1b0f3ddbba5c9e08a481c25ef0886"},{"bytes":11231,"module":"n074_operator.owned_io","package":False,"path":"source/n074_operator/owned_io.py","sha256":"43e3a7bada246e2dc26083e39cad34388b41bebb209e0867db8d4c53274ac0fa"},{"bytes":8708,"module":"n074_operator.selection","package":False,"path":"source/n074_operator/selection.py","sha256":"80229542a856b2f703c37ece8a070091ebc6f04f90fd013b48e0f562e3637757"},{"bytes":3692,"module":"n074_operator.host_contract","package":False,"path":"source/n074_operator/host_contract.py","sha256":"3111a924273f4308324b884be2f0035f1362e3e66ca407900f81b634017c5378"},{"bytes":17260,"module":"n074_operator.candidate","package":False,"path":"source/n074_operator/candidate.py","sha256":"03081805af04af726c4e9d24f7ca8f41c9abf3d2646ee613247ee0c249755d26"},{"bytes":13411,"module":"n074_operator.panel","package":False,"path":"source/n074_operator/panel.py","sha256":"36359e94e53c5c368a8ce9a365f26b2874185943a0cd3c2582f2c144fe5b9e5a"},{"bytes":14557,"module":"n074_operator.packet","package":False,"path":"source/n074_operator/packet.py","sha256":"b9a154c89041592f6633c66ce5751f75a280143e82852a381af2e15b973c1cd1"},{"bytes":17172,"module":"n074_operator_boundary_controls","package":False,"path":"controls/test_operator_boundary.py","sha256":"1d8a1c35cffaff004cb052b33f360be6a34cb44328adaaaf6271e5cfc7ea6463"}]

def need(ok, reason):
    if not ok:
        raise ValueError(reason)

def pin(raw):
    return {'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}

def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()

def stamp(s):
    return (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def ordinary(path):
    p = Path(path)
    need(p.is_absolute() and str(p)==str(path), 'absolute canonical path')
    need(not any(q.is_symlink() for q in (p,*p.parents)), 'ordinary path ancestry')
    return p

def describe(exc, seen=None, depth=0):
    seen = set() if seen is None else seen
    if id(exc) in seen or depth >= 16:
        return {'incomplete':True,'reason':'repeated object or bounded chain'}
    seen.add(id(exc))
    try:
        message = str(exc)
    except BaseException as secondary:
        message = '<message unavailable: '+type(secondary).__name__+'>'
    row={'module':type(exc).__module__,'type':type(exc).__name__,
         'message':message[:4096],'message_truncated':len(message)>4096}
    for name in ('first','original','__cause__'):
        value=getattr(exc,name,None)
        if isinstance(value,BaseException):
            row[name]=describe(value,seen,depth+1)
    for name in ('secondary','supervisor_cleanup_errors','launcher_cleanup_errors'):
        values=getattr(exc,name,())
        if type(values) in (tuple,list):
            row[name]=[describe(v,seen,depth+1) for v in values[:16] if isinstance(v,BaseException)]
            if len(values)>16: row[name+'_incomplete']=True
    return row

class Custody:
    def __init__(self, origin, deadline):
        need(type(origin) is float and type(deadline) is float and
             math.isfinite(origin) and math.isfinite(deadline) and
             deadline == origin + 175., 'original selected child clock')
        self.origin,self.deadline=origin,deadline
        self.first=None; self.original_errors=[]; self.events=[]
        self.read_reserved=0; self.read_observed=0
        self.write_reserved=0; self.write_observed=0
        self.census_entries=0; self.io_records=[]
    def check(self):
        need(time.monotonic()<self.deadline,'original whole-suite wall horizon')
        u=resource.getrusage(resource.RUSAGE_SELF)
        need(u.ru_utime+u.ru_stime<155.,'original full-process CPU ceiling')
    def fail(self,stage,exc):
        if self.first is None: self.first=exc
        self.original_errors.append(exc)
        self.events.append({'stage':stage,'error':describe(exc)})
    def reserve_read(self,n):
        self.check()
        need(type(n) is int and 0<=n<=64*MIB-self.read_reserved,'launcher cumulative read cap')
        self.read_reserved+=n
    def reserve_write(self,n):
        self.check()
        need(type(n) is int and 0<=n<=4*MIB-self.write_reserved,'launcher cumulative write cap')
        self.write_reserved+=n
    def capture(self,path,row):
        self.reserve_read(row['bytes']+1)
        need(type(row['bytes']) is int and 0<=row['bytes']<=2*MIB,'bounded ordinary source member')
        p=ordinary(path); rec={'operation':'capture','path':str(p),'complete':False,
                             'observed_bytes':0,'sha256_prefix':hashlib.sha256(b'').hexdigest()}
        self.io_records.append(rec)
        fd=None; first=None; later=[]; body=None; h=hashlib.sha256()
        try:
            before=os.lstat(p)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==row['bytes'],
                 'exact single-link source extent')
            fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            need(stamp(os.fstat(fd))==stamp(before),'opened source identity')
            pieces=[]; left=row['bytes']+1
            while left:
                self.check(); part=os.read(fd,min(65536,left))
                self.read_observed+=len(part); rec['observed_bytes']+=len(part);h.update(part)
                rec['sha256_prefix']=h.hexdigest()
                if not part: break
                pieces.append(part);left-=len(part)
            body=b''.join(pieces)
            need(stamp(os.fstat(fd))==stamp(before)==stamp(os.lstat(p)),'stable captured source')
            need(pin(body)=={k:row[k] for k in ('bytes','sha256')},'exact source content')
            self.check()
        except BaseException as exc: first=exc
        if fd is not None:
            closing,fd=fd,None
            try: os.close(closing)
            except BaseException as exc: later.append(exc)
        try: self.check()
        except BaseException as exc: later.append(exc)
        if first is not None or later:
            first=first if first is not None else later.pop(0)
            first.launcher_cleanup_errors=tuple(later)
            rec['error']=describe(first)
            raise first
        rec['complete']=True
        return body
    def publish(self,path,body):
        self.reserve_write(len(body))
        p=ordinary(path);rec={'operation':'publication','path':str(p),'complete':False,
                              'observed_bytes':0,**pin(body)}
        self.io_records.append(rec)
        fd=None;first=None;later=[]
        try:
            fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            off=0
            while off<len(body):
                self.check();n=os.write(fd,memoryview(body)[off:off+65536])
                need(type(n) is int and 0<n<=len(body)-off,'actual publication progress')
                off+=n;self.write_observed+=n;rec['observed_bytes']=off
            self.check();os.fsync(fd)
        except BaseException as exc:first=exc
        if fd is not None:
            closing,fd=fd,None
            try:os.close(closing)
            except BaseException as exc:later.append(exc)
        try:self.check()
        except BaseException as exc:later.append(exc)
        if first is not None or later:
            first=first if first is not None else later.pop(0)
            first.launcher_cleanup_errors=tuple(later);rec['error']=describe(first)
            raise first
        rec['complete']=True
        return {'path':str(p),**pin(body)}
    def observation(self):
        u=resource.getrusage(resource.RUSAGE_SELF)
        return {'origin':self.origin,'deadline':self.deadline,
                'read_reserved':self.read_reserved,'read_observed':self.read_observed,
                'write_reserved':self.write_reserved,'write_observed':self.write_observed,
                'census_entries':self.census_entries,
                'full_process_cpu_seconds':u.ru_utime+u.ru_stime,
                'observed_maxrss_bytes':u.ru_maxrss*1024,'observed_maxrss_raw_unit':'KiB on selected Linux','hard_RSS_bound':False,
                'managed_scope':'launcher captures, final fixture hashes and launcher publications only',
                'task_IO_scope':'unchanged operation Budgets plus source-derived whole-suite reservation',
                'io_records':self.io_records,'events':self.events}

class Captured(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,rows,bodies):
        self.rows={r['module']:r for r in rows};self.bodies=bodies;self.loaded=[]
    def find_spec(self,fullname,path=None,target=None):
        protected=(fullname in ('n074','n074_operator',CONTROL_MODULE) or
                   fullname.startswith(('n074.','n074_operator.')))
        if not protected:return None
        need(fullname in self.rows,'unselected task import: '+fullname)
        r=self.rows[fullname]
        spec=importlib.util.spec_from_loader(fullname,self,is_package=r['package'])
        spec.origin=r['path']
        if r['package']:spec.submodule_search_locations=[]
        return spec
    def create_module(self,spec):return None
    def exec_module(self,module):
        r=self.rows[module.__name__];module.__file__=r['path']
        module.__package__=module.__name__ if r['package'] else module.__name__.rpartition('.')[0]
        if r['package']:module.__path__=[]
        exec(compile(self.bodies[module.__name__],r['path'],'exec',dont_inherit=True),module.__dict__)
        self.loaded.append(module.__name__)

class Retained:
    def __init__(self,root,custody):
        self.root=ordinary(root);self.custody=custody;self.records=[];self.counter=0
        self.root.mkdir(mode=0o700);os.chmod(self.root,0o700)
        self.identity=stamp(os.lstat(self.root))[:3]
    def mkdtemp(self,suffix='',prefix='tmp',dir=None):
        self.custody.check()
        need(type(suffix) is str and type(prefix) is str and
             all('/' not in x and '\x00' not in x and len(x)<=128 for x in (suffix,prefix)),
             'finite tempfile spelling')
        parent=self.root if dir is None else ordinary(dir)
        need(parent==self.root or self.root in parent.parents,'fixture parent outside retained root')
        need(stamp(os.lstat(self.root))[:3]==self.identity,'retained root identity changed')
        need(parent.is_dir() and self.counter<12,'exact twelve tempfile-created directories cap')
        self.counter+=1;path=parent/(prefix+('%04d'%self.counter)+suffix)
        row={'path':str(path),'state':'attempted','cleanup_requests':0}
        self.records.append(row)
        path.mkdir(mode=0o700);os.chmod(path,0o700)
        row['state']='created';row['identity']=list(stamp(os.lstat(path))[:3])
        return str(path)
    def temporary(self,suffix='',prefix='tmp',dir=None,**kwargs):
        need(not kwargs,'no unselected TemporaryDirectory arguments')
        name=self.mkdtemp(suffix,prefix,dir);row=self.records[-1]
        class Kept:
            def __init__(self):self.name=name
            def cleanup(self):
                row['cleanup_requests']+=1
                row['cleanup_semantics']='retained; no deletion or finalizer'
            def __enter__(self):return self.name
            def __exit__(self,*exc):self.cleanup()
        return Kept()
    def namespace(self):
        return types.SimpleNamespace(TemporaryDirectory=self.temporary,mkdtemp=self.mkdtemp)

def census(root,custody,hash_files):
    """Bounded no-follow observation; failures retain actual known prefixes only."""
    result={'complete':False,'hash_files':hash_files,'files':0,'directories':0,
            'bytes':0,'rows':[],'errors':[],'unseen_extent':'unknown_until_complete'}
    def walk(path,relative,depth):
        custody.check();need(depth<=12,'fixture directory depth cap')
        before=os.lstat(path);need(stat.S_ISDIR(before.st_mode),'ordinary fixture directory')
        result['directories']+=1;need(result['directories']<=128,'fixture directory count cap')
        iterator=None;first=None;later=[]
        try:
            iterator=os.scandir(path)
            for ent in iterator:
                custody.check();custody.census_entries+=1
                need(custody.census_entries<=100000,'cumulative observed census entry cap')
                need(result['files']+result['directories']<=8192,'fixture entry cap')
                child=path/ent.name;rel=relative+'/'+ent.name if relative else ent.name
                s=ent.stat(follow_symlinks=False)
                need(not stat.S_ISLNK(s.st_mode),'no fixture symlink')
                if stat.S_ISDIR(s.st_mode):walk(child,rel,depth+1)
                else:
                    need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'single-link regular fixture')
                    result['files']+=1;result['bytes']+=s.st_size
                    row={'path':rel,'bytes':s.st_size,'mode':stat.S_IMODE(s.st_mode)}
                    if hash_files:result['rows'].append(row)
                    need(result['files']<=8192 and result['bytes']<=24*MIB and s.st_size<=2*MIB,
                         'whole fixture retained byte/member/file cap')
                    if hash_files:
                        custody.reserve_read(s.st_size+1)
                        fd=None;err=None;extras=[];h=hashlib.sha256();observed=0
                        try:
                            fd=os.open(child,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                            need(stamp(os.fstat(fd))==stamp(s),'fixture open identity')
                            left=s.st_size+1
                            while left:
                                custody.check();b=os.read(fd,min(65536,left))
                                observed+=len(b);custody.read_observed+=len(b);h.update(b)
                                row['observed_bytes']=observed;row['sha256_prefix']=h.hexdigest()
                                if not b:break
                                left-=len(b)
                            need(observed==s.st_size and stamp(os.fstat(fd))==stamp(s)==stamp(os.lstat(child)),
                                 'fixture final content identity')
                        except BaseException as exc:err=exc
                        if fd is not None:
                            closing,fd=fd,None
                            try:os.close(closing)
                            except BaseException as exc:extras.append(exc)
                        if err is not None or extras:
                            err=err if err is not None else extras.pop(0)
                            err.launcher_cleanup_errors=tuple(extras);raise err
                        row['sha256']=h.hexdigest();row['complete']=True
            need(stamp(os.lstat(path))==stamp(before),'fixture directory changed during census')
        except BaseException as exc:first=exc
        if iterator is not None:
            closing,iterator=iterator,None
            try:closing.close()
            except BaseException as exc:later.append(exc)
        if first is not None or later:
            first=first if first is not None else later.pop(0)
            old=tuple(getattr(first,'launcher_cleanup_errors',()))
            first.launcher_cleanup_errors=old+tuple(later);raise first
    try:
        walk(root,'',0);custody.check()
        result['complete']=True;result['unseen_extent']=0
    except BaseException as exc:
        result['errors'].append(describe(exc));custody.fail('fixture_census',exc)
    return result

class Results(unittest.TestResult):
    def __init__(self,custody,retained):
        super().__init__()
        self.failfast=True;self.custody=custody;self.retained=retained
        self.rows=[{'method':n,'status':'not_entered','events':[]} for n in METHODS]
        self.by_name={r['method']:r for r in self.rows}
        self.lifecycle=[];self.active=None;self.raw_error_tuples=[];self.snapshots=[]
    def row(self,test):
        return self.by_name.get(getattr(test,'_testMethodName',None))
    def startTest(self,test):
        self.custody.check()
        r=self.row(test);need(r is not None and r['status']=='not_entered','exact unique selected test')
        need([x['method'] for x in self.rows if x['status']=='not_entered'][0]==r['method'],
             'exact test order')
        r['status']='entered';self.active=r
        super().startTest(test)
    def record(self,test,status,err=None):
        r=self.row(test)
        event={'status':status,'test':str(test)}
        if err:
            self.raw_error_tuples.append(err);event['error']=describe(err[1])
            self.custody.fail('unittest.'+status,err[1])
        if r is None:self.lifecycle.append(event)
        else:r['events'].append(event);r['status']=status
        if status!='passed':self.stop()
    def addSuccess(self,test):
        super().addSuccess(test);self.record(test,'passed')
    def addError(self,test,err):
        # Keep actual tuples independently; avoid unbounded unittest traceback strings.
        self.errors.append((test,'see retained exact exception descriptor'))
        self.record(test,'error',err)
    def addFailure(self,test,err):
        self.failures.append((test,'see retained exact exception descriptor'))
        self.record(test,'failed',err)
    def addSkip(self,test,reason):
        super().addSkip(test,reason)
        exc=ValueError('selected test skipped: '+str(reason))
        self.record(test,'skipped',(type(exc),exc,None))
    def addExpectedFailure(self,test,err):
        self.record(test,'unexpected_expected_failure',err)
    def addUnexpectedSuccess(self,test):
        exc=ValueError('unexpected success disposition not selected')
        self.record(test,'unexpected_success',(type(exc),exc,None))
    def addSubTest(self,test,subtest,err):
        if err:self.record(test,'subtest_failure',err)
    def stopTest(self,test):
        r=self.row(test)
        try:
            self.custody.check()
            known={}
            for key in ('budget','eval_budget'):
                b=getattr(test,key,None)
                if b is not None:known[key]=b.observation()
            r['accessible_task_budgets']=known
            snapshot=census(self.retained.root,self.custody,False)
            self.snapshots.append({'after':r['method'],**snapshot})
            need(snapshot['complete'],'complete after-test fixture census required')
            self.custody.check()
        except BaseException as exc:
            self.record(test,'post_test_failure',(type(exc),exc,exc.__traceback__))
        finally:
            self.active=None;super().stopTest(test)

def runtime_admission():
    need(sys.platform=='linux' and sys.implementation.name=='cpython' and
         sys.version_info[:3]==(3,11,18),'selected Linux CPython3.11.18')
    need(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode and not sys.flags.optimize,
         'isolated no-site no-bytecode child')
    need(not any(k=='numpy' or k.startswith('numpy.') for k in sys.modules),
         'NumPy not loaded before selected installation admission')
    need(SITE not in sys.path,'ambient selected site path absent before admission')
    ordinary(SITE);ordinary(NUMPY)
    sys.path.append(SITE)
    numpy=importlib.import_module('numpy')
    need(numpy.__version__=='2.4.6' and
         str(Path(numpy.__file__).resolve())==NUMPY+'/__init__.py',
         'actual selected NumPy version and origin')
    return {'python':sys.version,'executable':sys.executable,'numpy_version':numpy.__version__,
            'numpy_origin':numpy.__file__,'site_root':SITE,
            'all_numpy_native_bytes_authenticated':False,
            'scientific_environment_parity':False,
            'trust_boundary':'selected CI Python/NumPy installation for four-value invented engineering maps; version/origin only'}

def run(args,c):
    out=ordinary(args.output)
    need(not out.exists(),'fresh child output root')
    out.mkdir(mode=0o700);os.chmod(out,0o700)
    result={'schema':'n074_operator_engineering_result_v1','status':'failed',
            'scientifically_qualified':False,'native_owner_execution':False,
            'original_scope':'eleven actual accepted operator tests; unchanged four-value fixtures',
            'ordered_tests':[{'method':n,'status':'not_entered','events':[]} for n in METHODS],
            'lifecycle_errors':[],'fixture_census':None}
    retained=None;finder=None;test_module=None;original_tempfile=None;test_result=None;suite=None
    bodies={};module_rows=[]
    try:
        raw=c.capture(args.selection,{'bytes':args.selection_bytes,'sha256':args.selection_sha256})
        selected=json.loads(raw)
        need(selected['schema']=='n074_public_operator_controls_v1' and
             selected['methods']==list(METHODS) and selected['attempts']==1 and
             selected['native_scientific_execution'] is False,'fixed exact controls selection')
        base=ordinary(args.source_root)
        need(Path(__file__)==base/'controls/run_controls.py','literal captured child path')
        need(out.name=='child' and out.parent.name=='neural074-operator-ci-v1' and
             base not in out.parents and out not in base.parents,'fresh disjoint output root')
        c.capture(__file__,selected['launcher'])
        need(selected['modules']==MODULES,'exact relocated original module identities')
        module_rows=[dict(r,path=str(base/r['path'])) for r in MODULES]
        need(len(module_rows)==20,'complete unchanged task module roster')
        need(len({r['module'] for r in module_rows})==20,'unique module identities')
        need(not any(k in ('n074','n074_operator',CONTROL_MODULE) or
                     k.startswith(('n074.','n074_operator.')) for k in sys.modules),
             'no preexisting task modules')
        for r in module_rows:bodies[r['module']]=c.capture(r['path'],r)
        result['captured_sources']=[{k:r[k] for k in ('module','path','bytes','sha256')} for r in module_rows]
        result['runtime']=runtime_admission();c.check()
        need(not any(k in ('n074','n074_operator',CONTROL_MODULE) or
                     k.startswith(('n074.','n074_operator.')) for k in sys.modules),
             'no task namespace introduced by runtime admission')
        finder=Captured(module_rows,bodies);sys.meta_path.insert(0,finder)
        test_module=importlib.import_module(CONTROL_MODULE);c.check()
        need(test_module.__loader__ is finder and test_module.__spec__.loader is finder and
             test_module.__file__ == finder.rows[CONTROL_MODULE]['path'],
             'actual control module must use the captured loader and source path')
        cls=test_module.OperatorBoundary
        need(issubclass(cls,unittest.TestCase),'actual selected unittest class')
        need(all(callable(getattr(cls,n,None)) for n in METHODS),'all exact selected methods')
        retained=Retained(out/'fixtures',c)
        original_tempfile=test_module.tempfile
        test_module.tempfile=retained.namespace()
        test_result=Results(c,retained)
        suite=unittest.TestSuite([cls(n) for n in METHODS])
        suite._cleanup=False
        suite.run(test_result)
        c.check()
    except BaseException as exc:c.fail('whole_control_body',exc)
    finally:
        if test_module is not None and original_tempfile is not None:
            try:test_module.tempfile=original_tempfile
            except BaseException as exc:c.fail('tempfile_binding_restore',exc)
        if finder is not None:
            try:
                need(sys.meta_path[0] is finder,'captured loader ownership unchanged')
                sys.meta_path.remove(finder)
            except BaseException as exc:c.fail('captured_loader_retire',exc)
        if test_result is not None:
            result['ordered_tests']=test_result.rows
            result['lifecycle_errors']=test_result.lifecycle
            result['tests_run']=test_result.testsRun
            result['boundary_censuses']=test_result.snapshots
        if finder is not None:result['loaded_modules']=list(finder.loaded)
        if retained is not None:
            result['retention_registry']=retained.records
            result['fixture_census']=census(retained.root,c,True)
    try:
        c.check()
        need(test_result is not None and test_result.testsRun==11 and
             all(r['status']=='passed' for r in result['ordered_tests']) and
             not result['lifecycle_errors'],'all eleven complete with no class/lifecycle error')
        need(result['fixture_census'] is not None and result['fixture_census']['complete'],
             'complete final retained fixture inventory')
        need(c.first is None,'no earlier body/cleanup/census error')
        result['status']='passed'
    except BaseException as exc:c.fail('final_complete_suite_admission',exc)
    result['counts']={k:sum(r['status']==k for r in result['ordered_tests'])
                      for k in sorted({r['status'] for r in result['ordered_tests']})}
    result['custody']=c.observation()
    result['snapshot_before_own_publication']=True
    result['success_requires_outer_natural_zero_and_final_terminal_closure']=True
    result['first_error']=None if c.first is None else describe(c.first)
    record=None;published_events=0
    try:
        body=encoded(result);need(len(body)<=3*MIB,'finite full control result')
        record=c.publish(out/'CONTROL_RESULT.json',body);published_events=len(c.events)
    except BaseException as exc:c.fail('control_result_publication',exc)
    terminal={'schema':'n074_control_terminal_v1','status':result['status'] if c.first is None else 'failed',
              'counts':result['counts'],'record':record,
              'first_error':None if c.first is None else describe(c.first),
              'later_events':c.events[published_events:],
              'record_is_prepublication_snapshot':True}
    try:
        c.check();b=encoded(terminal);need(len(b)<=24576,'finite terminal summary')
        sys.stdout.write(b.decode());sys.stdout.flush();c.check()
    except BaseException as exc:
        c.fail('terminal_or_final_clock',exc)
        try:
            fallback={'status':'failed','evidence_transport_incomplete':True,
                      'first_error':describe(c.first),'known_later_events':c.events[published_events:],
                      'scope':'one bounded fallback; last failure cannot guarantee durable evidence'}
            b=encoded(fallback);need(len(b)<=24576,'finite terminal fallback')
            sys.stderr.write(b.decode());sys.stderr.flush();c.check()
        except BaseException:pass
    return 0 if c.first is None and result['status']=='passed' else 1

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--selection',required=True)
    p.add_argument('--source-root',required=True)
    p.add_argument('--selection-bytes',required=True,type=int)
    p.add_argument('--selection-sha256',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--origin',required=True,type=float)
    p.add_argument('--deadline',required=True,type=float)
    a=p.parse_args()
    c=Custody(a.origin,a.deadline)
    # Full-process limits, never a new per-test CPU origin. No hard RSS claim.
    resource.setrlimit(resource.RLIMIT_CPU,(160,165))
    resource.setrlimit(resource.RLIMIT_FSIZE,(4*MIB,4*MIB))
    c.check()
    return run(a,c)

if __name__=='__main__':
    try:code=main()
    except BaseException as exc:
        code=1
        try:
            b=encoded({'status':'failed','admission_or_last_transport_incomplete':True,
                       'error':describe(exc)})
            if len(b)<=24576:sys.stderr.write(b.decode());sys.stderr.flush()
        except BaseException:pass
    raise SystemExit(code)
