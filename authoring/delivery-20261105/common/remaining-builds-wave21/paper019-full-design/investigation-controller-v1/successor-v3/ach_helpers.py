"""Exact private namespace for the frozen physical helper source."""
import builtins
from pathlib import Path
import types
from ach_util import need,read_exact,decode

BINDING={'bytes': 1853, 'sha256': '5239bc7b7ae5d147013d69d17b1dc50832dc902302864091eda1ae652a5f1987'}

class Helpers:
    def __init__(self,ledger=None):
        self.root=Path(__file__).absolute().parent
        manifest=decode(read_exact(self.root/'HELPER_BINDING.json',BINDING,8192,ledger),8192)
        self.specs=manifest['modules'];self.modules={};self.loading=set();self.bodies={}
        need(set(self.specs)=={'wire','store','processes','transport','linux_backend','supervisor','cgroup_gate','investigator_wire'},
             'fixed complete helper source namespace')
        for name,spec in self.specs.items():
            self.bodies[name]=read_exact(self.root/spec['path'],{k:spec[k] for k in ('bytes','sha256')},131072,ledger)

    def get(self,name):
        need(name in self.specs,'fixed helper module')
        if name in self.modules:return self.modules[name]
        need(name not in self.loading,'unexpected helper import cycle');self.loading.add(name)
        module=types.ModuleType('ach_physical_'+name);module.__file__=str(self.root/self.specs[name]['path']);module.__package__=''
        original=builtins.__import__
        def captured_import(module_name,globals=None,locals=None,fromlist=(),level=0):
            need(level==0,'absolute helper source imports')
            if module_name in self.specs:return self.get(module_name)
            return original(module_name,globals,locals,fromlist,level)
        module.__dict__['__builtins__']={**vars(builtins),'__import__':captured_import}
        try:
            exec(compile(self.bodies[name],module.__file__,'exec'),module.__dict__)
            self.modules[name]=module;return module
        finally:self.loading.remove(name)
