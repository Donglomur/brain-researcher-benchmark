"""Headless native observation-to-investigation source, inactive at public entry.
All underscore helpers need future genuine source/target/process owners. A map,
callable or receipt accepted by these consumers never manufactures that authority.
"""
import hashlib
from .native_projection import _project_admitted
from .assembly import assemble_secondary,public_context
from .support import support_tables
from .support_view import assessed_support_context
from .native_references import _fit_and_freeze_references
from .design import POLICIES
from .lifecycle import require_native_producers
from .membership_contract import require_population_shape
from .metadata_io import encoded

def _failure_chain(error):
    result=[];seen=set()
    while error is not None and id(error) not in seen:
        seen.add(id(error));result.append({'type':type(error).__name__,'message':str(error)})
        error=error.__cause__ or error.__context__
    return result

BEHAVIOR_KEYS=('session','condition','session_order','date','onset_order','image','native_image_novel',
 'lifetime_image_count','lifetime_count_status','within_session_prior_count','within_session_history',
 'pre_running_bin','pre_pupil_bin','pre_pupil_area','running','change','outcome_status','outcome_flags','phase')

def _project_population(records,paths,bindings,reader,core,*,secondary,history_producer=None):
    """Literal exact-file owner is inherited reader.opened_source. Its provenance
    admission and physical capacity plan remain missing, and it is not run here.
    Missing files are explicit; malformed sources fail their whole experiment.
    All failures are retained and no alternate source is substituted.
    """
    events=[];held={};coverage=[];dispositions=[];session_signatures={}
    for record in records:
        eid=str(record['ophys_experiment_id']);status='unavailable';error=None;census=None
        try:
            if eid not in paths or eid not in bindings:raise FileNotFoundError('unavailable planned source')
            with reader.opened_source(paths[eid],bindings[eid]) as f:
                subject=reader.internal(f,'general/subject/subject_id')[()]
                subject=subject.decode() if isinstance(subject,bytes) else str(subject)
                if subject!=str(record['mouse_id']):raise ValueError('source subject/membership disagreement')
                result=_project_admitted(f,record,reader,core,history_producer,secondary=secondary)
            # Duplicate imaging planes must agree in behavioral content. The
            # canonical source-session event identity is assigned by projection;
            # support_tables deduplicates overlap counts across imaging planes.
            import json
            signature=hashlib.sha256(json.dumps({'retained':[{k:e[k] for k in BEHAVIOR_KEYS} for e in result['events']],
                'excluded':[{k:e[k] for k in ('behavior_event','condition','reason')} for e in result['dispositions']]},sort_keys=True,allow_nan=False).encode()).hexdigest()
            sid=str(record['ophys_session_id'])
            if sid in session_signatures and session_signatures[sid]!=signature:raise ValueError('behavioral planes disagree')
            session_signatures[sid]=signature
            census=result['event_census']
            events.extend(result['events']);held.update(result['held_responses']);dispositions.extend(result['dispositions']);status='complete'
        except FileNotFoundError as e:error=_failure_chain(e)
        except Exception as e:status='failed';error=_failure_chain(e)
        coverage.append({'experiment':eid,'mouse':str(record['mouse_id']),'session':str(record['ophys_session_id']),
            'container':str(record['ophys_container_id']),'condition':record['experience_level'],'split':record.get('split'),'status':status,'error':error,
            **{key:census[key] if census is not None else None for key in ('source_event_observations','retained_event_observations','excluded_event_observations')}})
    return {'events':events,'held_responses':held,'experiments':coverage,'event_dispositions':dispositions}

def _prepare_admitted(catalogue,secondary,source_files,reader,core,history_producer=None):
    """Two genuine membership issuers must authenticate broader and selected lists
    before this consumer. The public CLI cannot create either in BUILD mode.
    """
    require_population_shape(catalogue,secondary)
    projections={};supports={}
    for name,binding in (('catalogue',catalogue),('secondary',secondary)):
        projection=_project_population(binding['records'],source_files[name]['paths'],source_files[name]['bindings'],reader,core,
            secondary=name=='secondary',history_producer=history_producer)
        membership={'population':name,'membership_status':'admitted','experiments':projection['experiments'],'source_membership_binding':binding['source_membership_binding']}
        context,table=assessed_support_context(membership,projection['events'],projection['event_dispositions'])
        projections[name]={'projection':projection,'membership':membership,'context':context}
        supports[name]=table
    selected=projections['secondary'];assembled=assemble_secondary(selected['membership'],selected['projection']['events'],secondary['mouse_assignments'],selected['projection']['event_dispositions'])
    public={'support_context':{name:projections[name]['context'] for name in ('catalogue','secondary')}};private={'support':supports,'analyses':{},'source_dispositions':projections}
    for policy in POLICIES:
        analysis=assembled['analyses'][policy];cases=analysis['cases']
        for row in cases:row['target']=selected['projection']['held_responses'][row['source_event']]
        fit=[r for r in cases if r['split']=='fit'];validation=[r for r in cases if r['split']=='validation'];query=[r for r in cases if r['split']=='query']
        # References never train on query and never choose a model using query.
        models=freeze=None;reference_predictions=None;reference_error=None
        if analysis['complete_primary_support']:
            try:
                models,freeze=_fit_and_freeze_references(fit,validation,policy,core)
                reference_predictions={name:{arm:models[arm][name].predict(query) for arm in ('JOINT','NUISANCE')} for name in ('hierarchical_mean','hist_gradient_boosting')}
            except Exception as error:reference_error=_failure_chain(error)
        public[policy]={'fit':[{**public_context(r,policy),'target':r['target']} for r in fit],
            'validation':[{**public_context(r,policy),'target':r['target']} for r in validation],
            'query':[public_context(r,policy) for r in query],'roles':assembled['roles']}
        private['analyses'][policy]={'cases':query,'training_target_sd':freeze['training_target_sd'] if freeze else None,
             'mouse_support':analysis['mouse_support'],'complete_primary_support':analysis['complete_primary_support'] and freeze is not None,
             'matching':analysis['matching'],'pair_dispositions':analysis['pair_dispositions'],
             'references':{'predictions':reference_predictions,'frozen_selection':freeze,'failure':reference_error}}
    query_bindings={policy:hashlib.sha256(encoded({'policy':policy,'cases':public[policy]['query']})).hexdigest() for policy in POLICIES}
    investigation_binding=hashlib.sha256(encoded({'queries':query_bindings,'populations':{name:projections[name]['membership']['source_membership_binding'] for name in ('catalogue','secondary')}})).hexdigest()
    private['query_bindings']=query_bindings;private['investigation_binding']=investigation_binding
    public['query_bindings']=query_bindings;public['investigation_binding']=investigation_binding
    return {'public':public,'private':private,'scientific_qualification':False}

def main():require_native_producers()
if __name__=='__main__':main()
