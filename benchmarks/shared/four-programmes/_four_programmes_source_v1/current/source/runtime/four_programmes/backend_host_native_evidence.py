"""Fixed independent H native observations for an original receiver/backend.

These functions contain real Linux operations. They are BUILD ONLY until the
complete root/source/native bootstrap gate is supplied and reviewed. A worker
publication is a claim to compare, never the observation itself.
"""
import os,select,stat
from pathlib import PurePosixPath
from .common import need,same
from .backend_capture import CapturedRecord
from .backend_native_boundary import BackendNativeOwner,HWorkerLaunchAdmission
from .backend_linux_io import DescriptorSlot
from .backend_linux_observations import read_kernel_fd,process_identity_from_observation,observe_namespace_links
from .backend_linux_host_observation import HostNativeIOCustody,observe_original_host_group_membership,resolve_original_host_threads
from .preparation_ownership import OwnedPreparationPath

class HBackendNativeEvidence:
    def __init__(self,view):
        from .backend_host_view import HBackendView
        need(type(view)is HBackendView,'actual registered H backend view');view.require_original()
        need(view.host_admission_owner is None,'one original independent H observation attempt')
        self.view=view;self.receiver=view.receiver;self.attempt=view.attempt;self.channel=self.receiver.channel
        self.io=None;self.slots=[];self.raw_first=None;self.secondaries=[]
        self.initialization_entered=False;self.initialization_complete=False
        self.closure_entered=False;self.closure_complete=False
        self.root=None;self.server_dir=None;self.pidfd=None;self.peer_slot=None
        self.server_identity=None;self.server_namespaces=None;self.worker_namespaces=None
        self.stat_before=None;self.stat_after=None;self.raw_peer=None;self.census=None;self.threads=None
        self.socket_stat=None;self.socket_identity=None;self.host_process=None;self.host_socket=None;self.host_peer=None
        self.host_observation=None;self.admission=None;self.shutdown_census=None;self.shutdown_threads=None
        self.server_exit_observed=False;self.socket_absent=False;self.close_entered=False;self.closed=False
        view.host_admission_owner=self
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.receiver.retain(error,'host_native_'+site)
    def require_original(self):
        self.view.require_original();need(self.view.host_admission_owner is self,'same registered H native observer')
    def _slot(self,role='proc'):
        need(role in ('proc','pidfd','host_peer'),'closed independent H observation roles')
        self.io.work();self.io.meter.charge('retained_bytes',512)
        slot=DescriptorSlot(self.io,role);self.slots.append(slot);return slot
    def _file(self,parent,name,maximum,deadline):
        slot=self._slot();slot.openat(parent.fd,name,os.O_RDONLY|os.O_NONBLOCK)
        return read_kernel_fd(slot,maximum,deadline)
    def _anchor(self,deadline):
        anchor=self.attempt.arm.control
        need(type(anchor)is OwnedPreparationPath and anchor.custody.owner is self.attempt.owner and
             anchor.condition==self.attempt.condition and anchor.fd is not None and anchor.identity is not None,
             'same original private control directory, never worker workspace/path')
        self.io.now(deadline);self.io.work();actual=os.fstat(anchor.fd);expected=anchor.identity
        need(stat.S_ISDIR(actual.st_mode) and (actual.st_dev,actual.st_ino,actual.st_uid)==
             (expected['device'],expected['inode'],expected['uid']) and stat.S_IMODE(actual.st_mode)==0o700,
             'unchanged actual original private control anchor')
        return anchor
    def _capture(self,name,kind,body):
        return self.receiver.activation.host_publisher.capture(
            'native_context/'+self.attempt.condition+'/'+name+'.json',kind,body)
    def observe_initialization(self):
        self.require_original();need(not self.initialization_entered,'one actual H initialization attempt')
        self.initialization_entered=True
        try:
            a=self.attempt;v=self.view;r=self.receiver;act=r.activation
            need(v.initialization is not None and v.base is not None,'actual earlier worker initialization/base captures')
            native=a.native_launch_admission
            need(type(native)is HWorkerLaunchAdmission and type(native.native)is BackendNativeOwner,
                 'actual original fixed native launch admission, not wire qualification')
            # The existing actual native issuer gate remains unavailable until
            # source qualification and complete V3 bootstrap are integrated.
            native.native.assert_worker_admission(native)
            self.io=HostNativeIOCustody(self.channel)
            self.io.meter=a.owner.host # Actual H observation uses original H share.
            init=v.initialization.body;base=v.base.body;claimed=init['server_identity']
            need(same(init['attempt'],v.base.pin) and same(init['worker_identity'],a.process.identity),
                 'same original worker and backend before independent observations')
            deadline=act.J;self.io.now(deadline)
            self.pidfd=self._slot('pidfd');self.pidfd.acquire_entered=True;self.io.work()
            try:self.pidfd.fd=os.pidfd_open(claimed['pid'],0)
            except BaseException as error:self.pidfd.retain(error);raise
            self.io.work();ready,_,_=select.select([self.pidfd.fd],[],[],0);need(not ready,'actual live original server pidfd')
            self.root=self._slot();self.root.fixed_proc_root()
            self.server_dir=self._slot();self.server_dir.openat(self.root.fd,str(claimed['pid']),os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
            self.stat_before=self._file(self.server_dir,'stat',8192,deadline)
            mapping=a.host.mapping;worker=a.process.identity
            identity,fields=process_identity_from_observation(self.stat_before,claimed['pid'],mapping['boot_id'],mapping,
                 act.context['launch_nonce']+'/server/0',a.pair.contract.backend['server_executable'],a.launch_ack.pin)
            need(fields['parent_pid']==worker['pid'] and same(identity,claimed),'actual server PID/start/parent/source, no reported identity substitution')
            self.server_namespaces=observe_namespace_links(self.server_dir.fd,self.io,deadline)
            wd=self._slot();wd.openat(self.root.fd,str(worker['pid']),os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
            worker_stat=self._file(wd,'stat',8192,deadline)
            worker_now,_=process_identity_from_observation(worker_stat,worker['pid'],mapping['boot_id'],mapping,
                worker['launch_nonce'],worker['source'],worker['parent_launch'])
            need(same(worker_now,worker),'same actual worker start during independent H observation')
            self.worker_namespaces=observe_namespace_links(wd.fd,self.io,deadline)
            need(same(self.server_namespaces,self.worker_namespaces),'actual selected same worker/server namespaces')
            self.census=observe_original_host_group_membership(self.io,deadline)
            self.threads=resolve_original_host_threads(self.io,self.census,deadline)
            pids={pid for row in self.census.passes[-1]for pid in row[3]}
            need(claimed['pid']in pids and worker['pid']in pids and not self.threads.unresolved,
                 'both actual processes in complete original group/thread census')
            anchor=self._anchor(deadline);self.io.work();self.socket_stat=os.stat('backend.sock',dir_fd=anchor.fd,follow_symlinks=False)
            observed=self.socket_stat;need(stat.S_ISSOCK(observed.st_mode) and observed.st_uid==anchor.identity['uid'],
                 'actual original anchored socket and user')
            self.peer_slot=self._slot('host_peer');self.peer_slot.unix_socket()
            path=str(PurePosixPath(str(anchor.store.root))/anchor.name/'backend.sock')
            self.raw_peer=self.io.connect(self.peer_slot,path,claimed['pid'],anchor.identity['uid'],deadline)
            self.io.work();after=os.stat('backend.sock',dir_fd=anchor.fd,follow_symlinks=False)
            need((after.st_dev,after.st_ino,after.st_uid,after.st_mode)==
                 (observed.st_dev,observed.st_ino,observed.st_uid,observed.st_mode),'same actual anchored socket throughout connection')
            self.stat_after=self._file(self.server_dir,'stat',8192,deadline)
            identity_after,after_fields=process_identity_from_observation(self.stat_after,claimed['pid'],mapping['boot_id'],mapping,
                 act.context['launch_nonce']+'/server/0',a.pair.contract.backend['server_executable'],a.launch_ack.pin)
            need(same(identity,identity_after) and after_fields['parent_pid']==worker['pid'],'same server start after peer/group observations')
            self.io.work();ready,_,_=select.select([self.pidfd.fd],[],[],0);need(not ready,'original server still live')
            self.server_identity=identity;now=self.io.now(deadline);cost=a.owner.cost_prefix()
            self.host_process=self._capture('host_server_process','ProcessObservation',dict(schema='ci_process_observation_v1',
              attempt=v.base.pin,condition=a.condition,cost_prefix=cost,identity=identity,group_identity=worker,
              parent_identity=worker,observed_ns=now,producer='host',subject='server'))
            self.socket_identity=dict(schema='ci_owned_path_identity_v1',parent_handle_ordinal=anchor.ordinal,
              relative_path='backend.sock',device=observed.st_dev,inode=observed.st_ino,kind='socket',
              mode=stat.S_IMODE(observed.st_mode),uid=observed.st_uid,observed_ns=now)
            self.host_socket=self._capture('host_server_socket','SocketObservation',dict(schema='ci_socket_observation_v1',
              attempt=v.base.pin,condition=a.condition,cost_prefix=a.owner.cost_prefix(),identity=self.socket_identity,
              listen_or_connected='connected',observed_ns=now,producer='host',relative_path='backend.sock',
              server=identity,socket_type='AF_UNIX_STREAM'))
            pid,uid,gid=self.raw_peer
            self.host_peer=self._capture('host_server_peer','PeerCredentialObservation',dict(schema='ci_peer_credential_observation_v1',
              attempt=v.base.pin,condition=a.condition,cost_prefix=a.owner.cost_prefix(),gid=gid,uid=uid,pid=pid,
              observed_ns=now,producer='host',server=identity,socket_observation=self.host_socket.pin))
            self.host_observation=self._capture('host_initialization','HostInitializationObservation',dict(
              schema='ci_host_initialization_observation_v1',attempt=v.base.pin,condition=a.condition,cost_prefix=a.owner.cost_prefix(),
              host_owner_binding=a.owner.parent.binding_pin,initialization=v.initialization.pin,observed_ns=now,
              pair_nonce=act.context['launch_nonce'],peer=self.host_peer.pin,server_process=self.host_process.pin,
              socket=self.host_socket.pin,source_admission=act.context['source_admission'],worker_process=a.process_capture.pin))
            self.admission=self._capture('host_backend_admission','BackendAdmissionAck',dict(schema='ci_llama_backend_admission_ack_v1',
              backend_attempt=v.base.pin,condition=a.condition,generation_deadline_ns=act.G,
              host_observation=self.host_observation.pin,host_owner_binding=a.owner.parent.binding_pin,
              initialization=v.initialization.pin,issued_ns=self.io.now(act.G),nonce=act.context['launch_nonce'],
              pair_id=act.context['pair_id'],source_admission=act.context['source_admission'],worker_attempt=a.prefix_capture.pin))
            # Retain actual completed products before later close/clock checks.
            v.host_observation=self.host_observation;v.admission=self.admission
            self._close_transient();self.io.now(act.G);self.initialization_complete=True;return self
        except BaseException as error:self.retain(error,'initialize');self.close_all_once();raise
    def _close_transient(self):
        first=None
        for slot in reversed(self.slots):
            if slot is self.pidfd:continue
            if not slot.close():
                error=slot.raw_first or RuntimeError('unknown original H descriptor closure')
                if first is None:first=error
                self.retain(error,'transient_close')
                for later in slot.raw_secondaries:self.retain(later,'transient_close_secondary')
        if first is not None:raise first
    def observe_closure(self):
        self.require_original();need(self.initialization_complete and not self.closure_entered and self.raw_first is None,
             'one same original qualified initialization before server closure observation')
        self.closure_entered=True;self.view.host_closure_owner=self
        try:
            v=self.view;a=self.attempt;act=self.receiver.activation
            need(v.closure is not None and v.closure.body['status']=='complete' and
                 same(v.closure.body['server_identity'],self.server_identity),'same original worker closure claim')
            self.io.now(act.R);self.io.work();ready,_,_=select.select([self.pidfd.fd],[],[],0)
            need(ready==[self.pidfd.fd],'actual retained original server pidfd reports exit')
            self.server_exit_observed=True
            self.shutdown_census=observe_original_host_group_membership(self.io,act.R)
            self.shutdown_threads=resolve_original_host_threads(self.io,self.shutdown_census,act.R)
            pids={pid for row in self.shutdown_census.passes[-1]for pid in row[3]}
            need(pids=={a.process.identity['pid']} and not self.shutdown_threads.other_threads and
                 not self.shutdown_threads.unresolved,'no backend residual PID or TID in complete original aggregate')
            anchor=self._anchor(act.R);self.io.work()
            try:os.stat('backend.sock',dir_fd=anchor.fd,follow_symlinks=False)
            except FileNotFoundError:self.socket_absent=True
            need(self.socket_absent,'actual anchored absence; no H cleanup masquerades as worker closure')
            self.close_all_once();need(self.closed and self.raw_first is None,'all actual H observation slots closed once')
            self.io.now(act.R);self.closure_complete=True;return self
        except BaseException as error:self.retain(error,'closure');self.close_all_once();raise
    def close_all_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;ok=True
        for slot in reversed(self.slots):
            if not slot.close():
                ok=False;self.retain(slot.raw_first or RuntimeError('unknown original H descriptor close'),'close')
                for later in slot.raw_secondaries:self.retain(later,'close_secondary')
        self.closed=ok;return ok
    def require_completed(self):
        self.require_original()
        need(self.initialization_complete and self.closure_complete and self.closed and self.raw_first is None and
             self.io.raw_first is None and not self.io.unknown_read and not self.io.unknown_write and
             self.server_exit_observed and self.socket_absent,'actual completed independent H native evidence')
        need(self.view.admission is self.admission and self.view.host_observation is self.host_observation and
             self.view.host_closure_owner is self,'same original captures and closure owner')
        return self
