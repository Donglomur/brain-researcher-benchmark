"""Typed, bounded, stateless local-window inference; no fitted artifacts bundled."""
from .runtime import GraphError, validate, evaluate

__all__ = ["GraphError", "validate", "evaluate"]
