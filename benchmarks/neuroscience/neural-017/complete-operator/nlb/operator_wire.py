"""Canonical NEURAL-017 plan bytes, including the one fixed factored table type.

This is ordinary bounded metadata publication. It supplies no scheduler, source
resolver, network transport, authority or scientific operation.
"""
import hashlib
import json
import os
from .contracts import Store, Handles, need, integer


def chunks(value, *, final_lf=True):
    """Same finite compact sorted-key UTF-8 JSON as contracts.canonical."""
    def encode(item):
        if type(item)is dict:
            need(all(type(k)is str for k in item),'closed JSON object uses text keys')
            yield b'{'
            for n,key in enumerate(sorted(item)):
                if n:yield b','
                yield json.dumps(key,ensure_ascii=False).encode('utf-8');yield b':'
                yield from encode(item[key])
            yield b'}'
        elif type(item)in(list,tuple):
            yield b'['
            for n,entry in enumerate(item):
                if n:yield b','
                yield from encode(entry)
            yield b']'
        elif type(item)in(str,int,float,bool)or item is None:
            yield json.dumps(item,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
        else:
            # Exact source-owned class only: no custom serialization callback.
            from .factored_runtime import FactoredRuntime
            need(type(item)is FactoredRuntime,'unsupported plan object')
            yield from item.canonical_chunks(final_lf=False)
    yield from encode(value)
    if final_lf:yield b'\n'


def identity(value):
    h=hashlib.sha256()
    for raw in chunks(value):h.update(raw)
    return h.hexdigest()


def extent(value,cap):
    integer(cap,1);count=0
    for raw in chunks(value):
        count+=len(raw);need(count<=cap,'complete selected metadata exceeds actual consumer cap')
    return count


def write_canonical(store,name,value,cap):
    """Create-only streamed publication, with original partial-write custody."""
    need(type(store)is Store,'actual bounded artifact Store');integer(cap,1)
    count=0;expected=hashlib.sha256()
    for raw in chunks(value):
        store.budget.admit();count+=len(raw);need(count<=cap,'complete ordinary metadata cap');expected.update(raw)
    expected_sha=expected.hexdigest()
    owner=Handles(store.custody);event={'path':name,'accepted_bytes':0,'created':False,
        'durable':False,'streamed_canonical':True,'expected_bytes':count,'expected_sha256':expected_sha}
    store.custody.events.append(event)
    actual=hashlib.sha256()
    try:
        store.budget.reserve('write_bytes',count);store.budget.reserve('created_files',1)
        parent,leaf=store.parent(name,owner)
        fd=owner.own(os.open(leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent),'file',name)
        event['created']=True;store.budget.charge('created_files',1)
        for raw in chunks(value):
            need(event['accepted_bytes']+len(raw)<=count,'metadata changed after its original extent admission')
            start=0
            while start<len(raw):
                store.budget.guard();written=os.write(fd,raw[start:]);need(written>0,'short metadata write')
                actual.update(raw[start:start+written]);start+=written;event['accepted_bytes']+=written
                store.budget.charge('write_bytes',written)
        need(event['accepted_bytes']==count and actual.hexdigest()==expected_sha,'exact immutable original metadata bytes')
        os.fsync(fd);os.fsync(parent);event['durable']=True
    except BaseException as error:
        store.custody.fail(error,'streamed_metadata_publication');store.budget.stop('original metadata publication incomplete')
    finally:owner.finish()
    store.custody.raise_if_failed();store.budget.guard()
    return {'path':name,'bytes':count,'sha256':expected_sha}
