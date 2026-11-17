"""Authenticated unchanged numerical modules, with explicit portable custody."""
import importlib.util
from pathlib import Path
import sys
import types
from common import need
from portable_config import current,state

ROOT=Path(__file__).absolute().parent
ORDER=('kernel','certificate','scorer','reader.contract','authentic','custody','score_owned')
FILES={name:'numeric/'+name.replace('.','/')+'.py' for name in ORDER}
FILES['custody']='portable_custody.py'

def load_numeric(budget):
    bodies=state()['source_bodies']
    need(type(bodies) is dict,'complete authenticated portable source closure')
    names=(*ORDER,'reader','controller_interface')
    need(not any(name in sys.modules for name in names),'fresh private numerical namespace')
    modules={}
    try:
        package=types.ModuleType('reader');package.__path__=[str(ROOT/'numeric/reader')]
        package.__file__=str(ROOT/'numeric/reader/__init__.py')
        sys.modules['reader']=package;modules['reader']=package
        for name in ORDER:
            filename=FILES[name];path=ROOT/filename
            spec=importlib.util.spec_from_file_location(name,path)
            mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;modules[name]=mod
            exec(compile(bodies[filename],str(path),'exec'),mod.__dict__)
        name='controller_interface';filename='numeric/interface.py';path=ROOT/filename
        spec=importlib.util.spec_from_file_location(name,path)
        mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;modules[name]=mod
        exec(compile(bodies[filename],str(path),'exec'),mod.__dict__)
    except BaseException:
        for name,mod in modules.items():
            if sys.modules.get(name) is mod:del sys.modules[name]
        raise
    return modules,{'portable_source_lock_sha256':state()['source_lock_sha256'],
                    'historical_constructor_imported':False,'scientific_kernel_changes':False}

def capture_selected_authentic(modules,*,selection,all_candidates_closed,budget):
    need(all_candidates_closed is True,'candidate closure before reference access')
    need(type(selection) is dict and set(selection)=={'schema','descriptor','source_lock_sha256',
         'transient_use_selected','input_projection_selected','image_content_selected','private_delivery_selected'},
         'complete authentic assessment selection')
    cfg=current();ref=cfg['reference']
    need(selection['schema']=='tms_p16_authentic_assessment_selection_v1'
         and all(selection[k] is True for k in ('transient_use_selected','input_projection_selected',
                                              'image_content_selected','private_delivery_selected'))
         and selection['descriptor']==ref['descriptor']
         and selection['source_lock_sha256']==ref['source_lock_sha256'],
         'same immutable owner configuration and selected reference')
    budget.charge_read(2100000)
    value=modules['custody'].capture(selected_source_lock_sha256=ref['source_lock_sha256'],
                                   selected_descriptor_pin=ref['descriptor'])
    budget.check();modules['custody'].require_operator_reference(value)
    return value
