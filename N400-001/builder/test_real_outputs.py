"""Genuine-output controls. Never refits or modifies original saved evidence."""
import csv
import json
import os
from pathlib import Path
import shutil
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import proof_of_work as q

@pytest.fixture
def original():
    value=os.environ.get('REPAIR_ORACLE_OUTPUT')
    if not value:pytest.skip('Requires parent-produced genuine source oracle outputs')
    return Path(value)

@pytest.fixture
def output(original,tmp_path):
    target=tmp_path/'output'
    shutil.copytree(original,target)
    return target

def table(output,name):
    with (output/name).open(newline='') as handle:
        reader=csv.DictReader(handle)
        return reader.fieldnames,list(reader)

def write_table(output,name,fields,rows):
    with (output/name).open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader();writer.writerows(rows)

def json_edit(output,name,mutate):
    path=output/name
    value=json.loads(path.read_text());mutate(value)
    path.write_text(json.dumps(value,allow_nan=False))

def test_genuine_original(original):
    q.validate_output_directory(original)

def test_genuine_independent_complete():
    value=os.environ.get('REPAIR_INDEPENDENT_OUTPUT')
    if not value:pytest.skip('Requires parent-run independent SET/FDT/NumPy-FFT outputs')
    q.validate_output_directory(value)

def test_row_column_order_and_extra_csv_fields(output):
    for name in q.KEYS:
        fields,rows=table(output,name)
        for row in rows:row['ungraded_note']='harmless'
        write_table(output,name,['ungraded_note']+fields[::-1],rows[::-1])
    q.validate_output_directory(output)

def test_integer_scientific_notation_exact_roundtrip(output):
    for name in q.KEYS:
        fields,rows=table(output,name)
        for row in rows:
            for field in q.INTEGER_FIELDS & set(row):
                if row[field]:
                    original=q.integer(row[field]);row[field]=format(original,'.17e')
                    assert q.integer(row[field])==original
        write_table(output,name,fields,rows)
    q.validate_output_directory(output)

def test_reasonable_amplitude_rounding(output):
    for name in q.KEYS:
        fields,rows=table(output,name)
        for row in rows:
            for field in q.AMPLITUDE_FIELDS & set(row):
                if row[field]:row[field]=format(float(row[field]),'.6f')
        write_table(output,name,fields,rows)
    json_edit(output,'n400.json',lambda result:result.update({k:round(v,6) for k,v in result.items() if k.endswith('amplitude_uv')}))
    q.validate_output_directory(output)

def test_honest_alternate_versions_and_free_prose(output):
    def mutate(meta):
        meta['software_versions']={'independent implementation':'equivalent numerical library'}
        meta['source_observed']['subjects'].reverse()
        meta['source_observed']['subjects'][0]['additional_observation']='ungraded'
        meta['source_observed']['additional_context']='ungraded'
        meta['additional_context']='ungraded'
    json_edit(output,'run_metadata.json',mutate)
    (output/'findings.md').write_text('A signed measured contrast for the requested sample.')
    q.validate_output_directory(output)

def test_unrequested_optional_pooled_json_not_scanned(output):
    json_edit(output,'n400.json',lambda result:result.update(pooled_prime_target_unscored={'value':999999,'note':'not a required branch'}))
    q.validate_output_directory(output)

@pytest.mark.parametrize('name',list(q.KEYS))
@pytest.mark.parametrize('mutation',['drop','duplicate','wrong_subject'])
def test_complete_membership_negative(output,name,mutation):
    fields,rows=table(output,name)
    if mutation=='drop':rows.pop()
    elif mutation=='duplicate':rows.append(dict(rows[0]))
    else:rows[0]['subject']='13'
    write_table(output,name,fields,rows)
    with pytest.raises(AssertionError):q.validate_output_directory(output)

@pytest.mark.parametrize('name',['source_events.csv','segments.csv','trial_measurements.csv','curves.csv','per_subject.csv','n400.json','run_metadata.json','findings.md'])
def test_missing_required_artifact(output,name):
    (output/name).unlink()
    with pytest.raises((AssertionError,FileNotFoundError)):q.validate_output_directory(output)

@pytest.mark.parametrize('mutation',['trial_compensating','subject_compensating','sign_flip','curve_unit_scale','curve_shift','wrong_event_sample','wrong_event_type','wrong_duration','wrong_support','wrong_segment','missing_curve_time','wrong_measurement_endpoint','bool_subject','nan_amplitude'])
def test_source_bound_coherent_and_schema_negatives(output,mutation):
    if mutation in ('trial_compensating','wrong_measurement_endpoint'):
        name='trial_measurements.csv';fields,rows=table(output,name)
        selected=[row for row in rows if row['status']=='retained']
        if mutation=='trial_compensating':
            pair=[row for row in selected if row['subject']==selected[0]['subject'] and row['condition']==selected[0]['condition']][:2]
            for row,delta in zip(pair,(10.,-10.)):
                row['window_raw_mean_uv']=str(float(row['window_raw_mean_uv'])+delta)
                row['window_baseline_corrected_uv']=str(float(row['window_baseline_corrected_uv'])+delta)
        else:selected[0]['window_baseline_corrected_uv']=str(float(selected[0]['window_baseline_corrected_uv'])+1)
    elif mutation in ('subject_compensating','sign_flip'):
        name='per_subject.csv';fields,rows=table(output,name)
        if mutation=='subject_compensating':
            for row,delta in zip(rows[:2],(100.,-100.)):
                row['unrelated_uv']=str(float(row['unrelated_uv'])+delta)
                row['n400_uv']=str(float(row['n400_uv'])+delta)
        else:
            for row in rows:
                row['related_uv'],row['unrelated_uv']=row['unrelated_uv'],row['related_uv']
                row['n400_uv']=str(-float(row['n400_uv']))
            json_edit(output,'n400.json',lambda result:result.update(n400_difference_amplitude_uv=-result['n400_difference_amplitude_uv']))
    elif mutation in ('curve_unit_scale','curve_shift','missing_curve_time','nan_amplitude'):
        name='curves.csv';fields,rows=table(output,name)
        if mutation=='curve_unit_scale':
            for row in rows:
                for key in ('related_uv','unrelated_uv','difference_uv'):row[key]=str(float(row[key])*1e-6)
        elif mutation=='curve_shift':
            rows[0]['related_uv']=str(float(rows[0]['related_uv'])+5)
            rows[0]['difference_uv']=str(float(rows[0]['unrelated_uv'])-float(rows[0]['related_uv']))
        elif mutation=='missing_curve_time':rows.pop(100)
        else:rows[0]['related_uv']='NaN'
    elif mutation=='wrong_segment':
        name='segments.csv';fields,rows=table(output,name);rows[0]['pad_samples']='0'
    else:
        name='source_events.csv';fields,rows=table(output,name)
        row=next(row for row in rows if row['role']=='target')
        if mutation=='wrong_event_sample':row['event_sample']=str(int(row['event_sample'])+1)
        elif mutation=='wrong_event_type':row['event_type']='111'
        elif mutation=='wrong_duration':row['duration_samples']='0';row['duration_status']='finite'
        elif mutation=='wrong_support':row['retained']='0';row['drop_reason']='out_of_data'
        else:row['subject']='true'
    write_table(output,name,fields,rows)
    with pytest.raises(AssertionError):q.validate_output_directory(output)

@pytest.mark.parametrize('mutation',['hash','hash_extra','method','manifest','contract_hash','source_count','channel_index','sampling','metadata_missing','pilot','versions_empty'])
def test_provenance_negatives(output,mutation):
    def mutate(meta):
        if mutation=='hash':meta['source_sha256'][next(iter(meta['source_sha256']))]='0'*64
        elif mutation=='hash_extra':meta['source_sha256']['invented.fdt']='0'*64
        elif mutation=='method':meta['method_contract']['filter']['n_taps']=113
        elif mutation=='manifest':meta['source_manifest_sha256']='0'*64
        elif mutation=='contract_hash':meta['method_contract_sha256']='0'*64
        elif mutation=='source_count':meta['source_observed']['subjects'][0]['n_source_events']+=1
        elif mutation=='channel_index':meta['source_observed']['subjects'][0]['readout_channel_indices']['CPz']=0
        elif mutation=='sampling':meta['source_observed']['subjects'][0]['sfreq_hz']=250
        elif mutation=='metadata_missing':del meta['source_observed']
        elif mutation=='pilot':meta['status']='resource_pilot'
        else:meta['software_versions']={}
    json_edit(output,'run_metadata.json',mutate)
    with pytest.raises(AssertionError):q.validate_output_directory(output)

@pytest.mark.parametrize('field',['n_subjects','n_target_events','n_retained_target_epochs','n_subjects_negative','n_subjects_zero','n_subjects_positive'])
def test_fabricated_counts(output,field):
    json_edit(output,'n400.json',lambda result:result.update({field:result[field]+1}))
    with pytest.raises(AssertionError):q.validate_output_directory(output)

def test_empty_findings(output):
    (output/'findings.md').write_text('   \n')
    with pytest.raises(AssertionError):q.validate_output_directory(output)

def test_actual_public_template_identity(original):
    meta=json.loads((original/'run_metadata.json').read_text())
    assert meta['method_contract']==json.loads((ROOT/'environment/method_contract.json').read_text())
    assert meta['method_contract_sha256']==q.sha256(ROOT/'environment/method_contract.json')
