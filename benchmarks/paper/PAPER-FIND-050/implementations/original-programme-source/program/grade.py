"""Protected full-support comparison, selected only after independent outer admission."""
import argparse,importlib.util,math,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from support import *
HERE=Path(__file__).resolve().parent

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def check_collection(c,outer,cpin,sessions):
    need(c['schema']=='critical_init_complete_collection_v1' and c['task_id']==TASK and c['all261closed']is True and c['private_grade_called']is False,'complete collected program')
    need(outer['schema']=='critical_init_outer_observation_v1' and outer['collection']==cpin and outer['source']==c['source'] and outer['natural_exit']is True and outer['exit_code']==0 and outer['owned_group_absent']is True and outer['streams_eof']is True and outer['collection_durable_before_deadline']is True and outer['original_origin']==c['original_origin'] and outer['original_deadline']==c['original_deadline'],'same exact external natural closure andclock')
    expected=phases(sessions);need(c['contexts']==expected and len(c['phase_receipts'])==261,'all original roster phases')
    for e,r in zip(expected,c['phase_receipts']):
        need(all(r['context'][k]==v for k,v in e.items()) and r['status']=='captured' and r['all_resources_closed']is True and r['producer_closed_before_capture']is True and r['cli_reaped']is True and r['error']is None and r['private_scoring_called']is False,'bound closed phase')
        s=r['natural_exit'];need(s=={'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False},'natural producer zero noOOM');need(len(r['closures'])==(1 if e['kind']=='stream' else 3) and all(x['closed']is True and x['absence_observed']is True and not x['creation_outcome_unknown'] for x in r['closures']),'all exact resources closed')
        need(r['started']<r['finished']<r['phase_cleanup_deadline']<=r['original_work_deadline']==c['original_deadline'],'phase original clock')
        for q in r['command_records']:need(q['error_type']is None and q['returncode']==0 and q['client_reaped']is True and q['cleanup_complete']is True and q['owned_group_absence_observed']is True,'CLI closure record')
        if e['kind']=='stream':need(r['stream']['success']is True and r['stream']['current_predictions_durable_before_next_input']is True and r['stream']['query_count']==r['context']['partition']['queries'],'complete chronological exposure')
    need(set(c['native_panels'])==set(c['forecast_panels'])==set(ROLES),'three independent complete roles');return True

def validate_prediction_files(c,prepared,budget,sessions):
    import numpy as np
    wanted={s['session_id'] for s in sessions};maps={};by={r['session_id']:r for r in prepared['records']}
    for role in ROLES:
        need(set(c['forecast_panels'][role])==wanted,'all29 forecastrecords');maps[role]={}
        for sid in [s['session_id'] for s in sessions]:
            p=by[sid]['partition'];methods=REFERENCE_NAMES if role=='operator' else ('candidate',);rows=c['forecast_panels'][role][sid];need(set(rows)==set(methods),'complete mandatoryreference set');maps[role][sid]={}
            for method in methods:
                desc=rows[method];need(desc['bytes']==8*p['neurons']*p['queries'],'exactfullpredictionextent');read(desc['path'],desc,budget,desc['bytes'],retain=False)
                array=np.memmap(desc['path'],mode='r',dtype='<f8',shape=(p['queries'],p['neurons']))
                for j in range(0,p['queries'],128):budget.reading(array[j:j+128].nbytes);need(np.isfinite(array[j:j+128]).all(),'every predictionfinite')
                maps[role][sid][method]=array
    # Bind every final panel file to its exact phase-captured artifact; no substitution.
    for r in c['phase_receipts']:
        e=r['context']
        if e['kind']=='stream':need(c['forecast_panels'][e['role']][e['session_id']]==r['artifacts'],'panel/phase exactjoin')
    return maps

def compare_forecasts(maps,prepared,sessions,budget):
    """First target read occurs after every output/native/outer guard passes."""
    import numpy as np
    by={r['session_id']:r for r in prepared['records']};errors={role:{method:{} for method in (REFERENCE_NAMES if role=='operator' else ('candidate',))} for role in ROLES};r2={role:{method:{} for method in errors[role]} for role in ROLES}
    for s in sessions:
        sid=s['session_id'];r=by[sid];p=r['partition'];d=r['prepared']['full.npy'];read(d['path'],d,budget,d['bytes'],retain=False);z=np.load(d['path'],allow_pickle=False,mmap_mode='r');need(z.dtype==np.dtype('float64') and z.shape==(p['neurons'],p['frames']),'exact targetframe source');sums={(role,m):0. for role in ROLES for m in errors[role]};den=0.;count=p['queries']*p['neurons']
        for first in range(0,p['queries'],128):
            end=min(first+128,p['queries']);target=np.asarray(z[:,p['query_start']+first+5:p['query_start']+end+5],dtype=np.float64).T;budget.reading(target.nbytes);need(np.isfinite(target).all(),'completefinitegold');den+=float(np.sum(target*target,dtype=np.float64))
            for role,m in sums:
                pred=maps[role][sid][m][first:end];budget.reading(pred.nbytes);delta=pred-target;sums[(role,m)]+=float(np.sum(delta*delta,dtype=np.float64))
        need(math.isfinite(den) and all(math.isfinite(v) for v in sums.values()),'no metric overflow')
        for (role,m),value in sums.items():errors[role][m][sid]=value/count;r2[role][m][sid]=None if den==0 else 1-value/den
    summaries={role:{m:group_mean(rows,sessions) for m,rows in methods.items()} for role,methods in errors.items()};deltas={arm:{m:summaries['operator'][m]['value']-summaries[arm]['candidate']['value'] for m in REFERENCE_NAMES} for arm in ('A','B')}
    strata={role:{method:strata_means(rows,sessions) for method,rows in methods.items()} for role,methods in errors.items()}
    return {'descriptive_modality_and_region_MSE':strata,'strata_are_not_a_pooled_composite':True,'primary_equal_source_label_group_MSE':summaries,'reference_minus_candidate_MSE':deltas,'all_session_MSE':errors,'all_session_R2_about_development_mean':r2,'R2_undefined_when_target_energy_zero':True,'all_three_references_required':True,'higher_delta_is_better_on_this_fixed_corpus':True,'native_metric_not_combined':True,'biological_independence_verified':False,'online_or_causal_claim':False}

def score(selection,origin,budget=None):
    authority=selection
    need(authority['schema']=='critical_init_protected_grade_authority_v1' and authority['selected_by_root']is True and authority['exclusive_operator_custody']is True and authority['independent_method_exposure_and_compute_review']is True,'separate explicitly admitted grading');budget=budget if budget is not None else Budget(authority['limits'],origin);need(ordinary(authority['root_source'])==HERE,'grading executes independently selected local source');bodies,expected_source=authenticate_source(HERE,authority['source_manifest'],budget,{'grade.py','common.py','support.py','COHORT.json','native-source/public/protocol.py','native-source/operator/metrics.py'});craw=read(authority['collection']['path'],authority['collection'],budget,67108864);c=parse(craw);need(c['source']==expected_source,'independently selected grading source equals captured producer source');outer=parse(read(authority['outer']['path'],authority['outer'],budget,16777216));sessions=validate_cohort(parse(bodies['COHORT.json']));check_collection(c,outer,descriptor(authority['collection']),sessions)
    admitted=parse(read(authority['external_admission']['path'],authority['external_admission'],budget,1048576))
    need(admitted['schema']=='critical_init_root_outer_admission_v1' and admitted['outer']==descriptor(authority['outer']) and admitted['root_observed_exit_code']==0 and admitted['terminal_closed']is True and admitted['outer_post_durability_monotonic']<outer['outer_deadline'] and admitted['source_and_clock_join_admitted']is True,'separate root durable outer/terminal admission')
    prepared=parse(read(c['prepared']['path'],c['prepared'],budget,1048576));need(prepared['source']==expected_source and [r['session_id'] for r in prepared['records']]==[s['session_id'] for s in sessions],'complete matchingpreparedroster');design=parse(read(c['design']['path'],c['design'],budget,1048576));proto=load('ci_protocol_grade',HERE/'native-source/public/protocol.py');proto.validate_design(design,sessions)
    native={}
    for role in ROLES:
        p=c['native_panels'][role];native[role]=proto.validate_result(parse(read(p['path'],p,budget,67108864)),design,c['design']['sha256'],sessions)
    for r in c['phase_receipts']:
        e=r['context']
        if e['kind']=='native':
            original=parse(read(r['artifacts']['path'],r['artifacts'],budget,67108864));actual=next(x for x in native[e['role']]['records'] if x['session_id']==e['session_id']);need(actual==original,'native aggregation equals captured source output')
    maps=validate_prediction_files(c,prepared,budget,sessions)
    metrics=load('ci_metrics_grade',HERE/'native-source/operator/metrics.py');native_scores={arm:metrics.compare(native[arm],native['operator'],sessions) for arm in ('A','B')};forecast=compare_forecasts(maps,prepared,sessions,budget)
    result={'schema':'critical_init_complete_paired_comparison_v1','task_id':TASK,'source':expected_source,'collection':descriptor(authority['collection']),'outer':descriptor(authority['outer']),'native_empirical_core':native_scores,'retrospective_chronological_forecast':forecast,'no_new_task':True,'no_whole_paper_or_SOTA_claim':True,'scientific_qualification_requires_external_review':True,'original_grade_origin':origin,'finished':time.monotonic(),'managed_read_charge':budget.read}
    return write(authority['output'],encode(result),budget)

def main():
    p=argparse.ArgumentParser();p.add_argument('--authority',required=True);p.add_argument('--authority-sha256',required=True);p.add_argument('--origin',type=float,required=True);a=p.parse_args();raw,v,budget=authority(a.authority,a.authority_sha256,a.origin);score(v,a.origin,budget)
if __name__=='__main__':main()
