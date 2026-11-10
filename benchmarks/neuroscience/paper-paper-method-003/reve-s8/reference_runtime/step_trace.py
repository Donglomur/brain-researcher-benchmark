"""Actual state/clock/exposure record construction, independent audit stays separate."""
from .catalog import identity
from .engine import state_digest

def step_row(before,model,microbatch,updates_before,updates_after,lr,rows,manifest,patches_per_epoch,samples_per_epoch):
    return {'microbatch':microbatch,'optimizer_before':updates_before,'optimizer_after':updates_after,'scheduler_before':updates_before,'scheduler_after':updates_after,'rank':0,'accumulation_index':0,'overflow_skipped':False,'lr_applied':[lr],'windows':len(rows),'patches':len(rows)*patches_per_epoch,'samples':len(rows)*samples_per_epoch,'people_support':identity(sorted({manifest['people'][i] for i in rows})) if rows else identity([]),'state_pin':state_digest(model.state_dict()),'state_before':before}

def profile(request,c,steps):
    total=len(steps)
    if request['stage']=='S08' and c['purpose']=='R-native':
        cycle=total//200;warm=int(.1*cycle);decay=int(.1*cycle)
        return {'id':'S7-native-source-cyclic-defaults-v1','source':request['source_id'],'configuration':identity(c),'environment':request['payload']['environment'],'W':warm,'P':cycle-warm-decay,'D':decay,'K':cycle,'start_lr':1e-5,'peak_lr':.001,'end_lr':1e-6,'native_formula':True,'rank_count':1,'accumulation':1,'resume':None}
    return {'id':'S7-fixed-prospective-step-clock-v1','source':request['source_id'],'configuration':identity(c),'environment':request['payload']['environment'],'W':0,'P':total,'D':0,'K':total,'start_lr':steps[0]['lr_applied'][0],'peak_lr':max(x['lr_applied'][0] for x in steps),'end_lr':steps[-1]['lr_applied'][0],'native_formula':False,'rank_count':1,'accumulation':1,'resume':None}

def rank_exposure(steps):
    first,last=steps[0],steps[-1]
    return {'ranks':[0],'ordered_keys':[[0,x['microbatch']] for x in steps],'resume':None,'start_states':{'0':{'microbatch':first['microbatch'],'optimizer':first['optimizer_before'],'scheduler':first['scheduler_before'],'state_pin':first['state_before']}},'end_states':{'0':{'microbatch':last['microbatch'],'optimizer':last['optimizer_after'],'scheduler':last['scheduler_after'],'state_pin':last['state_pin']}},'total_updates':{'0':sum(x['optimizer_after']-x['optimizer_before'] for x in steps)},'total_windows':{'0':sum(x['windows'] for x in steps)},'total_patches':{'0':sum(x['patches'] for x in steps)},'total_samples':{'0':sum(x['samples'] for x in steps)}}
