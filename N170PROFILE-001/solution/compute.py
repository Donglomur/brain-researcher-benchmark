"""Original-source N170 oracle; no import-time data reads or numerical bank."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat

import numpy as np

import measurement_kernel as mk
import oracle_source

SUBJECTS = tuple(str(i) for i in range(1,41) if i not in (1,5,16))
ANNOTATIONS = ('subject_id','source_event_index','type_json','latency_json','duration_json',
               'urevent_json','normalized_event_code','event_role')
TRIALS = ('subject_id','source_event_index','condition','event_sample','epoch_first_sample',
          'epoch_last_sample','epoch_status','accepted','rejection_reason')
PERSONS = ('subject_id','n_face_candidates','n_car_candidates','n_face_accepted','n_car_accepted',
           'n_face_rejected','n_car_rejected','waveform_status','amp_po8_uv','amplitude_status',
           'onset_ms','onset_status','measurement_baseline_uv','peak_selection','peak_sample_offset',
           'peak_time_ms','peak_uv','half_height_uv','crossing_sample_offset')
KERNEL_SHA = 'bc12162f1496b3f4b83419748ee33905a050331cc815ea7d7a9788e6a6fbba9e'


def need(ok, why):
    if not ok: raise ValueError(why)


def plain(value):
    if isinstance(value, np.ndarray): return [plain(v) for v in value.tolist()]
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, dict): return {k:plain(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [plain(v) for v in value]
    return value


def warning_strings(records):
    """Keep textual warnings and losslessly encode structured source warnings."""
    need(isinstance(records,list), 'warning_records_list')
    return [record if isinstance(record,str) else json.dumps(
        plain(record),sort_keys=True,ensure_ascii=False,allow_nan=False,
        separators=(',',':')) for record in records]


def group(values):
    result = mk.aggregate_complete(values)
    result['missing_subject_ids'] = [SUBJECTS[i] for i in result.pop('missing_indices')]
    return result


def compose(source):
    """Serialize this route's full37 evidence; the grader never imports this."""
    need(source['status']=='complete' and source['subjects']==list(SUBJECTS), 'full37_source_required')
    need(source['condition_labels']==['face','car'], 'condition_order')
    offsets = np.asarray(source['sample_offsets'])
    need(np.array_equal(offsets,np.arange(-51,103)), 'sample_grid')
    times = offsets.astype(np.float64) * (1000.0/256.0)
    waves = np.asarray(source['evoked_po8_uv'],dtype=np.float64)
    flags = np.asarray(source['condition_defined'])
    need(waves.shape==(37,2,154) and np.isfinite(waves).all(), 'waveforms')
    need(flags.shape==(37,2) and flags.dtype.kind=='b', 'condition_flags')
    rows=[]; measurements=[]
    for i,subject in enumerate(SUBJECTS):
        subset=[row for row in source['trials'] if row['subject_id']==subject]
        counts={}
        for condition in ('face','car'):
            candidates=[row for row in subset if row['condition']==condition]
            count=sum(bool(row['accepted']) for row in candidates)
            counts.update({f'n_{condition}_candidates':len(candidates),
                f'n_{condition}_accepted':count, f'n_{condition}_rejected':len(candidates)-count})
            need(bool(flags[i,0 if condition=='face' else 1])==(count>0), 'condition_count_support')
        for j in range(2):
            if not flags[i,j]: need(np.all(waves[i,j]==0), 'missing_zero_sentinel')
        if bool(flags[i].all()):
            face=np.ascontiguousarray(waves[i,0]); car=np.ascontiguousarray(waves[i,1])
            difference=face-car
            rebased=difference-np.mean(difference[:52],dtype=np.float64)
            limit=64*np.finfo(np.float64).eps*max(1.,float(np.max(np.abs(face))),float(np.max(np.abs(car))))
            supported=bool(np.max(np.abs(rebased))>limit)
            measurement=mk.measure_waveform(times,difference,onset_supported=supported)
            waveform_status='ok'
        else:
            measurement=mk.measure_waveform(times,None)
            waveform_status='missing_condition'
        measurements.append(measurement)
        def sample(index): return None if index is None else int(offsets[index])
        rows.append(dict(subject_id=subject,**counts,waveform_status=waveform_status,
            amp_po8_uv=measurement['amplitude_uv'],amplitude_status=measurement['amplitude_status'],
            onset_ms=measurement['onset_ms'],onset_status=measurement['onset_status'],
            measurement_baseline_uv=measurement['measurement_baseline_uv'],
            peak_selection=measurement['peak_selection'],peak_sample_offset=sample(measurement['peak_index']),
            peak_time_ms=measurement['peak_time_ms'],peak_uv=measurement['peak_uv'],
            half_height_uv=measurement['half_height_uv'],crossing_sample_offset=sample(measurement['crossing_index'])))
    amplitude=group([m['amplitude_uv'] for m in measurements])
    onset=group([m['onset_ms'] for m in measurements])
    result=dict(schema_version='n170-output-v1',n_subjects=37,electrode='PO8',
        amp_po8_uv=amplitude['mean'],amp_po8_ci95=amplitude['ci95'],
        onset_latency_ms=onset['mean'],onset_ci95=onset['ci95'],
        amplitude_summary=amplitude,onset_summary=onset)
    metadata=dict(schema_version='n170-output-v1',task_id='N170PROFILE-001',status='complete',
        **source['pins'],measurement_kernel_sha256=KERNEL_SHA,cohort=list(SUBJECTS),
        source_files=source['source_files'],source_observed=source['source_observed'],
        analysis_observed=source['analysis_observed'],
        software_versions={name:importlib.metadata.version(name) for name in ('numpy','scipy','mne')},
        warnings=warning_strings(source.get('warnings',[])),
        interpretation='paper-derived shifted_ds adaptation, not full paper or exact historical software reproduction')
    keys=source['epoch_keys']
    arrays=dict(subject_ids=np.asarray(SUBJECTS),condition_labels=np.asarray(['face','car']),
        sample_offsets=offsets,condition_defined=flags,evoked_po8_uv=waves,
        rejection_channel_labels=np.asarray(source['rejection_channel_labels']),
        epoch_subject_ids=np.asarray([s for s,_ in keys],dtype='U2'),
        epoch_source_event_index=np.asarray([index for _,index in keys],dtype=np.int64),
        epoch_peak_to_peak_uv=source['epoch_peak_to_peak_uv'],
        epoch_po8_baseline_uv=source['epoch_po8_baseline_uv'])
    findings=['# ERP CORE N170 processing adaptation','',
        'All 37 specified participants remain in the analysis. These are signed PO8 face-minus-car measurements.',
        'The independent unit for group summaries is the participant.']
    for name,summary,unit in [('Mean amplitude (110–150 ms)',amplitude,'µV'),('Fractional-peak latency',onset,'ms')]:
        if summary['mean'] is None:
            findings.append(f'{name}: complete-cohort estimate unavailable; {summary["n_defined"]}/37 defined, missing IDs {summary["missing_subject_ids"]}.')
        else:
            findings.append(f'{name}: {summary["mean"]:.6f} {unit}, 95% interval [{summary["ci95"][0]:.6f}, {summary["ci95"][1]:.6f}].')
    findings.extend(['','This uses a30-scalp-channel reference, .1–30Hz FIR, no ICA and no additional onset lowpass.',
        'It is not the complete paper pipeline or an exact reproduction of its published numbers.',
        'The fractional-peak descriptor does not establish a precise physiological onset. No cluster analysis was performed.'])
    return dict(annotations=source['annotations'],trials=source['trials'],persons=rows,arrays=arrays,
                result=result,metadata=metadata,findings='\n'.join(findings)+'\n')


def safe_output(value):
    path=Path(value)
    need(path.is_absolute() and not any(p in ('.','..') for p in os.fspath(value).split('/')), 'absolute_output_required')
    for parent in (*reversed(path.parents),path):
        if os.path.lexists(parent):
            mode=parent.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'symlink_output')
            need(stat.S_ISDIR(mode), 'output_directory')
    if not path.exists(): path.mkdir(parents=True)
    return path


def protect_output(value,data_dir,documents):
    """Check protected inputs before output creation or failure-marker eligibility."""
    output=Path(value).resolve()
    for protected in (Path(data_dir).resolve(),Path(__file__).resolve().parent):
        need(output!=protected and output not in protected.parents
             and protected not in output.parents, 'output_protected_directory_overlap')
    for document in documents:
        protected=Path(document).resolve()
        need(output!=protected and output not in protected.parents,
             'output_contains_protected_document')


def write_json(path,value):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(plain(value),stream,indent=2,allow_nan=False);stream.write('\n')


def csv_file(path,columns,rows):
    with path.open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore')
        writer.writeheader()
        for row in rows: writer.writerow({key:plain(row.get(key)) for key in columns})


def write_bundle(output,bundle):
    csv_file(output/'annotations.csv',ANNOTATIONS,bundle['annotations'])
    csv_file(output/'trials.csv',TRIALS,bundle['trials'])
    csv_file(output/'per_subject.csv',PERSONS,bundle['persons'])
    with (output/'erp_evidence.npz').open('xb') as stream:
        np.savez_compressed(stream,**bundle['arrays'])
    write_json(output/'n170.json',bundle['result'])
    write_json(output/'run_metadata.json',bundle['metadata'])
    with (output/'findings.md').open('x',encoding='utf-8') as stream:stream.write(bundle['findings'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',default=os.environ.get('DATA_DIR','/app/data/n170profile'))
    parser.add_argument('--manifest',default='/app/source_manifest.json')
    parser.add_argument('--method',default='/app/method_contract.json')
    parser.add_argument('--schema',default='/app/output_schema.json')
    parser.add_argument('--output-dir',default=os.environ.get('OUTPUT_DIR','/app/output'))
    args=parser.parse_args(argv); output=None
    try:
        protect_output(args.output_dir,args.data_dir,(args.manifest,args.method,args.schema))
        output=safe_output(args.output_dir)
        need(not any(output.iterdir()), 'fresh_empty_output_required')
        need(hashlib.sha256(Path(mk.__file__).read_bytes()).hexdigest()==KERNEL_SHA, 'measurement_kernel_identity')
        source=oracle_source.reconstruct(args.data_dir,args.manifest,args.method,args.schema)
        write_bundle(output,compose(source))
        print(json.dumps(dict(status='complete',n_subjects=37,output_dir=str(output))))
        return 0
    except Exception as exc:
        if output is not None and not os.path.lexists(output/'failure_report.json'):
            write_json(output/'failure_report.json',dict(status='failed_precondition',reason=str(exc),error_type=type(exc).__name__))
        print(json.dumps(dict(status='failed',error_type=type(exc).__name__,reason=str(exc))))
        return 1


if __name__=='__main__':raise SystemExit(main())
