"""Complete-cohort literal-label support counts; no atlas or scientific score.

The controller authenticates the exact compressed and decoded map identities.
This pure component independently validates every declared session/unit before
returning any report. Sparse rows mean exact zeros against explicit full rosters.
"""
import math

POLICY = 'guarded_global_one_based_peak_channel_v1'
POLICY_SHA256 = '2d04ea3db1f7a6f3c406631236866e8a7285350f95a04f9d406d81b86fe82ee1'
CATALOG_SHA256 = '55745fc5f68ae31979487f21c23296bafa13551bfffacf75f07d53451e46ef63'
TOTALS = {'sessions': 39, 'mice': 10, 'unit_count': 33997,
          'source_cluster_rows': 48661, 'channel_count': 34408}
FALSE_FLAGS = ('anatomical_ground_truth_established', 'historical_paper_producer_recovered',
               'region_keys_or_atlas_policy_selected', 'equal_unit_budgets_or_subsets_selected',
               'candidate_exposure_selected', 'regional_scoring_ready', 'scientific_performance_computed')
TOP_KEYS = {'schema', 'policy', 'policy_decision_sha256', 'input_manifest_sha256',
            'sessions', 'totals', 'prospective_g1_row_mapping_performed', *FALSE_FLAGS}
EXPECTED_KEYS = {'ordinal', 'session', 'mouse', 'unit_count', 'source_cluster_rows', 'channel_count'}
SESSION_KEYS = {*EXPECTED_KEYS, 'authenticated_identity_json_bytes',
                'authenticated_identity_json_sha256', 'units'}
UNIT_KEYS = {'session', 'mouse', 'unit', 'source_cluster_row', 'source_qc_code',
             'source_peak_channel', 'cluster_source_probe', 'global_channel_row',
             'channel_source_probe', 'allen_ontology_raw', 'allen_ontology_stripped',
             'ccf_coordinate_text_um', 'coordinate_is_finite'}
COORD_KEYS = {'ccf_ap', 'ccf_dv', 'ccf_lr'}


class CensusRefused(ValueError):
    """Whole-cohort failure; messages do not expose private identities/labels."""


def need(ok, code):
    if not ok:
        raise CensusRefused(code)


def integer(value, code, maximum=2**53 - 1):
    need(type(value) is int and 0 <= value <= maximum, code)
    return value


def fraction(numerator, denominator):
    integer(numerator, 'fraction_numerator'); integer(denominator, 'fraction_denominator')
    need(numerator <= denominator, 'fraction_support')
    return {'numerator': numerator, 'denominator': denominator,
            'status': 'undefined_zero_denominator' if denominator == 0 else 'defined'}


def _roster(rows, totals):
    need(type(rows) is list and 0 < len(rows) <= 39 and type(totals) is dict
         and set(totals) == set(TOTALS), 'complete_roster_shape')
    for n in totals.values(): integer(n, 'roster_total')
    need(len(rows) == totals['sessions'], 'complete_session_count')
    sessions, mice, sums = set(), [], dict.fromkeys(('unit_count', 'source_cluster_rows', 'channel_count'), 0)
    for ordinal, row in enumerate(rows, 1):
        need(type(row) is dict and set(row) == {'expected', 'decoded_metadata_json_bytes',
             'decoded_metadata_json_sha256', 'metadata_gzip'}, 'catalog_member_fields')
        e = row['expected']
        need(type(e) is dict and set(e) == EXPECTED_KEYS, 'expected_fields')
        need(type(e['ordinal']) is int and e['ordinal'] == ordinal, 'ordered_roster')
        need(all(type(e[k]) is str and 0 < len(e[k]) <= 256 for k in ('session', 'mouse')), 'roster_identity')
        need(e['session'] not in sessions, 'duplicate_session'); sessions.add(e['session'])
        if e['mouse'] not in mice: mice.append(e['mouse'])
        for k in sums: sums[k] += integer(e[k], 'roster_count')
        need(e['unit_count'] <= e['source_cluster_rows'], 'retained_source_count')
        need(integer(row['decoded_metadata_json_bytes'], 'identity_json_extent', 2097152) > 0, 'positive_identity_extent')
        digest = row['decoded_metadata_json_sha256']
        need(type(digest) is str and len(digest) == 64
             and all(c in '0123456789abcdef' for c in digest), 'identity_json_digest')
    need(len(mice) == totals['mice'] and all(sums[k] == totals[k] for k in sums), 'complete_roster_totals')
    return mice


def _support(counts):
    """Counts include explicit zero rows for all original groups."""
    triples = [(v[0], v[1], v[0] + v[1]) for v in counts]
    columns = list(zip(*triples))
    return {'denominator_groups': len(counts),
            'positive_groups': [sum(v > 0 for v in col) for col in columns],
            'minimum_over_all_groups': [min(col) for col in columns],
            'minimum_over_positive_groups': [min((v for v in col if v > 0), default=None) for col in columns]}


def _summarize(record, rows, totals, tick=lambda: None):
    """Generic pure kernel for invented controls; public entry fixes full39."""
    mice = _roster(rows, totals); mouse_index = {m: i for i, m in enumerate(mice)}
    need(type(record) is dict and set(record) == TOP_KEYS, 'mapping_fields')
    need(record['schema'] == 'neural094-prospective-guarded-g1-literal-region-map-v1'
         and record['policy'] == POLICY and record['policy_decision_sha256'] == POLICY_SHA256
         and record['input_manifest_sha256'] == CATALOG_SHA256, 'mapping_policy_identity')
    need(type(record['totals']) is dict and set(record['totals']) == set(totals)
         and all(type(record['totals'][k]) is int and record['totals'][k] == v for k, v in totals.items()),
         'mapping_exact_totals')
    need(record['prospective_g1_row_mapping_performed'] is True
         and all(record[k] is False for k in FALSE_FLAGS), 'mapping_unselected_consequences')
    members = record['sessions']
    need(type(members) is list and len(members) == len(rows), 'complete_session_list')
    # These maps remain private locals until every session/unit has validated.
    labels = {}; session_qc = []; mouse_qc = [[0, 0] for _ in mice]; all_qc = [0, 0]
    for ordinal, (member, row) in enumerate(zip(members, rows, strict=True), 1):
        tick(); e = row['expected']; mi = mouse_index[e['mouse']]
        need(type(member) is dict and set(member) == SESSION_KEYS, 'mapped_session_fields')
        need(all(type(member[k]) is type(v) and member[k] == v for k, v in e.items()), 'exact_session_join')
        need(type(member['authenticated_identity_json_bytes']) is int
             and member['authenticated_identity_json_bytes'] == row['decoded_metadata_json_bytes']
             and member['authenticated_identity_json_sha256'] == row['decoded_metadata_json_sha256'],
             'source_identity_json_join')
        units = member['units']; need(type(units) is list and len(units) == e['unit_count'], 'complete_unit_count')
        sq = [0, 0]; last = -1
        for alias, unit in enumerate(units):
            if alias % 128 == 0: tick()
            need(type(unit) is dict and set(unit) == UNIT_KEYS, 'mapped_unit_fields')
            need(type(unit['session']) is str and unit['session'] == e['session']
                 and type(unit['mouse']) is str and unit['mouse'] == e['mouse'], 'unit_session_join')
            need(type(unit['unit']) is int and unit['unit'] == alias, 'dense_unique_aliases')
            sr = integer(unit['source_cluster_row'], 'source_cluster_row')
            need(last < sr < e['source_cluster_rows'], 'ordered_unique_source_rows'); last = sr
            qc = integer(unit['source_qc_code'], 'QC_code', 3); need(qc in (2, 3), 'QC2_or_QC3')
            p = integer(unit['source_peak_channel'], 'peak_channel')
            g = integer(unit['global_channel_row'], 'global_channel_row')
            cp = integer(unit['cluster_source_probe'], 'cluster_probe')
            hp = integer(unit['channel_source_probe'], 'channel_probe')
            need(1 <= p <= e['channel_count'] and g == p - 1 and cp == hp, 'guarded_G1_probe_join')
            raw, stripped = unit['allen_ontology_raw'], unit['allen_ontology_stripped']
            need(type(raw) is str and type(stripped) is str and stripped == raw.strip(), 'literal_label_pair')
            coords, finite = unit['ccf_coordinate_text_um'], unit['coordinate_is_finite']
            need(type(coords) is dict and type(finite) is dict and set(coords) == set(finite) == COORD_KEYS,
                 'coordinate_fields')
            for key in COORD_KEYS:
                need(type(coords[key]) is str and type(finite[key]) is bool, 'coordinate_metadata_type')
                try: actual_finite = math.isfinite(float(coords[key]))
                except (ValueError, OverflowError): raise CensusRefused('coordinate_metadata_number') from None
                need(finite[key] is actual_finite, 'coordinate_finiteness_join')
            qi = qc - 2; sq[qi] += 1; mouse_qc[mi][qi] += 1; all_qc[qi] += 1
            entry = labels.setdefault(raw, {'stripped': stripped, 'qc': [0, 0], 'session': {}, 'mouse': {}})
            entry['qc'][qi] += 1
            entry['session'].setdefault(ordinal, [0, 0])[qi] += 1
            entry['mouse'].setdefault(mi, [0, 0])[qi] += 1
        session_qc.append(sq)
    need(sum(all_qc) == totals['unit_count'], 'complete_counted_unit_total')
    tick(); result = []
    for raw in sorted(labels):
        tick(); entry = labels[raw]; qc = entry['qc']; triple = [*qc, sum(qc)]
        result.append({'raw_label': raw, 'stripped_label_metadata': entry['stripped'], 'unit_counts': triple,
            'fraction_of_all_units_in_QC_group': [fraction(n, d) for n, d in zip(triple, [*all_qc, sum(all_qc)], strict=True)],
            'session_counts': [[i, *v] for i, v in sorted(entry['session'].items())],
            'mouse_counts': [[i, *v] for i, v in sorted(entry['mouse'].items())],
            'session_support': _support([entry['session'].get(i, [0, 0]) for i in range(1, len(rows) + 1)]),
            'mouse_support': _support([entry['mouse'].get(i, [0, 0]) for i in range(len(mice))])})
    tick()
    return {'schema': 'neural094_literal_region_support_census_v1', 'policy': POLICY,
            'cohort': dict(totals), 'counted_units_by_QC': [*all_qc, sum(all_qc)],
            'literal_raw_labels': len(result),
            'count_columns': ['QC2', 'QC3', 'QC2_plus_QC3'],
            'sparse_count_columns': ['original_session_ordinal_or_zero_based_mouse_index', 'QC2', 'QC3'],
            'zero_rule': 'Every omitted session or mouse entry is exactly [0,0] against the complete rosters below; zeros remain in all coverage denominators and all-group minima.',
            'session_roster': [{**r['expected'], 'unit_counts': [*q, sum(q)]} for r, q in zip(rows, session_qc, strict=True)],
            'mouse_roster': [{'mouse_index': i, 'mouse': mouse, 'unit_counts': [*mouse_qc[i], sum(mouse_qc[i])]} for i, mouse in enumerate(mice)],
            'labels': result,
            'scope': {'complete_cohort_validated_before_return': True, 'raw_label_groups_only': True,
                      'unknown_empty_or_whitespace_labels_dropped': False, 'stripped_labels_merged': False,
                      'atlas_regrouping_or_anatomical_ground_truth': False, 'equal_unit_selection': False,
                      'region_exclusion': False, 'scientific_performance': False, 'candidate_exposure': False}}


def summarize_full_cohort(record, catalog, tick=lambda: None):
    """Controller must authenticate both mapping and catalog before calling."""
    need(type(catalog) is dict and catalog.get('schema') == 'neural094-nma-anatomy-diagnostic-inputs-v1'
         and catalog.get('execution_authority') is False, 'frozen_catalog_schema')
    need(type(catalog.get('totals')) is dict and all(type(v) is int for v in catalog['totals'].values())
         and catalog['totals'] == {**TOTALS, 'gzip_bytes': 980124, 'decoded_metadata_json_bytes': 17286997},
         'frozen_full39_catalog_totals')
    return _summarize(record, catalog['sessions'], TOTALS, tick)
