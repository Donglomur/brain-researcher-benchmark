"""Concrete future stdio adapter supervisor; no provider/API-specific implementation.

The operator adapter is trusted, source-pinned and independently admitted. This
transport never reads credentials, guesses vendor APIs or claims handshake flags
prove server statelessness. No process can start without authentic authority.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time
from ..core.custody import VerifiedAuthority,canonical,digest
from ..core.plan import ContextState
from ..core.resources import ResourceLedger,CandidateCaps
from .protocol import (AdapterAdmission,TransportError,SCHEMA,encode_frame,decode_frame,
                       check_handshake,request_id,check_tokenization,check_result,
                       build_tokenize_request,build_generate_request)


class ModelAdapterSession:
    """Single-use context, single new adapter process, fail-stop/no retries."""
    def __init__(self,admission,*,authority,state,ledger):
        if not isinstance(admission,AdapterAdmission):raise TransportError('typed adapter admission required')
        admission.validate()
        if not isinstance(state,ContextState) or not isinstance(ledger,ResourceLedger):
            raise TransportError('actual trusted ContextState and ResourceLedger required')
        if (state.context.context_id!=admission.context_id or ledger.context_id!=admission.context_id
            or state.context.repetition!=admission.repetition):
            raise TransportError('context crossing forbidden')
        self.a=admission;self.state=state;self.ledger=ledger;self.authority=authority
        self.bindings={'context_digest':state.context.binding_digest,'caps_digest':CandidateCaps().binding_digest,
            'provider_admission_digest':admission.binding_digest,'fixed_model_evidence_digest':admission.fixed_model_evidence_digest,
            'stateless_evidence_digest':admission.stateless_evidence_digest,'tokenizer_evidence_digest':admission.tokenizer_evidence_digest,
            'usage_evidence_digest':admission.usage_evidence_digest,'environment_evidence_digest':admission.environment_evidence_digest,
            'inference_policy_digest':admission.inference_policy.binding_digest,
            'inference_binding_digest':digest(admission.inference_binding)}
        self._authorize(authority,model=True)
        self.lifecycle='allocated';self.proc=None;self.files={};self.captured=0;self.events=[]
        self.next_index=1;self.handshake_digest=None;self.capture_complete=True;self.owned_pid=None
        self.seen_draw_ids=set();self.generation_inference_records=[]

    def _authorize(self,authority,*,model=False,closing=False):
        if not isinstance(authority,VerifiedAuthority):raise TransportError('authentic verified adapter authority required before effects')
        if model:self.state.allow_model_call()
        role='close' if closing else ('candidate_query' if self.state.state=='query_open' else 'candidate_author')
        authority.require(role=role,domain='authentic',bindings=self.bindings)
        if model:self.ledger._open()

    def _deadline(self):
        left=self.ledger.started_ns+self.ledger.caps.wall_ns-time.monotonic_ns()
        if left<=0:raise TransportError('whole-context wall ceiling reached')
        return left/1e9

    def _capture(self,kind,data):
        if self.captured+len(data)>self.a.max_capture_bytes:
            self.capture_complete=False
            allowed=max(0,self.a.max_capture_bytes-self.captured)
            if allowed:self.files[kind].write(data[:allowed]);self.captured+=allowed
            raise TransportError('qualified aggregate capture capacity exhausted; no retry')
        self.files[kind].write(data);self.captured+=len(data)

    def _event(self,kind,body):
        event={'index':len(self.events),'context_id':self.a.context_id,'kind':kind,'body':body,
            'previous':self.events[-1]['event_digest'] if self.events else '0'*64}
        event['event_digest']=digest(event);self.events.append(event)
        if 'receipts' in self.files:self._capture('receipts',canonical(event)+b'\n')
        return event

    def _verify_sources(self):
        for pin in self.a.source_closure:
            path=Path(pin.path)
            if str(path.resolve(strict=True))!=pin.path:raise TransportError('source pin cannot follow symlink')
            st=path.stat()
            if not stat.S_ISREG(st.st_mode) or st.st_mode&0o022 or st.st_size!=pin.bytes:
                raise TransportError('adapter source regular-file/mode/size mismatch')
            if pin.path==self.a.argv[0] and not st.st_mode&0o111:raise TransportError('pinned adapter executable is not executable')
            if st.st_mode&(stat.S_ISUID|stat.S_ISGID):raise TransportError('privileged executable/source forbidden')
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                before=os.fstat(fd);h=hashlib.sha256();total=0
                while True:
                    data=os.read(fd,min(1048576,pin.bytes+1-total))
                    if not data:break
                    total+=len(data);h.update(data)
                    if total>pin.bytes:raise TransportError('source changed during read')
                after=os.fstat(fd)
                if total!=pin.bytes or h.hexdigest()!=pin.sha256 or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
                    raise TransportError('adapter exact source identity failed')
            finally:os.close(fd)

    def start(self):
        self._authorize(self.authority,model=True)
        if self.lifecycle!='allocated':raise TransportError('adapter launch is single-use, never retry')
        # Fail before effects if even the required handshake cannot fit its bound.
        encode_frame(self.a.handshake(),self.a.max_frame_bytes)
        self.lifecycle='starting'
        try:
            self._deadline();self._verify_sources()
            path=Path(self.a.capture_directory)
            if str(path.parent.resolve(strict=True))!=str(path.parent):raise TransportError('capture parent must be canonical and admitted')
            path.mkdir(mode=0o700) # Exclusive; never reuse another context's captures.
            for name in ('requests','responses','stderr','receipts'):
                self.files[name]=open(path/(name+'.bin'),'xb',buffering=0)
            self.proc=subprocess.Popen(list(self.a.argv),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                shell=False,close_fds=True,start_new_session=True,cwd='/',env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
            self.owned_pid=self.proc.pid
            for stream in (self.proc.stdin,self.proc.stdout,self.proc.stderr):os.set_blocking(stream.fileno(),False)
            self._event('original_launch',{'argv':list(self.a.argv),'pid':self.owned_pid,'admission_digest':self.a.binding_digest})
            ack=self._exchange(self.a.handshake())
            self.handshake_digest=check_handshake(self.a,ack)
            self.lifecycle='open'
            self._event('handshake_verified',{'handshake_digest':self.handshake_digest,
                'qualification':'protocol agreement only; independently authenticated evidence remains required'})
            return {'handshake_digest':self.handshake_digest,'admission_digest':self.a.binding_digest}
        except BaseException as exc:
            self._fail(exc)
            raise

    def _exchange(self,message):
        frame=encode_frame(message,self.a.max_frame_bytes)
        if self.proc is None or self.proc.poll() is not None:raise TransportError('adapter missing or already exited')
        selector=selectors.DefaultSelector();offset=0;buffer=bytearray();response=None
        try:
            selector.register(self.proc.stdin,selectors.EVENT_WRITE,'in')
            selector.register(self.proc.stdout,selectors.EVENT_READ,'out')
            selector.register(self.proc.stderr,selectors.EVENT_READ,'err')
            while response is None:
                left=self._deadline()
                events=selector.select(min(left,.05))
                if not events and self.proc.poll() is not None:raise TransportError('adapter exited without a complete response')
                for key,_ in events:
                    if key.data=='in':
                        written=os.write(key.fileobj.fileno(),frame[offset:offset+65536])
                        if written<=0:raise TransportError('adapter input made no progress')
                        self._capture('requests',frame[offset:offset+written]);offset+=written
                        if offset==len(frame):selector.unregister(self.proc.stdin)
                    else:
                        data=os.read(key.fileobj.fileno(),min(65536,self.a.max_frame_bytes+1) if key.data=='out' else 65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            if key.data=='out':raise TransportError('adapter EOF before complete JSONL response')
                            continue
                        self._capture('responses' if key.data=='out' else 'stderr',data)
                        if key.data=='err':continue
                        buffer.extend(data)
                        if len(buffer)>self.a.max_frame_bytes:raise TransportError('response exceeded qualified frame bound')
                        if b'\n' in buffer:
                            if offset!=len(frame) or buffer.count(b'\n')!=1 or not buffer.endswith(b'\n'):
                                raise TransportError('unsolicited/multiple/out-of-order response framing')
                            response=decode_frame(bytes(buffer),self.a.max_frame_bytes)
            return response
        finally:selector.close()

    def generate(self,payload,*,max_output_tokens,authority):
        # This check precedes tokenization as well as the actual provider request;
        # F after freeze/query can invoke neither through this transport.
        self._authorize(authority,model=True)
        if self.lifecycle!='open':raise TransportError('adapter context is not open')
        if type(max_output_tokens) is not int or max_output_tokens<0:raise TransportError('nonnegative declared output reservation required')
        payload_hash=digest(payload);index=self.next_index;self.next_index+=1
        tid=request_id(self.a.context_id,index,'tokenize');rid=request_id(self.a.context_id,index,'generate')
        try:
            tokenize=build_tokenize_request(self.a,index=index,payload=payload,max_output_tokens=max_output_tokens)
            tokenized=self._exchange(tokenize)
            count=check_tokenization(tokenized,context_id=self.a.context_id,request_id=tid,
                model_revision=self.a.model_revision,payload_digest=payload_hash,
                tokenizer_digest=self.a.tokenizer_evidence_digest,
                inference_binding=self.a.inference_binding,request_digest=digest(tokenize))
            self.ledger.reserve_model(rid,input_tokens=count,max_output_tokens=max_output_tokens,
                                      tokenizer_receipt_digest=tokenized['receipt_digest'])
            # State may have advanced since a trusted synchronous/tokenizer operation.
            self._authorize(authority,model=True)
            request=build_generate_request(self.a,index=index,payload=payload,
                max_output_tokens=max_output_tokens,tokenizer_receipt_digest=tokenized['receipt_digest'])
            self._event('model_reserved',{'request_id':rid,'payload_digest':payload_hash,'input_tokens':count,
                'max_output_tokens':max_output_tokens,'inference':self.a.inference_binding,
                'request_digest':digest(request)})
            result=self._exchange(request)
            usage=check_result(result,context_id=self.a.context_id,request_id=rid,model_revision=self.a.model_revision,
                payload_digest=payload_hash,usage_digest=self.a.usage_evidence_digest,
                inference_binding=self.a.inference_binding,request_digest=digest(request),
                seen_draw_ids=self.seen_draw_ids)
            original_inference=json.loads(canonical({'request_id':rid,'request_digest':digest(request),'failed':result['failed'],
                'applied_inference':result['applied_inference'],'generation_inference':result['generation_inference']}))
            self.generation_inference_records.append(original_inference)
            draw_id=result['generation_inference']['draw_id']
            if draw_id is not None:self.seen_draw_ids.add(draw_id)
            self.ledger.complete_model(rid,charged_input_tokens=usage['total_input_tokens'],
                charged_output_tokens=usage['total_output_tokens'],usage_receipt_digest=result['usage_receipt_digest'],failed=result['failed'])
            event=self._event('original_model_result',{'request_id':rid,'result_digest':digest(result),
                'usage_receipt_digest':result['usage_receipt_digest'],'failed':result['failed'],
                'inference_record':original_inference})
            return {'response':result['response'],'failed':result['failed'],'usage':usage,
                    'original_result_digest':digest(result),'event_digest':event['event_digest'],
                    'inference_record':original_inference}
        except BaseException as exc:
            # Unresolved provider usage remains a reserved ledger entry. Do not
            # guess zero cost, retry, refund calls or fabricate final completion.
            self._fail(exc)
            raise

    def _terminate_owned(self):
        if self.proc is None:return
        if self.proc.poll() is None:
            if os.getpgid(self.owned_pid)!=self.owned_pid:raise TransportError('owned adapter process-group identity changed')
            os.killpg(self.owned_pid,signal.SIGKILL)
            self.proc.wait(timeout=10)
        # The qualified adapter contract prohibits detached children. No PID
        # search or signal to a possibly reused dead leader's group occurs.
        for stream,kind in ((self.proc.stdout,'responses'),(self.proc.stderr,'stderr')):
            if stream is not None and not stream.closed:
                while True:
                    try:data=os.read(stream.fileno(),65536)
                    except BlockingIOError:
                        self.capture_complete=False
                        self.events.append({'kind':'undrained_stream_after_owned_termination','stream':kind,
                                            'event_digest':digest(['undrained',kind])})
                        break
                    if not data:break
                    self._capture(kind,data)
                    if kind=='responses':
                        self.capture_complete=False
                        self.events.append({'kind':'unexpected_trailing_adapter_stdout','bytes':len(data),
                                            'event_digest':digest(['trailing',len(data)])})
        for stream in (self.proc.stdin,self.proc.stdout,self.proc.stderr):
            if stream is not None and not stream.closed:stream.close()

    def _fail(self,exc):
        self.lifecycle='failed';self.capture_complete=False
        body={'error_type':type(exc).__name__,'error':str(exc),'returncode':None if self.proc is None else self.proc.poll(),
              'unresolved_usage':[k for k,v in self.ledger.provider_requests.items() if v['status']=='reserved'],
              'inference_binding':self.a.inference_binding,
              'generation_inference_records':list(self.generation_inference_records)}
        try:self._event('original_failure',body)
        except BaseException:
            self.events.append({'kind':'failure_receipt_persistence_failed','body':body,'event_digest':digest(body)})
        try:self._terminate_owned()
        except BaseException as cleanup:
            self.capture_complete=False
            self.events.append({'kind':'original_cleanup_failure','error':str(cleanup),'event_digest':digest(str(cleanup))})
        self._flush_close()

    def _flush_close(self):
        for file in self.files.values():
            if not file.closed:
                try:os.fsync(file.fileno())
                finally:file.close()

    def close(self,*,authority):
        self._authorize(authority,closing=True)
        if self.lifecycle!='open':raise TransportError('failed/unstarted adapter cannot claim successful closure')
        try:
            if any(v['status']=='reserved' for v in self.ledger.provider_requests.values()):
                raise TransportError('unresolved usage prohibits clean provider closure')
            request={'schema':SCHEMA,'kind':'goodbye','context_id':self.a.context_id,
                'request_id':self.a.context_id+':goodbye','model_revision':self.a.model_revision,
                'completed_generation_requests':self.next_index-1,'inference':self.a.inference_binding}
            response=self._exchange(request)
            expected={**request,'kind':'goodbye_ack','context_discarded':True}
            if canonical(response)!=canonical(expected):raise TransportError('adapter context closure mismatch')
            self._event('original_close_ack',{'ack':response})
            # Terminate the still-owned live group after acknowledgement. Ack is
            # not evidence of remote memory deletion beyond admitted contracts.
            self._terminate_owned();self.lifecycle='closed'
            if not self.capture_complete:raise TransportError('incomplete or unsolicited trailing adapter stream prohibits clean closure')
            result={'schema':'n073_model_transport_close_v1','context_id':self.a.context_id,
                'admission_digest':self.a.binding_digest,'events_digest':digest(self.events),
                'capture_bytes_before_closure_receipt':self.captured,'capture_complete':self.capture_complete,
                'completed_generation_requests':self.next_index-1,'original_returncode':self.proc.returncode,
                'closure_kind':'protocol_ack_then_owned_local_termination','provider_statelessness':'independently admitted evidence, not inferred from ack',
                'inference_binding':self.a.inference_binding,
                'generation_inference_records':list(self.generation_inference_records)}
            result['receipt_digest']=digest(result);self._event('closure_receipt',result);self._flush_close()
            return result
        except BaseException as exc:
            self._fail(exc);raise
