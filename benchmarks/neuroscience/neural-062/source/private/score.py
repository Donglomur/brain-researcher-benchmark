"""Portable probability-artifact verifier. No fitting, candidate execution or root ledger."""
from pathlib import Path
import re,math
import delivery_io as io
import cohort_binding
import protocol as p
from metrics import aggregate
HEX=re.compile('[a-f0-9]{64}')
def digest(x):return type(x)is str and HEX.fullmatch(x)
def vector(x):
 io.need(type(x)is list and len(x)==8 and all(type(v)in(int,float) and 0<=v<=1 and math.isfinite(v) for v in x) and abs(sum(x)-1)<=1e-6,'Finite8-probability simplex');return x

def validate_plan(plan):
 io.exact(plan,['format','generation','cases']);io.need(plan['format']=='neural062_plan_v1' and digest(plan['generation']) and type(plan['cases'])is list and 1<=len(plan['cases'])<=136,'Plan scope');seen=set();allids=set()
 for c in plan['cases']:
  io.exact(c,['case','query_ids']);io.need(digest(c['case']) and c['case'] not in seen and type(c['query_ids'])is list and len(c['query_ids'])<=500000,'Bounded unique case');seen.add(c['case']);ids=c['query_ids'];io.need(all(digest(x) for x in ids) and len(ids)==len(set(ids)) and not set(ids)&allids,'Unique row IDs');allids.update(ids)
def admit(x,plan,c,arm):
 io.exact(x,['format','generation','case','arm','probabilities']);io.need(x['format']=='neural062_predictions_v1' and x['generation']==plan['generation'] and x['case']==c['case'] and x['arm']==arm,'Current identity');rows=x['probabilities'];io.need(type(rows)is list and len(rows)==len(c['query_ids']),'Exact support');out={}
 for r in rows:io.exact(r,['id','p']);io.need(digest(r['id']) and r['id'] not in out,'Unique row');out[r['id']]=vector(r['p'])
 io.need(set(out)==set(c['query_ids']),'Exact identities');return out

def validate_reference(gold,plan,cohort):
 io.exact(gold,['format','generation','cases']);io.need(gold['format']=='neural062_reference_v1' and gold['generation']==plan['generation'] and len(gold['cases'])==len(plan['cases']),'Reference scope');q={c['case']:set(c['query_ids']) for c in plan['cases']};expected={(r['mouse_id'],r['image_set'],ctx) for r in cohort['rows'] if r['split']!='train' for ctx in p.CONTEXTS};seen=set();expmap={r['ophys_experiment_id']:r for r in cohort['rows']}
 for c in gold['cases']:
  io.exact(c,['case','mouse','image_set','context','split','expected_experiments','rows']);k=(c['mouse'],c['image_set'],c['context']);io.need(k in expected and k not in seen and c['case'] in q,'Exact held cohort case');seen.add(k);io.need(len(c['rows'])==len(q[c['case']]) and {r['id'] for r in c['rows']}==q.pop(c['case']),'Exact gold support')
  exps=sorted(e for e,r in expmap.items() if r['mouse_id']==c['mouse'] and r['image_set']==c['image_set']);io.need(c['expected_experiments']==exps and all(expmap[e]['split']==c['split'] for e in exps),'Expected source experiments')
  for r in c['rows']:
   io.exact(r,['id','label','experiment','bin']);io.need(type(r['label'])is int and 0<=r['label']<8 and r['experiment'] in exps and r['bin'] in('missing','below1','1to5','5to10','10plus'),'Exact target support')
 io.need(seen==expected and not q,'Every held mouse/image/context included')
def evaluate(submission,plan,load_reference,cohort):
 validate_plan(plan);pred={}
 try:
  root=io.regular(submission);io.need(root.is_dir(),'Submission directory');wanted={f'{c["case"]}_{a}.json' for c in plan['cases'] for a in p.ARMS};io.need({x.name for x in root.iterdir()}==wanted,'Exact complete artifact collection')
  for c in plan['cases']:
   for arm in p.ARMS:pred[(c['case'],arm)]=admit(io.json_file(root/f'{c["case"]}_{arm}.json',160000000),plan,c,arm)
 except (ValueError,OSError,KeyError,TypeError,OverflowError) as e:return {'status':'candidate_invalid','primary_score':None,'private_reference_read_attempts':0,'error':str(e)}
 try:
  gold=load_reference();validate_reference(gold,plan,cohort);return {'status':'artifact_verified','private_reference_read_attempts':1,**aggregate(gold,pred)}
 except Exception as e:return {'status':'operator_error','primary_score':None,'private_reference_read_attempts':1,'error':type(e).__name__+': '+str(e)}
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--submission',required=True);a.add_argument('--plan',required=True);a.add_argument('--plan-pin',required=True);a.add_argument('--reference',required=True);a.add_argument('--reference-pin',required=True);a.add_argument('--output',required=True);q=a.parse_args();out=io.fresh(q.output);root=Path(__file__).resolve().parent
 try:
  plan=io.json_file(q.plan,320000000,io.json_file(q.plan_pin));pin=io.json_file(q.reference_pin);result=evaluate(q.submission,plan,lambda:io.json_file(q.reference,640000000,pin),cohort_binding.load(root))
 except Exception as e:result={'status':'operator_error','primary_score':None,'private_reference_read_attempts':0,'error':type(e).__name__+': '+str(e)}
 io.put(out/'score.json',result,8000000)
