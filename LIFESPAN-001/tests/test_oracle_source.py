"""Tiny manufactured GIFTI/annotation/phenotype files only; no originals."""
import hashlib
import json
import os
from pathlib import Path
import sys

import nibabel as nib
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'solution'))
import source_reader as source


def json_write(path, value):
    raw = json.dumps(value).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def surface(path, *, frames=4, vertices=8, nonfinite=False, timestep='1000.000000', dtype=np.float32, intent=2001):
    arrays = []
    for t in range(frames):
        data = np.arange(vertices, dtype=dtype) + t
        if nonfinite:
            data[0] = np.nan
        array = nib.gifti.GiftiDataArray(data.astype(dtype), intent=intent,
                                       meta=nib.gifti.GiftiMetaData({'TimeStep': timestep}))
        arrays.append(array)
    nib.save(nib.gifti.GiftiImage(darrays=arrays), path)


def annotation(path):
    names = [b'Unknown', b'Medial_wall', b'R1', b'R2']
    ctab = np.array([[0, 0, 0, 0], [25, 25, 25, 0], [32, 4, 7, 0], [9, 8, 10, 0]], dtype=np.int32)
    labels = np.array([1, 1, 2, 2, 3, 3, 2, 3])
    nib.freesurfer.write_annot(path, labels, ctab, names)


@pytest.fixture
def originals(tmp_path, monkeypatch):
    root = tmp_path / 'originals'
    for sub in ('surface', 'phenotype', 'atlas'):
        (root / sub).mkdir(parents=True)
    ids = ['A00000001', 'A00000002']
    files = []
    for subject in ids:
        for hemi in ('lh', 'rh'):
            name = f'{subject}_{hemi}.gii'
            surface(root / 'surface' / name)
            files.append(dict(path='surface/' + name, role='surface_timeseries', subject_id=subject,
                              hemisphere=hemi, original_filename=name))
    (root / 'phenotype/pheno.csv').write_text(',Age,Dominant Hand,Sex\nA00000001,20.1,R,F\nA00000002,30,L,M\nextra,not_analysed,,\n')
    files.append(dict(path='phenotype/pheno.csv', original_filename='pheno.csv', role='phenotype', subject_id=None, hemisphere=None))
    for hemi in ('lh', 'rh'):
        name = hemi + '.annot'
        annotation(root / 'atlas' / name)
        files.append(dict(path='atlas/' + name, original_filename=name, role='surface_annotation', subject_id=None, hemisphere=hemi))
    for row in files:
        raw = (root / row['path']).read_bytes()
        row.update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    manifest = {'files': files}
    monkeypatch.setattr(source, 'SOURCE_SHA256', json_write(root / 'source_manifest.json', manifest))
    cohort_path, method_path = tmp_path / 'cohort.json', tmp_path / 'method.json'
    monkeypatch.setattr(source, 'COHORT_SHA256', json_write(cohort_path, {'subject_ids': ids}))
    method = {'source_manifest_sha256': source.SOURCE_SHA256, 'cohort': {'manifest_sha256': source.COHORT_SHA256},
              'source_observed': {'phenotype_rows': 3}}
    monkeypatch.setattr(source, 'METHOD_SHA256', json_write(method_path, method))
    for key, value in [('EXPECTED_FILES', 7), ('EXPECTED_BYTES', sum(x['size_bytes'] for x in files)),
                       ('N_SUBJECTS', 2), ('N_FRAMES', 4), ('N_VERTICES', 8), ('N_HEMI_ROIS', 2)]:
        monkeypatch.setattr(source, key, value)
    return root, method_path, cohort_path, manifest


def test_exact_source_auth_and_independent_reader(originals):
    root, method, cohort, manifest = originals
    inputs = source.load_inputs(root, method, cohort)
    assert inputs['subject_ids'] == ['A00000001', 'A00000002']
    assert len(inputs['parcels']) == 4 and inputs['parcels'][0]['annotation_id'] == 2
    assert inputs['parcels'][0]['vertex_count'] == 3
    q, before, observed = source.read_subject(inputs, 'A00000001')
    assert q.shape == (4, 4) and q.dtype == np.float32 and before.dtype == np.float64
    assert observed['left_intents'] == observed['right_intents'] == [2001]
    assert inputs['phenotype']['A00000001']['age_computational'] == float(np.float32(20.1))
    assert len(inputs['phenotype']) == 3


@pytest.mark.parametrize('mode', ['manifest', 'method', 'cohort', 'corrupt', 'missing', 'extra', 'emptydir',
                                 'symlink', 'fifo', 'source_root_link', 'manifest_fifo'])
def test_sources_fail_before_any_scientific_parser(originals, monkeypatch, mode):
    root, method, cohort, manifest = originals
    first = root / manifest['files'][0]['path']
    monkeypatch.setattr(source, 'read_phenotype', lambda *a: pytest.fail('parsed unauthenticated source'))
    if mode in ('manifest', 'method', 'cohort'):
        path = {'manifest': root / 'source_manifest.json', 'method': method, 'cohort': cohort}[mode]
        path.write_bytes(path.read_bytes() + b' ')
    elif mode == 'corrupt':
        raw = first.read_bytes(); first.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    elif mode == 'missing':
        first.unlink()
    elif mode == 'extra':
        (root / 'extra').write_bytes(b'x')
    elif mode == 'emptydir':
        (root / 'empty').mkdir()
    elif mode == 'symlink':
        first.unlink(); first.symlink_to(method)
    elif mode == 'fifo':
        first.unlink(); os.mkfifo(first)
    elif mode == 'source_root_link':
        link = root.with_name('source_link'); link.symlink_to(root, target_is_directory=True); root = link
    else:
        path = root / 'source_manifest.json'; path.unlink(); os.mkfifo(path)
    with pytest.raises((ValueError, FileNotFoundError)):
        source.load_inputs(root, method, cohort)


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":{"n":1e999}}'])
def test_authenticated_json_strict_even_with_correct_pin(tmp_path, raw):
    path = tmp_path / 'input.json'; path.write_bytes(raw)
    with pytest.raises(ValueError):
        source.authenticated_json(path, hashlib.sha256(raw).hexdigest())


def test_hash_and_parse_same_json_bytes(tmp_path, monkeypatch):
    path = tmp_path / 'input.json'; raw = b'{"genuine":true}'; path.write_bytes(raw)
    reader = source.bounded_read
    def swap(p, n):
        out = reader(p, n); path.write_bytes(b'{"genuine":false}'); return out
    monkeypatch.setattr(source, 'bounded_read', swap)
    assert source.authenticated_json(path, hashlib.sha256(raw).hexdigest()) == {'genuine': True}


@pytest.mark.parametrize('mode', ['frame', 'vertex', 'dtype', 'intent', 'timestep', 'nonfinite', 'external'])
def test_decoding_structural_and_finite_preconditions(originals, tmp_path, monkeypatch, mode):
    path = tmp_path / 'tiny.gii'
    kw = {}
    if mode == 'frame': kw['frames'] = 3
    if mode == 'vertex': kw['vertices'] = 7
    if mode == 'dtype': kw['dtype'] = np.int32
    if mode == 'intent': kw['intent'] = 0
    if mode == 'timestep': kw['timestep'] = '.645'
    if mode == 'nonfinite': kw['nonfinite'] = True
    surface(path, **kw)
    if mode == 'external':
        original = nib.load
        def altered(*a, **k):
            image = original(*a, **k); image.darrays[0].ext_fname = 'forbidden'; return image
        monkeypatch.setattr(nib, 'load', altered)
    with pytest.raises(ValueError):
        source.decode_surface(path)


@pytest.mark.parametrize('age', ['NaN', 'inf', '-2', '1e1000', 'bad'])
def test_selected_age_failure(tmp_path, age):
    path = tmp_path / 'pheno.csv'
    path.write_text(f',Age,Dominant Hand,Sex\nS,{age},R,F\n')
    with pytest.raises(ValueError):
        source.read_phenotype(path, ['S'])


@pytest.mark.parametrize('rows', ['S,20,R,F\nS,22,L,M', 'T,22,R,F', 'S,20,R,', 'S,20,R,F,extra'])
def test_phenotype_join_or_sex_failure(tmp_path, rows):
    path = tmp_path / 'pheno.csv'; path.write_text(',Age,Dominant Hand,Sex\n' + rows + '\n')
    with pytest.raises(ValueError):
        source.read_phenotype(path, ['S'])


@pytest.mark.parametrize('mode', ['unassigned', 'unknown', 'duplicate_name', 'wrong_table', 'empty_roi'])
def test_annotation_labels_not_silently_reinterpreted(originals, monkeypatch, mode):
    root, _, _, _ = originals
    reader = nib.freesurfer.read_annot
    def altered(*a, **k):
        labels, table, names = reader(*a, **k)
        if mode == 'unassigned': labels[0] = -1
        elif mode == 'unknown': labels[0] = 123
        elif mode == 'duplicate_name': names[3] = names[2]
        elif mode == 'wrong_table': table[2, 4] += 1
        else: labels[labels == table[2, 4]] = table[1, 4]
        return labels, table, names
    monkeypatch.setattr(nib.freesurfer, 'read_annot', altered)
    with pytest.raises(ValueError):
        source.read_annotation(root / 'atlas/lh.annot', 'lh', 0)


def test_original_manifest_pin_is_declared_in_code():
    assert source.SOURCE_SHA256 == '18fd1271190687765461243943ced2b82d5d5fb703c3d675a2f7586992b5f932'
    assert source.METHOD_SHA256 == '47c9450cfee4db7140aee2a269510644dde6a3388dfeea9deee2f1f5ae466471'
