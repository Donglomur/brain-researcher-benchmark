"""Full animal-transfer work graph; dynamic reference reuse is identity-based."""
from core import need
from ordering import sessions
from contracts import MODES, ROLES, TOOLS, REPLICATES, HEADS, source_animal_split


def panels():
    for mode in MODES:
        for role in ROLES:
            for tool in TOOLS:
                for rep in REPLICATES:
                    yield {'id': f'{mode}/{role}/{tool}/r{rep}', 'mode':mode, 'role':role, 'tool':tool, 'replicate':rep}


def author_contexts(roster, panel):
    for animal in (['global'] if panel['mode'] == 'F' else roster['eval_animals']):
        yield {'id': panel['id']+'/author/'+animal, 'panel':panel['id'], 'animal':animal,
               'evaluation_sessions': [] if animal == 'global' else sessions(roster,'evaluation',animal)}


def candidate_sessions(roster, panel):
    for eid in sessions(roster,'evaluation'):
        row=roster['evaluation'][eid]
        context = 'global' if panel['mode'] == 'F' else row['animal']
        yield {'id': panel['id']+'/predict/'+eid, 'panel':panel['id'], 'animal':row['animal'],
               'session':eid, 'author':panel['id']+'/author/'+context, 'heads':list(HEADS)}


def configurations():
    for i, alpha in enumerate((0.01,1.,100.,10000.)):
        yield {'id':f'ridge-{i}','family':'ridge','alpha':alpha}
    for i, (depth, leaf) in enumerate((d,l) for d in (16,None) for l in (5,20)):
        yield {'id':f'forest-{i}','family':'forest','max_depth':depth,'min_samples_leaf':leaf,
               'n_estimators':512,'random_state':580058}
    for i, (lr, wd, epochs) in enumerate((a,b,c) for a in (0.001,0.0003) for b in (0.,0.01) for c in (50,100)):
        yield {'id':f'set-{i}','family':'set','learning_rate':lr,'weight_decay':wd,'epochs':epochs}


def reference_selection(roster):
    for role in ROLES:
        for fold in range(5):
            train, val = source_animal_split(roster, fold)
            for config in configurations():
                yield {'id':f'reference/cv/{role}/{fold}/{config["id"]}', 'role':role,
                       'fold':fold,'config':config,'training_sessions':train,'validation_sessions':val,
                       'heads':list(HEADS)}


def final_models(selection):
    """All family/role/endpoint choices; no incomplete-family shortcut."""
    configs = {x['id']:x for x in configurations()}
    expected = {f'{r}/{f}/{h}' for r in ROLES for f in ('ridge','forest','set') for h in HEADS}
    need(type(selection) is dict and set(selection) == expected, 'complete twelve family/role/endpoint selectors')
    grouped = {}
    for key in sorted(expected):
        role, family, head = key.split('/'); config_id = selection[key]
        need(config_id in configs and configs[config_id]['family'] == family, 'same selected reference family')
        grouped.setdefault((role,config_id),[]).append(head)
    need(6 <= len(grouped) <= 12, 'only exact selected-configuration reuse')
    for (role, config_id), selected_heads in sorted(grouped.items()):
        yield {'id':f'reference/full/{role}/{config_id}','role':role,'fold':'full',
               'config':configs[config_id],'selected_heads':selected_heads,'heads':list(HEADS)}


def final_reference_sessions(roster, selection):
    for model in final_models(selection):
        for eid in sessions(roster,'evaluation'):
            row=roster['evaluation'][eid]
            yield {'id':model['id']+'/predict/'+eid,'model':model['id'],'role':model['role'],
                   'session':eid,'animal':row['animal'],'selected_heads':model['selected_heads']}


def required_counts(roster, selection=None):
    ps = list(panels())
    result = {'candidate_panels':len(ps),
              'author_contexts':sum(sum(1 for _ in author_contexts(roster,p)) for p in ps),
              'candidate_session_predictions':sum(sum(1 for _ in candidate_sessions(roster,p)) for p in ps),
              'reference_selection_fits':sum(1 for _ in reference_selection(roster))}
    need(result == {'candidate_panels':24,'author_contexts':168,'candidate_session_predictions':696,'reference_selection_fits':160},
         'full accepted work graph')
    if selection is not None:
        result['reference_final_fits'] = sum(1 for _ in final_models(selection))
        result['reference_session_predictions'] = sum(1 for _ in final_reference_sessions(roster,selection))
    return result
