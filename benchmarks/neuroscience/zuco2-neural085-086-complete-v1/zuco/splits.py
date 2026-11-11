"""Full source held-person/item split, repeat-aware pairing and opaque per-job views."""
import hashlib,hmac,copy
from collections import defaultdict,Counter
from .io import *
from .constants import *
from .panel import exact_text,text_id,group_id,fold,group_text

def token(key,*parts):return hmac.new(key,encode(list(parts)),hashlib.sha256).hexdigest()
def plan(panel,selected,key,programme_sha):
    need(type(key)is bytes and len(key)==32,"fresh_campaign_secret");jobs=[]
    for task,rep,mode in selected:
        need(task in ARMS and rep in REPRESENTATIONS and mode in MODES,"selected_condition")
        for person in PERSONS:
            for part in range(5):
                for context in (("sentence",) if task=="NEURAL-085" else CONTEXTS):
                    for arm in ARMS[task]:
                        i={"task":task,"person_token":token(key,"person",person),"item_fold":part,"context":context,"arm":arm,"representation":rep,"mode":mode,"seed":0,"programme_sha256":programme_sha,"source_sha256":panel["source_sha256"],"split_sha256":"0"*64,"information_set":INFORMATION_SET,"generation":token(key,"generation",programme_sha),"role":"participant","method":"candidate"}
                        jobs.append({"identity":i,"private_person":person,"source_disposition":"required_unscorable_secondary_context" if task=="NEURAL-086" and context!="FFD" and not panel.get("context_capabilities",{}).get(context,True) else "planned"})
    basis={"source":panel["source_sha256"],"J":panel["J"],"selected":selected,"coordinates":[{k:v for k,v in x["identity"].items() if k!="split_sha256"} for x in jobs]};sha=digest(basis)
    for j in jobs:j["identity"]["split_sha256"]=sha;j["id"]=digest(j["identity"])
    need(len({j["id"] for j in jobs})==len(jobs),"duplicate_selected_job");return {"source_sha256":panel["source_sha256"],"programme_sha256":programme_sha,"split_sha256":sha,"selected":selected,"jobs":jobs,"J":panel["J"],"all_jobs_frozen_before_views":True}
def paired(rows,J,context):
    by=defaultdict(lambda:defaultdict(list));dispositions=[]
    for r in rows:
        if text_id(r["text"]) not in J:continue
        for pos,w in enumerate(r["words"]):
            z=w["windows"][context];d=z["duration_ms"]
            if not finite(d) or d<=0:dispositions.append({"person":r["person"],"index":r["index"],"condition":r["condition"],"word_index":pos,"reason":"missing_or_nonpositive_window"});continue
            by[(r["person"],text_id(r["text"]),pos)][r["condition"]].append({"sentence":r,"word_index":pos,"word":w,"window":z})
    result=[]
    for k,b in by.items():
        if set(b)==set(CONDITIONS):
            for c in CONDITIONS:result.extend(b[c])
        else:dispositions.append({"cell":list(k),"reason":"unilateral_window","conditions":sorted(b)})
    return result,dispositions

def weights(rows,task):
    cells=defaultdict(lambda:defaultdict(lambda:defaultdict(Counter)))
    if task=="NEURAL-085":
        by=defaultdict(lambda:defaultdict(Counter))
        for z in rows:r=z["sentence"];by[r["person"]][r["condition"]][text_id(r["text"])]+=1
        need(all(set(x)==set(CONDITIONS) for x in by.values()),"training_class_support")
        out=[1/(len(by)*2*len(by[z["sentence"]["person"]][z["sentence"]["condition"]])*by[z["sentence"]["person"]][z["sentence"]["condition"]][text_id(z["sentence"]["text"])]) for z in rows]
    else:
        for z in rows:r=z["sentence"];cells[r["person"]][text_id(r["text"])][z["word_index"]][r["condition"]]+=1
        out=[]
        for z in rows:
            r=z["sentence"];a=cells[r["person"]];b=a[text_id(r["text"])];c=b[z["word_index"]];need(set(c)==set(CONDITIONS),"paired_training_classes");out.append(1/(len(cells)*len(a)*len(b)*2*c[r["condition"]]))
    need(out,"nonempty_training");s=sum(out);return [w*len(out)/s for w in out]

def partition(panel,job,key):
    i=job["identity"];person=job["private_person"];part=i["item_fold"]
    if i["task"]=="NEURAL-085":rows=[{"sentence":r,"word_index":None} for r in panel["rows"]];dispositions=[]
    else:rows,dispositions=paired(panel["rows"],panel["J"],i["context"])
    train=[z for z in rows if z["sentence"]["person"]!=person and fold(z["sentence"]["text"])!=part];query=[z for z in rows if z["sentence"]["person"]==person and fold(z["sentence"]["text"])==part]
    need({z["sentence"]["person"] for z in train}==set(PERSONS)-{person},"all17_training_people")
    need(not {group_id(z["sentence"]["text"]) for z in train}&{group_id(z["sentence"]["text"]) for z in query},"held_item_leakage")
    def rid(z):r=z["sentence"];return token(key,job["id"],r["person"],r["condition"],r["index"],z["word_index"])
    train.sort(key=rid);query.sort(key=rid)
    return {"train":train,"query":query,"train_ids":[rid(z) for z in train],"query_ids":[rid(z) for z in query],"weights":weights(train,i["task"]),"dispositions":dispositions}
def inner_groups(train):
    people=sorted({z["sentence"]["person"] for z in train},key=lambda s:hashlib.sha256(s.encode()).hexdigest());person_groups={s:k%3 for k,s in enumerate(people)}
    return [(a,b,[k for k,z in enumerate(train) if person_groups[z["sentence"]["person"]]!=a and fold(z["sentence"]["text"],3)!=b],[k for k,z in enumerate(train) if person_groups[z["sentence"]["person"]]==a and fold(z["sentence"]["text"],3)==b]) for a in range(3) for b in range(3)]
