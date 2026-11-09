"""Trusted explicit-data scoring for NEURAL073; no import-time I/O."""
from .core import (Record, QualificationError, exact_weights, validate_full_scope,
                   score_panel, weighted_prior, records_digest, probability_vector)
from .parsing import parse_jsonl, bind_submission
from .selection import (select_configuration, select_family, calibrate_temperature,
                        apply_temperature, stable_softmax, TEMPERATURES, FAMILIES)
from .comparison import aggregate_repetitions, paired_comparison, person_uncertainty, compare_reference
from .workload import grid, workload, resource_algebra
