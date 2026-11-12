"""Two-artifact admission and actual guarded numerical/claim grading."""
import collections
import json
import math
from pathlib import Path
import types
import claims
import common as c
import guard
import report_contract

SCOPE = {'recordings': 47, 'participants': 41,
         'area_recordings': {'A1': 39, 'A2': 8}, 'conditions': 8}
OUTPUT_CAPS = {'report.json': 64000000, 'claims.json': 1000000}


def roster_admit(roster):
    guard.validate_roster(roster, ValueError)
    c.need(dict(collections.Counter(row['area'] for row in roster)) == SCOPE['area_recordings'],
           'Exact released39A1/eightA2 scope, not paper relabeling')


def closure_admit(value, source, artifacts):
    keys = {'schema', 'task_id', 'source', 'program', 'scope', 'artifacts',
            'native_record', 'view_retirement', 'producer_natural_exit',
            'producer_resources_closed', 'producer_closed_before_capture',
            'cli_groups_reaped', 'all_public_views_retired',
            'complete_artifacts_captured', 'numerical_grading_performed',
            'scientific_qualified', 'chronology_is_operator_observed'}
    c.need(type(value) is dict and set(value) == keys, 'Exact trusted closure record')
    c.need(value['schema'] == 'neural100_investigation_closed_candidate_v1'
           and value['task_id'] == 'NEURAL-100' and value['scope'] == SCOPE,
           'Full candidate closure identity')
    c.need(value['source'] == c.exact_pin(source), 'Selected source closure join')
    for name in ('program', 'native_record', 'view_retirement'):
        c.exact_pin(value[name])
    c.need(value['artifacts'] == artifacts and set(artifacts) == set(OUTPUT_CAPS),
           'Both exact output bodies joined to closure')
    for name in OUTPUT_CAPS:
        c.need(c.exact_pin(artifacts[name])['bytes'] <= OUTPUT_CAPS[name], 'Artifact extent')
    for name in ('producer_resources_closed', 'producer_closed_before_capture',
                 'cli_groups_reaped', 'all_public_views_retired',
                 'complete_artifacts_captured', 'chronology_is_operator_observed'):
        c.need(value[name] is True, 'Observed closure required: ' + name)
    c.validate_natural_exit(value['producer_natural_exit'])
    c.need(value['numerical_grading_performed'] is False and value['scientific_qualified'] is False,
           'No premature grading/qualification')
    return value


def admit_pair(report_raw, claims_raw, closure, source, roster, np):
    """No packet/source-provider callback is accepted by this admission function."""
    c.need(type(report_raw) is bytes and 0 < len(report_raw) <= OUTPUT_CAPS['report.json'],
           'Bounded report body')
    c.need(type(claims_raw) is bytes and 0 < len(claims_raw) <= OUTPUT_CAPS['claims.json'],
           'Bounded claims body')
    artifacts = {'report.json': c.pin(report_raw), 'claims.json': c.pin(claims_raw)}
    closure_admit(closure, source, artifacts)
    roster_admit(roster)
    report, stated = c.parse(report_raw), c.parse(claims_raw)
    # Neither admission compares a candidate claim to its own report as truth.
    guard.admit(report, roster, report_contract, np)
    claims.admit(stated, roster)
    return report, stated


def evaluate_admitted(report, stated, roster, reference_loader, sources, np,
                      actual_guard=guard):
    """Guard evaluates once; the very same full core result grounds claim truth."""
    roster_admit(roster)
    contract = sources.module('report_contract')
    actual_guard.admit(report, roster, contract, np)
    claims.admit(stated, roster)
    captured = []

    def once():
        c.need(not captured, 'One independent full reference call only')
        # Append a sentinel before calling: a failed callback cannot be retried.
        captured.append(None)
        full = reference_loader()
        c.need(type(full) is dict, 'Actual full core result required')
        captured[0] = full
        return full

    numeric = actual_guard.evaluate(report, roster, once, sources, np)
    c.need(len(captured) == 1 and captured[0] is not None, 'Exactly one reference result')
    projected = contract.project(captured[0])
    expected = claims.derive(captured[0], projected, roster)
    claim_result = claims.compare(stated, expected)
    return {'schema': 'neural100_investigation_grade_v1', 'task_id': 'NEURAL-100',
            'status': 'compared_unqualified', 'scope': SCOPE,
            'numerical': numeric, 'scientific_claims': claim_result,
            'independent_reference_calls': 1, 'same_full_reference_for_both_outputs': True,
            'candidate_claims_used_as_truth': False, 'scientific_qualified': False,
            'runtime_qualified': False, 'submission_ready': False,
            'open_ended_reasoning_or_causal_claim': False,
            'authentic_identity_and_measurement_qualification_inherited': False}


def load_support_entry(package, binding, export_sha):
    """Only invoked after common admission; captures the exact accepted entry."""
    package = c.path(package)
    expected = binding['support_entry']
    c.need(export_sha == binding['export_pin']['sha256'], 'Fixed export identity')
    raw = c.capture(package / expected['path'], expected['bytes'], c.only_pin(expected))
    module = types.ModuleType('neural100_selected_support_entry')
    module.__file__ = str(package / expected['path'])
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    return module.start(package, export_sha)


def run_grade(package, source, binding, report_raw, claims_raw, closure, roster, np):
    """Actual grade transition, not grade.py alone or a precomputed result receipt."""
    report, stated = admit_pair(report_raw, claims_raw, closure, source, roster, np)
    actual_guard, sources = load_support_entry(package, binding, binding['export_pin']['sha256'])
    c.need(sources.roster == roster, 'Same authenticated public/operator roster')

    def reference():
        # No native data adapter or prepared input is touched before admission.
        adapter, core = sources.module('data_adapter'), sources.module('analysis_core')
        packet = c.path(package) / 'public/input'
        manifest = adapter.load_manifest(packet / 'PREPARED.json', sources.binding['manifest_sha256'])
        return core.analyze(adapter.records(packet, manifest), roster)

    return evaluate_admitted(report, stated, roster, reference, sources, np, actual_guard)
