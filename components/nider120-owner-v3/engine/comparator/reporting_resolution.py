"""Numeric-only author-table reporting resolution; definitions, no I/O/fits.

The official extractMAinfo function prints these nine real fields per contrast.
This is a source-table precision criterion, not evidence of paper scale parity,
cross-language binary identity or accuracy for unreported diagnostic quantities.
Exact halfway values are indeterminate: no dependency on platform sprintf ties.
"""
from fractions import Fraction

DECIMALS = {'random_z_estimate':2, 'random_z_lower':2, 'random_z_upper':2,
            'random_z_p':3, 'tau':2, 'lower_tau':2, 'upper_tau':2, 'Q':2, 'p_Q':3}
COUNTS = frozenset(('df_Q','k','k_all','k_TE','k_study','N_author_sum','submitted_rows'))


def rational(value):
    return {'numerator':str(value.numerator),'denominator':str(value.denominator)}


def units(field):
    if field=='df_Q':return 'degrees_of_freedom'
    if field=='N_author_sum':return 'sum_of_source_sample_sizes_not_unique_participants'
    if field=='submitted_rows':return 'post_merge_input_rows'
    if field in COUNTS:return 'native_study_count_not_verified_independent_cohorts'
    if field.endswith('_p') or field=='p_Q':return 'probability'
    if field in ('I2','lower_I2','upper_I2'):return 'fraction_not_percent'
    if '_r_' in field:return 'correlation'
    if field.endswith('_statistic') or field in ('Q','H','lower_H','upper_H'):return 'dimensionless_statistic'
    if field in ('tau2','se_tau2','lower_tau2','upper_tau2'):return 'Fisher_z_squared'
    if '_z_' in field or field in ('tau','lower_tau','upper_tau'):return 'Fisher_z'
    raise ValueError('explicit_units_required')


def continuous(actual,expected,actual_state,expected_state,field):
    result={'units':units(field),'candidate_state':actual_state,'reference_state':expected_state}
    if actual is None or expected is None:
        result.update(state='UNDEFINED',signed_error=None,absolute_error=None,relative_absolute_error=None)
    else:
        if type(actual) is not Fraction or type(expected) is not Fraction:
            raise ValueError('validated_exact_numeric_values_required')
        delta=actual-expected
        result.update(state='FINITE',signed_error=rational(delta),absolute_error=rational(abs(delta)),
                      relative_absolute_error=(None if expected==0 else rational(abs(delta)/abs(expected))),
                      relative_state=('UNDEFINED_ZERO_REFERENCE' if expected==0 else 'FINITE'))
    return result


def bin_index(value, decimals):
    if type(value) is not Fraction or type(decimals) is not int or decimals not in (2,3):
        raise ValueError('exact_rational_and_source_precision_required')
    scaled = value * 10**decimals
    floor = scaled.numerator // scaled.denominator
    displacement = scaled - floor
    if displacement == Fraction(1,2):
        return None
    return floor + int(displacement > Fraction(1,2))


def compare_validated(candidate, reference):
    """Consume the unchanged extended_score.validate mappings; no file loading.

    Caller must authenticate complete reference/input/arm and validate both first.
    All120 fields carry continuous errors or explicit undefined states. Binary
    qualification of72 nonreported real fields remains held. Matching nonfinite
    states never produces an agreement. Metadata mismatches are separate failures.
    """
    ids=('quest_self','amy_quest','amy_self')
    if set(candidate)!=set(ids) or set(reference)!=set(ids):
        raise ValueError('complete_three_contrast_universe')
    outcomes=[]
    for name in ids:
        cr,cv=candidate[name];rr,rv=reference[name]
        if set(cv)!=set(rv) or len(cv)!=40:
            raise ValueError('complete_40_field_universe')
        metadata=all(cr[k]==rr[k] for k in ('settings','tau_interval','membership'))
        for field in rv:
            actual,expected=cv[field],rv[field]
            if field not in COUNTS and field not in DECIMALS:
                status='HELD_UNREPORTED_DIAGNOSTIC'
            elif actual is None or expected is None:
                status='INDETERMINATE_UNDEFINED_VALUE'
            elif field in COUNTS:
                if any(type(v) is not Fraction or v.denominator!=1 or v<0 for v in (actual,expected)):
                    raise ValueError('validated_nonnegative_integer_required')
                status='EXACT_COUNT_AGREEMENT' if actual==expected else 'COUNT_DISAGREEMENT'
            else:
                a=bin_index(actual,DECIMALS[field]);r=bin_index(expected,DECIMALS[field])
                status=('INDETERMINATE_REPORTING_BOUNDARY' if a is None or r is None else
                        'AUTHOR_TABLE_BIN_AGREEMENT' if a==r else 'AUTHOR_TABLE_BIN_DISAGREEMENT')
            outcomes.append({'contrast':name,'field':field,'status':status,
                             'continuous_error':continuous(actual,expected,cr['fields'][field]['state'],
                                                           rr['fields'][field]['state'],field),
                             'exact_metadata_agreement':metadata})
    return {'schema':'nider_author_table_numeric_resolution_result_v1','cells':outcomes,
            'caller_reference_authentication_required':True,'paper_scale_parity_established':False,
            'full_120_binary_endpoint_qualified':False,'held_binary_real_cells':72,
            'continuous_total_fields':120,'continuous_fields_excluded':0,
            'aggregate_binary_pass_defined':False}


def boundary_control_definitions():
    """Explicit invented controls for a later selected no-fit invocation."""
    return [
      ('positive_inside',Fraction(234,10000),2,2),
      ('positive_upper_neighbor',Fraction(251,10000),2,3),
      ('positive_exact_boundary',Fraction(25,1000),2,None),
      ('negative_inside',Fraction(-234,10000),2,-2),
      ('negative_lower_neighbor',Fraction(-251,10000),2,-3),
      ('negative_exact_boundary',Fraction(-25,1000),2,None),
      ('zero',Fraction(0),2,0),
      ('three_digit_inside',Fraction(2344,100000),3,23),
      ('three_digit_upper_neighbor',Fraction(2351,100000),3,24),
      ('three_digit_exact_boundary',Fraction(235,10000),3,None)]
