"""Manufactured serialization/failure checks; original source reconstruction blocked."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import sys
import types

import numpy as np
import pytest


@pytest.fixture
def compute(monkeypatch):
    blocked=types.ModuleType('oracle_source')
    blocked.reconstruct=lambda *a,**k:pytest.fail('source access in serializer fixture')
    monkeypatch.setitem(sys.modules,'oracle_source',blocked)
    spec=importlib.util.spec_from_file_location('manufactured_compute',Path(__file__).resolve().parents[1]/'solution'/'compute.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def reference(module):
    offsets=np.arange(-51,103)
    profile=np.zeros(154);profile[51+20]=-2;profile[51+21]=-4;profile[51+22]=-2
    profile[51+28:51+39]=-1
    waves=np.zeros((37,2,154));waves[:,0,:]=profile
    trials=[dict(subject_id=s,source_event_index=c,condition=name,event_sample=100,
        epoch_first_sample=49,epoch_last_sample=202,epoch_status='ok',accepted=True,
        rejection_reason='accepted') for s in module.SUBJECTS for c,name in enumerate(('face','car'))]
    return dict(status='complete',subjects=list(module.SUBJECTS),condition_labels=['face','car'],
        sample_offsets=offsets,condition_defined=np.ones((37,2),bool),evoked_po8_uv=waves,
        rejection_channel_labels=['C'+str(i) for i in range(30)],annotations=[],trials=trials,
        epoch_keys=[(r['subject_id'],r['source_event_index']) for r in trials],
        epoch_peak_to_peak_uv=np.ones((74,30)),epoch_po8_baseline_uv=np.zeros(74),
        pins=dict(source_manifest_sha256='a'*64,method_contract_sha256='b'*64,output_schema_sha256='c'*64),
        source_files=[],source_observed=dict(persons=[]),analysis_observed=dict(persons=[]))


def test_compose_signed_amplitude_point_ci_and_own_waveform(compute):
    ref=reference(compute);before=copy.deepcopy(ref)
    bundle=compute.compose(ref)
    assert bundle['result']['amp_po8_uv']==-1
    assert bundle['result']['amplitude_summary']['interval_kind']=='constant_point'
    assert bundle['result']['amp_po8_ci95']==[-1,-1]
    assert all(row['peak_sample_offset']==21 and row['crossing_sample_offset']==20 for row in bundle['persons'])
    assert bundle['metadata']['schema_version']=='n170-output-v1'
    assert np.array_equal(ref['evoked_po8_uv'],before['evoked_po8_uv'])


def test_positive_zero_and_missing_onset_preserve_amplitude(compute):
    ref=reference(compute);ref['evoked_po8_uv']*=-1
    positive=compute.compose(ref)
    assert positive['result']['amp_po8_uv']==1
    assert positive['result']['onset_latency_ms'] is None
    ref['evoked_po8_uv'][:]=0
    zero=compute.compose(ref)
    assert zero['result']['amp_po8_uv']==0
    assert all(r['onset_status']=='numerical_zero_difference' for r in zero['persons'])
    assert zero['result']['onset_summary']['n_missing']==37


@pytest.mark.parametrize('missing_condition',[0,1])
def test_one_missing_person_nulls_complete_endpoint_not_available_case(compute,missing_condition):
    ref=reference(compute);ref['condition_defined'][0,missing_condition]=False
    ref['evoked_po8_uv'][0,missing_condition]=0
    row=ref['trials'][missing_condition];row.update(accepted=False,rejection_reason='peak_to_peak')
    result=compute.compose(ref)['result']
    assert result['amp_po8_uv'] is result['amp_po8_ci95'] is None
    assert result['amplitude_summary']['n_defined']==36
    assert result['amplitude_summary']['missing_subject_ids']==['2']


@pytest.mark.parametrize('kind',['pilot','wrong_subjects','wrong_conditions','grid','nonfinite','false_mask','bad_zero'])
def test_malformed_source_adapter_not_silently_serialized(compute,kind):
    ref=reference(compute)
    if kind=='pilot':ref['status']='resource_pilot'
    elif kind=='wrong_subjects':ref['subjects']=ref['subjects'][::-1]
    elif kind=='wrong_conditions':ref['condition_labels']=['car','face']
    elif kind=='grid':ref['sample_offsets']=ref['sample_offsets']+1
    elif kind=='nonfinite':ref['evoked_po8_uv'][0,0,0]=np.nan
    elif kind=='false_mask':ref['condition_defined'][0,0]=False
    else:
        ref['condition_defined'][0,0]=False
        ref['trials'][0]['accepted']=False
    with pytest.raises(ValueError):compute.compose(ref)


def test_bundle_files_are_exclusive_and_json_finite(compute,tmp_path):
    bundle=compute.compose(reference(compute));out=compute.safe_output(str(tmp_path/'out'))
    compute.write_bundle(out,bundle)
    assert len(list(out.iterdir()))==7
    assert json.loads((out/'n170.json').read_text())['n_subjects']==37
    with (out/'per_subject.csv').open() as stream:rows=list(csv.DictReader(stream))
    assert len(rows)==37 and rows[0]['subject_id']=='2'
    with np.load(out/'erp_evidence.npz',allow_pickle=False) as arrays:
        assert arrays['evoked_po8_uv'].shape==(37,2,154)
    with pytest.raises(FileExistsError):compute.write_bundle(out,bundle)


def test_main_existing_output_preserves_files_and_marks_stale_failure(compute,tmp_path):
    out=tmp_path/'out';out.mkdir();(out/'prior').write_text('keep')
    assert compute.main(['--output-dir',str(out)])==1
    assert (out/'prior').read_text()=='keep'
    assert json.loads((out/'failure_report.json').read_text())['reason']=='fresh_empty_output_required'
    marker=(out/'failure_report.json').read_bytes()
    assert compute.main(['--output-dir',str(out)])==1
    assert (out/'failure_report.json').read_bytes()==marker


def test_main_source_error_records_failure(compute,tmp_path,monkeypatch):
    def refuse(*args,**kwargs):raise ValueError('manufactured source precondition')
    monkeypatch.setattr(compute.oracle_source,'reconstruct',refuse)
    out=tmp_path/'out'
    assert compute.main(['--output-dir',str(out)])==1
    assert json.loads((out/'failure_report.json').read_text())['reason']=='manufactured source precondition'


def test_symlink_output_is_never_written(compute,tmp_path):
    target=tmp_path/'target';target.mkdir();link=tmp_path/'link';link.symlink_to(target)
    assert compute.main(['--output-dir',str(link)])==1
    assert not list(target.iterdir())


def test_structured_warnings_are_deterministic_lossless_strings(compute,tmp_path):
    ref=reference(compute)
    warning=dict(subject_id='2',stage='filter',category='RuntimeWarning',
                 message='short segment: µV\nretained',details={'n_samples':np.int64(3)})
    ref['warnings']=[warning,'already textual']
    bundle=compute.compose(ref)
    strings=bundle['metadata']['warnings']
    assert all(isinstance(value,str) for value in strings)
    assert json.loads(strings[0])==compute.plain(warning)
    assert strings[1]=='already textual'
    ref['warnings']=[dict(reversed(list(warning.items()))),'already textual']
    assert compute.compose(ref)['metadata']['warnings']==strings
    compute.write_json(tmp_path/'metadata.json',bundle['metadata'])
    assert json.loads((tmp_path/'metadata.json').read_text())['warnings']==strings


def test_nonfinite_structured_warning_is_not_serialized_as_json_nan(compute):
    with pytest.raises(ValueError):compute.warning_strings([{'detail':float('nan')}])


@pytest.mark.parametrize('kind',['source','source_child','source_parent','code','code_child','code_parent',
                                  'manifest_parent','method_parent','schema_parent','manifest_file'])
def test_protected_output_is_rejected_without_marker_or_creation(compute,tmp_path,monkeypatch,kind):
    source=tmp_path/'data'/'source';source.mkdir(parents=True)
    (source/'keep').write_text('original placeholder')
    code=tmp_path/'private'/'solution';code.mkdir(parents=True)
    (code/'compute.py').write_text('code placeholder')
    monkeypatch.setattr(compute,'__file__',str(code/'compute.py'))
    docs={name:tmp_path/(name+'_docs')/(name+'.json') for name in ('manifest','method','schema')}
    for path in docs.values():path.parent.mkdir();path.write_text('{}')
    options={'source':source,'source_child':source/'new','source_parent':source.parent,
             'code':code,'code_child':code/'new','code_parent':code.parent,
             'manifest_parent':docs['manifest'].parent,'method_parent':docs['method'].parent,
             'schema_parent':docs['schema'].parent,'manifest_file':docs['manifest']}
    before={str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    paths_before={str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*')}
    args=['--data-dir',str(source),'--output-dir',str(options[kind])]
    for name,path in docs.items():args.extend(['--'+name,str(path)])
    assert compute.main(args)==1
    assert before=={str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert paths_before=={str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*')}


def test_sibling_output_beside_public_documents_remains_allowed(compute,tmp_path,monkeypatch):
    source=tmp_path/'data';source.mkdir()
    docs=[tmp_path/(name+'.json') for name in ('manifest','method','schema')]
    for path in docs:path.write_text('{}')
    def refuse(*args,**kwargs):raise ValueError('manufactured source precondition')
    monkeypatch.setattr(compute.oracle_source,'reconstruct',refuse)
    out=tmp_path/'output'
    args=['--data-dir',str(source),'--output-dir',str(out)]
    for name,path in zip(('manifest','method','schema'),docs):args.extend(['--'+name,str(path)])
    assert compute.main(args)==1
    assert json.loads((out/'failure_report.json').read_text())['reason']=='manufactured source precondition'
    assert all(path.read_text()=='{}' for path in docs)
