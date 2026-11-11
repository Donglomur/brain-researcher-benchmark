"""Complete original participant/video/session/trial/coordinate joins."""
from collections import Counter
import math
from .core import need, exact, digest
from .protocol import PARTICIPANTS,VIDEOS,repetitions,ROIS,MEASUREMENT_LABEL
TRIAL_FIELDS=("participant","session","task","run","trial","video","repetition","beta_row","source_member","onset_seconds","duration_seconds")
def validate_trials(rows):
    need(type(rows)is list and len(rows)==40200,"All source-declared 40,200 trials; no convenient subcohort")
    seen=set();counts=Counter();groups={}
    for row in rows:
        exact(row,TRIAL_FIELDS)
        p,v=row["participant"],row["video"]
        need(p in PARTICIPANTS and v in VIDEOS and row["session"]in(2,3,4,5),"Typed original subject/video/session")
        need(type(row["run"])is int and row["run"]>0 and type(row["trial"])is str and row["trial"],"Original run/trial identity")
        need(row["task"]in("train","test"),"Original train/test run namespace")
        need((row["task"]=="train")== (int(v[3:])<=1000),"Published 1000/102 membership retained")
        key=(p,row["session"],row["task"],row["run"],row["trial"]);need(key not in seen,"Unique original trial");seen.add(key)
        need(type(row["beta_row"])is int and row["beta_row"]>=0 and row["source_member"],"Exact estimator row/source")
        need(type(row["repetition"])is int and 1<=row["repetition"]<=repetitions(v),"Source repetition, not invented animal/person")
        counts[p,v]+=1;groups.setdefault((p,v),set()).add(row["repetition"])
        need(type(row["onset_seconds"])in(int,float) and math.isfinite(row["onset_seconds"]) and row["onset_seconds"]>=0 and row["duration_seconds"]==3,
             "Source-clock seconds and 3-second silent stimulus; timing qualified separately")
    for p in PARTICIPANTS:
        for v in VIDEOS:
            n=repetitions(v);need(counts[p,v]==n and groups[p,v]==set(range(1,n+1)),"Full repeated-video denominator")
    return {"trial_identity":digest(rows),"trials":len(rows),"declared_people":10,"declared_videos":1102,
            "measurement":MEASUREMENT_LABEL}
def validate_coordinates(rows):
    need(type(rows)is list and rows,"Original coordinate roster")
    keys=set();cells=set()
    for row in rows:
        exact(row,("participant","roi","coordinate","source_index","space","independent_mask_member"))
        need(row["participant"]in PARTICIPANTS and row["roi"]in ROIS and row["space"]=="fsLR32k","Fixed person/ROI/space")
        key=(row["participant"],row["roi"],row["coordinate"]);need(key not in keys,"Unique coordinate within ROI");keys.add(key)
        need(type(row["source_index"])is int and 0<=row["source_index"]<91282 and row["independent_mask_member"],"Authentic surface/volume index mapping")
        cells.add(key[:2])
    # Missing cells are retained by caller as dispositions. They cannot satisfy qualification.
    missing=sorted(set((p,r)for p in PARTICIPANTS for r in ROIS)-cells)
    return {"identity":digest(rows),"missing_cells":missing,"complete":not missing}

