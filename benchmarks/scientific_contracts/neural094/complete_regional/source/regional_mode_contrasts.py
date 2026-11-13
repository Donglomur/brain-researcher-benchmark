"""Paired F/I deployment contrasts, never an anatomical improvement reward."""
import math
from regional_custody import need

NAMES = ('I_gain_over_F_left_logloss','I_gain_over_F_right_logloss',
         'I_minus_F_right_minus_left_logloss')


def trials(targets, views, arithmetic):
    need(set(views) == {'F_left','F_right','I_left','I_right'} and len(targets)>0
         and all(len(v)==len(targets) for v in views.values()), 'Exact paired mode support')
    acc = {name:arithmetic._Mean() for name in NAMES}
    for i,y in enumerate(targets):
        need(not isinstance(y,bool) and int(y)==y and 0<=int(y)<3, 'Original three-class target')
        losses = {}
        for name,rows in views.items():
            p = arithmetic._probability(rows[i])[int(y)]
            losses[name] = math.inf if p == 0 else -math.log(p)
        a,b,c,d = (losses[k] for k in ('F_left','F_right','I_left','I_right'))
        for name,value in zip(NAMES,(a-c,b-d,(d-c)-(b-a)),strict=True):
            acc[name].add(value,('paired_inf_minus_inf',))
    return {name:{'effect':arithmetic.extended(v.value()),'undefined_causes':v.reasons()} for name,v in acc.items()}


def mean(rows, arithmetic):
    need(bool(rows), 'Nonempty fixed structural denominator')
    result = {}
    for name in NAMES:
        acc = arithmetic._Mean()
        for row in rows:
            acc.add(arithmetic.number(row[name]['effect']),row[name]['undefined_causes'])
        result[name] = {'effect':arithmetic.extended(acc.value()),'undefined_causes':acc.reasons()}
    return result


def regional_pair(support, observations, arithmetic):
    """Observations are already source-owned paired-trial reductions, not candidates."""
    expected = {(r['ordinal'],seed) for r in support['session_roster'] if r['K']>0 for seed in support['fixed_seeds']}
    need(set(observations)==expected, 'Every required seed/session; no failure renormalization')
    sessions=[]
    for row in support['session_roster']:
        values=[observations[row['ordinal'],seed] for seed in support['fixed_seeds']] if row['K'] else []
        sessions.append({'ordinal':row['ordinal'],'mouse':row['mouse'],'K':row['K'],
                         'structural_status':row['structural_status'],
                         'seeds':[{'seed':seed,'contrasts':observations[row['ordinal'],seed]} for seed in support['fixed_seeds']] if row['K'] else
                                 [{'seed':seed,'contrasts':None,'status':'structurally_unavailable'} for seed in support['fixed_seeds']],
                         'contrasts':mean(values,arithmetic) if values else None})
    mice=[]
    for row in support['mouse_roster']:
        values=[r['contrasts'] for r in sessions if r['mouse']==row['mouse'] and r['K']>0]
        mice.append({'mouse':row['mouse'],'n_sessions':len(values),
                     'structurally_supported':bool(values),'contrasts':mean(values,arithmetic) if values else None})
    defined=[r['contrasts'] for r in mice if r['structurally_supported']]
    return {'schema':'neural094_paired_strategy_region_contrasts_v1','pair_index':support['pair_index'],
            'session_roster':sessions,'mouse_roster':mice,'equal_supported_mouse_contrasts':mean(defined,arithmetic) if defined else None,
            'trial_then_five_seeds_then_sessions_then_mice':True,'averaged_seed_probabilities':False,
            'anatomical_improvement_reward':False,'causal_claim':False,'significance_claim':False}
