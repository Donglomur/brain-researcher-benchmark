"""One N031 complete-observation Responses request; injected transport only."""
import hashlib
import json
import math
import re
import struct

OBS_CAP = 524288
ANSWER_CAP = 131072
RAW_CAP = 524288
PREFIX = struct.Struct('!I')


def need(ok, code):
    if not ok:
        raise ValueError(code)


def decode(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'duplicate_json_key')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def encode(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def observation(prompt):
    need(type(prompt) is str and 0 < len(prompt.encode()) <= OBS_CAP, 'complete_observation_capacity')
    value = decode(prompt)
    need(type(value) is dict and set(value) == {'schema', 'candidate_id', 'access_condition',
         'request_id', 'instructions', 'context', 'arrays'} and
         value['schema'] == 'neural031_direct_numeric_context_v1' and value['candidate_id'] == 'NEURAL-031' and
         value['access_condition'] == 'direct_numeric_no_tools' and type(value['request_id']) is str and
         re.fullmatch('[0-9a-f]{64}', value['request_id']), 'n031_observation_identity')
    rows = value['arrays']['query_rowid']
    need(type(rows) is list and 0 < len(rows) < 774 and all(type(x) is int for x in rows) and
         len(set(rows)) == len(rows), 'complete_query_rows')
    return value


def query_identity(prompt):
    return observation(prompt)['request_id']


def request_body(prompt, model, max_output_tokens):
    identity = query_identity(prompt)
    need(type(model) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', model) and
         type(max_output_tokens) is int and 1 <= max_output_tokens <= 32768, 'selected_model_output')
    row = {'type': 'object', 'properties': {'row_id': {'type': 'integer'},
           'prediction': {'type': 'number'}}, 'required': ['row_id', 'prediction'], 'additionalProperties': False}
    schema = {'type': 'object', 'properties': {
        'schema': {'type': 'string', 'enum': ['neural031_direct_response_v1']},
        'request_id': {'type': 'string', 'enum': [identity]}, 'rows': {'type': 'array', 'items': row}},
        'required': ['schema', 'request_id', 'rows'], 'additionalProperties': False}
    return encode({'model': model, 'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': prompt}]}],
                   'tools': [], 'tool_choice': 'none', 'parallel_tool_calls': False, 'store': False,
                   'stream': False, 'background': False, 'truncation': 'disabled',
                   'max_output_tokens': max_output_tokens, 'text': {'format': {'type': 'json_schema',
                   'name': 'neural031_ratios', 'strict': True, 'schema': schema}}})


def answer(raw, prompt):
    need(type(raw) is bytes and 0 < len(raw) <= ANSWER_CAP, 'bounded_first_answer')
    value, obs = decode(raw), observation(prompt)
    need(type(value) is dict and set(value) == {'schema', 'request_id', 'rows'} and
         value['schema'] == 'neural031_direct_response_v1' and value['request_id'] == obs['request_id'] and
         type(value['rows']) is list and len(value['rows']) == len(obs['arrays']['query_rowid']),
         'complete_request_bound_rows')
    for row, expected in zip(value['rows'], obs['arrays']['query_rowid']):
        need(type(row) is dict and set(row) == {'row_id', 'prediction'} and type(row['row_id']) is int and
             row['row_id'] == expected and type(row['prediction']) in (int, float) and
             math.isfinite(row['prediction']) and row['prediction'] >= 0, 'ordered_finite_ratios')
    return value


def completed(raw, prompt, model, max_output_tokens):
    need(type(raw) is bytes and 0 < len(raw) <= RAW_CAP, 'bounded_provider_body')
    value = decode(raw)
    need(type(value) is dict and value.get('object') == 'response' and value.get('status') == 'completed' and
         value.get('error') is None and value.get('incomplete_details') is None, 'incomplete_provider_response')
    need(value.get('tools') == [] and value.get('tool_choice') == 'none' and
         value.get('parallel_tool_calls') is False and value.get('store') is False and
         value.get('truncation') == 'disabled' and value.get('previous_response_id') is None and
         value.get('conversation') is None and value.get('background', False) is False, 'provider_policy_history')
    need(value.get('model') == model and type(value.get('max_output_tokens')) is int and
         value['max_output_tokens'] == max_output_tokens, 'provider_model_output')
    need(type(value.get('id')) is str and re.fullmatch('resp_[A-Za-z0-9_-]{1,160}', value['id']), 'provider_response_id')
    output = value.get('output')
    need(type(output) is list and 1 <= len(output) <= 32 and all(type(x) is dict and
         x.get('type') in ('reasoning', 'message') for x in output), 'provider_output_inventory')
    messages = [x for x in output if x['type'] == 'message']
    need(len(messages) == 1, 'one_first_final_message')
    message = messages[0]
    need(message.get('role') == 'assistant' and message.get('status') == 'completed' and
         type(message.get('content')) is list and len(message['content']) == 1, 'complete_first_message')
    content = message['content'][0]
    need(type(content) is dict and content.get('type') == 'output_text' and
         type(content.get('text')) is str, 'refusal_or_nontext')
    text = content['text'].encode()
    answer(text, prompt)
    usage = value.get('usage')
    need(type(usage) is dict and all(type(usage.get(k)) is int and 0 <= usage[k] <= 100000000
         for k in ('input_tokens', 'output_tokens', 'total_tokens')), 'provider_token_accounting')
    need(usage['total_tokens'] == usage['input_tokens'] + usage['output_tokens'] and
         usage['output_tokens'] <= max_output_tokens, 'provider_token_limit')
    return text, {'provider_response_id': value['id'], 'usage': {k: usage[k]
                  for k in ('input_tokens', 'output_tokens', 'total_tokens')}}


def exchange(prompt, *, model, max_output_tokens, send_json, record):
    request = request_body(prompt, model, max_output_tokens)
    receipt = {'schema': 'neural031_provider_exchange_v1', 'request': pin(request), 'response': None,
               'answer': None, 'sender_calls_attempted': 0, 'retry_count': 0, 'status': 'not_sent'}
    try:
        receipt['sender_calls_attempted'] = 1
        raw = send_json(request)
        need(type(raw) is bytes and 0 < len(raw) <= RAW_CAP, 'bounded_provider_body')
        receipt['response'] = pin(raw)
        text, details = completed(raw, prompt, model, max_output_tokens)
        receipt.update(details, answer=pin(text), status='complete_unscored_answer')
        return text
    except Exception:
        receipt['status'] = 'failed_no_answer'
        raise ValueError('provider_exchange_failed_no_retry') from None
    finally:
        record(receipt)


def serve(inp, out, *, model, max_output_tokens, send_json, record):
    def take(size):
        body = bytearray()
        while len(body) < size:
            part = inp.read(size - len(body))
            need(type(part) is bytes and 0 < len(part) <= size - len(body), 'incomplete_input_frame')
            body.extend(part)
        return bytes(body)
    size = PREFIX.unpack(take(4))[0]
    need(0 < size <= OBS_CAP, 'complete_observation_capacity')
    prompt = take(size).decode()
    need(inp.read(1) == b'', 'one_independent_input_frame')
    text = exchange(prompt, model=model, max_output_tokens=max_output_tokens, send_json=send_json, record=record)
    frame = PREFIX.pack(len(text)) + text
    offset = 0
    while offset < len(frame):
        count = out.write(frame[offset:])
        need(type(count) is int and count > 0, 'complete_output_write')
        offset += count
    out.flush()
