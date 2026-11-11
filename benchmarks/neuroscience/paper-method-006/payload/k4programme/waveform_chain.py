"""Actual aligned waveform-bank composition; no inferred original-source authority.

The original release applies igood to wfs, wfs_x and contaminations together
(simulation.py 88--90). This prospective paper-method route carries all three
through the same row selection, plus the complete rejected-unit disposition.
Numerical kernels retain their V1 named conventions. Original arrays, geometry,
pyKilosort version, clocks and preprocessing still require qualified producers.
"""
from copy import deepcopy
import math
from .common import require, unique

RULES = ('literal-relative-squared-0.5', 'paper-euclidean-0.25')
LINEAGE = ('recording_id','source_version','clock_binding','whitening_binding')


def initial_support(source, unit_ids, channel_indices):
    require(source['source_sorter']=='pyKilosort' and all(
        type(source[k]) is str and source[k] for k in LINEAGE), 'original-source-lineage-open')
    units=source['units']; unique(units,'source_unit_id')
    require([r['source_unit_id'] for r in units]==list(unit_ids)
            and [r['channel_indices'] for r in units]==[list(c) for c in channel_indices],
            'original-unit-channel-order-mismatch')
    rows=[]
    for i,row in enumerate(units):
        require(type(row['channel_offset']) is int and 0<=row['channel_offset']<4,
                'unbound-original-channel-offset')
        c=row['contamination']
        require(type(c) in (int,float) and math.isfinite(c) and c>=0,
                'invalid-original-contamination')
        rows.append({'source_row':i,'source_unit_id':row['source_unit_id'],
                     'channel_indices':list(row['channel_indices']),
                     'channel_offset':row['channel_offset'],'contamination':c,
                     'count_status':'not-selected','variation_status':'not-evaluated'})
    return {'schema':'k4-waveform-support-v2','stage':'depth-means',
            **{k:source[k] for k in LINEAGE},'source_sorter':source['source_sorter'],
            'rows':rows,'active':list(range(len(rows))),'historical_equivalence':False,
            'native_and_authentic_lineage_qualified':False}


def check_support(support, stage, size):
    require(support['schema']=='k4-waveform-support-v2' and support['stage']==stage,
            'waveform-support-stage')
    require(support['source_sorter']=='pyKilosort' and all(
        type(support[k]) is str and support[k] for k in LINEAGE),'original-source-lineage-open')
    rows=support['rows']; unique(rows,'source_unit_id'); active=support['active']
    require([r['source_row'] for r in rows]==list(range(len(rows)))
            and all(type(i) is int and 0<=i<len(rows) for i in active)
            and active==sorted(set(active)) and len(active)==size,'waveform-row-alignment')
    for r in rows:
        c=r['channel_indices']
        require(type(c) is list and c and all(type(i) is int and i>=0 for i in c)
                and len(c)==len(set(c)),'waveform-channel-identity')
        require(type(r['channel_offset']) is int and 0<=r['channel_offset']<4
                and type(r['contamination']) in (int,float)
                and math.isfinite(r['contamination']) and r['contamination']>=0,
                'waveform-offset-contamination-identity')
    return rows,active


def waveform_depth_means(voltage,sample_indices,unit_indices,event_depths,*,source,
                         unit_ids,channel_indices,depth_edges,waveform_offsets,
                         edge_policy,count_boundary,budget):
    from .extraction import waveform_depth_means as kernel
    support=initial_support(source,unit_ids,channel_indices)
    result=kernel(voltage,sample_indices,unit_indices,event_depths,unit_ids,
                  channel_indices,depth_edges,waveform_offsets,edge_policy=edge_policy,
                  count_boundary=count_boundary,budget=budget)
    support['count_boundary']=count_boundary
    result['support']=support
    return result


def eligible_depth_selection(means,counts,*,support,minimum_count,boundary_rule,budget):
    import numpy as np
    rows,active=check_support(support,'depth-means',len(means))
    require(minimum_count==50 and boundary_rule in {'greater-than','greater-or-equal'},
            'unselected-waveform-count-boundary')
    expected='greater-than-50' if boundary_rule=='greater-than' else 'greater-or-equal-50'
    require(support['count_boundary']==expected,'count-producer-selector-rule-mismatch')
    require(means.ndim==4 and means.shape[1]==20 and counts.shape==means.shape[:2]
            and counts.dtype.kind in 'iu' and np.all(counts>=0),'depth-selection-support')
    selected=np.all(counts>50,axis=1) if boundary_rule=='greater-than' else np.all(counts>=50,axis=1)
    keep=[i for i,v in enumerate(selected.tolist()) if v]
    budget.charge('array',means.nbytes+counts.nbytes+selected.nbytes)
    out=deepcopy(support)
    for i,index in enumerate(active):
        out['rows'][index].update(count_status='accepted' if bool(selected[i]) else 'rejected',
                                  counts=counts[i].tolist())
    out.update(stage='count-selected',active=[active[i] for i in keep])
    # A zero-row recording remains represented and is never silently omitted.
    return {'means':means[keep].copy(),'support':out,'historical_equivalence':False}


def denoise_depth_waveforms(means,*,support,variation_rule,budget):
    import numpy as np
    from .extraction import denoise_depth_waveforms as kernel
    check_support(support,'count-selected',len(means))
    require(variation_rule in RULES,'unselected-depth-variation-rule')
    if len(means):
        result=kernel(means,variation_rule=variation_rule,budget=budget)
    else:
        require(means.ndim==4 and means.shape[1]==20 and means.shape[3]>4,
                'empty-depth-waveform-shape')
        result={'waveforms':means.copy(),'variation':np.empty((0,),dtype='float64'),
                'retained':np.empty((0,),dtype='bool'),'variation_rule':variation_rule,
                'historical_equivalence':False}
    out=deepcopy(support);out.update(stage='denoised',variation_rule=variation_rule)
    result['support']=out
    return result


def retained_depth_selection(waveforms,retained,variation,*,support,budget):
    """Apply the actual denoiser mask once to all aligned source coordinates."""
    import numpy as np
    rows,active=check_support(support,'denoised',len(waveforms))
    require(waveforms.ndim==4 and waveforms.shape[1]==20 and waveforms.shape[3]>4
            and retained.shape==variation.shape==(len(active),)
            and retained.dtype.kind=='b' and variation.dtype.kind in 'fi',
            'denoise-mask-support')
    rule=support['variation_rule'];require(rule in RULES,'unselected-depth-variation-rule')
    values=variation.tolist();flags=retained.tolist()
    require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in values),
            'nonfinite-depth-variation')
    expected=[v<.5 if rule==RULES[0] else v<=.25 for v in values]
    require(flags==expected,'denoiser-mask-rule-mismatch')
    keep=[i for i,flag in enumerate(flags) if flag]
    budget.charge('array',waveforms.nbytes+retained.nbytes+variation.nbytes)
    budget.charge('operations',len(active))
    out=deepcopy(support)
    for i,index in enumerate(active):
        out['rows'][index].update(variation=values[i],variation_rule=rule,
                                  variation_status='accepted' if flags[i] else 'rejected')
    out.update(stage='variation-selected',active=[active[i] for i in keep])
    # Indexing the same full rows carries channel_indices, offset, contamination
    # and recording/unit IDs. Rejected rows remain in support['rows'].
    return {'waveforms':waveforms[keep].copy(),'support':out,
            'historical_equivalence':False}


def kriging_depth_grid(waveforms,original_positions,target_positions,*,support,
                       geometry_classes,budget):
    import numpy as np
    from .extraction import kriging_depth_grid as kernel
    rows,active=check_support(support,'variation-selected',len(waveforms))
    require(geometry_classes==[0,1,2,3],'all-four-original-offset-classes-required')
    require(waveforms.ndim==4 and waveforms.shape[1]==20,'twenty-depths-required')
    n,d,t,c=waveforms.shape
    require(original_positions.shape==(4,d,c,2) and target_positions.shape==(4,d*100,c,2),
            'class-specific-ups100-position-support')
    require(all(rows[i]['count_status']=='accepted' and rows[i]['variation_status']=='accepted'
                and len(rows[i]['channel_indices'])==c for i in active),
            'unselected-unit-before-kriging')
    require(np.all(np.isfinite(original_positions)) and np.all(np.isfinite(target_positions)),
            'nonfinite-probe-geometry')
    budget.charge('array',n*d*100*t*c*8+waveforms.nbytes)
    result=np.empty((n,d*100,t,c),dtype='float64')
    for offset in geometry_classes:
        indexes=[j for j,i in enumerate(active) if rows[i]['channel_offset']==offset]
        if indexes:
            result[indexes]=kernel(waveforms[indexes],original_positions[offset],
                                   target_positions[offset],budget=budget)
    out=deepcopy(support);out.update(stage='kriged',geometry_classes=list(geometry_classes))
    return {'waveforms':result,'support':out,'historical_equivalence':False}


def assemble_eleven(arrays,supports,isi_records,expected_recording_ids,*,budget,
                    expected_waveforms=597,expected_isi_sources=1497):
    """Concatenate actual kriging outputs; count mismatch is unavailable, never padding."""
    import numpy as np
    require(type(expected_waveforms) is int and expected_waveforms==597
            and type(expected_isi_sources) is int and expected_isi_sources==1497,
            'full-original-bank-counts-required')
    require(len(expected_recording_ids)==len(set(expected_recording_ids))==11
            and len(arrays)==len(supports)==11,'eleven-original-recordings-required')
    isi=unique(isi_records,'recording_id')
    require(set(isi)==set(expected_recording_ids),'incomplete-ISI-recording-roster')
    waveform_rows=[];isi_rows=[];dispositions=[];rules=set();boundaries=set()
    for recording,a,s in zip(expected_recording_ids,arrays,supports):
        rows,active=check_support(s,'kriged',len(a))
        require(s['recording_id']==recording,'bank-recording-order-mismatch')
        require(a.ndim==4 and a.shape[1]==2000,'complete-kriging-grid-required')
        require(isi[recording]['source_sorter']=='pyKilosort' and all(
            isi[recording][k]==s[k] for k in LINEAGE),'ISI-waveform-source-lineage-mismatch')
        source_isi=unique(isi[recording]['isi_sources'],'source_unit_id')
        for unit in source_isi.values():
            # ISI source eligibility is independent of waveform variation/counts.
            isi_rows.append({'recording_id':recording,**unit})
        for j,i in enumerate(active):
            require(rows[i]['count_status']==rows[i]['variation_status']=='accepted',
                    'rejected-unit-in-bank')
            waveform_rows.append({'recording_id':recording,'array_row':len(waveform_rows),
                                  'recording_array_row':j,**deepcopy(rows[i])})
        dispositions.append(deepcopy(s));rules.add(s['variation_rule']);boundaries.add(s['count_boundary'])
    require(len(rules)==len(boundaries)==1,'mixed-bank-method-rules')
    observed={'waveforms':len(waveform_rows),'isi_sources':len(isi_rows)}
    require(observed=={'waveforms':597,'isi_sources':1497},'original-source-count-mismatch',
            {'observed':observed,'complete_recording_dispositions':dispositions})
    require(len({a.shape[1:] for a in arrays})==1,'incompatible-waveform-grid-support')
    budget.charge('array',sum(a.nbytes for a in arrays))
    waveform_array=np.concatenate(arrays,axis=0)
    return {'waveforms':waveform_array,'waveform_rows':waveform_rows,'isi_sources':isi_rows,
            'recording_dispositions':dispositions,'variation_rule':next(iter(rules)),
            'count_boundary':next(iter(boundaries)),'historical_equivalence':False,
            'native_and_authentic_lineage_qualified':False}


def validate_waveform_edges(job,jobs):
    """Bind paired operands to real same-job outputs before any operand read.

    This enforces source composition, not authentic scientific qualification.
    The actual Programme resolver subsequently verifies returned output custody.
    """
    operation=job.get('operation')
    chain={'eligible_depth_selection':('waveform_depth_means',('means','counts','support')),
           'denoise_depth_waveforms':('eligible_depth_selection',('means','support')),
           'retained_depth_selection':('denoise_depth_waveforms',('waveforms','retained','variation','support')),
           'kriging_depth_grid':('retained_depth_selection',('waveforms','support'))}
    def parent(roles,expected):
        identities=[]
        for input_role,result_role in roles:
            binding=job['inputs'].get(input_role,{})
            require(binding.get('source')=='job' and binding.get('job_id') in jobs,
                    'waveform-edge-requires-actual-producer',input_role)
            key=binding['job_id'];upstream=jobs[key]
            require(key in job['depends_on'] and upstream.get('operation')==expected
                    and binding.get('result_path')==[result_role],
                    'waveform-producer-role-mismatch',input_role)
            identities.append(key)
        require(len(set(identities))==1,'waveform-operands-from-different-producers')
        return identities[0]
    if operation in chain:
        expected,roles=chain[operation];parent([(r,r) for r in roles],expected)
    if operation=='eleven_source_join':
        parents=[parent([(f'waveforms_{i:02}','waveforms'),(f'support_{i:02}','support')],
                        'kriging_depth_grid') for i in range(11)]
        require(len(set(parents))==11,'eleven-distinct-waveform-producers-required')


def build_waveform_jobs(recordings,*,prefix,family,variation_rule,count_boundary,
                        isi_binding,isi_dependencies):
    """Construct all 56 concrete jobs, to be included in the full 121-obligation plan.

    Each recording supplies original raw/source/geometry bindings and explicit
    depth/time/edge parameters. This does not select authentic roots or assert
    the existence of the independently constructed 1497-source ISI population.
    """
    require(type(prefix) is str and prefix and family in {f'G{i:02}' for i in range(1,23)},
            'waveform-job-namespace')
    require(len(recordings)==11,'eleven-original-recordings-required')
    unique(recordings,'recording_id')
    require(variation_rule in RULES and count_boundary in
            {'greater-than-50','greater-or-equal-50'},'unselected-waveform-method-rule')
    jobs=[];kriging_ids=[]
    def edge(key,field):return {'source':'job','job_id':key,'result_path':[field]}
    def add(key,operation,dependencies,inputs,parameters):
        jobs.append({'id':key,'family':family,'status':'concrete-consumer',
                     'operation':operation,'depends_on':list(dependencies),
                     'inputs':deepcopy(inputs),'parameters':deepcopy(parameters)})
    for i,record in enumerate(recordings):
        key=f'{prefix}-{i:02}';initial=record['inputs'];parameters=record['parameters']
        require(set(initial)=={'voltage','sample_indices','unit_indices','event_depths','source'},
                'raw-waveform-operands')
        require(set(parameters)=={'unit_ids','channel_indices','depth_edges','waveform_offsets','edge_policy'},
                'explicit-original-waveform-parameters')
        add(key+'-means','waveform_depth_means',record['depends_on'],initial,
            {**parameters,'count_boundary':count_boundary})
        add(key+'-count','eligible_depth_selection',[key+'-means'],
            {r:edge(key+'-means',r) for r in ('means','counts','support')},
            {'minimum_count':50,'boundary_rule':'greater-than' if count_boundary=='greater-than-50' else 'greater-or-equal'})
        add(key+'-denoise','denoise_depth_waveforms',[key+'-count'],
            {r:edge(key+'-count',r) for r in ('means','support')},{'variation_rule':variation_rule})
        add(key+'-retained','retained_depth_selection',[key+'-denoise'],
            {r:edge(key+'-denoise',r) for r in ('waveforms','retained','variation','support')},{})
        require(set(record['geometry_inputs'])=={'original_positions','target_positions'},
                'original-offset-class-geometry-required')
        add(key+'-kriging','kriging_depth_grid',[key+'-retained',*record['geometry_dependencies']],
            {**{r:edge(key+'-retained',r) for r in ('waveforms','support')},**record['geometry_inputs']},
            {'geometry_classes':[0,1,2,3]})
        kriging_ids.append(key+'-kriging')
    inputs={'isi_records':deepcopy(isi_binding)}
    for i,key in enumerate(kriging_ids):
        inputs[f'waveforms_{i:02}']=edge(key,'waveforms');inputs[f'support_{i:02}']=edge(key,'support')
    add(prefix+'-bank','eleven_source_join',kriging_ids+list(isi_dependencies),inputs,
        {'expected_recording_ids':[r['recording_id'] for r in recordings],
         'expected_waveforms':597,'expected_isi_sources':1497})
    keyed=unique(jobs,'id')
    for job in jobs:validate_waveform_edges(job,keyed)
    return jobs
