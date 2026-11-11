"""Inactive N092 source inspection and the original live Selection operator.

Generic execution/scoring remain null. An authorized Linux root supervisor may
use the original issuer through load_selection, then execute its same live
Selection. This module creates no Host, authority registry entry or receipt.
"""
import argparse,ast,hashlib,importlib,json,os,stat,sys
from importlib.machinery import ModuleSpec
from contextlib import contextmanager
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parent
ONE=1048576
NAMESPACES=('gain','host092','prospective','source')
class InactiveSource(RuntimeError):pass
def require(ok,message):
 if not ok:raise ValueError(message)
def relative(name):
 require(type(name)is str and name and '\\'not in name,'literal source relative name')
 p=PurePosixPath(name);require(not p.is_absolute()and all(x not in('','.','..')for x in name.split('/')),'source path domain')
 return Path(*p.parts)
def read(path,expected=None):
 require(not any(p.is_symlink()for p in(path,*path.parents)),'source aliases refused')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);first=None
 try:
  before=os.fstat(fd);require(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and 0<=before.st_size<=ONE,'bounded ordinary source')
  body=bytearray()
  while len(body)<=before.st_size:
   b=os.read(fd,min(65536,before.st_size+1-len(body)))
   if not b:break
   body.extend(b)
  after=os.fstat(fd);fields=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  require(fields(before)==fields(after)==fields(path.lstat())and len(body)==before.st_size,'complete stable source bytes')
  body=bytes(body);body.decode('utf8');require(b'\0'not in body,'ordinary UTF8 source')
  if expected is not None:require({'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}=={k:expected[k]for k in('bytes','sha256')},'exact selected source')
  return body
 except BaseException as e:first=e;raise
 finally:
  try:os.close(fd)
  except BaseException as e:
   if first is None:raise
   first.source_retirement_failures=getattr(first,'source_retirement_failures',())+(e,)
def parse(body):
 def pairs(items):
  out={}
  for k,v in items:require(k not in out,'duplicate metadata key');out[k]=v
  return out
 return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in()).throw(ValueError('nonfinite metadata')))
def inspect_definition():
 resolution=parse(read(ROOT/'INSTALLED_SOURCE_RESOLUTION.json'))
 require(resolution['schema']=='n092-v4-central-source-resolution-v1','selected V4 source schema')
 require(resolution['role_count']==49 and resolution['role_bytes']==250309 and len(resolution['files'])==49,'complete selected49 source roles')
 source=parse(read(ROOT/'SOURCE_MANIFEST.json',resolution['source_manifest']))
 require(source['schema']=='neural092-complete-host-source-v4'and all(source[k]is False for k in('source_complete','runnable','research_qualified')),'original inactive flags')
 expected={(r['path'],r['bytes'],r['sha256'])for r in source['roles']}
 actual={(r['original_relative'],r['bytes'],r['sha256'])for r in resolution['files']}
 require(len(expected)==len(actual)==49 and actual==expected,'complete source/runtime inverse')
 require(len({r['installed_relative']for r in resolution['files']})==49,'unique49 destinations')
 total=0;python_roles={}
 for row in resolution['files']:
  require(row['installed_relative']=='programme/'+row['original_relative'],'unchanged original source layout')
  body=read(ROOT/relative(row['installed_relative']),row);total+=len(body)
  if row['original_relative'].endswith('.py'):python_roles[row['original_relative']]=row
 require(total==250309,'complete source extent')
 contracts={(r['path'],r['bytes'],r['sha256'])for r in source['contracts']}
 require(len(contracts)==len(resolution['contracts'])==4,'all four original norms')
 require(contracts=={(r['original_relative'],r['bytes'],r['sha256'])for r in resolution['contracts']},'exact norm inverse')
 for row in resolution['contracts']:
  require(row['installed_relative']=='programme/'+row['original_relative'],'original norm layout')
  read(ROOT/relative(row['installed_relative']),row)
 api=parse(read(ROOT/'SOURCE_API.json',resolution['source_api']))
 require(api['complete']is True and api['source_roles']==49 and len(api['modules'])==38,'full accepted API')
 gates=parse(read(ROOT/'REMAINING_QUALIFICATION.json',resolution['qualification']))
 require(len(gates['holds'])==7 and all(gates[k]is False for k in('authentic_input_profile_issued','native_execution','scientific_execution','runnable','research_qualified','source_complete')),'original seven hold families preserved')
 tree=ast.parse(read(ROOT/'programme/host092/source_lock.py'))
 required=next(ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='REQUIRED_SOURCE_FILES'for t in n.targets))
 require(set(required)=={r[0]for r in expected}and len(required)==49,'actual original host source-file lock')
 manifest=parse(read(ROOT/'manifest.json'))
 require(manifest['id']=='NEURAL-092'and all(manifest[k]is None for k in('run','score','program_execution')),'generic interfaces inactive')
 require(all(v is False for v in manifest['admission'].values()),'no readiness promotion')
 return {'schema':'n092-central-source-inspection-v1','id':'NEURAL-092','source_version':'V4','source_roles':49,'source_bytes':total,'contracts':4,'api_modules':38,'scope':source['full_scope'],'source_root':str(ROOT/'programme'),'original_hold_families':gates['holds'],'run':None,'score':None,'source_complete':False,'runnable':False,'research_qualified':False,'actual_issuer':'host092.admission.load_selection','actual_operator':'host092.operator.execute','actual_observed_bridge':'source/run.py reference|score','scientific_execution':False}
def _check_loaded(source_root,roles):
 for name,module in tuple(sys.modules.items()):
  if not any(name==n or name.startswith(n+'.')for n in NAMESPACES):continue
  file=getattr(module,'__file__',None)
  spec=getattr(module,'__spec__',None)
  require(spec is not None and spec.name==name,'exact loaded module name')
  if file is None:
   require(name in ('source','prospective'),'only original namespace packages may lack files')
   require(tuple(map(str,getattr(module,'__path__',())))==(str(source_root/name),),'exact original namespace path')
   require(tuple(map(str,spec.submodule_search_locations or()))==(str(source_root/name),)and spec.origin is None,'exact namespace search locations')
   continue
  path=Path(file).absolute();require(source_root in path.parents,'conflicting already-loaded scientific namespace')
  rel=str(path.relative_to(source_root));expected=name.replace('.','/')+('/__init__.py'if name in ('gain','host092')else'.py')
  require(rel==expected and rel in roles,'loaded name binds its exact selected Python role')
  require(Path(spec.origin).absolute()==path,'exact selected module origin')
  if name in ('gain','host092'):
   require(tuple(map(str,getattr(module,'__path__',())))==(str(source_root/name),)and tuple(map(str,spec.submodule_search_locations or()))==(str(source_root/name),),'exact ordinary package search paths')
  else:require(spec.submodule_search_locations is None,'selected module is not a package')
  read(path,roles[rel])
class _ExactSourceLoader:
 """Execute only already captured selected source; no cache or path fallback."""
 def __init__(self,name,path,body):self.name=name;self.path=path;self.body=body
 def create_module(self,spec):return None
 def exec_module(self,module):
  require(module.__name__==self.name and module.__spec__.name==self.name,'exact selected module identity before body')
  require(module.__spec__.origin==str(self.path),'exact selected source origin before body')
  exec(compile(self.body,str(self.path),'exec',dont_inherit=True),module.__dict__)
class _SelectedSourceFinder:
 """Bind every covered import before any other finder or module can act.

 Namespace specifications preserve the original initializer-free directories.
 Selected ordinary modules use captured source bytes, never unlisted pyc files.
 Other, nonprogramme imports retain the enclosing trusted interpreter's policy.
 """
 def __init__(self,source_root,roles):self.source_root=source_root;self.roles=roles
 def find_spec(self,fullname,path=None,target=None):
  if not any(fullname==n or fullname.startswith(n+'.')for n in NAMESPACES):return None
  if fullname in ('prospective','source'):
   spec=ModuleSpec(fullname,loader=None,origin=None,is_package=True)
   spec.submodule_search_locations=[str(self.source_root/fullname)]
   return spec
  package=fullname in ('gain','host092')
  relative_name=fullname.replace('.','/')+('/__init__.py'if package else'.py')
  if relative_name not in self.roles:raise ModuleNotFoundError('unselected programme module: '+fullname,name=fullname)
  selected=self.source_root/relative_name
  body=read(selected,self.roles[relative_name])
  loader=_ExactSourceLoader(fullname,selected,body)
  spec=ModuleSpec(fullname,loader,origin=str(selected),is_package=package)
  spec.has_location=True
  if package:spec.submodule_search_locations=[str(selected.parent)]
  return spec
@contextmanager
def _source_graph(definition):
 source_root=Path(definition['source_root'])
 resolution=parse(read(ROOT/'INSTALLED_SOURCE_RESOLUTION.json'))
 roles={r['original_relative']:r for r in resolution['files']if r['original_relative'].endswith('.py')}
 _check_loaded(source_root,roles)
 previous=list(sys.path);previous_finders=list(sys.meta_path);sys.dont_write_bytecode=True
 finder=_SelectedSourceFinder(source_root,roles)
 try:
  # Resolve covered names ourselves before any later regular package or import
  # hook can run. Prepending a path alone cannot bind a namespace package.
  sys.meta_path.insert(0,finder)
  sys.path.insert(0,str(source_root))
  importlib.import_module('prospective')
  _check_loaded(source_root,roles)
  admission=importlib.import_module('host092.admission');operator=importlib.import_module('host092.operator')
  _check_loaded(source_root,roles)
  require(Path(admission.__file__).absolute()==source_root/'host092/admission.py'and Path(operator.__file__).absolute()==source_root/'host092/operator.py','actual original issuer/operator graph')
  yield admission,operator,resolution
  _check_loaded(source_root,roles)
 finally:
  sys.meta_path[:]=previous_finders
  sys.path[:]=previous
def load_selection(path,expected_sha256):
 """Call the original Linux-root issuer; this does not issue qualification."""
 definition=inspect_definition()
 with _source_graph(definition)as(admission,_,_):
  return admission.load_selection(path,expected_sha256)
def _execute(selection,definition,bootstrap=None):
 with _source_graph(definition)as(admission,operator,resolution):
  # The original registry and PID validation establish live selection identity.
  profile=admission.selected_profile(selection)
  require(profile['source_root']==definition['source_root'],'profile selects this exact deployed programme root')
  require({(path,r['bytes'],r['sha256'])for path,r in profile['source_files'].items()}=={(r['original_relative'],r['bytes'],r['sha256'])for r in resolution['files']},'profile selects every exact accepted source role')
  return operator.execute(selection,bootstrap=bootstrap)
def execute(selection):
 """Preserve an already-issued Selection object and original outer operator.

 Costs before this call, including a separately invoked issuer, require the
 enclosing supervisor's observation. No caller-supplied bootstrap is accepted.
 """
 import resource,time
 bootstrap=(time.monotonic_ns(),resource.getrusage(resource.RUSAGE_SELF))
 return _execute(selection,inspect_definition(),bootstrap)
def execute_from_root_selection(path,expected_sha256):
 """Include source inspection and original selection loading in outer timing."""
 import resource,time
 bootstrap=(time.monotonic_ns(),resource.getrusage(resource.RUSAGE_SELF))
 definition=inspect_definition()
 with _source_graph(definition)as(admission,_,_):
  selection=admission.load_selection(path,expected_sha256)
  return _execute(selection,definition,bootstrap)
def main(argv=None,*,selection=None):
 parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group(required=True)
 mode.add_argument('--inspect',action='store_true');mode.add_argument('--run',action='store_true');args=parser.parse_args(argv)
 if args.inspect:
  result=inspect_definition();print(json.dumps(result,sort_keys=True));return result
 if selection is None:raise InactiveSource('No genuine original live Selection supplied. Generic execution is inactive; authentic profile, data and native qualification remain unissued.')
 return execute(selection)
if __name__=='__main__':main()
