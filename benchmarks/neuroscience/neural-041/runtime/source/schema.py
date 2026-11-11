"""NEURAL-041 normative identities, exposure and grouping; no numerical imports."""
from dataclasses import dataclass
from core import need,descriptor,integer

TASK='NEURAL-041'
DATASET='000673/0.240118.2135'
AUTHOR_REVISION='a25e8cc3f61630a428f190381745257d4506f148'
MODES=('frozen_program','case_adaptive_equal_inputs_tools_compute')
ARMS=('numeric','decoder_only','agent_plus_decoder')
REFERENCES=('prior','availability_only','rate_only','power_only','combined')

def exact(value,fields,reason):
    need(type(value)is dict and set(value)==set(fields),reason)
    return value

def opaque(value):
    need(type(value)is str and len(value)==32 and all(c in '0123456789abcdef' for c in value),'opaque study-local identity')
    return value

@dataclass(frozen=True)
class Identity:
    patient:str
    session:str
    trial:str
    def __post_init__(self):
        for x in (self.patient,self.session,self.trial):opaque(x)

def cohort(rows):
    """Complete already authenticated private trial lineage, never actor input."""
    need(type(rows)is list and rows,'complete nonempty private trial manifest')
    seen=set();sessions={};people=set()
    for r in rows:
        exact(r,('identity','source','trial_row0','eligibility','reason','epoch','load'),'private trial row')
        exact(r['identity'],('patient','session','trial'),'full private identity')
        i=Identity(**r['identity']);need(i.trial not in seen,'one trial probability, never one per channel');seen.add(i.trial)
        need(sessions.setdefault(i.session,i.patient)==i.patient,'session belongs to one patient');people.add(i.patient)
        integer(r['trial_row0'],0);descriptor(r['source'])
        need(type(r['eligibility'])is bool and type(r['reason'])is str,'explicit trial disposition')
        need(r['load'] in (1,3) and type(r['load'])is int,'literal source low/high load values')
        if r['eligibility']:need(r['epoch'] is not None and not r['reason'],'eligible complete epoch')
        else:need(r['epoch'] is None and r['reason'],'no silent exclusion')
    return {'patients':tuple(sorted(people)),'sessions':sessions,'trials':seen}

def folds(rows):
    lineage=cohort(rows)
    # Declared 36/44 are admission goals, not asserted facts. Completion below
    # requires the future authenticated source roster and complete dispositions.
    patients=lineage['patients'];need(len(patients)>=3,'nested patient groups require at least three people')
    result=[]
    for held in patients:
        training=tuple(x for x in patients if x!=held)
        result.append({'held':held,'training':training,
            'inner':tuple({'held':v,'training':tuple(x for x in training if x!=v)} for v in training)})
    return tuple(result)

def view_row(row,*,training):
    need(row['eligibility'],'excluded trial cannot enter actor view')
    value={'id':row['identity']['trial'],'epoch':row['epoch']}
    if training:value.update(group=row['identity']['patient'],target=int(row['load']==3))
    # No original session/order/timestamp/load/PicID/probe/correctness/name fields.
    return value

def validate_view(view):
    exact(view,('schema','training','query','regions','protocol'),'closed actor view schema')
    need(view['schema']=='n041_view_v1','view version')
    seen=set();groups=set()
    for train,rows in ((True,view['training']),(False,view['query'])):
        need(type(rows)is list,'finite view rows')
        for row in rows:
            exact(row,('id','epoch','group','target') if train else ('id','epoch'),'no target/event metadata in query')
            opaque(row['id']);need(row['id'] not in seen,'unique disjoint training/query trials');seen.add(row['id'])
            if train:
                groups.add(opaque(row['group']));need(type(row['target'])is int and row['target'] in(0,1),'training binary target')
            exact(row['epoch'],('path','pin'),'fixed opaque epoch descriptor');descriptor(row['epoch']['pin'])
            need(row['epoch']['path']==row['id']+'.npz','no source/event-coded path')
    need(len(groups)>=2 and view['query'],'training groups and complete held query')
    need(type(view['regions'])is list and view['regions']==sorted(set(view['regions'])),'preselected exact anatomical vocabulary')
    return view

def validate_prediction(value,expected):
    exact(value,('schema','probabilities'),'prediction schema has no claimed scores')
    need(value['schema']=='n041_predictions_v1','prediction version')
    rows=value['probabilities'];need(type(rows)is list and len(rows)==len(expected),'complete held trial predictions')
    ids=[r.get('id') for r in rows]
    need(len(set(ids))==len(ids) and set(ids)==set(expected),'exact held trial bijection')
    from core import finite
    for r in rows:
        exact(r,('id','p_high'),'one probability per trial');opaque(r['id'])
        p=finite(r['p_high']);need(0<=p<=1,'bounded probability')
    return rows

def prediction_keys(value,expected):
    """Nonnumerical preflight used by engineering controls."""
    exact(value,('schema','probabilities'),'closed prediction envelope')
    ids=[r['id'] for r in value['probabilities']]
    need(len(ids)==len(set(ids)) and set(ids)==set(expected),'one complete exact ID set')
    return tuple(ids)
