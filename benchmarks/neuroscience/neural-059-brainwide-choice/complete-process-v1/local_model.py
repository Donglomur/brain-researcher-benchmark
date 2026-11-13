"""Concrete fresh CPU/greedy local-transformers model leaf; no hosted API."""
import time
from .core import need, keys


class ResidentModel:
    """One arm's fixed weights; every generation has entirely local request state."""
    def __init__(self, config):
        self.config=config; self.calls=0
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        torch.set_num_threads(1); torch.set_num_interop_threads(1)
        torch.manual_seed(config['seed'])
        self.torch=torch
        self.tokenizer=AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=False)
        self.model=AutoModelForCausalLM.from_pretrained('/model',local_files_only=True,
            trust_remote_code=False,torch_dtype=torch.float32)
        self.model.eval(); self.model.requires_grad_(False)
        self.identity=self.parameters()

    def parameters(self):
        return [(kind,name,list(value.shape),str(value.dtype),value.data_ptr(),value._version)
                for kind,items in (('parameter',self.model.named_parameters()),('buffer',self.model.named_buffers()))
                for name,value in items]

    def generate(self, request, deadline):
        need(self.parameters()==self.identity,'unchanged resident parameter/buffer identity before request')
        result=generate(request,self.config,deadline,self)
        need(self.parameters()==self.identity,'generation did not mutate retained model tensors')
        self.calls+=1
        # No request, conversation, token tensor or returned cache is stored.
        return result


def generate(request, config, deadline, resident):
    keys(request, ('messages','max_new_tokens'))
    need(config['kind']=='local_transformers_text_v1','exact selected model backend')
    messages=request['messages']
    need(type(messages) is list and 0<len(messages)<=128 and all(type(m) is dict and
         set(m)=={'role','content'} and m['role'] in ('user','assistant') and type(m['content']) is str
         for m in messages), 'bounded user/assistant conversation; fixed system prefix')
    need(sum(len(m['content'].encode()) for m in messages)<=config['request_bytes'],'whole message extent')
    maximum=request['max_new_tokens']
    need(type(maximum) is int and 0<maximum<=config['maximum_output_tokens'],'selected output token ceiling')
    # Only this separate, arm-owned model container sees /model. The
    # candidate never receives checkpoint, cache, provider image or daemon access.
    torch=resident.torch; tokenizer=resident.tokenizer; model=resident.model
    from transformers import StoppingCriteria, StoppingCriteriaList
    torch.manual_seed(config['seed'])
    prompt=[{'role':'system','content':config['system_prompt']},*messages]
    text=tokenizer.apply_chat_template(prompt,tokenize=False,add_generation_prompt=True)
    inputs=tokenizer(text,return_tensors='pt',add_special_tokens=False)
    n=int(inputs['input_ids'].shape[1])
    need(0<n<=config['maximum_input_tokens'],'observed actual model input token cap')
    need(time.monotonic()<deadline,'model load/tokenization shares original whole-call clock')
    class Deadline(StoppingCriteria):
        def __call__(self,input_ids,scores,**kwargs):
            return time.monotonic()>=deadline
    with torch.inference_mode():
        output=model.generate(**inputs,max_new_tokens=maximum,do_sample=False,
            use_cache=False,past_key_values=None,return_dict_in_generate=False,
            stopping_criteria=StoppingCriteriaList([Deadline()]),
            pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    need(time.monotonic()<deadline,'late model output is unavailable')
    generated=output[0,n:]; count=int(generated.numel())
    need(0<=count<=maximum,'actual generated token count')
    return {'text':tokenizer.decode(generated,skip_special_tokens=True),
            'usage':{'input_tokens':n,'output_tokens':count},'qualification':False}
