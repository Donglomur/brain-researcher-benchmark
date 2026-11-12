"""Independent validation of arbitrary participant calibration selections.

This does not fit, modify, serialize or manufacture any participant state.
Original fitted-state and cost custody are admitted by the controller first.
"""
import math
from .common import LEVELS,require,result
from .scoring import loss,interval_value


def select(payload):
    req=payload['request'];p=payload['protocol']
    require(p.get('selection_stage')=='public_calibration' and p.get('fit_state_registry_admitted') is True and p.get('original_costs_admitted') is True,'original participant fit/state/cost admission required','qualification_required')
    require(req.get('scope')=='complete_primary_calibration','different participant calibration weighting needs a separately accepted exact contract','qualification_required')
    expected=req['expected_cases'];roster={x['case_id']:x for x in expected};configs=req['configurations'];planned=req['declared_configuration_ids']
    require(len(roster)==len(expected)==5760,'complete primary calibration has5760 views')
    require(1<=len(planned)<=12 and len(set(planned))==len(planned) and set(configs)==set(planned),'all declared configurations, at most12')
    groups={};worlds={}
    for case in expected:
        group=(case['family'],case['cell'],case['view']);groups.setdefault(group,[]).append(case['case_id'])
        worlds.setdefault((case['family'],case['cell'],case['world_id']),[]).append(case['view'])
    from .catalog import PRIMARY_KEYS
    required_groups={(k['family'],cell,k['trial_view']) for k in PRIMARY_KEYS for cell in k['cells']}
    require(set(groups)==required_groups and len(groups)==144 and all(len(ids)==40 for ids in groups.values()),'exact accepted72cells x2views x40worlds')
    require(len(worlds)==2880 and all(sorted(v)==[2,4] for v in worlds.values()),'2880 independent calibration worlds with pairedviews')
    families={x['family'] for x in expected};require(len(families)==12,'all twelve families')
    require(all(len({x['cell'] for x in expected if x['family']==f})==6 for f in families),'six cells per family')
    alphas=[(1-c)/2 for c in LEVELS];ranked=[]
    for ident in planned:
        config=configs[ident];records=config['records'];by={x['case_id']:x for x in records}
        require(len(by)==len(records) and set(by)==set(roster),'complete calibration products for every configuration')
        cpu=config['original_total_cpu_seconds'];require(type(cpu) in (float,int) and math.isfinite(cpu) and cpu>=0,'original total CPU cost')
        require(config.get('source_sha256') and config.get('original_fit_receipt_id'),'source and original fit receipt required')
        fitted=config.get('fit_status')=='ok' and bool(config.get('fitted_state_id'))
        point_losses=[];interval_scores=[];cover={level:{} for level in LEVELS}
        for case_id,case in roster.items():
            row=by[case_id]
            for key in ('world_id','family','cell','view','input_identity','target_identity'):require(row[key]==case[key],'participant calibration identity '+key)
            require(row['configuration_id']==ident and row['source_sha256']==config['source_sha256'] and row['state_id']==config.get('fitted_state_id'),'calibration source/config/state changed')
            # A failed fit is a retained attempted configuration, never an eligible
            # new frozen state. Its complete case failure records remain present.
            point_losses.append(loss(row,case['truth'])['loss'] if fitted else 1.)
            scores=[]
            for level in LEVELS:
                m=interval_value(row.get('sets',{}).get(str(level),{}) if fitted else {},case['truth'],level)
                scores.append(m['normalized_interval_score']);cover[level].setdefault((case['family'],case['cell'],case['view']),[]).append(m['coverage'])
            interval_scores.append(sum(w*s for w,s in zip(alphas,scores))/sum(alphas))
        # Equal case weights equal the accepted equal-cell/world/view weights
        # because exact complete membership and counts were checked above.
        risk=math.fsum(point_losses)/5760;interval_score=math.fsum(interval_scores)/5760
        eligible=fitted
        for level in LEVELS:
            for f in families:
                for view in (2,4):
                    cells=[v for (fam,cell,vw),v in cover[level].items() if fam==f and vw==view]
                    coverage=math.fsum(math.fsum(v) for v in cells)/240
                    eligible=eligible and abs(coverage-level)<=.03+1e-12 and all(math.fsum(v)/40>=level-.10-1e-12 for v in cells)
        ranked.append({'configuration_id':ident,'state_id':config.get('fitted_state_id'),'point_risk':risk,'interval_score':interval_score,'fit_eligible':fitted,'uncertainty_eligible':bool(eligible),'original_total_cpu_seconds':cpu,'source_sha256':config['source_sha256']})
    point_order=sorted(ranked,key=lambda x:(x['point_risk'],x['original_total_cpu_seconds'],x['configuration_id'].encode('utf8')))
    uncertainty_order=sorted(ranked,key=lambda x:(x['interval_score'],x['original_total_cpu_seconds'],x['configuration_id'].encode('utf8')))
    point_winner=next((x for x in point_order if x['fit_eligible']),None)
    uncertainty_winner=next((x for x in uncertainty_order if x['uncertainty_eligible']),None)
    point_id=point_winner['configuration_id'] if point_winner else None;uncertainty_id=uncertainty_winner['configuration_id'] if uncertainty_winner else None
    declaration=req['participant_selection']
    matches=declaration.get('point_configuration_id')==point_id and declaration.get('point_state_id')==(point_winner['state_id'] if point_winner else None) and declaration.get('uncertainty_configuration_id')==uncertainty_id and declaration.get('uncertainty_state_id')==(uncertainty_winner['state_id'] if uncertainty_winner else None)
    status='ok' if matches and point_id is not None else ('invalid_artifact' if not matches else 'insufficient_support')
    return result({'selected_point_configuration_id':point_id,'selected_point_state_id':point_winner['state_id'] if point_winner else None,'selected_uncertainty_configuration_id':uncertainty_id,'selected_uncertainty_state_id':uncertainty_winner['state_id'] if uncertainty_winner else None,'participant_selection_matches':matches,'point_ranking':point_order,'uncertainty_ranking':uncertainty_order},dict(configurations=len(planned),case_views=5760,worlds=2880,states_created=0,uncertainty_selection_available=uncertainty_id is not None),['All selected states must already exist under original admitted fit receipts.','No uncertainty-qualified configuration yields a null uncertainty selection, not a fabricated state.'],status=status)
