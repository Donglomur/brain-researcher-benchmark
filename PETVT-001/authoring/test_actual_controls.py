"""Opt-in authoring QA only; never included by the production runner."""
import copy
import hashlib
import os
from pathlib import Path
import types

import numpy as np
import pytest

pytestmark=pytest.mark.skipif(os.environ.get('REPAIR_RUN_ACTUAL_CONTROLS')!='1',reason='authoring originals not authorized')


@pytest.fixture(scope='module')
def baseline():
    path=Path('/tests/grader_bootstrap.py');raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='557e431e4ea5774b76ac632acdcf57d652fc3381ba08b9b6b31468b2cd589bdd'
    boot=types.ModuleType('actual_boot');boot.__file__=str(path);exec(compile(raw,str(path),'exec'),boot.__dict__)
    c=boot.load_private();m=c['modules'];d=c['documents']
    reference=m['source_reference'].reconstruct('/app/data/petvt',d['source_manifest.json'],d['method_contract.json'],d['output_schema.json'])
    actual=m['artifact_reader'].read_output('/app/output')
    assert m['proof_of_work'].verify(actual,reference)['status']=='ok'
    return m,reference,actual


def test_genuine_baseline(baseline,record_property):
    m,ref,actual=baseline
    assert m['proof_of_work'].verify(actual,ref)['status']=='ok'
    record_property('control_outcome','accepted_genuine')


@pytest.mark.parametrize('variant',['records','axes','extras'])
def test_equivalent_representation(baseline,variant,record_property):
    m,ref,original=baseline;actual=copy.deepcopy(original);a=actual['arrays']
    if variant=='records':
        actual['rows'].reverse()
        for key in ('groups','paired_changes','paired_summaries'):actual['summary'][key].reverse()
        actual['metadata']['source_files'].reverse();actual['metadata']['source_observed']['persons'].reverse()
    elif variant=='axes':
        a['subject_ids']=a['subject_ids'][::-1]
        for key in ('coefficients','coefficients_defined','model_rank','model_column_scales','model_singular_values','model_diagnostics_defined'):a[key]=a[key][::-1]
        frames=len(a['frame_indices']);knots=len(a['knot_time_s'])
        for key in ('frame_subject_ids','frame_indices','frame_start_s','frame_end_s','tissue_concentration','tissue_integral','plasma_integral','plasma_integral_defined','fit_mask'):a[key]=a[key][np.arange(frames)[::-1]]
        for key in ('knot_subject_ids','knot_source_rows','knot_time_s','parent_input'):a[key]=a[key][np.arange(knots)[::-1]]
    else:
        actual['summary']['extra_note']='non-authoritative';actual['metadata']['extra_note']='descriptive only'
        actual['findings']+='\nAdditional descriptive report.\n'
    assert m['proof_of_work'].verify(actual,ref)['status']=='ok'
    record_property('control_outcome','accepted_genuine')


@pytest.mark.parametrize('mutation',['source_hash','tissue','input_integral','coefficient','coefficient_receipt','vt',
    'summary','missing_subject','duplicate_frame','ledger','rank','nan','reactivation'])
def test_binding_and_numeric_controls(baseline,mutation,record_property):
    m,ref,original=baseline;actual=copy.deepcopy(original);a=actual['arrays']
    if mutation=='source_hash':actual['metadata']['source_manifest_sha256']='0'*64
    elif mutation=='tissue':a['tissue_concentration'][0]+=100
    elif mutation=='input_integral':a['plasma_integral'][-1,0]+=100
    elif mutation=='coefficient':a['coefficients'][0,0,0,0]+=1
    elif mutation=='coefficient_receipt':
        token=actual['rows'][0]['coefficient_0'];value=float(token)if token else 0.
        actual['rows'][0]['coefficient_0']=str(value+1e-8+1e-6*abs(value)+5e-7)
    elif mutation=='vt':
        token=actual['rows'][0]['vt'];actual['rows'][0]['vt']=str((float(token)if token else 0.)+1)
    elif mutation=='summary':
        value=actual['summary']['groups'][0]['mean'];actual['summary']['groups'][0]['mean']=1 if value is None else value+1
    elif mutation=='missing_subject':actual['rows']=[r for r in actual['rows']if r['subject_id']!=ref['subject_ids'][0]]
    elif mutation=='duplicate_frame':a['frame_indices'][1]=a['frame_indices'][0]
    elif mutation=='ledger':actual['metadata']['source_observed']['persons'][0]['coalesced_knot_ledger'][0]['multiplicity']+=1
    elif mutation=='rank':a['model_rank'][0,0,0]=1
    elif mutation=='nan':a['coefficients'][0,0,0,0]=np.nan
    else:a['coefficients_defined'][0,0,0]=not a['coefficients_defined'][0,0,0]
    with pytest.raises((ValueError,KeyError)):m['proof_of_work'].verify(actual,ref)
    record_property('control_outcome','rejected_effective')


def test_failure_marker_is_authoritative(baseline,tmp_path,record_property):
    m,ref,_=baseline;(tmp_path/'failure_report.json').write_text('{}')
    with pytest.raises(ValueError):m['proof_of_work'].validate(tmp_path,ref)
    record_property('control_outcome','rejected_effective')
