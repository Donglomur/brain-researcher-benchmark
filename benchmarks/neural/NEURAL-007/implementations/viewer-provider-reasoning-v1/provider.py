"""Narrow current-turn reasoning extension of the frozen injected image bridge.

Opaque reasoning is retained privately, never decrypted or replayed. No HTTP,
credentials, SDK, models, signals, extra tools or actual provider qualification.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'viewer-provider-v1'
POLICY = 'current_turn_reasoning_v1'
MAX_REASONING_ITEMS = 8
MAX_OPAQUE_BYTES = 262144
EFFORTS = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')


def load_previous():
    binding = json.loads((HERE / 'SOURCE_BINDINGS.json').read_bytes())
    if set(binding) != {'schema', 'members'} or binding['schema'] != 'neural-current-turn-reasoning-dependencies/v1' or set(binding['members']) != {'provider.py', 'policy.py', 'SOURCE_BINDINGS.json'}:
        raise ValueError('Exact frozen bridge dependencies required')
    for name, expected in binding['members'].items():
        path = PREVIOUS / name
        if path.is_symlink() or path.stat().st_size != expected['bytes']:
            raise ValueError('Frozen bridge source size mismatch')
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != expected['sha256']:
            raise ValueError('Frozen bridge source identity mismatch')
    spec = importlib.util.spec_from_file_location('current_turn_previous_bridge', PREVIOUS / 'provider.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


previous = load_previous()
Budget, need, encode, decode, pin = previous.Budget, previous.need, previous.encode, previous.decode, previous.pin
ROLLING_CONDITION = previous.ROLLING_CONDITION


def identifier(value):
    return type(value) is str and re.fullmatch('[A-Za-z0-9_-]{1,160}', value) is not None


class Bridge(previous.Bridge):
    """Same viewer lifecycle/history, with explicitly current-turn-only reasoning.

    reasoning_effort is required, frozen and echoed exactly. Listing a value in
    the API schema does not establish support by the selected model. A response
    may contain up to eight opaque reasoning items followed by one final action.
    The original entire body and full usage remain private before action output.
    """
    def __init__(self, *, reasoning_effort, **kwargs):
        need(type(reasoning_effort) is str and reasoning_effort in EFFORTS,
             'Explicit documented reasoning effort required')
        self.reasoning_effort = reasoning_effort
        self._visible_message = None
        self._prior_opaque_ids = []
        self._opaque_items_seen = 0
        super().__init__(**kwargs)

    def request(self):
        value = decode(super().request())
        value['reasoning'] = {'context': 'current_turn', 'effort': self.reasoning_effort}
        # No include is required by the current stateless API. No prior response
        # ID, conversation, reasoning input, summary or configuration update.
        return encode(value)

    def receipt(self, event, request=None, response=None, **details):
        details.update(execution_policy=POLICY,
                       requested_reasoning={'context': 'current_turn', 'effort': self.reasoning_effort},
                       prior_turn_opaque_replay=False,
                       unreplayed_previous_turn_opaque_ids=list(self._prior_opaque_ids),
                       prior_opaque_items_seen=self._opaque_items_seen)
        # Capture failed/incomplete attempts as well as successes. Parsing this
        # bounded body is only for private evidence; it never authorizes an action.
        # The exact raw body remains authoritative if parsing/shape checks fail.
        if event == 'exchange' and type(response) is bytes and len(response) <= self.b.max_response_bytes:
            try:
                value = decode(response)
            except (ValueError, UnicodeError, TypeError, RecursionError, OverflowError):
                value = None
            if type(value) is dict:
                report = {key: value[key] for key in
                    ('status', 'error', 'incomplete_details', 'usage', 'reasoning', 'input_transformations') if key in value}
                try:
                    # Ensure nesting is safe inside the receipt envelope. An
                    # unprojectable report cannot prevent exact raw retention.
                    encode({'provider_report': report})
                except (ValueError, UnicodeError, TypeError, RecursionError, OverflowError):
                    details['provider_report_projection'] = 'unavailable_raw_body_retained'
                else:
                    details['provider_report'] = report
                details['provider_report_is_action_authority'] = False
        super().receipt(event, request, response, **details)

    def response(self, raw, token_bound):
        self._visible_message = None
        self.stage = 'reasoning_response_decode'
        value = decode(raw)
        need(type(value) is dict, 'Response object required')
        self.stage = 'reasoning_effective_policy'
        reasoning = value.get('reasoning')
        need(type(reasoning) is dict and reasoning.get('context') == 'current_turn' and
             reasoning.get('effort') == self.reasoning_effort, 'Effective reasoning context/effort mismatch')
        need(reasoning.get('summary') is None and reasoning.get('generate_summary') is None,
             'Reasoning summaries not requested')
        self.stage = 'reasoning_input_transformations'
        need('input_transformations' not in value or value['input_transformations'] == [],
             'Unexpected reasoning input transformation')
        self.stage = 'reasoning_output_inventory'
        output = value.get('output')
        need(type(output) is list and 1 <= len(output) <= MAX_REASONING_ITEMS + 1 and
             all(type(item) is dict for item in output), 'Bounded output inventory required')
        opaque, message = output[:-1], output[-1]
        need(message.get('type') == 'message' and all(item.get('type') == 'reasoning' for item in opaque),
             'Only opaque reasoning followed by one final message')
        identities, inventory, opaque_bytes = set(), [], 0
        for item in opaque:
            self.stage = 'reasoning_item_shape'
            need(set(item) <= {'id', 'type', 'summary', 'encrypted_content', 'status', 'content'} and
                 {'id', 'type', 'summary', 'encrypted_content'} <= set(item), 'Opaque reasoning fields')
            need(identifier(item['id']) and item['id'] not in identities, 'Unique bounded reasoning identity')
            identities.add(item['id'])
            need(item['summary'] == [] and item.get('content', []) == [] and
                 ('status' not in item or item['status'] == 'completed'), 'Completed opaque item without raw text/summary')
            encrypted = item['encrypted_content']
            need(type(encrypted) is str and bool(encrypted), 'Nonempty opaque content')
            body = encrypted.encode('utf-8')
            opaque_bytes += len(body)
            self.stage = 'reasoning_opaque_byte_capacity'
            need(opaque_bytes <= MAX_OPAQUE_BYTES, 'Opaque reasoning local byte limit')
            inventory.append({'id': item['id'], 'opaque': pin(body), 'item': pin(encode(item))})
        self.stage = 'reasoning_visible_phase'
        need(identifier(message.get('id')) and message['id'] not in identities,
             'Unique bounded visible message identity')
        need('phase' not in message or message['phase'] in (None, 'final_answer'),
             'One final message; commentary is not a viewer action')
        # Reuse every frozen model/policy/action/token check. This validation-only
        # copy omits phase for the old parser; original message and raw response
        # are preserved, and the original message is the replayed visible item.
        checked = dict(value)
        checked['output'] = [{key: item for key, item in message.items() if key != 'phase'}]
        text, action, metadata = super().response(encode(checked), token_bound)
        self.stage = 'reasoning_token_accounting'
        usage = value['usage']
        output_details = usage.get('output_tokens_details')
        need(type(output_details) is dict and type(output_details.get('reasoning_tokens')) is int and
             0 <= output_details['reasoning_tokens'] <= usage['output_tokens'], 'Reasoning usage within output allocation')
        if 'input_tokens_details' in usage:
            need(type(usage['input_tokens_details']) is dict, 'Input usage details object')
            if 'cached_tokens' in usage['input_tokens_details']:
                cached = usage['input_tokens_details']['cached_tokens']
                need(type(cached) is int and 0 <= cached <= usage['input_tokens'], 'Cached input usage bound')
        self._visible_message = decode(encode(message))
        metadata.update(usage=decode(encode(usage)), usage_validated=True,
                        opaque_reasoning_items=inventory, opaque_reasoning_bytes=opaque_bytes,
                        visible_message=pin(encode(message)),
                        visible_phase_present='phase' in message,
                        visible_phase=message.get('phase'))
        # Updated only after the exchange receipt: its prior-item list refers to
        # what this request intentionally did not replay, not its own new output.
        self._next_opaque_ids = [item['id'] for item in opaque]
        return text, action, metadata

    def append_action(self, text):
        self.stage = 'reasoning_visible_message_retention'
        need(self._visible_message is not None and
             self._visible_message['content'][0]['text'] == text, 'Validated original visible message required')
        item = self._visible_message
        need(len(encode(self.history + [item])) <= self.b.max_history_bytes, 'Visible history byte capacity')
        if self.rolling:
            self.visible_turns[-1].append(item)
        self.history.append(item)

    def exchange(self):
        frame = super().exchange()
        self._prior_opaque_ids = list(self._next_opaque_ids)
        self._opaque_items_seen += len(self._next_opaque_ids)
        return frame
