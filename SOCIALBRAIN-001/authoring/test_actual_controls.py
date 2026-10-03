"""Authoring only: 1 genuine baseline, 3 equivalents, 9 rejection controls.

Never collect this file for production scoring or source-free qualification.
No original or output access occurs until the session fixture is requested.
Root binds the final private bootstrap SHA before the separately gated actual QA.
"""
import copy
import hashlib
import os
from pathlib import Path
import re
import stat
import types

import numpy as np
import pytest


BOOTSTRAP_SHA = 'c6d70f3a433c5360f4e2bd8fe2af4dcbf0e9d8a94cce8415b34beb0d5435a95f'


def private_bootstrap():
    if type(BOOTSTRAP_SHA) is not str or re.fullmatch('[0-9a-f]{64}', BOOTSTRAP_SHA) is None:
        raise ValueError('unfrozen_authoring_bootstrap_pin')
    path = Path('/tests/grader_bootstrap.py')
    for part in (*reversed(path.parents), path):
        mode = part.lstat().st_mode
        if stat.S_ISLNK(mode) or (part != path and not stat.S_ISDIR(mode)):
            raise ValueError('private_bootstrap_path')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= 1024**2:
        raise ValueError('private_bootstrap_size')
    def signature(info):
        return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        if signature(before) != signature(os.fstat(stream.fileno())): raise ValueError('private_bootstrap_changed')
        raw = stream.read(1024**2 + 1)
        if signature(before) != signature(os.fstat(stream.fileno())): raise ValueError('private_bootstrap_changed')
    if signature(before) != signature(path.lstat()) or len(raw) != before.st_size:
        raise ValueError('private_bootstrap_changed')
    if hashlib.sha256(raw).hexdigest() != BOOTSTRAP_SHA: raise ValueError('private_bootstrap_sha256')
    module = types.ModuleType('_socialbrain_actual_private_bootstrap'); module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


@pytest.fixture(scope='session')
def genuine():
    boot = private_bootstrap()
    boot.disjoint_output('/app/output', '/app/data/socialbrain', boot.PUBLIC_DOCUMENTS.values(), '/tests')
    context = boot.load_private(); modules = context['modules']
    reference = modules['source_reference'].reconstruct(data_dir='/app/data/socialbrain', **context['documents'], pilot=False)
    actual = modules['io_contract'].read_output('/app/output')
    result = modules['verify_artifacts'].verify_artifacts(actual, reference)
    boot.recheck_documents(context)
    assert result['status'] == 'ok'
    return modules['verify_artifacts'], modules['io_contract'], reference, actual


def test_genuine_baseline(genuine, record_property):
    record_property('control_mode', 'baseline')
    record_property('control_category', 'genuine')
    # The session fixture already performed the complete unmodified validation.
    assert genuine[2]['status'] == 'complete'
    record_property('control_outcome', 'accepted_genuine')


@pytest.mark.parametrize('mode', ['coherent_permutations', 'six_decimal_derived', 'metadata_equivalents'])
def test_equivalent_representation(genuine, record_property, mode):
    validator, _, reference, baseline = genuine; actual = copy.deepcopy(baseline)
    record_property('control_mode', mode); record_property('control_category', 'equivalent')
    a = actual['signal_evidence.npz']; m = actual['run_metadata.json']
    if mode == 'coherent_permutations':
        frames = np.arange(len(a['frame_indices']))[::-1]; subjects = np.arange(len(a['subject_ids']))[::-1]
        rois = np.arange(len(a['roi_ids']))[::-1]; pipelines = [1, 0]
        for key in ('frame_indices','frame_subject_ids','global_signal'): a[key] = a[key][frames]
        a['raw_roi'] = a['raw_roi'][frames][:,rois]
        a['cleaned_roi'] = a['cleaned_roi'][frames][:,pipelines][:,:,rois]
        a['canonical_active'] = a['canonical_active'][subjects][:,pipelines][:,:,rois]
        a['subject_ids'] = a['subject_ids'][subjects]; a['roi_ids'] = a['roi_ids'][rois]
        a['pipeline_ids'] = a['pipeline_ids'][pipelines]
        actual['network_connectivity.csv'] = [dict(reversed(list(row.items()))) for row in reversed(actual['network_connectivity.csv'])]
        for key in ('source_files','cohort','roi_definitions'): m[key].reverse()
        m['source_observed']['persons'].reverse(); m['analysis_observed']['persons'].reverse()
        for person in m['source_observed']['persons']:
            person['roi_supports'].reverse(); person['missing_selected_entries'].reverse()
        for person in m['analysis_observed']['persons']:
            person['pipelines'].reverse()
            for pipeline in person['pipelines']: pipeline['roi_activity'].reverse()
    elif mode == 'six_decimal_derived':
        for row in actual['network_connectivity.csv']:
            for key in validator.METRICS:
                if row[key] != '': row[key] = format(float(row[key]), '.6f')
        def rounded(value):
            if type(value) is float: return round(value, 6)
            if type(value) is list: return [rounded(item) for item in value]
            if type(value) is dict: return {key:rounded(item) for key,item in value.items()}
            return value
        actual['age_effects.json'] = rounded(actual['age_effects.json'])
        # Raw/clean/GS, source FD/age and metadata diagnostics retain precision.
    else:
        for row in m['roi_definitions']:
            row['center_mm'] = [float(value) for value in row['center_mm']]
            row['radius_mm'] = int(row['radius_mm'])
        headers = [m['source_observed']['template']['header']]
        headers += [person['bold_header'] for person in m['source_observed']['persons']]
        for header in headers:
            dtype = np.dtype(header['storage_dtype'])
            header['storage_dtype'] = dtype.name if dtype.isnative else dtype.str
        m['optional_note'] = 'Bounded descriptive metadata does not supply scientific authority.'
        actual['findings.md'] += '\nRepresentation-only authoring control.\n'
    assert validator.verify_artifacts(actual, reference)['status'] == 'ok'
    record_property('control_outcome', 'accepted_equivalent')


@pytest.mark.parametrize('mode,reason,category', [
    ('empty','required_object_fields','binding'), ('wrong_source_hash','exact_string','binding'),
    ('clean_offset','clean_pointwise_fidelity','numerical'), ('raw_offset','source_primitive_tolerance','numerical'),
    ('fd_offset','numeric_tolerance','numerical'), ('wrong_group','exact_string','binding'),
    ('missing_participant','record_membership','binding'), ('p_domain','p_domain','numerical')])
def test_rejection_control(genuine, record_property, mode, reason, category):
    validator, _, reference, baseline = genuine; actual = copy.deepcopy(baseline)
    record_property('control_mode', mode); record_property('control_category', category)
    if mode == 'empty': actual = {}
    elif mode == 'wrong_source_hash':
        original = actual['run_metadata.json']['source_manifest_sha256']
        actual['run_metadata.json']['source_manifest_sha256'] = ('0' if original[0] != '0' else '1') + original[1:]
    elif mode == 'clean_offset': actual['signal_evidence.npz']['cleaned_roi'].flat[0] += 1.
    elif mode == 'raw_offset': actual['signal_evidence.npz']['raw_roi'].flat[0] += 1e4
    elif mode == 'fd_offset':
        row = actual['network_connectivity.csv'][0]; row['mean_fd'] = repr(float(row['mean_fd']) + 1.)
    elif mode == 'wrong_group':
        row = actual['network_connectivity.csv'][0]; row['group'] = 'adult' if row['group'] == 'child' else 'child'
    elif mode == 'missing_participant': actual['network_connectivity.csv'].pop()
    else: actual['age_effects.json']['within_tom']['p'] = 1.001
    with pytest.raises(ValueError, match=reason): validator.verify_artifacts(actual, reference)
    record_property('control_outcome', 'effective_' + category + '_rejection')


def test_authoritative_failure_marker(genuine, tmp_path, record_property):
    _, io, _, _ = genuine
    record_property('control_mode', 'failure_marker'); record_property('control_category', 'binding')
    output = tmp_path/'detached-output'; output.mkdir()
    (output/'failure_report.json').write_text('{"status":"manufactured_failure"}\n')
    with pytest.raises(ValueError, match='failed_run_marker'): io.read_output(output)
    record_property('control_outcome', 'effective_binding_rejection')
