"""Manufactured GIFTI/CIFTI and authentication fixtures; no original input."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('source193', Path(__file__).with_name('source_reference.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
IDS = (1, 2, 3, 4)


def gii(values, hemi, sphere=False):
    arrays = [nib.gifti.GiftiDataArray(np.asarray(values, dtype=np.float32), intent='NIFTI_INTENT_POINTSET' if sphere else 'NIFTI_INTENT_SHAPE')]
    if sphere:
        arrays.append(nib.gifti.GiftiDataArray(np.array([[0, 1, 2]], dtype=np.int32), intent='NIFTI_INTENT_TRIANGLE'))
    return nib.gifti.GiftiImage(darrays=arrays, meta=nib.gifti.GiftiMetaData({'AnatomicalStructurePrimary': 'CortexLeft' if hemi == 'L' else 'CortexRight'})).to_bytes()


def atlas_bytes(brain=None, labels=None, table=None, reverse_axes=False):
    if brain is None:
        left = nib.cifti2.BrainModelAxis.from_surface(np.array([4, 0, 2]), 5, name='CortexLeft')
        right = nib.cifti2.BrainModelAxis.from_surface(np.array([5, 1, 3]), 6, name='CortexRight')
        brain = right + left  # compressed and deliberately right-first
    if labels is None: labels = np.array([3, 4, 4, 1, 2, 1], dtype=np.int32)
    if table is None:
        table = {0: ('background', (0., 0., 0., 0.)), **{pid: (f'7Networks_{"L" if pid <= 2 else "R"}H_Vis_{pid}', (1., 0., 0., 1.)) for pid in IDS}}
    label = nib.cifti2.LabelAxis(['manufactured'], [table])
    axes = (brain, label) if reverse_axes else (label, brain)
    data = labels[:, None] if reverse_axes else labels[None, :]
    return nib.Cifti2Image(data, nib.cifti2.Cifti2Header.from_axes(axes)).to_bytes()


def fixture_payloads():
    left = np.array([[1., 0., 1.], [1., 1., 1.], [0., 1., 1.], [-1., 0., 1.], [0., -1., 1.]])
    right = np.array([[1., 0., 2.], [1., 1., 2.], [0., 1., 2.], [-1., 0., 2.], [0., -1., 2.], [1., -1., 2.]])
    return dict(gradient_l=gii([10, 90, 20, 80, 30], 'L'), gradient_r=gii([50, 4, 60, 8, 70, 12], 'R'),
                thickness_l=gii([1, 9, 2, 8, 4], 'L'), thickness_r=gii([5, 2, 6, 6, 7, 8], 'R'),
                sphere_l=gii(left, 'L', True), sphere_r=gii(right, 'R', True), atlas=atlas_bytes())


def test_keyed_join_not_position_or_hemisphere_half():
    structure = m.inspect_sources(fixture_payloads(), IDS)
    assert structure['hemisphere'].tolist() == [0, 0, 1, 1]
    assert [x.tolist() for x in structure['supports']] == [[2, 4], [0], [5], [1, 3]]
    result = m.reduce_parcels(structure)
    np.testing.assert_array_equal(result['maps'], [[25, 3], [10, 1], [12, 8], [6, 4]])
    np.testing.assert_allclose(np.linalg.norm(result['centroids'], axis=1), 100)
    assert result['support_n'].tolist() == [2, 1, 1, 2]
    assert result['support_sha256'][0] == hashlib.sha256(b'MAPREL_support_v2\nL\n'+np.array([2, 4], dtype='<i8').tobytes()).hexdigest()


def test_axis_order_is_discovered():
    p = fixture_payloads(); p['atlas'] = atlas_bytes(reverse_axes=True)
    r = m.reduce_parcels(m.inspect_sources(p, IDS))
    np.testing.assert_array_equal(r['maps'], [[25, 3], [10, 1], [12, 8], [6, 4]])
    assert r['source_observed']['atlas']['brain_model_axis_index'] == 0


def test_support_counts_are_original_supported_vertices_not_parcel_means():
    payloads = fixture_payloads()
    # Vertex 1 on the left is an unsupported zero and must not enter counts.
    payloads['gradient_l'] = gii([0, 0, 20, 80, 30], 'L')
    payloads['thickness_r'] = gii([5, 2, 6, 0, 7, 8], 'R')
    result = m.reduce_parcels(m.inspect_sources(payloads, IDS))
    assert result['source_map_support'] == [
        dict(map_id=key, included_vertices=6, finite_vertices=6,
             nonfinite_vertices=0, zero_vertices=1)
        for key in ('gradient2', 'thickness')]
    np.testing.assert_array_equal(result['maps'], [[25, 3], [0, 1], [12, 8], [6, 1]])


def test_structure_only_never_reduces(monkeypatch):
    monkeypatch.setattr(m, 'reduce_parcels', lambda *a: pytest.fail('reduction'))
    s = m.inspect_sources(fixture_payloads(), IDS)
    assert 'maps' not in s and 'centroids' not in s


@pytest.mark.parametrize('kind', ['gradient', 'thickness'])
def test_nonfinite_unused_vertices_are_not_dropped_parcels(kind):
    p = fixture_payloads(); vals = np.array([10., np.nan, 20., np.inf, 30.])
    p[kind+'_l'] = gii(vals, 'L')
    s = m.inspect_sources(p, IDS)
    assert len(s['parcel_ids']) == 4


@pytest.mark.parametrize('value', [np.nan, np.inf, -np.inf])
def test_nonfinite_used_vertex_fails(value):
    p = fixture_payloads(); p['gradient_l'] = gii([value, 90, 20, 80, 30], 'L')
    with pytest.raises(ValueError, match='nonfinite_supported_map'): m.inspect_sources(p, IDS)


def test_wrong_declared_hemisphere_fails():
    p = fixture_payloads(); p['gradient_l'] = gii([1, 2, 3, 4, 5], 'R')
    with pytest.raises(ValueError, match='hemisphere_declaration'): m.inspect_sources(p, IDS)


def test_full_surface_size_mismatch():
    p = fixture_payloads(); p['gradient_l'] = gii([1, 2, 3, 4], 'L')
    with pytest.raises(ValueError, match='full_surface_alignment'): m.inspect_sources(p, IDS)


def test_label_zero_and_unrepresented_vertices_are_excluded():
    p = fixture_payloads(); p['atlas'] = atlas_bytes(labels=np.array([3, 4, 0, 1, 2, 1]))
    s = m.inspect_sources(p, IDS)
    assert s['source_observed']['atlas']['excluded_zero_entries'] == 1
    assert s['supports'][3].tolist() == [1]


@pytest.mark.parametrize('case', ['duplicate_vertex', 'outside_vertex', 'mixed_parcel', 'missing_label', 'wrong_name'])
def test_structural_failures(case):
    p = fixture_payloads()
    left = nib.cifti2.BrainModelAxis.from_surface(np.array([4, 0, 2]), 5, name='CortexLeft')
    right = nib.cifti2.BrainModelAxis.from_surface(np.array([5, 1, 3]), 6, name='CortexRight')
    b = right+left; labels = np.array([3, 4, 4, 1, 2, 1])
    if case == 'duplicate_vertex': b.vertex[-1] = 4
    if case == 'outside_vertex': b.vertex[-1] = 5
    if case == 'mixed_parcel': labels[0] = 1; labels[1] = 3
    if case == 'missing_label': labels[0] = 4
    if case == 'wrong_name':
        table = {0: ('background', (0, 0, 0, 0)), **{i: (f'7Networks_RH_Vis_{i}', (1, 0, 0, 1)) for i in IDS}}
        p['atlas'] = atlas_bytes(b, labels, table)
    else: p['atlas'] = atlas_bytes(b, labels)
    with pytest.raises(ValueError): m.inspect_sources(p, IDS)


def test_noncortical_nonzero_rejected_but_zero_allowed():
    p = fixture_payloads()
    left = nib.cifti2.BrainModelAxis.from_surface(np.array([4, 0, 2]), 5, name='CortexLeft')
    right = nib.cifti2.BrainModelAxis.from_surface(np.array([5, 1, 3]), 6, name='CortexRight')
    mask = np.ones((1, 1, 1), dtype=bool)
    sub = nib.cifti2.BrainModelAxis.from_mask(mask, name='ThalamusLeft')
    b = right+left+sub
    p['atlas'] = atlas_bytes(b, np.array([3, 4, 4, 1, 2, 1, 0]))
    assert len(m.inspect_sources(p, IDS)['parcel_ids']) == 4
    p['atlas'] = atlas_bytes(b, np.array([3, 4, 4, 1, 2, 1, 1]))
    with pytest.raises(ValueError, match='noncortical_label_support'): m.inspect_sources(p, IDS)


def test_zero_centroid_fails_without_pole_rescue():
    s = m.inspect_sources(fixture_payloads(), IDS)
    s['values']['sphere_l'][[2, 4]] = [[1, 0, 0], [-1, 0, 0]]
    with pytest.raises(ValueError, match='supported_centroid'): m.reduce_parcels(s)


def write_bundle(tmp_path, payloads=None):
    payloads = fixture_payloads() if payloads is None else payloads
    root = tmp_path/'data'; root.mkdir()
    files = []
    for role, raw in payloads.items():
        name = role+'.source'; (root/name).write_bytes(raw)
        files.append(dict(role=role, path=name, size_bytes=len(raw), sha256=m.digest(raw)))
    manifest = dict(task_id='MAPREL-001', schema_version='maprel-source-v2', files=files)
    paths, pins = [], {}
    for key, value in [('source_manifest_sha256', manifest), ('method_contract_sha256', {'method':'manufactured'}), ('output_schema_sha256', {'schema':'manufactured'})]:
        path = tmp_path/(key+'.json'); raw = (json.dumps(value)+'\n').encode(); path.write_bytes(raw)
        paths.append(path); pins[key] = m.digest(raw)
        if key == 'source_manifest_sha256': (root/'source_manifest.json').write_bytes(raw)
    return root, paths, pins, manifest


def test_authenticates_all_members_before_decode(tmp_path, monkeypatch):
    root, paths, pins, _ = write_bundle(tmp_path)
    (root/'atlas.source').write_bytes(b'changed')
    monkeypatch.setattr(m, 'inspect_sources', lambda *a: pytest.fail('decoded before auth'))
    with pytest.raises(ValueError, match='source_size'): m.reconstruct(root, *paths, pins)


def test_complete_authenticated_bytes(tmp_path):
    root, paths, pins, manifest = write_bundle(tmp_path)
    raw, records, docs = m.authenticated_bundle(root, *paths, pins)
    assert raw == fixture_payloads() and len(records) == 7
    assert all(set(r) == {'role', 'path', 'size_bytes', 'sha256'} for r in records)
    assert docs['source_manifest_sha256'] == manifest


@pytest.mark.parametrize('case', ['wrong_pin', 'same_size_wrong_bytes', 'symlink_file', 'symlink_ancestor'])
def test_authentication_negatives(tmp_path, case):
    root, paths, pins, _ = write_bundle(tmp_path)
    if case == 'wrong_pin': pins['source_manifest_sha256'] = '0'*64
    if case == 'same_size_wrong_bytes':
        p = root/'gradient_l.source'; p.write_bytes(b'x'*p.stat().st_size)
    if case == 'symlink_file':
        p = root/'gradient_l.source'; saved = root/'saved'; p.rename(saved); p.symlink_to(saved)
    if case == 'symlink_ancestor':
        link = tmp_path/'link'; link.symlink_to(root, target_is_directory=True); root = link
    with pytest.raises(ValueError): m.authenticated_bundle(root, *paths, pins)


@pytest.mark.parametrize('case', ['duplicate_role', 'duplicate_path', 'traversal', 'boolean_size', 'oversized', 'missing_role'])
def test_manifest_guards(tmp_path, case):
    root, paths, pins, manifest = write_bundle(tmp_path)
    row = manifest['files'][0]
    if case == 'duplicate_role': manifest['files'][1]['role'] = row['role']
    if case == 'duplicate_path': manifest['files'][1]['path'] = row['path']
    if case == 'traversal': row['path'] = '../outside'
    if case == 'boolean_size': row['size_bytes'] = True
    if case == 'oversized': row['size_bytes'] = m.MAX_FILE+1
    if case == 'missing_role': row['role'] = 'other'
    raw = json.dumps(manifest).encode(); paths[0].write_bytes(raw); pins['source_manifest_sha256'] = m.digest(raw)
    with pytest.raises(ValueError): m.authenticated_bundle(root, *paths, pins)


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}'])
def test_strict_json(raw):
    with pytest.raises(ValueError): m.strict_json(raw)


def test_snapshot_cannot_follow_later_file_mutation(tmp_path):
    p = tmp_path/'small'; p.write_bytes(b'original')
    raw = m.frozen_bytes(p, m.digest(b'original'), 8)
    p.write_bytes(b'replaced')
    assert raw == b'original'


@pytest.mark.parametrize('case', ['extra_file', 'extra_directory', 'extra_symlink', 'extra_fifo', 'missing_internal', 'wrong_internal'])
def test_closed_inventory(tmp_path, case):
    import os
    root, paths, pins, _ = write_bundle(tmp_path)
    p = root/'extra'
    if case == 'extra_file': p.write_text('extra')
    if case == 'extra_directory': p.mkdir()
    if case == 'extra_symlink': p.symlink_to(root/'missing')
    if case == 'extra_fifo': os.mkfifo(p)
    if case == 'missing_internal': (root/'source_manifest.json').unlink()
    if case == 'wrong_internal': (root/'source_manifest.json').write_text('{}')
    with pytest.raises(ValueError): m.authenticated_bundle(root, *paths, pins)


@pytest.mark.parametrize('case', ['external', 'huge', 'entity', 'wrong_count', 'wrong_encoding', 'truncated_data'])
def test_gifti_predecode_guards(case, monkeypatch):
    raw = gii([1, 2, 3, 4, 5], 'L')
    if case == 'external': raw = raw.replace(b'ExternalFileName=""', b'ExternalFileName="/never/read"')
    if case == 'huge': raw = raw.replace(b'Dim0="5"', b'Dim0="9999999"')
    if case == 'entity': raw = b'<!ENTITY x "x">'+raw
    if case == 'wrong_count': raw = raw.replace(b'NumberOfDataArrays="1"', b'NumberOfDataArrays="2"')
    if case == 'wrong_encoding': raw = raw.replace(b'GZipBase64Binary', b'ExternalFileBinary')
    if case == 'truncated_data': raw = raw.replace(b'Dim0="5"', b'Dim0="4"')
    monkeypatch.setattr(nib.gifti.GiftiImage, 'from_bytes', lambda *a: pytest.fail('decoded unsafe GIFTI'))
    with pytest.raises(ValueError): m.gifti(raw, 'gradient_l', 'L')


def test_gifti_inert_system_dtd_is_removed_not_resolved():
    raw = gii([1, 2, 3, 4, 5], 'L')
    assert b'<!DOCTYPE' in raw
    clean = m.guard_gifti(raw)
    assert b'<!DOCTYPE' not in clean
    np.testing.assert_array_equal(m.gifti(raw, 'gradient_l', 'L')[0], [1, 2, 3, 4, 5])


@pytest.mark.parametrize('dtd', [b'<!DOCTYPE GIFTI [<!ELEMENT GIFTI ANY>]>', b'<!DOCTYPE GIFTI PUBLIC "x" "y">'])
def test_gifti_unreviewed_dtd_forms_fail(dtd):
    with pytest.raises(ValueError, match='gifti_xml_declarations'):
        m.guard_gifti(dtd + b'<GIFTI/>')
