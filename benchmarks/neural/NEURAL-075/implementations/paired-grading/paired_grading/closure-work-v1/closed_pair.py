"""Capture the selected incumbent's complete unscored NEURAL-075 producer.

This is a trusted-host source interface, not execution/grading authority. It never
loads targets, runs a candidate, imports native dependencies, or authorizes grade.
The pure verifier accepts explicit trusted fixture bindings for engineering tests;
production capture always loads the fixed authenticated incumbent source chain.
"""
import ast
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import types
from types import MappingProxyType

REG = 'authoring/delivery-20261105/common/neural075-full-cohort-registration-v1'
REG_PIN = {'bytes':640,'sha256':'7dc9d4ef326af8372f33b17bd88d057304a535552641cc291bb543ae7c0814ff'}
DESIGN_PIN = {'bytes':934634,'sha256':'56ff1e67bb824b9ad6ab9005db82a11349581bb634a0725f4a1cca81019a6026'}
CASES = tuple(f'Subject{p}/{a}/{t}' for p in range(1,6) for a in ('neural','no_neural','training_permuted') for t in ('imagery','perception'))
SOURCE_FILES = frozenset(('LOCK.json','entry.py','holder.py','invoke.py','panel.py','stage.py','SOURCE_MANIFEST.json'))
META_CAP = 100000


def need(ok, why='closed pair boundary'):
    if not ok: raise ValueError(why)


def pin(raw): return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def encoded(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def parse(raw):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate JSON key'); result[key]=value
        return result
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda _: need(False,'nonfinite JSON'))


def descriptor(value, cap):
    need(type(value)is dict and set(value)=={'bytes','sha256'} and type(value['bytes'])is int and 0<value['bytes']<=cap and type(value['sha256'])is str and re.fullmatch('[a-f0-9]{64}',value['sha256']) is not None,'descriptor')
    return value


def absolute(value):
    need(type(value)is str and value.startswith('/') and '\x00' not in value and '\n' not in value,'absolute path')
    p=PurePosixPath(value); need(str(p)==value and '..' not in p.parts,'canonical path'); return value


@dataclass
class ReadBudget:
    max_bytes:int
    max_files:int
    deadline:float
    used_bytes:int=0
    used_files:int=0
    def __post_init__(self):
        need(type(self.max_bytes)is int and self.max_bytes>0 and type(self.max_files)is int and self.max_files>0 and type(self.deadline)in (int,float) and math.isfinite(self.deadline) and self.deadline>time.monotonic(),'explicit positive capture budget')
    def tick(self):
        need(time.monotonic()<self.deadline,'capture cutoff')
    def read(self, extent, label='body'):
        self.charge(extent)
    def charge(self, extent):
        need(type(extent)is int and extent>0 and time.monotonic()<self.deadline,'capture cutoff')
        need(self.used_bytes+extent<=self.max_bytes and self.used_files+1<=self.max_files,'capture budget exhausted')
        self.used_bytes+=extent; self.used_files+=1


class FileReader:
    """Stable bounded reads with one retained immutable body per selected path."""
    def __init__(self,budget): self.budget=budget; self.bodies={}; self.directories={}
    def tick(self): self.budget.tick()
    def read(self,path,expected=None,cap=META_CAP):
        self.tick(); key=absolute(str(path))
        if expected is not None: descriptor(expected,cap)
        if key not in self.bodies:
            p=Path(key)
            for q in (p,*p.parents): need(not q.is_symlink(),'symlink component')
            fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,'rb') as stream:
                a=os.fstat(stream.fileno()); need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=cap,'ordinary bounded body')
                self.budget.read(a.st_size+1,'NEURAL075 selected captured body'); raw=stream.read(a.st_size+1); z=os.fstat(stream.fileno()); n=p.lstat()
            need(len(raw)==a.st_size and all(getattr(a,k)==getattr(z,k)==getattr(n,k) for k in ('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns')),'body changed during capture')
            self.bodies[key]=raw
        raw=self.bodies[key]; need(len(raw)<=cap and (expected is None or pin(raw)==expected),'body pin'); self.tick(); return raw
    def children(self,path):
        self.tick(); key=absolute(str(path))
        if key not in self.directories:
            p=Path(key)
            for q in (p,*p.parents): need(not q.is_symlink(),'directory symlink')
            a=p.lstat(); need(stat.S_ISDIR(a.st_mode),'ordinary directory')
            names=[]
            with os.scandir(p) as entries:
                for entry in entries:
                    need(len(names)<128,'bounded directory census'); names.append(entry.name)
            z=p.lstat(); need(all(getattr(a,k)==getattr(z,k) for k in ('st_dev','st_ino','st_mtime_ns','st_ctime_ns')),'directory changed during census')
            self.budget.tick(); self.directories[key]=frozenset(names)
        self.tick(); return self.directories[key]
    def exists(self,path):
        p=PurePosixPath(str(path)); return p.name in self.children(str(p.parent))


@dataclass(frozen=True)
class SourceBindings:
    """Trusted immutable source values. Production creates these only via load."""
    binding_raw:bytes
    source_manifest:bytes
    source_bodies:tuple
    adapter_raw:bytes
    lifecycle_raw:bytes
    provenance_raw:bytes
    @property
    def binding(self): return parse(self.binding_raw)
    @property
    def lock(self): return parse(dict(self.source_bodies)['LOCK.json'])
    @property
    def source_pin(self): return pin(self.source_manifest)


def load_fixed_bindings(repository,budget):
    repo=absolute(str(repository)); r=FileReader(budget); base=repo+'/'+REG
    manifest_raw=r.read(base+'/SOURCE_MANIFEST.json',REG_PIN)
    manifest=parse(manifest_raw)
    need(set(manifest)=={'schema','task_id','files'} and manifest['schema']=='neural075_complete_pair_adapter_source_v1' and manifest['task_id']=='NEURAL-075' and set(manifest['files'])=={'adapter.py','BINDINGS.json','ACCESS_BINDING.json','README.md'},'registration chain')
    reg={n:r.read(base+'/'+n,p) for n,p in manifest['files'].items()}
    binding=parse(reg['BINDINGS.json']); cm=binding['controller_manifest']
    def selected(row):
        need(type(row)is dict and set(row)=={'path','bytes','sha256'} and not row['path'].startswith('/') and '..' not in PurePosixPath(row['path']).parts,'source path')
        return r.read(repo+'/'+row['path'],{k:row[k] for k in ('bytes','sha256')},150000)
    source_manifest=selected(cm); sm=parse(source_manifest)
    need(sm['schema']=='neural075_invocation_source_v1' and set(sm['runtime_files'])==SOURCE_FILES-{'SOURCE_MANIFEST.json'},'controller members')
    bodies={n:selected(binding['controller_members'][n]) for n in sm['runtime_files']}
    need(all(pin(bodies[n])==p for n,p in sm['runtime_files'].items()),'controller manifest joins')
    lock=parse(bodies['LOCK.json'])
    need(tuple(binding['cases'])==tuple(lock['cases'])==CASES and lock['design']==DESIGN_PIN and binding['collection_manifest']==lock['collection_manifest'],'original complete design binding')
    need(pin(reg['ACCESS_BINDING.json'])=={k:binding['paired_access_binding'][k] for k in ('bytes','sha256')},'access source join')
    lifecycle=selected(lock['pins']['lifecycle'])
    provenance=encoded({'registration_manifest':REG_PIN,'captured_sources':{str(PurePosixPath(p).relative_to(repo)):pin(b) for p,b in r.bodies.items()},'design_body_read':False,'native_imported':False})
    return SourceBindings(reg['BINDINGS.json'],source_manifest,tuple(sorted(bodies.items())),reg['adapter.py'],lifecycle,provenance)


def _functions(raw,names,namespace):
    """Compile exact selected function ASTs; imports and native entrypoints excluded."""
    tree=ast.parse(raw); nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    need({n.name for n in nodes}==set(names) and len(nodes)==len(names),'exact source functions')
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<captured-incumbent>','exec'),namespace)
    return types.SimpleNamespace(**namespace)


class _VPath:
    def __init__(self,path,reader): self.value=absolute(str(path)); self.reader=reader
    def __truediv__(self,other): return _VPath(str(PurePosixPath(self.value)/other),self.reader)
    def __str__(self): return self.value
    @property
    def name(self): return PurePosixPath(self.value).name
    def iterdir(self): return tuple(self/n for n in self.reader.children(self.value))


def _validators(bindings,reader):
    a=_functions(bindings.adapter_raw,{'need','parse','commit_metadata'},{'json':json})
    b=bindings.binding
    ns={'hashlib':hashlib,'math':math,'re':re,'CONDITION':b['condition'],'FILES':set(SOURCE_FILES)-{'SOURCE_MANIFEST.json'}}
    ns['path']=ns['Path']=lambda p:_VPath(str(p),reader)
    ns['os']=types.SimpleNamespace(path=types.SimpleNamespace(lexists=lambda p:reader.exists(str(p))))
    ns['capture']=lambda p,expected=None,cap=META_CAP:reader.read(str(p),expected,cap)
    def tree(root,limit=100):
        root=str(root); files=set(); dirs=set(); pending=[('',root)]; count=0
        while pending:
            relative,current=pending.pop(); count+=1; need(count<=limit,'bounded snapshot tree')
            names=reader.children(current)
            for name in names:
                rel=(relative+'/' if relative else '')+name; full=current+'/'+name
                if full in reader.directories: dirs.add(rel); pending.append((rel,full))
                else: files.add(rel); count+=1; need(count<=limit,'bounded snapshot members')
        return files,dirs,0
    ns['tree_names']=tree
    def source(expected):
        need(expected==bindings.source_pin,'captured source identity'); return dict(bindings.source_bodies),bindings.source_manifest
    ns['source']=source
    m=_functions(dict(bindings.source_bodies)['invoke.py'],{'need','pin','validate_output','output_check','child_ok','closed_case','receipt'},ns)
    life=_functions(bindings.lifecycle_raw,{'lifecycle_closed'},{'need':m.need})
    e=types.SimpleNamespace(r=types.SimpleNamespace(parse=a.parse,IMAGE=b['fixed_image']),closed=life.lifecycle_closed)
    return a,m,e


def _layout(root,commits):
    """Complete fixed producer layout; no arbitrary recursive body acquisition."""
    files={root+'/'+n for n in ('FROZEN_PANEL.json','CLOSED60.json','COMPLETE.json','A-RECEIPTS.json','B-RECEIPTS.json')}
    dirs={root,root+'/views',root+'/runs'}
    for access in ('A','B'):
        base=root+'/'+access; dirs.update((base,base+'/submission',base+'/contexts',root+'/runs/'+access)); files.add(base+'/COMPLETE.json')
        files.update((base+'/submission/collection.json',base+'/contexts/CONTEXTS.json'))
        commit=commits[access]['directory']; files.update((commit+'/COMMIT.json',commit+'/program.py'))
        for index in range(30):
            d=f'{root}/runs/{access}/{index:02d}'; files.add(d+'-HOST.json'); dirs.update((d,d+'/source',d+'/attempt',d+'/attempt/snapshot',d+'/attempt/captured'))
            files.update(d+'/'+n for n in ('HOST_EXIT.json','context.json'))
            files.update(d+'/attempt/'+n for n in ('COMPLETE.json','INTENT.json','EXECUTION.json','INTENT-volume.json','INTENT-holder.json','INTENT-candidate.json','captured/prediction.json'))
            files.update(d+'/source/'+n for n in SOURCE_FILES)
            files.update(d+'/attempt/snapshot/'+n for n in SOURCE_FILES|{'program.py'})
            files.update((f'{base}/submission/{index:02d}.json',f'{base}/contexts/{index:02d}.json'))
    return files,dirs


def _census(reader,root,commits):
    files,dirs=_layout(root,commits)
    expected={d:set() for d in dirs}
    for p in files|dirs:
        parent=str(PurePosixPath(p).parent)
        if parent in expected and p!=parent: expected[parent].add(PurePosixPath(p).name)
    for d in sorted(dirs):
        need(reader.children(d)==expected[d],'exact producer directory '+d)
    return files,dirs


@dataclass(frozen=True)
class ClosedSnapshot:
    root:str
    complete_pin_raw:bytes
    commits_raw:bytes
    bodies:tuple
    directories:tuple


class SnapshotReader:
    def tick(self):
        if self.budget is not None: self.budget.tick()
    def __init__(self,snapshot,budget=None):
        self.budget=budget
        self.bodies=MappingProxyType(dict(snapshot.bodies)); self.directories=MappingProxyType({p:frozenset(n) for p,n in snapshot.directories})
        need(len(self.bodies)==len(snapshot.bodies) and len(self.directories)==len(snapshot.directories),'unique snapshot paths')
        need(all(type(b)is bytes for b in self.bodies.values()),'immutable captured bodies')
    def read(self,path,expected=None,cap=META_CAP):
        self.tick(); p=absolute(str(path)); raw=self.bodies[p]
        if self.budget is not None: self.budget.read(len(raw)+1,'NEURAL075 immutable snapshot replay')
        need(0<len(raw)<=cap and (expected is None or pin(raw)==descriptor(expected,cap)),'snapshot pin'); self.tick(); return raw
    def children(self,path):
        self.tick(); return self.directories[absolute(str(path))]
    def exists(self,path):
        p=PurePosixPath(str(path)); return p.name in self.children(str(p.parent))


@dataclass(frozen=True)
class CapturedCase:
    access:str
    case:str
    prediction:bytes
    context:bytes


@dataclass(frozen=True)
class ClosedPair:
    cases:tuple
    snapshot:ClosedSnapshot
    closure_summary:bytes


def _selection(root,complete,commits):
    absolute(root); descriptor(complete,META_CAP)
    need(type(commits)is dict and set(commits)=={'A','B'},'both selected commitments')
    roots=[PurePosixPath(root)]
    for a in ('A','B'):
        need(set(commits[a])=={'directory','commit_pin'},'commit selection schema'); descriptor(commits[a]['commit_pin'],10000)
        roots.append(PurePosixPath(absolute(commits[a]['directory'])))
    need(all(x!=y and x not in y.parents and y not in x.parents for i,x in enumerate(roots) for y in roots[i+1:]),'disjoint producer and commitment roots')


def _verify(reader,bindings,root,complete_pin,commits):
    _selection(root,complete_pin,commits); _census(reader,root,commits)
    a,m,e=_validators(bindings,reader); binding=bindings.binding; lock=bindings.lock; sp=bindings.source_pin
    def obj(path,expected=None,cap=META_CAP): return a.parse(reader.read(path,expected,cap))
    frozen={}
    for access in ('A','B'):
        row=commits[access]; c=obj(row['directory']+'/COMMIT.json',row['commit_pin'],10000)
        a.commit_metadata(c,access,c['program'],row['commit_pin'],binding)
        reader.read(row['directory']+'/program.py',c['program'],131072).decode('utf-8'); frozen[access]=c
    total=sum(30*(frozen[x]['seconds']+1680) for x in ('A','B'))+1800
    top=obj(root+'/COMPLETE.json',complete_pin)
    need(set(top)=={'schema','source','commits','closed60','collections','cases_per_access','candidate_invocations','scientific_tasks','private_scoring_calls','runtime_qualified','scientific_qualification_added','conservative_host_phase_reservations','elapsed','limit'},'top completion schema')
    need(top['schema']=='neural075_complete_ab_program_panel_v1' and top['source']==sp and top['commits']==commits and top['cases_per_access']==30 and top['candidate_invocations']==60 and top['scientific_tasks']==1 and top['private_scoring_calls']==0 and top['runtime_qualified']is False and top['scientific_qualification_added']is False and type(top['elapsed'])in(int,float) and math.isfinite(top['elapsed']) and 0<=top['elapsed']<=top['limit']==total,'complete unscored panel')
    need(top['conservative_host_phase_reservations']=={'read_reserved':126000000000,'write_reserved':17320000000},'original full host phase reservation')
    freeze=obj(root+'/FROZEN_PANEL.json')
    need(freeze=={'schema':'neural075_frozen_ab_panel_v1','source':sp,'commits':commits,'collection_manifest':lock['collection_manifest'],'ordered_cases':list(CASES),'access_order':['A','B'],'feedback':'none','programs_frozen_before_query_staging':True,'seconds':total},'both programs frozen before staging')
    closed=obj(root+'/CLOSED60.json',top['closed60'])
    need(set(closed)=={'schema','source','commits','records','candidate_calls','feedback_calls','private_scoring_calls'} and closed['schema']=='neural075_closed60_v1' and closed['source']==sp and closed['commits']==commits and closed['candidate_calls']==60 and closed['feedback_calls']==0 and closed['private_scoring_calls']==0 and type(closed['records'])is list and len(closed['records'])==60,'closed60 barrier')
    need(type(top['collections'])is dict and set(top['collections'])=={'A','B'},'both collection completions')
    prepared=[]
    # Entire compact metadata chain for both accesses precedes any score body.
    for ai,access in enumerate(('A','B')):
        c=frozen[access]; cp=commits[access]['commit_pin']; product=top['collections'][access]
        need(set(product)=={'completion','child'},'collection child'); m.child_ok(product['child'])
        finish=obj(root+'/'+access+'/COMPLETE.json',product['completion'])
        need(set(finish)=={'schema','source','commit','program','condition','access','operator_receipts','cases','collection','context_index','outputs','grading_performed','runtime_qualified'} and finish['schema']=='neural075_full30_collection_v1' and finish['source']==sp and finish['commit']==cp and finish['program']==c['program'] and finish['condition']==binding['condition'] and finish['access']==access and finish['cases']==list(CASES) and finish['outputs']==30 and finish['grading_performed']is False and finish['runtime_qualified']is False,'full30 collection')
        receipts=obj(root+'/'+access+'-RECEIPTS.json',finish['operator_receipts'])
        need(type(receipts)is list and len(receipts)==30,'thirty receipts')
        index=obj(root+'/'+access+'/submission/collection.json',finish['collection'],2**20)
        context_index=obj(root+'/'+access+'/contexts/CONTEXTS.json',finish['context_index'],2**20)
        need(set(index)=={'protocol','program','cases'} and index['protocol']=='neural075-v1' and index['program']==c['program'] and type(index['cases'])is list and len(index['cases'])==30,'submission index')
        need(set(context_index)=={'protocol','design_sha256','access_condition','cases'} and context_index['protocol']=='neural075-v1' and context_index['design_sha256']==lock['design']['sha256'] and context_index['access_condition']==access and type(context_index['cases'])is list and len(context_index['cases'])==30,'context design index')
        for k,case in enumerate(CASES):
            reader.tick(); d=f'{root}/runs/{access}/{k:02d}'; proof=closed['records'][ai*30+k]
            need(set(proof)=={'case','access','record'} and proof['case']==case and proof['access']==access,'ordered CLOSED60 member')
            host=obj(d+'-HOST.json',proof['record'])
            need(set(host)=={'case','access','stage_child','invocation_child','input_identity','host_exit'} and host['case']==case and host['access']==access,'host case/access')
            m.child_ok(host['stage_child']); m.child_ok(host['invocation_child'])
            need(receipts[k]=={'case':case,'directory':d,'host_exit':host['host_exit'],'enclosing_natural_zero_observed':True},'receipt path and exit join')
            h=obj(d+'/HOST_EXIT.json',host['host_exit']); m.child_ok(h['child'])
            done=obj(d+'/attempt/COMPLETE.json',h['completion'])
            need(done['input_identity']==host['input_identity'],'host staged identity join')
            intent=obj(d+'/attempt/INTENT.json',done['intent'])
            x=obj(d+'/attempt/EXECUTION.json',done['execution']); e.closed(x)
            need(intent['admission']['identity']==host['input_identity'],'staging admission identity')
            for j,prefix in ((index['cases'][k],'prediction'),(context_index['cases'][k],'context')):
                need(set(j)=={'case_id','path','bytes','sha256'} and j['case_id']==case and j['path']==f'{k:02d}.json','ordered index path')
                descriptor({z:j[z] for z in ('bytes','sha256')},4*2**20 if prefix=='prediction' else 2**20)
            need({z:index['cases'][k][z] for z in ('bytes','sha256')}==done['outputs']['prediction.json'] and {z:context_index['cases'][k][z] for z in ('bytes','sha256')}==intent['admission']['context_pin'],'collected source body joins')
            prepared.append((access,case,k,d,c,cp,host,intent,done))
    need(len(prepared)==60,'all sixty metadata before body validation')
    result=[]
    for access,case,k,d,c,cp,host,intent,done in prepared:
        reader.tick(); observed=m.receipt(e,c,cp,sp,case,d,host['host_exit']); need(observed==done,'actual incumbent receipt')
        pr=reader.read(d+'/attempt/captured/prediction.json',done['outputs']['prediction.json'],4*2**20)
        cr=reader.read(d+'/context.json',intent['admission']['context_pin'],2**20)
        need(a.parse(cr)==intent['admission']['context'],'captured context equality')
        need(reader.read(f'{root}/{access}/submission/{k:02d}.json',pin(pr),4*2**20)==pr and reader.read(f'{root}/{access}/contexts/{k:02d}.json',pin(cr),2**20)==cr,'exact collection copies')
        result.append(CapturedCase(access,case,pr,cr))
    summary=encoded({'schema':'neural075_captured_closed_pair_v1','source':sp,'complete':complete_pin,'closed60':top['closed60'],'commits':commits,'cases':60,'scientific_tasks':1,'private_scoring_calls':0,'runtime_qualified':False,'scientific_qualification_added':False,'design':lock['design'],'source_provenance':pin(bindings.provenance_raw),'authority':'capture_only_requires_independent_grade_selection'})
    reader.tick(); return tuple(result),summary


def verify_closed_snapshot(snapshot,bindings,budget=None):
    """Pure verifier; trusted fixture bindings must remain labelled as invented."""
    reader=SnapshotReader(snapshot,budget)
    cases,summary=_verify(reader,bindings,snapshot.root,parse(snapshot.complete_pin_raw),parse(snapshot.commits_raw))
    return ClosedPair(cases,snapshot,summary)


def capture_closed_pair(repository,root,expected_complete_pin,selected_commits,budget):
    """Production entry: source-authenticate then capture selected ordinary files.

    Independent root grading authority must be checked by the caller *before*
    this method. Passing pins never grants private-data or execution authority.
    No native qualification is inferred from the observed historical receipts.
    """
    bindings=load_fixed_bindings(repository,budget)
    reader=FileReader(budget)
    cases,summary=_verify(reader,bindings,absolute(str(root)),expected_complete_pin,selected_commits)
    snapshot=ClosedSnapshot(str(root),encoded(expected_complete_pin),encoded(selected_commits),tuple(sorted(reader.bodies.items())),tuple(sorted((p,tuple(sorted(n))) for p,n in reader.directories.items())))
    reader.tick(); return ClosedPair(cases,snapshot,summary)
