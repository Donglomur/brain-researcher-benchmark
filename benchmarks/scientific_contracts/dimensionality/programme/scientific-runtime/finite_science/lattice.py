"""Independent equality-partition / Möbius contraction reference.

Exact row equality partitions retain all 15 possibilities for t5, including
2+2. Einsum computes each unconstrained contraction; partition Möbius sums
remove coincidences. No author code and no direct reference import.
"""
from itertools import product,combinations
from math import factorial,prod
from .common import PATTERNS,prepare,falling,require,finalize

def partitions(n):
    def visit(prefix):
        if len(prefix)==n:yield tuple(prefix);return
        for k in range(max(prefix,default=-1)+2):yield from visit(prefix+[k])
    yield from visit([])

def mu(part):
    return prod((-1)**(part.count(k)-1)*factorial(part.count(k)-1) for k in set(part))

def contraction(matrices, rows, cols, rowpartition,colpartition, rowweights,colweights, extra, force_pairs):
    import numpy as np
    # Disjoint-set equality union over current Möbius row/column blocks.
    rp={v:v for v in rowpartition};cp={v:v for v in colpartition}
    def find(parent,v):
        while parent[v]!=v:v=parent[v]
        return v
    for a,b in force_pairs:
        ra,rb=find(rp,rowpartition[rows[a]]),find(rp,rowpartition[rows[b]])
        ca,cb=find(cp,colpartition[cols[a]]),find(cp,colpartition[cols[b]])
        rp[rb]=ra;cp[cb]=ca
    rmap={k:find(rp,rowpartition[k]) for k in set(rows)}
    cmap={k:find(cp,colpartition[k]) for k in set(cols)}
    args=[]
    for slot,mat in matrices: args.extend([mat,[rmap[rows[slot]],4+cmap[cols[slot]]]])
    for block,w in enumerate(rowweights):args.extend([w,[rmap[block]]])
    for block,w in enumerate(colweights):args.extend([w,[4+cmap[block]]])
    for a,b,mat in extra:args.extend([mat,[rmap[a],4+cmap[b]]])
    # Weight vectors also account for free indices when covariance terms remove factors.
    args.append([])
    return float(np.einsum(*args,optimize='greedy'))

def compute(payload):
    import numpy as np
    x,mask,rw,cw,assignments,finite=prepare(payload);T,P,Q=x.shape
    req=payload['request'];protocol=payload['protocol'];mode=req.get('correction','both')
    distinct_r=mode in ('row','both'); distinct_c=mode in ('column','both')
    known=bool(req.get('known_noise'));work=0;limit=req.get('max_contractions')
    require(type(limit)is int and limit>0,'positive contraction reservation required')
    values=[];normalizers=[];partition_counts=[]
    for index,pattern in enumerate(PATTERNS):
        if protocol.get('axis')=='uncentered' and index not in (0,2):values.append(0.);normalizers.append([]);partition_counts.append([0,0]);continue
        r=max(pattern)+1
        if finite:require(P>=min(finite[0],r) and Q>=min(finite[1],2),'finite HT tuple inclusion is zero','insufficient_support')
        denominator=(falling(P,r) if distinct_r else P**r)*(falling(Q,2) if distinct_c else Q**2)
        require(finite or denominator>0,'insufficient support','insufficient_support')
        rp=list(partitions(r)) if finite or not distinct_r else [tuple(range(r))]
        cp=list(partitions(2)) if finite or not distinct_c else [(0,1)]
        sums=[];validden=[]
        for trial in assignments:
            total=0.;validtotal=0.;weighttotal=0.
            for er,ec in product(rp,cp):
                nr=max(er)+1;nc=max(ec)+1
                if finite and (nr>finite[0] or nc>finite[1]):continue
                if nr>P or nc>Q:continue
                rows=[er[k] for k in pattern];cols=[ec[k//2] for k in range(4)]
                factor=1.
                if finite:
                    R,C=finite
                    pi=falling(P,nr)/falling(R,nr)*falling(Q,nc)/falling(C,nc)
                    factor=1/(pi*R**r*C**2)
                extra=[]
                units={}
                for k in range(4):
                    unit=(rows[k],cols[k]) if protocol.get('mask_unit')=='entry_shared_trials' else (trial[k],rows[k],cols[k])
                    units.setdefault(unit,k)
                for k in units.values():
                    m=mask[trial[k]].astype(float)
                    if protocol.get('mask_law')=='independent_entry_bernoulli':m=m/protocol['mask_probability']
                    extra.append((rows[k],cols[k],m))
                terms=[(1.,list(enumerate(x[list(trial)])),[])]
                if known:
                    def c(a,b):
                        d=abs(trial[a]-trial[b]);rho=protocol['rho']
                        return protocol['sigma']**2*(rho**d if protocol['noise_law']=='gaussian_entry_ar1' else (1. if d==0 else rho))
                    for a,b in combinations(range(4),2):terms.append((-c(a,b),[(k,x[trial[k]]) for k in range(4) if k not in (a,b)],[(a,b)]))
                    for a,b,c_,d in [(0,1,2,3),(0,2,1,3),(0,3,1,2)]:terms.append((c(a,b)*c(c_,d),[],[(a,b),(c_,d)]))
                # Möbius removes any equality between the declared distinct blocks.
                for pr,pc in product(partitions(nr),partitions(nc)):
                    coefficient=mu(pr)*mu(pc)*factor
                    for scale,mats,forced in terms:
                        work+=1;require(work<=limit,'contraction reservation exceeded')
                        total+=coefficient*scale*contraction(mats,rows,cols,pr,pc,[rw]*nr,[cw]*nc,extra,forced)
                    if req.get('weight_normalization')=='self_normalized_diagnostic':
                        work+=1;require(work<=limit,'contraction reservation exceeded')
                        weighttotal+=coefficient*contraction([],rows,cols,pr,pc,[rw]*nr,[cw]*nc,extra,[])
                    if protocol.get('mask_law')=='literal_valid_count':
                        work+=1;require(work<=limit,'contraction reservation exceeded')
                        validtotal+=coefficient*contraction([],rows,cols,pr,pc,[np.ones(P)]*nr,[np.ones(Q)]*nc,extra,[])
            norm=1 if finite else denominator
            if protocol.get('mask_law')=='literal_valid_count':
                require(not finite,'literal valid-count is not finite HT');norm=validtotal;require(norm>0,'no valid tuples','insufficient_support')
            if req.get('weight_normalization')=='self_normalized_diagnostic':
                norm=weighttotal;require(norm>0,'zero self-normalization support','insufficient_support')
            sums.append(total/norm);validden.append(norm)
        values.append(float(np.mean(sums)));normalizers.append(validden);partition_counts.append([len(rp),len(cp)])
    if protocol.get('axis')=='uncentered':values[1]=values[3]=values[4]=0.
    return finalize(values,dict(P=P,Q=Q,T=T,precision='float64',correction=mode,weight_normalization=req.get('weight_normalization','fixed_tuple_count'),normalizers=normalizers,equality_partition_counts=partition_counts,trial_assignments=assignments,contractions=work,finite_population=finite,implementation='independent_partition_lattice_v1'))
