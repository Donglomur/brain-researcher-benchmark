"""Evaluator-owned matched-bank and full reference-family contracts.

No private bank is opened here. Exact common byte commitments are checked before
release and the committed bank is authenticated only after producer closure.
"""
import copy,math
from statistics import mean
from .io import need,digest
from .source import paper,neural,configuration

REFERENCE_FAMILIES=('R0','R1','R2','R3','nonlinear','ANCCR','microstimulus_TDRL','IRI_scaled_TDRL','SOP')

def resources(job,budget):
    t=job['timeout_seconds']; n=job['output_cap_bytes']
    need(type(t) in (int,float) and math.isfinite(t) and 0<t<=budget.limits['candidate_seconds'],'per-job time within central allowance')
    need(type(n) is int and 0<n<=budget.limits['output_bytes'],'per-job output within central allowance')

def terminal_resources(job,budget):
    resources(job,budget)
    r=job['terminal_routine'];t=r['timeout_seconds'];n=r['output_cap_bytes']
    need(type(t) in (int,float) and math.isfinite(t) and 0<t<=job['timeout_seconds'],'F terminal timeout exceeds job allowance')
    need(type(n) is int and 0<n<=job['output_cap_bytes'],'F terminal output exceeds job allowance')
    need(t<=budget.limits['candidate_seconds'] and n<=budget.limits['output_bytes'],'F terminal exceeds central allowance')
    return r

def paper_banks(setup,request,available):
    modes={s['mode'] for _,s,_ in available}
    banks=request.get('evaluation_banks',{})
    need(set(banks)==modes,'complete available-mode evaluator bank commitments')
    for mode,b in banks.items():
        need(set(b)=={'private','public_semantics_sha256','biological_registry_sha256','scoring'},'common evaluator bank fields')
        need(set(b['private'])=={'path','bytes','sha256'},'opaque evaluator byte commitment')
        need(b['biological_registry_sha256']==setup['binding']['biological_registry_sha256'],'common evaluation biological fold')
        need(b['scoring']=={'mode':mode,'scope_sha256':digest(setup['scope']),
             'source_lock_sha256':request['scoring_source_lock_sha256'],
             'bootstrap':request.get('engineering_bootstrap',20)},'common scoring registration')
    for _,s,j in available:
        b=banks[s['mode']]
        need(j['private']==b['private'],'both arms use exactly the common evaluator-owned bank')
        need(j['source_commit']['evaluation_bank_sha256']==digest(b),'pre-release source binds evaluator bank')
        need(sorted(set(j['animals']))==sorted(j['evaluation_animals']),'declared evaluator animal fold')
    bymode={}
    for _,s,j in available:bymode.setdefault(s['mode'],[]).append(j)
    for mode,js in bymode.items():
        need(all(j['evaluation_animals']==js[0]['evaluation_animals'] for j in js),'paired actual evaluation animals')
    return copy.deepcopy(banks)

def paper_public(public,bank):
    semantic={k:v for k,v in public.items() if k not in ('access_contract_sha256','staged_access_files')}
    need(digest(semantic)==bank['public_semantics_sha256'],'paired actual public case and support identity')

def paper_private(value,job,mode):
    value=copy.deepcopy(value)
    if mode=='improvement':
        need(set(value)=={'cases','registered','support_manifest'},'common target/reference/support package has no arm fields')
        need('support_precommit' not in value['registered'],'common registration is arm neutral')
        need(set(r['animal_id'] for r in value['cases'])==set(job['evaluation_animals']),'actual target animal fold')
        need(digest(value['support_manifest'])==job['support_precommit']['support_manifest_sha256'],'common full support matches each arm commitment')
        value['source_commit_sha256']=digest(job['source_commit'])
        value['registered']['support_precommit']=copy.deepcopy(job['support_precommit'])
    else:
        need(set(value)=={'reference'},'common reproduction reference')
    return value

def permission(family,cell_id):
    rights=neural('contracts').cell(cell_id,'NEURAL-045')['input_control_contract']
    if rights['training_neural_state']=='none':return False
    if family=='R0':return rights['elapsed_conditioning_E_authorized']
    if family=='R1':return True
    if family=='R2':return rights['delivered_reward_N_authorized']
    # Flexible/native references require their complete declared input contract.
    return rights['elapsed_conditioning_E_authorized'] and rights['delivered_reward_N_authorized']

def references(numerical,budget):
    extras=[];obligations={};links={}
    for key,slot,j in numerical:
        if slot['task']!='NEURAL-045':continue
        refs=j.get('references',{})
        need(set(refs)==set(REFERENCE_FAMILIES),'all nine mandatory N045 reference families must be accounted for')
        obligations[key]={}
        for family,r in refs.items():
            need(r['status'] in ('available','required_unscorable'),'reference status')
            if r['status']!='available':
                need(set(r)=={'status','reason','support_receipt_sha256'} and r['reason'] and len(r['support_receipt_sha256'])==64,'missing reference evidence')
                obligations[key][family]=dict(r,required=True);continue
            need(permission(family,slot['cell_id']),'reference backfills removed inputs')
            need(set(r)=={'status','program','terminal_routine','registration','actor_lineage','timeout_seconds','output_cap_bytes'},'available fixed reference programme')
            reg=r['registration']
            need(set(reg)=={'family','program_sha256','input_contract_sha256','training_only','selection_receipt_sha256','independent_source_receipt_sha256','engineering_only'},'reference training/source provenance')
            need(reg['family']==family and reg['program_sha256']==r['program']['sha256'] and reg['training_only'] is True and reg['engineering_only'] is True,'reference family/source/training binding')
            need(reg['input_contract_sha256']==digest(neural('contracts').cell(slot['cell_id'],'NEURAL-045')['input_control_contract']),'reference exact information permission')
            need(all(isinstance(reg[k],str) and len(reg[k])==64 for k in ('selection_receipt_sha256','independent_source_receipt_sha256')),'reference provenance commitments')
            need(r['actor_lineage']!=j['actor_lineage'] and r['actor_lineage'],'independent reference actor')
            resources(r,budget);terminal_resources(r,budget)
            need(r['timeout_seconds']<=j['timeout_seconds'] and r['output_cap_bytes']<=j['output_cap_bytes'],'matched reference resources')
            rid=key+'/reference/'+family
            refjob={k:copy.deepcopy(v) for k,v in j.items() if k not in ('references','interactive_report_program','model_tool')}
            refjob.update({k:copy.deepcopy(v) for k,v in r.items() if k not in ('registration','status')})
            refjob['reference_registration']=reg
            # Reference algorithms are frozen even in an adaptive candidate arm.
            refslot=dict(slot,mode='F',tier='X',cell_id='F_X_'+neural('contracts').cell(slot['cell_id'],'NEURAL-045')['control'])
            extras.append((rid,refslot,refjob));links.setdefault(key,{})[family]=rid
            obligations[key][family]={'status':'available_engineering_only','required':True,'job':rid,'registration':reg}
    return extras,obligations,links

def reference_join(candidate,reference):
    a,b=candidate['public'],reference['public']
    need(candidate['private']==reference['private'],'reference protected cases/target grid mismatch')
    for k in ('task','endpoint','view','training','query','endpoint_support'):
        need(a.get(k)==b.get(k),'reference query/support/training/fold mismatch: '+k)
    need(candidate['training_animals']==reference['training_animals'],'reference biological training fold')
    need(candidate['source_export_digest']==reference['source_export_digest'],'reference source export')
    need(neural('contracts').cell(a['cell_id'],'NEURAL-045')['input_control_contract']==
         neural('contracts').cell(b['cell_id'],'NEURAL-045')['input_control_contract'],'reference information permission')

def reference_summary(candidate,closed,links,ids,obligations):
    rows={}
    cc=closed[ids[candidate]]['metrics']
    for family,r in obligations[candidate].items():
        row=copy.deepcopy(r)
        if family in links.get(candidate,{}):
            rr=closed[ids[links[candidate][family]]]['metrics']
            need(set(cc['animals'])==set(rr['animals']),'reference summary animal join')
            paired={a:{'candidate_mse':cc['animals'][a]['mse'],'reference_mse':rr['animals'][a]['mse'],
                       'difference':cc['animals'][a]['mse']-rr['animals'][a]['mse']} for a in cc['animals']}
            zero=[a for a in paired if paired[a]['reference_mse']==0]
            # mean accumulates finite float skills exactly before division, so
            # a representable equal-animal mean cannot overflow in the sum.
            row.update(paired_animals=paired,undefined_reference_animals=zero,
                reference_relative_skill=None if zero else mean(1-v['candidate_mse']/v['reference_mse'] for v in paired.values()))
        rows[family]=row
    required_missing=any(r['status']=='required_unscorable' for r in rows.values())
    primary=rows['R0']
    return {'families':rows,'canonical_denominator':'R0','primary_status':
        'required_unscorable' if primary['status']=='required_unscorable' else
        ('undefined_zero_reference' if primary['undefined_reference_animals'] else 'engineering_score_only'),
        'any_mandatory_reference_unscorable':required_missing,'strongest_reference_improvement_claim_qualified':False,
        'scientific_qualification':False}
