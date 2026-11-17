"""Actual component bridge and competent same-feature reference calls."""
from dataclasses import dataclass
from .components import fit_components
from .contracts import require
from .linear import fit_ridge

ARMS = ('shared_components', 'full_rank_ridge', 'rank_matched_ridge')


@dataclass(frozen=True)
class Fitted:
    arm: str
    regression: object
    spatial_template: object | None
    component_diagnostics: object | None

    def predict(self, x):
        import numpy as np
        prediction = self.regression.predict(x)
        if self.spatial_template is not None:
            prediction = prediction @ self.spatial_template.T
        require(np.isfinite(prediction).all(), 'Nonfinite model prediction')
        return prediction


def fit(arm, responses, features, config):
    import numpy as np
    require(arm in ARMS, 'Unknown P1 arm')
    config.validate()
    y = np.asarray(responses, dtype=float)
    require(y.ndim == 3 and y.shape[1] == features.shape[0], 'Training features and responses are not aligned')
    require(np.isfinite(y).all(), 'Nonfinite training response')
    if arm == 'shared_components':
        components = fit_components(y, config)
        require(components.converged, 'Component fit did not meet its predeclared convergence rule')
        regression = fit_ridge(features, components.profiles, config.ridge_penalty)
        diagnostics = {'rank': config.rank, 'iterations': components.iterations,
                       'objective': components.objective, 'converged': components.converged,
                       'aggregation': 'equal_training_person_mean'}
        return Fitted(arm, regression, components.spatial_template, diagnostics)
    rank = None if arm == 'full_rank_ridge' else config.rank
    regression = fit_ridge(features, y.mean(axis=0), config.ridge_penalty, rank=rank)
    return Fitted(arm, regression, None, None)
