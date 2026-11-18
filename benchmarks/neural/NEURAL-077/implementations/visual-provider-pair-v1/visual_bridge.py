"""Exact image-history Requests adapter for the existing N077 typed viewer.

No HTTP, credentials, model invocation or signal arrays occur in this module.
Provider output text is forwarded unchanged; the original viewer owns action
validation and locks the first validly shaped finalize, even for a bad scalar.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import struct

PREFIX = struct.Struct('!II')
HEADER_CAP = 32768
PNG_CAP = 4 * 1024 * 1024
ACTION_CAP = 8192
RESPONSE_CAP = 524288
REQUEST_CAP = 8 * 1024 * 1024
POLICY = ('Return exactly one JSON viewer action from the supplied action schema. '
          'Use only the supplied viewer images, metadata and demonstrations. '
          'Do not use tools, code execution, external retrieval, files, or memory '
          'from other query trials. A finalize response is terminal and cannot '
          'be replaced. Never invent additional observations or query feedback.')


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def decode(body):
    return json.loads(body.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def encode(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False,
                       sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def identifier(value):
    need(type(value) is str and re.fullmatch(r'development-00[12]-[0-9a-f]{24}', value),
         'Exact original query identity required')
    return value


def take(stream, size):
    body = bytearray()
    while len(body) < size:
        part = stream.read(size - len(body))
        need(type(part) is bytes and 0 < len(part) <= size - len(body), 'Incomplete viewer frame')
        body.extend(part)
    return bytes(body)


def read_frame(stream):
    prefix = take(stream, PREFIX.size)
    hsize, psize = PREFIX.unpack(prefix)
    need(0 < hsize <= HEADER_CAP and 0 <= psize <= PNG_CAP, 'Viewer frame bound')
    raw_header, png = take(stream, hsize), take(stream, psize)
    header = decode(raw_header)
    need(type(header) is dict, 'Viewer header must be an object')
    if png:
        need(png.startswith(b'\x89PNG\r\n\x1a\n'), 'Image frame must contain PNG bytes')
    return header, png, prefix + raw_header + png


def write_action(stream, action):
    need(type(action) is bytes and 0 < len(action) <= ACTION_CAP, 'Bounded exact action text required')
    action.decode('utf-8')
    frame = PREFIX.pack(len(action), 0) + action
    written = 0
    while written < len(frame):
        count = stream.write(frame[written:])
        need(type(count) is int and 0 < count <= len(frame) - written, 'Incomplete viewer action write')
        written += count
    stream.flush()
    return frame


def first_frame(header, png, trial_id, encode_png):
    identifier(trial_id)
    need(set(header) == {'status', 'episode_id', 'trial_id', 'prompt', 'actions', 'limits',
                         'instructions', 'initial'} and header['status'] == 'ready'
         and header['trial_id'] == trial_id, 'Exact initial viewer projection required')
    need(type(header['episode_id']) is str and re.fullmatch(r'[0-9a-f]{32}', header['episode_id']),
         'Fresh viewer episode identity required')
    prompt = header['prompt']
    need(type(prompt) is str and 0 < len(prompt.encode()) <= HEADER_CAP
         and set(re.findall(r'development-00[12]-[0-9a-f]{24}', prompt)) == {trial_id},
         'One original scientific prompt required')
    projection(header['initial'], png)
    need(header['initial']['status'] == 'rendered' and bool(png), 'Initial image required')
    need(type(header['actions']) is dict and type(header['limits']) is dict
         and type(header['instructions']) is str, 'Original declared action interface required')
    # First content remains the exact scientific prompt for inherited Sender's
    # context guard. Policy and display JSON are separate visible content.
    metadata = {key: value for key, value in header.items() if key != 'prompt'}
    delivered, image_mapping = encode_png(png)
    return [{'role': 'user', 'content': [
        {'type': 'input_text', 'text': prompt},
        {'type': 'input_text', 'text': POLICY},
        {'type': 'input_text', 'text': encode(metadata).decode()},
        {'type': 'input_image', 'image_url': 'data:image/png;base64,' + base64.b64encode(delivered).decode('ascii'),
         'detail': 'high'}]}], image_mapping


def projection(header, png):
    need(type(header) is dict and type(header.get('status')) is str, 'Exact viewer projection required')
    status = header['status']
    if status == 'rendered':
        need(set(header) == {'status', 'display', 'remaining_actions', 'image'}
             and type(header['display']) is dict and type(header['remaining_actions']) is int
             and header['remaining_actions'] >= 0 and type(header['image']) is dict
             and header['image'] == {'mime_type': 'image/png', 'bytes': len(png)} and bool(png),
             'Exact rendered image projection required')
        need(header['display'].get('record') != 'query'
             or 'demonstration_target' not in header['display'], 'Query labels prohibited')
    elif status == 'rejected':
        need(set(header) == {'status', 'error', 'remaining_actions'} and not png
             and type(header['error']) is str and type(header['remaining_actions']) is int,
             'Exact rejection projection required')
    elif status in ('valid_unscored', 'invalid_response'):
        need(set(header) == {'status', 'response_sha256', 'terminal'} and not png
             and header['terminal'] is True and type(header['response_sha256']) is str
             and re.fullmatch(r'[0-9a-f]{64}', header['response_sha256']), 'Exact final projection required')
    elif status == 'closed':
        need(set(header) == {'status', 'error', 'terminal'} and not png and header['terminal'] is True,
             'Exact closed projection required')
    else:
        raise ValueError('Unknown viewer projection')


def append_frame(history, action, header, png, encode_png):
    projection(header, png)
    content = [{'type': 'input_text', 'text': encode(header).decode()}]
    image_mapping = None
    if png:
        delivered, image_mapping = encode_png(png)
        content.append({'type': 'input_image', 'image_url': 'data:image/png;base64,' + base64.b64encode(delivered).decode('ascii'),
                        'detail': 'high'})
    return history + [{'role': 'assistant', 'content': [{'type': 'output_text', 'text': action.decode('utf-8')}]},
                      {'role': 'user', 'content': content}], image_mapping


def request_body(history, model, max_output_tokens, cap=REQUEST_CAP):
    need(type(model) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', model), 'Explicit model identity')
    need(type(max_output_tokens) is int and 1 <= max_output_tokens <= 32768, 'Output token allocation')
    need(type(cap) is int and 1 <= cap <= REQUEST_CAP and type(history) is list and 1 <= len(history) <= 253,
         'Bounded complete local history required')
    body = encode({'model': model, 'input': history, 'tools': [], 'tool_choice': 'none',
                   'parallel_tool_calls': False, 'store': False, 'stream': False, 'background': False,
                   'truncation': 'disabled', 'max_output_tokens': max_output_tokens,
                   'text': {'format': {'type': 'json_object'}}})
    need(len(body) <= cap, 'Complete history exceeds declared provider request cap; no truncation')
    return body


def typed_finalize(action):
    """Recognize only the viewer's exact finalize envelope, never parse its scalar."""
    try:
        value = decode(action)
    except (ValueError, UnicodeError, TypeError, RecursionError, OverflowError):
        return None
    if (type(value) is dict and set(value) == {'action', 'response'} and value['action'] == 'finalize'
            and type(value['response']) is str and len(value['response'].encode()) <= 4096):
        return value['response'].encode()
    return None


def completed_action(body, model, max_output_tokens):
    need(type(body) is bytes and 0 < len(body) <= RESPONSE_CAP, 'Bounded provider response required')
    value = decode(body)
    need(type(value) is dict and value.get('object') == 'response' and value.get('status') == 'completed'
         and value.get('error') is None and value.get('incomplete_details') is None, 'Incomplete provider response')
    need(value.get('tools') == [] and value.get('tool_choice') == 'none'
         and value.get('parallel_tool_calls') is False and value.get('store') is False
         and value.get('truncation') == 'disabled' and value.get('previous_response_id') is None
         and value.get('conversation') is None, 'Provider policy/history mismatch')
    need(value.get('model') == model and type(value.get('max_output_tokens')) is int
         and value['max_output_tokens'] == max_output_tokens, 'Provider model/allocation mismatch')
    need(type(value.get('id')) is str and re.fullmatch(r'resp_[A-Za-z0-9_-]{1,160}', value['id']),
         'Bounded provider response identity required')
    output = value.get('output')
    need(type(output) is list and 1 <= len(output) <= 32, 'Bounded response inventory')
    messages = []
    for item in output:
        need(type(item) is dict and item.get('type') in ('reasoning', 'message'), 'Tool or unsupported output forbidden')
        if item['type'] == 'message':
            messages.append(item)
    need(len(messages) == 1, 'Exactly one assistant message required')
    message = messages[0]
    need(message.get('role') == 'assistant' and message.get('status') == 'completed'
         and type(message.get('content')) is list and len(message['content']) == 1, 'One completed text content required')
    content = message['content'][0]
    need(type(content) is dict and content.get('type') == 'output_text' and type(content.get('text')) is str,
         'Refusal or nontext content is not a viewer action')
    action = content['text'].encode('utf-8')
    need(0 < len(action) <= ACTION_CAP, 'Bounded original viewer action text required')
    # Do not repair, strip fields or parse the nested final scalar. The original
    # viewer records malformed actions and owns its established rejection path.
    usage = value.get('usage')
    need(type(usage) is dict, 'Provider token accounting required')
    counts = {}
    for name in ('input_tokens', 'output_tokens', 'total_tokens'):
        need(type(usage.get(name)) is int and 0 <= usage[name] <= 100000000, 'Integral token count required')
        counts[name] = usage[name]
    need(counts['total_tokens'] == counts['input_tokens'] + counts['output_tokens']
         and counts['output_tokens'] <= max_output_tokens, 'Token accounting mismatch')
    return action, {'provider_response_id': value['id'], 'model': value['model'], 'usage': counts}


class SenderAdapter:
    """Bind the unchanged Sender's prompt guard to the complete exact image request."""
    decode = staticmethod(decode)

    def __init__(self, history, model, max_output_tokens, cap, trial_id):
        self.prompt = history[0]['content'][0]['text']
        self.model, self.max_output_tokens, self.trial_id = model, max_output_tokens, identifier(trial_id)
        need(set(re.findall(r'development-00[12]-[0-9a-f]{24}', self.prompt)) == {self.trial_id}, 'Context identity mismatch')
        self.request = request_body(history, model, max_output_tokens, cap)

    def query_identity(self, prompt):
        need(prompt == self.prompt, 'Complete exact initial prompt required')
        return self.trial_id

    def request_body(self, prompt, model, max_output_tokens):
        need(prompt == self.prompt and model == self.model and max_output_tokens == self.max_output_tokens,
             'Request policy/context mismatch')
        return self.request
