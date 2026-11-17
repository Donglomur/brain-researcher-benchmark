"""Complete operator-private HMP/reconstruction computation and retained state.

No actor receives this directory. Owner projects only the fixed tool schema after
private identity remapping; reconstruction target evidence remains separately held.
"""
import json
from pathlib import Path
from . import binding, native, reconstruction
from .schedule import PEOPLE, COUNTS, schedule, curve_nodes, need
from .storage import Session, Store, load_array, pin


class HMPFailure(RuntimeError):
    def __init__(self,record):
        super().__init__('HMP operation failed; retained operator accounting/evidence')
        self.record=record


def admit(epoch_data, admission):
    need(admission['schema']=='neural004_hmp_admission_v1'and admission['people']==list(PEOPLE),'complete26 source people')
    need(list(epoch_data.participant.values.astype(str))==list(PEOPLE),'exact source person order')
    need(float(epoch_data.sfreq)==512 and list(map(str,epoch_data.channel.values))==admission['channel_order']and len(admission['channel_order'])==32,'native512Hz32-channel source order')
    need(float(epoch_data.offset)==admission['offset'],'source response offset retained')
    need(set(admission['rows'])==set(PEOPLE),'complete per-person roster')
    for person in PEOPLE:
        rows=admission['rows'][person]
        need(type(rows)is list and rows and len({(type(r['epoch']).__name__,r['epoch'])for r in rows})==len(rows),'unique complete private epoch rows')
        for row in rows:
            need(set(row)=={'epoch','sample_count'}and type(row['epoch'])in(int,str)and(type(row['epoch'])is int or len(row['epoch'])<=256)and type(row['sample_count'])is int and row['sample_count']>=8,'ordinary complete row identity/sample count')


def blocked_evaluation(held,k,support,gain,admission,state,reason):
    people=[held]if support=='held'else[p for p in PEOPLE if p!=held]
    return {'schema':'neural004_hmp_evaluation_v1','held':held,'events':k,'support':support,'gain':gain,'state':state,
            'rows':[[p,r['epoch']]for p in people for r in admission['rows'][p]],'groups':[],
            'status':'blocked','failure':reason,'location':False,'sfreq':512,'offset':admission['offset']}


def run_complete_hmp(epoch_data, admission, limits, inherited_context):
    session=Session(limits,inherited_context);index={'schema':'neural004_complete_hmp_index_v1','source':binding.EXPECTED_BINDING,
        'dataset_pin':admission.get('dataset_pin'),'people':list(PEOPLE),'jobs':[{**r,'status':'unattempted'}for r in schedule()],
        'pca':{},'models':{},'evaluations':{},'pairs':{},'reconstruction':{},'curve_histories':{},'complete':False,'qualified':False}
    jobs={r['id']:r for r in index['jobs']};store=None
    try:
        admit(epoch_data,admission)
        doc,bodies=binding.capture(admission,session);hmp,np=binding.load_native(admission,session,doc,bodies)
        protocol=binding.contract_module('neural004_source_protocol',bodies['protocol.py'])
        recipe=binding.contract_module('neural004_source_recipe',bodies['hmp_recipe.py'],protocol)
        core=binding.contract_module('neural004_source_stage',bodies['stage_core.py'],protocol)
        official=binding.contract_module('neural004_source_curves',bodies['models.py'])
        store=Store(session,limits['output_root'])
        # This private roster is never part of the candidate tool mount.
        index['admission']=store.json('ADMISSION.json',admission)
        reports=[]
        for held in PEOPLE:
            pjob=jobs['pca/'+held];pjob['status']='attempted';pca=None;train=test=pattern=None
            try:
                train,test,pattern,pca,pd=native.preprocess(epoch_data,held,admission,hmp,recipe,store,session)
                index['pca'][held]=pd;pjob.update(status='complete',artifact=pd)
            except Exception as exc:
                pjob.update(status='failed',failure=type(exc).__name__);session.context.fail(pjob['id'],type(exc).__name__)
            evaluations={};event_objects={}
            for k in COUNTS:
                job=jobs[f'fit/{held}/{k}'];model=None;state=None;sd=None
                if pca is None:job.update(status='blocked',failure='pca_dependency')
                else:
                    job['status']='attempted'
                    try:
                        model,state,sd=native.fit_model(train,pattern,held,k,index['pca'][held],admission,bodies,hmp,np,store,session)
                        job.update(status=state['status'],artifact=sd,failure=state['failure'])
                    except Exception as exc:job.update(status='failed',failure=type(exc).__name__);session.context.fail(job['id'],type(exc).__name__)
                if sd is None:
                    state={'schema':'neural004_hmp_state_v1','held':held,'events':k,'status':job['status'],'failure':job.get('failure'),
                           'history':[],'arrays':{},'pca':index['pca'].get(held),'stop':None,'grouping':{},'training_people':[p for p in PEOPLE if p!=held],
                           'source_binding':admission['source_binding'],'dataset_pin':admission['dataset_pin']}
                    sd=store.json(f'fit-{held}-{k}-failed.json',state)
                index['models'][f'{held}/{k}']=sd
                for support in('train','held'):
                    for gain in('ordinary','zero'):
                        ej=jobs[f'eval/{held}/{k}/{support}/{gain}'];events=None
                        if model is None:
                            evaluation=blocked_evaluation(held,k,support,gain,admission,sd,'fit_dependency');ej.update(status='blocked',failure='fit_dependency')
                            ed=store.json(f'eval-{held}-{k}-{support}-{gain}-blocked.json',evaluation)
                        else:
                            ej['status']='attempted'
                            try:
                                evaluation,ed,events=native.evaluate(model,train if support=='train'else test,held,k,support,gain,sd,admission,bodies,hmp,np,store,session)
                                ej.update(status=evaluation['status'],failure=evaluation['failure'])
                            except Exception as exc:
                                evaluation=blocked_evaluation(held,k,support,gain,admission,sd,type(exc).__name__);evaluation['status']='failed';ej.update(status='failed',failure=type(exc).__name__)
                                session.context.fail(ej['id'],type(exc).__name__);ed=store.json(f'eval-{held}-{k}-{support}-{gain}-failed.json',evaluation)
                        ej['artifact']=ed;index['evaluations'][f'{held}/{k}/{support}/{gain}']=ed
                        evaluations[(k,support,gain)]=evaluation
                        # Only original5 ordinary event objects are needed by reconstruction.
                        event_objects[(k,support,gain)]=events if gain=='ordinary'and(k==5 or support=='held')else None
                    a=evaluations[(k,support,'ordinary')];b=evaluations[(k,support,'zero')]
                    pair={'held':held,'events':k,'support':support,'ordinary':index['evaluations'][f'{held}/{k}/{support}/ordinary'],
                          'zero':index['evaluations'][f'{held}/{k}/{support}/zero'],'status':'unavailable','groups':[]}
                    if a['status']==b['status']=='complete':
                        need(len(a['groups'])==len(b['groups']),'matched complete group inventory')
                        for ga,gb in zip(a['groups'],b['groups']):
                            need(all(ga[x]==gb[x]for x in('id','M','location','members')),'identical paired group M and population')
                            left=load_array(session,store.root,ga['arrays']['log_masses']);right=load_array(session,store.root,gb['arrays']['log_masses'])
                            delta=left-right;need(np.isfinite(delta).all(),'finite signed mass difference; no positive-gain rule')
                            pair['groups'].append({'id':ga['id'],'M':ga['M'],'members':ga['members'],
                                'delta':store.array(f'pair-{held}-{k}-{support}-g{ga["id"]}.bin',delta,('trial',),'ordinary minus zero natural-log mass')})
                        pair['status']='complete'
                    index['pairs'][f'{held}/{k}/{support}']=store.json(f'pair-{held}-{k}-{support}.json',pair)
            curve_progress={r['id']:{**r,'status':'unattempted','failure':None}for r in curve_nodes(held)}
            index['inflight_curve_history']=curve_progress
            try:
                report,curves=reconstruction.fold_report(epoch_data,held,evaluations,event_objects,recipe,core,protocol,official.latency,store,session,curve_progress)
                reports.append(report);index['reconstruction'][held]={'status':'complete','artifact':store.json('report-'+held+'.json',report)};index['curve_histories'][held]=curves
            except Exception as exc:
                index['reconstruction'][held]={'status':'failed','failure':type(exc).__name__}
                for row in curve_progress.values():
                    if row['status']=='unattempted':row.update(status='blocked',failure='reconstruction_dependency')
                    elif row['status']=='attempted':row.update(status='failed',failure='aborted_unknown_completion')
                index['curve_histories'][held]=store.json('curves-'+held+'-partial.json',{'held':held,'nodes':list(curve_progress.values()),'scope':'Preserve completed/failed/blocked work exactly; never label an earlier attempt unattempted.'})
                session.context.fail('reconstruction/'+held,type(exc).__name__)
            index.pop('inflight_curve_history');del curve_progress
            session.tick()
        if len(reports)==26:
            report={'schema':'neural004_report_v1','mode':protocol.MODE,'dataset_sha256':admission['dataset_pin']['sha256'],'people':reports}
            protocol.validate(report,admission['dataset_pin']['sha256']);index['report']=store.json('RECONSTRUCTION.json',report)
        index['complete']=all(j['status']=='complete'for j in index['jobs'])and len(reports)==26
        index['costs_before_index_publication']=dict(session.cost);index['artifacts_before_index']=list(store.members)
        descriptor=store.json('INDEX.json',index);session.tick()
        return {'index':descriptor,'output_root':str(store.root),'complete':index['complete'],'costs_after_index_publication':dict(session.cost),'qualified':False}
    except BaseException as exc:
        for job in index['jobs']:
            if job['status']=='unattempted':job.update(status='blocked',failure='operation_stopped')
            elif job['status']=='attempted':job.update(status='failed',failure='operation_stopped_unknown_native_completion')
        index.update(failure=type(exc).__name__,costs=dict(session.cost),artifacts=[]if store is None else list(store.members))
        # No attempt to reset an expired/exhausted clock/budget for failure publication.
        raise HMPFailure(index) from exc


def restore_state(output_root, descriptor, admission, limits, inherited_context):
    session=Session(limits,inherited_context);raw=session.read(Path(output_root)/descriptor['name'],descriptor);state=json.loads(raw)
    need(state['schema']=='neural004_hmp_state_v1'and state['status']=='complete'and state['events']in COUNTS,'complete exact state schema')
    need(state['source_binding']==admission['source_binding']and state['dataset_pin']==admission['dataset_pin'],'exact restored source and dataset lineage')
    need(state['training_people']==[p for p in PEOPLE if p!=state['held']]and state['fit_support']==[[p,r['epoch']]for p in PEOPLE if p!=state['held']for r in admission['rows'][p]],'complete original training-only support')
    doc,bodies=binding.capture(admission,session);hmp,np=binding.load_native(admission,session,doc,bodies)
    pattern=hmp.patterns.HalfSine.create_expected(sfreq=512,width=25)
    model=hmp.models.EventModel(pattern,n_events=state['events'],tolerance=1e-4,max_iteration=1000,min_iteration=1,starting_points=1)
    arrays={k:load_array(session,output_root,d)for k,d in state['arrays'].items()}
    k=state['events'];need(arrays['channel_pars'].shape==(1,k,15)and arrays['time_pars'].shape==(1,k+1,2),'fixed complete state geometry')
    need(all(np.isfinite(arrays[n]).all()for n in('channel_pars','time_pars','traces','time_pars_dev','likelihoods'))and len(arrays['traces'])<=1000,'same finite fit admission on restoration')
    need(state['grouping']['dictionary']=={}and np.array_equal(arrays['channel_map'],np.zeros((1,k)))and np.array_equal(arrays['time_map'],np.zeros((1,k+1))),'original default single-group model')
    for name in('channel_pars','time_pars','traces','time_pars_dev','channel_map','time_map','group'):setattr(model,name,arrays[name])
    model.lkhs=arrays['likelihoods'];model.n_dims=15;model.grouping_dict={};model._fitted=True
    session.tick();return model,state,session
