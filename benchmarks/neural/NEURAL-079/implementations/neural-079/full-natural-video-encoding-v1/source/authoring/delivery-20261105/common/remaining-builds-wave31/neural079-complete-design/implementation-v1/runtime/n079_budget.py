"""Additive declared-work allocation; physical peaks/inventories are not summed."""
from n079_common import fields, require, integer, checked_pin
from n079_plan import policies, bundles, native_jobs, PERSONS

DIMENSIONS = ('provider_calls', 'provider_input_tokens', 'provider_output_tokens', 'spend_nano_units',
              'code_revisions', 'code_executions', 'fit_calls', 'validation_calls',
              'source_read_bytes', 'data_read_bytes', 'write_bytes', 'log_bytes', 'logical_float_slots',
              'numeric_block_applications', 'process_starts')


def vector(value):
    fields(value, DIMENSIONS)
    return {key: integer(value[key]) for key in DIMENSIONS}


def roster():
    rows = [('policy/' + p['id'], 'pre_exposure_source') for p in policies()]
    for b in bundles():
        rows.append(('training/' + b['id'], 'training_investigation'))
        rows.extend(('query/%s/%d' % (b['id'], q), 'current_query') for q in b['query_ids'])
        rows.append(('report/' + b['id'], 'post_prediction_report'))
    rows.extend(('reference/%s/%s' % (p, signal), 'full_reference_grid')
                for p in PERSONS for signal in ('measured', 'mismatch'))
    rows.extend((r['id'], 'native_companion') for r in native_jobs())
    rows += [(name, 'shared_overhead') for name in ('assembler', 'raw-all17-features', 'feature-grams',
              'controller', 'supervisor', 'custody-issuer', 'observer', 'provider-proxy', 'target-last-grader',
              'finalizer', 'serialization', 'failed-attempt-closeout')]
    return rows


def allocation(selection):
    fields(selection, ('schema', 'source_pin', 'study_pin', 'deployment_pin', 'whole', 'rows'))
    require(selection['schema'] == 'n079_complete_additive_allocation_v1', 'selected full allocation')
    for key in ('source_pin', 'study_pin', 'deployment_pin'):
        checked_pin(selection[key])
    whole = vector(selection['whole'])
    expected = dict(roster())
    require(type(selection['rows']) is list and len(selection['rows']) == len(expected), 'complete work allocations')
    rows = {}
    total = {key: 0 for key in DIMENSIONS}
    for row in selection['rows']:
        fields(row, ('id', 'scope', 'limit', 'selection_evidence'))
        key = row['id']
        require(key in expected and key not in rows and row['scope'] == expected[key], 'exact work identity/scope')
        checked_pin(row['selection_evidence'])
        limit = vector(row['limit']); rows[key] = limit
        for dimension in DIMENSIONS:
            total[dimension] += limit[dimension]
    require(all(whole[k] >= total[k] for k in DIMENSIONS), 'whole allocation covers every local ceiling and overhead')
    # Matched mode/tool/signal ceilings within each phase and seed. Different
    # phase usability is the explicit F/I intervention, not free I calls.
    for seed in range(3):
        for phase in ('training', 'report'):
            vals = [rows[phase + '/' + b['id']] for b in bundles() if b['seed'] == seed]
            require(all(x == vals[0] for x in vals), 'matched complete bundle ceilings')
        for q in range(1001, 1103):
            vals = [rows['query/%s/%d' % (b['id'], q)] for b in bundles() if b['seed'] == seed]
            require(all(x == vals[0] for x in vals), 'matched current-query ceilings')
        vals = [rows['policy/' + p['id']] for p in policies() if p['seed'] == seed]
        require(all(x == vals[0] for x in vals), 'matched source-generation ceilings')
    for p in policies():
        minimum = rows['policy/' + p['id']]
        require(minimum['provider_calls'] >= 1 and minimum['code_revisions'] >= 1,
                'each of12 actual source policies needs a provider call and generated revision')
    for b in bundles():
        works = ['training/' + b['id'], 'report/' + b['id']] + ['query/%s/%d' % (b['id'], q) for q in b['query_ids']]
        for work in works:
            require(rows[work]['code_executions'] >= 1 and rows[work]['process_starts'] >= 1,
                    'every complete training/query/report has a real process allocation')
            if b['mode'] == 'I':
                require(rows[work]['provider_calls'] >= 1 and rows[work]['code_revisions'] >= 1,
                        'each adaptive context must at least finish with an actual source revision')
    for p in PERSONS:
        for signal in ('measured', 'mismatch'):
            require(rows['reference/%s/%s' % (p, signal)]['fit_calls'] >= 459,
                    'all458 target fits plus one separate training-mean state per person/signal')
    for row in native_jobs():
        require(rows[row['id']]['process_starts'] >= 1 and rows[row['id']]['code_executions'] >= 1,
                'all22 actual complete native jobs individually allocated')
    for work in ('assembler', 'raw-all17-features', 'feature-grams', 'controller', 'supervisor',
                 'custody-issuer', 'observer', 'provider-proxy', 'target-last-grader'):
        require(rows[work]['process_starts'] >= 1, 'all actual outer-owned source processes allocated')
    require(rows['reference/sub-01/measured']['process_starts'] >= 1, 'one protected full reference producer allocated')
    require(all(rows[work]['source_read_bytes'] > 0 and rows[work]['write_bytes'] > 0
                for work, scope in roster() if scope == 'shared_overhead'),
            'every named shared/failure/serialization overhead has explicit finite nonzero source and output capacity')
    return {'whole': whole, 'rows': rows, 'required': total,
            'meaning': 'declared additive capacity; actual cost and physical feasibility remain independently observed'}


class Ledger:
    def __init__(self, selected, clock):
        self.selected = allocation(selected)
        self.clock = clock
        self.actual = {k: 0 for k in DIMENSIONS}
        self.local = {name: {k: 0 for k in DIMENSIONS} for name in self.selected['rows']}
        self.attempts = []

    def charge(self, work_id, delta, reason, phase='scientific'):
        require(work_id in self.local and type(delta) is dict and set(delta) <= set(DIMENSIONS), 'named actual work counter')
        values = {k: integer(v) for k, v in delta.items()}
        attempt = {'work_id': work_id, 'delta': values, 'reason': reason, 'status': 'attempted'}
        self.attempts.append(attempt)
        # Charge both attempted counters before refusal; no partial rollback.
        for k, amount in values.items():
            self.actual[k] += amount
            self.local[work_id][k] += amount
        try:
            self.clock.tick(phase)
            require(all(self.actual[k] <= self.selected['whole'][k] for k in DIMENSIONS), 'whole additive ceiling')
            require(all(self.local[work_id][k] <= self.selected['rows'][work_id][k] for k in DIMENSIONS), 'local additive ceiling')
        except BaseException as error:
            attempt['status'] = 'refused'; attempt['error_type'] = type(error).__name__
            error.n079_prefix = self.snapshot()
            raise
        attempt['status'] = 'reserved'

    def snapshot(self):
        return {'actual_attempted': dict(self.actual), 'local_attempted': {k: dict(v) for k, v in self.local.items()},
                'attempts': list(self.attempts), 'physical_peaks_or_network_total': 'not inferred'}
