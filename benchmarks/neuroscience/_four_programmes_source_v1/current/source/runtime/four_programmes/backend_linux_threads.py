"""Actual bounded per-thread TGID/start observations for an earlier group census.

Numeric thread IDs never imply that an unknown thread belongs to the excluded
worker. All original census IDs are retained until individually resolved. This
raw observer creates neither no-escape qualification nor a wire success.
"""
import os
from .common import need
from .backend_linux_cgroup import GroupCensus
from .backend_linux_observations import read_kernel_fd,parse_proc_stat,process_identity_from_observation


def parse_thread_status(raw,tid):
    need(type(raw) is bytes and len(raw)<=65536,'bounded original process status')
    selected={}
    for line in raw.splitlines():
        if b':' not in line:continue
        key,value=line.split(b':',1)
        if key in (b'Pid',b'Tgid'):
            need(key not in selected,'unique original status identity field')
            word=value.strip();need(word.isdigit(),'exact positive decimal kernel identity')
            selected[key]=int(word)
    need(set(selected)=={b'Pid',b'Tgid'} and selected[b'Pid']==tid and selected[b'Tgid']>0,
         'complete actual thread and group identity fields')
    return selected[b'Tgid']


class GroupThreadIdentityAttempt:
    def __init__(self,census):
        need(type(census) is GroupCensus and census.stable and census.closed and census.raw_first is None and
             len(census.thread_passes)==2,'actual completed same-owner full thread membership census')
        self.census=census;self.io=census.io;self.handle=self.io.handle
        self.expected=None;self.unresolved=None;self.records=[];self.prefixes=[];self.slots=[]
        self.worker_threads=[];self.other_threads=[];self.root=None;self.entered=False
        self.raw_first=None;self.secondaries=[];self.close_entered=False;self.closed=False
        self.observed_ns=None;self.membership_recheck=None

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.io.retain(error,'thread_identity_'+site)

    def _slot(self):
        slot=self.io.slot('proc');self.slots.append(slot);return slot

    def _file(self,directory,name,cap,deadline,prefix,label):
        slot=self._slot();slot.openat(directory.fd,name,os.O_RDONLY|os.O_NONBLOCK)
        raw=read_kernel_fd(slot,cap,deadline);prefix[label]=raw
        return raw

    def run(self,mapping,deadline):
        need(not self.entered,'one original per-thread observation');self.entered=True
        try:
            worker=self.io.original_worker_identity()
            need(mapping['boot_id']==worker['boot_id'],'same original worker boot mapping')
            self.io.work(4096*64);self.io.meter.charge('retained_bytes',4096*256)
            self.expected=tuple(t for row in self.census.thread_passes[-1] for t in row[3])
            self.unresolved=set(self.expected)
            known_pids={p for row in self.census.passes[-1] for p in row[3]}
            self.root=self._slot();self.root.fixed_proc_root()
            for tid in self.expected:
                self.io.now(deadline);self.io.meter.charge('retained_bytes',16384)
                first_slot=len(self.slots)
                prefix={'tid':tid};self.prefixes.append(prefix)
                directory=self._slot();directory.openat(self.root.fd,str(tid),os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
                before=self._file(directory,'stat',8192,deadline,prefix,'stat_before')
                status=self._file(directory,'status',65536,deadline,prefix,'status_before')
                tgid=parse_thread_status(status,tid);fields=parse_proc_stat(before,tid)
                need(tgid in known_pids,'actual thread belongs to a process in the same complete census')
                group_dir=self._slot();group_dir.openat(self.root.fd,str(tgid),os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
                leader_before=self._file(group_dir,'stat',8192,deadline,prefix,'leader_before')
                leader_fields=parse_proc_stat(leader_before,tgid)
                leader_after=self._file(group_dir,'stat',8192,deadline,prefix,'leader_after')
                after=self._file(directory,'stat',8192,deadline,prefix,'stat_after')
                after_status=self._file(directory,'status',65536,deadline,prefix,'status_after')
                after_fields=parse_proc_stat(after,tid)
                need(parse_thread_status(after_status,tid)==tgid and
                     fields['start_ticks']==after_fields['start_ticks'] and
                     fields['parent_pid']==after_fields['parent_pid'] and
                     leader_fields['start_ticks']==parse_proc_stat(leader_after,tgid)['start_ticks'],
                     'same actual thread/TGID/start throughout original observation')
                if tgid==worker['pid']:
                    observed,_=process_identity_from_observation(leader_after,tgid,worker['boot_id'],mapping,
                        worker['launch_nonce'],worker['source'],worker['parent_launch'])
                    need(observed==worker,'exclude only threads of the exact original worker process/start')
                    self.worker_threads.append(tid)
                else:self.other_threads.append(tid)
                self.records.append({'tid':tid,'tgid':tgid,'start_ticks':fields['start_ticks'],
                    'leader_start_ticks':leader_fields['start_ticks'],'observed_ns':self.io.now(deadline)})
                # Bound simultaneous OS descriptors independently of the
                # finite retained evidence roster. No later thread can reuse
                # a numeric FD before its original slot is closed/latching.
                self._close_slots(self.slots[first_slot:])
                self.unresolved.remove(tid)
            # The original membership may have changed during per-thread IO.
            # Reobserve the same owned hierarchy; this is separately charged
            # original work, not a reset/replacement of either census.
            c=self.census
            self.membership_recheck=GroupCensus(self.io,c.fd,c.identity,c.worker_pid,c.server_pid,deadline)
            self.membership_recheck.run()
            need(c.passes[-1]==self.membership_recheck.passes[-1] and
                 c.thread_passes[-1]==self.membership_recheck.thread_passes[-1],
                 'complete original membership unchanged across thread identity observations')
            self.observed_ns=self.io.now(deadline)
            return self
        except BaseException as error:self.retain(error,'run');raise
        finally:
            original=self.raw_first
            try:self.close_once()
            except BaseException as error:
                self.retain(error,'close')
                if original is None:raise

    def _close_slots(self,slots):
        first=None
        for slot in reversed(slots):
            if slot.close_entered:continue
            if not slot.close():
                error=slot.raw_first or RuntimeError('unknown original thread metadata descriptor closure')
                if first is None:first=error
                self.retain(error,'fd_close')
                for secondary in slot.raw_secondaries:self.retain(secondary,'fd_close_secondary')
        if first is not None:raise first
    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True
        self._close_slots(self.slots)
        self.closed=all(slot.closed for slot in self.slots)
        need(self.closed,'all original thread observer descriptors closed')
        return True
