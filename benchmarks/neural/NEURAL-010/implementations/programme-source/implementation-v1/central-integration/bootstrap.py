"""Capture central, unchanged parent and actual shared campaign functions."""
import sys
import types
from pathlib import Path

NAMES = {'entry.py','bootstrap.py','common_io.py','protocol.py','authority.py',
         'registration.py','dispatch.py','driver.py','readback.py','outer_admission.py',
         'PARENT_BINDINGS.json','SHARED_SOURCE_BINDINGS.json','DEPLOYMENT_CONTRACT.md'}

def module(raw,path,name=None,**bindings):
    name=name or 'neural010_central_'+Path(path).stem
    item=types.ModuleType(name);item.__file__=str(path);item.__dict__.update(bindings)
    sys.modules[name]=item
    try:exec(compile(raw,str(path),'exec'),item.__dict__)
    except BaseException:sys.modules.pop(name,None);raise
    return item

def capture(here,source,reader,entry_start,python):
    repo=here.parents[6]
    mr=(here/'SOURCE_MANIFEST.json').relative_to(repo).as_posix()
    manifest,_=reader.json(here/'SOURCE_MANIFEST.json',131072,source)
    u.need(set(manifest)=={'schema','files','qualified'} and manifest['schema']=='neural010-central-source-v1'
           and manifest['qualified']is False and set(manifest['files'])==NAMES,'exact full central closure')
    bodies={};rows={mr:source}
    for name,pin in manifest['files'].items():
        u.relative(name);bodies[name]=reader.read(here/name,131072,pin)
        rows[(here/name).relative_to(repo).as_posix()]=pin
    fixed=u.parse(bodies['PARENT_BINDINGS.json']);external={}
    for row in fixed['runtime']+fixed['preparation']:
        name=u.relative(row['path']);pin=u.only_pin(row)
        u.need(name not in rows,'distinct fixed source members')
        external[name]=reader.read(repo/name,16777216,pin);rows[name]=pin
    parent_manifest=fixed['runtime'][0];parent_root=(repo/parent_manifest['path']).parent
    entry_name=(parent_root/'entry.py').relative_to(repo).as_posix()
    parent_entry=module(external[entry_name],parent_root/'entry.py','neural010_original_entry')
    # Original bootstrap reads its exact unchanged closure itself. Reserve all
    # those reads, including the entry reread, before invoking it.
    reserve=sum(d['bytes']+1 for d in fixed['runtime'])+rows[entry_name]['bytes']+1
    reader.reserve_read(reserve)
    root,parent_bodies,source_files,load,observed,parent_pin=parent_entry.bootstrap(parent_manifest['bytes'],parent_manifest['sha256'])
    u.need(observed==reserve and root==parent_root,'exact original captured bootstrap geometry/cost')
    wanted=[{'path':str(repo/d['path']),**u.only_pin(d)}for d in fixed['runtime'][1:]]
    u.need(source_files==wanted,'complete original ordered source roster')
    for desc in source_files:
        name=Path(desc['path']).relative_to(parent_root).as_posix()
        u.need(parent_bodies[name]==external[Path(desc['path']).relative_to(repo).as_posix()],'same originally captured bytes')
    reader.read_observed+=observed-len(fixed['runtime'])-1
    reader.hash_bytes+=observed-len(fixed['runtime'])-1
    shared=u.parse(bodies['SHARED_SOURCE_BINDINGS.json'])
    for row in shared['external']+shared['campaign_contract_files']:
        name=u.relative(row['path']);pin=u.only_pin(row)
        if name in rows:u.need(rows[name]==pin,'same repeated source');continue
        external[name]=reader.read(repo/name,131072,pin);rows[name]=pin
    gate=module(external['tools/neurobench_campaign_gate.py'],repo/'tools/neurobench_campaign_gate.py')
    vn='authoring/delivery-20261105/common/campaign-exposure-contract-v1/validate.py'
    u.need(u.pin(external[vn])==gate.VALIDATOR,'actual selected validator')
    validator=module(external[vn],repo/vn)
    gate.validator=lambda selected_repo:(validator,Path(selected_repo)/gate.CONTRACT)
    base=module(external['tools/neurobench_campaign.py'],repo/'tools/neurobench_campaign.py')
    u.need(u.pin(external['tools/neurobench_campaign_gate.py'])==base.CAMPAIGN_HELPER,'actual selected shared gate')
    base._campaign_module=lambda selected_repo=repo:gate
    env={'repo':repo,'here':here,'python':python,'entry_start':entry_start,'bodies':bodies,
         'source_pin':source,'source_rows':rows,'manifest_relative':mr,
         'entry_relative':(here/'entry.py').relative_to(repo).as_posix(),'gate':gate,'base':base,
         'parent_root':parent_root,'parent_pin':parent_pin,'parent_files':source_files,
         'parent_bodies':parent_bodies,'load':load,'bootstrap':sys.modules[__name__]}
    # All parent modules loaded here are stdlib source; no numeric producer is
    # invoked. The qualified original child retains its independent -I -B site.
    env['c']=load('common');env['parent_authority']=load('authority')
    env['parent_observer']=load('observation.observer');env['parent_driver']=load('phase_driver')
    env['process']=load('transport.process');env['bridge']=load('native').Bridge
    protocol=module(bodies['protocol.py'],here/'protocol.py',u=u);env['protocol']=protocol
    for name in ('registration','authority','driver','readback','dispatch','outer_admission'):
        env[name]=module(bodies[name+'.py'],here/(name+'.py'),u=u,p=protocol)
    reader.tick();return env
