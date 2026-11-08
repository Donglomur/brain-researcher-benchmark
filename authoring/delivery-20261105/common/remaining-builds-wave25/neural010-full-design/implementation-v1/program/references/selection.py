"""Closed inner predictions -> complete event calibration -> deterministic choice."""
import math
from common import need,exact,finite,integer,descriptor,STRONG_GRID,MONTAGE_GRID,load_array
from contracts import check_context,validation_rows,normalize_worker
import event_protocol as event


def validate(request,io,out,identity):
    predictions=io.json(request['predictions']);exact(predictions,('schema','source_identity','model','fit_receipt','query_manifest','prepared_query_view','normalization','context','family','condition','grid_index','support_sha256','threshold','threshold_kind','records','original_prediction_task_id','qualification'))
    need(predictions['schema']=='neural010-predictions-v1' and predictions['source_identity']==identity and predictions['qualification'] is False and predictions['original_prediction_task_id']=='NEURAL-009','sealed complete prediction source')
    people=check_context(predictions['context']);inner=predictions['context']['inner_person'];need(inner is not None and len(people)==21 and predictions['threshold'] is None and predictions['threshold_kind']=='probability','only closed inner predictions, never outer outcomes')
    family=predictions['family'];condition=predictions['condition'];grid=predictions['grid_index'];need((family=='strong' and condition in ('joint','matched_no_eeg') and integer(grid,0,8)) or (family=='montage_only' and condition=='montage_only' and grid is None),'inner reference family')
    thresholds=STRONG_GRID if family=='strong' else MONTAGE_GRID
    need(type(request['thresholds']) is list and request['thresholds']==list(thresholds) and all(type(x) is float for x in request['thresholds']),'complete exact historical/strong threshold grid')
    fit_receipt=io.json(predictions['fit_receipt'])
    need(fit_receipt['schema']=='neural010-fit-receipt-v1' and fit_receipt['model']==predictions['model'] and fit_receipt['source_identity']==identity and fit_receipt['training_people']==people and fit_receipt['selection'] is None and fit_receipt['qualified'] is False,'closed21-person fit lineage')
    for k in ('context','family','condition','grid_index','support_sha256'):need(fit_receipt[k]==predictions[k],'inner fit/prediction join '+k)
    # Allowed inner labels are read only after closed predictions and fit ancestry.
    normalized,validation_manifest,normalization=normalize_worker(io,request['records'],None,'validation',condition,predictions['context'],out,identity)
    rows=validation_rows(normalized);need({r['patient_id'] for r in rows}=={inner},'only permitted inner labels')
    predrows=predictions['records'];need(type(predrows) is list and len(predrows)==len(rows),'complete prediction membership');per_threshold=[[] for _ in thresholds];total=0
    for row,pred in zip(rows,predrows):
        exact(pred,('recording_id','patient_id','duration_seconds','probabilities','scores','events'))
        for k in ('recording_id','patient_id','duration_seconds'):need(pred[k]==row[k],'all validation records and seconds match sealed predictions')
        need(pred['scores'] is None and pred['events'] is None,'unselected inner probabilities');d=row['duration_seconds'];total+=d;need(total<=io.limits['max_rows'] and d*64<=io.limits['max_design_bytes'],'complete continuous validation allocation')
        prob=load_array(io,pred['probabilities'],(d,),'float64');need(bool(((prob>=0)&(prob<=1)).all()),'complete bounded raw probability stream')
        for i,threshold in enumerate(thresholds):
            scores=[int(p>=threshold) for p in prob];hypothesis=event.from_scores(scores,d);per_threshold[i].append(event.count_events(row['events'],hypothesis,d))
    metrics=[]
    for threshold,counts in zip(thresholds,per_threshold):
        summary=event.summarize(counts);need(summary['event_f1'] is not None and finite(summary['event_f1']) and finite(summary['false_alarms_per_24_observed_hours']),'defined full-person event F1/FAR')
        metrics.append({'threshold':threshold,'summary':summary,'per_record_counts':[{'recording_id':r['recording_id'],'counts':c} for r,c in zip(rows,counts)]})
    result={'schema':'neural010-validation-v1','source_identity':identity,'context':predictions['context'],'family':family,'condition':condition,'grid_index':grid,'person':inner,'predictions':request['predictions'],'validation_records':validation_manifest,'prepared_validation_view':request['records'],'normalization':normalization,'model':predictions['model'],'fit_receipt':predictions['fit_receipt'],'support_sha256':predictions['support_sha256'],'training_people':people,'recording_ids':[r['recording_id'] for r in rows],'observed_seconds':total,'threshold_metrics':metrics,'qualification':False}
    return io.write_json(out/'VALIDATION.json',result)


def choose(calibration):
    """Pure exact-binary64 lexicographic selection, no tolerance clustering."""
    need(type(calibration) is list and calibration,'complete finite calibration')
    for row in calibration:
        exact(row,('grid_index','threshold','patient_macro_event_f1','patient_macro_false_alarms_per_24h'))
        need((row['grid_index'] is None or integer(row['grid_index'],0,8)) and finite(row['threshold']) and finite(row['patient_macro_event_f1']) and 0<=row['patient_macro_event_f1']<=1 and finite(row['patient_macro_false_alarms_per_24h']) and row['patient_macro_false_alarms_per_24h']>=0,'finite selection objective')
    return max(calibration,key=lambda r:(r['patient_macro_event_f1'],-r['patient_macro_false_alarms_per_24h'],r['threshold'],-(r['grid_index'] or 0)))


def validate_selection(doc):
    exact(doc,('schema','source_identity','context','family','condition','expected_validation_people','validation_receipts','calibration','grid_index','threshold','selection_rule','qualified'))
    need(doc['schema']=='neural010-selection-v1' and doc['qualified'] is False,'source-only selection');people=check_context(doc['context']);need(doc['context']['inner_person'] is None and doc['expected_validation_people']==people and len(people)==22,'all22 final selection people')
    family=doc['family'];condition=doc['condition'];need((family=='strong' and condition in ('joint','matched_no_eeg')) or (family=='montage_only' and condition=='montage_only'),'selection family')
    grids=range(9) if family=='strong' else (None,);thresholds=STRONG_GRID if family=='strong' else MONTAGE_GRID
    need(type(doc['validation_receipts']) is list and len(doc['validation_receipts'])==len(grids)*22,'all required validation receipts')
    for d in doc['validation_receipts']:descriptor(d)
    calibration=doc['calibration'];need([(r['grid_index'],r['threshold']) for r in calibration]==[(g,t) for g in grids for t in thresholds],'complete fixed calibration pairs')
    best=choose(calibration);need(doc['grid_index']==best['grid_index'] and doc['threshold']==best['threshold'] and doc['selection_rule']=='max_mean_person_f1,min_mean_person_far,higher_threshold,earlier_grid_exact_binary64','exact chosen pair')


def select(request,io,out,identity):
    people=check_context(request['context']);need(request['context']['inner_person'] is None and len(people)==22 and request['expected_validation_people']==people,'complete22-person outer training selection')
    family,condition=request['family'],request['condition'];need((family=='strong' and condition in ('joint','matched_no_eeg')) or (family=='montage_only' and condition=='montage_only'),'selected family')
    grids=range(9) if family=='strong' else (None,);thresholds=STRONG_GRID if family=='strong' else MONTAGE_GRID;descs=request['validation_receipts'];need(type(descs) is list and len(descs)==len(grids)*22,'all independent validation jobs required')
    found={};person_inputs={};person_ids={}
    for desc in descs:
        receipt=io.json(desc);exact(receipt,('schema','source_identity','context','family','condition','grid_index','person','predictions','validation_records','prepared_validation_view','normalization','model','fit_receipt','support_sha256','training_people','recording_ids','observed_seconds','threshold_metrics','qualification'))
        need(receipt['schema']=='neural010-validation-v1' and receipt['source_identity']==identity and receipt['qualification'] is False and receipt['family']==family and receipt['condition']==condition,'matching closed calibration source and condition')
        pid=receipt['person'];grid=receipt['grid_index'];need(pid in people and grid in grids and (grid,pid) not in found,'one independent result per setting and inner person')
        context=dict(request['context'],inner_person=pid);need(receipt['context']==context and receipt['training_people']==check_context(context),'exact inner exclusion and full21 support')
        need(receipt['prepared_validation_view']==person_inputs.setdefault(pid,receipt['prepared_validation_view']) and receipt['recording_ids']==person_ids.setdefault(pid,receipt['recording_ids']),'identical full-person validation support across all settings')
        need(integer(receipt['observed_seconds'],1,10000000),'full observed seconds');metrics=receipt['threshold_metrics'];need(type(metrics) is list and len(metrics)==len(thresholds),'all thresholds')
        for row,threshold in zip(metrics,thresholds):
            exact(row,('threshold','summary','per_record_counts'));need(type(row['threshold']) is float and row['threshold']==threshold,'exact threshold order');counts=row['per_record_counts'];need([x['recording_id'] for x in counts]==receipt['recording_ids'],'all records in each validation metric');summary=event.summarize([x['counts'] for x in counts]);need(summary==row['summary'] and summary['observed_seconds']==receipt['observed_seconds'] and summary['event_f1'] is not None,'full additive event summary integrity')
            need(finite(summary['event_f1']) and 0<=summary['event_f1']<=1 and finite(summary['false_alarms_per_24_observed_hours']) and summary['false_alarms_per_24_observed_hours']>=0,'all22 F1/FAR defined')
        found[(grid,pid)]=receipt
    need(set(found)=={(g,p) for g in grids for p in people},'complete Cartesian calibration; no failed-setting exclusion')
    calibration=[]
    for grid in grids:
        for i,t in enumerate(thresholds):
            summaries=[found[(grid,p)]['threshold_metrics'][i]['summary'] for p in people];calibration.append({'grid_index':grid,'threshold':t,'patient_macro_event_f1':math.fsum(x['event_f1'] for x in summaries)/22,'patient_macro_false_alarms_per_24h':math.fsum(x['false_alarms_per_24_observed_hours'] for x in summaries)/22})
    best=choose(calibration);result={'schema':'neural010-selection-v1','source_identity':identity,'context':request['context'],'family':family,'condition':condition,'expected_validation_people':people,'validation_receipts':descs,'calibration':calibration,'grid_index':best['grid_index'],'threshold':best['threshold'],'selection_rule':'max_mean_person_f1,min_mean_person_far,higher_threshold,earlier_grid_exact_binary64','qualified':False};validate_selection(result)
    return io.write_json(out/'SELECTION.json',result)
