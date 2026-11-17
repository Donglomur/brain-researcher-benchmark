"""Private module namespaces for exact captured nativeV3 and improvementV2.

No mutable sys.path/sys.modules replacement and no candidate-selected module
list. Captured source is reused unchanged; this loader is not OS isolation or
proof of interpreter/import custody preceding its execution.
"""
import builtins
from pathlib import Path
import types
from ach_util import need,read_exact,decode,pin

BINDING_PIN={'bytes':7257,'sha256':'4cf9c64ae5b44e0b224c764ef7ca4e95abb1639ca50df422fac04000b1deaa30'}
CORE=('common','study','history','nulls','grading','native_compare','numeric_backend','reference_workflow','completion')
NATIVE=('protocol','capture','dispatch')

class Libraries:
    def __init__(self,ledger=None):
        self.root=Path(__file__).absolute().parent;self.ledger=ledger
        manifest=decode(read_exact(self.root/'SOURCE_BINDINGS.json',BINDING_PIN,16384,ledger),16384)
        need(manifest['schema']=='ach_controller_exact_parent_sources_v1' and
             manifest['native_member_count']==12,'fixed complete parent source capture')
        self.members={x['path']:x for x in manifest['files']}
        need(len(self.members)==22,'exact captured parent closure')
        self.modules={};self.loading=set();self.source_bodies={}
        for name,record in self.members.items():
            need(name.startswith(('captured-core/','captured-native/')) and '..' not in name.split('/'),
                 'fixed captured relative source')
            self.source_bodies[name]=read_exact(self.root/name,{k:record[k] for k in ('bytes','sha256')},262144,ledger)
        self.manifest_pin=BINDING_PIN

    def get(self,family,name):
        allowed=CORE if family=='core' else NATIVE if family=='native' else ()
        need(name in allowed,'fixed source-owned scientific module')
        key=(family,name)
        if key in self.modules:return self.modules[key]
        if family=='core' and name=='numeric_backend' and self.ledger is not None:
            self.ledger.reserve({'read_bytes':24406},'captured numeric backend independent exact source reread')
        need(key not in self.loading,'unexpected captured import cycle');self.loading.add(key)
        relative='captured-'+family+'/'+name+'.py';module=types.ModuleType('ach_captured_'+family+'_'+name)
        module.__file__=str(self.root/relative);module.__package__=''
        trusted_import=builtins.__import__
        def import_frozen(module_name,globals=None,locals=None,fromlist=(),level=0):
            need(level==0,'captured source uses only absolute imports')
            if module_name in allowed:return self.get(family,module_name)
            return trusted_import(module_name,globals,locals,fromlist,level)
        module.__dict__['__builtins__']={**vars(builtins),'__import__':import_frozen}
        try:
            exec(compile(self.source_bodies[relative],module.__file__,'exec'),module.__dict__)
            self.modules[key]=module
            return module
        finally:self.loading.remove(key)

    def native_contract(self):
        return self.get('native','protocol').canonical_contract(
            decode(self.source_bodies['captured-native/CONTRACT.json'],262144))

    def source_identity(self):
        return pin({k:{x:v[x] for x in ('bytes','sha256')} for k,v in self.members.items()})
