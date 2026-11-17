"""Fixed complete code roster; no caller-selected scientific implementation."""
from pathlib import Path
from .common import need,hash_source_tree

OWNER=('__init__','admission','authority','bindings','candidate_worker','common','context_budget','controller','entry','evidence','execution','failures','grading','investigator','policies','report_agents','spatial','views','workload')
PHYSICAL=('__init__','cgroup_gate','investigator_wire','linux_backend','processes','store','supervisor','transport','wire')
REFERENCES=('__init__','budget','features','models','orchestration','protocol','selection')
HMP=('__init__','binding','export','native','pipeline','reconstruction','schedule','storage')
def roster():
    return sorted([n+'.py' for n in OWNER]+['physical/'+n+'.py' for n in PHYSICAL]+
        ['reference_core/'+n+'.py' for n in REFERENCES]+['hmp_core/'+n+'.py' for n in HMP]+
        ['hmp_core/SOURCES.json','REFERENCE_CAPTURE.json','HMP_CAPTURE.json'])

def authenticate_runtime(source_root,records,expected,ledger):
    actual=Path(__file__).resolve().parent;selected=Path(source_root)
    need(selected.is_absolute() and not selected.is_symlink() and selected.resolve()==actual,'source root is the actually imported fixed package')
    need(type(records) is list and [r['path'] for r in records]==roster(),'exact complete fixed source roster including both helper initializers')
    need(hash_source_tree(actual,records,ledger)==expected,'every actual runtime/helper source byte matches selected deployment')
    # Already imported owner modules must come from this same concrete package.
    import sys
    namespace=__package__
    for name,module in tuple(sys.modules.items()):
        if name==namespace or name.startswith(namespace+'.'):
            filename=getattr(module,'__file__',None)
            if filename is not None:need(Path(filename).resolve().is_relative_to(actual),'loaded module cannot come from a substitute source tree')
    return actual
