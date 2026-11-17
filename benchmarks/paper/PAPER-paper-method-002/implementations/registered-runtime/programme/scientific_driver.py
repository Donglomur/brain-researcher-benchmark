"""Fixed reviewed scientific producer entry, for a separately admitted OS child."""
from importlib import import_module
from runtime.strict import Root,require,canonical_bytes,digest
from scientific.campaign import DISPATCH,LIMITS,product_extent
from scientific.protocol import JobContext
from scientific.output_support import require_full_support
from runtime.programme import PRODUCTS
from runtime.full_scientific_bindings import Failures

def run_exact_job(job,input_path,output_path):
    require(input_path=='/inputs'and output_path=='/output','fixed scientific mounts')
    require(job['group']in DISPATCH and job['required']is True,'full selected source family')
    require(job['route']=='prospective_full_scientific_source_v1','legacy route cannot imply larger source limits')
    require(set(job['producer_limits'])==set(LIMITS),'complete source allowances')
    outputs=job['output_contract']['outputs']
    require([p['artifact_id']for p in outputs]==list(PRODUCTS[job['group']]),'complete fixed product roster before scientific imports')
    require_full_support(job['group'],outputs)
    total=sum(product_extent(p)for p in outputs)+job['metadata_limits']['receipt_bytes']
    require(total<=job['producer_limits']['output_bytes'],'full output admission before any scientific import')
    require(job['native_deadline_ns']>0,'actual original parent-issued deadline required')
    # Job/metadata does not issue native authority. The enclosing source-owned
    # controller must supply actual immutable mounts, source ownership, original
    # resource grant, process birth/waits and target isolation before this child.
    owner=Failures()
    try:
        inputs=owner.own(Root(input_path,private=True));outputs_root=owner.own(Root(output_path,private=True))
        ctx=JobContext(job,inputs,outputs_root)
        module,function=DISPATCH[job['group']]
        consumer=getattr(import_module(module),function)
        result=consumer(ctx)
        require(result is None,'scientific source must publish every original product, not return a success value')
        ctx.finish()
    except BaseException as error:owner.catch(error)
    owner.close_all();owner.raise_first()
