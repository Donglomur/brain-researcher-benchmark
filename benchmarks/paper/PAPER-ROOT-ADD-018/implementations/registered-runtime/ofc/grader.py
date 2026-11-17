from .lifecycle import guard,current,LifecycleError
"""Separate protected scorer. No candidate callback or candidate-authored targets."""
from .common import require,identity,keyed,finite
from .contracts import FAMILIES,expected_rows
from .universe import commitment

TARGET_STATUSES={'observed','observed_restricted_censored','outside_scoring_mask','scientifically_undefined','unavailable_input_binding','unavailable_operator_target'}
def target_admission(family,row):
 guard('protected grader function admission')
 require(row['disposition']in TARGET_STATUSES,'private target disposition')
 if row['disposition']in('observed','observed_restricted_censored'):
  if family=='I_NEURAL':require(finite(row['value'])>=0,'sqrt count target domain')
  elif family=='I_WAIT':
   require(0<=finite(row['value'])<=100,'restricted wait target');require(row['clock_seconds']==100 and row['assigned_catch']is True,'authentic catch/clock binding')
   if row['disposition']=='observed_restricted_censored':require(row['value']==100 and row['documented_timeout']is True,'missing recording is not timeout')
  elif family=='I_REWARD':require(type(row['value'])is int and row['value']in(1,2,3,4,5),'reward target')
  elif family in('I_SIM_ATI','I_REAL_ATI'):
   require(finite(row['value']['u'])>=0 and finite(row['value']['v'])>=0,'truth norm');require(row['value']['coordinate_map_id'],'truth coordinate map')
 return row
def fixed_support(family,rows,policy):
 guard('protected grader function admission')
 """Scientific support validation, without computing a statistic."""
 required=policy['required_strata'];observed={tuple(r['group_keys'][k]for k in policy['stratum_keys'])for r in rows}
 if observed!=set(tuple(x)for x in required):return 'empty_or_changed_required_stratum'
 if family=='I_REWARD':
  for stratum in required:
   guard('protected grader loop admission')
   subset=[r for r in rows if tuple(r['group_keys'][k]for k in policy['stratum_keys'])==tuple(stratum)]
   if {r['target']for r in subset}!={1,2,3,4,5}:return 'missing_fifth_reward_class'
 if family in('I_SIM_ATI','I_REAL_ATI'):
  if any(r['prediction']['u']+r['prediction']['v']==0 or r['target']['u']+r['target']['v']==0 for r in rows):return 'undefined_full_support_ATI'
  if family=='I_SIM_ATI':
   m=policy['case_mechanisms']
   if len(m)!=200 or sum(v=='additive'for v in m.values())!=100 or sum(v=='divisive'for v in m.values())!=100:return 'not_original200_cases'
 return None
def native_component_support(prediction,target):
 guard('protected grader function admission')
 """A candidate cannot turn a defined required statistic into an exclusion."""
 c={x['component_id']:x for x in prediction['components']};r={x['component_id']:x for x in target['components']}
 if set(c)!=set(r):return False
 for key in c:
  guard('protected grader loop admission')
  if c[key]['disposition']!=r[key]['disposition']:return False
  if c[key]['disposition']=='native_nonfinite':
   a,b=c[key]['data'],r[key]['data']
   if len(a)!=len(b)or any((x if isinstance(x,str)else None)!=(y if isinstance(y,str)else None)for x,y in zip(a,b)):return False
 return True
def _evaluate(family,rows,policy,scientific_authorization):
 guard('protected grader function admission')
 require(scientific_authorization is True,'scientific numerical execution not authorized')
 # Lazy import makes engineering metadata/failure paths unable to execute kernels.
 from scientific import metrics
 if family=='I_NEURAL':return metrics.neural_loss(rows)
 if family=='I_WAIT':return metrics.waiting_loss(rows)['MSE']
 if family=='I_REWARD':return metrics.reward_balanced_accuracy(rows,policy['required_strata'])
 if family=='I_SIM_ATI':return metrics.simulation_recovery(rows,policy['case_mechanisms'])['squared']
 if family.startswith('R_'):return [metrics.native_compare(r['prediction'],r['target'],policy['tolerances'][r['query_id']])for r in rows]
 # Descriptive association and real ATI have independent typed products; no
 # invented mixed metric. Their qualified estimator is a separately pinned source.
 if family in('I_ASSOCIATION','I_REAL_ATI'):
  require(policy['descriptive_producer_qualified'],'descriptive producer not qualified')
  if family=='I_REAL_ATI':
   from scientific.native_semantics import ati
   groups={}
   for r in rows:groups.setdefault((r['group_keys']['rat'],r['group_keys']['session']),[]).append(r)
   return [{'rat':k[0],'session':k[1],**ati([r['prediction']['u']for r in rs],[r['prediction']['v']for r in rs])}for k,rs in groups.items()]
  from scientific.analysis import association_products
  return association_products(rows,policy)
 raise ValueError('unknown family')
def _grade(plan,sealed,private,reference_records,*,scientific_authorization=False):
 guard('protected grader function admission')
 """Called only after the orchestration has closed all candidate/reference arms."""
 require(sealed['plan_id']==identity(plan)and sealed['policy_id']==plan['policy_id'],'sealed plan/policy mismatch')
 require(sealed['public_universe_id']==identity(plan['public_universes']),'public universe mismatch')
 require(private['policy_id']==plan['policy_id'],'target policy')
 require(commitment(plan['public_universes'],plan['native_requests'],private,plan['policy_id'])==plan['protected_commitment']==sealed['private_commitment'],'private precommitment mismatch')
 expected=expected_rows(plan);keys=lambda rows:{(r['family_id'],r['query_id']):r for r in rows}
 pred=keys(sealed['rows']);targets=keys(private['rows']);require(len(targets)==len(private['rows'])and set(targets)==set(expected),'private exact support')
 require(len(pred)==len(sealed['rows'])and set(pred)==set(expected),'sealed prediction support')
 active=[f for f in FAMILIES if f.startswith(plan['condition'][0]+'_')];scores=[]
 for family in active:
  guard('protected grader loop admission')
  familykeys=[k for k in expected if k[0]==family];policy=private['family_policies'][family]
  allpred=[pred[k]for k in familykeys];alltarget=[target_admission(family,targets[k])for k in familykeys]
  candidate_bad=family in sealed['invalid_families']or not sealed['receipt_chain']['natural_complete']or any(r['disposition']in('missing','declared_fit_failure','declared_prediction_failure')for r in allpred)
  undefined=any(r['disposition']=='declared_undefined'for r in allpred);inapplicable=any(r['disposition']=='declared_inapplicable'for r in allpred)
  # Every undefined/inapplicable assertion needs independent operator validation.
  if any(r['disposition']in('declared_undefined','declared_inapplicable')and targets[(family,r['query_id'])].get('validated_candidate_disposition')!=r['disposition']for r in allpred):candidate_bad=True
  unavailable=any(t['disposition'].startswith('unavailable')for t in alltarget)
  target_undefined=any(t['disposition']=='scientifically_undefined'for t in alltarget)
  if family.startswith('R_'):
   for k in familykeys:
    guard('protected grader loop admission')
    t=targets[k];p=pred[k]
    if t['disposition']=='observed'and p['disposition']=='value':
     if not native_component_support(p['value'],t['value']):candidate_bad=True
     if any(c['disposition']in('native_nonfinite','scientifically_undefined')for c in t['value']['components']):target_undefined=True
  counts={'required':len(familykeys),'missing':sum(r['disposition']=='missing'for r in allpred),'invalid_output_records':sum(x['key'][0]in(family,None)for x in sealed['collector_failures']),'declared_fit_or_prediction_failure':sum(r['disposition']in('declared_fit_failure','declared_prediction_failure')for r in allpred),'candidate_undefined':sum(r['disposition']=='declared_undefined'for r in allpred),'candidate_inapplicable':sum(r['disposition']=='declared_inapplicable'for r in allpred),'scored':sum(t['disposition']in('observed','observed_restricted_censored')for t in alltarget),'unscored':sum(t['disposition']=='outside_scoring_mask'for t in alltarget),'censored':sum(t['disposition']=='observed_restricted_censored'for t in alltarget),'undefined':sum(t['disposition']=='scientifically_undefined'for t in alltarget),'unavailable_targets':sum(t['disposition'].startswith('unavailable')for t in alltarget)}
  base={'family_id':family,'condition':plan['condition'],'candidate_status':'invalid'if candidate_bad else'inapplicable'if inapplicable else'scientifically_undefined'if undefined else'complete_valid','target_status':'unavailable'if unavailable else'scientifically_undefined'if target_undefined else'complete_with_valid_censoring'if counts['censored']else'complete_defined','full_counts':counts,'full_support_id':identity(familykeys),'weights_id':identity(policy),'official_absolute_value':None,'paired_gain_by_comparator':{},'reference_status_by_comparator':{},'inferential_claim_status':'not_qualified','family_disposition':'invalid_candidate'if candidate_bad else'required_unscorable','reason':None,'partial_diagnostics_are_official':False}
  rows=[]
  if not candidate_bad and not(undefined or inapplicable or unavailable or target_undefined):
   for k in familykeys:
    guard('protected grader loop admission')
    t=targets[k]
    if t['disposition']=='outside_scoring_mask':continue
    rows.append({'query_id':k[1],'prediction':pred[k]['value'],'target':t['value'],'group_keys':t['group_keys']})
   support_error=fixed_support(family,rows,policy)
   if support_error:base['reason']=support_error
   elif not scientific_authorization:base['reason']='scientific_execution_not_authorized'
   elif not policy['qualified']:base['reason']='scientific_policy_not_qualified'
   else:
    try:base['official_absolute_value']=evaluate(family,rows,policy,True);base['family_disposition']='scored_with_censoring'if counts['censored']else'scored'
    except LifecycleError:raise
    except(ValueError,ArithmeticError)as e:base['reason']='required_scientific_undefined:'+str(e)
  for comparator in policy['mandatory_comparators']:
   guard('protected grader loop admission')
   ref=reference_records.get(comparator);base['paired_gain_by_comparator'][comparator]=None
   if ref is None:base['reference_status_by_comparator'][comparator]='unavailable';continue
   require(ref['plan_id']==identity(plan)and ref['policy_id']==plan['policy_id']and ref['public_universe_id']==sealed['public_universe_id'],'comparator context mismatch')
   require(ref['qualified_source_id']==policy['comparator_sources'][comparator],'comparator source qualification mismatch')
   rmap=keys(ref['rows']);complete=ref['natural_complete']and len(rmap)==len(ref['rows'])and set(rmap)==set(expected)and all(rmap[k]['disposition']=='value'for k in familykeys)
   if not complete:base['reference_status_by_comparator'][comparator]='failed';continue
   base['reference_status_by_comparator'][comparator]='complete_qualified'if policy['qualified']else'unavailable'
   base.setdefault('reference_qualification_details',{})[comparator]='complete_independently_qualified'if policy['qualified']else'complete_execution_but_scientific_reference_qualification_unavailable'
   if base['family_disposition']in('scored','scored_with_censoring')and family in('I_NEURAL','I_WAIT','I_REWARD','I_SIM_ATI'):
    reference_rows=[{**r,'prediction':rmap[(family,r['query_id'])]['value']}for r in rows]
    if fixed_support(family,reference_rows,policy):base['reference_status_by_comparator'][comparator]='scientifically_undefined';continue
    try:
     reference_value=evaluate(family,reference_rows,policy,scientific_authorization)
     base['paired_gain_by_comparator'][comparator]=(base['official_absolute_value']-reference_value)if family=='I_REWARD'else(reference_value-base['official_absolute_value'])
     inference=policy.get('inference',{})
     if family in('I_NEURAL','I_WAIT','I_REWARD')and inference.get('qualified')is True:
      require(inference['all_controls_passed']is True and inference['multiplicity_policy_id'],'inference controls/multiplicity binding')
      differences={}
      for rat in sorted({r['group_keys']['rat']for r in rows}):
       guard('protected grader loop admission')
       cr=[r for r in rows if r['group_keys']['rat']==rat];rr=[r for r in reference_rows if r['group_keys']['rat']==rat];rp=dict(policy)
       if family=='I_REWARD':rp['required_strata']=[s for s in policy['required_strata']if s[0]==rat]
       cv=evaluate(family,cr,rp,True);rv=evaluate(family,rr,rp,True);differences[rat]=cv-rv if family=='I_REWARD'else rv-cv
      from scientific.metrics import paired_rat_interval
      interval=paired_rat_interval(differences,inference['seed'],inference['replicates'],inference['alpha'])
      base.setdefault('paired_rat_uncertainty',{})[comparator]=interval
      base.setdefault('directional_gain_claims',{})[comparator]=interval['lower']>inference['minimum_gain']
    except LifecycleError:raise
    except(ValueError,ArithmeticError):base['reference_status_by_comparator'][comparator]='scientifically_undefined'
  base['mandatory_comparison_status']='complete'if all(x=='complete_qualified'for x in base['reference_status_by_comparator'].values())else'required_unscorable'
  if base.get('directional_gain_claims')and set(base['directional_gain_claims'])==set(policy['mandatory_comparators'])and base['mandatory_comparison_status']=='complete':base['inferential_claim_status']='qualified_directional_gain'if all(base['directional_gain_claims'].values())else'no_qualified_directional_gain'
  scores.append(base)
 return {'schema':'ofc-protected-scores-v1','task_id':plan['task_id'],'condition':plan['condition'],'plan_id':identity(plan),'submission_id':identity(sealed),'private_commitment':plan['protected_commitment'],'policy_id':plan['policy_id'],'source_id':sealed['receipt_chain']['source_id'],'model_id':sealed['receipt_chain']['model_id'],'scores':scores,'scientific_authorized':scientific_authorization,'qualified_benchmark':False}


def evaluate(family,rows,policy,scientific_authorization):
 guard('numerical evaluator admission');result=_evaluate(family,rows,policy,scientific_authorization);guard('numerical evaluator completion');return result

def grade(plan,sealed,private,reference_records,*,scientific_authorization=False):
 c=current()
 if c is not None:
  c.protected('protected grade entry');require(sealed['receipt_chain']['campaign_id']==c.campaign.id,'sealed collection belongs to another campaign')
 result=_grade(plan,sealed,private,reference_records,scientific_authorization=scientific_authorization)
 if c is not None:c.protected('protected grade return')
 return result
