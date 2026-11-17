"""Domain-owned errors, finite identities and raw failure occurrence custody."""
from dataclasses import dataclass, field
from .native.io import Refusal, need, exact, digest, identity, canonical

class Unsupported(Refusal):
    pass

@dataclass
class Attempt:
    stage: str
    errors: list = field(default_factory=list)
    children: list = field(default_factory=list)
    originals: dict = field(default_factory=dict)
    publications: dict = field(default_factory=dict)
    def fail(self, stage, error):
        # Every occurrence is retained, including repeated use of the same object.
        self.errors.append((stage,error))
    def call(self, stage, function, *args, **kwargs):
        try:return function(*args,**kwargs)
        except BaseException as error:self.fail(stage,error);return None
    def raise_first(self):
        if self.errors:raise self.errors[0][1]
    def publish(self, name, body, writer):
        slot={"body":body,"state":"attempted"};self.publications[name]=slot
        try:slot["pin"]=writer();slot["state"]="durable"
        except BaseException as error:
            slot["error"]=error;slot["state"]="failed_unknown_prefix";self.fail("publish:"+name,error)
        return slot
    def summary(self):
        return {"stage":self.stage,"errors":[{"stage":s,"type":type(e).__name__}for s,e in self.errors],
                "publications":{k:{"state":v["state"],"pin":v.get("pin")}for k,v in self.publications.items()},
                "children":len(self.children)}

