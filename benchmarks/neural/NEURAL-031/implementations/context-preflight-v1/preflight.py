"""Validate one participant's NEURAL-031 output using only its own public input.

This is schema/identity validation, not scoring, source-data authentication,
execution provenance or a replacement for the operator's full-panel collector.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types
import zipfile

HERE = Path(__file__).resolve().parent
DEPENDENCIES = {
    'runtime-qualification-v1/control.py':
        'ebc56e0e44a4d2dbcf609acc23ef37a02f1c31c29bb38a467a25bf71f00355cc',
    'ratio-scoring-v2/endpoint.py':
        '92a040819e8e9cc0e11d6c50ebcc05f5c838e42a9e2aaa16525ad3af14a44f92',
}
COMMON = ['baseline_volume', 'basal_indicator', 'local_missing', 'coincident_missing']
MANIFEST_KEYS = {'schema', 'candidate_id', 'fold', 'held_mouse', 'view', 'data',
                 'features', 'training_mouse_indices', 'train_rows', 'query_rows',
                 'training_target', 'query_target_or_followup_metadata',
                 'neural_activity_values_physically_present', 'prediction_time'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def read(path, cap):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= cap,
             'Bounded ordinary file required')
        body = stream.read(cap + 1)
        need(len(body) == info.st_size and len(body) <= cap, 'Complete bounded bytes required')
    return body


def decode(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON constant'))


def dependencies():
    # Private source staging can use the read-only checkout. This selects code,
    # never an input store; every selected source body must retain its public pin.
    source_root = os.environ.get('NEUROBENCH_SOURCE_ROOT')
    root = (Path(source_root) / 'benchmarks/neural/NEURAL-031/implementations'
            if source_root else HERE.parent)
    modules = []
    for index, (relative, digest) in enumerate(DEPENDENCIES.items()):
        body = read(root / relative, 65536)
        need(pin(body)['sha256'] == digest, 'Declared source dependency changed: ' + relative)
        module = types.ModuleType('_neural031_context_dependency_' + str(index))
        module.__file__ = str(root / relative)
        exec(compile(body, module.__file__, 'exec'), module.__dict__)
        modules.append(module)
    return tuple(modules)


def validate(data, manifest_body, submission_body):
    need(type(data) is bytes and 0 < len(data) <= 262144 and
         type(manifest_body) is bytes and 0 < len(manifest_body) <= 16384 and
         type(submission_body) is bytes and 0 < len(submission_body) <= 131072,
         'Original bounded context and submission bytes required')
    control, endpoint = dependencies()
    manifest = decode(manifest_body)
    need(type(manifest) is dict and set(manifest) == MANIFEST_KEYS and
         manifest['schema'] == 'neural031_ordinary_public_view_v1' and
         manifest['candidate_id'] == 'NEURAL-031' and
         type(manifest['fold']) is int and 0 <= manifest['fold'] < 20 and
         manifest['view'] in ('baseline', 'neural'), 'Original public context required')
    fold, view = manifest['fold'], manifest['view']
    need(manifest['held_mouse'] == endpoint.MICE[fold] and
         type(manifest['training_mouse_indices']) is list and
         all(type(item) is int for item in manifest['training_mouse_indices']) and
         manifest['training_mouse_indices'] == [i for i in range(20) if i != fold] and
         type(manifest['query_rows']) is int and 0 < manifest['query_rows'] <= 774 and
         type(manifest['train_rows']) is int and
         manifest['train_rows'] == 774 - manifest['query_rows'] > 0 and
         manifest['features'] == COMMON + (
             ['local_coactivity_norm', 'dendrite_coincident_norm'] if view == 'neural' else []) and
         manifest['training_target'] == 'next_day_ratio_with_NaN_unavailable' and
         manifest['query_target_or_followup_metadata'] is False and
         manifest['neural_activity_values_physically_present'] is (view == 'neural') and
         manifest['prediction_time'] == 'after_complete_Early_recording_for_next_day_size',
         'Original fold, physical view, complete support and target semantics required')
    expected = manifest['data']
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'} and
         type(expected['bytes']) is int and type(expected['sha256']) is str and
         expected == pin(data), 'Manifest must bind the exact supplied archive')
    # This existing decoder opens only query_rowid.npy. It does not decode
    # features or training labels; runtime_probe() and predict() are never called.
    rows = control.query_ids(data, manifest['query_rows'])
    value = decode(submission_body)
    need(type(value) is dict and set(value) ==
         {'schema', 'candidate_id', 'fold', 'view', 'input_manifest', 'rows'} and
         value['schema'] == 'neural031_ordinary_prediction_v1' and
         value['candidate_id'] == 'NEURAL-031' and type(value['fold']) is int and
         value['fold'] == fold and value['view'] == view and
         type(value['input_manifest']) is dict and
         set(value['input_manifest']) == {'bytes', 'sha256'} and
         type(value['input_manifest']['bytes']) is int and
         type(value['input_manifest']['sha256']) is str and
         value['input_manifest'] == pin(manifest_body) and
         type(value['rows']) is list and len(value['rows']) == len(rows),
         'One complete output bound to this exact context required')
    for item, row in zip(value['rows'], rows):
        need(type(item) is dict and set(item) == {'row_id', 'prediction'} and
             type(item['row_id']) is int and item['row_id'] == row and
             endpoint.finite_number(item['prediction']) and item['prediction'] >= 0,
             'All query rows in order with finite nonnegative ratio predictions required')
    return {'schema': 'neural031_context_preflight_v1', 'candidate_id': 'NEURAL-031',
            'status': 'valid_single_context_submission', 'fold': fold, 'view': view,
            'request_rows': len(rows),
            'inputs': {'data': pin(data), 'manifest': pin(manifest_body),
                       'submission': pin(submission_body)},
            'array_members_decoded': ['query_rowid.npy'], 'private_targets_opened': 0,
            'other_contexts_opened': 0, 'score_computed': False,
            'scientific_qualification': False,
            'scope': 'schema_and_supplied_identity_only; original_input_authenticity_and_full_panel_custody_require_operator'}


def run(data_path, manifest_path, submission_path):
    return validate(read(data_path, 262144), read(manifest_path, 16384),
                    read(submission_path, 131072))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--submission', required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.input, args.manifest, args.submission)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (ValueError, OSError, KeyError, TypeError, OverflowError, EOFError,
            zipfile.BadZipFile) as error:
        print(json.dumps({'status': 'invalid', 'error_type': type(error).__name__,
                          'error': str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
