"""Grader-owned authenticated BrainModelAxis join; no oracle/stager imports.

NiBabel format decoding and NumPy arithmetic are shared dependencies, not an
independent calibration of the spatial null. No import-time input access.
"""
from __future__ import annotations
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET
import zlib

import nibabel as nib
import numpy as np

SCIENCE = ('gradient_l', 'gradient_r', 'thickness_l', 'thickness_r',
           'sphere_l', 'sphere_r', 'atlas')
STRUCTURES = {'CIFTI_STRUCTURE_CORTEX_LEFT': 'L', 'CIFTI_STRUCTURE_CORTEX_RIGHT': 'R'}
NETWORKS = ('Vis', 'SomMot', 'DorsAttn', 'SalVentAttn', 'Limbic', 'Cont', 'Default')
MAX_FILE = 16 * 1024**2
MAX_TOTAL = 32 * 1024**2


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def bad(_):
        raise ValueError('nonfinite_json')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    def walk(v):
        if isinstance(v, float):
            need(math.isfinite(v), 'nonfinite_json')
        elif isinstance(v, dict):
            for x in v.values(): walk(x)
        elif isinstance(v, list):
            for x in v: walk(x)
    walk(value)
    return value


def safe_path(value):
    raw = os.fspath(value)
    need(isinstance(raw, str) and raw.startswith('/') and '\0' not in raw
         and all(x not in ('.', '..') for x in raw.split('/')), 'absolute_lexical_path')
    p = Path(raw)
    for part in (*reversed(p.parents), p):
        if os.path.lexists(part):
            mode = part.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'source_symlink')
            need(part == p or stat.S_ISDIR(mode), 'source_ancestor')
    return p


def signature(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def frozen_bytes(path, expected_sha, size=None, cap=MAX_FILE):
    """Return the very bytes authenticated, not a path reopened by a decoder."""
    path = safe_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'bounded_regular_source')
    need(size is None or type(size) is int and before.st_size == size, 'exact_source_size')
    need(isinstance(expected_sha, str) and re.fullmatch('[0-9a-f]{64}', expected_sha), 'source_hash_format')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as f:
        need(signature(os.fstat(f.fileno())) == signature(before), 'source_replaced')
        raw = f.read(before.st_size + 1)
        need(len(raw) == before.st_size and digest(raw) == expected_sha, 'source_digest')
        need(signature(os.fstat(f.fileno())) == signature(before) == signature(path.lstat()), 'source_changed')
    return raw


def authenticated_bundle(data_dir, manifest_path, method_path, schema_path, pins):
    expected_keys = {'source_manifest_sha256', 'method_contract_sha256', 'output_schema_sha256'}
    need(set(pins) == expected_keys, 'contract_pin_keys')
    records, contract_bytes = {}, {}
    for key, path in [('source_manifest_sha256', manifest_path), ('method_contract_sha256', method_path),
                      ('output_schema_sha256', schema_path)]:
        contract_bytes[key] = frozen_bytes(path, pins[key], cap=1024**2)
        records[key] = strict_json(contract_bytes[key])
    manifest = records['source_manifest_sha256']
    need(manifest.get('task_id') == 'MAPREL-001' and manifest.get('schema_version') == 'maprel-source-v2', 'manifest_identity')
    files = manifest.get('files')
    need(isinstance(files, list) and 7 <= len(files) <= 32, 'source_member_count')
    root = safe_path(data_dir)
    need(root.is_dir(), 'source_root')
    roles, paths, total = set(), set(), 0
    for row in files:
        need(isinstance(row, dict), 'source_member_schema')
        role, name = row.get('role'), row.get('path')
        need(isinstance(role, str) and re.fullmatch('[a-z][a-z0-9_]{0,79}', role) and role not in roles, 'source_role')
        need(isinstance(name, str) and name and not name.startswith('/') and '\\' not in name
             and '\0' not in name and all(x not in ('', '.', '..') for x in name.split('/')) and name not in paths, 'source_member_path')
        need(type(row.get('size_bytes')) is int and 0 < row['size_bytes'] <= MAX_FILE, 'source_member_size')
        total += row['size_bytes']; roles.add(role); paths.add(name)
    need(total <= MAX_TOTAL and set(SCIENCE) <= roles, 'source_bundle_bounds')
    need('source_manifest.json' not in paths, 'reserved_manifest_path')
    expected_files = paths | {'source_manifest.json'}
    expected_dirs = {str(parent) for name in paths for parent in Path(name).parents if str(parent) != '.'}
    seen_files, seen_dirs = set(), set()
    def inventory(directory):
        for entry in os.scandir(directory):
            relative = Path(entry.path).relative_to(root).as_posix()
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISDIR(mode):
                need(relative in expected_dirs, 'unexpected_source_directory')
                seen_dirs.add(relative); inventory(entry.path)
            else:
                need(stat.S_ISREG(mode) and relative in expected_files, 'unexpected_source_member')
                seen_files.add(relative)
    inventory(root)
    need(seen_files == expected_files and seen_dirs == expected_dirs, 'closed_source_inventory')
    need(frozen_bytes(root/'source_manifest.json', pins['source_manifest_sha256'], cap=1024**2)
         == contract_bytes['source_manifest_sha256'], 'internal_manifest_identity')
    # Authenticate every science and documentary member before any format decode.
    payloads = {r['role']: frozen_bytes(root / r['path'], r['sha256'], r['size_bytes']) for r in files}
    identities = [{k: r[k] for k in ('role', 'path', 'size_bytes', 'sha256')}
                  for r in sorted(files, key=lambda row: row['path'])]
    return payloads, identities, records


def guard_gifti(raw):
    """Bound declared/encoded arrays and disallow external files before decoding."""
    need(0 < len(raw) <= MAX_FILE and b'<!ENTITY' not in raw.upper(), 'gifti_xml_declarations')
    # GIFTI writers emit an external SYSTEM DTD declaration. Strip only that
    # inert declaration, never resolve it; reject internal subsets/other DTDs.
    raw, n_dtd = re.subn(br'<!DOCTYPE\s+GIFTI\s+SYSTEM\s+([\x22\x27])[^\x22\x27\r\n<>\[\]]+\1\s*>', b'', raw)
    need(n_dtd <= 1 and b'<!DOCTYPE' not in raw.upper(), 'gifti_xml_declarations')
    root = ET.fromstring(raw)
    need(root.tag == 'GIFTI', 'gifti_xml_root')
    arrays = root.findall('DataArray')
    need(1 <= len(arrays) <= 2 and root.attrib.get('NumberOfDataArrays') == str(len(arrays)), 'gifti_declared_array_count')
    total = 0
    for arr in arrays:
        need(arr.attrib.get('ExternalFileName', '') == '' and arr.attrib.get('ExternalFileOffset', '') in ('', '0'), 'gifti_external_file')
        encoding = arr.attrib.get('Encoding')
        need(encoding in ('ASCII', 'Base64Binary', 'GZipBase64Binary'), 'gifti_encoding')
        ndim = arr.attrib.get('Dimensionality', '')
        need(ndim in ('1', '2'), 'gifti_declared_dimensions')
        shape = []
        for i in range(int(ndim)):
            token = arr.attrib.get('Dim'+str(i), '')
            need(re.fullmatch('[0-9]{1,7}', token) and 0 < int(token) <= 2_000_000, 'gifti_declared_shape')
            shape.append(int(token))
        count = math.prod(shape)
        need(count <= 2_000_000, 'gifti_declared_elements')
        try: dtype = np.dtype(nib.nifti1.data_type_codes.dtype[arr.attrib['DataType']])
        except (KeyError, TypeError, ValueError) as exc: raise ValueError('gifti_declared_dtype') from exc
        need(dtype.kind in 'iuf' and dtype.itemsize <= 8, 'gifti_declared_dtype')
        expected = count*dtype.itemsize; total += expected
        need(total <= MAX_FILE, 'gifti_decoded_cap')
        data = arr.findall('Data')
        need(len(data) == 1, 'gifti_data_element')
        if encoding != 'ASCII':
            encoded = ''.join((data[0].text or '').split())
            compressed = base64.b64decode(encoded, validate=True)
            if encoding == 'GZipBase64Binary':
                decoder = zlib.decompressobj()
                decoded = decoder.decompress(compressed, expected+1)
                need(decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data, 'gifti_compressed_bound')
            else: decoded = compressed
            need(len(decoded) == expected, 'gifti_exact_decoded_length')
    return raw


def gifti(raw, role, hemi):
    raw = guard_gifti(raw)
    image = nib.gifti.GiftiImage.from_bytes(raw)
    expected = 'CortexLeft' if hemi == 'L' else 'CortexRight'
    declarations = []
    for meta in [image.meta, *(x.meta for x in image.darrays)]:
        value = dict(meta).get('AnatomicalStructurePrimary')
        if value is not None:
            need(value == expected, 'gifti_hemisphere_declaration')
            declarations.append(value)
    arrays = []
    for arr in image.darrays:
        need(arr.data is not None and arr.data.dtype.kind in 'iuf' and arr.data.dtype.itemsize <= 8, 'gifti_numeric_array')
        need(arr.data.size <= 2_000_000, 'gifti_array_bound')
        transform = None
        if arr.coordsys is not None:
            matrix = np.asarray(arr.coordsys.xform, dtype=np.float64)
            need(matrix.shape == (4, 4) and np.isfinite(matrix).all(), 'gifti_transform')
            transform = dict(dataspace=int(arr.coordsys.dataspace), xformspace=int(arr.coordsys.xformspace), matrix=matrix.tolist())
        arrays.append(dict(intent=int(arr.intent), shape=list(arr.data.shape), dtype=arr.data.dtype.str,
                           metadata=dict(arr.meta), coordinate_system=transform))
    if role.startswith('sphere_'):
        points = [x for x in image.darrays if int(x.intent) == 1008]
        faces = [x for x in image.darrays if int(x.intent) == 1009]
        need(len(points) == 1 and len(faces) == 1 and len(image.darrays) == 2, 'sphere_intents')
        values = np.asarray(points[0].data, dtype=np.float64)
        triangles = np.asarray(faces[0].data)
        need(values.ndim == 2 and values.shape[1] == 3 and 2 <= len(values) <= 100000
             and np.isfinite(values).all(), 'sphere_coordinates')
        need(triangles.ndim == 2 and triangles.shape[1] == 3 and triangles.dtype.kind in 'iu'
             and triangles.size > 0 and np.all((triangles >= 0) & (triangles < len(values))), 'sphere_triangles')
    else:
        need(len(image.darrays) == 1 and int(image.darrays[0].intent) not in (1008, 1009), 'map_single_scalar_array')
        values = np.asarray(image.darrays[0].data, dtype=np.float64)
        if values.ndim == 2 and values.shape[1] == 1: values = values[:, 0]
        need(values.ndim == 1 and 2 <= len(values) <= 100000, 'map_vertex_shape')
    info = dict(role=role, hemisphere=hemi, metadata=dict(image.meta), arrays=arrays,
                vertex_count=len(values), declared_hemispheres=declarations)
    return values, info


def inspect_sources(payloads, expected_ids=tuple(range(1, 401))):
    """Decode support/geometry, not parcel means, correlations or rotations."""
    need(set(SCIENCE) <= set(payloads), 'science_inventory')
    values, observed = {}, {}
    for role in SCIENCE[:-1]:
        hemi = 'L' if role.endswith('_l') else 'R'
        values[role], observed[role] = gifti(payloads[role], role, hemi)
    atlas = nib.Cifti2Image.from_bytes(payloads['atlas'])
    need(len(atlas.shape) == 2 and math.prod(atlas.shape) <= 200000, 'cifti_shape')
    axes = [atlas.header.get_axis(i) for i in range(2)]
    label_axes = [i for i, a in enumerate(axes) if isinstance(a, nib.cifti2.LabelAxis)]
    brain_axes = [i for i, a in enumerate(axes) if isinstance(a, nib.cifti2.BrainModelAxis)]
    need(len(label_axes) == len(brain_axes) == 1 and label_axes != brain_axes, 'cifti_axis_types')
    label_index, brain_index = label_axes[0], brain_axes[0]
    labels_axis, brain = axes[label_index], axes[brain_index]
    need(len(labels_axis) == 1 and len(brain) == atlas.shape[brain_index], 'single_label_map')
    label_values = np.asarray(atlas.dataobj, dtype=np.float64)
    label_values = np.moveaxis(label_values, brain_index, 0).reshape(len(brain))
    need(np.isfinite(label_values).all() and np.equal(label_values, np.floor(label_values)).all(), 'integer_label_values')
    need(set(np.unique(label_values)) <= {0, *expected_ids}
         and set(np.unique(label_values)) - {0} == set(expected_ids), 'complete_label_support')
    labels = label_values.astype(np.int64)
    names = labels_axis.label[0]
    need(set(names) == {0, *expected_ids}, 'complete_label_table')
    cortex = np.isin(brain.name, list(STRUCTURES))
    need(np.all(labels[~cortex] == 0), 'noncortical_label_support')
    structure_records, joins = [], {}
    for name in dict.fromkeys(brain.name.tolist()):
        positions = np.flatnonzero(brain.name == name)
        row = dict(brain_structure=name, entries=len(positions), nonzero_entries=int(np.count_nonzero(labels[positions])))
        if name in STRUCTURES:
            hemi = STRUCTURES[name]; suffix = hemi.lower()
            full = brain.nvertices.get(name)
            need(type(full) is int and 2 <= full <= 100000, 'declared_full_surface')
            need(all(len(values[f'{kind}_{suffix}']) == full for kind in ('gradient', 'thickness', 'sphere')), 'full_surface_alignment')
            vertices = np.asarray(brain.vertex[positions])
            need(vertices.dtype.kind in 'iu' and len(np.unique(vertices)) == len(vertices)
                 and np.all((vertices >= 0) & (vertices < full)), 'unique_inrange_cortical_vertices')
            joins[hemi] = (positions, vertices)
            row.update(hemisphere=hemi, full_surface_vertices=full,
                       vertex_ids_sha256=digest(np.asarray(vertices, dtype='<i8').tobytes()))
        structure_records.append(row)
    need(set(joins) == {'L', 'R'}, 'both_cortical_hemispheres')
    supports, parcel_labels, networks, hemis = [], [], [], []
    for pid in expected_ids:
        entries = np.flatnonzero(labels == pid)
        structures = set(brain.name[entries].tolist())
        need(len(structures) == 1 and next(iter(structures)) in STRUCTURES, 'parcel_hemisphere_purity')
        hemi = STRUCTURES[next(iter(structures))]
        vertices = np.sort(np.asarray(brain.vertex[entries], dtype=np.int64))
        name = names[pid][0]
        need(isinstance(name, str) and bool(name), 'label_name')
        matches = [n for n in NETWORKS if name.startswith(f'7Networks_{hemi}H_{n}_')]
        need(len(matches) == 1, 'label_network_name')
        for kind in ('gradient', 'thickness'):
            need(np.isfinite(values[f'{kind}_{hemi.lower()}'][vertices]).all(), 'nonfinite_supported_map')
        supports.append(vertices); parcel_labels.append(name); networks.append(matches[0]); hemis.append(0 if hemi == 'L' else 1)
    observed['atlas'] = dict(shape=list(atlas.shape), label_axis_index=label_index,
                            brain_model_axis_index=brain_index, label_map_name=str(labels_axis.name[0]),
                            structures=structure_records, excluded_zero_entries=int(np.count_nonzero(labels == 0)),
                            label_keys=sorted(int(k) for k in names), cortical_join='brain_structure_and_local_vertex_id',
                            sphere_coordinate_transform='stored_pointset_no_transform',
                            map_support='nonzero_cortical_labels_no_imputation')
    return dict(values=values, supports=supports, labels=parcel_labels, networks=networks,
                hemisphere=np.asarray(hemis, dtype=np.int64), parcel_ids=np.asarray(expected_ids, dtype=np.int64),
                source_observed=observed)


def reduce_parcels(structure):
    ids, hemi, supports = structure['parcel_ids'], structure['hemisphere'], structure['supports']
    maps = np.empty((len(ids), 2), dtype=np.float64)
    centroids = np.empty((len(ids), 3), dtype=np.float64)
    support_hashes = []
    source_map_support = [dict(map_id=key, included_vertices=0, finite_vertices=0,
                               nonfinite_vertices=0, zero_vertices=0)
                          for key in ('gradient2', 'thickness')]
    for i, vertices in enumerate(supports):
        h = 'L' if hemi[i] == 0 else 'R'; suffix = h.lower()
        for j, kind in enumerate(('gradient', 'thickness')):
            samples = structure['values'][f'{kind}_{suffix}'][vertices]
            maps[i, j] = np.mean(samples, dtype=np.float64)
            receipt = source_map_support[j]
            receipt['included_vertices'] += len(samples)
            receipt['finite_vertices'] += int(np.count_nonzero(np.isfinite(samples)))
            receipt['nonfinite_vertices'] += int(np.count_nonzero(~np.isfinite(samples)))
            receipt['zero_vertices'] += int(np.count_nonzero(samples == 0))
        center = np.mean(structure['values'][f'sphere_{suffix}'][vertices], axis=0, dtype=np.float64)
        norm = np.linalg.norm(center)
        need(np.isfinite(center).all() and math.isfinite(norm) and norm > 0, 'supported_centroid')
        centroids[i] = center / norm * 100.
        support_hashes.append(digest(b'MAPREL_support_v2\n' + h.encode('ascii') + b'\n' + np.asarray(vertices, dtype='<i8').tobytes()))
    need(np.isfinite(maps).all() and np.isfinite(centroids).all(), 'finite_parcel_primitives')
    return dict(parcel_ids=ids, labels=structure['labels'], networks=structure['networks'], hemisphere=hemi,
                support_n=np.asarray([len(s) for s in supports], dtype=np.int64), support_sha256=support_hashes,
                centroids=centroids, maps=maps, source_observed=structure['source_observed'],
                source_map_support=source_map_support)


def reconstruct(data_dir, manifest_path, method_path, schema_path, pins):
    payloads, source_files, _ = authenticated_bundle(data_dir, manifest_path, method_path, schema_path, pins)
    result = reduce_parcels(inspect_sources(payloads))
    return dict(result, pins=dict(pins), source_files=source_files)
