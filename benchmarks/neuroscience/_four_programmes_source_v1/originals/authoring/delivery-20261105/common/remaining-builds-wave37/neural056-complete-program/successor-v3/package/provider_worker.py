"""Unrun local causal-LM adapter. Exact versions/model/ABI require qualification.

API source: https://huggingface.co/docs/transformers/v4.46.3/en/main_classes/model
Local-only loading; remote custom Python and automatic checkpoint fetch forbidden.
"""
import os,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from n056.core import need,read_json,save,canonical
def main():
    import torch,transformers
    need(torch.__version__.split('+')[0]=='2.5.1' and transformers.__version__=='4.46.3','selected local provider versions')
    request=read_json('/input/0/request.json',4*1024**2);limits=request['limits']
    need(all(type(limits[k])is int and limits[k]>0 for k in ('input','output')),'finite token caps')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    tokenizer=transformers.AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=False)
    need(tokenizer.chat_template is not None,'qualified model chat template')
    messages=[{'role':'system','content':'Return exactly one JSON object matching the requested answer schema. No markdown or commentary.'},
              {'role':'user','content':canonical(request['request']).decode()}]
    ids=tokenizer.apply_chat_template(messages,add_generation_prompt=True,return_tensors='pt')
    need(ids.ndim==2 and ids.shape[0]==1 and ids.shape[1]<=limits['input'],'input token bound before model load/generation')
    model=transformers.AutoModelForCausalLM.from_pretrained('/model',local_files_only=True,
          trust_remote_code=False,use_safetensors=True,torch_dtype=torch.float32).eval()
    with torch.inference_mode():
        seq=model.generate(ids,attention_mask=torch.ones_like(ids),do_sample=False,
             max_new_tokens=limits['output'],use_cache=True)
    generated=seq[0,ids.shape[1]:];need(len(generated)<=limits['output'],'output token bound')
    text=tokenizer.decode(generated,skip_special_tokens=True);need(len(text.encode())<=2*1024**2,'bounded response')
    from n056.core import json_bytes
    answer=json_bytes(text.encode())
    save('/output/response.json',{'schema':'neural056_provider_response_v1','answer':answer,
       'usage':{'input_tokens':int(ids.shape[1]),'output_tokens':len(generated)}})
if __name__=='__main__':main()

