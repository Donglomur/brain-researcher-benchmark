"""Source-grounded metadata compilation; scientific runtime remains separate."""
from .catalog import compile_catalog, extraction_selection, source_order
__all__ = ['compile_catalog', 'extraction_selection', 'source_order']
