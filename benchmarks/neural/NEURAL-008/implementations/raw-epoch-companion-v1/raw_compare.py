"""Public coordinator and protected worker for the new four-panel raw condition.

Separate command invocations make the gate explicit; operating-system separation
and target confinement must be supplied by the operator. Both gates independently
admit all complete public custody. No CLI accepts a candidate target loader.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import raw_contract as C
import raw_programme as P
import raw_admission as A

SCORER='benchmarks/neural/NEURAL-008/implementations/finite-paired-scorer'
SCORER_FILES=('score.py','target_identity.json','neural008_vendor/__init__.py',
              'neural008_vendor/candidate_adapter.py','neural008_vendor/paired_core.py')


def scorer(source,dependency_root=None):
    runtime=C.verify_source(source,dependency_root)
    C.need({SCORER+'/'+name for name in SCORER_FILES} <= runtime['bindings']['upstream'].keys(), 'Complete unchanged N008 scorer source')
    root=runtime['root']/SCORER
    name='neural008_vendor'
    if name in sys.modules:
        C.need(Path(sys.modules[name].__file__).resolve()==root/'neural008_vendor/__init__.py','Exact maintained scorer package')
    else:
        spec=importlib.util.spec_from_file_location(name,root/'neural008_vendor/__init__.py',
            submodule_search_locations=[str(root/'neural008_vendor')])
        package=importlib.util.module_from_spec(spec);sys.modules[name]=package;spec.loader.exec_module(package)
    return P.module('_raw008_original_score',root/'score.py',runtime['bindings']['upstream'][SCORER+'/score.py'])


def checked_panels(scoring,panels):
    C.need(type(panels) is dict and set(panels)==set(A.CONDITIONS.values()),'Four complete fixed raw panels before targets')
    validated={}
    for key in A.PANELS:
        item=panels[A.CONDITIONS[key]]
        validated[key]=scoring.adapter.validate_submission(item['path'],P.plain(item),scoring.SPEC)
    return validated


def _arithmetic_after_public(scoring,panels,target_loader):
    """Trusted arithmetic seam, also used by generated numeric controls; no custody claim.

    Production calls only after worker admission. A generated call to this helper
    exercises unchanged score arithmetic and cannot emit a public-custody freeze.
    """
    checked_panels(scoring,panels)
    targets=target_loader()  # Exactly one actual target operand load, after all four numerical panels.
    scoring.adapter._checked_targets(targets,scoring.SPEC)
    claims={'schema_version':1,'candidate_id':'NEURAL-008','reported_contrast':None}
    results={}
    for arm in A.ARMS:
        arm_files={old:(panels[A.CONDITIONS[(arm,new)]]['path'],P.plain(panels[A.CONDITIONS[(arm,new)]]))
                   for old,new in zip(scoring.paired_core.ARMS,C.MODALITIES)}
        results[arm]=scoring.paired_core.evaluate(arm_files,claims,scoring.SPEC,lambda:targets)
    differences={}
    for old,new in zip(scoring.paired_core.ARMS,C.MODALITIES):
        differences[new]=scoring.adapter._difference(results['programme']['absolute_performance'][old],
                                                    results['viewer']['absolute_performance'][old])
    return {'schema':'neural008_raw_arithmetic_v1','within_arm_eog_contrasts':results,
            'programme_minus_viewer':differences,'actual_target_loader_calls':1,
            'core_target_callback_calls':2,'core_callbacks_reuse_same_loaded_targets':True,
            'arithmetic_only_no_access_admission':True,'population_inference':False,
            'causal_tools_only_attribution':False,'scientific_qualification':False}


def public_coordinator(config):
    C.need(type(config) is dict and set(config)=={'public','target_root','output_root'}, 'Exact coordinator request')
    frozen=A.admit_four(config['public'])
    scoring=scorer(config['public']['source'],config['public']['dependency_root'])
    checked_panels(scoring,frozen['panels'])
    root=C.ordinary_path(config['output_root']);root.mkdir(mode=0o700)
    freeze=C.write_new(root/'FOUR_PANEL_FREEZE.json',C.encode(frozen))
    request=C.write_new(root/'WORKER_REQUEST.json',C.encode({'schema':'neural008_raw_worker_request_v1',
        'public':config['public'],'public_freeze':freeze,'target_root':str(C.ordinary_path(config['target_root'])),
        'output_path':str(root/'GRADE.json')}))
    return {'public_freeze':freeze,'worker_request':request,'worker_argv':[sys.executable,'-I','-B',str(HERE/'raw_compare.py'),
        '--operation','worker','--config',request['path'],'--bytes',str(request['bytes']),'--sha256',request['sha256']],
        'operating_system_separation_qualified':False,'targets_loaded':0}


def protected_worker(config):
    C.need(type(config) is dict and set(config)=={'schema','public','public_freeze','target_root','output_path'}
           and config['schema']=='neural008_raw_worker_request_v1','Exact independently pinned worker request')
    # Repeat admission first: a coordinator result or four finished arrays cannot substitute.
    frozen=A.admit_four(config['public'])
    C.need(C.capture(config['public_freeze'],65536)==C.encode(frozen),'Independent complete public-freeze equality')
    scoring=scorer(config['public']['source'],config['public']['dependency_root'])
    result=_arithmetic_after_public(scoring,frozen['panels'],lambda:scoring.historical_targets(config['target_root']))
    report={'schema':'neural008_raw_four_panel_result_v1','family':C.FAMILY,'public_freeze':P.plain(config['public_freeze']),
            'public_custody_complete':True,'conditions':A.CONDITIONS.values(),'arithmetic':result,
            'epochs_per_panel':C.TOTAL,'people':2,'exposure':'two historical public development people',
            'temporal_context_removed':True,'whole_history_comparison_valid':False,'source_of_task_signal':'same original epoch',
            'shared_declared_prior_only':True,'hidden_pretraining_verified':False,'trained_richer_arms_in_this_condition':False,
            'runtime_qualification':False,'provider_qualification':False,'scientific_qualification':False,
            'sota_claim':False,'population_inference':False,'epoch_count_is_not_independent_sample_size':True}
    report['conditions']=list(report['conditions'])
    return C.write_new(config['output_path'],C.encode(report))


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--operation',choices=('coordinate','worker'),required=True)
    parser.add_argument('--config',required=True);parser.add_argument('--bytes',type=int,required=True);parser.add_argument('--sha256',required=True)
    a=parser.parse_args(argv);config=C.decode(C.capture({'path':a.config,'bytes':a.bytes,'sha256':a.sha256},2**20))
    result=(public_coordinator if a.operation=='coordinate' else protected_worker)(config)
    print(C.encode({'status':'complete','result':result,'scientific_qualification':False}).decode(),end='');return result


if __name__=='__main__':main()
