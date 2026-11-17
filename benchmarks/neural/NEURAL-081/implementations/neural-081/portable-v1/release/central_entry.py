"""Literal isolated central route; authenticate all custom source before import."""
import argparse,hashlib,importlib.abc,importlib.util,json,os,resource,stat,sys,time
from pathlib import Path

HERE=Path(__file__).absolute().parent
REPO=HERE.parents[1]
MODULES=('n081_routing','n081_selection','n081_host','n081_readback','n081_dispatch')
BOOT_READ=128*2**20
BOOT_SOURCE=4*2**20
BOOT_MEMORY=512*2**20

def need(value,reason):
    if not value:raise ValueError(reason)

def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'duplicate source metadata key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite metadata'))

def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

class Bootstrap:
    def __init__(self):self.started=time.monotonic();self.used=0;self.body_bytes=0
    def check_clock(self):need(time.monotonic()<self.started+30,'bounded central bootstrap interval')
    def charge(self,key,amount):
        self.check_clock();need(key=='read_bytes'and type(amount)is int and amount>=0,'bootstrap read reservation')
        self.used+=amount;need(self.used<=BOOT_READ,'central bootstrap read ceiling')
    def capture(self,desc,maximum=262144):
        need(type(desc)is dict and set(desc)=={'path','bytes','sha256'}and type(desc['bytes'])is int and 0<desc['bytes']<=maximum,'bounded exact initial descriptor')
        p=Path(desc['path']);need(p.is_absolute()and str(p)==desc['path']and not str(p).startswith('//')and all(x not in('','.','..')for x in str(p).split('/')[1:])and not any(x.is_symlink()for x in(p,*p.parents)),'ordinary canonical bootstrap path')
        self.charge('read_bytes',desc['bytes']+1)
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd);need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==desc['bytes'],'exact initial file extent')
            with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(desc['bytes']+1)
            after=os.fstat(fd);named=p.lstat();keys=('st_dev','st_ino','st_size','st_mode','st_nlink','st_mtime_ns','st_ctime_ns')
            need(pin(raw)=={k:desc[k]for k in('bytes','sha256')}and all(getattr(before,k)==getattr(after,k)==getattr(named,k)for k in keys),'complete stable captured source')
        finally:os.close(fd)
        self.check_clock();return raw

NAMES=frozenset(('arrays','authority','candidate_runner','channel','closure','common','controller','custody','entry_driver','episodes','fd_protocol','grade_driver','grade_entry','grading','host_observation','issuer_entry','issuer_sandbox','issuer_worker','metrics','model_io','numeric_entry','numeric_worker','outer','outputs','preparation','preparation_driver','preparation_entry','preparation_worker','projection_broker','projection_engine','protocol','public_projection','reference_driver','reference_tools','runtime','schedule','transport','transport.common','transport.process','transport.provider','worker_bootstrap'))

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

def source_package(args,boot):
    need(HERE==REPO/'neural081/central','literal portable central layout')
    source={'path':str(HERE/'SOURCE_MANIFEST.json'),'bytes':int(args.source_bytes),'sha256':args.source_sha256}
    source_descriptor(source,REPO)
    raw=boot.capture(source,65536);boot.body_bytes=len(raw);manifest=parse(raw)
    exact(manifest,('schema','task_id','files'))
    need(manifest['schema']=='neural081_portable_central_source_v1'and manifest['task_id']=='NEURAL-081','exact local central manifest')
    local={'entry.py','BINDINGS.json','portable_gate.py',*(n+'.py'for n in MODULES)}
    need(type(manifest['files'])is dict and set(manifest['files'])==local,'complete fixed central source set')
    bodies={source['path']:raw};rows={str(Path(source['path']).relative_to(REPO)):{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}}
    def get(desc):
        source_descriptor(desc,REPO);rel=str(Path(desc['path']).relative_to(REPO));value={k:desc[k]for k in('bytes','sha256')}
        if rel in rows:
            need(same(rows[rel],value),'consistent deduplicated source');return bodies[desc['path']]
        body=boot.capture(desc);boot.body_bytes+=len(body);need(boot.body_bytes<=BOOT_SOURCE,'complete retained source bound')
        rows[rel]=value;bodies[desc['path']]=body;return body
    for name,value in manifest['files'].items():
        exact(value,('bytes','sha256'));get({'path':str(HERE/name),**value})
    need(Path(__file__).absolute()==HERE/'entry.py','genuine source-owned central entry')
    boot.charge('read_bytes',manifest['files']['entry.py']['bytes'])
    bindings=parse(bodies[str(HERE/'BINDINGS.json')]);exact(bindings,('schema','task_id','parent_manifest','construction','source_rows','tools'))
    need(bindings['schema']=='neural081_portable_central_bindings_v1'and bindings['task_id']=='NEURAL-081','fixed local task bindings')
    metadata={'neural081/PORTABLE_RELEASE.json','neural081/PUBLIC_ORIGIN_MAP.json','neural081/parent/CONSTRUCTION.json','neural081/parent/SOURCE_MANIFEST.json','neural081/central/BINDINGS.json','neural081/central/SOURCE_MANIFEST.json'}
    expected=python_paths()|CONTEXT_PATHS|metadata
    need(len(expected)==72,'literal complete72 source closure')
    preceding=expected-{str((HERE/name).relative_to(REPO))for name in local}-{'neural081/central/SOURCE_MANIFEST.json'}
    need(type(bindings['source_rows'])is list and len(bindings['source_rows'])==63,'exact acyclic preceding63 source rows')
    for row in bindings['source_rows']:source_descriptor(row,REPO)
    need([r['path']for r in bindings['source_rows']]==sorted(str(REPO/p)for p in preceding),'literal sorted63 pre-binding source locators')
    for row in bindings['source_rows']:get(row)
    need(set(rows)==expected,'exact complete source membership, no subset or unrelated body')
    parent_source=bindings['parent_manifest'];source_descriptor(parent_source,REPO)
    need(parent_source['path']==str(REPO/'neural081/parent/SOURCE_MANIFEST.json'),'genuine local parent manifest')
    parent=parse(get(parent_source));exact(parent,('schema','task_id','entry','modules','auxiliary','construction'))
    need(parent['schema']=='neural081_portable_parent_source_v1'and parent['task_id']=='NEURAL-081','exact complete local parent')
    paths=execution_paths();need(parent['entry']['path']==str(REPO/paths['entry']),'genuine local parent entry')
    need(type(parent['modules'])is list and [r.get('name')for r in parent['modules']]==sorted(NAMES),'full source-owned ordered41 parent modules')
    execution=[parent['entry']]
    captured={name:(str(HERE/(name+'.py')),bodies[str(HERE/(name+'.py'))])for name in MODULES}
    for row in parent['modules']:
        exact(row,('name','source'));name=row['name'];need(row['source']['path']==str(REPO/paths['modules'][name])and name not in captured,'original module name and genuine location')
        body=get(row['source']);execution.append(row['source']);captured[name]=(row['source']['path'],body)
    need(type(parent['auxiliary'])is list and len(parent['auxiliary'])==2,'both independent numerical sources')
    for role,row in zip(('r1','r2'),parent['auxiliary']):
        exact(row,('role','source'));need(row['role']==role and row['source']['path']==str(REPO/paths['auxiliary'][role]),'exact numerical source role/location')
        get(row['source']);execution.append(row['source'])
    need(same(parent['construction'],bindings['construction']),'same acyclic parent construction')
    construction,release,active=validate_construction(bindings['construction'],REPO,get,execution)
    execution.append(bindings['construction']);need(len(execution)==45 and len({r['path']for r in execution})==45,'complete relocated execution45')
    for desc in active.values():get(desc)
    exact(bindings['tools'],('campaign','campaign_gate'))
    for alias,key,name in(('n081_shared_campaign','campaign','neurobench_campaign.py'),('n081_shared_gate','campaign_gate','neurobench_campaign_gate.py')):
        desc=bindings['tools'][key];need(desc['path']==str(REPO/'tools'/name),'unchanged shared helper literal location')
        body=get(desc);captured[alias]=(desc['path'],body)
    captured['n081_portable_gate']=(str(HERE/'portable_gate.py'),bodies[str(HERE/'portable_gate.py')])
    need(not any(name in sys.modules for name in captured),'no ambient custom source')
    class Loader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
        def find_spec(self,name,path=None,target=None):
            if name in captured:return importlib.util.spec_from_loader(name,self,origin=captured[name][0],is_package=name=='transport')
            return None
        def create_module(self,spec):return None
        def exec_module(self,module):
            path,body=captured[module.__name__];module.__file__=path;exec(compile(body,path,'exec'),module.__dict__)
    sys.meta_path.insert(0,Loader())
    return {'repo':REPO,'here':HERE,'source':source,'manifest':manifest,'bindings':bindings,'bodies':bodies,'rows':rows,'parent':parent,'parent_source':parent_source,'parent_files':execution,'construction':bindings['construction'],'bootstrap':boot}

def main():
    parser=argparse.ArgumentParser()
    for key in('condition','program','output','review','other-reserve-bytes','source-bytes','source-sha256'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args();need(args.condition in('default','full10_instructed_excerpt_v1'),'one complete-study alias')
    need(sys.flags.isolated==1 and sys.flags.no_site==1 and sys.dont_write_bytecode,'actual isolated no-site central launch')
    need(Path.cwd()==REPO and sys.platform=='linux','qualified Linux central cwd/platform')
    soft,hard=resource.getrlimit(resource.RLIMIT_AS);need(hard==resource.RLIM_INFINITY or hard>=BOOT_MEMORY,'bootstrap address-space capacity')
    resource.setrlimit(resource.RLIMIT_AS,(BOOT_MEMORY,hard))
    boot=Bootstrap();ctx=source_package(args,boot)
    import n081_dispatch
    result=n081_dispatch.execute(args,ctx)
    print(json.dumps(result,sort_keys=True,separators=(',',':')),flush=True)
    ctx['budget'].check_clock()

if __name__=='__main__':main()
