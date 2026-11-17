"""Portable NEURAL083 metadata composition; never imports or runs task code.

Preparation, model requests, Docker, scoring and positive authority are not
operations of this helper. All writes are create-only into a fresh directory.
The selected SOURCE.json pin is an external input, not self-issued authority.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

ROSTER = [(person,session) for person in range(1,55) for session in (1,2)]
FIELDS = ('schema','preparation_complete','preparation_closure','preparation_review','method_review',
    'entrant','tool_mode','provider_configuration','prompt','frozen_program','preparation_costs',
    'output','limits','other_future_bytes','docker_binary','docker_socket','image','memory_bytes',
    'fit_seconds','infer_seconds','query_seconds','max_model_calls_per_query','max_tool_calls_per_query',
    'model_input_token_budget','model_output_token_budget','model_request_budget',
    'model_cost_record_cap_bytes','completion_record_cap_bytes')
ORIGINAL_ERRORS=[]


def need(value,message):
    if not value:raise ValueError(message)


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def provider_encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def pin(raw):
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def parse(raw):
    def pairs(rows):
        result={}
        for key,value in rows:
            need(key not in result,'duplicate JSON key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))


def path(value):
    p=Path(value)
    need(p.is_absolute() and str(p)==os.path.normpath(str(p)) and
         not any(x.is_symlink() for x in (p,*p.parents)),'normalized unlinked absolute path')
    return p


class Metadata:
    def __init__(self):
        self.end=time.monotonic()+30;self.reads=0;self.writes=0
    def tick(self):need(time.monotonic()<self.end,'original metadata composition interval')
    def read(self,name,maximum,expected=None):
        self.tick();p=path(name);s=p.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=maximum,'bounded ordinary metadata/source')
        self.reads+=s.st_size+1;need(self.reads<=8388608,'8MiB metadata/source read ceiling')
        stamp=lambda v:(v.st_dev,v.st_ino,v.st_mode,v.st_nlink,v.st_size,v.st_mtime_ns,v.st_ctime_ns)
        fd=None;parts=[];first=None;later=None
        try:
            fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            need(stamp(s)==stamp(os.fstat(fd)),'opened source identity')
            left=s.st_size
            while left:
                self.tick();block=os.read(fd,min(left,65536));need(bool(block),'short source read')
                parts.append(block);left-=len(block)
            need(not os.read(fd,1),'source extent changed')
            need(stamp(s)==stamp(os.fstat(fd))==stamp(p.lstat()),'stable source identity')
        except BaseException as error:first=error
        finally:
            if fd is not None:
                try:os.close(fd)
                except BaseException as error:later=error
        if first or later:
            ORIGINAL_ERRORS.append((first,later,tuple(parts)))
            if first and later:first.add_note('Secondary metadata close: '+repr(later))
            raise first or later
        raw=b''.join(parts)
        if expected is not None:need(pin(raw)==expected,'exact selected metadata/source pin')
        self.tick();return raw
    def descriptor(self,name,maximum=1048576):
        p=path(name);return dict(path=str(p),**pin(self.read(p,maximum)))
    def put(self,root,name,value):
        self.tick();need(Path(name).name==name,'fixed output basename')
        raw=encoded(value);self.writes+=len(raw);need(self.writes<=2097152,'2MiB metadata write ceiling')
        p=root/name;fd=None;first=None;later=None
        try:
            fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
            done=0
            while done<len(raw):
                self.tick();n=os.write(fd,raw[done:done+65536]);need(n>0,'metadata write progress');done+=n
            os.fsync(fd)
        except BaseException as error:first=error
        finally:
            if fd is not None:
                try:os.close(fd)
                except BaseException as error:later=error
        if first or later:
            ORIGINAL_ERRORS.append((first,later,raw))
            if first and later:first.add_note('Secondary output close: '+repr(later))
            raise first or later
        self.tick();return dict(path=str(p),**pin(raw))


def exact_pin(value):
    need(type(value)is dict and set(value)=={'bytes','sha256'} and type(value['bytes'])is int
         and 0<value['bytes']<=1048576 and type(value['sha256'])is str
         and re.fullmatch('[0-9a-f]{64}',value['sha256']),'exact source pin')
    return value


def source(meta,root,selected):
    raw=meta.read(root/'SOURCE.json',262144,exact_pin(selected));table=parse(raw)
    need(set(table)=={'schema','files','inherited'} and table['schema']=='neural083_case_adaptive_source_v1',
         'actual adaptive source manifest')
    need(type(table['files'])is dict and 1<=len(table['files'])<=32,'finite adaptive sources')
    for name,row in table['files'].items():
        need(Path(name).name==name,'source basename');meta.read(root/name,1048576,exact_pin(row))
    inherited_raw=meta.read(root/'inherited/SOURCE.json',131072,exact_pin(table['inherited']))
    old=parse(inherited_raw)
    need(set(old)=={'schema','files'} and old['schema']=='neural083_preparation_programme_source_v1'
         and type(old['files'])is dict and 1<=len(old['files'])<=96,'full inherited closure')
    for name,row in old['files'].items():
        need(not Path(name).is_absolute() and all(x not in ('','.','..') for x in name.split('/'))
             and '\\' not in name,'closed inherited source member')
        meta.read(root/'inherited'/name,1048576,exact_pin(row))
    return table,old


def configuration(raw):
    value=parse(raw)
    need(type(value)is dict and set(value)==set(FIELDS) and value['schema']=='neural083_case_adaptive_selection_v1',
         'actual closed configuration keys')
    need(value['entrant'] in ('frozen_program','case_adaptive_equal_inputs_tools_compute','decoder_alone')
         and value['tool_mode'] in ('generic_numerical','agent_plus_decoder','decoder_alone'),'actual entrant/tool modes')
    need((value['entrant']=='decoder_alone')==(value['tool_mode']=='decoder_alone'),'decoder-only mode pairing')
    return value


def selected_resources(value):
    names=('fit_seconds','infer_seconds','query_seconds','max_model_calls_per_query','max_tool_calls_per_query',
           'memory_bytes','model_cost_record_cap_bytes','completion_record_cap_bytes')
    need(all(type(value[k])is int and value[k]>0 for k in names),'actual positive non-Boolean resource selections')
    need(1<=value['max_tool_calls_per_query']<=16 and 1<=value['max_model_calls_per_query']<=8
         and 1<=value['fit_seconds']<=3600 and value['max_tool_calls_per_query']<=value['infer_seconds']<=3600
         and value['infer_seconds']<value['query_seconds']<=86400 and value['memory_bytes']>=268435456,
         'actual complete per-query/native policy')
    need(type(value['limits'])is dict and set(value['limits'])==
         {'reads','writes','retained','free_floor_bytes','whole_seconds','observer_seconds'}
         and all(type(v)is int and v>0 for v in value['limits'].values())
         and value['limits']['observer_seconds']==30 and 60<value['limits']['whole_seconds']<=604800,
         'actual whole operation metadata/resource selections')
    need(type(value['image'])is str and re.fullmatch('sha256:[0-9a-f]{64}',value['image'])
         and value['image']!='sha256:'+'0'*64,'actual selected image identity, not template')
    for k in ('other_future_bytes','model_input_token_budget','model_output_token_budget','model_request_budget'):
        need(type(value[k])is int and value[k]>=0,'actual nonnegative selected accounting quantity')


def configuration_pin(value):
    return pin(encoded({k:v for k,v in value.items() if k!='method_review'}))


def actions(mode):
    result={
        'python':{'type':'object','properties':{'code':{'type':'string','minLength':1,'maxLength':65536}},
                  'required':['code'],'additionalProperties':False},
        'predict':{'type':'object','properties':{'p_right':{'type':'number','minimum':0,'maximum':1}},
                   'required':['p_right'],'additionalProperties':False},
        'abstain':{'type':'object','properties':{'reason':{'type':'string','minLength':1,'maxLength':256}},
                   'required':['reason'],'additionalProperties':False}}
    if mode=='agent_plus_decoder':result['decoder']={'type':'object','properties':{},'required':[],'additionalProperties':False}
    return result


def frozen_descriptor(meta,spec,cap):
    need(type(spec)is dict and set(spec)=={'path','bytes','sha256'},'supplied exact metadata descriptor')
    meta.read(path(spec['path']),cap,exact_pin({k:spec[k] for k in ('bytes','sha256')}))
    return spec


def prepare_request(meta,root,table,old,args,output):
    kind=args.command.removeprefix('prepare-')
    value=parse(meta.read(path(args.configuration),262144))
    common={'schema','source_manifest','source_inventory','records_root','deadline_ns','limits'}
    extra={'source_root','schema_bindings','max_record_output_bytes'} if kind=='project' else {'projection_record','identity_key','product_root'}
    need(set(value)==common|extra and value['schema']=='neural083_'+kind+'_request_v1','complete preparation request schema')
    need(type(value['deadline_ns'])is int and value['deadline_ns']>time.monotonic_ns(),
         'actual original future preparation deadline, not a placeholder')
    need(type(value['limits'])is dict and set(value['limits'])=={'read_bytes','write_bytes','retained_bytes'}
         and all(type(v)is int and 65536<=v<=1000000000000 for v in value['limits'].values()),
         'actual complete preparation budgets')
    if kind=='project':
        need(type(value['max_record_output_bytes'])is int and
             200*251*20*4+100000<value['max_record_output_bytes']<=8000000,
             'full record serialization and metadata ceiling')
    inventory_path=root/'inherited/preparation/source-inventory.json'
    expected=old['files']['preparation/source-inventory.json']
    inventory=parse(meta.read(inventory_path,200000,exact_pin(expected)))
    value['source_inventory']=dict(path=str(inventory_path),**expected)
    for key in ('records_root','source_root','product_root'):
        if key in value:
            protected=path(value[key])
            need(output!=protected and output not in protected.parents and protected not in output.parents,
                 'preparation metadata output disjoint from data/product roots')
    manifest_spec=value['source_manifest'];need(type(manifest_spec)is dict and 'path' in manifest_spec,'selected source manifest path')
    raw=meta.read(path(manifest_spec['path']),100000);manifest=parse(raw)
    need(set(manifest)=={'schema','files'} and manifest['schema']=='neural083_verified_sources_v1'
         and len(manifest['files'])==108 and len(inventory['files'])==108,'full exact source roster')
    seen=set()
    for (person,session),row,original in zip(ROSTER,manifest['files'],inventory['files']):
        need(set(row)=={'person','session','path','bytes','sha256'} and (row['person'],row['session'])==(person,session)
             and all(row[k]==original[k] for k in ('person','session','path','bytes')),'original full member identity/extent')
        need(type(row['sha256'])is str and re.fullmatch('[0-9a-f]{64}',row['sha256']) and row['sha256'] not in seen,
             'distinct externally measured source digests; no data read here');seen.add(row['sha256'])
    value['source_manifest']=dict(path=str(path(manifest_spec['path'])),**pin(raw))
    if kind=='project':
        need(type(value['schema_bindings'])is list and len(value['schema_bindings'])==108,'all108 observed schema bindings')
        for (person,session),row in zip(ROSTER,value['schema_bindings']):
            need(set(row)=={'person','session','binding'} and (row['person'],row['session'])==(person,session),'binding identity order')
            spec=row['binding'];binding_raw=meta.read(path(spec['path']),65536);binding=parse(binding_raw)
            need(set(binding)=={'schema','channel_order','class_names_field','class_codes'}
                 and binding['schema']=='neural083_observed_mat_schema_v1','actual binding schema')
            need(type(binding['channel_order'])is list and len(binding['channel_order'])==62
                 and all(type(x)is str and x for x in binding['channel_order']) and len(set(binding['channel_order']))==62,
                 'all62 original observed channel names; placeholders refused')
            need(binding['class_names_field'] in ('class','y_class') and set(binding['class_codes'])=={'left','right'}
                 and all(type(x)is int for x in binding['class_codes'].values())
                 and binding['class_codes']['left']!=binding['class_codes']['right'],'observed class semantics')
            row['binding']=dict(path=str(path(spec['path'])),**pin(binding_raw))
    else:
        value['projection_record']=meta.descriptor(path(value['projection_record']['path']),4000000)
        # Do not open, generate, copy, print or hash the separately supplied key.
        key=value['identity_key'];need(set(key)=={'path','bytes','sha256'} and key['bytes']==32,'external32-byte key descriptor')
        path(key['path']);need(re.fullmatch('[0-9a-f]{64}',key['sha256']) is not None,'external key digest')
    need(args.owner_selection is not None and args.evidence_output is not None,'explicit preparation owner limits/evidence path')
    owner=parse(meta.read(path(args.owner_selection),65536))
    need(set(owner)=={'whole_seconds','limits'} and set(owner['limits'])=={'read_bytes','write_bytes','retained_bytes'}
         and all(type(v)is int and 65536<=v<=64*1024**2 for v in owner['limits'].values())
         and type(owner['whole_seconds'])is int and 30<owner['whole_seconds']<=604800,'finite original preparation owner selection')
    now=time.monotonic_ns()
    need(now<value['deadline_ns']<=now+(owner['whole_seconds']-15)*1000000000,
         'preparation deadline fits selected future owner work interval; actual owner rechecks it')
    spec=meta.put(output,'PREPARATION_REQUEST.json',value)
    request={'schema':'neural083_integration_operation_v1','operation':args.command,'source':table['inherited'],
             'output':str(path(args.evidence_output)),'limits':owner['limits'],'whole_seconds':owner['whole_seconds'],
             'inputs':{'preparation_request':spec}}
    req=meta.put(output,'OWNER_REQUEST.json',request)
    auth=meta.put(output,'AUTHORITY.DISABLED.json',{'schema':'neural083_integration_root_authority_v1',
         'operation':args.command,'configuration':{k:req[k] for k in ('bytes','sha256')},
         'source':table['inherited'],'execution_authorized':False})
    argv=[str(Path(sys.executable).resolve()),'-I','-S','-B',str(root/'inherited/entry.py'),args.command,
          '--source-pin',json.dumps(table['inherited']),'--request',json.dumps(req),'--authority',json.dumps(auth),
          '--whole-seconds',str(owner['whole_seconds']),'--read-limit',str(owner['limits']['read_bytes']),
          '--write-limit',str(owner['limits']['write_bytes']),'--retained-limit',str(owner['limits']['retained_bytes'])]
    meta.put(output,'COMMAND.NOT_EXECUTED.json',{'argv':argv,'execution_authorized':False,
             'requires_separately_issued_root_authority':True,'records':108,'conditions':2592})


def main():
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('command',choices=('draft','bind-costs','bind-method','request','prepare-project','prepare-finalize','extract-terminal'))
    parser.add_argument('--source-root',type=Path,default=Path(__file__).absolute().parent/'package')
    parser.add_argument('--source-pin',required=True)
    parser.add_argument('--configuration',type=Path,required=True)
    parser.add_argument('--provider-study',type=Path)
    parser.add_argument('--costs',type=Path)
    parser.add_argument('--method',type=Path)
    parser.add_argument('--operation',choices=('inspect','run','grade'))
    parser.add_argument('--evidence-output',type=Path)
    parser.add_argument('--terminal',type=Path)
    parser.add_argument('--outer-proof',type=Path)
    parser.add_argument('--owner-selection',type=Path)
    parser.add_argument('--outer-run',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();meta=Metadata();root=path(args.source_root)
    selected=exact_pin(parse(args.source_pin));table,old=source(meta,root,selected)
    output=path(args.output)
    need(not os.path.lexists(output) and output!=root and output not in root.parents and root not in output.parents,
         'fresh metadata output disjoint from authenticated task sources')
    if args.command.startswith('prepare-'):
        output.mkdir(mode=0o700)
        prepare_request(meta,root,table,old,args,output)
        meta.tick();print(json.dumps({'status':'preparation_metadata_only','output':str(output),
                                    'execution_authorized':False,'records':108,'conditions':2592}));meta.tick();return
    config=configuration(meta.read(path(args.configuration),1048576))
    # Metadata composition is separate from the canonical arrays, protected
    # products and actual programme/evidence directories supplied by operators.
    for field in ('output','preparation_complete'):
        value=config[field];protected=path(value['path']).parent if type(value)is dict else path(value)
        need(output!=protected and output not in protected.parents and protected not in output.parents,
             'metadata bundle disjoint from protected/programme output')
    output.mkdir(mode=0o700)
    if args.command=='draft':
        selected_resources(config)
        need(config['preparation_costs'] is None and config['method_review'] is None,
             'draft starts before external cost/method documents')
        for field in ('preparation_complete','preparation_closure','preparation_review'):
            frozen_descriptor(meta,config[field],1048576)
        if config['entrant']=='case_adaptive_equal_inputs_tools_compute':
            need(args.provider_study is not None,'actual selected provider study required')
            study=parse(meta.read(path(args.provider_study),262144))
            need(set(study)=={'endpoint','model','generation','caps','declared_rates'},
                 'study operands exclude source/action bindings, which are source-derived')
            study.update(actions=actions(config['tool_mode']),
                         provider_source_sha256=table['files']['local_chat_provider.py']['sha256'])
            provider={'study':study,'frozen_study_config_sha256':hashlib.sha256(provider_encoded(study)).hexdigest()}
            config['provider_configuration']=meta.put(output,'PROVIDER.json',provider)
            frozen_descriptor(meta,config['prompt'],32768)
            need(config['frozen_program'] is None,'adaptive entrant has no frozen comparator body')
            calls=129600*config['max_model_calls_per_query']
            need(type(study['caps']['reported_prompt_tokens'])is int and study['caps']['reported_prompt_tokens']>0
                 and type(study['generation']['max_output_tokens'])is int and study['generation']['max_output_tokens']>0,
                 'actual nonzero token caps')
            floor={'model_request_budget':calls,
                   'model_input_token_budget':calls*study['caps']['reported_prompt_tokens'],
                   'model_output_token_budget':calls*study['generation']['max_output_tokens']}
            need(all(config[k]>=v for k,v in floor.items()),'full model reservation floors; no reduced roster')
        else:
            need(args.provider_study is None and config['provider_configuration'] is None and config['prompt'] is None,
                 'no model provider in frozen/decoder-only mode')
            if config['entrant']=='frozen_program':frozen_descriptor(meta,config['frozen_program'],65536)
            else:need(config['frozen_program'] is None,'decoder only has no arbitrary programme')
            floor={'model_request_budget':0,'model_input_token_budget':0,'model_output_token_budget':0}
        meta.put(output,'MODEL_RESERVATION_FLOORS.json',{'candidate_queries':129600,'floors':floor,
                 'not_a_complete_compute_or_storage_budget':True})
        meta.put(output,'CONFIGURATION_BASE.json',config)
        meta.put(output,'PREPARATION_COST_BINDING.json',{'schema':'neural083_setup_cost_binding_v1',
                 'configuration':configuration_pin({**config,'preparation_costs':None}),
                 'produces_actual_cost_document':False})
    elif args.command=='bind-costs':
        need(args.costs is not None and config['preparation_costs'] is None and config['method_review'] is None,
             'cost binding is a separate once-only stage')
        raw=meta.read(path(args.costs),262144);costs=parse(raw)
        need(costs.get('schema')=='neural083_matched_preparation_costs_v1'
             and costs.get('configuration')==configuration_pin({**config,'preparation_costs':None}),
             'actual externally supplied preparation cost binding')
        config['preparation_costs']=dict(path=str(path(args.costs)),**pin(raw))
        meta.put(output,'CONFIGURATION_WITH_COSTS.json',config)
        meta.put(output,'METHOD_BINDING.json',{'schema':'neural083_setup_method_binding_v1','source':selected,
                 'configuration':configuration_pin(config),
                 'preparation_complete':{k:config['preparation_complete'][k] for k in ('bytes','sha256')},
                 'produces_independent_method_review':False})
    elif args.command=='bind-method':
        need(args.method is not None and config['method_review'] is None and config['preparation_costs'] is not None,
             'method binding follows frozen external costs')
        frozen_descriptor(meta,config['preparation_costs'],262144)
        raw=meta.read(path(args.method),262144);method=parse(raw)
        need(method.get('schema')=='neural083_case_adaptive_method_admission_v1'
             and method.get('source')==selected and method.get('configuration')==configuration_pin(config)
             and method.get('preparation_complete')=={k:config['preparation_complete'][k] for k in ('bytes','sha256')},
             'externally issued review bound to exact source/configuration/preparation')
        config['method_review']=dict(path=str(path(args.method)),**pin(raw))
        meta.put(output,'CONFIGURATION.json',config)
    elif args.command=='extract-terminal':
        need(args.outer_run is not None,'actual outer run receipt required')
        outer=parse(meta.read(path(args.outer_run),4000000))
        need(outer.get('schema')=='neural083_adaptive_outer_v1' and outer.get('source')==selected
             and outer.get('operation')=='run' and outer.get('configuration')==
             pin(meta.read(path(args.configuration),1048576)),'same source/configuration actual outer receipt')
        terminal=outer['worker_terminal']
        need(terminal.get('schema')=='neural083_adaptive_worker_terminal_v1'
             and terminal.get('source')==selected and terminal.get('operation')=='run','actual run terminal wrapper')
        meta.put(output,'RUN_WORKER_TERMINAL.json',terminal)
        meta.put(output,'EXTRACTION.json',{'independent_outer_admission_issued':False,
                 'grading_authorized':False,'result_pin_for_independent_outer_proof':pin(encoded(terminal['result']))})
    else:
        need(args.operation is not None and args.evidence_output is not None,'actual operation/evidence path')
        request={'schema':'neural083_adaptive_operator_request_v1','operation':args.operation,
                 'configuration':meta.descriptor(path(args.configuration)),
                 'evidence_output':str(path(args.evidence_output)),'grade_inputs':None}
        if args.operation=='grade':
            need(args.terminal is not None and args.outer_proof is not None,'actual separate grade operands')
            request['grade_inputs']={'terminal':meta.descriptor(path(args.terminal),65536),
                                     'outer_proof':meta.descriptor(path(args.outer_proof),65536)}
        else:need(args.terminal is None and args.outer_proof is None,'run/inspect never receives grading operands')
        req=meta.put(output,'REQUEST.json',request)
        authority={'schema':'neural083_adaptive_root_authority_v1','source':selected,
                   'request':{k:req[k] for k in ('bytes','sha256')},'operation':args.operation,'execution_authorized':False}
        auth=meta.put(output,'AUTHORITY.DISABLED.json',authority)
        argv=[str(Path(sys.executable).resolve()),'-I','-S','-B',str(root/'entry.py'),args.operation,
              '--source-pin',json.dumps(selected),'--request',json.dumps(req),
              '--whole-seconds',str(config['limits']['whole_seconds'])]
        if args.operation!='inspect':argv+=['--authority',json.dumps(auth)]
        meta.put(output,'COMMAND.NOT_EXECUTED.json',{'argv':argv,'execution_authorized':False,
                 'authority_descriptor_must_reference_a_separately_issued_document':args.operation!='inspect'})
    meta.tick()
    print(json.dumps({'status':'metadata_only','source':selected,'output':str(output),
                      'records':108,'conditions':2592,'execution_authorized':False,
                      'reads':meta.reads,'writes':meta.writes},sort_keys=True))
    meta.tick()


if __name__=='__main__':main()
