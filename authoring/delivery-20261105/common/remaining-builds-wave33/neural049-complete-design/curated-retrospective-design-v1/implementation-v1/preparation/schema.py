"""The selected converter schema, explicitly qualified before original HDF5 access."""
from contextlib import contextmanager
from . import contracts as c
from .storage import closing

SIGNAL='/acquisition/ElectricalSeries'
TABLE='/general/extracellular_ephys/electrodes'
REACH='/intervals/reaches'
GEOMETRY={'schema','samples','channels','rows','starting_time','rate','conversion','offset','unit','time_unit','channel_map'}

def validate_geometry(g,axis,budget):
    c.need(type(g) is dict and set(g)==GEOMETRY and g['schema']==c.SCHEMA,'exact qualified geometry')
    for key in ('samples','channels','rows'): c.need(c.integer(g[key]),'nonnegative full geometry')
    c.need(g['channels']>0 and g['channels']<=budget.limits['channels'] and len(axis)<=budget.limits['channels'],'channel cap')
    c.need(g['rows']<=budget.limits['rows'] and g['rate']==500 and type(g['rate']) in (int,float),'qualified exact500Hz')
    c.need(all(c.finite(g[k]) for k in ('starting_time','conversion','offset')) and g['conversion']!=0,'qualified finite conversion and clock')
    c.need(g['unit']=='volts' and g['time_unit']=='seconds','selected SI electrical/time units')
    mapping=g['channel_map'];c.need(type(mapping) is list and len(mapping)==g['channels'],'every source channel mapped')
    seen=[]
    for j,item in enumerate(mapping):
        c.need(type(item) is dict and set(item)=={'column','table_row','table_id','group_path','axis_id'}
               and type(item['column']) is int and item['column']==j and c.integer(item['table_row']) and type(item['table_id']) is int,'complete ordered DTR map')
        c.need(item['axis_id'] in axis and item['axis_id'] not in seen,'unique admitted person channel mapping')
        seen.append(item['axis_id']);c.need(type(item['group_path']) is str and item['group_path'].startswith('/general/extracellular_ephys/'),'qualified group reference path')
    return g

def node(file,path,h5,dataset=True):
    c.need(type(path) is str and path.startswith('/') and all(x not in ('','.','..') for x in path.split('/')[1:]),'canonical internal HDF5 path')
    current=''
    for part in path.split('/')[1:]:
        current+='/'+part
        link=file.get(current,getlink=True)
        c.need(isinstance(link,h5.HardLink),'no soft/external HDF5 links')
    result=file[path]
    if dataset:
        c.need(isinstance(result,h5.Dataset) and not result.is_virtual and not result.external,'ordinary internal dataset')
    else:c.need(isinstance(result,h5.Group),'ordinary group/table')
    return result

def numeric(ds,shape,kind,budget):
    c.need(tuple(ds.shape)==tuple(shape) and ds.dtype.kind in kind and ds.dtype.itemsize<=8
           and ds.dtype.fields is None and ds.dtype.subdtype is None,'native primitive shape/dtype')
    count=1
    for n in shape:count*=n
    budget.elements(count)
    return ds

def scalar(ds,index,budget):
    # Exact primitive shape is checked by caller before any allocation/read.
    budget.array(128)
    x=budget.call('HDF5 scalar read',ds.__getitem__,index)
    value=x.item() if hasattr(x,'item') else x
    c.need(c.finite(value),'finite original scalar')
    return value

def numeric_attribute(value):
    # h5py/NumPy scalar wrappers become exact Python primitives; bool is never numeric.
    primitive=value.item() if hasattr(value,'item') else value
    c.need(c.finite(primitive),'finite non-Boolean numeric attribute')
    return primitive

class Day:
    def __init__(self,file,g,axis,h5,budget):
        self.file,self.g,self.axis,self.h5,self.budget=file,g,axis,h5,budget
        validate_geometry(g,axis,budget)
        self.data=numeric(node(file,SIGNAL+'/data',h5),(g['samples'],g['channels']),'fi',budget)
        start=numeric(node(file,SIGNAL+'/starting_time',h5),(),'f',budget)
        c.need(SIGNAL+'/timestamps' not in file,'timestamps alternative unselected')
        c.need(float(scalar(start,(),budget))==float(g['starting_time']),'actual starting time matches independent geometry')
        # Qualified source pin/native metadata profile bounds these known scalar attributes.
        rate=budget.call('HDF5 rate attribute',start.attrs.__getitem__,'rate')
        unit=budget.call('HDF5 clock unit attribute',start.attrs.__getitem__,'unit')
        if isinstance(unit,bytes):unit=unit.decode('ascii')
        c.need(numeric_attribute(rate)==500 and unit==g['time_unit'],'actual native clock attributes')
        for key in ('conversion','offset','unit'):
            value=budget.call('HDF5 electrical attribute '+key,self.data.attrs.__getitem__,key)
            if isinstance(value,bytes):value=value.decode('ascii')
            if key!='unit':value=numeric_attribute(value)
            c.need(value==g[key],'actual native conversion/unit '+key)
        table=node(file,TABLE,h5,dataset=False)
        dtr=numeric(node(file,SIGNAL+'/electrodes',h5),(g['channels'],),'iu',budget)
        reference=budget.call('HDF5 DTR table reference',dtr.attrs.__getitem__,'table')
        c.need(isinstance(reference,h5.Reference) and bool(reference) and file[reference].id==table.id,'DTR resolves identical electrode table object')
        ids=node(file,TABLE+'/id',h5);numeric(ids,(g['channels'],),'iu',budget)
        groups=node(file,TABLE+'/group',h5)
        c.need(groups.shape==(g['channels'],) and h5.check_dtype(ref=groups.dtype) is h5.Reference,'electrode group reference vector')
        table_rows=[];table_ids=[]
        for item in g['channel_map']:
            row=scalar(dtr,item['column'],budget)
            c.need(type(row) is int and row==item['table_row'] and 0<=row<g['channels'],'DTR row joins complete map')
            value=scalar(ids,row,budget)
            c.need(type(value) is int and value==item['table_id'],'electrode ID joins independent map')
            group=budget.call('HDF5 electrode group reference read',groups.__getitem__,row)
            c.need(isinstance(group,h5.Reference) and bool(group),'valid group object reference')
            expected=node(file,item['group_path'],h5,dataset=False)
            c.need(file[group].id==expected.id,'exact electrode group object')
            table_rows.append(row);table_ids.append(value)
        c.need(len(set(table_rows))==g['channels'] and len(set(table_ids))==g['channels'],'all channels unique; no filtering')
        self.columns={}
        for name in ('id','start_time',*c.ENDPOINTS.values()):
            self.columns[name]=numeric(node(file,REACH+'/'+name,h5),(g['rows'],),'iu' if name=='id' else 'fi',budget)
        budget.tick()

    def row(self,i):
        c.need(c.integer(i) and i<self.g['rows'],'original ordered row index')
        values={k:scalar(v,i,self.budget) for k,v in self.columns.items()}
        c.need(type(values['id']) is int,'integer original interval ID')
        c.need(0<=values['start_time']<86400 and -90<=values['Reach_angle_degrees']<=90
               and values['Reach_magnitude_px']>=0 and values['Onset_speed_px_per_sec']>=0,'source target units/support; no clipping')
        return values

    def epoch(self,w,np):
        n=len(self.axis);g=self.g
        cells=n*5000
        self.budget.elements(cells);self.budget.array(cells*9)
        # Caller holds enough for output, read slab, finite mask, conversion and copies.
        x=np.zeros((n,5000),dtype='<f8');mask=np.zeros((n,5000),dtype='|b1')
        lo,hi=w['source_read_start'],w['source_read_stop'];width=hi-lo
        reason={'outside_day_positions':5000-width,'absent_channels':n-g['channels'],'nonfinite_source_values':0}
        if width:
            self.budget.elements(width*g['channels']);self.budget.array(width*g['channels']*32)
            slab=self.budget.call('HDF5 same-day all-channel epoch',self.data.__getitem__,(slice(lo,hi),slice(None)))
            slab=np.asarray(slab,dtype='<f8')
            valid=np.isfinite(slab)
            # Finite zero remains valid; conversion overflow is a numerical failure.
            converted=slab*g['conversion']+g['offset']
            c.need(bool(np.all(np.isfinite(converted[valid]))),'finite admitted conversion')
            reason['nonfinite_source_values']=int(valid.size-np.count_nonzero(valid))
            start=lo-w['first_index']
            for item in g['channel_map']:
                k=self.axis.index(item['axis_id']);j=item['column']
                x[k,start:start+width]=np.where(valid[:,j],converted[:,j],0.)
                mask[k,start:start+width]=valid[:,j]
        self.budget.tick();return x,mask,reason

@contextmanager
def open_day(store,source_root,source,axis,environment):
    # This entry is reached only after full external authority qualification.
    import numpy as np
    import h5py as h5
    c.need(np.__version__==environment['numpy'] and h5.__version__==environment['h5py'],'exact qualified native versions')
    with store.verified(source_root,{'path':source['path'],'pin':source['pin']}) as stream:
        file=h5.File(stream,'r')
        with closing(file,store.meter,'HDF5 file'):
            yield Day(file,source['geometry'],axis,h5,store.meter),np
