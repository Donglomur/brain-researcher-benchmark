"""Exact ordinary-scalar Python -> JSON -> R table bridge, source only.

Column types are selected explicitly. Unsupported original types are refused;
the bridge does not infer factors, integer64, dates or aliases. Actual native
dtype/historical parity remains an independent qualification.
"""
import json
import struct
from .codec import need,parse,pin,finite_number
from banc_graph_core.banc_graph import R_SOURCE,PY_SOURCE,WRAPPER_SOURCE

R_TYPES=('character','logical','integer32','binary64')
R_BRANCHES=('captured_R_unsigned_literal','captured_R_signed_labelled_literal','R_to_Python_literal_wrapper')


def wire_encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')


def sha(value):
    need(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value), 'SHA256 binding')


def text(value):
    need(type(value) is str and '\0' not in value, 'ordinary R UTF-8 string, not numeric ID/coercion')
    value.encode('utf8')
    return value


def source_members():
    result={key:{'path':'source/'+row[0],'bytes':row[1],'sha256':row[2]}
            for key,row in (('R',R_SOURCE),('wrapper',WRAPPER_SOURCE),('Python',PY_SOURCE))}
    result['normalizer']={'path':'source/captured-functions/calculate_influence_norms.R',
        'bytes':3342,'sha256':'ad7ee89734be62d670f384365e074aa0d3b6aaefd2b38cea19e70d7d5913e895'}
    return result


def typed_table(table, types, *, role):
    need(type(types) is tuple and len(types)==len(table.columns) and all(t in R_TYPES for t in types),
         'explicit type for every original column')
    need(type(table.columns) is tuple and table.columns and len(set(table.columns))==len(table.columns),
         'original unique ordered columns')
    for name in table.columns:need(text(name)!='', 'nonempty original column')
    need(type(table.rows) is tuple and len(table.rows)<=2147483647, 'ordinary R row domain')
    sha(table.declared_content_sha256)
    columns=[{'name':name,'r_type':kind} for name,kind in zip(table.columns,types)]
    def cell(value,kind):
        if value is None:return None
        if kind=='character':return text(value)
        if kind=='logical':need(type(value) is bool,'exact logical cell');return value
        if kind=='integer32':
            need(type(value) is int and -2147483647<=value<=2147483647,
                 'exact R integer excluding reserved NA sentinel; no integer64 coercion')
            return str(value)
        need(type(value) is float and finite_number(value), 'exact finite binary64 cell; no inferred integer promotion')
        return struct.pack('>d',value).hex()
    rows=[]
    for row in table.rows:
        need(type(row) is tuple and len(row)==len(columns),'complete original row width')
        rows.append([cell(v,t) for v,t in zip(row,types)])
    body=wire_encode({'schema':'banc_typed_R_table_v1','role':role,'columns':columns,'rows':rows,'row_count':len(rows)})
    result={'schema':'banc_R_table_envelope_v1','payload_json':body.decode('ascii'),
            **pin(body),'declared_content_sha256':table.declared_content_sha256}
    decode_table(result,role=role)
    return result


def decode_table(envelope, *, role):
    need(type(envelope) is dict and set(envelope)=={'schema','payload_json','bytes','sha256','declared_content_sha256'}, 'exact typed table envelope')
    need(envelope['schema']=='banc_R_table_envelope_v1' and type(envelope['payload_json']) is str,'typed table schema')
    raw=envelope['payload_json'].encode('ascii');sha(envelope['declared_content_sha256'])
    need(type(envelope['bytes']) is int and pin(raw)=={'bytes':envelope['bytes'],'sha256':envelope['sha256']},'table wire identity')
    table=parse(raw)
    need(type(table) is dict and set(table)=={'schema','role','columns','rows','row_count'} and
         table['schema']=='banc_typed_R_table_v1' and table['role']==role,'typed table role/body')
    columns=table['columns'];rows=table['rows']
    need(type(columns) is list and columns and all(type(c) is dict and set(c)=={'name','r_type'} for c in columns),'exact column schema')
    names=tuple(text(c['name']) for c in columns);types=tuple(c['r_type'] for c in columns)
    need(all(names) and len(names)==len(set(names)) and all(t in R_TYPES for t in types),'ordered unique typed columns')
    need(type(rows) is list and type(table['row_count']) is int and len(rows)==table['row_count']<=2147483647,'complete row count')
    def cell(v,t):
        if v is None:return None
        if t=='character':return text(v)
        if t=='logical':need(type(v) is bool,'logical wire cell');return v
        if t=='integer32':
            need(type(v) is str,'decimal integer wire string')
            n=int(v);need(str(n)==v and -2147483647<=n<=2147483647,'canonical finite R integer');return n
        need(type(v) is str and len(v)==16 and all(x in '0123456789abcdef' for x in v),'binary64 big-endian hexadecimal')
        n=struct.unpack('>d',bytes.fromhex(v))[0];need(finite_number(n),'finite binary64 wire value');return n
    result=[]
    for row in rows:
        need(type(row) is list and len(row)==len(columns),'complete ordered wire row')
        result.append(tuple(cell(v,t) for v,t in zip(row,types)))
    required={'root_id':'character'} if role=='metadata' else {'pre':'character','post':'character','norm':'binary64'}
    typed=dict(zip(names,types))
    need(all(typed.get(k)==v for k,v in required.items()),'source ID/norm dtype contract')
    if role=='metadata':
        need('id' not in typed or typed['id']=='character','id stays a separate optional string column')
        need('top_nt' not in typed or typed['top_nt']=='character','transmitter label type')
    else:need(typed.get('count') in ('integer32','binary64'),'count stays numeric and distinct from norm')
    idcols=('root_id',) if role=='metadata' else ('pre','post')
    need(all(row[names.index(k)] is not None for row in result for k in idcols),'required native IDs never null')
    return names,tuple(result),types


def make_native_r_job(request,seed_requests,*,metadata_types,edge_types,program_identity):
    sha(program_identity)
    need(request.operator_branch in R_BRANCHES and request.raw_metadata is not None and request.raw_edges is not None,'complete R-side request')
    need(type(seed_requests) is tuple and seed_requests and all(type(x) is tuple and len(x)==3 for x in seed_requests),'complete named native requests')
    names=[]
    for name,ids,silenced in seed_requests:
        names.append(text(name));need(type(ids) is tuple and type(silenced) is tuple,'immutable seed/silencing IDs')
        for value in ids+silenced:text(value)
        need(set(silenced)<=set(request.silenced_ids),'declared silencing support')
    need(len(names)==len(set(names)) and set(x for _,ids,_ in seed_requests for x in ids)==set(request.source_ids),'all declared source IDs/unique requests')
    p=request.parameters
    selection={'program_identity':program_identity,'metadata_sha256':request.binding.metadata_sha256,
        'edges_sha256':request.binding.edges_sha256,'materialization':request.binding.materialization,
        'synapse_source':request.binding.synapse_source,'annotation_profile':request.binding.annotation_profile,
        'id_cast_profile':request.binding.id_cast_profile,'producer_revision':request.binding.producer_revision}
    job={'schema':'banc_native_r_job_v2','selection':selection,'operator_branch':request.operator_branch,
        'graph_variant':request.graph_variant,'metadata_table':typed_table(request.raw_metadata,metadata_types,role='metadata'),
        'edges_table':typed_table(request.raw_edges,edge_types,role='edges'),'source_members':source_members(),
        'selected_edge_indices':[i+1 for i in request.selected_edge_indices],'edge_indices_base':'one',
        'count_thresh':p.count_thresh,'const':p.const,'signed':p.wrapper_signed if request.operator_branch==R_BRANCHES[2] else request.operator_branch==R_BRANCHES[1],
        'neg_neurotransmitters':list(p.r_neg_neurotransmitters),'seed_requests':[{'seed':n,'seed_ids':list(ids),'silenced_ids':list(s)} for n,ids,s in seed_requests],
        'source_ids':list(request.source_ids),'silenced_ids':list(request.silenced_ids),
        'target_ids':list(request.target_ids),'ordered_node_ids':list(request.ordered_node_ids),'holds':list(request.holds),
        'operator_contract':{'weight':p.syn_weight_measure,'scaling_rule':request.scaling_rule,'response_rule':request.response_rule},
        'qualified_exact_python_import_closure':False,'native_dtype_parity_qualified':False,'scientific_qualification':False}
    validate_native_r_job(job,program_identity=program_identity)
    return job


def validate_native_r_job(job,*,program_identity):
    sha(program_identity)
    fields={'schema','selection','operator_branch','graph_variant','metadata_table','edges_table','source_members','selected_edge_indices','edge_indices_base','count_thresh','const','signed','neg_neurotransmitters','seed_requests','source_ids','silenced_ids','target_ids','ordered_node_ids','holds','operator_contract','qualified_exact_python_import_closure','native_dtype_parity_qualified','scientific_qualification'}
    need(type(job) is dict and set(job)==fields and job['schema']=='banc_native_r_job_v2','exact R job schema')
    s=job['selection'];need(type(s) is dict and set(s)=={'program_identity','metadata_sha256','edges_sha256','materialization','synapse_source','annotation_profile','id_cast_profile','producer_revision'},'exact source/selection binding')
    need(s['program_identity']==program_identity and s['materialization']==888 and s['synapse_source']=='v2' and
         s['annotation_profile']=='canonical_enriched_metadata' and s['id_cast_profile']=='already_plain_string_ids_no_missing_scalars' and
         s['producer_revision']=='2e78ce38e946ab80e120a42f504a019b3a567fef','literal selected annotation/version profile')
    for k in ('metadata_sha256','edges_sha256'):sha(s[k])
    metadata=decode_table(job['metadata_table'],role='metadata');edges=decode_table(job['edges_table'],role='edges')
    need(job['metadata_table']['declared_content_sha256']==s['metadata_sha256'] and job['edges_table']['declared_content_sha256']==s['edges_sha256'],'table/original input binding')
    need(job['source_members']==source_members(),'exact captured native source members')
    need(job['operator_branch'] in R_BRANCHES and job['edge_indices_base']=='one','explicit R operator and row numbering')
    need(job['graph_variant'] in ('full_CNS_source/sequential_supplied_calculator','no_neck_CNS_source/sequential_supplied_calculator','full_CNS_source/parallel_rebuild_default_global','no_neck_CNS_source/parallel_rebuild_default_global'),'literal graph/loop variant')
    ix=job['selected_edge_indices'];need(type(ix) is list and all(type(x) is int and 1<=x<=len(edges[1]) for x in ix) and ix==sorted(set(ix)),'complete ordered distinct selected row indices')
    need(type(job['count_thresh']) is int and 0<=job['count_thresh']<=2147483647 and finite_number(job['const']) and type(job['signed']) is bool,'native constructor scalar domain')
    need(not job['graph_variant'].endswith('/parallel_rebuild_default_global') or job['count_thresh']==5,'original parallel threshold5')
    r=job['operator_branch']!=R_BRANCHES[2];expected_signed=job['operator_branch']==R_BRANCHES[1]
    if r:need(job['signed']==expected_signed,'literal R signed-labelled branch')
    need(job['operator_contract']['weight']==('norm' if r else 'count'),'literal R norm / wrapper count')
    from banc_graph_core.banc_graph import scaling_rule,response_rule
    need(job['operator_contract']=={'weight':'norm' if r else 'count','scaling_rule':scaling_rule(job['operator_branch']),
         'response_rule':response_rule(job['operator_branch'],wrapper_signed=job['signed'])},'exact source operator semantics')
    for field in ('source_ids','silenced_ids','target_ids','ordered_node_ids','holds','neg_neurotransmitters'):
        need(type(job[field]) is list,'ordered string vector')
        for x in job[field]:text(x)
    need(type(job['seed_requests']) is list and job['seed_requests'],'complete request list')
    for row in job['seed_requests']:
        need(type(row) is dict and set(row)=={'seed','seed_ids','silenced_ids'},'exact native seed row');text(row['seed'])
        for key in ('seed_ids','silenced_ids'):
            need(type(row[key]) is list,'seed ID vector')
            for x in row[key]:text(x)
    need(len({x['seed'] for x in job['seed_requests']})==len(job['seed_requests']), 'unique native seed names')
    need(set(v for x in job['seed_requests'] for v in x['seed_ids'])==set(job['source_ids']) and
         set(v for x in job['seed_requests'] for v in x['silenced_ids'])<=set(job['silenced_ids']), 'complete declared source/silencing support')
    need(all(job[k] is False for k in ('qualified_exact_python_import_closure','native_dtype_parity_qualified','scientific_qualification')),'source build cannot grant native/scientific qualification')
    return metadata,edges


def serialize_native_r_job(job,*,program_identity):
    validate_native_r_job(job,program_identity=program_identity)
    body=wire_encode(job)
    return wire_encode({'schema':'banc_native_r_wire_v2','payload_json':body.decode('ascii'),**pin(body)})


def read_native_r_wire(raw,*,program_identity,expected_payload_sha256):
    """Python mirror admits the exact serialized handoff; it runs no R."""
    w=parse(raw);need(type(w) is dict and set(w)=={'schema','payload_json','bytes','sha256'} and w['schema']=='banc_native_r_wire_v2','exact R wire envelope')
    body=w['payload_json'].encode('ascii');sha(expected_payload_sha256)
    need(pin(body)=={'bytes':w['bytes'],'sha256':w['sha256']} and w['sha256']==expected_payload_sha256,'independently selected handoff body')
    job=parse(body);validate_native_r_job(job,program_identity=program_identity)
    return job
