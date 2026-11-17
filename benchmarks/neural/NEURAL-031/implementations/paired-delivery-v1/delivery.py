#!/usr/bin/env python3
"""Original full paired projection, one-context export and target-free collection.

Operator utilities only. They never execute a submitted program and never open
private target files. A separate qualified runner must enforce fresh contexts.
"""
import argparse
from pathlib import Path
import sys
import types

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from io031 import archive, arrays, decode, descriptor, encoded, join, need, pin, read, Writer
from projection031 import (COMMON_FEATURES, NEURAL_FEATURES, KEYS, VIEWS,
                           check_all_folds, original_packet, physical_view, validate_views)


def endpoint():
    """Use the already accepted scientific endpoint, authenticated before import."""
    source = decode(read(HERE / 'SOURCES.json', 16384))['endpoint']
    need(source['relative'] == '../ratio-scoring-v1/endpoint.py', 'Fixed scorer dependency')
    path = HERE.parent / 'ratio-scoring-v1/endpoint.py'
    body = read(path, 65536, {k: source[k] for k in ('bytes', 'sha256')})
    module = types.ModuleType('_neural031_ratio_endpoint')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def inputs():
    return validate_inputs(decode(read(HERE / 'SOURCE_INPUTS.json', 65536)))


def validate_inputs(value):
    need(type(value) is dict and set(value) == {'schema', 'candidate_id',
         'original_sealed_manifest_sha256', 'paired_sealed_manifest_sha256',
         'original_folds', 'paired_views', 'support'} and
         value['schema'] == 'neural031_paired_delivery_source_inputs_v1' and
         value['candidate_id'] == 'NEURAL-031', 'Exact source identity document')
    for key in ('original_sealed_manifest_sha256', 'paired_sealed_manifest_sha256'):
        descriptor({'bytes': 1, 'sha256': value[key]}, 1)
    need(type(value['original_folds']) is list and len(value['original_folds']) == 20 and
         type(value['paired_views']) is list and len(value['paired_views']) == 40,
         'All twenty original folds and forty paired views')
    for index, item in enumerate(value['original_folds']):
        need(type(item) is dict and set(item) == {'fold', 'data', 'manifest'} and
             type(item['fold']) is int and item['fold'] == index, 'Ordered original fold')
        descriptor(item['data'], 262144); descriptor(item['manifest'], 16384)
    for index, item in enumerate(value['paired_views']):
        need(type(item) is dict and set(item) == {'fold', 'view', 'data', 'manifest'} and
             type(item['fold']) is int and item['fold'] == index // 2 and
             item['view'] == VIEWS[index % 2], 'Ordered paired context')
        descriptor(item['data'], 262144); descriptor(item['manifest'], 16384)
    descriptor(value['support'], 131072)
    return value


def public_manifest(fold, view, packet, data_pin, mice):
    return {'schema': 'neural031_ordinary_public_view_v1', 'candidate_id': 'NEURAL-031',
            'fold': fold, 'held_mouse': mice[fold], 'view': view, 'data': data_pin,
            'features': list(COMMON_FEATURES if view == 'baseline' else NEURAL_FEATURES),
            'training_mouse_indices': [i for i in range(20) if i != fold],
            'train_rows': len(packet['train_x']), 'query_rows': len(packet['query_x']),
            'training_target': 'next_day_ratio_with_NaN_unavailable',
            'query_target_or_followup_metadata': False,
            'neural_activity_values_physically_present': view == 'neural',
            'prediction_time': 'after_complete_Early_recording_for_next_day_size'}


def project_packets(np, packets, manifests):
    """Pure original preparation seam; all twenty inputs must be operator-only."""
    ep = endpoint()
    need(len(packets) == len(manifests) == 20, 'No partial-panel projection')
    for fold in range(20):
        original_packet(np, packets[fold], manifests[fold], fold, ep.MICE)
    rows = check_all_folds(np, packets)
    need(sum(map(len, rows)) == ep.REQUEST_ROWS, 'All 774 original baseline requests')
    files, folds = {}, []
    for fold, packet in enumerate(packets):
        paired = {view: physical_view(np, packet, view) for view in VIEWS}
        validate_views(np, packet, paired['baseline'], paired['neural'])
        item = {'fold': fold, 'rowids': rows[fold], 'views': {}}
        for view in VIEWS:
            prefix = f'public/fold{fold:02d}/{view}/'
            data = archive(np, paired[view])
            manifest = encoded(public_manifest(fold, view, paired[view], pin(data), ep.MICE))
            files[prefix + 'data.npz'] = data
            files[prefix + 'manifest.json'] = manifest
            item['views'][view] = {'data': pin(data), 'manifest': pin(manifest)}
        folds.append(item)
    support = {'schema': 'neural031_ordinary_public_support_v1', 'candidate_id': 'NEURAL-031',
               'folds': folds, 'request_rows': ep.REQUEST_ROWS, 'query_targets_included': False}
    ep.validate_support(support)
    files['support.json'] = encoded(support)
    return files


def prepare(original_root, output, source=None):
    """Rebuild exact retained views; no output is written before all pins match."""
    import numpy as np
    source = inputs() if source is None else validate_inputs(source)
    packets, manifests = [], []
    for item in source['original_folds']:
        prefix = f"public/fold{item['fold']:02d}/"
        manifest = decode(read(join(original_root, prefix + 'manifest.json'), 16384, item['manifest']))
        need(manifest['data'] == item['data'], 'Original manifest and admitted archive agree')
        body = read(join(original_root, prefix + 'data.npz'), 262144, item['data'])
        packets.append(arrays(np, body, KEYS)); manifests.append(manifest)
    files = project_packets(np, packets, manifests)
    for item in source['paired_views']:
        prefix = f"public/fold{item['fold']:02d}/{item['view']}/"
        for key, name in (('data', 'data.npz'), ('manifest', 'manifest.json')):
            need(pin(files[prefix + name]) == item[key], 'Exact retained paired representation')
    need(pin(files['support.json']) == source['support'], 'Exact retained support and row identities')
    writer = Writer(output, 16777216)
    for name, body in files.items():
        writer.write(name, body, 131072 if name == 'support.json' else
                     (262144 if name.endswith('.npz') else 16384))
    return {'schema': 'neural031_paired_preparation_receipt_v1', 'contexts': 40,
            'request_rows': 774, 'support': source['support'], 'written_bytes': writer.used,
            'participant_programs_executed': 0, 'private_targets_opened': 0,
            'status': 'exact_pinned_public_views_prepared'}


def load_support(store_root, source):
    support = decode(read(join(store_root, 'support.json'), 131072, source['support']))
    endpoint().validate_support(support)
    for item in source['paired_views']:
        need(support['folds'][item['fold']]['views'][item['view']] ==
             {k: item[k] for k in ('data', 'manifest')}, 'Pinned views and support agree')
    return support


def export_context(store_root, output, fold, view, source=None):
    """Copy only two pinned files into a fresh participant input directory.

    Do not mount the operator store, support file or any other fold. This copy
    is an input projection; a filesystem copy alone does not isolate a program.
    """
    need(type(fold) is int and 0 <= fold < 20 and view in VIEWS, 'One declared context')
    source = inputs() if source is None else validate_inputs(source)
    support = load_support(store_root, source)
    item = source['paired_views'][2 * fold + VIEWS.index(view)]
    prefix = f'public/fold{fold:02d}/{view}/'
    manifest_body = read(join(store_root, prefix + 'manifest.json'), 16384, item['manifest'])
    data_body = read(join(store_root, prefix + 'data.npz'), 262144, item['data'])
    manifest = decode(manifest_body)
    need(manifest['schema'] == 'neural031_ordinary_public_view_v1' and
         manifest['candidate_id'] == 'NEURAL-031' and manifest['fold'] == fold and
         manifest['view'] == view and manifest['data'] == item['data'] and
         manifest['query_rows'] == len(support['folds'][fold]['rowids']) and
         manifest['query_target_or_followup_metadata'] is False,
         'Current paired context and query support')
    writer = Writer(output, 278528)
    writer.write('data.npz', data_body, 262144)
    writer.write('manifest.json', manifest_body, 16384)
    return {'schema': 'neural031_context_export_receipt_v1', 'fold': fold, 'view': view,
            'files': writer.files, 'written_bytes': writer.used,
            'isolation_enforced': False, 'participant_programs_executed': 0}


def collect(store_root, predictions_root, output, source=None):
    """Exact forty-file collection, before the unchanged scorer opens targets."""
    source = inputs() if source is None else validate_inputs(source)
    support = load_support(store_root, source)
    root = Path(predictions_root)
    need(root.is_dir() and not root.is_symlink() and
         {p.name for p in root.iterdir()} == {f'fold{i:02d}' for i in range(20)},
         'Exactly twenty output folds; no omitted or extra context')
    outputs = []
    for fold in range(20):
        directory = join(root, f'fold{fold:02d}')
        need(directory.is_dir() and {p.name for p in directory.iterdir()} == set(VIEWS),
             'Exactly two output views for every mouse')
        for view in VIEWS:
            directory = join(root, f'fold{fold:02d}/{view}')
            need(directory.is_dir() and {p.name for p in directory.iterdir()} == {'predictions.json'},
                 'One complete prediction file per context')
            outputs.append(decode(read(join(directory, 'predictions.json'), 131072)))
    bundle = {'schema': 'neural031_ordinary_submission_bundle_v1',
              'candidate_id': 'NEURAL-031', 'outputs': outputs}
    endpoint().validate_all(bundle, support)
    # No target path is accepted by this tool. All malformed outputs fail above.
    writer = Writer(output, 6422528)
    writer.write('submission.json', encoded(bundle), 6291456)
    writer.write('support.json', encoded(support), 131072)
    return {'schema': 'neural031_complete_collection_receipt_v1', 'contexts': 40,
            'predictions': 1548, 'files': writer.files, 'written_bytes': writer.used,
            'private_targets_opened': 0, 'execution_provenance_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare_p = sub.add_parser('prepare')
    prepare_p.add_argument('--original-root', required=True)
    prepare_p.add_argument('--output', required=True)
    export_p = sub.add_parser('export')
    export_p.add_argument('--store-root', required=True)
    export_p.add_argument('--output', required=True)
    export_p.add_argument('--fold', required=True, type=int)
    export_p.add_argument('--view', required=True, choices=VIEWS)
    collect_p = sub.add_parser('collect')
    collect_p.add_argument('--store-root', required=True)
    collect_p.add_argument('--predictions-root', required=True)
    collect_p.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.original_root, args.output)
    elif args.command == 'export':
        result = export_context(args.store_root, args.output, args.fold, args.view)
    else:
        result = collect(args.store_root, args.predictions_root, args.output)
    print(encoded(result).decode(), end='')


if __name__ == '__main__':
    main()
