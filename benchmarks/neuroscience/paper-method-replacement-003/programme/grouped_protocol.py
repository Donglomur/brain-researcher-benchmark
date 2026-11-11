"""Target-blind biological-group partitions and exact TRAIN-only job supports.

No authentic split is instantiated here. Operator group identities must already
resolve animal aliases across sessions/laboratories; this contract is not an
issuer of biological truth or hidden-test authority.
"""
from dataclasses import dataclass
from .cohort import CLASSES,SupportError

@dataclass(frozen=True)
class GroupPlan:
    unit_order: tuple
    group_by_unit: dict
    outer_by_group: dict
    inner_by_outer: dict
    provenance: str

    def validate(self):
        if not self.provenance or not self.unit_order or len(set(self.unit_order))!=len(self.unit_order):
            raise SupportError('complete unique ordered biological support required')
        if set(self.group_by_unit)!=set(self.unit_order):raise SupportError('group binding must cover every unit exactly')
        groups=set(self.group_by_unit.values())
        if any(type(g) is not str or not g for g in groups):raise SupportError('canonical biological group IDs required')
        if set(self.outer_by_group)!=groups:raise SupportError('outer assignment does not cover full groups')
        animals={}
        for unit in self.unit_order:
            unit.validate();animal=(unit.species,unit.lab,unit.animal)
            previous=animals.setdefault(animal,self.group_by_unit[unit])
            if previous!=self.group_by_unit[unit]:raise SupportError('sessions of an animal cross biological groups')
        outer=tuple(dict.fromkeys(self.outer_by_group.values()))
        if len(outer)<2 or any(type(f) is not str or not f for f in outer):
            raise SupportError('at least two explicit outer folds required')
        if set(self.inner_by_outer)!=set(outer):raise SupportError('inner plans missing an outer fold')
        for fold in outer:
            training={g for g in groups if self.outer_by_group[g]!=fold}
            inner=self.inner_by_outer[fold]
            if set(inner)!=training or len(set(inner.values()))<2:
                raise SupportError('each inner plan must cover all and only outer-TRAIN groups')
            if any(type(f) is not str or not f for f in inner.values()):raise SupportError('invalid inner-fold identity')
        return self

    def outer_folds(self):
        self.validate();return tuple(dict.fromkeys(self.outer_by_group.values()))

@dataclass(frozen=True)
class FitJob:
    identity: str
    family: str
    outer_fold: str
    inner_fold: str | None
    candidate: int
    training_units: tuple
    evaluation_units: tuple
    stage: str

def training_labels(units,labels):
    if set(labels)!=set(units):raise SupportError('held or missing label in exact training scope')
    if any(labels[k] not in CLASSES for k in units):raise SupportError('label outside five-class ontology')
    return tuple(labels[k] for k in units)

def nested_jobs(plan,grid_by_family):
    """Complete per-family grids; no data-dependent fold or candidate removal."""
    plan.validate()
    if set(grid_by_family)!= {'logistic_regression','random_forest','gaussian_process'}:
        raise SupportError('all three prospective model families required')
    jobs=[]
    for family,grid in grid_by_family.items():
        if not grid or any(type(p) is not dict for p in grid):raise SupportError('precommitted finite parameter grid required')
        for outer in plan.outer_folds():
            inner=plan.inner_by_outer[outer]
            for candidate,_ in enumerate(grid):
                for inner_fold in dict.fromkeys(inner.values()):
                    train=tuple(k for k in plan.unit_order if plan.group_by_unit[k] in inner
                                and inner[plan.group_by_unit[k]]!=inner_fold)
                    validation=tuple(k for k in plan.unit_order if plan.group_by_unit[k] in inner
                                     and inner[plan.group_by_unit[k]]==inner_fold)
                    if not train or not validation:raise SupportError('empty inner training/validation support')
                    jobs.append(FitJob(f'{family}/{outer}/{candidate}/{inner_fold}',family,outer,
                                       inner_fold,candidate,train,validation,'inner_tuning'))
    return tuple(jobs)

def final_job(plan,family,outer,candidate):
    plan.validate()
    if outer not in plan.outer_folds():raise SupportError('unknown outer fold')
    train=tuple(k for k in plan.unit_order if plan.outer_by_group[plan.group_by_unit[k]]!=outer)
    query=tuple(k for k in plan.unit_order if plan.outer_by_group[plan.group_by_unit[k]]==outer)
    return FitJob(f'{family}/{outer}/selected',family,outer,None,candidate,train,query,'outer_query')
