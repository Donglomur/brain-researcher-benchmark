"""Fixed actual six-operation worker initialization prefix, not whole MAIN.

No input Context, grant, provider, path, callback or numerical limit is accepted.
Server/environment/HTTP/agent/render/whole-terminal producers remain separate.
"""
from .common import need
from . import worker_fixed_entry_v3 as fixed_entry
from .worker_backend_v3 import WorkerBackendOwnerV3
from .worker_initialization_recipe_v4 import produce_worker_initialization_recipe_v4,OPERATIONS

_MAIN=object();_attempt=None

class WorkerMainNativeOwnerV4:
    def __init__(self,token):
        need(token is _MAIN,'fixed no-argument original worker initializer')
        self.backend=None;self.recipe=None;self.current=None;self.captures=[];self.returned_captures=[];self.entry_attempt=None
        self.raw_first=None;self.secondaries=[];self.prefix_complete=False
        self.close_entered=False;self.closed=False
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append((site,error))
        if self.backend is not None:
            try:self.backend.retain(error,'fixed_main_'+site)
            except BaseException as later:
                if later is not self.raw_first:self.secondaries.append(('backend_retention',later))
    def require_prefix(self):
        if self.raw_first is not None:raise self.raw_first
        b=self.backend
        need(_attempt is self and type(b)is WorkerBackendOwnerV3 and
             getattr(b,'main_native_owner_v4',None)is self and not self.close_entered and
             self.recipe is b.initialization_recipe_v4 and self.recipe.complete and self.prefix_complete and
             len(self.captures)==6 and self.captures[0]is b.base and
             all(self.captures[i]is b.artifact_captures[role]for i,role in enumerate(OPERATIONS[1:],1)),
             'complete real base/five-artifact prefix, never server/agent completion')
        self.recipe.require_original();return self
    def close_once(self):
        """Unconditional original native/endpoint cleanup; no new grants."""
        if self.close_entered:return self.closed
        self.close_entered=True;ok=True;b=self.backend
        endpoint=(None if self.entry_attempt is None else self.entry_attempt['endpoint'])
        if b is not None:
            try:
                value=b.close_preparation_once_v3()
                if value is not True:
                    error=b.raw_first
                    if error is None and b.io is not None:error=b.io.raw_first
                    if error is None:error=RuntimeError('original initialization descriptor closure unknown')
                    self.retain(error,'native_close');ok=False
            except BaseException as error:self.retain(error,'native_close');ok=False
            try:
                current=b.context.channel.endpoint
                need(endpoint is None or current is endpoint,'same original endpoint for unconditional cleanup')
                endpoint=current
            except BaseException as error:self.retain(error,'endpoint_identity');ok=False
        if endpoint is not None:
            try:
                value=endpoint.close_all_once()
                if value is not True:
                    error=endpoint.raw_first
                    if error is None:error=RuntimeError('original initialization endpoint closure unknown')
                    self.retain(error,'endpoint_close');ok=False
            except BaseException as error:self.retain(error,'endpoint_close');ok=False
        self.closed=ok;return ok

def run_fixed_worker_initialization_v4():
    global _attempt
    need(_attempt is None,'one complete original fixed initializer attempt, including failures')
    main=WorkerMainNativeOwnerV4(_MAIN);_attempt=main
    try:
        need(fixed_entry._entry_attempt is None,'no adoption or cleanup of an earlier unrelated fixed entry')
        try:backend=fixed_entry.prepare_fixed_worker_backend_v3()
        finally:
            main.entry_attempt=fixed_entry._entry_attempt
            if main.entry_attempt is not None:main.backend=main.entry_attempt['backend']
        main.backend=backend
        need(type(backend)is WorkerBackendOwnerV3 and getattr(backend,'main_native_owner_v4',None)is None,
             'same actual unconsumed fixed prepared backend')
        backend.main_native_owner_v4=main
        main.recipe=produce_worker_initialization_recipe_v4(backend)
        for ordinal in range(6):
            operation=main.recipe.next_operation();main.current=operation
            try:
                effect=backend.meter.reserve_effect(operation.site,operation.stage,operation.maximum,operation.prior)
                main.recipe.retain_effect(operation,effect)
            except BaseException:
                # reserve_effect registers its actual partial attempt before
                # packets/clock/grant delivery; retain it even without a return.
                current=backend.meter.current_effect
                if current is not None and operation.effect is None:
                    try:main.recipe.retain_effect(operation,current)
                    except BaseException as later:main.secondaries.append(('retain_failed_reservation',later))
                raise
            capture=(backend.capture_base_v3(effect)if ordinal==0 else
                     backend.observe_artifact_v3(operation.operation,effect))
            main.returned_captures.append(capture)
            main.recipe.accept(operation,capture);main.captures.append(capture);main.current=None
        main.prefix_complete=True;return main.require_prefix()
    except BaseException as error:
        main.retain(error,'initialization')
        main.close_once()
        raise main.raw_first
