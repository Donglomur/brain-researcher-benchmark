"""Trusted original-recording to nine-method views; never participant-selected."""
from .protocol import HandleCustody,need, fields, identity, boundary, stream_capture, observation, Refusal


def bind_events(record, rows, events):
    """Metadata-only one-to-one scientific row join, without labels or arrays."""
    need(record['dataset'] in ('TUAB','TUEV') and rows, 'complete Temple source recording')
    need(len({r['id'] for r in rows})==len(rows), 'unique complete original row ids')
    rate=record['sampling_hz'];need(type(rate) in (int,float) and rate>0,'original physical source clock')
    if record['dataset']=='TUAB':
        need(events is None,'TUAB windows derive from complete source recording, not annotations')
        result={}
        for row in rows:
            window=row['raw_window'];fields(window,('epoch_index','start_sample','end_sample'),'original TUAB interval')
            need(window['epoch_index'] is None and window['start_sample']>=0 and window['end_sample']-window['start_sample']==10*rate and window['start_sample']%(10*rate)==0,'exact original continuous ten-second window')
            key=str(int(window['start_sample']/(10*rate)));need(key not in result,'unique full TUAB window');result[key]=row
        return result
    need(type(events) is list and events,'complete original TUEV event times')
    event_map={}
    for event in events:
        fields(event,('id','start_seconds','end_seconds'),'signal-only event timing')
        need(type(event['id']) is str and event['id'] not in event_map and type(event['start_seconds']) in (int,float) and type(event['end_seconds']) in (int,float) and 0<=event['start_seconds']<event['end_seconds'],'unique valid original TUEV event identity and interval')
        event_map[event['id']]=event
    need(len({r['event'] for r in rows})==len(rows) and {r['event'] for r in rows}==set(event_map),'all original TUEV events exactly once; no available subset or invented event')
    return {row['event']:row for row in rows}


def build_recording_views(raw, record, rows, events, destination, qualification, budget, produced):
    """Actual complete continuous preprocessing and durable scientific lineage."""
    import numpy as np
    from .temple_reference import METHODS, preparation_contract, prepare_recording, extract_epochs
    from .data_preparation import OriginalArrayWriter
    bound=bind_events(record,rows,events);result={r['id']:{} for r in rows};cache={}
    need(getattr(raw,'ndim',None)==2,'Temple source is full continuous recording, never already segmented epoch')
    for method in METHODS:
        contract=preparation_contract(record['dataset'],method);contract_id=identity(contract)
        if contract_id not in cache:
            prepared,metadata=boundary(budget,'whole_temple_recording_preparation',prepare_recording,raw,{k:record[k] for k in ('channels','sampling_hz','units')},record['dataset'],method)
            need(prepared.nbytes*5+raw.nbytes<=budget.limits['resident_bytes'],'whole method preprocessing and wrap allocation reserved; no reduced recording fallback')
            views={};seen=set()
            with HandleCustody('original_temple_epoch_iteration') as epoch_owner:
                iterator=epoch_owner.own(extract_epochs(prepared,metadata,record['dataset'],method,events),'epochs')
                while True:
                    budget.guard('before_each_original_temple_epoch')
                    try:epoch=next(iterator)
                    except StopIteration:break
                    budget.guard('after_each_original_temple_epoch');key=epoch['event_id'];need(key in bound and key not in seen,'actual extracted event joins exactly one qualified original row');seen.add(key);row=bound[key]
                    value=np.asarray(epoch['signal'],dtype='<f8',order='C');need(list(value.shape)==[len(contract['output_channels']),contract['samples']] and np.isfinite(value).all(),'all finite complete method signal samples')
                    lineage={'raw_source_identity':identity(record),'raw_member':record['member'],'original_row_id':row['id'],'original_event':epoch['source_event'],'derived_interval':epoch['interval'],'preparation_contract':contract,'continuous_transform_before_epoching':True}
                    name=identity(lineage)+'.npy';writer=None;failure=None;write_error=None;capacity=value.nbytes+4096
                    try:
                        with HandleCustody('original_temple_signal_writer') as writer_owner:
                            writer=writer_owner.own(OriginalArrayWriter(destination,name,capacity,budget),'writer');np.lib.format.write_array(writer,value,version=(1,0),allow_pickle=False);writer.flush()
                    except BaseException as exc:write_error=exc;failure=observation(exc)
                    if failure is not None:raise Refusal('original whole Temple signal write failed',observation={'row':row['id'],'method':method,'failure':failure,'original_writer':None if writer is None else writer.evidence(),'earlier_original_captures':produced}) from write_error
                    need(writer.extent==writer.accepted and writer.extent<=capacity,'original complete Temple bytes within reserve')
                    capture=stream_capture(destination,name,size=writer.extent,cap=budget.limits['per_file_bytes'],ledger=budget)
                    view={'signal':{'root':'prepared_signals','member':capture['source'],'format':'npy_little_endian_c_float','shape':list(value.shape),'label_free_evidence':qualification},'channels':contract['output_channels'],'sampling_hz':contract['sampling_hz'],'units':contract['units'],'interval':epoch['interval'],'transform_ancestry':identity(lineage),'preparation_contract':contract}
                    views[row['id']]=view;produced.append({'row_id':row['id'],'method_preparation':contract_id,'original_capture':capture,'lineage':lineage,'same_source_view_for_both_actors_and_modes':True})
            need(seen==set(bound),'all complete source windows/events retained, no silent drop');cache[contract_id]=views;prepared=None
        for row in rows:result[row['id']][method]={'H':cache[contract_id][row['id']],'P_I':cache[contract_id][row['id']]}
    need(all(set(views)==set(METHODS) for views in result.values()),'all nine concrete method views for every original event')
    return result
