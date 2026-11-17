"""Prospective NEURAL098 temporal analysis; no data access at import."""
import hashlib
import math
import re

CHANNELS = ('MEG1931','MEG2121','MEG2331','MEG1921','MEG2111','MEG2341')
WINDOWS = {'pre':(-.3,-.1),'onset':(.1,.3),'middle':(.6,.8),
           'late':(1.1,1.3),'post':(1.6,1.8)}
BASELINE = (-.5,-.3)
DURATIONS = (500,1000,1500)
RELEVANCE = ('Irrelevant','Relevant non-target')
ORIENTATIONS = ('Center','Left','Right')
MAPPINGS = tuple((w,w) for w in WINDOWS) + tuple(('onset',w) for w in WINDOWS if w!='onset')
AVAILABLE = {500:('pre','onset','middle'),1000:('pre','onset','middle','late'),1500:tuple(WINDOWS)}
CELL_KEYS = tuple(f'{r}|{d}|{a}>{b}' for r in RELEVANCE for d in DURATIONS for a,b in MAPPINGS if b in AVAILABLE[d])


def image_fold(trigger):
    if type(trigger) is not int or not 1<=trigger<=40:
        raise ValueError('face/object trigger 1..40 required')
    return ((trigger-1)%20)%2


def validate_rows(rows,participants):
    if type(rows) is not list or not 72<=len(rows)<=100000:
        raise ValueError('bounded complete row roster required')
    if type(participants) is not list or len(set(participants))!=len(participants) or len(participants)<3:
        raise ValueError('unique biological participant roster required')
    keys={'participant','trial_id','stim_trigger','category','duration_ms','relevance','orientation'}
    seen=set();support={}
    for row in rows:
        if type(row) is not dict or set(row)!=keys:raise ValueError('exact observed metadata keys')
        p=row['participant']; t=row['stim_trigger']
        if p not in participants or type(row['trial_id']) is not str or not 1<=len(row['trial_id'])<=100:
            raise ValueError('participant/trial identity')
        identity=(p,row['trial_id'])
        if identity in seen:raise ValueError('duplicate trial')
        seen.add(identity); f=image_fold(t)
        if type(row['category']) is not int or row['category']!=(0 if t<=20 else 1):raise ValueError('category/identity disagreement')
        if type(row['duration_ms']) is not int or row['duration_ms'] not in DURATIONS or row['relevance'] not in RELEVANCE or row['orientation'] not in ORIENTATIONS:
            raise ValueError('exact experimental conditions')
        k=(p,f,row['category'],row['duration_ms'],row['relevance'],row['orientation'])
        support[k]=support.get(k,0)+1
    expected={(p,f,c,d,r,o) for p in participants for f in (0,1) for c in (0,1)
              for d in DURATIONS for r in RELEVANCE for o in ORIENTATIONS}
    if set(support)!=expected:raise ValueError('incomplete fixed participant/identity-half/condition support; do not drop favorable cases')
    return support


def split(rows,held,half):
    if half not in (0,1):raise ValueError('identity half')
    # Long-duration training fixes the classifier across the duration contrast.
    train=[i for i,r in enumerate(rows) if r['participant']!=held and image_fold(r['stim_trigger'])!=half and r['duration_ms']==1500]
    test=[i for i,r in enumerate(rows) if r['participant']==held and image_fold(r['stim_trigger'])==half]
    if not train or not test:raise ValueError('empty fold')
    return train,test


def training_weights(rows,indices):
    # Equal participant x category x duration x relevance x orientation mass.
    groups={}
    for i in indices:
        r=rows[i];k=tuple(r[f] for f in ('participant','category','duration_ms','relevance','orientation'))
        groups.setdefault(k,[]).append(i)
    n=len(indices); out={i:n/(len(groups)*len(v)) for v in groups.values() for i in v}
    return [out[i] for i in indices]


def contrasts(cells):
    if set(cells)!=set(CELL_KEYS):raise ValueError('all 42 cells required')
    out={}
    for r in RELEVANCE:
        for mode in ('diagonal','onset_transfer'):
            def value(d,w):
                a=w if mode=='diagonal' else 'onset'
                return cells[f'{r}|{d}|{a}>{w}']
            effects={
                'middle_duration_interaction':(value(1500,'middle')-value(500,'middle'))-(value(1500,'onset')-value(500,'onset')),
                'late_duration_interaction':(value(1500,'late')-value(1000,'late'))-(value(1500,'onset')-value(1000,'onset')),
                'long_late_minus_onset':value(1500,'late')-value(1500,'onset'),
                'long_post_minus_late':value(1500,'post')-value(1500,'late')}
            for name,x in effects.items():out[f'{r}|{mode}|{name}']=x
    for mode in ('diagonal','onset_transfer'):
        for name in ('middle_duration_interaction','late_duration_interaction','long_late_minus_onset','long_post_minus_late'):
            out[f'relevance_modulation|{mode}|{name}']=out[f'Relevant non-target|{mode}|{name}']-out[f'Irrelevant|{mode}|{name}']
    return out


CONTRAST_KEYS = tuple(contrasts(dict.fromkeys(CELL_KEYS,.5)))


def validate_packet(packet,participants):
    if type(packet) is not dict or set(packet)!={'schema','features_sha256','rows'} or packet['schema']!='neural098-packet-v1':raise ValueError('exact packet schema')
    if type(packet['features_sha256']) is not str or re.fullmatch('[0-9a-f]{64}',packet['features_sha256']) is None:raise ValueError('exact feature SHA256')
    validate_rows(packet['rows'],participants)
    return packet


def validate_report(report,participants):
    if type(report) is not dict or set(report)!={'schema','participants'} or report['schema']!='neural098-analysis-v1':
        raise ValueError('exact report schema')
    if type(report['participants']) is not dict or set(report['participants'])!=set(participants):raise ValueError('full fixed cohort')
    for p,row in report['participants'].items():
        if type(row) is not dict or set(row)!={'cells','contrasts'}:raise ValueError('exact participant outputs')
        if type(row['cells']) is not dict or set(row['cells'])!=set(CELL_KEYS):raise ValueError('full temporal cells')
        for x in row['cells'].values():
            if type(x) not in (int,float) or not 0<=x<=1 or not math.isfinite(x):raise ValueError('finite accuracy in [0,1]')
        expected=contrasts(row['cells'])
        if type(row['contrasts']) is not dict or set(row['contrasts'])!=set(CONTRAST_KEYS):raise ValueError('full signed contrasts')
        for k,x in row['contrasts'].items():
            if type(x) not in (int,float) or not -4<=x<=4 or not math.isfinite(x) or abs(x-expected[k])>1e-12:
                raise ValueError('contrast must agree with supplied cells')
    return report
