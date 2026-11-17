"""Concrete original HM H issuer, two-ended credit grant and physical prefix.

This is the H issuer only. Actual HM W dispatch/HR1 process closure and final
whole-H reconciliation remain separate producers. No W aggregate is borrowed
as H own-process CPU, and no response claims a future C bridge-exit observation.
"""
import os
import time
from .common import need, closed, integer, encode, parse, pin, Store
from .channel import HostEndpoint
from .roots import BoundRoots
from .resources import RootResources, Share
from .identity import process_identity
from . import dependencies
from .hm_issuer_transport_v1 import (_module, _plan, _split, HMFrameCreditV1,
    HMTransportMeterV1, HMOwnProcessSpanV1, HMChannelConstructionV1, _CREDIT, _CUSTODY)

_HOST = object()
_OWNERS = {}


class HMIssuerHostV1:
    def __init__(self, token, *, session, plan, resources, roots, bootstrap, controller, identity):
        need(token is _HOST, 'fixed actual HM host issuer factory')
        self.session = session;self.plan = plan;self.resources = resources;self.roots = roots
        self.bootstrap = bootstrap;self.controller = parse(encode(controller), 131072)
        self.identity = parse(encode(identity), 131072);self.pid = os.getpid()
        self.endpoint = None;self.meter = HMTransportMeterV1(self, bootstrap)
        self.raw_first = None;self.secondaries = [];self.spans = []
        self.bootstrap_entered = False;self.bootstrap_complete = False
        self.slots = {};self.close_entered = False;self.close_complete = False
        self._plan_raw = encode(plan.body);self._binding_raw = None
    def retain(self, error, site):
        if self.raw_first is None:self.raw_first = error
        elif error is not self.raw_first:self.secondaries.append((error, site))
    def require_original(self):
        construction = getattr(self, 'construction', None)
        need(_OWNERS.get(id(self)) is self and self.resources.hm_issuer_owner_v1 is self and
             type(construction) is HMChannelConstructionV1 and construction.owner is self and
             construction.endpoint is True and construction.complete and construction.channel is self.endpoint and
             type(self.endpoint) is HostEndpoint and self.endpoint.meter is self.meter and
             self.meter.owner is self and os.getpid() == self.pid and
             not self.close_entered and not self.session.closed and
             encode(self.plan.body) == self._plan_raw and encode(self.endpoint.binding) == self._binding_raw,
             'same original source-created H issuer and original H endpoint')
        if self.raw_first is not None:raise self.raw_first
        return self
    def close_owned_once(self, primary=None):
        construction = getattr(self, 'construction', None)
        need(_OWNERS.get(id(self)) is self and type(construction) is HMChannelConstructionV1 and
             construction.owner is self and construction.endpoint is True and
             type(construction.channel) is HostEndpoint and construction.channel.meter is self.meter,
             'only actual retained H endpoint construction owns cleanup')
        if primary is not None:self.retain(primary, 'caller_primary')
        if self.endpoint is not construction.channel:
            try:need(False, 'original H endpoint replaced after construction')
            except BaseException as error:self.retain(error, 'endpoint_custody_loss')
        if not construction.complete:
            return construction.close_failed_once(primary=self.raw_first)
        if not self.close_entered:
            self.close_entered = True
            try:construction.channel.close();self.close_complete = True
            except BaseException as error:self.retain(error, 'endpoint_close')
        if self.raw_first is not None:raise self.raw_first
        return self.close_complete
    def serve_bootstrap_once(self):
        self.require_original();need(not self.bootstrap_entered, 'one original issuer bootstrap attempt')
        self.bootstrap_entered = True
        try:
            request = self.endpoint.accept();body = request['body']
            need(body['operation'] == 'continuation', 'fixed issuer bootstrap operation')
            incoming = body['body'];closed(incoming, ('schema', 'reservation_plan', 'controller'))
            need(incoming == {'schema': 'hm_issuer_credit_bootstrap_request_v1',
                'reservation_plan': self.plan.pin, 'controller': self.controller},
                'actual original complete C bootstrap request')
            grants = []
            for sequence in (1, 2, 3):
                t = self.plan.stage(sequence);row = self.plan.rows[t['issuer_host_row']];a = row['issuance']
                share = self.resources.share('H', row['stage']);split = _split(a)
                need(type(share) is Share and share.row['reservation_id'] == row['adapter_reservation_id'] and
                     all(value == 0 for value in share.spent.values()),
                     'one previously unspent actual H parent issuer/dispatch counter owner')
                grant = {'slot': a['slot'], 'host_row': t['issuer_host_row'], 'window': a['window'],
                         'split': split, 'reservation_plan': self.plan.pin}
                self.slots[a['slot']] = {'sequence': sequence, 'grant': grant, 'share': share,
                    'entered': False, 'returned': False, 'complete': False, 'raw_first': None,
                    'request': None, 'response_pin': None, 'return': None, 'ack_pin': None,
                    'span': None, 'credit': None, 'products': {}, 'raw_products': {}}
                self.slots[a['slot']]['physical_accounted'] = False
                # Attach each attempted debit before effects; failures preserve
                # the exact slot plus actual Share's attempted charge prefix.
                slot = self.slots[a['slot']];slot['reservation_attempts'] = [];slot['reservation_complete'] = False
                for kind, amount in split['total'].items():
                    attempt = {'kind': kind, 'amount': amount, 'returned': False, 'error': None}
                    slot['reservation_attempts'].append(attempt)
                    try:share.charge(kind, amount);attempt['returned'] = True
                    except BaseException as error:
                        attempt['error'] = error;slot['raw_first'] = error;raise
                slot['reservation_complete'] = True
                grants.append(grant)
            result = {'schema': 'hm_issuer_credit_bootstrap_response_v1',
                'reservation_plan': self.plan.pin, 'controller': self.controller, 'slots': grants}
            self.bootstrap_response = self.endpoint.respond(request, status='observed', result=result)
            self.bootstrap_complete = True;return self.bootstrap_response
        except BaseException as error:self.retain(error, 'issuer_bootstrap');raise self.raw_first
    def _logical_prefix(self, row):
        spent = row['share'].spent
        return {'read_bytes': spent['read_bytes'], 'write_bytes': spent['write_bytes'], 'work': spent['work_units']}
    def serve_next_issuer_once(self):
        self.require_original();need(self.bootstrap_complete, 'original complete bootstrap grant before issuer spend')
        remaining = [self.slots[k] for k in ('IR', 'IA', 'IB') if not self.slots[k]['entered']]
        need(remaining, 'no fourth issuer opportunity')
        row = remaining[0];row['entered'] = True
        need(all(self.slots[k]['complete'] for k in ('IR', 'IA', 'IB')[:row['sequence'] - 1]),
             'all earlier original issuer transfers must be complete')
        t = self.plan.stage(row['sequence']);a = self.plan.rows[t['issuer_host_row']]['issuance']
        credit = HMFrameCreditV1(_CREDIT, self, a['slot'], 'H', row['grant']['split']['H'], a['window'])
        row['credit'] = credit;primary = None
        try:
            self.meter.select(credit)
            row['span'] = HMOwnProcessSpanV1(self, 'H_issuer_own_process', a['window'], a['physical']['cpu_ns'])
            row['span'].begin_once()
            request = self.endpoint.accept();row['request'] = request
            need(request['body']['operation'] == 'continuation', 'actual original issuer request operation')
            body = request['body']['body']
            closed(body, ('schema', 'slot', 'request', 'invocation', 'C_entry', 'credit_grant'))
            need(body['schema'] == 'hm_original_issuer_request_v1' and body['slot'] == a['slot'] and
                 body['credit_grant'] == row['grant'], 'same original grant and next source-owned issuer slot')
            im = _module(self.session, 'issuance');ident = _module(self.session, 'identity_contract')
            request_body = im['wire'](body['request'], 'IssuanceRequest');invocation = body['invocation']
            need(request_body['controller'] == self.controller and request_body['sequence'] == row['sequence'] and
                 request_body['reservation_plan'] == self.plan.pin and request_body['issuer_slot'] == a['slot'] and
                 request_body['stage'] == t['stage'], 'complete original selected C invocation and issuer interval')
            entry = body['C_entry'];closed(entry, ('monotonic_ns', 'process_cpu_ns', 'pid'))
            need(entry['pid'] == self.controller['pid'] and
                 a['window']['start_ns'] <= entry['monotonic_ns'] <= time.monotonic_ns() < a['window']['stop_ns'],
                 'qualified original C bridge entry before actual H request capture')
            integer(entry['process_cpu_ns'])
            root = self.roots.roots['R'];store = Store(root, credit, forbidden=self.roots.stores['R'].forbidden)
            subject_raw = store.read(request_body['subject'], a['metadata_member_cap'], metadata=True)
            subject = ident['decode'](subject_raw, 'Subject', cap=a['metadata_member_cap'], meter=im['_IssuerMeter'](credit))
            ident['validate_subject'](subject, invocation=invocation, plan=self.plan)
            guard_raw = store.read(request_body['guard_state'], a['metadata_member_cap'], metadata=True)
            guard = parse(guard_raw, a['metadata_member_cap'])
            sm = _module(self.session, 'stage_budget');sm['state_valid'](guard, self.plan)
            need(guard_raw == encode(guard) and guard['mode'] == 'active_C' and not guard['failed'] and
                 guard['generation'] == t['base_generation'], 'actual complete original C guard snapshot')
            stamp = time.monotonic_ns()
            selection = {'schema': 'hundred_models_root_subject_selection_v4',
                'subject': request_body['subject'], 'root_issuer_source': self.plan.body['root_issuer_source'],
                'issuer_qualification': a['issuer_qualification'], 'source_admission': a['source_admission'],
                'clock_binding': self.plan.body['clock_binding'], 'issued_monotonic_ns': stamp,
                'decision': 'admit_exact_subject', 'reservation_plan': self.plan.pin, 'issuance_slot': a['slot'],
                'host_row': t['issuer_host_row'], 'adapter_reservation_id': self.plan.rows[t['issuer_host_row']]['adapter_reservation_id'],
                'issuer_window': a['window']}
            ident['typed'](selection, 'RootSelection')
            prefix = 'hm_issuer_' + a['slot']
            sr = ident['canonical'](selection);sd = store.write(prefix + '_root_selection.json', sr)
            row['products']['RootSelection'] = sd;row['raw_products']['RootSelection'] = sr
            authority = {'schema': 'hundred_models_stage_invocation_authority_v4', **invocation,
                         'pre_run_subject': request_body['subject'], 'root_selection': sd}
            ident['typed'](authority, 'InvocationAuthority')
            ar = ident['canonical'](authority);ad = store.write(prefix + '_invocation_authority.json', ar)
            row['products']['InvocationAuthority'] = ad;row['raw_products']['InvocationAuthority'] = ar
            physical = {'schema': 'hm_original_issuer_physical_prefix_v1', 'slot': a['slot'],
                'request': pin(encode(request_body)), 'reservation_plan': self.plan.pin, 'host_row': t['issuer_host_row'],
                'H_identity': self.identity, 'C_identity': self.controller, 'H_prefix': row['span'].observe_prefix(),
                'C_entry': entry, 'full_reservation_retained': True, 'C_exit_not_yet_observed': True,
                'whole_physical_reconciliation_required': True}
            pr = encode(physical);pd = store.write(prefix + '_physical_prefix.json', pr)
            row['products']['PhysicalPrefix'] = pd;row['raw_products']['PhysicalPrefix'] = pr
            stamp = time.monotonic_ns();logical = self._logical_prefix(row)
            need(a['window']['start_ns'] <= stamp < a['window']['stop_ns'], 'actual original response-prefix cut')
            response = {'schema': 'hundred_models_prelease_issuer_response_v4',
                **{key: request_body[key] for key in ('campaign_id', 'sequence', 'stage', 'reservation_plan',
                    'issuer_slot', 'controller', 'subject', 'guard_state')},
                'request': pin(encode(request_body)), 'issuer_source': self.plan.body['root_issuer_source'],
                'disposition': 'issued', 'root_selection': sd, 'invocation_authority': ad,
                'issuer_logical_attempted_prefix': logical, 'parent_logical_attempted_prefix': logical,
                'physical_observation_prefix': pd, 'response_prefix_observed_ns': stamp,
                'issued_objects': [sd, ad, pd], 'original_failure': None, 'cleanup_errors': [], 'unknown_dimensions': []}
            im['wire'](response, 'IssuanceResponse')
            rr = encode(response);rd = store.write(prefix + '_response.json', rr)
            row['products']['IssuanceResponse'] = rd;row['raw_products']['IssuanceResponse'] = rr
            row['products']['Subject'] = request_body['subject'];row['raw_products']['Subject'] = subject_raw
            result = {'schema': 'hundred_models_issuer_document_transport_v1', 'response': rd,
                'documents': [{'kind': kind, 'descriptor': row['products'][kind], 'hex': row['raw_products'][kind].hex()}
                    for kind in im['KINDS']]}
            row['response_pin'] = self.endpoint.respond(request, status='observed', result=result)
            returned = self.endpoint.accept();rb = returned['body']['body'];row['return'] = returned
            need(returned['body']['operation'] == 'continuation', 'fixed original credit return operation')
            closed(rb, ('schema', 'slot', 'response', 'request', 'C_prefix', 'credit_prefix', 'remaining_credit_fully_reserved'))
            need(rb['schema'] == 'hm_issuer_credit_return_v1' and rb['slot'] == a['slot'] and
                 rb['response'] == row['response_pin'] and rb['request'] == pin(encode(request_body)) and
                 rb['remaining_credit_fully_reserved'] is True, 'same actual original returned credit and full retained remainder')
            cp = rb['credit_prefix'];closed(cp, ('slot', 'side', 'limits', 'attempted', 'entered', 'closed',
                'full_H_reservation_retained', 'failure'))
            need(cp['slot'] == a['slot'] and cp['side'] == 'C' and cp['limits'] == row['grant']['split']['C'] and
                 cp['entered'] is True and cp['closed'] is False and cp['failure'] is None and
                 cp['full_H_reservation_retained'] is True, 'actual authenticated source C credit prefix; no refund')
            closed(cp['attempted'], cp['limits'])
            for kind, amount in cp['attempted'].items():integer(amount);need(amount <= cp['limits'][kind], 'C attempted prefix fits prior grant')
            cspan = rb['C_prefix'];closed(cspan, ('role', 'begin', 'observed', 'cpu_ns', 'wall_ns', 'complete'))
            need(cspan['role'] == 'C_issuer_bridge' and cspan['begin'] == entry and cspan['complete'] is False and
                 cspan['observed']['pid'] == self.controller['pid'] and
                 entry['monotonic_ns'] <= cspan['observed']['monotonic_ns'] < a['window']['stop_ns'] and
                 cspan['cpu_ns'] == cspan['observed']['process_cpu_ns'] - entry['process_cpu_ns'] and
                 cspan['wall_ns'] == cspan['observed']['monotonic_ns'] - entry['monotonic_ns'],
                 'distinct actual source C bridge prefix before its remaining reserved return/ack tail')
            integer(cspan['cpu_ns']);integer(cspan['wall_ns'])
            need(cspan['cpu_ns'] <= self.plan.rows[t['issue_from']]['physical']['cpu_ns'], 'original C physical prefix ceiling')
            row['returned'] = True
            row['ack_pin'] = self.endpoint.respond(returned, status='observed', result={
                'schema': 'hm_issuer_credit_return_ack_v1', 'slot': a['slot'], 'response': row['response_pin'],
                'request': pin(encode(request_body)), 'return_prefix': pin(encode(rb)), 'full_reservation_retained': True})
        except BaseException as error:
            primary = error;row['raw_first'] = error;self.retain(error, 'H_issuer_transfer')
        finally:
            if row['span'] is not None and not row['span'].end_entered:
                try:row['span'].finish_once()
                except BaseException as error:
                    if primary is None:primary = error;row['raw_first'] = error
                    self.retain(error, 'H_issuer_exit')
            if row['span'] is not None and row['span'].end_entered:
                try:self._account_H_span_once(row)
                except BaseException as error:
                    if primary is None:primary = error;row['raw_first'] = error
                    self.retain(error, 'H_issuer_physical_account')
            if self.meter.credit is credit:
                try:self.meter.release(credit)
                except BaseException as error:
                    if primary is None:primary = error;row['raw_first'] = error
                    self.retain(error, 'H_credit_close')
        if primary is not None:raise primary
        row['complete'] = True;return row['ack_pin']
    def _account_H_span_once(self, row):
        need(not row['physical_accounted'], 'one H own-process span debit to its actual parent Share')
        row['physical_accounted'] = True;span = row['span'];share = row['share']
        need(type(span) is HMOwnProcessSpanV1 and span.owner is self and span.role == 'H_issuer_own_process' and
             type(share) is Share and share._active is None,
             'actual H issuer span disjoint from later dispatch/worker-monitor span')
        for clock, dimension in (('process_cpu_ns', 'cpu_ns'), ('monotonic_ns', 'wall_ns')):
            if span.begin is None or span.begin[clock] is None or span.end is None or span.end[clock] is None:
                share.unknown.add('hm_issuer_' + dimension);continue
            delta = span.end[clock] - span.begin[clock];need(delta >= 0, 'original H nonnegative actual own-process usage')
            setattr(share, dimension, getattr(share, dimension) + delta)
        need(not share.unknown and share.cpu_ns <= share.row['cpu_ns'] and share.wall_ns <= share.row['wall_ns'],
             'same original H physical issuer+dispatch cap; unknown never becomes zero')
    def require_dispatch_ready(self, slot, lease):
        self.require_original();need(slot in self.slots, 'one original issuer slot')
        row = self.slots[slot]
        need(row['complete'] and row['returned'] and row['raw_first'] is None and row['span'].complete and
             row['credit'].closed and lease['invocation_authority'] == row['products']['InvocationAuthority'] and
             lease['authority_subject'] == row['products']['Subject'] and lease['sequence'] == row['sequence'] and
             lease['reservation_plan'] == self.plan.pin,
             'same original fully closed H issuer and exact later lease, not a manufactured ready flag')
        return row


def open_hm_issuer_host_v1(*, session, plan, resources, roots, read_fd, write_fd,
        binding, selected_qualification, controller, host_identity, mapping):
    _plan(session, plan)
    need(type(resources) is RootResources and not resources.staged and resources.plan == plan.root and
         resources.pin == plan.root_pin and getattr(resources, 'hm_issuer_owner_v1', None) is None,
         'one original whole H owner and exact selected complete resource plan')
    need(type(roots) is BoundRoots and set(roots.roots) == {'R'} and roots.relative_base == 'R',
         'one actual earlier explicit HM metadata namespace')
    dependencies.require('hm_issuer_transport_native_qualification', plan.body['native_qualification'])
    bootstrap = resources.share('H', plan.rows['H00']['stage'])
    need(type(bootstrap) is Share and binding['source'] == plan.body['root_issuer_source'] and
         binding['campaign'] == plan.body['campaign_id'] and binding['launch'] == controller['parent_launch'] and
         mapping['source'] == plan.body['clock_binding'], 'same actual H bootstrap and original channel/clock domains')
    for identity in (host_identity, controller):
        actual = process_identity(identity['pid'], launch_nonce=identity['launch_nonce'], source=identity['source'],
            parent_launch=identity['parent_launch'], mapping=mapping, meter=bootstrap)
        need(actual == identity, 'actual original H/C process identity observed by H')
    need(host_identity['pid'] == os.getpid() and host_identity['source'] == plan.body['root_issuer_source'] and host_identity != controller,
         'this actual H process is distinct from original C')
    owner = HMIssuerHostV1(_HOST, session=session, plan=plan, resources=resources, roots=roots,
        bootstrap=bootstrap, controller=controller, identity=host_identity)
    resources.hm_issuer_owner_v1 = owner
    owner.endpoint = object.__new__(HostEndpoint)
    owner._binding_raw = encode(binding);_OWNERS[id(owner)] = owner
    construction = HMChannelConstructionV1(_CUSTODY, owner, owner.endpoint, endpoint=True)
    construction.initialize_once(read_fd, write_fd, binding=binding,
        selected_qualification=selected_qualification)
    owner.require_original();return owner
