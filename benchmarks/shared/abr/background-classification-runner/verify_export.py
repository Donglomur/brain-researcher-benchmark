"""Verify the exact portable source tree; no packet/runtime operation occurs."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat

# Encoded pattern text avoids embedding forbidden workstation strings in the
# package scanner itself. These are exclusion rules, never credentials or data.
FORBIDDEN = tuple(bytes.fromhex(x) for x in (
    '2f55736572732f', '2f686f6d652f',
    '62656e63686d61726b2d656e67696e656572696e672d65766964656e6365',
    '72656d61696e696e672d6275696c64732d776176653430',
    '534146455f505249564154455f53454c454354494f4e',
    '46494e414c5f505249564154455f53454c454354494f4e',
    '582d416d7a2d5369676e6174757265', '4157534163636573734b65794964'))

def require(ok, reason):
    if not ok: raise ValueError(reason)

def relative(name):
    require(type(name) is str and name and '\\' not in name, 'plain relative source path')
    p=PurePosixPath(name)
    require(not p.is_absolute() and all(x not in ('','.','..') for x in p.parts) and
            str(p)==name and not any(x.startswith('.') for x in p.parts), 'canonical relative source path')
    return name

def decode(raw):
    def pairs(rows):
        result={}
        for k,v in rows:
            require(k not in result,'duplicate source manifest key');result[k]=v
        return result
    return json.loads(raw,object_pairs_hook=pairs)

def content(name, body):
    require(type(body) is bytes and 0<len(body)<=1048576 and b'\0' not in body,'bounded source text')
    body.decode('utf8')
    require(not any(x.lower() in body.lower() for x in FORBIDDEN),'private locator or signed credential in source')
    require(not re.search(rb'(?:animal|record)_[0-9a-f]{64}(?![0-9a-f])',body), 'literal individual identity in source')
    if name.endswith('.py'):
        import ast
        tree=ast.parse(body)
        require(not any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and
            n.name in {'admitted_animals','parse_member','manifest_from_witnesses','build_manifest','_records','_build'}
            for n in ast.walk(tree)),'private preparation or released-label builder in public source')

def verify(root=None):
    root=Path(root or Path(__file__).resolve().parent)
    require(root.is_absolute() and not root.is_symlink(),'ordinary source root')
    raw=(root/'SOURCE_MANIFEST.json').read_bytes();require(len(raw)<=131072,'bounded source manifest')
    doc=decode(raw)
    require(type(doc) is dict and set(doc)=={'schema','files'} and
        doc['schema']=='abr-portable-public-source-manifest/v1' and type(doc['files']) is list,
        'closed source manifest')
    expected={};total=0
    for row in doc['files']:
        require(type(row) is dict and set(row)=={'path','bytes','sha256'},'closed source member')
        name=relative(row['path']);require(name not in expected and name!='SOURCE_MANIFEST.json','unique source member')
        require(type(row['bytes']) is int and 0<row['bytes']<=1048576 and
            type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']),'source member extent/hash')
        expected[name]=row
    require(0<len(expected)<=128,'finite complete source manifest')
    observed=set()
    for p in root.rglob('*'):
        s=p.lstat();require(not p.is_symlink() and (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)), 'ordinary source tree')
        if p.is_dir(): continue
        name=p.relative_to(root).as_posix();observed.add(name)
        require(s.st_nlink==1,'single-link source file')
        if name=='SOURCE_MANIFEST.json': continue
        require(name in expected,'unexpected source member')
        body=p.read_bytes();row=expected[name];total+=len(body)
        require(len(body)==row['bytes'] and hashlib.sha256(body).hexdigest()==row['sha256'],'exact source member')
        content(name,body)
    require(observed==set(expected)|{'SOURCE_MANIFEST.json'} and total<=4194304,'complete bounded source tree')
    return {'schema':'abr-public-source-verification/v1','files':len(observed),'member_bytes':total,
            'public_source_only':True,'authentic_runtime_qualified':False}

if __name__=='__main__':
    print(json.dumps(verify(),sort_keys=True))
