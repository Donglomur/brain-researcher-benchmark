"""Synchronous parent publication before the unchanged Provider releases work."""
from pathlib import Path
import re
import time
from common import (CONDITIONS, EVENT_CAP, JOURNAL_CAP, OwnerWriter, body, descriptor, encoded,
                    need, ordinary, pin, publish)

EVENTS = {'OWNERSHIP', 'CLI-INTENT', 'CLI-CHILD', 'RESOURCE-INTENT',
          'CREATE-ATTEMPT', 'RESOURCE-ACK', 'PHASE-CLOSURE'}


class ParentJournal:
    def __init__(self, folder, invocation, invocation_pin, source, legacy, custody, writer):
        self.folder = ordinary(folder)
        self.invocation, self.invocation_pin = invocation, invocation_pin
        self.source, self.legacy, self.custody = source, legacy, custody
        self.writer = writer
        self.sequence = self.bytes = 0
        self.prepared, self.ownership, self.indices, self.intents = {}, {}, {}, {}
        self.closed = set()
        self.controller_ready = False
        self.done = None

    def _prepared(self, value):
        need(self.controller_ready and type(value) is dict and set(value) == {'request', 'request_file'},
             'Prepared exact request from active controller')
        request = value['request']
        phase = request['phase_id']
        need(phase in CONDITIONS and phase not in self.prepared, 'Both unique full conditions')
        protocol, runtime = self.legacy.admit_protocol(self.invocation['protocol_path'],
                                                     self.invocation['protocol_pin']['sha256'])
        expected = {'schema': 'osl_owned_phase_request_v1', 'phase_id': phase,
            'action': 'held_attempt', 'role': 'A' if phase == CONDITIONS[0] else 'B',
            'image': runtime['image'], 'command': self.legacy.COMMAND, 'workdir': '/work',
            'source': protocol['source'], 'exposure': request['exposure'],
            'clock': {'origin': self.invocation['clock']['origin'],
                      'phase_deadline': self.invocation['clock']['controller_deadline']},
            'resources': self.legacy.resources(protocol['outcome'], runtime),
            'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
        need(request == expected, 'Exact source, programme outcome, profile and retained clock')
        descriptor(request['exposure'])
        request_path = Path(self.invocation['output']) / 'jobs' / phase / 'REQUEST.json'
        need(pin(body(request_path)) == value['request_file']
             and self.legacy.read(request_path) == request, 'Exact owned saved request')
        exposure_path = request_path.parent / 'EXPOSURE.json'
        need(pin(body(exposure_path)) == request['exposure'], 'Exact owned exposure before native release')
        self.prepared[phase] = request
        self.indices[phase] = 0

    def _provider(self, name, value):
        need(name in EVENTS and type(value) is dict and set(value) == {'record', 'pin'},
             'Closed unchanged Provider callback schema')
        row = value['record']
        phase = row['phase_id']
        need(phase in self.prepared and set(self.prepared) == set(CONDITIONS),
             'Both frozen requests precede any native phase')
        request_pin = pin(encoded(self.prepared[phase]))
        need(set(row) == {'schema', 'phase_id', 'request_sha256', 'index', 'event', 'value'}
             and row['schema'] == 'osl_transport_journal_v1' and row['event'] == name
             and row['request_sha256'] == request_pin['sha256']
             and type(row['index']) is int and row['index'] == self.indices[phase]
             and pin(encoded(row)) == descriptor(value['pin']), 'Exact contiguous Provider record identity')
        event = row['value']
        if name == 'OWNERSHIP':
            need(phase not in self.ownership and row['index'] == 0,
                 'Durable resource ownership is first and unique')
            own = event['ownership']
            need(set(event) == {'ownership_pin', 'ownership'}
                 and pin(encoded(own)) == descriptor(event['ownership_pin'])
                 and set(own) == {'schema', 'phase_id', 'request_pin', 'engine_source_pin',
                                 'original_deadline', 'phase_deadline', 'attempt_prefix', 'resources'}
                 and own['schema'] == 'osl_phase_ownership_v1' and own['phase_id'] == phase
                 and own['request_pin'] == request_pin
                 and own['engine_source_pin']['sha256'] == self.legacy.TRANSPORT_SHA
                 and own['original_deadline'] == self.invocation['clock']['deadline']
                 and time.monotonic() < own['phase_deadline'] <= self.invocation['clock']['controller_deadline'],
                 'Exact resource ownership within preactivation clock')
            prefix = own['attempt_prefix']
            need(type(prefix) is str and re.fullmatch('osl-[0-9a-f]{24}', prefix), 'Exact owned resource prefix')
            expected = {key: {'kind': 'volume' if key == 'volume' else 'container',
                'name': prefix + '-' + key, 'owner': prefix + '/' + key,
                'attempted': False, 'acknowledged': False} for key in ('volume', 'holder', 'producer')}
            need(own['resources'] == expected, 'Complete exact three-resource plan')
            self.ownership[phase] = event
        else:
            need(phase in self.ownership, 'Parent ownership must precede every resource action')
            if name == 'CLI-INTENT':
                need(set(event) == {'index', 'phase', 'cap', 'original_end'}
                     and type(event['index']) is int and 0 <= event['index'] < 256
                     and type(event['cap']) is int and 0 < event['cap'] <= 2**20
                     and time.monotonic() < event['original_end'] <= self.invocation['clock']['controller_deadline']
                     and (phase, event['index']) not in self.intents, 'Unique bounded original CLI intent')
                self.intents[phase, event['index']] = event
            elif name == 'CLI-CHILD':
                intent = self.intents.get((phase, event['index']))
                need(intent is not None and event['phase'] == intent['phase']
                     and event['original_end'] == intent['original_end'] and not intent.get('_child'),
                     'CLI child joins its exact unconsumed parent intent')
                self.custody.capture(event, self.invocation['clock']['controller_deadline'])
                intent['_child'] = True
            elif name in ('RESOURCE-INTENT', 'CREATE-ATTEMPT', 'RESOURCE-ACK'):
                resource = event['resource'] if name == 'RESOURCE-INTENT' else event
                planned = self.ownership[phase]['ownership']['resources']
                need(any(all(resource.get(k) == expected[k] for k in ('kind', 'name', 'owner'))
                         for expected in planned.values()), 'Only exact planned resource can be released')
                if name == 'RESOURCE-INTENT':
                    need(event['creation_obligation_until_closed'] is True,
                         'Intent retains creation custody until closure')
            elif name == 'PHASE-CLOSURE':
                need(event['phase_id'] == phase and event['request_sha256'] == request_pin['sha256']
                     and event['ownership_pin'] == self.ownership[phase]['ownership_pin']
                     and event['timing']['original_deadline'] == self.invocation['clock']['deadline'],
                     'Observed phase closure retains source and owner clock')
                if event['status'] == 'captured':
                    self.legacy.validate_closed(self.prepared[phase], event)
                    self.closed.add(phase)
        self.indices[phase] += 1

    def accept(self, message, *, controller_check=None):
        need(type(message) is dict and set(message) == {'schema', 'invocation_pin', 'sequence', 'event', 'value'}
             and message['schema'] == 'smc_owner_rpc_v1'
             and message['invocation_pin'] == self.invocation_pin
             and type(message['sequence']) is int and message['sequence'] == self.sequence,
             'Exact current invocation and synchronous sequence')
        need(time.monotonic() < self.invocation['clock']['controller_deadline'],
             'No event acknowledgement after original controller cutoff')
        name, value = message['event'], message['value']
        if name == 'CONTROLLER-READY':
            need(not self.controller_ready and self.sequence == 0 and controller_check is not None,
                 'One actual owned controller birth before all work')
            controller_check(value)
            self.controller_ready = True
        elif name == 'PREPARED':
            self._prepared(value)
        elif name == 'CONTROLLER-DONE':
            need(self.controller_ready and self.done is None and self.closed == set(CONDITIONS),
                 'Both phases closed before controller completion')
            descriptor(value)
            need(pin(body(Path(self.invocation['output']) / 'PAIR_CLOSED.json')) == value,
                 'Complete saved paired report before controller completion')
            self.done = value
        else:
            self._provider(name, value)
        wrapped = {'schema': 'smc_long_owner_event_v1', 'owner_source': self.source,
                   'invocation_pin': self.invocation_pin, 'message': message}
        raw = encoded(wrapped)
        need(self.sequence < EVENT_CAP and self.bytes + len(raw) <= JOURNAL_CAP,
             'Finite cumulative owner journal')
        self.writer.publish(self.folder / ('EVENT-' + str(self.sequence).zfill(6) + '.json'), wrapped)
        self.bytes += len(raw)
        self.sequence += 1
        need(time.monotonic() < self.invocation['clock']['controller_deadline'],
             'Durable acknowledgement still inside original controller cutoff')
        # Returning is acknowledgement authority only AFTER file and directory fsync.
        return {'schema': 'smc_owner_ack_v1', 'sequence': message['sequence'],
                'message_pin': pin(encoded(message))}
