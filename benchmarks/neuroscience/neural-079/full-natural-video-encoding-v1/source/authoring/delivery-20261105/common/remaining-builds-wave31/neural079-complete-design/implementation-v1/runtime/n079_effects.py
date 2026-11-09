"""Concrete effect gate, durable journal and authenticated bounded Unix exchange.

Deployment authenticity/custody is an independently selected trust boundary;
metadata flags or hashes do not establish it. Default source is inactive.
"""
import os
import socket
import stat
from ach_resource_common import Clock, peer_identity, bounded_encode, bounded_decode, close_all, collect_errors
from ach_resource_admission import source_admission, verify_peer
from ach_resource_endpoints import Endpoints, send_frame, receive_frame
from n079_common import require, fields, integer, checked_pin, pin, identity, error_record
from n079_budget import Ledger


class Journal:
    def __init__(self, directory, name, context, work_id, maximum):
        self.context, self.work_id, self.maximum = context, work_id, integer(maximum, 1)
        self.parent = None; self.fd = None; self.written = 0; self.sequence = 0; self.closed = False
        require(type(name) is str and name not in ('', '.', '..') and '/' not in name and '\\' not in name, 'one journal name')
        try:
            context.tick()
            from n079_observer import open_directory
            self.parent = open_directory(directory)
            require(stat.S_ISDIR(os.fstat(self.parent).st_mode), 'actual protected journal directory')
            self.fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.parent)
            status = os.fstat(self.fd); self.observed_identity = {'device': status.st_dev, 'inode': status.st_ino}
            os.fsync(self.parent)
        except BaseException as error:
            self.close(error); raise

    def append(self, kind, payload, phase='scientific'):
        require(not self.closed, 'owned live journal')
        row = {'sequence': self.sequence, 'kind': kind, 'payload': payload}
        raw = bounded_encode(row, self.context.encoding_limits) + b'\n'
        require(self.written + len(raw) <= self.maximum, 'complete journal byte ceiling')
        self.context.ledger.charge(self.work_id, {'write_bytes': len(raw), 'log_bytes': len(raw)},
                                   'journal record before write', phase)
        self.written += len(raw); self.sequence += 1
        self.context.tick(phase); done = 0
        while done < len(raw):
            self.context.tick(phase); count = os.write(self.fd, raw[done:])
            require(count > 0, 'full journal write'); done += count
        os.fsync(self.fd); self.context.tick(phase)
        return pin(raw)

    def close(self, primary=None):
        if self.closed:
            return
        self.closed = True; fd, parent = self.fd, self.parent; self.fd = self.parent = None
        operations = []
        if fd is not None:
            operations += [('journal fsync', lambda: os.fsync(fd)), ('journal close', lambda: os.close(fd))]
        if parent is not None:
            operations += [('journal parent fsync', lambda: os.fsync(parent)), ('journal parent close', lambda: os.close(parent))]
        close_all(operations, primary)


class AuthorityClient:
    def __init__(self, context, selected, endpoint):
        fields(selected, ('socket', 'peer', 'source_pin', 'maximum_reply_bytes', 'allowed_kinds'))
        checked_pin(selected['source_pin']); integer(selected['maximum_reply_bytes'], 1)
        require(context.profile['encoding_limits']['bytes'] <= selected['maximum_reply_bytes'], 'selected whole frame capacity')
        require(selected['peer'] == context.admission['selection']['peers']['issuer'], 'same independent issuer process')
        self.context, self.selected, self.endpoint = context, selected, endpoint
        self.pending = []; self.sequence = 0

    def exchange(self, kind, payload, phase='scientific'):
        require(kind in self.selected['allowed_kinds'], 'source-selected issuer exchange kind')
        self.context.tick(phase); self.sequence += 1
        request = {'schema': 'n079_issuer_request_v1', 'sequence': self.sequence, 'kind': kind,
                   'source_pin': self.context.source_pin, 'payload': payload}
        attempt = self.endpoint.begin(self.context.issuer_endpoint)
        pending = {'request': request, 'reply': None, 'validation': 'not_reached', 'failure': None}
        self.pending.append(pending); connection = None; first = None; reply = None
        try:
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.settimeout((getattr(self.context.clock, phase) - self.context.tick(phase)) / 1e9)
            connection.connect(self.selected['socket'])
            verify_peer(peer_identity(connection), self.selected['peer'], self.context.profile, self.context.clock, phase)
            send_frame(connection, request, self.context.profile, self.endpoint, attempt, self.context.clock, phase)
            reply, reply_raw = receive_frame(connection, self.context.profile, self.endpoint, attempt, self.context.clock, phase)
            pending['reply'] = reply
            import base64
            pending['raw_reply_base64'] = base64.b64encode(reply_raw).decode('ascii')
        except BaseException as error:
            first = error; pending['failure'] = error_record(error)
        # Exact received reply survives close failure. Validate/journal are
        # independent cleanup/evidence attempts, never allowed to erase it.
        def validate():
            if reply is None:
                return
            fields(reply, ('schema', 'request_pin', 'issuer_source_pin', 'decision', 'evidence'))
            require(reply['schema'] == 'n079_issuer_response_v1' and reply['issuer_source_pin'] == self.selected['source_pin'] and
                    reply['request_pin'] == identity(request, self.context.encoding_limits), 'same authenticated request/source reply')
            require(reply['decision'] in ('admit', 'refuse'), 'typed independent issuer decision')
            checked_pin(reply['evidence']); pending['validation'] = 'authenticated_joined'
        operations = []
        if connection is not None:
            operations.append(('issuer socket close', connection.close))
        operations += [('issuer reply validation', validate)]
        first = collect_errors(operations, first)
        pending['failure'] = None if first is None else error_record(first)
        first = collect_errors([('issuer exact exchange retention',
            lambda: self.context.journal.append('issuer_exchange', pending, phase))], first)
        first = collect_errors([('issuer endpoint closure',
            lambda: self.endpoint.end(attempt, failed=first is not None))], first)
        if first is not None:
            first.n079_prefix = pending; raise first
        require(reply is not None and pending['validation'] == 'authenticated_joined' and reply['decision'] == 'admit',
                'independently admitted effect')
        self.context.tick(phase); return reply['evidence']


ROLE_EFFECTS = {
    'assembler': {'prepare_targets', 'recording_read', 'array_read', 'array_write', 'numeric_state'},
    'features': {'visual_model', 'array_read', 'array_write', 'numeric_state'},
    'grams': {'array_read', 'array_write', 'numeric_state'},
    'references': {'array_read', 'array_write', 'numeric_state', 'reference_fit'},
    'controller': {'candidate_job', 'policy_provider', 'report_provider', 'array_read', 'array_write', 'numeric_state'},
    'supervisor': {'candidate_job', 'native_job', 'array_read'},
    'provider': {'provider_http'},
    'observer': {'resource_read'},
    'issuer': {'custody_read'},
    'grader': {'array_read', 'array_write', 'numeric_state', 'grade_targets'},
    'finalizer': {'resource_read', 'outer_closeout'},
}


class EffectContext:
    def __init__(self, selected):
        require(type(selected) is dict and selected.get('execution_enabled') is True,
                'NEURAL079 deployment disabled before source/host/data/library/key effects')
        fields(selected, ('execution_enabled', 'clock', 'profile', 'source_admission', 'allocation', 'role',
                           'effect_admission', 'encoding_limits', 'storage_reservation_limit', 'issuer_endpoint'))
        fields(selected['clock'], ('origin', 'scientific', 'closeout', 'outer'))
        self.clock = Clock(**selected['clock']); self.profile = selected['profile']
        self.encoding_limits = selected['encoding_limits']; self.role = selected['role']
        require(self.role in ROLE_EFFECTS, 'named complete scientific role')
        require(self.encoding_limits == self.profile['encoding_limits'], 'same bounded protocol encoding')
        self.allocation = selected['allocation']; self.ledger = Ledger(self.allocation, self.clock)
        # Ordinary source/receipt/live-proc rereads are known logical metadata
        # work, not silently excluded under a terminal reporting boundary.
        source = selected['source_admission']; maximum = self.profile['reader_limits']['file_bytes']
        source_cost = sum(row['pin']['bytes'] for row in source['sources']) + 4 * maximum + 16 * maximum
        work = {'features': 'raw-all17-features', 'grams': 'feature-grams', 'issuer': 'custody-issuer',
                'provider': 'provider-proxy', 'grader': 'target-last-grader', 'references': 'reference/sub-01/measured'}.get(self.role, self.role)
        require(work in self.ledger.local, 'explicit source-startup work allocation')
        self.ledger.charge(work, {'source_read_bytes': source_cost}, 'full source/receipt/live identity admission bound')
        self.admission = source_admission(source, self.profile, self.clock)
        require(source['role'] == self.role, 'actual admitted role matches scientific effects')
        self.source_pin = self.admission['source_pin']
        effect = selected['effect_admission']
        fields(effect, ('source_pin', 'study_pin', 'allocation_pin', 'role', 'operations', 'issuer_evidence'))
        require(effect['source_pin'] == self.source_pin and effect['role'] == self.role and
                effect['operations'] == sorted(ROLE_EFFECTS[self.role]) and
                effect['allocation_pin'] == identity(selected['allocation'], self.encoding_limits), 'complete source/effect/allocation join')
        checked_pin(effect['issuer_evidence']); checked_pin(effect['study_pin'])
        # External protected issuer custody must authenticate this exact
        # per-role rule before population; the later issuer_evidence is bound by
        # the actual outer release/gate/configuration chain, without a hash cycle.
        require(self.admission['receipts']['custody_receipt']['n079_effect_rules'][self.role] ==
                {k: v for k, v in effect.items() if k != 'issuer_evidence'}, 'independent custody receipt binds exact N079 effects')
        self.effect_admission = effect; self.storage_limit = integer(selected['storage_reservation_limit'], 1)
        self.storage_reserved = 0; self.issuer_endpoint = selected['issuer_endpoint']
        self.journal = None; self.authority = None; self.closed = False

    def tick(self, phase='scientific'):
        return self.clock.tick(phase)

    def require_effect(self, effect, work_id):
        require(not self.closed and effect in ROLE_EFFECTS[self.role] and work_id in self.ledger.local, 'admitted role/work effect')
        from n079_budget_service import RemoteLedger, BudgetAuthority
        observer = getattr(self, 'budget_authority', None)
        require(type(self.ledger) is RemoteLedger and self.ledger.admitted or
                self.role == 'observer' and type(observer) is BudgetAuthority and observer.context is self and self.ledger is observer.ledger,
                'single whole-study budget authority before scientific/host effects')
        self.tick()

    def bind_budget(self, selected, endpoints):
        from n079_budget_service import RemoteLedger
        require(type(self.ledger) is Ledger, 'one initial bounded startup ledger')
        previous = self.ledger
        remote = RemoteLedger(self, selected, endpoints)
        remote.admit_startup(previous.local)
        self.ledger = remote

    def reserve_storage(self, amount, work_id):
        integer(amount); require(work_id in self.ledger.local, 'named complete output allocation')
        self.storage_reserved += amount
        require(self.storage_reserved <= self.storage_limit, 'prospective owned logical storage reservation')
        self.tick()

    def join_feature_admission(self, selection):
        require(self.authority is not None, 'independent issuer before model/decoder access')
        return self.authority.exchange('feature_environment', selection)

    def write_numeric_state(self, work_id, name, array, lineage):
        self.require_effect('numeric_state', work_id)
        # Concrete state writer is installed only by the owned producer with
        # its selected ordinary directory, never supplied by candidate code.
        from n079_state import write_state
        return write_state(self, work_id, name, array, lineage)

    def record_numeric_digest(self, work_id, name, arrays, lineage):
        self.require_effect('numeric_state', work_id)
        from n079_state import digest_record
        result = digest_record(self, work_id, arrays, lineage)
        self.journal.append('reconstructible_numeric_block', {'name': name, 'record': result})
        return result
