"""Authoring-only independent original-source bank; no oracle/checker imports.

Uses direct TSV/JSON parsing, compensated cumulative frame areas, and centered,
scaled NumPy least squares rather than the oracle's centered-moment quotient.
Original source execution requires the parent-approved scientific/resource gate.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import tempfile
import numpy as np

PIPELINE='petdvr-fixed-window-reference-logan-v2'
MANIFEST_SHA='9ca371309a1a5b5e8ebbc80b5c40d1b766bff666774b9f243f6cc27ca1def6a6'
METHOD_SHA='f82719c34120a87a0a2143294a45e1f9db115a7f83afe40d0168e13e4dab3d69'
SCANS=[(s,e) for s in ('sub-01','sub-02') for e in ('ses-baseline','ses-rescan')]
TARGETS=['highbinding','left_thalamus','right_thalamus','left_caudate','right_caudate','left_putamen','right_putamen']
STARTS=[0,10,20,30,40]
ENDS=['native','common50']
FITKEY=('subject','session','target','end_policy','start_min')

def need(condition,message):
    if not condition:raise ValueError(message)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def finite(value):
    need(not isinstance(value,bool),'Boolean source numeric')
    value=float(value)
    need(math.isfinite(value),'Nonfinite source/arithmetic')
    return value

def avg(values):
    # Preserve the exact mathematical zero-variance case for decimal float64s.
    if len(values) and all(value==values[0] for value in values):return finite(values[0])
    return finite(math.fsum(values)/len(values))

def integral(values,durations_min):
    areas=[finite(c*d) for c,d in zip(values,durations_min)]
    return [finite(math.fsum(areas[:i])+.5*area) for i,area in enumerate(areas)]

def fit_line(x,y):
    out=dict(Sxx_min2=None,Sxy_min2=None,Syy_min2=None,rank_threshold_min2=None,logan_slope=None,
             intercept_min=None,sse_min2=None,rmse_min=None,r_squared=None,r_squared_status='fit_unavailable',
             fit_status='insufficient_frames')
    if not len(x):return out,[]
    x=np.asarray(x,dtype=np.float64);y=np.asarray(y,dtype=np.float64)
    need(np.isfinite(x).all() and np.isfinite(y).all(),'Nonfinite fit coordinates')
    xb,yb=avg(x),avg(y);dx=x-xb;dy=y-yb
    xx=finite(math.fsum(dx*dx));xy=finite(math.fsum(dx*dy));yy=finite(math.fsum(dy*dy))
    threshold=finite(1e-24*max(1.,math.fsum(x*x)))
    out.update(Sxx_min2=xx,Sxy_min2=xy,Syy_min2=yy,rank_threshold_min2=threshold)
    if len(x)<3:return out,[]
    if xx<=threshold:
        out['fit_status']='rank_deficient_under_public_rule';return out,[]
    # Public objective, independently solved after centering/scaling its columns.
    scale=math.sqrt(xx)
    design=np.column_stack((dx/scale,np.ones(len(x))))
    coef=np.linalg.lstsq(design,dy,rcond=None)[0]
    slope=finite(coef[0]/scale);intercept=finite(yb-slope*xb+coef[1])
    predicted=slope*dx+yb+coef[1]
    residual=predicted-y;sse=finite(math.fsum(residual*residual))
    out.update(fit_status='ok',logan_slope=slope,intercept_min=intercept,sse_min2=sse,
               rmse_min=math.sqrt(sse/len(x)),r_squared=finite(1-sse/yy) if yy>0 else None,
               r_squared_status='ok' if yy>0 else 'constant_y')
    return out,[float(value) for value in predicted]

def ratio_statistics(times,values):
    out=dict(ratio_mean=None,ratio_min=None,ratio_max=None,ratio_population_sd=None,ratio_cv=None,
             ratio_cv_status='no_valid_ratio',ratio_time_slope_per_min=None,ratio_trend_status='no_valid_ratio')
    if not values:return out
    mean=avg(values);sd=finite(math.sqrt(math.fsum((value-mean)**2 for value in values)/len(values)))
    out.update(ratio_mean=mean,ratio_min=min(values),ratio_max=max(values),ratio_population_sd=sd,
               ratio_cv=finite(sd/abs(mean)) if mean!=0 else None,ratio_cv_status='ok' if mean!=0 else 'zero_mean',
               ratio_trend_status='insufficient_distinct_times')
    if len(values)>=2:
        t=np.asarray(times);r=np.asarray(values);dt=t-avg(t);ss=finite(math.fsum(dt*dt))
        if ss>0:
            design=np.column_stack((dt/math.sqrt(ss),np.ones(len(dt))))
            coef=np.linalg.lstsq(design,r-mean,rcond=None)[0]
            out.update(ratio_time_slope_per_min=finite(coef[0]/math.sqrt(ss)),ratio_trend_status='ok')
    return out

def analyze_frames(frames):
    """Generic small-fixture compatible numerical engine, with fixed public windows."""
    tables={'source_frames.csv':frames,'graph_points.csv':[],'window_fits.csv':[],'fit_points.csv':[]}
    scans=sorted({(r['subject'],r['session']) for r in frames})
    for subject,session in scans:
        source=sorted((r for r in frames if (r['subject'],r['session'])==(subject,session)),key=lambda r:r['frame_index'])
        durations=[r['frame_duration_s']/60 for r in source]
        ref=[r['reference'] for r in source];ir=integral(ref,durations)
        for target in TARGETS:
            ct=[r[target] for r in source];it=integral(ct,durations);graphs=[]
            for i,row in enumerate(source):
                graph=dict(subject=subject,session=session,target=target,frame_index=row['frame_index'],
                           integral_target_bq_min_per_ml=it[i],integral_reference_bq_min_per_ml=ir[i],
                           x_min=finite(ir[i]/ct[i]) if ct[i]!=0 else None,y_min=finite(it[i]/ct[i]) if ct[i]!=0 else None,
                           graph_status='ok' if ct[i]!=0 else 'zero_target',
                           target_over_reference=finite(ct[i]/ref[i]) if ref[i]!=0 else None,
                           ratio_status='ok' if ref[i]!=0 else 'zero_reference',
                           reference_over_target=finite(ref[i]/ct[i]) if ct[i]!=0 else None)
                graphs.append(graph);tables['graph_points.csv'].append(graph)
            for policy in ENDS:
                end=source[-1]['frame_end_s'] if policy=='native' else 3000.
                for start in STARTS:
                    members=[i for i,row in enumerate(source) if row['frame_mid_s']>=60*start and row['frame_end_s']<=end]
                    eligible=[i for i in members if graphs[i]['graph_status']=='ok']
                    ratios=[i for i in members if graphs[i]['ratio_status']=='ok']
                    key=dict(subject=subject,session=session,target=target,end_policy=policy,start_min=start)
                    fit,predicted=fit_line([graphs[i]['x_min'] for i in eligible],[graphs[i]['y_min'] for i in eligible])
                    row=key|dict(requested_end_s=end,n_window=len(members),n_fit=len(eligible),n_ratio=len(ratios),
                        first_window_frame=source[members[0]]['frame_index'] if members else None,
                        last_window_frame=source[members[-1]]['frame_index'] if members else None,
                        first_fit_frame=source[eligible[0]]['frame_index'] if eligible else None,
                        last_fit_frame=source[eligible[-1]]['frame_index'] if eligible else None,
                        actual_window_start_s=source[members[0]]['frame_start_s'] if members else None,
                        actual_window_end_s=source[members[-1]]['frame_end_s'] if members else None,
                        actual_fit_first_mid_s=source[eligible[0]]['frame_mid_s'] if eligible else None,
                        actual_fit_last_mid_s=source[eligible[-1]]['frame_mid_s'] if eligible else None)|fit
                    row.update(ratio_statistics([source[i]['frame_mid_s']/60 for i in ratios],[graphs[i]['target_over_reference'] for i in ratios]))
                    tables['window_fits.csv'].append(row)
                    pmap=dict(zip(eligible,predicted))
                    for i in members:
                        valid=graphs[i]['graph_status']=='ok';used=valid and fit['fit_status']=='ok'
                        tables['fit_points.csv'].append(key|dict(frame_index=source[i]['frame_index'],graph_valid=valid,in_fit=used,
                            point_status='used' if used else ('zero_target' if not valid else 'fit_unavailable'),
                            predicted_y_min=pmap[i] if used else None,
                            residual_y_min=finite(pmap[i]-graphs[i]['y_min']) if used else None))
    return tables

def summaries(fits):
    indexed={tuple(row[k] for k in FITKEY):row for row in fits}
    subjects=sorted({row['subject'] for row in fits});pairs=[];groups=[]
    for subject in subjects:
        for target in TARGETS:
            for end in ENDS:
                for start in STARTS:
                    baseline=indexed[subject,'ses-baseline',target,end,start];rescan=indexed[subject,'ses-rescan',target,end,start]
                    valid=baseline['fit_status']==rescan['fit_status']=='ok'
                    pairs.append(dict(subject=subject,target=target,end_policy=end,start_min=start,
                        baseline_fit_status=baseline['fit_status'],rescan_fit_status=rescan['fit_status'],
                        baseline_slope=baseline['logan_slope'],rescan_slope=rescan['logan_slope'],
                        rescan_minus_baseline=finite(rescan['logan_slope']-baseline['logan_slope']) if valid else None,
                        pair_status='ok' if valid else 'incomplete_pair'))
    for target in TARGETS:
        for end in ENDS:
            for start in STARTS:
                selected=[r for r in fits if (r['target'],r['end_policy'],r['start_min'])==(target,end,start) and r['fit_status']=='ok']
                paired=[r for r in pairs if (r['target'],r['end_policy'],r['start_min'])==(target,end,start) and r['pair_status']=='ok']
                represented=sorted({r['subject'] for r in selected})
                groups.append(dict(target=target,end_policy=end,start_min=start,n_expected_scans=4,n_expected_subjects=2,
                    n_defined_scans=len(selected),defined_scans=sorted([[r['subject'],r['session']] for r in selected]),
                    n_represented_subjects=len(represented),represented_subjects=represented,
                    mean_logan_slope=avg([r['logan_slope'] for r in selected]) if selected else None,
                    n_defined_pairs=len(paired),defined_pair_subjects=sorted(r['subject'] for r in paired),
                    mean_rescan_minus_baseline=avg([r['rescan_minus_baseline'] for r in paired]) if paired else None))
    return dict(status='ok',task_id='PETDVR-001',pipeline_id=PIPELINE,n_scans=4,n_subjects=2,targets=TARGETS,
                start_min=STARTS,end_policies=ENDS,paired_changes=pairs,group_windows=groups)

def load_source(data_dir,method_path):
    data_dir=Path(data_dir);method_path=Path(method_path);manifest_path=data_dir/'source_manifest.json'
    need(not data_dir.is_symlink() and not manifest_path.is_symlink() and not method_path.is_symlink(),'Symlink input')
    need(sha(manifest_path)==MANIFEST_SHA and sha(method_path)==METHOD_SHA,'Frozen manifest/method checksum mismatch')
    manifest=json.loads(manifest_path.read_text());contract=json.loads(method_path.read_text())
    need(len(manifest['files'])==24,'Full original24 files required')
    hashes={};paths={}
    for entry in manifest['files']:
        name=entry['path'];relative=Path(name)
        need(not relative.is_absolute() and '..' not in relative.parts and name not in hashes,'Invalid original path')
        path=data_dir/relative
        need(path.is_file() and not any(p.is_symlink() for p in [path,*path.parents] if p!=data_dir.parent),'Missing/symlink original')
        need(path.stat().st_size==entry['size_bytes'] and sha(path)==entry['sha256'],'Original file checksum mismatch')
        hashes[name]=entry['sha256']
        if entry['role'] in ('tac','pet_metadata'):
            key=(entry['subject'],entry['session'],entry['role']);need(key not in paths,'Duplicate source role');paths[key]=path
    need({p.relative_to(data_dir).as_posix() for p in data_dir.rglob('*') if p.is_file()}==set(hashes)|{'source_manifest.json'},'Unexpected source files')
    frames=[];observations=[]
    for subject,session in SCANS:
        tac=paths[subject,session,'tac'];pet=paths[subject,session,'pet_metadata'];meta=json.loads(pet.read_text())
        need(meta['Units']=='Bq/mL' and meta['ScanStart']==meta['InjectionStart']==meta['ImageDecayCorrectionTime']==0 and meta['ImageDecayCorrected'] is True,'Source time/decay/unit precondition')
        with tac.open(newline='') as handle:
            reader=csv.DictReader(handle,delimiter='\t');columns=reader.fieldnames;raw=list(reader)
        need(columns and len(columns)==len(set(columns)) and set(['frame_start','frame_end','reference',*TARGETS])<=set(columns),'Source TAC columns')
        starts=[finite(v) for v in meta['FrameTimesStart']];durations=[finite(v) for v in meta['FrameDuration']]
        need(len(raw)==len(starts)==len(durations) and starts[0]==0,'Source frame support')
        for i,original in enumerate(raw):
            a,b=finite(original['frame_start']),finite(original['frame_end'])
            need(a==starts[i] and b==starts[i]+durations[i] and b>a,'Source frame-sidecar mismatch')
            need(i==0 or a==frames[-1]['frame_end_s'],'Source temporal gap')
            frames.append(dict(subject=subject,session=session,frame_index=i,frame_start_s=a,frame_end_s=b,
                frame_duration_s=b-a,frame_mid_s=(a+b)/2,**{name:finite(original[name]) for name in ['reference',*TARGETS]}))
        end=starts[-1]+durations[-1]
        observations.append(dict(subject=subject,session=session,tac_path=tac.relative_to(data_dir).as_posix(),
            pet_metadata_path=pet.relative_to(data_dir).as_posix(),n_frames=len(raw),tac_columns=columns,
            source_time_unit='s',analysis_time_unit='min',activity_unit='Bq/mL',
            activity_unit_evidence='raw_pet_sidecar_and_derivative_lineage_not_TAC_specific_sidecar',
            scan_start_s=meta['ScanStart'],injection_start_s=meta['InjectionStart'],image_decay_corrected=meta['ImageDecayCorrected'],
            image_decay_correction_time_s=meta['ImageDecayCorrectionTime'],native_end_s=end,
            common50_actual_end_s=max(a+d for a,d in zip(starts,durations) if a+d<=3000),first_frame_start_s=starts[0],frames_contiguous=True))
    metadata=dict(status='ok',task_id='PETDVR-001',pipeline_id=PIPELINE,source_manifest_sha256=MANIFEST_SHA,
        method_contract_sha256=METHOD_SHA,source_sha256=hashes,method_contract=contract,source_observed={'scans':observations},
        software_versions={'python':platform.python_version(),'numpy':np.__version__})
    return frames,metadata

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',default='/app/data/petdvr')
    parser.add_argument('--method-contract',default='/app/method_contract.json')
    parser.add_argument('--reference',type=Path,default=Path(__file__).with_name('reference.npz'))
    parser.add_argument('--output-dir',type=Path,action='append',required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();need(not args.report.exists(),'Report already exists; preserve evidence')
    frames,metadata=load_source(args.data_dir,args.method_contract)
    tables=analyze_frames(frames)
    payload=dict(pipeline_id=PIPELINE,provenance='independent-original-tsv-centered-scaled-lstsq',tables=tables,
                 summary=summaries(tables['window_fits.csv']),metadata=metadata)
    from proof_of_work import validate_output_directory,load_reference
    for output in args.output_dir:validate_output_directory(output,payload)
    with tempfile.NamedTemporaryFile(prefix='.petdvr-',suffix='.npz',dir=args.reference.parent,delete=False) as handle:
        temporary=Path(handle.name);np.savez_compressed(handle,reference_json=np.array(json.dumps(payload,allow_nan=False)))
    try:
        load_reference(temporary);temporary.replace(args.reference)
    finally:
        if temporary.exists():temporary.unlink()
    report=dict(status='ok',pipeline_id=PIPELINE,reference_sha256=sha(args.reference),reference_bytes=args.reference.stat().st_size,
                counts={name:len(rows) for name,rows in tables.items()},checked_outputs=[str(path) for path in args.output_dir])
    args.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
