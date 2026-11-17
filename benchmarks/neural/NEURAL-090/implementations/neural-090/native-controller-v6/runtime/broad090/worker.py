"""Actual isolated frozen-reference entry; no evaluator source or targets mounted."""
from pathlib import Path
import io,os
from programme.contracts import Pin,Asset,need
from .custody import Ledger,Accounting,open_pinned,write_fresh,encoded,stable
from .catalogue import exact_json
from .views import ArmViews
from .models import fit_and_predict

def reference(source_root,runtime_manifest,view_root,manifest_asset,output_root,seed,device,limits):
    ledger=Ledger();account=Accounting(limits['read_bytes'],limits['write_bytes']);f=None;result=None
    from .runtime_source import verify_runtime,verify_loaded_modules
    source_manifest=verify_runtime(source_root,runtime_manifest,account,ledger)
    verify_loaded_modules(source_root,source_manifest)
    try:
        f,before=open_pinned(view_root,manifest_asset,account,ledger);account.charge('read',manifest_asset.pin.bytes+1)
        body=f.read(manifest_asset.pin.bytes+1);need(len(body)==manifest_asset.pin.bytes and stable(before,os.fstat(f.fileno())),'whole stable view manifest')
        manifest=exact_json(body)
    except BaseException as e:ledger.propagated('worker-view-admission',e)
    finally:
        if f is not None:ledger.attempt('worker-view-close',f.close)
    ledger.raise_first();out=Path(output_root);need(not out.exists(),'fresh actor output');out.mkdir(mode=0o700)
    views=ArmViews(view_root,manifest,account,ledger)
    def checkpoint(kind,state,details):
        import torch
        buffer=io.BytesIO();torch.save({'state_dict':state,'details':details},buffer)
        return write_fresh(out/(kind+'.pt'),buffer.getvalue(),account,ledger).json()
    try:
        result=fit_and_predict(source_root,manifest['arm'],seed,views,device,checkpoint)
        verify_loaded_modules(source_root,source_manifest)
        # Logical bytes are not physical process/RSS/GPU/native qualification.
        receipt=write_fresh(out/'logical-resource.json',encoded(account.report()),account,ledger)
        prediction={'schema':'n090-prediction-v1','predictions':result['predictions'],'source_checkpoint':result['source_checkpoint'],
                    'final_checkpoint':result['final_checkpoint'],'resource_receipt':receipt.json()}
        pin=write_fresh(out/'prediction.json',encoded(prediction),account,ledger)
        write_fresh(out/'reference-provenance.json',encoded({k:v for k,v in result.items() if k!='predictions'}),account,ledger)
        return Asset('prediction.json',pin)
    except BaseException as e:ledger.propagated('actual-reference-worker',e);ledger.raise_first()
