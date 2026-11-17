"""Pure metrics on declared probabilities; never fits or imports author code."""
import argparse,functools,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from contract import *

THRESHOLDS=(1,2,3,5,10)
COVERAGES=(0.25,0.5,0.75,1.0)
def mean_prob(rows):return [[math.fsum(r['probabilities'][j][c]/10 for j in range(10)) for c in range(5)] for r in rows]
def pred(p):return max(range(5),key=lambda i:p[i])
def top(p):a=sorted(p,reverse=True);return a[0],a[1]
def ratio_at_least(p,t):a,b=top(p);return a>=t*b

def summary(probs,labels,selected):
    n=len(labels);cm=[[0]*5 for _ in CLASSES];excluded=[0]*5
    for p,y,keep in zip(probs,labels,selected):
        k=CLASSES.index(y)
        if keep:cm[k][pred(p)]+=1
        else:excluded[k]+=1
    count=sum(map(sum,cm));support=[sum(cm[i])+excluded[i] for i in range(5)]
    correct=sum(cm[i][i] for i in range(5));recall=[cm[i][i]/sum(cm[i]) if sum(cm[i]) else None for i in range(5)]
    f1=[]
    for i in range(5):
        den=sum(cm[i])+sum(row[i] for row in cm)
        f1.append(2*cm[i][i]/den if den else None)
    return dict(total=n,retained=count,coverage=count/n if n else None,accuracy=correct/count if count else None,
                confusion_counts=cm,unclassified_counts=excluded,class_support=support,
                confusion_row_conditional=[[v/sum(row) for v in row] if sum(row) else [None]*5 for row in cm],
                unclassified_fraction=[excluded[i]/support[i] if support[i] else None for i in range(5)],
                class_recall=recall,macro_recall=math.fsum(recall)/5 if all(v is not None for v in recall) else None,
                class_f1=f1,macro_f1=math.fsum(f1)/5 if all(v is not None for v in f1) else None,
                observed_union_macro_f1=math.fsum(v for v in f1 if v is not None)/sum(v is not None for v in f1) if any(v is not None for v in f1) else None)

def ratio_cmp(a,b):
    # Exact rational comparison of finite binary-float probabilities; handles second=0.
    from fractions import Fraction
    aa,ab=map(Fraction,top(a));ba,bb=map(Fraction,top(b));v=aa*bb-ba*ab
    return (v>0)-(v<0)
def coverage_weights(probs,coverage):
    # Include whole higher-ratio groups; boundary ties share weight. No ID/label tiebreak.
    need(0<coverage<=1,'coverage');order=sorted(range(len(probs)),key=functools.cmp_to_key(lambda i,j:-ratio_cmp(probs[i],probs[j])))
    weights=[0.0]*len(probs);remaining=coverage*len(probs);pos=0
    while pos<len(order) and remaining>0:
        end=pos+1
        while end<len(order) and ratio_cmp(probs[order[pos]],probs[order[end]])==0:end+=1
        w=min(1.0,remaining/(end-pos))
        for k in order[pos:end]:weights[k]=w
        remaining-=w*(end-pos);pos=end
    return weights

def weighted_accuracy(probs,labels,cov):
    w=coverage_weights(probs,cov);den=math.fsum(w)
    return dict(requested_coverage=cov,retained_weight=den,accuracy=math.fsum(x for p,y,x in zip(probs,labels,w) if CLASSES[pred(p)]==y)/den if den else None,tie_policy='fractional boundary group; diagnostic expected accuracy, not a realized subset')
def metrics(probs,labels,groups):
    ratios={str(t):summary(probs,labels,[ratio_at_least(p,t) for p in probs]) for t in THRESHOLDS}
    brier=math.fsum(math.fsum((v-(CLASSES[c]==y))**2/len(labels) for c,v in enumerate(p)) for p,y in zip(probs,labels))
    group_accuracy={}
    for field in ('animal','session','lab'):
        keys=sorted(set(g[field] for g in groups));v=[]
        for k in keys:
            ix=[i for i,g in enumerate(groups) if g[field]==k];v.append({'group':k,'n':len(ix),'accuracy':sum(CLASSES[pred(probs[i])]==labels[i] for i in ix)/len(ix)})
        group_accuracy[field]={'groups':v,'macro_accuracy':math.fsum(x['accuracy']/len(v) for x in v)}
    return dict(all_units=ratios['1'],ratio_thresholds=ratios,mean_probability_threshold_diagnostics={str(t):summary(probs,labels,[max(p)>t for p in probs]) for t in (0.0,0.5,0.6,0.7,0.8,0.9)},matched_coverage=[weighted_accuracy(probs,labels,c) for c in COVERAGES],brier=brier,group_descriptive=group_accuracy)
def grade(s,q,t):
    submission(s,q);target(t,q);out={}
    for m in METHODS:
        out[m]={d:metrics(mean_prob(s['predictions'][m][d]),t['labels'][d],t['groups'][d]) for d in DOMAINS}
        for d in DOMAINS:
            rows=s['predictions'][m][d];ys=t['labels'][d]
            per=[summary([r['probabilities'][j] for r in rows],ys,[True]*len(ys)) for j in range(10)]
            f=[r['observed_union_macro_f1'] for r in per];mu=math.fsum(v/10 for v in f)
            out[m][d]['per_instantiation']={'accuracy':[r['accuracy'] for r in per],'observed_union_macro_f1':f,'macro_f1_mean':mu,'macro_f1_population_std':math.sqrt(math.fsum((v-mu)**2/10 for v in f))}
            # Baseline plots pool repeats; deep plot_confusion_matrices averages CV repeats first.
            if m in METHODS[:3]:
                pp=[r['probabilities'][j] for j in range(10) for r in rows];yy=ys*10
            else:pp=mean_prob(rows);yy=ys
            grid=(0,.5,.6,.7,.8,.9) if m in METHODS[:3] else (0,.4,.5,.6,.7,.8,.9)
            out[m][d]['source_plot_probability_thresholds']={str(th):summary(pp,yy,[max(p)>th for p in pp]) for th in grid}
            out[m][d]['plot_policy_basis']='pinned_baseline_pooled_repeats' if m in METHODS[:3] else 'pinned_deep_mean' if m=='deep' else 'prospective_improved_mean'
    paired={}
    for d in DOMAINS:
        paired[d]={}
        for base in METHODS[:-1]:
            paired[d][base]={'accuracy_delta':out['improved'][d]['all_units']['accuracy']-out[base][d]['all_units']['accuracy'],
                'brier_delta':out['improved'][d]['brier']-out[base][d]['brier'],
                'matched_coverage_accuracy_delta':[a['accuracy']-b['accuracy'] for a,b in zip(out['improved'][d]['matched_coverage'],out[base][d]['matched_coverage'])]}
    return dict(schema='c4_metrics_v1',task_id=TASK,query_sha256=digest(q),metrics=out,prospective_improvement=paired,binary_reward=None,limitations=['Prediction artifacts do not prove training, fold isolation, exposure, architecture or compute equality.','Mouse ground truth and monkey expert agreement are separate endpoints.','Animal/session/lab aggregation is descriptive; unit LOO is not held-animal validation.'])
def main():
    a=argparse.ArgumentParser();a.add_argument('--query',required=True);a.add_argument('--submission',required=True);a.add_argument('--target',required=True);a.add_argument('--output',required=True);z=a.parse_args();fresh(z.output)
    q=query(load(z.query));s=submission(load(z.submission),q) # Before private target is opened.
    save(z.output,grade(s,q,load(z.target)))
if __name__=='__main__':main()
