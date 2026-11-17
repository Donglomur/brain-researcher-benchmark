"""Concrete local-model transport and immutable generated-program admission."""
import ast
from pathlib import Path
from .core import need,read_json,capture,save,write_new,digest,byte_pin
from .runtime import tree,check_tree

class Provider:
    """Qualified local backend only; no automatic API credential/network path."""
    def __init__(self,profile,dispatcher,source,budget):
        self.profile=profile;self.dispatcher=dispatcher;self.source=source;self.budget=budget
        need(profile['kind']=='qualified_local_stdio_json_v1','selected local provider ABI')
        check_tree(profile['model'],budget)
        need(type(profile['argv'])is list and profile['argv'] and profile['argv'][0].startswith('/'),'qualified literal provider argv')
    def ask(self,request,destination,token_limits):
        out=Path(destination);out.mkdir();i=out/'input';i.mkdir()
        self.budget.reserve(model_calls=1,input_tokens=token_limits['input'],output_tokens=token_limits['output'])
        self.budget.observe(model_calls=1)
        save(i/'request.json',{'schema':'neural056_provider_request_v1','request':request,
             'limits':token_limits,'response_contract':'one response.json; program UTF8 and finite JSON config(s)'},self.budget)
        result=self.dispatcher.run(self.profile['argv'],[i],self.source,out/'call','provider',model=self.profile['model']['root'])
        need(result['complete'],'provider original lifetime incomplete')
        root=Path(result['outputs']['root']);need({x['relative'] for x in result['outputs']['members']}=={'response.json'},'exact provider output')
        response=read_json(root/'response.json',self.profile['response_bytes'],budget=self.budget)
        need(set(response)=={'schema','answer','usage'} and response['schema']=='neural056_provider_response_v1','qualified provider ABI')
        u=response['usage'];need(set(u)=={'input_tokens','output_tokens'} and all(type(v)is int and v>=0 for v in u.values()),'observed backend token use')
        need(u['input_tokens']<=token_limits['input'] and u['output_tokens']<=token_limits['output'],'provider exceeded token allocation')
        self.budget.observe(**u)
        return response['answer'],result

def admit_program(answer,destination,trial_count,budget,mode):
    need(type(answer)is dict and set(answer)=={'program','configs'},'exact generated programme')
    source=answer['program'];configs=answer['configs']
    need(type(source)is str and 0<len(source.encode())<=1024**2,'bounded UTF8 program')
    ast.parse(source);need(type(configs)is list and len(configs)==trial_count,'complete frozen trial list')
    for c in configs:
        need(type(c)is dict and len(str(c))<=65536,'bounded finite JSON config');digest(c)
    out=Path(destination);out.mkdir(mode=0o700)
    pin=write_new(out/'program.py',source.encode(),budget)
    meta={'schema':'neural056_generated_program_v1','mode':mode,'program':{k:pin[k] for k in ('bytes','sha256')},
          'configs':configs,'source_id':digest({'program':byte_pin(source.encode()),'configs':configs})}
    save(out/'PROGRAM.json',meta,budget)
    return {'directory':str(out),'metadata':meta,'tree':tree(out,2*1024**2,3,budget)}

def author_frozen(provider,documentation,configs,rounds,destination,tokens):
    """All authoring precedes neural views; finite source revision history only."""
    need(type(rounds)is int and rounds>0,'positive selected authoring rounds')
    out=Path(destination);out.mkdir();prior=None;receipts=[]
    for index in range(rounds):
        request={'mode':'F','task':documentation,'trial_configs':configs,
          'answer_schema':{'program':'train/query CLI Python source','configs':configs},
          'all_neural_views_withheld':True,'previous_source':prior,'revision_index':index,
          'instruction':'Return the complete improved program and the unchanged configuration roster.'}
        answer,receipt=provider.ask(request,out/('round-'+str(index)),tokens)
        need(type(answer)is dict and answer.get('configs')==configs,'pre-view configurations unchanged')
        need(type(answer.get('program'))is str and len(answer['program'].encode())<=1024**2,'bounded source')
        ast.parse(answer['program']);prior=answer;receipts.append(receipt)
    return prior,receipts

