"""One original context, with method-bound resources and independently held failure evidence."""
from .common import fresh_dir,publish,need,object_pin
from .native import LinuxExecutor,NativeFailure
from .provider import ProviderBridge
def job(job,packet,work,root,argv,profile,scope,evidence,provider_profile=None):
    token=None
    receipt={"job":job,"starts":0,"cpu_us":0,"provider":[],"status":"not_started"}
    primary=None;outputs=None;provider=None
    try:
        token=evidence.allocate(evidence.policy["job_receipt_bytes"],"original context receipt",scope)
        run=fresh_dir(work/job["job_id"])
        for name in ("input","output","logs","provider"):(run/name).mkdir(mode=0o700)
        need(object_pin(packet)==job["input_pin"],"Exact job input")
        publish(run/"input"/"case.json",packet,scope,"one isolated context")
        if provider_profile is not None:provider=ProviderBridge(provider_profile,scope,run/"provider",evidence)
        executor=LinuxExecutor(profile,scope,evidence)
        outputs,receipt=executor.execute(job,root,run/"input",run/"output",run/"logs",argv,provider)
    except BaseException as error:
        primary=error
        if isinstance(error,NativeFailure):receipt=error.receipt
        receipt["failure"]={"type":type(error).__name__,"message":str(error)[:512]}
    finally:
        if provider is not None:receipt["provider"]=provider.snapshot()
        if hasattr(scope,"finish"):
            try:receipt["method_context"]=scope.finish(receipt.get("cpu_us"))
            except BaseException as error:
                receipt["method_failure"]={"type":type(error).__name__,"message":str(error)[:512]}
                receipt["method_totals"]=scope.method.summary(compact=True)
                if primary is None:primary=error
        if primary is not None:receipt["status"]="failed"
        try:
            need(token is not None,"Original context evidence was never admitted")
            receipt["evidence"]=evidence.emit(token,work/"receipts"/(job["job_id"]+".json"),receipt)
        except BaseException as error:
            receipt["receipt_persistence_error"]={"type":type(error).__name__,"message":str(error)[:256]}
            if primary is None:primary=error
    if primary is not None:raise NativeFailure("Original context failed; available original evidence retained",receipt) from primary
    return outputs,receipt

