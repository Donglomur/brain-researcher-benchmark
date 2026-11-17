"""Complete original MindBridge Table 2 metric panel on operator-produced payloads.

This source-only component does not generate images, authenticate model exposure,
or decide scientific reproduction/improvement. Its source-aware selection accesses
true target features and must remain operator-only after generation is frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

import numpy as np

TASK = 'PAPER-paper-method-033'
SCHEMA = 'mindbridge-original-panel/v1'
ARMS = ('vanilla', 'mindbridge')
BUDGETS = (500, 1500, 4000)
FEATURES = ('alexnet2', 'alexnet5', 'inception', 'clip', 'effnet_b', 'swav')
METRICS = ('pixcorr', 'ssim', *FEATURES)
TWO_WAY = frozenset(FEATURES[:4])
SOURCE_SELECTION_SHA = '9a84d3938071bf57b9e0f6f7675fac023f343f5218a5d051aeabcf38cb2f9d2b'
HEX = re.compile('[0-9a-f]{64}')


class PanelError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise PanelError(message)


def sha(value):
    need(type(value) is str and HEX.fullmatch(value), 'canonical SHA256 required')
    return value


def identities(value, name, count=None):
    need(type(value) is list and all(type(v) is str and v and v.strip() == v for v in value),
         name + ' needs canonical nonempty string identities')
    need(len(value) == len(set(value)) and (count is None or len(value) == count),
         name + ' requires complete unique identity coverage')
    return value


def descriptor(value):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'exact array descriptor')
    path = value['path']
    need(type(path) is str and path and '\\' not in path and '\x00' not in path
         and not Path(path).is_absolute() and '..' not in Path(path).parts
         and Path(path).as_posix() == path, 'ordinary relative payload path')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= 256 * 1024**2,
         'positive bounded single-array extent')
    sha(value['sha256'])
    return value


def validate_payload(payload):
    need(type(payload) is dict and set(payload) ==
         {'image_sha256', 'extraction_receipt_sha256', 'selection', 'rgb425', 'features'},
         'one image binds selection, pixels and every metric feature')
    sha(payload['image_sha256']); sha(payload['extraction_receipt_sha256'])
    descriptor(payload['selection']); descriptor(payload['rgb425'])
    need(type(payload['features']) is dict and set(payload['features']) == set(FEATURES),
         'all six final metric feature families required')
    for value in payload['features'].values():
        descriptor(value)


def validate_packet(packet):
    need(type(packet) is dict and packet.get('schema') == SCHEMA and packet.get('task_id') == TASK,
         'original MindBridge panel schema/task required')
    kind = packet.get('source_kind')
    need(kind in ('generated_engineering_control', 'operator_prepared_source'), 'explicit input evidence kind')
    ids = identities(packet.get('test_image_ids'), 'test gallery')
    need(len(ids) >= 2 and (kind == 'generated_engineering_control' or len(ids) == 982),
         'original operator panel requires all 982 target images')
    need(packet.get('target_subject') == 7 and type(packet.get('target_subject')) is int
         and packet.get('source_subjects') == [1, 2, 5]
         and all(type(v) is int for v in packet['source_subjects']), 'original target7/source1,2,5 cohort')
    sha(packet.get('feature_pipeline_sha256')); sha(packet.get('image_prior_sha256'))
    need(type(packet.get('skimage_version')) is str and packet['skimage_version'], 'exact SSIM runtime version')
    calibration = packet.get('calibration')
    need(type(calibration) is dict and set(calibration) == {str(n) for n in BUDGETS},
         'all three original calibration budgets')
    previous = []
    for n in BUDGETS:
        current = identities(calibration[str(n)], 'calibration', n)
        need(current == sorted(current) and current[:len(previous)] == previous,
             'source lexicographic nested train-only prefixes')
        need(not set(current) & set(ids), 'calibration cannot include test images')
        previous = current
    rows = packet.get('rows')
    need(type(rows) is list and len(rows) == 6, 'all six original method-budget rows')
    seen, targets = set(), {}
    for row in rows:
        need(type(row) is dict, 'method-budget row object')
        arm, budget = row.get('arm'), row.get('budget')
        need(arm in ARMS and type(budget) is int and budget in BUDGETS
             and (arm, budget) not in seen, 'unique original method-budget combination')
        seen.add((arm, budget))
        sha(row.get('freeze_receipt_sha256'))
        need(row.get('generation_frozen_before_target_selection') is True,
             'operator declares generation frozen before target-aware choice')
        images = row.get('images')
        need(type(images) is list and len(images) == len(ids), 'complete image population per condition')
        got = identities([image.get('image_id') for image in images if type(image) is dict], 'condition images')
        need(set(got) == set(ids), 'no omitted, duplicate or substituted target images')
        for image in images:
            need(set(image) == {'image_id', 'target', 'candidates'}, 'image packet shape')
            validate_payload(image['target'])
            ident = image['image_id']
            if ident in targets:
                need(targets[ident] == image['target'], 'same targets and extractor lineage in all six conditions')
            else:
                targets[ident] = image['target']
            candidates = image['candidates']
            need(type(candidates) is list and len(candidates) == 8, 'exactly eight generation-ordered candidates')
            for candidate in candidates:
                validate_payload(candidate)
    need(seen == {(a, b) for a in ARMS for b in BUDGETS}, 'complete original Table2 condition coverage')
    return ids


def _finite_matrix(value, name):
    need(isinstance(value, np.ndarray) and value.ndim == 2 and value.shape[0] >= 2
         and value.shape[1] >= 2 and value.dtype in (np.dtype('float32'), np.dtype('float64')),
         name + ' must be floating image-by-feature matrix')
    need(np.isfinite(value).all() and np.all(np.ptp(value, axis=1) > 0),
         name + ' needs finite nonconstant features for every image')
    return value


def feature_scores(reference, prediction, metric):
    """Original strict predicted-column Pearson identification or SciPy distance."""
    need(metric in FEATURES, 'unknown final feature metric')
    r, p = _finite_matrix(reference, 'reference'), _finite_matrix(prediction, 'prediction')
    need(r.shape == p.shape and r.dtype == p.dtype, 'matching complete feature shape/dtype')
    if metric in TWO_WAY:
        need(r.dtype == np.dtype('float32'), 'source identification features are cast to float32')
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            correlations = np.corrcoef(r, p)[:len(r), len(r):]
        need(np.isfinite(correlations).all(), 'all source Pearson comparisons must be defined')
        paired = np.diag(correlations)
        result = np.sum(correlations < paired, axis=0) / (len(r) - 1)
    else:
        # Source uses scipy.spatial.distance.correlation on each original dtype;
        # avoid replacing this with 1-np.corrcoef under another precision policy.
        from scipy.spatial.distance import correlation
        result = np.array([correlation(a, b) for a, b in zip(r, p)])
    need(np.isfinite(result).all(), 'all original per-image scores finite')
    return result


def image_pair_metrics(reference, prediction, *, skimage_version):
    """Literal source pixel metrics AFTER the declared 425 bilinear resize.

    SSIM deliberately retains the original multichannel=True call on grayscale.
    Its interpretation depends on the explicitly recorded installed skimage
    version, which the authors did not pin. This is not historical parity.
    """
    import skimage
    from skimage.color import rgb2gray
    from skimage.metrics import structural_similarity
    need(skimage.__version__ == skimage_version, 'exact declared SSIM runtime required')
    r, p = reference, prediction
    need(isinstance(r, np.ndarray) and isinstance(p, np.ndarray) and r.shape == p.shape
         and r.ndim == 3 and r.shape[0] == 3 and min(r.shape[1:]) == 425
         and max(r.shape[1:]) <= 4096 and r.dtype == p.dtype
         and r.dtype in (np.dtype('float32'), np.dtype('float64')), 'source-resized matching RGB tensors')
    need(np.isfinite(r).all() and np.isfinite(p).all()
         and np.min(r) >= 0 and np.max(r) <= 1 and np.min(p) >= 0 and np.max(p) <= 1,
         'finite source-clamped pixel range [0,1]')
    need(np.ptp(r) > 0 and np.ptp(p) > 0, 'pixel correlation needs nonconstant images')
    pixel = float(np.corrcoef(r.reshape(-1), p.reshape(-1))[0, 1])
    rg, pg = rgb2gray(np.moveaxis(r, 0, -1)), rgb2gray(np.moveaxis(p, 0, -1))
    structural = float(structural_similarity(pg, rg, multichannel=True,
        gaussian_weights=True, sigma=1.5, use_sample_covariance=False, data_range=1.0))
    need(math.isfinite(pixel) and math.isfinite(structural), 'both source image metrics must be finite')
    return {'pixcorr': pixel, 'ssim': structural}


def select_best_of_eight(target, candidates):
    """Use the existing independently reviewed selection implementation."""
    path = Path(__file__).resolve().parents[1] / 'source-protocol-v2/source_protocol.py'
    raw = path.read_bytes()
    need(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == SOURCE_SELECTION_SHA,
         'exact reviewed source selection dependency')
    name = '_mindbridge_original_panel_source_selection'
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module.select_best_of_eight(target, candidates)


def evaluate_panel(packet, load_array, *, max_working_bytes):
    """Compute every Table2 cell using one shared best-of-eight image per case.

    load_array is trusted operator I/O. Its returned arrays are validated here;
    descriptor authentication and cumulative I/O limits are supplied by FileArrays
    in the CLI. Test-only providers may exercise generated data without file I/O.
    """
    ids = validate_packet(packet)
    need(type(max_working_bytes) is int and 0 < max_working_bytes < 2**63,
         'explicit positive working-memory allocation')
    def workspace(descriptors, multiplier=8, correlation=False):
        # Conservative array-workspace admission, not an OS memory limit. The
        # full NumPy correlation operation retains float64 arrays and an N*N
        # matrix; its admission must precede materializing the feature gallery.
        estimate = multiplier * sum(d['bytes'] for d in descriptors) + 32 * 1024**2
        if correlation:
            estimate += 64 * len(ids)**2
        need(estimate <= max_working_bytes, 'complete-operation numerical workspace exceeds allocation')
    conditions, cells = [], {}
    for row in sorted(packet['rows'], key=lambda r: (r['budget'], ARMS.index(r['arm']))):
        by_id = {image['image_id']: image for image in row['images']}
        selected, per_image = {}, {'pixcorr': [], 'ssim': []}
        for ident in ids:
            image = by_id[ident]
            workspace([image['target']['selection'],
                max((c['selection'] for c in image['candidates']), key=lambda d: d['bytes'])])
            selection = select_best_of_eight(load_array(image['target']['selection']),
                (load_array(candidate['selection']) for candidate in image['candidates']))
            need(type(selection.index) is int and 0 <= selection.index < 8, 'one valid selected image')
            selected[ident] = selection.index
            candidate = image['candidates'][selection.index]
            workspace([image['target']['rgb425'], candidate['rgb425']])
            image_scores = image_pair_metrics(load_array(image['target']['rgb425']),
                load_array(candidate['rgb425']), skimage_version=packet['skimage_version'])
            for metric in ('pixcorr', 'ssim'):
                value = image_scores[metric]
                need(type(value) in (int, float) and math.isfinite(value), 'complete finite image metric')
                per_image[metric].append(value)
        # One feature family at a time. Full np.corrcoef preserves source's exact
        # predicted-column/tie operation; it is not a lower-memory proxy metric.
        for metric in FEATURES:
            workspace([d for ident in ids for d in
                (by_id[ident]['target']['features'][metric],
                 by_id[ident]['candidates'][selected[ident]]['features'][metric])], correlation=True)
            references, predictions = [], []
            for ident in ids:
                image = by_id[ident]
                references.append(load_array(image['target']['features'][metric]))
                predictions.append(load_array(image['candidates'][selected[ident]]['features'][metric]))
            need(all(isinstance(a, np.ndarray) and a.ndim == 1 for a in references + predictions),
                 'one flattened final feature vector per image')
            try:
                ref, pred = np.stack(references), np.stack(predictions)
            except ValueError as exc:
                raise PanelError('all image feature dimensions must agree') from exc
            per_image[metric] = feature_scores(ref, pred, metric).tolist()
            del references, predictions, ref, pred
        need(set(per_image) == set(METRICS) and all(len(v) == len(ids) for v in per_image.values()),
             'complete eight-metric original image panel')
        means = {metric: float(np.mean(per_image[metric])) for metric in METRICS}
        for metric, value in means.items():
            need(math.isfinite(value), 'finite full-gallery metric mean')
            cells[f'table2.{row["arm"]}.{row["budget"]}.{metric}'] = value
        conditions.append({'arm': row['arm'], 'budget': row['budget'], 'image_ids': ids,
            'selected_candidate_indices': [selected[ident] for ident in ids],
            'freeze_receipt_sha256': row['freeze_receipt_sha256'],
            'per_image': per_image, 'means': means})
    need(len(cells) == 48, 'all 48 original findings produced')
    return {'schema': 'mindbridge-original-panel-result/v1', 'task_id': TASK,
        'source_kind': packet['source_kind'], 'images_per_condition': len(ids),
        'condition_count': 6, 'finding_count': 48, 'conditions': conditions, 'findings': cells,
        'selected_primary': {'finding': 'table2.mindbridge.4000.clip', 'role': 'benchmark nomination'},
        'source_target_aware_selection': True, 'deployable_target_blind_selection': False,
        'skimage_version': packet['skimage_version'],
        'feature_pipeline_sha256': packet['feature_pipeline_sha256'],
        'image_prior_sha256': packet['image_prior_sha256'],
        'historical_SSIM_runtime_identity': 'unresolved',
        'scientific_qualification': False, 'reproduction': 'unknown', 'improvement': 'unknown',
        'limits': ['Input and freeze declarations do not authenticate original membership or protected custody.',
                   'Provided feature/image payloads need independent native extraction and weight verification.',
                   'Source skimage version is unpinned; literal SSIM call is runtime-specific.',
                   'No accepted equivalence tolerance, meaningful gain or uncertainty decision is introduced.']}


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate JSON key'); out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(PanelError('nonfinite JSON')))


def stable_bytes(path, expected, cap):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'no symlink payload or ancestor')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
             'bounded ordinary single-link input')
        need(expected is None or before.st_size == expected['bytes'], 'exact input extent')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(before.st_size + 1)
        after = os.fstat(fd)
        key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(len(raw) == before.st_size and len(raw) <= cap
             and key(before) == key(after) == key(path.lstat()), 'stable bounded input and EOF')
        need(expected is None or hashlib.sha256(raw).hexdigest() == expected['sha256'], 'exact input SHA256')
        return raw
    finally:
        os.close(fd)


class FileArrays:
    """Hash-checked plain NPY reader with no pickle, mmap race or oversized header allocation."""
    def __init__(self, root, *, max_read_bytes, max_array_bytes):
        self.root = Path(root).resolve()
        need(type(max_read_bytes) is int and max_read_bytes > 0
             and type(max_array_bytes) is int and 0 < max_array_bytes <= 256 * 1024**2,
             'positive bounded explicit I/O limits')
        self.maximum = max_read_bytes; self.cap = max_array_bytes; self.read_bytes = 0

    def __call__(self, value):
        d = descriptor(value)
        need(d['bytes'] <= self.cap and self.read_bytes + d['bytes'] + 1 <= self.maximum,
             'cumulative payload read budget before I/O')
        # Include one EOF/growth probe in the conservative read charge, including
        # refused reads. The successful payload itself has exactly d['bytes'].
        self.read_bytes += d['bytes'] + 1
        raw = stable_bytes(self.root / d['path'], d, self.cap)
        buffer = io.BytesIO(raw)
        version = np.lib.format.read_magic(buffer)
        need(version in ((1, 0), (2, 0)), 'plain NPY v1/v2 only')
        reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
        shape, fortran, dtype = reader(buffer, max_header_size=10000)
        need(not fortran and dtype in (np.dtype('float32'), np.dtype('float64'))
             and 1 <= len(shape) <= 3 and all(type(v) is int and v > 0 for v in shape),
             'finite-shape C-order floating source array')
        size = math.prod(shape) * dtype.itemsize
        need(buffer.tell() + size == len(raw), 'exact NPY header/body extent without trailing data')
        array = np.frombuffer(raw, dtype=dtype, offset=buffer.tell()).reshape(shape)
        need(np.isfinite(array).all(), 'finite complete payload')
        return array


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet'); parser.add_argument('payload_root'); parser.add_argument('output')
    parser.add_argument('--packet-sha256', required=True)
    parser.add_argument('--max-read-bytes', type=int, required=True)
    parser.add_argument('--max-array-bytes', type=int, required=True)
    parser.add_argument('--max-working-bytes', type=int, required=True)
    args = parser.parse_args(argv)
    raw = stable_bytes(args.packet, None, 128 * 1024**2)
    need(hashlib.sha256(raw).hexdigest() == sha(args.packet_sha256), 'operator-selected complete packet digest')
    arrays = FileArrays(args.payload_root, max_read_bytes=args.max_read_bytes, max_array_bytes=args.max_array_bytes)
    result = evaluate_panel(strict_json(raw), arrays, max_working_bytes=args.max_working_bytes)
    result['packet_sha256'] = args.packet_sha256
    result['payload_read_charge_bytes'] = arrays.read_bytes
    output = Path(args.output).absolute()
    need(not any(p.is_symlink() for p in (output, *output.parents)), 'ordinary exclusive output path')
    body = (json.dumps(result, sort_keys=True, allow_nan=False, separators=(',', ':')) + '\n').encode()
    need(len(body) <= 32 * 1024**2, 'complete result output bound')
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(body); stream.flush(); os.fsync(fd)
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()
