"""Full selected input views, after global source commitment; saved fits excluded."""
import os
from pathlib import Path
from common import canonical, capture, descriptor, need, ordinary, parse, pin, relative, save
import npy_transport
import protocol
import transport


def roster(persons):
    need(type(persons)is list and [p.get('participant') for p in persons]==list(protocol.PEOPLE),'all9 original person ordering')
    rows=[]
    for p in persons:
        person=p['participant'];ids=p['electrode_ids']
        need(type(ids)is list and len(ids)==protocol.COUNTS[person] and len(set(ids))==len(ids) and all(type(x)is str and x for x in ids),'all433 native electrode IDs')
        need(p['response_signal_order']==list(protocol.SIGNALS) and set(p['apertures'])==set(protocol.SIGNALS),'fixed native signal and aperture identities')
        for sig,model,neg in protocol.CONDITIONS:
            condition=sig+'__'+model+('__sign_free' if neg else '__positive_gain')
            for i,electrode in enumerate(ids):
                rows.append(dict(case_id=person+'__'+condition+'__'+str(i).zfill(4),participant=person,electrode_id=electrode,signal=sig,model=model,allow_negative_gain=neg))
    need(len(rows)==3464,'all selected spatial cases');return rows


def source_row(repo,row):
    return {**row,'source':ordinary(repo/relative(row['source']))}


def admit(repo,b,budget):
    """Only read fixed metadata; authentic numeric hashes are checked during each full view copy."""
    need(b['task_id']==protocol.TASK and b['condition']==protocol.CONDITION and b['versions']==protocol.VERSIONS,'exact scientific condition')
    documents={}
    for name,row in b['rosters'].items():
        documents[name]=parse(capture(repo/relative(row['source']),row,1048576,budget))
    persons=documents['persons.json']; rows=roster(persons)
    need(documents['parameter_roster.json']==rows,'exact original public parameter roster')
    spectral=documents['spectral_roster.json']
    need(type(spectral)is list and len(spectral)==36,'complete spectral roster')
    lookup={(r['participant'],r['signal']):r for r in spectral}
    need(set(lookup)=={(p,s) for p in protocol.PEOPLE for s in protocol.SIGNALS},'spectral complete product')
    for p in persons:
        for sig in protocol.SIGNALS:
            need(lookup[p['participant'],sig]['electrode_ids']==p['electrode_ids'],'same complete original spectral native ordering')
            key=p['apertures'][sig];need(key in b['spatial_inputs'] and key.startswith('apertures/'),'exact signal-specific aperture descriptor')
        need(p['participant']+'/responses.npy' in b['spatial_inputs'],'fixed released response descriptor')
    # Source admission provenance is an exact cryptographic join; no Boolean alone grants parity.
    provenance={r['path']:parse(capture(repo/relative(r['path']),r,1048576,budget)) for r in b['provenance'] if r['path'].endswith('.json')}
    numeric=next(v for k,v in provenance.items() if k.endswith('/actual001-review/REVIEW_RECEIPT.json'))
    need(numeric['numeric_preparation_outputs_admitted']is True and numeric['accepted_complete_scope']['arrays']==27 and numeric['accepted_complete_scope']['channels']==433,'exact existing full numeric preparation admission')
    need(len(b['spectral_inputs'])==37 and len(b['spectral_B_code'])==40 and len(b['spatial_B_code'])==78,'complete typed inputs and distinct source assistance')
    return dict(persons=persons,parameter_rows=rows,spectral_rows=spectral,parameter_sha=b['rosters']['parameter_roster.json']['sha256'],spectral_sha=b['rosters']['spectral_roster.json']['sha256'])


class View(transport.View):
    def __init__(self,root,rows,generated,metadata,budget):
        self.root=ordinary(root);self.budget=budget;self.expected={};self.live=False
        before=budget.retained_charge
        need(not self.root.exists() and len(rows)+len(generated)<=180,'fresh complete selected view')
        self.root.mkdir(mode=0o700,parents=True)
        for row in rows:
            name=str(relative(row['target']));need(name not in self.expected and name!='VIEW.json','unique exact source target')
            self.expected[name]=transport.copy(row['source'],self.root/name,row,budget)
        for name,body in generated.items():
            relative(name);need(name not in self.expected and name!='VIEW.json','unique generated view member')
            self.expected[name]=save(self.root/name,body,budget,cap=16*1024**2,metadata=False);os.chmod(self.root/name,0o444)
        self.expected['VIEW.json']=save(self.root/'VIEW.json',canonical(metadata),budget);os.chmod(self.root/'VIEW.json',0o444)
        self.verify()
        _,dirs=transport.tree(self.root)
        for name in sorted(dirs,key=lambda n:n.count('/'),reverse=True):
            os.chmod(self.root/name,0o555);transport.sync(self.root/name)
        os.chmod(self.root,0o555);transport.sync(self.root);transport.sync(self.root.parent)
        self.live=True;self.retirement_credit=budget.retained_charge-before


def materialize(root,repo,b,design,ctx,budget):
    mode=ctx['mode'];arm=ctx['arm'];rows=[source_row(repo,r) for r in b['common']];generated={}
    meta={'schema':'visual_alpha_program_view_v1','task_id':protocol.TASK,'condition':protocol.CONDITION,**ctx,'versions':protocol.VERSIONS,'parameter_roster_sha256':design['parameter_sha'],'spectral_roster_sha256':design['spectral_sha'],'held_responses_present':mode in ('spectral','spatial'),'cross_context_state_allowed':False,'source_assistance':arm=='B','native_MATLAB_parity':False}
    if mode=='spectral':
        rows += [source_row(repo,r) for r in b['spectral_inputs']+b['spectral_configs']]
        rows += [source_row(repo,b['rosters']['spectral_roster.json'])]
        if arm=='B':rows += [source_row(repo,r) for r in b['spectral_B_code']]
        meta.update(input_kind='complete27_numeric_arrays_and9_original_metadata_plus224_aperture',source_original_descriptors=b['original_spectral_inputs'],projection_provenance=b['provenance'][:5],output_schema='visual_alpha_timecourses_v1',all36_required=True)
    else:
        people=design['persons'] if mode=='spatial' else [p for p in design['persons'] if p['participant']==ctx['participant']]
        role='full' if mode=='spatial' else ctx['fit_role']; ix=protocol.indices(role)
        selected=[];apertures={}
        for p in people:
            pid=p['participant'];r=b['spatial_inputs'][pid+'/responses.npy'];raw=capture(repo/relative(r['source']),r,1048576,budget)
            srows={}
            for si,sig in enumerate(protocol.SIGNALS):
                name=pid+'/'+sig+'.npy';generated[name]=npy_transport.select_response(raw,(protocol.COUNTS[pid],4,75),si,ix)
                key=p['apertures'][sig];apertures[key]=b['spatial_inputs'][key]
                srows[sig]={'responses':name,'aperture':key,'aperture_identity':b['spatial_inputs'][key]['sha256'],'band':('FaCLbBW' if pid in ('p10','p11') else 'FaCLb') if sig=='corrected_alpha' else {'raw_alpha':'FaLb','broadband':'bbS','low_broadband':'bbL'}[sig]}
            selected.append({'participant':pid,'electrode_ids':p['electrode_ids'],'response_indices':ix,'signals':srows})
        rows += [source_row(repo,r) for r in apertures.values()]
        if arm=='B':rows += [source_row(repo,r) for r in b['spatial_B_code']]
        selected_roster=design['parameter_rows'] # Public identities only; never other-person responses
        rows.append(source_row(repo,b['rosters']['parameter_roster.json']))
        meta.update(participants=selected,response_indices=ix,fit_roles=list(protocol.ROLES) if mode=='spatial' else [role],output_schema='visual_alpha_parameters_v1' if mode=='spatial' else 'visual_alpha_context_parameters_v1',fixed_released_responses=True,stage1_outputs_used=False,full_series_initialization_allowed=mode=='spatial')
    return View(root,rows,generated,meta,budget)
