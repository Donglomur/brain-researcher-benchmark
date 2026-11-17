"""Standard-library source inspection only. Never imports model/data runtimes."""
from pathlib import Path,PurePosixPath
import ast,hashlib,json

def require(ok,reason):
    if not ok:raise ValueError(reason)

def ordinary(root,name):
    require(type(name)is str,'literal path')
    require(name and all(x not in ('','.','..')for x in name.split('/')),'canonical relative path')
    relative=PurePosixPath(name)
    require(not relative.is_absolute() and relative.parts and all(x not in ('.','..')for x in relative.parts),'relative public path')
    path=root.joinpath(*relative.parts)
    require(not any(p.is_symlink()for p in [path,*path.parents]),'no symlink in source namespace')
    return path

def pin(path):
    raw=path.read_bytes()
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def fixed_closure(root,fixed,external):
    ext={r['path']:r for r in external['unbundled_members']}
    require(len(ext)==len(external['unbundled_members']),'duplicate external source path')
    covered=set();bundled=0
    for row in fixed['files']:
        p=ordinary(root,row['path']);identity={k:row[k]for k in ('bytes','sha256')}
        if p.is_file() and pin(p)==identity:bundled+=1
        else:
            require(row['path']in ext,'unclassified fixed-reference dependency')
            require({k:ext[row['path']][k]for k in ('bytes','sha256')}==identity,'external source identity changed')
            require(ext[row['path']]['status']=='not_bundled_not_runtime_ready','external source cannot be marked ready')
            covered.add(row['path'])
    require(covered==set(ext),'extraneous external source record')
    require(len(fixed['files'])==external['original_members']==222,'complete original fixed source roster')
    return {'bundled':bundled,'external':len(ext),'original':222}

def check(root=None):
    root=Path(__file__).resolve().parent if root is None else Path(root).resolve()
    m=json.loads((root/'SOURCE_MANIFEST.json').read_text());names=[r['path']for r in m['files']]
    require(len(names)==len(set(names)),'duplicate public source')
    paths=[ordinary(root,n)for n in names] # validate all names before any body read
    for row,p in zip(m['files'],paths):
        require(p.is_file()and p.stat().st_nlink==1,'ordinary single-link source')
        require(pin(p)=={k:row[k]for k in ('bytes','sha256')},'public source identity')
        text=p.read_bytes().decode('utf8');require('\0'not in text,'text source only')
        if p.suffix=='.py':ast.parse(text)
    require(set(names)|{'SOURCE_MANIFEST.json'}=={str(p.relative_to(root))for p in root.rglob('*')if p.is_file()},'closed public pathset')
    external=json.loads((root/'EXTERNAL_SOURCE_DEPENDENCIES.json').read_text())
    fixed=json.loads((root/'contracts/FIXED_REFERENCE_SOURCE.json').read_text())
    closure=fixed_closure(root,fixed,external)
    status=json.loads((root/'PUBLIC_STATUS.json').read_text());require(status['execution_enabled']is False and status['scientific_qualified']is False,'inspection-only status')
    graph=json.loads((root/'RUNTIME_DEPENDENCIES.json').read_text())
    require(graph['all_dependency_edges_classified']is True and graph['unclassified_internal_imports']==[],'classified import closure')
    external_names={r['path']for r in external['unbundled_members']}
    for edge in graph['imports']:
        require(edge['from']in names and edge['from'].endswith('.py'),'known import owner')
        if edge['kind']in ('bundled_python','bundled_reference_kernel_sibling'):
            require(edge['target']in names,'bundled import source exists')
        elif edge['kind']=='external_exact_source':
            require(edge['target']in external_names,'missing source explicitly declared')
        else:require(edge['kind']in ('python_standard_library','external_runtime_package'),'known import role')
    provenance=json.loads((root/'PUBLIC_FILE_PROVENANCE.json').read_text())
    roles=provenance['files'];by={r['path']:r for r in roles}
    require(len(roles)==len(by),'unique per-file provenance')
    require(set(by)|{'PUBLIC_FILE_PROVENANCE.json'}==set(names),'complete per-file provenance')
    manifest_by={r['path']:r for r in m['files']}
    for name,row in by.items():
        require({k:row[k]for k in ('bytes','sha256')}=={k:manifest_by[name][k]for k in ('bytes','sha256')},'provenance source identity')
        require(row['license_evidence']in names and row['creator'] and row['visibility_rationale'],'source license and creator evidence')
    panel=json.loads((root/'contracts/PANEL.json').read_text());gates=json.loads((root/'contracts/GATES.json').read_text())
    require(len(panel['cases'])==2144 and len(panel['datasets'])==10 and len(gates['gates'])==30,'complete original scope')
    return {'source_identity_checks':len(names),'fixed_source':closure,'open_gates':30,'execution_enabled':False,'scientific_qualified':False,'source_only':True}

if __name__=='__main__':print(json.dumps(check(),sort_keys=True))
