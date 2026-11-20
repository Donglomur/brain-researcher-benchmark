"""Typed VALID prediction byte custody and original four-metric comparison.

This operator-only module neither executes a candidate nor establishes process,
container, checkpoint-training or inference qualification. A separately selected
owner must prevent inference actors from accessing target/evaluator material.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import stat
import types

DATASET = 'mc_maze_20'
PHASE = 'val'
ROUTE = 'smc_restricted_validation_v1'
ROLES = ('reference', 'candidate')
METRICS = ('co-bps', 'vel R2', 'psth R2', 'fp-bps')
META_CAP = 128 * 1024
FILE_CAP = 512 * 1024 * 1024
PAIR_SNAPSHOT_CAP = 2 * FILE_CAP
PANEL_PIN = {'bytes':5047,'sha256':'773a54ed1cfd1083b6d08fee17c7bcb416088a35b5e65a01d9485a3c7c58158a'}
PROJECTOR_PIN = {'bytes':19882,'sha256':'47adbe1428345d6303243eadcc90efec33dc35b8f6bb519058211d4a1b79d3fb'}
EVALUATOR_PIN = {'bytes':18292,'sha256':'05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476'}
TARGET_SHA256 = 'e49d7ba5ab99adc1ab8a065b425051446c6a320a50fcbe646fe8ce54335baf48'
AUTHOR_COMMIT = 'c808c76ad940491b0a14d2671e3884140aa61258'
ORDER = {
    'trial_indices_sha256':'e2261c95ca4a46b3ca4c14b74bfbf222486f5f39c0c77fd22ffe12d8a97af8ce',
    'neuron_indices_sha256':'1c70f09e86c025e6236367ae6837bd07224bb73e548916e264b9a54dd66baf88',
    'conditions_sha256':'2b21b6d389fdc0ad8d751a9f996c1568d7b1dafbd510b5685354d5602939152e',
    'tensor_trial_indices_sha256':'1180bcd7082f6eec884944481a90e983dc832421bb00cf94f3227b6b99007738',
}
GEOMETRY = {'train_trials':1721,'eval_trials':574,'observed_bins':35,
            'train_forward_bins':10,'heldin_units':137,'heldout_units':45,'bin_size_ms':20}
PACKET_ROLES = {'train':'original_train_only_metric_decoder_inference_inputs',
                'eval':'restricted_validation_observations_only'}
INPUT_SHAPES = {
    'mc_maze/val/train_input_20ms.h5': {
        'train_spikes_heldin':[1721,35,137], 'train_spikes_heldin_forward':[1721,10,137],
        'train_spikes_heldout':[1721,35,45], 'train_spikes_heldout_forward':[1721,10,45]},
    'mc_maze/val/eval_input_20ms.h5': {'eval_spikes_heldin':[574,35,137]},
}
INPUT_CONTENT = {
    'train_spikes_heldin':'a810f84a5063dbf02fc95292266ee577f3b11e6ee33592ba3f29f5e52d47f9fd',
    'train_spikes_heldin_forward':'8e688930a0409c9f303a23696c03463e834eed2adc914a4d79529250790f922f',
    'train_spikes_heldout':'c43d9fb5722cb6d7a9b759b53cf421baad4d9866fb727a77d70a1982e5ee12a3',
    'train_spikes_heldout_forward':'fa741dcdbdcf7b70674cb24b93c0637f79d6c450a7a172708188aa3fd168afc9',
    'eval_spikes_heldin':'5f1ca725d1fd49ae1a318a453a99ac2e6864eabd9acb6ceb1cf518e2a829bb34',
}
REFERENCE_RECIPE = {'arm':'noncausal','seed':20261118,'particles':192,'repeats':32,
                    'smooth':False,'device':'cpu','training':False,'checkpoint_search':False,
                    'access_condition':'paper_data_author_code_and_weights'}
RATE_KEYS = tuple(f'{split}_rates_{units}{suffix}' for split in ('train','eval')
                  for suffix in ('','_forward') for units in ('heldin','heldout'))
OPTIONAL_KEYS = {'train_rates_heldin_forward','train_rates_heldout_forward'}
REQUIRED_KEYS = set(RATE_KEYS) - OPTIONAL_KEYS
SHAPES = {name:[1721 if name.startswith('train_') else 574,
               10 if name.endswith('_forward') else 35,
               137 if 'heldin' in name else 45] for name in RATE_KEYS}
FREEZE_KEYS = {'schema','route','phase','role','source','snapshot','panel','packet','method',
               'shapes','target_accessed_by_freeze','inference_execution_qualified',
               'pipeline_execution_qualified','physical_owner_qualified'}


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


def source_identity():
    return pin(body(Path(__file__).absolute()))


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


def validate_panel(panel_descriptor):
    need({k:descriptor(panel_descriptor,META_CAP)[k] for k in ('bytes','sha256')}==PANEL_PIN,
         'exact authentic VALID panel metadata')
    panel = decode(checked(panel_descriptor))
    need(panel['schema']=='smc_nlb_panel_v1' and panel['dataset']==DATASET and panel['phase']==PHASE
         and panel['source_commit']==AUTHOR_COMMIT and panel['validation_target_sha256']==TARGET_SHA256,
         'typed original VALID panel and target identity')
    need(encoded(panel['expected_shapes'])==encoded(SHAPES)
         and all(panel[k]==v for k,v in ORDER.items())
         and encoded(panel['split_counts'])==encoded({'train':1721,'val':574,'test':574}),
         'complete original VALID geometry and row identities')
    return panel


def validate_packet_metadata(packet_descriptor):
    """Join packet metadata only; the worker/projector separately verify its H5s."""
    packet = decode(checked(packet_descriptor))
    need(type(packet) is dict and set(packet)=={'schema','dataset','phase','units','geometry','roles','order','projector','files'},
         'closed restricted packet metadata')
    need(packet['schema']=='smc_restricted_validation_packet_v1' and packet['dataset']=='mc_maze'
         and packet['phase']==PHASE and packet['units']=='spike_counts_per_20ms_bin'
         and encoded(packet['geometry'])==encoded(GEOMETRY) and packet['roles']==PACKET_ROLES
         and packet['order']==ORDER and packet['projector']==PROJECTOR_PIN,
         'exact restricted VALID packet identity and source')
    need(type(packet['files']) is dict and set(packet['files'])==set(INPUT_SHAPES), 'exact two-file packet')
    total = 0
    for relative, shapes in INPUT_SHAPES.items():
        row = packet['files'][relative]
        need(type(row) is dict and set(row)=={'bytes','sha256','datasets'}, 'packet file metadata')
        validate_pin({k:row[k] for k in ('bytes','sha256')},160*1024*1024)
        total += row['bytes']
        need(type(row['datasets']) is dict and set(row['datasets'])==set(shapes), 'only allowed packet arrays')
        for name, shape in shapes.items():
            item = row['datasets'][name]
            need(type(item) is dict and set(item)=={'shape','dtype','content_sha256'}
                 and encoded(item['shape'])==encoded(shape) and item['content_sha256']==INPUT_CONTENT[name]
                 and type(item['dtype']) is str and 0<len(item['dtype'])<=32,
                 'exact projected array shape and content identity')
    need(total+packet_descriptor['bytes']<=160*1024*1024,'whole packet metadata byte budget')
    return packet


def validate_method(method_descriptor, packet_descriptor, role):
    need(role in ROLES, 'reference or candidate prediction role')
    method = decode(checked(method_descriptor))
    keys = {'schema','route','phase','role','program','bindings','recipe','packet_sha256','AI_attempt','scientific_improvement'}
    if role=='reference':
        keys.add('author_reference_resource_profile')
    need(type(method) is dict and set(method)==keys and method['schema']=='smc_restricted_validation_method_v1'
         and method['route']==ROUTE and method['phase']==PHASE and method['role']==role
         and method['packet_sha256']==packet_descriptor['sha256']
         and method['AI_attempt'] is False and method['scientific_improvement'] is False,
         'exact selected VALID method, role and packet join')
    validate_pin(method['program']); validate_pin(method['bindings'])
    if role=='reference':
        need(encoded(method['recipe'])==encoded(REFERENCE_RECIPE), 'original noncausal192x32 recipe')
        profile = method['author_reference_resource_profile']
        need(type(profile) is dict and set(profile)=={'cpu_seconds','wall_seconds','memory_bytes','threads'}
             and all(type(value) is int for value in profile.values())
             and 1<=profile['cpu_seconds']<=64800 and profile['wall_seconds']==10800
             and profile['memory_bytes']==8589934592 and profile['threads']==6,
             'explicit frozen author-reference resource profile; no default or adequacy claim')
    else:
        recipe = method['recipe']
        need(type(recipe) is dict and set(recipe)=={'method_id','seed'}
             and type(recipe['method_id']) is str and 0<len(recipe['method_id'])<=200
             and type(recipe['seed']) is int and recipe['seed']>=0,
             'distinct finite candidate method and seed')
    return method


def validate_prediction(prediction_path, role):
    """Retain the original rate-key, full-shape, finite/nonnegative contract."""
    import h5py
    import numpy as np
    need(role in ROLES, 'prediction role')
    p = ordinary(prediction_path); before = content_pin(p)
    fd = os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        with h5py.File(stream,'r') as handle:
            need(set(handle)=={DATASET} and isinstance(handle.get(DATASET,getlink=True),h5py.HardLink),
                 'exact direct dataset group')
            group = handle[DATASET]
            need(isinstance(group,h5py.Group),'prediction group')
            need(set(group)==set(RATE_KEYS) or (role=='candidate' and set(group)==REQUIRED_KEYS),
                 'complete original prediction rate-key contract')
            for name in group:
                need(isinstance(group.get(name,getlink=True),h5py.HardLink), 'direct prediction array')
                item = group[name]
                need(isinstance(item,h5py.Dataset) and not item.is_virtual and not item.external,
                     'no indirect prediction array')
                need(list(item.shape)==SHAPES[name] and item.dtype.kind in 'fiu', 'full VALID prediction array')
                for first in range(0,item.shape[0],32):
                    block = item[first:first+32]
                    need(bool(np.isfinite(block).all()) and bool((block>=0).all()), 'finite nonnegative predictions')
    need(content_pin(p)==before,'prediction unchanged during shape/value validation')
    return before


def freeze_prediction(prediction_path, panel_descriptor, packet_descriptor, method_descriptor, output_root, *, role):
    """Create immutable prediction bytes and metadata; accepts no target path."""
    validate_panel(panel_descriptor); validate_packet_metadata(packet_descriptor)
    validate_method(method_descriptor,packet_descriptor,role)
    original = ordinary(prediction_path); root_path = absolute(output_root)
    need(not original.is_relative_to(root_path) and not root_path.is_relative_to(original), 'disjoint freeze output')
    root = fresh_root(root_path)
    snapshot = copy_snapshot(original,root/'prediction.h5')
    need(validate_prediction(snapshot['path'],role)=={k:snapshot[k] for k in ('bytes','sha256')},
         'validated immutable prediction snapshot')
    record = {'schema':'smc_restricted_validation_prediction_freeze_v1','route':ROUTE,'phase':PHASE,'role':role,
              'source':source_identity(),'snapshot':{'filename':'prediction.h5',**{k:snapshot[k] for k in ('bytes','sha256')}},
              'panel':panel_descriptor,'packet':packet_descriptor,'method':method_descriptor,'shapes':SHAPES,
              'target_accessed_by_freeze':False,'inference_execution_qualified':False,
              'pipeline_execution_qualified':False,'physical_owner_qualified':False}
    return publish(root/'FREEZE.json',record)


def validate_freeze(freeze_descriptor):
    record = decode(checked(freeze_descriptor))
    need(type(record) is dict and set(record)==FREEZE_KEYS
         and record['schema']=='smc_restricted_validation_prediction_freeze_v1'
         and record['route']==ROUTE and record['phase']==PHASE and record['role'] in ROLES
         and record['source']==source_identity() and encoded(record['shapes'])==encoded(SHAPES)
         and all(record[k] is False for k in ('target_accessed_by_freeze','inference_execution_qualified',
                                            'pipeline_execution_qualified','physical_owner_qualified')),
         'exact frozen VALID source/shape/role record; no inferred execution qualification')
    validate_panel(record['panel']); validate_packet_metadata(record['packet'])
    validate_method(record['method'],record['packet'],record['role'])
    root = ordinary(freeze_descriptor['path']).parent
    need(Path(freeze_descriptor['path']).name=='FREEZE.json'
         and {p.name for p in root.iterdir()}=={'FREEZE.json','prediction.h5'}, 'exact freeze directory')
    snap = record['snapshot']
    need(type(snap) is dict and set(snap)=={'filename','bytes','sha256'} and snap['filename']=='prediction.h5',
         'fixed frozen snapshot name')
    expected = validate_pin({k:snap[k] for k in ('bytes','sha256')})
    snapshot = root/'prediction.h5'
    need(stat.S_IMODE(snapshot.lstat().st_mode)==0o400, 'immutable frozen prediction mode')
    need(validate_prediction(snapshot,record['role'])==expected, 'frozen prediction identity')
    return {'record':record,'snapshot':{'path':str(snapshot),**expected},'freeze':dict(freeze_descriptor)}


def load_original_evaluator(source_path):
    raw = body(source_path)
    need(pin(raw)==EVALUATOR_PIN,'unchanged canonical original nlb-tools0.0.3 evaluator')
    expected = {'numpy':'1.26.3','scipy':'1.12.0','scikit-learn':'1.5.0','h5py':'3.10.0'}
    actual = {name:importlib.metadata.version(name) for name in expected}
    need(actual==expected,'selected scientific dependency versions')
    module = types.ModuleType('_smc_restricted_validation_original_evaluator')
    module.__file__ = str(ordinary(source_path))
    exec(compile(raw,str(source_path),'exec'),module.__dict__)
    return module


def authenticate_target(target_path):
    """First target access. score_pair calls this only after both snapshots."""
    result = content_pin(target_path)
    need(result['sha256']==TARGET_SHA256, 'exact original VALID target content')
    return {'path':str(ordinary(target_path)),**result}


def extract_metrics(result):
    need(type(result) is list and len(result)==1 and type(result[0]) is dict
         and set(result[0])=={DATASET+'_split'}, 'one complete VALID dataset result')
    metrics = result[0][DATASET+'_split']
    need(type(metrics) is dict and set(metrics)==set(METRICS), 'all four original companion metrics')
    need(all(type(v) in (int,float) and math.isfinite(v) for v in metrics.values()), 'finite metric scalars')
    return {key:float(metrics[key]) for key in METRICS}


def score_pair(freezes, target_path, evaluator_path, output_root):
    """Subordinate numerical API for an actual bounded owner or generated controls.

    It does not supply the required 2GiB/600CPU/720s+60s grading owner. The public
    CLI remains disabled until that concrete owner is separately implemented.
    """
    need(type(freezes) is dict and set(freezes)==set(ROLES), 'exact frozen reference/candidate pair')
    admitted = {role:validate_freeze(freezes[role]) for role in ROLES}
    need(all(admitted[role]['record']['role']==role for role in ROLES), 'role-bound paired freezes')
    reference,candidate = (admitted[role]['record'] for role in ROLES)
    need(reference['panel']==candidate['panel'] and reference['packet']==candidate['packet'],
         'same exact VALID panel and projected observations')
    target,root_path = absolute(target_path),absolute(output_root)
    need(not target.is_relative_to(root_path) and not root_path.is_relative_to(target), 'target outside fresh scoring output')
    need(all(not target.is_relative_to(Path(a['snapshot']['path']).parent)
             and not root_path.is_relative_to(Path(a['snapshot']['path']).parent)
             for a in admitted.values()), 'operator target and output separate from freezes')
    need(sum(a['snapshot']['bytes'] for a in admitted.values())<=PAIR_SNAPSHOT_CAP,'paired snapshot byte budget')
    root = fresh_root(root_path)
    started = publish(root/'GRADE_STARTED.json',{'schema':'smc_restricted_validation_grade_started_v1',
        'source':source_identity(),'freezes':freezes,'phase':PHASE,'paired_order':list(ROLES)})
    snapshots = {}
    for role in ROLES:
        expected = {k:admitted[role]['snapshot'][k] for k in ('bytes','sha256')}
        snapshots[role] = copy_snapshot(admitted[role]['snapshot']['path'],root/(role+'.h5'),expected)
        need(validate_prediction(snapshots[role]['path'],role)==expected, 'paired operator snapshot validation')
    barrier = publish(root/'BOTH_SNAPSHOTS.json',{'schema':'smc_restricted_validation_both_snapshots_v1',
        'phase':PHASE,'source':source_identity(),'freezes':freezes,'snapshots':snapshots,
        'target_accessed_by_this_call':False,'inference_execution_qualified':False})
    # The helper has made no target stat, read or numerical call above this line.
    evaluator = load_original_evaluator(evaluator_path)
    target_ref = authenticate_target(target)
    metrics = {}
    for role in ROLES:
        metrics[role] = extract_metrics(evaluator.evaluate(str(target),snapshots[role]['path']))
        need(content_pin(target)=={k:target_ref[k] for k in ('bytes','sha256')}, 'target unchanged during paired scoring')
        need(content_pin(snapshots[role]['path'])=={k:snapshots[role][k] for k in ('bytes','sha256')},
             'operator snapshot unchanged during scoring')
    report = {'schema':'smc_restricted_validation_paired_metrics_v1','route':ROUTE,'phase':PHASE,
        'dataset':DATASET,'status':'both_frozen_predictions_scored','source':source_identity(),
        'started':started,'barrier':barrier,'freezes':freezes,'snapshots':snapshots,
        'panel':reference['panel'],'packet':reference['packet'],'target':target_ref,'evaluator':EVALUATOR_PIN,
        'metrics':metrics,'candidate_minus_reference':{k:metrics['candidate'][k]-metrics['reference'][k] for k in METRICS},
        'checkpoint_training_cohort':'unknown','validation_role':'development_split_not_checkpoint_independent_test',
        'train_rates_role':'canonical_metric_decoder_inputs_not_restricted_calibration',
        'inference_execution_qualified':False,'pipeline_execution_qualified':False,'physical_owner_qualified':False,
        'resource_adequacy':False,'scientific_equivalence':None,'scientific_improvement':False,'SOTA':False,
        'packet_payloads_reopened_by_grader':False,
        'execution_prerequisite':'Separately selected qualified owner must enforce process/resource/mount custody; this module provides no execution receipt.'}
    return publish(root/'REPORT.json',report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',required=True); parser.add_argument('--sha256',required=True)
    args = parser.parse_args(argv)
    raw = body(args.request); need(pin(raw)['sha256']==args.sha256,'selected exact operator request')
    request = decode(raw)
    need(type(request) is dict and set(request)=={'schema','source','freezes','target','evaluator','output_root'}
         and request['schema']=='smc_restricted_validation_grade_request_v1'
         and request['source']==source_identity(),'typed source-bound VALID scoring request')
    need(False, 'VALID grading CLI unavailable: genuine external 2GiB/600CPU/720wall+60cleanup owner is required')


if __name__=='__main__':
    main()
