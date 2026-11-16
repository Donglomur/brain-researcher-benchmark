"""Actual original hierarchy/window materializer and separate public/private projections."""
from dataclasses import asdict
from .contracts import need,cohort,HEADS,catalogue,ARMS,canonical,atlas,ScientificUnavailable
from .native_projection import joined_units,project_windows
from .matching import select

def prepare(originals,cohort_rows,ontology,owner,opaque,selected=None,plan=None):
    from .admission import require_native
    require_native('same-open original preparation and protected target projection',originals,owner)
    try:return _prepare(originals,cohort_rows,ontology,owner,opaque,selected,plan)
    except BaseException as error:owner.fail(error);raise

def _prepare(originals,cohort_rows,ontology,owner,opaque,selected=None,plan=None):
    """originals is a trusted same-open capture context, specified in NATIVE_CONTRACT.

    Each yielded Data object is consumed while its original descriptor is live.
    opaque allocates aliases from a fixed operator table before any outcome reads;
    it may not encode labels or use random aliases to choose reduction ordering.
    """
    from .policy import policy
    from .catalogue import build
    selected=policy() if selected is None else selected
    selected.require_selected()
    if plan is not None:
        plan.validate()
        need(plan.original_cohort==tuple(cohort_rows) and plan.original_ontology is ontology and plan.aliases is opaque and plan.catalogue.policy is selected,'earlier actual planning inputs retained')
    roles=cohort(cohort_rows);atlas_doc=atlas(ontology);regions=atlas_doc['grey_regions']
    catalogue(regions) # Validate the complete ontology, without choosing regions on outcomes.
    cells=tuple((selected.head,r,selected.budget,s,selected.realization) for r in regions for s in selected.seeds)
    public={};private={};census=[]
    for ordinal,row in enumerate(cohort_rows):
        owner.tick();sid=opaque.session(row['session']);aid=opaque.animal(row['animal'])
        with originals.capture(row['session'],owner) as captured:
            data=captured.data
            # Rate estimation uses only unlabeled, originally separate training domain.
            rate_domain=getattr(data,'pretrain_train_domain' if row['role']=='source' else 'ts1_train_domain')
            unit_rows,rate_census=joined_units(data,row,atlas_doc['regions'],rate_domain,owner.tick)
            windows={};targets={};head_status={}
            for head in (selected.head,):
                try:original=project_windows(data,row['role'],head,owner.tick)
                except ScientificUnavailable as error:
                    windows[head]=();targets[head]=();head_status[head]={'status':'unavailable','reason':error.reason,'details':error.details};continue
                except ValueError as error:
                    # No caught scientific failure is called an exclusion. Required producer
                    # failures abort preparation; eligible empty heads need explicit admission.
                    owner.fail(error);raise
                projected=[];protected=[]
                for w in original:
                    query=opaque.query(row['session'],head,w['window_ordinal'])
                    common={k:v for k,v in w.items() if k not in ('values','original_trial','original_a0','original_interval','task_origin')}
                    common['query']=query;common['session']=sid;common['animal']=aid
                    projected.append(common)
                    protected.append({'query':query,'values':w['values'],'mask':w['mask'],
                                      'original_trial':w['original_trial'],'original_interval':w['original_interval'],
                                      'original_a0':w['original_a0'],'task_origin':w['task_origin']})
                    if row['role']=='source':common['values']=w['values']
                windows[head]=tuple(projected);targets[head]=tuple(protected);head_status[head]='complete'
            assignments={};private_assignments={}
            for head,region,k,seed,realization in cells:
                # Identical biological matching across heads: cache repeats explicitly.
                key=(region,k,seed,realization)
                if key not in assignments:
                    original_assignment=select(unit_rows,region,k,seed,realization,regions)
                    private_assignments[key]=original_assignment
                    # Original probe/session identities and rate values stay operator-only.
                    assignments[key]={f:original_assignment[f] for f in ('status','region','budget','seed','realization')}
                    assignments[key]['session']=sid
                    if original_assignment['status']=='complete':assignments[key]['arms']=original_assignment['arms']
                    else:assignments[key].update(reason=original_assignment['reason'],required=k,available=original_assignment['available'])
            public[sid]={'session':sid,'animal':aid,'ordinal':ordinal,'role':row['role'],'fold':row['fold'],
                         'windows':windows,'head_status':head_status,'assignments':assignments,
                         'unit_axis':tuple({'index':u.index,'opaque_unit':opaque.unit(row['session'],u.index)} for u in unit_rows)}
            private[sid]={'targets':targets,'original_units':tuple(asdict(u) for u in unit_rows),
                          'original_session':row,'rate_census':rate_census,'capture':captured.identity,'assignments':private_assignments}
            census.append({'session':sid,'ordinal':ordinal,'head_status':head_status,'original_capture':captured.identity})
            owner.tick()
    need(len(public)==452 and len(private)==452,'complete corpus before publication')
    study=build(selected,regions,public)
    need(study.cells==cells,'actual preparation and selected catalogue inverse')
    if plan is not None:
        need(study==plan.catalogue,'same actual prepared cohort/cell/output inverse as earlier plan')
        study=plan.catalogue
    return {'public':public,'private':private,'census':tuple(census),'ontology':regions,'atlas':atlas_doc,
            'cells':cells,'catalogue':study,'policy':selected,'cost':owner.snapshot()}

def session_view(prepared,sid,cell,arm,training):
    need(arm in ARMS,'fixed neural arm');head,region,k,seed,realization=cell
    s=prepared['public'][sid];assignment=s['assignments'][region,k,seed,realization]
    if s['head_status'][head]!='complete':return {'status':'unavailable','disposition':s['head_status'][head]}
    if assignment['status']!='complete':return {'status':'unavailable','disposition':assignment}
    need(training==(s['role']=='source'),'source-label exposure boundary')
    windows=[];selected=assignment['arms'][arm]
    import numpy as np
    for w in s['windows'][head]:
        # Full source events are never handed to candidate and then "masked" by a hint.
        keep=np.isin(w['spike_units'],selected)
        inverse={old:new for new,old in enumerate(selected)}
        row={k:v for k,v in w.items() if k not in ('spike_units','spike_times','values')}
        row['spike_times']=np.array(w['spike_times'][keep],copy=True)
        row['spike_units']=np.array([inverse[int(x)] for x in w['spike_units'][keep]],dtype=np.int64)
        row['unit_count']=len(selected)
        if training:row['values']=np.array(w['values'],copy=True)
        windows.append(row)
    return {'status':'complete','session':sid,'animal':s['animal'],'ordinal':s['ordinal'],
            'fold':s['fold'],'head':head,'windows':tuple(windows),'arm':arm,'cell':cell}
