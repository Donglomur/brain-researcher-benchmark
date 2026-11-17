"""Concrete parameter-bound VAE reconstruction, never an executed notebook.

Uses GPL-3.0 NeuroPyxels model definitions at 703a10f. Integration modified
2026-11-11. Notebook training identity is unresolved after retained transport
failures: this module is a paper-method reconstruction, not historical parity.
"""
from c4_distribution.import_guard import require_bound_source as _c4_require_source
from dataclasses import dataclass
from .profiles import MethodGap
from .cohort import Population, SupportError

@dataclass(frozen=True)
class VAERecipe:
    modality: str
    epochs: int
    learning_rate: float
    batch_size: int
    beta: float
    latent_samples: int
    seed: int
    kl_schedule: str
    initialization: str
    optimizer: str
    scheduler_period: int
    recipe_provenance: str

    def validate(self):
        if self.modality not in ('waveform', 'acg'):
            raise MethodGap('unsupported pretraining modality')
        paper = (60, 1e-4, 128) if self.modality == 'waveform' else (60, 5e-4, 32)
        if (self.epochs, self.learning_rate, self.batch_size) != paper or self.beta != 5:
            raise MethodGap('not the selected paper-method pretraining recipe')
        if self.optimizer != 'Adam' or self.kl_schedule != 'released_generate_kl_weight':
            raise MethodGap('optimizer/annealing source choice must be explicit')
        if self.initialization != 'released_model_constructor' or not self.recipe_provenance:
            raise MethodGap('initializer/recipe provenance missing')
        if type(self.seed) is not int or self.latent_samples < 1 or self.scheduler_period < 1:
            raise MethodGap('explicit seed/Monte-Carlo/scheduler inputs required')

@dataclass
class Pretrained:
    modality: str
    encoder: object
    decoder: object
    training_units: tuple
    recipe: VAERecipe
    history: tuple
    initial_rng: object
    final_rng: object
    source_profile: str = 'paper_methods_2025_parameter_bound'

def train_vae(cohort, prepared, recipe, *, device):
    """Train every specified epoch on the complete independent unlabelled set."""
    _c4_require_source()
    recipe.validate()
    expected = tuple(m.key for m in cohort.eligible(Population.MOUSE_UNLABELLED_PRETRAIN))
    if tuple(u.key for u in prepared) != expected:
        raise SupportError('pretraining input/order does not match full original support')
    cohort.classification_support(historical_counts=True)
    import numpy as np
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    _c4_require_source()
    from npyx.ml import set_seed
    _c4_require_source()
    from npyx.c4.dl_utils import define_forward_vae, ACG3DVAE, generate_kl_weight
    _c4_require_source()
    from npyx.c4.run_deep_classifier import WVF_ENCODER_ARGS_SINGLE
    set_seed(recipe.seed, seed_torch=True)
    initial_rng = {'numpy':np.random.get_state(), 'torch':torch.get_rng_state()}
    if recipe.modality == 'waveform':
        array = np.stack([u.waveform for u in prepared]).reshape(-1, 1, 90)
        encoder, decoder = define_forward_vae(90, init_weights=True,
                                              params=dict(WVF_ENCODER_ARGS_SINGLE), device=device)
    else:
        array = np.stack([u.acg_log_full[:, 100:] for u in prepared]).reshape(-1, 1, 10, 101)
        model = ACG3DVAE(10, 10, 101, pool='avg')
        encoder, decoder = model.encoder.to(device), model.decoder.to(device)
    loader = DataLoader(TensorDataset(torch.as_tensor(array, dtype=torch.float32)),
                        batch_size=recipe.batch_size, shuffle=True, num_workers=0)
    optimizer = torch.optim.Adam(list(encoder.parameters()) + list(decoder.parameters()),
                                 lr=recipe.learning_rate)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=recipe.scheduler_period, T_mult=1)
    weights = generate_kl_weight(recipe.epochs, recipe.beta)
    history = []
    for epoch in range(recipe.epochs):
        encoder.train(); decoder.train(); records = []
        for batch_index, (x,) in enumerate(loader):
            x = x.to(device); optimizer.zero_grad(); loss = 0
            for _ in range(recipe.latent_samples):
                q = encoder(x); z = q.rsample(); reconstructed = decoder(z)
                if reconstructed.shape != x.shape:
                    raise SupportError('VAE reconstruction shape mismatch')
                prior = torch.distributions.Normal(torch.zeros_like(q.loc), torch.ones_like(q.scale))
                mse = (reconstructed - x).square().flatten(1).sum(1)
                kl = torch.distributions.kl_divergence(q, prior).sum(1)
                loss = loss + (mse + weights[epoch] * (len(x)/len(prepared)) * kl).mean()
            loss = loss / recipe.latent_samples
            if not torch.isfinite(loss):raise SupportError('nonfinite pretraining objective')
            loss.backward(); optimizer.step()
            records.append({'batch':batch_index, 'rows':len(x), 'loss':float(loss.detach().cpu()),
                            'optimizer_steps':1, 'latent_draws':recipe.latent_samples})
        scheduler.step()
        history.append({'epoch':epoch, 'batches':records, 'rows':sum(x['rows'] for x in records),
                        'beta':float(weights[epoch]), 'learning_rate':optimizer.param_groups[0]['lr']})
    encoder.eval();decoder.eval()
    return Pretrained(recipe.modality, encoder, decoder, expected, recipe, tuple(history),
                      initial_rng, {'numpy':np.random.get_state(), 'torch':torch.get_rng_state()})
