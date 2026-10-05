"""Small synthetic mechanics only: never original-source scientific evidence."""
import copy
import csv
import json
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
sys.path.insert(0,str(ROOT/'builder'))
import proof_of_work as q
import independent_source as s

def synthetic_payload():
    contract=json.loads((ROOT/'environment/method_contract.json').read_text())
    tables={name:[] for name in q.KEYS}
    for subject in (1,2):
        events=[{'type':211,'latency':201.25},{'type':221,'latency':601.25},
                {'type':201,'latency':700.25}]
        ledger,segments,trials=s.source_support(subject,events,1000)
        signal=np.sin(np.arange(1000)/40)*(subject-1.5)*3
        curves,sub,_,_=s.measurements(subject,signal,trials)
        for name,rows in (('source_events.csv',ledger),('segments.csv',segments),('trial_measurements.csv',trials),('curves.csv',curves),('per_subject.csv',[sub])):
            tables[name].extend(rows)
    metadata=dict(status='ok',task_id=q.TASK,pipeline_id=q.PIPELINE,source_manifest_sha256='1'*64,
                  method_contract_sha256='2'*64,source_sha256={'fixture-only':'3'*64},method_contract=contract,
                  source_observed={'subjects':[{'subject':n,'n_samples':1000,'sfreq_hz':256.,'fixture_note':'mechanics only'} for n in (1,2)]},
                  software_versions={'fixture':'mechanics only'})
    return {'pipeline_id':q.PIPELINE,'provenance':'synthetic-mechanics-not-a-production-bank',
            'tables':tables,'results':s.summarize(tables),'metadata':metadata}

def write_payload(path,payload):
    path.mkdir(parents=True,exist_ok=True)
    for name,rows in payload['tables'].items():
        fields=payload['metadata']['method_contract']['outputs'][name]
        with (path/name).open('w',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (path/'n400.json').write_text(json.dumps(payload['results'],allow_nan=False))
    (path/'run_metadata.json').write_text(json.dumps(payload['metadata'],allow_nan=False))
    (path/'findings.md').write_text('Measured adaptation; no required phrase.')
    return path

@pytest.fixture
def fixture_output(tmp_path):
    reference=synthetic_payload()
    return write_payload(tmp_path/'output',reference),reference

@pytest.mark.parametrize('value',[1,'1','1.0','1e0',' 1.000 '])
def test_integer_equivalent_notation(value):
    assert q.integer(value)==1

@pytest.mark.parametrize('value',[True,False,'true','NaN','Infinity','1.5','1junk',''])
def test_integer_rejects_invalid(value):
    with pytest.raises(AssertionError):q.integer(value)

@pytest.mark.parametrize('value',[True,False,'nan','inf','-inf',None,{},[]])
def test_finite_parser(value):
    with pytest.raises(AssertionError):q.number(value)

@pytest.mark.parametrize('value,expected',[(True,True),('true',True),('FALSE',False),('1.0',True),('0e0',False)])
def test_boolean_notation(value,expected):
    assert q.boolean(value) is expected

@pytest.mark.parametrize('value',[2,-1,'yes','NaN',''])
def test_boolean_invalid(value):
    with pytest.raises(AssertionError):q.boolean(value)

def test_full_synthetic_receipt_acceptance(fixture_output):
    output,reference=fixture_output
    q.validate_output_directory(output,reference)

def test_both_effect_directions_zero_group_allowed(fixture_output):
    output,reference=fixture_output
    assert reference['results']['n_subjects_negative']==1
    assert reference['results']['n_subjects_positive']==1
    assert reference['results']['n400_difference_amplitude_uv']==0
    q.validate_output_directory(output,reference)

def test_legacy_bank_always_rejected(tmp_path):
    path=tmp_path/'old.npz'
    np.savez(path,ref_subjects=[1,2],ref_target=[-4,-6])
    with pytest.raises(AssertionError,match='Obsolete'):q.load_reference(path)

def test_mechanics_cannot_become_production_bank(tmp_path):
    path=tmp_path/'fixture.npz'
    np.savez(path,reference_json=json.dumps(synthetic_payload()))
    with pytest.raises(AssertionError,match='provenance'):q.load_reference(path)

@pytest.mark.parametrize('mutation',['missing','duplicate','alias','bool','fractional','nonfinite','wrong_condition'])
def test_trial_schema_negative(fixture_output,mutation):
    output,reference=fixture_output
    data=copy.deepcopy(reference)
    rows=data['tables']['trial_measurements.csv']
    if mutation=='missing':rows.pop()
    elif mutation=='duplicate':rows.append(dict(rows[0]))
    elif mutation=='alias':rows[0]['subject']='subject1'
    elif mutation=='bool':rows[0]['subject']=True
    elif mutation=='fractional':rows[0]['event_index']=.5
    elif mutation=='nonfinite':rows[0]['baseline_uv']='NaN'
    else:rows[0]['condition']='unrelated'
    write_payload(output,data)
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)

def test_metadata_flexible_stack_extras_and_subject_order(fixture_output):
    output,reference=fixture_output
    data=copy.deepcopy(reference)
    data['metadata']['software_versions']={'independent':'actual alternate'}
    data['metadata']['source_observed']['subjects'].reverse()
    data['metadata']['source_observed']['subjects'][0]['additional_note']='ungraded'
    data['metadata']['extra']='fine'
    data['results']['pooled_prime_target_explanatory_number']=12345
    write_payload(output,data)
    q.validate_output_directory(output,reference)

@pytest.mark.parametrize('where',['hash_extra','method_extra','observed_wrong','version_missing','version_empty','status','bool_count'])
def test_metadata_identity_negative(fixture_output,where):
    output,reference=fixture_output
    data=copy.deepcopy(reference)
    if where=='hash_extra':data['metadata']['source_sha256']['invented']='0'*64
    elif where=='method_extra':data['metadata']['method_contract']['secret_filter']='yes'
    elif where=='observed_wrong':data['metadata']['source_observed']['subjects'][0]['sfreq_hz']=250
    elif where=='version_missing':del data['metadata']['software_versions']
    elif where=='version_empty':data['metadata']['software_versions']={}
    elif where=='status':data['metadata']['status']='resource_pilot'
    else:data['results']['n_subjects']=True
    write_payload(output,data)
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)

def test_rounded_cancellation_propagates_tolerance():
    # Two million-uV fixture operands are not scientific inputs: parser/arithmetic only.
    q.algebra(0.,(1e6+.5)-(1e6-.5),[(1,1e6),(-1,1e6)],'cancellation')
    with pytest.raises(AssertionError):q.algebra(0.,10.,[(1,1e6),(-1,1e6)],'cancellation')

def test_source_sign_category_not_rounded_result(fixture_output):
    output,reference=fixture_output
    data=copy.deepcopy(reference)
    # Required sign counts remain source-derived, never re-threshold rounded amplitudes.
    data['results']['n_subjects_negative']=0
    write_payload(output,data)
    with pytest.raises(AssertionError):q.validate_output_directory(output,reference)

@pytest.mark.parametrize('text',['{"x":NaN}','{"x":Infinity}','{"x":1,"x":2}'])
def test_json_rejects_nonfinite_and_duplicates(tmp_path,text):
    path=tmp_path/'bad.json';path.write_text(text)
    with pytest.raises(AssertionError):q.read_json(path)

def test_python3_offline_entrypoint():
    text=(ROOT/'tests/test.sh').read_text()
    assert 'python3 -m pytest' in text
    assert not any(token in text for token in ('curl','pip install','apt-get','$HOME','uv '))

def test_public_template_discloses_complete_contract():
    public=json.loads((ROOT/'environment/method_contract.json').read_text())
    assert public['pipeline_id']==q.PIPELINE
    assert public['filter']['n_taps']==8449
    assert public['epochs']['measurement_offsets_inclusive']==[77,128]
    assert set(q.KEYS)<set(public['outputs'])
