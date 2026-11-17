"""Fixed captured original programme modules and explicit unselected Context seam.

This loader is source, not qualification. Runtime activation requires the exact
later Context source/admission and immutable environment selections. Native
reference loaders and all scientific methods remain their original source.
"""
import ast
import builtins
import hashlib
import importlib
import importlib.util
import sys
import types
from pathlib import Path
from .common import need, DependencyUnavailable, pin, bounded_size
from . import dependencies

BASES={
 "NEURAL-098":("NEURAL-098","program","authoring/delivery-20261105/common/remaining-builds-wave38/neural098-complete-design/implementation-v1/successor-v2/program"),
 "PAPER-FIND-050":("CriticalInit","critical_init","authoring/delivery-20261105/common/remaining-builds-wave39/critical-init-complete-design/implementation-v1/successor-v3/critical_init"),
 "PAPER-paper-method-replacement-016":("Hundred Models","hundred_models_complete","authoring/delivery-20261105/common/remaining-builds-wave38/hundred-models-complete-design/implementation-v1/successor-v2/hundred_models_complete"),
}
EXTENSIONS={
 "PAPER-FIND-050":frozenset(("stage_budget","stage_closure","authorization_v3","authorization_v4","workflow_v3","workflow_v4","stage_worker","output_contract","host_stage","host_failure","poststage","coordinator","precommit_public","programme_links_v3","programme_output_v2")),
 "PAPER-paper-method-replacement-016":frozenset(("fixed_tables","reservations","identity_contract","stage_budget","stage_worker","issuance","stage_closure","coordinator")),
 "NEURAL-098":frozenset(),
}
OVERRIDES={"ci_authority":("authorization_v4","Selection"),"ci_budget":("stage_budget","ExclusiveBudget"),
           "ci_plan":("workflow_v4","selected_plan"),"ci_stage":("workflow_v4","execute_selected"),
           "ci_collect":("workflow_v4","collect"),"ci_grade":("workflow_v4","protected_grade"),
           "ci_views":("output_contract","materialize_candidate_views")}

class SourceSession:
    def __init__(self,programme,*,catalog,ordinary_store,extension_sources,root,
                 selected_context,selected_templates,environment):
        need(programme in BASES,"fixed in-process original programme")
        need(type(extension_sources)is dict and set(extension_sources)==EXTENSIONS[programme],
             "entire fixed source-owned extension closure, no missing or ambient module")
        dependencies.require("context_v6_source_admission",selected_context)
        dependencies.require("context_four_programme_source_templates",selected_templates)
        # This is deliberately a source-owned missing prerequisite rather than
        # accepting an arbitrary callback/true flag as an engine admission.
        from .context_boundary import admitted_context
        admitted_context(programme,catalog,selected_context,selected_templates,environment)
        self.programme=programme;self.catalog=catalog;self.store=ordinary_store
        self.root=Path(root);self.environment=environment;self.modules={};self.loading=set();self.raw={}
        label,package,base=BASES[programme];self.base=base;self.original_package=package
        self.prefix="_four_"+package+"_"+catalog["programmes"][programme]["source_manifest"]["sha256"]
        need(self.prefix not in sys.modules,"fresh owned original namespace")
        self.definitions={}
        for row in catalog["original_roles"]:
            if row["programme"]!=label:continue
            if row["body_authenticated"] is not True:
                need(programme=="NEURAL-098" and row["path"] in (
                    "authoring/delivery-20261105/neural098/public/COHORT.json",
                    "authoring/delivery-20261105/neural098/public/source/phase3.txt"),"exact two held bodies remain unread")
                continue
            need(row["body_authenticated"] is True,"ordinary source only")
            expected={k:row[k] for k in ("path","bytes","sha256")}
            raw=ordinary_store.read(expected,row["bytes"]+1)
            if row["path"].startswith(base+"/") and row["path"].endswith(".py"):
                name=row["path"][len(base)+1:-3].replace("/",".")
                name=name.removesuffix(".__init__") if name.endswith(".__init__") else ("" if name=="__init__" else name)
                need(name not in self.raw,"one exact selected original module")
                self.raw[name]=(raw,expected)
        for name,entry in extension_sources.items():
            need(name in EXTENSIONS[programme],"fixed complete source-owned programme additions, no metadata module name")
            need(name not in self.raw,"original source never replaced")
            raw=ordinary_store.read(entry,entry["bytes"]+1);self.raw[name]=(raw,entry)
        for key,row in catalog["APIs"].items():
            if not row.get("path","").startswith(base+"/") or "definition" not in row:continue
            name=row["path"][len(base)+1:-3].replace("/",".")
            raw=self.raw[name][0];tree=ast.parse(raw)
            nodes=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and
                   n.lineno==row["line"] and n.end_lineno==row["end_line"]]
            need(len(nodes)==1 and hashlib.sha256(ast.dump(nodes[0],include_attributes=False).encode()).hexdigest()==row["AST_sha256"],
                 "exact original public API AST and source")
            self.definitions[key]=(name,row["definition"])
        self.closed=False
    def _external(self,name,globals,locals,fromlist,level):
        # Exact immutable-runtime admission is source-selected. It is not an
        # invitation to install/download a missing package or search a new path.
        self.environment.require_original_import(name,fromlist)
        return builtins.__import__(name,globals,locals,fromlist,level)
    def _import(self,name,globals=None,locals=None,fromlist=(),level=0):
        need(not self.closed,"active owned source session")
        if level:
            need(type(globals) is dict and type(globals.get("__package__")) is str and
                 (globals["__package__"]==self.prefix or globals["__package__"].startswith(self.prefix+".")),
                 "original captured private package")
            absolute=importlib.util.resolve_name("."*level+name,globals["__package__"])
        else:absolute=name
        if absolute==self.prefix or absolute.startswith(self.prefix+"."):
            local=absolute[len(self.prefix):].lstrip(".")
            module=self.module(local)
            for child in fromlist:
                need(type(child) is str,"original fromlist names")
                if child=="*":continue
                childname=(local+"." if local else "")+child
                if childname in self.raw and child not in vars(module):self.module(childname)
            return module if fromlist else self.module("")
        need(not absolute.startswith(self.original_package),"no ambient original package alias")
        return self._external(name,globals,locals,fromlist,level)
    def module(self,name):
        need(not self.closed and type(name) is str,"active literal module lookup")
        if name in self.modules:return self.modules[name]
        fullname=self.prefix+("."+name if name else "")
        need(fullname not in sys.modules,"no preexisting foreign module cache")
        parent=name.rpartition(".")[0] if name else None
        if name:self.module(parent)
        is_package=name=="" or any(k.startswith(name+".") for k in self.raw)
        if name not in self.raw:
            need(is_package,"module must be in exact captured source closure")
            raw=b"";path=str(self.root/self.base)
        else:
            raw,d=self.raw[name];path=str(self.root/d["path"])
        self.store.meter.charge("work_units",len(raw)*64+4096)
        self.store.meter.charge("retained_bytes",len(raw)*16+4096)
        module=types.ModuleType(fullname)
        module.__file__=path;module.__package__=fullname if is_package else fullname.rpartition(".")[0]
        module.__loader__=self
        if is_package:module.__path__=[]
        # Empty __path__ prevents any Python filesystem fallthrough.
        module.__builtins__={**vars(builtins),"__import__":self._import}
        self.modules[name]=module;sys.modules[fullname]=module;self.loading.add(name)
        try:
            exec(compile(raw,path,"exec",dont_inherit=True),vars(module))
            if name:setattr(self.modules[parent],name.rpartition(".")[2],module)
            return module
        except BaseException:
            self.modules.pop(name,None)
            if sys.modules.get(fullname) is module:del sys.modules[fullname]
            raise
        finally:self.loading.discard(name)
    def api(self,key):
        need(key in self.definitions,"one of the exact original API bindings")
        mod,member=OVERRIDES.get(key,self.definitions[key])
        value=self.module(mod)
        for part in member.split("."):
            need(part in vars(value),"exact source-owned API member")
            value=vars(value)[part]
        return value
    def close(self):
        if self.closed:return
        self.closed=True
        for name,module in list(self.modules.items())[::-1]:
            full=self.prefix+("."+name if name else "")
            need(sys.modules.get(full) is module,"owned module identity unchanged")
            del sys.modules[full]
        self.modules.clear()

