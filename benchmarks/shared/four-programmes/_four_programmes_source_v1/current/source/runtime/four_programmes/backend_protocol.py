"""Fixed local HTTP wire and response semantics; no IO or model execution.

These functions are deterministic protocol producers/consumers. Their values
alone confer no live socket/backend/agent authority; the lifecycle owner must
authenticate actual captures, source/native provenance and the pending step.
"""
import json
import re
from .common import need, same, integer
from .backend_json import parse, scalar_text
from .precommit_records import validate_type, RECORDS

COMMIT='4ed88da2ea2a51edc158efe0ee2a1e452d75644d'
RESPONSE_FIELDS=('index','content','id_slot','stop','model','tokens_predicted','tokens_evaluated',
                 'has_new_line','truncated','stop_type','stopping_word','tokens_cached',
                 'generation_settings/n_predict')
ENDPOINTS={'health':('GET','/health'),'slots':('GET','/slots'),'completion':('POST','/completion')}
_HEADER_NAME=re.compile(rb"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")

def _decimal_milli(value):
    integer(value)
    return str(value//1000)+'.'+str(value%1000).zfill(3)

def completion_body(request,profile):
    validate_type('CompletionRequest',request);validate_type('LocalBackendProfile',profile)
    sample=profile['sampling']
    need(same(request['sampling'],sample) and request['maximum_generated_tokens']==sample['maximum_generated_tokens'],
         'same immutable sampler and exact generated-token request')
    scalar_text(request['prompt'])
    prompt=request['prompt'].encode('utf8')
    need(len(prompt)==request['prompt_bytes'],'actual exact UTF8 prompt bytes')
    # Explicitly encode fixed-point settings as exact three-decimal JSON tokens,
    # not binary floating point or a participant serializer callback.
    values={'prompt':json.dumps(request['prompt'],ensure_ascii=False,allow_nan=False),
        'stream':'false','cache_prompt':'false','n_predict':str(sample['maximum_generated_tokens']),
        'seed':str(sample['seed']),'top_k':str(sample['top_k']),
        'temperature':_decimal_milli(sample['temperature_milli']),
        'top_p':_decimal_milli(sample['top_p_milli']),'min_p':_decimal_milli(sample['min_p_milli']),
        'repeat_penalty':_decimal_milli(sample['repeat_penalty_milli']),
        'response_fields':json.dumps(list(RESPONSE_FIELDS),separators=(',',':'))}
    raw=('{'+','.join(json.dumps(k)+':'+values[k] for k in sorted(values))+'}').encode('utf8')
    need(len(raw)<=profile['limits']['maximum_request_bytes'],'whole fixed request body within original cap')
    return raw

def request_wire(endpoint,profile,request=None):
    need(endpoint in ENDPOINTS,'one fixed source endpoint')
    method,path=ENDPOINTS[endpoint]
    if endpoint=='completion':body=completion_body(request,profile)
    else:
        need(request is None,'no generation payload in initialization probes')
        body=b''
    headers=[method+' '+path+' HTTP/1.1','Host: localhost','Connection: close',
             'Content-Length: '+str(len(body))]
    if endpoint=='completion':headers.append('Content-Type: application/json')
    wire=('\r\n'.join(headers)+'\r\n\r\n').encode('ascii')+body
    need(len(wire)<=profile['limits']['maximum_request_bytes'],'complete headers plus body within original request cap')
    return wire,len(body)

def response_header(header,profile):
    """Parse only the complete already observed header, never probe an EOF."""
    need(type(header) is bytes and len(header)<=min(profile['limits']['maximum_header_bytes'],65536),
         'finite original header bytes')
    need(header.endswith(b'\r\n\r\n') and b'\r\n\r\n' not in header[:-4],
         'one exact complete header block')
    lines=header[:-4].split(b'\r\n')
    need(all(len(line)<=8192 and b'\r' not in line and b'\n' not in line for line in lines),
         'bounded CRLF lines without bare CR/LF')
    need(len(lines)>=1 and len(lines)-1<=64,'bounded header field count')
    match=re.fullmatch(rb'HTTP/1\.1 ([0-9]{3})(?: [\x20-\x7e]*)?',lines[0])
    need(match is not None,'exact HTTP/1.1 status framing')
    status=int(match.group(1));validate_type('HttpStatus',status)
    fields={}
    for line in lines[1:]:
        need(b':' in line and line[:1] not in (b' ',b'\t'),'no obs-fold')
        name,value=line.split(b':',1)
        need(_HEADER_NAME.fullmatch(name) is not None,'ASCII HTTP field name')
        need(all(32<=n<=126 for n in value),'no header control/nonASCII bytes')
        name=name.lower();value=value.strip(b' ')
        need(name not in fields,'no duplicate case-folded header names')
        need(name not in (b'transfer-encoding',b'content-encoding',b'upgrade',b'location',b'trailer',
                          b'content-range',b'proxy-connection'),'unsupported framing-changing header')
        fields[name]=value
    length=fields.get(b'content-length')
    need(type(length) is bytes and len(length)<=20 and re.fullmatch(rb'[0-9]+',length) is not None,
         'one bounded decimal Content-Length')
    length=int(length)
    need(length<=min(profile['limits']['maximum_response_bytes'],1048576),'finite declared complete body')
    content=fields.get(b'content-type',b'').lower()
    need(re.fullmatch(rb'application/json(?: *; *charset=utf-8)?',content) is not None,
         'exact JSON content type and optional UTF8 charset')
    need(b'connection' not in fields or fields[b'connection'].lower()==b'close',
         'no persistent or upgraded connection')
    return status,length

def parse_response(raw,request,profile,artifacts,*,semantic_request=None,generation_deadline=None):
    """Complete wire/schema/endpoint joins; returns a typed body, not authority."""
    validate_type('RawHttpResponse',raw);validate_type('BackendHttpRequest',request)
    validate_type('LocalBackendProfile',profile);validate_type('LocalArtifactSelection',artifacts)
    need(raw['state']=='complete' and raw['first_error'] is None and not raw['secondary_errors'] and
         raw['unknown_physical_read'] is False and raw['started_ns'] is not None and raw['finished_ns'] is not None,
         'only exact complete known original response')
    need(raw['finished_ns']>=raw['started_ns'],'original nondecreasing response interval')
    for key in ('attempt','condition','endpoint','ordinal','pair_nonce'):
        need(same(raw[key],request[key]),'same source request and response '+key)
    header=bytes.fromhex(raw['header_prefix_hex']);body=bytes.fromhex(raw['body_prefix_hex'])
    need(len(header)==raw['header_bytes'] and len(body)==raw['body_bytes'] and
         raw['known_wire_bytes']==len(header)+len(body),'actual observed exact returned byte counts')
    status,length=response_header(header,profile)
    need(raw['status_code']==status and raw['declared_content_length']==length==len(body),
         'framing derived from observed raw bytes, not caller labels')
    value=parse(body,min(profile['limits']['maximum_response_bytes'],1048576),
        maximum_depth=8,maximum_members=128,maximum_string_bytes=1048576)
    endpoint=raw['endpoint']
    if endpoint=='health':
        if status==503:
            need(same(value,{'error':{'code':503,'message':'Loading model','type':'unavailable_error'}}),
                 'sole exact loading variant')
            return 'loading',value
        need(status==200 and same(value,{'status':'ok'}),'exact health success')
        return 'health',value
    need(status==200,'only successful status for slots or completion')
    if endpoint=='slots':
        need(type(value) is list and len(value)==1 and type(value[0]) is dict and
             set(value[0])=={'id','n_ctx','speculative','is_processing'},'one exact fresh slot with absent task fields')
        slot={'schema':RECORDS['SlotBody']['schema_literal'],**value[0]}
        validate_type('SlotBody',slot)
        need(slot['n_ctx']==profile['limits']['context_tokens'],'original selected slot context')
        return 'slots',slot
    need(endpoint=='completion' and semantic_request is not None,'original pending semantic completion')
    validate_type('CompletionRequest',semantic_request)
    need(type(value) is dict and set(value)==set(RESPONSE_FIELDS),'exact thirteen wire keys, no nested replacement')
    typed={'schema':RECORDS['CompletionBody']['schema_literal'],**value}
    validate_type('CompletionBody',typed)
    need(typed['model']==artifacts['model_alias'] and
         typed['generation_settings/n_predict']==semantic_request['maximum_generated_tokens'],
         'same model alias and original n_predict')
    need(semantic_request['request_ordinal']==raw['ordinal'] and
         same(semantic_request['sampling'],profile['sampling']),'same pending ordinal and immutable sampling')
    integer(generation_deadline)
    need(raw['finished_ns']<=generation_deadline,'unchanged original generation cutoff')
    need(not typed['truncated'] and typed['stop_type']!='none','complete nontruncated context')
    limit=profile['limits']['context_tokens']+semantic_request['maximum_generated_tokens'];integer(limit)
    need(all(typed[key]<=limit for key in ('tokens_cached','tokens_evaluated','tokens_predicted')),
         'all actual diagnostic counters within selected finite envelope')
    need(typed['stop_type']!='limit' or typed['content']!='','empty token-limited generation is terminal failure')
    return 'completion',typed
