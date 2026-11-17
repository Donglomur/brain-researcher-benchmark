"""One whole outer case per actor context; all private targets remain operator only."""
from pathlib import Path
from .core import need,digest,save
from .packets import build_packet
from .runtime import tree,check_tree
from .evaluation import development,paired_lifetime
from .protocol import ARMS,ALPHAS,choose

def invoke(packet,source,config,out,dispatcher,reference=False):
    out=Path(out);out.mkdir()
    # Config is public and identical across all three arms. It is passed as a
    # literal JSON file in the program directory, never interpolated into a shell.
    check_tree(source['tree'],dispatcher.budget)
    python=dispatcher.profile['python']
    if reference:
        trainargv=[python,'/source/worker.py','--stage','train','--alpha',str(config['alpha'])]
        queryargv=[python,'/source/worker.py','--stage','query']
    else:
        from .core import canonical
        trainargv=[python,'-I','-B','/source/program.py','--stage','train','--input','/input/0','--output','/output','--config-json',canonical(config).decode()]
        queryargv=[python,'-I','-B','/source/program.py','--stage','query','--input','/input/0','--model','/model','--output','/output','--config-json',canonical(config).decode()]
    dispatcher.budget.reserve(fits=1)
    train=dispatcher.run(trainargv,[packet['train']],source['directory'],out/'train','train')
    if train['launched']:dispatcher.budget.observe(fits=1)
    need(train['complete'],'fit failed; no query or fallback')
    # No query input or private targets were mounted for the fit.
    query=dispatcher.run(queryargv,[packet['query']],source['directory'],out/'query','query',model=train['outputs']['root'])
    paired_lifetime(train,query)
    return {'packet':packet,'train':train,'query':query}

def trial(panel,case,source,config,out,dispatcher,reference=False,investigator=None):
    out=Path(out);out.mkdir();records=[]
    for inner in case['inner']:
        for arm in ARMS:
            label=inner['context_id']+'-'+case['arms'][arm]
            packet=build_packet(panel,case,arm,out/(label+'-packet'),inner)
            actual_source,actual_config=source,config;investigation=None
            if investigator is not None:
                from .investigation import investigate
                actual_source,actual_config,investigation=investigate(packet,investigator['provider'],investigator['policy'],config,out/(label+'-investigation'))
            record=invoke(packet,actual_source,actual_config,out/label,dispatcher,reference)
            records.append({**record,'investigation':investigation,'actual_source_id':actual_source['metadata']['source_id'],'actual_config':actual_config})
    score=development(panel,records,dispatcher.budget)
    matched_id=digest(investigator['policy']) if investigator is not None else source['metadata']['source_id']
    row={'source_id':source['metadata']['source_id'] if source else None,'policy_id':matched_id if investigator else None,'config':config,'method_id':digest([matched_id,config]),
         'records':records,**score}
    save(out/'TRIAL.json',row,dispatcher.budget);return row

def finals(panel,case,source,config,out,dispatcher,role,protocol,reference=False,investigator=None):
    matched_id=digest(investigator['policy']) if investigator is not None else source['metadata']['source_id']
    out=Path(out);out.mkdir();rows=[];method=digest([matched_id,config])
    for arm in ARMS:
        label=case['arms'][arm];packet=build_packet(panel,case,arm,out/(label+'-packet'))
        actual_source,actual_config=source,config;investigation=None
        if investigator is not None:
            from .investigation import investigate
            actual_source,actual_config,investigation=investigate(packet,investigator['provider'],investigator['policy'],config,out/(label+'-investigation'))
        row=invoke(packet,actual_source,actual_config,out/label,dispatcher,reference)
        rows.append({**row,'role':role,'person':case['person'],'arm':arm,'method_id':method,'protocol_id':digest(protocol),
          'matching_level':'frozen_investigator_policy' if investigator else 'frozen_program_and_config',
          'actual_source_id':actual_source['metadata']['source_id'],'actual_config':actual_config,'investigation':investigation})
    save(out/'FINAL_CASE.json',rows,dispatcher.budget);return rows

