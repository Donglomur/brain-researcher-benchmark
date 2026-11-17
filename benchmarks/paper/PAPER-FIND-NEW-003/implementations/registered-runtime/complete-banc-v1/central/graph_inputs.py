"""Complete original table readers and exact compact/native joins.

Only qualified worker processes call these functions. No samples, inferred ID
casts, column dropping, row filtering, weight changes or answer caches.
"""
from dataclasses import fields
from banc_runtime.codec import need,parse,pin
from banc_graph_core.banc_graph import Metadata,Edge,RawTable,Binding,Limits,NativeParameters
from banc_runtime.execution import prepare_native_request,native_r_job
from banc_runtime.r_bridge import decode_table,serialize_native_r_job
from .io import exact_fields,read

def original_table(root,spec,role,meter,cap):
    exact_fields(spec,('descriptor','format'),'whole original table')
    raw=read(root,spec['descriptor'],meter,cap)
    if spec['format']=='typed_R_table_v1':
        envelope=parse(raw);columns,rows,types=decode_table(envelope,role=role)
        # The envelope names the original source body. The independently
        # qualified input view must bind the conversion, never just its header.
        origin=envelope['declared_content_sha256']
    elif spec['format'] in ('arrow_feather','arrow_parquet'):
        import io
        if spec['format']=='arrow_feather':
            import pyarrow.feather
            table=pyarrow.feather.read_table(io.BytesIO(raw))
        else:
            import pyarrow.parquet
            table=pyarrow.parquet.read_table(io.BytesIO(raw))
        columns=tuple(table.column_names)
        need(len(set(columns))==len(columns),'original unique column names')
        # to_pylist preserves Python str/int/bool and null; no astype/stringify.
        records=table.to_pylist();rows=tuple(tuple(r[c] for c in columns) for r in records)
        origin=pin(raw)['sha256'];types=None
    else:raise ValueError('unsupported original table representation; no inferred adapter')
    meter.admit_rows(len(rows));return RawTable(tuple(columns),tuple(rows),origin),types

def compact(table,cls):
    names=set(table.columns);required={'root_id'} if cls is Metadata else {'pre','post','count','norm'}
    need(required<=names,'complete original mandatory columns')
    result=[]
    for row in table.rows:
        d=dict(zip(table.columns,row));args={}
        for f in fields(cls):
            key='id' if f.name=='native_id' else f.name
            args[f.name]=d.get(key)
        result.append(cls(**args))
    return tuple(result)

def graph_request(root,parameters,program,inputs,meter,cap):
    exact_fields(parameters,('metadata','edges','binding','limits','native','source_ids','target_ids','silenced_ids','neck_metadata','seed_requests','metadata_types','edge_types'),'complete native request parameters')
    for key,role in (('metadata','banc_metadata'),('edges','banc_edges')):
        name=parameters[key]['descriptor']['path']
        need(name in inputs and inputs[name]['role']==role and inputs[name]['descriptor']==parameters[key]['descriptor'],'native table bound to exact admitted role')
    meta,mt=original_table(root,parameters['metadata'],'metadata',meter,cap)
    edges,et=original_table(root,parameters['edges'],'edges',meter,cap)
    binding=Binding(**parameters['binding'])
    need(binding.metadata_sha256==meta.declared_content_sha256 and binding.edges_sha256==edges.declared_content_sha256,'full source table provenance')
    limits=Limits(**parameters['limits']);native=dict(parameters['native'])
    for name in ('inhibitory_nts','excluded_nts','r_neg_neurotransmitters'):
        if native.get(name) is not None:native[name]=tuple(native[name])
    neck=None;neck_sha=None
    if parameters['neck_metadata'] is not None:
        spec=parameters['neck_metadata'];name=spec['descriptor']['path']
        need(name in inputs and inputs[name]['role']=='seed_and_neck_maps','full original neck provenance')
        nr,_=original_table(root,spec,'metadata',meter,cap)
        # The accepted graph constructor's neck contract is the original
        # (root_id, cell_type) pairs, not compact Metadata objects.
        nc={name:i for i,name in enumerate(nr.columns)}
        need('cell_type' in nc,'original neck cell_type column required')
        neck=tuple((row[nc['root_id']],row[nc['cell_type']]) for row in nr.rows)
        neck_sha=nr.declared_content_sha256
    request=prepare_native_request(compact(meta,Metadata),compact(edges,Edge),binding,
      graph_variant=program['graph_variant'],operator_branch=program['operator_branch'],parameters=NativeParameters(**native),
      raw_metadata=meta,raw_edges=edges,source_ids=tuple(parameters['source_ids']),target_ids=tuple(parameters['target_ids']),
      silenced_ids=tuple(parameters['silenced_ids']),neck_metadata=neck,neck_metadata_sha256=neck_sha,limits=limits)
    seeds=tuple((r[0],tuple(r[1]),tuple(r[2])) for r in parameters['seed_requests'])
    mts=tuple(parameters['metadata_types']);ets=tuple(parameters['edge_types'])
    need(mt is None or mts==mt,'original metadata dtype remains exact')
    need(et is None or ets==et,'original edge dtype remains exact')
    return request,seeds,mts,ets

def r_wire(request,seeds,mt,et,identity):
    job=native_r_job(request,seeds,metadata_types=mt,edge_types=et,program_identity=identity)
    return serialize_native_r_job(job,program_identity=identity)
