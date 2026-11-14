"""Evaluator-private original readers; importing this module does no native work.

Exact recording/audio/annotation/equivalence operands must be supplied by the
external data/clock owner. No filename, public descriptor or hash creates that
authority. Header/layout qualification is absent until real admitted execution.
"""
import csv,hashlib,os
from programme.contracts import Asset,Pin,need,fields,rational
from programme.n090_adapter import inspect
from .custody import open_pinned,stable
from .protocol import PHONEMES
from .catalogue import exact_json,complete_catalogue,source_events,whole_event_support,KEYS

class SourceStore:
    def __init__(self,root,index,supplements,channels,accounting,ledger):
        self.root,self.index,self.supplements=root,index,supplements
        self.channels,self.accounting,self.ledger=channels,accounting,ledger
        self.handles={};self.owned=[];self.closed=False
    def bytes(self,asset):
        self.ledger.raise_first();f=None;body=None
        try:
            f,before=open_pinned(self.root,asset,self.accounting,self.ledger)
            self.accounting.charge('read',asset.pin.bytes+1);body=f.read(asset.pin.bytes+1)
            need(len(body)==asset.pin.bytes and stable(before,os.fstat(f.fileno())),'stable exact source decoder read')
        except BaseException as e:self.ledger.propagated('source-read',e)
        finally:
            if f is not None:self.ledger.attempt('source-read-close',f.close)
        self.ledger.raise_first();return body
    def json(self,asset):return exact_json(self.bytes(asset))
    def _native(self,key,kind):
        need(not self.closed,'live original source owner');self.ledger.raise_first()
        identity=(key,kind)
        if identity in self.handles:return self.handles[identity]
        run=self.index[key];s=self.supplements[key]
        asset=run.recording if kind=='meg' else Asset.parse(s['audio']['asset'])
        f,before=open_pinned(self.root,asset,self.accounting,self.ledger)
        self.owned.append(('raw',f,before))
        if kind=='meg':
            import numpy as np
            import h5py
            h=h5py.File(f,'r');self.owned.append(('native',h,None))
            self.accounting.charge('read',run.clock.sample_count*8)
            data=inspect(h,run,self.channels,np);result=data
        else:
            import soundfile as sf
            h=sf.SoundFile(f,mode='r');self.owned.append(('native',h,None))
            need(h.channels==1 and h.samplerate==s['audio']['sample_rate'] and len(h)==s['audio']['sample_count'],
                 'full authenticated mono audio layout and declared rate/count')
            result=h
        self.handles[identity]=result;return result
    def meg(self,key,first,stop):
        need(type(first) is int and type(stop) is int and 0<=first<stop<=self.index[key].clock.sample_count,'exact admitted MEG interval')
        data=self._native(key,'meg');self.accounting.charge('read',306*(stop-first)*data.dtype.itemsize)
        result=data[:,first:stop]
        need(result.shape==(306,stop-first),'complete original MEG read')
        return result
    def audio(self,key,first,stop):
        s=self.supplements[key]['audio'];need(type(first) is int and type(stop) is int and 0<=first<stop<=s['sample_count'],'admitted segment-first audio interval')
        h=self._native(key,'audio');self.accounting.charge('read',(stop-first)*8)
        h.seek(first);result=h.read(stop-first,dtype='float64',always_2d=False)
        need(result.shape==(stop-first,),'complete source mono audio segment');return result
    def close(self):
        if self.closed:return
        self.closed=True
        for kind,handle,before in reversed(self.owned):
            if kind=='raw':self.ledger.attempt('source-final-stat',lambda h=handle,b=before:need(stable(b,os.fstat(h.fileno())),'source stable through decoder'))
            self.ledger.attempt('source-'+kind+'-close',handle.close)
        self.owned=[];self.handles={}
    def words(self,key):
        run=self.index[key];s=self.supplements[key]
        body=self.bytes(run.annotations);alignment=self.json(Asset.parse(s['word_alignment']))
        fields(alignment,('schema','run_key','annotations','evidence','words'))
        need(alignment['schema']=='original-word-intervals-v1' and tuple(alignment['run_key'])==key and Pin.parse(alignment['annotations'])==run.annotations.pin,'actual word-alignment source join')
        Pin.parse(alignment['evidence'])
        reader=csv.DictReader(body.decode('utf8').splitlines(),delimiter='\t')
        need(reader.fieldnames and len(set(reader.fieldnames))==len(reader.fieldnames) and {'kind','segment','idx','timemeg'}<=set(reader.fieldnames),'original complete word TSV')
        original={};seen=set()
        for ordinal,row in enumerate(reader):
            need(None not in row and None not in row.values() and row['idx'] not in seen,'exact unique original row')
            seen.add(row['idx'])
            if row['kind']=='word':original[row['idx']]=(ordinal,row)
        supplied={}
        for item in alignment['words']:
            fields(item,('source_idx','source_row0','canonical_word','onset_seconds','end_seconds'))
            need(item['source_idx'] not in supplied,'unique word support');supplied[item['source_idx']]=item
        need(set(supplied)==set(original),'every original word has measured interval; no inferred next-onset endpoint')
        result=[]
        for idx,(ordinal,row) in original.items():
            item=supplied[idx];need(item['source_row0']==ordinal and rational(item['onset_seconds'])==rational(row['timemeg']),'word identity/onset equals literal producer')
            need(rational(item['end_seconds'])>rational(item['onset_seconds']),'measured nonempty completed-word interval')
            result.append({**item,'text':row['segment'].strip(),'run_key':key})
        return tuple(result)

def load_originals(root,catalogue_asset,supplement_asset,classes_asset,channels_asset,accounting,ledger):
    """Read only evaluator-owned originals; never give this object to an actor."""
    store=SourceStore(root,{}, {},None,accounting,ledger)
    try:
        document=store.json(catalogue_asset);index=complete_catalogue(document)
        classes=store.json(classes_asset)
        fields(classes,('schema','classes','producer_evidence'))
        need(classes['schema']=='original-39-phonemes-v1' and tuple(classes['classes'])==PHONEMES,'fixed original phoneme order')
        Pin.parse(classes['producer_evidence'])
        channel_bytes=store.bytes(channels_asset);channels=exact_json(channel_bytes)
        need(all(r.channels==channels_asset.pin for r in index.values()),'channel identity for all64')
        need(len(channels['channel_names'])==len(channels['channel_types'])==306 and len(set(channels['channel_names']))==306,'exact channel schema')
        doc=store.json(supplement_asset);fields(doc,('schema','runs'))
        need(doc['schema']=='n090-original-supplements-v1','explicit original supplement protocol');supplements={}
        for item in doc['runs']:
            fields(item,('run_key','equivalence','word_alignment','audio'))
            key=tuple(item['run_key']);need(key in index and key not in supplements,'complete unique supplement run')
            Asset.parse(item['equivalence']);Asset.parse(item['word_alignment']);a=item['audio']
            fields(a,('asset','sample_rate','sample_count','sample_zero_seconds','annotation_to_audio_seconds','clock_rate','evidence','decode_evidence','amplitude_evidence'))
            Asset.parse(a['asset']);Pin.parse(a['evidence']);Pin.parse(a['decode_evidence']);Pin.parse(a['amplitude_evidence'])
            need(type(a['sample_rate']) is int and 1<=a['sample_rate']<=384000 and type(a['sample_count']) is int and a['sample_count']>0,'finite declared audio extent')
            need(rational(a['clock_rate'])==1,'unsupported drift has no fallback');rational(a['sample_zero_seconds']);rational(a['annotation_to_audio_seconds'])
            supplements[key]=item
        need(set(supplements)==set(KEYS),'complete64 source supplements')
        store.index,store.supplements,store.channels=index,supplements,channels
        events={};disposition={};words={}
        for key in KEYS:
            events[key],disposition[key]=source_events(index[key],root,classes['classes'],Asset.parse(supplements[key]['equivalence']),accounting.read_limit,store.bytes)
            words[key]=store.words(key)
            wordmap={w['canonical_word']:w for w in words[key]}
            need(len(wordmap)==len(words[key]),'unique canonical word occurrences per run')
            for e in events[key]:
                w=wordmap.get(e['canonical_word']);need(w is not None and rational(w['onset_seconds'])==rational(e['word_onset_seconds']) and rational(w['end_seconds'])==rational(e['word_end_seconds']),'phoneme equivalence and measured original word alignment agree')
        support=whole_event_support(events,index)
        return store,events,words,support,{'class_order':classes['classes'],'row_dispositions':{'/'.join(k):v for k,v in disposition.items()}}
    except BaseException as e:
        ledger.propagated('original-load',e);store.close();ledger.raise_first()
