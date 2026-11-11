"""Actual owned Linux server PID/start/boot/namespace/environment observations.

The supplied selected mapping is data, not source/native admission. The fixed
context factory must bind it to the same actual original qualified H mapping.
No output of this observer independently grants root/native authority.
"""
import os
import select
from .common import need,closed,same
from .precommit_records import validate_type
from .backend_linux_process import ServerProcessOwner
from .backend_linux_artifacts import ArtifactReadAttempt
from .backend_linux_observations import read_kernel_fd,process_identity_from_observation,observe_namespace_links


class ServerIdentityAttempt:
    def __init__(self,process):
        need(type(process) is ServerProcessOwner and process.child is not None and process.spawn_returned and
             process.pidfd is not None and process.pidfd.fd is not None,'actual returned original server and retained pidfd')
        self.process=process;self.io=process.io;self.handle=process.handle
        self.entered=False;self.slots=[];self.root=None;self.directory=None;self.raw_first=None;self.secondaries=[]
        self.proc_before=None;self.proc_after=None;self.boot_raw=None;self.environment_raw=None
        self.identity=None;self.namespaces=None;self.environment=None;self.observed_ns=None
        self.executable_before=None;self.executable_after=None
        self.close_entered=False;self.closed=False

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.io.retain(error,'identity_'+site)

    def _slot(self):
        slot=self.io.slot('proc');self.slots.append(slot);return slot

    def _live_pidfd(self,deadline):
        self.io.now(deadline);self.io.work()
        readable,_,_=select.select([self.process.pidfd.fd],[],[],0)
        need(not readable,'same original live pidfd, not an exited/reused numeric PID')

    def _file(self,parent,name,cap,deadline):
        slot=self._slot();slot.openat(parent.fd,name,os.O_RDONLY|os.O_NONBLOCK)
        return read_kernel_fd(slot,cap,deadline)

    def run(self,mapping,expected_environment,deadline,executable_artifact):
        need(not self.entered,'one actual original server identity/environment attempt');self.entered=True
        try:
            closed(mapping,('schema','source','qualification','clock_ticks','tick_to_monotonic_offset_ns','boot_id'))
            need(mapping['schema']=='four_linux_start_clock_mapping_v1','exact selected qualified clock-map format')
            validate_type('Pin',mapping['source']);validate_type('Pin',mapping['qualification'])
            need(type(expected_environment) is dict and len(expected_environment)<=64 and
                 all(type(k) is str and type(v) is str and '\0' not in k+v and '=' not in k for k,v in expected_environment.items()),
                 'exact source-selected finite environment; no caller ambient merge')
            need(same(expected_environment,self.process.spec.environment),'same original exact Popen environment')
            need(type(executable_artifact) is ArtifactReadAttempt and executable_artifact.io is self.io and
                 executable_artifact.role=='server_executable' and executable_artifact.entered and
                 executable_artifact.closed and executable_artifact.raw_first is None and
                 executable_artifact.observation is not None and
                 same(executable_artifact.selected,self.handle.profile_body['server_executable']),
                 'actual same-owner completed selected executable artifact observation')
            expected_stat=executable_artifact.observation['stat']
            self._live_pidfd(deadline)
            self.root=self._slot();self.root.fixed_proc_root()
            parent=self.root
            for component in ('sys','kernel','random'):
                slot=self._slot();slot.openat(parent.fd,component,os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK);parent=slot
            # This is the existing boot identifier, never an entropy/RNG call.
            self.boot_raw=self._file(parent,'boot_id',128,deadline)
            boot=self.boot_raw.decode('ascii').strip();need(boot==mapping['boot_id'],'actual same selected Linux boot')
            self.directory=self._slot();self.directory.openat(self.root.fd,str(self.process.child.pid),os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
            self.io.work();self.io.meter.charge('read_bytes',4096)
            # Only this fixed kernel process-executable interface is followed;
            # no unselected filesystem alias or requested path is opened.
            self.executable_before=os.stat('exe',dir_fd=self.directory.fd,follow_symlinks=True)
            exe_fields=('st_dev','st_ino','st_size','st_mode','st_mtime_ns','st_ctime_ns')
            need(all(getattr(self.executable_before,k)==getattr(expected_stat,k) for k in exe_fields),
                 'actual running executable is the earlier fully authenticated original artifact')
            self.proc_before=self._file(self.directory,'stat',8192,deadline)
            identity,fields=process_identity_from_observation(self.proc_before,self.process.child.pid,boot,mapping,
                self.handle.ack_body['nonce']+'/server/0',self.handle.profile_body['server_executable'],self.handle.admission.ack.pin)
            need(fields['parent_pid']==self.handle.ack_body['worker_identity']['pid'],
                 'actual server parent is the original worker, not an unrelated process')
            self.namespaces=observe_namespace_links(self.directory.fd,self.io,deadline)
            self.environment_raw=self._file(self.directory,'environ',1048576,deadline)
            need(not self.environment_raw or self.environment_raw.endswith(b'\0'),'complete proc environment delimiter')
            entries=self.environment_raw.split(b'\0')[:-1] if self.environment_raw else []
            need(len(entries)<=64,'no unselected environment growth')
            observed={}
            for raw in entries:
                need(b'=' in raw,'complete original environment entry')
                key,val=raw.split(b'=',1);key=key.decode('utf8');val=val.decode('utf8')
                need(key not in observed,'no duplicate original environment key');observed[key]=val
            need(same(observed,expected_environment),'actual complete process environment equals exact selected allowlist')
            # Never publish unexpected environment values; raw failed prefixes
            # remain original private observation custody, not diagnostics.
            self.environment=observed
            self.proc_after=self._file(self.directory,'stat',8192,deadline)
            self.io.work();self.io.meter.charge('read_bytes',4096)
            self.executable_after=os.stat('exe',dir_fd=self.directory.fd,follow_symlinks=True)
            need(all(getattr(self.executable_after,k)==getattr(self.executable_before,k) for k in exe_fields),
                 'same actual executable throughout original process observation')
            after,after_fields=process_identity_from_observation(self.proc_after,self.process.child.pid,boot,mapping,
                self.handle.ack_body['nonce']+'/server/0',self.handle.profile_body['server_executable'],self.handle.admission.ack.pin)
            need(same(identity,after) and fields['parent_pid']==after_fields['parent_pid'],
                 'actual same process/start/parent throughout environment/namespace observation')
            self._live_pidfd(deadline);self.identity=identity;self.observed_ns=self.io.now(deadline)
            return self
        except BaseException as error:self.retain(error,'run');raise
        finally:
            original=self.raw_first
            try:self.close_once()
            except BaseException as error:
                self.retain(error,'close')
                if original is None:raise

    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;first=None
        for slot in reversed(self.slots):
            if not slot.close():
                error=slot.raw_first or RuntimeError('unknown original proc descriptor closure')
                if first is None:first=error
                self.retain(error,'fd_close')
                # A failed read may already occupy the slot's first-error
                # cell. Its later close failure must also reach this caller's
                # ordered custody, not only the aggregate IO owner.
                for secondary in slot.raw_secondaries:self.retain(secondary,'fd_close_secondary')
        self.closed=first is None
        if first is not None:raise first
        return True
