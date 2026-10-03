"""Manufactured serialization and output-ownership checks only."""
import copy
import importlib.util
import json
import os
from pathlib import Path

import numpy as np
import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


W, K = load('output_writer'), load('reporting_kernel')


@pytest.fixture
def reference():
    ids = [f'sub-pixar{i:03d}' for i in range(1, 156)]
    rng = np.random.default_rng(515)
    clean = rng.normal(size=(8, 2, 12))
    clean -= clean.mean(axis=0)
    persons = {sid: dict(cleaned_roi=clean.copy(), canonical_active=np.ones((2, 12), bool),
                         frame_indices=np.arange(8), raw_roi=clean[:, 0, :].copy(),
                         global_signal=np.arange(8, dtype=float)) for sid in ids}
    covariates = {sid: dict(age=float(5 + i % 10), group='child' if i < 122 else 'adult',
                           mean_fd=float(.1 + (i % 8) / 100)) for i, sid in enumerate(ids)}
    return dict(status='complete', subject_ids=ids, roi_ids=list(K.ROI_IDS),
        pipeline_ids=list(K.PIPELINE_IDS), persons=persons, covariates=covariates,
        pins={key: str(i) * 64 for i, key in enumerate(('source_manifest_sha256', 'method_sha256',
                'output_schema_sha256', 'reporting_kernel_sha256'), 1)},
        source_files=[], source_observed={}, analysis_observed={'persons': []},
        cohort=[], roi_definitions=[])


def test_exact_five_artifacts_and_unrounded_own_replay(reference, tmp_path):
    output = tmp_path / 'output'
    result = W.write_artifacts(reference, output, K)
    assert {p.name for p in output.iterdir()} == set(W.FILES)
    assert result['n_children'] == 122 and result['n_adults'] == 33
    assert result['within_tom']['status'] == 'constant_source_metric'
    assert result['adult_support']['within_tom']['status'] == 'ok'
    with np.load(output / 'signal_evidence.npz', allow_pickle=False) as archive:
        assert archive['cleaned_roi'].shape == (1240, 2, 12)
        assert archive['canonical_active'].shape == (155, 2, 12)
        np.testing.assert_array_equal(archive['cleaned_roi'][:8], reference['persons']['sub-pixar001']['cleaned_roi'])
    assert json.loads((output / 'age_effects.json').read_text()) == result
    assert len((output / 'network_connectivity.csv').read_text().splitlines()) == 156
    assert (output / 'findings.md').stat().st_size > 0
    metadata = json.loads((output / 'run_metadata.json').read_text())
    assert metadata['status'] == 'complete' and metadata['software_versions']['nilearn'] == '0.12.1'
    assert metadata['analysis_observed']['child_motion_nuisance_rank'] == 2


def test_existing_real_empty_directory_allowed(reference, tmp_path):
    output = tmp_path / 'empty'; output.mkdir()
    W.write_artifacts(reference, output, K)
    assert len(list(output.iterdir())) == 5


@pytest.mark.parametrize('case', ['file', 'symlink', 'broken_link', 'fifo', 'nonempty', 'failure_marker'])
def test_unsafe_outputs_preserved(reference, tmp_path, case):
    output = tmp_path / 'output'
    if case == 'file': output.write_text('keep')
    elif case == 'symlink':
        target = tmp_path / 'target'; target.mkdir(); output.symlink_to(target)
    elif case == 'broken_link': output.symlink_to(tmp_path / 'absent')
    elif case == 'fifo': os.mkfifo(output)
    else:
        output.mkdir()
        (output / ('failure_report.json' if case == 'failure_marker' else 'keep')).write_text('keep')
    with pytest.raises(ValueError): W.write_artifacts(reference, output, K)
    if case == 'file': assert output.read_text() == 'keep'
    if case in ('nonempty', 'failure_marker'):
        assert len(list(output.iterdir())) == 1


@pytest.mark.parametrize('case', ['source', 'source_child', 'ancestor', 'code'])
def test_protected_source_and_code_paths(reference, tmp_path, case):
    source = tmp_path / 'source'; source.mkdir()
    protected = [source]
    output = {'source': source, 'source_child': source / 'new', 'ancestor': tmp_path,
              'code': Path(W.__file__).parent}[case]
    with pytest.raises(ValueError, match='protected_overlap'):
        W.write_artifacts(reference, output, K, protected=protected)
    assert list(source.iterdir()) == []


@pytest.mark.parametrize('case', ['partial', 'wrong_cohort', 'serialization', 'nonfinite'])
def test_owned_failure_marker_no_success_relabel(reference, tmp_path, case):
    if case == 'partial': reference['status'] = 'pilot_only'
    elif case == 'wrong_cohort': reference['subject_ids'][0] = '001'
    elif case == 'serialization': reference['source_observed']['invalid'] = object()
    else: reference['persons']['sub-pixar001']['cleaned_roi'][0, 0, 0] = np.nan
    output = tmp_path / 'output'
    with pytest.raises((ValueError, TypeError)):
        W.write_artifacts(reference, output, K)
    marker = json.loads((output / 'failure_report.json').read_text())
    assert marker['status'] == 'failed_precondition'
    before = (output / 'failure_report.json').read_bytes()
    with pytest.raises(ValueError): W.write_artifacts(reference, output, K)
    assert (output / 'failure_report.json').read_bytes() == before


def test_writer_leaves_reference_unchanged(reference, tmp_path):
    before = copy.deepcopy(reference)
    W.write_artifacts(reference, tmp_path / 'output', K)
    assert reference['analysis_observed'] == before['analysis_observed']
    assert reference['pins'] == before['pins']
    for sid in reference['subject_ids']:
        for key in reference['persons'][sid]:
            np.testing.assert_array_equal(reference['persons'][sid][key], before['persons'][sid][key])
