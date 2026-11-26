#!/usr/bin/env python3
"""One-context numeric presentation and complete target-free direct collection.

Operator utilities only: no model invocation, scoring or isolation enforcement.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
CONDITION = 'neural031_direct_numeric_context_v1'
KEYS = ('train_x', 'train_y', 'train_mouse', 'train_rowid', 'query_x', 'query_rowid')
COMMON = ['baseline_volume', 'basal_indicator', 'local_missing', 'coincident_missing']
MANIFEST_KEYS = {'schema', 'candidate_id', 'fold', 'held_mouse', 'view', 'data',
                 'features', 'training_mouse_indices', 'train_rows', 'query_rows',
                 'training_target', 'query_target_or_followup_metadata',
                 'neural_activity_values_physically_present', 'prediction_time'}
DEPENDENCIES = ('paired-delivery-v1/io031.py', 'paired-delivery-v1/SOURCE_INPUTS.json',
                'ratio-scoring-v1/endpoint.py')
OBSERVATION_CAP = 524288
RESPONSE_CAP = 131072
INSTRUCTIONS = (
    'Predict a finite nonnegative follow-up/baseline spine-volume ratio for every query row, '
    'in its original order. One means no change; zero is permitted. Use only this complete '
    'context and your existing knowledge, without tools, code execution, files or retrieval. '
    'Training rows are the other nineteen mice; null training ratios are unavailable, not zero. '
    'Only the neural view contains activity measurements; both views share missingness flags. '
    'Null neural measurements are missing, not zero. Do not omit any query or infer whether '
    'its follow-up is available. The observed endpoint is a follow-up ratio after the complete '
    'Early recording; exact elapsed visit time is unqualified despite inherited next_day wording. '
    'Return only an object with schema neural031_direct_response_v1, request_id copied below, '
    'and rows containing each query row_id and its prediction. This is direct numeric observation '
    'of processed measurements, not raw microscopy or waveform interpretation.'
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def raw_read(path, cap):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= cap, 'Bounded regular file required')
        body = stream.read(cap + 1)
        need(len(body) == info.st_size and len(body) <= cap, 'Complete bounded bytes required')
        return body


def load_source(source_sha256):
    body = raw_read(HERE / 'SOURCE.json', 65536)
    need(pin(body)['sha256'] == source_sha256, 'Exact operator-selected source manifest required')
    source = json.loads(body)
    need(set(source) == {'schema', 'files', 'dependencies', 'scope'} and
         source['schema'] == 'neural031_numeric_observation_source_v1' and
         set(source['files']) == {'observation.py', 'test_observation.py', 'README.md'} and
         set(source['dependencies']) == set(DEPENDENCIES), 'Exact source closure required')
    captured = {}
    for name, expected in source['files'].items():
        data = raw_read(HERE / name, 262144)
        need(pin(data) == expected, 'Current package source identity changed')
    for relative in DEPENDENCIES:
        data = raw_read(HERE.parent / relative, 65536)
        need(pin(data) == source['dependencies'][relative], 'Pinned dependency identity changed')
        captured[relative] = data
    return captured


def module(body, name):
    result = types.ModuleType(name)
    exec(compile(body, name, 'exec'), result.__dict__)
    return result


class Engine:
    def __init__(self, source_sha256):
        captured = load_source(source_sha256)
        self.source_sha256 = source_sha256
        self.io = module(captured[DEPENDENCIES[0]], '_neural031_numeric_io')
        self.endpoint = module(captured[DEPENDENCIES[2]], '_neural031_numeric_endpoint')
        self._source_inputs = self.io.decode(captured[DEPENDENCIES[1]])

    def source_inputs(self):
        # The CLI has no alternate original-cohort or source-roster operand.
        return self._source_inputs

    def item(self, fold, view):
        need(type(fold) is int and 0 <= fold < 20 and view in ('baseline', 'neural'),
             'One declared fold and physical view required')
        return self.source_inputs()['paired_views'][2 * fold + (view == 'neural')]

    def presentation(self, data, manifest_body, fold, view):
        """Pure presentation seam; authenticate selected context before array decode."""
        import numpy as np
        item = self.item(fold, view)
        need(pin(manifest_body) == item['manifest'] and pin(data) == item['data'],
             'Exact selected original context bytes required')
        m = self.io.decode(manifest_body)
        need(type(m) is dict and set(m) == MANIFEST_KEYS and
             m['schema'] == 'neural031_ordinary_public_view_v1' and m['candidate_id'] == 'NEURAL-031' and
             type(m['fold']) is int and m['fold'] == fold and m['view'] == view and
             m['held_mouse'] == self.endpoint.MICE[fold] and m['data'] == item['data'] and
             type(m['training_mouse_indices']) is list and
             all(type(i) is int for i in m['training_mouse_indices']) and
             m['training_mouse_indices'] == [i for i in range(20) if i != fold] and
             type(m['query_rows']) is int and 0 < m['query_rows'] < 774 and
             type(m['train_rows']) is int and m['train_rows'] == 774 - m['query_rows'] and
             m['features'] == COMMON + (['local_coactivity_norm', 'dendrite_coincident_norm'] if view == 'neural' else []) and
             m['training_target'] == 'next_day_ratio_with_NaN_unavailable' and
             m['query_target_or_followup_metadata'] is False and
             m['neural_activity_values_physically_present'] is (view == 'neural') and
             m['prediction_time'] == 'after_complete_Early_recording_for_next_day_size',
             'Original one-context scientific manifest required')
        p = self.io.arrays(np, data, KEYS)
        columns = 4 if view == 'baseline' else 6
        for split in ('train', 'query'):
            x, rows = p[split + '_x'], p[split + '_rowid']
            need(x.dtype == np.dtype('float64') and x.shape == (m[split + '_rows'], columns) and
                 rows.dtype == np.dtype('int64') and rows.shape == (len(x),) and
                 bool(np.all((rows >= 0) & (rows < 1143))) and bool(np.all(np.diff(rows) > 0)) and
                 bool(np.all(np.isfinite(x[:, :4]))) and bool(np.all(x[:, 0] > 0)) and
                 bool(np.all((x[:, 1:4] == 0) | (x[:, 1:4] == 1))),
                 'Complete ordered physical predictors and query identities required')
            if view == 'neural':
                activity = x[:, 4:]
                need(bool(np.all(np.isnan(activity) | np.isfinite(activity))) and
                     np.array_equal(x[:, 2:4], np.isnan(activity).astype(np.float64)),
                     'Neural values and shared missingness must agree')
        y, groups = p['train_y'], p['train_mouse']
        need(y.dtype == np.dtype('float64') and y.shape == (m['train_rows'],) and
             groups.dtype == np.dtype('int64') and groups.shape == y.shape and
             set(groups.tolist()) == set(range(20)) - {fold} and
             not set(p['train_rowid'].tolist()).intersection(p['query_rowid'].tolist()) and
             bool(np.all(np.isnan(y) | (np.isfinite(y) & (y >= 0)))) and
             all(bool(np.any((groups == i) & np.isfinite(y))) for i in range(20) if i != fold),
             'Nineteen training groups and original finite-or-unavailable training labels required')
        def numeric(value):
            if isinstance(value, list):
                return [numeric(v) for v in value]
            return None if type(value) is float and math.isnan(value) else value
        observation = {'schema': CONDITION, 'candidate_id': 'NEURAL-031',
                       'access_condition': 'direct_numeric_no_tools',
                       'request_id': item['manifest']['sha256'], 'instructions': INSTRUCTIONS,
                       'context': m, 'arrays': {key: numeric(p[key].tolist()) for key in KEYS}}
        body = self.io.encoded(observation)
        need(len(body) <= OBSERVATION_CAP, 'Complete observation exceeds capacity; never truncate')
        return body

    def present(self, input_root, fold, view, output):
        item = self.item(fold, view)
        manifest = self.io.read(self.io.join(input_root, 'manifest.json'), 16384, item['manifest'])
        data = self.io.read(self.io.join(input_root, 'data.npz'), 262144, item['data'])
        observation = self.presentation(data, manifest, fold, view)
        receipt = {'schema': 'neural031_numeric_presentation_v1', 'condition': CONDITION,
                   'source_sha256': self.source_sha256, 'fold': fold, 'view': view,
                   'inputs': {k: item[k] for k in ('manifest', 'data')}, 'observation': pin(observation),
                   'provider_delivery_verified': False, 'fresh_model_context_verified': False,
                   'no_tools_enforced': False, 'scientific_qualification': False}
        writer = self.io.Writer(output, OBSERVATION_CAP + 16384)
        writer.write('OBSERVATION.json', observation, OBSERVATION_CAP)
        writer.write('PRESENTATION.json', self.io.encoded(receipt), 16384)
        return {'presentation': writer.files['PRESENTATION.json'], 'written_bytes': writer.used}

    def load_presentation(self, directory, expected, fold, view):
        item = self.item(fold, view)
        receipt_body = self.io.read(self.io.join(directory, 'PRESENTATION.json'), 16384, expected)
        receipt = self.io.decode(receipt_body)
        need(type(receipt) is dict and set(receipt) ==
             {'schema', 'condition', 'source_sha256', 'fold', 'view', 'inputs', 'observation',
              'provider_delivery_verified', 'fresh_model_context_verified', 'no_tools_enforced',
              'scientific_qualification'} and
             receipt['schema'] == 'neural031_numeric_presentation_v1' and receipt['condition'] == CONDITION and
             receipt['source_sha256'] == self.source_sha256 and type(receipt['fold']) is int and
             receipt['fold'] == fold and receipt['view'] == view and
             receipt['inputs'] == {k: item[k] for k in ('manifest', 'data')} and
             all(receipt[k] is False for k in ('provider_delivery_verified', 'fresh_model_context_verified',
                                              'no_tools_enforced', 'scientific_qualification')),
             'Exact selected numeric presentation receipt required')
        body = self.io.read(self.io.join(directory, 'OBSERVATION.json'), OBSERVATION_CAP, receipt['observation'])
        observation = self.io.decode(body)
        need(observation['schema'] == CONDITION and observation['request_id'] == item['manifest']['sha256'] and
             observation['context']['fold'] == fold and observation['context']['view'] == view,
             'Observation must match selected context')
        return receipt, observation

    def prediction(self, response, observation, fold, view):
        value = self.io.decode(response)
        need(type(value) is dict and set(value) == {'schema', 'request_id', 'rows'} and
             value['schema'] == 'neural031_direct_response_v1' and
             value['request_id'] == observation['request_id'] and type(value['rows']) is list,
             'One request-bound direct response required')
        rows = observation['arrays']['query_rowid']
        need(len(value['rows']) == len(rows), 'Every query needs its first prediction')
        for output, row in zip(value['rows'], rows):
            need(type(output) is dict and set(output) == {'row_id', 'prediction'} and
                 type(output['row_id']) is int and output['row_id'] == row and
                 self.endpoint.finite_number(output['prediction']) and output['prediction'] >= 0,
                 'Original ordered query IDs and finite nonnegative ratios required')
        return {'schema': 'neural031_ordinary_prediction_v1', 'candidate_id': 'NEURAL-031',
                'fold': fold, 'view': view, 'input_manifest': self.item(fold, view)['manifest'],
                'rows': value['rows']}

    def capture(self, presentations, presentation_pin, response_path, response_pin, fold, view, output):
        receipt, observation = self.load_presentation(presentations, presentation_pin, fold, view)
        # Reserve the context before reading/validating the first supplied response.
        writer = self.io.Writer(output, 2 * RESPONSE_CAP + 32768)
        try:
            response = self.io.read(response_path, RESPONSE_CAP)
            writer.write('FIRST_RESPONSE.bin', response, RESPONSE_CAP)
            self.io.descriptor(response_pin, RESPONSE_CAP)
            need(pin(response) == response_pin, 'Operator-selected first response identity mismatch')
            prediction = self.prediction(response, observation, fold, view)
            writer.write('predictions.json', self.io.encoded(prediction), RESPONSE_CAP)
            captured = {'schema': 'neural031_numeric_capture_v1', 'condition': CONDITION,
                        'source_sha256': self.source_sha256, 'fold': fold, 'view': view,
                        'presentation': presentation_pin, 'observation': receipt['observation'],
                        'response': pin(response), 'prediction': writer.files['predictions.json'],
                        'status': 'valid_first_supplied_response', 'actual_provider_first_response_verified': False,
                        'fresh_model_context_verified': False, 'no_tools_enforced': False}
            writer.write('CAPTURE.json', self.io.encoded(captured), 16384)
            return {'capture': writer.files['CAPTURE.json'], 'written_bytes': writer.used}
        except (ValueError, OSError, TypeError, KeyError, OverflowError) as error:
            writer.write('FAILED.json', self.io.encoded({'status': 'failed_first_response',
                         'error_type': type(error).__name__}), 16384)
            raise

    def collect(self, support_path, presentations_root, captures_root, inventory_path, inventory_pin, output):
        inventory_body = self.io.read(inventory_path, 16384, inventory_pin)
        inventory = self.io.decode(inventory_body)
        need(type(inventory) is dict and set(inventory) == {'schema', 'condition', 'source_sha256', 'captures'} and
             inventory['schema'] == 'neural031_numeric_capture_inventory_v1' and
             inventory['condition'] == CONDITION and inventory['source_sha256'] == self.source_sha256 and
             type(inventory['captures']) is list and len(inventory['captures']) == 40,
             'Externally selected complete capture inventory required')
        for index, entry in enumerate(inventory['captures']):
            need(type(entry) is dict and set(entry) == {'fold', 'view', 'capture'} and
                 type(entry['fold']) is int and entry['fold'] == index // 2 and
                 entry['view'] == ('baseline', 'neural')[index % 2], 'Exact ordered capture inventory required')
            self.io.descriptor(entry['capture'], 16384)
        support = self.io.decode(self.io.read(support_path, 131072, self.source_inputs()['support']))
        self.endpoint.validate_support(support)
        roots = [Path(presentations_root), Path(captures_root)]
        for root in roots:
            need(root.is_dir() and not root.is_symlink() and
                 {p.name for p in root.iterdir()} == {f'fold{i:02d}' for i in range(20)},
                 'Exactly twenty complete folds required')
        outputs, captures = [], []
        for fold in range(20):
            for root in roots:
                directory = self.io.join(root, f'fold{fold:02d}')
                need(directory.is_dir() and {p.name for p in directory.iterdir()} == {'baseline', 'neural'},
                     'Exactly two physical views per fold required')
            for view in ('baseline', 'neural'):
                present_dir = self.io.join(roots[0], f'fold{fold:02d}/{view}')
                capture_dir = self.io.join(roots[1], f'fold{fold:02d}/{view}')
                need(present_dir.is_dir() and {p.name for p in present_dir.iterdir()} ==
                     {'OBSERVATION.json', 'PRESENTATION.json'} and capture_dir.is_dir() and
                     {p.name for p in capture_dir.iterdir()} ==
                     {'FIRST_RESPONSE.bin', 'predictions.json', 'CAPTURE.json'},
                     'Only complete presentation and first-response files admitted')
                selected = inventory['captures'][2 * fold + (view == 'neural')]['capture']
                capture_body = self.io.read(self.io.join(capture_dir, 'CAPTURE.json'), 16384, selected)
                c = self.io.decode(capture_body)
                need(type(c) is dict and set(c) == {'schema', 'condition', 'source_sha256', 'fold', 'view',
                     'presentation', 'observation', 'response', 'prediction', 'status',
                     'actual_provider_first_response_verified', 'fresh_model_context_verified', 'no_tools_enforced'} and
                     c['schema'] == 'neural031_numeric_capture_v1' and c['condition'] == CONDITION and
                     c['source_sha256'] == self.source_sha256 and type(c['fold']) is int and c['fold'] == fold and
                     c['view'] == view and c['status'] == 'valid_first_supplied_response' and
                     all(c[k] is False for k in ('actual_provider_first_response_verified',
                                                'fresh_model_context_verified', 'no_tools_enforced')),
                     'Exact local first-response capture required')
                receipt, observation = self.load_presentation(present_dir, c['presentation'], fold, view)
                need(c['observation'] == receipt['observation'], 'Captured observation identity changed')
                response = self.io.read(self.io.join(capture_dir, 'FIRST_RESPONSE.bin'), RESPONSE_CAP, c['response'])
                expected_prediction = self.prediction(response, observation, fold, view)
                prediction_body = self.io.read(self.io.join(capture_dir, 'predictions.json'), RESPONSE_CAP, c['prediction'])
                need(prediction_body == self.io.encoded(expected_prediction), 'Prediction must retain first supplied response')
                need(support['folds'][fold]['views'][view] ==
                     {k: self.item(fold, view)[k] for k in ('data', 'manifest')}, 'Original support and input pins must agree')
                outputs.append(expected_prediction)
                captures.append({'fold': fold, 'view': view, 'capture': pin(capture_body)})
        bundle = {'schema': 'neural031_ordinary_submission_bundle_v1', 'candidate_id': 'NEURAL-031', 'outputs': outputs}
        self.endpoint.validate_all(bundle, support)
        writer = self.io.Writer(output, 6553600)
        writer.write('submission.json', self.io.encoded(bundle), 6291456)
        writer.write('support.json', self.io.encoded(support), 131072)
        record = {'schema': 'neural031_numeric_collection_v1', 'condition': CONDITION,
                  'source_sha256': self.source_sha256, 'contexts': 40, 'predictions': 1548,
                  'capture_inventory': pin(inventory_body),
                  'information_views': ['baseline', 'neural'], 'captures': captures, 'files': dict(writer.files),
                  'private_targets_opened': 0, 'scores_computed': 0,
                  'actual_provider_first_responses_verified': False, 'fresh_model_contexts_verified': False,
                  'no_tools_enforced': False, 'scientific_qualification': False}
        writer.write('COLLECTION.json', self.io.encoded(record), 131072)
        return {'collection': writer.files['COLLECTION.json'], 'written_bytes': writer.used}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha256', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    present = sub.add_parser('present')
    present.add_argument('--input', required=True)
    capture = sub.add_parser('capture')
    capture.add_argument('--presentation', required=True)
    capture.add_argument('--presentation-bytes', required=True, type=int)
    capture.add_argument('--presentation-sha256', required=True)
    capture.add_argument('--response', required=True)
    capture.add_argument('--response-bytes', required=True, type=int)
    capture.add_argument('--response-sha256', required=True)
    for command in (present, capture):
        command.add_argument('--fold', required=True, type=int)
        command.add_argument('--view', required=True, choices=['baseline', 'neural'])
        command.add_argument('--output', required=True)
    collect = sub.add_parser('collect')
    collect.add_argument('--support', required=True)
    collect.add_argument('--presentations', required=True)
    collect.add_argument('--captures', required=True)
    collect.add_argument('--inventory', required=True)
    collect.add_argument('--inventory-bytes', required=True, type=int)
    collect.add_argument('--inventory-sha256', required=True)
    collect.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        engine = Engine(args.source_sha256)
        if args.command == 'present':
            result = engine.present(args.input, args.fold, args.view, args.output)
        elif args.command == 'capture':
            result = engine.capture(args.presentation, {'bytes': args.presentation_bytes, 'sha256': args.presentation_sha256},
                                    args.response, {'bytes': args.response_bytes, 'sha256': args.response_sha256},
                                    args.fold, args.view, args.output)
        else:
            result = engine.collect(args.support, args.presentations, args.captures, args.inventory,
                                    {'bytes': args.inventory_bytes, 'sha256': args.inventory_sha256}, args.output)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        print(json.dumps({'status': 'invalid', 'error_type': type(error).__name__, 'error': str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
