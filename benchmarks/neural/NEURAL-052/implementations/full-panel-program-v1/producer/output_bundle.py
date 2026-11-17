"""Bounded stopped-output decoding; no report values are interpreted here."""
import base64,hashlib,json,re

CAPS={'candidate':{'result.json':4000000,'METHODS.md':1048576},
      'admission':{'support.json':262144}}
REPLY_CAP=7000000

def need(ok,message):
    if not ok:raise ValueError(message)

def decode(raw,kind):
    need(kind in CAPS,'exact output role')
    need(type(raw)is bytes and 0<len(raw)<=REPLY_CAP,'whole encoded reply cap')
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate envelope key');out[k]=v
        return out
    obj=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite envelope'))
    need(type(obj)is dict and set(obj)=={'schema','kind','files'} and obj['schema']=='neural052_opaque_capture_v1' and obj['kind']==kind,'exact role envelope')
    need(type(obj['files'])is dict and set(obj['files'])==set(CAPS[kind]),'complete exact output bundle')
    result={}
    for name,cap in CAPS[kind].items():
        row=obj['files'][name]
        need(type(row)is dict and set(row)=={'bytes','sha256','base64'},'exact member descriptor')
        n=row['bytes'];need(type(n)is int and 0<n<=cap,'bounded member extent')
        need(type(row['sha256'])is str and re.fullmatch('[0-9a-f]{64}',row['sha256']),'member SHA256')
        value=row['base64'];need(type(value)is str and len(value)==4*((n+2)//3),'exact encoded extent')
        body=base64.b64decode(value,validate=True)
        need(len(body)==n and hashlib.sha256(body).hexdigest()==row['sha256'],'member content identity')
        need(base64.b64encode(body).decode('ascii')==value,'canonical base64')
        if name=='METHODS.md':need('\0' not in body.decode('utf-8'),'UTF8 METHODS without NUL')
        result[name]=body
    return result
