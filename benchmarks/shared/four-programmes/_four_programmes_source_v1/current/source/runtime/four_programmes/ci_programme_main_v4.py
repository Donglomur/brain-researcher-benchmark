"""Fixed complete CI development continuation under its actual original owner.

This source owns preparation, both native arms, their once-only terminal call,
and complete source capture/assembly. It never issues Context, native grants,
or the later independent scientific execution selection.
"""
from .common import need, Store
from .precommit_construction import (
    PrecommitConstructionResult, _CONSTRUCTION,
    prepare_original_pair_v3, capture_original_programmes_v3,
)
from .observer import HostObserver
from .development_handles import PairCompletionHandle
from .worker_pair_entry_v3 import run_prepared_native_pair_v3

_MAIN = object()


class CIProgrammeMainV4:
    """Retained actual attempted prefix; no serialized or callback constructor."""
    def __init__(self, token, construction, host):
        need(token is _MAIN and type(construction) is PrecommitConstructionResult
             and construction._token is _CONSTRUCTION
             and construction.parent.precommit_construction is construction,
             'actual original CI construction and private return token')
        self.construction = construction
        self.parent = construction.parent
        if self.parent.first_raw is not None:
            raise self.parent.first_raw
        need(not hasattr(self.parent, 'ci_main_v4'),
             'one original complete CI MAIN attempt including failures')
        self.host = host
        self.workspace_parent = None
        self.control_parent = None
        self.pair = None
        self.pair_completion = None
        self.assembly = None
        self.phase = 'registered'
        self.raw_first = None
        self.secondaries = []
        self.entered = False
        self.complete = False
        # Register before host validation, clock, Store construction, or effects.
        self.parent.ci_main_v4 = self

    def retain(self, error, site):
        first = self.parent.first_raw
        if self.raw_first is None:
            self.raw_first = error if first is None else first
        if error is not self.raw_first:
            self.secondaries.append(error)
        self.phase = 'failed'
        self.complete = False
        self.construction.phase = 'failed'
        if self.construction.raw_first is None:
            self.construction.raw_first = self.raw_first
        elif error is not self.construction.raw_first:
            self.construction.raw_secondaries.append(error)
        try:
            self.parent.retain(error, 'development_observe', 'unknown_failure',
                               'CIProgrammeMainV4.' + site)
        except BaseException as later:
            self.secondaries.append(later)
        return self.raw_first

    def run_once(self):
        if self.raw_first is not None:
            raise self.raw_first
        need(not self.entered, 'no original CI MAIN replay')
        self.entered = True
        c = self.construction
        try:
            need(c.complete and c.phase == 'contract_captured'
                 and c.preparation is None and not c.completion_attempted
                 and not c.output_attempted,
                 'complete original contract before any pair/native/output effect')
            contract = c.contract
            owner = contract.owner
            need(owner.parent is self.parent and c.construction.owner is owner
                 and c.construction.session.programme == 'PAPER-FIND-050'
                 and not c.construction.session.closed,
                 'same live complete CI source session, contract and parent')
            need(type(self.host) is HostObserver and self.host.meter is owner.host
                 and type(self.host.outputs) is Store
                 and self.host.outputs.meter is owner.host
                 and self.host.outputs.root == c.bootstrap.outputs.root
                 and self.host.mapping['source'] == self.parent.clock['mapping_source']
                 and self.host.mapping['boot_id'] == self.parent.identity['boot_id'],
                 'actual earlier original H observer under the same source/clock/share')
            # Both roots come from the complete admitted original recipe. The
            # Store constructor and all preparation effects retain that payer.
            self.phase = 'parent_roots'
            recipe = contract.recipe
            for path in (recipe['workspace_parent'], recipe['private_control_parent']):
                amount = len(path.encode('utf8'))
                owner.host.charge('work_units', amount * 64 + 4096)
                owner.host.charge('retained_bytes', amount * 16 + 4096)
            self.workspace_parent = Store(recipe['workspace_parent'], owner.host)
            self.control_parent = Store(recipe['private_control_parent'], owner.host)
            self.phase = 'preparation'
            returned = prepare_original_pair_v3(
                c, workspace_parent=self.workspace_parent,
                control_parent=self.control_parent)
            self.pair = c.preparation
            need(returned is c, 'same retained original preparation result')
            if c.raw_first is not None:
                raise c.raw_first
            need(c.phase == 'preparation_completed'
                 and self.pair is self.parent.preparation
                 and self.pair.promotion is self.pair,
                 'both exact original arms prepared before either worker launches')
            self.phase = 'native_pair'
            self.pair_completion = run_prepared_native_pair_v3(self.pair, self.host)
            # run_prepared_native_pair_v3 already invokes the one original
            # finish_pair_backend_v1. Calling complete_original_pair_v3 here
            # would repeat terminal observation and is deliberately forbidden.
            need(type(self.pair_completion) is PairCompletionHandle
                 and self.pair.backend_completion is self.pair_completion
                 and self.pair_completion.pair is self.pair,
                 'same complete actual H-owned two-arm terminal return')
            self.pair_completion.require_original()
            c.pair_completion = self.pair_completion
            c.completion_attempted = True
            c.phase = 'pair_completed'
            self.phase = 'complete_source_capture'
            returned = capture_original_programmes_v3(c)
            need(returned is c and c.programmes_complete,
                 'full two-arm source receipts, seals and original scientific census')
            self.assembly = c.assembly
            self.complete = True
            self.phase = 'programmes_completed'
            return self
        except BaseException as error:
            # Keep outputs even when a producer failed after registration but
            # before returning. No repeating launch/finish/capture or deleting
            # unresolved workspaces to manufacture a cleaner terminal state.
            self.pair = c.preparation
            if self.pair is not None:
                self.pair_completion = getattr(self.pair, 'backend_completion', None)
            self.assembly = c.assembly
            raise self.retain(error, 'run_once')


def continue_original_ci_main_v4(construction, host):
    """Actual fixed sequence from an original contract to complete programmes."""
    return CIProgrammeMainV4(_MAIN, construction, host).run_once()

