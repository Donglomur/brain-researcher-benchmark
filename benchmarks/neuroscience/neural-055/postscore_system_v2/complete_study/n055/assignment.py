"""Exact binary64 maximum assignment with lexicographic secondary objective."""
import math
from .common import require

def assign(scores):
    n=len(scores)
    require(n>0 and all(len(row)==n for row in scores),'square full assignment')
    pairs=[];denominator=1
    for row in scores:
        r=[]
        for value in row:
            v=float(value);require(math.isfinite(v),'finite assignment scores')
            a,b=v.as_integer_ratio();denominator=max(denominator,b);r.append((a,b))
        pairs.append(r)
    base=n+1;priority=base**n
    # Secondary magnitude is strictly < priority, so no non-tied primary can change.
    cost=[[-(a*(denominator//b)*priority-j*base**(n-1-i)) for j,(a,b) in enumerate(row)] for i,row in enumerate(pairs)]
    u=[0]*(n+1);v=[0]*(n+1);p=[0]*(n+1);way=[0]*(n+1)
    for i in range(1,n+1):
        p[0]=i;j0=0;minimum=[None]*(n+1);used=[False]*(n+1)
        while True:
            used[j0]=True;i0=p[j0];delta=None;j1=None
            for j in range(1,n+1):
                if used[j]:continue
                cur=cost[i0-1][j-1]-u[i0]-v[j]
                if minimum[j] is None or cur<minimum[j]:minimum[j]=cur;way[j]=j0
                if delta is None or minimum[j]<delta:delta=minimum[j];j1=j
            for j in range(n+1):
                if used[j]:u[p[j]]+=delta;v[j]-=delta
                elif minimum[j] is not None:minimum[j]-=delta
            j0=j1
            if p[j0]==0:break
        while True:
            j1=way[j0];p[j0]=p[j1];j0=j1
            if j0==0:break
    result=[None]*n
    for j in range(1,n+1):result[p[j]-1]=j-1
    require(sorted(result)==list(range(n)),'complete exact bijection')
    return result
