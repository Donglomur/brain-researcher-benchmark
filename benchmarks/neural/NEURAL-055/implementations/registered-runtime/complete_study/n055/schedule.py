"""Actual domain-separated deterministic schedule source; never run by source controls."""
import hashlib
from .common import encoded, require

class Counter:
    def __init__(self,domain):
        self.prefix=encoded({'protocol':'complete-scientific-api-design-s3','domain':domain})
        self.index=0
    def block(self):
        result=int.from_bytes(hashlib.sha256(self.prefix+b'\x00'+self.index.to_bytes(16,'big')).digest(),'big')
        self.index+=1
        return result
    def integer(self,n):
        require(type(n)is int and n>0,'positive draw range')
        limit=(1<<256)//n*n
        while True:
            value=self.block()
            if value<limit:return value%n
    def permutation(self,n):
        values=list(range(n))
        for i in range(n-1,0,-1):
            j=self.integer(i+1);values[i],values[j]=values[j],values[i]
        return values
    def unit53(self):
        return ((self.block()>>(256-53))+.5)/(1<<53)

def derangement(seed,person):
    rng=Counter({'purpose':'alignment','seed':seed,'outer':person})
    for attempt in range(10000):
        values=rng.permutation(200)
        if all(i!=v for i,v in enumerate(values)):
            return {'indices':values,'attempts':attempt+1,'domain':{'seed':seed,'outer':person}}
    raise ValueError('alignment schedule unavailable after 10000 original attempts')

def development(concepts,training_ids):
    require(len(concepts)==16540 and len(training_ids)==16540,'complete training identity roster')
    unique=set(concepts);require(len(unique)==1654,'full concept coverage')
    ordered=sorted(unique,key=lambda c:(hashlib.sha256(('NEURAL-055/draft1/concept-development/'+c).encode()).digest(),c))
    held=ordered[:330];rows={c:[i for i,x in enumerate(concepts) if x==c] for c in held}
    require(all(len(v)==10 for v in rows.values()),'ten distinct exemplars per dev concept')
    for c,v in rows.items():
        rows[c]=sorted(v,key=lambda i:(hashlib.sha256(('NEURAL-055/design1/selection-exemplar/'+training_ids[i]).encode()).digest(),training_ids[i]))
    panels=[[rows[c][rank] for c in held] for rank in range(10)]
    fit=[i for i,c in enumerate(concepts) if c not in set(held)]
    require(len(fit)==13240 and len({i for p in panels for i in p})==3300,'full nested support')
    return {'fit':fit,'selection_panels':panels,'development_concepts':held}
