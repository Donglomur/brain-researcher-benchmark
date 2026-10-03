"""Manufactured writer/ownership tests; no original source or output reads."""
import copy
import csv
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


W, K = load('output_writer'), load('reporting_kernel')


@pytest.fixture
def reference():
    ids = list(W.IDS)
    rois = [f'Power-row-{i:03d}' for i in range(264)]
    coordinates = np.column_stack((np.arange(264, dtype=float), np.zeros((264, 2))))
    persons = {sid: dict(raw_roi=np.full((8, 264), 100.),
                        cleaned_roi=np.zeros((8, 264)),
                        canonical_active=np.zeros(264, bool),
                        frame_indices=np.arange(8)) for sid in ids}
    covariates = {sid: dict(age=float(5 + i % 10), group='child' if i < 122 else 'adult',
                           mean_fd=float(.1 + (i % 8) / 100)) for i, sid in enumerate(ids)}
    return dict(status='complete', subject_ids=ids, structural_subject_ids=ids,
        roi_ids=rois, coordinates=coordinates, persons=persons, covariates=covariates,
        pins={key: str(i) * 64 for i, key in enumerate(W.PIN_NAMES, 1)},
        source_files=[], source_observed={'persons': []}, analysis_observed={'persons': []},
        cohort=[dict(subject_id=sid, **covariates[sid], mean_fd_observed_count=8,
                     mean_fd_missing_frame_indices=[]) for sid in ids],
        roi_definitions=[dict(roi_id=rid, center_mm=xyz.tolist(), radius_mm=5.)
                         for rid, xyz in zip(rois, coordinates)], warnings=['Manufactured writer fixture.'])


@pytest.fixture
def active_reference(reference):
    rng = np.random.default_rng(871)
    selected = [0, 1, 130, 262, 263]
    for sid in W.IDS:
        person = reference['persons'][sid]
        value = rng.normal(size=(8, 5))
        value -= value.mean(axis=0)
        person['cleaned_roi'][:, selected] = value
        person['raw_roi'][:, selected] = value + 100.
        person['canonical_active'][selected] = True
    return reference


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def wrapped_kernel(change):
    def analyze(*args, **kwargs):
        result = K.analyze(*args, **kwargs)
        change(result)
        return result
    return SimpleNamespace(**{name: getattr(K, name) for name in
        ('METRICS','ASSOCIATIONS','real_array','validate_clean_series','bootstrap_indices')}, analyze=analyze)


def test_exact_five_artifacts_complete_undefined_and_fixed_bootstrap(reference,tmp_path):
    output=tmp_path/'output'
    effects=W.write_artifacts(reference,output,K)
    assert {p.name for p in output.iterdir()}==set(W.FILES)
    assert effects['n_children']==122 and effects['n_adults']==33
    for record in effects['children_age_spearman'].values():
        assert record['status']=='incomplete_subject_support' and record['r'] is None
        assert record['raw_bootstrap']['n_defined']==0 and record['raw_bootstrap']['ci95'] is None
    with np.load(output/W.FILES[0],allow_pickle=False) as archive:
        assert len(archive.files)==17
        assert archive['raw_roi'].shape==archive['cleaned_roi'].shape==(1240,264)
        assert archive['canonical_active'].shape==(155,264)
        assert archive['bootstrap_r'].shape==(1000,3,2)
        assert archive['bootstrap_defined'].dtype==bool and not archive['bootstrap_defined'].any()
        assert np.all(archive['bootstrap_r']==0.)
        np.testing.assert_array_equal(archive['bootstrap_child_ids'],list(W.IDS)[:122])
        np.testing.assert_array_equal(archive['bootstrap_indices'],K.bootstrap_indices(122))
        np.testing.assert_array_equal(archive['bootstrap_draw_ids'],np.arange(1000))
    rows=read_csv(output/W.FILES[1])
    assert list(rows[0])==list(W.COLUMNS) and len(rows)==155
    assert rows[0]['short_range']==rows[0]['segregation']==''
    assert rows[0]['short_range_status']=='empty_edge_family'
    assert json.loads((output/W.FILES[2]).read_text())==effects
    meta=json.loads((output/W.FILES[3]).read_text())
    assert meta['warnings']==reference['warnings']
    assert meta['source_observed']==reference['source_observed']
    assert meta['analysis_observed']==reference['analysis_observed']
    assert meta['reporting_kernel_sha256']==reference['pins']['reporting_kernel_sha256']
    assert all(type(v) is str and v for v in meta['software_versions'].values())
    assert (output/W.FILES[4]).stat().st_size>0


def test_active_quantitative_own_replay_never_csv_cascade(active_reference,tmp_path):
    reference=active_reference
    accepted={sid:p['cleaned_roi'].copy() for sid,p in reference['persons'].items()}
    accepted['sub-pixar001'][:,0]+=np.linspace(-1e-9,1e-9,8)
    calls=[]
    def analyze(*args,**kw):
        calls.append(args)
        return K.analyze(*args,**kw)
    module=SimpleNamespace(**{name:getattr(K,name) for name in
        ('METRICS','ASSOCIATIONS','real_array','validate_clean_series','bootstrap_indices')},analyze=analyze)
    output=tmp_path/'own'
    effects=W.write_artifacts(reference,output,module,accepted_clean=accepted)
    assert len(calls)==1 and calls[0][0] is not calls[0][1]
    np.testing.assert_array_equal(calls[0][0]['sub-pixar001'],accepted['sub-pixar001'])
    np.testing.assert_array_equal(calls[0][1]['sub-pixar001'],reference['persons']['sub-pixar001']['cleaned_roi'])
    with np.load(output/W.FILES[0],allow_pickle=False) as archive:
        np.testing.assert_array_equal(archive['cleaned_roi'][:8],accepted['sub-pixar001'])
    own=K.participant_metrics(accepted['sub-pixar001'],reference['persons']['sub-pixar001']['canonical_active'],
                              K.distance_bins(reference['coordinates'],reference['roi_ids']))
    row=read_csv(output/W.FILES[1])[0]
    for metric in K.METRICS:
        assert own['values'][metric] is not None
        assert float(row[metric])==own['values'][metric]
        assert effects['group_means'][metric]['child']['n_defined']==122


def test_coherent_subject_frame_and_roi_order(reference,tmp_path):
    # The ROI axis remains tied to coordinates and definitions; no integer ID alias.
    reference['subject_ids'].reverse()
    order=np.arange(264)[::-1]
    reference['roi_ids']=[reference['roi_ids'][i] for i in order]
    reference['coordinates']=reference['coordinates'][order]
    reference['roi_definitions']=[reference['roi_definitions'][i] for i in order]
    for p in reference['persons'].values():
        p['frame_indices']=np.arange(8)[::-1]
        p['raw_roi']=np.arange(8*264,dtype=float).reshape(8,264)[::-1][:,order]
        p['cleaned_roi']=p['cleaned_roi'][::-1][:,order]
        p['canonical_active']=p['canonical_active'][order]
    output=tmp_path/'permuted'
    W.write_artifacts(reference,output,K)
    with np.load(output/W.FILES[0],allow_pickle=False) as archive:
        np.testing.assert_array_equal(archive['subject_ids'],W.IDS)
        np.testing.assert_array_equal(archive['roi_ids'],reference['roi_ids'])
        np.testing.assert_array_equal(archive['frame_indices'][:8],np.arange(8))
        np.testing.assert_array_equal(archive['raw_roi'][:8],
                                     np.arange(8*264,dtype=float).reshape(8,264)[:,order])
        # Child IDs and index draw slots remain canonical despite participant reorder.
        np.testing.assert_array_equal(archive['bootstrap_child_ids'],list(W.IDS)[:122])
        np.testing.assert_array_equal(archive['bootstrap_indices'],K.bootstrap_indices(122))


def test_existing_empty_output_allowed(reference,tmp_path):
    output=tmp_path/'empty';output.mkdir()
    W.write_artifacts(reference,output,K)
    assert len(list(output.iterdir()))==5


@pytest.mark.parametrize('case',['file','symlink','broken_link','fifo','nonempty','failure_marker','broken_failure'])
def test_unsafe_outputs_preserved(reference,tmp_path,case):
    output=tmp_path/'output'
    if case=='file':output.write_text('keep')
    elif case=='symlink':
        target=tmp_path/'target';target.mkdir();output.symlink_to(target)
    elif case=='broken_link':output.symlink_to(tmp_path/'absent')
    elif case=='fifo':os.mkfifo(output)
    else:
        output.mkdir()
        if case=='broken_failure':(output/'failure_report.json').symlink_to(tmp_path/'missing')
        else:(output/('failure_report.json' if case=='failure_marker' else 'keep')).write_text('keep')
    with pytest.raises(ValueError):W.write_artifacts(reference,output,K)
    if case=='file':assert output.read_text()=='keep'
    if case in ('nonempty','failure_marker','broken_failure'):assert len(list(output.iterdir()))==1


@pytest.mark.parametrize('case',['source','source_child','ancestor','code','document'])
def test_protected_paths_never_get_failure_marker(reference,tmp_path,case):
    source=tmp_path/'source';source.mkdir()
    document=tmp_path/'method.json';document.write_text('original')
    protected=[source,document]
    output={'source':source,'source_child':source/'new','ancestor':tmp_path,
            'code':Path(W.__file__).parent,'document':document}[case]
    with pytest.raises(ValueError):W.write_artifacts(reference,output,K,protected=protected)
    assert list(source.iterdir())==[] and document.read_text()=='original'
    assert not (tmp_path/'failure_report.json').exists()


@pytest.mark.parametrize('case',['partial','wrong_cohort','duplicate_cohort','missing_person','extra_person',
    'wrong_roi','duplicate_roi','numeric_roi','frame_missing','frame_boolean','active_numeric',
    'raw_nonfinite','clean_nonfinite','pin','warning_object','serialization'])
def test_owned_failure_marker_no_success_relabel(reference,tmp_path,case):
    p=reference['persons']['sub-pixar001']
    if case=='partial':reference['status']='resource_pilot'
    elif case=='wrong_cohort':reference['subject_ids'][0]='001'
    elif case=='duplicate_cohort':reference['subject_ids'][0]=reference['subject_ids'][1]
    elif case=='missing_person':reference['persons'].pop('sub-pixar001')
    elif case=='extra_person':reference['persons']['other']=p
    elif case=='wrong_roi':reference['roi_ids'].pop()
    elif case=='duplicate_roi':reference['roi_ids'][0]=reference['roi_ids'][1]
    elif case=='numeric_roi':reference['roi_ids'][0]=1
    elif case=='frame_missing':p['frame_indices'][0]=1
    elif case=='frame_boolean':p['frame_indices']=[False,*range(1,8)]
    elif case=='active_numeric':p['canonical_active']=np.zeros(264,dtype=int)
    elif case=='raw_nonfinite':p['raw_roi'][0,0]=np.inf
    elif case=='clean_nonfinite':p['cleaned_roi'][0,0]=np.nan
    elif case=='pin':reference['pins']['method_sha256']=None
    elif case=='warning_object':reference['warnings']=[{}]
    else:reference['source_observed']['bad']=object()
    output=tmp_path/'output'
    with pytest.raises((ValueError,TypeError)):W.write_artifacts(reference,output,K)
    before=(output/'failure_report.json').read_bytes()
    assert json.loads(before)['status']=='failed_precondition'
    with pytest.raises(ValueError):W.write_artifacts(reference,output,K)
    assert (output/'failure_report.json').read_bytes()==before


@pytest.mark.parametrize('case',['missing','wrong_shape','source_far'])
def test_optional_accepted_inputs_source_close_and_complete(reference,tmp_path,case):
    values={sid:p['cleaned_roi'].copy() for sid,p in reference['persons'].items()}
    if case=='missing':values.pop('sub-pixar001')
    elif case=='wrong_shape':values['sub-pixar001']=np.zeros((8,263))
    else:values['sub-pixar001'][0,0]=.01
    with pytest.raises(ValueError):W.write_artifacts(reference,tmp_path/'bad',K,accepted_clean=values)


@pytest.mark.parametrize('case',['child_order','slot_order','seed','draw_count','metric_order',
    'sentinel','nonfinite','defined_type','rank_type','df'])
def test_bootstrap_axes_slots_and_typed_sentinels(reference,tmp_path,case):
    def change(result):
        b=result['bootstrap']
        if case=='child_order':b['subject_ids'].reverse()
        elif case=='slot_order':b['indices']=b['indices'][:,::-1]
        elif case=='seed':b['seed']=12
        elif case=='draw_count':b['n_draws']=999
        elif case=='metric_order':b['metric_ids'].reverse()
        elif case=='sentinel':b['r'][0,0,0]=.01
        elif case=='nonfinite':b['r'][0,0,0]=np.nan
        elif case=='defined_type':b['defined']=b['defined'].astype(int)
        elif case=='rank_type':b['motion_nuisance_rank']=b['motion_nuisance_rank'].astype(float)
        else:b['motion_df'][0]+=1
    with pytest.raises(ValueError):W.write_artifacts(reference,tmp_path/'bad',wrapped_kernel(change))


@pytest.mark.parametrize('kind',['failure','broken_failure','extra_file','extra_dir'])
def test_late_output_entries_invalidate_success(reference,tmp_path,monkeypatch,kind):
    output=tmp_path/'output'
    original=W.findings
    def late(effects):
        if kind=='failure':(output/'failure_report.json').write_text('preserved')
        elif kind=='broken_failure':(output/'failure_report.json').symlink_to(output/'absent')
        elif kind=='extra_file':(output/'intruder').write_text('late')
        else:(output/'intruder').mkdir()
        return original(effects)
    monkeypatch.setattr(W,'findings',late)
    with pytest.raises(ValueError):W.write_artifacts(reference,output,K)
    assert os.path.lexists(output/'failure_report.json')
    if kind=='failure':assert (output/'failure_report.json').read_text()=='preserved'


def test_caps_and_reference_no_mutation(reference,tmp_path,monkeypatch):
    before=copy.deepcopy(reference)
    monkeypatch.setattr(W,'TOTAL_CAP',1)
    with pytest.raises(ValueError,match='artifact_size_cap'):W.write_artifacts(reference,tmp_path/'cap',K)
    assert reference['pins']==before['pins'] and reference['analysis_observed']==before['analysis_observed']
    for sid in W.IDS:
        for key in reference['persons'][sid]:
            np.testing.assert_array_equal(reference['persons'][sid][key],before['persons'][sid][key])


def test_expanded_arrays_are_bounded_before_archive_write(reference,tmp_path,monkeypatch):
    monkeypatch.setattr(W,'NPZ_EXPANDED_CAP',1)
    output=tmp_path/'expanded'
    with pytest.raises(ValueError,match='expanded_array_cap'):W.write_artifacts(reference,output,K)
    assert not (output/W.FILES[0]).exists()
    assert (output/'failure_report.json').exists()


def test_schema_required_array_and_csv_names_are_exact():
    schema=json.loads(Path(__file__).with_name('output_schema.json').read_text())
    assert schema['required_files']==list(W.FILES)
    assert schema[W.FILES[1]]['required_columns']==list(W.COLUMNS)
    arrays=schema[W.FILES[0]]['required_arrays']
    assert set(arrays)=={'subject_ids','roi_ids','frame_subject_ids','frame_indices','raw_roi','cleaned_roi',
        'canonical_active','bootstrap_child_ids','bootstrap_draw_ids','bootstrap_metric_ids',
        'bootstrap_association_ids','bootstrap_indices','bootstrap_r','bootstrap_defined','bootstrap_status',
        'bootstrap_motion_nuisance_rank','bootstrap_motion_df'}
