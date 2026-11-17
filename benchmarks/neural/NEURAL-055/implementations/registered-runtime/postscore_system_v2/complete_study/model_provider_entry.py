"""Actual local provider entry for the qualified v3 broker.

Nothing in this file is imported/executed by BUILD ONLY model controls.
"""
import time
ORIGIN=time.monotonic()
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

def require(ok,reason):
    if not ok:raise ValueError(reason)

def load_json(path,cap):
    p=Path(path);require(p.is_file() and not p.is_symlink() and p.stat().st_size<=cap,'bounded provider input')
    return json.loads(p.read_bytes())

def emit(value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    require(len(raw)<=8388608,'bounded complete provider result')
    offset=0
    while offset<len(raw):
        n=os.write(1,raw[offset:]);require(n>0,'actual provider output progress');offset+=n

def main():
    p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--config',required=True)
    a=p.parse_args();request=load_json(a.request,1048576);config=load_json(a.config,1048576)
    require(config['kind']=='local_transformers_text_v1','exact qualified local model adapter')
    require(request['operation']=='generate' and request['role']=='investigator_decision','actual provider role')
    deadline=request['deadline'];require(ORIGIN<deadline,'original inherited provider deadline')
    payload=request['payload'];messages=payload['messages']
    require(type(messages)is list and 0<len(messages)<=128,'bounded actual conversation')
    require(all(type(m)is dict and set(m)=={'role','content'} and m['role'] in ('user','assistant') and type(m['content'])is str for m in messages),'no caller system-policy override')
    require(sum(len(m['content'].encode()) for m in messages)<=config['request_bytes'],'actual message extent')
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM,StoppingCriteria,StoppingCriteriaList
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    torch.manual_seed(config['seed'])
    tokenizer=AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained('/model',local_files_only=True,trust_remote_code=False,torch_dtype=torch.float32)
    model.eval()
    prompt=[{'role':'system','content':config['system_prompt']},*messages]
    text=tokenizer.apply_chat_template(prompt,tokenize=False,add_generation_prompt=True)
    inputs=tokenizer(text,return_tensors='pt',add_special_tokens=False)
    n=int(inputs['input_ids'].shape[1]);require(0<n<=config['maximum_input_tokens'],'actual input token cap')
    maximum=payload['max_new_tokens'];require(type(maximum)is int and 0<maximum<=config['maximum_output_tokens'],'declared output token cap')
    require(time.monotonic()<deadline,'model preparation inside original action')
    class OriginalDeadline(StoppingCriteria):
        def __call__(self,input_ids,scores,**kwargs):return time.monotonic()>=deadline
    with torch.inference_mode():
        output=model.generate(**inputs,max_new_tokens=maximum,do_sample=False,
                              stopping_criteria=StoppingCriteriaList([OriginalDeadline()]),
                              pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    require(time.monotonic()<deadline,'late model output unavailable')
    generated=output[0,n:];count=int(generated.numel())
    require(0<=count<=maximum,'actual output tokens bounded')
    result=tokenizer.decode(generated,skip_special_tokens=True)
    emit({'schema':'neural055-provider-result-v3','role':'investigator_decision','result':{'text':result},
          'usage':{'input_tokens':n,'output_tokens':count,'maximum_input_tokens':config['maximum_input_tokens'],
                   'maximum_output_tokens':maximum,'cpu_placement':'same_original_native_cgroup'},
          'request_sha256':request['request_sha256'],'source_identity':config['source_identity']})
    return 0

if __name__=='__main__':raise SystemExit(main())

