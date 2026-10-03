"""Oracle artifact construction from authenticated sources, without private imports."""
import csv
import io
import json
import math
from pathlib import Path
import platform

import numpy as np
import scipy

import kinetics as k


def compute_person(person):
    ct=k.cortical_mean(person['cortical_values'])
    mid,it=k.tissue_integral(person['frame_starts_s'],person['frame_ends_s'],ct)
    inputs=[];integrals=[];defined=[];knots=None
    for assumption in k.ASSUMPTIONS:
        curve=k.parent_knots(person['time_s'],person['plasma'],person['parent_fraction'],assumption)
        knots=curve['times_min']*60;inputs.append(curve['values'])
        mask=mid<=curve['times_min'][-1]
        integral=np.zeros(len(mid));integral[mask]=k.input_integral(curve['times_min'],curve['values'],mid[mask])
        integrals.append(integral);defined.append(mask)
    ip=np.column_stack(integrals);support=np.column_stack(defined)
    models={}
    for arm,assumption in enumerate(k.ASSUMPTIONS):
        for estimator in k.ESTIMATORS:
            models[assumption,estimator]=k.fit_model(mid,ct,it,ip[:,arm] if support[mid>=30,arm].all() else None,estimator)
    return dict(tissue_concentration=ct,primitive=dict(midpoint_min=mid,tissue_integral=it,
        plasma_integral=ip,plasma_integral_defined=support,fit_mask=mid>=30,knot_time_s=knots,
        parent_input=np.column_stack(inputs)),models=models,
        knot_rows=([-1]+person['knot_rows'] if curve['inserted_zero_anchor'] else person['knot_rows']))


def summaries(subjects,models):
    groups=[];changes=[];paired=[]
    for assumption in k.ASSUMPTIONS:
        for estimator in k.ESTIMATORS:
            values=[models[s][assumption,estimator]['vt'] for s in subjects]
            groups.append(dict(assumption_id=assumption,estimator_id=estimator,**k.complete_summary(values)))
    for estimator in k.ESTIMATORS:
        values=[]
        for s in subjects:
            a=models[s][k.ASSUMPTIONS[0],estimator]['vt'];b=models[s][k.ASSUMPTIONS[1],estimator]['vt']
            value=None if a is None or b is None else b-a
            status='unavailable_pair' if value is None else 'ok'
            if value is not None and not math.isfinite(value):value=None;status='numerical_failure'
            values.append(value);changes.append(dict(subject_id=s,estimator_id=estimator,status=status,delta_vt=value))
        paired.append(dict(estimator_id=estimator,**k.complete_summary(values)))
    return dict(schema_version='petvt-summary-v2',status='complete',groups=groups,paired_changes=changes,paired_summaries=paired)


def artifacts(source):
    subjects=source['subject_ids']
    if source['status']!='complete' or len(subjects)!=7:raise ValueError('full seven-source output only')
    computed={s:compute_person(source['persons'][s]) for s in subjects}
    models={s:computed[s]['models'] for s in subjects}
    a=dict(subject_ids=np.array(subjects),assumption_ids=np.array(k.ASSUMPTIONS),estimator_ids=np.array(k.ESTIMATORS),
        cortical_column_ids=np.array(source['method']['source']['cortical_columns']))
    frame_fields={key:[] for key in ('frame_subject_ids','frame_indices','frame_start_s','frame_end_s','tissue_concentration',
        'tissue_integral','plasma_integral','plasma_integral_defined','fit_mask')}
    knot_fields={key:[] for key in ('knot_subject_ids','knot_source_rows','knot_time_s','parent_input')}
    a.update(coefficients=np.zeros((7,2,2,2)),coefficients_defined=np.zeros((7,2,2),dtype=bool),
        model_rank=np.full((7,2,2),-1,dtype=np.int64),model_column_scales=np.zeros((7,2,2,2)),
        model_singular_values=np.zeros((7,2,2,2)),model_diagnostics_defined=np.zeros((7,2,2),dtype=bool))
    rows=[]
    for s_index,s in enumerate(subjects):
        p=source['persons'][s];c=computed[s];pr=c['primitive'];n=len(p['frame_starts_s']);nk=len(c['knot_rows'])
        values=dict(frame_subject_ids=np.array([s]*n),frame_indices=np.arange(n),frame_start_s=p['frame_starts_s'],
            frame_end_s=p['frame_ends_s'],tissue_concentration=c['tissue_concentration'],
            **{key:pr[key] for key in ('tissue_integral','plasma_integral','plasma_integral_defined','fit_mask')})
        for key in frame_fields:frame_fields[key].append(values[key])
        for key,value in dict(knot_subject_ids=np.array([s]*nk),knot_source_rows=np.array(c['knot_rows']),
                             knot_time_s=pr['knot_time_s'],parent_input=pr['parent_input']).items():knot_fields[key].append(value)
        for arm,assumption in enumerate(k.ASSUMPTIONS):
            for e,estimator in enumerate(k.ESTIMATORS):
                result=c['models'][assumption,estimator];idx=(s_index,arm,e)
                if result['coefficients'] is not None:a['coefficients'][idx]=result['coefficients'];a['coefficients_defined'][idx]=True
                if result['rank'] is not None:a['model_rank'][idx]=result['rank']
                if result['column_scales'] is not None:
                    a['model_diagnostics_defined'][idx]=True;a['model_column_scales'][idx]=result['column_scales']
                    a['model_singular_values'][idx]=result['singular_values']
                coeff=result['coefficients']
                rows.append(dict(subject_id=s,assumption_id=assumption,estimator_id=estimator,status=result['status'],
                    n_fit_rows=result['n_fit_rows'],rank=result['rank'],coefficient_0=None if coeff is None else float(coeff[0]),
                    coefficient_1=None if coeff is None else float(coeff[1]),vt=result['vt'],nonpositive_vt=result['nonpositive_vt'],
                    residual_rss=result['residual_rss'],rss_status=result['rss_status']))
    for key,values in {**frame_fields,**knot_fields}.items():a[key]=np.concatenate(values,axis=0)
    summary=summaries(subjects,models)
    metadata=dict(schema_version='petvt-metadata-v2',task_id='PETVT-001',status='complete',**source['pins'],
        source_files=source['source_files'],source_observed=source['source_observed'],warnings=[],
        software=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__))
    findings=['# Two blood-reference assumptions','',
        'These are conditional methods-sensitivity estimates, not a determination of the blood decay reference or a biological replication.',
        'The tissue target is an equal-region cortical composite. Both branches use identical frame support and explicit input representation.',
        'Already-image-reference uses P*f; sample-time-reference uses P*f*exp(log(2)*(t-d)/6586.2). Neither assumption is established as true.','']
    for row in summary['groups']:
        findings.append(f"{row['assumption_id']} / {row['estimator_id']}: {row['n_defined']}/7 defined; status={row['status']}; mean={row['mean']}; sample SD={row['sample_sd']}.")
    findings.extend(['','Paired changes are sample-time-reference minus already-image-reference; incomplete families remain unavailable. No fitted-value sign/range or direction was required.'])
    return dict(rows=rows,arrays=a,summary=summary,metadata=metadata,findings='\n'.join(findings)+'\n')


def write(output,actual):
    output=Path(output)
    if not output.is_dir() or any(output.iterdir()):raise ValueError('fresh empty output required')
    columns=['subject_id','assumption_id','estimator_id','status','n_fit_rows','rank','coefficient_0','coefficient_1','vt','nonpositive_vt','residual_rss','rss_status']
    with (output/'vt_estimates.csv').open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        for row in actual['rows']:
            writer.writerow({k:('' if row[k] is None else str(row[k]).lower() if type(row[k])is bool else row[k])for k in columns})
    with (output/'kinetic_evidence.npz').open('xb') as stream:np.savez_compressed(stream,**actual['arrays'])
    for filename,key in (('sensitivity_summary.json','summary'),('run_metadata.json','metadata')):
        with (output/filename).open('x',encoding='utf-8') as stream:json.dump(actual[key],stream,indent=2,allow_nan=False);stream.write('\n')
    with (output/'findings.md').open('x',encoding='utf-8') as stream:stream.write(actual['findings'])
