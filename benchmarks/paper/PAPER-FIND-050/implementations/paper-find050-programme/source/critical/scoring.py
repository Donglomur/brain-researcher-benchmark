"""Scientific scorers are implemented source and remain unexecuted/unqualified."""
from .core import *
from .result import validate
def flatten(v):
 if type(v) is list:
  for x in v:yield from flatten(x)
 else:yield number(v)
def mae(a,b):
 import math
 x=list(flatten(a));y=list(flatten(b));need(len(x)==len(y)>0,"metric support")
 residual=[abs(i-j) for i,j in zip(x,y)];need(all(math.isfinite(v) for v in residual),"finite residual")
 return {"mae":math.fsum(residual)/len(x),"max_error":max(residual),"count":len(x)}
def complex_match(left,right,operation,name,spec,run):
 from .spectral import workload,MatchingTransaction,NativeMatching
 return MatchingTransaction(workload(operation,name,spec),NativeMatching(run)).run(left,right)
def reproduction(candidate_raw,design,run,vault):
 # Only the actual closed runner object permits target access.
 from .sandbox import actual_closed
 actual_closed(run)
 need(run.returncode==0 and run.output_sha256==pin(candidate_raw)["sha256"],"closed successful candidate producer")
 candidate=validate(candidate_raw,design,run)
 reference=vault.open_for(run,design)
 target=validate(reference,design,run,root=vault.path.parent,protected=True)
 out=[]
 for a,b in zip(candidate["records"],target["records"]):
  if a["status"]!="complete" or b["status"]!="complete":
   out.append({"operation":a["operation"],"status":"not_comparable","candidate":a["status"],"reference":b["status"],"reason":a["reason"] or b["reason"]});continue
  metrics={}
  for k,v in a["outputs"].items():
   kind=design["outputs"][a["operation"]][k]["kind"]
   from . import tensors
   spec=design["outputs"][a["operation"]][k]
   if kind=="complex_pairs":
    left=lambda:list(tensors.values(v,spec,run.output_path.parent,run.owner.output_cost))
    right=lambda:list(tensors.values(b['outputs'][k],spec,vault.path.parent,run.owner.output_cost))
    metrics[k]=complex_match(left,right,a['operation'],k,spec,run)
   else:metrics[k]=tensors.pair_error(v,b["outputs"][k],spec,run.output_path.parent,vault.path.parent,run.owner.output_cost)
  out.append({"operation":a["operation"],"status":"compared","metrics":metrics})
 return {"schema":"critical_init_reproduction_score_v1","records":out,"complete_programme_denominator":len(out),
         "no_mixed_unit_composite":True,"binary_reproduction_pass":None,"scientific_qualified":False}
def normalized_auc(values,delays):
 import math
 need(len(values)==len(delays)>=2 and all(delays[i]<delays[i+1] for i in range(len(delays)-1)),"complete ordered delay support")
 need(all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in values),"accuracy curve")
 return math.fsum((delays[i+1]-delays[i])*(values[i]+values[i+1])/2 for i in range(len(values)-1))/(delays[-1]-delays[0])
def paired_improvement(candidate,reference,design):
 """Paired network bootstrap; this function is never an engineering fixture."""
 import random
 import math
 need(design["test_networks"]==20 and design["bootstrap_replicates"]==10000,"prospective statistical support")
 need(set(candidate)==set(reference)==set(design["network_ids"]),"all planned networks, including failures")
 refs=design["reference_ids"];need(len(refs)>0 and len(refs)==len(set(refs)),"fixed reference family")
 effects={k:[] for k in refs};failures=[]
 for ident in design["network_ids"]:
  c=candidate[ident];r=reference[ident]
  need(set(r)==set(refs) and all(r[k]["status"]=="complete" for k in refs),"all references must complete competence-qualified denominator")
  if c["status"]!="complete":cv=0.;failures.append(ident)
  else:cv=normalized_auc(c["accuracy"],design["delays_seconds"])
  for k in refs:effects[k].append(cv-normalized_auc(r[k]["accuracy"],design["delays_seconds"]))
 rng=random.Random(design["bootstrap_seed"]);boot={k:[] for k in refs}
 for _ in range(design["bootstrap_replicates"]):
  indices=[rng.randrange(20) for j in range(20)]
  for k in refs:boot[k].append(math.fsum(effects[k][i] for i in indices)/20)
 # Bonferroni one-sided bounds, with a fixed quantile definition.
 alpha=(1-design["confidence"])/len(refs);qi=int(alpha*(design["bootstrap_replicates"]-1))
 bounds={k:sorted(boot[k])[qi] for k in refs}
 return {"mean_paired_auc_gain":{k:math.fsum(v)/20 for k,v in effects.items()},
         "simultaneous_lower_bounds":bounds,"practical_margin":design["margin"],
         "meets_prespecified_criterion":all(v>design["margin"] for v in bounds.values()),
         "failed_networks":failures,"network_denominator":20,"independent_unit":"network",
         "inference_limit":"Prospective conditional simulation comparison; bootstrap calibration remains a numerical qualification gate."}
