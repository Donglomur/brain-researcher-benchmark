"""Actual receipt/array-to-reviewed-consumer composition and appendix production."""
from pathlib import Path
from dataclasses import asdict
import importlib.util
import sys
from .guard import need,capture,strict,bare,encoded,Unscorable
from .array_io import load_array,finite_json
from . import legacy,endpoints,depth as depth_production
from .source import source_bytes

def load_numerical(package):
    path=Path(package)/'numerical-producers/numerical.py';spec=importlib.util.spec_from_file_location('_hundred_models_numerical',path)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

def production(session,package,scope,receipts,schedule,publisher):
    np=session.np;b=session.budget;mods=legacy.modules(package);cat=mods['hundred_models_program.catalog']
    protocol_raw=source_bytes(package,'source-donors/metadata/PROTOCOL.json',b);inventory_raw=source_bytes(package,'source-donors/metadata/MODEL_SOURCE_INVENTORY.json',b)
    protocol=strict(protocol_raw)
    graph=legacy.graph_binding(protocol,receipts['features'],session.env,session.inputs,bare(protocol_raw));graph_raw=encoded(graph)
    catalog=cat.compile_catalog(protocol_raw,inventory_raw,graph_raw,cat.pin(graph_raw),require_complete=True)
    graph_desc=publisher.write('observed_graph.json',graph_raw);catalog_desc=publisher.write('catalog.json',encoded(catalog))
    layers={m:catalog['models'][m]['layers'] for m in catalog['model_order']}
    def read_values(receipt):return load_array(np,Path(receipt['output_root']),receipt['values'],receipt['shape'],b,allow_undefined=True)
    def selected_values(condition,roi):
        receipt=receipts['rsa'][(condition,roi)];values=read_values(receipt);names=[x.replace('.','_') for x in receipt['layers']]
        need(len(names)==len(set(names)),'no emitted namespace collisions');model=condition.split(':',2)[2]
        order=layers[model] if model in layers else auxiliary_order
        need(set(order)<=set(names),'full retained evaluation layers')
        return [(name,values[names.index(name),:].tolist()) for name in order]
    # The auxiliary model uses the same source rule on its actual observed graph/config.
    aux_config=strict(capture(session.root,session.inputs['auxiliary_configuration'],b))
    aux_feature=receipts['features'][('test','videomae_B_pretrainONLY')]
    auxiliary_order=cat.source_order({'config':aux_config},aux_feature['named_modules'])
    need(set(auxiliary_order)=={x.replace('.','_') for x in aux_feature['emitted_feature_keys']}-set(aux_config.get('rsa_skips',[])),'complete auxiliary source layer closure')
    undefined=[];selections={};ranked={};scaled={}
    for roi in session.inputs['rois']:
        selections[roi]={}
        for m in catalog['model_order']:
            rows=selected_values('test:pca:'+m,roi);values=finite_json([row for _,row in rows])
            selections[roi][m]=endpoints.selected_layer([name for name,_ in rows],values)
            if selections[roi][m]['status']=='undefined':undefined.append({'roi':roi,'model':m,'field':'observed_RSA'})
        ranked[roi]=endpoints.rankings(selections[roi],[m['id'] for m in protocol['models'] if m['type'] in ('image-k400','video-k400')],[m['id'] for m in protocol['models'] if m['type']=='image-in1k'])
        scaled[roi]=endpoints.ceiling_scaling(selections[roi],receipts['rsa'][('test:pca:'+catalog['model_order'][0],roi)]['noise_ceilings'])
    def observed_frames():
        for roi in session.inputs['rois']:
            yield roi,[(m,selected_values('test:pca:'+m,roi)) for m in catalog['model_order']]
    def null_frames():
        for roi in session.inputs['rois']:
            arrays={};orders={}
            for m in catalog['model_order']:
                row=receipts['null'][(m,roi)];need(row['schedule']==bare(encoded(schedule)),'one exact shared null schedule')
                a=read_values(row);need(np.isfinite(a).all(),'undefined source-null coverage cannot become a partial mean')
                arrays[m]=a;orders[m]=[x.replace('.','_') for x in row['layers']]
            for k in range(1000):
                b.check();yield roi,k,[(m,[(layer,float(arrays[m][orders[m].index(layer),k])) for layer in layers[m]]) for m in catalog['model_order']]
    if undefined:
        inference={'status':'required_unscorable','gate':'G11','undefined_coverage':undefined,'note':'Original finite-only reviewed consumer refuses; all observed records retained, no partial cohort result.'}
    else:inference=legacy.main_inference(mods,protocol_raw,inventory_raw,graph_raw,schedule,observed_frames(),null_frames(),session.inputs['consumer_limits']['inference'])
    dimensions={}
    for branch in ('figure16','figure17'):
        run=legacy.dimension_run_binding(branch,protocol,catalog,graph,session.inputs,receipts,bare(protocol_raw))
        panel='test' if branch=='figure16' else 'train';folders=run['comparison_folders']+[run['base_folder']]
        ids=scope['main92'] if branch=='figure16' else scope['training_figure17_51']
        def frames():
            for roi in session.inputs['rois']:
                out=[]
                for m in ids:
                    for folder in folders:
                        method={'models':'srp','models_pca_rerun':'pca','models_no_dimred':'none'}[folder] if branch=='figure16' else 'pca'
                        values=selected_values(f'{panel}:{method}:{m}',roi)
                        means=[]
                        for name,v in values:
                            if not all(np.isfinite(x) for x in v):raise Unscorable('G11','Undefined dimension-branch input retained; consumer cannot drop it')
                            means.append((name,sum(v)/10))
                        out.append((m,folder,means))
                yield roi,out,receipts['rsa'][(f'{panel}:pca:{ids[0]}',roi)]['noise_ceilings']
        dimensions[branch]=legacy.dimension_consume(mods,branch,protocol_raw,inventory_raw,graph_raw,run,frames(),session.inputs['consumer_limits']['dimension'])
    numerical=load_numerical(package);auxiliary={}
    b.charge('work',session.inputs['numerical_limits']['work'])
    nb=numerical.Budget(max_work=session.inputs['numerical_limits']['work'],max_elements=session.inputs['numerical_limits']['elements'],deadline_ns=b.deadline_ns)
    for roi in session.inputs['rois']:
        observed={};null={};chosen={}
        for m in ('videomae_B','videomae_B_pretrainONLY'):
            records=selected_values('test:pca:'+m,roi);values=finite_json([x for _,x in records])
            summary=numerical.source_layer_summary(values,budget=nb);chosen[m]=summary
            observed[m]=summary['observed_max_mean'];row=receipts['null'][(m,roi)];a=read_values(row)
            if summary['selected_layer_index'] is None:null[m]=[None]*1000
            else:
                selected_name=records[summary['selected_layer_index']][0];names=[x.replace('.','_') for x in row['layers']];null[m]=finite_json(a[names.index(selected_name),:].tolist())
        auxiliary[roi]={'selection':chosen,'inference':numerical.source_group_inference((('videomae_B',('videomae_B',)),('videomae_B_pretrainONLY',('videomae_B_pretrainONLY',))),observed,null,budget=nb)}
    appendix,depth,complexity=native_appendix(session,package,protocol,selections,receipts,selected_values,publisher)
    result={'inference':inference,'dimension16':dimensions['figure16'],'dimension17':dimensions['figure17'],'selections':selections,'depth':depth,'rankings':ranked,'complexity':complexity,'scaled':scaled,'auxiliary18':auxiliary}
    figures=endpoints.figure_records(scope,result,appendix)
    from .render import render_bound
    rendering=render_bound(session,session.inputs['render_calls'],protocol,receipts,selected_values,publisher)
    main=publisher.write('numerical_results.json',encoded(finite_json(result)));app=publisher.write('appendix_results.json',encoded(finite_json(appendix)))
    from .scope import condition_rows
    submission_rows=[]
    for condition in condition_rows(scope):
        for roi in session.inputs['rois']:
            records=selected_values(condition['id'],roi)
            submission_rows.append({'condition':condition['id'],'roi':roi,'layers':[k for k,v in records],'values':finite_json([v for k,v in records])})
    figure_data=[]
    for figure in figures['figures']:
        figure_data.append({'figure':figure['figure'],'status':figure['status'],'data':{key:scope if key=='scope' else appendix[key] if key.startswith('F') else result[key] for key in figure['families']}})
    from .projection import scientific_figures,scientific_support
    custody={'schema':'hundred_models_own_run_custody_v1','inputs':bare(encoded(session.inputs)),'plan':session.authority['plan'],'runtime_source':session.authority['source'],'environment':{k:session.inputs['environment'][k] for k in ('bytes','sha256')},'source_workspace':str(publisher.root),'raw_endpoint_records':bare(encoded(finite_json({'result':result,'appendix':appendix})))}
    submission=publisher.write('submission.json',encoded(finite_json({'schema':'hundred_models_submission_v2','scope':bare(encoded(scope)),'subjects':scope['subjects'],'scientific_support':scientific_support(scope,session.inputs),'rsa':submission_rows,'figures':scientific_figures(finite_json(figure_data)),'tables':figures['tables'],'custody':custody})))
    return {'schema':'hundred_models_complete_consumer_receipt_v1','graph':graph_desc,'catalog':catalog_desc,'numerical_results':main,'appendix_results':app,'submission':submission,'figure_manifest':figures,'rendering':rendering,'source_completion':'required_unscorable' if undefined or any(v.get('status')=='required_unscorable' for v in appendix.values()) or any(v.get('status')=='required_unscorable' for v in rendering) else 'complete_source_outputs','all20_empirical_gates_remain_open':True,'scientific_qualification':False}

def native_appendix(session,package,protocol,selections,receipts,selected_values,publisher):
    """Run exact known source transforms and explicitly source-bound remaining callers.

    Arbitrary callable names or source supplied by a candidate are never executed.
    Unknown historical invocations remain required-unscorable.
    """
    b=session.budget;np=session.np;inputs=session.inputs;rows=[]
    for roi in inputs['rois']:
        for m in protocol['models']:
            for index,(layer,values) in enumerate(selected_values('test:pca:'+m['id'],roi)):
                rows.append({'ROI':roi,'Model':m['id'],'ModelType':m['type'],'ArchType':m['architecture'],'Layer':index,'Layer_FullNames':layer,'R':finite_json(float(np.mean(values))),'R_array':finite_json(values),'ModelParams':m['config'].get('params'),'ModelFlops':m['config'].get('flops'),'ModelAccuracy':m['config'].get('accuracy')})
    mods=legacy.modules(package)
    depth=depth_production.comparisons(mods,rows,inputs['rois'],inputs['consumer_limits']['dimension']['depth'])
    complexity={}
    for roi in inputs['rois']:
        selected=[m for m in protocol['models'] if m['type']=='video-k400'];fields={}
        for field in ('flops','params','accuracy'):
            x=[m['config'].get(field) for m in selected];y=[selections[roi][m['id']].get('R') for m in selected]
            if any(v is None for v in x+y):fields[field]={'status':'required_unscorable','missing_or_undefined':True,'model_order':[m['id'] for m in selected]}
            else:
                b.charge('work',len(x));correlation,pvalue=session.stats.pearsonr(x,y);fields[field]={'x':x,'y':y,'model_order':[m['id'] for m in selected],'pearson_r':float(correlation),'source_pvalue':float(pvalue)}
        complexity[roi]=fields
    appendix={}
    for key,desc in inputs['appendix_calls'].items():
        call=strict(capture(session.root,desc,b))
        if call.get('historical_caller_resolved') is not True:
            appendix[key]={'status':'required_unscorable','gate':'G12','admitted_call':desc,'reason':'Exact historical filter/highlight/top-depth/call identity is unresolved.'};continue
        need(call['schema']=='hundred_models_closed_appendix_call_v1' and call['figure']==key,'closed appendix call ABI')
        # Source-resolved numerical data routes; renderer invocation is a separate native function.
        if key in ('F15','F19','F20'):
            ids=call['models'];rois=call['rois'];need(set(ids)<=set(m['id'] for m in protocol['models'][:92]) and set(rois)<=set(inputs['rois']),'source-bound appendix subsets')
            appendix[key]={'status':'source_output_unqualified','call':desc,'records':[x for x in rows if x['Model'] in ids and x['ROI'] in rois],'highlight_models':call['highlight_models'],'depth_data':{roi:depth_production.grouped(mods,[r for r in rows if r['ROI']==roi],tuple((g['label'],tuple(g['models'])) for g in call['depth_groups']),inputs['consumer_limits']['dimension']['depth']) for roi in rois},'historical_rendering_qualified':False}
        elif key=='F21':
            need(call['analysis']=='pearson_best_layer' and call['fields']==['params','accuracy'],'resolved supported F21 estimands')
            selected=[m for m in protocol['models'] if m['id'] in call['models']]
            need([m['id'] for m in selected]==call['models'],'complete frozen F21 model order')
            records={}
            for roi in call['rois']:
                need(roi in inputs['rois'],'F21 source ROI')
                records[roi]={}
                for field in call['fields']:
                    x=[m['config'].get(field) for m in selected];y=[selections[roi][m['id']].get('R') for m in selected]
                    need(len(x)>=3 and None not in x+y,'complete finite F21 support')
                    r,p=session.stats.pearsonr(x,y);records[roi][field]={'models':call['models'],'x':x,'y':y,'r':float(r),'p':float(p)}
            appendix[key]={'status':'source_output_unqualified','call':desc,'records':records,'historical_rendering_qualified':False}
        else:
            # F22 needs an explicit source-evidenced top-layer depth definition, not guessed interpolation.
            if call.get('depth_definition')!='source_adjusted_layer_before_group_summary':raise Unscorable('G12','F22 depth definition is not the implemented source-domain route')
            result={}
            for roi in call['rois']:
                data=[]
                for group in depth_production.grouped(mods,[r for r in rows if r['ROI']==roi],tuple((g['label'],tuple(g['models'])) for g in call['depth_groups']),inputs['consumer_limits']['dimension']['depth']):
                    table=group['normalized']['table'];cols=[x['name'] for x in table['columns']];ix={k:cols.index(k) for k in ('Model','Layer','R')}
                    for m in call['models']:
                        subset=[x for x in table['rows'] if x[ix['Model']]==m]
                        if not subset:continue
                        best=max(subset,key=lambda x:x[ix['R']]);meta=next(x for x in protocol['models'] if x['id']==m)
                        data.append({'model':m,'depth':best[ix['Layer']],'params':meta['config'].get('params')})
                need({x['model'] for x in data}==set(call['models']),'complete CNN preferred-depth support')
                x=[v['params'] for v in data];y=[v['depth'] for v in data]
                if None in x:raise Unscorable('G12','Missing parameters in F22 model roster')
                r,p=session.stats.pearsonr(x,y);result[roi]={'records':data,'r':float(r),'p':float(p)}
            appendix[key]={'status':'source_output_unqualified','call':desc,'regions':result,'historical_rendering_qualified':False}
    return appendix,depth,complexity
