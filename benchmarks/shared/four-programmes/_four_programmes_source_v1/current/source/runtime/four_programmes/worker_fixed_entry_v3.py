"""Fixed no-argument preparation entry; not complete backend/agent MAIN.

The returned owner has selected bootstrap objects but no base, model, server,
request or scientific result. Further consumers require actual original effect
grants from a separately selected complete native operation resource recipe.
"""
from .backend_linux_worker_channel import fixed_worker_endpoint_v3
from .worker_context_v3 import start_worker_context
from .worker_backend_v3 import WorkerBootstrapAdmissionV3,WorkerBackendOwnerV3

_entry_attempt=None

def prepare_fixed_worker_backend_v3():
    """Actual installed entry -> channel bootstrap -> retained V3 backend owner."""
    global _entry_attempt
    from .common import need
    need(_entry_attempt is None,'one fixed preparation entry including failures')
    attempt={'endpoint':None,'context':None,'backend':None,'raw_first':None,'secondaries':[]}
    _entry_attempt=attempt
    try:
        endpoint=fixed_worker_endpoint_v3();attempt['endpoint']=endpoint
        context=start_worker_context(endpoint);attempt['context']=context
        admission=WorkerBootstrapAdmissionV3.from_context(context)
        owner=WorkerBackendOwnerV3(admission);attempt['backend']=owner
        return owner
    except BaseException as error:
        attempt['raw_first']=error
        owner=attempt['backend'];endpoint=attempt['endpoint']
        if owner is not None:
            try:owner.close_preparation_once_v3()
            except BaseException as later:attempt['secondaries'].append(later)
        if endpoint is not None:
            try:endpoint.close_all_once()
            except BaseException as later:attempt['secondaries'].append(later)
        raise
