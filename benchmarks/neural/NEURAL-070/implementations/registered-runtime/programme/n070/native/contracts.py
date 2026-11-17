"""OCI qualification is supplied only by an authenticated N070 Deployment."""
from .io import need
from ..deployment import Deployment
from contextvars import ContextVar
from contextlib import contextmanager
_CURRENT=ContextVar('n070_verified_deployment',default=None)
@contextmanager
def bind(deployment):
    need(isinstance(deployment,Deployment),"Original evaluator deployment")
    token=_CURRENT.set(deployment)
    try:yield
    finally:_CURRENT.reset(token)
def require_qualification(qualification,selected,role):
    deployment=_CURRENT.get()
    need(isinstance(deployment,Deployment),"No dict/callback qualification authority")
    deployment.require()
    need(qualification==selected==deployment.identity and role in("participant","reference_preparation"),"Exact original deployment and role")

