"""Exact protected metric mathematics. Not imported or run by build controls."""
from .io import need
from .contract import ARMS, RELEVANCES, DURATIONS, ORIENTATIONS, METRICS

def evaluate(targets,predictions):
    import math
    need(type(targets)is dict and targets,"Complete private target map")
    need(set(predictions)==set(ARMS),"All five prediction arms")
    expected=set(targets)
    need(all(type(v)in(int,float)and math.isfinite(v)and 0<=v<=1 for a in ARMS for v in predictions[a].values()),"Finite nonboolean probability in every candidate/reference arm")
    need(all(set(predictions[a])==expected for a in ARMS),"Same complete cases in every arm")
    need({r["person_index"]for r in targets.values()}==set(range(33)),"All33 independent-person indices")
    for row in targets.values():
        need(type(row["y"])is int and row["y"]in(0,1),"Face-positive target")
        need(row["stratum"][0]in RELEVANCES and row["stratum"][1]in DURATIONS and row["stratum"][2]in ORIENTATIONS,"Exact private stratum")
    people=[]
    def mean(values):
        return math.fsum(values)/len(values)if values and all(v is not None for v in values)else None
    for p in range(33):
        person={"person_index":p,"arms":{}}
        for arm in ARMS:
            per_rel={}
            for rel in RELEVANCES:
                cells=[]
                for duration in DURATIONS:
                    for orientation in ORIENTATIONS:
                        ids=[k for k,r in targets.items()if r["person_index"]==p and r["stratum"]==[rel,duration,orientation]]
                        groups=[[k for k in ids if targets[k]["y"]==y]for y in (0,1)]
                        recalls=[];balanced_losses=[];briers=[]
                        for y,group in enumerate(groups):
                            recalls.append(mean([float((predictions[arm][k]>=.5)==bool(y))for k in group]))
                            balanced_losses.append(mean([-math.log(max(1e-15,predictions[arm][k]if y else 1-predictions[arm][k]))for k in group]))
                            briers.append(mean([(predictions[arm][k]-y)**2 for k in group]))
                        ll=mean([-math.log(max(1e-15,predictions[arm][k]if targets[k]["y"]else 1-predictions[arm][k]))for k in ids])
                        cells.append({"duration":duration,"orientation":orientation,"n":len(ids),"class_counts":[len(x)for x in groups],
                          "balanced_accuracy":mean(recalls),"legacy_logloss":ll,"balanced_logloss":mean(balanced_losses),"balanced_brier":mean(briers),
                          "unavailable_reasons":[]if all(groups)else["missing_class_support"]})
                per_rel[rel]={"cells":cells,**{m:mean([x[m]for x in cells])for m in METRICS}}
            person["arms"][arm]=per_rel
        people.append(person)
    macro={a:{r:{m:mean([p["arms"][a][r][m]for p in people])for m in METRICS}for r in RELEVANCES}for a in ARMS}
    return {"persons":people,"macro":macro,"primary_value":macro["SIGNAL"]["Irrelevant"]["balanced_accuracy"],
            "expected_report_cells_per_arm":594,"expected_class_counts_per_arm":1188,
            "full_support_complete":all(c["class_counts"][0]>0 and c["class_counts"][1]>0 for p in people for a in ARMS for r in RELEVANCES for c in p["arms"][a][r]["cells"]),
            "population_or_theory_verdict":False,"scientific_qualification":False}
