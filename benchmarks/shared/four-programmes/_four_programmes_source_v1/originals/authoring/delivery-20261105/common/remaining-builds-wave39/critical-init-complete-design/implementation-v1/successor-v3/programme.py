"""Explicit future controller interface; no implicit operation or environment discovery."""
from pathlib import Path
import argparse,json
from critical_init.custody import write_json,read_pin,parse,need
from critical_init.guard import Budget
from critical_init.workflow import selected_plan,execute_selected,collect,protected_grade
from critical_init.views import materialize

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('operation',choices=['source_inventory','prepare','independent_reference','native_reference','views','candidate','collect','grade'])
 p.add_argument('--root',required=True);p.add_argument('--output',required=True)
 p.add_argument('--authority-path');p.add_argument('--authority-bytes',type=int);p.add_argument('--authority-sha256')
 p.add_argument('--seconds',type=float,required=True);p.add_argument('--read-bytes',type=int,required=True)
 p.add_argument('--write-bytes',type=int,required=True);p.add_argument('--array-bytes',type=int,required=True)
 p.add_argument('--condition',choices=['paper_data','paper_data_author_code'])
 a=p.parse_args();budget=Budget(seconds=a.seconds,read_bytes=a.read_bytes,write_bytes=a.write_bytes,array_bytes=a.array_bytes)
 output=Path(a.output)
 if a.operation=='source_inventory':
  # Only ordinary package source; this never inspects or hashes data/header/model objects.
  source=Path(__file__).parent/'IMPLEMENTATION_MAP.json'
  raw=source.read_bytes();budget.charge_read(len(raw));budget.read_completed+=len(raw)
  d=parse(raw);result={'canonical_id':'PAPER-FIND-050','mandatory_panels':len(d['rows']),'stages':len(d['stage_ids']),
    'gates':len(d['gate_ids']),'original_conflicts':len(d['conflict_ids']),'all_required_unscorable':True,
    'scientific_runs':0,'submission_ready':False}
 else:
  need(a.authority_path and a.authority_bytes and a.authority_sha256,'future independent root authority required')
  authority={'path':a.authority_path,'bytes':a.authority_bytes,'sha256':a.authority_sha256}
  if a.operation in ('prepare','independent_reference','native_reference','candidate'):
   result=execute_selected(a.root,authority,output,budget,operation=a.operation)
  elif a.operation=='views':
   selection,scope,census=selected_plan(a.root,authority,budget,'candidate')
   manifest=parse(read_pin(a.root,selection.body['paired_view_manifest'],selection.body['evidence_cap_bytes'],budget))
   result=materialize(a.root,manifest,output,nonce=selection.body['view_nonce'],budget=budget)
  elif a.operation=='collect':
   need(a.condition,'explicit condition');result=collect(a.root,authority,budget,a.condition)
  else:
   selection,scope,census=selected_plan(a.root,authority,budget,'grade')
   collections={arm:parse(read_pin(a.root,record,selection.body['collection_cap_bytes'],budget))
    for arm,record in selection.body['sealed_collection_pins'].items()}
   result=protected_grade(a.root,authority,budget,collections)
 return write_json(output/'CONTROLLER_RESULT.json',result,budget)

if __name__=='__main__':main()

