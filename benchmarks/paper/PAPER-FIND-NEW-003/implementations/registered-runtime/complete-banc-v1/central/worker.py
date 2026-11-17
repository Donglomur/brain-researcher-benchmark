"""Closed native producer worker, invoked only inside the qualified enclosure.

This is not an actor entrypoint. It has no callable/plugin dispatch. Original
constructors/scripts retain their literal branch and failure behavior.
"""
from pathlib import Path
from dataclasses import asdict,is_dataclass
import sys,time,subprocess
from banc_runtime.codec import parse,encode,need,pin
from banc_runtime.resources import Meter,Limits
from banc_runtime.native_python import run_python_literal,PY_SOURCE
from banc_graph_core.banc_graph import run_centrality
from .graph_inputs import graph_request,r_wire
from .io import metadata,write_json,exact_fields,read,read_json

def resolve(value,root,inputs,meter,cap):
    """Closed selectors for original or actual upstream data, never Python/R."""
    if type(value) is dict and '$input' in value:
        exact_fields(value,('$input','path'),'data selector')
        name=value['$input'];need(name in inputs and type(value['path']) is list,'exact staged full input')
        result=read_json(root,inputs[name]['descriptor'],meter,cap)
        for key in value['path']:
            need(type(key) in (str,int),'explicit JSON key/index')
            if type(key) is str:need(type(result) is dict and key in result,'present original JSON column')
            else:need(type(result) is list and 0<=key<len(result),'present original JSON row')
            result=result[key]
        return result
    if type(value) is dict:return {k:resolve(v,root,inputs,meter,cap) for k,v in value.items()}
    if type(value) is list:return [resolve(v,root,inputs,meter,cap) for v in value]
    return value

def data_selector(value):return type(value) is dict and set(value)=={'$input','path'}

def plain(value):
    if is_dataclass(value):return plain(asdict(value))
    if type(value) is dict:return {k:plain(v) for k,v in value.items()}
    if type(value) in (tuple,list):return [plain(v) for v in value]
    if hasattr(value,'tolist'):return plain(value.tolist())
    return value

def execute(control,root,source_root,meter):
    exact_fields(control,('schema','request','program','input_bindings','native_authority','limits','Rscript'),'native worker control')
    need(control['schema']=='banc_complete_native_worker_v1','source-owned closed worker')
    q=control['request'];kind=q['kind'];p=q['parameters'];program=control['program'];cap=control['limits']['read_bytes']
    need(kind in ('influence_python','influence_R_wire','sensory_R_wires','sensory_python','original_figure','native_statistics','centrality'),'closed native producer')
    if kind=='native_statistics':
        # Actual upstream/original data, not numerical answers embedded in a
        # request. The original source owns the statistical method itself.
        data_fields={'rows','arguments','hm','diagonal','off_diagonal','successes','total'}&set(p)
        need(data_fields and all(data_selector(p[k]) for k in data_fields),'statistical operands must come from actual captured data')
    if kind=='sensory_R_wires':need(data_selector(p['sensory_job']),'sensory membership/lookup body comes from source-bound data')
    if kind=='original_figure':exact_fields(p,('script',),'exact original script request')
    p=resolve(p,root,control['input_bindings'],meter,cap)
    if kind=='sensory_python':
        from .sensory_python import execute_sensory
        return execute_sensory(p,control,root,source_root,meter)
    if kind in ('influence_python','influence_R_wire','centrality'):
        gp=p
        if kind=='centrality':
            exact_fields(p,('graph','centrality_branch'),'explicit source centrality discrepancy')
            gp=p['graph']
        request,seeds,mt,et=graph_request(root,gp,program,control['input_bindings'],meter,cap)
        if kind=='centrality':
            # All graph endpoints and both directed source modes are retained.
            from banc_graph_core.banc_graph import Metadata,Edge,Binding,Limits as GLimits
            from .graph_inputs import compact
            value=run_centrality(compact(request.raw_metadata,Metadata),compact(request.raw_edges,Edge),request.binding,
              branch=p['centrality_branch'],limits=GLimits(**gp['limits']))
            return plain(value)
        if kind=='influence_python':
            from banc_runtime.native_python import PY_BYTES,PY_SHA
            raw=read(source_root,{'path':PY_SOURCE,'bytes':PY_BYTES,'sha256':PY_SHA},meter,cap)
            return plain(run_python_literal(request,raw_source=raw,sqlite_path=root/'native-original.sqlite',
              max_sqlite_bytes=control['limits']['file_bytes'],seed_requests=seeds,meter=meter))
        wires=[r_wire(request,seeds,mt,et,program['selection_identity'])]
        rjob={}
    elif kind=='sensory_R_wires':
        exact_fields(p,('requests','sensory_job'),'full sensory request')
        need(type(p['requests']) is list and len(p['requests'])==3,'all3 threshold requests')
        wires=[]
        for params,threshold in zip(p['requests'],(3,5,10)):
            need(params['native']['count_thresh']==threshold,'exact sensory threshold order')
            request,seeds,mt,et=graph_request(root,params,program,control['input_bindings'],meter,cap)
            wires.append(r_wire(request,seeds,mt,et,program['selection_identity']))
        rjob=p['sensory_job']
    else:wires=[];rjob=p
    # The whole worker is already under the same process group, CPU/RSS/disk
    # enclosure and deadline. R is a concrete child; its errors propagate.
    wire_descriptors=[]
    for i,raw in enumerate(wires):
        from .io import write
        d=write(root,'native-wire-'+str(i)+'.json',raw,meter)
        envelope=parse(raw)
        wire_descriptors.append({'file':d,'payload_sha256':envelope['sha256']})
    dispatch={'schema':'banc_R_dispatch_v1','kind':kind,'program_identity':program['selection_identity'],
      'job':rjob,'wires':wire_descriptors,'native_authority':control['native_authority'],
      'source_root':str(source_root),'output_path':str(root/'result.json')}
    write_json(root,'r-dispatch.json',dispatch,meter)
    result=subprocess.run([control['Rscript'],'--vanilla',str(source_root.parent/'central/native_dispatch.R'),str(root/'r-dispatch.json')],
      cwd=root,check=False)
    need(result.returncode==0,'original R/native producer failed:'+str(result.returncode))
    # No R result recoding: the dispatcher writes the original structured result.
    return None

def main():
    need(len(sys.argv)==2,'one independently staged worker control')
    # External resource enclosure is mandatory; this meter is a subordinate
    # logical meter, charged back by the parent receipt, never a fresh grant.
    bootstrap=Meter(Limits(2097152,2097152,1000000,1000000,1000,time.monotonic_ns()+30_000_000_000))
    c=parse(metadata(sys.argv[1],bootstrap,1048576));l=c['limits']
    meter=Meter(Limits(l['read_bytes'],l['output_bytes'],l['row_count'],l['pair_work'],l['jobs'],time.monotonic_ns()+l['wall_seconds']*10**9))
    meter.reserve_read(bootstrap.read_reserved);meter.complete_read(bootstrap.read_completed)
    root=Path.cwd();value=execute(c,root,Path('/programme/runtime'),meter)
    if value is not None:write_json(root,'result.json',value,meter)
    write_json(root,'worker-costs.json',meter.report(),meter)

if __name__=='__main__':main()
