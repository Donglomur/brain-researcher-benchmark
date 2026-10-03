"""Private SOCIALBRAIN source reconstruction; no downloads or endpoint analysis.

All source bytes are authenticated before parsing and immutable buffers are the
only numerical inputs. Generic header/table parsing is shared, disclosed code;
array decoding, extraction and cleaning are not imported from the oracle.
Production document pins deliberately fail closed until parent freeze. Import
does not load source/code documents, discover data, or compute any statistics.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
import time
import types
import zlib

SOURCE_SHA = '9458c48ac61e1e8b0ee36d513ebf6e7613e889a9895747ca46d4c7bd50af8d0b'
METHOD_SHA = 'fb75a7cc8858de75f4269175d57c41cb70bf182409c0c68410931976672c5a12'
SCHEMA_SHA = 'f1388ffa06e5a04a684287724e5b86e914896980f4e0c7fa3366c8d1bd2f23c4'
REPORTING_SHA = '89db8ca04db493d5f8522246200b7c8b11562856b2fb977f201748b1ebb1f4d6'
MODULE_PINS = {
    'inspect_structure.py': '85091795d59ad3983782686ff60f2bde94a1d517eee62b2d6fd7720167845587',
    'source_numerics.py': '393116d935d5d84530641db07343ae0320a3b609122b3c5c78e53b2138787059',
    'reporting_kernel.py': REPORTING_SHA,
}
IDS = tuple(f'sub-pixar{i:03d}' for i in range(1, 156))
VERSIONS = {'numpy': '2.1.3', 'scipy': '1.14.1', 'nibabel': '5.3.2',
            'nilearn': '0.12.1', 'scikit-learn': '1.5.2', 'pandas': '2.2.3'}
HEADER_FIELDS = ('shape', 'selected_affine', 'storage_dtype', 'spatial_units',
                 'temporal_units', 'zooms', 'raw_toffset', 'raw_scl_slope',
                 'raw_scl_inter', 'effective_slope', 'effective_intercept')


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def signature(s):
    return s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def exact_read(value, digest, cap):
    """Small pinned code/document read before trusting imported helpers."""
    raw = os.fspath(value)
    need(type(raw) is str and raw.startswith('/') and '\0' not in raw
         and not any(p in ('.', '..') for p in raw.split('/')), 'safe_absolute_path')
    path = Path(raw)
    for part in (*reversed(path.parents), path):
        if os.path.lexists(part):
            mode = part.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'symlink_input')
            if part != path:
                need(stat.S_ISDIR(mode), 'input_ancestor')
    need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'unfrozen_pin')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'input_size_or_type')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        need(signature(os.fstat(stream.fileno())) == signature(before), 'input_changed')
        payload = stream.read(cap + 1)
        need(signature(os.fstat(stream.fileno())) == signature(before), 'input_changed')
    need(signature(path.lstat()) == signature(before), 'input_path_changed')
    need(len(payload) == before.st_size and hashlib.sha256(payload).hexdigest() == digest, 'input_hash')
    return payload


@dataclass(frozen=True)
class Policy:
    source_sha: str | None
    method_sha: str | None
    schema_sha: str | None
    reporting_sha: str | None
    module_pins: dict
    versions: dict
    subject_ids: tuple = IDS
    max_decoded_bytes: int = 512 * 1024**2
    wall_seconds: int = 1800


def production_policy():
    return Policy(SOURCE_SHA, METHOD_SHA, SCHEMA_SHA, REPORTING_SHA,
                  dict(MODULE_PINS), dict(VERSIONS))


def load_modules(policy):
    need(set(policy.module_pins) == set(MODULE_PINS), 'module_closure')
    need(policy.module_pins['reporting_kernel.py'] == policy.reporting_sha, 'reporting_pin')
    directory = Path(__file__).absolute().parent
    # Authenticate the complete closure before the first compile/import.
    payloads = {name: exact_read(directory / name, pin, 1024**2)
                for name, pin in policy.module_pins.items()}
    modules = {}
    for filename, payload in payloads.items():
        key = '_socialbrain_private_' + filename[:-3]
        module = types.ModuleType(key)
        module.__file__ = str(directory / filename)
        sys.modules[key] = module  # dataclass resolves its defining module.
        try:
            exec(compile(payload, module.__file__, 'exec'), module.__dict__)
        except BaseException:
            sys.modules.pop(key, None)
            raise
        modules[filename[:-3]] = module
    return modules


def header(raw, ndim, helper, policy, check):
    """Decode only bounded logical NIfTI header/extensions from immutable gzip."""
    from nibabel import Nifti1Header
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    prefix = bytearray()
    cursor = 0

    def fill(target):
        nonlocal cursor
        while len(prefix) < target:
            check()
            if decoder.unconsumed_tail:
                chunk = decoder.unconsumed_tail
            else:
                need(cursor < min(len(raw), policy.max_header_bytes), 'header_compressed_cap')
                chunk = raw[cursor:min(cursor + 1024, len(raw), policy.max_header_bytes)]
                cursor += len(chunk)
            out = decoder.decompress(chunk, target - len(prefix))
            prefix.extend(out)
            need(out or not decoder.eof, 'header_truncated')

    fill(352)
    h = Nifti1Header(binaryblock=bytes(prefix[:348]), check=False)
    shape = tuple(int(v) for v in h.get_data_shape())
    dtype = h.get_data_dtype()
    need(int(h['sizeof_hdr']) == 348 and h['magic'].tobytes() == b'n+1\0', 'single_file_nifti1')
    need(len(shape) == ndim and all(v > 0 for v in shape), 'source_image_dimensions')
    need(dtype.kind in 'iuf' and dtype.itemsize <= 8 and int(h['bitpix']) == dtype.itemsize * 8,
         'source_image_dtype')
    offset = float(h['vox_offset'])
    need(math.isfinite(offset) and offset.is_integer() and 352 <= offset <= policy.max_header_bytes,
         'header_offset')
    offset = int(offset)
    fill(offset)
    position = 352
    if prefix[348]:
        while position < offset:
            need(position + 8 <= offset, 'extension_header')
            length, unused_code = struct.unpack(h.endianness + 'ii', prefix[position:position + 8])
            need(length >= 16 and length % 16 == 0 and position + length <= offset, 'extension_length')
            position += length
    else:
        need(not any(prefix[352:]), 'unflagged_extension')
    affine = h.get_best_affine()
    import numpy as np
    need(np.isfinite(affine).all() and np.array_equal(affine[3], [0., 0., 0., 1.])
         and math.isfinite(float(np.linalg.det(affine[:3, :3])))
         and np.linalg.det(affine[:3, :3]) != 0, 'source_affine')
    slope, intercept = h.get_slope_inter()
    units = h.get_xyzt_units()
    result = dict(shape=list(shape), selected_affine=affine.tolist(), storage_dtype=dtype.str,
                  spatial_units=units[0], temporal_units=units[1],
                  zooms=[helper.literal(v) for v in h.get_zooms()],
                  raw_toffset=helper.literal(h['toffset']), raw_scl_slope=helper.literal(h['scl_slope']),
                  raw_scl_inter=helper.literal(h['scl_inter']),
                  effective_slope=1. if slope is None else float(slope),
                  effective_intercept=0. if intercept is None else float(intercept))
    need(all(type(v) is float and math.isfinite(v) and v > 0 for v in result['zooms']), 'source_zooms')
    return result, offset, dtype


def decode_values(raw, observed_header, offset, dtype, policy, check):
    """Bounded strict gzip EOF and direct NIfTI Fortran storage decoding."""
    import numpy as np
    shape = tuple(observed_header['shape'])
    expected = offset + math.prod(shape) * dtype.itemsize
    need(expected <= policy.max_decoded_bytes, 'decoded_image_cap')
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    output = bytearray()
    cursor = 0
    while not decoder.eof:
        check()
        if decoder.unconsumed_tail:
            chunk = decoder.unconsumed_tail
        else:
            need(cursor < len(raw), 'gzip_truncated')
            chunk = raw[cursor:cursor + 65536]
            cursor += len(chunk)
        output.extend(decoder.decompress(chunk, min(1024**2, expected + 1 - len(output))))
        need(len(output) <= expected, 'decoded_image_overrun')
    need(not decoder.unused_data and not decoder.unconsumed_tail and cursor == len(raw), 'gzip_trailing_bytes')
    need(len(output) == expected, 'decoded_image_length')
    values = np.frombuffer(output, dtype=dtype, count=math.prod(shape), offset=offset).reshape(shape, order='F')
    values = np.array(values, dtype=np.float64, order='C', copy=True)
    # Explicit two float64 operations match the declared calibrated arithmetic.
    values *= observed_header['effective_slope']
    values += observed_header['effective_intercept']
    return values


def confounds(raw, helper, policy, names, missing_policy, frames):
    import numpy as np
    columns, rows = helper.table(raw, policy)
    need(len(rows) == frames and set(names) <= set(columns), 'confound_frame_or_columns')
    allowed = missing_policy['missing_tokens']
    need(type(allowed) is list and all(type(v) is str for v in allowed), 'missing_tokens_unfrozen')
    need(missing_policy['permitted_row_indices'] == [0] and missing_policy['replacement'] == 0., 'missing_policy')
    values = np.empty((frames, len(names)), dtype=np.float64)
    missing = []
    fd_values, fd_missing = [], []
    for j, name in enumerate(names):
        index = columns.index(name)
        for i, row in enumerate(rows):
            token = row[index]
            if token in allowed:
                need(i == 0, 'missing_outside_first_frame')
                values[i, j] = 0.
                missing.append(dict(frame_index=i, column_name=name, original_token=token, applied_value=0.))
                if name == 'framewise_displacement':
                    fd_missing.append(i)
            else:
                try:
                    value = float(token)
                except ValueError as exc:
                    raise ValueError('invalid_confound_token') from exc
                need(math.isfinite(value), 'nonfinite_confound')
                values[i, j] = value
                if name == 'framewise_displacement':
                    fd_values.append(value)
    need(fd_values, 'no_observed_fd')
    fd_sum = math.fsum(fd_values)
    need(math.isfinite(fd_sum), 'fd_sum_nonfinite')
    return dict(values=values, columns=columns, excluded=[v for v in columns if v not in names],
                missing=missing, fd_sum=fd_sum, fd_count=len(fd_values),
                fd_missing=fd_missing, mean_fd=fd_sum / len(fd_values))


def validate_method(method, schema, policy):
    need(method.get('task_id') == schema.get('task_id') == 'SOCIALBRAIN-001', 'document_task')
    need(method['source']['source_manifest_sha256'] == policy.source_sha, 'method_source_pin')
    need(schema.get('source_manifest_sha256') == policy.source_sha
         and schema.get('method_sha256') == policy.method_sha
         and schema.get('reporting_kernel_sha256') == policy.reporting_sha, 'schema_pins')
    frames = method['source']['frame_counts_by_subject']
    need(type(frames) is dict and set(frames) == set(policy.subject_ids)
         and all(type(v) is int and v >= 2 for v in frames.values()), 'frame_counts_unfrozen')
    need(method['source']['n_subjects'] == len(policy.subject_ids), 'method_cohort')
    need(method['activity']['relative_threshold'] == 1e-12, 'activity_method')
    unit = method['source']['spatial_unit_policy']
    need(unit['world_coordinate_unit'] == 'mm' and all(type(unit[key]) is list
         and unit[key] and set(unit[key]) <= {'mm', 'unknown'} for key in
         ('allowed_bold_header_units', 'allowed_template_header_units')), 'spatial_policy_unfrozen')
    need(type(method['confounds']['missingness']['missing_tokens']) is list, 'missing_tokens_unfrozen')
    return frames, unit


def reconstruct(data_dir='/app/data/socialbrain', manifest_path='/app/source_manifest.json',
                method_path='/app/method_contract.json', schema_path='/app/output_schema.json',
                *, pilot=False, _policy=None):
    """Pilot authenticates all sources; decodes only the first subject's BOLD."""
    need(type(pilot) is bool, 'pilot_boolean')
    policy = production_policy() if _policy is None else _policy  # explicit manufactured API only
    need(all(type(pin) is str and re.fullmatch('[0-9a-f]{64}', pin) for pin in
             (policy.source_sha, policy.method_sha, policy.schema_sha, policy.reporting_sha)), 'unfrozen_pin')
    modules = load_modules(policy)
    h, n, kernel = (modules[key] for key in ('inspect_structure', 'source_numerics', 'reporting_kernel'))
    import numpy as np
    from scipy import linalg, stats
    started = time.monotonic()

    def check():
        need(time.monotonic() - started < policy.wall_seconds, 'source_deadline')

    method_raw = exact_read(method_path, policy.method_sha, 4 * 1024**2)
    schema_raw = exact_read(schema_path, policy.schema_sha, 4 * 1024**2)
    method, schema = h.strict_json(method_raw), h.strict_json(schema_raw)
    frames, unit_policy = validate_method(method, schema, policy)
    source, manifest_path = h.safe_path(data_dir), h.safe_path(manifest_path)
    auth = h.Policy(policy.source_sha, policy.versions, participant_ids=policy.subject_ids)
    manifest, rows, originals, opaque, versions = h.frozen_manifest(source, manifest_path, auth)
    h.closed_inventory(source, rows, check)
    buffers, signatures = {}, {}
    for path, row in rows.items():
        buffers[path], signatures[path] = h.authenticated_bytes(source / path, row, check, retain=True)
    # Nothing scientific has been parsed until this complete authenticated pass.
    keyed = {(row['role'], row.get('participant_id')): path for path, row in rows.items()
             if row['role'] in ('bold', 'confounds', 'participants', 'template')}
    need(sum(row['role'] == 'template' for row in rows.values()) == 1, 'one_template')
    template_path = keyed['template', None]
    template_row = rows[template_path]
    need(method['global_signal']['template_sha256'] == template_row['sha256'], 'method_template_pin')
    template_header, offset, dtype = header(buffers[template_path], 3, h, auth, check)
    need(template_header['spatial_units'] in unit_policy['allowed_template_header_units'], 'template_units')
    template = decode_values(buffers[template_path], template_header, offset, dtype, policy, check)
    normalized, maximum = n.normalize_template(template)
    del normalized
    phenotype = h.phenotype(buffers[keyed['participants', None]], auth)
    need(all(row['age_kind'] == 'finite' and row['group_known'] for row in phenotype['selected']), 'phenotype_values')
    need(phenotype['group_token_counts'] == method['source']['expected_group_counts'], 'group_counts')
    demographics = {row['participant_id']: row for row in phenotype['selected']}
    rois = method['roi_geometry']['rois']
    roi_ids = [row['roi_id'] for row in rois]
    need(tuple(roi_ids) == kernel.ROI_IDS, 'roi_ids')
    pipelines = method['temporal_cleaning']['pipeline_ids']
    need(tuple(pipelines) == kernel.PIPELINE_IDS, 'pipeline_ids')
    names = method['confounds']['columns']
    need(tuple(names) == h.NUISANCE, 'confound_names')
    selected = policy.subject_ids[:1] if pilot else policy.subject_ids
    persons, covariates, cohort, source_people, analysis_people = {}, {}, [], [], []
    geometry = {}
    for sid in policy.subject_ids:
        check()
        bold_path, conf_path = keyed['bold', sid], keyed['confounds', sid]
        observed, offset, dtype = header(buffers[bold_path], 4, h, auth, check)
        need(observed['shape'][3] == frames[sid], 'source_frame_count')
        need(observed['spatial_units'] in unit_policy['allowed_bold_header_units'], 'bold_units')
        c = confounds(buffers[conf_path], h, auth, names, method['confounds']['missingness'], frames[sid])
        cov = dict(age=demographics[sid]['age'], group=demographics[sid]['group_token'], mean_fd=c['mean_fd'])
        covariates[sid] = cov
        cohort.append(dict(subject_id=sid, **cov, mean_fd_observed_count=c['fd_count'],
                           mean_fd_missing_frame_indices=c['fd_missing']))
        shape, affine = tuple(observed['shape'][:3]), np.asarray(observed['selected_affine'], dtype=np.float64)
        geometry_key = (shape, affine.tobytes())
        if geometry_key not in geometry:
            support = n.sphere_supports(shape, affine, [r['center_mm'] for r in rois], method['roi_geometry']['radius_mm'])
            gs = n.global_support(template, template_header['selected_affine'], shape, affine)
            geometry[geometry_key] = (support, gs['indices'])
        support, gs_indices = geometry[geometry_key]
        roi_supports = [dict(roi_id=rid, n_voxels=int(indices.size),
                            support_sha256=n.support_digest(shape, affine, indices)) for rid, indices in zip(roi_ids, support)]
        global_support = dict(n_voxels=int(gs_indices.size), support_sha256=n.support_digest(shape, affine, gs_indices))
        source_people.append(dict(subject_id=sid, bold_path=bold_path, confounds_path=conf_path,
            bold_header=observed, frame_count=frames[sid], confound_column_names=c['columns'],
            selected_confound_columns=list(names), excluded_confound_columns=c['excluded'],
            missing_selected_entries=c['missing'], mean_fd_sum=c['fd_sum'], mean_fd_observed_count=c['fd_count'],
            roi_supports=roi_supports, global_support=global_support))
        if sid not in selected:
            continue
        values = decode_values(buffers[bold_path], observed, offset, dtype, policy, check)
        raw_roi, global_signal = n.extract_raw_and_gs(values, support, gs_indices)
        del values
        results = [n.clean_roi(raw_roi, nuisance, activity_fn=kernel.residual_active) for nuisance in
                   (c['values'], np.column_stack([c['values'], global_signal]))]
        persons[sid] = dict(raw_roi=raw_roi, global_signal=global_signal,
            cleaned_roi=np.stack([r['cleaned'] for r in results], axis=1),
            canonical_active=np.stack([r['active'] for r in results]), frame_indices=np.arange(frames[sid], dtype=np.int64))
        diagnostics = []
        for pipeline, result in zip(pipelines, results):
            activity = [dict(roi_id=rid, raw_centered_l2=float(result['raw_centered_l2'][j]),
                residual_centered_l2=float(result['residual_centered_l2'][j]),
                activity_threshold=float(result['activity_threshold'][j]), active=bool(result['active'][j]))
                for j, rid in enumerate(roi_ids)]
            diagnostics.append(dict(pipeline_id=pipeline, cleaning_rank=result['rank'], roi_activity=activity,
                                    n_active_rois=int(result['active'].sum())))
        analysis_people.append(dict(subject_id=sid, pipelines=diagnostics))
    # Canonical covariate-only design rank, never a source connectivity endpoint.
    motion = np.array([covariates[sid]['mean_fd'] for sid in policy.subject_ids if covariates[sid]['group'] == 'child'])
    need(motion.size > 0, 'no_children')
    design = np.column_stack([np.ones(motion.size), stats.rankdata(motion, method='average')])
    _, singular, _ = linalg.svd(design, full_matrices=False, lapack_driver='gesvd')
    rank = int(np.sum(singular > max(design.shape) * np.finfo(np.float64).eps * singular[0]))
    # Recheck all source hashes, signatures and closed membership after consumption.
    h.closed_inventory(source, rows, check)
    for path, row in rows.items():
        _, after = h.authenticated_bytes(source / path, row, check)
        need(after == signatures[path], 'source_changed_after_consumption')
    h.frozen_manifest(source, manifest_path, auth)
    exact_read(method_path, policy.method_sha, 4 * 1024**2)
    exact_read(schema_path, policy.schema_sha, 4 * 1024**2)
    return dict(status='resource_pilot' if pilot else 'complete', subject_ids=list(selected),
        roi_ids=roi_ids, pipeline_ids=pipelines, persons=persons, covariates=covariates, cohort=cohort,
        roi_definitions=[dict(**r, radius_mm=method['roi_geometry']['radius_mm']) for r in rois],
        source_files=[dict(path=path, role=row['role'], subject_id=row.get('participant_id'),
                           size_bytes=row['size_bytes'], sha256=row['sha256']) for path, row in rows.items()],
        source_observed=dict(participants_column_names=phenotype['columns'],
            template=dict(path=template_path, sha256=template_row['sha256'], header=template_header,
                normalization=dict(dtype='float32', operator='divide_by_global_maximum', maximum=maximum)),
            persons=source_people, frame_alignment='All released frames kept in original row order; measured movie onset is not asserted.'),
        analysis_observed=dict(persons=analysis_people, child_motion_nuisance_rank=rank),
        pins=dict(source_manifest_sha256=policy.source_sha, method_sha256=policy.method_sha,
                  output_schema_sha256=policy.schema_sha, reporting_kernel_sha256=policy.reporting_sha),
        method=method, schema=schema, warnings=[])
