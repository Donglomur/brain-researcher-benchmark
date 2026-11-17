"""Finite source-event joins. Metadata controls may use invented category tokens.
Authentic projections/target values require the currently absent native owner.
"""
import hashlib
from .matching import match_secondary
from .support import support_tables
from .design import POLICIES,ROLE_NAMES

def key_id(*items):return hashlib.sha256('|'.join(map(str,items)).encode()).hexdigest()[:24]

def validate_roles(records,assignments):
    observed={r['mouse'] for r in records}
    if observed!=set(assignments) or any(v not in ROLE_NAMES for v in assignments.values()):raise ValueError('complete source-owned mouse assignments')
    for r in records:
        if r['split']!=assignments[r['mouse']]:raise ValueError('whole-mouse role mismatch')
    return {role:sorted(m for m,v in assignments.items() if v==role) for role in ROLE_NAMES}

def assemble_secondary(membership,events,assignments,dispositions):
    if membership.get('population')!='secondary' or membership.get('membership_status')!='admitted':raise ValueError('secondary membership not admitted')
    support=support_tables(membership,events,dispositions);roles=validate_roles(membership['experiments'],assignments)
    recs={r['experiment']:r for r in membership['experiments']}
    for e in events:
        if e['split']!=recs[e['experiment']]['split'] or e['phase']!={'Novel 1':'FIRST','Novel >1':'REPEAT'}.get(e['condition']):raise ValueError('literal phase/role binding')
    # Classify the image from every FIRST row before matching or neural support.
    first_images={}
    for e in events:
        if e['phase']=='FIRST':
            key=(e['container'],e['image']);v=e['native_image_novel']
            if key in first_images and first_images[key]!=v:raise ValueError('inconsistent source FIRST image classification')
            first_images[key]=v
    by_id={e['event']:e for e in events};analyses={}
    for policy in POLICIES:
        matched=match_secondary(events,policy);cases=[];pair_dispositions=[]
        for pair in matched['pairs']:
            pid=key_id(policy,pair['first'],pair['repeat']);novel=first_images.get((pair['container'],pair['image']))
            subset='new_image' if novel is True else 'already_familiar_image_control' if novel is False else 'unknown_first_image_status'
            pair_dispositions.append({'pair':pid,'mouse':pair['mouse'],'container':pair['container'],'status':pair['status'],'subset':subset})
            if pair['status']!='supported':continue
            for eid in (pair['first'],pair['repeat']):
                r=by_id[eid]
                row={'id':key_id(policy,pid,r['phase']),'pair':pid,'source_event':eid,'mouse':r['mouse'],'container':r['container'],'split':r['split'],
                     'cre_line':r['cre_line'],'phase':r['phase'],'image':r['image'],'image_novel_at_first':novel,'subset':subset,
                     'image_set':r['image_set'],'area':r['area'],'depth':r['depth'],'change':r['change'],'outcome':r['outcome_flags'],
                     'running':r['running'],'pupil_bin':r['pre_pupil_bin'],'running_bin':r['pre_running_bin'],'history_bin':r['within_session_history'],
                     'prior_image_count':r['within_session_prior_count']}
                cases.append(row)
        per_mouse=[]
        for mouse in sorted(assignments):
            rr=[r for r in cases if r['mouse']==mouse];pp=[r for r in pair_dispositions if r['mouse']==mouse]
            ee=[r for r in events if r['mouse']==mouse]
            unknown=any(r['native_image_novel'] is None for r in ee if r['phase']=='FIRST')
            missing_experiments=[r['experiment'] for r in membership['experiments'] if r['mouse']==mouse and r['status']!='complete']
            supported=any(r['subset']=='new_image' for r in rr)
            unsupported_new=any(r['subset']=='new_image' and r['status']!='supported' for r in pp)
            status='incomplete_source' if missing_experiments else 'unknown_new_image_denominator' if unknown else 'unsupported_matched_new_image_pair' if unsupported_new else 'no_supported_new_image_pair' if not supported else 'complete_supported'
            per_mouse.append({'mouse':mouse,'split':assignments[mouse],'status':status,'supported_cases':len(rr),'missing_experiments':missing_experiments})
        analyses[policy]={'cases':sorted(cases,key=lambda r:r['id']),'matching':matched,'pair_dispositions':pair_dispositions,'mouse_support':per_mouse,
                          'complete_primary_support':all(r['status']=='complete_supported' for r in per_mouse)}
    return {'support':support,'roles':roles,'analyses':analyses,'source_assignments':dict(assignments),'scientific_execution':False}

def public_context(row,policy):
    # Outcome columns are unavailable to the pre-stimulus primary analysis.
    excluded={'source_event','target'}|({'outcome'} if policy=='prestate_history' else set())
    return {k:v for k,v in row.items() if k not in excluded}
