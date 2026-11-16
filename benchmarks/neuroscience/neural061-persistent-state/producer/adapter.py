"""Concrete A0 host for the unchanged complete scientific production caller.

This adapter consumes a previously captured frozen F method. It performs no LLM
authoring, raw capture, target access, native qualification or public admission.
"""
from dataclasses import dataclass
import hashlib
import uuid
from wire import need
from supervisor import ParticipantChild, NativeCommand, raise_all


@dataclass(frozen=True)
class Authored:
    source_identity: tuple
    body: bytes


@dataclass
class Fitted:
    state_identity: str
    child: ParticipantChild
    cell: tuple
    arm: str
    next_query: int = 0
    closure: object = None


@dataclass(frozen=True)
class Predicted:
    predictions: dict


@dataclass(frozen=True)
class Receipt:
    ordinal: int
    kind: str
    request: object
    original_outcome: object
    qualified: bool = False


class A0Host:
    def __init__(self, command, scratch, child_sources, method_body, owner):
        need(type(command) is NativeCommand and command.owner is owner, 'same original command owner')
        need(type(method_body) is bytes and 0 < len(method_body) <= 1048576, 'captured complete frozen method')
        self.command, self.scratch, self.sources, self.owner = command, scratch, child_sources, owner
        self.method = Authored((len(method_body), hashlib.sha256(method_body).hexdigest()), method_body)
        self.prepared = None; self.authored = False; self.retired = False
        self.states = {}; self.reference_states = {}; self.receipts = []; self.fit_pairs = set()

    def require_entry(self, prepared, owner):
        need(owner is self.owner and self.prepared is None, 'one entry under original owner')
        owner.tick(); cat = prepared['catalogue'].validate(); cat.policy.require_selected()
        need(cat.policy.panels == (('F', 'T0', 0),) and prepared['policy'] is cat.policy and
             prepared['cells'] == cat.cells and set(prepared['public']) == set(cat.source + cat.evaluation),
             'complete unchanged selected A0 programme')
        need(all(prepared['public'][sid]['role'] == 'source' for sid in cat.source) and
             all(prepared['public'][sid]['role'] == 'evaluation' for sid in cat.evaluation), 'exact split roles')
        self.prepared = prepared; self.cat = cat

    def author(self, request, projected_views, owner):
        need(owner is self.owner and not self.authored and self.prepared is not None, 'one global F source')
        need(request['panel'] == ('F', 'T0', 0) and request['access'] == 'source_only' and
             request['evaluation_sessions'] == () and request['source_sessions'] == self.cat.source and
             set(projected_views) == set(self.cat.source), 'all and only source sessions')
        owner.tick(); self.authored = True
        # The operator has already frozen this method. This is not a provider
        # transcript or evidence that an LLM used only the allowed author views.
        return self.method

    def fit(self, request, authored, source_views, tool_lease, owner):
        need(owner is self.owner and authored is self.method and self.authored and
             not self.retired and tool_lease is None, 'exact source and T0')
        cell, arm = request['cell'], request['arm']; pair = (cell, arm)
        need(cell in self.cat.cells and arm in ('BR', 'BC') and pair not in self.fit_pairs and
             cell in self.reference_states and request['source_sessions'] == self.cat.source and
             request['method'] == authored.source_identity and len(source_views) == 423,
             'complete matching cell/arm fit once')
        need(not any(s.closure is None for s in self.states.values()), 'serial fresh cell state; no shared lifetime')
        binding = {'method': authored.source_identity, 'cell': cell, 'arm': arm,
                   'source': self.cat.source, 'evaluation': self.cat.evaluation, 'state': uuid.uuid4().hex}
        child = ParticipantChild(self.command, self.scratch, self.sources, authored.body, binding, owner)
        fitted = Fitted(binding['state'], child, cell, arm)
        self.states[binding['state']] = fitted; self.fit_pairs.add(pair)
        child.start(); result = child.request_operation('fit', {'source': source_views})
        need(result == {'state': binding['state']}, 'bound original fit reply')
        return fitted

    def _skip_to(self, fitted, stop):
        from n061.preparation import session_view
        while fitted.next_query < stop:
            sid = self.cat.evaluation[fitted.next_query]
            view = session_view(self.prepared, sid, fitted.cell, fitted.arm, False)
            need(view['status'] == 'unavailable', 'missing complete prediction cannot become a skip')
            result = fitted.child.request_operation('skip', {'session': sid})
            need(result == {'skipped': sid}, 'same unavailable roster position')
            fitted.next_query += 1

    def predict(self, request, fitted, query_view, tool_lease, owner):
        need(owner is self.owner and self.states.get(fitted.state_identity) is fitted and
             fitted.closure is None and tool_lease is None, 'live exact fitted state, T0')
        need(request['cell'] == fitted.cell and request['arm'] == fitted.arm and
             request['state'] == fitted.state_identity and request['method'] == self.method.source_identity,
             'no cross-cell/arm/source state reuse')
        sid = request['session']; need(sid in self.cat.evaluation, 'original evaluation session')
        stop = self.cat.evaluation.index(sid); self._skip_to(fitted, stop)
        need(fitted.next_query == stop, 'no duplicate or reordered query')
        need(query_view['status'] == 'complete' and query_view['session'] == sid and
             query_view['cell'] == fitted.cell and query_view['arm'] == fitted.arm and
             all('values' not in w for w in query_view['windows']), 'same unlabeled view')
        result = fitted.child.request_operation('predict', {'session': sid, 'query': query_view})
        need(type(result) is dict and set(result) == {'status', 'windows'} and result['status'] == 'complete' and
             type(result['windows']) is tuple and len(result['windows']) == len(query_view['windows']),
             'complete participant response')
        import numpy as np
        for row, window in zip(result['windows'], query_view['windows'], strict=True):
            need(type(row) is dict and set(row) == {'query', 'values'} and row['query'] == window['query'], 'ordered query inverse')
            values = row['values']
            need(type(values) is np.ndarray and values.dtype.kind in 'fiu' and not values.dtype.hasobject and
                 values.ndim == 1 and len(values) == len(window['mask']) and np.isfinite(values).all(),
                 'all finite scalar wheel-velocity predictions before masking')
        fitted.next_query += 1; return Predicted(result)

    def retire_state(self, fitted, owner):
        need(owner is self.owner and self.states.get(fitted.state_identity) is fitted and
             fitted.closure is None, 'retire original live state once')
        self._skip_to(fitted, len(self.cat.evaluation))
        result = fitted.child.request_operation('retire', None)
        need(result == {'retired': fitted.state_identity}, 'same child state retirement')
        fitted.closure = fitted.child.finish(); return fitted.closure

    def observe_operation(self, kind, request, original_outcome, owner):
        need(owner is self.owner, 'same observation owner'); owner.tick()
        if kind == 'reference':
            cell = request['cell']; need(cell in self.cat.cells and cell not in self.reference_states, 'reference once per cell')
            need(set(original_outcome['states']) == set(self.cat.policy.reference_arms) and
                 set(original_outcome['predictions']) == {(s, a) for s in self.cat.evaluation for a in self.cat.policy.reference_arms},
                 'all six original reference models and predictions')
            self.reference_states[cell] = original_outcome
        receipt = Receipt(len(self.receipts), kind, request, original_outcome)
        self.receipts.append(receipt); return receipt

    def retire_method(self, authored, owner):
        need(owner is self.owner and authored is self.method and not self.retired and
             all(s.closure is not None for s in self.states.values()) and
             self.fit_pairs == {(c, a) for c in self.reference_states for a in ('BR', 'BC')},
             'all supported full catalogue cell/arm states closed before method retirement')
        owner.tick(); self.retired = True; return {'method': authored.source_identity, 'retired': True}

    def retire_reference(self, cell, original_reference, owner):
        need(owner is self.owner and self.retired and self.reference_states.get(cell) is original_reference,
             'same complete original reference state population')
        owner.tick(); del self.reference_states[cell]; return {'cell': cell, 'retired': True}

    def open_tool(self, *args):
        raise ValueError('T1 is prospectively unselected; cannot substitute reference state or borrowed child')

    retire_tool = open_tool

    def cleanup_remaining(self):
        errors = []
        for fitted in self.states.values():
            if not fitted.child.closed:
                try: fitted.child.abort()
                except BaseException as error: errors.append(error)
        raise_all(None, errors)

    def publish_production(self, product, owner):
        # Only the separate original outside issuer can authorize publication.
        # Neither container closure nor generated controls fabricate that issuer.
        from n061.admission import MissingNativeProducers
        raise MissingNativeProducers('original outside publication, complete allocation and target issuer')


def construct_prepared(prepared, host, owner):
    """Component entry into the real full caller, explicitly NOT public admission.

    The returned Production is unqualified. Public collect/programme/score retain
    their existing hard holds. No target or report is generated here.
    """
    from n061.production import _collect
    need(type(host) is A0Host and host.owner is owner, 'concrete selected host')
    primary = None; result = None
    try: result = _collect(prepared, host, owner)
    except BaseException as error:
        primary = error
        try: owner.fail(error)
        except BaseException as secondary: primary = BaseExceptionGroup('collection and owner failure', [error, secondary])
    failures = []
    try: host.cleanup_remaining()
    except BaseException as error: failures.append(error)
    raise_all(primary, failures)
    return result.validate()
