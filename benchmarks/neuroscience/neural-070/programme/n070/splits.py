"""Group closure precedes deterministic partitioning; no authentic groups fabricated."""
import hashlib
from .core import need, exact, digest
from .protocol import VIDEOS
def verify_groups(binding):
    exact(binding,("videos","groups","source_identity","review_identity","closure_status","shared_EEGMoments","pretraining_exposure"))
    need(binding["closure_status"]=="independently_complete" and binding["source_identity"] and binding["review_identity"],
         "Original source-video equivalence and duplicate closure required")
    need(set(binding["videos"])==set(VIDEOS) and len(binding["videos"])==1102,"All 1102 video identities")
    need(set(binding["groups"])==set(VIDEOS) and all(type(v)is str and v for v in binding["groups"].values()),"Every video has actual group")
    need(binding["shared_EEGMoments"]=="resolved" and binding["pretraining_exposure"]=="resolved","Cross-dataset/model exposure closure")
    return binding["groups"]
def assign(groups,salt,folds=5):
    need(type(salt)is str and len(salt)>=16,"Operator-committed partition salt")
    unique=set(groups.values());need(len(unique)>=folds,"Enough independently established groups")
    order=sorted(unique,key=lambda g:(hashlib.sha256((salt+"\0"+g).encode()).hexdigest(),g))
    sizes={g:sum(v==g for v in groups.values())for g in unique}
    loads=[0]*folds;allocation={}
    for g in order:
        f=min(range(folds),key=lambda i:(loads[i],i));allocation[g]=f;loads[f]+=sizes[g]
    return {v:allocation[g]for v,g in groups.items()}
def build(binding,salt):
    groups=verify_groups(binding);outer=assign(groups,salt);inner={}
    for f in range(5):
        training={v:g for v,g in groups.items()if outer[v]!=f}
        inner[str(f)]=assign(training,salt+":inner:"+str(f))
    result={"groups_identity":digest(binding),"outer":outer,"inner":inner,"salt_commitment":digest(salt),
            "scope":"same_video_groups_across_all_people; every_repeat_stays_grouped",
            "exposure":"public_development_only; no independent raw-measurement claim"}
    validate(result,groups);return result
def validate(plan,groups):
    need(set(plan["outer"])==set(VIDEOS),"Complete outer video denominator")
    for g in set(groups.values()):
        need(len({plan["outer"][v]for v in VIDEOS if groups[v]==g})==1,"No source-equivalence leak")
    for f in range(5):
        inner=plan["inner"][str(f)];need(set(inner)=={v for v in VIDEOS if plan["outer"][v]!=f},"Inner is outer-training only")
        need(set(inner.values())==set(range(5)),"Every inner fold nonempty")
        for g in set(groups.values()):
            need(len({inner[v]for v in inner if groups[v]==g})<=1,"Inner groups remain intact")
    need(set(plan["outer"].values())==set(range(5)),"Every outer fold nonempty")
    return plan

