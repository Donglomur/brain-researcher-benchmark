"""Target-owned release barrier; private identities never constitute features."""
from common import need, integer, pin
from study import EVENT_ORDER

class HistoryBarrier:
    def __init__(self, obligations, session_order):
        need(type(obligations) is list and obligations, 'complete obligations')
        need(type(session_order) is list and len(session_order) == len(set(session_order)), 'session order')
        self.rows = {}
        self.target_members = {}
        self.target_times = {}
        self.target_sessions = {}
        self.session_order = {s: i for i, s in enumerate(session_order)}
        for row in obligations:
            need(set(row) == {'id', 'query_id', 'target_key', 'session', 'trial', 'stratum',
                             'variant_ordinal', 'observation_end_ns', 'target_available_ns'}, 'history obligation schema')
            q = row['id']; need(type(q) is str and q not in self.rows, 'unique obligation')
            need(row['session'] in self.session_order and row['stratum'] in EVENT_ORDER, 'history chronology')
            for name in ('trial', 'variant_ordinal', 'observation_end_ns', 'target_available_ns'):
                integer(row[name])
            self.rows[q] = dict(row)
            target = row['target_key']
            self.target_members.setdefault(target, set()).add(q)
            identity = (row['session'], row['target_available_ns'])
            need(target not in self.target_times or
                 (self.target_sessions[target], self.target_times[target]) == identity, 'shared target release identity')
            self.target_sessions[target], self.target_times[target] = identity
        order = sorted(self.rows, key=lambda q: (
            self.session_order[self.rows[q]['session']], self.rows[q]['observation_end_ns'],
            self.rows[q]['trial'], EVENT_ORDER[self.rows[q]['stratum']],
            self.rows[q]['variant_ordinal'], self.rows[q]['query_id'], q))
        self.batches = []
        for q in order:
            row = self.rows[q]; boundary = (row['session'], row['observation_end_ns'])
            if not self.batches or self.batches[-1][0] != boundary:
                self.batches.append((boundary, []))
            self.batches[-1][1].append(q)
        self.position, self.active, self.failed = 0, None, False
        self.closed, self.closed_at, self.receipts, self.released = set(), {}, {}, set()

    def next_batch(self):
        need(not self.failed and self.active is None, 'previous batch must close durably')
        if self.position == len(self.batches):
            return None
        boundary, ids = self.batches[self.position]
        session, time = boundary
        for target, members in self.target_members.items():
            if target in self.released or self.target_sessions[target] != session:
                continue
            if members <= self.closed and self.target_times[target] <= time and self.closed_at[target] < time:
                self.released.add(target)
        self.active = tuple(ids)
        available = sorted(t for t in self.released if self.target_sessions[t] == session)
        need(not set(available) & {self.rows[q]['target_key'] for q in ids}, 'current target embargo')
        return {'boundary': boundary, 'obligation_ids': list(ids), 'released_target_keys': available}

    def close_batch(self, receipts):
        need(not self.failed and self.active is not None, 'active live batch')
        need(type(receipts) is dict and set(receipts) == set(self.active), 'whole tied batch before release')
        boundary = self.batches[self.position][0]
        for q, record in receipts.items():
            need(type(record) is dict and set(record) == {'obligation_id', 'prediction_pin', 'closure_pin'},
                 'exact durable prediction/closure descriptors')
            from common import require_pin
            need(record['obligation_id'] == q, 'same obligation')
            require_pin(record['prediction_pin']); require_pin(record['closure_pin'])
        # Authentic durable custody is an independent runtime obligation. This
        # source checks full descriptor joins; supplied pins do not prove fsync.
        for q, record in receipts.items():
            self.closed.add(q); self.receipts[q] = pin(record)
            self.closed_at[self.rows[q]['target_key']] = boundary[1]
        self.position += 1; self.active = None

    def fail(self):
        self.failed = True

    def finish(self):
        need(not self.failed and self.active is None and len(self.closed) == len(self.rows),
             'complete successful query obligations')
        return {'obligations': len(self.rows), 'batches': len(self.batches),
                'closed_receipts_pin': pin(self.receipts), 'physical_custody_qualified': False}

def logical_training_schedule(obligations, session_order):
    """Complete-success metadata schedule, independent of numeric labels/results."""
    barrier = HistoryBarrier(obligations, session_order)
    out = []
    while True:
        batch = barrier.next_batch()
        if batch is None:
            break
        out.append(batch)
        receipts = {q: {'obligation_id': q, 'prediction_pin': pin({'logical_only': q}),
                        'closure_pin': pin({'assumed_complete_success': q})}
                    for q in batch['obligation_ids']}
        barrier.close_batch(receipts)
    barrier.finish()
    return {'schema': 'ach_logical_training_information_schedule_v1', 'batches': out,
            'labels_read': False, 'actual_query_closure': False}
