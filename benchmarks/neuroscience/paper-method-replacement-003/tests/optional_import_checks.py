"""New optional-source import behavior controls, two invented source packages."""
from pathlib import Path
import hashlib,importlib,json,sys,tempfile
from unittest.mock import patch
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D))
from c4_distribution import dependencies as d, import_guard as g
from c4_distribution.io_core import SourceError
def pin(p):
 b=p.read_bytes();return {'path':str(p.relative_to(D)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
before=[pin(D/'c4_distribution'/n)for n in('io_core.py','dependencies.py','import_guard.py')]
checks=refusals=0
def check(x):
 global checks
 checks+=1
 if not x:raise AssertionError('new optional-import predicate')
def reset():
 for n in list(sys.modules):
  if n=='npyx'or n.startswith('npyx.'):sys.modules.pop(n)
 if g._ACTIVE in sys.meta_path:sys.meta_path.remove(g._ACTIVE)
 g._ACTIVE=None
def spec_for(files):
 rows=[]
 for n,b in files.items():rows.append({'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'git_blob':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),'url':'unused-invented-local-fixture'})
 return {'files':rows,'file_count':len(rows),'total_bytes':sum(map(len,files.values()))}
with tempfile.TemporaryDirectory(prefix='optional-import-',dir=None)as td:
 root=Path(td).resolve()
 for caught in (True,False):
  initializer=(b'try:\n from .optional import X\nexcept ImportError:\n OPTIONAL = False\nfrom .core import VALUE\n'if caught else b'from .optional import X\n')
  files={'npyx/__init__.py':initializer,'npyx/c4/__init__.py':b'# invented\n','npyx/core.py':b'VALUE = 11\n','npyx/optional.py':b'raise ImportError("invented optional dependency unavailable")\n'}
  source=root/('caught-input'if caught else'unhandled-input');source.mkdir()
  for n,b in files.items():
   f=source/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
  out=root/('caught'if caught else'unhandled')
  with patch.object(d,'specification',return_value=spec_for(files)),patch.object(d,'MANIFEST_SHA256','e'*64),patch.object(g,'verify_dependencies',side_effect=d.verify_dependencies):
   d.prepare_dependencies(out,source_root=source);bound=g.activate_originals(out)
   if caught:
    module=importlib.import_module('npyx')
    check(module.OPTIONAL is False and module.VALUE==11)
    check(g.require_bound_source()is bound and g._ACTIVE.failed is None)
    failed=g._ACTIVE.failed_modules['npyx.optional'];check(isinstance(failed,ImportError))
    try:importlib.import_module('npyx.optional')
    except ImportError as exc:check(exc is failed);refusals+=1
    else:raise AssertionError('failed optional import unexpectedly retried')
    check(g.require_bound_source()is bound)
   else:
    try:importlib.import_module('npyx')
    except ImportError as exc:check(g._ACTIVE.failed is exc);refusals+=1
    else:raise AssertionError('unhandled root import expected')
    try:g.require_bound_source()
    except SourceError:refusals+=1
    else:raise AssertionError('unhandled root import must poison binding')
   reset()
 for f in root.rglob('*'):
  if f.is_dir():f.chmod(0o755)
after=[pin(D/x['path'])for x in before];check(after==before)
result={'status':'pass','cases':2,'assertions':checks,'expected_refusals':refusals,'source_before':before,'source_after':after,'scope':'Actual source preparation and importer with tiny invented optional/nonoptional Python imports. No originalscientificpackage/environment installed/imported or oldcontrols replayed.'}
print(json.dumps(result))
