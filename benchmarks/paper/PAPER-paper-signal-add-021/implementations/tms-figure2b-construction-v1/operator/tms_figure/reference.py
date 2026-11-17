"""Concrete future reference path from authenticated complete derivative fields."""
from __future__ import annotations
import math
from .contract import CONDITIONS, WINDOWS, FREQUENCY, metadata
from .derivative import Derivative
from . import reduction
from .outputs import publish_fields

def compute_fields(reader, identity):
    """Internal scientific calculation; public grading always constructs Derivative."""
    metadata(identity)
    fields={}
    for cond in CONDITIONS:
        means=[];counts=[];masks=[]
        for c in range(62):
            for f in range(53):
                for t in range(200):
                    values=reader.stored_position_values(cond,c,f,t)
                    mean,n=reduction.mean_db(values)
                    means.append(mean);counts.append(n)
                    masks.append(sum(1<<i for i,v in enumerate(values) if not math.isnan(v)))
        stem='mean.'+cond
        fields[stem+'.value']=means
        fields[stem+'.undefined']=[int(math.isnan(x)) for x in means]
        fields[stem+'.positions']=masks
        fields[stem+'.contributors']=counts
    for cond in ['NT','T']:
        values=[reduction.normalized(x,y) for x,y in zip(fields['mean.'+cond+'.pin.all.value'],fields['mean.'+cond+'.pout.all.value'])]
        fields['normalized.'+cond+'.value']=values
        fields['normalized.'+cond+'.undefined']=[int(math.isnan(x)) for x in values]
        for win,bounds in WINDOWS.items():
            reduced=reduction.window_reduce(values,channels=62,frequency_axis=identity['frequency'],time_axis=identity['time'],frequency_bounds=FREQUENCY,time_bounds=bounds)
            stem='window.'+cond+'.'+win
            fields[stem+'.value']=reduced['topography']
            fields[stem+'.undefined']=[int(math.isnan(x)) for x in reduced['topography']]
            fields[stem+'.time_contributors']=[x for row in reduced['time_contributors'] for x in row]
            fields[stem+'.frequency_contributors']=reduced['frequency_contributors']
    return fields

def reference_to_directory(derivative_path, identity, output, budget, *, metadata_read_reservation):
    with Derivative(derivative_path,identity,budget,metadata_read_reservation=metadata_read_reservation) as reader:
        fields=compute_fields(reader,identity)
    return publish_fields(output,identity,fields,budget,producer='independent-binary64-source-reduction-v1')
