"""Immutable authority window and trusted entry/exit checks, never participant callbacks."""
import time
from functools import wraps
from dataclasses import dataclass
from .errors import Refusal,require
from .custody import custody,failure_notice

@dataclass(frozen=True)
class Window:
    _original: tuple
    _monotonic_expiry: int
    def __init__(self,valid_after,expires_at):
        require(type(valid_after) is int and type(expires_at) is int and valid_after<expires_at,'authority nanosecond window')
        wall=time.time_ns();mono=time.monotonic_ns()
        object.__setattr__(self,'_original',(valid_after,expires_at))
        object.__setattr__(self,'_monotonic_expiry',mono+max(0,expires_at-wall))
    @property
    def original(self):return self._original
    def check(self):
        require(self._original[0]<=time.time_ns()<self._original[1] and time.monotonic_ns()<self._monotonic_expiry,'original authority expired or not yet valid')
    def remaining_ns(self):
        self.check()
        return min(self._original[1]-time.time_ns(),self._monotonic_expiry-time.monotonic_ns())

def boundary(fn):
    @wraps(fn)
    def call(self,*args,**kwargs):
        guard=getattr(self,'guard',None)
        try:
            begin=getattr(self,'begin_boundary',None)
            if begin is not None:begin(fn.__qualname__)
            if guard:guard()
            result=fn(self,*args,**kwargs)
            if guard:guard()
            release=getattr(self,'release_boundary_success',None)
            if release is not None:release(fn.__qualname__)
            return result
        except BaseException as exc:
            state=custody(self);state.fail(exc,fn.__qualname__)
            # Strong exception and phase precede all fallible error encoding.
            self.first_failure=state
            handler=getattr(self,'retain_boundary_failure',None)
            if handler is not None:
                try:handler(exc,fn.__qualname__)
                except BaseException as secondary:state.add_secondary(secondary,fn.__qualname__+':custody_hook')
            if getattr(self,'ledger',None) is not None:
                failure_notice(self,exc,fn.__qualname__,'boundary_failure',lambda:{'boundary':fn.__qualname__,'original_error':state.record(),'ordinary_admission':False})
            raise
    return call
