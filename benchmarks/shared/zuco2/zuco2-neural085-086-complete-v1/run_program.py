"""Central ordinary-program-manifest run route, with captured independent outer process."""
import argparse,os,sys,copy
from pathlib import Path
from zuco.io import *
from zuco.authority import Authority
from zuco.budget import Ledger
from zuco.programme import admit
from zuco.process import Process
from zuco.trusted_driver import TrustedDriverBackend

def run(args):
    need(type(args.other_reserve_bytes)is int and args.other_reserve_bytes>=0,"other_reservation_nonnegative");authority=Authority(args.review);review=authority.review;authority.guard();program=admit(args.program,authority.guard);need(program["manifest_pin"]==review["programme_pin"],"selected_program")
    selection=(args.task,args.representation,args.mode);need(selection in [tuple(x) for x in review["selected"]],"default_named_route_selection")
    output=path_guard(args.output);need(output==Path(review["output_root"]).absolute() and not output.exists(),"selected_fresh_output")
    spec=copy.deepcopy(review["budget"]);spec["storage_bytes"]-=args.other_reserve_bytes;need(spec["storage_bytes"]>0,"other_reservation");ledger=Ledger(spec);ledger.guard()
    runtime=decode(read(review["runtime_manifest_pin"]["path"],8*1024**2,review["runtime_manifest_pin"],ledger.guard));root=Path(review["runtime_manifest_pin"]["path"]).parent
    for d in runtime["files"]:read(below(root,d["path"]),d["bytes"],d,ledger.guard)
    ledger.guard();output.mkdir(parents=True)
    request={"review":authority.pin,"program":str(Path(args.program).absolute()),"root_selection":review["selection_id"]};directory=output/"driver";limits=copy.deepcopy(review["job_limits"]);limits.update(review["whole_campaign_reservation"]["driver_limits"])
    job={"id":"trusted-campaign-driver","identity":{"selection_id":review["selection_id"],"task_route":list(selection)},"source_pin":{"sha256":digest(runtime["files"]),"bytes":sum(x["bytes"] for x in runtime["files"])},"directory":str(directory),"limits":limits,"engineering":False,"trusted_controller":True}
    backend=TrustedDriverBackend([sys.executable,str(root/"campaign_worker.py"),"--request",str(directory/"request.json"),"--output",str(directory/"output")],str(root),{"PATH":os.environ.get("PATH",""),"PYTHONDONTWRITEBYTECODE":"1","LANG":"C.UTF-8"},review["OCI_profile"]["delegated_cgroup_root"])
    proc=Process(job,ledger,backend);receipt=proc.run(request);envelope={"schema":"zuco2-original-driver-envelope-v1","runtime_manifest_pin":review["runtime_manifest_pin"],"programme_pin":review["programme_pin"],"review_pin":authority.pin,"driver_request":request,"driver_receipt":receipt,"source_ledger":ledger.snapshot(),"campaign_result_path":str(directory/"output/result.json"),"scientifically_qualified":False}
    # Reserved original receipt capacity survives failed/unknown budget closure.
    raw=encode(envelope);need(len(raw)<=limits['receipt_bytes'],'original_submission_extent');write(output/"SUBMISSION.json",raw);proc.require_success();ledger.final();return envelope
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--task",choices=["NEURAL-085","NEURAL-086"],required=True);a.add_argument("--program",required=True);a.add_argument("--output",required=True);a.add_argument("--review",required=True);a.add_argument("--other-reserve-bytes",type=int,default=0);a.add_argument("--representation",default="released_summary");a.add_argument("--mode",default="frozen_program");run(a.parse_args())
