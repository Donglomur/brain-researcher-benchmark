"""Selected late-target grading with one shared complete-ten-seed domain."""
from dataclasses import dataclass
from .contracts import need,CONTRASTS
from .policy import panel_name
from .outputs import Disposition
from .target_barrier import admit
from .scoring import joined_losses,session_contrasts,reduce_common,sign_interval_and_p,holm_family,arm_window_means

@dataclass(frozen=True)
class ProtectedAxisJoin:
    output:object
    public_window:object
    target_window:object
    window_index:int
    axis:tuple

def score(prepared_public,production,late_host,owner):
    from .admission import require_native
    require_native('independent production closure and late protected target issuer',late_host,owner)
    try:return _score(prepared_public,production,late_host,owner)
    except BaseException as error:
        try:owner.fail(error)
        except BaseException as secondary:raise BaseExceptionGroup('grading and owner failure',[error,secondary])
        raise

def _score(prepared_public,production,late_host,owner):
    access=admit(production,late_host,owner)
    need(prepared_public['catalogue'] is production.catalogue,'same public preparation catalogue')
    private=access.capture(owner)
    return _score_targets(prepared_public,access,private,owner)

def target_joins(prepared,access,private,owner):
    """Validate every complete output, even where a different operand excludes a session."""
    import numpy as np
    access.validate();cat=access.production.catalogue
    need(set(private)==set(cat.evaluation),'exact late selected evaluation target projection')
    need(prepared['catalogue'] is cat,'same public preparation producer')
    joins={}
    for row in access.seal:
        if row.status is not Disposition.COMPLETE:continue
        sid=row.key.session;head=row.key.cell[0]
        target_rows=private[sid]['targets'][head];public_rows=prepared['public'][sid]['windows'][head]
        predictions=row.body['windows']
        need(len(target_rows)==len(public_rows)==len(predictions) and len(public_rows)>0,'full target/public/output window inverse')
        items=[]
        for i,(target,public,predicted) in enumerate(zip(target_rows,public_rows,predictions,strict=True)):
            owner.tick()
            need(target['query']==public['query']==predicted['query'],'exact original query order')
            mask=np.asarray(target['mask']);values=np.asarray(target['values']);p=np.asarray(predicted['values'])
            need(mask.dtype.kind=='b' and mask.shape==values.shape==p.shape and values.ndim==1,'full original value/mask/prediction extent')
            need(np.array_equal(mask,public['mask']) and len(values)==len(public['target_times']),'exact protected/public mask and time inverse')
            need(mask.any() and np.isfinite(values[mask]).all() and np.isfinite(p[mask]).all(),'finite actual scored support')
            axis=(public['query'],tuple(float(t) for t in public['target_times']),tuple(bool(v) for v in mask))
            items.append(ProtectedAxisJoin(row,public,target,i,axis))
        joins[row.key]=tuple(items)
    need(set(joins)=={r.key for r in access.seal if r.status is Disposition.COMPLETE},'no supplied or omitted target join')
    return joins

def _score_targets(prepared,access,private,owner):
    import numpy as np
    access.validate();cat=access.production.catalogue;support=access.support
    joins=target_joins(prepared,access,private,owner)
    rows={r.key:r for r in access.seal}
    supports={(s.region,s.session):s for s in support.sessions}
    panels=('REFERENCE',)+tuple(panel_name(p) for p in cat.policy.panels)
    all_records={};all_aggregates={}
    from .catalogue import OutputKey,exploratory_catalogue,sensitivity_catalogue
    for panel in panels:
        arms=cat.required_arms(panel)
        contrasts=CONTRASTS if panel=='REFERENCE' else (CONTRASTS[0],)
        records=[]
        for cell in cat.cells:
            head,region,k,seed,real=cell
            for sid,animal in cat.session_animals:
                owner.tick();ss=supports[region,sid]
                meta={'session':sid,'animal':animal,'panel':panel,'head':head,'region':region,
                      'budget':k,'match_seed':seed,'realization':real,'support':ss,'status':ss.status.value}
                if ss.status is not Disposition.COMPLETE:
                    records.append({**meta,'values':None,'arm_losses':None,'causes':ss.causes});continue
                keys={a:OutputKey(panel,cell,sid,a) for a in arms}
                need(all(rows[keys[a]].status is Disposition.COMPLETE for a in arms),'all selected operands in common domain')
                window_losses=[]
                for i in range(len(joins[keys[arms[0]]])):
                    j=joins[keys[arms[0]]][i];target=j.target_window;public=j.public_window
                    need(all(joins[keys[a]][i].target_window is target and joins[keys[a]][i].public_window is public
                             and joins[keys[a]][i].axis==j.axis for a in arms),'same original protected target for every paired arm')
                    ids=tuple((public['query'],n) for n in range(len(target['values'])))
                    canonical={'ids':ids,'axis':j.axis,'mask':target['mask'],'values':target['values']}
                    predictions={a:{'ids':ids,'target_axis':j.axis,'values':rows[keys[a]].body['windows'][i]['values']} for a in arms}
                    window_losses.append(joined_losses(canonical,predictions,head,arms))
                records.append({**meta,'values':session_contrasts(window_losses,contrasts),
                                'arm_losses':arm_window_means(window_losses,arms)})
        all_records[panel]=tuple(records)
        for region in cat.regions:
            result=reduce_common([r for r in records if r['region']==region],support,region,panel,tuple(c[0] for c in contrasts))
            # Primary significance is reference-only; candidate effects are descriptive.
            if panel=='REFERENCE':
                result['inference']={'replacement':sign_interval_and_p([v['replacement'] for v in result['animals'].values()])}
            all_aggregates[panel,cat.policy.head,region,10,'anatomy']=result
    primary_keys=tuple(('REFERENCE',cat.policy.head,r,10,'anatomy','replacement') for r in cat.regions)
    pvalues={key:all_aggregates[key[:-1]]['inference']['replacement']['p'] for key in primary_keys}
    primary=holm_family(pvalues,primary_keys)
    indexed={p:{(r['region'],r['session'],r['match_seed']):r for r in records} for p,records in all_records.items()}
    competence={}
    for panel in panels[1:]:
        records=paired_records(indexed,panel,'REFERENCE',support,'competence')
        competence[panel]={region:reduce_common([r for r in records if r['region']==region],support,region,'competence:'+panel,('BR_improvement','BC_improvement','candidate_BR_loss','candidate_BC_loss','reference_BR_loss','reference_BC_loss')) for region in cat.regions}
    # Predeclared paired secondary mode/tool contrasts. No outcome-selected pairs.
    contrasts={}
    for left,right,kind in comparison_pairs(cat.policy.panels):
        records=paired_records(indexed,panel_name(left),panel_name(right),support,kind)
        label=kind+':'+panel_name(left)+'-'+panel_name(right)
        contrasts[label]={region:reduce_common([r for r in records if r['region']==region],support,region,label,('BR_loss_difference','BC_loss_difference','replacement_difference')) for region in cat.regions}
    return {'task':'NEURAL-061','policy':cat.policy,'session_records':all_records,'animal_aggregates':all_aggregates,
            'primary_family':primary,'paired_reference_loss_improvement':competence,'secondary_mode_tool_contrasts':contrasts,
            'support':support,'coverage':support.coverage(),'protected_axis_joins':joins,
            'sensitivity_catalogue':sensitivity_catalogue(cat),'exploratory_catalogue':exploratory_catalogue(cat),
            'tier':cat.policy.tier.value,'comparison_claim':'programme construction and competence only' if len(cat.policy.panels)==1 else 'selected paired secondary modes/tools; no confirmatory expansion',
            'family_policy':'R-region six-arm-reference replacement primary; all optional full sensitivity/exploratory work explicitly NOT_SELECTED.',
            'scientific_qualification':False,'causal_claim':False,'sota_claim':False,
            'exposure':'public development; preparation handles protected targets; later server withholding is not historical privacy',
            'grading_cost':owner.snapshot()}

def comparison_pairs(panels):
    pairs=[]
    for panel in panels:
        mode,tool,repeat=panel
        if mode=='I' and ('F',tool,repeat) in panels:pairs.append((panel,('F',tool,repeat),'mode'))
        if tool=='T1' and (mode,'T0',repeat) in panels:pairs.append((panel,(mode,'T0',repeat),'tool'))
    return tuple(pairs)

def paired_records(indexed,left,right,support,kind):
    """Source arithmetic called only after both operands used the same support."""
    rows=[];cat=support.collection.catalogue
    label='competence:'+left if kind=='competence' else kind+':'+left+'-'+right
    for ss in support.sessions:
        for seed in cat.policy.seeds:
            key=(ss.region,ss.session,seed);a=indexed[left][key];b=indexed[right][key]
            need(a['support'] is b['support'] is ss and a['status']==b['status']==ss.status.value,'paired complete-ten-seed common parent')
            values=None
            if ss.status is Disposition.COMPLETE:
                la,lb=a['arm_losses'],b['arm_losses']
                if kind=='competence':
                    values={'BR_improvement':lb['BR']-la['BR'],'BC_improvement':lb['BC']-la['BC'],
                            'candidate_BR_loss':la['BR'],'candidate_BC_loss':la['BC'],'reference_BR_loss':lb['BR'],'reference_BC_loss':lb['BC']}
                else:
                    values={'BR_loss_difference':la['BR']-lb['BR'],'BC_loss_difference':la['BC']-lb['BC'],
                            'replacement_difference':a['values']['replacement']-b['values']['replacement']}
            rows.append({'panel':label,'region':ss.region,'session':ss.session,'animal':ss.animal,'match_seed':seed,
                         'support':ss,'status':ss.status.value,'values':values})
    return tuple(rows)
