"""Strong original failure ownership; serialization is a secondary, fallible effect.

The carrier retains references, not deep copies. Its fixed secondary slots bound
reporting failures without recursive attempts to report a failed report. Receipt
and byte-buffer references are installed before publication and remain private.
"""
from contextlib import contextmanager


def text(exc):
    try:return str(exc)[:4096]
    except BaseException:return '<exception text unavailable>'


class Custody:
    def __init__(self):
        self.first_exception=None
        self.first_phase=None
        self.secondary=[None]*32
        self.secondary_count=0
        self.secondary_dropped=0
        self.observations=[]
        self.process=None
        self.links=[None]*32
        self.link_count=0

    def fail(self,exc,phase):
        if self.first_exception is None:
            self.first_exception=exc
            self.first_phase=phase
        elif exc is not self.first_exception:
            self.add_secondary(exc,phase)
        previous=getattr(exc,'reve_custody',None)
        if previous is not None and previous is not self and all(previous is not x for x in self.links[:self.link_count]) and self.link_count<len(self.links):
            self.links[self.link_count]=previous;self.link_count+=1
        try:exc.reve_custody=self
        except BaseException:pass
        return exc

    def add_secondary(self,exc,phase):
        if self.secondary_count<len(self.secondary):
            self.secondary[self.secondary_count]=(phase,exc)
            self.secondary_count+=1
        else:self.secondary_dropped+=1

    def record(self):
        return {'phase':self.first_phase,'type':type(self.first_exception).__name__ if self.first_exception is not None else None,
                'message':text(self.first_exception) if self.first_exception is not None else None,
                'secondary':[{'phase':p,'type':type(e).__name__,'message':text(e)} for p,e in self.secondary[:self.secondary_count]],
                'secondary_dropped':self.secondary_dropped}


def custody(owner):
    state=getattr(owner,'custody',None)
    if state is None:
        state=Custody();owner.custody=state
    return state


def failure_notice(owner,exc,phase,kind=None,payload=None):
    """Never replace exc with payload construction, error text or ledger failure."""
    state=custody(owner);state.fail(exc,phase)
    if kind is not None:
        try:
            body=payload() if callable(payload) else payload
            owner.ledger.append(kind,body)
        except BaseException as secondary:state.add_secondary(secondary,phase+':failure_publication')
    return state


@contextmanager
def observation(owner,phase,details,kind=None,refresh=None):
    """Retain live consumption before work, and keep first cause through reporting."""
    state=custody(owner);state.observations.append(details)
    original=None
    try:
        yield details
    except BaseException as exc:
        original=exc;state.fail(exc,phase)
        raise
    finally:
        try:
            if refresh is not None:refresh(details)
            if kind is not None:owner.ledger.append(kind,details)
        except BaseException as secondary:
            if original is not None:state.add_secondary(secondary,phase+':observation_publication')
            else:
                state.fail(secondary,phase+':observation_publication')
                raise


def reader_details(reader):
    return {'reserved_bytes':reader.bytes,'consumed_bytes':reader.consumed_bytes,'files':reader.files,
            'partial_observations':reader.partial_observations,'completed_objects':reader.observations}
