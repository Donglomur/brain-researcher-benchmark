"""Future private study-context copies; source build never opens primary bodies."""
from .contracts import need,closed,canonical,digest,descriptor,Store,Custody

def context_manifest(view,entries,exposure_review,rights_review,programme):
 need(view in('A','B'),'paper/code view');closed(exposure_review,{'schema','programme','entries','source_comments_reviewed','historical_outputs_absent','cross_task_exposure','verdict'})
 need(exposure_review['schema']=='NLB017_context_exposure_review_v1'and exposure_review['programme']==programme and exposure_review['entries']==entries and exposure_review['verdict']=='accepted'and exposure_review['source_comments_reviewed']is True and exposure_review['historical_outputs_absent']is True,'exact source/context exposure review')
 need(rights_review['programme']==programme and rights_review['verdict']=='accepted'and rights_review['entries']==entries,'exact local study-copy rights')
 allowed={'licensed_primary','method_description','schema','tool_API','exposure_disclosure'}|({'curated_author_code','code_license'}if view=='B'else set())
 selected=[];names=set()
 for e in entries:
  closed(e,{'name','role','source_root','source','provenance'});descriptor(e['source']);need(e['name']not in names,'context member uniqueness');names.add(e['name'])
  need(e['role']in{'licensed_primary','method_description','schema','tool_API','exposure_disclosure','curated_author_code','code_license'},'no historical scores/state/predictions in contexts')
  if e['role']in allowed:selected.append(e)
 need(any(e['role']=='licensed_primary'for e in selected)and any(e['role']=='exposure_disclosure'for e in selected),'full paper and exposure context')
 if view=='B':need(any(e['role']=='curated_author_code'for e in selected),'actual paper+code condition')
 return {'schema':'NLB017_private_context_recipe_v1','programme':programme,'view':view,'members':selected,'cross_task_exposure':exposure_review['cross_task_exposure'],'public_redistribution_authorized':False}

def materialize(recipe,authority,budget,output):
 """Called only under S01/S04 current private-study context authority."""
 authority.check('S01','context_builder');need(recipe['schema']=='NLB017_private_context_recipe_v1','context recipe');rows=[]
 for e in recipe['members']:
  authority.check('S01','context_builder');need(e['source']in list(authority.input_pins),'exact authorized context body');source=Store(e['source_root'],budget,Custody('context_source:'+e['name']))
  raw=source.read(e['source'],32*2**20);pin=output.write(e['name'],raw,32*2**20);rows.append({'name':e['name'],'role':e['role'],'source':e['source'],'copied':pin,'provenance':e['provenance']})
 return output.write('CONTEXT.json',canonical({'schema':'NLB017_private_context_v1','programme':recipe['programme'],'view':recipe['view'],'members':rows,'cross_task_exposure':recipe['cross_task_exposure'],'publication_permission':False}),4*2**20)
