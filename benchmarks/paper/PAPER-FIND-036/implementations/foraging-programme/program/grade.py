"""Protected full40 grader; complete source/closure/output admission precedes y."""
import argparse,math,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from support import *
from array_io import open_array,raw_panel
import metrics,materials
HERE=Path(__file__).resolve().parent
DEPENDENCIES={'grade.py','common.py','support.py','array_io.py','metrics.py','controller.py','engine.py','docker_cli.py','observe.py','BINDING.json','reference_math.py','prepare.py','operator_program.py','operator_state.py','materials.py','CANDIDATE_ABI.md','bootstrap.py','holder.py'}
METRICS=('balanced_accuracy','avoidance_recall','escape_recall','brier','reporting_log_loss')

def phase_admission(collection,records):
    expected=phases(records,collection['model_cap_bytes']);need(collection['contexts']==expected and len(collection['phases'])==1320 and collection['all1320closed']is True and collection['private_grade_called']is False,'all 1,320 expected phases before any targets')
    origin,end=collection['original_origin'],collection['original_deadline'];previous=origin;resource_names=set()
    for ctx,r in zip(expected,collection['phases']):
        need(r['schema']=='foraging_owned_phase_v1'and r['context']==ctx and r['status']=='captured'and r['error']is None,'exact complete phase receipt')
        need(all(r[k]is True for k in ('all_resources_closed','producer_closed_before_capture','cli_reaped'))and r['private_scoring_called']is False,'natural closure before private scoring')
        need(r['natural_exit']=={'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False},'exact natural producer exit')
        need(len(r['closures'])==3 and sorted(x['kind']for x in r['closures'])==['container','container','volume']and len({x['name']for x in r['closures']})==3,'complete exact owned resource closure')
        names={x['name']for x in r['closures']};need(not names&resource_names,'fresh resource identity for every phase');resource_names.update(names)
        need(all(x['closed']is True and x['absence_observed']is True and x['creation_outcome_unknown']is False for x in r['closures']),'no unknown residual resources')
        clocks=[r[k]for k in ('started','finished','phase_work_deadline','phase_cleanup_deadline')];need(all(type(x)in(int,float)and math.isfinite(x)for x in clocks),'finite original clocks')
        need(origin<=previous<=r['started']<=r['finished']<r['phase_cleanup_deadline']<=end and r['started']<r['phase_work_deadline']<r['phase_cleanup_deadline']and r['original_work_deadline']==end,'serial original whole-work and phase cutoffs');previous=r['finished']
        commands=r['command_records'];need(type(commands)is list and commands,'observable managed command history')
        for command in commands:
            need(command['returncode']==0 and command['error_type']is None and all(command[k]is True for k in ('client_reaped','cleanup_complete','cleanup_before_original_cutoff','owned_group_absence_observed'))and command['leader_exited_with_group_alive']is False and command['group_probe_or_cleanup_error']is None,'every CLI naturally reaped without descendant survival')
            need(type(command['materialized_pipe_bytes'])is int and command['materialized_pipe_bytes']>=command['observed_retained_bytes']>=0,'actual transport I/O accounting')
        descriptor(r['artifacts']);need(0<r['artifacts']['bytes']<=ctx['output_bytes']and(ctx['kind']=='fit'or r['artifacts']['bytes']==ctx['output_bytes']),'all complete output extents')
    need(previous<=collection['before_final_persistence']<end,'collection after complete closure within original clock')
    return expected

def admission_record(v,key,schema,budget):
    d=v[key];a=parse(read(d['path'],d,budget,v['metadata_cap_bytes']));need(a['schema']==schema and a['task_id']==TASK and a['admitted_by_root']is True and a['independently_reviewed']is True,'independent exact '+key);return a

def score(v,origin,budget=None):
    import numpy as np
    need(v['schema']=='foraging_full40_grade_authority_v1'and v['task_id']==TASK and v['selected_by_root']is True and v['exclusive_operator_custody']is True,'explicit protected grading authority and exclusive target custody')
    budget=budget if budget is not None else Budget(v['limits'],origin);need(ordinary(v['root_source'])==HERE,'current grader source root')
    # Authenticate all current code and externally expected manifest before
    # importing a result, observing numerical outputs or opening target labels.
    bodies,source=authenticate_source(HERE,v['source_manifest'],budget,DEPENDENCIES)
    collection=parse(read(v['collection']['path'],v['collection'],budget,v['metadata_cap_bytes']));need(collection['schema']=='foraging_collection_v1'and collection['task_id']==TASK and collection['source']==source,'independently selected exact collection source')
    outer=admission_record(v,'outer_admission','foraging_independent_outer_admission_v1',budget)
    need(outer['collection']==descriptor(v['collection'])and outer['source']==source and all(outer[k]is True for k in ('external_natural_exit','outer_original_clock_closed','durable_collection_and_observer_closed','no_owned_process_or_resource_residual')),'external whole controller/observer natural closure')
    prepared_admission=admission_record(v,'prepared_authority','foraging_full40_preparation_admission_v1',budget)
    need(collection['prepared_admission']==descriptor(v['prepared_authority'])and descriptor(prepared_admission['prepared'])==descriptor(collection['prepared'])and all(prepared_admission[k]is True for k in ('external_natural_exit_admitted','full40_original_members_and_shape_admitted','source_preprocessing_and_fixed_window_admitted','full_native_and_nested3_support_admitted')),'exact full original preparation admission')
    bundle=parse(read(collection['prepared']['path'],collection['prepared'],budget,v['metadata_cap_bytes']));need(bundle['source']==source,'exact preparation source');records=validate_prepared(bundle)
    need(descriptor(bundle['archive'])=={'bytes':15089711,'sha256':'ed1e4551cc96acff35b895da5c608857c36c448e7b997f6f8fb4f7fefd462f2a'},'original archive identity')
    paper,_,_=materials.admit(v,bodies,budget);need(collection['paper_admission']==descriptor(v['paper_material_admission'])and paper['narrative_methods_figures_captions_complete']is True and paper['unresolved_required_materials']==[],'matched complete common paper exposure')
    exposure=admission_record(v,'method_exposure_admission','foraging_method_exposure_admission_v1',budget);need(exposure['collection']==descriptor(v['collection'])and exposure['all_four_independent_before_numeric_exposure']is True and exposure['full_scope_no_forbidden_state_or_label_access']is True,'actual candidate method/exposure compliance')
    competence=admission_record(v,'reference_competence_admission','foraging_reference_competence_admission_v1',budget);need(competence['collection']==descriptor(v['collection'])and competence['native_equations_numerical_parity_checked']is True and competence['complete_native_and_nested_logistic_competence_checked']is True and competence['no_weaker_fallback']is True,'actual independent mandatory reference competence')
    commitment=parse(read(collection['commitment']['path'],collection['commitment'],budget,v['metadata_cap_bytes']));need(commitment['schema']=='foraging_global_four_program_freeze_v1'and commitment['all_four_before_numeric_views']is True and set(commitment['programs'])=={'A','B'}and all(set(commitment['programs'][x])==set(PURPOSES)for x in ('A','B')),'all four globally committed programs')
    expected=phase_admission(collection,records)
    # Admission is deliberately complete, including every model, before the
    # first protected target read. A late malformed panel invalidates everything.
    artifacts={}
    for ctx,r in zip(expected,collection['phases']):
        d=r['artifacts'];key=(ctx['session_id'],ctx['kind'],ctx['role'],ctx['fold']);need(key not in artifacts,'unique full phase output')
        if ctx['kind']=='fit':read(d['path'],d,budget,collection['model_cap_bytes'],retain=False)
        else:raw_panel(d,ctx['rows'],ctx['columns'],budget)
        artifacts[key]=d
    mapping=None
    if v.get('animal_mapping')is not None:
        d=v['animal_mapping'];mapping=parse(read(d['path'],d,budget,v['metadata_cap_bytes']))
        # Validate complete authenticated identity mapping before its use; never
        # infer animals from session labels. This is scientific cohort metadata,
        # not a user/private personal identity key.
        animal_description({r['session_id']:0.0 for r in records},records,mapping)
    per_native={arm:{}for arm in ROLES};fidelity={arm:{}for arm in ('A','B')};per_improvement={arm:{}for arm in ('A','B',*REFERENCES)}
    for r in records:
        sid=r['session_id'];y=open_array(r['prepared']['y.npy'],budget,(r['rows'],),'int64');budget.reading(y.nbytes);need(np.isin(y,[0,1]).all()and len(np.unique(y))==2,'complete protected binary labels')
        panels={role:raw_panel(artifacts[(sid,'native',role,0)],r['rows'],101,budget)for role in ROLES}
        for role in ROLES:per_native[role][sid]=metrics.finish(metrics.add(metrics.accumulator(101),y,panels[role],budget))
        for role in ('A','B'):fidelity[role][sid]=metrics.fidelity(panels[role],panels['operator'],budget)
        states={arm:metrics.accumulator(1)for arm in per_improvement}
        for fold in r['folds']:
            query=fold['query_order0'];budget.reading(8*len(query));truth=np.asarray(y[query],dtype=np.int64)
            for role in ROLES:
                p=raw_panel(artifacts[(sid,'predict',role,fold['fold'])],len(query),3 if role=='operator'else 1,budget)
                if role=='operator':
                    for col,name in enumerate(REFERENCES):metrics.add(states[name],truth,p[:,col:col+1],budget)
                else:metrics.add(states[role],truth,p,budget)
        for method in per_improvement:per_improvement[method][sid]=metrics.finish(states[method])[0]
        del y,panels
    native={}
    for role in ROLES:
        native[role]={'real':{metric:equal_sessions({sid:rows[0][metric]for sid,rows in per_native[role].items()},records)for metric in METRICS},'seeded_control_balanced_accuracies':[equal_sessions({sid:rows[j]['balanced_accuracy']for sid,rows in per_native[role].items()},records)for j in range(1,101)],'sessions':per_native[role]}
        x=native[role]['seeded_control_balanced_accuracies'];mean=math.fsum(x)/100;sd=math.sqrt(math.fsum((a-mean)**2 for a in x)/99);native[role]['seeded_control_summary']={'mean':mean,'monte_carlo_sd':sd,'monte_carlo_se':sd/10,'calibrated_permutation_p_value':None,'historical_unseeded_RNG_reproduced':False}
    reproduction={arm:{'primary_equal_session_real_probability_MAE':equal_sessions({sid:x['mean_absolute_error_by_column'][0]for sid,x in fidelity[arm].items()},records),'max_real_probability_error':max(x['max_absolute_error_by_column'][0]for x in fidelity[arm].values()),'separate_seeded_control_MAE_by_replicate':[equal_sessions({sid:x['mean_absolute_error_by_column'][j]for sid,x in fidelity[arm].items()},records)for j in range(1,101)],'sessions':fidelity[arm]}for arm in ('A','B')}
    improvement={method:{'equal_session':{metric:equal_sessions({sid:m[metric]for sid,m in per_improvement[method].items()},records)for metric in METRICS},'sessions':per_improvement[method]}for method in per_improvement};paired={}
    for arm in ('A','B'):
        paired[arm]={}
        for ref in REFERENCES:
            diffs={sid:per_improvement[arm][sid]['balanced_accuracy']-per_improvement[ref][sid]['balanced_accuracy']for sid in per_improvement[arm]};paired[arm][ref]={'session_BA_differences':diffs,'equal_session_BA_difference':equal_sessions(diffs,records),'animal_descriptive_stability':animal_description(diffs,records,mapping)}
    result={'schema':'foraging_full40_results_v1','task_id':TASK,'collection':descriptor(v['collection']),'source':source,'sessions':40,'outer_folds':200,'producer_phases':1320,'native_reproduction':reproduction,'native_real_and_separate_seeded_control':native,'hidden_label_improvement':improvement,'paired_BA_improvement':paired,'historical_report_only':{'real_BA':.7271,'unseeded_shuffled_BA':.5162,'t39':10.06,'p_less_than':.001},'scope':'complete selected Figure6B real-HW endpoint and separately named controlled/improvement programs; not whole-paper reproduction','released_features_transductive':True,'session_weighting_can_overweight_animals':True,'causal_or_new_animal_claim':False,'method_novelty_or_SOTA_claim':False,'synthetic_composite_score':None,'current_execution_requires_independent_result_review':True,'before_final_persistence':time.monotonic()}
    raw=encode_bounded(result,v['metadata_cap_bytes']);d={'path':str(ordinary(v['output'])),**write(v['output'],raw,budget)};return {'result':d,'post_durability':time.monotonic(),'original_deadline':budget.end,'requires_independent_outer_exit_admission':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--authority',required=True);p.add_argument('--sha256',required=True);p.add_argument('--origin',type=float,required=True);a=p.parse_args();raw,v,budget=authority(a.authority,a.sha256,a.origin);print(encode(score(v,a.origin,budget)).decode(),end='')
if __name__=='__main__':main()
