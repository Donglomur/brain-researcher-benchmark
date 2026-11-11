"""Fixed bounded native-context metadata codec; no supplied schema/provider.

V2 definitions are a frozen construction preimage. V3 activation remains held.
Callers own/read-admit every buffer before these pure metadata operations.
"""
import re
from .common import need, same
from .backend_json import canonical, parse, scalar_text
from .precommit_records import validate_type
from .backend_native_wire_data import NATIVE_RECORDS, NATIVE_PRIMITIVES, REQUEST_KINDS, REPLY_KINDS

_LIST = re.compile(r'^([A-Za-z][A-Za-z0-9_]*)\[([0-9]+):([0-9]+)\]$')

def validate_native_type(name, value, depth=0):
    need(depth <= 64, 'finite fixed native metadata depth')
    if type(name) is dict:
        spec=name;kind=spec['kind']
    else:
        need(type(name) is str, 'source-owned native type name')
        seq=_LIST.fullmatch(name)
        if seq:
            element,low,high=seq.groups()
            need(type(value) is list and int(low)<=len(value)<=int(high),'closed finite list')
            for child in value:validate_native_type(element,child,depth+1)
            return value
        if name in NATIVE_RECORDS:
            fields=NATIVE_RECORDS[name]['fields']
            need(type(value) is dict and set(value)==set(fields),'all and only fixed native record fields')
            for key,typ in fields.items():validate_native_type(typ,value[key],depth+1)
            return value
        if name not in NATIVE_PRIMITIVES:return validate_type(name,value,depth=depth)
        spec=NATIVE_PRIMITIVES[name];kind=spec['kind']
    if kind=='literal':need(same(value,spec['value']),'exact native literal and builtin type')
    elif kind=='boolean':need(type(value) is bool,'exact native boolean')
    elif kind=='nullable':
        if value is not None:validate_native_type(spec['value_type'],value,depth+1)
    elif kind=='enum':need(any(same(value,v)for v in spec['values']),'closed native enum')
    elif kind=='integer':need(type(value) is int and spec['minimum']<=value<=spec['maximum'],'bounded exact integer')
    elif kind=='string':
        scalar_text(value,maximum=spec.get('maximum_length',4096))
        need(len(value)>=spec.get('minimum_length',0),'nonempty required text')
        if name=='ChunkHex':need(len(value)%2==0 and all(c in '0123456789abcdef'for c in value),'exact lower-case byte hex')
        elif name=='PathComponent':need(value not in ('.','..') and '/'not in value,'single original path component')
        elif name=='AbsolutePath':need(value.startswith('/') and all(c not in ('','.','..')for c in value.split('/')[1:]),'canonical absolute path')
        elif name=='NamespaceLink':need(re.fullmatch(r'[a-z]+:\[[0-9]+\]',value)is not None,'fixed kernel namespace text')
    elif kind=='closed_map':
        need(type(value) is dict and set(value)==set(spec['keys']),'fixed resource dimension map')
        for child in value.values():validate_native_type(spec['values'],child,depth+1)
    elif kind=='closed_schema_discriminated_union':
        need(type(value) is dict and type(value.get(spec['discriminant']))is str,'closed native union discriminator')
        matches=[x for x in spec['alternatives']if NATIVE_RECORDS[x]['schema_literal']==value[spec['discriminant']]]
        need(len(matches)==1,'one selected current native union branch')
        validate_native_type(matches[0],value,depth+1)
    else:need(False,'compiled native schema kind')
    return value

def packet_decode(raw,maximum):
    value=parse(raw,maximum,maximum_depth=64,maximum_members=maximum,maximum_string_bytes=maximum)
    validate_native_type('PacketV1',value)
    need(canonical(value,maximum)==raw,'complete canonical packet, no alternate whitespace or representation')
    return value

def packet_encode(value,maximum):
    validate_native_type('PacketV1',value)
    return canonical(value,maximum)

def payload_name(body,*,reply=False):
    permitted=REPLY_KINDS if reply else REQUEST_KINDS
    need(type(body) is dict,'fixed packet payload')
    names=[name for name in permitted if NATIVE_RECORDS[name]['schema_literal']==body.get('schema')]
    need(len(names)==1,'source-selected request/reply direction')
    validate_native_type(names[0],body)
    return names[0]
