"""Fixed restricted VALID reference adapter; the model/evaluator are unchanged."""
import argparse
from pathlib import Path
import runpy
import sys
import tempfile
from validation_reference import (ACCESS,ROUTE,HELPERS,body,decode,encode,need,path,pin,
    read,validate_job,write_new,inspect_inputs,validate_material_record)


def invoke_author(helper_root,selected,input_root,output,scratch,packet_sha256,resource_profile):
    old_argv,old_path=sys.argv,list(sys.path)
    try:
        sys.path.insert(0,str(helper_root))
        sys.argv=[str(helper_root/'author_predict_val.py'),'--source',str(input_root/'official_source'),
                  '--inputs',str(input_root/'inputs'),'--arm',selected['arm'],'--mode','predict',
                  '--packet-sha256',packet_sha256,'--report',str(scratch/'author_report.json'),
                  '--output',str(output/'offline.h5'),'--cpu-seconds',str(resource_profile['cpu_seconds'])]
        runpy.run_path(str(helper_root/'author_predict_val.py'),run_name='__main__')
    finally:
        sys.argv,sys.path[:]=old_argv,old_path
    return read(scratch/'author_report.json')


def validate_author_report(report,selected,packet_sha256,resource_profile):
    need(type(report) is dict and report.get('schema')=='smc_restricted_validation_native_attempt_v1'
         and report.get('mode')=='predict' and report.get('arm')==selected['arm']
         and report.get('seed')==selected['seed'] and report.get('particles')==192
         and report.get('source_requested_repeats')==32 and report.get('smooth') is False
         and report.get('phase')=='val' and report.get('packet_sha256')==packet_sha256
         and report.get('restricted_eval_shape')==[574,35,137]
         and report.get('train_rates_role')=='canonical_metric_decoder_inputs_not_restricted_calibration'
         and report.get('checkpoint_training_cohort')=='unknown' and report.get('resource_adequacy') is False
         and report.get('complete_source_prediction') is True
         and type(report.get('selected_cpu_seconds')) is int
         and report['selected_cpu_seconds']==resource_profile['cpu_seconds'],
         'Completed exact restricted VALID reference report; no historical cohort or budget adequacy claim')
    return report


def run(plan_path,execution_path,source_path,bindings_path,helper_root,input_root,output):
    plan_raw,job_raw,binding_raw=body(plan_path),body(execution_path),body(bindings_path)
    bindings,plan,job=decode(binding_raw),decode(plan_raw),decode(job_raw)
    program_pin,binding_pin=pin(body(source_path)),pin(binding_raw)
    selected=validate_job(plan,job,program_pin,binding_pin)
    need(job['declaration_sha256']==job['method_freeze_sha256']==pin(plan_raw)['sha256'],
         'Frozen actual method bytes before release and original inference')
    helper_root,input_root,output=map(path,(helper_root,input_root,output))
    need(type(bindings) is dict and set(bindings)=={'schema','helpers','packet','materials'}
         and bindings['schema']=='smc_restricted_validation_bindings_v1'
         and set(bindings['helpers'])==HELPERS and bindings['packet']['sha256']==job['packet_sha256'],
         'Exact selected helper and packet bindings')
    for name,expected in bindings['helpers'].items():body(helper_root/name,expected)
    packet_raw=body(input_root/'inputs/PACKET.json',bindings['packet'])
    inspect_inputs(input_root/'inputs',pin(packet_raw)['sha256'])
    need(output.is_dir() and not any(output.iterdir()),'Fresh private inference output')
    # Only individually admitted capsule leaves are mounted; neither original raw
    # input/target containers nor their parent directories are part of this ABI.
    with tempfile.TemporaryDirectory(prefix='smc-restricted-validation-') as temporary:
        report=invoke_author(helper_root,selected,input_root,output,path(Path(temporary).resolve()),job['packet_sha256'],job['resource_profile'])
        validate_author_report(report,selected,job['packet_sha256'],job['resource_profile'])
    need({p.name for p in output.iterdir()}=={'offline.h5'},'Only original author prediction output')
    prediction=output/'offline.h5';st=prediction.lstat()
    need(prediction.is_file() and not prediction.is_symlink() and st.st_nlink==1
         and 0<st.st_size<=job['max_file_bytes'],'Bounded original inference prediction')
    actual={'schema':'smc_restricted_validation_actual_v1','route':ROUTE,'role':'restricted_validation_reference',
            'phase_id':job['phase_id'],'phase':'val','access_condition':ACCESS,'recipe':selected,
            'program_sha256':program_pin['sha256'],'bindings':binding_pin,'packet_sha256':job['packet_sha256'],
            'method_freeze_sha256':job['method_freeze_sha256'],'author_reference_resource_profile':job['resource_profile'],'author_report':report,
            'train_rates_role':'canonical_metric_decoder_inputs_not_restricted_calibration',
            'checkpoint_training_cohort':'unknown','resource_adequacy':False,'training':False,'adaptation':False,
            'AI_attempt':False,'scientific_improvement':False,'runtime_qualified_by_this_adapter':False}
    write_new(output/'actual_declaration.json',encode(actual));return actual


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('input','out','outcome','declaration','selected-artifacts'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args(argv)
    need(vars(args)=={'input':'/materials','out':'/output','outcome':'restricted_validation_reference',
         'declaration':'/declaration.json','selected_artifacts':'/selected_artifacts'},'Fixed restricted VALID worker ABI')
    return run(Path(args.declaration),Path('/execution.json'),Path(__file__).resolve(),
               Path('/selected_artifacts/BINDINGS.json'),Path('/selected_artifacts/restricted_validation'),
               Path(args.input),Path(args.out))


if __name__=='__main__':
    main()
