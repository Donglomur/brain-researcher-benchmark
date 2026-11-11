"""Concrete Linux FD and AF_UNIX operations for a fixed backend owner.

BUILD ONLY: definitions do not perform IO on import. Actual callers must possess
the source-owned backend handle and selected native context. There is no OS
provider/callback argument. Tests replace module syscall leaves, never authority.
"""
import errno
import os
import select
import socket
import stat
import struct
import time
from .common import need
from .backend_protocol import response_header


class DescriptorSlot:
    """One acquisition and one relinquishment; no ambiguous-close retry."""
    __slots__=('custody','role','fd','socket','acquire_entered','close_entered','closed',
               'unknown','raw_first','raw_secondaries','identity','nonblocking')
    def __init__(self,custody,role):
        self.custody=custody;self.role=role;self.fd=None;self.socket=None
        self.acquire_entered=False;self.close_entered=False;self.closed=False
        self.unknown=False;self.raw_first=None;self.raw_secondaries=[]
        self.identity=None;self.nonblocking=False
        custody.slots.append(self) # Registered before any syscall.

    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.unknown=True;self.custody.retain(error,self.role)

    def openat(self,parent,name,flags,mode=0o600):
        need(not self.acquire_entered and self.fd is None,'one original descriptor acquisition')
        need(type(parent) is int and parent>=0 and type(name) is str and name not in ('','.', '..') and
             '/' not in name and '\0' not in name,'exact anchored one-component child')
        self.acquire_entered=True
        try:
            self.custody.work()
            self.fd=os.open(name,flags|os.O_NOFOLLOW|os.O_CLOEXEC,mode,dir_fd=parent)
            # Actual fd is owned before fstat/nonblocking/identity observation.
            a=os.fstat(self.fd);self.identity=(a.st_dev,a.st_ino,a.st_mode)
            return self
        except BaseException as error:self.retain(error);raise

    def unix_socket(self):
        need(not self.acquire_entered,'one original socket acquisition')
        self.acquire_entered=True
        try:
            self.custody.work()
            self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM|socket.SOCK_CLOEXEC)
            self.fd=self.socket.fileno()
            self.socket.setblocking(False);self.nonblocking=True
            return self
        except BaseException as error:self.retain(error);raise

    def fixed_proc_root(self):
        need(self.role=='proc' and not self.acquire_entered,'one fixed source-selected proc root acquisition')
        self.acquire_entered=True
        try:
            self.custody.work()
            self.fd=os.open('/proc',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            s=os.fstat(self.fd);self.identity=(s.st_dev,s.st_ino,s.st_mode)
            need(stat.S_ISDIR(s.st_mode),'actual Linux proc directory')
            return self
        except BaseException as error:self.retain(error);raise

    def set_nonblocking(self):
        try:
            need(self.fd is not None and not self.close_entered,'owned live descriptor')
            self.custody.work();os.set_blocking(self.fd,False);self.nonblocking=True
        except BaseException as error:self.retain(error);raise

    def close(self):
        if self.close_entered:return self.closed
        self.close_entered=True
        # Clear both integer and object slots BEFORE ambiguous close. Never
        # subsequently close the recycled integer after socket.close raises.
        fd,sock=self.fd,self.socket;self.fd=None;self.socket=None
        try:
            if sock is not None:sock.close()
            elif fd is not None:os.close(fd)
            elif self.acquire_entered:self.unknown=True;return False
            self.closed=True;return True
        except BaseException as error:self.retain(error);return False


class NativeIOCustody:
    """Actual original resource/error ownership, without a replacement budget."""
    def __init__(self,handle):
        from .backend_lifecycle import BackendAttemptHandle
        need(type(handle) is BackendAttemptHandle,'actual original backend handle')
        self.handle=handle;self.meter=handle.meter;self.slots=[]
        self.raw_first=None;self.raw_secondaries=[];self.last_time=None
        self.known_read=0;self.known_written=0;self.unknown_read=False;self.unknown_write=False

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.handle.retain(error,'native_io_'+site)

    def work(self,amount=4096):self.meter.charge('work_units',amount)

    def mark_unknown(self):self.handle.unknown_native()

    def original_worker_identity(self):return self.handle.ack_body['worker_identity']

    def now(self,deadline):
        self.meter.check();now=time.monotonic_ns()
        need(type(now) is int and self.handle.ack_body['original_start_ns']<=now<=deadline and
             (self.last_time is None or now>=self.last_time),'same original nondecreasing Linux monotonic clock')
        self.last_time=now;return now

    def slot(self,role):
        need(role in ('http','stdout','stderr','pidfd','workspace','control','group','proc',
                      'executable','model','template','tokenizer','renderer','artifact_root','artifact_directory'),
             'fixed source-owned descriptor role')
        self.work();self.meter.charge('retained_bytes',512)
        return DescriptorSlot(self,role)

    def wait_ready(self,slot,deadline,write=False):
        need(slot.fd is not None and slot.nonblocking and not slot.close_entered,'proven live nonblocking descriptor')
        while True:
            now=self.now(deadline);need(now<deadline,'no readiness wait after original cutoff')
            self.work();timeout=min(.05,(deadline-now)/1000000000)
            try:
                r,w,x=select.select([] if write else [slot.fd],[slot.fd] if write else [],[slot.fd],timeout)
            except InterruptedError:continue # Interrupted readiness, not a repeated physical transfer.
            need(not x,'original descriptor exceptional condition')
            if (w if write else r):return

    def recv(self,slot,n,deadline):
        need(type(n) is int and n>0 and slot.nonblocking,'positive admitted nonblocking transfer; no zero-budget probe')
        self.now(deadline)
        self.meter.charge('read_bytes',n);self.meter.charge('retained_bytes',n)
        try:
            data=slot.socket.recv(n) if slot.socket is not None else os.read(slot.fd,n)
        except BlockingIOError:return None # Full original reservation remains charged.
        except BaseException as error:
            self.unknown_read=True;self.retain(error,'read');raise
        need(type(data) is bytes and len(data)<=n,'actual bounded syscall return')
        self.known_read+=len(data) # Acknowledged consumption precedes fallible final clock.
        return data

    def send_all(self,slot,wire,deadline):
        need(type(wire) is bytes and slot.socket is not None and slot.nonblocking,'fixed complete source-owned request bytes')
        offset=0
        while offset<len(wire):
            self.wait_ready(slot,deadline,write=True);n=min(65536,len(wire)-offset)
            self.meter.charge('write_bytes',n);self.meter.charge('retained_bytes',n)
            try:sent=slot.socket.send(wire[offset:offset+n])
            except BlockingIOError:continue
            except BaseException as error:
                self.unknown_write=True;self.retain(error,'write');raise
            need(type(sent) is int and 0<sent<=n,'actual positive bounded socket write')
            offset+=sent;self.known_written+=sent
            self.now(deadline)
        return offset

    def connect(self,slot,path,expected_pid,expected_uid,deadline):
        need(type(path) is str and path.startswith('/') and path.endswith('/backend.sock') and '\0' not in path,
             'exact owned absolute Unix backend path')
        need(slot.socket is not None and slot.nonblocking,'actual owned socket before connect')
        try:
            self.now(deadline);self.work()
            code=slot.socket.connect_ex(path) # Exactly one connect attempt.
            need(code in (0,errno.EINPROGRESS,errno.EAGAIN,errno.EWOULDBLOCK),'original Unix connect result')
            if code:
                self.wait_ready(slot,deadline,write=True)
                code=slot.socket.getsockopt(socket.SOL_SOCKET,socket.SO_ERROR)
                need(code==0,'original completed Unix connect, no reconnect')
            self.meter.charge('read_bytes',12);self.meter.charge('retained_bytes',12)
            raw=slot.socket.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12)
            need(type(raw) is bytes and len(raw)==12,'actual Linux ucred extent')
            pid,uid,gid=struct.unpack('3i',raw)
            need(pid==expected_pid and uid==expected_uid and gid>=0,'actual expected server process/uid peer')
            self.now(deadline);return pid,uid,gid
        except BaseException as error:self.retain(error,'connect_peer');raise


class HttpAttempt:
    """Retains acknowledged raw prefixes even if a later clock or parse fails."""
    def __init__(self,custody,endpoint,ordinal,deadline):
        self.custody=custody;self.endpoint=endpoint;self.ordinal=ordinal;self.deadline=deadline
        self.slot=None;self.started=None;self.finished=None;self.header=b'';self.body=b''
        self.parts=[];self.known_wire_bytes=0;self.status=None;self.declared=None
        self.raw_first=None;self.raw_secondaries=[];self.sent=0;self.complete=False
        self.entered=False;self.closed=False
        self.peer_credentials=None;self.write_origin=None

    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.custody.retain(error,'http')

    def run(self,path,pid,uid,wire,profile):
        need(not self.entered,'one original HTTP attempt, no retry')
        self.entered=True;c=self.custody
        header_cap=min(profile['limits']['maximum_header_bytes'],65536)
        body_cap=min(profile['limits']['maximum_response_bytes'],1048576)
        try:
            # Header/body, hex expansion and parser materialization all paid
            # before any request/response effect, from the same original arm.
            c.meter.charge('retained_bytes',8*(header_cap+body_cap+len(wire)))
            c.meter.charge('work_units',64*(header_cap+body_cap+len(wire)))
            need(8*(header_cap+body_cap+len(wire))<=profile['limits']['maximum_pending_retained_bytes'],
                 'whole pending transport/parser footprint fits selected profile')
            self.started=c.now(self.deadline);self.slot=c.slot('http');self.slot.unix_socket()
            self.peer_credentials=c.connect(self.slot,path,pid,uid,self.deadline)
            self.write_origin=c.known_written;self.sent=c.send_all(self.slot,wire,self.deadline)
            prefix=b''
            while self.declared is None:
                remaining=header_cap-len(prefix);need(remaining>0,'no header EOF probe beyond original cap')
                c.wait_ready(self.slot,self.deadline);part=c.recv(self.slot,min(4096,remaining),self.deadline)
                if part is None:continue
                self.parts.append(part);self.known_wire_bytes+=len(part)
                need(part!=b'','premature header EOF')
                prefix+=part;self.header=prefix # Retain before parser/clock may fail.
                marker=prefix.find(b'\r\n\r\n')
                if marker>=0:
                    self.header=prefix[:marker+4];self.body=prefix[marker+4:]
                    self.status,self.declared=response_header(self.header,profile)
                    need(len(self.body)<=self.declared,'extra bytes in already observed header/body read')
                c.now(self.deadline)
            while len(self.body)<self.declared:
                remaining=self.declared-len(self.body)
                c.wait_ready(self.slot,self.deadline);part=c.recv(self.slot,min(65536,remaining),self.deadline)
                if part is None:continue
                self.parts.append(part);self.known_wire_bytes+=len(part)
                need(part!=b'','premature declared-body EOF')
                self.body+=part;c.now(self.deadline)
            need(len(self.body)==self.declared and self.known_wire_bytes==len(self.header)+len(self.body),
                 'exact actual observed complete framing, no extra zero-allowance read')
            self.finished=c.now(self.deadline);self.complete=True
        except BaseException as error:self.retain(error)
        finally:
            if self.write_origin is not None:self.sent=c.known_written-self.write_origin
            if self.slot is not None:
                self.closed=self.slot.close()
                if not self.closed:
                    self.complete=False
                    if self.slot.raw_first is not None:self.retain(self.slot.raw_first)
            try:c.now(self.deadline)
            except BaseException as error:self.complete=False;self.retain(error)
        if self.raw_first is not None:raise self.raw_first
        return self
