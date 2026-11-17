"""Finite source capture before any input exposure or protected target authority."""
import builtins
import os
import sys
import types
from pathlib import Path
from .common import capture,parse,require,sha,encoded,keys

class Sources:
    def __init__(self,root,manifest_descriptor,budget):
        self.root=Path(root);self.budget=budget
        raw=capture(root,manifest_descriptor,budget,1048576);self.identity=sha(raw);m=parse(raw)
        keys(m,('schema','files'));require(m['schema']=='neural055-complete-runtime-source-v1','complete runtime source schema')
        self.bodies={};self.descriptors={}
        for d in m['files']:
            require(d['path'] not in self.bodies,'source path uniqueness')
            require(d['role'] in ('runtime_source','legacy_source','source_contract','public_instructions'),'ordinary source-only role')
            self.bodies[d['path']]=capture(root,d,budget,16777216);self.descriptors[d['path']]=d
        require('LEGACY_ROLES.json' in self.bodies,'actual retained legacy role closure')
        self.legacy=parse(self.bodies['LEGACY_ROLES.json']);self.loaded={}
        self.actor_root=None;self.actor_descriptors={}
        for d in self.legacy.values():
            require(d['path'] in self.bodies and self.descriptors[d['path']]['bytes']==d['bytes'] and sha(self.bodies[d['path']])==d['sha256'],'every legacy dependency captured')
        require(self.bodies.get('n055/original_r1.py')==self.bodies[self.legacy['private/reference_core.py']['path']],
                'executing original R1 core is byte-identical to retained exact numerical source')
    def submitted(self,operator_root,source_descriptors):
        captured={}
        require(set(source_descriptors)=={'F','I','common_policy'},'complete paired source policies')
        for role,d in source_descriptors.items():
            body=capture(operator_root,d,self.budget,131072 if role in ('F','I') else 1048576)
            body.decode('utf-8');captured[role]={'descriptor':d,'body':body,'sha256':sha(body)}
        return captured
    def stage_actor_runtime(self,journal):
        require(self.actor_root is None,'one pre-exposure readonly actor runtime')
        root=journal.root/'actor_runtime';root.mkdir(mode=0o700);(root/'n055').mkdir(mode=0o700)
        # Operator credentials, trust, protected scorer, target loaders, private
        # source metadata and campaign state never enter the actor mount.
        names=('phase_entry.py','capture_entry.py','reference_entry.py','broker_client.py','model_provider_entry.py','tool_provider_entry.py','n055/__init__.py',
               'n055/common.py','n055/registry.py','n055/schedule.py','n055/learning.py','n055/original_r1.py','n055/assignment.py')
        for name in names:
            require(name in self.bodies,'complete exact actor source dependency')
            body=self.bodies[name];path=root/name;journal.write(str(path.relative_to(journal.root)),body);os.chmod(path,0o444)
            self.actor_descriptors[name]={'bytes':len(body),'sha256':sha(body),'mode':'0o444','role':'exact_actor_source','path':name}
        os.chmod(root/'n055',0o555);os.chmod(root,0o555);self.actor_root=root
        self.budget.check('after complete pre-exposure actor source staging')
        return root
    def actor_current(self):
        require(self.actor_root is not None,'original actor runtime staged')
        for name,d in self.actor_descriptors.items():
            require(capture(self.actor_root,d,self.budget,16777216)==self.bodies[name],'same exact actor code')
        return self.actor_root
    def current(self):
        for name,d in self.descriptors.items():
            body=capture(self.root,d,self.budget,16777216)
            require(body==self.bodies[name],'same complete current source')
        return self.identity
    def legacy_module(self,role):
        if role in self.loaded:return self.loaded[role]
        d=self.legacy[role];body=self.bodies[d['path']]
        module=types.ModuleType('n055_legacy_'+role.replace('/','_'));module.__file__=str(self.root/d['path'])
        original_import=builtins.__import__
        def importing(name,globals=None,locals=None,fromlist=(),level=0):
            require(level==0,'legacy absolute import source contract')
            if name=='interface':return self.legacy_module('public/interface.py')
            if name=='scorer':return self.legacy_module('private/scorer.py')
            if name=='sys':
                proxy=types.ModuleType('sys');proxy.__dict__.update(sys.__dict__);proxy.path=list(sys.path);return proxy
            require(name in ('argparse','hashlib','hmac','json','math','pathlib','re','stat','ast','os','collections'),'finite original grader/packet/metadata dependency set')
            return original_import(name,globals,locals,fromlist,level)
        namespace=dict(vars(builtins));namespace['__import__']=importing;module.__dict__['__builtins__']=namespace
        self.loaded[role]=module
        try:exec(compile(body,module.__file__,'exec'),module.__dict__)
        except BaseException:
            del self.loaded[role];raise
        self.budget.check('after exact legacy source capture/load')
        return module
