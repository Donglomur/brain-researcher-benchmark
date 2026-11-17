"""Signed, complete-support metrics and listener-first descriptive contrasts."""
import math
from .errors import need

def required_mean(values):
    if not values or any(v is None for v in values):return None
    need(all(math.isfinite(v) for v in values),"metric-arithmetic")
    scale=max(abs(v) for v in values)
    return 0. if scale==0 else math.fsum(v/scale for v in values)/len(values)*scale

def part(pred,target,training_mean):
    import numpy as np
    from .scientific import mean
    a=np.asarray(pred,dtype=np.float64);b=np.asarray(target,dtype=np.float64)
    mu=np.asarray(training_mean,dtype=np.float64)
    need(a.shape==b.shape and b.ndim==2 and b.shape[1]==400 and len(b)>=20 and mu.shape==(400,),
         "metric-common-support")
    need(np.isfinite(a).all() and np.isfinite(b).all() and np.isfinite(mu).all(),"metric-finite-inputs")
    x=a-mean(a,np.ones(len(a)));y=b-mean(b,np.ones(len(b)))
    sx=(x*x).sum(axis=0);sy=(y*y).sum(axis=0)
    mse=((a-b)**2).mean(axis=0);den=((b-mu)**2).mean(axis=0)
    cor=[];q2=[]
    for k in range(400):
        cor.append(None if sy[k]==0 else (0. if sx[k]==0 else
                   max(-1.,min(1.,float((x[:,k]*y[:,k]).sum()/math.sqrt(sx[k]*sy[k]))))))
        q2.append(None if den[k]==0 else float(1-mse[k]/den[k]))
    need(all(v is None or math.isfinite(v) for v in cor+q2+list(mse)),"finite-metric-result")
    return {"signed_r":required_mean(cor),"Q2":required_mean(q2),"MSE":required_mean(list(mse)),
            "parcel_signed_r":cor,"parcel_Q2":q2,"parcel_MSE":mse.tolist(),
            "undefined_r":sum(v is None for v in cor),"undefined_Q2":sum(v is None for v in q2)}

def case_score(predictions,targets,training_mean,rows):
    need(len(rows)==len(targets),"case-metric-rows")
    groups=sorted({(r["run"],r["segment"]) for r in rows})
    output={}
    for condition,pred in predictions.items():
        need(len(pred)==len(rows),"metric-prediction-completeness")
        parts={}
        for run,segment in groups:
            ids=[i for i,r in enumerate(rows) if (r["run"],r["segment"])==(run,segment)]
            parts[(run,segment)]=part([pred[i] for i in ids],[targets[i] for i in ids],training_mean)
        runs=sorted({r for r,_ in groups})
        values={metric:required_mean([required_mean([parts[(r,s)][metric] for rr,s in groups if rr==r])
                                     for r in runs]) for metric in ("signed_r","Q2","MSE")}
        output[condition]={"values":values,"parts":[{"run":r,"segment":s,**v} for (r,s),v in parts.items()]}
    return output

def aggregate(cases,contrasts):
    need(len(cases)==486 and len({c["person"] for c in cases})==171,"full-scored-estimand")
    conditions=set(cases[0]["scores"])
    need(all(c[side] in conditions for c in contrasts for side in ("left","right")),
         "contrast-condition-join")
    need(len(conditions)==21 and all(set(c["scores"])==conditions for c in cases),"all21-conditions")
    people=sorted({c["person"] for c in cases})
    person={p:{condition:{m:required_mean([c["scores"][condition]["values"][m] for c in cases
                                        if c["person"]==p])
                         for m in ("signed_r","Q2","MSE")} for condition in sorted(conditions)}
            for p in people}
    means={c:{m:required_mean([person[p][c][m] for p in people])
              for m in ("signed_r","Q2","MSE")} for c in sorted(conditions)}
    differences=[]
    need(len(contrasts)==57,"all57-contrasts")
    for c in contrasts:
        for metric in c["metrics"]:
            values=[None if person[p][c["left"]][metric] is None or person[p][c["right"]][metric] is None
                    else person[p][c["left"]][metric]-person[p][c["right"]][metric] for p in people]
            differences.append({"contrast":c["id"],"metric":metric,"value":required_mean(values),
                                "listener_values":dict(zip(people,values)),"n_required":171,
                                "n_defined":sum(v is not None for v in values),
                                "design_evidence":c["design_evidence"]})
    families={f:{condition:{m:required_mean([c["scores"][condition]["values"][m] for c in cases
                                          if c["family"]==f])
                           for m in ("signed_r","Q2","MSE")} for condition in sorted(conditions)}
              for f in sorted({c["family"] for c in cases})}
    return {"conditions":means,"listeners":person,"story_family_descriptive_marginals":families,
            "contrasts":differences,"primary_F":means["F/CONTEXT/REAL_RESPONSE"]["signed_r"],
            "primary_I":means["I/CONTEXT/REAL_RESPONSE"]["signed_r"],
            "required_listeners":171,"ineligible_single_family":174,
            "inference":"descriptive dependent unbalanced marginals; no IID test or causal interpretation"}
