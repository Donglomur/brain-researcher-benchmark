"""Original development stdout/stderr custody and prospective bounded reads.

This is used by the separate development route. It does not launch a child,
qualify an environment, invent EOF, refund an uncertain read, or grant success.
"""
import os
import time
from .common import need,integer
from .early_resources import EarlyResources

NAMES=('stdout','stderr')

class DevelopmentStreams:
    def __init__(self,owner,limit):
        need(type(owner)is EarlyResources and owner.parent.owner is owner,'same actual development resource owner')
        integer(limit,1)
        self.owner=owner;self.limit=limit
        self.streams={name:None for name in NAMES}
        self.original_streams={name:None for name in NAMES}
        self.chunks={name:[] for name in NAMES}
        self.counts={name:0 for name in NAMES}
        self.eof={name:False for name in NAMES}
        self.close_attempted={name:False for name in NAMES}
        self.closed={name:False for name in NAMES}
        self.closed_ns={name:None for name in NAMES}
        self.close_clock_raw={name:None for name in NAMES}
        self.unknown_reads=set();self.unknown_closes=set()
        self.pending_raw={name:None for name in NAMES}
        self.read_reservations={name:0 for name in NAMES}
        self.materialization_attempted={name:False for name in NAMES}
        self.materialized={name:None for name in NAMES}
        self.first_raw=None;self.secondary_raw=[]
    def retain(self,error,site,*,unknown=None):
        # Preserve the original error before diagnostics or any other action.
        if self.first_raw is None:self.first_raw=error
        elif self.first_raw is not error:self.secondary_raw.append(error)
        self.owner.parent.retain(error,'development_observe','unknown_failure',site,unknown)
    def bind(self,name,stream):
        try:
            need(name in NAMES and self.original_streams[name]is None and not self.close_attempted[name],
                 'each actual original pipe bound once')
            need(stream is not None,'actual returned Popen stream required')
            # Store the owner before fallible fileno/nonblocking setup. An
            # unknown setup result never loses a returned original pipe.
            self.streams[name]=stream;self.original_streams[name]=stream
            self.owner.host.charge('work_units',256)
            os.set_blocking(stream.fileno(),False)
        except BaseException as error:
            self.retain(error,'DevelopmentStreams.bind');raise
    def read_ready(self,name):
        attempted=False
        try:
            need(name in NAMES and self.streams[name]is not None and not self.close_attempted[name],
                 'same original live stream')
            need(not self.eof[name] and self.pending_raw[name]is None,'no duplicate EOF or lost earlier returned chunk')
            remaining=self.limit-self.counts[name]
            need(remaining>0,'zero allowance refuses without an EOF probe')
            amount=min(65536,remaining)
            # Actual physical read allowance, retained allocation and processing
            # are all admitted before fileno/read. Holds survive failure/EAGAIN.
            self.owner.host.charge('read_bytes',amount)
            self.read_reservations[name]+=amount
            self.owner.host.charge('retained_bytes',amount+64)
            self.owner.host.charge('work_units',amount+64)
            fd=self.streams[name].fileno()
            attempted=True
            try:raw=os.read(fd,amount)
            except BlockingIOError:return 'would_block'
            self.pending_raw[name]=raw
            need(type(raw)is bytes and len(raw)<=amount,'bounded actual bytes returned by original read')
            if not raw:
                self.eof[name]=True;self.pending_raw[name]=None
                return 'eof'
            # Keep the returned object in pending_raw until append completes.
            self.counts[name]+=len(raw)
            self.chunks[name].append(raw)
            self.pending_raw[name]=None
            return 'data'
        except BaseException as error:
            if attempted and self.pending_raw[name]is None:self.unknown_reads.add(name)
            self.retain(error,'DevelopmentStreams.read_ready',unknown='read_bytes' if attempted and name in self.unknown_reads else None)
            raise
    def materialize(self,name):
        try:
            need(name in NAMES and not self.materialization_attempted[name],'one original materialization attempt')
            self.materialization_attempted[name]=True
            need(self.pending_raw[name]is None and name not in self.unknown_reads,'no lost or uncertain original stream extent')
            self.owner.terminal_host.charge('retained_bytes',self.counts[name])
            self.owner.terminal_host.charge('work_units',self.counts[name]+64)
            raw=b''.join(self.chunks[name])
            need(len(raw)==self.counts[name],'complete original ordered stream bytes')
            self.materialized[name]=raw
            return raw
        except BaseException as error:
            self.retain(error,'DevelopmentStreams.materialize');raise
    def close(self,name):
        try:
            need(name in NAMES and not self.close_attempted[name],'one original close attempt')
            self.close_attempted[name]=True
            # Clear the retry slot before an ambiguous close. original_streams
            # remains diagnostic custody, not a usable retry capability.
            stream=self.streams[name];self.streams[name]=None
            if stream is None:
                need(self.original_streams[name]is None,'no prior ambiguous original pipe close')
                self.closed[name]=True;return
            original=None
            try:self.owner.terminal_host.charge('work_units',256)
            except BaseException as error:
                original=error
                self.retain(error,'DevelopmentStreams.close_admission',unknown='work_units')
            try:stream.close()
            except BaseException as error:
                self.unknown_closes.add(name)
                self.retain(error,'DevelopmentStreams.close')
                if original is None:raise
                raise original
            self.closed[name]=True
            # Own the actual successful close before the following fallible
            # original-H clock observation. A clock error cannot reopen/retry
            # the descriptor or manufacture a complete timed side.
            try:
                self.owner.check()
                observed=time.monotonic_ns();self.close_clock_raw[name]=observed
                integer(observed)
                need(observed<self.owner.parent.original_deadline,'original H close observation cutoff')
                self.closed_ns[name]=observed
            except BaseException as error:
                self.retain(error,'DevelopmentStreams.close_clock',unknown='wall_ns')
                if original is None:raise
            if original is not None:raise original
        except BaseException as error:
            if self.first_raw is not error and not any(e is error for e in self.secondary_raw):
                self.retain(error,'DevelopmentStreams.close')
            raise
    @property
    def complete(self):
        return (self.first_raw is None and all(self.eof.values()) and all(self.closed.values()) and
                all(type(value)is int for value in self.closed_ns.values()) and
                not self.unknown_reads and not self.unknown_closes and
                all(self.materialization_attempted.values()) and
                all(type(value)is bytes for value in self.materialized.values()))
