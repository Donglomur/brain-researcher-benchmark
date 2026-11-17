"""Bounded timing-report comparison; pure stdlib, no work at import.

Any implementation may submit answers. Equality does not prove signal extraction,
biological inference, or historical MATLAB equivalence. Public validation precedes
one private-reference callback; missing answers never shrink error denominators.
"""
import json
import math

ID = 'PAPER-ROOT-ADD-019'
MAX_BYTES = 1000000
TABLES = ('latency_ledger', 'correlations', 'rat_descriptions',
          'matched_rat_descriptions', 'pooled_source_comparisons')
LAT_ID = ('member', 'member_sha256', 'rat', 'sensor', 'datatype', 'cell_row1', 'cell_column1')
CURVE_ID = ('datatype', 'cell_row1', 'cell_column1')
RAT_ID = ('rat', 'sensor', 'datatype')
MATCH_ID = ('rat', 'datatype')
LAT_FIELDS = ('segment_index1', 'absolute_sample_index0', 'amplitude', 'source_latency_ms',
              'scientific_latency_ms', 'physical_grid_time_ms_separate_diagnostic', 'finite_samples', 'nan_samples')
RAT_FIELDS = ('conditions', 'defined_conditions', 'source_equal_condition_mean_ms', 'scientific_equal_condition_mean_ms')
RANK_FIELDS = ('n_DA_condition_rows', 'n_ACh_condition_rows', 'DA_rank_sum', 'DA_U',
               'normal_variance', 'normal_continuity_corrected_z', 'normal_two_sided_p')


class InvalidSubmission(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidSubmission(message)


def decode(body):
    require(type(body) is bytes and 0 < len(body) <= MAX_BYTES, 'Nonempty UTF-8 JSON at most 1000000 bytes')
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, 'Duplicate JSON key')
            out[k] = v
        return out
    def constant(_):
        raise InvalidSubmission('NaN and infinity literals are forbidden; use null')
    try:
        obj = json.loads(body.decode('utf-8', errors='strict'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise InvalidSubmission('Malformed bounded UTF-8 JSON') from error
    def walk(x, depth=0):
        require(depth <= 12, 'JSON depth exceeds 12')
        if isinstance(x, dict):
            for k, v in x.items():
                require(type(k) is str and len(k) <= 100, 'Bounded object key'); walk(v, depth+1)
        elif isinstance(x, list):
            require(len(x) <= 1000, 'Array exceeds 1000 items')
            for v in x: walk(v, depth+1)
        elif isinstance(x, str): require(len(x) <= 300, 'String exceeds 300 characters')
        elif type(x) in (int, float):
            try: require(math.isfinite(x), 'Finite JSON numbers required')
            except OverflowError as error: raise InvalidSubmission('Number outside finite range') from error
        else: require(x is None or type(x) is bool, 'Unsupported scalar')
    walk(obj)
    return obj


def keys(row, wanted):
    require(type(row) is dict and set(row) == set(wanted), 'Exact object fields required')


def numeric(value, integer=False, low=None, high=None):
    if value is None: return
    require(type(value) is int if integer else type(value) in (int, float), 'Numeric answer or null required')
    require(math.isfinite(value), 'Finite answers only')
    if low is not None: require(value >= low, 'Value below declared domain')
    if high is not None: require(value <= high, 'Value above declared domain')


def vector(value, length, integer=False, low=None, high=None):
    require(type(value) is list and len(value) == length, 'Full fixed vector required; null entries preserve coverage')
    for x in value: numeric(x, integer, low, high)


def indexed(rows, roster, fields):
    require(type(rows) is list and len(rows) == len(roster), 'All externally declared identities are required')
    out = {}
    for row in rows:
        require(type(row) is dict, 'Row object required')
        try: key = tuple(row[f] for f in fields); hash(key)
        except (KeyError, TypeError) as error: raise InvalidSubmission('Malformed row identity') from error
        require(key not in out, 'Duplicate row identity'); out[key] = row
    expected = {tuple(row[f] for f in fields) for row in roster}
    require(set(out) == expected, 'Row identities differ from external public roster')
    ordered = [out[tuple(row[f] for f in fields)] for row in roster]
    for actual, expected_row in zip(ordered, roster):
        require(all(type(actual[f]) is type(expected_row[f]) for f in fields), 'Exact identity scalar types; booleans are not indices')
    return ordered


def validate(obj, contract):
    keys(obj, ('schema_version', 'candidate_id', 'submission_status') + TABLES)
    require(obj['schema_version'] == 1 and type(obj['schema_version']) is int and obj['candidate_id'] == ID, 'Task/schema identity')
    require(obj['submission_status'] in ('complete', 'partial', 'abstain'), 'Explicit submission status')
    if obj['submission_status'] == 'abstain':
        require(all(obj[t] == [] for t in TABLES), 'Abstention uses five empty tables')
        return obj
    result = dict(obj)
    for table, fields in [('latency_ledger', LAT_ID), ('correlations', CURVE_ID),
                          ('rat_descriptions', RAT_ID), ('matched_rat_descriptions', MATCH_ID),
                          ('pooled_source_comparisons', ('datatype',))]:
        result[table] = indexed(obj[table], contract['rosters'][table], fields)
    for r in result['latency_ledger']:
        keys(r, LAT_ID + ('status',) + LAT_FIELDS)
        require(r['status'] in ('defined', 'all_nan_scientific_latency_undefined', 'abstained'), 'Latency status')
        for f in LAT_FIELDS: numeric(r[f], f in ('segment_index1', 'absolute_sample_index0', 'finite_samples', 'nan_samples'))
        numeric(r['segment_index1'], True, 1, 242); numeric(r['absolute_sample_index0'], True, 2409, 2650)
        numeric(r['finite_samples'], True, 0, 242); numeric(r['nan_samples'], True, 0, 242)
    for r in result['correlations']:
        keys(r, CURVE_ID + ('status', 'lags_samples', 'values', 'pointwise_rat_counts'))
        require(r['status'] in ('defined', 'undefined_nonfinite_average', 'undefined_zero_or_overflow_energy', 'abstained'), 'Curve status')
        require(r['lags_samples'] == contract['lags_samples'] and all(type(v) is int for v in r['lags_samples']), 'Exact 483 lag identities')
        vector(r['values'], 483)
        keys(r['pointwise_rat_counts'], ('DA', 'ACh'))
        for v in r['pointwise_rat_counts'].values(): vector(v, 290, True, 0, 10)
    for r in result['rat_descriptions']:
        keys(r, RAT_ID + RAT_FIELDS)
        for f in RAT_FIELDS: numeric(r[f], f in ('conditions', 'defined_conditions'))
        numeric(r['conditions'], True, 0, 4); numeric(r['defined_conditions'], True, 0, 4)
    for r in result['matched_rat_descriptions']:
        keys(r, MATCH_ID + ('DA_minus_ACh_ms',)); numeric(r['DA_minus_ACh_ms'])
    for r in result['pooled_source_comparisons']:
        keys(r, ('datatype', 'source_literal_pooled_DA_ms', 'source_literal_pooled_ACh_ms',
                 'source_literal_pooled_mean_DA_minus_ACh_ms', 'ranks'))
        n = contract['pooled_rows_per_sensor'][r['datatype']]
        for sensor in ('DA', 'ACh'): vector(r['source_literal_pooled_'+sensor+'_ms'], n)
        numeric(r['source_literal_pooled_mean_DA_minus_ACh_ms'])
        keys(r['ranks'], RANK_FIELDS + ('tie_group_sizes', 'normal_status'))
        for f in RANK_FIELDS: numeric(r['ranks'][f], f.startswith('n_'))
        ties = r['ranks']['tie_group_sizes']
        require(ties is None or (type(ties) is list and 0 < len(ties) <= 2*n), 'Tie counts or explicit null')
        if ties is not None:
            for v in ties: numeric(v, True, 1, 2*n)
            require(all(v is not None for v in ties), 'Tie list entries are integers')
        require(r['ranks']['normal_status'] in ('defined', 'undefined_zero_rank_variance', 'abstained'), 'Rank status')
    return result


def family(pairs):
    """No mean over only answered items: any missing expected answer nulls the mean."""
    total = len(pairs); defined = sum(b is not None for a, b in pairs)
    missing = sum(a is None and b is not None for a, b in pairs)
    unexpected = sum(a is not None and b is None for a, b in pairs)
    errors = []; unsupported = False
    for a, b in pairs:
        if a is not None and b is not None:
            try:
                d = abs(a-b)
                if not math.isfinite(d): unsupported = True
                else: errors.append(d)
            except (OverflowError, ValueError): unsupported = True
    complete = missing == 0 and unexpected == 0 and not unsupported
    # Divide before summing; hypot avoids intermediate square overflow.
    mae = math.fsum(d/defined for d in errors) if complete and defined else None
    rmse = math.hypot(*(d/math.sqrt(defined) for d in errors)) if complete and defined else None
    return {'declared_values': total, 'reference_numeric_values': defined,
            'answered_reference_numeric_values': defined-missing, 'missing_expected_values': missing,
            'unexpected_numeric_for_undefined': unexpected, 'complete': complete,
            'MAE': mae, 'RMSE': rmse, 'maximum_absolute_error': max(errors) if complete and errors else None,
            'unsupported_derived_arithmetic': unsupported}


def consistency(candidate, contract):
    """Own-report identities only; cannot check extrema or correlations against signals."""
    failures = []; checked = 0; skipped = 0
    def relation(name, actual, expected):
        nonlocal checked, skipped
        if actual is None or expected is None: skipped += 1; return
        checked += 1
        if type(actual) is str or type(expected) is str: same = actual == expected
        else: same = math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-8)
        if not same: failures.append(name)
    dt = contract['sample_interval_seconds']
    ledger = candidate['latency_ledger']
    for i, row in enumerate(ledger):
        n = row['segment_index1']
        relation(f'row{i}:absolute_index', row['absolute_sample_index0'], None if n is None else 2409+n-1)
        relation(f'row{i}:source_ms', row['source_latency_ms'], None if n is None else n*dt*1000)
        relation(f'row{i}:physical_ms', row['physical_grid_time_ms_separate_diagnostic'], None if n is None else (-5+(2409+n-1)*15/7228)*1000)
        relation(f'row{i}:coverage', None if row['finite_samples'] is None or row['nan_samples'] is None else row['finite_samples']+row['nan_samples'], 242)
        if row['status'] == 'defined': relation(f'row{i}:scientific_ms', row['scientific_latency_ms'], row['source_latency_ms'])
        elif row['status'] == 'all_nan_scientific_latency_undefined':
            relation(f'row{i}:all_nan_index', n, 1)
            relation(f'row{i}:all_nan_support', row['finite_samples'], 0)
            checked += 1
            if row['scientific_latency_ms'] is not None or row['amplitude'] is not None: failures.append(f'row{i}:undefined_scientific_value')
    for i, row in enumerate(candidate['rat_descriptions']):
        own = [v for v in ledger if all(v[k] == row[k] for k in RAT_ID)]
        relation(f'rat{i}:conditions', row['conditions'], len(own))
        relation(f'rat{i}:defined_conditions', row['defined_conditions'], sum(v['status']=='defined' for v in own))
        for source, target in [('source_latency_ms','source_equal_condition_mean_ms'), ('scientific_latency_ms','scientific_equal_condition_mean_ms')]:
            values = [v[source] for v in own]
            mean = math.fsum(v/len(values) for v in values) if values and all(v is not None for v in values) else None
            relation(f'rat{i}:{target}', row[target], mean)
    rats = {(r['rat'], r['sensor'], r['datatype']):r for r in candidate['rat_descriptions']}
    for i, row in enumerate(candidate['matched_rat_descriptions']):
        a = rats[(row['rat'],'DA',row['datatype'])]['scientific_equal_condition_mean_ms']
        b = rats[(row['rat'],'ACh',row['datatype'])]['scientific_equal_condition_mean_ms']
        relation(f'matched{i}',row['DA_minus_ACh_ms'],None if a is None or b is None else a-b)
    for row in candidate['pooled_source_comparisons']:
        for sensor in ('DA','ACh'):
            values = [r['source_latency_ms'] for r in ledger if r['sensor']==sensor and r['datatype']==row['datatype']]
            for i,(a,b)in enumerate(zip(row['source_literal_pooled_'+sensor+'_ms'],values)):relation(f'pool:{row["datatype"]}:{sensor}:{i}',a,b)
        da,ach=row['source_literal_pooled_DA_ms'],row['source_literal_pooled_ACh_ms']
        if all(v is not None for v in da+ach):
            relation('pooled_signed_mean',row['source_literal_pooled_mean_DA_minus_ACh_ms'],math.fsum(v/len(da)for v in da)-math.fsum(v/len(ach)for v in ach))
        else: skipped+=1
        relation('rank_n_DA',row['ranks']['n_DA_condition_rows'],len(da));relation('rank_n_ACh',row['ranks']['n_ACh_condition_rows'],len(ach))
        ties=row['ranks']['tie_group_sizes']
        if ties is None:skipped+=1
        else:relation('tie_total',sum(ties),len(da)+len(ach))
    return {'checked_relations':checked,'skipped_missing_relations':skipped,'failures':len(failures),'first_30':failures[:30],
            'meaning':'Own-report arithmetic only; no signal-grounded correctness or extraction provenance inferred.'}


def compare(candidate, reference, contract):
    errors={}; status={}
    def add(name, pairs):errors[name]=family(pairs)
    for f in LAT_FIELDS:
        add('latency.'+f,[(a[f],b[f])for a,b in zip(candidate['latency_ledger'],reference['latency_ledger'])])
    # Primary latency errors have four equally weighted sensor x datatype strata.
    primary={}
    for sensor in ('DA','ACh'):
        for datatype in ('volume','delay'):
            pairs=[(a['source_latency_ms'],b['source_latency_ms'])for a,b in zip(candidate['latency_ledger'],reference['latency_ledger'])if b['sensor']==sensor and b['datatype']==datatype]
            primary[sensor+':'+datatype]=family(pairs)
    primary_complete=all(v['complete'] and v['MAE'] is not None for v in primary.values())
    for table in ('latency_ledger','correlations'):
        status[table]={'declared_rows':len(reference[table]),'mismatches':sum(a['status']!=b['status']for a,b in zip(candidate[table],reference[table]))}
    add('correlation.full_curve',[(x,y)for a,b in zip(candidate['correlations'],reference['correlations'])for x,y in zip(a['values'],b['values'])])
    for sensor in ('DA','ACh'):
        add('correlation.support_'+sensor,[(x,y)for a,b in zip(candidate['correlations'],reference['correlations'])for x,y in zip(a['pointwise_rat_counts'][sensor],b['pointwise_rat_counts'][sensor])])
    curve_details=[{'identity':{k:b[k]for k in CURVE_ID},'error':family(list(zip(a['values'],b['values'])))}for a,b in zip(candidate['correlations'],reference['correlations'])]
    for f in RAT_FIELDS:add('rat.'+f,[(a[f],b[f])for a,b in zip(candidate['rat_descriptions'],reference['rat_descriptions'])])
    add('matched.DA_minus_ACh_ms',[(a['DA_minus_ACh_ms'],b['DA_minus_ACh_ms'])for a,b in zip(candidate['matched_rat_descriptions'],reference['matched_rat_descriptions'])])
    for datatype in ('volume','delay'):
        a=next(x for x in candidate['pooled_source_comparisons']if x['datatype']==datatype);b=next(x for x in reference['pooled_source_comparisons']if x['datatype']==datatype)
        for sensor in ('DA','ACh'):add('pooled.'+datatype+'.'+sensor,list(zip(a['source_literal_pooled_'+sensor+'_ms'],b['source_literal_pooled_'+sensor+'_ms'])))
        add('pooled.'+datatype+'.signed_mean',[(a['source_literal_pooled_mean_DA_minus_ACh_ms'],b['source_literal_pooled_mean_DA_minus_ACh_ms'])])
        for f in RANK_FIELDS:add('rank.'+datatype+'.'+f,[(a['ranks'][f],b['ranks'][f])])
        status['rank.'+datatype]={'status_matches':a['ranks']['normal_status']==b['ranks']['normal_status'],'tie_groups_match':a['ranks']['tie_group_sizes']==b['ranks']['tie_group_sizes']}
    return {'candidate_id':ID,'status':'scored','primary_metric':{'name':'equal_sensor_datatype_source_latency_MAE_ms','value':math.fsum(v['MAE']/4 for v in primary.values())if primary_complete else None,'complete':primary_complete,'strata':primary},'errors':errors,'status_agreement':status,'curve_details':curve_details,'own_consistency':consistency(candidate,contract),'scientific_success':None,'historical_MATLAB_rank_or_SEM_parity_established':False,'signal_extraction_or_program_provenance_verified':False}


def grade(body, contract, load_reference):
    try:candidate=validate(decode(body),contract)
    except (InvalidSubmission,TypeError,KeyError,OverflowError,RecursionError) as error:
        return {'candidate_id':ID,'status':'invalid_submission','reason':str(error)[:180],'private_reference_reads':0}
    if candidate['submission_status']=='abstain':
        return {'candidate_id':ID,'status':'abstained','private_reference_reads':0,'primary_metric':{'name':'equal_sensor_datatype_source_latency_MAE_ms','value':None,'complete':False},'coverage':{'answered_latency_rows':0,'required_latency_rows':120,'answered_curves':0,'required_curves':6},'scientific_success':None}
    try:
        reference=validate(decode(load_reference()),contract)
        if reference['submission_status']!='complete':raise ValueError('Trusted reference must be complete')
    except Exception as error:
        return {'candidate_id':ID,'status':'operator_error','reason':'Invalid trusted reference: '+type(error).__name__,'private_reference_reads':1}
    try:result=compare(candidate,reference,contract)
    except (ArithmeticError,ValueError) as error:
        return {'candidate_id':ID,'status':'unsupported_derived_numerics','reason':type(error).__name__,'private_reference_reads':1,'scientific_success':None}
    result['private_reference_reads']=1
    result['submission_status_claim']=candidate['submission_status']
    result['all_numeric_families_complete']=all(x['complete']for x in result['errors'].values())
    return result
