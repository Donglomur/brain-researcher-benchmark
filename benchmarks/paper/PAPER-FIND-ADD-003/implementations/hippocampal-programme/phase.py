"""Concrete private container entrypoints; invoked only by a future authorized operation."""
import json
from pathlib import Path
import subprocess
import time
BOOT=time.monotonic() # container-local elapsed origin; never compared to host epoch
from core import encoded,need
from safe_io import array,capture,child,new_json,pin,strict,write_array


def native(request,operation):
    from native.bridge import command,verify_inputs,validate_preparation,finalize_reference
    verify_inputs(request)
    result=subprocess.run(command(operation),stdin=subprocess.DEVNULL,check=False,close_fds=True)
    if operation=='prepare':
        need(result.returncode==0,'Native structural export exit; no fabricated preparation')
        value=validate_preparation('/output','/identity/EVIDENCE.json',request['identity_sha256'])
    else:value=finalize_reference('/output') # preserves failed/unstarted calls after nonzero
    new_json(Path('/output/RESULT.json'),value)


def train(request):
    import numpy as np
    from native.bridge import command
    from graph.compile_reference import build_reference,training_roundtrip
    result=subprocess.run(command('fit'),stdin=subprocess.DEVNULL,check=False,close_fds=True)
    root=Path('/output');parameters_path=root/'MODEL_PARAMETERS.json'
    if not parameters_path.exists():
        new_json(root/'RESULT.json',{'schema':'h_reference_training_result_v1','status':'incomplete','native_exit':result.returncode,'reason':'No typed native parameter export'});return
    exported=strict(capture(parameters_path,request['model_limits']['max_model_bytes']))
    if result.returncode or exported.get('status')!='complete':
        new_json(root/'RESULT.json',{'schema':'h_reference_training_result_v1','status':'incomplete','native_exit':result.returncode,'parameter_export':pin(capture(parameters_path,request['model_limits']['max_model_bytes']))});return
    constants={}
    for name,d in exported['arrays'].items():
        x=array(root,{k:d[k] for k in ('path','bytes','sha256','shape','dtype')},request['model_limits']['max_array_bytes'])
        if name=='all_missing':need(np.all((x==0)|(x==1)),'Binary all-missing mask');x=x.astype(bool)
        constants[name]=x
    graph,compiled,inputs=build_reference({k:exported['parameters'][k] for k in ('schema','family','channels','clock')},constants)
    training=strict(capture('/input/TRAINING.json',request['model_limits']['max_training_metadata_bytes']))
    a=training['arrays'];values=array('/input',a['values'],request['model_limits']['max_training_array_bytes']);mask=array('/input',a['missing'],request['model_limits']['max_training_array_bytes'])
    need(np.all((mask==0)|(mask==1)),'Binary complete training mask')
    clocks=array('/input',a['clock'],request['model_limits']['max_training_array_bytes']) if training['clock'] else None
    support=[{'values':np.asarray(values[i],dtype='float64'),'missing':np.asarray(mask[i],dtype=bool),**({'clock':np.asarray(clocks[i],dtype='float64')} if clocks is not None else {})} for i in range(values.shape[0])]
    margins=array(root,{k:exported['native_training_margins'][k] for k in ('path','bytes','sha256','shape','dtype')},request['model_limits']['max_array_bytes']).reshape(-1)
    limits={**request['model_limits']['graph_limits'],'deadline':request['local_deadline']}
    proof=training_roundtrip(graph,compiled,support,margins,limits,atol=request['model_limits']['roundtrip_atol'],rtol=request['model_limits']['roundtrip_rtol'])
    descriptors={}
    for name,x in compiled.items():
        y=np.ascontiguousarray(x.astype('|u1') if x.dtype==np.dtype('bool') else x,dtype='|u1' if x.dtype==np.dtype('bool') else '<f8')
        # Preserve scalar rank after ascontiguousarray (which otherwise adds axis).
        y=y.reshape(x.shape)
        descriptors[name]=write_array(root/('graph_'+name+'.npy'),y,request['model_limits']['max_array_bytes'])
    model={'schema':'h_model_v1','family':request['family'],'graph':graph,'arrays':descriptors,'input_shapes':inputs,'training_provenance':{'schema':'h_independent_training_proof_v1','native_exit':result.returncode,'complete_training_roundtrip':proof,'parameters':pin(capture(parameters_path,request['model_limits']['max_model_bytes'])),'query_use':False}}
    need(len(encoded(model))<=len(encoded(graph))+65536,'Reference model framing/provenance bound admitted before all models')
    new_json(root/'MODEL.json',model);new_json(root/'RESULT.json',{'schema':'h_reference_training_result_v1','status':'complete','roundtrip':proof,'scientific_qualification':False})


def main():
    request=strict(capture('/job/REQUEST.json',8388608));action=request['action']
    need(type(request['container_elapsed_seconds']) is int and request['container_elapsed_seconds']>0,'Explicit bounded container-local elapsed allowance')
    request['local_deadline']=BOOT+request['container_elapsed_seconds']
    need(time.monotonic()<request['local_deadline'],'Container-local elapsed cutoff before private work; original host cutoff remains authoritative externally')
    if action=='prepare_originals':native(request,'prepare')
    elif action=='native_attempt':native(request,'reference')
    elif action=='prepare_fold':
        from views import construct
        manifest=strict(capture('/input/admitted-preparation.json',request['preparation_limits']['max_metadata_bytes']))
        seed=capture('/randomization/SEED',32,request['randomization_seed_pin'])
        construct('/input',manifest,request['case'],request['preparation_limits'],'/output/fold',seed)
        # Keep fold manifest/arrays together and expose an explicit subtree pointer.
        new_json('/output/RESULT.json',{'schema':'h_fold_phase_v1','directory':'fold','manifest':pin(capture('/output/fold/RESULT.json',request['preparation_limits']['max_metadata_bytes']))})
    elif action=='train_model':train(request)
    elif action=='evaluate_model':
        from models import evaluate_model
        evaluate_model('/model',request['model_files'],'/query',request['family'],request['producer_role'],request['case'],request['channels'],request['model_limits'],request['local_deadline'],'/output')
    elif action=='grade':
        from grade import run
        index=strict(capture('/input/INDEX.json',request['preparation_limits']['max_grade_index_bytes']))
        run(index,'/input',request['preparation_limits']['grade_limits'],'/output')
    elif action=='report':
        summary=strict(capture('/input/RESULT.json',request['preparation_limits']['max_metadata_bytes']))
        new_json('/output/RESULT.json',{'schema':'h_final_program_report_v1','private_grade':summary,'actual_whole_program_custody':'external_supervisor_required','scientific_qualification':False,'authentic_run_status':'This file only exists after a separately authorized invocation; source construction does not run it.'})
    else:raise ValueError('No undeclared private action')
    need(time.monotonic()<request['local_deadline'],'Container-local elapsed cutoff after private work; no host deadline refresh')


if __name__=='__main__':main()
