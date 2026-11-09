"""Single authoritative additive ledger; clients cannot reset per-process caps."""
import socket
from ach_resource_common import peer_identity, collect_errors
from ach_resource_admission import verify_peer
from ach_resource_endpoints import send_frame, receive_frame
from n079_common import fields, require, integer, identity, error_record
from n079_budget import Ledger, DIMENSIONS


class BudgetAuthority:
    def __init__(self, context, allocation, participants):
        require(context.role == 'observer', 'independent observer owns complete additive ledger')
        require(type(context.ledger) is Ledger, 'observer has only its bounded source-startup ledger')
        bootstrap = context.ledger.local
        self.context, self.ledger, self.participants = context, Ledger(allocation, context.clock), participants
        self.allocation_pin = identity(allocation, context.encoding_limits)
        require(self.allocation_pin == context.effect_admission['allocation_pin'], 'same complete observer allocation')
        self.sequences = {}; self.receipts = []
        for work_id, values in bootstrap.items():
            nonzero = {k: v for k, v in values.items() if v}
            if nonzero:
                self.ledger.charge(work_id, nonzero, 'actual observer source/bootstrap work')
        context.ledger = self.ledger; context.budget_authority = self

    def handle(self, request, actual_peer):
        fields(request, ('schema', 'participant', 'sequence', 'allocation_pin', 'source_pin', 'work_id', 'delta', 'reason', 'phase'))
        require(request['schema'] == 'n079_additive_charge_v1' and request['allocation_pin'] == self.allocation_pin,
                'one selected whole-study allocation')
        participant = request['participant']; require(participant in self.participants, 'admitted cost producer')
        selected = self.participants[participant]
        verify_peer(actual_peer, selected['identity'], self.context.profile, self.context.clock, request['phase'])
        require(request['source_pin'] == selected['source_pin'], 'same independently admitted producer source')
        sequence = integer(request['sequence'], 1)
        require(sequence == self.sequences.get(participant, 0) + 1, 'ordered once-only cost request, no silent retries')
        self.sequences[participant] = sequence
        require(request['work_id'] in selected['work_ids'] and set(request['delta']) <= set(selected['dimensions']),
                'source-selected producer work/dimension ownership')
        require(set(selected['dimensions']) <= set(DIMENSIONS), 'known actual additive counters')
        # Commit attempted charges centrally even when they exceed a ceiling.
        self.ledger.charge(request['work_id'], request['delta'], request['reason'], request['phase'])
        receipt = {'schema': 'n079_additive_reservation_v1', 'request_pin': identity(request, self.context.encoding_limits),
                   'allocation_pin': self.allocation_pin, 'sequence': sequence, 'participant': participant,
                   'whole_attempted': dict(self.ledger.actual), 'local_attempted': dict(self.ledger.local[request['work_id']])}
        self.receipts.append(receipt)
        # Server service loop durably writes request/receipt under its reserved
        # accounting overhead before sending this reply. No successful charge
        # is inferred by the client merely from its local attempted prefix.
        return receipt


class RemoteLedger:
    def __init__(self, context, selected, endpoints):
        fields(selected, ('socket', 'peer', 'participant', 'allocation_pin', 'endpoint', 'source_pin'))
        require(selected['peer'] == context.admission['selection']['peers']['observer'], 'same actual independent budget observer')
        require(selected['allocation_pin'] == context.effect_admission['allocation_pin'], 'same controller/provider whole allocation')
        require(selected['source_pin'] == context.source_pin, 'same full independently admitted source closure')
        self.context, self.selected, self.endpoints = context, selected, endpoints
        self.sequence = 0; self.pending = []; self.local = context.ledger.local
        self.admitted = False

    def charge(self, work_id, delta, reason, phase='scientific'):
        require(work_id in self.local and set(delta) <= set(DIMENSIONS), 'declared full work identity')
        self.sequence += 1
        request = {'schema': 'n079_additive_charge_v1', 'participant': self.selected['participant'],
                   'sequence': self.sequence, 'allocation_pin': self.selected['allocation_pin'],
                   'source_pin': self.context.source_pin, 'work_id': work_id, 'delta': delta, 'reason': reason, 'phase': phase}
        pending = {'request': request, 'response': None, 'status': 'attempted'}; self.pending.append(pending)
        attempt = self.endpoints.begin(self.selected['endpoint']); connection = None; first = None; reply = None
        try:
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.settimeout((getattr(self.context.clock, phase) - self.context.tick(phase)) / 1e9)
            connection.connect(self.selected['socket'])
            verify_peer(peer_identity(connection), self.selected['peer'], self.context.profile, self.context.clock, phase)
            send_frame(connection, request, self.context.profile, self.endpoints, attempt, self.context.clock, phase)
            reply, reply_raw = receive_frame(connection, self.context.profile, self.endpoints, attempt, self.context.clock, phase)
            pending['response'] = reply
            import base64
            pending['raw_response_base64'] = base64.b64encode(reply_raw).decode('ascii')
            fields(reply, ('schema', 'request_pin', 'allocation_pin', 'sequence', 'participant', 'whole_attempted', 'local_attempted'))
            require(reply['schema'] == 'n079_additive_reservation_v1' and
                    reply['request_pin'] == identity(request, self.context.encoding_limits) and
                    reply['allocation_pin'] == self.selected['allocation_pin'] and reply['sequence'] == self.sequence and
                    reply['participant'] == self.selected['participant'], 'actual centrally reserved exact operation')
            self.context.tick(phase); pending['status'] = 'reserved'
        except BaseException as error:
            first = error; pending['status'] = 'failed_or_unknown'
        first = collect_errors([] if connection is None else [('budget socket close', connection.close)], first)
        first = collect_errors([('budget endpoint closure', lambda: self.endpoints.end(attempt, failed=first is not None))], first)
        if first is not None:
            pending['status'] = 'failed_or_unknown'; pending['failure'] = error_record(first)
            first.n079_prefix = pending; raise first
        return reply

    def admit_startup(self, initial_local):
        require(not self.admitted, 'one exact bootstrap-cost transfer')
        for work_id, values in initial_local.items():
            nonzero = {k: v for k, v in values.items() if v}
            if nonzero:
                self.charge(work_id, nonzero, 'known source/live identity startup rereads')
        self.admitted = True

    def snapshot(self):
        return {'pending': list(self.pending), 'admitted': self.admitted,
                'whole_actual': 'owned by independent observer, never inferred from per-process local copies'}
