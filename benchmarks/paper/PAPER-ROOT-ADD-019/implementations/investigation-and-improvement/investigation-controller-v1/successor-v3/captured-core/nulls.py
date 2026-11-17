"""Explicit cyclic epoch-shift diagnostic; no actual null policy is installed."""
from common import need, integer, require_pin, pin, token

def validate_and_map(study, policy):
    need(type(policy) is dict and set(policy) == {'id', 'kind', 'refit', 'groups',
         'clock_support_evidence', 'selection_evidence'}, 'exact independently selected null policy')
    token(policy['id']); need(policy['id'] != 'observed', 'separate null realization')
    need(policy['kind'] == 'within_session_joint_neural_epoch_cyclic_shift_v1' and
         policy['refit'] == 'full_graph', 'specific diagnostic and complete refit')
    require_pin(policy['clock_support_evidence']); require_pin(policy['selection_evidence'])
    rows = {r['id']: r for r in study['queries']}
    need(len(rows) == len(study['queries']), 'unique complete query ledger')
    def identity(row):
        return (row['animal'],row['session'],row['stratum'],tuple(row['channel_mask']),
                row['grid_pin']['bytes'],row['grid_pin']['sha256'])
    full_groups={}
    for row in rows.values():full_groups.setdefault(identity(row),[]).append(row['id'])
    for ids in full_groups.values():ids.sort(key=lambda q:(rows[q]['observation_end_ns'],q))
    mapping, used = {}, set()
    need(type(policy['groups']) is list and policy['groups'], 'complete admitted groups')
    for group in policy['groups']:
        need(set(group) == {'ids', 'offset', 'minimum_separation_ns',
                           'circular_period_ns', 'maximum_circular_gap_ns', 'boundary'}, 'null group schema')
        ids = group['ids']; need(type(ids) is list and len(ids) > 1 and len(ids) == len(set(ids)), 'nontrivial full group')
        need(not set(ids) & used and set(ids) <= set(rows), 'partition without duplicates')
        offset = integer(group['offset'], 1); need(offset < len(ids), 'nonidentity cyclic offset')
        separation = integer(group['minimum_separation_ns'], 1)
        period = integer(group['circular_period_ns'], 1)
        maxgap = integer(group['maximum_circular_gap_ns'], 1)
        need(group['boundary'] == 'declared_circular_wrap_no_exchangeability_claim', 'explicit boundary interpretation')
        first = rows[ids[0]]
        group_identity = identity(first)
        need(ids==full_groups[group_identity], 'one complete original chronological identity group; no subgroup split')
        times = []
        for q in ids:
            row = rows[q]
            need(identity(row) == group_identity,
                 'no cross-animal/session/event/sensor/grid donor')
            times.append(integer(row['observation_end_ns']))
        need(times == sorted(set(times)), 'strict authentic within-group chronology')
        span = times[-1] - times[0]; need(period > span, 'positive declared circular gap')
        gaps = [b-a for a,b in zip(times,times[1:])] + [period-span]
        need(max(gaps) <= maxgap, 'admitted maximum circular gap')
        for i, q in enumerate(ids):
            donor = ids[(i+offset) % len(ids)]
            distance = abs(times[(i+offset) % len(ids)]-times[i])
            need(min(distance, period-distance) >= separation, 'every donor has declared real-time separation')
            mapping[q] = donor
        used.update(ids)
    need(used == set(rows) and set(mapping.values()) == set(rows), 'complete bijective full-support null')
    return {'id': policy['id'], 'mapping': mapping, 'policy_pin': pin(policy),
            'refit': 'full_graph', 'actual_clock_support_qualified': False,
            'exchangeability_or_causal_inference_claimed': False}

def shift_private_rows(rows, admitted_mapping):
    """Return private reference/preparation rows, not a candidate query view.

    Both neural channels travel together; labels/history/masks/target identities
    remain attached to the recipient. Caller must revalidate original lineage.
    """
    mapping = admitted_mapping['mapping']
    need(type(rows) is dict and set(rows) == set(mapping), 'all original private rows')
    out, lineage = {}, {}
    for key, donor in mapping.items():
        row, source = rows[key], rows[donor]
        need(row['channel_mask'] == source['channel_mask'] and row['grid_pin'] == source['grid_pin'],
             'actual donor neural support equality')
        result = dict(row)
        result['epochs'] = {name: source['epochs'][name] for name in ('D','ACh')}
        lineage[key] = {'policy_pin': admitted_mapping['policy_pin'], 'recipient': key, 'donor': donor}
        out[key] = result
    # Private lineage is an adjacent artifact, never an extra feature/row field.
    return {'rows': out, 'lineage': lineage, 'lineage_pin': pin(lineage),
            'policy_pin': admitted_mapping['policy_pin']}

def require_complete_null_results(plan, policies, results):
    need(type(policies) is list and policies, 'mandatory real null policy remains unadmitted if absent')
    ids = [p['id'] for p in policies]
    need(len(ids) == len(set(ids)) and set(results) == set(ids), 'every selected null result')
    need(plan['counts']['realizations'] == len(ids)+1, 'complete graph accounted for every null')
    for policy in policies:
        result = results[policy['id']]
        need(result['policy_pin'] == pin(policy) and result['complete_graph'] is True,
             'null complete graph and source lineage')
    return {'policies': len(ids), 'no_actual_runtime_or_policy_qualification': True}
