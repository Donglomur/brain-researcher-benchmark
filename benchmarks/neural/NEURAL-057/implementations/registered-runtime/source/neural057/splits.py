"""Target-independent person/concept grouping and physical time-coordinate selection."""
import hashlib
from .domain import need,real,PEOPLE,WINDOWS

def concept_groups(concepts):
    need(len(set(concepts))==1654,'all training concept IDs before any target filtering')
    order=sorted(set(concepts),key=lambda x:(hashlib.sha256(('NEURAL-057/v1/concept/'+x).encode()).hexdigest(),x))
    # Fixed 60/20/20 split: no taxonomic class balancing or target-driven dropping.
    return {'fit':tuple(order[:994]),'tune':tuple(order[994:1324]),'calibrate':tuple(order[1324:])}

def person_roles(outer):
    need(outer in PEOPLE,'outer person')
    other=tuple(p for p in PEOPLE if p!=outer)
    return {'final_train':other,'inner_tune':other[0],'inner_train':other[1:]}

def window_indices(times, channel_names):
    need(type(times) is list and len(times)==100,'original 100 sample coordinates')
    need(type(channel_names) is list and len(channel_names)==17 and len(set(channel_names))==17 and all(type(x) is str and x for x in channel_names),'17 original whitened coordinates')
    micro=[]
    for t in times:
        real(t);v=round(t*1000000);need(abs(t-v/1000000)<=1e-7,'coordinate representable to original microsecond tolerance');micro.append(v)
    need(all(b-a==10000 for a,b in zip(micro,micro[1:])),'verified released 100Hz coordinate coverage')
    result={k:tuple(i for i,t in enumerate(micro) if lo<=t<hi) for k,(lo,hi) in WINDOWS.items()}
    need(len(result['PRE'])==10 and len(result['LATE'])==20,'both prospective predeclared windows completely covered')
    need(not set(result['PRE']) & set(result['LATE']),'disjoint fixed windows')
    return result

def rows_for(metadata, concepts, assigned):
    allowed=set(concepts)
    return tuple(r['row'] for r in metadata if r['concept_id'] in allowed and assigned[r['concept_id']] is not None)
