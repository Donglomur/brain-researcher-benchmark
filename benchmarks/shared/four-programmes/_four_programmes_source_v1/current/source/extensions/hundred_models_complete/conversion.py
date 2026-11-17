"""Selected operator-only source pickle -> safe arrays; never runs during BUILD.

Restricted globals reduce callable exposure but are not a sandbox or allocation bound.
An independently qualified external memory/filesystem/process limit is mandatory.
"""
import io
import pickle
from .guard import need,capture,strict,encoded,bare
from .array_io import save_array

def convert_part(session,original,admission,publisher):
    b=session.budget;np=session.np
    need(admission['operator_conversion_selected'] is True and admission['original']==original,'separate exact original-file conversion selection')
    need(admission['external_allocation_limit_qualified'] is True,'external unpickle allocation limit required')
    need(admission['source_version']=='versionB/MNI152/prepared_allvoxel_pkl','exact source derivative version')
    raw=capture(session.root,original,b,cap=admission['maximum_original_bytes'])
    allowed={('numpy','ndarray'):np.ndarray,('numpy','dtype'):np.dtype}
    for module_name in ('numpy.core.multiarray','numpy._core.multiarray','numpy.core.numeric','numpy._core.numeric'):
        if module_name in session.env.get('pickle_globals',{}):
            import importlib
            from .array_io import verify_file
            from pathlib import Path
            module=importlib.import_module(module_name);path=verify_file(session.root,session.env['pickle_globals'][module_name],b)
            need(Path(module.__file__).resolve()==path.resolve(),'qualified conversion native globals')
            for name in ('_reconstruct','scalar','_frombuffer'):
                if hasattr(module,name):allowed[(module_name,name)]=getattr(module,name)
    class Restricted(pickle.Unpickler):
        def find_class(self,module,name):
            need((module,name) in allowed,'unselected pickle callable forbidden')
            return allowed[(module,name)]
        def persistent_load(self,pid):raise ValueError('external pickle object forbidden')
    stream=io.BytesIO(raw);data=Restricted(stream).load();need(stream.read(1)==b'','no trailing pickle stream')
    need(type(data)is dict and set(data)=={'test_data_allvoxel','train_data_allvoxel'},'original exact two-panel dictionary')
    outputs={}
    for panel,n,repeats in (('test',102,10),('train',1000,3)):
        a=data[panel+'_data_allvoxel'];need(type(a)is np.ndarray and a.dtype.kind in ('f','i','u') and not a.dtype.hasobject,'plain original numeric response')
        need(list(a.shape)==[n,repeats,admission['voxel_count']] and np.isfinite(a).all(),'complete finite original panel geometry')
        b.charge('work',int(a.size));outputs[panel]=save_array(np,publisher,panel+'.npy',a)
    return publisher.write('CONVERSION.json',encoded({'original':original,'admission':bare(encoded(admission)),'outputs':outputs,'source_values_transformed':False,'scientific_qualification':False}))
