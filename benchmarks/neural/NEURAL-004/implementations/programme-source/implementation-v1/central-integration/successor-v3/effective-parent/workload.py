"""Complete prospective schedules; these counts never assert completed fits."""
from .common import PEOPLE,MODES,VIEWS,PREDICTION_POLICIES,need

def graph():
    yield {'id':'source/admission','kind':'admission'}
    for held in PEOPLE:
        yield {'id':f'pca/{held}','kind':'pca','held':held,'training':[p for p in PEOPLE if p!=held]}
        for k in (4,5,6):
            yield {'id':f'hmp/fit/{held}/{k}','kind':'hmp_fit','held':held,'events':k}
            for support in ('training','held'):
                for gain in ('ordinary','zero'):
                    yield {'id':f'hmp/eval/{held}/{k}/{support}/{gain}','kind':'hmp_evaluation','held':held,'events':k,'support':support,'gain':gain}
        for inner in PEOPLE:
            if inner==held:continue
            for candidate in range(23):
                yield {'id':f'reference/inner/{held}/{inner}/{candidate}','kind':'reference_inner','held':held,'validation':inner,'candidate_index':candidate}
        for family in ('B','N'):
            yield {'id':f'reference/final/{held}/{family}','kind':'reference_final_slot','held':held,'family':family}
        for stage in range(8):
            for condition in ('speed','accuracy'):
                for curve in ('linear','pieron','fechner'):
                    for train in PEOPLE:
                        if train!=held:
                            yield {'id':f'curve/{held}/{stage}/{condition}/{curve}/{train}','kind':'curve_fit_maximum_slot','held':held,'fitting_person':train}
        for mode in MODES:
            for view in VIEWS:
                yield {'id':f'prediction/{mode}/{view}/{held}','kind':'prediction_actor','mode':mode,'view':view,'held':held}
            yield {'id':f'reconstruction/{mode}/{held}','kind':'reconstruction_actor','mode':mode,'held':held}
    for policy in PREDICTION_POLICIES:yield {'id':'explanation/'+policy,'kind':'explanation_actor','policy':policy}

def expected_counts():
    return {'people':26,'pca_fits':26,'hmp_fits':78,'ordinary_evaluations':156,'zero_evaluations':156,
        'base_ordinary_evaluations':104,'reference_inner_contexts':650,'reference_inner_states':14950,
        'reference_final_slots':52,'reference_states_maximum':15002,'curve_fits_maximum':31200,
        'report_cells':2964,'prediction_actor_contexts':208,'reconstruction_actor_contexts':52,
        'explanation_actor_contexts':8,'actor_contexts':268,'event_spatial_records':1820,'window_spatial_records':2184}

def context_order():
    # Predictions precede reconstruction; explanation follows both immutable seals.
    for mode in MODES:
        for view in VIEWS:
            for held in PEOPLE:yield ('prediction',mode,view,held)
    for mode in MODES:
        for held in PEOPLE:yield ('reconstruction',mode,None,held)
    for mode in MODES:
        for view in VIEWS:yield ('explanation',mode,view,None)
