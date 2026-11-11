"""Actual fixed worker endpoint over the retained original physical import.

No FD/provider/clock arguments. Every packet uses the original parent PIDFD,
anchored proc directory, credentials and deadline. Local logical counters are
cursors inside the original H-prepaid control vector, never fresh allowances.
Unknown transfer/close effects poison the owner; datagrams are never replayed.
"""
import os
import select
import socket
import struct
import time
from .common import need,same
from .backend_worker_bootstrap_physical_v3 import _parse_parent_stat_v3
from .worker_context_records_v3 import body

_ENDPOINT=object()
class WorkerNativeChannelEndpoint:
    def __init__(self,token,admission):
        from .worker_installed_expectation_v1 import WorkerPreHelloAdmissionV3
        need(token is _ENDPOINT and type(admission)is WorkerPreHelloAdmissionV3,'fixed actual installed admission only')
        admission.require_original();need(admission.endpoint is None,'one original application endpoint')
        self.admission=admission;self.physical=admission.physical;d=self.physical.descriptor
        self.descriptor=d;self.reservation=d['reservation_body'];self.limits=dict(self.reservation['arm_reserved'])
        self.maximum_packet=self.reservation['packet_limit'];self.maximum_sequences=self.reservation['maximum_sequences']
        self.maximum_logical_record=self.reservation['logical_record_limit']
        self.maximum_publications=self.maximum_sequences
        self.original_bootstrap_deadline=d['prehello_deadline_ns'];self.original_R=d['start_body']['R_ns']
        self.protocol=None;self.raw_first=None;self.secondaries=[];self.unknowns=set();self.events=[]
        self.used=dict.fromkeys(self.limits,0);self.used.update(read_bytes=self.physical.read_reserved,
            work_units=self.physical.work_used,retained_bytes=self.physical.retained_used)
        self.last_time=self.physical.last_time;self.closed=False;self.close_entered=False;self.source_check_attempts=0
        self.sent=0;self.received=0;self.send_attempts=0;self.receive_attempts=0;self.temporary=[];self.expected_grant=None;self.unexpected_rights=[]
        for key in self.used:need(self.used[key]<=self.limits[key],'retained initial prefix inside same original reserve')
        admission.endpoint=self
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.unknowns.add(site);self.physical.retain(error,'worker_endpoint_'+site)
    def _debit(self,dimension,amount):
        need(type(amount)is int and amount>=0 and self.used[dimension]+amount<=self.limits[dimension],
             'whole source operation inside original prepaid control vector')
        self.used[dimension]+=amount
    def reserve_source_check(self,extent):
        need(self.source_check_attempts<16*self.maximum_sequences,'full preflighted installed-source validation occurrence bound')
        self.source_check_attempts+=1
        self._debit('work_units',extent*128+4096);self._debit('retained_bytes',extent*16+4096)
    def require_original(self):
        if self.raw_first is not None:raise self.raw_first
        try:
            need(self.admission.endpoint is self and not self.close_entered and self.physical.channel.fd==198,
                 'same original live private endpoint, no adopted integer replacement')
            self.admission.require_original();return self
        except BaseException as error:self.retain(error,'require_original');raise self.raw_first
    def _now(self,deadline):
        need(type(deadline)is int and deadline<=self.original_R,'unchanged actual original worker deadline')
        self._debit('work_units',1);self._debit('retained_bytes',32)
        value=time.monotonic_ns();self.events.append(('clock',value))
        need(type(value)is int and self.last_time<=value<=deadline,'same original monotonic time, no renewed clock')
        self.last_time=value;return value
    def now(self,deadline):
        try:self.require_original();return self._now(deadline)
        except BaseException as error:self.retain(error,'clock');raise self.raw_first
    def _parent(self,deadline):
        self._now(deadline);p=self.physical
        self._debit('work_units',8193*64+4096);self._debit('retained_bytes',8193*8+4096)
        self._debit('read_bytes',8194)
        live=select.select([p.pidfd.fd],[],[p.pidfd.fd],0);self.events.append(('parent_live',live))
        need(live==([],[],[]),'actual original parent PIDFD remains live')
        slot={'fd':None,'entered':False,'close_entered':False,'closed':False,'raw':None,'error':None}
        self.temporary.append(slot);slot['entered']=True
        try:
            slot['fd']=os.open('stat',os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=p.parent_proc.fd)
            raw=os.read(slot['fd'],8193);slot['raw']=raw
            need(type(raw)is bytes and 0<len(raw)<=8192,'bounded original anchored process stat prefix')
            eof=os.read(slot['fd'],1);slot['eof']=eof
            need(eof==b'','actual complete anchored stat EOF, no prefix success')
            fields=_parse_parent_stat_v3(raw,p.observed_parent_pid)
            start=fields['start_ticks']*1000000000//p.original_clock_ticks+self.descriptor['tick_to_monotonic_offset_ns']
            need(fields['state']not in ('Z','X','x')and start==self.descriptor['host']['start_monotonic_ns'],
                 'same original parent start/boot, no PID reuse')
            user=os.fstat(p.parent_proc.fd);self.events.append(('parent_user',user.st_uid))
            need(user.st_uid==p.peer_credentials[1],'same original parent UID')
        except BaseException as error:slot['error']=error;self.retain(error,'parent_observe')
        finally:
            if slot['fd']is not None:
                slot['close_entered']=True
                try:os.close(slot['fd']);slot['closed']=True
                except BaseException as error:self.retain(error,'parent_close')
        if self.raw_first is not None:raise self.raw_first
        live=select.select([p.pidfd.fd],[],[p.pidfd.fd],0);self.events.append(('parent_live_after',live))
        need(live==([],[],[]),'actual parent live after anchored observation');self._now(deadline)
    def _wait(self,write,deadline):
        now=self._now(deadline);sock=self.physical.channel.socket
        ready=select.select([]if write else[sock],[sock]if write else[],[sock],(deadline-now)/1000000000)
        self.events.append(('ready',ready));need(not ready[2]and (ready[1]if write else ready[0]),'original endpoint ready before fixed cutoff')
        self._now(deadline)
    def send(self,raw,maximum,deadline):
        try:
            self.require_original();need(type(raw)is bytes and 0<len(raw)<=maximum==self.maximum_packet,'same full admitted original packet')
            self._debit('write_bytes',len(raw));self._debit('work_units',maximum*64+4096)
            self._debit('retained_bytes',maximum*8+4096)
            while True:
                need(self.send_attempts<4096,'same finite physical send-attempt bound as original H')
                self.send_attempts+=1
                self._parent(deadline)
                try:count=self.physical.channel.socket.sendmsg([raw],[],socket.MSG_DONTWAIT|socket.MSG_NOSIGNAL)
                except BlockingIOError:self._wait(True,deadline);continue
                self.events.append(('send_return',count));self.sent+=count if type(count)is int and count>0 else 0
                need(type(count)is int and count==len(raw),'full original datagram; no partial replay')
                self._parent(deadline);return count
        except BaseException as error:self.retain(error,'send_unknown');raise self.raw_first
    def receive(self,maximum,deadline):
        try:
            self.require_original();need(maximum==self.maximum_packet,'same exact original packet cap')
            self._debit('read_bytes',maximum+1+12);self._debit('work_units',maximum*64+4096)
            self._debit('retained_bytes',maximum*8+4096)
            while True:
                need(self.receive_attempts<4096,'same finite physical receive-attempt bound as original H')
                self.receive_attempts+=1
                self._parent(deadline)
                try:result=self.physical.channel.socket.recvmsg(maximum+1,socket.CMSG_SPACE(12),socket.MSG_DONTWAIT|socket.MSG_CMSG_CLOEXEC)
                except BlockingIOError:self._wait(False,deadline);continue
                self.events.append(('recv_return',result));raw,anc,flags,address=result
                self.received+=len(raw)if type(raw)is bytes else 0
                # SCM_RIGHTS installs actual new worker descriptors even on
                # a refused packet. Register all returned occurrences first.
                for level,kind,data in anc:
                    if level==socket.SOL_SOCKET and kind==socket.SCM_RIGHTS:
                        need(type(data)is bytes,'actual returned rights bytes')
                        for index in range(0,len(data)-len(data)%4,4):
                            self.unexpected_rights.append({'fd':struct.unpack('i',data[index:index+4])[0],
                                'close_entered':False,'closed':False,'error':None})
                        need(len(data)%4==0,'complete returned rights integers')
                need(type(raw)is bytes and 0<len(raw)<=maximum and not flags&(socket.MSG_TRUNC|socket.MSG_CTRUNC),
                     'whole original packet and complete credentials; no consumed-prefix retry')
                need(len(anc)==1 and anc[0][0]==socket.SOL_SOCKET and anc[0][1]==socket.SCM_CREDENTIALS and
                     type(anc[0][2])is bytes and len(anc[0][2])==12,'one exact kernel credential, no foreign control FD')
                need(struct.unpack('3i',anc[0][2])==self.physical.peer_credentials,'same actual original parent per packet')
                self._parent(deadline);return raw
        except BaseException as error:
            self.retain(error,'receive_unknown');self.close_unexpected_rights_once();raise self.raw_first
    def close_unexpected_rights_once(self):
        for slot in self.unexpected_rights:
            if slot['close_entered']:continue
            slot['close_entered']=True
            try:os.close(slot['fd']);slot['closed']=True
            except BaseException as error:slot['error']=error;self.retain(error,'unexpected_right_close')
    def hello_body(self):
        self.require_original();return body('BootstrapHelloV3',bootstrap_fd=199,channel_fd=198,
            carrier_sha256=self.physical.digest,schema_version='four-native-context-v3',
            start_observation=self.descriptor['start_observation'])
    def verify_bootstrap_grant(self,grant):
        self.require_original();d=self.descriptor;s=d['start_body'];p=self.physical
        need(grant['context']==d['context']and grant['host']==d['host']and
             grant['worker']['pid']==p.observed_worker_pid and grant['worker']['boot_id']==p.boot and
             grant['channel_reservation']==d['reservation']and grant['mapping_source']==d['clock_mapping_source']and
             grant['boot_id']==p.boot and grant['clock_ticks']==p.original_clock_ticks and
             grant['tick_to_monotonic_offset_ns']==d['tick_to_monotonic_offset_ns'],
             'actual original inherited context/host/worker/clock/reservation grant inverse')
        need(all(grant[k]==s[k]for k in ('original_S_ns','J_ns','G_ns','R_ns','E_ns'))and
             s['original_S_ns']<=grant['issued_ns']<=s['J_ns'],'same earlier actual start and every unchanged cutoff')
        self.expected_grant=grant
    def verify_bootstrap_objects(self,objects):
        self.require_original();d=self.descriptor
        actual={x.kind:x for x in objects if x.kind!='NativeRootObservationV1'}
        for kind,field in [('BootstrapEntrySelectionV1','entry_selection'),('NativeContextPolicyV2','context_policy'),
                           ('ChannelBudgetReservationV1','reservation'),('ChannelOpenObservationV1','channel_open')]:
            need(actual[kind].pin==d[field],'same actual original earlier '+kind)
        need(actual['ChannelBudgetReservationV1'].body==d['reservation_body'],'full original reservation body unchanged')
        entry=actual['BootstrapEntrySelectionV1'].body;expected=self.admission.expected['entry_configuration']
        need(all(entry[k]==expected[k]for k in expected),'same independently installed complete worker entry')
        need(actual['NativeContextPolicyV2'].body['canonical_publisher_source']==self.require_canonical_publisher_source_v3(),
             'actual H policy inverse of independently installed publisher')
    def require_canonical_publisher_source_v3(self):
        self.require_original();return dict(self.admission.expected['canonical_publisher_source'])
    def close_all_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True
        self.close_unexpected_rights_once()
        try:self.closed=self.physical.close_all_once() and all(x['closed']for x in self.unexpected_rights)
        except BaseException as error:self.retain(error,'close');self.closed=False
        return self.closed

def fixed_worker_endpoint_v3():
    from .worker_installed_expectation_v1 import admit_fixed_worker_entry_v3
    admission=admit_fixed_worker_entry_v3()
    try:return WorkerNativeChannelEndpoint(_ENDPOINT,admission)
    except BaseException as error:
        admission.retain(error)
        try:admission.physical.close_all_once()
        except BaseException as later:admission.retain(later)
        raise admission.raw_first

def fixed_worker_context_v3():
    """Concrete no-argument installed entry → physical → semantic → Hello."""
    from .worker_context_v3 import start_worker_context
    endpoint=fixed_worker_endpoint_v3()
    try:return start_worker_context(endpoint)
    except BaseException as error:
        endpoint.retain(error,'bootstrap_context')
        endpoint.close_all_once()
        raise endpoint.raw_first
