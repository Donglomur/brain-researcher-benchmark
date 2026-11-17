"""Prospective closed agent JSON envelopes; values never issue tool authority.

All bytes use the existing canonical encoder and full source-owned occurrence
rosters. The input constructor is a pure projection checked against already
admitted originals. It does not create those originals or dereference Pins.
The response parser returns an unadmitted action; a tool-specific closed ABI
and real original owner must still admit tool_call before any effect.
"""
import hashlib
from .common import need
from .backend_json import canonical,parse,scalar_text,_tree
from .precommit_records import validate_type

def _keys(value,keys):need(type(value)is dict and set(value)==set(keys),'all and only closed protocol fields')
def _pin(value):validate_type('Pin',value)
def _exact(raw,maximum):
    need(type(raw)is bytes and 0<len(raw)<=maximum,'full bounded original canonical JSON')
    value=parse(raw,maximum,maximum_depth=64,maximum_members=maximum,maximum_string_bytes=maximum)
    need(canonical(value,maximum)==raw,'exact source canonical representation; no duplicate/unknown alternate syntax')
    return value
def _bytes(value):
    _keys(value,('bytes','sha256','utf8'))
    scalar_text(value['utf8'],maximum=1048576);raw=value['utf8'].encode('utf8')
    need(type(value['bytes'])is int and value['bytes']==len(raw)and
         value['sha256']==hashlib.sha256(raw).hexdigest(),'exact complete source-owned UTF8 bytes and digest')
    return raw

def validate_public_request_v1(value):
    _keys(value,('schema','development_request','development_request_body','public_interface','public_ABI',
                 'view_inventory','products'))
    need(value['schema']=='four_agent_public_request_v1','current prospective request version')
    for key in ('development_request','public_interface','public_ABI','view_inventory'):_pin(value[key])
    validate_type('DevelopmentRequest',value['development_request_body']);d=value['development_request_body']
    raw=canonical(d,value['development_request']['bytes'])
    need(len(raw)==value['development_request']['bytes']and hashlib.sha256(raw).hexdigest()==value['development_request']['sha256'],
         'full same original DevelopmentRequest body')
    need(all(value[k]==d[k]for k in ('public_interface','public_ABI','view_inventory')),
         'same earlier admitted original public identities')
    products=value['products'];need(type(products)is list and len(products)<=8192,'complete finite original public roster')
    paths=[]
    for ordinal,product in enumerate(products):
        _keys(product,('ordinal','descriptor','source_occurrence','content'))
        need(type(product['ordinal'])is int and product['ordinal']==ordinal,'complete original ordered product occurrence')
        _pin(product['descriptor']);_pin(product['source_occurrence']);content=_bytes(product['content'])
        need(product['descriptor']['bytes']==len(content)and
             product['descriptor']['sha256']==hashlib.sha256(content).hexdigest(),'full exact public body, no truncation')
        paths.append(product['descriptor']['path'])
    need(paths==sorted(set(paths),key=lambda x:x.encode('utf8')),'whole unique unsigned UTF8 source roster')
    return value

def validate_transcript_v1(value):
    _keys(value,('schema','development_request','occurrences'))
    need(value['schema']=='four_agent_transcript_v1','current full transcript version');_pin(value['development_request'])
    rows=value['occurrences'];need(type(rows)is list and len(rows)<=8192,'full finite original transcript, no windowing')
    previous=None
    for ordinal,row in enumerate(rows):
        _keys(row,('ordinal','step_ordinal','kind','previous_occurrence','source_occurrence','source',
                   'request','result','cost_prefix','failure'))
        need(type(row['ordinal'])is int and row['ordinal']==ordinal and type(row['step_ordinal'])is int and
             0<=row['step_ordinal']<=ordinal,'complete ordered actual occurrence/step positions')
        need(row['kind']in ('agent_completion','tool_result'),'closed documentary occurrence kind')
        need(row['previous_occurrence']==previous,'full immediate original predecessor chain')
        _pin(row['source_occurrence']);_pin(row['source']);_bytes(row['request']);_bytes(row['result'])
        validate_type('CostPrefix',row['cost_prefix'])
        if row['failure']is not None:
            from .backend_native_v3_codec import validate_native_type
            validate_native_type('WireFailureProjectionV1',row['failure'])
        previous=row['source_occurrence']
    return value

def compile_public_products_v1(request,transcript,maximum):
    """Pure exact serialization; caller must check the complete original owners.

    In particular source_occurrence is documentary data. It is not an allowed
    replacement for the actual source-owned public exposure/tool/result handle.
    """
    validate_public_request_v1(request);validate_transcript_v1(transcript)
    need(transcript['development_request']==request['development_request'],'same original request/transcript')
    return canonical(request,maximum),canonical(transcript,maximum)

class ParsedAgentActionV1:
    """Unadmitted retained raw response projection; no execution method."""
    __slots__=('raw','body','kind','admitted')
    def __init__(self,raw,value):
        self.raw=raw;self.body=value;self.kind=value['action'];self.admitted=False

def parse_agent_action_v1(raw,maximum):
    value=_exact(raw,maximum)
    need(type(value)is dict and value.get('schema')=='four_agent_json_protocol_v1','fixed prospective response version')
    action=value.get('action')
    if action=='tool_call':
        _keys(value,('schema','action','tool','arguments'))
        _pin(value['tool'])
        # The exact arguments are already bounded/canonical parsed data. Their
        # tool-specific domain remains unadmitted until the actual earlier
        # selected tool ABI is checked. No generic callback runs here.
    elif action=='final_programme':
        _keys(value,('schema','action','programme'))
        validate_type('ProgrammeOutputManifest',value['programme'])
    else:need(False,'exactly one existing-tool or complete-programme action')
    return ParsedAgentActionV1(raw,value)

def validate_selected_tool_arguments_v1(action,selected_tool,closed_schema,maximum_depth,maximum_members):
    """Pure schema check only, never an actual tool invocation admission.

    The fixed original source-owned caller must obtain all operands from its
    independently selected existing tool ABI and verify same-owner provenance.
    Returning a value here still does not change action.admitted or grant work.
    """
    from .schema import check
    need(type(action)is ParsedAgentActionV1 and action.kind=='tool_call'and not action.admitted,
         'same original unconsumed parsed tool action')
    need(action.body['tool']==selected_tool,'existing exactly selected tool only')
    # Existing source validator, no supplied callable or newly executed schema
    # implementation. Its closed schema vocabulary is itself checked by check.
    need(type(maximum_depth)is int and 0<maximum_depth<=64 and type(maximum_members)is int and
         maximum_members>0,'same finite source-selected argument tree limits')
    _tree(action.body['arguments'],0,maximum_depth,[0],maximum_members)
    check(action.body['arguments'],closed_schema)
    return action
