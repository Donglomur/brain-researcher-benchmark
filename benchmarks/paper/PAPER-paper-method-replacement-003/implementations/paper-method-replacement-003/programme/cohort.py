"""Typed biological identities and complete support admission.

This is a source contract, not an issuer of data, targets, or deployment authority.
Authentic bindings must be supplied by the evaluator's independently qualified
source preparation. No actual identities are embedded here.
"""
from dataclasses import dataclass
from enum import Enum

class SupportError(ValueError):
    pass

class Population(str, Enum):
    MOUSE_GROUND_TRUTH = 'mouse_ground_truth'
    MOUSE_UNLABELLED_PRETRAIN = 'mouse_unlabelled_pretrain'
    MOUSE_EXPERT = 'mouse_expert_medina'
    MONKEY_EXPERT = 'monkey_expert_lisberger'
    ALL_PHOTOACTIVATED = 'mouse_all_photoactivated'
    IN_VITRO = 'in_vitro'
    BEHAVIOUR_HULL = 'behaviour_hull'
    BEHAVIOUR_MEDINA = 'behaviour_medina'
    BEHAVIOUR_HAUSSER = 'behaviour_hausser'
    BEHAVIOUR_LISBERGER = 'behaviour_lisberger'

CLASSES = ('GoC', 'MLI', 'MFB', 'PkC_ss', 'PkC_cs')
SOURCE_ROLES = ('hull_unlabelled', 'lisberger', 'medina_unlabelled', 'hausser', 'hull_labelled')

@dataclass(frozen=True, order=True)
class UnitKey:
    species: str
    lab: str
    animal: str
    session: str
    recording: str
    unit: str

    def validate(self):
        if self.species not in ('mouse', 'macaque'):
            raise SupportError('unresolved species')
        if any(not isinstance(x, str) or not x.strip() for x in
               (self.lab, self.animal, self.session, self.recording, self.unit)):
            raise SupportError('complete original biological identity required')

@dataclass(frozen=True)
class Member:
    key: UnitKey
    source_role: str
    h5_group: str
    population: Population
    disposition: str
    reason: str
    original_order: int
    label_provenance: str

    def validate(self):
        self.key.validate()
        if self.source_role not in SOURCE_ROLES and self.population not in (
                Population.IN_VITRO, Population.ALL_PHOTOACTIVATED):
            raise SupportError('source role is not in the five-file release')
        if not self.h5_group or '/' in self.h5_group or self.h5_group in ('.', '..'):
            raise SupportError('exact immediate HDF5 unit group required')
        if self.disposition not in ('eligible', 'excluded', 'unresolved') or not self.reason:
            raise SupportError('every unit requires a retained disposition')
        if type(self.original_order) is not int or self.original_order < 0:
            raise SupportError('original row order required')
        if not self.label_provenance:
            raise SupportError('ground-truth/expert/unlabelled distinction required')

@dataclass(frozen=True)
class Cohort:
    members: tuple[Member, ...]
    source_roles: tuple[str, ...]
    source_complete: bool
    source_census_identity: str

    def validate(self):
        if set(self.source_roles) != set(SOURCE_ROLES) or len(self.source_roles) != 5:
            raise SupportError('all five original release sources must have dispositions')
        if not self.source_complete or not self.source_census_identity:
            raise SupportError('complete authentic source census not established')
        seen = set(); orders = set()
        for m in self.members:
            m.validate()
            token = (m.population, m.key)
            if token in seen:
                raise SupportError('duplicate biological unit within population')
            seen.add(token)
            order = (m.population, m.original_order)
            if order in orders:
                raise SupportError('duplicate original order within population')
            orders.add(order)
        if any(m.disposition == 'unresolved' for m in self.members):
            raise SupportError('unresolved source membership cannot silently disappear')
        return self

    def eligible(self, population):
        self.validate()
        return tuple(sorted((m for m in self.members if m.population == population
                            and m.disposition == 'eligible'), key=lambda m: m.original_order))

    def classification_support(self, *, historical_counts):
        gt = self.eligible(Population.MOUSE_GROUND_TRUTH)
        pre = self.eligible(Population.MOUSE_UNLABELLED_PRETRAIN)
        if not gt or not pre:
            raise SupportError('both labelled and independent unlabelled populations required')
        if {m.key for m in gt} & {m.key for m in pre}:
            raise SupportError('pretraining includes a ground-truth unit')
        if historical_counts and (len(gt) != 202 or len(pre) != 3090):
            raise SupportError('published 202/3090 support not reproduced; retain discrepancy')
        for pop in (Population.MOUSE_EXPERT, Population.MONKEY_EXPERT):
            target = self.eligible(pop)
            if not target or {m.key for m in target} & ({m.key for m in gt} | {m.key for m in pre}):
                raise SupportError('external transfer support missing or overlaps training')
        return gt, pre

@dataclass(frozen=True)
class Fold:
    repeat: int
    held: UnitKey
    training: tuple[UnitKey, ...]

def leave_one_unit_out(cohort, *, historical_counts=True, population=Population.MOUSE_GROUND_TRUTH):
    """All ten repeats and every unit; this is not animal-held-out inference."""
    gt, pre = cohort.classification_support(historical_counts=historical_counts)
    if population == Population.ALL_PHOTOACTIVATED:
        gt = cohort.eligible(population)
        if not gt or {m.key for m in gt} & {m.key for m in pre}:
            raise SupportError('complete independent all-photoactivated ablation support missing')
    elif population != Population.MOUSE_GROUND_TRUTH:
        raise SupportError('unselected LOO population')
    keys = tuple(m.key for m in gt)
    return tuple(Fold(r, held, tuple(k for k in keys if k != held))
                 for r in range(10) for held in keys)

def validate_transfer_ensemble(folds, trained):
    """Reject missing/duplicated/subsampled models before external prediction."""
    expected = tuple((f.repeat, f.held) for f in folds)
    actual = tuple((m.repeat, m.held) for m in trained)
    if actual != expected:
        raise SupportError('transfer requires the complete ordered LOO ensemble')
    for fold, model in zip(folds, trained):
        if tuple(model.training) != fold.training:
            raise SupportError('model training identity does not match original fold')
