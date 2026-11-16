"""One complete-ten-seed common domain for every selected comparison operand."""
from dataclasses import dataclass
from .contracts import need,MATCH_SEEDS
from .outputs import Collection,Disposition

@dataclass(frozen=True)
class SessionSupport:
    region:str
    session:str
    animal:str
    status:Disposition
    required_seeds:tuple
    complete_seeds:tuple
    operands:tuple
    rows:tuple
    causes:tuple

@dataclass(frozen=True)
class CommonSupport:
    collection:Collection
    original_seal:tuple
    sessions:tuple
    planned_animals:tuple
    def validate(self):
        need(self.collection.validate_seal() is self.original_seal,'same original production seal')
        cat=self.collection.catalogue
        need(self.planned_animals==cat.animals and len(self.planned_animals)==13,'all planned animals retained')
        need(tuple((x.region,x.session,x.animal) for x in self.sessions)==tuple((r,s,a) for r in cat.regions for s,a in cat.session_animals),'complete region/session/animal inverse')
        by={(r.key.cell[1],r.key.session,r.key.cell[3],r.key.panel,r.key.arm):r for r in self.original_seal}
        expected_operands=tuple(dict.fromkeys((k.panel,k.arm) for k in cat.expected))
        for x in self.sessions:
            need(x.operands==expected_operands,'one full selected comparison operand domain')
            need(x.required_seeds==MATCH_SEEDS and len(x.rows)==10*len(x.operands),'complete ten-seed operand census')
            expected_rows=tuple(by[x.region,x.session,seed,p,a] for seed in MATCH_SEEDS for p,a in x.operands)
            need(len(expected_rows)==len(x.rows) and all(a is b for a,b in zip(x.rows,expected_rows,strict=True)),'exact seed/operand order and original parent identities')
            want=Disposition.COMPLETE if all(row.status is Disposition.COMPLETE for row in x.rows) else Disposition.UNAVAILABLE
            need(x.status is want and all(row.status in (Disposition.COMPLETE,Disposition.UNAVAILABLE) for row in x.rows),'failure cannot become scientific exclusion')
            complete=tuple(seed for seed in MATCH_SEEDS if all(row.status is Disposition.COMPLETE for row in x.rows if row.key.cell[3]==seed))
            need(x.complete_seeds==complete,'exact completed-seed census')
            need(x.causes==tuple((r.key,r.cause) for r in x.rows if r.status is Disposition.UNAVAILABLE),'actual scientific unavailable causes, not arbitrary exclusions')
            need(x.status is not Disposition.COMPLETE or x.complete_seeds==MATCH_SEEDS,'never partial-seed primary support')
        return self
    def region(self,region):
        self.validate();return tuple(x for x in self.sessions if x.region==region)
    def coverage(self):
        self.validate()
        return tuple({'region':x.region,'session':x.session,'animal':x.animal,'status':x.status.value,
                      'required_seed_count':10,'completed_seed_count':len(x.complete_seeds),
                      'complete_seeds':x.complete_seeds,'causes':x.causes,
                      'included_in_every_comparison':x.status is Disposition.COMPLETE} for x in self.sessions)

def build(collection):
    need(type(collection) is Collection,'actual typed collection producer')
    seal=collection.validate_seal();cat=collection.catalogue
    operands=tuple(dict.fromkeys((k.panel,k.arm) for k in cat.expected))
    by={(r.key.cell[1],r.key.session,r.key.cell[3],r.key.panel,r.key.arm):r for r in seal}
    sessions=[]
    for region in cat.regions:
        for session,animal in cat.session_animals:
            rows=tuple(by[region,session,seed,panel,arm] for seed in MATCH_SEEDS for panel,arm in operands)
            complete=tuple(seed for seed in MATCH_SEEDS if all(by[region,session,seed,p,a].status is Disposition.COMPLETE for p,a in operands))
            status=Disposition.COMPLETE if complete==MATCH_SEEDS else Disposition.UNAVAILABLE
            causes=tuple((r.key,r.cause) for r in rows if r.status is Disposition.UNAVAILABLE)
            sessions.append(SessionSupport(region,session,animal,status,MATCH_SEEDS,complete,operands,rows,causes))
    return CommonSupport(collection,seal,tuple(sessions),cat.animals).validate()
