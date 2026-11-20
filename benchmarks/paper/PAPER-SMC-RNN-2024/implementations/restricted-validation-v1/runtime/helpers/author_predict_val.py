#!/usr/bin/env python3
"""Fixed restricted-VALID noncausal prediction with the original author algorithm."""
import argparse
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time

from prepare import PIN, sha, write_json, versions, ensure_external
from memory_reduction import bounded_eval_nlb, verify_reduction

ARMS = {'noncausal': 'smoothing'}
HERE = Path(__file__).resolve().parent


def verify_source(root):
    manifest = json.loads((HERE / 'validation_author_manifest.json').read_text())
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


def validate_cpu_seconds(value):
    if type(value) is not int or not 0 < value <= 64800:
        raise ValueError('An explicit non-bool integer CPU selection in1..64800seconds is required; adequacy is unqualified')
    return value


def run(args):
    selected_cpu_seconds = validate_cpu_seconds(args.cpu_seconds)
    if args.arm != 'noncausal' or args.mode != 'predict' or args.output is None:
        raise ValueError('Only the fixed noncausal VALID prediction route is supported')
    source, inputs = args.source.resolve(), args.inputs.resolve()
    from validation_reference import inspect_inputs
    packet = inspect_inputs(inputs, args.packet_sha256)
    import torch
    import numpy as np
    from nlb_tools.make_tensors import save_to_h5
    ensure_external(args.report)
    ensure_external(args.output)
    if args.report.exists() or args.output.exists():
        raise ValueError('Refuse to overwrite native evidence')
    verify_source(source)
    torch.set_num_threads(6)
    torch.set_num_interop_threads(1)
    seed = 20261118
    np.random.seed(seed)
    torch.manual_seed(seed)
    config, model, metadata = load_author(source, args.arm)
    from vi_rnn.datasets import NLBDataset, load_nlb_dataset
    from evaluation.eval_nlb import eval_nlb
    dc = dict(config.dataset)
    dc['phase'] = 'val'
    if (dc.get('name'), dc.get('bin_size'), dc.get('t_forward'), dc.get('input_field'), dc.get('u')) != ('mc_maze', 20, 10, None, 0) or dc.get('cosmooth') is not True:
        raise ValueError('Exact original unconditioned co-smoothing VALID loader required')
    tr, ev, ut, ue = load_nlb_dataset(inputs, **dc)
    if (tuple(tr.shape), tuple(ev.shape)) != ((1721, 45, 182), (574, 35, 137)):
        raise ValueError('Loaded tensors differ from the restricted VALID packet')
    train = NLBDataset(tr, {'name':'mc_maze'}, inputs=ut)
    test = NLBDataset(ev, {'name':'mc_maze'}, inputs=ue)
    report = {'schema':'smc_restricted_validation_native_attempt_v1','mode':args.mode,'arm':args.arm,'seed':seed,
              'phase':'val','particles':192,'source_requested_repeats':32,'smooth':False,
              'source_commit':PIN,'packet_sha256':args.packet_sha256,'metadata':metadata,
              'versions':versions(),'target_access':'Projected packet only and target=None; outer custody must enforce mounts independently. This process is not an OS sandbox.',
              'restricted_eval_shape':[574,35,137],
              'train_input_shape':[1721,45,182],
              'train_rates_role':'canonical_metric_decoder_inputs_not_restricted_calibration',
              'checkpoint_training_cohort':'unknown','resource_adequacy':False,
              'selected_cpu_seconds':selected_cpu_seconds,
              'resource_limit_scope':'An explicitly selected CPU ceiling is bounded by6threads*10800wall=64800 CPU-seconds; it creates no actual allocation and gives no VALID completion guarantee.',
              'training':False,'adaptation':False,'AI_attempt':False,'scientific_improvement':False,
              'scientific_result':False,'metrics':None}
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
                  next_step='Freeze the restricted VALID submission before any VALID target staging or scoring; do not use the TEST-only scorer boundary.')
    report['cpu_seconds'] = time.process_time()
    report['maxrss_native_units'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write_json(args.report,report)
    print(json.dumps({k:report[k] for k in ['mode','arm','cpu_seconds','scientific_result']}),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--arm',choices=ARMS,required=True)
    p.add_argument('--mode',choices=['predict'],required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--packet-sha256',required=True)
    p.add_argument('--cpu-seconds',type=int,required=True)
    a=p.parse_args()
    selected_cpu_seconds = validate_cpu_seconds(a.cpu_seconds)
    resource.setrlimit(resource.RLIMIT_CPU,(selected_cpu_seconds,selected_cpu_seconds))
    run(a)
