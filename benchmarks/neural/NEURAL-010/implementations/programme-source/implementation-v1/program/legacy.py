"""Compile the captured unchanged private/public source with explicit imports."""
import builtins,types
from pathlib import Path
import common as c

def load(bodies):
    needed=('public/event_protocol.py','public/io_contract.py','protected/scorer.py','protected/analysis_core.py')
    c.need(all(n in bodies for n in needed),'complete original independent protected source')
    original=builtins.__import__;modules={}
    for path in needed:
        name=Path(path).stem;m=types.ModuleType('_neural010_captured_'+name);m.__file__=path
        def imp(n,g=None,l=None,fromlist=(),level=0):
            if n=='vendor':
                c.need(level==0 and tuple(fromlist)==('event_protocol',),'exact original protected import')
                return types.SimpleNamespace(event_protocol=modules['event_protocol'])
            if n in('event_protocol','io_contract'):return modules[n]
            return original(n,g,l,fromlist,level)
        m.__dict__['__builtins__']={**vars(builtins),'__import__':imp}
        exec(compile(bodies[path],path,'exec'),m.__dict__);modules[name]=m
    return modules
