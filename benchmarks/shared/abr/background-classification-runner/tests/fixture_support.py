"""Wholly invented metadata; no released identities or canonical label rule.

These receipts deliberately represent fake maintainer evidence for interface
controls. They are not deployable preparation artifacts or authentic admission.
"""
import hashlib
import split
import common as c
import prepared_manifest as pm

def invented_manifest():
    animals=[]
    for label,count in ((0,54),(1,50)):
        group=[{'animal_id':'animal_'+hashlib.sha256(('synthetic-only/%d/%d'%(label,i)).encode()).hexdigest(),
                'label':label}for i in range(count)]
        group.sort(key=lambda a:hashlib.sha256(('fixture-outer/'+a['animal_id']).encode()).hexdigest())
        for i,a in enumerate(group):a['outer_fold']=i%5
        animals.extend(group)
    animals.sort(key=lambda a:a['animal_id']);folds=[]
    for outer in range(5):
        train=[a for a in animals if a['outer_fold']!=outer];test=[a for a in animals if a['outer_fold']==outer]
        assigned={}
        for label in (0,1):
            group=sorted((a for a in train if a['label']==label),key=lambda a:hashlib.sha256(('fixture-inner/%d/'%outer+a['animal_id']).encode()).hexdigest())
            for i,a in enumerate(group):assigned[a['animal_id']]=i%4
        inner=[{'inner_fold':i,'train_animal_ids':[a['animal_id']for a in train if assigned[a['animal_id']]!=i],
                'validation_animal_ids':[a['animal_id']for a in train if assigned[a['animal_id']]==i]}for i in range(4)]
        folds.append({'outer_fold':outer,'train_animal_ids':[a['animal_id']for a in train],
                      'test_animal_ids':[a['animal_id']for a in test],'inner_folds':inner})
    return split.validate_manifest({'schema':split.SCHEMA,'outer_fold_count':5,'inner_fold_count':4,
        'animal_count':104,'class_counts':{'0':54,'1':50},'animals':animals,'folds':folds,
        'state_policy':dict(split.STATE_POLICY)})

def invented_receipt(manifest_pin,completion_pin):
    value={'schema':pm.SCHEMA,'projection':pm.PROJECTION,'counts':dict(pm.COUNTS),
           'opaque_manifest':manifest_pin,'opaque_completion':completion_pin,
           'original_manifest':c.pin(b'invented original manifest'),
           'original_completion':c.pin(b'invented original completion'),
           'private_validator':c.pin(b'invented-only maintainer validation')}
    value.update({k:True for k in pm.FLAGS})
    return value
