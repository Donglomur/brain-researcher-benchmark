"""Captured ordinary-source loader: no source-file cache lookup."""
import importlib.abc,importlib.util,sys,types
from pathlib import Path
from .common import capture,need
class Captured(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,root,rows,budget):
        self.root=Path(root);self.bodies={};self.files={};self.packages={}
        for row in rows:
            rel=row['path'];raw=capture(self.root/rel,budget,row['bytes'],{'bytes':row['bytes'],'sha256':row['sha256']})
            if not rel.endswith('.py'):continue
            name=rel[:-3].replace('/','.')
            if name.startswith('vendor.experiments.'):name=name[len('vendor.experiments.'):]
            package=name.endswith('.__init__')
            if package:name=name[:-9]
            need(name not in self.bodies,'unique captured Python role');self.bodies[name]=raw;self.files[name]=self.root/rel
            if package:self.packages[name]=self.root/rel.rsplit('/',1)[0]
            bits=name.split('.')
            for n in range(1,len(bits)):
                parent='.'.join(bits[:n]);base=self.root/('vendor/experiments' if rel.startswith('vendor/experiments/')else '')
                self.packages.setdefault(parent,base/('/'.join(bits[:n])))
        for n in set(self.bodies)|set(self.packages):need(n not in sys.modules,'project namespace must be absent before captured admission')
    def find_spec(self,fullname,path=None,target=None):
        if fullname in self.bodies or fullname in self.packages:return importlib.util.spec_from_loader(fullname,self,is_package=fullname in self.packages)
    def create_module(self,spec):return None
    def exec_module(self,module):
        n=module.__name__;module.__file__=str(self.files[n] if n in self.files else self.packages[n]/'__init__.py')
        if n in self.packages:module.__path__=[str(self.packages[n])]
        if n in self.bodies:exec(compile(self.bodies[n],module.__file__,'exec',dont_inherit=True),module.__dict__)
    def install(self):sys.meta_path.insert(0,self);return self
