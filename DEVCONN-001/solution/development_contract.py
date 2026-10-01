"""Child-only movie-data association, motion sensitivity and participant-bootstrap CI."""
import numpy as np
from scipy import stats

VERSION="devconn-child-motion-id-v2"
def partial_spearman(y,x,cov):
    def resid(a,b):
        design=np.c_[np.ones(len(b)),stats.rankdata(b)]
        ranked=stats.rankdata(a)
        return ranked-design@np.linalg.lstsq(design,ranked,rcond=None)[0]
    r=float(np.corrcoef(resid(x,cov),resid(y,cov))[0,1])
    df=len(y)-3
    p=float(2*stats.t.sf(abs(r*np.sqrt(df/max(1e-12,1-r*r))),df))
    return r,p

def estimate(age,values,fd):
    r,p=stats.spearmanr(age,values)
    ar,ap=partial_spearman(values,age,fd)
    rng=np.random.default_rng(11)
    boot=[];adjusted=[]
    for _ in range(1000):
        index=rng.integers(0,len(age),len(age))
        boot.append(stats.spearmanr(age[index],values[index]).statistic)
        adjusted.append(partial_spearman(values[index],age[index],fd[index])[0])
    return {"r":float(r),"p":float(p),"ci95":np.quantile(boot,[.025,.975]).tolist(),
            "motion_adjusted_r":ar,"motion_adjusted_p":ap,
            "motion_adjusted_ci95":np.quantile(adjusted,[.025,.975]).tolist(),"n":len(age)}

def validate_report(data,report):
    child=data[data.group=="child"]
    adult=data[data.group=="adult"]
    assert len(child)==122 and len(adult)==33
    assert report["population"]=="children_only" and report["n_children"]==122 and report["n_adults"]==33
    for col in ("short_range","long_range","segregation"):
        expected=estimate(child.age.to_numpy(),child[col].to_numpy(),child.mean_fd.to_numpy())
        actual=report["children_age_spearman"][col]
        for key,value in expected.items():
            assert np.allclose(actual[key],value,atol=1e-6,rtol=1e-5), f"wrong {col}/{key}"
        for group,subset in (("child",child),("adult",adult)):
            assert np.isclose(report["group_means"][col][group],subset[col].mean(),atol=1e-6)
    restriction=report["motion_control"]["segregation_low_motion_restriction"]
    eligible=data[data.mean_fd<.2]
    lowchild=eligible[eligible.group=="child"];lowadult=eligible[eligible.group=="adult"]
    t,p=stats.ttest_ind(lowchild.segregation,lowadult.segregation,equal_var=False)
    assert restriction["n_child"]==len(lowchild) and restriction["n_adult"]==len(lowadult)
    assert np.isclose(restriction["t"],t,atol=1e-6) and np.isclose(restriction["p"],p,atol=1e-6)
