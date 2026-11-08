"""Full structural-shape admission with the actual shared reference graph planner."""
from core import DAYS,VARIANTS,need,identity
from graph.compile_reference import reference_capacity


def full_shape_plan(manifest,policy,preparation_policy,reservation,metadata_deadline):
    need(manifest.get('status')=='structural_export_with_bound_identity_document','Independent original identity plus complete structural census')
    rows=manifest['imaging_sessions'];need(len(rows)==88,'All variant-session records')
    keys=set();plans=[];capacity={};maximum_training=0
    for row in rows:
        key=(row['variant'],row['animal_ordinal'],row['day']);need(key not in keys,'Unique selected session');keys.add(key)
        shape=row['arrays']['spks']['shape'];need(len(shape)==3 and shape[1:]==[140,402],'Full original trial/time geometry')
        rois=shape[0];need(type(rois) is int and rois>0,'Positive full source ROI upper')
        n=119*5;channels=rois+2;training_bytes=n*(channels*15*9+5*8+2*8)
        need(training_bytes+65545<=policy['max_training_array_bytes'] and training_bytes+65545<=preparation_policy['max_array_bytes'],'Complete training tensor capacity; no ROI/window cropping')
        need(100*channels*15*8+65545<=policy['max_query_array_bytes'],'Full100record local query payload capacity; no missing cohort/window trimming')
        capacity_keys=[]
        for c,clock in ((rois,False),(2,True),(rois+2,True)):
            for family in ('linear_mean','linear_fullwindow','gaussian_fullwindow'):
                parameters={'schema':'h_svm_parameters_v1','family':family,'channels':c,'clock':clock}
                cache_key=identity({'parameters':parameters,'support_rows_upper':n})
                # Reuse an identical deterministic metadata proof, never an
                # actual fitted model, source-array check or scientific result.
                if cache_key not in capacity:
                    value=reference_capacity(parameters,n if family=='gaussian_fullwindow' else None,{**policy['graph_limits'],'deadline':metadata_deadline})
                    plan=value['plan'];constant_arrays=value['array_shapes']
                    max_payload=0
                    for d in constant_arrays.values():
                        count=1
                        for axis in d['shape']:count*=axis
                        max_payload=max(max_payload,count*(1 if d['dtype']=='bool' else 8))
                    # NPY1's header is at most65535 bytes plus10 framing bytes.
                    # Reference MODEL framing/provenance has a separately
                    # enforced64KiB allowance beyond its exact graph JSON.
                    model_upper=plan['constant_bytes']+len(constant_arrays)*65545+plan['graph_bytes']+65536
                    need(max_payload+65545<=policy['max_array_bytes'] and model_upper<=policy['max_model_bytes'],'Complete typed nonlinear/linear reference publication capacity')
                    capacity[cache_key]={'parameters':parameters,'support_rows_upper':n,'model_encoding_upper':model_upper,'array_payload_upper':max_payload,'constant_arrays':constant_arrays,'inference_plan':{k:v for k,v in plan.items() if k not in ('nodes','uses')},'source':'Shared graph.compile_reference._assemble plus actual graph.runtime.validate; no numeric model allocated'}
                capacity_keys.append(cache_key)
        session_bytes=sum(x.get('bytes',0) for x in row['arrays'].values() if type(x) is dict)
        need(session_bytes<=preparation_policy['session_input_bytes'],'Complete source session byte admission')
        maximum_training=max(maximum_training,training_bytes)
        plans.append({'variant':key[0],'animal_ordinal':key[1],'day':key[2],'source_ROIs':rois,'combined_channel_upper':channels,'training_rows_upper':n,'training_payload_upper':training_bytes,'capacity_keys':capacity_keys})
    expected={(v,a,d) for v in VARIANTS for a in range(11) for d in DAYS};need(keys==expected,'Every selected animal/day/variant; no substitute cohort')
    need(reservation['model_count']==9240 and reservation['all_model_bytes']>=9240*policy['max_model_bytes'],'Full sealed-model reservation before any model training')
    return {'schema':'h_full_shape_admission_v2','sessions':plans,'capacity_by_exact_parameter_shape':capacity,'model_count':9240,'maximum_training_payload_upper':maximum_training,'not_a_runtime_feasibility_certificate':True,'fitting_export_compilation_and_process_RSS':'Separate enforced envelopes/qualification; inference-array plan does not certify MATLAB or host peak memory'}
