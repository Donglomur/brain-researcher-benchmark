"""Complete internal reference/control flow; no fabricated native admission."""
from contextlib import contextmanager
from dataclasses import dataclass
import time
from .core import Custody, Refusal, encode_json, write_exact
from .roster import PARTICIPANTS, ACCESS
from .study import participant
from .statistics import group
from .figures import draw
from .artifacts import save_product, save_group


class Operations:
    def __init__(self, budget, custody):
        self.budget, self.custody = budget, custody
        self.events = []
        self.original = self

    def scoped(self, custody):
        """Route existing occurrences through an actual descendant owner.

        This is a view of one original operation ledger and Budget, not a new
        accounting lifetime, native authority, or reconstruction from raw errors.
        """
        current, seen = custody, set()
        while current is not self.custody:
            if type(current) is not Custody or current in seen:
                raise Refusal('operation custody must descend from its actual owner')
            seen.add(current)
            current = current.parent
        if type(current) is not Custody:
            raise Refusal('original operation custody required')
        if custody is self.custody:
            return self
        view = object.__new__(Operations)
        view.budget, view.custody = self.budget, custody
        view.events, view.original = self.events, self.original
        return view

    @contextmanager
    def __call__(self, name, scope):
        row = {'index': len(self.events), 'name': name, 'scope': scope,
               'start': None, 'finish': None, 'status': 'attempted', 'native': 'unqualified'}
        self.events.append(row)  # Original occurrence exists before observation.
        local = Custody(self.custody)
        with local.attempt('operation ' + name):
            try:
                self.budget.checkpoint()
                row['start'] = time.monotonic()
                yield
                row['status'] = 'body_returned'
            except BaseException as error:
                if local.first is None:
                    local.catch('operation body', error)
                row['status'] = 'failed'
            finally:
                try:
                    row['finish'] = time.monotonic()
                except BaseException as error:
                    local.catch('operation final clock', error)
                    row['status'] = 'failed_unknown_clock'
            local.raise_first()


@dataclass
class Outcome:
    status: str
    products: tuple
    unavailable: tuple
    cost: dict
    operations: tuple
    custody: Custody
    group_result: object = None


def reference_campaign(plan, input_root_fd, output_root_fd, budget, custody, *,
                       fixed_seed, member_bytes):
    """Full corrected reference; native/scientific admission is not minted here.

    Caller owns root FDs and native deployment. This internal method creates no
    process and accepts no caller-supplied native receipts. No BUILD invocation.
    """
    local = Custody(custody)
    operations = Operations(budget, local)
    rows, people, unavailable = [], [], []
    figures = {}
    result = None
    try:
        for person in PARTICIPANTS:
            current = participant(plan, person, input_root_fd, budget, local, operations)
            people.append(current)
            unavailable.extend({'participant': person, **x} for x in current.unavailable)
            coverage = {name: [{k: v for k, v in row.items() if k != 'cells'} for row in value]
                        for name, value in current.support.items() if name.startswith('theoretical_coverage/')}
            raw_coverage = encode_json({'participant': person, 'coverage': coverage,
                'structural_random': {name: value for name, value in current.support.items()
                                      if name.startswith('structural_random/')}})
            if len(raw_coverage) > member_bytes:
                raise Refusal('complete coverage metadata exceeds preselected member cap')
            rows.append(write_exact(output_root_fd, 'coverage_' + person + '.json', raw_coverage, budget, local))
            for key, array in current.products.items():
                rows.append(save_product(output_root_fd, key, array, current.axes, budget, local,
                                         member_bytes=member_bytes))
        result = group(people, fixed_seed=fixed_seed, operation=operations)
        unavailable.extend({'endpoint': name, **row} for name, row in result.unavailable.items())
        rows.extend(save_group(output_root_fd, result, budget, local, member_bytes=member_bytes))
        figures = draw(result, operation=operations, custody=local)
        # Actual figure products are required; defaults never leave save=False.
        import io
        for name, figure in figures.items():
            stream = io.BytesIO()
            try:
                with operations('figure-pdf', {'figure': name}):
                    figure.savefig(stream, format='pdf')
                raw = stream.getvalue()
                if len(raw) > member_bytes:
                    raise Refusal('figure exceeds preselected member cap')
                rows.append(write_exact(output_root_fd, name + '.pdf', raw, budget, local))
            except BaseException as error:
                if local.first is None:
                    local.catch('figure serialization', error)
            finally:
                local.close('figure serialization buffer', stream.close)
            local.raise_first()
    except BaseException as error:
        if local.first is None:
            local.catch('campaign body', error)
    finally:
        if figures:
            import matplotlib.pyplot as plt
            for figure in figures.values():
                local.close('figure retirement', lambda figure=figure: plt.close(figure))
    # Publication is a finite terminal effect. If it fails, retain it on the
    # original owner; do not recursively publish another failure report.
    status = 'failed' if local.first is not None else ('partial_scientific_support_unqualified' if unavailable else 'source_run_returned_unqualified')
    if local.first is None:
        try:
            write_exact(output_root_fd, 'RESULT_MANIFEST.json', encode_json({
                'profile': 'corrected_methods_v1', 'status': status, 'products': rows,
                'unavailable': unavailable, 'structural_controls': result.structural,
                'scientific_qualification': False,
                'native_qualification': False, 'cost_before_publication': budget.report()}), budget, local)
        except BaseException as error:
            if local.first is None:
                local.catch('terminal publication', error)
            status = 'failed'
    # Clock-free live report includes publication's logical costs and unknowns.
    budget.closed = True
    return Outcome(status, tuple(rows), tuple(unavailable), budget.report(),
                   tuple(operations.events), local, result)


def participant_launcher(*args, **kwargs):
    from .participant_executor import launch
    return launch(*args, **kwargs)


def paired_access_plan():
    return {'arms': ACCESS, 'same_inputs': True, 'same_scientific_profile': True,
            'same_noncode_resources': True, 'official_code_extra_only': True,
            'native_execution': 'concrete complete-study source implemented; native qualification held',
            'qualified_comparison': False}
