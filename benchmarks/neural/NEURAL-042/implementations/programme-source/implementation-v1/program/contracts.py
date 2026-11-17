"""Exact metadata/report admission. No numerical library or input effects."""
from core import need,integer,finite,descriptor
TASK='NEURAL-042'
DESIGNS=('count_only','nuisance_matched')
CONTRASTS=('load3_minus_load1_correct','correct_minus_incorrect_within_load')
METRICS=('corrected_mi','mi','trial_null','shift_null','early_mi','late_mi','theta_power','gamma_power','firing_rate','harmonic_plv','waveform_asymmetry')
CLAIM='descriptive_patient_associations_not_causal_or_crossoscillator_proof'
CELLS=tuple((mode,world,tool) for mode in ('F','I') for world,tool in (('O','T0'),('O','T1'),('D','T0'),('A','T0')))


def exact(value,keys,reason):
    need(type(value)is dict and set(value)==set(keys),reason)
    return value


def opaque(value):
    need(type(value)is str and len(value)==24 and all(c in '0123456789abcdef' for c in value),'opaque24hex identity')
    return value


def identities(values,count=None):
    need(type(values)is list and values==sorted(values) and len(values)==len(set(values)),'sorted unique identity roster')
    for value in values:opaque(value)
    if count is not None:need(len(values)==count,'complete identity count')
    return values


def metric_values(value):
    exact(value,METRICS,'all eleven exact metrics')
    for key in METRICS:
        v=finite(value[key])
        cap=2.0000000001 if key in ('corrected_mi','waveform_asymmetry') else 1.0000000001
        if key not in ('theta_power','gamma_power','firing_rate'):need(abs(v)<=cap,'analytic contrast range '+key)
    return value


def person_rows(rows,person):
    opaque(person);need(type(rows)is list and len(rows)==4,'all four person rows')
    keys=[(d,c) for d in DESIGNS for c in CONTRASTS]
    for row,(design,contrast) in zip(rows,keys):
        exact(row,('patient','design','contrast','n_sessions','n_channels','metrics'),'exact canonical person row')
        need(row['patient']==person and row['design']==design and row['contrast']==contrast,'canonical ordered person identity')
        ns=integer(row['n_sessions'],0,44);nc=integer(row['n_channels'],0,4096)
        if row['metrics'] is None:need(ns==nc==0,'null support counts')
        else:
            metric_values(row['metrics']);need(1<=ns<=nc,'supported session/channel counts')
    return rows


def report(value,roster):
    identities(roster,36)
    exact(value,('schema','patients','groups','claim_scope'),'exact full report')
    need(value['schema']=='neural042_report_v1' and value['claim_scope']==CLAIM,'canonical report schema/scope')
    rows=value['patients'];groups=value['groups']
    need(type(rows)is list and len(rows)==144 and type(groups)is list and len(groups)==4,'full144/four rows')
    for i,person in enumerate(roster):person_rows(rows[4*i:4*i+4],person)
    for j,(d,c) in enumerate((d,c) for d in DESIGNS for c in CONTRASTS):
        g=groups[j];exact(g,('design','contrast','n_patients','mean','ci95','sign_flip_p'),'exact group')
        need(g['design']==d and g['contrast']==c,'canonical group order')
        supported=[rows[i*4+j]['metrics']['corrected_mi'] for i in range(36) if rows[i*4+j]['metrics'] is not None]
        n=integer(g['n_patients'],0,36);need(n==len(supported),'group/person support equality')
        if n<2:need(g['mean'] is None and g['ci95'] is None and g['sign_flip_p'] is None,'insufficient group all statistics null')
        else:
            mean=finite(g['mean']);need(abs(mean-sum(supported)/n)<=1e-10,'group mean/person join')
            need(type(g['ci95'])is list and len(g['ci95'])==2,'two confidence endpoints')
            lo,hi=map(finite,g['ci95']);need(-2.0000000001<=lo<=hi<=2.0000000001,'finite ordered interval')
            need(0<=finite(g['sign_flip_p'])<=1,'probability range')
    return value


def projection(value):
    exact(value,('schema','source','protocol','preparation','people','sessions','views','dispositions'),'exact prepared public projection')
    need(value['schema']=='neural042_projection_v1','projection schema')
    for key in ('source','protocol','preparation'):descriptor(value[key])
    people=identities(value['people'],36);sessions=value['sessions']
    need(type(sessions)is list and len(sessions)==44,'all44 source sessions')
    ids=[]
    for s in sessions:
        exact(s,('id','person','eligible_channels'),'exact opaque session projection');ids.append(opaque(s['id']))
        need(s['person']in people,'session/person roster');identities(s['eligible_channels'])
    need(ids==sorted(ids) and len(set(ids))==44,'unique sorted session membership')
    need(set(s['person']for s in sessions)==set(people),'every source person represented')
    need(type(value['views'])is list and len(value['views'])==108,'all36 O/D/A case manifests')
    keys=[]
    for view in value['views']:
        exact(view,('world','person','path','pin'),'exact case view descriptor')
        need(view['world']in ('O','D','A')and view['person']in people,'case world/person');descriptor(view['pin'])
        keys.append((view['world'],view['person']))
    need(set(keys)=={(w,p)for w in ('O','D','A')for p in people}and len(keys)==len(set(keys)),'complete case views')
    need(type(value['dispositions'])is dict,'bounded public disposition counts')
    return value
