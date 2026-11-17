"""Paired resampling source; explicit failure accounting and duplicate-role isolation."""
import random
from collections import Counter, defaultdict
from .base import require, finite, digest
from .models import mean


def refitted_animal_bootstrap(animals, pipeline, replicates=10000, seed=0, synthetic=False):
    """Call a pinned full-preprocessing/inner-selection/outer-refit pipeline per draw.

    `pipeline` receives complete original biological groups with multiplicities.
    Every duplicate of a held original remains held, never in its training role.
    It must return one paired loss vector per held original. This source phase
    rejects authentic use; independent full-pipeline qualification remains open.
    """
    require(synthetic is True, 'authentic_refitting_paused')
    require(type(replicates) is int and replicates > 0 and animals, 'resampling_spec')
    groups = defaultdict(list)
    for animal, condition in animals.items(): groups[condition].append(animal)
    require(all(len(v) >= 2 for v in groups.values()), 'cluster_support')
    rng = random.Random(seed); records = []
    for draw in range(replicates):
        counts = Counter(a for values in groups.values() for a in rng.choices(values, k=len(values)))
        folds = [{'held_original': a, 'query_multiplicity': counts[a],
                  'training_multiplicities': {b: n for b, n in counts.items() if b != a}}
                 for a in sorted(counts)]
        require(all(f['held_original'] not in f['training_multiplicities'] for f in folds), 'duplicate_role_leak')
        try:
            response = pipeline(folds)
            require(set(response) == set(counts), 'refit_missing_original')
            names = set(next(iter(response.values())))
            require(names and all(set(r) == names for r in response.values()), 'unpaired_refit_models')
            losses = {m: sum(counts[a] * finite(response[a][m]) for a in counts) / sum(counts.values())
                      for m in names}
            records.append({'draw': draw, 'multiplicities': dict(counts), 'status': 'valid', 'losses': losses})
        except Exception as error:
            records.append({'draw': draw, 'multiplicities': dict(counts), 'status': 'failed',
                            'reason': type(error).__name__ + ':' + str(error)})
    failures = sum(r['status'] != 'valid' for r in records)
    # Never manufacture a successful-only confidence interval.
    return {'schema': 'refitted_animal_bootstrap_receipt_v1', 'replicates': replicates,
            'seed': seed, 'records': records, 'failures': failures, 'failure_fraction': failures / replicates,
            'full_population_interval': None, 'pipeline_qualification': False,
            'interval_status': 'required_unscorable_until_full_pipeline_and_estimability_qualified',
            'synthetic': True, 'scientific_qualification': False}
