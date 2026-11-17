"""Actual exclusive directory creation charged to a separate administration owner."""
import os
from .errors import Custody,need
from .identity import identity

class Allocator:
    def __init__(self,root,setup_store,scope_observer):
        self.root=os.fspath(root);self.setup_store=setup_store;self.scope_observer=scope_observer
        self.owned={}

    def __call__(self,name,limits):
        need(name not in self.owned,"scope-directory-once")
        key=identity(name);path=os.path.join(self.root,key)
        budget=self.setup_store.budget
        attempt=budget.attempt("creation_attempts","scope-mkdir-"+key)
        self.owned[name]={"attempt":attempt,"acknowledged":False}
        try:os.mkdir(path,0o700)
        except BaseException:
            # The attempt is retained; an interruption can leave a created directory.
            budget.unknown.append({"effect":"scope-mkdir-"+key,"unacknowledged_capacity":"directory creation"})
            raise
        self.owned[name]["acknowledged"]=True
        observer=self.scope_observer.start(name,path,limits)
        receipt=self.setup_store.put("scope-allocation-"+key+".json",
                   {"name":name,"root":path,"attempt":attempt,"created":True,
                    "scope_observer":observer.identity,"limits":limits})
        return {"root":path,"original_receipt":receipt,"setup_owner":budget.name,"observer":observer}

    def close(self):
        need(all(x["acknowledged"] for x in self.owned.values()),"all-allocation-acknowledgements")
        return self.setup_store.budget.close()
