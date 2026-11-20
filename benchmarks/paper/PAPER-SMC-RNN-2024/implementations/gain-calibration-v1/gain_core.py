"""Frozen global-rate calibration lineage and protected selection preparation.

No model, target or numerical work occurs during source/method preparation.
Selection is subordinate to the selected bounded host; target-free submission
admits that host's saved owned closure before using the frozen gain.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import types

META_CAP = 128 * 1024
FILE_CAP = 512 * 1024 * 1024
ROUTE = 'smc_valid_global_rate_gain_calibration_v1'
GRID = [[1,1],[8,9],[9,8],[4,5],[5,4],[2,3],[3,2],[1,2],[2,1]]
KERNEL_FILES = {'gain_core.py','gain_selector.py','gain_transform.py','METHOD.json'}
RUNTIME_FILES = {'gain_selector_host.py','gain_selector_child.py','owned_exit.py','bounded_capture.py','label_policy.py'}
METHOD_PIN = {'bytes':3001,'sha256':'5c10c138ccfc86fd43fd2eb8f681ce1aaf3c51235335e17b31a055b5efa647f4'}
VALIDATION_PIN = {'bytes':24571,'sha256':'d794e972069784833093b32f03e74345cd41d6f19d4a82c1e08dc88875819a38'}
EVALUATOR_PIN = {'bytes':18292,'sha256':'05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476'}
TARGET_SHA256 = 'e49d7ba5ab99adc1ab8a065b425051446c6a320a50fcbe646fe8ce54335baf48'
RATE_KEYS = tuple(f'{split}_rates_{units}{suffix}' for split in ('train','eval') for suffix in ('','_forward') for units in ('heldin','heldout'))
SHAPES = {name:[1721 if name.startswith('train_') else 574,10 if name.endswith('_forward') else 35,137 if 'heldin' in name else 45] for name in RATE_KEYS}
ARITHMETIC_POLICY = 'gain numerator/denominator and multiplication in source float32/float64 precision, preserving source byte order; canonical metric receives disposable float64 copies of submitted rounded rates; zero preserved; positive underflow and nonfinite refused'
TIE_RULE = 'maximum canonical co-bps; exact tie earliest declared index'
METHOD_KEYS = {'schema','source','declaration','baseline_freeze','baseline_prediction','validation_source','runtime_source','lineage','grid','arithmetic_policy','selection_metric','tie_rule'}
REQUEST_KEYS = {'schema','source','method','baseline_freeze','target','evaluator','output_root'}

def need(ok, message):
    if not ok:
        raise ValueError(message)

def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def decode(raw):
    def unique(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'duplicate JSON field')
            value[key] = item
        return value
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:need(False,'finite JSON'))

def pin(raw):
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def absolute(value):
    need(isinstance(value,(str,Path)), 'absolute path type')
    text = str(value)
    need(not any(c in text for c in ('\0','\n','\r')), 'unambiguous path')
    p = Path(text)
    need(p.is_absolute() and '..' not in p.parts and str(p)==text, 'canonical absolute path')
    return p

def ordinary(value):
    p = absolute(value)
    need(not any(q.is_symlink() for q in (p,*p.parents)), 'no named-path symlink')
    return p

def signature(value):
    return tuple(getattr(value,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))

def body(value, cap=META_CAP):
    p = ordinary(value)
    fd = os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=cap,
             'bounded ordinary single-link file')
        raw = stream.read(cap+1)
        after = os.fstat(stream.fileno())
    need(len(raw)==before.st_size and signature(before)==signature(after)==signature(p.lstat()),
         'stable complete named metadata')
    return raw

def content_pin(value, cap=FILE_CAP):
    p = ordinary(value)
    fd = os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=cap,
             'bounded ordinary single-link payload')
        h = hashlib.sha256(); count = 0
        while True:
            block = stream.read(min(1024*1024,cap-count+1))
            if not block:
                break
            count += len(block); need(count<=cap,'payload byte limit'); h.update(block)
        after = os.fstat(stream.fileno())
    need(count==before.st_size and signature(before)==signature(after)==signature(p.lstat()),
         'stable complete payload authentication')
    return {'bytes':count,'sha256':h.hexdigest()}

def validate_pin(value, cap=FILE_CAP):
    need(type(value) is dict and set(value)=={'bytes','sha256'}
         and type(value['bytes']) is int and 0<value['bytes']<=cap
         and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']),
         'exact bounded content pin')
    return value

def descriptor(value, cap=FILE_CAP):
    need(type(value) is dict and set(value)=={'path','bytes','sha256'}, 'exact file descriptor')
    absolute(value['path']); validate_pin({k:value[k] for k in ('bytes','sha256')},cap)
    return value

def checked(value, cap=META_CAP):
    descriptor(value,cap); raw = body(value['path'],cap)
    need(pin(raw)=={k:value[k] for k in ('bytes','sha256')}, 'authenticated metadata descriptor')
    return raw

def publish(path, value):
    p = ordinary(path); raw = encoded(value); need(len(raw)<=META_CAP,'metadata publication cap')
    fd = os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    with os.fdopen(fd,'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return {'path':str(p),**pin(raw)}

def fresh_root(value):
    p = ordinary(value)
    need(p.parent.is_dir() and not os.path.lexists(p), 'fresh private output directory')
    p.mkdir(mode=0o700)
    return p

def copy_snapshot(source, destination, expected=None):
    """Copy compressed serialization exactly; no HDF5 rewrite or target access."""
    source,destination = ordinary(source),ordinary(destination)
    need(source!=destination, 'distinct immutable snapshot')
    fd = os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as incoming:
        before = os.fstat(incoming.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=FILE_CAP,
             'bounded snapshot source')
        outfd = os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        with os.fdopen(outfd,'wb') as outgoing:
            h = hashlib.sha256(); count = 0
            while True:
                block = incoming.read(min(1024*1024,FILE_CAP-count+1))
                if not block:
                    break
                count += len(block); need(count<=FILE_CAP,'snapshot byte limit')
                outgoing.write(block); h.update(block)
            outgoing.flush(); os.fsync(outgoing.fileno())
        after = os.fstat(incoming.fileno())
    need(count==before.st_size and signature(before)==signature(after)==signature(source.lstat()),
         'snapshot source remained stable')
    result = {'bytes':count,'sha256':h.hexdigest()}
    if expected is not None:
        need(result==validate_pin(expected), 'snapshot matches frozen prediction bytes')
    need(content_pin(destination)==result,'complete immutable snapshot bytes')
    return {'path':str(destination),**result}


def same(left, right):
    return encoded(left) == encoded(right)


def source_identity():
    filename = Path(__file__).absolute().with_name('SOURCE.json')
    return {'path':str(filename), **pin(body(filename))}


def authenticate_kernel(source):
    record = decode(checked(source))
    need(type(record) is dict and set(record)=={'schema','files'} and record['schema']=='smc_gain_kernel_source_v1'
         and type(record['files']) is dict and set(record['files'])==KERNEL_FILES, 'exact gain kernel source roster')
    root = ordinary(source['path']).parent
    blobs = {}
    for name, expected in record['files'].items():
        validate_pin(expected, META_CAP)
        raw = body(root/name)
        need(same(pin(raw),expected), 'authenticated gain kernel leaf')
        blobs[name] = raw
    need(same(record['files']['METHOD.json'],METHOD_PIN), 'fixed predeclared scientific method')
    declaration = decode(blobs['METHOD.json'])
    need(same(declaration['ordered_gain_rationals'],GRID), 'fixed ordered rational grid')
    return record, blobs


def execute_source(name, filename, raw):
    module = types.ModuleType(name)
    module.__file__ = str(filename)
    exec(compile(raw,str(filename),'exec',dont_inherit=True),module.__dict__)
    return module


def load_kernel_module(name, source):
    need(name in {'gain_selector','gain_transform'}, 'fixed gain kernel module')
    record, blobs = authenticate_kernel(source)
    return execute_source('smc_authenticated_'+name,ordinary(source['path']).parent/(name+'.py'),blobs[name+'.py'])


def load_validation(selected):
    need(same({k:descriptor(selected,META_CAP)[k] for k in ('bytes','sha256')},VALIDATION_PIN), 'unchanged accepted VALID freeze/scorer source')
    return execute_source('smc_gain_original_validation',selected['path'],checked(selected))


def authenticate_runtime(source):
    record = decode(checked(source))
    need(type(record) is dict and set(record)=={'schema','files','kernel'}
         and record['schema']=='smc_gain_selector_runtime_source_v1'
         and type(record['files']) is dict and set(record['files'])==RUNTIME_FILES,
         'exact selected bounded selector runtime')
    need(same(record['kernel'],{k:source_identity()[k] for k in ('bytes','sha256')}), 'runtime binds this exact gain kernel')
    root = ordinary(source['path']).parent
    blobs = {}
    for name, expected in record['files'].items():
        validate_pin(expected,META_CAP); raw = body(root/name)
        need(same(pin(raw),expected), 'authenticated bounded selector runtime leaf')
        blobs[name] = raw
    return record, blobs


def baseline_metadata(freeze_descriptor, validation):
    freeze = decode(checked(freeze_descriptor))
    need(type(freeze) is dict and set(freeze)==validation.FREEZE_KEYS
         and freeze['schema']=='smc_restricted_validation_prediction_freeze_v1'
         and freeze['route']==validation.ROUTE and freeze['phase']=='val' and freeze['role']=='reference'
         and same(freeze['source'],VALIDATION_PIN) and same(freeze['shapes'],SHAPES),
         'original source-bound reference VALID freeze metadata')
    for flag in ('target_accessed_by_freeze','inference_execution_qualified','pipeline_execution_qualified','physical_owner_qualified'):
        need(freeze[flag] is False, 'freeze is byte custody, not inferred operational qualification')
    snapshot = freeze['snapshot']
    need(type(snapshot) is dict and set(snapshot)=={'filename','bytes','sha256'} and snapshot['filename']=='prediction.h5',
         'exact original prediction snapshot selector')
    validate_pin({k:snapshot[k] for k in ('bytes','sha256')})
    validation.validate_panel(freeze['panel'])
    validation.validate_packet_metadata(freeze['packet'])
    validation.validate_method(freeze['method'],freeze['packet'],'reference')
    lineage = {'phase':'val','dataset':'mc_maze_20','panel':freeze['panel'],'packet':freeze['packet'],
               'reference_method':freeze['method'],'baseline_freeze':dict(freeze_descriptor),
               'baseline_prediction':{k:snapshot[k] for k in ('bytes','sha256')},
               'checkpoint_provenance':{'author_commit':validation.AUTHOR_COMMIT,'fit_cohort':'unknown'}}
    return freeze,lineage


def prepare_method(source_descriptor, baseline_freeze_descriptor, validation_source_descriptor,
                   runtime_source_descriptor, output_path):
    """Target-free metadata freeze. Prediction body admission happens in the child."""
    authenticate_kernel(source_descriptor)
    need(same(source_descriptor,source_identity()), 'selected executing method-freeze source')
    authenticate_runtime(runtime_source_descriptor)
    validation = load_validation(validation_source_descriptor)
    freeze,lineage = baseline_metadata(baseline_freeze_descriptor,validation)
    record = {'schema':'smc_gain_method_freeze_v1','source':dict(source_descriptor),
              'declaration':dict(METHOD_PIN),'baseline_freeze':dict(baseline_freeze_descriptor),
              'baseline_prediction':lineage['baseline_prediction'],
              'validation_source':dict(validation_source_descriptor),'runtime_source':dict(runtime_source_descriptor),
              'lineage':lineage,'grid':GRID,'arithmetic_policy':ARITHMETIC_POLICY,
              'selection_metric':'canonical VALID co-bps','tie_rule':TIE_RULE}
    return publish(output_path,record)


def admit_method(method_descriptor, source_descriptor, baseline_freeze_descriptor):
    """Metadata/source-only admission; does not stat/read predictions or targets."""
    authenticate_kernel(source_descriptor)
    record = decode(checked(method_descriptor))
    need(type(record) is dict and set(record)==METHOD_KEYS and record['schema']=='smc_gain_method_freeze_v1',
         'exact frozen gain method')
    need(same(record['source'],source_descriptor) and same(record['declaration'],METHOD_PIN)
         and same(record['baseline_freeze'],baseline_freeze_descriptor) and same(record['grid'],GRID)
         and record['arithmetic_policy']==ARITHMETIC_POLICY
         and record['selection_metric']=='canonical VALID co-bps' and record['tie_rule']==TIE_RULE,
         'predeclared source/grid/reference identities')
    descriptor(record['runtime_source'],META_CAP)  # host authenticates full runtime before launch
    validation = load_validation(record['validation_source'])
    freeze,lineage = baseline_metadata(baseline_freeze_descriptor,validation)
    need(same(record['baseline_prediction'],lineage['baseline_prediction']) and same(record['lineage'],lineage),
         'frozen VALID panel/order/checkpoint lineage')
    return {'record':record,'freeze':freeze,'lineage':lineage,'validation_grade':validation}


def prepare_selection(request_path, request_sha256):
    """Authenticate/snapshot full baseline before any target or evaluator body."""
    raw = body(request_path)
    need(pin(raw)['sha256']==request_sha256, 'selected gain request SHA')
    request = decode(raw)
    need(type(request) is dict and set(request)==REQUEST_KEYS and request['schema']=='smc_gain_selection_request_v1',
         'exact protected gain selection request')
    request_descriptor = {'path':str(ordinary(request_path)),**pin(raw)}
    source = request['source']
    need(same(source,source_identity()), 'executed selected gain kernel identity')
    admitted = admit_method(request['method'],source,request['baseline_freeze'])
    descriptor(request['target']); descriptor(request['evaluator'],META_CAP)
    need(request['target']['sha256']==TARGET_SHA256
         and same({k:request['evaluator'][k] for k in ('bytes','sha256')},EVALUATOR_PIN),
         'exact original VALID target and unchanged canonical evaluator selectors')
    # These two descriptors are lexical only until the baseline barrier exists.
    validation = admitted['validation_grade']
    verified = validation.validate_freeze(request['baseline_freeze'])
    need(same(verified['record'],admitted['freeze']), 'same authenticated baseline freeze')
    output = fresh_root(request['output_root'])
    baseline_snapshot = copy_snapshot(verified['snapshot']['path'],output/'baseline.h5',admitted['record']['baseline_prediction'])
    validation.validate_prediction(baseline_snapshot['path'],'reference')
    transform = load_kernel_module('gain_transform',source)
    # The transform's exact eight-field, self-contained HDF5 admission is repeated
    # by selection before target access; original freeze allows two optional fields.
    import h5py
    before = content_pin(baseline_snapshot['path'])
    with h5py.File(baseline_snapshot['path'],'r') as handle:
        transform._inspect(handle,SHAPES,[1,1])
    need(same(content_pin(baseline_snapshot['path']),before), 'stable self-contained complete eight-rate baseline')
    barrier_record = {'schema':'smc_gain_method_baseline_barrier_v1','request_sha256':request_sha256,
                      'source':source,'method':request['method'],'baseline_freeze':request['baseline_freeze'],
                      'baseline_snapshot':baseline_snapshot,'lineage':admitted['lineage'],
                      'method_and_baseline_frozen':True,'target_accessed':False}
    barrier = publish(output/'METHOD_AND_BASELINE_FROZEN.json',barrier_record)
    return {'request':request,'request_descriptor':request_descriptor,'baseline_snapshot':baseline_snapshot,
            'barrier':barrier,'lineage':admitted['lineage'],'source':source,
            'module_map':{'validation_grade':validation,'gain_transform':transform}}


def validate_selection_record(report, method_descriptor, admitted):
    keys = {'schema','route','phase','dataset','status','request_sha256','source','method','baseline_freeze',
            'baseline_snapshot','barrier','lineage','target','evaluator','ordered_scores','selected_index','selected_gain',
            'selected_executed_gain','selected_co_bps','metric','tie_rule','canonical_endpoint',
            'selection_is_development_calibration','heldout_improvement','inference_execution_qualified',
            'physical_owner_qualified','scientific_improvement','SOTA'}
    need(type(report) is dict and set(report)==keys and report['schema']=='smc_gain_selection_report_v1'
         and report['route']==ROUTE and report['phase']=='val' and report['dataset']=='mc_maze_20',
         'typed frozen VALID gain selection')
    need(report['status']=='selected_from_all_nine_canonical_co_bps_scores'
         and report['metric']=='co-bps' and report['tie_rule']=='first_exact_maximum'
         and report['canonical_endpoint']=='original_evaluator.bits_per_spike', 'canonical complete selection semantics')
    descriptor(report['target']); descriptor(report['evaluator'],META_CAP)
    need(report['target']['sha256']==TARGET_SHA256
         and same({k:report['evaluator'][k] for k in ('bytes','sha256')},EVALUATOR_PIN), 'fixed VALID target/evaluator lineage')
    method = admitted['record']
    need(same(report['source'],method['source']) and same(report['method'],method_descriptor)
         and same(report['baseline_freeze'],method['baseline_freeze']) and same(report['lineage'],method['lineage']),
         'selection method and baseline lineage')
    descriptor(report['baseline_snapshot']); descriptor(report['barrier'],META_CAP)
    need(same({k:report['baseline_snapshot'][k] for k in ('bytes','sha256')},method['baseline_prediction']),
         'selected original baseline bytes')
    rows=report['ordered_scores']; need(type(rows) is list and len(rows)==len(GRID),'all nine declared scores')
    transform=load_kernel_module('gain_transform',method['source'])
    for index,(gain,row) in enumerate(zip(GRID,rows)):
        need(type(row) is dict and set(row)=={'index','gain','executed_gain','co_bps'}
             and type(row['index']) is int and row['index']==index and same(row['gain'],gain)
             and type(row['co_bps']) is float and math.isfinite(row['co_bps']), 'ordered finite canonical score')
        execution=row['executed_gain']; need(type(execution) is dict and 'dtype' in execution,'executed dtype record')
        need(same(execution,transform.executed_gain(execution['dtype'],gain)), 'shared dtype-rounded scalar identity')
        if index: need(execution['dtype']==rows[0]['executed_gain']['dtype'],'same source rates dtype for all gains')
    winner=max(range(len(rows)),key=lambda index:rows[index]['co_bps'])
    need(type(report['selected_index']) is int and report['selected_index']==winner
         and same(report['selected_gain'],GRID[winner])
         and same(report['selected_executed_gain'],rows[winner]['executed_gain'])
         and same(report['selected_co_bps'],rows[winner]['co_bps']), 'exact maximum and earliest tie')
    need(report['selection_is_development_calibration'] is True,'same-VALID development scope')
    for flag in ('heldout_improvement','inference_execution_qualified','physical_owner_qualified','scientific_improvement','SOTA'):
        need(report[flag] is False,'no unsupported scientific or operational claim')
    return report


def admit_selected_gain(selection_descriptor, method_descriptor, selector_result_descriptor):
    """Target-free read-only saved selector custody admission."""
    method=decode(checked(method_descriptor))
    need(type(method) is dict and set(method)==METHOD_KEYS,'selected method envelope')
    admitted=admit_method(method_descriptor,method['source'],method['baseline_freeze'])
    need(same(method['source'],source_identity()),'selected transform/kernel source identity')
    runtime,blobs=authenticate_runtime(method['runtime_source'])
    host_path=ordinary(method['runtime_source']['path']).parent/'gain_selector_host.py'
    host=execute_source('smc_gain_selected_host',host_path,blobs['gain_selector_host.py'])
    report=host.admit_completed_selection(selector_result_descriptor,selection_descriptor,
        method_descriptor=method_descriptor,baseline_freeze_descriptor=method['baseline_freeze'])
    report=validate_selection_record(report,method_descriptor,admitted)
    freeze=admitted['freeze']
    baseline={'path':str(ordinary(method['baseline_freeze']['path']).parent/'prediction.h5'),
              **{k:freeze['snapshot'][k] for k in ('bytes','sha256')}}
    return {'gain':report['selected_gain'],'baseline_descriptor':baseline,'method':dict(method_descriptor),
            'selection':dict(selection_descriptor),'lineage':admitted['lineage'],'source':method['source']}


def main():
    parser=argparse.ArgumentParser(description='Target-free gain method freeze; selection requires bounded owner')
    parser.add_argument('--request',required=True); parser.add_argument('--sha256',required=True)
    args=parser.parse_args(); raw=body(args.request)
    need(pin(raw)['sha256']==args.sha256,'method preparation request SHA')
    request=decode(raw)
    need(type(request) is dict and set(request)=={'schema','source','baseline_freeze','validation_source','runtime_source','output'}
         and request['schema']=='smc_gain_method_prepare_request_v1','exact target-free method preparation request')
    result=prepare_method(request['source'],request['baseline_freeze'],request['validation_source'],request['runtime_source'],request['output'])
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
