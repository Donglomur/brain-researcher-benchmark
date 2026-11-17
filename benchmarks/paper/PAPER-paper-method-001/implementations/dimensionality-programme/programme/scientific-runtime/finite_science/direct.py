"""Independent ordered-tuple oracle. No optimized/author estimator imports."""
from itertools import permutations,product,combinations
import math
from .common import PATTERNS,prepare,falling,require,finalize

def compute(payload):
    x,mask,rw,cw,assignments,finite=prepare(payload)
    protocol=payload['protocol']; req=payload['request']; T,P,Q=x.shape
    mode=req.get('correction','both'); row_distinct=mode in ('row','both'); col_distinct=mode in ('column','both')
    counts=[]; estimate=0
    for index,pat in enumerate(PATTERNS):
        if protocol.get('axis')=='uncentered' and index not in (0,2):counts.append(0);continue
        r=max(pat)+1
        if finite:require(P>=min(finite[0],r) and Q>=min(finite[1],2),'finite HT tuple inclusion is zero','insufficient_support')
        count=(P**r if finite or not row_distinct else falling(P,r))*(Q**2 if finite or not col_distinct else falling(Q,2))
        require(count>0,'insufficient tuple support','insufficient_support');counts.append(count);estimate+=count*len(assignments)
    require(type(req.get('max_tuples'))is int and estimate<=req['max_tuples'],'direct tuple reservation too small')
    values=[]; valid_counts=[];normalizers=[]
    for pat,totalcount in zip(PATTERNS,counts):
        if totalcount==0:values.append(0.);valid_counts.append(0);normalizers.append([]);continue
        r=max(pat)+1; sums=[];valid=0;pattern_norms=[]
        for trial in assignments:
            rowiter=product(range(P),repeat=r) if finite or not row_distinct else permutations(range(P),r)
            subtotal=[];weightterms=[]
            for row in rowiter:
                coliter=product(range(Q),repeat=2) if finite or not col_distinct else permutations(range(Q),2)
                for col in coliter:
                    coords=[(row[pat[k]],col[k//2]) for k in range(4)]
                    slots=[(trial[k],*coords[k]) for k in range(4)]
                    if not all(mask[s] for s in slots):continue
                    val=math.prod(float(x[s]) for s in slots)
                    if req.get('known_noise'):
                        def cov(a,b):
                            if coords[a]!=coords[b]:return 0.
                            dt=abs(trial[a]-trial[b]);rho=protocol['rho']
                            return protocol['sigma']**2*((rho**dt) if protocol['noise_law']=='gaussian_entry_ar1' else (1. if dt==0 else rho))
                        for a,b in combinations(range(4),2):
                            others=[k for k in range(4) if k not in (a,b)]
                            val-=cov(a,b)*float(x[slots[others[0]]])*float(x[slots[others[1]]])
                        val+=cov(0,1)*cov(2,3)+cov(0,2)*cov(1,3)+cov(0,3)*cov(1,2)
                    weight=math.prod(float(rw[i]) for i in set(row))*math.prod(float(cw[j]) for j in set(col))
                    if protocol.get('mask_law')=='independent_entry_bernoulli':
                        units=set(coords) if protocol['mask_unit']=='entry_shared_trials' else set(slots)
                        weight/=protocol['mask_probability']**len(units)
                    val*=weight;weightterms.append(weight)
                    if finite:
                        R,C=finite; nr=len(set(row));nc=len(set(col))
                        pi=falling(P,nr)/falling(R,nr)*falling(Q,nc)/falling(C,nc)
                        val/=pi*R**r*C**2
                    subtotal.append(val);valid+=1
            denominator=1 if finite else totalcount
            if protocol.get('mask_law')=='literal_valid_count':
                require(not finite,'literal valid count is not HT');denominator=len(subtotal)
                require(denominator>0,'no valid tuples','insufficient_support')
            if req.get('weight_normalization')=='self_normalized_diagnostic':
                denominator=math.fsum(weightterms);require(denominator>0,'zero self-normalization support','insufficient_support')
            pattern_norms.append(denominator)
            sums.append(math.fsum(subtotal)/denominator)
        values.append(math.fsum(sums)/len(sums));valid_counts.append(valid);normalizers.append(pattern_norms)
    if protocol.get('axis')=='uncentered':values[1]=values[3]=values[4]=0.
    return finalize(values,dict(P=P,Q=Q,T=T,precision='float64',correction=mode,tuple_counts=counts,valid_tuple_counts=valid_counts,normalizers=normalizers,weight_normalization=req.get('weight_normalization','fixed_tuple_count'),trial_assignments=assignments,normalization=('finite_HT' if finite else ('self_normalized_diagnostic' if req.get('weight_normalization')=='self_normalized_diagnostic' else ('literal_valid_count' if protocol.get('mask_law')=='literal_valid_count' else 'fixed_ordered_tuple_count'))),finite_population=finite,implementation='independent_direct_v1'))
