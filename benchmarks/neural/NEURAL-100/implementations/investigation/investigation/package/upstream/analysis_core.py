"""New released-panel cortical latency investigation; NOT paper reconstruction.

Pure array functions: no files, data acquisition, models, or fitting. The caller
must authenticate 47 recordings, 41 participants, source areas and unit/contact
assignments, and the unresolved absolute click-time alignment. Counts have shape
(trials, units, 100): unsmoothed 1-ms bins with edges [-50,50) ms. All normalized
source units are retained. The primary uses L4/L6 labels exactly as released,
even when different contacts at the same depth have different labels.

Even ZERO-BASED trial indices are test; odd indices are development. Primary
population rate is mean count per unit/trial divided by bin width in seconds.
Baseline is [-50,-5) ms; its sample SD (ddof=1) is over population time bins.
Onset is the left edge of the first run strictly above mean+3*SD in [1,50) ms
lasting at least 2 ms. Zero SD and absent crossing are undefined, not zero.
The 2-ms-bin control retains the same physical 2-ms persistence; only complete
bins contained in the stated baseline/search interval are used.

Controls are fixed, jointly reported, and not selected for favorable results:
2.5/3.5-SD thresholds; 2-ms bins; one-depth boundary erosion; baseline pseudo
onset (baseline [-50,-30), search [-25,0), latency relative to -25 ms); and
development-only SNR-bin/contact-count matching. Matching pairs L4/L6 contacts
within EXACT (number of assigned units, floor(SNR/0.5)) strata. SNR is the
development population mean in [1,20) minus baseline mean, divided by baseline
SD. It is coarse SNR-bin matching, NOT exact SNR, firing-rate, or biological
matching. Unsupported strata are counted, never relabeled as successful matches.

Boundary erosion removes a target contact if any differently labeled cortical
or outside contact is within one unique recorded depth rank. It does not impose
a consensus label or invent anatomical shifts at mixed-label depths. Alternative
first-spike medians are conditional on test trials with a spike in [1,50) ms;
they are descriptive and are NOT the Chase-Young significance estimator.

For every control, average all repeats within participant/area, then all recorded
participants equally. Any undefined repeat makes its participant undefined; any
undefined participant makes the full-area mean undefined. Observed-only means
are separate diagnostics. All areas use the SAME 1,000 union-participant draws,
PCG64 seed 100043, size 41. Any undefined draw withholds its 95% interval.
No success/sign threshold, causal interpretation, or manuscript-cohort identity
is asserted. The published 31/16 area counts do not match the released 39/8.
"""
import hashlib
import math
import numpy as np

SEED=100043
BOOTSTRAP_DRAWS=1000
AREAS=('A1','A2')
LAYERS=('L4','L6')
SOURCE_LAYERS={'L1','L23','L4','L5','L6','outside'}
CONDITIONS=('primary','threshold_2_5','threshold_3_5','bins_2ms',
            'boundary_erosion_one_depth','baseline_pseudo_onset',
            'development_snr_bin_contact_matched','first_spike_median_descriptive')


def _need(value,message):
    if not value:raise ValueError(message)


def _undefined(reason,**details):
    return {'status':'undefined','latency_ms':None,'reason':reason,**details}


def _validate_recording(record):
    required={'recording_id','participant_id','area','counts','unit_electrode_id','electrodes'}
    _need(type(record) is dict and set(record)==required,'exact normalized recording fields')
    for key in ('recording_id','participant_id'):
        _need(type(record[key]) is str and bool(record[key]),'nonempty source identity')
    _need(record['area'] in AREAS,'source A1/A2 area required')
    counts=np.asarray(record['counts'])
    _need(counts.ndim==3 and counts.shape[2]==100 and counts.dtype.kind in 'iuf',
          'counts must be trials x units x 100 numeric bins')
    _need(np.isfinite(counts).all() and (counts>=0).all() and (counts==np.floor(counts)).all()
          and (counts<=2**53).all(),'finite nonnegative exactly represented spike counts')
    electrodes=record['electrodes'];_need(type(electrodes) is list and electrodes,'complete electrode map')
    by_id={}
    for e in electrodes:
        _need(type(e) is dict and set(e)=={'electrode_id','depth_rank','layer'},'exact contact fields')
        key=e['electrode_id']
        _need(type(key) in (int,str) and (type(key) is int or bool(key)) and key not in by_id,
              'unique source contact identity')
        _need(type(e['depth_rank']) is int and e['depth_rank']>=0 and e['layer'] in SOURCE_LAYERS,
              'ordered physical depth rank and normalized source label')
        by_id[key]=e
    ranks=sorted({e['depth_rank'] for e in electrodes})
    _need(ranks==list(range(len(ranks))),'depth ranks must enumerate unique recorded depths without gaps')
    assigned=record['unit_electrode_id']
    _need(type(assigned) is list and len(assigned)==counts.shape[1], 'one source contact per unit')
    _need(all(type(k) in (int,str) and k in by_id for k in assigned),'every unit contact in source map')
    return counts.astype(np.float64,copy=False),by_id


def _indices(record,by_id,layer,contacts=None):
    return [i for i,k in enumerate(record['unit_electrode_id'])
            if by_id[k]['layer']==layer and (contacts is None or k in contacts)]


def _population(test_counts,indices,bin_ms):
    selected=test_counts[:,indices,:]
    # Mean first, then rebin counts and convert to spikes/second/unit.
    rate=selected.mean(axis=(0,1))
    if bin_ms==2:rate=rate.reshape(50,2).sum(axis=1)
    return rate*(1000/bin_ms)


def onset(test_counts,indices,threshold_sd=3.,bin_ms=1,baseline=(-50.,-5.),
          search=(1.,50.),time_origin=0.):
    """Pure fixed detector, on already validated counts and selected unit rows."""
    _need(bin_ms in (1,2) and threshold_sd in (2.5,3.,3.5),'fixed detector settings')
    if test_counts.shape[0]==0:return _undefined('no_test_trials',units=len(indices))
    if not indices:return _undefined('no_target_layer_units',units=0)
    rate=_population(test_counts,indices,bin_ms)
    left=np.arange(-50,50,bin_ms,dtype=float);right=left+bin_ms
    before=(left>=baseline[0])&(right<=baseline[1])
    eligible=(left>=search[0])&(right<=search[1])
    b=rate[before]
    _need(len(b)>=2,'at least two complete baseline bins')
    mean=float(b.mean());sd=float(b.std(ddof=1));level=mean+threshold_sd*sd
    details={'units':len(indices),'test_trials':int(test_counts.shape[0]),'bin_ms':bin_ms,
             'baseline_bins':int(before.sum()),'search_bins':int(eligible.sum()),
             'baseline_mean_rate':mean,'baseline_sample_sd_rate':sd,
             'threshold_rate':level,'threshold_sd':threshold_sd,'persistence_ms':2,
             'rate_unit':'spikes_per_second_per_source_unit'}
    if sd==0:return _undefined('zero_baseline_sd',**details)
    if not np.isfinite(level):return _undefined('nonfinite_threshold',**details)
    required=2//bin_ms;above=(rate>level)&eligible
    for i in range(len(rate)-required+1):
        if above[i:i+required].all():
            return {'status':'defined','latency_ms':float(left[i]-time_origin),**details}
    return _undefined('no_persistent_crossing',**details)


def _contrast(layers,**extra):
    defined=all(layers[k]['status']=='defined' for k in LAYERS)
    return {'status':'defined' if defined else 'undefined',
            'delta_l6_minus_l4_ms':layers['L6']['latency_ms']-layers['L4']['latency_ms'] if defined else None,
            'layers':layers,**extra}


def _erosion(record,by_id):
    keep={};support={}
    for layer in LAYERS:
        candidates=[e for e in by_id.values() if e['layer']==layer]
        chosen=[e['electrode_id'] for e in candidates if not any(
            other['layer']!=layer and abs(other['depth_rank']-e['depth_rank'])<=1
            for other in by_id.values())]
        keep[layer]=set(chosen)
        support[layer]={'original_contacts':len(candidates),'retained_contacts':len(chosen),
                        'removed_contacts':len(candidates)-len(chosen)}
    return keep,support


def _matching(record,counts,by_id):
    dev=counts[1::2];strata={layer:{} for layer in LAYERS}
    support={layer:{'source_contacts':0,'no_units':0,'zero_development_sd':0,'eligible_contacts':0}
             for layer in LAYERS}
    if len(dev)==0:return None,{'status':'unsupported','reason':'no_development_trials','layers':support}
    left=np.arange(-50,50);baseline=(left>=-50)&(left<-5);early=(left>=1)&(left<20)
    for key,e in by_id.items():
        layer=e['layer']
        if layer not in LAYERS:continue
        support[layer]['source_contacts']+=1
        units=[i for i,k in enumerate(record['unit_electrode_id']) if k==key]
        if not units:support[layer]['no_units']+=1;continue
        curve=dev[:,units,:].mean(axis=(0,1))
        sd=float(curve[baseline].std(ddof=1))
        if sd==0:support[layer]['zero_development_sd']+=1;continue
        snr=float((curve[early].mean()-curve[baseline].mean())/sd)
        _need(math.isfinite(snr),'finite development SNR')
        bucket=(len(units),math.floor(snr/.5))
        strata[layer].setdefault(bucket,[]).append((key,snr))
        support[layer]['eligible_contacts']+=1
    keep={layer:set() for layer in LAYERS};pairs=[]
    def priority(item):
        return hashlib.sha256((str(SEED)+'\0'+record['recording_id']+'\0'+
                               type(item[0]).__name__+'\0'+str(item[0])).encode()).digest()
    for bucket in sorted(set(strata['L4'])&set(strata['L6'])):
        a=sorted(strata['L4'][bucket],key=priority);b=sorted(strata['L6'][bucket],key=priority)
        for x,y in zip(a,b):
            keep['L4'].add(x[0]);keep['L6'].add(y[0]);pairs.append((x,y,bucket[0]))
    matched=len(pairs)
    details={'status':'supported' if matched else 'unsupported','reason':None if matched else 'no_shared_development_strata',
             'development_trials':len(dev),'snr_bin_width':.5,'unit_count_exactly_matched_per_contact':True,
             'matched_contacts_per_layer':matched,'matched_units_per_layer':sum(p[2] for p in pairs),
             'maximum_paired_snr_difference':max((abs(p[0][1]-p[1][1]) for p in pairs),default=None),
             'layers':support,'selection_uses_test_trials':False,
             'interpretation':'coarse development-SNR-bin and equal contact/unit count control; not exact-SNR or biological matching'}
    for layer in LAYERS:
        support[layer]['unmatched_eligible_contacts']=support[layer]['eligible_contacts']-matched
        details[layer+'_selected_contact_ids']=sorted(keep[layer],key=lambda x:(type(x).__name__,str(x)))
    return (keep if matched else None),details


def _first_spike(test_counts,indices):
    if not indices:return _undefined('no_target_layer_units',test_trials=len(test_counts),spiking_trials=0)
    values=[]
    for row in test_counts:
        times=np.flatnonzero(row[indices,51:].sum(axis=0)>0)
        if len(times):values.append(float(times[0]+1))
    details={'test_trials':len(test_counts),'spiking_trials':len(values),
             'no_spike_trials':len(test_counts)-len(values),'units':len(indices),
             'interpretation':'median first population spike, conditional on a spike in [1,50)ms; no significance correction'}
    if not values:return _undefined('no_test_trial_has_post_onset_spike',**details)
    return {'status':'defined','latency_ms':float(np.median(values)),**details}


def analyze_recording(record):
    counts,by_id=_validate_recording(record);test=counts[::2]
    units={layer:_indices(record,by_id,layer) for layer in LAYERS}
    conditions={}
    for name,threshold,bin_ms in [('primary',3.,1),('threshold_2_5',2.5,1),
                                  ('threshold_3_5',3.5,1),('bins_2ms',3.,2)]:
        conditions[name]=_contrast({layer:onset(test,units[layer],threshold,bin_ms) for layer in LAYERS})
    keep,support=_erosion(record,by_id)
    conditions['boundary_erosion_one_depth']=_contrast(
        {layer:onset(test,_indices(record,by_id,layer,keep[layer])) for layer in LAYERS},
        support=support,interpretation='exclude near-boundary contacts; no shifted or consensus anatomy')
    conditions['baseline_pseudo_onset']=_contrast({layer:onset(test,units[layer],baseline=(-50.,-30.),
        search=(-25.,0.),time_origin=-25.) for layer in LAYERS},
        interpretation='pre-stimulus detector behavior, not a calibrated permutation p-value')
    matched,details=_matching(record,counts,by_id)
    conditions['development_snr_bin_contact_matched']=_contrast({layer:
        onset(test,_indices(record,by_id,layer,matched[layer])) if matched is not None else
        _undefined('unsupported_development_matching') for layer in LAYERS},matching=details)
    conditions['first_spike_median_descriptive']=_contrast({layer:_first_spike(test,units[layer]) for layer in LAYERS})
    return {'recording_id':record['recording_id'],'participant_id':record['participant_id'],'area':record['area'],
            'total_trials':int(len(counts)),'test_trials':int(len(test)),'development_trials':int(len(counts[1::2])),
            'unit_counts':{layer:len(units[layer]) for layer in LAYERS},'conditions':conditions}


def _aggregate(results,condition,participants,multiplicity):
    output={}
    for area in AREAS:
        grouped={}
        for r in results:
            if r['area']==area:grouped.setdefault(r['participant_id'],[]).append(r['conditions'][condition])
        subject=[]
        for p in sorted(grouped):
            records=grouped[p];values=[r['delta_l6_minus_l4_ms'] for r in records]
            ok=all(v is not None for v in values)
            subject.append({'participant_id':p,'recordings':len(records),'status':'defined' if ok else 'undefined',
                            'delta_l6_minus_l4_ms':math.fsum(values)/len(values) if ok else None,
                            'undefined_recordings':sum(v is None for v in values)})
        observed=[s['delta_l6_minus_l4_ms'] for s in subject if s['status']=='defined']
        full=bool(subject) and len(observed)==len(subject)
        index={p:i for i,p in enumerate(participants)}
        columns=[index[s['participant_id']] for s in subject]
        w=multiplicity[:,columns];denom=w.sum(axis=1)
        missing=np.asarray([s['status']!='defined' for s in subject],dtype=bool)
        undefined_selected=(w[:,missing].sum(axis=1)>0) if missing.any() else np.zeros(len(w),dtype=bool)
        no_area=denom==0;valid=~no_area&~undefined_selected
        values=np.asarray([0. if s['status']!='defined' else s['delta_l6_minus_l4_ms'] for s in subject])
        draws=(w[valid]@values)/denom[valid]
        ci=np.percentile(draws,[2.5,97.5]).tolist() if full and valid.all() else None
        output[area]={'recorded_participants':len(subject),'recordings':sum(s['recordings'] for s in subject),
            'participant_effects':subject,'defined_participants':len(observed),'undefined_participants':len(subject)-len(observed),
            'full_area_mean_ms':math.fsum(observed)/len(observed) if full else None,
            'full_area_status':'defined' if full else 'undefined_incomplete_participant_effects',
            'observed_only_mean_ms':math.fsum(observed)/len(observed) if observed else None,
            'observed_only_is_full_cohort':full,
            'bootstrap':{'draws':len(w),'defined_draws':int(valid.sum()),'undefined_draws':int((~valid).sum()),
                'no_area_participant_draws':int(no_area.sum()),'undefined_participant_selected_draws':int(undefined_selected.sum()),
                'percentile_95_interval_ms':ci,'interval_status':'defined' if ci is not None else 'withheld_no_complete_unconditional_interval',
                'redrawn_or_conditioned_on_defined_draws':False}}
    return output


def analyze(recordings,roster):
    """Complete released 47-recording/41-participant analysis of normalized arrays."""
    _need(type(roster) is list and len(roster)==47,'exact complete 47-recording roster required')
    expected={}
    for row in roster:
        _need(type(row) is dict and set(row)=={'recording_id','participant_id','area'},'exact roster fields')
        _need(all(type(row[k]) is str and row[k] for k in ('recording_id','participant_id')) and row['area'] in AREAS,
              'canonical source identities and area')
        _need(row['recording_id'] not in expected,'unique source recording IDs');expected[row['recording_id']]=row
    participants=sorted({r['participant_id'] for r in roster})
    _need(len(participants)==41 and {r['area'] for r in roster}==set(AREAS),'complete 41-participant two-area panel')
    _need(not isinstance(recordings,(dict,str,bytes)),'recordings must be an iterable of normalized records')
    # Consume one recording at a time: the real released count tensors need not
    # coexist in memory. Retain only small numerical/support summaries.
    actual={}
    for record in recordings:
        _need(type(record) is dict and 'recording_id' in record,'normalized recording object required')
        key=record['recording_id']
        _need(key in expected and key not in actual,'exact unique recording join')
        _need(all(record[k]==expected[key][k] for k in expected[key]),'recording participant/area identity')
        actual[key]=analyze_recording(record)
    _need(set(actual)==set(expected),'all 47 normalized recordings must be supplied')
    results=[actual[key] for key in sorted(expected)]
    rng=np.random.Generator(np.random.PCG64(SEED))
    draws=rng.integers(0,len(participants),size=(BOOTSTRAP_DRAWS,len(participants)))
    multiplicity=np.asarray([np.bincount(d,minlength=len(participants)) for d in draws],dtype=np.int64)
    digest=hashlib.sha256(multiplicity.astype('<u4').tobytes()).hexdigest()
    return {'policy':'neural100_released_panel_draft_v1','exact_paper_reproduction':False,
            'timing_alignment_established_by_core':False,'recordings':47,'participants':41,
            'source_area_recording_counts':{a:sum(r['area']==a for r in roster) for a in AREAS},
            'paper_area_counts_used_to_select_or_relabel':False,'per_recording':results,
            'conditions':{c:_aggregate(results,c,participants,multiplicity) for c in CONDITIONS},
            'bootstrap_schedule':{'generator':'PCG64','seed':SEED,'draws':BOOTSTRAP_DRAWS,
                'participant_order':participants,'draw_size':len(participants),'multiplicity_sha256':digest,
                'shared_across_areas_and_conditions':True},
            'anatomical_shift_reconstruction':False,'boundary_control':'one_depth_exclusion_without_relabeling',
            'scientific_success_threshold':None,'causal_pathway_claim':False}
