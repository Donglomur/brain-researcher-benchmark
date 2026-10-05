"""Source-bound, single-person response-locked FCz method control.

Import-safe: no source read or computation occurs until main/run.
The public method fixes a signed descriptive contrast, not its direction.
"""
import argparse
from contextlib import contextmanager
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import stat
import sys
import warnings

import numpy as np

METHOD_SHA256 = 'e5725d66b28fdb429315721693dd740bc66cbf1cc3d6b92a2689e8a03e26fd1a'
SOURCE_SHA256 = '31b2d095d29abb0236d2439b67c1a7fc7c301c2562ee46de74f399934095df60'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink path or ancestor refused')
    return path.resolve(strict=False)


def regular(path):
    path = safe_path(path)
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode), 'Regular file required: ' + path.name)
    return path


def prepare_output(source_dir, output_dir, method_path):
    source, output, method = map(safe_path, (source_dir, output_dir, method_path))
    require(source != output and source not in output.parents and output not in source.parents,
            'Source and output directories must be disjoint')
    require(output != method and output not in method.parents, 'Output cannot contain method input')
    if output.exists():
        require(output.is_dir() and not any(output.iterdir()), 'Refuse existing output evidence')
    else:
        output.mkdir(parents=True, exist_ok=False)
    return output


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def source_helper_path(task_helper=None, runtime_helper=Path('/opt/source/stage_data.py')):
    task_helper = task_helper or Path(__file__).resolve().parents[1] / 'environment' / 'stage_data.py'
    path = next((p for p in (Path(task_helper), Path(runtime_helper)) if p.exists()), None)
    require(path is not None, 'Offline source verifier missing')
    return regular(path)


def load_inputs(data_dir, method_path):
    method_path = regular(method_path)
    require(method_path.stat().st_size <= 100_000, 'Public method file too large')
    method_bytes = method_path.read_bytes()
    require(hashlib.sha256(method_bytes).hexdigest() == METHOD_SHA256, 'Public method SHA256 mismatch')
    method = json.loads(method_bytes)
    spec = importlib.util.spec_from_file_location('errmon_source_integrity', source_helper_path())
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    manifest = helper.verify_staged(data_dir)
    data_dir = safe_path(data_dir)
    raw_manifest = regular(data_dir / 'source_manifest.json').read_bytes()
    require(hashlib.sha256(raw_manifest).hexdigest() == SOURCE_SHA256 == method['source_manifest_sha256'],
            'Source manifest identity mismatch')
    source_file = next(e for e in manifest['files'] if e['role'] == 'raw_fif')
    require(source_file['path'] == method['input']['filename'], 'FIF source filename mismatch')
    return dict(method=method, manifest=manifest, fif_path=data_dir / source_file['path'],
                source_fif_sha256=source_file['sha256'])


@contextmanager
def recorded_warnings(messages):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:
            yield
        finally:
            for warning in caught:
                messages.append(warning.category.__name__ + ': ' + str(warning.message))
                sys.stderr.write(warnings.formatwarning(warning.message, warning.category,
                                                       warning.filename, warning.lineno))


def validate_header(raw, method):
    expected = method['input']
    require(float(raw.info['sfreq']) == expected['sfreq_hz'], 'Source sampling frequency mismatch')
    require(raw.n_times == expected['n_samples'] and raw.first_samp == expected['first_sample'],
            'Source sample-axis mismatch')
    require(raw.ch_names == expected['eeg_channels'] + expected['eog_channels'],
            'Exact source channel names/order required')
    require(raw.get_channel_types() == ['eeg'] * 30 + ['eog'] * 3, 'Source EEG/EOG types mismatch')
    require(not raw.info['bads'] and not raw.info['projs'], 'Unexpected bad channels or projectors')
    require(int(raw.info['custom_ref_applied']) == 1, 'Unexpected released reference flag')
    require(raw.info['meas_date'] is None, 'Unexpected recording time origin')
    require(raw.annotations.orig_time is None, 'Unexpected annotation origin')
    for channel in raw.info['chs']:
        require(channel['unit'] == 107 and channel['unit_mul'] == 0 and channel['range'] == 1.0 and
                channel['cal'] == 9.999999974752427e-7, 'Stored voltage calibration mismatch')


def annotation_ledger(raw, method):
    annotations = raw.annotations
    require(np.isfinite(annotations.onset).all() and np.isfinite(annotations.duration).all(),
            'Nonfinite annotation time')
    samples = raw.time_as_index(annotations.onset, use_rounding=True, origin=annotations.orig_time)
    if annotations.orig_time is not None:
        samples += raw.first_samp
    rows, mapped_samples = [], []
    mapping = method['events']['description_to_role']
    for i, (onset, duration, description, sample) in enumerate(zip(
            annotations.onset, annotations.duration, annotations.description, samples)):
        require(np.isfinite(onset) and np.isfinite(duration), 'Nonfinite annotation time')
        require(duration == 0, 'Nonzero annotation duration')
        require(0 <= onset < raw.n_times / raw.info['sfreq'] and 0 <= sample < raw.n_times,
                'Annotation outside the recording')
        require(not str(description).lower().startswith(('bad', 'edge')), 'Unexpected boundary/BAD annotation')
        role = mapping.get(str(description), 'unmapped')
        if role != 'unmapped':
            mapped_samples.append(int(sample))
        rows.append(dict(annotation_index=i, onset_s=float(onset), duration_s=float(duration),
                         description=str(description), event_sample=int(sample), event_role=role,
                         paired_stimulus_annotation_index=None,
                         disposition='orphan_response' if role.startswith('response_') else 'unmapped'))
    require(len(mapped_samples) == len(set(mapped_samples)), 'Mapped annotation sample tie')
    return rows


def pair_trials(annotations, n_samples, sfreq):
    stimuli = sorted((r for r in annotations if r['event_role'].startswith('stimulus_')),
                     key=lambda r: r['event_sample'])
    responses = sorted((r for r in annotations if r['event_role'].startswith('response_')),
                       key=lambda r: r['event_sample'])
    trials = []
    for j, stimulus in enumerate(stimuli):
        stop = stimuli[j + 1]['event_sample'] if j + 1 < len(stimuli) else n_samples
        candidates = [r for r in responses if stimulus['event_sample'] < r['event_sample'] < stop]
        _, compatibility, target = stimulus['event_role'].split('_')
        trial = dict(stimulus_annotation_index=stimulus['annotation_index'], stimulus_sample=stimulus['event_sample'],
                     response_annotation_index=None, response_sample=None, target_hand=target, response_hand=None,
                     compatibility=compatibility, is_error=None, rt_s=None, pair_status='unanswered',
                     epoch_status='unpaired', baseline_mean_uv=None, window_mean_prebaseline_uv=None, window_mean_uv=None)
        stimulus['disposition'] = 'unanswered_stimulus'
        if candidates:
            response = candidates[0]
            hand = response['event_role'].split('_')[-1]
            trial.update(response_annotation_index=response['annotation_index'], response_sample=response['event_sample'],
                         response_hand=hand, is_error=int(hand != target),
                         rt_s=(response['event_sample'] - stimulus['event_sample']) / sfreq, pair_status='paired')
            stimulus['disposition'] = 'paired_stimulus'
            response['disposition'] = 'paired_response'
            for event in (stimulus, response):
                event['paired_stimulus_annotation_index'] = stimulus['annotation_index']
            for extra in candidates[1:]:
                extra['disposition'] = 'extra_response'
        trials.append(trial)
    return trials


def filter_fcz(raw, method):
    eeg = raw.copy().pick(method['input']['eeg_channels']).load_data()
    data = eeg.get_data()
    require(data.dtype == np.float64 and np.isfinite(data).all(), 'Nonfinite or non-float64 calibrated EEG')
    eeg.filter(l_freq=0.1, h_freq=30.0, picks='all', filter_length=33793,
               l_trans_bandwidth=0.1, h_trans_bandwidth=7.5, n_jobs=1,
               method='fir', phase='zero', fir_window='hamming', fir_design='firwin',
               skip_by_annotation=(), pad='reflect_limited', verbose=False)
    filtered = eeg.get_data()
    require(np.isfinite(filtered).all(), 'Nonfinite filtered EEG')
    fcz = (filtered[eeg.ch_names.index('FCz')] - np.mean(filtered, axis=0, dtype=np.float64)) * 1e6
    require(np.isfinite(fcz).all(), 'Nonfinite average-referenced FCz')
    return fcz


def epoch_measurements(fcz_uv, trials, method):
    settings = method['processing']
    start, end = settings['sample_offset_inclusive']
    offsets = np.arange(start, end + 1, dtype=np.int64)
    times = offsets / float(method['input']['sfreq_hz'])
    baseline = (times >= settings['baseline_seconds_inclusive'][0]) & (times <= settings['baseline_seconds_inclusive'][1])
    window = (times >= settings['measurement_seconds_inclusive'][0]) & (times <= settings['measurement_seconds_inclusive'][1])
    require(len(offsets) == settings['epoch_samples'] and baseline.sum() == settings['baseline_samples']
            and window.sum() == settings['measurement_samples'], 'Public sample-window mismatch')
    require(np.array_equal(offsets[baseline][[0, -1]], settings['baseline_offsets_inclusive']) and
            np.array_equal(offsets[window][[0, -1]], settings['measurement_offsets_inclusive']),
            'Public window endpoint mismatch')
    keys, epochs, errors = [], [], []
    for trial in trials:
        if trial['pair_status'] != 'paired':
            continue
        sample = trial['response_sample']
        if sample + start < 0 or sample + end >= len(fcz_uv):
            trial['epoch_status'] = 'outside_record'
            continue
        epoch = np.asarray(fcz_uv[sample + offsets], dtype=np.float64)
        require(np.isfinite(epoch).all(), 'Nonfinite source epoch')
        b = float(np.mean(epoch[baseline], dtype=np.float64))
        trial.update(epoch_status='retained', baseline_mean_uv=b,
                     window_mean_prebaseline_uv=float(np.mean(epoch[window], dtype=np.float64)),
                     window_mean_uv=float(np.mean(epoch[window] - b, dtype=np.float64)))
        keys.append(trial['stimulus_annotation_index'])
        epochs.append(epoch)
        errors.append(trial['is_error'])
    prebaseline = np.asarray(epochs, dtype=np.float64).reshape(len(epochs), len(offsets))
    errors = np.asarray(errors, dtype=np.int64)
    corrected = prebaseline - np.mean(prebaseline[:, baseline], axis=1, keepdims=True) if len(epochs) else prebaseline.copy()
    curves, means = {}, {}
    for name, code in (('error', 1), ('correct', 0)):
        selected = corrected[errors == code]
        curves[name] = np.mean(selected, axis=0) if len(selected) else None
        means[name] = float(np.mean(selected[:, window], dtype=np.float64)) if len(selected) else None
    defined = curves['error'] is not None and curves['correct'] is not None
    curves['difference'] = curves['error'] - curves['correct'] if defined else None
    return dict(stimulus_annotation_index=np.asarray(keys, dtype=np.int64), sample_offset=offsets,
                fcz_prebaseline_uv=prebaseline, errors=errors, curves=curves, means=means,
                status='ok' if defined else 'insufficient_condition',
                difference=means['error'] - means['correct'] if defined else None)


def summarize(method, annotations, trials, measured):
    return dict(status=measured['status'], subject=method['subject'], electrode='FCz', units='microvolt',
                contrast='error-minus-correct', n_annotations=len(annotations), n_stimuli=len(trials),
                n_paired_trials=sum(t['pair_status'] == 'paired' for t in trials),
                n_error_trials=int(np.sum(measured['errors'] == 1)),
                n_correct_trials=int(np.sum(measured['errors'] == 0)),
                n_retained_trials=len(measured['errors']),
                measurement_offsets_inclusive=method['processing']['measurement_offsets_inclusive'],
                measurement_samples=method['processing']['measurement_samples'],
                error_mean_uv=measured['means']['error'], correct_mean_uv=measured['means']['correct'],
                ern_amplitude_uv=measured['difference'])


def make_metadata(inputs, raw, result, messages):
    import mne
    import scipy
    return dict(status=result['status'], method_id=inputs['method']['method_id'],
                method_contract_sha256=METHOD_SHA256, source_manifest_sha256=SOURCE_SHA256,
                source_fif_sha256=inputs['source_fif_sha256'], sfreq_hz=float(raw.info['sfreq']),
                n_samples=int(raw.n_times), first_sample=int(raw.first_samp),
                eeg_channels=[name for name, kind in zip(raw.ch_names, raw.get_channel_types()) if kind == 'eeg'],
                eog_channels=[name for name, kind in zip(raw.ch_names, raw.get_channel_types()) if kind == 'eog'],
                bads=list(raw.info['bads']), n_projectors=len(raw.info['projs']),
                custom_ref_applied=int(raw.info['custom_ref_applied']), historical_reference_known=False,
                **{key: result[key] for key in ('n_annotations', 'n_stimuli', 'n_paired_trials', 'n_retained_trials')},
                software_versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, mne=mne.__version__),
                warnings=list(messages))


def write_csv(path, columns, rows):
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def emit(output, method, annotations, trials, measured, result, metadata):
    write_csv(output / 'annotations.csv', method['outputs']['annotations.csv'], annotations)
    write_csv(output / 'trials.csv', method['outputs']['trials.csv'], trials)
    with (output / 'response_epochs.npz').open('xb') as stream:
        np.savez_compressed(stream, **{key: measured[key] for key in method['outputs']['response_epochs.npz']})
    waveforms = []
    for j, offset in enumerate(measured['sample_offset']):
        row = dict(sample_offset=int(offset), time_s=float(offset / method['input']['sfreq_hz']))
        for name in ('error', 'correct', 'difference'):
            curve = measured['curves'][name]
            row[name + '_uv'] = None if curve is None else float(curve[j])
        waveforms.append(row)
    write_csv(output / 'fcz_waveforms.csv', method['outputs']['fcz_waveforms.csv'], waveforms)
    def number(value):
        return 'undefined' if value is None else f'{value:.9g}'
    findings = (
        '# Single-person response-locked FCz adaptation\n\n'
        f"Retained {result['n_error_trials']} error and {result['n_correct_trials']} correct trials from "
        f"{result['n_paired_trials']} paired stimuli. Error and correct window means are "
        f"{number(result['error_mean_uv'])} and {number(result['correct_mean_uv'])} microvolts; "
        f"the signed error-minus-correct contrast is {number(result['ern_amplitude_uv'])} microvolts.\n\n"
        'This is a descriptive result for one MNE-modified ERP CORE recording under the declared filter, '
        'fixed 30-channel average reference, common response epoch and immediate pre-response baseline. '
        'It does not reproduce the paper’s multi-person analysis, establish a causal error generator, '
        'or demonstrate artifact-free EEG. Original reference/export details remain incompletely established.\n')
    with (output / 'findings.md').open('x', encoding='utf-8') as stream:
        stream.write(findings)
    # Complete-status JSONs follow successful serialization of the primitive evidence.
    write_json(output / 'run_metadata.json', metadata)
    write_json(output / 'ern.json', result)


def run(data_dir, method_path, output, messages=None):
    import mne
    messages = [] if messages is None else messages
    with recorded_warnings(messages):
        inputs = load_inputs(data_dir, method_path)
        raw = mne.io.read_raw_fif(inputs['fif_path'], preload=False, allow_maxshield=False,
                                  on_split_missing='raise', verbose=False)
        try:
            require(len(raw.filenames) == 1 and safe_path(raw.filenames[0]) == safe_path(inputs['fif_path']),
                    'Expected exactly the authenticated single FIF source')
            method = inputs['method']
            validate_header(raw, method)
            annotations = annotation_ledger(raw, method)
            trials = pair_trials(annotations, raw.n_times, float(raw.info['sfreq']))
            fcz = filter_fcz(raw, method)
            measured = epoch_measurements(fcz, trials, method)
            result = summarize(method, annotations, trials, measured)
        finally:
            raw.close()
    metadata = make_metadata(inputs, raw, result, messages)
    emit(output, method, annotations, trials, measured, result, metadata)
    return result


def failure_output(output, error, messages):
    reason = str(error) or type(error).__name__
    payload = dict(status='failed_precondition', reason=reason, warnings=list(messages))
    for name in ('ern.json', 'run_metadata.json'):
        path = output / name
        if not path.exists():
            write_json(path, payload)
    path = output / 'findings.md'
    if not path.exists():
        with path.open('x', encoding='utf-8') as stream:
            stream.write('# Failed precondition\n\n' + reason + '\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path(os.environ.get('ERRMON_DATA_DIR', '/app/data/errmon')))
    parser.add_argument('--method-contract', type=Path, default=Path(os.environ.get('METHOD_CONTRACT', '/app/method_contract.json')))
    parser.add_argument('--output-dir', type=Path, default=Path(os.environ.get('OUTPUT_DIR', '/app/output')))
    args = parser.parse_args(argv)
    output, messages = None, []
    try:
        output = prepare_output(args.data_dir, args.output_dir, args.method_contract)
        result = run(args.data_dir, args.method_contract, output, messages)
        print(json.dumps(result, allow_nan=False))
        return 0
    except Exception as error:
        if output is not None:
            failure_output(output, error, messages)
        print(type(error).__name__ + ': ' + (str(error) or type(error).__name__), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
