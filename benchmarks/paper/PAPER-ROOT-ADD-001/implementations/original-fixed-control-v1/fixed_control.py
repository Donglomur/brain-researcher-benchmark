"""Exactly admitted trusted fixed-programme exercise of the selected full task.

No process or data store is opened on import. This is not author prediction replay,
an AI evaluation, a fitted model, or a qualified arbitrary-candidate provider.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time
import types

HERE=Path(__file__).resolve().parent
EXECUTION_SHA='5ee501891b963abbce4f6f4aa5085e60e78544cc65f261e00ec75a0c5852229d'
PRODUCER_SHA='620a265897e0b110ffb25da1816f27938f70df4ae3122f7a5c8a71232e9232e9'
READER_SHA='84a1f6e94dd855aec991026f3804cfe660914d084dbe14ee8b73ba63db39e6c3'
WORKER_SHA='7085f45a2e2f79c4c9e77f7b870dece03f625bdd6c4bae88ba800f53ef154f0d'
STORE_SHA='cc98fa05b7b9f756af426d14b590136ed525efb0fd19c7f93b5797918160db16'
SUPPORT_SHA='3d2d46bbc6534b282f97d29c51b1961c8d284cf7a9894839fb851550b7549e37'
SOURCE_FILES={'execution.py':HERE.parent/'original-figure3b-execution-v1/execution.py',
 'producer.py':HERE.parent/'original-figure3b-store-v1/producer.py',
 'reader.py':HERE.parent/'original-figure3b-store-v1/reader.py',
 'fixed_provider.py':HERE/'fixed_provider.py','time_worker.py':HERE/'time_worker.py',
 'fixed_control.py':HERE/'fixed_control.py','supervise.py':HERE/'supervise.py'}


def need(ok,message):
    if not ok:raise ValueError(message)


def read_verified(path,expected,cap):
    path=Path(path).absolute()
    need(not any(p.is_symlink() for p in (path,*path.parents)),'No source/protocol symlink')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=cap,'Bounded ordinary source/protocol before read')
        raw=stream.read(before.st_size+1)
        stamp=lambda s:tuple(getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))
        need(len(raw)==before.st_size and hashlib.sha256(raw).hexdigest()==expected
             and stamp(before)==stamp(os.fstat(stream.fileno()))==stamp(path.lstat()),'Exact stable authenticated source/protocol bytes')
    return raw


path=SOURCE_FILES['execution.py'];raw=read_verified(path,EXECUTION_SHA,131072)
e=types.ModuleType('_language_fixed_control_selected_execution');e.__file__,e.__package__=str(path),''
sys.modules[e.__name__]=e
try:exec(compile(raw,str(path),'exec',dont_inherit=True),e.__dict__)
except BaseException:sys.modules.pop(e.__name__,None);raise

KEYS={'schema','activity','source_pins','store_root','store_sha256','source_support_sha256','schedule_sha256',
 'store_read_limits','store_working_bytes','artifact_root','provider_config','collection_limits','recovery_limits',
 'operator_joint_admission_bytes','child_working_bytes','whole_seconds','numpy_version','summary_output_bytes'}
ACTIVITY='trusted_fixed_time_only_programme_pipeline_control'


def protocol_snapshot(p):
    need(type(p) is dict and set(p)==KEYS and p['schema']=='language-selected-fixed-control-protocol/v1'
         and p['activity']==ACTIVITY,'Exact fixed non-learning control protocol')
    need(type(p['source_pins']) is dict and set(p['source_pins'])==set(SOURCE_FILES),'Complete actual source pins')
    expected={'execution.py':EXECUTION_SHA,'producer.py':PRODUCER_SHA,'reader.py':READER_SHA,'time_worker.py':WORKER_SHA}
    for name,path in SOURCE_FILES.items():
        e.J.P.digest(p['source_pins'][name])
        need(name not in expected or p['source_pins'][name]==expected[name],'No substitute scientific source or worker')
        read_verified(path,p['source_pins'][name],131072)
    need(p['store_sha256']==STORE_SHA and p['source_support_sha256']==SUPPORT_SHA,'Exact authenticated original selected store/support')
    e.J.P.digest(p['schedule_sha256'])
    for key in ('store_root','artifact_root'):
        need(type(p[key]) is str and 0<len(p[key])<=4096 and Path(p[key]).is_absolute(),'Absolute private operator root')
        path=Path(p[key]);need(not any(v.is_symlink() for v in (path,*path.parents)),'No private path alias')
    a,b=Path(p['store_root']),Path(p['artifact_root'])
    need(a!=b and a not in b.parents and b not in a.parents,'Immutable source and new results disjoint')
    need(type(p['store_read_limits']) is dict and set(p['store_read_limits'])=={'collection','recovery'}
         and all(e.integer(v,1) for v in p['store_read_limits'].values()),'Two separately charged source-reader allowances')
    collection=e.limits_snapshot(p['collection_limits']);recovery=e.limits_snapshot(p['recovery_limits'])
    need(e.integer(p['store_working_bytes'],1,1024**3) and e.integer(p['operator_joint_admission_bytes'],1,1024**3)
         and e.integer(p['child_working_bytes'],1,256*1024**2) and e.integer(p['whole_seconds'],1,3600)
         and e.integer(p['summary_output_bytes'],1,262144),'Finite joint operator/child/output/deadline declarations')
    c=p['provider_config']
    need(type(c) is dict and c.get('scope')=='original_figure3b_improvement' and c.get('condition')=='paper_data'
         and c.get('candidate_sha256')==WORKER_SHA and c.get('store_sha256')==STORE_SHA
         and c.get('schedule_sha256')==p['schedule_sha256'] and type(c.get('caps')) is dict,'Fixed programme/source/schedule identity')
    caps=c['caps'];need(caps.get('max_jobs')==42 and caps.get('max_requests')==5685,'All42 jobs/5685 derived responses retained')
    need(e.integer(caps.get('working_bytes'),1,1024**3) and e.integer(caps.get('run_seconds'),1,p['whole_seconds']),
         'Finite fixed provider work/wall within whole attempt')
    # Deliberately conservative separate component reservations. This is not a
    # process-tree RSS measurement or an OS memory limit.
    joint=3*max(collection['working_bytes'],recovery['working_bytes'])+collection['cache_working_bytes']+p['store_working_bytes']+caps['working_bytes']+p['child_working_bytes']
    need(p['operator_joint_admission_bytes']>=joint,'Complete simultaneous private operator plus child allocation')
    need(collection['wall_seconds']+recovery['wall_seconds']<=p['whole_seconds'],
         'Collection/recovery phase ceilings fit the whole cooperative envelope')
    need(p['numpy_version']==e.np.__version__,'Exact admitted numerical scoring runtime')
    need(type(c.get('python')) is dict and c['python'].get('path')==str(Path(sys.executable).resolve())
         and c['python'].get('version')==sys.version.split()[0],'Existing exact trusted interpreter; no new runtime')
    return e.J.P.parse(e.encoded(p))


def load_reader():
    producer=e.load_pinned('_language_fixed_control_store_producer','original-figure3b-store-v1','producer.py',PRODUCER_SHA)
    prior=sys.modules.get('producer')
    try:
        sys.modules['producer']=producer
        return e.load_pinned('_language_fixed_control_store_reader','original-figure3b-store-v1','reader.py',READER_SHA)
    finally:
        if prior is None:sys.modules.pop('producer',None)
        else:sys.modules['producer']=prior


def control_summary(packet):
    """Use the unchanged endpoint's null-preserving equal-session estimand."""
    endpoint=e.J.ENDPOINT
    values=endpoint._packet(packet,'candidate')
    sessions=[{'session':sid,'person':sid.split('_')[0],
        'lag_correlations':values[3*i:3*i+3],
        'mean':endpoint._mean(values[3*i:3*i+3])}
        for i,sid in enumerate(endpoint.SESSIONS)]
    return {'sessions':sessions,'equal_session_mean':endpoint._mean([row['mean'] for row in sessions]),
        'defined_session_means':sum(row['mean'] is not None for row in sessions),
        'reference_comparison':None,'scientific_qualification':False}


@contextmanager
def interruptible():
    """A terminating wrapper gets ordinary owned-child cleanup, not silent exit."""
    old={}
    def stop(signum,frame):raise KeyboardInterrupt('fixed control interrupted by signal '+str(signum))
    try:
        for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):
            old[sig]=signal.getsignal(sig);signal.signal(sig,stop)
        yield
    finally:
        for sig,handler in old.items():signal.signal(sig,handler)


def execute(p,admission,*,clock=time.monotonic):
    p=protocol_snapshot(p)
    provider_module=e.load_pinned('_language_fixed_control_provider','original-fixed-control-v1','fixed_provider.py',p['source_pins']['fixed_provider.py'])
    c=provider_module.config_snapshot(p['provider_config'])
    need(c['provider_source_sha256']==provider_module.identity(),'Exact actual fixed provider identity')
    a=provider_module.admission_snapshot(c,admission)
    need(a['protocol_sha256']==e.sha(e.encoded(p)),'Root admission binds this entire protocol, not only provider config')
    started=clock();deadline=started+p['whole_seconds']
    def live():
        now=clock();need(e.np.isfinite(now) and started<=now<=deadline,'Whole fixed-control deadline')
    root=e.ordinary_root(p['artifact_root'],fresh=True)
    provider=reader=None;summary_meter=e.Meter(p['summary_output_bytes'])
    try:
        with interruptible():
            live()
            # Constructor verifies programme/runtime admission before source
            # arrays are traversed. It does not execute the first child yet.
            provider=provider_module.FixedProvider(c,a,evidence_root=root/'provider')
            readers=load_reader()
            reader=readers.StoreReader(p['store_root'],expected_store_sha256=STORE_SHA,
                read_limit=p['store_read_limits']['collection'],working_limit=p['store_working_bytes'])
            need(reader.scope=='original_figure3b_improvement','Authentic complete selected source only')
            run=e.J.make_run(store_sha256=STORE_SHA,candidate_sha256=WORKER_SHA,
                schedule_sha256=p['schedule_sha256'],provider_source_sha256=c['provider_source_sha256'],
                condition='paper_data',working_limit=p['collection_limits']['working_bytes'])
            collected,cpin=e.collect(reader,provider,run,root/'collection',limits=p['collection_limits'],clock=clock)
            reader=provider=None;live()
            proof=collected['provider']
            need(proof.get('generated') is False and proof.get('jobs')==proof.get('worker_executions')==42
                 and proof.get('derived_responses')==5685,'Complete actual42-worker/5685-derived-response fixed control')
            reader=readers.StoreReader(p['store_root'],expected_store_sha256=STORE_SHA,
                read_limit=p['store_read_limits']['recovery'],working_limit=p['store_working_bytes'])
            recovered,rpin=e.recover(reader,run,root/'collection',collected,collection_sha256=cpin['sha256'],
                limits=p['recovery_limits'],source_support_sha256=SUPPORT_SHA,clock=clock)
            reader=None;live()
            need(len(recovered['result']['candidate_scores']['scores'])==42,'All original score cells retained, including undefinednull')
            result={'schema':'language-selected-fixed-time-control-result/v1','activity':ACTIVITY,
                'protocol_sha256':e.sha(e.encoded(p)),'root_admission_id':a['root_admission_id'],
                'collection':cpin,'recovery':rpin,'store_sha256':STORE_SHA,'source_support_sha256':SUPPORT_SHA,
                'procedural_scores':control_summary(recovered['result']['candidate_scores']),
                'scope':{'sessions':14,'people':8,'source_jobs':42,'software_callbacks':5685,'actual_fixed_worker_executions':42},
                'worker_source_sha256':WORKER_SHA,'worker_inputs':'Only complete public time-index vector; zero response labels/features/qids.',
                'reuse':'Allrow fixed outputs sliced to each original held support. This is source-proved for this programme only, not general participant batching.',
                'original_metric_evaluations':42,'new_training_runs':0,'AI_or_API_runs':0,
                'author_prediction_replay':False,'original_independent_reproduction':False,'candidate_improvement':False,
                'native_containment_qualified':False,'scientific_qualification':False,
                'elapsed_seconds':clock()-started,'source_reader_logical_read_ceiling_bytes':sum(p['store_read_limits'].values()),
                'metric_interpretation':'Procedural fixed-control correlations only. No paper improvement, historical baseline parity or current SOTA claim.',
                'no_binary_win_or_missing_case_drop':True}
            pin=e.save_json(root,'CONTROL.json',result,summary_meter)
            return result,pin
    except BaseException as exc:
        try:e.save_json(root,'FAILURE.json',{'schema':'language-selected-fixed-control-failure/v1',
            'error_type':type(exc).__name__,'error':str(exc)[:512],'complete':False,
            'protocol_sha256':e.sha(e.encoded(p)),'scientific_qualification':False},summary_meter)
        except BaseException:pass
        raise
    finally:e.close_owned(provider,reader)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',required=True);parser.add_argument('--protocol-sha256',required=True)
    parser.add_argument('--admission',required=True);parser.add_argument('--admission-sha256',required=True)
    args=parser.parse_args(argv)
    p_raw=read_verified(args.protocol,args.protocol_sha256,65536);p=e.J.P.parse(p_raw)
    need(e.encoded(p)==p_raw,'Canonical complete protocol')
    a_raw=read_verified(args.admission,args.admission_sha256,16384);a=e.J.P.parse(a_raw)
    need(e.encoded(a)==a_raw,'Canonical separate root admission')
    _,pin=execute(p,a)
    print(json.dumps({'result':pin,'activity':ACTIVITY,'scientific_qualification':False}))


if __name__=='__main__':main()
