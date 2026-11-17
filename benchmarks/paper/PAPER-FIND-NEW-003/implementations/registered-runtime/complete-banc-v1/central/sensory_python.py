"""Full direct-Python sensory solves followed by the exact captured R normalizer.

This branch does not relabel R magnitudes as signed Python responses. It uses
the accepted full-source sweep/join/panel constructors and real native solvers.
"""
from pathlib import Path
import subprocess,struct
from banc_runtime.codec import need,encode,parse
from banc_runtime.native_python import run_python_literal,PY_SOURCE,PY_BYTES,PY_SHA
from banc_runtime.influence import sensory_sweeps,validate_native_rows,mapped_sensory_rows,full_panel,collect_three_panels
from .graph_inputs import graph_request
from .io import exact_fields,read,write_json,fresh_directory,metadata

def frame(rows):
    need(rows,'nonempty full sensory normalization input')
    columns=list(rows[0]);need(all(set(r)==set(columns) for r in rows),'equal original sensory row schema')
    types=[]
    for c in columns:
        ts={type(r[c]) for r in rows if r[c] is not None}
        need(len(ts)<=1,'no implicit original scalar type promotion')
        t=next(iter(ts),str);need(t in (str,bool,int,float),'ordinary original scalar')
        types.append({str:'character',bool:'logical',int:'integer32',float:'binary64'}[t])
    encoded=[]
    for row in rows:
        encoded.append([None if row[c] is None else (str(row[c]) if t=='integer32' else struct.pack('>d',row[c]).hex() if t=='binary64' else row[c]) for c,t in zip(columns,types)])
    return {'encoding':'typed_frame_v1','columns':[{'name':c,'r_type':t} for c,t in zip(columns,types)],'rows':encoded}

def execute_sensory(p,control,root,source_root,meter):
    exact_fields(p,('requests','mapping','sensory_seed_order','effector_ids','effector_lookup','score_column'),'complete direct Python sensory programme')
    need(len(p['requests'])==3,'all3 complete graph requests')
    source=read(source_root,{'path':PY_SOURCE,'bytes':PY_BYTES,'sha256':PY_SHA},meter,control['limits']['read_bytes'])
    panels=[];lineage=[]
    for params,threshold in zip(p['requests'],(3,5,10)):
        need(params['native']['count_thresh']==threshold,'literal sensory threshold order')
        request,seeds,mt,et=graph_request(root,params,control['program'],control['input_bindings'],meter,control['limits']['read_bytes'])
        metadata_rows=tuple(dict(zip(request.raw_metadata.columns,row)) for row in request.raw_metadata.rows)
        sweeps=sensory_sweeps(metadata_rows,sensory_seed_order=tuple(p['sensory_seed_order']),effector_ids=tuple(p['effector_ids']),
          mapping=p['mapping'],metadata_identity=request.binding.metadata_sha256,operator_branch=request.operator_branch,graph_variant=request.graph_variant,meter=meter)
        selected=tuple(s for s in sweeps if s.threshold==threshold)
        need(tuple((s.seed,s.seed_ids,()) for s in selected)==seeds,'complete original seed cohort; no omitted/group-shortened requests')
        native=run_python_literal(request,raw_source=source,sqlite_path=root/('native-'+str(threshold)+'.sqlite'),
          max_sqlite_bytes=control['limits']['file_bytes'],seed_requests=seeds,meter=meter)
        joined=[]
        for sweep,(name,rows) in zip(selected,native['responses']):
            need(name==sweep.seed,'native seed result order')
            validate_native_rows(rows,ordered_node_ids=request.ordered_node_ids,score_column=p['score_column'],branch=request.operator_branch,
              raw_operator_identity=request.operator_branch,meter=meter)
            joined.extend(mapped_sensory_rows(sweep,rows,p['effector_lookup'],p['mapping'],score_column=p['score_column'],normalizer_seed_count=len(set(sweep.seed_ids)),meter=meter))
        output='normalized-'+str(threshold)+'.json'
        dispatch={'schema':'banc_R_dispatch_v1','kind':'sensory_python_normalization','program_identity':control['program']['selection_identity'],
          'job':{'rows':frame(tuple(joined))},'wires':[],'native_authority':{'wrapper':None,'original_figure':None},
          'source_root':str(source_root),'output_path':str(root/output)}
        controlfile='normalize-'+str(threshold)+'.json';write_json(root,controlfile,dispatch,meter)
        completed=subprocess.run([control['Rscript'],'--vanilla',str(source_root.parent/'central/native_dispatch.R'),str(root/controlfile)],cwd=root,check=False)
        need(completed.returncode==0,'literal source sensory normalizer failed')
        normalized=parse(metadata(root/output,meter,control['limits']['file_bytes']))
        need(type(normalized) is list,'complete original normalized rows')
        panels.append(full_panel(tuple(normalized),mapping=p['mapping'],threshold=threshold,meter=meter))
        lineage.append({'threshold':threshold,'operator_branch':request.operator_branch,'source_sha256':PY_SHA,'native_executed':True})
    result=collect_three_panels(tuple(panels),p['mapping']);result['literal_native_lineage']=lineage
    return result
