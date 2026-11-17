"""Private physical-person/image splits and neutral episode projections."""
import hashlib
import secrets
from .io import need, canonical, identity
from .contract import ROSTER, ARMS, require_deployment

def opaque():
    return secrets.token_hex(24)

def ordered(groups,seed):
    return sorted(groups,key=lambda x:hashlib.sha256(str(seed).encode()+b"\0"+x.encode()).digest())

def inner_groups(train):
    people=ordered({r["person"]for r in train},97097)
    pgroup={p:k%4 for k,p in enumerate(people)}
    images={}
    for y in (0,1):
        selected=ordered({r["image"]for r in train if r["y"]==y},97097)
        need(len(selected)>=2,"Both inner image groups support each training class")
        for k,image in enumerate(selected):
            need(image not in images,"Image identity cannot change category");images[image]=k%2
    folds=[]
    for p in range(4):
        for h in (0,1):
            tr=[i for i,r in enumerate(train)if pgroup[r["person"]]!=p and images[r["image"]]!=h]
            va=[i for i,r in enumerate(train)if pgroup[r["person"]]==p and images[r["image"]]==h]
            need(tr and va,"Full eight crossed inner folds")
            folds.append({"person_group":p,"image_group":h,"train":tr,"validation":va})
    return folds

def outer_plan(observations):
    require_deployment()
    rows=observations["rows"];out=[]
    for p,person in enumerate(ROSTER):
        for half in (0,1):
            train=[r for r in rows if r["person"]!=person and r["half"]!=half]
            query=[r for r in rows if r["person"]==person and r["half"]==half]
            need(train and query and {r["y"]for r in train}=={0,1},"Complete fold training/query support")
            need({r["image"]for r in train}.isdisjoint({r["image"]for r in query}),"Physical-image separation")
            out.append({"person_index":p,"person":person,"half":half,"train":train,"query":query,
                        "inner":inner_groups(train),"source_panel":identity(canonical(observations))})
    return out

def episode_view(fold,arm,access,mode,seed,binding):
    """Private joins stay with controller. Candidate sidecars are episode-local."""
    require_deployment();need(arm in ARMS,"Feature arm")
    groups={name:{}for name in ("person","image","session","run")}
    train=[]
    for row in fold["train"]:
        out={"opaque_case":opaque(),"yface":row["y"],"x":row["views"][arm],
             "validation_stratum":row["stratum"]}
        for name in groups:
            key=row[name] if name in ("person","image")else (row["person"],row[name])
            out["opaque_"+name+"_group"]=groups[name].setdefault(key,opaque())
        train.append(out)
    # Random order derives only from fresh trusted randomness, never labels.
    order=list(range(len(fold["query"])));secrets.SystemRandom().shuffle(order)
    query=[];private={}
    for i in order:
        row=fold["query"][i];nonce=opaque()
        query.append({"opaque_query_nonce":nonce,"x_numeric_vector":row["views"][arm]})
        private[nonce]={"private_id":row["private_id"],"y":row["y"],"stratum":row["stratum"]}
    return {"schema":"n097-episode-v1","contract":binding,"opaque_episode_nonce":opaque(),
            "access":access,"mode":mode,"seed":seed,"feature_arm":arm,
            "train":train,"inner_validation":fold["inner"],"query":query},private

def public_train_view(episode):
    return {k:episode[k]for k in ("schema","contract","opaque_episode_nonce","access","mode","seed","feature_arm","train","inner_validation")}

def public_query_view(episode,query):
    need(query in episode["query"],"Selected one-query capability")
    return {"schema":"n097-query-v2","opaque_episode_nonce":episode["opaque_episode_nonce"],
            "opaque_query_nonce":query["opaque_query_nonce"],"x_numeric_vector":query["x_numeric_vector"]}
