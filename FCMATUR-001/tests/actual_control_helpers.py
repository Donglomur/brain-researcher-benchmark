"""Authoring-only FCMATUR output controls; never part of scoring acceptance.

No original-table reader, source reconstruction, HTTP or import-time analysis.
All alternate calculations use already authenticated reference covariates and
the genuine accepted participant values. Mutants are classified before the
normal complete validator is called by the authoring test harness.
"""
import copy
from decimal import Decimal
import math

import output_contract as c


POSITIVES = ('key_permutation', 'six_decimal_derived', 'optional_extras',
             'integer_representations', 'own_affine_replay')
NUMERICAL = ('weighted_between', 'within_without_site', 'motion_without_fd',
             'sex_without_sex', 'controls_use_parent', 'nominal_extra_rank',
             'quadratic_missing_df', 'quadratic_linear_denominator',
             'absolute_signed_correlations', 'stale_affine_receipts')
BINDING = ('signflip_values', 'constant_values', 'permuted_values', 'covariate_swap',
           'metadata_swap', 'active_mask', 'missing_person', 'missing_site',
           'source_hash', 'participant_alias')


def need(ok, reason):
    c.need(ok, reason)


def replay(documents, reference):
    ids = reference['participant_ids']
    need(0 < len(ids) <= 1035 and len(reference['phenotype_ledger']) <= 1112,
         'authoring bounded participant/phenotype set')
    _, accepted = c.validate_participants(documents['connectivity.csv'], reference)
    kernel = c.load_kernel()
    return kernel, accepted, kernel.analyze(reference['canonical_rows'], accepted)


def install_replay(documents, result):
    candidate = copy.deepcopy(documents)
    primary, sensitivity = c.public_statistics(result)
    candidate['connectivity_age.json'] = primary
    candidate['sensitivity.json'] = sensitivity
    return candidate


def numeric_effects(actual, expected):
    """Required numeric/null/Boolean and inference-status discrepancies.

    Called on kernel-shaped scientific views, whose keyed rows already have
    canonical order. The validator's public tolerance/domain comparator is the
    criterion; exact discrete numeric support changes are also identified.
    """
    changes = []
    def walk(a, e, path, key=''):
        if isinstance(e, dict):
            if not isinstance(a, dict): return
            for k, value in e.items():
                if k in a: walk(a[k], value, path + '.' + k, k)
        elif isinstance(e, list):
            if e and all(isinstance(v, (int, float, Decimal)) and not isinstance(v, bool) for v in e) and a is None:
                changes.append(dict(path=path, actual=None, expected=e, absolute_gap=None, kind='numeric_support'))
            elif isinstance(a, list):
                for i, (av, ev) in enumerate(zip(a, e)):
                    walk(av, ev, path + '[' + str(i) + ']', key)
        elif e is None or isinstance(e, (bool, int, float, Decimal)):
            try:
                c.match(a, e, path, key=key)
            except (ValueError, TypeError):
                numeric = lambda v: isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)
                gap = abs(float(a) - float(e)) if numeric(a) and numeric(e) else None
                changes.append(dict(path=path, actual=a, expected=e, absolute_gap=gap, kind='numeric'))
        elif isinstance(e, str) and (key == 'status' or key.endswith('_status')) and a != e:
            changes.append(dict(path=path, actual=a, expected=e, absolute_gap=None, kind='inference_status'))
    walk(actual, expected, 'scientific')
    return dict(n_changed=len(changes), n_numeric_changes=sum(r['kind'] != 'inference_status' for r in changes),
                n_inference_status_changes=sum(r['kind'] == 'inference_status' for r in changes), max_absolute_gap=max(
        (r['absolute_gap'] for r in changes if r['absolute_gap'] is not None), default=None),
        examples=changes[:12])


def scientific_view(documents):
    return {'primary': documents['connectivity_age.json'], 'sensitivity': documents['sensitivity.json']}


def report(mode, category, status, reason='', effects=None):
    return dict(mode=mode, category=category, status=status, reason=reason,
                effect=effects or dict(n_changed=0, max_absolute_gap=None, examples=[]))


def affine_values(accepted):
    return {sid: None if value is None else value * (1 + 2e-7) + 2e-7
            for sid, value in accepted.items()}


def put_values(documents, values):
    for row in documents['connectivity.csv']:
        value = values[row['FILE_ID']]
        row['connectivity'] = '' if value is None else repr(float(value))


def positive_candidate(mode, documents, reference):
    need(mode in POSITIVES, 'unknown positive authoring mode')
    candidate = copy.deepcopy(documents)
    if mode == 'key_permutation':
        candidate['connectivity.csv'].reverse()
        def permute(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in c.MEMBERSHIPS | set(c.KEYED_LISTS) | {'exact_constant_columns'}:
                        if isinstance(child, list): child.reverse()
                    permute(child)
            elif isinstance(value, list):
                for child in value: permute(child)
        for name in ('connectivity_age.json', 'sensitivity.json', 'run_metadata.json'):
            permute(candidate[name])
    elif mode == 'six_decimal_derived':
        def rounded(value):
            if isinstance(value, (float, Decimal)): return round(float(value), 6)
            if isinstance(value, list): return [rounded(v) for v in value]
            if isinstance(value, dict): return {k: rounded(v) for k, v in value.items()}
            return value
        for name in ('connectivity_age.json', 'sensitivity.json'): candidate[name] = rounded(candidate[name])
    elif mode == 'optional_extras':
        for row in candidate['connectivity.csv']: row['authoring_note'] = 'optional descriptive field'
        for name in ('connectivity_age.json', 'sensitivity.json', 'run_metadata.json'):
            candidate[name]['authoring_note'] = 'No required scientific direction.'
        candidate['sensitivity.json']['checks']['nonlinear_age'].update(
            added_norm='optional', added_cutoff='optional', added_basis_orthogonality='optional')
    elif mode == 'integer_representations':
        # Only declared counts/codes; participant identities and source tokens
        # remain exact strings, not digit-normalized aliases.
        for row in candidate['connectivity.csv']:
            for key in ('n_frames', 'n_columns', 'n_active_columns', 'n_edges', 'sex', 'dx_group'):
                if row[key] != '': row[key] = str(c.io.integer(row[key])) + 'e0'
            for key in c.FLAGS: row[key] = 'TRUE' if c.io.csv_boolean(row[key]) else '0'
    else:
        kernel, accepted, _ = replay(documents, reference)
        changed = affine_values(accepted)
        try:
            result = kernel.analyze(reference['canonical_rows'], changed)
        except ValueError as exc:
            return None, report(mode, 'positive', 'not_constructed', 'public_fidelity: ' + str(exc))
        put_values(candidate, changed)
        candidate = install_replay(candidate, result)
    return candidate, report(mode, 'positive', 'constructed')


def replacement_correlation(target, r, kernel):
    if target['r'] is None or r is None:
        return False
    target.update(kernel.correlation_inference(float(r), int(target['df'])))
    return True


def numerical_candidate(mode, documents, reference):
    need(mode in NUMERICAL, 'unknown numerical authoring mode')
    kernel, accepted, result = replay(documents, reference)
    baseline = install_replay(documents, result)
    candidate = copy.deepcopy(baseline)
    primary, checks = candidate['connectivity_age.json'], candidate['sensitivity.json']['checks']
    rows = {r['subject']: r for r in reference['canonical_rows']}
    available = True

    def raw_r(ids, *, sites=False):
        if len(ids) < 2: return None
        selected = [rows[sid] for sid in ids]
        model = kernel.nuisance_design(len(ids), sites=[r['site_id'] for r in selected] if sites else None)
        x = model.residual([r['age'] for r in selected])
        y = model.residual([accepted[sid] for sid in ids])
        return kernel.pearson(x, y)

    if mode == 'weighted_between':
        means = result['site_means']
        # Repeat site means by source-defined sample sizes: deliberately wrong
        # ecological weighting, with correct site IDs/df/provenance retained.
        need(sum(r['n'] for r in means) <= 1035, 'authoring weighted sample cap')
        x = [r['mean_age'] for r in means for _ in range(r['n'])]
        y = [r['mean_connectivity'] for r in means for _ in range(r['n'])]
        available = replacement_correlation(primary['between_site'], kernel.pearson(x, y), kernel)
    elif mode == 'within_without_site':
        target = primary['within_site']
        available = replacement_correlation(target, raw_r(target['ids']), kernel)
    elif mode in ('motion_without_fd', 'sex_without_sex'):
        which = 'motion' if mode == 'motion_without_fd' else 'sex'
        target = checks[which]['within_site']
        available = replacement_correlation(target, raw_r(target['ids'], sites=True), kernel)
    elif mode == 'controls_use_parent':
        target = checks['diagnosis']['within_site']
        available = replacement_correlation(target, raw_r(primary['within_site']['ids'], sites=True), kernel)
    elif mode == 'nominal_extra_rank':
        target = primary['within_site']
        available = target['n'] > 0
        if available:
            target['rank'] += 1
            target['df'] -= 1
            if target['r'] is not None: target.update(kernel.correlation_inference(target['r'], target['df']))
    elif mode in ('quadratic_missing_df', 'quadratic_linear_denominator'):
        q = checks['nonlinear_age']
        denominator = q['rss_quadratic'] if mode == 'quadratic_missing_df' else q['rss_linear']
        available = q['status'] == 'ok' and denominator is not None and denominator > 0
        if available:
            wrong_df2 = 1 if mode == 'quadratic_missing_df' else q['df2']
            wrong = (q['gain_ss'] / q['df1']) / (denominator / wrong_df2)
            if math.isfinite(wrong):
                q['F_added_quadratic'] = wrong
                q['p_added_quadratic'] = float(kernel.stats.f.sf(wrong, q['df1'], q['df2']))
            else: available = False
    elif mode == 'absolute_signed_correlations':
        associations = [primary[k] for k in ('pooled', 'within_site', 'between_site')]
        associations += [checks[k][level] for k in ('motion', 'diagnosis', 'sex') for level in ('pooled', 'within_site')]
        associations += checks['site_specific_slopes']['per_site']
        available = any(r['r'] is not None for r in associations)
        for row in associations:
            if row['r'] is not None: replacement_correlation(row, abs(row['r']), kernel)
    else:
        changed = affine_values(accepted)
        try:
            own = kernel.analyze(reference['canonical_rows'], changed)
        except ValueError as exc:
            return None, report(mode, 'numerical', 'not_constructed', 'public_fidelity: ' + str(exc))
        put_values(candidate, changed)
        expected = install_replay(candidate, own)
        effects = numeric_effects(scientific_view(candidate), scientific_view(expected))
        status = 'effective' if effects['n_changed'] else 'nondiscriminating'
        return candidate, report(mode, 'numerical', status, effects=effects)
    if not available:
        return None, report(mode, 'numerical', 'unavailable', 'required finite mathematical support absent')
    need(candidate['connectivity.csv'] == documents['connectivity.csv'] and
         candidate['run_metadata.json'] == documents['run_metadata.json'], 'numerical control changed source receipts')
    effects = numeric_effects(scientific_view(candidate), scientific_view(baseline))
    return candidate, report(mode, 'numerical', 'effective' if effects['n_changed'] else 'nondiscriminating', effects=effects)


def binding_candidate(mode, documents, reference):
    need(mode in BINDING, 'unknown binding authoring mode')
    kernel, accepted, result = replay(documents, reference)
    candidate = install_replay(documents, result)
    table, metadata = candidate['connectivity.csv'], candidate['run_metadata.json']
    if mode in ('signflip_values', 'constant_values', 'permuted_values'):
        finite = sorted(sid for sid, value in accepted.items() if value is not None)
        if not finite: return None, report(mode, 'binding', 'unavailable', 'no defined participant values')
        changed = dict(accepted)
        for i, sid in enumerate(finite):
            changed[sid] = (-accepted[sid] if mode == 'signflip_values' else 0.0 if mode == 'constant_values'
                            else accepted[finite[-1 - i]])
        if changed == accepted:
            return candidate, report(mode, 'binding', 'nondiscriminating', 'primitive transformation is an exact no-op')
        put_values(candidate, changed)
    elif mode == 'covariate_swap':
        pair = next(((i, j) for i in range(len(table)) for j in range(i + 1, len(table))
                     if table[i]['age'] != table[j]['age']), None)
        if pair is None: return None, report(mode, 'binding', 'unavailable', 'no distinct age receipts')
        i, j = pair
        table[i]['age'], table[j]['age'] = table[j]['age'], table[i]['age']
    elif mode == 'metadata_swap':
        ledger = metadata['phenotype_ledger']
        pair = next(((i, j) for i in range(len(ledger)) for j in range(i + 1, len(ledger))
                     if ledger[i]['tokens'] != ledger[j]['tokens']), None)
        if pair is None: return None, report(mode, 'binding', 'unavailable', 'no distinct phenotype token receipts')
        i, j = pair
        ledger[i]['tokens'], ledger[j]['tokens'] = ledger[j]['tokens'], ledger[i]['tokens']
    elif mode == 'active_mask':
        person = metadata['source_observed']['persons'][reference['participant_ids'][0]]
        person['active_columns'][0] = not person['active_columns'][0]
    elif mode == 'missing_person': table.pop()
    elif mode == 'missing_site':
        sites = candidate['connectivity_age.json']['eligible_site_ids']
        if not sites: return None, report(mode, 'binding', 'unavailable', 'no eligible sites')
        sites.pop()
    elif mode == 'source_hash':
        item = metadata['source_files'][0]
        item['sha256'] = ('1' if item['sha256'][0] == '0' else '0') + item['sha256'][1:]
    else:
        table[0]['FILE_ID'] = table[0]['FILE_ID'].rsplit('_', 1)[-1]
    # Bound-slice checks precede the complete validator. If primitive changes
    # remain lawful, recompute their own scientific target before classifying
    # stale receipts; never claim every changed float is an effective negative.
    try:
        _, changed_values = c.validate_participants(table, reference)
        c.validate_metadata(metadata, reference)
        expected = install_replay(candidate, kernel.analyze(reference['canonical_rows'], changed_values))
        c.match(candidate['connectivity_age.json'], expected['connectivity_age.json'], 'primary')
        c.match(candidate['sensitivity.json'], expected['sensitivity.json'], 'sensitivity')
    except (ValueError, TypeError) as exc:
        return candidate, report(mode, 'binding', 'effective', 'prevalidated binding/receipt discrepancy: ' + str(exc),
                                 dict(n_changed=1, max_absolute_gap=None, examples=[]))
    return candidate, report(mode, 'binding', 'nondiscriminating', 'transformed receipts remain within the public contract')
