"""Concrete operator preparation and campaign CLI; no effect on import.

One original preparation process keeps path custody through genuine deployment
qualification pauses. The existing campaign CLI then owns its original process,
clock and independent-review pauses. No authority/review issuer is implemented.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from .contracts import (Authority, Budget, Custody, Handles, Store, canonical,
                        closed, descriptor, digest, need, parse, relative)
from .operator_compiler import (authoring_selection, attach_reviews, compile_campaign,
                                path_selection, GROUPS, group_id)
from .factored_runtime import FactoredPreparation
from .openai_gateway import OpenAIExecutor
from .predata_authoring import produce_all, render_context_messages
from .operator_wire import write_canonical

COMPLETE_NATIVE_METADATA_CAP = 1024 * 2**20


def campaign_launch_prefix():
    """Use the actual selected bootstrap and a distinct one-use next prefix."""
    boot=getattr(sys,'_nlb017_bootstrap',None)
    need(type(boot)is dict and boot.get('schema')=='NLB017_captured_host_bootstrap_v1',
         'supported captured-source standalone entry required')
    need(sys.flags.isolated==1 and sys.flags.dont_write_bytecode==1
         and sys.dont_write_bytecode is True,'actual isolated no-bytecode interpreter')
    entry=str(Path(__file__).absolute().parent.parent/'nlb_entry.py')
    need(boot['entry']==entry and boot['cache_prefix']==sys.pycache_prefix,
         'same captured package and original cache prefix')
    return [sys.executable,'-I','-B','-X','pycache_prefix='+sys.pycache_prefix+'.campaign',
            entry,'campaign']



def create_directories(store, paths):
    """Explicit finite create-only preparation; all failures remain on disk."""
    selected = set()
    for path in paths:
        relative(path)
        bits = path.split('/')
        selected.update('/'.join(bits[:i]) for i in range(1,len(bits)+1))
    for path in sorted(selected, key=lambda x:(x.count('/'),x)):
        store.budget.admit(); owner = Handles(store.custody)
        event = {'directory':path,'attempted':False,'created':False};store.custody.events.append(event)
        try:
            store.budget.reserve('created_files',1)
            parent,leaf=store.parent(path,owner);event['attempted']=True
            os.mkdir(leaf,mode=0o700,dir_fd=parent);event['created']=True
            store.budget.charge('created_files',1);os.fsync(parent)
        except BaseException as error:
            store.custody.fail(error,'operator_directory_preparation');store.budget.stop('original preparation failed')
        finally:owner.finish()
        store.custody.raise_if_failed()


def gateway_configurations(store, full, preparation, model, selected, root_source):
    """Generate every job-bound gateway config from one selected protocol table."""
    closed(selected, {'max_request_bytes','max_response_bytes','timeout_seconds','max_messages','max_items'})
    profile=full['profiles']['model_gateway']; transport=profile['gateway_transport']
    result={}
    for row in preparation.iter_physical_entries():
        if preparation.roster.row(row['slot_ordinal'])['role']!='model_exchange':continue
        c={'schema':'NLB017_OpenAI_gateway_config_v1','job':row['job'],'stage':row['stage'],
           'source':profile['source'],'result_prefix':row['paths']['output_prefix'],
           'model':model['model_identity'],'configuration':model['configuration'],
           'prompt':model['prompt'],'tokenizer':model['tokenizer'],
           'authority':profile['authority'],'expected_root_source':root_source,
           'transport_qualification':transport['qualification'],'transport':transport['transport'],
           'credential':transport['credential'],**selected}
        path=preparation.namespace_receipt['path'].rsplit('/',1)[0]+'/gateway-'+row['token']+'.json'
        pin=store.write(path,canonical(c),2**20);result[row['job']]={'config_pin':pin}
    return result


def materialize_contexts(store, authority, selection):
    """Actual reviewed source copies plus rebased manifests, never fake review."""
    from .context_builder import context_manifest, materialize
    closed(selection,{'programme','entries','exposure_review','rights_review','output_prefix'})
    entries=store.json(selection['entries'],8*2**20)
    exposure=store.json(selection['exposure_review'],8*2**20)
    rights=store.json(selection['rights_review'],8*2**20)
    prefix=selection['output_prefix'];relative(prefix)
    # Member paths are source-declared ordinary relative paths; make every parent
    # before copying. Both complete A and B recipes retain their real provenance.
    recipes={v:context_manifest(v,entries,exposure,rights,selection['programme']) for v in ('A','B')}
    dirs=[prefix+'/'+v for v in ('A','B')]
    for v,recipe in recipes.items():
        dirs += [prefix+'/'+v+'/'+e['name'].rsplit('/',1)[0] for e in recipe['members'] if '/'in e['name']]
    create_directories(store,dirs)
    views={}
    for v,recipe in recipes.items():
        output=Store(store.path(prefix+'/'+v),store.budget,store.custody)
        original=materialize(recipe,authority,store.budget,output)
        body=output.json(original,4*2**20)
        body['members']=[{**e,'copied':{**e['copied'],'path':prefix+'/'+v+'/'+e['copied']['path']}} for e in body['members']]
        views[v]=store.write(prefix+'/CONTEXT_'+v+'.json',canonical(body),4*2**20)
    return views


def campaign_contexts(store, code_views, prompt_pin, context_programme):
    """Complete shared context and compact fresh-case instruction, all fifty I groups."""
    prompt=store.json(prompt_pin,2**20);contexts={}
    for g in GROUPS:
        if g['mode']!='I':continue
        gid=group_id(g);pin=code_views[g['code_view']]
        rendered=render_context_messages(store,store,public_context=pin,prompt=prompt_pin,
                                         group=gid,context_programme=context_programme)
        body=store.json(pin,4*2**20);members={};roles={}
        for e in body['members']:
            members[e['name']]=e['copied']
            roles[e['name']]='curated_code_B'if e['role']in('curated_author_code','code_license')else e['role']
        neutral=g['condition']=='metadata_neutral'
        case=[{'role':'system','content':prompt['neutral_system'if neutral else'system']},
              {'role':'user','content':prompt['neutral_investigation_instruction'if neutral else'investigation_instruction']}]
        contexts[gid]={'preparation_messages':rendered['messages'],'case_messages':case,
                       'public_members':members,'public_member_roles':roles}
    return contexts


class OperatorPreparation:
    """Real preparation state; qualification gaps pause, never generate verdicts."""
    def __init__(self,store,selection):
        closed(selection,{'schema','root_source','slots','model','source_recipe','author_recipe',
                          'author_geometry','campaign_geometry','context_selection','design',
                          'gateway_limits','publication_prefix','receipt_limits'})
        need(selection['schema']=='NLB017_concrete_preparation_v1','closed concrete preparation')
        self.store=store;self.selection=selection;self.layouts={};self.runtime={};self.authority=None
        self.authored=None;self.code_views=None;self.compiled=None;self.final=None;self.started=False
        need(selection['source_recipe']['root_source']==selection['author_recipe']['root_source']==selection['root_source'], 'one selected root source')
        need(selection['source_recipe']['model']==selection['author_recipe']['model']==selection['model'], 'same exact F/I model and configuration')
        need(selection['source_recipe']['slots']==selection['author_recipe']['slots']==selection['slots'], 'one finite slot recipe')
        need(selection['source_recipe']['group_limits']==selection['author_recipe']['group_limits'], 'same original cumulative F/I budgets')
        need(selection['source_recipe']['original_deadline']==store.budget.deadline,'original campaign deadline selected before authoring')
    def initialize(self):
        need(not self.started,'one original coordinator start');self.started=True
        prefix=self.selection['publication_prefix'];relative(prefix)
        create_directories(self.store,[prefix,'programme','stages','evidence','collection','actors','reports','processes'])
        return {'status':'awaiting_actual_context_authority_and_deployment','full_groups':100,'workflow_roles':28844}
    def paths(self,phase):
        need(self.started and phase not in self.layouts,'one original phase path preparation')
        need(phase in ('authoring','campaign'), 'closed full preparation phase')
        selected=self.selection['author_geometry' if phase=='authoring' else 'campaign_geometry']
        closed(selected,{'programme','run_id','store_root','output_parent','metadata_parent','profiles'})
        geometry={k:v for k,v in selected.items() if k!='profiles'}
        author_prefix=self.selection['author_recipe']['output_prefix'] if phase=='authoring' else None
        prep=FactoredPreparation(geometry,self.selection['slots'],phase,selected['profiles'],
            self.selection['receipt_limits'],authoring_output_prefix=author_prefix)
        self.layouts[phase]={'preparation':prep}
        prep.prepare_paths(self.store)
        # The full physical paths are deterministic entry(ordinal) metadata;
        # do not expand tens of thousands of rows into the control response.
        return {'phase':phase,'slot_count':len(prep.roster),'physical_count':prep.roster.physical_count,
            'namespace_receipt':prep.namespace_receipt,'geometry':geometry,
            'path_lookup':'FactoredPreparation.entry(physical_ordinal)','source_qualification':False}
    def contexts(self,authority_pin):
        need(self.code_views is None,'one original context preparation')
        authority=Authority.from_selected(self.store,authority_pin,self.selection['root_source'])
        self.code_views=materialize_contexts(self.store,authority,self.selection['context_selection'])
        self.authority=authority
        return {'code_views':self.code_views,'context_roots':{'A':str(self.store.root),'B':str(self.store.root)}}
    def qualify(self,phase,profiles_pin,qualifications_pin,authority_pin):
        need(phase in self.layouts and phase not in self.runtime,'one original qualified phase composition')
        authority=Authority.from_selected(self.store,authority_pin,self.selection['root_source'])
        profiles=self.store.json(profiles_pin,COMPLETE_NATIVE_METADATA_CAP);qualifications=self.store.json(qualifications_pin,COMPLETE_NATIVE_METADATA_CAP)
        for profile in profiles.values():
            need(profile['authority']==authority_pin,'same current selected phase authority')
        model_profile=profiles['model_gateway']
        need(model_profile['source']==self.selection['model']['runtime'],'same selected model gateway source')
        required=[('engine_source',model_profile['source']),('gateway_qualification',model_profile['gateway_transport']['qualification'])]
        required += [('engine_source',self.selection['model'][k])for k in ('model_identity','configuration','prompt','tokenizer')]
        for role,pin in required:
            existing=[r for r in model_profile['static_inputs']if r['source']['path']==pin['path']]
            need(not existing or existing==[{'role':role,'source':pin}],'exact gateway metadata mount identity')
            if not existing:model_profile['static_inputs'].append({'role':role,'source':pin})
        if phase=='campaign':
            need(profiles['reference_producer']['source']==profiles['reference_tool']['source']==self.selection['source_recipe']['reference_source'],
                 'both arms call the exact original qualified reference source')
        row=self.layouts[phase];prep=row['preparation']
        gateway_jobs=gateway_configurations(self.store,{'profiles':profiles},prep,self.selection['model'],
            self.selection['gateway_limits'],self.selection['root_source'])
        prep.prepare_mounts(self.store,profiles,qualifications,gateway_jobs)
        runtime=prep.finish(self.store)
        if phase=='authoring':
            need(self.code_views is not None,'actual complete context precedes F authoring')
            author=authoring_selection({**self.selection['author_recipe'],
                'context_roots':{'A':str(self.store.root),'B':str(self.store.root)}},self.code_views)
            create_directories(self.store,[author['outer_output_prefix']]+[x['output_prefix']for x in author['groups'].values()])
            self.author_selection=author
        self.runtime[phase]=runtime;self.authorities=getattr(self,'authorities',{});self.authorities[phase]=authority
        return {'status':'source_compiled_from_actual_selected_qualification_pins','phase':phase,
                'native_jobs':len(runtime.roster),'scientifically_qualified':False}
    def author(self):
        need('authoring'in self.runtime and self.authored is None,'single complete F authoring attempt')
        authority=self.authorities['authoring'];executor=OpenAIExecutor(authority,self.store,self.selection['root_source'],self.runtime['authoring'])
        self.author_executor=executor
        pin,result=produce_all(self.author_selection,authority=authority,executor=executor,outer_store=self.store)
        self.authored=result;self.authored_pin=pin
        return {'status':'awaiting_fifty_genuine_independent_authoring_reviews','pending':pin}
    def compile(self,author_reviews_pin):
        need(self.authored is not None and 'campaign'in self.runtime and self.compiled is None,'actual authoring and runtime precede one frozen compilation')
        reviews=self.store.json(author_reviews_pin,8*2**20)
        contexts=campaign_contexts(self.store,self.code_views,self.selection['model']['prompt'],self.selection['context_selection']['programme'])
        from .cli import load_design
        design=load_design(self.store,self.selection['design'])
        recipe={**self.selection['source_recipe'],'code_views':self.code_views}
        self.compiled=compile_campaign(recipe,runtime=self.runtime['campaign'],authored=self.authored,
                                      author_reviews=reviews,contexts=contexts,design=design)
        prefix=self.selection['publication_prefix']
        self.programme_pin=self.store.write(prefix+'/PROGRAMME.json',canonical(self.compiled['programme']),16*2**20)
        return {'status':'awaiting_exact_programme_bound_E01_E02_E03_and_checkpoint_reviews',
                'programme':self.programme_pin,'programme_sha256':self.compiled['campaign']['programme_sha256']}
    def publish(self,preconditions_pin,checkpoint_reviews_pin,authority_pin,campaign_budget):
        need(self.compiled is not None and self.final is None,'one original final selection publication')
        launch_prefix=campaign_launch_prefix()
        authority=Authority.from_selected(self.store,authority_pin,self.selection['root_source'])
        compiled=attach_reviews(self.compiled,self.store.json(preconditions_pin,8*2**20),self.store.json(checkpoint_reviews_pin,16*2**20))
        # Actual Campaign initialization/Authority consumers validate every review.
        # This publication does not issue an acceptance or assert a runnable host.
        prefix=self.selection['publication_prefix']
        campaign=write_canonical(self.store,prefix+'/CAMPAIGN.json',compiled['campaign'],1024*2**20)
        final={'schema':'NLB017_operator_selection_v1','source_sha256':self.selection['root_source'],
            'authority':authority_pin,'budget':campaign_budget,'original_deadline':self.store.budget.deadline,
            'programme':self.programme_pin,'design':self.selection['design'],'campaign':campaign}
        closed(campaign_budget,Budget.KEYS)
        # F costs are joined exactly once by unchanged authoring.consume. Outer
        # preparation costs remain a separate original pool and are not erased.
        final_pin=self.store.write(prefix+'/OPERATOR_SELECTION.json',canonical(final),16*2**20)
        self.final=final_pin
        return {'selection':final_pin,'invoke':launch_prefix+['operator','--root',str(self.store.root),
                '--selection',final_pin['path'],'--selection-sha256',final_pin['sha256']],
                'original_deadline':self.store.budget.deadline,'independent_review_pauses_retained':True}


def main(argv=None):
    p=argparse.ArgumentParser(description='Concrete full NEURAL-017 preparation; explicit future authority only.')
    p.add_argument('--root',required=True);p.add_argument('--selection',required=True)
    p.add_argument('--selection-bytes',type=int,required=True);p.add_argument('--selection-sha256',required=True)
    p.add_argument('--limits',required=True,help='Exact seven-counter JSON preparation Budget; no defaults')
    p.add_argument('--original-deadline',type=float,required=True)
    args=p.parse_args(argv);owner=Custody('concrete_operator_preparation')
    budget=Budget(parse(args.limits.encode()),args.original_deadline,custody=owner)
    store=Store(args.root,budget,owner);coordinator=None
    try:
        selection=store.json({'path':args.selection,'bytes':args.selection_bytes,'sha256':args.selection_sha256},16*2**20)
        coordinator=OperatorPreparation(store,selection)
        from .cli import OperatorLines
        lines=OperatorLines(sys.stdin.fileno())
        while True:
            raw=lines.read(budget)
            if not raw:break
            message=parse(raw);op=message.get('operation')
            if op=='initialize':closed(message,{'operation'});result=coordinator.initialize()
            elif op=='paths':closed(message,{'operation','phase'});result=coordinator.paths(message['phase'])
            elif op=='contexts':closed(message,{'operation','authority'});result=coordinator.contexts(message['authority'])
            elif op=='qualify':
                closed(message,{'operation','phase','profiles','qualifications','authority'})
                result=coordinator.qualify(message['phase'],message['profiles'],message['qualifications'],message['authority'])
            elif op=='author':closed(message,{'operation'});result=coordinator.author()
            elif op=='compile':closed(message,{'operation','author_reviews'});result=coordinator.compile(message['author_reviews'])
            elif op=='publish':
                closed(message,{'operation','preconditions','checkpoint_reviews','authority','campaign_budget'})
                result=coordinator.publish(message['preconditions'],message['checkpoint_reviews'],message['authority'],message['campaign_budget'])
            else:raise ValueError('closed concrete preparation operation')
            out=canonical({'operation':op,'result':result});budget.charge('stream_bytes',len(out))
            sys.stdout.buffer.write(out);sys.stdout.buffer.flush()
        need(coordinator.final is not None,'original preparation EOF before complete selection')
        return 0
    except BaseException as error:
        owner.fail(error,'original_operator_preparation');owner.original_coordinator=coordinator
        # No deletion, rollback, fresh clock or synthetic completed result.
        sys.stderr.buffer.write(canonical({'status':'incomplete','original':owner.snapshot(),'budget':budget.snapshot()}))
        raise owner.first_error


if __name__=='__main__':raise SystemExit(main())
