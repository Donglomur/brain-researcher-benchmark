"""Actual cgroup-v2 acquisition and empty-tree closure; no block/logical alias."""
import os
import time
from dataclasses import dataclass
from .custody import require
from .filesystem import Directory, acquire_fd, component
from .linux_api import require_cgroup2

_READ = frozenset(("cgroup.type", "cgroup.controllers", "cgroup.subtree_control",
                   "cgroup.events", "cpu.stat", "memory.current", "memory.peak",
                   "memory.events", "pids.current", "pids.events", "cgroup.procs"))
_WRITE = frozenset(("memory.max", "memory.swap.max", "pids.max", "cpu.max",
                    "cgroup.procs", "cgroup.kill"))
@dataclass(frozen=True)
class Sample:
    original_group: object
    monotonic_ns: int
    cpu_usec: int
    memory_peak_bytes: int
    memory_current_bytes: int
    pids_current: int
    populated: bool
    oom_kills: int
    raw: tuple

class Cgroup:
    cleanup_priority = 100
    def __init__(self, parent, name, memory_bytes, pids_limit, cpu_quota, cpu_period,
                 cleanup_seconds):
        require(type(parent) is Directory, "actual-cgroup-parent")
        component(name)
        require(all(type(x) is int and x > 0 for x in
                    (memory_bytes, pids_limit, cpu_quota, cpu_period, cleanup_seconds)),
                "cgroup-positive-required-limits")
        self.parent, self.name = parent, name
        self.owner, self.capacity = parent.owner, parent.capacity
        self.attempt = self.owner.begin("cgroup-create:" + name)
        self.created = False
        self.directory = None
        self.closed = False
        self.close_attempted = False
        self.final = None
        self.samples = []
        self.cleanup_seconds = cleanup_seconds
        self.owner.retain(self)  # incomplete owner before mkdir
        try:
            require_cgroup2(parent.fd.require_live())
            self.capacity.consume_attempt("creation_attempts", "cgroup-mkdir:" + name)
            os.mkdir(name, 0o700, dir_fd=parent.fd.require_live())
            self.created = True
            self.directory = parent.child(name)
            self._write("memory.max", str(memory_bytes))
            self._write("memory.swap.max", "0")
            self._write("pids.max", str(pids_limit))
            self._write("cpu.max", str(cpu_quota) + " " + str(cpu_period))
            self.initial = self.sample()
            require(not self.initial.populated, "fresh-empty-cgroup")
            self.attempt.finish()
        except BaseException as error:
            self.attempt.fail(error, "cgroup-initialization")
            if self.created and self.directory is None:
                self.attempt.uncertain("created-cgroup-without-open-handle", name)
            self.attempt.raise_first()

    def _read(self, name, *, cleanup=False):
        require(name in _READ and self.directory is not None, "cgroup-read-name")
        attempt = self.owner.begin("cgroup-read:" + name, cleanup=cleanup)
        token = self.capacity.reserve("read_bytes", 65537, name, cleanup=cleanup)
        fd = None
        raw = bytearray()
        count = 0
        pending = False
        attempt.returned.append(raw)
        try:
            fd = acquire_fd(self.owner,self.capacity,name,os.O_RDONLY,
                            parent=self.directory.fd.require_live(),cleanup=cleanup)
            while count < 65537:
                pending = True
                part = os.read(fd.require_live(), min(4096,65537-count))
                count += len(part)
                pending = False
                attempt.returned.append(part)
                if not part: break
                raw.extend(part)
            require(count <= 65536, "cgroup-pseudofile-cap")
        except BaseException as error:
            attempt.fail(error,"cgroup-read")
        finally:
            try: self.capacity.settle(token,count,unknown=pending)
            except BaseException as error:
                attempt.fail(error,"cgroup-read-accounting")
                attempt.uncertain("cgroup-read-accounting",count)
            if fd is not None:
                try: fd.close()
                except BaseException as error: attempt.fail(error,"cgroup-read-close")
        attempt.raise_first()
        body=bytes(raw)
        attempt.returned.append(body)
        attempt.finish()
        return body

    def _write(self, name, value, *, cleanup=False):
        require(name in _WRITE and type(value) is str and
                len(value) <= 128 and "\n" not in value, "cgroup-write-name")
        body = (value+"\n").encode("ascii")
        attempt = self.owner.begin("cgroup-write:"+name,cleanup=cleanup)
        token = self.capacity.reserve("write_bytes",len(body),name,cleanup=cleanup)
        fd=None;count=0;pending=False
        try:
            fd=acquire_fd(self.owner,self.capacity,name,os.O_WRONLY,
                          parent=self.directory.fd.require_live(),cleanup=cleanup)
            pending=True
            count=os.write(fd.require_live(),body)
            pending=False
            require(count==len(body),"single-cgroup-control-write")
        except BaseException as error:
            attempt.fail(error,"cgroup-control")
        finally:
            try:self.capacity.settle(token,count,unknown=pending)
            except BaseException as error:
                attempt.fail(error,"cgroup-control-accounting")
                attempt.uncertain("cgroup-control-accounting",count)
            if fd is not None:
                try:fd.close()
                except BaseException as error:attempt.fail(error,"cgroup-control-close")
        attempt.raise_first()
        attempt.finish()

    @staticmethod
    def _fields(raw):
        pairs=[line.split() for line in raw.decode("ascii").splitlines()]
        require(all(len(p)==2 for p in pairs) and len({p[0] for p in pairs})==len(pairs),
                "kernel-counter-fields")
        values={k:int(v) for k,v in pairs}
        require(all(x>=0 for x in values.values()),"kernel-nonnegative")
        return values

    def sample(self, *, cleanup=False):
        bodies=tuple((k,self._read(k,cleanup=cleanup)) for k in
                     ("cpu.stat","memory.peak","memory.current","pids.current",
                      "cgroup.events","memory.events"))
        rows=dict(bodies)
        cpu=self._fields(rows["cpu.stat"])
        events=self._fields(rows["cgroup.events"])
        memory=self._fields(rows["memory.events"])
        require(events["populated"] in (0,1),"cgroup-populated-bit")
        sample=Sample(self,time.monotonic_ns(),cpu["usage_usec"],
                      int(rows["memory.peak"]),int(rows["memory.current"]),
                      int(rows["pids.current"]),bool(events["populated"]),
                      memory["oom_kill"],bodies)
        self.samples.append(sample)
        require(all(type(x) is int and x>=0 for x in
                    (sample.cpu_usec,sample.memory_peak_bytes,sample.memory_current_bytes,
                     sample.pids_current,sample.oom_kills)),"native-counter-domains")
        if len(self.samples)>1:
            prior=self.samples[-2]
            require(sample.cpu_usec>=prior.cpu_usec and
                    sample.memory_peak_bytes>=prior.memory_peak_bytes,
                    "same-cgroup-monotonic-counters")
        return sample

    def attach_stopped_pid(self, pid):
        # Caller must own a real stopped child; this raw operation is private
        # to the launcher's source, never a public receipt/JSON admission API.
        require(type(pid) is int and pid>0 and not self.close_attempted,
                "actual-stopped-child-pid")
        self._write("cgroup.procs",str(pid))

    def close(self):
        if self.close_attempted:return
        self.close_attempted=True
        if not self.created:
            return  # failed mkdir never authorizes killing an existing group
        if self.directory is None:
            self.attempt.uncertain("cgroup-no-owned-descriptor",self.name)
            return
        self.final=None
        try:
            self._write("cgroup.kill","1",cleanup=True)
        except BaseException as error:
            self.attempt.fail(error,"cgroup-kill")
        deadline=time.monotonic()+self.cleanup_seconds
        try:
            while True:
                current=self.sample(cleanup=True)
                if not current.populated:
                    self.final=current
                    break
                require(time.monotonic()<deadline,"cgroup-cleanup-deadline")
                time.sleep(0.01)
        except BaseException as error:
            self.attempt.fail(error,"cgroup-final-observation")
            self.attempt.uncertain("cgroup-final-observation",self.name)
        self.closed=self.final is not None and not self.final.populated
        self.attempt.raise_first()

    def report(self):
        return {"created":self.created,"closed":self.closed,
                "final":None if self.final is None else {
                    "cpu_usec":self.final.cpu_usec,
                    "memory_footprint_peak_upper_bytes":self.final.memory_peak_bytes,
                    "final_simultaneous_tasks":self.final.pids_current,
                    "populated":self.final.populated,"oom_kills":self.final.oom_kills},
                "logical_read_write_coverage":False,
                "cumulative_process_creation_coverage":False,
                "memory_is_exact_rss":False,
                "whole_native_qualification":False}

