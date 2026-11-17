"""Paired complete-cohort contrasts of independently private graded metrics."""
import math
from core import need, ROLES, PROFILES, MODALITIES


def comparisons(rows):
    lookup={(r['role'],r['profile']):r['metrics'] for r in rows}
    out=[]
    pairs=[(r,'CM','reference','CM','primary_candidate_minus_reference') for r in ('A','B')]
    pairs += [(r,'CM',r,p,'same_method_information_or_null_control') for r in ROLES for p in ('C','M','CM-shuffled')]
    pairs += [('B','CM','A','CM','paired_code_access_descriptive_difference')]
    for left,lp,right,rp,kind in pairs:
        result={'left':{'role':left,'profile':lp},'right':{'role':right,'profile':rp},'kind':kind,'modalities':{}}
        if (left,lp) not in lookup or (right,rp) not in lookup:
            result.update(available=False,reason='Complete paired profile missing');out.append(result);continue
        for m in MODALITIES:
            a=lookup[(left,lp)]['modalities'][m];b=lookup[(right,rp)]['modalities'][m]
            need(a['available'] and b['available'],'Both complete modality denominators')
            need(a['counts']==b['counts'],'Identical support counts, never favorable subsets')
            for level in ('acquisitions','sessions','animals'):
                need(set(a['mse_hierarchy'][level])==set(b['mse_hierarchy'][level]),'Authenticated identical paired biological units')
            for key,record in a['acquisition_details'].items():
                other=b['acquisition_details'][key]
                need(record['cell_tokens']==other['cell_tokens'] and set(record['trials'])==set(other['trials']),'Identical cells and physical trials')
            differences={k:a['mse_hierarchy']['animals'][k]-b['mse_hierarchy']['animals'][k] for k in a['mse_hierarchy']['animals']}
            need(differences and all(math.isfinite(x) for x in differences.values()),'Complete finite paired-animal differences')
            result['modalities'][m]={'paired_animal_mse_differences':differences,'mean_difference':math.fsum(differences.values())/len(differences),'animals':len(differences),'lower_is_better':True,'uncertainty_or_significance_claim':None}
        result['available']=True;out.append(result)
    return {'schema':'paper_i_paired_comparisons_v1','comparisons':out,'causal_code_effect_claim':False,'combined_modality_scalar':None}
