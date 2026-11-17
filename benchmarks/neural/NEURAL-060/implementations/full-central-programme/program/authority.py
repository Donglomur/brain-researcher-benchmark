"""Protected operator admission, distinct from source review and candidate facts."""
from pathlib import Path
import os
import time

from core import Budget, capture, capture_new_protected, descriptor, finite, integer, need, parse, relative

REQUIRED = ('full_inputs', 'runtime_environment', 'provider_transport', 'independent_observer',
            'resource_envelope', 'scientific_method_review_policy')


def disjoint(a, b):
    a, b = Path(a), Path(b)
    need('..' not in a.parts and '..' not in b.parts, 'canonical roots without dot-dot')
    a, b = a.absolute(), b.absolute()
    return a != b and a not in b.parents and b not in a.parents


def selected(authority, runtime_pin, observed_origin):
    """No candidate/data/provider path or credential opens in this function."""
    need(type(authority) is dict and authority.get('schema') == 'neural060_root_authority_v1',
         'root-selected authority schema')
    need(authority.get('active') is True, 'not qualified: source-only NEURAL060 authority')
    need(authority.get('task_id') == 'NEURAL-060' and authority.get('runtime_source') == runtime_pin,
         'exact selected task/runtime source')
    need(type(authority.get('qualifications')) is dict and set(authority['qualifications']) == set(REQUIRED),
         'all independent qualification authorities required')
    need(authority['original_origin'] == observed_origin and type(observed_origin) in (int, float),
         'inherited actual outer origin, no nested reset')
    deadline = finite(authority['whole_deadline'])
    need(deadline > observed_origin, 'selected original whole deadline')
    for name in ('packet_root', 'attempt_root', 'operator_root', 'observation_root'):
        need(type(authority[name]) is str and Path(authority[name]).is_absolute(), 'explicit operator roots')
    need(disjoint(authority['packet_root'], authority['attempt_root'])
         and disjoint(authority['operator_root'], authority['attempt_root'])
         and disjoint(authority['operator_root'], authority['packet_root']), 'isolated protected roots')
    need(all(disjoint(authority['observation_root'], authority[k]) for k in ('packet_root', 'attempt_root', 'operator_root')),
         'separate fresh observation root')
    resource = authority['resources']
    need(type(resource) is dict and type(resource.get('full_workload_selected')) is bool
         and resource['full_workload_selected'], 'full-workload resource selection')
    integer(resource['read_bytes'], 1); integer(resource['write_bytes'], 1)
    integer(resource['observer_read_bytes'], 1); integer(resource['observer_write_bytes'], 1)
    need(integer(resource['whole_read_bytes'], 1) >= resource['read_bytes']+resource['observer_read_bytes']
         and integer(resource['whole_write_bytes'], 1) >= resource['write_bytes']+resource['observer_write_bytes'],
         'independent worker/observer reservations covered by whole-study envelope')
    native_limits = [authority[name] for name in ('candidate_native_limits', 'reference_native_limits',
                                                 'tool_native_limits')]
    for limits in native_limits:
        for name in ('cpu_seconds', 'cpu_nanos', 'cleanup_seconds', 'cleanup_read_bytes', 'cleanup_write_bytes'):
            integer(limits[name], 1)
    # Six global episodes each pool29 allowances;174 adaptive episodes retain
    # one each. This is348 base tool-CPU allowances, plus every fixed process.
    total_cpu = (870*native_limits[0]['cpu_seconds']+145*native_limits[1]['cpu_seconds']
                 +348*integer(authority['authoring_limits']['tool_cpu_seconds'], 1))
    need(integer(resource['whole_native_cpu_seconds'], 1) >= total_cpu,
         'all candidate/reference/investigation CPU reservations covered prospectively')
    observer = authority['observer_limits']
    need(integer(observer['closeout_seconds'], 1) >= integer(observer['resource_stop_seconds'], 1)
         >= max(limits['cleanup_seconds'] for limits in native_limits),
         'independent outer stop allowance covers selected per-phase stop latency')
    for name in REQUIRED:
        row = authority['qualifications'][name]
        need(type(row) is dict and set(row) == {'path', 'pin'}, 'qualified protected receipt descriptor')
        relative(row['path']); descriptor(row['pin'])
    return authority


def qualify(authority, runtime_pin, observed_origin, budget):
    selected(authority, runtime_pin, observed_origin)
    root = Path(authority['operator_root'])
    records = {}
    for name in REQUIRED:
        row = authority['qualifications'][name]
        raw, _ = capture(root/relative(row['path']), row['pin'], 1048576, budget, readonly=True)
        record = parse(raw)
        need(type(record) is dict and record.get('schema') == 'neural060_independent_qualification_v1'
             and record.get('kind') == name and record.get('task_id') == 'NEURAL-060'
             and record.get('runtime_source') == runtime_pin and record.get('qualified') is True
             and record.get('issuer') == authority['operator_identity']
             and record.get('realm') == 'actual_external_evidence', 'actual independent qualification identity')
        need(type(record.get('evidence')) is list and record['evidence'], 'concrete independent evidence closure')
        for evidence in record['evidence']:
            need(type(evidence) is dict and set(evidence) == {'path', 'pin'}, 'exact external evidence')
            capture(root/relative(evidence['path']), evidence['pin'], authority['resources']['evidence_bytes'],
                    budget, retain=False, readonly=True)
        need(record.get('selection_pin') == authority['qualification_selection_pins'][name],
             'qualification binds exact selected inputs/provider/environment/resources')
        records[name] = row['pin']
    return records


def method_admission(authority, episode, source_pin, recipe_pin, claim_pin, budget, cutoff):
    """A protected independently created receipt, not an agent declaration.

    The root selects the protected publication path before the study. A qualified
    independent reviewer may publish the exact dynamic-source receipt after the
    author terminates; waiting consumes the SAME original clock. No provider or
    native operation is retried. A missing receipt at cutoff leaves a failed study.
    """
    key = '/'.join(str(x) for x in episode)
    rows = authority['method_admissions']
    need(type(rows) is dict and key in rows, 'source created but independent method admission missing')
    row = rows[key]
    need(type(row) is dict and set(row) == {'path'} and row['path'].startswith('methods/')
         and row['path'].endswith('.json'), 'preselected protected method publication name')
    path = Path(authority['operator_root'])/relative(row['path'])
    while not os.path.lexists(path):
        budget.tick(cutoff)
        time.sleep(min(0.1, max(0., cutoff-time.monotonic())))
    budget.tick(cutoff)
    raw, captured_pin = capture_new_protected(path, 1048576, budget)
    value = parse(raw)
    need(value.get('schema') == 'neural060_method_admission_v1' and value.get('issuer') == authority['operator_identity']
         and value.get('episode') == list(episode) and value.get('source') == source_pin
         and value.get('study_id') == authority['study_id']
         and value.get('recipe') == recipe_pin and value.get('claim') == claim_pin,
         'exact independently reviewed source/recipe/claim lineage')
    required = ('no_carried_learned_numeric_state', 'trainval_only_final_fitting',
                'prediction_only_inference', 'no_shift_detection_or_undo', 'no_target_reconstruction',
                'full_support', 'deterministic_paired_rng', 'typed_recipe_roles_reviewed')
    need(value.get('accepted') is True and type(value.get('findings')) is dict
         and set(value['findings']) == set(required) and all(value['findings'][k] is True for k in required),
         'independent semantic method admission incomplete')
    need(type(value.get('review_evidence')) is list and value['review_evidence'], 'method review evidence missing')
    for evidence in value['review_evidence']:
        capture(Path(authority['operator_root'])/relative(evidence['path']), evidence['pin'], 1048576,
                budget, retain=False, readonly=True)
    budget.tick(cutoff)
    return captured_pin
