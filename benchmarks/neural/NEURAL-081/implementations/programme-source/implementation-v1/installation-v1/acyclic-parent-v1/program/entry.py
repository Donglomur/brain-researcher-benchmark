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
    need(type(manifest)is dict and set(manifest)=={'schema','task_id','entry','modules','auxiliary','design_merge'},'exact full programme source manifest')
    need(manifest['schema']=='neural081_complete_source_manifest_v1'and manifest['task_id']=='NEURAL-081'and manifest['entry']['path']==str(Path(__file__).absolute()),'exact literal source entry')
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
    expected={'bytes':1898,'sha256':'218d395b47c77d1398b300a8118e35d03a31fbc3d05a130170bfb03844ed376e'}
    need({k:manifest['design_merge'][k]for k in expected}==expected,'actual root adopted complete V4 design merge204')
    capture(manifest['design_merge']);files.append(manifest['design_merge'])
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
