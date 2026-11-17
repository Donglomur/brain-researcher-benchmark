"""THINGS-fMRI image-disjoint prospective split. No data access at import."""
import hashlib
import math
SUBJECTS=('01','02','03')
ROIS=('V1','IT')
IT_FIELDS=('glasser-TE1p','glasser-TE2p','glasser-FFC','glasser-VVC','glasser-VMV2','glasser-VMV3','glasser-PHA1','glasser-PHA2','glasser-PHA3')
def image_id(name): return 'i'+hashlib.sha256(name.encode()).hexdigest()[:24]
def split(rows_by_person, strict=True):
    if strict and set(rows_by_person)!=set(SUBJECTS): raise ValueError('complete three-person cohort')
    seen_image={}
    for person,rows in rows_by_person.items():
        if strict and len(rows)!=9840: raise ValueError('complete native trial rows')
        ids=set()
        for r in rows:
            if set(r)!=set(('trial_type','session','run','subject_id','trial_id','stimulus','concept')): raise ValueError('source fields')
            if r['subject_id']!=int(person) or not 1<=r['session']<=12 or not 1<=r['run']<=10 or r['trial_id'] in ids: raise ValueError('identity')
            ids.add(r['trial_id'])
            if r['trial_type'] not in ('train','test') or not r['stimulus'].endswith('.jpg') or '/' in r['stimulus'] or not r['concept']: raise ValueError('image identity')
            old=seen_image.setdefault(r['stimulus'],r['concept'])
            if old!=r['concept']: raise ValueError('cross-person image concept mismatch')
        if strict:
            if ids!=set(range(9840)): raise ValueError('complete row index')
            for session in range(1,13):
                rs=[r for r in rows if r['session']==session]
                if len(rs)!=820 or len({r['stimulus'] for r in rs})!=820: raise ValueError('session support')
                if any(sum(r['run']==run for r in rs)!=82 for run in range(1,11)): raise ValueError('run support')
    query={r['stimulus'] for rows in rows_by_person.values() for r in rows if r['session']>=11}
    val={r['stimulus'] for rows in rows_by_person.values() for r in rows if 9<=r['session']<=10 and r['stimulus'] not in query}
    out={}
    for p,rs in rows_by_person.items():
        out[p]={'train':[r for r in rs if r['session']<=8 and r['stimulus'] not in query|val],
                'validation':[r for r in rs if 9<=r['session']<=10 and r['stimulus'] not in query],
                'query':[r for r in rs if r['session']>=11]}
        if strict and (len(out[p]['train'])!=2880 or len(out[p]['validation'])!={'01':1440,'02':720,'03':720}[p] or len(out[p]['query'])!=1640 or len({r['stimulus'] for r in out[p]['query']})!=1540): raise ValueError('frozen split census mismatch')
    if strict and len(query)!=3700: raise ValueError('candidate pool census')
    return out,sorted(query),seen_image

def expected_rank_metrics(scores, correct):
    # Exact expectation over uniform random tie ordering; no gold-based tie break.
    value=scores[correct]; above=sum(x>value for x in scores); ties=sum(x==value for x in scores)
    return ((1.0/ties if above==0 else 0.0),math.fsum(1.0/i for i in range(above+1,above+ties+1))/ties)
