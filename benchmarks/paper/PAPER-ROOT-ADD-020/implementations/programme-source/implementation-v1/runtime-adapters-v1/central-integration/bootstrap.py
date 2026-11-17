"""Closed source capture; only stdlib metadata modules execute before routing."""
import sys
import types
from pathlib import Path

NAMES={'entry.py','observer_entry.py','bootstrap.py','common_io.py','registration.py','authority.py',
       'dispatch.py','transcript.py','artifacts.py','external.py','credential.py',
       'ROOT_CONTEXT.json','SHARED_SOURCE_BINDINGS.json','DEPLOYMENT_CONTRACT.md',
       'source-capture/capture.py','source-capture/BINDING.json'}

def module(raw,path,name=None,**bindings):
    name=name or '_paper020_central_'+Path(path).stem
    m=types.ModuleType(name);m.__file__=str(path);m.__dict__.update(bindings);sys.modules[name]=m
    try:exec(compile(raw,str(path),'exec'),m.__dict__)
    except BaseException:sys.modules.pop(name,None);raise
    return m

def capture(here,source,reader,entry_start,python):
    repo=here.parents[7];mrel=(here/'SOURCE_MANIFEST.json').relative_to(repo).as_posix()
    manifest,_=reader.json(here/'SOURCE_MANIFEST.json',131072,source)
    u.need(manifest.get('schema')=='paper020_central_source_v1' and set(manifest.get('files',{}))==NAMES,'complete central source closure required')
    bodies={};rows={mrel:source}
    for n,p in manifest['files'].items():
        u.relative(n);bodies[n]=reader.read(here/n,131072,p);rows[(here/n).relative_to(repo).as_posix()]=p
    helper=module(bodies['source-capture/capture.py'],here/'source-capture/capture.py')
    # Inventory pins are source metadata. Actual parent capture occurs only after
    # the fixed registry/preference gate, before any scientific operands/imports.
    binding=u.parse(bodies['source-capture/BINDING.json']);pins={}
    for p in binding['files']:
        n=u.relative(p['source_path']);pins[n]=u.only_pin(p);rows[n]=pins[n]
    adapter_pin=next(u.only_pin(p)for p in binding['files']if p['staged_path'].endswith('/ADAPTER_SOURCE_MANIFEST.json'))
    parent={'pins':pins,'members':None,'scientific_source_digest':helper.SCIENTIFIC_SOURCE_DIGEST,'adapter_manifest_pin':adapter_pin}
    context=u.parse(bodies['ROOT_CONTEXT.json']);proof=context['root_receipt']
    raw=reader.read(repo/u.relative(proof['path']),131072,u.only_pin(proof));rows[proof['path']]=u.only_pin(proof)
    receipt=u.parse(raw)
    u.need(receipt.get('batch')==123 and receipt['integration']['commit']==context['root_merge_commit']
           and receipt['integration']['parents'][1]==context['agent_commit'] and receipt['integration']['cleanup']=='complete'
           and receipt['completion']['exit_code']==0,'actual root natural source-merge receipt required')
    external={};bindings=u.parse(bodies['SHARED_SOURCE_BINDINGS.json'])
    for p in bindings['external']+bindings['campaign_contract_files']:
        n=u.relative(p['path']);expected=u.only_pin(p)
        if n in rows:u.need(rows[n]==expected,'consistent source overlap');continue
        external[n]=reader.read(repo/n,131072,expected);rows[n]=expected
    gate=module(external['tools/neurobench_campaign_gate.py'],repo/'tools/neurobench_campaign_gate.py')
    vn='authoring/delivery-20261105/common/campaign-exposure-contract-v1/validate.py'
    u.need(u.pin(external[vn])==gate.VALIDATOR,'actual campaign validator identity')
    validator=module(external[vn],repo/vn);gate.validator=lambda selected_repo:(validator,Path(selected_repo)/gate.CONTRACT)
    base=module(external['tools/neurobench_campaign.py'],repo/'tools/neurobench_campaign.py')
    u.need(u.pin(external['tools/neurobench_campaign_gate.py'])==base.CAMPAIGN_HELPER,'actual campaign helper identity')
    base._campaign_module=lambda selected_repo=repo:gate
    env={'repo':repo,'here':here,'python':python,'source_pin':source,'source_rows':rows,'bodies':bodies,
         'parent':parent,'capture_helper':helper,'gate':gate,'base':base,'entry_start':entry_start,'bootstrap':sys.modules[__name__],
         'manifest_relative':mrel,'entry_relative':(here/'entry.py').relative_to(repo).as_posix()}
    env['interface']={'path':here.relative_to(repo).as_posix(),'source':{'path':mrel,**source}}
    for name in ('registration','authority','dispatch','transcript','artifacts','external','credential'):
        env[name]=module(bodies[name+'.py'],here/(name+'.py'),u=u)
    return env

def capture_parent(env,reader):
    helper=env['capture_helper'];reader.reserve_read(helper.REQUIRED_READ_LIMIT_BYTES)
    try:
        captured=helper.capture_source(str(env['repo']),read_limit_bytes=helper.REQUIRED_READ_LIMIT_BYTES,
                                      origin_ns=reader.origin,deadline_ns=reader.deadline)
    except helper.CaptureError as error:
        reader.read_observed+=error.read_bytes;reader.hash_bytes+=error.read_bytes;raise
    reader.read_observed+=captured.read_bytes;reader.hash_bytes+=captured.read_bytes
    actual={p.source_path:{'bytes':p.size_bytes,'sha256':p.sha256}for p in captured.members}
    u.need(actual==env['parent']['pins'] and len(captured.members)==34,'complete exact captured parent source')
    env['parent']['members']=captured.members;reader.tick()
