"""Manufactured files only. Never discover or open original scientific inputs."""
import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

import source_reconstruction as s


def make_nifti(shape=(3, 4, 5, 7), affine=None, endian='<', dtype=np.float32, units=('mm', 'sec')):
    h = nib.Nifti1Header(endianness=endian)
    h.set_data_shape(shape); h.set_data_dtype(dtype)
    h.set_zooms((2., 2., 2.) + ((2.,) if len(shape) == 4 else ()))
    h.set_xyzt_units(*units)
    h.set_sform(np.diag([2., 2., 2., 1.]) if affine is None else affine, code=4)
    h['vox_offset'] = 352; h['scl_slope'] = 1; h['scl_inter'] = 0
    return h, h.binaryblock + b'\0' * 4


def hashes(raw):
    return dict(sha256=hashlib.sha256(raw).hexdigest(), md5=hashlib.md5(raw).hexdigest(),
                git=hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest())


def fixture_bundle(tmp_path, monkeypatch, people=('sub-0002',)):
    monkeypatch.setattr(s, 'IDS', people)
    root = tmp_path / 'originals'; root.mkdir()
    rows = []
    for person, role in sorted([(p, r) for p in people for r in s.PERSON_ROLES] +
                               [(None, r) for r in s.SINGLE_ROLES], key=str):
        path = f'{person or "metadata"}/{role}.bin'
        raw = (path + '\n').encode()
        p = root / path; p.parent.mkdir(exist_ok=True); p.write_bytes(raw)
        digest = hashes(raw)
        annex = role in {'bold', 'atlas_image'}
        rows.append(dict(path=path, role=role, participant_id=person, size_bytes=len(raw),
                         sha256=digest['sha256'], md5=digest['md5'] if annex else None,
                         identity_kind='published_annex_payload_md5' if annex else 'git_blob_content',
                         content_git_blob_sha1=None if annex else digest['git'],
                         source_git_blob_sha1='e' * 40 if annex else digest['git'],
                         source_git_mode='120000' if annex else '100644',
                         source_commit=s.ATLAS_COMMIT if role.startswith('atlas_') else s.DATA_COMMIT))
    m = dict(dataset_id='ds002790', dataset_release='2.0.0', dataset_commit=s.DATA_COMMIT,
             templateflow_commit=s.ATLAS_COMMIT, selected_participant_ids=list(people),
             files=rows, file_count=len(rows), total_bytes=sum(r['size_bytes'] for r in rows))
    manifest = tmp_path / 'manifest.json'
    return root, manifest, m


def save_manifest(path, m):
    raw = json.dumps(m).encode(); path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_complete_131_identity_no_parser(tmp_path, monkeypatch):
    people = s.IDS
    root, manifest, m = fixture_bundle(tmp_path, monkeypatch, people)
    monkeypatch.setattr(s, 'read_header', lambda *_: pytest.fail('no parsing during authentication'))
    actual, rows, sig = s.authenticate(root, manifest, save_manifest(manifest, m))
    assert len(actual['files']) == len(rows) == len(sig) == 131


@pytest.mark.parametrize('mutation,error', [
    ('sha_null', 'completed_measured'), ('sha_wrong', 'source_sha256'), ('md5', 'source_published_md5'),
    ('git', 'source_git_blob'), ('duplicate_path', 'duplicate_source_path'),
    ('duplicate_key', 'duplicate_source_key'), ('escape', 'unsafe_relative_path'),
    ('absolute', 'unsafe_relative_path'), ('backslash', 'unsafe_relative_path'),
    ('commit', 'source_commits'), ('cohort', 'cohort_identity'), ('role', 'source_role_membership'),
    ('size', 'source_size'), ('pointer_as_content', 'annex_payload_identity'), ('extra_dir', 'closed_source_inventory'),
    ('extra_file', 'closed_source_inventory'), ('symlink', 'nonregular_inventory_member'),
    ('fifo', 'nonregular_inventory_member')])
def test_auth_fail_closed(tmp_path, monkeypatch, mutation, error):
    root, manifest, m = fixture_bundle(tmp_path, monkeypatch)
    annex = next(r for r in m['files'] if r['identity_kind'] == 'published_annex_payload_md5')
    regular = next(r for r in m['files'] if r['identity_kind'] == 'git_blob_content')
    if mutation == 'sha_null': annex['sha256'] = None
    elif mutation == 'sha_wrong': annex['sha256'] = 'f' * 64
    elif mutation == 'md5': annex['md5'] = 'f' * 32
    elif mutation == 'git': regular['content_git_blob_sha1'] = regular['source_git_blob_sha1'] = 'f' * 40
    elif mutation == 'duplicate_path': m['files'][1]['path'] = m['files'][0]['path']
    elif mutation == 'duplicate_key': m['files'][1].update(role=m['files'][0]['role'], participant_id=m['files'][0]['participant_id'])
    elif mutation == 'escape': annex['path'] = '../escape'
    elif mutation == 'absolute': annex['path'] = '/escape'
    elif mutation == 'backslash': annex['path'] = 'a\\b'
    elif mutation == 'commit': m['dataset_commit'] = '0' * 40
    elif mutation == 'cohort': m['selected_participant_ids'] = ['sub-9999']
    elif mutation == 'role': next(r for r in m['files'] if r['participant_id'] is not None and r['role'] == 'events')['role'] = 'unknown'
    elif mutation == 'size': annex['size_bytes'] += 1; m['total_bytes'] += 1
    elif mutation == 'pointer_as_content': annex['content_git_blob_sha1'] = annex['source_git_blob_sha1']
    elif mutation == 'extra_dir': (root / 'empty').mkdir()
    elif mutation == 'extra_file': (root / 'extra').write_bytes(b'extra')
    elif mutation == 'symlink': (root / 'extra').symlink_to(tmp_path / 'absent')
    elif mutation == 'fifo': os.mkfifo(root / 'extra')
    with pytest.raises(ValueError, match=error):
        s.authenticate(root, manifest, save_manifest(manifest, m))


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"nested":{"a":1e999}}'])
def test_strict_json(raw):
    with pytest.raises(ValueError): s.strict_json(raw)




@pytest.mark.parametrize('dangling', [False, True])
def test_symlink_dotdot_not_normalized_away(tmp_path, dangling):
    target = tmp_path / 'target'
    if not dangling: target.mkdir()
    (tmp_path / 'link').symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink_path'): s.safe_path(str(tmp_path / 'link' / '..' / 'out'))



@pytest.mark.parametrize('endian', ['<', '>'])
def test_nifti_header(endian):
    _, raw = make_nifti(endian=endian)
    h, dtype, affine = s.header_from_bytes(raw, 'bold')
    assert h['shape'] == [3, 4, 5, 7] and h['header_tr_seconds'] == 2
    assert h['sform_code'] == 4 and dtype.kind == 'f' and h['logical_header_bytes_read'] == 352
    np.testing.assert_array_equal(affine, np.diag([2., 2., 2., 1.]))


@pytest.mark.parametrize('unit,rate,expected', [('sec', 2, 2), ('msec', 2000, 2), ('usec', 2000000, 2), ('unknown', 2, None)])
def test_literal_timing_units(unit, rate, expected):
    h, _ = make_nifti(units=('mm', unit)); h['pixdim'][4] = rate
    report, _, _ = s.header_from_bytes(h.binaryblock + b'\0' * 4, 'bold')
    assert report['header_tr_raw'] == rate and report['header_tr_seconds'] == expected


@pytest.mark.parametrize('slope,inter,effective', [(2, -3, (2, -3)), (0, 5, (1, 0)), (float('nan'), float('nan'), (1, 0))])
def test_nifti_scaling_metadata(slope, inter, effective):
    h, _ = make_nifti(); h['scl_slope'] = slope; h['scl_inter'] = inter
    report, _, _ = s.header_from_bytes(h.binaryblock + b'\0' * 4, 'bold')
    assert (report['effective_slope'], report['effective_intercept']) == effective
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize('kind', ['short', 'magic', 'shape', 'oversize', 'complex', 'offset', 'intercept'])
def test_bad_header(kind):
    h, raw = make_nifti()
    if kind == 'short': raw = raw[:-1]
    else:
        if kind == 'magic': h['magic'] = b'ni1\0'
        elif kind == 'shape': h.set_data_shape((3, 4, 5))
        elif kind == 'oversize': h.set_data_shape((1000, 1000, 1000, 7))
        elif kind == 'complex': h.set_data_dtype(np.complex64)
        elif kind == 'offset': h['vox_offset'] = 351
        elif kind == 'intercept': h['scl_slope'] = 1; h['scl_inter'] = np.inf
        raw = h.binaryblock + b'\0' * 4
    with pytest.raises(ValueError): s.header_from_bytes(raw, 'bold')


def test_bold_read_only_352_logical_bytes(tmp_path, monkeypatch):
    _, raw = make_nifti()
    p = tmp_path / 'bold.nii.gz'; p.write_bytes(b'opaque')
    class HeaderOnly:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, n):
            assert n == 352
            return raw
    monkeypatch.setattr(s.gzip, 'GzipFile', lambda **_: HeaderOnly())
    row = {'path': p.name, 'role': 'bold'}
    h, _, _ = s.read_header(tmp_path, row, {p.name: s.signature(p.stat())})
    assert h['shape'][-1] == 7


def test_atlas_decoder_refuses_bold_before_open(monkeypatch):
    monkeypatch.setattr(s, 'read_header', lambda *_: pytest.fail('must not open'))
    with pytest.raises(ValueError, match='atlas_decoder_role'): s.read_atlas(None, {'role': 'bold'}, None)


@pytest.mark.parametrize('endian', ['<', '>'])
def test_atlas_fortran_label_decode(tmp_path, endian):
    h, raw = make_nifti(shape=(3, 4, 5), endian=endian, dtype=np.int16)
    labels = np.arange(60).reshape((3, 4, 5))
    p = tmp_path / 'atlas.nii.gz'
    p.write_bytes(gzip.compress(raw + labels.astype(h.get_data_dtype()).tobytes(order='F')))
    report, actual, _ = s.read_atlas(tmp_path, {'path': p.name, 'role': 'atlas_image'}, {p.name: s.signature(p.stat())})
    np.testing.assert_array_equal(actual, labels)
    assert report['label_counts']['59'] == 1


def test_changed_source_signature(tmp_path):
    p = tmp_path / 'source'; p.write_bytes(b'123')
    sig = s.signature(p.stat()); p.write_bytes(b'1234')
    with pytest.raises(ValueError, match='source_changed'):
        with s.opened(p, sig): pass


@pytest.mark.parametrize('token,status,value', [('n/a', 'missing', None), ('', 'missing', None),
    ('NaN', 'nonfinite', None), ('inf', 'nonfinite', None), ('NULL', 'invalid', None),
    ('0', 'finite', 0), ('-1', 'finite', -1), ('1.2', 'finite', 1.2)])
def test_literal_numeric_tokens(token, status, value):
    assert s.numeric_token(token) == dict(token=token, status=status, value=value)


def test_events_full_original_ledger_duration_rt():
    raw = b'onset\tduration\ttrial_type\tresponse_time\taccuracy\n0\t1.2\temotion\t1.2\t0\n5\t4.8\tcontrol\tn/a\t0\n5\t2\temotion\t2\t1\n-25\t0\tother\tNaN\t1\n'
    r = s.event_report(raw, 135, 2)
    assert r['row_count'] == 4 and r['pooled_valid_rt_count'] == 2
    assert r['pooled_valid_rt_median'] == 1.6 and r['duplicate_finite_onsets'] == 1
    assert r['finite_onset_descents'] == 1 and r['rows'][0]['included_condition']
    assert r['rows'][1]['omitted_duration_minus_pooled_median'] == pytest.approx(3.2)
    assert r['rows'][0]['original']['accuracy'] == '0'  # Never accuracy-filter.
    assert not r['modeled_design_or_response_read']


@pytest.mark.parametrize('rt', ['0', '-.1', 'NaN', 'inf', 'garbage'])
def test_invalid_target_rt_kept_as_issue(rt):
    r = s.event_report(f'onset\tduration\ttrial_type\tresponse_time\n0\t4.8\temotion\t{rt}\n'.encode(), 135, 2)
    assert r['row_count'] == 1 and r['issues'][0]['code'] == 'nonpositive_or_invalid_response_time'
    assert r['pooled_valid_rt_median'] is None


def test_confound_masks_no_imputation_or_rank():
    raw = ('\t'.join(s.CONFOUNDS) + '\n' + '\t'.join(['n/a'] * 13) + '\n' + '\t'.join(['0'] * 12 + ['NaN']) + '\n').encode()
    r = s.confound_report(raw, 3)
    assert r['row_count'] == 2 and r['issues'][0]['code'] == 'confound_frame_mismatch'
    assert r['columns']['csf']['positions'] == {'missing': [0], 'invalid': [], 'nonfinite': [1]}
    assert r['columns']['trans_x']['tokens'] == ['n/a', '0']
    assert not r['imputation_performed'] and not r['rank_or_regression_computed']


def test_missing_confound_preserves_report():
    r = s.confound_report(b'trans_x\n1\n', 1)
    assert len(r['issues']) == 12 and len(r['columns']) == 1


@pytest.mark.parametrize('raw', [b'a\ta\n1\t2\n', b'a\tb\n1\n', b'\n'])
def test_bad_tsv(raw):
    with pytest.raises(ValueError): s.tsv(raw)


def lut_bytes():
    nets = sorted(s.NETWORKS)
    return ('index\tname\tcolor\n' + ''.join(f'{i}\t7Networks_{"LH" if i <= 50 else "RH"}_{nets[(i-1)%7]}_{i}\t#123456\n' for i in range(1, 101))).encode()


def test_lut_session_independent_original_names():
    rows = s.atlas_lut(lut_bytes())
    assert len(rows) == 100 and {r['network'] for r in rows} == s.NETWORKS


@pytest.mark.parametrize('old,new', [(b'1\t', b'0\t'), (b'7Networks_LH_', b'7Networks_XX_'), (b'_Vis_', b'_Unknown_')])
def test_bad_lut(old, new):
    with pytest.raises(ValueError): s.atlas_lut(lut_bytes().replace(old, new, 1))


def test_half_grid_and_domain_rules():
    labels = np.arange(1, 5).reshape((4, 1, 1))
    coords = np.array([[v, 0, 0] for v in (.5, .5-5e-8, .5+5e-8, .5-2e-7, -5e-8, -2e-7, 3+5e-8, 3+2e-7)])
    np.testing.assert_array_equal(s.nearest_labels(coords, labels), [2, 2, 2, 1, 1, 0, 4, 0])


@pytest.mark.parametrize('linear', [np.eye(3), np.diag([-2., 3., 4.]), np.array([[2., .2, .1], [0, 3., .3], [0, 0, 4.]])])
def test_geometry_flipped_sheared_identity(linear, monkeypatch):
    monkeypatch.setattr(s, 'SPHERES', {})
    labels = np.arange(1, 61).reshape((3, 4, 5))
    affine = np.eye(4); affine[:3, :3] = linear; affine[:3, 3] = [-9, -12, -15]
    r = s.geometry_support(labels.shape, affine, labels, affine, chunk_size=7)
    for i in range(60):
        assert r['supports'][i]['n_voxels'] == 1
        assert r['supports'][i]['support_sha256'] == s.support_digest([i])


def test_physical_sphere_no_rescue_and_chunk_digest(monkeypatch):
    monkeypatch.setattr(s, 'SPHERES', {'center': (0, 0, 0), 'far': (100, 100, 100)})
    affine = np.diag([2., 2., 2., 1.]); affine[:3, 3] = -8
    shape = (9, 9, 9); labels = np.ones(shape, dtype=np.int16)
    a = s.geometry_support(shape, affine, labels, affine, chunk_size=5)
    b = s.geometry_support(shape, affine, labels, affine, chunk_size=10000)
    assert a == b
    assert a['supports'][-2]['n_voxels'] == 123 and a['supports'][-1]['n_voxels'] == 0
    xyz = np.column_stack(np.unravel_index(np.arange(729), shape)) * 2 - 8
    flat = np.flatnonzero(np.sum(xyz**2, axis=1) <= 36)
    assert np.count_nonzero(np.sum(xyz[flat]**2, axis=1) == 36) == 30
    assert a['supports'][-2]['support_sha256'] == s.support_digest(flat)


def test_support_digest_prefix_and_order():
    assert s.support_digest([3, 1, 3]) == hashlib.sha256(b'EMOMATCH_support_v1\n' + np.array([1, 3], dtype='<i8').tobytes()).hexdigest()
    assert s.support_digest([]) == hashlib.sha256(b'EMOMATCH_support_v1\n').hexdigest()





def bold_fixture(tmp_path, values, *, endian="<", slope=1., inter=0., offset=352, suffix=b""):
    data = np.asarray(values)
    h, _ = make_nifti(shape=data.shape, endian=endian, dtype=data.dtype)
    h["scl_slope"] = slope; h["scl_inter"] = inter; h["vox_offset"] = offset
    raw = h.binaryblock + b"\0" * (offset - 348) + data.astype(h.get_data_dtype()).tobytes(order="F") + suffix
    path = tmp_path / "bold.nii.gz"; path.write_bytes(gzip.compress(raw))
    row = {"path": path.name, "role": "bold"}
    sig = {path.name: s.signature(path.stat())}
    header, dtype, _ = s.read_header(tmp_path, row, sig)
    return row, sig, header, dtype


@pytest.mark.parametrize("endian", ["<", ">"])
@pytest.mark.parametrize("dtype", [np.int16, np.float32, np.float64])
@pytest.mark.parametrize("offset", [352, 512])
def test_sequential_volume_fortran_C_support_and_scaling(tmp_path, endian, dtype, offset):
    values = np.arange(3*4*5*7, dtype=dtype).reshape((3, 4, 5, 7))
    row, sig, header, parsed_dtype = bold_fixture(tmp_path, values, endian=endian, slope=2., inter=-3., offset=offset)
    support = {"first": np.array([0, 1, 2], dtype=np.int64), "last": np.array([5, 24, 59], dtype=np.int64)}
    actual, peaks = s.extract_roi_means(tmp_path, row, sig, header, parsed_dtype, list(support), support)
    scaled = values.astype(np.float64) * 2 - 3
    expected = np.stack([[scaled[:, :, :, t].ravel(order="C")[ix].mean(dtype=np.float64)
                          for ix in support.values()] for t in range(7)])
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(peaks, [np.max(np.abs(scaled.reshape((60, 7), order="C")[ix])) for ix in support.values()])
    assert actual.dtype == np.float64 and actual.shape == (7, 2)


def test_stream_decoder_never_uses_nibabel_BOLD_array_api(tmp_path, monkeypatch):
    values = np.arange(16, dtype=np.float32).reshape((2, 2, 2, 2))
    row, sig, header, dtype = bold_fixture(tmp_path, values)
    monkeypatch.setattr(s.nib, "load", lambda *_: pytest.fail("no nibabel image/proxy"))
    actual, _ = s.extract_roi_means(tmp_path, row, sig, header, dtype, ["r"], {"r": np.arange(8)})
    np.testing.assert_array_equal(actual[:, 0], [7., 8.])


@pytest.mark.parametrize("kind", ["nan_inside", "nan_outside", "infinity", "scaled_overflow", "truncated", "trailing", "changed", "header"])
def test_stream_rejects_unsupported_source_not_silent_QC(tmp_path, kind):
    values = np.arange(16, dtype=np.float64).reshape((2, 2, 2, 2))
    if kind in {"nan_inside", "nan_outside"}: values[0 if kind == "nan_inside" else 1, 0, 0, 0] = np.nan
    elif kind == "infinity": values[0, 0, 0, 0] = np.inf
    elif kind == "scaled_overflow": values[:] = 1e308
    row, sig, header, dtype = bold_fixture(tmp_path, values, slope=2., suffix=b"extra" if kind == "trailing" else b"")
    if kind == "changed":
        (tmp_path / row["path"]).write_bytes(b"changed")
    elif kind == "truncated":
        raw = gzip.decompress((tmp_path / row["path"]).read_bytes())
        (tmp_path / row["path"]).write_bytes(gzip.compress(raw[:-8]))
        sig[row["path"]] = s.signature((tmp_path / row["path"]).stat())
    elif kind == "header":
        header["effective_slope"] = 3.
    with pytest.raises((ValueError, FloatingPointError)):
        s.extract_roi_means(tmp_path, row, sig, header, dtype, ["r"], {"r": np.array([0])})


@pytest.mark.parametrize("indices", [[], [1, 0], [0, 0], [-1], [8], [1.5], [True]])
def test_stream_support_membership_guards(tmp_path, indices):
    row, sig, header, dtype = bold_fixture(tmp_path, np.zeros((2, 2, 2, 2), dtype=np.float32))
    with pytest.raises(ValueError):
        s.extract_roi_means(tmp_path, row, sig, header, dtype, ["r"], {"r": np.asarray(indices)})


def test_geometry_indices_match_digest_and_chunk_order(monkeypatch):
    monkeypatch.setattr(s, "SPHERES", {"inside": (0, 0, 0), "outside": (99, 99, 99)})
    shape = (3, 4, 5); labels = np.arange(1, 61).reshape(shape)
    affine = np.eye(4)
    ids, indices = s.spatial_indices(shape, affine, labels, affine, chunk_size=7)
    diagnostic = s.geometry_support(shape, affine, labels, affine, chunk_size=11)
    assert ids == [r["roi_id"] for r in diagnostic["supports"]]
    for row in diagnostic["supports"]:
        key = row["roi_id"]
        assert row["n_voxels"] == len(indices[key])
        assert row["support_sha256"] == s.support_digest(indices[key])
        assert np.all(indices[key][1:] > indices[key][:-1])


def test_event_primitives_exact_membership_and_missing_mask():
    raw = b"onset\tduration\ttrial_type\tresponse_time\n0\t1\temotion\t1\n5\t4.8\tcontrol\tn/a\n10\t2\tother\t2\n"
    result = s.event_primitives(s.event_report(raw, 135, 2))
    np.testing.assert_array_equal(result["selected_source_event_row"], [0, 1])
    np.testing.assert_array_equal(result["response_time"], [1., 0.])
    np.testing.assert_array_equal(result["response_time_missing"], [False, True])
    assert len(result["ledger"]) == 3 and result["conditions"].tolist() == ["emotion", "control"]
    assert result["column_names"] == ["onset", "duration", "trial_type", "response_time"]


@pytest.mark.parametrize("onset,duration,ok", [(-24, 0, True), (-24.000001, 1, False),
                                             (0, -1e-9, False), (0, 1, True)])
def test_final_presignal_event_boundaries(onset, duration, ok):
    raw = f"onset\tduration\ttrial_type\tresponse_time\n{onset}\t{duration}\temotion\t1\n".encode()
    report = s.event_report(raw, 135, 2)
    if ok:
        result = s.event_primitives(report)
        assert result["onsets"].tolist() == [onset] and result["source_durations"].tolist() == [duration]
    else:
        with pytest.raises(ValueError, match="unsupported_event_metadata_precondition"):
            s.event_primitives(report)


def test_all_missing_confound_is_preserved_for_public_zero_imputation():
    raw = ("\t".join(s.CONFOUNDS) + "\n" + ("\t".join(["n/a"] * 13) + "\n") * 2).encode()
    values, missing = s.confound_primitives(s.confound_report(raw, 2))
    assert missing.all() and np.all(values == 0)


def test_confound_primitives_do_not_impute():
    raw = ("\t".join(s.CONFOUNDS) + "\n" + "\t".join(["n/a"] + ["2"] * 12) + "\n" +
           "\t".join(["8"] * 13) + "\n").encode()
    values, missing = s.confound_primitives(s.confound_report(raw, 2))
    assert values.shape == missing.shape == (2, 13)
    assert values[0, 0] == 0 and missing[0, 0] and values[1, 0] == 8
    assert int(missing.sum()) == 1


@pytest.mark.parametrize("kind", ["event_no_valid", "event_bad_RT", "confound_nonfinite", "confound_missing_column"])
def test_inputs_fail_before_modeling(kind):
    with pytest.raises(ValueError):
        if kind.startswith("event"):
            rt = "n/a" if kind == "event_no_valid" else "NaN"
            s.event_primitives(s.event_report(f"onset\tduration\ttrial_type\tresponse_time\n0\t4.8\temotion\t{rt}\n".encode(), 135, 2))
        else:
            raw = b"trans_x\nNaN\n" if kind == "confound_nonfinite" else b"trans_x\n1\n"
            s.confound_primitives(s.confound_report(raw, 1))


def test_private_source_pin_required_no_caller_hash_bypass(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "SOURCE_MANIFEST_SHA256", "PENDING_PARENT_FINAL_MANIFEST_FREEZE")
    monkeypatch.setattr(s, "authenticate", lambda *_: pytest.fail("must stop before source reads"))
    with pytest.raises(ValueError, match="source_manifest_freeze_pending"):
        s.reconstruct(str(tmp_path), str(tmp_path / "manifest.json"))


@pytest.mark.parametrize("chosen", [[], ["sub-9999"], ["sub-0002", "sub-0002"]])
def test_reconstruct_subject_scope_before_authentication(tmp_path, monkeypatch, chosen):
    manifest = tmp_path / "manifest.json"; manifest.write_bytes(b"{}")
    monkeypatch.setattr(s, "SOURCE_MANIFEST_SHA256", "0" * 64)
    monkeypatch.setattr(s, "authenticate", lambda *_: pytest.fail("must stop before source reads"))
    with pytest.raises(ValueError, match="requested_subject_membership"):
        s.reconstruct(str(tmp_path), str(manifest), subjects=chosen)


def test_reconstruct_complete_manufactured_basis_and_provenance(tmp_path, monkeypatch):
    root, manifest, m = fixture_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(s, "SOURCE_BOLD_SHAPE", (5, 5, 4, 7))
    monkeypatch.setattr(s, "SOURCE_CONDITION_COUNTS", {"emotion": 1, "control": 1})
    monkeypatch.setattr(s, "SPHERES", {name: (0, 0, 0) for name in s.SPHERES})
    _, bold_header = make_nifti(shape=(5, 5, 4, 7))
    _, atlas_header = make_nifti(shape=(5, 5, 4), dtype=np.int16)
    bold = np.arange(700, dtype='<f4').reshape((5, 5, 4, 7))
    confound = ('\t'.join(s.CONFOUNDS) + '\n' + ('\t'.join(['0'] * 13) + '\n') * 7).encode()
    for row in m['files']:
        role = row['role']
        if role == 'bold': raw = gzip.compress(bold_header + bold.tobytes(order='F'))
        elif role == 'atlas_image': raw = gzip.compress(atlas_header + np.arange(1, 101, dtype='<i2').reshape((5, 5, 4)).tobytes(order='F'))
        elif role == 'atlas_labels': raw = lut_bytes()
        elif role == 'events': raw = b'onset\tduration\ttrial_type\tresponse_time\n0\t1\temotion\t1\n5\t4.8\tcontrol\tn/a\n'
        elif role == 'confounds': raw = confound
        elif role == 'participants': raw = b'participant_id\tsex\nsub-0002\tF\nsub-0999\tM\n'
        elif role == 'participants_schema': raw = b'{"NEO_A":1,"NEO_A":2}'  # Unused documentation only authenticated.
        else: raw = b'{"RepetitionTime":2}'
        (root / row['path']).write_bytes(raw)
        digest = hashes(raw); row['size_bytes'] = len(raw); row['sha256'] = digest['sha256']
        if row['identity_kind'] == 'git_blob_content': row['content_git_blob_sha1'] = row['source_git_blob_sha1'] = digest['git']
        else: row['md5'] = digest['md5']
    m['total_bytes'] = sum(r['size_bytes'] for r in m['files'])
    monkeypatch.setattr(s, 'SOURCE_MANIFEST_SHA256', save_manifest(manifest, m))
    basis = s.reconstruct(str(root), str(manifest))
    assert basis['source_manifest'] == m and basis['source_records'] == m['files']
    assert basis['source_documents']['participants_schema'] == '{"NEO_A":1,"NEO_A":2}'
    assert basis['participant_ids'] == ['sub-0002'] and len(basis['cohort_rows']) == 2
    person = basis['subjects'][0]
    assert person['event_column_names'] == ['onset', 'duration', 'trial_type', 'response_time']
    assert person['confound_column_names'] == list(s.CONFOUNDS)
    assert person['raw_roi_mean'].shape == (7, 111) and len(person['supports']) == 111
    np.testing.assert_array_equal(person['raw_roi_mean'][:, :100], bold.reshape((100, 7), order='C').T)
    np.testing.assert_array_equal(person['frame_times_s'], 2*np.arange(7))
    assert not basis['source_proof']['model_fitting_performed'] and not basis['source_proof']['public_helper_imported']
