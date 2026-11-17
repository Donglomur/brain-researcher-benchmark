"""Exact original public bundle/identity validators, bound by source pin.

Only metadata grammar is inspected here; no NPZ/header/data reader is invoked.
"""
from .common import need, closed, integer, bounded_size
from .schema import check

def validate_jobs(rows):
    """Original ABI row grammar; reference equality is checked by its caller."""
    need(type(rows) is list and 0 < len(rows) <= 8192, 'complete original ABI job sequence')
    seen = set()
    for row in rows:
        closed(row, ('job_id','kind','task_expected_outputs','report_cap_bytes','bundles','identity_schema'))
        need(type(row['job_id']) is str and 0 < len(row['job_id']) <= 256 and row['job_id'] not in seen,
             'unique ordered original job identities')
        seen.add(row['job_id'])
        need(type(row['kind']) is str and row['kind'] in ('numeric','native','artifact'), 'original kind domain')
        bounded_size(row['task_expected_outputs'])
        need(bool(row['task_expected_outputs']), 'original nonempty output declaration')
        integer(row['report_cap_bytes'],1)
        need(type(row['bundles']) is list and 0 < len(row['bundles']) <= 8192, 'complete selected bundle schema')
        names = set()
        for bundle in row['bundles']:
            closed(bundle, ('schema','cap_bytes')); integer(bundle['cap_bytes'],1)
            _bundle_schema(bundle['schema'])
            need(not names.intersection(bundle['schema']), 'unique original candidate output names')
            names.update(bundle['schema'])
        _json_shape(row['identity_schema'])
        need(row['identity_schema']['type']=='object' and 'scientific_identity' in row['identity_schema']['required'],
             'complete scientific and task-specific identities')
        need(not names.intersection(row['identity_schema']['required']), 'identities cannot overwrite numeric outputs')
    return rows

def _json_shape(schema,depth=0):
    """Closed bounded literal public identity grammar, with no refs or callbacks."""
    need(type(schema) is dict and depth<=16,"finite public identity schema")
    kind=schema.get('type')
    if kind=='object':
        closed(schema,('type','properties','required','additionalProperties'))
        need(schema['additionalProperties'] is False and type(schema['properties']) is dict and
             type(schema['required']) is list and len(schema['properties'])<=128 and
             len(set(schema['required']))==len(schema['required']) and
             set(schema['required'])==set(schema['properties']),'closed complete identity fields')
        for key,spec in schema['properties'].items():
            need(type(key) is str and 0<len(key)<=256,'bounded literal identity field')
            _json_shape(spec,depth+1)
    elif kind=='array':
        closed(schema,('type','items','minItems','maxItems'))
        integer(schema['minItems']);integer(schema['maxItems']);need(schema['minItems']<=schema['maxItems']<=8192,'finite identity array')
        _json_shape(schema['items'],depth+1)
    elif kind=='string':
        closed(schema,('type','minLength','maxLength'))
        integer(schema['minLength']);integer(schema['maxLength']);need(schema['minLength']<=schema['maxLength']<=4096,'finite identity string')
    elif kind in ('integer','number'):
        closed(schema,('type','minimum','maximum'))
        # Source-owned schema.check rejects nonfinite values and boolean numbers.
        for value in (schema['minimum'],schema['maximum']):check(value,{'type':'number'})
        need(schema['minimum']<=schema['maximum'],'ordered finite identity bounds')
    else:
        closed(schema,('type',));need(kind in ('boolean','null'),'closed original JSON identity type')

def _bundle_schema(shapes):
    need(type(shapes) is dict and 0<len(shapes)<=8192,'complete finite original array-name schema')
    for name,spec in shapes.items():
        need(type(name) is str and 0<len(name)<=256 and '/' not in name and '\\' not in name and name not in ('.','..'),
             'ordinary original NPZ member name')
        closed(spec,('shape','dtype'))
        need(type(spec['shape']) is list and len(spec['shape'])<=32,'original bounded rank')
        for n in spec['shape']:integer(n)
        need(type(spec['dtype']) is str and 0<len(spec['dtype'])<=64,'literal original dtype')
