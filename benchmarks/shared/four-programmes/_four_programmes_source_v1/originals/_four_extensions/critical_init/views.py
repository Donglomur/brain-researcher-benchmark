"""Matched isolated A/B materialization from exact, role-labelled selected members."""
from pathlib import Path
from .custody import read_pin,write_new,new_directory,need,pin,encode
from .guard import distinct,RequiredUnscorable

COMMON_ROLES={'paper','data','clarification','common_library','task'}
CODE_ROLES={'author_code','author_license','author_configuration'}

def validate_pair(manifest):
    need(manifest['conditions']==['paper_data','paper_data_author_code'],'exact two access conditions')
    members=manifest['common'];code=manifest['author_code']
    distinct([m['destination']for m in members+code])
    need(all(m['role']in COMMON_ROLES for m in members)and all(m['role']in CODE_ROLES for m in code),'no answer or historical run artifacts in views')
    need(manifest['complete_original_author_source']is True and manifest['import_closure_pin'],'complete B code, not held11-file subset')
    need(manifest['identical_population_clarification']is True and manifest['identical_observed_DMD_clarification']is True,'same scientific clarifications')
    need(manifest['prior_answer_exposure_policy']and manifest['fresh_agent_state']is True,'explicit exposure and state isolation')
    need(manifest['arm_limits']['paper_data']==manifest['arm_limits']['paper_data_author_code'],'matched resource opportunity')
    for m in members+code:
        dest=Path(m['destination'])
        need(not dest.is_absolute()and len(dest.parts)==1 and dest.name not in ('.','..'),'flat exact input names')
        need(m['source']['sha256']not in manifest['forbidden_answer_hashes'],'protected answers absent')
    return pin(encode(manifest))

def materialize(root,manifest,parent,*,nonce,budget):
    pair_pin=validate_pair(manifest);pair=new_directory(parent,nonce,budget);views={}
    try:
        for condition in manifest['conditions']:
            view=new_directory(pair,condition,budget);views[condition]=str(view)
            source_members=manifest['common']+(manifest['author_code']if condition=='paper_data_author_code'else [])
            for member in source_members:
                raw=read_pin(root,member['source'],manifest['member_cap_bytes'],budget)
                write_new(view/member['destination'],raw,budget)
        return {'views':views,'pair_manifest':pair_pin,'fresh_pair_root':str(pair)}
    except BaseException as error:
        error.partial_view_roots=views;error.pair_root=str(pair);raise

