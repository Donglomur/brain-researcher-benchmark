"""Full manufactured source -> independent grade; no original-data imports."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec)
    sys.modules[name]=obj;spec.loader.exec_module(obj);return obj


fixtures=module('proof_source_fixtures',ROOT/'authoring'/'test_source_reader.py')
manufactured=fixtures.manufactured
io=module('artifact_reader',ROOT/'tests'/'artifact_reader.py')
rm=module('reference_math',ROOT/'tests'/'reference_math.py')
ref=module('source_reference',ROOT/'tests'/'source_reference.py')
proof=module('proof_of_work',ROOT/'tests'/'proof_of_work.py')
k=module('kinetics',ROOT/'solution'/'kinetics.py')
writer=module('output_writer',ROOT/'solution'/'output_writer.py')


@pytest.fixture
def pair(manufactured,monkeypatch,tmp_path):
    source,docs,manifest,method=manufactured
    # Expand only manufactured tables to five frames and a resolved late fit.
    for row in manifest['files']:
        path=source/row['path'];raw=path.read_bytes()
        if row['role']=='tac':
            raw=('frame_start\tframe_end\tctx-lh-a\tctx-rh-b\n'+''.join(
                f'{i*1200}\t{(i+1)*1200}\t{v}\t{v+1}\n'for i,v in enumerate([1,3,2,1.5,1]))).encode()
        elif row['role']=='pet_metadata':
            value=json.loads(raw);value.update(FrameTimesStart=[i*1200 for i in range(5)],FrameDuration=[1200]*5)
            raw=fixtures.encode(value)
        elif row['role']=='blood':raw=raw.replace(b'3600\t',b'6000\t')
        path.write_bytes(raw);row.update(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            git_blob_sha1=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest())
    manifest['total_bytes']=sum(row['size_bytes']for row in manifest['files'])
    method['source']['frame_counts']={sid:5 for sid in fixtures.r.SUBJECTS}
    for name,value,pin in [('source_manifest.json',manifest,'SOURCE_SHA'),('method_contract.json',method,'METHOD_SHA')]:
        raw=fixtures.encode(value);(docs/name).write_bytes(raw);monkeypatch.setattr(fixtures.r,pin,hashlib.sha256(raw).hexdigest())
        if name=='source_manifest.json':(source/name).write_bytes(raw)
    for name in ('SOURCE_SHA','METHOD_SHA','SCHEMA_SHA'):monkeypatch.setattr(ref,name,getattr(fixtures.r,name))
    basis=ref.reconstruct(source,docs/'source_manifest.json',docs/'method_contract.json',docs/'output_schema.json')
    actual=writer.artifacts(fixtures.load(manufactured))
    out=tmp_path/'output';out.mkdir();writer.write(out,actual)
    return io.read_output(out),basis,out


def test_full_manufactured_writer_grade(pair):
    actual,basis,out=pair
    assert proof.validate(out,basis)==dict(status='ok',n_subjects=7,n_records=28)
    assert all(row['status']=='ok'for row in actual['rows'])


def test_coherent_axis_record_and_csv_permutations(pair):
    original,basis,_=pair;actual=copy.deepcopy(original);a=actual['arrays']
    for key in ('coefficients','coefficients_defined','model_rank','model_column_scales','model_singular_values','model_diagnostics_defined'):
        a[key]=a[key][::-1,::-1,::-1].copy()
    for key in ('subject_ids','assumption_ids','estimator_ids','cortical_column_ids'):a[key]=a[key][::-1].copy()
    for key in ('frame_subject_ids','frame_indices','frame_start_s','frame_end_s','tissue_concentration','tissue_integral','fit_mask'):
        a[key]=a[key][::-1].copy()
    for key in ('plasma_integral','plasma_integral_defined'):a[key]=a[key][::-1,::-1].copy()
    for key in ('knot_subject_ids','knot_source_rows','knot_time_s'):a[key]=a[key][::-1].copy()
    a['parent_input']=a['parent_input'][::-1,::-1].copy()
    actual['rows'].reverse();actual['metadata']['source_files'].reverse();actual['metadata']['source_observed']['persons'].reverse()
    for key in ('groups','paired_changes','paired_summaries'):actual['summary'][key].reverse()
    assert proof.verify(actual,basis)['status']=='ok'


@pytest.mark.parametrize('mutation',['source_pin','source_value','mask','coefficient','coefficient_nan','rank','vt','summary',
    'missing_person','duplicate_frame','knot_key','row_count','ledger','bool_count','status'])
def test_binding_and_numerical_mutations_reject(pair,mutation):
    baseline,basis,_=pair;actual=copy.deepcopy(baseline)
    if mutation=='source_pin':actual['metadata']['source_manifest_sha256']='0'*64
    elif mutation=='source_value':actual['arrays']['tissue_concentration'][0]+=1
    elif mutation=='mask':actual['arrays']['plasma_integral_defined'][0,0]=False
    elif mutation=='coefficient':actual['arrays']['coefficients'][0,0,0,0]+=1
    elif mutation=='coefficient_nan':actual['arrays']['coefficients'][0,0,0,0]=np.nan
    elif mutation=='rank':actual['arrays']['model_rank'][0,0,0]=1
    elif mutation=='vt':actual['rows'][0]['vt']=str(float(actual['rows'][0]['vt'])+1)
    elif mutation=='summary':actual['summary']['groups'][0]['mean']+=1
    elif mutation=='missing_person':actual['rows'].pop()
    elif mutation=='duplicate_frame':actual['arrays']['frame_indices'][1]=actual['arrays']['frame_indices'][0]
    elif mutation=='knot_key':actual['arrays']['knot_source_rows'][0]=-1
    elif mutation=='row_count':actual['rows'][0]['n_fit_rows']='3.0'
    elif mutation=='ledger':actual['metadata']['source_observed']['persons'][0]['coalesced_knot_ledger'][0]['multiplicity']=1
    elif mutation=='bool_count':actual['summary']['groups'][0]['n_defined']=True
    elif mutation=='status':actual['rows'][0]['status']='rank_deficient'
    with pytest.raises((ValueError,KeyError)):proof.verify(actual,basis)


def test_own_coefficients_not_hidden_source_endpoint_target(pair):
    baseline,basis,_=pair;actual=copy.deepcopy(baseline)
    # Deliberately widen only the manufactured source-copy change within the
    # public coefficient band, then reconstruct every dependent own receipt.
    old=actual['arrays']['coefficients'][0,0,0].copy();new=old.copy();new[0]+=1e-8
    actual['arrays']['coefficients'][0,0,0]=new
    s=basis['subject_ids'][0];m=basis['persons'][s]['models']['already_image_reference','logan']
    row=next(r for r in actual['rows']if(r['subject_id'],r['assumption_id'],r['estimator_id'])==(s,'already_image_reference','logan'))
    row['coefficient_0']=str(new[0]);row['vt']=str(new[0]);row['nonpositive_vt']=str(new[0]<=0).lower()
    row['residual_rss']=str(rm.rss(m['design'],m['response'],new)[0])
    ownmodels={sid:{}for sid in basis['subject_ids']}
    for r in actual['rows']:ownmodels[r['subject_id']][r['assumption_id'],r['estimator_id']]={'vt':None if r['vt']==''else float(r['vt'])}
    actual['summary']=writer.summaries(basis['subject_ids'],ownmodels)
    assert proof.verify(actual,basis)['status']=='ok'


def test_late_failure_marker_rejects(pair):
    _,basis,out=pair;(out/'failure_report.json').write_text('{}')
    with pytest.raises(ValueError):proof.validate(out,basis)


@pytest.mark.parametrize('inside',[True,False])
def test_csv_coefficient_receipt_uses_its_public_tolerance(pair,inside):
    baseline,basis,_=pair;actual=copy.deepcopy(baseline)
    value=float(actual['rows'][0]['coefficient_0']);bound=1e-8+1e-6*abs(value)
    actual['rows'][0]['coefficient_0']=str(value+(bound*.5 if inside else bound+5e-7))
    if inside:assert proof.verify(actual,basis)['status']=='ok'
    else:
        with pytest.raises(ValueError):proof.verify(actual,basis)
