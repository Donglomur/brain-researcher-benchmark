"""Manufactured FCMATUR output validation only; no original source or bank."""
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import types

import numpy as np
import pytest

import output_contract as c


def reference_fixture(*, mode='ordinary', ledger_count=20):
    ids = [f'Toy_{i + 1:07d}' for i in range(18)]
    rows, persons, ledger, files = [], {}, [], []
    for i, sid in enumerate(ids):
        site = ('A', 'B', 'C')[i // 6]
        age = float(10 + i % 6 + 3 * (i // 6))
        value = .01 * i + .05 * math.sin(i * 1.73)
        if mode == 'constant': value = .2
        if mode == 'undefined': value = None
        if mode == 'perfect': value = age / 100
        if mode == 'cap': value = math.atanh(.999)
        if mode == 'mixed' and i == 0: value = None
        normalized = dict(age=age, site_id=site, sex=1 + i % 2, dx_group=1 + i % 2,
                          mean_fd=None if i == 3 else .1 + (i % 4) * .01,
                          typical_control=bool(i % 2))
        statuses = {key: ('missing' if val is None else 'ok') for key, val in normalized.items()
                    if key != 'typical_control'}
        tokens = dict(AGE_AT_SCAN=str(age), SITE_ID=site, SEX=str(normalized['sex']),
                      DX_GROUP=str(normalized['dx_group']),
                      func_mean_fd='' if normalized['mean_fd'] is None else str(normalized['mean_fd']))
        path = f'roi/{sid}_rois_cc200.1D'
        n_active = 1 if value is None else 3
        person = dict(source_path=path, source_sha256=hashlib.sha256(sid.encode()).hexdigest(),
                      subject_id=str(i + 1), phenotype_row_index=i, n_frames=32, n_columns=4,
                      header_sha256='a' * 64, source_column_ids=[1, 2, 3, 4], all_finite=True,
                      active_columns=[j < n_active for j in range(4)],
                      exact_constant_columns=list(range(n_active + 1, 5)), n_active_columns=n_active,
                      n_edges=n_active * (n_active - 1) // 2, connectivity=value,
                      status='insufficient_active_columns' if value is None else 'ok')
        persons[sid] = person
        rows.append(dict(subject=sid, connectivity=value, **{k: normalized[k] for k in
                    ('age', 'site_id', 'mean_fd', 'sex', 'typical_control')}))
        ledger.append(dict(phenotype_row_index=i, subject_id=str(i + 1), source_subject_id_token=f'{i+1:07d}',
                           file_id=sid, source_availability='released_filename', source_path=path,
                           tokens=tokens, normalized=normalized, covariate_status=statuses))
        files.append(dict(path=path, role='roi_timeseries', size_bytes=100 + i,
                          sha256=person['source_sha256'], subject_id=str(i + 1), file_id=sid,
                          phenotype_row_index=i))
    for i in range(len(ids), ledger_count):
        ledger.append(dict(phenotype_row_index=i, subject_id=str(i + 1), source_subject_id_token=str(i + 1),
                           file_id='no_filename', source_availability='no_filename', source_path=None,
                           tokens=dict(AGE_AT_SCAN='', SITE_ID='', SEX='', DX_GROUP='', func_mean_fd=''),
                           normalized=dict(age=None, site_id=None, sex=None, dx_group=None,
                                           mean_fd=None, typical_control=None),
                           covariate_status={k: 'missing' for k in ('age', 'site_id', 'sex', 'dx_group', 'mean_fd')}))
    files.extend([dict(path='phenotype.csv', role='phenotype', size_bytes=123, sha256='b' * 64),
                  dict(path='provenance/notice.rst', role='provenance_abide_notice', size_bytes=42, sha256='c' * 64)])
    columns = ['', 'SUB_ID', 'FILE_ID', 'AGE_AT_SCAN', 'SITE_ID', 'SEX', 'DX_GROUP', 'func_mean_fd']
    observed = dict(n_source_files=len(files), source_bytes=sum(r['size_bytes'] for r in files),
                    n_phenotype_rows=len(ledger), n_no_filename=len(ledger) - len(ids), total_frames=32 * len(ids),
                    phenotype_columns=columns, source_column_ids=[1, 2, 3, 4], persons={
                        sid: {k: persons[sid][k] for k in ('n_frames', 'n_columns', 'header_sha256', 'all_finite',
                              'active_columns', 'exact_constant_columns', 'n_active_columns', 'n_edges')} for sid in ids})
    return dict(status='complete', participant_ids=ids, canonical_rows=rows, persons=persons,
                phenotype_ledger=ledger, phenotype_columns=columns, source_files=files,
                source_observed=observed, pins=dict(c.PINS))


def documents(reference, accepted=None):
    kernel = c.load_kernel()
    if accepted is None:
        accepted = {r['subject']: r['connectivity'] for r in reference['canonical_rows']}
    replay = kernel.analyze(reference['canonical_rows'], accepted)
    primary, sensitivity = c.public_statistics(replay)
    membership = {row['subject']: row for row in replay['cohort']}
    phenotypes = {row['file_id']: row for row in reference['phenotype_ledger']
                  if row['source_availability'] == 'released_filename'}
    table = []
    for sid in reference['participant_ids']:
        p, ph, m = reference['persons'][sid], phenotypes[sid], membership[sid]
        row = dict(FILE_ID=sid, connectivity=accepted[sid], connectivity_status=p['status'],
                   **{k: ph['normalized'][k] for k in ('age', 'site_id', 'sex', 'dx_group', 'mean_fd')},
                   **{k + '_status': v for k, v in ph['covariate_status'].items()},
                   **{k: p[k] for k in ('n_frames', 'n_columns', 'n_active_columns', 'n_edges')},
                   **{k: m[k] for k in (*c.FLAGS, 'base_reason')})
        table.append({k: '' if v is None else str(v).lower() if type(v) is bool else str(v)
                      for k, v in row.items()})
    metadata = dict(schema_version='fcmatur-metadata-v3', status='complete', task_id='FCMATUR-001',
                    pins=copy.deepcopy(reference['pins']), source_files=copy.deepcopy(reference['source_files']),
                    phenotype_ledger=copy.deepcopy(reference['phenotype_ledger']),
                    source_observed=copy.deepcopy(reference['source_observed']),
                    software=dict(python='manufactured', numpy='different-version', scipy='not-a-fingerprint'))
    return {'connectivity.csv': table, 'connectivity_age.json': primary,
            'sensitivity.json': sensitivity, 'run_metadata.json': metadata,
            'findings.md': 'A manufactured example without a required scientific direction.'}


def emit(path, docs):
    path.mkdir()
    for name, data in docs.items():
        if name.endswith('.csv'):
            fields = list(data[0]) if data else list(c.CSV_COLUMNS)
            with (path / name).open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader(); writer.writerows(data)
        elif name.endswith('.json'):
            (path / name).write_text(json.dumps(data, allow_nan=False))
        else:
            (path / name).write_text(data)
    return path


@pytest.fixture
def example():
    reference = reference_fixture()
    return reference, documents(reference)


def reject(tmp_path, reference, docs, pattern=None):
    with pytest.raises((ValueError, TypeError), match=pattern):
        c.validate(emit(tmp_path / 'output', docs), reference)


def test_genuine_all_three_levels_and_five_sensitivities(tmp_path, example):
    ref, docs = example
    assert set(docs['sensitivity.json']['checks']) == {'motion', 'diagnosis', 'sex', 'nonlinear_age', 'site_specific_slopes'}
    assert c.validate(emit(tmp_path / 'output', docs), ref)['n_source'] == 18


@pytest.mark.parametrize('mode', ['constant', 'undefined', 'mixed', 'perfect', 'cap'])
def test_legitimate_undefined_perfect_and_cap_cases(tmp_path, mode):
    ref = reference_fixture(mode=mode)
    assert c.validate(emit(tmp_path / 'output', documents(ref)), ref)['status'] == 'accepted'


def test_entire_1112_row_provenance_ledger(tmp_path):
    ref = reference_fixture(ledger_count=1112)
    assert c.validate(emit(tmp_path / 'output', documents(ref)), ref)['status'] == 'accepted'


def test_coherent_permutations_and_benign_extras(tmp_path, example):
    ref, docs = example
    docs['connectivity.csv'].reverse()
    for row in docs['connectivity.csv']: row['interpretation'] = 'extra text'
    def reorder(value):
        if isinstance(value, dict):
            value['extra_note'] = 'not a correctness target'
            for key, child in list(value.items()):
                if key in {'ids', 'eligible_site_ids', 'source_files', 'phenotype_ledger',
                           'site_means', 'per_site', 'exact_constant_columns'}:
                    child.reverse()
                if key not in {'persons', 'site_counts', 'all_base_site_counts'}:
                    reorder(child)
                elif isinstance(child, dict):
                    for record in child.values():
                        if isinstance(record, dict): reorder(record)
        elif isinstance(value, list):
            for child in value: reorder(child)
    for name in ('connectivity_age.json', 'sensitivity.json', 'run_metadata.json'): reorder(docs[name])
    out = emit(tmp_path / 'output', docs)
    (out / 'additional.txt').write_text('Benign small extra artifact.')
    assert c.validate(out, ref)['status'] == 'accepted'


def test_six_decimal_derived_receipts_not_downstream_inputs(tmp_path, example):
    ref, docs = example
    def rounded(value):
        if type(value) is float: return round(value, 6)
        if type(value) is list: return [rounded(v) for v in value]
        if type(value) is dict: return {k: rounded(v) for k, v in value.items()}
        return value
    for name in ('connectivity_age.json', 'sensitivity.json'): docs[name] = rounded(docs[name])
    assert c.validate(emit(tmp_path / 'output', docs), ref)['status'] == 'accepted'


def test_integral_numeric_receipts_and_csv_boolean_spellings(tmp_path, example):
    ref, docs = example
    def ints_to_floats(value):
        if type(value) is int: return float(value)
        if type(value) is list: return [ints_to_floats(v) for v in value]
        if type(value) is dict: return {k: ints_to_floats(v) for k, v in value.items()}
        return value
    for name in ('connectivity_age.json', 'sensitivity.json', 'run_metadata.json'):
        docs[name] = ints_to_floats(docs[name])
    for row in docs['connectivity.csv']:
        row['sex'] = row['sex'] + 'e0'
        for key in c.FLAGS: row[key] = 'TRUE' if row[key] == 'true' else '0'
    assert c.validate(emit(tmp_path / 'output', docs), ref)['status'] == 'accepted'


def test_optional_diagnostics_are_not_additional_acceptance_gates(tmp_path, example):
    ref, docs = example
    for name in ('pooled', 'within_site', 'between_site'):
        docs['connectivity_age.json'][name]['age_support']['arbitrary_diagnostic'] = 'unscored'
    quadratic = docs['sensitivity.json']['checks']['nonlinear_age']
    quadratic.update(added_norm=0, added_cutoff=100, added_basis_orthogonality='optional diagnostic')
    assert c.validate(emit(tmp_path / 'output', docs), ref)['status'] == 'accepted'


def test_source_close_own_values_drive_all_downstream_once(tmp_path):
    ref = reference_fixture()
    accepted = {r['subject']: r['connectivity'] * (1 + 2e-7) + 2e-7 for r in ref['canonical_rows']}
    own = documents(ref, accepted)
    baseline = documents(ref)
    assert own['connectivity_age.json']['site_means'] != baseline['connectivity_age.json']['site_means']
    assert c.validate(emit(tmp_path / 'output', own), ref)['status'] == 'accepted'


def test_float32_fisher_cap_serialization(tmp_path):
    ref = reference_fixture(mode='cap')
    accepted = {r['subject']: float(np.float32(r['connectivity'])) for r in ref['canonical_rows']}
    assert c.validate(emit(tmp_path / 'output', documents(ref, accepted)), ref)['status'] == 'accepted'


def test_source_close_but_conditioning_breaking_values_fail(tmp_path):
    ref = reference_fixture()
    for i, row in enumerate(ref['canonical_rows']):
        row['connectivity'] = 1e-9 * math.sin(i + .2)
        ref['persons'][row['subject']]['connectivity'] = row['connectivity']
    docs = documents(ref)
    before = float(docs['connectivity.csv'][0]['connectivity'])
    docs['connectivity.csv'][0]['connectivity'] = str(before + 1e-8)
    # Well inside the pointwise allowance, but far outside the declared
    # relative fidelity on this manufactured small active source direction.
    assert abs(float(docs['connectivity.csv'][0]['connectivity']) - before) < 1e-6
    reject(tmp_path, ref, docs, 'fidelity')


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'digit_alias', 'extra', 'bool_number',
                                 'text_null', 'float_count', 'negative_fd', 'invalid_age', 'fractional_sex',
                                 'wrong_status', 'wrong_support', 'wrong_eligible', 'wrong_reason',
                                 'source_value', 'null_defined'])
def test_csv_binding_and_typing_failures(tmp_path, example, fault):
    ref, docs = example
    rows = docs['connectivity.csv']; row = rows[0]
    if fault == 'missing': rows.pop()
    elif fault == 'duplicate': rows[-1] = dict(row)
    elif fault == 'digit_alias': row['FILE_ID'] = row['FILE_ID'].split('_')[-1]
    elif fault == 'extra': rows.append(dict(row, FILE_ID='alien'))
    elif fault == 'bool_number': row['connectivity'] = 'true'
    elif fault == 'text_null': rows[3]['mean_fd'] = 'null'
    elif fault == 'float_count': row['n_edges'] = '3.5'
    elif fault == 'negative_fd': row['mean_fd'] = '-1e-12'
    elif fault == 'invalid_age': row['age'] = '0'
    elif fault == 'fractional_sex': row['sex'] = '1.0000000001'
    elif fault == 'wrong_status': row['age_status'] = 'missing'
    elif fault == 'wrong_support': row['n_active_columns'] = '4'
    elif fault == 'wrong_eligible': row['base_eligible'] = 'false'
    elif fault == 'wrong_reason': row['base_reason'] = 'excluded'
    elif fault == 'source_value': row['connectivity'] = '0.9'
    elif fault == 'null_defined': row['connectivity'] = ''
    reject(tmp_path, ref, docs)


@pytest.mark.parametrize('fault', ['bool_count', 'bool_real', 'numeric_string', 'fractional_rank',
                                 'ids_alias', 'ids_duplicate', 'ids_missing', 'column_order',
                                 'extra_site_count', 'support', 'false_null', 'wrong_r', 'wrong_p', 'wrong_ci'])
def test_primary_wrong_statistics_or_types(tmp_path, example, fault):
    ref, docs = example
    primary = docs['connectivity_age.json']; row = primary['pooled']
    if fault == 'bool_count': primary['n_source'] = True
    elif fault == 'bool_real': row['r'] = False
    elif fault == 'numeric_string': row['r'] = str(row['r'])
    elif fault == 'fractional_rank': row['rank'] = 1.1
    elif fault == 'ids_alias': row['ids'][0] = '0000001'
    elif fault == 'ids_duplicate': row['ids'][-1] = row['ids'][0]
    elif fault == 'ids_missing': row['ids'].pop()
    elif fault == 'column_order': primary['within_site']['column_ids'].reverse()
    elif fault == 'extra_site_count': primary['all_base_site_counts']['alien'] = 0
    elif fault == 'support': row['connectivity_support']['active'] = False
    elif fault == 'false_null': row['r'] = None
    elif fault == 'wrong_r': row['r'] = -row['r']
    elif fault == 'wrong_p': row['p'] = 0.7
    elif fault == 'wrong_ci': row['ci95'].reverse()
    reject(tmp_path, ref, docs)


@pytest.mark.parametrize('fault', ['missing_check', 'missing_site', 'duplicate_site', 'wrong_slope',
                                 'wrong_gain', 'wrong_F', 'false_rank', 'wrong_sign_count',
                                 'drop_adjusted_member', 'support_bool_number'])
def test_sensitivity_complete_replay_failures(tmp_path, example, fault):
    ref, docs = example
    checks = docs['sensitivity.json']['checks']
    quadratic = checks['nonlinear_age']; per_site = checks['site_specific_slopes']
    if fault == 'missing_check': del checks['sex']
    elif fault == 'missing_site': per_site['per_site'].pop()
    elif fault == 'duplicate_site': per_site['per_site'].append(copy.deepcopy(per_site['per_site'][0]))
    elif fault == 'wrong_slope': per_site['per_site'][0]['slope'] += .1
    elif fault == 'wrong_gain': quadratic['gain_ss'] += .1
    elif fault == 'wrong_F': quadratic['F_added_quadratic'] = 10.
    elif fault == 'false_rank': quadratic['full_rank'] += 1
    elif fault == 'wrong_sign_count': per_site['n_sites_positive'] += 1
    elif fault == 'drop_adjusted_member': checks['diagnosis']['ids'].pop()
    elif fault == 'support_bool_number': quadratic['full_residual_support']['active'] = 1
    reject(tmp_path, ref, docs)


@pytest.mark.parametrize('fault', ['pin', 'source_swap', 'source_missing', 'source_extra', 'source_bool_size',
                                 'ledger_missing', 'ledger_duplicate_index', 'token', 'normalized',
                                 'subject_alias', 'status', 'active_bool', 'constant_duplicate',
                                 'column_order', 'phenotype_order', 'extra_person', 'software_empty'])
def test_full_metadata_source_binding_failures(tmp_path, example, fault):
    ref, docs = example
    m = docs['run_metadata.json']; row = m['phenotype_ledger'][0]
    person = m['source_observed']['persons'][ref['participant_ids'][0]]
    if fault == 'pin': m['pins']['source_manifest_sha256'] = '0' * 64
    elif fault == 'source_swap': m['source_files'][0]['sha256'] = m['source_files'][1]['sha256']
    elif fault == 'source_missing': m['source_files'].pop()
    elif fault == 'source_extra': m['source_files'].append(dict(m['source_files'][0], path='extra'))
    elif fault == 'source_bool_size': m['source_files'][0]['size_bytes'] = True
    elif fault == 'ledger_missing': m['phenotype_ledger'].pop()
    elif fault == 'ledger_duplicate_index': m['phenotype_ledger'][1]['phenotype_row_index'] = 0.0
    elif fault == 'token': row['tokens']['AGE_AT_SCAN'] = '10.000'
    elif fault == 'normalized': row['normalized']['mean_fd'] += .01
    elif fault == 'subject_alias': row['subject_id'] = row['source_subject_id_token']
    elif fault == 'status': row['covariate_status']['mean_fd'] = 'missing'
    elif fault == 'active_bool': person['active_columns'][0] = 1
    elif fault == 'constant_duplicate': person['exact_constant_columns'] *= 2
    elif fault == 'column_order': m['source_observed']['source_column_ids'].reverse()
    elif fault == 'phenotype_order': m['source_observed']['phenotype_columns'].reverse()
    elif fault == 'extra_person': m['source_observed']['persons']['extra'] = copy.deepcopy(person)
    elif fault == 'software_empty': m['software']['python'] = ' '
    reject(tmp_path, ref, docs)


@pytest.mark.parametrize('key,value', [('r', 1.0000001), ('p', -5e-7), ('p', 1.0000001)])
def test_scalar_domain_independent_of_tolerance(key, value):
    expected = 1.0 if value > 1 else 0.0
    with pytest.raises(ValueError, match='domain'):
        c.match(value, expected, 'scalar', key=key)


@pytest.mark.parametrize('key', ['F_added_quadratic', 'gain_ss', 'rss_linear', 'rss_quadratic', 'mean_fd'])
def test_negative_near_zero_nonnegative_receipts_fail(key):
    with pytest.raises(ValueError, match='domain'):
        c.match(-5e-7, 0.0, 'scalar', key=key)
    c.match(0.0, 0.0, 'scalar', key=key)


def test_inactive_support_cannot_be_reactivated_by_jitter(tmp_path):
    ref = reference_fixture(mode='constant')
    accepted = {r['subject']: r['connectivity'] + (i % 2) * 1e-7 for i, r in enumerate(ref['canonical_rows'])}
    docs = documents(ref, accepted)
    assert docs['connectivity_age.json']['pooled']['r'] is None
    docs['connectivity_age.json']['pooled']['r'] = 0.0
    reject(tmp_path, ref, docs, 'required null')


def test_private_kernel_ignores_public_or_cached_module(tmp_path, example, monkeypatch):
    ref, docs = example
    poison = types.ModuleType('statistics_kernel')
    poison.analyze = lambda *a, **k: pytest.fail('untrusted public kernel used')
    monkeypatch.setitem(sys.modules, 'statistics_kernel', poison)
    private_name = '_fcmatur_held_kernel_' + c.KERNEL_SHA
    monkeypatch.setitem(sys.modules, private_name, poison)
    (tmp_path / 'statistics_kernel.py').write_text('raise RuntimeError("untrusted cwd")')
    monkeypatch.chdir(tmp_path)
    assert c.validate(emit(tmp_path / 'output', docs), ref)['status'] == 'accepted'
    assert sys.modules[private_name] is poison


def test_private_kernel_tamper_fails_before_execution(tmp_path, monkeypatch):
    marker = tmp_path / 'ran'
    (tmp_path / 'statistics_kernel.py').write_text(f'open({str(marker)!r}, "w").write("bad")')
    monkeypatch.setattr(c, '__file__', str(tmp_path / 'output_contract.py'))
    with pytest.raises(ValueError, match='private kernel digest'): c.load_kernel()
    assert not marker.exists()


@pytest.mark.parametrize('kind', ['empty', 'dangling', 'directory'])
def test_failure_marker_always_authoritative(tmp_path, example, kind):
    ref, docs = example
    out = emit(tmp_path / 'output', docs)
    marker = out / 'failure_report.json'
    if kind == 'empty': marker.touch()
    elif kind == 'dangling': marker.symlink_to(out / 'absent')
    else: marker.mkdir()
    with pytest.raises(ValueError, match='failure_report'): c.validate(out, ref)


def test_late_failure_marker_after_replay(tmp_path, example, monkeypatch):
    ref, docs = example
    out = emit(tmp_path / 'output', docs)
    original = c.load_kernel
    def loader():
        kernel = original()
        analyze = kernel.analyze
        def late(*args, **kwargs):
            result = analyze(*args, **kwargs)
            (out / 'failure_report.json').touch()
            return result
        kernel.analyze = late
        return kernel
    monkeypatch.setattr(c, 'load_kernel', loader)
    with pytest.raises(ValueError, match='failure_report'): c.validate(out, ref)


def test_revalidation_does_not_cache_acceptance(tmp_path, example):
    ref, docs = example
    out = emit(tmp_path / 'output', docs)
    assert c.validate(out, ref)['status'] == 'accepted'
    primary = docs['connectivity_age.json']; primary['pooled']['r'] = None
    (out / 'connectivity_age.json').write_text(json.dumps(primary))
    with pytest.raises(ValueError): c.validate(out, ref)


@pytest.mark.parametrize('fault', ['pin', 'status'])
def test_untrusted_incomplete_reference_rejected(tmp_path, example, fault):
    ref, docs = example
    if fault == 'pin': ref['pins']['method_contract_sha256'] = '0' * 64
    else: ref['status'] = 'partial'
    reject(tmp_path, ref, docs)


def test_module_does_not_import_original_reconstruction_or_public_kernel():
    text = Path(c.__file__).read_text()
    assert 'import source_reference' not in text
    assert 'import statistics_kernel' not in text
    assert '/app/statistics_kernel.py' not in text
