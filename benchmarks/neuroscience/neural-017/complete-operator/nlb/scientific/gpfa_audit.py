"""Observe original pinned GPFA OptimizeResults without changing its solver.

Only the GPFA core module's local optimize reference is replaced temporarily.
The SciPy module/function and all exact original call arguments remain unchanged.
"""
from .common import require,ScientificFailure
from ..contracts import Custody

class NativeOptimizerAudit:
    def __init__(self,latent,record,scope):
        self.latent=latent;self.record=record;self.scope=scope;self.rows=[];self.original_results=[];self.core=None;self.original=None;self.custody=Custody("native_optimizer:"+scope);record.custody.resources.append(self.custody)
    def __enter__(self):
        from elephant.gpfa import gpfa_core,gpfa_util
        self.core=gpfa_core;self.original=gpfa_core.optimize;self.fun=gpfa_util.grad_betgam
        require(not isinstance(self.original,NativeOptimizerAudit),'no nested/concurrent GPFA optimizer instrumentation')
        if not hasattr(self.record,'original_native_optimizer_results'):self.record.original_native_optimizer_results=[]
        gpfa_core.optimize=self
        return self
    def __getattr__(self,name):return getattr(self.original,name)
    def minimize(self,fun,x0,*args,**kwargs):
        import numpy as np
        require(fun is self.fun and not args and set(kwargs)=={'args','method','jac'}and kwargs['method']=='L-BFGS-B'and kwargs['jac']is True,'exact pinned original GPFA minimize call')
        result=self.original.minimize(fun,x0,*args,**kwargs)
        # Retain original returned object before conversion/event publication.
        self.original_results.append(result);self.record.original_native_optimizer_results.append(result)
        i=len(self.rows);row={'call_index':i,'iteration':i//self.latent+1,'latent_index':i%self.latent,
             'success':bool(result.success),'status':int(result.status),'nit':int(result.nit),
             'nfev':int(result.nfev),'njev':int(result.njev),'fun':float(result.fun),
             'x':float(np.asarray(result.x).item()),'jac':float(np.asarray(result.jac).item()),'message':str(result.message)}
        self.rows.append(row);self.record.event('original_gpfa_optimizer_result',scope=self.scope,**row)
        return result
    def __exit__(self,kind,error,tb):
        if error is not None:self.custody.fail(error,'native_fit_body')
        try:
            if self.core.optimize is not self:
                self.custody.fail(ScientificFailure('original GPFA optimizer reference changed during fitting'),'optimizer_reference_changed')
        except BaseException as secondary:self.custody.fail(secondary,'optimizer_reference_observation')
        # Restoration is independent of inspection and diagnostic publication.
        try:self.core.optimize=self.original
        except BaseException as secondary:self.custody.fail(secondary,'optimizer_reference_restore')
        self.record.custody.fail(None,'optimizer_cleanup',self.custody)
        if error is None:self.custody.raise_if_failed()
        return False
