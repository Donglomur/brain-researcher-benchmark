"""Precommitted balanced treatment order across matched campaign pairs."""
import random
from .validation import exact,need,ident,integer


def orders(seed,pair_ids):
    integer(seed,0,2**32-1)
    need(type(pair_ids) is list and len(pair_ids)>=2 and len(pair_ids)%2==0 and len(set(pair_ids))==len(pair_ids),'complete even matched-pair block')
    for key in pair_ids:ident(key)
    flags=[False]*(len(pair_ids)//2)+[True]*(len(pair_ids)//2)
    random.Random(seed).shuffle(flags)
    return {key:['reference',*(['candidate_B','candidate_A'] if flag else ['candidate_A','candidate_B'])] for key,flag in zip(pair_ids,flags)}


def validate(schedule):
    exact(schedule,('seed','pair_ids','pair_id','order'),'frozen matched order')
    expected=orders(schedule['seed'],schedule['pair_ids'])
    need(schedule['pair_id'] in expected and schedule['order']==expected[schedule['pair_id']],'original reproducible assigned order')
    return list(schedule['order'])


def validate_block(campaigns):
    need(campaigns,'complete matched campaign block')
    first=campaigns[0]['schedule'];expected=orders(first['seed'],first['pair_ids'])
    need([c['schedule']['pair_id'] for c in campaigns]==first['pair_ids'],'every precommitted pair realized exactly once in order')
    for campaign in campaigns:
        schedule=campaign['schedule'];validate(schedule)
        need(schedule['seed']==first['seed'] and schedule['pair_ids']==first['pair_ids'],'no retrospective schedule change')
    return expected
