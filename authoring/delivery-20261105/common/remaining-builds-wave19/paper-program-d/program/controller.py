"""Concrete complete261-phase source composition; private scientific grading separate."""
import argparse,importlib.util,os,re,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from support import *
import engine
HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def validate_selection(v):
    expected={'schema','task_id','selected_by_root','operation_id','images','image_exposure_review','native_linux_host','exclusive_operator_custody','source_environment_qualified','prepared_authority','paired_authoring','source_manifest','root_source','repository_root','outer_control','container_versions','output','limits','outer_limits','profile','model_cap_bytes','phase_seconds','cleanup_seconds','docker','array_ceiling_bytes','expanded_ceiling_bytes','host_versions','source_qualification_inherited'}
    need(type(v)is dict and set(v)==expected and v['schema']=='critical_init_full29_operation_v1' and v['task_id']==TASK,'exact operation selection')
    need(all(v[k]is True for k in ('selected_by_root','native_linux_host','exclusive_operator_custody','source_environment_qualified')) and v['source_qualification_inherited']is False,'explicit future qualified operation; no source inheritance')
    need(type(v['operation_id'])is str and re.fullmatch('[a-z0-9-]{1,80}',v['operation_id']),'owned operationid');need(set(v['images'])==set(ROLES) and all(re.fullmatch('sha256:[a-f0-9]{64}',x) for x in v['images'].values()),'exact immutable images');need(v['images']['A']==v['images']['B'],'matched generic A/B numerical image')
    need(v['image_exposure_review']['no_author_code_in_generic_image']is True and v['image_exposure_review']['no_candidate_access_to_operator_runtime']is True and v['image_exposure_review']['no_network_or_extra_mounts']is True,'independent image and source exposure review')
    need(set(v['phase_seconds'])=={'native','fit','stream'} and all(type(x)is int and x>0 for x in v['phase_seconds'].values()) and type(v['cleanup_seconds'])is int and v['cleanup_seconds']>=60,'complete phase/cleanup allowances')
    need(v['outer_limits']['wall_seconds']>=v['limits']['wall_seconds']+120,'separate original outerclosure interval')
    need(set(v['container_versions'])==set(ROLES) and v['container_versions']['A']==v['container_versions']['B'],'matched declared numerical versions')
    p=v['profile'];need(set(p)=={'memory_bytes','cpus','pids','tmp_bytes','threads'} and all(type(p[k])is int and p[k]>0 for k in ('memory_bytes','pids','tmp_bytes','threads')) and type(p['cpus'])in(int,float) and math.isfinite(p['cpus']) and p['cpus']>0,'explicit matched resources')
    need(type(v['model_cap_bytes'])is int and v['model_cap_bytes']>0 and v['model_cap_bytes']+1048576<p['memory_bytes'],'entire quota-backed fit output plus process memory separately admitted');return v

def capture_source(v,budget,out):
    raw=read(v['source_manifest']['path'],v['source_manifest'],budget,1048576);m=parse(raw);need(m['schema']=='critical_init_program_source_v1' and m['task_id']==TASK and type(m['files'])is dict and 1<=len(m['files'])<=128,'complete captured source set');bodies={}
    for n,d in m['files'].items():
        need(not n.startswith('/') and '..' not in Path(n).parts,'relative source');body=read(ordinary(v['root_source'])/n,d,budget,16777216);bodies[n]=body;write(out/'source'/n,body,budget)
    write(out/'source/SOURCE_MANIFEST.json',raw,budget);need(set(bodies)==set(m['files']),'complete runtime source');return bodies,descriptor(v['source_manifest'])

def global_commit(v,bodies,budget,out):
    pair=parse(read(v['paired_authoring']['path'],v['paired_authoring'],budget,1048576));need(pair['schema']=='critical_init_four_program_pair_v1' and pair['task_id']==TASK and set(pair['programs'])=={'A','B'},'exact fourprogram pair');need(pair['separate_contexts_attested']is True and pair['numeric_exposure_before_freeze']is False and pair['cross_program_feedback']is False,'independent globalfreeze before data')
    binding=parse(bodies['BINDING.json']);seen=set();programs={}
    for arm in ('A','B'):
        need(set(pair['programs'][arm])==set(PURPOSES),'native and forecastbotharms')
        for purpose in PURPOSES:
            row=pair['programs'][arm][purpose];need(row['context_id']not in seen and type(row['context_id'])is str and row['image']==v['images'][arm] and row['authoring_protocol']==pair['authoring_protocol'],'distinct matched authoring contexts');seen.add(row['context_id']);need(row['numeric_inputs_seen']is False and row['operator_material_seen']is False,'no forbidden prefreeze exposure')
            expected=binding['common_authoring']+(binding['expanded_author_code'] if arm=='B' else [])
            need(row['visible_materials']==expected and row['interface_sha256']==pin(bodies['CANDIDATE_ABI.md'])['sha256'],'same exact paper/spec plus B-only expandedsource')
            body=read(row['program']['path'],row['program'],budget,8388608);need(body and '\0'not in body.decode('utf8'),'bounded UTF8 program');p=out/'programs'/arm/(purpose+'.py');d=write(p,body,budget);programs[(arm,purpose)]={'path':str(p),**d}
    receipt={'schema':'critical_init_global_four_program_freeze_v1','task_id':TASK,'pair':descriptor(v['paired_authoring']),'programs':{arm:{purpose:programs[(arm,purpose)] for purpose in PURPOSES} for arm in ('A','B')},'all_four_before_numeric_views':True,'independent_context_history_is_external_attestation':True,'future_method_exposure_review_required':True}
    write(out/'COMMITMENT.json',encode(receipt),budget);return programs,receipt

def admit_prepared(v,budget,sessions):
    p=v['prepared_authority'];a=parse(read(p['path'],p,budget,1048576));need(a['schema']=='critical_init_preparation_admission_v1' and a['admitted_by_root']is True and a['external_natural_exit_admitted']is True and a['full29_publisher_and_shape_identity_admitted']is True,'independent authentic preparation admission')
    raw=read(a['prepared']['path'],a['prepared'],budget,1048576);bundle=parse(raw);need(bundle['schema']=='critical_init_full29_prepared_v1' and bundle['task_id']==TASK and bundle['source']==descriptor(v['source_manifest']) and [r['session_id'] for r in bundle['records']]==[s['session_id'] for s in sessions],'complete exact prepared29')
    for s,r in zip(sessions,bundle['records']):
        g=r['native_geometry'];native_shape_support(g,s);need(r['partition']==partition(g['n_fig3'],g['t_fig3']) and r['normalization_prefix_stop']==r['partition']['development_end'] and r['forecast_dtype']=='float64' and r['normalization_epsilon']==.001 and r['source_neuron_population_preserved']is True,'exact preparation profile')
        need(set(r['prepared'])=={'full.npy','development.npy','mean.npy','scale.npy'},'fullnativepopulations and completeforecast inputs')
        for d in [r['source_original'],*r['prepared'].values()]:read(d['path'],d,budget,d['bytes'],retain=False)
    return bundle,a

def stage(v,bodies,binding,record,session,asset,ctx,out,budget):
    view=out/'views'/ctx['id'];view.mkdir(parents=True,mode=0o700);expected={}
    materials=binding['common_authoring']+(binding['expanded_author_code'] if ctx['role']=='B' else [])
    for row in materials:
        dst=view/row['target'];dst.parent.mkdir(parents=True,exist_ok=True);expected[row['target']]=copy(ordinary(v['repository_root'])/row['path'],dst,row,budget)
    for name in ('CANDIDATE_ABI.md',):expected[name]=write(view/name,bodies[name],budget)
    if ctx['kind']=='native':
        row=record['source_original'];expected[session['file']]=copy(row['path'],view/session['file'],row,budget)
    elif ctx['kind']=='fit':
        for name in ('development.npy','mean.npy','scale.npy'):
            row=record['prepared'][name];expected[name]=copy(row['path'],view/name,row,budget)
    case={'versions':v['container_versions'][ctx['role']],'session':session,'asset':asset,'native_geometry':record['native_geometry'],'partition':record['partition'],'design_sha256':binding['current_design_sha256'],'device':'cpu','expanded_ceiling_bytes':v['expanded_ceiling_bytes'],'array_ceiling_bytes':v['array_ceiling_bytes'],'forecast_profile':'chronological_five_frame_processed_signal_v1','scope':'complete selected empirical core; retrospective suffix forecast; no whole-paper claim'}
    expected['CASE.json']=write(view/'CASE.json',encode(case),budget);expected['VIEW.json']=write(view/'VIEW.json',encode({'context':ctx,'files':expected,'contains_full_query_matrix':False,'contains_targets':False}),budget)
    for p in sorted(view.rglob('*'),reverse=True):
        if p.is_dir():os.chmod(p,0o555)
    os.chmod(view,0o555);return view,expected

def retire_view(view,expected,receipt,budget):
    need(receipt['status']=='captured' and receipt['all_resources_closed']is True,'closed producer before input retirement');actual={p.relative_to(view).as_posix():p for p in view.rglob('*') if not p.is_dir()};need(set(actual)==set(expected),'exact view unchanged')
    for name,p in actual.items():read(p,expected[name],budget,expected[name]['bytes'],retain=False)
    os.chmod(view,0o700)
    for p in view.rglob('*'):
        if p.is_dir():os.chmod(p,0o700)
    for p in actual.values():p.unlink()
    for p in sorted([x for x in view.rglob('*') if x.is_dir()],key=lambda x:len(x.parts),reverse=True):p.rmdir()
    view.rmdir();sync(view.parent);budget.retire(sum(d['bytes']+8192 for d in expected.values()))

def queries(record,budget):
    import numpy as np
    d=record['prepared']['full.npy'];read(d['path'],d,budget,d['bytes'],retain=False);z=np.load(d['path'],allow_pickle=False,mmap_mode='r');p=record['partition'];need(z.dtype==np.dtype('float64') and z.shape==(p['neurons'],p['frames']),'exact private fullmatrix')
    for t in range(p['query_start'],p['query_stop']):
        budget.tick();body=np.asarray(z[:,t],dtype='<f8').tobytes();budget.reading(len(body));yield body

def run(v,origin,budget=None):
    v=validate_selection(v)
    import importlib.metadata,platform
    need(v['host_versions']['python']==platform.python_version(),'qualified exacthost Python')
    for package,version in v['host_versions'].items():
        if package!='python':need(importlib.metadata.version(package)==version,'exact qualifiedhost numericalversion')
    budget=budget if budget is not None else Budget(v['limits'],origin);out=ordinary(v['output']);need(not out.exists() and out.parent.is_dir(),'exclusive new operation directory');out.mkdir(mode=0o700);bodies,source=capture_source(v,budget,out);programs,commitment=global_commit(v,bodies,budget,out);sessions=validate_cohort(parse(bodies['COHORT.json']));assets=parse(bodies['ASSETS.json'])['assets'];bundle,admission=admit_prepared(v,budget,sessions);records={r['session_id']:r for r in bundle['records']};binding=parse(bodies['BINDING.json']);design={'schema':'critical_init_design_v1','source_revision':'2c15edf4e770165fc3962dcc3920c8bcaf555bed','records':[r['native_geometry'] for r in bundle['records']]};binding['current_design_sha256']=pin(encode(design))['sha256'];write(out/'DESIGN.json',encode(design),budget)
    plan=resource_components(design['records'],v['model_cap_bytes']);write(out/'RESOURCE_COMPONENTS.json',encode(plan),budget);required=plan['five_method_prediction_numeric_bytes']+plan['model_capture_ceiling_bytes']+plan['native_json_capture_ceiling_bytes'];need(required<budget.limits['retained_bytes'],'complete declared components inside selected retention, additionalstaging remains checked');budget.reserve(out,required)
    expected=phases(sessions);phase_records=[];models={};native={r:[] for r in ROLES};forecast={r:{} for r in ROLES}
    for base in expected:
        r=records[base['session_id']];s=next(x for x in sessions if x['session_id']==base['session_id']);asset=next(x for x in assets if x['session_id']==base['session_id']);ctx={**base}
        if ctx['kind']=='stream':ctx['partition']=r['partition']
        view,files=stage(v,bodies,binding,r,s,asset,ctx,out,budget);program=programs[(ctx['role'],ctx['purpose'])] if ctx['role']!='operator' else {'path':str(HERE/'operator_program.py'),**pin(bodies['operator_program.py'])};read(program['path'],program,budget,8388608,retain=False)
        model=models.get((ctx['role'],ctx['session_id']))
        if ctx['kind']=='stream':need(model is not None,'same-session captured sealed fittedstate');read(model['path'],model,budget,v['model_cap_bytes'],retain=False)
        receipt=engine.phase(v,ctx,view,program['path'],None if model is None else model['path'],out/'phases'/ctx['id'],budget,queries(r,budget) if ctx['kind']=='stream' else None)
        read(program['path'],program,budget,8388608,retain=False)
        if ctx['kind']=='stream':read(model['path'],model,budget,v['model_cap_bytes'],retain=False)
        if ctx['kind']=='fit':models[(ctx['role'],ctx['session_id'])]=receipt['artifacts']
        elif ctx['kind']=='native':native[ctx['role']].append(receipt['artifacts'])
        else:forecast[ctx['role']][ctx['session_id']]=receipt['artifacts']
        retire_view(view,files,receipt,budget);phase_records.append(receipt)
    need(len(phase_records)==261 and [r['context']['id'] for r in phase_records]==[r['id'] for r in expected] and all(r['status']=='captured' for r in phase_records),'complete original261 closure')
    # All candidate and reference phases are closed before semantic numeric admission.
    proto=load('ci_protocol',HERE/'native-source/public/protocol.py');native_panels={}
    for role in ROLES:
        values=[parse(read(d['path'],d,budget,67108864)) for d in native[role]];panel={'schema':'critical_init_result_v1','design_sha256':binding['current_design_sha256'],'records':values};proto.validate_result(panel,design,binding['current_design_sha256'],sessions);body=encode(panel);need(len(body)<=67108864,'original full native panel64MiBcap');native_panels[role]={'path':str(out/'panels'/(role+'-native.json')),**write(out/'panels'/(role+'-native.json'),body,budget)}
    result={'schema':'critical_init_complete_collection_v1','task_id':TASK,'source':source,'operation_id':v['operation_id'],'contexts':expected,'phase_receipts':phase_records,'commitment':commitment,'prepared_admission':descriptor(v['prepared_authority']),'prepared':admission['prepared'],'design':{'path':str(out/'DESIGN.json'),**pin(encode(design))},'native_panels':native_panels,'forecast_panels':forecast,'all261closed':True,'private_grade_called':False,'original_origin':origin,'original_deadline':budget.end,'before_final_persistence':time.monotonic(),'runtime_qualified':False,'scientific_qualified':False,'full_paper_reproduction':False,'managed_read_charge':budget.read,'managed_write_charge':budget.write,'retained_charge':budget.retained}
    receipt=write(out/'COLLECTION.json',encode(result),budget);return {'collection':receipt,'post_durability':time.monotonic(),'original_deadline':budget.end,'requires_independent_outer_exit_admission':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--selection',required=True);p.add_argument('--selection-sha256',required=True);p.add_argument('--origin',type=float,required=True);a=p.parse_args();raw,v,budget=authority(a.selection,a.selection_sha256,a.origin);result=run(v,a.origin,budget);print(encode(result).decode(),end='')
if __name__=='__main__':main()
