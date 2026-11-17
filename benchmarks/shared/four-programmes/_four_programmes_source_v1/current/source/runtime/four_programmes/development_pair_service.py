"""Fixed fair H service of both actual original worker attempts.

This caller begins only after the actual source-owned launch and receiver
issuers have registered both attempts. It creates no launch/native authority.
Its independent terminal continuation always visits both retained attempts.
"""
import select
from .common import need
from .development_preparation import PreparationHandle
from .development_handles import DevelopmentAttemptHandle
from .development_worker_io import DevelopmentWorkerKernel
from .precommit_records import CONDITIONS


class DevelopmentPairService:
    def __init__(self,pair):
        need(type(pair)is PreparationHandle and pair.promotion is pair and
             pair.owner.parent.preparation is pair,'actual same promoted original pair')
        need(not hasattr(pair,'worker_service'),'one service continuation including failure')
        self.pair=pair;self.owner=pair.owner;self.attempts={};self.kernels={};self.receivers={}
        self.raw_first=None;self.secondaries=[];self.rounds=0;self.entered=False
        self.stopped={};self.complete=False;self.completion=None;self.terminal_entered=False
        self.last_ready=None;self.last_timeout=None
        pair.worker_service=self # Retain before any charge/clock/receiver effect.

    def retain(self,error,site):
        first=self.owner.parent.first_raw
        if self.raw_first is None:self.raw_first=error if first is None else first
        if error is not self.raw_first:self.secondaries.append(error)
        try:self.owner.parent.retain(error,'development_observe','unknown_failure',site)
        except BaseException as later:self.secondaries.append(later)
        # Productive work stops for both arms. Mark actual kernels so their
        # existing terminal path cannot wait naturally on an unresponsive child.
        seen=set()
        for condition in CONDITIONS:
            # A binding failure may precede the second arm's scheduler entry.
            # Its independently registered original kernel still needs the
            # same stop disposition before the terminal caller visits it.
            attempt=self.pair.launches.get(condition)
            if (type(attempt)is not DevelopmentAttemptHandle or attempt.pair is not self.pair or
                    attempt.condition!=condition):continue
            kernel=attempt.worker_kernel
            if (type(kernel)is not DevelopmentWorkerKernel or kernel.attempt is not attempt or
                    kernel.running is not attempt.process or id(kernel)in seen):continue
            seen.add(id(kernel))
            try:kernel.retain(self.raw_first,site)
            except BaseException as later:self.secondaries.append(later)

    def _bind(self):
        from .backend_host_receiver import HChannelReceiver
        from .backend_linux_channel import HNativeChannelOwner
        for condition in CONDITIONS:
            a=self.pair.launches.get(condition)
            need(type(a)is DevelopmentAttemptHandle and a.pair is self.pair and a.condition==condition,
                 'entire same original attempt roster')
            a.require_live_original();self.attempts[condition]=a
            k=a.worker_kernel
            need(type(k)is DevelopmentWorkerKernel and k.attempt is a and k.running is a.process,
                 'same actual original kernel and process')
            self.kernels[condition]=k
            channel=a.native_channel
            need(type(channel)is HNativeChannelOwner and channel.attempt is a,
                 'same actual source-owned original channel')
            receiver=channel.protocol
            need(type(receiver)is HChannelReceiver and receiver.channel is channel and receiver.attempt is a and
                 receiver.activation.receiver is receiver and channel.receiver_activation is receiver.activation,
                 'actual original issuer/receiver registration')
            receiver.activation.require_original()
            need(k.spawn_entered and a.spawn_entered and a.launch_ack is not None and
                 k.raw_first is None and a.raw_first is None and receiver.raw_first is None,
                 'actual acknowledged original launch before paired service')
            self.receivers[condition]=receiver;self.stopped[condition]=False
        need(len({id(k)for k in self.kernels.values()})==2 and
             len({id(r)for r in self.receivers.values()})==2,'distinct actual original arm owners')

    def _readiness(self):
        # Fixed six-endpoint maximum: two H channels and four original pipes.
        # The lists and select result are bounded and prepaid under original H.
        self.owner.host.charge('retained_bytes',4096)
        self.owner.host.charge('work_units',4096)
        reads=[];writes=[];interest={};identities=set();deadlines=[]
        for condition in CONDITIONS:
            a=self.attempts[condition];k=self.kernels[condition];r=self.receivers[condition]
            if not self.stopped[condition]:deadlines.append(a.run_deadline_ns)
            if not r.finished:
                endpoint,direction=r.io_interest_v3()
                need(endpoint is a.native_channel.host and direction in ('read','write'),
                     'source-owned exact original readiness projection')
                need(id(endpoint)not in identities,'no endpoint aliased across original arms')
                identities.add(id(endpoint));interest[condition]=(endpoint,direction)
                (reads if direction=='read' else writes).append(endpoint)
            if not self.stopped[condition]:
                for key in k.selector.get_map().values():
                    need(key.data in ('stdout','stderr')and
                         key.fileobj is k.streams.original_streams[key.data],
                         'only actual returned original pipe occurrences')
                    need(id(key.fileobj)not in identities,'no channel/stream occurrence alias')
                    identities.add(id(key.fileobj));reads.append(key.fileobj)
        need(len(reads)+len(writes)<=6 and deadlines,'finite actual pending original endpoints')
        now=self.pair.clock();deadline=min(deadlines)
        need(now<deadline,'original unfinished worker R; no scheduler extension')
        timeout=min(.05,(deadline-now)/1000000000)
        self.last_timeout=timeout
        ready=select.select(reads,writes,[],timeout)
        self.last_ready=ready # Retain returned observations before validation.
        need(type(ready)is tuple and len(ready)==3 and not ready[2],
             'actual read/write readiness only')
        for returned,selected in ((ready[0],reads),(ready[1],writes)):
            need(type(returned)is list and len(returned)<=len(selected) and
                 all(any(item is original for original in selected)for item in returned),
                 'no fabricated readiness endpoint')
        return ready,interest

    def run(self):
        need(not self.entered,'one actual service loop, no retry')
        self.entered=True
        try:
            self._bind()
            while not all(self.stopped.values()):
                need(self.owner.parent.first_raw is None,'no productive service after original failure')
                ready,interest=self._readiness();self.rounds+=1
                # Both arms get one fixed nonblocking turn per round. A busy
                # endpoint never drains itself repeatedly ahead of its peer.
                for condition in CONDITIONS:
                    k=self.kernels[condition];r=self.receivers[condition]
                    if condition in interest:
                        endpoint,direction=interest[condition]
                        observed=ready[0]if direction=='read'else ready[1]
                        if any(item is endpoint for item in observed):r.step_once_v3()
                    if not self.stopped[condition]:
                        live=k.pump_ready_v1()
                        if k.raw_first is not None:raise k.raw_first
                        if self.attempts[condition].raw_first is not None:raise self.attempts[condition].raw_first
                        if not live:
                            need(r.finished and r.pending is None and not r.poisoned and r.raw_first is None,
                                 'actual complete final H reply before worker/stream termination')
                            self.stopped[condition]=True
            self.complete=True
        except BaseException as error:self.retain(error,'DevelopmentPairService.run')
        return self

    def finish(self):
        need(self.entered and not self.terminal_entered,'one terminal continuation after attempted service')
        self.terminal_entered=True
        from .development_completion import finish_pair_backend_v1
        try:
            self.completion=finish_pair_backend_v1(self.pair)
            need(self.complete and self.raw_first is None,'both original service arms completed before output promotion')
            return self.completion
        except BaseException as error:
            self.completion=getattr(self.pair,'backend_completion',None)
            self.retain(error,'DevelopmentPairService.finish');raise self.raw_first


def service_original_workers_v3(pair):
    """Actual service then both original terminal callers, including failure."""
    return DevelopmentPairService(pair).run().finish()
