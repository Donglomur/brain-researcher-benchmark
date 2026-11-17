"""Portable full-field little-endian output encoding and complete admission."""
from __future__ import annotations
from array import array
import hashlib,json,math,os,stat,sys
from pathlib import Path
from .contract import *
from . import reduction

def specs(meta):return field_specs(meta,lambda axis,bounds:reduction.nearest_window(axis,*bounds))

def encode(values,kind,budget):
    size={'f8':8,'u2':2,'u1':1}[kind]
    budget.charge(read=len(values)*size,write=len(values)*size)
    a=array({'f8':'d','u2':'H','u1':'B'}[kind],values)
    require(a.itemsize==size,'native scalar size')
    if sys.byteorder!='little':a.byteswap()
    return a.tobytes()

def decode(body,kind,budget):
    budget.charge(read=len(body),write=len(body))
    a=array({'f8':'d','u2':'H','u1':'B'}[kind]);a.frombytes(body)
    if sys.byteorder!='little':a.byteswap()
    return a

def publish_fields(root,meta,fields,budget,*,producer):
    """Trusted reference or isolated candidate writer; refuses existing directory."""
    root=Path(root);root.mkdir(mode=0o700)
    layout=specs(meta);require(set(fields)==set(layout),'complete field set')
    rows={}
    for name,spec in layout.items():
        require(len(fields[name])==math.prod(spec['shape']),'field extent')
        body=encode(fields[name],spec['dtype'],budget)
        budget.charge(write=len(body))
        with (root/(name+'.bin')).open('xb') as f:f.write(body)
        rows[name]={**spec,'sha256':hashlib.sha256(body).hexdigest()}
    manifest={'schema':OUTPUT_SCHEMA,'identity':meta,'producer':producer,'fields':rows}
    body=json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    require(len(body)<=1048576,'manifest bound');budget.charge(write=len(body))
    with (root/'OUTPUT.json').open('xb') as f:f.write(body)
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def admit(root,manifest_pin,meta,budget):
    """Captures every field before any reference computation; no partial submission."""
    root=Path(root);require(not root.is_symlink() and root.is_dir(),'ordinary output directory')
    require(manifest_pin['bytes']<=1048576,'manifest cap')
    manifest=json_body(read_pinned(root/'OUTPUT.json',manifest_pin,budget))
    keys(manifest,['schema','identity','producer','fields'])
    submitted_identity=metadata(manifest['identity'])
    require(manifest['schema']==OUTPUT_SCHEMA and submitted_identity==metadata(meta),'output identity')
    require(type(manifest['producer']) is str and manifest['producer'],'producer descriptor')
    layout=specs(meta);require(type(manifest['fields']) is dict and set(manifest['fields'])==set(layout),'complete output fields')
    require(set(x.name for x in root.iterdir())=={'OUTPUT.json'}|{k+'.bin' for k in layout},'exact output directory')
    captured={}
    for name,spec in layout.items():
        row=manifest['fields'][name];keys(row,['shape','dtype','bytes','sha256'])
        require(type(row['shape']) is list and all(type(x) is int for x in row['shape']) and type(row['dtype']) is str and strict_int(row['bytes'],1),'strict field descriptor types')
        pin({'bytes':row['bytes'],'sha256':row['sha256']})
        require(all(row[k]==v for k,v in spec.items()),'field shape/dtype/extent')
        body=read_pinned(root/(name+'.bin'),{'bytes':row['bytes'],'sha256':row['sha256']},budget)
        captured[name]=decode(body,spec['dtype'],budget)
    validate_fields(captured,layout)
    return captured

def validate_fields(fields,layout):
    """Meaningful local consistency independent of private reference values."""
    require(set(fields)==set(layout),'complete captured field set')
    for name,spec in layout.items():
        a=fields[name];require(len(a)==math.prod(spec['shape']),'captured extent')
        if name.endswith('.undefined'):
            values=fields[name[:-len('undefined')]+'value']
            require(all(type(x) is int and x in (0,1) and bool(x)==math.isnan(v) for x,v in zip(a,values)),'undefined mask')
        if name.endswith('.positions'):
            counts=fields[name[:-len('positions')]+'contributors']
            require(all(type(x) is int and 0<=x<32768 and x.bit_count()==n for x,n in zip(a,counts)),'stored-position support and counts')
        if name.endswith('.time_contributors'):require(all(0<=x<=200 for x in a),'time support range')
        if name.endswith('.frequency_contributors'):require(all(0<=x<=53 for x in a),'frequency support range')
