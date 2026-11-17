from .custody import Custody
"""Exact biological/temporal supports and per-actor projections."""
from pathlib import Path
import secrets
import math
from .errors import require
from .objects import Reader,canonical,digest,fields,pin,rel,unique_paths,write_new


ROW_FIELDS=('event_id','dataset','person','recording','session','start','end','source_clock_hz',
            'samples','sampling_hz','channels','geometry','reference','units','signal','target','stimulus','sequence')


def validate_rows(rows):
    require(rows,'empty biological support');ids=set()
    for row in rows:
        fields(row,ROW_FIELDS)
        require(row['event_id'] not in ids,'duplicate event');ids.add(row['event_id'])
        require(row['person'] and row['recording'] and row['session'],'missing biological identity')
        require(row['end']>row['start']>=0 and row['source_clock_hz']>0,'source clock')
        require(row['sampling_hz']==200 and row['samples']>0,'qualified epoch clock')
        require(len(row['channels'])==len(set(row['channels']))==len(row['geometry'])>0,'geometry/channel join')
        require(row['units'] in ('mV','uV','V','dimensionless_z'),'unit declaration')
        require(row['reference'],'reference scheme missing')
        require(all(type(x) in (list,tuple) and len(x)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in x) for x in row['geometry']),'finite three-dimensional channel geometry')
        if row['sequence'] is not None:
            fields(row['sequence'],('group','index','length'));q=row['sequence']
            require(type(q['index']) is int and type(q['length']) is int and 0<=q['index']<q['length'],'sequence clock/index')
        require(type(row['target']) is int and row['target']>=0,'class target')
    return ids


def validate_split(rows,split,condition,layout_contract=None):
    ids=validate_rows(rows);fields(split,('train','validation','query','classes','alias_qualification','montage_policy'))
    parts=[set(split[x]) for x in ('train','validation','query')]
    require(all(parts) and not any(parts[i]&parts[j] for i in range(3) for j in range(i)),'overlapping or empty split')
    require(set.union(*parts)==ids,'whole event support')
    lookup={x['event_id']:x for x in rows}
    if condition in ('strict_person','strict_person_and_montage'):
        people=[{lookup[x]['person'] for x in p} for p in parts]
        require(not any(people[i]&people[j] for i in range(3) for j in range(i)),'person leakage')
        require(split['alias_qualification'],'unknown aliases')
    if condition=='strict_person_and_montage':
        require(layout_contract is not None,'qualified physical montage contract required')
        def montage(row):return canonical_montage(row,layout_contract)
        layouts=[{montage(lookup[x]) for x in p} for p in parts]
        require(not any(layouts[i]&layouts[j] for i in range(3) for j in range(i)),'same actual montage under different labels')
    for p in parts:require({lookup[x]['target'] for x in p}==set(range(split['classes'])),'class support unavailable')
    return {'condition':condition,'support':digest(canonical(rows)),'split':digest(canonical(split))}


def validate_corpus(manifest,downstream_people,downstream_recordings):
    fields(manifest,('sources','people_aliases','recordings','exclusions','source_terms','preprocessing','qualified_scope','historical_count_reconciliation'))
    require(len(manifest['sources'])==92 and len({r['id'] for r in manifest['sources']})==92,'full 92-source manifest required')
    require(manifest['qualified_scope']=='complete_original_sources','public subset is not corpus reproduction')
    require(manifest['historical_count_reconciliation'],'unresolved source name/count reconciliation')
    require(set(manifest['source_terms'])=={r['id'] for r in manifest['sources']},'per-source terms')
    ids=set()
    for row in manifest['recordings']:
        fields(row,('id','source','person','sessions','raw_objects','processed_objects','channels','duration','coordinate_provenance','eligible','exclusion_reason'))
        require(row['id'] not in ids,'duplicate recording');ids.add(row['id'])
        require(row['source'] in manifest['source_terms'] and row['person'] in manifest['people_aliases'],'corpus source/person join')
        if row['eligible']:
            require(row['id'] not in downstream_recordings and manifest['people_aliases'][row['person']] not in downstream_people,'downstream corpus exposure')
            require(row['raw_objects'] and row['processed_objects'] and row['coordinate_provenance'],'missing whole corpus producer')
        else:require(row['exclusion_reason'],'unexplained exclusion')
    require(ids,'empty corpus')
    return {'identity':digest(canonical(manifest)),'sources':92,'recordings':len(ids),'eligible_recordings':sum(bool(x['eligible']) for x in manifest['recordings'])}


def fewshot_support(rows,person,shots,seed,session):
    """Prospective selector, separately qualified from original unknown sampler."""
    import random
    require(shots in (1,2,5,10,20),'shot roster')
    data=[r for r in rows if r['person']==person and r['target'] in (0,1)]
    require(len(data)==288 and len({r['event_id'] for r in data})==288,'full person left/right universe')
    sessions={r['session'] for r in data};require(len(sessions)==2 and all(sum(x['session']==s for x in data)==144 for s in sessions),'two complete sessions')
    require(session in sessions,'preselected calibration session')
    rng=random.Random(seed);cal=[]
    for label in (0,1):
        pool=sorted(r['event_id'] for r in data if r['session']==session and r['target']==label)
        require(len(pool)>=shots,'calibration class support');cal.extend(rng.sample(pool,shots))
    all_ids={r['event_id'] for r in data}
    return {'calibration_events':sorted(cal),'query_events':sorted(all_ids-set(cal)),'universe':sorted(all_ids),'sampler_profile':'prospective_session_fixed_v1'}


def materialize_view(rows,event_ids,label_ids,source_root,destination,byte_cap,file_cap,role,*,guard):
    """Build fresh opaque paths; raw private names/targets never enter query metadata."""
    guard()
    by={r['event_id']:r for r in rows};require(set(event_ids)<=set(by) and set(label_ids)<=set(event_ids),'view support')
    require(role in ('training','validation','calibration','query'),'view role')
    if role=='query':require(not label_ids,'query targets forbidden')
    require(len(event_ids)==len(set(event_ids)),'duplicate view event')
    dest=Path(destination);public=[];private={};objects=[];planned=[];groups={};people={}
    for event in event_ids:
        guard()
        row=by[event];token=secrets.token_hex(16);path=token+'.npy';original=row['signal']
        from .objects import check_pin
        check_pin(original)
        sequence=None
        if row['sequence'] is not None:
            q=row['sequence'];fields(q,('group','index','length'))
            if q['group'] not in groups:groups[q['group']]=secrets.token_hex(16)
            sequence={'group':groups[q['group']],'index':q['index'],'length':q['length']}
        item={'id':token,'signal':{**original,'path':path},'samples':row['samples'],'sampling_hz':row['sampling_hz'],
              'channels':row['channels'],'geometry':row['geometry'],'reference':row['reference'],'units':row['units'],'sequence':sequence}
        if role!='query':
            if row['person'] not in people:people[row['person']]=secrets.token_hex(16)
            item['person_group']=people[row['person']]
        if event in label_ids:item['label']=row['target']
        public.append(item);private[token]=event;objects.append(item['signal']);planned.append((path,original))
    metadata=canonical({'schema':'reve-actor-view-v1','role':role,'observations':public})
    require(sum(row['bytes'] for _,row in planned)+len(metadata)<=byte_cap and len(planned)+1<=file_cap,'whole projected view reservation before reads/writes')
    state=Custody();completed=[];partial={'destination':str(dest),'reader':None,'completed':completed,'eligible':False};state.observations.append(partial)
    guard();dest.mkdir(mode=0o700,exist_ok=False);reader=Reader(source_root,byte_cap+file_cap,file_cap,guard=guard);partial['reader']=reader
    try:
        for path,original in planned:
            guard();raw=reader.read(original);write_new(dest/path,raw,guard=guard);completed.append(pin(raw,path))
        write_new(dest/'view.json',metadata,guard=guard)
    except BaseException as exc:
        # No caller may admit this partial root. The exception carries original
        # costs and the exact retained partial inventory for its operator ledger.
        state.fail(exc,'materialize_view')
        try:exc.reve_partial_view=partial
        except BaseException as secondary:state.add_secondary(secondary,'materialize_view:partial_attachment')
        raise
    return {'public_index':public,'private_bijection':private,'objects':[ *objects,pin(metadata,'view.json')],
            'reader_cost':{'bytes':reader.bytes,'consumed_bytes':reader.consumed_bytes,'partial_observations':reader.partial_observations,'files':reader.files},'support':digest(canonical(event_ids))}


def canonical_montage(row,contract):
    """A paired permutation is identical; qualified physical aliases are explicit."""
    fields(contract,('coordinate_frame','coordinate_units','reference_aliases','channel_derivations','signal_units','qualification'))
    require(contract['coordinate_units']=='m' and contract['coordinate_frame'] and contract['qualification'],'qualified canonical metre frame required')
    require(row['reference'] in contract['reference_aliases'] and row['units']==contract['signal_units'],'qualified reference/signal units')
    def terms(value):
        require(value and type(value)is list,'signed physical derivation')
        result=[]
        for term in value:
            fields(term,('electrode','coefficient'))
            require(type(term['electrode']) is str and term['electrode'] and type(term['coefficient']) in (int,float) and math.isfinite(term['coefficient']) and term['coefficient']!=0,'physical derivation term')
            result.append((term['electrode'],float(term['coefficient'])))
        require(len({x[0] for x in result})==len(result),'duplicate derivation electrode')
        return sorted(result)
    reference=terms(contract['reference_aliases'][row['reference']])
    pairs=[]
    for channel,coordinate in zip(row['channels'],row['geometry']):
        require(channel in contract['channel_derivations'],'unqualified channel alias')
        derivation=terms(contract['channel_derivations'][channel])
        pairs.append({'derivation':derivation,'coordinate_m':[0.0 if v==0 else float(v) for v in coordinate]})
    encoded=[canonical(x).decode() for x in pairs]
    require(len(set(encoded))==len(encoded),'duplicate physical channel')
    return digest(canonical({'frame':contract['coordinate_frame'],'coordinate_units':'m','reference_terms':reference,'paired_channels':sorted(encoded)}))

def validate_support_plan(plan,scope):
    expected={d['id']+'|'+c for d in scope.panel['datasets'] for c in scope.panel['prospective_conditions']}
    require(set(plan['support_admission'])==expected,'all20 physical support cells required')
    jobs={j['id']:j for j in plan['jobs']}
    for key,b in plan['support_admission'].items():
        fields(b,('job','product','panel','dataset','condition','support','split','layout_contract','disposition','unavailable_evidence'))
        require(key==b['dataset']+'|'+b['condition'],'physical support cell identity')
        require(b['job'] in jobs and jobs[b['job']]['stage']=='S04' and b['product'] in jobs[b['job']]['expected_outputs'],'actual S04 support producer')
        require(b['disposition'] in ('available','unavailable'),'support availability disposition')
        if b['disposition']=='available':require(b['support'] and b['split'] and b['layout_contract'] and b['unavailable_evidence'] is None,'original support/layout contract missing')
        else:require(b['unavailable_evidence'] and b['support'],'explicit source-bound infeasibility/missing evidence; retain planned support identity')
    for group in plan['prediction_groups'].values():
        if group['purpose'] in ('I-person','I-person-montage'):
            cell=group['dataset']+'|'+group['condition']
            require(cell in plan['support_admission'] and group['support']==plan['support_admission'][cell]['support'],'protected group must bind selected support cell')

def admit_support_product(controller,job,product):
    selected={k:v for k,v in controller.plan['support_admission'].items() if v['product']==product['id']}
    if not selected:return {}
    require(job['stage']=='S04' and all(v['job']==job['id'] for v in selected.values()),'support producer job mismatch')
    panels=product['details']['support_panels']
    require(type(panels)is dict and set(panels)=={v['panel'] for v in selected.values()},'complete selected support panels')
    admitted={}
    for key,b in selected.items():
        controller.guard()
        panel=panels[b['panel']]
        if b['disposition']=='unavailable':
            fields(panel,('status','evidence','reason'))
            require(panel['status']=='unavailable' and panel['evidence']==b['unavailable_evidence'] and panel['reason'],'exact original unavailable support disposition')
            admitted[key]={'job':job['id'],'product':product['id'],'product_identity':digest(canonical(product)),'status':'unavailable','reason':panel['reason'],'evidence':panel['evidence'],'required_cell_retained':True}
            continue
        fields(panel,('rows','split','layout_contract'))
        require(panel['layout_contract']==b['layout_contract'],'physical alias/frame/reference policy substitution')
        require(all(r['dataset']==b['dataset'] for r in panel['rows']),'support dataset identity')
        actual=validate_split(panel['rows'],panel['split'],b['condition'],panel['layout_contract'])
        require(actual['support']==b['support'] and actual['split']==b['split'],'original support/split identity')
        query=set(panel['split']['query'])
        for group in controller.plan['prediction_groups'].values():
            if group['dataset']==b['dataset'] and group['condition']==b['condition'] and group['purpose'] in ('I-person','I-person-montage'):
                require(set(group['events'])==query,'whole protected group matches admitted query support')
        admitted[key]={'job':job['id'],'product':product['id'],'product_identity':digest(canonical(product)),'support':actual,'layout_contract':digest(canonical(panel['layout_contract']))}
        controller.guard()
    return admitted
