"""Concrete full classification schedule; no generic scientific callback slots.

Internal scientific source only. The missing genuine source/native/target and
capacity owners prevent a public runnable claim. No dictionary issues authority.
"""
from c4_distribution.import_guard import require_bound_source as _c4_require_source
from .cohort import Population,SupportError
from .profiles import release_profile
from .programme import ScientificDriver

CLASSIFICATION_POPULATIONS=(Population.MOUSE_GROUND_TRUTH,Population.MOUSE_UNLABELLED_PRETRAIN,
    Population.ALL_PHOTOACTIVATED,Population.MOUSE_EXPERT,Population.MONKEY_EXPERT,
    Population.BEHAVIOUR_HULL,Population.BEHAVIOUR_MEDINA,
    Population.BEHAVIOUR_HAUSSER,Population.BEHAVIOUR_LISBERGER)

def internal_complete_classification(cohort,source_paths,outputs,source_identity,*,
        preparation_recipes,vae_recipes,classifier_recipes,training_targets,device):
    """Full primary, no-layer and all-photoactivated fits plus every transfer.

    Recipe values and biological annotations are unqualified scientific inputs.
    This method does not render the missing Fig2/3/7 or supplementary producers
    complete; their explicit dispositions remain in the returned driver.
    """
    _c4_require_source()
    if set(preparation_recipes)!=set(CLASSIFICATION_POPULATIONS):
        raise SupportError('complete population-specific preprocessing recipes required')
    if set(vae_recipes)!= {'waveform','acg'} or set(classifier_recipes)!= {'primary','no_layer','all_photoactivated'}:
        raise SupportError('complete pretraining and three classifier schedules required')
    if set(training_targets)!= {Population.MOUSE_GROUND_TRUTH,Population.ALL_PHOTOACTIVATED}:
        raise SupportError('training label scope must exclude transfer and behavior targets')
    d=ScientificDriver(cohort,source_paths,outputs,source_identity)
    for p in CLASSIFICATION_POPULATIONS:d.prepare_population(p,**preparation_recipes[p])
    for modality in ('waveform','acg'):d.pretrain(vae_recipes[modality],device=device)
    for variant,population,use_layer in (
        ('primary',Population.MOUSE_GROUND_TRUTH,True),
        ('no_layer',Population.MOUSE_GROUND_TRUTH,False),
        ('all_photoactivated',Population.ALL_PHOTOACTIVATED,True)):
        recipe=classifier_recipes[variant]
        if set(recipe)!= {'augment_waveform','augment_spikes','freeze_heads','source_seed'}:
            raise SupportError('explicit complete classifier recipe required')
        d.classify(variant,training_targets[population],profile=release_profile(),use_layer=use_layer,
                   device=device,population=population,**recipe)
    for p in CLASSIFICATION_POPULATIONS[3:]:d.transfer('primary',p,use_layer=True)
    return d

def internal_target_blind_reference(cohort,source_paths,outputs,source_identity,*,population,
        qc_bindings,feature_recipe,group_plan,reference_recipe,training_targets_by_outer,
        external_quality_policy):
    """Complete separate prospective route; no query targets in the signature.

    All same37 original definitions, three model families and complete nested
    grids are called. A genuine independent QC/group/source/native owner is
    still required. The original literal/deep/transfer routes above are retained.
    """
    _c4_require_source()
    d=ScientificDriver(cohort,source_paths,outputs,source_identity)
    d.target_blind_features(population,qc_bindings,feature_recipe,
                           external_quality_policy=external_quality_policy)
    d.grouped_target_blind_reference(population,group_plan,reference_recipe,training_targets_by_outer)
    return d
