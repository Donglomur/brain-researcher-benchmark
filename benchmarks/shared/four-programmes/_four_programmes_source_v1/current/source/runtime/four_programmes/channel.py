"""Private original host channel. Its qualified launch supplies the FDs, never a request."""
import os
import selectors
import struct
import time
from . import dependencies
from .common import need, closed, integer, encode, parse, pin, bounded_size, failure

_HOST_EVENT = object()

class HostEvent:
    __slots__=("body","raw_pin","sequence","source","campaign","_token")
    def __init__(self,token,body,raw,sequence,source,campaign):
        need(token is _HOST_EVENT,"only actual qualified host-channel reader creates an event")
        self.body=body;self.raw_pin=pin(raw);self.sequence=sequence
        self.source=source;self.campaign=campaign;self._token=token

class RootChannel:
    """CI C/H transport bridge; exact launch-bound source and sequence.

    Native isolation must keep both ends outside participant views. Authentication
    is the independently qualified original inherited channel, not a JSON issuer
    string or local Python type. The currently unselected qualification refuses.
    """
    def __init__(self,read_fd,write_fd,*,binding,selected_qualification,meter):
        dependencies.require("root_issuer_source_and_qualification",selected_qualification)
        closed(binding,("campaign","source","launch","read_identity","write_identity","maximum_frame_bytes"))
        self.read_fd=integer(read_fd);self.write_fd=integer(write_fd)
        need(read_fd!=write_fd,"distinct original channel ends")
        self.binding=binding;self.meter=meter;self.sequence=0;self.closed=False
        self.failed=False;self.outstanding=None;self.completed_events=[]
        self.cap=integer(binding["maximum_frame_bytes"],1)
        need(self.cap<=268435456,"finite whole original control frame; never a scientific subset")
        for fd,expected in ((read_fd,binding["read_identity"]),(write_fd,binding["write_identity"])):
            s=os.fstat(fd)
            need([s.st_dev,s.st_ino,s.st_mode]==expected,"actual independently selected FD identity")
            os.set_inheritable(fd,False);os.set_blocking(fd,False)
    def _whole_job_poll(self):
        campaign=getattr(self,'_hm_whole_poll_campaign_v1',None)
        if campaign is None:
            # Actual W endpoint carries the source-owned stage meter. Its check
            # polls the enclosing whole domain and original W physical counter;
            # select uses the same prospectively selected polling interval.
            from .hm_whole_job_native_observations_v1 import HMStageChannelMeterV1
            if type(self.meter)is HMStageChannelMeterV1:
                stage=self.meter.stage
                need(type(self)is HostEndpoint and stage.carrier.endpoint is self,
                     'same actual H/W endpoint and original stage meter')
                self.meter.check()
                return min(.05,stage.campaign.plan.body['polling']['interval_ns']/1e9)
            return .05
        from .hm_whole_job_native_v1 import HMNativeCampaignOwnerV1
        need(type(campaign)is HMNativeCampaignOwnerV1 and type(self)is HostEndpoint and
             campaign.reservations.controller_endpoint is self and
             campaign.reservations.controller_custody.construction.channel is self,
             'only actual original whole-job H controller channel may activate native polling')
        campaign.poll_whole_once()
        return min(.05,campaign.reservations.plan.body['polling']['interval_ns']/1e9)

    def _wait(self,fd,event):
        self.meter.check();sel=None;primary=None
        try:
            sel=selectors.DefaultSelector();sel.register(fd,event)
            while True:
                self.meter.check()
                period=self._whole_job_poll()
                ready=sel.select(min(period,max(0,(self.meter.deadline_ns-time.monotonic_ns())/1e9)))
                self._whole_job_poll()
                if ready:break
        except BaseException as error:
            primary=error;self.meter.own_error(error,"channel_wait")
        if sel is not None:
            try:sel.close()
            except BaseException as error:
                self.meter.cleanup_errors.append(failure(error))
                if primary is None:primary=error;self.meter.own_error(error,"channel_selector_close")
        if primary is not None:raise primary
    def _read(self,size):
        self.meter.charge("read_bytes",size)
        self.meter.charge("retained_bytes",size)
        parts=[];remaining=size
        try:
            while remaining:
                self._wait(self.read_fd,selectors.EVENT_READ)
                try:raw=os.read(self.read_fd,min(65536,remaining))
                except BlockingIOError:continue
                need(raw,"original channel premature EOF")
                parts.append(raw);remaining-=len(raw)
            return b"".join(parts)
        except BaseException as error:
            self.meter.own_error(error,"channel_read_extent");raise
    def _write(self,raw):
        need(type(raw) is bytes and 0<len(raw)<=self.cap,"complete earlier-bounded control frame")
        frame=struct.pack(">Q",len(raw))+raw
        self.meter.charge("write_bytes",len(frame));self.meter.charge("retained_bytes",len(frame))
        offset=0
        try:
            while offset<len(frame):
                self._wait(self.write_fd,selectors.EVENT_WRITE)
                try:n=os.write(self.write_fd,frame[offset:])
                except BlockingIOError:continue
                need(n>0,"original control write progress");offset+=n
        except BaseException as error:
            self.meter.own_error(error,"channel_write_extent");raise
    def send(self,operation,body):
        need(not self.closed and not self.failed and self.outstanding is None and
             operation in ("stage","continuation","final_report","failure"),
             "closed source-owned host operations")
        self.meter.charge("work_units",bounded_size(body)+4096)
        self.sequence+=1
        message={"schema":"four_programme_host_request_v1","campaign":self.binding["campaign"],
                 "launch":self.binding["launch"],"sequence":self.sequence,"operation":operation,"body":body}
        raw=encode(message);need(len(raw)<=self.cap,"complete control request within earlier reservation")
        self.outstanding=pin(raw)
        try:self._write(raw)
        except BaseException:
            self.failed=True;raise
        return self.outstanding
    def receive(self,request_identity):
        need(not self.closed and not self.failed and self.outstanding==request_identity and
             self.outstanding is not None,"actual outstanding original request")
        try:
            size=struct.unpack(">Q",self._read(8))[0]
            need(0<size<=self.cap,"admitted finite response extent before body read")
            self.meter.charge("work_units",size*64+4096)
            raw=self._read(size);body=parse(raw,self.cap)
            closed(body,("schema","campaign","source","sequence","request","status","result"))
            need(body["schema"]=="four_programme_host_response_v1" and
                 body["campaign"]==self.binding["campaign"] and body["source"]==self.binding["source"] and
                 type(body["sequence"]) is int and body["sequence"]==self.sequence and
                 body["request"]==request_identity and body["status"] in ("observed","failed","unknown"),
                 "same actual host source, original request and nonreplayable sequence")
            # Retain each actual returned response under this exact channel.
            # This is additional ownership bookkeeping, not a replayed event.
            self.meter.charge('retained_bytes',512)
            event=HostEvent(_HOST_EVENT,body,raw,self.sequence,body["source"],body["campaign"])
            self.completed_events.append(event)
            self.outstanding=None;return event
        except BaseException as error:
            self.failed=True;self.meter.own_error(error,"coordinator_response_capture");raise
    def owns_completed_event(self,event):
        return (type(event) is HostEvent and any(item is event for item in self.completed_events) and
                event.source==self.binding['source'] and event.campaign==self.binding['campaign'])
    def exchange(self,operation,body):
        return self.receive(self.send(operation,body))
    def close(self):
        if self.closed:return
        self.closed=True;primary=None
        for name in ("read_fd","write_fd"):
            fd=getattr(self,name);setattr(self,name,None)
            try:os.close(fd)
            except BaseException as error:
                self.meter.cleanup_errors.append(failure(error))
                if primary is None:primary=error;self.meter.own_error(error,"channel_close")
        if primary is not None:raise primary

class HostEndpoint(RootChannel):
    """Actual H end of the same private bounded original C/H channel.

    It accepts only one pending complete request. A response is committed after
    actual full frame persistence; failed writes retain the pending request and
    forbid another operation. Endpoint/source isolation remains independently
    qualified; JSON pins cannot create that property.
    """
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.pending=None;self.failed=False
    def accept(self):
        need(not self.closed and not self.failed and self.pending is None,
             "one original source request at a time")
        try:
            size=struct.unpack(">Q",self._read(8))[0]
            need(0<size<=self.cap,"pre-admitted complete request frame")
            self.meter.charge("work_units",size*64+4096)
            raw=self._read(size);body=parse(raw,self.cap)
            closed(body,("schema","campaign","launch","sequence","operation","body"))
            need(body["schema"]=="four_programme_host_request_v1" and
                 body["campaign"]==self.binding["campaign"] and body["launch"]==self.binding["launch"] and
                 type(body["sequence"]) is int and body["sequence"]==self.sequence+1 and
                 body["operation"] in ("stage","continuation","final_report","failure"),
                 "same original C launch and next fixed operation")
            self.pending={"body":body,"raw_identity":pin(raw)}
            return self.pending
        except BaseException as error:
            self.failed=True;self.meter.own_error(error,"host_request_capture");raise
    def respond(self,request,*,status,result):
        need(not self.closed and not self.failed and request is self.pending and request is not None,
             "actual outstanding captured request")
        need(status in ("observed","failed","unknown"),"explicit original observation disposition")
        try:
            message={"schema":"four_programme_host_response_v1","campaign":self.binding["campaign"],
                     "source":self.binding["source"],"sequence":request["body"]["sequence"],
                     "request":request["raw_identity"],"status":status,"result":result}
            self.meter.charge("work_units",bounded_size(message))
            raw=encode(message);self._write(raw)
            self.meter.check()
            self.sequence=request["body"]["sequence"];self.pending=None
            return pin(raw)
        except BaseException as error:
            self.failed=True;self.meter.own_error(error,"host_response_publication");raise
    def send(self,*args,**kwargs):
        need(False,"host owns responses, never coordinator requests")
    def receive(self,*args,**kwargs):
        need(False,"host accepts exact request, never coordinator responses")

class TerminalEvidence:
    """Only exact H-carried terminal metadata, while C's programme writer is inactive.

    No filesystem, source, array, target, or candidate-report body is accessed.
    Full raw original stage/job/stream evidence is carried by the previously
    bounded bridge frame. Input cannot supply an additional body-reader callback.
    """
    KINDS=frozenset(("start_binding","stage_completion","budget_return","terminal_state",
                     "physical_observation","stage_receipt","original_outcome","original_process",
                     "stdout","stderr"))
    def __init__(self,event,meter):
        need(type(event) is HostEvent,"actual host bridge event")
        self.meter=meter;self.rows={}
        rows=event.body["result"]["evidence"]
        need(type(rows) is list and len(rows)<=65536,"complete bounded terminal evidence domain")
        for row in rows:
            closed(row,("kind","descriptor","hex"))
            need(row["kind"] in self.KINDS,"terminal-only fixed evidence kind")
            d=row["descriptor"];closed(d,("path","bytes","sha256"));integer(d["bytes"])
            need(type(row["hex"]) is str and len(row["hex"])==d["bytes"]*2 and
                 all(c in "0123456789abcdef" for c in row["hex"]),"canonical full bounded raw evidence")
            meter.charge("work_units",len(row["hex"])+4096)
            meter.charge("retained_bytes",d["bytes"])
            raw=bytes.fromhex(row["hex"])
            need(pin(raw)=={k:d[k] for k in ("bytes","sha256")},"exact original H-captured bytes")
            key=encode(d);need(key not in self.rows,"no duplicate evidence alias")
            self.rows[key]=(row["kind"],raw)
    def read(self,d,cap,*,metadata=False):
        key=encode(d);need(key in self.rows and d["bytes"]<=cap,"only original complete terminal evidence")
        raw=self.rows[key][1]
        self.meter.charge("read_bytes",len(raw))
        if metadata:self.meter.charge("work_units",len(raw)*64+4096)
        return raw
    def document(self,d,cap):
        return parse(self.read(d,cap,metadata=True),cap)

