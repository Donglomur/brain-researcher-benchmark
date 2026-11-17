"""Public participant contract selection; no private controller records included."""
from .common import require,keys,encoded,sha

PUBLIC_V3=('PROGRAM_ABI_V3.md','CELL_SCHEMA.json','SELECTED_METHOD_SCHEMA.json','OPERATIONS_SCHEMA.json',
           'BROKER_REQUEST_SCHEMA.json','BROKER_RESPONSE_SCHEMA.json','PREEXPOSURE_POLICY_SCHEMA.json','RESOURCE_POLICY_V1.json')

def selected_documents(source):
    docs={}
    for name in ('TASK.md','POLICY.json','interface.py','CASE_SCHEMA.json','PREDICTION_SCHEMA.json')+PUBLIC_V3:
        path='public/'+name;require(path in source.bodies,'complete public participant ABI v3')
        require(source.descriptors[path]['role']=='public_instructions','public source role')
        docs[name]=source.bodies[path]
    for name in ('TASK.md','POLICY.json','interface.py'):
        require(docs[name]==source.bodies[source.legacy['public/'+name]['path']],'unchanged original public contract')
    for name in ('CASE_SCHEMA.json','PREDICTION_SCHEMA.json'):
        found=[body for path,body in source.bodies.items() if path.startswith('legacy/')and path.endswith('/'+name)]
        require(len(found)==1 and docs[name]==found[0],'unchanged original public schema')
    return docs

def interface_identity(source):
    docs=selected_documents(source)
    return {'schema':'neural055-participant-interface-v4',
            'documents':{name:{'bytes':len(body),'sha256':sha(body)} for name,body in sorted(docs.items())}}

def operations(value,cell,phase):
    keys(value,('schema','cell','phase','records'),('first_error',))
    require(value['schema']=='neural055-participant-operations-v3' and value['cell']==cell and value['phase']==phase,
            'same complete public participant operations ABI')
    require(type(value['records'])is list and all(type(r)is dict for r in value['records']),'participant analysis records')
    require(value.get('first_error') is None or type(value['first_error'])is dict,'typed participant claimed failure')
    return value
