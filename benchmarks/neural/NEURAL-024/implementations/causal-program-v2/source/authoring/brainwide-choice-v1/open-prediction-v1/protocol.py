"""ERP strict response admission and commit gate adapted to93 fixed choice cases."""
import hashlib
import json
import math
import re


def need(ok, message):
    if not ok: raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'Duplicate response key'); result[key] = value
    return result


def real(token):
    value = float(token); need(math.isfinite(value), 'Nonfinite response number')
    if value == 0:
        need(not any(c in '123456789' for c in token.lower().split('e')[0]), 'Nonzero underflow')
    return value


def decode(body):
    need(type(body) is bytes and 0 < len(body) <= 4096, 'Bounded response')
    return json.loads(body, object_pairs_hook=unique, parse_float=real,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite constant')))


def wire(value):
    return (json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode()


def answer(body, request):
    value = decode(body)
    need(type(value) is dict and set(value) == {'nonce', 'case_id', 'probability_left'}, 'Exact current response keys')
    need(all(type(value[k]) is str and value[k] == request[k] for k in ('nonce', 'case_id')), 'Exact current nonce/case')
    p = value['probability_left']
    need(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1, 'Finite P(left) in[0,1], not boolean')
    return {'case_id': value['case_id'], 'probability_left': float(p)}


def wrapped(frame, case_id, nonce):
    """Forward trusted frame bytes opaquely; never decode its neural vector."""
    need(type(frame) is bytes and 0 < len(frame) <= 30000 and frame.endswith(b'\n')
         and frame[:1] == b'{' and frame[-2:-1] == b'}', 'Bounded canonical object fragment')
    prefix = wire({'protocol': 'NEURAL059-sequential-v1', 'case_id': case_id, 'nonce': nonce})[:-2]
    body = prefix + b',"observation":' + frame[:-1] + b'}\n'
    need(len(body) <= 32768, 'Inherited bounded request frame')
    return body


class Gate:
    def __init__(self, entries):
        need(type(entries) is list and len(entries) == 93, 'All93 selected query cases')
        ids = [e['case_id'] for e in entries]; original = [e['original_trial_index'] for e in entries]
        need(len(set(ids)) == 93 and all(type(k) is str and re.fullmatch('NEURAL059-[a-f0-9]{24}', k) for k in ids),
             'Exact unique opaque case IDs')
        need(all(type(i) is int and 0 <= i < 424 for i in original)
             and all(a < b for a, b in zip(original, original[1:])), 'Original chronological case order')
        self.entries = entries; self.position = 0; self.pending = None; self.committed = {}; self.previous = None

    def reveal(self, entry, nonce):
        need(self.pending is None and self.position < 93 and entry == self.entries[self.position],
             'One exact current case; durable commit before next reveal')
        need(type(nonce) is str and re.fullmatch('[a-f0-9]{32}', nonce), 'Fresh unpredictable nonce shape')
        history = entry['history_authorization']; original = entry['original_trial_index']
        need(history['prior_original_trial_index'] == (original - 1 if original else None),
             'Immediate original predecessor, never previous retained case')
        need(type(history['available']) is bool and type(history['requires_prior_query_commit']) is bool,
             'Exact history availability flags')
        if history['requires_prior_query_commit']:
            prior = history['prior_query_case_id']
            need(history['available'] is True and prior in self.committed
                 and self.committed[prior]['original_trial_index'] == original - 1,
                 'Previously committed immediate query required before its outcome can appear in history')
        else:
            need(history['prior_query_case_id'] is None, 'No fabricated predecessor query authorization')
        self.pending = {'case_id': entry['case_id'], 'nonce': nonce, 'original_trial_index': original}
        return dict(self.pending)

    def commit(self, response, record_bytes, acknowledged_pin, fsync_completed):
        need(self.pending is not None and fsync_completed is True and type(record_bytes) is bytes,
             'Exact durable acknowledgement before state advance')
        expected = {'bytes': len(record_bytes), 'sha256': hashlib.sha256(record_bytes).hexdigest()}
        need(acknowledged_pin == expected and response['case_id'] == self.pending['case_id'], 'Exact written commit bytes and identity')
        p = response['probability_left']
        need(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1, 'Admitted current probability')
        self.committed[response['case_id']] = {'pin': expected, 'original_trial_index': self.pending['original_trial_index']}
        self.previous = expected; self.position += 1; self.pending = None
        return expected
