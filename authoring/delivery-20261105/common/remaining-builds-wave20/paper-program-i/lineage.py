"""Full-source identity and direct-sample support admission. No invented joins."""
from core import need, descriptor, identity, MODALITIES


def _name(value):
    need(type(value) is str and 0<len(value.encode())<=1024, 'Authenticated nonempty private identity')
    return value


def interval(value):
    need(type(value) is dict and set(value)=={'recording','start','stop'}, 'Exact source-sample interval')
    _name(value['recording'])
    need(type(value['start']) is int and type(value['stop']) is int and 0<=value['start']<value['stop'], 'Half-open physical sample support')
    return value


def overlaps(left,right):
    return any(a['recording']==b['recording'] and max(a['start'],b['start'])<min(a['stop'],b['stop']) for a in left for b in right)


def validate(prepared,prepared_pin,certificate,certificate_pin,evidence_pins,eligible):
    """Certificate is preapproved operator evidence, never a candidate assertion.

    A body with unresolved physical sample support cannot pass. Existing global
    normalization is separately named and cannot discharge direct overlap.
    This source validator checks the complete certificate joins; it does not
    manufacture historical extraction evidence or certify its scientific truth.
    """
    descriptor(prepared_pin);descriptor(certificate_pin)
    need(type(certificate) is dict and set(certificate)=={'schema','prepared','derivation','evidence','processing','acquisitions','physical_acquisitions'}, 'Complete lineage certificate')
    need(certificate['schema']=='filio_i_lineage_v1' and certificate['prepared']==prepared_pin, 'Exact prepared source lineage')
    descriptor(certificate['derivation'])
    need(type(certificate['evidence']) is list and certificate['evidence'] and certificate['evidence']==evidence_pins, 'Externally bound complete scientific evidence list')
    for p in evidence_pins: descriptor(p)
    process=certificate['processing']
    need(type(process) is dict and set(process)=={'estimand','direct_support_complete','normalization','filtering','registration','inductive_claim'}, 'Explicit upstream processing')
    need(process['estimand']=='released_processed_target' and process['direct_support_complete'] is True and process['inductive_claim'] is False, 'No unresolved direct support or invented inductive claim')
    for k in ('normalization','filtering','registration'): _name(process[k])
    source=prepared['acquisitions'];rows=certificate['acquisitions']
    need(type(source) is list and type(rows) is dict and len(source)==len({a['key'] for a in source}) and set(rows)=={a['key'] for a in source}, 'Complete original acquisition census including empty views')
    need(type(eligible) is dict and set(eligible)==set(rows),'Every source-row eligibility disposition supplied by trusted extraction')
    physical={};out={}
    for a in source:
        key=a['key'];r=rows[key]
        if a.get('status')=='structural_absence':
            need(r=={'status':'structural_absence','reason':a['reason']} and eligible[key]==[], 'Preserve absent source collection, no invented census')
            continue
        n=a['original_trial_count']
        need(type(n) is int and n>=0 and type(r) is dict and set(r)=={'animal','session','acquisition','trials','cells','sample_support','clock_evidence','selected_row_bijection','encoding_binding'}, 'Exact acquisition lineage')
        for k in ('animal','session','acquisition'):
            need(r[k] is None or type(r[k]) is str and r[k], 'Known or explicitly unknown excluded hierarchy')
        selected=eligible[key]
        need(type(selected) is list and len(selected)==len(set(selected)) and all(type(i) is int and 0<=i<n for i in selected),'All selected source-row ordinals')
        need(a['views'] or selected==[], 'Outside-native-view rows cannot enter encoding')
        if selected:
            for k in ('animal','session','acquisition'):_name(r[k])
            descriptor(r['clock_evidence']);descriptor(r['selected_row_bijection'])
            eb=r['encoding_binding']
            need(type(eb) is dict and set(eb)=={'status','dtb_seconds','position_units','behavior_clock','rew_pos_clock','event_clock_join','omission_clock_join','target_grid_join','trial_axis_join','evidence_pin'},'Exact reviewed selected-row clock binding')
            need(eb['status']=='authenticated' and eb['dtb_seconds']==a['dtb_seconds'] and eb['behavior_clock']=='tmpxx' and eb['rew_pos_clock']=='reward_aligned','Source-bound behavior clock')
            need(all(eb[k] is True for k in ('event_clock_join','omission_clock_join','target_grid_join','trial_axis_join')),'Selected-row event/target joins')
            descriptor(eb['evidence_pin'])
        need(type(r['trials']) is list and len(r['trials'])==n , 'Complete source-array row dispositions')
        for i,t in enumerate(r['trials']):
            if i in selected:_name(t)
            else:need(t is None or type(t) is str and t,'Excluded rows retain explicit unknown/known trial disposition')
        need(set(r['cells'])==set(MODALITIES) and set(r['sample_support'])==set(MODALITIES), 'Both modalities accounted')
        mods={m['name']:m for m in a['modalities']}
        need(set(mods)==set(MODALITIES), 'Both original modality dispositions')
        for m in MODALITIES:
            cells=r['cells'][m];sup=r['sample_support'][m];native=mods[m]
            need(type(cells) is list and len(set(cells))==len(cells),'Unique source cell-axis identities')
            if native['status']=='outside_selected_views':
                need(a['views']==[] and not selected and cells==[] and sup==[], 'Explicit outside-selected-view disposition, no invented targets')
                continue
            need(not selected or len(cells)==native['required_cells'],'Complete selected modality cell-axis bijection')
            for cell in cells:_name(cell)
            if native['status']=='structural_absence':
                need(cells==[] and sup==[], 'Structural modality absence preserved')
            else:
                need(native['status']=='present' and type(sup) is list and
                     (len(sup)==n and bool(cells) if selected else len(sup) in (0,n)),
                     'Selected rows require full source trial/cell support; excluded rows may remain unknown')
                for i,segments in enumerate(sup):
                    need(type(segments) is list and (segments or i not in selected), 'Selected trajectories require all contributing released processed-stream samples and interpolation support')
                    for s in segments: interval(s)
        folds=[None]*n  # Assigned only from authenticated acquisition-wide released-row chronology.
        identity_tuple=(r['animal'],r['session'])
        if selected:need(r['acquisition'] not in physical or physical[r['acquisition']]==identity_tuple, 'One biological membership per physical acquisition')
        if selected:physical[r['acquisition']]=identity_tuple
        out[key]={**r,'folds':folds,'views':a['views'],'source_key':key}
    # Each selected physical acquisition is ordered exactly once from reviewed
    # released rows/aliases, including original exclusions, never unseen attempts.
    groups=certificate['physical_acquisitions']
    need(type(groups) is dict,'Authenticated physical acquisition chronology mapping')
    source_by_key={a['key']:a for a in source}
    required=set()
    for key,r in out.items():
        a=source_by_key[key]
        if a['views'] and any(m['status']=='present' and m['required_cells']>0 for m in a['modalities']):
            _name(r['acquisition']);required.add(r['acquisition'])
    need(set(groups)==required,'Exactly every required physical acquisition, never source-fragment models')
    joined={};trial_owner={}
    for acquisition,g in groups.items():
        _name(acquisition)
        need(type(g) is dict and set(g)=={'animal','session','chronology_evidence','cells','chronology'},
             'Complete acquisition-wide released-row chronology/cell axes')
        _name(g['animal']);_name(g['session'])
        descriptor(g['chronology_evidence'])
        need(g['chronology_evidence'] in evidence_pins,'Chronology evidence is one of the externally approved evidence pins')
        need(type(g['cells']) is dict and set(g['cells'])==set(MODALITIES),'Canonical physical modality cell axes')
        for cells in g['cells'].values():
            need(type(cells) is list and len(cells)==len(set(cells)),'Unique canonical physical cell identities')
            for cell in cells:_name(cell)
        members={key:r for key,r in out.items() if r['acquisition']==acquisition}
        expected={(key,i) for key in members for i in range(source_by_key[key]['original_trial_count'])}
        chronology=g['chronology']
        need(type(chronology) is list and chronology,'Complete nonempty released physical-trial chronology')
        seen=set();trials=[];source_to_joined={}
        for ordinal,event in enumerate(chronology):
            need(type(event) is dict and set(event)=={'trial','source_rows'},'Exact chronological physical trial and source aliases')
            trial=_name(event['trial'])
            need(trial not in trials and (trial not in trial_owner or trial_owner[trial]==acquisition),
                 'Unique physical trial chronology and acquisition identity')
            trial_owner[trial]=acquisition;trials.append(trial)
            refs=event['source_rows']
            need(type(refs) is list and refs,'Chronology consists only of observed released source rows')
            for ref in refs:
                need(type(ref) is dict and set(ref)=={'source_key','row'} and type(ref['source_key']) is str and
                     type(ref['row']) is int,'Exact released source row reference')
                coordinate=(ref['source_key'],ref['row'])
                need(coordinate in expected and coordinate not in seen,'Exhaustive unique released-row chronology membership')
                seen.add(coordinate);source_to_joined[coordinate]=ordinal
                r=members[ref['source_key']];i=ref['row']
                need(r['trials'][i] in (None,trial) and (i not in eligible[ref['source_key']] or r['trials'][i]==trial),
                     'Original selected physical identity agrees with reviewed chronology')
                need(r['animal'] in (None,g['animal']) and r['session'] in (None,g['session']),
                     'Fragments share authenticated physical animal/session')
        need(seen==expected,'Every released row, including excluded rows and aliases, appears exactly once')
        folds=[min(4,(5*i)//len(chronology)) for i in range(len(chronology))]
        for (key,row),ordinal in source_to_joined.items():out[key]['folds'][row]=folds[ordinal]
        for key,r in members.items():
            if not eligible[key]:continue
            a=source_by_key[key]
            for m in a['modalities']:
                if m['status']=='present':
                    need(set(r['cells'][m['name']])==set(g['cells'][m['name']]) and
                         len(r['cells'][m['name']])==len(g['cells'][m['name']]),
                         'Every selected fragment has the full canonical physical cell set; no intersection subset')
        joined[acquisition]={**g,'trials':trials,'folds':folds,'source_keys':list(members),
                             'source_to_joined':source_to_joined}
    # The same session cannot acquire different animals through another row.
    sessions={}
    for r in out.values():
        if not eligible[r['source_key']]:continue
        need(r['session'] not in sessions or sessions[r['session']]==r['animal'],'Complete session to animal join')
        sessions[r['session']]=r['animal']
    return {'schema':'filio_i_admitted_lineage_v1','prepared':prepared_pin,'certificate':certificate_pin,
            'rows':out,'physical_acquisitions':joined,'processing':process,'scientific_truth_inferred_from_shape':False}


def partitions(lineage,eligible,outer_fold,inner_fold=None):
    """Full held support; purge only training physical trials across all aliases.

    eligible maps every source key to all selected physical row ordinals. The
    caller derives it from original source flags, never candidate choices.
    """
    need(type(outer_fold) is int and 0<=outer_fold<5, 'Five source-order folds')
    need(inner_fold is None or type(inner_fold) is int and 0<=inner_fold<5 and inner_fold!=outer_fold, 'Inner fold from outer training')
    rows=lineage['rows'];need(set(rows)<=set(eligible), 'All source rows in split census')
    held=[];all_rows=[]
    for key,r in rows.items():
        indexes=eligible[key]
        need(type(indexes) is list and len(set(indexes))==len(indexes) and all(type(i) is int and 0<=i<len(r['trials']) for i in indexes), 'Exact selected source ordinals')
        for i in indexes:
            segments=[s for m in MODALITIES for s in (r['sample_support'][m][i] if r['sample_support'][m] else [])]
            row={'key':key,'row':i,'trial':r['trials'][i],'fold':r['folds'][i],'support':segments}
            all_rows.append(row)
            if row['fold'] in (outer_fold,inner_fold):held.append(row)
    forbidden={r['trial'] for r in held}
    for r in all_rows:
        if r['fold'] not in (outer_fold,inner_fold) and any(overlaps(r['support'],q['support']) for q in held):forbidden.add(r['trial'])
    out={k:{'train':[],'validation':[],'query':[],'purged_train':[]} for k in rows}
    for r in all_rows:
        k,i,f=r['key'],r['row'],r['fold']
        if f==outer_fold:out[k]['query'].append(i)
        elif inner_fold is not None and f==inner_fold:out[k]['validation'].append(i)
        elif r['trial'] in forbidden:out[k]['purged_train'].append(i)
        else:out[k]['train'].append(i)
    return out
