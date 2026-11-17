"""Original HM C-row publication credit; no new programme allowance.

Guard/base/lease publication must not change the frozen programme prefix.
This fixed owner reserves the remainder of the actual C00/C01/C02 row before
forming those snapshots, then spends only that original finite credit. It is
separate from the existing C05 score reservation and supplies no native authority.
"""
from pathlib import Path
from .common import need, pin, encode, bounded_size
from .source_session import SourceSession
from .roots import BoundRoots

PROGRAMME = 'PAPER-paper-method-replacement-016'
_ROW = object()
_PUBLICATION = object()
SLOTS = ('SUBJECT.json', 'GUARD_STATE.json', 'BASE_STATE.json', 'LEASE.json', 'WORKER_REQUEST.json')


def captured_module(session, name):
    need(type(session) is SourceSession and session.programme == PROGRAMME and not session.closed,
         'same actual live captured HM source session')
    module = session.module(name)
    need(vars(module).get('__loader__') is session and
         vars(module).get('__name__') == session.prefix + '.' + name,
         'actual captured HM module, never an ambient scientific callback')
    return vars(module)


class HMMainMetadataPublicationV1:
    __slots__ = ('owner', 'name', 'raw', 'local_descriptor', 'descriptor', '_token')

    def __init__(self, token, owner, name, raw, local_descriptor):
        need(token is _PUBLICATION, 'only the actual completed original Publisher return')
        self._token = token
        self.owner = owner
        self.name = name
        self.raw = raw
        self.local_descriptor = dict(local_descriptor)
        # Explicit R namespace inverse of this exact Publisher root and return.
        self.descriptor = {**local_descriptor, 'path': owner.relative_root + '/' + local_descriptor['path']}

    def require_original(self):
        owner = self.owner
        need(self._token is _PUBLICATION and owner.publications.get(self.name) is self and
             type(owner.publisher) is owner._publisher_class and
             owner.publisher.root == owner.root and owner.publisher.budget is owner and
             self.local_descriptor['path'] == self.name and
             pin(self.raw) == {k: self.local_descriptor[k] for k in ('bytes', 'sha256')} and
             self.descriptor == {**self.local_descriptor,
                 'path': owner.relative_root + '/' + self.local_descriptor['path']} and
             {**self.local_descriptor, 'complete': True} in owner.publisher.outputs,
             'actual completed same-owner write and exact original R descriptor base')
        return self


class HMRowMetadataOwnerV1:
    def __init__(self, token, *, session, budget, roots):
        need(token is _ROW, 'fixed original row-credit factory')
        bm = captured_module(session, 'stage_budget')
        gm = captured_module(session, 'guard')
        need(type(budget) is bm['ExclusiveBudget'] and type(roots) is BoundRoots and
             set(roots.roots) == {'R'} and roots.relative_base == 'R' and
             budget.owner == 'C' and budget.row in ('C00', 'C01', 'C02'),
             'actual complete original HM C writer, fixed issuing row and R')
        self.session = session
        self.budget = budget
        self.row = budget.row
        self.generation = budget.generation
        self.roots = roots
        self.relative_root = 'central_output/hm-main-' + self.row
        self.root = Path(roots.roots['R']) / self.relative_root
        self.remaining = {}
        self.attempted = {}
        self.reserved = {}
        self.publications = {}
        self.attempts = {}
        self.publisher = None
        self.raw_first = None
        self.secondaries = []
        self.complete = False
        self._guard = gm
        self._budget_class = bm['ExclusiveBudget']
        self._publisher_class = gm['Publisher']
        owners = getattr(budget, '_hm_main_metadata_rows_v1', None)
        if owners is None:
            owners = {}
            budget._hm_main_metadata_rows_v1 = owners
        need(type(owners) is dict and self.row not in owners,
             'one actual metadata reserve attempt per original C row, including failure')
        owners[self.row] = self  # Retain the attempted owner before any debit/effect.
        try:
            budget.require_operation('subject')
            need(budget.guard is None and budget.pending is None and budget.active and
                 not budget.failed and budget.primary is None,
                 'original active prelude before issuer arm or stage delegation')
            limits = budget.plan.rows[self.row]['logical']
            need(set(limits) == {'read_bytes', 'write_bytes', 'work'}, 'only original logical dimensions')
            credit = {k: limits[k] - budget.rows[self.row][k] for k in limits}
            need(all(type(v) is int and v >= 0 for v in credit.values()),
                 'actual finite remaining row credit, no extra allowance')
            for kind in ('read_bytes', 'write_bytes', 'work'):
                budget.charge(kind, credit[kind])
                self.reserved[kind] = credit[kind]
            self.remaining = dict(credit)
            self.attempted = dict.fromkeys(credit, 0)
            self.publisher = gm['Publisher'](self.root, self)
            self.complete = True
        except BaseException as error:
            self.retain(error)
            raise self.raw_first

    def retain(self, error):
        if self.raw_first is None:
            self.raw_first = error
        elif error is not self.raw_first:
            self.secondaries.append(error)
        self.budget._own(error)

    def check(self):
        if self.raw_first is not None:
            raise self.raw_first
        need(not self.session.closed and type(self.budget) is self._budget_class and
             self.root == Path(self.roots.roots['R']) / self.relative_root and
             self.budget._hm_main_metadata_rows_v1.get(self.row) is self and
             self.budget.row == self.row and self.budget.generation == self.generation,
             'same original nontransferable row/generation credit')
        # This also forbids publication while armed/waiting or after suspension.
        self.budget.check()

    def snapshot(self):
        return self.budget.snapshot()

    def charge(self, kind, amount):
        self.check()
        need(kind in self.remaining and type(amount) is int and amount >= 0,
             'exact finite original metadata credit category and amount')
        self.attempted[kind] += amount
        if amount > self.remaining[kind]:
            extra = amount - self.remaining[kind]
            self.remaining[kind] = 0
            # Keep the real attempt beyond credit in the original failed prefix.
            try:
                self.budget.charge(kind, extra)
            except BaseException as error:
                self.retain(error)
                raise self.raw_first
            need(False, 'original row overrun cannot be admitted')
        else:
            self.remaining[kind] -= amount

    def publish(self, name, body):
        self.check()
        need(self.complete and name in SLOTS and name not in self.attempts,
             'one complete fixed metadata slot, no retry or arbitrary publication')
        attempt = {'raw': None, 'returned': None, 'raw_first': None}
        self.attempts[name] = attempt
        try:
            self.charge('work', bounded_size(body) * 64 + 4096)
            raw = encode(body)
            attempt['raw'] = raw
            returned = self.publisher.write(name, raw)
            attempt['returned'] = returned  # Retain before any later validation.
            need(returned == {'path': name, **pin(raw)}, 'actual complete canonical write return')
            result = HMMainMetadataPublicationV1(_PUBLICATION, self, name, raw, returned)
            self.publications[name] = result
            result.require_original()
            return result
        except BaseException as error:
            attempt['raw_first'] = error
            self.retain(error)
            raise self.raw_first


def reserve_original_hm_row_metadata_v1(*, session, budget, roots):
    return HMRowMetadataOwnerV1(_ROW, session=session, budget=budget, roots=roots)
