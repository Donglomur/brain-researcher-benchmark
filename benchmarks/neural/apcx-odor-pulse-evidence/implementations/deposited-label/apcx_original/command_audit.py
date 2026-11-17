"""Conditional command reconstruction, never a physical-delivery target.

The official guideline allows 100-multiple overlap. Fixed-width additive
rectangles, a 1 ms clock, zero prehistory and sampling-start alignment remain
explicit hypotheses: the deposited file does not carry their certificates.
All arrays and identities produced here are owner-only diagnostic evidence.
"""
import math
import struct
from collections import Counter


HYPOTHESIS = {
    'command_scale': 100, 'pulse_width_samples': 50,
    'sampling_window_samples': 5000, 'unobserved_prefix_samples': 500,
    'sample_interval_seconds': 0.001, 'sample_zero_is_sampling_start': True,
    'zero_prehistory': True, 'additive_fixed_width_rectangles': True,
    'authenticated_for_each_released_trial': False,
}


def _atom(value):
    if type(value) is float and not math.isfinite(value):
        return {'type': 'float64_nonfinite', 'ieee754_be_hex': struct.pack('>d', value).hex()}
    if value is None or type(value) in (bool, int, float, str):
        return value
    return {'unsupported_type': type(value).__name__}


def _runs(values):
    """Complete numeric run-length representation, including zero intervals."""
    out = []
    for i, value in enumerate(values):
        # Preserve float sign/bit identity; no tolerance or saturation repair.
        key = (type(value).__name__, struct.pack('>d', value) if type(value) is float else value)
        if out and key == previous:
            out[-1]['end_exclusive'] = i + 1
        else:
            out.append({'start': i, 'end_exclusive': i + 1, 'command_value': _atom(value)})
        previous = key
    return out


def _positive_runs(values):
    out = []; start = None
    for i in range(len(values) + 1):
        positive = i < len(values) and values[i] > 0
        if positive and start is None: start = i
        if not positive and start is not None:
            out.append({'start': start, 'end_exclusive': i, 'length_samples': i - start})
            start = None
    return out


def audit_commands(values, legacy, source_fingerprint, hypothesis):
    """Explain declared conventions without clearing any original scientific hold.

    A compatible recurrence is an algebraic explanation conditional on the
    stated clock/generator assumptions. It is not proof of historical starts,
    physical valve transitions, delivered concentration or perceived pulses.
    """
    if (type(hypothesis) is not dict or set(hypothesis) != set(HYPOTHESIS)
            or any(type(hypothesis[k]) is not type(v) or hypothesis[k] != v
                   for k, v in HYPOTHESIS.items())):
        raise ValueError('exact prospective conditional hypothesis required')
    out = {
        'schema': 'apcx-command-multiplicity-diagnostic-v1',
        'status': 'UNRESOLVED', 'hypothesis': dict(hypothesis),
        'hypothesis_is_authentic_trial_metadata': False,
        'source_command_fingerprint': source_fingerprint,
        'legacy_diagnostic_unchanged': legacy,
        'physical_event_count': None, 'physical_delivery_verified': False,
        'scientific_primary_admitted': False, 'candidate_packet': False,
        'conditional_scheduled_starts': None, 'conditional_start_counts': None,
        'coincident_end_and_start_samples': None,
        'non50_binary_run_explanations': None,
        'issues': [],
    }
    if type(values) is not list or len(values) > 250000:
        out['issues'].append('COMMAND_NOT_BOUNDED_LIST'); return out
    out['source_samples'] = len(values)
    bad = [{'index': i, 'value': _atom(v)} for i, v in enumerate(values)
           if type(v) not in (int, float) or not math.isfinite(v)]
    if bad:
        out['invalid_numeric_positions'] = bad
        out['issues'].append('COMMAND_NONFINITE_OR_NONNUMERIC'); return out
    out['complete_command_runs'] = _runs(values)
    scale = hypothesis['command_scale']; width = hypothesis['pulse_width_samples']
    end = hypothesis['sampling_window_samples']; early = hypothesis['unobserved_prefix_samples']
    bad = [{'index': i, 'value': v} for i, v in enumerate(values)
           if v < 0 or v > scale * (2**31 - 1) or v % scale != 0]
    if bad:
        out['nonmultiplicity_positions'] = bad
        out['issues'].append('COMMAND_NOT_EXACT_NONNEGATIVE_100_MULTIPLE'); return out
    m = [int(v / scale) for v in values]
    multiplicities = Counter(m)
    out['multiplicity_histogram_samples'] = {str(k): multiplicities[k] for k in sorted(multiplicities)}
    out['has_overlap_multiplicity'] = any(v > 1 for v in m)
    out['full_positive_support_runs'] = _positive_runs(m)
    window = m[:end]
    out['first5000_positive_support_runs'] = _positive_runs(window)
    if max(m, default=0) <= 1:
        out['non50_binary_run_explanations'] = [
            {**r, 'explanation_status': 'UNRESOLVED_PENDING_CONDITIONAL_MODEL_CHECK',
             'conditional_starts': None, 'has_coincident_end_start': None,
             'sampling_window_clips_pulse': None, 'record_end_clips_pulse': None}
            for r in out['first5000_positive_support_runs'] if r['length_samples'] != width]
    out['full_command_area_scale_sample_units'] = sum(m)
    out['legacy_full_array_ceiling_quantity_hypothesis'] = (sum(m) + width - 1) // width
    out['first5000_area_scale_sample_units'] = sum(window)
    out['full_array_complete_pulse_equivalents'] = {'numerator': sum(m), 'denominator': width}
    out['first5000_complete_pulse_equivalents'] = {'numerator': sum(window), 'denominator': width}
    if len(m) < end:
        out['issues'].append('TRACE_SHORTER_THAN_HYPOTHESIZED_FIVE_SECONDS')
    starts = []; failures = []; previous = 0
    for i, current in enumerate(m):
        value = current - previous + (starts[i - width] if i >= width else 0)
        starts.append(value); previous = current
        if value < 0: failures.append({'index': i, 'signed_start_coefficient': value})
    out['negative_recurrence_coefficients'] = failures
    if failures:
        out['issues'].append('FIXED_WIDTH_ZERO_PREHISTORY_HYPOTHESIS_INCOMPATIBLE')
        return out
    # Forward synthesis via interval additions is independent of the inverse
    # difference recurrence. Entire acquired trace, including the tail, joins.
    delta = [0] * (len(m) + width + 1)
    events = []
    for i, count in enumerate(starts):
        if count:
            delta[i] += count; delta[i + width] -= count
            events.append({'start_sample': i, 'multiplicity': count,
                           'end_exclusive': i + width})
    active = 0; differences = []
    for i, wanted in enumerate(m):
        active += delta[i]
        if active != wanted: differences.append({'index': i, 'observed': wanted, 'synthesized': active})
    out['forward_reconstruction_differences'] = differences
    out['entire_observed_trace_reconstructed'] = not differences
    out['conditional_scheduled_starts'] = events
    out['conditional_start_counts'] = {
        'entire_trace': sum(starts), 'first5000': sum(starts[:end]),
        'unobserved_first500': sum(starts[:early]),
        'observed500to5000': sum(starts[early:end]), 'at_or_after5000': sum(starts[end:]),
    }
    out['starts_at_zero'] = starts[0] if starts else 0
    out['coincident_end_and_start_samples'] = [i for i in range(width, len(starts))
                                               if starts[i] > 0 and starts[i - width] > 0]
    out['starts_crossing_sampling_end'] = [e for e in events if e['start_sample'] < end < e['end_exclusive']]
    out['starts_crossing_record_end'] = [e for e in events if e['end_exclusive'] > len(m)]
    out['nonzero_samples_at_or_after5000'] = sum(v > 0 for v in m[end:])
    # Complete explanations for every non50 binary support run. This is not
    # available for the legacy early-return amplitude branch by guessing.
    explanations = []
    if max(m, default=0) <= 1:
        for run in out['first5000_positive_support_runs']:
            if run['length_samples'] == width: continue
            selected = [e for e in events if run['start'] <= e['start_sample'] < run['end_exclusive']]
            explanation = {**run, 'conditional_starts': selected,
                'has_coincident_end_start': any(run['start'] < i < run['end_exclusive']
                                                for i in out['coincident_end_and_start_samples']),
                'sampling_window_clips_pulse': any(e['start_sample'] < end < e['end_exclusive'] for e in selected),
                'record_end_clips_pulse': any(e['end_exclusive'] > len(m) for e in selected),
                'explanation_status': 'CONDITIONAL_RECTANGLE_COMPATIBILITY_ONLY'}
            explanations.append(explanation)
    out['non50_binary_run_explanations'] = explanations
    if differences: out['issues'].append('FORWARD_RECONSTRUCTION_MISMATCH')
    out['status'] = ('COMPATIBLE_CONDITIONAL_COMMAND_MODEL_NOT_PHYSICAL_DELIVERY'
                     if not out['issues'] else 'PARTIAL_OR_INCOMPATIBLE_COMMAND_HYPOTHESIS')
    return out
