"""Manufactured oracle-source fixtures; no source cache or packaged template."""
from dataclasses import replace
import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import struct
import sys
import zlib

import nibabel as nib
import numpy as np
import pytest

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('oracle_source_fixture', HERE / 'oracle_source.py')
o = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = o
spec.loader.exec_module(o)


def digest(raw): return hashlib.sha256(raw).hexdigest()


def image_bytes(values, *, endian='<', slope=1., intercept=0., extension=False, units=10):
    values = np.asarray(values)
    dtype = np.dtype(endian + ('f4' if values.dtype.kind == 'f' else 'i2'))
    offset = 368 if extension else 352
    prefix = bytearray(offset)
    struct.pack_into(endian + 'i', prefix, 0, 348)
    struct.pack_into(endian + '8h', prefix, 40, values.ndim, *values.shape, *([1] * (7 - values.ndim)))
    struct.pack_into(endian + 'hh', prefix, 70, 16 if dtype.kind == 'f' else 4, 8 * dtype.itemsize)
    struct.pack_into(endian + '8f', prefix, 76, 1., 1., 1., 1., 2., 1., 1., 1.)
    struct.pack_into(endian + 'fff', prefix, 108, offset, slope, intercept)
    prefix[123] = units
    struct.pack_into(endian + 'hh', prefix, 252, 0, 1)
    for axis in range(3):
        row = [0., 0., 0., -5.]; row[axis] = 1.
        struct.pack_into(endian + '4f', prefix, 280 + 16 * axis, *row)
    prefix[344:348] = b'n+1\0'
    if extension:
        prefix[348] = 1
        struct.pack_into(endian + 'ii', prefix, 352, 16, 6)
        prefix[360:368] = b'comment!'
    return gzip.compress(bytes(prefix) + values.astype(dtype).tobytes(order='F'), mtime=0)


def identities(raw):
    return dict(size_bytes=len(raw), sha256=digest(raw), md5=hashlib.md5(raw).hexdigest(),
                git_blob_sha1=hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest())


def repin(f):
    manifest = f['manifest']
    manifest.update(n_files=len(manifest['files']), total_bytes=sum(row['size_bytes'] for row in manifest['files']))
    raw = json.dumps(manifest).encode()
    f['manifest_path'].write_bytes(raw)
    (f['data'] / 'source_manifest.json').write_bytes(raw)
    source_sha = digest(raw)
    f['method']['source']['source_manifest_sha256'] = source_sha
    f['method']['global_signal']['template_sha256'] = next(row['sha256'] for row in manifest['files'] if row['role'] == 'template')
    raw_method = json.dumps(f['method']).encode(); f['method_path'].write_bytes(raw_method)
    f['schema'].update(source_manifest_sha256=source_sha, method_sha256=digest(raw_method), reporting_kernel_sha256=f['policy'].reporting_sha)
    raw_schema = json.dumps(f['schema']).encode(); f['schema_path'].write_bytes(raw_schema)
    f['policy'] = replace(f['policy'], source_sha=source_sha, method_sha=digest(raw_method), schema_sha=digest(raw_schema),
                          source_count=manifest['n_files'], source_bytes=manifest['total_bytes'])


def change(f, role, sid, payload):
    row = next(row for row in f['manifest']['files'] if (row['role'], row.get('participant_id')) == (role, sid))
    (f['data'] / row['path']).write_bytes(payload)
    row.update(identities(payload)); repin(f)


@pytest.fixture
def fixture(tmp_path):
    subjects = ('sub-pixar001', 'sub-pixar002')
    data = tmp_path / 'data'; data.mkdir()
    method = json.loads((HERE / 'method_contract.json').read_bytes())
    schema = json.loads((HERE / 'output_schema.json').read_bytes())
    files, arrays = [], {}
    generator = np.random.default_rng(127)

    def add(name, role, sid, payload):
        target = data / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(payload)
        row = dict(path=name, role=role, participant_id=sid, **identities(payload))
        if role in ('bold', 'confounds', 'participants'):
            oid = f'{len(files) + 1:024x}'
            row.update(osf_object_id=oid, source_version=2,
                source_url=f'https://files.osf.io/v1/resources/5hju4/providers/osfstorage/{oid}?revision=2')
        else:
            commit = 'a' * 40
            row.update(source_commit=commit, source_url=f'https://raw.githubusercontent.com/nilearn/nilearn/{commit}/{name}')
        files.append(row)

    for sid in subjects:
        arrays[sid] = (100. + generator.normal(size=(11, 11, 11, 32))).astype(np.float32)
        add(sid + '_task-pixar_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz', 'bold', sid, image_bytes(arrays[sid]))
        names = method['confounds']['columns'] + ['ignored_column']
        numbers = generator.normal(size=(32, len(names)))
        lines = ['\t'.join(names)]
        for i, values in enumerate(numbers):
            tokens = [repr(float(value)) for value in values]
            if i == 0: tokens[names.index('framewise_displacement')] = 'n/a'
            tokens[-1] = 'documentary-only'
            lines.append('\t'.join(tokens))
        add(sid + '_task-pixar_desc-confounds_regressors.tsv', 'confounds', sid, ('\n'.join(lines) + '\n').encode())
    add('participants.tsv', 'participants', None,
        b'participant_id\tAge\tChild_Adult\nsub-pixar002\t30\tadult\nsub-pixar001\t9\tchild\n')
    add('templates/fixture.nii.gz', 'template', None, image_bytes(np.ones((11, 11, 11), dtype=np.float32)))
    add('provenance/notice.txt', 'provenance', None, b'Inert source notice\n')
    pins = {name: digest((HERE / name).read_bytes()) for name in o.CODE_PINS}
    policy = o.Policy(None, None, None, None, None, pins['reporting_kernel.py'], pins,
        {name: importlib.metadata.version(name) for name in o.SOFTWARE}, subjects=subjects)
    method['source'].update(n_subjects=2, frame_counts_by_subject=dict.fromkeys(subjects, 32),
        expected_group_counts={'child': 1, 'adult': 1}, spatial_unit_policy={'world_coordinate_unit': 'mm',
        'allowed_bold_header_units': ['mm'], 'allowed_template_header_units': ['mm']})
    method['confounds']['missingness']['missing_tokens'] = ['', 'n/a']
    method['roi_geometry']['radius_mm'] = 2.
    for i, roi in enumerate(method['roi_geometry']['rois']): roi['center_mm'] = [i % 3 - 1, (i // 3) % 3 - 1, i // 9]
    f = dict(data=data, manifest_path=tmp_path / 'manifest.json', method_path=tmp_path / 'method.json',
        schema_path=tmp_path / 'schema.json', manifest=dict(schema_version='socialbrain-source-v2', task_id='SOCIALBRAIN-001',
        participant_ids=list(subjects), files=files), method=method, schema=schema, policy=policy, arrays=arrays)
    repin(f)
    return f


def run(f, **kwargs):
    return o.reconstruct(f['data'], f['manifest_path'], f['method_path'], f['schema_path'], _policy=f['policy'], **kwargs)


def test_unfrozen_production_refuses_before_source(tmp_path):
    with pytest.raises(ValueError, match='unfrozen_document'):
        o.reconstruct(tmp_path / 'absent', _policy=replace(o.production_policy(), source_sha=None))


def test_complete_interface_no_endpoints_and_source_unchanged(fixture):
    before = {p: p.read_bytes() for p in fixture['data'].rglob('*') if p.is_file()}
    result = run(fixture)
    assert result['status'] == 'complete' and result['subject_ids'] == ['sub-pixar001', 'sub-pixar002']
    assert len(result['source_files']) == 7 and len(result['cohort']) == 2
    assert len(result['source_observed']['persons']) == len(result['analysis_observed']['persons']) == 2
    assert result['analysis_observed']['child_motion_nuisance_rank'] == 1
    assert result['source_observed']['template']['normalization'] == dict(dtype='float32', operator='divide_by_global_maximum', maximum=1.)
    for person in result['persons'].values():
        assert person['raw_roi'].shape == (32, 12)
        assert person['cleaned_roi'].shape == (32, 2, 12)
        assert person['canonical_active'].shape == (2, 12) and person['canonical_active'].dtype == bool
        assert np.isfinite(person['cleaned_roi']).all()
    assert not {'metrics', 'connectivity', 'age_effects'} & set(result)
    assert {p: p.read_bytes() for p in fixture['data'].rglob('*') if p.is_file()} == before


def test_pilot_only_first_image_but_full_auth_metadata(fixture, monkeypatch):
    original = o.image_values
    shapes = []
    def capture(raw, record, *args):
        shapes.append(record['shape'])
        return original(raw, record, *args)
    monkeypatch.setattr(o, 'image_values', capture)
    result = run(fixture, pilot=True)
    assert result['status'] == 'resource_pilot' and list(result['persons']) == ['sub-pixar001']
    assert len(result['cohort']) == len(result['source_observed']['persons']) == 2
    assert len(result['analysis_observed']['persons']) == 1
    assert [len(shape) for shape in shapes] == [3, 4]


def test_authenticates_last_member_before_first_parse(fixture, monkeypatch):
    (fixture['data'] / 'provenance/notice.txt').write_bytes(b'corrupt')
    monkeypatch.setattr(o, 'image_header', lambda *args: pytest.fail('decoded before authentication'))
    with pytest.raises(ValueError, match='source_size'): run(fixture)


def test_no_network_no_private_extractor_and_geometry_memo(fixture, monkeypatch):
    original = o.code_modules
    calls = []
    def modules(policy):
        loaded = original(policy)
        assert set(loaded) == {'stage_data', 'inspect_structure', 'oracle_numerics', 'reporting_kernel'}
        loaded['stage_data'].open_once = lambda *a: pytest.fail('network attempted')
        loaded['stage_data'].stage = lambda *a: pytest.fail('stage attempted')
        loaded['inspect_structure'].authenticated_bytes = lambda *a, **k: pytest.fail('private auth used')
        loaded['inspect_structure'].decode_header = lambda *a: pytest.fail('shared scientific header decoder used')
        backend = loaded['oracle_numerics'].global_support
        def geometry(*args): calls.append(1); return backend(*args)
        loaded['oracle_numerics'].global_support = geometry
        return loaded
    monkeypatch.setattr(o, 'code_modules', modules)
    run(fixture)
    assert calls == [1]


@pytest.mark.parametrize('endian', ['<', '>'])
@pytest.mark.parametrize('shape', [(3, 4, 5), (3, 4, 5, 7)])
@pytest.mark.parametrize('extension', [False, True])
@pytest.mark.parametrize('floating', [False, True])
@pytest.mark.parametrize('slope,intercept', [(2.5, -3.), (.1, .3)])
def test_nibabel_scaling_endian_fortran_exact_float64(fixture, endian, shape, extension, floating, slope, intercept, monkeypatch):
    values = np.arange(np.prod(shape), dtype=np.float32 if floating else np.int16).reshape(shape)
    raw = image_bytes(values, endian=endian, slope=slope, intercept=intercept, extension=extension)
    modules = o.code_modules(fixture['policy'])
    record, length = o.image_header(raw, len(shape), modules['inspect_structure'], fixture['policy'], lambda: None)
    original = nib.Nifti1Image.from_bytes
    calls = []
    def construct(cls, raw, **kwargs): calls.append(len(raw)); return original(raw, **kwargs)
    monkeypatch.setattr(nib.Nifti1Image, 'from_bytes', classmethod(construct))
    result = o.image_values(raw, record, length, fixture['policy'], lambda: None)
    np.testing.assert_array_equal(result, values.astype(np.float64) * float(np.float32(slope)) + float(np.float32(intercept)))
    assert calls == [length] and result.dtype == np.float64 and result.flags.c_contiguous


@pytest.mark.parametrize('mutation', ['truncated', 'trailing_stream', 'trailing_byte', 'short_values', 'long_values', 'bad_extension'])
def test_strict_gzip_and_extensions(fixture, mutation):
    raw = image_bytes(np.ones((3, 4, 5), dtype=np.float32), extension=mutation == 'bad_extension')
    if mutation == 'truncated': raw = raw[:-4]
    if mutation == 'trailing_stream': raw += gzip.compress(b'')
    if mutation == 'trailing_byte': raw += b'\0'
    if mutation == 'short_values': raw = gzip.compress(gzip.decompress(raw)[:-1])
    if mutation == 'long_values': raw = gzip.compress(gzip.decompress(raw) + b'x')
    if mutation == 'bad_extension':
        block = bytearray(gzip.decompress(raw)); struct.pack_into('<i', block, 352, 15); raw = gzip.compress(block)
    doc = o.code_modules(fixture['policy'])['inspect_structure']
    with pytest.raises((ValueError, zlib.error)):
        record, length = o.image_header(raw, 3, doc, fixture['policy'], lambda: None)
        o.image_values(raw, record, length, fixture['policy'], lambda: None)


@pytest.mark.parametrize('kind', ['extra', 'symlink', 'extra_directory', 'internal_manifest', 'wrong_sha', 'wrong_md5', 'wrong_git'])
def test_source_identity_guards(fixture, kind):
    root = fixture['data']
    if kind == 'extra': (root / 'extra').write_bytes(b'x')
    if kind == 'symlink': (root / 'link').symlink_to(root / 'participants.tsv')
    if kind == 'extra_directory': (root / 'unneeded').mkdir()
    if kind == 'internal_manifest': (root / 'source_manifest.json').write_bytes(b'{}')
    if kind.startswith('wrong_'):
        key = {'wrong_sha': 'sha256', 'wrong_md5': 'md5', 'wrong_git': 'git_blob_sha1'}[kind]
        row = fixture['manifest']['files'][-1]; row[key] = '0' * len(row[key]); repin(fixture)
    with pytest.raises(ValueError): run(fixture)


@pytest.mark.parametrize('frame,token,valid', [(0, '', True), (0, 'n/a', True), (1, 'n/a', False),
                                             (0, 'nan', False), (2, 'inf', False), (0, 'bad', False)])
def test_first_frame_missing_rule_and_fd_receipts(fixture, frame, token, valid):
    row = next(row for row in fixture['manifest']['files'] if row['role'] == 'confounds')
    lines = (fixture['data'] / row['path']).read_text().splitlines()
    fields = lines[frame + 1].split('\t'); fields[0] = token; lines[frame + 1] = '\t'.join(fields)
    change(fixture, 'confounds', row['participant_id'], ('\n'.join(lines) + '\n').encode())
    if not valid:
        with pytest.raises(ValueError): run(fixture, pilot=True)
    else:
        result = run(fixture, pilot=True)
        assert result['cohort'][0]['mean_fd_observed_count'] == 31
        assert dict(frame_index=0, column_name='trans_x', original_token=token, applied_value=0.) in result['source_observed']['persons'][0]['missing_selected_entries']


def test_post_use_source_hash_recheck(fixture, monkeypatch):
    original = o.image_values
    target = fixture['data'] / 'provenance/notice.txt'; raw = target.read_bytes()
    def mutate(*args):
        values = original(*args)
        target.write_bytes(b'X' + raw[1:])
        return values
    monkeypatch.setattr(o, 'image_values', mutate)
    with pytest.raises(ValueError, match='source_sha256_mismatch'): run(fixture, pilot=True)


def test_contributing_values_only(fixture):
    sid = fixture['policy'].subjects[0]
    values = fixture['arrays'][sid].copy(); values[0, 0, 0, 0] = np.nan
    change(fixture, 'bold', sid, image_bytes(values)); run(fixture, pilot=True)
    values[5, 5, 5, 0] = np.inf
    change(fixture, 'bold', sid, image_bytes(values))
    with pytest.raises(ValueError, match='nonfinite_contributing'): run(fixture, pilot=True)


def test_source_schema_role_and_version_are_not_inferred(fixture):
    fixture['manifest']['files'][0]['source_version'] = None; repin(fixture)
    with pytest.raises(ValueError, match='manifest_version_md5'): run(fixture)


def test_caps_and_deadline(fixture):
    fixture['policy'] = replace(fixture['policy'], decoded_byte_cap=100)
    with pytest.raises(ValueError, match='decoded_image_cap'): run(fixture, pilot=True)
    fixture['policy'] = replace(fixture['policy'], decoded_byte_cap=512 * 1024**2, wall_seconds=0)
    with pytest.raises(ValueError, match='oracle_source_deadline'): run(fixture, pilot=True)
