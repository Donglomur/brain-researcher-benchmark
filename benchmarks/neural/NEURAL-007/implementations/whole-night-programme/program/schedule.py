"""Complete support-derived programme graph; pure metadata, no scientific run."""
from .common import MODES, VIEWS, PROFILES, need
from .references import GRID


def graph(folds, rows, profile):
    need(profile in PROFILES, 'Predeclared fixed-program fitting profile')
    caches, refs, contexts, reuse = [], [], [], []
    for row in rows:
        caches.append({'id': f"cache-{row['official_subject']}-{row['official_night']}", 'kind': 'reference_cache',
                       'subject': row['official_subject'], 'night': row['official_night'], 'producer_seconds': 300})
    for fold in folds:
        f = fold['fold']; pre = f'f{f}'
        refs.append({'id': pre+'-R0-validation-fit', 'kind': 'reference_fit', 'family': 'R0', 'view': 'C', 'fold': f, 'role': 'fit52', 'parameter': 1})
        for alpha in (1,10,100):
            refs.append({'id': f'{pre}-R0-validation-{alpha}', 'kind': 'reference_validation', 'family': 'R0', 'view': 'C', 'fold': f, 'alpha': alpha,
                         'model': pre+'-R0-validation-fit', 'people': fold['validation_people']})
        refs.append({'id': pre+'-R0-final-fit', 'kind': 'reference_fit', 'family': 'R0', 'view': 'C', 'fold': f, 'role': 'fit65', 'selection': pre+'-R0'})
        for view in VIEWS:
            if profile == 'training_only_reuse':
                reuse.append({'id': f'{pre}-{view}-fixed-shared-fit', 'kind': 'candidate_shared_fit', 'fold': f, 'view': view,
                              'query_access': False, 'fit_people': fold['final_training_people'], 'seal_before': 'any corresponding query exposure'})
            refs.append({'id': f'{pre}-R1-{view}-final-fit', 'kind': 'reference_fit', 'family': 'R1', 'view': view, 'fold': f, 'role': 'fit65'})
            for leaf in (1,5):
                refs.append({'id': f'{pre}-R2-{view}-validation-fit-{leaf}', 'kind': 'reference_fit', 'family': 'R2', 'view': view, 'fold': f, 'role': 'fit52', 'parameter': leaf})
            for i,(leaf,power) in enumerate(GRID):
                refs.append({'id': f'{pre}-R2-{view}-validation-{i}', 'kind': 'reference_validation', 'family': 'R2', 'view': view, 'fold': f, 'power': power,
                             'model': f'{pre}-R2-{view}-validation-fit-{leaf}', 'people': fold['validation_people']})
            refs.append({'id': f'{pre}-R2-{view}-final-fit', 'kind': 'reference_fit', 'family': 'R2', 'view': view, 'fold': f, 'role': 'fit65', 'selection': f'{pre}-R2-{view}'})
            if view in ('C','EC'):
                refs.append({'id': f'{pre}-R2-{view}-association-fit', 'kind': 'reference_fit', 'family': 'R2', 'view': view, 'fold': f, 'role': 'fit65',
                             'association_control': True, 'selection': f'{pre}-R2-{view}'})
        for subject in fold['query_people']:
            nights = [r['official_night'] for r in rows if r['official_subject'] == subject]
            for view in VIEWS:
                for mode in MODES:
                    generic = mode == MODES[1] or profile == 'generic_current_person'
                    contexts.append({'id': f'{pre}-p{subject}-{view}-'+('fixed' if mode == MODES[0] else 'adaptive'),
                        'fold': f, 'subject': subject, 'nights': nights, 'view': view, 'mode': mode,
                        'fitting_profile': profile if mode == MODES[0] else 'current_person',
                        'probe_limit': 6 if generic else 0, 'provider_decision_limit': 8 if mode == MODES[1] else 0,
                        'final_fit': 'fresh_current_context' if generic else f'{pre}-{view}-fixed-shared-fit',
                        'inferences': ['original','shifted'] if view in ('EC','EOC') else ['original'],
                        'enclosure_seconds': (14640 if view in ('EC','EOC') else 12840) if generic else (4020 if view in ('EC','EOC') else 2220)})
            for family,view in [('R0','C')]+[(x,y) for x in ('R1','R2') for y in VIEWS]:
                model = pre+'-R0-final-fit' if family == 'R0' else f'{pre}-{family}-{view}-final-fit'
                for control in (['original','shifted'] if family != 'R0' and view in ('EC','EOC') else ['original']):
                    refs.append({'id': f'{pre}-{family}-{view}-p{subject}-{control}', 'kind': 'reference_infer', 'family': family, 'view': view,
                                 'fold': f, 'subject': subject, 'nights': nights, 'control': control, 'model': model})
                if family == 'R2' and view in ('C','EC'):
                    refs.append({'id': f'{pre}-R2-{view}-p{subject}-association', 'kind': 'reference_infer', 'family': family, 'view': view,
                                 'fold': f, 'subject': subject, 'nights': nights, 'control': 'association', 'model': f'{pre}-R2-{view}-association-fit'})
    ids = [r['id'] for r in caches+refs+contexts+reuse]
    need(len(ids)==len(set(ids)), 'Complete unique producer/context identities')
    counts = {'candidate_contexts':len(contexts),'candidate_original':len(contexts),
        'candidate_shifted':sum('shifted' in r['inferences'] for r in contexts),
        'candidate_final_fits':sum(r['final_fit']=='fresh_current_context' for r in contexts)+len(reuse),
        'reference_cache':len(caches),'reference_fit':sum(r['kind']=='reference_fit' for r in refs),
        'reference_validation':sum(r['kind']=='reference_validation' for r in refs),
        'reference_infer':sum(r['kind']=='reference_infer' for r in refs)}
    need(counts == {'candidate_contexts':624,'candidate_original':624,'candidate_shifted':312,
        'candidate_final_fits':624 if profile=='generic_current_person' else 336,
        'reference_cache':153,'reference_fit':120,'reference_validation':162,'reference_infer':1170}, 'Complete accepted-design workload')
    return {'schema':'neural007_full153_graph_v1','profile':profile,'counts':counts,'reference_caches':caches,
            'references':refs,'shared_candidate_fits':reuse,'candidate_contexts':contexts,
            'scientific_qualification':False,'independent_task_count':1}
