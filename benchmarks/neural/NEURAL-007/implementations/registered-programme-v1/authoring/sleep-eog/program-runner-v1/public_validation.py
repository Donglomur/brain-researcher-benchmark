"""Optional public training/case join checks; no fits or private inputs."""
import io
import math
from pathlib import Path
import stat
import zipfile
import numpy as np

CHANNELS = ('EEG Fpz-Cz', 'EEG Pz-Oz', 'EOG horizontal')
FEATURES = ('delta_mean_relative', 'theta_mean_relative', 'alpha_mean_relative',
            'sigma_mean_relative', 'beta_mean_relative', 'log_variance_volts2')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load_public(path, lock, case_id, n, labels=False):
    # The same frozen bounded cache reader handles file/hash identity. Header
    # validation here adds feature/label geometry before any payload allocation.
    import cache_io
    body = cache_io.locked_bytes(path, lock)
    layout = {'epoch_id': ((n,), 'U')}
    if labels:
        layout.update(stage=((n,), 'iu'), score_mask=((n,), 'b'))
    else:
        layout.update(epoch_start_seconds=((n,), 'f'), clock_features=((n, 3), 'f'),
                      signal_features=((n, 3, 6), 'f'), channels=((3,), 'U'),
                      feature_names=((6,), 'U'), sample_rate_hz=((), 'iu'), epoch_seconds=((), 'iu'))
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        entries = archive.infolist()
        need(len(entries) == len(layout) and {e.filename for e in entries} ==
             {k + '.npy' for k in layout} and not archive.comment, 'Exact public NPZ inventory')
        need(sum(e.file_size for e in entries) <= 2_000_000, 'Bounded public arrays')
        for entry in entries:
            need(not entry.is_dir() and not entry.flag_bits & 1 and entry.compress_type == zipfile.ZIP_STORED and
                 entry.file_size == entry.compress_size and not stat.S_ISLNK(entry.external_attr >> 16), 'Ordinary stored NPY')
            with archive.open(entry) as stream:
                version = np.lib.format.read_magic(stream)
                need(version in ((1, 0), (2, 0)), 'Supported NPY version')
                reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
                shape, order, dtype = reader(stream, max_header_size=4096)
                expected_shape, kind = layout[entry.filename[:-4]]
                need(shape == expected_shape and type(order) is bool and not dtype.hasobject and dtype.fields is None and
                     dtype.kind in kind and 0 < dtype.itemsize <= (512 if kind == 'U' else 8), 'Exact bounded public geometry/type')
                need(stream.tell() + math.prod(shape) * dtype.itemsize == entry.file_size, 'Exact NPY length')
        with np.load(io.BytesIO(body), allow_pickle=False, max_header_size=4096) as source:
            values = {key: source[key] for key in layout}
    ids = np.asarray([case_id + '/' + f'{i:05d}' for i in range(n)])
    need(np.array_equal(values['epoch_id'], ids), 'Canonical full-clock public IDs')
    if labels:
        y, mask = values['stage'], values['score_mask']
        need(mask.dtype == np.dtype(bool) and np.isin(y, [-1, 0, 1, 2, 3, 4]).all() and
             np.array_equal(mask, y >= 0) and mask.any(), 'Public training stage/mask relation')
    else:
        need(all(np.isfinite(values[k]).all() for k in ('signal_features', 'clock_features', 'epoch_start_seconds')),
             'Finite public features')
        need(np.array_equal(values['channels'], CHANNELS) and np.array_equal(values['feature_names'], FEATURES),
             'Exact channel/feature axes')
        need(np.array_equal(values['epoch_start_seconds'], np.arange(n) * 30) and
             int(values['sample_rate_hz']) == 100 and int(values['epoch_seconds']) == 30, 'Full clock/rate')
        clock = values['clock_features']
        need(np.array_equal(clock[:, 0], np.arange(n) * 30 / 3600) and
             np.allclose(np.sum(clock[:, 1:] ** 2, axis=1), 1, atol=1e-12, rtol=0), 'Clock feature geometry')
    return values


def validate_manifest(manifest):
    import cache_io
    rows = manifest['training_files']
    cases = sorted({r['case_id'] for r in rows})
    need(cases == [f'train-{i:03d}' for i in range(1, 7)] and len(rows) == 18, 'All six training cases')
    counts = []
    for case_id in cases:
        items = {r['role']: r for r in rows if r['case_id'] == case_id}
        need(set(items) == {'training_labels', 'training_features', 'common_model'}, 'Three roles per training person')
        n = items['training_labels']['epochs']
        need(all(r['epochs'] == n for r in items.values()), 'Training count join')
        lock = lambda row: {k: row[k] for k in ('bytes', 'sha256')}
        labels = load_public(Path(items['training_labels']['mount_destination']), lock(items['training_labels']), case_id, n, True)
        features = load_public(Path(items['training_features']['mount_destination']), lock(items['training_features']), case_id, n)
        cache = cache_io.load_cache(Path(items['common_model']['mount_destination']), lock(items['common_model']), case_id, n)
        need(np.array_equal(labels['epoch_id'], features['epoch_id']) and
             np.array_equal(labels['epoch_id'], cache['epoch_id']), 'Complete three-way training identity join')
        counts.append(n)
    need(counts == [2630, 2740, 2690, 2740, 2740, 2750], 'Frozen six-person epoch counts')
    active = {r['role']: r for r in manifest['active_files']}
    case_id, n = manifest['case_id'], manifest['epochs']
    features = load_public('/input/features.npz', lock(active['development_features']), case_id, n)
    cache = cache_io.load_cache('/input/model.npz', lock(active['development_common_model_outputs']), case_id, n)
    need(np.array_equal(features['epoch_id'], cache['epoch_id']), 'Active-case feature/model join')
    return cache, {'training_people': 6, 'training_full_epochs': sum(counts), 'active_case': case_id,
                   'active_epochs': n, 'three_way_training_join_checked': True, 'fits': 0}
