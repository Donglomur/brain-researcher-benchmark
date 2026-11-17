"""Actual paired runner consumer, with full source programme and no fabricated scores."""
from .core import *
from .programme import planned_jobs
from .exposure import stage,paired
from .readiness import require_live_authority
from .result import validate
def execute_one(request,host,cost):
 exact(request,("condition","profile","source_sha256","program","asset_root","common","author","exposure_directory","output_directory","design"),"run request")
 require_live_authority(host,"before_exposure",request["source_sha256"])
 design=request["design"];need(design["profile"]==request["profile"],"same complete profile")
 if design["kind"]=="reproduction":planned_jobs(request["profile"])
 else:need(design["kind"]=="improvement" and request["profile"]=="prospective_memory","explicit prospective endpoint")
 exposure=stage(request["condition"],request["common"],request["author"],request["program"],
    request["asset_root"],request["exposure_directory"],cost)
 host.require("after_exposure_before_launch",request["source_sha256"])
 run,raw=host.run(exposure,request["output_directory"],cost)
 if design["kind"]=="reproduction":validate(raw,design,run)
 else:
  from .improvement import validate_predictions
  validate_predictions(raw,design,run)
 return run,raw
def execute_pair(a,b,hosts,costs):
 need(len(hosts)==len(costs)==2 and hosts[0] is not hosts[1],"independent one-use arm hosts")
 need(a["condition"]=="paper-data" and b["condition"]=="paper-data-author","fixed paired order")
 need(a["profile"]==b["profile"] and a["design"]==b["design"],"same scientific design")
 ra,ba=execute_one(a,hosts[0],costs[0]);rb,bb=execute_one(b,hosts[1],costs[1])
 return {"pair":paired(ra.exposure,rb.exposure),"runs":(ra,rb),"bodies":(ba,bb)}
