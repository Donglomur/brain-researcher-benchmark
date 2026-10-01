"""Fisher-z network aggregation and child-only nuisance sensitivity."""
import numpy as np
from scipy.stats import rankdata,t

VERSION="socialbrain-fisher-id-v2"
def fisher_mean(values):
    values=np.asarray(values,float)
    assert np.isfinite(values).all()
    return float(np.tanh(np.arctanh(np.clip(values,-.999999,.999999)).mean()))

def partial_rank_corr(age,values,motion):
    a=rankdata(age);y=rankdata(values);m=rankdata(motion)
    design=np.column_stack([np.ones(len(a)),m])
    ra=a-design@np.linalg.lstsq(design,a,rcond=None)[0]
    ry=y-design@np.linalg.lstsq(design,y,rcond=None)[0]
    r=float(np.corrcoef(ra,ry)[0,1]);df=len(a)-3
    p=float(2*t.sf(abs(r*np.sqrt(df/(1-r*r))),df))
    return r,p
