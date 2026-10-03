"""Manufactured metadata only: no source files, kinetic fitting or model calls."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    path=ROOT/'tests'/(name+'.py')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


io=load('artifact_reader')
load('reference_math')
proof=load('proof_of_work')


@pytest.fixture
def records():
    people=[]
    for i in range(7):
        people.append(dict(subject_id=f'fabricated-{i}',n_blood_rows=3,
            blood_row_ledger=[
                dict(source_row=0,time_s=0.,paired_eligible=True,reasons=[]),
                dict(source_row=1,time_s=1.,paired_eligible=False,reasons=['missing_plasma_radioactivity']),
                dict(source_row=2,time_s=2.,paired_eligible=False,reasons=[
                    'missing_plasma_radioactivity','missing_metabolite_parent_fraction'])],
            source_clock=dict(time_zero='12:34:56',scan_start_s=0,injection_start_s=0,
                image_reference_s=0,half_life_s=6586.2,concentration_units='Bq/mL'),
            coalesced_knot_ledger=[dict(time_s=0.,representative_source_row=0,
                contributing_row_indices=[0],multiplicity=1,exact_pair_equal=True)],
            missing_selected_entries=[dict(source_row=1,column='plasma_radioactivity',token='n/a')],
            invalid_domain_entries=[]))
    reference=dict(pins=dict(source_manifest_sha256='a'*64,method_contract_sha256='b'*64,
        output_schema_sha256='c'*64),source_files=[dict(path='fabricated.tsv',role='blood',
        participant_id='fabricated-0',size_bytes=123,sha256='d'*64,git_blob_sha1='e'*40)],
        source_observed={'persons':people})
    metadata=dict(schema_version='petvt-metadata-v2',task_id='PETVT-001',status='complete',
        **reference['pins'],source_files=copy.deepcopy(reference['source_files']),
        source_observed=copy.deepcopy(reference['source_observed']),warnings=[],
        software={'python':'fixture','numpy':'fixture','scipy':'fixture'})
    return metadata,reference


def aliases(metadata,*,both=False):
    for person in metadata['source_observed']['persons']:
        for row in person['blood_row_ledger']:
            row['eligible']=row['paired_eligible']
            row['missing_columns']=[r.removeprefix('missing_')for r in row['reasons']][::-1]
            row['status']='paired'if row['eligible']else'missing_pair'
            row['invalid_domain_entries']=[]
            if not both:
                del row['paired_eligible'];del row['reasons']
        clock=person['source_clock'];clock.update(pet_units='Bq/mL',plasma_units='Bq/mL',blood_time_units='s')
        if not both:del clock['concentration_units']


@pytest.mark.parametrize('encoding',['canonical','aliases','both','canonical_reasons_reverse','partial_aliases','descriptive_status'])
def test_equivalent_complete_metadata(records,encoding):
    actual,reference=records
    if encoding in ('aliases','both'):aliases(actual,both=encoding=='both')
    elif encoding=='canonical_reasons_reverse':
        actual['source_observed']['persons'][0]['blood_row_ledger'][2]['reasons'].reverse()
    elif encoding=='partial_aliases':
        person=actual['source_observed']['persons'][0]
        person['blood_row_ledger'][0]['eligible']=True
        person['source_clock']['pet_units']='Bq/mL'
    elif encoding=='descriptive_status':
        actual['source_observed']['persons'][0]['blood_row_ledger'][0]['status']='source pair retained'
    original=copy.deepcopy(actual)
    proof.metadata(actual,reference)
    assert actual==original  # never rewrite submitted artifacts or caller data


@pytest.mark.parametrize('change',[
    'eligibility_conflict','eligibility_integer','eligibility_missing','wrong_eligibility',
    'missing_fields_conflict','missing_fields_missing','missing_fields_duplicate','unknown_missing_field',
    'unknown_reason','eligibility_reason_conflict','wrong_missing_field','status_conflict',
    'status_bool','invalid_domain','missing_row','duplicate_row','wrong_row_id','row_id_float','row_id_bool',
    'wrong_time','nan_time','missing_person','duplicate_person','source_hash','source_count','method_hash',
    'schema_hash','units_conflict','units_wrong','units_incomplete','units_missing','time_units_wrong',
    'clock_changed','clock_nan','clock_bool','missing_token_changed','coalesced_multiplicity'])
def test_incorrect_or_contradictory_metadata_rejected(records,change):
    actual,reference=records;aliases(actual,both=True)
    person=actual['source_observed']['persons'][0];row=person['blood_row_ledger'][0]
    clock=person['source_clock']
    if change=='eligibility_conflict':row['eligible']=False
    elif change=='eligibility_integer':row['eligible']=1
    elif change=='eligibility_missing':del row['paired_eligible'];del row['eligible']
    elif change=='wrong_eligibility':
        row.update(paired_eligible=False,eligible=False,reasons=['missing_plasma_radioactivity'],
            missing_columns=['plasma_radioactivity'],status='missing_pair')
    elif change=='missing_fields_conflict':row['missing_columns']=['plasma_radioactivity']
    elif change=='missing_fields_missing':del row['reasons'];del row['missing_columns']
    elif change=='missing_fields_duplicate':row['missing_columns']=['plasma_radioactivity']*2
    elif change=='unknown_missing_field':row['missing_columns']=['whole_blood_radioactivity']
    elif change=='unknown_reason':row['reasons']=['arbitrary_exclusion']
    elif change=='eligibility_reason_conflict':row.update(reasons=['missing_plasma_radioactivity'],missing_columns=['plasma_radioactivity'])
    elif change=='wrong_missing_field':
        person['blood_row_ledger'][1].update(reasons=['missing_metabolite_parent_fraction'],missing_columns=['metabolite_parent_fraction'])
    elif change=='status_conflict':row['status']='missing_pair'
    elif change=='status_bool':row['status']=True
    elif change=='invalid_domain':row['invalid_domain_entries']=['negative_plasma']
    elif change=='missing_row':person['blood_row_ledger'].pop()
    elif change=='duplicate_row':person['blood_row_ledger'][1]=copy.deepcopy(row)
    elif change=='wrong_row_id':row['source_row']=8
    elif change=='row_id_float':row['source_row']=0.
    elif change=='row_id_bool':row['source_row']=False
    elif change=='wrong_time':row['time_s']=60.
    elif change=='nan_time':row['time_s']=float('nan')
    elif change=='missing_person':actual['source_observed']['persons'].pop()
    elif change=='duplicate_person':actual['source_observed']['persons'][1]=copy.deepcopy(person)
    elif change=='source_hash':actual['source_files'][0]['sha256']='0'*64
    elif change=='source_count':actual['source_files'][0]['size_bytes']=True
    elif change=='method_hash':actual['method_contract_sha256']='0'*64
    elif change=='schema_hash':actual['output_schema_sha256']='0'*64
    elif change=='units_conflict':clock['pet_units']='kBq/mL'
    elif change=='units_wrong':clock.update(concentration_units='kBq/mL',pet_units='kBq/mL',plasma_units='kBq/mL')
    elif change=='units_incomplete':del clock['concentration_units'];del clock['plasma_units']
    elif change=='units_missing':
        for field in ('concentration_units','pet_units','plasma_units'):del clock[field]
    elif change=='time_units_wrong':clock['blood_time_units']='min'
    elif change=='clock_changed':clock['half_life_s']=6586.26
    elif change=='clock_nan':clock['scan_start_s']=float('nan')
    elif change=='clock_bool':clock['scan_start_s']=False
    elif change=='missing_token_changed':person['missing_selected_entries'][0]['token']='NaN'
    elif change=='coalesced_multiplicity':person['coalesced_knot_ledger'][0]['multiplicity']=2
    with pytest.raises((ValueError,KeyError)):proof.metadata(actual,reference)


@pytest.mark.parametrize('token',['NaN','Infinity','-Infinity','1e999'])
def test_nonfinite_extra_json_not_admitted(token):
    with pytest.raises(ValueError):io.json_bytes(('{"optional_extra":'+token+'}').encode())


def test_private_code_and_shell_pin_chain():
    boot=load('grader_bootstrap')
    for name,pin in boot.CODE_PINS.items():
        assert hashlib.sha256((ROOT/'tests'/(name+'.py')).read_bytes()).hexdigest()==pin
    for name,pin in boot.DOC_PINS.items():
        assert hashlib.sha256((ROOT/'tests'/name).read_bytes()).hexdigest()==pin
        assert (ROOT/'tests'/name).read_bytes()==(ROOT/'environment'/name).read_bytes()
    bootstrap_sha=hashlib.sha256((ROOT/'tests'/'grader_bootstrap.py').read_bytes()).hexdigest()
    outputs_sha=hashlib.sha256((ROOT/'tests'/'test_outputs.py').read_bytes()).hexdigest()
    assert bootstrap_sha in (ROOT/'tests'/'test_outputs.py').read_text()
    shell=(ROOT/'tests'/'test.sh').read_text()
    assert bootstrap_sha in shell and outputs_sha in shell
    assert bootstrap_sha in (ROOT/'authoring'/'test_actual_controls.py').read_text()
