"""Vendor-neutral, strict JSONL adapter protocol. Pure codec/accounting functions."""
from dataclasses import dataclass,asdict
import json
import math
import posixpath
from ..core.custody import canonical,digest,require_digest
from ..core.inference import (InferencePolicy, require_applied_inference,
                              validate_generation_record)

SCHEMA='n073_model_stdio_v2'


class TransportError(RuntimeError):
    pass


def _positive(value):
    return type(value) is int and value>0


def _absolute(path):
    if not isinstance(path,str) or not path.startswith('/') or path=='/' or posixpath.normpath(path)!=path or '\x00' in path:
        raise TransportError('canonical explicit absolute path required')


@dataclass(frozen=True)
class SourcePin:
    path:str
    bytes:int
    sha256:str

    def validate(self):
        _absolute(self.path);require_digest(self.sha256)
        if type(self.bytes) is not int or self.bytes<0:raise TransportError('exact source byte length required')


@dataclass(frozen=True)
class AdapterAdmission:
    context_id:str
    inference_policy:InferencePolicy
    repetition:int
    argv:tuple
    source_closure:tuple
    source_closure_digest:str
    model_revision:str
    fixed_model_evidence_digest:str
    stateless_evidence_digest:str
    tokenizer_evidence_digest:str
    usage_evidence_digest:str
    environment_evidence_digest:str
    protocol_evidence_digest:str
    capacity_evidence_digest:str
    capacity_basis:str
    max_frame_bytes:int
    max_capture_bytes:int
    capture_directory:str

    def validate(self):
        if type(self.inference_policy) is not InferencePolicy:
            raise TransportError('typed canonical inference policy required')
        self.inference_policy.binding_for(self.repetition)
        if not isinstance(self.context_id,str) or not self.context_id or not isinstance(self.model_revision,str) or not self.model_revision:
            raise TransportError('fixed context/model identity required')
        if (not isinstance(self.argv,tuple) or not self.argv or
            any(not isinstance(a,str) or '\x00' in a for a in self.argv)):
            raise TransportError('explicit immutable argv required')
        _absolute(self.argv[0]);_absolute(self.capture_directory)
        if not isinstance(self.source_closure,tuple) or not self.source_closure:raise TransportError('pinned source/runtime closure required')
        for p in self.source_closure:
            if not isinstance(p,SourcePin):raise TransportError('typed closure pin required')
            p.validate()
        paths=[p.path for p in self.source_closure]
        if paths!=sorted(set(paths)) or self.argv[0] not in paths:raise TransportError('sorted exact executable/source closure required')
        if digest([asdict(p) for p in self.source_closure])!=self.source_closure_digest:raise TransportError('closure digest mismatch')
        for name in ('fixed_model','stateless','tokenizer','usage','environment','protocol','capacity'):
            require_digest(getattr(self,name+'_evidence_digest'))
        if self.capacity_basis not in ('qualified_finite_transport_capacity','proven_tokenizer_wire_bound'):
            raise TransportError('qualified transport capacity proof required')
        if not _positive(self.max_frame_bytes) or not _positive(self.max_capture_bytes) or self.max_capture_bytes<self.max_frame_bytes:
            raise TransportError('finite capacity may not be inferred from token count alone')

    @property
    def binding_digest(self):return digest(asdict(self))

    @property
    def inference_binding(self):
        return self.inference_policy.binding_for(self.repetition)

    def handshake(self):
        self.validate()
        return {'schema':SCHEMA,'kind':'hello','context_id':self.context_id,'request_id':self.context_id+':hello',
            'admission_digest':self.binding_digest,'model_revision':self.model_revision,
            'contracts':{name:getattr(self,name+'_evidence_digest') for name in
                ('fixed_model','stateless','tokenizer','usage','environment','protocol','capacity')},
            'source_closure_digest':self.source_closure_digest,'max_frame_bytes':self.max_frame_bytes,
            'max_capture_bytes':self.max_capture_bytes,'inference':self.inference_binding}


def _pairs(items):
    result={}
    for k,v in items:
        if k in result:raise TransportError('duplicate JSON object key')
        result[k]=v
    return result


def _bad_constant(value):raise TransportError('nonfinite JSON constant')


def encode_frame(obj,limit):
    if not isinstance(obj,dict) or obj.get('schema')!=SCHEMA:raise TransportError('explicit protocol object required')
    frame=canonical(obj)+b'\n'
    if len(frame)>limit:raise TransportError('qualified frame capacity exceeded; no truncation')
    return frame


def decode_frame(frame,limit):
    if not isinstance(frame,bytes) or len(frame)>limit or not frame.endswith(b'\n') or b'\n' in frame[:-1]:
        raise TransportError('one complete bounded JSONL frame required')
    try:obj=json.loads(frame[:-1].decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_bad_constant)
    except (ValueError,UnicodeError,RecursionError) as exc:raise TransportError('malformed adapter frame') from exc
    if not isinstance(obj,dict) or obj.get('schema')!=SCHEMA:raise TransportError('wrong protocol schema')
    # Also rejects exponent-overflow floats admitted by the JSON parser.
    try:canonical(obj)
    except ValueError as exc:raise TransportError('nonfinite adapter value') from exc
    return obj


def check_handshake(admission,ack):
    if type(ack) is not dict:raise TransportError('handshake object required')
    expected=admission.handshake();expected['kind']='hello_ack'
    expected['assertions']={'fresh_process_context':True,'local_tokenization_without_provider':True,
        'fixed_revision':True,'online_learning':False,'persistent_memory':False,'no_detached_children':True,
        'effective_inference_settings_complete':True,'argv_cannot_override_admitted_inference':True}
    expected['effective_inference']=admission.inference_binding
    require_applied_inference(ack.get('effective_inference'),admission.inference_binding)
    if canonical(ack)!=canonical(expected):raise TransportError('adapter revision/contracts/handshake mismatch')
    return digest(ack)


def request_id(context_id,index,kind):
    if not _positive(index) or kind not in ('tokenize','generate'):raise TransportError('deterministic request identity required')
    return f'{context_id}:{index:06d}:{kind}'


def _request_fields(admission,index,payload,max_output_tokens):
    if type(admission) is not AdapterAdmission:raise TransportError('typed request admission required')
    admission.validate()
    if type(max_output_tokens) is not int or not 0<=max_output_tokens<=131072:
        raise TransportError('bounded output reservation including reasoning required')
    # Exactly the actual settings/schedule, not arbitrary caller metadata. The
    # qualified adapter must reject any effective argv/backend override.
    return {'schema':SCHEMA,'context_id':admission.context_id,
            'model_revision':admission.model_revision,'payload':payload,
            'payload_digest':digest(payload),
            'max_output_tokens_including_reasoning':max_output_tokens,
            'inference':admission.inference_binding}


def build_tokenize_request(admission,*,index,payload,max_output_tokens):
    request=_request_fields(admission,index,payload,max_output_tokens)
    request.update(kind='tokenize',request_id=request_id(admission.context_id,index,'tokenize'),
                   tokenizer_evidence_digest=admission.tokenizer_evidence_digest)
    return request


def build_generate_request(admission,*,index,payload,max_output_tokens,tokenizer_receipt_digest):
    require_digest(tokenizer_receipt_digest)
    request=_request_fields(admission,index,payload,max_output_tokens)
    request.update(kind='generate',request_id=request_id(admission.context_id,index,'generate'),
                   tokenizer_receipt_digest=tokenizer_receipt_digest,
                   usage_evidence_digest=admission.usage_evidence_digest)
    return request


def check_tokenization(response,*,context_id,request_id,model_revision,payload_digest,
                       tokenizer_digest,inference_binding,request_digest):
    keys={'schema','kind','context_id','request_id','model_revision','payload_digest',
          'tokenizer_evidence_digest','input_tokens','receipt_digest','effective_inference','request_digest'}
    if (type(response) is not dict or set(response)!=keys or response['schema']!=SCHEMA or response['kind']!='tokenize_result'
        or response['context_id']!=context_id or response['request_id']!=request_id
        or response['model_revision']!=model_revision or response['request_digest']!=request_digest
        or response['payload_digest']!=payload_digest or response['tokenizer_evidence_digest']!=tokenizer_digest
        or type(response['input_tokens']) is not int or response['input_tokens']<0):
        raise TransportError('tokenizer identity/count/inference contract mismatch')
    require_applied_inference(response['effective_inference'],inference_binding)
    core={k:v for k,v in response.items() if k!='receipt_digest'}
    if response['receipt_digest']!=digest(core):raise TransportError('tokenizer receipt digest mismatch')
    return response['input_tokens']


def check_result(response,*,context_id,request_id,model_revision,payload_digest,usage_digest,
                 inference_binding,request_digest,seen_draw_ids=()):
    expected={'schema','kind','context_id','request_id','model_revision','payload_digest','failed','response','usage',
              'usage_receipt_digest','applied_inference','generation_inference','request_digest'}
    if (type(response) is not dict or set(response)!=expected or response['schema']!=SCHEMA or response['kind']!='result'
        or response['context_id']!=context_id or response['request_id']!=request_id
        or response['model_revision']!=model_revision or response['payload_digest']!=payload_digest
        or response['request_digest']!=request_digest or type(response['failed']) is not bool):
        raise TransportError('model result identity/schema/inference mismatch')
    require_applied_inference(response['applied_inference'],inference_binding)
    validate_generation_record(response['generation_inference'],binding=inference_binding,
        context_id=context_id,request_id=request_id,failed=response['failed'],seen_draw_ids=seen_draw_ids)
    usage=response['usage']
    names={'uncached_input_tokens','cached_input_tokens','visible_output_tokens','reasoning_output_tokens',
           'total_input_tokens','total_output_tokens','usage_evidence_digest','provider_usage_digest','provider_usage_record'}
    if not isinstance(usage,dict) or set(usage)!=names:raise TransportError('complete normalized usage required, including failure')
    for k in names-{'usage_evidence_digest','provider_usage_digest','provider_usage_record'}:
        if type(usage[k]) is not int or usage[k]<0:raise TransportError('nonnegative exact usage counters required')
    require_digest(usage['provider_usage_digest'])
    if (not isinstance(usage['provider_usage_record'],dict) or not usage['provider_usage_record'] or
        usage['provider_usage_digest']!=digest(usage['provider_usage_record'])):
        raise TransportError('original provider usage record must be present and bound')
    if (usage['usage_evidence_digest']!=usage_digest or
        usage['total_input_tokens']!=usage['uncached_input_tokens']+usage['cached_input_tokens'] or
        usage['total_output_tokens']!=usage['visible_output_tokens']+usage['reasoning_output_tokens']):
        raise TransportError('cached/reasoning totals cannot be omitted, overlapped or refunded')
    if response['usage_receipt_digest']!=digest(usage):raise TransportError('normalized usage receipt mismatch')
    return usage
