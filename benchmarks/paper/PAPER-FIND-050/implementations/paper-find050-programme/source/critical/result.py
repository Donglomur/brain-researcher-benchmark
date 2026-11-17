"""Admit complete result support before loading any protected target."""
from .core import *
from .programme import catalogue,require_complete_statuses
def validate(raw,design,run,root=None,protected=False):
 result=decode(raw,design["result_cap_bytes"])
 exact(result,("schema","programme_sha256","design_sha256","condition","records"),"candidate result")
 need(result["schema"]=="critical_init_full_result_v1","result schema")
 need(result["programme_sha256"]==design["programme_sha256"] and result["design_sha256"]==design["design_sha256"],"frozen scientific support")
 need(result["condition"]==("common_protected_reference" if protected else run.exposure.condition),"actual condition")
 root=run.output_path.parent if root is None else root
 require_complete_statuses(result["records"],design["profile"])
 for row in result["records"]:
  exact(row,("operation","status","reason","outputs","method_lineage"),"operation result")
  need(type(row['method_lineage']) is dict and bool(row['method_lineage']),'method lineage retained')
  if protected:need(row['method_lineage'].get('domain')=='native_reference','engineering/candidate closure cannot become a protected reference')
  need(type(row["outputs"]) is dict,"typed output map")
  spec=design["outputs"][row["operation"]]
  from .spectral import check_population,check_spec
  check_population(row['operation'],spec)
  if row["status"]!="complete":need(row["outputs"]=={},"failure cannot supply partial success");continue
  need(set(row["outputs"])==set(spec),"all declared estimands")
  for name,v in row["outputs"].items():
   if spec[name]['kind']=='complex_pairs':check_spec(row['operation'],name,spec[name])
   validate_tensor(v,spec[name],root,run.owner.output_cost)
 return result
def validate_tensor(value,spec,root,cost):
 exact(spec,('shape','kind','spectrum') if spec['kind']=='complex_pairs' else ('shape','kind'),"trusted output geometry")
 shape=spec["shape"];need(type(shape) is list and all(type(x) is int and 0<x<=10000000 for x in shape),"fixed nonempty shape")
 need(spec["kind"] in ("real","complex_pairs"),"known numeric output")
 from . import tensors
 tensors.validate(value,spec,root,cost)
 if spec["kind"]=="complex_pairs":need(shape[-1]==2,"complex real/imaginary pairs")
