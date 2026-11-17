"""Literal isolated full-study entry. Source capture precedes custom imports."""
import argparse,hashlib,importlib.abc,importlib.util,json,os,stat,sys,time
from pathlib import Path

NAMES=frozenset(('arrays','authority','candidate_runner','channel','closure','common','controller','custody','entry_driver','episodes','fd_protocol','grade_driver','grade_entry','grading','host_observation','issuer_entry','issuer_sandbox','issuer_worker','metrics','model_io','numeric_entry','numeric_worker','outer','outputs','preparation','preparation_driver','preparation_entry','preparation_worker','projection_broker','projection_engine','protocol','public_projection','reference_driver','reference_tools','runtime','schedule','transport','transport.common','transport.process','transport.provider','worker_bootstrap'))

def need(v,r):
    if not v:raise ValueError(r)

def parse(raw):
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate metadata key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite metadata'))

PROTOCOL_PATH='neural081/protocol/CANDIDATE_PROTOCOL.txt'
CONTEXT_PATHS=frozenset(('neural081/protocol/SOURCE_AND_BOUNDARIES.md', 'neural081/protocol/SOURCE_BINDINGS.json', 'neural081/protocol/CANDIDATE_PROJECTION.md', 'neural081/protocol/DESIGN.md', 'neural081/protocol/EXECUTION_ADMISSION.md', 'neural081/protocol/EXPOSURE_AND_WORKLOAD.md', 'neural081/protocol/GRAPH_AND_CUSTODY.md', 'neural081/protocol/INTERFACES_AND_REVIEW_GATES.md', 'neural081/protocol/REFERENCE_MATHEMATICS.md', 'neural081/protocol/RESOURCE_CONTRACT.md', 'neural081/protocol/SUPPORT_CUSTODY.md', 'neural081/protocol/CANDIDATE_PROTOCOL.txt'))
VARIANT_ORIGINALS={'neural081/central/entry.py': {'path': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/central-adapter-v1/entry.py', 'bytes': 10092, 'sha256': '87fb1ef2b8cb8e31011cda0507fd1c1f0c9983c034262e35a93eaeff4d65c9e8'}, 'neural081/central/n081_routing.py': {'path': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/central-adapter-v1/n081_routing.py', 'bytes': 5812, 'sha256': '9e7de0f1c643dc5bbdb842df9f79962b8fe5cfbd888b8565ae684fd7f90b0e4e'}, 'neural081/central/n081_selection.py': {'path': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/central-adapter-v1/n081_selection.py', 'bytes': 12592, 'sha256': '391815c0bba259ea27e6a057447a23265f1df14f7f584c6c39762b82806bdf39'}, 'neural081/parent/program/entry.py': {'path': 'authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design/implementation-v1/installation-v1/acyclic-parent-v1/program/entry.py', 'bytes': 6486, 'sha256': '826663ae0b1ba1f4d94769e20cacab772cc00dd1bd7a37071f8478047afc9e48'}}

def exact(value,keys):
    need(type(value)is dict and set(value)==set(keys),'exact portable source metadata fields')

def same(a,b):
    if type(a)is not type(b):return False
    if type(a)is dict:return a.keys()==b.keys()and all(type(k)is str and same(a[k],b[k])for k in a)
    if type(a)is list:return len(a)==len(b)and all(same(x,y)for x,y in zip(a,b))
    return type(a)in(str,int,bool,type(None))and a==b

def relative(value):
    need(type(value)is str and 0<len(value)<=4096 and '\\'not in value and not value.startswith('/')and all(p not in('','.','..')for p in value.split('/')),'canonical source-relative locator')
    return value

def source_descriptor(desc,root=None):
    exact(desc,('path','bytes','sha256'));need(type(desc['bytes'])is int and 0<desc['bytes']<=16*2**20,'bounded nonboolean source extent')
    need(type(desc['sha256'])is str and len(desc['sha256'])==64 and all(x in '0123456789abcdef'for x in desc['sha256']),'exact source digest')
    if root is None:relative(desc['path'])
    else:
        p=Path(desc['path']);need(type(desc['path'])is str and p.is_absolute()and str(p)==desc['path']and not desc['path'].startswith('//')and '\\'not in desc['path']and all(x not in('','.','..')for x in desc['path'].split('/')[1:])and p.is_relative_to(root),'canonical source-instance descriptor')
    return desc

def execution_paths():
    prefix='neural081/parent/'
    return {'entry':prefix+'program/entry.py','modules':{n:prefix+'program/'+('transport/__init__.py'if n=='transport'else n.replace('.','/')+'.py')for n in NAMES},'auxiliary':{r:prefix+'references/'+r+'/numeric.py'for r in('r1','r2')}}

def python_paths():
    paths=execution_paths()
    return {paths['entry'],*paths['modules'].values(),*paths['auxiliary'].values(),*('neural081/central/'+n for n in('entry.py','n081_routing.py','n081_selection.py','n081_host.py','n081_readback.py','n081_dispatch.py','portable_gate.py')),'tools/neurobench_campaign.py','tools/neurobench_campaign_gate.py','tools/neural081_instance.py'}

def original_role_paths():
    base='authoring/delivery-20261105/common/remaining-builds-wave32/neural081-complete-design'
    install=base+'/implementation-v1/installation-v1'
    result={target:install+'/acyclic-parent-v1/'+target[len('neural081/parent/'):]for target in python_paths()if target.startswith('neural081/parent/')}
    for name in('n081_host.py','n081_readback.py','n081_dispatch.py'):
        result['neural081/central/'+name]=install+'/central-adapter-v1/'+name
    for name in('neurobench_campaign.py','neurobench_campaign_gate.py'):result['tools/'+name]='tools/'+name
    for target in CONTEXT_PATHS-{PROTOCOL_PATH}:
        name=Path(target).name
        result[target]=base+('/'if name in('SOURCE_AND_BOUNDARIES.md','SOURCE_BINDINGS.json')else '/correction-v4/')+name
    return result

def validate_construction(desc,root,capture,execution):
    """Authenticate acyclic construction, release and public-origin provenance.

    The caller's externally bound source manifest selects this construction.
    A constructor status never becomes independent runtime authorization.
    """
    source_descriptor(desc,root);need(desc['path']==str(root/'neural081/parent/CONSTRUCTION.json'),'fixed construction locator')
    construction=parse(capture(desc));exact(construction,('schema','task_id','root','release','public_origin','python_bodies','context_bodies','variants','construction_only','runtime_authorization'))
    need(construction['schema']=='neural081_portable_construction_v1'and construction['task_id']=='NEURAL-081'and construction['root']==str(root)and construction['construction_only']is True and construction['runtime_authorization']is False,'actual local construction only, no synthetic root/runtime acceptance')
    for key,name in(('release','PORTABLE_RELEASE.json'),('public_origin','PUBLIC_ORIGIN_MAP.json')):
        source_descriptor(construction[key],root);need(construction[key]['path']==str(root/'neural081'/name),'fixed original/release source metadata locator')
    release=parse(capture(construction['release']));origin=capture(construction['public_origin'])
    need({'bytes':len(origin),'sha256':hashlib.sha256(origin).hexdigest()}=={'bytes':48901,'sha256':'32705c641e263ac91c5f0b7f5ed60ac42cac9f9af87c07cd74e30cd1bcfee2f5'},'exact immutable reviewed public-origin manifest')
    origin_doc=parse(origin);need(origin_doc.get('schema')=='neural081_complete_public_original_source_manifest_v1','original public origin schema')
    origin_map={row['path']:{k:row[k]for k in('path','bytes','sha256')}for row in origin_doc['files']}
    originals=original_role_paths()
    exact(release,('schema','task_id','public_files','public_manifest','active_sources','variants'))
    need(release['schema']=='neural081_portable_release_v1'and release['task_id']=='NEURAL-081','separate portable release schema')
    public=release['public_files'];need(type(public)is list and len(public)==105,'full reviewed public source extent')
    for row in public:source_descriptor(row)
    public_paths=[r['path']for r in public];need(public_paths==sorted(public_paths)and len(set(public_paths))==105,'ordered unique public source roster')
    source_descriptor(release['public_manifest']);need(any(same(release['public_manifest'],r)for r in public),'public original manifest belongs to full public release')
    need({k:construction['public_origin'][k]for k in('bytes','sha256')}=={k:release['public_manifest'][k]for k in('bytes','sha256')}and {'bytes':len(origin),'sha256':hashlib.sha256(origin).hexdigest()}=={k:release['public_manifest'][k]for k in('bytes','sha256')},'public origin is exact original public metadata, never a rebound old hash')
    actual={};public_by_path={r['path']:r for r in public}
    for key,expected in(('python_bodies',python_paths()),('context_bodies',CONTEXT_PATHS)):
        rows=construction[key];need(type(rows)is list and len(rows)==len(expected),'exact complete construction role count')
        for row in rows:source_descriptor(row,root)
        paths=[r['path']for r in rows];need(paths==sorted(paths)and len(set(paths))==len(paths),'ordered unique active bodies')
        need({str(Path(p).relative_to(root))for p in paths}==expected,'literal complete active role map')
        actual.update({str(Path(r['path']).relative_to(root)):r for r in rows})
    active=release['active_sources'];need(type(active)is dict and list(active)==sorted(active)and set(active)==set(actual)and len(active)==66,'exact release active66 role roster')
    release_roles={'neural081/parent/program/entry.py','neural081/central/entry.py','neural081/central/n081_routing.py','neural081/central/n081_selection.py','neural081/central/portable_gate.py','tools/neural081_instance.py',PROTOCOL_PATH}
    for target,row in active.items():
        relative(target);exact(row,('kind','source','bytes','sha256'));relative(row['source'])
        source_descriptor({'path':target,'bytes':row['bytes'],'sha256':row['sha256']})
        need({k:row[k]for k in('bytes','sha256')}=={k:actual[target][k]for k in('bytes','sha256')},'release and actual construction identity join')
        need(row['kind']==('release'if target in release_roles else 'public'),'exact new/original source role distinction')
        if row['kind']=='public':
            need(row['source']==originals[target]and same(origin_map.get(row['source']),{'path':row['source'],'bytes':row['bytes'],'sha256':row['sha256']})and same(public_by_path.get(row['source']),origin_map[row['source']]),'exact role-specific unchanged original body from pinned public origin')
    variants=release['variants'];need(type(variants)is list and len(variants)==4,'exact four provenance-bootstrap variants')
    wanted=[]
    for row in variants:
        exact(row,('target','original'));source_descriptor(row['target']);source_descriptor(row['original']);target=row['target']['path']
        need(target in VARIANT_ORIGINALS and same(row['original'],VARIANT_ORIGINALS[target])and same(public_by_path.get(row['original']['path']),row['original']),'exact unchanged original variant identity')
        need(same(row['target'],{'path':target,**{k:actual[target][k]for k in('bytes','sha256')}}),'actual new variant identity')
        wanted.append({'target':actual[target],'original':row['original']})
    need([r['target']['path']for r in variants]==sorted(VARIANT_ORIGINALS)and same(construction['variants'],wanted),'ordered four source-derived variant pairs')
    for row in execution:
        source_descriptor(row,root);need(same(actual.get(str(Path(row['path']).relative_to(root))),row),'actual captured execution body in complete source construction')
    return construction,release,actual

def main():
    parser=argparse.ArgumentParser()
    for key in('operation','config','config-bytes','config-sha256','source','source-bytes','source-sha256','origin','deadline','bootstrap-read-cap'):
        parser.add_argument('--'+key,required=True)
    a=parser.parse_args();origin=float(a.origin);deadline=float(a.deadline);cap=int(a.bootstrap_read_cap)
    need(a.operation in('outer','controller')and 0<=origin<time.monotonic()<deadline and 0<cap<=64*2**20,'selected original entry bounds')
    count=0
    def capture(desc,maximum=16*2**20):
        nonlocal count
        need(type(desc)is dict and set(desc)=={'path','bytes','sha256'}and type(desc['bytes'])is int and 0<desc['bytes']<=maximum,'bounded complete source descriptor')
        path=desc['path'];p=Path(path);need(type(path)is str and p.is_absolute()and str(p)==path and not path.startswith('//')and all(x not in('','.','..')for x in path.split('/')[1:])and not any(x.is_symlink()for x in(p,*p.parents)),'canonical ordinary source path')
        count+=desc['bytes']+1;need(count<=cap and time.monotonic()<deadline,'initial full source read bound')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd);need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==desc['bytes'],'exact ordinary source extent')
            with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(desc['bytes']+1)
            after=os.fstat(fd);named=p.lstat();keys=('st_dev','st_ino','st_size','st_mode','st_nlink','st_mtime_ns','st_ctime_ns')
            need(len(raw)==desc['bytes']and hashlib.sha256(raw).hexdigest()==desc['sha256']and all(getattr(before,k)==getattr(after,k)==getattr(named,k)for k in keys),'actual complete immutable source body')
        finally:os.close(fd)
        need(time.monotonic()<deadline,'original startup deadline');return raw
    source={'path':a.source,'bytes':int(a.source_bytes),'sha256':a.source_sha256};manifest=parse(capture(source))
    need(type(manifest)is dict and set(manifest)=={'schema','task_id','entry','modules','auxiliary','construction'},'exact full programme source manifest')
    need(manifest['schema']=='neural081_portable_parent_source_v1'and manifest['task_id']=='NEURAL-081'and manifest['entry']['path']==str(Path(__file__).absolute()),'exact literal source entry')
    capture(manifest['entry'])
    # Reserve the interpreter's initial entry-source demand separately from the
    # subsequent explicit identity capture; package/OS physical I/O is not metered.
    count+=manifest['entry']['bytes'];need(count<=cap,'initial interpreter entry-source reservation')
    captured={};files=[manifest['entry']]
    base=Path(__file__).absolute().parent
    for row in manifest['modules']:
        need(type(row)is dict and set(row)=={'name','source'},'fixed module row');name=row['name']
        need(name in NAMES and name not in captured and name not in sys.modules,'fixed complete captured source, no ambient custom module')
        relative='transport/__init__.py'if name=='transport'else name.replace('.','/')+'.py'
        need(row['source']['path']==str(base/relative),'fixed source-owned module locator')
        captured[name]=(row['source']['path'],capture(row['source']));files.append(row['source'])
    need(set(captured)==NAMES,'all complete implementation modules before import')
    need(type(manifest['auxiliary'])is list and len(manifest['auxiliary'])==2,'both independently authored numerical sources retained')
    for role,row in zip(('r1','r2'),manifest['auxiliary']):
        need(type(row)is dict and set(row)=={'role','source'}and row['role']==role and row['source']['path']==str(base.parent/'references'/role/'numeric.py'),'exact independent numerical source identity')
        capture(row['source']);files.append(row['source'])
    root=base.parents[2]
    need(base==root/'neural081/parent/program','literal portable parent layout')
    validate_construction(manifest['construction'],root,capture,files)
    files.append(manifest['construction'])
    need(len({d['path']for d in files})==len(files),'unique complete source bodies')
    config_desc={'path':a.config,'bytes':int(a.config_bytes),'sha256':a.config_sha256};config=parse(capture(config_desc))
    need(type(config)is dict and config.get('schema')=='neural081_selected_execution_envelope_v2'and config.get('source_manifest')==source,'separate selected actual acyclic operation envelope')
    run=parse(capture(config['controller']['run']))
    need(run['origin']==origin and run['normal_endpoint']==deadline,'literal inherited original clock, no reset')
    class Loader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
        def find_spec(self,name,path=None,target=None):
            if name in captured:return importlib.util.spec_from_loader(name,self,origin=captured[name][0],is_package=name=='transport')
            return None
        def create_module(self,spec):return None
        def exec_module(self,module):
            path,body=captured[module.__name__];module.__file__=path;exec(compile(body,path,'exec'),module.__dict__)
    sys.meta_path.insert(0,Loader())
    import entry_driver
    entry_driver.start(a.operation,config,config_desc,source,files,run,count,vars(a))

if __name__=='__main__':main()
