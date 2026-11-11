"""Fixed closed operator grammar, before semantic or live-owner admission."""
import math
import re
from .operator_schema_data import DATA
from .operator_intake import require,canonical
from .precommit_records import validate_type as _original_type

def _json_schema(schema,value,root=None):
    root=schema if root is None else root
    if '$ref'in schema:
        parts=schema['$ref'].split('/')
        require(parts[0]=='#','no external schema body resolution')
        target=root
        for p in parts[1:]:target=target[p.replace('~1','/').replace('~0','~')]
        return _json_schema(target,value,root)
    for key in ('oneOf','anyOf'):
        if key in schema:
            passed=0
            for branch in schema[key]:
                try:_json_schema(branch,value,root)
                except (ValueError,TypeError,KeyError):pass
                else:passed+=1
            require(passed==1 if key=='oneOf' else passed>=1,'exact original union branch')
    if 'allOf'in schema:
        for branch in schema['allOf']:_json_schema(branch,value,root)
    if 'const'in schema:require(type(value)is type(schema['const'])and value==schema['const'],'exact original constant')
    if 'enum'in schema:require(any(type(value)is type(x)and value==x for x in schema['enum']),'exact original enum')
    kind=schema.get('type')
    if kind=='object':
        require(type(value)is dict,'exact original object')
        fields=schema.get('properties',{})
        require(set(schema.get('required',[]))<=set(value),'all original required fields')
        if schema.get('additionalProperties')is False:require(set(value)<=set(fields),'no extra original fields')
        for k,v in value.items():
            if k in fields:_json_schema(fields[k],v,root)
    elif kind=='array':
        require(type(value)is list,'exact original list')
        require(schema.get('minItems',0)<=len(value)<=schema.get('maxItems',9007199254740991),'original list extent')
        if schema.get('uniqueItems'):require(len({canonical(x)for x in value})==len(value),'unique original items')
        for item in value:_json_schema(schema.get('items',{}),item,root)
    elif kind=='string':
        require(type(value)is str,'exact original text')
        require(schema.get('minLength',0)<=len(value)<=schema.get('maxLength',9007199254740991),'original string extent')
        if 'pattern'in schema:require(re.search(schema['pattern'],value)is not None,'original string pattern')
    elif kind in ('integer','number'):
        require(type(value)is int if kind=='integer' else type(value)in (int,float),'exact original numeric type')
        require(math.isfinite(value),'finite original scalar')
        for key,fn in (('minimum',lambda x,b:x>=b),('maximum',lambda x,b:x<=b),('exclusiveMinimum',lambda x,b:x>b),('exclusiveMaximum',lambda x,b:x<b)):
            if key in schema:require(fn(value,schema[key]),'original numeric bound')
    elif kind=='boolean':require(type(value)is bool,'exact original bool')
    elif kind=='null':require(value is None,'exact original null')

def _layout(spec,value):
    if type(spec)is str:
        match=re.fullmatch(r'(.+)\[(\d+):(\d+)\]',spec)
        if match:
            require(type(value)is list and int(match[2])<=len(value)<=int(match[3]),'fixed typed list extent')
            for item in value:_layout(match[1],item)
            return
        if spec.startswith('literal:'):
            name=spec.split(':',1)[1]
            record=DATA['native_records'].get(name)or DATA['records'].get(name)
            if record is not None:return _layout({'literal':record['schema_literal']},value)
            # The original base validator owns its original literal aliases.
            return _original_type(spec,value)
        if spec in ('OperatorQualificationCaseV1','OriginalOperatorQualificationObservationV1'):
            return validate_operator_record(spec,value)
        if spec in DATA['records']:return _layout(DATA['records'][spec],value)
        if spec in DATA['layouts']:return _layout(DATA['layouts'][spec],value)
        if spec in DATA['native_records']:return _layout(DATA['native_records'][spec],value)
        if spec in DATA['native_primitives']:return _layout(DATA['native_primitives'][spec],value)
        if spec=='SHA256':require(type(value)is str and re.fullmatch('[0-9a-f]{64}',value)is not None,'exact SHA256');return
        # This is the fixed original validator, never a caller callback/type resolver.
        return _original_type(spec,value)
    if type(spec)is list or spec is None or type(spec)in (int,bool):
        require(type(value)is type(spec)and value==spec,'exact finite observation literal');return
    require(type(spec)is dict,'closed source-owned type expression')
    if 'literal'in spec:require(type(value)is type(spec['literal'])and value==spec['literal'],'exact literal');return
    if 'enum'in spec:require(any(type(value)is type(x)and value==x for x in spec['enum']),'closed enum');return
    if 'integer'in spec:
        s=spec['integer'];require(type(value)is int and s['min']<=value<=s['max'],'closed integer extent');return
    if 'record'in spec:spec={'kind':'closed_record','fields':spec['record']}
    if 'ordered_list'in spec or 'ordered_unique_list'in spec:
        key='ordered_unique_list'if 'ordered_unique_list'in spec else'ordered_list'
        require(type(value)is list and len(value)<=spec.get('max',8192),'complete bounded ordered list')
        for v in value:_layout(spec[key],v)
        if key=='ordered_unique_list':require(len({canonical(x)for x in value})==len(value),'unique original values')
        return
    kind=spec.get('kind')
    if kind=='closed_discriminated_union':
        require(type(value)is dict and value.get(spec['discriminator'])in spec['branches'],'closed programme branch')
        return _layout(spec['branches'][value[spec['discriminator']]],value)
    if kind=='closed_record' or kind is None and 'fields'not in spec:
        fields=spec['fields']if kind=='closed_record'else spec
        require(type(value)is dict and set(value)==set(fields),'exact complete closed fields')
        for k,t in fields.items():
            if k=='schema'and 'schema_literal'in spec:_layout({'literal':spec['schema_literal']},value[k])
            else:_layout(t,value[k])
    elif kind=='literal':_layout({'literal':spec['value']},value)
    elif kind=='enum':_layout({'enum':spec['values']},value)
    elif kind=='bounded_list':
        require(type(value)is list and spec['minimum']<=len(value)<=spec['maximum'],'fixed full list')
        for item in value:_layout(spec['item'],item)
    elif kind=='tuple':
        require(type(value)is list and len(value)==len(spec['items']),'exact tuple extent')
        for t,v in zip(spec['items'],value):_layout(t,v)
    elif kind=='closed_map':
        require(type(value)is dict and set(value)==set(spec['keys']),'exact complete dimensions')
        for v in value.values():_layout(spec['values'],v)
    elif kind=='exact_json_schema':_json_schema(spec['schema'],value)
    elif kind=='integer':
        require(type(value)is int and spec['minimum']<=value<=spec['maximum'],'fixed integer')
    elif kind in ('string','absolute_single_argv_element'):
        require(type(value)is str,'exact text')
        lo=spec.get('minimum_length',spec.get('minimum_utf8_bytes',0));hi=spec.get('maximum_length',spec.get('maximum_utf8_bytes',4096))
        require(lo<=len(value.encode('utf-8'))<=hi,'fixed text bound')
        if 'pattern'in spec:require(re.fullmatch(spec['pattern'],value)is not None,'fixed text pattern')
        if kind=='absolute_single_argv_element' or spec.get('constraint','').startswith('canonical absolute'):
            require(value.startswith('/')and not any(x in ('','.','..')for x in value.split('/')[1:]),'literal canonical absolute command/path')
        if spec.get('constraint','').startswith('no slash'):require('/'not in value and value not in ('.','..'),'literal path component')
    else:raise ValueError('unresolved fixed operator layout '+str(kind))

def validate_operator_record(name,body):
    if name=='OperatorEntrySelectionV3':
        require(type(body)is dict and set(body)==set(DATA['records']['OperatorEntrySelectionV1']['fields'])|{'native_evidence'} and
                body['schema']=='four_operator_entry_selection_v3','single active full protected entry selection')
        static=body['static_values'];validate_operator_record('OperatorStaticSelectionV2',static)
        # Only semantic validation is projected to the retained original V2;
        # the actual immutable V3 body/descriptor and live owner are untouched.
        original={**body,'schema':'four_operator_entry_selection_v2',
                  'static_values':{k:v for k,v in static.items()if k!='agent_input_selection'}}
        original['static_values']['schema']='four_operator_static_selection_v1'
        validate_operator_record('OperatorEntrySelectionV2',original)
        return body
    if name=='OperatorEntrySelectionV2':
        require(type(body)is dict and set(body)==set(DATA['records']['OperatorEntrySelectionV1']['fields'])|{'native_evidence'} and
                body['schema']=='four_operator_entry_selection_v2','closed versioned protected entry selection')
        # Semantic validation projection only: the original V2 raw bytes and
        # descriptor remain the invocation identity; no old capture is minted.
        original={k:v for k,v in body.items()if k!='native_evidence'}
        original['schema']='four_operator_entry_selection_v1'
        validate_operator_record('OperatorEntrySelectionV1',original)
        from .native_qualification_v4 import validate_native_evidence_bundle_v4
        validate_native_evidence_bundle_v4(body['native_evidence'])
        return body
    require(name in DATA['records'],'closed operator record family')
    canonical(body)
    if name in ('OperatorQualificationCaseV1','OriginalOperatorQualificationObservationV1'):
        fields=DATA['records'][name]['fields'];require(type(body)is dict and set(body)==set(fields),'complete case fields')
        for k,t in fields.items():
            if k!='observation':_layout(t,body[k])
        require(body['case']in DATA['observations'],'fixed original case')
        _layout({'kind':'closed_record','fields':DATA['observations'][body['case']]['fields']},body['observation'])
    else:_layout(DATA['records'][name],body)
    return body
