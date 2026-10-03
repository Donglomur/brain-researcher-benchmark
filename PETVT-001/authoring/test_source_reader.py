"""Manufactured immutable source decoding; no historical/original table use."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

PATH = Path(__file__).resolve().parents[1]/'solution'/'source_reader.py'
SPEC = importlib.util.spec_from_file_location('oracle_source_fixture', PATH)
r = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(r)


def encode(value): return (json.dumps(value, allow_nan=False)+'\n').encode()


@pytest.fixture
def manufactured(tmp_path, monkeypatch):
    root = tmp_path/'source'; root.mkdir(); docs = tmp_path/'docs'; docs.mkdir()
    pet = dict(Units='Bq/mL', ImageDecayCorrected=True, ImageDecayCorrectionTime=0,
        InjectionStart=0, ScanStart=0, RadionuclideHalfLife=6586.2, TimeZero='11:00:00',
        FrameTimesStart=[0, 1200, 2400], FrameDuration=[1200]*3)
    meta = dict(time={'Units':'s'}, plasma_radioactivity={'Units':'Bq/mL'})
    payload = {'tac': b'frame_start\tframe_end\tctx-lh-a\tctx-rh-b\n0\t1200\t1\t3\n1200\t2400\t2\t4\n2400\t3600\t3\t5\n',
        'blood': b'time\tplasma_radioactivity\tmetabolite_parent_fraction\twhole_blood_radioactivity\n3600\t2\t.5\t9\n0\t0\t0\t0\n0\t0\t0\t0\n',
        'pet_metadata': encode(pet), 'blood_metadata': encode(meta), 'provenance': b'fixture only\n'}
    rows = []
    for path, (role, sid) in r.expected_paths().items():
        raw = payload[role]; file = root/path; file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(raw)
        rows.append(dict(path=path,role=role,participant_id=sid,size_bytes=len(raw),sha256=r.digest(raw),
            git_blob_sha1=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()))
    manifest = dict(task_id='PETVT-001',schema_version='petvt-source-v2',status='complete_source_identity',
        participant_ids=list(r.SUBJECTS),files=rows,n_files=len(rows),total_bytes=sum(x['size_bytes'] for x in rows))
    method = {'source':dict(cortical_columns=['ctx-lh-a','ctx-rh-b'],frame_counts={s:3 for s in r.SUBJECTS},
        blood_row_counts={s:3 for s in r.SUBJECTS},distinct_knot_counts={s:2 for s in r.SUBJECTS})}
    for name, value, pin in [('source_manifest.json',manifest,'SOURCE_SHA'),('method_contract.json',method,'METHOD_SHA'),
                              ('output_schema.json',{'fixture':True},'SCHEMA_SHA')]:
        raw = encode(value); (docs/name).write_bytes(raw); monkeypatch.setattr(r,pin,r.digest(raw))
        if name=='source_manifest.json': (root/name).write_bytes(raw)
    return root, docs, manifest, method


def load(example, **kwargs):
    root, docs, _, _ = example
    return r.load(root,docs/'source_manifest.json',docs/'method_contract.json',docs/'output_schema.json',**kwargs)


def test_all_seven_with_coalesced_ledger_and_no_fits(manufactured):
    basis = load(manufactured)
    assert basis['status']=='complete' and len(basis['persons'])==7 and len(basis['source_files'])==31
    p = basis['persons'][r.SUBJECTS[0]]
    np.testing.assert_array_equal(p['cortical_values'],[[1,3],[2,4],[3,5]])
    np.testing.assert_array_equal(p['time_s'],[0,3600])
    assert p['knot_rows']==[1,0] and p['observed']['coalesced_knot_ledger'][0]['contributing_row_indices']==[1,2]
    assert p['observed']['input_time_support'] and not p['observed']['inserts_zero_anchor']
    assert 'vt' not in p


def test_pilot_cannot_be_complete_cohort(manufactured):
    basis = load(manufactured,pilot=True)
    assert basis['status']=='resource_pilot' and basis['subject_ids']==['sub-sf02']
    assert len(basis['source_observed']['persons'])==7 and len(basis['source_files'])==31


@pytest.mark.parametrize('mutation',['source','manifest','method','schema','extra','symlink','unfrozen'])
def test_authentication_failures(manufactured,mutation,monkeypatch):
    root,docs,manifest,_=manufactured
    if mutation=='source': (root/manifest['files'][0]['path']).write_bytes(b'x')
    elif mutation in ('manifest','method','schema'):
        name={'manifest':'source_manifest.json','method':'method_contract.json','schema':'output_schema.json'}[mutation]
        (docs/name).write_bytes(b'{}')
    elif mutation=='extra': (root/'extra').write_bytes(b'x')
    elif mutation=='symlink': (root/'extra').symlink_to('/absent')
    else: monkeypatch.setattr(r,'SCHEMA_SHA',None)
    with pytest.raises(ValueError): load(manufactured)


@pytest.mark.parametrize('text',['0\t1\t1\t0\n','0\t0\t0.0000000001\t0\n'])
def test_same_time_conflict_before_science(manufactured,text):
    root,docs,manifest,method=manufactured
    buffers={row['path']: (root/row['path']).read_bytes() for row in manifest['files']}
    row=next(x for x in manifest['files'] if x['role']=='blood' and x['participant_id']==r.SUBJECTS[0])
    buffers[row['path']]=buffers[row['path']].rsplit(b'0\t0\t0\t0\n',1)[0]+text.encode()
    with pytest.raises(ValueError,match='conflicting'):
        r.decode_person(r.SUBJECTS[0],manifest,method,buffers)


def test_atime_not_part_of_identity(manufactured):
    first=load(manufactured); second=load(manufactured)
    assert first['source_files']==second['source_files']


def test_reader_does_not_mutate_source(manufactured):
    root,_,manifest,_=manufactured
    before={x['path']:(root/x['path']).read_bytes() for x in manifest['files']}
    load(manufactured)
    assert before=={x['path']:(root/x['path']).read_bytes() for x in manifest['files']}
