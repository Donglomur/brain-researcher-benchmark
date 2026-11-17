"""Role-scoped file access; lexical checks complement qualified physical custody."""
from pathlib import Path
import common as c

class Access:
    def __init__(self,role,allowed,protected,budget,opaque=()):
        c.need(role in ('G0','G1','G2','G3','G4','G5','issuer','observer'),'source-owned role')
        self.role=role;self.allowed={};self.protected=[];self.budget=budget;self.opaque=set(opaque)
        for d in protected:c.descriptor(d);self.protected.append(c.absolute(d['path']))
        for d in allowed:
            c.descriptor(d,True);c.need(d['path']not in self.allowed,'unique allowed operand');self.allowed[d['path']]=d
        if role not in ('G0','G5'):
            for d in allowed:self._protected(d['path'])
    def _protected(self,path):
        p=c.absolute(path)
        c.need(not any(p==q or p.is_relative_to(q)or q.is_relative_to(p)for q in self.protected),'global labels are G0/G5-only; no alternate protected read')
    def admit(self,desc):
        c.descriptor(desc,True)
        if self.role not in ('G0','G5'):self._protected(desc['path'])
        c.need(desc['path']in self.allowed and c.typed_equal(desc,self.allowed[desc['path']]),'exact selected role operand before body access')
        return desc
    def read(self,desc):
        self.admit(desc);c.need(desc['path']not in self.opaque,'controller transports opaque operand descriptors without body reads');return c.capture(desc,self.budget,[Path(desc['path']).parent],empty=desc['bytes']==0)
    def json(self,desc):return c.parse(self.read(desc))
    def authenticate(self,desc):
        self.admit(desc);c.need(desc['path']not in self.opaque,'opaque controller operand cannot be hash-read');return c.authenticate_stream(desc,self.budget,[Path(desc['path']).parent],empty=desc['bytes']==0)
    def copy(self,desc,path):
        self.admit(desc);c.need(desc['path']not in self.opaque,'opaque controller operand cannot be copied');return c.copy_stream(desc,path,self.budget,[Path(desc['path']).parent])

def disjoint_roots(paths):
    roots=[c.absolute(p)for p in paths]
    c.need(len(set(roots))==len(roots),'distinct roots')
    for i,p in enumerate(roots):
        c.need(not any(p==q or p.is_relative_to(q)or q.is_relative_to(p)for q in roots[i+1:]),'lexically disjoint role roots')
        c.need(not any(x.is_symlink()for x in (p,*p.parents)),'ordinary role root ancestry')
    return roots
