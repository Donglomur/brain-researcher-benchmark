"""Actual raw-operand fold projection, shared by paper/data and paper/code arms.

Genuine read-only mount, actor sandbox and source/target issuers are outside this
source construction. This function writes a finite view; it cannot grant access.
"""
from .cohort import CLASSES,SupportError

def emit_fold_view(fold,prepared,training_targets,outputs,*,arm,paper_capture,code_capture):
    if arm not in ('paper_data','paper_data_code'):raise SupportError('unknown paired exposure arm')
    if not paper_capture:raise SupportError('same original paper selection required')
    if arm=='paper_data' and code_capture is not None:raise SupportError('code leaked into paper/data arm')
    if arm=='paper_data_code' and not code_capture:raise SupportError('complete frozen code exposure required')
    wanted=fold.training+(fold.held,)
    if set(prepared)!=set(wanted) or set(training_targets)!=set(fold.training):
        raise SupportError('fold view must contain all and only its raw units/training labels')
    rows=[]
    for i,key in enumerate(wanted):
        u=prepared[key]
        if u.key!=key:raise SupportError('raw producer identity mismatch')
        role='train' if key in fold.training else 'query'
        token=f'unit-{i:06d}'
        row={'token':token,'role':role,'sampling_rate':u.source_spike_sampling_rate,'layer':u.layer}
        # Full source clock and every QC-retained spike are preserved. No ACG
        # inversion or invented multi-channel waveform replaces raw operands.
        row['spikes']=outputs.array(token+'-spikes.npy',u.source_spikes).__dict__
        row['waveform']=outputs.array(token+'-waveform.npy',u.waveform).__dict__
        row['multi_template']=outputs.array(token+'-template.npy',u.multichannel_template).__dict__
        row['acg']=outputs.array(token+'-acg.npy',u.acg_log_full).__dict__
        if role=='train':
            label=training_targets[key]
            if label not in CLASSES:raise SupportError('training target outside fixed five-class ontology')
            row['label']=label
        rows.append(row)
    index=outputs.json('fold-view.json',{'repeat':fold.repeat,'class_order':CLASSES,'units':rows,
        'arm':arm,'paper_capture':paper_capture,'code_capture':code_capture,
        'scope':'published-unit LOO reproduction; no new hidden holdout claim'})
    return index

def training_targets_only(fold,protected_training_targets):
    """The caller cannot smuggle a held target through a surplus mapping row."""
    if set(protected_training_targets)!=set(fold.training):
        raise SupportError('held or extraneous label in training exposure')
    return dict(protected_training_targets)
