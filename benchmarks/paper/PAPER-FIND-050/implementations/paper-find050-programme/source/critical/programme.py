"""Full scientific route catalogue; expanding it performs no scientific work."""
from pathlib import Path
from .core import decode,need,relative,read,Costs
ROOT=Path(__file__).absolute().parents[1]
_CONTRACT_COST=Costs(16*1048576,0)
_CONTRACT_BYTES={}
def contract(name):
 relative(name)
 if name not in _CONTRACT_BYTES:_CONTRACT_BYTES[name]=read(ROOT/"contracts"/name,1048576,_CONTRACT_COST)
 return decode(_CONTRACT_BYTES[name],1048576)
def contract_costs():return _CONTRACT_COST.report()
def programme():return contract("PROGRAMME.json")
def improvement():return contract("IMPROVEMENT.json")
def catalogue():
 rows=programme()["operations"];need(len({r["id"] for r in rows})==len(rows),"unique operation IDs")
 return {r["id"]:r for r in rows}
def planned_jobs(profile="complete"):
 p=programme();need(profile in p["profiles"],"known programme profile")
 selected=p["profiles"][profile]
 rows=[catalogue()[k] for k in selected]
 need(len(rows)==len(selected),"full selected programme denominator")
 return rows
def require_complete_statuses(records,profile="complete"):
 rows=planned_jobs(profile)
 need(type(records) is list and [r.get("operation") for r in records]==[r["id"] for r in rows],"exact complete ordered operation support")
 for r,s in zip(records,rows):
  need(r.get("status") in ("complete","scientific_unavailable","operational_failure","not_attempted"),"explicit outcome status")
  if r["status"]=="scientific_unavailable":
   need(r.get("reason") in s["allowed_unavailability"],"prespecified scientific unavailability")
  if r["status"]!="complete":need(bool(r.get("reason")),"retained failure/unavailability reason")
 return records
