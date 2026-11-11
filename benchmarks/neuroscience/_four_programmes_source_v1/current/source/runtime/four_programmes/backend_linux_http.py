"""Actual ordered request -> physical exchange -> raw -> parsed capture caller.

The publisher and arm are the original lifecycle objects. The class does not
grant execution authority or manufacture an H admission from its outputs.
"""
from .common import need, same
from .backend_capture import CapturedRecord
from .backend_protocol import request_wire, parse_response, ENDPOINTS, COMMIT
from .backend_linux_io import NativeIOCustody, HttpAttempt
from .precommit_records import RECORDS, validate_type
from .early_resources import failure_observations


def _row(kind, **fields):
    return {'schema':RECORDS[kind]['schema_literal'],**fields}


class LocalHttpExchange:
    def __init__(self,handle,io,endpoint,ordinal):
        need(type(io) is NativeIOCustody and io.handle is handle,'same original IO custody')
        need(endpoint in ENDPOINTS and type(ordinal) is int and ordinal>=0,'fixed endpoint/ordinal')
        self.handle=handle;self.io=io;self.endpoint=endpoint;self.ordinal=ordinal
        self.request=None;self.raw=None;self.parsed=None;self.rejected=None;self.transport=None
        self.error=None;self.secondaries=[];self.entered=False;self.loading=False
        self.body=None;self.raw_body=None;self.parsed_value=None
        # This owner is retained by the native owner before run's first effect.

    def retain(self,error,site):
        if self.error is None:self.error=error
        elif error is not self.error:self.secondaries.append(error)
        self.handle.retain(error,'http_'+site)

    def _name(self,suffix):
        return 'worker/http_'+self.endpoint+'_'+str(self.ordinal)+'_'+suffix+'.json'

    def _common(self):
        h=self.handle
        return dict(attempt=h.base.pin,condition=h.condition,endpoint=self.endpoint,
                    ordinal=self.ordinal,pair_nonce=h.ack_body['nonce'])

    def run(self,path,pid,uid,artifacts,semantic_capture=None):
        need(not self.entered,'one original request slot, never retry a failed exchange')
        self.entered=True;h=self.handle;f=h.profile_body
        deadline=h.G if self.endpoint=='completion' else h.J
        semantic=None
        try:
            need(h.base is not None and h.raw_first is None,'actual admitted live base before transport')
            if self.endpoint=='completion':
                need(type(semantic_capture) is CapturedRecord,'actual earlier pending completion capture')
                semantic=h.read_capture(semantic_capture,'CompletionRequest')
                need(h.pending is semantic_capture and semantic['request_ordinal']==self.ordinal,
                     'same original pending semantic completion')
            else:need(semantic_capture is None,'no generation before initialization')
            h._reserve_record()
            wire,body_bytes=request_wire(self.endpoint,f,semantic)
            prepared=self.io.now(deadline);method,route=ENDPOINTS[self.endpoint]
            self.body=_row('BackendHttpRequest',**self._common(),method=method,path=route,
                completion_request=None if semantic_capture is None else semantic_capture.pin,
                wire_hex=wire.hex(),wire_bytes=len(wire),body_bytes=body_bytes,prepared_ns=prepared,
                cost_prefix=h.meter.record())
            self.request=h.publisher.capture(self._name('request'),'BackendHttpRequest',self.body)
            # Retain transport owner before any socket acquisition or send.
            self.transport=HttpAttempt(self.io,self.endpoint,self.ordinal,deadline)
            try:self.transport.run(path,pid,uid,wire,f)
            except BaseException as error:self.retain(error,'physical')
            a=self.transport
            h._reserve_record()
            failures=[] if self.error is None else failure_observations(h.owner.parent)
            need(self.error is None or failures,'retained raw first failure has closed observation')
            state='complete' if a.complete and self.error is None else ('partial' if a.known_wire_bytes else 'failed')
            self.raw_body=_row('RawHttpResponse',**self._common(),request=self.request.pin,source_commit=COMMIT,
                state=state,status_code=a.status,header_prefix_hex=a.header.hex(),body_prefix_hex=a.body.hex(),
                header_bytes=len(a.header),body_bytes=len(a.body),declared_content_length=a.declared,
                known_wire_bytes=a.known_wire_bytes,unknown_physical_read=self.io.unknown_read,
                started_ns=a.started,finished_ns=a.finished,first_error=None if not failures else failures[0],
                secondary_errors=failures[1:],cost_prefix=h.meter.record())
            self.raw=h.publisher.capture(self._name('raw'),'RawHttpResponse',self.raw_body)
            if self.error is not None:raise self.error
            kind,value=parse_response(self.raw_body,self.body,f,artifacts,
                semantic_request=semantic,generation_deadline=h.G if semantic is not None else None)
            self.parsed_value=value
            # The sole permitted loading retry is a complete authenticated raw
            # 503 body. There is no invented LoadingHealth wire type.
            if kind=='loading':self.loading=True;return self
            h._reserve_record();common=self._common()
            if kind=='health':
                record_kind='ParsedHealth';row=_row(record_kind,**common,raw=self.raw.pin,
                    source_commit=COMMIT,body=value,observed_ns=a.finished)
            elif kind=='slots':
                record_kind='ParsedSlots';row=_row(record_kind,**common,raw=self.raw.pin,
                    source_commit=COMMIT,slots=[value],observed_ns=a.finished)
            else:
                need(kind=='completion' and semantic_capture is not None,'closed parsed response kind')
                record_kind='ParsedCompletion';row=_row(record_kind,**common,raw=self.raw.pin,
                    source_commit=COMMIT,body=value,request=self.request.pin,received_ns=a.finished)
            self.parsed=h.publisher.capture(self._name('parsed'),record_kind,row)
            return self
        except BaseException as error:
            self.retain(error,'exchange')
            # Publication can already have failed. Preserve the original error;
            # no new publisher, fresh budget, or fictitious successful raw Pin.
            if self.request is not None:
                try:
                    h._reserve_record();errors=failure_observations(h.owner.parent)
                    rejected=_row('RejectedResponse',**self._common(),
                        raw=None if self.raw is None else self.raw.pin,source_commit=COMMIT,
                        http_status=None if self.transport is None else self.transport.status,
                        reason='transport_incomplete' if self.transport is None or not self.transport.complete else 'schema',
                        first_error=errors[0],cost_prefix=h.meter.record())
                    self.rejected=h.publisher.capture(self._name('rejected'),'RejectedResponse',rejected)
                except BaseException as secondary:self.retain(secondary,'rejection_capture')
            raise self.error


class InitializationHttpOwner:
    """Contiguous sole health/loading probes, followed by one fresh slots probe."""
    def __init__(self,handle,io):
        need(type(io) is NativeIOCustody and io.handle is handle,'same original initialization owner')
        self.handle=handle;self.io=io;self.attempts=[];self.entered=False;self.health=None;self.slots=None
    def run(self,path,pid,uid,artifacts):
        need(not self.entered,'one original initialization HTTP sequence');self.entered=True
        h=self.handle;limit=h.profile_body['limits']['maximum_initialization_probes']
        while self.health is None:
            need(len(self.attempts)+1<limit,'leave original one slots request within probe cap')
            a=LocalHttpExchange(h,self.io,'health',len(self.attempts));self.attempts.append(a)
            a.run(path,pid,uid,artifacts)
            if a.loading:
                self.io.now(h.J);continue
            need(a.parsed is not None,'actual complete health publication');self.health=a
        a=LocalHttpExchange(h,self.io,'slots',len(self.attempts));self.attempts.append(a)
        a.run(path,pid,uid,artifacts);need(not a.loading and a.parsed is not None,'actual complete slots publication')
        self.slots=a;return self.health.parsed,self.slots.parsed
