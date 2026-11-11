"""Exact captured metadata conversion identity; no aggregate-count substitution."""
from pathlib import Path
import delivery_io as io
PIN={'bytes':5834685,'sha256':'4bcc3017b4a28d16f39bd8962961472f1fa23d82097bcd19f3e45900b8792f74'}
def load(root,cohort_path=None):return io.json_file(Path(root)/'COHORT.json' if cohort_path is None else Path(cohort_path),16000000,PIN)
