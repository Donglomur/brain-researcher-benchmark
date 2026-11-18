"""Private raw-prediction recovery and attributed fresh-exec lineage.

This module never fits an estimator. Native collection belongs to the existing
provider; original pooled-Pearson recovery remains unchanged. Authentic use needs
the separate paired-entrypoint admission. Generated controls prove no native or
scientific qualification. The operator and its immutable host remain trusted.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys
import types

PINS = {
 'original-figure3b-execution-v1/execution.py': '5ee501891b963abbce4f6f4aa5085e60e78544cc65f261e00ec75a0c5852229d',
 'original-figure3b-store-v1/producer.py': '620a265897e0b110ffb25da1816f27938f70df4ae3122f7a5c8a71232e9232e9',
 'original-figure3b-store-v1/reader.py': '84a1f6e94dd855aec991026f3804cfe660914d084dbe14ee8b73ba63db39e6c3',
 'original-exec-provider-v1/provider.py': 'c9426ce6c51f2ac830809a9aab6649ab5926e5de7d983d0085b448001afb1b98',
}
ROLES = ('executed_author_reference', 'paper_data', 'paper_data_author_code')
COMMON_KEYS = ('context','coordinates','rows','outputs','target_sha256','support_class_sha256',
               'feature','qid_sha256','time_sha256','requests')
REQUEST_KEYS = {'held_f64le','query_rows','request_sha256','bundle_sha256','bundle_bytes'}
_SEAL = object()


def need(ok, message):
    if not ok: raise ValueError(message)


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    need(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value), 'Exact SHA256')
    return value


def parse(raw):
    def pairs(rows):
        result={}
        for key,value in rows:
            need(key not in result,'Duplicate JSON key'); result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite JSON'))


class Meter:
    def __init__(self, limit):
        need(type(limit) is int and 0 < limit <= 2**34,'Finite private read/write allocation')
        self.limit,self.used=limit,0
    def charge(self, count):
        need(type(count) is int and count>=0 and self.used+count<=self.limit,'Cumulative byte allocation')
        self.used+=count


def owned_bytes(path, expected, cap, meter):
    path=Path(path).absolute()
    need(not any(p.is_symlink() for p in (path,*path.parents)),'No source/product path alias')
    need(type(expected) is dict and set(expected)=={'bytes','sha256'} and
         type(expected['bytes']) is int and 0<expected['bytes']<=cap,'Bounded exact file identity')
    digest(expected['sha256']); meter.charge(expected['bytes']+1)
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        stamp=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes'],'Exact ordinary file before allocation')
        raw=stream.read(expected['bytes']+1)
        need(len(raw)==expected['bytes'] and sha(raw)==expected['sha256'] and
             stamp(before)==stamp(os.fstat(stream.fileno()))==stamp(path.lstat()),'Stable complete file authentication')
    return raw


def load_stack(task_home):
    """Load only the four fixed scientific/source seams; no original arrays."""
    home=Path(task_home).absolute()/'implementations'
    def load(relative, name):
        path=home/relative
        size=path.stat().st_size
        raw=owned_bytes(path,{'bytes':size,'sha256':PINS[relative]},262144,Meter(262145))
        module=types.ModuleType(name); module.__file__,module.__package__=str(path),''
        sys.modules[name]=module
        try: exec(compile(raw,str(path),'exec',dont_inherit=True),module.__dict__)
        except BaseException:
            sys.modules.pop(name,None); raise
        return module
    e=load('original-figure3b-execution-v1/execution.py','_language_pair_execution')
    producer=load('original-figure3b-store-v1/producer.py','_language_pair_store_producer')
    previous=sys.modules.get('producer')
    try:
        sys.modules['producer']=producer
        reader=load('original-figure3b-store-v1/reader.py','_language_pair_store_reader')
    finally:
        if previous is None: sys.modules.pop('producer',None)
        else: sys.modules['producer']=previous
    provider=load('original-exec-provider-v1/provider.py','_language_pair_provider')
    return e,reader,provider


def common_lineage(authority):
    """Exclude programme/run identity, never original data/held-row identity."""
    need(type(authority) is dict and all(k in authority for k in COMMON_KEYS),'Complete original job authority')
    value={k:copy.deepcopy(authority[k]) for k in COMMON_KEYS}
    need(type(value['requests']) is list and len(value['requests'])>=2 and
         all(type(r) is dict and set(r)==REQUEST_KEYS for r in value['requests']), 'Complete held-query roster')
    return value,sha(b'language-paired-original-job/v1\0'+encoded(value))


def lifecycle_records(raw, expected_count):
    need(type(raw) is bytes and 0<len(raw)<=16*1024**2 and raw.endswith(b'\n'),'Bounded complete lifecycle journal')
    rows=raw.splitlines(keepends=True)
    need(len(rows)==2+2*expected_count and all(0<len(r)<=8192 for r in rows),'One open/start/closed/finish grammar')
    parsed=[]
    for row in rows:
        value=parse(row); need(encoded(value)==row,'Canonical lifecycle JSON'); parsed.append(value)
    return parsed


def verify_lifecycle(records, requests, packed_records, provider, config, *, mode):
    """Join actual fresh-exec events to packed transport/closure hashes.

    This verifies attributed records from the pinned provider. It does not itself
    establish an OS namespace, external qualification or an unexposed holdout.
    """
    need(mode=='exec_reset_bwrap_v1' and provider.get('schema')=='language-exec-provider-receipt/v1'
         and provider.get('mode')==mode and provider.get('config_sha256')==sha(encoded(config)), 'Exact learner fresh-exec provider; fixed-time reuse refused')
    n=len(requests)
    need(len(records)==2+2*n and len(packed_records)==n and n>0,'Complete fresh-exec request count')
    first,last=records[0],records[-1]
    need(set(first)=={'event','mode','config_sha256','admission','scientific_qualification'} and
         first['event']=='open' and first['mode']==mode and first['config_sha256']==provider['config_sha256']
         and first['admission']==provider['admission'] and first['scientific_qualification'] is False,'Provider open binds admitted configuration')
    need(set(last)=={'event','counters_before_finish_record'} and last['event']=='finish','Successful complete journal terminator')
    cgroups=set()
    for i,((job_ordinal,request,feature_bytes),record) in enumerate(zip(requests,packed_records)):
        start,closed=records[1+2*i:3+2*i]
        need(set(start)=={'event','request','request_sha256','feature_bytes','bundle_bytes','descriptor_bytes'} and
             start['event']=='start' and start['request']==i+1 and start['request_sha256']==request['request_sha256']
             and start['feature_bytes']==feature_bytes and start['bundle_bytes']==request['bundle_bytes']
             and type(start['descriptor_bytes']) is int and 0<start['descriptor_bytes']<=8192, 'Each original request starts one fresh invocation')
        need(set(closed)=={'event','request','closure','observation'} and closed['event']=='closed' and closed['request']==i+1,'No derived job closures or failed invocation')
        closure,observation=closed['closure'],closed['observation']
        need(type(closure) is dict and set(closure)=={'schema','request_sha256','candidate_sha256','provider_source_sha256',
             'natural_exit_zero','owned_processes_absent','private_view_retired','transport_sha256'}
             and closure['schema']=='language-private-invocation-closure/v1'
             and closure['request_sha256']==request['request_sha256']
             and closure['candidate_sha256']==config['candidate_sha256']
             and closure['provider_source_sha256']==config['provider_source_sha256']
             and all(closure[k] is True for k in ('natural_exit_zero','owned_processes_absent','private_view_retired')),'Exact fresh request closure')
        need(record[0]==i and record[1]==job_ordinal and record[2]==request['query_rows'] and record[3]==1
             and struct.pack('<d',record[6]).hex()==request['held_f64le']
             and record[9].hex()==request['request_sha256'] and record[10].hex()==closure['transport_sha256']
             and record[12].hex()==sha(encoded(closure)), 'Lifecycle closure and raw transport match authenticated packed request')
        need(type(observation) is dict and all(observation.get(k) is True for k in
             ('natural_exit_zero','owned_processes_absent','gate_joined_before_exec','pidfd_owned')),
             'Owned invocation joined before exec and completely retired')
        name=observation.get('cgroup_name')
        need(type(name) is str and name.startswith('language-') and len(name)==41 and name not in cgroups
             and all(c in '0123456789abcdef' for c in name[9:]),'Unique per-invocation cgroup ownership, not PID uniqueness')
        need(all(type(observation.get(k)) is int and observation[k]>0 for k in ('cgroup_inode','cgroup_device'))
             and observation.get('memory_events',{}).get('oom_kill')==0,'Valid owned group and no OOM')
        cgroups.add(name)
    need(provider['counters']['max_requests']==n and last['counters_before_finish_record']['max_requests']==n,
         'Closed journal and provider count match original requests')
    jobs=len({job for job,_,_ in requests})
    before=last['counters_before_finish_record'];after=provider['counters']
    need(before['max_jobs']==after['max_jobs']==jobs and set(before)==set(after), 'Provider job count and full counter roster match source')
    need(before['journal_bytes']==sum(len(encoded(row)) for row in records[:-1])
         and after['journal_bytes']==before['journal_bytes']+len(encoded(last))
         and all(before[key]==after[key] for key in before if key!='journal_bytes'), 'Exact authenticated lifecycle byte/counter closure')
    return sorted(cgroups)


class Recovered:
    __slots__=('_payload','_seal')
    def __init__(self, value, seal):
        object.__setattr__(self,'_payload',encoded(value));object.__setattr__(self,'_seal',seal)
    def __setattr__(self,name,value): raise AttributeError('Immutable recovered product')
    def snapshot(self): return parse(self._payload)


def snapshot(value):
    need(type(value) is Recovered and value._seal is _SEAL,'Raw-recovered sealed product required; aggregate substitutions refused')
    return value.snapshot()


def recover_executed(e, reader_module, run, collection, collection_pin, role, config,
                     *, store_root, output_root, evidence_root, store_limit, store_working,
                     limits, support_sha256, extra_read_limit, working_limit):
    """Authenticate lifecycle/source joins, then call unchanged raw recovery.

    Entry validation supplies only pinned modules/configurations and a globally
    frozen role. This function has no candidate import or fitting path.
    """
    need(role in ROLES and type(working_limit) is int and 256*1024**2<=working_limit<=1024**3,'Bounded role-recovery workspace')
    binding=e.J._binding(run)
    need(binding['scope']==e.J.ORIGINAL_SCOPE and (binding['jobs'],binding['requests'])==(42,5685), 'Exact original42/5685 scope; generated products cannot become author evidence')
    need(binding['condition']==('paper_data_author_code' if role=='executed_author_reference' else role),
         'Author calibration uses code-bearing transport but is neither AI condition')
    need(binding['candidate_sha256']==config['candidate_sha256'] and binding['provider_source_sha256']==config['provider_source_sha256'], 'Frozen programme/provider binding')
    need(collection_pin=={'bytes':len(encoded(collection)),'sha256':sha(encoded(collection))}
         and collection.get('run_binding_sha256')==sha(run.binding_json)
         and collection.get('jobs')==42 and collection.get('software_callbacks')==5685,'Complete exact collection receipt')
    root=Path(output_root).absolute()
    need(not (root/'RECOVERY.json').exists(),'Fresh original recovery receipt required; preserve prior attempts')
    provider=collection['provider']
    need(provider.get('schema')=='language-exec-provider-receipt/v1' and provider.get('mode')=='exec_reset_bwrap_v1'
         and provider.get('config_sha256')==sha(encoded(config)) and provider.get('candidate_sha256')==binding['candidate_sha256']
         and provider.get('provider_source_sha256')==binding['provider_source_sha256']
         and provider.get('condition')==binding['condition'],'Pinned fresh-learner provider before private map/target reads')
    meter=Meter(extra_read_limit)
    life=provider['lifecycle']; need(set(life)=={'path','bytes','sha256'} and life['path']=='LIFECYCLE.jsonl','Exact lifecycle member')
    life_raw=owned_bytes(Path(evidence_root)/life['path'],{k:life[k] for k in ('bytes','sha256')},16*1024**2,meter)
    records=lifecycle_records(life_raw,5685)
    packed_manifest=root/'packed'/'MANIFEST.json'
    manifest_raw=owned_bytes(packed_manifest,{'bytes':packed_manifest.stat().st_size,'sha256':collection['join']['packed_manifest_sha256']},65536,meter)
    manifest=parse(manifest_raw)
    request_pin=manifest['files']['REQUESTS.bin']
    need(request_pin['bytes']==5685*e.J.P.REQUEST.size,'Exact packed request extent')
    packed_raw=owned_bytes(root/'packed'/'REQUESTS.bin',request_pin,5685*e.J.P.REQUEST.size,meter)
    packed_records=list(e.J.P.REQUEST.iter_unpack(packed_raw))
    reader=authority=None; jobs=[]; requests=[]
    try:
        reader=reader_module.StoreReader(store_root,expected_store_sha256=binding['store_sha256'],read_limit=store_limit,working_limit=store_working)
        need(reader.scope==e.J.ORIGINAL_SCOPE,'Original selected store only')
        authority=e.AuthorityReader(root/'authorities',run,collection['authorities'],receipt_sha256=sha(encoded(collection['authorities'])),
            read_limit=limits['authority_read_bytes'],working_limit=limits['working_bytes'])
        for session in reader.iter_sessions():
            try:
                for item in session.iter_jobs(include_targets=False):
                    job=authority.next_job(qid=item['qid'],time_indices=item['time_indices'])
                    a,_,_=e.J._job_snapshot(run,job,limits['working_bytes'])
                    need(a['context']==item['context'] and a['target_sha256']==item['target_sha256']
                         and a['support_class_sha256']==item['support_class_sha256'] and a['feature']==item['feature'], 'Full source binding before private target recovery')
                    common,identity=common_lineage(a)
                    need(len(jobs)<42 and a['coordinates']==e.J.ENDPOINT.coordinates()[len(jobs)],'Canonical complete42-job order')
                    requests.extend((len(jobs),r,a['feature']['bytes']) for r in common['requests'])
                    jobs.append({'context':common['context'],'lineage_sha256':identity,'requests':len(common['requests'])})
            finally:session.close()
        need(len(jobs)==42 and len(requests)==5685,'Complete original jobs/held rows')
        authority_receipt=authority.finish()
        reader_cost=reader.private_metrics()
    finally:e.close_owned(authority,reader)
    groups=verify_lifecycle(records,requests,packed_records,provider,config,mode='exec_reset_bwrap_v1')
    # Raw predictions and private targets are authenticated/scored by the existing
    # recovery implementation. No supplied correlation packet is accepted here.
    reader=reader_module.StoreReader(store_root,expected_store_sha256=binding['store_sha256'],read_limit=store_limit,working_limit=store_working)
    result,recovery_pin=e.recover(reader,run,root,collection,collection_sha256=collection_pin['sha256'],limits=limits,
        source_support_sha256=support_sha256,reference=None,reference_sha256=None)
    scores=result['result']['candidate_scores']
    need(scores['prediction_run_sha256']==collection_pin['sha256'] and scores['source_support_sha256']==support_sha256,
         'Recovered scores remain bound to raw collection/source')
    e.J.ENDPOINT._packet(scores,'candidate')
    value={'schema':'language-executed-selected-product/v1','role':role,
        'information_condition':None if role=='executed_author_reference' else role,
        'reference_kind':'fresh_historical_stack_source_method_replay' if role=='executed_author_reference' else None,
        'transport_condition':binding['condition'],'store_sha256':binding['store_sha256'],'schedule_sha256':binding['schedule_sha256'],
        'source_support_sha256':support_sha256,'candidate_sha256':binding['candidate_sha256'],
        'collection':collection_pin,'recovery':recovery_pin,'provider_config_sha256':sha(encoded(config)),
        'lifecycle':copy.deepcopy(life),'invocation_groups':groups,'jobs':jobs,'scores':copy.deepcopy(scores['scores']),
        'extra_read_bytes':meter.used,'lineage_store_read_metrics':reader_cost,'authority_verification':authority_receipt,
        'historical_numerical_parity_established':False,'native_qualification_independently_verified':False,
        'scientific_qualification':False,'binary_win':None,'current_sota':False}
    return Recovered(value,_SEAL)
