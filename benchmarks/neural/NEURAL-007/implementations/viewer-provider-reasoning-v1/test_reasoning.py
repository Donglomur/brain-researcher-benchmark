"""Generated reasoning-successor controls, reusing the frozen viewer fixtures.

No authentic signals, HTTP, model, credentials or subprocesses. Opaque strings
are invented markers, not actual reasoning or encrypted provider material.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


r = load('generated_current_turn_bridge', HERE / 'provider.py')
f = load('frozen_viewer_provider_fixtures', HERE.parent / 'viewer-provider-v1/test_provider.py')


def budget(**changes):
    with patch.object(f.p, 'Budget', r.Budget):
        return f.budget(**changes)


def reasoning_body(body, effort='medium', count=1):
    body['reasoning'] = {'context': 'current_turn', 'effort': effort}
    body['input_transformations'] = []
    message = body['output'][0]
    message['id'] = 'msg_' + body['id']
    message['phase'] = 'final_answer'
    opaque = [{'id': 'rs_' + body['id'] + '_' + str(i), 'type': 'reasoning',
               'summary': [], 'encrypted_content': 'OPAQUE_GENERATED_' + body['id'] + '_' + str(i)}
              for i in range(count)]
    body['output'] = opaque + [message]
    body['usage']['output_tokens_details'] = {'reasoning_tokens': 11}
    body['usage']['input_tokens_details'] = {'cached_tokens': 7}
    return body


class Harness(f.Harness):
    def __init__(self, test, *args, effort='medium', mutate=None, **kwargs):
        def transformed(body):
            body = reasoning_body(body, effort)
            return mutate(body) if mutate else body
        factory = lambda **options: r.Bridge(reasoning_effort=effort, **options)
        with patch.object(f.p, 'Bridge', factory), patch.object(f.p, 'Budget', r.Budget):
            super().__init__(test, *args, mutate=transformed, **kwargs)


class CurrentTurnReasoningControls(unittest.TestCase):
    def failed(self, h, calls=1, actions=0, stage=None):
        with self.assertRaisesRegex(ValueError, 'Viewer provider bridge failed'):
            h.run()
        self.assertEqual(len(h.requests), calls)
        self.assertEqual(len(h.pipe.actions), actions)
        self.assertEqual(h.receipts[-1][0]['event'], 'failed_no_further_action')
        if stage:
            self.assertEqual(h.receipts[-1][0]['failure_stage'], stage)

    def test_effort_is_required_explicit_and_echoed_in_current_turn_request(self):
        options = dict(task='NEURAL-077', condition='zero_shot', model=f.MODEL,
                       budget=budget(), send_json=lambda *_: b'',
                       input_token_bound=lambda *_: 1000, record=lambda *_: None)
        with self.assertRaises(TypeError):
            r.Bridge(**options)
        for effort in (None, '', True, 'automatic', 'MEDIUM'):
            with self.subTest(effort=effort), self.assertRaises(ValueError):
                r.Bridge(reasoning_effort=effort, **options)
        for effort in r.EFFORTS:
            with self.subTest(effort=effort):
                h = Harness(self, effort=effort); h.run()
                request = json.loads(h.requests[0])
                self.assertEqual(request['reasoning'], {'context': 'current_turn', 'effort': effort})
                self.assertNotIn('include', request)
                self.assertNotIn('previous_response_id', request)
                self.assertNotIn('conversation', request)
                self.assertEqual(request['tools'], [])
                self.assertEqual(request['truncation'], 'disabled')
                self.assertFalse(request['store'])

    def test_exact_private_opaque_capture_original_visible_phase_and_no_replay(self):
        h = Harness(self, actions=[{'action': 'inspect'}, f.final_action()]); h.run()
        first_response = json.loads(h.raw_replies[0])
        first_opaque, first_visible = first_response['output']
        second_request = json.loads(h.requests[1])
        self.assertIn(first_visible, second_request['input'])
        self.assertNotIn(first_opaque, second_request['input'])
        self.assertNotIn(first_opaque['encrypted_content'], h.requests[1].decode())
        self.assertNotIn(first_opaque['id'], h.requests[1].decode())
        self.assertEqual(first_visible['phase'], 'final_answer')
        self.assertEqual(h.pipe.actions, [{'action': 'inspect'}, f.final_action()])
        exchanges = [x for x in h.receipts if x[0]['event'] == 'exchange']
        for index, (meta, request, response) in enumerate(exchanges):
            self.assertEqual(request, h.requests[index])
            self.assertEqual(response, h.raw_replies[index])
            self.assertEqual(meta['response'], r.pin(response))
            self.assertEqual(meta['execution_policy'], 'current_turn_reasoning_v1')
            self.assertFalse(meta['prior_turn_opaque_replay'])
            self.assertEqual(meta['prior_opaque_items_seen'], index)
            expected_prior = [] if index == 0 else [first_opaque['id']]
            self.assertEqual(meta['unreplayed_previous_turn_opaque_ids'], expected_prior)
            self.assertFalse(meta['provider_report_is_action_authority'])
            self.assertEqual(meta['usage'], json.loads(response)['usage'])
            self.assertTrue(meta['usage_validated'])
            self.assertEqual(meta['visible_message'], r.pin(r.encode(json.loads(response)['output'][-1])))
        self.assertTrue(all(events[-1] == 'exchange' for events in h.pipe.receipts_at_emission))

    def test_absent_null_and_final_answer_phases_are_preserved_exactly(self):
        for phase in ('ABSENT', None, 'final_answer'):
            with self.subTest(phase=phase):
                def mutate(body):
                    message = body['output'][-1]
                    if phase == 'ABSENT': message.pop('phase')
                    else: message['phase'] = phase
                    return body
                h = Harness(self, actions=[{'action': 'inspect'}, f.final_action()], mutate=mutate); h.run()
                visible = json.loads(h.raw_replies[0])['output'][-1]
                self.assertEqual(json.loads(h.requests[1])['input'][1], visible)
                meta = next(meta for meta, _, _ in h.receipts if meta['event'] == 'exchange')
                self.assertEqual(meta['visible_phase_present'], phase != 'ABSENT')
                self.assertEqual(meta['visible_phase'], None if phase == 'ABSENT' else phase)

    def test_commentary_or_unknown_phase_cannot_become_viewer_action(self):
        for phase in ('commentary', 'analysis', '', 0, False, []):
            with self.subTest(phase=phase):
                def mutate(body): body['output'][-1]['phase'] = phase; return body
                self.failed(Harness(self, mutate=mutate), stage='reasoning_visible_phase')

    def test_missing_or_changed_effective_reasoning_policy_refused(self):
        changes = [None, {}, {'context': 'all', 'effort': 'medium'},
                   {'context': 'current_turn', 'effort': 'high'},
                   {'context': 'current_turn'}, {'effort': 'medium'},
                   {'context': 'current_turn', 'effort': 'medium', 'summary': 'auto'},
                   {'context': 'current_turn', 'effort': 'medium', 'generate_summary': 'concise'}]
        for reasoning in changes:
            with self.subTest(reasoning=reasoning):
                def mutate(body):
                    if reasoning is None: body.pop('reasoning')
                    else: body['reasoning'] = reasoning
                    return body
                self.failed(Harness(self, mutate=mutate), stage='reasoning_effective_policy')

    def test_transformations_absent_or_empty_only_and_preserved_on_failure(self):
        def omitted(body): body.pop('input_transformations'); return body
        h = Harness(self, mutate=omitted); h.run()
        for value in (None, {}, 'dropped', [{'type': 'truncation', 'removed': 1}]):
            with self.subTest(value=value):
                def mutate(body): body['input_transformations'] = value; return body
                h = Harness(self, mutate=mutate)
                self.failed(h, stage='reasoning_input_transformations')
                meta = next(meta for meta, _, _ in h.receipts if meta['event'] == 'exchange')
                self.assertEqual(meta['provider_report']['input_transformations'], value)

    def test_zero_and_eight_opaque_items_allowed_nine_refused(self):
        for count in (0, 8, 9):
            with self.subTest(count=count):
                def mutate(body):
                    prototype, message = body['output']
                    body['output'] = [dict(prototype, id='rs_generated_' + str(i)) for i in range(count)] + [message]
                    return body
                h = Harness(self, mutate=mutate)
                if count == 9:
                    self.failed(h, stage='reasoning_output_inventory')
                else:
                    h.run()
                    meta = next(meta for meta, _, _ in h.receipts if meta['event'] == 'exchange')
                    self.assertEqual(len(meta['opaque_reasoning_items']), count)

    def test_reasoning_item_fields_content_summary_status_and_identity(self):
        changes = [('id', ''), ('id', 'é'), ('id', 'x' * 161), ('id', True),
                   ('summary', None), ('summary', [{'type': 'summary_text', 'text': 'invented'}]),
                   ('content', [{'type': 'reasoning_text', 'text': 'invented'}]),
                   ('status', 'in_progress'), ('encrypted_content', ''),
                   ('encrypted_content', 4), ('unknown', 'invented')]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                def mutate(body): body['output'][0][key] = value; return body
                self.failed(Harness(self, mutate=mutate))
        for key in ('id', 'summary', 'encrypted_content'):
            with self.subTest(missing=key):
                def mutate(body): body['output'][0].pop(key); return body
                self.failed(Harness(self, mutate=mutate), stage='reasoning_item_shape')

    def test_optional_completed_status_and_empty_content_do_not_alter_visible_reply(self):
        def mutate(body): body['output'][0].update(status='completed', content=[]); return body
        h = Harness(self, mutate=mutate); h.run()
        self.assertEqual(h.pipe.actions, [f.final_action()])

    def test_duplicate_reasoning_and_visible_ids_and_wrong_output_order_refused(self):
        def duplicate_reasoning(body): body['output'].insert(1, dict(body['output'][0])); return body
        def duplicate_visible(body): body['output'][-1]['id'] = body['output'][0]['id']; return body
        def missing_visible(body): body['output'][-1].pop('id'); return body
        def wrong_order(body): body['output'].reverse(); return body
        def extra_visible(body): body['output'].append(dict(body['output'][-1])); return body
        def tool(body): body['output'][0] = {'type': 'function_call', 'name': 'python'}; return body
        for mutate in (duplicate_reasoning, duplicate_visible, missing_visible, wrong_order, extra_visible, tool):
            with self.subTest(case=mutate.__name__):
                self.failed(Harness(self, mutate=mutate))

    def test_opaque_capacity_counts_utf8_and_combined_items_not_characters(self):
        for excess in (False, True):
            with self.subTest(excess=excess):
                def mutate(body):
                    original, message = body['output']
                    first = dict(original, id='rs_first', encrypted_content='é' * 65536)
                    second = dict(original, id='rs_second', encrypted_content='é' * 65536 + ('x' if excess else ''))
                    body['output'] = [first, second, message]
                    return body
                h = Harness(self, mutate=mutate, allocation=budget(max_response_bytes=524288))
                if excess:
                    self.failed(h, stage='reasoning_opaque_byte_capacity')
                else:
                    h.run()
                    meta = next(meta for meta, _, _ in h.receipts if meta['event'] == 'exchange')
                    self.assertEqual(meta['opaque_reasoning_bytes'], 262144)

    def test_full_usage_retained_and_reasoning_tokens_not_double_counted(self):
        def mutate(body):
            body['max_output_tokens'] = 20
            body['usage']['output_tokens_details']['reasoning_tokens'] = 20
            body['usage']['provider_extra'] = {'generated_counter': 9}
            return body
        h = Harness(self, mutate=mutate, allocation=budget(context_tokens=120, output_tokens=20), bound=lambda *_: 100)
        h.run()
        meta = next(meta for meta, _, _ in h.receipts if meta['event'] == 'exchange')
        self.assertEqual(meta['usage'], json.loads(h.raw_replies[0])['usage'])
        self.assertEqual(meta['usage']['total_tokens'], 120)
        self.assertEqual(meta['usage']['output_tokens_details']['reasoning_tokens'], 20)

    def test_reasoning_usage_omissions_and_impossible_cached_counts_refused(self):
        def missing_details(body): body['usage'].pop('output_tokens_details'); return body
        def missing_count(body): body['usage']['output_tokens_details'] = {}; return body
        mutations = [missing_details, missing_count]
        for value in (None, True, -1, 21, 1.5):
            def mutate(body, value=value): body['usage']['output_tokens_details']['reasoning_tokens'] = value; return body
            mutations.append(mutate)
        for value in (None, True, -1, 101, 1.5):
            def mutate(body, value=value): body['usage']['input_tokens_details']['cached_tokens'] = value; return body
            mutations.append(mutate)
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                h = Harness(self, mutate=mutate)
                self.failed(h, stage='reasoning_token_accounting')
                meta = next(meta for meta, _, _ in h.receipts if meta['event'] == 'exchange')
                self.assertEqual(meta['provider_report']['usage'], json.loads(h.raw_replies[0])['usage'])
                self.assertNotIn('usage_validated', meta)

    def test_effective_context_preflight_and_actual_allocation_remain_enforced(self):
        h = Harness(self, bound=lambda *_: 20000)
        self.failed(h, calls=0, stage='input_token_capacity')
        def over_allocation(body):
            body['usage'].update(output_tokens=129, total_tokens=229)
            return body
        self.failed(Harness(self, mutate=over_allocation), stage='provider_token_accounting')

    def test_failed_and_incomplete_attempt_reports_preserve_exact_private_body(self):
        for status in ('failed', 'incomplete'):
            with self.subTest(status=status):
                def mutate(body):
                    body['status'] = status
                    body['error'] = {'code': 'generated_error', 'message': 'invented provider detail'}
                    body['incomplete_details'] = {'reason': 'max_output_tokens'}
                    return body
                h = Harness(self, mutate=mutate)
                self.failed(h)
                meta, request, response = next(x for x in h.receipts if x[0]['event'] == 'exchange')
                self.assertEqual(response, h.raw_replies[0])
                self.assertEqual(request, h.requests[0])
                self.assertEqual(meta['provider_report']['status'], status)
                self.assertEqual(meta['provider_report']['usage'], json.loads(response)['usage'])
                self.assertEqual(meta['provider_report']['reasoning'], {'context': 'current_turn', 'effort': 'medium'})
                self.assertFalse(meta['provider_report_is_action_authority'])

    def test_malformed_response_captured_without_fabricated_parsed_report(self):
        h = Harness(self, mutate=lambda _: b'{"reasoning":')
        self.failed(h, stage='reasoning_response_decode')
        meta, _, raw = next(x for x in h.receipts if x[0]['event'] == 'exchange')
        self.assertEqual(raw, b'{"reasoning":')
        self.assertNotIn('provider_report', meta)

    def test_unpaired_surrogate_in_private_usage_cannot_destroy_raw_failure_capture(self):
        def mutate(body):
            body['usage']['extra'] = chr(0xD800)
            return json.dumps(body, ensure_ascii=True).encode('ascii')
        h = Harness(self, mutate=mutate)
        self.failed(h)
        meta, request, raw = next(x for x in h.receipts if x[0]['event'] == 'exchange')
        self.assertEqual(raw, h.raw_replies[0])
        self.assertEqual(request, h.requests[0])
        self.assertIn(b'\\ud800', raw)
        self.assertEqual(meta['provider_report_projection'], 'unavailable_raw_body_retained')
        self.assertNotIn('provider_report', meta)
        self.assertFalse(meta['provider_report_is_action_authority'])
        self.assertEqual(meta['response'], r.pin(raw))

    def test_original_v1_remains_pinned_and_refuses_reasoning(self):
        binding = json.loads((HERE / 'SOURCE_BINDINGS.json').read_bytes())
        for name, expected in binding['members'].items():
            body = (HERE.parent / 'viewer-provider-v1' / name).read_bytes()
            self.assertEqual({'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}, expected)
        h = f.Harness(self, mutate=reasoning_body)
        self.failed(h, stage='provider_response_validation')

    def test_first_invalid_eeg_final_remains_terminal_with_reasoning(self):
        action = f.final_action('INVALID GENERATED SCALAR')
        h = Harness(self, actions=[action, f.final_action()])
        result = h.run()
        self.assertEqual(result['status'], 'invalid_response')
        self.assertEqual(h.pipe.actions, [action])
        self.assertEqual(len(h.requests), 1)
        self.assertEqual(h.receipts[-1][0]['terminal_status'], 'invalid_response')

    def test_rolling_31_32_33_preserves_visible_phase_only_and_all_private_bodies(self):
        actions = []
        for i in range(33):
            actions.extend([{'action': 'epoch', 'index': i},
                            {'action': 'respond', 'epoch_id': f'development-001/{i:05d}', 'probabilities': [0.2] * 5}])
        actions.append({'action': 'finish'})
        h = Harness(self, 'NEURAL-007', r.ROLLING_CONDITION, actions,
                    generated_epochs=33,
                    allocation=budget(max_turns=80, max_images=32, max_total_provider_bytes=4000000))
        self.assertEqual(h.run()['epochs'], 33)
        histories = [json.loads(raw)['input'] for raw in h.requests]
        self.assertEqual([len(histories[i]) for i in (30, 31, 32, 33)], [61, 63, 64, 64])
        self.assertTrue(all(history[0] == histories[0][0] for history in histories))
        first_visible = json.loads(h.raw_replies[0])['output'][-1]
        self.assertIn(first_visible, histories[31])
        self.assertNotIn(first_visible, histories[32])
        for raw, history in zip(h.requests, histories):
            self.assertNotIn(b'OPAQUE_GENERATED_', raw)
            self.assertTrue(all(item.get('type') != 'reasoning' for item in history))
            self.assertTrue(all(item.get('phase') == 'final_answer' for item in history if item.get('role') == 'assistant'))
        exchanges = [row for row in h.receipts if row[0]['event'] == 'exchange']
        self.assertEqual(len(exchanges), 67)
        self.assertEqual([row[2] for row in exchanges], h.raw_replies)
        for index, (meta, _, _) in enumerate(exchanges):
            self.assertEqual(meta['prior_opaque_items_seen'], index)
            expected = [] if index == 0 else [json.loads(h.raw_replies[index - 1])['output'][0]['id']]
            self.assertEqual(meta['unreplayed_previous_turn_opaque_ids'], expected)
        self.assertEqual(len(h.session.answers), 33)
        self.assertEqual(h.bridge.images, 33)

    def test_reasoning_does_not_restore_evicted_answer_or_allow_replacement(self):
        original = {'action': 'respond', 'epoch_id': 'development-001/00000', 'probabilities': [0.2] * 5}
        actions = [{'action': 'epoch', 'index': 0}, original, {'action': 'epoch', 'index': 1}]
        actions += [{'action': 'inspect'}] * 33
        actions += [{'action': 'epoch', 'index': 0}, dict(original, probabilities=[0, 0, 0, 0, 1])]
        h = Harness(self, 'NEURAL-007', r.ROLLING_CONDITION, actions,
                    allocation=budget(max_turns=50, max_images=32, max_total_provider_bytes=4000000))
        self.failed(h, calls=len(actions), actions=len(actions) - 1, stage='viewer_action_validation')
        self.assertEqual(h.session.answers, {0: [0.2] * 5})
        self.assertNotIn(json.loads(h.raw_replies[1])['output'][-1], json.loads(h.requests[-1])['input'])
        self.assertNotIn(b'OPAQUE_GENERATED_', h.requests[-1])

    def test_private_sink_failure_cannot_emit_reasoning_validated_action(self):
        def failing(meta, *_):
            if meta['event'] == 'exchange': raise OSError('generated private sink failure')
        h = Harness(self, record_hook=failing)
        with self.assertRaisesRegex(ValueError, 'receipt_callback'):
            h.run()
        self.assertEqual(len(h.requests), 1)
        self.assertEqual(h.pipe.actions, [])
        self.assertTrue(h.bridge.sink_failed)

    def test_sender_failure_after_reasoning_turn_preserves_prior_attempt_without_replay(self):
        h = Harness(self, actions=[{'action': 'inspect'}, f.final_action()])
        original_send = h.bridge.send_json
        def send(request, deadline):
            if h.requests:
                h.requests.append(request)
                raise RuntimeError('Bearer GENERATED_REASONING_SECRET')
            return original_send(request, deadline)
        h.bridge.send_json = send
        self.failed(h, calls=2, actions=1, stage='sender_callback')
        self.assertNotIn(b'OPAQUE_GENERATED_', h.requests[-1])
        self.assertNotIn(b'GENERATED_REASONING_SECRET', r.encode([x[0] for x in h.receipts]))
        exchanges = [x for x in h.receipts if x[0]['event'] == 'exchange']
        self.assertEqual(exchanges[0][2], h.raw_replies[0])
        self.assertIsNone(exchanges[1][2])


if __name__ == '__main__':
    unittest.main()
