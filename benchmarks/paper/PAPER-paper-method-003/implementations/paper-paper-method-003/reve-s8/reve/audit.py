"""Future protected scientific oracles. Never imported participant/native models.

These routines are source implementation only in this build phase. They operate
on closed passive arrays and independently selected operator targets, and never
infer historical provenance from numerical agreement.
"""
import math
import struct
from .errors import require
from .objects import canonical,digest,decode,fields,finite_rows
from .objectives import reconstruction_component,total_objective,validate_step_trace


def loss(grader,identifier,oracle):
    item=grader.controller.collector.products[identifier];d=item['product']['details']
    fields(oracle,('kind','purpose','profiles','batch_reduction','alpha','lambda','secondary_enabled','support','targets','absolute_tolerance','relative_tolerance','rank','accumulation'))
    require(d['objective_profile'] in oracle['profiles'] and d['batch_reduction']==oracle['batch_reduction'],'source intent/loss profile mismatch')
    require(all(d[k]==oracle[k] for k in ('alpha','lambda','secondary_enabled','support','rank','accumulation')),'loss coefficient/support/update binding')
    require(oracle['purpose']!='R-paper' or d['objective_profile']=='R-paper.patch_L1','paper arm cannot be penalized by an undisclosed native convention')
    values={};masks={};targets=set()
    for component in d['components']:
        grader.guard()
        reconstructed=[];gold=[];maskrows=[];example_ids=[]
        for example in component['examples']:
            grader.guard()
            target_id=example['target'];require(target_id in oracle['targets'],'unselected reconstruction target')
            selected=grader.reader.json(oracle['targets'][target_id]);fields(selected,('example','component','support','array'))
            require(selected['example']==example['id'] and selected['component']==component['name'] and selected['support']==d['support'],'independent reconstruction support')
            arr=selected['array'];fields(arr,('object','shape','dtype'))
            require(len(arr['shape'])==2 and arr['shape'][1]==200 and arr['dtype'] in ('<f4','<f8'),'target patch ABI')
            flat=finite_rows(grader.reader.read(arr['object']),arr['shape'],arr['dtype']);patches=[flat[k:k+200] for k in range(0,len(flat),200)]
            mask=example['mask'];require(all(x<len(patches) for x in mask),'mask outside actual target support')
            pred=example['prediction'];pf=finite_rows(grader.read_product(identifier,pred['object']),pred['shape'],pred['dtype'])
            reconstructed.append([pf[k:k+200] for k in range(0,len(pf),200)]);gold.append([patches[k] for k in mask]);maskrows.append(mask);example_ids.append(example['id']);targets.add(target_id)
        require(len(example_ids)==len(set(example_ids)),'duplicate example in objective batch')
        values[component['name']]=reconstruction_component(reconstructed,gold,maskrows,d['objective_profile'],d['batch_reduction'])
        masks[component['name']]={'examples':example_ids,'masks':maskrows}
    require(targets==set(oracle['targets']),'complete selected reconstruction support')
    if 'secondary' in masks:require(masks['primary']==masks['secondary'],'primary and secondary must share exact examples/masks, not merely counts')
    value=total_objective(values['primary'],values.get('secondary'),d['alpha'],d['lambda'],d['phase'],d['secondary_enabled'])
    claimed=d['backpropagated_scalar'];require(type(claimed) in (int,float) and math.isfinite(claimed),'reported scalar')
    tol=oracle['absolute_tolerance']+oracle['relative_tolerance']*abs(value['value'])
    require(oracle['absolute_tolerance']>=0 and oracle['relative_tolerance']>=0,'qualified oracle tolerance')
    return {'kind':'loss_trace','product':identifier,'objective':value,'reported_scalar':claimed,'absolute_difference':abs(claimed-value['value']),
            'scalar_agrees':abs(claimed-value['value'])<=tol,'mask_identity':d['mask_identity'],'oracle':digest(canonical(oracle)),
            'checkpoint_or_gradient_equivalence_established':False,'historical_batch_intent_established':False,'scientifically_qualified':False}


def schedule(grader,identifier,oracle):
    fields(oracle,('kind','profile','census'));d=grader.controller.collector.products[identifier]['product']['details']
    require(d['profile']==oracle['profile'],'schedule intent/native identity')
    trace=decode(grader.read_product(identifier,d['steps']))
    from .trace_contract import validate_census
    grader.guard();census=grader.reader.json(oracle['census'])
    metadata=validate_census(trace,oracle['profile'],census,d['rank_exposure'],guard=grader.guard)
    grader.guard();numeric=validate_step_trace(trace,oracle['profile'],expected=census['expected_steps'],guard=grader.guard)
    grader.guard()
    return {'kind':'schedule_trace','product':identifier,'census':metadata,'check':numeric,'scientifically_qualified':False}


def tensors(grader,identifier):
    item=grader.controller.collector.products[identifier];require(item['product']['kind']=='state','soup member must be an actual closed passive state')
    d=item['product']['details'];result={};types={'F64':'d','F32':'f','F16':'e','I64':'q','I32':'i','I16':'h','I8':'b','U8':'B','BOOL':'?'}
    for obj in d['tensor_index']:
        grader.guard()
        raw=grader.read_product(identifier,obj['object']);n=int.from_bytes(raw[:8],'little');header=decode(raw[8:8+n]);body=raw[8+n:]
        for name,row in header.items():
            if name=='__metadata__':continue
            require(name not in result,'duplicate tensor across shards')
            a,b=row['data_offsets'];payload=body[a:b]
            if row['dtype']=='BF16':values=[struct.unpack('<f',b'\x00\x00'+payload[i:i+2])[0] for i in range(0,len(payload),2)]
            else:values=[v[0] for v in struct.iter_unpack('<'+types[row['dtype']],payload)]
            require(all(math.isfinite(x) for x in values),'nonfinite actual tensor')
            result[name]={'dtype':row['dtype'],'shape':row['shape'],'values':values}
    return result


def soup(grader,identifier,oracle):
    fields(oracle,('kind','member_count','weights','buffer_policy','absolute_tolerance','relative_tolerance'))
    d=grader.controller.collector.products[identifier]['product']['details'];identities={v['identity']:k for k,v in grader.controller.collector.products.items()}
    require(len(d['members'])==oracle['member_count'] and d['weights']==oracle['weights'] and d['buffer_policy']==oracle['buffer_policy'],'selected full soup recipe')
    require(oracle['buffer_policy']=='equal_nonfloating_weighted_floating','unqualified buffer/LoRA merge policy')
    require(all(x in identities for x in [*d['members'],d['state']]),'unclosed soup state')
    members=[tensors(grader,identities[x]) for x in d['members']];actual=tensors(grader,identities[d['state']]);errors=[]
    require(all(set(x)==set(actual) for x in members),'whole tensor schema, not accuracy averaging')
    for name,out in actual.items():
        grader.guard()
        require(all(x[name]['shape']==out['shape'] and x[name]['dtype']==out['dtype'] for x in members),'soup incompatible tensors')
        floating=out['dtype'] in ('F16','BF16','F32','F64');maximum=0.0;agrees=True
        for i,value in enumerate(out['values']):
            if i%4096==0:grader.guard()
            inputs=[x[name]['values'][i] for x in members]
            expected=math.fsum(w*v for w,v in zip(d['weights'],inputs)) if floating else inputs[0]
            if not floating:require(all(v==expected for v in inputs),'nonfloating buffers differ')
            error=abs(value-expected);maximum=max(maximum,error)
            tol=oracle['absolute_tolerance']+oracle['relative_tolerance']*abs(expected) if floating else 0
            agrees=agrees and error<=tol
        errors.append({'tensor':name,'maximum_error':maximum,'agrees':agrees})
    require(errors and oracle['absolute_tolerance']>=0 and oracle['relative_tolerance']>=0,'empty/unqualified soup comparison')
    return {'kind':'soup','product':identifier,'actual_tensor_checks':errors,'arithmetic_agrees':all(x['agrees'] for x in errors),
            'selection_competence_established':False,'scientifically_qualified':False}


def passive_contract(grader,identifier,oracle):
    """Independent sealed exact support/configuration facts; no caller pass flag."""
    fields(oracle,('kind','expected_fields','independent_source'))
    require(oracle['independent_source'] and oracle['expected_fields'],'independent scientific source contract required')
    product=grader.controller.collector.products[identifier]['product'];require(product['kind']==oracle['kind'],'audit product type')
    actual=product['details'];checks={name:actual.get(name)==value for name,value in oracle['expected_fields'].items()}
    return {'kind':oracle['kind'],'product':identifier,'exact_scientific_contract_checks':checks,'agrees':all(checks.values()),
            'independent_source':oracle['independent_source'],'empirical_method_validity_established':False,'scientifically_qualified':False}
