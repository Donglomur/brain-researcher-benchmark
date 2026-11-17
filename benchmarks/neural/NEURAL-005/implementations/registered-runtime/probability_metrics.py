"""Transparent scalar probability metrics; no estimator or source-program execution."""
import math
ARMS=('history','prestimulus','all_erp','candidate')
EPS=1e-15

def metrics(y,p):
    n=len(y);q=[min(1-EPS,max(EPS,x))for x in p];pos=sum(y);neg=n-pos
    auc=None if not pos or not neg else math.fsum(1. if a>b else .5 if a==b else 0. for a,t in zip(p,y)if t for b,u in zip(p,y)if not u)/(pos*neg)
    observed=pos/n;mean=math.fsum(p)/n
    return {'log_loss':-math.fsum(math.log(a)if t else math.log1p(-a)for a,t in zip(q,y))/n,'brier':math.fsum((a-t)**2 for a,t in zip(p,y))/n,'auc':auc,'mean_probability':mean,'observed_frequency':observed,'calibration_mean_error':mean-observed}

def calculate(rows):
    people=[]
    for who in sorted({r['participant']for r in rows}):
        group=[r for r in rows if r['participant']==who];y=[r['target']for r in group]
        people.append({'participant':who,'n':len(group),'positive_n':sum(y),'arms':{a:metrics(y,[r['probabilities'][a]for r in group])for a in ARMS}})
    means={}
    for arm in ARMS:
        auc=[p['arms'][arm]['auc']for p in people if p['arms'][arm]['auc']is not None]
        means[arm]={k:math.fsum(p['arms'][arm][k]for p in people)/len(people)for k in('log_loss','brier','mean_probability','observed_frequency','calibration_mean_error')}
        means[arm].update(auc_mean_defined_only=math.fsum(auc)/len(auc)if auc else None,auc_defined_participant_n=len(auc),auc_undefined_participant_n=len(people)-len(auc))
    comparisons={}
    for left,right in [('history','candidate'),('prestimulus','candidate'),('all_erp','candidate'),('history','all_erp'),('history','prestimulus'),('prestimulus','all_erp')]:
        differences=[{'participant':p['participant'],**{m:p['arms'][left][m]-p['arms'][right][m]for m in('log_loss','brier')}}for p in people]
        comparisons[left+'_minus_'+right]={'left_arm':left,'right_arm':right,'direction':'positive means lower loss for right arm','per_participant':differences,'equal_participant_mean':{m:math.fsum(p[m]for p in differences)/len(people)for m in('log_loss','brier')}}
    return {'per_participant':people,'equal_participant_arms':means,'signed_comparisons':comparisons,'record_n':len(rows),'participant_n':len(people),'primary_unit':'participant','log_loss_clip_epsilon':EPS}
