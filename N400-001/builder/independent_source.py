"""Independent original SET/FDT reference path; never imports the solution.

Shares the documented source layout and FIR contract, but uses direct source
memory mapping, SciPy FIR/convolution, and separate epoch/support arithmetic.
Nothing reads source data at import. Full execution requires the authoring gate.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.io import loadmat
from scipy.signal import fftconvolve, firwin

PIPELINE = 'erpcore-n400-target-subset-v2'
MANIFEST_SHA256 = '09483405a6b48aec79d9e40c96409709a7e0c4e462cb0deb646551fe6cfb2616'
METHOD_SHA256 = '8771e08ea44ee3c973a9b57c32f7d0352078f50e89767334635b8e2c8f1a0dc1'
CHANNELS = ('FP1','F3','F7','FC3','C3','C5','P3','P7','P9','PO7','PO3','O1','Oz','Pz','CPz',
            'FP2','Fz','F4','F8','FC4','FCz','Cz','C4','C6','P4','P8','P10','PO8','PO4','O2',
            'HEOG_left','HEOG_right','VEOG_lower')
OFFSETS = np.arange(-51, 206)

def check(condition, message):
    if not condition:
        raise ValueError(message)

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def scalar(value):
    array = np.asarray(value)
    check(array.size == 1, 'Expected scalar source field')
    return array.reshape(-1)[0].item() if isinstance(array.reshape(-1)[0], np.generic) else array.reshape(-1)[0]

def integral(value):
    value = scalar(value)
    check(not isinstance(value, (bool, np.bool_)) and isinstance(value, (int, float)) and math.isfinite(value) and int(value) == value, 'Invalid source integer')
    return int(value)

def records(value):
    if isinstance(value, dict):
        return [value]
    return list(np.asarray(value, dtype=object).reshape(-1))

def event_type(value):
    value = scalar(value)
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode('utf-8')
    return str(integral(value))

def event_role(code):
    if code in ('211', '212'):
        return 'target', 'related'
    if code in ('221', '222'):
        return 'target', 'unrelated'
    if code in ('111', '112'):
        return 'prime', 'related'
    if code in ('121', '122'):
        return 'prime', 'unrelated'
    if code in ('201', '202'):
        return 'response', ''
    return ('boundary', '') if code in ('boundary', '-99') else ('other', '')

def duration(row):
    if 'duration' not in row:
        return None, 'absent'
    if row['duration'] is None or np.asarray(row['duration']).size == 0:
        return None, 'empty'
    value = scalar(row['duration'])
    check(not isinstance(value, (bool, np.bool_)) and isinstance(value, (float, int)), 'Malformed source duration')
    return (float(value), 'finite') if math.isfinite(value) else (None, 'nonfinite')

def source_support(subject, events, n_samples):
    ledger = []
    cuts = {0, n_samples}
    for index, original in enumerate(events):
        check(isinstance(original, dict), 'Unexpected source event record')
        code = event_type(original['type'])
        role, condition = event_role(code)
        latency = float(scalar(original['latency']))
        check(math.isfinite(latency), 'Nonfinite source latency')
        dur, dur_status = duration(original)
        cut, sample = None, None
        if role == 'boundary':
            cut = math.floor(latency)
            check(latency - cut == .5 and 0 <= cut <= n_samples, 'Ambiguous source boundary')
            cuts.add(cut)
        else:
            sample = int(np.rint(latency - 1))
        ledger.append(dict(subject=subject, event_index=index, event_type=code, latency_samples=latency,
                           duration_samples=dur, duration_status=dur_status, event_sample=sample,
                           boundary_cut_sample=cut, role=role, condition=condition, segment_id=None,
                           retained=False, drop_reason='not_target'))
    bounds = sorted(cuts)
    segments = [dict(subject=subject, segment_id=index, start_sample=start, end_sample_exclusive=end,
                     n_samples=end-start, filter_length=8449, pad_samples=min(8449, end-start)-1)
                for index, (start, end) in enumerate(zip(bounds[:-1], bounds[1:])) if start < end]
    target_samples = [row['event_sample'] for row in ledger if row['role'] == 'target']
    check(len(set(target_samples)) == len(target_samples), 'Duplicate rounded target samples')
    trials = []
    for row in ledger:
        sample = row['event_sample']
        if sample is not None:
            anchors = [s for s in segments if s['start_sample'] <= sample < s['end_sample_exclusive']]
            row['segment_id'] = anchors[0]['segment_id'] if anchors else None
        if row['role'] != 'target':
            continue
        start, end = sample - 51, sample + 206
        if start < 0 or end > n_samples:
            reason = 'out_of_data'
        elif not any(s['start_sample'] <= start and end <= s['end_sample_exclusive'] for s in segments):
            reason = 'boundary_crossing'
        else:
            reason = ''
        row['retained'], row['drop_reason'] = not reason, reason
        trials.append({k: row[k] for k in ('subject', 'event_index', 'event_type', 'event_sample', 'condition', 'segment_id')} |
                      dict(epoch_start_sample=start, epoch_end_sample_exclusive=end, status='dropped' if reason else 'retained',
                           drop_reason=reason, baseline_uv=None, window_raw_mean_uv=None, window_baseline_corrected_uv=None))
    return ledger, segments, trials

def coefficients():
    h = -firwin(8449, .05, fs=256, window='hamming', scale=True)
    h[4168:4281] += firwin(113, 33.75, fs=256, window='hamming', scale=True)
    return h

def filter_segments(raw, segments, kernel=None):
    raw = np.asarray(raw, dtype=np.float64)
    check(raw.ndim == 2 and raw.shape[0] == 3 and np.isfinite(raw).all(), 'Required CPz/P9/P10 data nonfinite or malformed')
    h = coefficients() if kernel is None else kernel
    out = np.empty(raw.shape[1], dtype=np.float64)
    # Rereference before the same linear filter, independently from MNE's path.
    referenced = raw[0] - (raw[1] + raw[2]) / 2
    for segment in segments:
        start, end, pad = segment['start_sample'], segment['end_sample_exclusive'], segment['pad_samples']
        values = np.pad(referenced[start:end], (pad, pad), mode='edge')
        convolved = fftconvolve(values, h, mode='full')
        out[start:end] = convolved[pad + 4224:pad + 4224 + end - start]
    check(np.isfinite(out).all(), 'Filtered signal nonfinite')
    return out

def measurements(subject, filtered, trials):
    check(np.asarray(filtered).ndim == 1 and np.isfinite(filtered).all(), 'Nonfinite/malformed filtered signal')
    epochs, event_indices = [], []
    for row in trials:
        if row['status'] != 'retained':
            continue
        epoch = filtered[row['event_sample'] + OFFSETS]
        baseline = float(epoch[:52].mean(dtype=np.float64))
        window = float(epoch[128:180].mean(dtype=np.float64))
        row.update(baseline_uv=baseline, window_raw_mean_uv=window, window_baseline_corrected_uv=window-baseline)
        epochs.append(epoch-baseline)
        event_indices.append(row['event_index'])
    epochs = np.asarray(epochs, dtype=np.float64)
    lookup = {event: idx for idx, event in enumerate(event_indices)}
    subject_row = {'subject': subject}
    curves = {}
    for condition in ('related', 'unrelated'):
        candidates = [row for row in trials if row['condition'] == condition]
        selected = [row for row in candidates if row['status'] == 'retained']
        check(selected, 'Subject missing retained condition')
        subject_row[f'n_{condition}_candidate'] = len(candidates)
        subject_row[f'n_{condition}_retained'] = len(selected)
        subject_row[f'n_{condition}_dropped'] = len(candidates)-len(selected)
        subject_row[f'{condition}_uv'] = float(np.mean([row['window_baseline_corrected_uv'] for row in selected], dtype=np.float64))
        curves[condition] = epochs[[lookup[row['event_index']] for row in selected]].mean(axis=0, dtype=np.float64)
    subject_row['n400_uv'] = subject_row['unrelated_uv']-subject_row['related_uv']
    curve_rows = [dict(subject=subject, sample_offset=int(offset), time_ms=float(offset*1000/256),
                       related_uv=float(curves['related'][i]), unrelated_uv=float(curves['unrelated'][i]),
                       difference_uv=float(curves['unrelated'][i]-curves['related'][i])) for i, offset in enumerate(OFFSETS)]
    return curve_rows, subject_row, epochs, np.asarray(event_indices, dtype=np.int64)

def summarize(tables):
    rows = tables['per_subject.csv']
    mean = lambda field: float(np.mean([row[field] for row in rows], dtype=np.float64))
    values = np.asarray([row['n400_uv'] for row in rows])
    return dict(status='ok', pipeline_id=PIPELINE, channel='CPz', contrast='unrelated minus related (target words)',
                n_subjects=len(rows), subject_ids=[row['subject'] for row in rows], window_ms=[300, 500],
                epoch_sample_offsets=[-51,205], baseline_sample_offsets=[-51,0], measurement_sample_offsets=[77,128],
                n400_difference_amplitude_uv=mean('n400_uv'), related_mean_amplitude_uv=mean('related_uv'),
                unrelated_mean_amplitude_uv=mean('unrelated_uv'), n_target_events=len(tables['trial_measurements.csv']),
                n_retained_target_epochs=sum(row['status']=='retained' for row in tables['trial_measurements.csv']),
                n_subjects_negative=int(np.sum(values<0)), n_subjects_zero=int(np.sum(values==0)), n_subjects_positive=int(np.sum(values>0)))

def load_inputs(data_dir, contract_path):
    data_dir, contract_path = Path(data_dir), Path(contract_path)
    manifest_path = data_dir/'data_manifest.json'
    check(not data_dir.is_symlink() and not manifest_path.is_symlink() and not contract_path.is_symlink(), 'Symlink source identity')
    check(digest(manifest_path) == MANIFEST_SHA256 and digest(contract_path) == METHOD_SHA256, 'Frozen source/method fingerprint mismatch')
    manifest = json.loads(manifest_path.read_text())
    contract = json.loads(contract_path.read_text())
    check(contract['pipeline_id'] == PIPELINE and contract['subjects'] == list(range(1,13)), 'Wrong public method')
    check(manifest['subjects'] == list(range(1,13)) and len(manifest['files']) == 24, 'Incomplete original source manifest')
    paths, hashes = {}, {}
    for row in manifest['files']:
        subject, role = row['subject'], row['role']
        name = row['path']
        check(subject in range(1,13) and role in ('set','fdt') and name == f'{subject}_N400_shifted_ds.{role}', 'Source manifest identity')
        check((subject,role) not in paths, 'Duplicate source pair')
        path = data_dir/name
        check(path.is_file() and not path.is_symlink(), 'Source file missing or symlink')
        check(path.stat().st_size == row['size_bytes'] and digest(path) == row['sha256'], 'Original source checksum mismatch')
        paths[subject,role], hashes[name] = path, row['sha256']
    check({path.name for path in data_dir.iterdir()} == set(hashes) | {'data_manifest.json'}, 'Unexpected file in frozen source directory')
    return dict(paths=paths, hashes=hashes, manifest_hash=digest(manifest_path), contract_hash=digest(contract_path), contract=contract)

def read_subject(inputs, subject):
    set_path, fdt_path = inputs['paths'][subject,'set'], inputs['paths'][subject,'fdt']
    fields = loadmat(set_path, simplify_cells=True)
    eeg = fields.get('EEG', fields)
    check(eeg['data'] == fdt_path.name and eeg['datfile'] == fdt_path.name, 'External FDT basename mismatch')
    n_samples, n_channels = integral(eeg['pnts']), integral(eeg['nbchan'])
    sfreq = float(scalar(eeg['srate']))
    check(n_samples>0 and n_channels==33 and sfreq==256 and integral(eeg['trials'])==1, 'Unexpected source sampling/layout')
    labels = [str(c['labels']) for c in records(eeg['chanlocs'])]
    check(tuple(labels)==CHANNELS, 'Source channel identity')
    indices = {name:labels.index(name) for name in ('CPz','P9','P10')}
    check(indices=={'CPz':14,'P9':8,'P10':26}, 'Unexpected readout channel layout')
    check(fdt_path.stat().st_size==4*n_channels*n_samples, 'FDT dimensions mismatch')
    raw = np.memmap(fdt_path, dtype='<f4', mode='r', shape=(n_channels,n_samples), order='F')
    selected = np.asarray(raw[list(indices.values())], dtype=np.float64)
    check(np.isfinite(selected).all(), 'Nonfinite original readout channels')
    events = records(eeg['event'])
    check(all(np.asarray(eeg.get(name,[])).size==0 for name in ('icaweights','icasphere','icawinv','icachansind')), 'Unexpected source ICA state')
    ledger, segments, trials = source_support(subject, events, n_samples)
    info = dict(subject=subject, set_path=set_path.name, fdt_path=fdt_path.name, sfreq_hz=sfreq,
                n_samples=n_samples,n_channels=n_channels,channel_labels=labels,readout_channel_indices=indices,
                header_reference=str(eeg['ref']),n_source_events=len(events),event_type_counts=dict(sorted(Counter(row['event_type'] for row in ledger).items())),
                n_boundary_events=sum(row['role']=='boundary' for row in ledger),n_segments=len(segments),
                n_target_candidates=len(trials),n_retained_target_epochs=sum(row['status']=='retained' for row in trials),
                n_dropped_out_of_data=sum(row['drop_reason']=='out_of_data' for row in trials),
                n_dropped_boundary_crossing=sum(row['drop_reason']=='boundary_crossing' for row in trials),
                duration_fields_present=any('duration' in row for row in events),
                ica_fields_empty=all(np.asarray(eeg.get(name,[])).size==0 for name in ('icaweights','icasphere','icawinv','icachansind')),
                history_sha256=hashlib.sha256(str(eeg.get('history','')).encode('utf-8')).hexdigest())
    return selected, ledger, segments, trials, info

def build_payload(inputs):
    tables = {name:[] for name in ('source_events.csv','segments.csv','trial_measurements.csv','curves.csv','per_subject.csv')}
    observations, arrays = [], {'filter_coefficients':coefficients()}
    for subject in range(1,13):
        raw, ledger, segments, trials, info = read_subject(inputs,subject)
        filtered = filter_segments(raw,segments,arrays['filter_coefficients'])
        curves, per_subject, epochs, event_indices = measurements(subject,filtered,trials)
        for name, rows in (('source_events.csv',ledger),('segments.csv',segments),('trial_measurements.csv',trials),('curves.csv',curves),('per_subject.csv',[per_subject])):
            tables[name].extend(rows)
        observations.append(info)
        arrays[f'retained_epochs_subject_{subject}'] = epochs
        arrays[f'retained_event_index_subject_{subject}'] = event_indices
    results = summarize(tables)
    metadata = dict(status='ok',task_id='N400-001',pipeline_id=PIPELINE,source_manifest_sha256=inputs['manifest_hash'],
                    method_contract_sha256=inputs['contract_hash'],source_sha256=inputs['hashes'],method_contract=inputs['contract'],
                    source_observed={'subjects':observations},software_versions={'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__})
    return dict(pipeline_id=PIPELINE,provenance='independent-original-set-fdt-scipy',tables=tables,results=results,metadata=metadata), arrays
