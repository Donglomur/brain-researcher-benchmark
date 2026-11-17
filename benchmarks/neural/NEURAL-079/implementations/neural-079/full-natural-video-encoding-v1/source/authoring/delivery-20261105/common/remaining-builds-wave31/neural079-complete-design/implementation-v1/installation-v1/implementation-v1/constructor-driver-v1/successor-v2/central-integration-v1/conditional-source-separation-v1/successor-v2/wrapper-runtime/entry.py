"""Inactive named NEURAL079 route through the unchanged real shared CLI gates.

Deployment supplies the earlier clean environment bootstrap metadata. No
operation receives a restarted clock or a fabricated deployment budget.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

TASK='NEURAL-079'
CONDITION='full_natural_video_encoding_v1'
REGISTRY='benchmarks/neuroscience/neural-079/manifest.json'
PREFIX='authoring/delivery-20261105/common/remaining-builds-wave31/neural079-complete-design/implementation-v1/installation-v1/implementation-v1/constructor-driver-v1/successor-v2/central-integration-v1/conditional-source-separation-v1/successor-v2'
PRODUCTION_ENTRY='authoring/delivery-20261105/common/remaining-builds-wave31/neural079-complete-design/implementation-v1/installation-v1/implementation-v1/source-successor-v2/central-runtime/nb079_central_entry.py'
IO_PIN={'bytes':11694,'sha256':'d1c764658deb5fa546532b642c4237a092ffabf77701517bdd00e974d5348ee9'}

DEFERRED_CAMPAIGN_DEPENDENCIES={'artifacts-build/dmfc096-scoring-materialize-002/packet/TASK.md': {'bytes': 6234, 'sha256': 'f6b34caab8222d682afe7168c41ee3180d0374d06f6637d48c17f1738481e54a'}, 'authoring/delivery-20261105/dmfc/NEURAL-095/delivery_manifest.json': {'bytes': 11090, 'sha256': '92333fc46bf0e23671c154f89b7a8a64dc3c2c82b03ebb2d48a3289173713ec6'}, 'authoring/delivery-20261105/dmfc/NEURAL-095/public/TASK.md': {'bytes': 2559, 'sha256': 'fcb48f9b1bf748b66a883b9a459b031ed1e00536145dbf42598a99008e7f54bd'}, 'authoring/delivery-20261105/dmfc/NEURAL-096/delivery_manifest.json': {'bytes': 12649, 'sha256': 'aaeaa0b88b1ac9c1b332c1420bf54f66e13efa1955ea1956ae3127ecc594cf09'}, 'authoring/delivery-20261105/neural023/delivery_manifest.json': {'bytes': 12072, 'sha256': '5cd4aab32a9a9a6513acd8ecf52b36eeb0766751a697c913f5a25f42a00f045d'}, 'authoring/delivery-20261105/neural023/public/TASK.md': {'bytes': 4394, 'sha256': '87dbea378b22663e0296fbf35ea665faebab74470fe90d021e74eac349cb4352'}, 'authoring/delivery-20261105/rtt-forecast/delivery_manifest.json': {'bytes': 13240, 'sha256': 'a3aed33412b4ecaecf691f2daf896b2a5661230ac4cf46d6d1d47fd029fcb017'}, 'authoring/delivery-20261105/rtt-forecast/public/TASK.md': {'bytes': 4090, 'sha256': '567ef08695a032a0972057f87bfaa4e8d0d90d23495a825110038fbdc9ea4eb8'}, 'docs/neuroscience-benchmarks/build/exposure_audit.json': {'bytes': 199521, 'sha256': '1fb6a27f54db6fd66177a4e26f139faee999fb92aed92b9df92286fdf7a00b66'}, 'tools/build_neuro_exposure_audit.py': {'bytes': 10036, 'sha256': 'a3e041aa1d48cdd939046460e6c903d726d3a66c56913cfff2286cd95c7437a1'}}

def need(ok,why):
    if not ok:raise ValueError(why)
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
def parse(raw):
    def pairs(items):
        value={}
        for k,v in items:need(k not in value,'duplicate wrapper JSON field');value[k]=v
        return value
    def bad(_):raise ValueError('nonfinite wrapper metadata')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
def clocks(raw):
    x=parse(raw);need(type(x) is dict and set(x)=={'origin','scientific','closeout','outer'},'one original four-clock environment value')
    v=[x[k] for k in ('origin','scientific','closeout','outer')]
    need(all(type(k) is int and k>=0 for k in v) and all(a<b for a,b in zip(v,v[1:])),'strict original integer clock')
    need(canonical(x).decode('ascii')==raw,'canonical original-clock environment bytes');return x
def tick(clock,phase='scientific'):
    n=time.monotonic_ns();need(clock['origin']<=n<clock[phase],'original wrapper cutoff');return n
def module(raw,path,name,**bindings):
    m=types.ModuleType(name);m.__file__=str(path);m.__dict__.update(bindings)
    exec(compile(raw,str(path),'exec'),m.__dict__);return m
def cleanup(ops,first=None):
    for label,fn in ops:
        try:fn()
        except BaseException as error:
            if first is None:first=error
            else:first.nb079_wrapper_secondary=list(getattr(first,'nb079_wrapper_secondary',[]))+[{'phase':label,'type':type(error).__name__}]
    return first

def initial_io(root,clock,selected):
    path=root/PREFIX/'wrapper-runtime/common_io.py';parent=None;fd=None;first=None;parts=[];count=0
    need(selected['allocation']['source_read_bytes']>=IO_PIN['bytes']+1,'earlier actual startup source capacity')
    try:
        tick(clock);parent=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        for name in path.parent.parts[1:]:
            child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);old,parent=parent,child;os.close(old)
        tick(clock);fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent);a=os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==IO_PIN['bytes'],'exact ordinary captured metadata helper')
        while True:
            tick(clock);b=os.read(fd,min(65536,IO_PIN['bytes']-count+1))
            if not b:break
            count+=len(b);need(count<=IO_PIN['bytes'],'helper extent');parts.append(b)
        raw=b''.join(parts);stamp=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
        need(pin(raw)==IO_PIN and stamp(a)==stamp(os.fstat(fd))==stamp(os.stat(path.name,dir_fd=parent,follow_symlinks=False)),'complete stable actual helper bytes')
    except BaseException as error:first=error
    finally:
        first=cleanup(([('initial helper close',lambda:os.close(fd))]if fd is not None else[])+([('initial helper directory close',lambda:os.close(parent))]if parent is not None else[]),first)
    if first is not None:first.nb079_wrapper_bootstrap={'attempted_source_bytes':IO_PIN['bytes']+1,'returned_bytes':count};raise first
    tick(clock);return module(raw,path,'_nb079_wrapper_io'),count

def capture(root,args,reader,u):
    manifest_path=PREFIX+'/SOURCE_MANIFEST.json'
    manifest,source_pin=reader.json(root/manifest_path,2097152,{'bytes':args.source_bytes,'sha256':args.source_sha256})
    need(type(manifest) is dict and set(manifest)=={'schema','files','qualified'} and manifest['schema']=='nb079_complete_central_source_v1' and manifest['qualified'] is False,'exact fixed complete source manifest')
    rows=manifest['files'];need(type(rows) is dict and 1<=len(rows)<=511 and sum(p['bytes'] for p in rows.values())<=16777216-source_pin['bytes'],'unchanged complete shared512file/16MiB envelope')
    # Classify before reading any declared member body. The complete current
    # contract's ten dependencies are immutable descriptors, not source inputs.
    need(not(set(rows)&set(DEFERRED_CAMPAIGN_DEPENDENCIES)),
         'deferred campaign dependencies cannot enter the source manifest')
    shared_name=PREFIX+'/wrapper-runtime/SHARED_SOURCE_BINDINGS.json'
    contract_name='authoring/delivery-20261105/common/campaign-exposure-contract-v2-bounded-work/SOURCE_MANIFEST.json'
    bodies={}
    for name in(shared_name,contract_name):
        bodies[name]=reader.read(root/name,16777216,u.only_pin(rows[name]))
    shared=u.parse(bodies[shared_name]);contract=u.parse(bodies[contract_name])
    deferred={row['path']:{k:row[k]for k in('bytes','sha256')}for row in contract['dependencies']}
    need(deferred==DEFERRED_CAMPAIGN_DEPENDENCIES==shared.get('deferred_campaign_dependencies'),
         'exact complete deferred contract dependency descriptors')
    need(all(d['path']not in deferred for d in shared['external']+shared['campaign_contract_files']),
         'ordinary shared source roster excludes deferred dependencies')
    for name,p in rows.items():
        u.relative(name)
        if name not in bodies:bodies[name]=reader.read(root/name,16777216,u.only_pin(p))
    source_rows={**rows,manifest_path:source_pin}
    for d in shared['external']+shared['campaign_contract_files']:
        need(source_rows[d['path']]==u.only_pin(d),'every actual shared function and campaign contract source pinned')
    gate=module(bodies['tools/neurobench_campaign_gate_bounded_v3.py'],root/'tools/neurobench_campaign_gate_bounded_v3.py','_nb079_actual_shared_gate')
    vn='authoring/delivery-20261105/common/campaign-exposure-contract-v2-bounded-work/validate.py'
    need(pin(bodies[vn])==gate.VALIDATOR,'exact shared validator source')
    validator=module(bodies[vn],root/vn,'_nb079_actual_campaign_validator')
    def captured_validator(chosen_root, *, view=None):
        need(Path(chosen_root).absolute()==root and view is None,'fixed actual root; no replacement source view')
        return validator,root/gate.CONTRACT
    gate.validator=captured_validator
    base=module(bodies['tools/neurobench_campaign_bounded_v3.py'],root/'tools/neurobench_campaign_bounded_v3.py','_nb079_actual_base_dispatch')
    need(pin(bodies['tools/neurobench_campaign_gate_bounded_v3.py'])==base.CAMPAIGN_HELPER,'actual base dispatcher gate binding')
    def captured_gate(chosen_root=root, *, view=None):
        need(Path(chosen_root).absolute()==root and view is None,'fixed actual root; no replacement gate view')
        return gate
    base._campaign_module=captured_gate
    return {'root':root,'u':u,'reader':reader,'bodies':bodies,'source_rows':source_rows,'source_pin':source_pin,'manifest_path':manifest_path,'gate':gate,'base':base,'deferred_campaign_dependencies':deferred}

def qualify(env):
    root=env['root'];u=env['u'];reader=env['reader']
    doc,registry_pin=reader.json(root/REGISTRY,131072)
    need(doc.get('id')==TASK and doc.get('program_execution') is None,'named-only source route; no generic default programme')
    meta=doc.get('program_conditions',{}).get(CONDITION)
    need(type(meta) is dict and meta.get('verification',{}).get('status')=='passed' and meta.get('scope')=='complete_natural_video_EEG_encoding','independent complete named-condition qualification required before program operand')
    need(meta.get('deferred_campaign_dependencies')==env['deferred_campaign_dependencies'],'qualified route retains exact deferred contract descriptors')
    frozen=meta['source_freeze'];u.relative(frozen['path'])
    freeze,_=reader.json(root/frozen['path'],2097152,u.only_pin(frozen))
    deployment=meta['deployment_source_closure'];need(type(deployment) is dict and deployment and not(set(deployment)&set(env['source_rows'])),'separate exact deployment closure')
    need(not(set(deployment)&set(env['deferred_campaign_dependencies'])),'deferred campaign dependency is not a deployment source')
    expected={**env['source_rows'],**deployment}
    need(len(expected)<=512 and sum(p['bytes'] for p in expected.values())<=16777216 and freeze.get('schema')=='nb079_complete_central_qualification_v1' and freeze.get('task_id')==TASK and freeze.get('files')==expected,'complete current task/shared/deployment source qualification')
    entry=meta['entrypoint'];index=env['gate'].python_launch(entry['argv'])
    need(entry['argv'][index]==PREFIX+'/wrapper-runtime/entry.py' and entry.get('working_directory')=='.' and entry['sha256']==env['source_rows'][PREFIX+'/wrapper-runtime/entry.py']['sha256'],'literal actual wrapper/source entry')
    # The real helper performs its own captures; charge their admitted complete
    # bounded reads before invoking it, without pretending to observe OS I/O.
    reader.reserve_read(4*(2097152+1)+2*(16777216+1)+sum(p['bytes']+1 for p in expected.values()))
    selected={**doc,'program_execution':meta}
    need(env['base'].verified_program_runtime(root/REGISTRY,selected,root) is True,'actual unchanged shared qualification refused')
    for name,p in deployment.items():u.relative(name);reader.read(root/name,16777216,u.only_pin(p))
    need(type(meta.get('source_merge')) is str and re.fullmatch('[a-f0-9]{40}',meta['source_merge']),'actual separately installed/qualified implementation merge required')
    return {'doc':doc,'selected':selected,'meta':meta,'registry_pin':registry_pin,'qualified_sources':expected}

def campaign(env,registered,review,args):
    gate=env['gate'];reader=env['reader'];root=env['root'];u=env['u']
    reader.reserve_read(gate.CAPTURE_CAP+gate.VALIDATOR['bytes']+1+gate.PREFERENCE_READ_CAP)
    request=review['campaign_request'];u.descriptor(request)
    first=gate.admit(root,TASK,'run',CONDITION,request['path'],request['sha256'],review['work_sha256'])
    need(first['request']==u.only_pin(request),'exact independent campaign request')
    route=gate.preferred_route(root,TASK,'run',CONDITION,review['work_sha256'],(root/REGISTRY,registered['doc']))
    need(route.get('status')=='preferred_source_bound' and route['interface']=={'path':PREFIX,'source':{'path':env['manifest_path'],**env['source_pin']}} and route['registration']=={'path':REGISTRY,**registered['registry_pin']},'actual exact preferred source named route')
    index=route['wrapper_index'];template=route['registered_argv'];values={'{program}':args.program,'{review}':args.review,'{output}':args.output,'{other_reserve_bytes}':str(args.other_reserve_bytes)}
    command=[sys.executable,*template[1:index],route['wrapper_absolute'],*[values.get(v,v)for v in template[index+1:]]]
    need(command==list(sys.orig_argv) and os.getcwd()==str(root),'literal original shared-CLI invocation/cwd')
    first['preferred_program_route']=route;first['metadata_read_charge_bytes']+=route['metadata_read_charge_bytes'];return first,command

def executing_environment(env,command):
    """Concrete local guard, after separate qualification and before execution."""
    prior=env.setdefault('executing_environment_prefix',[])
    event={'attempt':len(prior)+1,'attempted':True,'completed':False,
           'filesystem_stat_costs_unmeasured':True,'qualification_granted':False}
    prior.append(event)
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
         and not sys.flags.optimize,'actual isolated unoptimized process')
    # runtime_environment accepts the constructed absolute wrapper argv;
    # python_source_launch is deliberately restricted to registered relative paths.
    result=env['gate'].runtime_environment(command)
    need(result['pycache_freshness_checked'] is True and result['runtime_qualification_granted'] is False,
         'actual current-host guard, never scientific authorization')
    cache=command[5][len('pycache_prefix='):]
    need(sys.pycache_prefix==cache and sys._xoptions.get('pycache_prefix')==cache,
         'actual interpreter cache prefix equals selected command')
    event.update(completed=True,result=result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser()
    for n in ('program','review','output','source-sha256'):parser.add_argument('--'+n,required=True)
    for n in ('source-bytes','other-reserve-bytes'):parser.add_argument('--'+n,type=int,required=True)
    args=parser.parse_args(argv);reader=None;env=None;u=None;result=None;first=None
    try:
        need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize,'exact isolated/no-site/no-bytecode entry')
        clock_raw=os.environ.get('NEUROBENCH_N079_ORIGINAL_CLOCK','');need(0<len(clock_raw)<=1024,'bounded earlier original clock metadata')
        original=clocks(clock_raw);tick(original)
        boot_raw=os.environ.get('NEUROBENCH_N079_ENTRY_BOOTSTRAP','');need(0<len(boot_raw)<=32768,'bounded earlier explicit bootstrap limits')
        selected=parse(boot_raw)
        need(canonical(selected).decode('ascii')==boot_raw and selected['schema']=='nb079_entry_bootstrap_v2' and selected['role']=='central_preparation' and selected['original_clock']==original,'same earlier source-owned wrapper/central row')
        root=Path.cwd().absolute();need(Path(__file__).absolute()==root/PREFIX/'wrapper-runtime/entry.py','actual fixed repository wrapper path')
        u,observed=initial_io(root,original,selected)
        reader=u.Reader(read_limit=selected['allocation']['source_read_bytes'],write_limit=selected['allocation']['write_bytes'],deadline=original['scientific'])
        reader.reserve_read(IO_PIN['bytes']+1);reader.read_observed=observed;reader.hash_bytes=observed
        env=capture(root,args,reader,u);registered=qualify(env)
        review,review_pin=reader.json(args.review,32768)
        fields={'schema','task_id','condition','program','source_manifest','source_merge','original_clock','entry_bootstrap','campaign_request','work_sha256','actual_program_path','actual_review_path','actual_output_path','other_reserve_bytes','environment_pin'}
        need(type(review) is dict and set(review)==fields and review['schema']=='nb079_complete_execution_review_v1' and review['task_id']==TASK and review['condition']==CONDITION,'exact independent whole-program review')
        need(review['source_manifest']=={'path':str(root/env['manifest_path']),**env['source_pin']} and review['source_merge']==registered['meta']['source_merge'] and review['original_clock']==original and review['entry_bootstrap']==selected,'same actual qualified source/original pre-preparation clock/row')
        need([review[k]for k in ('actual_program_path','actual_review_path','actual_output_path','other_reserve_bytes')]==[args.program,args.review,args.output,args.other_reserve_bytes] and type(args.other_reserve_bytes) is int and args.other_reserve_bytes>=0,'actual selected CLI operand/reserve names')
        u.descriptor(review['program']);need(review['program']['path']==args.program,'exact immutable R path')
        need(review['environment_pin']==pin(canonical(dict(os.environ))),'whole exact admitted clean wrapper environment')
        first_gate,command=campaign(env,registered,review,args)
        # Only after actual shared qualification, complete review and campaign.
        R,request_pin=reader.json(args.program,selected['limits']['metadata_bytes'],u.only_pin(review['program']))
        qd=R['central_source_selection'];Q,_=reader.json(qd['path'],selected['limits']['metadata_bytes'],qd['pin'])
        need(R['original_clock']==Q['original_clock']==original and Q['environment']==dict(os.environ) and Q['source_pin']==selected['source_pin'],'same real earlier Qc and later R, no clock/environment reset')
        source_list=[{'path':str(root/name),'pin':p}for name,p in sorted(env['source_rows'].items())]
        need(Q['sources']==source_list and pin(canonical(source_list))==Q['source_pin'],'one complete source closure at wrapper and actual central entry')
        for name,p in env['source_rows'].items():reader.opaque({'path':str(root/name),**p},16777216)
        entry_relative=PRODUCTION_ENTRY;entry_raw=env['bodies'][entry_relative]
        need(Q['prelude']=={'path':str(root/entry_relative),'pin':pin(entry_raw)},'genuine selected captured same-process central/prelude source')
        logical=[str(root/entry_relative),'--independently-enabled','--mode','central','--entry-bootstrap',boot_raw,'--entry-bootstrap-bytes',str(len(boot_raw.encode('ascii'))),'--output',args.output]
        for key,item in (('policy',qd),('request',{'path':args.program,'pin':request_pin})):
            logical+=['--'+key,item['path'],'--'+key+'-bytes',str(item['pin']['bytes']),'--'+key+'-sha256',item['pin']['sha256']]
        again=qualify(env);need(again==registered,'qualification unchanged before concrete dispatch')
        second_gate,again_command=campaign(env,again,review,args)
        gate_result=env['gate'].finish(first_gate,second_gate,again_command,root)
        need(command==again_command,'same literal original command')
        runtime_environment=executing_environment(env,command)
        prefix={'schema':'nb079_actual_wrapper_prefix_v1','reader':reader.report(),'campaign':gate_result,'registry':{'path':REGISTRY,**registered['registry_pin']},'review':{'path':args.review,'pin':review_pin},'source_manifest':review['source_manifest'],'actual_argv':list(sys.orig_argv),'original_clock':original,'same_process_dispatch':True,'executing_environment':runtime_environment,'executing_environment_attempts':env['executing_environment_prefix']}
        namespace={'__name__':'__main__','__file__':str(root/entry_relative),'__package__':None,
            '_CAPTURED_ENTRY_PIN':pin(entry_raw),'_CAPTURED_ENTRY_CLOCK':[original[k]for k in ('origin','scientific','closeout','outer')],
            '_CAPTURED_ENTRY_READ_BYTES':0,'_WRAPPER_PREFIX':prefix}
        prior=list(sys.argv)
        code=compile(entry_raw,namespace['__file__'],'exec')
        try:
            # Exact local freshness is observed after compilation, immediately
            # before this same-process production dispatch. No other operation
            # is authorized by this filesystem predicate.
            prefix['executing_environment']=executing_environment(env,command)
            prefix['reader']=reader.report()
            sys.argv=logical;exec(code,namespace)
        finally:sys.argv=prior
        tick(original,'outer');result=0
    except BaseException as error:first=error
    if first is not None:
        record={'schema':'nb079_wrapper_refusal_v1','type':type(first).__name__,'metadata_prefix':None if reader is None else reader.report(),
            'entry_prefix':getattr(first,'nb079_entry_prefix',None),'central_prefix':getattr(first,'nb079_complete_central_prefix',None),
            'prelude_prefix':getattr(first,'nb079_prelude_prefix',None),'atomic_prefix':getattr(first,'atomic_prefix',None),
            'secondary':list(getattr(first,'nb079_wrapper_secondary',[])),'executing_environment_prefix':None if env is None else env.get('executing_environment_prefix'),'qualified':False,'unknown_costs_not_zero':True}
        try:
            cap=32768 if u is None else selected['limits']['stream_bytes']
            raw=(canonical(record) if u is None else u.bounded_canonical(record,cap))+b'\n'
            need(len(raw)<=cap+1,'bounded diagnostic framing')
            if reader is not None:reader.reserve_write(len(raw))
            offset=0
            while offset<len(raw):
                n=os.write(2,memoryview(raw)[offset:]);need(n>0,'diagnostic write');offset+=n
        except BaseException:pass
        return 2
    return result

if __name__=='__main__':raise SystemExit(main())
