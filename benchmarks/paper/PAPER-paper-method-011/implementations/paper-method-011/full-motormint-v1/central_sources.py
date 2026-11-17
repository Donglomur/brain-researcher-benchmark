"""Portable MotorMINT identities and exact captured-source imports."""
import builtins,sys,types,importlib.util
from central_common import need,keys,pin,absolute,relative,exact_json

class Sources:
    def __init__(self,root,manifest,body,files,meter,current_binding=None):
        self.root=absolute(root);self.manifest=manifest;self.manifest_body=body
        self.manifest_pin=pin(body);self.files=files;self.meter=meter
        keys(manifest,('schema','task','files','central_modules','scope','runtime_files','deferred_dependencies'))
        need(manifest['schema']=='motormint_portable_source_v1' and manifest['task']=='PAPER-paper-method-011','complete portable identity')
        need(set(files)==set(manifest['files']),'exact complete captured source')
        self.current_binding=current_binding
        historical=exact_json(body,1048576) if current_binding is not None else manifest
        self.runtime=exact_json(files['RUNTIME_MANIFEST.json'],1048576)
        need(self.runtime=={'files':[{'path':k,**v} for k,v in sorted(historical['runtime_files'].items())]},'runtime/portable manifest join')
        if current_binding is not None:
            binding,binding_body=current_binding
            need(binding['historical_manifest']=={'path':'SOURCE_MANIFEST.json',**pin(body)},'current/historical source join')
            expected=dict(historical,files=dict(historical['files']),runtime_files=dict(historical['runtime_files']))
            for row in binding['overrides']:
                need(expected['files'][row['path']]==row['historical'],'selected historical replacement')
                expected['files'][row['path']]=row['current']
                if row['path'].startswith('runtime/'):
                    expected['runtime_files'][row['path'][len('runtime/'):]]=row['current']
            need(manifest==expected,'only explicit selected source replacements')
        for key,value in manifest['runtime_files'].items():
            need(pin(files['runtime/'+key])==value,'every runtime body matches selected identity')
        self.runtime_pin=pin(files['RUNTIME_MANIFEST.json'])
    def path(self,key):
        relative(key);need(key in self.files,'selected source member');return self.root+'/'+key
    def inspect(self):
        scope=exact_json(self.files['runtime/SCOPE.json'],1048576)
        gates=exact_json(self.files['runtime/GAP_REGISTER.json'],1048576)
        need(len(scope['datasets'])==9 and len(scope['modules'])==17 and len(gates['gaps'])==17,'full source scope unchanged')
        result={'schema':'motormint_portable_inspection_v1','task':'PAPER-paper-method-011',
            'source':self.manifest_pin,'runtime':self.runtime_pin,'files':len(self.files),
            'runtime_bodies':len(self.manifest['runtime_files']),'scope':self.manifest['scope'],
            'deployment':'unconfigured','deferred_dependency_descriptors':self.manifest['deferred_dependencies'],
            'deferred_bodies_opened':False,'scientific_execution':False,'qualified':False}
        if self.current_binding is not None:
            binding,body=self.current_binding
            result['current_source_binding']=pin(body)
            result['current_source_selection']='explicit_inspection_only'
            result['historical_source_manifest']=self.manifest_pin
            result['historical_runtime_manifest']=self.runtime_pin
            result['current_runtime_overrides']=[row for row in binding['overrides'] if row['path'].startswith('runtime/')]
            result['source']=pin(body)
            result['source_kind']='current_inspection_binding'
            result['execution_authority']=False
        return result

class Runtime:
    """Trusted captured modules; candidate/native extension execution stays sandboxed.

    This namespace is owned only for the call. Runtime filesystem readers retain
    their independent pins; source directories require the selected exclusive
    read-only lease. The loader does not certify a host filesystem isolation.
    """
    def __init__(self,sources):
        self.sources=sources;self.modules={}
        need('mintbench' not in sys.modules,'no pre-existing project module namespace')
    def load(self,name):
        need(name=='mintbench' or name.startswith('mintbench.'),'closed project namespace')
        if name in self.modules:return self.modules[name]
        key='runtime/'+name.replace('.','/')+('/__init__.py' if name=='mintbench' else '.py')
        need(key in self.sources.files,'selected project module')
        raw=self.sources.files[key];self.sources.meter.charge(metadata_bytes=65*len(raw),objects=1)
        module=types.ModuleType(name);module.__file__=self.sources.path(key)
        module.__package__=name if name=='mintbench' else name.rsplit('.',1)[0]
        if name=='mintbench':module.__path__=[self.sources.root+'/runtime/mintbench']
        self.modules[name]=module;sys.modules[name]=module
        def imp(n,g=None,l=None,fromlist=(),level=0):
            if level:
                n=importlib.util.resolve_name('.'*level+n,g['__package__'])
            if n=='mintbench' or n.startswith('mintbench.'):
                found=self.load(n)
                if fromlist:
                    for child in fromlist:
                        full=n+'.'+child
                        candidate='runtime/'+full.replace('.','/')+'.py'
                        if child!='*' and not hasattr(found,child) and candidate in self.sources.files:
                            setattr(found,child,self.load(full))
                    return found
                return self.load('mintbench')
            return builtins.__import__(n,g,l,fromlist,0)
        b=dict(vars(builtins));b['__import__']=imp;module.__dict__['__builtins__']=b
        try:
            exec(compile(raw,module.__file__,'exec',dont_inherit=True),module.__dict__)
            if '.' in name:setattr(self.load(name.rsplit('.',1)[0]),name.rsplit('.',1)[1],module)
            return module
        except BaseException:
            self.modules.pop(name,None);sys.modules.pop(name,None);raise
    def close(self):
        for name,module in reversed(list(self.modules.items())):
            need(sys.modules.get(name) is module,'owned project namespace unchanged')
            del sys.modules[name]
        self.modules.clear()

