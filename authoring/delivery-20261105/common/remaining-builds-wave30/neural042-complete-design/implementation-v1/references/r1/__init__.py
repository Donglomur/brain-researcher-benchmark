"""Independent full prospective P reference R1; no import-time numerical work."""
from .runtime import Budget, METRICS
from .engine import evaluate_person, aggregate_world

reference_identity = "R1"

__all__ = ["Budget", "METRICS", "evaluate_person", "aggregate_world", "reference_identity"]
