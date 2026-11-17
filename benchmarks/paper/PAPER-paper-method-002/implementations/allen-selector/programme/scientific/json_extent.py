"""Complete explicit JSON schema extents, before launch and publication.

Bounds count canonical UTF-8 bytes conservatively. A schema is a resource/source
contract, not proof of authentic scientific inputs or completed work.
"""
import math
from runtime.strict import require,integer,canonical_bytes

def layout_bytes(layout,depth=0):
    require(type(layout)is dict and depth<=64,'finite closed JSON layout')
    kind=layout.get('kind')
    if kind in('null','boolean','number'):
        require(set(layout)=={'kind'},'scalar layout fields')
        return {'null':4,'boolean':5,'number':32}[kind]
    if kind=='integer':
        require(set(layout)=={'kind','minimum','maximum'},'integer layout fields')
        lo=layout['minimum'];hi=layout['maximum'];require(type(lo)is int and type(hi)is int and lo<=hi,'bounded JSON integer domain')
        return max(len(str(lo)),len(str(hi)))
    if kind=='string':
        require(set(layout)=={'kind','max_utf8_bytes'},'string layout fields')
        return 2+6*integer(layout['max_utf8_bytes'],'complete string bound',0)
    if kind=='array':
        require(set(layout)=={'kind','minimum_count','maximum_count','items'},'array layout fields')
        low=integer(layout['minimum_count'],'minimum full row count',0);high=integer(layout['maximum_count'],'maximum full row count',0)
        require(low<=high,'full array count range')
        return 2+high*layout_bytes(layout['items'],depth+1)+max(0,high-1)
    if kind=='object':
        require(set(layout)=={'kind','fields'}and type(layout['fields'])is dict,'complete closed object layout')
        total=2;fields=layout['fields']
        for key,value in fields.items():
            require(type(key)is str,'literal complete object key')
            total+=len(canonical_bytes(key))-1+1+layout_bytes(value,depth+1)
        return total+max(0,len(fields)-1)
    require(kind=='union'and set(layout)=={'kind','variants'}and type(layout['variants'])is list and layout['variants'],'explicit finite JSON variants')
    return max(layout_bytes(v,depth+1)for v in layout['variants'])

def matches(value,layout,depth=0):
    if depth>64:return False
    kind=layout['kind']
    if kind=='null':return value is None
    if kind=='boolean':return type(value)is bool
    if kind=='number':return type(value)in(int,float)and (type(value)is not float or math.isfinite(value))and len(canonical_bytes(value))-1<=32
    if kind=='integer':return type(value)is int and layout['minimum']<=value<=layout['maximum']
    if kind=='string':return type(value)is str and len(value.encode('utf8'))<=layout['max_utf8_bytes']
    if kind=='array':return type(value)is list and layout['minimum_count']<=len(value)<=layout['maximum_count']and all(matches(v,layout['items'],depth+1)for v in value)
    if kind=='object':return type(value)is dict and set(value)==set(layout['fields'])and all(matches(value[k],v,depth+1)for k,v in layout['fields'].items())
    if kind=='union':return any(matches(value,v,depth+1)for v in layout['variants'])
    return False

def require_json_product(value,product):
    layout=product['extent']['derivation']['layout'];bound=layout_bytes(layout)+1
    require(product['extent']['bytes']>=bound,'complete JSON grammar exceeds selected extent')
    require(matches(value,layout),'actual complete JSON product differs from admitted full schema/count support')
    return bound
