"""Construct a fresh source-primitives bank, never from oracle outputs or old banks.

Shared components are MNE's calibrated FIF reader/filter and verifier event/arithmetic
utilities. This is a separately executed source reconstruction, not a claim of three
independent numerical filters. The separate authoring checker supplies that comparison.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import time
import warnings
import numpy as np
import epoch_contract as e
import proof_of_work as p


def destinations(source, method_path, output, report):
    source, method_path, output, report = map(p.safe_path, (source, method_path, output, report))
    p.require(output != report and output not in report.parents and report not in output.parents,
              'bank/report destinations overlap')
    for target in (output, report):
        p.require(not target.exists(), 'preserve existing evidence')
        p.require(target != source and source not in target.parents and target not in source.parents,
                  'source/output overlap')
        p.require(target != method_path and target not in method_path.parents, 'method/output overlap')
    return source, method_path, output, report


def load_inputs(source, method_path):
    source = p.safe_path(source)
    p.require(source.is_dir(), 'source directory required')
    p.require(p.sha256(method_path) == p.METHOD_SHA, 'method fingerprint')
    method = p.read_json(method_path)
    p.require(p.sha256(source / 'source_manifest.json') == p.SOURCE_SHA, 'manifest fingerprint')
    manifest = p.read_json(source / 'source_manifest.json')
    p.require(method['source_manifest_sha256'] == p.SOURCE_SHA, 'method source binding')
    names = {r['path'] for r in manifest['files']} | {'source_manifest.json'}
    p.require({x.name for x in source.iterdir()} == names, 'exact source inventory including directories')
    p.require(len(manifest['files']) == 3 and len(names) == 4, 'source member identity')
    for row in manifest['files']:
        path = p.regular(source / row['path'])
        p.require(path.parent == source and path.stat().st_size == row['size_bytes'], 'source regular size')
        p.require(p.sha256(path) == row['sha256'], 'source member fingerprint')
    fif = next(r for r in manifest['files'] if r['role'] == 'raw_fif')
    p.require(fif['path'] == method['input']['filename'] and fif['sha256'] == p.FIF_SHA, 'FIF identity')
    return method, source / fif['path']


def header_and_events(raw, method):
    inp = method['input']
    p.require(raw.n_times == inp['n_samples'] and raw.first_samp == inp['first_sample'] and
              float(raw.info['sfreq']) == inp['sfreq_hz'], 'source sampling/header')
    p.require(raw.ch_names == inp['eeg_channels'] + inp['eog_channels'] and
              raw.get_channel_types() == ['eeg'] * 30 + ['eog'] * 3, 'source channel identity')
    p.require(not raw.info['bads'] and not raw.info['projs'] and int(raw.info['custom_ref_applied']) == 1,
              'source bad/projector/reference precondition')
    p.require(raw.info['meas_date'] is None, 'source measurement clock')
    for ch in raw.info['chs']:
        p.require(ch['unit'] == 107 and ch['unit_mul'] == 0 and ch['range'] == 1 and ch['cal'] == 9.999999974752427e-7,
                  'source physical calibration')
    a = raw.annotations
    p.require(a.orig_time is None and np.isfinite(a.onset).all() and np.isfinite(a.duration).all(), 'annotation clock')
    p.require(np.all(a.duration == 0), 'annotation duration precondition')
    samples = np.rint(a.onset * inp['sfreq_hz']).astype(np.int64)
    rows = []
    for i, (onset, duration, description, sample) in enumerate(zip(a.onset, a.duration, a.description, samples)):
        p.require(0 <= onset < raw.n_times / inp['sfreq_hz'] and 0 <= sample < raw.n_times,
                  'annotation outside recording')
        p.require(not str(description).lower().startswith(('bad', 'edge')), 'boundary annotation precondition')
        rows.append(dict(annotation_index=i, onset_s=float(onset), duration_s=float(duration),
                         description=str(description), event_sample=int(sample)))
    return e.ledger(rows, method)


def source_epochs(raw, trials, method):
    import mne
    names = method['input']['eeg_channels']
    values = raw.get_data(picks=names)
    p.require(values.dtype == np.float64 and values.shape == (30, raw.n_times) and np.isfinite(values).all(),
              'calibrated full EEG shape/finite')
    referenced = values[names.index('FCz')] - np.mean(values, axis=0, dtype=np.float64)
    filtered = mne.filter.filter_data(referenced, method['input']['sfreq_hz'], 0.1, 30.0,
        filter_length=33793, l_trans_bandwidth=0.1, h_trans_bandwidth=7.5, method='fir',
        phase='zero', fir_window='hamming', fir_design='firwin', pad='reflect_limited', n_jobs=1,
        copy=True, verbose=False)
    p.require(np.isfinite(filtered).all(), 'filtered finite')
    lo, hi = method['processing']['sample_offset_inclusive']
    offsets = np.arange(lo, hi + 1, dtype=np.int64)
    retained = [r for r in trials if r['epoch_status'] == 'retained']
    ids = np.array([r['stimulus_annotation_index'] for r in retained], dtype=np.int64)
    epochs = np.empty((len(ids), len(offsets)), dtype=np.float64)
    for i, trial in enumerate(retained):
        epochs[i] = filtered[trial['response_sample'] - raw.first_samp + offsets] * 1e6
    p.require(np.isfinite(epochs).all(), 'full source epochs finite')
    return ids, offsets, epochs


def construct(source, method_path):
    import mne
    import scipy
    method, fif = load_inputs(source, method_path)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        raw = mne.io.read_raw_fif(fif, preload=False, allow_maxshield=False, on_split_missing='raise', verbose=False)
        try:
            p.require(len(raw.filenames) == 1 and p.regular(raw.filenames[0]) == p.regular(fif),
                      'exact single FIF member, no undeclared split inputs')
            annotations, trials = header_and_events(raw, method)
            ids, offsets, epochs = source_epochs(raw, trials, method)
        finally:
            raw.close()
    own = e.derive(epochs, ids, offsets, annotations, trials, method)
    inp, result = method['input'], own['results']
    metadata = dict(status=result['status'], method_id=method['method_id'], method_contract_sha256=p.METHOD_SHA,
                    source_manifest_sha256=p.SOURCE_SHA, source_fif_sha256=p.FIF_SHA,
                    sfreq_hz=inp['sfreq_hz'], n_samples=inp['n_samples'], first_sample=inp['first_sample'],
                    eeg_channels=inp['eeg_channels'], eog_channels=inp['eog_channels'], bads=[], n_projectors=0,
                    custom_ref_applied=1, historical_reference_known=False,
                    **{k: result[k] for k in ('n_annotations', 'n_stimuli', 'n_paired_trials', 'n_retained_trials')},
                    software_versions=dict(python=platform.python_version(), numpy=np.__version__,
                                           scipy=scipy.__version__, mne=mne.__version__),
                    warnings=[w.category.__name__ + ': ' + str(w.message) for w in caught])
    return dict(method=method, metadata=metadata, annotations=annotations, trials=trials,
                trial_ids=ids, offsets=offsets, epochs=epochs)


def write_bank(path, ref):
    arrays = {k + '_json': np.array(json.dumps(ref[k], allow_nan=False))
              for k in ('method', 'metadata', 'annotations', 'trials')}
    arrays.update(schema=np.array(p.BANK_SCHEMA), **{k: ref[k] for k in ('trial_ids', 'offsets', 'epochs')})
    with p.safe_path(path).open('xb') as f:
        np.savez_compressed(f, **arrays)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=Path('/app/data/errmon'))
    parser.add_argument('--method-contract', type=Path, default=Path('/app/method_contract.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--oracle-output', type=Path, help='Optional postconstruction comparison only')
    args = parser.parse_args(argv)
    source, method, output, report = destinations(args.source_dir, args.method_contract, args.output, args.report)
    for target in (output, report):
        target.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    ref = construct(source, method)
    write_bank(output, ref)
    # Never consume oracle artifacts for bank construction, including metadata.
    validation = None
    if args.oracle_output is not None:
        validation = p.validate_output_directory(args.oracle_output, ref)['results']['status']
    record = dict(status='ok', source_manifest_sha256=p.SOURCE_SHA, method_contract_sha256=p.METHOD_SHA,
                  source_fif_sha256=p.FIF_SHA, bank_sha256=p.sha256(output), size_bytes=output.stat().st_size,
                  epoch_shape=list(ref['epochs'].shape), n_annotations=len(ref['annotations']),
                  n_stimuli=len(ref['trials']), metadata=ref['metadata'], postconstruction_validation=validation,
                  elapsed_seconds=time.monotonic() - start,
                  construction='Original source only; shared MNE calibrated FIF reader and filter; separate reference-before-filter and slicing; shared verifier ledger/arithmetic; no oracle code, counts, output or prior bank inputs.',
                  code_sha256={name: p.sha256(Path(__file__).with_name(name))
                               for name in ('build_reference.py', 'proof_of_work.py', 'epoch_contract.py')})
    with report.open('x') as f:
        json.dump(record, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(record, allow_nan=False))


if __name__ == '__main__':
    main()
