"""Two explicitly selected source overlays; original helper bodies stay immutable."""
from core import need

ALLOWED = {'preparation/prepare.py':'owner-helper-repairs-v1/preparation_prepare.py',
           'references/r2/budget.py':'owner-helper-repairs-v1/r2_budget.py'}


def source(manifest, logical):
    overrides = manifest.get('overrides',{})
    need(overrides == ALLOWED, 'exact two root-selected helper source overlays')
    actual = overrides.get(logical,logical)
    need(logical in manifest['files'] and actual in manifest['files'], 'original and effective source both captured')
    return actual,manifest['files'][actual]
