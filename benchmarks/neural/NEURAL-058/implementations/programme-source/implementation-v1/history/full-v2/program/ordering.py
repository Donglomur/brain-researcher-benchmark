"""Stable original-roster ordinals; opaque aliases never determine traversal."""
from core import need


def animals(sessions):
    rows={}
    for s in sessions:
        a=s['animal'];ordinal=s['animal_ordinal']
        need(type(ordinal)is int and ordinal>=0,'source-owned ordinary animal ordinal')
        need(a not in rows or rows[a]==ordinal,'one ordinal per biological animal')
        rows[a]=ordinal
    need(len(set(rows.values()))==len(rows),'unique biological animal ordinals')
    return sorted(rows,key=lambda a:rows[a])


def roster(rows):
    result={}
    for role,count,animal_count in (('source',423,126),('evaluation',29,13)):
        group={s:r for s,r in rows.items() if r['role']==role}
        need(len(group)==count,'complete ordered source corpus')
        need(all(type(r['session_ordinal'])is int for r in group.values()) and
             sorted(r['session_ordinal'] for r in group.values())==list(range(count)),'exact stable session ordinal bijection')
        ordered=sorted(group,key=lambda s:group[s]['session_ordinal'])
        people=animals([group[s] for s in ordered])
        need(len(people)==animal_count and sorted({r['animal_ordinal'] for r in group.values()})==list(range(animal_count)),
             'complete source-owned animal ordinal bijection')
        result[role]=group;result[role+'_order']=ordered
        result['source_animals' if role=='source' else 'eval_animals']=people
    need(not set(result['source_animals'])&set(result['eval_animals']),'full disjoint biological roster')
    folds={}
    for r in result['source'].values():
        a=r['animal'];f=r['fold'];need(type(f)is int and 0<=f<5,'ordinary full source fold')
        need(a not in folds or folds[a]==f,'one fold per animal');folds[a]=f
    need([list(folds.values()).count(i) for i in range(5)]==[26,25,25,25,25],'exact biological fold sizes')
    result['folds']=folds;return result


def sessions(roster,role,animal=None):
    order=roster[role+'_order'];need(len(order)==len(set(order)) and set(order)==set(roster[role]),'complete explicit session order')
    return [s for s in order if animal is None or roster[role][s]['animal']==animal]


def subset_animals(roster,session_ids):
    present={roster['source'][s]['animal'] for s in session_ids}
    return [a for a in roster['source_animals'] if a in present]
