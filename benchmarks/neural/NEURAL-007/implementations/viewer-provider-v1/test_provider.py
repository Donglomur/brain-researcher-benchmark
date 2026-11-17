"""Generated in-memory provider controls; no authentic inputs, HTTP or models.

The two-epoch sleep fixture explicitly patches the trusted population constant
inside this process and invokes the original viewer state machine. It cannot
qualify the complete canonical population or any provider's actual capacity.
"""
from __future__ import annotations

import base64
from dataclasses import replace
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('generated_viewer_provider', HERE / 'provider.py')
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)

# Invented one-pixel PNG; no neuroscience signal is encoded in this body.
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a0XcAAAAASUVORK5CYII=')
MODEL = 'generated-vision-model-001'
SLEEP = 'whole_person_raw_viewer_zero_shot'
TRIAL = 'development-001-' + 'a' * 24


def budget(**changes):
    original = p.Budget(max_turns=12, max_images=8, max_history_bytes=200000,
                        max_request_bytes=400000, max_response_bytes=8192,
                        max_total_provider_bytes=2000000, context_tokens=20000,
                        output_tokens=128, wall_seconds=30)
    return replace(original, **changes)


def provider_body(action, ordinal=1):
    return {'object': 'response', 'id': 'resp_generated_' + str(ordinal),
            'status': 'completed', 'error': None, 'incomplete_details': None,
            'model': MODEL, 'tools': [], 'tool_choice': 'none',
            'parallel_tool_calls': False, 'store': False, 'background': False,
            'truncation': 'disabled', 'previous_response_id': None,
            'conversation': None, 'max_output_tokens': 128,
            'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed',
                        'content': [{'type': 'output_text', 'text': p.encode({'viewer_action': action}).decode()}]}],
            'usage': {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120}}


def final_action(response=None):
    if response is None:
        response = json.dumps({'trial_id': TRIAL, 'target_probability': 0.3})
    return {'action': 'finalize', 'response': response}


class Duplex:
    """Real byte framing, short I/O and original-state-machine acknowledgments."""
    def __init__(self, transport, ready, png, respond, receipts):
        self.t, self.respond, self.receipts = transport, respond, receipts
        self.incoming = bytearray(transport.wire(ready, png))
        self.output, self.pending, self.actions = bytearray(), bytearray(), []
        self.receipts_at_emission, self.reply_mutator = [], None
        self.read_calls = 0

    def read(self, count):
        self.read_calls += 1
        body = bytes(self.incoming[:min(count, 29)])
        del self.incoming[:len(body)]
        return body

    def write(self, body):
        body = body[:17]  # Exercise short writes without dropping action bytes.
        self.output.extend(body)
        self.pending.extend(body)
        if len(self.pending) >= self.t.PREFIX.size:
            hs, ps = self.t.PREFIX.unpack(self.pending[:self.t.PREFIX.size])
            size = self.t.PREFIX.size + hs + ps
            if len(self.pending) == size:
                action, image = self.t.unpack(bytes(self.pending), inbound=True)
                if image:
                    raise AssertionError('Participant emitted image data')
                self.pending.clear()
                self.actions.append(action)
                self.receipts_at_emission.append([m['event'] for m, _, _ in self.receipts])
                header, png = self.respond(action)
                if self.reply_mutator:
                    header, png = self.reply_mutator(header, png)
                self.incoming.extend(self.t.wire(header, png))
        return len(body)

    def flush(self):
        pass


class Harness:
    def __init__(self, test, task='NEURAL-077', condition='zero_shot', actions=None,
                 allocation=None, mutate=None, bound=None, record_hook=None,
                 canonical=False, generated_epochs=2):
        self.requests, self.raw_replies, self.receipts, self.deadlines = [], [], [], []
        self.actions = list(actions if actions is not None else [final_action()])
        self.mutate, self.record_hook = mutate, record_hook
        self.bridge = p.Bridge(task=task, condition=condition, model=MODEL,
                               budget=allocation or budget(), send_json=self.send,
                               input_token_bound=bound or self.bound, record=self.record)
        self.t, self.v = self.bridge.p.t, self.bridge.p.t.v
        if task == 'NEURAL-007':
            if not canonical:
                scope = patch.dict(self.v.CASES, {'development-001': generated_epochs}, clear=True)
                scope.start(); test.addCleanup(scope.stop)
            epochs = self.v.CASES['development-001']
            self.packet = SimpleNamespace(case='development-001', epochs=epochs,
                clock=[[i / 120, 0.1, 0.9] for i in range(epochs)],
                samples=lambda start, stop, channels: [[0.0] * (stop - start) for _ in channels])
            limits = self.t.Limits(max_actions=max(2 * epochs + 12, self.bridge.b.max_turns),
                max_images=max(epochs + 6, self.bridge.b.max_turns), max_output_bytes=16 * 1024**2, wall_seconds=30)
            self.ready = self.t.ready_header(self.packet, limits, '1' * 32)
            renderer = SimpleNamespace(render=lambda *args, **kwargs: PNG)
            self.session = self.v.Session(self.packet, limits.max_actions, None, renderer)
            respond = lambda action: self.t.projection(self.session.handle(action))
            initial = b''
        else:
            self.limits = self.t.Limits(max_actions=16, max_images=8,
                max_output_bytes=16 * 1024**2, wall_seconds=30)
            self.state, self.sequence = self.v.initial_state(), 1
            self.ready = self.t.ready_header(SimpleNamespace(query={'trial_id': TRIAL},
                prompt=self.v.scientific_prompt(TRIAL, condition)), self.limits, '2' * 32)
            self.ready['initial'] = self.eeg_view()
            respond, initial = self.eeg_reply, PNG
        self.pipe = Duplex(self.t, self.ready, initial, respond, self.receipts)

    def bound(self, request, deadline):
        self.deadlines.append(deadline)
        return 1000

    def record(self, meta, request, response):
        if self.record_hook:
            self.record_hook(meta, request, response)
        self.receipts.append((meta, request, response))

    def send(self, request, deadline):
        self.requests.append(request)
        self.deadlines.append(deadline)
        action = self.actions[len(self.requests) - 1]
        body = provider_body(action, len(self.requests))
        if self.mutate:
            body = self.mutate(body)
        raw = p.encode(body) if isinstance(body, dict) else body
        self.raw_replies.append(raw)
        return raw

    def eeg_view(self):
        record = {} if self.state['record'] == 'query' else {'target': 1}
        return {'status': 'rendered', 'display': self.v.display_metadata(self.state, record),
                'remaining_actions': self.limits.max_actions - self.sequence,
                'image': {'mime_type': 'image/png', 'bytes': len(PNG)}}

    def eeg_reply(self, action):
        self.sequence += 1
        try:
            state = self.v.transition(self.state, action, self.bridge.p.condition)
        except (ValueError, TypeError):
            return {'status': 'rejected', 'error': 'Invalid action or parameters',
                    'remaining_actions': self.limits.max_actions - self.sequence}, b''
        if action['action'] == 'finalize':
            # Generated known scalar/invalid fixtures only; authoritative scalar
            # admission is the existing collector, which is not rerun here.
            status = 'invalid_response' if action['response'] == 'INVALID GENERATED SCALAR' else 'valid_unscored'
            return {'status': status, 'response_sha256': hashlib.sha256(action['response'].encode()).hexdigest(),
                    'terminal': True}, b''
        self.state = state
        return self.eeg_view(), PNG

    def run(self):
        return self.bridge.serve(self.pipe, self.pipe)


class GeneratedProviderControls(unittest.TestCase):
    def failed(self, h, calls=None, actions=0):
        with self.assertRaisesRegex(ValueError, 'Viewer provider bridge failed'):
            h.run()
        if calls is not None:
            self.assertEqual(len(h.requests), calls)
        self.assertEqual(len(h.pipe.actions), actions)
        self.assertNotIn('session_terminal', [x[0]['event'] for x in h.receipts])

    def test_sleep_original_state_machine_two_epoch_complete_roundtrip(self):
        actions = [
            {'action': 'epoch', 'index': 0},
            {'action': 'respond', 'epoch_id': 'development-001/00000', 'probabilities': [0.1, 0.2, 0.3, 0.1, 0.3]},
            {'action': 'epoch', 'index': 1},
            {'action': 'respond', 'epoch_id': 'development-001/00001', 'probabilities': [0, 0, 0, 0, 1]},
            {'action': 'finish'}]
        h = Harness(self, 'NEURAL-007', SLEEP, actions)
        result = h.run()
        self.assertEqual(result, {'kind': 'complete', 'case_id': 'development-001', 'epochs': 2})
        self.assertTrue(h.session.finished)
        self.assertEqual(h.session.answers, {0: actions[1]['probabilities'], 1: actions[3]['probabilities']})
        self.assertEqual(h.pipe.actions, actions)
        self.assertEqual(len(h.requests), 5)
        histories = [json.loads(r)['input'] for r in h.requests]
        self.assertEqual([len(x) for x in histories], [1, 3, 5, 7, 9])
        for previous, following in zip(histories, histories[1:]):
            self.assertEqual(following[:len(previous)], previous)
        self.assertEqual([sum(i.get('type') == 'input_image' for m in hist for i in m['content'] if isinstance(m['content'], list)) for hist in histories], [0, 1, 1, 2, 2])
        self.assertTrue(all(events[-1] == 'exchange' for events in h.pipe.receipts_at_emission))
        self.assertEqual(len(set(h.deadlines)), 1)

    def test_eeg_images_are_real_content_with_full_history_and_no_hidden_tools(self):
        h = Harness(self, actions=[{'action': 'inspect'}, final_action()])
        result = h.run()
        self.assertEqual(result['status'], 'valid_unscored')
        requests = [json.loads(r) for r in h.requests]
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[1]['input'][:1], requests[0]['input'])
        for request in requests:
            self.assertEqual(request['tools'], [])
            self.assertEqual(request['tool_choice'], 'none')
            self.assertIs(request['store'], False)
            self.assertEqual(request['truncation'], 'disabled')
            self.assertNotIn('previous_response_id', request)
            self.assertNotIn('conversation', request)
            images = [item for msg in request['input'] if isinstance(msg['content'], list)
                      for item in msg['content'] if item['type'] == 'input_image']
            for image in images:
                self.assertEqual(base64.b64decode(image['image_url'].split(',', 1)[1]), PNG)
                self.assertEqual(image['detail'], 'original')
        self.assertEqual(len(images), 2)
        self.assertEqual(h.pipe.actions[-1]['response'], final_action()['response'])

    def test_receipts_bind_exact_bodies_and_event_chain_before_action(self):
        h = Harness(self); h.run()
        previous = '0' * 64
        for index, (meta, request, response) in enumerate(h.receipts):
            self.assertEqual(meta['sequence'], index)
            self.assertEqual(meta['previous_sha256'], previous)
            self.assertEqual(meta['retry_count'], 0)
            self.assertFalse(meta['scientific_qualification'])
            if request is not None:
                self.assertEqual(meta['request'], p.pin(request))
            if response is not None:
                self.assertEqual(meta['response'], p.pin(response))
            previous = hashlib.sha256(p.encode(meta)).hexdigest()
        exchanges = [r for r in h.receipts if r[0]['event'] == 'exchange']
        self.assertEqual(exchanges[0][1:], (h.requests[0], h.raw_replies[0]))
        self.assertEqual(h.pipe.receipts_at_emission[0][-1], 'exchange')

    def test_fresh_instance_has_no_other_episode_history_and_reuse_refused(self):
        first = Harness(self); first.run()
        second = Harness(self); second.run()
        self.assertEqual(len(json.loads(second.requests[0])['input']), 1)
        self.assertEqual(first.requests[0], second.requests[0])
        with self.assertRaisesRegex(ValueError, 'single-session'):
            first.run()
        self.assertEqual(len(first.requests), 1)

    def test_canonical_sleep_fails_capacity_before_any_provider_send(self):
        h = Harness(self, 'NEURAL-007', SLEEP, canonical=True,
                    allocation=budget(max_turns=10000, max_images=1500))
        self.failed(h, calls=0)
        self.assertEqual([r[0]['event'] for r in h.receipts], ['ready', 'failed_no_further_action'])
        self.assertEqual(h.receipts[-1][0]['failure_stage'], 'canonical_full_history_image_capacity')

    def test_changed_ready_prompt_actions_and_private_metadata_refused(self):
        changes = [lambda x: x.update(prompt=x['prompt'] + ' EXTRA'),
                   lambda x: x.update(actions={}),
                   lambda x: x.update(private_target='PRIVATE SENTINEL'),
                   lambda x: x.update(episode_id='not-an-episode'),
                   lambda x: x['initial']['display'].update(demonstration_target=1)]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                h = Harness(self); change(h.ready)
                h.pipe.incoming = bytearray(h.t.wire(h.ready, PNG))
                self.failed(h, calls=0)

    def test_wrong_task_condition_and_source_bytes_refused(self):
        for task, condition in [('NEURAL-007', 'four_demo'), ('NEURAL-077', SLEEP), ('NEURAL-999', 'zero_shot')]:
            with self.subTest(task=task, condition=condition), self.assertRaises(ValueError):
                p.Bridge(task=task, condition=condition, model=MODEL, budget=budget(),
                         send_json=lambda *_: b'', input_token_bound=lambda *_: 1, record=lambda *_: None)
        original = Path.read_bytes
        def changed(path):
            body = original(path)
            return body + b'\n' if path.name == 'transport.py' and path.parent.name == 'visual-transport-v1' else body
        with patch.object(Path, 'read_bytes', changed), self.assertRaisesRegex(ValueError, 'Source identity'):
            Harness(self)

    def test_bad_framing_truncation_and_png_fail_before_provider(self):
        for kind in ('truncated', 'header_cap', 'png_cap', 'bad_png', 'wrong_png_size'):
            with self.subTest(kind=kind):
                h = Harness(self)
                if kind == 'truncated': h.pipe.incoming = h.pipe.incoming[:-1]
                elif kind == 'header_cap': h.pipe.incoming = bytearray(struct.pack('!II', h.t.HEADER_MAX + 1, 0))
                elif kind == 'png_cap': h.pipe.incoming = bytearray(struct.pack('!II', 1, h.t.PNG_MAX + 1))
                elif kind == 'bad_png': h.pipe.incoming = bytearray(h.t.wire(h.ready, b'not PNG'))
                else:
                    h.ready['initial']['image']['bytes'] += 1
                    h.pipe.incoming = bytearray(h.t.wire(h.ready, PNG))
                self.failed(h, calls=0)

    def test_token_bound_refuses_before_send_and_actual_usage_is_checked(self):
        for bound in (0, True, 1.5, 20000):
            with self.subTest(bound=bound):
                h = Harness(self, bound=lambda *_: bound)
                self.failed(h, calls=0)
                self.assertEqual(h.receipts[-1][0]['failure_stage'], 'input_token_capacity')
                exchange = next(meta for meta, _, _ in h.receipts if meta['event'] == 'exchange')
                self.assertEqual(exchange['failure_stage'], 'input_token_capacity')
                self.assertEqual(exchange['sender_calls_attempted'], 0)
        h = Harness(self, bound=lambda *_: 99)
        self.failed(h, calls=1)
        self.assertEqual(h.receipts[-2][0]['event'], 'exchange')
        self.assertEqual(h.receipts[-1][0]['failure_stage'], 'provider_token_accounting')

    def test_request_history_total_byte_and_response_limits(self):
        first = Harness(self); first.run()
        first_size = len(first.requests[0])
        limits = [budget(max_history_bytes=first_size - 1, max_request_bytes=first_size - 1),
                  budget(max_history_bytes=128), budget(max_total_provider_bytes=1)]
        for allocation in limits:
            with self.subTest(allocation=allocation):
                self.failed(Harness(self, allocation=allocation), calls=0)
        h = Harness(self, mutate=lambda _: b'x' * 8193)
        self.failed(h, calls=1)
        exchange = next(r for r in h.receipts if r[0]['event'] == 'exchange')
        self.assertEqual(exchange[2], b'x' * 8193)

    def test_provider_turn_and_full_history_image_exhaustion_no_extra_send(self):
        for allocation in (budget(max_turns=1), budget(max_images=1)):
            with self.subTest(allocation=allocation):
                h = Harness(self, actions=[{'action': 'inspect'}, final_action()], allocation=allocation)
                self.failed(h, calls=1, actions=1)

    def test_cumulative_capacity_accounts_repeated_full_history(self):
        reference = Harness(self, actions=[{'action': 'inspect'}, final_action()]); reference.run()
        first = len(reference.requests[0]) + len(reference.raw_replies[0])
        cap = first + len(reference.requests[1]) + 8192 - 1
        h = Harness(self, actions=[{'action': 'inspect'}, final_action()],
                    allocation=budget(max_total_provider_bytes=cap))
        self.failed(h, calls=1, actions=1)

    def test_invalid_budget_types_and_endpoint_image_ceiling(self):
        for changes in ({'max_turns': True}, {'max_images': 1501}, {'wall_seconds': float('inf')},
                        {'output_tokens': 20000}, {'image_detail': 'auto'}, {'max_response_bytes': 524289}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Harness(self, allocation=budget(**changes))

    def test_deadline_expiration_in_bound_or_sender_emits_no_action(self):
        for where in ('bound', 'sender'):
            with self.subTest(where=where):
                now = [0.0]
                with patch.object(p.time, 'monotonic', side_effect=lambda: now[0]):
                    h = Harness(self)
                    if where == 'bound':
                        def expired(*_): now[0] = 31; return 1000
                        h.bridge.input_token_bound = expired
                    else:
                        def expired(body): now[0] = 31; return body
                        h.mutate = expired
                    self.failed(h, calls=0 if where == 'bound' else 1)

    def test_sender_failure_retained_without_sensitive_exception_text(self):
        h = Harness(self)
        def failing(request, deadline):
            h.requests.append(request)
            raise RuntimeError('Bearer GENERATED_SECRET_NOT_A_CREDENTIAL')
        h.bridge.send_json = failing
        with self.assertRaisesRegex(ValueError, 'failed at sender_callback') as failure:
            h.run()
        self.assertEqual(len(h.requests), 1)
        self.assertEqual(h.pipe.actions, [])
        self.assertEqual(h.receipts[-1][0]['failure_stage'], 'sender_callback')
        self.assertNotIn('GENERATED_SECRET', str(failure.exception))
        encoded = p.encode([x[0] for x in h.receipts])
        self.assertNotIn(b'GENERATED_SECRET', encoded)
        exchange = next(x for x in h.receipts if x[0]['event'] == 'exchange')
        self.assertEqual(exchange[0]['sender_calls_attempted'], 1)
        self.assertEqual(exchange[0]['failure_stage'], 'sender_callback')
        self.assertIsNone(exchange[2])

    def test_sink_failure_withholds_prepared_action_and_does_not_retry(self):
        for fail_event, calls in [('ready', 0), ('exchange', 1)]:
            with self.subTest(event=fail_event):
                def sink(meta, *_):
                    if meta['event'] == fail_event: raise OSError('generated sink failure')
                h = Harness(self, record_hook=sink)
                self.failed(h, calls=calls)
                self.assertTrue(h.bridge.sink_failed)

    def test_policy_model_output_and_usage_mismatches_fail_closed(self):
        cases = [('tools', [{'type': 'function'}]), ('tool_choice', 'auto'),
                 ('parallel_tool_calls', True), ('store', True), ('truncation', 'auto'),
                 ('previous_response_id', 'resp_other'), ('conversation', 'other'),
                 ('background', True), ('model', 'other-model'), ('max_output_tokens', 127),
                 ('status', 'incomplete'), ('id', 'unbounded-invalid-id'),
                 ('usage', {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 119}),
                 ('usage', {'input_tokens': 100, 'output_tokens': 129, 'total_tokens': 229})]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                def mutate(body): body[key] = value; return body
                self.failed(Harness(self, mutate=mutate), calls=1)

    def test_hidden_reasoning_tools_refusals_and_multiple_messages_refused(self):
        def extra_reasoning(b): b['output'].insert(0, {'type': 'reasoning', 'summary': []}); return b
        def tool(b): b['output'] = [{'type': 'function_call', 'name': 'python'}]; return b
        def refusal(b): b['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'No'}]; return b
        def multiple(b): b['output'] *= 2; return b
        for mutate in (extra_reasoning, tool, refusal, multiple):
            with self.subTest(mutate=mutate.__name__):
                self.failed(Harness(self, mutate=mutate), calls=1)

    def test_malformed_provider_json_and_action_wrapper_refused(self):
        for raw in (b'not json', b'{"status":1,"status":2}', b'{"x":NaN}', 'not bytes'):
            with self.subTest(raw=raw):
                self.failed(Harness(self, mutate=lambda _: raw), calls=1)
        for text in ('{"viewer_action":{},"extra":1}', '{"viewer_action":{},"viewer_action":{}}',
                     '{"viewer_action":null}'):
            with self.subTest(text=text):
                def mutate(body): body['output'][0]['content'][0]['text'] = text; return body
                self.failed(Harness(self, mutate=mutate), calls=1)

    def test_sleep_no_early_response_or_finish_or_replacement(self):
        invalid_scripts = [
            [{'action': 'respond', 'epoch_id': 'development-001/00000', 'probabilities': [0.2] * 5}],
            [{'action': 'finish'}],
            [{'action': 'epoch', 'index': 0},
             {'action': 'respond', 'epoch_id': 'development-001/00000', 'probabilities': [0.2] * 5},
             {'action': 'respond', 'epoch_id': 'development-001/00000', 'probabilities': [0, 0, 0, 0, 1]}]]
        for actions in invalid_scripts:
            with self.subTest(actions=actions):
                h = Harness(self, 'NEURAL-007', SLEEP, actions)
                self.failed(h, calls=len(actions), actions=len(actions) - 1)
                if len(actions) > 1:
                    self.assertEqual(h.session.answers[0], [0.2] * 5)

    def test_sleep_acknowledgment_mismatch_prevents_next_provider_call(self):
        h = Harness(self, 'NEURAL-007', SLEEP, [{'action': 'epoch', 'index': 0}])
        def changed(header, image): header['epoch_id'] = 'development-001/00001'; return header, image
        h.pipe.reply_mutator = changed
        self.failed(h, calls=1, actions=1)

    def test_zero_shot_demo_action_rejection_is_retained_not_silently_repaired(self):
        h = Harness(self, actions=[{'action': 'select', 'record': 'demo1'}, final_action()])
        h.run()
        self.assertEqual(h.pipe.actions[0], {'action': 'select', 'record': 'demo1'})
        second_history = json.loads(h.requests[1])['input']
        reply = json.loads(second_history[-1]['content'][0]['text'])
        self.assertEqual(reply['status'], 'rejected')
        self.assertNotIn('demonstration_target', h.requests[1].decode())

    def test_four_demo_label_only_enters_history_with_selected_demo_image(self):
        h = Harness(self, condition='four_demo', actions=[{'action': 'select', 'record': 'demo1'}, final_action()])
        h.run()
        self.assertNotIn('demonstration_target', h.requests[0].decode())
        second = json.loads(h.requests[1])['input'][-1]['content']
        self.assertEqual(json.loads(second[0]['text'])['display']['demonstration_target'], 1)
        self.assertEqual(second[1]['type'], 'input_image')

    def test_first_invalid_eeg_scalar_is_terminal_and_never_replaced(self):
        action = final_action('INVALID GENERATED SCALAR')
        h = Harness(self, actions=[action, final_action()])
        terminal = h.run()
        self.assertEqual(terminal['status'], 'invalid_response')
        self.assertEqual(h.pipe.actions, [action])
        self.assertEqual(len(h.requests), 1)
        self.assertEqual(h.receipts[-1][0]['terminal_status'], 'invalid_response')

    def test_action_output_failure_does_not_retry_or_read_more_views(self):
        h = Harness(self)
        h.pipe.write = lambda body: 0
        self.failed(h, calls=1)
        self.assertEqual(h.pipe.actions, [])
        self.assertNotIn('action_emitted', [x[0]['event'] for x in h.receipts])

    def test_rolling_31_32_33_boundaries_and_more_than_32_total_images(self):
        actions = []
        first_probabilities = [0.123, 0.222, 0.111, 0.333, 0.211]
        for i in range(33):
            actions.extend([{'action': 'epoch', 'index': i},
                            {'action': 'respond', 'epoch_id': f'development-001/{i:05d}',
                             'probabilities': first_probabilities if i == 0 else [0.2] * 5}])
        actions.append({'action': 'finish'})
        h = Harness(self, 'NEURAL-007', p.ROLLING_CONDITION, actions,
                    allocation=budget(max_turns=80, max_images=32, max_total_provider_bytes=4000000),
                    generated_epochs=33)
        self.assertEqual(h.run()['epochs'], 33)
        histories = [json.loads(body)['input'] for body in h.requests]
        self.assertEqual([len(histories[i]) for i in (30, 31, 32, 33)], [61, 63, 64, 64])
        self.assertTrue(all(history[0] == histories[0][0] for history in histories))
        first_action = {'role': 'assistant', 'content': p.encode({'viewer_action': actions[0]}).decode()}
        self.assertIn(first_action, histories[31])
        self.assertNotIn(first_action, histories[32])
        # Its acknowledgment belongs to the next complete turn, so the identity
        # remains one request longer than the evicted probability-bearing turn.
        self.assertNotIn('development-001/00000', h.requests[34].decode())
        self.assertNotIn(p.encode(first_probabilities).decode(), h.requests[33].decode())
        for history in histories:
            images = sum(part['type'] == 'input_image' for item in history
                         if isinstance(item['content'], list) for part in item['content'])
            self.assertLessEqual(images, 32)
        self.assertEqual(h.bridge.images, 33)
        observed = 0
        for meta, _, _ in h.receipts:
            if meta['event'] == 'viewer_reply' and meta['image'] is not None:
                observed += 1
            self.assertEqual(meta['observed_images'], observed)
        self.assertEqual(h.session.answers[0], first_probabilities)
        exchanges = [meta for meta, _, _ in h.receipts if meta['event'] == 'exchange']
        self.assertEqual([exchanges[i]['evicted_complete_turns'] for i in (30, 31, 32, 33)], [0, 0, 1, 2])
        self.assertTrue(all(m['condition'] == p.ROLLING_CONDITION and m['viewer_condition'] == SLEEP for m in exchanges))
        self.assertEqual(len(exchanges), 67)  # All bodies retained despite model-history eviction.

    def test_rolling_eviction_does_not_allow_replacement_of_old_sleep_answer(self):
        original = {'action': 'respond', 'epoch_id': 'development-001/00000', 'probabilities': [0.2] * 5}
        actions = [{'action': 'epoch', 'index': 0}, original, {'action': 'epoch', 'index': 1}]
        actions += [{'action': 'inspect'}] * 33
        actions += [{'action': 'epoch', 'index': 0}, dict(original, probabilities=[0, 0, 0, 0, 1])]
        h = Harness(self, 'NEURAL-007', p.ROLLING_CONDITION, actions,
                    allocation=budget(max_turns=50, max_images=32, max_total_provider_bytes=4000000))
        self.failed(h, calls=len(actions), actions=len(actions) - 1)
        self.assertGreater(h.bridge.evicted_turns, 0)
        last_history = json.loads(h.requests[-1])['input']
        self.assertNotIn({'role': 'assistant', 'content': p.encode({'viewer_action': original}).decode()}, last_history)
        self.assertEqual(h.session.answers, {0: [0.2] * 5})

    def test_rolling_capacity_failure_never_evicts_extra_turns_to_fit(self):
        actions = [{'action': 'inspect'}] * 40
        calls = [0]
        def bounded(request, deadline):
            calls[0] += 1
            return 20000 if calls[0] == 34 else 1000
        h = Harness(self, 'NEURAL-007', p.ROLLING_CONDITION, actions,
                    allocation=budget(max_turns=50, max_images=32, max_total_provider_bytes=4000000), bound=bounded)
        self.failed(h, calls=33, actions=33)
        self.assertEqual(h.bridge.evicted_turns, 2)
        self.assertEqual(len(h.bridge.visible_turns), 32)
        self.assertEqual(sum(part['type'] == 'input_image' for item in h.bridge.history
                             if isinstance(item['content'], list) for part in item['content']), 32)

    def test_rolling_condition_identity_and_exact_slots_cannot_be_silently_changed(self):
        for task, slots in [('NEURAL-077', 32), ('NEURAL-007', 31), ('NEURAL-007', 33)]:
            with self.subTest(task=task, slots=slots), self.assertRaises(ValueError):
                Harness(self, task, p.ROLLING_CONDITION, allocation=budget(max_images=slots))

    def test_terminal_sink_expiring_deadline_cannot_return_session_success(self):
        now = [0.0]
        def delayed_sink(meta, *_):
            if meta['event'] == 'session_terminal':
                now[0] = 31.0
        with patch.object(p.time, 'monotonic', side_effect=lambda: now[0]):
            h = Harness(self, record_hook=delayed_sink)
            with self.assertRaisesRegex(ValueError, 'Viewer provider bridge failed'):
                h.run()
        self.assertEqual(len(h.requests), 1)
        self.assertEqual(h.pipe.actions, [final_action()])
        events = [meta['event'] for meta, _, _ in h.receipts]
        self.assertEqual(events[-2:], ['session_terminal', 'failed_no_further_action'])
        self.assertTrue(all(meta['observed_images'] == 1 for meta, _, _ in h.receipts))


if __name__ == '__main__':
    unittest.main()
