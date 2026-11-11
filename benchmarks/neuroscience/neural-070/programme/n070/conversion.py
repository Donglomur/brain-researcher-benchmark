"""Future trusted, isolated conversion of original object containers to primitives.

Pickled original estimators are never participant inputs. This worker requires
an independently qualified immutable converter image and exact pinned inputs.
There is no host fallback and no source-authority inference from a dictionary.
"""
from pathlib import Path
from .core import need
from .native.io import read,load,dump
from .numeric_io import save
from .roster import validate_trials,validate_coordinates
from .protocol import PARTICIPANTS,ROIS,MEASUREMENT_LABEL
def run(request):
    import numpy as np
    import io,pickle
    root=Path("/inputs");out=Path("/output")
    manifest=load(root/request["manifest"])
    need(manifest["estimator"]=="VersionB_joint_GLMsingle"and manifest["field"]=="betasmd"
         and manifest["normalization"]=="none","Selected unnormalized measurement")
    rows=manifest["trials"];coordinates=manifest["coordinates"];validate_trials(rows)
    need(validate_coordinates(coordinates)["complete"],"All fixed independent 46 ROI cells")
    need(manifest["object_container_review"]=="independently_qualified","Object containers require trusted isolated conversion")
    cap=request["member_bytes"];products={}
    for person in PARTICIPANTS:
        personrows=[];pieces={roi:[]for roi in ROIS}
        for session in (2,3,4,5):
            selected=manifest["sessions"][person][str(session)]
            expected=sorted([r for r in rows if r["participant"]==person and r["session"]==session],key=lambda r:r["beta_row"])
            need([r["beta_row"]for r in expected]==list(range(len(expected))),"Exact complete estimator row order")
            need(selected["expanded_bytes"]<=request["expanded_bytes"],"Qualified object expansion bound before deserialization")
            original=np.load(io.BytesIO(read(root/selected["betas"]["path"],cap,selected["betas"])),allow_pickle=True).item()
            x=original["betasmd"].squeeze().T
            events,_=pickle.loads(read(root/selected["condition_order"]["path"],cap,selected["condition_order"]))
            order=[str(v)for event in events for v in event["trial_type"]]
            need(x.shape==(len(expected),91282)and order==[r["video"]for r in expected],"Actual conditionOrder-to-estimator row join")
            original=[(task,run,video,onset)for (task,run),event in zip(
                [("test",i)for i in range(1,4)]+[("train",i)for i in range(1,11)],events)
                for video,onset in zip(event["trial_type"],event["onset"])]
            need(len(events)==13 and original==[(r["task"],r["run"],r["video"],r["onset_seconds"])for r in expected],
                 "Original task/run/video/onset to beta row; fractional seconds retained")
            need(all(r["source_member"]==selected["betas"]["path"]for r in expected),"Original source member identity")
            for roi in ROIS:
                indices=[c["source_index"]for c in coordinates if c["participant"]==person and c["roi"]==roi]
                a=x[:,indices];need(np.isfinite(a).all(),"Nonfinite measurement disposition required; no coordinate dropping")
                pieces[roi].append(a)
            personrows.extend(expected)
        products[person]={"trials":personrows,"responses":{},"coordinates":[c for c in coordinates if c["participant"]==person]}
        for roi in ROIS:
            products[person]["responses"][roi]=save(out,person+"/"+roi+".npy",np.concatenate(pieces[roi]),cap)
    return dump(out/"primitive_manifest.json",{"measurement":MEASUREMENT_LABEL,"participants":products,
        "coordinate_identity":manifest["coordinate_identity"],"trials_identity":manifest["trials_identity"]})

