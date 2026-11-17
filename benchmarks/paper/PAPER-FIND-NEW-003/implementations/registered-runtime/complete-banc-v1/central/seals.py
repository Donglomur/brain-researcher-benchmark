"""Exact retained JSON bodies; complete admission precedes all target access."""
from banc_runtime.codec import need,encode,parse
from banc_runtime.collect import Seal,admit_retained,seal_identity
from .io import exact_fields

def serialize(seal):
    need(type(seal) is Seal,'actual immutable collector seal')
    return {'schema':'banc_retained_seal_v1','program_identity':seal.program_identity,
      'manifest_utf8':seal.manifest_bytes.decode('utf-8'),
      'payloads':[[k,None if b is None else b.decode('utf-8')] for k,b in seal.payloads],
      'products':[[k,b.decode('utf-8')] for k,b in seal.products],'identity':seal.identity}

def restore(doc,contracts,program_identity,cap=1048576):
    exact_fields(doc,('schema','program_identity','manifest_utf8','payloads','products','identity'),'retained seal')
    need(doc['schema']=='banc_retained_seal_v1' and doc['program_identity']==program_identity,'retained programme binding')
    raw=doc['manifest_utf8'].encode('utf-8')
    payloads=tuple((k,None if b is None else b.encode('utf-8')) for k,b in doc['payloads'])
    products=tuple((k,b.encode('utf-8')) for k,b in doc['products'])
    admit_retained(raw,payloads,products,contracts,program_identity=program_identity,cap=cap)
    need(doc['identity']==seal_identity(raw,payloads,products),'complete retained seal identity')
    return Seal(program_identity,raw,payloads,doc['identity'],products)
