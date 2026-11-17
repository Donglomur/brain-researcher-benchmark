"""Conservative declared-memory admission; never a measured capacity check."""
from io_utils import need


def byte_envelope(request):
    # Two concurrent operator/grader public objects, private JSON, and one
    # maximal output decode. Multipliers reserve Python object/parser copies;
    # shape-specific matrices, accumulated predictions and reports follow.
    return 64 * (2*request['public_pin']['bytes'] + request['private_pin']['bytes']
                 + request['submission_cap_bytes'])


def admit_bytes(request):
    required = max(2147483648, byte_envelope(request))
    need(request['host_memory_budget_bytes'] >= required, 'Declared host budget below full JSON/copy envelope')
    return required


def admit(public, request):
    admit_bytes(request)
    max_dense = 0; query_trials = 0; query_bins = 0
    for case in public['cases']:
        widths = set(); nrows = 0
        for split in ('train', 'development', 'query'):
            for trial in case[split]:
                grc, cf = trial['grc'], trial['cf']
                need(type(grc) is list and grc and type(cf) is list and cf,
                     'Explicit nonempty channel axes for memory admission')
                width = 8 + len(grc) + len(cf); widths.add(width)
                nbin = int(round(trial['delay_s']/.1)); nrows += nbin
                if split == 'query':
                    query_trials += 1; query_bins += nbin
        need(len(widths) == 1, 'Fixed within-session feature width')
        width = next(iter(widths))
        # Sixteen float64 dense-matrix/workspace equivalents plus sixteen
        # complete feature-array equivalents. Ridge itself is unchanged.
        max_dense = max(max_dense, 128 * (width*width + nrows*width))
    # All8 prediction groups and12 detailed reports may remain live. Reserve
    # sixteen full groups with generous row/bin/dictionary overhead.
    accumulated = 16*(4096*query_trials + 256*query_bins + 1024*16)
    required = max(2147483648, byte_envelope(request)+max_dense+accumulated+67108864)
    need(request['host_memory_budget_bytes'] >= required,
         'Declared host budget below complete dimension-derived reference/report envelope')
    return {'required_host_bytes': required, 'dense_reference_workspace_bytes': max_dense,
            'parsed_json_copy_bytes': byte_envelope(request),
            'accumulated_prediction_report_bytes': accumulated,
            'query_trials': query_trials, 'query_bins': query_bins,
            'measured_capacity': False, 'whole_population_retained': True}
