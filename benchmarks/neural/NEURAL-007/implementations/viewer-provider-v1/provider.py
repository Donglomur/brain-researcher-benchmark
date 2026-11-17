"""Injected image/action bridge. No HTTP, credentials, models or data loading.

This is an operator-side source seam, not an authorized network client. The
existing participant sandbox remains network-denying. A real broker placement,
endpoint, image/token capacity and isolation still need separate qualification.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('viewer_provider_policy', HERE / 'policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
need = policy.need
PROVIDER_IMAGE_CAP = 1500
PROVIDER_REQUEST_CAP = 512000000  # Conservative decimal interpretation of 512 MB.
ROLLING_CONDITION = 'whole_person_raw_viewer_last32_turns_zero_shot_v1'
SLEEP_CONDITION = 'whole_person_raw_viewer_zero_shot'


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def decode(body):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


@dataclass(frozen=True)
class Budget:
    max_turns: int
    max_images: int
    max_history_bytes: int
    max_request_bytes: int
    max_response_bytes: int
    max_total_provider_bytes: int
    context_tokens: int
    output_tokens: int
    wall_seconds: float
    image_detail: str = 'original'

    def validate(self):
        for name in ('max_turns', 'max_images', 'max_history_bytes', 'max_request_bytes',
                     'max_response_bytes', 'max_total_provider_bytes', 'context_tokens', 'output_tokens'):
            need(type(getattr(self, name)) is int and getattr(self, name) > 0, 'Positive explicit integral budgets')
        need(self.max_turns <= 100000 and self.max_images <= PROVIDER_IMAGE_CAP, 'Turn/image service ceiling')
        need(self.max_history_bytes <= self.max_request_bytes <= PROVIDER_REQUEST_CAP, 'Bounded complete history/request')
        need(self.max_response_bytes <= 524288 and self.output_tokens <= 32768 and self.output_tokens < self.context_tokens, 'Response/context bounds')
        need(type(self.wall_seconds) in (int, float) and math.isfinite(self.wall_seconds) and 0 < self.wall_seconds <= 86400, 'Wall budget')
        need(self.image_detail in ('high', 'original'), 'Explicit image detail; no automatic low-resolution fallback')


class Bridge:
    """One fresh viewer session; full or explicitly named last32 visible history.

    send_json and input_token_bound receive the absolute monotonic deadline.
    They and the binary streams must enforce their I/O deadlines externally;
    this synchronous source cannot preempt a blocked callback. The token-bound
    callback includes image/schema overhead and is unqualified until audited.
    record receives private exact bodies (never HTTP headers) before any action
    emission. It must durably retain them or raise. No default sender exists.
    """
    def __init__(self, *, task, condition, model, budget, send_json, input_token_bound, record):
        need(type(model) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', model), 'Explicit model identity')
        need(type(budget) is Budget, 'Explicit budget')
        budget.validate()
        need(all(callable(x) for x in (send_json, input_token_bound, record)), 'Injected trusted callbacks')
        self.condition = condition
        self.rolling = condition == ROLLING_CONDITION
        need(not self.rolling or task == 'NEURAL-007', 'Rolling condition is sleep-only')
        need(not self.rolling or budget.max_images == 32, 'Prospective rolling condition fixes 32 image slots')
        self.p, self.model, self.b = policy.Policy(task, SLEEP_CONDITION if self.rolling else condition), model, budget
        self.send_json, self.input_token_bound, self.record = send_json, input_token_bound, record
        self.used, self.sink_failed = False, False
        self.history, self.images, self.turns, self.provider_bytes = [], 0, 0, 0
        self.initial, self.visible_turns, self.evicted_turns = None, [], 0
        self.sequence, self.previous = 0, '0' * 64
        self.deadline = None
        self.stage = 'not_started'

    def clock(self):
        if time.monotonic() >= self.deadline:
            self.stage = 'wall_deadline'
            need(False, 'Deadline exhausted')

    def receipt(self, event, request=None, response=None, **details):
        meta = {'schema': 'neural-viewer-responses-bridge/v1', 'event': event,
                'sequence': self.sequence, 'previous_sha256': self.previous,
                'task': self.p.task, 'condition': self.condition, 'viewer_condition': self.p.condition,
                'episode_id': self.p.episode,
                'turn': self.turns, 'model': self.model, 'retry_count': 0,
                'request': None if request is None else pin(request),
                'response': None if response is None else pin(response),
                'provider_bytes': self.provider_bytes,
                'history_policy': 'initial_plus_last32_visible_turns' if self.rolling else 'full_visible_transcript_no_hidden_reasoning',
                'evicted_complete_turns': self.evicted_turns,
                'observed_images': self.images,
                'retained_turns': len(self.visible_turns) if self.rolling else self.turns,
                'provider_execution_qualified': False, 'provider_capacity_qualified': False,
                'scientific_qualification': False, **details}
        encoded = encode(meta)
        previous_stage, self.stage = self.stage, 'receipt_callback'
        try:
            self.record(decode(encoded), request, response)
        except Exception:
            self.sink_failed = True
            raise ValueError('Private receipt sink failed; no further action') from None
        self.stage = previous_stage
        self.previous, self.sequence = pin(encoded)['sha256'], self.sequence + 1

    def read(self, stream):
        self.stage = 'viewer_frame_read'
        def take(size):
            result = bytearray()
            while len(result) < size:
                self.clock()
                self.stage = 'viewer_frame_read'
                part = stream.read(size - len(result))
                need(type(part) is bytes and 0 < len(part) <= size - len(result), 'Incomplete viewer frame')
                result.extend(part)
            self.clock()
            return bytes(result)
        prefix = take(self.p.t.PREFIX.size)
        hs, ps = self.p.t.PREFIX.unpack(prefix)
        self.stage = 'viewer_frame_capacity'
        need(0 < hs <= self.p.t.HEADER_MAX and 0 <= ps <= self.p.t.PNG_MAX, 'Frame lengths')
        need(hs + ps <= self.b.max_history_bytes, 'Frame cannot fit history budget')
        raw = prefix + take(hs + ps)
        self.stage = 'viewer_frame_validation'
        header, png = self.p.t.unpack(raw)
        return raw, header, png

    def append(self, header, png, *, initial=False):
        content = [{'type': 'input_text', 'text': encode(header).decode()}]
        if png:
            content.append({'type': 'input_image', 'image_url': 'data:image/png;base64,' + base64.b64encode(png).decode('ascii'), 'detail': self.b.image_detail})
        observation = {'role': 'user', 'content': content}
        if self.rolling:
            if initial:
                need(self.initial is None and not png, 'Immutable sleep instructions without initial image')
                self.initial = observation
                self.visible_turns = [[]]  # First instruction-only action still counts as a turn.
            else:
                need(self.initial is not None and self.visible_turns and self.visible_turns[-1][-1]['role'] == 'assistant', 'Previous turn must be complete')
                if len(self.visible_turns) == 32:
                    self.visible_turns.pop(0)
                    self.evicted_turns += 1
                self.visible_turns.append([observation])
            self.history = [self.initial] + [item for turn in self.visible_turns for item in turn]
        else:
            self.history.append(observation)
        visible_images = sum(part.get('type') == 'input_image' for item in self.history
                             if type(item['content']) is list for part in item['content'])
        self.stage = 'visible_history_image_capacity'
        need(visible_images <= self.b.max_images, 'Visible-history image capacity exhausted')
        self.stage = 'visible_history_byte_capacity'
        need(len(encode(self.history)) <= self.b.max_history_bytes, 'Full visible history capacity exhausted')

    def append_action(self, text):
        item = {'role': 'assistant', 'content': text}
        self.stage = 'visible_history_byte_capacity'
        need(len(encode(self.history + [item])) <= self.b.max_history_bytes, 'Action cannot fit complete history')
        if self.rolling:
            self.visible_turns[-1].append(item)
        self.history.append(item)

    def request(self):
        return encode({'model': self.model, 'input': self.history,
                       'instructions': ('Use only the original viewer actions in the supplied task instructions. Return one JSON object with viewer_action containing exactly the next typed viewer action. No tools, code, files, retrieval or other-session memory. '
                                        + ('Memory condition: immutable initial instructions plus at most31 complete observation/action turns and the current observation. Older turns are removed automatically in order; no summaries or saved answer memory are supplied. Original explicit viewer navigation remains available.' if self.rolling else 'Memory condition: the complete visible observation/action transcript of this one session.')),
                       'tools': [], 'tool_choice': 'none', 'parallel_tool_calls': False,
                       'store': False, 'stream': False, 'background': False, 'truncation': 'disabled',
                       'max_output_tokens': self.b.output_tokens,
                       'text': {'format': {'type': 'json_schema', 'name': 'viewer_action', 'strict': True, 'schema': self.p.schema()}}})

    def response(self, raw, token_bound):
        self.stage = 'provider_response_validation'
        value = decode(raw)
        need(type(value) is dict and value.get('object') == 'response' and value.get('status') == 'completed' and value.get('error') is None and value.get('incomplete_details') is None, 'Complete provider response')
        need(value.get('tools') == [] and value.get('tool_choice') == 'none' and value.get('parallel_tool_calls') is False and value.get('store') is False and value.get('truncation') == 'disabled' and value.get('previous_response_id') is None and value.get('conversation') is None, 'Provider policy/history mismatch')
        need(value.get('background', False) is False, 'Background response refused')
        need(value.get('model') == self.model and type(value.get('max_output_tokens')) is int and value['max_output_tokens'] == self.b.output_tokens, 'Model/output allocation mismatch')
        need(type(value.get('id')) is str and re.fullmatch('resp_[A-Za-z0-9_-]{1,160}', value['id']), 'Provider response identity')
        output = value.get('output')
        # No silently discarded reasoning/tool/provider state. This narrow route
        # accepts only the visible final action message, not reasoning output items.
        need(type(output) is list and len(output) == 1 and type(output[0]) is dict, 'One visible output message')
        message = output[0]
        need(set(message) <= {'id', 'type', 'role', 'status', 'content'}, 'Unrecognized assistant state')
        need(message.get('type') == 'message' and message.get('role') == 'assistant' and message.get('status') == 'completed', 'Visible assistant message required')
        content = message.get('content')
        need(type(content) is list and len(content) == 1 and type(content[0]) is dict and content[0].get('type') == 'output_text' and type(content[0].get('text')) is str, 'Refusal/non-text response')
        need(set(content[0]) <= {'type', 'text', 'annotations', 'logprobs'} and content[0].get('annotations', []) == [] and content[0].get('logprobs', []) in ([], None), 'Unsupported extra output state')
        text = content[0]['text']
        wrapped = decode(text)
        need(type(wrapped) is dict and set(wrapped) == {'viewer_action'} and type(wrapped['viewer_action']) is dict, 'Exact action wrapper')
        usage = value.get('usage')
        self.stage = 'provider_token_accounting'
        need(type(usage) is dict and all(type(usage.get(k)) is int and 0 <= usage[k] <= 100000000 for k in ('input_tokens', 'output_tokens', 'total_tokens')), 'Token accounting')
        counts = {key: usage[key] for key in ('input_tokens', 'output_tokens', 'total_tokens')}
        need(counts['input_tokens'] <= token_bound and counts['output_tokens'] <= self.b.output_tokens and counts['total_tokens'] == counts['input_tokens'] + counts['output_tokens'] and counts['total_tokens'] <= self.b.context_tokens, 'Token capacity/accounting mismatch')
        return text, wrapped['viewer_action'], {'provider_response_id': value['id'], 'usage': counts, 'provider_text': pin(text.encode())}

    def exchange(self):
        self.clock()
        self.stage = 'turn_capacity'
        need(self.turns < self.b.max_turns, 'Turn budget exhausted')
        self.stage = 'request_construction'
        request, raw, attempted = self.request(), None, False
        status, details = 'failed_no_action', {}
        try:
            self.stage = 'request_byte_capacity'
            need(len(request) <= self.b.max_request_bytes, 'Complete request exceeds capacity')
            # Reserve worst-case response bytes before sending, never spend into
            # an inevitable cumulative-budget overrun.
            self.stage = 'cumulative_provider_byte_capacity'
            need(self.provider_bytes + len(request) + self.b.max_response_bytes <= self.b.max_total_provider_bytes, 'Cumulative provider byte capacity')
            self.stage = 'token_bound_callback'
            bound = self.input_token_bound(request, self.deadline)
            self.stage = 'input_token_capacity'
            need(type(bound) is int and bound > 0 and bound + self.b.output_tokens <= self.b.context_tokens, 'Complete input token capacity')
            self.clock()
            attempted, self.turns = True, self.turns + 1
            self.provider_bytes += len(request)
            self.stage = 'sender_callback'
            raw = self.send_json(request, self.deadline)
            self.stage = 'provider_response_byte_capacity'
            need(type(raw) is bytes, 'Raw provider bytes required')
            self.provider_bytes += len(raw)
            need(0 < len(raw) <= self.b.max_response_bytes, 'Provider response size')
            self.clock()
            text, action, details = self.response(raw, bound)
            self.stage = 'viewer_action_validation'
            frame = self.p.action(action)
            self.append_action(text)
            details.update(action_frame=pin(frame), input_token_bound=bound)
            status = 'action_prepared_unscored'
            return frame
        finally:
            # Keep the exact attempted body even if malformed; never retain HTTP
            # headers or callback exception text. A failing sink withholds action.
            self.receipt('exchange', request, raw if type(raw) is bytes else None,
                         sender_calls_attempted=int(attempted), status=status,
                         failure_stage=self.stage if status == 'failed_no_action' else None, **details)

    def serve(self, binary_in, binary_out):
        need(not self.used, 'Bridge instances are single-session only')
        self.used, self.deadline = True, time.monotonic() + self.b.wall_seconds
        try:
            raw, header, png = self.read(binary_in)
            self.stage = 'ready_projection_validation'
            self.p.ready(header, png)
            self.images += bool(png)
            self.receipt('ready', frame=pin(raw), budget=asdict(self.b))
            if self.p.task == 'NEURAL-007':
                self.stage = 'canonical_full_history_image_capacity'
                need(self.rolling or self.p.epochs <= self.b.max_images, 'Canonical person exceeds full-history image capacity')
                self.stage = 'whole_person_turn_capacity'
                need(2 * self.p.epochs + 1 <= self.b.max_turns, 'Whole-person minimum turn capacity')
            self.append(header, png, initial=True)
            while True:
                frame = self.exchange()
                self.clock()
                self.stage = 'action_emission'
                sent = 0
                while sent < len(frame):
                    count = binary_out.write(frame[sent:])
                    need(type(count) is int and 0 < count <= len(frame) - sent, 'Incomplete action write')
                    sent += count
                    self.clock()
                binary_out.flush()
                self.clock()
                self.receipt('action_emitted', action_frame=pin(frame))
                raw, header, png = self.read(binary_in)
                self.stage = 'viewer_reply_validation'
                terminal = self.p.observe(header, png)
                self.images += bool(png)
                self.receipt('viewer_reply', frame=pin(raw), image=None if not png else pin(png), terminal=terminal)
                if terminal:
                    self.receipt('session_terminal', terminal_status=header.get('status', header.get('kind')))
                    self.clock()
                    return header
                self.append(header, png)
        except Exception:
            if not self.sink_failed:
                self.receipt('failed_no_further_action', failure_stage=self.stage)
            raise ValueError('Viewer provider bridge failed at ' + self.stage + '; no retry or further action') from None
