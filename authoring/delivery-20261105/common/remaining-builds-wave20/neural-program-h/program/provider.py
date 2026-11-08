"""Concrete host-only chat-completion wire transport, never an investigation callback.

Protocol/model/token-bound compatibility and account authorization are external
operator qualifications. Importing this file performs no credential or network I/O.
"""
import hashlib
import http.client
import os
import ssl
import stat
from urllib.parse import urlsplit

from core import encoded, finite, integer, need, parse, pin


def request_seed(episode, ordinal):
    mode, replicate, role, slot = episode
    bases = {'replicate-01': 60201, 'replicate-02': 60202, 'replicate-03': 60203}
    # Design specifies compact JSON order, not sorted object serialization.
    raw = encoded(['neural060-author-v1', bases[replicate], mode, replicate,
                   role, slot, integer(ordinal, 1)])
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], 'big') & 0x7fffffff


def action(body, source_cap=131072, recipe_cap=65536, claim_cap=32768):
    obj = parse(body)
    need(type(obj) is dict and obj.get('action') in ('python', 'submit', 'stop'), 'typed agent action')
    kind = obj['action']
    if kind == 'python':
        need(set(obj) == {'action', 'code', 'rationale'} and type(obj['code']) is str
             and 0 < len(obj['code'].encode()) <= source_cap and type(obj['rationale']) is str
             and len(obj['rationale'].encode()) <= claim_cap, 'bounded Python action')
    elif kind == 'submit':
        need(set(obj) == {'action', 'source', 'recipe', 'claim'} and type(obj['source']) is str
             and 0 < len(obj['source'].encode()) <= source_cap and type(obj['recipe']) is dict
             and len(encoded(obj['recipe'])) <= recipe_cap and type(obj['claim']) is dict
             and len(encoded(obj['claim'])) <= claim_cap, 'source/recipe/claim submission')
        need(set(obj['claim']) == {'endpoint', 'estimator', 'comparator', 'biological_unit',
                                   'uncertainty', 'leakage_limits', 'null_interpretation'}
             and all(type(x) is str and x for x in obj['claim'].values()), 'pre-outcome scientific claim')
    else:
        need(set(obj) == {'action', 'reason'} and type(obj['reason']) is str
             and 0 < len(obj['reason'].encode()) <= claim_cap, 'explicit bounded failed episode')
    return obj


class Provider:
    def __init__(self, selection, budget, record, limits):
        self.selection, self.budget, self.record, self.limits = selection, budget, record, limits
        url = urlsplit(selection['endpoint'])
        need(url.scheme == 'https' and url.hostname and not url.username and not url.password
             and not url.fragment and not url.query, 'qualified fixed HTTPS endpoint')
        self.url = url
        need(selection['wire_protocol'] == 'chat_completions_json_action_v1', 'qualified exact wire protocol')
        need(type(selection['seed_supported']) is bool and type(selection['model']) is str,
             'explicit model/seed compatibility')
        self.calls = self.tokens = self.prompt_tokens = self.completion_tokens = 0
        self.attempted = []

    def _credential(self):
        # Secret value is neither hashed nor logged. This method is never called
        # by source/invented controls or before the root activation gate.
        path = self.selection['credential_path']
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            st = os.fstat(fd)
            need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size <= 8192
                 and st.st_mode & 0o077 == 0, 'protected bounded provider credential')
            secret = os.read(fd, 8193).decode('utf-8').strip()
            need(secret and '\n' not in secret and '\r' not in secret, 'one authorization token')
            return secret
        finally:
            os.close(fd)

    def complete(self, messages, episode, cutoff):
        need(type(messages) is list and messages and all(type(row) is dict and set(row) == {'role', 'content'}
             and row['role'] in ('system', 'user', 'assistant') and type(row['content']) is str
             for row in messages), 'explicit isolated text transcript only')
        now = self.budget.tick(cutoff)
        ordinal = self.calls + 1
        need(ordinal <= integer(self.limits['provider_calls'], 1), 'provider request cap')
        remaining = integer(self.limits['tokens'], 1)-self.tokens
        # This serializer-specific upper bound MUST be separately qualified for
        # the selected endpoint/model. It is not a general tokenizer theorem.
        bound = len(encoded(messages))*integer(self.selection['token_bound_per_utf8_byte'], 1)
        bound += integer(self.selection['token_bound_fixed_overhead'])
        need(bound < remaining, 'qualified prompt bound exhausts token allowance')
        out_cap = min(integer(self.limits['per_response_tokens'], 1), remaining-bound)
        payload = {'model': self.selection['model'], 'messages': messages, 'stream': False,
                   'max_tokens': out_cap, 'temperature': self.selection['temperature']}
        seed = request_seed(episode, ordinal)
        if self.selection['seed_supported']:
            payload['seed'] = seed
        raw = encoded(payload)
        need(len(raw) <= integer(self.limits['request_bytes'], 1), 'bounded provider request')
        self.calls += 1
        intent = {'kind': 'provider_attempted', 'episode': list(episode), 'ordinal': ordinal,
                  'request': pin(raw), 'requested_model': self.selection['model'],
                  'request_seed': seed if self.selection['seed_supported'] else None,
                  'seed_supported': self.selection['seed_supported'], 'prompt_upper_bound': bound,
                  'output_token_ceiling': out_cap, 'original_origin': self.budget.origin,
                  'cutoff': cutoff, 'observed_start': now}
        self.attempted.append(intent); self.record(intent)
        self.budget.reserve_write(len(raw))
        conn = None
        try:
            secret = self._credential()
            conn = http.client.HTTPSConnection(self.url.hostname, self.url.port or 443,
                                              timeout=min(60., cutoff-now), context=ssl.create_default_context())
            conn.request('POST', self.url.path or '/', body=raw,
                         headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+secret,
                                  'Connection': 'close'})
            # Never follow a redirect or repeat a request after an error.
            response = conn.getresponse()
            cap = integer(self.limits['response_bytes'], 1)
            self.budget.reserve_read(cap)
            length = response.getheader('Content-Length')
            if length is not None:
                need(length.isdigit() and int(length) <= cap, 'provider response length bound')
            chunks, count = [], 0
            while True:
                self.budget.tick(cutoff)
                chunk = response.read(min(65536, cap+1-count))
                if not chunk:
                    break
                chunks.append(chunk); count += len(chunk)
                need(count <= cap, 'provider response byte ceiling')
            body = b''.join(chunks)
            # A misbehaving service echoing the credential must not cause its
            # private body to be persisted or hashed as benchmark evidence.
            need(secret.encode() not in body, 'credential echo refused without capture')
            need(response.status == 200, 'provider HTTP failure:' + str(response.status))
            value = parse(body)
            usage = value['usage']
            prompt = integer(usage['prompt_tokens'])
            completion = integer(usage['completion_tokens'])
            total = integer(usage['total_tokens'])
            need(total == prompt+completion, 'complete provider usage accounting')
            # Preserve observed expenditure BEFORE testing ceilings.
            self.tokens += total; self.prompt_tokens += prompt; self.completion_tokens += completion
            self.record({'kind': 'provider_usage_observed', 'episode': list(episode), 'ordinal': ordinal,
                         'response': pin(body), 'prompt_tokens': prompt, 'completion_tokens': completion,
                         'cumulative_tokens': self.tokens, 'observed_end': self.budget.tick(cutoff)})
            need(prompt <= bound and completion <= out_cap and self.tokens <= self.limits['tokens'],
                 'observed provider usage violated qualified bound/selected cap')
            need(value['model'] == self.selection['response_model'], 'exact qualified response model revision')
            choices = value['choices']
            need(type(choices) is list and len(choices) == 1 and choices[0]['finish_reason'] == 'stop',
                 'one complete response; truncation/tool protocol changes refused')
            message = choices[0]['message']
            need(message.get('role') == 'assistant' and type(message.get('content')) is str
                 and not message.get('tool_calls'), 'explicit JSON action text only')
            selected_action = action(message['content'].encode('utf-8'))
            self.record({'kind': 'provider_completed', 'episode': list(episode), 'ordinal': ordinal,
                         'response': pin(body), 'action': selected_action,
                         'backend_fingerprint': value.get('system_fingerprint'),
                         'determinism_qualified': self.selection['determinism_qualified']})
            return selected_action, message['content'], body
        except BaseException as error:
            # Missing usage is unknown, not zero. No unbilled-success or retry.
            self.record({'kind': 'provider_failed', 'episode': list(episode), 'ordinal': ordinal,
                         'error_type': type(error).__name__, 'usage_may_be_incomplete': True,
                         'attempted_requests': self.calls, 'observed_tokens': self.tokens})
            raise
        finally:
            if conn is not None:
                conn.close()
