#!/usr/bin/env python3
"""Prepare the complete original NLB panel; never load released test targets."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import time

PIN = 'c808c76ad940491b0a14d2671e3884140aa61258'
NWB_NAMES = {
    'sub-Jenkins_ses-full_desc-test_ecephys.nwb': 3392688,
    'sub-Jenkins_ses-full_desc-train_behavior+ecephys.nwb': 690612247,
}


def ensure_external(path):
    resolved = Path(path).resolve()
    for parent in [resolved, *resolved.parents]:
        if (parent / '.git').exists():
            raise ValueError('Authentic payload/evidence must remain outside any Git checkout')
    return resolved


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':'), sort_keys=True).encode()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def versions(role='inference'):
    packages=['numpy','scipy','pandas','pynwb','hdmf','h5py','nlb-tools']
    if role=='inference':packages+=['scikit-learn','torch','omegaconf']
    return {p:importlib.metadata.version(p) for p in packages}


def prepare(nwb_dir, output):
    environment_versions=versions('preparation')
    if environment_versions['pandas']!='1.3.4':
        raise ValueError('Original preprocessing requires pandas1.3.4; later versions can omit the final trial (official NLB issue3).')
    import h5py
    import numpy as np
    from nlb_tools.nwb_interface import NWBDataset
    from nlb_tools.make_tensors import (make_train_input_tensors, make_eval_input_tensors,
                                        make_eval_target_tensors)
    from memory_prepare import install_memory_preparation, bounded_dataset
    install_memory_preparation()
    import nlb_tools.nwb_interface as nwb_module
    import nlb_tools.make_tensors as tensor_module
    # Scheduling-only compatibility: identical smooth_column/order, no multiprocessing pool.
    # Original validation PSTH default starts all host CPUs; this stays inside the lease.
    nwb_module._poolmap = lambda f, X, **kwargs: list(map(f, X))
    if sha(tensor_module.__file__) != 'e79badd983e37fa0c8f0ddbdeb74972ed505ba4672035daca4e8af16a7bc2d9d':
        raise ValueError('Unexpected NLB tensor implementation')
    nwb_dir, output = Path(nwb_dir).resolve(), Path(output).resolve()
    ensure_external(output)
    data_manifest = json.loads((Path(__file__).parent / 'data_manifest.json').read_text())
    canonical = {row['name']: row['sha256'] for row in data_manifest['nwb_inputs']}
    if output.exists() and any(output.iterdir()):
        raise ValueError('Refuse to overwrite prepared evidence; choose a new empty output')
    if set(p.name for p in nwb_dir.glob('*.nwb')) != set(NWB_NAMES):
        raise ValueError('Require exactly both full MC_Maze NWBs, no additional or missing files')
    nwbs = []
    for name, size in sorted(NWB_NAMES.items()):
        path = nwb_dir / name
        if path.stat().st_size != size:
            raise ValueError('NWB byte size differs: ' + name)
        digest = sha(path)
        if digest != canonical[name]:
            raise ValueError('NWB content differs from immutable source: ' + name)
        nwbs.append({'name': name, 'bytes': size, 'sha256': digest})
    # Retain ALL original fields: native trial dropout checks NaNs across fields.
    dataset = bounded_dataset(str(nwb_dir),bin_width=20)
    info = dataset.trial_info
    ordered_trials = {s: info.loc[info.split == s, 'trial_id'].astype(int).tolist()
                      for s in ('train', 'val', 'test')}
    neurons = {key: [str(x) for x in dataset.data[key].columns]
               for key in ('spikes', 'heldout_spikes')}
    if [len(neurons[k]) for k in ('spikes', 'heldout_spikes')] != [137, 45]:
        raise ValueError('Not the source182neuron panel')
    relevant = info[info.split.isin(['train','val','test'])]
    conditions = relevant[['trial_type', 'trial_version']].dropna().drop_duplicates().values.tolist()
    if len(conditions) != 108:
        raise ValueError('Not the complete108condition source cohort')
    output.mkdir(parents=True, exist_ok=True)
    for phase in ('val', 'test'):
        dest = output / 'mc_maze' / phase
        dest.mkdir(parents=True, exist_ok=True)
        splits = ['train'] if phase == 'val' else ['train', 'val']
        tr = make_train_input_tensors(dataset, 'mc_maze', trial_split=splits,
            save_path=str(dest / 'train_input_20ms.h5'), include_forward_pred=True, include_behavior=True)
        ev = make_eval_input_tensors(dataset, 'mc_maze', trial_split=phase,
            save_path=str(dest / 'eval_input_20ms.h5'))
        if phase == 'val':
            make_eval_target_tensors(dataset, 'mc_maze', train_trial_split='train',
                eval_trial_split='val', include_psth=True, save_path=str(dest / 'eval_target_20ms.h5'))
        elif set(ev) != {'eval_spikes_heldin'} or (dest / 'eval_target_20ms.h5').exists():
            raise ValueError('Test input boundary violated')
        n_train, n_bins, n_heldin = tr['train_spikes_heldin'].shape
        n_eval = ev['eval_spikes_heldin'].shape[0]
        n_heldout = tr['train_spikes_heldout'].shape[-1]
        if (n_bins, n_heldin, n_heldout) != (35, 137, 45):
            raise ValueError('Unexpected native panel shape')
        for name, arr in {**tr, **ev}.items():
            if 'spikes' in name and (not np.isfinite(arr).all() or (arr < 0).any()):
                raise ValueError('Invalid spikes in prepared ' + name)
        expected = {}
        for split, n in [('train', n_train), ('eval', n_eval)]:
            for held, count in [('heldin', n_heldin), ('heldout', n_heldout)]:
                expected[f'{split}_rates_{held}'] = [n, n_bins, count]
                expected[f'{split}_rates_{held}_forward'] = [n, 10, count]
        input_content_hashes = {}
        for filename in ['train_input_20ms.h5', 'eval_input_20ms.h5']:
            with h5py.File(dest / filename, 'r') as handle:
                for key in sorted(handle):
                    arr = np.asarray(handle[key][()], dtype='<f8', order='C')
                    # Canonical dtype/shape/value digest independent of HDF5 container bytes.
                    digest = hashlib.sha256(json.dumps(list(arr.shape),separators=(',', ':')).encode())
                    digest.update(arr.tobytes(order='C'))
                    input_content_hashes[filename + ':' + key] = digest.hexdigest()
        tensor_ids = {'train': info.loc[info.split.isin(splits), 'trial_id'].astype(int).tolist(),
                      'eval': ordered_trials[phase]}
        if len(tensor_ids['train']) != n_train or len(tensor_ids['eval']) != n_eval:
            raise ValueError('Native tensor trial order/count mismatch')
        membership = info[['trial_id','split','trial_type','trial_version']].values.tolist()
        input_hashes = {name: sha(dest / name) for name in ['train_input_20ms.h5', 'eval_input_20ms.h5']}
        manifest = dict(schema='smc_nlb_panel_v1', dataset='mc_maze_20', phase=phase,
            source_commit=PIN, dandiset='000128', dandi_version='0.220113.0400', bin_ms=20,
            n_train=n_train, n_eval=n_eval, n_bins=n_bins, forward_bins=10,
            n_heldin=n_heldin, n_heldout=n_heldout, condition_count=108,
            trial_indices_sha256=digest_json(ordered_trials), neuron_indices_sha256=digest_json(neurons),
            conditions_sha256=digest_json(conditions), inputs_sha256=input_hashes,
            input_content_sha256=input_content_hashes,
            tensor_trial_indices_sha256=digest_json(tensor_ids),
            condition_membership_sha256=digest_json(membership),
            implementation_sha256={name:sha(Path(__file__).parent/name) for name in ['prepare.py','memory_prepare.py','preparation_memory.patch']},
            memory_blocks=dataset.smc_memory_blocks,
            nlb_tensor_source_sha256=sha(tensor_module.__file__),
            nlb_nwb_source_sha256=sha(nwb_module.__file__),
            scheduling_patch='Sequential map replaces host-wide pool only for original validation PSTH smoothing.',
            memory_patch='Complete16-neuron allocation blocks with original group representatives, full original timebounds, ALL source fields; original Gaussian smoothing then20msresample before all-neuron trial/condition aggregation.',
            expected_shapes=expected, nwb_sources=nwbs, versions=environment_versions,
            split_counts={s:len(ids) for s,ids in ordered_trials.items()},
            source_excluded_split_rows=int(len(info)-len(relevant)),
            exposure='Original test targets publicly exposed January2026; never untouched.',
            condition_count_scope='All source cohort conditions; not a claim of108nonempty scored PSTHs')
        if phase == 'val':
            manifest['validation_target_sha256'] = sha(dest / 'eval_target_20ms.h5')
            with h5py.File(dest/'eval_target_20ms.h5','r') as h:
                manifest['validation_target_shapes'] = {k:list(v.shape) for k,v in h['mc_maze_20'].items()}
        write_json(dest / 'panel.json', manifest)
        print(json.dumps({'phase': phase, 'n_train': n_train, 'n_eval': n_eval,
                          'bins': n_bins, 'panel_sha256': sha(dest / 'panel.json')}), flush=True)
    # Operator-only identity maps contain no neural arrays, but still stay outside public Git.
    write_json(output / 'source_identity.json', {'ordered_trials': ordered_trials, 'neurons': neurons,
                                                 'conditions': conditions})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--nwb-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cpu-seconds-remaining', type=int, required=True)
    args = p.parse_args()
    if not 0 < args.cpu_seconds_remaining <= 7200:
        raise ValueError('Remaining CPU budget must be1..7200seconds')
    resource.setrlimit(resource.RLIMIT_CPU,(args.cpu_seconds_remaining,args.cpu_seconds_remaining))
    start = time.monotonic()
    try:
        prepare(args.nwb_dir, args.output)
    finally:
        r = resource.getrusage(resource.RUSAGE_SELF)
        print(json.dumps({'stage': 'prepare', 'wall_seconds': time.monotonic()-start,
                          'cpu_seconds': r.ru_utime+r.ru_stime, 'maxrss_native_units': r.ru_maxrss}), flush=True)
