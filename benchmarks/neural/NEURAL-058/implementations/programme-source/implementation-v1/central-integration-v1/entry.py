"""Externally authenticated central source entry; no scientific operation at import."""
import time
ENTRY_START=time.monotonic()
import argparse,hashlib,json,os,stat,sys,types
from pathlib import Path
REL='authoring/delivery-20261105/common/remaining-builds-wave29/neural058-complete-design/implementation-v1/central-integration-v1'
REGISTRY_ALIAS='benchmarks/neuroscience/neural-058-brainwide-wheel/score.py'

def sources(repo,expected,start):
    """Capture source before executing it. External caller must pin this entry."""
    here=repo/REL;ledger={'read_reserved':0,'read_observed':0,'attempted':[]};rows={};raws={}
    def tick():
        if not start<=time.monotonic()<start+120:raise TimeoutError('central source startup120s')
    def capture(path,pin,cap=2097152):
        tick();text=str(path)
        if not text.startswith('/')or text.startswith('//')or str(Path(text))!=text or '..'in path.parts:raise ValueError('canonical source path')
        for parent in reversed(path.parents):
            if not stat.S_ISDIR(os.lstat(parent).st_mode):raise ValueError('source parent custody')
        n=pin['bytes']
        if type(n)is not int or not 0<=n<=cap:raise ValueError('source cap')
        ledger['read_reserved']+=n+1;ledger['attempted'].append(text)
        if ledger['read_reserved']>16*1048576:raise ValueError('source bootstrap allowance')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd)
            if not stat.S_ISREG(a.st_mode)or a.st_nlink!=1 or a.st_size!=n:raise ValueError('source extent')
            raw=bytearray()
            while len(raw)<n:
                tick();b=os.read(fd,min(65536,n-len(raw)));ledger['read_observed']+=len(b)
                if not b:raise ValueError('short source')
                raw.extend(b)
            extra=os.read(fd,1);ledger['read_observed']+=len(extra)
            stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if extra or stamp(a)!=stamp(os.fstat(fd))or stamp(a)!=stamp(os.lstat(path)):raise ValueError('source changed')
            if hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('source hash')
        finally:
            first=sys.exception()
            try:os.close(fd)
            except BaseException as later:
                if first is not None:raise BaseExceptionGroup('capture and close',[first,later])from None
                raise
        if stamp(a)!=stamp(os.lstat(path)):raise ValueError('source postclose name')
        tick();rows[str(path.relative_to(repo))]=pin;raws[str(path.relative_to(repo))]=bytes(raw);return bytes(raw)
    def module(name,path,body,inject=None):
        tick();m=types.ModuleType(name);m.__file__=str(path)
        if inject:m.__dict__.update(inject)
        exec(compile(body,str(path),'exec',dont_inherit=True),m.__dict__);tick();return m
    try:
        body=capture(here/'SOURCE_MANIFEST.json',expected);manifest=json.loads(body)
        if manifest.get('schema')!='neural058_central_runtime_source_v1':raise ValueError('source manifest schema')
        for name,p in manifest['files'].items():
            if '/'in name or name in('.','..')or '\\'in name:raise ValueError('central source leaf')
            capture(here/name,p)
        bindings=json.loads(raws[REL+'/BINDINGS.json']);parent_root=repo/bindings['parent_root']
        for row in bindings['external_sources']:
            rel=row['path']
            if Path(rel).is_absolute()or '..'in Path(rel).parts:raise ValueError('relative external source')
            capture(repo/rel,{'bytes':row['bytes'],'sha256':row['sha256']})
        parent_pin=bindings['parent_manifest']['pin'];parent_manifest_path=repo/bindings['parent_manifest']['path']
        parent_manifest=json.loads(raws[bindings['parent_manifest']['path']])
        if parent_manifest.get('task_id')!='NEURAL-058':raise ValueError('exact parent task')
        if len(parent_manifest['files'])!=41:raise ValueError('complete41 runtime source members')
        # Bootstrap has its own prospective read ledger; debit it in full on
        # success and export the partial mutable context on failure.
        bp=parent_manifest['files']['program/bootstrap.py'];bootstrap_raw=capture(parent_root/'program/bootstrap.py',bp)
        bootstrap=module('_neural058_central_parent_bootstrap',parent_root/'program/bootstrap.py',bootstrap_raw)
        context={'origin':start,'deadline':start+120,'read_cap':16*1048576,'read_reserved':0,'read_observed':0,'attempted_paths':[]}
        captured=bootstrap.load(str(parent_root),str(parent_manifest_path),parent_pin,context)
        for name,p in parent_manifest['files'].items():rows[str((parent_root/name).relative_to(repo))]=p
        import importlib
        parent={name:importlib.import_module(name)for name in ('core','authority','outer','caller_observer','schedule','contracts')}
        u=module('_neural058_central_io',here/'io.py',raws[REL+'/io.py'])
        gate_path=repo/'tools/neurobench_campaign_gate.py';base_path=repo/'tools/neurobench_campaign.py'
        contract_path=repo/'authoring/delivery-20261105/common/campaign-exposure-contract-v1/validate.py'
        gate=module('_neural058_central_campaign_gate',gate_path,raws[str(gate_path.relative_to(repo))])
        base=module('_neural058_central_campaign',base_path,raws[str(base_path.relative_to(repo))])
        contract=module('_neural058_central_contract',contract_path,raws[str(contract_path.relative_to(repo))])
        gate.validator=lambda _: (contract,contract_path.parent);base._campaign_module=lambda _:gate
        components={name:module('_neural058_central_'+name,here/(name+'.py'),raws[REL+'/'+name+'.py'],{'u':u})for name in ('routing','readback','dispatch')}
        freeze=dict(rows);freeze[REGISTRY_ALIAS]=manifest['files']['entry.py']
        return {'repo':repo,'here':here,'source':expected,'manifest':manifest,'bindings':bindings,'source_rows':rows,'freeze_files':freeze,
            'parent_root':parent_root,'parent_manifest_path':parent_manifest_path,'parent_manifest':parent_manifest,'parent_pin':parent_pin,
            'captured_parent':captured,'parent_context':context,'parent':parent,'u':u,'base':base,'gate':gate,'components':components,
            'source_accounting':ledger,'source_read_reserved':ledger['read_reserved']+context['read_reserved']}
    except BaseException as error:
        error.source_accounting={'central':ledger,'parent':locals().get('context'),'physical_io_unmeasured':True};raise

def compact_source(value):
    """Known counters survive; potentially long source paths are counted only."""
    if not isinstance(value,dict):return None
    def ledger(row):
        if not isinstance(row,dict):return None
        out={k:row[k]for k in('origin','deadline','read_cap','read_reserved','read_observed','physical_io_unmeasured')
             if k in row and type(row[k])in(int,float,bool,str,type(None))}
        paths=row.get('attempted_paths',row.get('attempted',[]))
        out['attempted_path_count']=len(paths)if type(paths)is list else None
        out['attempted_paths_omitted']=out['attempted_path_count']
        return out
    return {'central':ledger(value.get('central',value)),'parent':ledger(value.get('parent')),
            'path_bodies_omitted':True}

def compact_failure(value):
    """Bounded truthful diagnostic, never completion or a substitute receipt."""
    if not isinstance(value,dict):return None
    keys=('schema','phase','error_type','caller_attempted','unknown_surviving_child_state',
          'forced_termination_supported','private_grading_may_have_started','automatic_retry',
          'diagnostic_encoding_bytes','retained_bytes_are_not_natural_closure')
    out={k:value[k]for k in keys if k in value and type(value[k])in(int,float,bool,str,type(None))}
    for k in ('original_streams','original_caller_record_pin','costs','costs_after_failure_publication'):
        if k in value:out[k]=value[k]
    rows=value.get('later_errors',[])
    out['later_errors']=rows[:16]if type(rows)is list else []
    out['later_errors_omitted']=max(0,len(rows)-16)if type(rows)is list else None
    caller=value.get('caller')
    if isinstance(caller,dict):
        fields=('pid','spawn_attempted','spawn_returned','natural_exit','exit_code','process_reaped',
                'process_group_absent','stdout_eof','stderr_eof','stdout_bytes','stderr_bytes',
                'observed_stdout_bytes','observed_stderr_bytes','combined_stream_bytes',
                'successful_observation','cleanup_ownership_unknown','failed_unknown_child_state',
                'requires_separate_child_inspection','observed_start','normal_closed_at','final_closed_at',
                'normal_end','cleanup_end','error_type','error_stage')
        out['caller']={k:caller[k]for k in fields if k in caller and type(caller[k])in(int,float,bool,str,type(None))}
        out['caller_fields_omitted']=len(caller)-len(out['caller'])
    else:out['caller']=None
    out['full_failure_record_omitted']=True
    return out

def failure_terminal(record):
    raw=json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(raw.encode())<=60000:return raw
    small={'status':'failed','error_type':record['error_type'],'source':compact_source(record.get('source')),
           'central_costs':record.get('central_costs'),'failure':compact_failure(record.get('failure')),
           'failure_record_truncated':True,'terminal_encoding_before_current_bytes':len(raw.encode())}
    encoded=json.dumps(small,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(encoded.encode())>60000:
        # Every generated projection above has fixed bounded fields. This is
        # an explicit refusal of a violated diagnostic contract, never success.
        raise ValueError('bounded central failure diagnostic exceeded')
    return encoded

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--operation',choices=['collect','grade'],required=True)
    parser.add_argument('--condition',choices=['default','full423_29_held_animal_v1'],default='default')
    for n in ('program','output','review','source-sha256'):parser.add_argument('--'+n,required=True)
    for n in ('other-reserve-bytes','source-bytes'):parser.add_argument('--'+n,type=int,required=True)
    args=parser.parse_args();cli=vars(args);cli['condition']=None if args.condition=='default'else args.condition
    cli['actual_argv']=list(sys.orig_argv);cli['actual_cwd']=os.getcwd();cli['source_pin']={'bytes':args.source_bytes,'sha256':args.source_sha256}
    repo=Path(cli['actual_cwd']);host=None;env=None
    try:
        if str(Path(__file__).absolute())not in(str(repo/REL/'entry.py'),str(repo/REGISTRY_ALIAS)):raise ValueError('fixed repo entry or installed alias')
        env=sources(repo,cli['source_pin'],ENTRY_START);host=env['u'].Host(ENTRY_START);host.reads=env['source_read_reserved']
        got=host.read(Path(__file__).absolute(),2097152,env['manifest']['files']['entry.py'])
        result=env['components']['dispatch'].execute(cli,env,host)
        print(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False));return 0
    except BaseException as error:
        record={'status':'failed','error_type':type(error).__name__,'source':getattr(error,'source_accounting',None if env is None else env['source_accounting']),
                'central_costs':None if host is None else host.record(),'failure':getattr(error,'failure_record',None),'automatic_retry':False}
        print(failure_terminal(record));return 1
if __name__=='__main__':raise SystemExit(main())
