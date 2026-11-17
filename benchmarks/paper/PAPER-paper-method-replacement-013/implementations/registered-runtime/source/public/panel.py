"""Declared case axes, not empirical subjects or new benchmark counts."""
from io_contract import require

COHORTS = {'medial': 1905, 'lateral': 2022}
METHODS = ('lasso', 'glm', 'mlp', 'bidirectional_gru', 'neuroformer')
ABLATIONS = ('current', 'past', 'video', 'behavior', 'contrastive')

def cases():
    rows=[]
    def add(cohort,family,method,kind,budget=100):
        rows.append({'id':f'{cohort}--{family}--{method}--{budget}',
          'cohort':cohort,'family':family,'method':method,'kind':kind,'budget_percent':budget})
    for cohort in COHORTS:
        for method in METHODS:
            add(cohort,'speed_regression',method,'regression')
            add(cohort,'speed_classification',method,'classification')
        for percent in (1,10):
            for method in ('pretrained','scratch'):
                add(cohort,'fewshot_speed',method,'regression',percent)
        for method in ABLATIONS:add(cohort,'neural_ablation',method,'counts')
        add(cohort,'blocked_speed','improved','regression')
        add(cohort,'blocked_neural','improved','counts')
        add(cohort,'held_session_speed','improved','regression')
    add('lateral','joint_speed_gaze','neuroformer','joint')
    add('lateral','blocked_joint','improved','joint')
    return rows

PANEL=cases()

def visible_modalities(case):
    """Prospective field boundary; native source parity is separately qualified."""
    if case['kind']!='counts':return ('neural_history','neural_current')
    names=[]
    if case['method']!='current':names.append('neural_history')
    if case['method'] in ('video','behavior','contrastive','improved'):names.append('video')
    if case['method'] in ('behavior','contrastive','improved'):
        names.append('speed' if case['cohort']=='medial' else 'gaze')
    return tuple(names)

def definition(cid):
    values=[r for r in PANEL if r['id']==cid];require(len(values)==1,'declared case');return values[0]
