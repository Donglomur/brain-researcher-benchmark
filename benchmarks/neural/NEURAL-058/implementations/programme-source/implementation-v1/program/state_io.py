"""Safe complete reference state as primitive arrays plus bounded strict JSON."""
from core import need, integer
from arrays import write_array, read_array, write_json, read_json


def save(root,state,budget,limits):
    import numpy as np
    serial=0; entries=[]
    def visit(value,depth=0):
        nonlocal serial
        budget.tick(); need(depth<=32,'state nesting bound')
        if isinstance(value,np.ndarray):
            serial+=1; need(serial<=limits['state_arrays'],'full state array cap')
            d=write_array(root,'state-'+str(serial)+'.npy',value,budget,limits['expanded_bytes'])
            entries.append(d); return {'__array__':d}
        if type(value) is dict:
            need(all(type(k)is str and k!='__array__' for k in value),'ordinary state keys')
            return {k:visit(v,depth+1) for k,v in value.items()}
        if type(value) in (list,tuple): return [visit(v,depth+1) for v in value]
        need(value is None or type(value) in (str,int,float,bool),'safe reference metadata scalar')
        return value
    tree=visit(state)
    metadata={'schema':'neural058_complete_state_v1','tree':tree,'array_count':serial}
    descriptor=write_json(root,'STATE.json',metadata,budget,limits['metadata_bytes'])
    budget.tick(); return {'metadata':descriptor,'arrays':entries}


def load(root,descriptor,budget,limits):
    document=read_json(root,descriptor,budget,limits['metadata_bytes'])
    need(document.get('schema')=='neural058_complete_state_v1','safe state schema')
    count=0; paths=set()
    def visit(value,depth=0):
        nonlocal count
        budget.tick(); need(depth<=32,'safe state nesting')
        if type(value) is dict:
            if '__array__' in value:
                need(set(value)=={'__array__'},'exact tagged array')
                count+=1; need(count<=limits['state_arrays'],'full state array read bound')
                item=value['__array__']; need(item['path'] not in paths,'unique reference state body')
                paths.add(item['path'])
                return read_array(root,item,budget,limits['array_bytes'],limits['expanded_bytes'])[0]
            return {k:visit(v,depth+1) for k,v in value.items()}
        if type(value)is list: return [visit(v,depth+1) for v in value]
        need(value is None or type(value) in (str,int,float,bool),'strict primitive state')
        return value
    state=visit(document['tree']); need(count==document['array_count'],'complete state arrays')
    budget.tick(); return state
