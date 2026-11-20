"""Trusted-operator TEST identity and completed VALID gain selection joins.

No prediction, checkpoint, evaluator or target body is opened by this module.
No old protocol is execution authority. Frozen method/source/runtime descriptors
are trusted operator inputs, never participant-generated qualification flags.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types

META_CAP = 128 * 1024
FILE_CAP = 512 * 1024 * 1024
SOURCE_FILES = {'test_core.py','transform/test_transform.py','TEST_PROFILE.json'}
GAIN_FILES = {'gain_core.py','gain_selector.py','gain_transform.py','METHOD.json'}
GAIN_RUNTIME_FILES = {'gain_selector_host.py','gain_selector_child.py','owned_exit.py','bounded_capture.py','label_policy.py'}
GRADE_FILES = {'test_pair_grade.py','test_pair_child.py','scorer.py','reference_panel.json','gain_transform.py'}
RUNTIME_FILES = {'test_pair_grade_host.py','owned_exit.py','bounded_capture.py','label_policy.py'}
INPUT_KEYS = {'gain_kernel','gain_runtime','valid_selector_result','valid_selection','valid_method',
              'valid_reference_bindings','valid_materials','valid_author_manifest','valid_component_source',
              'test_panel','test_protocol','test_reference_freeze','test_reference_prediction',
              'test_source_manifest','test_source_postcheck','test_target','evaluator'}
METHOD_KEYS = {'schema','source','grader_source','runtime_source','inputs','selected_row','lineage','candidate_recipe'}
CANDIDATE_RECIPE = {'role':'candidate','arm':'noncausal','seed':0,'particles':None,'repeats':None,'source_author_commit':None}
PINS = {
 'gain_kernel':{'bytes':604,'sha256':'34bcd3a7dc56440e58694f3275bbb59d6f46a7ddc0e3a248c10cd98399c1b44c'},
 'gain_runtime':{'bytes':884,'sha256':'0104cd632c855e624d076965669f1103128a569b116562181d516761839c8076'},
 'valid_author_manifest':{'bytes':3704,'sha256':'907d9209d9bcb281a7aabc95ad4234cae12e5dfbc94a106fa53953cfeea48404'},
 'valid_component_source':{'bytes':1416,'sha256':'2f953188e39b51a7b76a79f8dc37adb6631b1803f762437a9d6c7a4974b44e83'},
 'test_panel':{'bytes':4333,'sha256':'3b160dfb4aef8c68cbae8d4a02d5933576a77e4bc47a7c3a5b484369caf95be5'},
 'test_protocol':{'bytes':11499,'sha256':'71242e29e6fba3146a9ae0bfceef4de079390bad4ce02a450ec287c3ec759535'},
 'test_reference_freeze':{'bytes':814,'sha256':'1d927a636ccc7e966c0390521b5f8daac13a8b6d345e8dbcf9d3a848322cf6f7'},
 'test_reference_prediction':{'bytes':87250290,'sha256':'fcca208d1d09641a941dfdaf4290493e01ae98be560d665c22f066718c630896'},
 'test_source_manifest':{'bytes':8534,'sha256':'07f763fea98dd95f8874939c1898c686b687008746265fe5eae4192c10699f34'},
 'test_source_postcheck':{'bytes':4789,'sha256':'257e7b02e9b3d387b4d6da2f4bbb4e9f28799b4319344bcf4317812c36786b05'},
 'test_target':{'bytes':105927616,'sha256':'f2f434d30193251b58e6a693381fdd185c8fbc0e47d38f8810e65295bc42c865'},
 'evaluator':{'bytes':18292,'sha256':'05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476'}}
SCORER_PIN = {'bytes':15050,'sha256':'48638a595755138b32ff9c228804fd8c19c9ff874cd254f135fc5245ee9a25f8'}
REFERENCE_PANEL_PIN = {'bytes':3665,'sha256':'209a15e2189499a9e68264df5c9f81057dd919564d98a46fb64d75b3f39af2f3'}
TRANSFORM_PIN = {'bytes':19658,'sha256':'b78a4eaae4b5ea1af893ed133e9973c71f131bccadb62cb7b93aa7e13cfc5dda'}
HELPER_PINS = {'owned_exit.py':{'bytes':8088,'sha256':'d1d4aa36bf3893ee07e16f7086fd123c08d81ec47278efd6be3091c862c59426'},
              'bounded_capture.py':{'bytes':7749,'sha256':'0a9274a1b08b00ee778143aa5ba35e4a3bf6b27dd6e8ea8838428b0652c0949f'},
              'label_policy.py':{'bytes':2169,'sha256':'9c87d897215caead93206ecaa09ec2a33717609fd84a6e374d8e63f4daa330ef'}}
PROFILE_PIN = {'bytes': 3348, 'sha256': 'ea9dca30997ff6f5a4993ac2fe554e864b7ff2c08e3a2cfb2c902fe1a76a0ce8'}

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

def same(left, right):
    return encoded(left) == encoded(right)

def execute_source(name, filename, raw):
    module = types.ModuleType(name)
    module.__file__ = str(filename)
    exec(compile(raw,str(filename),'exec',dont_inherit=True),module.__dict__)
    return module


def named_pin(row):
    descriptor(row)
    return {key:row[key] for key in ('bytes','sha256')}


def fixed(row, key, *, read_metadata=True):
    need(same(named_pin(row),PINS[key]), 'exact recorded '+key+' descriptor')
    return decode(checked(row)) if read_metadata else None


def source_identity():
    path = Path(__file__).absolute().with_name('SOURCE.json')
    return {'path':str(path),**pin(body(path))}


def authenticate_source(selected):
    value=decode(checked(selected))
    need(type(value) is dict and set(value)=={'schema','files'} and value['schema']=='smc_test_gain_source_v1'
         and type(value['files']) is dict and set(value['files'])==SOURCE_FILES,'exact three-leaf TEST source')
    root=ordinary(selected['path']).parent
    for name,expected in value['files'].items():
        validate_pin(expected,META_CAP);need(same(pin(body(root/name)),expected),'authenticated TEST source leaf')
    need(same(value['files']['TEST_PROFILE.json'],PROFILE_PIN),'fixed original TEST/checkpoint/order profile')
    return decode(body(root/'TEST_PROFILE.json'))


def authenticate_successors(source, grader, runtime):
    grade=decode(checked(grader));run=decode(checked(runtime))
    need(type(grade) is dict and set(grade)=={'schema','files','test_kernel'}
         and grade['schema']=='smc_test_gain_grade_source_v1' and set(grade['files'])==GRADE_FILES
         and same(grade['test_kernel'],named_pin(source)), 'selected TEST grader and kernel back-reference')
    need(same(grade['files']['scorer.py'],SCORER_PIN) and same(grade['files']['reference_panel.json'],REFERENCE_PANEL_PIN)
         and same(grade['files']['gain_transform.py'],TRANSFORM_PIN),'unchanged numerical and transform sources')
    need(type(run) is dict and set(run)=={'schema','files'} and run['schema']=='smc_test_gain_grade_runtime_source_v1'
         and set(run['files'])==RUNTIME_FILES and all(same(run['files'][k],v) for k,v in HELPER_PINS.items()),
         'selected TEST runtime and unchanged ownership helpers')
    for selected,manifest in ((grader,grade),(runtime,run)):
        for name,expected in manifest['files'].items():
            validate_pin(expected,META_CAP)
            need(same(pin(body(ordinary(selected['path']).parent/name)),expected),'authenticated selected operator source')


def load_gain_gate(inputs):
    kernel=fixed(inputs['gain_kernel'],'gain_kernel');runtime=fixed(inputs['gain_runtime'],'gain_runtime')
    need(set(kernel)=={'schema','files'} and kernel['schema']=='smc_gain_kernel_source_v1' and set(kernel['files'])==GAIN_FILES,
         'unchanged gain kernel closure')
    need(set(runtime)=={'schema','files','kernel'} and runtime['schema']=='smc_gain_selector_runtime_source_v1'
         and set(runtime['files'])==GAIN_RUNTIME_FILES and same(runtime['kernel'],PINS['gain_kernel']),
         'unchanged genuine completed-selector gate closure')
    sources={}
    for selected,manifest in ((inputs['gain_kernel'],kernel),(inputs['gain_runtime'],runtime)):
        for name,expected in manifest['files'].items():
            raw=body(ordinary(selected['path']).parent/name)
            need(same(pin(raw),expected),'authenticated retained gain source leaf')
            if name=='gain_selector_host.py': sources[name]=raw
    filename=ordinary(inputs['gain_runtime']['path']).parent/'gain_selector_host.py'
    return execute_source('smc_test_original_gain_host',filename,sources['gain_selector_host.py'])


def admit_valid_checkpoint(inputs,selection,profile):
    """Check recorded method/material/checkpoint identities; never read weights."""
    component=fixed(inputs['valid_component_source'],'valid_component_source')
    author=fixed(inputs['valid_author_manifest'],'valid_author_manifest')
    binding=decode(checked(inputs['valid_reference_bindings']));materials=decode(checked(inputs['valid_materials']))
    reference=decode(checked(selection['lineage']['reference_method']))
    packet=decode(checked(selection['lineage']['packet']))
    need(same(reference['program'],component['files']['validation_adapter.py'])
         and same(reference['bindings'],named_pin(inputs['valid_reference_bindings'])),
         'genuine VALID reference method binds selected adapter and bindings')
    helpers={name.removeprefix('helpers/'):row for name,row in component['files'].items() if name.startswith('helpers/')}
    need(type(binding) is dict and set(binding)=={'schema','helpers','packet','materials'}
         and binding['schema']=='smc_restricted_validation_bindings_v1' and same(binding['helpers'],helpers)
         and same(binding['packet'],named_pin(selection['lineage']['packet']))
         and same(binding['materials'],named_pin(inputs['valid_materials'])),'recorded VALID binding/material/packet join')
    need(type(materials) is dict and set(materials)=={'schema','route','packet','author_manifest','files','train_rate_scope',
          'checkpoint_training_cohort','resource_adequacy'}
         and materials['schema']=='smc_restricted_validation_materials_v1'
         and materials['route']=='smc_restricted_validation_v1'
         and same(materials['author_manifest'],PINS['valid_author_manifest']) and same(materials['packet'],binding['packet'])
         and materials['train_rate_scope']=='canonical_metric_decoder_inputs_not_restricted_calibration'
         and materials['checkpoint_training_cohort']=='unknown' and materials['resource_adequacy'] is False,
         'original restricted VALID material identity and limits')
    official={r['path']:{k:r[k] for k in ('bytes','sha256')} for r in author['files']}
    expected={'inputs/PACKET.json':binding['packet'],**{'official_source/'+k:v for k,v in official.items()}}
    for relative,row in packet['files'].items():expected['inputs/'+relative]={k:row[k] for k in ('bytes','sha256')}
    need(same(materials['files'],expected),'exact original VALID materials, no substituted checkpoint')
    need(author['source_commit']==profile['source_commit'] and author['arm']=='noncausal'
         and author['checkpoint_training_cohort']=='unknown','original recorded checkpoint provenance only')
    recorded={r['path']:{k:r[k] for k in ('bytes','sha256')} for r in author['files'] if r['role']=='checkpoint'}
    need(same(recorded,profile['checkpoint_files']), 'VALID checkpoint identities match authentic TEST recorded artifacts')
    for name,row in profile['adjacent_config'].items():need(same(official[name],row),'same recorded adjacent released config')
    return {'reference_method':selection['lineage']['reference_method'],'bindings':inputs['valid_reference_bindings'],
            'materials':inputs['valid_materials'],'author_manifest':inputs['valid_author_manifest'],
            'component_source':inputs['valid_component_source'],'checkpoint_files':recorded}


def admit_test_metadata(inputs,profile):
    panel=fixed(inputs['test_panel'],'test_panel');protocol=fixed(inputs['test_protocol'],'test_protocol')
    freeze=fixed(inputs['test_reference_freeze'],'test_reference_freeze')
    manifest=fixed(inputs['test_source_manifest'],'test_source_manifest');post=fixed(inputs['test_source_postcheck'],'test_source_postcheck')
    # Payload and evaluator descriptors are lexical/identity checks only here.
    for key in ('test_reference_prediction','test_target','evaluator'):fixed(inputs[key],key,read_metadata=False)
    need(panel['schema']=='smc_nlb_panel_v1' and panel['phase']=='test' and panel['dataset']=='mc_maze_20'
         and panel['source_commit']==profile['source_commit'] and same(panel['expected_shapes'],profile['shapes'])
         and same({k:panel[k] for k in profile['geometry']},profile['geometry'])
         and same({k:panel[k] for k in profile['order']},profile['order']), 'original TEST geometry and recorded tensor order')
    need(freeze['schema']=='smc_nlb_prediction_freeze_v1' and freeze['role']=='author_calibration'
         and freeze['arm']=='noncausal' and freeze['seed']==20261118 and freeze['particles']==192 and freeze['repeats']==32
         and freeze['source_author_commit']==profile['source_commit']
         and freeze['submission_sha256']==PINS['test_reference_prediction']['sha256']
         and freeze['panel_manifest_sha256']==PINS['test_panel']['sha256']
         and freeze['protocol_sha256']==PINS['test_protocol']['sha256']
         and freeze['reference_panel_sha256']==REFERENCE_PANEL_PIN['sha256']
         and freeze['target_exposure']==profile['target_exposure'],'genuine historical TEST reference freeze, never VALID relabeling')
    need(manifest['schema']=='smc_source_manifest_v1' and manifest['source_commit']==profile['source_commit']
         and len(manifest['files'])==38,'original complete recorded author source manifest')
    files={r['path']:{k:r[k] for k in ('bytes','sha256')} for r in manifest['files']}
    for name,row in {**profile['checkpoint_files'],**profile['adjacent_config']}.items():
        need(same(files[name],row),'original recorded TEST checkpoint/config identity')
    need(post['schema']=='smc_completed_arm_source_check_v1' and post['arm']=='noncausal'
         and post['author_source_commit']==profile['source_commit'] and type(post['author_files_verified']) is int
         and post['author_files_verified']==38 and post['author_source_manifest_sha256']==PINS['test_source_manifest']['sha256']
         and post['input_panel_sha256']==PINS['test_panel']['sha256']
         and post['submission_sha256']==PINS['test_reference_prediction']['sha256']
         and post['submission_bytes']==PINS['test_reference_prediction']['bytes']
         and post['protocol_sha256']==PINS['test_protocol']['sha256']
         and post['native_report_sha256']=='e010326e053e4be542540107f4ea70b8dc4051f3b17df749924e52f91a4da18c',
         'recorded source postcheck joins actual historical artifact; no new execution claim')
    return {'panel':inputs['test_panel'],'protocol':inputs['test_protocol'],'reference_freeze':inputs['test_reference_freeze'],
            'source_manifest':inputs['test_source_manifest'],'source_postcheck':inputs['test_source_postcheck'],
            'baseline':inputs['test_reference_prediction'],'geometry':profile['geometry'],'shapes':profile['shapes'],
            'order':profile['order'],'decoder_cohort':profile['decoder_cohort'],'decoder_timebins':35}


def admit_inputs(inputs,profile):
    need(type(inputs) is dict and set(inputs)==INPUT_KEYS,'exact source-bound TEST and completed VALID input set')
    for row in inputs.values():descriptor(row)
    gate=load_gain_gate(inputs)
    valid_method=decode(checked(inputs['valid_method']))
    selection=gate.admit_completed_selection(inputs['valid_selector_result'],inputs['valid_selection'],
        method_descriptor=inputs['valid_method'],baseline_freeze_descriptor=valid_method['baseline_freeze'])
    need(selection['phase']=='val' and selection['source']==inputs['gain_kernel']
         and selection['method']==inputs['valid_method'],'genuine completed frozen VALID gain selection')
    checkpoint=admit_valid_checkpoint(inputs,selection,profile)
    test=admit_test_metadata(inputs,profile)
    lineage={'phase':'test','dataset':'mc_maze_20','test':test,'valid_selection':inputs['valid_selection'],
             'valid_selector_result':inputs['valid_selector_result'],'valid_method':inputs['valid_method'],
             'valid_checkpoint':checkpoint,'checkpoint_identity_scope':'recorded matching artifact descriptors, not new weight-body authentication',
             'checkpoint_training_run':'unresolved','paper_table2_link':'unresolved','paper_dandi_link':'unresolved',
             'released_config_and_model_selection':'Released configuration declares val; the pinned trainer selects checkpoints by VALID co-bps. Actual run/selection history is unresolved; no untouched cohort claim.',
             'target_exposure':profile['target_exposure'],'historical_failed_noncausal_supervision_repaired':False}
    role_inputs={'predictions':{'reference':inputs['test_reference_prediction']},
                 'freezes':{'reference':inputs['test_reference_freeze']},'panel':inputs['test_panel'],
                 'protocol':inputs['test_protocol'],'target':inputs['test_target'],'evaluator':inputs['evaluator']}
    return selection,lineage,role_inputs


def freeze_method(request_descriptor, output_path):
    request=decode(checked(request_descriptor))
    need(type(request) is dict and set(request)=={'schema','source','grader_source','runtime_source','inputs'}
         and request['schema']=='smc_test_gain_method_request_v1','exact trusted-operator TEST method preparation')
    need(same(request['source'],source_identity()),'current selected TEST kernel')
    profile=authenticate_source(request['source'])
    authenticate_successors(request['source'],request['grader_source'],request['runtime_source'])
    selection,lineage,_=admit_inputs(request['inputs'],profile)
    method={'schema':'smc_test_gain_method_v1','source':request['source'],'grader_source':request['grader_source'],
            'runtime_source':request['runtime_source'],'inputs':request['inputs'],
            'selected_row':selection['ordered_scores'][selection['selected_index']],
            'lineage':lineage,'candidate_recipe':CANDIDATE_RECIPE}
    return publish(output_path,method)


def admit_test_method(method_descriptor):
    record=decode(checked(method_descriptor))
    need(type(record) is dict and set(record)==METHOD_KEYS and record['schema']=='smc_test_gain_method_v1'
         and same(record['candidate_recipe'],CANDIDATE_RECIPE),'exact distinct TEST candidate method')
    need(same(record['source'],source_identity()),'executed TEST kernel matches frozen method')
    profile=authenticate_source(record['source'])
    authenticate_successors(record['source'],record['grader_source'],record['runtime_source'])
    selection,lineage,inputs=admit_inputs(record['inputs'],profile)
    need(same(record['selected_row'],selection['ordered_scores'][selection['selected_index']])
         and same(record['lineage'],lineage),'frozen actual VALID winner and authentic TEST/checkpoint/order lineage')
    return {'record':record,'selection':selection,'lineage':lineage,'inputs':inputs}


def admit_test_transform(method_descriptor):
    admitted=admit_test_method(method_descriptor)
    record=admitted['record']
    return {'gain':record['selected_row']['gain'],'baseline_descriptor':record['inputs']['test_reference_prediction'],
            'gain_source':record['inputs']['gain_kernel'],'source':record['source'],
            'method':dict(method_descriptor),'lineage':admitted['lineage']}


def admit_candidate_metadata(prediction_descriptor,freeze_descriptor,method_descriptor,admitted):
    descriptor(prediction_descriptor);freeze=decode(checked(freeze_descriptor))
    keys={'schema','arm','created_utc','dataset','method_id','panel_manifest_sha256','particles','protocol_sha256',
          'reference_panel_sha256','repeats','role','seed','source_author_commit','submission_sha256','target_exposure'}
    need(type(freeze) is dict and set(freeze)==keys and freeze['schema']=='smc_nlb_prediction_freeze_v1'
         and freeze['dataset']=='mc_maze_20' and freeze['role']=='candidate' and freeze['arm']=='noncausal'
         and type(freeze['seed']) is int and freeze['seed']==0
         and freeze['particles'] is None and freeze['repeats'] is None and freeze['source_author_commit'] is None
         and freeze['method_id']=='smc-test-gain/'+method_descriptor['sha256']
         and freeze['panel_manifest_sha256']==PINS['test_panel']['sha256']
         and freeze['protocol_sha256']==PINS['test_protocol']['sha256']
         and freeze['reference_panel_sha256']==REFERENCE_PANEL_PIN['sha256']
         and freeze['submission_sha256']==prediction_descriptor['sha256']
         and freeze['target_exposure']==admitted['lineage']['target_exposure'],
         'genuine distinct candidate freeze bound to this TEST method and prediction')
    need(type(freeze['created_utc']) is str and 0<len(freeze['created_utc'])<=100,'finite original candidate freeze timestamp')
    return {'prediction':dict(prediction_descriptor),'freeze':dict(freeze_descriptor)}


def main():
    parser=argparse.ArgumentParser(description='Freeze trusted TEST method metadata; no target or prediction access')
    parser.add_argument('--request',required=True);parser.add_argument('--sha256',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();raw=body(args.request);need(pin(raw)['sha256']==args.sha256,'selected preparation request hash')
    result=freeze_method({'path':str(ordinary(args.request)),**pin(raw)},args.output)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
