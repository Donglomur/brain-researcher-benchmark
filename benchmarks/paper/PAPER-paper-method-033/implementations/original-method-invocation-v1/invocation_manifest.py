"""Offline source-supported MindBridge invocation and checkpoint-role bindings.

No source module, model, checkpoint or payload is opened or executed. Consistent
declarations are not proof of actual checkpoint identity, exposure or compatibility.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re

COMMIT = '2a3943ff5b619db6f85f16a5e7ff1331d25def55'
SOURCE_BINDINGS_SHA = 'da41d3bbc26bbf108563a61157606abb1ffd8804dec9d24f92709bd581acd268'
CAPTURE_HELPER_SHA = '08e2f9bc35fae9d3ce195ee22e646384c1434000bb3c41568782f099b3cba495'
BUDGETS = (500, 1500, 4000)
ARMS = {'vanilla': 'scratch', 'mindbridge': 'reset'}
HEX = re.compile('[a-f0-9]{64}')
MODEL = re.compile('[A-Za-z0-9][A-Za-z0-9_-]{0,119}')


class BindingError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise BindingError(message)


def exact(value, fields, name):
    need(type(value) is dict and set(value) == set(fields), name + ': exact fields')


def sha(value):
    need(type(value) is str and HEX.fullmatch(value), 'canonical declared SHA256')
    return value


def path(value):
    need(type(value) is str and value.startswith('/') and '\x00' not in value and
         '\\' not in value and PurePosixPath(value).as_posix() == value and
         '..' not in PurePosixPath(value).parts, 'explicit canonical absolute path')
    return value


def subjects(value, expected):
    need(type(value) is list and all(type(v) is int for v in value) and value == expected,
         'exact declared source-subject exposure')


def checkpoint(value, *, role, model_root):
    exact(value, ('role', 'model_name', 'tag', 'path', 'bytes', 'sha256',
                  'training_receipt_sha256'), 'checkpoint declaration')
    need(value['role'] == role and type(value['model_name']) is str and MODEL.fullmatch(value['model_name']),
         'checkpoint role/model name')
    need(value['tag'] == 'last', 'checked-in inference uses last, not an outcome-selected checkpoint')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= 10000000000,
         'bounded declared checkpoint extent')
    sha(value['sha256']); sha(value['training_receipt_sha256'])
    expected = f"{model_root}/{value['model_name']}/last.pth"
    need(path(value['path']) == expected, 'source model-name/checkpoint-path binding')
    return value


def admit_transport(value):
    """Only the existing high-level eight-draw adapter can feed this capture seam.

    Original recon.py saves the chosen reconstruction, not all eight candidates.
    These are role declarations; no image bytes or generation order are inspected.
    """
    exact(value, ('producer', 'producer_sha256', 'generated_draws', 'retained_draws', 'selection_stage'), 'transport')
    need(value['producer'] == 'native_predict_eight_draws', 'selected-only reference output is not panel capture')
    need(sha(value['producer_sha256']) == CAPTURE_HELPER_SHA, 'exact existing capture-helper identity declaration')
    need(type(value['generated_draws']) is int and value['generated_draws'] == 8 and
         type(value['retained_draws']) is int and value['retained_draws'] == 8,
         'eight generation-ordered retained candidates required')
    need(value['selection_stage'] == 'operator_after_freeze', 'real target selection must follow candidate freeze')


def build(binding):
    exact(binding, ('schema', 'source_kind', 'source_bindings_sha256', 'information_condition', 'composition_sha256',
                    'locations', 'source_pretrain', 'conditions'), 'invocation binding')
    need(binding['schema'] == 'mindbridge-invocation-bindings/v1', 'known binding schema')
    need(sha(binding['source_bindings_sha256']) == SOURCE_BINDINGS_SHA, 'unchanged source-contract pin required')
    need(binding['source_kind'] in ('generated_engineering_control', 'operator_declared_bindings'),
         'explicit evidence kind')
    need(binding['information_condition'] in ('paper_data', 'paper_data_author_code'),
         'information condition is separate from method arm')
    sha(binding['composition_sha256'])
    loc = binding['locations']
    exact(loc, ('python', 'author_root', 'operator_root', 'reference_data_root', 'vd_cache_dir',
                'cache_manifest', 'cache_manifest_pin'), 'explicit locations')
    for value in loc.values():
        path(value)
    operator_parent = str(PurePosixPath(loc['operator_root']).parent)
    supported_roots = [operator_parent + '/source/official', operator_parent + '/public/author_code']
    need(loc['author_root'] in supported_roots, 'existing native_bridge source lookup layout')
    model_root = loc['author_root'] + '/train_logs'
    pre = binding['source_pretrain']
    exact(pre, ('subjects', 'excluded_target', 'train_per_subject', 'validation_per_subject', 'checkpoint'),
          'source pretraining declaration')
    subjects(pre['subjects'], [1, 2, 5])
    need(type(pre['excluded_target']) is int and pre['excluded_target'] == 7 and
         type(pre['train_per_subject']) is int and pre['train_per_subject'] == 8559 and
         type(pre['validation_per_subject']) is int and pre['validation_per_subject'] == 300,
         'target-excluded complete source training/validation declaration')
    pretrained = checkpoint(pre['checkpoint'], role='source125_pretrain', model_root=model_root)
    need(pretrained['model_name'] == 'mindbridge_subj125', 'checked-in reset load_from points to source125')
    rows = binding['conditions']
    need(type(rows) is list and len(rows) == 6, 'all six original conditions required')
    seen, models, outputs, views = set(), set(), set(), set()
    conditions = []
    for row in rows:
        exact(row, ('case_id', 'arm', 'budget', 'target_subject', 'source_subjects', 'checkpoint',
                    'view_root', 'view_pin_file', 'checkpoint_pin_file', 'capture_output',
                    'capture_max_bytes', 'transport'), 'condition')
        arm, budget = row['arm'], row['budget']
        need(type(arm) is str and arm in ARMS and type(budget) is int and budget in BUDGETS and
             (arm, budget) not in seen, 'unique original arm/budget')
        seen.add((arm, budget))
        cid = f'adapt_{ARMS[arm]}_s07_k{budget:04d}'
        need(row['case_id'] == cid and type(row['target_subject']) is int and row['target_subject'] == 7,
             'case identity and target7')
        subjects(row['source_subjects'], [1, 2, 5] if arm == 'mindbridge' else [])
        ckpt = checkpoint(row['checkpoint'], role=cid, model_root=model_root)
        need(ckpt['model_name'] not in models and ckpt['model_name'] != pretrained['model_name'],
             'distinct source/pretrained and per-condition model paths')
        models.add(ckpt['model_name'])
        for key in ('view_root', 'view_pin_file', 'checkpoint_pin_file', 'capture_output'):
            path(row[key])
        need(row['view_root'] not in views and row['view_root'] != loc['reference_data_root'],
             'separate case views; private reference data cannot be candidate view')
        need(row['capture_output'] not in outputs and row['capture_output'] != row['view_root'],
             'distinct fresh capture destinations are declared')
        views.add(row['view_root']); outputs.add(row['capture_output'])
        need(type(row['capture_max_bytes']) is int and row['capture_max_bytes'] > 0,
             'explicit capture output allowance; sufficient storage is not established here')
        admit_transport(row['transport'])
        cwd = loc['author_root'] + '/src'
        training = {'argv': None, 'historical_invocation_verified': False,
                    'source_parameterization_possible': True}
        if arm == 'mindbridge':
            training['paper_supported_condition'] = {'epochs': 200, 'source_subjects': [1, 2, 5],
                'target_subject': 7, 'same_train_only_length_per_source_and_target': budget,
                'exact_historical_CLI_and_checkpoint_lineage_verified': False}
        if arm == 'mindbridge' and budget == 4000 and ckpt['model_name'] == 'mindbridge_subj125_a7_l4000':
            literal = ['python', '-W', 'ignore', 'main.py',
                '--model_name', 'mindbridge_subj125_a7_l4000', '--subj_target', '7', '--subj_source', '1', '2', '5',
                '--num_epochs', '200', '--batch_size', '50', '--val_batch_size', '50',
                '--h_size', '2048', '--n_blocks', '4', '--pool_type', 'max', '--pool_num', '8192',
                '--mse_mult', '10000', '--rec_mult', '1', '--cyc_mult', '1',
                '--eval_interval', '10', '--ckpt_interval', '10',
                '--load_from', '../train_logs/mindbridge_subj125/last.pth', '--num_workers', '8',
                '--max_lr', '1.5e-4', '--adapting', '--length', '4000']
            training.update(argv=[loc['python'], *literal[1:], '--data_path', row['view_root']],
                checked_in_expanded_argv=literal, cwd=cwd, environment={'CUDA_VISIBLE_DEVICES': '0'},
                binding_changes=['Explicit interpreter location and --data_path bind the prepared case view.'],
                evidence='scripts/adapt_bridge.sh; only target7/reset4000 is checked in',
                referenced_pretrain=pretrained, output_checkpoint=ckpt,
                wandb_default=True, learning_rate_rule='main.py multiplies max_lr by actual accelerator process count')
        else:
            training['missing_binding'] = (
                'Exact target7 limited-data scratch epochs/topology/LR recipe; train_single is subject1/full-data/600epochs/two processes.'
                if arm == 'vanilla' else
                'Original reset recipe for this budget/output model name; only4000 with mindbridge_subj125_a7_l4000 is checked in.')
        reference_argv = [loc['python'], '-W', 'ignore', 'recon.py', '--model_name', ckpt['model_name'],
            '--ckpt_from', 'last', '--h_size', '2048', '--n_blocks', '4', '--pool_type', 'max',
            '--subj_load', '7', '--subj_test', '7', '--text_image_ratio', '0.5', '--guidance_scale', '5',
            '--recons_per_sample', '8', '--data_path', loc['reference_data_root'],
            '--vd_cache_dir', loc['vd_cache_dir'], '--test_start', '0', '--test_end', '982']
        original_reference = {'argv': reference_argv, 'cwd': cwd, 'environment': {'CUDA_VISIBLE_DEVICES': '0'},
            'source_status': 'Target7/model/location/full-range parameterization of the checked-in subject1 inference script.',
            'argument_changes': 'Canonical --guidance_scale expands source --guidance; data/cache/range are explicit bindings.',
            'role': 'operator_original_reference_only', 'generated_draws': 8, 'retained_draws': 1,
            'selection': 'Original utils.reconstruction target-aware selection; recon.py saves only selected .pt.',
            'panel_capture_compatible': False, 'checkpoint': ckpt,
            'expected_output_directory': model_root + '/' + ckpt['model_name'] + '/recon_on_subj7',
            'autoencoder_presence_dependency': model_root + '/None/epoch120.pth',
            'historical_invocation_verified': False}
        capture_argv = [loc['python'], loc['operator_root'] + '/native_predict.py',
            '--view', row['view_root'], '--view-pin', row['view_pin_file'],
            '--checkpoint', ckpt['path'], '--checkpoint-pin', row['checkpoint_pin_file'],
            '--cache', loc['cache_manifest'], '--cache-pin', loc['cache_manifest_pin'],
            '--output', row['capture_output'], '--max-output-bytes', str(row['capture_max_bytes'])]
        capture = {'argv': capture_argv, 'cwd': loc['operator_root'],
            'expected_helper_bytes': 4986, 'expected_helper_sha256': CAPTURE_HELPER_SHA,
            'route': 'existing native_predict.py high-level-only adapter', 'generated_draws': 8, 'retained_draws': 8,
            'dummy_image_selection': 'discarded; all generation-ordered candidates retained',
            'real_selection': 'one existing operator best-of-eight after candidate freeze',
            'source_equivalence_or_publication_parity_verified': False}
        conditions.append({'case_id': cid, 'arm': arm, 'budget': budget, 'checkpoint': ckpt,
            'target_subject': 7, 'source_subjects': row['source_subjects'], 'test_images': 982,
            'validation_images_per_included_subject': 300, 'prefix_rule': 'source train-only sorted-key prefix',
            'training': training, 'original_reference': original_reference, 'eight_draw_capture': capture})
    need(seen == {(a, k) for a in ARMS for k in BUDGETS}, 'complete six-condition coverage')
    conditions.sort(key=lambda r: (r['budget'], r['arm']))
    return {'schema': 'mindbridge-original-method-invocation-manifest/v1', 'task_id': 'PAPER-paper-method-033',
        'source_commit': COMMIT, 'source_kind': binding['source_kind'],
        'source_bindings_sha256': SOURCE_BINDINGS_SHA,
        'information_condition': binding['information_condition'], 'composition_sha256': binding['composition_sha256'],
        'operator_private': True, 'launched': False, 'execution_authorized': False,
        'checkpoint_bytes_verified': False, 'checkpoint_state_compatibility_verified': False,
        'training_exposure_authenticated': False, 'source_lookup_verified': False,
        'scientific_qualification': False, 'reproduction': 'unknown', 'improvement': 'unknown',
        'pretraining': {'argv': None, 'declaration': pre,
            'missing_binding': 'Exact source125 recipe/checkpoint lineage; checked-in train_bridge uses1257/eight processes.'},
        'conditions': conditions,
        'holds': ['Declarations can reject contradictions, not detect mislabeled weight bytes whose declarations also changed.',
                  'Source/data/caption/cache/pin files were not opened; all source modules and weights require independent authentication.',
                  'Original training preloads all73000 captions; access-qualified caption mapping is unresolved.',
                  'Original scripts leave wandb enabled and may download weights; no offline execution or launch is granted.',
                  'Source checkpoint loading uses strict=False; hash strings do not prove state compatibility.',
                  'Reference autoencoder presence changes img2img; existing capture adapter is separately high-level-only.',
                  'If public/author_code is selected, source/official must be absent or separately proven identical because source lookup prefers it.',
                  'Historical runtime/weights/memberships, protected freeze chronology, sufficient output storage and published comparability remain open.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binding')
    parser.add_argument('output')
    args = parser.parse_args()
    with open(args.binding, 'rb') as stream:
        raw = stream.read(65537)
    need(len(raw) <= 65536, 'bounded metadata input')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    binding = json.loads(raw, object_pairs_hook=pairs,
                         parse_constant=lambda value: (_ for _ in ()).throw(BindingError('nonfinite JSON')))
    body = (json.dumps(build(binding), indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    need(len(body) <= 65536, 'bounded invocation metadata output')
    with open(args.output, 'xb') as stream:
        stream.write(body)


if __name__ == '__main__':
    main()
