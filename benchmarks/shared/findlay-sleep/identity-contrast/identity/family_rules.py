"""Source-derived analytic-view census. Zero I/O, no fits, no scientific imports.

Caller must verify the selected ledger byte pins before passing parsed objects.
All input rows belong to the outer full census; this module only classifies views.
"""
from collections import Counter
from dataclasses import dataclass
import math
from types import MappingProxyType

FAMILY_LEDGER_SHA256 = 'e6602394041e2a6f448db374ffccbf06856f262e13df468003a901ae4fa2eced'
INPUT_LEDGER_SHA256 = 'd2756c791ccdedf22de2ef5e2949b43d804c0232c1aeddcb6ff25411ddaafed1'
HOMEOSTASIS_CONDITIONS = ('Early.BSL.NREM', 'Late.BSL.NREM', 'Early.EXT.Wake',
                         'Late.EXT.Wake', 'Early.REC.NREM', 'Late.REC.NREM')
EXPERIMENTS = ('Novelty', 'Locomotion', 'Dual')
BALANCED_SUBJECTS = None

def configure_private_policy(policy):
    global BALANCED_SUBJECTS
    BALANCED_SUBJECTS = frozenset(policy["balanced_subjects"])
R_HOMEOSTASIS_CONTRASTS = (
    ('E.REC - L.BSL', HOMEOSTASIS_CONDITIONS[4], HOMEOSTASIS_CONDITIONS[1]),
    ('L.REC - E.REC', HOMEOSTASIS_CONDITIONS[5], HOMEOSTASIS_CONDITIONS[4]),
    ('L.EWK - E.EWK', HOMEOSTASIS_CONDITIONS[3], HOMEOSTASIS_CONDITIONS[2]),
    ('E.BSL - L.BSL', HOMEOSTASIS_CONDITIONS[0], HOMEOSTASIS_CONDITIONS[1]),
    ('E.REC - E.BSL', HOMEOSTASIS_CONDITIONS[4], HOMEOSTASIS_CONDITIONS[0]))
PYTHON_CONDITION_CONTRASTS = MappingProxyType({
    'nrem_rebound': ('early_rec_nrem', 'early_rec_nrem_match'),
    'nrem_surge': ('early_rec_nrem', 'early_bsl_nrem'),
    'nrem_rec_decline': ('early_rec_nrem', 'late_rec_nrem'),
    'nrem_bsl_decline': ('early_bsl_nrem', 'early_rec_nrem_match'),
    'ext_wake_incline': ('late_ext_wake', 'early_ext_wake'),
    'sd_wake_incline': ('early_sd_wake', 'late_sd_wake')})
CONTRAST_SUFFIXES = ('.Rebound', '.REC.Decline', '.Surge', '.BSL.Decline')
PROCESSED_CONTRAST_BINDING_VERIFIED = False
CONDITION_ALIASES = MappingProxyType({
    'early_bsl_nrem': 'Early.BSL.NREM', 'early_rec_nrem_match': 'Late.BSL.NREM',
    'early_ext_wake': 'Early.EXT.Wake', 'late_ext_wake': 'Late.EXT.Wake',
    'early_rec_nrem': 'Early.REC.NREM', 'late_rec_nrem': 'Late.REC.NREM',
    'early_nod_wake': 'Early.NOD.Wake', 'early_sd_wake': 'Early.SD.Wake',
    'late_sd_wake': 'Late.SD.Wake', 'sd_wake': 'SD.Wake', 'ext_wake': 'EXT.Wake',
    'nod_wake': 'NOD.Wake', 'cow_wake': 'COW.Wake', 'ctn_wake': 'CTN.Wake',
    'late_cow_wake': 'Late.COW.Wake'})
REM_SOURCE_RENAMES = MappingProxyType({'REM fraction': 'REM.Fraction',
    'Total Hippocampal Theta:Delta': 'Total.Hippocampal.ThetaDeltaRatio'})
EXPECTED_FAMILY_COUNTS = MappingProxyType({
    'condition_correlation': 15, 'condition_difference_correlation': 24,
    'cortical_spindle': 6, 'eta_ext_wake_increase': 1, 'firing_rates': 3,
    'first_novelty': 7, 'homeostasis': 13,
    'multiregion_condition_difference_correlation': 20,
    'ripple_freq': 1, 'sgfg': 1, 'state_rate': 2, 'fractional_occupancy': 5})
OCCUPANCY_IDS = ('baseline_occupancy', 'recovery_occupancy', 'novelty_occupancy',
                 'locomotion_occupancy', 'rem_fraction_theta_delta')
EXPECTED_IDS = frozenset(
    family + ':' + str(i)
    for family, count in EXPECTED_FAMILY_COUNTS.items() if family != 'fractional_occupancy'
    for i in (range(4, 7) if family == 'firing_rates' else range(1, count + 1))) | frozenset(
    'fractional_occupancy:' + name for name in OCCUPANCY_IDS)
EXPECTED_TABLES = frozenset(('condition_measures.pqt', 'condition_contrasts.pqt',
    'multicortical_condition_measures.pqt', 'multicortical_condition_contrasts.pqt',
    'cortical_spindle_condition_measures.pqt', 'cortical_spindle_state_rates.pqt',
    'dspk_state_rates.pqt', 'firing_rates.pqt', 'off_durations.pqt',
    'ripple_frequency_by_state.pqt', 'AeryJones_sgfg_medians_by_epoch_type.pqt',
    'sleep_period_fractional_occupancy.pqt', 'rec_rem_vs_ewk_tdr.pqt'))


def need(ok, message):
    if not ok:
        raise ValueError(message)


def missing(value):
    return value is None or (type(value) is float and math.isnan(value))


def numeric(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def intervals(indices):
    result = []
    for value in sorted(set(indices)):
        if result and result[-1][1] == value:
            result[-1][1] = value + 1
        else:
            result.append([value, value + 1])
    return result


@dataclass(frozen=True)
class Rule:
    identifier: str
    family: str
    parameters: object
    tables: tuple
    active: tuple
    required: object
    key_fields: tuple
    subject_field: str
    experiment_field: object
    condition_field: object
    levels: tuple
    filters: object
    numeric_fields: tuple
    transform: str
    gates: tuple


def _rule(row, schemas):
    identifier = row['source_analysis_id']
    family = identifier.split(':')[0]
    p = dict(row['source_parameters'])
    tables = tuple(row['input_tables'])
    need(tables and len(set(tables)) == len(tables) and set(tables) <= EXPECTED_TABLES,
         'Exact distinct declared source tables')
    base = ['subject', 'experiment']
    subject, experiment, condition = 'subject', 'experiment', None
    levels, filters, nums, transform = (), {}, (), 'identity'
    gates = ['endpoint_cohort_join_pending', 'model_design_and_fit_unexecuted']
    active = tables
    param_names = ('x_variable', 'y_variable') if 'correlation' in family else (
        ('response_var', 'region', 'cell_type') if family == 'firing_rates' else
        ('response_variable',) if family in ('homeostasis', 'cortical_spindle',
            'eta_ext_wake_increase', 'first_novelty', 'state_rate') else ())
    if family == 'condition_correlation':
        param_names += ('x_condition', 'y_condition')
    need(all(type(p.get(k)) is str and 0 < len(p[k]) <= 256 for k in param_names),
         'Typed exact source parameters for ' + identifier)
    if family == 'condition_correlation':
        condition = 'condition'
        levels = tuple(dict.fromkeys((p['x_condition'], p['y_condition'])))
        filters[condition] = levels
        nums = (p['x_variable'], p['y_variable'])
        required = base + [condition] + list(nums)
        key = tuple(base)
    elif 'condition_difference_correlation' in family:
        nums = (p['x_variable'], p['y_variable'])
        required = base + list(nums)
        key = tuple(base)
        gates += ['processed_contrast_export_algebra_unresolved',
                  '29_vs_28_complete_case_support_pending']
        if family.startswith('multiregion'):
            required += ['acronym', 'region', 'spw_probe']
            key += ('acronym', 'region', 'spw_probe')
            gates += ['68_vs_64_regional_support_pending']
    elif family in ('homeostasis', 'eta_ext_wake_increase', 'cortical_spindle', 'first_novelty'):
        condition = 'condition'
        levels = HOMEOSTASIS_CONDITIONS
        if family == 'cortical_spindle':
            levels = tuple(x for x in levels if 'NREM' in x)
        if family == 'first_novelty':
            levels = ('Early.NOD.Wake',)
            filters['experiment'] = ('Novelty', 'Dual')
            gates += ['balanced_and_unbalanced_subviews_not_extra_families']
        filters[condition] = levels
        nums = (p['response_variable'],)
        required = base + [condition] + list(nums)
        key = tuple(base + [condition])
    elif family == 'firing_rates':
        experiment, condition = None, 'condition'
        levels = HOMEOSTASIS_CONDITIONS
        filters.update(condition=levels, region=(p['region'],), petersen_cell_type=(p['cell_type'],))
        nums = (p['response_var'],)
        required = ['subject', 'cluster_id', 'condition', 'probe', 'region',
                    'petersen_cell_type'] + list(nums)
        key = ('subject', 'cluster_id', 'condition')
        transform = 'precomputed_sqrt_no_second_transform'
        gates += ['probe_to_subject_cluster_identity_join_pending']
    elif family == 'sgfg':
        subject, experiment, condition = 'Subject', 'Experiment', 'Epoch.Type'
        levels = ('SPW.Wake', 'No.SPW.Wake', 'SPW.NREM', 'No.SPW.NREM')
        filters['ROI'] = ('CA1-slm',)
        nums = ('Slow.Fast.Gamma.Ratio',)
        key = ('Subject', 'Experiment', 'ROI', 'Epoch.Type')
        required = list(key) + list(nums)
        gates += ['Epoch_Type_created_but_Epoch_dot_Type_fitted',
                  'four_level_factor_and_contrast_matrix_join_unresolved']
    elif family == 'ripple_freq':
        condition, levels = 'state', ('Wake', 'NREM')
        filters[condition] = levels
        nums = ('Ripple.Frequency',)
        key = tuple(base + [condition]); required = list(key) + list(nums)
    elif family == 'state_rate':
        condition, levels = 'state', ('Wake', 'NREM', 'IS', 'REM')
        filters[condition] = levels
        nums, transform = (p['response_variable'],), 'sqrt'
        key = tuple(base + [condition]); required = list(key)
        gates += ['outer_merge_multiplicity_must_be_unique']
    elif family == 'fractional_occupancy':
        suffix = identifier.split(':', 1)[1]
        if suffix == 'rem_fraction_theta_delta':
            active = ('rec_rem_vs_ewk_tdr.pqt',)
            subject, experiment = 'Subject', 'Experiment'
            key = ('Subject', 'Experiment')
            nums = ('REM fraction', 'Total Hippocampal Theta:Delta')
            required = list(key) + list(nums)
            gates += ['complete_cases_all_raw_columns', '28_advertised_rows_not_verified_cohort']
        else:
            active = ('sleep_period_fractional_occupancy.pqt',)
            condition, levels = 'state', ('NREM', 'IS', 'REM', 'Wake', 'MA')
            filters.update(experiment=('Novelty', 'Locomotion'), state=levels,
                           day=('Baseline', 'Recovery'))
            if suffix.startswith('baseline'): filters['day'] = ('Baseline',)
            if suffix.startswith('recovery'): filters['day'] = ('Recovery',)
            if suffix.startswith('novelty'): filters['experiment'] = ('Novelty',)
            if suffix.startswith('locomotion'): filters['experiment'] = ('Locomotion',)
            nums = ('fractional_occupancy',)
            key = ('subject', 'experiment', 'day', 'state')
            required = list(key) + list(nums)
            gates += ['upstream_single_subject_exclusion_requires_actual_roster_check']
    else:
        raise ValueError('Unsupported published source family')
    need(set(active) <= set(tables), 'Source-selected active table declared in ledger')
    if experiment:
        filters.setdefault(experiment, EXPERIMENTS)
    required_by_table = {}
    for table in active:
        fields = list(required)
        if family == 'state_rate' and nums[0] in schemas.get(table, ()):
            fields += list(nums)
        if identifier.endswith(':rem_fraction_theta_delta'):
            fields += list(schemas.get(table, ()))
        required_by_table[table] = tuple(dict.fromkeys(fields))
    return Rule(identifier, family, MappingProxyType(p), tables, active,
                MappingProxyType(required_by_table), key, subject, experiment, condition,
                levels, MappingProxyType(filters), nums, transform, tuple(gates))


class RuleBook:
    def __init__(self, rules, schemas, sizes):
        self._rules = MappingProxyType(dict(rules))
        self._schemas = MappingProxyType(dict(schemas))
        self._sizes = MappingProxyType(dict(sizes))
        self.ids = tuple(rules)

    def tables_for(self, identifier):
        return self._rules[identifier].tables

    def describe(self, identifier):
        r = self._rules[identifier]
        return {'source_analysis_id': identifier, 'family': r.family,
                'tables': list(r.tables), 'active_tables': list(r.active),
                'required_fields': {k: list(v) for k, v in r.required.items()},
                'key_fields': list(r.key_fields), 'condition_levels': list(r.levels),
                'source_filters': {k: list(v) for k, v in r.filters.items()},
                'numeric_fields': list(r.numeric_fields), 'transform': r.transform,
                'unresolved_gates': list(r.gates), 'fit_executed': False,
                'scientific_qualification': False}

    def assess_schema(self, identifier):
        r = self._rules[identifier]
        tables = {table: {'required': list(fields),
                         'missing': sorted(set(fields) - set(self._schemas.get(table, ())))}
                  for table, fields in r.required.items()}
        extra = []
        if r.family == 'state_rate' and sum(r.numeric_fields[0] in self._schemas.get(t, ())
                                            for t in r.active) != 1:
            extra.append('response_must_have_exactly_one_outer_merge_source')
        return {'source_analysis_id': identifier, 'tables': tables,
                'schema_fields_present': not extra and all(not v['missing'] for v in tables.values()),
                'schema_gates': extra, 'unresolved_gates': list(r.gates),
                'authentic_rows_observed': False}

    def _decision(self, identifier, table, row):
        r = self._rules[identifier]
        need(table in r.tables, 'Only declared family tables')
        need(type(row) is dict, 'Decoded scalar row mapping required')
        if table not in r.active:
            return {'status': 'irrelevant', 'reasons': ['other_subfamily_table']}, None
        schema = self.assess_schema(identifier)
        absent = [k for k in r.required[table] if k not in row]
        absent += schema['tables'][table]['missing']
        if absent or schema['schema_gates']:
            return {'status': 'unresolved', 'reasons': sorted(set(
                ['missing_field:' + k for k in absent] + schema['schema_gates']))}, None
        filters = ['source_filter:' + k for k, allowed in r.filters.items()
                   if row.get(k) not in allowed]
        # A row in the X condition need not have a finite value of the unrelated
        # Y variable; the official source joins separately selected X/Y columns.
        applicable = set(r.required[table])
        if r.family == 'condition_correlation':
            applicable -= set(r.numeric_fields)
            if row['condition'] == r.parameters['x_condition']:
                applicable.add(r.parameters['x_variable'])
            if row['condition'] == r.parameters['y_condition']:
                applicable.add(r.parameters['y_variable'])
        nulls = ['null:' + k for k in sorted(applicable) if missing(row[k])]
        # The REM loader explicitly applies complete.cases to every raw column.
        if identifier.endswith(':rem_fraction_theta_delta'):
            nulls += ['complete_cases_null:' + k for k in self._schemas[table] if missing(row.get(k))]
        if filters:
            return {'status': 'excluded', 'reasons': sorted(set(filters + nulls))}, None
        if nulls:
            return {'status': 'excluded', 'reasons': sorted(set(nulls))}, None
        # The official regional exporter stores a Boolean same-SPW-probe flag.
        # Keep its two exact levels; do not coerce 0/1 or strings into identities.
        bad_keys = [k for k in r.key_fields if (
                    type(row[k]) is not bool if k == 'spw_probe' else
                    (type(row[k]) not in (str, int, float) or
                     (type(row[k]) is str and not row[k]) or
                     (type(row[k]) is float and not math.isfinite(row[k]))))]
        if bad_keys:
            return {'status': 'unresolved', 'reasons': ['invalid_identity:' + k for k in bad_keys]}, None
        text_keys = [r.subject_field] + ([r.condition_field] if r.condition_field else [])
        if any(type(row[k]) is not str or not row[k] for k in text_keys):
            return {'status': 'unresolved', 'reasons': ['invalid_categorical_identity']}, None
        nums = r.numeric_fields
        roles = {}
        if r.family == 'condition_correlation':
            if row['condition'] == r.parameters['x_condition']: roles['x'] = r.parameters['x_variable']
            if row['condition'] == r.parameters['y_condition']: roles['y'] = r.parameters['y_variable']
        elif r.family == 'state_rate':
            if nums[0] in self._schemas[table]: roles['value'] = nums[0]
        else:
            roles = {str(i): field for i, field in enumerate(nums)}
        bad = ['nonfinite_or_nonnumeric:' + field for field in roles.values() if not numeric(row[field])]
        if bad:
            return {'status': 'unresolved', 'reasons': sorted(set(bad))}, None
        values = {role: row[field] for role, field in roles.items()}
        if r.transform == 'sqrt' and values:
            if values['value'] < 0:
                return {'status': 'unresolved', 'reasons': ['negative_sqrt_domain']}, None
            values['value'] = math.sqrt(values['value'])
        payload = {'key': tuple(row[k] for k in r.key_fields), 'roles': values,
                   'subject': row[r.subject_field],
                   'experiment': row[r.experiment_field] if r.experiment_field else None,
                   'condition': row[r.condition_field] if r.condition_field else None,
                   'balanced': r.family == 'first_novelty' and row[r.subject_field] in BALANCED_SUBJECTS}
        return {'status': 'selected', 'reasons': []}, payload

    def select_row(self, identifier, table, row):
        return self._decision(identifier, table, row)[0]

    def new_accumulator(self, identifier, max_keys=16384, max_intervals=8192):
        return Accumulator(self, identifier, max_keys, max_intervals)


class Accumulator:
    def __init__(self, book, identifier, max_keys, max_intervals):
        need(type(max_keys) is int and 1 <= max_keys <= 65536 and
             type(max_intervals) is int and 1 <= max_intervals <= 65536, 'Bounded census metadata')
        self.book, self.rule = book, book._rules[identifier]
        self.max_keys, self.max_intervals = max_keys, max_intervals
        self.seen = Counter(); self.counts = Counter(); self.reason_counts = Counter()
        self.spans = {}; self.keys = {}; self.duplicates = {}; self.subjects = set()
        self.sessions = set(); self.conditions = Counter(); self.balanced = Counter()
        self.group_conditions = {}
        self.failed = False; self.closed = False

    def _span(self, table, reason, index):
        spans = self.spans.setdefault((table, reason), [])
        if spans and spans[-1][1] == index:
            spans[-1][1] = index + 1
        else:
            spans.append([index, index + 1])
        need(sum(len(v) for v in self.spans.values()) <= self.max_intervals,
             'Complete interval census exceeds declared bound')

    def observe(self, table, row, row_index=None):
        need(not self.failed and not self.closed, 'Open nonfailed accumulator')
        try:
            need(table in self.rule.tables, 'Exact relevant table')
            index = self.seen[table] if row_index is None else row_index
            need(type(index) is int and index == self.seen[table], 'Contiguous zero-based table row index')
            decision, payload = self.book._decision(self.rule.identifier, table, row)
            self.seen[table] += 1
            self.counts[decision['status']] += 1
            self._span(table, 'status:' + decision['status'], index)
            for reason in decision['reasons']:
                self.reason_counts[reason] += 1; self._span(table, reason, index)
            if payload is None:
                return decision
            self.subjects.add(payload['subject'])
            if payload['experiment'] is not None:
                self.sessions.add((payload['subject'], payload['experiment']))
            if payload['condition'] is not None:
                self.conditions[payload['condition']] += 1
                group = ((payload['subject'], row['cluster_id']) if self.rule.family == 'firing_rates'
                         else (payload['subject'], payload['experiment']))
                self.group_conditions.setdefault(group, set()).add(payload['condition'])
            if payload['balanced']:
                self.balanced['selected_rows'] += 1
                self._span(table, 'balanced_selected', index)
            key = payload['key']
            if key not in self.keys:
                need(len(self.keys) < self.max_keys, 'Complete key census exceeds declared bound')
                self.keys[key] = {'tables': Counter(), 'roles': Counter(), 'first': {}, 'balanced': payload['balanced']}
            item = self.keys[key]
            # Correlation X and Y rows are distinct roles of the same join key.
            labels = tuple(payload['roles']) if self.rule.family == 'condition_correlation' else ('row',)
            for label in labels:
                cell = (table, label)
                if cell in item['first']:
                    self.duplicates.setdefault(table, set()).update((item['first'][cell], index))
                else:
                    item['first'][cell] = index
            item['tables'][table] += 1
            item['roles'].update(payload['roles'].keys())
            return decision
        except BaseException:
            self.failed = True
            raise

    def finish(self):
        need(not self.failed and not self.closed, 'Exactly one complete nonfailed census finish')
        self.closed = True
        r = self.rule
        support = {'unique_keys': len(self.keys), 'subjects': len(self.subjects),
                   'subject_experiment_pairs': len(self.sessions),
                   'condition_counts': dict(sorted(self.conditions.items())),
                   'missing_declared_condition_levels': sorted(set(r.levels) - set(self.conditions)),
                   'unexpected_condition_levels': sorted(set(self.conditions) - set(r.levels)) if r.levels else [],
                   'groups_with_all_declared_conditions': (sum(set(r.levels) <= v for v in self.group_conditions.values())
                                                          if r.levels else None)}
        if r.family == 'condition_correlation':
            support['one_to_one_complete_pairs'] = sum(v['roles']['x'] == v['roles']['y'] == 1
                                                       for v in self.keys.values())
            support['unpaired_or_ambiguous_keys'] = len(self.keys) - support['one_to_one_complete_pairs']
        if r.family == 'state_rate':
            support['unique_outer_join_response_keys'] = sum(v['roles']['value'] == 1 and
                all(n == 1 for n in v['tables'].values()) for v in self.keys.values())
            support['outer_join_keys_without_response'] = sum(v['roles']['value'] == 0 for v in self.keys.values())
        reconciled = {t: {'observed': self.seen[t], 'advertised': self.book._sizes[t],
                         'matches': self.seen[t] == self.book._sizes[t]} for t in r.tables}
        duplicate_spans = {t: intervals(v) for t, v in self.duplicates.items()}
        need(sum(len(v) for v in self.spans.values()) + sum(len(v) for v in duplicate_spans.values())
             <= self.max_intervals, 'Complete duplicate interval census exceeds declared bound')
        if r.family == 'first_novelty':
            paired = {}
            for key, item in self.keys.items():
                if item['balanced']:
                    paired.setdefault(key[0], set()).add(key[1])
            self.balanced['subjects'] = len(paired)
            self.balanced['complete_Novelty_Dual_subject_pairs'] = sum(
                {'Novelty', 'Dual'} <= v for v in paired.values())
        gates = list(r.gates)
        if duplicate_spans: gates.append('duplicate_model_or_join_keys_not_deduplicated')
        if not all(v['matches'] for v in reconciled.values()): gates.append('incomplete_table_row_census')
        if self.counts['unresolved']: gates.append('unresolved_row_domain_or_schema')
        report = {'source_analysis_id': r.identifier, 'family': r.family,
                  'rows_observed_by_table': reconciled, 'row_status_counts': dict(self.counts),
                  'reason_counts': dict(sorted(self.reason_counts.items())),
                  'row_index_intervals': {t: {reason: spans for (table, reason), spans in self.spans.items()
                                             if table == t} for t in r.tables},
                  'interval_convention': 'zero-based half-open original table positions',
                  'duplicate_affected_rows': {t: len(v) for t, v in self.duplicates.items()},
                  'duplicate_row_index_intervals': duplicate_spans, 'support': support,
                  'balanced_subview': dict(self.balanced) if r.family == 'first_novelty' else None,
                  'source_schema': self.book.assess_schema(r.identifier),
                  'unresolved_gates': gates, 'census_rows_complete': all(v['matches'] for v in reconciled.values()),
                  'fit_executed': False, 'scientific_qualification': False,
                  'input_rows_mutated_or_discarded': False}
        return report


def build_rules(family_ledger, input_ledger):
    need(BALANCED_SUBJECTS is not None and len(BALANCED_SUBJECTS) == 5,
         "Admitted complete private cohort policy required")
    need(type(family_ledger) is dict and family_ledger.get('schema') == 'findlay-published98-exact-family-join/v1',
         'Selected published-family ledger schema')
    need(type(input_ledger) is dict and input_ledger.get('schema') == 'findlay-full-input-contract/v1',
         'Selected complete input ledger schema')
    rows, members = family_ledger.get('rows'), input_ledger.get('members')
    need(type(rows) is list and len(rows) == 98 and all(type(r) is dict for r in rows), 'All 98 source families')
    ids = [r.get('source_analysis_id') for r in rows]
    need(all(type(x) is str for x in ids) and len(set(ids)) == 98 and set(ids) == EXPECTED_IDS,
         'Exact unique published source-analysis identities')
    need(Counter(x.split(':')[0] for x in ids) == dict(EXPECTED_FAMILY_COUNTS), 'Exact family counts')
    need(type(members) is list, 'Complete source input members')
    schemas, sizes = {}, {}
    for member in members:
        need(type(member) is dict and type(member.get('path')) is str, 'Typed member metadata')
        table = member['path']
        if not table.endswith('.pqt'):
            continue
        need(table in EXPECTED_TABLES and table not in schemas, 'Exact unique Parquet table')
        fields, size = member.get('columns'), member.get('footer_advertised_rows')
        need(type(fields) is list and len(fields) == len(set(fields)) and
             all(type(f) is str and 0 < len(f) <= 256 for f in fields), 'Exact footer field names')
        need(type(size) is int and 0 <= size <= 2000000, 'Bounded advertised table row count')
        schemas[table], sizes[table] = tuple(fields), size
    need(set(schemas) == EXPECTED_TABLES, 'All 13 input tables retained in contract')
    rules = {}
    for row in rows:
        need(type(row.get('source_parameters')) is dict and type(row.get('input_tables')) is list,
             'Source parameter and input-table records')
        rule = _rule(row, schemas)
        rules[rule.identifier] = rule
    return RuleBook(rules, schemas, sizes)
