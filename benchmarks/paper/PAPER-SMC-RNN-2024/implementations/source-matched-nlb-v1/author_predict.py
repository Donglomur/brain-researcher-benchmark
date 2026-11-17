#!/usr/bin/env python3
"""Target-blind source prediction or native-work characterization, never training."""
import argparse
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time

from prepare import PIN, sha, write_json, versions, ensure_external
from memory_reduction import bounded_eval_nlb, verify_reduction

ARMS = {'causal': 'filtering', 'noncausal': 'smoothing'}
HERE = Path(__file__).resolve().parent


def verify_source(root):
    manifest = json.loads((HERE / 'source_manifest.json').read_text())
    for entry in manifest['files']:
        if sha(root / entry['path']) != entry['sha256']:
            raise ValueError('Source or checkpoint hash mismatch: ' + entry['path'])


def load_author(root, arm):
    import torch
    from omegaconf import OmegaConf
    sys.path.insert(0, str(root))
    from vi_rnn.saving import load_model
    model_dir = root / f'models/reach_nlb_{ARMS[arm]}_proposal_36d'
    config = OmegaConf.load(model_dir / 'config.yaml')
    prefixes = list((model_dir / 'checkpoints/best').glob('*_vae_params.pkl'))
    if len(prefixes) != 1:
        raise ValueError('Expected exactly one selected checkpoint')
    prefix = str(prefixes[0])[:-len('_vae_params.pkl')]
    model, vp, tp, trainp = load_model(prefix)
    expected = (model.dim_x, model.dim_z, vp['dim_N'], vp['dim_x_hat'])
    if expected != (137, 36, 512, 182):
        raise ValueError('Wrong selected checkpoint dimensions')
    key_report = {}
    for suffix, target in [('rnn', model.rnn), ('enc', model.encoder)]:
        original = torch.load(prefix + '_state_dict_' + suffix + '.pkl', map_location='cpu')
        original = {k.replace('latent_step', 'transition'): v for k,v in original.items()}
        loaded = target.state_dict()
        missing, extra = sorted(set(loaded)-set(original)), sorted(set(original)-set(loaded))
        mismatch = [k for k in set(original)&set(loaded) if original[k].shape != loaded[k].shape]
        key_report[suffix] = {'count': len(loaded), 'missing': missing, 'extra': extra, 'shape_mismatch': mismatch}
        if missing or extra or mismatch:
            raise ValueError('Checkpoint incompatibility: ' + json.dumps(key_report))
    metadata = {'arm': arm, 'source_commit': PIN, 'checkpoint_files': [p.name for p in sorted(prefixes[0].parent.glob('*.pkl'))],
                'dimensions': {'heldin': 137, 'heldout': 45, 'latent': 36, 'units': 512},
                'checkpoint_task_name': tp.get('name'),
                'checkpoint_encoder': vp['enc_params'], 'key_compatibility': key_report,
                'table2_linkage': 'Released selected36D directory; exact published score linkage requires numerical calibration.'}
    model.to_device(torch.device('cpu'))
    return config, model, metadata


def run(args):
    import torch
    import numpy as np
    from nlb_tools.make_tensors import save_to_h5
    source, inputs = args.source.resolve(), args.inputs.resolve()
    ensure_external(args.report)
    if args.output:
        ensure_external(args.output)
    if args.report.exists() or (args.output and args.output.exists()):
        raise ValueError('Refuse to overwrite native evidence')
    verify_source(source)
    panel_path = inputs / 'mc_maze/test/panel.json'
    panel = json.loads(panel_path.read_text())
    if (panel['dataset'], panel['phase'], panel['n_bins'], panel['condition_count']) != ('mc_maze_20','test',35,108):
        raise ValueError('Not the complete original test panel')
    for name, expected in panel['inputs_sha256'].items():
        if sha(panel_path.parent / name) != expected:
            raise ValueError('Prepared input hash mismatch')
    if (panel_path.parent / 'eval_target_20ms.h5').exists():
        raise ValueError('Test target must not exist in author input tree')
    torch.set_num_threads(6)
    torch.set_num_interop_threads(1)
    seed = 20261117 if args.arm == 'causal' else 20261118
    np.random.seed(seed)
    torch.manual_seed(seed)
    config, model, metadata = load_author(source, args.arm)
    from vi_rnn.datasets import NLBDataset, load_nlb_dataset
    from evaluation.eval_nlb import eval_nlb
    dc = dict(config.dataset)
    dc['phase'] = 'test'
    tr, ev, ut, ue = load_nlb_dataset(inputs, **dc)
    train = NLBDataset(tr, {'name':'mc_maze'}, inputs=ut)
    test = NLBDataset(ev, {'name':'mc_maze'}, inputs=ue)
    report = {'schema':'smc_native_attempt_v1','mode':args.mode,'arm':args.arm,'seed':seed,
              'particles':192,'source_requested_repeats':32,'smooth':False,
              'source_commit':PIN,'panel_sha256':sha(panel_path),'metadata':metadata,
              'versions':versions(),'target_access':'No target argument, no target download by runner, input directory checked; process is not an OS sandbox.',
              'scientific_result':False,'metrics':None}
    if args.mode == 'characterize':
        timings = []
        for name, ds in [('train',train),('eval',test)]:
            chunks = len(ds.data)//int(config.training_params.batch_size)//2
            x = torch.chunk(ds.data.permute(0,2,1), chunks=chunks, dim=0)[0]
            u = torch.chunk(ds.stim.permute(0,2,1), chunks=chunks, dim=0)[0]
            cpu0 = time.process_time(); wall0 = time.monotonic()
            with torch.no_grad():
                result = model.predict_NLB(x, u=u, k=192, t_held_in=35, t_forward=10)
            rate = result[2].mean(dim=-1)
            if not torch.isfinite(rate).all() or (rate < 0).any():
                raise ValueError('Invalid native predicted rates')
            reduction_control = verify_reduction([result[2].detach().cpu().numpy()[:2], result[2].detach().cpu().numpy()[2:5]])
            timings.append({'split':name,'n_trials':len(ds.data),'source_chunks':chunks,
                'actual_chunks':len(torch.chunk(ds.data,chunks,dim=0)), 'chunk_trials':len(x),
                'wall_seconds':time.monotonic()-wall0,'cpu_seconds':time.process_time()-cpu0,
                'full_repeats':32,'full_array_shape':list(result[2].shape),'finite_nonnegative':True, 'particle_reduction_control':reduction_control})
            del result,rate
        report['timings'] = timings
        report['estimated_full_cpu_seconds'] = sum(t['cpu_seconds']*t['actual_chunks']*32 for t in timings)
        report['estimated_full_wall_seconds'] = sum(t['wall_seconds']*t['actual_chunks']*32 for t in timings)
        report['estimate_limit'] = 'First original chunk per split, original192particles and routine; estimate only, no complete predictions or score.'
    else:
        if args.output is None:
            raise ValueError('Full prediction requires --output')
        # Exactly the source averaging/chunking/routine; target=None avoids evaluator imports of truth.
        infer = bounded_eval_nlb(eval_nlb)
        result, submission = infer(config, model, train, test, target=None,
                                    n_particles=192, n_repeats=32, device='cpu', smooth=False)
        if result is not None:
            raise ValueError('Unexpected target-derived result')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        save_to_h5(submission, str(args.output), overwrite=False)
        report['packaging_optimization'] = 'Chunk-local identical NumPy particle mean before trial concatenation; original RNG order retained.'
        report['particle_reduction_patch_sha256'] = sha(HERE/'particle_reduction.patch')
        report.update(submission_sha256=sha(args.output), complete_source_prediction=True,
                      next_step='Freeze submission with scorer.py before any target staging/scoring.')
    report['cpu_seconds'] = time.process_time()
    report['maxrss_native_units'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write_json(args.report,report)
    print(json.dumps({k:report[k] for k in ['mode','arm','cpu_seconds','scientific_result']}),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--arm',choices=ARMS,required=True)
    p.add_argument('--mode',choices=['characterize','predict'],required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--output',type=Path)
    p.add_argument('--cpu-seconds-remaining',type=int,required=True)
    a=p.parse_args()
    if not 0 < a.cpu_seconds_remaining <= 7200:
        raise ValueError('Remaining CPU budget must be1..7200seconds')
    resource.setrlimit(resource.RLIMIT_CPU,(a.cpu_seconds_remaining,a.cpu_seconds_remaining))
    run(a)
