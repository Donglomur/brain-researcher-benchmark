"""Exact producer/checkpoint DAG. External acceptance is separately pinned authority."""
from .contracts import closed,need,descriptor,canonical,digest,Refusal

class Evidence:
 def __init__(self,authority,programme_sha,source_sha,dag,lineage,gates,store,selected_reviews):
  self.authority=authority;self.programme=programme_sha;self.source=source_sha;self.store=store
  self.stages={x['id']:x for x in dag['stages']};self.parents={x:set()for x in self.stages}
  for a,b in dag['edges']:self.parents[b].add(a)
  self.products={x['id']:x for x in lineage['evidence_products']}
  self.checkpoints={c['id']:c for g in gates['gates']for c in g['checkpoints']}
  self.selected_reviews={x['checkpoint']:x['review']for x in selected_reviews};need(len(self.selected_reviews)==len(selected_reviews),'duplicate checkpoint review')
  self.done={};self.evidence={};self.approved={};self.active=None;self.failed=None
 def external(self,product,pin):
  need(product in('E01','E02','E03')and product not in self.evidence,'external predecessor')
  d=self.store.json(pin);closed(d,{'schema','product','programme','source','parents','verdict','authority_pin'})
  need(d['schema']=='NLB017_external_acceptance_v1'and d['product']==product and d['programme']==self.programme and d['source']==self.source and d['verdict']=='accepted','exact external acceptance')
  need(d['parents']=={x:self.evidence[x]for x in self.products[product]['depends_on']},'external lineage')
  need(d['authority_pin']in list(self.authority.input_pins),'operator selected independent acceptance')
  self.store.read(d['authority_pin'],8*2**20);self.evidence[product]=pin
 def checkpoint(self,key):
  if key in self.approved:return
  need(key in self.checkpoints and key in self.selected_reviews,'checkpoint open: '+key)
  c=self.checkpoints[key];need(all(x in self.evidence for x in c['evidence']),'checkpoint missing producer')
  pin=self.selected_reviews[key];need(pin in list(self.authority.input_pins),'review not currently selected')
  d=self.store.json(pin);closed(d,{'schema','checkpoint','programme','source','evidence','independent_reviewer','verdict','unresolved'})
  need(d['schema']=='NLB017_checkpoint_review_v1'and d['checkpoint']==key and d['programme']==self.programme and d['source']==self.source,'checkpoint identity')
  need(d['evidence']=={e:self.evidence[e]for e in c['evidence']}and d['verdict']=='accepted'and d['unresolved']==[],'exact evidence review')
  need(type(d['independent_reviewer'])is str and bool(d['independent_reviewer']),'reviewer identity');self.approved[key]=pin
 def enter(self,stage,role=None):
  self.authority.check(stage,role);self.store.budget.guard();need(self.active is None and stage not in self.done and self.failed is None,'stage single entry')
  need(stage in self.stages and self.parents[stage]<=set(self.done),'stage predecessors')
  for c in self.stages[stage]['required_checkpoints_before_entry']:self.checkpoint(c)
  self.active=stage
 def product(self,key,payloads,terminal):
  need(key not in self.evidence and self.products[key]['produced_at']==self.active,'producer ownership')
  need(all(x in self.evidence for x in self.products[key]['depends_on']),'evidence lineage')
  need(terminal['complete']is True and terminal['first_error']is None,'natural complete producer')
  for d in payloads:descriptor(d);self.store.read(d,128*2**20)
  body={'schema':'NLB017_evidence_v1','product':key,'stage':self.active,'programme':self.programme,'source':self.source,'parents':{x:self.evidence[x]for x in self.products[key]['depends_on']},'payloads':payloads,'terminal':terminal}
  pin=self.store.write('evidence/'+key+'.json',canonical(body),16*2**20);self.evidence[key]=pin;return pin
 def leave(self,terminal):
  need(self.active is not None,'active stage');stage=self.active
  need(terminal['complete']is True and terminal['first_error']is None,'complete stage')
  need(all(x in self.evidence for x in self.stages[stage]['evidence_products']),'all stage products')
  self.done[stage]=terminal;self.active=None
 def abort(self,error,custody):
  if self.failed is None:self.failed={'stage':self.active,'error':error,'custody':custody}
  self.active=None
 def target(self,stage):
  self.authority.check(stage,'protected_score'if stage=='S13'else'protected_uncertainty');self.store.budget.guard()
  need(self.active==stage and stage in('S13','S14')and 'E14'in self.evidence,'no pre-barrier assessment access')
  self.checkpoint('G11.barrier')
 def disposition(self):return {'completed_stages':sorted(self.done),'evidence':dict(self.evidence),'checkpoints':dict(self.approved),'complete':self.failed is None and 'S16'in self.done,'scientifically_qualified':False,'claims_require_separate_exact_review':True}
