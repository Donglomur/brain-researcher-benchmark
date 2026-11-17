"""Metadata lineage and operator-only export from actual official loaders.

No native dependency is imported until export_observations is invoked. Metadata
controls never call CustomDataset.__getitem__, decode a sample or inspect gold.
"""
import hashlib
import json
import os
from pathlib import Path
import re

PRIMARY = ('FACED', 'SEED-V', 'PhysioNet-MI', 'SHU-MI', 'ISRUC', 'CHB-MIT',
           'BCIC2020-3', 'Mumtaz2016', 'SEED-VIG', 'MentalArithmetic', 'TUEV', 'TUAB')
LMDB = {'FACED', 'SEED-V', 'PhysioNet-MI', 'SHU-MI', 'BCIC2020-3',
        'Mumtaz2016', 'SEED-VIG', 'MentalArithmetic', 'BCIC-IV-2a'}
SHAPES = {'FACED': (32, 10, 200), 'SEED-V': (62, 1, 200), 'PhysioNet-MI': (64, 4, 200),
          'SHU-MI': (32, 4, 200), 'ISRUC': (20, 6, 6000), 'CHB-MIT': (16, 10, 200),
          'BCIC2020-3': (64, 3, 200), 'Mumtaz2016': (19, 5, 200), 'SEED-VIG': (17, 8, 200),
          'MentalArithmetic': (20, 5, 200), 'TUEV': (16, 5, 200), 'TUAB': (16, 10, 200),
          'BCIC-IV-2a': (22, 4, 200)}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def _text(value):
    if not isinstance(value, str) or not value or len(value.encode()) > 4096 or any(c in value for c in ('\0', '\n', '\r')):
        raise ValueError('nonempty bounded source identity required')
    return value


def _relative(value):
    value = _text(value)
    p = Path(value)
    if p.is_absolute() or '..' in p.parts or str(p) != value:
        raise ValueError('source keys must be normalized relative names')
    return value


def row_lineage(dataset_id, split, source_keys, group_by_key):
    """Bind exact loader order; ISRUC yields20 rows while keeping each sequence.

    group_by_key is a complete, explicit prequalified identity join; this function
    validates the join structurally but never invents or qualifies person IDs.
    Paired sleep filenames must already match: the official unsorted zip is not
    silently sorted or repaired by the benchmark adapter.
    """
    if dataset_id not in SHAPES or split not in ('train', 'val', 'test'):
        raise ValueError('dataset/split not declared')
    if not isinstance(source_keys, list) or not source_keys or len(source_keys) > 1000000 or not isinstance(group_by_key, dict):
        raise ValueError('explicit nonempty complete source order required')
    keys = []
    seen = set()
    rows = []
    for ordinal, original in enumerate(source_keys):
        if dataset_id == 'ISRUC':
            if not isinstance(original, (list, tuple)) or len(original) != 2:
                raise ValueError('ISRUC needs sequence/label path pairs')
            key, label = map(_relative, original)
            if not key.startswith('seq/') or not label.startswith('labels/'):
                raise ValueError('ISRUC role path mismatch')
            if key.removeprefix('seq/') != label.removeprefix('labels/'):
                raise ValueError('official unsorted ISRUC sequence/label pairing is inconsistent')
            if not re.fullmatch(r'seq/ISRUC-group1-[0-9]+/ISRUC-group1-[0-9]+-[0-9]+\.npy', key):
                raise ValueError('ISRUC source sequence key malformed')
            n = key.split('/')[1].removeprefix('ISRUC-group1-')
            if not Path(key).name.startswith('ISRUC-group1-' + n + '-'):
                raise ValueError('ISRUC night/path identity mismatch')
            epochs = range(20)
        else:
            key = _relative(original)
            epochs = (None,)
        if key in seen:
            raise ValueError('duplicate source sample key')
        keys.append(key)
        seen.add(key)
        if key not in group_by_key:
            raise ValueError('source key lacks explicit person/group join')
        group = _text(group_by_key[key])
        for epoch in epochs:
            identity = {'dataset_id': dataset_id, 'split': split, 'source_key': key, 'epoch_index': epoch}
            row = {'id': digest(identity), 'group': group, 'source_key': key,
                   'source_ordinal': ordinal, 'epoch_index': epoch}
            if dataset_id == 'ISRUC':
                row['label_key'] = label
                row['sequence_key'] = key
            rows.append(row)
    if set(group_by_key) != set(keys):
        raise ValueError('person/group join must cover exactly the selected source keys')
    result = {'schema': 'cbramod_observation_lineage_v1', 'dataset_id': dataset_id, 'split': split,
              'source_keys': source_keys, 'group_by_key': group_by_key, 'rows': rows,
              'loader_sample_shape': list(SHAPES[dataset_id]), 'loader_units': 'official loader signal divided by100',
              'source_identity_qualified': False, 'metadata_construction_reads_targets': False}
    result['lineage_sha256'] = digest(result)
    return result


def observe_loaded_dataset(dataset_id, split, dataset, prepared_root, group_by_key):
    """Extract actual loader metadata in its existing order, without sample reads."""
    root = Path(prepared_root)
    if not root.is_absolute() or '..' in root.parts:
        raise ValueError('explicit absolute prepared root required')
    if dataset_id in LMDB:
        source_keys = list(dataset.keys)
    elif dataset_id == 'ISRUC':
        source_keys = [[str(Path(s).relative_to(root)), str(Path(l).relative_to(root))]
                       for s, l in dataset.seqs_labels_path_pair]
    elif dataset_id == 'TUEV':
        source_keys = list(dataset.files)
        if any(Path(k).is_absolute() for k in source_keys):
            raise ValueError('TUEV source loader uses relative filenames')
    elif dataset_id in ('CHB-MIT', 'TUAB'):
        source_keys = [str(Path(p).relative_to(root / split)) for p in dataset.files]
    else:
        raise ValueError('unknown source loader')
    return row_lineage(dataset_id, split, source_keys, group_by_key)


def training_descriptor(lineage, prepared_root, source_commit, official_manifest_sha256, inputs_root):
    """Emit train/validation-only actual-loader join for the native bridge."""
    if lineage['split'] not in ('train', 'val'):
        raise ValueError('test targets are not training bridge inputs')
    expected = row_lineage(lineage['dataset_id'], lineage['split'], lineage['source_keys'], lineage['group_by_key'])
    if expected != lineage:
        raise ValueError('lineage metadata identity mismatch')
    relative = _relative(prepared_root)
    if relative == '.':
        raise ValueError('prepared root must name a child input owner')
    root = Path(inputs_root)
    if not root.is_absolute() or '..' in root.parts or str(root) != str(inputs_root):
        raise ValueError('explicit normalized inputs owner required')
    if not re.fullmatch('[a-f0-9]{40}', source_commit) or not re.fullmatch('[a-f0-9]{64}', official_manifest_sha256):
        raise ValueError('exact source commit/manifest identities required')
    return {'schema': 'cbramod_training_split_v1', 'dataset_id': lineage['dataset_id'], 'split': lineage['split'],
            'prepared_root': relative, 'source_keys': lineage['source_keys'], 'group_by_key': lineage['group_by_key'],
            'lineage_sha256': lineage['lineage_sha256'], 'source_commit': source_commit,
            'official_manifest_sha256': official_manifest_sha256}


def export_observations_aggregate(dataset_id, split, dataset, prepared_root, group_by_key,
                                  output_dir, maximum_sample_bytes, maximum_total_bytes,
                                  maximum_metadata_bytes, execution):
    """Actual official loader→one C-order<float32 target-free observation bank.

    Invoked only by future native operator preparation. Complete output and one
    source-shaped float64→float32/finite scratch are admitted before native
    import or sample decode; authentic loader allocation/header admission is a
    separate caller obligation. The20-epoch ISRUC axis remains intact. Actual
    official loader __getitem__ performs all original EEG transformations.
    """
    if execution != 'native_operator_preparation':
        raise ValueError('signal export is native operator preparation only')
    allocations = (maximum_sample_bytes, maximum_total_bytes, maximum_metadata_bytes)
    if any(type(v) is not int or v <= 0 for v in allocations) or maximum_metadata_bytes > maximum_total_bytes:
        raise ValueError('explicit positive sample, total and metadata allocations required')
    from benchmark.native.owners import admit_owners
    if not Path(prepared_root).is_absolute() or not Path(output_dir).is_absolute():
        raise ValueError('explicit absolute observation owners required')
    roots = admit_owners({'prepared': prepared_root}, {'output': output_dir})
    prepared_root, out = roots['prepared'], roots['output']
    lineage = observe_loaded_dataset(dataset_id, split, dataset, prepared_root, group_by_key)
    shape = SHAPES[dataset_id]
    count = len(lineage['source_keys'])
    elements = 1
    for size in shape:
        elements *= size
    maximum_file = count * elements * 4 + 1024
    if elements * 13 > maximum_sample_bytes or maximum_file + maximum_metadata_bytes > maximum_total_bytes:
        raise ValueError('complete observation bank or sample scratch exceeds allocation')
    descriptor = {'path': 'observations.npy', 'shape': [count, *shape], 'dtype': '<f4',
                  'bytes': maximum_file, 'sha256': 'f' * 64, 'fortran_order': False}
    projected = {'schema': 'cbramod_target_free_observations_v2', 'dataset_id': dataset_id,
                 'split': split, 'lineage': lineage, 'signal_file': descriptor,
                 'contains_target_labels': False, 'source_parity_qualified': False}
    if len(json.dumps(projected, sort_keys=True, indent=2).encode()) + 1 > maximum_metadata_bytes:
        raise ValueError('complete observation lineage/receipt exceeds metadata allocation')
    import numpy as np
    out.mkdir(mode=0o700, parents=False, exist_ok=False)
    destination = out / descriptor['path']
    bank = np.lib.format.open_memmap(destination, mode='w+', dtype=np.dtype('<f4'),
                                     shape=tuple(descriptor['shape']), fortran_order=False)
    try:
        for index in range(count):
            pair = dataset[index]
            array = np.asarray(pair[0])
            if tuple(array.shape) != shape or array.dtype.kind != 'f' or array.dtype.itemsize not in (4, 8) or not np.isfinite(array).all():
                raise ValueError('official loader signal violates declared observation shape/type')
            cast = np.ascontiguousarray(array, dtype=np.dtype('<f4'))
            if not np.isfinite(cast).all():
                raise ValueError('float32 observation conversion is nonfinite')
            bank[index] = cast
            del pair, array, cast
        bank.flush()
    finally:
        # Close the mapping before the receipt captures its final bytes.
        bank._mmap.close()
        del bank
    size = destination.stat().st_size
    if size > maximum_file:
        raise ValueError('NPY serialization exceeded admitted file extent')
    h = hashlib.sha256()
    with open(destination, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    descriptor['bytes'] = size
    descriptor['sha256'] = h.hexdigest()
    receipt = json.dumps(projected, sort_keys=True, indent=2).encode() + b'\n'
    if len(receipt) > maximum_metadata_bytes or size + len(receipt) > maximum_total_bytes:
        raise ValueError('complete observation receipt exceeded its admitted allocation')
    with open(out / 'OBSERVATIONS.json', 'xb') as f:
        f.write(receipt)
    return projected


# One operative export route; the previous unjoined per-sample draft is retained
# only in the authoring preimage, not selectable as an alternate data protocol.
export_observations = export_observations_aggregate
