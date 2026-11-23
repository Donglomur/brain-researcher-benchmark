"""Complete fixed-profile fresh author-reference fit; no shortened production mode."""
import argparse
import hashlib
import json
import math
import os
import stat
from pathlib import Path
import time

from source_loading import require, input_paths, reauthenticate_inputs, load_frozen_sources, runtime_requirements


def publish_json(root, name, document, maximum):
    raw = (json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    require(len(raw) <= maximum, 'bounded output ' + name)
    path = root / name
    with open(path, 'xb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return {'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def prediction_packet(meta, predictions):
    return {'schema': 'jaxley-retinal-prediction-v1', 'cell_id': meta['cell_id'],
            'test_row_ids': meta['splits']['test'],
            'site_keys': [[site['field'], site['branch'], site['bin']] for site in meta['sites']],
            'predictions': predictions.tolist()}


def run(input_manifest, output, seconds):
    require(type(seconds) is float and math.isfinite(seconds) and 0.0 < seconds <= 365 * 86400,
            'finite positive resource deadline of at most one year')
    component = Path(__file__).resolve().parent
    input_manifest, output = Path(input_manifest).absolute(), Path(output).absolute()
    require(not output.exists(), 'output directory must be absent')
    for ancestor in output.parents:
        require(stat.S_ISDIR(os.lstat(ancestor).st_mode), 'ordinary existing output directory ancestry')
    output = output.resolve(strict=False)
    input_root = input_manifest.parent.resolve(strict=True)
    require(not output.is_relative_to(component) and not component.is_relative_to(output),
            'source and output roots must be disjoint')
    require(not output.is_relative_to(input_root) and not input_root.is_relative_to(output),
            'input and output roots must be disjoint')
    output.mkdir(mode=0o700, parents=False)
    started = time.monotonic()
    runtime = None
    artifacts = {}
    common = {'schema': 'jaxley-streamed-full-fit-result-v1', 'scientific_status': 'UNQUALIFIED',
              'participant_transport_qualified': False, 'historical_checkpoint_or_score_reproduction': False,
              'test_targets_consumed': False, 'test_score_computed': False,
              'deadline_seconds': seconds, 'production_schedule': {
                  'epochs': 21, 'batches_per_epoch': 48, 'full_batches_per_epoch': 47,
                  'full_batch_rows': 256, 'tail_batch_rows': 153, 'optimizer_updates': 1008,
                  'validation_checks': 21, 'validation_chunks': [1024, 1024, 999], 'test_rows': 128}}
    try:
        root, manifest = input_paths(input_manifest)
        requirements = runtime_requirements(component)
        model = load_frozen_sources(component)
        arrays, meta = model.load_packet(root / 'model_arrays.npz', root / 'model_metadata.json')
        # Target names were refused before model.load_packet touched any member.
        require(arrays['currents'].shape == (15360, 287), 'exact selected connection layout')
        for array in arrays.values():
            array.flags.writeable = False
        from fit_runtime import FitRuntime
        from fit_loop import run_production
        def notice(record):
            # At most21 bounded, durable progress records; these are partial evidence.
            publish_json(output, 'epoch-%02d.json' % record['epoch_zero_based'], record, 32768)
        runtime = FitRuntime(arrays, meta, str(root), deadline=started + seconds, checkpoint_notice=notice)
        result = run_production(runtime)
        expected = {'training_singletons_completed': 255885, 'completed_original_gradient_batches': 1008,
                    'validation_singletons_completed': 63987, 'completed_original_validation_batches': 63,
                    'test_singletons_completed': 128, 'last_global_mean_denominator': 153,
                    'last_training_batch_completed_rows': 153, 'last_validation_batch_completed_rows': 999}
        require(runtime.stats == expected, 'complete singleton and batch counters')
        require(runtime.updates == 1008 and len(runtime.history) == 21, 'complete optimizer and validation history')
        runtime.model_state_unchanged()
        codec, np, tree = runtime.codec, runtime.np, runtime.tree_util
        selected = codec.encode_tree(result['best_snapshot'], np, tree, role='parameters')
        selected_hash = hashlib.sha256(codec.canonical(selected)).hexdigest()
        require(selected_hash == runtime.selected_snapshot_sha256, 'selected snapshot final commitment')
        artifacts['selected_parameters'] = publish_json(output, 'selected_parameters.json', selected, 512 * 1024)
        artifacts['last_parameters'] = publish_json(output, 'last_parameters.json',
            codec.encode_tree(runtime.opt, np, tree, role='parameters'), 512 * 1024)
        artifacts['last_optimizer_state'] = publish_json(output, 'last_optimizer_state.json',
            codec.encode_tree(runtime.optimizer_states, np, tree, role='optimizer_state'), 1024**2)
        artifacts['contexts'] = publish_json(output, 'contexts.json', {
            'initial': runtime.initial_context,
            'final': codec.tree_witness((runtime.opt, runtime.states, runtime.optimizer_states), np, tree),
            'fixed_neuronal_state': runtime.initial_model_state}, 2 * 1024**2)
        artifacts['validation_history'] = publish_json(output, 'validation_history.json', runtime.history, 1024**2)
        artifacts['selected_validation_predictions'] = publish_json(output, 'selected_validation_predictions.json',
            {'row_ids': meta['splits']['val'], 'predictions': runtime.selected_predictions.tolist()}, 12 * 1024**2)
        artifacts['prediction'] = publish_json(output, 'prediction.json', prediction_packet(meta, result['test_predictions']), 1024**2)
        artifacts['rng'] = publish_json(output, 'rng.json', runtime.rng, 128 * 1024)
        # Reauthenticate inputs after the complete operation. No scientific targets
        # are exposed by this source check; actual read-only mount enforcement is external.
        reauthenticate_inputs(input_manifest, root, manifest)
        report = {**common, 'status': 'COMPLETE_FRESH_STREAMED_AUTHOR_REFERENCE', 'complete': True,
                  'optimizer_updates': runtime.updates, 'validation_checks': len(runtime.history),
                  'selected_epoch_zero_based': result['best_epoch_zero_based'],
                  'selected_completed_updates': 48 * (result['best_epoch_zero_based'] + 1),
                  'validation_mean_Pearson': result['best_validation_mean'],
                  'selected_parameters_sha256': selected_hash, 'identity_sha256': meta['identity_sha256'],
                  'input_files': manifest['files'], 'runtime_profile': requirements['schema'],
                  'fixed_coordinate_policy_sha256': runtime.policy.POLICY_SHA256,
                  'statistics': runtime.stats, 'artifacts': artifacts,
                  'elapsed_seconds': time.monotonic() - started}
        publish_json(output, 'RESULT.json', report, 65536)
        return report
    except BaseException as error:
        report = {**common, 'status': 'FAILED_OR_PARTIAL_NOT_A_COMPLETE_FIT', 'complete': False,
                  'optimizer_updates': 0 if runtime is None else runtime.updates,
                  'validation_checks': 0 if runtime is None else len(runtime.history),
                  'statistics': {} if runtime is None else runtime.stats,
                  'error_type': type(error).__name__, 'error': str(error)[:512],
                  'artifacts': artifacts, 'elapsed_seconds': time.monotonic() - started}
        if not (output / 'RESULT.json').exists():
            publish_json(output, 'RESULT.json', report, 65536)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-manifest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--seconds', required=True, type=float, help='resource deadline only; does not shorten the scientific schedule')
    args = parser.parse_args()
    report = run(args.input_manifest, args.output, args.seconds)
    print(json.dumps({'status': report['status'], 'complete': report['complete']}))


if __name__ == '__main__':
    main()
