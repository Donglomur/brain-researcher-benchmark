"""Closed text input and conservative byte-BPE upper bound before dispatch.

The selected local model/encoding/framing equivalence is external qualification,
not issued by this parser. Actual rank/implementation bodies are authenticated;
no Boolean 'qualified' flag or remote file/image/reference input is accepted.
"""
import base64,re
from pathlib import Path
from .common import *

def text_input(value,contract,budget,reservation,model):
    fields(contract,('path','bytes','sha256'))
    root=Path(contract['path']).parent;profile=parse(capture(contract['path'],budget,contract['bytes'],{'bytes':contract['bytes'],'sha256':contract['sha256']}))
    fields(profile,('schema','model','encoding','ranks','implementation','request_framing_tokens','message_framing_tokens','equivalence_evidence'))
    need(profile['schema']=='n090-selected-byte-bpe-framing-v1'and profile['model']==model,'selected exact model/tokenizer contract')
    need(type(profile['encoding'])is str and 0<len(profile['encoding'])<=128,'explicit encoding identity')
    for name in('request_framing_tokens','message_framing_tokens'):integer(profile[name],1)
    bodies={}
    for name in('ranks','implementation','equivalence_evidence'):
        row=fields(profile[name],('path','bytes','sha256'));p=Path(row['path']);need(not p.is_absolute()and '..'not in p.parts,'local explicit tokenizer evidence member')
        bodies[name]=capture(root/p,budget,row['bytes'],{'bytes':row['bytes'],'sha256':row['sha256']})
    alphabet=set();ranks=set();tokens=set()
    for line in bodies['ranks'].splitlines():
        fields_=line.split();need(len(fields_)==2 and fields_[1].isdigit(),'actual complete BPE rank row')
        token=base64.b64decode(fields_[0],validate=True);rank=int(fields_[1]);need(token and token not in tokens and rank not in ranks,'unique nonempty byte tokens/ranks');tokens.add(token);ranks.add(rank)
        if len(token)==1:alphabet.add(token[0])
    need(alphabet==set(range(256)),'complete256-byte base alphabet in actual selected ranks')
    need(type(value)is list and 1<=len(value)<=128,'finite full text message sequence')
    upper=profile['request_framing_tokens']
    for message in value:
        fields(message,('role','content'));need(message['role']in('system','developer','user','assistant')and type(message['content'])is str,'text-only messages; no file/image/item/tool references')
        need(not any(0xD800<=ord(ch)<=0xDFFF for ch in message['content']),'valid Unicode text')
        # A merge-only byte BPE cannot emit more ordinary text tokens than bytes.
        # Framing is separately selected for the exact model/protocol; no hidden
        # provider overhead is assumed to be zero or deducted after dispatch.
        upper+=len(message['role'].encode())+len(message['content'].encode('utf-8'))+profile['message_framing_tokens']
    need(upper<=reservation,'pre-dispatch conservative input token ceiling')
    return {'contract':contract,'model':model,'encoding':profile['encoding'],'input_token_upper_bound':upper,'selected_input_reservation':reservation,'framing_is_external_qualification':True,'text_only':True}
