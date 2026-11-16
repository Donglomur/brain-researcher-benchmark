"""Single-program successor: exact accepted 3300+180 prefix, then 780 seconds.

The semantic receipt checks derive from the accepted four-output accounting
adapter. Only the prospective operation is changed. Original metadata stays
owner-local and is authenticated before any scalar/path fields are interpreted.
"""
from copy import deepcopy
from pathlib import PurePosixPath
from files import descriptor, need

TASK = 'PAPER-FIND-ADD-006'
LEGACY_FREEZE = '40d4b1bcf8b62cfdeef1b4ff1d519445b534c87f4a101b548500a116aec781fc'
REQUEST_SCHEMA = 'hierarchy25a_single_program_closed_reference_accounting_v1'
LEGACY_RECEIPT = {'path': '.hierarchy25a-operator/legacy-prefix.json', 'bytes': 6810,
    'sha256': '65071a8c9cf522eeeb7065b0b0fcb79a09f89d33088e8a0b84463c7c7bebd29f'}
REFERENCE_RECEIPT = {'path': '.hierarchy25a-operator/reference-event.json', 'bytes': 4766,
    'sha256': '0906f93089a338952b8b73538f4bdb3468e25cf74188a85c057b992647235b6f'}
REFERENCE_ACCEPTANCE = {'path': '.hierarchy25a-operator/reference-acceptance.json', 'bytes': 23562,
    'sha256': 'b9fec4898d2879b9c9fa16b2bf67e044ec0b189e0402ebd6fda58445f33a70a4'}


def original_descriptor(value, size, sha256):
    # This is a descriptor inside an already hash-authenticated original. Its
    # absolute historical locator is never followed or published. Identity is
    # joined by exact bytes/hash, not by caller-supplied ancestry or a new alias.
    return (type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}
            and type(value['path']) is str and PurePosixPath(value['path']).is_absolute()
            and '..' not in PurePosixPath(value['path']).parts
            and not any(c in value['path'] for c in '\r\n\0')
            and type(value['bytes']) is int and value['bytes'] == size
            and value['sha256'] == sha256)


def expected_request():
    return {'schema': REQUEST_SCHEMA,
        'legacy_prefix_receipt': deepcopy(LEGACY_RECEIPT),
        'latest_accounting_evidence': deepcopy(REFERENCE_RECEIPT),
        'independent_reference_acceptance': deepcopy(REFERENCE_ACCEPTANCE),
        'freeze_sha256': LEGACY_FREEZE, 'prior_known_seconds': 3480,
        'new_full_allocation_seconds': 780, 'known_after_seconds': 4260,
        'prior_is_latest_known_closed_family_event': True, 'lifetime_cost_complete': False}


def validate_values(review, seconds, old, reference, acceptance):
    """Pure semantic join for generated controls and captured original metadata."""
    expected = expected_request()
    need(type(review) is dict and set(review) == set(expected), 'exact reference accounting request')
    for key in ('prior_known_seconds', 'new_full_allocation_seconds', 'known_after_seconds'):
        need(type(review[key]) is int, 'integer allocation rather than boolean/float')
    need(type(seconds) is int and seconds == 780, 'complete original single-program allocation')
    need(review == expected, 'exact current 3480 prefix and prospective 4260 total')
    need(review['prior_is_latest_known_closed_family_event'] is True
           and review['lifetime_cost_complete'] is False, 'latest known event; lifetime remains incomplete')

    need(type(old) is dict and old.get('candidate_id') == TASK
           and old.get('runtime_id') == 'hierarchy_bounded_task_v1'
           and old.get('status') == 'passed'
           and old.get('source_freeze_sha256') == LEGACY_FREEZE, 'original same-family legacy receipt')
    for key, value in (('prior_known_seconds', 2520), ('charged_seconds', 780), ('known_after_seconds', 3300)):
        need(type(old.get(key)) is int and old[key] == value, 'exact closed legacy allocation chain')
    need(all(old.get(key) is True for key in ('all_owned_absent', 'all_activated_groups_absent',
                                             'controller_process_reaped', 'controller_launch_attempted')),
           'legacy native and process closure')
    need(old.get('lifetime_cost_complete') is False and old.get('automatic_retry') is False,
           'legacy cost and retry limits retained')

    need(type(reference) is dict
           and reference.get('schema') == 'hierarchy_retained_reference_owner_outcome_v1'
           and reference.get('accepted') is True and reference.get('dispatched') is True
           and reference.get('status') == 'constructed_pending_independent_whole_review',
           'actual dispatched retained-reference producer receipt')
    for key, value in (('prior_known_seconds', 3300), ('new_full_charge_seconds', 180), ('known_after_seconds', 3480)):
        need(type(reference.get(key)) is int and reference[key] == value, 'actual reference full180 charge')
    need(original_descriptor(reference.get('accounting_custody'), 4990, 'de70e28ea3db7d703d62176487e7fabb4cc67973760443d9a1c962966ce4d12c')
           and reference.get('lifetime_cost_complete') is False
           and reference.get('automatic_retry') is False
           and reference.get('scientific_qualification') is False,
           'retained reference custody and limits')
    transport = reference.get('transport', {})
    need(type(transport) is dict and transport.get('schema') == 'nider_gated_capture_bridge_v2'
           and type(transport.get('exit_code')) is int and transport['exit_code'] == 0
           and transport.get('child_reaped') is True and transport.get('process_group_absent') is True
           and transport.get('pipe_EOF') == ['stdout', 'stderr']
           and transport.get('observer_exception') is None and transport.get('termination_reason') is None,
           'complete successful reference transport closure')

    need(type(acceptance) is dict
           and acceptance.get('schema') == 'hierarchy_full_independent_retained_reference_admission_v1'
           and acceptance.get('accepted') is True
           and original_descriptor(acceptance.get('owner_outcome'), REFERENCE_RECEIPT['bytes'], REFERENCE_RECEIPT['sha256'])
           and acceptance.get('automatic_retry') is False
           and acceptance.get('scientific_qualification') is False,
           'independent whole admission joins exact actual owner')
    cost = acceptance.get('cost', {})
    for key, value in (('prior_known_producer_family_seconds', 3300), ('producer_full_charge_seconds', 180),
                       ('known_producer_family_seconds', 3480), ('independent_review_allocation_seconds', 180)):
        need(type(cost.get(key)) is int and cost[key] == value, 'same complete accepted allocation')
    need(cost.get('lifetime_complete') is False
           and cost.get('independent_review_separate_from_producer_family_charge') is True,
           'separate review cost is not hidden or double-counted')
    producer = acceptance.get('producer', {})
    need(producer.get('engine_natural_exit_observed') is True
           and type(producer.get('outside_natural_exit_code')) is int and producer['outside_natural_exit_code'] == 0
           and type(producer.get('worker_exit_code')) is int and producer['worker_exit_code'] == 0
           and producer.get('forced_signals') == [], 'independently observed natural producer exit')
    absence = producer.get('fresh_owned_absence')
    need(type(absence) is list and len(absence) == 10
           and all(type(row) is dict and type(row.get('pid')) is int and row['pid'] > 0
                   and row.get('pid_state') == row.get('pgid_state') == 'ESRCH' for row in absence)
           and len({row['pid'] for row in absence}) == 10, 'all ten recorded process/group closures')
    return 3480

def accounting(review, seconds):
    need(type(seconds) is int and seconds == 780, 'Single-program full allocation')
    expected = expected_request()
    need(review.get('accounting_successor') == expected, 'Exact current accounting component')
    need(type(review.get('prior_known_seconds')) is int and review['prior_known_seconds'] == 3480
         and type(review.get('known_after_seconds')) is int and review['known_after_seconds'] == 4260,
         'No stale prefix, skipped event, bool or allocation reset')
    need(review.get('latest_accounting_evidence') == REFERENCE_RECEIPT
         and review.get('prior_is_latest_known_closed_family_event') is True,
         'Owner attests this is still the latest completed family event')
    # Fixed exact descriptors are admitted before any historical path is read.
    records = [descriptor(p, 32768) for p in
               (LEGACY_RECEIPT, REFERENCE_RECEIPT, REFERENCE_ACCEPTANCE)]
    return validate_values(expected, seconds, *records)
