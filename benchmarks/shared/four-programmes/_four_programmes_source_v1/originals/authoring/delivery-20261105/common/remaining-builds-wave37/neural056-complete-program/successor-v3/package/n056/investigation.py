"""Fresh bounded investigator state for one training context and one arm."""
from pathlib import Path
import ast
from .core import need,digest,read_json,save,write_new,canonical
from .actors import admit_program
from .runtime import tree
def investigate(packet,provider,policy,base_config,destination):
    """No history/program/model escapes into another context's provider request."""
    out=Path(destination);out.mkdir();history=[];b=provider.budget;d=provider.dispatcher
    meta=read_json(Path(packet['train'])/'context.json',budget=b)
    # Private operator fields (person, arm mapping, inner target, query indices)
    # never enter the model request. Only this context's training metadata does.
    public={k:meta[k] for k in ('schema','context_id','arm_id','train_rows','feature_count',
                               'response_shape','seed','query_EEG_present','fit_only')}
    policy_id=digest(policy)
    need(type(policy['max_rounds'])is int and 1<=policy['max_rounds']<=16,'finite investigative rounds')
    for index in range(policy['max_rounds']):
        request={'mode':'I','fixed_policy':policy['prompt'],'policy_id':policy_id,
          'trial_configuration':base_config,'own_training_context':public,
          'round':index,'history':history,'tool_contract':policy['tool_contract'],
          'answer_schema':{'inspect':{'action':'inspect','python':'standalone Python writing /output/analysis.json'},
                           'final':{'action':'final','program':'train/query CLI Python source','config':'finite JSON object'}},
          'no_other_context_or_held_targets_available':True}
        answer,provider_receipt=provider.ask(request,out/('round-'+str(index)),policy['tokens_per_round'])
        need(type(answer)is dict and answer.get('action') in ('inspect','final'),'typed investigation action')
        if answer['action']=='final':
            need(set(answer)=={'action','program','config'},'exact final action')
            program=admit_program({'program':answer['program'],'configs':[answer['config']]},out/'program',1,b,'I')
            receipt={'policy_id':policy_id,'base_config':base_config,'public_context':public,
              'actual_source_id':program['metadata']['source_id'],'actual_config':answer['config'],
              'history':history,'final_provider':provider_receipt,'fresh_context':True,
              'query_inputs_seen_by_LLM':False,'held_response_access':False}
            save(out/'INVESTIGATION.json',receipt,b)
            return program,answer['config'],receipt
        need(set(answer)=={'action','python'} and type(answer['python'])is str
             and len(answer['python'].encode())<=policy['tool_source_bytes'],'bounded inspect Python')
        ast.parse(answer['python']);tool=out/('tool-source-'+str(index));tool.mkdir()
        write_new(tool/'inspect.py',answer['python'].encode(),b)
        run=d.run([d.profile['python'],'-I','-B','/source/inspect.py'],[packet['train']],
                  tool,out/('tool-'+str(index)),'train')
        need(run['complete'],'inspection original operation failed; no retry hidden from costs')
        need({x['relative'] for x in run['outputs']['members']}=={'analysis.json'},'inspection returns only bounded JSON')
        summary=read_json(Path(run['outputs']['root'])/'analysis.json',policy['tool_result_bytes'],budget=b)
        # Only this context's history is fed back. The selector receives scores,
        # never this history, raw views, embedded-source observations or models.
        history.append({'inspection_source':answer['python'],'analysis':summary,
                         'original_operation':{'complete':True,'exit_code':run['exit_code']}})
        save(out/('TOOL_RECEIPT_'+str(index)+'.json'),{'provider':provider_receipt,'tool':run},b)
    raise ValueError('investigator exhausted its original round allocation without sealed program')

