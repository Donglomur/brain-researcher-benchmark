"""Full scientific roster and phase support; no data decoding."""
import math
from common import need,TASK
ROLES=('A','B','operator')
REFERENCE_NAMES=('dmd','persistence','diagonal_ar')
PURPOSES=('native','forecast')

def validate_cohort(cohort):
    need(cohort['task_id']==TASK and cohort['source_revision']=='2c15edf4e770165fc3962dcc3920c8bcaf555bed' and len(cohort['sessions'])==29,'exact original29 cohort')
    rows=cohort['sessions'];need(len({r['session_id'] for r in rows})==29 and [r['session_id'] for r in rows]==cohort['fig2_order'],'unique ordered all29')
    need(sum(r['modality']=='calcium' for r in rows)==26 and sum(r['modality']=='ephys' for r in rows)==3,'26 calcium plus3 ephys');return rows

def partition(n,t):
    need(type(n)is int and n>0 and type(t)is int and t>=2000,'full finite observed geometry');d=4*t//5;v=3*t//5;need(d>10 and t-5>d,'all source-supported development/query pairs')
    return {'neurons':n,'frames':t,'development_end':d,'suggested_inner_end':v,'horizon':5,'fit_pair_start':0,'fit_pair_stop':d-5,'query_start':d,'query_stop':t-5,'queries':t-5-d,'target_stop':t,'future_targets_in_query_batch':False,'inner_guidance_preprocessing_disjoint':False}

def phases(sessions):
    out=[]
    for s in sessions:
        for kind in ('native','fit','stream'):
            for role in ROLES:
                out.append({'index':len(out),'id':f'{len(out):03d}-{kind}-{role}-{s["session_id"]}','session_id':s['session_id'],'kind':kind,'role':role,'purpose':'native' if kind=='native' else 'forecast'})
    need(len(out)==261,'all261 scientific producer phases');return out

def native_shape_support(g,s):
    need(g['n_fig2']==g['n_fig3'] and min(g['ntrain_fig2'],g['ntest_fig2'],g['n_fig2'])>=500,'no fabricated500ranks');need(min(g['ntrain_fig3'],g['ntest_fig3'])>=s['pc_rows'],'all original plottedPCs');need(g['dmd_modes']==min(1000,g['n_fig3']),'all sourceDMDmodes')

def resource_components(geometries,model_cap):
    need(type(model_cap)is int and model_cap>0,'explicit sealed model cap');parts=[partition(g['n_fig3'],g['t_fig3']) for g in geometries]
    full=sum(8*p['neurons']*p['frames'] for p in parts);dev=sum(8*p['neurons']*p['development_end'] for p in parts);pred=5*sum(8*p['neurons']*p['queries'] for p in parts)
    return {'full_standardized_numeric_bytes':full,'development_numeric_bytes':dev,'five_method_prediction_numeric_bytes':pred,'model_capture_ceiling_bytes':87*model_cap,'native_json_capture_ceiling_bytes':87*67108864,'lower_component_only':True,'physical_RSS_or_wall_measured':False,'future_staging_headers_source_arrays_journals_copies_and_native_dense_workspaces_additional':True}

def group_mean(session_values,sessions):
    need(set(session_values)=={s['session_id'] for s in sessions},'all29 metric values');groups={}
    for s in sessions:
        v=session_values[s['session_id']];need(type(v)in(int,float) and math.isfinite(v),'defined full metric');groups.setdefault(s['mouse_label'],[]).append(v)
    need(len(groups)==28,'source-label grouping stays28');g={k:math.fsum(v)/len(v) for k,v in groups.items()};return {'value':math.fsum(g.values())/len(g),'source_label_groups':g,'independent_animals_verified':False}

def strata_means(session_values,sessions):
    """Descriptive full-support strata; no cross-stratum composite or new endpoint."""
    group_mean(session_values,sessions)  # Refuse missing/undefined global support first.
    result={}
    for field in ('modality','region'):
        strata={}
        for s in sessions:strata.setdefault(s[field],[]).append(s)
        result[field]={}
        for name,rows in sorted(strata.items()):
            grouped={}
            for s in rows:grouped.setdefault(s['mouse_label'],[]).append(session_values[s['session_id']])
            values={label:math.fsum(v)/len(v) for label,v in grouped.items()}
            result[field][name]={'value':math.fsum(values.values())/len(values),'session_ids':[s['session_id'] for s in rows],'source_label_groups':values,'source_label_count':len(values),'session_count':len(rows),'descriptive_only':True}
    return result
