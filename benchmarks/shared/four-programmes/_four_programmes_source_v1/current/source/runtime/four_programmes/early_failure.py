"""Actual bounded capture and failure publication under the same early owner."""
from .common import Store, need, integer, descriptor, relative, parse, encode, bounded_size
from .precommit_records import validate_type
from .early_resources import ParentCustody, EarlyResources, preselection_failure_v2

_RETURN = object()

def _store_view(store, meter):
    need(type(store) is Store, 'fixed anchored ordinary Store, not a writer callback')
    # Retain the exact already admitted roots/exclusions. This view does not
    # re-resolve a supplied path, create a new Share or manufacture a root.
    view = Store.__new__(Store)
    view.root, view.forbidden, view.meter = store.root, store.forbidden, meter
    view.raw_close_errors=store.raw_close_errors
    view.raw_close_diagnostic_errors=store.raw_close_diagnostic_errors
    view.last_close_diagnostic_error=store.last_close_diagnostic_error
    view.raw_io_errors=store.raw_io_errors
    view.raw_io_diagnostic_errors=store.raw_io_diagnostic_errors
    return view

class SelectionReadState:
    def __init__(self, owner, *, path, cap):
        need(type(owner) is EarlyResources and owner.parent.owner is owner, 'actual original owner')
        relative(path); integer(cap, 1)
        need(owner.seed is not None and path == owner.seed['private_selection_path'] and
             cap == owner.seed['maximum_selection_bytes'], 'earlier exact selected selection path/cap')
        self.owner = owner
        self.raw = self.body = None
        self._attempted = False
        self.capture = {'schema': 'ci_selectioncaptureprefix_v2', 'path': path, 'requested_limit': cap,
                        'read_attempted': False, 'observed_bytes': 0, 'retained_prefix': None,
                        'complete_body': None, 'parse_complete': False, 'authenticated': False}
    def read_parse(self, store, expected):
        need(type(store) is Store and store.meter is self.owner.host, 'same already admitted host source store')
        need(not self._attempted, 'one original selection read attempt')
        self._attempted = True
        parent = self.owner.parent
        try:
            descriptor(expected)
            need(expected['path'] == self.capture['path'] and expected['bytes'] <= self.capture['requested_limit'],
                 'exact prior produced selection descriptor and cap')
            # Both complete input and parsed representation are reserved before
            # I/O/parse. A failed read retains the full irreversible allowance.
            self.owner.host.charge('retained_bytes', expected['bytes']*8 + 4096)
            self.capture['read_attempted'] = True
            raw = store.read(expected, self.capture['requested_limit'], metadata=True)
            self.raw = raw
            self.capture['observed_bytes'] = len(raw)
            self.capture['complete_body'] = dict(expected)
            body = parse(raw, self.capture['requested_limit'])
            self.body = body
            self.capture['parse_complete'] = True
            # Parsing a complete body is deliberately not independent issuer
            # authentication. The source-owned issuer consumer must do that.
            return body
        except BaseException as error:
            parent.retain(error, 'selection_parse' if self.raw is not None else 'selection_read',
                          'decode_failure' if self.raw is not None else 'read_failure',
                          'SelectionReadState.read_parse', None if self.raw is not None else 'read_bytes')
            raise

class FailureReturn:
    __slots__ = ('parent', 'prefix', 'publication', 'publication_error', '_token')
    def __init__(self, token, parent, prefix, publication, publication_error):
        need(token is _RETURN, 'actual fixed source failure return')
        self.parent, self.prefix, self.publication = parent, prefix, publication
        self.publication_error, self._token = publication_error, token

def _publish_complete(store, name, value, record_type, *, cap=None):
    # No participant encoder, recursive alias walk or custom exception text.
    bound = bounded_size(value)
    store.meter.charge('work_units', bound)
    store.meter.charge('retained_bytes', bound)
    validate_type(record_type, value)
    raw = encode(value)
    if cap is not None:
        integer(cap,1);need(len(raw)<=cap,'earlier selected complete output byte cap')
    expected = store.write(name, raw)
    observed = store.read(expected, len(raw)+1, metadata=True)
    need(observed == raw, 'complete original publication and bounded exact readback')
    return expected

def fail_v2(parent, error, *, attempt, phase, code, site, output_store=None, selection_state=None):
    need(type(parent) is ParentCustody, 'actual earlier parent custody')
    parent.retain(error, phase, code, site)
    # Raw first error is already owned before inspecting any supplied source
    # state or attempting clocks, projection, cleanup or publication.
    if parent.failure_publication_attempted:
        return parent.failure_return
    parent.failure_publication_attempted = True
    result = FailureReturn(_RETURN, parent, None, None, None)
    parent.failure_return = result
    prefix_pin = None
    publication_state = 'unattempted'
    try:
        owner = parent.owner
        if owner is None:
            # Failure before seed attachment has no trustworthy nested owner
            # or output authority. Preserve the original parent, without
            # manufacturing a secondary error merely to describe absence.
            return result
        need(type(owner) is EarlyResources, 'retained attempted EarlyResources')
        if owner.partitions is None or output_store is None or selection_state is None:
            # Before a trustworthy seed/capture/output root or terminal plan,
            # keep the actual parent and raw error. Do not invent a wire prefix.
            return result
        need(type(selection_state) is SelectionReadState and selection_state.owner is owner,
             'same actual source-owned selection read state')
        need(type(output_store) is Store and output_store.meter is owner.host,
             'same earlier private output root and live host meter')
        need(parent.selection is None, 'postselection failure requires the separately bound actual selection path')
        owner.enter_terminal()
        terminal = _store_view(output_store, owner.terminal_host)
        prefix = preselection_failure_v2(parent, attempt, selection_state.capture)
        result.prefix = prefix
        publication_state = 'unknown'
        prefix_pin = _publish_complete(terminal, 'preselection_failure_prefix.json', prefix, 'PreselectionFailurePrefix')
        publication_state = 'complete'
    except BaseException as later:
        # Never replace the initiating raw exception with publication failure.
        parent.retain(later, 'failure_publish', 'publication_failure', 'EarlyFailure.fail_v2')
        result.publication_error = later
        prefix_pin = None
        publication_state = 'failed'
    try:
        publication = {'schema': 'ci_failurepublication_v2', 'attempt': attempt,
                       'first_error_ordinal': 0, 'secondary_error_ordinals': list(range(1, len(parent.raw_errors))),
                       'state': publication_state, 'prefix_record': prefix_pin,
                       'cost_prefix': parent.owner.cost_prefix(), 'parent_custody_continues': True}
        validate_type('FailurePublication', publication)
        result.publication = publication
    except BaseException as later:
        parent.retain(later, 'failure_publish', 'publication_failure', 'EarlyFailure.return_projection')
        result.publication_error = later
        # No recursive publication of the publication's own failure.
    return result

def fail_after_selection_v3(parent,error,*,attempt,phase,code,site,output_store):
    """Actual postselection custody without a fabricated preparation outcome.

The original owner remains the primary result when any diagnostic publication
fails. Every emitted prefix names earlier completed diagnostic captures only.
"""
    need(type(parent) is ParentCustody,'actual same original parent after selection')
    parent.retain(error,phase,code,site)
    if parent.failure_publication_attempted:return parent.failure_return
    parent.failure_publication_attempted=True
    result=FailureReturn(_RETURN,parent,None,None,None);parent.failure_return=result
    prefix_pin=None;state='unattempted'
    try:
        from .backend_capture import CanonicalPublisher
        from .early_resources import failure_observations
        owner=parent.owner
        need(type(owner) is EarlyResources and parent.selection is not None and parent.binding_pin is not None,
             'actual authenticated selection and original owner before postselection failure')
        need(type(output_store) is Store and output_store.meter is owner.host,
             'same original fixed output root')
        owner.enter_terminal()
        terminal=_store_view(output_store,owner.terminal_host)
        publisher=CanonicalPublisher(owner,terminal,maximum_bytes=owner.plan['maximum_output_bytes'],
            maximum_members=owner.plan['maximum_members'],maximum_depth=owner.plan['maximum_depth'])
        parent.postselection_failure_publisher=publisher
        rows=failure_observations(parent)
        need(len(rows)<=1025,'bounded original diagnostic prefix; exhaustion stays private raw custody')
        diagnostic=[]
        for ordinal,row in enumerate(rows):
            state='unknown'
            capture=publisher.capture('postselection_failure_'+str(ordinal)+'.json','FailureObservation',row)
            diagnostic.append(capture.pin)
        prefix={'schema':'ci_failureprefix_v2','attempt':attempt,'selection':parent.selection,
            'early_owner_binding':parent.binding_pin,'last_phase':phase,'known_records':list(parent.known_records),
            'original_owner_failure':diagnostic[0],'ordered_secondary_failures':diagnostic[1:],
            'unknown_dimensions':sorted(parent.unknown),'charged_reservation_retained':True,
            'cost_prefix':owner.cost_prefix(),'dependent_execution_allowed':False}
        result.prefix=prefix
        prefix_pin=publisher.capture('postselection_failure_prefix.json','FailurePrefix',prefix).pin
        state='complete'
    except BaseException as later:
        parent.retain(later,'failure_publish','publication_failure','EarlyFailure.fail_after_selection_v3')
        result.publication_error=later;state='failed'
    try:
        result.publication={'schema':'ci_failurepublication_v2','attempt':attempt,'first_error_ordinal':0,
            'secondary_error_ordinals':list(range(1,len(parent.raw_errors))), 'state':state,
            'prefix_record':prefix_pin,'cost_prefix':parent.owner.cost_prefix(),'parent_custody_continues':True}
        validate_type('FailurePublication',result.publication)
    except BaseException as later:
        parent.retain(later,'failure_publish','publication_failure','EarlyFailure.postselection_projection')
        result.publication_error=later
    return result
