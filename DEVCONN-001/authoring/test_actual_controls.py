"""Authoring-only DEVCONN controls; never part of production scoring.

Default collection is source-free: actual cases skip unless the parent gate sets
REPAIR_RUN_ACTUAL_CONTROLS=1. Once enabled, missing inputs/pins fail, not skip.
One module-scoped complete private reconstruction and one genuine oracle bundle
are validated before detached mutations. No source override, original writes,
canonical endpoint target, model search, or signal-perturbation retry is allowed.
Unexpected candidates are retained under pytest's parent-owned basetemp.
"""
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types

import numpy as np
import pytest


BOOTSTRAP_SHA = 'aca6f8b5f2e53db071678b43a122dab97ea3fd03d996933955e111a972dc228e'
WRITER_SHA = '99c33e0f796eeb818f6520886eba0086dbfc64c8867a8b1954b8426512ca1c5b'
DATA = '/app/data/devconn'
OUTPUT = '/app/output'
WRITER = '/solution/output_writer.py'


def held_module(path, digest, name):
    if type(digest) is not str or re.fullmatch('[0-9a-f]{64}', digest) is None:
        raise ValueError('unfrozen_authoring_code_pin')
    path = Path(path)
    for part in (*reversed(path.parents), path):
        mode = part.lstat().st_mode
        if stat.S_ISLNK(mode) or (part != path and not stat.S_ISDIR(mode)):
            raise ValueError('authoring_code_path')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= 1024**2:
        raise ValueError('authoring_code_size')
    def sig(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        if sig(before) != sig(os.fstat(stream.fileno())): raise ValueError('authoring_code_changed')
        raw = stream.read(before.st_size + 1)
        stream.seek(0)
        again = stream.read(before.st_size + 1)
        if raw != again or sig(before) != sig(os.fstat(stream.fileno())):
            raise ValueError('authoring_code_changed')
    if sig(before) != sig(path.lstat()) or len(raw) != before.st_size:
        raise ValueError('authoring_code_changed')
    if hashlib.sha256(raw).hexdigest() != digest: raise ValueError('authoring_code_sha256')
    module = types.ModuleType(name); module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


@pytest.fixture(scope='module')
def genuine():
    if os.environ.get('REPAIR_RUN_ACTUAL_CONTROLS') != '1':
        pytest.skip('actual source/output controls require a separate explicit parent gate')
    boot = held_module('/tests/grader_bootstrap.py', BOOTSTRAP_SHA, '_devconn_actual_bootstrap')
    boot.disjoint_output(OUTPUT, DATA, boot.PUBLIC_DOCUMENTS.values(), '/tests')
    context = boot.load_private(); modules = context['modules']
    io = modules['io_contract']; validator = modules['validator']
    inventory = io.output_inventory(OUTPUT)
    file_hashes = {name: hashlib.sha256(io.read_bytes(Path(OUTPUT)/name, io.FILE_CAPS[name])).hexdigest()
                   for name in io.FILES}
    reference = modules['source_reference'].reconstruct(data_dir=DATA, **context['documents'], pilot=False)
    baseline = io.read_output(OUTPUT)
    assert validator.verify_artifacts(baseline, reference)['status'] == 'ok'
    boot.recheck_documents(context)
    yield dict(boot=boot, context=context, modules=modules, io=io, validator=validator,
               reference=reference, baseline=baseline)
    boot.recheck_documents(context)
    assert io.output_inventory(OUTPUT) == inventory, 'genuine output inventory changed'
    assert file_hashes == {name: hashlib.sha256(io.read_bytes(Path(OUTPUT)/name, io.FILE_CAPS[name])).hexdigest()
                           for name in io.FILES}, 'genuine output bytes changed'


def properties(record, mode, category, classification='constructed', numeric=0, status=0, gap=None, **details):
    for key, value in dict(control_mode=mode, control_category=category,
            prevalidation_classification=classification, numeric_effect_count=int(numeric),
            status_effect_count=int(status), effect_count=int(numeric + status),
            effect_max_absolute_gap=gap, control_details=json.dumps(details, sort_keys=True)).items():
        record(key, value)


def fresh_candidate(g, path):
    path = g['io'].safe_path(path)
    protected = [Path(DATA), Path(OUTPUT), Path('/tests'), Path('/solution'),
                 *map(Path, g['context']['documents'].values()),
                 *map(Path, g['boot'].PUBLIC_DOCUMENTS.values())]
    if not path.parent.is_dir() or os.path.lexists(path): raise ValueError('fresh_candidate_required')
    if any(path == p or path in p.parents or p in path.parents for p in protected):
        raise ValueError('candidate_protected_overlap')
    path.mkdir(); return path


def retain_candidate(g, actual, path):
    """Exclusively serialize this detached candidate, not the source/baseline."""
    path = fresh_candidate(g, path); io = g['io']
    for name in io.FILES:
        if name not in actual: continue  # Incomplete controls remain incomplete.
        value = actual[name]; destination = path/name
        if name.endswith('.npz'):
            if sum(v.nbytes for v in value.values()) > io.LIMIT: raise ValueError('candidate_array_cap')
            with destination.open('xb') as stream: np.savez_compressed(stream, **value)
        elif name.endswith('.csv'):
            columns = list(value[0]) if value else list(io.CSV_COLUMNS)
            with destination.open('x', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader(); writer.writerows(value)
        else:
            raw = ((json.dumps(value, allow_nan=False, sort_keys=True) + '\n').encode()
                   if name.endswith('.json') else value.encode('utf-8'))
            if len(raw) > io.FILE_CAPS[name]: raise ValueError('candidate_file_cap')
            with destination.open('xb') as stream: stream.write(raw)
        if destination.stat().st_size > io.FILE_CAPS[name]: raise ValueError('candidate_file_cap')
    return path


def require_accept(g, actual, tmp_path, record):
    try:
        assert g['validator'].verify_artifacts(actual, g['reference'])['status'] == 'ok'
    except BaseException:
        record('control_outcome', 'unexpected_positive_rejection')
        retain_candidate(g, actual, tmp_path/'unexpected-positive')
        raise
    record('control_outcome', 'accepted_positive')


def test_genuine_baseline(genuine, record_property):
    properties(record_property, 'baseline', 'genuine')
    assert genuine['reference']['status'] == 'complete'
    record_property('control_outcome', 'accepted_genuine')


@pytest.mark.parametrize('mode', ['coherent_permutations', 'six_decimal_csv_only', 'harmless_representation'])
def test_equivalent_representation(genuine, tmp_path, record_property, mode):
    g = genuine; actual = copy.deepcopy(g['baseline'])
    properties(record_property, mode, 'positive')
    a = actual['signal_evidence.npz']; m = actual['run_metadata.json']
    if mode == 'coherent_permutations':
        frames = np.arange(len(a['frame_indices']))[::-1]; subjects = np.arange(len(a['subject_ids']))[::-1]
        rois = np.arange(len(a['roi_ids']))[::-1]; draws = np.arange(len(a['bootstrap_draw_ids']))[::-1]
        metrics, associations = [2, 0, 1], [1, 0]
        for key in ('frame_indices', 'frame_subject_ids'): a[key] = a[key][frames]
        for key in ('raw_roi', 'cleaned_roi'): a[key] = a[key][frames][:, rois]
        a['canonical_active'] = a['canonical_active'][subjects][:, rois]
        a['subject_ids'] = a['subject_ids'][subjects]; a['roi_ids'] = a['roi_ids'][rois]
        a['bootstrap_metric_ids'] = a['bootstrap_metric_ids'][metrics]
        a['bootstrap_association_ids'] = a['bootstrap_association_ids'][associations]
        for key in ('bootstrap_draw_ids', 'bootstrap_indices', 'bootstrap_motion_nuisance_rank', 'bootstrap_motion_df'):
            a[key] = a[key][draws]
        for key in ('bootstrap_r', 'bootstrap_defined', 'bootstrap_status'):
            a[key] = a[key][draws][:, metrics][:, :, associations]
        # bootstrap_child_ids and bootstrap_indices COLUMNS are deliberately fixed.
        actual['connectivity_metrics.csv'] = [dict(reversed(list(row.items())))
                                              for row in reversed(actual['connectivity_metrics.csv'])]
        for key in ('cohort', 'source_files', 'roi_definitions'): m[key].reverse()
        for key in ('source_observed', 'analysis_observed'): m[key]['persons'].reverse()
        for person in m['source_observed']['persons']:
            for key in ('roi_supports', 'missing_selected_entries', 'mean_fd_missing_entries', 'mean_fd_missing_frame_indices'):
                person[key].reverse()
        for person in m['analysis_observed']['persons']: person['roi_activity'].reverse()
        restriction = actual['age_effects.json']['motion_control']['segregation_low_motion_restriction']
        for key in ('child_ids', 'adult_ids'): restriction[key].reverse()
    elif mode == 'six_decimal_csv_only':
        for row in actual['connectivity_metrics.csv']:
            for key in g['validator'].METRICS:
                if row[key] != '': row[key] = format(float(row[key]), '.6f')
        # Never round source age/FD, primitive series, bootstrap receipts or JSON.
        # The deliberately unchanged inference tests no CSV-rounding cascade.
    else:
        for person in m['source_observed']['persons']:
            dtype = np.dtype(person['bold_header']['storage_dtype'])
            person['bold_header']['storage_dtype'] = dtype.name if dtype.isnative else dtype.str
        m['software_versions'] = {'descriptive_authoring_version': 'not-a-scoring-fingerprint'}
        m['optional_note'] = {'finite_example': 1.25, 'description': 'Harmless extra field'}
        for row in actual['connectivity_metrics.csv']: row['optional_note'] = 'descriptive'
        a['optional_numeric_extra'] = np.asarray([1., 2.])
        actual['findings.md'] = 'Independent interpretation and wording; structured artifacts retain authority.\n'
        candidate = retain_candidate(g, actual, tmp_path/'harmless-representation')
        (candidate/'optional.txt').write_text('Bounded descriptive extra.\n', encoding='utf-8')
        actual = g['io'].read_output(candidate)
    require_accept(g, actual, tmp_path, record_property)


def test_accepted_clean_replay(genuine, tmp_path, record_property):
    g = genuine; ref = g['reference']; sid = 'sub-pixar001'
    active = np.flatnonzero(ref['persons'][sid]['canonical_active'])
    if not len(active):
        properties(record_property, 'tiny_accepted_clean', 'positive', 'unavailable', reason='fixed first subject has no active ROI')
        record_property('control_outcome', 'unavailable')
        pytest.skip('Missing declared first-subject active-support precondition; not a positive pass')
    writer = held_module(WRITER, WRITER_SHA, '_devconn_actual_writer')
    kernel = g['modules']['reporting_kernel']
    accepted, _, _ = g['validator'].canonical_primitives(g['baseline']['signal_evidence.npz'], ref)
    accepted = {key: value.copy() for key, value in accepted.items()}
    roi = int(active[0]); original = accepted[sid][:, roi].copy()
    # One fixed non-affine perturbation. No retries, magnitude search or endpoint target.
    scale = float(np.max(np.abs(original)))
    delta = 1e-10 * scale * np.sin(np.arange(len(original), dtype=np.float64) + .5)
    accepted[sid][:, roi] += delta
    count = int(np.count_nonzero(accepted[sid][:, roi] != original))
    if not count:
        properties(record_property, 'tiny_accepted_clean', 'positive', 'nondiscriminating', reason='fixed perturbation has no representable effect')
        record_property('control_outcome', 'nondiscriminating'); pytest.skip('No representable perturbation, not a positive pass')
    gap = float(np.max(np.abs(accepted[sid][:, roi]-original)))
    candidate = fresh_candidate(g, tmp_path/'accepted-clean-replay')
    try:
        writer.write_artifacts(ref, candidate, kernel, accepted_clean=accepted,
            protected=(DATA, OUTPUT, '/tests', '/solution', *g['context']['documents'].values()))
    except ValueError as exc:
        # Source-close continuous-conditioning guards can make this fixed proposal
        # inadmissible. This is not a production-verifier rejection or a QA pass.
        if str(exc) not in ('clean_pointwise_fidelity', 'clean_centered_fidelity', 'continuous_centered_fidelity'):
            raise
        properties(record_property, 'tiny_accepted_clean', 'positive', 'not_constructed',
                   numeric=count, gap=gap, subject_id=sid, roi_id=ref['roi_ids'][roi])
        record_property('control_outcome', 'not_constructed')
        record_property('construction_guard', str(exc))
        pytest.skip('Fixed proposed signal fails public fidelity; no perturbation retuning')
    actual = g['io'].read_output(candidate)
    own, _, _ = g['validator'].canonical_primitives(actual['signal_evidence.npz'], ref)
    assert np.array_equal(own[sid], accepted[sid]), 'writer changed accepted primitive'
    properties(record_property, 'tiny_accepted_clean', 'positive', numeric=count,
               gap=gap, subject_id=sid, roi_id=ref['roi_ids'][roi])
    # All endpoints are freshly produced from accepted_clean, then the unmodified
    # grader independently replays them. No canonical endpoint equality is asserted.
    require_accept(g, actual, tmp_path, record_property)


NEGATIVES = (
    'zero_signals', 'fabricated_signals', 'wrong_raw', 'wrong_fd', 'wrong_source_hash',
    'wrong_geometry_metadata', 'wrong_cleaning_rank', 'wrong_bootstrap_rank', 'wrong_ci',
    'flipped_defined_mask', 'missing_participant', 'incomplete_bundle', 'permuted_child_order')


def clean_effect(g, actual):
    accepted, reference, active = g['validator'].canonical_primitives(actual['signal_evidence.npz'], g['reference'])
    count, gap = 0, 0.
    kernel = g['modules']['reporting_kernel']
    for sid, value in accepted.items():
        difference = np.abs(value-reference[sid])
        count += int(np.count_nonzero(difference > 1e-7 + 1e-7*np.abs(reference[sid])))
        gap = max(gap, float(np.max(difference)))
        # A source-active column can fail relative fidelity even if pointwise tiny.
        count += sum(kernel.centered_relative_error(value[:, j], reference[sid][:, j]) > 1e-6
                     for j in np.flatnonzero(active[sid]))
    return int(count), gap


@pytest.mark.parametrize('mode', NEGATIVES)
def test_rejection_control(genuine, tmp_path, record_property, mode):
    g = genuine; actual = copy.deepcopy(g['baseline']); a = actual['signal_evidence.npz']
    m = actual['run_metadata.json']; numeric, status, gap = 0, 0, None
    category, reasons = 'binding', ()
    if mode in ('zero_signals', 'fabricated_signals'):
        if mode == 'zero_signals': a['cleaned_roi'][:] = 0.
        else: a['cleaned_roi'][:] = np.where(np.arange(len(a['frame_indices']))[:, None] % 2, .25, -.25)
        numeric, gap = clean_effect(g, actual); category = 'numerical'
        reasons = ('clean_pointwise_fidelity', 'clean_centered_fidelity')
    elif mode == 'wrong_raw':
        old = float(a['raw_roi'].flat[0]); new = old + max(1., abs(old))*.01 + 1.
        a['raw_roi'].flat[0] = new; numeric, gap = 1, abs(new-old)
        category, reasons = 'numerical', ('numeric_array_tolerance',)
    elif mode == 'wrong_fd':
        row = actual['connectivity_metrics.csv'][0]; old = float(row['mean_fd'])
        row['mean_fd'] = repr(old + 1.); numeric, gap = 1, 1.
        category, reasons = 'numerical', ('numeric_tolerance',)
    elif mode in ('wrong_source_hash', 'wrong_geometry_metadata'):
        obj, key = (m, 'source_manifest_sha256') if mode == 'wrong_source_hash' else (
            m['source_observed']['persons'][0]['roi_supports'][0], 'support_sha256')
        value = obj[key]; obj[key] = ('0' if value[0] != '0' else '1') + value[1:]
        status, reasons = 1, ('exact_string',)
    elif mode == 'wrong_cleaning_rank':
        m['analysis_observed']['persons'][0]['cleaning_rank'] += 1
        status, reasons = 1, ('exact_integer',)
    elif mode == 'wrong_bootstrap_rank':
        old = int(a['bootstrap_motion_nuisance_rank'][0]); new = 2 if old == 1 else 1
        a['bootstrap_motion_nuisance_rank'][0] = new; a['bootstrap_motion_df'][0] = 122-new-1
        status, reasons, category = 2, ('bootstrap_rank_or_df',), 'numerical'
    elif mode == 'wrong_ci':
        record = actual['age_effects.json']['children_age_spearman']['short_range']['raw_bootstrap']
        old = record['ci95']
        if old is None:
            record['ci95'] = [-.25, .25]; status, reasons = 1, ('required_null',)
        else:
            record['ci95'] = [-1., -.9] if old[0] >= 0 else [.9, 1.]
            differences = [abs(x-y) for x, y in zip(record['ci95'], old)]
            gap = max(differences)
            numeric = sum(difference > 1e-6 + 1e-6*abs(value)
                          for difference, value in zip(differences, old))
            reasons = ('numeric_tolerance',)
        category = 'numerical'
    elif mode == 'flipped_defined_mask':
        a['bootstrap_defined'][0, 0, 0] = not bool(a['bootstrap_defined'][0, 0, 0])
        status, reasons, category = 1, ('bootstrap_support',), 'numerical'
    elif mode == 'missing_participant':
        actual['connectivity_metrics.csv'].pop(); status, reasons = 1, ('record_membership',)
    elif mode == 'incomplete_bundle':
        del actual['age_effects.json']; status, reasons = 1, ('required_object_fields',)
    else:
        a['bootstrap_child_ids'] = a['bootstrap_child_ids'][::-1]
        status, reasons = len(a['bootstrap_child_ids']), ('fixed_bootstrap_child_order',)
    classification = 'effective' if numeric + status else 'nondiscriminating'
    properties(record_property, mode, category, classification, numeric, status, gap,
        isolation='deliberately wrong component; other receipts are not recomputed', expected_reasons=reasons)
    if not numeric + status:
        record_property('control_outcome', 'nondiscriminating')
        pytest.skip('Mutation does not violate a public numerical/support bound; not a rejection pass')
    try:
        g['validator'].verify_artifacts(actual, g['reference'])
    except ValueError as exc:
        if str(exc) not in reasons:
            record_property('control_outcome', 'unexpected_rejection_reason')
            retain_candidate(g, actual, tmp_path/'unexpected-rejection')
            raise
        record_property('rejection_reason', str(exc))
        record_property('control_outcome', 'effective_' + category + '_rejection')
    else:
        record_property('control_outcome', 'unexpected_acceptance')
        retain_candidate(g, actual, tmp_path/'unexpected-acceptance')
        pytest.fail('Effective control accepted by unmodified validator')


def test_authoritative_failure_marker(genuine, tmp_path, record_property):
    properties(record_property, 'failure_marker', 'binding', 'effective', status=1)
    output = fresh_candidate(genuine, tmp_path/'marked-output')
    with (output/'failure_report.json').open('x', encoding='utf-8') as stream:
        stream.write('{"status":"manufactured_failure"}\n')
    with pytest.raises(ValueError, match='^failed_run_marker$'): genuine['io'].read_output(output)
    record_property('control_outcome', 'effective_binding_rejection')
