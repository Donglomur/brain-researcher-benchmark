"""Manufactured closed-source and writer fixtures; no originals or network."""
import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import warnings

import nibabel as nib
import numpy as np
import pytest


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1]/'solution'/filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


k = load_module('signal_kernel', 'signal_kernel.py')
s = load_module('source_reader', 'source_reader.py')
c = load_module('fcvar_oracle_compute', 'compute.py')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def image_bytes(values, *, endian='<', slope=1., inter=0., tr=2., offset=352, extension=False):
    values = np.asarray(values)
    h = nib.Nifti1Header(endianness=endian)
    h.set_data_dtype(values.dtype)
    h.set_data_shape(values.shape)
    h.set_sform(np.diag([2., 2., 2., 1.]), code=2)
    h.set_qform(np.diag([2., 2., 2., 1.]), code=1)
    h.set_xyzt_units('mm', 'sec')
    h.set_zooms((2., 2., 2., tr) if values.ndim == 4 else (2., 2., 2.))
    h['vox_offset'] = offset
    h['scl_slope'], h['scl_inter'] = slope, inter
    if extension:
        assert offset == 384
        extra = b'\x01\0\0\0' + struct.pack(endian+'ii', 32, 6) + b'fixture'.ljust(24, b'\0')
    else:
        extra = b'\0' * (offset-348)
    payload = values.astype(values.dtype.newbyteorder(endian)).tobytes(order='F')
    return h.binaryblock + extra + payload


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False)+'\n').encode()


def bundle(tmp_path, monkeypatch):
    root = tmp_path/'source'; root.mkdir()
    rows = []
    n = 64
    atlas = np.zeros((4, 4, 4), dtype=np.int16)
    atlas.flat[:48] = np.arange(1, 49)
    bold = np.random.default_rng(8).normal(size=(4, 4, 4, n)).astype(np.float32)
    header = list(k.CONFOUND_COLUMNS) + ['unused']
    conf = np.random.default_rng(9).normal(size=(n, len(header)))
    conf_bytes = ('\t'.join(header)+'\n'+'\n'.join('\t'.join(map(repr, map(float, row))) for row in conf)+'\n').encode()
    def add(path, role, raw, sid=None):
        target = root/path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        rows.append(dict(path=path, role=role, participant_id=sid, size_bytes=len(raw), sha256=digest(raw), md5=hashlib.md5(raw).hexdigest()))
    for sid in s.FIXED_IDS:
        add(f'data/{sid}/bold.nii.gz', 'bold', gzip.compress(image_bytes(bold), mtime=0), sid)
        add(f'data/{sid}/confounds.tsv', 'confounds', conf_bytes, sid)
    add('atlas/labels.nii.gz', 'atlas_image', gzip.compress(image_bytes(atlas), mtime=0))
    xml = '<atlas><data>'+''.join(f'<label index="{j}"> ROI {j+1} </label>' for j in range(48))+'</data></atlas>'
    add('atlas/labels.xml', 'atlas_labels', xml.encode())
    add('metadata/ids.txt', 'cohort_ids', ('\n'.join(s.FIXED_IDS)+'\n').encode())
    add('metadata/phenotype.csv', 'phenotype_metadata', (',Subject,site\n'+'\n'.join(f'{j},{int(sid)},TEST' for j,sid in enumerate(s.FIXED_IDS))+'\n').encode())
    add('metadata/timing.csv', 'slice_timing_metadata', b'Site,TR (seconds),Reference,Acquisition\nTEST,2,fake,fake\n')
    add('provenance/adhd.rst', 'provenance_adhd_notice', b'fake scientific-source-free notice\n')
    add('provenance/ho.rst', 'provenance_ho_notice', b'fake atlas notice\n')
    manifest = dict(task_id='FCVAR-001', files=rows)
    method = dict(task_id='FCVAR-001', contract_status='frozen_manufactured_fixture',
        source=dict(participant_ids=list(s.FIXED_IDS), n_frames_by_participant={sid:n for sid in s.FIXED_IDS},
            tr_sec_by_participant={sid:2. for sid in s.FIXED_IDS},
            phenotype_join=dict(delimiter=',', id_column='Subject', site_column='site', allow_leading_unnamed_index=True),
            site_timing_join=dict(delimiter=',', site_column='Site', tr_column='TR (seconds)', tr_units='sec')),
        temporal_cleaning=dict(confound_columns=list(k.CONFOUND_COLUMNS)))
    schema = dict(task_id='FCVAR-001')
    (root/'source_manifest.json').write_bytes(json_bytes(manifest))
    method_path, schema_path = tmp_path/'method.json', tmp_path/'schema.json'
    method_path.write_bytes(json_bytes(method)); schema_path.write_bytes(json_bytes(schema))
    monkeypatch.setattr(s, 'SOURCE_SHA', digest(json_bytes(manifest)))
    monkeypatch.setattr(s, 'METHOD_SHA', digest(json_bytes(method)))
    monkeypatch.setattr(s, 'SCHEMA_SHA', digest(json_bytes(schema)))
    return dict(root=root, manifest=manifest, method=method, schema=schema,
                method_path=method_path, schema_path=schema_path, atlas=atlas, bold=bold)


def authenticate(b):
    return s.authenticate(b['root'], b['method_path'], b['schema_path'])


def repin_member(b, monkeypatch, role, raw, sid=None):
    row = next(r for r in b['manifest']['files'] if r['role'] == role and r['participant_id'] == sid)
    (b['root']/row['path']).write_bytes(raw)
    row.update(size_bytes=len(raw), sha256=digest(raw), md5=hashlib.md5(raw).hexdigest())
    encoded = json_bytes(b['manifest'])
    (b['root']/'source_manifest.json').write_bytes(encoded)
    monkeypatch.setattr(s, 'SOURCE_SHA', digest(encoded))


def test_unfrozen_pins_fail_before_source_open(tmp_path, monkeypatch):
    monkeypatch.setattr(s, 'SOURCE_SHA', None)
    with pytest.raises(k.PreconditionError, match='pins'):
        s.authenticate(tmp_path/'missing', tmp_path/'method', tmp_path/'schema')


def test_authenticate_closed67_and_all_hashes(tmp_path, monkeypatch):
    b = bundle(tmp_path, monkeypatch)
    seen = []
    original = s.read_member
    def track(root, row):
        seen.append(row['path']); return original(root, row)
    monkeypatch.setattr(s, 'read_member', track)
    result = authenticate(b)
    assert len(seen) == 67 and len(set(seen)) == 67
    assert result['pins']['source_manifest_sha256'] == s.SOURCE_SHA


@pytest.mark.parametrize('kind', ['extra_file', 'extra_directory', 'symlink', 'fifo', 'source_change', 'manifest_change', 'method_change', 'schema_change'])
def test_authentication_rejects_invalid_inventory_or_pin(tmp_path, monkeypatch, kind):
    b = bundle(tmp_path, monkeypatch)
    root = b['root']
    if kind == 'extra_file': (root/'extra').write_bytes(b'x')
    if kind == 'extra_directory': (root/'extra').mkdir()
    if kind == 'symlink': (root/'linked').symlink_to(tmp_path/'missing')
    if kind == 'fifo': os.mkfifo(root/'pipe')
    if kind == 'source_change':
        path = root/b['manifest']['files'][0]['path']; raw=path.read_bytes(); path.write_bytes(bytes([raw[0]^1])+raw[1:])
    if kind == 'manifest_change': (root/'source_manifest.json').write_bytes(b'{}')
    if kind == 'method_change': b['method_path'].write_bytes(b'{}')
    if kind == 'schema_change': b['schema_path'].write_bytes(b'{}')
    with pytest.raises(k.PreconditionError): authenticate(b)


@pytest.mark.parametrize('kind', ['duplicate', 'escape', 'wrong_person', 'missing_role', 'bool_size', 'md5', 'git_blob'])
def test_manifest_and_secondary_identity_guards(tmp_path, monkeypatch, kind):
    b = bundle(tmp_path, monkeypatch)
    rows = b['manifest']['files']
    if kind == 'duplicate': rows[1]['path'] = rows[0]['path']
    if kind == 'escape': rows[0]['path'] = '../outside'
    if kind == 'wrong_person': rows[0]['participant_id'] = '0000000'
    if kind == 'missing_role': rows[-1]['role'] = rows[-2]['role']
    if kind == 'bool_size': rows[0]['size_bytes'] = True
    if kind == 'md5': rows[0]['md5'] = '0'*32
    if kind == 'git_blob': rows[0]['git_blob_sha1'] = '0'*40
    raw=json_bytes(b['manifest']); (b['root']/'source_manifest.json').write_bytes(raw)
    monkeypatch.setattr(s, 'SOURCE_SHA', digest(raw))
    with pytest.raises(k.PreconditionError): authenticate(b)


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":1e999}'])
def test_strict_json(raw):
    with pytest.raises(k.PreconditionError): s.strict_json(raw)


def test_documentary_unnamed_index_is_role_specific_and_preserved():
    raw=b',Subject,site\n0,10042,TEST\n'
    columns,rows=s.table(raw,',',allow_leading_unnamed=True)
    assert columns==['','Subject','site'] and rows[0]['']=='0'
    with pytest.raises(k.PreconditionError): s.table(raw,',')


@pytest.mark.parametrize('header',[b'Subject,,site',b',Subject,',b',,Subject',b'',b'Subject,Subject,site'])
def test_documentary_allowance_does_not_allow_other_empty_or_duplicate_columns(header):
    raw=header+b'\n'+b','.join([b'0']*(header.count(b',')+1))+b'\n'
    with pytest.raises(k.PreconditionError): s.table(raw,',',allow_leading_unnamed=True)


@pytest.mark.parametrize('endian', ['<', '>'])
@pytest.mark.parametrize('compressed', [False, True])
def test_calibrated_decode_endian_and_compression(endian, compressed):
    values = np.arange(2*3*4*5, dtype=np.int16).reshape(2,3,4,5)
    raw = image_bytes(values, endian=endian, slope=2., inter=-3.)
    raw = gzip.compress(raw) if compressed else raw
    got, _, meta = s.decode_image(raw, compressed)
    np.testing.assert_array_equal(got, values*2.-3.)
    assert meta['effective_slope'] == 2. and meta['effective_intercept'] == -3.


def test_extension_offset_and_zero_slope():
    values = np.arange(48, dtype=np.float32).reshape(2,3,4,2)
    raw = image_bytes(values, offset=384, extension=True, slope=0., inter=0.)
    got, _, meta = s.decode_image(raw, False)
    np.testing.assert_array_equal(got, values)
    assert meta['effective_slope'] == 1. and meta['raw_scl_slope'] == 0.


@pytest.mark.parametrize('kind', ['truncated', 'trailing', 'offset', 'huge'])
def test_nifti_size_guards(kind):
    raw = image_bytes(np.zeros((2,3,4,5), dtype=np.float32))
    if kind == 'truncated': raw=raw[:-1]
    if kind == 'trailing': raw+=b'x'
    if kind in ('offset', 'huge'):
        h=nib.Nifti1Header(binaryblock=raw[:348],check=False)
        if kind=='offset': h['vox_offset']=351
        else: h.set_data_shape((10000,10000,10000,10000))
        raw=h.binaryblock+raw[348:]
    with pytest.raises(k.PreconditionError): s.decode_image(raw, False)


def test_header_only_does_not_need_payload():
    raw=image_bytes(np.zeros((2,3,4,5),dtype=np.float32))[:352]
    _, _, meta, expected=s.image_header(raw,False)
    assert meta['shape']==[2,3,4,5] and expected>352


@pytest.mark.parametrize('unit,factor',[('sec',1.),('msec',1e-3),('usec',1e-6)])
def test_documentary_clock_uses_declared_header_float32_precision(unit,factor):
    assert s.documentary_at_header_precision(1.96,unit)==float(np.float32(1.96/factor))*factor


@pytest.mark.parametrize('value,unit',[(float('nan'),'sec'),(float('inf'),'sec'),(0.,'sec'),(2.,'unknown')])
def test_documentary_clock_rejects_nonfinite_or_unsupported(value,unit):
    with pytest.raises(k.PreconditionError):s.documentary_at_header_precision(value,unit)


@pytest.mark.parametrize('kind', ['entity', 'duplicate', 'missing', 'bad_index'])
def test_xml_guards(kind):
    labels=[f'<label index="{j}">label{j}</label>' for j in range(48)]
    if kind=='entity': labels.insert(0,'<!ENTITY evil SYSTEM "file:///forbidden">')
    if kind=='duplicate': labels[-1]=labels[0]
    if kind=='missing': labels.pop()
    if kind=='bad_index': labels[0]='<label index="-1">bad</label>'
    raw=('<atlas><data>'+''.join(labels)+'</data></atlas>').encode()
    with pytest.raises(k.PreconditionError): s.atlas_labels(raw)


def test_xml_strip_only_preserves_original_spelling():
    raw=('<atlas><data>'+''.join(f'<label index="{j}"> A  B{j} </label>' for j in range(48))+'</data></atlas>').encode()
    assert s.atlas_labels(raw)[0]=='A  B0'


def test_geometry_copy_full_matrix_and_grid_bound_digest(monkeypatch):
    atlas=np.arange(8,dtype=np.int16).reshape(2,2,2)
    affine=np.eye(4)
    supports,digests=s.spatial_support(atlas,affine,atlas.shape,affine)
    assert supports[0].tolist()==[1] and len(supports[47])==0
    expected=hashlib.sha256(b'FCVAR_support_v3\n'+np.array([2,2,2],dtype='<i8').tobytes()+affine.astype('<f8').tobytes()+np.array([1],dtype='<i8').tobytes()).hexdigest()
    assert digests[0]==expected
    seen=[]
    def transform(labels,**kwargs):
        seen.append(kwargs); return np.zeros(kwargs['output_shape'],dtype=labels.dtype)
    monkeypatch.setattr(s.ndimage,'affine_transform',transform)
    s.spatial_support(atlas,affine,(3,2,2),affine)
    assert seen[0]['matrix'].shape==(3,3) and np.array_equal(seen[0]['matrix'],np.eye(3))
    shifted=affine.copy();shifted[0,3]=1
    _, changed=s.spatial_support(atlas,affine,(2,2,2),shifted)
    assert changed[0]!=digests[0]


@pytest.mark.parametrize('value',[np.nan,np.inf,.5,-1,49])
def test_atlas_all_values_finite_integer_domain(value):
    atlas=np.zeros((2,2,2));atlas.flat[-1]=value
    with pytest.raises(k.PreconditionError): s.spatial_support(atlas,np.eye(4),atlas.shape,np.eye(4))


def test_outside_roi_nan_allowed_inside_nan_rejected_before_activity():
    atlas=np.zeros((2,2,2),dtype=np.int16);atlas.flat[0]=1
    supports,_=s.spatial_support(atlas,np.eye(4),atlas.shape,np.eye(4))
    bold=np.ones((2,2,2,40));bold[-1,-1,-1,:]=np.nan
    values=s.extract_means(bold,supports)
    assert np.all(values[:,0]==1) and np.all(values[:,1:]==0)
    bold[0,0,0,0]=np.nan
    with pytest.raises(k.PreconditionError,match='before activity'): s.extract_means(bold,supports)


def test_pilot_hashes_and_structures_all_but_decodes_only_first_bold(tmp_path,monkeypatch):
    b=bundle(tmp_path,monkeypatch); inputs=authenticate(b)
    original=s.decode_image; decoded=[]; checkpoints=[]
    def spy(raw,compressed):
        result=original(raw,compressed);decoded.append(result[0].ndim);return result
    monkeypatch.setattr(s,'decode_image',spy)
    result=s.load(inputs,subjects=[s.FIXED_IDS[0]],on_person=lambda sid,p:checkpoints.append(sid))
    assert decoded==[3,4] and checkpoints==[s.FIXED_IDS[0]]
    assert len(result['source_observed']['persons'])==30 and len(result['persons'])==1
    assert result['source_observed']['persons'][s.FIXED_IDS[0]]['source_participant_token']==str(int(s.FIXED_IDS[0]))
    assert result['source_observed']['phenotype_columns']==['','Subject','site']
    assert result['source_observed']['slice_timing_columns']==['Site','TR (seconds)','Reference','Acquisition']
    assert result['roi_labels'][0]=='ROI 1'


def test_documentary_decimal_vs_nifti_float32_clock_is_not_override(tmp_path,monkeypatch):
    b=bundle(tmp_path,monkeypatch)
    # Each fake source keeps the same full-frame finite signal and source IDs.
    raw=gzip.compress(image_bytes(b['bold'],tr=1.96),mtime=0)
    for sid in s.FIXED_IDS:repin_member(b,monkeypatch,'bold',raw,sid)
    repin_member(b,monkeypatch,'slice_timing_metadata',b'Site,TR (seconds),Reference,Acquisition\nTEST,1.96,fake,fake\n')
    b['method']['source']['tr_sec_by_participant']={sid:float(np.float32(1.96)) for sid in s.FIXED_IDS}
    encoded=json_bytes(b['method']);b['method_path'].write_bytes(encoded);monkeypatch.setattr(s,'METHOD_SHA',digest(encoded))
    result=s.load(authenticate(b),subjects=[s.FIXED_IDS[0]])
    clock=result['source_observed']['persons'][s.FIXED_IDS[0]]['operational_TR_s']
    assert clock==1.9600000381469727 and clock!=1.96


@pytest.mark.parametrize('role',['atlas_image','bold'])
def test_source_spatial_units_must_be_mm(tmp_path,monkeypatch,role):
    b=bundle(tmp_path,monkeypatch);sid=s.FIXED_IDS[0] if role=='bold' else None
    row=next(r for r in b['manifest']['files'] if r['role']==role and r['participant_id']==sid)
    raw=gzip.decompress((b['root']/row['path']).read_bytes())
    header=nib.Nifti1Header(binaryblock=raw[:348],check=False);header.set_xyzt_units('meter','sec')
    repin_member(b,monkeypatch,role,gzip.compress(header.binaryblock+raw[348:],mtime=0),sid)
    with pytest.raises(k.PreconditionError,match='mm'):s.load(authenticate(b),subjects=[s.FIXED_IDS[0]])


@pytest.mark.parametrize('kind',['source_after_auth','missing_selected','nonfinite_confound','phenotype_duplicate','site_clock'])
def test_source_load_preconditions(tmp_path,monkeypatch,kind):
    b=bundle(tmp_path,monkeypatch);sid=s.FIXED_IDS[0]
    if kind=='source_after_auth':
        inputs=authenticate(b);row=next(r for r in b['manifest']['files'] if r['role']=='bold')
        path=b['root']/row['path'];raw=path.read_bytes();path.write_bytes(bytes([raw[0]^1])+raw[1:])
    else:
        if kind=='missing_selected':
            repin_member(b,monkeypatch,'confounds',b'wrong\n'+b'0\n'*64,sid)
        if kind=='nonfinite_confound':
            row=next(r for r in b['manifest']['files'] if r['role']=='confounds' and r['participant_id']==sid)
            raw=(b['root']/row['path']).read_bytes();lines=raw.splitlines();fields=lines[1].split(b'\t');fields[0]=b'nan';lines[1]=b'\t'.join(fields)
            repin_member(b,monkeypatch,'confounds',b'\n'.join(lines)+b'\n',sid)
        if kind=='phenotype_duplicate':
            repin_member(b,monkeypatch,'phenotype_metadata',b'Subject,site\n10042,TEST\n0010042,TEST\n')
        if kind=='site_clock':
            repin_member(b,monkeypatch,'slice_timing_metadata',b'Site,TR (seconds),Reference,Acquisition\nTEST,3,fake,fake\n')
        inputs=authenticate(b)
    with pytest.raises(k.PreconditionError): s.load(inputs,subjects=[sid])


def fake_basis(ids):
    persons={}
    for sid in ids:
        raw=np.zeros((48,48));clean=raw.copy();active=np.zeros(48,dtype=bool)
        persons[sid]=dict(site='TEST',n_frames=48,tr_sec=2.,source_paths=dict(bold=sid+'.nii',confounds=sid+'.tsv'),
            raw=raw,clean=clean,active=active,geometry_present=np.ones(48,dtype=bool),
            n_voxels=np.ones(48,dtype=np.int64),support_sha256=np.array(['0'*64]*48),
            raw_sample_sd=np.zeros(48),prestandardization_centered_l2=np.zeros(48),
            activity_threshold=np.zeros(48),full_clean_centered_l2=np.zeros(48),cleaning_rank=13)
    return dict(participant_ids=list(ids),roi_ids=np.arange(1,49),roi_labels=[f'ROI{i}' for i in range(1,49)],
        persons=persons,pins=dict(source_manifest_sha256='a'*64,method_contract_sha256='b'*64,output_schema_sha256='c'*64),
        source_files=[],source_observed={})


def writer_setup(tmp_path,monkeypatch,pilot=False):
    data=tmp_path/'inputs';data.mkdir()
    method=tmp_path/'method.json';method.write_text('{}')
    schema=tmp_path/'schema.json';schema.write_text('{}')
    args=argparse.Namespace(data_dir=str(data),contract_path=str(method),schema_path=str(schema),
        output_dir=str(tmp_path/'output'),private_dir=str(tmp_path/'private'),report=str(tmp_path/'report.json'),
        pilot_first_person=pilot,seed=0)
    monkeypatch.setattr(s,'authenticate',lambda *a:{})
    def fake_load(inputs,subjects=None,progress=None,on_person=None):
        warnings.warn('manufactured source warning',UserWarning)
        basis=fake_basis(list(s.FIXED_IDS) if subjects is None else subjects)
        if on_person:
            for sid,p in basis['persons'].items():on_person(sid,p)
        return basis
    monkeypatch.setattr(s,'load',fake_load)
    monkeypatch.setattr(c,'versions',lambda:dict(python='fixture',numpy='fixture',scipy='fixture',nibabel='fixture',nilearn='fixture'))
    return args


@pytest.mark.parametrize('pilot',[False,True])
def test_writer_seven_files_status_warning_and_axes(tmp_path,monkeypatch,pilot):
    args=writer_setup(tmp_path,monkeypatch,pilot)
    got=c.compute(args);out=Path(args.output_dir)
    assert set(p.name for p in out.iterdir())=={'cohort.csv','roi_evidence.npz','variability.csv','surrogate_statistics.csv','dynamics.json','run_metadata.json','findings.md'}
    metadata=json.loads((out/'run_metadata.json').read_text())
    assert metadata['warnings']==['manufactured source warning']
    assert metadata['status']==('resource_pilot' if pilot else 'ok')
    assert got['observed_rows']==(0 if pilot else 90) and got['surrogate_rows']==(0 if pilot else 4500)
    with np.load(out/'roi_evidence.npz',allow_pickle=False) as arrays:
        assert arrays['raw_roi_mean'].shape==((1 if pilot else 30)*48,48)
        assert arrays['phase_angles'].shape==(0,50) if pilot else arrays['phase_angles'].shape==(30*3*25,50)
    result=json.loads((out/'dynamics.json').read_text())
    assert result['status']==('resource_pilot' if pilot else 'complete')
    if pilot:
        assert result['windows'] is None and not result['resource_pilot_scope']['phase_inference_computed']


@pytest.mark.parametrize('late',[False,True])
def test_early_and_late_failure_preserve_marker_and_existing_evidence(tmp_path,monkeypatch,late):
    args=writer_setup(tmp_path,monkeypatch,True)
    if late:
        original=c.write_json
        def write(path,value):
            if Path(path)==Path(args.report):raise OSError('late outer report failure')
            return original(path,value)
        monkeypatch.setattr(c,'write_json',write)
    else:
        monkeypatch.setattr(s,'load',lambda *a,**kw:(_ for _ in ()).throw(ValueError('early failure')))
    with pytest.raises((ValueError,OSError)):c.compute(args)
    out=Path(args.output_dir)
    marker=json.loads((out/'failure_report.json').read_text())
    assert marker['status']=='failed_precondition'
    assert (out/'run_metadata.json').exists() is late


@pytest.mark.parametrize('kind',['existing','inside_source','same_private','symlink'])
def test_output_guards_before_mutation(tmp_path,monkeypatch,kind):
    args=writer_setup(tmp_path,monkeypatch,True)
    source_before=sorted(p.relative_to(args.data_dir) for p in Path(args.data_dir).rglob('*'))
    if kind=='existing':Path(args.output_dir).mkdir()
    if kind=='inside_source':args.output_dir=str(Path(args.data_dir)/'output')
    if kind=='same_private':args.private_dir=args.output_dir
    if kind=='symlink':Path(args.output_dir).symlink_to(tmp_path/'missing')
    with pytest.raises(k.PreconditionError):c.compute(args)
    assert sorted(p.relative_to(args.data_dir) for p in Path(args.data_dir).rglob('*'))==source_before
    assert not Path(args.private_dir).exists() or args.private_dir==args.output_dir


def test_wrapper_contract_mode_and_output_default(tmp_path):
    path=tmp_path/'method.json';path.write_text('{"fixture":true}\n')
    result=subprocess.run(['bash',str(Path(__file__).resolve().parents[1]/'solution/solve.sh'),'--print-contract','--contract-path',str(path)],
        capture_output=True,text=True,check=False,timeout=20,
        env=os.environ|{'PYTHONDONTWRITEBYTECODE':'1','OUTPUT_DIR':str(tmp_path/'unused')})
    assert result.returncode==0 and json.loads(result.stdout)=={'fixture':True}
    assert not (tmp_path/'unused').exists()
