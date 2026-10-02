"""Offline fixed12 signed-lateralization oracle; no outcome-based acceptance.

MNE EEG reader and segmented FIR are the supplied implementation, not a claim
that numerical -99 handling reproduces the legacy unsegmented pipeline.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import platform

import numpy as np
import scipy
import mne

import core
import source_reader as source


def write_json(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def write_npz(path,arrays):
    with path.open('xb') as stream:np.savez_compressed(stream,**arrays)


def write_csv(path,columns,rows):
    with path.open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='raise');writer.writeheader()
        for row in rows:writer.writerow({k:('' if v is None else int(v) if type(v) is bool else v) for k,v in row.items()})


def validate_destinations(output_dir,private_dir,data_dir,method_path):
    output=source.safe_path(output_dir);private=source.safe_path(private_dir) if private_dir else None
    here=Path(__file__).resolve().parent
    code_root=here.parent if (here.parent/'task.toml').is_file() else here
    protected=[source.safe_path(data_dir),source.safe_path(method_path),code_root]
    destinations=[output]+([private] if private is not None else [])
    for destination in destinations:
        source.need(not os.path.lexists(destination) and destination.parent.is_dir(),'fresh_destination_with_existing_parent')
        for item in protected:
            source.need(destination!=item and destination not in item.parents and item not in destination.parents,'source_or_code_output_overlap')
    if private is not None:
        source.need(output!=private and output not in private.parents and private not in output.parents,'output_private_overlap')
    return output,private


def processing_observed(subject,trials,segments,contract):
    return dict(subject=subject,eeg_reference_channels=contract['filter']['eeg_reference_channels'],
                excluded_eog_channels=contract['filter']['excluded_eog_channels'],filter_segments=segments,fir_length=33793,
                epoch_offsets=[-205,461],baseline_offsets=[-204,0],measurement_offsets=[205,307],
                n_left_retained=sum(r['retained'] and r['target_field']=='left' for r in trials),
                n_right_retained=sum(r['retained'] and r['target_field']=='right' for r in trials),
                drop_reason_counts={k:sum(r['drop_reason']==k for r in trials) for k in ('out_of_data','boundary_crossing','bad_annotation')})


def combine_arrays(parts):
    return dict(subject=np.concatenate([p['subject'] for p in parts]),source_event_index=np.concatenate([p['source_event_index'] for p in parts]),
                channel_labels=np.array(['PO7','PO8']),sample_offsets=core.OFFSETS.copy(),epochs_uv=np.concatenate([p['epochs_uv'] for p in parts],axis=0))


def analyze(inputs,warning_records,private_dir=None,pilot_subject=None):
    subjects=[pilot_subject] if pilot_subject is not None else list(source.SUBJECTS)
    annotations=[];trials=[];parts=[];observed=[];processing=[]
    for subject in subjects:
        metadata=source.read_metadata(inputs,subject)
        ann,rows,segments,obs=core.annotate_and_select(metadata)
        eeg=source.load_mne_eeg(inputs,metadata,warning_records)
        pair=core.filter_reference(eeg,segments,inputs['contract'],subject,warning_records)
        del eeg
        arrays=core.extract_epochs(pair,rows)
        if private_dir is not None:
            write_npz(private_dir/f'subject_{subject:03d}.npz',dict(
                filtered_referenced_pair_uv=pair,filter_segments=np.asarray(segments,dtype=np.int64),
                **arrays))
        annotations.extend(ann);trials.extend(rows);parts.append(arrays);observed.append(obs)
        processing.append(processing_observed(subject,rows,segments,inputs['contract']))
    arrays=combine_arrays(parts)
    trials,people,waveforms,result=core.derive(trials,arrays,subjects,pilot=pilot_subject is not None)
    metadata=dict(status='resource_pilot' if pilot_subject is not None else 'ok',dataset_id='erp-core-n2pc-fixed12',
                  source_manifest_sha256=source.SOURCE_SHA256,method_contract_sha256=source.METHOD_SHA256,subjects=subjects,
                  source_files=[{k:r[k] for k in ('subject','role','path','object_id','version','size_bytes','sha256','md5')} for r in inputs['manifest']['files']],
                  source_observed=observed,processing_observed=processing,
                  software_versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,mne=mne.__version__),
                  implementation='Owned source authentication/metadata and event/epoch algebra; MNE EEG reader and per-segment Hamming FIR, explicit30-channel reference. Not legacy numeric-boundary equivalence.',
                  warnings=warning_records)
    if pilot_subject is not None:
        scope=dict(subjects_decoded=subjects,all24_originals_authenticated=True,complete_fixed12=False)
        result['resource_pilot_scope']=scope;metadata['resource_pilot_scope']=scope
    return dict(annotations=annotations,trials=trials,arrays=arrays,people=people,waveforms=waveforms,result=result,metadata=metadata)


def findings(result):
    value=result['n2pc_amplitude_uv'];fixed=result['fixed_po8_minus_po7_pooled_uv_for_reference']
    show=lambda x:'undefined' if x is None else f'{x:.9g} uV'
    return (f"# Signed N2pc method control\n\nStatus: {result['status']}. "
            f"The equal-field then equal-person signed200–300 ms contrast is {show(value)}; "
            f"the fixed PO8−PO7 comparator is {show(fixed)}. Retained support: "
            f"{result['n_left_target_trials_total']} left and {result['n_right_target_trials_total']} right, "
            f"with {result['n_dropped_target_events_total']} source-support drops.\n\n"
            "The numeric−99 discontinuity is explicitly segmented for filtering and crossing-epoch rejection. "
            "PO7/PO8 use the fixed30-electrode average reference; peripheral channels are excluded. "
            "The signed values are descriptive, without a required polarity or fixed-channel cancellation. "
            "This fixed-cohort raw-data adaptation is not the paper's cleaned35-person characterization. "
            "No ICA, ocular, amplitude or behavioral rejection is added. The microvolt calibration follows "
            "the declared EEGLAB/MNE convention, not an independent calibration measurement.\n")


def emit(output,analysis,contract):
    schema=contract['output_schema']
    for name,key in (('annotations.csv','annotations'),('trials.csv','trials'),('per_subject.csv','people'),('waveforms.csv','waveforms')):
        write_csv(output/name,list(schema[name]['required_columns']),analysis[key])
    write_npz(output/'response_epochs.npz',analysis['arrays'])
    write_json(output/'n2pc.json',analysis['result']);write_json(output/'run_metadata.json',analysis['metadata'])
    with (output/'findings.md').open('x',encoding='utf-8') as stream:stream.write(findings(analysis['result']))


def run(data_dir,method_path,output_dir,private_dir=None,pilot_subject=None):
    output,private=validate_destinations(output_dir,private_dir,data_dir,method_path)
    output.mkdir(mode=0o700)
    warnings=[];stage='create_private_evidence'
    try:
        if private is not None:private.mkdir(mode=0o700)
        stage='authenticate_all24_originals_and_method';inputs=source.load_inputs(data_dir,method_path)
        stage='source_metadata_signal_and_derivation';analysis=analyze(inputs,warnings,private,pilot_subject)
        stage='emit_public_eight_artifacts';emit(output,analysis,inputs['contract'])
        if private is not None:
            stage='emit_private_receipts'
            write_json(private/'analysis_receipt.json',dict(source_manifest_sha256=source.SOURCE_SHA256,method_contract_sha256=source.METHOD_SHA256,
                       status=analysis['result']['status'],n_epochs=len(analysis['arrays']['subject']),
                       source_observed=analysis['metadata']['source_observed'],processing_observed=analysis['metadata']['processing_observed'],warnings=warnings))
        return analysis['result']
    except BaseException as error:
        failure=dict(status='failed_precondition',stage=stage,reason=str(error),error_type=type(error).__name__,warnings=warnings)
        write_json(output/'failure_report.json',failure)
        for name in ('n2pc.json','run_metadata.json'):
            if not os.path.lexists(output/name):write_json(output/name,failure)
        if not os.path.lexists(output/'findings.md'):
            with (output/'findings.md').open('x',encoding='utf-8') as stream:stream.write('Run failed; see the authoritative failure_report.json. No successful result is claimed.\n')
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',default=os.environ.get('N2PC_DIR','/app/data/n2pc'))
    parser.add_argument('--method-contract',default='/app/method_contract.json')
    parser.add_argument('--output-dir',default=os.environ.get('OUTPUT_DIR','/app/output'))
    parser.add_argument('--private-dir')
    parser.add_argument('--pilot-subject',type=int,choices=[8])
    args=parser.parse_args(argv)
    try:
        result=run(args.data_dir,args.method_contract,args.output_dir,args.private_dir,args.pilot_subject)
        print(json.dumps({k:result[k] for k in ('status','n_subjects','n_target_events_total','n_dropped_target_events_total')}));return 0
    except BaseException as error:
        print(json.dumps(dict(status='failed_precondition',error_type=type(error).__name__)));return 1


if __name__=='__main__':raise SystemExit(main())
