"""Concrete bounded chat/tool HTTP wire; no actual provider is selected here.

The named wire is the operator-admitted chat-completions-compatible protocol.
Its actual model support, tokenizer/accounting, endpoint and spend enforcement
must be independently admitted. This is no claim of current vendor coverage.
"""
import http.client
import ssl
import base64
import struct
from urllib.parse import urlsplit
from wire import need, integer, check_pin, pin, encode, decode, body_pin, Refusal, Cleanup
from transport import deployment

class ProviderFailure(Refusal):
    def __init__(self, message, receipt):super().__init__(message);self.receipt=receipt

def image_dimensions(raw, mime):
    """Bounded header geometry, not a complete decoder or scientific admission."""
    if mime=='image/png':
        need(len(raw)>=33 and raw[:8]==b'\x89PNG\r\n\x1a\n' and raw[8:12]==b'\0\0\0\r' and raw[12:16]==b'IHDR','PNG signature/IHDR')
        return struct.unpack('!II',raw[16:24])
    need(mime=='image/jpeg' and raw[:2]==b'\xff\xd8','JPEG SOI')
    position=2
    while position<len(raw):
        need(raw[position]==255,'JPEG marker boundary')
        while position<len(raw) and raw[position]==255:position+=1
        need(position<len(raw),'JPEG marker');marker=raw[position];position+=1
        if marker in (0xD8,0xD9) or 0xD0<=marker<=0xD7:continue
        need(position+2<=len(raw),'JPEG segment length');size=int.from_bytes(raw[position:position+2],'big')
        need(size>=2 and position+size<=len(raw),'bounded complete JPEG segment')
        if marker in (0xC0,0xC1,0xC2):
            need(size>=8,'JPEG frame header');height=int.from_bytes(raw[position+3:position+5],'big');width=int.from_bytes(raw[position+5:position+7],'big')
            return width,height
        need(marker!=0xDA,'JPEG frame geometry before scan');position+=size
    raise Refusal('JPEG frame geometry unavailable')

def image_part(raw, mime, source_pin, limits, *, detail='auto'):
    need(type(raw) is bytes and mime in ('image/png','image/jpeg'),'exact PNG/JPEG source bytes')
    need(len(raw)<=integer(limits['max_image_bytes'],1),'source image byte ceiling')
    check_pin(source_pin);need(body_pin(raw)==source_pin,'exact source image content')
    width,height=image_dimensions(raw,mime)
    need(width>0 and height>0 and width*height<=integer(limits['max_image_pixels'],1),'bounded image geometry')
    need(detail in ('auto','low','high'),'declared image detail')
    url='data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')
    return {'part':{'type':'image_url','image_url':{'url':url,'detail':detail}},'source_pin':source_pin,
            'mime':mime,'width':width,'height':height,'full_decoder_or_neural_semantics_qualified':False}

def build_request(policy, messages, tools, limits, *, image_sources=None):
    base={'schema','model','temperature','seed','endpoint','policy_pin'}
    need(type(policy) is dict and base<=set(policy)<=base|{'image_capability'},'immutable investigator wire policy')
    need(policy['schema']=='operator_admitted_chat_completions_v1','named admitted protocol')
    check_pin(policy['policy_pin']);need(type(policy['model']) is str and policy['model'],'fixed model')
    required={'max_request_bytes','max_response_bytes','max_messages','max_tools','max_tool_calls',
              'max_generated_source_bytes','max_input_tokens','max_output_tokens','max_calls'}
    image_keys={'max_images','max_image_bytes','max_total_image_bytes','max_image_pixels'}
    need(type(limits) is dict and required<=set(limits)<=required|image_keys,'all bounded investigator extents')
    for value in limits.values():integer(value,1)
    need(type(messages) is list and len(messages)<=limits['max_messages'],'complete bounded conversation')
    image_sources={} if image_sources is None else image_sources
    need(type(image_sources) is dict,'exact image source inventory');used_images={};image_count=0;image_bytes=0
    for message in messages:
        need(type(message) is dict and message.get('role') in ('system','user','assistant','tool') and
             set(message)<= {'role','content','tool_calls','tool_call_id','name'},'declared conversation messages')
        content=message.get('content')
        need(content is None or type(content) in (str,list),'literal bounded message content')
        if type(content) is list:
            need(len(content)<=limits['max_request_bytes'],'bounded content parts')
            for part in content:
                need(type(part) is dict and part.get('type') in ('text','image_url'),'admitted text/image part')
                if part['type']=='text':
                    need(set(part)=={'type','text'} and type(part['text']) is str,'literal text part');continue
                capability=policy.get('image_capability')
                need(type(capability) is dict and set(capability)=={'admission_pin','message_roles','mime_types'},'independently admitted image capability')
                check_pin(capability['admission_pin']);need(message['role'] in capability['message_roles'],'model admits images for this role')
                need(image_keys<=set(limits),'complete image resource ceilings')
                need(set(part)=={'type','image_url'} and type(part['image_url']) is dict and
                     set(part['image_url'])=={'url','detail'},'literal inline image part')
                item=part['image_url'];url=item['url'];need(type(url) is str and item['detail'] in ('auto','low','high'),'inline image URL/detail')
                prefixes={'data:image/png;base64,':'image/png','data:image/jpeg;base64,':'image/jpeg'}
                prefix=next((p for p in prefixes if url.startswith(p)),None);need(prefix is not None,'data-only PNG/JPEG, no remote fetch')
                mime=prefixes[prefix];need(mime in capability['mime_types'],'admitted model MIME')
                need(len(url)-len(prefix)<=4*((limits['max_image_bytes']+2)//3),'encoded image extent before decode')
                raw_image=base64.b64decode(url[len(prefix):],validate=True);source=body_pin(raw_image)
                need(source['sha256'] in image_sources,'exact training-derived source image inventory')
                evidence=image_sources[source['sha256']]
                need(type(evidence) is dict and set(evidence)=={'source_pin','provenance_pin'} and evidence['source_pin']==source,'image source identity')
                check_pin(evidence['provenance_pin']);width,height=image_dimensions(raw_image,mime)
                need(len(raw_image)<=limits['max_image_bytes'] and width>0 and height>0 and
                     width*height<=limits['max_image_pixels'],'bounded exact image source/geometry')
                used_images[source['sha256']]=evidence;image_count+=1;image_bytes+=len(raw_image)
                need(image_count<=limits['max_images'] and image_bytes<=limits['max_total_image_bytes'],'full repeated-conversation image extent')
    need(set(used_images)==set(image_sources),'no unmatched image-source descriptors')
    need(type(tools) is list and len(tools)<=limits['max_tools'],'declared complete tool set')
    names=[]
    for tool in tools:
        need(type(tool) is dict and set(tool)=={'type','function'} and tool['type']=='function','concrete function tool')
        function=tool['function'];need(type(function) is dict and set(function)=={'name','description','parameters'},'exact fixed tool definition')
        need(type(function['name']) is str and function['name'],'fixed tool name');names.append(function['name'])
    need(len(set(names))==len(names),'unique permitted tools')
    request={'model':policy['model'],'temperature':policy['temperature'],'seed':policy['seed'],
        'max_completion_tokens':limits['max_output_tokens'],'messages':messages,'tools':tools,
        'tool_choice':'auto','stream':False}
    raw=encode(request,limits['max_request_bytes'])
    return {'body':raw,'request_pin':body_pin(raw),'policy_pin':policy['policy_pin'],
            'tool_names':names,'limits':dict(limits),'endpoint':policy['endpoint'],
            'image_sources':used_images,'image_count':image_count,'total_source_image_bytes':image_bytes}

def parse_response(raw, request):
    limits=request['limits'];reply=decode(raw,limits['max_response_bytes'])
    need(type(reply) is dict and type(reply.get('choices')) is list and len(reply['choices'])==1,'exactly one investigator choice; no best-of')
    choice=reply['choices'][0];need(choice.get('finish_reason') in ('stop','tool_calls'),'complete nontruncated investigator turn')
    message=choice.get('message');need(type(message) is dict and message.get('role')=='assistant','assistant message')
    content=message.get('content');need(content is None or type(content) is str,'assistant text')
    calls=message.get('tool_calls',[]);need(type(calls) is list and len(calls)<=limits['max_tool_calls'],'bounded tool actions')
    actions=[];ids=set();generated=len((content or '').encode('utf-8'))
    for call in calls:
        need(type(call) is dict and set(call)=={'id','type','function'} and call['type']=='function','tool-call schema')
        need(type(call['id']) is str and call['id'] and call['id'] not in ids,'fresh tool-call identity');ids.add(call['id'])
        function=call['function'];need(type(function) is dict and set(function)=={'name','arguments'},'literal function call')
        need(function['name'] in request['tool_names'] and type(function['arguments']) is str,'permitted tool and literal arguments')
        args_bytes=function['arguments'].encode('utf-8');generated+=len(args_bytes)
        need(generated<=limits['max_generated_source_bytes'],'total generated source/text extent')
        arguments=decode(args_bytes,limits['max_generated_source_bytes']);need(type(arguments) is dict,'object tool arguments')
        actions.append({'id':call['id'],'name':function['name'],'arguments':arguments,'literal_arguments_pin':body_pin(args_bytes)})
    need(generated<=limits['max_generated_source_bytes'],'total generated text extent')
    usage=reply.get('usage');need(type(usage) is dict and {'prompt_tokens','completion_tokens','total_tokens'}<=set(usage),'actual provider usage required')
    for k in ('prompt_tokens','completion_tokens','total_tokens'):integer(usage[k])
    need(usage['prompt_tokens']<=limits['max_input_tokens'] and usage['completion_tokens']<=limits['max_output_tokens'] and
         usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens'],'observed usage fits reserved envelope')
    return {'analysis':content or '', 'actions':actions,'usage':{k:usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens')},
        'response_pin':body_pin(raw),'request_pin':request['request_pin'],'policy_pin':request['policy_pin'],
        'finished':choice['finish_reason'],'scientific_result_or_method_success_claimed':False}

def send_https(request, policy, deployment_path, deployment_pin, ledger, authorization_header):
    admitted=deployment(deployment_path,deployment_pin,ledger,'provider')
    check_pin(admitted['spend_authority'])
    selected=admitted['investigator']
    need(type(selected) is dict and set(selected)=={'policy_pin','endpoint','model','max_cost_microunits','spend_enforcement_admission'},
         'independently selected investigator and spend enforcement')
    check_pin(selected['spend_enforcement_admission']);integer(selected['max_cost_microunits'],1)
    need(request['policy_pin']==policy['policy_pin'] and request['endpoint']==policy['endpoint'],'same immutable provider request policy')
    need(selected['policy_pin']==policy['policy_pin'] and selected['endpoint']==policy['endpoint'] and
         selected['model']==policy['model'],'deployment binds exact investigator policy endpoint and model')
    endpoint=urlsplit(policy['endpoint'])
    need(endpoint.scheme=='https' and endpoint.hostname and endpoint.port in (None,443) and
         not endpoint.username and not endpoint.password and not endpoint.fragment,'fixed TLS endpoint')
    need(type(authorization_header) is str and authorization_header and '\n' not in authorization_header and '\r' not in authorization_header,
         'opaque externally supplied credential; never logged or read from disk here')
    limits=request['limits'];need({'provider_calls','provider_input_tokens','provider_output_tokens','provider_cost_microunits'}<=set(ledger.limits),'whole ledger call/token/spend dimensions')
    need(ledger.used['provider_calls']<limits['max_calls'],'fixed investigator call ceiling')
    ledger.reserve({'requests':1,'provider_calls':1,'write_bytes':len(request['body']),
                    'read_bytes':limits['max_response_bytes']+1,'retained_bytes':limits['max_response_bytes']+1,
                    'provider_input_tokens':limits['max_input_tokens'],
                    'provider_output_tokens':limits['max_output_tokens'],
                    'provider_cost_microunits':selected['max_cost_microunits']},'attempted provider call and token/spend reservation')
    raw=None;parts=[];status=None;cleanup_record={}
    try:
        with Cleanup(ledger,cleanup_record) as cleanup:
            ledger.tick()
            connection=http.client.HTTPSConnection(endpoint.hostname,443,timeout=(ledger.scientific-ledger.clock())/1e9,
                                                   context=ssl.create_default_context())
            cleanup.defer('close provider connection',connection.close)
            with ledger.live(2*(limits['max_response_bytes']+1),'bounded provider response'):
                ledger.tick();connection.request('POST',endpoint.path+('?' +endpoint.query if endpoint.query else ''),
                    body=request['body'],headers={'Authorization':authorization_header,'Content-Type':'application/json'})
                response=connection.getresponse();cleanup.defer('close provider response',response.close)
                status=response.status;need(response.status==200,'provider HTTP failure; no retry')
                length=response.getheader('Content-Length')
                if length is not None:need(length.isdecimal() and int(length)<=limits['max_response_bytes'],'response declared extent')
                total=0
                while True:
                    ledger.tick();block=response.read(min(65536,limits['max_response_bytes']+1-total))
                    if not block:break
                    total+=len(block);parts.append(block)
                    need(total<=limits['max_response_bytes'],'provider response cap')
                raw=b''.join(parts);ledger.tick();result=parse_response(raw,request)
                result['reserved_input_tokens']=limits['max_input_tokens'];result['reserved_output_tokens']=limits['max_output_tokens']
                result['raw_response']=raw
                return result
    except BaseException as error:
        ledger.fail('provider request',error)
        if raw is None:ledger.note_unknown('provider outcome/usage after failed or interrupted request')
        receipt={'request_pin':request['request_pin'],'response_prefix':b''.join(parts),'http_status':status,
                 'actual_usage_or_spend_qualified':False,'resources':ledger.report(),'retry_authorized':False,
                 'cleanup_failures':list(cleanup_record.get('cleanup_failures',[]))}
        failure=ProviderFailure(type(error).__name__+': '+str(error)[:1024],receipt)
        if hasattr(error,'ach_cleanup_errors'):failure.ach_cleanup_errors=list(error.ach_cleanup_errors)
        raise failure from error
