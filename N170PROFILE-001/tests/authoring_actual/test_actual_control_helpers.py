"""Manufactured controls only; never import source reconstruction or originals."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module


HERE=Path(__file__).absolute().parent
# External preparation uses sibling files. Installed tests/authoring_actual uses
# private code in tests/ and the source-free emitter in task-root authoring/.
CODE=HERE if (HERE/'io_contract.py').is_file() else HERE.parent
SUPPORT=HERE/'proof_fixture_support.py'
if not SUPPORT.is_file():SUPPORT=HERE.parent.parent/'authoring'/'proof_fixture_support.py'
modules={name:load(name,CODE/(name+'.py')) for name in
         ('io_contract','measurement_kernel','wave_contract','proof_of_work')}
f=load('_n170_manufactured_emitter',SUPPORT)
h=load('_n170_manufactured_controls',HERE/'actual_control_helpers.py')
reader=modules['io_contract'];proof=modules['proof_of_work']


@pytest.fixture
def bundle(tmp_path):
    ref=f.manufactured_reference();out=f.emit(tmp_path/'genuine',ref)
    assert proof.validate_bundle(out,ref)['status']=='accepted'
    return out,ref,h.snapshot(out,reader),h.baseline_replay(out,ref,modules)


@pytest.mark.parametrize('mode',tuple(h.MODES))
def test_each_predeclared_control_has_expected_effect_and_normal_validation(bundle,tmp_path,mode):
    original,ref,captured,replay=bundle;out=h.clone(tmp_path/'copy',captured,reader,[original])
    info=h.mutate(out,mode,ref,modules,replay)
    if h.MODES[mode]=='positive':
        assert info['classification']=='constructed'
        assert proof.validate_bundle(out,ref)['status']=='accepted'
    else:
        assert info['classification']=='effective' and info['effect_count']>0
        with pytest.raises(ValueError,match=info['expected_rejection_fragment']):proof.validate_bundle(out,ref)
    assert h.snapshot(original,reader)==captured


@pytest.mark.parametrize('mode',['condition_sign_flip','participant_amplitude_plus_one','headline_mean_plus_one'])
def test_missing_conditions_do_not_forge_effective_numerical_controls(tmp_path,mode):
    ref=f.manufactured_reference('missing_all');out=f.emit(tmp_path/'out',ref)
    assert proof.validate_bundle(out,ref)['status']=='accepted'
    info=h.mutate(out,mode,ref,modules,h.baseline_replay(out,ref,modules))
    assert info['classification']=='nondiscriminating' and info['effect_count']==0


def test_exact_zero_condition_waves_make_sign_flip_nondiscriminating(tmp_path):
    ref=f.manufactured_reference();ref['evoked_po8_uv'][:]=0
    out=f.emit(tmp_path/'out',ref);assert proof.validate_bundle(out,ref)['status']=='accepted'
    info=h.mutate(out,'condition_sign_flip',ref,modules,h.baseline_replay(out,ref,modules))
    assert info['classification']=='nondiscriminating' and info['effect_max_absolute_gap']==0


def test_no_changed_values_is_explicitly_nondiscriminating():
    info=h.classify(h.receipt('ptp_plus_one'),np.empty((0,30)),np.empty((0,30),bool))
    assert info['classification']=='nondiscriminating' and info['effect_count']==0
    assert info['effect_max_absolute_gap'] is None


def test_amplitude_effect_is_against_accepted_wave_replay_not_source_endpoint(tmp_path):
    ref=f.manufactured_reference();waves=ref['evoked_po8_uv'].copy();waves[:,0]*=1+2e-9
    out=f.emit(tmp_path/'out',ref,waves);assert proof.validate_bundle(out,ref)['status']=='accepted'
    replay=h.baseline_replay(out,ref,modules)
    info=h.mutate(out,'participant_amplitude_plus_one',ref,modules,replay)
    assert info['classification']=='effective'
    assert abs(info['effect_max_absolute_gap']-1)<1e-12


def test_ptp_effect_alignment_uses_epoch_and_channel_keys(bundle,tmp_path):
    original,ref,captured,replay=bundle;out=h.clone(tmp_path/'copy',captured,reader,[original])
    h.mutate(out,'coherent_axes_rows',ref,modules,replay)
    info=h.mutate(out,'ptp_plus_one',ref,modules,replay)
    assert info['numeric_effect_count']==len(ref['epoch_keys'])*30
    with pytest.raises(ValueError,match='numeric_tolerance'):proof.validate_bundle(out,ref)


def test_extra_regular_artifact_is_preserved(bundle,tmp_path):
    original,ref,_,replay=bundle;(original/'extra.txt').write_text('descriptive only')
    captured=h.snapshot(original,reader);out=h.clone(tmp_path/'copy',captured,reader,[original])
    h.mutate(out,'coherent_axes_rows',ref,modules,replay)
    assert reader.read_bytes(out/'extra.txt')==captured['extra.txt']
    assert proof.validate_bundle(out,ref)['status']=='accepted'


@pytest.mark.parametrize('kind',['real_symlink','dangling_symlink','directory'])
def test_snapshot_rejects_nonregular_extra_without_touching_target(bundle,tmp_path,kind):
    original,_,_,_=bundle;target=tmp_path/'target';target.write_bytes(b'preserved')
    if kind=='directory':(original/'extra').mkdir()
    else:(original/'extra').symlink_to(target if kind=='real_symlink' else tmp_path/'absent')
    with pytest.raises(ValueError,match='nonregular_output'):h.snapshot(original,reader)
    assert target.read_bytes()==b'preserved'


def test_failure_marker_is_not_copied_as_a_genuine_bundle(bundle):
    original,_,_,_=bundle;(original/'failure_report.json').write_text('{}')
    with pytest.raises(ValueError,match='failed_run_marker'):h.snapshot(original,reader)


def test_copy_rejects_existing_destination_and_source_overlap(bundle,tmp_path):
    original,_,captured,_=bundle;existing=tmp_path/'exists';existing.mkdir();(existing/'keep').write_bytes(b'old')
    with pytest.raises(ValueError,match='fresh_control_destination'):h.clone(existing,captured,reader,[original])
    with pytest.raises(ValueError,match='control_source_overlap'):h.clone(original/'nested',captured,reader,[original])
    assert (existing/'keep').read_bytes()==b'old'


@pytest.mark.parametrize(
    "name",
    ["../escape", "/absolute", "sub/path", "a\\b", ".."],
)
def test_copy_rejects_unsafe_snapshot_member(bundle,tmp_path,name):
    original,_,captured,_=bundle;captured=dict(captured);captured[name]=b'x'
    with pytest.raises(ValueError,match='control_name'):h.clone(tmp_path/'copy',captured,reader,[original])
    assert not (tmp_path/'copy').exists()


def test_serialization_headroom_is_not_an_acceptance_requirement(bundle,monkeypatch):
    out,_,captured,_=bundle
    monkeypatch.setattr(reader,'AGGREGATE_LIMIT',sum(map(len,captured.values())))
    with pytest.raises(h.NotConstructed,match='no headroom requirement'):
        h.replace(out,'findings.md',captured['findings.md']+b'x',reader)
    assert h.snapshot(out,reader)==captured


def test_unknown_output_is_not_created(bundle):
    out,_,captured,_=bundle
    with pytest.raises(ValueError,match='unknown_control_file'):h.replace(out,'unknown.txt',b'x',reader)
    assert h.snapshot(out,reader)==captured


def test_large_valid_documentary_csv_field_uses_public_field_bound(bundle):
    out,_,_,_=bundle;fields,rows=h.read_csv(out/'per_subject.csv',reader)
    fields.append('optional_note')
    for row in rows:row['optional_note']='x'*140000 if row is rows[0] else ''
    h.replace(out,'per_subject.csv',h.csv_bytes(fields,rows),reader)
    got_fields,got_rows=h.read_csv(out/'per_subject.csv',reader)
    assert got_fields==fields and len(got_rows[0]['optional_note'])==140000
