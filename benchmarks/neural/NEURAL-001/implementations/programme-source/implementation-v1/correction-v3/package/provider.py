"""Concrete bounded chat-completions action transport. Import performs no I/O.

Derived in approach from reviewed NEURAL060 provider source, not its cohort/seed
policy. Actual endpoint/model/token accounting and account authority require
independent qualification. No request or credential read is performed by controls.
"""
import hashlib
import http.client
import json
import ssl
from urllib.parse import urlsplit
from .protocol import canonical, pin_bytes, require, exact_int


def paired_seed(replicate, public_person_alias, public_query_id, ordinal):
    # Arm and mode deliberately excluded so matched cases share a requested seed.
    # Endpoint stochastic determinism is separately measured, never presumed.
    raw = canonical(['NEURAL-001', replicate, public_person_alias, public_query_id, ordinal])
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], 'big') & 0x7fffffff


def parse_action(text, *, source_cap=65536):
    require(type(text) is str and len(text.encode('utf-8')) <= 2*source_cap, 'bounded complete action text')
    def unique(items):
        result = {}
        for k,v in items:
            require(k not in result, 'duplicate action key')
            result[k] = v
        return result
    obj = json.loads(text, object_pairs_hook=unique,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite action')))
    require(type(obj) is dict and obj.get('action') in ('python', 'submit', 'stop'), 'typed action required')
    if obj['action'] == 'python':
        require(set(obj) == {'action', 'code', 'rationale'}, 'exact Python action fields')
        require(type(obj['code']) is str and 0 < len(obj['code'].encode()) <= source_cap, 'bounded Python source')
        require(type(obj['rationale']) is str and len(obj['rationale'].encode()) <= 8192, 'bounded rationale')
    elif obj['action'] == 'submit':
        require(set(obj) == {'action', 'source', 'method'}, 'exact source/method submission')
        require(type(obj['source']) is str and 0 < len(obj['source'].encode()) <= source_cap, 'bounded authored program')
        require(type(obj['method']) is dict and len(canonical(obj['method'])) <= 32768, 'bounded method trace')
    else:
        require(set(obj) == {'action', 'reason'} and type(obj['reason']) is str
                and 0 < len(obj['reason'].encode()) <= 8192, 'bounded explicit failed stop')
    return obj


class Provider:
    def __init__(self, selection, budget, journal, credential_capability):
        self.selection, self.budget, self.journal = selection, budget, journal
        self.credential_capability = credential_capability
        self.calls = 0
        u = urlsplit(selection['endpoint'])
        require(u.scheme == 'https' and u.hostname and not u.username and not u.password
                and not u.query and not u.fragment, 'fixed qualified HTTPS endpoint')
        require(selection['wire_protocol'] == 'chat_completions_json_action_v1', 'qualified exact wire protocol')
        self.url = u

    def complete(self, messages, *, replicate, person_alias, query_id, cutoff):
        require(type(messages) is list and messages and all(type(x) is dict
                and set(x) == {'role','content'} and x['role'] in ('system','user','assistant')
                and type(x['content']) is str for x in messages), 'fresh plain text transcript required')
        now = self.budget.tick(cutoff)
        limits = self.selection['limits']
        require(self.calls < exact_int(limits['requests'], 'provider requests', 1), 'provider request limit')
        prompt_bound = (len(canonical(messages))*exact_int(self.selection['token_bound_per_utf8_byte'], 'qualified tokenizer bound', 1)
                        + exact_int(self.selection['token_bound_fixed_overhead'], 'token overhead'))
        output = exact_int(limits['per_response_output_tokens'], 'response output limit', 1)
        token = self.budget.reserve_provider(prompt_bound, output)
        self.calls += 1
        connection = None
        usage_closed = False
        try:
            seed = paired_seed(replicate, person_alias, query_id, self.calls)
            payload = {'model': self.selection['model'], 'messages': messages, 'stream': False,
                       'temperature': self.selection['temperature'], 'max_tokens': output}
            if self.selection['seed_supported']:
                payload['seed'] = seed
            raw = canonical(payload)
            require(len(raw) <= limits['request_bytes'], 'request byte cap')
            self.journal({'kind':'provider_attempt', 'ordinal':self.calls, 'request_pin':pin_bytes(raw),
                          'requested_seed':seed if self.selection['seed_supported'] else None,
                          'original_origin':self.budget.origin, 'cutoff':cutoff})
            # Credential capability is host-only; never hashed, logged or mounted.
            secret = self.credential_capability()
            require(type(secret) is str and secret and '\n' not in secret and '\r' not in secret,
                    'bounded protected authorization token required')
            require(len(secret.encode()) <= 8192, 'authorization token cap')
            self.budget.charge_io(write_bytes=len(raw))
            connection = http.client.HTTPSConnection(self.url.hostname, self.url.port or 443,
                    timeout=min(60., cutoff-now), context=ssl.create_default_context())
            connection.request('POST', self.url.path or '/', body=raw,
                               headers={'Authorization':'Bearer '+secret, 'Content-Type':'application/json',
                                        'Connection':'close'})
            response = connection.getresponse()
            cap = exact_int(limits['response_bytes'], 'provider response bytes', 1)
            length = response.getheader('Content-Length')
            require(length is None or length.isdigit() and int(length) <= cap, 'response content length cap')
            chunks=[]; size=0
            while True:
                self.budget.tick(cutoff)
                chunk=response.read(min(65536,cap+1-size))
                if not chunk:break
                size+=len(chunk);self.budget.charge_io(read_bytes=len(chunk))
                require(size<=cap,'response byte ceiling');chunks.append(chunk)
            body=b''.join(chunks)
            require(secret.encode() not in body, 'credential echo refused without hashing or capture')
            require(response.status==200,'provider HTTP failure; no redirect or retry')
            value=json.loads(body)
            usage=value['usage']
            prompt=exact_int(usage['prompt_tokens'],'observed prompt tokens')
            completion=exact_int(usage['completion_tokens'],'observed completion tokens')
            require(type(usage.get('completion_tokens_details')) is dict
                    and 'reasoning_tokens' in usage['completion_tokens_details'],
                    'reasoning usage must be explicitly reported; missing is not zero')
            reasoning=exact_int(usage['completion_tokens_details']['reasoning_tokens'],'reasoning tokens')
            require(reasoning<=completion,'reasoning tokens included in completion total')
            require(exact_int(usage['total_tokens'],'observed total')==prompt+completion,'complete usage identity')
            # Record expenditure before admission; errors do not erase billing.
            self.budget.finish_provider(token,prompt,completion,reasoning)
            usage_closed=True
            self.journal({'kind':'provider_usage','ordinal':self.calls,'response_pin':pin_bytes(body),
                          'input_tokens':prompt,'output_tokens':completion,'reasoning_tokens':reasoning})
            require(prompt<=prompt_bound and completion<=output,'qualified token bound violated')
            require(value['model']==self.selection['response_model'],'exact response model revision')
            choices=value['choices']
            require(type(choices)is list and len(choices)==1 and choices[0]['finish_reason']=='stop','one untruncated response')
            msg=choices[0]['message']
            require(msg.get('role')=='assistant' and type(msg.get('content'))is str and not msg.get('tool_calls'),
                    'plain JSON action wire protocol required')
            self.budget.tick(cutoff)
            return parse_action(msg['content']),msg['content']
        except BaseException:
            if not usage_closed:self.budget.abandon_provider(token,'observed usage incomplete')
            self.journal({'kind':'provider_failure','ordinal':self.calls,'usage_incomplete':not usage_closed,
                          'retry_permitted':False})
            raise
        finally:
            if connection is not None:connection.close()
