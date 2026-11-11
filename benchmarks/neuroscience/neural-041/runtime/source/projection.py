"""Exact candidate views; private original labels and clocks never enter mounts."""
from pathlib import Path
import os
from core import need,encoded,publish,pin,copy_sealed,fresh
from schema import cohort,folds,view_row,validate_view

def build(private,epoch_root,output,budget,epoch_cap,protocol):
    rows=private['rows'];lineage=cohort(rows);schedule=folds(rows);root=fresh(output,budget);views=[]
    pool=fresh(root/'epochs',budget)
    # Private preparation writes in source order. Reusing those inodes would
    # disclose that order through filesystem metadata. Make one public pool in
    # keyed-ID order and normalize readable times; do not expose original inodes.
    for row in sorted(rows,key=lambda r:r['identity']['trial']):
        if not row['eligibility']:continue
        path=row['epoch']['path'];copy_sealed(Path(epoch_root)/path,row['epoch']['pin'],pool/path,epoch_cap,budget)
        os.utime(pool/path,ns=(0,0),follow_symlinks=False)
        budget.tick()
    for fold in schedule:
        held=fold['held'];folder=fresh(root/held,budget)
        training=[];query=[];ids=[]
        for row in sorted(rows,key=lambda r:r['identity']['trial']):
            if not row['eligibility']:continue
            patient=row['identity']['patient'];is_train=patient in fold['training'];is_query=patient==held
            need(is_train != is_query,'complete outer patient partition')
            target=training if is_train else query;target.append(view_row(row,training=is_train))
            path=row['epoch']['path'];ids.append(row['identity']['trial'])
            # Transport mounts only the sanitized shared pool, never original
            # prepared inodes. The scientific corpus is copied once, not36 times.
        view=validate_view({'schema':'n041_view_v1','training':training,'query':query,'regions':private['regions'],'protocol':protocol})
        vp=publish(folder/'VIEW.json',encoded(view),budget,readonly=True)
        # Targets stay in caller-owned private memory. The public view contains
        # neither session grouping nor order; whole-patient training groups are
        # present solely for nested tuning and never used as model features.
        views.append({'held':held,'path':str(folder/'VIEW.json'),'pin':vp,'epoch_root':str(pool),'query_ids':[r['id'] for r in query],
            'training_ids':[r['id'] for r in training],'inner_folds':fold['inner']})
    need(len(views)==len(lineage['patients']),'all patient folds, including those failing eligibility qualification')
    return views
