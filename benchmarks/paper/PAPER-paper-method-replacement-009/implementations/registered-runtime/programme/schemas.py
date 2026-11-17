"""Closed metadata domains. Validation never issues a Capture or an owner handle.

No coercion: JSON integer coordinates and Pin lengths reject floats and Booleans.
Type-sensitive canonical inverses supplement, never replace, original custody.
"""
import math
from .domain import Refusal,Pin,closed,integer,text,identity,unique,canonical,CONDITIONS,PARTITIONS
PRIMITIVES=('<f8','<f4','<i8','<i4','<u8','<u4','|u1','|b1')

def sequence(value,label):
    if type(value) is not list:raise Refusal(label+': JSON list')
    return value

def names(value,label):
    sequence(value,label)
    for item in value:text(item)
    unique(value,label)
    return value

def ids(value,label):
    sequence(value,label);parsed=[identity(x) for x in value];unique(parsed,label)
    return value

def coordinates(value,label,ordered=True):
    sequence(value,label)
    for item in value:integer(item)
    unique(value,label)
    if ordered and any(a>=b for a,b in zip(value,value[1:])):raise Refusal(label+': ordered coordinates')
    return value

def pins(value,label):
    sequence(value,label)
    for item in value:Pin.parse(item)
    return value

def real(value,label):
    if type(value) not in (int,float) or not math.isfinite(value):raise Refusal(label+': finite number')
    return value

def exact(actual,expected,label):
    # A comparison of validated documents, not a constructor for source authority.
    if canonical(actual)!=canonical(expected):raise Refusal(label+': exact typed inverse')
    return actual

def numeric_leaf(v):
    closed(v,('pin','dtype','shape','axis_ids'),'numeric leaf');Pin.parse(v['pin'])
    if type(v['dtype']) is not str or v['dtype'] not in PRIMITIVES:raise Refusal('primitive dtype')
    sequence(v['shape'],'shape')
    for extent in v['shape']:integer(extent)
    names(v['axis_ids'],'axis IDs')
    if len(v['shape'])!=len(v['axis_ids']):raise Refusal('axis rank')
    return v

def trial_support(v):
    closed(v,('schema','session','trial_ids','partition','sequence_index','sequence_segment','eligibility',
              'unit_ids','unit_regions','clock_source','mask_source','split_source','prior_source'),'support')
    if v['schema']!='trial_session_support_v1':raise Refusal('support schema')
    text(v['session']);ids(v['trial_ids'],'trial support');ids(v['unit_ids'],'unit support')
    n=len(v['trial_ids'])
    for key in ('partition','sequence_index','sequence_segment','eligibility'):
        sequence(v[key],key)
        if len(v[key])!=n:raise Refusal('support length')
    if any(type(x) is not str or x not in PARTITIONS for x in v['partition']):raise Refusal('partition domain')
    coordinates(v['sequence_index'],'original sequence index',ordered=False)
    # A segment is an original textual or unsigned-integer label, not a number
    # converted to one. Repetition is allowed; chronology stays in sequence_index.
    for segment in v['sequence_segment']:
        if type(segment) is int:integer(segment)
        elif type(segment) is str:text(segment)
        else:raise Refusal('original sequence segment label')
    if any(type(x) is not bool for x in v['eligibility']):raise Refusal('mask boolean')
    sequence(v['unit_regions'],'unit regions')
    if len(v['unit_regions'])!=len(v['unit_ids']):raise Refusal('unit region length')
    for region in v['unit_regions']:text(region)
    for key in ('clock_source','mask_source','split_source'):Pin.parse(v[key])
    if v['prior_source'] is not None:Pin.parse(v['prior_source'])
    return v

def prepared(v):
    closed(v,('schema','case_id','x','y','row_inverse','full_support','exclusions','window','method','unit_selection','common_split'),'interchange')
    if v['schema']!='trial_session_interchange_v1':raise Refusal('interchange schema')
    text(v['case_id']);trial_support(v['full_support'])
    for key in ('x','y'):numeric_leaf(v[key])
    coordinates(v['row_inverse'],'row inverse')
    n=len(v['full_support']['trial_ids'])
    if any(x>=n for x in v['row_inverse']):raise Refusal('row inverse outside original support')
    sequence(v['exclusions'],'exclusions')
    if len(v['exclusions'])!=n:raise Refusal('complete exclusions roster')
    for reasons in v['exclusions']:names(reasons,'exclusion reasons')
    closed(v['window'],('align','left','right','binsize','bins'),'window')
    text(v['window']['align'])
    for key in ('left','right','binsize'):real(v['window'][key],'window '+key)
    integer(v['window']['bins'],1)
    if v['window']['left']>=v['window']['right'] or v['window']['binsize']<=0:raise Refusal('window domain')
    text(v['method']);Pin.parse(v['unit_selection']);Pin.parse(v['common_split'])
    return v

def training(v):
    closed(v,('schema','job','condition','cases','interchange','regions','split','split_binding','configuration','source'),'training lineage')
    if v['schema']!='trial_session_training_lineage_v2':raise Refusal('training schema')
    text(v['job'])
    if type(v['condition']) is not str or v['condition'] not in CONDITIONS:raise Refusal('training condition')
    names(v['cases'],'training cases')
    if not v['cases']:raise Refusal('empty training cases')
    for key in ('interchange','regions'):
        pins(v[key],key)
        if len(v[key])!=len(v['cases']):raise Refusal('training case lineage lengths')
    for key in ('split','split_binding','configuration','source'):Pin.parse(v[key])
    return v

def prediction(v):
    closed(v,('schema','job','condition','case_id','trial_ids','output_columns','prediction','model','training',
              'selection','source','cost','prepared','unit_selection','split','split_binding'),'prediction')
    if v['schema']!='trial_session_prediction_v2':raise Refusal('prediction schema')
    text(v['job']);text(v['case_id'])
    if type(v['condition']) is not str or v['condition'] not in CONDITIONS:raise Refusal('prediction condition')
    ids(v['trial_ids'],'prediction trial IDs');coordinates(v['output_columns'],'output columns')
    numeric_leaf(v['prediction'])
    for key in ('model','training','selection','source','cost','prepared','unit_selection','split','split_binding'):Pin.parse(v[key])
    return v

def job_output(v):
    closed(v,('schema','job','condition','cases','outputs','configuration','split','source'),'job output')
    if v['schema']!='trial_session_job_output_v2':raise Refusal('job output schema')
    text(v['job'])
    if type(v['condition']) is not str or v['condition'] not in CONDITIONS:raise Refusal('job condition')
    names(v['cases'],'job cases');sequence(v['outputs'],'job outputs')
    for row in v['outputs']:
        closed(row,('case','prediction'),'job prediction');text(row['case']);Pin.parse(row['prediction'])
    for key in ('configuration','split','source'):Pin.parse(v[key])
    return v

def model_state(v):
    closed(v,('schema','parameters','normalization'),'model state')
    if v['schema']!='trial_session_model_state_v1':raise Refusal('model state schema')
    keys=[]
    for group in ('parameters','normalization'):
        sequence(v[group],group)
        for row in v[group]:
            closed(row,('name','leaf') if group=='parameters' else ('case_index','name','leaf'),'model field')
            text(row['name']);numeric_leaf(row['leaf'])
            if group=='normalization':integer(row['case_index'])
            keys.append((group,row.get('case_index'),row['name']))
    unique(keys,'model state field')
    if not v['parameters']:raise Refusal('empty model parameters')
    return v
