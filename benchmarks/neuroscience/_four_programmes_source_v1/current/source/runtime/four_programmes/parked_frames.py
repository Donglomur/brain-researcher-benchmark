"""Incremental H transport for the existing Ready, Release and ACK records.

One step makes at most one nonblocking I/O call so the actual H caller can pump
worker streams/whole resources between steps. Parsed frames are transport
evidence, never issuer authority, entry admission, or original completion.
"""
import os
import struct
import time
from .common import need,integer,same,encode,parse,bounded_size,pin
from .precommit_records import validate_type
from .parked_pipes import ParkedPipes

class ParkedHostFrames:
    def __init__(self,pipes,*,ticket,ticket_pin):
        need(type(pipes)is ParkedPipes,'actual source-owned original pipe pair')
        self.pipes=pipes;self.meter=pipes.meter
        self.first_raw=None;self.failed=False;self.received=[]
        self.header=bytearray();self.body=bytearray();self.body_size=None
        self.header_reserved=False;self.body_reserved=False;self.current=None
        self.release_attempted=False;self.outgoing=None;self.sent=0;self.release_complete=False
        self.release_body=None;self.release_identity=None
        self.read_known=0;self.write_known=0;self.read_extent_unknown=False;self.write_extent_unknown=False
        self.pending_raw=None;self.last_write_result=None;self.tail_reserved=False;self.ready_eof=False
        try:
            self.meter.charge('work_units',bounded_size(ticket)+bounded_size(ticket_pin))
            validate_type('WorkerTicket',ticket);validate_type('Pin',ticket_pin)
            self.meter.charge('retained_bytes',bounded_size(ticket))
            need(pin(encode(ticket))=={k:ticket_pin[k]for k in ('bytes','sha256')},'exact complete earlier ticket bytes')
            self.cap=integer(ticket['max_frame_bytes'],1)
            need(self.cap<=268435456,'same finite existing frame convention')
            need(self.cap+8<=self.meter.limits['read_bytes']and self.cap+8<=self.meter.limits['write_bytes']and
                 19*self.cap+4168<=self.meter.limits['retained_bytes']and
                 64*self.cap+8192<=self.meter.limits['work_units'],
                 'whole frame and fixed logical parse/allocation reservations fit earlier allowance')
            self.ticket=ticket;self.ticket_pin=ticket_pin
            self.run_deadline=integer(ticket['original_run_deadline_ns'],1)
            need(self.run_deadline<=ticket['original_evidence_deadline_ns']<=self.meter.deadline_ns,
                 'original run/evidence cutoffs, no transport renewal')
        except BaseException as error:self._fail(error,'construct');raise
    def _fail(self,error,site):
        if self.first_raw is None:self.first_raw=error
        self.failed=True;self.pipes.retain(error,'frame_'+site)
    def _check(self):
        need(not self.failed,'no transport continuation after original failure')
        self.meter.check();now=time.monotonic_ns();integer(now)
        need(now<self.run_deadline,'unchanged original parked run cutoff')
    def _reserve_read(self,size):
        self.meter.charge('read_bytes',size)
        self.meter.charge('retained_bytes',size+64)
        self.meter.charge('work_units',64*size+4096)
    def read_step(self):
        attempted=False;returned=False
        try:
            self._check();need(self.current is None,'take the actual prior complete frame before another read')
            need(len(self.received)<2,'exactly Ready followed by EntryAcknowledgement; no extra frame read')
            fd=self.pipes.require_live('ready_reader')
            if not self.header_reserved:
                self._reserve_read(8);self.header_reserved=True
            destination=self.header if len(self.header)<8 else self.body
            remaining=8-len(self.header)if destination is self.header else self.body_size-len(self.body)
            need(remaining>0,'never issue a zero-size read or completion probe')
            attempted=True
            try:raw=os.read(fd,min(65536,remaining))
            except BlockingIOError:return 'pending'
            self.pending_raw=raw;returned=True
            need(type(raw)is bytes and 0<len(raw)<=remaining,'original complete frame cannot contain premature EOF or oversized read')
            self.read_known+=len(raw)
            destination.extend(raw)
            self.pending_raw=None
            if destination is self.header and len(self.header)==8:
                size=struct.unpack('>Q',self.header)[0]
                need(0<size<=self.cap,'positive finite body length admitted before body read/allocation')
                self._reserve_read(size);self.body_reserved=True;self.body_size=size
                return 'progress'
            if destination is self.body and len(self.body)==self.body_size:
                # Raw conversion, canonical re-encoding and the same bounded
                # logical metadata representation used by the other source
                # readers are admitted before parse/allocation. This is not a
                # claim to measure physical Python RSS; whole memory remains
                # independently enforced/qualified.
                self.meter.charge('retained_bytes',18*self.body_size+4096)
                raw_body=bytes(self.body);value=parse(raw_body,self.cap)
                need(encode(value)==raw_body,'exact canonical original control JSON')
                kind=('Ready','EntryAcknowledgement')[len(self.received)];validate_type(kind,value)
                if kind=='Ready':
                    need(same(value['ticket'],self.ticket_pin)and value['launch_nonce']==self.ticket['launch_nonce'],
                         'Ready binds this exact earlier ticket/nonce, no self-asserted worker identity')
                else:
                    need(self.release_complete,'ACK cannot precede actual complete Release write')
                    need({k:value['release'][k]for k in ('bytes','sha256')}==self.release_identity and
                         same(value['start_binding'],self.release_body['start_binding'])and
                         same(value['worker_request'],self.release_body['worker_request']),
                         'ACK joins the exact outgoing original Release body/request/start')
                    # Exact StartBinding/worker/request joins belong to the
                    # source-owned H admission caller; shape is not admission.
                self.current={'kind':kind,'body':value,'raw':raw_body,'identity':pin(raw_body)}
                return 'complete'
            return 'progress'
        except BaseException as error:
            if attempted and not returned:
                self.read_extent_unknown=True
            self._fail(error,'read');raise
    def take(self):
        try:
            self._check();need(self.current is not None,'actual fully captured frame required')
            result=self.current;self.received.append(result)
            self.current=None;self.header=bytearray();self.body=bytearray();self.body_size=None
            self.header_reserved=False;self.body_reserved=False
            return result
        except BaseException as error:self._fail(error,'take');raise
    def begin_release(self,release):
        try:
            self._check();need(not self.release_attempted,'one original Release attempt including failed validation')
            self.release_attempted=True
            need(len(self.received)==1 and self.received[0]['kind']=='Ready','actual Ready frame precedes Release')
            self.meter.charge('work_units',bounded_size(release));validate_type('Release',release)
            need(same(release['ticket'],self.ticket_pin)and release['launch_nonce']==self.ticket['launch_nonce'],
                 'same original ticket and nonce in outgoing Release')
            # The complete original source caller must provide the actual
            # captured Ready descriptor. Its bytes must match this observation.
            need({k:release['ready'][k]for k in ('bytes','sha256')}==self.received[0]['identity'],
                 'Release refers to this actual original Ready body')
            bound=bounded_size(release)
            self.meter.charge('retained_bytes',bound+8)
            raw=encode(release);need(0<len(raw)<=self.cap,'whole original Release body within selected cap')
            self.meter.charge('write_bytes',len(raw)+8)
            self.release_body=release;self.release_identity=pin(raw)
            self.outgoing=struct.pack('>Q',len(raw))+raw
            return len(self.outgoing)
        except BaseException as error:self._fail(error,'release_prepare');raise
    def write_step(self):
        attempted=False;returned=False
        try:
            self._check();need(self.outgoing is not None and not self.release_complete,'actual uncompleted original Release frame')
            fd=self.pipes.require_live('release_writer');remaining=len(self.outgoing)-self.sent
            need(remaining>0,'positive original pending write extent')
            # memoryview avoids allocating an unreserved repeated suffix.
            attempted=True
            try:n=os.write(fd,memoryview(self.outgoing)[self.sent:])
            except BlockingIOError:return 'pending'
            self.last_write_result=n;returned=True
            need(type(n)is int and 0<n<=remaining,'known positive original partial write')
            self.sent+=n;self.write_known+=n
            if self.sent==len(self.outgoing):self.release_complete=True;return 'complete'
            return 'progress'
        except BaseException as error:
            if attempted and not returned:self.write_extent_unknown=True
            self._fail(error,'release_write');raise
    def finish_ready_stream_step(self):
        attempted=False;returned=False
        try:
            self._check();need(len(self.received)==2 and self.current is None and self.release_complete and not self.ready_eof,
                               'actual Ready/ACK and outgoing Release before final channel closure')
            fd=self.pipes.require_live('ready_reader')
            if not self.tail_reserved:self._reserve_read(1);self.tail_reserved=True
            attempted=True
            try:raw=os.read(fd,1)
            except BlockingIOError:return 'pending'
            self.pending_raw=raw;returned=True
            need(type(raw)is bytes and raw==b'','extra/trailing frame bytes forbid channel completion')
            self.pending_raw=None;self.ready_eof=True
            return 'complete'
        except BaseException as error:
            if attempted and not returned:self.read_extent_unknown=True
            self._fail(error,'trailing_or_eof');raise
    @property
    def transport_complete(self):
        return (not self.failed and len(self.received)==2 and self.release_complete and self.ready_eof and
                not self.read_extent_unknown and not self.write_extent_unknown and self.pending_raw is None)
