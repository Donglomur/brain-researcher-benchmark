"""Admit the original, already projected physical views. No new extraction."""
import io
from pathlib import Path
import stat
import numpy as np
from common import ARMS, CASES, CLASSES, HERE, decode, file_mount, need, ordinary, read


def arrays(body, keys):
    with np.load(io.BytesIO(body), allow_pickle=False, max_header_size=4096) as values:
        need(set(values.files) == set(keys), 'Exact view array inventory')
        return {key: values[key] for key in keys}


def validate_pair(left, right, case):
    count = CASES[case]
    expected_ids = np.asarray([f'{case}/{i:05d}' for i in range(count)], dtype='<U21')
    for arm, values, width in zip(ARMS, (left, right), (15, 21)):
        ids, matrix = values['epoch_id'], values['X']
        need(ids.shape == (count,) and ids.dtype == np.dtype('<U21') and ids.flags.c_contiguous
             and np.array_equal(ids, expected_ids),
             'Complete original chronological epoch roster')
        need(matrix.shape == (count, width) and matrix.dtype == np.dtype('<f8')
             and matrix.flags.c_contiguous and np.isfinite(matrix).all(), 'Finite exact arm geometry')
    shared = np.ascontiguousarray(right['X'][:, [*range(12), 18, 19, 20]])
    need(left['X'].tobytes() == shared.tobytes(), 'Bit-identical shared EEG and clock columns')


def admit(root, bindings=None):
    """Operator-only: reads public features/labels, never development targets.

    The CLI always uses committed historical bindings. The optional argument is
    for generated controls, not an alternative authentic input registration.
    """
    root = ordinary(root)
    bindings = bindings if bindings is not None else decode(read(HERE / 'INPUTS.json', 32768))
    need(set(bindings) == set(ARMS), 'Exactly the original paired arms')
    mounted, bodies = {}, {}
    expected_names = ({case + '_features.npz' for case in CASES}
                      | {case + '_labels.npz' for case in CASES if case.startswith('train-')}
                      | {'manifest.json'})
    for arm in ARMS:
        need(len(bindings[arm]) == 15, 'Fifteen physical files per arm')
        mounted[arm], bodies[arm] = {}, {}
        for row in bindings[arm]:
            need(set(row) == {'path', 'bytes', 'sha256', 'mount_destination', 'read_only'}
                 and row['read_only'] is True, 'Exact readonly input descriptor')
            relative = Path(row['path'])
            need(not relative.is_absolute() and '..' not in relative.parts, 'Relative input locator')
            path, target = ordinary(root / relative), row['mount_destination']
            need(target.startswith('/input/') and target[7:] in expected_names
                 and target not in mounted[arm], 'Exact unique participant input path')
            need(not stat.S_IMODE(path.stat().st_mode) & 0o222, 'Readonly physical public file')
            identity = {k: row[k] for k in ('bytes', 'sha256')}
            bodies[arm][target[7:]] = read(path, 1048576, identity)
            mounted[arm][target] = file_mount(path, identity)
        need(set(bodies[arm]) == expected_names, 'No raw signals, caches, development labels or missing inputs')
        manifest = decode(bodies[arm]['manifest.json'])
        need(set(manifest) == {'arm', 'classes', 'development', 'feature_count', 'files', 'training'}
             and manifest['arm'] == arm and manifest['classes'] == CLASSES
             and manifest['feature_count'] == (15 if arm == ARMS[0] else 21), 'Exact participant arm manifest')
        for role, prefix in (('training', 'train-'), ('development', 'development-')):
            need(manifest[role] == [{'case_id': k, 'epochs': n} for k, n in CASES.items() if k.startswith(prefix)],
                 'Complete original training/development membership')
        entries = {row['filename']: row for row in manifest['files']}
        need(len(entries) == len(manifest['files']) == 14 and set(entries) == expected_names - {'manifest.json'},
             'Exact public manifest membership')
        for name, row in entries.items():
            case = name.removesuffix('_features.npz').removesuffix('_labels.npz')
            role = ('training_labels' if name.endswith('_labels.npz') else
                    'training_features' if case.startswith('train-') else 'development_features')
            expected = next(iter(mounted[arm]['/input/' + name]['files'].values()))
            need(row == {'filename': name, **expected, 'case_id': case, 'role': role}, 'Manifest joins physical files')
    scored = 0
    for case, count in CASES.items():
        pair = [arrays(bodies[arm][case + '_features.npz'], ('epoch_id', 'X')) for arm in ARMS]
        validate_pair(*pair, case)
        if case.startswith('train-'):
            name = case + '_labels.npz'
            need(bodies[ARMS[0]][name] == bodies[ARMS[1]][name], 'Identical public training supervision')
            labels = arrays(bodies[ARMS[0]][name], ('epoch_id', 'stage', 'score_mask'))
            stage, mask = labels['stage'], labels['score_mask']
            need(np.array_equal(labels['epoch_id'], pair[0]['epoch_id']) and stage.shape == mask.shape == (count,)
                 and stage.dtype.kind in 'iu' and mask.dtype == np.dtype(bool)
                 and np.all((stage[mask] >= 0) & (stage[mask] < 5)), 'Aligned original training supervision')
            scored += int(mask.sum())
    need(scored == 16211, 'Original 16290 training epochs, 16211 scored and 79 masked')
    return mounted
