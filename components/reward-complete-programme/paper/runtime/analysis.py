"""Independent finite-sample summaries, learning geometry and inference.

Native source conventions are separately collected, never silently substituted.
"""
import math
import statistics as st
import itertools
from reward_common import need, finite_number


def summary(values):
    values=[finite_number(x) for x in values]
    if not values:return {'n':0,'mean':None,'sd':None,'sem':None,'median':None}
    sd=st.stdev(values) if len(values)>1 else None
    return {'n':len(values),'mean':st.mean(values),'sd':sd,
            'sem':None if sd is None else sd/math.sqrt(len(values)),'median':st.median(values)}


def _betacf(a,b,x):
    tiny=1e-300; qab=a+b; qap=a+1; qam=a-1
    c=1.0;d=1-qab*x/qap;d=tiny if abs(d)<tiny else d;d=1/d;h=d
    for m in range(1,401):
        m2=2*m;aa=m*(b-m)*x/((qam+m2)*(a+m2))
        d=1+aa*d;d=tiny if abs(d)<tiny else d;c=1+aa/c;c=tiny if abs(c)<tiny else c
        d=1/d;h*=d*c
        aa=-(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
        d=1+aa*d;d=tiny if abs(d)<tiny else d;c=1+aa/c;c=tiny if abs(c)<tiny else c
        d=1/d;delta=d*c;h*=delta
        if abs(delta-1)<3e-14:return h
    raise ValueError('Incomplete beta failed to converge')


def ibeta(a,b,x):
    need(a>0 and b>0 and 0<=x<=1,'Beta domain')
    if x in (0,1):return float(x)
    bt=math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log1p(-x))
    return bt*_betacf(a,b,x)/a if x<(a+1)/(a+b+2) else 1-bt*_betacf(b,a,1-x)/b


def t_two_tail(t,df):
    need(df>0,'Positive t degrees of freedom')
    return ibeta(df/2,.5,df/(df+t*t))


def compare(x,y=None,paired=False,one_sample=None):
    x=[finite_number(v) for v in x]
    if paired:
        need(y is not None and len(x)==len(y),'Paired observations')
        x=[a-finite_number(b) for a,b in zip(x,y)];one_sample=0;y=None
    if one_sample is not None:
        need(len(x)>1,'Two replicates for t inference')
        effect=st.mean(x)-finite_number(one_sample);v=st.variance(x)/len(x);df=len(x)-1
    else:
        need(y is not None and len(x)>1 and len(y)>1,'Two groups with replication')
        y=[finite_number(v) for v in y];vx=st.variance(x)/len(x);vy=st.variance(y)/len(y)
        effect=st.mean(x)-st.mean(y);v=vx+vy
        denom=vx*vx/(len(x)-1)+vy*vy/(len(y)-1)
        df=v*v/denom if denom>0 else None
    if v==0 or df is None:
        return {'status':'degenerate','effect':effect,'se':0,'df':df,'p':None}
    t=effect/math.sqrt(v)
    return {'status':'computed','effect':effect,'se':math.sqrt(v),'t':t,'df':df,'p':t_two_tail(t,df)}


def regression(x,y):
    need(len(x)==len(y)>=2,'Regression observations')
    x=[finite_number(v) for v in x];y=[finite_number(v) for v in y]
    mx,my=st.mean(x),st.mean(y);xx=math.fsum((v-mx)**2 for v in x)
    need(xx>0,'Nonconstant regressor')
    slope=math.fsum((a-mx)*(b-my) for a,b in zip(x,y))/xx;intercept=my-slope*mx
    rss=math.fsum((b-(intercept+slope*a))**2 for a,b in zip(x,y));yy=math.fsum((v-my)**2 for v in y)
    df=len(x)-2;se=math.sqrt(rss/df/xx) if df>0 else None
    return {'slope':slope,'intercept':intercept,'rss':rss,'r2':None if yy==0 else 1-rss/yy,
            'n':len(x),'df':df,'slope_se':se,'p_slope_zero':t_two_tail(slope/se,df) if se and df else None}


def adjust_p(pvalues,method):
    p=[finite_number(v) for v in pvalues];need(all(0<=v<=1 for v in p),'Probability range')
    n=len(p)
    if method=='bonferroni':return [min(1,v*n) for v in p]
    need(method in ('BH','BY','Holm'),'Multiplicity method')
    order=sorted(range(n),key=lambda i:p[i]);out=[0.0]*n
    if method=='Holm':
        running=0
        for j,i in enumerate(order):running=max(running,min(1,(n-j)*p[i]));out[i]=running
    else:
        factor=sum(1/i for i in range(1,n+1)) if method=='BY' else 1;running=1
        for j in range(n-1,-1,-1):
            i=order[j];running=min(running,p[i]*n/(j+1)*factor);out[i]=running
    return out


def variance_test(x,y):
    need(len(x)>1 and len(y)>1,'Variance replication');vx,vy=st.variance(x),st.variance(y)
    if min(vx,vy)==0:return {'status':'degenerate','variance_x':vx,'variance_y':vy,'p':None}
    f=vx/vy;d1,d2=len(x)-1,len(y)-1;cdf=ibeta(d1/2,d2/2,d1*f/(d1*f+d2))
    return {'status':'computed','F':f,'df1':d1,'df2':d2,'p':min(1,2*min(cdf,1-cdf))}


def welch_anova(groups):
    need(len(groups)>1 and all(len(g)>1 for g in groups),'ANOVA replicated groups')
    n=[len(g) for g in groups];means=[st.mean(g) for g in groups];v=[st.variance(g) for g in groups]
    if any(s==0 for s in v):return {'status':'degenerate','p':None}
    w=[a/b for a,b in zip(n,v)];W=sum(w);mu=sum(a*b for a,b in zip(w,means))/W;k=len(groups)
    q=sum((1-a/W)**2/(nn-1) for a,nn in zip(w,n));df2=(k*k-1)/(3*q)
    f=sum(a*(b-mu)**2 for a,b in zip(w,means))/(k-1)/(1+2*(k-2)*q/(k*k-1))
    p=1-ibeta((k-1)/2,df2/2,(k-1)*f/((k-1)*f+df2))
    return {'status':'computed','F':f,'df1':k-1,'df2':df2,'p':p}


def ranks(values):
    values=[finite_number(v) for v in values];order=sorted(range(len(values)),key=values.__getitem__)
    result=[0]*len(values);ties=[];i=0
    while i<len(order):
        j=i+1
        while j<len(order) and values[order[j]]==values[order[i]]:j+=1
        for k in order[i:j]:result[k]=(i+1+j)/2
        ties.append(j-i);i=j
    return result,ties


def mann_whitney(x,y,method='asymptotic',exact_max_allocations=200000):
    need(x and y,'Rank-test observations');n,m=len(x),len(y);r,ties=ranks(list(x)+list(y))
    u=sum(r[:n])-n*(n+1)/2;center=n*m/2
    if method=='exact_permutation':
        total=math.comb(n+m,n);need(total<=exact_max_allocations,'Registered exact permutation resource bound')
        distance=abs(u-center);extreme=0
        for inds in itertools.combinations(range(n+m),n):
            test=sum(r[i] for i in inds)-n*(n+1)/2
            extreme+=abs(test-center)>=distance-1e-12
        p=extreme/total;extra={'allocations':total,'ties':'label permutation conditional on pooled observations'}
    else:
        need(method=='asymptotic','Declared rank inference')
        N=n+m;variance=n*m/12*((N+1)-sum(t*t*t-t for t in ties)/(N*(N-1)))
        if variance<=0:return {'status':'degenerate','U':u,'p':None}
        z=max(0,abs(u-center)-.5)/math.sqrt(variance)
        p=math.erfc(z/math.sqrt(2));extra={'continuity_correction':.5,'tie_corrected':True}
    return dict(status='computed',U=u,n_x=n,n_y=m,p=p,method=method,**extra)


def gamma_upper_regularized(a,x):
    need(a>0 and x>=0,'Gamma domain')
    if x==0:return 1.0
    factor=math.exp(-x+a*math.log(x)-math.lgamma(a))
    if x<a+1:
        term=1/a;total=term
        for n in range(1,1001):
            term*=x/(a+n);total+=term
            if abs(term)<abs(total)*1e-14:return max(0,min(1,1-factor*total))
    else:
        tiny=1e-300;b=x+1-a;c=1/tiny;d=1/b;h=d
        for n in range(1,1001):
            an=-n*(n-a);b+=2;d=an*d+b;d=tiny if abs(d)<tiny else d
            c=b+an/c;c=tiny if abs(c)<tiny else c;d=1/d;delta=d*c;h*=delta
            if abs(delta-1)<1e-14:return max(0,min(1,factor*h))
    raise ValueError('Incomplete gamma failed to converge')


def kruskal_wallis(groups):
    need(len(groups)>1 and all(groups),'Independent rank groups')
    flat=[v for g in groups for v in g];r,ties=ranks(flat);N=len(r);offset=0;terms=[]
    for group in groups:
        terms.append(sum(r[offset:offset+len(group)])**2/len(group));offset+=len(group)
    correction=1-sum(t**3-t for t in ties)/(N**3-N)
    if correction<=0:return {'status':'degenerate','p':None}
    h=max(0,(12*sum(terms)/(N*(N+1))-3*(N+1))/correction);df=len(groups)-1
    return {'status':'computed','H':h,'df':df,'p':gamma_upper_regularized(df/2,h/2),
            'method':'tie_corrected_chi_square_approximation','group_n':[len(g) for g in groups]}


def scaling_bootstrap(group_animals,nominal_iti,replicates,seed,query_iri):
    """Animal-within-condition resampling, never four means as many animals."""
    import random
    need(len(group_animals)==len(nominal_iti)==4,'Original four-condition scaling fit')
    need(type(replicates) is int and 1<=replicates<=100000,'Bounded registered bootstrap')
    need(all(g and all(finite_number(v)>0 for v in g) for g in group_animals),'Positive uncensored onset support')
    need(all(finite_number(v)>0 for v in query_iri),'Positive query IRI')
    rng=random.Random(seed);x=[math.log10(v+4.25) for v in nominal_iti];draws=[]
    for _ in range(replicates):
        y=[math.log10(st.mean(rng.choice(g) for _ in g)) for g in group_animals];fit=regression(x,y)
        draws.append({'slope':fit['slope'],'predicted_onsets':[10**(fit['intercept']+fit['slope']*math.log10(v)) for v in query_iri]})
    return {'draws':draws,'resampling_unit':'animals_within_each_condition','seed':seed,
            'censoring_handling':'requires explicit separate sensitivity analysis; censored subjects cannot be silently removed'}


def changepoint(values, fraction=.75, direction='increase'):
    need(0<fraction<=1 and direction in ('increase','decrease'),'Changepoint convention')
    vals=[finite_number(x) for x in values];cs=[];total=0
    for x in vals:total+=x;cs.append(total)
    stop=len(cs)
    while stop>=3:
        y=cs[:stop];dx=stop-1;dy=y[-1]-y[0];denom=math.hypot(dx,dy)
        if denom==0:return {'status':'degenerate','trial':None,'cumsum':cs}
        signed=[(v-y[0])-dy*i/dx for i,v in enumerate(y)]
        dist=[abs(z)*dx/denom for z in signed];peak=max(dist)
        if peak<=1e-15:return {'status':'no_change','trial':None,'cumsum':cs}
        i=next(i for i,d in enumerate(dist) if d>=fraction*peak)
        correct=signed[i]<0 if direction=='increase' else signed[i]>0
        if correct:
            norm=None
            if y[-1]!=0:
                yn=[v/y[-1] for v in y];d=yn[-1]-yn[0]
                norm=abs((yn[i]-yn[0])-d*i/dx)*dx/math.hypot(dx,d)
            return {'status':'computed','trial':i+1,'distance':dist[i],'normalized_distance':norm,
                    'horizon':stop,'cumsum':cs,'branch':'independent_actual_first_point_chord'}
        stop=i+1
    return {'status':'no_change','trial':None,'cumsum':cs}


def animal_analysis(animal):
    trials=[r for r in animal['trials'] if r['kind'] in ('CS_plus','shock')]
    valid=[r for r in trials if r.get('D') is not None or r.get('behavior',{}).get('status')=='computed']
    vals=[r['D'] if 'D' in r else r['behavior']['freezing_change'] for r in valid]
    perday={}
    for r in valid:
        perday.setdefault(r['session_number'],[]).append(r.get('delta_hz',r.get('behavior',{}).get('freezing_change')))
    native_learner=sum(st.mean(x)>=.5 for x in perday.values())>=2
    if animal['condition'] in ('60s-10percent','FC-45s','FC-135s'):native_learner=None
    behavior=changepoint(vals) if len(vals)>=3 and len(valid)==len(trials) else {'status':'unscorable','trial':None,'reason':'missing_or_short_behavior_history'}
    da=[r['cue_da']['auc'] for r in trials if r.get('cue_da',{}).get('status')=='computed']
    direction='decrease' if animal['condition'].startswith('FC-') else 'increase'
    da_onset=changepoint(da,direction=direction) if len(da)>=3 and len(da)==len(trials) else {'status':'unscorable','trial':None,'reason':'missing_or_short_neural_history'}
    reward=[r['reward_da']['auc'] for r in trials if r.get('reward_da',{}).get('status')=='computed']
    norm=st.mean(sorted(reward,reverse=True)[:3]) if len(reward)>=3 else None
    return {'animal_id':animal['animal_id'],'condition':animal['condition'],'n_trials':len(trials),
            'n_behavior_observed':len(valid),'behavior':behavior,'cue_da_onset_fixed_horizon':da_onset,
            'native_learner_diagnostic':native_learner,'daily_behavior':{str(k):summary(v) for k,v in perday.items()},
            'cue_behavior':summary(vals),'cue_da_auc':summary(da),'reward_da_auc':summary(reward),
            'retrospective_top3_reward_normalizer':norm,
            'missing_behavior_trials':[r['trial_id'] for r in trials if r not in valid],
            'interpretation':'Independent fixed-horizon geometry; not native1.5×behavior DA horizon'}


def analyse(prepared):
    animals=[animal_analysis(a) for a in prepared['animals']];groups={}
    for a in animals:groups.setdefault(a['condition'],[]).append(a)
    out={'schema':'reward_analysis_v1','animals':animals,'groups':{},'scaling':None}
    for c,rows in groups.items():
        onset=[a['behavior']['trial'] for a in rows if a['behavior']['trial'] is not None]
        out['groups'][c]={'animals':[a['animal_id'] for a in rows],'onset_summary':summary(onset),
                          'censored_or_unscorable':len(rows)-len(onset)}
    four=['30s','60s','300s','600s'];x=[];y=[]
    for c in four:
        val=out['groups'].get(c,{}).get('onset_summary',{}).get('mean')
        if val is not None and val>0:x.append(math.log10(float(c[:-1])+4.25));y.append(math.log10(val))
    if len(x)==4:out['scaling']=regression(x,y)
    return out
