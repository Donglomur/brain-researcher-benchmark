"""Exact prospective scientific metrics. BUILD ONLY tests must not execute this module's math."""
import math,random,statistics
from collections import defaultdict
from .io import need,finite
EPS=1e-6

def loss(y,p):
    need(type(y)is int and y in (0,1) and finite(p) and 0<=p<=1,"loss_arguments");q=min(1-EPS,max(EPS,p));return -math.log(q if y else 1-q)
def average(xs):return sum(xs)/len(xs) if xs else None
def percentile(v,q):
    a=sorted(v);t=(len(a)-1)*q;k=int(t);return a[k]+(a[min(k+1,len(a)-1)]-a[k])*(t-k)
def crossed(matrix,people,items):
    need(set(matrix)=={(s,j) for s in people for j in items} and len(people)==18 and items,"complete_uncertainty_rectangle")
    pm={s:average([matrix[s,j] for j in items]) for s in people};im={j:average([matrix[s,j] for s in people]) for j in items};rng=random.Random(194086);draws=[]
    for _ in range(1000):
        ss=[rng.randrange(18) for _ in range(18)];jj=[rng.randrange(len(items)) for _ in items];draws.append(average([matrix[people[s],items[j]] for s in ss for j in jj]))
    return {"mean":average(list(pm.values())),"person_means":pm,"item_means":im,"descriptive_person_SE":statistics.stdev(pm.values())/math.sqrt(18),"descriptive_item_SE":statistics.stdev(im.values())/math.sqrt(len(items)) if len(items)>1 else None,"descriptive_crossed_resampling_interval95":[percentile(draws,.025),percentile(draws,.975)],"seed":194086,"resamples":1000,"model_refit":False,"population_coverage_claim":False}
def n085(rows,people,J):
    need(len(people)==18,"biological_people");result={};matrices={}
    for stratum in ("matched","full","exclusive"):
        chosen=[r for r in rows if stratum=="full" or (r["item"]in J)==(stratum=="matched")];bucket=defaultdict(list)
        for r in chosen:bucket[r["person"],r["item"],r["label"]].append(r)
        cells={k:{"loss":average([loss(r["label"],r["p"]) for r in rs]),"correct":average([int((r["p"]>=.5)==bool(r["label"])) for r in rs]),"brier":average([(r["p"]-r["label"])**2 for r in rs]),"occurrences":len(rs),"mean_probability":average([r["p"] for r in rs])} for k,rs in bucket.items()};person={};missing=[]
        for s in people:
            classes={y:[v for (ss,j,yy),v in cells.items() if ss==s and yy==y] for y in (0,1)}
            if not all(classes.values()):missing.append({"person":s,"reason":"missing_class"});continue
            if stratum=="matched" and any({j for ss,j,yy in cells if ss==s and yy==y}!=set(J) for y in (0,1)):missing.append({"person":s,"reason":"missing_matched_item"});continue
            person[s]={k:average([average([v[k] for v in classes[y]]) for y in (0,1)]) for k in ("loss","correct","brier")}
        paired={}
        for s,j in {(s,j) for s,j,y in cells}:
            if (s,j,0) in cells and (s,j,1) in cells:paired[s,j]={k:(cells[s,j,0][k]+cells[s,j,1][k])/2 for k in ('loss','correct','brier')};paired[s,j]['occurrences']=sum(cells[s,j,y]['occurrences'] for y in (0,1))
        calibration=[]
        for label in (0,1):
            selected=[r for r in chosen if r['label']==label];bins=[]
            for b in range(10):
                v=[r for r in selected if min(9,int(r['p']*10))==b];bins.append({'bin':b,'count':len(v),'mean_predicted_probability':average([r['p'] for r in v]),'observed_fraction':label if v else None})
            calibration.append({'class':label,'presentation_count':len(selected),'presentation_weighted_Brier':average([(r['p']-label)**2 for r in selected]),'fixed_probability_bins':bins})
        result[stratum]={"log_loss":None if missing else average([v["loss"] for v in person.values()]),"balanced_accuracy":None if missing else average([v["correct"] for v in person.values()]),"brier":None if missing else average([v["brier"] for v in person.values()]),"people":person,"support_missing":missing,"presentation_count":len(chosen),"condition_prevalence":average([r["label"] for r in chosen]),"class_calibration":calibration,"class_averaged_person_item_cells":[{"person":s,"item":j,**v} for (s,j),v in sorted(paired.items())],"cells":[{"person":s,"item":j,"label":y,**v} for (s,j,y),v in sorted(cells.items())]}
    return result

def word_cells(rows):
    bucket=defaultdict(list)
    for r in rows:bucket[r["person"],r["item"],r["word_index"],r["label"]].append(r)
    words=defaultdict(dict)
    for (s,j,w,y),rs in bucket.items():words[s,j,w][y]={"loss":average([loss(y,r["p"]) for r in rs]),"correct":average([int((r["p"]>=.5)==bool(y)) for r in rs]),"occurrences":len(rs)}
    cells=defaultdict(list)
    for (s,j,w),by in words.items():need(set(by)=={0,1},"paired_word_classes");cells[s,j].append({"word":w,"loss":(by[0]["loss"]+by[1]["loss"])/2,"accuracy":(by[0]["correct"]+by[1]["correct"])/2,"class_occurrences":{str(y):by[y]["occurrences"] for y in (0,1)}})
    return {k:{"loss":average([v["loss"] for v in vv]),"accuracy":average([v["accuracy"] for v in vv]),"paired_words":len(vv),"word_details":vv} for k,vv in cells.items()}
def paired_contrast(base,plus,people,J):
    a=word_cells(base);b=word_cells(plus);need(set(a)==set(b),"paired_comparison_support");expected={(s,j) for s in people for j in J};missing=sorted(expected-set(a));need(set(a)<=expected,"extra_comparison_cell")
    matrix={k:a[k]["loss"]-b[k]["loss"] for k in a}
    return {"base_loss":None if missing else average([a[k]["loss"] for k in expected]),"plus_loss":None if missing else average([b[k]["loss"] for k in expected]),"base_balanced_accuracy":None if missing else average([a[k]["accuracy"] for k in expected]),"plus_balanced_accuracy":None if missing else average([b[k]["accuracy"] for k in expected]),"signed_difference":None if missing else average(list(matrix.values())),"complete_support":not missing,"missing_cells":[list(k) for k in missing],"expected_person_item_cells":len(expected),"supported_person_item_cells":len(a),"paired_cell_matrix":[{"person":s,"item":j,"base_loss":a[s,j]["loss"],"plus_loss":b[s,j]["loss"],"difference":matrix[s,j],"paired_words":a[s,j]["paired_words"]} for s,j in sorted(a)],"uncertainty":None if missing else crossed(matrix,people,J),"interpretation":"finite observed-panel procedure contrast; not conditional information, neural origin or causal demand"}
def metric_equal(a,b):
    if a is None or b is None:return a is b
    if isinstance(a,dict):return type(b)is dict and set(a)==set(b) and all(metric_equal(v,b[k]) for k,v in a.items())
    if isinstance(a,list):return type(b)is list and len(a)==len(b) and all(metric_equal(x,y) for x,y in zip(a,b))
    if type(a)is float:return finite(b) and abs(a-b)<=1e-10+1e-8*abs(a)
    return type(a)is type(b) and a==b

def n085_contrast(base,plus,people,J):
    a={(v['person'],v['item']):v for v in base['matched']['class_averaged_person_item_cells']};b={(v['person'],v['item']):v for v in plus['matched']['class_averaged_person_item_cells']};need(set(a)==set(b),'N085_paired_contrast_support');expected={(s,j) for s in people for j in J};missing=expected-set(a);matrix={k:a[k]['loss']-b[k]['loss'] for k in a}
    return {'signed_difference':None if missing else average(list(matrix.values())),'paired_cell_matrix':[{'person':s,'item':j,'base_loss':a[s,j]['loss'],'plus_loss':b[s,j]['loss'],'difference':d} for (s,j),d in sorted(matrix.items())],'missing_cells':[list(k) for k in sorted(missing)],'uncertainty':None if missing else crossed(matrix,people,J)}
