"""Actual bounded video/checkpoint/ME feature producer, capsule only."""
from pathlib import Path
from .core import need,digest
from .native.io import load,read,dump,relative
from .numeric_io import save
from .protocol import VIDEOS
def run(request):
    import io
    import av,numpy as np,torch
    from scipy.io import loadmat
    from .features import extract,PERMUTATIONS
    root=Path("/inputs");out=Path("/output");cap=request["member_bytes"];source=load(root/request["manifest"])
    need(set(source["videos"])==set(VIDEOS),"All 1102 source videos")
    need(source["motion_energy"]["producer_status"]=="independently_bound_released_S_fin","No frame-difference proxy for published motion energy")
    need(source["category"]["provenance"]=="source_annotations_MiT_classID","Actual annotation provenance")
    descriptor=source["checkpoint"]
    checkpoint=torch.load(io.BytesIO(read(root/relative(descriptor["path"]),cap,descriptor)),map_location="cpu",weights_only=True)
    need("state_dict"in checkpoint,"Pinned M4 checkpoint layout")
    rows={};arrays=[]
    for video in VIDEOS:
        selected=source["videos"][video];body=read(root/relative(selected["video"]["path"]),cap,selected["video"])
        frames=[];timestamps=[]
        with av.open(io.BytesIO(body))as container:
            need(len(container.streams.video)==1,"One original video stream")
            for frame in container.decode(video=0):
                need(len(frames)<request["max_frames"] and frame.pts is not None,"Bounded decoded frames and original clock")
                need(frame.width*frame.height*3<=request["frame_bytes"],"Decoded frame extent")
                frames.append(frame.to_image());timestamps.append(float(frame.pts*frame.time_base))
        extracted,indices=extract(frames,timestamps,checkpoint["state_dict"])
        mat=selected["motion_energy"]
        motion=loadmat(io.BytesIO(read(root/relative(mat["path"]),cap,mat)))["S_fin"].reshape(-1)
        need(np.isfinite(motion).all() and len(motion)==source["motion_energy"]["dimension"],"Complete same original motion-energy layout")
        rows[video]={"category":selected["MiT_classID"],"frame_indices":indices,"timestamps":[timestamps[i]for i in indices],"layers":{}}
        need(type(rows[video]["category"])is list and all(type(c)is str for c in rows[video]["category"]),"Typed original categories, not response labels")
        rows[video]["motion"]=save(out,"features/"+video+"/motion.npy",motion,cap);arrays.append(rows[video]["motion"])
        for layer,values in extracted.items():
            rows[video]["layers"][layer]={}
            for model,value in values.items():
                pin=save(out,"features/"+video+"/"+layer+"/"+model+".npy",value,cap)
                rows[video]["layers"][layer][model]=pin;arrays.append(pin)
    return dump(out/"feature_manifest.json",{"videos":list(VIDEOS),"rows":rows,"arrays":arrays,
         "source_identity":digest(source),"checkpoint":descriptor,"permutations":PERMUTATIONS,
         "claim":"bidirectional shared checkpoint matched ablations; not independent static training"})

