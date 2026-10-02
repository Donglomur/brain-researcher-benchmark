"""Authoring-only original-output QA, excluded from production scoring.

Install beside actual_control_helpers.py in tests/authoring_actual. Parent
tests/conftest.py supplies authenticated private_modules and the single session
original_reference. Importing or collecting this file performs no source IO.
Unexpected failures retain their detached candidate under pytest's basetemp.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

_path=Path(__file__).absolute().with_name('actual_control_helpers.py')
_spec=importlib.util.spec_from_file_location('_n170_actual_control_helpers',_path)
helpers=importlib.util.module_from_spec(_spec)
sys.modules[_spec.name]=helpers
_spec.loader.exec_module(helpers)


@pytest.fixture(scope='session')
def genuine_context(original_reference,private_modules):
    reader=private_modules['io_contract'];proof=private_modules['proof_of_work']
    path=reader.safe_path(os.environ.get('REPAIR_ORACLE_OUTPUT',os.environ.get('OUTPUT_DIR','/app/output')))
    result=proof.validate_bundle(path,original_reference)
    assert result['status']=='accepted' and result['n_subjects']==37
    captured=helpers.snapshot(path,reader)
    replayed=helpers.baseline_replay(path,original_reference,private_modules)
    assert helpers.snapshot(path,reader)==captured
    return dict(path=path,captured=captured,replayed=replayed,
                reference=original_reference,modules=private_modules)


def record_effect(record_property,info):
    record_property('control_mode',info['mode'])
    record_property('control_category',info['category'])
    record_property('prevalidation_classification',info['classification'])
    for key in ('effect_count','numeric_effect_count','binding_effect_count','status_effect_count'):
        record_property(key,str(info[key]))
    gap=info['effect_max_absolute_gap']
    record_property('effect_max_absolute_gap','None' if gap is None else repr(gap))
    record_property('control_effect',json.dumps(info,sort_keys=True,allow_nan=False))


@pytest.mark.parametrize('mode',tuple(helpers.MODES))
def test_actual_control(genuine_context,tmp_path,record_property,mode):
    context=genuine_context;modules=context['modules'];reader=modules['io_contract']
    reference=context['reference'];proof=modules['proof_of_work']
    protected=[context['path'],Path(__file__).absolute().parent,
               os.environ.get('DATA_DIR','/app/data/n170profile')]
    candidate=helpers.clone(tmp_path/'candidate',context['captured'],reader,protected)
    record_property('genuine_prevalidation','accepted')
    try:
        try:info=helpers.mutate(candidate,mode,reference,modules,context['replayed'])
        except helpers.NotConstructed as exc:
            info=helpers.receipt(mode);info.update(classification='not_constructed',reason=str(exc))
            record_effect(record_property,info)
            record_property('control_outcome','not_constructed')
            return
        record_effect(record_property,info)
        if info['classification']=='nondiscriminating':
            record_property('control_outcome','nondiscriminating')
            return
        if info['category']=='positive':
            result=proof.validate_bundle(candidate,reference)
            assert result['status']=='accepted' and result['n_subjects']==37
            record_property('control_outcome','accepted_genuine' if mode=='baseline' else 'accepted_positive')
        else:
            assert info['classification']=='effective' and info['effect_count']>0
            with pytest.raises(ValueError) as caught:proof.validate_bundle(candidate,reference)
            record_property('rejection_reason',str(caught.value))
            assert info['expected_rejection_fragment'] in str(caught.value)
            record_property('control_outcome','effective_'+info['category']+'_rejection')
    finally:
        assert helpers.snapshot(context['path'],reader)==context['captured'],'genuine artifact bytes changed'
