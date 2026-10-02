"""Independent bounded source primitives; no import-time I/O or source defaults.

Header interpretation shares nibabel with the oracle. Signal extraction instead
streams original NIfTI Fortran volumes through gzip and enumerates physical
supports independently. No oracle, stager or numerical bank imports.
"""
from __future__ import annotations
from contextlib import contextmanager
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat

import nibabel as nib
import numpy as np

MAX_FILE = 1024**3
MAX_SMALL = 16*1024**2
MAX_VOXELS = 20_000_000
MAX_FRAMES = 10_000
SUPPORT_PREFIX = b"TASKFC_support_v2\n"
ROIS = ("L_lateral_occipital", "R_lateral_occipital")
CENTERS = ((-30., -90., -6.), (30., -90., -6.))
MOTION = ("X", "Y", "Z", "RotX", "RotY", "RotZ")


def need(ok, code):
    if not ok:
        raise ValueError(code)


def safe_path(value):
    raw = os.fspath(value)
    need(isinstance(raw, str) and raw.startswith('/') and '\0' not in raw
         and all(p not in ('.', '..') for p in raw.split('/')), 'absolute_lexical_path')
    path = Path(raw)
    for part in (*reversed(path.parents), path):
        if os.path.lexists(part):
            mode = part.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'source_symlink')
            need(part == path or stat.S_ISDIR(mode), 'non_directory_ancestor')
    return path


def signature(s):
    return s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns


@contextmanager
def authenticated_stream(path, row):
    """Hash then rewind the same descriptor; preserve identity around parsing."""
    path = safe_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode), 'source_regular_file')
    need(type(row['size_bytes']) is int and 0 < before.st_size == row['size_bytes'] <= MAX_FILE,
         'bounded_exact_source_size')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        need(signature(os.fstat(stream.fileno())) == signature(before), 'source_replaced_before_read')
        digest, count = hashlib.sha256(), 0
        while chunk := stream.read(1024**2):
            count += len(chunk)
            need(count <= row['size_bytes'], 'source_grew')
            digest.update(chunk)
        need(count == row['size_bytes'] and digest.hexdigest() == row['sha256'], 'source_digest')
        stream.seek(0)
        yield stream
        need(signature(os.fstat(stream.fileno())) == signature(before)
             == signature(path.lstat()), 'source_changed_during_read')
        # Metadata clocks may not advance on a same-size rewrite. Rehash the
        # same descriptor after consumption as well; source bytes are authority.
        stream.seek(0)
        after_digest, after_count = hashlib.sha256(), 0
        while chunk := stream.read(1024**2):
            after_count += len(chunk)
            need(after_count <= row['size_bytes'], 'source_changed_during_read')
            after_digest.update(chunk)
        need(after_count == row['size_bytes'] and after_digest.hexdigest() == row['sha256']
             and signature(os.fstat(stream.fileno())) == signature(before)
             == signature(path.lstat()), 'source_changed_during_read')


def small_bytes(path, row):
    need(row['size_bytes'] <= MAX_SMALL, 'small_source_cap')
    with authenticated_stream(path, row) as stream:
        raw = stream.read(MAX_SMALL + 1)
    need(len(raw) == row['size_bytes'], 'small_source_size')
    return raw


def literal(value):
    value = float(value)
    return value if math.isfinite(value) else 'NaN' if math.isnan(value) else '+Inf' if value > 0 else '-Inf'


def header_from_bytes(raw):
    need(len(raw) == 352, 'nifti_header_length')
    h = nib.Nifti1Header(raw[:348], check=False)
    need(int(h['sizeof_hdr']) == 348 and bytes(h['magic']) == b'n+1\0', 'single_file_nifti1')
    shape = tuple(int(x) for x in h.get_data_shape())
    need(len(shape) == 4 and all(x > 0 for x in shape) and math.prod(shape[:3]) <= MAX_VOXELS
         and 2 <= shape[3] <= MAX_FRAMES, 'bounded_nifti_shape')
    dtype = h.get_data_dtype()
    need(dtype.kind in 'iuf' and dtype.itemsize <= 8 and int(h['bitpix']) == dtype.itemsize*8,
         'real_nifti_dtype')
    offset = float(h['vox_offset'])
    need(math.isfinite(offset) and offset.is_integer() and 352 <= offset <= 1024**2,
         'bounded_nifti_offset')
    need(int(offset) + math.prod(shape)*dtype.itemsize <= 2*1024**3, 'decoded_nifti_cap')
    affine = np.asarray(h.get_best_affine(), dtype=np.float64)
    need(affine.shape == (4, 4) and np.isfinite(affine).all()
         and np.array_equal(affine[3], [0, 0, 0, 1]) and np.linalg.det(affine[:3, :3]) != 0,
         'finite_nonsingular_affine')
    slope, intercept = h.get_slope_inter()
    slope, intercept = (1., 0.) if slope is None else (float(slope), float(intercept))
    need(math.isfinite(slope) and math.isfinite(intercept), 'finite_effective_scaling')
    spatial, temporal = h.get_xyzt_units()
    record = dict(shape=list(shape), selected_affine=affine.tolist(), storage_dtype=dtype.str,
                  spatial_units=spatial, temporal_units=temporal,
                  zooms=[literal(v) for v in h.get_zooms()], raw_toffset=literal(h['toffset']),
                  raw_scl_slope=literal(h['scl_slope']), raw_scl_inter=literal(h['scl_inter']),
                  effective_slope=slope, effective_intercept=intercept,
                  qform_code=int(h['qform_code']), sform_code=int(h['sform_code']),
                  qform=h.get_qform().tolist(), sform=h.get_sform().tolist(),
                  vox_offset=int(offset), extension_flag=list(raw[348:352]),
                  description=bytes(h['descrip']).rstrip(b'\0').decode('utf-8', 'replace'))
    return record, dtype, affine


@contextmanager
def image_stream(path, row):
    with authenticated_stream(path, row) as stream:
        if str(path).endswith('.gz'):
            with gzip.GzipFile(fileobj=stream, mode='rb') as decoded:
                yield decoded
        else:
            yield stream


def read_header(path, row):
    with image_stream(path, row) as stream:
        # Logical header only; gzip may buffer compressed bytes but no sample is decoded here.
        return header_from_bytes(stream.read(352))


def sphere_support(shape, affine, centers=CENTERS, radius=8., chunk_size=16384):
    need(len(shape) == 3 and all(type(x) is int and x > 0 for x in shape)
         and math.prod(shape) <= MAX_VOXELS, 'geometry_shape')
    a = np.asarray(affine, dtype=np.float64)
    need(a.shape == (4, 4) and np.isfinite(a).all() and np.array_equal(a[3], [0, 0, 0, 1])
         and np.linalg.det(a[:3, :3]) != 0, 'geometry_affine')
    centers = np.asarray(centers, dtype=np.float64)
    need(centers.shape == (2, 3) and np.isfinite(centers).all()
         and type(radius) in (int, float) and math.isfinite(radius) and radius > 0, 'sphere_definition')
    need(type(chunk_size) is int and chunk_size > 0, 'geometry_chunk_size')
    selected = [[], []]
    for start in range(0, math.prod(shape), chunk_size):
        flat = np.arange(start, min(start+chunk_size, math.prod(shape)), dtype=np.int64)
        ijk = np.column_stack(np.unravel_index(flat, shape, order='C'))
        world = ijk @ a[:3, :3].T + a[:3, 3]
        need(np.isfinite(world).all(), 'finite_geometry')
        for roi, center in enumerate(centers):
            d = world-center
            distance = d[:, 0]*d[:, 0] + d[:, 1]*d[:, 1] + d[:, 2]*d[:, 2]
            selected[roi].append(flat[distance <= radius*radius])
    result = [np.concatenate(parts) for parts in selected]
    need(all(len(x) for x in result), 'empty_sphere')
    return result


def support_records(indices):
    need(len(indices) == 2, 'two_supports')
    return [dict(roi_id=roi, n_voxels=len(ids), support_sha256=hashlib.sha256(
        SUPPORT_PREFIX+np.asarray(ids, dtype='<i8').tobytes()).hexdigest())
        for roi, ids in zip(ROIS, indices)]


def extract_series(path, row, expected_header=None):
    with image_stream(path, row) as stream:
        header, dtype, affine = header_from_bytes(stream.read(352))
        if expected_header is not None:
            need(header == expected_header, 'header_changed')
        shape = tuple(header['shape'])
        support = sphere_support(shape[:3], affine)
        prefix = stream.read(header['vox_offset']-352)
        need(len(prefix) == header['vox_offset']-352, 'truncated_extensions')
        volume_bytes = math.prod(shape[:3])*dtype.itemsize
        out = np.empty((shape[3], 2), dtype=np.float64)
        for frame in range(shape[3]):
            raw = stream.read(volume_bytes)
            need(len(raw) == volume_bytes, 'truncated_volume')
            values = np.frombuffer(raw, dtype=dtype).reshape(shape[:3], order='F')
            for roi, indices in enumerate(support):
                selected = np.ascontiguousarray(values.ravel(order='C')[indices], dtype=np.float64)
                selected = selected*header['effective_slope'] + header['effective_intercept']
                need(np.isfinite(selected).all(), 'nonfinite_measured_voxel')
                out[frame, roi] = np.mean(selected, dtype=np.float64)
        need(stream.read(1) == b'', 'extra_decoded_image_bytes')
    need(np.isfinite(out).all(), 'nonfinite_roi_means')
    return out, header, support_records(support)


def table(raw, delimiter='\t'):
    need(len(raw) <= MAX_SMALL, 'table_byte_cap')
    parsed = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), delimiter=delimiter))
    need(parsed and parsed[0] and len(parsed) <= 100001 and len(parsed[0]) <= 256,
         'table_size')
    columns = parsed[0]
    need(all(columns) and len(columns) == len(set(columns)), 'table_unique_headers')
    need(all(len(row) == len(columns) for row in parsed[1:]), 'table_row_width')
    return columns, [dict(zip(columns, row)) for row in parsed[1:]]


def number(token):
    need(isinstance(token, str) and token.strip() != '', 'missing_numeric_token')
    value = float(token)
    need(math.isfinite(value), 'nonfinite_numeric_token')
    return value


def events(raw):
    columns, rows = table(raw)
    need({'onset', 'duration', 'trial_type'} <= set(columns), 'event_columns')
    parsed, records = [], []
    for i, original in enumerate(rows):
        values = dict(onset=number(original['onset']), duration=number(original['duration']),
                      trial_type=original['trial_type'],
                      modulation=number(original['modulation']) if 'modulation' in columns else 1.)
        need(values['trial_type'] in ('language', 'string') and values['duration'] >= 0
             and math.isfinite(values['onset']+values['duration']), 'event_domain')
        parsed.append(values)
        records.append(dict(source_row_index=i, original=original, numeric=values))
    need({row['trial_type'] for row in parsed} == {'language', 'string'}, 'both_conditions')
    return columns, parsed, records


def motion(raw, n_frames):
    columns, rows = table(raw)
    need(set(MOTION) <= set(columns) and len(rows) == n_frames, 'complete_motion_table')
    values = np.asarray([[number(row[k]) for k in MOTION] for row in rows], dtype=np.float64)
    need(values.shape == (n_frames, 6), 'motion_shape')
    return columns, values
