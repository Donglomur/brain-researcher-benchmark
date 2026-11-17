"""Literal isolated central route; authenticate all custom source before import."""
import argparse,hashlib,importlib.abc,importlib.util,json,os,resource,stat,sys,time
from pathlib import Path

HERE=Path(__file__).absolute().parent
REPO=HERE.parents[7]
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

def source_package(args,boot):
    source={'path':str(HERE/'SOURCE_MANIFEST.json'),'bytes':int(args.source_bytes),'sha256':args.source_sha256}
    raw=boot.capture(source,65536);boot.body_bytes=len(raw);manifest=parse(raw)
    need(type(manifest)is dict and set(manifest)=={'schema','task_id','files'}and manifest['schema']=='neural081_central_source_manifest_v1'and manifest['task_id']=='NEURAL-081','exact central manifest')
    need(type(manifest['files'])is dict and set(manifest['files'])=={'entry.py','BINDINGS.json',*(n+'.py'for n in MODULES)},'complete fixed central source set')
    bodies={str(HERE/'SOURCE_MANIFEST.json'):raw};rows={str((HERE/'SOURCE_MANIFEST.json').relative_to(REPO)):pin(raw)}
    def get(desc):
        relative=str(Path(desc['path']).relative_to(REPO));value={k:desc[k]for k in('bytes','sha256')}
        if relative in rows:need(rows[relative]==value,'consistent deduplicated source');return bodies[desc['path']]
        body=boot.capture(desc);boot.body_bytes+=len(body);need(boot.body_bytes<=BOOT_SOURCE,'complete retained source bound');rows[relative]=value;bodies[desc['path']]=body;return body
    for name,value in manifest['files'].items():
        need(type(value)is dict and set(value)=={'bytes','sha256'},'central member descriptor');get({'path':str(HERE/name),**value})
    need(bodies[str(HERE/'entry.py')]and Path(__file__).absolute()==HERE/'entry.py','genuine source-owned central entry')
    boot.charge('read_bytes',manifest['files']['entry.py']['bytes'])
    bindings=parse(bodies[str(HERE/'BINDINGS.json')]);need(bindings['schema']=='neural081_central_bindings_v1'and bindings['task_id']=='NEURAL-081','fixed task bindings')
    for row in bindings['source_rows']:get(row)
    acceptance=parse(bodies[bindings['root_acceptance']['path']]);merge=parse(bodies[bindings['root_merge']['path']])
    need(acceptance['schema']=='root_corrected_parent_and_complete_adapter_design_acceptance_v1'and acceptance['scientific_qualification_added']is False,'actual corrected parent/design root adoption')
    need(merge['schema']=='root_state_recovered_reviewed_source_merge_v1'and merge['batch']==222 and type(merge['batch'])is int and merge['source_only']is True and merge['scientific_qualification_added']is False,'exact root-selected state-recovered source integration')
    need(merge['original_exit_observed']is None and merge['completion_output_available']is False,'original merge-tool exit remains unavailable, never invented')
    need(merge['merge_commit']==bindings['root_merge_commit']=='ed3653904b9988a0356191aa03a6998710f557ab'and merge['agent_commit']==bindings['parent_agent_commit']=='c528f49217d76802bf736d17155aca03e5aefbf4'and merge['parents']==['80eb6f6a8441f1594191eecd0d72ec39907b126f',bindings['parent_agent_commit']],'exact recovered corrected-parent source lineage')
    need(all(type(merge[k])is int and merge[k]==v for k,v in [('verified_members',97),('changed_paths',97),('verified_bytes',942985)]),'complete recovered source extent')
    recovery=merge['recovery_observations'];need(all(recovery.get(k)is True for k in('all_exact_reviewed_committed_blobs_verified','changed_paths_within_allowlist','no_active_queue_process_observed','no_transaction_or_owned_locks','shared_index_equals_HEAD')),'root independently checked complete recovered source state')
    queue=bindings['repair_union'];need(merge['reviewed_manifest']=={'path':str(Path(queue['path']).relative_to(REPO)),'bytes':queue['bytes'],'sha256':queue['sha256']},'actual complete reviewed repair union')
    parent_source=bindings['parent_manifest'];parent=parse(bodies[parent_source['path']]);proposal=parse(bodies[bindings['parent_proposal']['path']])
    need(parent['schema']=='neural081_complete_source_manifest_v1'and parent['task_id']=='NEURAL-081'and len(parent['modules'])==41,'original full parent manifest')
    parent_root=Path(parent_source['path']).parent
    need(acceptance['parent_manifest']=={'path':str(Path(parent_source['path']).relative_to(REPO)),'bytes':parent_source['bytes'],'sha256':parent_source['sha256']}and acceptance['parent_proposal']=={'path':str(Path(bindings['parent_author_proposal']['path']).relative_to(REPO)),'bytes':bindings['parent_author_proposal']['bytes'],'sha256':bindings['parent_author_proposal']['sha256']},'actual root adoption binds corrected source, not historical cyclic parent')
    need(proposal['owned_prefix']==str(parent_root.relative_to(REPO))and len(proposal['files'])==63,'full corrected63 parent construction')
    for name,value in proposal['files'].items():need(rows.get(str((parent_root/name).relative_to(REPO)))==value,'every corrected parent body in closure')
    execution=[parent['entry'],*[r['source']for r in parent['modules']],*[r['source']for r in parent['auxiliary']],parent['design_merge']]
    need(len(execution)==45 and len({d['path']for d in execution})==45,'exact complete original execution closure')
    for desc in execution:need(rows.get(str(Path(desc['path']).relative_to(REPO)))=={k:desc[k]for k in('bytes','sha256')},'original execution identity in complete freeze')
    need(parent['entry']['path']==str(parent_root/'program/entry.py'),'genuine corrected entry location')
    captured={name:(str(HERE/(name+'.py')),bodies[str(HERE/(name+'.py'))])for name in MODULES}
    for row in parent['modules']:
        name=row['name'];relative='transport/__init__.py'if name=='transport'else name.replace('.','/')+'.py'
        need(row['source']['path']==str(parent_root/'program'/relative)and name not in captured,'original module name/location');captured[name]=(row['source']['path'],bodies[row['source']['path']])
    for name,key in [('n081_shared_gate','campaign_gate'),('n081_shared_campaign','campaign')]:
        desc=bindings['tools'][key];captured[name]=(desc['path'],bodies[desc['path']])
    need(not any(name in sys.modules for name in captured),'no ambient custom source')
    class Loader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
        def find_spec(self,name,path=None,target=None):
            if name in captured:return importlib.util.spec_from_loader(name,self,origin=captured[name][0],is_package=name=='transport')
            return None
        def create_module(self,spec):return None
        def exec_module(self,module):
            path,body=captured[module.__name__];module.__file__=path;exec(compile(body,path,'exec'),module.__dict__)
    sys.meta_path.insert(0,Loader())
    return {'repo':REPO,'here':HERE,'source':source,'manifest':manifest,'bindings':bindings,'bodies':bodies,'rows':rows,'parent':parent,'parent_source':parent_source,'parent_files':execution,'bootstrap':boot}

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
