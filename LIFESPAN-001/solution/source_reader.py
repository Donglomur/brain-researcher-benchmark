"""Direct pinned original readers for the supplied oracle; no grader imports."""
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

import nibabel as nib
import numpy as np

from core import parcel_means

METHOD_SHA256 = '47c9450cfee4db7140aee2a269510644dde6a3388dfeea9deee2f1f5ae466471'
SOURCE_SHA256 = '18fd1271190687765461243943ced2b82d5d5fb703c3d675a2f7586992b5f932'
COHORT_SHA256 = '9c24cf46cdc138a52fc5a10e064ce7ea052a4834339a71f7e5e3595f81898009'
EXPECTED_FILES, EXPECTED_BYTES = 121, 4_997_109_352
N_SUBJECTS, N_FRAMES, N_VERTICES, N_HEMI_ROIS = 59, 895, 10242, 74
EXCLUDED = {'Unknown', 'Medial_wall'}
ROLE_DIR = {'surface_timeseries': 'surface', 'phenotype': 'phenotype', 'surface_annotation': 'atlas'}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def safe_path(value):
    require('..' not in os.fspath(value).split('/'), 'Parent traversal refused')
    path = Path(value).absolute()
    for p in (path, *path.parents):
        require(not p.is_symlink(), 'Symlink path/ancestor refused')
    return path.resolve(strict=False)


def regular(path):
    path = safe_path(path)
    require(stat.S_ISREG(path.lstat().st_mode), 'Regular file required')
    return path


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, 'Duplicate JSON key')
        out[key] = value
    return out


def finite_json(value):
    if isinstance(value, float):
        require(math.isfinite(value), 'Nonfinite JSON')
    elif isinstance(value, dict):
        for item in value.values():
            finite_json(item)
    elif isinstance(value, list):
        for item in value:
            finite_json(item)


def bounded_read(path, maximum):
    path = regular(path)
    require(path.stat().st_size <= maximum, 'Input byte cap exceeded')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'Regular opened file required')
        data = stream.read(maximum + 1)
    require(len(data) <= maximum, 'Input byte cap exceeded during read')
    return data


def authenticated_json(path, digest):
    raw = bounded_read(path, 200_000)
    require(hashlib.sha256(raw).hexdigest() == digest, 'Public JSON identity mismatch')
    def invalid(token):
        raise ValueError('Nonfinite JSON constant')
    out = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid)
    finite_json(out)
    return out


def hash_original(path, size):
    path = regular(path)
    before = path.stat()
    require(type(size) is int and 0 < size <= 50_000_000 and before.st_size == size, 'Original size mismatch')
    h, total = hashlib.sha256(), 0
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        while block := stream.read(min(1_048_576, size + 1 - total)):
            total += len(block)
            require(total <= size, 'Original grew during hash')
            h.update(block)
        after = os.fstat(stream.fileno())
    identity = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
    require(total == size and identity(before) == identity(after) == identity(path.stat()), 'Original changed during hash')
    return h.hexdigest()


def authenticate_source(data_dir, manifest):
    root = safe_path(data_dir)
    files = manifest['files']
    require(len(files) == EXPECTED_FILES and sum(r['size_bytes'] for r in files) == EXPECTED_BYTES, 'Original inventory cardinality mismatch')
    expected = {'source_manifest.json'}
    for row in files:
        name = row['path']
        require(isinstance(name, str) and not name.startswith('/') and '\\' not in name
                and all(p not in ('', '.', '..') for p in name.split('/')), 'Unsafe source member path')
        require(row['role'] in ROLE_DIR and name == ROLE_DIR[row['role']] + '/' + row['original_filename'], 'Source role/path mismatch')
        require(name not in expected, 'Duplicate source path')
        require(re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None, 'Malformed source digest')
        expected.add(name)
    dirs = {str(p) for name in expected for p in PurePosixPath(name).parents if str(p) != '.'}
    observed, observed_dirs = set(), set()
    require(root.is_dir(), 'Source root must be a directory')
    for parent, directories, names in os.walk(root, followlinks=False):
        for name in directories + names:
            path = Path(parent) / name
            mode = path.lstat().st_mode
            rel = path.relative_to(root).as_posix()
            if stat.S_ISDIR(mode):
                observed_dirs.add(rel)
            else:
                require(stat.S_ISREG(mode), 'Nonregular source member refused')
                observed.add(rel)
    require(observed == expected and observed_dirs == dirs, 'Closed original inventory mismatch')
    for row in files:
        require(hash_original(root / row['path'], row['size_bytes']) == row['sha256'], 'Original SHA256 mismatch')


def read_phenotype(path, ids):
    rows = list(csv.reader(io.StringIO(bounded_read(path, 100_000).decode('utf-8'), newline='')))
    require(rows and rows[0] == ['', 'Age', 'Dominant Hand', 'Sex'], 'Literal phenotype header mismatch')
    header, table = rows[0], {}
    for index, tokens in enumerate(rows[1:]):
        require(len(tokens) == len(header) and tokens[0] and tokens[0] not in table, 'Phenotype duplicate/width/ID failure')
        table[tokens[0]] = dict(phenotype_row_index=index, source_tokens=dict(zip(header, tokens)))
    require(set(ids) <= table.keys(), 'Missing selected phenotype')
    for subject in ids:
        row = table[subject]
        age = float(row['source_tokens']['Age'])
        require(math.isfinite(age) and age >= 0, 'Invalid source age')
        age32 = float(np.float32(age))
        require(math.isfinite(age32) and row['source_tokens']['Sex'].strip(), 'Invalid computational age or missing sex')
        row.update(age_source=age, age_computational=age32, sex=row['source_tokens']['Sex'])
    return table, header


def read_annotation(path, hemi, first_roi):
    labels, ctab, names = nib.freesurfer.read_annot(str(regular(path)), orig_ids=True)
    require(labels.shape == (N_VERTICES,) and labels.dtype.kind in 'iu', 'Annotation vertex shape/type mismatch')
    require(ctab.shape == (len(names), 5), 'Annotation table mismatch')
    packed = ctab[:, 0].astype(np.int64) + (ctab[:, 1].astype(np.int64) << 8) + (ctab[:, 2].astype(np.int64) << 16)
    require(np.array_equal(packed, ctab[:, 4]) and len(set(packed.tolist())) == len(packed), 'Ambiguous packed annotation IDs')
    names = [x.decode('utf-8') for x in names]
    require(len(set(names)) == len(names), 'Duplicate annotation name')
    require(not np.any((labels == -1) | (labels == 0)) and set(labels.tolist()) <= set(packed.tolist()), 'Unassigned or unknown annotation ID')
    rows, vertices, diagnostics = [], [], []
    for index, (name, source_id) in enumerate(zip(names, packed)):
        v = np.flatnonzero(labels == source_id).astype(np.int64)
        excluded = name in EXCLUDED
        diagnostics.append(dict(hemisphere=hemi, annotation_id=index, packed_rgb_id=int(source_id),
                                label_name=name, vertex_count=len(v), excluded=excluded))
        if excluded:
            continue
        require(len(v) > 0, 'Empty required cortical parcel')
        rows.append(dict(roi_index=first_roi + len(rows), hemisphere=hemi, annotation_id=index,
                         label_name=name, vertex_count=len(v)))
        vertices.append(v)
    require(len(rows) == N_HEMI_ROIS, 'Required cortical parcel count mismatch')
    return rows, vertices, diagnostics


def load_inputs(data_dir, method_path, cohort_path):
    root = safe_path(data_dir)
    method = authenticated_json(method_path, METHOD_SHA256)
    cohort = authenticated_json(cohort_path, COHORT_SHA256)
    manifest = authenticated_json(root / 'source_manifest.json', SOURCE_SHA256)
    require(method['source_manifest_sha256'] == SOURCE_SHA256 and method['cohort']['manifest_sha256'] == COHORT_SHA256,
            'Method/source/cohort relationship mismatch')
    ids = cohort['subject_ids']
    require(len(ids) == len(set(ids)) == N_SUBJECTS, 'Complete fixed cohort required')
    authenticate_source(root, manifest)  # Before any anatomical or scientific parser.
    sources = {(r['subject_id'], r['hemisphere']): r for r in manifest['files'] if r['role'] == 'surface_timeseries'}
    require(set(sources) == {(s, h) for s in ids for h in ('lh', 'rh')}, 'Exact hemisphere cohort mismatch')
    phenos = [r for r in manifest['files'] if r['role'] == 'phenotype']
    annotations = {r['hemisphere']: r for r in manifest['files'] if r['role'] == 'surface_annotation'}
    require(len(phenos) == 1 and set(annotations) == {'lh', 'rh'}, 'Phenotype/atlas identity mismatch')
    table, header = read_phenotype(root / phenos[0]['path'], ids)
    require(len(table) == method['source_observed']['phenotype_rows'], 'Source phenotype row count changed')
    parcels, membership, diagnostics = [], {}, []
    for hemi in ('lh', 'rh'):
        rows, vertices, details = read_annotation(root / annotations[hemi]['path'], hemi, len(parcels))
        parcels += rows
        membership[hemi] = vertices
        diagnostics += details
    return dict(root=root, method=method, manifest=manifest, cohort=cohort, subject_ids=ids, sources=sources,
                phenotype=table, phenotype_header=header, parcels=parcels, membership=membership,
                annotation_diagnostics=diagnostics)


def decode_surface(path):
    image = nib.load(str(regular(path)))
    require(isinstance(image, nib.gifti.GiftiImage), 'GIFTI source required')
    require(len(image.darrays) == N_FRAMES, 'Original frame count mismatch')
    x = np.empty((N_FRAMES, N_VERTICES), dtype=np.float32)
    intents, dtypes, time_steps = set(), set(), set()
    for i, array in enumerate(image.darrays):
        require(array.ext_fname == '' and array.data.shape == (N_VERTICES,), 'External storage or vertex support mismatch')
        require(array.data.dtype == np.dtype('float32') and array.intent == 2001, 'Source dtype/intent mismatch')
        require(np.isfinite(array.data).all(), 'Nonfinite original functional value')
        require(array.meta.get('TimeStep') == '1000.000000', 'Header TimeStep literal changed')
        x[i] = array.data
        intents.add(int(array.intent)); dtypes.add(str(array.data.dtype)); time_steps.add(array.meta['TimeStep'])
    return x, dict(data_array_count=len(image.darrays), values_per_array=N_VERTICES,
                   storage_dtype=sorted(dtypes)[0], intents=sorted(intents), timestep_literals=sorted(time_steps))


def read_subject(inputs, subject):
    q_parts, double_parts, observed = [], [], {'subject_id': subject}
    for hemi, prefix in [('lh', 'left'), ('rh', 'right')]:
        entry = inputs['sources'][(subject, hemi)]
        x, details = decode_surface(inputs['root'] / entry['path'])
        q, before = parcel_means(x, inputs['membership'][hemi])
        q_parts.append(q); double_parts.append(before)
        observed.update({prefix + '_' + k: details[k] for k in ('data_array_count', 'values_per_array', 'storage_dtype', 'intents')})
    return np.concatenate(q_parts, axis=1), np.concatenate(double_parts, axis=1), observed
