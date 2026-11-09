"""Continuous actual pipe/wait collection; exact nonblocking framed exchanges."""
import base64
import errno
import hashlib
import os
import selectors
import socket
import stat
import struct
import subprocess
from ach_resource_common import (require, fields, integer, body_pin, bounded_encode,
    bounded_decode, collect_errors, close_all, peer_identity)
from ach_resource_admission import verify_peer


class StreamPump:
    def __init__(self, root_fd, root_path, selected, clock, endpoints, audit, limits):
        self.root, self.root_path, self.selected, self.clock = root_fd, root_path, selected, clock
        self.endpoints, self.audit, self.limits = endpoints, audit, limits
        self.selector = selectors.DefaultSelector(); self.jobs = {}; self.records = {}; self.files = {}
        self.finished = {}; self.closed = False

    def attach(self, role, job):
        require(role not in self.jobs and type(job['process']) is subprocess.Popen, 'actual unique parent-owned Popen')
        self.jobs[role] = job
        for name in ('stdout','stderr'):
            stream = getattr(job['process'], name); fd = stream.fileno()
            require(stat.S_ISFIFO(os.fstat(fd).st_mode), 'actual owned full process pipe')
            os.set_blocking(fd, False)
            key = (role,name); endpoint = job['blueprint'][name+'_endpoint']
            attempt = self.endpoints.begin(endpoint)
            record = {'bytes':0,'retained_bytes':0,'digest':hashlib.sha256(),'retained_digest':hashlib.sha256(),
                'eof':False,'durable':False,'pending_block_base64':None,'pending_block_retained_bytes':0,
                'endpoint_attempt':attempt,'output':role+'-'+name+'.log'}
            self.records[key] = record
            self.files[key] = os.open(record['output'], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400, dir_fd=self.root)
            self.selector.register(fd, selectors.EVENT_READ, ('stream',role,name))

    def attach_pidfd(self, role):
        self.selector.register(self.jobs[role]['pidfd'], selectors.EVENT_READ, ('exit',role))

    def consume(self, role, name, raw, phase):
        """Actual read return is committed before any limit/write failure."""
        key = (role,name); record = self.records[key]
        if not raw:
            record['eof'] = True
            os.fsync(self.files[key]); os.fsync(self.root); record['durable'] = True
            self.endpoints.end(record['endpoint_attempt']); record['endpoint_attempt'] = None
            return
        record['bytes'] += len(raw); record['digest'].update(raw)
        record['pending_block_base64'] = base64.b64encode(raw).decode('ascii'); record['pending_block_retained_bytes'] = 0
        self.audit.returned('pipe_read_bytes',len(raw)); first = None
        try:
            self.endpoints.charge(record['endpoint_attempt'],'read_bytes',len(raw))
            self.audit.charge({'data_read_bytes':len(raw),'write_bytes':len(raw),'log_bytes':len(raw)}, 'actual returned role stream retained in full', phase)
            require(record['bytes'] <= self.limits['stream_bytes'], 'full stream bound, no truncated success')
        except BaseException as error: first = error
        def retain():
            done = 0
            while done < len(raw):
                self.clock.tick(phase); n = os.write(self.files[key], memoryview(raw)[done:])
                require(type(n) is int and 0 < n <= len(raw)-done, 'actual positive stream write')
                record['retained_digest'].update(memoryview(raw)[done:done+n]); done += n
                record['retained_bytes'] += n; record['pending_block_retained_bytes'] += n
                self.audit.returned('write_bytes',n)
            record['pending_block_base64'] = None; record['pending_block_retained_bytes'] = 0
        first = collect_errors([('retain actual returned stream prefix',retain)],first)
        if first is not None: raise first

    def once(self, phase, maximum_wait_ns):
        now = self.clock.tick(phase)
        timeout = max(0,min(integer(maximum_wait_ns),getattr(self.clock,phase)-now))/1e9
        for key,_ in self.selector.select(timeout):
            if key.data[0] == 'exit':
                role = key.data[1]; job = self.jobs[role]
                result = os.waitid(os.P_PIDFD, job['pidfd'], os.WEXITED | os.WNOWAIT | os.WNOHANG)
                require(result is not None and result.si_pid == job['process'].pid, 'actual source-owned waitid event')
                self.finished[role] = {'pid':result.si_pid,'code':result.si_code,'status':result.si_status,
                    'natural_zero':result.si_code == os.CLD_EXITED and result.si_status == 0,
                    'observed_ns':self.clock.tick(phase)}
                # Preserve wait evidence before reaping, and join the actual Popen status.
                returned = job['process'].wait(timeout=0)
                expected = result.si_status if result.si_code == os.CLD_EXITED else -result.si_status
                require(returned == expected, 'actual Popen and waitid return join')
                self.finished[role]['popen_returncode'] = returned
                self.selector.unregister(key.fd)
            else:
                _,role,name = key.data; record = self.records[(role,name)]
                remaining = self.limits['stream_bytes'] - record['bytes']
                raw = os.read(key.fd,min(self.limits['block_bytes'],max(1,remaining+1)))
                self.consume(role,name,raw,phase)
                if not raw: self.selector.unregister(key.fd)
        self.clock.tick(phase)

    def ready(self, fd, phase):
        os.set_blocking(fd,False); raw = bytearray()
        while True:
            self.once(phase,self.limits['poll_ns'])
            try: block = os.read(fd,2-len(raw))
            except BlockingIOError: continue
            if not block:
                require(bytes(raw) == b'R', 'exact actual readiness byte and EOF'); return
            raw.extend(block); self.audit.returned('readiness_pipe_read_bytes',len(block))
            self.audit.charge({'data_read_bytes':len(block)},'actual readiness pipe return',phase)
            require(bytes(raw) == b'R', 'one source-owned readiness byte only')

    def complete(self, role):
        return role in self.finished and all(self.records.get((role,name),{}).get('eof') for name in ('stdout','stderr'))

    def wait_role(self, role, phase):
        while not self.complete(role): self.once(phase,self.limits['poll_ns'])
        require(self.finished[role]['natural_zero'], 'actual role failed; full streams retained')
        require(all(self.records[(role,name)]['durable'] for name in ('stdout','stderr')), 'both full streams durable, including empty')
        return self.finished[role]

    def descriptors(self, role=None):
        return {r+'/'+name:{'path':self.root_path+'/'+row['output'],'bytes':row['bytes'],
            'sha256':row['digest'].hexdigest(),'retained_bytes':row['retained_bytes'],
            'retained_sha256':row['retained_digest'].hexdigest(),'eof':row['eof'],'durable':row['durable'],
            'pending_block_base64':row['pending_block_base64'],'pending_block_retained_bytes':row['pending_block_retained_bytes']}
            for (r,name),row in self.records.items() if role is None or r == role}

    def close(self, primary=None):
        if self.closed: return
        self.closed = True; operations = [('capture selector close',self.selector.close)]
        for key,fd in list(self.files.items()):
            del self.files[key]
            operations += [('partial stream sync',lambda fd=fd:os.fsync(fd)),('stream descriptor close',lambda fd=fd:os.close(fd))]
        for row in self.records.values():
            attempt = row['endpoint_attempt']; row['endpoint_attempt'] = None
            if attempt is not None: operations.append(('failed stream endpoint disposition',lambda attempt=attempt:self.endpoints.end(attempt,failed=True)))
        close_all(operations,primary)


class FramedExchange:
    """Concrete AF_UNIX request, pumped alongside process streams; no result callback."""
    def __init__(self,pump,context,endpoints,selected,request,phase):
        fields(selected,('socket','peer','endpoint'), 'exact installed service transport')
        self.pump,self.context,self.endpoints,self.selected,self.request,self.phase = pump,context,endpoints,selected,request,phase
        self.socket = None; self.attempt = None; self.received = bytearray(); self.sent = 0; self.raw_reply = None
        self.record = {'request':request,'reply':None,'sent_bytes':0,'received_bytes':0,'complete':False}

    def run(self):
        first = None; result = None
        try:
            self.attempt = self.endpoints.begin(self.selected['endpoint'])
            body = bounded_encode(self.request,self.context.profile['encoding_limits']); wire = struct.pack('!Q',len(body))+body
            self.context.audit.charge({'source_read_bytes':len(wire)}, 'framed metadata request serialization', self.phase)
            self.socket = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); self.socket.setblocking(False)
            code = self.socket.connect_ex(self.selected['socket'])
            require(code in (0,errno.EINPROGRESS,errno.EAGAIN,errno.EWOULDBLOCK), 'actual nonblocking Unix connection')
            poller = selectors.DefaultSelector(); polling_error = None
            try:
                poller.register(self.socket,selectors.EVENT_READ|selectors.EVENT_WRITE)
                connected = False; needed = None
                while True:
                    self.pump.once(self.phase,self.pump.limits['poll_ns'])
                    events = poller.select(0)
                    if not events: continue
                    if not connected:
                        require(self.socket.getsockopt(socket.SOL_SOCKET,socket.SO_ERROR) == 0,'actual connected service socket')
                        self.context.audit.charge({'source_read_bytes':16*(self.context.profile['reader_limits']['file_bytes']+1)},'live service peer verification bound',self.phase)
                        verify_peer(peer_identity(self.socket),self.selected['peer'],self.context.profile,self.context.clock,self.phase)
                        connected = True
                    if self.sent < len(wire):
                        try: n = self.socket.send(memoryview(wire)[self.sent:self.sent+self.pump.limits['block_bytes']])
                        except BlockingIOError: continue
                        require(n > 0, 'actual positive framed send')
                        self.sent += n; self.record['sent_bytes'] = self.sent
                        self.endpoints.charge(self.attempt,'write_bytes',n)
                    else:
                        if needed is None and len(self.received) >= 8:
                            needed = 8+struct.unpack('!Q',self.received[:8])[0]
                            require(needed-8 <= self.context.profile['encoding_limits']['bytes'], 'whole framed reply before allocation')
                        if needed is not None and len(self.received) == needed: break
                        remaining = 8-len(self.received) if needed is None else needed-len(self.received)
                        try: raw = self.socket.recv(min(self.pump.limits['block_bytes'],remaining))
                        except BlockingIOError: continue
                        require(raw,'full framed service response required')
                        self.received.extend(raw); self.record['received_bytes'] = len(self.received)
                        self.endpoints.charge(self.attempt,'read_bytes',len(raw))
                        self.context.audit.charge({'source_read_bytes':len(raw)}, 'actual framed reply read', self.phase)
                self.raw_reply = bytes(self.received[8:]); result = bounded_decode(self.raw_reply,self.context.profile['encoding_limits'])
                self.record.update(reply=result,raw_reply_base64=base64.b64encode(self.raw_reply).decode('ascii'),complete=True)
            except BaseException as error: polling_error = error; raise
            finally: close_all([('framed exchange selector close',poller.close)],polling_error)
        except BaseException as error: first = error
        operations = [] if self.socket is None else [('framed exchange socket close',self.socket.close)]
        if self.attempt is not None: operations.append(('framed endpoint disposition',lambda:self.endpoints.end(self.attempt,failed=first is not None)))
        first = collect_errors(operations,first)
        if first is not None:
            self.record['received_prefix_base64'] = base64.b64encode(self.received).decode('ascii')
            self.record['failure_type'] = type(first).__name__; first.n079_exchange_prefix = self.record; raise first
        return result


def parse_terminal(raw, role, source_pin, encoding):
    # Original libraries may log before the terminal line; retain the complete
    # stream separately. Exactly one typed terminal is required, at its last line.
    require(type(raw) is bytes and raw.endswith(b'\n'), 'complete final role terminal newline')
    found = []
    for i,line in enumerate(raw.splitlines()):
        try: value = bounded_decode(line,encoding)
        except (ValueError,UnicodeError): continue
        if type(value) is dict and value.get('schema') == 'n079_actual_role_return_v1': found.append((i,value))
    require(len(found) == 1 and found[0][0] == len(raw.splitlines())-1, 'one final source-owned role terminal line')
    result = found[0][1]
    fields(result,('schema','status','role','result','source_pin','budget_prefix','endpoint_record','configuration_custody'), 'complete actual terminal schema')
    require(result['configuration_custody'] == 'requires_actual_outer_release_gate_bootstrap_and_return_join',
            'terminal retains the exact detached custody requirement, never self-admission')
    require(result['status'] == 'complete' and result['role'] == role and result['source_pin'] == source_pin,
            'actual role/source/complete return join')
    return result
