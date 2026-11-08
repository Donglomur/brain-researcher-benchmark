"""Original summary contract and equivalent curve traversal with complete history."""
from .schedule import PEOPLE, curve_nodes, need


def curve_evidence(training, held_rows, held_y, held, latency_class, protocol, store, session, history):
    import numpy as np
    need(list(history)==[r['id']for r in curve_nodes(held)],'complete pre-registered curve history')
    out = {}
    for sidx,stage in enumerate(protocol.STAGES):
        for condition in protocol.CONDITIONS:
            hi=[i for i,r in enumerate(held_rows)if r['condition']==condition]
            xs=sorted(set(float(held_rows[i]['stimulus'])/100 for i in hi))
            for model in protocol.CURVES:
                key=stage+'/'+condition+'/'+model+'_rmse_ms';prefix=f'curve/{held}/{stage}/{condition}/{model}/'
                nodes=[history[prefix+p]for p in PEOPLE if p!=held]
                if not xs:
                    for node in nodes:node.update(status='blocked',failure='held_insufficient_support')
                    out[key]=protocol.cell(None,0,'insufficient_support');continue
                preds=[];reason=None
                for index,(person,rows,y)in enumerate(training):
                    node=nodes[index];need(node['person']==person,'complete source-order curve schedule')
                    ti=[i for i,r in enumerate(rows)if r['condition']==condition]
                    tx=np.asarray([float(rows[i]['stimulus'])/100 for i in ti]);ty=np.asarray([y[i,sidx]/1000 for i in ti])
                    if len(set(tx))<4:
                        node.update(status='blocked',failure='training_insufficient_support');reason='insufficient_support';break
                    node['status']='attempted'
                    session.charge('curve_fit_attempts',1,node['id'])
                    try:
                        session.tick();obj=latency_class(model,ty,tx);obj.fit();session.tick()
                        values=np.asarray(obj.lat_func(np.asarray(xs),*obj.pars),float)*1000
                        if values.shape!=(len(xs),)or not np.all(np.isfinite(values)):raise ValueError('Nonfinite curve')
                        node.update(status='complete',parameters=np.asarray(obj.pars).tolist(),training_rows=len(ti),predictions_ms=values.tolist(),contrast_support=xs)
                        preds.append(values)
                    except (ValueError,RuntimeError,FloatingPointError,OverflowError)as exc:
                        node.update(status='failed',failure=type(exc).__name__);reason='fit_failed';session.context.fail(node['id'],type(exc).__name__);break
                if reason is not None:
                    for node in nodes:
                        if node['status']=='unattempted':node.update(status='blocked',failure='source_prior_training_failure')
                    out[key]=protocol.cell(None,0,reason);continue
                need(len(preds)==25,'all25 training people; no dropped curve fit')
                prediction=np.mean(preds,axis=0)
                observed=np.asarray([np.mean([held_y[i,sidx]for i in hi if float(held_rows[i]['stimulus'])/100==x])for x in xs])
                out[key]=protocol.cell(np.sqrt(np.mean((observed-prediction)**2)),len(xs))
    need(len(history)==1200 and all(x['status']in('complete','failed','blocked')for x in history.values()),'every original maximum curve node disposed')
    record={'held':held,'planned':1200,'nodes':list(history.values()),'semantics':'Exact original early-break and undefined-report behavior; later nodes blocked, never called complete.'}
    return out,store.json('curves-'+held+'.json',record)


def fold_report(epoch_data, held, evaluations, events, recipe, core, protocol, latency_class, store, session, history):
    import numpy as np
    needed=[(k,'held','ordinary')for k in(4,5,6)]+[(5,'train','ordinary')]
    need(all(evaluations[x]['status']=='complete'and events[x]is not None for x in needed),'complete original reconstruction dependencies')
    rows,d,lags=recipe.event_rows(epoch_data,events[(5,'held','ordinary')],held)
    metrics,rank,negative,y=core.summarize_rows(rows,d,lags)
    for k in(4,5,6):
        evaluation=evaluations[(k,'held','ordinary')];total=float(np.asarray([g['scalar_total']for g in evaluation['groups']]).sum())
        n=len(evaluation['rows']);metrics['hmp_'+str(k)+'_nats_per_trial']=protocol.cell(total/n,n)
    training=[]
    for person in PEOPLE:
        if person==held:continue
        tr,td,tl=recipe.event_rows(epoch_data,events[(5,'train','ordinary')],person)
        _,_,_,ty=core.summarize_rows(tr,td,tl);training.append((person,tr,ty))
    curves,history_descriptor=curve_evidence(training,rows,y,held,latency_class,protocol,store,session,history);metrics.update(curves)
    need(len(metrics)==114,'complete114 source report cells')
    return {'person':held,'n_trials':len(rows),'design_rank':rank,'negative_interval_trials':negative,'metrics':metrics},history_descriptor
