"""Concrete trusted-operator CLI for complete NEURAL078 deferred numerical grading."""
import time
ORIGIN=time.monotonic()
import argparse,ast,hashlib,json,os,re,signal,stat,sys,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
SOURCE_SCHEMA='neural078_deferred_grade_source_v1'
CURRENT_SOURCE_SCHEMA='neural078_deferred_grade_current_source_v1'
PROGRAM_PIN={'bytes':1801,'sha256':'8a1b62ca449c5d3c089407fbe76345910fcc4684a3cbaf2811f6e043adb9dc6d'}
ADAPTER_PIN={'bytes':472,'sha256':'a5912bbdb00ed898e67cd15e6e9f1fe75ddf1eb29c5807e78ef5ad8a50845e8f'}
SECONDS=180

def bootstrap(expected,here=HERE,*,manifest_path=None):
    def need(ok,message):
        if not ok:raise ValueError(message)
    def capture(p,cap):
        need(not any(x.is_symlink() for x in (p,*p.parents)),'Unlinked bootstrap source')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=cap,'Bounded ordinary bootstrap source')
            with os.fdopen(fd,'rb',closefd=False) as f:b=f.read(s.st_size+1)
            need(len(b)==s.st_size and all(getattr(s,k)==getattr(os.fstat(fd),k)==getattr(p.lstat(),k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'Stable bootstrap source');return b
        finally:os.close(fd)
    def pin(b):return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
    def parse(b):
        def pairs(rows):
            out={}
            for k,v in rows:need(k not in out,'Duplicate bootstrap JSON key');out[k]=v
            return out
        return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite bootstrap JSON'))
    selected_manifest=here/'SOURCE_MANIFEST.json' if manifest_path is None else Path(manifest_path)
    need(selected_manifest.is_absolute() and '..' not in selected_manifest.parts,'Literal absolute selected source manifest')
    raw=capture(selected_manifest,65536);need(pin(raw)==expected and type(expected['bytes'])is int,'Externally selected source manifest')
    m=parse(raw);historical_bytes=0
    if type(m)is dict and m.get('schema')==CURRENT_SOURCE_SCHEMA:
        need(manifest_path is not None and set(m)=={'schema','historical_manifest','files'},'Explicit current source manifest')
        old_raw=capture(here/'SOURCE_MANIFEST.json',65536)
        historical_bytes=len(old_raw)
        need(type(m['historical_manifest'])is dict and set(m['historical_manifest'])=={'bytes','sha256'} and type(m['historical_manifest']['bytes'])is int and pin(old_raw)==m['historical_manifest'],'Unchanged historical source manifest')
        old=parse(old_raw);need(type(old)is dict and set(old)=={'schema','files'} and old['schema']==SOURCE_SCHEMA and type(old['files'])is list,'Historical source format')
        need(type(m['files'])is list and {row['path'] for row in m['files']}=={row['path'] for row in old['files']},'Current complete historical member set')
        m={'schema':SOURCE_SCHEMA,'files':m['files']}
    need(type(m)is dict and set(m)=={'schema','files'} and m['schema']==SOURCE_SCHEMA and type(m['files'])is list and 1<=len(m['files'])<=64,'Exact source closure format')
    sources={};total=len(raw)+historical_bytes
    for row in m['files']:
        n=row['path'];p=Path(n);need(type(n)is str and not p.is_absolute() and '..' not in p.parts and str(p)==n and n not in sources,'Unique confined source member')
        b=capture(here/p,1000000);total+=len(b);need(total<=4000000 and type(row['bytes'])is int and pin(b)=={k:row[k] for k in ('bytes','sha256')},'Exact complete source body');sources[n]=b
    for prefix,expected_inner in [('producer/',ADAPTER_PIN),('producer/program/',PROGRAM_PIN)]:
        need(pin(sources[prefix+'SOURCE_MANIFEST.json'])==expected_inner,'Exact original producer manifest')
        inner=parse(sources[prefix+'SOURCE_MANIFEST.json'])
        for n,q in inner['files'].items():need(pin(sources[prefix+n])==q,'Byte-identical original producer closure')
    def load(name,body,path,**injected):
        mod=types.ModuleType(name);mod.__file__=str(path);mod.__dict__.update(injected);sys.modules[name]=mod;exec(compile(body,str(path),'exec'),mod.__dict__);return mod
    mods={}
    for name in ('bound_io','absence','admission','public_report','gold_binding','transport','grading'):
        mods[name]=load(name,sources[name+'.py'],here/(name+'.py'))
    c=load('_078_original_common',sources['producer/program/common.py'],here/'producer/program/common.py');mods['common']=c
    for name in ('policy','observer'):
        n='observe' if name=='observer' else name;mods[name]=load('_078_original_'+name,sources['producer/program/'+n+'.py'],here/'producer/program'/ (n+'.py'),c=c)
    return sources,mods,total

def selected(request,source,mods):
    io=mods['bound_io'];a=mods['admission'];need=io.need
    keys={'schema','task_id','operator_authority_id','source','numeric_grading_authorized','candidate_access_closed','producer','observation','output','runtime','other_future_bytes'}
    need(type(request)is dict and set(request)==keys and request['schema']=='neural078_trusted_grade_selection_v1' and request['task_id']=='NEURAL-078','Exact separately selected grade request')
    need(a.same(request['source'],source) and request['numeric_grading_authorized'] is True and request['candidate_access_closed'] is True,'Explicit new numerical-grade authority and closed access')
    need(type(request['operator_authority_id'])is str and 0<len(request['operator_authority_id'])<=512,'Trusted operator authority identifier')
    need(type(request['other_future_bytes'])is int and request['other_future_bytes']>=0,'Fresh explicit OTHER')
    p=request['producer'];need(set(p)=={'repository','source_directory','attempt','package','selection','review','external_receipt'},'Exact original producer operands')
    args=types.SimpleNamespace(repository=p['repository'],producer_source=p['source_directory'],producer_attempt=p['attempt'],package=p['package'])
    for key,target in [('selection','producer_selection'),('review','producer_review'),('external_receipt','producer_external')]:
        row=p[key];need(type(row)is dict and set(row)=={'path','bytes','sha256'},'Pinned original operand');setattr(args,target,io.ordinary(row['path']));setattr(args,{'selection':'selection_pin','review':'review_pin','external_receipt':'external_pin'}[key],a.only(row))
    obs=request['observation'];need(type(obs)is dict and set(obs)=={'path','bytes','sha256'},'Separately pinned trusted observer operand')
    outer=io.parse(io.capture(obs['path'],65536,a.only(obs)))
    runtime=request['runtime'];need(set(runtime)=={'docker_binary','docker_socket','docker_config','image'},'Explicit current native operands')
    for key in ('docker_binary','docker_socket','docker_config'):runtime[key]=str(io.ordinary(runtime[key]))
    need(type(runtime['image'])is str and re.fullmatch('sha256:[a-f0-9]{64}',runtime['image']),'Immutable already-provisioned grade image')
    return args,outer

def rollback(path,published,io):
    if published and os.path.lexists(path):
        s=path.lstat()
        if (s.st_dev,s.st_ino)==(published['st_dev'],published['st_ino']):
            links=(1,)
            if s.st_nlink==2:
                t=path.with_name('.'+path.name+'.pending').lstat();io.need((t.st_dev,t.st_ino)==(s.st_dev,s.st_ino),'Own pending completion link');links=(1,2)
            io.capture(path,32768,published,allowed_links=links);path.unlink();io.fsync_dir(path.parent)

def execute(request,source,*,context=None,clock=time.monotonic,check=None,call=None,budget_class=None,grade_runner=None):
    sources,mods,_=context or bootstrap(source);io=mods['bound_io'];a=mods['admission'];need=io.need
    need(clock()-ORIGIN<30,'Original-clock source bootstrap')
    args,outer=selected(request,source,mods);check=check or a.absent
    admitted=a.admit(args,sources,mods,outer,check)
    validator=mods['public_report'].load(sources['producer/program/report_contract.py'])
    report=validator.validate_report(validator.strict_json_bytes(admitted['report']));fields=mods['public_report'].field_names(report)
    need(clock()-ORIGIN<90,'Whole producer admission before private release')
    runtime=request['runtime'];need(runtime['image']==admitted['selection']['image'],'Same explicitly reviewed producer image; no qualification inherited')
    out=io.ordinary(request['output']);need(not os.path.lexists(out) and out.parent.is_dir(),'Fresh grade output')
    for p in (io.ordinary(args.producer_attempt),io.ordinary(args.package),io.ordinary(args.producer_source)):
        need(out!=p and not out.is_relative_to(p) and not p.is_relative_to(out),'Separate protected grade custody')
    out.mkdir(mode=0o700);io.fsync_dir(out.parent);budget=(budget_class or io.Budget)(out,request['other_future_bytes']);end=ORIGIN+SECONDS
    lib=mods['transport'].bind(runtime['docker_binary'],runtime['docker_socket'],runtime['docker_config'],runtime['image'],budget,call)
    result=dict(schema='neural078_deferred_grade_attempt_v1',source=source,producer_complete=admitted['complete_pin'],program=admitted['program'],report=admitted['report_pin'],external_receipt=admitted['external'],outer_observation=a.only(request['observation']),private_gold_body_read_by_host=False,success=False,private_grade_dispatched=False,scientific_qualified=False,runtime_qualified=False,requires_external_natural_exit_zero=True)
    try:
        budget.save(out/'ATTEMPT.json',result,65536)
        fresh=mods['transport'].previous_absence(admitted['native'],lib,min(end-60,clock()+30));budget.save(out/'FORMER_RESOURCE_ABSENCE.json',fresh,8192)
        need(check(outer['process']['pid'],outer['process']['pgid']) is True,'Outer absence immediately before private binding')
        scorer_pins={n:io.identity(sources['scorer/'+n]) for n in ('score.py','analysis_core.py')}
        for n,p in scorer_pins.items():need(a.same(p,a.only(admitted['rows']['private/source/'+n])),'Exact original numerical source')
        metadata,gold_pin=mods['gold_binding'].read(io.ordinary(args.package),admitted['rows'],list(validator.PEOPLE),scorer_pins)
        folder=out/'grade';budget.mkdir(folder);inputs=folder/'inputs';budget.mkdir(inputs)
        stage={n:sources[n] for n in ('trusted_entry.py','bound_io.py','admission.py','gold_binding.py','public_report.py')}
        stage.update({n:sources['scorer/'+n] for n in ('score.py','analysis_core.py')});stage['report_contract.py']=sources['producer/program/report_contract.py']
        mounts={}
        for n,b in stage.items():budget.write(inputs/n,b);mounts['/source/'+n]=inputs/n
        budget.write(inputs/'report.json',admitted['report']);mounts['/inputs/report.json']=inputs/'report.json'
        rows_raw=io.encoded(admitted['rows']);budget.write(inputs/'ROWS.json',rows_raw);mounts['/inputs/ROWS.json']=inputs/'ROWS.json'
        for n,b in metadata.items():budget.write(inputs/n,b);mounts['/private/'+n]=inputs/n
        plan=dict(sources={n:io.identity(b) for n,b in stage.items() if n!='trusted_entry.py'},report=admitted['report_pin'],metadata={n:io.identity(b) for n,b in metadata.items()},rows=io.identity(rows_raw));plan_raw=io.encoded(plan)
        budget.write(inputs/'INPUTS.json',plan_raw);mounts['/inputs/INPUTS.json']=inputs/'INPUTS.json';mounts['/private/GOLD.json']=io.ordinary(args.package)/'private/reference/GOLD.json'
        grade=mods['grading'];grade.COMMAND=['-I','-B','/source/trusted_entry.py','--inputs-sha256',io.identity(plan_raw)['sha256']]
        need(clock()<end-45,'Complete trusted grading and cleanup allocation')
        result['private_grade_dispatched']=True;completed=(grade_runner or grade.run)(lib,folder,mounts,budget,end)
        score_raw=io.capture(folder/'score.json',65536,completed['files']['score.json']);value=grade.score_envelope(io.parse(score_raw))
        need(sorted(x['field'] for x in value['field_checks'])==fields,'All exact original195 field identities returned')
        result.update(success=True,score=io.identity(score_raw),grade_completion=io.identity(io.capture(folder/'GRADE_COMPLETION.json',200000)),required_fields=195)
    except BaseException as error:result.update(success=False,error_type=type(error).__name__)
    finally:
        cleanup=[]
        for engine in reversed(lib['engines']):
            engine.end=end-1
            for row in reversed(engine.owned):cleanup.append(engine.cleanup(row['kind'],row['name']))
        result['final_cleanup']=cleanup;result['all_grade_resources_absent']=bool(cleanup) and all(x['absence_verified'] is True for x in cleanup)
        result['elapsed_seconds']=clock()-ORIGIN;result['success']=bool(result['success'] and result['all_grade_resources_absent'] and result['elapsed_seconds']<SECONDS)
        budget.save(out/'ATTEMPT.json',result,65536,replace=True)
        if result['success']:
            published={};marker=out/'COMPLETION.json'
            try:
                need(clock()<end,'Clock before final completion');budget.save(marker,dict(schema='neural078_deferred_grade_complete_v1',attempt=io.identity(io.capture(out/'ATTEMPT.json',65536)),source=source,score=result['score'],producer_complete=admitted['complete_pin'],required_fields=195,private_captures=1,scientific_qualified=False,runtime_qualified=False,requires_external_natural_exit_zero=True),32768,publication=published);need(clock()<end,'Clock after final completion publication')
            except BaseException as error:
                rollback(marker,published,io);result.update(success=False,error_type=type(error).__name__);budget.save(out/'ATTEMPT.json',result,65536,replace=True)
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['inspect','run']);p.add_argument('--source-bytes',type=int,required=True);p.add_argument('--source-sha256',required=True);p.add_argument('--source-manifest',type=Path);p.add_argument('--request',type=Path);p.add_argument('--request-bytes',type=int);p.add_argument('--request-sha256');a=p.parse_args(argv)
    source=dict(bytes=a.source_bytes,sha256=a.source_sha256)
    if a.mode=='inspect':
        bodies,_,_=bootstrap(source,manifest_path=a.source_manifest);print(json.dumps(dict(task_id='NEURAL-078',source_members=len(bodies),participants=8,required_fields=195,private_reads=0,runtime_qualified=False)));return 0
    if not(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):raise ValueError('Host requires -I -S -B')
    if any(x is None for x in (a.request,a.request_bytes,a.request_sha256)):raise ValueError('Explicit independently selected request operands')
    def stop(*_):raise TimeoutError('Original deferred-grade work deadline')
    if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise ValueError('No inherited timer')
    old={s:signal.signal(s,stop) for s in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
    signal.setitimer(signal.ITIMER_REAL,max(.001,165-(time.monotonic()-ORIGIN)))
    try:
        context=bootstrap(source,manifest_path=a.source_manifest);io=context[1]['bound_io'];request=io.parse(io.capture(a.request,65536,context[1]['admission'].pin(dict(bytes=a.request_bytes,sha256=a.request_sha256),65536)));result=execute(request,source,context=context)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for s,handler in old.items():signal.signal(s,handler)
    print(json.dumps({k:result.get(k) for k in ('success','private_grade_dispatched','required_fields','runtime_qualified','scientific_qualified')}));return 0 if result['success'] else 2
if __name__=='__main__':raise SystemExit(main())
