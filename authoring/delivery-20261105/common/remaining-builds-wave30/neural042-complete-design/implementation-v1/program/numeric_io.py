"""Safe primitive prepared NPY admission before NumPy allocation; no pickle."""
import ast
import io
import math
from pathlib import Path
from core import need,integer,finite,capture,parse,descriptor,relative,encoded,pin
from contracts import exact,opaque


def header(raw,shape,max_allocation):
    need(type(raw)is bytes and len(raw)>=10 and raw[:8]==b'\x93NUMPY\x01\x00','exact prepared NPY1 primitive')
    size=int.from_bytes(raw[8:10],'little');need(0<size<=65535 and 10+size<=len(raw),'bounded header')
    text=raw[10:10+size];need(text.endswith(b'\n'),'terminated header')
    expr=ast.parse(text.decode('latin1').strip(),mode='eval')
    need(isinstance(expr.body,ast.Dict)and len(expr.body.keys)==3 and all(isinstance(x,ast.Constant)and type(x.value)is str for x in expr.body.keys)
         and {x.value for x in expr.body.keys}=={'descr','fortran_order','shape'},'exact unique primitive header fields')
    obj=ast.literal_eval(expr);need(obj['descr']=='<f8'and obj['fortran_order']is False,'only explicitly little-endian f8 C-order')
    need(type(obj['shape'])is tuple and list(obj['shape'])==list(shape)and all(type(x)is int and x>=0 for x in obj['shape']),'exact required array shape')
    payload=math.prod(shape)*8;need(10+size+payload==len(raw)and 2*payload+2*(10+size)+4096<=max_allocation,'exact extent and predecoder memory bound')
    return {'shape':list(shape),'payload_bytes':payload,'header_bytes':10+size}


def load_array(path,desc,shape,budget,cap,max_allocation):
    body,_=capture(path,desc,cap,budget,readonly=True);admitted=header(body,shape,max_allocation);budget.tick()
    import numpy as np
    need(np.__version__=='2.2.6','production numeric library version')
    array=np.load(io.BytesIO(body),allow_pickle=False)
    need(type(array)is np.ndarray and array.dtype==np.dtype('<f8')and array.shape==tuple(shape)and array.flags.c_contiguous
         and np.isfinite(array).all(),'exact finite primitive decoded array')
    budget.tick();return array,admitted


def labels(value,channel):
    exact(value,('id','session','loads','correct','probe','order','ids','n_trials','samples','fs','units'),'exact source-prepared channel metadata')
    need(value['id']==channel['id']and value['session']==channel['session'],'exact channel metadata lineage')
    n=integer(value['n_trials'],1,140);need(value['samples']==1000 and type(value['samples'])is int and value['fs']==400 and type(value['fs'])is int and value['units']=='volts','exact window/time/units')
    for key,allowed in [('loads',(1,3)),('correct',(0,1)),('probe',(0,1))]:
        need(type(value[key])is list and len(value[key])==n and all(type(x)is int and x in allowed for x in value[key]),'exact finite group labels')
    need(type(value['order'])is list and len(value['order'])==n and len(set(value['order']))==n and all(type(x)is int and 0<=x<140 for x in value['order']),'original unique row order')
    need(type(value['ids'])is list and len(value['ids'])==n and len(set(value['ids']))==n,'complete trial IDs')
    for x in value['ids']:opaque(x)
    return value


def load_case(view,root,budget,limits,*,with_arrays=True):
    from views import admit_view
    admit_view(view,view['world'],view['person']);root=Path(root)
    # Prospective whole retained array bank, not one-file-at-a-time illusion.
    total=sum(ch[k]['pin']['bytes']for ch in view['channels']for k in ('lfp','rates')if k in ch)
    need(6*total+limits['metadata_live_bytes']+65536<=limits['case_live_bytes'],'complete case planned-live capacity before any payload')
    result=[];trial_schema={}
    for ch in view['channels']:
        row=ch['metadata'];raw,_=capture(root/relative(row['path']),row['pin'],limits['metadata_bytes'],budget,readonly=True);m=labels(parse(raw),ch)
        for i,identity in enumerate(m['ids']):
            signature=(m['session'],m['order'][i],m['loads'][i],m['correct'][i],m['probe'][i])
            need(identity not in trial_schema or trial_schema[identity]==signature,'shared trial IDs retain actual session/order/labels');trial_schema[identity]=signature
        item={k:m[k]for k in ('id','session','loads','correct','probe','order','ids')}
        if view['world']!='A'and with_arrays:
            for key,shape in [('lfp',(m['n_trials'],1000)),('rates',(m['n_trials'],))]:
                row=ch[key];item[key],_=load_array(root/relative(row['path']),row['pin'],shape,budget,limits['array_bytes'],limits['case_live_bytes'])
            need((item['rates']>=0).all(),'nonnegative rates')
        else:item.update(lfp=None,rates=None)
        result.append(item)
    budget.tick();return result
