"""Manufactured mechanics only: never a replacement for original-source evidence."""
import csv
import json
from pathlib import Path
import numpy as np
import epoch_contract as e
import proof_of_work as p


def toy_reference():
    method = p.read_json(p.public_method_path())
    n = method['input']['n_samples']
    events = [(5, 'response/left'), (50, 'stimulus/compatible/target_left'), (100, 'response/right'),
              (500, 'stimulus/compatible/target_left'), (800, 'response/left'), (810, 'response/right'),
              (2000, 'stimulus/incompatible/target_left'), (2400, 'response/right'),
              (4000, 'stimulus/compatible/target_right'), (4300, 'response/right'),
              (6000, 'stimulus/incompatible/target_left'), (7000, 'auxiliary/note'),
              (n - 300, 'stimulus/compatible/target_right'), (n - 100, 'response/left')]
    rows = [dict(annotation_index=i, onset_s=sample / 1024., duration_s=0., description=description,
                 event_sample=sample) for i, (sample, description) in enumerate(events)]
    annotations, trials = e.ledger(rows, method)
    ids = np.array([t['stimulus_annotation_index'] for t in trials if t['epoch_status'] == 'retained'])
    offsets = np.arange(-256, 564, dtype=np.int64)
    rng = np.random.default_rng(25178)
    x = rng.normal(0, 3, (len(ids), len(offsets))) + np.arange(len(ids))[:, None]
    own = e.derive(x, ids, offsets, annotations, trials, method)
    result, inp = own['results'], method['input']
    metadata = dict(status=result['status'], method_id=method['method_id'], method_contract_sha256=p.METHOD_SHA,
                    source_manifest_sha256=p.SOURCE_SHA, source_fif_sha256=p.FIF_SHA, sfreq_hz=1024.,
                    n_samples=inp['n_samples'], first_sample=0, eeg_channels=inp['eeg_channels'],
                    eog_channels=inp['eog_channels'], bads=[], n_projectors=0, custom_ref_applied=1,
                    historical_reference_known=False,
                    **{k: result[k] for k in ('n_annotations', 'n_stimuli', 'n_paired_trials', 'n_retained_trials')},
                    software_versions={'manufactured_fixture': 'not_scientific_evidence'}, warnings=[])
    return dict(method=method, metadata=metadata, annotations=annotations, trials=trials,
                trial_ids=ids, offsets=offsets, epochs=x)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, allow_nan=False))


def write_table(path, rows, columns):
    with Path(path).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)


def read_table(path):
    with Path(path).open(newline='') as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames


def emit(output, ref, x=None):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    x = ref['epochs'] if x is None else np.asarray(x)
    own = e.derive(x, ref['trial_ids'], ref['offsets'], ref['annotations'], ref['trials'], ref['method'])
    fields = ref['method']['outputs']
    for filename, rows in [('annotations.csv', ref['annotations']), ('trials.csv', own['trials']),
                           ('fcz_waveforms.csv', own['waveforms'])]:
        write_table(output / filename, rows, fields[filename])
    np.savez_compressed(output / 'response_epochs.npz', stimulus_annotation_index=ref['trial_ids'],
                        sample_offset=ref['offsets'], fcz_prebaseline_uv=x)
    write_json(output / 'ern.json', own['results'])
    meta = dict(ref['metadata'])
    for key in ('status', 'n_annotations', 'n_stimuli', 'n_paired_trials', 'n_retained_trials'):
        meta[key] = own['results'][key]
    write_json(output / 'run_metadata.json', meta)
    (output / 'findings.md').write_text('A single-person descriptive calculation. No population inference.')
    return own
