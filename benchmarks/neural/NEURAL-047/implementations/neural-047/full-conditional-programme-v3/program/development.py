"""Whole-animal inner splits, never assessment targets or the held-out animal."""
import math
from .common import exact,need
from .legacy.features import summaries
LOGISTIC_C=(0.01,0.1,1.0,10.0,100.0)
BOOST_GRID=tuple({"max_leaf_nodes":leaf,"l2_regularization":penalty,"max_iter":200,"learning_rate":0.05}
                 for leaf in (7,15) for penalty in (0.0,1.0))
def validate(packet):
    exact(packet,["schema","packet_id","fold_id","arm","test_group","training","query"])
    need(packet["schema"]=="neural047-fold-v1" and packet["arm"] in ("N","B","NB"),"Exact source case")
    train=packet["training"];query=packet["query"];need(type(train) is list and type(query) is list and 2<=len(train)<=50000 and 1<=len(query)<=50000,"Full bounded events")
    seen=set();groups=set()
    for row in train:
        exact(row,["case_key","group","features","dorsal"])
        need(type(row["case_key"]) is str and row["case_key"] not in seen,"Unique train case");seen.add(row["case_key"])
        need(type(row["group"]) is str and row["group"]!=packet["test_group"],"Assessment animal absent from training")
        need(type(row["dorsal"]) is int and row["dorsal"] in (0,1),"Binary training labels")
        groups.add(row["group"]);summaries(row["features"],packet["arm"])
    need(len(groups)>=2 and {r["dorsal"] for r in train}=={0,1},"Two training animals and both directions")
    for row in query:
        exact(row,["case_key","features"]);need(type(row["case_key"]) is str and row["case_key"] not in seen,"No duplicate/query overlap");seen.add(row["case_key"])
        summaries(row["features"],packet["arm"])
    return sorted(groups)
def weights(groups,labels):
    need(len(groups)==len(labels)>0 and all(type(y) is int and y in (0,1) for y in labels),"Aligned binary training rows")
    units=sorted(set(groups));counts={(g,y):sum(h==g and z==y for h,z in zip(groups,labels)) for g in units for y in (0,1)}
    return [len(groups)/(len(units)*sum(counts[(g,z)]>0 for z in (0,1))*counts[(g,y)]) for g,y in zip(groups,labels)]
def inner_contexts(packet):
    groups=validate(packet);result=[]
    for held in groups:
        train=[r for r in packet["training"] if r["group"]!=held]
        val=[r for r in packet["training"] if r["group"]==held]
        need(train and val and {r["dorsal"] for r in train}=={0,1},"Inner training animal support insufficient; no event-level fallback")
        result.append({"held_group":held,"training":train,"validation":val})
    return result
def macro_loss(rows,probs):
    need(len(rows)==len(probs)>0,"Complete inner validation")
    units=sorted({r["group"] for r in rows});loss=[]
    for group in units:
        vs=[]
        for r,p in zip(rows,probs):
            need(type(p) in (int,float) and math.isfinite(p) and 0<=p<=1,"Finite inner probability")
            if r["group"]==group:vs.append(-math.log(max(1e-15,p if r["dorsal"] else 1-p)))
        loss.append(math.fsum(vs)/len(vs))
    return math.fsum(loss)/len(loss)

