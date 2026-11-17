"""All160 source-fold scores; deterministic endpoint/family selection only."""
from core import need
from schedule import configurations
from contracts import ROLES,HEADS


def choose(out_of_fold, source_animals):
    """Each input is an independently admitted actual fit/OOF result, never
    supplied by an agent. The controller's producer graph is verified first.
    """
    expected={(r,c['id'],f) for r in ROLES for c in configurations() for f in range(5)}
    need(set(out_of_fold)==expected,'all160 completed source selection fits')
    configs=list(configurations()); scores={}
    for role in ROLES:
        for config in configs:
            animals={}
            for fold in range(5):
                item=out_of_fold[(role,config['id'],fold)]
                need(item['role']==role and item['config']==config and item['fold']==fold,'exact role/config/fold producer')
                need(not set(animals)&set(item['animals']),'animal occurs in exactly one held fold')
                animals.update(item['animals'])
            need(set(animals)==set(source_animals),'all126 held source animals')
            need(all(len(v)==2 and all(type(x) in (int,float) for x in v) for v in animals.values()),'both defined source OOF endpoints required')
            scores[(role,config['id'])]=[sum(animals[a][h] for a in source_animals)/len(source_animals) for h in range(2)]
    choices={}; strongest={}
    for role in ROLES:
        for h,head in enumerate(HEADS):
            family_scores=[]
            for family in ('ridge','forest','set'):
                selected=max((c for c in configs if c['family']==family),key=lambda c:scores[(role,c['id'])][h])
                choices[role+'/'+family+'/'+head]=selected['id']
                family_scores.append((family,selected['id'],scores[(role,selected['id'])][h]))
            family,config,score=max(family_scores,key=lambda x:x[2])
            strongest[role+'/'+head]={'family':family,'config':config,'source_oof_animal_r2':score}
    return {'schema':'neural058_source_selected_references_v1','choices':choices,'strongest':strongest,
            'all_scores':{r+'/'+c:v for (r,c),v in scores.items()},
            'tie_order':'configuration declaration order, then ridge/forest/set',
            'evaluation_targets_or_scores_used':False}
