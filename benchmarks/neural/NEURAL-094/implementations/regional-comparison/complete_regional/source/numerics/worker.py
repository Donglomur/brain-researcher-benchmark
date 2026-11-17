"""Isolated094 trusted export, reference fit/inference, and all39 final grade.

Source component only. Numerical imports and all I/O below run solely in future
root-owned containers. No candidate code/model is ever imported or unpickled.
Root owns actual source/packet/model custody, mounts, process closure and budget.
"""
import time
STARTED = time.monotonic()
import argparse
import ast
import hashlib
import io
import json
import math
import os
from pathlib import Path
import pickle
import re
import signal
import stat
import sys
from types import ModuleType
import zipfile

BINDINGS_PIN = {'bytes': 41149, 'sha256': '9e3cd8009e434486690793dcc1084145308a844cbe19a16450e412fb827603ef'}
WORK_LIMITS = {'export':45,'reference_fit':240,'reference_infer':90,'grade':240}
PAYLOAD_KEYS = {'export':('inputs','artifact_relative_root','token_key'),
    'reference_fit':('fitval_manifest',),'reference_infer':('query_manifest','support','model_artifact','model_commitment'),
    'grade':('supports','combined_commit')}
ARMS = ('context_wheel','context_wheel_neural')
REFERENCES = ('training_prior','selected_context','matched_context_logistic','matched_joint_logistic')
MODEL_CAP = 64*1024*1024
PACKET_CAP = 128*1024*1024
REQUEST_CAP = 4*1024*1024
META_CAP = 1024*1024
DEADLINE = None
WORK_END = None
OPEN_HANDLES = 0
BINDINGS = None
MODULES = {}
CAPTURED = {}
ACTIVE_COUNTERS = {}
# New local generated guards are root-source-closure authenticated with the worker;
# exact bytes are additionally bound by the request and captured before execution.


class Deadline(BaseException):
    pass


def need(ok, message):
    if not ok: raise ValueError(message)


def tick():
    if WORK_END is None or time.monotonic() >= WORK_END: raise Deadline('Trusted worker work deadline')


def pin(raw):
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def digest(value):
    return type(value) is str and re.fullmatch(r'[a-f0-9]{64}',value) is not None


def descriptor(value, cap):
    need(type(value) is dict and set(value)=={'path','bytes','sha256'}
         and type(value['path']) is str and bool(value['path'])
         and not value['path'].startswith('/') and all(p not in ('','.','..') for p in value['path'].split('/'))
         and type(value['bytes']) is int and 0<value['bytes']<=cap and digest(value['sha256']),
         'Exact relative source/artifact descriptor')
    return value


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'Duplicate JSON field');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite JSON'))


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def bounded(path,cap,expected=None):
    """Same captured bytes are authenticated and consumed; every handle closes."""
    global OPEN_HANDLES
    path=Path(path)
    need(path.is_absolute() and '..' not in path.parts
         and all(not p.is_symlink() for p in (path,*path.parents)), 'Literal non-symlink mounted path')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);OPEN_HANDLES+=1
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=cap,
             'Bounded ordinary single-link mounted file')
        if expected is not None:need(before.st_size==expected['bytes'],'Exact expected extent before capture')
        with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(cap+1)
        after=os.fstat(fd);linked=path.lstat()
        need(len(raw)==before.st_size and all(getattr(before,k)==getattr(after,k)==getattr(linked,k)
             for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')), 'Stable complete capture')
    finally:
        os.close(fd);OPEN_HANDLES-=1
    if expected is not None:need(pin(raw)=={k:expected[k] for k in ('bytes','sha256')},'Exact captured content')
    return raw


def source(name):
    if name in MODULES:return MODULES[name]
    expected=BINDINGS['sources'][name]
    raw=bounded('/source/'+name+'.py',131072,expected)
    alias=name if name in ('choice_export_validation','choice_projection') else '_neural094_trusted_'+name
    module=ModuleType(alias);module.__file__='/source/'+name+'.py'
    if name in ('choice_export_validation','choice_projection'):
        need(alias not in sys.modules,'No source alias shadowing');sys.modules[alias]=module
    exec(compile(raw,module.__file__,'exec'),module.__dict__)
    CAPTURED[name]=raw;MODULES[name]=module
    return module


def write_bytes(out,name,raw,cap):
    global OPEN_HANDLES
    need(type(raw) is bytes and 0<len(raw)<=cap and re.fullmatch(r'[A-Z][A-Z_]*\.(json|pkl)',name),
         'Exact bounded worker output filename')
    fd=os.open(out/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);OPEN_HANDLES+=1
    try:
        view=memoryview(raw)
        while view:
            need(time.monotonic()<DEADLINE,'Publication stays inside worker deadline')
            n=os.write(fd,view);need(n>0,'Complete output progress');view=view[n:]
        os.fsync(fd)
    finally:
        os.close(fd);OPEN_HANDLES-=1
    return {'filename':name,**pin(raw)}


def publish(out,name,value,cap=META_CAP):
    return write_bytes(out,name,canonical(value),cap)


def request_contract(request,mode):
    need(type(request) is dict and set(request)=={'schema','execution_authority','mode','ordinal',
         'candidate_sha256','reference_sha256','worker_seconds','eligibility_adoption','worker_guards','payload'}
         and request['schema']=='neural094_trusted_worker_request_v1' and request['execution_authority'] is False
         and request['mode']==mode and mode in WORK_LIMITS,'Exact source-only request; external authority separate')
    seconds=request['worker_seconds']
    need(type(seconds) in (int,float) and math.isfinite(seconds) and 1<seconds<=WORK_LIMITS[mode], 'Fixed finite relative ceiling')
    need(request['reference_sha256']==BINDINGS['reference_source_sha256']
         and request['eligibility_adoption']==BINDINGS['eligibility_adoption'], 'Exact frozen reference and genuine support adoption')
    descriptor(request['worker_guards'],131072)
    need(request['worker_guards']==BINDINGS['sources']['worker_guards'],'Exact frozen bridge-guard source')
    if mode=='grade':need(request['ordinal'] is None and digest(request['candidate_sha256']),'One all39 final candidate identity')
    else:need(type(request['ordinal']) is int and 1<=request['ordinal']<=39
              and request['candidate_sha256'] is None,'One source ordinal, no candidate access in reference/export')
    need(type(request['payload']) is dict and set(request['payload'])==set(PAYLOAD_KEYS[mode]),'Exact mode payload, no query fit input')
    return seconds


def support_adoption():
    doc=strict(bounded('/control/ELIGIBILITY_ADOPTION.json',16384,BINDINGS['eligibility_adoption']))
    need(doc['schema']=='root_neural094_all39_eligibility_scientific_adoption_v1'
         and doc['root_adopted'] is True and doc['status']=='accepted_complete_all39_eligibility'
         and doc['sessions']==39 and doc['mice']==10 and doc['eligible_rows']==10050
         and doc['partition_rows']=={'fit':6014,'validation':1994,'query':2042}
         and doc['original_row_support_preserved'] is True and doc['physical_packets_written']==0
         and doc['models_fitted']==0 and doc['known_shared_seconds']==153210
         and doc['execution_authority'] is False, 'Actual complete eligibility is historical support, not current cost or authority')


def support_row(row,ordinal):
    expected=BINDINGS['cohort'][ordinal-1];q=expected['source_partitions']['query']
    need(type(row) is dict and set(row)=={'ordinal','session','mouse','session_token','query_tokens','query_source_rows',
         'public_manifests','private_mapping'} and type(row['ordinal']) is int
         and all(row[k]==expected[k] for k in ('ordinal','session','mouse')) and digest(row['session_token']),
         'Original source identity and label-free support ABI')
    need(row['query_source_rows']==list(range(q['original_source_row_start'],q['original_source_row_stop_exclusive']))
         and all(type(i) is int for i in row['query_source_rows']) and type(row['query_tokens']) is list
         and len(row['query_tokens'])==q['source_rows'] and all(digest(t) for t in row['query_tokens'])
         and len(set(row['query_tokens']))==len(row['query_tokens']), 'Every actual adopted original query row, no label-based filtering')
    need(type(row['public_manifests']) is dict and set(row['public_manifests'])==set(ARMS),'Both query support pins')
    for v in row['public_manifests'].values():descriptor(v,META_CAP)
    descriptor(row['private_mapping'],4*META_CAP)
    return row


def read_support(pin_value,ordinal,alias='/control/SUPPORT.json'):
    descriptor(pin_value,META_CAP)
    return support_row(strict(bounded(alias,META_CAP,pin_value)),ordinal)


def archive_contract(raw,np):
    """Check header extent before np.load can allocate from a hostile shape."""
    with zipfile.ZipFile(io.BytesIO(raw),'r') as archive:
        entries=archive.infolist();names=[x.filename for x in entries]
        need(0<len(entries)<=16 and len(set(names))==len(names)
             and all(re.fullmatch(r'[a-z_]+\.npy',x) for x in names)
             and all(not x.flag_bits&1 and x.file_size>0 for x in entries)
             and sum(x.file_size for x in entries)<=PACKET_CAP,'Bounded unique numeric NPZ members before decode')
        for entry in entries:
            with archive.open(entry,'r') as stream:
                version=np.lib.format.read_magic(stream)
                need(version in ((1,0),(2,0)),'Only fixed ordinary NPY header versions')
                reader=np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0
                shape,fortran,dtype=reader(stream,max_header_size=10000)
                need(type(shape) is tuple and len(shape)==1 and type(shape[0]) is int and shape[0]>=0
                     and not dtype.hasobject and dtype.kind in 'biuf' and dtype.fields is None
                     and shape[0]*dtype.itemsize==entry.file_size-stream.tell(),
                     'Complete numeric one-dimensional extent before allocation, no object or oversized header')
    return True


def packet(manifest_pin,phase,np,validation):
    descriptor(manifest_pin,META_CAP)
    raw=bounded('/packet/MANIFEST.json',META_CAP,manifest_pin);doc=strict(raw);validation.validate_manifest(doc)
    need(doc['phase']==phase and doc['arm']=='context_wheel_neural','Only exact requested reference packet phase')
    result={};total=len(raw)
    for name,spec in doc['files'].items():
        total+=spec['bytes'];need(total<=PACKET_CAP,'Complete packet retained bound')
        data=bounded('/packet/'+name,PACKET_CAP,spec)
        archive_contract(data,np)
        with np.load(io.BytesIO(data),allow_pickle=False) as archive:
            arrays={key:archive[key] for key in archive.files}
        need(all(type(a) is np.ndarray and a.dtype.kind in 'biuf' and a.ndim==1 for a in arrays.values()),
             'Only native numeric vectors, no pickle/object/unbounded dimensions')
        result[name]=arrays;tick()
    return result,doc


def pure_binding_validator():
    raw=bounded('/source/eligibility_worker.py',131072,BINDINGS['sources']['eligibility_worker'])
    nodes=[n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name in ('need','clean_pin','validate_bindings')]
    need(len(nodes)==3,'Exact unchanged three pure eligibility binding functions')
    namespace={};exec(compile(ast.Module(body=nodes,type_ignores=[]),'<captured-eligibility-binding>','exec'),namespace)
    return namespace['validate_bindings']


def export_inputs_contract(inputs,ordinal):
    need(type(inputs) is dict and set(inputs)==set(BINDINGS['export_inputs'])|{'schema','execution_authority','choice_member'}
         and inputs['schema']=='neural094-candidate-native-export-inputs-v1' and inputs['execution_authority'] is False,
         'Exact export inputs, no arbitrary paths/deadline')
    need(all(inputs[k]==v for k,v in BINDINGS['export_inputs'].items())
         and inputs['choice_member']==BINDINGS['choice_members'][ordinal-1],
         'Exact source/metadata aliases and original selected choice member')
    return True


def export_phase(request,out,np,modules):
    payload=request['payload']
    need(set(payload)=={'inputs','artifact_relative_root','token_key'},'Exact export payload')
    exporter=source('export');projection=source('projection');census=source('census');census.DEADLINE=WORK_END
    need(census.np is np,'Same isolated numerical dependency')
    guards=census.invented_guards();need(len(guards)==29 and all(r['passed'] is True for r in guards),'Original29 guards before data')
    primitive=source('primitive_guards').run(np=np,census=census,old_projection=projection,choice=modules['choice'])
    need(primitive['status']=='passed' and primitive['count']==52,'All52 primitive guards')
    integration=source('integration_guards').run(np=np,census=census,projection=projection,choice=modules['choice'],
        export=exporter,validation=modules['validation'],validate_bindings=pure_binding_validator(),export_source=CAPTURED['export'])
    need(integration['status']=='passed' and integration['count']==27,'All27 integration guards')
    generated=publish(out,'GENERATED.json',{'status':'passed','counts':[29,52,27],'empirical_inputs_opened':0})
    descriptor(payload['token_key'],32);key=bounded('/control/TOKEN_KEY.bin',32,payload['token_key']);need(len(key)==32,'Private256bit exporter key')
    inputs=dict(payload['inputs']);export_inputs_contract(inputs,request['ordinal'])
    inputs['deadline_monotonic']=WORK_END
    root=out/'export';root.mkdir(mode=0o700);counters=ACTIVE_COUNTERS
    result=exporter.export_session(inputs,request['ordinal'],root,payload['artifact_relative_root'],key,np,tick,counters);del key
    need(result['status']=='complete_native_public_private_export'
         and result['all39_support_passed_before_empirical_read'] is result['all39_choice_schema_joined_before_empirical_read'] is True,
         'Complete reviewed export')
    expected=BINDINGS['cohort'][request['ordinal']-1]
    need(result['eligible_partition_rows']=={k:v['source_rows'] for k,v in expected['source_partitions'].items()},
         'Exact actual adopted full support reproduced')
    private=strict(bounded(root/'private/SESSION.json',4*META_CAP,result['private_mapping']))
    row={k:private[k] for k in ('ordinal','session','mouse','session_token')}
    row.update(query_tokens=[r['token'] for r in private['query']],query_source_rows=[r['source_row'] for r in private['query']],
        public_manifests={a:result['public_manifests'][a]['query'] for a in ARMS},private_mapping=result['private_mapping'])
    support_row(row,request['ordinal']);del private
    saved=publish(out,'SUPPORT.json',row)
    return {'status':'complete_trusted_export','export_receipt':publish(out,'EXPORT_RECEIPT.json',result),
            'support':saved,'generated':generated,'empirical_estimator_fit_attempts':0,'query_label_scoring_calls':0,
            'retained':result['retained'],'source_support_adoption':BINDINGS['eligibility_adoption']}


class CappedBuffer(io.BytesIO):
    def write(self,raw):
        # Pickle protocol5 may supply PickleBuffer; count bytes, not elements.
        # Keep BytesIO's original contiguous-buffer admission; make no copy.
        with memoryview(raw) as view:
            size=view.nbytes
            need(self.tell()+size<=MODEL_CAP,'Complete trusted artifact cap, no truncation');tick()
            written=super().write(raw)
            need(type(written) is int and written==size,'Complete trusted artifact write')
            return written


def serialize_trusted(bundle):
    """Only our own fitted states: no candidate deserialization or arbitrary class input."""
    with CappedBuffer() as stream:
        pickle.dump(bundle,stream,protocol=5)
        return stream.getvalue()


def deserialize_trusted(raw,expected):
    need(pin(raw)=={k:expected[k] for k in ('bytes','sha256')} and len(raw)<=MODEL_CAP,'Authenticate complete trusted bytes BEFORE pickle')
    with io.BytesIO(raw) as stream:
        value=pickle.load(stream)
        need(stream.read(1)==b'','No trailing pickle data')
    return value


def reference_fit_phase(request,out,np,modules,stack):
    payload=request['payload'];need(set(payload)=={'fitval_manifest'},'Fit has no query/support/private/model input')
    ref=modules['reference'];Logistic,HGB,Warning,versions=stack
    generated=source('reference_guards').run(np,ref,modules['choice'],modules['validation'],Logistic,HGB,Warning,versions,tick)
    need(generated['status']=='passed' and generated['count']==34,'All34 fixed-reference synthetic guards before empirical packet')
    generated_pin=publish(out,'GENERATED.json',generated)
    data,manifest=packet(payload['fitval_manifest'],'fitval',np,modules['validation'])
    expected=BINDINGS['cohort'][request['ordinal']-1]['source_partitions']
    need(manifest['case_splits']==['fit']*expected['fit']['source_rows']+['validation']*expected['validation']['source_rows'],
         'Full adopted original fit and validation supports')
    counters=ACTIVE_COUNTERS
    bundle,report=ref.fit_references(data,manifest,BINDINGS['reference_source_sha256'],versions=versions,np=np,
        choice=modules['choice'],validator=modules['validation'],LogisticRegression=Logistic,
        HistGradientBoostingClassifier=HGB,ConvergenceWarning=Warning,tick=tick,counters=counters)
    need(set(bundle['states'])==set(REFERENCES) and report['models_committed'] is False
         and counters.get('estimator_fit_attempts',0)<=15,'All4 final states, exact15 maximum empirical estimator fits')
    raw=serialize_trusted(bundle);model=write_bytes(out,'TRUSTED_MODEL.pkl',raw,MODEL_CAP)
    # Roundtrip the exact saved representation before claiming fit completion.
    reloaded=deserialize_trusted(raw,model)
    need(reloaded['schema']==bundle['schema'] and reloaded['reference_sha256']==bundle['reference_sha256']
         and set(reloaded['states'])==set(REFERENCES),'Complete4-state trusted serialization roundtrip')
    report.update(model_artifact=model,empirical_fit_counters=counters,generated=generated_pin,
                  serialization_roundtrip_verified=True,model_commitment_pending_external_closure=True)
    return {'status':'complete_trusted_reference_fit','model_artifact':model,
            'fit_report':publish(out,'FIT_REPORT.json',report),'generated':generated_pin,
            'empirical_estimator_fit_attempts':counters.get('estimator_fit_attempts',0),
            'query_features_read':False,'query_targets_read':0,'models_committed':False}


def model_commitment(value,payload,request):
    need(type(value) is dict and set(value)=={'schema','reference_sha256','session_token','all_four_states_committed_before_query',
         'fit_process_closed','sealed_readonly','artifact_sha256_verified_by_loader','artifact'}
         and value['schema']=='neural094_trusted_reference_model_commit_v1'
         and value['reference_sha256']==request['reference_sha256']
         and digest(value['session_token'])
         and value['all_four_states_committed_before_query'] is value['fit_process_closed'] is value['sealed_readonly'] is True
         and value['artifact_sha256_verified_by_loader'] is True and value['artifact']==payload['model_artifact'],
         'Exact authenticated host4-state closure/seal before query; no candidate model')
    descriptor(value['artifact'],MODEL_CAP)
    return value


def reference_json(result,row,reference_sha256,ref,np):
    need(type(result) is dict and set(result)==set(REFERENCES),'All4 reference views')
    views={}
    for key in REFERENCES:
        matrix=ref.probability_admission(result[key],len(row['query_tokens']),np)
        views[key]=[{'token':token,'probabilities':[float(v) for v in probs]}
                    for token,probs in zip(row['query_tokens'],matrix,strict=True)]
    return {'schema':'neural094-trusted-reference-predictions-v1','reference_sha256':reference_sha256,
        'ordinal':row['ordinal'],'session_token':row['session_token'],'class_order':['right','NoGo','left'],
        'query_tokens':row['query_tokens'],'query_source_rows':row['query_source_rows'],'views':views,
        'fresh094_choice_reference':True,'selected_on_fit_validation_only':True,'refit_on_fit_validation_only':True,
        'query_targets_used_for_fit_or_selection':False}


def reference_infer_phase(request,out,np,modules,stack):
    payload=request['payload']
    need(set(payload)=={'query_manifest','support','model_artifact','model_commitment'},'Exact inference inputs without private targets')
    descriptor(payload['model_commitment'],META_CAP)
    commit=model_commitment(strict(bounded('/control/MODEL_COMMIT.json',META_CAP,payload['model_commitment'])),payload,request)
    row=read_support(payload['support'],request['ordinal'])
    need(row['public_manifests']['context_wheel_neural']==payload['query_manifest'] and row['session_token']==commit['session_token'],
         'Saved reference and exact source-bound query packet')
    raw=bounded('/model/TRUSTED_MODEL.pkl',MODEL_CAP,payload['model_artifact'])
    saved=deserialize_trusted(raw,payload['model_artifact']);del raw
    # Query archive loading occurs after authenticated host commitment and trusted artifact capture.
    data,manifest=packet(payload['query_manifest'],'query',np,modules['validation'])
    need(manifest['case_tokens']==row['query_tokens'],'Exact full query source support')
    counters=ACTIVE_COUNTERS;_,_,Warning,versions=stack
    result,report=modules['reference'].infer_references(saved,data,manifest,commit,versions=versions,np=np,
        choice=modules['choice'],validator=modules['validation'],ConvergenceWarning=Warning,tick=tick,counters=counters)
    need(counters.get('estimator_fit_attempts',0)==0 and report['query_fits']==0,'No empirical fits in query process')
    doc=reference_json(result,row,request['reference_sha256'],modules['reference'],np)
    raw=canonical(doc);need(len(raw)<=16*META_CAP,'Complete4-view scorer bridge cap')
    # Validate the exact serialized scorer ABI before publication; no target is read.
    fake_pin={'path':'trusted/REFERENCE_PREDICTIONS.json',**pin(raw)}
    source('score_adapter').reference_predictions(raw,fake_pin,row,request['reference_sha256'],source('metric_core'),np)
    result_pin=write_bytes(out,'REFERENCE_PREDICTIONS.json',raw,16*META_CAP)
    return {'status':'complete_trusted_reference_inference','reference_predictions':result_pin,
            'inference_report':publish(out,'INFERENCE_REPORT.json',report),'empirical_estimator_fit_attempts':0,
            'query_targets_read':0,'all_four_views':list(REFERENCES)}


def grade_phase(request,out,np,modules):
    payload=request['payload'];need(set(payload)=={'supports','combined_commit'},'Exact all39 grade metadata')
    need(type(payload['supports']) is list and len(payload['supports'])==39,'Every original session support descriptor')
    scorer=source('score_adapter');core=source('metric_core')
    generated=source('score_guards').run(np,scorer,core,modules['validation'])
    need(generated['status']=='passed' and generated['count']==58,'All58 scorer guards before any actual candidate/private reads')
    generated_pin=publish(out,'GENERATED.json',generated)
    descriptor(payload['combined_commit'],4*META_CAP)
    commit=strict(bounded('/control/ALL78_COMMIT.json',4*META_CAP,payload['combined_commit']))
    roster=[read_support(p,i,f'/support/{i:02d}.json') for i,p in enumerate(payload['supports'],1)]
    scorer.roster_contract(roster)
    need(type(commit.get('sessions')) is list and len(commit['sessions'])==39,'Complete actual78-output commit')
    public=[]
    for row,saved in zip(roster,commit['sessions'],strict=True):
        i=row['ordinal'];query={};predictions={}
        for arm in ARMS:
            query[arm]={'pin':row['public_manifests'][arm],
                'body':bounded(f'/query/{i:02d}/{arm}/MANIFEST.json',META_CAP,row['public_manifests'][arm])}
            d=saved['arms'][arm]['prediction'];descriptor(d,4*META_CAP)
            predictions[arm]=bounded(f'/predictions/{i:02d}/{arm}/predictions.json',4*META_CAP,d)
        public.append({'ordinal':i,'session_token':row['session_token'],'query_packets':query,'predictions':predictions})
    private_map={r['private_mapping']['path']:(r['private_mapping'],f'/private/{r["ordinal"]:02d}/SESSION.json') for r in roster}
    reference_map={s['trusted_reference_prediction']['path']:(s['trusted_reference_prediction'],f'/references/{i:02d}/REFERENCE_PREDICTIONS.json')
                   for i,s in enumerate(commit['sessions'],1)}
    need(len(private_map)==len(reference_map)==39,'No alias collision among private/reference inputs')
    calls=[]
    def private_loader(d):
        tick();need(d['path'] in private_map and private_map[d['path']][0]==d,'Exact closed private callback descriptor')
        calls.append(('private',d['path']));return bounded(private_map[d['path']][1],4*META_CAP,d)
    def reference_loader(d):
        tick();need(d['path'] in reference_map and reference_map[d['path']][0]==d,'Exact closed reference callback descriptor')
        calls.append(('reference',d['path']));return bounded(reference_map[d['path']][1],16*META_CAP,d)
    try:
        result=scorer.score_cohort(public,commit,roster,request['candidate_sha256'],request['reference_sha256'],
            private_loader,reference_loader,core,modules['validation'],np)
    except ValueError as exc:
        if not calls:publish(out,'PUBLIC_REJECTION.json',{'schema':'neural094_all39_public_rejection_v1',
            'status':'rejected_before_any_private_callback','private_callbacks':0,'error':str(exc)[:2000]},65536)
        raise
    need([x[0] for x in calls]==['private','reference']*39 and result['public_predictions_validated_before_any_private_callback']==78
         and result['arrays_or_trial_losses_exported'] is False,'All78 public validation then exact39 private/reference callback pairs')
    return {'status':'complete_all39_trusted_grade','score':publish(out,'SCORE.json',result,4*META_CAP),
        'generated':generated_pin,'private_mapping_callbacks':39,'trusted_reference_callbacks':39,
        'public_predictions_validated_before_any_private_callback':78,'empirical_estimator_fit_attempts':0,
        'candidate_models_deserialized':False,'trial_arrays_exported':False}


def main(argv=None):
    global DEADLINE,WORK_END,BINDINGS
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=tuple(WORK_LIMITS))
    parser.add_argument('--request',required=True);parser.add_argument('--request-sha256',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    need(args.request=='/control/request.json' and args.output=='/output' and digest(args.request_sha256),'Fixed trusted entrypoint aliases')
    BINDINGS=strict(bounded('/source/BINDINGS.json',65536,BINDINGS_PIN))
    raw=bounded(args.request,REQUEST_CAP);need(pin(raw)['sha256']==args.request_sha256,'Exact immutable request bytes')
    request=strict(raw);seconds=request_contract(request,args.mode)
    DEADLINE=STARTED+seconds;WORK_END=DEADLINE-1
    need(time.monotonic()<WORK_END,'Request/source preparation charged to same worker clock')
    def alarm(*unused):raise Deadline('Trusted worker wall deadline')
    signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,max(.001,WORK_END-time.monotonic()))
    out=Path(args.output);need(out.is_dir() and all(not p.is_symlink() for p in (out,*out.parents)) and not any(out.iterdir()),'Fresh owned output')
    receipt={'schema':'neural094_trusted_worker_terminal_v1','execution_authority':False,'mode':args.mode,
        'ordinal':request['ordinal'],'request':pin(raw),'reference_sha256':request['reference_sha256'],
        'candidate_sha256':request['candidate_sha256'],'local_allowance_seconds':seconds,'status':'started'}
    code=1
    try:
        tick();support_adoption()
        modules={'validation':source('choice_export_validation'),'choice':source('choice_projection')}
        guards_raw=bounded('/source/generated_guards.py',131072,request['worker_guards'])
        guards=ModuleType('_neural094_trusted_bridge_guards');exec(compile(guards_raw,'/source/generated_guards.py','exec'),guards.__dict__)
        bridge=guards.run(sys.modules[__name__]);need(bridge['status']=='passed' and bridge['count']==30,'All30 new bridge guards before empirical inputs')
        receipt['bridge_guards']=bridge
        import numpy as np
        numeric_bridge=guards.run_numeric(np,sys.modules[__name__])
        need(numeric_bridge['status']=='passed' and numeric_bridge['count']==8,'All8 archive/serialization guards before empirical input')
        receipt['numeric_bridge_guards']=numeric_bridge
        if args.mode.startswith('reference_'):
            import scipy
            import sklearn
            from sklearn.linear_model import LogisticRegression
            from sklearn.ensemble import HistGradientBoostingClassifier
            from sklearn.exceptions import ConvergenceWarning
            versions={'numpy':np.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__}
            modules['reference']=source('reference');modules['reference'].stack_versions(versions)
            stack=(LogisticRegression,HistGradientBoostingClassifier,ConvergenceWarning,versions)
        else:need(np.__version__=='2.2.6','Exact isolated NumPy stack')
        tick()
        if args.mode=='export':receipt.update(export_phase(request,out,np,modules))
        elif args.mode=='reference_fit':receipt.update(reference_fit_phase(request,out,np,modules,stack))
        elif args.mode=='reference_infer':receipt.update(reference_infer_phase(request,out,np,modules,stack))
        else:receipt.update(grade_phase(request,out,np,modules))
        tick();code=0
    except BaseException as exc:
        receipt.update(status='failed_trusted_worker',error_type=type(exc).__name__,error=str(exc)[:2000])
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        receipt['worker_elapsed_seconds']=time.monotonic()-STARTED
        receipt['all_worker_owned_capture_handles_closed']=OPEN_HANDLES==0
        receipt['empirical_counters']=ACTIVE_COUNTERS
        # No clock extension: absent terminal publication remains an external failure.
        publish(out,'WORKER_RECEIPT.json',receipt)
    return code


if __name__=='__main__':raise SystemExit(main())
