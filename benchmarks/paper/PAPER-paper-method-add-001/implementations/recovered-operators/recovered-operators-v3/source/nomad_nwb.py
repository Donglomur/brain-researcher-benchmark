"""Concrete bounded HDF5/NWB field intake for a separately admitted schema.

No physical dataset path is guessed from the README. This module is not invoked
during source construction; every required physical path/type/clock is a future
source-selected fact. It has no normalized-callback alternative.
"""
import io
import math
from .nomad_math import need,closed,integer,finite,identity


ACQUISITION=('binned_spikes','cursor_pos','target_pos','cursor_vel','block_num','cond_id')
TRIALS=('start_time','stop_time','cond_id','tgt_x','tgt_y','result','is_calibration','block_num')
ROLES=tuple('acquisition/'+x for x in ACQUISITION)+tuple('trials/'+x for x in TRIALS)


def convert_neural_clock(values,observed_units,clock,np,budget):
    need(observed_units==clock['expected_units'], 'actual neural-clock units match conversion evidence')
    scale=finite(clock['seconds_per_unit']);offset=finite(clock['offset_seconds'])
    need(scale>0 and clock['source_pin'], 'explicit positive source-bound neural clock conversion')
    count=values.size;budget.reserve('NWB.clock_conversion',{'raw_cast_scaled_offset':4*count})
    times=values.astype('float64')*scale+offset
    need(bool(np.isfinite(times).all()), 'finite converted full neural clock')
    return times


def read_physical_fields(catalog,artifact_name,schema,budget):
    closed(schema,['h5py_version','numpy_version','fields','clock','session_id','schema_source_pin'],
           'fully source-selected physical NWB schema')
    need(set(schema['fields'])==set(ROLES),'every described physical field, no aliases omitted')
    for role,row in schema['fields'].items():
        closed(row,['path','shape','dtype','units_attribute','expected_units'], 'exact field selection')
        need(type(row['path']) is str and row['path'].startswith('/') and
             '..' not in row['path'].split('/'),'ordinary absolute HDF5 field path')
        need(type(row['shape']) is list and row['shape'] and
             all(type(n) is int and n>=0 for n in row['shape']),'declared complete field shape')
        need(type(row['dtype']) is str and row['dtype'],'observed physical dtype required')
        # Null means unresolved, not permission to discard unit evidence.
        need(row['units_attribute'] is not None and row['expected_units'] is not None,
             'original field units/explicit unitless disposition unresolved')
    closed(schema['clock'],['path','shape','dtype','units_attribute','expected_units','seconds_per_unit','offset_seconds','source_pin'],
           'explicit physical neural clock and source-selected conversion')
    clock=schema['clock']
    need(type(clock['units_attribute']) is str and clock['units_attribute'] not in ('','explicit_unitless')
         and type(clock['expected_units']) is str and clock['expected_units'] and clock['source_pin'],
         'physical clock attribute and source evidence required')
    need(finite(clock['seconds_per_unit'])>0,'resolved positive clock conversion');finite(clock['offset_seconds'])
    need(type(schema['schema_source_pin']) is str and schema['schema_source_pin'],
         'independently selected schema source identity')
    # All declared extents are reserved before loading HDF5 or opening its tree.
    import h5py
    import numpy as np
    need(h5py.__version__==schema['h5py_version'] and np.__version__==schema['numpy_version'],
         'exact separately selected HDF5/NumPy versions')
    entries=list(schema['fields'].values())+[schema['clock']]
    byte_slots={}
    for i,row in enumerate(entries):
        dtype=np.dtype(row['dtype'])
        need(dtype.kind in 'biufSU' and dtype.itemsize>0,
             'bounded primitive physical field dtype before data capture')
        byte_slots['field_'+str(i)]=(math.prod(row['shape'])*max(dtype.itemsize,8)+7)//8
    budget.reserve('NWB.full_declared_fields',byte_slots)
    raw=catalog.raw(artifact_name)
    result={};field_units={};failure=None;file=None
    try:
        file=h5py.File(io.BytesIO(raw),'r')
        def ordinary(path):
            need(type(path) is str and path.startswith('/') and '..' not in path.split('/'),
                 'absolute ordinary HDF5 path')
            parts=path.strip('/').split('/')
            need(all(parts),'no empty internal HDF5 path component')
            current=''
            for part in parts:
                current+='/'+part
                need(type(file.get(current,getlink=True)) is h5py.HardLink,
                     'no external/soft-link ancestor before traversal')
        for role,row in schema['fields'].items():
            ordinary(row['path'])
            node=file.get(row['path'],getlink=True)
            need(type(node) is h5py.HardLink,'no external/soft-link source substitution')
            data=file[row['path']]
            need(type(data) is h5py.Dataset and list(data.shape)==row['shape'] and
                 data.dtype.str==row['dtype'],'complete observed field shape/dtype')
            if row['units_attribute']=='explicit_unitless':
                need(row['expected_units']=='unitless','named unitless policy')
            else:
                unit=data.attrs.get(row['units_attribute'])
                if type(unit) is bytes:unit=unit.decode('utf-8')
                need(unit==row['expected_units'],'actual field unit metadata')
            need(data.dtype.kind in 'biufSU','no pickle/object/compound/vlen dtype fallback')
            field_units[role]=row['expected_units']
            result[role]=data[()]
        row=schema['clock'];ordinary(row['path']);node=file.get(row['path'],getlink=True)
        need(type(node) is h5py.HardLink,'ordinary clock object')
        data=file[row['path']]
        need(type(data) is h5py.Dataset and list(data.shape)==row['shape'] and
             data.dtype.str==row['dtype'] and data.dtype.kind in 'fiu','actual full physical clock')
        unit=data.attrs.get(row['units_attribute'])
        if type(unit) is bytes:unit=unit.decode('utf-8')
        need(unit==row['expected_units'],'actual neural-clock units match conversion evidence')
        raw_times=data[()]
        times=convert_neural_clock(raw_times,unit,row,np,budget)
        result['timestamps']=times
        n=result['acquisition/binned_spikes'].shape[0]
        need(result['timestamps'].shape==(n,),'one complete timestamp per neural sample')
        need(all(float(a)<float(b) for a,b in zip(result['timestamps'],result['timestamps'][1:])),
             'ordered complete physical neural clock')
        for k in ACQUISITION:need(result['acquisition/'+k].shape[0]==n,'same complete acquisition support')
        nt=result['trials/start_time'].shape[0]
        for k in TRIALS:need(result['trials/'+k].shape==(nt,),'full trial table column support')
    except BaseException as error:
        failure=error
    finally:
        if file is not None:
            try:file.close()
            except BaseException as cleanup:
                if failure is None:failure=cleanup
                else:setattr(failure,'nwb_close_secondary',type(cleanup).__name__)
    if failure is not None:raise failure
    return {'session_id':schema['session_id'],'fields':result,'field_units':field_units,
        'clock_evidence':{'units_attribute':schema['clock']['units_attribute'],'observed_units':unit,
            'seconds_per_unit':schema['clock']['seconds_per_unit'],'offset_seconds':schema['clock']['offset_seconds'],
            'source_pin':schema['clock']['source_pin'],'output_units':'seconds'},
        'physical_source_descriptor':catalog.artifacts[artifact_name],
        'schema_identity':identity(schema),'original_biological_schema_independently_qualified':False,
        'native_HDF5_workspace_RSS':'unmeasured and deployment-dependent'}


def physical_trial_rows(captured,selection):
    """Join true HDF5 columns to exact empirical IDs before sequence operations."""
    closed(selection,['trial_ids','block_labels','sequence_members','source_schema_identity',
                      'calibration_block_mapping','trial_clock'],'complete source-selected trial/sequence identity join')
    need(selection['source_schema_identity']==captured['schema_identity'],'exact captured physical schema')
    f=captured['fields'];n=len(f['trials/start_time']);ids=selection['trial_ids']
    need(type(ids) is list and len(ids)==n and len(set(ids))==n,'every physical trial ID')
    mapping=selection['calibration_block_mapping']
    closed(mapping,['source_pin','calibration_blocks','evaluation_blocks','flag_codes'], 'resolved exact calibration mapping')
    need(type(mapping['source_pin']) is str and mapping['source_pin'],'calibration mapping source identity')
    cal=mapping['calibration_blocks'];ev=mapping['evaluation_blocks']
    need(type(cal) is list and len(cal)==1 and type(ev) is list and ev and len(set(cal+ev))==len(cal+ev),
         'one calibration block and full distinct evaluation blocks')
    codes=mapping['flag_codes'];need(type(codes) is list and codes,'explicit physical calibration flag codes')
    seen=[]
    for code in codes:
        closed(code,['value','role'],'exact physical flag code')
        need(type(code['value']) in (str,int,float,bool) and code['role'] in ('calibration','evaluation'), 'literal flag code and role')
        if type(code['value']) is float:finite(code['value'])
        key=(type(code['value']).__name__,str(code['value']));need(key not in seen,'unique typed flag code');seen.append(key)
    need({r['role'] for r in codes}=={'calibration','evaluation'},'both physical flag dispositions')
    clocks=selection['trial_clock'];closed(clocks,['source_pin','start_time','stop_time'],'explicit physical trial clock conversions')
    need(type(clocks['source_pin']) is str and clocks['source_pin'],'trial clock source evidence')
    for key in ('start_time','stop_time'):
        row=clocks[key];closed(row,['physical_units','seconds_per_unit','offset_seconds'],'complete trial clock conversion')
        need(row['physical_units']==captured['field_units']['trials/'+key] and finite(row['seconds_per_unit'])>0,
             'trial clock conversion matches physically captured units');finite(row['offset_seconds'])
    blockmap=selection['block_labels'];need(type(blockmap) is dict and set(blockmap.values())==set(cal+ev)
        and len(set(blockmap.values()))==len(blockmap), 'complete one-to-one physical block labels')
    out={};dispositions={};observed=set()
    for i,tid in enumerate(ids):
        code=f['trials/block_num'][i].item()
        need(str(code) in blockmap,'every observed physical block has admitted identity')
        block=blockmap[str(code)];observed.add(block)
        flag=f['trials/is_calibration'][i].item()
        if type(flag) is bytes:flag=flag.decode('utf-8')
        matched=[r for r in codes if type(r['value']) is type(flag) and r['value']==flag]
        need(len(matched)==1,'every observed physical calibration flag has one explicit mapping')
        role=matched[0]['role'];need((block in cal)==(role=='calibration'), 'physical flag agrees with actual mapped block')
        dispositions[tid]={'physical_flag':flag,'block_id':block,'role':role}
        result=f['trials/result'][i].item()
        if type(result) is bytes:result=result.decode('utf-8')
        out[tid]={'trial_id':tid,'block_id':blockmap[str(code)],'result':result,
                  'start_time':finite(finite(f['trials/start_time'][i].item())*clocks['start_time']['seconds_per_unit']+clocks['start_time']['offset_seconds']),
                  'stop_time':finite(finite(f['trials/stop_time'][i].item())*clocks['stop_time']['seconds_per_unit']+clocks['stop_time']['offset_seconds'])}
    need(observed==set(cal+ev),'every selected calibration/evaluation block has actual physical trials')
    return {'trial_rows':out,'sequence_members':selection['sequence_members'],
            'physical_schema_identity':captured['schema_identity'],
            'offline_calibration_mapping':mapping,'actual_calibration_dispositions':dispositions,'trial_clock_conversion':clocks}
