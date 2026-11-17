"""Complete source depth groups, including architecture and matched training cohorts."""
from dataclasses import asdict
from .guard import need

def grouped(mods,rows,groups,limits):
    d=mods['hundred_models_dimensions._depth'];result=[];allmodels=[]
    columns=(d.Column('Model','text'),d.Column('Layer','integer'),d.Column('Layer_FullNames','text'),d.Column('R','real'))
    for label,members in groups:
        need(members and len(set(members))==len(members),'complete unique depth members')
        selected=[x for x in rows if x['Model'] in members]
        need({x['Model'] for x in selected}==set(members),'no omitted depth model')
        need(all(x['R'] is not None for x in selected),'undefined depth remains unscorable')
        table=d.Table(columns,tuple((x['Model'],x['Layer'],x['Layer_FullNames'],float(x['R'])) for x in selected))
        adjusted=d.adjust_layers(table,limits=d.Limits(**limits))
        normalized=d.normalize_to_model_depth(adjusted.table,limits=d.Limits(**limits))
        result.append({'group':label,'members':list(members),'adjustment':asdict(adjusted),'normalized':asdict(normalized)})
        allmodels.extend(members)
    need(len(allmodels)==len(set(allmodels)),'disjoint source groups per comparison')
    return result

def comparisons(mods,rows,rois,limits):
    inf=mods['hundred_models_program.inference'];out={}
    for name in inf.SOURCE_COMPARISONS:
        groups=inf.comparison_groups(name)
        out[name]={roi:grouped(mods,[x for x in rows if x['ROI']==roi],groups,limits) for roi in rois}
    return out
