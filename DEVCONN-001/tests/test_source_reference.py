"""Manufactured-only DEVCONN source-reader QA; no original bodies or endpoints."""
from dataclasses import replace
import builtins
import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import struct
import sys
import zlib

import numpy as np
import pytest

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('devconn_private_source_fixture', HERE / 'source_reference.py')
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def nifti(values, *, endian='<', slope=1., intercept=0., extension=False, units=10):
    values = np.asarray(values)
    dtype = np.dtype(endian + ('f4' if values.dtype.kind == 'f' else 'i2'))
    offset = 368 if extension else 352
    block = bytearray(offset)
    struct.pack_into(endian + 'i', block, 0, 348)
    struct.pack_into(endian + '8h', block, 40, values.ndim, *values.shape, *([1] * (7 - values.ndim)))
    struct.pack_into(endian + 'hh', block, 70, 16 if dtype.kind == 'f' else 4, dtype.itemsize * 8)
    struct.pack_into(endian + '8f', block, 76, 1., 1., 1., 1., 2., 1., 1., 1.)
    struct.pack_into(endian + 'fff', block, 108, offset, slope, intercept)
    block[123] = units
    struct.pack_into(endian + 'hh', block, 252, 0, 1)
    for axis in range(3):
        row = [0., 0., 0., -5.]
        row[axis] = 1.
        struct.pack_into(endian + '4f', block, 280 + 16 * axis, *row)
    block[344:348] = b'n+1\0'
    if extension:
        block[348] = 1
        struct.pack_into(endian + 'ii', block, 352, 16, 6)
        block[360:368] = b'fixture!'
    return gzip.compress(bytes(block) + np.asarray(values, dtype=dtype).tobytes(order='F'), mtime=0)


def pinned_row(name, role, sid, raw):
    return dict(path=name, role=role, participant_id=sid, size_bytes=len(raw), sha256=sha(raw),
                md5=hashlib.md5(raw).hexdigest(),
                git_blob_sha1=hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest())


def repin(f):
    m = f['manifest']
    m['n_files'] = len(m['files'])
    m['total_bytes'] = sum(row['size_bytes'] for row in m['files'])
    raw = json.dumps(m).encode()
    (f['source'] / 'source_manifest.json').write_bytes(raw)
    f['manifest_path'].write_bytes(raw)
    source_sha = sha(raw)
    f['method']['source'].update(source_manifest_sha256=source_sha, n_files=m['n_files'],
                                total_bytes=m['total_bytes'])
    coordinate = next(row for row in m['files'] if row['role'] == 'coordinates')
    f['method']['roi_geometry']['coordinates_sha256'] = coordinate['sha256']
    method_raw = json.dumps(f['method']).encode()
    f['method_path'].write_bytes(method_raw)
    f['schema'].update(source_manifest_sha256=source_sha, method_sha256=sha(method_raw),
                       reporting_kernel_sha256=f['policy'].reporting_sha)
    schema_raw = json.dumps(f['schema']).encode()
    f['schema_path'].write_bytes(schema_raw)
    f['policy'] = replace(f['policy'], source_sha=source_sha, method_sha=sha(method_raw), schema_sha=sha(schema_raw))


def replace_member(f, role, sid, raw):
    row = next(row for row in f['manifest']['files'] if (row['role'], row.get('participant_id')) == (role, sid))
    (f['source'] / row['path']).write_bytes(raw)
    row.update(pinned_row(row['path'], role, sid, raw))
    repin(f)


def mutate_cell(f, name, frame, token, sid='sub-pixar001'):
    row = next(row for row in f['manifest']['files'] if row['role'] == 'confounds' and row['participant_id'] == sid)
    lines = (f['source'] / row['path']).read_text().splitlines()
    headers = lines[0].split('\t')
    fields = lines[frame + 1].split('\t')
    fields[headers.index(name)] = token
    lines[frame + 1] = '\t'.join(fields)
    replace_member(f, 'confounds', sid, ('\n'.join(lines) + '\n').encode())


@pytest.fixture
def fixture(tmp_path):
    ids = ('sub-pixar001', 'sub-pixar002')
    source = tmp_path / 'source'
    source.mkdir()
    files, arrays = [], {}

    def add(name, role, sid, payload):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        files.append(pinned_row(name, role, sid, payload))

    method = json.loads((HERE / 'method_contract.json').read_bytes())
    schema = json.loads((HERE / 'output_schema.json').read_bytes())
    rng = np.random.default_rng(42)
    for sid in ids:
        values = (rng.normal(size=(11, 11, 11, 48)) + 100.).astype(np.float32)
        arrays[sid] = values
        add(f'{sid}_task-pixar_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz', 'bold', sid, nifti(values))
        # Original column order deliberately differs from declared nuisance order.
        columns = ['UNUSED_COLUMN', 'framewise_displacement', *reversed(method['confounds']['columns'])]
        noise = rng.normal(size=(48, len(columns)))
        rows = []
        for i in range(48):
            row = [repr(float(v)) for v in noise[i]]
            row[0] = 'unparsed-documentary-token'
            row[1] = 'n/a' if i == 0 else '0.25'
            rows.append('\t'.join(row))
        add(f'{sid}_task-pixar_desc-confounds_regressors.tsv', 'confounds', sid,
            ('\t'.join(columns) + '\n' + '\n'.join(rows) + '\n').encode())
    add('participants.tsv', 'participants', None,
        b'participant_id\tAge\tChild_Adult\textra\nsub-pixar002\t25\tadult\tprivate\nsub-pixar001\t8\tchild\tprivate\n')
    add('atlas/power_2011.csv', 'coordinates', None, b'ROI,X,Y,Z\nR-A,-2,0,0\n007,0,0,0\nZ,2,0,0\n')
    for name in ('power_2011.rst', 'development_fmri.rst'):
        add('provenance/nilearn_0_12_1/nilearn/datasets/description/' + name,
            'provenance', None, b'Inert manufactured notice\n')
    add('provenance/nilearn_0_12_1/LICENSE', 'provenance', None, b'Manufactured license\n')
    add('provenance/processing_README_version2.md', 'provenance', None, b'Manufactured processing notice\n')
    module_pins = {name: sha((HERE / name).read_bytes()) for name in r.MODULE_PINS}
    versions = {name: importlib.metadata.version(name) for name in r.VERSIONS}
    policy = r.Policy(None, None, None, module_pins['reporting_kernel.py'], module_pins, versions,
                      subject_ids=ids, expected_rois=3)
    method['reporting_kernel_sha256'] = policy.reporting_sha
    method['source'].update(n_subjects=2, frame_counts_by_subject=dict.fromkeys(ids, 48), total_frames=96,
        expected_group_counts={'child': 1, 'adult': 1},
        spatial_unit_policy={'world_coordinate_unit': 'mm', 'allowed_bold_header_units': ['mm']})
    method['confounds']['missingness'].update(missing_tokens=['', 'n/a'], fill_value=0)
    method['roi_geometry'].update(n_rois=3, radius_mm=5, source_columns=['ROI', 'X', 'Y', 'Z'])
    f = dict(source=source, manifest_path=tmp_path / 'manifest.json', method_path=tmp_path / 'method.json',
             schema_path=tmp_path / 'schema.json', policy=policy, method=method, schema=schema,
             manifest=dict(task_id='DEVCONN-001', schema_version='devconn-source-v2',
                           participant_ids=list(ids), files=files), arrays=arrays)
    repin(f)
    return f


def run(f, **kwargs):
    return r.reconstruct(f['source'], f['manifest_path'], f['method_path'], f['schema_path'],
                         _policy=f['policy'], **kwargs)


def test_production_unfrozen_refuses_without_data_read(tmp_path):
    with pytest.raises(ValueError, match='unfrozen_pin'):
        r.reconstruct(tmp_path / 'absent', _policy=replace(r.production_policy(), method_sha=None))


def test_complete_primitives_metadata_and_no_endpoints(fixture):
    result = run(fixture)
    assert result['status'] == 'complete'
    assert result['subject_ids'] == result['structural_subject_ids'] == list(fixture['policy'].subject_ids)
    assert len(result['source_files']) == 10
    assert len(result['source_observed']['persons']) == len(result['analysis_observed']['persons']) == 2
    assert result['roi_ids'] == ['R-A', '007', 'Z']
    assert result['coordinates'].shape == (3, 3)
    assert result['analysis_observed']['distance_bins']['n_pairs'] == 3
    cov = result['cohort'][0]
    assert cov['mean_fd'] == (47 * .25) / 48
    assert cov['mean_fd_observed_count'] == 47 and cov['mean_fd_missing_frame_indices'] == [0]
    p = result['source_observed']['persons'][0]
    assert p['mean_fd_denominator'] == 48 and p['mean_fd_zero_filled_sum'] == 47 * .25
    assert p['mean_fd_sum'] == 47 * .25 and p['mean_fd_observed_count'] == 47
    assert p['mean_fd_missing_entries'] == [dict(frame_index=0, column_name='framewise_displacement',
        original_token='n/a', applied_value=0.)]
    assert p['selected_confound_columns'] == fixture['method']['confounds']['columns']
    assert p['excluded_confound_columns'] == ['UNUSED_COLUMN', 'framewise_displacement']
    for person in result['persons'].values():
        assert person['raw_roi'].shape == person['cleaned_roi'].shape == (48, 3)
        assert person['canonical_active'].shape == (3,) and person['canonical_active'].dtype == bool
        np.testing.assert_array_equal(person['frame_indices'], np.arange(48))
        assert np.isfinite(person['cleaned_roi']).all()
    assert not {'connectivity', 'age_effects', 'bootstrap', 'metrics', 'p_values'} & set(result)
    assert 'private' not in json.dumps(result['cohort'])
    assert 'template' not in result['source_observed']
    assert all('global_signal' not in person for person in result['persons'].values())


def test_pilot_decodes_only_first_bold_all_metadata(fixture, monkeypatch):
    original = r.decode_values
    shapes = []
    def capture(raw, observed, *args):
        shapes.append(observed['shape'])
        return original(raw, observed, *args)
    monkeypatch.setattr(r, 'decode_values', capture)
    result = run(fixture, pilot=True)
    assert result['status'] == 'resource_pilot' and result['subject_ids'] == ['sub-pixar001']
    assert len(result['cohort']) == len(result['source_observed']['persons']) == 2
    assert len(result['analysis_observed']['persons']) == 1
    assert shapes == [[11, 11, 11, 48]]


def test_geometry_only_has_no_signal_decode_or_cleaning(fixture, monkeypatch):
    monkeypatch.setattr(r, 'decode_values', lambda *args: pytest.fail('geometry decoded BOLD'))
    result = run(fixture, geometry_only=True)
    assert result['status'] == 'geometry_only' and result['persons'] == {}
    assert result['subject_ids'] == [] and len(result['structural_subject_ids']) == 2
    assert result['analysis_observed']['persons'] == []
    assert len(result['source_observed']['persons']) == len(result['cohort']) == 2
    assert all(len(p['roi_supports']) == 3 for p in result['source_observed']['persons'])


@pytest.mark.parametrize('kwargs', [{'pilot':1}, {'geometry_only':1}, {'pilot':np.bool_(True)},
                                   {'geometry_only':np.bool_(True)}, {'pilot':True,'geometry_only':True}])
def test_mode_flags_are_strict_and_mutually_exclusive(fixture, kwargs):
    with pytest.raises(ValueError, match='exclusive_boolean_modes'): run(fixture, **kwargs)


def test_all_sources_authenticate_before_header_or_coordinate_parse(fixture, monkeypatch):
    row = fixture['manifest']['files'][-1]
    (fixture['source'] / row['path']).write_bytes(b'bad')
    monkeypatch.setattr(r, 'header', lambda *args: pytest.fail('header before authentication'))
    original = r.load_modules
    def modules(policy):
        out = original(policy)
        out['coordinate_contract'].parse_power = lambda *a, **kw: pytest.fail('coordinates before authentication')
        return out
    monkeypatch.setattr(r, 'load_modules', modules)
    with pytest.raises(ValueError, match='source_size'): run(fixture)


def test_all_subject_metadata_checked_before_pilot_signal(fixture, monkeypatch):
    mutate_cell(fixture, 'trans_x', 7, 'INVALID', sid='sub-pixar002')
    monkeypatch.setattr(r, 'decode_values', lambda *a: pytest.fail('premature BOLD decode'))
    with pytest.raises(ValueError, match='invalid_confound_token'): run(fixture, pilot=True)


@pytest.mark.parametrize('mutation', ['extra_file','extra_dir','source_link','internal_manifest','duplicate_coordinate'])
def test_closed_inventory_and_manifest_binding(fixture, mutation):
    source = fixture['source']
    if mutation == 'extra_file': (source / 'extra').write_bytes(b'x')
    elif mutation == 'extra_dir': (source / 'unused').mkdir()
    elif mutation == 'source_link': (source / 'link').symlink_to(source / 'participants.tsv')
    elif mutation == 'internal_manifest': (source / 'source_manifest.json').write_bytes(b'{}')
    else:
        payload = b'ROI,X,Y,Z\nA,0,0,0\nB,1,0,0\nC,2,0,0\n'
        (source / 'atlas/second.csv').write_bytes(payload)
        fixture['manifest']['files'].append(pinned_row('atlas/second.csv', 'coordinates', None, payload))
        repin(fixture)
    with pytest.raises(ValueError): run(fixture)


@pytest.mark.parametrize('endian', ['<','>'])
@pytest.mark.parametrize('extension', [False,True])
def test_scaled_fortran_buffer_decoder(fixture, endian, extension):
    h = r.load_modules(fixture['policy'])['inspect_structure']
    hp = h.Policy(fixture['policy'].source_sha, fixture['policy'].versions)
    values = np.arange(3 * 4 * 5 * 7, dtype=np.int16).reshape(3,4,5,7)
    raw = nifti(values, endian=endian, slope=2.5, intercept=-3., extension=extension)
    observed, offset, dtype = r.header(raw, 4, h, hp, lambda: None)
    actual = r.decode_values(raw, observed, offset, dtype, fixture['policy'], lambda: None)
    np.testing.assert_array_equal(actual, values.astype(np.float64) * 2.5 - 3.)
    assert actual.flags.c_contiguous and actual.dtype == np.float64
    assert observed['storage_dtype'] == np.dtype(endian + 'i2').str


@pytest.mark.parametrize('mutation', ['truncated','trailing_gzip','trailing_raw','short_payload','long_payload','bad_extension'])
def test_image_payload_length_and_eof_guards(fixture, mutation):
    h = r.load_modules(fixture['policy'])['inspect_structure']
    hp = h.Policy(fixture['policy'].source_sha, fixture['policy'].versions)
    raw = nifti(np.ones((3,4,5,7),dtype=np.float32), extension=mutation=='bad_extension')
    if mutation == 'truncated': raw = raw[:-4]
    if mutation == 'trailing_gzip': raw += gzip.compress(b'x')
    if mutation == 'trailing_raw': raw += b'x'
    if mutation == 'short_payload': raw = gzip.compress(gzip.decompress(raw)[:-1])
    if mutation == 'long_payload': raw = gzip.compress(gzip.decompress(raw) + b'x')
    if mutation == 'bad_extension':
        bad=bytearray(gzip.decompress(raw));struct.pack_into('<i',bad,352,15);raw=gzip.compress(bad)
    with pytest.raises((ValueError,zlib.error)):
        observed,offset,dtype=r.header(raw,4,h,hp,lambda:None)
        r.decode_values(raw,observed,offset,dtype,fixture['policy'],lambda:None)


@pytest.mark.parametrize('name', ['trans_x','framewise_displacement'])
@pytest.mark.parametrize('token,frame,valid', [('n/a',0,True),('',0,True),('n/a',7,True),('',47,True),
    ('NaN',0,False),('inf',1,False),('-Infinity',2,False),('bad',0,False),('NA',4,False)])
def test_exact_missing_tokens_any_original_row(fixture,name,token,frame,valid):
    mutate_cell(fixture,name,frame,token)
    if not valid:
        with pytest.raises(ValueError):run(fixture,geometry_only=True)
    else:
        p=run(fixture,geometry_only=True)['source_observed']['persons'][0]
        ledger=p['mean_fd_missing_entries'] if name=='framewise_displacement' else p['missing_selected_entries']
        assert dict(frame_index=frame,column_name=name,original_token=token,applied_value=0.) in ledger


def test_all_missing_fd_zero_fill_retains_original_denominator(fixture):
    for frame in range(48):mutate_cell(fixture,'framewise_displacement',frame,'n/a')
    result=run(fixture,geometry_only=True)
    assert result['covariates']['sub-pixar001']['mean_fd']==0.
    p=result['source_observed']['persons'][0]
    assert p['mean_fd_observed_count']==0 and p['mean_fd_denominator']==48
    assert p['mean_fd_zero_filled_sum']==0. and len(p['mean_fd_missing_entries'])==48


def test_fd_first_finite_zero_is_observed_and_not_a_regressor(fixture):
    mutate_cell(fixture,'framewise_displacement',0,'0')
    baseline=run(fixture,pilot=True)
    for frame in range(48):mutate_cell(fixture,'framewise_displacement',frame,'1000')
    changed=run(fixture,pilot=True)
    assert baseline['cohort'][0]['mean_fd_observed_count']==48
    assert baseline['cohort'][0]['mean_fd_missing_frame_indices']==[]
    assert changed['cohort'][0]['mean_fd']==1000.
    np.testing.assert_array_equal(baseline['persons']['sub-pixar001']['cleaned_roi'],
                                  changed['persons']['sub-pixar001']['cleaned_roi'])


@pytest.mark.parametrize('kind', ['frames','columns','missing_fd','duplicate_columns','phenotype_duplicate','age_nan','group_unknown'])
def test_source_tables_fail_closed(fixture,kind):
    if kind in ('frames','columns','missing_fd','duplicate_columns'):
        row=next(row for row in fixture['manifest']['files'] if row['role']=='confounds')
        raw=(fixture['source']/row['path']).read_bytes()
        if kind=='frames':raw=b'\n'.join(raw.splitlines()[:-1])+b'\n'
        if kind=='columns':raw=raw.replace(b'trans_x',b'trans_missing',1)
        if kind=='missing_fd':raw=raw.replace(b'framewise_displacement',b'not_fd',1)
        if kind=='duplicate_columns':raw=raw.replace(b'trans_x',b'trans_y',1)
        replace_member(fixture,'confounds',row['participant_id'],raw)
    else:
        raw=(fixture['source']/'participants.tsv').read_bytes()
        if kind=='phenotype_duplicate':raw=raw.replace(b'sub-pixar002',b'sub-pixar001')
        if kind=='age_nan':raw=raw.replace(b'\t25\t',b'\tnan\t')
        if kind=='group_unknown':raw=raw.replace(b'\tadult\t',b'\tunknown\t')
        replace_member(fixture,'participants',None,raw)
    with pytest.raises(ValueError):run(fixture,pilot=True)


def test_post_consumption_rehash_catches_same_size_change(fixture,monkeypatch):
    original=r.decode_values
    target=fixture['source']/'provenance/nilearn_0_12_1/LICENSE'
    before=target.read_bytes()
    def change(*args):
        out=original(*args);target.write_bytes(b'X'+before[1:]);return out
    monkeypatch.setattr(r,'decode_values',change)
    with pytest.raises(ValueError,match='source_sha256'):run(fixture,pilot=True)


@pytest.mark.parametrize('key',['source_sha','method_sha','schema_sha','reporting_sha'])
def test_wrong_document_or_kernel_pin(fixture,key):
    fixture['policy']=replace(fixture['policy'],**{key:'0'*64})
    with pytest.raises(ValueError):run(fixture,pilot=True)


@pytest.mark.parametrize('filename',list(r.MODULE_PINS))
def test_entire_code_closure_authenticates_before_any_compile(fixture,monkeypatch,filename):
    fixture['policy']=replace(fixture['policy'],module_pins=dict(fixture['policy'].module_pins,**{filename:'0'*64}))
    # reporting pin has its explicit cross-pin check; all other files fail exact_read.
    monkeypatch.setattr(builtins,'compile',lambda *a,**kw:pytest.fail('compiled before complete closure authentication'))
    with pytest.raises(ValueError):r.load_modules(fixture['policy'])


def test_document_duplicate_key_rejected_after_same_buffer_pin(fixture):
    raw=b'{"task_id":"wrong",'+fixture['method_path'].read_bytes()[1:]
    fixture['method_path'].write_bytes(raw);fixture['policy']=replace(fixture['policy'],method_sha=sha(raw))
    with pytest.raises(ValueError,match='duplicate_json_key'):run(fixture)


@pytest.mark.parametrize('field', ['missing_tokens','spatial_units','frame_counts','coordinate_columns','coordinate_hash'])
def test_unfrozen_method_choices_refused(fixture,field):
    if field=='missing_tokens':fixture['method']['confounds']['missingness']['missing_tokens']=None
    elif field=='spatial_units':fixture['method']['source']['spatial_unit_policy']['allowed_bold_header_units']=None
    elif field=='frame_counts':fixture['method']['source']['frame_counts_by_subject']=None
    elif field=='coordinate_columns':fixture['method']['roi_geometry']['source_columns']=None
    else:fixture['method']['roi_geometry']['coordinates_sha256']=None
    if field!='coordinate_hash':repin(fixture)
    else:
        raw=json.dumps(fixture['method']).encode();fixture['method_path'].write_bytes(raw)
        fixture['policy']=replace(fixture['policy'],method_sha=sha(raw))
        fixture['schema']['method_sha256']=sha(raw);raw=json.dumps(fixture['schema']).encode()
        fixture['schema_path'].write_bytes(raw);fixture['policy']=replace(fixture['policy'],schema_sha=sha(raw))
    with pytest.raises(ValueError):run(fixture)


def test_contributing_nonfinite_fails_unused_nonfinite_allowed(fixture):
    sid=fixture['policy'].subject_ids[0]
    values=fixture['arrays'][sid].copy();values[0,0,0,0]=np.nan
    replace_member(fixture,'bold',sid,nifti(values));run(fixture,pilot=True)
    values[5,5,5,0]=np.inf;replace_member(fixture,'bold',sid,nifti(values))
    with pytest.raises(ValueError,match='nonfinite_contributing_values'):run(fixture,pilot=True)


def test_empty_single_sphere_fails_geometry_without_decoding(fixture,monkeypatch):
    raw=b'ROI,X,Y,Z\nR-A,-2,0,0\n007,0,0,0\nZ,1000,0,0\n'
    replace_member(fixture,'coordinates',None,raw)
    monkeypatch.setattr(r,'decode_values',lambda *a:pytest.fail('decoded before geometry checked'))
    with pytest.raises(ValueError,match='empty_sphere'):run(fixture,geometry_only=True)


def test_decoded_cap_and_deadline(fixture):
    fixture['policy']=replace(fixture['policy'],max_decoded_bytes=100)
    with pytest.raises(ValueError,match='decoded_image_cap'):run(fixture,pilot=True)
    fixture['policy']=replace(fixture['policy'],max_decoded_bytes=512*1024**2,wall_seconds=0)
    with pytest.raises(ValueError,match='source_deadline'):run(fixture,pilot=True)


def test_final_source_unchanged_and_geometry_cached(fixture,monkeypatch):
    original=r.load_modules;calls=[]
    def load(policy):
        out=original(policy);geometry=out['source_numerics'].sphere_supports
        def count(*a):calls.append(1);return geometry(*a)
        out['source_numerics'].sphere_supports=count
        return out
    monkeypatch.setattr(r,'load_modules',load)
    before={p:p.read_bytes() for p in fixture['source'].rglob('*') if p.is_file()}
    run(fixture)
    assert calls==[1]
    assert {p:p.read_bytes() for p in fixture['source'].rglob('*') if p.is_file()}==before


@pytest.mark.parametrize('field',['md5','git_blob_sha1'])
def test_secondary_digest_binding(fixture,field):
    row=fixture['manifest']['files'][-1];row[field]='0'*len(row[field]);repin(fixture)
    with pytest.raises(ValueError,match='source_'+field):run(fixture)


def test_nonselected_pilot_bold_hash_failure_is_fatal(fixture):
    row=next(row for row in fixture['manifest']['files'] if row['role']=='bold' and row['participant_id']=='sub-pixar002')
    target=fixture['source']/row['path'];raw=target.read_bytes()
    target.write_bytes(bytes([raw[0]^1])+raw[1:])
    with pytest.raises(ValueError,match='source_sha256'):run(fixture,pilot=True)


def test_document_parent_symlink_refused(fixture):
    link=fixture['method_path'].parent/'link';link.symlink_to(fixture['method_path'].parent,target_is_directory=True)
    fixture['method_path']=link/fixture['method_path'].name
    with pytest.raises(ValueError,match='symlink_input'):run(fixture)


def test_unknown_units_need_public_policy_but_raw_clock_stays(fixture):
    sid=fixture['policy'].subject_ids[0]
    replace_member(fixture,'bold',sid,nifti(fixture['arrays'][sid],units=0))
    with pytest.raises(ValueError,match='bold_units'):run(fixture,pilot=True)
    fixture['method']['source']['spatial_unit_policy']['allowed_bold_header_units']=['mm','unknown'];repin(fixture)
    header=run(fixture,pilot=True)['source_observed']['persons'][0]['bold_header']
    assert header['spatial_units']==header['temporal_units']=='unknown'
    assert header['zooms'][3]==2.0
