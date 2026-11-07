"""Protected prospective grading adapter; no file/data reads or work on import.

Every candidate panel is admitted before operator baseline capture, and the
baseline is pinned and admitted before any private response callback. OS custody
and scientific qualification belong to the trusted parent controller.
"""
import importlib.util
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location('_spatial_grade_contracts', Path(__file__).with_name('contracts.py'))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)


def _native_parameters(native, n):
    C.need(type(native) is dict and set(native) == set(C.ROLES), 'three verified native parameter roles')
    for role in C.ROLES:
        a = native[role]
        C.need(type(a) is np.ndarray and a.dtype == np.dtype('float64')
               and a.shape == (n, 5), 'native five-parameter source conversion')
        C.need(np.all(np.isfinite(a).all(axis=1) | np.isnan(a).all(axis=1)),
               'native rows finite or explicit all-NaN unavailable conversion')


def _private_person(value, person):
    pid = person['participant']; n = len(person['electrode_ids'])
    C.need(type(value) is dict and set(value) == {'participant', 'signals', 'references'}
           and value['participant'] == pid, 'exact operator private participant')
    signals, references = value['signals'], value['references']
    C.need(type(signals) is dict and set(signals) == set(C.S.protocol.SIGNALS), 'complete private signals')
    keys = {C.S.protocol.condition_key(*condition) for condition in C.S.protocol.CONDITIONS}
    C.need(type(references) is dict and set(references) == keys, 'complete eight private references')
    for signal, row in signals.items():
        C.need(type(row) is dict and set(row) == {'responses', 'aperture'}, 'exact private signal fields')
        y, a = row['responses'], row['aperture']
        C.source_responses(y, (n, 75))
        C.need(type(a) is np.ndarray and a.dtype == np.dtype('float64') and a.shape == (100, 100, 75), 'full source aperture')
        C.need(np.isfinite(a).all(), 'signed finite aperture')
    for key, ref in references.items():
        C.need(type(ref) is dict and set(ref) == {'published_xval_percent', 'native_branch_verification', 'native_parameters'}, 'exact private reference fields')
        published = ref['published_xval_percent']
        C.need(type(published) is np.ndarray and published.dtype == np.dtype('float64')
               and published.shape == (n,), 'all saved published scores; source nonfinites remain unavailable')
        status = ref['native_branch_verification']
        C.need(status in ('verified', 'unverified'), 'explicit native gain branch provenance')
        native = ref['native_parameters']
        if status == 'unverified':
            C.need(native is None, 'no native parameters without verified gain branch')
        else:
            _native_parameters(native, n)
    return value


def _metric(result, metric):
    row = result.get(metric)
    return row.get('value_percent') if row else None


def _aggregate_metric(rows, reports, persons, field, metric):
    expected = {p['participant']: p['electrode_ids'] for p in persons}
    out = {}
    for condition in C.S.protocol.CONDITIONS:
        key = C.S.protocol.condition_key(*condition)
        values = {p: {} for p in C.S.protocol.PARTICIPANTS}
        for row in rows:
            if (row['signal'], row['model'], row['allow_negative_gain']) != condition:
                continue
            result = reports[row['case_id']].get(field)
            values[row['participant']][row['electrode_id']] = _metric(result, metric) if result else None
        out[key] = C.S.metrics.aggregate_participants(values, expected)
    return out


def grade_panels(candidate_raw_by_panel, persons, roster_sha256, *,
                 capture_operator_baseline, expected_baseline_pin, load_person):
    """Return complete summaries and private per-case dispositions, never qualification.

    candidate_raw_by_panel contains exactly four bounded byte payloads. The
    baseline callback returns one sealed complete parameter-panel byte payload;
    its output pin is sealed by the operator before protected grading. The
    operator algorithm/source and budget are frozen before candidate exposure;
    baseline execution may occur later. A payload pin alone proves no chronology.
    load_person
    returns the exact ABI in README.md, never candidate-chosen baseline scores.
    """
    rows = C.full_roster(persons)
    C.need(type(candidate_raw_by_panel) is dict and set(candidate_raw_by_panel) == set(C.PANELS), 'all four candidate arms')
    # Admission of the last case in the last panel precedes both callbacks.
    candidates = {name: C.admit_panel(candidate_raw_by_panel[name], rows, roster_sha256) for name in C.PANELS}
    C.need(type(expected_baseline_pin) is dict and set(expected_baseline_pin) == {'bytes', 'sha256'}
           and type(expected_baseline_pin['bytes']) is int
           and 0 < expected_baseline_pin['bytes'] <= C.S.interface.MAX_BYTES
           and C.S.interface._sha(expected_baseline_pin['sha256']), 'operator baseline pin sealed before grading')
    baseline_raw = capture_operator_baseline()
    C.need(type(baseline_raw) is bytes and C.pin(baseline_raw) == expected_baseline_pin, 'sealed independent operator baseline identity')
    baseline = C.admit_panel(baseline_raw, rows, roster_sha256)
    baseline_by = {r['case_id']: r for r in baseline['cases']}
    candidate_by = {p: {r['case_id']: r for r in doc['cases']} for p, doc in candidates.items()}
    reports = {name: {} for name in C.PANELS}
    native_provenance = {}
    for person in persons:
        pid = person['participant']; private = _private_person(load_person(pid), person)
        native_provenance[pid] = {k: v['native_branch_verification'] for k, v in private['references'].items()}
        for row in C.context_rows(rows, pid):
            ident = row['case_id']; i = person['electrode_ids'].index(row['electrode_id'])
            signal = private['signals'][row['signal']]
            ref = private['references'][C.S.protocol.condition_key(row['signal'], row['model'], row['allow_negative_gain'])]
            y, aperture = signal['responses'][i], signal['aperture']
            kwargs = {'model': row['model'], 'sign_free': row['allow_negative_gain']}
            operator = C.S.score_core.score_case(y, aperture, baseline_by[ident], **kwargs)
            native = None
            native_available = (ref['native_branch_verification'] == 'verified'
                and all(np.isfinite(ref['native_parameters'][role][i]).all() for role in C.ROLES))
            if native_available:
                parameters = {role: C.S.interface._parameters(ref['native_parameters'][role][i].tolist(), row) for role in C.ROLES}
                native = C.S.score_core.score_case(y, aperture, parameters, **kwargs)
            published = float(ref['published_xval_percent'][i])
            published = published if np.isfinite(published) else None
            for panel in C.PANELS:
                candidate = C.S.score_core.score_case(y, aperture, candidate_by[panel][ident], **kwargs)
                reports[panel][ident] = {'candidate': candidate, 'baseline': native,
                    'operator_baseline': operator, 'published_xval_percent': published,
                    'native_branch_verification': ref['native_branch_verification'],
                    'native_parameter_conversion_available': native_available}
    summaries = {}
    for panel in C.PANELS:
        saved = C.S.score_core.aggregate(rows, reports[panel], persons)
        # This is descriptive artifact reconstruction only; its historical seed
        # leakage and unknown native branch cannot become corrected improvement.
        saved['primary_model_comparison'] = 'descriptive native parameter comparison only; never a training-only improvement claim'
        source_candidate = _aggregate_metric(rows, reports[panel], persons, 'candidate', 'source_cv')
        source_operator = _aggregate_metric(rows, reports[panel], persons, 'operator_baseline', 'source_cv')
        literal_candidate = _aggregate_metric(rows, reports[panel], persons, 'candidate', 'literal_eq6')
        literal_operator = _aggregate_metric(rows, reports[panel], persons, 'operator_baseline', 'literal_eq6')
        corrected = {}
        for key in source_candidate:
            mean = 'prospective_equal_person_mean_percent'
            corrected[key] = {'source_formula_candidate': source_candidate[key],
                'source_formula_operator': source_operator[key],
                'source_formula_gain_pp': C.S.score_core.difference(source_candidate[key].get(mean), source_operator[key].get(mean)),
                'literal_eq6_candidate': literal_candidate[key], 'literal_eq6_operator': literal_operator[key],
                'literal_eq6_gain_pp': C.S.score_core.difference(literal_candidate[key].get(mean), literal_operator[key].get(mean))}
        summaries[panel] = {'saved_artifact_reconstruction': saved,
            'corrected_training_only_comparison': corrected if panel.startswith('corrected_') else None,
            'operator_profile': C.PROFILE, 'training_isolation_proven_by_artifact': False}
    return {'schema': 'visual_alpha_complete_spatial_report_v1', 'panels': summaries,
            'private_cases': reports, 'native_branch_provenance': native_provenance,
            'operator_baseline_pin': expected_baseline_pin,
            'primary_corrected_endpoint': 'corrected_alpha__GS__positive_gain source_formula_gain_pp',
            'secondary_literal_endpoint': 'corrected_alpha__GS__positive_gain literal_eq6_gain_pp; different formula',
            'case_count_per_panel': 3464, 'native_electrodes': 433, 'participants': 9,
            'candidate_controlled_baseline_allowed': False, 'scientific_qualification': False,
            'full_paper_reproduction': False, 'historical_366_selection_reproduced': False,
            'native_matlab_parity': False, 'arbitrary_pass_threshold': None}
