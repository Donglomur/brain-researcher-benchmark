"""Explicit original descriptor bases; never infer a base from an artifact parent."""
from pathlib import Path
from .common import Store, need, relative, closed, integer

class BoundRoots:
    def __init__(self, roots, *, relative_base, meter, forbidden=()):
        need(type(roots) is dict and relative_base in roots, "source-selected typed roots")
        self.stores = {name:Store(path,meter,forbidden=forbidden) for name,path in roots.items()}
        self.relative_base = relative_base
        self.meter = meter
        self.roots = {name:s.root for name,s in self.stores.items()}
        need(len(set(self.roots.values())) == len(self.roots), "distinct declared roots")
    def route(self, d):
        closed(d,("path","bytes","sha256"));integer(d["bytes"])
        name=d["path"]
        need(type(name) is str and name and "\\" not in name, "original exact path")
        if not name.startswith("/"):
            relative(name);return self.stores[self.relative_base],dict(d)
        relative(name[1:])
        p=Path(name)
        matches=[]
        for key,root in self.roots.items():
            try:rel=p.relative_to(root).as_posix()
            except ValueError:continue
            matches.append((len(root.parts),key,rel))
        need(matches,"original absolute descriptor inside an explicitly selected root")
        _,key,rel=max(matches)
        # Longest *selected* root is fixed by root authority, never by a receipt.
        relative(rel);return self.stores[key],{**d,"path":rel}
    def read(self,d,cap,*,metadata=False):
        store,translated=self.route(d)
        return store.read(translated,cap,metadata=metadata)
    def document(self,d,cap):
        from .common import parse
        return parse(self.read(d,cap,metadata=True),cap)

