"""Concrete participant entry inside an already isolated, qualified native child.

This module must never be used to import participant source into a trusted host.
External fixed bootstrap admits source/input images and owns native caps first.
"""
import importlib.util
from pathlib import Path
from .contracts import need

def load_method(captured_path):
    # Fixed bootstrap supplies this exact isolated path after authenticating it.
    path=Path(captured_path)
    need(path==Path('/participant/method.py'),'fixed child-only source destination')
    spec=importlib.util.spec_from_file_location('n061_participant_method',path)
    need(spec is not None and spec.loader is not None,'ordinary participant module')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    need(callable(getattr(module,'fit',None)) and callable(getattr(module,'infer',None)),'fit and infer participant ABI')
    return module

def fit(method,source_view,trained_tool):
    need(all(v.get('status')=='unavailable' or all('values' in w for w in v['windows']) for v in source_view),'source labeled views')
    return method.fit({'task':'NEURAL-061','source':source_view,'tool':trained_tool})

def infer(method,state,query_view,trained_tool):
    import numpy as np
    need(query_view['status']=='complete' and all('values' not in w for w in query_view['windows']),'no query target values')
    rows=method.infer({'task':'NEURAL-061','query':query_view,'tool':trained_tool},state)
    need(type(rows) in (tuple,list) and len(rows)==len(query_view['windows']),'complete returned query roster')
    out=[]
    for row,window in zip(rows,query_view['windows'],strict=True):
        need(type(row) is dict and set(row)=={'query','values'} and row['query']==window['query'],'exact prediction query identity')
        values=np.asarray(row['values']);need(values.dtype.kind in 'fiu' and not values.dtype.hasobject and np.isfinite(values).all(),'primitive finite predictions')
        need(len(values)==len(window['mask']),'all target positions before masking')
        out.append({'query':row['query'],'values':values})
    return {'status':'complete','windows':tuple(out)}
