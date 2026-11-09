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

from core import encoded, finite, integer, need, parse, pin, parent_chain, close_preserving, cleanup_preserving


def request_seed(episode, ordinal):
    # Accepted author-01 request seed is paired across conditions. Endpoint
    # stochasticity and unreplicated policy variation remain unqualified.
    raw = encoded(['neural042-author-seed-v1', 'author-01'])
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], 'big')


def action(body, mode='author', source_cap=131072):
    obj = parse(body)
    need(type(obj) is dict, 'one typed response')
    if mode == 'fixed_numeric':
        need(set(obj) == {'values'} and type(obj['values']) is list
             and 0 < len(obj['values']) <= 4096, 'bounded frozen numerical response only')
        obj['values'] = [finite(x) for x in obj['values']]
        return obj
    need(mode == 'author' and obj.get('action') in ('python', 'submit', 'stop'), 'author action')
    if obj['action'] == 'python':
        need(set(obj) == {'action','code','rationale'} and type(obj['code']) is str
             and 0 < len(obj['code'].encode()) <= source_cap and type(obj['rationale']) is str
             and len(obj['rationale'].encode()) <= 32768, 'bounded isolated analysis source')
    elif obj['action'] == 'submit':
        need(set(obj) == {'action','source','recipe','claim'} and type(obj['source']) is str
             and 0 < len(obj['source'].encode()) <= source_cap and type(obj['recipe']) is dict
             and len(encoded(obj['recipe'])) <= 65536 and type(obj['claim']) is dict
             and len(encoded(obj['claim'])) <= 32768, 'bounded source/recipe/pre-outcome claim')
    else:
        need(set(obj) == {'action','reason'} and type(obj['reason']) is str, 'explicit failed episode')
    return obj


class GlobalQuota:
    """Conservative whole-study request/token/money reservations across contexts."""
    def __init__(self,calls,tokens,money):
        self.limits={'calls':integer(calls,1),'tokens':integer(tokens,1),'money':finite(money)}
        need(self.limits['money']>0,'positive full provider allowance')
        self.calls=0;self.tokens=0;self.money=0.;self.identities=set();self.observed_tokens=0
    def reserve(self,episode,ordinal,tokens,money):
        identity=pin(encoded([episode,ordinal]))['sha256']
        need(identity not in self.identities,'no duplicate provider request identity')
        integer(tokens,1);money=finite(money)
        need(self.calls+1<=self.limits['calls'] and self.tokens+tokens<=self.limits['tokens']
             and money>=0 and self.money+money<=self.limits['money'],'whole-study provider reservation before billing')
        self.identities.add(identity);self.calls+=1;self.tokens+=tokens;self.money+=money
    def observe(self,tokens):self.observed_tokens+=integer(tokens)
    def record(self):return {'limits':dict(self.limits),'calls_reserved':self.calls,'tokens_reserved':self.tokens,
                             'money_reserved':self.money,'tokens_observed':self.observed_tokens,
                             'unknown_failed_request_usage_not_zero':True}


class Provider:
    def __init__(self, selection, budget, record, limits, global_quota):
        self.selection, self.budget, self.record, self.limits = selection, budget, record, limits
        need(type(global_quota)is GlobalQuota, 'source-owned whole-study provider quota');self.global_quota=global_quota
        url = urlsplit(selection['endpoint'])
        need(url.scheme == 'https' and url.hostname and not url.username and not url.password
             and not url.fragment and not url.query, 'qualified fixed HTTPS endpoint')
        self.url = url
        need(selection['wire_protocol'] == 'neural042_chat_json_v1', 'qualified exact wire protocol')
        need(type(selection['seed_supported']) is bool and type(selection['model']) is str,
             'explicit model/seed compatibility')
        self.calls = self.tokens = self.prompt_tokens = self.completion_tokens = 0
        self.money_reserved=0.
        self.attempted = []

    def _credential(self):
        # Secret value is neither hashed nor logged. This method is never called
        # by source/invented controls or before the root activation gate.
        path = parent_chain(self.selection['credential_path'])
        self.budget.reserve_read(8193)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            st = os.fstat(fd)
            need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size <= 8192
                 and st.st_mode & 0o077 == 0, 'protected bounded provider credential')
            secret = os.read(fd, 8193).decode('utf-8').strip()
            need(secret and '\n' not in secret and '\r' not in secret, 'one authorization token')
            self.budget.tick()
            return secret
        finally:
            close_preserving(fd)

    def complete(self, messages, episode, cutoff, mode='author'):
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
        cap = integer(self.limits['response_bytes'], 1)
        money=(bound+out_cap)*finite(self.selection['qualified_max_price_per_token'])+finite(self.selection['qualified_max_fee_per_request'])
        need(money>=0 and self.money_reserved+money<=finite(self.limits['money']),'prospective episode monetary allowance')
        self.global_quota.reserve(episode,ordinal,bound+out_cap,money)
        self.money_reserved+=money
        self.budget.reserve_read(cap + 1)
        self.budget.reserve_write(len(raw))
        self.calls += 1
        intent = {'kind': 'provider_attempted', 'episode': list(episode), 'ordinal': ordinal,
                  'request': pin(raw), 'requested_model': self.selection['model'],
                  'request_seed': seed if self.selection['seed_supported'] else None,
                  'seed_supported': self.selection['seed_supported'], 'prompt_upper_bound': bound,
                  'output_token_ceiling': out_cap,'money_reserved':money, 'original_origin': self.budget.origin,
                  'cutoff': cutoff, 'observed_start': now}
        self.attempted.append(intent); self.record(intent)
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
            self.budget.tick(cutoff)
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
            self.global_quota.observe(total)
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
            selected_action = action(message['content'].encode('utf-8'), mode)
            self.record({'kind': 'provider_completed', 'episode': list(episode), 'ordinal': ordinal,
                         'response': pin(body), 'action': selected_action,
                         'backend_fingerprint': value.get('system_fingerprint'),
                         'determinism_qualified': self.selection['determinism_qualified']})
            return selected_action, message['content'], body
        except BaseException as error:
            # Missing usage is unknown, not zero. No unbilled-success or retry.
            failure={'kind': 'provider_failed', 'episode': list(episode), 'ordinal': ordinal,
                     'error_type': type(error).__name__, 'usage_may_be_incomplete': True,
                     'attempted_requests': self.calls, 'observed_tokens': self.tokens, 'whole_study_provider': self.global_quota.record()}
            try:self.record(failure)
            except BaseException as publication:
                combined=BaseExceptionGroup('provider failure and accounting publication failed',[error,publication])
                combined.failure_record=failure
                raise combined from None
            raise
        finally:
            if conn is not None:
                cleanup_preserving(conn.close)
