"""Actual fixed private file-handoff consumer selected by the adopted design.

The root issuer remains independently qualified and separately owned. This
reader cannot mint approval from a descriptor, participant text or a callback.
It consumes only the exact finite original event names in the private binding.
"""
import os
import stat
import time
from .common import need,integer,relative,parse,failure
from . import dependencies

_EVENT=object()

class RootFileEvent:
    __slots__=("body","descriptor","raw","root_binding","_token")
    def __init__(self,token,body,descriptor,raw,root_binding):
        need(token is _EVENT,"only qualified fixed root file channel")
        self.body=body;self.descriptor=descriptor;self.raw=raw;self.root_binding=root_binding;self._token=token

class RootAuthorityFiles:
    def __init__(self,*,store,schemas,binding,binding_pin,selected_qualification,
                 bound_request,issuer,issuer_source,adapter_source,accepted_manifest,reader_source,
                 private_root_binding):
        dependencies.require("root_issuer_source_and_qualification",selected_qualification)
        schemas.validate("resources","authority_channel_schema",binding,store.meter)
        need(binding["kind"]=="root_owned_bounded_file_handoff_v2","exact original channel kind")
        need(binding["channel_qualification"]==selected_qualification and
             binding["reader_source"]==reader_source and binding["issuer_source"]==issuer_source and
             binding["private_root_binding"]==private_root_binding,
             "selected exact channel, root, issuer and reader source")
        names=binding["relative_event_names"];stages=binding["ordered_stages"]
        need(len(names)==len(stages)<=binding["max_events"] and len(set(names))==len(names),
             "all source-selected original event names")
        for name in names:relative(name)
        self.store=store;self.schemas=schemas;self.binding=binding;self.binding_pin=binding_pin
        self.request=bound_request;self.issuer=issuer;self.adapter_source=adapter_source
        self.accepted_manifest=accepted_manifest;self.position=0;self.previous=None;self.closed=False
        self.attempts=[];self.consumed={}
    def _present(self,name):
        # No byte reads or globbing during wait. Exactly one ordinary path is
        # tested, under the same bounded source-owned root; all probe work is
        # charged before the syscall. Absence is an expected pending event.
        self.store.meter.check();self.store.meter.charge("work_units",4096)
        fds=[];primary=None;present=False
        try:
            fds,leaf=self.store._parent(name)
            try:s=os.stat(leaf,dir_fd=fds[-1],follow_symlinks=False)
            except FileNotFoundError:present=False
            else:
                need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=self.binding["event_byte_cap"],
                     "complete bounded ordinary root event")
                present=True
        except BaseException as error:
            primary=error;self.store.meter.own_error(error,"root_event_probe")
        cleanup=self.store._close(fds)
        if primary is not None:raise primary
        if cleanup is not None:
            self.store.meter.own_error(cleanup,"root_event_probe_close");raise cleanup
        return present
    def next(self,stage):
        need(not self.closed and self.position<len(self.binding["ordered_stages"]),"one pending original root event")
        need(stage==self.binding["ordered_stages"][self.position],"exact original stage continuation order")
        name=self.binding["relative_event_names"][self.position]
        attempt={"sequence":self.position+1,"stage":stage,"name":name,"observed":None,"admitted":False,"failure":None}
        self.attempts.append(attempt)
        try:
            while not self._present(name):
                self.store.meter.check()
                remaining=(self.store.meter.deadline_ns-time.monotonic_ns())/1e9
                need(remaining>0,"original authority wait cutoff")
                time.sleep(min(.01,remaining))
            raw,actual=self.store.capture_created(name,self.binding["event_byte_cap"],metadata=True)
            attempt["observed"]=actual
            body=parse(raw,self.binding["event_byte_cap"])
            self.schemas.validate("authority","continuation_event_schema",body,self.store.meter)
            need(body["programme"]==self.binding["programme"] and body["campaign_id"]==self.binding["campaign_id"],
                 "same original canonical programme and campaign")
            need(body["request"]==self.request and body["issuer"]==self.issuer and
                 body["adapter_source"]==self.adapter_source and body["accepted_manifest"]==self.accepted_manifest,
                 "exact original source/request/issuer authority")
            need(type(body["sequence"]) is int and body["sequence"]==self.position+1 and
                 body["stage"]==stage and body["predecessor"]==self.previous,"exact nonreplayable continuation lineage")
            need(len(body["cause_artifacts"])<=self.binding["event_member_cap"],"complete bounded original cause set")
            # No cause/result/reference/model body is dereferenced here. Later
            # source-owned consumers must independently admit their exact type
            # and original completion. A root event is not numerical evidence.
            event=RootFileEvent(_EVENT,body,actual,raw,self.binding_pin)
            self.consumed[self.position+1]=event;self.position+=1;self.previous=actual;attempt["admitted"]=True
            return event
        except BaseException as error:
            attempt["failure"]=failure(error);self.store.meter.own_error(error,"root_continuation")
            self.closed=True
            raise
    def require_observed(self,event,*,stage,completion,causes):
        need(type(event) is RootFileEvent and event.root_binding==self.binding_pin and
             self.consumed.get(event.body["sequence"]) is event,"actual event from this original channel")
        body=event.body
        need(body["stage"]==stage and body["verdict"]=="admitted" and
             body["original_external_completion"]==completion and body["cause_artifacts"]==causes,
             "exact observed original cause/completion before dependent operation")
        need(body["legacy_authority"] is not None,"actual selected original operation authority")
        return body["legacy_authority"]
    def close(self):
        # Stores open and close bounded handles per operation; no hidden FD or
        # issuer process is owned by this reader. A failed event never retries.
        self.closed=True
