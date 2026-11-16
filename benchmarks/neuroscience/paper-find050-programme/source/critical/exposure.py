"""Build one arm from a common selected input map. No target names are accepted."""
from dataclasses import dataclass
from pathlib import Path
from .core import *
from .programme import contract
@dataclass(frozen=True)
class Exposure:
 condition:str
 common_sha256:str
 candidate_program_sha256:str
 members:tuple
 directory:Path
def stage(condition,common,author,program,root,out,cost):
 need(condition in ("paper-data","paper-data-author"),"paired condition")
 need(type(common) is list and type(author) is list,"finite source sets")
 need(0<len(common)<=256 and len(author)<=128,"exposure membership bound")
 for r in common:
  exact(r,("path","bytes","sha256","role"),"shared member");relative(r["path"]);sha(r["sha256"])
  need(r["role"] in ("paper","public_contract","training_input","training_target","query_input"),"no evaluator/heldout target role")
 need(sum(r["role"]=="paper" for r in common)==1,"same primary paper required")
 for r in author:
  exact(r,("path","bytes","sha256","role"),"author member");relative(r["path"]);sha(r["sha256"])
  need(r["role"]=="original_author_source" and r["path"].startswith("author/"),"B-only exact author path")
 expected=contract("AUTHOR_EXPOSURE.json")["members"]
 need(author==expected,"complete frozen author-source condition, no convenient subset")
 selected=common+(author if condition=="paper-data-author" else [])
 names=[r["path"] for r in selected]
 need(len(names)==len(set(names)) and "candidate.py" not in names,"disjoint exposure paths")
 need(not any(x.split("/")[0] in ("operator","targets","references","legacy") for x in names),"protected namespace excluded")
 out=ordinary(out);need(not out.exists(),"fresh condition directory");out.mkdir(mode=0o700)
 records=[]
 # No candidate is launched or mounted until every streamed leaf is complete.
 # The native lease owns this unexposed namespace, including prior open handles.
 program_raw=read(program,1048576,cost)
 for r in selected:
  p=out/r["path"];p.parent.mkdir(parents=True,exist_ok=True);copy_selected(Path(root)/r["path"],p,r,cost);p.chmod(0o444);records.append(dict(r))
 write(out/"candidate.py",program_raw,cost);(out/"candidate.py").chmod(0o444)
 for p in sorted(out.rglob("*"),reverse=True):
  if p.is_dir():p.chmod(0o555)
 out.chmod(0o555)
 return Exposure(condition,pin(encode(common))["sha256"],pin(program_raw)["sha256"],tuple(records),out)
def paired(a,b):
 need(type(a) is Exposure and type(b) is Exposure and a is not b,"two separately produced exposures")
 need((a.condition,b.condition)==("paper-data","paper-data-author") and a.common_sha256==b.common_sha256,"matched A/B common bytes")
 need(a.directory!=b.directory,"no cross-arm writable state")
 return {"common_sha256":a.common_sha256,"candidate_programs":[a.candidate_program_sha256,b.candidate_program_sha256],"additional_task":False}
