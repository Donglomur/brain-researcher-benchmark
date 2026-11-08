"""Source-only reference library; importing this package performs no numerical work."""
from .budget import Budget
from .features import behavior_features, waveform_features, build_features
from .models import fit, predict
from .protocol import Refusal, candidate_specs, feature_order
from .selection import select
from .orchestration import iter_outer_reference, fit_full_reference
