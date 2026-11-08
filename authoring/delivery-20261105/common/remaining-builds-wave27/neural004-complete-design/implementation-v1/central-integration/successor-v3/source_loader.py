"""Private exact captured-package imports; no caller-selected scientific module."""
import importlib.abc,importlib.util,sys
from pathlib import Path
from central_io import need
class Captured(importlib.abc.MetaPathFinder,importlib.abc.Loader):
 def __init__(self,name,root,bodies):
  need(name not in sys.modules and type(bodies)is dict and '__init__.py'in bodies,'Fresh complete captured package')
  self.name=name;self.root=Path(root);self.bodies=dict(bodies);self.owned=[];self.installed=False
 def path(self,fullname):
  suffix=fullname[len(self.name):].lstrip('.').replace('.','/')
  package=(suffix+'/'if suffix else'')+'__init__.py';module=suffix+'.py'
  return package if package in self.bodies else module if module in self.bodies else None
 def find_spec(self,fullname,path=None,target=None):
  if fullname!=self.name and not fullname.startswith(self.name+'.'):return None
  source=self.path(fullname);need(source is not None,'No undeclared package import: '+fullname)
  return importlib.util.spec_from_loader(fullname,self,is_package=source.endswith('/__init__.py')or source=='__init__.py')
 def create_module(self,spec):return None
 def exec_module(self,module):
  source=self.path(module.__name__);need(source is not None,'Exact captured module')
  module.__file__=str(self.root/source);module.__loader__=self
  if source.endswith('/__init__.py')or source=='__init__.py':module.__path__=[str((self.root/source).parent)]
  self.owned.append(module.__name__);exec(compile(self.bodies[source],module.__file__,'exec'),module.__dict__)
 def install(self):
  need(not self.installed,'One captured finder');sys.meta_path.insert(0,self);self.installed=True;return self
 def module(self,suffix=''):
  import importlib
  return importlib.import_module(self.name+('.'+suffix if suffix else''))
 def close(self):
  if self.installed:
   need(self in sys.meta_path,'Owned finder still installed');sys.meta_path.remove(self);self.installed=False
  for name in reversed(self.owned):sys.modules.pop(name,None)
