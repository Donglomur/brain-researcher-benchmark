"""Concrete private phase entry points for future separately authorized runs.

This file is operator/reference image source. It must never be mounted in A.
No source function below runs at import; Docker transport owns real execution,
natural exit, capture and retirement outside this worker's self-reports.
"""
import argparse
import hashlib
from pathlib import Path
from core import TASK, HMM, identity, need, encoded
from safe_io import capture, child, strict, new_json, array, write_array, pin


def rows(view, root, cap):
    return [{'person':r['person'],'run':r['run'],'observations':array(root,r['observations'],cap)}
            for r in view['runs']]


def native_data(branch):
    """Literal historical numerical preparation, separate from held profiles."""
    from glob import glob
    from osl_dynamics.data import Data
    if branch.startswith('elekta'):
        data=Data(inputs=sorted(glob('data/src/*/sflip_parc-raw.fif')),picks='misc',
                  reject_by_annotation='omit',sampling_frequency=250,store_dir='/work/selection_data',n_jobs=8)
    else:
        data=Data(inputs='training_data/'+('bursts' if branch=='ctf_bursts' else'networks'),
                  sampling_frequency=100 if branch=='ctf_bursts' else 250,
                  store_dir='/work/selection_data',n_jobs=8)
    if branch=='elekta_ae':
        methods={'amplitude_envelope':{},'moving_average':{'n_window':5},'standardize':{}}
    elif branch=='ctf_bursts':
        methods={'tde':{'n_embeddings':21},'standardize':{}}
    else:
        methods={'tde_pca':{'n_embeddings':15,'n_pca_components':80},'standardize':{}}
    data.prepare(methods)
    return data


def original_hmm_constructor(branch):
    d,k,_=HMM[branch]
    return {'n_states':k,'n_channels':d,'sequence_length':2000,
            'learn_means':branch=='elekta_ae','learn_covariances':True,
            'batch_size':32,'learning_rate':.01,'n_epochs':20}


def prepare_originals(payload, output):
    from source_inputs import build
    return build(payload['source_spec'],output/'originals',payload['io_limits'])


def prepare_fold(payload, output):
    import prepare
    import reference
    from core import encoded
    packet=strict(capture(payload['packet_path'],payload['packet_pin']['bytes'],payload['packet_pin']))
    result=prepare.build(packet,payload['original_root'],payload['packet_identity'],
                         payload['branch'],payload['fold'],output/'fold',payload['budget'])
    view=prepare.training_view(result,'real','reference')
    baseline=reference.static(rows(view,output/'fold',payload['budget']['array_bytes']),payload['branch'],payload['fold'])
    static_pin=new_json(output/'STATIC.json',baseline)
    return {'preparation':result,'static':{'path':'STATIC.json',**static_pin},
            'representation_id':result['representation_id'],'query_was_candidate_input':False}


def held_reference(payload, output):
    import reference
    view=strict(capture(payload['view_path'],payload['view_pin']['bytes'],payload['view_pin']))
    training=rows(view,payload['input_root'],payload['array_cap'])
    binding=identity(view)
    result=reference.fit(training,payload['job'],binding,binding,payload['environment'])
    model={'schema':'osl_held_model_v1','task_id':TASK,'job_id':payload['job']['id'],
           'representation_id':view['representation_id'],'parameters':result['parameters']}
    model_pin=new_json(output/'MODEL.json',model)
    # Full native initialization/history is retained as primitive report state.
    from reporting import write
    diagnostics=write(result,output/'training_diagnostics',payload['diagnostic_cap'])
    return {'model':model_pin,'training_diagnostics':diagnostics,
            'selection_requires_independent_operator_evaluation':True}


def native_reference(payload, output):
    from native_run import run
    return run(payload['job'],payload['context'],payload['script'],payload['script_pin'],
               payload['wrapper_pin'],'/work',output,payload['exposure'],payload['capture_cap'])


def select_model(payload, output):
    import admission
    import selection
    job=payload['disposition']['job']
    if job['phase']=='held_hmm':
        admitted=admission.held(payload['model_root'],payload['disposition'],
                                payload['representation_id'],payload['output_cap'])
        view=strict(capture(payload['view_path'],payload['view_pin']['bytes'],payload['view_pin']))
        training=rows(view,payload['input_root'],payload['array_cap'])
        try:
            result=selection.held_hmm(training,admitted['parameters'],job,identity(view),identity(view),payload['environment'])
        except ValueError as error:
            result={'available':False,'reason':str(error),'criterion':'historical_model_free_energy_on_training_sequences'}
    else:
        admitted=admission.native(payload['model_root'],payload['disposition'],payload['context'],payload['output_cap'])
        if job['branch']=='ctf_dynemo':
            # This flag is authenticated by the outer source/command equality
            # check. It is never read from the candidate artifact.
            if payload['trusted_original_pipeline'] and job['role']!='A':
                table={r['key']:r for r in admitted['assembled']['ordered_fields']}
                value=float(admitted['load'](table['model.free_energy']))
                from core import finite
                need(finite(value),'Finite original literal final training loss')
                result={'available':True,'value':value,'criterion':'literal_final_epoch_history_loss',
                        'evidence_mode':'trusted_exact_source_training_observation','query_used':False,'candidate_supplied':False}
            else:
                result={'available':False,'criterion':'literal_final_epoch_history_loss',
                        'reason':'independent_original_training_trajectory_not_established'}
        else:
            constructor=original_hmm_constructor(job['branch'])
            try:
                result=selection.native_hmm_parameters(admitted['assembled'],admitted['load'],native_data(job['branch']),
                    constructor,identity(constructor),payload['environment'])
            except ValueError as error:
                result={'available':False,'reason':str(error),'criterion':'historical_model_free_energy_on_training_sequences'}
    return result


def final_evaluate(payload, output):
    import admission
    import evaluation
    import diagnostic_bridge
    from native.sink import DirectoryStore
    from reporting import write
    execution=strict(capture(payload['execution_path'],payload['execution_pin']['bytes'],payload['execution_pin']))
    artifacts=payload['artifacts'];folds=payload['folds']
    def admit(disposition):
        job=disposition['job'];a=artifacts[job['id']]
        if job['phase']=='native':
            return admission.native(a['root'],disposition,a['context'],payload['per_output_read_cap'])
        f=folds[f"{job['branch']}:{job['fold']}"]
        return admission.held(a['root'],disposition,f['representation_id'],payload['per_output_read_cap'])
    def query(branch,fold):
        f=folds[f'{branch}:{fold}'];p=strict(capture(f['preparation_path'],f['preparation_pin']['bytes'],f['preparation_pin']))
        return [{'person':r['person'],'run':r['run'],'observations':array(f['root'],r['observations'],payload['array_cap'])}
                for r in p['operator_private_query']]
    def static(branch,fold):
        f=folds[f'{branch}:{fold}'];return strict(capture(f['static_path'],f['static_pin']['bytes'],f['static_pin']))
    ages=strict(capture(payload['age_path'],payload['age_pin']['bytes'],payload['age_pin']))
    def diagnostics(a):
        b=a['assembled']['branch'];store=None
        if b in ('ctf_tde','elekta_tde'):
            path=output/'nnmf'/a['job_id'];path.mkdir(parents=True,exist_ok=False)
            store=DirectoryStore(path,payload['derived_write_cap'])
        return diagnostic_bridge.run(a,ages,payload['age_identity'],store,payload['derived_read_cap'])
    result=evaluation.evaluate(execution,admit,query,static,payload['scales'],payload['scale_pins'],diagnostics)
    receipt=write(result,output/'report',payload['report_write_cap'])
    return {'evaluation_report':receipt,'complete':result['complete'],'scientific_qualification':False}


def finish(request, request_raw, output, result):
    resources=request['resources'];new_json(output/'RESULT.json',result)
    files={};total=0
    for p in sorted(output.rglob('*')):
        need(not p.is_symlink(),'No output links')
        if p.is_file():
            name=str(p.relative_to(output));size=p.stat().st_size
            need(size<=resources['max_file_bytes'],'Complete per-file allocation')
            body=capture(p,resources['max_file_bytes']);files[name]=pin(body);total+=len(body)
    need(len(files)<=resources['max_files'] and total<=resources['max_output_bytes'],'Complete phase output allocation')
    manifest={'schema':'osl_transport_output_manifest_v1','phase_id':request['phase_id'],
              'request_sha256':hashlib.sha256(request_raw).hexdigest(),'files':files}
    need(len(encoded(manifest))<=resources['manifest_bytes'],'Complete manifest allocation')
    need(len(files)+1<=resources['max_files'] and total+len(encoded(manifest))<=resources['max_output_bytes'],'Manifest included in total output allocation')
    new_json(output/'OUTPUTS.json',manifest)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--payload',default='/input/PAYLOAD.json')
    args=parser.parse_args()
    request_raw=capture('/request.json',1048576);request=strict(request_raw)
    payload=strict(capture(args.payload,request['resources']['max_file_bytes']))
    output=Path('/output')
    need(output.is_dir() and not any(output.iterdir()),'Fresh bounded provider output volume')
    action=request['action']
    table={'prepare_originals':prepare_originals,'prepare_fold':prepare_fold,
           'selection_evaluate':select_model,'final_evaluate':final_evaluate,'report':final_evaluate}
    if action=='native_attempt':
        need(request['role'] in ('B','reference'),'Canonical original native source unavailable to A')
        native_reference(payload,output)
    elif action=='held_attempt':
        need(request['role']=='reference','Private fixed reference entry point')
        finish(request,request_raw,output,held_reference(payload,output))
    else:
        need(request['role']=='operator' and action in table,'Concrete private operator phase')
        finish(request,request_raw,output,table[action](payload,output))


if __name__=='__main__':
    main()
