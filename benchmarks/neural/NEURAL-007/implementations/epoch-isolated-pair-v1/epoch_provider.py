"""Bounded same-epoch visual provider and read-only exact custody replay.

This trusted operator reuses the unchanged N077 HTTPS Sender/Custody and N007
response/HTTP validators. It never provides a qualification decision.
"""
from dataclasses import asdict
import http.client
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import epoch_visual as V

CONDITION = V.CONDITION
EVENT_SCHEMA = 'sleep007_epoch_visual_event_v1'
END_SCHEMA = 'sleep007_epoch_visual_end_v1'

def checked_budget(runtime, value):
    budget = runtime['provider'].Budget(**value) if type(value) is dict else value
    V.need(type(budget) is runtime['provider'].Budget, 'Original explicit provider budget')
    budget.validate()
    V.need(asdict(budget) == (value if type(value) is dict else asdict(value))
           and budget.max_images >= 2
           and budget.max_request_bytes <= runtime['sender'].REQUEST_CAP
           and budget.wall_seconds > 4
           and budget.max_total_provider_bytes >= budget.max_request_bytes + budget.max_response_bytes + 1,
           'Finite complete overview/detail and failed-response reserve')
    return budget

def config_value(runtime, session, knowledge, budget):
    runtime['contract'].checked_knowledge(knowledge)
    V.need(knowledge['provider'] == 'openai', 'Declared shared provider agrees with the reused HTTPS endpoint')
    return {'schema': 'sleep007_epoch_visual_config_v1', 'condition': CONDITION,
            'memory_policy': V.MEMORY_POLICY, 'session_id': session.session_id,
            'target': session.packet.metadata(), 'knowledge': knowledge,
            'knowledge_pin': runtime['contract'].pin(runtime['contract'].encode(knowledge)),
            'model': knowledge['model'], 'budget': asdict(budget),
            'source': runtime['source'], 'render_runtime': runtime['runtime_identity']}

class RequestAdapter:
    def __init__(self, raw, session, knowledge, budget):
        self.raw, self.model, self.output_tokens = raw, knowledge['model'], budget.output_tokens
        self.decode = session.runtime['base_client'].decode
        value = self.decode(raw)
        self.prompt = value['input'][0]['content'][0]['text']
        first = self.decode(self.prompt)
        V.need(first['condition'] == CONDITION and first['memory_policy'] == V.MEMORY_POLICY
               and first['knowledge'] == knowledge
               and first['observation']['session_id'] == session.session_id
               and first['observation']['target'] == session.packet.metadata(),
               'Exact isolated target and shared prior context')
        self.identity = session.session_id + ':' + session.packet.epoch_id

    def query_identity(self, prompt):
        V.need(prompt == self.prompt, 'Exact fresh target prompt')
        return self.identity

    def request_body(self, prompt, model, max_output_tokens):
        V.need((prompt, model, max_output_tokens) == (self.prompt, self.model, self.output_tokens),
               'Exact immutable request context')
        return self.raw

def response_action(runtime, model, budget, raw, token_bound):
    holder = SimpleNamespace(stage=None, model=model, b=budget)
    return runtime['provider'].Bridge.response(holder, raw, token_bound)

def _event(config_pin, session, deadline, sequence, previous, request, response, bound,
           action, details, status, failure):
    observation, _ = session.observation()
    return {'schema': EVENT_SCHEMA, 'condition': CONDITION, 'config': config_pin,
            'session_id': session.session_id, 'epoch_id': session.packet.epoch_id,
            'sequence': sequence, 'previous_sha256': previous, 'deadline': deadline,
            'observation': observation, 'request': V.pin(request),
            'response': None if response is None else V.pin(response),
            'input_token_bound': bound, 'action': action, 'provider': details,
            'status': status, 'failure_stage': failure,
            'provider_context_qualified': False, 'provider_capacity_qualified': False,
            'token_bound_qualified': False, 'scientific_qualification': False}

def _end(config_pin, session, deadline, turns, request_bytes, response_bytes, upper,
         status, failure, response_ids):
    return {'schema': END_SCHEMA, 'condition': CONDITION, 'config': config_pin,
            'session_id': session.session_id, 'epoch_id': session.packet.epoch_id,
            'deadline': deadline, 'turns': turns, 'request_bytes': request_bytes,
            'response_bytes': response_bytes, 'response_charge_contains_upper_bound': upper,
            'response_ids': response_ids, 'status': status, 'failure_stage': failure,
            'probabilities': session.answer, 'first_accepted_answer': session.answer is not None,
            'complete_three_channel_epoch': session.overview is not None,
            'provider_context_qualified': False, 'provider_capacity_qualified': False,
            'token_bound_qualified': False, 'scientific_qualification': False}

def run_epoch(runtime, packet, knowledge, budget, custody_root, credential, input_token_bound,
              *, session_id=None, http_factory=http.client.HTTPSConnection):
    """Future explicitly selected trusted operation, one target and no retry.

    Generated controls inject finite fake HTTPS at the existing Sender seam.
    No CLI switch or generated-proof flag can grant production qualification.
    """
    budget = checked_budget(runtime, budget)
    V.need(callable(input_token_bound), 'Explicit external complete-input token bound')
    base, sender = runtime['base_client'], runtime['sender']
    V.need(type(credential) is str and 0 < len(credential) <= sender.CREDENTIAL_CAP
           and all(33 <= ord(c) <= 126 for c in credential), 'Explicit trusted credential')
    session = V.Session(packet, runtime, budget.max_turns, session_id)
    config = config_value(runtime, session, knowledge, budget)
    root = runtime['common'].path(custody_root)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    events_fd = turns_fd = None
    deadline = time.monotonic() + budget.wall_seconds
    alarm = None
    turns = request_bytes = response_bytes = 0
    previous, upper, response_ids = '0' * 64, False, []
    stage, failed, result = 'initialization', None, None
    config_pin = V.pin(V.encode(config))
    try:
        V.need(stat.S_IMODE(os.fstat(directory).st_mode) == 0o700, 'Private fresh target custody')
        base.write_new(directory, 'CONFIG.json', V.encode(config))
        os.mkdir('events', 0o700, dir_fd=directory)
        os.mkdir('turns', 0o700, dir_fd=directory)
        events_fd = os.open('events', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        turns_fd = os.open('turns', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        alarm = sender.Alarm(deadline)
        stage = 'complete_initial_epoch_view'
        session.initial()
        while not session.closed:
            V.need(time.monotonic() < deadline and turns < budget.max_turns, 'Epoch wall/turn capacity')
            stage = 'complete_request_capacity'
            request = V.request_bytes(session, knowledge['model'], budget, knowledge)
            V.need(request_bytes + response_bytes + len(request) + budget.max_response_bytes + 1
                   <= budget.max_total_provider_bytes, 'Reserve complete request and failed-response extent')
            stage = 'external_token_bound'
            bound = input_token_bound(request, deadline)
            V.need(type(bound) is int and 0 < bound
                   and bound + budget.output_tokens <= budget.context_tokens, 'Complete input token capacity')
            V.need(time.monotonic() < deadline, 'External bound deadline')
            adapter = RequestAdapter(request, session, knowledge, budget)
            name = f'{turns:06d}'
            os.mkdir(name, 0o700, dir_fd=turns_fd)
            turn_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=turns_fd)
            custody = sender.Custody(turn_fd, config_pin, deadline)
            sender_config = {'model': knowledge['model'], 'max_output_tokens': budget.output_tokens,
                             'deadline': deadline, 'trial_id': adapter.identity,
                             'context_sha256': V.pin(adapter.prompt.encode())['sha256']}
            client = sender.Sender(sender_config, config_pin, credential, custody, adapter, alarm,
                                   http_factory=http_factory, response_cap=budget.max_response_bytes)
            raw = action = details = None
            event_status, event_failure = 'failed_no_action', None
            request_bytes += len(request)
            this_turn = turns
            turns += 1
            try:
                stage = 'sender'
                alarm.arm(deadline - sender.CUSTODY_SECONDS)
                raw = client(request)
                response_bytes += len(raw)
                V.need(not base.decoded_echo(base.decode(raw), credential), 'Decoded credential echo')
                stage = 'response_validation'
                _, proposed, details = response_action(runtime, knowledge['model'], budget, raw, bound)
                V.need(details['provider_response_id'] not in response_ids, 'Fresh response identity')
                action = session.validate_action(proposed)
                V.need(not base.decoded_echo(action, credential), 'Decoded action credential echo')
                event_status = 'action_prepared_unscored'
            except BaseException:
                event_failure = stage
                if raw is None and 'HTTP.json' in custody.created:
                    response_bytes += budget.max_response_bytes + 1
                    upper = True
                raise
            finally:
                try:
                    stage_before_record, stage = stage, 'durable_event_before_action'
                    event = _event(config_pin, session, deadline, this_turn, previous,
                                   request, raw, bound, action, details, event_status, event_failure)
                    V.need(not base.decoded_echo(event, credential), 'Decoded event credential echo')
                    custody.json('BRIDGE.json', event)
                    V.need(custody.created == sender.FILES, 'Complete original sender custody')
                    body = V.encode(event)
                    base.write_new(events_fd, name + '.json', body)
                    previous = V.pin(body)['sha256']
                    stage = stage_before_record
                finally:
                    client.credential = None
                    os.close(turn_fd)
            stage = 'apply_durably_recorded_action'
            V.need(time.monotonic() < deadline, 'Action deadline')
            session.handle(action)
            response_ids.append(details['provider_response_id'])
        result = _end(config_pin, session, deadline, turns, request_bytes, response_bytes, upper,
                      'complete_unscored', None, response_ids)
    except BaseException:
        failed = stage
        result = _end(config_pin, session, deadline, turns, request_bytes, response_bytes, upper,
                      'failed_no_admission', stage, response_ids)
    finally:
        try:
            if alarm is not None:
                alarm.arm(deadline)
            base.write_new(directory, 'END.json', V.encode(result), cap=65536)
        finally:
            credential = None
            for fd in (events_fd, turns_fd, directory):
                if fd is not None:
                    os.close(fd)
            if alarm is not None:
                alarm.close()
    V.need(failed is None, 'Epoch provider failed at ' + str(failed) + '; no retry or admission')
    return result

def audit_session(session_root, packet, runtime, knowledge):
    """Reconstruct every exact same-target image request without HTTP or token code."""
    C, base, sender = runtime['common'], runtime['base_client'], runtime['sender']
    exact = runtime['prior_admission'].exact_inventory
    root = exact(session_root, {'CONFIG.json', 'events', 'turns', 'END.json'})
    config_raw = C.snapshot(root / 'CONFIG.json', 65536)
    config = base.decode(config_raw)
    V.need(type(config) is dict and config_raw == V.encode(config), 'Canonical target configuration')
    budget = checked_budget(runtime, config['budget'])
    session = V.Session(packet, runtime, budget.max_turns, config['session_id'])
    expected_config = config_value(runtime, session, knowledge, budget)
    V.need(config == expected_config, 'Exact source, target, model, runtime and shared prior policy')
    config_pin = V.pin(config_raw)
    end_raw = C.snapshot(root / 'END.json', 65536)
    end = base.decode(end_raw)
    V.need(end_raw == V.encode(end) and end['status'] == 'complete_unscored'
           and type(end['turns']) is int and 1 <= end['turns'] <= budget.max_turns,
           'Complete finite target provider evidence')
    deadline = end['deadline']
    V.need(type(deadline) in (int, float) and math.isfinite(deadline), 'Original finite deadline')
    names = {f'{n:06d}' for n in range(end['turns'])}
    exact(root / 'turns', names)
    exact(root / 'events', {name + '.json' for name in names})
    previous, request_bytes, response_bytes = '0' * 64, 0, 0
    response_ids = []
    previous_http_end = deadline - budget.wall_seconds
    session.initial()
    for turn in range(end['turns']):
        V.need(not session.closed, 'No provider turn after first accepted target answer')
        row = exact(root / 'turns' / f'{turn:06d}', sender.FILES)
        request = V.request_bytes(session, knowledge['model'], budget, knowledge)
        V.need(request_bytes + response_bytes + len(request) + budget.max_response_bytes + 1
               <= budget.max_total_provider_bytes, 'Replay reserves the complete failed-response extent before each call')
        saved = C.snapshot(row / 'REQUEST.bin', min(sender.REQUEST_CAP, budget.max_request_bytes))
        raw = C.snapshot(row / 'RESPONSE.bin', budget.max_response_bytes)
        V.need(saved == request, 'Exact full overview, same-target detail and fresh context lineage')
        http = base.decode(C.snapshot(row / 'HTTP.json', 16384))
        started, finished = runtime['prior_admission'].http_receipt(http, config_pin, request, raw, deadline)
        V.need(previous_http_end <= started, 'Ordered nonoverlapping one-call exchanges')
        previous_http_end = finished
        event_raw = C.snapshot(root / 'events' / f'{turn:06d}.json', 32768)
        event = base.decode(event_raw)
        V.need(event_raw == V.encode(event), 'Canonical target custody event')
        bound = event['input_token_bound']
        V.need(type(bound) is int and 0 < bound and bound + budget.output_tokens <= budget.context_tokens,
               'Recorded complete-input token bound')
        _, proposed, details = response_action(runtime, knowledge['model'], budget, raw, bound)
        V.need(details['provider_response_id'] not in response_ids, 'No reused response identity')
        action = session.validate_action(proposed)
        expected = _event(config_pin, session, deadline, turn, previous, request, raw, bound,
                          action, details, 'action_prepared_unscored', None)
        V.need(event == expected and C.snapshot(row / 'BRIDGE.json', 16384) == sender.encode(expected),
               'Exact sender/event/action/target chain')
        request_bytes += len(request)
        response_bytes += len(raw)
        V.need(request_bytes + response_bytes <= budget.max_total_provider_bytes,
               'Declared cumulative provider bytes')
        previous = V.pin(event_raw)['sha256']
        session.handle(action)
        response_ids.append(details['provider_response_id'])
    V.need(session.closed and session.answer is not None, 'One irreversible accepted target answer')
    expected_end = _end(config_pin, session, deadline, end['turns'], request_bytes, response_bytes, False,
                        'complete_unscored', None, response_ids)
    V.need(end == expected_end, 'Exact complete unqualified target end receipt')
    return {'epoch_id': packet.epoch_id, 'probabilities': session.answer[:],
            'knowledge': runtime['contract'].pin(runtime['contract'].encode(knowledge)),
            'session_id': session.session_id, 'response_ids': response_ids,
            'source': runtime['source'], 'request_bytes': request_bytes,
            'response_bytes': response_bytes, 'condition': CONDITION,
            'provider_context_qualified': False, 'provider_capacity_qualified': False,
            'token_bound_qualified': False, 'scientific_qualification': False}
