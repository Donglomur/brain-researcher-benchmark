"""Private outcome-independent input presentation; no randomness on import.

Future operation only: random UUID aliases/permutations are private operands,
not hashes of an enumerable public roster. They are fixed across matched views,
modes and controls. Scientific arrays and canonical reference order stay intact.
"""
import random
import uuid
from .common import need,encoded,pin


def create(fold, rows):
    people=fold['final_training_people']+fold['query_people']
    need(len(people)==78 and len(set(people))==78,'Whole original fold')
    rng=random.SystemRandom()
    fit=list(fold['fit_people']);validation=list(fold['validation_people'])
    rng.shuffle(fit);rng.shuffle(validation)
    aliases={str(s):uuid.uuid4().hex for s in people}
    need(len(set(aliases.values()))==78,'Unique fresh random aliases; collision fails, no retry')
    nights={str(s):sorted(r['official_night'] for r in rows if r['official_subject']==s) for s in people}
    for value in nights.values():rng.shuffle(value)
    result={'schema':'neural007_private_presentation_v1','fold':fold['fold'],'aliases':aliases,
            'fit_group_order':fit,'validation_group_order':validation,'night_order':nights,
            'matched_scope':'all candidate views/modes/controls in this outer fold; reference order unchanged'}
    admit(result,fold,rows);return result


def admit(value,fold,rows):
    need(type(value) is dict and set(value)=={'schema','fold','aliases','fit_group_order','validation_group_order','night_order','matched_scope'},'Exact private presentation schema')
    need(type(value['fold']) is int and all(type(x) is list and all(type(y) is int for y in x) for x in (value['fit_group_order'],value['validation_group_order'])),'Exact integer grouped orders')
    need(value['schema']=='neural007_private_presentation_v1' and value['fold']==fold['fold'],'Exact presentation fold')
    need(len(value['fit_group_order'])==52 and set(value['fit_group_order'])==set(fold['fit_people'])
         and len(value['validation_group_order'])==13 and set(value['validation_group_order'])==set(fold['validation_people']), 'Complete unchanged52/13 membership')
    people=set(fold['final_training_people']+fold['query_people'])
    need(set(value['aliases'])==set(value['night_order'])=={str(s) for s in people},'All78 people retained privately')
    import re
    need(len(set(value['aliases'].values()))==78 and all(re.fullmatch('[0-9a-f]{32}',x) for x in value['aliases'].values()),'Opaque unique aliases')
    for s in people:
        wanted=[r['official_night'] for r in rows if r['official_subject']==s];got=value['night_order'][str(s)]
        need(type(got) is list and all(type(n) is int for n in got) and len(got)==len(wanted) and set(got)==set(wanted),'Every original night; listing only, no chronological-array change')
    return value


def handles(value,fold,person):
    need(person in fold['query_people'],'Current original person')
    return {str(s):value['aliases'][str(s)] for s in fold['final_training_people']+[person]}


def apply(plan,value):
    """Only change public group/night listing order, never any artifact bytes."""
    private={r['directory']:r for r in plan['source_membership']}
    by_source={(r['subject'],r['night']):r['directory'] for r in private.values()}
    role_people=list(value['fit_group_order'])+list(value['validation_group_order'])
    remaining={r['subject'] for r in private.values()}-set(role_people)
    need(len(remaining)<=1,'Only one current held person in a candidate view')
    role_people+=list(remaining)
    order=[by_source[(s,n)] for s in role_people for n in value['night_order'][str(s)] if (s,n) in by_source]
    need(len(order)==len(plan['nights']) and set(order)==set(private),'Complete private/public presentation bijection')
    rank={name:i for i,name in enumerate(order)}
    from pathlib import PurePosixPath
    nights=sorted(plan['nights'],key=lambda r:rank[r['directory']])
    members=sorted(plan['members'],key=lambda r:(rank[str(PurePosixPath(r['target']).parent)],r['target']))
    return {**plan,'nights':nights,'members':members,'source_membership':sorted(private.values(),key=lambda r:rank[r['directory']]),
            'presentation':pin(encoded(value))}
