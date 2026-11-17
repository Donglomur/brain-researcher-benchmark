"""Quantity-level native comparison under a separately frozen independent policy."""
import math
from common import need, integer, finite, require_pin, pin

ROLES = ('A_clarified', 'B_author_code', 'operator_reference')

def validate_policy(policy, roots):
    need(type(roots) is list and len(roots) == len(set(roots)) == 37, 'all original37 root IDs')
    need(type(policy) is dict and set(policy) == {'selection_pin','root_source_pin','producer_source_pins','roots'}, 'native policy schema')
    require_pin(policy['selection_pin']); require_pin(policy['root_source_pin'])
    need(set(policy['roots']) == set(roots), 'every original native root policy')
    need(type(policy['producer_source_pins']) is dict and set(policy['producer_source_pins']) ==
         {role+'/'+root for role in ROLES for root in roots}, 'all independent producer source bindings')
    for value in policy['producer_source_pins'].values():
        require_pin(value)
    for root, quantities in policy['roots'].items():
        need(type(quantities) is dict and quantities, 'independently fixed numeric quantities')
        for name, rule in quantities.items():
            need(type(name) is str and name and type(rule) is dict and
                 set(rule) == {'kind','units','shape','support_pin','absolute_tolerance','relative_tolerance','nonfinite'},
                 'exact quantity policy')
            need(rule['kind'] in ('exact','float') and type(rule['units']) is str and rule['units'], 'units and comparison kind')
            need(type(rule['shape']) is list, 'full quantity shape')
            for d in rule['shape']: integer(d)
            require_pin(rule['support_pin'])
            atol, rtol = finite(rule['absolute_tolerance']), finite(rule['relative_tolerance'])
            need(atol >= 0 and rtol >= 0, 'nonnegative frozen tolerances')
            need(rule['kind'] == 'float' or atol == rtol == 0, 'exact quantities cannot choose tolerance')
            need(rule['nonfinite'] in ('reject','same_position_nan_and_signed_inf'), 'explicit nonfinite rule')
    return pin(policy)

def flatten(value, shape):
    if not shape:
        need(type(value) in (int,float,bool,str) or value is None, 'typed scalar')
        return [value]
    need(type(value) is list and len(value) == shape[0], 'complete original shape')
    return [v for child in value for v in flatten(child, shape[1:])]

def compare(policy, roots, panels):
    policy_pin = validate_policy(policy, roots)
    expected = {role+'/'+root for role in ROLES for root in roots}
    need(type(panels) is dict and set(panels) == expected, 'all111 original records before comparison')
    # Validate all keys/units/support/shapes first; no result-derived tolerance.
    material = {}
    for key, panel in panels.items():
        root = key.split('/',1)[1]
        need(type(panel) is dict and set(panel) == {'source_pin','quantities'}, 'native panel schema')
        require_pin(panel['source_pin'])
        need(panel['source_pin']==policy['producer_source_pins'][key], 'same independently committed native producer')
        need(set(panel['quantities']) == set(policy['roots'][root]), 'complete root quantities')
        material[key] = {}
        for name, value in panel['quantities'].items():
            rule = policy['roots'][root][name]
            need(type(value) is dict and set(value) == {'units','support_pin','values','status'}, 'quantity value schema')
            need(value['units'] == rule['units'] and value['support_pin'] == rule['support_pin'], 'same original units/support')
            need(value['status'] == 'complete', 'undefined or failed native quantity not scientific pass')
            material[key][name] = flatten(value['values'], rule['shape'])
    comparisons = {}
    for role in ROLES[:2]:
        for root in roots:
            outcomes = {}
            for name, rule in policy['roots'][root].items():
                actual, expected_values = material[role+'/'+root][name], material['operator_reference/'+root][name]
                flags = []
                for a, b in zip(actual, expected_values):
                    nonfinite_a=type(a) is float and not math.isfinite(a)
                    nonfinite_b=type(b) is float and not math.isfinite(b)
                    if nonfinite_a or nonfinite_b:
                        need(rule['nonfinite'] != 'reject', 'nonfinite native value forbidden')
                        flags.append(type(a) is float and type(b) is float and
                            ((math.isnan(a) and math.isnan(b)) or (math.isinf(a) and a==b)))
                        continue
                    if rule['kind'] == 'exact':
                        flags.append(type(a) is type(b) and a == b)
                    else:
                        need(type(a) in (int,float) and type(b) in (int,float), 'numeric quantity scalars')
                        if math.isfinite(a) and math.isfinite(b):
                            threshold=rule['absolute_tolerance']+rule['relative_tolerance']*abs(b)
                            difference=abs(a-b)
                            need(math.isfinite(threshold) and math.isfinite(difference),'finite comparator arithmetic')
                            flags.append(difference <= threshold)
                        else:
                            need(rule['nonfinite'] != 'reject', 'nonfinite native value forbidden')
                            flags.append((math.isnan(a) and math.isnan(b)) or (math.isinf(a) and a == b))
                outcomes[name] = {'passed': all(flags), 'scalars': len(flags), 'mismatches': flags.count(False)}
            comparisons[role+'/'+root] = outcomes
    return {'policy_pin': policy_pin, 'records': 111, 'comparisons': comparisons,
            'all_declared_quantities_match': all(v['passed'] for o in comparisons.values() for v in o.values()),
            'native_environment_or_historical_parity_qualified': False, 'whole_paper_reproduced': False}
