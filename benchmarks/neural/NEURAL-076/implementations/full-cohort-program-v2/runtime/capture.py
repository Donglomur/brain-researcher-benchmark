"""Opaque stopped output capture; no prediction decoding or private targets."""
import base64
from common import need,short,PRED,MIB

def capture_output(e,d,keeper,end,destination,writer):
    base=['exec',keeper['id'],'python','-I','-B','/trusted/holder.py']
    idx=e.r.parse(e.r.call(d,base+['index','--name','predictions.npz'],end,'output_index',4096))
    need(set(idx)=={'schema','bytes','sha256'}and idx['schema']=='neural076_output_index_v1'and type(idx['bytes'])is int and 0<idx['bytes']<=PRED,'one bounded archive')
    chunks=[]
    for offset in range(0,idx['bytes'],4*MIB):
        v=e.r.parse(e.r.call(d,base+['chunk','--name','predictions.npz','--offset',str(offset)],end,'output_chunk',6*MIB,15))
        need(set(v)=={'schema','offset','total_bytes','bytes','sha256','base64'}and v['schema']=='neural076_output_chunk_v1'and v['offset']==offset and v['total_bytes']==idx['bytes'],'exact chunk')
        b=base64.b64decode(v['base64'],validate=True);need(len(b)==min(4*MIB,idx['bytes']-offset)and short(b)=={k:v[k]for k in('bytes','sha256')},'chunk integrity');chunks.append(b)
    raw=b''.join(chunks);need(short(raw)=={k:idx[k]for k in('bytes','sha256')},'full archive integrity')
    # Native lifecycle removes holder and volume before the caller publishes.
    writer.pending=raw
    return {'predictions.npz':short(raw)}
