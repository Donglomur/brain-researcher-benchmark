"""Full programme construction, not multiplication of canonical task counts."""
from .io import need,digest
from .source import TASKS,FULL,configuration,paper,neural

PAPER_ARMS=('paper_data','paper_data_author_code')
VIEWS45=(('appetitive','retrospective'),('appetitive','cue_time'),('aversive','retrospective'))
ENDPOINTS46=(('appetitive','cue'),('appetitive','reward'),('appetitive','omission'),('appetitive','delivery'),('aversive','aversive'))

def corpus_binding(binding):
    need(set(binding)=={'corpus_id','version','asset_manifest_sha256','biological_registry_sha256','views','synthetic'},'one corpus binding')
    need(binding['corpus_id']=='reward-spacing-10.1038-s41593-026-02206-2' and type(binding['synthetic']) is bool,'shared corpus identity')
    for key in ('asset_manifest_sha256','biological_registry_sha256'):
        need(isinstance(binding[key],str) and len(binding[key])==64 and all(c in '0123456789abcdef' for c in binding[key]),'corpus metadata digest')
    need(set(binding['views'])=={'paper','neural'} and all(isinstance(v,str) and len(v)==64 for v in binding['views'].values()),'two source export views of one corpus')
    # A release label/export/registry digest is not evidence of new animals.
    # This ledger is scoped to one physical source family. New replication needs
    # separately authenticated alias lineage; no metadata-only reset is admitted.
    return digest({'corpus_id':binding['corpus_id'],'synthetic':binding['synthetic']})

def conditions(task):
    need(task in TASKS,'existing canonical task')
    if task==TASKS[0]:return [FULL,'paper_data','paper_data_author_code','reproduction','improvement']
    matrix,_=neural('contracts').specifications()
    return [FULL]+[c['cell_id'] for c in matrix['cells']]

def construct(task,condition,registry,binding):
    condition=condition or FULL;need(condition in conditions(task),'registered named route')
    config=configuration();scope=paper('pipeline').full_scope(config)
    need(set(registry)==set(scope['conditions']),'all thirteen conditions retained')
    aliases=set();animals=set()
    for name,record in registry.items():
        need(set(record)=={'state','reason','animals'} and record['state'] in ('verified','source_unavailable','behavior_only_no_neural_target'),'condition support state')
        need(isinstance(record['reason'],str) and isinstance(record['animals'],list),'support reason/animals')
        for a in record['animals']:
            need(set(a)=={'id','aliases','neural_designated'} and isinstance(a['id'],str) and a['id'] not in animals and a['aliases'] and type(a['neural_designated']) is bool,'biological registry entry')
            need(len(a['aliases'])==len(set(a['aliases'])) and not(aliases&set(a['aliases'])),'cross-condition source alias overlap')
            need(not a['neural_designated'] or name in paper('observations').D_CONDITIONS,'behavior-only cohort has no fabricated neural designation')
            animals.add(a['id']);aliases.update(a['aliases'])
    corpus_key=corpus_binding(binding);need(binding['biological_registry_sha256']==digest(registry),'same complete biological registry binding');slots=[]
    if task==TASKS[0]:
        arms=(condition,) if condition in PAPER_ARMS else PAPER_ARMS
        modes=(condition,) if condition in ('reproduction','improvement') else ('reproduction','improvement')
        for arm in arms:
            for mode in modes:
                slots.append({'id':arm+'/'+mode,'kind':'paper_'+mode,'arm':arm,'mode':mode,'required':True,
                              'full_panel_ids':scope['panels'] if mode=='reproduction' else [],'conditions':scope['conditions']})
    else:
        matrix,_=neural('contracts').specifications()
        chosen=matrix['cells'] if condition==FULL else [c for c in matrix['cells'] if c['cell_id']==condition]
        for c in chosen:
            profile=VIEWS45 if task=='NEURAL-045' else ENDPOINTS46
            for domain,view_or_endpoint in profile:
                for fold_kind in ('animal','condition'):
                    membership=[(name,a) for name,row in registry.items() for a in row['animals']
                                if a['neural_designated'] and (name.startswith('FC-'))==(domain=='aversive')]
                    helds=sorted({a['id'] if fold_kind=='animal' else name for name,a in membership})
                    # An absent native population remains a required, unscorable template.
                    for held in helds or ['SOURCE_POPULATION_UNAVAILABLE']:
                        endpoint='cue' if task=='NEURAL-045' else view_or_endpoint
                        view=view_or_endpoint if task=='NEURAL-045' else 'retrospective'
                        status='applicable'
                        try:neural('contracts').assert_endpoint_applicable(c['cell_id'],task,endpoint,'packet_evidence' if c['tier']=='P' else 'numerical')
                        except ValueError as e:status='structurally_inapplicable: '+str(e)
                        if held=='SOURCE_POPULATION_UNAVAILABLE' and status=='applicable':status='source_unavailable'
                        ident='/'.join((c['cell_id'],domain,view_or_endpoint,fold_kind,held))
                        slots.append({'id':ident,'kind':'packet' if c['tier']=='P' else 'neural_numeric','cell_id':c['cell_id'],
                            'mode':c['mode'],'tier':c['tier'],'domain':domain,'view':view,'endpoint':endpoint,
                            'fold_kind':fold_kind,'held':held,'applicability':status,'required':True})
    need(len({s['id'] for s in slots})==len(slots),'unique full programme slots')
    return {'schema':'reward_complete_central_setup_v1','task':task,'condition':condition,'full_default':condition==FULL,
        'canonical_ids':list(TASKS),'independent_corpora':1,'corpus_key':corpus_key,'binding':binding,
        'condition_registry':registry,'scope':scope,'neural_cell_count':84,'slots':slots,
        'primary_claim':'reproduction and available-case exploratory improvement' if task==TASKS[0] else 'protected numerical evidence subject to all scientific gates; P interpretation distinct',
        'scientific_qualification':False,'deployment':'unconfigured','canonical_count_delta':0}

def paired_access(access):
    need(set(access)==set(PAPER_ARMS),'paired access arms')
    a,b=(access[k] for k in PAPER_ARMS)
    keys={'actor_lineage','context_id','paper_pins','data_pins','tool_contract','budget','prompt_sha256','ordinary_author_code'}
    need(set(a)==keys and set(b)==keys,'complete paired access contracts')
    need(a['context_id']!=b['context_id'],'independent paired contexts')
    need(all(a[k]==b[k] for k in keys-{'actor_lineage','context_id','ordinary_author_code'}),'matched paper/data/tools/budgets/prompts')
    need(not a['ordinary_author_code'] and b['ordinary_author_code'],'code difference only in B')
    roles=paper('pipeline').source_roles(configuration())['roles']
    allowed={(v['pin']['bytes'],v['pin']['sha256']) for v in roles.values()}
    need(all((p['bytes'],p['sha256']) in allowed for p in b['ordinary_author_code']),'captured ordinary author code only')
    return {'matched':True,'access_sha256':digest(access),'fresh_context_is_not_fresh_model_lineage':True}
