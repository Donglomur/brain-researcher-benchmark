"""Complete full40 native A/B and 200-fold improvement A/B construction."""
import argparse,importlib.metadata,os,platform,re,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from support import *
import array_io,engine,materials
HERE=Path(__file__).resolve().parent
REQUIRED={'common.py','controller.py','support.py','array_io.py','materials.py','engine.py','docker_cli.py','holder.py','bootstrap.py','operator_program.py','operator_state.py','reference_math.py','prepare.py','observe.py','grade.py','metrics.py','CANDIDATE_ABI.md','BINDING.json'}

def validate_selection(v):
    need(type(v)is dict and v['schema']=='foraging_full40_operation_v1'and v['task_id']==TASK,'exact full40 operation')
    need(all(v[k]is True for k in ('selected_by_root','native_linux_host','exclusive_operator_custody','source_environment_qualified'))and v['source_qualification_inherited']is False,'future independently qualified operation; no inherited scientific qualification')
    need(type(v['operation_id'])is str and re.fullmatch('[a-z0-9-]{1,80}',v['operation_id']),'owned operation ID')
    need(set(v['images'])==set(ROLES)and all(re.fullmatch('sha256:[a-f0-9]{64}',x)for x in v['images'].values())and v['images']['A']==v['images']['B'],'exact cached and matched A/B images')
    q=v['image_exposure_review'];need(all(q[k]is True for k in ('independently_reviewed','no_author_code_in_generic_image','no_candidate_access_to_operator_runtime','no_network_or_extra_mounts')),'independent image/source exposure review')
    need(set(v['phase_seconds'])=={'native','fit','predict'}and all(type(x)is int and x>0 for x in v['phase_seconds'].values())and type(v['cleanup_seconds'])is int and v['cleanup_seconds']>=60,'explicit phase/cleanup allowances')
    need(type(v['metadata_cap_bytes'])is int and 1048576<=v['metadata_cap_bytes']<=v['controller_limits']['read_bytes'],'bounded full collection/metadata capacity')
    need(set(v['container_versions'])==set(ROLES)and v['container_versions']['A']==v['container_versions']['B'],'matched dependency profiles')
    for versions in [v['host_versions'],*v['container_versions'].values()]:
        need(versions['numpy']=='2.2.6'and versions['scipy']=='1.15.3'and versions['scikit-learn']=='1.6.1'and type(versions['python'])is str,'exact adopted numerical reconstruction profile; Python/image additionally qualified')
    p=v['profile'];need(set(p)=={'memory_bytes','cpus','pids','tmp_bytes','threads'}and all(type(p[k])is int and p[k]>0 for k in ('memory_bytes','pids','tmp_bytes','threads'))and type(p['cpus'])in(int,float)and math.isfinite(p['cpus'])and p['cpus']>0,'matched explicit resource profile')
    need(type(v['model_cap_bytes'])is int and v['model_cap_bytes']>0 and v['model_cap_bytes']+1048576<p['memory_bytes'],'opaque model cap within separately qualified process resources')
    for key in ('array_ceiling_bytes','mat_decoded_bytes','numeric_array_bytes'):need(type(v[key])is int and v[key]>0,'explicit complete array/decode capacity')
    return v

def global_commit(v,bodies,common,binding,budget,out):
    pair=parse(read(v['paired_authoring']['path'],v['paired_authoring'],budget,v['metadata_cap_bytes']))
    need(pair['schema']=='foraging_four_program_pair_v1'and pair['task_id']==TASK and set(pair['programs'])=={'A','B'},'exact globally frozen four-program pair')
    need(pair['separate_contexts_attested']is True and pair['numeric_exposure_before_freeze']is False and pair['cross_program_feedback']is False,'external independent authoring history; no numerical exposure or cross-program feedback')
    programs={};seen=set()
    for arm in ('A','B'):
        need(set(pair['programs'][arm])==set(PURPOSES),'both native and improvement programs')
        for purpose in PURPOSES:
            r=pair['programs'][arm][purpose];need(type(r['context_id'])is str and r['context_id']and r['context_id']not in seen,'four distinct authoring contexts');seen.add(r['context_id'])
            need(r['image']==v['images'][arm]and r['authoring_protocol']==pair['authoring_protocol']and r['numeric_inputs_seen']is False and r['operator_material_seen']is False,'matched authoring protocol and no privileged exposure')
            need(r['visible_materials']==materials.visible(common,binding,arm)and r['interface_sha256']==pin(bodies['CANDIDATE_ABI.md'])['sha256'],'identical exact common paper/interface plus B author code')
            raw=read(r['program']['path'],r['program'],budget,8388608);need(raw and '\0'not in raw.decode('utf8'),'bounded UTF8 program');target=out/'programs'/arm/(purpose+'.py');programs[(arm,purpose)]={'path':str(target),**write(target,raw,budget)}
    receipt={'schema':'foraging_global_four_program_freeze_v1','task_id':TASK,'pair':descriptor(v['paired_authoring']),'programs':{arm:{purpose:programs[(arm,purpose)]for purpose in PURPOSES}for arm in ('A','B')},'all_four_before_numeric_views':True,'independent_context_history_is_external_attestation':True,'no_scientific_qualification':True}
    return programs,{'path':str(out/'COMMITMENT.json'),**write(out/'COMMITMENT.json',encode(receipt),budget)}

def admit_prepared(v,budget):
    d=v['prepared_authority'];a=parse(read(d['path'],d,budget,v['metadata_cap_bytes']))
    need(a['schema']=='foraging_full40_preparation_admission_v1'and a['task_id']==TASK and all(a[k]is True for k in ('admitted_by_root','independently_reviewed','external_natural_exit_admitted','full40_original_members_and_shape_admitted','source_preprocessing_and_fixed_window_admitted','full_native_and_nested3_support_admitted')),'complete independently admitted original preparation')
    raw=read(a['prepared']['path'],a['prepared'],budget,v['metadata_cap_bytes']);bundle=parse(raw);need(bundle['source']==descriptor(v['source_manifest']),'preparation source matches exact selected program')
    need(descriptor(bundle['archive'])=={'bytes':15089711,'sha256':'ed1e4551cc96acff35b895da5c608857c36c448e7b997f6f8fb4f7fefd462f2a'},'exact original Dryad archive; no substitute source')
    records=validate_prepared(bundle)
    for r in records:
        need(r['features']*r['rows']*8<=v['array_ceiling_bytes'],'complete selected array capacity; no smaller endpoint fallback')
        need(v['model_cap_bytes']>=8*(7*r['features']+54)+65554,'complete operator state plus bounded header')
    return bundle,a

def case_metadata(v,r,ctx):
    case={'kind':ctx['kind'],'rows':ctx['rows'],'features':r['features'],'columns':ctx['columns'],'versions':v['container_versions'][ctx['role']],'model_cap_bytes':v['model_cap_bytes'],'fixed_window_seconds':[-1,1],'released_preprocessing':'whole-session normalized; temporally smoothed; transductive','device':'cpu'}
    if ctx['kind']=='native':case.update(source_session_token=r['source_session_token'],source_folds=[{k:f[k]for k in ('fold','train_positions0','test_positions0')}for f in r['folds']],original_mat_bytes=r['original_mat']['bytes'],mat_decoded_bytes=v['mat_decoded_bytes'],numeric_array_bytes=v['numeric_array_bytes'])
    return case

def stage(v,bodies,common,binding,r,ctx,out,budget):
    import numpy as np
    view=out/'views'/uuid.uuid4().hex;need(not view.exists(),'fresh opaque view namespace');mkdir_owned(view,budget);files=materials.stage(common,binding,ctx['role'],bodies,view,budget)
    for d in files.values():d['allocation_charge']=d['bytes']+8192
    case=case_metadata(v,r,ctx)
    if ctx['kind']=='native':
        d=r['original_mat'];files['original.mat']={**copy(d['path'],view/'original.mat',d,budget),'allocation_charge':d['bytes']+8192}
    else:
        f=r['folds'][ctx['fold']-1];positions=f['train_order0']if ctx['kind']=='fit'else f['query_order0'];budget.reading(8*len(positions)*r['features']);x=array_io.open_array(r['prepared']['X.npy'],budget,(r['rows'],r['features']),'float64');selected=np.asarray(x[positions],dtype=np.float64);name='Xtrain.npy'if ctx['kind']=='fit'else 'Xquery.npy';desc=array_io.save_array(view/name,selected,budget);files[name]={**descriptor(desc),'allocation_charge':selected.nbytes+131072};del selected,x
        if ctx['kind']=='fit':
            budget.reading(8*len(positions));y=array_io.open_array(r['prepared']['y.npy'],budget,(r['rows'],),'int64');selected=np.asarray(y[positions],dtype=np.int64);desc=array_io.save_array(view/'ytrain.npy',selected,budget);files['ytrain.npy']={**descriptor(desc),'allocation_charge':selected.nbytes+131072};del selected,y
    # No private context/session/fold/row identity enters improvement CASE.
    d=write(view/'CASE.json',encode(case),budget);files['CASE.json']={**d,'allocation_charge':d['bytes']+8192}
    for p in sorted(view.rglob('*'),key=lambda x:len(x.parts),reverse=True):
        if p.is_dir():os.chmod(p,0o555)
    os.chmod(view,0o555);return view,files

def retire_view(view,files,receipt,budget):
    need(receipt['status']=='captured'and receipt['all_resources_closed']is True,'all resources closed before input retirement')
    dirs=[view,*[p for p in view.rglob('*')if p.is_dir()]];actual={p.relative_to(view).as_posix():p for p in view.rglob('*')if not p.is_dir()};need(set(actual)==set(files),'exact view file inventory')
    for name,p in actual.items():read(p,files[name],budget,files[name]['bytes'],retain=False)
    for p in dirs:os.chmod(p,0o700)
    for p in actual.values():p.unlink()
    for p in sorted(dirs,key=lambda x:len(x.parts),reverse=True):p.rmdir()
    sync(view.parent);budget.retire(sum(d['allocation_charge']for d in files.values())+8192*len(dirs))

def stage_model_alias(model,out,budget):
    # Docker mountinfo can expose bind source paths: never mount the retained
    # phase/<source-digest>-f<fold> locator into a candidate process.
    path=out/'model-views'/uuid.uuid4().hex/'model.bin';need(not path.parent.exists(),'fresh opaque model alias namespace')
    return {'path':str(path),**copy(model['path'],path,model,budget)}

def retire_model_alias(alias,receipt,budget):
    need(receipt['status']=='captured'and receipt['all_resources_closed']is True,'closed producer before alias retirement');path=ordinary(alias['path']);need(list(path.parent.iterdir())==[path],'only owned model alias')
    read(path,alias,budget,alias['bytes'],retain=False);path.unlink();path.parent.rmdir();sync(path.parent.parent);budget.retire(alias['bytes']+16384)

def run(v,origin,budget=None):
    v=validate_selection(v);need(v['host_versions']['python']==platform.python_version(),'qualified exact host Python')
    for package,version in v['host_versions'].items():
        if package!='python':need(importlib.metadata.version(package)==version,'qualified exact host dependency')
    budget=budget if budget is not None else Budget(v['controller_limits'],origin);need(ordinary(v['root_source'])==HERE,'execute only exact captured source directory')
    bodies,source=authenticate_source(HERE,v['source_manifest'],budget,REQUIRED);out=ordinary(v['output']);need(not out.exists()and out.parent.is_dir(),'exclusive fresh operation directory');mkdir_owned(out,budget)
    paper,common,binding=materials.admit(v,bodies,budget);programs,commitment=global_commit(v,bodies,common,binding,budget,out);bundle,admission=admit_prepared(v,budget);records=bundle['records'];lookup={r['session_id']:r for r in records};plan=resources(records,v['model_cap_bytes']);write(out/'RESOURCE_COMPONENTS.json',encode(plan),budget)
    minimum=plan['three_native_output_numeric_bytes']+plan['five_improvement_output_numeric_bytes']+plan['all_sealed_model_ceiling_bytes'];need(minimum<budget.limits['retained_bytes'],'complete result/model components plus separately metered additional costs');budget.reserve(out,minimum)
    expected=phases(records,v['model_cap_bytes']);receipts=[];models={}
    for ctx in expected:
        r=lookup[ctx['session_id']];view,files=stage(v,bodies,common,binding,r,ctx,out,budget);program=programs[(ctx['role'],ctx['purpose'])]if ctx['role']!='operator'else {'path':str(HERE/'operator_program.py'),**pin(bodies['operator_program.py'])};read(program['path'],program,budget,8388608,retain=False)
        key=(ctx['role'],ctx['session_id'],ctx['fold']);model=models.get(key)if ctx['kind']=='predict'else None
        if ctx['kind']=='predict':need(model is not None,'exact same role/session/fold captured state');read(model['path'],model,budget,v['model_cap_bytes'],retain=False)
        alias=stage_model_alias(model,out,budget)if model is not None else None
        receipt=engine.phase(v,ctx,view,program['path'],None if alias is None else alias['path'],out/'phases'/ctx['id'],budget)
        read(program['path'],program,budget,8388608,retain=False)
        if model is not None:read(model['path'],model,budget,v['model_cap_bytes'],retain=False)
        if ctx['kind']=='fit':models[key]=receipt['artifacts']
        if alias is not None:retire_model_alias(alias,receipt,budget)
        retire_view(view,files,receipt,budget);receipts.append(receipt)
    need(len(receipts)==1320 and [r['context']for r in receipts]==expected and all(r['status']=='captured'for r in receipts),'complete 1,320-phase closure')
    result={'schema':'foraging_collection_v1','task_id':TASK,'source':source,'operation_id':v['operation_id'],'contexts':expected,'phases':receipts,'commitment':commitment,'prepared_admission':descriptor(v['prepared_authority']),'prepared':admission['prepared'],'paper_admission':descriptor(v['paper_material_admission']),'all1320closed':True,'private_grade_called':False,'original_origin':origin,'original_deadline':budget.end,'before_final_persistence':time.monotonic(),'runtime_qualified':False,'scientific_qualified':False,'full_paper_reproduction':False,'managed_read_charge':budget.read,'managed_write_charge':budget.write,'retained_charge':budget.retained,'model_cap_bytes':v['model_cap_bytes']}
    raw=encode_bounded(result,v['metadata_cap_bytes']);receipt={'path':str(out/'COLLECTION.json'),**write(out/'COLLECTION.json',raw,budget)};return {'collection':receipt,'post_durability':time.monotonic(),'original_deadline':budget.end,'requires_independent_outer_exit_admission':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--selection',required=True);p.add_argument('--sha256',required=True);p.add_argument('--origin',type=float,required=True);a=p.parse_args();raw,v,budget=authority(a.selection,a.sha256,a.origin,'controller_limits');print(encode(run(v,a.origin,budget)).decode(),end='')
if __name__=='__main__':main()
