"""Fixed original-author entry adapter. Never imported/run in build-only controls.

The original source is independently pinned before import. Known silent-fallback
and catch-and-continue branches remain original outputs requiring qualification;
an exit code alone never establishes valid scientific output.
"""
import argparse
import importlib.util
import inspect
import io
import os
from pathlib import Path
import sys
from .custody import need,read_pin,write_new,write_json,new_directory,capture
from .guard import Budget
from .workflow import selected_plan
from .native_abi import construct

ROUTES={
 'dense':'simulations.py:simulate_random',
 'distribution_grid':'simulations.py:random_probs_sim',
 'bin_grid':'simulations.py:tbin_analysis',
 'noise_grid':'simulations.py:random_uniform_sim_sizes',
 'near_critical_examples':'simulations.py:sims_fig2',
 'near_critical_grid':'simulations.py:enorm_sweep',
 'sparse_grid':'fig4/sparse_clustered_local_sims.py:sparse_evals',
 'cluster_grid':'fig4/sparse_clustered_local_sims.py:clustered_evals',
 'local_grid':'fig4/sparse_clustered_local_sims.py:local_evals',
 'spatial_neural':'fig4/analysis.py:neural_strong_pairs',
 'memory_binary':'fig5/fig5.py:run_multishot',
 'memory_zeroshot':'fig5/fig5.py:run_zeroshot',
 'core_powerlaws':'fig2/analysis.py:neural_powerlaws',
 'ephys_areas':'fig2/analysis.py:ephys_areas',
 'ephys_binning':'fig2/analysis.py:ephys_tbins',
 'behavioural_state':'fig2/analysis.py:running',
 'reduced_rate_imaging':'fig2/analysis.py:gcamp_subsample',
 'core_dmd':'lyapun.py:dmd',
 'core_acg':'lyapun.py:pc_timescales',
 'external_plitt':'fig3/other_datasets.py:plitt_hippo',
 'external_grosmark':'fig3/other_datasets.py:grosmark_hippo',
 'external_zhong':'fig3/other_datasets.py:zhong_visual',
 'external_area2':'fig3/other_datasets.py:area2_bump',
 'external_rtt':'fig3/other_datasets.py:mc_rtt',
 'external_maze':'fig3/other_datasets.py:mc_maze',
 'render_fig1':'fig1/fig1.py:fig1',
 'render_fig2':'fig2/fig2.py:fig2',
 'render_fig4':'fig4/fig4.py:fig4',
 'render_ed1':'fig1/fig1.py:suppfig_probs',
 'render_ed2':'fig1/fig1.py:suppfig_sim',
 'render_ed3':'fig1/fig1.py:suppfig_tbin',
 'render_ed4':'fig1/fig1.py:suppfig_poisson',
 'render_ed5':'fig2/fig2.py:suppfig_ephys',
 'render_ed6':'fig2/fig2.py:suppfig_svca2',
 'render_ed7':'fig2/fig2.py:suppfig_running',
 'render_ed8':'fig3/other_datasets.py:suppfig_rotate'
}

def _original_call(root,job,body,output,budget,arguments):
    need(job['native_route']in ROUTES,'fixed genuine original route')
    relative,function=ROUTES[job['native_route']].split(':')
    source_root=Path(body['native_source_root'])
    need(source_root.is_absolute(),'qualified immutable native source root')
    expected=body['native_files'][relative]
    need(Path(expected['path'])==source_root/relative,'fixed route path pin')
    for record in body['native_files'].values():read_pin(root,record,body['evidence_cap_bytes'],budget)
    need(job['native_import_closure']==body['native_import_closure'],'whole qualified original import closure')
    # Isolation happens in a fresh process, so fig2/fig4 analysis modules cannot
    # contaminate one another through Python's import cache.
    sys.path[:0]=[str((source_root/relative).parent),str(source_root)]
    spec=importlib.util.spec_from_file_location('_critical_init_original_entry',source_root/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    fn=getattr(module,function)
    for name in job['path_arguments']:
        need(name in arguments,'declared original path argument')
        if type(arguments[name])is list:arguments[name]=[Path(x)for x in arguments[name]]
        else:arguments[name]=Path(arguments[name])
    if 'device' in inspect.signature(fn).parameters:
        import torch
        arguments['device']=torch.device(body['native_device'])
    inspect.signature(fn).bind(**arguments)
    # Preserve original relative results paths inside the owned writable job.
    output=Path(output).absolute()
    stage=new_directory(output,'native_stage',budget)
    results_dir=new_directory(output,'results',budget)
    for link in job['native_input_links']:
        name=link['name'];target=link['target']
        need(type(name)is str and '/'not in name and name not in ('.','..'),'one native relative input directory')
        need(type(target)is str and target.startswith('/input/')and '..'not in Path(target).parts,'selected read-only input mount only')
        os.symlink(target,stage/name)
    previous=Path.cwd()
    try:
        os.chdir(stage)
        result=fn(**arguments)
    finally:os.chdir(previous)
    import numpy as np
    artifacts=[];saved_results={}
    for item in job['native_side_effect_outputs']:
        relative=Path(item['path'])
        need(not relative.is_absolute()and '..'not in relative.parts and relative.parts[0]=='results','original results only in owned namespace')
        raw,identity=capture(output/relative,item['cap_bytes'],budget)
        need(item['format']in ('numpy_object_dictionary','npz_numeric','ordinary_binary'),'selected original output format')
        if item['format']=='numpy_object_dictionary':
            # This is the just-produced, pinned AUTHOR output inside the already
            # isolated native process, never candidate input to the grader.
            value=np.load(io.BytesIO(raw),allow_pickle=True).item()
            need(type(value)is dict and set(value)==set(item['required_keys']),'complete original native result dictionary')
            saved_results[item['role']]=value
        elif item['format']=='npz_numeric':
            with np.load(io.BytesIO(raw),allow_pickle=False)as z:
                need(set(z.files)==set(item['required_keys']),'complete original saved result schema')
                saved_results[item['role']]={k:z[k].copy()for k in z.files}
        artifacts.append({'role':item['role'],'original_file':identity,'format':item['format'],
                          'parsed':item['format']!='ordinary_binary','scientifically_qualified':False})
    arrays={};nonfinite={}
    def convert(value):
        if hasattr(value,'detach'):value=value.detach().cpu().numpy()
        if isinstance(value,np.ndarray):
            need(value.dtype.kind in 'biufc','native object arrays require separate admitted projection')
            key='a'+str(len(arrays));arrays[key]=value
            count=int((~np.isfinite(value)).sum());nonfinite[key]=count
            return {'array':key,'shape':list(value.shape),'dtype':value.dtype.str,'nonfinite_elements':count}
        if isinstance(value,np.generic):return convert(value.item())
        if type(value)is dict:return {str(k):convert(v)for k,v in value.items()}
        if type(value)in (tuple,list):return [convert(v)for v in value]
        if value is None or type(value)in (str,bool,int,float):return value
        # Genuine author render outputs, never a substitute for numeric targets.
        if type(value).__module__.startswith('matplotlib.') and hasattr(value,'savefig'):
            stream=io.BytesIO();value.savefig(stream,format='png')
            binding=write_new(Path(output)/'figure.png',stream.getvalue(),budget)
            return {'render':binding,'numeric_gold':False}
        raise ValueError('unadmitted native result type')
    skeleton=convert({'return':result,'saved_results':saved_results});buffer=io.BytesIO();np.savez(buffer,**arrays)
    array_pin=write_new(Path(output)/'native_result.npz',buffer.getvalue(),budget)
    record={'job_id':job['id'],'route':job['native_route'],'literal_original_source':expected,
            'result':skeleton,'arrays':array_pin,'nonfinite_elements':nonfinite,'original_side_effect_artifacts':artifacts,
            'valid_reference':False,'requires_original_process_and_native_semantic_qualification':True,
            'costs':budget.record()}
    return write_json(Path(output)/'native_result.json',record,budget)

def original_call(root,job,body,output,budget):
    # No author module is imported until every nested input has been admitted.
    need(job['native_route']in ROUTES,'fixed genuine original route')
    arguments,reserved=construct(root,job['id'],job['native_abi'],body['native_abi_jobs'],budget)
    try:
        return _original_call(root,job,body,output,budget,arguments)
    finally:
        original=sys.exception();arguments.clear()
        try:budget.release_array(reserved)
        except BaseException as cleanup:
            if original is None:raise
            original.add_note('native argument release: '+type(cleanup).__name__)

def main():
    parser=argparse.ArgumentParser()
    for name in ('root','selection_path','selection_sha256','job','output'):parser.add_argument('--'+name.replace('_','-'),required=True)
    for name in ('selection_bytes','read_bytes','write_bytes','array_bytes'):parser.add_argument('--'+name.replace('_','-'),required=True,type=int)
    parser.add_argument('--seconds',required=True,type=float)
    a=parser.parse_args();budget=Budget(seconds=a.seconds,read_bytes=a.read_bytes,write_bytes=a.write_bytes,array_bytes=a.array_bytes)
    authority={'path':a.selection_path,'bytes':a.selection_bytes,'sha256':a.selection_sha256}
    selection,scope,census=selected_plan(a.root,authority,budget,'native_reference')
    job=next(j for j in census['jobs']if j['id']==a.job)
    need(job['operation']=='native_reference'and job['kind']=='native','exact original native job')
    need(a.array_bytes==job['logical_array_bytes'] and a.seconds<=job['limits']['seconds'],'selected native worker resource envelope')
    return original_call(a.root,job,selection.body,a.output,budget)

if __name__=='__main__':main()

