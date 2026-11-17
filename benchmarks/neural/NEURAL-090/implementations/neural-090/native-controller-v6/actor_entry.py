"""Fixed in-container entry. Only this invocation's sources and view are mounted.

This entry is executed by an immutable qualified image with -I -B; every local
project module is captured/compiled, never loaded through a pyc cache.
"""
import hashlib,json,os,sys,types
from pathlib import Path

def load_native():
    root=Path('/launcher');raw=(root/'SOURCE.json').read_bytes();lock=json.loads(raw)
    package=types.ModuleType('n090native');package.__path__=[str(root)];sys.modules['n090native']=package
    for name in ('common','source_loader'):
        body=(root/(name+'.py')).read_bytes();row=lock[name+'.py']
        if len(body)!=row['bytes']or hashlib.sha256(body).hexdigest()!=row['sha256']:raise ValueError('fixed launcher source identity')
        mod=types.ModuleType('n090native.'+name);mod.__package__='n090native';mod.__file__=str(root/(name+'.py'));sys.modules[mod.__name__]=mod
        exec(compile(body,mod.__file__,'exec',dont_inherit=True),mod.__dict__)
    return sys.modules['n090native.common'],sys.modules['n090native.source_loader']

def main():
    if not sys.flags.isolated or not sys.dont_write_bytecode or len(sys.argv)!=2:raise ValueError('fixed isolated launcher argv')
    c,loader=load_native();cfg=c.parse(Path(sys.argv[1]).read_bytes());c.fields(cfg,('kind','seed','limits','device','view','runtime','candidate','round','response'))
    end=__import__('time').monotonic()+cfg['limits']['wall_seconds'];budget=c.Budget(cfg['limits']['read_bytes'],cfg['limits']['write_bytes'],end)
    if cfg['kind']=='reference':
        manifest=c.parse(c.capture('/source/RUNTIME_SOURCE.json',budget,cfg['runtime']['bytes'],cfg['runtime']))
        loader.Captured('/source',manifest['members'],budget).install()
        from broad090.worker import reference
        from programme.contracts import Asset,Pin
        asset=reference('/source',Asset('RUNTIME_SOURCE.json',Pin.parse(cfg['runtime'])),'/view',Asset.parse(cfg['view']),'/work/final',cfg['seed'],cfg['device'],cfg['limits'])
        action={'kind':'finish','prediction':asset.json() if hasattr(asset,'json')else{'path':asset.path,**asset.pin.json()}}
    else:
        c.need(cfg['kind']=='candidate','closed actor role')
        body=c.capture('/candidate/program.py',budget,cfg['candidate']['bytes'],cfg['candidate'])
        namespace={'__name__':'__n090_candidate__','__file__':'/candidate/program.py'}
        exec(compile(body,'/candidate/program.py','exec',dont_inherit=True),namespace)
        c.need(callable(namespace.get('next_action')),'fixed next_action(context) candidate ABI')
        # No host path, global row map, query label, other arm or prior invocation.
        action=namespace['next_action']({'view_root':'/view','manifest':cfg['view'],'work_root':'/work','output_root':'/work/final','seed':cfg['seed'],'limits':cfg['limits'],'round':cfg['round'],'response':cfg['response']})
    raw=c.encoded(action);c.need(len(raw)<=65536,'bounded action frame')
    c.save('/work/action-'+str(cfg['round'])+'.json',raw,budget,0o600)
if __name__=='__main__':main()
