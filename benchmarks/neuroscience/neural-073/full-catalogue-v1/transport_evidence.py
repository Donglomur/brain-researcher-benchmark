"""Extract original settled transport usage after authenticated actual closure.

No launch, provider call, neural/model read or credential discovery occurs here.
The bytes are post-close custody observations, not invented launch-time file pins.
The pure parser is independently testable; it cannot issue native qualification.
Protocol payload/response fields are not projected. Original provider usage metadata
is preserved; its vendor-defined content requires the admitted usage-only contract,
not an assumption from dictionary shape. This module never silently filters it.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib
import json
import math
import os
import stat
import time
from .runtime.core.custody import VerifiedAuthority, canonical, digest, require_digest
from .runtime.core.outcomes import classify_aggregate, valid_violation
from .runtime.provider_transport.protocol import (AdapterAdmission, SCHEMA,
    decode_frame, check_handshake, check_tokenization, check_result,
    build_tokenize_request, build_generate_request, request_id)


class ExtractionError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractionLimits:
    max_capture_bytes: int
    max_frame_bytes: int
    max_projection_bytes: int
    max_workspace_bytes: int
    max_frames: int
    wall_seconds: int

    def __post_init__(self):
        if any(type(v) is not int or v<=0 for v in asdict(self).values()):
            raise ExtractionError('finite positive extraction bounds required')
        if self.max_frame_bytes>self.max_capture_bytes:
            raise ExtractionError('frame bound exceeds complete capture bound')
        # Conservative logical envelope includes decoded receipt frames, original
        #inference/usage records, serializers and simultaneous protocol frames.
        if self.max_workspace_bytes<128*self.max_frame_bytes+64*self.max_projection_bytes+65536:
            raise ExtractionError('workspace does not cover complete bounded parser/projection')


@dataclass(frozen=True)
class StudyExtractionLimits:
    max_total_capture_bytes: int
    max_total_projection_bytes: int
    max_workspace_bytes: int
    wall_seconds: int
    max_contexts: int = 234

    def __post_init__(self):
        if any(type(v) is not int or v<=0 for v in asdict(self).values()) or self.max_contexts!=234:
            raise ExtractionError('finite full234 extraction capacity required')


class UsageExtractionBudget:
    """One whole-study counter. Failed invocations consume reservations; no retry."""
    def __init__(self,limits,expected_context_ids):
        if type(limits) is not StudyExtractionLimits:
            raise ExtractionError('typed whole-study extraction limits required')
        ids=tuple(expected_context_ids)
        if len(ids)!=234 or len(set(ids))!=234 or any(type(x) is not str or not x for x in ids):
            raise ExtractionError('all234 exact distinct context identities required')
        self.limits=limits;self.expected=frozenset(ids);self.started={};self.completed={}
        self.reserved_reads=0;self.reserved_outputs=0;self.actual_read_bytes=0;self.projection_bytes=0
        self.deadline=time.monotonic()+limits.wall_seconds
    def begin(self,cid,limits):
        if time.monotonic()>self.deadline:raise ExtractionError('whole-study extraction wall bound exhausted')
        if cid not in self.expected or cid in self.started:raise ExtractionError('unselected or repeated capture extraction')
        if limits.max_workspace_bytes>self.limits.max_workspace_bytes:
            raise ExtractionError('context workspace exceeds whole-study workspace capacity')
        if (self.reserved_reads+limits.max_capture_bytes>self.limits.max_total_capture_bytes
            or self.reserved_outputs+limits.max_projection_bytes>self.limits.max_total_projection_bytes):
            raise ExtractionError('full-study extraction reservation exhausted')
        self.reserved_reads+=limits.max_capture_bytes;self.reserved_outputs+=limits.max_projection_bytes
        self.started[cid]={'reserved_read_bytes':limits.max_capture_bytes,'reserved_projection_bytes':limits.max_projection_bytes,
                           'actual_read_bytes':0,'status':'started'}
    def read(self,cid,n):
        self.started[cid]['actual_read_bytes']+=n;self.actual_read_bytes+=n
    def complete(self,cid,projection,size):
        if cid not in self.started or cid in self.completed:raise ExtractionError('unstarted/repeated projection completion')
        self.started[cid]['status']='complete';self.projection_bytes+=size
        self.completed[cid]=projection['projection_digest']
    def fail(self,cid,exc):
        if cid in self.started:self.started[cid].update(status='failed',exception_type=type(exc).__name__,message=str(exc))
    def receipt(self):
        return {'schema':'n073_usage_extraction_accounting_v1','contexts_started':len(self.started),
            'contexts_completed':len(self.completed),'reserved_capture_bytes':self.reserved_reads,
            'reserved_projection_bytes':self.reserved_outputs,'actual_capture_body_read_bytes':self.actual_read_bytes,
            'actual_projection_bytes':self.projection_bytes,'attempts':dict(self.started),
            'limits':asdict(self.limits),'physical_RSS_measured':False}
    def require_complete(self,expected_context_ids):
        if frozenset(expected_context_ids)!=self.expected or set(self.completed)!=self.expected:
            raise ExtractionError('complete original234 extraction closure required')
        if time.monotonic()>self.deadline:raise ExtractionError('whole-study extraction wall bound exhausted')
        receipt=self.receipt();receipt['projection_index_digest']=digest(dict(sorted(self.completed.items())))
        receipt['receipt_digest']=digest(receipt);return receipt


def _closed(value,fields,role):
    if type(value) is not dict or set(value)!=set(fields):raise ExtractionError('closed '+role+' fields required')
    return value


def _same(actual,expected,message):
    if canonical(actual)!=canonical(expected):raise ExtractionError(message)


def _hashed(row,key='receipt_digest'):
    if type(row) is not dict or row.get(key)!=digest({k:v for k,v in row.items() if k!=key}):
        raise ExtractionError('original '+key+' mismatch')


def _nonnegative(v):
    if type(v) is not int or v<0:raise ExtractionError('nonnegative exact counter required')
    return v


class _Meter:
    def __init__(self,limits,budget=None,cid=None):
        self.limits=limits;self.budget=budget;self.cid=cid;self.read_bytes=0;self.frames=0;self.retained_json_bytes=0;self.projected_row_bytes=0
        self.deadline=time.monotonic()+limits.wall_seconds
    def check(self):
        if time.monotonic()>self.deadline or (self.budget is not None and time.monotonic()>self.budget.deadline):
            raise ExtractionError('capture extraction deadline exhausted')
    def read(self,n):
        self.check()
        if self.read_bytes+n>self.limits.max_capture_bytes:raise ExtractionError('capture read bound exceeded')
        self.read_bytes+=n
        if self.budget is not None:self.budget.read(self.cid,n)
    def keep(self,value):
        from .runtime.private_store.store import bounded_json
        size=len(bounded_json(value,self.limits.max_projection_bytes))
        if 128*self.limits.max_frame_bytes+64*(self.retained_json_bytes+size)+65536>self.limits.max_workspace_bytes:
            raise ExtractionError('retained original metadata workspace bound exceeded')
        self.retained_json_bytes+=size
        return size
    def frame(self):
        self.check();self.frames+=1
        if self.frames>self.limits.max_frames:raise ExtractionError('capture frame-work bound exceeded')


def _signature(st):return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode,st.st_uid,st.st_nlink)


def _extent(name,st):
    return {'file':name,'bytes':st.st_size,'device':st.st_dev,'inode':st.st_ino,
        'mode':stat.S_IMODE(st.st_mode),'uid':st.st_uid,'mtime_ns':st.st_mtime_ns,'ctime_ns':st.st_ctime_ns}


def _safe_stat(st):
    if (not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_uid!=os.getuid()
        or st.st_mode&0o022 or st.st_mode&(stat.S_ISUID|stat.S_ISGID)):
        raise ExtractionError('owned regular single-link non-group-writable capture required')


def _root(path):
    if type(path) is not str or not path.startswith('/') or path=='/' or os.path.normpath(path)!=path or '\0' in path:
        raise ExtractionError('explicit canonical admitted capture directory required')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for part in path.split('/')[1:]:
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=nxt
        st=os.fstat(fd)
        if st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o700:
            raise ExtractionError('owned private0700 capture root required')
        return fd,_signature(st)
    except BaseException:os.close(fd);raise


@dataclass(frozen=True)
class _Frame:
    body: bytes
    offset: int
    def pin(self):return {'offset':self.offset,'bytes':len(self.body),'sha256':hashlib.sha256(self.body).hexdigest()}
    @property
    def complete(self):return self.body.endswith(b'\n')


class _Frames:
    """One pass over one exact owned file; retains at most one bounded frame."""
    def __init__(self,rootfd,name,meter,frame_limit):
        self.fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=rootfd)
        try:
            self.before=os.fstat(self.fd);_safe_stat(self.before)
            if self.before.st_size>meter.limits.max_capture_bytes:raise ExtractionError('file capture bound exceeded')
        except BaseException:os.close(self.fd);raise
        self.name=name;self.meter=meter;self.limit=frame_limit;self.buffer=bytearray();self.readn=0;self.offset=0
        self.hash=hashlib.sha256();self.eof=False;self.pin=None
    def next(self):
        self.meter.check()
        while True:
            newline=self.buffer.find(b'\n')
            if newline>=0:
                body=bytes(self.buffer[:newline+1]);del self.buffer[:newline+1]
                if len(body)>self.limit:raise ExtractionError('complete capture frame exceeds selected bound')
                out=_Frame(body,self.offset);self.offset+=len(body);self.meter.frame();return out
            if self.eof:
                if not self.buffer:return None
                body=bytes(self.buffer);self.buffer.clear();out=_Frame(body,self.offset)
                self.offset+=len(body);self.meter.frame();return out
            if len(self.buffer)>=self.limit:raise ExtractionError('capture frame exceeds selected bound')
            request=min(65536,self.limit-len(self.buffer),self.before.st_size-self.readn)
            if request:
                self.meter.read(request);chunk=os.read(self.fd,request)
                if len(chunk)!=request:raise ExtractionError('short original capture read')
                self.readn+=len(chunk);self.hash.update(chunk);self.buffer.extend(chunk)
            else:
                #Exact initial size and stable final stat establish this extent;
                #do not perform an uncharged speculative one-byte lookahead.
                after=os.fstat(self.fd)
                if _signature(after)!=_signature(self.before):raise ExtractionError('original capture changed during read')
                self.pin={**_extent(self.name,after),'sha256':self.hash.hexdigest()};self.eof=True
    def finish(self):
        if self.next() is not None:raise ExtractionError('unexpected extra original protocol bytes')
        return self.pin
    def verify_stable(self,rootfd):
        after=os.fstat(self.fd);named=os.stat(self.name,dir_fd=rootfd,follow_symlinks=False)
        if _signature(after)!=_signature(self.before) or _signature(named)!=_signature(self.before):
            raise ExtractionError('capture extent/name changed after its read')
    def close(self):os.close(self.fd)


def _decode(frame,cap):
    if frame is None or not frame.complete:raise ExtractionError('complete original protocol frame required')
    return decode_frame(frame.body,cap)


def _json_event(frame,limit):
    if frame is None or not frame.complete or len(frame.body)>limit:
        raise ExtractionError('complete original receipt frame required')
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out:raise ExtractionError('duplicate receipt key')
            out[k]=v
        return out
    def bad(_):raise ExtractionError('nonfinite receipt value')
    try:obj=json.loads(frame.body[:-1].decode(),object_pairs_hook=unique,parse_constant=bad)
    except (ValueError,UnicodeError,RecursionError) as exc:raise ExtractionError('invalid original receipt JSON') from exc
    _closed(obj,('index','context_id','kind','body','previous','event_digest'),'receipt event')
    if canonical(obj)+b'\n'!=frame.body:raise ExtractionError('noncanonical original receipt bytes')
    _hashed(obj,'event_digest');return obj


def _receipt_chain(admission,transport,frames,meter,expected_custody=None):
    head='0'*64;index=0;h=hashlib.sha256();h.update(b'[');model={};handshake=None;launch=None
    close_ack=None;failures=[];closing=None;closing_frame=None;events_count=0
    reservations={};pending=None
    normal=transport['schema']=='n073_model_transport_close_v1'
    final_kind='closure_receipt' if normal else 'original_exhaustion_closure'
    while True:
        f=frames.next()
        if f is None:break
        e=_json_event(f,meter.limits.max_frame_bytes)
        if (type(e['index']) is not int or e['index']!=index or e['previous']!=head or e['context_id']!=admission.context_id):
            raise ExtractionError('original receipt chain/identity mismatch')
        kind=e['kind'];body=e['body']
        if kind==final_kind:
            closing=e;closing_frame=f
            if closing['body']!=transport:raise ExtractionError('capture closure differs from actual broker transport')
            if normal and pending is not None:raise ExtractionError('normal close has unmatched original model reservation')
            if frames.next() is not None:raise ExtractionError('bytes after original closure receipt')
            break
        if index:h.update(b',')
        h.update(canonical(e));events_count+=1
        if kind=='original_aggregate_broker_launch':
            if index!=0 or launch is not None or type(body) is not dict or body.get('admission_digest')!=admission.binding_digest or body.get('argv')!=list(admission.argv):
                raise ExtractionError('original actual aggregate launch identity differs')
            if expected_custody is not None:
                _same(body.get('actual_custody'),expected_custody,'original aggregate launch custody differs')
            launch=body
        elif kind=='handshake_verified':
            if index!=1 or handshake is not None or launch is None:raise ExtractionError('handshake receipt order')
            require_digest(body['handshake_digest']);handshake=body['handshake_digest']
        elif kind=='model_reserved':
            _closed(body,('request_id','payload_digest','input_tokens','max_output_tokens','inference','request_digest'),'model reservation event')
            rid=body['request_id']
            if (handshake is None or pending is not None or close_ack is not None or failures
                or rid in reservations or rid!=request_id(admission.context_id,len(reservations)+1,'generate')):
                raise ExtractionError('duplicate/unmatched/out-of-order original model reservation')
            for key in ('payload_digest','request_digest'):require_digest(body[key])
            _nonnegative(body['input_tokens']);_nonnegative(body['max_output_tokens'])
            if body['max_output_tokens']>131072:raise ExtractionError('original reservation exceeds response ceiling')
            _same(body['inference'],admission.inference_binding,'original reservation inference differs')
            meter.keep(body);reservations[rid]=body;pending=rid
        elif kind=='original_model_result':
            _closed(body,('request_id','result_digest','usage_receipt_digest','failed','inference_record'),'model result event')
            rid=body['request_id']
            if handshake is None or pending!=rid or rid in model or close_ack is not None or failures:
                raise ExtractionError('unreserved/duplicate/out-of-order model result receipt')
            for key in ('result_digest','usage_receipt_digest'):require_digest(body[key])
            meter.keep(body);model[rid]=body;pending=None
        elif kind=='original_close_ack':
            if not normal or close_ack is not None or handshake is None or pending is not None:
                raise ExtractionError('unexpected/repeated goodbye or unmatched original reservation')
            _closed(body,('ack',),'close ack');close_ack=body['ack']
        elif kind=='original_settled_exhaustion_failure':
            if normal or handshake is None or close_ack is not None or failures:raise ExtractionError('unexpected/repeated exhaustion failure')
            if body.get('type')!='BudgetExceeded' or not valid_violation(body.get('ledger_violation')):
                raise ExtractionError('original qualified settled exhaustion required')
            failures.append(body)
        else:raise ExtractionError('unsupported/failed original transport receipt event: '+str(kind))
        index+=1;head=e['event_digest']
    h.update(b']')
    if (closing is None or launch is None or handshake is None or h.hexdigest()!=transport['events_digest']
        or (normal and close_ack is None)):
        raise ExtractionError('complete original transport receipt closure required')
    if not normal and failures!=transport['original_failures']:
        raise ExtractionError('original settled failures differ from exhaustion receipt')
    return {'model_events':model,'reservations':reservations,'pending_reservation':pending,'handshake_digest':handshake,'close_ack':close_ack,'failures':failures,
            'closure_frame_bytes':len(closing_frame.body),'event_count':events_count+1,
            'source_receipts_event_digest':h.hexdigest()}


def _tail(admission,transport,request,response,requests,responses,chain,meter,index,settled_rows):
    if transport['schema']!='n073_model_transport_exhaustion_close_v2':
        raise ExtractionError('normal transport cannot omit a generation or truncate a frame')
    failures=chain['failures'];kind=transport.get('partial_protocol_kind')
    if not failures or failures[-1].get('failed_exchange_kind')!=kind:
        raise ExtractionError('terminal tokenize tail lacks original same-context qualified failure')
    rp=None if request is None else request.pin();sp=None if response is None else response.pin()
    status=None
    if request is None:
        if response is not None or kind!='tokenize':raise ExtractionError('unmatched terminal protocol bytes')
        status='interrupted_tokenize_before_request_bytes'
    elif not request.complete:
        if kind!='tokenize' or response is not None:raise ExtractionError('only original interrupted tokenize request may be partial')
        #encode_frame emits canonical keys. Even an early prefix must agree with
        #the known context/inference/kind prefix; qualified original exception
        #metadata establishes tokenize when interruption precedes the kind bytes.
        prefix=canonical({'context_id':admission.context_id,'inference':admission.inference_binding,'kind':'tokenize'})[:-1]+b','
        if request.body[:min(len(request.body),len(prefix))]!=prefix[:min(len(request.body),len(prefix))]:
            raise ExtractionError('partial request is not the original canonical tokenize prefix')
        status='interrupted_tokenize_request'
    else:
        q=_decode(request,admission.max_frame_bytes)
        expected=build_tokenize_request(admission,index=index,payload=q.get('payload'),max_output_tokens=q.get('max_output_tokens_including_reasoning'))
        _same(q,expected,'terminal request is not exact next tokenize request')
        if response is None or not response.complete:
            if kind!='tokenize':raise ExtractionError('truncated tokenize response requires original interrupted exchange')
            status='interrupted_tokenize_response'
        else:
            r=_decode(response,admission.max_frame_bytes)
            reserved=check_tokenization(r,context_id=admission.context_id,request_id=request_id(admission.context_id,index,'tokenize'),
                model_revision=admission.model_revision,payload_digest=q['payload_digest'],tokenizer_digest=admission.tokenizer_evidence_digest,
                inference_binding=admission.inference_binding,request_digest=digest(q))
            if kind is not None:raise ExtractionError('completed tokenize exchange cannot claim partial exchange')
            violation=failures[-1]['ledger_violation'];dimension=violation['dimension']
            values={'model_calls':len(settled_rows)+1,
                    'input_tokens':sum(x['usage']['total_input_tokens'] for x in settled_rows)+reserved,
                    'output_tokens_reserved':sum(x['usage']['total_output_tokens'] for x in settled_rows)+q['max_output_tokens_including_reasoning']}
            caps={'model_calls':512,'input_tokens':2097152,'output_tokens_reserved':131072}
            if dimension not in values or violation!={'dimension':dimension,'used':values[dimension],'cap':caps[dimension]} or values[dimension]<=caps[dimension]:
                raise ExtractionError('terminal complete tokenization does not match original reservation exhaustion')
            status='completed_tokenize_before_reservation_exhaustion'
    if requests.next() is not None or responses.next() is not None:
        raise ExtractionError('extra bytes after unique terminal tokenize-only tail')
    return {'kind':status,'generation_performed':False,'request_id':request_id(admission.context_id,index,'tokenize'),
            'request_frame_pin':rp,'response_frame_pin':sp,'original_failure_digest':digest(failures[-1]),
            'original_partial_protocol_kind':kind,'raw_tail_bytes_exported':False}


def _protocol(admission,transport,generation_records,requests,responses,chain,meter):
    hello=_decode(requests.next(),admission.max_frame_bytes);_same(hello,admission.handshake(),'actual original hello differs')
    ack=_decode(responses.next(),admission.max_frame_bytes)
    if check_handshake(admission,ack)!=chain['handshake_digest']:raise ExtractionError('original hello receipt differs')
    if type(generation_records) is not list or len(generation_records)>512:
        raise ExtractionError('complete bounded original generation list required')
    out=[];seen=set();model_used=set()
    for index,original in enumerate(generation_records,1):
        meter.check();qf=requests.next();tf=responses.next()
        q=_decode(qf,admission.max_frame_bytes)
        tokenize=build_tokenize_request(admission,index=index,payload=q.get('payload'),max_output_tokens=q.get('max_output_tokens_including_reasoning'))
        _same(q,tokenize,'original tokenize request differs from admitted constructed request')
        t=_decode(tf,admission.max_frame_bytes)
        reserved=check_tokenization(t,context_id=admission.context_id,request_id=request_id(admission.context_id,index,'tokenize'),
            model_revision=admission.model_revision,payload_digest=q['payload_digest'],tokenizer_digest=admission.tokenizer_evidence_digest,
            inference_binding=admission.inference_binding,request_digest=digest(q))
        gf=requests.next();rf=responses.next();g=_decode(gf,admission.max_frame_bytes)
        expected=build_generate_request(admission,index=index,payload=q['payload'],max_output_tokens=q['max_output_tokens_including_reasoning'],
                                        tokenizer_receipt_digest=t['receipt_digest'])
        _same(g,expected,'original generate differs from its preceding validated tokenize')
        rid=request_id(admission.context_id,index,'generate')
        reservation=chain['reservations'].get(rid)
        _same(reservation,{'request_id':rid,'payload_digest':q['payload_digest'],'input_tokens':reserved,
            'max_output_tokens':g['max_output_tokens_including_reasoning'],'inference':admission.inference_binding,
            'request_digest':digest(g)},'original model reservation differs from actual tokenize/generate fields')
        result=_decode(rf,admission.max_frame_bytes);rid=request_id(admission.context_id,index,'generate')
        usage=check_result(result,context_id=admission.context_id,request_id=rid,model_revision=admission.model_revision,
            payload_digest=q['payload_digest'],usage_digest=admission.usage_evidence_digest,
            inference_binding=admission.inference_binding,request_digest=digest(g),seen_draw_ids=seen)
        if usage['total_input_tokens']<reserved:raise ExtractionError('original charged input cannot refund reservation')
        inference={'request_id':rid,'request_digest':digest(g),'failed':result['failed'],
            'applied_inference':result['applied_inference'],'generation_inference':result['generation_inference']}
        _same(inference,original,'captured actual result differs from retained generation inference')
        draw=result['generation_inference']['draw_id']
        if draw is not None:seen.add(draw)
        event=chain['model_events'].get(rid)
        if event is not None:
            _same(event,{'request_id':rid,'result_digest':digest(result),'usage_receipt_digest':result['usage_receipt_digest'],
                'failed':result['failed'],'inference_record':inference},'ordinary model event differs from original captured result')
            model_used.add(rid)
        elif (transport['schema']!='n073_model_transport_exhaustion_close_v2' or index!=len(generation_records)
              or not chain['failures'] or transport['partial_protocol_kind'] is not None
              or chain['pending_reservation']!=rid):
            raise ExtractionError('missing model event is not the one original settled overflow result')
        if event is None:
            violation=chain['failures'][-1]['ledger_violation'];dimension=violation['dimension']
            field={'input_tokens':'total_input_tokens','output_tokens':'total_output_tokens'}.get(dimension)
            cap={'input_tokens':2097152,'output_tokens':131072}.get(dimension)
            used=None if field is None else sum(x['usage'][field] for x in out)+usage[field]
            if field is None or violation!={'dimension':dimension,'used':used,'cap':cap} or used<=cap:
                raise ExtractionError('missing model event does not match actual settled token overflow')
        row={'request_id':rid,'request_digest':digest(g),'tokenizer_receipt_digest':t['receipt_digest'],
            'reserved_input_tokens':reserved,'max_output_tokens':g['max_output_tokens_including_reasoning'],
            'original_result_digest':digest(result),'usage':usage,'inference_record':inference,
            'request_frame_pin':gf.pin(),'response_frame_pin':rf.pin()}
        size=meter.keep(row)
        if meter.projected_row_bytes+size>meter.limits.max_projection_bytes:
            raise ExtractionError('complete generation projection body bound exceeded')
        meter.projected_row_bytes+=size;out.append(row)
    if model_used!=set(chain['model_events']):raise ExtractionError('extra original model result not in generation list')
    if set(chain['reservations'])!={row['request_id'] for row in out}:
        raise ExtractionError('missing or unmatched original model reservation; no unresolved generate tail')
    q=requests.next();r=responses.next();tail=None
    if transport['schema']=='n073_model_transport_close_v1':
        goodbye={'schema':SCHEMA,'kind':'goodbye','context_id':admission.context_id,
            'request_id':admission.context_id+':goodbye','model_revision':admission.model_revision,
            'completed_generation_requests':len(generation_records),'inference':admission.inference_binding}
        _same(_decode(q,admission.max_frame_bytes),goodbye,'exact original goodbye required')
        expected={**goodbye,'kind':'goodbye_ack','context_discarded':True}
        _same(_decode(r,admission.max_frame_bytes),expected,'exact original goodbye acknowledgement required')
        _same(chain['close_ack'],expected,'original close acknowledgement event differs')
        if transport['completed_generation_requests']!=len(generation_records):raise ExtractionError('completed generation count differs')
        if requests.next() is not None or responses.next() is not None:raise ExtractionError('bytes after complete original goodbye')
    elif q is not None or r is not None or transport.get('partial_protocol_kind')=='tokenize':
        tail=_tail(admission,transport,q,r,requests,responses,chain,meter,len(generation_records)+1,out)
    elif transport.get('partial_protocol_kind') is not None:
        raise ExtractionError('partial/unresolved generation or non-tokenize exchange is forbidden')
    return out,tail


def _check_closure(admission,broker,aggregate,generation_records):
    if type(admission) is not AdapterAdmission:raise ExtractionError('exact typed AdapterAdmission required')
    admission.validate();_hashed(broker,'digest');_hashed(aggregate)
    classify_aggregate(aggregate,context_id=admission.context_id).require_scoreable()
    if aggregate.get('broker_closure')!=broker or aggregate.get('context_id')!=admission.context_id:
        raise ExtractionError('actual aggregate and broker closure differ')
    if broker.get('context_id')!=admission.context_id or broker.get('provider_admission_digest')!=admission.binding_digest or broker.get('populated')!=0:
        raise ExtractionError('actual broker admission/context/drain differs')
    transport=broker['transport_receipt'];_hashed(transport)
    if (transport.get('schema') not in ('n073_model_transport_close_v1','n073_model_transport_exhaustion_close_v2')
        or transport.get('context_id')!=admission.context_id or transport.get('admission_digest')!=admission.binding_digest
        or transport.get('capture_complete') is not True or transport.get('unresolved_usage',[])!=[]
        or transport.get('inference_binding')!=admission.inference_binding
        or transport.get('generation_inference_records')!=generation_records):
        raise ExtractionError('complete original same-context transport closure required')
    if transport['schema']=='n073_model_transport_exhaustion_close_v2':
        if broker.get('exhaustion_evidence')!=transport.get('exhaustion_evidence') or broker.get('exhaustion_evidence') is None:
            raise ExtractionError('actual qualified exhaustion custody required')
    return transport


def _stderr_extent(rootfd):
    """Inspect only an owned regular stderr extent; never block on a FIFO."""
    fd=os.open('stderr.bin',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=rootfd)
    try:
        before=os.fstat(fd);_safe_stat(before)
        return before
    finally:os.close(fd)


def _capture_projection(admission,transport,generation_records,limits,meter,extraction_source_digest,expected_custody=None):
    """Guarded explicit file consumer; caller authenticates the actual closure first."""
    rootfd,root_identity=_root(admission.capture_directory);opened=[]
    try:
        #Read only metadata of stderr; its body is deliberately outside this parser.
        stderr=_stderr_extent(rootfd)
        readers={}
        for name in ('requests','responses','receipts'):
            reader=_Frames(rootfd,name+'.bin',meter,admission.max_frame_bytes if name!='receipts' else limits.max_frame_bytes)
            opened.append(reader);readers[name]=reader
        total=sum(r.before.st_size for r in opened)+stderr.st_size
        if total>admission.max_capture_bytes or total>limits.max_capture_bytes:
            raise ExtractionError('actual complete original four-stream capture exceeds admitted capacity')
        chain=_receipt_chain(admission,transport,readers['receipts'],meter,expected_custody)
        rows,tail=_protocol(admission,transport,generation_records,readers['requests'],readers['responses'],chain,meter)
        pins={name:reader.finish() for name,reader in readers.items()}
        #Closure is the final receipt frame, added after the original cumulative
        #capture_bytes_before_closure_receipt counter. No body hash is inferred for stderr.
        if total-chain['closure_frame_bytes']!=transport['capture_bytes_before_closure_receipt']:
            raise ExtractionError('actual four-stream byte total differs from original closure')
        stderr_now=os.stat('stderr.bin',dir_fd=rootfd,follow_symlinks=False)
        if _signature(stderr_now)!=_signature(stderr):raise ExtractionError('stderr extent changed after original closure')
        for reader in opened:reader.verify_stable(rootfd)
        if _signature(os.fstat(rootfd))!=root_identity:raise ExtractionError('capture directory changed during extraction')
        namedfd,named_identity=_root(admission.capture_directory)
        os.close(namedfd)
        if named_identity!=root_identity:raise ExtractionError('capture root path changed during extraction')
        pins['stderr_extent']={**_extent('stderr.bin',stderr),'body_hashed':False}
        result={'schema':'n073_original_transport_usage_projection_v1','context_id':admission.context_id,
            'provider_admission_digest':admission.binding_digest,'transport_receipt_digest':transport['receipt_digest'],
            'source_capture_pins':pins,'source_receipts_event_digest':chain['source_receipts_event_digest'],
            'generation_records':rows,'unmetered_terminal_tokenize_tail':tail,
            'extraction_source_digest':extraction_source_digest}
        result['projection_digest']=digest(result)
        from .runtime.private_store.store import bounded_json
        raw=bounded_json(result,limits.max_projection_bytes);meter.check()
        return result,len(raw)
    finally:
        for reader in opened:reader.close()
        os.close(rootfd)


def extract_transport_usage(*,admission,broker_closure,aggregate_receipt,generation_records,
                            limits,extraction_source_digest,writer_authority,study_budget):
    """Authenticated future writer entry; never call for invented native success.

    Owner obtains writer_authority from its independently admitted OperatorContext
    only after extract_usage permission. This module does not accept a boolean or
    JSON claim of authorization. Original score capability must already be saved
    before any new close capability increments the owner's issuance ordinal.
    """
    if type(limits) is not ExtractionLimits or type(study_budget) is not UsageExtractionBudget:
        raise ExtractionError('typed per-context and whole234 capacity required')
    if type(admission) is not AdapterAdmission:raise ExtractionError('exact admitted original adapter required')
    admission.validate();require_digest(extraction_source_digest)
    if type(generation_records) is not list or len(generation_records)>512:
        raise ExtractionError('bounded complete original generation metadata required')
    from .runtime.private_store.store import bounded_json
    bounded_json(generation_records,limits.max_projection_bytes)
    if type(writer_authority) is not VerifiedAuthority:raise ExtractionError('genuine independently verified writer capability required')
    transport=broker_closure.get('transport_receipt',{}) if type(broker_closure) is dict else {}
    writer_authority.require(role='close',domain='authentic',bindings={
        'provider_admission_digest':admission.binding_digest,'context_digest':digest(admission.context_id),
        'transport_receipt_digest':transport.get('receipt_digest'),
        'generation_records_digest':digest(generation_records),'extraction_source_digest':extraction_source_digest})
    if limits.max_frame_bytes<admission.max_frame_bytes or limits.max_capture_bytes<admission.max_capture_bytes:
        raise ExtractionError('selected extraction opportunity must cover admitted original transport ceilings')
    transport=_check_closure(admission,broker_closure,aggregate_receipt,generation_records)
    study_budget.begin(admission.context_id,limits)
    meter=_Meter(limits,study_budget,admission.context_id)
    try:
        expected_custody={'context_id':admission.context_id,'aggregate_identity':broker_closure['aggregate_identity'],
            'broker_identity':broker_closure['broker_identity'],'capture_directory':admission.capture_directory,
            'oom_protection_digest':broker_closure['oom_protection_digest'],
            'payload_eligibility_contract_digest':aggregate_receipt['oom_contract_digest']}
        projection,size=_capture_projection(admission,transport,generation_records,limits,meter,extraction_source_digest,expected_custody)
        study_budget.complete(admission.context_id,projection,size)
        return projection
    except BaseException as exc:
        study_budget.fail(admission.context_id,exc);raise


def validate_usage_projection(projection,*,context_id,provider_admission_digest,
        transport_receipt_digest,generation_records,extraction_source_digest):
    """Pure shape/hash/identity check AFTER independent artifact custody admission.

    This function cannot establish genuine capture/native/operator provenance.
    It never opens the source_capture_pins or turns this JSON into an authority.
    """
    keys=('schema','context_id','provider_admission_digest','transport_receipt_digest',
          'source_capture_pins','source_receipts_event_digest','generation_records',
          'unmetered_terminal_tokenize_tail','extraction_source_digest','projection_digest')
    _closed(projection,keys,'usage projection');_hashed(projection,'projection_digest')
    if (projection['schema']!='n073_original_transport_usage_projection_v1' or projection['context_id']!=context_id
        or projection['provider_admission_digest']!=provider_admission_digest
        or projection['transport_receipt_digest']!=transport_receipt_digest
        or projection['extraction_source_digest']!=extraction_source_digest):
        raise ExtractionError('original usage projection identity differs')
    for field in ('provider_admission_digest','transport_receipt_digest','source_receipts_event_digest','extraction_source_digest'):
        require_digest(projection[field])
    pins=projection['source_capture_pins'];_closed(pins,('requests','responses','receipts','stderr_extent'),'capture pins')
    common={'file','bytes','device','inode','mode','uid','mtime_ns','ctime_ns'}
    for name,row in pins.items():
        _closed(row,common|({'body_hashed'} if name=='stderr_extent' else {'sha256'}),'capture extent')
        if row['file']!=('stderr.bin' if name=='stderr_extent' else name+'.bin'):
            raise ExtractionError('unexpected capture member')
        for field in common-{'file'}:_nonnegative(row[field])
        if row['mode']&0o022 or row['mode']&0o6000:raise ExtractionError('unsafe original capture mode')
        if name=='stderr_extent':
            if row['body_hashed'] is not False:raise ExtractionError('stderr body was not hashed by extraction')
        else:require_digest(row['sha256'])
    def frame_pin(value,member,allow_none=False):
        if allow_none and value is None:return
        _closed(value,('offset','bytes','sha256'),'frame pin');require_digest(value['sha256'])
        _nonnegative(value['offset']);_nonnegative(value['bytes'])
        if value['bytes']==0 or value['offset']+value['bytes']>pins[member]['bytes']:
            raise ExtractionError('frame lies outside exact original capture')
    rows=projection['generation_records']
    if type(rows) is not list or type(generation_records) is not list or len(rows)!=len(generation_records) or len(rows)>512:
        raise ExtractionError('complete exact generation usage list required')
    last_request_end=last_response_end=0
    for index,(row,original) in enumerate(zip(rows,generation_records),1):
        _closed(row,('request_id','request_digest','tokenizer_receipt_digest','reserved_input_tokens','max_output_tokens',
                     'original_result_digest','usage','inference_record','request_frame_pin','response_frame_pin'),'generation usage')
        if row['request_id']!=request_id(context_id,index,'generate') or row['inference_record']!=original or row['request_digest']!=original.get('request_digest'):
            raise ExtractionError('captured generation list/order differs')
        for field in ('request_digest','tokenizer_receipt_digest','original_result_digest'):require_digest(row[field])
        _nonnegative(row['reserved_input_tokens']);_nonnegative(row['max_output_tokens'])
        if row['max_output_tokens']>131072:raise ExtractionError('output reservation exceeds selected ceiling')
        frame_pin(row['request_frame_pin'],'requests');frame_pin(row['response_frame_pin'],'responses')
        if row['request_frame_pin']['offset']<last_request_end or row['response_frame_pin']['offset']<last_response_end:
            raise ExtractionError('overlapping or reordered original generation frame pins')
        last_request_end=row['request_frame_pin']['offset']+row['request_frame_pin']['bytes']
        last_response_end=row['response_frame_pin']['offset']+row['response_frame_pin']['bytes']
        usage=row['usage'];fields={'uncached_input_tokens','cached_input_tokens','visible_output_tokens','reasoning_output_tokens',
            'total_input_tokens','total_output_tokens','usage_evidence_digest','provider_usage_digest','provider_usage_record'}
        _closed(usage,fields,'normalized original usage')
        for field in fields-{'usage_evidence_digest','provider_usage_digest','provider_usage_record'}:_nonnegative(usage[field])
        require_digest(usage['usage_evidence_digest']);require_digest(usage['provider_usage_digest'])
        if (type(usage['provider_usage_record']) is not dict or not usage['provider_usage_record']
            or usage['provider_usage_digest']!=digest(usage['provider_usage_record'])
            or usage['total_input_tokens']!=usage['uncached_input_tokens']+usage['cached_input_tokens']
            or usage['total_output_tokens']!=usage['visible_output_tokens']+usage['reasoning_output_tokens']
            or usage['total_input_tokens']<row['reserved_input_tokens']):
            raise ExtractionError('invalid original usage decomposition/reservation')
    tail=projection['unmetered_terminal_tokenize_tail']
    if tail is not None:
        _closed(tail,('kind','generation_performed','request_id','request_frame_pin','response_frame_pin',
                     'original_failure_digest','original_partial_protocol_kind','raw_tail_bytes_exported'),'terminal tokenize tail')
        allowed=('interrupted_tokenize_before_request_bytes','interrupted_tokenize_request','interrupted_tokenize_response',
                 'completed_tokenize_before_reservation_exhaustion')
        if (tail['kind'] not in allowed or tail['generation_performed'] is not False or tail['raw_tail_bytes_exported'] is not False
            or tail['request_id']!=request_id(context_id,len(rows)+1,'tokenize')):
            raise ExtractionError('only explicit unmetered terminal tokenize may be projected')
        require_digest(tail['original_failure_digest'])
        qpin,rpin=tail['request_frame_pin'],tail['response_frame_pin']
        if (tail['kind']=='interrupted_tokenize_before_request_bytes' and (qpin is not None or rpin is not None)
            or tail['kind']=='interrupted_tokenize_request' and (qpin is None or rpin is not None)
            or tail['kind']=='interrupted_tokenize_response' and qpin is None
            or tail['kind']=='completed_tokenize_before_reservation_exhaustion' and (qpin is None or rpin is None)):
            raise ExtractionError('terminal tokenize kind/pin extent mismatch')
        expected=None if tail['kind']=='completed_tokenize_before_reservation_exhaustion' else 'tokenize'
        if tail['original_partial_protocol_kind']!=expected:raise ExtractionError('tail kind differs from original exchange')
        frame_pin(tail['request_frame_pin'],'requests',True);frame_pin(tail['response_frame_pin'],'responses',True)
        for member,start in (('request',last_request_end),('response',last_response_end)):
            pin=tail[member+'_frame_pin']
            if pin is not None and (pin['offset']<start or pin['offset']+pin['bytes']!=pins[member+'s']['bytes']):
                raise ExtractionError('terminal tokenize tail not at exact capture end')
    return projection
