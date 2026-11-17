"""Fixed two-pipe original ownership for the five parked CI worker stages.

An endpoint integer in a record is never authority. The private owner below
retains the actual pipe2 returns and fstat identities; launch/entry admission
and native isolation remain separate, required caller/qualification work.
"""
import os
import sys
import stat
import fcntl
from .common import Store,need,integer,relative,encode,bounded_size
from .precommit_records import validate_type
from .observer import HostObserver

ROLES=('ready_reader','ready_writer','release_reader','release_writer')
CHILD_ROLES=('ready_writer','release_reader')

class ParkedPipes:
    def __init__(self,host):
        need(type(host)is HostObserver,'actual independently admitted fixed H observer')
        self.host=host;self.meter=host.meter
        self.creation_attempted=False;self.publication_attempted=False
        self.fd={role:None for role in ROLES};self.original_fd={role:None for role in ROLES}
        self.identity={role:None for role in ROLES};self.closed={role:False for role in ROLES}
        self.close_attempted={role:False for role in ROLES}
        self.actual_returns=[];self.pending_actual_return=None
        self.unknown_creation_calls=set()
        self.first_raw=None;self.secondary_raw=[];self.unknown=set()
        self.call_pins=[];self.endpoint_pins={};self.relinquish_attempted=False
    def retain(self,error,site):
        if self.first_raw is None:self.first_raw=error
        elif self.first_raw is not error:self.secondary_raw.append(error)
        self.meter.own_error(error,'parked_pipe_'+site)
    def create(self):
        try:
            need(not self.creation_attempted,'one original pipe creation attempt')
            self.creation_attempted=True
            need(sys.platform=='linux'and hasattr(os,'pipe2'),'separately qualified Linux pipe2 required')
            flags=os.O_NONBLOCK|os.O_CLOEXEC
            for ordinal,roles in enumerate((ROLES[:2],ROLES[2:])):
                self.meter.check();self.meter.charge('work_units',1024);self.meter.charge('retained_bytes',512)
                # Keep the exact original return before validation/allocation.
                try:self.pending_actual_return=os.pipe2(flags)
                except BaseException as error:
                    self.unknown_creation_calls.add(ordinal)
                    self.retain(error,'create_call');raise
                pair=self.pending_actual_return
                need(type(pair)is tuple and len(pair)==2 and all(type(fd)is int and fd>=0 for fd in pair)and pair[0]!=pair[1],
                     'actual original two-endpoint tuple')
                for role,fd in zip(roles,pair):
                    need(fd not in [v for v in self.original_fd.values()if v is not None],
                         'original live endpoints cannot alias earlier pipe')
                    self.fd[role]=fd;self.original_fd[role]=fd
                self.actual_returns.append(pair);self.pending_actual_return=None
                for role in roles:self.identity[role]=self._observe(role)
            return self
        except BaseException as error:
            self.retain(error,'create');raise
    def _observe(self,role):
        self.meter.check();self.meter.charge('work_units',512)
        fd=self.fd[role];need(fd is not None and not self.close_attempted[role],'same owned original endpoint')
        observed=os.fstat(fd)
        need(stat.S_ISFIFO(observed.st_mode),'actual anonymous pipe endpoint')
        need(fcntl.fcntl(fd,fcntl.F_GETFD)&fcntl.FD_CLOEXEC and fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_NONBLOCK,
             'actual nonblocking close-on-exec endpoint flags')
        identity=[observed.st_dev,observed.st_ino,observed.st_mode]
        for item in identity:integer(item)
        return identity
    def require_live(self,role):
        try:
            need(role in ROLES and self.identity[role]is not None,'original endpoint identity exists')
            need(self._observe(role)==self.identity[role],'same original fstat identity, not a reused integer')
            return self.fd[role]
        except BaseException as error:
            self.retain(error,'identity');raise
    def child_pass_fds(self):
        try:
            need(self.first_raw is None and len(self.actual_returns)==2 and len(self.endpoint_pins)==4,
                 'complete actual two-pipe capture before launch inheritance')
            return tuple(self.require_live(role)for role in CHILD_ROLES)
        except BaseException as error:
            self.retain(error,'inheritance');raise
    def publish_observations(self,store,*,prefix,cap):
        try:
            need(not self.publication_attempted,'one original pipe observation publication')
            self.publication_attempted=True
            need(type(store)is Store and store.meter is self.meter,'same earlier H private output store')
            relative(prefix);integer(cap,1)
            need(self.first_raw is None and len(self.actual_returns)==2,'both actual creation calls completed')
            def publish(name,value):
                bound=bounded_size(value);self.meter.charge('work_units',bound);self.meter.charge('retained_bytes',bound)
                raw=encode(value);need(len(raw)<=cap,'complete earlier selected observation cap')
                expected=store.write(name,raw);self.meter.charge('retained_bytes',len(raw)+1)
                need(store.read(expected,cap,metadata=True)==raw,'actual complete pipe observation publication/readback')
                return expected
            for ordinal,pair in enumerate(self.actual_returns):
                body={'schema':'ci_original_pipe2_call_observation_v1','call_ordinal':ordinal,
                      'returned_endpoints':list(pair),'nonblocking':True,'close_on_exec':True,
                      'actual_owner':'H','observation_is_not_native_qualification':True}
                call_pin=publish(prefix+'_call_'+str(ordinal)+'.json',body);self.call_pins.append(call_pin)
                for role in ROLES[2*ordinal:2*ordinal+2]:
                    self.require_live(role)
                    row={'schema':'ci_childfd_v1','role':role,'descriptor_integer':self.fd[role],
                         'pipe_call_observation':call_pin,'tuple_ordinal':ROLES.index(role)%2,
                         'fstat_identity':list(self.identity[role]),'actual_owner':'H'}
                    validate_type('ChildFD',row)
                    self.endpoint_pins[role]=publish(prefix+'_'+role+'.json',row)
            return dict(self.endpoint_pins)
        except BaseException as error:
            self.retain(error,'publication');raise
    def close_role(self,role):
        need(role in ROLES and not self.close_attempted[role],'one original endpoint close attempt')
        self.close_attempted[role]=True
        fd=self.fd[role];self.fd[role]=None
        if fd is None:
            need(self.original_fd[role]is None,'no retry after ambiguous original close')
            self.closed[role]=True;return
        try:
            self.meter.check();self.meter.charge('work_units',256)
            need(self.identity[role]is not None,'original endpoint identity required before close')
            observed=os.fstat(fd)
            need([observed.st_dev,observed.st_ino,observed.st_mode]==self.identity[role]and stat.S_ISFIFO(observed.st_mode),
                 'never close a reused or unknown endpoint integer')
            os.close(fd);self.closed[role]=True
        except BaseException as error:
            self.unknown.add(role);self.retain(error,'close');raise
    def relinquish_child_copies(self,running):
        try:return self._relinquish_child_copies(running)
        except BaseException as error:
            self.retain(error,'relinquish');raise
    def _relinquish_child_copies(self,running):
        from .observer import RunningProcess
        need(not self.relinquish_attempted,'one actual inherited-end release attempt')
        self.relinquish_attempted=True
        need(type(running)is RunningProcess and running.owner is self.host and
             running.child is not None and running.record['spawn_acknowledged']is True,
             'actual original Popen return before H relinquishes child ends')
        need(getattr(running,'_parked_pipe_owner',None)is self,
             'same actual source-owned parked launch, not another live process')
        primary=None
        for role in CHILD_ROLES:
            try:self.close_role(role)
            except BaseException as error:
                if primary is None:primary=error
        if primary is not None:raise primary
    def close_all(self):
        primary=None
        for role in ROLES:
            if self.close_attempted[role]:continue
            try:self.close_role(role)
            except BaseException as error:
                if primary is None:primary=error
        if primary is not None:raise primary
