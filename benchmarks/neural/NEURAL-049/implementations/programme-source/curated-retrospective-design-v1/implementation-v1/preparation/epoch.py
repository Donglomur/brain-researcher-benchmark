"""Scalar epoch/assignment operators; no authentic inputs at import."""
import hashlib
import math
from . import contracts as c

def window(event,start,samples):
    c.need(c.finite(event) and c.finite(start) and c.integer(samples),'finite uniform grid')
    event=float(event);start=float(start)
    k0=math.ceil(500*(event-5-start))
    first=start+k0/500;last=start+(k0+4999)/500
    r0=first-event;rlast=last-event;offset=r0+5
    c.need(-5<=r0<5 and -5<=rlast<5 and 0<=offset<.002,'exact half-open epoch/fractional alignment; no tolerance substitution')
    # Independent exact grid membership, not inferred from rounded k0 alone.
    for width,count in ((1.,500),(.5,250)):
        for j in range(int(10/width)):
            lo=-5+j*width;hi=lo+width
            n=sum(lo<=start+(k0+k)/500-event<hi for k in range(5000))
            c.need(n==count,'qualified floating grid bin membership')
    lo=max(0,k0);hi=min(samples,k0+5000)
    hi=max(lo,hi) if lo<=samples else lo
    lo=min(lo,samples);hi=min(hi,samples)
    return {'first_index':k0,'last_index':k0+4999,'source_read_start':lo,'source_read_stop':hi,
            'first_time':first,'last_time':last,'offset':offset,'event_time':event,'recording_start':start,
            'samples':samples,'status':'complete5000_positions'}

def context(day,event):
    c.need(c.integer(day,1) and c.finite(event) and 0<=event<86400,'qualified original day and time of day')
    theta=2*math.pi*event/86400
    return [float(day),math.sin(theta),math.cos(theta)]+[float(i==int(event//28800)) for i in range(3)]

def donor_order(person,day,path,n):
    c.need(type(person) is str and c.integer(day,1) and c.integer(n),'donor scope')
    c.relative(path)
    roster=[[path,'intervals/reaches',i] for i in range(n)]
    digest=hashlib.sha256(c.canonical(roster)).hexdigest()
    if n==0:return {'status':'empty','roster_sha256':digest,'offset':None,'donors':[]}
    if n==1:return {'status':'unsupported_singleton','roster_sha256':digest,'offset':None,'donors':[]}
    seed=c.canonical([c.D_LITERAL,person,day,digest]);offset=1+int.from_bytes(hashlib.sha256(seed).digest(),'big')%(n-1)
    return {'status':'complete','roster_sha256':digest,'offset':offset,'donors':[(i+offset)%n for i in range(n)]}
