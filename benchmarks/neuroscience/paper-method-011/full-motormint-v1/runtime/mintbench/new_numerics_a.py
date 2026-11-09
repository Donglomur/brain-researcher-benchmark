"""Owner-derived numerical extension; independent helper never reads this body.

Cycle distances follow original MathML inf454. Student-t tail is obtained by
transforming the symmetric t-density to regularized incomplete beta; beta is
computed with a convergent continued fraction (DLMF8.17), not the helper's code.
"""
import bisect
import math
from .validation import exact, need, matrix, vector, integer, finite


def _positive(x):
    finite(x); need(x>0,'positive original scale'); return x


def _beta_fraction(a,b,x):
    tiny=1e-300
    c=1.0;d=1-(a+b)*x/(a+1)
    if abs(d)<tiny:d=tiny
    d=1/d;h=d
    for m in range(1,10001):
        for term in (m*(b-m)*x/((a-1+2*m)*(a+2*m)),
                     -(a+m)*(a+b+m)*x/((a+2*m)*(a+1+2*m))):
            d=1+term*d;c=1+term/c
            if abs(d)<tiny:d=tiny
            if abs(c)<tiny:c=tiny
            d=1/d;delta=d*c;h*=delta
        if abs(delta-1)<2e-14:
            finite(h);return h
    raise ValueError('incomplete beta convergence failure')


def _beta(x,a,b):
    if x<=0:return 0.0
    if x>=1:return 1.0
    front=math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log1p(-x))
    answer=front*_beta_fraction(a,b,x)/a if x<(a+1)/(a+b+2) else 1-front*_beta_fraction(b,a,1-x)/b
    need(-1e-12<=answer<=1+1e-12,'probability bounds')
    return max(0.0,min(1.0,answer))


def _paired(p):
    exact(p,('left','right','unit_ids'),'paired test')
    left=vector(p['left']);right=vector(p['right'],len(left));ids=p['unit_ids'];n=len(left)
    need(n>=2 and type(ids) is list and len(ids)==n and len(set(ids))==n and all(type(x) is str and x for x in ids),'original unique paired units')
    diff=[a-b for a,b in zip(left,right)];mean=math.fsum(diff)/n
    sd=math.sqrt(math.fsum((x-mean)**2 for x in diff)/(n-1));se=sd/math.sqrt(n)
    t=mean/se if se else None
    probability=_beta((n-1)/(n-1+t*t),(n-1)/2,.5) if t is not None else None
    for value in (mean,sd,se):finite(value)
    if t is not None:finite(t)
    return {'n':n,'mean_difference':mean,'sample_sd':sd,'standard_error':se,'t_statistic':t,
            'degrees_of_freedom':n-1,'two_sided_p':probability,'undefined_reason':None if t is not None else 'zero_standard_error'}


def _interval(p):
    exact(p,('draws','alpha'),'draw interval');draws=p['draws'];alpha=finite(p['alpha'])
    need(type(draws) is list and draws and 0<alpha<1,'nonempty prespecified interval')
    for value in draws:
        if value is not None:finite(value)
    undefined=sum(x is None for x in draws)
    answer=None
    if not undefined:
        ordered=sorted(draws)
        def quantile(q):
            position=(len(ordered)-1)*q;lo=int(position);hi=min(len(ordered)-1,lo+1)
            return ordered[lo]+(ordered[hi]-ordered[lo])*(position-lo)
        answer=[quantile(alpha/2),quantile(1-alpha/2)]
    return {'draw_count':len(draws),'undefined_count':undefined,'interval':answer,
            'status':'undefined_draws' if undefined else 'complete'}


def _cycle(p):
    exact(p,('neural_a','neural_b','muscle','phase','velocity','scales','pair_policy','edges',
             'ordering_draws','ordering_min_neural_difference','ordering_tie_policy'),'Cycle metric')
    a=matrix(p['neural_a']);n=len(a);need(n>=2,'at least two states')
    b=matrix(p['neural_b'],n,len(a[0]));muscle=matrix(p['muscle'],n,7)
    phase=vector(p['phase'],n);velocity=vector(p['velocity'],n)
    scale=p['scales'];exact(scale,('muscle_sd','phase_sd','phase_period','velocity_sd'),'original scales')
    sd=vector(scale['muscle_sd'],7)
    for value in sd:_positive(value)
    phase_sd=_positive(scale['phase_sd']);period=_positive(scale['phase_period']);velocity_sd=_positive(scale['velocity_sd'])
    need(p['pair_policy'] in ('unique_offdiagonal','full_ordered_with_diagonal'),'supplied original pair enumeration')
    def pairs():
        return ((i,j) for i in range(n) for j in (range(i+1,n) if p['pair_policy']=='unique_offdiagonal' else range(n)))
    def distance(i,j):
        v={'neural':math.dist(a[i],a[j]),'partition':math.dist(b[i],b[j]),
           'muscle':math.sqrt(math.fsum(((x-y)/s)**2 for x,y,s in zip(muscle[i],muscle[j],sd))),
           'kinematic':math.hypot(((phase[i]-phase[j]+period/2)%period-period/2)/phase_sd,(velocity[i]-velocity[j])/velocity_sd)}
        for x in v.values():finite(x)
        return v
    sums={k:0.0 for k in ('neural','muscle','kinematic','partition')};count=0
    for i,j in pairs():
        for key,value in distance(i,j).items():sums[key]+=value
        count+=1
    means={key:_positive(value/count) for key,value in sums.items()}
    edges=p['edges'];exact(edges,sums,'fixed joint histogram axes')
    for value in edges.values():
        vector(value);need(len(value)>=2 and all(x<y for x,y in zip(value,value[1:])),'strict fixed edges')
    def cell(value,bins):
        return None if value<bins[0] or value>bins[-1] else min(len(bins)-2,bisect.bisect_right(bins,value)-1)
    hist={key:{'counts':[[0]*(len(edges[key])-1) for _ in range(len(edges['neural'])-1)],'outside':0,'total':count} for key in sums if key!='neural'}
    for i,j in pairs():
        d={key:value/means[key] for key,value in distance(i,j).items()};y=cell(d['neural'],edges['neural'])
        for key,h in hist.items():
            x=cell(d[key],edges[key])
            if x is None or y is None:h['outside']+=1
            else:h['counts'][y][x]+=1
    draws=p['ordering_draws'];need(type(draws) is list,'original draw sequence')
    threshold=finite(p['ordering_min_neural_difference'],nonnegative=True)
    tie=p['ordering_tie_policy'];need(tie in ('include_as_disagreement','exclude'),'original tie policy')
    order={key:dict(draw_count=len(draws),eligible=0,concordant=0,discordant=0,ties=0,neural_excluded=0,concordance=None) for key in hist}
    for draw in draws:
        need(type(draw) is list and len(draw)==4,'two original state pairs')
        for index in draw:integer(index,0,n-1)
        i,j,k,l=draw
        need(p['pair_policy']!='unique_offdiagonal' or (i!=j and k!=l),'offdiagonal original pairs')
        first,second=distance(i,j),distance(k,l);neural=(first['neural']-second['neural'])/means['neural']
        for key,result in order.items():
            if abs(neural)<=threshold:result['neural_excluded']+=1;continue
            difference=(first[key]-second[key])/means[key]
            if difference==0:
                result['ties']+=1
                if tie=='include_as_disagreement':result['eligible']+=1
            else:
                result['eligible']+=1
                result['concordant' if neural*difference>0 else 'discordant']+=1
    for result in order.values():
        if result['eligible']:result['concordance']=result['concordant']/result['eligible']
    return {'pair_count':count,'means':means,'histograms':hist,'ordering':order}


def evaluate(kind,payload):
    need(kind in ('cycle_geometry','paired_test','draw_interval'),'new declared numerical kind')
    return {'cycle_geometry':_cycle,'paired_test':_paired,'draw_interval':_interval}[kind](payload)
