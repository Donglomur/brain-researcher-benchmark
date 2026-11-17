"""Prospective native-time waveform and fixed causal GPT2 primitive producers."""
import csv
import io
import math
import re
import hashlib
from .errors import need
LAGS=(1.5,3.,4.5,6.)

def token(word):
    return re.sub("[^a-z']", "", word.lower())

def aligned_words(body):
    result=[];missing=0
    for row in csv.reader(io.StringIO(body.decode("utf-8"))):
        need(len(row)==4,"gentle-four-columns")
        word,_,start,end=row
        if not start or not end:
            missing+=1
            continue
        a,b=float(start),float(end)
        need(math.isfinite(a) and math.isfinite(b) and 0<=a<=b<=20000,"word-clock")
        result.append({"word":token(word),"start":a,"end":b,"order":len(result)})
    need(result and all(a["start"]<=b["start"] for a,b in zip(result,result[1:])), "word-order")
    return result,missing

def guarded_indices(n,tr,origin,start,stop):
    need(type(n)is int and 1<=n<=10000 and tr in (1.5,1.52) and
         all(math.isfinite(x) for x in (origin,start,stop)) and stop>start,"native-timeline")
    out=[i for i in range(n) if origin+i*tr-6-tr-16>=start and origin+i*tr+12<stop]
    need(len(out)>=20,"guarded-segment-too-short")
    return out

def hashed(word):
    b=hashlib.sha256(word.encode()).digest()
    return int.from_bytes(b[:4],"little")%64,1. if b[4]&1 else -1.

def waveform(audio,sr,start,end,np):
    lo=math.ceil(start*sr);hi=math.ceil(end*sr)
    need(0<=lo<hi<=len(audio) and hi-lo>=2,"waveform-support")
    a=audio[lo:hi];energy=np.abs(np.fft.rfft(a*np.hanning(len(a))))**2
    freq=np.fft.rfftfreq(len(a),1/sr)
    out=[float(np.log1p(np.mean(a*a))),float(np.log1p(np.mean(np.abs(a)))),
         float(np.std(a)),float(np.mean(a[:-1]*a[1:]<0))]
    out += [float(np.log1p(energy[(freq>=l)&(freq<h)].sum()/len(a)**2))
            for l,h in ((0,300),(300,1000),(1000,3000),(3000,8000))]
    return out

def logmel(audio,sr,start,end,np):
    n=math.floor(.020*sr);fft=1 << (n-1).bit_length()
    need(n>=2 and sr>=16000,"mel-sample-rate")
    # Starts remain on the audio-global grid, including fractional-rate hops.
    k0=max(0,math.floor(start/.010)-2);k1=math.ceil(end/.010)+2
    starts=[math.floor(k*.010*sr) for k in range(k0,k1)
            if math.floor(k*.010*sr)/sr>=start and
               (math.floor(k*.010*sr)+n)/sr<=end]
    need(starts and all(0<=a and a+n<=len(audio) for a in starts),"complete-mel-frames")
    h=np.hanning(n);norm=(h*h).sum();freq=np.fft.rfftfreq(fft,1/sr)
    mel=lambda f:2595*np.log10(1+f/700)
    edges=700*(10**(np.linspace(mel(50),mel(min(8000,sr/2)),66)/2595)-1)
    filters=[]
    for j in range(64):
        f=np.maximum(0,np.minimum((freq-edges[j])/(edges[j+1]-edges[j]),
                                 (edges[j+2]-freq)/(edges[j+2]-edges[j+1])))
        need(f.sum()>0,"zero-mel-filter")
        filters.append(f/f.sum())
    powers=[]
    for a in starts:
        power=np.abs(np.fft.rfft(audio[a:a+n]*h,n=fft))**2/norm
        if fft%2==0:power[1:-1]*=2
        else:power[1:]*=2
        powers.append(power)
    return np.log1p(np.asarray(filters)@np.mean(powers,axis=0))

class GPT2Extractor:
    def __init__(self, local_model, local_tokenizer):
        import torch
        from transformers import GPT2Model,GPT2Tokenizer
        self.torch=torch
        self.tokenizer=GPT2Tokenizer.from_pretrained(local_tokenizer,local_files_only=True,
                                                    add_prefix_space=False)
        self.model=GPT2Model.from_pretrained(local_model,local_files_only=True,
                                            torch_dtype=torch.float32,attn_implementation="eager")
        self.model.eval()
        need(self.model.config.n_embd==768 and self.model.config.n_positions==1024,"gpt2-shape")

    def tokens(self, text):
        ids=self.tokenizer.encode(text,add_special_tokens=False)
        need(1<=len(ids)<=1024,"gpt2-context-overflow")
        return self.torch.tensor([ids],dtype=self.torch.long)

    def lexical(self,word):
        ids=self.tokens(" "+word)
        with self.torch.no_grad():
            return self.model.wte(ids)[0].mean(dim=0).cpu().numpy()

    def contextual(self,word,words,segment_audio_start):
        history=[w for w in words if w["word"] and w["order"]<word["order"] and
                 max(segment_audio_start,word["end"]-16)<=w["end"]<=word["end"]]
        history.append(word)
        ids=self.tokens("".join(" "+w["word"] for w in history))
        with self.torch.no_grad():
            result=self.model(input_ids=ids,position_ids=self.torch.arange(ids.shape[1])[None,:],
                              use_cache=False,output_hidden_states=True,return_dict=True)
            return result.hidden_states[8][0,-1].cpu().numpy()

def primitives(audio,sr,words,clock,indices,tr,extractor):
    import numpy as np
    audio=np.asarray(audio,dtype=np.float64)
    need(audio.ndim==1 and np.isfinite(audio).all() and sr>=16000,"mono-finite-audio")
    origin=clock["first_sample_scanner_seconds"];story=clock["story_start"]
    stop=clock["story_stop"];shift=clock["audio_at_scanner_zero"]
    result=[]
    for i in indices:
        t=origin+i*tr;legacy=[];timing=[];acoustic=[];lexical=[];context=[];terms=[]
        for lag in LAGS:
            end=t-lag+shift;start=end-tr
            selected=[w for w in words if w["word"] and start<=w["end"]<end]
            current=[w["word"] for w in selected]
            history=[w["word"] for w in words if w["word"] and start-16<=w["end"]<start]
            a=waveform(audio,sr,start,end,np);lex=np.zeros(64);ctx=np.zeros(64)
            for w in current:
                j,s=hashed(w);lex[j]+=s/tr
            for j,w in enumerate(history):
                k,s=hashed("unigram:"+w);ctx[k]+=s/max(1,len(history))
                if j:
                    k,s=hashed("bigram:"+history[j-1]+" "+w);ctx[k]+=s/max(1,len(history)-1)
            rate=len(current)/tr;length=sum(map(len,current))/max(1,len(current))
            elapsed=(t-story)/3600
            legacy.append(a+[rate,length,elapsed]+list(lex)+list(ctx))
            timing.append([rate,length,0.,elapsed,(t-story)/(stop-story)] +
                          [min(max((t-story)/tau,0.),1.) for tau in (3,6,12,24,48,96)])
            acoustic.append(a+list(logmel(audio,sr,start,end,np)))
            lexical.append(np.mean([extractor.lexical(w) for w in current],axis=0)
                           if current else np.zeros(768))
            context.append(np.mean([extractor.contextual(w,words,story+shift) for w in selected],axis=0)
                           if current else np.zeros(768))
            terms.append(current)
        result.append({"legacy":np.asarray(legacy,dtype="<f4").tolist(),
                       "T":np.asarray(timing,dtype="<f4").tolist(),
                       "A":np.asarray(acoustic,dtype="<f4").tolist(),
                       "L":np.asarray(lexical,dtype="<f4").tolist(),
                       "C":np.asarray(context,dtype="<f4").tolist(),"terms":terms})
    return result
