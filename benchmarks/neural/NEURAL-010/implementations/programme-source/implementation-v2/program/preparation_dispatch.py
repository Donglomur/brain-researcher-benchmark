"""Prepared-data dispatch under the caller's unchanged whole-study budget.

The explicit compatibility selection is an independently bound part of the
original phase request. Metadata admission replays only label-free journal
frames and checks all529 materialized view extents before the first native job.
Scientific labels remain opaque until the original isolated worker/release gate.
"""
from pathlib import Path
import common as c
import preparation_compatibility as compat


class BudgetIO(compat.FileIO):
    def __init__(self, roots, budget):
        # Do not reset the run clock or create a second independent allowance.
        self.budget = budget
        self.roots = [compat.absolute(str(p)) for p in roots]
        self.limit = min(256 * 1048576, budget.limits['read_bytes'] - budget.used['read_bytes'])
        compat.integer(self.limit, 1)
        self.used = 0
        self.accesses = []

    def charge(self, n):
        compat.integer(n)
        self.budget.check_clock()
        compat.need(self.used + n <= self.limit, 'bounded admission within original whole-study budget')
        self.budget.charge('read_bytes', n)
        self.used += n


def roots_for(selection):
    keys = ('public_root', 'private_root')
    roots = [compat.absolute(selection[k]) for k in keys]
    for k in ('receipt', 'records', 'configuration'):
        if k in selection:
            compat.descriptor(selection[k], True)
            roots.append(compat.absolute(selection[k]['path']).parent)
    for k in ('workspace_root', 'anchor_root'):
        if k in selection:
            roots.append(compat.absolute(selection[k]))
    return roots


def preparation(selection, budget):
    """Both explicit routes keep their truthful receipt identity and schema."""
    io = BudgetIO(roots_for(selection), budget)
    prepared = compat.admit(selection, io, require_all_views=True)
    prepared['compatibility_metadata_reserved_bytes'] = io.used
    return prepared


def legacy_preflight(config):
    """Admit the existing five-field request before its receipt is captured."""
    c.exact(config, ('receipt', 'public_root', 'private_root',
                     'selected_source_manifest', 'selected_original_roster'))
    c.descriptor(config['receipt'])
    private = c.absolute(config['private_root'])
    c.need(config['receipt']['path'] == str(private / 'PREPARATION.json'),
           'literal original receipt path before any capture')
    c.need(c.typed_equal(config['selected_source_manifest'], compat.ORIGINAL_MANIFEST)
           and c.typed_equal(config['selected_original_roster'], compat.LOCK),
           'immutable selected original preparation source')


def legacy_materialization(prepared, budget):
    """Existing five-field route; stat only, never TRAIN/VALIDATION body reads."""
    compat.descriptor(prepared['receipt']['assessment'])
    io = BudgetIO([prepared['private_root']], budget)
    for artifacts in prepared['views'].values():
        for desc in artifacts.values():
            io.stat_only(desc, 'required_materialized_original_view')
    prepared['assessment_pin'] = prepared['receipt']['assessment']
    prepared['route'] = 'original'
    prepared['all_views_materialized_checked'] = True
    prepared['runtime_or_scientific_qualification'] = False
    return prepared


def validate_legacy_receipt(receipt):
    return compat.validate_original_receipt(receipt)
