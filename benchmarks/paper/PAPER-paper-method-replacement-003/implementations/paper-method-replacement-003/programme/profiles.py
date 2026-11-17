"""Explicit released-code versus textual-method parameters; no execution."""
from dataclasses import dataclass

class MethodGap(ValueError):
    pass

@dataclass(frozen=True)
class Profile:
    name: str
    classifier_epochs: int
    classifier_batch: int
    layer_width: int
    waveform_vae_lr: float | None
    acg_vae_lr: float | None
    waveform_vae_epochs: int | None
    acg_vae_epochs: int | None
    historical_equivalence: bool = False

def release_profile():
    # cross_validate call in run_deep_classifier.py:1291; notebook pretraining
    # parameters must be reconciled separately before this profile can train.
    return Profile('release_703a10f', 20, 64, 4, None, None, None, None)

def paper_profile():
    # Textual method reconstruction only. The unknown-layer representation and
    # convergence rule are not determined by the three-bit prose.
    return Profile('paper_methods_2025', 20, 128, 3, 1e-4, 5e-4, 60, 60)

def require_complete_recipe(profile, recipe):
    required = {'pretraining_source_identity', 'pretraining_selection',
                'waveform_vae_recipe', 'acg_vae_recipe', 'seed_schedule',
                'source_revision', 'early_stopping_rule', 'layer_unknown_rule'}
    if set(recipe) != required or any(recipe[k] is None for k in required):
        raise MethodGap('complete explicit recipe required; no historical defaults inferred')
    if recipe['source_revision'] != '703a10fb43fc7fe0076c9c331e6b52d3195b5e60':
        raise MethodGap('wrong author source revision')
    if profile.name == 'paper_methods_2025' and recipe['early_stopping_rule'] == 'unspecified':
        raise MethodGap('paper convergence stopping rule remains unspecified')
    return recipe
